"""What each deny rule in /cpp:init's Trusted and YOLO profiles matches (issue #1716).

`Bash(dd if=:*)` advertised a protection it did not give: it matches only
`dd if=` followed by a SPACE, and nobody types that. `Bash(mkfs:*)` had the
same defect for `mkfs.ext4`.

THE MATCHER HERE IS A STAND-IN. Claude Code's own permission matcher cannot be
run from a test, so `matches()` below is written from two sentences of the
Claude Code permissions documentation
(https://code.claude.com/docs/en/permissions, "Wildcard patterns"):

    "The `:*` suffix is an equivalent way to write a trailing wildcard, so
    `Bash(ls:*)` matches the same commands as `Bash(ls *)`."

    "`Bash(ls *)` requires a space after `ls`, so `lsof` doesn't match."

and its statement that "A `*` in a Bash rule matches any text, including
spaces". The real matcher was NOT run. If this reading of the documentation is
wrong, every test here passes and the rules protect nothing; what these tests
do establish is that the rules say what we think the documentation says they
say, and that nobody changes one without seeing which commands move.

A deny rule is also not a boundary, in the documentation's own words: "It
doesn't match the same program invoked in a different form, so a deny or ask
rule covers the invocation Claude usually produces and isn't a security
boundary around the program." The cases marked `False` below pin that too.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / ".claude" / "commands" / "cpp" / "init.md"


def matches(rule: str, command: str) -> bool:
    """Does `Bash(<pattern>)` match `command`, per the documented semantics above?"""
    inner = re.fullmatch(r"Bash\((.*)\)", rule)
    assert inner, f"not a Bash rule: {rule}"
    pattern = inner.group(1)
    if pattern.endswith(":*"):  # documented as equivalent to a trailing " *"
        pattern = pattern[:-2] + " *"
    if pattern.endswith(" *"):  # the prefix alone, or the prefix, a space, then anything
        prefix = _to_regex(pattern[:-2])
        return re.fullmatch(prefix + r"(?: .*)?", command, re.DOTALL) is not None
    return re.fullmatch(_to_regex(pattern), command, re.DOTALL) is not None


def _to_regex(pattern: str) -> str:
    return ".*".join(re.escape(part) for part in pattern.split("*"))


def deny_lists() -> list[list[str]]:
    """The `deny` array of every JSON settings block in the document that has one with a `dd` rule."""
    text = DOCUMENT.read_text(encoding="utf-8")
    found = []
    for block in re.findall(r"```json\n(.*?)\n```", text, re.DOTALL):
        try:
            deny = json.loads(block).get("permissions", {}).get("deny")
        except (json.JSONDecodeError, AttributeError):
            continue
        if deny and any(rule.startswith("Bash(dd") for rule in deny):
            found.append(deny)
    return found


def test_the_matcher_agrees_with_the_documentations_own_examples() -> None:
    """The stand-in's only anchor: the cases the documentation itself states."""
    assert matches("Bash(ls *)", "ls -la")
    assert matches("Bash(ls *)", "ls")
    assert not matches("Bash(ls *)", "lsof")
    assert matches("Bash(ls*)", "ls -la")
    assert matches("Bash(ls*)", "lsof")
    assert matches("Bash(ls:*)", "ls -la") and not matches("Bash(ls:*)", "lsof")


def test_both_profiles_carry_a_deny_list_and_they_are_the_same() -> None:
    lists = deny_lists()
    assert len(lists) == 2, f"expected the Trusted and YOLO deny lists, found {len(lists)}"
    assert lists[0] == lists[1], "YOLO is documented as using Trusted's deny list exactly"


