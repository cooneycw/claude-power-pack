"""Run identity for the /flow:auto plan record (issue #1320).

The record was keyed on the issue, so a SECOND run on an issue was satisfied by
the FIRST run's committed approval: `reconcile` restored it and the Step-3 guard
accepted any `Approval: granted`. A run is now one driving session in one
worktree. Its id lives in the per-worktree git dir, and every check reads only
that run's section.

Orchestrator rulings pinned here:
  - the same CLAUDE_CODE_SESSION_ID keeps the run (resume, compaction, a kyle
    respawn via `claude --resume`), so an approved run is not re-gated;
  - a different session mints a new run, which needs its own approval;
  - an UNSET or EMPTY session always mints: an unknown identity never inherits.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "flow-plan-record.py"
GUARD = ROOT / "scripts" / "step3-record-guard.sh"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")
requires_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "wt"
    r.mkdir()
    git(r, "init", "-q", "-b", "issue-42-a-fixture")
    git(r, "config", "user.email", "t@e.com")
    git(r, "config", "user.name", "t")
    (r / "README.md").write_text("base\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    return r


def helper(repo: Path, session: str | None, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    if session is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session
    return subprocess.run(["python3", str(HELPER), *args], cwd=repo, capture_output=True,
                          text=True, env=env)


def run_id(repo: Path) -> str:
    gitdir = git(repo, "rev-parse", "--absolute-git-dir").strip()
    text = (Path(gitdir) / "flow-plan-run-42").read_text()
    m = re.search(r"^run_id=([0-9a-f]{32})$", text, re.M)
    assert m, text
    return m.group(1)


def reconcile(repo: Path, session: str | None) -> str:
    proc = helper(repo, session, "reconcile", "42")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def approve_run(repo: Path, session: str | None) -> None:
    assert helper(repo, session, "begin-run", "42").returncode == 0
    with (repo / "docs" / "flow-runs" / "issue-42.md").open("a") as fh:
        fh.write("- Approval:          granted\n\n### Section C - the approved plan\n"
                 "1. `src/a.py` - because\n")


def guard(repo: Path) -> subprocess.CompletedProcess:
    payload = '{"tool_name":"Write","tool_input":{"file_path":"%s"}}' % (repo / "src" / "a.py")
    return subprocess.run(["bash", str(GUARD)], input=payload, cwd=repo, capture_output=True,
                          text=True)


# ------------------------------------------------------------------ what is a run

@requires_git
def test_the_same_session_keeps_its_run(repo: Path) -> None:
    assert "FLOW_PLAN_RUN: minted" in reconcile(repo, "session-A")
    first = run_id(repo)
    assert "FLOW_PLAN_RUN: kept (same session)" in reconcile(repo, "session-A")
    assert run_id(repo) == first


@requires_git
def test_a_different_session_is_a_new_run(repo: Path) -> None:
    reconcile(repo, "session-A")
    first = run_id(repo)
    assert "FLOW_PLAN_RUN: minted" in reconcile(repo, "session-B")
    assert run_id(repo) != first


@pytest.mark.parametrize("session", [None, ""], ids=["unset", "empty"])
@requires_git
def test_an_unknown_session_always_mints(repo: Path, session: str | None) -> None:
    """Orchestrator ruling: an unknown identity must never inherit an approval."""
    reconcile(repo, session)
    first = run_id(repo)
    assert "FLOW_PLAN_RUN: minted" in reconcile(repo, session)
    assert run_id(repo) != first


@requires_git
def test_begin_run_needs_a_run_identity(repo: Path) -> None:
    proc = helper(repo, "session-A", "begin-run", "42")
    assert proc.returncode == 1
    assert "has no usable run identity" in proc.stdout


@requires_git
def test_begin_run_is_append_only_and_idempotent(repo: Path) -> None:
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")
    record = repo / "docs" / "flow-runs" / "issue-42.md"
    before = record.read_text()
    assert helper(repo, "session-A", "begin-run", "42").returncode == 0
    assert record.read_text() == before, "a second begin-run for the same run must not append"
    # Committed before the next session reconciles: reconcile treats an UNCOMMITTED
    # record as a dead run's scratch and removes it (#1080, unchanged).
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run 1")
    reconcile(repo, "session-B")
    assert helper(repo, "session-B", "begin-run", "42").returncode == 0
    after = record.read_text()
    assert after.startswith(before), "run 1's section was edited, not appended to"
    assert "## Run 2" in after


# ------------------------------------------------------------------ the gate (#1320 red case)

@requires_git
@requires_bash
def test_a_second_session_is_refused_on_the_first_runs_approval(repo: Path) -> None:
    """THE #1320 BYPASS: run 1 approved and committed; a new session reconciles and edits."""
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")
    assert guard(repo).returncode == 0, "precondition: run 1's own approval lets run 1 edit"
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run 1 approved")
    reconcile(repo, "session-B")
    refused = guard(repo)
    assert refused.returncode == 2
    assert "THIS run has not been approved" in refused.stderr
    assert run_id(repo) in refused.stderr, "the refusal names this run's id"


