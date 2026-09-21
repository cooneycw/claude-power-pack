"""Control for the /flow:auto plan-versus-diff compliance check (issue #1082).

The documented block is EXTRACTED from auto.md and RUN against fixture
repositories. It is never re-implemented here: a case that restated the logic
would pass while the documented commands were wrong, which is the failure this
whole chain of issues is about.
"""

from __future__ import annotations

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
    (repo / "docs" / "measurements" / "counter-model").mkdir(parents=True)
    (repo / "docs" / "measurements" / "counter-model" / "r.json").write_text("{}\n")
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


# ------------------------------------------------------------------ the sweep, mechanised

def test_every_unknown_branch_has_a_case_that_PINS_IT() -> None:
    """Same mechanism as #1081: enumerate the branches, require a distinctive pin.

    A rule that must be remembered at each site will be forgotten at some site.
    """
    messages = re.findall(r'unknown\(f?"([^"]*)"', block())
    assert len(messages) >= 4, f"expected >=4 unknown branches, found {len(messages)}: {messages}"
    asserts = "\n".join(
        ln for ln in Path(__file__).read_text().splitlines() if "assert " in ln
    )

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
