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
- Address bootstrap is honest (#672): a failed self-derivation names its cause
  (``no-sock-dir`` vs ``no-match``), reports ``FLOW_WAVE_BOOTSTRAP=deadlock``
  instead of promising a ``verify`` that cannot fire, re-derives on a retry
  (the socket dir is created lazily), and never downgrades a recorded address
  to ``unknown``.
- ``list`` warns on lane overlap only for the useful signal (same repo + same
  issue, same branch, same/nested worktrees) - gate condition 2: same repo
  alone is the normal wave shape and must NOT warn.
- Waves are namespaced: the same role in two waves never conflicts.
- Loud default (issue #671): ``register``/``get``/``verify`` into wave
  ``default`` without an explicit ``--wave`` print one advisory stderr line
  (register also names the likely intended wave when exactly one other wave
  has a live orchestrator), and ``list`` appends a note for LIVE entries
  parked in OTHER waves. Advisory only - verdicts and exit codes unchanged.

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


def _json_payload(proc: subprocess.CompletedProcess[str]) -> dict:
    """The JSON body of a ``list --json`` run, minus the trailing contract lines.

    Split on the ``FLOW_WAVE`` prefix rather than a fixed offset so adding a
    detail line to the contract cannot silently break the parse.
    """
    body: list[str] = []
    for line in proc.stdout.splitlines():
        if line.startswith("FLOW_WAVE"):
            break
        body.append(line)
    return json.loads("\n".join(body))


def _sock_dir(tmp: Path) -> Path:
    """The socket dir ``_run`` points the helper at (absent until created)."""
    return tmp / "socks"


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
        assert _json_payload(p)["1"]["liveness"] == "live"


@requires_tools
class TestAddressBootstrap:
    """Address bootstrap honesty (issue #672).

    The 2026-08-11 wave deadlocked with every session recording ``unknown``:
    the socket dir did not exist, so self-derivation could not succeed, and the
    helper nonetheless reported that the orchestrator's ``verify`` would supply
    the address later. It could not - ``verify`` needs an observed ``from=``,
    which needs a delivered message, which needs an address somebody already
    holds. These tests pin the three properties that close it: the failure
    NAMES its cause, an address recorded before the (lazily created) socket dir
    appears is re-derived on a retry, and a failed derivation never downgrades
    an address the roster already has.
    """

    def test_missing_sock_dir_is_named_not_flattened(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "register", "1")
        assert _detail(p, "FLOW_WAVE_SOCKET") == "unknown"
        assert _detail(p, "FLOW_WAVE_SOCKET_SOURCE") == "unknown"
        assert _detail(p, "FLOW_WAVE_SOCKET_REASON") == "no-sock-dir"
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "deadlock"

    def test_present_dir_without_match_is_a_distinct_reason(self, tmp_path: Path) -> None:
        _sock_dir(tmp_path).mkdir(parents=True)
        p = _run(tmp_path, "register", "1")
        assert _detail(p, "FLOW_WAVE_SOCKET") == "unknown"
        assert _detail(p, "FLOW_WAVE_SOCKET_REASON") == "no-match"

    def test_unaddressed_register_never_promises_verify(self, tmp_path: Path) -> None:
        """The exact dishonesty #672 was filed about: a promise that cannot fire."""
        p = _run(tmp_path, "register", "1")
        assert "cannot fire" in p.stderr
        # ...and it points at lanes that do NOT depend on self-derivation.
        assert "--socket" in p.stderr
        assert "user-relayed hello" in p.stderr

    def test_explicit_socket_is_the_manual_bootstrap_lane(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/relayed.sock")
        assert _detail(p, "FLOW_WAVE_SOCKET_SOURCE") == "explicit"
        assert _detail(p, "FLOW_WAVE_SOCKET_REASON") == "-"
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "ok"

    def test_reregister_adopts_a_socket_that_appeared_later(self, tmp_path: Path) -> None:
        """The socket dir is created LAZILY - 'unknown' is point-in-time, not final.

        Live evidence (2026-08-11): role A recorded ``unknown`` at 07:52 and
        role B self-derived a real socket at 10:27 on the same host.
        """
        first = _run(tmp_path, "register", "1")
        assert _detail(first, "FLOW_WAVE_SOCKET") == "unknown"

        socks = _sock_dir(tmp_path)
        socks.mkdir(parents=True)
        (socks / f"{SELF_PID}.sock").touch()

        second = _run(tmp_path, "register", "1")
        assert _detail(second, "FLOW_WAVE_SOCKET") == f"uds:{socks}/{SELF_PID}.sock"
        assert _detail(second, "FLOW_WAVE_SOCKET_SOURCE") == "self"
        assert _detail(second, "FLOW_WAVE_BOOTSTRAP") == "ok"
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["socket"].endswith(
            f"{SELF_PID}.sock"
        )

    def test_failed_derivation_never_downgrades_a_recorded_address(
        self, tmp_path: Path
    ) -> None:
        """The trust model's reverse direction: 'unknown' never wins (#638/#672).

        register.md recommends re-registering as the cheap re-brief, so a
        derivation that fails afterwards must not destroy the address the wave
        is actually running on.
        """
        socks = _sock_dir(tmp_path)
        socks.mkdir(parents=True)
        (socks / f"{SELF_PID}.sock").touch()
        _run(tmp_path, "register", "1")

        shutil.rmtree(socks)  # transport disappears under a live wave
        p = _run(tmp_path, "register", "1")

        assert _detail(p, "FLOW_WAVE_SOCKET") == f"uds:{socks}/{SELF_PID}.sock"
        assert _detail(p, "FLOW_WAVE_SOCKET_SOURCE") == "preserved"
        assert _detail(p, "FLOW_WAVE_SOCKET_REASON") == "no-sock-dir"
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "ok"
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["socket"].endswith(f"{SELF_PID}.sock")
        # The failed assertion is still recorded honestly as such.
        assert entry["self_socket"] == "unknown"

    def test_explicit_socket_overrides_a_recorded_address(self, tmp_path: Path) -> None:
        """Preservation is a floor against 'unknown', not a lock - operator wins."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/old.sock")
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/new.sock")
        assert _detail(p, "FLOW_WAVE_SOCKET") == "uds:/tmp/new.sock"
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["socket"] == "uds:/tmp/new.sock"

    def test_get_on_an_unaddressed_role_reports_deadlock(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1")
        p = _run(tmp_path, "get", "1")
        assert _verdict(p) == "listed"
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "deadlock"
        assert "NO address" in p.stderr

    def test_get_on_an_addressed_role_reports_ok(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock")
        p = _run(tmp_path, "get", "1")
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "ok"
        assert "NO address" not in p.stderr

    def test_list_flags_live_roles_with_no_address(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1")  # unaddressed
        p = _run(tmp_path, "list", live=SELF_PID)
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "deadlock"
        assert "1 LIVE role(s) have no address" in p.stdout
        assert "blocked, not pending" in p.stdout

    def test_list_is_ok_when_every_live_role_is_addressed(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock")
        p = _run(tmp_path, "list", live=SELF_PID)
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "ok"
        assert "have no address" not in p.stdout

    def test_stale_unaddressed_entries_are_not_a_live_deadlock(self, tmp_path: Path) -> None:
        """Only LIVE roles can deadlock a wave; a dead one is just history."""
        _run(tmp_path, "register", "1")  # unaddressed, and not in the live set
        p = _run(tmp_path, "list")
        assert _detail(p, "FLOW_WAVE_BOOTSTRAP") == "ok"

    def test_self_address_names_why_it_failed(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "self-address")
        assert p.stdout.strip() == "unknown"
        assert "no socket dir" in p.stderr
        assert "lazily" in p.stderr

    def test_self_address_walk_starts_at_the_session_pid(self, tmp_path: Path) -> None:
        """CLAUDE_PID is the session's own pid; $PPID alone starts a hop too low."""
        socks = _sock_dir(tmp_path)
        socks.mkdir(parents=True)
        (socks / f"{SELF_PID}.sock").touch()
        p = _run(tmp_path, "self-address")
        assert p.stdout.strip() == f"uds:{socks}/{SELF_PID}.sock"


@requires_tools
class TestImplicitDefaultAdvisory:
    """Loud default + cross-wave visibility (issue #671).

    A worker that omits ``--wave`` lands in wave 'default' with a clean
    verdict while the orchestrator's named-wave roster stays empty - both
    sides read success. Every assertion here is advisory-only: verdicts and
    exit codes must be exactly what they were before #671.
    """

    WARN = "no --wave given"

    def test_register_without_wave_warns_but_registers(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "register", "A", "--socket", "uds:/tmp/a.sock")
        assert p.returncode == 0
        assert _verdict(p) == "registered"
        assert self.WARN in p.stderr
        assert "wave 'default'" in p.stderr

    def test_explicit_wave_default_is_silent(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "register", "A", "--wave", "default", "--socket", "uds:/tmp/a.sock")
        assert p.returncode == 0
        assert self.WARN not in p.stderr

    def test_named_wave_is_silent(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "register", "A", "--wave", "cpp", "--socket", "uds:/tmp/a.sock")
        assert p.returncode == 0
        assert self.WARN not in p.stderr

    def test_get_and_verify_without_wave_warn(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "A", "--socket", "uds:/tmp/a.sock")
        g = _run(tmp_path, "get", "A")
        assert g.returncode == 0
        assert self.WARN in g.stderr
        v = _run(tmp_path, "verify", "A", "--from", "uds:/tmp/a.sock")
        assert v.returncode == 0
        assert _verdict(v) == "verified"
        assert self.WARN in v.stderr

    def test_suggestion_names_the_one_live_orchestrator_wave(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "orchestrator",
            "--wave",
            "cpp-install",
            "--socket",
            "uds:/tmp/o.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(tmp_path, "register", "A", "--socket", "uds:/tmp/a.sock", live=OTHER_PID)
        assert p.returncode == 0
        assert "Did you mean --wave 'cpp-install'?" in p.stderr

    def test_no_suggestion_when_ambiguous_or_stale(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "orchestrator",
            "--wave",
            "wave-one",
            "--socket",
            "uds:/tmp/o1.sock",
            pid="7777",
            session="s-one",
        )
        _run(
            tmp_path,
            "register",
            "orchestrator",
            "--wave",
            "wave-two",
            "--socket",
            "uds:/tmp/o2.sock",
            pid="8888",
            session="s-two",
        )
        # Two live orchestrators: ambiguous, no suggestion (warning still fires).
        both = _run(tmp_path, "register", "A", "--socket", "uds:/tmp/a.sock", live="7777:8888")
        assert self.WARN in both.stderr
        assert "Did you mean" not in both.stderr
        # Neither live: stale orchestrators suggest nothing.
        stale = _run(tmp_path, "register", "B", "--socket", "uds:/tmp/b.sock")
        assert "Did you mean" not in stale.stderr

    def test_list_notes_live_entry_stranded_in_default(self, tmp_path: Path) -> None:
        """The observed 2026-08-11 failure: roster of one, worker invisible."""
        _run(
            tmp_path,
            "register",
            "orchestrator",
            "--wave",
            "cpp-install",
            "--socket",
            "uds:/tmp/o.sock",
        )
        _run(
            tmp_path,
            "register",
            "A",
            "--socket",
            "uds:/tmp/a.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(tmp_path, "list", "--wave", "cpp-install", live=f"{SELF_PID}:{OTHER_PID}")
        assert "note:" in p.stdout
        assert "wave 'default'" in p.stdout
        assert f"role A pid {OTHER_PID}" in p.stdout
        assert "omitted --wave?" in p.stdout

    def test_list_note_skips_stale_other_wave_entries(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "orchestrator",
            "--wave",
            "cpp-install",
            "--socket",
            "uds:/tmp/o.sock",
        )
        _run(
            tmp_path,
            "register",
            "A",
            "--socket",
            "uds:/tmp/a.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        # Only the orchestrator is live: the dead default-wave worker is not noted.
        p = _run(tmp_path, "list", "--wave", "cpp-install", live=SELF_PID)
        assert "note:" not in p.stdout

    def test_list_note_appears_on_empty_roster_too(self, tmp_path: Path) -> None:
        _run(
            tmp_path,
            "register",
            "A",
            "--socket",
            "uds:/tmp/a.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(tmp_path, "list", "--wave", "cpp-install", live=OTHER_PID)
        assert "no roles registered" in p.stdout
        assert "note:" in p.stdout

    def test_list_json_stdout_stays_parseable_note_on_stderr(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "orchestrator", "--wave", "cpp-install", "--socket", "uds:/tmp/o.sock")
        _run(
            tmp_path,
            "register",
            "A",
            "--socket",
            "uds:/tmp/a.sock",
            pid=OTHER_PID,
            session=OTHER_SESSION,
        )
        p = _run(tmp_path, "list", "--wave", "cpp-install", "--json", live=f"{SELF_PID}:{OTHER_PID}")
        assert "orchestrator" in _json_payload(p)
        assert "note:" not in p.stdout
        assert "note:" in p.stderr


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
