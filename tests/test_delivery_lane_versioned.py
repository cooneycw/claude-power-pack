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
    """#870 acceptance: chosen values with a recorded reason, not absence.

    Anchored on the BULLET that defines each setting, not on the first place its
    name appears. The earlier version took a fixed window from the first mention,
    which made it fail the moment unrelated prose referred to `crossSessionInbound`
    further up - a true statement about the document moved the anchor off the
    bullet and the probe reported a missing recommendation that was still there.

    Worth recording because the repair is not "widen the window". A window that
    has to be widened whenever the document grows is measuring distance, and this
    probe is meant to measure whether a setting was given a value. The bullet is
    the thing the acceptance criterion is about, so the bullet is what to find.
    """
    section = _delivery_section(REGISTER.read_text())
    for setting in ("crossSessionInbound", "isolatePeerMachines"):
        assert setting in section, f"{setting} is not discussed"
        bullet = re.search(
            rf"^- \*\*`{setting}`\*\*(.*?)(?=^- \*\*`|\Z)", section, re.M | re.S
        )
        assert bullet, (
            f"{setting} is mentioned but has no bullet defining it - the acceptance "
            "criterion is a chosen value, which needs somewhere to be chosen"
        )
        assert re.search(r"Recommended:", bullet.group(1)), (
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


#: The claim this section made about containers until 2026-09-13, which measurement refuted.
CONTAINER_ABSENCE_CLAIM = re.compile(
    r"lane 1 \"?(?:does not exist|is not available)\"?", re.I
)


def test_the_container_absence_claim_is_not_asserted_bare() -> None:
    """"No local peer" and "no lane 1" are different claims. Do not re-collapse them.

    Measured from inside a container on 2.1.266, 2026-09-13: local discovery is
    empty, AND `ListAgents` still returns 49 names - every one of them a Remote
    Control session on another machine. The mechanism this document gave was right
    and the conclusion it drew from it was wrong, because Remote Control is an
    account-level path that owes nothing to the filesystem.

    The collapse is worth a guard rather than a fix-and-forget because the wrong
    version is the one that sounds more careful, and it reads as a stronger warning
    than the truth. A lane that is MISSING gets noticed when it fails. A lane that
    answers with a population containing no fleet peer gets used, and returns
    `success=true` when it is.

    Shaped like `test_the_expired_premise_is_not_asserted_bare`: the claim may be
    quoted as the thing that was corrected; it may not stand as current fact.
    """
    section = _delivery_section(REGISTER.read_text())
    for match in CONTAINER_ABSENCE_CLAIM.finditer(section):
        window = section[max(0, match.start() - 600) : match.end() + 600]
        assert re.search(
            r"does NOT follow|was wrong|it exists|exists, and it is populated", window
        ), (
            "the delivery section asserts lane 1 is absent inside a container with "
            "nothing marking that as the claim measurement refuted"
        )


def test_the_container_finding_keeps_the_population_it_qualifies() -> None:
    """A resolvable address set is only good news if it contains someone you want.

    Same discipline as the no-kill caveat: the result must not be separable from
    what limits it. "Lane 1 resolves peers inside a container" on its own is a
    strictly worse statement than the one it replaced - it invites exactly the send
    that cannot arrive. The off-box population is the whole content of the finding.
    """
    section = _delivery_section(REGISTER.read_text())
    if not re.search(r"Remote Control", section):
        return
    assert re.search(r"off-box|another machine|other machines", section, re.I), (
        "the container measurement records that peers resolve without recording "
        "that none of them is on this machine"
    )
    assert re.search(r"no fleet peer|cannot be the groupmate|cannot be it", section, re.I), (
        "the container measurement does not say the resolvable set contains no "
        "fleet peer - which is the only reason the finding changes any behaviour"
    )


def test_a_result_that_differs_by_vantage_says_so() -> None:
    """Two measurements, one harness version, different answers - name the variable.

    The section now carries results taken on 2.1.266 from the host and results
    taken on 2.1.266 from inside a container, and they disagree. A version stamp
    cannot explain that, and a reader who assumes it can will take whichever table
    is nearer and treat the other as stale.

    This is #870's own defect at one remove. The original was a claim outliving its
    evidence in TIME; this is a claim outrunning its evidence in POPULATION, and
    the stamp discipline as written does not catch it - which is why it needs its
    own probe rather than a wider version regex.
    """
    section = _delivery_section(REGISTER.read_text())
    if not re.search(r"from inside a (?:per-session )?(?:Kyle )?container", section, re.I):
        return
    assert re.search(r"vantage", section, re.I), (
        "the section reports a container-vantage result without ever naming vantage "
        "as the thing that distinguishes it from the host-vantage rows"
    )
    assert re.search(r"on the host|running \*\*on the host\*\*", section, re.I), (
        "the host-vantage rows are not labelled as host-vantage, so the container "
        "rows read as a correction rather than a different population"
    )


def test_both_surfaces_agree_on_the_container_lane_order() -> None:
    """register.md and wave.md must not give a containerised session opposite orders.

    #883 shipped an intra-file contradiction (evidence section said one direction
    measured, lane list claimed both) and it took a dedicated probe to catch. The
    same class is likelier across files than within one, because the container
    boundary is now stated in both and only one of them is where a router looks.
    """
    register = _delivery_section(REGISTER.read_text())
    wave = WAVE.read_text()
    inverted = re.compile(r"mailbox is lane 1", re.I)
    assert bool(inverted.search(register)) == bool(inverted.search(wave)), (
        "only one of register.md / wave.md states the container lane inversion - "
        "an orchestrator reads wave.md and a worker reads register.md, so a split "
        "here routes the two ends differently"
    )


# ---------------------------------------------------------------------------
# The same stamp discipline, applied to flow-wave-mailbox.sh (issue #898).
#
# #870's defect was a harness claim with no version on it, in a document a
# reader routes from. The identical defect was still standing in the mailbox
# script's own design comment: "No script here can make the HARNESS re-invoke a
# specific agent's conversation on a background process's completion", written
# as an absolute, undated, and load-bearing - it is the stated justification for
# the `route_state()` four-state model directly below it.
#
# It was wrong on the harness we run. #868's closing measurement (2.1.266,
# 2026-09-13) established that a correctly-formed write to a session's inbox
# socket DOES render as a turn (5/5 with a live parent chain), and that what
# actually gates delivery is process lineage (0/4 reparented to init) - so the
# conclusion "this daemon cannot wake the session" survived, but its stated
# reason did not.
#
# What these pin is the STAMP, not the verdict, exactly as the tests above do.
# Whether lineage still gates delivery, whether the socket stays fire-and-forget,
# whether a cross-namespace write lands - all of that is expected to move, and a
# test asserting today's answer would have to be edited by whoever next
# re-measures, which is how a guard becomes a formality. These fail when a claim
# loses its stamp, or when the retracted absolute comes back unmarked.
# ---------------------------------------------------------------------------

#: Every copy of the mailbox script - the source and its generated Codex mirrors.
#: Derived by glob rather than listed, so a mirror added later is covered without
#: anyone remembering to add it here.
MAILBOX_COPIES = sorted(ROOT.glob("**/flow-wave-mailbox.sh"))

#: The retracted absolute, in the shape the comment asserted it.
RETRACTED_ABSOLUTE = re.compile(
    r"No script here can make the\s*#?\s*HARNESS re-invoke", re.I
)


def _harness_capability_comment(text: str) -> str:
    """The design comment about waking a session, up to the ROUTE READINESS section.

    Anchored on "What this does not" (which both the old and the corrected
    heading start with) and terminated by the next section, which the comment
    itself cross-references by name. Raises rather than returning "" when the
    block cannot be found: an extractor that silently yields nothing would make
    every assertion below vacuously true, which is the failure these are for.
    """
    match = re.search(
        r"^# What this does not.*?(?=^# Route readiness)", text, re.M | re.S
    )
    if not match:
        raise AssertionError(
            "the 'What this does not ...' comment block was not found - the "
            "extractor is broken, or the block was renamed; either way these "
            "probes cannot report on it"
        )
    return match.group(0)


def test_the_mailbox_copies_are_all_discovered() -> None:
    """The glob above must actually find the copies it is meant to guard.

    Without this, a glob that matched nothing would make every parametrized test
    below collect zero cases and the file would report green having checked
    nothing - a scan whose silence is indistinguishable from a clean result.
    """
    names = {p.relative_to(ROOT).as_posix() for p in MAILBOX_COPIES}
    assert "scripts/flow-wave-mailbox.sh" in names, (
        f"the source copy was not discovered by the glob; found {sorted(names)}"
    )
    assert len(MAILBOX_COPIES) >= 3, (
        "expected the source plus its two generated Codex mirrors, found "
        f"{sorted(names)}"
    )


@pytest.mark.parametrize(
    "surface", MAILBOX_COPIES, ids=lambda p: p.parent.parent.name + "/" + p.name
)
def test_the_wake_comment_carries_a_harness_version(surface: Path) -> None:
    """A claim about what the harness can or cannot do needs the version it holds on.

    This is #870's rule, and the mailbox script asserted harness behaviour for
    months without one.
    """
    block = _harness_capability_comment(surface.read_text())
    assert VERSION.search(block), (
        f"{surface.name}: the comment states what the harness can or cannot do "
        "with no version anywhere in it - the #870 defect, in the file that "
        "justifies route_state()"
    )


@pytest.mark.parametrize(
    "surface", MAILBOX_COPIES, ids=lambda p: p.parent.parent.name + "/" + p.name
)
def test_the_retracted_absolute_is_not_asserted_bare(surface: Path) -> None:
    """The "no script here can" absolute may be quoted as history, not stated as fact.

    #868 measured the capability working 5/5 from a writer with a live parent
    chain, so the absolute is false on the installed harness. If the sentence
    reappears it must sit beside a word marking it as corrected - that is what
    stops the next reader acting on it.
    """
    text = surface.read_text()
    for match in RETRACTED_ABSOLUTE.finditer(text):
        window = text[max(0, match.start() - 700) : match.end() + 700]
        assert re.search(
            r"used to|wrong|retracted|corrected|no longer|refuted", window, re.I
        ), (
            f"{surface.name}: the retracted absolute is asserted with nothing "
            "marking it as superseded by measurement"
        )
