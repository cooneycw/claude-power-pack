"""Regression tests for issue #440: /flow rides native worktrees.

These pin the migration from bespoke ``git worktree add/remove`` plumbing to
Claude Code's native ``EnterWorktree``/``ExitWorktree`` tools, while proving the
issue-anchored gate policy (the moat) stays layered on top: the eli5 necessity
gate, quality gates, the ``issue-<N>-<slug>`` branch name, squash-merge
discipline, and the cross-session ``git worktree`` cleanup fallback.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_start_uses_native_enter_worktree() -> None:
    text = _read(".claude/commands/flow/start.md")
    assert "EnterWorktree" in text
    # Fresh path creates the worktree by name (native), not a sibling dir.
    assert 'name="${BRANCH}"' in text


def test_auto_uses_native_enter_and_exit_worktree() -> None:
    text = _read(".claude/commands/flow/auto.md")
    assert "EnterWorktree" in text  # Step 1 create/enter
    assert "ExitWorktree" in text  # Step 7 same-session cleanup


def test_fresh_path_drops_sibling_worktree_dir() -> None:
    # The old plumbing created ../<repo>-issue-<N> and branched it with git; the
    # native fresh path must not reintroduce that create mechanic. The
    # cross-machine path (which git-adds "$LOCAL_BRANCH"), the cross-repo lane
    # (which git-adds via `git -C "$TARGET_REPO"`, issue #578), and the
    # FLOW_WORKTREE_BASE override lane (which git-adds "$WT_PATH", issue #584 /
    # ADR 0003) are intentionally kept - only the bare same-repo default fresh
    # path must stay native.
    for rel in (".claude/commands/flow/start.md", ".claude/commands/flow/auto.md"):
        text = _read(rel)
        assert 'WORKTREE_DIR="../' not in text, f"{rel} still creates a sibling worktree dir"
        for match in re.findall(r'git worktree add -b "\$BRANCH" \S+', text):
            assert '"$WT_PATH"' in match, (
                f"{rel} git-adds the fresh path outside the #584 override lane: {match}"
            )


def test_auto_cross_repo_lane() -> None:
    # Issue #578: /flow:auto invoked with a PROJECT arg, or from a session cwd
    # outside any git repo, must resolve the target checkout and deterministically
    # ride the git-worktree lane instead of attempting EnterWorktree (which is
    # bound to the session cwd's repo). The mechanics were extracted from inline
    # doc bash into scripts/flow-start-resolve.sh (#581); the doc wires the
    # helper and the helper owns resolution + git-lane creation.
    text = _read(".claude/commands/flow/auto.md")
    assert "/flow:auto <ISSUE> [PROJECT]" in text  # documented invocation form
    assert "flow-start-resolve.sh" in text  # Step 1 delegates to the helper
    assert "CROSS_REPO" in text and "cross-repo" in text  # lane surfaced in the contract
    script = _read("scripts/flow-start-resolve.sh")
    assert '"$PROJECTS_DIR/$PROJECT"' in script  # /project:next resolution convention
    assert "worktree add" in script  # git-lane creation lives in the helper
    # The default layout keeps the worktree under the TARGET repo so the
    # #473/#486 guards and friction buffer resolve unchanged.
    assert "/.claude/worktrees/" in script
    # start.md points cross-repo users at /flow:auto rather than half-supporting it.
    start = _read(".claude/commands/flow/start.md")
    assert "#578" in start


def test_native_worktrees_are_gitignored() -> None:
    assert ".claude/worktrees/" in _read(".gitignore")


def test_moat_preserved_in_auto() -> None:
    text = _read(".claude/commands/flow/auto.md")
    # eli5 necessity gate still runs before implementation.
    assert "eli5" in text.lower()
    # Issue-anchored branch enforcement moved into the Step-1 helper's --verify
    # gate (#581): auto.md must wire it and the helper must enforce it.
    assert "flow-start-resolve.sh --verify" in text
    script = _read("scripts/flow-start-resolve.sh")
    assert 'BRANCH="issue-${ISSUE_NUM}-${SLUG}"' in script
    assert "branch -m" in script
    # Squash-merge discipline is unchanged.
    assert "--squash" in text
    # Quality gates are unchanged.
    assert "lib.cicd run --plan finish" in text or "make verify" in text or "make lint" in text


def test_cross_session_cleanup_keeps_git_fallback() -> None:
    # /flow:merge and /flow:cleanup usually run in a fresh session where
    # ExitWorktree is a no-op, so the git-worktree removal path must remain.
    merge = _read(".claude/commands/flow/merge.md")
    cleanup = _read(".claude/commands/flow/cleanup.md")
    assert "git worktree remove" in merge or "worktree-remove.sh" in merge
    assert "git worktree" in cleanup


def test_worktree_remove_script_retained_as_fallback() -> None:
    assert (ROOT / "scripts" / "worktree-remove.sh").exists(), (
        "worktree-remove.sh must remain as the cross-session cleanup fallback"
    )


def test_stale_branch_guard_before_squash_merge() -> None:
    """Issue #462: bring a stale branch current + re-gate before the squash-merge.

    Both the /flow:auto Step 7 merge and the standalone /flow:merge Step 3 must,
    before ``gh pr merge --squash``, fetch ``origin/main``, merge it into a branch
    that is behind, and re-run the quality gate on the POST-MERGE tree - so the
    squash is deterministic and the gate reflects exactly what lands on ``main``.
    """
    for rel in (".claude/commands/flow/auto.md", ".claude/commands/flow/merge.md"):
        text = _read(rel)
        assert "git fetch origin main" in text, f"{rel} does not fetch origin/main before merge"
        # Behind-check + merge main in (not rebase) so the squash is conflict-free.
        assert "HEAD..origin/main" in text, f"{rel} does not test whether the branch is behind main"
        assert "git merge --no-edit origin/main" in text, f"{rel} does not merge main in before squash"
        # Conflicts are surfaced and stopped-on, never silently auto-resolved.
        assert "--diff-filter=U" in text, f"{rel} does not surface merge conflicts on STOP"
        # The re-gate runs on the merged tree via the deterministic runner.
        assert "lib.cicd run --plan finish" in text, f"{rel} does not re-gate the post-merge tree"


# ---------------------------------------------------------------------------
# Issue #486: native EnterWorktree + hand-built absolute `.claude/worktrees/...`
# path lands the edit in the MAIN repo, not the worktree. The fix is a directive
# (resolve paths from `git rev-parse --show-toplevel`) plus an advisory,
# fail-open guard (scripts/flow-worktree-guard.sh) that makes the leak
# VERIFIABLE: run from a linked worktree, it warns when the main working tree has
# tracked modifications - the leaked-edit signature.
# ---------------------------------------------------------------------------

GUARD = ROOT / "scripts" / "flow-worktree-guard.sh"

# The behaviour tests drive real `git` and `bash` subprocesses. The Woodpecker
# `validate` step runs in `uv:python3.11-bookworm-slim`, which ships bash but NOT
# git, so those tests skip there (issue #430). The wiring tests need neither.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)


def test_path_rule_directive_in_docs() -> None:
    """AC #2: a directive documents the show-toplevel path-resolution rule."""
    for rel in ("CLAUDE.md", ".claude/commands/flow/auto.md", ".claude/commands/flow/start.md"):
        text = _read(rel)
        assert "git rev-parse --show-toplevel" in text, f"{rel} lacks the show-toplevel rule"
        assert "#486" in text or "486" in text, f"{rel} does not reference issue #486"


