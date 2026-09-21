"""Control for the /flow:auto plan record (issue #1080).

WHY THIS RUNS THE DOC'S OWN SNIPPET INSTEAD OF RE-IMPLEMENTING IT
----------------------------------------------------------------
A test asserting that `auto.md` CONTAINS certain words is a marker: written by
the thing being measured, and green whether or not the documented commands
work. That is the shape counter-model-receipt.py was written against, and the
shape this wave keeps finding.

So these cases EXTRACT the fenced bash block from under the reconcile heading in
`auto.md` and RUN it. If the documented commands are wrong, the cases fail. If
the heading or the block disappears, `extract_reconcile_snippet` raises rather
than silently testing nothing - an absent subject must not read as a pass.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

# These drive real `git` and `bash` subprocesses. The Woodpecker `validate` step
# runs in a slim image that ships bash but NOT git (issue #430/#577), so a test
# that shells out unguarded passes locally and errors only in CI.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

REPO = Path(__file__).resolve().parents[1]
AUTO_MD = REPO / ".claude" / "commands" / "flow" / "auto.md"
HEADING = "#### Reconcile the plan record (issue #1080)"
RECORD_REL = "docs/flow-runs/issue-42.md"


def extract_reconcile_snippet() -> str:
    """The bash block under HEADING, or raise.

    Raising is the point: a renamed heading must fail loudly here rather than
    leave every case below passing over an empty string.
    """
    text = AUTO_MD.read_text()
    if text.count(HEADING) != 1:
        raise AssertionError(
            f"expected exactly one {HEADING!r} in auto.md, found {text.count(HEADING)}"
        )
    after = text.split(HEADING, 1)[1]
    m = re.search(r"```bash\n(.*?)```", after, re.DOTALL)
    if not m:
        raise AssertionError("no fenced bash block follows the reconcile heading")
    snippet = m.group(1)
    if 'cat-file -e "HEAD:' not in snippet:
        raise AssertionError(
            "the reconcile snippet no longer asks HEAD whether the record was "
            "COMMITTED. An index-based test (`git ls-files`) answers a different "
            "question and is wrong in both directions - see the staged-deletion "
            f"and staged-addition cases below:\n{snippet}"
        )
    return snippet


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "wt"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "code.py").write_text("x = 1\n")
    git(repo, "add", "code.py")
    git(repo, "commit", "-qm", "base")
    return repo


WRITE_HEADING = "#### First, write the plan record (issue #1080)"


def extract_write_snippet() -> str:
    """The bash block that WRITES the record, or raise.

    The squash case used to create its own hardcoded record, so deleting the
    documented write left every case green - the tests would have kept passing
    over a procedure that no longer wrote anything (counter-model review,
    gpt-6-astra). Running the documented block is what ties them to it.
    """
    text = AUTO_MD.read_text()
    if text.count(WRITE_HEADING) != 1:
        raise AssertionError(
            f"expected exactly one {WRITE_HEADING!r}, found {text.count(WRITE_HEADING)}"
        )
    after = text.split(WRITE_HEADING, 1)[1]
    m = re.search(r"```bash\n(.*?)```", after, re.DOTALL)
    if not m:
        raise AssertionError("no fenced bash block follows the write heading")
    snippet = m.group(1)
    if RECORD_REL not in snippet:
        raise AssertionError(
            f"the documented write no longer targets {RECORD_REL}:\n{snippet}"
        )
    return snippet


def run_snippet(repo: Path, snippet: str) -> None:
    """Run a documented snippet and REQUIRE it to succeed.

    The status used to be discarded, so a snippet that mutated the tree and then
    failed would leave the assertions green.
    """
    proc = subprocess.run(
        ["bash", "-c", snippet], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 0, (
        f"the documented snippet exited {proc.returncode}\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


def run_reconcile(repo: Path) -> None:
    run_snippet(repo, extract_reconcile_snippet())


def run_documented_write(repo: Path) -> None:
    run_snippet(repo, extract_write_snippet())


def staged_paths(repo: Path) -> list[str]:
    return [p for p in git(repo, "diff", "--cached", "--name-only").split("\n") if p]


@requires_git
def test_no_prior_record_and_step3_not_reached_leaves_nothing(tmp_path: Path) -> None:
    """Case 1: nothing before, nothing after, nothing staged."""
    repo = make_repo(tmp_path)
    run_reconcile(repo)
    assert not (repo / RECORD_REL).exists()
    assert staged_paths(repo) == []


@requires_git
def test_committed_record_survives_a_run_that_aborts_before_step3(tmp_path: Path) -> None:
    """Case 3 (the counter-model gap): run A's APPROVED record must survive run B.

    Deleting unconditionally here leaves run A's code on the branch with no
    approval record, and stages the deletion. That is worse than a stale record:
    a stale record is a wrong answer, this is no answer where there was one.
    """
    repo = make_repo(tmp_path)
    rec = repo / RECORD_REL
    rec.parent.mkdir(parents=True)
    rec.write_text("# Flow run record - issue #42\nApproval: granted\n")
    git(repo, "add", RECORD_REL)
    git(repo, "commit", "-qm", "run A: approved plan")
    before = rec.read_bytes()

    run_reconcile(repo)

    assert rec.exists(), "run A's committed approval record was destroyed"
    assert rec.read_bytes() == before, "run A's record was modified"
    assert staged_paths(repo) == [], "a deletion was staged; the PR would show it"


@requires_git
def test_untracked_record_from_a_dead_run_is_removed(tmp_path: Path) -> None:
    """Case 2: scratch from a run that died before committing must not ship.

    Left in place, Step 6's staging sweeps it into THIS run's commit and a plan
    nobody approved in this run ships as this run's approval.
    """
    repo = make_repo(tmp_path)
    rec = repo / RECORD_REL
    rec.parent.mkdir(parents=True)
    rec.write_text("# Flow run record - issue #42\nApproval: granted\n")
    assert rec.exists()

    run_reconcile(repo)

    assert not rec.exists(), "unapproved scratch survived and would be committed"


@requires_git
def test_uncommitted_edits_to_a_tracked_record_are_restored(tmp_path: Path) -> None:
    """The committed version is the one a reviewer signed; edits do not win."""
    repo = make_repo(tmp_path)
    rec = repo / RECORD_REL
    rec.parent.mkdir(parents=True)
    rec.write_text("approved\n")
    git(repo, "add", RECORD_REL)
    git(repo, "commit", "-qm", "run A")
    rec.write_text("edited by nobody in particular\n")

    run_reconcile(repo)

    assert rec.read_text() == "approved\n"


@requires_git
def test_a_staged_record_from_a_dead_run_does_not_become_this_runs_approval(
    tmp_path: Path,
) -> None:
    """The staged path, and it is reachable by auto.md's own design.

    Step 6 stages the record, so a run that stages it and then dies leaves the
    record tracked AND staged with THAT run's content. `git checkout -- <path>`
    restores from the INDEX, so it would hand this run the dead run's plan, which
    this run then commits at Step 6 as its own approval - the failure the
    untracked branch prevents, arriving by the staged path instead.

    Measured: with run B's scratch staged over run A's commit, a bare `--`
    yields run B's text; `HEAD --` yields run A's and clears the staged diff.
    """
    repo = make_repo(tmp_path)
    rec = repo / RECORD_REL
    rec.parent.mkdir(parents=True)
    rec.write_text("approved by A\n")
    git(repo, "add", RECORD_REL)
    git(repo, "commit", "-qm", "run A: approved plan")

    rec.write_text("UNAPPROVED scratch from run B\n")
    git(repo, "add", RECORD_REL)  # run B reached Step 6, staged, then died

    run_reconcile(repo)

    assert rec.read_text() == "approved by A\n", (
        "a plan approved in a DIFFERENT run was restored and would ship as this "
        "run's approval - the reconcile is restoring from the index, not HEAD"
    )
    assert staged_paths(repo) == [], "run B's staged scratch is still staged"


@requires_git
def test_a_committed_record_survives_a_squash_merge(tmp_path: Path) -> None:
    """Acceptance: the Step 6 squash does not drop it.

    Documenting a check that ASKS the PR is not the same as showing the record
    survives the collapse, so this measures the collapse itself rather than
    trusting that a squash keeps every file. `git merge --squash` is the same
    flattening `gh pr merge --squash` performs server-side.
    """
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "-b", "issue-42")
    run_documented_write(repo)          # the procedure's own write, not a fixture
    rec = repo / RECORD_REL
    assert rec.exists(), "the documented write produced no record"
    (repo / "code.py").write_text("x = 2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "feat: the work, plus its approved plan")

    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--squash", "issue-42")
    git(repo, "commit", "-qm", "feat: squashed (#42)")

    tracked = git(repo, "ls-tree", "-r", "--name-only", "HEAD").split("\n")
    assert RECORD_REL in tracked, (
        f"the squash dropped the plan record; HEAD carries {tracked}"
    )
    assert "Flow run record" in (repo / RECORD_REL).read_text()


@requires_git
def test_a_committed_record_with_a_staged_deletion_is_restored(tmp_path: Path) -> None:
    """`git ls-files` answers about the INDEX, which is the wrong question.

    With the record committed and then `git rm --cached`'d, an index-based
    existence test fails, the else-branch deletes the remaining approved file,
    and the staged deletion survives - an APPROVED record destroyed.
    """
    repo = make_repo(tmp_path)
    rec = repo / RECORD_REL
    rec.parent.mkdir(parents=True)
    rec.write_text("approved by A\n")
    git(repo, "add", RECORD_REL)
    git(repo, "commit", "-qm", "run A")
    git(repo, "rm", "-q", "--cached", RECORD_REL)

    run_reconcile(repo)

    assert rec.exists(), "an approved, committed record was destroyed"
    assert rec.read_text() == "approved by A\n"
    assert staged_paths(repo) == [], "the staged deletion survived"


@requires_git
def test_a_staged_record_absent_from_head_is_removed(tmp_path: Path) -> None:
    """The mirror state: staged, never committed, so never approved."""
    repo = make_repo(tmp_path)
    rec = repo / RECORD_REL
    rec.parent.mkdir(parents=True)
    rec.write_text("UNAPPROVED scratch\n")
    git(repo, "add", RECORD_REL)

    run_reconcile(repo)

    assert not rec.exists(), "unapproved scratch survived and would be committed"
    assert staged_paths(repo) == [], "unapproved scratch is still staged"


@requires_git
def test_the_record_path_is_not_gitignored() -> None:
    """A JSON record would be silently dropped; verified by EXIT CODE.

    `git check-ignore -v` prints the last MATCHING pattern even when that
    pattern is a NEGATION, so its OUTPUT cannot be read as the verdict - a
    negated path prints a match and is not ignored. Only the exit code answers
    the question asked.
    """
    def ignored(rel: str) -> int:
        return subprocess.run(
            ["git", "-C", str(REPO), "check-ignore", "-q", rel]
        ).returncode

    md, js = ignored("docs/flow-runs/issue-42.md"), ignored("docs/flow-runs/issue-42.json")

    # REQUIRE THE DONE-SET, never `!= ignored`. check-ignore returns 0 ignored,
    # 1 not ignored, and 128 when it could not answer at all (no repository).
    # Collapsing 128 into "not ignored" would report a clean verdict from a run
    # that never examined anything - found by this control's own red run, where
    # a non-repo fixture returned 128 and the assertion blamed .gitignore.
    assert md in (0, 1), f"check-ignore could not answer for the .md path (exit {md})"
    assert js in (0, 1), f"check-ignore could not answer for the .json path (exit {js})"
    assert md == 1, "the documented .md record path is ignored; it would never ship"
    assert js == 0, (
        "a .json record at this path is NOT ignored any more - the blanket *.json "
        "rule changed, and the doc's warning about needing a negation first is stale"
    )