@requires_git
@requires_bash
def test_a_resumed_session_is_not_re_gated(repo: Path) -> None:
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run 1 approved")
    reconcile(repo, "session-A")                 # the same session resumes
    assert guard(repo).returncode == 0


@requires_git
@requires_bash
def test_the_real_legacy_record_from_main_behaves_as_run_1(repo: Path) -> None:
    """Orchestrator condition: pin the transition with a REAL record, not only a synthetic."""
    legacy = git(ROOT, "show", "HEAD:docs/flow-runs/issue-1289.md")
    assert "- Approval:          granted" in legacy and "flow-run n=" not in legacy
    (repo / "docs" / "flow-runs").mkdir(parents=True)
    (repo / "docs" / "flow-runs" / "issue-42.md").write_text(legacy)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a committed pre-#1320 record")
    # In flight, no run file in this worktree: allowed exactly as before #1320.
    assert guard(repo).returncode == 0
    # A new session starts a run here: the legacy approval is not this run's.
    reconcile(repo, "session-B")
    refused = guard(repo)
    assert refused.returncode == 2
    assert "a legacy (pre-#1320) record" in refused.stderr


# ------------------------------------------------------------------ head-check

@requires_git
def test_head_check_requires_this_runs_section_at_the_head(repo: Path) -> None:
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run 1")
    head = git(repo, "rev-parse", "HEAD").strip()
    ok = helper(repo, "session-A", "head-check", "42", "--head", head)
    assert ok.returncode == 0 and "with this run's section" in ok.stdout
    reconcile(repo, "session-B")                  # run 2, whose section is not committed
    absent = helper(repo, "session-B", "head-check", "42", "--head", head)
    assert absent.returncode == 1
    assert "has no section of its own" in absent.stdout


# ------------------------------------------------------------------ counter-model review fixes

@requires_git
@requires_bash
def test_a_resuming_session_keeps_its_uncommitted_new_record(repo: Path) -> None:
    """HIGH: reconcile deleted the same session's uncommitted, approved section."""
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")
    record = repo / "docs" / "flow-runs" / "issue-42.md"
    before = record.read_text()
    out = reconcile(repo, "session-A")            # the SAME session resumes, nothing committed
    assert "the same session is resuming" in out
    assert record.read_text() == before
    assert guard(repo).returncode == 0


@requires_git
@requires_bash
def test_a_resuming_session_keeps_its_section_appended_to_committed_history(repo: Path) -> None:
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run 1")
    reconcile(repo, "session-B")
    approve_run(repo, "session-B")                # run 2's section: appended, uncommitted
    record = repo / "docs" / "flow-runs" / "issue-42.md"
    before = record.read_text()
    reconcile(repo, "session-B")                  # run 2 resumes
    assert record.read_text() == before, "restoring HEAD erased run 2's uncommitted section"
    assert guard(repo).returncode == 0


