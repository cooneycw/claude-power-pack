"""Tests for the cross-session worktree claim (issue #597).

Covers ``scripts/flow-worktree-claim.sh`` and the owner check it gives
``scripts/worktree-remove.sh``.

Contract:
- ``claim`` locks the worktree with a parseable ``flow-claim`` reason; a second
  ``check`` from the same session reports ``self`` with the owner detail intact.
- A claim held by a LIVE foreign session reports ``held``; ``claim`` then exits 1
  and ``worktree-remove.sh`` refuses with exit 4 - the silent-data-loss failure
  this whole mechanism exists to prevent.
- A claim whose owning process is gone reports ``stale`` and is taken over
  automatically, so the mechanism can never permanently wedge a repo.
- A lock this family did not write is ``foreign`` and is never stolen.
- The primary checkout cannot be locked at all - ``unsupported``, fail-open.
- ``--steal`` is the deliberate override on both scripts.

Liveness is pinned with the ``FLOW_CLAIM_LIVE_PIDS`` hook rather than real
processes, so no test depends on a pid that happens to exist. The tests build
REAL throwaway git repos.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAIM = ROOT / "scripts" / "flow-worktree-claim.sh"
REMOVE = ROOT / "scripts" / "worktree-remove.sh"

# These drive real `git` and `bash` subprocesses. The Woodpecker `validate` step
# runs in `uv:python3.11-bookworm-slim`, which ships bash but NOT git, so they
# are skipped there (issue #430). The read-only wiring tests need neither.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

SELF_PID = "4242"
SELF_SESSION = "session-self"
OTHER_PID = "9999"
OTHER_SESSION = "session-other"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
        capture_output=True,
        text=True,
        check=False,
    )


def _run(
    script: Path,
    *args: str,
    pid: str = SELF_PID,
    session: str = SELF_SESSION,
    live: str = "",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_PID": pid,
            "CLAUDE_CODE_SESSION_ID": session,
            "FLOW_CLAIM_HOST": "testhost",
            # Liveness is simulated: only pids listed here are "alive".
            "FLOW_CLAIM_LIVE_PIDS": live,
        }
    )
    return subprocess.run(
        ["bash", str(script), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("FLOW_CLAIM: "):
            return line.removeprefix("FLOW_CLAIM: ").strip()
    return "<none>"


def _field(proc: subprocess.CompletedProcess[str], key: str) -> str:
    prefix = f"FLOW_CLAIM_{key}="
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return "<none>"


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    """A primary checkout plus one linked worktree on an issue branch."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "-q", "--allow-empty", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "issue-42-thing")
    return main, wt


# --- wiring (no git needed) --------------------------------------------------


def test_claim_script_is_registered_with_the_helper_family() -> None:
    """A helper the flow lane calls must ship with the family, or a plugin-only
    install dead-ends at exit 127 (the #590 failure)."""
    installer = (ROOT / "scripts" / "flow-helpers-install.sh").read_text()
    assert "flow-worktree-claim.sh" in installer

    plugin_sync = (ROOT / "scripts" / "plugin-sync.sh").read_text()
    assert "scripts/flow-worktree-claim.sh" in plugin_sync

    perms = (ROOT / "templates" / "claude-settings-permissions.json").read_text()
    assert "Bash(~/.claude/scripts/flow-worktree-claim.sh:*)" in perms


# --- claim lifecycle ---------------------------------------------------------


@requires_git
def test_free_then_claim_then_self(repo: tuple[Path, Path]) -> None:
    _main, wt = repo
    assert _verdict(_run(CLAIM, "check", str(wt))) == "free"

    claimed = _run(CLAIM, "claim", str(wt), "--issue", "42")
    assert claimed.returncode == 0
    assert _verdict(claimed) == "self"

    check = _run(CLAIM, "check", str(wt))
    assert _verdict(check) == "self"
    # The owner detail must survive out of the classifier, not be blanked.
    assert _field(check, "OWNER_PID") == SELF_PID
    assert _field(check, "OWNER_SESSION") == SELF_SESSION
    assert _field(check, "ISSUE") == "42"


@requires_git
def test_claim_is_idempotent_for_its_owner(repo: tuple[Path, Path]) -> None:
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42")
    again = _run(CLAIM, "claim", str(wt), "--issue", "42")
    assert again.returncode == 0
    assert _verdict(again) == "self"


@requires_git
def test_live_foreign_claim_is_held_and_blocks_claiming(
    repo: tuple[Path, Path],
) -> None:
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42", pid=OTHER_PID, session=OTHER_SESSION)

    check = _run(CLAIM, "check", str(wt), live=OTHER_PID)
    assert _verdict(check) == "held"
    assert _field(check, "OWNER_PID") == OTHER_PID

    lost = _run(CLAIM, "claim", str(wt), "--issue", "42", live=OTHER_PID)
    assert lost.returncode == 1, "claiming a live-owned worktree must fail loudly"
    assert _verdict(lost) == "held"


