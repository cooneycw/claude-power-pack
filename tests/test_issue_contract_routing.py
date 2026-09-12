"""Routing tripwire for the canonical issue contract (issue #856).

What this guards, and only this: the repository used to answer "how much
paperwork does a small change need?" three different ways on one page - the
constitution's P3 demanded a spec before any code, P7 demanded proportional
ceremony, and the tier table said Tier 1 needs no spec - while routing authors
through `/spec:create` and `/spec:sync`, retired in epic #417 Phase A and absent
from the tree. #856 replaced that with one canonical definition
(`docs/agents/issue-contract.md`) that the authoring surfaces point at.

The failure mode this catches is drift: a surface stops pointing at the canonical
document, a pointer stops resolving, or a retired command reappears as a live
instruction. Those are structural facts about files, so these assertions are
structural. Nothing here inspects policy wording - a test that pins prose breaks
on every legitimate edit and gets relaxed until it means nothing, and the presence
of a word is not evidence that the policy it names is coherent.

What this test CANNOT do, stated so nobody reads a green run as more than it is:

  * It does NOT discover new surfaces. ``ROUTED_SURFACES`` is a fixed list. A new
    authoring surface added tomorrow is invisible here until someone adds it, and
    the test passing says nothing about it. The list is a tripwire that fails
    loudly when a listed surface drifts, not a coverage map.
  * It does NOT verify any semantic acceptance criterion of #856 - not that the
    parts stay optional, not that tiers route proportionally, and above all not
    criterion 6, that a constrained implementation choice stays binding and cannot
    be silently reclassified as optional. Those are properties of judgment, and no
    string check reaches them. They are carried by the reviewed worked examples in
    the canonical document, including the legacy constraint with no recorded
    rationale, and by human review of that document.
  * It does NOT prove an author or agent actually used the contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
CANONICAL = Path("docs/agents/issue-contract.md")

# Fixed tripwire list: every surface #856 routed to the canonical contract. Adding
# a surface here is a deliberate act; the list never grows by itself.
ROUTED_SURFACES = (
    Path(".specify/memory/constitution.md"),
    Path(".claude/commands/spec/help.md"),
    Path(".claude/commands/github/issue-create.md"),
    Path(".claude/commands/evaluate/issue.md"),
    Path(".claude/skills/spec-driven-dev/SKILL.md"),
    Path("docs/skills/spec-driven-dev.md"),
    Path(".specify/templates/spec-template.md"),
    Path("CLAUDE.md"),
)

# Commands retired in epic #417 Phase A. `lib/spec_bridge` went with them.
RETIRED_COMMANDS = ("/spec:create", "/spec:sync", "/spec:status", "/spec:init")

# The two documents whose JOB is to record that retirement. A mention here is
# history, not an instruction - but only when the surrounding lines say so, which
# is asserted below rather than assumed.
RETIREMENT_HISTORY = frozenset(
    {
        Path(".claude/commands/spec/help.md"),
        Path(".claude/commands/spec/adopt.md"),
    }
)

RETIREMENT_WORDS = ("retire", "removed", "legacy", "no longer")

# Paths that must not instruct anyone to run a retired command. Supported surfaces
# only: historical review notes and completed specs under .specify/specs/ record
# what the repository used to do and are not instructions.
LIVE_INSTRUCTION_PATHS = ROUTED_SURFACES + (
    Path(".claude/commands/spec/adopt.md"),
    Path(".specify/templates/tasks-template.md"),
    Path(".github/ISSUE_TEMPLATE/feature-request.yml"),
    Path(".github/ISSUE_TEMPLATE/bug-report.yml"),
)

FEATURE_FORM = Path(".github/ISSUE_TEMPLATE/feature-request.yml")

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+)")

# A repo-root mention: the canonical path NOT preceded by path characters, so the
# tail of `../agents/issue-contract.md` or a wrongly rooted
# `../../docs/agents/issue-contract.md` does not count as one. Those spellings are
# relative links and are recognized only by resolving them.
REPO_ROOT_MENTION_RE = re.compile(r"(?<![\w./-])" + re.escape(CANONICAL.as_posix()))


def _read(rel: Path) -> str:
    path = REPO / rel
    assert path.is_file(), f"{rel} is missing; the tripwire list is stale"
    return path.read_text(encoding="utf-8")


def _resolved_link_targets(surface: Path, text: str) -> list[Path]:
    """Local markdown link targets, resolved against the file that contains them."""
    parent = (REPO / surface).parent
    targets = []
    for target in MARKDOWN_LINK_RE.findall(text):
        target = target.strip()
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        targets.append((parent / target).resolve())
    return targets


def _routes_to_canonical(surface: Path, text: str) -> bool:
    """True when this surface points at the canonical contract.

    Exactly two spellings are recognized, because exactly two are used here: a
    repo-root path (the SKILL.md and CLAUDE.md house style) or a relative markdown
    link that RESOLVES to the file. A relative link is resolved rather than
    string-matched, so one that spells the path correctly but is rooted wrong
    fails. Any other way of gesturing at the document is not recognized, which is
    a limit of this check and not a claim about the document.
    """
    if REPO_ROOT_MENTION_RE.search(text):
        return True
    return (REPO / CANONICAL).resolve() in _resolved_link_targets(surface, text)


def test_canonical_contract_exists() -> None:
    """Every surface below points here, so its absence breaks all of them at once."""
    assert (REPO / CANONICAL).is_file(), f"{CANONICAL} is missing"


@pytest.mark.parametrize("surface", ROUTED_SURFACES, ids=lambda p: str(p))
def test_routed_surface_points_at_the_canonical_contract(surface: Path) -> None:
    """A named route still resolves. This is the drift this test exists to catch."""
    assert _routes_to_canonical(surface, _read(surface)), (
        f"{surface} no longer references {CANONICAL} as a repo-root path or a "
        f"resolving relative link - either the route was dropped or the canonical "
        f"document moved and this list was not updated"
    )


@pytest.mark.parametrize("surface", ROUTED_SURFACES, ids=lambda p: str(p))
def test_routed_surface_relative_links_resolve(surface: Path) -> None:
    """A pointer to a file that does not exist is worse than no pointer."""
    for target in _resolved_link_targets(surface, _read(surface)):
        assert target.exists(), f"{surface} links to missing {target}"


@pytest.mark.parametrize("surface", LIVE_INSTRUCTION_PATHS, ids=lambda p: str(p))
def test_no_retired_command_reads_as_a_live_instruction(surface: Path) -> None:
    """Criterion 5's second half: obsolete command references on touched paths.

    A mention is tolerated only in the documents that record the retirement, and
    only when the lines around it say it was retired. Without that second half the
    allowlist would be a hole a live instruction could slip back through.
    """
    lines = _read(surface).splitlines()

    for number, line in enumerate(lines):
        hits = [command for command in RETIRED_COMMANDS if command in line]
        if not hits:
            continue
        assert surface in RETIREMENT_HISTORY, (
            f"{surface}:{number + 1} references retired {hits} as a live instruction"
        )
        window = " ".join(lines[max(0, number - 2) : number + 3]).lower()
        assert any(word in window for word in RETIREMENT_WORDS), (
            f"{surface}:{number + 1} mentions retired {hits} without marking it retired"
        )


def test_feature_form_does_not_require_a_prescribed_design() -> None:
    """Criterion 4, as form behavior rather than as wording.

    A form that makes a proposed design mandatory manufactures the blur this issue
    removes: the reporter must invent a mechanism, and it then reads as binding.
    The intended outcome stays required; the design does not.
    """
    form = yaml.safe_load(_read(FEATURE_FORM))
    fields = {
        field["id"]: field
        for field in form["body"]
        if isinstance(field, dict) and "id" in field
    }

    assert fields["problem"]["validations"]["required"] is True, (
        "the intended outcome is the binding part of a feature request"
    )
    assert fields["solution"].get("validations", {}).get("required", False) is False, (
        "the proposed approach must be optional - requiring it asks the reporter to "
        "prescribe a design, which is what #856 removes"
    )