@requires_git
def test_a_legacy_snapshot_prefix_survives_later_approvals(repo: Path) -> None:
    """MEDIUM: the legacy text before the first marker was dropped on a rewrite."""
    snap = repo / "docs" / "flow-runs" / "issue-42.as-read.md"
    snap.parent.mkdir(parents=True)
    legacy = "# Issue #42 as read by this run\n\nLEGACY-EVIDENCE-LINE\n"
    snap.write_text(legacy)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a legacy snapshot")
    for session in ("session-A", "session-B"):
        reconcile(repo, session)
        approve_run(repo, session)
        helper(repo, session, "approve", "42")
        helper(repo, session, "approve", "42")    # re-approval rewrites this run's part
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", f"approved {session}")
    assert snap.read_text().startswith(legacy), "the legacy snapshot bytes were lost"


@requires_git
def test_head_check_without_a_run_file_refuses_a_marked_record(repo: Path) -> None:
    """MEDIUM: only a LEGACY record may pass head-check with no run identity."""
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a marked record")
    head = git(repo, "rev-parse", "HEAD").strip()
    gitdir = git(repo, "rev-parse", "--absolute-git-dir").strip()
    (Path(gitdir) / "flow-plan-run-42").unlink()
    assert not (Path(gitdir) / "flow-plan-run-42").exists(), "precondition: no run identity"
    proc = helper(repo, "session-A", "head-check", "42", "--head", head)
    assert proc.returncode == 1
    assert "has no run identity" in proc.stdout


@requires_git
def test_a_marker_line_inside_the_issue_body_is_not_a_run_boundary(repo: Path, tmp_path: Path) -> None:
    """MEDIUM: quoted issue text could forge a run boundary in the snapshot."""
    body = tmp_path / "body.md"
    body.write_bytes(("intro\n<!-- flow-run n=99 id=" + "a" * 32 + " -->\n## Run 99\ntail\n").encode())
    reconcile(repo, "session-A")
    assert helper(repo, "session-A", "read-issue", "42", "--body-file", str(body)).returncode == 0
    approve_run(repo, "session-A")
    assert helper(repo, "session-A", "approve", "42").returncode == 0
    snap = (repo / "docs" / "flow-runs" / "issue-42.as-read.md").read_text()
    markers = re.findall(r"^<!-- flow-run n=(\d+) id=([0-9a-f]{32}) -->$", snap, re.M)
    assert markers == [("1", run_id(repo))], f"the quoted body forged a boundary: {markers}"
    drift = helper(repo, "session-A", "drift", "42", "--live-file", str(body))
    assert drift.returncode == 0 and "ISSUE_DRIFT: clean" in drift.stdout, drift.stdout


@requires_git
def test_a_malformed_run_file_does_not_reopen_the_legacy_fallback(repo: Path) -> None:
    """Re-review MEDIUM: an EXISTING but empty run file is not "no run file"."""
    legacy = git(ROOT, "show", "HEAD:docs/flow-runs/issue-1289.md")
    (repo / "docs" / "flow-runs").mkdir(parents=True)
    (repo / "docs" / "flow-runs" / "issue-42.md").write_text(legacy)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a committed pre-#1320 record")
    head = git(repo, "rev-parse", "HEAD").strip()
    gitdir = Path(git(repo, "rev-parse", "--absolute-git-dir").strip())
    (gitdir / "flow-plan-run-42").write_text("")          # emptied / truncated
    assert (gitdir / "flow-plan-run-42").exists(), "precondition: the file EXISTS"
    approve = helper(repo, "session-A", "approve", "42")
    assert approve.returncode == 1 and "malformed" in approve.stdout, approve.stdout
    headcheck = helper(repo, "session-A", "head-check", "42", "--head", head)
    assert headcheck.returncode == 1 and "malformed" in headcheck.stdout, headcheck.stdout
    assert "FLOW_PLAN_RUN: minted" in reconcile(repo, "session-A"), "reconcile repairs it"


