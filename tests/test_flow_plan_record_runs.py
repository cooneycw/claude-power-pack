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
    assert "has no run identity" in proc.stdout


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
