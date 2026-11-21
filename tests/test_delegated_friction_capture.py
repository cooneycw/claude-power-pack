"""Pin the parent capture procedure and its actual linked policy, not live logging."""

import re
import shlex
from pathlib import Path

import pytest

from tests.test_delegated_plan_finish import bash_blocks

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/delegated-friction-capture"
HEADING = "### Friction Capture (always-on, fail-open)"
START = "### Step 1: Start - Create Worktree"
LINK = "../flow/auto.md#friction-capture-always-on"
HELPER = "~/.claude/scripts/friction-log.sh"


def canonical_friction_policy(policy: str) -> bool:
    """Check this canonical source's ATX-heading, comment and fence forms."""
    policy = re.sub(r"<!--.*?(?:-->|\Z)", "", policy, flags=re.DOTALL)
    policy_heading = "### Friction Capture (always-on)"
    visible = []
    fence: tuple[str, int] | None = None
    for line in policy.splitlines():
        mark = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if mark:
                fence = (mark[1][0], len(mark[1]))
            else:
                visible.append(line)
        elif mark and mark[1][0] == fence[0] and len(mark[1]) >= fence[1] and not mark[2].strip():
            fence = None
    headings = [index for index, line in enumerate(visible) if line.rstrip() == policy_heading]
    if len(headings) != 1:
        return False
    start = headings[0] + 1
    end = next((index for index in range(start, len(visible))
                if re.match(r"^ {0,3}#{1,3}(?:[ \t]+|$)", visible[index])), len(visible))
    rule = "\n".join(visible[start:end])
    rule = " ".join(rule.replace("**", "").split())
    return all(instruction in rule for instruction in (
        "the moment it happens", "every step, success OR failure", "before any STOP",
        "quality-gate failure or retry", "red output", "manual intervention / correction",
        "Never log the permission-prompt class by hand", "Missing helper: skip capture",
        "Capture only", "fixes are proposed and applied in the retro",
    ))


def capture_contract(document: str, driver: str) -> bool:
    """Require the literal documented command and reachable canonical policy."""
    if document.count(HEADING) != 1 or START not in document:
        return False
    if document.index(HEADING) > document.index(START):
        return False
    capture = document.split(HEADING, 1)[1].split(START, 1)[0]
    prose = " ".join(capture.split())
    for instruction in (
        f"[/flow:auto's friction rule]({LINK})",
        "Parent:", "every step, before STOP",
        "Classes: gate-failure, red-output, manual-intervention",
        "never log permission-prompt by hand",
        "Missing helper: continue",
        "Substitute assigned issue for 42",
        "Capture only; retro fixes",
    ):
        if instruction not in prose:
            return False
    commands = [line for block in bash_blocks(capture) for _, line in block if line.startswith(HELPER)]
    if len(commands) != 1:
        return False
    words = shlex.split(commands[0])
    expected = {
        "--class": "<class>", "--signal": "<signal>",
        "--run": f"{driver}:auto #42", "--step": "<N/8 Name>",
    }
    if len(words) != 1 + 2 * len(expected) or words[0] != HELPER:
        return False
    if dict(zip(words[1::2], words[2::2], strict=True)) != expected:
        return False

    # Read the real referenced file relative to the actual generated command.
    command = ROOT / f".claude/commands/{driver}/auto.md"
    target, anchor = LINK.split("#")
    policy_file = (command.parent / target).resolve()
    if policy_file != (ROOT / ".claude/commands/flow/auto.md").resolve():
        return False
    policy = policy_file.read_text()
    return anchor == "friction-capture-always-on" and canonical_friction_policy(policy)


@pytest.mark.parametrize("driver", ("codex", "qwen", "gemma"))
def test_actual_driver_imports_friction_policy_before_any_step(driver: str) -> None:
    document = (ROOT / f".claude/commands/{driver}/auto.md").read_text()
    assert capture_contract(document, driver), f"{driver}: missing parent capture before Step 1"


@pytest.mark.parametrize("case", ("good", "missing-call", "commented-call", "after-step-1"))
def test_committed_driver_capture_cases(case: str) -> None:
    document = (FIXTURES / f"{case}.md").read_text()
    if case == "missing-call":
        assert HELPER not in document
    elif case == "commented-call":
        assert "# " + HELPER in document
        assert not any(line.startswith(HELPER) for block in bash_blocks(document) for _, line in block)
    elif case == "after-step-1":
        assert document.index(START) < document.index(HEADING)
    else:
        assert document.index(HEADING) < document.index(START)
        assert any(line.startswith(HELPER) for block in bash_blocks(document) for _, line in block)
    assert capture_contract(document, "codex") is (case == "good")


def test_an_empty_document_never_establishes_capture() -> None:
    assert not capture_contract("", "codex")


def test_renamed_policy_heading_cannot_establish_the_link_anchor() -> None:
    policy = (FIXTURES / "policy-renamed-heading.md").read_text()
    heading = "### Friction Capture (always-on)"
    assert heading in policy
    assert heading not in policy.splitlines()
    assert heading + " archived" in policy.splitlines()
    assert not canonical_friction_policy(policy)


def test_a_fenced_policy_heading_is_not_an_active_anchor() -> None:
    policy = (ROOT / ".claude/commands/flow/auto.md").read_text()
    example = f"````markdown\n{policy}\n````\n"
    assert example.startswith("````markdown\n")
    assert "### Friction Capture (always-on)" in example
    assert not canonical_friction_policy(example)


def test_an_html_commented_policy_has_no_active_anchor() -> None:
    policy = (FIXTURES / "policy-html-comment.md").read_text()
    assert policy.startswith("<!--\n") and policy.endswith("-->\n")
    assert "### Friction Capture (always-on)" in policy
    assert not canonical_friction_policy(policy)


def test_a_sibling_section_cannot_supply_the_friction_policy() -> None:
    policy = (FIXTURES / "policy-sibling-section.md").read_text()
    assert policy.startswith("### Friction Capture (always-on)\n### Another section\n")
    assert "the moment it happens" in policy.split("### Another section", 1)[1]
    assert not canonical_friction_policy(policy)
