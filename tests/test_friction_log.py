"""Tests for scripts/friction-log.sh - the always-on friction capture helper.

The capture helper is the "record" half of the grill-me cycle (issue #426). Its
contract:
- Append exactly one valid JSON object per invocation to the buffer (JSONL).
- Create the buffer's parent directory if missing.
- Honour CPP_FRICTION_LOG for the buffer path.
- Be fail-open: never exit non-zero, never write a junk record on bad input.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRICTION_LOG = ROOT / "scripts" / "friction-log.sh"

# Some tests drive a real `git` subprocess to build a worktree. The Woodpecker
# `validate` container (uv:python3.11-bookworm-slim) has no git, so guard those
# tests rather than error the whole suite on collection/run (cf. #451).
requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available (e.g. Woodpecker validate container)"
)


def _run(
    tmp_path: Path,
    *args: str,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CPP_FRICTION_LOG"] = str(log_path or (tmp_path / ".claude" / "friction.jsonl"))
    return subprocess.run(
        [str(FRICTION_LOG), *args],
        check=False,
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _read_lines(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_script_is_executable():
    assert FRICTION_LOG.exists()
    assert os.access(FRICTION_LOG, os.X_OK), "friction-log.sh must be executable"


def test_appends_valid_jsonl(tmp_path: Path):
    log = tmp_path / ".claude" / "friction.jsonl"
    result = _run(
        tmp_path,
        "--class",
        "permission-prompt",
        "--signal",
        "gh issue view 426 required approval",
        "--fix",
        "Bash(gh issue view:*)",
        "--scope",
        "local",
        "--run",
        "flow:auto #426",
        "--step",
        "1/9 Start",
        "--outcome",
        "approved",
        log_path=log,
    )
    assert result.returncode == 0, result.stderr
    records = _read_lines(log)
    assert len(records) == 1
    rec = records[0]
    assert rec["class"] == "permission-prompt"
    assert rec["signal"] == "gh issue view 426 required approval"
    assert rec["fix"] == "Bash(gh issue view:*)"
    assert rec["scope"] == "local"
    assert rec["run"] == "flow:auto #426"
    assert rec["step"] == "1/9 Start"
    assert rec["outcome"] == "approved"
    assert rec["ts"].endswith("Z")  # ISO-8601 UTC stamp


def test_creates_parent_directory(tmp_path: Path):
    log = tmp_path / "nested" / "deeper" / "friction.jsonl"
    result = _run(tmp_path, "--class", "other", "--signal", "hello", log_path=log)
    assert result.returncode == 0, result.stderr
    assert log.exists()
    assert len(_read_lines(log)) == 1


def test_scope_defaults_to_local(tmp_path: Path):
    log = tmp_path / "friction.jsonl"
    _run(tmp_path, "--class", "gate-failure", "--signal", "make test failed", log_path=log)
    assert _read_lines(log)[0]["scope"] == "local"


def test_risk_defaults_to_empty(tmp_path: Path):
    # The risk tier is optional: callers that do not set it (all pre-census
    # call sites) still produce a valid record with an empty risk field.
    log = tmp_path / "friction.jsonl"
    _run(tmp_path, "--class", "gate-failure", "--signal", "make test failed", log_path=log)
    assert _read_lines(log)[0]["risk"] == ""


def test_risk_tier_is_recorded(tmp_path: Path):
    # The permission-prompt census hook passes a risk tier so retro can
    # allowlist only the safe tiers.
    log = tmp_path / "friction.jsonl"
    _run(
        tmp_path,
        "--class",
        "permission-prompt",
        "--signal",
        "Bash: rm -rf build",
        "--risk",
        "DESTRUCTIVE",
        log_path=log,
    )
    assert _read_lines(log)[0]["risk"] == "DESTRUCTIVE"


def test_harness_defaults_to_empty(tmp_path: Path, monkeypatch):
    # #557: callers that do not set --harness (or $CPP_HARNESS) still produce a
    # valid record with an empty harness field (unattributed / pre-#557 shape).
    monkeypatch.delenv("CPP_HARNESS", raising=False)
    log = tmp_path / "friction.jsonl"
    _run(tmp_path, "--class", "gate-failure", "--signal", "make test failed", log_path=log)
    assert _read_lines(log)[0]["harness"] == ""


def test_harness_flag_is_recorded(tmp_path: Path):
    # A harness passes --harness so a mixed buffer can be split (#557).
    log = tmp_path / "friction.jsonl"
    _run(
        tmp_path,
        "--class", "gate-failure", "--signal", "codex gate flake",
        "--harness", "codex", log_path=log,
    )
    assert _read_lines(log)[0]["harness"] == "codex"


def test_harness_defaults_from_env(tmp_path: Path, monkeypatch):
    # $CPP_HARNESS tags every capture without repeating --harness (#557).
    monkeypatch.setenv("CPP_HARNESS", "codex")
    log = tmp_path / "friction.jsonl"
    _run(tmp_path, "--class", "other", "--signal", "x", log_path=log)
    assert _read_lines(log)[0]["harness"] == "codex"


def test_multiple_invocations_accumulate(tmp_path: Path):
    log = tmp_path / "friction.jsonl"
    _run(tmp_path, "--class", "other", "--signal", "one", log_path=log)
    _run(tmp_path, "--class", "other", "--signal", "two", log_path=log)
    _run(tmp_path, "--class", "other", "--signal", "three", log_path=log)
    records = _read_lines(log)
    assert [r["signal"] for r in records] == ["one", "two", "three"]


def test_fail_open_on_missing_required_args(tmp_path: Path):
    log = tmp_path / "friction.jsonl"
    # No --signal: must exit 0 (fail-open) and write nothing.
    result = _run(tmp_path, "--class", "permission-prompt", log_path=log)
    assert result.returncode == 0
    assert not log.exists() or _read_lines(log) == []


def test_fail_open_on_unknown_args_still_records(tmp_path: Path):
    log = tmp_path / "friction.jsonl"
    result = _run(
        tmp_path,
        "--bogus",
        "value",
        "--class",
        "other",
        "--signal",
        "still recorded",
        log_path=log,
    )
    assert result.returncode == 0
    assert _read_lines(log)[0]["signal"] == "still recorded"


def test_json_escaping_of_quotes_and_backslashes(tmp_path: Path):
    log = tmp_path / "friction.jsonl"
    tricky = 'said "hello" and used C:\\path\\to'
    result = _run(tmp_path, "--class", "other", "--signal", tricky, log_path=log)
    assert result.returncode == 0, result.stderr
    # The line must remain parseable JSON and round-trip the value exactly.
    rec = _read_lines(log)[0]
    assert rec["signal"] == tricky


def test_newline_in_field_folded_to_single_line(tmp_path: Path):
    log = tmp_path / "friction.jsonl"
    _run(tmp_path, "--class", "other", "--signal", "line1\nline2", log_path=log)
    raw = log.read_text().splitlines()
    assert len(raw) == 1  # folded to one JSONL line
    assert _read_lines(log)[0]["signal"] == "line1 line2"


def test_cpp_friction_log_env_override(tmp_path: Path):
    custom = tmp_path / "custom-buffer.jsonl"
    result = _run(tmp_path, "--class", "other", "--signal", "x", log_path=custom)
    assert result.returncode == 0
    assert custom.exists()
    default = tmp_path / ".claude" / "friction.jsonl"
    assert not default.exists()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        check=True,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run_no_env(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the helper with CPP_FRICTION_LOG unset, so default resolution kicks in."""
    env = os.environ.copy()
    env.pop("CPP_FRICTION_LOG", None)
    return subprocess.run(
        [str(FRICTION_LOG), *args],
        check=False,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


@requires_git
def test_default_targets_main_repo_from_worktree(tmp_path: Path):
    """Issue #471: a signal captured inside a linked worktree must land in the
    MAIN repo's buffer, so it survives the worktree being removed at cleanup."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "config", "user.email", "t@t.t")
    _git(main, "config", "user.name", "t")
    _git(main, "commit", "-q", "--allow-empty", "-m", "root")

    worktree = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(worktree), "-b", "feature")

    result = _run_no_env(worktree, "--class", "other", "--signal", "from-worktree")
    assert result.returncode == 0, result.stderr

    main_buffer = main / ".claude" / "friction.jsonl"
    worktree_buffer = worktree / ".claude" / "friction.jsonl"
    assert main_buffer.exists(), "signal must land in the durable main-repo buffer"
    assert _read_lines(main_buffer)[0]["signal"] == "from-worktree"
    assert not worktree_buffer.exists(), "signal must NOT land in the worktree buffer"


@requires_git
def test_default_targets_repo_root_from_subdir(tmp_path: Path):
    """From a subdirectory of the main repo, the default resolves to the repo
    root's .claude/friction.jsonl (not a cwd-relative buffer in the subdir)."""
    main = tmp_path / "main"
    (main / "src" / "deep").mkdir(parents=True)
    _git(main, "init", "-q")

    result = _run_no_env(main / "src" / "deep", "--class", "other", "--signal", "deep")
    assert result.returncode == 0, result.stderr

    root_buffer = main / ".claude" / "friction.jsonl"
    subdir_buffer = main / "src" / "deep" / ".claude" / "friction.jsonl"
    assert root_buffer.exists()
    assert _read_lines(root_buffer)[0]["signal"] == "deep"
    assert not subdir_buffer.exists()


def test_default_falls_back_to_cwd_outside_git(tmp_path: Path):
    """Fail-open: with no git repo around, the default is still the cwd-relative
    buffer (git resolution is best-effort, never a hard dependency)."""
    plain = tmp_path / "plain"
    plain.mkdir()
    result = _run_no_env(plain, "--class", "other", "--signal", "no-git")
    assert result.returncode == 0, result.stderr
    assert (plain / ".claude" / "friction.jsonl").exists()
