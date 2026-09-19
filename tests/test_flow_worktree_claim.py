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
    """A helper the flow lane calls must ship in the host and Codex surfaces."""
    installer = (ROOT / "scripts" / "flow-helpers-install.sh").read_text()
    assert "flow-worktree-claim.sh" in installer

    bundled = ROOT / "codex" / "skills" / "flow-auto" / "scripts" / "flow-worktree-claim.sh"
    assert bundled.read_text() == (ROOT / "scripts" / "flow-worktree-claim.sh").read_text()

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


# --- Process identity, not process existence (issue #1032) -------------------
#
# `kill -0 <pid>` answers "some process has this number". Linux recycles pids -
# on a busy host the space wraps in hours - so a claim read that way reports a
# long-dead session as LIVE. That is the unsafe direction here: it is the
# reading that BLOCKS recovery, leaving the worktree removable only via
# --steal, which is supposed to mean "I am overriding a genuinely live owner".
#
# Confirmed RED against the pre-fix helper (`git show <base>:` - never
# `git stash`, issue #1056): a claim whose pid exists with a non-matching
# start-time read `held`. It now reads `stale`.
#
# The witness is written into the claim as `start=`, field 22 of
# /proc/<pid>/stat. FLOW_CLAIM_PROC_ROOT is the test seam for it - it exists so
# BOTH lanes, readable and unreadable, are reachable on a host whose /proc
# works, which is every host this suite runs on.

MATCHING_START = "111111"
RECYCLED_START = "999999"


def _fake_proc(root: Path, pid: str, start: str) -> Path:
    """A /proc stand-in holding one process with a chosen start-time.

    The comm field deliberately contains a space and a parenthesis - the one
    field a process controls, and the reason field 22 cannot be reached by
    splitting the line on whitespace.
    """
    d = root / pid
    d.mkdir(parents=True, exist_ok=True)
    fields = ["0"] * 20
    # Field 22 of the line is field 20 of what remains after the comm, and the
    # remainder's first field is the state - so the start-time is fields[18].
    # Verified against a real process on this host whose comm contains spaces
    # ("npm exec tavily"): there `awk '{print $22}'` yields 11 while this
    # extraction yields the true start-time, which is the whole reason the
    # script consumes through the last ') ' instead of splitting the line.
    fields[18] = start
    (d / "stat").write_text(f"{pid} (odd )name) S " + " ".join(fields) + "\n")
    return root


def _lock_with(main: Path, wt: Path, *, pid: str, start: str | None, age_s: int = 0) -> None:
    """Write a claim reason directly, so a specific witness/age can be posed."""
    import time as _time

    ts = int(_time.time()) - age_s
    reason = (
        f"flow-claim issue=42 pid={pid} session={OTHER_SESSION} "
        f"host=testhost ts={ts}"
    )
    if start is not None:
        reason += f" start={start}"
    _git(main, "worktree", "unlock", str(wt))
    _git(main, "worktree", "lock", "--reason", reason, str(wt))


