"""Pin: delivery-lane claims carry the harness version they were established on (issue #870).

The preference order in `flow/register.md` rested on one incident of 2026-08-11,
written as a property of "the harness" with no version attached: `SendMessage`
reportedly routed only to subagents the calling session spawned, so
orchestrator->worker was declared unreliable. Cross-session messaging between
independent sessions shipped in v2.1.224. The premise expired, the text could not
say so, and a wave kept routing around a restriction that no longer existed.

**The defect was never the verdict - it was the missing stamp.** A re-measurement
that does not carry its own version is the same artifact with a fresher date, and
#871 is the evergreen re-check that has to trust whatever is written here. So what
this file pins is the STAMP DISCIPLINE, not the current verdict: a version beside
every harness claim, contract readings labelled separately from measurements, and
the population caveats kept attached to the result they qualify.

**What is deliberately NOT pinned.** Whether lane 1 is first, whether a send kills
a background task, what `crossSessionInbound` should be - all of that is expected
to change, and a test asserting today's answer would have to be edited by the same
person who next re-measures, which is how a guard becomes a formality. The tests
below fail when a claim loses its stamp, never when a claim changes.

Verified non-vacuous: stashed against the pre-change tree, all 9 fail.

One probe had to be tightened to get there. `test_the_expired_premise_is_not_asserted_bare`
first accepted a bare `2026-08-11` near the claim as evidence it was marked
historical - but the OLD text carried that date too, so the probe passed over the
very defect it was written for. It now requires a word that actually says the
claim is dead (`expired`, `retired`, `no longer`). The general trap: when a probe
looks for context around a defect, check that the defect's own surroundings do not
already supply it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"
REGISTER = COMMANDS / "flow" / "register.md"
WAVE = COMMANDS / "flow" / "wave.md"

#: A harness version, as it must appear beside a claim: 2.1.224, 2.1.266, v2.1.224.
VERSION = re.compile(r"\bv?2\.1\.\d{3}\b")

#: The expired premise, in the exact shape both documents used to assert it.
EXPIRED_PREMISE = re.compile(
    r"routes only to subagents the calling session spawned", re.I
)


def _delivery_section(text: str) -> str:
    match = re.search(
        r"^#+[^\n]*(delivery lane|delivery preference)[^\n]*$(.*?)(?=^## |\Z)",
        text,
        re.M | re.S | re.I,
    )
    assert match, "no delivery-lane section found"
    return match.group(0)


@pytest.mark.parametrize("surface", (REGISTER, WAVE), ids=lambda p: p.name)
def test_the_expired_premise_is_not_asserted_bare(surface: Path) -> None:
    """The August claim may be QUOTED as history; it may not stand as current fact.

    Both documents stated it flatly, in the present tense, as a property of the
    harness. Wherever it still appears it must sit next to a word marking it as
    past - that is what stops a reader acting on it.
    """
    text = surface.read_text()
    for match in EXPIRED_PREMISE.finditer(text):
        window = text[max(0, match.start() - 700) : match.end() + 700]
        assert re.search(r"expired|retired|no longer|was written up", window, re.I), (
            f"{surface.name}: the 2026-08-11 premise appears with nothing marking "
            "it as expired"
        )


@pytest.mark.parametrize("surface", (REGISTER, WAVE), ids=lambda p: p.name)
def test_the_delivery_section_carries_a_harness_version(surface: Path) -> None:
    section = _delivery_section(surface.read_text())
    assert VERSION.search(section), (
        f"{surface.name}: the delivery section states harness behaviour with no "
        "version anywhere in it - the #870 defect exactly"
    )


def test_register_separates_contract_readings_from_measurements() -> None:
    """A reading of the docs and a field result are different kinds of evidence.

    Collapsing them is how an expired reading gets replaced by a fresher reading
    and the document looks re-verified when nothing was run.
    """
    section = _delivery_section(REGISTER.read_text())
    assert re.search(r"contract", section, re.I), "contract facts are not labelled"
    assert re.search(r"\bmeasured\b", section, re.I), "no measurement is labelled"
    assert re.search(
        r"installed tool contract|CONTRACT facts", section
    ), "the source of the contract claims is not named"


def test_register_states_the_container_boundary_where_the_lanes_are_chosen() -> None:
    """#870's constraint: a session in a container must not be routed into lane 1.

    It has to be stated where the choice is made. A reader picking a lane does not
    go looking for a caveat in another document.
    """
    section = _delivery_section(REGISTER.read_text())
    assert re.search(r"contain(er|erised)", section, re.I), (
        "the container boundary is not stated in the delivery section"
    )
    assert re.search(r"cannot see each other|no path between them", section, re.I), (
        "the container boundary is mentioned without saying lane 1 cannot exist"
    )


def test_register_gives_both_settings_a_value_and_a_reason() -> None:
    """#870 acceptance: chosen values with a recorded reason, not absence."""
    section = _delivery_section(REGISTER.read_text())
    for setting in ("crossSessionInbound", "isolatePeerMachines"):
        assert setting in section, f"{setting} is not discussed"
        window = section[section.index(setting) : section.index(setting) + 900]
        assert re.search(r"Recommended:", window), (
            f"{setting} has no recommended value"
        )


