"""Every run-closing surface routes to the closing-report contract (issue #965).

WHY THIS IS SHAPED LIKE `tests/test_detector_contracts.py` AND NOT LIKE
`tests/test_eli5_gate_not_bypassable.py`
---------------------------------------------------------------------------
#965 proposed the eli5-gate test as the model. It is the wrong one, and the
reason is the defect this test exists to prevent, one level up: that test pins a
HARDCODED four-name tuple, `("eli5.md", "auto.md", "auto_codex.md", "help.md")`,
and all four live under `.claude/commands/flow/`. It has never reached
`codex/auto.md`, `qwen/auto.md` or `gemma/auto.md`. Nothing is wrong with its
assertions; its POPULATION is three surfaces short of its name, and a hardcoded
list is why.

So: DERIVE THE MEMBERS, HARDCODE THE UNIVERSE.

- Candidates are derived from the tree BY PATH, so a driver added at
  `.claude/commands/<model>/auto.md` becomes a candidate the moment it exists -
  not when someone remembers to edit a tuple, and not when the driver opts in.
  The first cut discovered candidates by the marker it was also asserting, which
  made coverage OPT-IN: a new driver that never added the marker was never
  discovered, both checks stayed green, and this docstring claimed coverage it
  did not have. Codex found it on review. The derivation is by filename
  convention, which is narrower than "any run-closer" - see CLOSER_FILENAMES.
- The universe is pinned separately (`test_discovery_is_not_vacuous`), so a
  matcher that silently stops matching goes RED instead of quiet. Discovery
  alone would make every downstream assertion vacuously true against an empty
  set - which is exactly the failure `docs/agents/detector-contracts.md` names.

THE TWO SIGNALS ARE INDEPENDENT, WHICH IS THE POINT
---------------------------------------------------------------------------
A surface is DISCOVERED by a marker comment, and ASSERTED to carry a POINTER to
the contract. Deliberately two different strings:

    drop the pointer only  -> discovered, routing assertion fails      RED
    drop the marker only   -> not discovered, non-vacuity notices the
                              known member is gone                     RED
    drop both              -> non-vacuity fails                        RED

Had discovery keyed on the pointer itself, removing the pointer would remove the
surface from the set and every assertion would pass on the remainder. That is
the circular-detector trap, and it is why the marker exists as a separate token
rather than being folded into the link.

WHAT THIS TEST DOES NOT DO
---------------------------------------------------------------------------
It cannot check that a run actually EMITS a closing report. These seven files
are instructions to an agent, not code; nothing executes them, and the report is
model output rather than a file. This test enforces the POINTER. The BODY is
unenforced and `docs/agents/closing-report-contract.md` says so in those words -
a fact this module asserts, so the admission cannot quietly go missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CANONICAL = Path("docs/agents/closing-report-contract.md")

# The token that MARKS a document as a run-closing surface. Deliberately not the
# contract link - see the module docstring.
MARKER = "<!-- closing-report-surface -->"

# The token asserted to be PRESENT on every discovered surface. Matched on the
# filename so a surface may link by any relative path.
CONTRACT_LINK = "closing-report-contract.md"

# The real directory a new run-closing surface would land in. DERIVED, not
# listed: a fixed tuple of the four model directories that exist today would not
# scan `.claude/commands/<new-model>/`, which is exactly where the next driver
# appears - the opt-in gap one level further up.
COMMANDS_ROOT = REPO / ".claude" / "commands"


def _scanned_roots() -> tuple[Path, ...]:
    return tuple(sorted(d for d in COMMANDS_ROOT.iterdir() if d.is_dir()))


SCANNED_ROOTS = _scanned_roots()

# THE UNIVERSE, pinned. Derived membership is checked against this floor so an
# empty or shrunken set cannot pass silently.
KNOWN_SURFACES = {
    Path(".claude/commands/flow/auto.md"),
    Path(".claude/commands/flow/auto_codex.md"),
    Path(".claude/commands/flow/finish.md"),
    Path(".claude/commands/flow/merge.md"),
    Path(".claude/commands/codex/auto.md"),
    Path(".claude/commands/qwen/auto.md"),
    Path(".claude/commands/gemma/auto.md"),
}


# Documents that close a run, identified WITHOUT reference to anything this
# change introduces. Every lifecycle driver in this repo is `<model>/auto.md`;
# `flow/finish.md` and `flow/merge.md` end runs standalone.
#
# Codex found the first cut of this file discovering candidates BY THE MARKER,
# which made coverage opt-in: a new driver that never added the marker was never
# discovered, both checks stayed green, and this module's own docstring claimed
# it would be "covered the day it lands". A detector that only finds what
# volunteered is the defect this ticket is about.
# The filenames that close a run, applied per directory. Deriving this way
# means a tree with none of them yields an EMPTY set - the previous cut appended
# repo-absolute paths regardless of the roots it was handed, so its own negative
# control could never return empty.
#
# BOUND, stated rather than implied: this derives candidates by FILENAME
# CONVENTION. A new driver at `.claude/commands/<model>/auto.md` is caught; a
# run-closer named something else (`flow/auto_gemini.md`, say) is not. That is
# narrower than "any document that closes a run" and is the residual this
# instrument carries.
CLOSER_FILENAMES = ("auto.md", "auto_codex.md", "finish.md", "merge.md")


def candidate_closing_surfaces(*roots: Path) -> list[Path]:
    """Run-closing surfaces, derived from the tree by PATH, not by opt-in."""
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for name in CLOSER_FILENAMES:
            candidate = root / name
            if candidate.is_file():
                found.append(candidate)
    return sorted(set(found))


def discover_closing_surfaces(*roots: Path) -> list[Path]:
    """Candidates that have OPTED IN by carrying the marker.

    Kept separate from the candidate set on purpose: the gap between the two is
    the finding. `test_every_candidate_declares_itself` asserts it is empty.
    """
    out: list[Path] = []
    for path in candidate_closing_surfaces(*roots):
        try:
            if MARKER in path.read_text(encoding="utf-8"):
                out.append(path)
        except (OSError, UnicodeDecodeError):
            continue
    return out


def closing_block(text: str) -> str:
    """Just the closing-report instructions, from the marker to the next rule.

    Scoped because an assertion over the WHOLE document cannot tell a
    prescribed section name from a sentence discussing one - the same
    documentation-defeats-the-guard trap this file already hit once.
    """
    if MARKER not in text:
        return ""
    tail = text.split(MARKER, 1)[1]
    return tail.split("\n---", 1)[0]


def prescribed_sections(block: str) -> list[str]:
    """Section names the block INSTRUCTS an agent to emit.

    A prescription is a numbered list item naming a backticked `## X` heading.
    Prose discussing a name - including a prohibition - is not a prescription,
    which is the distinction the previous cut could not draw.
    """
    import re as _re

    return [
        m.group(1)
        for m in _re.finditer(r"^\s*\d+\.\s+`(##\s[^`]+)`", block, _re.M)
    ]


def contract_link_resolves(surface: Path) -> bool:
    """A markdown link to the contract whose destination actually exists."""
    import re

    block = closing_block(surface.read_text(encoding="utf-8"))
    for dest in re.findall(r"\]\(([^)]+)\)", block):
        if CONTRACT_LINK not in dest:
            continue
        if (surface.parent / dest).resolve() == (REPO / CANONICAL).resolve():
            return True
    return False


CANDIDATES = [p.relative_to(REPO) for p in candidate_closing_surfaces(*SCANNED_ROOTS)]
DISCOVERED = [p.relative_to(REPO) for p in discover_closing_surfaces(*SCANNED_ROOTS)]


def test_the_declared_set_is_exactly_the_candidate_set() -> None:
    """The two populations must agree, asserted rather than assumed.

    Codex found the per-surface checks parametrized over DISCOVERED while only
    CANDIDATES carried a non-vacuity floor: forcing discovery to return []
    deleted every routing assertion while the floor stayed green, so a
    regression in discovery would silently disable broken-link detection instead
    of reddening. Every per-surface check now runs over CANDIDATES, and this
    pins the relationship directly.

    This test was itself lost once - dropped by an edit that moved the
    definitions above it - and its absence was invisible until the mutation that
    should have reddened did not. That is the whole argument for mutating a
    control rather than reading it.
    """
    assert set(DISCOVERED) == set(CANDIDATES), (
        "declared and candidate sets differ: undeclared="
        f"{sorted(map(str, set(CANDIDATES) - set(DISCOVERED)))}"
    )



def test_the_contract_document_exists_and_states_its_three_sections() -> None:
    doc = REPO / CANONICAL
    assert doc.is_file(), f"{CANONICAL} is missing - every surface points at nothing"
    text = doc.read_text(encoding="utf-8")
    for section in ("## TO-DO (owner)", "## In plain language", "## Evidence"):
        assert section in text, f"{CANONICAL} does not define {section}"


def test_the_contract_states_plainly_that_the_body_is_unenforced() -> None:
    """The honest half, pinned so it cannot quietly go missing.

    A contract carrying an enforced pointer and an unenforced body reads as
    fully enforced unless it says otherwise. That admission is the most
    load-bearing sentence in the document precisely because nothing else in the
    repository can supply it, so it is asserted rather than trusted.
    """
    text = (REPO / CANONICAL).read_text(encoding="utf-8")
    assert "Nothing would notice" in text, (
        f"{CANONICAL} no longer states that nothing detects a run dropping the "
        f"block - without it the tripwire below implies coverage it does not have"
    )


def test_the_contract_cites_the_eli5_floor_rather_than_restating_it() -> None:
    """One plain-language standard, not two (#965's convention-collision risk)."""
    text = (REPO / CANONICAL).read_text(encoding="utf-8")
    assert "eli5.md" in text, f"{CANONICAL} must cite the existing Section A floor"
    assert "## In plain language" in text, f"{CANONICAL} must name the section"

    # The contract DESCRIBES the sections rather than containing them, so a
    # heading check is the wrong instrument here and the first two cuts of this
    # test used it anyway: one substring-matched `## ELI5` and tripped on the
    # contract's own sentence rejecting that name, the other looked for a
    # heading the document has no reason to carry. The naming risk does not live
    # in this document's prose - it lives in what the SURFACES tell an agent to
    # emit, which is checked below.
    assert not [
        ln for ln in text.splitlines() if ln.strip() == "## ELI5"
    ], f"{CANONICAL} must not carry a section literally named ELI5"


@pytest.mark.parametrize("surface", CANDIDATES, ids=str)
def test_no_surface_instructs_a_second_section_named_eli5(surface: Path) -> None:
    """The convention collision #965 was held behind #953 to avoid.

    "ELI5" names the pre-implementation APPROVAL gate, pinned by a test named
    for it. A driver instructing agents to emit an `## ELI5` section at the END
    of a run creates a second thing by that name which gates nothing, and
    invites the closing report to be read as a second approval checkpoint.

    This is the assertion that bites: the contract's prose can discuss the
    rejected name freely, but no surface may prescribe it.
    """
    # PRESCRIPTION, not occurrence. Scoping to the block was not enough and
    # Codex caught it failing in both directions: a compliant sentence saying
    # "do not call this `## ELI5`" was rejected, while a literal `## ELI5`
    # heading inside a fenced output template passed, because it carries no
    # backticks. So two precise checks replace one loose one.
    block = closing_block((REPO / surface).read_text(encoding="utf-8"))
    assert block, f"{surface} has no closing-report block to check"

    prescribed = set(prescribed_sections(block))
    assert "## In plain language" in prescribed, (
        f"{surface} does not prescribe `## In plain language` - prescribed: "
        f"{sorted(prescribed)}"
    )
    assert "## ELI5" not in prescribed, (
        f"{surface} prescribes a closing section named ELI5 - use "
        f"`## In plain language`; ELI5 is the Step 3 approval gate"
    )
    literal = [ln for ln in block.splitlines() if ln.strip() == "## ELI5"]
    assert not literal, (
        f"{surface} carries a literal `## ELI5` heading in its closing-report "
        f"block (an output template counts)"
    )


def test_the_scan_finds_nothing_in_a_tree_with_no_driver(tmp_path: Path) -> None:
    """Negative control: the scan is not matching everything it is shown."""
    (tmp_path / "notes.md").write_text("# Notes\n\nNo run ends here.\n", encoding="utf-8")
    (tmp_path / "help.md").write_text("# Help\n\nNot a driver.\n", encoding="utf-8")
    assert candidate_closing_surfaces(tmp_path) == []


def test_the_scan_reaches_where_a_NEW_DRIVER_would_land() -> None:
    """The control that matters: aimed where a new driver actually appears.

    A matcher working on a directory handed to it is a weaker claim than it
    looks - a scan aimed at the wrong root passes that and still sees nothing
    real. This plants a whole new model directory under the REAL commands root,
    the way a new lifecycle driver would arrive, and asserts the candidate scan
    returns it WITHOUT the probe opting in.
    """
    probe_dir = COMMANDS_ROOT / "_closing_report_probe_"
    probe = probe_dir / "auto.md"
    probe_dir.mkdir(parents=True, exist_ok=False)
    try:
        probe.write_text("# probe driver\n\nNo marker, no pointer.\n", encoding="utf-8")
        assert probe in candidate_closing_surfaces(*_scanned_roots()), (
            "a new lifecycle driver added under .claude/commands/ would not be "
            "treated as a candidate - coverage would silently be opt-in"
        )
    finally:
        probe.unlink(missing_ok=True)
        probe_dir.rmdir()


def test_discovery_is_not_vacuous() -> None:
    """Membership floor on the real tree: non-empty AND complete.

    A zero here makes the routing assertion below vacuously true. A subset makes
    it true of fewer surfaces than its name claims - which is exactly how the
    eli5-gate test came to cover four of seven without anyone noticing.
    """
    surfaces = {p.relative_to(REPO) for p in candidate_closing_surfaces(*_scanned_roots())}
    assert surfaces, "no run-closing surface found - the path scan has stopped matching"
    missing = KNOWN_SURFACES - surfaces
    assert not missing, (
        f"known run-closing surfaces no longer discovered: {sorted(map(str, missing))}"
    )


@pytest.mark.parametrize("surface", CANDIDATES, ids=str)
def test_every_candidate_declares_itself(surface: Path) -> None:
    """Coverage must not be opt-in.

    The candidate set is derived by PATH, so a driver added at
    `.claude/commands/<model>/auto.md` is a candidate the moment it exists. This
    asserts it also carries the marker - closing the gap where a new driver
    silently escapes both discovery and routing by simply never opting in.
    """
    text = (REPO / surface).read_text(encoding="utf-8")
    assert MARKER in text, (
        f"{surface} closes a run but carries no {MARKER} - add the closing-report "
        f"block; coverage here is not opt-in"
    )


@pytest.mark.parametrize("surface", CANDIDATES, ids=str)
def test_every_closing_surface_points_at_the_contract(surface: Path) -> None:
    """A run-closing surface that does not route here will drift from the rest.

    Discovered from the tree, so a NEW surface is covered by adding it - not by
    remembering to edit this file.
    """
    # RESOLVED, not merely present. The first cut matched the filename anywhere
    # in the document, so `../../../missing/closing-report-contract.md` passed,
    # and so did the bare filename left in prose after the link was removed. A
    # pointer that does not reach the contract is not a pointer.
    assert contract_link_resolves(REPO / surface), (
        f"{surface} closes a run but has no markdown link that RESOLVES to "
        f"{CANONICAL} (a broken path or a bare filename in prose does not count)"
    )


@pytest.mark.parametrize("surface", CANDIDATES, ids=str)
def test_every_known_surface_orders_todo_before_plain_language(surface: Path) -> None:
    """The order is the content, so it is pinned rather than described.

    #965's complaint is specifically about what gets read FIRST. A surface that
    lists the sections in the wrong order satisfies "mentions all three" while
    losing the only property the issue asked for.
    """
    text = (REPO / surface).read_text(encoding="utf-8")
    todo, plain = text.find("## TO-DO (owner)"), text.find("## In plain language")
    assert todo != -1 and plain != -1, f"{surface} does not name both sections"
    assert todo < plain, f"{surface} puts the plain-language layer before the owner TO-DO"
