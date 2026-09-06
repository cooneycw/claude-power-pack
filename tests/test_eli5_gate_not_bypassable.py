"""Pin: the ELI5 gate has no bypass (issue #775).

`/flow:auto`'s Step 3 is the only checkpoint between reading an issue and writing
code - everything after it reviews a diff that already exists - and it could be
skipped three ways: `--yes`, its `--auto-approve` alias, and an
`eli5: auto-approve` trailer read from the issue body or the HEAD commit message.

The trailer was the channel no invoker controlled. An issue body is written by
whoever filed the issue (in a fleet, routinely another agent); and on a worktree
freshly branched off main, HEAD *is* main's tip commit, written by whoever merged
last. One merged commit carrying the trailer disarmed the gate for every later run
branched from that tip, across unrelated issues and unrelated sessions. It was not
hypothetical: when #775 was filed, both `dbf72bf` (main's tip - the commit that
declined to propagate the trailer to the delegated drivers) and the body of #775
itself contained the literal string, so the run that fixed this would have been
auto-approved on two channels at once.

The flags went with it under one structural argument that covers all three: a
bypass is chosen before Section C exists, so it can never be an approval *of* the
plan - only standing consent to whatever plan the run later produces. `--yes` and
`--auto-approve` are still recognized, and refused out loud; the trailer is not
read at all; and `auto-granted` left the report vocabulary, because a field that
can still be produced means something can still skip the gate.

These are prompt documents, so the document is the enforceable layer. The rule
lives in eli5.md's VENDORED CORE (canonical: cooneycw/eli5-gate), so it is the
gate's own behavior rather than a CPP-local override - `test_the_rule_lives_in_the_vendored_core`
is what keeps that true through a future re-vendor.

Verified non-vacuous: run against the pre-change tree (`git show HEAD~1:...`),
every test below fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"
FLOW = COMMANDS / "flow"

#: The surfaces that describe the ELI5 gate itself. A bypass reintroduced in any
#: of them is a reachable bypass.
GATE_SURFACES = ("eli5.md", "auto.md", "auto_codex.md", "help.md")

#: Every removed channel, as it would appear if someone reinstated it.
BYPASS_TOKENS = ("--yes", "--auto-approve", "eli5: auto-approve")

#: Words that mark a mention as a refusal rather than a grant. A block naming a
#: bypass token must carry one of these, so the tokens can stay NAMED (a future
#: editor should reinstate one deliberately, not by accident) without any of them
#: being honored.
REFUSAL = re.compile(
    r"\b(?:no|not|never|nor|none|cannot|refus\w*|forbid\w*|remov\w*|"
    r"skippable|unconditional\w*|prohibit\w*|reject\w*)\b",
    re.IGNORECASE,
)

#: Phrases that describe a bypass actually working. A refusal word alone is too
#: weak a signal - the pre-#775 text said "to proceed without pausing" and
#: "Auto-approve never overrides a `No longer needed` verdict" in the SAME
#: paragraph, so a negation belonging to a different clause would have vouched
#: for a live bypass. This is the #772 lesson (a stray `not` must not speak for
#: an unrelated claim) applied to the gate: naming a channel is allowed, but
#: describing it as functional is not, whatever else the block happens to say.
GRANT = re.compile(
    r"proceed(?:s|ing)?\s+without\s+pausing"
    r"|skip(?:s|ping)?\s+(?:the|its|that)\s+[\w\s]{0,30}?pause"
    r"|approval\s+was\s+auto-granted"
    r"|note\s+auto-approval"
    r"|unless\s+invoked\s+with"
    r"|for\s+unattended\s+runs?,?\s+(?:accept|use|pass|add|run)"
    r"|(?:or\s+)?add\s+an?\s+.{0,40}?trailer"
    r"|accept\s+`--yes`",
    re.IGNORECASE,
)

BEGIN_MARKER = "<!-- eli5-core:begin"
END_MARKER = "<!-- eli5-core:end"


def _read(name: str) -> str:
    return (FLOW / name).read_text(encoding="utf-8")


def _blocks(text: str) -> list[str]:
    """Split markdown into the smallest unit a claim can reasonably span.

    A block is a blank-line-delimited paragraph, except that a top-level bullet
    starts a new one - so "- `--yes`: refused" is judged on its own words and
    cannot borrow a negation from an unrelated neighbouring bullet. Indented
    continuation lines stay with their bullet.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        starts_bullet = re.match(r"^[-*+] |^\d+\. ", line) is not None
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        if starts_bullet and current:
            blocks.append(current)
            current = []
        current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(b) for b in blocks]


def _blocks_naming(text: str, token: str) -> list[str]:
    return [b for b in _blocks(text) if token in b]


def _core(text: str) -> str:
    """The vendored eli5-core section, anchored at line starts like the vendor guard."""
    lines = text.splitlines(keepends=True)
    start = end = None
    for i, line in enumerate(lines):
        if start is None and line.startswith(BEGIN_MARKER):
            start = i + 1
        elif start is not None and line.startswith(END_MARKER):
            end = i
            break
    assert start is not None and end is not None, "eli5.md lost its eli5-core markers"
    return "".join(lines[start:end])


