"""Regression tests for Nit Store #864 (comments 5983011277, 6155393127):
worktree-remove.sh's undeletable-path pre-scan and --allow-dirty-without-force
gaps.

Root cause 1 (undeletable path): `git worktree remove` can report SUCCESS while
a path survives it - observed here with a parent directory that lacks write
permission, so git cannot unlink the entry inside it. That leaves a half-
deleted worktree with no `.git` file behind. The fix here is prevention: a
pre-scan refuses before deleting anything (exit 9, naming the path). Completing
an already half-deleted worktree was attempted as --finish-partial-removal and
removed from this PR after a third cross-model review pass found that nearby-
repo discovery can never prove a worktree is unowned - only that it isn't
registered with whatever repos happen to be reachable nearby - which is a
structural gap, not a bug to patch; see claude-power-pack#1491 for the
decision and the follow-up issue for a redesigned, POSITIVE-ownership version.

Root cause 2 (--allow-dirty without --force): `--allow-dirty` only cleared this
helper's OWN dirty-tree refusal. `git worktree remove` makes its own separate
judgment about a dirty tree and still refused without `--force` (exit 128,
undocumented) - so `--allow-dirty` alone used to remove nothing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "worktree-remove.sh"

requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

requires_proc = pytest.mark.skipif(
    not Path("/proc/self/cwd").exists(),
    reason="occupancy detection reads /proc (Linux only)",
)

# Permission-based refusals mean nothing to root (CAP_DAC_OVERRIDE bypasses the
# write-bit check this whole file exercises), so these tests would pass for the
# wrong reason - or not at all - in a container that runs as root.
requires_non_root = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="permission-based refusals are meaningless to root",
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


def _run_remove(
    cwd: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        env=run_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )


def _repo(tmp_path: Path) -> Path:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "base.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    return main


def _add_worktree(main: Path, path: Path, branch: str) -> Path:
    _git(main, "worktree", "add", "-q", str(path), "-b", branch)
    return path


def _make_locked_dir(wt: Path) -> Path:
    """An untracked directory whose own mode refuses unlink/rmdir of its
    contents - the permission shape that lets `git worktree remove` leave
    files behind while still reporting success."""
    locked = wt / "locked"
    locked.mkdir()
    (locked / "file.txt").write_text("data\n")
    locked.chmod(0o555)
    return locked


def _unlock(locked: Path) -> None:
    # So pytest's tmp_path teardown (and a failed test) can still clean up.
    if locked.exists():
        locked.chmod(0o755)


@requires_git
@requires_non_root
def test_prescan_refuses_before_deleting_an_undeletable_path(tmp_path: Path) -> None:
    """Nit Store #864 (comment 5983011277): refuse before deleting anything,
    rather than letting `git worktree remove` silently leave a half-deleted
    worktree behind. Nothing must be touched when the pre-scan refuses."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    locked = _make_locked_dir(wt)
    try:
        res = _run_remove(main, str(wt), "--force", "--allow-dirty")

        assert res.returncode == 9, (
            f"expected the pre-scan refusal (exit 9), got {res.returncode}\n"
            f"stdout={res.stdout}\nstderr={res.stderr}"
        )
        assert str(locked) in res.stderr, res.stderr
        # Refused BEFORE deleting anything: the worktree is fully intact.
        assert (wt / ".git").is_file()
        assert (locked / "file.txt").is_file()
    finally:
        _unlock(locked)