def _check_witness(
    wt: Path, proc_root: Path, *, live: str = OTHER_PID, max_age_hours: str = "24"
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_PID": SELF_PID,
            "CLAUDE_CODE_SESSION_ID": SELF_SESSION,
            "FLOW_CLAIM_HOST": "testhost",
            "FLOW_CLAIM_LIVE_PIDS": live,
            "FLOW_CLAIM_PROC_ROOT": str(proc_root),
            "FLOW_CLAIM_MAX_AGE_HOURS": max_age_hours,
        }
    )
    return subprocess.run(
        ["bash", str(CLAIM), "check", str(wt)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@requires_git
def test_claim_records_a_start_time_witness(repo: tuple[Path, Path]) -> None:
    """The claim carries the field the whole fix depends on."""
    main, wt = repo
    _run(CLAIM, "claim", str(wt), "--issue", "42")

    porcelain = _git(main, "worktree", "list", "--porcelain").stdout
    locked = [ln for ln in porcelain.splitlines() if ln.startswith("locked flow-claim")]
    assert locked, porcelain
    assert " start=" in locked[0], locked[0]


@requires_git
def test_a_recycled_pid_reads_stale_not_held(tmp_path: Path, repo: tuple[Path, Path]) -> None:
    """RED: the pid exists, but it is a different process now."""
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-recycled", OTHER_PID, RECYCLED_START)
    _lock_with(main, wt, pid=OTHER_PID, start=MATCHING_START)

    res = _check_witness(wt, proc)

    assert _field(res, "OWNER_WITNESS") == "mismatched", res.stdout
    assert _verdict(res) == "stale", res.stdout


@requires_git
def test_a_matching_witness_is_still_held(tmp_path: Path, repo: tuple[Path, Path]) -> None:
    """GREEN: a genuinely live owner must still refuse.

    Without this half, the demotion above is indistinguishable from a helper
    that calls every claim stale - which would be worse than the bug, because
    it fails toward deleting live sessions' work.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-live", OTHER_PID, MATCHING_START)
    _lock_with(main, wt, pid=OTHER_PID, start=MATCHING_START)

    res = _check_witness(wt, proc)

    assert _field(res, "OWNER_WITNESS") == "matched", res.stdout
    assert _verdict(res) == "held", res.stdout


@requires_git
def test_a_recycled_pid_is_taken_over_without_steal(
    tmp_path: Path, repo: tuple[Path, Path]
) -> None:
    """The consequence that matters: recovery no longer needs the override.

    Before #1032 this claim was reclaimable only via --steal, collapsing the
    safe path and the deliberate override into one flag.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-recycled", OTHER_PID, RECYCLED_START)
    _lock_with(main, wt, pid=OTHER_PID, start=MATCHING_START)

    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_PID": SELF_PID,
            "CLAUDE_CODE_SESSION_ID": SELF_SESSION,
            "FLOW_CLAIM_HOST": "testhost",
            "FLOW_CLAIM_LIVE_PIDS": OTHER_PID,
            "FLOW_CLAIM_PROC_ROOT": str(proc),
        }
    )
    taken = subprocess.run(
        ["bash", str(CLAIM), "claim", str(wt), "--issue", "42"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert taken.returncode == 0, taken.stdout + taken.stderr
    assert _verdict(taken) == "self", taken.stdout
    assert "recycled" in taken.stderr, taken.stderr


@requires_git
def test_an_unverifiable_claim_is_bounded_by_age(
    tmp_path: Path, repo: tuple[Path, Path]
) -> None:
    """A claim written before #1032 carries no witness, so it is aged out.

    Until #1032 the age bound applied only to claims from ANOTHER host, so a
    same-host claim on a recycled pid never aged out at all: nothing could ever
    unwedge it. This is the bound that guarantees it always can.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-legacy", OTHER_PID, MATCHING_START)
    _lock_with(main, wt, pid=OTHER_PID, start=None, age_s=48 * 3600)

    res = _check_witness(wt, proc)

    assert _field(res, "OWNER_WITNESS") == "absent", res.stdout
    assert _verdict(res) == "stale", res.stdout


@requires_git
def test_a_fresh_unverifiable_claim_is_still_held(
    tmp_path: Path, repo: tuple[Path, Path]
) -> None:
    """GREEN for the bound: inside the window, a witness-less claim still holds.

    `absent` must never be rendered as `mismatched` - a check that cannot read
    identity has not disproved it.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-legacy", OTHER_PID, MATCHING_START)
    _lock_with(main, wt, pid=OTHER_PID, start=None, age_s=0)

    res = _check_witness(wt, proc)

    assert _field(res, "OWNER_WITNESS") == "absent", res.stdout
    assert _verdict(res) == "held", res.stdout


@requires_git
def test_a_verified_owner_is_never_aged_out(tmp_path: Path, repo: tuple[Path, Path]) -> None:
    """The two-sided guard on the threshold change (Oscillation Control).

    Extending the age bound to same-host claims could evict a session that has
    legitimately worked one worktree for days. It cannot: the bound is applied
    ONLY where identity could not be established, so a matching witness is
    decisive at any age. This is the case that would have to fail for anyone to
    want the threshold moved back.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-live", OTHER_PID, MATCHING_START)
    _lock_with(main, wt, pid=OTHER_PID, start=MATCHING_START, age_s=90 * 24 * 3600)

    res = _check_witness(wt, proc)

    assert _field(res, "OWNER_WITNESS") == "matched", res.stdout
    assert _verdict(res) == "held", res.stdout


@requires_git
def test_an_unreadable_proc_falls_back_rather_than_inventing_staleness(
    tmp_path: Path, repo: tuple[Path, Path]
) -> None:
    """Portability: no /proc (not Linux) degrades to the pre-#1032 reading.

    Degraded, never wrong. The witness may only DEMOTE on a positively read
    conflicting value; an unreadable one must not.
    """
    main, wt = repo
    empty = tmp_path / "proc-empty"
    empty.mkdir()
    _lock_with(main, wt, pid=OTHER_PID, start=MATCHING_START)

    res = _check_witness(wt, empty)

    assert _field(res, "OWNER_WITNESS") == "unreadable", res.stdout
    assert _verdict(res) == "held", res.stdout


@requires_git
def test_a_recycled_pid_landing_on_our_own_pid_is_not_self(
    tmp_path: Path, repo: tuple[Path, Path]
) -> None:
    """RED (was): the pid-only `self` shortcut bypassed the witness entirely.

    Session id is authoritative, but the fallback matched on the pid ALONE -
    the same pid-identity mistake this issue is about, pointed at ourselves. A
    recycled pid can land on OUR number while the claim belongs to a session
    that has since died.

    This was the worse half, because `self` ALSO makes worktree-remove.sh skip
    its independent occupancy check (``CLAIM_OWNED_BY_US``): a false `self`
    removes a guard rather than merely misreporting a state. Found by the
    counter-model review of this change.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-recycled", SELF_PID, RECYCLED_START)
    # The claim records OUR pid, a DIFFERENT session, and a conflicting witness.
    _lock_with(main, wt, pid=SELF_PID, start=MATCHING_START)

    res = _check_witness(wt, proc, live=SELF_PID)

    assert _field(res, "OWNER_WITNESS") == "mismatched", res.stdout
    assert _verdict(res) == "stale", res.stdout


@requires_git
def test_our_own_live_claim_is_still_self(tmp_path: Path, repo: tuple[Path, Path]) -> None:
    """GREEN for the above: the ordinary self-owned case must be untouched."""
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-live", SELF_PID, MATCHING_START)
    _lock_with(main, wt, pid=SELF_PID, start=MATCHING_START)

    res = _check_witness(wt, proc, live=SELF_PID)
    assert _verdict(res) == "self", res.stdout


@requires_git
def test_staleness_names_its_cause_rather_than_asserting_a_death(
    tmp_path: Path, repo: tuple[Path, Path]
) -> None:
    """A claim released by the age bound must not be reported as a dead owner.

    Three causes reach `stale`, and the takeover message asserted one of them
    for all three. An expired witness-less claim whose pid is STILL RUNNING is
    expiry, not a death - claiming otherwise states a fact the check never
    established, which is the failure class this whole issue is about.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-live", OTHER_PID, MATCHING_START)
    _lock_with(main, wt, pid=OTHER_PID, start=None, age_s=48 * 3600)

    res = _check_witness(wt, proc)
    assert _verdict(res) == "stale", res.stdout
    assert _field(res, "STALE_REASON") == "aged-out-unverified", res.stdout

    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_PID": SELF_PID,
            "CLAUDE_CODE_SESSION_ID": SELF_SESSION,
            "FLOW_CLAIM_HOST": "testhost",
            "FLOW_CLAIM_LIVE_PIDS": OTHER_PID,
            "FLOW_CLAIM_PROC_ROOT": str(proc),
        }
    )
    taken = subprocess.run(
        ["bash", str(CLAIM), "claim", str(wt), "--issue", "42"],
        env=env, capture_output=True, text=True, check=False,
    )
    assert "EXPIRED" in taken.stderr, taken.stderr
    assert "is gone" not in taken.stderr, taken.stderr


@requires_git
def test_a_departed_owner_still_reads_as_gone(tmp_path: Path, repo: tuple[Path, Path]) -> None:
    """GREEN for the above: the genuinely-exited case keeps its own wording.

    Without this half, the previous test passes for a helper that has simply
    stopped saying "gone" at all - which would lose the distinction rather than
    draw it.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-empty", "1", MATCHING_START)
    _lock_with(main, wt, pid=OTHER_PID, start=MATCHING_START)

    res = _check_witness(wt, proc, live="")
    assert _verdict(res) == "stale", res.stdout
    assert _field(res, "STALE_REASON") == "owner-exited", res.stdout


@requires_git
def test_a_takeover_does_not_inherit_the_old_claims_stale_reason(
    tmp_path: Path, repo: tuple[Path, Path]
) -> None:
    """The acquired claim's record must describe the acquired claim.

    After taking over an expired claim, the emit block reported the NEW owner
    with age 0 alongside the PREVIOUS owner's `aged-out-unverified` - a record
    asserting something untrue of the thing it names, which is the failure class
    this issue exists to remove. Found by the second counter-model pass.
    """
    main, wt = repo
    proc = _fake_proc(tmp_path / "proc-live", OTHER_PID, MATCHING_START)
    _lock_with(main, wt, pid=OTHER_PID, start=None, age_s=48 * 3600)

    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_PID": SELF_PID,
            "CLAUDE_CODE_SESSION_ID": SELF_SESSION,
            "FLOW_CLAIM_HOST": "testhost",
            "FLOW_CLAIM_LIVE_PIDS": OTHER_PID,
            "FLOW_CLAIM_PROC_ROOT": str(proc),
        }
    )
    taken = subprocess.run(
        ["bash", str(CLAIM), "claim", str(wt), "--issue", "42"],
        env=env, capture_output=True, text=True, check=False,
    )

    assert _verdict(taken) == "self", taken.stdout
    assert _field(taken, "STALE_REASON") == "-", taken.stdout
    assert _field(taken, "AGE_MIN") == "0", taken.stdout
