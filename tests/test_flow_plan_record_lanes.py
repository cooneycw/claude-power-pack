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
- The stability digest leaves out the `Lanes demonstrated` block and nothing
  else, so the block cannot be used to hide a plan edit.
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


# --- the stability digest leaves out one block and only that block -----------

DEMONSTRATED = """
### Lanes demonstrated

| Lane | What happened |
|---|---|
| Checkout | tested in a linked worktree |
| Harness | tested through a symlink |
"""


def approved(repo: Path, section: str = PLAN + FULL_TABLE) -> Path:
    record = begin(repo, section)
    assert run(repo, "approve", "42").returncode == 0
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "plan")
    return record


def stability(repo: Path) -> str:
    base = git(repo, "rev-parse", "main").strip()
    out = run(repo, "compliance", "42", "--base", base).stdout
    return next(ln for ln in out.splitlines() if ln.startswith("PLAN_RECORD_STABILITY:"))


def test_adding_the_demonstrated_block_does_not_read_as_a_changed_plan(repo: Path) -> None:
    record = approved(repo)
    assert "unchanged" in stability(repo), "precondition"
    with record.open("a") as fh:
        fh.write(DEMONSTRATED)
    assert "unchanged" in stability(repo)


def test_a_plan_line_added_after_the_block_still_reads_as_changed(repo: Path) -> None:
    """The block must not be a place to hide an edit: only the block itself is
    outside the digest, not everything below its heading."""
    record = approved(repo)
    with record.open("a") as fh:
        fh.write(DEMONSTRATED + "\n### Section C addendum\n  2. `src/other.py` - slipped in later\n")
    assert "CHANGED" in stability(repo)


def test_a_plan_line_added_before_the_block_still_reads_as_changed(repo: Path) -> None:
    record = approved(repo)
    text = record.read_text().replace("Scope: 1 file", "  2. `src/other.py` - slipped in\nScope: 1 file")
    record.write_text(text + DEMONSTRATED)
    assert "CHANGED" in stability(repo)


def test_an_edit_to_the_approval_table_still_reads_as_changed(repo: Path) -> None:
    record = approved(repo)
    record.write_text(record.read_text().replace("| Checkout | will test |", "| Checkout | not covered |")
                      + DEMONSTRATED)
    assert "CHANGED" in stability(repo)


def test_a_record_stamped_before_this_change_keeps_its_digest(tmp_path: Path) -> None:
    """Records approved before this lands are not re-judged: the old helper's
    stamp is the new helper's digest for a section with no demonstrated block."""
    r = make_repo(tmp_path / "wt", lanes=None)
    begin(r, PLAN + FULL_TABLE, helper=BEFORE)
    assert run(r, "approve", "42", helper=BEFORE).returncode == 0
    git(r, "add", "-A")
    git(r, "commit", "-qm", "plan")
    assert "unchanged" in stability(r)


# --- the close-time note -----------------------------------------------------

def compliance(repo: Path) -> subprocess.CompletedProcess:
    return run(repo, "compliance", "42", "--base", git(repo, "rev-parse", "main").strip())


def test_a_will_test_lane_with_no_demonstrated_row_is_named_on_stderr(repo: Path) -> None:
    record = approved(repo)
    quiet = compliance(repo)
    assert "has no row under `### Lanes demonstrated` - Checkout" in quiet.stderr
    assert "- Harness" in quiet.stderr
    assert "Project state" not in quiet.stderr, "not applicable owes no row"
    with record.open("a") as fh:
        fh.write(DEMONSTRATED.replace("| Harness | tested through a symlink |\n", ""))
    partial = compliance(repo)
    assert "- Harness" in partial.stderr and "- Checkout" not in partial.stderr
    assert "Lanes demonstrated" not in partial.stdout, "the note is stderr only"
    assert partial.returncode == quiet.returncode, "the note changes no verdict"


def test_every_will_test_lane_demonstrated_draws_no_note(repo: Path) -> None:
    record = approved(repo)
    with record.open("a") as fh:
        fh.write(DEMONSTRATED)
    assert "Lanes demonstrated" not in compliance(repo).stderr


