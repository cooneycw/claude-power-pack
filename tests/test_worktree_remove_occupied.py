"""Regression tests for issue #888: worktree-remove.sh must not delete a
worktree that a live session is working in without a claim.

Root cause: the #597 cross-session claim protects a worktree only where a claim
was actually staked. ``flow-worktree-claim.sh check`` can report seven states,
but the removal script's ``case`` handled only ``held|foreign`` (hard stop) and
``self|stale`` (release and proceed). ``free``, ``unsupported`` and ``unknown``
fell through it silently - and ``free`` is simply what a worktree created
outside the /flow lane reports. The uncommitted-changes backstop below could not
catch the fall-through either, because it is skipped whenever ``--force`` is
passed, and ``/flow:auto`` Step 7 always passes ``--force``.

Observed on 2026-09-13: a session sitting in ``flow-finish-gate`` held a 21KB
staged file in a worktree reporting ``CLAIM=free``. The only thing between it and
deletion was the #503 mtime heuristic, whose 30-minute window that session had
already outlived by being in a long test run - so both guards read "clear" on a
checkout that was plainly occupied.

The fix: when no claim names this session, scan for live processes whose working
directory is inside the worktree. Occupied AND dirty is a hard stop (exit 5) that
``--force`` does not suppress; ``--steal`` still overrides. A host that cannot
scan reports ``unknown``, never ``clear``.
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

# Same constraint as test_worktree_remove_squash.py: the Woodpecker ``validate``
# step runs in a slim image with bash but no git.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

# The occupancy signal is /proc-based, so the behavioural tests are Linux-only.
# Skipping is honest here: on a host without /proc the guard genuinely does not
# fire, and test_cannot_scan_reports_unknown_not_clear pins that degradation.
requires_proc = pytest.mark.skipif(
    not Path("/proc/self/cwd").exists(),
    reason="occupancy detection reads /proc (Linux only)",
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


@pytest.fixture()
def occupant():
    """Spawn a real long-lived process whose cwd is a given directory.

    A real process is used rather than a synthetic /proc tree on purpose: a
    hand-built tree would only prove the matcher agrees with the author's idea of
    what /proc looks like.
    """
    procs: list[subprocess.Popen] = []

    def _spawn(cwd: Path) -> subprocess.Popen:
        p = subprocess.Popen(
            ["sleep", "60"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for the kernel to publish its cwd link before the scan runs.
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
def test_occupied_and_dirty_refused_despite_force(tmp_path: Path, occupant) -> None:
    """The core bug: --force must NOT delete a worktree in use with unsaved work."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    # Unsaved work of exactly the shape that was nearly lost: a staged new file.
    (wt / "spec.md").write_text("work that exists nowhere else\n")
    _git(wt, "add", "-A")
    occupant(wt)

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 5, (
        f"expected the #888 in-use refusal (exit 5), got {res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    assert wt.exists(), "worktree was removed out from under a live process"
    assert (wt / "spec.md").read_text() == "work that exists nowhere else\n"
    assert "WORKTREE_REMOVE_OCCUPANCY: occupied-dirty" in res.stderr
    # The report must name what it found, or the operator cannot act on it.
    assert "spec.md" in res.stderr


@requires_git
@requires_proc
def test_occupied_but_clean_is_still_removed(tmp_path: Path, occupant) -> None:
    """Occupancy alone does not block: with nothing unsaved, nothing is lost."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    occupant(wt)

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, f"clean occupied worktree should remove:\n{res.stderr}"
    assert not wt.exists()
    assert "WORKTREE_REMOVE_OCCUPANCY: occupied-clean" in res.stderr


@requires_git
@requires_proc
def test_idle_and_clean_still_removed_with_force(tmp_path: Path) -> None:
    """Regression guard for the normal /flow:auto Step 7 path.

    This is what #889's ``test_idle_and_dirty_still_removed_with_force`` was
    really protecting, and it is UNCHANGED: the tempting over-broad fix - refuse
    whenever no claim names us - would turn a rare data-loss bug into an everyday
    blocker, because ``free`` is what every worktree created outside the /flow
    lane reports, AND what a /flow worktree reports by the time the helper runs,
    since both callers release the claim first (auto.md, merge.md).

    #899 did not take that fix. Claim state still never causes a refusal on its
    own. What changed is narrower - see the test below - and the ordinary path is
    unaffected because a post-merge worktree is CLEAN: measured on three
    worktrees that had each run the full suite and built a .venv, `status
    --porcelain` reported zero while `--ignored` reported fifteen.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, (
        f"an idle clean worktree must still be removable with --force:\n{res.stderr}"
    )
    assert not wt.exists()
    assert "WORKTREE_REMOVE_OCCUPANCY: clear" in res.stderr


@requires_git
def test_idle_and_dirty_is_refused_despite_force(tmp_path: Path) -> None:
    """#899: --force no longer deletes uncommitted work on an idle worktree.

    This inverts #889's assertion, deliberately and with its reasoning kept.
    #889 read "idle" as sufficient licence; #899's trace showed that "idle" is
    the NORMAL state of an agent session between tool calls, which has no process
    running while its worktree may hold hours of work. #888's observed case was a
    STAGED 21KB spec file, and the occupancy guard reaches that only while a
    process is live.

    `--force` and "the contents are expendable" were the same flag until now.
    They are two different assertions: --force says git must remove a busy
    worktree, --allow-dirty says the work in it is not wanted.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "leftover.txt").write_text("uncommitted but nobody is here\n")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 6, f"--force must not destroy this:\n{res.stderr}"
    assert wt.exists(), "the worktree must survive a refusal"
    assert (wt / "leftover.txt").exists(), "the work must survive a refusal"
    assert "WORKTREE_REMOVE_DIRTY: refused" in res.stderr

    allowed = _run_remove(
        main, str(wt), "--force", "--delete-branch", "--allow-dirty"
    )
    assert allowed.returncode == 0, f"--allow-dirty must work:\n{allowed.stderr}"
    assert not wt.exists()


@requires_git
@requires_proc
def test_sibling_worktree_sharing_a_path_prefix_is_not_occupancy(
    tmp_path: Path, occupant
) -> None:
    """A finding must tell this worktree from its neighbour.

    ``<wt>-2`` starts with ``<wt>``, so a bare prefix test reports the neighbour's
    processes as occupying this one. That is not hypothetical: on the host where
    #888 was found, ``kyle-issue-1142`` is a real prefix of
    ``kyle-issue-1142-container-spec-superseded``.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    sibling = _add_worktree(main, tmp_path / "wt-2", "feature-2")
    (wt / "leftover.txt").write_text("dirty, but nobody is in THIS worktree\n")
    occupant(sibling)  # live process in the NEIGHBOUR only

    # --allow-dirty because the leftover file above is SCAFFOLDING for the
    # occupancy scenario, not this test's subject: #899 made a dirty worktree a
    # refusal in its own right, so without it this would stop on that instead of
    # exercising the prefix matching it exists for.
    res = _run_remove(main, str(wt), "--force", "--delete-branch", "--allow-dirty")

    assert res.returncode == 0, (
        "the neighbour's process was mistaken for occupancy of this worktree "
        f"(path-prefix false positive):\n{res.stderr}"
    )
    assert not wt.exists()
    assert sibling.exists(), "the neighbour must be untouched"
    assert "WORKTREE_REMOVE_OCCUPANCY: clear" in res.stderr


@requires_git
@requires_proc
def test_steal_overrides_the_occupancy_refusal(tmp_path: Path, occupant) -> None:
    """--steal stays the deliberate override, as it is for a #597 claim."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "spec.md").write_text("work\n")
    _git(wt, "add", "-A")
    occupant(wt)

    # #899 CHANGED THIS, deliberately. --steal overrides the OCCUPANCY refusal -
    # it asserts those processes can be killed - and that is all it ever meant.
    # It does not assert the worktree's CONTENTS are expendable, which is a
    # separate claim needing its own flag. Before #899 one --steal silenced both,
    # so a session certain about the processes was also, silently, authorising
    # the loss of the work.
    refused = _run_remove(main, str(wt), "--force", "--delete-branch", "--steal")
    assert refused.returncode == 6, (
        "--steal must no longer silence the uncommitted-work refusal on its own "
        f"(issue #899):\n{refused.stderr}"
    )

    res = _run_remove(
        main, str(wt), "--force", "--delete-branch", "--steal", "--allow-dirty"
    )

    assert res.returncode == 0, f"--steal must override the #888 stop:\n{res.stderr}"
    assert not wt.exists()


@requires_git
def test_cannot_scan_reports_unknown_not_clear(tmp_path: Path) -> None:
    """An unscanned host must read as unknown, never as clean.

    A guard that cannot look, but prints a clean result, is worse than no guard:
    it manufactures the reassurance that stopped anyone checking. Pointed at a
    proc tree with nothing in it, the scan must say so.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "leftover.txt").write_text("dirty\n")
    empty_proc = tmp_path / "empty-proc"
    empty_proc.mkdir()

    # --allow-dirty: the leftover file is scaffolding for the unscannable-host
    # scenario, and #899's dirty refusal would otherwise pre-empt the occupancy
    # reporting this test is about.
    res = _run_remove(
        main,
        str(wt),
        "--force",
        "--delete-branch",
        "--allow-dirty",
        env={"WORKTREE_REMOVE_PROC_ROOT": str(empty_proc)},
    )

    assert "WORKTREE_REMOVE_OCCUPANCY: unknown" in res.stderr, (
        f"an unscannable host must report unknown:\n{res.stderr}"
    )
    assert "WORKTREE_REMOVE_OCCUPANCY: clear" not in res.stderr
    # Fail-open by design: it degrades to the pre-#888 behaviour, loudly.
    assert res.returncode == 0