def test_auto_wires_worktree_guard_at_step4_and_step6() -> None:
    """AC #1: /flow:auto runs the leak guard both at implement and before commit."""
    text = _read(".claude/commands/flow/auto.md")
    assert text.count("scripts/flow-worktree-guard.sh") >= 2, (
        "auto.md must invoke the worktree guard in Step 4 (implement) and Step 6 (pre-commit)"
    )


def test_guard_script_exists_and_executable() -> None:
    assert GUARD.exists(), "scripts/flow-worktree-guard.sh must exist"
    assert os.access(GUARD, os.X_OK), "flow-worktree-guard.sh must be executable"


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


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GUARD), *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _make_repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A main repo on ``main`` with a tracked file, plus a linked worktree."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "tracked.txt").write_text("v0\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    wt = main / ".claude" / "worktrees" / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "feature")
    return main, wt


@requires_git
def test_guard_silent_when_main_clean(tmp_path: Path) -> None:
    _main, wt = _make_repo_with_worktree(tmp_path)
    res = _run(wt)
    assert res.returncode == 0
    assert res.stdout == "" and res.stderr == ""


@requires_git
def test_guard_warns_on_leaked_edit_from_worktree(tmp_path: Path) -> None:
    # The leak signature (issue #486/#536): a path this run edited in the worktree
    # ALSO shows up modified in MAIN. The overlap is what makes it a leak rather
    # than unrelated pre-existing dirt.
    main, wt = _make_repo_with_worktree(tmp_path)
    (wt / "tracked.txt").write_text("intended-in-worktree\n")
    (main / "tracked.txt").write_text("LEAKED\n")
    res = _run(wt)
    assert res.returncode == 0  # advisory: never blocks
    assert "WARNING" in res.stderr
    assert "tracked.txt" in res.stderr
    assert "#486" in res.stderr


