"""The review prompt asks only what the plan-record helper cannot catch (issue #1863).

`scripts/codex-review-run.sh` asks the counter-model reviewer questions about
the plan record. A question `flow-plan-record.py` already enforces costs a
review finding and catches nothing new, so it is dropped - but only when the
helper catches it. This file holds that split, clause by clause, against the
REAL helper:

- A DROPPED clause has a fixture the clause would have flagged, and `approve`
  refuses it. If the helper stops refusing, this goes red and the clause has
  to come back.
- A KEPT clause has a fixture the clause flags and the helper lets through,
  and the prompt still carries the clause. If someone trims the clause while
  the helper still misses its case, this goes red.

It does not run the reviewing model; whether a model answers a kept question
well is an observation, recorded in `docs/agents/lanes.md`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HELPER = REPO / "scripts" / "flow-plan-record.py"
REVIEW_HELPER = REPO / "scripts" / "codex-review-run.sh"
FIXTURES = REPO / "tests" / "fixtures" / "lanes"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

#: Dropped by #1863 - `approve` refuses what it asked about.
DROPPED_UNANSWERED_LANE = "each listed lane that the plan's 'Lanes for this change' table in this diff does not answer"
DROPPED_NO_TABLE = "with no such table, say so once"
#: Kept - the helper misses what these ask about.
KEPT_UNTESTED_LANE = "each lane the plan marks 'will test' that no test in the diff exercises"
KEPT_READER = "report each reader with no 'Reader:' row in the plan's table"

HEADER = "- Approval:          granted\n\n"


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def review_prompt() -> str:
    text = REVIEW_HELPER.read_text(encoding="utf-8")
    start = text.index('"You are reviewing a code change as an independent reviewer.')
    return normalized(text[start : text.index('> "$STREAM"', start)])


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")}
    env["CLAUDE_CODE_SESSION_ID"] = "session-parity"
    return subprocess.run([sys.executable, str(HELPER), *args], cwd=repo, capture_output=True,
                          text=True, env=env)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository that has adopted lanes, with the fixture lane list."""
    path = tmp_path / "wt"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@example.invalid")
    git(path, "config", "user.name", "t")
    (path / ".claude").mkdir()
    shutil.copy(FIXTURES / "lanes.md", path / ".claude" / "lanes.md")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "base")
    git(path, "checkout", "-q", "-b", "issue-42-parity")
    return path


def approve(repo: Path, section: str) -> subprocess.CompletedProcess:
    body = repo.parent / "body.md"
    body.write_text("The issue body.\n")
    for args in (("reconcile", "42"), ("read-issue", "42", "--body-file", str(body)),
                 ("begin-run", "42")):
        done = run(repo, *args)
        assert done.returncode == 0, done.stdout + done.stderr
    with (repo / "docs" / "flow-runs" / "issue-42.md").open("a") as fh:
        fh.write(HEADER + section)
    return run(repo, "approve", "42")


def stamped(repo: Path) -> bool:
    return (Path(git(repo, "rev-parse", "--absolute-git-dir").strip()) / "flow-plan-baseline-42").exists()


def commit_files(repo: Path, *rels: str) -> None:
    for rel in rels:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# changed\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "impl")


def compliance(repo: Path) -> subprocess.CompletedProcess:
    return run(repo, "compliance", "42", "--base", "main")


# --- dropped: an unanswered listed lane, and a missing lanes table -----------------


def test_the_prompt_no_longer_asks_the_dropped_lane_question() -> None:
    prompt = review_prompt()
    assert DROPPED_UNANSWERED_LANE not in prompt
    assert DROPPED_NO_TABLE not in prompt


def test_approve_refuses_the_plan_the_dropped_question_flagged(repo: Path) -> None:
    """The very fixture the question was validated on (2026-11-11, docs/agents/lanes.md)."""
    plan = (FIXTURES / "plan-omits-lane.md").read_text(encoding="utf-8")
    assert "| Session age |" not in plan  # the precondition: the lane really is omitted
    done = approve(repo, plan)
    assert done.returncode == 1, done.stdout
    assert "leaves these listed lanes unanswered: Session age." in done.stdout
    assert not stamped(repo)


def test_approve_accepts_the_same_plan_answering_every_lane(repo: Path) -> None:
    """Red pair for the refusal above: it is about the omitted lane, not the fixture."""
    done = approve(repo, (FIXTURES / "plan-complete.md").read_text(encoding="utf-8"))
    assert done.returncode == 0, done.stdout + done.stderr
    assert stamped(repo)


