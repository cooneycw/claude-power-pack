"""Pin: the delegated drivers halt before delegating (issue #774).

`/codex:auto`, `/qwen:auto` and `/gemma:auto` each printed a Step 2 plan report -
issue, acceptance criteria, files in scope, testing expectations - and then fell
straight into delegating implementation in the same turn. The report reads
exactly like a checkpoint and was not one: a grep for
`approv|confirm|wait for|pause|before proceeding|halt` between the Step 2 and
Step 3 headings returned nothing in any of the three, while `/flow:auto` genuinely
pauses at the equivalent boundary.

There is no later recovery. Each driver's Review step inspects a DIFF, which only
exists after the model has written it, so the Step 2 -> delegate boundary is the
only moment before code exists. Found on a six-worker kyle orchestration wave:
three workers described the boundary as a halt it did not have, and two were
running `/codex:auto` under a policy that assumed one.

These are prompt documents, so the document is the enforceable layer - which is
what makes this test the mechanism rather than the discipline it replaces. A
future editor cannot delete the halt, reorder it after the delegation, drop the
invoker-controlled escape hatch, or introduce the trailer-shaped bypass that
issue #775 is open about, without turning one of these red.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"

#: driver family -> (gate heading, delegation heading, the CLI it must not reach early)
DRIVERS = {
    "codex": ("### Step 3: Approve", "### Step 4: Execute Codex", "codex exec"),
    "qwen": ("### Step 3: Approve", "### Step 4: Execute Qwen", "qwen"),
    "gemma": ("### Step 3: Approve", "### Step 4: Execute Gemma", "opencode run"),
}

#: A trailer bypass is read from the issue body or HEAD commit - written by the
#: filer, not the invoker - so it can never stand in for reviewer approval (#775).
TRAILER_BYPASS = re.compile(r"auto-approve\s+trailer|trailer\s+in the issue body", re.IGNORECASE)


def _driver(family: str) -> str:
    return (COMMANDS / family / "auto.md").read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    lines = text.splitlines()
    first = next(index for index, line in enumerate(lines) if line.startswith(start))
    last = next(index for index, line in enumerate(lines) if line.startswith(end))
    assert first < last, f"{start!r} must precede {end!r}"
    return "\n".join(lines[first:last])


@pytest.mark.parametrize("family", sorted(DRIVERS), ids=sorted(DRIVERS))
def test_gate_sits_between_the_plan_report_and_the_delegation(family: str) -> None:
    gate_heading, delegate_heading, _ = DRIVERS[family]
    text = _driver(family)
    lines = text.splitlines()

    analyze = next(i for i, line in enumerate(lines) if line.startswith("### Step 2: Analyze"))
    gate = next(i for i, line in enumerate(lines) if line.startswith(gate_heading))
    delegate = next(i for i, line in enumerate(lines) if line.startswith(delegate_heading))

    assert analyze < gate < delegate, (
        f"{family}/auto.md: the approval gate must sit strictly between the Step 2 plan "
        f"report and the delegation step (issue #774); found Analyze@{analyze}, "
        f"gate@{gate}, delegate@{delegate}"
    )


@pytest.mark.parametrize("family", sorted(DRIVERS), ids=sorted(DRIVERS))
def test_gate_halts_rather_than_merely_announcing(family: str) -> None:
    gate_heading, delegate_heading, cli = DRIVERS[family]
    section = _section(_driver(family), gate_heading, delegate_heading)

    assert "STOP HERE" in section, f"{family}: the gate must say STOP, not describe a boundary"
    assert "ends the turn" in section, f"{family}: the gate must end the turn, not continue"
    assert "WAIT" in section, f"{family}: the gate must wait for the reviewer"
    assert cli in section, (
        f"{family}: the gate must name {cli!r} as the thing it withholds - a halt that does "
        "not name what it is stopping is advice, not a gate"
    )
    for verdict in ("approve", "revise", "abandon"):
        assert f"**{verdict}**" in section, f"{family}: the gate must offer the {verdict!r} verdict"


@pytest.mark.parametrize("family", sorted(DRIVERS), ids=sorted(DRIVERS))
def test_the_plan_report_no_longer_promises_to_proceed(family: str) -> None:
    gate_heading = DRIVERS[family][0]
    text = _driver(family)
    lines = text.splitlines()
    gate = next(i for i, line in enumerate(lines) if line.startswith(gate_heading))
    before_gate = "\n".join(lines[:gate])

    # codex/auto.md's Step 2 report template used to end "Proceeding to Codex
    # execution..." - the single line that most made a report look like consent.
    assert not re.search(r"Proceeding to \w+ execution", before_gate), (
        f"{family}/auto.md: nothing before the approval gate may announce that execution "
        "is about to proceed (issue #774)"
    )


@pytest.mark.parametrize("family", sorted(DRIVERS), ids=sorted(DRIVERS))
def test_only_an_invoker_typed_flag_skips_the_gate(family: str) -> None:
    text = _driver(family)

    assert "`--yes` (optional, alias `--auto-approve`)" in text, (
        f"{family}/auto.md: the gate needs an invoker-controlled escape hatch, or unattended "
        "callers are broken by it"
    )
    assert not TRAILER_BYPASS.search(text) or "no trailer-based" in text.casefold() or "NO\ntrailer-based" in text, (
        f"{family}/auto.md: a trailer bypass would let the issue filer approve on the "
        "invoker's behalf (the #775 hazard) - do not propagate it here"
    )


@pytest.mark.parametrize("family", sorted(DRIVERS), ids=sorted(DRIVERS))
def test_step_numbering_is_internally_consistent(family: str) -> None:
    text = _driver(family)

    # The renumber to 8 must be total: a leftover /7 means some report line still
    # tells the user a step count the driver no longer has.
    assert "/7:" not in text, f"{family}/auto.md: leftover 7-step reference after the #774 renumber"
    for step in range(1, 9):
        assert f"Step {step}/8" in text, f"{family}/auto.md: no report line for Step {step}/8"


def test_flow_auto_still_pauses_at_its_own_gate() -> None:
    # The parity claim these drivers now make is only true while flow:auto's gate
    # exists; if it is ever removed, this pin must fail rather than quietly rot.
    text = (COMMANDS / "flow" / "auto.md").read_text(encoding="utf-8")

    assert "pause and wait for reviewer approval" in text
    assert "Step 3/9: ELI5" in text