@requires_git
def test_guard_strict_exits_nonzero_on_leak(tmp_path: Path) -> None:
    main, wt = _make_repo_with_worktree(tmp_path)
    (wt / "tracked.txt").write_text("intended-in-worktree\n")
    (main / "tracked.txt").write_text("LEAKED\n")
    res = _run(wt, "--strict")
    assert res.returncode == 3
    assert "tracked.txt" in res.stderr


@requires_git
def test_guard_downgrades_nonoverlapping_main_dirt_to_info(tmp_path: Path) -> None:
    """Issue #536: pre-existing main dirt on a file THIS run did not touch is not a
    leak - downgrade to a quiet info note, never a WARNING or a --strict failure."""
    main, wt = _make_repo_with_worktree(tmp_path)
    # Main carries a pre-existing modification unrelated to this run...
    (main / "tracked.txt").write_text("pre-existing-unrelated\n")
    # ...while the run edits a DIFFERENT file in the worktree.
    (wt / "other.txt").write_text("mine\n")
    res = _run(wt, "--strict")
    assert res.returncode == 0, "non-overlapping main dirt must not fail, even --strict"
    assert "WARNING" not in res.stderr
    assert "note" in res.stderr and "tracked.txt" in res.stderr
    assert "#536" in res.stderr


@requires_git
def test_guard_warns_on_total_leak_idle_worktree(tmp_path: Path) -> None:
    """Issue #573: a TOTAL leak leaves the worktree pristine, so nothing overlaps.
    When the run produced NO worktree activity yet main has a FRESHLY edited tracked
    file, that is the total-leak signature - warn (advisory: still exit 0)."""
    main, wt = _make_repo_with_worktree(tmp_path)
    # Every edit "leaked" to main; the worktree is untouched (no commits, no dirt).
    (main / "tracked.txt").write_text("LEAKED-ALL-OF-IT\n")
    res = _run(wt)
    assert res.returncode == 0  # advisory: never blocks
    assert "WARNING" in res.stderr
    assert "tracked.txt" in res.stderr
    assert "#573" in res.stderr
    assert "NO worktree changes" in res.stderr


@requires_git
def test_guard_strict_fails_on_total_leak(tmp_path: Path) -> None:
    """Under --strict the total-leak signature fails (exit 3), like an overlap leak."""
    main, wt = _make_repo_with_worktree(tmp_path)
    (main / "tracked.txt").write_text("LEAKED-ALL-OF-IT\n")
    res = _run(wt, "--strict")
    assert res.returncode == 3
    assert "WARNING" in res.stderr
    assert "tracked.txt" in res.stderr


@requires_git
def test_guard_total_leak_stale_main_stays_quiet(tmp_path: Path) -> None:
    """The freshness filter keeps #573 from re-crying-wolf on genuinely pre-existing
    main dirt: an idle worktree + STALE main edit (older than FRESH_MIN) is a quiet
    note, never a WARNING or --strict failure (preserves the issue #536 intent)."""
    main, wt = _make_repo_with_worktree(tmp_path)
    (main / "tracked.txt").write_text("pre-existing-unrelated\n")
    # Backdate the main edit two hours so it falls outside the freshness window.
    stale = time.time() - 7200
    os.utime(main / "tracked.txt", (stale, stale))
    res = _run(wt, "--strict")
    assert res.returncode == 0, "stale main dirt with an idle worktree must not fail"
    assert "WARNING" not in res.stderr
    assert "note" in res.stderr and "tracked.txt" in res.stderr


