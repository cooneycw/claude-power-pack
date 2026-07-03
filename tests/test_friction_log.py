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
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRICTION_LOG = ROOT / "scripts" / "friction-log.sh"


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
