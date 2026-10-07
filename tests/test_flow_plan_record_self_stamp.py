"""Control for flow-plan-record.py's own-copy identification (issue #1399).

A kyle-installed `~/.claude/scripts/flow-plan-record.py` copy can silently
differ from the checkout and omit a fix the checkout already carries (Nit
Store #864 comment 5874632553), and nothing printed alongside a verdict said
so. These cases run the production entry point and assert on its printed
`FLOW_PLAN_RECORD_SELF` line, never re-implement `self_stamp()` directly -
the same rule `test_flow_plan_record.py` states for its own subject.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "scripts" / "flow-plan-record.py"

STAMP_RE = re.compile(r"^FLOW_PLAN_RECORD_SELF: (.+)$", re.M)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


def _make_cwd(tmp_path: Path, name: str) -> Path:
    """A minimal git repo for the command to examine - any valid one will do;
    these cases are about the RUNNING COPY's own identity, not this tree."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "t")
    return repo


def _stamp_from(copy_path: Path, cwd: Path) -> str:
    proc = subprocess.run(
        ["python3", str(copy_path), "drift", "42"],
        cwd=cwd, capture_output=True, text=True,
    )
    m = STAMP_RE.search(proc.stdout)
    assert m, f"no FLOW_PLAN_RECORD_SELF line in output:\n{proc.stdout}{proc.stderr}"
    return m.group(1)


@requires_git
def test_two_differing_copies_report_different_stamps(tmp_path: Path) -> None:
    """The stamp must reflect CONTENT, not merely existing.

    Both copies live outside any git work tree (no `.git` under tmp_path
    beyond the unrelated cwd repos), so this exercises the content-hash
    fallback specifically - the shape a kyle-installed copy with no `.git`
    anywhere nearby actually takes.
    """
    original = HELPER.read_bytes()
    copy_a = tmp_path / "copy-a.py"
    copy_b = tmp_path / "copy-b.py"
    copy_a.write_bytes(original)
    copy_b.write_bytes(original + b"\n# one byte different\n")
    stamp_a = _stamp_from(copy_a, _make_cwd(tmp_path, "cwd-a"))
    stamp_b = _stamp_from(copy_b, _make_cwd(tmp_path, "cwd-b"))
    assert stamp_a != stamp_b, f"two different copies produced the same stamp: {stamp_a!r}"
    assert "content-" in stamp_a and "content-" in stamp_b, (
        f"expected the content-hash fallback (no .git beside the copy): {stamp_a!r}, {stamp_b!r}"
    )


@requires_git
def test_two_byte_identical_copies_report_the_same_stamp(tmp_path: Path) -> None:
    """The inverse: a stamp keyed on path or mtime would differ here even
    though the content is identical - a CONTENT stamp must not."""
    original = HELPER.read_bytes()
    copy_a = tmp_path / "copy-a.py"
    copy_b = tmp_path / "copy-b.py"
    copy_a.write_bytes(original)
    copy_b.write_bytes(original)
    stamp_a = _stamp_from(copy_a, _make_cwd(tmp_path, "cwd-a"))
    stamp_b = _stamp_from(copy_b, _make_cwd(tmp_path, "cwd-b"))
    assert stamp_a == stamp_b, (
        f"two byte-identical copies produced different stamps: {stamp_a!r} vs {stamp_b!r}"
    )


@requires_git
def test_an_uncommitted_edit_to_the_script_itself_changes_the_stamp(tmp_path: Path) -> None:
    """Counter-model review (#1399): the commit-only half of the stamp names
    the CHECKOUT's HEAD, which does not move when this exact file gets an
    uncommitted local edit - two different sets of bytes at the same HEAD
    would otherwise read as the same copy. The content hash must differ even
    though `worktree-at-<sha>` does not.
    """
    repo = tmp_path / "wt"
    repo.mkdir()
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    committed = scripts_dir / "flow-plan-record.py"
    committed.write_bytes(HELPER.read_bytes())
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@e.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "x"], check=True)

    stamp_clean = _stamp_from(committed, repo)
    with committed.open("a") as fh:
        fh.write("\n# an uncommitted local edit\n")
    stamp_dirty = _stamp_from(committed, repo)

    assert "worktree-at-" in stamp_clean and "worktree-at-" in stamp_dirty, (
        f"expected the git-tracked branch for both: {stamp_clean!r}, {stamp_dirty!r}"
    )
    assert stamp_clean.split()[0] == stamp_dirty.split()[0], (
        "precondition: HEAD must not have moved between the two readings"
    )
    assert stamp_clean != stamp_dirty, (
        f"an uncommitted edit to the script itself did not change its stamp: {stamp_clean!r}"
    )


@requires_git
def test_the_stamp_appears_beside_every_verdict_producing_subcommand(tmp_path: Path) -> None:
    """compliance, drift and head-check each print it - a stale copy lies in
    every sub-command, not only the one that happened to be measured."""
    cwd = _make_cwd(tmp_path, "repo")
    (cwd / "README.md").write_text("x\n")
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-qm", "base")
    for args in (["drift", "42"], ["compliance", "42"], ["head-check", "42", "--head", "0" * 40]):
        proc = subprocess.run(["python3", str(HELPER), *args], cwd=cwd,
                              capture_output=True, text=True)
        assert STAMP_RE.search(proc.stdout), (
            f"{args[0]} printed no FLOW_PLAN_RECORD_SELF line:\n{proc.stdout}{proc.stderr}"
        )
