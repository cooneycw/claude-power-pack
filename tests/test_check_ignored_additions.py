"""Regression tests for the silently-ignored-file guard (issue #430, Finding 1).

The `.gitignore` blanket-ignore + negation-allowlist pattern silently drops
new files the repo should track. `scripts/check-ignored-additions.sh` makes
that loud. These tests pin its behaviour: warn on an individual ignored file
in a tracked source dir, stay silent on the usual venv/cache noise.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "check-ignored-additions.sh"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path, gitignore: str) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "init")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(GUARD), *args], cwd=repo, capture_output=True, text=True
    )


def test_clean_repo_is_silent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, "*.json\n!package.json\n")
    result = _run(repo)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_warns_on_ignored_source_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, "*.json\n!package.json\n")
    (repo / "templates").mkdir()
    (repo / "templates" / "new-config.json").write_text("{}", encoding="utf-8")

    result = _run(repo)
    assert result.returncode == 0  # advisory by default
    assert "WARNING" in result.stderr
    assert "templates/new-config.json" in result.stderr


def test_strict_exits_nonzero_on_finding(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, "*.json\n")
    (repo / "data.json").write_text("{}", encoding="utf-8")

    result = _run(repo, "--strict")
    assert result.returncode == 3
    assert "data.json" in result.stderr


def test_ignores_venv_and_cache_noise(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, ".venv/\n__pycache__/\n*.pyc\n")
    # The usual scratch noise: a whole ignored dir + a stray pyc.
    venv = repo / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    pycache = repo / "pkg" / "__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "mod.cpython-311.pyc").write_text("x", encoding="utf-8")

    result = _run(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_negated_file_is_not_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, "*.json\n!renovate.json\n")
    # renovate.json is negated -> tracked, so it must NOT be reported.
    (repo / "renovate.json").write_text("{}", encoding="utf-8")

    result = _run(repo)
    assert result.returncode == 0
    assert result.stderr == ""
