"""Actual thin CLI, shared core and complete canonical output in disposable repos."""
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/antigravity-skill-sync.py"
pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for immutable source")


def command(*args, cwd=None):
    result = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, (args, result.returncode, result.stdout, result.stderr)
    return result.stdout.strip()


@pytest.mark.parametrize("shape", ["checkout", "worktree", "shallow"])
@pytest.mark.parametrize("location", ["root", "external"])
def test_actual_cli_build_then_verify_complete_output(tmp_path, shape, location):
    source = tmp_path / "source"
    # Snapshot committed build inputs, not the CI checkout's transport/history.
    # Sibling CI steps may deepen that shared repository while tests run.
    seed = tmp_path / "seed"
    seed.mkdir()
    archive = tmp_path / "inputs.tar"
    command("git", "-C", ROOT, "archive", "--format=tar", f"--output={archive}",
            "HEAD", ".claude/skills", "docs", "scripts")
    with tarfile.open(archive) as members:
        for member in members:
            target = seed / member.name
            assert target.resolve().is_relative_to(seed)
            assert member.isdir() or member.isfile(), member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                content = members.extractfile(member)
                assert content is not None
                target.write_bytes(content.read())
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    command("git", "-C", seed, "init", "-q")
    command("git", "-C", seed, "add", ".")
    command("git", "-C", seed, "-c", "user.name=Fixture",
            "-c", "user.email=fixture@example.invalid", "commit", "-qm", "source")
    if shape == "worktree":
        command("git", "-C", seed, "worktree", "add", "--detach", source, "HEAD")
    elif shape == "shallow":
        command("git", "clone", "-q", "--depth=1", seed.as_uri(), source)
    else:
        source = seed
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
