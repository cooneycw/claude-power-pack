"""Plan approval refuses a record that does not answer the project's lanes (issue #1731).

Since #1695 a plan in a project with `.claude/lanes.md` must answer every
listed lane. Nothing checked it: three plans were approved without the table
in one afternoon. `flow-plan-record.py approve` now refuses such a record, in
the line it already prints for a record it cannot stamp, before it writes
anything.

What these tests hold still, in order of what would hurt most if it moved:

- A project with NO lane file gets byte-identical output to the helper before
  this change. That is every repository but one today.
- A lane file that exists and cannot be used never reads as "no lanes".
- The stability digest is untouched: the digest code is main's, character for
  character, and old and new helper stamp the same digest for every record.
  What was demonstrated goes in a file of its own, so no part of an approved
  record is ever outside the digest.
- The close-time note is stderr only and changes no verdict.

Not checked anywhere, by design: whether an answer is true.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "flow-plan-record.py"
BEFORE = ROOT / "controls" / "flow-plan-record-lanes" / "anchors" / "pre-1731-flow-plan-record.py"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

LANES = """# Lanes

Reviewed: 2026-11-11

| Lane | Values | How it is exercised |
|---|---|---|
| Checkout | main checkout / linked worktree | Tests build both |
| Harness | Claude install / Codex install | The mirrors are built |
| Project state | adopted / not adopted | Tests build both |
"""

PLAN = """- Approval:          granted

## Section C - the approved plan
  1. `src/app.py` - because
