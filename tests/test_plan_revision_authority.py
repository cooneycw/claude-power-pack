"""Routing and packaging checks for the plan-revision path (issue #859).

**What these tests establish, stated narrowly on purpose.** They check FILE STATE:
that the revision guidance reaches each surface that needs it, that the vendored
ELI5 core is byte-identical to the version CPP does not own, that the delegated
drivers' capability fences were not widened to make room for it, and that no new
approval checkpoint was introduced.

**What they do not establish.** They cannot show that an agent revises correctly,
that it recognises a consequential change, or that it will never ask for an extra
approval. A phrase in a prompt is not a decision. Those are behavioural properties,
evidenced in this issue by four bounded decision cases recorded in the PR, and more
broadly by #861's pilots - not by anything in this file.

Core integrity is NOT checked here. `tests/test_eli5_vendor.py` owns it against the
vendor manifest's upstream commit pin, which is a real baseline; a check in this file
comparing the core to `HEAD` would be vacuous the moment this change is committed, and
it would shell out to git, which the CI validate container does not ship. What this
file does check is that the #859 additions sit OUTSIDE the core markers.

The one non-obvious property here is DELIVERY. The delegated drivers run models
whose execution fence forbids reading `.claude/commands/**`, so guidance that lives
only in a command document is guidance those models never see. It has to be inside
the prompt text itself, in the implementation call and in the fix loop.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"

DELEGATED_DRIVERS = ("codex", "qwen", "gemma")
CORE_BEGIN = "<!-- eli5-core:begin"
CORE_END = "<!-- eli5-core:end -->"


def _read(rel: str) -> str:
    path = COMMANDS / rel
    assert path.is_file(), f"{rel} is missing; this check is stale"
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Whitespace-collapsed, because these documents wrap prose at 80 columns.

    Searching the raw text for a phrase makes the assertion depend on where a line
    happens to break, which is not the property under test.
    """
    return " ".join(text.split())


def _prompt_regions(text: str) -> list[str]:
    """The fenced blocks that ARE prompts sent to a delegated model.

    Anchored on the execution fence, which every such prompt carries at its top by
    contract. Prose about the prompt does not count: the model never reads it.
    """
    regions = []
    for match in re.finditer(r"EXECUTION FENCE - MANDATORY CONSTRAINTS", text):
        end = text.find("```", match.start())
        regions.append(text[match.start() : end if end != -1 else len(text)])
    return regions


@pytest.mark.parametrize("driver", DELEGATED_DRIVERS)
def test_the_revision_guidance_is_inside_the_delegated_prompt(driver: str) -> None:
    """Delivery, not mere presence: the model cannot read the command document."""
    text = _read(f"{driver}/auto.md")
    regions = _prompt_regions(text)
    assert regions, f"{driver}: no execution-fence prompt found; the anchor moved"

    assert any("PLAN REVISION" in region for region in regions), (
        f"{driver}: the revision guidance is not inside the prompt the model receives. "
        "Its fence forbids reading .claude/commands/**, so guidance outside the prompt "
        "never reaches it."
    )


@pytest.mark.parametrize("driver", DELEGATED_DRIVERS)
def test_the_fix_loop_prompt_also_carries_it(driver: str) -> None:
    """A gate failure is exactly when the approach turns out to be wrong."""
    text = _read(f"{driver}/auto.md")

    assert "Fix the issues while preserving the original implementation intent." in _flat(text)
    assert "report the conflict, the evidence and a concrete alternative" in _flat(text), (
        f"{driver}: the fix loop can change the approach but says nothing about what to "
        "do when the proper fix would cross a constraint"
    )


@pytest.mark.parametrize("driver", DELEGATED_DRIVERS)
def test_the_capability_fence_was_not_widened(driver: str) -> None:
    """Guidance to investigate must not become licence to reach past the sandbox."""
    text = _read(f"{driver}/auto.md")

    assert "IMPLEMENTATION-ONLY" in text
    assert re.search(r"\*\*Cannot take\*\*.*research", text), (
        f"{driver}: the Cannot-take row no longer names research"
    )
    assert re.search(r"\*\*Web\*\*\s*\|\s*\*\*no", text), (
        f"{driver}: the Web capability row is no longer a plain no"
    )


