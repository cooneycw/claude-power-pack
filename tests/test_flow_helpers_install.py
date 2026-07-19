"""Tests for scripts/flow-helpers-install.sh - the #590 marketplace repair path.

Contract:
- Install the flow helper family into $HOME/.claude/scripts/, idempotently.
- SYMLINK when the source is a CPP checkout (follows `git pull`, matching
  /cpp:init Tier 2); COPY when the source is a plugin bundle (a symlink into a
  version-stamped plugin cache dangles at the next upgrade).
- `--check` is read-only and reports ok / missing / stale, exit 1 on the latter
  two, so /flow:doctor can call it without mutating the host.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "flow-helpers-install.sh"

HELPERS = [
    "flow-start-resolve.sh",
    "flow-live-driver-guard.sh",
    "flow-stale-check.sh",
    "flow-worktree-guard.sh",
    "gh-pr-merge.sh",
    "worktree-remove.sh",
    "friction-log.sh",
    "check-ignored-additions.sh",
    "flow-helpers-install.sh",
]


def _run(
    *args: str,
    home: Path,
    source: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FLOW_HELPERS_HOME"] = str(home)
    if source is not None:
        env["FLOW_HELPERS_SOURCE"] = str(source)
    else:
        env.pop("FLOW_HELPERS_SOURCE", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    return subprocess.run(
        [str(INSTALLER), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_HELPERS:")]
    assert lines, f"no verdict line in output:\n{proc.stdout}\n{proc.stderr}"
    return lines[-1].split(":", 1)[1].strip()


@pytest.fixture
def plugin_source(tmp_path: Path) -> Path:
    """A plugin-shaped source dir: scripts/ with no CLAUDE.md above it."""
    src = tmp_path / "plugin" / "scripts"
    src.mkdir(parents=True)
    for name in HELPERS:
        dest = src / name
        dest.write_bytes((ROOT / "scripts" / name).read_bytes())
        dest.chmod(0o755)
    return src


def test_script_is_executable():
    assert INSTALLER.exists()
    assert os.access(INSTALLER, os.X_OK), "flow-helpers-install.sh must be executable"


def test_installs_the_whole_family(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    proc = _run(home=home, source=plugin_source)
    assert proc.returncode == 0, proc.stderr
    assert _verdict(proc) == "installed"
    for name in HELPERS:
        installed = home / ".claude" / "scripts" / name
        assert installed.is_file(), f"{name} not installed"
        assert installed.stat().st_mode & 0o111, f"{name} installed without exec bit"


def test_install_is_idempotent(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    second = _run(home=home, source=plugin_source)
    assert second.returncode == 0
    assert _verdict(second) == "ok", "re-running must be a no-op, not a rewrite"


def test_plugin_source_copies_rather_than_symlinks(tmp_path: Path, plugin_source: Path):
    # A symlink into a version-stamped plugin cache dangles on upgrade; the copy
    # keeps working (and goes "stale", which --check reports).
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    installed = home / ".claude" / "scripts" / "flow-start-resolve.sh"
    assert not installed.is_symlink(), "plugin-sourced helpers must be copied, not linked"


def test_checkout_source_symlinks(tmp_path: Path):
    # A checkout-shaped source: CLAUDE.md + .claude/commands one level above scripts/.
    checkout = tmp_path / "cpp"
    (checkout / "scripts").mkdir(parents=True)
    (checkout / ".claude" / "commands").mkdir(parents=True)
    (checkout / "CLAUDE.md").write_text("# CPP\n")
    for name in HELPERS:
        dest = checkout / "scripts" / name
        dest.write_bytes((ROOT / "scripts" / name).read_bytes())
        dest.chmod(0o755)

    home = tmp_path / "home"
    proc = _run(home=home, source=checkout / "scripts")
    assert proc.returncode == 0, proc.stderr
    installed = home / ".claude" / "scripts" / "flow-start-resolve.sh"
    assert installed.is_symlink(), "checkout-sourced helpers must be symlinked to follow git pull"
    assert installed.resolve() == (checkout / "scripts" / "flow-start-resolve.sh").resolve()


def test_check_reports_missing_on_a_fresh_host(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 1
    assert _verdict(proc) == "missing"
    assert not (home / ".claude" / "scripts").exists(), "--check must not write anything"


def test_check_reports_ok_after_install(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 0
    assert _verdict(proc) == "ok"


def test_check_detects_stale_copies_after_a_plugin_upgrade(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    _run(home=home, source=plugin_source)
    # Simulate the upgrade: the bundled source moves on, the installed copy does not.
    upgraded = plugin_source / "gh-pr-merge.sh"
    upgraded.write_text(upgraded.read_text() + "\n# v2\n")

    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 1
    assert _verdict(proc) == "stale"
    assert "STALE gh-pr-merge.sh" in proc.stdout

    # And repair brings it back.
    fixed = _run(home=home, source=plugin_source)
    assert _verdict(fixed) == "installed"
    assert _verdict(_run("--check", home=home, source=plugin_source)) == "ok"


def test_check_treats_a_dangling_symlink_as_missing(tmp_path: Path, plugin_source: Path):
    # The failure mode a naive symlink-into-plugin-cache install would produce.
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "flow-start-resolve.sh").symlink_to(tmp_path / "gone" / "flow-start-resolve.sh")

    proc = _run("--check", home=home, source=plugin_source)
    assert proc.returncode == 1
    assert _verdict(proc) == "missing"
    assert "dangling symlink" in proc.stdout


def test_install_replaces_a_dangling_symlink(tmp_path: Path, plugin_source: Path):
    home = tmp_path / "home"
    scripts = home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    stale_link = scripts / "flow-start-resolve.sh"
    stale_link.symlink_to(tmp_path / "gone" / "flow-start-resolve.sh")

    proc = _run(home=home, source=plugin_source)
    assert proc.returncode == 0, proc.stderr
    assert not stale_link.is_symlink()
    assert stale_link.is_file() and stale_link.stat().st_mode & 0o111


def test_unknown_argument_is_rejected(tmp_path: Path, plugin_source: Path):
    proc = _run("--nope", home=tmp_path / "home", source=plugin_source)
    assert proc.returncode == 2
    assert "unknown argument" in proc.stderr