@requires_git
def test_allow_dirty_alone_removes_without_force(tmp_path: Path) -> None:
    """Nit Store #864 (comment 6155393127): `--allow-dirty` must actually
    remove a dirty worktree, not merely clear this helper's own refusal and
    then hand the job to a `git worktree remove` that refuses right behind it
    (exit 128, "use --force to delete it")."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "base.txt").write_text("dirty\n")

    res = _run_remove(main, str(wt), "--allow-dirty")

    assert res.returncode == 0, (
        f"--allow-dirty must remove a dirty worktree on its own:\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert not wt.exists()


@pytest.fixture()
def occupant():
    """Spawn a real long-lived process whose cwd is a given directory (same
    shape as test_worktree_remove_occupied.py's fixture - a real process
    rather than a synthetic /proc tree, so it proves the matcher agrees with
    reality rather than with the author's idea of /proc)."""
    procs: list[subprocess.Popen] = []

    def _spawn(cwd: Path) -> subprocess.Popen:
        p = subprocess.Popen(
            ["sleep", "60"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 5
        link = Path(f"/proc/{p.pid}/cwd")
        while time.time() < deadline:
            try:
                if link.resolve() == cwd.resolve():
                    break
            except OSError:
                pass
            time.sleep(0.02)
        procs.append(p)
        return p

    yield _spawn

    for p in procs:
        p.kill()
        p.wait()


@requires_git
@requires_proc
def test_allow_dirty_does_not_defeat_the_occupancy_guard(
    tmp_path: Path, occupant
) -> None:
    """cnb-orch review of #1491: confirm that making --allow-dirty imply
    --force does not also weaken the #888 occupancy guard, which --force
    alone was never able to suppress (occupancy is a hard stop regardless of
    FORCE; this pins that the new auto-force path is no different)."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "base.txt").write_text("dirty\n")
    occupant(wt)

    res = _run_remove(main, str(wt), "--allow-dirty")

    assert res.returncode == 5, (
        f"expected the #888 in-use refusal (exit 5), got {res.returncode}\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert wt.exists()


@requires_git
@requires_proc
def test_allow_dirty_does_not_defeat_a_live_claim(
    tmp_path: Path, occupant
) -> None:
    """Same concern, for the #597 cross-session claim: a worktree another
    live session genuinely HOLDS must stay refused (exit 4) under
    --allow-dirty's auto-force, exactly as it already does under --force."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "base.txt").write_text("dirty\n")

    claim_helper = ROOT / "scripts" / "flow-worktree-claim.sh"
    if not claim_helper.is_file():
        pytest.skip("flow-worktree-claim.sh not present")

    # A real, separate live process stands in for "another session's pid" -
    # claimed under ITS pid/session, then checked under OUR OWN (different)
    # identity, which is what makes the claim read as foreign rather than self.
    owner = occupant(tmp_path)
    claim_env = {
        **os.environ,
        "CLAUDE_PID": str(owner.pid),
        "CLAUDE_CODE_SESSION_ID": "other-session",
    }
    held = subprocess.run(
        ["bash", str(claim_helper), "claim", str(wt), "--issue", "999"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=claim_env,
    )
    if held.returncode != 0:
        pytest.skip(f"could not stake a claim: {held.stderr}")

    res = _run_remove(main, str(wt), "--allow-dirty")

    assert res.returncode == 4, (
        f"expected the #597 live-claim refusal (exit 4), got {res.returncode}\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert wt.exists()


@requires_git
@requires_non_root
def test_prescan_refuses_on_an_unreadable_directory_not_just_unwritable(
    tmp_path: Path,
) -> None:
    """Codex review of #1491: a 0300 (write+execute, no READ) directory passed
    a write/execute-only check, but `find` cannot enumerate what is inside it
    either - the scan silently stopped exactly where it should have reported,
    and an incomplete walk must not read as a clean one."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    blocked = wt / "blocked"
    blocked.mkdir()
    (blocked / "inner").mkdir()
    (blocked / "inner" / "file.txt").write_text("data\n")
    blocked.chmod(0o300)
    try:
        res = _run_remove(main, str(wt), "--force", "--allow-dirty")

        assert res.returncode == 9, (
            f"expected the pre-scan refusal (exit 9), got {res.returncode}\n"
            f"stdout={res.stdout}\nstderr={res.stderr}"
        )
        assert "not the same as clean" in res.stderr or str(blocked) in res.stderr
        assert (wt / ".git").is_file()
    finally:
        blocked.chmod(0o755)


@requires_git
@requires_non_root
def test_prescan_checks_the_worktree_roots_own_parent(tmp_path: Path) -> None:
    """Codex review of #1491: emptying every descendant still leaves one more
    removal - rmdir on the worktree ROOT itself - which needs write+execute
    on a directory `find "$root" ...` never walks, because it is OUTSIDE the
    root. A non-writable parent must refuse exactly like an internal one."""
    main = _repo(tmp_path)
    parent = tmp_path / "parent"
    parent.mkdir()
    wt = _add_worktree(main, parent / "wt", "feature")
    parent.chmod(0o500)
    try:
        res = _run_remove(main, str(wt), "--force", "--allow-dirty")

        assert res.returncode == 9, (
            f"expected the pre-scan refusal (exit 9), got {res.returncode}\n"
            f"stdout={res.stdout}\nstderr={res.stderr}"
        )
        assert str(parent) in res.stderr
        assert (wt / ".git").is_file()
    finally:
        parent.chmod(0o755)


# --------------------------------------------------------------------------- #
# --finish-partial-removal, redesigned around POSITIVE ownership (#1524).
# Replaces the discovery-based version removed above (20e72086): the caller
# must NAME the owner, and that repo's OWN registry must positively confirm
# the path as prunable, in git's own words - never a search.
# --------------------------------------------------------------------------- #


def _independent_repo(path: Path) -> Path:
    """A repo unrelated to any fixture's `main` - for the neighbour-repo red case."""
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    (path / "base.txt").write_text("base\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "base")
    return path


def _half_delete(wt: Path) -> None:
    """Simulate the state --finish-partial-removal exists for: directory
    present, .git FILE gone (the admin registration still names it)."""
    (wt / ".git").unlink()


def _run_printed_rm(stdout: str) -> None:
    """--finish-partial-removal PRINTS the verified command rather than
    running it (issue #1524, post pass-3). Extract the `rm -rf -- ...` line
    and actually execute it, so tests prove the PRINTED command is correct
    and runnable, not merely that something plausible-looking was printed."""
    rm_line = next(line for line in stdout.splitlines() if line.startswith("rm -rf -- "))
    subprocess.run(["bash", "-c", rm_line], check=True)


# Reuses the `occupant` fixture already defined above (line ~163) for the
# normal-path occupancy tests - same shape, no need for a second one.


@requires_git
def test_finish_partial_removal_requires_owner_repo(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(main, str(wt), "--finish-partial-removal")

    assert res.returncode == 10, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "requires --owner-repo" in res.stderr
    assert wt.exists()  # refused before touching anything


@requires_git
def test_owner_repo_without_finish_partial_removal_is_refused(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")

    res = _run_remove(main, str(wt), "--owner-repo", str(main))

    assert res.returncode == 10, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "only meaningful with --finish-partial-removal" in res.stderr


@requires_git
def test_finish_partial_removal_rejects_embedded_newline(tmp_path: Path) -> None:
    """Red case 2 (#1524): a trailing-newline path corrupts a line-based
    registry comparison via command-substitution's trailing-newline strip.
    The redesign removes the whole class: refuse outright, never compare."""
    main = _repo(tmp_path)
    weird = tmp_path / "wt-with-a\nnewline"
    weird.mkdir()

    res = _run_remove(main, str(weird), "--finish-partial-removal", "--owner-repo", str(main))

    assert res.returncode == 11, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert weird.exists()


@requires_git
def test_owner_repo_must_be_a_readable_git_repo(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()

    res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(not_a_repo))

    assert res.returncode == 12, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists()


@requires_git
def test_an_unrelated_neighbour_repo_is_refused_as_owner(tmp_path: Path) -> None:
    """Red case 1 (#1524): the OLD discovery-based code asked only a nearby
    unrelated repo, got 'not registered', and deleted anyway - a repo that
    truthfully never had the path answers identically to one simply never
    asked. Pre-#1524 (no --finish-partial-removal at all) this fails because
    the flag does not exist - an unknown-argument-style failure, stated here
    rather than implied as testing a security property the old code had none
    of. Post-#1524: the unrelated neighbour must be refused, and only the
    TRUE owner succeeds."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)
    neighbour = _independent_repo(tmp_path / "neighbour")

    res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(neighbour))

    assert res.returncode == 13, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists(), "the neighbour's refusal must not have deleted anything"

    res2 = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty", "--allow-unpushed"
    )

    assert res2.returncode == 15, f"stdout={res2.stdout}\nstderr={res2.stderr}"
    assert wt.exists(), "verify-and-print removes nothing itself"
    _run_printed_rm(res2.stdout)
    assert not wt.exists()


@requires_git
def test_a_locked_half_deleted_worktree_is_refused(tmp_path: Path) -> None:
    """Measured (#1524): git reports `prunable` for a half-deleted worktree,
    but a LOCKED one in the identical state carries `locked <reason>` and no
    prunable line at all - so requiring the prunable attribute already
    refuses this case with no extra code."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _git(main, "worktree", "lock", str(wt), "--reason", "testing")
    _half_delete(wt)

    res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(main))

    assert res.returncode == 13, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists()


@requires_git
@requires_non_root
def test_an_unreadable_worktrees_admin_dir_is_a_refusal_not_a_silent_pass(tmp_path: Path) -> None:
    """Measured (#1524): denying read on .git/worktrees does NOT make
    `git worktree list --porcelain -z` fail outright - git silently OMITS
    the entry it cannot enumerate, exit 0, as if that worktree did not
    exist. That is a DEGRADED read, not a command failure, and it must still
    refuse: 'the record is absent from a successful listing' and 'the record
    is absent because the listing failed' both have to land on the same
    refusal, never be mistaken for 'not found, so nothing says no'."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)
    worktrees_admin = main / ".git" / "worktrees"
    assert worktrees_admin.is_dir()
    worktrees_admin.chmod(0o000)
    try:
        res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(main))

        assert res.returncode == 13, f"stdout={res.stdout}\nstderr={res.stderr}"
        assert wt.exists()
    finally:
        worktrees_admin.chmod(0o755)


@requires_git
def test_the_porcelain_command_itself_failing_is_also_a_refusal(tmp_path: Path) -> None:
    """The genuine 'git worktree list --porcelain -z' NON-ZERO EXIT branch,
    distinct from the degraded-listing case above (#1524): a `git` on PATH
    that fails that exact subcommand while `rev-parse --git-dir` (asked
    first, to validate --owner-repo) still succeeds. Isolates the `! git
    ... > file` check itself, never exercised by a real git in this repo
    (git tolerates unreadable admin entries by omission, not failure)."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    real_git = shutil.which("git")
    assert real_git is not None
    bindir = tmp_path / "stub-bin"
    bindir.mkdir()
    stub = bindir / "git"
    stub.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        '  *" worktree list --porcelain "*)\n'
        '    echo "fatal: stubbed failure" >&2\n'
        "    exit 1\n"
        "    ;;\n"
        "esac\n"
        f'exec "{real_git}" "$@"\n'
    )
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}

    res = subprocess.run(
        ["bash", str(SCRIPT), str(wt), "--finish-partial-removal", "--owner-repo", str(main)],
        cwd=main, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60,
    )

    assert res.returncode == 13, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "could not read" in res.stderr
    assert wt.exists()


@requires_git
@requires_proc
def test_occupancy_refuses_a_live_process_in_the_half_deleted_path(
    tmp_path: Path, occupant
) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)
    occupant(wt)

    res = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty", "--allow-unpushed"
    )

    assert res.returncode == 5, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists()


@requires_git
@requires_non_root
def test_prescan_refuses_an_undeletable_path_in_finish_partial_removal(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    locked = _make_locked_dir(wt)
    _half_delete(wt)
    try:
        res = _run_remove(
            main, str(wt), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty", "--allow-unpushed"
        )

        assert res.returncode == 9, f"stdout={res.stdout}\nstderr={res.stderr}"
        assert str(locked) in res.stderr
        assert wt.exists()
    finally:
        _unlock(locked)


@requires_git
def test_finish_partial_removal_succeeds_with_the_true_owner(tmp_path: Path) -> None:
    """Verify-and-print, not auto-remove (issue #1524, owner decision after
    pass 3): a confirmed-ownership pass prints the exact rm -rf command
    rather than removing anything itself."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty", "--allow-unpushed"
    )

    assert res.returncode == 15, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists(), "verify-and-print removes nothing itself"
    assert f"rm -rf -- {wt}" in res.stdout
    assert f"git -C {main} worktree prune --dry-run --verbose" in res.stdout
    _run_printed_rm(res.stdout)
    assert not wt.exists()
    # The admin registration is NOT pruned by this tool - the printed
    # command is a dry-run hint for the human to review, never run for them.
    assert "feature" in _git(main, "worktree", "list")


@requires_git
def test_finish_partial_removal_requires_allow_dirty(tmp_path: Path) -> None:
    """Codex cross-model review (#1524, pass 1, HIGH): removing .git does not
    remove the FILES - a worktree with real uncommitted or untracked work is
    still full of exactly that content, and there is no `git status` left to
    verify it is clean. --allow-dirty is REQUIRED here, not merely honoured,
    because the state it normally overrides cannot be checked at all."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "uncommitted.txt").write_text("real work that was never pushed\n")
    _half_delete(wt)

    res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(main))

    assert res.returncode == 14, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "cannot verify this path is clean" in res.stderr
    assert wt.exists()
    assert (wt / "uncommitted.txt").is_file()

    res2 = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty", "--allow-unpushed"
    )

    assert res2.returncode == 15, f"stdout={res2.stdout}\nstderr={res2.stderr}"
    assert wt.exists(), "verify-and-print removes nothing itself"
    _run_printed_rm(res2.stdout)
    assert not wt.exists()


@requires_git
def test_newline_guard_also_covers_the_resolved_symlink_target(tmp_path: Path) -> None:
    """Codex cross-model review (#1524, pass 1, HIGH): `readlink -f` STRIPS a
    trailing newline from its own output. The newline guard on WORKTREE_PATH
    alone would miss a newline-free symlink whose TARGET ends in a newline -
    WT_REAL would silently become the newline-stripped form, which could
    collide with a DIFFERENT registered path. WT_REAL is checked too now."""
    main = _repo(tmp_path)
    wt_with_newline = tmp_path / "wt-with-a\nnewline"
    wt_with_newline.mkdir()
    _git(main, "worktree", "add", "-q", str(wt_with_newline), "-b", "feature")
    _half_delete(wt_with_newline)
    link = tmp_path / "link-no-newline"
    link.symlink_to(wt_with_newline)

    res = _run_remove(
        main, str(link), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty", "--allow-unpushed"
    )

    assert res.returncode == 11, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt_with_newline.exists()


@requires_git
def test_a_newline_free_symlink_to_a_trailing_newline_target_cannot_collide(
    tmp_path: Path,
) -> None:
    """Codex cross-model review (#1524, pass 2, HIGH): plain command
    substitution (`WT_REAL="$(readlink -f ...)"`) strips a TRAILING newline
    from its own captured output - verified directly in a scratch dir before
    this fix, where it resolved to a byte-for-byte newline-free path. The
    pass-1 fix checked that already-stripped WT_REAL, so it could never see
    a newline in exactly this position. The exploit this closes: a SEPARATE,
    newline-free worktree happens to be registered at the stripped form of
    the trailing-newline target's path, so a naive resolution would silently
    match and delete the WRONG one. The fix (robust FP_WT_REAL, preserving
    the real trailing byte) must refuse outright - neither worktree touched -
    rather than letting the collision reach the registry comparison at all.
    """
    main = _repo(tmp_path)
    collider = tmp_path / "collider"
    collider.mkdir()
    _git(main, "worktree", "add", "-q", str(collider), "-b", "collider-branch")
    _half_delete(collider)

    real_target = tmp_path / ("collider" + "\n")
    real_target.mkdir()
    _git(main, "worktree", "add", "-q", str(real_target), "-b", "real-branch")
    _half_delete(real_target)

    link = tmp_path / "newline-free-link"
    link.symlink_to(real_target)

    res = _run_remove(
        main, str(link), "--finish-partial-removal", "--owner-repo", str(main),
        "--allow-dirty", "--allow-unpushed",
    )

    assert res.returncode == 11, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert collider.exists(), "the OTHER, newline-free worktree must never be touched"
    assert real_target.exists(), "the actual target must also survive - refused outright"


@requires_git
def test_a_symlink_to_the_worktree_is_left_dangling_not_deleted(tmp_path: Path) -> None:
    """Owner ruling (#1524): rm -rf on a symlink TO the worktree removes only
    the link, leaving the real directory behind as an orphan once `worktree
    prune` drops the registration - the opposite hazard from the one this
    flag exists to fix. The fix resolves the input via realpath ONCE, early,
    and PRINTS a command naming THAT, never the caller's own symlink - which
    is not part of the worktree and may live anywhere (a different repo, a
    home directory). The printed rm names the real directory; the symlink is
    warned about but never itself touched by this tool."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)
    link = tmp_path / "wt-link"
    link.symlink_to(wt)

    res = _run_remove(
        main, str(link), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty", "--allow-unpushed"
    )

    assert res.returncode == 15, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists(), "verify-and-print removes nothing itself"
    assert f"rm -rf -- {wt}" in res.stdout, "the printed command names the REAL target, not the symlink"
    assert str(link) not in res.stdout.split("\n")[1], "the symlink itself must never be the rm target"
    assert str(link) in res.stderr and "dangling" in res.stderr

    _run_printed_rm(res.stdout)

    assert not wt.exists(), "the real worktree directory is gone once the printed command runs"
    # The symlink itself survives, now genuinely dangling - never deleted by
    # this tool, only by the printed command the human chose to run.
    assert link.is_symlink(), "the caller's own symlink must not be deleted"
    assert not link.exists(), "but it is now dangling, since its target is gone"


@requires_git
def test_unpushed_commit_is_refused_without_allow_unpushed(tmp_path: Path) -> None:
    """Codex cross-model review (#1524, pass 2, HIGH): unlike dirtiness,
    unpushed-ness IS verifiable from the owner's own objects and remote-
    tracking refs, via the matched porcelain record's HEAD sha. No remote at
    all means nothing is pushed - must refuse, same #899 shape as the normal
    removal path's existing --allow-unpushed gate."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty"
    )

    assert res.returncode == 7, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "commits that are on no remote" in res.stderr
    assert wt.exists()


@requires_git
def test_a_pushed_commit_does_not_need_allow_unpushed(tmp_path: Path) -> None:
    """The positive case for the same check: a commit reachable from ANY
    remote-tracking ref in the owner is verifiably safe, so --allow-unpushed
    is not required at all."""
    main = _repo(tmp_path)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    _git(main, "remote", "add", "origin", str(remote))
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _git(wt, "push", "-q", "origin", "feature")
    _half_delete(wt)

    res = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main), "--allow-dirty"
    )

    assert res.returncode == 15, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists(), "verify-and-print removes nothing itself"
    _run_printed_rm(res.stdout)
    assert not wt.exists()


@requires_git
def test_normal_path_rejects_a_relative_trailing_newline_argument(tmp_path: Path) -> None:
    """Codex cross-model review (#1524, pass 3, HIGH): the relative-path
    normalization two lines below "Worktree path is required" - shared by
    BOTH removal paths, written long before this issue - silently strips a
    trailing newline from a RELATIVE argument via `basename` plus command
    substitution. A real worktree, never half-deleted, exercises the NORMAL
    path with exactly that hazard: a relative "wt" + a literal trailing
    newline must be refused before normalization ever runs, globally, not
    only inside --finish-partial-removal."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")

    # cwd is tmp_path (wt's own parent), so "wt" is the correct RELATIVE
    # spelling of a real, sibling-of-main worktree - not main's cwd, which
    # would resolve "wt" to a path that never existed in the first place.
    res = _run_remove(tmp_path, "wt" + "\n")

    assert res.returncode == 11, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists(), "a worktree the script never even identified must be untouched"


@requires_git
def test_finish_partial_removal_also_rejects_a_relative_trailing_newline_argument(
    tmp_path: Path,
) -> None:
    """Same guard, same global location, exercised through
    --finish-partial-removal's own entry point."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(
        tmp_path, "wt" + "\n", "--finish-partial-removal", "--owner-repo", str(main),
        "--allow-dirty", "--allow-unpushed",
    )

    assert res.returncode == 11, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists()


# ---------------------------------------------------------------------------
# Supplementary review (cnb-orch's own read plus an independent Gemini pass,
# after the pass-3 ceiling): five small fixes to the verify-and-print design
# itself, none of them a fourth cross-model review pass on the destructive
# logic (there is none left to review - this flag never deletes anything).
# ---------------------------------------------------------------------------


@requires_git
def test_normalization_failure_refuses_rather_than_substituting_root(
    tmp_path: Path,
) -> None:
    """Supplementary review finding: the relative-path resolution used to be
    one combined expression, `"$(cd "$(dirname ...)" 2>/dev/null && pwd)/$(basename ...)"`.
    When the `cd` fails (the argument's parent directory does not exist),
    that combined form silently substitutes an EMPTY string for the failed
    `cd`'s output, producing WORKTREE_PATH = "/<basename>" - an absolute,
    filesystem-ROOT path with no relation to the argument's real (missing)
    parent - and the script carried on as though that had been the intent.

    Confirmed directly against the pre-fix script (commit 6f5c20b0): given a
    real worktree at <tmp>/wt and the relative argument "missing/wt" (whose
    dirname "missing" does not exist), the old code computed WORKTREE_PATH
    "/wt", reported it as a missing worktree, searched for a nearby repo to
    prune, and exited 0 - "succeeding" at an operation that named no real
    path at all. The fix refuses instead (exit 1, naming the argument) the
    moment `cd` into the dirname fails."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")

    res = _run_remove(tmp_path, "missing/wt")

    assert res.returncode == 1, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "missing/wt" in res.stderr
    assert wt.exists(), "the real sibling worktree must be untouched by a refused argument"


@requires_git
def test_owner_repo_rejects_an_embedded_newline(tmp_path: Path) -> None:
    """Supplementary review finding: the global newline guard added for
    pass-3's HIGH only ever inspected WORKTREE_PATH. --owner-repo feeds its
    own `git -C "$OWNER_REPO" ...` calls exactly the same way, so a literal
    newline in IT was never rejected at all - only ever implicitly, and not
    reliably, by whatever happened to come after. Same guard, same exit code
    (11), now applied to --owner-repo too."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(
        main,
        str(wt),
        "--finish-partial-removal",
        "--owner-repo",
        str(main) + "\n",
        "--allow-dirty",
        "--allow-unpushed",
    )

    assert res.returncode == 11, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert wt.exists()


@requires_git
def test_finish_partial_removal_succeeds_with_exit_15_not_2(tmp_path: Path) -> None:
    """Supplementary review finding: a plain exit 2 is not distinct enough
    under `set -euo pipefail` - a failing `grep` or a bash builtin misuse
    anywhere else in this script can itself surface as exit 2, which a
    caller could misread as 'verified'. The success/print path now uses 15,
    an otherwise-unused code in this script's table."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main),
        "--allow-dirty", "--allow-unpushed",
    )

    assert res.returncode == 15, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "WORKTREE_REMOVE_FINISH_PARTIAL_VERIFIED" in res.stderr


@requires_git
def test_the_printed_prune_hint_is_a_comment_not_a_bare_sentence(
    tmp_path: Path,
) -> None:
    """Supplementary review finding: 'then review: git -C ... worktree
    prune --dry-run --verbose' is not valid shell on its own line - a human
    who copies BOTH printed lines into a shell at once (the rm line above
    it, plus this one) hits a syntax error on 'then'. Printed as a '#'
    comment, both lines can always be pasted together safely."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main),
        "--allow-dirty", "--allow-unpushed",
    )

    assert res.returncode == 15, f"stdout={res.stdout}\nstderr={res.stderr}"
    hint_lines = [line for line in res.stdout.splitlines() if "worktree prune" in line]
    assert len(hint_lines) == 1, res.stdout
    assert hint_lines[0].startswith("#"), (
        f"the prune hint must be a '#' comment, not a bare sentence: {hint_lines[0]!r}"
    )
    assert str(main) in hint_lines[0]


