"""The guard that keeps real-history tests off the network (issue #1718).

CI's clone is partial (`--depth=1 --filter=tree:0`): a read of an absent
object is a fetch from the remote. `tests/conftest.py::skip_in_partial_clone`
skips such a test there, and ONLY there. These tests hold both directions: a
full clone runs, a partial clone skips with the reason that names who does the
comparison instead, and a repository git cannot read is neither.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import PARTIAL_CLONE_SKIP_REASON, is_partial_clone, skip_in_partial_clone

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="requires git")

_GIT = ["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
        "-c", "commit.gpgsign=false", "-c", "protocol.file.allow=always"]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run([*_GIT, *args], cwd=cwd, check=True, capture_output=True, timeout=60)


@pytest.fixture()
def source(tmp_path: Path) -> Path:
    """A two-commit repository to clone from, allowing filtered fetches."""
    src = tmp_path / "source"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main", f"--template={tmp_path / 'no-template'}")
    for name in ("one", "two"):
        (src / name).write_text(name)
        _git(src, "add", name)
        _git(src, "commit", "-q", "-m", name)
    _git(src, "config", "uploadpack.allowFilter", "true")
    _git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    return src


def _clone(source: Path, dest: Path, *extra: str) -> Path:
    _git(source.parent, "clone", "-q", *extra, f"file://{source}", str(dest))
    return dest


def test_a_full_clone_is_not_partial_and_the_test_runs(source: Path, tmp_path: Path) -> None:
    full = _clone(source, tmp_path / "full")
    assert is_partial_clone(full) is False
    skip_in_partial_clone(full)  # returns: the calling test goes on


def test_a_shallow_clone_that_is_not_partial_runs_too(source: Path, tmp_path: Path) -> None:
    """Shallow alone makes no network read: an absent commit is just absent."""
    shallow = _clone(source, tmp_path / "shallow", "--depth=1")
    out = subprocess.run(["git", "-C", str(shallow), "rev-parse", "--is-shallow-repository"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "true", "the fixture must be shallow for this to say anything"
    assert is_partial_clone(shallow) is False


def test_cis_own_clone_shape_is_partial_and_skips_with_the_reason(source: Path, tmp_path: Path) -> None:
    partial = _clone(source, tmp_path / "partial", "--depth=1", "--filter=tree:0")
    assert is_partial_clone(partial) is True
    with pytest.raises(pytest.skip.Exception) as skipped:
        skip_in_partial_clone(partial)
    assert str(skipped.value) == PARTIAL_CLONE_SKIP_REASON
    assert "negative-controls CI step" in PARTIAL_CLONE_SKIP_REASON


def test_the_extension_alone_is_partial(source: Path, tmp_path: Path) -> None:
    full = _clone(source, tmp_path / "ext")
    assert is_partial_clone(full) is False
    _git(full, "config", "extensions.partialclone", "origin")
    assert is_partial_clone(full) is True


def test_a_promisor_setting_of_false_is_not_partial(source: Path, tmp_path: Path) -> None:
    full = _clone(source, tmp_path / "off")
    _git(full, "config", "remote.origin.promisor", "false")
    assert is_partial_clone(full) is False


@pytest.mark.parametrize("damage", ["broken-config", "not-a-repository"])
def test_a_repository_git_cannot_read_is_an_error_not_a_skip_and_not_a_no(
        source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str) -> None:
    if damage == "broken-config":
        repo = _clone(source, tmp_path / "broken")
        with (repo / ".git" / "config").open("a") as handle:
            handle.write('[remote "origin"\n  promisor = \n')
    else:
        repo = tmp_path / "plain-directory"
        repo.mkdir()
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
        outside = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"],
                                 capture_output=True, text=True, check=False)
        assert outside.returncode != 0, "the fixture must be outside any repository"
    with pytest.raises(AssertionError, match="could not say whether"):
        skip_in_partial_clone(repo)
