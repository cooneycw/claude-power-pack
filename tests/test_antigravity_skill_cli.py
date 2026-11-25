"""Actual thin CLI, shared core and complete canonical output in disposable repos."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/antigravity-skill-sync.py"
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for immutable source")


def command(*args, cwd=None):
    return subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.mark.parametrize("shape", ["checkout", "worktree", "shallow"])
@pytest.mark.parametrize("location", ["root", "external"])
def test_actual_cli_build_then_verify_complete_output(tmp_path, shape, location):
    source = tmp_path / "source"
    if shape == "worktree":
        clone = tmp_path / "clone"
        command("git", "clone", "-q", "--no-hardlinks", ROOT, clone)
        command("git", "-C", clone, "worktree", "add", "--detach", source, "HEAD")
    else:
        args = ["git", "clone", "-q"] + (["--depth=1"] if shape == "shallow" else [])
        command(*args, ROOT.as_uri(), source)
    if shape == "shallow":
        assert command("git", "-C", source, "rev-parse", "--is-shallow-repository") == "true"
    output = tmp_path / "output"
    base = [sys.executable, CLI, "--source-root", source, "--output-root", output, "--json"]
    cwd = ROOT if location == "root" else tmp_path
    report = json.loads(command(*base, "--write", cwd=cwd))
    assert report["exit_code"] == 0 and report["coverage"] == "antigravity-topic-build-only"
    row = report["results"][0]
    assert row["after"]["expected_packages"] == 18
    guide = output / "python-packaging/references/docs/skills/python-packaging.md"
    assert guide.is_file() and "pyproject.toml" in guide.read_text()
    assert json.loads(command(*base, "--check", cwd=cwd))["exit_code"] == 0
    guide.unlink()
    assert not guide.exists()
    missing = subprocess.run(list(map(str, [*base, "--check"])), cwd=cwd, capture_output=True, text=True)
    assert missing.returncode == 1 and json.loads(missing.stdout)["results"][0]["after"]["state"] == "absent"


def test_unknown_source_and_canonical_output_overlap_refused(tmp_path):
    missing = tmp_path / "missing-source"
    assert not missing.exists()
    result = subprocess.run([sys.executable, str(CLI), "--source-root", str(missing),
                             "--output-root", str(tmp_path / "out"), "--write", "--json"],
                            capture_output=True, text=True)
    assert result.returncode == 4 and json.loads(result.stdout)["exit_code"] == 4
    refused = subprocess.run([sys.executable, str(CLI), "--source-root", str(ROOT),
                              "--output-root", str(ROOT / ".claude/skills"), "--write", "--json"],
                             capture_output=True, text=True)
    assert refused.returncode == 1 and "overlaps" in json.loads(refused.stdout)["results"][0]["reason"]
