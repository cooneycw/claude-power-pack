"""Recorded metadata stays safe under CI's pinned, history-based secret scan."""

import copy
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "controls/secret-scan/cases/plan-record-history"
GUIDANCE = ("Run-start already records the starting commit; do not restate hashes in free text "
            "or place api/key/token beside them.")
GIT = shutil.which("git")
STAGE = 'mkdir -p .ci-bin && cp "$(command -v gitleaks)" .ci-bin/gitleaks'
requires_git = pytest.mark.skipif(GIT is None, reason="UNKNOWN: git unavailable; history scan not run")
requires_scanner = pytest.mark.skipif(
    shutil.which("gitleaks") is None, reason="UNKNOWN: pinned gitleaks 8.30.1 unavailable; scan not run",
)


def pipeline() -> dict:
    return yaml.safe_load((ROOT / ".woodpecker.yml").read_text())


def assert_staged(config: dict) -> None:
    secret = config["steps"]["secret-scan"]
    validate = config["steps"]["validate"]
    assert secret["image"].startswith("zricethezav/gitleaks:v8.30.1@sha256:")
    assert STAGE in secret["commands"]
    assert "secret-scan" in validate["depends_on"]
    assert any(command.startswith('PATH="$PWD/.ci-bin:$PATH" uv run pytest ')
               for command in validate["commands"])


def pinned_scanner() -> str:
    executable = shutil.which("gitleaks")
    if executable is None:
        pytest.skip("UNKNOWN: pinned gitleaks 8.30.1 unavailable; scan not run")
    version = subprocess.run([executable, "version"], capture_output=True, text=True, check=False)
    if version.returncode or version.stdout.strip().removeprefix("v") != "8.30.1":
        pytest.skip("UNKNOWN: gitleaks is not the required 8.30.1; scan not run")
    return executable


def git(repo: Path, *args: str) -> str:
    assert GIT is not None
    result = subprocess.run(
        [GIT, "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", *args], capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def scan(repo: Path, content: bytes) -> subprocess.CompletedProcess[str]:
    scanner = pinned_scanner()
    repo.mkdir()
    git(repo, "init", "-q")
    record = repo / "docs/flow-runs/issue-1871.md"
    record.parent.mkdir(parents=True)
    record.write_bytes(content)
    assert record.read_bytes() == content
    for name in (".gitleaks.toml", ".gitleaks-findings.tmpl"):
        shutil.copyfile(ROOT / name, repo / name)
        assert (repo / name).read_bytes() == (ROOT / name).read_bytes()
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "owned scan input")
    commands = [shlex.split(command) for command in pipeline()["steps"]["secret-scan"]["commands"]
                if command.startswith("gitleaks detect ")]
    assert len(commands) == 1
    command = commands[0]
    assert "--no-git" not in command
    command[0] = scanner  # Same CI argv; executable resolved before changing cwd.
    return subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)


def test_section_b_guidance_does_not_restate_the_starting_commit() -> None:
    assert GUIDANCE in (ROOT / "docs/agents/flow-plan-record.md").read_text()


def test_ci_stages_the_pinned_scanner_for_pytest() -> None:
    config = pipeline()
    assert_staged(config)
    missing = copy.deepcopy(config)
    missing["steps"]["secret-scan"]["commands"].remove(STAGE)
    assert STAGE not in missing["steps"]["secret-scan"]["commands"]
    assert len(missing["steps"]["secret-scan"]["commands"]) == len(config["steps"]["secret-scan"]["commands"]) - 1
    with pytest.raises(AssertionError):
        assert_staged(missing)


def test_new_fixtures_do_not_expand_the_registered_working_tree_cases() -> None:
    manifest = json.loads((ROOT / "controls/secret-scan/control.json").read_text())
    assert {case["input"] for case in manifest["cases"]} == {
        "cases/bad-private-key", "cases/good-short-body", "cases/good-clean", "cases/unknown-empty-target",
    }


def test_scanner_absence_on_a_restricted_path_is_an_unknown_skip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    assert shutil.which("gitleaks") is None
    with pytest.raises(pytest.skip.Exception, match="UNKNOWN: pinned gitleaks"):
        pinned_scanner()


def test_wrong_scanner_version_is_an_unknown_skip(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/fixture/gitleaks")
    monkeypatch.setattr(subprocess, "run", lambda args, **_: subprocess.CompletedProcess(args, 0, "0.0.0\n", ""))
    with pytest.raises(pytest.skip.Exception, match="UNKNOWN: gitleaks is not"):
        pinned_scanner()


@requires_git
@requires_scanner
@pytest.mark.parametrize(("case", "expected"), (("bad-api-main", 1), ("good-generated-header", 0)))
def test_ci_history_scan_distinguishes_committed_record_forms(tmp_path: Path, case: str, expected: int) -> None:
    content = (CASES / f"{case}.md").read_bytes()
    assert content
    result = scan(tmp_path / "scan", content)
    assert result.returncode == expected
    if expected:
        assert "RuleID: generic-api-key" in result.stdout
        assert "File: docs/flow-runs/issue-1871.md" in result.stdout
    else:
        assert "RuleID:" not in result.stdout


@requires_git
@requires_scanner
def test_actual_generated_header_is_safe_for_the_ci_reader(tmp_path: Path) -> None:
    repo = tmp_path / "generator"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "source.txt").write_text("fixture\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "preserved fixture")
    commit = git(repo, "rev-parse", "HEAD")
    helper = ROOT / "scripts/flow-plan-record.py"
    for args in (("reconcile", "1871"), ("begin-run", "1871"),
                 ("declare-salvage", "1871", commit, "--reason", "fixture preservation")):
        subprocess.run([sys.executable, str(helper), *args], cwd=repo, env=os.environ.copy(),
                       capture_output=True, text=True, check=True)
    record = (repo / "docs/flow-runs/issue-1871.md").read_text()
    assert re.search(r"^- Run-id: +[0-9a-f]{32}$", record, re.M)
    for name in ("Run-start", "Salvage"):
        assert re.search(rf"^- {name}: +{commit}$", record, re.M)
    result = scan(tmp_path / "reader", record.encode())
    assert result.returncode == 0
    assert "RuleID:" not in result.stdout