# ---------------------------------------------------------------------------
# Issue #899: unpushed commits.
#
# The helper never looked at commits at all. `git status --porcelain` reports
# CLEAN for a tree whose commits were never pushed, so the occupancy guard saw
# occupied-clean and proceeded; with --delete-branch the ref went too and the
# commits survived only via `git fsck --lost-found` until gc.
#
# These need a real remote, because the whole difficulty is telling "these
# commits are on no remote" from "this repo has no remotes" and from "the remote
# branch was pruned after a merge" - three states a single boolean flattens.
# ---------------------------------------------------------------------------


def _repo_with_remote(tmp_path: Path) -> Path:
    """A clone with a real origin, so `--not --remotes` has something to answer."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    main = tmp_path / "main"
    _git(tmp_path, "clone", "-q", str(origin), str(main))
    _git(main, "config", "user.email", "t@example.com")
    _git(main, "config", "user.name", "t")
    (main / "base.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    # Cloning an EMPTY bare repo leaves the branch name to the local default, so
    # name it explicitly rather than assuming; otherwise a later `push origin
    # main` has no local `main` to push.
    _git(main, "branch", "-M", "main")
    _git(main, "push", "-q", "-u", "origin", "main")
    _git(main, "fetch", "-q")
    return main


@requires_git
def test_unpushed_commits_are_refused_despite_force(tmp_path: Path) -> None:
    """The data-loss case: commits that exist on no remote ref.

    Clean tree, no live process, so every guard that existed before #899 reports
    fine and the removal proceeds - taking the branch ref with it under
    --delete-branch.
    """
    main = _repo_with_remote(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "work.txt").write_text("committed, never pushed\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "the only copy")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 7, f"unpushed work must not be destroyed:\n{res.stderr}"
    assert wt.exists()
    assert "WORKTREE_REMOVE_UNPUSHED: refused" in res.stderr
    assert "WORKTREE_REMOVE_DIRTY: clean" in res.stderr, (
        "the tree IS clean - which is exactly why status --porcelain could not "
        "see this and why the check had to be separate"
    )

    allowed = _run_remove(
        main, str(wt), "--force", "--delete-branch", "--allow-unpushed"
    )
    assert allowed.returncode == 0, allowed.stderr
    assert not wt.exists()


@requires_git
def test_a_merged_branch_whose_remote_ref_was_pruned_is_not_refused(
    tmp_path: Path,
) -> None:
    """THE regression guard, and the reason `@{u}..` could not be the instrument.

    This is the ORDINARY path: `gh pr merge --delete-branch` removes the remote
    branch, so `git fetch --prune` drops refs/remotes/origin/<branch> and the
    branch has no upstream at all. Measured, `git log @{u}..` fails here with
    "fatal: no upstream configured" - the SAME failure it gives for genuinely
    unpushed work - so anything built on it must refuse both and break every
    ordinary removal, or allow both and close nothing.

    `HEAD --not --remotes` asks the question that actually matters: the commits
    are reachable from origin/main, so there is nothing to lose, whatever
    happened to the branch ref.
    """
    main = _repo_with_remote(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "work.txt").write_text("work\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "the work")
    _git(wt, "push", "-q", "origin", "feature")
    # merge it into main and delete the remote branch, as gh pr merge would
    _git(main, "merge", "-q", "--no-ff", "feature", "-m", "merged")
    _git(main, "push", "-q", "origin", "main")
    _git(main, "push", "-q", "origin", "--delete", "feature")
    _git(main, "fetch", "-q", "--prune")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, (
        f"a merged branch must not be mistaken for unpushed work:\n{res.stderr}"
    )
    assert "WORKTREE_REMOVE_UNPUSHED: pushed" in res.stderr
    assert not wt.exists()


@requires_git
def test_a_repo_with_no_remotes_reads_unknown_not_unpushed(tmp_path: Path) -> None:
    """"No remotes configured" and "on no remote" are different facts.

    `HEAD --not --remotes` reports EVERY commit in a repo that has no remote
    refs, because there is no remote for anything to be on. Reading that as
    unpushed would refuse every removal in any local-only repo - including every
    other fixture in this file - which is the membership-floor mistake in its
    most expensive form: a guard that fires everywhere gets removed.
    """
    main = _repo(tmp_path)  # plain `git init`, no origin
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "work.txt").write_text("local\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "local only")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, f"a local-only repo must still work:\n{res.stderr}"
    assert "WORKTREE_REMOVE_UNPUSHED: unknown" in res.stderr
    assert "WORKTREE_REMOVE_UNPUSHED: refused" not in res.stderr


@requires_git
def test_each_override_silences_only_its_own_refusal(tmp_path: Path) -> None:
    """Three refusals, three flags, and no flag reaches past its own.

    The property the issue is really about: safety that one flag can switch off
    is one flag away from no safety. A worktree that is BOTH dirty and unpushed
    must refuse twice, and each override must leave the other standing.
    """
    main = _repo_with_remote(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "committed.txt").write_text("committed, never pushed\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "unpushed")
    (wt / "uncommitted.txt").write_text("not committed either\n")

    dirty_first = _run_remove(main, str(wt), "--force", "--delete-branch")
    assert dirty_first.returncode == 6, dirty_first.stderr

    still_unpushed = _run_remove(
        main, str(wt), "--force", "--delete-branch", "--allow-dirty"
    )
    assert still_unpushed.returncode == 7, (
        "--allow-dirty must not also silence the unpushed refusal:\n"
        f"{still_unpushed.stderr}"
    )

    still_dirty = _run_remove(
        main, str(wt), "--force", "--delete-branch", "--allow-unpushed"
    )
    assert still_dirty.returncode == 6, (
        "--allow-unpushed must not also silence the dirty refusal:\n"
        f"{still_dirty.stderr}"
    )

    both = _run_remove(
        main,
        str(wt),
        "--force",
        "--delete-branch",
        "--allow-dirty",
        "--allow-unpushed",
    )
    assert both.returncode == 0, both.stderr
    assert not wt.exists()


# ---------------------------------------------------------------------------
# Issue #916: a SQUASH-merged branch read as unpushed once its ref was pruned.
#
# #905's check asks `git log HEAD --not --remotes`. A squash rewrites the
# branch onto main under a different sha, so its commits are ancestors of
# NOTHING and the verdict rests entirely on `refs/remotes/origin/<branch>`
# surviving - which `gh-pr-merge.sh` deletes on the ordinary path. This
# repository squash-merges exclusively, so every merged worktree read as
# holding unreachable commits and #887's sweep removed nothing.
#
# WHY #905's OWN REGRESSION GUARD MISSED IT, and it is the reason these
# fixtures squash: `test_a_merged_branch_whose_remote_ref_was_pruned_is_not_
# refused` builds the merge with `git merge --no-ff`. Under --no-ff the branch
# commits ARE ancestors of origin/main and the check reads empty. Right
# property, wrong merge strategy, in a repo that never uses that strategy - a
# guard that passes on a case which cannot occur here.
# ---------------------------------------------------------------------------


def _squash_merged(tmp_path: Path, *, record: bool) -> tuple[Path, Path]:
    """Reproduce `gh pr merge --squash --delete-branch` exactly.

    `record` writes the `branch.<name>.cpp-merged-head` entry that
    `gh-pr-merge.sh` writes inside its MERGED block, before the delete. Passing
    False is the branch merged some OTHER way - a web-UI squash - which no
    helper recorded.
    """
    main = _repo_with_remote(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "issue-1")
    (wt / "work.txt").write_text("the work\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "the work")
    _git(wt, "push", "-q", "-u", "origin", "issue-1")
    oid = _git(wt, "rev-parse", "HEAD").strip()
    # SQUASH, not --no-ff: the commits land on main under a different sha.
    _git(main, "merge", "-q", "--squash", "issue-1")
    _git(main, "commit", "-qm", "the work (#1)")
    _git(main, "push", "-q", "origin", "main")
    if record:
        _git(main, "config", "branch.issue-1.cpp-merged-head", oid)
    _git(main, "push", "-q", "origin", "--delete", "issue-1")
    return main, wt


@requires_git
def test_a_squash_merged_branch_with_the_merge_record_is_removed(
    tmp_path: Path,
) -> None:
    """The #916 defect, fixed: the record says this exact commit landed."""
    main, wt = _squash_merged(tmp_path, record=True)

    # Precondition, or this could pass for the wrong reason.
    assert _git(wt, "log", "--oneline", "HEAD", "--not", "--remotes").strip(), (
        "precondition: the commits must be on no remote ref, which is the "
        "state that used to be refused"
    )

    res = _run_remove(main, str(wt), "--delete-branch")
    assert res.returncode == 0, f"a landed branch must be removable:\n{res.stderr}"
    assert "WORKTREE_REMOVE_UNPUSHED: landed" in res.stderr
    assert not wt.exists()