@requires_git
def test_dead_owner_is_stale_and_taken_over(repo: tuple[Path, Path]) -> None:
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42", pid=OTHER_PID, session=OTHER_SESSION)

    # No live pids: the owner is gone.
    assert _verdict(_run(CLAIM, "check", str(wt), live="")) == "stale"

    taken = _run(CLAIM, "claim", str(wt), "--issue", "42", live="")
    assert taken.returncode == 0
    assert _verdict(taken) == "self"
    assert _field(taken, "OWNER_PID") == SELF_PID


@requires_git
def test_steal_overrides_a_live_claim(repo: tuple[Path, Path]) -> None:
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42", pid=OTHER_PID, session=OTHER_SESSION)
    stolen = _run(CLAIM, "claim", str(wt), "--issue", "42", "--steal", live=OTHER_PID)
    assert stolen.returncode == 0
    assert _verdict(stolen) == "self"


@requires_git
def test_non_flow_lock_is_foreign_and_never_stolen(repo: tuple[Path, Path]) -> None:
    main, wt = repo
    _git(main, "worktree", "lock", "--reason", "held for surgery", str(wt))

    assert _verdict(_run(CLAIM, "check", str(wt))) == "foreign"

    # Fail-open: claiming does not error the caller, but must not take the lock.
    attempt = _run(CLAIM, "claim", str(wt), "--issue", "42")
    assert attempt.returncode == 0
    assert _verdict(attempt) == "foreign"
    assert _verdict(_run(CLAIM, "check", str(wt))) == "foreign"


@requires_git
def test_primary_checkout_cannot_be_claimed(repo: tuple[Path, Path]) -> None:
    main, _wt = repo
    result = _run(CLAIM, "claim", str(main), "--issue", "42")
    assert result.returncode == 0, "the current-branch lane must not be blocked"
    assert _verdict(result) == "unsupported"


@requires_git
def test_check_resolves_the_worktree_by_issue_number(repo: tuple[Path, Path]) -> None:
    """The cross-session check runs before this session has a path of its own."""
    main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42", pid=OTHER_PID, session=OTHER_SESSION)

    found = _run(CLAIM, "check", "--issue", "42", "--repo", str(main), live=OTHER_PID)
    assert _verdict(found) == "held"
    assert Path(_field(found, "PATH")).resolve() == wt.resolve()

    # An issue nobody is working on is free, not an error.
    absent = _run(CLAIM, "check", "--issue", "77", "--repo", str(main))
    assert absent.returncode == 0
    assert _verdict(absent) == "free"


@requires_git
def test_release_drops_own_claim_but_not_a_live_foreign_one(
    repo: tuple[Path, Path],
) -> None:
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42")
    assert _verdict(_run(CLAIM, "release", str(wt))) == "free"
    assert _verdict(_run(CLAIM, "check", str(wt))) == "free"

    _run(CLAIM, "claim", str(wt), "--issue", "42", pid=OTHER_PID, session=OTHER_SESSION)
    kept = _run(CLAIM, "release", str(wt), live=OTHER_PID)
    assert kept.returncode == 0
    assert _verdict(kept) == "held", "another session's live claim must survive"
    assert _verdict(_run(CLAIM, "check", str(wt), live=OTHER_PID)) == "held"


# --- the removal guard -------------------------------------------------------


@requires_git
def test_remove_refuses_a_worktree_claimed_by_a_live_session(
    repo: tuple[Path, Path],
) -> None:
    """The #597 headline: a sibling session's cleanup must not delete live work."""
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42", pid=OTHER_PID, session=OTHER_SESSION)
    (wt / "uncommitted.txt").write_text("step 4 work nobody else knows about\n")

    result = _run(REMOVE, str(wt), "--force", "--delete-branch", live=OTHER_PID)
    assert result.returncode == 4
    assert wt.exists(), "the claimed worktree must still be on disk"
    assert (wt / "uncommitted.txt").exists()
    assert OTHER_PID in result.stderr


@requires_git
def test_remove_steals_only_when_asked(repo: tuple[Path, Path]) -> None:
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42", pid=OTHER_PID, session=OTHER_SESSION)

    result = _run(REMOVE, str(wt), "--force", "--delete-branch", "--steal", live=OTHER_PID)
    assert result.returncode == 0
    assert not wt.exists()


@requires_git
def test_remove_releases_and_removes_its_own_claim(repo: tuple[Path, Path]) -> None:
    """A run cleaning up after itself must not be blocked by its own claim."""
    _main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42")

    result = _run(REMOVE, str(wt), "--force", "--delete-branch")
    assert result.returncode == 0, result.stderr
    assert not wt.exists()


@requires_git
def test_remove_is_unaffected_when_nothing_is_claimed(repo: tuple[Path, Path]) -> None:
    """Fail-open: the pre-claim behaviour is preserved exactly."""
    _main, wt = repo
    result = _run(REMOVE, str(wt), "--force", "--delete-branch")
    assert result.returncode == 0, result.stderr
    assert not wt.exists()
