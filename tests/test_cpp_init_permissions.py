"""The init profiles must ask before GitHub issue mutations (Refs #1586)."""

import json
import re
from pathlib import Path

import pytest

INIT = Path(__file__).resolve().parents[1] / ".claude/commands/cpp/init.md"
READ_GITHUB_RULES = {
    "Bash(gh issue list:*)", "Bash(gh issue view:*)", "Bash(gh pr list:*)", "Bash(gh pr view:*)"
}


@pytest.mark.parametrize("profile", ["Cautious", "Standard", "Trusted"])
def test_profile_issue_permissions_are_read_only(profile):
    text = INIT.read_text()
    match = re.search(rf"\*\*{profile} Profile(?: \(Default\))?:\*\*\s*```json\n(.*?)```", text, re.S)
    assert match, f"missing {profile} profile JSON"
    rules = json.loads(match[1])["permissions"]["allow"]
    # Validate all GitHub rules: a broad root or PR namespace would otherwise
    # bypass the same confirmation boundary without naming issue mutations.
    gh_rules = {rule for rule in rules if rule.startswith("Bash(gh")}
    assert gh_rules <= READ_GITHUB_RULES, f"{profile} grants GitHub writes: {gh_rules - READ_GITHUB_RULES}"
    if profile != "Cautious":
        assert gh_rules == READ_GITHUB_RULES, f"{profile} must still auto-approve GitHub reads"



def test_custom_read_category_names_only_read_verbs():
    text = INIT.read_text()
    match = re.search(r"^\| \*\*GitHub CLI \(read\)\*\* \| ([^|]+) \|", text, re.M)
    assert match, "missing Custom GitHub CLI read category"
    assert {verb.strip() for verb in match[1].split(",")} == {
        "gh issue list", "gh issue view", "gh pr list", "gh pr view"
    }


@pytest.mark.parametrize(
    "bad_rule",
    ["Bash(gh:*)", "Bash(gh issue:*)", "Bash(gh pr:*)", "Bash(gh pr merge:*)"]
    + [
        f"Bash(gh issue {verb}:*)"
        for verb in ("create", "close", "delete", "edit", "transfer", "lock", "reopen", "comment")
    ],
)
def test_issue_permission_guard_rejects_write_rules(tmp_path, monkeypatch, bad_rule):
    text = INIT.read_text()
    original = '"Bash(gh issue list:*)"'
    assert original in text, "fixture requires the shipped Standard read rule"
    poisoned = text.replace(original, original + ", " + json.dumps(bad_rule), 1)
    assert all(json.dumps(rule) in poisoned for rule in READ_GITHUB_RULES)
    assert json.dumps(bad_rule) in poisoned
    fixture = tmp_path / "init.md"
    fixture.write_text(poisoned)
    monkeypatch.setitem(globals(), "INIT", fixture)
    with pytest.raises(AssertionError):
        test_profile_issue_permissions_are_read_only("Standard")
