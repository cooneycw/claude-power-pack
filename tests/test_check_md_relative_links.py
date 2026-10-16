"""`scripts/check-md-relative-links.py` - relative markdown links in tracked docs resolve (#1413)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check-md-relative-links.py"

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

_spec = importlib.util.spec_from_file_location("check_md_relative_links", SCRIPT)
assert _spec and _spec.loader
LINKS = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = LINKS
_spec.loader.exec_module(LINKS)


def _repo(tmp_path: Path, files: dict[str, str], tracked: bool = True) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    env = dict(os.environ)
    subprocess.run(["git", "init", "-q"], cwd=root, env=env, check=True, capture_output=True)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if tracked:
        subprocess.run(["git", "add", "-A"], cwd=root, env=env, check=True, capture_output=True)
    return root


def _run(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", str(SCRIPT), "--root", str(root), "--min-files", "1", *extra],
                          capture_output=True, text=True)


# --------------------------------------------------------------------------- #
# What counts as a relative link.
# --------------------------------------------------------------------------- #

def test_links_outside_code_are_found_with_line_numbers() -> None:
    text = "# T\n\n[a](a.md) and [b](sub/b.md#h)\n"
    assert LINKS.links_in(text) == [(3, "a.md"), (3, "sub/b.md")]


@pytest.mark.parametrize("line", [
    "[u](https://example.com/a.md)",
    "[m](mailto:x@example.com)",
    "[h](#heading)",
    "[abs](/etc/passwd)",
    "![img](missing.png)",
    "`[code](gone.md)`",
    "``[code](gone.md) with ` inside``",
])
def test_non_relative_or_code_links_are_not_examined(line: str) -> None:
    assert LINKS.links_in(line + "\n") == []


def test_links_in_fences_are_not_examined_and_the_fence_closes() -> None:
    text = "```md\n[gone](gone.md)\n```\n[live](live.md)\n~~~~\n[g](g.md)\n~~~~\n"
    assert LINKS.links_in(text) == [(4, "live.md")]


def test_a_blockquoted_fence_is_a_fence() -> None:
    text = "> ```\n> [gone](gone.md)\n> ```\n"
    assert LINKS.links_in(text) == []


def test_angle_bracket_and_titled_targets() -> None:
    assert LINKS.links_in('[a](<with space.md>) [b](b.md "title")\n') == [
        (1, "with space.md"), (1, "b.md")]


# --------------------------------------------------------------------------- #
# The gate, two-sided.
# --------------------------------------------------------------------------- #

@requires_git
def test_a_dead_link_is_reported_by_path_and_line(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"README.md": "# R\n\n[g](guide.md)\n"})
    assert not (root / "guide.md").exists()
    proc = _run(root)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "README.md:3: (guide.md) does not exist" in proc.stderr


@requires_git
def test_links_resolve_from_the_linking_documents_directory(tmp_path: Path) -> None:
    root = _repo(tmp_path, {
        "README.md": "[d](docs/a.md)\n",
        "docs/a.md": "[up](../README.md) [side](b.md)\n",
        "docs/b.md": "x\n",
    })
    proc = _run(root)
    assert proc.returncode == 0, proc.stderr
    assert "ok - 3 relative link(s) across 3 tracked .md file(s)" in proc.stdout


@requires_git
def test_a_root_relative_reading_would_miss_this(tmp_path: Path) -> None:
    """`b.md` exists at the root but not beside docs/a.md: dead from docs/."""
    root = _repo(tmp_path, {"README.md": "[ok](b.md)\n", "b.md": "x\n", "docs/a.md": "[b](b.md)\n"})
    assert (root / "b.md").exists() and not (root / "docs" / "b.md").exists()
    proc = _run(root)
    assert proc.returncode == 1
    assert "docs/a.md:1: (b.md) does not exist" in proc.stderr


@requires_git
def test_an_untracked_unignored_document_is_checked_before_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"README.md": "[x](x.md)\n", "x.md": "x\n"})
    (root / "new.md").write_text("[gone](gone.md)\n", encoding="utf-8")
    proc = _run(root)
    assert proc.returncode == 1
    assert "new.md:1: (gone.md)" in proc.stderr


@requires_git
def test_an_ignored_document_is_not_checked(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"README.md": "[x](x.md)\n", "x.md": "x\n", ".gitignore": "scratch/\n"})
    (root / "scratch").mkdir()
    (root / "scratch" / "n.md").write_text("[gone](gone.md)\n", encoding="utf-8")
    assert _run(root).returncode == 0


@requires_git
@pytest.mark.parametrize("prefix", LINKS.EXCLUDED_PREFIXES)
def test_excluded_prefixes_are_not_scanned(tmp_path: Path, prefix: str) -> None:
    root = _repo(tmp_path, {"README.md": "[x](x.md)\n", "x.md": "x\n",
                            f"{prefix}doc.md": "[gone](gone.md)\n"})
    proc = _run(root)
    assert proc.returncode == 0, proc.stderr


# --------------------------------------------------------------------------- #
# UNKNOWN is never clean.
# --------------------------------------------------------------------------- #

@requires_git
def test_zero_links_examined_is_unknown(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"README.md": "no links, only [a url](https://x.y/)\n"})
    proc = _run(root)
    assert proc.returncode == 2
    assert "UNKNOWN" in proc.stderr and "nothing was checked" in proc.stderr


@requires_git
def test_below_the_membership_floor_is_unknown(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"README.md": "[x](x.md)\n", "x.md": "x\n"})
    proc = subprocess.run(["python3", str(SCRIPT), "--root", str(root)],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    assert f"need >= {LINKS.MIN_TRACKED_MD_FILES}" in proc.stderr


def test_not_a_git_repository_is_unknown(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("requires git")
    (tmp_path / "README.md").write_text("[gone](gone.md)\n", encoding="utf-8")
    proc = _run(tmp_path, "--min-files", "1")
    assert proc.returncode == 2
    assert "could not list" in proc.stderr


def test_no_git_at_all_is_unavailable_not_unknown(tmp_path: Path) -> None:
    empty = tmp_path / "bin"
    empty.mkdir()
    py = shutil.which("python3")
    assert py
    assert shutil.which("git", path=str(empty)) is None
    proc = subprocess.run([py, str(SCRIPT), "--root", str(tmp_path), "--min-files", "1"],
                          env={**os.environ, "PATH": str(empty)}, capture_output=True, text=True)
    assert proc.returncode == 2
    assert "UNAVAILABLE - git is not installed" in proc.stderr


def test_the_real_tree_floor_is_the_default() -> None:
    assert LINKS.MIN_TRACKED_MD_FILES == 100
