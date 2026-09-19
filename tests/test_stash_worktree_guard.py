"""Tests for scripts/stash-worktree-guard.sh - the #1056 shared-stash guard.

THE NEGATIVE CONTROL THIS FILE CARRIES, stated by issue #1056 itself:

    "A `git stash push` attempted from a linked worktree must be refused, and
    the same command from the main checkout must behave as configured -
    otherwise the guard cannot distinguish the two cases it exists to separate."

Both halves are here, on REAL repositories with REAL linked worktrees, because
the property under test is a property of git's ref plumbing and no fixture
shaped like it would exercise the thing that failed. `test_blind_guard_*` runs
the same known-bad input against a hook that always exits 0 and asserts the
FIRST half fails there - so a green from this file is a claim about the guard
rather than about the harness.

The pop/drop limitation is pinned deliberately (see `test_pop_is_not_guarded`).
It is not an oversight to be fixed later: git removes the entry before the hook
can veto, so a guard that acted on deletions would refuse AFTER the damage.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "stash-worktree-guard.sh"

NULL_TREE_MARKER = "stash-worktree-guard: REFUSED"

requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A main checkout plus one linked worktree - the population that shares a stack."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "f.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "wtbranch")
    return main, wt


def _install(guard: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(guard), "--install", str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )


def _stash_push(cwd: Path, msg: str, env: dict[str, str] | None = None):
    import os

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        ["git", "-C", str(cwd), "stash", "push", "-m", msg],
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
    )


# ---------------------------------------------------------------------------
# Wiring - these need no binary and always run.
# ---------------------------------------------------------------------------


def test_guard_script_exists_and_is_executable() -> None:
    import os

    assert GUARD.is_file(), "scripts/stash-worktree-guard.sh must exist"
    assert os.access(GUARD, os.X_OK), "stash-worktree-guard.sh must be executable"


def test_header_states_the_pop_limitation() -> None:
    """The limitation must be in the file, not only in the issue.

    A reader who trusts this guard to mean "stash is handled in worktrees" is
    wrong in a way that costs them another session's work. The script says so;
    this pins that it keeps saying so.
    """
    text = GUARD.read_text()
    assert "does NOT guard" in text or "does not guard" in text.lower()
    assert "pop" in text and "drop" in text


# ---------------------------------------------------------------------------
# THE NEGATIVE CONTROL - both halves, on real git.
# ---------------------------------------------------------------------------


@requires_git
def test_push_from_linked_worktree_is_refused(tmp_path: Path) -> None:
    """Half one: the known-bad input must be REFUSED."""
    main, wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    (wt / "f.txt").write_text("base\nworktree-work\n")
    result = _stash_push(wt, "should-refuse")

    assert result.returncode != 0, "a worktree stash push must not succeed"
    assert NULL_TREE_MARKER in result.stderr, (
        f"the refusal must identify itself; got: {result.stderr!r}"
    )


@requires_git
def test_refused_push_leaves_the_working_tree_byte_identical(tmp_path: Path) -> None:
    """A refusal that damaged the tree would be worse than no guard at all.

    This is the assertion that makes the guard safe to install repo-wide: the
    abort happens at `prepared`, before git touches any file.
    """
    main, wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    (wt / "f.txt").write_text("base\nworktree-work\n")
    before = (wt / "f.txt").read_bytes()

    _stash_push(wt, "should-refuse")

    assert (wt / "f.txt").read_bytes() == before, "the refusal MOVED the user's work"
    assert _git(wt, "stash", "list").stdout.strip() == "", "an entry was created anyway"


@requires_git
def test_push_from_main_checkout_still_works(tmp_path: Path) -> None:
    """Half two: the known-GOOD input must behave as configured.

    Without this the guard could be wedged at "refuse" and half one would still
    pass - which is the difference between a working guard and a broken one.
    """
    main, _wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    (main / "f.txt").write_text("base\nmain-work\n")
    result = _stash_push(main, "should-allow")

    assert result.returncode == 0, f"main-checkout stash must succeed: {result.stderr!r}"
    assert "should-allow" in _git(main, "stash", "list").stdout


@requires_git
def test_blind_guard_fails_the_known_bad_case(tmp_path: Path) -> None:
    """Prove this file can FAIL: a hook that never refuses must not pass half one.

    A control that has never been observed failing is a control whose green is
    unearned. This runs the identical known-bad input against a deliberately
    blind hook and asserts the outcome flips.
    """
    main, wt = _make_repo(tmp_path)
    hooks = Path(_git(main, "rev-parse", "--git-common-dir").stdout.strip())
    if not hooks.is_absolute():
        hooks = (main / hooks).resolve()
    hook = hooks / "hooks" / "reference-transaction"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/usr/bin/env bash\nexit 0\n")
    hook.chmod(0o755)

    (wt / "f.txt").write_text("base\nworktree-work\n")
    result = _stash_push(wt, "blind-lets-this-through")

    assert result.returncode == 0, "the blind hook should not have refused"
    assert NULL_TREE_MARKER not in result.stderr
    assert "blind-lets-this-through" in _git(wt, "stash", "list").stdout, (
        "the known-bad input must actually reach the stack when the guard is blind - "
        "otherwise the real guard's refusal proves nothing"
    )


# ---------------------------------------------------------------------------
# Bounds: what it must NOT do.
# ---------------------------------------------------------------------------


@requires_git
def test_pop_is_not_guarded(tmp_path: Path) -> None:
    """PIN, not an aspiration (issue #1056).

    Measured on git 2.43.0: on `pop` git applies the stash and drops the entry
    BEFORE the hook's veto is effective, so refusing there would leave the tree
    mutated and the entry gone - strictly worse than not guarding. The guard
    therefore acts only on entry CREATION.

    If someone later "completes" the guard by acting on deletions, this test
    fails and tells them what they actually did.
    """
    main, wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    # An entry created legitimately from the main checkout ...
    (main / "f.txt").write_text("base\nfrom-main\n")
    assert _stash_push(main, "from-main").returncode == 0

    # ... is poppable from the linked worktree. The guard does not stop this.
    result = subprocess.run(
        ["git", "-C", str(wt), "stash", "pop"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert NULL_TREE_MARKER not in result.stderr, (
        "the guard refused a pop - it must not: git removes the entry first, so a "
        "refusal here fires after the damage. See the script header."
    )


@requires_git
def test_ordinary_ref_updates_are_unaffected(tmp_path: Path) -> None:
    """The hook fires on EVERY ref update, so this is the blast-radius check."""
    main, wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    (wt / "f.txt").write_text("base\ncommitted\n")
    assert _git(wt, "commit", "-qam", "wip", check=False).returncode == 0
    assert _git(wt, "branch", "probe", check=False).returncode == 0
    assert _git(wt, "tag", "probetag", check=False).returncode == 0
    assert _git(main, "branch", "probe-main", check=False).returncode == 0


@requires_git
def test_escape_hatch_permits_a_deliberate_stash(tmp_path: Path) -> None:
    main, wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    (wt / "f.txt").write_text("base\ndeliberate\n")
    result = _stash_push(wt, "tagged-entry", env={"CPP_ALLOW_WORKTREE_STASH": "1"})

    assert result.returncode == 0, f"escape hatch must work: {result.stderr!r}"
    assert "tagged-entry" in _git(wt, "stash", "list").stdout


@requires_git
def test_guard_is_inert_in_a_repo_with_no_linked_worktree(tmp_path: Path) -> None:
    """A repository with no worktrees shares its stack with nobody."""
    main = tmp_path / "solo"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "f.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "init")
    assert _install(GUARD, main).returncode == 0

    (main / "f.txt").write_text("base\nedit\n")
    assert _stash_push(main, "solo").returncode == 0


# ---------------------------------------------------------------------------
# Installer lane.
# ---------------------------------------------------------------------------


@requires_git
def test_install_refuses_to_overwrite_a_foreign_hook(tmp_path: Path) -> None:
    """A reference-transaction hook fires on every ref update - never clobber one."""
    main, _wt = _make_repo(tmp_path)
    hooks = main / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    foreign = hooks / "reference-transaction"
    foreign.write_text("#!/usr/bin/env bash\n# somebody else's hook\nexit 0\n")
    foreign.chmod(0o755)

    result = _install(GUARD, main)

    assert result.returncode != 0
    assert "STASH_GUARD: foreign" in result.stdout
    assert "somebody else's hook" in foreign.read_text(), "the foreign hook was overwritten"


@requires_git
def test_check_reports_absent_then_current(tmp_path: Path) -> None:
    main, _wt = _make_repo(tmp_path)

    before = subprocess.run(
        ["bash", str(GUARD), "--check", str(main)], capture_output=True, text=True, check=False
    )
    assert "STASH_GUARD: absent" in before.stdout
    assert before.returncode != 0

    assert _install(GUARD, main).returncode == 0

    after = subprocess.run(
        ["bash", str(GUARD), "--check", str(main)], capture_output=True, text=True, check=False
    )
    assert "STASH_GUARD: current" in after.stdout
    assert after.returncode == 0


@requires_git
def test_check_from_a_linked_worktree_resolves_the_same_hook(tmp_path: Path) -> None:
    """One install must cover the whole worktree family, as the stack does."""
    main, wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    result = subprocess.run(
        ["bash", str(GUARD), "--check", str(wt)], capture_output=True, text=True, check=False
    )
    assert "STASH_GUARD: current" in result.stdout


@requires_git
def test_install_follows_core_hookspath(tmp_path: Path) -> None:
    """A repo with `core.hooksPath` set must be guarded WHERE GIT READS.

    Counter-model finding on this branch: resolving the common dir's `hooks/`
    directly would install into a directory git never consults and report
    success, while every worktree push stayed unguarded - a guard reporting
    enforcement it does not have.
    """
    main, wt = _make_repo(tmp_path)
    custom = tmp_path / "custom-hooks"
    custom.mkdir()
    _git(main, "config", "core.hooksPath", str(custom))

    assert _install(GUARD, main).returncode == 0
    assert (custom / "reference-transaction").exists(), (
        "installed into the common dir's hooks/ while git reads core.hooksPath"
    )

    # The claim that matters is not where the file landed - it is that a push
    # from the worktree is actually refused.
    (wt / "f.txt").write_text("base\nworktree-work\n")
    result = _stash_push(wt, "should-refuse")
    assert result.returncode != 0
    assert NULL_TREE_MARKER in result.stderr


@requires_git
def test_install_refuses_a_relative_core_hookspath(tmp_path: Path) -> None:
    """One install cannot cover the family when core.hooksPath is RELATIVE.

    Measured: each worktree resolves a relative hooksPath against its OWN
    top-level, so a hook in `main/.githooks` is not read by `../wt` at all. An
    `installed` verdict there would claim family-wide coverage the configuration
    cannot provide (counter-model finding, this branch).
    """
    main, _wt = _make_repo(tmp_path)
    _git(main, "config", "core.hooksPath", ".githooks")

    result = _install(GUARD, main)

    assert result.returncode != 0
    assert "STASH_GUARD: unsupported" in result.stdout
    assert not (main / ".githooks" / "reference-transaction").exists()


@requires_git
def test_relative_hookspath_really_is_per_worktree(tmp_path: Path) -> None:
    """The precondition behind the refusal above, asserted rather than assumed."""
    main, wt = _make_repo(tmp_path)
    _git(main, "config", "core.hooksPath", ".githooks")
    hooks = main / ".githooks"
    hooks.mkdir()
    (hooks / "reference-transaction").write_text("#!/usr/bin/env bash\nexit 1\n")
    (hooks / "reference-transaction").chmod(0o755)

    (wt / "f.txt").write_text("base\nworktree-work\n")
    result = _stash_push(wt, "unguarded-relative-hookspath")

    assert result.returncode == 0, "the worktree read the main checkout's relative hooksPath"
    assert "unguarded-relative-hookspath" in _git(wt, "stash", "list").stdout


@requires_git
def test_absolute_core_hookspath_is_still_supported(tmp_path: Path) -> None:
    """The refusal must be narrow: an ABSOLUTE hooksPath IS shared by the family."""
    main, wt = _make_repo(tmp_path)
    custom = tmp_path / "abs-hooks"
    custom.mkdir()
    _git(main, "config", "core.hooksPath", str(custom))

    assert _install(GUARD, main).returncode == 0
    (wt / "f.txt").write_text("base\nworktree-work\n")
    assert NULL_TREE_MARKER in _stash_push(wt, "should-refuse").stderr


@requires_git
def test_check_refuses_current_for_a_non_executable_hook(tmp_path: Path) -> None:
    """git SILENTLY IGNORES a non-executable hook, so identical bytes prove nothing.

    Counter-model finding on this branch: `--check` compared content only and
    reported `current` for a mode-0644 copy that git would never run.
    """
    main, _wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0
    hook = main / ".git" / "hooks" / "reference-transaction"
    hook.chmod(0o644)

    result = subprocess.run(
        ["bash", str(GUARD), "--check", str(main)], capture_output=True, text=True, check=False
    )
    assert "STASH_GUARD: current" not in result.stdout, (
        "reported `current` for a hook git ignores - the verdict claims enforcement "
        "this run did not establish"
    )
    assert "STASH_GUARD: stale" in result.stdout
    assert result.returncode != 0


@requires_git
def test_a_non_executable_hook_really_is_ignored_by_git(tmp_path: Path) -> None:
    """The precondition behind the test above, asserted rather than assumed.

    If git ever started honouring non-executable hooks, the check above would be
    guarding a condition that no longer exists and would say nothing while
    looking identical. This fails loudly in that world instead.
    """
    main, wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0
    (main / ".git" / "hooks" / "reference-transaction").chmod(0o644)

    (wt / "f.txt").write_text("base\nworktree-work\n")
    result = _stash_push(wt, "unguarded-because-not-executable")
    assert result.returncode == 0, "git honoured a non-executable hook"
    assert "unguarded-because-not-executable" in _git(wt, "stash", "list").stdout


@requires_git
def test_uninstall_removes_only_our_hook(tmp_path: Path) -> None:
    main, _wt = _make_repo(tmp_path)
    assert _install(GUARD, main).returncode == 0

    result = subprocess.run(
        ["bash", str(GUARD), "--uninstall", str(main)], capture_output=True, text=True, check=False
    )
    assert "STASH_GUARD: absent" in result.stdout
    assert not (main / ".git" / "hooks" / "reference-transaction").exists()
