"""Tests for scripts/flow-live-driver-guard.sh - concurrent live-driver guard (issue #503).

Contract:
- With no dirty file (or every dirty file older than the threshold), the verdict
  is ``clear`` and exit is 0.
- With a dirty file (tracked-modified OR untracked) modified within the freshness
  threshold, the verdict is ``suspected`` and the fresh file is NAMED in the
  output; ``--exit-code`` then returns 1 so a caller can gate on it.
- ``--threshold-minutes N`` narrows/widens the freshness window.
- Outside a git work tree (or a missing path) the verdict is ``unknown`` and exit
  is 0 (fail-open, advisory).

"now" is pinned via the ``FLOW_LIVE_DRIVER_NOW`` env hook and file mtimes are set
with ``os.utime`` so the age math is deterministic (no sleeping, no wall-clock
flakiness). The tests build REAL throwaway git repos.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-live-driver-guard.sh"

# The behaviour tests drive real `git` and `bash` subprocesses. The Woodpecker
# `validate` step runs in `uv:python3.11-bookworm-slim`, which ships bash but NOT
# git, so those tests are skipped there (issue #430). The read-only wiring tests
# below need neither and always run.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

# A fixed epoch used as "now" so age math is deterministic.
NOW = 1_700_000_000


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout


def _run(*args: str, now: int | None = NOW) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if now is not None:
        env["FLOW_LIVE_DRIVER_NOW"] = str(now)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a0\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def _set_age(path: Path, minutes: float) -> None:
    """Set the file's mtime so it reads as ``minutes`` old relative to NOW."""
    ts = NOW - int(minutes * 60)
    os.utime(path, (ts, ts))


# --- read-only wiring (no git/bash needed) ---------------------------------


def test_script_exists_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), "guard script must be executable"


# --- behaviour --------------------------------------------------------------


@requires_git
def test_clear_when_no_dirty(tmp_path: Path):
    repo = _make_repo(tmp_path)
    res = _run(str(repo))
    assert res.returncode == 0
    assert "FLOW_LIVE_DRIVER: clear" in res.stdout


@requires_git
def test_suspected_when_fresh_tracked_edit(tmp_path: Path):
    repo = _make_repo(tmp_path)
    (repo / "a.txt").write_text("a1 changed\n")
    _set_age(repo / "a.txt", minutes=2)
    res = _run(str(repo))
    assert "FLOW_LIVE_DRIVER: suspected" in res.stdout
    # the fresh file is named in the human-facing block (stderr)
    assert "a.txt" in res.stderr
    assert res.returncode == 0  # advisory by default


@requires_git
def test_suspected_when_fresh_untracked_file(tmp_path: Path):
    repo = _make_repo(tmp_path)
    live = repo / "live.py"
    live.write_text("# a live driver just wrote this\n")
    _set_age(live, minutes=1)
    res = _run(str(repo))
    assert "FLOW_LIVE_DRIVER: suspected" in res.stdout
    assert "live.py" in res.stderr


@requires_git
def test_exit_code_flag_returns_1_on_suspected(tmp_path: Path):
    repo = _make_repo(tmp_path)
    (repo / "a.txt").write_text("edit\n")
    _set_age(repo / "a.txt", minutes=0)
    res = _run(str(repo), "--exit-code")
    assert "FLOW_LIVE_DRIVER: suspected" in res.stdout
    assert res.returncode == 1


@requires_git
def test_clear_when_dirty_but_stale(tmp_path: Path):
    repo = _make_repo(tmp_path)
    (repo / "a.txt").write_text("edited long ago\n")
    _set_age(repo / "a.txt", minutes=120)  # 2h old, past the 30m default
    res = _run(str(repo), "--exit-code")
    assert "FLOW_LIVE_DRIVER: clear" in res.stdout
    assert res.returncode == 0


@requires_git
def test_threshold_option_narrows_window(tmp_path: Path):
    repo = _make_repo(tmp_path)
    (repo / "a.txt").write_text("edited 10m ago\n")
    _set_age(repo / "a.txt", minutes=10)
    # default 30m -> suspected
    assert "FLOW_LIVE_DRIVER: suspected" in _run(str(repo)).stdout
    # narrowed to 5m -> the 10m-old edit is now clear
    res = _run(str(repo), "--threshold-minutes", "5")
    assert "FLOW_LIVE_DRIVER: clear" in res.stdout


@requires_git
def test_unknown_outside_git(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    res = _run(str(plain))
    assert "FLOW_LIVE_DRIVER: unknown" in res.stdout
    assert res.returncode == 0


def test_unknown_missing_path(tmp_path: Path):
    res = _run(str(tmp_path / "does-not-exist"))
    assert "FLOW_LIVE_DRIVER: unknown" in res.stdout
    assert res.returncode == 0


# --- the verdict names what it is about (issue #1271) ------------------------


def _path_line(out: str) -> str:
    lines = [ln for ln in out.splitlines() if ln.startswith("FLOW_LIVE_DRIVER_PATH: ")]
    assert len(lines) == 1, out
    return lines[0].split(": ", 1)[1]


@requires_git
def test_an_explicit_path_is_named_and_no_note_is_printed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    result = _run(str(repo))
    assert _path_line(result.stdout) == str(repo.resolve())
    lines = result.stdout.splitlines()
    assert lines[-1] == "FLOW_LIVE_DRIVER: clear", "the verdict stays the last stdout line"
    assert lines[-2].startswith("FLOW_LIVE_DRIVER_PATH: "), "the path immediately precedes it"
    assert "no WORKTREE_PATH given" not in result.stderr


@requires_git
def test_a_defaulted_path_is_said_and_names_the_ambient_repo(tmp_path: Path) -> None:
    """The #1271 shape: a bare call answers about wherever the cwd happens to be.

    The default is kept (it is a published interface), so this pins that the
    substitution is VISIBLE: a note on stderr, and a path line naming the repo
    the verdict is actually about - here, one that is not the caller's worktree.
    """
    elsewhere = _make_repo(tmp_path)
    env = os.environ.copy()
    env["FLOW_LIVE_DRIVER_NOW"] = str(NOW)
    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=elsewhere, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert "no WORKTREE_PATH given" in result.stderr
    assert _path_line(result.stdout) == str(elsewhere.resolve())


def test_an_unknown_verdict_still_names_its_path(tmp_path: Path) -> None:
    """Fail-open lanes too: `unknown` about WHAT must be answerable."""
    missing = tmp_path / "not-here"
    result = _run(str(missing))
    assert "FLOW_LIVE_DRIVER: unknown" in result.stdout
    assert _path_line(result.stdout) == str(missing)


def test_flow_auto_passes_the_worktree_path_to_the_step_4_guard() -> None:
    """The documented call site must not rely on the ambient cwd (issue #1271)."""
    auto = (ROOT / ".claude" / "commands" / "flow" / "auto.md").read_text(encoding="utf-8")
    calls = [ln.strip() for ln in auto.splitlines()
             if ln.strip().startswith("~/.claude/scripts/flow-live-driver-guard.sh")]
    assert calls, "flow/auto.md no longer invokes the live-driver guard"
    for call in calls:
        assert len(call.split()) >= 2, f"bare call relies on the ambient cwd: {call}"
