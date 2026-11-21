"""Pin flow:auto's own friction policy; CommonMark owns visible document structure."""

from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/delegated-friction-capture"


def plain_text(tokens: list[Token]) -> str:
    """Visible inline text only; HTML comments cannot supply obligations."""
    return " ".join("".join(child.content if child.type in {"text", "code_inline"} else
                            " " if child.type in {"softbreak", "hardbreak"} else ""
                            for child in token.children or [])
                    for token in tokens if token.type == "inline")


def section(tokens: list[Token], title: str) -> tuple[int, list[Token]] | None:
    headings = [index for index, token in enumerate(tokens[:-1])
                if token.type == "heading_open" and plain_text([tokens[index + 1]]) == title]
    if len(headings) != 1:
        return None
    heading = headings[0]
    rank = int(tokens[heading].tag[1:])
    start = heading + 3  # heading_open, inline, heading_close
    end = next((index for index in range(start, len(tokens))
                if tokens[index].type == "heading_open" and int(tokens[index].tag[1:]) <= rank), len(tokens))
    return heading, tokens[start:end]


def canonical_friction_policy(policy: str) -> bool:
    found = section(MarkdownIt("commonmark").parse(policy), "Friction Capture (always-on)")
    if found is None:
        return False
    rule = " ".join(plain_text(found[1]).split())
    return all(instruction in rule for instruction in (
        "the moment it happens", "every step, success OR failure", "before any STOP",
        "quality-gate failure or retry", "red output", "manual intervention / correction",
        "Never log the permission-prompt class by hand", "Missing helper: skip capture",
        "Capture only", "fixes are proposed and applied in the retro",
    ))


def test_flow_auto_pins_its_own_friction_obligations() -> None:
    policy = (ROOT / ".claude/commands/flow/auto.md").read_text()
    assert canonical_friction_policy(policy)


def test_inline_markup_cannot_invent_spaces_in_a_heading_title() -> None:
    tokens = MarkdownIt("commonmark").parse("### Friction**Capture**(always-on)\n")
    assert tokens[1].children and any(child.type == "strong_open" for child in tokens[1].children)
    assert section(tokens, "Friction Capture (always-on)") is None


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



def test_a_literal_comment_opener_in_an_example_does_not_hide_the_policy() -> None:
    policy = (FIXTURES / "policy-literal-comment.md").read_text()
    assert policy.startswith("```text\n<!--\n```\n")
    assert policy.index("```\n") < policy.index("### Friction Capture (always-on)")
    assert canonical_friction_policy(policy)

