"""`flow-plan-record.py compliance` leaves the index as it found it (issue #1713).

Compliance marks untracked files intent-to-add so `git diff <ref>` can see a
brand-new file. It never took those marks back. The index then held entries
nobody asked for: a later `git merge` could refuse to start, and `git status`
showed new files as added. The marks are now undone on every exit.

Also here: `approve` says, at approve time, which Section C lines compliance
will not be able to parse, without changing what callers read.
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

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")


@pytest.fixture(autouse=True)
def isolated_session_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let the test runner's real session own a fixture run."""
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout


def helper(repo: Path, *args: str, session: str = "session-index") -> subprocess.CompletedProcess:
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID=session)
    return subprocess.run(["python3", str(HELPER), *args], cwd=repo, capture_output=True,
                          text=True, env=env)


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, str]:
    r = tmp_path / "wt"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@e.com")
    git(r, "config", "user.name", "t")
    (r / "README.md").write_text("base\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "base")
    base = git(r, "rev-parse", "HEAD").strip()
    git(r, "checkout", "-q", "-b", "issue-42-a-fixture")
    d = r / "docs" / "flow-runs"
    d.mkdir(parents=True)
    (d / "issue-42.md").write_text(
        "# Flow run record - issue #42\n## Section C - the approved plan\n"
        "  1. `src/app.py` - because\nScope: 1 file\n"
    )
    git(r, "add", "-A")
    git(r, "commit", "-qm", "plan")
    return r, base


def index_state(repo: Path) -> tuple[str, str]:
    """What the index holds, and how git describes the tree against it."""
    return git(repo, "ls-files", "--stage"), git(repo, "status", "--porcelain=v1", "-uall")


def test_the_index_is_unchanged_after_a_normal_run(repo) -> None:
    r, base = repo
    (r / "src").mkdir()
    (r / "src" / "app.py").write_text("a\n")       # planned, untracked
    (r / "scratch.txt").write_text("notes\n")      # unplanned, untracked
    before = index_state(r)
    assert "?? src/app.py" in before[1], "precondition: the new file is untracked"
    proc = helper(r, "compliance", "42", "--base", base)
    assert proc.returncode in (0, 3), proc.stdout + proc.stderr
    assert "TOUCHED BUT NOT PLANNED: scratch.txt" in proc.stdout, "the new files were still compared"
    assert index_state(r) == before


def test_the_index_is_unchanged_when_the_diff_cannot_be_taken(repo) -> None:
    """The case that matters most: an UNKNOWN exit used to leave the marks behind
    too, and that is the run nobody looks at twice."""
    r, _base = repo
    (r / "src").mkdir()
    (r / "src" / "app.py").write_text("a\n")
    before = index_state(r)
    assert "?? src/app.py" in before[1], "precondition: the new file is untracked"
    proc = helper(r, "compliance", "42", "--base", "no-such-ref")
    assert proc.returncode == 4, f"expected an UNKNOWN verdict, got {proc.returncode}\n{proc.stdout}"
    assert "PLAN_COMPLIANCE: unknown" in proc.stdout
    assert index_state(r) == before


def test_an_entry_the_caller_marked_before_the_run_survives(repo) -> None:
    """Only what compliance itself marked is undone. A file the caller had
    already marked intent-to-add was in the index, so it was never 'untracked'."""
    r, base = repo
    (r / "mine.py").write_text("mine\n")
    (r / "other.py").write_text("other\n")
    git(r, "add", "-N", "mine.py")
    before = index_state(r)
    assert " A mine.py" in before[1] and "?? other.py" in before[1], f"precondition:\n{before[1]}"
    proc = helper(r, "compliance", "42", "--base", base)
    assert proc.returncode in (0, 3), proc.stdout + proc.stderr
    assert index_state(r) == before


# --- approve: say now what compliance will not be able to parse ---------------

def _record(repo: Path, section_c_lines: list[str], elsewhere: str = "") -> None:
    assert helper(repo, "reconcile", "42").returncode == 0
    assert helper(repo, "begin-run", "42").returncode == 0
    path = repo / "docs" / "flow-runs" / "issue-42.md"
    with path.open("a") as fh:
        fh.write("- Approval:          granted\n")
        if elsewhere:
            fh.write("\n### Gate conditions\n" + elsewhere + "\n")
        fh.write("\n### Section C - the approved plan\n".replace("### Section C", "## Section C"))
        fh.write("\n".join(section_c_lines) + "\nScope: some files\n")


def _shape(stdout: str) -> str:
    return re.sub(r"[0-9a-f]{64}", "<digest>", stdout)


def test_approve_names_a_section_c_line_compliance_cannot_parse(repo) -> None:
    r, _ = repo
    _record(r, ["1. `src/app.py` - because", "2. src/b.py: a colon is not the documented separator"])
    proc = helper(r, "approve", "42")
    assert "will read UNKNOWN at compliance" in proc.stderr
    assert "src/b.py: a colon" in proc.stderr
    assert "src/app.py" not in proc.stderr, "a parseable line must not be reported"
    assert "will read UNKNOWN" not in proc.stdout, "the note is stderr only"


def test_the_note_changes_neither_stdout_nor_the_exit_code(tmp_path: Path, repo) -> None:
    r, _ = repo
    _record(r, ["1. `src/app.py` - because"])
    good = helper(r, "approve", "42")
    assert good.stderr.count("will read UNKNOWN") == 0, "precondition: a clean plan draws no note"
    path = r / "docs" / "flow-runs" / "issue-42.md"
    path.write_text(path.read_text().replace(
        "1. `src/app.py` - because", "1. `src/app.py` - because\n2. src/b.py: colon form"))
    noted = helper(r, "approve", "42")
    assert noted.stderr.count("will read UNKNOWN") == 1
    assert noted.returncode == good.returncode
    assert _shape(noted.stdout) == _shape(good.stdout)


def test_a_numbered_line_outside_section_c_is_not_reported(repo) -> None:
    """A plan record carries numbered lines that are not planned files (gate
    conditions, evidence). Only Section C is the file list."""
    r, _ = repo
    _record(r, ["1. `src/app.py` - because"],
            elsewhere="1. Three tests, each red where it can be\n2. make lint before the gate")
    proc = helper(r, "approve", "42")
    assert "will read UNKNOWN" not in proc.stderr, proc.stderr


# --- the cleanup must touch ONLY the entries compliance created ---------------
# Both found by the counter-model review of the first cut, which used `git reset`.

def test_a_staged_deletion_whose_file_is_still_on_disk_survives(repo) -> None:
    """`git rm --cached f` leaves f on disk, so f is listed as untracked and
    compliance marks it. `git reset -- f` would then restore f's HEAD entry and
    undo the caller's staged deletion."""
    r, base = repo
    git(r, "rm", "--cached", "-q", "README.md")
    before = index_state(r)
    assert "D  README.md" in before[1] and "?? README.md" in before[1], f"precondition:\n{before[1]}"
    proc = helper(r, "compliance", "42", "--base", base)
    assert proc.returncode in (0, 3), proc.stdout + proc.stderr
    assert index_state(r) == before


def test_a_file_named_like_a_pattern_does_not_touch_its_neighbours(repo) -> None:
    """A path is data. An untracked file literally named `*.txt`, passed to git
    as a pathspec, matches every `.txt` file and would unstage the caller's
    staged change to a neighbour."""
    r, base = repo
    (r / "notes.txt").write_text("v1\n")
    git(r, "add", "notes.txt")
    git(r, "commit", "-qm", "notes")
    (r / "notes.txt").write_text("v2 staged by the caller\n")
    git(r, "add", "notes.txt")
    (r / "*.txt").write_text("a file whose name is a glob\n")
    before = index_state(r)
    assert "M  notes.txt" in before[1] and "?? *.txt" in before[1], f"precondition:\n{before[1]}"
    proc = helper(r, "compliance", "42", "--base", base)
    assert proc.returncode in (0, 3), proc.stdout + proc.stderr
    assert index_state(r) == before


# --- lanes (docs/agents/lanes.md) ---------------------------------------------

def test_the_index_is_restored_in_a_linked_worktree(repo, tmp_path: Path) -> None:
    """Lane: Checkout, linked worktree. A linked worktree has its OWN index, and
    a flow run always executes compliance from one. The other tests here run in
    the main checkout of their fixture."""
    r, base = repo
    wt = tmp_path / "linked"
    git(r, "worktree", "add", "-q", "-b", "issue-42-linked", str(wt), "issue-42-a-fixture")
    assert (wt / ".git").is_file(), "precondition: a linked worktree has a .git FILE"
    (wt / "src").mkdir()
    (wt / "src" / "app.py").write_text("a\n")
    before = index_state(wt)
    assert "?? src/app.py" in before[1], "precondition: the new file is untracked"
    proc = helper(wt, "compliance", "42", "--base", base)
    assert proc.returncode in (0, 3), proc.stdout + proc.stderr
    assert index_state(wt) == before
    assert index_state(r)[1] == "", "the main checkout's index was not touched either"


def test_the_index_is_restored_when_the_repository_has_no_plan_record(repo) -> None:
    """Lane: Project state, a repository that has not adopted the record.
    Compliance marks the files BEFORE it looks for the record, so the
    not-adopted answer (UNKNOWN) must restore them too."""
    r, base = repo
    git(r, "rm", "-q", "docs/flow-runs/issue-42.md")
    git(r, "commit", "-qm", "no record")
    (r / "new.py").write_text("n\n")
    before = index_state(r)
    assert "?? new.py" in before[1] and not (r / "docs/flow-runs/issue-42.md").exists()
    proc = helper(r, "compliance", "42", "--base", base)
    assert proc.returncode == 4 and "no plan record" in proc.stdout, proc.stdout
    assert index_state(r) == before
