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

  * It discovers new surfaces only through ONE door (issue #1343). ``ROUTED_SURFACES``
    is still a fixed list, and it is still the drift tripwire: it fails loudly when
    a listed surface drifts. What is derived is a FLOOR beside it. Every command or
    skill document under ``.claude/commands`` or ``.claude/skills`` that mentions the
    literal ``gh issue create`` must be in ``ROUTED_SURFACES`` or in
    ``ISSUE_CREATE_EXEMPT`` with a reason, so a new issue-filing command cannot
    arrive unrouted without a decision. The door is narrow, and that is a stated
    limit, not a claim:
      - A surface that files issues any other way (``gh api``, a helper script, a
        form) is NOT seen, and a green floor says nothing about it.
      - A document that only QUOTES the command in prose is seen. It must be exempted
        with that reason, or reworded. That friction is intended.
      - ``codex/skills/`` is excluded on purpose. It holds generated mirrors of the
        command documents, whose drift from their sources is caught by
        ``codex-skill-sync.py --check`` (``make codex-skills-check``), not here.
        Scanning them would count every source twice and add no decision.
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

# Documents that mention `gh issue create` but are deliberately NOT routed to the
# canonical contract (issue #1343). Each reason names the FACT that makes the
# document exempt, not a category, so a reader can check whether it still holds.
# The stale-exempt tripwire below is STRUCTURAL only: it catches an entry whose
# path is gone, no longer mentions the command, has a blank reason, or is also
# routed. It cannot tell whether the stated fact is still TRUE - if wave.md began
# instructing authors to file issues, it would stay green. Checking the reason
# is the job of whoever reviews a change to an exempt document (counter-model
# review).
ISSUE_CREATE_EXEMPT: dict[Path, str] = {
    Path(".claude/commands/flow/wave.md"): (
        "it only prohibits `gh issue create` during an active wave and files nothing"
    ),
    Path(".claude/commands/self-improvement/retro.md"): (
        "the body is the stored issue_candidate the retro tool emits, not something "
        "an author composes"
    ),
    Path(".claude/commands/self-improvement/memory.md"): (
        "the body is the fingerprint-marker template the memory tool emits, not "
        "something an author composes"
    ),
    Path(".claude/commands/qa/test.md"): (
        "the body is a reproduction of an observed failure (steps, expected, actual), "
        "not an outcome/constraint contract"
    ),
}

ISSUE_CREATE = "gh issue create"

# Where issue-filing surfaces are derived from. `codex/skills/` is excluded on
# purpose: see the module docstring.
ISSUE_CREATE_ROOTS = (Path(".claude/commands"), Path(".claude/skills"))

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


def _issue_creating_surfaces(root: Path) -> list[Path]:
    """Every command or skill document under ``root`` that mentions ``gh issue create``."""
    found = []
    for base in ISSUE_CREATE_ROOTS:
        for path in sorted((root / base).rglob("*.md")):
            if ISSUE_CREATE in path.read_text(encoding="utf-8"):
                found.append(path.relative_to(root))
    return found


def _unaccounted(found: list[Path], routed: tuple[Path, ...], exempt: dict[Path, str]) -> list[Path]:
    return [path for path in found if path not in routed and path not in exempt]


def _stale_exemptions(root: Path, routed: tuple[Path, ...], exempt: dict[Path, str]) -> list[str]:
    problems = []
    for path, reason in exempt.items():
        if not reason.strip():
            problems.append(f"{path}: exempt with no reason")
        if path in routed:
            problems.append(f"{path}: both routed and exempt - pick one")
        if not (root / path).is_file():
            problems.append(f"{path}: exempt but missing")
        elif ISSUE_CREATE not in (root / path).read_text(encoding="utf-8"):
            problems.append(f"{path}: exempt but no longer mentions `{ISSUE_CREATE}`")
    return problems


def _fixture_tree(tmp_path: Path, name: str) -> Path:
    doc = tmp_path / ".claude" / "commands" / "fake" / name
    doc.parent.mkdir(parents=True)
    doc.write_text("Then run:\n\n    gh issue create --title t --body b\n", encoding="utf-8")
    return doc.relative_to(tmp_path)


def test_the_issue_create_scan_finds_the_known_filing_surface() -> None:
    """Positive control and membership floor: a scan that finds nothing is broken,
    not clean. `github/issue-create.md` is the surface #856 routed on purpose."""
    found = _issue_creating_surfaces(REPO)
    assert Path(".claude/commands/github/issue-create.md") in found, found


def test_every_issue_filing_surface_is_routed_or_exempt() -> None:
    """The derived floor (issue #1343): a new issue-filing command is a decision."""
    missing = _unaccounted(_issue_creating_surfaces(REPO), ROUTED_SURFACES, ISSUE_CREATE_EXEMPT)
    assert not missing, (
        f"these documents run `{ISSUE_CREATE}` but are neither in ROUTED_SURFACES nor in "
        f"ISSUE_CREATE_EXEMPT with a reason: {[str(p) for p in missing]}"
    )


def test_no_issue_create_exemption_is_stale() -> None:
    """An exemption that is structurally stale must not keep excusing its path.

    Structural only: see ISSUE_CREATE_EXEMPT for what this cannot judge.
    """
    problems = _stale_exemptions(REPO, ROUTED_SURFACES, ISSUE_CREATE_EXEMPT)
    assert not problems, problems


def test_an_unrouted_issue_filing_doc_is_reported(tmp_path: Path) -> None:
    """The committed red case: a doc in neither list is named, and only it."""
    doc = _fixture_tree(tmp_path, "filer.md")
    found = _issue_creating_surfaces(tmp_path)
    assert found == [doc], "precondition: the fixture is seen by the scan"

    assert _unaccounted(found, (), {}) == [doc]
    assert _unaccounted(found, (doc,), {}) == [], "routed is accounted for"
    assert _unaccounted(found, (), {doc: "a reason"}) == [], "exempt is accounted for"


def test_a_stale_exemption_is_reported(tmp_path: Path) -> None:
    """The tripwire's other verdict: each stale shape is named."""
    doc = _fixture_tree(tmp_path, "filer.md")
    assert _stale_exemptions(tmp_path, (), {doc: "a reason"}) == [], "precondition: fresh is clean"

    (tmp_path / doc).write_text("This command files nothing.\n", encoding="utf-8")
    assert any("no longer mentions" in p for p in _stale_exemptions(tmp_path, (), {doc: "a reason"}))
    gone = Path(".claude/commands/fake/gone.md")
    assert any("missing" in p for p in _stale_exemptions(tmp_path, (), {gone: "a reason"}))
    assert any("no reason" in p for p in _stale_exemptions(tmp_path, (), {doc: " "}))
    assert any("both routed" in p for p in _stale_exemptions(tmp_path, (doc,), {doc: "a reason"}))


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
