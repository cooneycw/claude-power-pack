"""Control for the /flow:auto plan-versus-diff compliance check (issue #1082).

The documented block is EXTRACTED from auto.md and RUN against fixture
repositories. It is never re-implemented here: a case that restated the logic
would pass while the documented commands were wrong, which is the failure this
whole chain of issues is about.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash (absent in the CI validate container)",
)

REPO = Path(__file__).resolve().parents[1]
AUTO_MD = REPO / ".claude" / "commands" / "flow" / "auto.md"
MARKER = "7. **Compare the diff against the approved plan** (issue #1082)"


def block() -> str:
    text = AUTO_MD.read_text()
    if text.count(MARKER) != 1:
        raise AssertionError(f"expected exactly one {MARKER!r}, found {text.count(MARKER)}")
    m = re.search(r"```bash\n(.*?)```", text.split(MARKER, 1)[1], re.DOTALL)
    if not m:
        raise AssertionError("no fenced bash block follows the compliance heading")
    snippet = re.sub(r"^   ", "", m.group(1), flags=re.M)
    for needed in ("add -N", "PLAN_COMPLIANCE", "PLAN_RECORD_STABILITY"):
        if needed not in snippet:
            raise AssertionError(f"the documented block no longer contains {needed!r}")
    return snippet


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout


def make_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "wt"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@e.com")
    git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("base\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "-q", "-b", "feature")
    return repo, base


def write_plan(repo: Path, *files: str) -> None:
    d = repo / "docs" / "flow-runs"
    d.mkdir(parents=True, exist_ok=True)
    lines = ["# Flow run record - issue #42", "## Section C - the approved plan"]
    lines += [f"  {i}. `{f}` - because" for i, f in enumerate(files, 1)]
    lines.append(f"Scope: {len(files)} files")
    (d / "issue-42.md").write_text("\n".join(lines) + "\n")


def stamp_baseline(repo: Path) -> None:
    """What Step 4 does immediately after writing the approved plan."""
    gitdir = git(repo, "rev-parse", "--git-dir").strip()
    digest = subprocess.run(["sha256sum", "docs/flow-runs/issue-42.md"],
                            cwd=repo, capture_output=True, text=True).stdout.split()[0]
    (repo / gitdir / "flow-plan-baseline-42").write_text(digest + "\n")


def run(repo: Path, base: str) -> str:
    script = block().replace('$(git merge-base HEAD origin/main)', base)
    proc = subprocess.run(["bash", "-c", script], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, f"block exited {proc.returncode}\n{proc.stderr}"
    return proc.stdout


# ------------------------------------------------------------------ the three verdicts

@requires_git
def test_a_diff_matching_its_plan_reports_agreement(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    assert "PLAN_COMPLIANCE: agreement" in run(repo, base)


@requires_git
def test_a_file_the_plan_never_named_is_divergence_and_is_NAMED(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    (repo / "src" / "extra.py").write_text("b\n")
    write_plan(repo, "src/app.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: divergence" in out
    assert "TOUCHED BUT NOT PLANNED: src/extra.py" in out


@requires_git
def test_a_plan_item_never_touched_is_reported(tmp_path: Path) -> None:
    """The other half: a plan item silently not done."""
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py", "tests/test_app.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: divergence" in out
    assert "PLANNED BUT NOT TOUCHED: tests/test_app.py" in out


# ------------------------------------------------------------------ the #1030 case

@requires_git
def test_an_UNTRACKED_new_file_diverges_without_any_manual_intent_to_add(tmp_path: Path) -> None:
    """The case this issue names, and the one the check shipped blind to.

    `git diff <ref>` skips untracked paths entirely, so before the block did its
    OWN `add -N` this reported AGREEMENT with a whole unplanned file in the tree.
    #1030 fixed that for the REVIEW diff in code_review.md; `add -N` appears
    nowhere else, and this step computes its own diff, so it inherited nothing.

    The fixture deliberately performs NO intent-to-add of its own - doing so would
    supply the step under test and the case would pass however wrong the block was.
    """
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "planned")
    (repo / "src" / "surprise.py").write_text("brand new\n")   # untracked, never staged
    assert "surprise.py" in git(repo, "ls-files", "--others", "--exclude-standard")

    out = run(repo, base)

    assert "PLAN_COMPLIANCE: divergence" in out, (
        "an unplanned untracked file was invisible to the comparison"
    )
    assert "TOUCHED BUT NOT PLANNED: src/surprise.py" in out


@requires_git
def test_TWO_untracked_files_one_with_a_space_are_BOTH_named(tmp_path: Path) -> None:
    """Issue #1220: the case above uses ONE file, where a separator bug is invisible.

    The block captured `ls-files -z` through command substitution, which strips
    NUL bytes, so N paths collapsed into one glued pathspec, `add -N` failed and the
    verdict was `unknown` for every change adding more than one file. At N=1 a
    separator bug, an iteration bug and correct code are indistinguishable.

    Both names are asserted - a verdict-only check would pass a fix that recovered
    one path and dropped the other. One name carries a space, because whitespace in
    filenames is the reason `-z` was chosen; two plain names prove the separator
    survives, only this one proves it survives for that reason.
    """
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "planned")
    (repo / "src" / "new one.py").write_text("first\n")    # untracked, never staged
    (repo / "src" / "second.py").write_text("second\n")    # untracked, never staged
    assert len(git(repo, "ls-files", "--others", "--exclude-standard", "-z")
               .split("\0")[:-1]) == 2

    out = run(repo, base)

    assert "PLAN_COMPLIANCE: divergence" in out, f"two untracked files were not compared:\n{out}"
    assert "TOUCHED BUT NOT PLANNED: src/new one.py" in out
    assert "TOUCHED BUT NOT PLANNED: src/second.py" in out


@requires_git
def test_the_untracked_list_is_not_itself_an_untracked_file(tmp_path: Path) -> None:
    """The #1220 fix holds the list in a temp FILE; it must not enumerate itself.

    With TMPDIR inside the worktree, a default `mktemp` lands in the population
    `ls-files --others` is about to list, is deleted before `add -N` runs, and the
    stale pathspec turns a MATCHING change into `unknown` (counter-model review).
    """
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    stamp_baseline(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")

    script = block().replace('$(git merge-base HEAD origin/main)', base)
    proc = subprocess.run(["bash", "-c", script], cwd=repo, capture_output=True,
                          text=True, env={**os.environ, "TMPDIR": str(repo)})
    assert "PLAN_COMPLIANCE: agreement" in proc.stdout, (
        f"a temp file under TMPDIR=<worktree> leaked into the comparison:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
    assert not git(repo, "ls-files", "--others", "--exclude-standard").strip()


# ------------------------------------------------------------------ mirrors are DERIVED

@requires_git
def test_a_mirror_whose_source_IS_planned_is_not_divergence(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "docs" / "agents").mkdir(parents=True)
    (repo / "codex" / "skills" / "s" / "docs" / "agents").mkdir(parents=True)
    (repo / "docs" / "agents" / "k.md").write_text("k\n")
    (repo / "codex" / "skills" / "s" / "docs" / "agents" / "k.md").write_text("k\n")
    write_plan(repo, "docs/agents/k.md")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "source+mirror")
    assert "PLAN_COMPLIANCE: agreement" in run(repo, base)


@requires_git
def test_a_mirror_whose_source_is_NOT_planned_IS_divergence(tmp_path: Path) -> None:
    """Excluding codex/skills/** outright would hide this - real drift, and in the
    check's largest category by file count."""
    repo, base = make_repo(tmp_path)
    (repo / "docs" / "agents").mkdir(parents=True)
    (repo / "codex" / "skills" / "s" / "docs" / "agents").mkdir(parents=True)
    (repo / "docs" / "agents" / "k.md").write_text("k\n")
    (repo / "codex" / "skills" / "s" / "docs" / "agents" / "k.md").write_text("k\n")
    (repo / "codex" / "skills" / "s" / "docs" / "agents" / "orphan.md").write_text("z\n")
    write_plan(repo, "docs/agents/k.md")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "orphan mirror")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: divergence" in out
    assert "orphan.md" in out and "docs/agents/orphan.md" in out, (
        f"the report does not name the derived source:\n{out}"
    )


# ------------------------------------------------------------------ the exclusion set is CLOSED

@requires_git
def test_an_excluded_path_is_not_divergence_but_a_neighbour_IS(tmp_path: Path) -> None:
    """Pins the exclusions as a closed list rather than an escape hatch."""
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    cm = repo / "docs" / "measurements" / "counter-model"
    cm.mkdir(parents=True)
    (cm / "2026-09-21T000000Z-issue-42.json").write_text("{}\n")   # THIS run's receipt
    write_plan(repo, "src/app.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "with receipt")
    assert "PLAN_COMPLIANCE: agreement" in run(repo, base)

    # a NEIGHBOURING path under docs/measurements/ that is NOT the excluded prefix
    (repo / "docs" / "measurements" / "other.json").write_text("{}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "neighbour")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: divergence" in out, (
        "the exclusion is matching more than its declared prefix"
    )
    assert "docs/measurements/other.json" in out


# ------------------------------------------------------------------ the record is the check's own input

@requires_git
def test_an_unchanged_plan_record_reports_stable(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    stamp_baseline(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    assert "PLAN_RECORD_STABILITY: unchanged" in run(repo, base)


@requires_git
def test_a_plan_record_edited_after_its_first_commit_is_REPORTED(tmp_path: Path) -> None:
    """Moving the goalposts.

    Excluding the record silently would let a run add a file to its own plan at
    Step 5, touch that file, and report agreement. #1080's Step 1 reconcile
    protects the NEXT run, not this one.
    """
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    stamp_baseline(repo)                       # the approval baseline, at Step 4
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")

    (repo / "src" / "late.py").write_text("late\n")
    write_plan(repo, "src/app.py", "src/late.py")        # the plan grows mid-run
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "grew the plan")

    out = run(repo, base)
    assert "PLAN_COMPLIANCE: agreement" in out, "file set does match the (edited) plan"
    assert "PLAN_RECORD_STABILITY: THE PLAN RECORD CHANGED" in out, (
        f"the record moved and the check did not say so:\n{out}"
    )


# ------------------------------------------------------------------ unknown, never agreement

@requires_git
def test_no_plan_record_is_unknown_never_agreement(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: unknown" in out
    assert "no plan record" in out
    assert "PLAN_COMPLIANCE: agreement" not in out


@requires_git
def test_a_record_without_section_c_is_unknown(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    d = repo / "docs" / "flow-runs"
    d.mkdir(parents=True)
    (d / "issue-42.md").write_text("# Flow run record - issue #42\n\nno section here\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: unknown" in out
    assert "carries no Section C" in out
    assert "PLAN_COMPLIANCE: agreement" not in out


@requires_git
def test_a_section_c_naming_no_files_is_unknown(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    d = repo / "docs" / "flow-runs"
    d.mkdir(parents=True)
    (d / "issue-42.md").write_text(
        "# Flow run record - issue #42\n## Section C - the approved plan\nprose only\nScope: 0\n"
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: unknown" in out
    assert "names no files" in out
    assert "PLAN_COMPLIANCE: agreement" not in out


@requires_git
def test_an_uncomputable_diff_is_unknown_never_agreement(tmp_path: Path) -> None:
    """Found by test_every_unknown_branch_has_a_case_that_PINS_IT.

    If the base ref does not resolve, the diff cannot be taken. Reporting that as
    agreement would say the change matches its plan on the strength of having
    examined nothing.
    """
    repo, _ = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")

    bogus = "0" * 40                      # a well-formed SHA that resolves to nothing
    out = run(repo, bogus)

    assert "PLAN_COMPLIANCE: unknown" in out
    assert "could not be computed" in out, f"reached a different unknown branch:\n{out}"
    assert "PLAN_COMPLIANCE: agreement" not in out


@requires_git
def test_a_plan_record_grown_BEFORE_its_first_commit_is_still_caught(tmp_path: Path) -> None:
    """The HIGH finding: the record is not COMMITTED until Step 6, after the work.

    Comparing against its first commit would miss an implementer who grows the
    record and the diff together before that commit - the ordinary execution path,
    not an exotic one. The baseline is stamped at Step 4 instead.
    """
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    stamp_baseline(repo)                       # Step 4: approved plan, baseline taken

    # implementation grows BOTH the work and the record, before any commit
    (repo / "src" / "extra.py").write_text("extra\n")
    write_plan(repo, "src/app.py", "src/extra.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "first commit of the record, post-implementation")

    out = run(repo, base)
    assert "PLAN_COMPLIANCE: agreement" in out, "the file set matches the edited plan"
    assert "PLAN_RECORD_STABILITY: THE PLAN RECORD CHANGED" in out, (
        f"the record grew before its first commit and was not reported:\n{out}"
    )


@requires_git
def test_an_unparseable_plan_item_is_unknown_not_a_subset_comparison(tmp_path: Path) -> None:
    """One parsed item must not be enough to proceed.

    Skipping an unmatched line drops an approved file from the population, and
    agreement then means "the subset I happened to understand matched".
    """
    repo, base = make_repo(tmp_path)
    d = repo / "docs" / "flow-runs"
    d.mkdir(parents=True)
    (d / "issue-42.md").write_text(
        "# Flow run record - issue #42\n## Section C - the approved plan\n"
        "  1. `src/app.py` - change\n"
        "  2. this line names no file in the documented form\n"
        "Scope: 2 files\n"
    )
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: unknown" in out
    # "be parsed" is NOT distinctive - the missing-Section-C branch also ends
    # "it cannot be parsed". Pin a phrase only this branch carries.
    assert "item(s) could not be parsed" in out, f"reached a different unknown branch:\n{out}"
    assert "PLAN_COMPLIANCE: agreement" not in out


@requires_git
def test_a_rename_into_a_planned_path_still_reports_the_removed_source(tmp_path: Path) -> None:
    """Rename detection reports only the DESTINATION, hiding an unauthorised removal."""
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "legacy.py").write_text("x\n" * 40)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "legacy exists")
    base2 = git(repo, "rev-parse", "HEAD").strip()

    git(repo, "mv", "src/legacy.py", "src/new.py")
    write_plan(repo, "src/new.py")
    stamp_baseline(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "rename")

    out = run(repo, base2)
    assert "PLAN_COMPLIANCE: divergence" in out, (
        f"a rename removed an unplanned file and reported agreement:\n{out}"
    )
    assert "src/legacy.py" in out


@requires_git
def test_a_neighbouring_flow_runs_file_is_not_silently_excluded(tmp_path: Path) -> None:
    """The exclusion is two EXACT paths, not a prefix."""
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    stamp_baseline(repo)
    (repo / "docs" / "flow-runs" / "issue-42.notes.md").write_text("sneaky\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: divergence" in out
    assert "issue-42.notes.md" in out


@requires_git
def test_another_runs_receipt_is_not_excluded(tmp_path: Path) -> None:
    """#1171's enrolment check establishes THIS branch's receipt, not that history
    was left alone."""
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    stamp_baseline(repo)
    cm = repo / "docs" / "measurements" / "counter-model"
    cm.mkdir(parents=True)
    (cm / "2026-01-01T000000Z-issue-999.json").write_text("{}\n")   # another run's
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_COMPLIANCE: divergence" in out
    assert "issue-999" in out


@requires_git
def test_an_explicitly_planned_codex_path_is_honoured(tmp_path: Path) -> None:
    """A planned path wins over any derivation rule."""
    repo, base = make_repo(tmp_path)
    (repo / "codex" / "skills").mkdir(parents=True)
    (repo / "codex" / "skills" / "README.md").write_text("hand-written\n")
    write_plan(repo, "codex/skills/README.md")
    stamp_baseline(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    assert "PLAN_COMPLIANCE: agreement" in run(repo, base)


@requires_git
def test_a_missing_step4_baseline_is_unknown_not_unchanged(tmp_path: Path) -> None:
    """No baseline means the question cannot be answered, not that nothing moved."""
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")                 # deliberately NOT stamped
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_RECORD_STABILITY: unknown" in out
    assert "baseline was stamped" in out, f"reached a different unknown branch:\n{out}"
    assert "PLAN_RECORD_STABILITY: unchanged" not in out


@requires_git
def test_an_empty_baseline_file_is_unknown_not_unchanged(tmp_path: Path) -> None:
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    gitdir = git(repo, "rev-parse", "--git-dir").strip()
    (repo / gitdir / "flow-plan-baseline-42").write_text("")      # stamped, but empty
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    out = run(repo, base)
    assert "PLAN_RECORD_STABILITY: unknown" in out
    assert "carries no digest" in out, f"reached a different unknown branch:\n{out}"


@requires_git
def test_an_unenumerable_worktree_is_unknown_not_agreement(tmp_path: Path) -> None:
    """The shell half's first unknown, and it is reachable.

    Run outside a repository: `git rev-parse --show-toplevel` fails, so the
    enumeration of untracked files cannot be performed. Reporting agreement there
    would claim the file set matched having never established what the files were.
    """
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    script = block().replace('$(git merge-base HEAD origin/main)', "HEAD")
    proc = subprocess.run(["bash", "-c", script], cwd=outside,
                          capture_output=True, text=True)
    assert "PLAN_COMPLIANCE: unknown" in proc.stdout
    assert "enumerate untracked files" in proc.stdout, (
        f"reached a different unknown branch:\n{proc.stdout}\n{proc.stderr}"
    )
    assert "PLAN_COMPLIANCE: agreement" not in proc.stdout


@requires_git
def test_a_failed_intent_to_add_is_unknown_not_agreement(tmp_path: Path) -> None:
    """The shell half's second unknown.

    Probes the property rather than an identity: it makes the index unwritable and
    SKIPS if the add still succeeds, which is true for root or for a filesystem
    that does not enforce permissions.
    """
    repo, base = make_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("a\n")
    write_plan(repo, "src/app.py")
    stamp_baseline(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    (repo / "src" / "surprise.py").write_text("new\n")

    gitdir = Path(git(repo, "rev-parse", "--git-dir").strip())
    index = (repo / gitdir / "index") if not gitdir.is_absolute() else gitdir / "index"
    index.chmod(0o444)
    try:
        probe = subprocess.run(["git", "-C", str(repo), "add", "-N", "--", "src/surprise.py"],
                               capture_output=True, text=True)
        if probe.returncode == 0:
            pytest.skip("this environment can write a read-only index; the state is unreachable")
        out = run(repo, base)
    finally:
        index.chmod(0o644)

    assert "PLAN_COMPLIANCE: unknown" in out
    assert "files intent-to-add" in out, f"reached a different unknown branch:\n{out}"
    assert "PLAN_COMPLIANCE: agreement" not in out


# ------------------------------------------------------------------ the sweep, mechanised

def test_every_unknown_branch_has_a_case_that_PINS_IT() -> None:
    """Same mechanism as #1081: enumerate the branches, require a distinctive pin.

    A rule that must be remembered at each site will be forgotten at some site.
    """
    blk = block()
    messages = re.findall(r'unknown\(f?"([^"]*)"', blk)
    # The SHELL half emits its own unknowns before python is reached. Enumerating
    # only the python calls omitted both of them - the gate's own population was
    # narrower than the thing it was gating (counter-model review, gpt-6-astra).
    messages += re.findall(r'echo "PLAN_COMPLIANCE: unknown \(([^"]*)', blk)
    messages += re.findall(r'print\("PLAN_RECORD_STABILITY: unknown \(([^"]*)', blk)
    assert len(messages) >= 4, f"expected >=4 unknown branches, found {len(messages)}: {messages}"
    # NORMALISE BOTH SIDES. The runs are derived from the message with punctuation
    # stripped, so searching them in raw assert text means "item s" can never match
    # "item(s)" however well the branch is pinned - the gate would demand a phrase
    # no correct assertion can contain.
    raw_asserts = "\n".join(
        ln for ln in Path(__file__).read_text().splitlines() if "assert " in ln
    )
    asserts = " ".join(w for w in re.split(r"[^A-Za-z-]+", raw_asserts) if w)

    def runs_of(msg: str) -> set[str]:
        literal = re.sub(r"\{[^}]*\}", " ", msg)
        words = [w for w in re.split(r"[^A-Za-z-]+", literal) if w]
        return {" ".join(words[i:i + 2]) for i in range(max(1, len(words) - 1))}

    all_runs = [runs_of(m) for m in messages]
    unpinned = []
    for i, msg in enumerate(messages):
        others = set().union(*(r for j, r in enumerate(all_runs) if j != i))
        distinctive = all_runs[i] - others
        if not distinctive or not any(r in asserts for r in distinctive):
            unpinned.append(msg)
    assert not unpinned, (
        "these unknown branches have no case pinning a phrase distinctive to them:\n  "
        + "\n  ".join(unpinned)
    )