def test_the_no_kill_observation_keeps_its_population_caveat() -> None:
    """The confound must travel with the result, not sit in a footnote.

    This host disables the background-shell pressure reaper, so a surviving task
    may be a property of the configuration rather than of the harness version. A
    reader who takes the observation without the caveat concludes lane 1 is safe
    everywhere, which is not what was established.
    """
    section = _delivery_section(REGISTER.read_text())
    assert "CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP" in section, (
        "the confound is not named where the observation is made"
    )
    assert re.search(r"does not generalize|not measurable on this host", section, re.I), (
        "the no-kill observation is stated without its population limit"
    )


def test_the_hazard_reports_are_each_stamped() -> None:
    """Three upstream data points on three harness versions, one of them a non-repro.

    Without the stamps they average into "there is a hazard", which is both weaker
    and less true than what the thread actually says.
    """
    section = _delivery_section(REGISTER.read_text())
    versions = set(VERSION.findall(section))
    assert len(versions) >= 3, (
        f"expected several distinct harness versions beside the hazard reports, got {versions}"
    )
    assert "91139" in section, "the upstream issue is not cited"


def test_the_guidance_does_not_claim_more_than_the_evidence_records() -> None:
    """The lane list must not assert a direction the evidence section says was not measured.

    This one is a regression, and of the worst kind: the first draft of this change
    stated in its evidence section that "only one direction was re-measured here"
    and, four paragraphs later in the numbered lane list, that `SendMessage` was
    "available in both directions on 2.1.266". Same file, contradictory, and the
    half an agent acts from is the lane list - nobody reads an evidence table before
    sending a message.

    The version stamp made it worse rather than better. A stamp asserts WHEN a fact
    was established, so stamping a direction that was never exercised manufactures
    provenance for the half that has none. That is not a milder form of #870's
    defect; it is #870's defect, inside #870's own remedy.

    The distinction that has to hold: retiring a one-directional RESTRICTION is
    justified by the v2.1.224 expiry plus one measured direction - ceasing to
    believe a negative is cheap. Claiming both directions WORK is a positive claim
    about an unexercised path, and costs a measurement.
    """
    section = _delivery_section(REGISTER.read_text())
    says_one = re.search(
        r"only one direction was re-measured|was NOT re-measured", section, re.I
    )
    assert says_one, "the evidence section no longer records how many directions were measured"
    claims_both = re.search(
        r"available in both directions|works in both directions|both directions on \d",
        section,
        re.I,
    )
    assert not claims_both, (
        "the lane guidance asserts both directions while the evidence section "
        "records only one as measured - the claim must not outrun its evidence"
    )


def test_a_contested_mechanism_is_marked_completely_or_not_at_all() -> None:
    """If the document flags a mechanism as contested, it must carry the whole finding.

    CONDITIONAL by design: it says nothing about whether a contested marker should
    be there, so settling the contradiction and deleting the block is a clean pass,
    not a test to edit. What it refuses is a HALF marker - "contested" with the
    reader left to guess what against, or without the reason the contradiction
    stands.

    That reason is the load-bearing part and the easiest to drop when trimming:
    neither end can measure this alone. The sender sees `success=true`, which a
    message queued for approval also produces; the receiver sees a message appear,
    which an approved message also produces; the discriminator is shown to the
    operator and to neither session. A reader who takes "contested" as merely
    "unverified" will go and verify it by sending one, and get a confident answer
    from one end - which is worse than the ambiguity, because it looks settled.
    """
    section = _delivery_section(REGISTER.read_text())
    if not re.search(r"CONTESTED|contested", section):
        return
    assert re.search(r"2\.1\.224", section), (
        "a contested mechanism must name the source it is contested against"
    )
    assert re.search(r"neither end can measure it alone", section, re.I), (
        "the contested block does not say WHY it stays unresolved - a reader will "
        "try to settle it with a single send and report a one-ended answer"
    )
    assert re.search(r"operator", section, re.I), (
        "the contested block does not say where the discriminator actually lives"
    )
