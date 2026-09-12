"""The pilot runner's inputs are pinned to the commit it names (issue #861).

`--commit` exists so a recorded result can be rebuilt from what `results.json`
names. That promise is only as good as the WEAKEST input: the guidance, the
scripts, the spec, the tasks file and the case wording all have to come from the
same snapshot, or the recorded `commit` and `fixtures_tree` describe a prompt that
was never actually used.

That is not hypothetical. The first pinning fix moved the spec and the scripts onto
`git archive` and left the case text being read from the working tree, so an
uncommitted edit reached a prompt built from a named commit while the metadata still
claimed that commit. Review caught it with a sentinel; this test is that sentinel,
kept.

No model is called. The runner's `--dry-run` writes the prompts and stops, which is
the whole surface under test here - what the model does with a prompt is a separate
question with separate evidence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run-delivery-pilots.py"
CASES = "tests/fixtures/delivery_pilots/completion/cases.json"
SENTINEL = "WORKING_TREE_SENTINEL_MUST_NOT_REACH_A_PINNED_PROMPT"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None
    or shutil.which("bash") is None
    or shutil.which("jq") is None,
    reason="requires git, bash and jq on PATH",
)


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(RUNNER), *args], cwd=cwd, capture_output=True, text=True
    )


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A real clone, so the working tree can be dirtied without touching the repo.

    Editing this checkout's own fixtures would race every other session sharing it
    and could leave the tree dirty if an assertion fails midway.
    """
    target = tmp_path / "clone"
    done = subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(target)],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        pytest.skip(f"could not clone the repository: {done.stderr.strip()}")
    return target


def _dirty_the_case_text(repo: Path) -> str:
    """Put a sentinel in the working tree's case wording. Returns the committed text."""
    path = repo / CASES
    committed = json.loads(path.read_text(encoding="utf-8"))
    original = committed["cases"][0]["work"]
    committed["cases"][0]["work"] = SENTINEL
    path.write_text(json.dumps(committed, indent=2) + "\n", encoding="utf-8")
    return original


def test_a_dirty_case_file_cannot_reach_a_prompt_built_from_a_commit(clone: Path) -> None:
    committed_text = _dirty_the_case_text(clone)
    out = clone / "out"

    result = _run("--suite", "completion", "--commit", "HEAD", "--out", str(out),
                  "--dry-run", cwd=clone)

    assert result.returncode == 0, result.stderr
    prompts = sorted(out.glob("*.prompt.txt"))
    assert prompts, "the dry run wrote no prompts, so this test proves nothing"
    joined = "\n".join(p.read_text(encoding="utf-8") for p in prompts)
    assert SENTINEL not in joined, (
        "an uncommitted edit reached a prompt built from a named commit"
    )
    assert committed_text[:60] in joined, (
        "the committed case text is missing, so the sentinel's absence may just mean "
        "no case text was used at all"
    )


def test_the_issue_and_its_spec_come_from_the_commit_too(clone: Path) -> None:
    """The same promise for the other inputs, which were pinned first."""
    spec = clone / "tests/fixtures/delivery_pilots/completion/spec-v1.md"
    spec.write_text(spec.read_text(encoding="utf-8") + f"\n- [ ] {SENTINEL}\n",
                    encoding="utf-8")
    out = clone / "out"

    result = _run("--suite", "completion", "--commit", "HEAD", "--out", str(out),
                  "--dry-run", cwd=clone)

    assert result.returncode == 0, result.stderr
    issue = (out / "issue.md").read_text(encoding="utf-8")
    assert SENTINEL not in issue
    assert "speckit-context:v1" in issue, "no generated block, so nothing was pinned"


def test_a_dirty_tree_is_what_makes_those_tests_meaningful(clone: Path) -> None:
    """Precondition guard: the edits above must actually leave the clone dirty.

    If the fixture silently failed to write, both tests would pass against a clean
    tree and establish nothing at all.
    """
    _dirty_the_case_text(clone)

    status = subprocess.run(["git", "status", "--porcelain", CASES],
                            cwd=clone, capture_output=True, text=True)

    assert status.stdout.strip(), "the case file was not actually modified"
    assert SENTINEL in (clone / CASES).read_text(encoding="utf-8")
