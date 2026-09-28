"""Routing tripwire for the canonical detector contract (issue #834).

#834 indexed twenty-one defects across two repositories that share one shape: a
check answers the narrow question it was built for, and its reader supplies a
broader one. The instances were fixed one at a time and the *shape* lived in a
single GitHub issue, so the next instance had nothing to reference. #834 asked
for it to be given a home in the review guidance; `docs/agents/detector-contracts.md`
is that home, and this file is the tripwire that keeps the surfaces pointing at it.

The failure mode guarded here is drift: a review surface stops pointing at the
canonical document, or a new review surface is added that never pointed at it.
Those are structural facts about files, so these assertions are structural.
Nothing here inspects policy wording beyond the two question sentences - a test
that pins prose breaks on every legitimate edit and gets relaxed until it means
nothing.

Per the contract this file guards, the two properties it must be able to assert
of itself:

  * Its review-surface set is DISCOVERED from the tree, not sampled. A sixth
    review surface added tomorrow without the questions fails
    ``test_every_discovered_review_surface_points_at_the_contract``. That is the
    ownership half - the set is derived from what is actually there rather than
    from what someone remembered to list.
  * It carries THREE controls, because a weaker set would leave the same hole one
    level up. ``test_the_surface_detector_can_fire`` proves the matcher fires;
    ``test_discovery_finds_nothing_in_a_tree_with_no_review_surface`` proves it is
    not matching everything; and
    ``test_discovery_reaches_the_real_root_a_new_surface_would_appear_in``
    plants a probe in the ACTUAL scanned root, because a scan aimed at the wrong
    directory passes a synthetic-fixture control and still sees nothing real.
    ``test_discovery_is_not_vacuous`` pins the floor on the live set. Without
    these, "every surface points at the contract" would be vacuously true over
    zero surfaces - question 1 of the contract, in the test rather than the code.

What a green run does NOT prove, stated so nobody reads it as more:

  * It does not prove any reviewer ASKED the two questions. Routing is not use.
  * It does not discover a review surface that carries none of ``REVIEW_MARKERS``
    - a document that instructs review in wording nobody anticipated is invisible
    here, and this test passing says nothing about it. The markers are a tripwire,
    not a census of every way a document could ask for a review.
  * It scans ``SCANNED_ROOTS`` only. A review surface that lands outside both -
    a README, a docs/ page, a template - is invisible, and the real-root control
    above proves only that the roots it DOES scan are live. Widening the roots is
    cheap; knowing which new root to add is the part no test supplies.
  * ``INDEXED_INSTANCES`` is a fixed list copied from #834. It pins that closing
    that issue does not bury its instances; it cannot notice an instance filed
    somewhere this repository never sees.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CANONICAL = Path("docs/agents/detector-contracts.md")
# Roots scanned for review surfaces. `.claude/commands/` holds them today;
# `.claude/skills/` is scanned too because nothing makes a review surface a
# COMMAND document, and a tripwire whose root is narrower than the thing it
# guards cannot represent a surface that appears one directory over.
# `codex/skills/` is deliberately excluded: it is generated from these roots by
# scripts/codex-skill-sync.py, so a finding there would be a duplicate of its
# source and `tests/test_codex_skill_sync.py` already pins that mirror.
SCANNED_ROOTS = (REPO / ".claude" / "commands", REPO / ".claude" / "skills")

# A command document is a REVIEW SURFACE when it tells a reader to review a
# change. These are the shapes actually in the tree; see the docstring for what
# they cannot see.
REVIEW_MARKERS = (
    "**Review for:**",
    "Review for: correctness",
    "Review - Claude Reviews",
)

# Surfaces that instruct review WITHOUT carrying a marker above, pinned by name.
# `/flow:auto` implements directly rather than reviewing a delegate's diff, so
# its detector guidance lives in its implement step and no marker applies.
PINNED_SURFACES = (Path(".claude/commands/flow/auto.md"),)

# The reference every routed surface must carry.
CONTRACT_LINK = "docs/agents/detector-contracts.md"

# The two questions, as the canonical document states them. Matched against a
# whitespace-normalized read so re-wrapping a blockquote is not a test failure.
QUESTION_MEMBERSHIP = (
    "Does this check's success message claim more than its input population supports?"
)
QUESTION_OWNERSHIP = (
    'Can a non-zero from this check distinguish "our thing changed" from '
    '"something that is not ours changed"?'
)


def normalized(text: str) -> str:
    """Collapse blockquote markers and line wrapping so prose can be re-wrapped."""
    return " ".join(text.replace("> ", " ").split())

# Every instance #834 indexed. Closing #834 must not bury these, so the canonical
# document has to carry each one (the orchestrator's condition on the close).
INDEXED_INSTANCES = (
    "#804",
    "#808",
    "#810",
    "#816",
    "#819",
    "#821",
    "#823",
    "#828",
    "#831",
    "#833",
    "#835",
    "#836",
    "#838",
    "#840",
    "#841",
    "#845",
    "#848",
    "#852",
    "#867",
    "#869",
    "#877",
    "kyle#994",
    "kyle#997",
)


def discover_review_surfaces(*roots: Path) -> list[Path]:
    """Every document under `roots` that instructs a reader to review a change."""
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in REVIEW_MARKERS):
                found.append(path)
    return sorted(found)


def test_canonical_document_exists_and_states_both_questions() -> None:
    doc = REPO / CANONICAL
    assert doc.is_file(), f"{CANONICAL} is missing - the contract has no home"
    text = normalized(doc.read_text(encoding="utf-8"))
    assert QUESTION_MEMBERSHIP in text, "the membership-floor question is not stated"
    assert QUESTION_OWNERSHIP in text, "the ownership-boundary question is not stated"


def test_the_surface_detector_can_fire(tmp_path: Path) -> None:
    """Positive control: the discovery function matches a synthetic surface.

    Without this, a green `test_every_discovered_review_surface_points_at_the_contract`
    is indistinguishable from a matcher that stopped matching anything.
    """
    (tmp_path / "made_up.md").write_text(
        "# Some command\n\n2. **Review for:**\n   - Correctness\n", encoding="utf-8"
    )
    assert discover_review_surfaces(tmp_path) == [tmp_path / "made_up.md"]


def test_discovery_finds_nothing_in_a_tree_with_no_review_surface(tmp_path: Path) -> None:
    """Negative control: the matcher is not matching everything it is shown."""
    (tmp_path / "unrelated.md").write_text("# Notes\n\nNothing to review here.\n", encoding="utf-8")
    assert discover_review_surfaces(tmp_path) == []


@pytest.mark.parametrize("root", SCANNED_ROOTS, ids=lambda r: r.name)
def test_discovery_reaches_the_real_root_a_new_surface_would_appear_in(root: Path) -> None:
    """The control that matters: the scan is pointed where a surface would land.

    `test_the_surface_detector_can_fire` proves the matcher works on a directory
    handed to it. That is a weaker claim than it looks: a scan aimed at the wrong
    root passes it and still sees nothing real. So this plants a probe inside the
    ACTUAL scanned root and asserts discovery returns it - proving the check runs
    where a new review surface would appear, not merely that it can match text.
    """
    assert root.is_dir(), f"{root.relative_to(REPO)} is no longer a real directory"
    # PER PROCESS (issue #1271): the probe lands in the SHARED live tree, so a
    # fixed name made two concurrent same-worktree runs collide on
    # `exist_ok=False` - one run's probe failing the other's test.
    probe = root / f"_detector_contract_probe_{os.getpid()}_" / "probe.md"
    probe.parent.mkdir(parents=True, exist_ok=False)
    try:
        probe.write_text("# probe\n\n2. **Review for:**\n   - Correctness\n", encoding="utf-8")
        assert probe in discover_review_surfaces(*SCANNED_ROOTS), (
            f"a review surface added under {root.relative_to(REPO)} would not be discovered"
        )
    finally:
        probe.unlink(missing_ok=True)
        probe.parent.rmdir()


def test_discovery_is_not_vacuous() -> None:
    """Membership floor on the real tree: the set must be non-empty and known.

    A zero here would make the routing assertion below vacuously true, which is
    precisely the defect `docs/agents/detector-contracts.md` exists to name.
    """
    surfaces = {p.relative_to(REPO) for p in discover_review_surfaces(*SCANNED_ROOTS)}
    assert surfaces, "no review surface discovered - the markers have stopped matching"
    expected = {
        Path(".claude/commands/codex/auto.md"),
        Path(".claude/commands/codex/code_review.md"),
        Path(".claude/commands/qwen/auto.md"),
        Path(".claude/commands/gemma/auto.md"),
    }
    missing = expected - surfaces
    assert not missing, f"known review surfaces no longer discovered: {sorted(map(str, missing))}"


ROUTED_SURFACES = [
    p.relative_to(REPO) for p in discover_review_surfaces(*SCANNED_ROOTS)
] + list(PINNED_SURFACES)


@pytest.mark.parametrize("surface", ROUTED_SURFACES, ids=str)
def test_every_discovered_review_surface_points_at_the_contract(surface: Path) -> None:
    """A review surface that does not route here is guidance nobody will reach.

    This is the assertion that fails when a NEW review surface is added without
    the two questions - the set is discovered from the tree, so adding one is
    enough to be covered.
    """
    text = (REPO / surface).read_text(encoding="utf-8")
    assert CONTRACT_LINK in text, (
        f"{surface} instructs a review but never routes to {CANONICAL}"
    )


def test_claude_md_routes_to_the_contract() -> None:
    text = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    assert CONTRACT_LINK in text, "CLAUDE.md does not point at the detector contract"
    assert re.search(
        r"represent the state it cannot currently see", text
    ), "the CLAUDE.md directive no longer states the contract it routes to"


def test_instance_index_carries_every_indexed_instance() -> None:
    """#834's instances must live in the doc, not only in the issue.

    This is the condition on closing #834: if the document said "see #834 for the
    list", closing the issue would bury the instances in a closed issue, which is
    the opposite of what the issue asked for.
    """
    text = (REPO / CANONICAL).read_text(encoding="utf-8")
    missing = [ref for ref in INDEXED_INSTANCES if ref not in text]
    assert not missing, f"instances absent from the index: {missing}"
# Test names the canonical document cites as prior art for the two test shapes.
# A document about claims that outrun their evidence must not carry a dead
# citation, so the pointers are pinned rather than trusted.
CITED_PRIOR_ART = (
    (Path("tests/test_pythonpath_lib_depth.py"), "def test_depth_detector_can_fire"),
    (
        Path("tests/test_flow_wave_mailbox.py"),
        "def test_a_same_wave_orphan_would_not_be_excluded_by_directory_alone",
    ),
)


@pytest.mark.parametrize(("path", "definition"), CITED_PRIOR_ART, ids=lambda v: str(v)[:60])
def test_cited_prior_art_still_exists(path: Path, definition: str) -> None:
    target = REPO / path
    assert target.is_file(), f"{path} is cited by {CANONICAL} and no longer exists"
    assert definition in target.read_text(encoding="utf-8"), (
        f"{CANONICAL} cites {definition} in {path}, which no longer defines it"
    )
_UNITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}


def count_word(word: str) -> int:
    """The integer an English count word names, 1-199 (issue #1333).

    The headings below are written in words, and the two literal dicts this
    replaces each ended somewhere (the index at thirty-five, the properties at
    Ten) - so a CORRECT change that grew the document past the last word failed
    as if it were a mismatch. Parsing the grammar removes that cliff. Anything it
    cannot parse RAISES and names the word: an unreadable count must never read
    as 0, which would turn a broken heading into a comparison that happens to
    fail - or, against an empty population, pass.

    Compounds are hyphenated ("twenty-one"), which is the document's style; an
    unhyphenated "twenty one" is refused rather than guessed at.
    """
    w = word.strip().lower()

    def below_hundred(part: str) -> int:
        if part in _UNITS:
            return _UNITS[part]
        if part in _TENS:
            return _TENS[part]
        tens, sep, unit = part.partition("-")
        if sep and tens in _TENS and unit in _UNITS and _UNITS[unit] < 10:
            return _TENS[tens] + _UNITS[unit]
        raise ValueError(f"unrecognised count word: {word!r}")

    if w == "one hundred":
        return 100
    if w.startswith("one hundred "):
        rest = w[len("one hundred "):]
        rest = rest[len("and "):] if rest.startswith("and ") else rest
        return 100 + below_hundred(rest)
    return below_hundred(w)


PROPERTIES_HEADING = re.compile(r"^## (\S+) properties that let it survive review$", re.M)
INDEX_LEAD = re.compile(r"^The (.+?) instances this contract was derived from\.", re.M)


def properties_count(text: str) -> tuple[int, int]:
    """(claimed, actual) for the properties heading of `text`."""
    heading = PROPERTIES_HEADING.search(text)
    assert heading, "the properties section heading has been renamed"
    claimed = count_word(heading.group(1))
    section = text.split(heading.group(0), 1)[1].split("\n## ", 1)[0]
    return claimed, len(re.findall(r"^\*\*", section, re.M))


def _index_rows(section: str) -> list[str]:
    return [
        line for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| instance ") and "---" not in line
    ]


def index_count(text: str) -> tuple[int, int]:
    """(claimed, actual) for the instance-index lead sentence of `text`."""
    heading = INDEX_LEAD.search(text)
    assert heading, "the instance-index lead sentence has been reworded"
    claimed = count_word(heading.group(1))
    section = text.split("## The instance index", 1)[1].split("\n## ", 1)[0]
    return claimed, len(_index_rows(section))


def test_the_properties_heading_matches_its_population() -> None:
    """The heading counts the properties it introduces.

    Written after the first draft shipped "Six properties" over a list of seven -
    a success message claiming more than its population supports, in the document
    about exactly that. The heading is a numeric aggregate, so the honest form is
    for the number to BE the count.
    """
    claimed, actual = properties_count((REPO / CANONICAL).read_text(encoding="utf-8"))
    assert claimed == actual, (
        f"the heading claims {claimed} properties; the section lists {actual}"
    )


def test_the_index_heading_matches_its_population() -> None:
    """The index says how many instances it carries; the number must be the count.

    Same shape as the properties-heading test, on the other numeric claim in the
    document. Both exist because the first draft shipped a heading that counted
    six over a population of seven.
    """
    claimed, actual = index_count((REPO / CANONICAL).read_text(encoding="utf-8"))
    assert claimed == actual, (
        f"the index claims {claimed} instances; the table has {actual} rows"
    )


# --- #1333: the heading checks can still fail, and growth no longer does ---

_NUMBER_WORDS = {n: w for w, n in {**_UNITS, **_TENS}.items()}


def _word_for(n: int) -> str:
    """Test-side spelling, independent of count_word's parsing path."""
    if n in _NUMBER_WORDS:
        return _NUMBER_WORDS[n]
    return f"{_NUMBER_WORDS[n - n % 10]}-{_NUMBER_WORDS[n % 10]}"


def _real_text() -> str:
    return (REPO / CANONICAL).read_text(encoding="utf-8")


def _with_index_word(text: str, word: str) -> str:
    old = INDEX_LEAD.search(text)
    assert old
    return text.replace(old.group(0), f"The {word} instances this contract was derived from.", 1)


def test_an_off_by_one_index_heading_fails() -> None:
    """The red case: the real document with its index word bumped by one."""
    text = _real_text()
    claimed, actual = index_count(text)
    assert claimed == actual, "precondition: the real document agrees"
    claimed, actual = index_count(_with_index_word(text, _word_for(actual + 1)))
    assert claimed == actual + 1 and claimed != actual


def test_an_off_by_one_properties_heading_fails() -> None:
    text = _real_text()
    claimed, actual = properties_count(text)
    assert claimed == actual, "precondition: the real document agrees"
    heading = PROPERTIES_HEADING.search(text)
    assert heading
    bumped = text.replace(heading.group(0),
                          f"## {_word_for(actual + 1).capitalize()} properties that let it survive review", 1)
    claimed, actual = properties_count(bumped)
    assert claimed == actual + 1 and claimed != actual


def test_growing_the_index_past_the_old_cliff_passes() -> None:
    """The index grown to fifty rows with a heading that says so agrees.

    Red on the pre-fix dict, which ended at thirty-five:
    `unrecognised count word: fifty`.
    """
    text = _real_text()
    section = text.split("## The instance index", 1)[1].split("\n## ", 1)[0]
    rows = _index_rows(section)
    assert 0 < len(rows) < 50, "precondition: the index is below the target size"
    extra = "\n".join(f"| synthetic-{i} | x | x |" for i in range(50 - len(rows)))
    grown_section = section.replace(rows[-1], rows[-1] + "\n" + extra, 1)
    grown = _with_index_word(text.replace(section, grown_section, 1), "fifty")
    assert index_count(grown) == (50, 50)


def test_an_unreadable_count_word_raises_and_is_never_zero() -> None:
    with pytest.raises(ValueError, match="umpteen"):
        index_count(_with_index_word(_real_text(), "umpteen"))


@pytest.mark.parametrize("word,expected", [
    ("one", 1), ("Seven", 7), ("thirteen", 13), ("twenty", 20), ("twenty-one", 21),
    ("thirty-five", 35), ("forty", 40), ("ninety-nine", 99), ("one hundred", 100),
    ("one hundred and one", 101), ("one hundred fifteen", 115),
    ("one hundred twenty-one", 121), ("One Hundred Ninety-Nine", 199),
])
def test_count_word_parses(word: str, expected: int) -> None:
    assert count_word(word) == expected


@pytest.mark.parametrize("word", [
    "", "zero", "twenty one", "two hundred", "thirty-", "-one", "twenty-ten",
    "one hundred and", "hundred", "31",
])
def test_count_word_refuses(word: str) -> None:
    with pytest.raises(ValueError, match="unrecognised count word"):
        count_word(word)