#: (command, the rule expected to decide it, whether ANY deny rule must match)
CASES = [
    # seq 623: the rule that did not match the command it names
    ("dd if=/dev/zero of=/dev/sda", "Bash(dd if=*)", True),
    ("dd if=disk.img of=/dev/sdb bs=4M", "Bash(dd if=*)", True),
    # found beside it: mkfs.<type> is the form people type
    ("mkfs.ext4 /dev/sda1", "Bash(mkfs*)", True),
    ("mkfs -t ext4 /dev/sda1", "Bash(mkfs*)", True),
    # the three rm -rf rules match the bare path only; pinned, deliberately not widened
    ("rm -rf /", "Bash(rm -rf /:*)", True),
    ("rm -rf / --no-preserve-root", "Bash(rm -rf /:*)", True),
    ("rm -rf ~", "Bash(rm -rf ~:*)", True),
    ("rm -rf /home", "Bash(rm -rf /home:*)", True),
    ("rm -rf /etc", None, False),
    ("rm -rf ~/project/build", None, False),
    ("rm -rf /home/someone", None, False),
    ("rm -rf ./build", None, False),
    ("git push --force origin main", "Bash(git push --force origin main:*)", True),
    ("git push --force origin master", "Bash(git push --force origin master:*)", True),
    ("git push --force origin feature", None, False),
    ("sudo rm -rf /var/tmp/x", "Bash(sudo rm:*)", True),
    ("sudo rmdir /var/tmp/x", None, False),
    # NOT a boundary: the same program in another form is not matched, as documented
    ("dd of=/dev/sda if=/dev/zero", None, False),
    ("/usr/bin/dd if=/dev/zero of=/dev/sda", None, False),
    ("sudo mkfs.ext4 /dev/sda1", None, False),
    ("git push -f origin main", None, False),
    # ordinary work that must stay undenied
    ("ddrescue /dev/sda image.img", None, False),
    ("ls -la", None, False),
]


@pytest.mark.parametrize(("command", "rule", "denied"), CASES)
def test_each_deny_rule_matches_what_it_names_and_nothing_else(command: str, rule: str | None, denied: bool) -> None:
    for deny in deny_lists():
        hits = [r for r in deny if matches(r, command)]
        assert bool(hits) == denied, f"{command!r}: matched by {hits}"
        if rule is not None:
            assert rule in deny, f"{rule} is not in the deny list"
            assert rule in hits, f"{command!r} is denied, but not by {rule}: {hits}"


def test_the_old_spellings_did_not_match_the_commands_they_named() -> None:
    """The defect itself, by the same matcher: why the two rules were respelled."""
    assert not matches("Bash(dd if=:*)", "dd if=/dev/zero of=/dev/sda")
    assert not matches("Bash(mkfs:*)", "mkfs.ext4 /dev/sda1")
    for deny in deny_lists():
        assert "Bash(dd if=:*)" not in deny and "Bash(mkfs:*)" not in deny


def test_the_wizard_does_not_call_the_deny_list_a_boundary() -> None:
    text = re.sub(r"\s+", " ", DOCUMENT.read_text(encoding="utf-8"))
    assert "while blocking dangerous commands" not in text
    assert "**A deny rule is not a boundary**" in text
    assert "use sandboxing for enforcement" in text


def test_a_profile_installed_before_the_respelling_is_no_longer_recognised(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A reader of the changed lists: init's own permission observer.

    It names a project's profile by comparing its settings file with the
    document. A Trusted file written before #1716 carries the two old
    spellings, so it now reads as unverified: accurate, and the cue to re-run
    the wizard. Pinned so the consequence is a known one.
    """
    from tests.test_cpp_init_profile_summary import CASES as OBSERVER_CASES
    from tests.test_cpp_init_profile_summary import _observe

    current = next(case for case in OBSERVER_CASES if case["name"] == "trusted")
    settings = tmp_path / "settings.local.json"
    settings.write_text(json.dumps(current["settings"]))
    code, report = _observe(monkeypatch, settings)
    assert code == 0 and report["verified"] is True  # the precondition: today's profile is recognised

    old = json.loads(json.dumps(current["settings"]))
    deny = old["permissions"]["deny"]
    assert "Bash(dd if=*)" in deny and "Bash(mkfs*)" in deny
    old["permissions"]["deny"] = [
        {"Bash(dd if=*)": "Bash(dd if=:*)", "Bash(mkfs*)": "Bash(mkfs:*)"}.get(rule, rule) for rule in deny
    ]
    settings.write_text(json.dumps(old))
    code, report = _observe(monkeypatch, settings)
    assert code == 3 and report["verified"] is False
