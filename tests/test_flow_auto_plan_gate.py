"""Step 6 of `/flow:auto` against the line the helper really prints (#1767).

`flow-plan-record.py compliance` now puts a LANES clause directly after its
verdict word. `/flow:auto` Step 6 is the document that tells a run how to read
that line, so it is checked here against the REAL line - produced by running
the helper on a fixture repository - for each verdict word, with the clause
and without it. A hand-written stand-in for the line would pass whatever the
helper printed.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from tests.test_flow_plan_record_lanes import (
    DEMONSTRATED,
    SIBLING,
    WORDS,
    approved,
    compliance_as,
    make_repo,
    verdict,
)

ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / ".claude" / "commands" / "flow" / "auto.md"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


@pytest.fixture(autouse=True)
def isolated_session_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)


def step_seven() -> str:
    """The compliance item of Step 6: from its heading to the next item."""
    text = AUTO.read_text()
    start = text.index("**Compare the diff against the approved plan**")
    return text[start:text.index("**Confirm the plan record reached the PR**", start)]


def documented_verdicts(passage: str) -> list[str]:
    """The `PLAN_COMPLIANCE: <word>` prefixes the passage tells a run to match."""
    return re.findall(r"`(PLAN_COMPLIANCE: [a-z]+)`", passage)


def documented_clauses(passage: str) -> list[str]:
    """The clause openings the passage names, as the helper would print them."""
    bullet = next(line for line in passage.split("\n   - ") if "LANES NOT DEMONSTRATED" in line)
    found = ["LANES NOT DEMONSTRATED"] if "`, LANES NOT DEMONSTRATED (...)`" in bullet else []
    if "`NOT CHECKED`" in bullet:
        found.append("LANES NOT CHECKED")
    return found


def test_the_passage_names_all_three_words_and_both_clauses() -> None:
    passage = step_seven()
    assert documented_verdicts(passage) == [f"PLAN_COMPLIANCE: {word}" for word in WORDS]
    assert documented_clauses(passage) == ["LANES NOT DEMONSTRATED", "LANES NOT CHECKED"]
    assert "docs/flow-runs/issue-42.lanes-demonstrated.md" in passage


@pytest.mark.parametrize("word", WORDS)
@pytest.mark.parametrize("state", ["no clause", "not demonstrated", "not checked"])
def test_the_real_line_is_read_by_the_passage_as_written(tmp_path: Path, word: str, state: str) -> None:
    """Every form the helper prints still starts with a prefix the passage
    documents, and a clause, when present, sits where the passage says:
    directly after the verdict word."""
    repo = make_repo(tmp_path / "wt")
    approved(repo)
    if state == "no clause":
        (repo / SIBLING).write_text(DEMONSTRATED)
    elif state == "not checked":
        (repo / SIBLING).mkdir()
    line = verdict(compliance_as(repo, word))
    passage = step_seven()
    prefixes = [prefix for prefix in documented_verdicts(passage) if line.startswith(prefix)]
    assert prefixes == [f"PLAN_COMPLIANCE: {word}"], line
    after_word = line[len(prefixes[0]):]
    clauses = [clause for clause in documented_clauses(passage) if after_word.startswith(f", {clause} (")]
    expected = {"no clause": [], "not demonstrated": ["LANES NOT DEMONSTRATED"],
                "not checked": ["LANES NOT CHECKED"]}[state]
    assert clauses == expected, line
    if not expected:
        assert "LANES" not in line


def test_following_the_passage_clears_the_clause(tmp_path: Path) -> None:
    """The remedy the passage gives - a row per named lane in the named file,
    then re-run - is what removes the clause."""
    repo = make_repo(tmp_path / "wt")
    approved(repo)
    line = verdict(compliance_as(repo, "agreement"))
    named = re.search(r", LANES NOT DEMONSTRATED \((.*?)\)", line)
    assert named, line
    rows = "".join(f"| {lane} | shown |\n" for lane in named.group(1).split(", "))
    path = re.search(r"`(docs/flow-runs/issue-42\.lanes-demonstrated\.md)`", step_seven())
    assert path
    (repo / path.group(1)).write_text("| Lane | What happened |\n|---|---|\n" + rows)
    again = verdict(compliance_as(repo, "agreement"))
    assert again.startswith("PLAN_COMPLIANCE: agreement - "), again


def test_the_codex_mirror_source_is_this_document() -> None:
    """The generated Codex skill is built from this file, so it carries the
    same passage; nothing else restates the verdict line for a run to match."""
    others = [path for path in (ROOT / ".claude" / "commands").rglob("*.md")
              if "PLAN_COMPLIANCE" in path.read_text() and path != AUTO]
    assert others == [], [str(path.relative_to(ROOT)) for path in others]
