"""Regression tests for MCP deployment-model drift detection."""

from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIFT_SCRIPT = ROOT / "scripts" / "drift-detect.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_drift_detect_flags_docker_systemd_conflicts_and_orphans(tmp_path: Path) -> None:
    home = tmp_path / "home"
    user_units = home / ".config" / "systemd" / "user"
    user_units.mkdir(parents=True)
    (user_units / "mcp-second-opinion.service").write_text("[Service]\nExecStart=fake\n", encoding="utf-8")
    (user_units / "mcp-playwright-persistent.service").write_text("[Service]\nExecStart=fake\n", encoding="utf-8")
    (user_units / "mcp-coordination.service").write_text("[Service]\nExecStart=fake\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "uv",
        """
        #!/usr/bin/env bash
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "docker",
        """
        #!/usr/bin/env bash
        if [[ "$1" == "--version" ]]; then
          echo "Docker version 26.0.0"
          exit 0
        fi
        if [[ "$1" == "compose" && "$2" == "version" ]]; then
          echo "Docker Compose version v2.27.0"
          exit 0
        fi
        if [[ "$1" == "compose" && "$*" == *" ps "* ]]; then
          echo "mcp-second-opinion:Up (healthy)"
          echo "mcp-playwright-persistent:Up (healthy)"
          exit 0
        fi
        if [[ "$1" == "ps" ]]; then
          echo "mcp-second-opinion:Up 2 hours (healthy)"
          echo "mcp-playwright-persistent:Up 2 hours (healthy)"
          exit 0
        fi
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "systemctl",
        """
        #!/usr/bin/env bash
        args="$*"
        if [[ "$args" == *"is-active mcp-second-opinion"* ]]; then
          echo "active"
          exit 0
        fi
        if [[ "$args" == *"is-active mcp-playwright-persistent"* ]]; then
          echo "failed"
          exit 3
        fi
        if [[ "$args" == *"is-active mcp-coordination"* ]]; then
          echo "activating"
          exit 3
        fi
        if [[ "$args" == *"is-active"* ]]; then
          echo "inactive"
          exit 3
        fi
        if [[ "$args" == *"list-units"* ]]; then
          echo "mcp-second-opinion.service loaded active running fake"
          echo "mcp-playwright-persistent.service loaded failed failed fake"
          echo "mcp-coordination.service loaded activating auto-restart fake"
          exit 0
        fi
        if [[ "$args" == *"list-unit-files"* ]]; then
          echo "mcp-second-opinion.service enabled"
          echo "mcp-playwright-persistent.service enabled"
          echo "mcp-coordination.service enabled"
          exit 0
        fi
        exit 1
        """,
    )
    _write_executable(
        bin_dir / "ss",
        """
        #!/usr/bin/env bash
        cat <<'EOF'
        State Recv-Q Send-Q Local Address:Port Peer Address:Port Process
        LISTEN 0 4096 0.0.0.0:8081 0.0.0.0:* users:(("docker-proxy",pid=100,fd=4))
        LISTEN 0 4096 127.0.0.1:8081 0.0.0.0:* users:(("python",pid=200,fd=5))
        EOF
        """,
    )
    _write_executable(
        bin_dir / "sysctl",
        """
        #!/usr/bin/env bash
        case "$2" in
          vm.swappiness) echo 10 ;;
          vm.vfs_cache_pressure) echo 50 ;;
          fs.inotify.max_user_watches) echo 524288 ;;
          fs.inotify.max_user_instances) echo 512 ;;
          *) echo unknown ;;
        esac
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{bin_dir}:{env['PATH']}",
            "USER": "tester",
        }
    )

    result = subprocess.run(
        ["bash", str(DRIFT_SCRIPT), "--fix"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 1
    output = result.stdout
    assert "deployment model conflict - mcp-second-opinion" in output
    # mcp-playwright-persistent was retired in #423, so a leftover unit is now an
    # orphan (repo no longer ships it), not an active-server failure.
    assert "orphaned systemd unit mcp-playwright-persistent" in output
    assert "orphaned systemd unit mcp-coordination" in output
    assert "port binding conflict - port 8081" in output
    assert "Default convergence is Docker" in output
    assert "claude mcp remove second-opinion" in output


def test_drift_detect_no_false_conflict_when_units_absent(tmp_path: Path) -> None:
    """`systemctl is-active <unit>` returns "inactive" (exit 0) even for units that
    were never installed. Presence must be derived from LoadState / on-disk unit
    files, not is-active - otherwise every Docker-only MCP server is wrongly flagged
    as a Docker/systemd deployment-model conflict."""
    home = tmp_path / "home"
    (home / ".config" / "systemd" / "user").mkdir(parents=True)  # deliberately empty

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "uv", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        bin_dir / "docker",
        """
        #!/usr/bin/env bash
        if [[ "$1" == "--version" ]]; then
          echo "Docker version 26.0.0"; exit 0
        fi
        if [[ "$1" == "compose" && "$2" == "version" ]]; then
          echo "Docker Compose version v2.27.0"; exit 0
        fi
        if [[ "$1" == "compose" && "$*" == *" ps "* ]]; then
          echo "mcp-second-opinion:Up (healthy)"
          echo "mcp-playwright-persistent:Up (healthy)"
          exit 0
        fi
        if [[ "$1" == "ps" ]]; then
          echo "mcp-second-opinion:Up 2 hours (healthy)"
          echo "mcp-playwright-persistent:Up 2 hours (healthy)"
          exit 0
        fi
        exit 0
        """,
    )
    # No unit files on disk and systemd knows nothing about these units:
    # is-active answers "inactive" (the real-world trap), LoadState answers "not-found".
    _write_executable(
        bin_dir / "systemctl",
        """
        #!/usr/bin/env bash
        args="$*"
        if [[ "$args" == *"show -p LoadState"* ]]; then
          echo "not-found"; exit 0
        fi
        if [[ "$args" == *"is-active"* ]]; then
          echo "inactive"; exit 0
        fi
        if [[ "$args" == *"list-unit"* ]]; then
          exit 0
        fi
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "ss",
        "#!/usr/bin/env bash\necho 'State Recv-Q Send-Q Local Address:Port Peer Address:Port Process'\n",
    )
    _write_executable(
        bin_dir / "sysctl",
        """
        #!/usr/bin/env bash
        case "$2" in
          vm.swappiness) echo 10 ;;
          vm.vfs_cache_pressure) echo 50 ;;
          fs.inotify.max_user_watches) echo 524288 ;;
          fs.inotify.max_user_instances) echo 512 ;;
          *) echo unknown ;;
        esac
        """,
    )

    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{bin_dir}:{env['PATH']}", "USER": "tester"})

    result = subprocess.run(
        ["bash", str(DRIFT_SCRIPT), "--fix"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    output = result.stdout
    assert "deployment model conflict" not in output
    assert "no Docker/systemd conflicts or failed units" in output


def test_drift_detect_flags_orphaned_docker_mcp(tmp_path: Path) -> None:
    """A curated server (nano-banana) that is gone from `docker compose config
    --services` but still present as a container must be surfaced as an orphaned
    Docker MCP, with a teardown plan under --fix. Exercises the mcp-drift.py
    delegation added for issue #405."""
    home = tmp_path / "home"
    (home / ".config" / "systemd" / "user").mkdir(parents=True)  # no systemd units

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "uv", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        bin_dir / "docker",
        """
        #!/usr/bin/env bash
        if [[ "$1" == "--version" ]]; then echo "Docker version 26.0.0"; exit 0; fi
        if [[ "$1" == "compose" && "$2" == "version" ]]; then echo "Docker Compose version v2.27.0"; exit 0; fi
        if [[ "$1" == "compose" && "$*" == *"config --profiles"* ]]; then
          echo core; echo browser; exit 0
        fi
        if [[ "$1" == "compose" && "$*" == *"config --services"* ]]; then
          # nano-banana deliberately ABSENT from the current service set
          echo mcp-second-opinion; echo aws-secrets-agent; exit 0
        fi
        if [[ "$1" == "compose" && "$*" == *" ps "* ]]; then
          echo "mcp-nano-banana:Up (healthy)"; exit 0
        fi
        if [[ "$1" == "ps" && "$2" == "-a" ]]; then
          printf 'mcp-nano-banana\\trunning\\n'; exit 0   # still present locally
        fi
        if [[ "$1" == "ps" ]]; then echo "mcp-nano-banana:Up 2 hours (healthy)"; exit 0; fi
        if [[ "$1" == "images" ]]; then exit 0; fi
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "systemctl",
        """
        #!/usr/bin/env bash
        args="$*"
        if [[ "$args" == *"show -p LoadState"* ]]; then echo "not-found"; exit 0; fi
        if [[ "$args" == *"is-active"* ]]; then echo "inactive"; exit 0; fi
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "claude",
        """
        #!/usr/bin/env bash
        if [[ "$1" == "mcp" && "$2" == "list" ]]; then echo "nano-banana"; exit 0; fi
        if [[ "$1" == "mcp" && "$2" == "get" ]]; then echo "Scope: local"; exit 0; fi
        exit 0
        """,
    )
    _write_executable(bin_dir / "codex", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "ss",
        "#!/usr/bin/env bash\necho 'State Recv-Q Send-Q Local Address:Port Peer Address:Port Process'\n")
    _write_executable(
        bin_dir / "sysctl",
        """
        #!/usr/bin/env bash
        case "$2" in
          vm.swappiness) echo 10 ;;
          vm.vfs_cache_pressure) echo 50 ;;
          fs.inotify.max_user_watches) echo 524288 ;;
          fs.inotify.max_user_instances) echo 512 ;;
          *) echo unknown ;;
        esac
        """,
    )

    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{bin_dir}:{env['PATH']}", "USER": "tester"})

    result = subprocess.run(
        ["bash", str(DRIFT_SCRIPT), "--fix"],
        cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )

    output = result.stdout
    assert result.returncode == 1
    assert "orphaned Docker MCP mcp-nano-banana" in output
    assert "docker rm -f mcp-nano-banana" in output          # teardown plan under --fix
    assert "claude mcp remove nano-banana" in output