@requires_git
def test_a_squash_merged_branch_without_a_record_is_still_refused(
    tmp_path: Path,
) -> None:
    """The residual, asserted rather than hidden.

    A branch squash-merged some other way - the web UI, another tool - and later
    pruned has no record, and is indistinguishable offline from work that was
    never pushed. It stays refused, which is the safe direction, and the message
    must point at the missing record rather than claim the commits are lost.

    This is also why the fix is future-only: nothing can retroactively record a
    merge that already happened without asking the network which merges happened.
    """
    main, wt = _squash_merged(tmp_path, record=False)

    res = _run_remove(main, str(wt), "--delete-branch")
    assert res.returncode == 7, res.stderr
    assert "WORKTREE_REMOVE_UNPUSHED: refused" in res.stderr
    assert wt.exists()


@requires_git
def test_a_record_that_does_not_match_head_is_refused(tmp_path: Path) -> None:
    """The OID keying, which is what actually makes a stale record harmless.

    The issue states the safety as "`git branch -D` removes the section, so the
    record cannot outlive the ref". MEASURED, that is only true of `branch -D`:
    `git update-ref -d refs/heads/<name>` deletes the branch and LEAVES the
    record. So records CAN survive their branch, and the cleanup is not the
    guarantee.

    The guarantee is that the reader accepts the record ONLY when it equals HEAD
    exactly. A surviving record names an OID that genuinely landed, so a match
    means the claim is true; anything else is refused. Here the branch has moved
    on to new, unpushed work and must be protected.
    """
    main = _repo_with_remote(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "issue-2")
    (wt / "a.txt").write_text("landed work\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "landed")
    landed = _git(wt, "rev-parse", "HEAD").strip()
    _git(main, "config", "branch.issue-2.cpp-merged-head", landed)
    # the branch moves on: this commit is NOT the one that landed
    (wt / "b.txt").write_text("new work nobody has\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "new unpushed work")

    res = _run_remove(main, str(wt), "--delete-branch")
    assert res.returncode == 7, (
        f"a record naming a DIFFERENT commit must not license removal:\n{res.stderr}"
    )
    assert "WORKTREE_REMOVE_UNPUSHED: refused" in res.stderr
    assert wt.exists(), "the new work must survive"


# ---------------------------------------------------------------------------
# Issue #916: a skipped check must not print what a passed check prints.
# ---------------------------------------------------------------------------


@requires_git
def test_the_dirty_marker_says_overridden_when_the_check_was_skipped(
    tmp_path: Path,
) -> None:
    """`--allow-dirty` used to print `WORKTREE_REMOVE_DIRTY: clean`.

    The echo sat outside the guard, so a tree holding uncommitted work announced
    `clean` - and it was never measured. Our own membership floor, in our own
    output: never-checked and checked-and-empty are different facts.
    """
    main = _repo_with_remote(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "issue-3")
    (wt / "uncommitted.txt").write_text("not committed\n")

    # BOTH flags, and the pairing is the #899 separation working rather than an
    # inconvenience: `--allow-dirty` says the CONTENTS are expendable, while
    # `--force` is what `git worktree remove` itself requires to remove a tree
    # holding modified files. Neither implies the other, which is the whole
    # point of splitting them.
    res = _run_remove(
        main, str(wt), "--force", "--allow-dirty", "--allow-unpushed", "--delete-branch"
    )
    assert res.returncode == 0, res.stderr
    assert "WORKTREE_REMOVE_DIRTY: overridden" in res.stderr
    assert "WORKTREE_REMOVE_DIRTY: clean" not in res.stderr, (
        "the tree was NOT measured clean - it held uncommitted work"
    )


@requires_git
def test_the_unpushed_marker_says_overridden_rather_than_nothing(
    tmp_path: Path,
) -> None:
    """`--allow-unpushed` used to emit NO marker at all.

    Silence is not a verdict. A consumer parsing this output could not tell an
    overridden check from a helper too old to have one - which is precisely the
    pre-#899 copy every container on this host is currently running.
    """
    main = _repo_with_remote(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "issue-4")
    (wt / "a.txt").write_text("committed, never pushed\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "unpushed")

    res = _run_remove(main, str(wt), "--allow-unpushed", "--delete-branch")
    assert res.returncode == 0, res.stderr
    assert "WORKTREE_REMOVE_UNPUSHED: overridden" in res.stderr
