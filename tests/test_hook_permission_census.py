"""Tests for scripts/hook-permission-census.sh - the PermissionRequest census hook.

The hook is the harness-driven "record" for the `permission-prompt` friction
class (issue #482): it fires when a permission dialog is shown, derives the
narrowest candidate allow rule + a risk tier, and appends one record to the
project's .claude/friction.jsonl via friction-log.sh. Its contract:

- Derive the retro Step 4 rule shape (gh/git prefixes, bare commands exact).
- Rate risk and emit an allow candidate ONLY for the safe tiers; a risky prompt
  (rm -rf, force push, code-exec, network) is recorded with its tier but NO
  allow candidate, so a one-off approval never becomes a blind allowlist rule.
- OBSERVE-ONLY: never writes to stdout (cannot influence the permission decision).
- FAIL-OPEN: never exits non-zero; bad/empty input records nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / "scripts" / "hook-permission-census.sh"

# The hook shells out to bash and python3 (for JSON parsing + derivation). Skip
# cleanly where either is unavailable - the Woodpecker `validate` image ships
# both, but this keeps the module importable everywhere (cf. issue #430).
pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("python3") is None,
    reason="requires bash and python3 on PATH",
)


def _run(tmp_path: Path, payload: dict | str) -> tuple[subprocess.CompletedProcess[str], Path]:
    log = tmp_path / ".claude" / "friction.jsonl"
    env = os.environ.copy()
    env["CPP_FRICTION_LOG"] = str(log)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run(
        ["bash", str(CENSUS)],
        input=stdin,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        check=False,
    )
    return proc, log


def _records(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _one(tmp_path: Path, payload: dict) -> dict:
    proc, log = _run(tmp_path, payload)
    assert proc.returncode == 0, proc.stderr
    recs = _records(log)
    assert len(recs) == 1, recs
    return recs[0]


def test_script_is_executable():
    assert CENSUS.exists()
    assert os.access(CENSUS, os.X_OK), "hook-permission-census.sh must be executable"


def test_records_permission_prompt_with_shown_outcome(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "git fetch origin"}})
    assert rec["class"] == "permission-prompt"
    assert rec["outcome"] == "shown"  # SHOWN, not approved - the hook cannot see the click
    assert rec["scope"] == "local"  # census records are per-machine, never shared
    assert rec["run"] == "permission-census"
    assert rec["ts"].endswith("Z")


# --- Rule derivation matches /self-improvement:retro Step 4 -------------------

def test_gh_rule_is_three_deep(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "gh issue view 482 --json body"}})
    assert rec["fix"] == "Bash(gh issue view:*)"


def test_git_rule_is_two_deep(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "git fetch origin main --quiet"}})
    assert rec["fix"] == "Bash(git fetch:*)"


def test_git_worktree_collapses_to_subcommand(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "git worktree add -b x path ref"}})
    assert rec["fix"] == "Bash(git worktree:*)"


def test_single_word_command_gets_wildcard(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "tr a-z A-Z"}})
    assert rec["fix"] == "Bash(tr:*)"


def test_bare_command_uses_exact_form(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "pwd"}})
    assert rec["fix"] == "Bash(pwd)"  # no args -> exact, no :*


# --- Risk rating: the safety property ----------------------------------------

def test_safe_readonly_gets_allow_candidate(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "git fetch origin"}})
    assert rec["risk"] == "READONLY-ADDABLE"
    assert rec["fix"] == "Bash(git fetch:*)"


def test_safe_local_write_gets_allow_candidate(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "git commit -m wip"}})
    assert rec["risk"] == "WRITE-LOCAL"
    assert rec["fix"] == "Bash(git commit:*)"


def test_destructive_rm_is_rated_but_not_allowlisted(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "rm -rf build/"}})
    assert rec["risk"] == "DESTRUCTIVE"
    assert rec["fix"] == ""  # a one-off approval must NEVER become an allow rule


def test_force_push_is_destructive_no_candidate(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}})
    assert rec["risk"] == "DESTRUCTIVE"
    assert rec["fix"] == ""


def test_write_outward_not_allowlisted(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "gh pr create --fill"}})
    assert rec["risk"] == "WRITE-OUTWARD"
    assert rec["fix"] == ""


def test_code_exec_not_allowlisted(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "python3 scripts/foo.py"}})
    assert rec["risk"] == "CODE-EXEC"
    assert rec["fix"] == ""


def test_dual_use_net_not_allowlisted(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "curl https://example.com"}})
    assert rec["risk"] == "DUAL-USE-NET"
    assert rec["fix"] == ""


# --- Non-Bash tools ----------------------------------------------------------

def test_readonly_tool_rule_is_the_tool_name(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}})
    assert rec["fix"] == "Read"
    assert rec["risk"] == "READONLY-ADDABLE"
    assert "Read" in rec["signal"]


# --- Observe-only + fail-open contracts --------------------------------------

def test_observe_only_emits_no_stdout(tmp_path: Path):
    # A PermissionRequest hook that printed a decision on stdout could allow/deny
    # the prompt. This hook must emit NOTHING.
    proc, _ = _run(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "gh issue view 1"}})
    assert proc.stdout == ""


def test_empty_stdin_fails_open(tmp_path: Path):
    proc, log = _run(tmp_path, "")
    assert proc.returncode == 0
    assert _records(log) == []


def test_malformed_json_fails_open(tmp_path: Path):
    proc, log = _run(tmp_path, "not json {")
    assert proc.returncode == 0
    assert _records(log) == []


def test_missing_tool_name_fails_open(tmp_path: Path):
    proc, log = _run(tmp_path, {"tool_input": {"command": "ls"}})
    assert proc.returncode == 0
    assert _records(log) == []


def test_empty_bash_command_records_nothing(tmp_path: Path):
    proc, log = _run(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "   "}})
    assert proc.returncode == 0
    assert _records(log) == []