def test_approve_refuses_a_plan_with_no_lanes_table(repo: Path) -> None:
    plan = (FIXTURES / "plan-omits-lane.md").read_text(encoding="utf-8")
    plan = plan[: plan.index("### Lanes for this change")]
    assert "Lanes for this change" not in plan and "Lanes:" not in plan  # the precondition
    done = approve(repo, plan)
    assert done.returncode == 1, done.stdout
    assert "the plan record has no lanes table" in done.stdout
    assert not stamped(repo)


# --- kept: a will-test lane no test exercises ----------------------------------------


def demonstrated(repo: Path, evidence: str | None) -> None:
    """Write this run's demonstrated rows; None writes no file at all."""
    if evidence is None:
        return
    stamp = json.loads((Path(git(repo, "rev-parse", "--absolute-git-dir").strip())
                        / "flow-plan-lanes-42").read_text())
    rows = "\n".join(f"| {lane} | {evidence} |" for lane in stamp["owed"])
    (repo / "docs" / "flow-runs" / "issue-42.lanes-demonstrated.md").write_text(
        f"<!-- lanes-demonstrated run={stamp['run_id']} plan={stamp['plan_digest']} -->\n\n"
        f"| Lane | Result |\n|---|---|\n{rows}\n")


@pytest.mark.parametrize("evidence,caught", [
    (None, True),
    ("passed - tests/test_archive.py::test_does_not_exist", False),
], ids=["no-demonstrated-row", "row-names-a-test-that-does-not-exist"])
def test_the_helper_misses_a_will_test_lane_no_test_exercises(
    repo: Path, evidence: str | None, caught: bool
) -> None:
    """The case the kept question asks about: a row names a test the diff never adds.

    The `no-demonstrated-row` case is the negative control: the close-time
    lane clause is live, so its silence on the other case is a real miss and
    not a blind check."""
    assert approve(repo, (FIXTURES / "plan-complete.md").read_text(encoding="utf-8")).returncode == 0
    demonstrated(repo, evidence)
    commit_files(repo, "app/records/archive.py", "app/templates/records_card.html", "tests/test_archive.py")
    assert "test_does_not_exist" not in (repo / "tests" / "test_archive.py").read_text()  # the precondition
    done = compliance(repo)
    assert done.returncode == 0, done.stdout + done.stderr
    verdict = next(line for line in done.stdout.splitlines() if line.startswith("PLAN_COMPLIANCE:"))
    assert ("LANES NOT" in verdict) is caught, verdict


def test_the_prompt_keeps_the_will_test_question() -> None:
    assert KEPT_UNTESTED_LANE in review_prompt()


# --- kept: a changed output with no Reader row --------------------------------------

READER_PLAN = """## Section C - the approved plan
1. `scripts/gate.sh` - change the refusal exit code from 1 to 3
Scope: 1 file
Risks: a caller reading exit 1

Lanes: none - no listed lane is reached by an exit-code change
"""


GATE = "scripts/gate.sh"
CALLER = "scripts/finish.sh"


def test_the_helper_misses_a_changed_output_with_no_reader_row(repo: Path) -> None:
    """A real output change: the base has a gate exiting 1 and a caller that reads
    that status; the diff changes the gate to exit 3 and names no reader."""
    git(repo, "checkout", "-q", "main")
    (repo / "scripts").mkdir()
    (repo / GATE).write_text("#!/bin/sh\nexit 1\n")
    (repo / CALLER).write_text('#!/bin/sh\nsh scripts/gate.sh\n[ "$?" -eq 1 ] && echo refused\n')
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "gate and its caller")
    git(repo, "checkout", "-q", "issue-42-parity")
    git(repo, "merge", "-q", "--ff-only", "main")
    assert "Reader:" not in READER_PLAN  # the precondition: no reader row
    done = approve(repo, READER_PLAN)
    assert done.returncode == 0, done.stdout + done.stderr
    (repo / GATE).write_text("#!/bin/sh\nexit 3\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "gate exits 3")
    diff = git(repo, "diff", "main", "--", GATE)
    assert "-exit 1" in diff and "+exit 3" in diff  # the precondition: the output changed
    assert "-eq 1" in (repo / CALLER).read_text()  # the precondition: a reader of it exists
    done = compliance(repo)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PLAN_COMPLIANCE: agreement" in done.stdout
    assert "reader" not in (done.stdout + done.stderr).lower()


def test_the_prompt_keeps_the_reader_question() -> None:
    assert KEPT_READER in review_prompt()
