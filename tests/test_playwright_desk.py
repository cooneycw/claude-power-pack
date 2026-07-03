"""Tests for scripts/playwright-desk.py - the lease-desk ledger (issue #421).

The script is a hyphenated CLI helper (not an importable module), so these tests
drive its real ``--json`` contract via subprocess, the same way
``tests/test_drift_detect.py`` exercises its script.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "playwright-desk.py"


def run(
    *args: str,
    root: Path,
    pool_config: Path | None = None,
    expect: int = 0,
) -> dict[str, Any]:
    """Invoke the helper with --json and return the parsed object."""
    cmd = [sys.executable, str(SCRIPT), "--root", str(root), "--json"]
    if pool_config is not None:
        cmd += ["--pool-config", str(pool_config)]
    cmd += list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == expect, (
        f"exit {proc.returncode} != {expect}\ncmd={cmd}\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return json.loads(proc.stdout)


def write_pool(path: Path, desks: list[str], idle: int = 1800) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "desks": desks, "idle_timeout_seconds": idle}),
        encoding="utf-8",
    )


def test_default_pool_when_no_config(tmp_path: Path) -> None:
    res = run("pool", root=tmp_path)
    assert res["ok"] is True
    assert res["desks"] == ["playwright-desk-1", "playwright-desk-2", "playwright-desk-3"]
    assert res["pool_config_exists"] is False
    assert res["idle_timeout_seconds"] == 1800


def test_create_leases_a_free_desk(tmp_path: Path) -> None:
    res = run("create", "gmail", root=tmp_path)
    assert res["ok"] is True
    assert res["session"] == "gmail"
    assert res["desk"] == "playwright-desk-1"
    assert res["mcp_prefix"] == "mcp__playwright-desk-1__"
    assert res["restore"] is False  # fresh session, nothing to restore
    assert res["free_desks_remaining"] == 2
    # Ledger persisted.
    ledger = json.loads((tmp_path / ".claude" / "playwright-sessions.json").read_text())
    assert ledger["sessions"]["gmail"]["status"] == "active"


def test_create_duplicate_name_is_usage_error(tmp_path: Path) -> None:
    run("create", "gmail", root=tmp_path)
    res = run("create", "gmail", root=tmp_path, expect=2)
    assert res["ok"] is False
    assert res["error"] == "session_exists"


def test_distinct_sessions_get_distinct_desks(tmp_path: Path) -> None:
    a = run("create", "a", root=tmp_path)
    b = run("create", "b", root=tmp_path)
    assert a["desk"] != b["desk"]
    assert {a["desk"], b["desk"]} == {"playwright-desk-1", "playwright-desk-2"}


def test_pool_exhaustion_returns_no_desk(tmp_path: Path) -> None:
    pool = tmp_path / ".claude" / "playwright-pool.json"
    write_pool(pool, ["only-desk"])
    run("create", "first", root=tmp_path, pool_config=pool)
    res = run("create", "second", root=tmp_path, pool_config=pool, expect=3)
    assert res["ok"] is False
    assert res["error"] == "no_free_desk"


def test_close_frees_desk_but_keeps_session(tmp_path: Path) -> None:
    pool = tmp_path / ".claude" / "playwright-pool.json"
    write_pool(pool, ["only-desk"])
    run("create", "s1", root=tmp_path, pool_config=pool)
    closed = run("close", "s1", root=tmp_path, pool_config=pool)
    assert closed["freed_desk"] == "only-desk"
    assert closed["discarded"] is False
    # Desk is now free again for a different named session.
    reused = run("create", "s2", root=tmp_path, pool_config=pool)
    assert reused["desk"] == "only-desk"
    # s1 still exists, now detached.
    listing = run("list", root=tmp_path, pool_config=pool)
    names = {row["session"]: row for row in listing["sessions"]}
    assert names["s1"]["status"] == "detached"
    assert names["s1"]["desk"] is None


def test_resume_restores_when_state_file_exists(tmp_path: Path) -> None:
    create = run("create", "login", root=tmp_path)
    run("close", "login", root=tmp_path)
    # Simulate the model having saved storage state to the reported path.
    state_file = tmp_path / create["state_file"]
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"cookies": []}), encoding="utf-8")

    resumed = run("resume", "login", root=tmp_path)
    assert resumed["status"] == "active"
    assert resumed["restore"] is True
    assert resumed["state_exists"] is True


def test_resume_unknown_session_is_usage_error(tmp_path: Path) -> None:
    res = run("resume", "ghost", root=tmp_path, expect=2)
    assert res["error"] == "unknown_session"


def test_resume_without_state_does_not_ask_to_restore(tmp_path: Path) -> None:
    run("create", "fresh", root=tmp_path)
    run("close", "fresh", root=tmp_path)
    resumed = run("resume", "fresh", root=tmp_path)
    assert resumed["restore"] is False


def test_save_requires_seated_session(tmp_path: Path) -> None:
    run("create", "s", root=tmp_path)
    run("close", "s", root=tmp_path)
    res = run("save", "s", root=tmp_path, expect=2)
    assert res["error"] == "not_seated"


def test_close_discard_removes_session_and_state(tmp_path: Path) -> None:
    create = run("create", "temp", root=tmp_path)
    state_file = tmp_path / create["state_file"]
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{}", encoding="utf-8")

    res = run("close", "temp", "--discard", root=tmp_path)
    assert res["discarded"] is True
    assert res["state_removed"] is True
    assert not state_file.exists()
    listing = run("list", root=tmp_path)
    assert listing["sessions"] == []


def test_cleanup_releases_idle_sessions(tmp_path: Path) -> None:
    run("create", "old", root=tmp_path)
    # idle-seconds=0 forces every active session past the threshold immediately.
    res = run("cleanup", "--idle-seconds", "0", root=tmp_path)
    assert len(res["released"]) == 1
    assert res["released"][0]["session"] == "old"
    listing = run("list", root=tmp_path)
    assert listing["sessions"][0]["status"] == "detached"


def test_cleanup_keeps_fresh_sessions(tmp_path: Path) -> None:
    run("create", "busy", root=tmp_path)
    res = run("cleanup", "--idle-seconds", "3600", root=tmp_path)
    assert res["released"] == []


def test_resume_is_idempotent_when_already_seated(tmp_path: Path) -> None:
    first = run("create", "x", root=tmp_path)
    again = run("resume", "x", root=tmp_path)
    assert again["desk"] == first["desk"]
    assert again["status"] == "active"
