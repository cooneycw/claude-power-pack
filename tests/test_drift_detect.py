"""Regression tests for MCP deployment-model drift detection."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

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
    # mcp-second-opinion was retired in #469 (moved to its own external repo, which
    # also removed CPP's entire Docker MCP runtime) and mcp-playwright-persistent in
    # #423, so a leftover unit for either is now an orphan (repo no longer ships it),
    # not an active-server deployment-model conflict.
    assert "orphaned systemd unit mcp-second-opinion" in output
    assert "orphaned systemd unit mcp-playwright-persistent" in output
    assert "orphaned systemd unit mcp-coordination" in output
    assert "port binding conflict - port 8081" in output
    # The orphan teardown targets the unit-named registration, never the reused
    # "second-opinion" name that now points at the external server via .mcp.json.
    assert "claude mcp remove mcp-second-opinion" in output


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


def test_drift_detect_reports_not_assessed_when_docker_is_unreadable(tmp_path: Path) -> None:
    """A refused docker socket must NOT be reported as `ok - none detected`
    (issue #673). This consumer line-parsed `--list-orphans` and swallowed its
    exit code with `|| true`, so an empty list from a host it could not read
    became a clean check - the relay that made the false clean actionable."""
    home = tmp_path / "home"
    (home / ".config" / "systemd" / "user").mkdir(parents=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "uv", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        bin_dir / "docker",
        """
        #!/usr/bin/env bash
        if [[ "$1" == "--version" ]]; then echo "Docker version 26.0.0"; exit 0; fi
        if [[ "$1" == "compose" && "$2" == "version" ]]; then echo "Docker Compose version v2.27.0"; exit 0; fi
        # The daemon-backed reads are refused; `compose config` (pure YAML parse)
        # is unaffected, which is exactly how a permission-denied socket behaves.
        if [[ "$1" == "ps" || "$1" == "images" ]]; then
          echo "permission denied while trying to connect to the Docker daemon socket" >&2
          exit 1
        fi
        exit 0
        """,
    )
    # No passwordless sudo: the non-interactive retry fails, so the verdict stays
    # "could not look". A fake is installed so the host's real sudo is never run.
    _write_executable(
        bin_dir / "sudo",
        "#!/usr/bin/env bash\necho 'sudo: a password is required' >&2\nexit 1\n",
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
    _write_executable(bin_dir / "claude", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "codex", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "ss",
        "#!/usr/bin/env bash\necho 'State Recv-Q Send-Q Local Address:Port Peer Address:Port Process'\n")
    _write_executable(
        bin_dir / "sysctl",
        """
        #!/usr/bin/env bash
        echo unknown
        """,
    )

    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{bin_dir}:{env['PATH']}", "USER": "tester"})

    result = subprocess.run(
        ["bash", str(DRIFT_SCRIPT)],
        cwd=ROOT, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )

    output = result.stdout
    assert "orphaned Docker MCPs - NOT ASSESSED" in output
    assert "orphaned Docker MCPs - none detected" not in output
    # The report must still COMPLETE: under `set -euo pipefail` an unguarded
    # `$(helper)` whose exit is now 3 aborts the whole run before the summary,
    # which silently truncates every check after this one.
    assert "checked," in output  # the trailing "N checked, M skipped" summary


def test_orphan_detection_ignores_sibling_worktree_templates(tmp_path: Path) -> None:
    """A deploy template inside .claude/worktrees/<sibling>/ (another session's
    checkout) must not make repo_ships_systemd_unit() treat the unit as shipped -
    otherwise orphan detection flakes on multi-session boxes depending on what
    sibling worktrees hold on disk (issue #518)."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    script = repo / "scripts" / "drift-detect.sh"
    script.write_text(DRIFT_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    # Sibling worktree still carrying a pre-retirement deploy template.
    sibling_deploy = repo / ".claude" / "worktrees" / "issue-999-sibling" / "mcp-second-opinion" / "deploy"
    sibling_deploy.mkdir(parents=True)
    (sibling_deploy / "mcp-second-opinion.service.template").write_text(
        "[Service]\nExecStart=stale\n", encoding="utf-8"
    )

    home = tmp_path / "home"
    user_units = home / ".config" / "systemd" / "user"
    user_units.mkdir(parents=True)
    (user_units / "mcp-second-opinion.service").write_text("[Service]\nExecStart=fake\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "uv", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        bin_dir / "docker",
        """
        #!/usr/bin/env bash
        if [[ "$1" == "--version" ]]; then echo "Docker version 26.0.0"; exit 0; fi
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
        ["bash", str(script), "--fix"],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    output = result.stdout
    assert result.returncode == 1
    # The sibling worktree's template must NOT suppress orphan detection.
    assert "orphaned systemd unit mcp-second-opinion" in output


# Committed controls: a clean host, an unassessed Docker inventory with real
# non-Docker drift, and an unhealthy Docker container. No host PATH is inherited.
@pytest.mark.parametrize(
    ("docker_present", "port_conflict", "systemd_state", "expected_rc"),
    [(False, False, "", 0), (False, True, "", 1), (True, False, "", 1),
     (False, False, "failed", 1), (False, False, "activating", 1)],
    ids=["docker-absent-clean", "docker-absent-port-drift", "docker-unhealthy",
         "docker-absent-unit-failed", "docker-absent-unit-activating"],
)
def test_drift_detect_controlled_inventory(
    tmp_path: Path, docker_present: bool, port_conflict: bool, systemd_state: str, expected_rc: int
) -> None:
    tools = ("bash", "dirname", "date", "grep", "sort", "awk", "cat", "sed",
             "mktemp", "head", "tr", "basename", "wc", "paste", "rm")
    for tool in tools:
        if shutil.which(tool) is None:
            pytest.skip(f"requires {tool}")

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    script = repo / "scripts" / "drift-detect.sh"
    shutil.copyfile(DRIFT_SCRIPT, script)
    (repo / "docker-compose.yml").write_text("services: {}\n")
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in tools:
        (bin_dir / tool).symlink_to(shutil.which(tool))
    # This fixture has no installed units or shared scripts. Avoid consulting
    # the host's /etc/systemd/system, while keeping later port checks real.
    _write_executable(bin_dir / "find", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "sysctl", """
        #!/usr/bin/env bash
        case "$2" in
          vm.swappiness) echo 10 ;;
          vm.vfs_cache_pressure) echo 50 ;;
          fs.inotify.max_user_watches) echo 524288 ;;
          fs.inotify.max_user_instances) echo 512 ;;
        esac
    """)
    listeners = ""
    if port_conflict:
        listeners = (
            'LISTEN 0 4096 0.0.0.0:8081 0.0.0.0:* users:(("first",pid=1,fd=4))\n'
            'LISTEN 0 4096 127.0.0.1:8081 0.0.0.0:* users:(("second",pid=2,fd=5))\n'
        )
    _write_executable(bin_dir / "ss", "#!/usr/bin/env bash\ncat <<'EOF'\n" + listeners + "EOF\n")
    if docker_present:
        _write_executable(bin_dir / "docker", """
            #!/usr/bin/env bash
            echo 'fixture-container:Up (unhealthy)'
        """)
    if systemd_state:
        # Current CPP ships no first-party MCPs. Populate its existing inventory
        # contract so the unit-only half cannot silently become Docker-dependent.
        script.write_text(script.read_text().replace(
            'declare -A DOCKER_STATUS=()',
            'declare -A DOCKER_STATUS=()\nMCP_SERVERS=(fixture)\nMCP_SYSTEMD_UNITS[fixture]=cpp-fixture'
        ))
        _write_executable(bin_dir / "systemctl", f"""
            #!/usr/bin/env bash
            if [[ "$*" == *"show -p LoadState"* ]]; then echo loaded; fi
            if [[ "$*" == *"is-active"* ]]; then echo {systemd_state}; fi
        """)
    env = {**os.environ, "PATH": str(bin_dir), "HOME": str(home)}
    docker_probe = subprocess.run(
        ["bash", "-c", "command -v docker"], env=env, capture_output=True, check=False
    )
    if docker_present:
        assert docker_probe.returncode == 0
        assert docker_probe.stdout.decode().strip() == str(bin_dir / "docker")
    else:
        # Assert the negative precondition before running the reporter (#1629).
        assert shutil.which("docker", path=env["PATH"]) is None
        assert docker_probe.returncode == 1
        assert not docker_probe.stdout

    if systemd_state:
        unit_probe = subprocess.run(
            ["systemctl", "--user", "is-active", "cpp-fixture"],
            env=env, text=True, capture_output=True, check=False,
        )
        assert unit_probe.stdout.strip() == systemd_state

    result = subprocess.run(
        ["bash", str(script)], cwd=repo, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    output = result.stdout
    assert result.returncode == expected_rc, output
    assert "checked," in output, output
    if docker_present:
        assert "docker - container fixture-container is unhealthy" in output
    else:
        assert "docker - not installed" in output
        assert "mcp deployment models - Docker/systemd conflict NOT ASSESSED (docker not installed)" in output
        assert "orphaned Docker MCPs - docker not installed" in output
        assert "no Docker/systemd conflicts or failed units" not in output
        assert "docker - all running containers healthy" not in output
        assert "orphaned Docker MCPs - none detected" not in output
    if port_conflict:
        assert "port binding conflict - port 8081" in output
        assert "DRIFT DETECTED" in output
    elif systemd_state:
        diagnosis = "failed" if systemd_state == "failed" else "stuck activating"
        assert f"systemd - unit cpp-fixture is {diagnosis} (fixture)" in output
        assert "DRIFT DETECTED" in output
    elif not docker_present:
        assert "ports - no MCP listeners" in output
        assert "NO DRIFT" in output

    if not docker_present:
        # Exercise the collector independently too: the public reporter guards
        # its call, but a missing optional tool must not trip errexit here.
        script.write_text(
            DRIFT_SCRIPT.read_text().removesuffix('main "$@"\n')
            + 'DOCKER_STATUS[stale]="Up"\ncollect_docker_status\n'
            + '[[ -z "${DOCKER_STATUS[stale]:-}" ]]\necho collector-completed\n'
        )
        collector = subprocess.run(
            ["bash", str(script)], cwd=repo, env=env, text=True,
            capture_output=True, check=False,
        )
        assert collector.returncode == 0, collector.stderr
        assert collector.stdout.strip() == "collector-completed"
