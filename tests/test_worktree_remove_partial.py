"""Regression tests for Nit Store #864 (comments 5983011277, 6155393127):
worktree-remove.sh's half-deleted-worktree and --allow-dirty-without-force gaps.

Root cause 1 (undeletable path): `git worktree remove` can report SUCCESS while
a path survives it - observed here with a parent directory that lacks write
permission, so git cannot unlink the entry inside it. When that happens mid-run,
`git worktree remove` has ALREADY deleted the worktree's own `.git` file, so a
retry hits "not a git worktree" with no path forward but a manual `rm -rf`. The
fix is two-sided: a pre-scan refuses before deleting anything the first time
(exit 9, naming the path), and `--finish-partial-removal` is the explicit,
named recovery for a tree already left in that state.

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


def _repo_at(main: Path) -> Path:
    main.mkdir(parents=True, exist_ok=True)
    _git(main, "init", "-q", "-b", "main")
    (main / "base.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    return main


def _repo(tmp_path: Path) -> Path:
    return _repo_at(tmp_path / "main")


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


@requires_git
@requires_non_root
def test_finish_partial_removal_completes_a_half_deleted_worktree(
    tmp_path: Path,
) -> None:
    """A worktree already left half-deleted (no `.git` file, an undeletable
    leftover) by a PRIOR `git worktree remove --force` must be completable by
    this helper, without the plain re-run and without a manual `rm -rf`."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    locked = _make_locked_dir(wt)
    try:
        # Produce the real half-deleted state the same way git does: a forced
        # removal that cannot unlink the locked path.
        forced = subprocess.run(
            ["git", "-C", str(main), "worktree", "remove", "--force", str(wt)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert forced.returncode != 0, "setup must leave a half-deleted worktree"
        assert not (wt / ".git").exists()
        assert (locked / "file.txt").is_file()

        # A plain re-run must still refuse, naming the recovery flag.
        plain = _run_remove(main, str(wt))
        assert plain.returncode == 1, plain.stderr
        assert "--finish-partial-removal" in plain.stderr

        # With the flag but the path still undeletable: refuse, naming it.
        blocked = _run_remove(main, str(wt), "--finish-partial-removal")
        assert blocked.returncode == 9, blocked.stderr
        assert str(locked) in blocked.stderr

        # Fix the permission and retry: the helper finishes the job itself.
        locked.chmod(0o755)
        done = _run_remove(main, str(wt), "--finish-partial-removal")
        assert done.returncode == 0, (
            f"stdout={done.stdout}\nstderr={done.stderr}"
        )
        assert not wt.exists()
    finally:
        _unlock(locked)


@requires_git
def test_finish_partial_removal_refuses_when_git_still_lists_it(
    tmp_path: Path,
) -> None:
    """A `.git` file missing for some OTHER reason, while git still has the
    worktree registered, is a different and more dangerous case than the
    silent-partial-failure this flag exists for - it must stay refused rather
    than having its still-tracked content rm -rf'd."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / ".git").unlink()

    assert "feature" in _git(main, "worktree", "list")

    res = _run_remove(main, str(wt), "--finish-partial-removal")

    assert res.returncode == 1, res.stderr
    assert "still lists this as a live worktree" in res.stderr
    assert wt.exists()
    assert "feature" in _git(main, "worktree", "list")


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
def test_finish_partial_removal_checks_every_candidate_repo_not_just_the_first(
    tmp_path: Path,
) -> None:
    """Codex review of #1491: a neighbouring repo that happens to sort before
    the TRUE owner must not be read as proof nobody owns this worktree.

    `a-repo` sorts alphabetically before `main`, which is the worktree's real
    owner and still has it registered. The old single-candidate check asked
    only `a-repo` (truthfully: no), read that as "not registered anywhere",
    and would have rm -rf'd a worktree `main` still lists as live.
    """
    a_repo = tmp_path / "a-repo"
    a_repo.mkdir()
    _git(a_repo, "init", "-q", "-b", "main")
    (a_repo / "base.txt").write_text("base\n")
    _git(a_repo, "add", "-A")
    _git(a_repo, "commit", "-qm", "base")

    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / ".git").unlink()

    assert tmp_path / "a-repo" < wt, "a-repo must sort before the target for this case to be meaningful"

    res = _run_remove(main, str(wt), "--finish-partial-removal")

    assert res.returncode == 1, res.stderr
    assert "still lists this as a live worktree" in res.stderr
    assert wt.exists()
    assert "feature" in _git(main, "worktree", "list")


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


def _force_half_delete(main: Path, wt: Path) -> Path:
    """Produce a REAL half-deleted worktree the way git itself does: a forced
    removal that cannot unlink a locked subdirectory. Returns the locked dir
    (still 0555) for the caller to `chmod(0o755)` once done."""
    locked = _make_locked_dir(wt)
    forced = subprocess.run(
        ["git", "-C", str(main), "worktree", "remove", "--force", str(wt)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert forced.returncode != 0, "setup must leave a half-deleted worktree"
    assert not (wt / ".git").exists()
    return locked


@requires_git
@requires_non_root
@requires_proc
def test_finish_partial_removal_checks_occupancy_before_deleting(
    tmp_path: Path, occupant
) -> None:
    """Codex review (pass 2) of #1491: the recovery path used to `exit` long
    before the script's #888 live-occupancy check was ever reached, so a live
    process sitting in a half-deleted worktree was never protected - unlike
    every other removal path in this script."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    locked = _force_half_delete(main, wt)
    locked.chmod(0o755)
    occupant(wt)

    res = _run_remove(main, str(wt), "--finish-partial-removal")

    assert res.returncode == 5, (
        f"expected the #888 occupancy refusal (exit 5), got {res.returncode}\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    assert wt.exists()


@requires_git
def test_finish_partial_removal_refuses_an_unresolvable_owner(
    tmp_path: Path,
) -> None:
    """Codex review (pass 2) of #1491: an EMPTY candidate-repo set used to be
    read as "nothing owns this" and the recovery proceeded. A worktree at an
    arbitrary path (neither a sibling nor a descendant of its owner) has no
    discoverable candidate at all, so this must refuse rather than guess -
    and --owner-repo must let the caller name the real one."""
    repos = tmp_path / "repos"
    repos.mkdir()
    main = _repo_at(repos / "main")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    wt = _add_worktree(main, scratch / "wt", "feature")
    (wt / ".git").unlink()

    no_owner = _run_remove(main, str(wt), "--finish-partial-removal")
    assert no_owner.returncode == 1, no_owner.stderr
    assert "--owner-repo" in no_owner.stderr
    assert wt.exists()

    named_owner = _run_remove(
        main, str(wt), "--finish-partial-removal", "--owner-repo", str(main)
    )
    assert named_owner.returncode == 1, named_owner.stderr
    assert "still lists this as a live worktree" in named_owner.stderr
    assert wt.exists()


@requires_git
def test_finish_partial_removal_refuses_a_registered_path_containing_a_newline(
    tmp_path: Path,
) -> None:
    """Codex review (pass 2) of #1491: switched the registration-matching read
    from the OLD line-based `sed -n 's/^worktree //p'` parse of plain
    `git worktree list --porcelain` to NUL-delimited `-z` output, since a path
    containing an embedded newline is itself a record delimiter the old parser
    relied on - measured directly, this host's git 2.43.0 neither quotes nor
    escapes it, so the old parse genuinely split the "worktree <path>" line in
    two.

    This pins the FIXED behavior (refuses correctly); it is NOT a
    discriminating red/green case for the old parser. A tab does not
    reproduce the claimed defect at all (measured: this git's plain porcelain
    neither quotes nor splits a tab). An embedded newline DOES split the old
    parser's line-based read, but the resulting truncated prefix then
    coincidentally reappears as one of grep's own split alternatives when
    `$WT_RESOLVED` - itself containing the same embedded newline - is passed
    to `grep -F` as a single multi-line pattern argument (GNU grep treats each
    line of a multi-line `-F` pattern as a separate alternative), so the old
    code still happened to refuse correctly on this exact input. The `-z`
    parse is applied anyway as the structurally correct fix - a NUL byte
    cannot appear in a path at all, so no delimiter collision is possible -
    but no input was found that makes the OLD code visibly wrong here."""
    main = _repo(tmp_path)
    wt_dir = tmp_path / "w\nt"
    wt = _add_worktree(main, wt_dir, "feature")
    (wt / ".git").unlink()

    assert "feature" in _git(main, "worktree", "list")

    res = _run_remove(main, str(wt), "--finish-partial-removal")

    assert res.returncode == 1, res.stderr
    assert "still lists this as a live worktree" in res.stderr
    assert wt.exists()
    assert "feature" in _git(main, "worktree", "list")
