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


def _run(
    tmp_path: Path, payload: dict | str, allow: list[str] | None = None
) -> tuple[subprocess.CompletedProcess[str], Path]:
    log = tmp_path / ".claude" / "friction.jsonl"
    env = os.environ.copy()
    env["CPP_FRICTION_LOG"] = str(log)
    # Hermetic allow-list for the #519 segment-walk: default empty so a test's
    # output never depends on the developer's real ~/.claude/settings.json. Pass
    # `allow` to exercise the "already-allowed leading segment is skipped" path.
    env["CENSUS_ALLOWLIST_JSON"] = json.dumps(allow or [])
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


def _one(tmp_path: Path, payload: dict, allow: list[str] | None = None) -> dict:
    proc, log = _run(tmp_path, payload, allow=allow)
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


def test_census_attributes_harness_claude(tmp_path: Path, monkeypatch):
    # #563: the census is a Claude Code PermissionRequest hook, so it stamps
    # harness=claude EXPLICITLY. Clear both env signals first to prove the tag
    # comes from the hook's own --harness claude, not friction-log.sh's
    # $CLAUDECODE default - so census rows attribute even outside a Claude shell.
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CPP_HARNESS", raising=False)
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "git fetch origin"}})
    assert rec["harness"] == "claude"


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


# --- Compound commands: candidate from the real driver (issue #519) ----------

def test_cd_prefix_is_stepped_over_to_the_real_command(tmp_path: Path):
    # The dominant flow shape: `cd $(...) && <real command>`. The candidate must
    # be the real command, NOT the already-allowed leading cd (that was 106 of
    # 109 useless Bash(cd:*) records in one retro).
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": 'cd "$(git rev-parse --show-toplevel)" && git commit -m wip'}})
    assert rec["fix"] == "Bash(git commit:*)"  # not Bash(cd:*)
    assert rec["risk"] == "WRITE-LOCAL"
    assert "cd " in rec["signal"]  # the signal still keeps the FULL command


def test_cd_prefix_then_outward_action_gets_no_candidate(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": "cd /repo && gh pr create --fill"}})
    assert rec["risk"] == "WRITE-OUTWARD"
    assert rec["fix"] == ""  # cd stepped over; the real driver is not allowlistable


def test_worst_risk_across_segments_wins(tmp_path: Path):
    # A safe leading segment must NOT mask a destructive later one, and any risky
    # segment blanks the candidate.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": "git commit -m wip && rm -rf build/"}})
    assert rec["risk"] == "DESTRUCTIVE"
    assert rec["fix"] == ""


def test_already_allowed_leading_segment_is_skipped(tmp_path: Path):
    # echo is already in the allow-list -> the candidate is the first NOT-allowed
    # driver, not the noise-header echo.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": 'echo "=== status ===" && git commit -m wip'}},
        allow=["Bash(echo:*)"])
    assert rec["fix"] == "Bash(git commit:*)"
    assert rec["risk"] == "WRITE-LOCAL"


def test_all_segments_allowed_falls_back_to_first(tmp_path: Path):
    # Degenerate case: every segment already allowed -> emit the first
    # substantive segment's own rule (pre-#519 behaviour), never crash.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": "git status && git diff"}},
        allow=["Bash(git status:*)", "Bash(git diff:*)"])
    assert rec["fix"] == "Bash(git status)"  # argless -> bare form; :* allow covers it
    assert rec["risk"] == "READONLY-AUTO"


def test_bare_cd_still_yields_its_own_candidate(tmp_path: Path):
    # A lone `cd DIR` prompt (no real driver behind it) should still suggest
    # Bash(cd:*) - the walk only steps OVER cd when a real command follows.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": "cd /some/dir"}})
    assert rec["fix"] == "Bash(cd:*)"
    assert rec["risk"] == "READONLY-ADDABLE"


def test_cd_then_allowed_command_does_not_resurrect_cd(tmp_path: Path):
    # cd + an already-allowed command: the fallback must NOT re-suggest the noise
    # cd; it surfaces the (allowed) real segment instead.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": "cd /repo && git status"}},
        allow=["Bash(git status:*)"])
    assert rec["fix"] == "Bash(git status)"
    assert rec["risk"] == "READONLY-AUTO"


def test_pipeline_is_a_segment_boundary(tmp_path: Path):
    # A pipe splits segments too: `grep ... | wc -l` with grep allowed surfaces wc.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": "grep -c foo file | wc -l"}},
        allow=["Bash(grep:*)"])
    assert rec["fix"] == "Bash(wc:*)"
    assert rec["risk"] == "READONLY-ADDABLE"


# --- Never-allowlist policy (issue #598) -------------------------------------
#
# /self-improvement:retro Step 4 tells the retro to trust the `fix` field and
# states that the census "already withholds a fix" for rules that would defeat a
# gate. These cases turn that stated invariant into an enforced one.

# File-dumpers: an allow rule for any of them defeats the PostToolUse masking
# hook on a secret file (`head -20 .env` leaks exactly as `cat .env` does).
FILE_DUMPERS = [
    "cat", "head", "tail", "less", "more", "tac", "nl",
    "strings", "xxd", "od", "hexdump", "base64",
]