def test_a_record_approved_before_the_check_draws_no_note(tmp_path: Path) -> None:
    """Not re-judged: approved by the old helper, checked at close by the new."""
    r = make_repo(tmp_path / "wt")
    begin(r, PLAN + FULL_TABLE, helper=BEFORE)
    assert run(r, "approve", "42", helper=BEFORE).returncode == 0
    git(r, "add", "-A")
    git(r, "commit", "-qm", "plan")
    assert "Lanes demonstrated" not in compliance(r).stderr


def test_a_waived_plan_draws_no_note(repo: Path) -> None:
    approved(repo, PLAN + "\nLanes: none - documentation only\n")
    assert "Lanes demonstrated" not in compliance(repo).stderr


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


def test_a_fenced_demonstrated_heading_does_not_open_the_digest(repo: Path) -> None:
    """A quoted `### Lanes demonstrated` is example text that was approved.
    Editing what follows it must read as a changed plan."""
    example = "\n```markdown\n### Lanes demonstrated\n\nthe approved example text\n```\n"
    record = approved(repo, PLAN + FULL_TABLE + example)
    assert "unchanged" in stability(repo), "precondition"
    record.write_text(record.read_text().replace("the approved example text", "something else"))
    assert "CHANGED" in stability(repo)


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


# The digest changes ONLY for a baseline whose approval ran the lanes check.

WITH_BLOCK = PLAN + FULL_TABLE + DEMONSTRATED


def test_with_no_lane_file_the_digest_is_the_old_digest_unmasked(tmp_path: Path) -> None:
    """One repository, one run, one record that already carries a
    `Lanes demonstrated` heading: the old helper and the new must stamp the
    SAME 64 characters. The first cut left the block out for everyone."""
    r = make_repo(tmp_path / "wt", lanes=None)
    begin(r, WITH_BLOCK, helper=BEFORE)
    old = run(r, "approve", "42", helper=BEFORE)
    new = run(r, "approve", "42")
    assert old.returncode == 0 and new.returncode == 0
    assert "baseline stamped" in old.stdout
    assert old.stdout == new.stdout and old.stderr == new.stderr


def test_a_baseline_stamped_by_the_old_helper_is_still_unchanged_for_the_new(tmp_path: Path) -> None:
    for lanes in (None, LANES):
        r = make_repo(tmp_path / f"wt-{bool(lanes)}", lanes=lanes)
        begin(r, WITH_BLOCK, helper=BEFORE)
        assert run(r, "approve", "42", helper=BEFORE).returncode == 0
        git(r, "add", "-A")
        git(r, "commit", "-qm", "plan")
        assert "unchanged" in stability(r)


def test_without_the_lanes_check_the_block_is_digested_like_any_text(tmp_path: Path) -> None:
    """No lane file, or a waived plan: nothing was promised about that block,
    so adding one after approval reads as the change it is."""
    r = make_repo(tmp_path / "wt", lanes=None)
    record = approved(r, PLAN)
    with record.open("a") as fh:
        fh.write(DEMONSTRATED)
    assert "CHANGED" in stability(r)


def test_a_legacy_record_approved_under_the_check_may_gain_the_block(repo: Path) -> None:
    """A record with no run markers is hashed whole. Approved under the lanes
    check, it gets the same one-block allowance as a marked run."""
    record = repo / "docs" / "flow-runs" / "issue-42.md"
    record.parent.mkdir(parents=True)
    record.write_text("# Flow run record - issue #42\n" + PLAN + FULL_TABLE)
    assert not (Path(git(repo, "rev-parse", "--absolute-git-dir").strip()) / "flow-run-42").exists()
    done = run(repo, "approve", "42")
    assert "baseline stamped" in done.stdout, done.stdout + done.stderr
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "plan")
    assert "unchanged" in stability(repo), "precondition"
    with record.open("a") as fh:
        fh.write(DEMONSTRATED)
    assert "unchanged" in stability(repo)
    with record.open("a") as fh:
        fh.write("\n### Later\n  2. `src/other.py` - slipped in\n")
    assert "CHANGED" in stability(repo)
