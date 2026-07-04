"""Tests for scripts/flow-stale-check.sh - early stale-base detection (issue #473).

Contract:
- When ``origin/main`` (the base ref) has not moved past HEAD, the verdict is
  ``current`` and exit is 0.
- When the base moved but none of the files this branch touched changed upstream,
  the verdict is ``moved-clean``.
- When the base moved AND a file this branch edited also changed upstream, the
  verdict is ``collision`` and the colliding file(s) are NAMED in the output.
- When a ``.claude/commands/flow/*.md`` file changed upstream, the output reminds
  the user to regenerate the packaged copies (``plugin-sync.sh``) so they do not drift.
- The check is advisory (exit 0) by default; ``--exit-code`` returns 1 on a
  collision so a caller can gate on it.

The tests build REAL throwaway git repos so the diff/intersection logic is
exercised for real; ``--no-fetch`` keeps them offline (no remote).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "flow-stale-check.sh"

FLOW_CMD = ".claude/commands/flow/auto.md"

# The behaviour tests drive real `git` and `bash` subprocesses. The Woodpecker
# `validate` step runs in `uv:python3.11-bookworm-slim`, which ships bash but NOT
# git, so those tests are skipped there (issue #430). The read-only wiring tests
# below need neither and always run.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)


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


def _write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _make_repo(tmp_path: Path) -> Path:
    """A repo on ``main`` with a couple of files, then a feature branch cut off it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo, "a.txt", "a0\n")
    _write(repo, "shared.txt", "s0\n")
    _write(repo, FLOW_CMD, "flow0\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    return repo


def _advance_main(repo: Path, rel: str, content: str) -> None:
    """Simulate a sibling PR landing on ``main`` while ``feature`` is checked out."""
    _git(repo, "checkout", "-q", "main")
    _write(repo, rel, content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"upstream change to {rel}")
    _git(repo, "checkout", "-q", "feature")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args, "--no-fetch"],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _verdict(out: str) -> str:
    for line in out.splitlines():
        if line.startswith("FLOW_STALE_BASE:"):
            return line.split(":", 1)[1].strip()
    return ""


def test_script_is_executable():
    assert SCRIPT.exists()
    assert os.access(SCRIPT, os.X_OK), "flow-stale-check.sh must be executable"


@requires_git
def test_base_current_when_not_behind(tmp_path: Path):
    repo = _make_repo(tmp_path)  # feature == main, nothing moved
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr
    assert _verdict(result.stdout) == "current"


@requires_git
def test_moved_clean_when_no_overlap(tmp_path: Path):
    repo = _make_repo(tmp_path)
    # Feature edits a.txt; main advances a DIFFERENT file.
    _write(repo, "a.txt", "a-mine\n")
    _git(repo, "commit", "-qam", "my edit")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr
    assert _verdict(result.stdout) == "moved-clean"
    assert "No overlap" in result.stdout
    assert "COLLISION" not in result.stdout


@requires_git
def test_collision_is_named(tmp_path: Path):
    repo = _make_repo(tmp_path)
    # Both feature and main touch shared.txt -> collision.
    _write(repo, "shared.txt", "s-mine\n")
    _git(repo, "commit", "-qam", "my edit to shared")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr  # advisory: still 0 by default
    assert _verdict(result.stdout) == "collision"
    assert "COLLISION" in result.stdout
    assert "shared.txt" in result.stdout, "the colliding file must be named"
    assert "git merge --no-edit main" in result.stdout


@requires_git
def test_collision_from_uncommitted_worktree_edit(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _advance_main(repo, "shared.txt", "s-upstream\n")
    # Dirty the work tree without committing - still counts as "touched".
    _write(repo, "shared.txt", "s-dirty\n")
    result = _run(repo, "main")
    assert _verdict(result.stdout) == "collision"
    assert "shared.txt" in result.stdout


@requires_git
def test_exit_code_flag_fails_on_collision(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _write(repo, "shared.txt", "s-mine\n")
    _git(repo, "commit", "-qam", "my edit")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main", "--exit-code")
    assert result.returncode == 1, "collision + --exit-code must return non-zero"
    assert _verdict(result.stdout) == "collision"


@requires_git
def test_exit_code_flag_passes_when_clean(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _write(repo, "a.txt", "a-mine\n")
    _git(repo, "commit", "-qam", "my edit")
    _advance_main(repo, "shared.txt", "s-upstream\n")
    result = _run(repo, "main", "--exit-code")
    assert result.returncode == 0, result.stderr


@requires_git
def test_flow_command_change_reminds_to_resync(tmp_path: Path):
    repo = _make_repo(tmp_path)
    _advance_main(repo, FLOW_CMD, "flow-upstream\n")
    result = _run(repo, "main")
    assert "plugin-sync.sh" in result.stdout, (
        "a flow command change upstream must remind to regenerate the packaged copies"
    )
    assert FLOW_CMD in result.stdout


@requires_git
def test_fail_open_outside_git_repo(tmp_path: Path):
    outside = tmp_path / "plain"
    outside.mkdir()
    result = _run(outside, "main")
    assert result.returncode == 0, "must fail open outside a git repo"
    assert _verdict(result.stdout) == "unknown"


@requires_git
def test_fail_open_when_base_ref_missing(tmp_path: Path):
    repo = _make_repo(tmp_path)
    result = _run(repo, "origin/does-not-exist")
    assert result.returncode == 0
    assert _verdict(result.stdout) == "unknown"


# --- Wiring: the flow surfaces must call the early check / re-sync ----------


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_auto_wires_early_check_at_step4_and_step6():
    text = _read(".claude/commands/flow/auto.md")
    # Referenced at least twice: Step 4 (early) and Step 6 (pre-commit).
    assert text.count("flow-stale-check.sh") >= 2, (
        "auto.md must run the early stale-base check at both Step 4 and Step 6"
    )
    # Step-7 #462 backstop is preserved.
    assert "git merge --no-edit origin/main" in text


def test_finish_wires_early_check():
    text = _read(".claude/commands/flow/finish.md")
    assert "flow-stale-check.sh" in text, "finish.md must run the early stale-base check"