@requires_git
def test_a_second_run_is_not_blamed_for_the_first_runs_committed_work(repo: Path) -> None:
    """Re-review MEDIUM: run A's committed src/a.py must not read as run B's unplanned
    change. Compliance defaults to THIS run's recorded start; an explicit --base is the
    broader, whole-branch scope."""
    branch_base = git(repo, "rev-parse", "HEAD").strip()
    reconcile(repo, "session-A")
    approve_run(repo, "session-A")                 # plans src/a.py
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run A's work")
    reconcile(repo, "session-B")
    assert helper(repo, "session-B", "begin-run", "42").returncode == 0
    with (repo / "docs" / "flow-runs" / "issue-42.md").open("a") as fh:
        fh.write("- Approval:          granted\n\n### Section C - the approved plan\n"
                 "1. `src/b.py` - run B\n")
    assert helper(repo, "session-B", "approve", "42").returncode in (0, 4)
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work")
    own = helper(repo, "session-B", "compliance", "42")
    assert "PLAN_COMPLIANCE_BASE: this run's start" in own.stdout, own.stdout
    assert "PLAN_COMPLIANCE: agreement" in own.stdout, own.stdout
    assert "src/a.py" not in own.stdout
    whole = helper(repo, "session-B", "compliance", "42", "--base", branch_base)
    assert "TOUCHED BUT NOT PLANNED: src/a.py" in whole.stdout, whole.stdout


def _plan_b(repo: Path, session: str) -> None:
    assert helper(repo, session, "begin-run", "42").returncode == 0
    with (repo / "docs" / "flow-runs" / "issue-42.md").open("a") as fh:
        fh.write("- Approval:          granted\n\n### Section C - the approved plan\n"
                 "1. `src/b.py` - this run\n")


