"""Pin the documented prefix/precedence contract used by init (Refs #1586).

Source: https://code.claude.com/docs/en/permissions.md, retrieved 2026-10-28.
This reference evaluator covers literal prefixes and the simple compound
commands committed here. It does not execute commands or replace Claude Code's
shell parser, wrapper handling, permission modes, or other settings layers.
"""

import json
import re
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"
FIXTURE = json.loads((ROOT / "tests/fixtures/cpp-init-trusted-yolo/cases.json").read_text())
CASES = FIXTURE["commands"]
ASK_CASES = [case for case in CASES if case["trusted"] == "ask"]
ASK_RULES = {case["ask_rule"] for case in CASES}


def _profile(name):
    match = re.search(rf"\*\*{name} Profile:\*\*\s*```json\n(.*?)```", INIT.read_text(), re.S)
    assert match, f"missing {name} profile JSON"
    return json.loads(match[1])["permissions"]


def _matches(rule, command):
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    pattern = rule[5:-1]
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    if pattern.endswith(" *") and pattern.count("*") == 1 and command == pattern[:-2]:
        return True
    # Only * is a wildcard; the rest is literal text, including quoted words.
    return re.fullmatch(re.escape(pattern).replace(r"\*", ".*"), command) is not None



def _subcommands(command):
    # Keep quoted tokens quoted: git 'push' is a documented alternate form,
    # so normalizing it to git push would claim coverage the rule lacks.
    lexer = shlex.shlex(command, posix=False, punctuation_chars=";&|")
    lexer.whitespace_split = True
    parts, current = [], []
    for token in lexer:
        if token in {"&&", "||", ";", "|", "|&", "&"}:
            assert current, "fixture must contain parseable subcommands"
            parts.append(" ".join(current))
            current = []
        else:
            current.append(token)
    assert current, "fixture must not end with an empty subcommand"
    return parts + [" ".join(current)]


def _decision(permissions, command):
    commands = _subcommands(command)
    for verdict in ("deny", "ask"):
        if any(_matches(rule, part) for rule in permissions.get(verdict, []) for part in commands):
            return verdict
    # The sole cd fixture stays inside the working directory; the docs
    # classify that as read-only. Unknown commands in Manual mode prompt.
    if all(
        part == "cd subdir" or any(_matches(rule, part) for rule in permissions.get("allow", []))
        for part in commands
    ):
        return "allow"
    return "ask"


def _assert_prompts(permissions, command):
    assert _decision(permissions, command) == "ask", command


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["command"])
def test_trusted_protects_the_enumerated_invocations(case):
    assert _decision(_profile("Trusted"), case["command"]) == case["trusted"]


def test_trusted_preserves_its_original_lists_and_adds_ask_exceptions():
    permissions = _profile("Trusted")
    assert ASK_RULES <= set(permissions.get("ask", []))
    assert ASK_RULES.isdisjoint(permissions["allow"])
    assert permissions["allow"] == FIXTURE["original_trusted"]["allow"]
    assert permissions["deny"] == FIXTURE["original_trusted"]["deny"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["command"])
def test_yolo_matches_the_disclosed_original_trusted_policy(case):
    assert _decision(_profile("YOLO"), case["command"]) == case["yolo"]


def test_yolo_is_exactly_the_original_trusted_preset():
    assert _profile("YOLO") == FIXTURE["original_trusted"]


@pytest.mark.parametrize(
    "command",
    ["git status", "git add file.py", "gh issue list", "gh pr create", "git commit -m fix",
     "git commit -a -m update", "git branch", "git branch feature", "git branch --show-current",
     "git branch -m source target", "git branch -c source target"],
)
def test_trusted_keeps_other_git_and_github_approvals(command):
    assert _decision(_profile("Trusted"), command) == "allow"


@pytest.mark.parametrize("case", ASK_CASES, ids=lambda case: case["command"])
def test_leaked_ask_rule_is_a_known_bad_case(case):
    permissions = _profile("Trusted")
    assert case["ask_rule"] in permissions.get("ask", []), "fixture requires the live ask rule"
    permissions["ask"].remove(case["ask_rule"])
    permissions["allow"].append(case["ask_rule"])
    assert case["ask_rule"] not in permissions["ask"]
    assert _decision(permissions, case["command"]) == "allow", "fixture must leak before checking the guard"
    with pytest.raises(AssertionError):
        _assert_prompts(permissions, case["command"])


def test_flag_prefix_leaks_when_the_flag_follows_operands():
    permissions = _profile("Trusted")
    assert "Bash(git push:*)" in permissions.get("ask", [])
    permissions["ask"].remove("Bash(git push:*)")
    permissions["ask"].append("Bash(git push --force:*)")
    command = "git push origin main --force"
    assert not _matches("Bash(git push --force:*)", command)
    assert _decision(permissions, command) == "allow"
    with pytest.raises(AssertionError):
        _assert_prompts(permissions, command)


def test_ask_precedes_even_a_more_specific_allow_and_deny_precedes_ask():
    command = "git push origin main --force"
    permissions = {"allow": [f"Bash({command})"], "ask": ["Bash(git push:*)"]}
    assert _decision(permissions, command) == "ask"
    permissions["deny"] = [f"Bash({command})"]
    assert _decision(permissions, command) == "deny"


@pytest.mark.parametrize(
    "command,expected",
    [
        ("git -C . push origin main --force", "allow"),
        ("git -c push.default=current push origin main --force", "allow"),
        ("git 'push' origin main --force", "allow"),
        ("/usr/bin/git push origin main --force", "ask"),
        ("sh -c 'git push origin main --force'", "ask"),
        ('python -c "import os; os.system(\'git push origin main -f\')"', "allow"),
    ],
)
def test_documented_alternate_forms_are_outside_this_ask_list(command, expected):
    permissions = _profile("Trusted")
    assert not any(_matches(rule, command) for rule in permissions.get("ask", []))
    assert _decision(permissions, command) == expected


@pytest.mark.parametrize("profile", ["Trusted", "YOLO"])
def test_system_deny_still_applies(profile):
    assert _decision(_profile(profile), "rm -rf /") == "deny"


def test_yolo_is_a_separate_explicit_choice_and_never_default_or_recommended():
    text = INIT.read_text()
    assert "**Standard Profile (Default):**" in text
    assert "**YOLO Profile:**" in text
    assert "YOLO is never the default and is never recommended" in text
    assert "Keep Trusted (default)" in text
    assert "YOLO (explicit opt-in)" in text
    section = text.split("### YOLO Disclosure", 1)[1].split("### Custom Mode Categories", 1)[0]
    for phrase in (
        "git push", "--force", "--force-with-lease", "git reset", "--hard", "git clean", "-f",
        "git branch", "-D", "-M", "-C", "git commit", "--amend", "git rebase", "git filter-branch", "git filter-repo",
        "git replace", "git update-ref", "gh repo delete", "gh repo archive", "gh pr merge",
        "gh issue delete", "gh release delete", "gh api", "-X DELETE",
    ):
        assert phrase in section, f"YOLO must disclose {phrase} before confirmation"
    assert "Proceed? [y/N]" in section
