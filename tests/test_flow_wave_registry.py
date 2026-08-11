"""Tests for the wave role registry (issue #638).

Covers ``scripts/flow-wave-registry.sh``, the role -> address roster behind
``/flow:register``.

Contract:
- ``register`` records role, socket, and lane detail; re-registering from the
  owning session is an idempotent refresh (``updated``).
- A role held by a LIVE other session is ``refused`` (exit 1); ``--force`` is
  the deliberate override; a dead owner's entry is stale and taken over
  automatically, so the roster can never wedge a wave.
- ``verify`` reconciles the recorded address against the transport-observed
  ``from=``. Gate condition 1 (#638): on mismatch the OBSERVED address becomes
  canonical and the entry is flagged - never the reverse.
- ``list`` warns on lane overlap only for the useful signal (same repo + same
  issue, same branch, same/nested worktrees) - gate condition 2: same repo
  alone is the normal wave shape and must NOT warn.
- Waves are namespaced: the same role in two waves never conflicts.

Liveness is pinned with the ``FLOW_WAVE_LIVE_PIDS`` hook rather than real
processes, so no test depends on a pid that happens to exist.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "scripts" / "flow-wave-registry.sh"

# Drives real `bash` + `jq` subprocesses; the CI validate container may ship
# neither, so skip there (same shape as the other flow helper suites).
requires_tools = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="requires bash and jq on PATH",
)

HOST = "testhost"
SELF_PID = "4242"
SELF_SESSION = "session-self"
OTHER_PID = "9999"
OTHER_SESSION = "session-other"


def _run(
    tmp: Path,
    *args: str,
    pid: str = SELF_PID,
    session: str = SELF_SESSION,
    live: str = "",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_PID": pid,
            "CLAUDE_CODE_SESSION_ID": session,
            "FLOW_WAVE_REGISTRY_DIR": str(tmp / "reg"),
            "FLOW_WAVE_SOCK_DIR": str(tmp / "socks"),
            "FLOW_WAVE_HOST": HOST,
            "FLOW_WAVE_LIVE_PIDS": live,
            "FLOW_WAVE_NOW": "1700000000",
        }
    )
    return subprocess.run(
        ["bash", str(REGISTRY), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    for line in proc.stdout.splitlines():
        if line.startswith("FLOW_WAVE: "):
            return line.removeprefix("FLOW_WAVE: ")
    return ""


def _detail(proc: subprocess.CompletedProcess[str], key: str) -> str:
    for line in proc.stdout.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return ""


def _registry_json(tmp: Path) -> dict:
    return json.loads((tmp / "reg" / "registry.json").read_text())


@requires_tools
class TestRegister:
    def test_register_records_entry(self, tmp_path: Path) -> None:
        p = _run(
            tmp_path,
            "register",
            "1",
            "--wave",
            "cpp",
            "--socket",
            "uds:/tmp/x.sock",
            "--repo",
            "/repos/a",
            "--issue",
            "42",
            "--branch",
            "issue-42-x",
            "--cwd",
            "/wt/a",
        )
        assert p.returncode == 0
        assert _verdict(p) == "registered"
        entry = _registry_json(tmp_path)["cpp"]["roles"]["1"]
        assert entry["socket"] == "uds:/tmp/x.sock"
        assert entry["issue"] == "42"
        assert entry["verified"] is False
        assert entry["address_mismatch"] is False

    def test_reregister_same_session_is_idempotent_refresh(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock", "--issue", "42")
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock", "--issue", "43")
        assert p.returncode == 0
        assert _verdict(p) == "updated"
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["issue"] == "43"

    def test_live_foreign_owner_refuses(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "1",
            "--socket",
            "uds:/tmp/other.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/self.sock", live=OTHER_PID)
        assert p.returncode == 1
        assert _verdict(p) == "refused"
        # The registry still holds the live owner.
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["session"] == OTHER_SESSION

    def test_force_takes_over_live_owner(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "1",
            "--socket",
            "uds:/tmp/other.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(
            tmp_path,
            "register",
            "1",
            "--socket",
            "uds:/tmp/self.sock",
            "--force",
            live=OTHER_PID,
        )
        assert p.returncode == 0
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["session"] == SELF_SESSION

    def test_stale_owner_taken_over_without_force(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "1",
            "--socket",
            "uds:/tmp/other.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        # OTHER_PID is not in the live set -> stale -> silent takeover.
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/self.sock")
        assert p.returncode == 0
        assert _verdict(p) == "registered"
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["session"] == SELF_SESSION

    def test_wave_namespacing_isolates_roles(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "1",
            "--wave",
            "poker",
            "--socket",
            "uds:/tmp/other.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(
            tmp_path,
            "register",
            "1",
            "--wave",
            "cpp",
            "--socket",
            "uds:/tmp/self.sock",
            live=OTHER_PID,
        )
        assert p.returncode == 0
        assert _verdict(p) == "registered"

    def test_unknown_socket_fallback_still_registers(self, tmp_path: Path) -> None:
        env_pid_one = _run(tmp_path, "register", "1")  # no --socket, no sock files
        assert env_pid_one.returncode == 0
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["socket"] == "unknown"


@requires_tools
class TestVerify:
    def test_match_marks_verified(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock")
        p = _run(tmp_path, "verify", "1", "--from", "uds:/tmp/x.sock")
        assert _verdict(p) == "verified"
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["verified"] is True
        assert entry["address_mismatch"] is False

    def test_mismatch_observed_address_becomes_canonical(self, tmp_path: Path) -> None:
        """Gate condition 1 (#638): the transport-observed from= wins.

        On mismatch the OBSERVED address replaces the self-derived one as
        canonical and the entry is flagged - never "flagged but self-derived
        kept", and never the reverse.
        """
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/self-derived.sock")
        p = _run(tmp_path, "verify", "1", "--from", "uds:/tmp/observed.sock")
        assert p.returncode == 0
        assert _verdict(p) == "mismatch-corrected"
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["socket"] == "uds:/tmp/observed.sock"
        assert entry["self_socket"] == "uds:/tmp/self-derived.sock"
        assert entry["address_mismatch"] is True
        assert entry["verified"] is True
        # And `get` serves the observed address from here on.
        g = _run(tmp_path, "get", "1")
        assert _detail(g, "FLOW_WAVE_SOCKET") == "uds:/tmp/observed.sock"
        assert _detail(g, "FLOW_WAVE_MISMATCH") == "true"

    def test_verify_unknown_role_reports_unknown(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "verify", "ghost", "--from", "uds:/tmp/x.sock")
        assert p.returncode == 0
        assert _verdict(p) == "unknown"


@requires_tools
class TestRelease:
    def test_release_marks_released(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock")
        p = _run(tmp_path, "release", "1")
        assert _verdict(p) == "released"
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["released"] is True

    def test_release_foreign_live_role_refuses_without_force(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "1",
            "--socket",
            "uds:/tmp/other.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(tmp_path, "release", "1", live=OTHER_PID)
        assert p.returncode == 1
        assert _verdict(p) == "refused"
        forced = _run(tmp_path, "release", "1", "--force", live=OTHER_PID)
        assert forced.returncode == 0
        assert _verdict(forced) == "released"


@requires_tools
class TestListOverlap:
    def _register_pair(self, tmp: Path, a: dict, b: dict) -> None:
        _run(
            tmp,
            "register",
            "A",
            "--socket",
            "uds:/tmp/a.sock",
            *a.get("extra", []),
            pid="1111",
            session="session-a",
        )
        _run(
            tmp,
            "register",
            "B",
            "--socket",
            "uds:/tmp/b.sock",
            *b.get("extra", []),
            pid="2222",
            session="session-b",
        )

    def test_same_repo_alone_is_info_not_warning(self, tmp_path: Path) -> None:
        """Gate condition 2 (#638): sharing a repo is the normal wave shape."""
        self._register_pair(
            tmp_path,
            {"extra": ["--repo", "/repos/a", "--cwd", "/wt/one", "--issue", "1"]},
            {"extra": ["--repo", "/repos/a", "--cwd", "/wt/two", "--issue", "2"]},
        )
        p = _run(tmp_path, "list", live="1111:2222")
        assert "WARNING" not in p.stdout
        assert "info:" in p.stdout

    def test_same_repo_same_issue_warns(self, tmp_path: Path) -> None:
        self._register_pair(
            tmp_path,
            {"extra": ["--repo", "/repos/a", "--cwd", "/wt/one", "--issue", "7"]},
            {"extra": ["--repo", "/repos/a", "--cwd", "/wt/two", "--issue", "7"]},
        )
        p = _run(tmp_path, "list", live="1111:2222")
        assert "WARNING" in p.stdout
        assert "issue #7" in p.stdout

    def test_same_branch_warns(self, tmp_path: Path) -> None:
        self._register_pair(
            tmp_path,
            {"extra": ["--branch", "issue-9-x", "--cwd", "/wt/one"]},
            {"extra": ["--branch", "issue-9-x", "--cwd", "/wt/two"]},
        )
        p = _run(tmp_path, "list", live="1111:2222")
        assert "WARNING" in p.stdout
        assert "issue-9-x" in p.stdout

    def test_nested_worktrees_warn(self, tmp_path: Path) -> None:
        self._register_pair(
            tmp_path,
            {"extra": ["--cwd", "/wt/one"]},
            {"extra": ["--cwd", "/wt/one/nested"]},
        )
        p = _run(tmp_path, "list", live="1111:2222")
        assert "WARNING" in p.stdout

    def test_stale_entries_excluded_from_overlap_and_marked(self, tmp_path: Path) -> None:
        self._register_pair(
            tmp_path,
            {"extra": ["--repo", "/repos/a", "--issue", "7"]},
            {"extra": ["--repo", "/repos/a", "--issue", "7"]},
        )
        # Only A live: the pairwise overlap must not fire, B reads stale.
        p = _run(tmp_path, "list", live="1111")
        assert "WARNING" not in p.stdout
        assert "[stale" in p.stdout

    def test_list_json_carries_liveness(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock")
        p = _run(tmp_path, "list", "--json", live=SELF_PID)
        payload = json.loads(p.stdout.rsplit("FLOW_WAVE:", 1)[0])
        assert payload["1"]["liveness"] == "live"


class TestWiring:
    """Read-only wiring assertions - no subprocesses needed."""

    def test_helper_is_in_installed_family(self) -> None:
        installer = (ROOT / "scripts" / "flow-helpers-install.sh").read_text()
        assert "flow-wave-registry.sh" in installer

    def test_helper_is_bundled_with_codex_skill(self) -> None:
        bundled = ROOT / "codex" / "skills" / "flow-wave" / "scripts" / "flow-wave-registry.sh"
        assert bundled.read_text() == (ROOT / "scripts" / "flow-wave-registry.sh").read_text()

    def test_helper_is_allowlisted_in_permissions_template(self) -> None:
        template = (ROOT / "templates" / "claude-settings-permissions.json").read_text()
        assert "Bash(~/.claude/scripts/flow-wave-registry.sh:*)" in template
