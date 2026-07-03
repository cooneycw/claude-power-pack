"""Regression tests for issue #440: /flow rides native worktrees.

These pin the migration from bespoke ``git worktree add/remove`` plumbing to
Claude Code's native ``EnterWorktree``/``ExitWorktree`` tools, while proving the
issue-anchored gate policy (the moat) stays layered on top: the eli5 necessity
gate, quality gates, the ``issue-<N>-<slug>`` branch name, squash-merge
discipline, and the cross-session ``git worktree`` cleanup fallback.
"""

from __future__ import annotations

from pathlib import Path

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
    # cross-machine path (which git-adds "$LOCAL_BRANCH") is intentionally kept.
    for rel in (".claude/commands/flow/start.md", ".claude/commands/flow/auto.md"):
        text = _read(rel)
        assert 'WORKTREE_DIR="../' not in text, f"{rel} still creates a sibling worktree dir"
        assert 'git worktree add -b "$BRANCH"' not in text, f"{rel} still git-adds the fresh path"


def test_native_worktrees_are_gitignored() -> None:
    assert ".claude/worktrees/" in _read(".gitignore")


def test_moat_preserved_in_auto() -> None:
    text = _read(".claude/commands/flow/auto.md")
    # eli5 necessity gate still runs before implementation.
    assert "eli5" in text.lower()
    # Issue-anchored branch name is enforced after native creation.
    assert 'BRANCH="issue-${ISSUE_NUM}-${SLUG}"' in text
    assert "git branch -m" in text
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
