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


def _run_remove(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
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

    res2 = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(main))

    assert res2.returncode == 0, f"stdout={res2.stdout}\nstderr={res2.stderr}"
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

    res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(main))

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
        res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(main))

        assert res.returncode == 9, f"stdout={res.stdout}\nstderr={res.stderr}"
        assert str(locked) in res.stderr
        assert wt.exists()
    finally:
        _unlock(locked)


@requires_git
def test_finish_partial_removal_succeeds_with_the_true_owner(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)

    res = _run_remove(main, str(wt), "--finish-partial-removal", "--owner-repo", str(main))

    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert not wt.exists()
    # The admin registration is actually pruned, not just the directory removed.
    assert "feature" not in _git(main, "worktree", "list")


@requires_git
def test_a_symlink_to_the_worktree_is_left_dangling_not_deleted(tmp_path: Path) -> None:
    """Owner ruling (#1524): rm -rf on a symlink TO the worktree removes only
    the link, leaving the real directory behind as an orphan once `worktree
    prune` drops the registration - the opposite hazard from the one this
    flag exists to fix. The fix resolves the input via realpath ONCE, early,
    and removes THAT, never the caller's own symlink - which is not part of
    the worktree and may live anywhere (a different repo, a home directory).
    The symlink is left dangling and named so the caller can clean it up."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    _half_delete(wt)
    link = tmp_path / "wt-link"
    link.symlink_to(wt)

    res = _run_remove(main, str(link), "--finish-partial-removal", "--owner-repo", str(main))

    assert res.returncode == 0, f"stdout={res.stdout}\nstderr={res.stderr}"
    assert not wt.exists(), "the real worktree directory must be gone"
    assert "feature" not in _git(main, "worktree", "list")
    # The symlink itself survives, now dangling - never deleted, and named.
    assert link.is_symlink(), "the caller's own symlink must not be deleted"
    assert not link.exists(), "but it is now dangling, since its target is gone"
    assert str(link) in res.stderr and "dangling" in res.stderr
