"""woodpecker/bootstrap-agent-host.sh - package selection (issue #1273).

The package step used to install docker.io, docker-compose-v2,
qemu-guest-agent, ca-certificates and curl only when `docker` was absent, so a
host that already had docker never got the other three - and the very next
line enables qemu-guest-agent. Each package is now decided on its own.

The script is driven with `sudo`, `dpkg-query` and `docker` stubbed first on
PATH, and an unreachable server so it stops at the reachability check, after
the package step and before anything else would touch the host. The stubbed
`sudo` only records its argv.
"""

from __future__ import annotations

import os
import pwd
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "woodpecker" / "bootstrap-agent-host.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("timeout") is None,
    reason="bash and timeout are required to drive the script",
)


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stub(bindir: Path, name: str, body: str) -> None:
    f = bindir / name
    f.write_text("#!/usr/bin/env bash\n" + body)
    f.chmod(0o755)


def _path_without_docker(tmp_path: Path) -> str:
    """This host's PATH, rebuilt as symlinks with every `docker` left out - so a
    docker-less host is CONSTRUCTED rather than required (counter-model review)."""
    shadow = tmp_path / "nodocker"
    shadow.mkdir()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or not os.path.isdir(d):
            continue
        for entry in os.scandir(d):
            if entry.name == "docker" or (shadow / entry.name).exists():
                continue
            if entry.is_file() and os.access(entry.path, os.X_OK):
                (shadow / entry.name).symlink_to(entry.path)
    return str(shadow)


def _run(tmp_path: Path, *, docker_present: bool, installed: set[str],
         held: set[str] = frozenset()) -> list[str]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "sudo.log"
    _stub(bindir, "sudo", f'printf "%s\\n" "$*" >> "{log}"\n')
    _stub(bindir, "sg", "exit 0\n")
    # Emulates dpkg-query for BOTH formats a caller might ask for: the combined
    # ${Status} ("<want> ok installed", where a held package's want is "hold")
    # and ${db:Status-Status} (the installed state alone).
    lines = ['fmt="$2"; pkg="${@: -1}"']
    for p in sorted(installed | held):
        want = "hold" if p in held else "install"
        lines.append(
            f'[ "$pkg" = "{p}" ] && {{ case "$fmt" in *db:Status-Status*) printf installed;; '
            f'*) printf "{want} ok installed";; esac; exit 0; }}'
        )
    _stub(bindir, "dpkg-query", "\n".join(lines) + "\nexit 1\n")
    if docker_present:
        _stub(bindir, "docker", "exit 0\n")
    base_path = os.environ["PATH"] if docker_present else _path_without_docker(tmp_path)
    if not docker_present:
        assert shutil.which("docker", path=f"{bindir}:{base_path}") is None, "fixture must lack docker"
    env = {
        **os.environ,
        "PATH": f"{bindir}:{base_path}",
        "WOODPECKER_SERVER": f"127.0.0.1:{_closed_port()}",
        "WOODPECKER_AGENT_SECRET": "unused-in-this-test",
        "AGENT_DIR": str(tmp_path / "agent"),
        # The script reads $USER under `set -u`; a container may not export it.
        "USER": os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name,
    }
    r = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 1 and "cannot reach" in r.stdout, (r.stdout, r.stderr)
    return log.read_text().splitlines() if log.exists() else []


def _installed_by(lines: list[str]) -> list[str]:
    for line in lines:
        if "apt-get install" in line:
            return line.split("-qq", 1)[1].split()
    return []


def test_a_host_with_docker_still_gets_the_guest_agent(tmp_path: Path) -> None:
    """The #1273 defect: docker present, qemu-guest-agent missing -> nothing installed."""
    lines = _run(tmp_path, docker_present=True, installed={"ca-certificates", "curl"})
    assert _installed_by(lines) == ["qemu-guest-agent"], lines


def test_docker_ce_hosts_never_get_docker_io(tmp_path: Path) -> None:
    """A docker on PATH (docker-ce, say) must not pull docker.io over it."""
    lines = _run(tmp_path, docker_present=True, installed=set())
    got = _installed_by(lines)
    assert "docker.io" not in got and "docker-compose-v2" not in got, lines
    assert got == ["qemu-guest-agent", "ca-certificates", "curl"], lines


def test_nothing_missing_installs_nothing(tmp_path: Path) -> None:
    lines = _run(tmp_path, docker_present=True,
                 installed={"qemu-guest-agent", "ca-certificates", "curl"})
    assert not any("apt-get" in line for line in lines), lines


def test_a_host_without_docker_gets_the_docker_family(tmp_path: Path) -> None:
    lines = _run(tmp_path, docker_present=False,
                 installed={"qemu-guest-agent", "ca-certificates", "curl"})
    assert _installed_by(lines) == ["docker.io", "docker-compose-v2"], lines


def test_a_held_package_is_installed_not_missing(tmp_path: Path) -> None:
    """Counter-model pass 2: a HELD package reads "hold ok installed", which the
    combined-status match took for missing - and apt-get install on a held
    package can fail the bootstrap."""
    lines = _run(tmp_path, docker_present=True, installed={"ca-certificates", "curl"},
                 held={"qemu-guest-agent"})
    assert not any("apt-get" in line for line in lines), lines