Scope: 1 file
Risks: none notable
"""

FULL_TABLE = """
### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test | a test in a linked worktree |
| Harness | will test (Claude install); not covered (Codex install) | through a symlink |
| Project state | not applicable | nothing reads an adopted file |
"""


@pytest.fixture(autouse=True)
def isolated_session_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout


def run(repo: Path, *args: str, helper: Path = HELPER) -> subprocess.CompletedProcess:
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID="session-lanes")
    return subprocess.run(["python3", str(helper), *args], cwd=repo, capture_output=True,
                          text=True, env=env)


def make_repo(path: Path, lanes: str | None = LANES) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@e.com")
    git(path, "config", "user.name", "t")
    (path / "README.md").write_text("base\n")
    if lanes is not None:
        (path / ".claude").mkdir()
        (path / ".claude" / "lanes.md").write_text(lanes)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "base")
    git(path, "checkout", "-q", "-b", "issue-42-a-fixture")
    return path


def begin(repo: Path, section: str, helper: Path = HELPER) -> Path:
    body = repo.parent / f"{repo.name}-body.md"
    body.write_text("The issue body.\n")
    for args in (("reconcile", "42"), ("read-issue", "42", "--body-file", str(body)),
                 ("begin-run", "42")):
        done = run(repo, *args, helper=helper)
        assert done.returncode == 0, done.stdout + done.stderr
    record = repo / "docs" / "flow-runs" / "issue-42.md"
    with record.open("a") as fh:
        fh.write(section)
    return record


def written(repo: Path) -> tuple[bool, bool]:
    """(the as-read snapshot exists, the baseline was stamped)."""
    baseline = Path(git(repo, "rev-parse", "--absolute-git-dir").strip()) / "flow-plan-baseline-42"
    return (repo / "docs" / "flow-runs" / "issue-42.as-read.md").exists(), baseline.exists()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "wt")


# --- the refusals ------------------------------------------------------------

def test_a_record_with_no_lanes_table_is_refused_and_nothing_is_written(repo: Path) -> None:
    begin(repo, PLAN)
    done = run(repo, "approve", "42")
    assert done.returncode == 1, done.stdout
    assert done.stdout.startswith("FLOW_PLAN_RECORD: error - the plan record has no lanes table")
    for lane in ("Checkout", "Harness", "Project state"):
        assert lane in done.stdout, "the refusal names the lanes to answer"
    assert written(repo) == (False, False), "a refused approval wrote something"


def test_the_same_record_was_approved_before_the_change(repo: Path) -> None:
    """Red case for the test above."""
    begin(repo, PLAN, helper=BEFORE)
    done = run(repo, "approve", "42", helper=BEFORE)
    assert done.returncode == 0 and "baseline stamped" in done.stdout


@pytest.mark.parametrize("row,why", [
    (None, "no row at all"),
    ("| Harness |  | left blank |", "an empty answer"),
    ("| Harness | tbd | later |", "an answer that is not one of the four"),
    ("| Harness | yes | sure |", "an answer that is not one of the four"),
    ("| Harness | tested | already |", "the closing word, not an approval answer"),
    ("| Harness |", "a row with no answer cell"),
])
def test_an_unanswered_lane_is_refused_by_name(repo: Path, row: str | None, why: str) -> None:
    table = FULL_TABLE.replace(
        "| Harness | will test (Claude install); not covered (Codex install) | through a symlink |\n",
        f"{row}\n" if row else "")
    assert table != FULL_TABLE, "precondition: the Harness row was replaced"
    begin(repo, PLAN + table)
    done = run(repo, "approve", "42")
    assert done.returncode == 1, f"{why}: {done.stdout}"
    assert "leaves these listed lanes unanswered: Harness." in done.stdout
    assert "Checkout" not in done.stdout.split("unanswered:")[1].split(".")[0]
    assert written(repo) == (False, False)


def test_every_lane_answered_is_approved(repo: Path) -> None:
    begin(repo, PLAN + FULL_TABLE)
    done = run(repo, "approve", "42")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "FLOW_PLAN_RECORD: baseline stamped" in done.stdout
    assert "WAIVED" not in done.stderr and "lane" not in done.stdout.lower()
    assert written(repo) == (True, True)


@pytest.mark.parametrize("answer", ["will test", "Will Test - how", "will refuse", "not applicable",
                                    "not covered", "**will test**", "`not covered`"])
def test_each_of_the_four_answers_counts(repo: Path, answer: str) -> None:
    begin(repo, PLAN + FULL_TABLE.replace("| Checkout | will test |", f"| Checkout | {answer} |"))
    assert run(repo, "approve", "42").returncode == 0


def test_a_lane_the_project_does_not_list_is_ignored(repo: Path) -> None:
    begin(repo, PLAN + FULL_TABLE + "| Weather | tbd | not a lane here |\n")
    assert run(repo, "approve", "42").returncode == 0


def test_lane_names_match_whatever_their_case_or_emphasis(repo: Path) -> None:
    begin(repo, PLAN + FULL_TABLE.replace("| Project state |", "| **project State** |"))
    assert run(repo, "approve", "42").returncode == 0


# --- the heading is a heading ------------------------------------------------

def test_the_words_in_prose_are_not_a_table(repo: Path) -> None:
    """A sentence that mentions the table, followed by a table of something
    else, must not be taken for the lanes table."""
    prose = ("\nThe Lanes for this change are answered in the pull request.\n\n"
             "| Lane | Answer |\n|---|---|\n| Checkout | will test |\n| Harness | will test |\n"
             "| Project state | will test |\n")
    begin(repo, PLAN + prose)
    done = run(repo, "approve", "42")
    assert done.returncode == 1 and "has no lanes table" in done.stdout


def test_a_table_under_a_later_heading_does_not_answer_for_the_lanes_heading(repo: Path) -> None:
    section = PLAN + ("\n### Lanes for this change\n\nSee below.\n\n### Something else\n\n"
                      "| Lane | Answer |\n|---|---|\n| Checkout | will test |\n"
                      "| Harness | will test |\n| Project state | will test |\n")
    begin(repo, section)
    done = run(repo, "approve", "42")
    assert done.returncode == 1 and "unanswered: Checkout, Harness, Project state" in done.stdout


# --- the one-line waiver -----------------------------------------------------

def test_a_waiver_with_a_reason_is_accepted_and_said_out_loud(repo: Path) -> None:
    begin(repo, PLAN + "\nLanes: none - documentation only\n")
    done = run(repo, "approve", "42")
    assert done.returncode == 0, done.stdout
    assert "lane table WAIVED for this plan - Lanes: none - documentation only" in done.stderr
    assert "WAIVED" not in done.stdout, "the note is stderr only"


@pytest.mark.parametrize("line", ["Lanes: none", "Lanes: none -", "Lanes: none -   "])
def test_a_bare_waiver_is_refused(repo: Path, line: str) -> None:
    begin(repo, PLAN + f"\n{line}\n")
    done = run(repo, "approve", "42")
    assert done.returncode == 1 and "gives no reason" in done.stdout
    assert written(repo) == (False, False)


def test_a_waiver_inside_a_sentence_is_not_a_waiver(repo: Path) -> None:
    begin(repo, PLAN + "\nWe considered writing Lanes: none - docs only, and did not.\n")
    assert run(repo, "approve", "42").returncode == 1


# --- project state: no lane file, and a lane file that cannot be used --------

@pytest.mark.parametrize("section", [PLAN, PLAN + FULL_TABLE, PLAN + "\nLanes: none\n"])
def test_with_no_lane_file_approval_is_byte_identical_to_before(tmp_path: Path, section: str) -> None:
    """Lane: Project state, not adopted. Same record, same repository shape,
    old helper and new: stdout, stderr and exit code must not differ by a byte
    (the digest is masked; it covers a run id minted per repository)."""
    outs = []
    for name, helper in (("old", BEFORE), ("new", HELPER)):
        r = make_repo(tmp_path / name, lanes=None)
        assert not (r / ".claude" / "lanes.md").exists(), "precondition: no lane file"
        begin(r, section, helper=helper)
        done = run(r, "approve", "42", helper=helper)
        mask = lambda s: re.sub(r"[0-9a-f]{64}", "<digest>", s)   # noqa: E731
        outs.append((done.returncode, mask(done.stdout), mask(done.stderr)))
    assert outs[0] == outs[1]
    assert outs[1][0] == 0


@pytest.mark.parametrize("lanes", [None, LANES], ids=["no-lane-file", "lane-file"])
def test_the_helper_works_shipped_alone(tmp_path: Path, lanes: str | None) -> None:
    """Lane: Harness, Codex install. The `flow-auto` bundle ships this helper
    WITHOUT lane-file.py, so the check must need nothing beside it - in a
    project with a lane file as much as in one without."""
    alone = tmp_path / "bundle" / "scripts" / "flow-plan-record.py"
    alone.parent.mkdir(parents=True)
    shutil.copy(HELPER, alone)
    assert [p.name for p in alone.parent.iterdir()] == ["flow-plan-record.py"]
    r = make_repo(tmp_path / "wt", lanes=lanes)
    begin(r, PLAN, helper=alone)
    done = run(r, "approve", "42", helper=alone)
    if lanes is None:
        assert done.returncode == 0, done.stdout + done.stderr
    else:
        assert done.returncode == 1 and "has no lanes table" in done.stdout, done.stdout
    begin_ok = make_repo(tmp_path / "wt2", lanes=lanes)
    begin(begin_ok, PLAN + FULL_TABLE, helper=alone)
    assert run(begin_ok, "approve", "42", helper=alone).returncode == 0


def test_the_check_runs_through_an_installed_symlink(tmp_path: Path) -> None:
    """Lane: Harness, Claude install. `~/.claude/scripts/flow-plan-record.py` is
    a symlink into the checkout."""
    link = tmp_path / "installed" / "flow-plan-record.py"
    link.parent.mkdir()
    link.symlink_to(HELPER)
    r = make_repo(tmp_path / "wt")
    begin(r, PLAN, helper=link)
    done = run(r, "approve", "42", helper=link)
    assert done.returncode == 1 and "has no lanes table" in done.stdout


def _unusable(kind: str, repo: Path) -> None:
    lane_file = repo / ".claude" / "lanes.md"
    lane_file.unlink()
    if kind == "directory":
        lane_file.mkdir()
    elif kind == "dangling symlink":
        lane_file.symlink_to(repo / "nowhere.md")
    elif kind == "no table":
        lane_file.write_text("# Lanes\n\nReviewed: 2026-11-11\n\nThe table is gone.\n")
    elif kind == "table with no rows":
        lane_file.write_text("# Lanes\n\n| Lane | Values |\n|---|---|\n")
    elif kind == "not text":
        lane_file.write_bytes(b"\xff\xfe\x00\x80 lanes")


@pytest.mark.parametrize("kind", ["directory", "dangling symlink", "no table",
                                  "table with no rows", "not text"])
def test_an_unusable_lane_file_is_unknown_and_never_reads_as_no_lanes(repo: Path, kind: str) -> None:
    _unusable(kind, repo)
    assert os.path.lexists(repo / ".claude" / "lanes.md"), "precondition: the lane file is there"
    begin(repo, PLAN)            # a record with NO table: must not slip through as "no lanes"
    done = run(repo, "approve", "42")
    assert done.returncode == 1, f"{kind}: {done.stdout}"
    assert done.stdout.startswith("FLOW_PLAN_RECORD: error - unknown: "), done.stdout
    assert "/lane:update" in done.stdout
    assert written(repo) == (False, False)


def _load(path: Path, name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("kind", ["absent", "readable", "directory", "dangling symlink",
                                  "not text", "parent is a file", "symlink to a file"])
def test_this_helper_and_lane_file_py_agree_on_what_a_lane_file_is(tmp_path: Path, kind: str) -> None:
    """Two readers of one file. They are kept apart so this helper can ship
    alone, and this is what stops them drifting: the same state must be
    absent, readable or unusable to both."""
    ours = _load(HELPER, "_fpr_under_test")
    theirs = _load(ROOT / "scripts" / "lane-file.py", "_lane_file_under_test")
    root = tmp_path / "project"
    (root / ".claude").mkdir(parents=True)
    path = root / ".claude" / "lanes.md"
    if kind == "readable":
        path.write_text(LANES)
    elif kind == "symlink to a file":
        (root / "real.md").write_text(LANES)
        path.symlink_to(root / "real.md")
    elif kind == "parent is a file":
        (root / ".claude").rmdir()
        (root / ".claude").write_text("not a directory\n")
    elif kind != "absent":
        path.write_text("x")
        _unusable(kind, root)

    def classify(reader, unusable) -> str:
        try:
            text = reader(path)
        except unusable:
            return "unusable"
        return "absent" if text is None else "readable"

    mine = classify(ours.read_lane_text, ours.LanesUnusable)
    other = classify(theirs.read_lane_file, theirs.Unusable)
    assert mine == other, f"{kind}: this helper says {mine}, lane-file.py says {other}"
    expected = {"absent": "absent", "readable": "readable", "symlink to a file": "readable"}
    assert mine == expected.get(kind, "unusable")


def test_the_lane_file_is_found_from_a_linked_worktree(tmp_path: Path) -> None:
    """Lane: Checkout, linked worktree - where a flow run actually approves."""
    main = make_repo(tmp_path / "main")
    wt = tmp_path / "linked"
    git(main, "worktree", "add", "-q", "-b", "issue-42-linked", str(wt), "main")
    assert (wt / ".git").is_file() and (wt / ".claude" / "lanes.md").is_file()
    begin(wt, PLAN)
    done = run(wt, "approve", "42")
    assert done.returncode == 1 and "has no lanes table" in done.stdout


# --- found by the counter-model review ---------------------------------------
# Each of these was approved, or hidden from the digest, by the first cut.

FENCED_TABLE = "\n```markdown\n" + FULL_TABLE.strip("\n") + "\n```\n"


@pytest.mark.parametrize("quoted", [
    FENCED_TABLE,
    FENCED_TABLE.replace("```", "~~~"),
    "\n````\n```\n" + FULL_TABLE.strip("\n") + "\n```\n````\n",
    "\n```\nLanes: none - example only\n```\n",
], ids=["backtick-fence", "tilde-fence", "nested-fence", "fenced-waiver"])
def test_an_example_inside_a_code_fence_does_not_answer_for_the_plan(repo: Path, quoted: str) -> None:
    begin(repo, PLAN + quoted)
    done = run(repo, "approve", "42")
    assert done.returncode == 1 and "has no lanes table" in done.stdout, done.stdout + done.stderr
    assert "WAIVED" not in done.stderr


def test_a_delimiter_row_with_no_header_is_not_a_table(repo: Path) -> None:
    rows = ("\n### Lanes for this change\n\n|---|---|---|\n| Checkout | will test | x |\n"
            "| Harness | will test | x |\n| Project state | will test | x |\n")
    begin(repo, PLAN + rows)
    done = run(repo, "approve", "42")
    assert done.returncode == 1 and "unanswered: Checkout, Harness, Project state" in done.stdout


def test_a_table_without_outer_pipes_is_a_table(tmp_path: Path) -> None:
    """Markdown allows it, in the lane file and in the plan alike."""
    lanes = ("# Lanes\n\nReviewed: 2026-11-11\n\nLane | Values\n--- | ---\n"
             "Checkout | main / linked\nHarness | Claude / Codex\n")
    table = ("\n### Lanes for this change\n\nLane | Answer | How\n---|---|---\n"
             "Checkout | will test | a test\nHarness | not covered | no bundle run\n")
    r = make_repo(tmp_path / "wt", lanes=lanes)
    begin(r, PLAN + table)
    done = run(r, "approve", "42")
    assert done.returncode == 0, done.stdout + done.stderr
    r2 = make_repo(tmp_path / "wt2", lanes=lanes)
    begin(r2, PLAN + table.replace("Harness | not covered | no bundle run\n", ""))
    assert "unanswered: Harness." in run(r2, "approve", "42").stdout


def test_an_escaped_pipe_stays_inside_its_cell(repo: Path) -> None:
    table = FULL_TABLE.replace("| Checkout | will test | a test in a linked worktree |",
                               "| Checkout | will test | run `a \\| b` in a linked worktree |")
    begin(repo, PLAN + table)
    assert run(repo, "approve", "42").returncode == 0


LANES_AB = LANES.replace("| Harness |", "| A_B |").replace("| Project state |", "| AB |")


def test_one_row_cannot_answer_two_lanes_whose_names_differ_inside(tmp_path: Path) -> None:
    r = make_repo(tmp_path / "wt", lanes=LANES_AB)
    table = ("\n### Lanes for this change\n\n| Lane | Answer |\n|---|---|\n"
             "| Checkout | will test |\n| AB | will test |\n")
    begin(r, PLAN + table)
    done = run(r, "approve", "42")
    assert done.returncode == 1 and "unanswered: A_B." in done.stdout, done.stdout


def test_a_lane_file_listing_one_name_twice_is_unknown(tmp_path: Path) -> None:
    lanes = LANES.replace("| Harness |", "| **Checkout** |")
    r = make_repo(tmp_path / "wt", lanes=lanes)
    begin(r, PLAN + FULL_TABLE)
    done = run(r, "approve", "42")
    assert done.returncode == 1 and "unknown: " in done.stdout and "same name" in done.stdout


def test_an_indented_lanes_heading_is_still_the_heading(repo: Path) -> None:
    begin(repo, PLAN + FULL_TABLE.replace("### Lanes for this change", "  ### Lanes for this change"))
    assert run(repo, "approve", "42").returncode == 0


def test_a_backtick_line_that_cannot_open_a_fence_does_not_unquote_what_follows(repo: Path) -> None:
    """```invalid`info is not a fence opener in markdown, so the NEXT ``` opens
    one and the table below is quoted. A tracker that took the first line for
    an opener read the second as its closer and the table as live."""
    quoted = "\n```invalid`info\n```\n" + FULL_TABLE.strip("\n") + "\n```\n"
    begin(repo, PLAN + quoted)
    done = run(repo, "approve", "42")
    assert done.returncode == 1 and "has no lanes table" in done.stdout, done.stdout


# --- the stability digest is main's, exactly ---------------------------------
# What a run demonstrated is written to a sibling file. An earlier design kept
# it inside the record and left that part out of the digest; three review
# passes each found another way to hide a plan edit in the part left out
# (a fenced heading, an indented heading, a numbered plan line with a pipe).
# So nothing is left out, and these tests hold the digest still.

DEMONSTRATED = """# Lanes demonstrated - issue #42

| Lane | What happened |
|---|---|
| Checkout | tested in a linked worktree |
| Harness | tested through a symlink |
"""

IN_RECORD_BLOCK = "\n### Lanes demonstrated\n\n| Lane | What happened |\n|---|---|\n| Checkout | x |\n"


def _function_source(path: Path, name: str) -> str:
    import ast
    src = path.read_text()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return "\n".join(src.split("\n")[node.lineno - 1:node.end_lineno])


@pytest.mark.parametrize("name", ["section_digest", "stability_check", "split_runs", "select_run"])
def test_the_digest_code_is_the_code_before_this_change(name: str) -> None:
    """Mechanical, not by reading: the source text of each function the digest
    runs through is identical in the helper and in the pre-change anchor."""
    assert _function_source(HELPER, name) == _function_source(BEFORE, name)


def test_approve_stamps_the_baseline_with_the_same_statements() -> None:
    new, old = _function_source(HELPER, "cmd_approve"), _function_source(BEFORE, "cmd_approve")
    tail = lambda s: s[s.index("    # The baseline is THIS RUN'S SECTION"):]   # noqa: E731
    assert tail(new) == tail(old)


@pytest.mark.parametrize("lanes", [None, LANES], ids=["no-lane-file", "lane-file"])
@pytest.mark.parametrize("section", [PLAN + FULL_TABLE, PLAN + FULL_TABLE + IN_RECORD_BLOCK,
                                     PLAN + "\nLanes: none - documentation only\n",
                                     PLAN + FENCED_TABLE + FULL_TABLE],
                         ids=["table", "table-and-an-in-record-block", "waived", "fenced-and-real"])
@pytest.mark.parametrize("sibling", [False, True], ids=["no-demonstrated-file", "demonstrated-file"])
def test_old_and_new_helper_stamp_the_same_digest(tmp_path: Path, lanes, section, sibling) -> None:
    """One repository, one run, one record: the old helper's stamp and the new
    helper's, unmasked, for every record shape the new helper approves."""
    r = make_repo(tmp_path / "wt", lanes=lanes)
    begin(r, section, helper=BEFORE)
    if sibling:
        (r / "docs" / "flow-runs" / "issue-42.lanes-demonstrated.md").write_text(DEMONSTRATED)
    old = run(r, "approve", "42", helper=BEFORE)
    new = run(r, "approve", "42")
    assert old.returncode == 0 and new.returncode == 0, old.stdout + new.stdout + new.stderr
    assert re.search(r"baseline stamped [0-9a-f]{64}", old.stdout)
    assert old.stdout == new.stdout


def approved(repo: Path, section: str = PLAN + FULL_TABLE) -> Path:
    record = begin(repo, section)
    assert run(repo, "approve", "42").returncode == 0
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "plan")
    return record


def compliance(repo: Path) -> subprocess.CompletedProcess:
    return run(repo, "compliance", "42", "--base", git(repo, "rev-parse", "main").strip())


def stability(repo: Path) -> str:
    return next(ln for ln in compliance(repo).stdout.splitlines()
                if ln.startswith("PLAN_RECORD_STABILITY:"))


@pytest.mark.parametrize("edit", [
    IN_RECORD_BLOCK,
    IN_RECORD_BLOCK + "  2. `src/other.py` - slipped in | evidence\n",
    "\n   ### Section C addendum\n  2. `src/other.py` - slipped in\n",
    "\n",
], ids=["an-in-record-block", "the-pass-3-finding", "indented-heading", "one-blank-line-kept-quiet"])
def test_any_edit_to_an_approved_record_reads_as_changed(repo: Path, edit: str) -> None:
    """No part of the record is outside the digest - including a block named
    `Lanes demonstrated`, which was the exempt one in the earlier design."""
    record = approved(repo)
    assert "unchanged" in stability(repo), "precondition"
    with record.open("a") as fh:
        fh.write(edit)
    assert ("unchanged" if edit == "\n" else "CHANGED") in stability(repo)


def test_writing_the_demonstrated_file_does_not_touch_the_stability_verdict(repo: Path) -> None:
    approved(repo)
    (repo / "docs" / "flow-runs" / "issue-42.lanes-demonstrated.md").write_text(DEMONSTRATED)
    assert "unchanged" in stability(repo)


# --- the close-time note -----------------------------------------------------

SIBLING = Path("docs") / "flow-runs" / "issue-42.lanes-demonstrated.md"


def test_no_demonstrated_file_is_reported_with_the_lanes_owed(repo: Path) -> None:
    approved(repo)
    done = compliance(repo)
    assert f"no {SIBLING} - this plan answered `will test` for Checkout, Harness" in done.stderr
    assert "Project state" not in done.stderr, "not applicable owes no row"
    assert "lanes-demonstrated" not in done.stdout, "the file is named on stderr; the line names the lanes"


def test_a_will_test_lane_with_no_row_is_named(repo: Path) -> None:
    approved(repo)
    quiet = compliance(repo)
    (repo / SIBLING).write_text(DEMONSTRATED.replace("| Harness | tested through a symlink |\n", ""))
    partial = compliance(repo)
    assert f"has no row in {SIBLING} - Harness" in partial.stderr
    assert "- Checkout" not in partial.stderr
    assert partial.stdout.replace("\n", "") != "" and partial.returncode == quiet.returncode
    (repo / SIBLING).write_text(DEMONSTRATED.replace("tested through a symlink", " "))
    assert f"has no row in {SIBLING} - Harness" in compliance(repo).stderr, "an empty cell is no row"


def test_every_will_test_lane_demonstrated_draws_no_note(repo: Path) -> None:
    approved(repo)
    (repo / SIBLING).write_text(DEMONSTRATED)
    assert "lanes-demonstrated" not in compliance(repo).stderr


@pytest.mark.parametrize("kind", ["directory", "dangling symlink", "not text"])
def test_an_unreadable_demonstrated_file_is_unreadable_not_missing(repo: Path, kind: str) -> None:
    approved(repo)
    path = repo / SIBLING
    if kind == "directory":
        path.mkdir()
    elif kind == "dangling symlink":
        path.symlink_to(repo / "nowhere.md")
    else:
        path.write_bytes(b"\xff\xfe\x00\x80")
    done = compliance(repo)
    assert f"no {SIBLING}" not in done.stderr, "an unreadable file was reported as missing"
    assert "cannot be checked against what was demonstrated" in done.stderr
    assert "Checkout, Harness" in done.stderr


def test_rows_quoted_in_a_code_fence_are_not_rows(repo: Path) -> None:
    approved(repo)
    (repo / SIBLING).write_text("# Example\n\n```\n" + DEMONSTRATED + "```\n")
    assert f"has no row in {SIBLING} - Checkout" in compliance(repo).stderr


@pytest.mark.parametrize("why", ["no-lane-file", "waived", "nothing-will-test"])
def test_the_note_is_silent_where_nothing_is_owed(tmp_path: Path, why: str) -> None:
    section = PLAN + FULL_TABLE
    if why == "waived":
        section = PLAN + "\nLanes: none - documentation only\n"
    elif why == "nothing-will-test":
        section = PLAN + FULL_TABLE.replace("will test (Claude install); not covered (Codex install)",
                                            "not covered").replace("| Checkout | will test |",
                                                                   "| Checkout | will refuse |")
    r = make_repo(tmp_path / "wt", lanes=None if why == "no-lane-file" else LANES)
    approved(r, section)
    done = compliance(r)
    assert "lanes-demonstrated" not in done.stderr and "demonstrated" not in done.stderr


# --- the clause on the verdict line (#1767) -----------------------------------
#
# The note above is on stderr, and in its first three hours five changes merged
# without the file because their authors read the verdict line and not the
# note. So the same state is now on the line itself, right after the verdict
# word. The exit code does not change: the owner chose the line, not a refusal.

PRE_1767 = ROOT / "controls" / "flow-plan-record-lanes-verdict" / "anchors" / "pre-1767-flow-plan-record.py"
WAIVED = PLAN + "\nLanes: none - documentation only\n"
NOTHING_WILL_TEST = PLAN + FULL_TABLE.replace(
    "will test (Claude install); not covered (Codex install)", "not covered").replace(
    "| Checkout | will test |", "| Checkout | will refuse |")


def verdict(done: subprocess.CompletedProcess) -> str:
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("PLAN_COMPLIANCE: ")]
    assert len(lines) == 1, done.stdout
    return lines[0]


def compliance_as(repo: Path, word: str, helper: Path = HELPER) -> subprocess.CompletedProcess:
    """Compliance steered to one verdict word: the planned file is written for
    `agreement`, left unwritten for `divergence`, and the base is a ref that
    does not exist for `unknown`."""
    planned = repo / "src" / "app.py"
    if word == "agreement" and not planned.exists():
        planned.parent.mkdir(exist_ok=True)
        planned.write_text("x = 1\n")
    base = "no-such-ref" if word == "unknown" else git(repo, "rev-parse", "main").strip()
    done = run(repo, "compliance", "42", "--base", base, helper=helper)
    assert verdict(done).startswith(f"PLAN_COMPLIANCE: {word}"), done.stdout
    return done


WORDS = ("agreement", "divergence", "unknown")


@pytest.mark.parametrize("word", WORDS)
def test_a_will_test_lane_with_nothing_shown_is_on_the_verdict_line(repo: Path, word: str) -> None:
    approved(repo)
    line = verdict(compliance_as(repo, word))
    assert line.startswith(f"PLAN_COMPLIANCE: {word}, LANES NOT DEMONSTRATED (Checkout, Harness)"), line
    assert "Project state" not in line, "not applicable owes no row"


@pytest.mark.parametrize("word", WORDS)
def test_only_the_lanes_still_missing_are_named_and_a_full_file_clears_the_line(repo: Path, word: str) -> None:
    approved(repo)
    (repo / SIBLING).write_text(DEMONSTRATED.replace("| Harness | tested through a symlink |\n", ""))
    assert verdict(compliance_as(repo, word)).startswith(
        f"PLAN_COMPLIANCE: {word}, LANES NOT DEMONSTRATED (Harness)")
    (repo / SIBLING).write_text(DEMONSTRATED.replace("tested through a symlink", " "))
    assert ", LANES NOT DEMONSTRATED (Harness)" in verdict(compliance_as(repo, word)), "an empty cell is no row"
    (repo / SIBLING).write_text(DEMONSTRATED)
    assert "LANES" not in verdict(compliance_as(repo, word))


@pytest.mark.parametrize("kind", ["directory", "dangling symlink", "not text"])
def test_an_unreadable_demonstrated_file_reads_not_checked_never_clean(repo: Path, kind: str) -> None:
    approved(repo)
    path = repo / SIBLING
    if kind == "directory":
        path.mkdir()
    elif kind == "dangling symlink":
        path.symlink_to(repo / "nowhere.md")
    else:
        path.write_bytes(b"\xff\xfe\x00\x80")
    line = verdict(compliance_as(repo, "divergence"))
    assert line.startswith("PLAN_COMPLIANCE: divergence, LANES NOT CHECKED ("), line
    assert "NOT DEMONSTRATED" not in line, "unreadable was reported as missing"


def _damage_lane_file(repo: Path, how: str) -> None:
    lane_file = repo / ".claude" / "lanes.md"
    if how == "absent":
        if lane_file.exists():
            lane_file.unlink()
        return
    lane_file.parent.mkdir(exist_ok=True)
    if lane_file.exists():
        lane_file.unlink()
    if how == "present":
        lane_file.write_text(LANES)
    elif how == "unusable":
        lane_file.mkdir()
    else:
        raise AssertionError(how)


def test_a_lane_file_that_cannot_be_read_at_close_is_not_checked_on_the_line(repo: Path) -> None:
    """At approval an unusable lane file refuses. At close the plan is already
    approved, so the answer is on the line: could not check - not silence, and
    not the clean line a project without lanes gets."""
    approved(repo)
    (repo / SIBLING).write_text(DEMONSTRATED)
    assert "LANES" not in verdict(compliance_as(repo, "divergence")), "precondition: clean before the damage"
    _damage_lane_file(repo, "unusable")
    done = compliance_as(repo, "divergence")
    assert verdict(done).startswith(
        "PLAN_COMPLIANCE: divergence, LANES NOT CHECKED (.claude/lanes.md is not a regular file)")
    assert "was not checked" in done.stderr


BYTE_IDENTICAL = {
    "no-lane-file": (None, PLAN + FULL_TABLE, False),
    "waived": (LANES, WAIVED, False),
    "nothing-will-test": (LANES, NOTHING_WILL_TEST, False),
}


@pytest.mark.parametrize("word", ["agreement", "divergence"])
@pytest.mark.parametrize("case", sorted(BYTE_IDENTICAL))
def test_where_nothing_is_owed_a_file_at_the_demonstrated_path_is_still_a_touched_file(
        tmp_path: Path, case: str, word: str) -> None:
    """The exclusion of the demonstrated file applies only where a lane result
    is owed. Anywhere else the old helper called a file at that path TOUCHED
    BUT NOT PLANNED, and so does this one: same stdout, same exit code."""
    lanes, section, _unused = BYTE_IDENTICAL[case]
    r = make_repo(tmp_path / "wt", lanes=lanes)
    approved(r, section)
    (r / SIBLING).write_text(DEMONSTRATED)
    base = git(r, "rev-parse", "main").strip()
    if word == "agreement":
        (r / "src").mkdir()
        (r / "src" / "app.py").write_text("x = 1\n")
    new = run(r, "compliance", "42", "--base", base)
    old = run(r, "compliance", "42", "--base", base, helper=PRE_1767)
    assert f"TOUCHED BUT NOT PLANNED: {SIBLING}" in old.stdout, "precondition: the old helper counts it"
    strip = lambda s: re.sub(r"FLOW_PLAN_RECORD_SELF: .*\n", "", s)   # noqa: E731
    assert strip(new.stdout) == strip(old.stdout)
    assert (new.returncode, new.stderr) == (old.returncode, old.stderr)


@pytest.mark.parametrize("word", WORDS)
@pytest.mark.parametrize("case", sorted(BYTE_IDENTICAL))
def test_where_nothing_is_owed_stdout_is_what_it_was_before(tmp_path: Path, case: str, word: str) -> None:
    """The whole of stdout, and the exit code, against the helper as it was
    before this change - for each verdict word. This is what keeps a project
    with no lane file unaffected: its line does not change by one byte."""
    lanes, section, _unused = BYTE_IDENTICAL[case]
    r = make_repo(tmp_path / "wt", lanes=lanes)
    approved(r, section)
    new = compliance_as(r, word)
    old = compliance_as(r, word, helper=PRE_1767)
    strip = lambda s: re.sub(r"FLOW_PLAN_RECORD_SELF: .*\n", "", s)   # noqa: E731
    assert strip(new.stdout) == strip(old.stdout)
    assert new.returncode == old.returncode
    assert new.stderr == old.stderr


@pytest.mark.parametrize("committed", [False, True])
def test_writing_the_demonstrated_file_does_not_itself_make_a_divergence(repo: Path, committed: bool) -> None:
    """The file the line asks for is the run's own record, like the plan record
    beside it. Before #1767 it counted as a touched file nobody planned, so
    writing it turned `agreement` into `divergence`; that is the one place the
    line for a run with every lane demonstrated differs from the old helper's."""
    approved(repo)
    assert verdict(compliance_as(repo, "agreement")).startswith(
        "PLAN_COMPLIANCE: agreement, LANES NOT DEMONSTRATED (Checkout, Harness) - "), "precondition"
    (repo / SIBLING).write_text(DEMONSTRATED)
    if committed:
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "work and lanes")
    new = compliance_as(repo, "agreement")
    assert verdict(new).startswith("PLAN_COMPLIANCE: agreement - the FILE SET matches the approved plan (")
    assert str(SIBLING) not in new.stdout and new.returncode == 0
    old = run(repo, "compliance", "42", "--base", git(repo, "rev-parse", "main").strip(), helper=PRE_1767)
    assert f"TOUCHED BUT NOT PLANNED: {SIBLING}" in old.stdout, "the old helper is where this was a divergence"


def test_a_demonstrated_file_for_another_issue_is_still_a_touched_file(repo: Path) -> None:
    approved(repo)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    other = repo / "docs" / "flow-runs" / "issue-43.lanes-demonstrated.md"
    other.write_text(DEMONSTRATED)
    done = run(repo, "compliance", "42", "--base", git(repo, "rev-parse", "main").strip())
    assert "TOUCHED BUT NOT PLANNED: docs/flow-runs/issue-43.lanes-demonstrated.md" in done.stdout


@pytest.mark.parametrize("word", WORDS)
def test_the_clause_is_the_only_change_and_the_exit_code_does_not_move(repo: Path, word: str) -> None:
    """Where a lane IS owed: remove the clause and stdout is the old stdout."""
    approved(repo)
    new = compliance_as(repo, word)
    old = compliance_as(repo, word, helper=PRE_1767)
    assert ", LANES NOT DEMONSTRATED (Checkout, Harness)" in new.stdout
    strip = lambda s: re.sub(r"FLOW_PLAN_RECORD_SELF: .*\n", "", s)   # noqa: E731
    assert strip(new.stdout).replace(", LANES NOT DEMONSTRATED (Checkout, Harness)", "") == strip(old.stdout)
    assert new.returncode == old.returncode
    assert old.stderr.strip().splitlines()[0] in new.stderr, "the note still opens as it did"
    assert "a header row, a `|---|---|` row, then `| <lane> | <what was demonstrated> |`" in new.stderr


HOSTILE_LANE = "Checkout) - linked worktree, 100% (really)"


def test_a_lane_name_cannot_end_or_split_the_clause(tmp_path: Path) -> None:
    """A lane file may name a lane anything. One carrying the clause's own
    delimiters is approved like any other; in the clause it is encoded, so the
    parenthesised list still ends where it ends and splits where it splits."""
    from urllib.parse import unquote

    lanes = LANES.replace("| Checkout |", f"| {HOSTILE_LANE} |")
    section = PLAN + FULL_TABLE.replace("| Checkout |", f"| {HOSTILE_LANE} |")
    r = make_repo(tmp_path / "wt", lanes=lanes)
    approved(r, section)
    line = verdict(compliance_as(r, "divergence"))
    listed = re.fullmatch(r"PLAN_COMPLIANCE: divergence, LANES NOT DEMONSTRATED \(([^()]*)\) - "
                          r"the change and its approved plan disagree\.", line)
    assert listed, line
    assert [unquote(name) for name in listed.group(1).split(", ")] == [HOSTILE_LANE, "Harness"]
    (r / SIBLING).write_text(DEMONSTRATED.replace("| Checkout |", f"| {HOSTILE_LANE} |"))
    assert "LANES" not in verdict(compliance_as(r, "divergence")), "the name still matches its own row"


def test_an_ordinary_lane_name_is_printed_as_written() -> None:
    helper = _load_helper()
    for name in ("Checkout", "CI provider", "Project state", "A_B", "Lane-2 / other"):
        assert helper.clause_lane(name) == name


@pytest.mark.parametrize("kind", ["directory", "dangling symlink", "not text"])
def test_a_reason_cannot_end_the_clause_either(repo: Path, kind: str) -> None:
    """The could-not-check reasons carry parentheses of their own."""
    approved(repo)
    path = repo / SIBLING
    if kind == "directory":
        path.mkdir()
    elif kind == "dangling symlink":
        path.symlink_to(repo / "nowhere.md")
    else:
        path.write_bytes(b"\xff\xfe\x00\x80")
    line = verdict(compliance_as(repo, "divergence"))
    assert re.fullmatch(r"PLAN_COMPLIANCE: divergence, LANES NOT CHECKED \([^()\n]+\) - "
                        r"the change and its approved plan disagree\.", line), line


def _load_helper():
    import importlib.util

    spec = importlib.util.spec_from_file_location("flow_plan_record_under_test", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LANE_FILE_STATES = ("absent", "present", "unusable")
PLAN_STATES = {"table": PLAN + FULL_TABLE, "waived": WAIVED, "no-table": PLAN}
SHOWN_STATES = ("present", "missing", "unreadable")


def _expected_state(lane_file: str, plan: str, shown: str) -> str:
    if lane_file == "absent":
        return "nothing-owed"
    if lane_file == "unusable":
        return "not-checked"
    if plan != "table":
        return "nothing-owed"
    return {"present": "all-shown", "missing": "missing", "unreadable": "not-checked"}[shown]


@pytest.mark.parametrize("shown", SHOWN_STATES)
@pytest.mark.parametrize("plan", sorted(PLAN_STATES))
@pytest.mark.parametrize("lane_file", LANE_FILE_STATES)
def test_every_combination_lands_in_exactly_one_of_the_four_states(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lane_file: str, plan: str, shown: str) -> None:
    """Lane file x plan table x demonstrated file: 27 combinations, each in one
    named state, and the line and the note both follow from that state alone."""
    # Approved with no lane file (approval then accepts any of the three plans),
    # and the lane file put into its state afterwards.
    r = make_repo(tmp_path / "wt", lanes=None)
    approved(r, PLAN_STATES[plan])
    _damage_lane_file(r, lane_file)
    if shown == "present":
        (r / SIBLING).write_text(DEMONSTRATED)
    elif shown == "unreadable":
        (r / SIBLING).mkdir()
    helper = _load_helper()
    monkeypatch.chdir(r)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-lanes")
    at_close = helper.lanes_at_close("42")
    assert at_close.state in helper.LANES_AT_CLOSE_STATES
    assert len(helper.LANES_AT_CLOSE_STATES) == 4
    assert at_close.state == _expected_state(lane_file, plan, shown)
    clause, note = helper.lanes_clause(at_close), helper.lanes_note(at_close)
    quiet = at_close.state in ("nothing-owed", "all-shown")
    assert (clause == "") is quiet and (note == []) is quiet, "the line and the note disagree"
    done = compliance_as(r, "divergence")
    assert verdict(done) == f"PLAN_COMPLIANCE: divergence{clause} - the change and its approved plan disagree."
    assert [ln for ln in done.stderr.splitlines() if ln.startswith("flow-plan-record: ")] == note


def test_the_combination_table_reaches_all_four_states() -> None:
    reached = {_expected_state(a, b, c) for a in LANE_FILE_STATES for b in PLAN_STATES for c in SHOWN_STATES}
    assert reached == {"nothing-owed", "all-shown", "missing", "not-checked"}


def test_a_run_with_no_section_in_the_record_is_not_checked(repo: Path) -> None:
    """A lane file, and a record this run never wrote to: nothing can be said
    about what it owes, and that is said."""
    done = run(repo, "compliance", "42", "--base", git(repo, "rev-parse", "main").strip())
    assert verdict(done).startswith("PLAN_COMPLIANCE: unknown, LANES NOT CHECKED ("), done.stdout


def test_a_lane_name_with_something_appended_is_unanswered_and_the_refusal_says_why(repo: Path) -> None:
    """Exact names are the rule (A_B is not AB), so the refusal has to say so:
    a real plan wrote the lane's values after its name and was told only that
    the lane was unanswered."""
    table = FULL_TABLE.replace("| Checkout |", "| Checkout (main checkout / linked worktree) |")
    begin(repo, PLAN + table)
    done = run(repo, "approve", "42")
    assert done.returncode == 1 and "unanswered: Checkout." in done.stdout
    assert "first cell is the lane's name exactly as .claude/lanes.md lists it" in done.stdout