@pytest.mark.parametrize("exe", FILE_DUMPERS)
def test_file_dumpers_never_yield_an_allow_candidate(tmp_path: Path, exe: str):
    # The record is still WRITTEN with its (truthful, read-only) tier - the
    # census keeps its signal; only the forbidden rule is withheld.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": f"{exe} .env"}})
    assert rec["fix"] == ""
    assert rec["risk"] == "READONLY-ADDABLE"
    assert exe in rec["signal"]


def test_file_dumper_driving_a_pipeline_still_withholds(tmp_path: Path):
    # `cat` is the segment that drove the prompt; the walk must not fall through
    # to grep and emit a candidate as though cat were never there.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": "cat .env | grep TOKEN"}})
    assert rec["fix"] == ""


def test_allowlisted_file_dumper_does_not_mask_the_real_driver(tmp_path: Path):
    # Withholding is applied at EMISSION, not in the coverage walk: a `cat`
    # segment the user already allowlisted is still stepped over, so the
    # candidate remains the real driver behind the prompt.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {
        "command": "cat notes.txt && git commit -m wip"}},
        allow=["Bash(cat:*)"])
    assert rec["fix"] == "Bash(git commit:*)"


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/repo status",        # flag before the verb
        "git --no-pager log --oneline",
        "gh -R owner/repo issue list",
        "docker -H tcp://host:2375 ps",
    ],
)
def test_bare_tool_namespace_is_never_emitted(tmp_path: Path, command: str):
    # `Bash(git:*)` would silently permit `git push` and `git reset --hard`.
    # When no subcommand can be derived the candidate is withheld, not widened -
    # a narrow rule could not match a flag-bearing invocation anyway, since allow
    # rules match a command PREFIX.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": command}})
    exe = command.split()[0]
    assert rec["fix"] not in (f"Bash({exe})", f"Bash({exe}:*)")
    assert rec["fix"] == ""


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git status --short", "Bash(git status:*)"),
        ("git worktree list", "Bash(git worktree:*)"),
        ("gh issue view 598", "Bash(gh issue view:*)"),
        ("docker ps -a", "Bash(docker ps:*)"),
        ("pwd", "Bash(pwd)"),
        ("wc -l file", "Bash(wc:*)"),
    ],
)
def test_subcommand_granular_candidates_still_emitted(
    tmp_path: Path, command: str, expected: str
):
    # Regression floor for #598: the policy withholds two specific classes and
    # must not blunt ordinary derivation.
    rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert rec["fix"] == expected


def test_no_forbidden_rule_survives_a_mixed_corpus(tmp_path: Path):
    # Belt-and-braces: run a corpus through the hook and assert the whole set of
    # emitted candidates is free of every rule the retro spec forbids.
    forbidden = {f"Bash({e}:*)" for e in FILE_DUMPERS} | {
        "Bash(git:*)", "Bash(gh:*)", "Bash(docker:*)",
        "Bash(git push:*)", "Bash(gh pr create:*)", "Bash(gh pr merge:*)",
    }
    corpus = [
        "cat .env", "head -5 secrets.yml", "tail -n 2 .env.local",
        "git -C /repo status", "git push origin main", "gh pr create --fill",
        "gh pr merge 12 --squash", "docker -H tcp://h ps", "less /etc/passwd",
        "cd /repo && cat .env", "git status && cat .env",
    ]
    emitted = set()
    for command in corpus:
        rec = _one(tmp_path, {"tool_name": "Bash", "tool_input": {"command": command}})
        if rec["fix"]:
            emitted.add(rec["fix"])
        # Every record is still captured - withholding a rule never drops signal.
        assert rec["signal"]
        (tmp_path / ".claude" / "friction.jsonl").unlink()
    assert emitted & forbidden == set(), sorted(emitted & forbidden)


# --- Non-Bash tools ----------------------------------------------------------

def test_readonly_tool_rule_is_the_tool_name(tmp_path: Path):
    rec = _one(tmp_path, {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}})
    assert rec["fix"] == "Read"
    assert rec["risk"] == "READONLY-ADDABLE"
    assert "Read" in rec["signal"]


# --- Inherently-interactive tools are NOT permission friction (issue #542) ----

@pytest.mark.parametrize(
    "tool", ["AskUserQuestion", "Skill", "EnterPlanMode", "ExitPlanMode"]
)
def test_interactive_tools_record_nothing(tmp_path: Path, tool: str):
    # AskUserQuestion/Skill/EnterPlanMode/ExitPlanMode raise a PermissionRequest
    # but are user-interaction dialogs, not permission friction: they can never be
    # allowlisted and only inflate the friction buffer + the SessionStart nag. The
    # census must skip them entirely (fail-open, no record).
    proc, log = _run(tmp_path, {"tool_name": tool, "tool_input": {}})
    assert proc.returncode == 0
    assert proc.stdout == ""  # observe-only contract still holds
    assert _records(log) == []


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
