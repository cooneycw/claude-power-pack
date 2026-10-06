"""Tests for scripts/skill-coverage-snapshot.py (#1370).

The full regeneration path needs a real skillc checkout and `uv run skillc`,
which this suite does not stand up - these tests pin the REFUSAL contract
(CI, dirty tree on either checkout) and the path-resolution fix a
counter-model review found, by stubbing `write_snapshot` rather than running
a real diagnose.
"""

from __future__ import annotations

import importlib.util
import json
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
        mod.main(["flow-check", "--cpp", str(tmp_path), "--skillc", str(tmp_path),
                   "--profile-dir", "cpp-codex-flow-check-ea6dbfa"])
    assert exc.value.code == 2


def test_profile_dir_is_required() -> None:
    """No default (#1370 refresh): omitting --profile-dir must refuse with a
    usage error, never silently fall back to a fixed profile directory."""
    with pytest.raises(SystemExit) as exc:
        mod.main(["flow-check", "--cpp", ".", "--skillc", "."])
    assert exc.value.code == mod.USAGE_EXIT


@needs_git
def test_profile_dir_path_traversal_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fix this test pins (counter-model review, 2026-10-06): an
    unvalidated --profile-dir let `../` and absolute paths escape
    evals/subjects/, so a clean skillc checkout could produce a snapshot
    from uncommitted data OUTSIDE it while recording the clean commit as
    provenance - defeating the whole point of _refuse_dirty."""
    _no_ci(monkeypatch)
    cpp, skillc = tmp_path / "cpp", tmp_path / "skillc"
    _init_repo(cpp)
    _init_repo(skillc)
    called = []
    monkeypatch.setattr(mod, "write_snapshot", lambda *a, **k: called.append(True))
    for escaping in ("../elsewhere", "/etc/passwd", "a/b"):
        with pytest.raises(SystemExit) as exc:
            mod.main(["flow-check", "--cpp", str(cpp), "--skillc", str(skillc), "--force-ci",
                       "--profile-dir", escaping])
        assert exc.value.code == 2, escaping
    assert not called, "write_snapshot must never run with an escaping --profile-dir"


@needs_git
def test_profile_dir_symlink_escape_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fix, the shape a plain string check cannot catch: a plain
    directory NAME that is a symlink pointing outside evals/subjects/."""
    _no_ci(monkeypatch)
    cpp, skillc = tmp_path / "cpp", tmp_path / "skillc"
    _init_repo(cpp)
    outside = tmp_path / "outside"
    outside.mkdir()
    _init_repo(skillc)
    subjects_dir = skillc / "evals" / "subjects"
    subjects_dir.mkdir(parents=True)
    (subjects_dir / "escape-link").symlink_to(outside, target_is_directory=True)
    subprocess.run(["git", "-C", str(skillc), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(skillc), "-c", "user.email=c@x.invalid", "-c", "user.name=c",
                     "commit", "--quiet", "-m", "add symlink"], check=True)
    called = []
    monkeypatch.setattr(mod, "write_snapshot", lambda *a, **k: called.append(True))
    with pytest.raises(SystemExit) as exc:
        mod.main(["flow-check", "--cpp", str(cpp), "--skillc", str(skillc), "--force-ci",
                   "--profile-dir", "escape-link"])
    assert exc.value.code == 2
    assert not called, "write_snapshot must never run with a profile-dir symlink escaping evals/subjects/"