@requires_git
@requires_proc
def test_occupancy_unknown_prints_a_warning_on_stdout_above_the_rm_line(
    tmp_path: Path,
) -> None:
    """Supplementary review finding: an unreadable /proc already made this
    branch PROCEED (same fail-open behaviour as the normal path) and said so
    on stderr - but this branch's whole job is printing a command a human
    may paste and run without re-reading stderr at all. The same fact must
    also appear on stdout, directly above the printed `rm -rf`, where a
    skimming human cannot miss it."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)
    empty_proc = tmp_path / "empty-proc"
    empty_proc.mkdir()

    res = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main),
        "--allow-dirty", "--allow-unpushed",
        env={"WORKTREE_REMOVE_PROC_ROOT": str(empty_proc)},
    )

    assert res.returncode == 15, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert "WORKTREE_REMOVE_OCCUPANCY: unknown" in res.stderr
    stdout_lines = res.stdout.splitlines()
    warning_idx = next(
        (i for i, line in enumerate(stdout_lines) if "WARNING" in line and "live processes" in line),
        None,
    )
    rm_idx = next((i for i, line in enumerate(stdout_lines) if line.startswith("rm -rf")), None)
    assert warning_idx is not None, f"no stdout WARNING line found:\n{res.stdout}"
    assert rm_idx is not None, f"no printed rm line found:\n{res.stdout}"
    assert warning_idx < rm_idx, "the warning must appear ABOVE the rm line, not after it"
    assert stdout_lines[warning_idx].startswith("#")


# --------------------------------------------------------------------------- #
# Issue #1520: sticky-bit directories restrict unlink to the entry's owner,
# the directory's owner, or root - regardless of the directory's own rwx bits.
# This single-UID container cannot create a file owned by a different REAL
# uid, so the caller's own identity is shimmed instead: a fake `id` on PATH
# makes the script's internal `id -u` report a uid that differs from every
# real file's actual owner, which makes every real file "foreign" to the
# shimmed caller without needing a second real user on the host.
# --------------------------------------------------------------------------- #

requires_stat = pytest.mark.skipif(
    shutil.which("stat") is None, reason="requires GNU stat (owner-uid lookup)"
)


def _shim_id(tmp_path: Path, uid: str) -> dict[str, str]:
    """PATH-shimmed `id` reporting a fixed `id -u` value, so the pre-scan's
    notion of "the caller" can be set without a real second uid on this host."""
    bin_dir = tmp_path / "idbin"
    bin_dir.mkdir()
    real_id = shutil.which("id") or "/usr/bin/id"
    stub = bin_dir / "id"
    stub.write_text(
        "#!/bin/bash\n"
        f'if [[ "$1" == "-u" ]]; then echo {uid}; exit 0; fi\n'
        f'exec {real_id} "$@"\n'
    )
    stub.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    return env


def _make_sticky_dir(wt: Path, *, sticky: bool) -> Path:
    sdir = wt / "sticky"
    sdir.mkdir()
    (sdir / "file.txt").write_text("data\n")
    sdir.chmod(0o1777 if sticky else 0o777)
    return sdir


def _foreign_uid() -> str:
    """A uid guaranteed to differ from this process's real euid, so a
    `_shim_id` value never accidentally equals the real owner of a fixture's
    files (Codex review of #1520: a runner whose real euid happened to be
    1001 would make every "foreign" case below pass for the wrong reason -
    directory and file owners would match the "shimmed" caller because it
    would not be shimmed to anything different at all)."""
    real = os.geteuid() if hasattr(os, "geteuid") else -1
    return "1001" if real != 1001 else "1002"


@requires_git
@requires_non_root
@requires_stat
def test_prescan_refuses_a_sticky_dir_containing_a_foreign_owned_file(
    tmp_path: Path,
) -> None:
    """issue #1520: a sticky directory (mode +t) where the caller has full
    rwx can still contain a file the caller cannot actually unlink - POSIX
    restricts that to the file's own owner, the directory's owner, or root.
    The rwx-only pre-scan reports this tree "clear"; it must now refuse it
    (exit 9, naming the file) exactly like the rwx gap it is a sibling of.

    This is the committed red/green case for the gap: confirmed failing
    (reports clear, exit 0) against the pre-#1520 script at origin/main
    bf674917 before this fix - see the PR body for the recorded command and
    output, since this container cannot reproduce the real kernel refusal to
    make that a second automated case."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    sticky = _make_sticky_dir(wt, sticky=True)
    env = _shim_id(tmp_path, _foreign_uid())

    res = _run_remove(main, str(wt), "--force", "--allow-dirty", env=env)

    assert res.returncode == 9, (
        f"expected the pre-scan refusal (exit 9), got {res.returncode}\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert str(sticky / "file.txt") in res.stderr, res.stderr
    assert (wt / ".git").is_file()


@requires_git
@requires_non_root
@requires_stat
def test_prescan_ignores_sticky_bit_without_a_foreign_owner_mismatch(
    tmp_path: Path,
) -> None:
    """cnb-orch review of #1520: the same tree and the same shimmed-foreign
    caller, but WITHOUT the sticky bit, must stay clear - the caller's write
    bit on a non-sticky directory governs regardless of who owns the file
    inside it. This is what stops the fix from refusing every worktree that
    merely contains a file owned by someone else."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _make_sticky_dir(wt, sticky=False)
    env = _shim_id(tmp_path, _foreign_uid())

    res = _run_remove(main, str(wt), "--allow-dirty", env=env)

    assert res.returncode == 0, (
        f"a non-sticky directory must stay clear regardless of file owner:\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert not wt.exists()


@requires_git
@requires_non_root
@requires_stat
def test_prescan_ignores_a_sticky_dir_when_the_caller_owns_the_file(
    tmp_path: Path,
) -> None:
    """A sticky directory is not itself a refusal - only a sticky directory
    containing a FOREIGN-owned entry is. With no `id` shim, the script's real
    caller uid matches the real owner of every file this test creates, so the
    sticky directory must stay clear."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _make_sticky_dir(wt, sticky=True)

    res = _run_remove(main, str(wt), "--allow-dirty")

    assert res.returncode == 0, (
        f"a sticky dir the caller owns every file in must stay clear:\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert not wt.exists()


def _predicate(dir_owner: str, entry_owner: str, caller_uid: str) -> bool:
    """Call the SHIPPED sticky_dir_is_safe function directly (extracted by
    sourcing only that function out of scripts/worktree-remove.sh), rather
    than a parallel reimplementation - cnb-orch review of #1520: a test
    exercising a copy of the predicate stays green even when the real one is
    wrong. This covers the exemption branches a single-UID container cannot
    build with real differently-owned files: a sticky directory the CALLER
    owns (regardless of who owns the entry inside it), and root, which this
    container's test process is never run as."""
    extract = "sed -n '/^sticky_dir_is_safe() {/,/^}/p' " + str(SCRIPT)
    script = f"source <({extract}); sticky_dir_is_safe \"$1\" \"$2\" \"$3\""
    res = subprocess.run(
        ["bash", "-c", script, "--", dir_owner, entry_owner, caller_uid],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    return res.returncode == 0


@requires_git
def test_sticky_dir_is_safe_predicate() -> None:
    # Directory owner matches the caller: the directory owner may unlink
    # anything inside it, whoever owns the individual entry.
    assert _predicate(dir_owner="5000", entry_owner="6000", caller_uid="5000")
    # Entry owner matches the caller: the file's own owner may always unlink it.
    assert _predicate(dir_owner="5000", entry_owner="6000", caller_uid="6000")
    # Root (uid 0) may unlink anything, even when neither owner matches.
    assert _predicate(dir_owner="5000", entry_owner="6000", caller_uid="0")
    # Nobody matches: the sticky restriction applies.
    assert not _predicate(dir_owner="5000", entry_owner="6000", caller_uid="7000")


@requires_git
@requires_non_root
@requires_stat
def test_prescan_refuses_a_sticky_foreign_owned_parent(tmp_path: Path) -> None:
    """Codex review of #1520: the worktree ROOT's own parent is checked
    separately from the `find "$root" ...` walk (issue #1491, since `find`
    never walks above root), and that check was rwx-only. It must be
    sticky-aware too, exactly like every directory `find` does walk - a
    sticky parent the caller does not own can refuse removal of the
    worktree directory itself even where the caller has full rwx on the
    parent."""
    main = _repo(tmp_path)
    parent = tmp_path / "parent"
    parent.mkdir()
    parent.chmod(0o1777)
    wt = _add_worktree(main, parent / "wt", "feature")
    env = _shim_id(tmp_path, _foreign_uid())

    res = _run_remove(main, str(wt), "--force", "--allow-dirty", env=env)

    assert res.returncode == 9, (
        f"expected the pre-scan refusal (exit 9), got {res.returncode}\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert str(wt) in res.stderr, res.stderr
    assert (wt / ".git").is_file()


@requires_git
@requires_non_root
@requires_stat
def test_prescan_ignores_a_sticky_parent_the_caller_owns(tmp_path: Path) -> None:
    """A sticky parent is not itself a refusal - only one the caller does not
    own, that also does not own the worktree root. With no `id` shim, the
    caller's real uid owns both, so this must stay clear."""
    main = _repo(tmp_path)
    parent = tmp_path / "parent"
    parent.mkdir()
    parent.chmod(0o1777)
    wt = _add_worktree(main, parent / "wt", "feature")

    res = _run_remove(main, str(wt), "--allow-dirty")

    assert res.returncode == 0, (
        f"a sticky parent the caller owns must stay clear:\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert not wt.exists()
