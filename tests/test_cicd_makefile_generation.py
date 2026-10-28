"""Run the real CLI and the shipped Tier 4 snippet against scratch projects."""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / ".claude/commands/cpp/init.md"


def project(tmp_path: Path, framework: str = "node") -> Path:
    if framework == "node":
        (tmp_path / "package.json").write_text(json.dumps({"name": "fixture", "version": "0.0.0"}))
        (tmp_path / "package-lock.json").write_text("{}")
    else:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="0.0.0"\n')
        (tmp_path / "uv.lock").write_text("")
    return tmp_path


def cli(root: Path, *options: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "lib.cicd", "detect", "--path", str(root), *options],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.mark.parametrize("framework,command", [("node", "npm test"), ("python", "uv run pytest")])
@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.skipif(shutil.which("uv") is None, reason="requires uv")
@pytest.mark.skipif(shutil.which("env") is None, reason="requires env")
def test_actual_tier4_snippet_generates_framework_makefile(tmp_path, framework, command):
    root = project(tmp_path, framework)
    assert not (root / "Makefile").exists()
    # The source intentionally pins Python3.11. Do not mistake an unavailable
    # interpreter for a regression in the generator, or download one in a test.
    available = subprocess.run(
        ["uv", "python", "find", "3.11"],
        env=dict(os.environ, UV_PYTHON_DOWNLOADS="never"),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if available.returncode:
        pytest.skip("requires an installed Python3.11 for the actual pinned snippet")
    text = INIT.read_text().split("If no Makefile exists, offer to generate one:", 1)[1]
    block = re.search(r"```bash\n(.*?)```", text, re.S)
    assert block, "the actual Tier4 generation block must exist"
    result = subprocess.run(
        ["bash", "-c", block[1]],
        cwd=root,
        env=dict(os.environ, CPP_DIR=str(ROOT), UV_OFFLINE="1", UV_NO_SYNC="1"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    target = root / "Makefile"
    assert target.is_file(), result.stdout + result.stderr
    content = target.read_text()
    assert "# Detected:" in content, "a generic template is not framework generation"
    assert command in content
    assert "✓ Makefile generated" in result.stdout


@pytest.mark.parametrize("framework", ["node", "python"])
def test_cli_generation_reports_written_path(tmp_path, framework):
    root = project(tmp_path, framework)
    assert not (root / "Makefile").exists()
    result = cli(root, "--generate-makefile")
    assert result.returncode == 0, result.stderr
    assert (root / "Makefile").is_file()
    assert str(root / "Makefile") in result.stdout


def test_existing_file_refused_and_preserved_without_force(tmp_path):
    root = project(tmp_path)
    target = root / "Makefile"
    before = b"# owner content\ncustom:\n\t@echo preserve\n"
    target.write_bytes(before)
    target.chmod(0o640)
    result = cli(root, "--generate-makefile")
    assert result.returncode == 1, result.stderr
    assert "already exists" in result.stderr
    assert target.read_bytes() == before
    assert target.stat().st_mode & 0o777 == 0o640


def test_explicit_force_replaces_existing_file_and_preserves_mode(tmp_path):
    root = project(tmp_path)
    target = root / "Makefile"
    target.write_text("# owner content\n")
    target.chmod(0o640)
    result = cli(root, "--generate-makefile", "--force")
    assert result.returncode == 0, result.stderr
    assert "npm test" in target.read_text()
    assert target.stat().st_mode & 0o777 == 0o640


@pytest.mark.parametrize("dangling", [False, True])
def test_existing_symlink_is_refused_without_following_it(tmp_path, dangling):
    root = project(tmp_path)
    external = root / "owner-target"
    if not dangling:
        external.write_text("owner bytes\n")
    else:
        assert not external.exists()
    target = root / "Makefile"
    target.symlink_to(external.name)
    assert target.is_symlink()
    result = cli(root, "--generate-makefile")
    assert result.returncode == 1, result.stderr
    assert "already exists" in result.stderr
    assert target.is_symlink()
    if dangling:
        assert not external.exists()
    else:
        assert external.read_text() == "owner bytes\n"


def test_force_replaces_symlink_entry_without_modifying_its_target(tmp_path):
    root = project(tmp_path)
    external = root / "owner-target"
    external.write_text("owner bytes\n")
    target = root / "Makefile"
    target.symlink_to(external.name)
    assert target.is_symlink()
    result = cli(root, "--generate-makefile", "--force")
    assert result.returncode == 0, result.stderr
    assert not target.is_symlink()
    assert "npm test" in target.read_text()
    assert external.read_text() == "owner bytes\n"


def test_force_cannot_replace_a_directory(tmp_path):
    root = project(tmp_path)
    target = root / "Makefile"
    target.mkdir()
    (target / "owner-file").write_text("preserve\n")
    result = cli(root, "--generate-makefile", "--force")
    assert result.returncode == 1, result.stderr
    assert "generation failed" in result.stderr
    assert (target / "owner-file").read_text() == "preserve\n"
    assert sorted(p.name for p in root.iterdir()) == ["Makefile", "package-lock.json", "package.json"]


def test_json_generation_reports_only_the_created_artifact(tmp_path):
    root = project(tmp_path)
    result = cli(root, "--generate-makefile", "--json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["makefile"] == {"path": str(root / "Makefile"), "status": "written"}
    assert report["framework"] == "node"


def test_force_requires_generation_and_does_not_write(tmp_path):
    root = project(tmp_path)
    assert not (root / "Makefile").exists()
    result = cli(root, "--force")
    assert result.returncode == 2
    assert "--force requires --generate-makefile" in result.stderr
    assert not (root / "Makefile").exists()


@pytest.mark.parametrize("link_error", [errno.EPERM, errno.EXDEV], ids=["EPERM", "EXDEV"])
@pytest.mark.parametrize("late_existing", [False, True], ids=["absent", "late-existing"])
def test_link_failure_is_named_and_never_falls_back(tmp_path, monkeypatch, capsys, link_error, late_existing):
    from lib.cicd.cli import main

    root = project(tmp_path)
    target = root / "Makefile"
    assert not target.exists()
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    reached = []

    def refuse_link(source, destination):
        source, destination = Path(source), Path(destination)
        assert source.parent.parent == root, "staging must stay inside the destination directory"
        assert source.stat().st_dev == root.stat().st_dev, "ordinary publication stays on one device"
        assert destination == target
        assert source.is_file() and not destination.exists()
        if late_existing:
            destination.write_text("# concurrent owner file\n")
        reached.append(True)
        raise OSError(link_error, "injected link failure")

    monkeypatch.setattr(os, "link", refuse_link)
    assert main(["detect", "--path", str(root), "--generate-makefile"]) == 1
    output = capsys.readouterr()
    assert reached == [True], "the failure must exercise the actual publish operation"
    assert "Makefile generation failed:" in output.err
    assert "injected link failure" in output.err
    assert "Wrote Makefile:" not in output.out
    for name, data in before.items():
        assert (root / name).read_bytes() == data
    if late_existing:
        assert target.read_text() == "# concurrent owner file\n"
    else:
        assert not target.exists()
    assert not list(root.glob(".cpp-makefile-*"))
