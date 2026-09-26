"""Regression tests for the silently-ignored-file guard (issue #430, Finding 1).

The `.gitignore` blanket-ignore + negation-allowlist pattern silently drops
new files the repo should track. `scripts/check-ignored-additions.sh` makes
that loud. These tests pin its behaviour: warn on an individual ignored file
in a tracked source dir, stay silent on the usual venv/cache noise.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.helper_exit_line import without_status

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "check-ignored-additions.sh"

# These tests drive real `git` and `bash` subprocesses. The Woodpecker
# `validate` step runs in `uv:python3.11-bookworm-slim`, which ships bash but
# NOT git, so without this guard the module errors (FileNotFoundError) and
# fails CI. Skip cleanly where git/bash are unavailable (issue #430).
pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH",
)


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
    assert without_status(result.stderr) == ""


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
    assert without_status(result.stderr) == ""


def test_negated_file_is_not_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, "*.json\n!renovate.json\n")
    # renovate.json is negated -> tracked, so it must NOT be reported.
    (repo / "renovate.json").write_text("{}", encoding="utf-8")

    result = _run(repo)
    assert result.returncode == 0
    assert without_status(result.stderr) == ""


def test_intentional_ignore_is_silent(tmp_path: Path) -> None:
    # Files git-ignored BY DESIGN (env-only per-machine .claude/ runtime state)
    # must not trip the guard - they are never intended additions (issue #504).
    repo = tmp_path / "repo"
    _init_repo(repo, ".claude/settings*.json\n.claude/friction.jsonl\n")
    claude = repo / ".claude"
    claude.mkdir()
    (claude / "settings.local.json").write_text("{}", encoding="utf-8")
    (claude / "friction.jsonl").write_text("{}\n", encoding="utf-8")

    result = _run(repo)
    assert result.returncode == 0
    assert without_status(result.stderr) == ""


def test_unlisted_claude_file_still_warns(tmp_path: Path) -> None:
    # The allow-list is a specific set of paths, NOT a blanket .claude/ exemption:
    # an ignored .claude/ file that is not on the list is still the trap and must
    # still warn, or the guard would silently swallow real mistakes (issue #504).
    repo = tmp_path / "repo"
    _init_repo(repo, ".claude/*.json\n")
    claude = repo / ".claude"
    claude.mkdir()
    (claude / "mystery-config.json").write_text("{}", encoding="utf-8")

    result = _run(repo)
    assert result.returncode == 0  # advisory by default
    assert "WARNING" in result.stderr
    assert ".claude/mystery-config.json" in result.stderr


# --- issue #1258: a worktree's own ignored addition blocks -------------------
#
# A flow worktree is created clean from a tracked tree, so a non-scratch ignored
# file in it was written during that run - the class that ships a clean clone
# without it (#1144). The same file in the primary checkout is ordinary local
# clutter and stays advisory.


def _worktree(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    _init_repo(repo, "*.json\n")
    wt = tmp_path / "repo-issue-1"
    _git(repo, "worktree", "add", "-q", "-b", "issue-1-x", str(wt))
    return repo, wt


def test_ignored_addition_in_a_linked_worktree_blocks(tmp_path: Path) -> None:
    _, wt = _worktree(tmp_path)
    (wt / "manifest.json").write_text("{}", encoding="utf-8")
    # Precondition: the file really is ignored in the worktree.
    assert subprocess.run(["git", "check-ignore", "-q", "manifest.json"], cwd=wt).returncode == 0
    result = _run(wt)
    assert result.returncode == 3
    assert "ERROR" in result.stderr
    assert "a clean clone will not have them" in result.stderr
    assert "CHECK_IGNORED_ADDITIONS_MODE=blocking" in result.stderr


def test_same_file_in_the_primary_checkout_stays_advisory(tmp_path: Path) -> None:
    repo, _ = _worktree(tmp_path)
    (repo / "manifest.json").write_text("{}", encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 0
    assert "manifest.json" in result.stderr
    assert "CHECK_IGNORED_ADDITIONS_MODE=advisory" in result.stderr


def test_advisory_flag_overrides_the_worktree_default(tmp_path: Path) -> None:
    _, wt = _worktree(tmp_path)
    (wt / "manifest.json").write_text("{}", encoding="utf-8")
    result = _run(wt, "--advisory")
    assert result.returncode == 0
    assert "WARNING" in result.stderr


def test_a_failed_gates_leftover_run_state_never_blocks_a_worktree(tmp_path: Path) -> None:
    # lib.cicd leaves .claude/runs/<plan>-<id>.json behind when a gate FAILS.
    # Blocking on it would make every run after the first red gate block too.
    _, wt = _worktree(tmp_path)
    (wt / ".claude" / "runs").mkdir(parents=True)
    (wt / ".claude" / "runs" / "finish-deadbeef.json").write_text("{}", encoding="utf-8")
    assert subprocess.run(
        ["git", "check-ignore", "-q", ".claude/runs/finish-deadbeef.json"], cwd=wt
    ).returncode == 0
    result = _run(wt)
    assert result.returncode == 0
    assert without_status(result.stderr) == ""


def test_a_local_env_file_is_runtime_config_not_a_swallowed_addition(tmp_path: Path) -> None:
    # counter-model review: `.env` is ignored so that it is NEVER committed.
    repo = tmp_path / "repo"
    _init_repo(repo, ".env\n.env.*\n")
    wt = tmp_path / "repo-issue-1"
    _git(repo, "worktree", "add", "-q", "-b", "issue-1-x", str(wt))
    (wt / ".env").write_text("X=1\n", encoding="utf-8")
    (wt / ".env.local").write_text("X=1\n", encoding="utf-8")
    assert _run(wt).returncode == 0


def test_an_ignored_env_template_still_blocks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo, ".env*\n")
    wt = tmp_path / "repo-issue-1"
    _git(repo, "worktree", "add", "-q", "-b", "issue-1-x", str(wt))
    (wt / ".env.example").write_text("X=\n", encoding="utf-8")
    result = _run(wt)
    assert result.returncode == 3
    assert ".env.example" in result.stderr


def test_an_unreadable_inventory_is_not_a_clean_result(tmp_path: Path) -> None:
    """counter-model review: `git status` failing inside a process substitution
    produced no entries and exit 0 - the same bytes as a clean tree."""
    import os

    _, wt = _worktree(tmp_path)
    real_git = shutil.which("git")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "git"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'case "$1" in status) exit 128 ;; esac\n'
        f'exec "{real_git}" "$@"\n'
    )
    shim.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
    result = subprocess.run(["bash", str(GUARD)], cwd=wt, capture_output=True, text=True, env=env)
    assert result.returncode == 4
    assert "NOT inspected" in result.stderr
    advisory = subprocess.run(
        ["bash", str(GUARD), "--advisory"], cwd=wt, capture_output=True, text=True, env=env
    )
    assert advisory.returncode == 0
    assert "NOT inspected" in advisory.stderr