@requires_git
def test_guard_warns_on_overlap_even_with_unrelated_dirt(tmp_path: Path) -> None:
    """A real overlap still warns even when other unrelated main dirt is present."""
    main, wt = _make_repo_with_worktree(tmp_path)
    (main / "tracked.txt").write_text("also-in-main\n")  # overlaps the wt edit
    (wt / "tracked.txt").write_text("edited-here\n")
    (main / "other.txt").write_text("unrelated\n")  # pre-existing, no overlap
    _git(main, "add", "other.txt")  # make it a tracked pre-existing mod
    _git(main, "commit", "-qm", "add other")
    (main / "other.txt").write_text("unrelated-dirty\n")
    res = _run(wt, "--strict")
    assert res.returncode == 3
    assert "WARNING" in res.stderr
    assert "tracked.txt" in res.stderr


@requires_git
def test_guard_noop_in_main_checkout_even_when_dirty(tmp_path: Path) -> None:
    """In the main checkout there is no separate tree to leak into - never warn."""
    main, _wt = _make_repo_with_worktree(tmp_path)
    (main / "tracked.txt").write_text("dirty-but-intentional\n")
    res = _run(main, "--strict")
    assert res.returncode == 0
    assert res.stderr == ""


@requires_git
def test_guard_fail_open_outside_git_repo(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    res = _run(plain, "--strict")
    assert res.returncode == 0
    assert res.stderr == ""


@requires_git
def test_guard_rejects_unknown_option(tmp_path: Path) -> None:
    _main, wt = _make_repo_with_worktree(tmp_path)
    res = _run(wt, "--bogus")
    assert res.returncode == 2


# ---------------------------------------------------------------------------
# Issue #576: /flow:auto Steps 4 and 6 invoke the guard WITH --strict, so exit 3
# now stops a run. That promotion is only safe if --strict distinguishes a leak
# from pre-existing dirt on a shared file the run legitimately also edits -
# otherwise the first high-traffic file (CLAUDE.md, a template) left uncommitted
# in main by someone else halts every subsequent flow run. Freshness is the
# discriminator, the same rule the #573 total-leak branch already applied.
# ---------------------------------------------------------------------------


@requires_git
def test_guard_strict_ignores_stale_overlap(tmp_path: Path) -> None:
    """Pre-existing main dirt on a file this run also edits warns but does NOT block."""
    main, wt = _make_repo_with_worktree(tmp_path)
    (wt / "tracked.txt").write_text("intended-in-worktree\n")
    (main / "tracked.txt").write_text("pre-existing-uncommitted-work\n")
    # Backdate main's copy well outside the 30m freshness window: this edit
    # predates the run, so it cannot be a leak FROM the run.
    stale = time.time() - 4 * 60 * 60
    os.utime(main / "tracked.txt", (stale, stale))

    res = _run(wt, "--strict")
    assert res.returncode == 0, (
        "stale overlapping dirt is someone else's uncommitted work, not a leak - "
        "it must not block a --strict run (issue #576)"
    )
    # It still WARNS: a human should look, the run just isn't stopped.
    assert "WARNING" in res.stderr
    assert "#576" in res.stderr


@requires_git
def test_guard_strict_still_blocks_fresh_overlap(tmp_path: Path) -> None:
    """The #486 leak signature is fresh by definition and must still exit 3."""
    main, wt = _make_repo_with_worktree(tmp_path)
    (wt / "tracked.txt").write_text("intended-in-worktree\n")
    (main / "tracked.txt").write_text("LEAKED\n")  # mtime = now
    res = _run(wt, "--strict")
    assert res.returncode == 3
    assert "blocking" in res.stderr


def test_auto_invokes_the_guard_in_strict_mode() -> None:
    """AC (#576 item 3): both call sites promoted from advisory to blocking."""
    text = _read(".claude/commands/flow/auto.md")
    assert text.count("flow-worktree-guard.sh --strict") >= 2, (
        "auto.md must invoke the guard with --strict at BOTH Step 4 and Step 6 "
        "(issue #576 promotion decision)"
    )
    assert "Exit 3 is a STOP" in text, (
        "auto.md must state that exit 3 stops the run, or --strict is decorative"
    )
