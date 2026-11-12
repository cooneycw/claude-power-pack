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
import subprocess
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


def documented_clause(passage: str) -> str:
    """The clause opening the passage tells a run to look for, with its `...`
    standing for the rest: `, LANES NOT ...` documents `, LANES NOT `."""
    found = re.findall(r"`(, LANES NOT )\.\.\.`", passage)
    assert len(found) == 1, passage
    return found[0]


def test_the_passage_names_all_three_words_the_clause_and_where_the_remedy_is() -> None:
    passage = step_seven()
    assert documented_verdicts(passage) == [f"PLAN_COMPLIANCE: {word}" for word in WORDS]
    bullet = next(part for part in passage.split("\n   - ") if "LANES NOT" in part)
    assert documented_clause(passage) == ", LANES NOT "
    assert "stderr note" in bullet and "commit" in bullet and "re-run" in bullet


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
    kinds = {"no clause": None, "not demonstrated": "DEMONSTRATED (", "not checked": "CHECKED ("}
    opening = documented_clause(passage)
    if kinds[state] is None:
        assert "LANES" not in line
    else:
        assert after_word.startswith(opening + kinds[state]), line


def stderr_note(done: subprocess.CompletedProcess) -> list[str]:
    return [ln for ln in done.stderr.splitlines() if ln.startswith("flow-plan-record: ")]


@pytest.mark.parametrize("start", ["no file", "one row missing", "an empty file", "prose and no table"])
def test_following_the_stderr_note_clears_the_clause(tmp_path: Path, start: str) -> None:
    """The passage sends a run to the stderr note. Doing exactly what the note
    says - nothing taken from this test's own knowledge of the format - is
    what removes the clause."""
    repo = make_repo(tmp_path / "wt")
    approved(repo)
    if start == "one row missing":
        (repo / SIBLING).write_text(DEMONSTRATED.replace("| Harness | tested through a symlink |\n", ""))
    elif start == "an empty file":
        (repo / SIBLING).write_text("")
    elif start == "prose and no table":
        (repo / SIBLING).write_text("# Lanes demonstrated\n\nTo be written.\n")
    first = compliance_as(repo, "agreement")
    assert ", LANES NOT DEMONSTRATED (" in verdict(first)
    note = "\n".join(stderr_note(first))
    path = re.search(r"(docs/flow-runs/issue-42\.lanes-demonstrated\.md)", note)
    assert path and "`| <lane> | <what was demonstrated> |`" in note, note
    lanes = re.search(r", LANES NOT DEMONSTRATED \((.*?)\)", verdict(first))
    assert lanes
    target = repo / path.group(1)
    if "a header row, a `|---|---|` row" in note:
        target.write_text("| Lane | What was demonstrated |\n|---|---|\n")
    else:
        assert target.exists(), "the note said to add to a table that is not there"
        assert "needs a header row and a `|---|---|` row above it, if the file has none" in note
        if "|---|" not in target.read_text():
            with target.open("a") as handle:
                handle.write("\n| Lane | What was demonstrated |\n|---|---|\n")
    with target.open("a") as handle:
        for lane in lanes.group(1).split(", "):
            handle.write(f"| {lane} | shown |\n")
    again = compliance_as(repo, "agreement")
    assert verdict(again).startswith("PLAN_COMPLIANCE: agreement - "), verdict(again)
    assert stderr_note(again) == []


@pytest.mark.parametrize("what", ["demonstrated file", "lane file"])
def test_a_not_checked_note_says_to_fix_it_or_report_unchecked(tmp_path: Path, what: str) -> None:
    """Adding rows repairs nothing here, and the note does not say to."""
    repo = make_repo(tmp_path / "wt")
    approved(repo)
    if what == "demonstrated file":
        (repo / SIBLING).mkdir()
    else:
        (repo / ".claude" / "lanes.md").unlink()
        (repo / ".claude" / "lanes.md").mkdir()
    done = compliance_as(repo, "divergence")
    assert ", LANES NOT CHECKED (" in verdict(done)
    note = stderr_note(done)
    assert len(note) == 1 and "Add `|" not in note[0]
    assert "Fix that and re-run, or report the lanes as NOT CHECKED - never as demonstrated" in note[0]


def test_the_codex_mirror_source_is_this_document() -> None:
    """The generated Codex skill is built from this file, so it carries the
    same passage; nothing else restates the verdict line for a run to match."""
    others = [path for path in (ROOT / ".claude" / "commands").rglob("*.md")
              if "PLAN_COMPLIANCE" in path.read_text() and path != AUTO]
    assert others == [], [str(path.relative_to(ROOT)) for path in others]
