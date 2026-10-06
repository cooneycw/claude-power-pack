"""Tests for scripts/skill-coverage-snapshot.py (#1370).

The full regeneration path needs a real skillc checkout and `uv run skillc`,
which this suite does not stand up - these tests pin the REFUSAL contract
(CI, dirty tree on either checkout) and the path-resolution fix a
counter-model review found, by stubbing `write_snapshot` rather than running
a real diagnose.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "skill-coverage-snapshot.py"


def _load():
    spec = importlib.util.spec_from_file_location("skill_coverage_snapshot", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git on PATH")


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "c@x.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "c"], check=True)
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "--quiet", "-m", "seed"], check=True)


def _no_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("WOODPECKER", raising=False)


@needs_git
def test_refuses_ci(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "1")
    with pytest.raises(SystemExit) as exc:
        mod.main(["flow-check", "--cpp", str(tmp_path), "--skillc", str(tmp_path)])
    assert exc.value.code == 2


@needs_git
def test_refuses_dirty_cpp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_ci(monkeypatch)
    cpp, skillc = tmp_path / "cpp", tmp_path / "skillc"
    _init_repo(cpp)
    _init_repo(skillc)
    (cpp / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        mod.main(["flow-check", "--cpp", str(cpp), "--skillc", str(skillc), "--force-ci"])
    assert exc.value.code == 2


@needs_git
def test_refuses_dirty_skillc_even_when_cpp_is_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fix this test pins (counter-model review, 2026-10-06): a dirty
    SKILLC checkout must refuse too, not only a dirty CPP one.
    `run_diagnose`/`_mint_subject`/`_mint_profile`/`_reference_digests` all
    read skillc's WORKING TREE (profile.json, subject.json,
    evidence/inventory.json) directly, while the snapshot records only
    `skillc_commit` (its HEAD) as provenance - an uncommitted edit there
    would run silently and be attributed to a commit that cannot reproduce
    it."""
    _no_ci(monkeypatch)
    cpp, skillc = tmp_path / "cpp", tmp_path / "skillc"
    _init_repo(cpp)
    _init_repo(skillc)
    (skillc / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(mod, "write_snapshot", lambda *a, **k: called.append(True))
    with pytest.raises(SystemExit) as exc:
        mod.main(["flow-check", "--cpp", str(cpp), "--skillc", str(skillc), "--force-ci"])
    assert exc.value.code == 2
    assert not called, "write_snapshot must never run against a dirty skillc checkout"


@needs_git
def test_relative_checkout_paths_resolve_before_any_subprocess_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fix this test pins (counter-model review, 2026-10-06):
    `run_diagnose` shells out with `cwd=skillc`, so a RELATIVE `--cpp` would
    resolve against the WRONG directory in that one call while every other
    call here (`git -C`, `_repo_head`) resolves it against the caller's cwd -
    diagnosing a repository that is not the one just checked clean. `main()`
    must hand `write_snapshot` ABSOLUTE paths regardless of what the caller
    typed."""
    _no_ci(monkeypatch)
    cpp, skillc = tmp_path / "cpp", tmp_path / "skillc"
    _init_repo(cpp)
    _init_repo(skillc)
    captured: dict[str, Path] = {}

    def fake_write_snapshot(skill: str, cpp_arg: Path, skillc_arg: Path, out_dir: Path) -> Path:
        captured["cpp"] = cpp_arg
        captured["skillc"] = skillc_arg
        return tmp_path / "out.json"

    monkeypatch.setattr(mod, "write_snapshot", fake_write_snapshot)
    monkeypatch.chdir(tmp_path)
    mod.main(["flow-check", "--cpp", "cpp", "--skillc", "skillc", "--force-ci"])
    assert captured["cpp"].is_absolute()
    assert captured["skillc"].is_absolute()
    assert captured["cpp"] == cpp.resolve()
    assert captured["skillc"] == skillc.resolve()
