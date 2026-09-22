"""Tests for scripts/step3-record-guard.sh - the Step 3 approved-plan floor.

Contract:
- In a flow worktree (branch `issue-<N>-<slug>`) with no approved-plan record at
  `docs/flow-runs/issue-<N>.md`, an edit is REFUSED with a block message naming
  what is missing and how to obtain it.
- With a record recording `Approval: granted`, the edit proceeds.
- Exactly ONE exemption: the record's own path, because the record is written BY
  an edit and a guard without it deadlocks every run on its first edit.

WHAT THIS IS NOT, asserted here as well as stated in the script, because a bound
that lives only in prose is the thing this branch exists to stop shipping: the
guard establishes that an ARTIFACT is present, never that an APPROVAL occurred,
and only on the tool paths it is matched against. It does not enforce #775.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "step3-record-guard.sh"

requires_git = pytest.mark.skipif(
    __import__("shutil").which("git") is None,
    reason="needs git: the guard reads the worktree's branch to find its subject",
)

APPROVED = (
    "# Flow run record - issue #4242\n\n"
    "- Issue:             #4242\n"
    "- Approval:          granted\n"
)


def _worktree(tmp_path: Path, branch: str = "issue-4242-a-fixture") -> Path:
    """A REAL throwaway repo outside every checkout.

    Built rather than borrowed: the guard's subject is a property of a run, and a
    test reading the ambient checkout would measure the repository it lives in.
    """
    wt = tmp_path / "wt"
    (wt / "docs" / "flow-runs").mkdir(parents=True)
    (wt / "scripts").mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig")}
    subprocess.run(["git", "init", "-q", "."], cwd=wt, check=True, env=env)
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=wt, check=True, env=env)
    subprocess.run(
        ["git", "-c", "user.email=f@example.invalid", "-c", "user.name=f",
         "commit", "-q", "--allow-empty", "-m", "base"],
        cwd=wt, check=True, env=env,
    )
    return wt


def _run(wt: Path, tool: str, target: str) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": target}})
    return subprocess.run(
        ["bash", str(GUARD)], input=payload, capture_output=True, text=True,
        cwd=wt, check=False,
    )


@requires_git
def test_an_edit_with_no_record_is_REFUSED(tmp_path: Path):
    wt = _worktree(tmp_path)
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "step3-record-guard: REFUSED" in proc.stdout
    # The refusal must be RECOVERABLE, not merely a refusal.
    assert "docs/flow-runs/issue-4242.md" in proc.stdout, "names what is missing"
    assert "WHAT TO DO" in proc.stdout, "names the route to approval"


@requires_git
def test_an_edit_WITH_an_approved_record_proceeds(tmp_path: Path):
    wt = _worktree(tmp_path)
    (wt / "docs" / "flow-runs" / "issue-4242.md").write_text(APPROVED, encoding="utf-8")
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == "", "an allowed edit must be silent"


@requires_git
def test_a_record_WITHOUT_an_approval_is_still_refused(tmp_path: Path):
    """Presence is not approval. A record that records no approval is not one."""
    wt = _worktree(tmp_path)
    (wt / "docs" / "flow-runs" / "issue-4242.md").write_text(
        "# Flow run record - issue #4242\n\n- Approval:          pending\n", encoding="utf-8"
    )
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 2, proc.stdout
    assert "does not record an approval" in proc.stdout


@requires_git
def test_the_record_path_is_exempt_or_every_run_DEADLOCKS(tmp_path: Path):
    """The bootstrap. The record is written BY an edit.

    Without this exemption the guard blocks the write of the very record that
    would unblock it, and no run can ever reach its second edit.
    """
    wt = _worktree(tmp_path)
    for target in ("docs/flow-runs/issue-4242.md", "docs/flow-runs/issue-4242.as-read.md"):
        proc = _run(wt, "Write", str(wt / target))
        assert proc.returncode == 0, f"{target} must be writable with no record:\n{proc.stdout}"


@requires_git
def test_the_exemption_is_EXACTLY_ONE_PATTERN(tmp_path: Path):
    """The other direction: the exemption must not be a directory pass.

    A neighbouring file under docs/flow-runs/ - including ANOTHER issue's record
    - is not this run's bootstrap and must still be refused. Keyed on the issue
    number, not on the directory: location would exempt every worker's artifact.
    """
    wt = _worktree(tmp_path)
    for target in ("docs/flow-runs/issue-9999.md", "docs/flow-runs/notes.md"):
        proc = _run(wt, "Write", str(wt / target))
        assert proc.returncode == 2, f"{target} must NOT be exempt:\n{proc.stdout}"


@requires_git
def test_a_NON_flow_branch_is_not_this_guards_business(tmp_path: Path):
    wt = _worktree(tmp_path, branch="some-other-branch")
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 0, proc.stdout


@requires_git
def test_an_UNBORN_branch_does_not_FAIL_OPEN(tmp_path: Path):
    """The fail-open this guard's own control caught before it shipped.

    `git rev-parse --abbrev-ref HEAD` FAILS on a branch with no commits and
    prints the literal "HEAD", so the branch went undetected and the guard
    ALLOWED - the one thing #1083 calls non-negotiable. `git symbolic-ref
    --short HEAD` reports the name correctly in both states.
    """
    wt = tmp_path / "unborn"
    (wt / "docs" / "flow-runs").mkdir(parents=True)
    (wt / "scripts").mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig")}
    subprocess.run(["git", "init", "-q", "."], cwd=wt, check=True, env=env)
    subprocess.run(["git", "checkout", "-q", "-b", "issue-4242-unborn"], cwd=wt, check=True, env=env)
    # No commit: the branch exists and has no history.
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 2, (
        "an unborn flow branch must still be refused - allowing here is the "
        f"fail-open the issue forbids:\n{proc.stdout}{proc.stderr}"
    )


@requires_git
def test_the_BASH_path_is_NOT_SEEN_and_that_is_committed_not_hidden(tmp_path: Path):
    """The bound, asserted rather than only described.

    A PreToolUse guard matching Write/Edit does not see an edit made by Bash
    redirection. In THIS fleet that is the INSTRUCTED default - sessions are
    steered to use heredocs over Write/Edit - so the guard's silence here is not
    coverage, and controls/step3-record-guard commits the same gap as a CASE so
    that a change in the steer or the matcher flips it.

    This test exists so the bound cannot be quietly widened into a claim.
    """
    wt = _worktree(tmp_path)
    payload = json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "cat > scripts/x.sh <<EOF\nx\nEOF"}}
    )
    proc = subprocess.run(
        ["bash", str(GUARD)], input=payload, capture_output=True, text=True,
        cwd=wt, check=False,
    )
    assert proc.returncode == 0, "the guard does not match Bash - see the limits"
    assert proc.stdout == ""


def test_the_TEMPLATE_matcher_and_the_SCRIPT_agree_on_the_matched_tools():
    """A template shipping a matcher the script disagrees with is decoration.

    The template tells a consumer which tools to match; the script decides which
    tools it acts on. If they drift, the installed hook silently covers a
    different set than its own documentation claims - and coverage claims are
    the thing this change is most careful about.
    """
    doc = (ROOT / "templates" / "hooks" / "step3-record-guard.md").read_text()
    block = re.search(r"```json\n(.*?)```", doc, re.S)
    assert block, "the template document ships no installable hook block"
    template = json.loads(block.group(1))
    matcher = template["hooks"]["PreToolUse"][0]["matcher"]["tool_name"]
    advertised = set(matcher.split("|"))

    source = GUARD.read_text()
    # The script's own case arm is the authority for what it acts on.
    line = next(
        ln for ln in source.splitlines()
        if ln.strip().startswith("Write|") and ln.rstrip().endswith(") ;;")
    )
    acted_on = set(line.strip().split(")")[0].split("|"))

    assert advertised == acted_on, (
        f"the template advertises {sorted(advertised)} and the script acts on "
        f"{sorted(acted_on)} - an installed hook would cover a different set "
        "than its documentation claims"
    )


def test_the_template_does_not_claim_to_enforce_775():
    """The floor framing is a shipped promise, so pin it where it ships.

    A consumer reading the template is the reader most likely to over-rely on
    this hook, and least able to check.
    """
    doc = (ROOT / "templates" / "hooks" / "step3-record-guard.md").read_text()
    assert "does not enforce #775" in doc
    assert "not evidence that no edit happened" in doc
    lowered = doc.lower()
    for overclaim in ("enforces #775", "guarantees", "cannot be bypassed"):
        assert overclaim not in lowered, f"the template overclaims: {overclaim!r}"