# --- the removed channels ----------------------------------------------------


@pytest.mark.parametrize("surface", GATE_SURFACES)
@pytest.mark.parametrize("token", BYPASS_TOKENS)
def test_no_gate_surface_grants_a_bypass(surface: str, token: str) -> None:
    """Naming a bypass is fine; granting one is not."""
    for block in _blocks_naming(_read(surface), token):
        grant = GRANT.search(block)
        assert not grant, (
            f"flow/{surface}: '{token}' is described as working ({grant.group(0)!r}) - that is a "
            f"live bypass of the ELI5 gate (issue #775):\n\n{block}"
        )
        assert REFUSAL.search(block), (
            f"flow/{surface}: '{token}' appears in a block that does not refuse it, so it "
            f"reads as a live bypass of the ELI5 gate (issue #775):\n\n{block}"
        )


def test_the_trailer_channel_is_never_read() -> None:
    """The issue body and HEAD commit message must not be scanned for approval.

    This is the channel no invoker controls, and the one a template or a single
    merged commit could reintroduce for every run branched from that tip.
    """
    scan_instruction = re.compile(
        r"(?:issue body|commit message|HEAD commit)[^.\n]{0,120}"
        r"(?:auto-approve|auto-granted|proceed without pausing|skip)",
        re.IGNORECASE,
    )
    for surface in GATE_SURFACES:
        for block in _blocks(_read(surface)):
            match = scan_instruction.search(block)
            if match and (GRANT.search(block) or not REFUSAL.search(block)):
                pytest.fail(
                    f"flow/{surface}: instructs reading approval out of an issue body or commit "
                    f"message ({match.group(0)!r}) - the #775 channel, which is written by the "
                    f"filer or the last merger rather than the invoker:\n\n{block}"
                )


def test_auto_granted_left_the_report_vocabulary() -> None:
    """A producible `auto-granted` means a reachable bypass, so the value is gone."""
    for surface in GATE_SURFACES:
        text = _read(surface)
        for block in _blocks(text):
            if not re.search(r"auto-granted|AUTO-GRANTED", block):
                continue
            assert REFUSAL.search(block), (
                f"flow/{surface}: 'auto-granted' is offered as an approval outcome again; if the "
                f"field can be produced, something can still skip the gate (issue #775):\n\n{block}"
            )

    step3_report = [
        line
        for line in _read("auto.md").splitlines()
        if line.startswith("Report: `Step 3/9: ELI5 complete")
    ]
    assert len(step3_report) == 1, "flow/auto.md: expected exactly one Step 3/9 report line"
    assert "auto-granted" not in step3_report[0], (
        f"flow/auto.md: the Step 3 report line still offers an auto-granted outcome: {step3_report[0]}"
    )


# --- the gate that remains ---------------------------------------------------


def test_the_rule_lives_in_the_vendored_core() -> None:
    """Not a CPP-local override.

    The core between the eli5-core markers is vendored verbatim from
    cooneycw/eli5-gate. Keeping the no-bypass rule INSIDE it is what makes the
    fix propagate to every consumer of the gate instead of contradicting a core
    that still grants the bypass - the failure #775 warned about. A re-vendor
    from an upstream that reinstated a bypass turns this red.
    """
    core = _core(_read("eli5.md"))
    assert "The gate has no bypass" in core, (
        ".claude/commands/flow/eli5.md: the no-bypass rule is not inside the eli5-core markers - "
        "it would be a CPP-local override that the next `make eli5-revendor` silently discards "
        "(issue #775)"
    )
    for token in BYPASS_TOKENS:
        for block in _blocks(core):
            if token in block:
                assert not GRANT.search(block) and REFUSAL.search(block), (
                    f"vendored eli5-core: '{token}' reads as a live bypass:\n\n{block}"
                )


def test_flow_auto_still_pauses_unconditionally() -> None:
    text = _read("auto.md")
    assert "pause and wait for reviewer approval" in text
    assert "The gate has no bypass" in text, (
        "flow/auto.md: Step 3 no longer states that the gate cannot be skipped (issue #775)"
    )


def test_no_tier_auto_approves_the_gate() -> None:
    """The fourth channel: scope, not a flag or a trailer.

    The governance ladder let Tier 1 (Surgical) skip the gate by change size.
    Scope is a fine dial for how much SPEC ceremony a change carries; it is not a
    reason to implement a plan nobody approved.
    """
    offenders = []
    for path in ROOT.rglob("*.md"):
        if ".git/" in str(path) or "/node_modules/" in str(path):
            continue
        if re.search(r"ELI5 auto-approves", path.read_text(encoding="utf-8")):
            offenders.append(path.relative_to(ROOT))
    assert not offenders, (
        f"a governance tier still auto-approves the ELI5 gate in: "
        f"{', '.join(str(o) for o in offenders)} (issue #775)"
    )