@requires_git
def test_upstream_merged_after_the_run_started_is_not_this_runs_work(repo: Path) -> None:
    """Pass-3 MEDIUM: run-start alone blamed the run for upstream files merged in later.

    The MECHANISM changed under #1399 (first-parent commit walk, not an
    endpoint-diff intersection with main_base - see log_touched), but the
    protection this pins must not: required regression, run before and
    after the #1399 fix.
    """
    base = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    reconcile(repo, "session-B")
    _plan_b(repo, "session-B")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's record")
    # upstream moves on with an unrelated file; the run merges it in
    git(repo, "checkout", "-q", "-b", "upstream", base)
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "unrelated.md").write_text("upstream\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "upstream work")
    git(repo, "update-ref", "refs/remotes/origin/main", git(repo, "rev-parse", "HEAD").strip())
    git(repo, "checkout", "-q", "issue-42-a-fixture")
    git(repo, "merge", "-q", "--no-edit", "origin/main")
    assert (repo / "docs" / "unrelated.md").exists(), "precondition: upstream merged in"
    (repo / "src").mkdir()
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work")
    out = helper(repo, "session-B", "compliance", "42").stdout
    assert "PLAN_COMPLIANCE_BASE: this run's start" in out, out
    assert "docs/unrelated.md" not in out, f"upstream work was blamed on this run:\n{out}"
    assert "PLAN_COMPLIANCE: agreement" in out, out


@requires_git
def test_upstream_work_absorbed_by_a_fast_forward_is_not_this_runs_work(repo: Path) -> None:
    """Counter-model review, pass 2 (#1399): the test above covers a MERGE
    commit; --first-parent alone cannot tell a fast-forward (no merge commit
    at all) apart from this run's own commits, because a fast-forwarded
    upstream commit sits directly ON the first-parent chain. The branch
    fast-forwards to upstream commit B (no local work yet, so no divergence
    to prevent it); this run's own commits come AFTER that. Upstream then
    moves on further to C, built on B, and does NOT fast-forward again (this
    branch has diverged by then) - so by compliance time, origin/main is C,
    and B (this run never created it) must still be excluded by identity.
    """
    base = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    reconcile(repo, "session-B")
    assert helper(repo, "session-B", "begin-run", "42").returncode == 0
    run_start = git(repo, "rev-parse", "HEAD").strip()
    # upstream moves to B; this run's own branch fast-forwards to it directly
    # (no merge commit - it has no commits of its own yet to diverge with).
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "unrelated.md").write_text("upstream B\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "upstream work (B)")
    git(repo, "update-ref", "refs/remotes/origin/main", git(repo, "rev-parse", "HEAD").strip())
    _plan_b(repo, "session-B")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's record")
    (repo / "src").mkdir()
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work")
    # upstream moves on FURTHER to C, built on B; this branch does not ff again.
    git(repo, "checkout", "-q", "-b", "upstream-continues", run_start)
    git(repo, "merge", "-q", "--no-edit", "origin/main")
    (repo / "docs" / "more.md").write_text("upstream C\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "upstream work (C)")
    git(repo, "update-ref", "refs/remotes/origin/main", git(repo, "rev-parse", "HEAD").strip())
    git(repo, "checkout", "-q", "issue-42-a-fixture")
    out = helper(repo, "session-B", "compliance", "42").stdout
    assert "docs/unrelated.md" not in out, f"fast-forwarded upstream work was blamed:\n{out}"
    assert "PLAN_COMPLIANCE: agreement" in out, out


@requires_git
def test_a_rewritten_run_start_is_unknown_never_a_wider_scope(repo: Path) -> None:
    """Pass-3 MEDIUM: after a rebase the run's start is not an ancestor; do not widen."""
    reconcile(repo, "session-B")
    (repo / "x.txt").write_text("1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a commit the run starts on")
    _plan_b(repo, "session-B")                     # records Run-start = that commit
    start = git(repo, "rev-parse", "HEAD").strip()
    record = (repo / "docs" / "flow-runs" / "issue-42.md").read_text()
    git(repo, "reset", "-q", "--hard", "HEAD~1")    # history rewritten under the run
    (repo / "x.txt").write_text("2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "a different commit")
    (repo / "docs" / "flow-runs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "flow-runs" / "issue-42.md").write_text(record)
    assert subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", start, "HEAD"],
                          capture_output=True).returncode != 0, "precondition: start rewritten"
    proc = helper(repo, "session-B", "compliance", "42")
    assert proc.returncode == 4, proc.stdout
    assert "is no longer an ancestor of HEAD" in proc.stdout


@requires_git
def test_an_unresolvable_upstream_falls_back_labelled_not_silently(repo: Path) -> None:
    """Counter-model review, pass 2 (#1399): with no origin/main to exclude
    by, don't guess - keep today's (pre-exclusion) behaviour and say so, so
    a reader can tell "verified, upstream work excluded" from "could not
    check, might be included" apart. The `repo` fixture carries no remote,
    which is the ordinary unresolvable case (no fetch has ever happened).
    """
    reconcile(repo, "session-B")
    _plan_b(repo, "session-B")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's record")
    (repo / "src").mkdir()
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work")
    out = helper(repo, "session-B", "compliance", "42").stdout
    assert "touched-set: upstream unresolved" in out, out
    assert "fast-forwarded upstream work may be counted" in out, out
    assert "PLAN_COMPLIANCE: agreement" in out, out


# ------------------------------------------------------------------ issue #1399: the
# elif-start branch had zero coverage of its own ordinary case, and the
# endpoint-diff intersection it used could not see a reverted file's own history

@requires_git
def test_a_planned_file_touched_on_this_runs_own_start_branch_is_agreement(repo: Path) -> None:
    """The first PLAIN agreement case for the run_start branch.

    Every other test of this branch exists only to pin a specific bug or
    boundary (a rewritten start, an upstream merge, the revert cases below) -
    the ordinary "planned work, no drift" case was never itself demonstrated
    here, so a red case for one of those bugs could in principle be the only
    thing keeping this path exercised at all.
    """
    reconcile(repo, "session-B")
    _plan_b(repo, "session-B")                      # Section C names only src/b.py
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's record")
    (repo / "src").mkdir()
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work")
    out = helper(repo, "session-B", "compliance", "42").stdout
    assert "PLAN_COMPLIANCE: agreement" in out, out


@requires_git
def test_a_revert_to_mains_content_is_still_this_runs_touch(repo: Path) -> None:
    """Nit Store #864 comment 5875009399: the endpoint-diff intersection with
    main_base silently dropped a file this run genuinely touched, whenever
    its net effect happened to match main's content again.

    Reproduced empirically on 86641e8 before fixing this. ORDER MATTERS:
    shared.py must exist at main's content BEFORE the "earlier run" edits
    it, or the later revert reads as a brand-new addition (differs from
    main_base either way) instead of the genuine revert this case is about -
    a mistake made and caught while building this case.
    """
    (repo / "src").mkdir()
    (repo / "src" / "shared.py").write_text("original\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "shared.py at main's content")
    git(repo, "update-ref", "refs/remotes/origin/main", git(repo, "rev-parse", "HEAD").strip())
    # "an earlier run" edits shared.py BEFORE session-B's run starts.
    (repo / "src" / "shared.py").write_text("edited-by-earlier-run\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "earlier run edits shared.py")
    reconcile(repo, "session-B")
    _plan_b(repo, "session-B")                      # Section C names only src/b.py
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's record")
    # THIS run reverts shared.py back to main's content, and does its own work.
    (repo / "src" / "shared.py").write_text("original\n")
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work: revert shared.py, add b.py")
    out = helper(repo, "session-B", "compliance", "42").stdout
    assert "PLAN_COMPLIANCE: divergence" in out, out
    assert "TOUCHED BUT NOT PLANNED: src/shared.py" in out, out


@requires_git
def test_an_uncommitted_unplanned_file_is_still_touched(repo: Path) -> None:
    """Counter-model review (#1399): `log_touched` reads COMMITTED history
    only - `git log` never looks at the index or the working tree - so a
    staged or unstaged file this run has not committed yet was invisible to
    it alone. Confirmed empirically before fixing: an uncommitted unplanned
    file reported PLAN_COMPLIANCE: agreement with the fix's first cut.
    changed_since("HEAD") (the same call `--base` and the no-Run-start
    branch already use) is unioned in to cover it.
    """
    reconcile(repo, "session-B")
    _plan_b(repo, "session-B")                      # Section C names only src/b.py
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's record")
    (repo / "src").mkdir()
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's planned work")
    (repo / "src" / "stray.py").write_text("stray\n")  # never committed
    out = helper(repo, "session-B", "compliance", "42").stdout
    assert "PLAN_COMPLIANCE: divergence" in out, out
    assert "TOUCHED BUT NOT PLANNED: src/stray.py" in out, out


@requires_git
def test_an_edit_and_revert_entirely_within_this_runs_own_commits_still_counts(
    repo: Path,
) -> None:
    """A DIFFERENT net-zero than the case above: shared.py is unchanged
    relative to THIS RUN'S OWN START by the time HEAD is reached, because
    this run edited it and then reverted it ITSELF - no pre-existing main_base
    drift at all. The old endpoint-diff-against-run_start could never see
    this (nothing differs between run_start and HEAD); the new per-commit log
    union does, because each of this run's own commits touched the file
    independently. Ruling (#1399): compliance only reports, so over-reporting
    is the safe direction, and the run genuinely did that work - count it.
    """
    (repo / "src").mkdir()
    (repo / "src" / "shared.py").write_text("v0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "shared.py exists before this run starts")
    reconcile(repo, "session-B")
    _plan_b(repo, "session-B")                      # Section C names only src/b.py
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's record")
    (repo / "src" / "shared.py").write_text("v1\n")  # this run's own edit
    (repo / "src" / "b.py").write_text("b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work, first pass")
    (repo / "src" / "shared.py").write_text("v0\n")  # this run reverts its OWN edit
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "run B's work, self-correction back to v0")
    out = helper(repo, "session-B", "compliance", "42").stdout
    assert "PLAN_COMPLIANCE: divergence" in out, out
    assert "TOUCHED BUT NOT PLANNED: src/shared.py" in out, out
