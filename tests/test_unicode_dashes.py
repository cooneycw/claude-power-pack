"""Pin: no U+2014/U+2013 in prose outside fenced code (issue #1037).

CLAUDE.md:22 said "never Unicode em or en dashes" with nothing checking it -
9 of 406 tracked `.md` files carried one. This suite pins the fix and its
negative controls (ADR 0008): a fixture with a dash outside a fence must
fail, the identical dash fenced must pass (the exclusion is not blanket), a
clean file must pass, and a shrunk/missing population must report UNKNOWN
rather than a vacuous clean.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.isolated_env import ISOLATED_PATH

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-unicode-dashes.py"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git on PATH")



def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
    )


def _run_without_git(root: Path) -> subprocess.CompletedProcess[str]:
    """PATH containing only Python's own directory - no `git` reachable at
    all, reproducing CI's `validate` image (issue #1037, pipeline 2128)."""
    git_free_path = str(Path(sys.executable).parent)
    assert shutil.which("git", path=git_free_path) is None, "fixture must lack git"
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
        env={"PATH": git_free_path},
    )


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
        env={"HOME": str(cwd), "PATH": ISOLATED_PATH,  # negative-fixture: allow PATH is isolation, not an absence
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    )


def _init_repo_with_md_files(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git("init", "-q", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "base", cwd=repo)
    return repo


def _padded_population(n: int) -> dict[str, str]:
    """N clean filler .md files, so a real repo's size doesn't gate the test."""
    return {f"filler-{i}.md": f"# filler {i}\n\nclean prose.\n" for i in range(n)}


@requires_git
def test_a_dash_outside_a_fence_is_a_committed_red_case(tmp_path: Path) -> None:
    files = _padded_population(60)
    files["doc.md"] = "# Title\n\nSomething — with an em dash outside a fence.\n"
    repo = _init_repo_with_md_files(tmp_path, files)

    proc = _run(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "doc.md" in proc.stderr
    assert "—" in proc.stderr


@requires_git
def test_a_dash_inside_a_fence_passes(tmp_path: Path) -> None:
    """Proves the fence exclusion isn't accidentally blanket - it targets a
    specific fenced dash, not "any file that also happens to have a fence"."""
    files = _padded_population(60)
    files["doc.md"] = "# Title\n\n```\nexample output — with an em dash\n```\n\nclean prose.\n"
    repo = _init_repo_with_md_files(tmp_path, files)

    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@requires_git
def test_the_pinned_exclusions_are_narrow_and_do_not_blind_the_check(tmp_path: Path) -> None:
    """The #1069 exclusion boundary, asserted in BOTH directions at once.

    `docs/project-next-contract.md` and `tests/project_next/fixtures/**` are
    excluded because the first is sha256-pinned by the ownership manifest and
    the second is `lib/project_next/render.py`'s own rendered output, which
    emits U+2014 itself. Rewriting either to satisfy a PROSE convention breaks
    the thing it exists to be.

    Both halves live in ONE test on purpose. Asserting only that the excluded
    paths pass would be satisfied by a check that had gone blanket-blind, and
    asserting only that other files fail would not notice the exclusion had
    stopped working. A widened exclusion is exactly where a check quietly loses
    the distinction it was built to draw, so the guard has to fail if EITHER
    direction breaks.
    """
    dash = "Something \u2014 with an em dash outside a fence.\n"

    # Direction 1: the excluded paths carry dashes and the tree is still clean.
    files = _padded_population(60)
    files["docs/project-next-contract.md"] = f"# Contract\n\n{dash}"
    files["tests/project_next/fixtures/golden/compact.md"] = f"## rendered\n\n{dash}"
    (tmp_path / "excluded").mkdir()
    repo = _init_repo_with_md_files(tmp_path / "excluded", files)
    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    # Direction 2: the SAME dash one directory over is still caught, so the
    # exclusion is a named set and not a blanket.
    files["docs/project-next-provenance.md"] = f"# Provenance\n\n{dash}"
    (tmp_path / "not-excluded").mkdir()
    repo = _init_repo_with_md_files(tmp_path / "not-excluded", files)
    proc = _run(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "docs/project-next-provenance.md" in proc.stderr
    # ...and the excluded neighbours are NOT named in the finding.
    assert "project-next-contract.md" not in proc.stderr
    assert "fixtures/golden/compact.md" not in proc.stderr


@requires_git
def test_the_as_read_suffix_is_excluded_without_blinding_its_own_directory(
    tmp_path: Path,
) -> None:
    """The #1185 exclusion boundary, in BOTH directions, same shape as above.

    `docs/flow-runs/issue-N.as-read.md` is #1187's byte-faithful copy of a
    GitHub issue body, digested over the full text. Its value IS fidelity, so
    normalising its dashes would make it a lie about what the run read - and the
    dashes are the issue author's, not this repository's.

    DIRECTION 2 IS THE ONE THAT MATTERS, and it is why this is a SUFFIX rule and
    not a `docs/flow-runs/` prefix. The plan record `issue-N.md` lives in the
    same directory and IS authored by this repository, so it must stay covered.
    A prefix exclusion passes direction 1 identically and FAILS this half - it
    would swallow the plan record with the snapshot, keying on location where
    the honest key is provenance.

    Measured before the exclusion was added: 9 of 23 recent open CPP issues
    carry an em or en dash, so roughly two in five /flow:auto runs would red the
    suite for a reason naming neither feature.
    """
    dash = "Something \u2014 with an em dash outside a fence.\n"

    # Direction 1: the snapshot carries the issue author's dashes; tree is clean.
    files = _padded_population(60)
    files["docs/flow-runs/issue-4242.as-read.md"] = f"# Issue #4242 as read\n\n{dash}"
    (tmp_path / "excluded").mkdir()
    repo = _init_repo_with_md_files(tmp_path / "excluded", files)
    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    # Direction 2: the plan record NEXT TO IT is ours, and is still caught.
    files["docs/flow-runs/issue-4242.md"] = f"# Flow run record\n\n{dash}"
    (tmp_path / "not-excluded").mkdir()
    repo = _init_repo_with_md_files(tmp_path / "not-excluded", files)
    proc = _run(repo)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "docs/flow-runs/issue-4242.md" in proc.stderr, (
        "the plan record shares a directory with the snapshot and is AUTHORED by "
        "this repository - a directory-prefix exclusion would have swallowed it"
    )
    assert "issue-4242.as-read.md" not in proc.stderr


@requires_git
def test_the_exclusion_predicates_are_both_applied(tmp_path: Path) -> None:
    """A prefix rule and a suffix rule are two comparisons, not one.

    The comment at the rule site used to say `str.startswith` takes a tuple "so
    this stays one comparison". Adding a suffix rule made that false. This pins
    that BOTH predicates are live, so a refactor collapsing back to one is a red
    test rather than a silently re-blinded check.
    """
    dash = "Something \u2014 with an em dash outside a fence.\n"
    files = _padded_population(60)
    files["docs/project-next-contract.md"] = f"# Contract\n\n{dash}"      # prefix rule
    files["docs/flow-runs/issue-4242.as-read.md"] = f"# As read\n\n{dash}"  # suffix rule
    repo = _init_repo_with_md_files(tmp_path, files)
    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@requires_git
def test_a_dash_inside_a_blockquoted_fence_passes(tmp_path: Path) -> None:
    """Codex review (#1037): a fence marker prefixed by Markdown blockquote
    (`> \\`\\`\\``) is still a fence, not prose - a legitimate quoted code
    example must not fail on a dash the fence exists to exclude."""
    files = _padded_population(60)
    files["doc.md"] = "# Title\n\n> ```\n> example output — with an em dash\n> ```\n\nclean prose.\n"
    repo = _init_repo_with_md_files(tmp_path, files)

    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@requires_git
def test_an_unreadable_file_is_unknown_not_clean(tmp_path: Path) -> None:
    """Codex review (#1037): a file this check cannot read is a file it did
    not scan, so 'ok' must not silently count it as clean - it could be
    hiding the exact violation the scan exists to find."""
    files = _padded_population(60)
    repo = _init_repo_with_md_files(tmp_path, files)
    # Invalid UTF-8 bytes, committed as a tracked .md file - git is byte-
    # agnostic, so this tracks fine while read_text(encoding="utf-8") cannot.
    (repo / "broken.md").write_bytes(b"# Title\n\n\xff\xfe not valid utf-8\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", "add unreadable file", cwd=repo)

    proc = _run(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) for an unreadable file, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )
    assert "broken.md" in proc.stderr


@requires_git
def test_git_binary_entirely_absent_is_unknown_not_a_crash(tmp_path: Path) -> None:
    """CI pipeline 2128 (issue #1037): `git` not on PATH at all raised an
    uncaught FileNotFoundError - not a script-detected failure, a crash.
    `@requires_git` guards building the fixture only; the script itself then
    runs with no git reachable, which is the whole point of this test."""
    repo = _init_repo_with_md_files(tmp_path, _padded_population(60))

    proc = _run_without_git(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) with git entirely absent, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )
    assert "Traceback" not in proc.stderr


@requires_git
def test_a_clean_tree_passes(tmp_path: Path) -> None:
    repo = _init_repo_with_md_files(tmp_path, _padded_population(60))

    proc = _run(repo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ok" in proc.stdout


@requires_git
def test_too_few_tracked_md_files_is_unknown_not_clean(tmp_path: Path) -> None:
    """Same floor shape as check-version-consistency.py: a shrunk population
    must not read as "scanned everything and found nothing."""
    repo = _init_repo_with_md_files(tmp_path, _padded_population(3))

    proc = _run(repo)
    assert proc.returncode == 2, (
        f"expected UNKNOWN (exit 2) for a too-small population, got "
        f"{proc.returncode}:\n{proc.stdout}{proc.stderr}"
    )


@requires_git
def test_the_real_repo_is_currently_clean() -> None:
    """Regression-test EXECUTION against the live tree, not a committed case.

    Guarded: CI's `validate` image has no `git` binary at all (issue #1037,
    pipeline 2128) - the script's own handling of that is what the
    too-few-tracked-files fixture above pins, not this test's job."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
