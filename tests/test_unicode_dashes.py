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

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-unicode-dashes.py"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git on PATH")


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True, text=True,
    )


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
        env={"HOME": str(cwd), "PATH": "/usr/bin:/bin",  # negative-fixture: allow PATH is isolation, not an absence
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


def test_the_real_repo_is_currently_clean() -> None:
    """Regression-test EXECUTION against the live tree, not a committed case."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