@needs_git
def test_refuses_dirty_cpp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _no_ci(monkeypatch)
    cpp, skillc = tmp_path / "cpp", tmp_path / "skillc"
    _init_repo(cpp)
    _init_repo(skillc)
    (cpp / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        mod.main(["flow-check", "--cpp", str(cpp), "--skillc", str(skillc), "--force-ci",
                   "--profile-dir", "cpp-codex-flow-check-ea6dbfa"])
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
        mod.main(["flow-check", "--cpp", str(cpp), "--skillc", str(skillc), "--force-ci",
                   "--profile-dir", "cpp-codex-flow-check-ea6dbfa"])
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
    captured_paths: dict[str, Path] = {}
    captured_profile_dir = ""

    def fake_write_snapshot(skill: str, cpp_arg: Path, skillc_arg: Path, profile_dir: str, out_dir: Path) -> Path:
        nonlocal captured_profile_dir
        captured_paths["cpp"] = cpp_arg
        captured_paths["skillc"] = skillc_arg
        captured_profile_dir = profile_dir
        return tmp_path / "out.json"

    monkeypatch.setattr(mod, "write_snapshot", fake_write_snapshot)
    monkeypatch.chdir(tmp_path)
    mod.main(["flow-check", "--cpp", "cpp", "--skillc", "skillc", "--force-ci",
               "--profile-dir", "cpp-codex-flow-check-ea6dbfa"])
    assert captured_paths["cpp"].is_absolute()
    assert captured_paths["skillc"].is_absolute()
    assert captured_paths["cpp"] == cpp.resolve()
    assert captured_paths["skillc"] == skillc.resolve()
    assert captured_profile_dir == "cpp-codex-flow-check-ea6dbfa"


def test_snapshot_provenance_names_the_profile_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#1370 refresh, instruction 5: the written snapshot must name WHICH
    profile directory produced it, so a reader never has to guess which of
    skillc's (potentially several) re-declared profiles a snapshot came
    from."""
    monkeypatch.setattr(
        mod, "_repo_head", lambda repo: "cccccccccccccccccccccccccccccccccccccccc"
    )
    monkeypatch.setattr(
        mod, "_skillc_commit", lambda skillc: "dddddddddddddddddddddddddddddddddddddddd"
    )
    monkeypatch.setattr(
        mod, "_reference_digests",
        lambda skillc, skill, profile_dir: {
            "description_digest": "sha256:" + "a" * 64,
            "body_digest": "sha256:" + "b" * 64,
            "source": f"evals/subjects/{profile_dir}/evidence/inventory.json",
        },
    )
    monkeypatch.setattr(
        mod, "run_diagnose",
        lambda skillc, cpp, skill, profile_dir, cpp_revision: {
            "command": "skillc profile diagnose (stub)",
            "result": {"skills": {skill: {"status": "intact"}}, "problems": []},
        },
    )
    monkeypatch.setattr(mod, "digest_tree", lambda root: {})

    out_dir = tmp_path / "out"
    out_path = mod.write_snapshot(
        "flow-check", tmp_path / "cpp", tmp_path / "skillc", "cpp-codex-flow-check-ea6dbfa", out_dir
    )
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["diagnose"]["profile_dir"] == "cpp-codex-flow-check-ea6dbfa"
    assert "cpp-codex-flow-check-ea6dbfa" in written["reference"]["source"]


def test_reference_files_keys_match_digest_tree_on_a_real_closure(tmp_path: Path) -> None:
    """#1390, cpp-orch's precision point 2: `_reference_files`' keys (the
    inventory's `files[].source`, stripped of `codex/skills/<skill>/`) must
    land EXACTLY where `digest_tree()` (over the real on-disk closure) puts
    the same paths - a byte-identical tree must diff to ZERO. A real
    multi-directory closure, not a one-file fixture: a silent off-by-one in
    the prefix strip would either leave every key still prefixed (matching
    nothing) or strip too much (colliding two files), and a shallow tree
    cannot distinguish either from success."""
    skill_dir = tmp_path / "codex" / "skills" / "flow-check"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("skill md\n", encoding="utf-8")
    (skill_dir / "reference.md").write_text("reference\n", encoding="utf-8")
    (skill_dir / "lib" / "cicd").mkdir(parents=True)
    (skill_dir / "lib" / "cicd" / "__init__.py").write_text("", encoding="utf-8")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "helper.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    current = mod.digest_tree(skill_dir)
    assert set(current) == {"SKILL.md", "reference.md", "lib/cicd/__init__.py", "scripts/helper.sh"}

    inventory_entry = {
        "name": "flow-check",
        "description_digest": "sha256:" + "a" * 64,
        "body_digest": "sha256:" + "b" * 64,
        "files": [
            {"source": f"codex/skills/flow-check/{rel}", "digest": digest}
            for rel, digest in current.items()
        ],
    }
    reference_files = mod._reference_files(inventory_entry, "flow-check", tmp_path / "inventory.json")
    assert reference_files == current, (
        "same keys, same values - the dict equality itself is the zero-drift proof: "
        "a key-alignment bug would make this dict compare unequal to digest_tree()'s own output"
    )


def test_reference_files_refuses_a_source_outside_the_skill_prefix(tmp_path: Path) -> None:
    """The REFUSAL half of the same fix: an inventory file entry whose
    `source` does not start with `codex/skills/<skill>/` must raise rather
    than be silently skipped or mis-keyed - a skipped row is exactly the
    'nothing compared' failure mode cpp-orch named."""
    inventory_entry = {
        "name": "flow-check",
        "files": [{"source": "codex/skills/OTHER-SKILL/SKILL.md", "digest": "sha256:" + "a" * 64}],
    }
    with pytest.raises(SystemExit):
        mod._reference_files(inventory_entry, "flow-check", tmp_path / "inventory.json")
