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
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "step3-record-guard.sh"

requires_git = pytest.mark.skipif(
    shutil.which("git") is None,
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
    assert "step3-record-guard: REFUSED" in proc.stderr
    # The refusal must be RECOVERABLE, not merely a refusal.
    assert "docs/flow-runs/issue-4242.md" in proc.stderr, "names what is missing"
    assert "WHAT TO DO" in proc.stderr, "names the route to approval"


@requires_git
def test_an_edit_WITH_an_approved_record_proceeds(tmp_path: Path):
    wt = _worktree(tmp_path)
    (wt / "docs" / "flow-runs" / "issue-4242.md").write_text(APPROVED, encoding="utf-8")
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == "" and proc.stderr == "", "an allowed edit must be silent"


@requires_git
def test_a_record_WITHOUT_an_approval_is_still_refused(tmp_path: Path):
    """Presence is not approval. A record that records no approval is not one."""
    wt = _worktree(tmp_path)
    (wt / "docs" / "flow-runs" / "issue-4242.md").write_text(
        "# Flow run record - issue #4242\n\n- Approval:          pending\n", encoding="utf-8"
    )
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 2, proc.stderr
    assert "does not record an approval" in proc.stderr


@requires_git
def test_the_record_path_is_exempt_or_every_run_DEADLOCKS(tmp_path: Path):
    """The bootstrap. The record is written BY an edit.

    Without this exemption the guard blocks the write of the very record that
    would unblock it, and no run can ever reach its second edit.
    """
    wt = _worktree(tmp_path)
    for target in ("docs/flow-runs/issue-4242.md", "docs/flow-runs/issue-4242.as-read.md"):
        proc = _run(wt, "Write", str(wt / target))
        assert proc.returncode == 0, f"{target} must be writable with no record:\n{proc.stderr}"


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
        assert proc.returncode == 2, f"{target} must NOT be exempt:\n{proc.stderr}"


@requires_git
def test_a_NON_flow_branch_is_not_this_guards_business(tmp_path: Path):
    wt = _worktree(tmp_path, branch="some-other-branch")
    proc = _run(wt, "Write", str(wt / "scripts" / "x.sh"))
    assert proc.returncode == 0, proc.stderr


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
        f"fail-open the issue forbids:\n{proc.stderr}"
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
    matcher = template["hooks"]["PreToolUse"][0]["matcher"]
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


# --- Fail-opens found by counter-model review, each reproduced first ---------
#
# #1083 calls fail-open the one non-negotiable thing, and this guard shipped
# three of them past its own author. Every test below was RED before its fix.


def _raw(wt: Path, payload: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GUARD)], input=payload, capture_output=True, text=True,
        cwd=wt, check=False, env={**os.environ, **(env or {})},
    )


@requires_git
def test_MALFORMED_input_refuses_rather_than_allowing(tmp_path: Path):
    """An inability to look is not a clean look."""
    wt = _worktree(tmp_path)
    proc = _raw(wt, "not json at all")
    assert proc.returncode == 2, proc.stderr
    assert "REFUSED" in proc.stderr


@requires_git
def test_a_request_with_NO_TOOL_NAME_refuses(tmp_path: Path):
    wt = _worktree(tmp_path)
    proc = _raw(wt, json.dumps({"tool_input": {"file_path": str(wt / "scripts" / "x.sh")}}))
    assert proc.returncode == 2, proc.stderr


@requires_git
def test_an_ABSENT_python3_refuses(tmp_path: Path):
    """The parser is a dependency, and a missing dependency used to ALLOW."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python3").write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
    (fake / "python3").chmod(0o755)
    wt = _worktree(tmp_path)
    proc = _raw(
        wt,
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(wt / "scripts" / "x.sh")}}),
        env={"PATH": f"{fake}:/usr/bin:/bin"},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr


@requires_git
def test_a_BROKEN_GIT_refuses_but_a_GENUINE_non_repo_does_not(tmp_path: Path):
    """The discriminator, in BOTH directions, because only one is safe to allow.

    Both failures say "not a git repository". They differ in the parenthetical:
    a genuine walk-up failure says "(or any of the parent directories)", a
    broken GIT_DIR names a path. Matching the GENERAL phrase allowed the broken
    environment - reproduced - so the specific one is matched instead, which
    puts the fragility in the safe direction.
    """
    wt = _worktree(tmp_path)
    payload = json.dumps(
        {"tool_name": "Write", "tool_input": {"file_path": str(wt / "scripts" / "x.sh")}}
    )
    broken = _raw(wt, payload, env={"GIT_DIR": "/nonexistent"})
    assert broken.returncode == 2, f"a broken git must refuse:\n{broken.stderr}"

    outside = tmp_path / "plain"
    outside.mkdir()
    ok = _raw(
        outside,
        json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(outside / "x.sh")}}),
    )
    assert ok.returncode == 0, (
        "a target genuinely outside any repository is DETERMINED and out of "
        f"scope; refusing it would block every edit outside a checkout:\n{ok.stderr}"
    )


@requires_git
def test_the_subject_is_the_TARGETS_worktree_not_the_hooks_cwd(tmp_path: Path):
    """The ownership question, on the guard's own subject.

    Resolving from the hook's cwd let the verdict describe a NEIGHBOUR: an edit
    into a recordless worktree returned 0 when the hook happened to run from an
    approved one.
    """
    approved = _worktree(tmp_path / "a")
    (approved / "docs" / "flow-runs" / "issue-4242.md").write_text(APPROVED, encoding="utf-8")
    recordless = _worktree(tmp_path / "b")

    proc = _raw(
        approved,
        json.dumps(
            {"tool_name": "Write", "tool_input": {"file_path": str(recordless / "scripts" / "x.sh")}}
        ),
    )
    assert proc.returncode == 2, (
        "the verdict must describe the worktree the EDIT LANDS IN, not the one "
        f"the hook runs in:\n{proc.stderr}"
    )


@requires_git
def test_a_LOOKALIKE_path_is_not_exempt(tmp_path: Path):
    """The exemption is two exact paths under the resolved root, not a suffix."""
    wt = _worktree(tmp_path)
    (wt / "vendor" / "docs" / "flow-runs").mkdir(parents=True)
    proc = _run(wt, "Write", str(wt / "vendor" / "docs" / "flow-runs" / "issue-4242.md"))
    assert proc.returncode == 2, (
        f"a nested lookalike must not be exempt:\n{proc.stderr}"
    )
