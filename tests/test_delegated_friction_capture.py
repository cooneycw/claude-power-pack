"""Pin the parent capture procedure and its actual linked policy, not live logging."""

import shlex
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from tests.test_flow_friction_policy import section

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/delegated-friction-capture"
HEADING = "### Friction Capture (always-on, fail-open)"
START = "### Step 1: Start - Create Worktree"
LINK = "../flow/auto.md#friction-capture-always-on"
HELPER = "~/.claude/scripts/friction-log.sh"


def capture_contract(document: str, driver: str) -> bool:
    """Require the literal documented command and reachable canonical policy."""
    tokens = MarkdownIt("commonmark").parse(document)
    capture = section(tokens, HEADING.removeprefix("### "))
    start = section(tokens, START.removeprefix("### "))
    if capture is None or start is None or capture[0] >= start[0]:
        return False
    links = [child.attrGet("href") for token in capture[1] if token.type == "inline"
             for child in token.children or [] if child.type == "link_open"]
    if links.count(LINK) != 1:
        return False
    commands = [line.strip() for token in capture[1] if token.type == "fence" and token.info == "bash"
                for line in token.content.splitlines() if line.strip().startswith(HELPER)]
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
    return (anchor == "friction-capture-always-on"
            and section(MarkdownIt("commonmark").parse(policy), "Friction Capture (always-on)") is not None)


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
        assert not any(line.startswith(HELPER) for line in document.splitlines())
    elif case == "after-step-1":
        assert document.index(START) < document.index(HEADING)
    else:
        assert document.index(HEADING) < document.index(START)
        assert any(line.startswith(HELPER) for line in document.splitlines())
    assert capture_contract(document, "codex") is (case == "good")


def test_an_empty_document_never_establishes_capture() -> None:
    assert not capture_contract("", "codex")


def test_an_html_commented_driver_capture_is_not_active() -> None:
    document = (FIXTURES / "commented-capture.md").read_text()
    assert document.startswith("<!--\n")
    assert document.index("-->\n") < document.index(START)
    assert HELPER in document
    assert not capture_contract(document, "codex")


