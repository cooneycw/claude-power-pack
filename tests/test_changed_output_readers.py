"""Readers of a changed output, and the judgement of lane tests (issue #1697, Part 2).

This file pins the routing and the wording: that the canonical reference
exists and states the rule, that every surface that must send a reader there
still does, that the counter-model prompt carries both questions, and that the
reader question does not depend on a lane file being present.

It does NOT run the reviewing model. Whether a reviewer reports a stale stub is
a model's judgement on a committed example pair; the reference records that
observation and says it is not a repeatable check.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CANONICAL = Path("docs/agents/changed-output-readers.md")
REVIEW_COMMAND = Path(".claude/commands/codex/code_review.md")
PLAN_GATE = Path(".claude/commands/flow/eli5.md")
FIXTURES = REPO / "tests" / "fixtures" / "readers"

ANSWERS = ("tested against real output", "reader unchanged", "not covered")

ROUTED_SURFACES = {
    Path("docs/agents/issue-contract.md"): "(changed-output-readers.md)",
    Path("docs/agents/closing-report-contract.md"): "(changed-output-readers.md)",
    Path("docs/agents/lanes.md"): "(changed-output-readers.md)",
    PLAN_GATE: "(../../../docs/agents/changed-output-readers.md)",
    REVIEW_COMMAND: "(../../../docs/agents/changed-output-readers.md)",
    Path("CLAUDE.md"): "docs/agents/changed-output-readers.md",
}

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


def normalized(text: str) -> str:
    return " ".join(text.split())


def read(rel: Path) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


# --- the canonical reference ---------------------------------------------------


def test_the_reference_states_the_three_answers() -> None:
    text = normalized(read(CANONICAL))
    for answer in ANSWERS:
        assert f"| {answer} |" in text, f"the reference no longer defines the answer {answer!r}"


def test_the_reference_says_a_stand_in_is_not_evidence_and_asks_how_readers_were_found() -> None:
    text = normalized(read(CANONICAL))
    assert "## A stand-in is not evidence" in read(CANONICAL)
    assert "It says nothing about the pair." in text
    assert "**Say how readers were looked for.**" in text
    assert "A search that can find nothing is not evidence" in text


def test_the_reference_applies_the_same_judgement_to_lane_tests() -> None:
    text = normalized(read(CANONICAL))
    assert "only through a stand-in where the real thing could be used" in text
    assert "could not fail if the lane or the reader were broken" in text


def test_the_reference_does_not_depend_on_a_lane_file() -> None:
    assert "the reader rule does not depend on lanes being adopted" in normalized(read(CANONICAL))


def test_the_reference_states_what_is_not_enforced() -> None:
    text = normalized(read(CANONICAL))
    assert "The table and the tests it names are not machine-checked." in text
    assert "a model's judgement on a committed example pair, not a repeatable check" in text
    assert "Not covered." in text
    assert "OBSERVATION_PLACEHOLDER" not in text, "the recorded observation was never filled in"


# --- routing --------------------------------------------------------------------


@pytest.mark.parametrize("surface", sorted(ROUTED_SURFACES), ids=str)
def test_every_surface_routes_to_the_reference(surface: Path) -> None:
    assert ROUTED_SURFACES[surface] in read(surface), f"{surface} no longer points at {CANONICAL}"


@pytest.mark.parametrize("surface", sorted(ROUTED_SURFACES), ids=str)
def test_the_routed_link_resolves(surface: Path) -> None:
    link = ROUTED_SURFACES[surface].strip("()")
    target = (REPO / link) if surface == Path("CLAUDE.md") else (REPO / surface).parent / link
    assert target.resolve() == (REPO / CANONICAL).resolve(), f"{surface}: {link} resolves elsewhere"


def test_the_two_parts_of_the_issue_name_the_same_thing_once() -> None:
    """Part 1's `Missed because:` answer and Part 2's rule point at each other."""
    contract = read(Path("docs/agents/closing-report-contract.md"))
    assert "`reader not tested against real output`" in contract
    assert "Missed because: reader not tested against real output" in normalized(read(CANONICAL))


def test_the_lanes_reference_says_readers_share_the_table_and_tests_are_judged() -> None:
    text = normalized(read(Path("docs/agents/lanes.md")))
    assert "**Readers share the table.**" in text
    assert "`Reader: <who reads it>`" in text
    assert "whether or not the project has a lane file" in text
    assert "**A lane test is judged, not only counted.**" in text


def test_the_plan_gate_sentence_applies_with_or_without_a_lane_file() -> None:
    text = read(PLAN_GATE)
    end = text.index("<!-- eli5-core:end -->")
    section = normalized(text[text.index("CPP integration: lanes and readers") :])
    assert text.index("CPP integration: lanes and readers") > end, "the pointer was written inside the vendored core"
    assert "Lane file or not, Section C names each reader of a changed output in a `Reader:` row" in section


# --- the counter-model questions -------------------------------------------------

READER_QUESTION = (
    "If the diff changes an output another part reads (response shape, file format, status line, "
    "exit code), report each reader with no 'Reader:' row in the plan's table, LANE LIST or not; "
    "with no plan in the diff, say so once."
)
TEST_QUESTION = (
    "For each row answered 'will test' or 'tested against real output', report any test reaching "
    "it only through a stand-in where the real thing could be used, or that could not fail."
)


def review_prompt(text: str) -> str:
    start = text.index('"You are reviewing a code change as an independent reviewer.')
    return text[start : text.index('| tee "$STREAM"', start)]


def test_the_review_prompt_carries_both_questions() -> None:
    prompt = normalized(review_prompt(read(REVIEW_COMMAND)))
    assert READER_QUESTION in prompt
    assert TEST_QUESTION in prompt


def test_the_reader_question_is_not_inside_the_lane_list_condition() -> None:
    """It must be asked in a project with no lane file.

    The lane paragraph opens "If a LANE LIST is given above" and closes "With
    no LANE LIST, do not raise lanes." The reader question is its own paragraph
    after that, and says so in its own words.
    """
    paragraphs = [normalized(p) for p in review_prompt(read(REVIEW_COMMAND)).split("\n\n")]
    (reader,) = [p for p in paragraphs if p.startswith("If the diff changes an output another part reads")]
    assert "If a LANE LIST is given" not in reader
    assert "LANE LIST or not;" in reader
    assert reader.endswith("with no plan in the diff, say so once.")
    (lanes,) = [p for p in paragraphs if p.startswith("If a LANE LIST is given above")]
    assert "Reader:" not in lanes
    assert lanes.endswith("With no LANE LIST, skip (1) and (2)."), (
        "the lane paragraph must say what a missing lane list switches off, and only that"
    )
    (tests,) = [p for p in paragraphs if p.startswith("For each row answered")]
    assert "LANE LIST" not in tests, "the test-quality question must not depend on a lane list"


def lanes_block() -> str:
    match = re.search(r'^LANES_LINE=""\n.*?^fi\n', read(REVIEW_COMMAND), re.DOTALL | re.MULTILINE)
    assert match, "the LANES_LINE block is no longer in the review command"
    return match.group(0)


@requires_git
@pytest.mark.parametrize("with_lane_file", [True, False], ids=["lane-file", "no-lane-file"])
def test_the_reader_question_reaches_the_reviewer_with_and_without_a_lane_file(
    tmp_path: Path, with_lane_file: bool
) -> None:
    """Project state: the prompt is BUILT both ways and the question is in both."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if with_lane_file:
        (tmp_path / ".claude").mkdir()
        shutil.copy(REPO / "tests" / "fixtures" / "lanes" / "lanes.md", tmp_path / ".claude" / "lanes.md")
    else:
        assert not (tmp_path / ".claude").exists()  # the negative precondition
    prompt_template = review_prompt(read(REVIEW_COMMAND))
    script = (
        'SCOPE_LINE="scope"; NETWORK_LINE="network"; CONTEXT="context"\n'
        + lanes_block()
        + 'PROMPT=' + prompt_template + '\nprintf "%s" "$PROMPT"\n'
    )
    built = subprocess.run(["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True, check=True)
    prompt = normalized(built.stdout)
    assert READER_QUESTION in prompt
    assert TEST_QUESTION in prompt
    assert ("LANE LIST between the markers" in prompt) is with_lane_file


def test_a_prompt_without_the_reader_question_is_reported() -> None:
    """Negative control: dropping either question (the next trim's cheapest cut) is seen."""
    text = read(REVIEW_COMMAND)
    for opening, question in (
        ("If the diff changes an output another part reads", READER_QUESTION),
        ("For each row answered 'will test' or 'tested against real output'", TEST_QUESTION),
    ):
        start = text.index(opening)
        trimmed = text[:start] + text[text.index("\n", start) :]
        assert question not in normalized(review_prompt(trimmed))


# --- the example pairs -----------------------------------------------------------


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_the_reader_pair_differs_only_in_whether_the_reader_sees_real_output() -> None:
    """The inputs are what they claim to be; this pins the FIXTURES, not the model."""
    stale, real = fixture("plan-stale-stub.md"), fixture("plan-real-output.md")
    for plan in (stale, real):
        assert "| Reader: `scripts/gate.sh`" in plan
        assert "tested against real output" in plan
        assert 'echo "STATUS: ok ($checks checks)"' in plan, "the writer no longer changes its output"
    assert 'STATUS_OUTPUT = "STATUS: ok\\n"' in stale, "the stale plan's test no longer uses a hand-written copy"
    assert 'grep -qx "STATUS: ok"' in stale, "the stale plan's reader no longer expects the old shape"
    assert '["sh", "scripts/status.sh"]' in real and "input=status.stdout" in real
    assert "STATUS_OUTPUT" not in real


def test_the_lane_pair_differs_only_in_whether_the_lane_is_reached_for_real() -> None:
    stub, real = fixture("plan-lane-stub-only.md"), fixture("plan-lane-real.md")
    for plan in (stub, real):
        assert "| Session age | will test:" in plan
        assert "def older_session(db):" in plan, "the real fixture must be in both, or 'could be used' is false"
    assert "MagicMock(" in stub and "older_session.id" not in stub
    assert "MagicMock" not in real
    assert "def test_archive_refused_for_an_older_session(client, older_session)" in real


@pytest.mark.parametrize(
    "name", ["plan-stale-stub.md", "plan-real-output.md", "plan-lane-stub-only.md", "plan-lane-real.md"]
)
def test_an_example_plan_does_not_give_the_answer_away(name: str) -> None:
    body = fixture(name).lower()
    for tell in ("bad case", "good case", "stale", "stand-in", "hand-written", "stub", "this plan does not"):
        assert tell not in body, f"{name} tells the reviewer the verdict ({tell!r})"


# --- the Harness lane: the generated plan-gate skill ------------------------------


def test_the_generated_plan_gate_skill_carries_the_reader_sentence(tmp_path: Path) -> None:
    out = tmp_path / "codex-skills"
    built = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "codex-skill-sync.py"), "--write", "--output-root", str(out)],
        capture_output=True, text=True, cwd=REPO, check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    text = normalized(
        "".join(
            (out / "flow-eli5" / name).read_text(encoding="utf-8")
            for name in ("SKILL.md", "reference.md")
            if (out / "flow-eli5" / name).is_file()
        )
    )
    assert "Lane file or not, Section C names each reader of a changed output in a `Reader:` row" in text