def test_the_challenge_question_lives_outside_the_core() -> None:
    text = _read("flow/eli5.md")
    core_end = text.index(CORE_END)

    assert "could this requirement" in _flat(text[core_end:]).lower(), (
        "the CPP challenge integration is missing from the CPP-owned tail"
    )
    assert "no material concern found" in _flat(text[core_end:]).lower()


def test_no_material_concern_is_stated_as_a_complete_answer() -> None:
    """Guards against the guidance being read as a quota of objections."""
    for rel in ("flow/eli5.md", "flow/auto.md"):
        assert "no material concern" in _flat(_read(rel)).lower(), rel


def test_routine_revision_is_not_routed_back_to_a_checkpoint() -> None:
    """Criterion 3: revising within the agreed outcome needs no new approval."""
    text = _read("flow/auto.md")

    assert "no new approval" in _flat(text).lower()
    assert "Only consequential deviations earn a record." in text or (
        "only consequential deviations" in text.lower()
    )


def test_authority_is_distinguished_from_approval() -> None:
    """Possessing authority is not the same as having approved THIS change."""
    text = _read("flow/auto.md")

    assert "is not agreement" in _flat(text), (
        "auto.md does not distinguish an approver existing from that approver agreeing"
    )


def test_no_blanket_gate_is_added_while_the_consequential_route_survives() -> None:
    """Two halves, and the second is the one an over-eager edit would drop.

    `tests/test_eli5_gate_not_bypassable.py` owns the bypass property itself. This
    checks only what the text CLAIMS: no blanket gate for ordinary choices, and the
    existing route for a consequential change still described. Neither is proof
    about runtime behaviour.
    """
    text = _flat(_read("flow/eli5.md"))

    assert "adds no blanket gate for ordinary implementation choices" in text
    assert "still needs agreement from the authority that already holds it" in text, (
        "the tail dropped the consequential route while disclaiming the gate"
    )


@pytest.mark.parametrize("driver", DELEGATED_DRIVERS)
def test_the_delegated_prompt_carries_prior_authorization(driver: str) -> None:
    """Criterion 5 inside the delegate, not only in host prose.

    A delegate told only that it "cannot agree and has no channel to ask" invents a
    second stop for a change its orchestrator already approved. The prompt therefore
    carries an AUTHORIZED CHANGES section, and an empty one has to read as "nothing
    pre-agreed", never as "approval is impossible".
    """
    regions = _prompt_regions(_read(f"{driver}/auto.md"))

    assert any("AUTHORIZED CHANGES" in region for region in regions), (
        f"{driver}: the prompt gives the delegate no way to know what was already agreed"
    )
    assert any(
        "not that approval is impossible" in _flat(region) for region in regions
    ), f"{driver}: an empty authorization section is not disambiguated"


@pytest.mark.parametrize("driver", DELEGATED_DRIVERS)
def test_the_fix_loop_does_not_permit_partial_boundary_changes(driver: str) -> None:
    """"Make the smallest honest change" read as licence to cross a boundary a bit."""
    text = _flat(_read(f"{driver}/auto.md"))

    assert "leave that boundary UNCHANGED pending agreement" in text
    assert "Do not implement part of the boundary change to make the gate pass." in text
    assert "make the smallest honest change you can" not in text, (
        f"{driver}: the ambiguous permission is still present"
    )


@pytest.mark.parametrize(
    "rel", ["flow/auto.md", "codex/auto.md", "qwen/auto.md", "gemma/auto.md"]
)
def test_no_surface_teaches_a_shallower_initial_review(rel: str) -> None:
    """Step 2 explores the codebase before Step 3 approves: the approval is informed.

    Parameterized over every surface carrying this premise, because the first fix
    corrected the host document only and left the three delegated prompts - the
    copies the models actually read - saying the opposite.
    """
    text = _flat(_read(rel))

    assert "approved before anyone had read the code" not in text
    assert (
        "Step 2 explored the codebase" in text
        or "reviewed against this codebase before it was approved" in text
    ), f"{rel} does not say the approval was informed"
