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
- ``verify`` distinguishes the benign fill from the contradiction (#674):
  ``unknown`` -> observed is ``address_filled`` (no warning, ``address_mismatch``
  stays false, ``list`` renders ``filled``), while a real recorded address
  contradicted by the observed one stays ``mismatch-corrected`` and loud. Both
  keep the observed address canonical and both exit 0 - a new verdict must never
  become a new exit code, or a ``set -euo pipefail`` caller aborts mid-script.
- Address bootstrap is honest (#672): a failed self-derivation names its cause
  (``no-sock-dir`` vs ``no-match``), reports ``FLOW_WAVE_BOOTSTRAP=deadlock``
  instead of promising a ``verify`` that cannot fire, re-derives on a retry
  (the socket dir is created lazily), and never downgrades a recorded address
  to ``unknown``.
- ``list`` warns on lane overlap only for the useful signal (same repo + same
  issue, same branch, same/nested worktrees) - gate condition 2: same repo
  alone is the normal wave shape and must NOT warn.
- Lane-less live roles are exempt from the overlap checks (#683) - the
  ``orchestrator`` and any role with no issue claimed - and the exemption is
  ANNOUNCED, never silent; ``register`` advises when ``--cwd`` looks like a
  shared parent rather than a lane.
- A leftover socket file never resurrects a dead pid (#869). ``kill -0`` has two
  failure modes behind one return code - ESRCH (gone) and EPERM (exists, not
  ours) - and the registry now separates them, so the case #675 introduced the
  socket fallback for (a pid the helper cannot signal) is answered by positive
  evidence instead. ``liveness_of`` returns a third state, ``unknown``, for a
  host whose process table cannot be enumerated at all; the socket file survives
  only in ``FLOW_WAVE_LIVENESS_BASIS``, where it corroborates and decides
  nothing. Supersedes the uds-only fallback of #689, whose one-factor asymmetry
  on non-uds transports is gone rather than documented.
- ``verified``/``address_filled``/``address_mismatch`` share ONE lifecycle
  (#691/#692): preserved together across a same-owner re-register at a
  byte-identical address, cleared together on a takeover or an address change.
- Wave POLICY is declared state in two tiers (#699): wave-level fields set once
  by the orchestrator (``policy set``, a MERGE that bumps ``rev``) and inherited
  by every role, plus role-level facts (``--model``, ``--permission-mode``,
  ``--files``, ``--capacity``) each session declares for itself. Only
  ``--authority`` and ``--authority-model`` are enum-validated; the rest are
  free text. ``policy_absent`` is a STATE and exits 0.
- A declared policy nobody reads is decoration, so four readers are pinned:
  ``register`` reprints it (the compaction-proof re-brief), an undeclared policy
  is reported as ``absent`` rather than passing silently, a role briefed on a
  superseded rev reads ``brief=stale``, and declared FILE LANES participate in
  overlap detection like branches do.
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
import time
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

# The #687 claim-reconciliation suite also drives real `git worktree` locks, so
# it carries the stricter guard (CPP core directive: the CI validate container
# ships none of these binaries).
requires_git_tools = pytest.mark.skipif(
    shutil.which("bash") is None
    or shutil.which("jq") is None
    or shutil.which("git") is None,
    reason="requires bash, jq and git on PATH",
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
    live: str | None = None,
    unknown: str = "",
    starttimes: str | None = None,
    now: str = "1700000000",
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    # `live` (issue #1094): most existing callers never passed it at
    # `register` time - only on a LATER `get`/`list` call meant to pin
    # liveness for the CHECK. Before pid_started existed that was harmless;
    # now `register` also captures a start-time witness for whichever pid it
    # is told is "self", and a witness captured with no live-pid hook active
    # falls through to a real /proc lookup that a synthetic test pid (never
    # SELF_PID/OTHER_PID's real process) cannot satisfy - recorded as blank,
    # which then reads `unknown` forever regardless of what a later call
    # pins. Defaulting `live` to the registering `pid` ITSELF, but ONLY for
    # `register` and only when a test did not explicitly ask for something
    # else, matches what every one of these tests already assumed ("the
    # session registering itself is presently alive") without having to
    # touch each call site individually.
    if live is None:
        live = pid if (args and args[0] == "register") else ""
    # `starttimes` (issue #1094): derived deterministically from `live` so
    # any two `_run` calls that agree on which pids are alive also agree on
    # those pids' witnesses, without needing literal shared state between
    # separate subprocess invocations - each pid gets a FIXED, pid-derived
    # value. A test exercising the recycling/absence behaviour on purpose
    # passes `starttimes` explicitly, which overrides this default entirely.
    if starttimes is None:
        starttimes = ":".join(
            f"{p}=witness-{p}" for p in live.split(":") if p
        )
    env = os.environ.copy()
    env.update(
        {
            "CLAUDE_PID": pid,
            "CLAUDE_CODE_SESSION_ID": session,
            "FLOW_WAVE_REGISTRY_DIR": str(tmp / "reg"),
            "FLOW_WAVE_SOCK_DIR": str(tmp / "socks"),
            "FLOW_WAVE_HOST": HOST,
            "FLOW_WAVE_LIVE_PIDS": live,
            "FLOW_WAVE_UNKNOWN_PIDS": unknown,
            "FLOW_WAVE_PID_STARTTIMES": starttimes,
            "FLOW_WAVE_NOW": now,
        }
    )
    # #1026: the merge-strict shelf life is configurable, so a test has to be
    # able to set FLOW_WAVE_MERGE_STRICT_TTL - including to a MALFORMED value,
    # which is the case that proved the guard could fail open.
    if extra_env:
        env.update(extra_env)
    # `cwd` defaults to None (inherit pytest's own cwd, as before every #891
    # call site below started passing it) so every existing call is unaffected.
    # #891 needs it to prove the registry answers the SAME way regardless of
    # which directory a caller happens to run `list`/`register` from.
    return subprocess.run(
        ["bash", str(REGISTRY), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
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
class TestAddressFilledVsMismatch:
    """The benign fill is not the pathological contradiction (issue #674).

    Both outcomes make the observed address canonical, so what separates them is
    what they SAY about the entry. Filling an absent address is the documented
    bootstrap fallback succeeding; a recorded real address contradicted by the
    transport is a possible misrouting or stale pid reuse. Before the split both
    emitted ``mismatch-corrected`` with the flag set, so on a host with no socket
    dir the flag fired on 100% of the fleet and carried no signal at all.
    """

    def test_unknown_recorded_is_filled_and_not_flagged(self, tmp_path: Path) -> None:
        # No --socket and no socket dir -> the entry records the literal 'unknown'.
        reg = _run(tmp_path, "register", "1")
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["socket"] == "unknown"
        assert _detail(reg, "FLOW_WAVE_BOOTSTRAP") == "deadlock"

        p = _run(tmp_path, "verify", "1", "--from", "uds:/tmp/observed.sock")
        assert p.returncode == 0
        assert _verdict(p) == "address_filled"
        assert _detail(p, "FLOW_WAVE_MISMATCH") == "false"
        assert _detail(p, "FLOW_WAVE_SOCKET") == "uds:/tmp/observed.sock"

        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["socket"] == "uds:/tmp/observed.sock"
        assert entry["verified"] is True
        assert entry["address_filled"] is True
        # The whole point: benign, so the flag stays DOWN.
        assert entry["address_mismatch"] is False

    def test_filled_does_not_tell_the_reader_to_investigate(self, tmp_path: Path) -> None:
        """A flag that fires on the normal case trains everyone to ignore it."""
        _run(tmp_path, "register", "1")
        p = _run(tmp_path, "verify", "1", "--from", "uds:/tmp/observed.sock")
        assert "WARNING" not in p.stderr
        assert "Investigate" not in p.stderr
        assert "Nothing to investigate" in p.stderr

    def test_real_address_contradiction_still_shouts(self, tmp_path: Path) -> None:
        """The discrimination: a genuine mismatch keeps the loud treatment."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/self-derived.sock")
        p = _run(tmp_path, "verify", "1", "--from", "uds:/tmp/observed.sock")
        assert _verdict(p) == "mismatch-corrected"
        assert "WARNING" in p.stderr
        assert "Investigate the discrepancy" in p.stderr
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["address_mismatch"] is True

    def test_list_renders_filled_and_mismatch_distinctly(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1")
        _run(tmp_path, "verify", "1", "--from", "uds:/tmp/observed.sock")
        _run(tmp_path, "register", "2", "--socket", "uds:/tmp/claimed.sock")
        _run(tmp_path, "verify", "2", "--from", "uds:/tmp/other-observed.sock")

        p = _run(tmp_path, "list", live=SELF_PID)
        assert "1 -> uds:/tmp/observed.sock [live, filled]" in p.stdout
        assert "2 -> uds:/tmp/other-observed.sock [live, MISMATCH-corrected]" in p.stdout

    def test_filled_verdict_does_not_abort_a_strict_caller(self, tmp_path: Path) -> None:
        """A new verdict must not become a new exit code (issue #673's lesson).

        Dropping ``|| true`` from drift-detect.sh let a helper's new exit 3 abort
        the whole report under ``set -euo pipefail`` - and the symptom was a
        TRUNCATED report, not an error, which reads as success. So assert the
        CALLER RUNS TO COMPLETION, not merely that the new verdict prints:
        completion is the property, and intent is not a regression test.
        """
        _run(tmp_path, "register", "1")
        caller = tmp_path / "caller.sh"
        caller.write_text(
            "set -euo pipefail\n"
            f'bash {REGISTRY} verify 1 --from uds:/tmp/observed.sock --wave default\n'
            "echo CALLER_REACHED_THE_END\n"
        )
        env = os.environ.copy()
        env.update(
            {
                "CLAUDE_PID": SELF_PID,
                "CLAUDE_CODE_SESSION_ID": SELF_SESSION,
                "FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg"),
                "FLOW_WAVE_SOCK_DIR": str(tmp_path / "socks"),
                "FLOW_WAVE_HOST": HOST,
                "FLOW_WAVE_LIVE_PIDS": "",
                "FLOW_WAVE_NOW": "1700000000",
            }
        )
        p = subprocess.run(
            ["bash", str(caller)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert p.returncode == 0
        assert "FLOW_WAVE: address_filled" in p.stdout
        assert "CALLER_REACHED_THE_END" in p.stdout


@requires_tools
class TestSharedParentCwdAdvisory:
    """Registering from a shared parent advises, it does not fail (#683)."""

    def _parent_with_two_checkouts(self, tmp: Path) -> Path:
        parent = tmp / "projects"
        for name in ("repo-a", "repo-b"):
            (parent / name / ".git").mkdir(parents=True)
        return parent

    def test_parent_cwd_advises_without_changing_the_verdict(self, tmp_path: Path) -> None:
        parent = self._parent_with_two_checkouts(tmp_path)
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock", "--cwd", str(parent))
        assert p.returncode == 0
        assert _verdict(p) == "registered"  # advisory only - verdict untouched
        assert "shared parent directory" in p.stderr
        assert "cry wolf" in p.stderr

    def test_ancestor_of_declared_repo_advises(self, tmp_path: Path) -> None:
        """The direct signature: cwd is a strict ancestor of --repo."""
        parent = tmp_path / "projects"
        repo = parent / "the-repo"
        repo.mkdir(parents=True)
        p = _run(
            tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock",
            "--cwd", str(parent), "--repo", str(repo),
        )
        assert "shared parent directory" in p.stderr

    def test_real_worktree_cwd_is_silent(self, tmp_path: Path) -> None:
        """A warning that fires on the normal case is the bug, so: no false positive."""
        wt = tmp_path / "projects" / "repo-a"
        (wt / ".git").mkdir(parents=True)
        p = _run(
            tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock",
            "--cwd", str(wt), "--repo", str(wt),
        )
        assert "shared parent" not in p.stderr


@requires_tools
class TestLaneLessRolesExemptFromOverlap:
    """A role that declared no lane cannot collide (#683).

    The overlap mechanism compares DECLARED lanes. The orchestrator never holds
    one (CLAUDE.md:136) and its cwd is structurally the projects parent, so it
    nested over every worktree and warned once per live worker for a whole wave.
    """

    def _wave(self, tmp: Path) -> None:
        _run(tmp, "register", "orchestrator", "--socket", "uds:/tmp/o.sock",
             "--cwd", "/projects", "--repo", "/projects/repo",
             pid="100", session="orch")
        _run(tmp, "register", "A", "--socket", "uds:/tmp/a.sock",
             "--cwd", "/projects/repo-wt-a", "--repo", "/projects/repo",
             "--issue", "1", "--branch", "b1", pid="101", session="s1")
        _run(tmp, "register", "IDLE", "--socket", "uds:/tmp/i.sock",
             "--cwd", "/projects", "--repo", "/projects/repo",
             pid="102", session="s2")

    def test_orchestrator_and_unassigned_roles_do_not_warn(self, tmp_path: Path) -> None:
        self._wave(tmp_path)
        p = _run(tmp_path, "list", live="100:101:102")
        assert "WARNING" not in p.stdout
        assert "WARNING" not in p.stderr

    def test_exemption_is_announced_not_silent(self, tmp_path: Path) -> None:
        """Do-not-alarm is not do-not-say: a skipped check must stay visible."""
        self._wave(tmp_path)
        p = _run(tmp_path, "list", live="100:101:102")
        assert "overlap checks skipped for lane-less live role(s)" in p.stdout
        assert "orchestrator" in p.stdout
        assert "IDLE" in p.stdout

    def test_a_real_overlap_between_lane_holders_still_warns(self, tmp_path: Path) -> None:
        """The discrimination: exempting lane-less roles must not blind the check."""
        self._wave(tmp_path)
        _run(tmp_path, "register", "B", "--socket", "uds:/tmp/b.sock",
             "--cwd", "/projects/repo-wt-a", "--repo", "/projects/repo",
             "--issue", "1", "--branch", "b1", pid="103", session="s3")
        p = _run(tmp_path, "list", live="100:101:102:103")
        assert "WARNING" in p.stdout
        assert "both claim issue #1" in p.stdout

    def test_exemption_lapses_when_the_role_claims_an_issue(self, tmp_path: Path) -> None:
        self._wave(tmp_path)
        # IDLE claims A's branch - now it holds a lane, so the check applies.
        _run(tmp_path, "register", "IDLE", "--socket", "uds:/tmp/i.sock",
             "--cwd", "/projects/repo-wt-a", "--repo", "/projects/repo",
             "--issue", "7", "--branch", "b1", pid="102", session="s2")
        p = _run(tmp_path, "list", live="100:101:102")
        assert "both claim branch 'b1'" in p.stdout


def _pid1_is_unsignalable() -> bool:
    """Can this process NOT signal pid 1?

    Asked by DOING it rather than by reasoning about uids. Whether a signal is
    permitted depends on real and effective uids, on privileges, on user
    namespaces and on the LSM - so any predicate built from `geteuid()` and
    `stat()` is a model of the kernel's rules that can disagree with the kernel.
    `kill(pid, 0)` delivers no signal and performs exactly the permission check
    the test's premise is about.

    Any other `OSError` (notably `ProcessLookupError`, which would mean no pid 1
    at all) answers False: the test needs a pid that EXISTS and is unsignalable,
    and a missing one is not that.
    """
    try:
        os.kill(1, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return False


class TestPid1SignalProbe:
    """`_pid1_is_unsignalable` must DISCRIMINATE, not just answer False.

    A skip guard that is always true deletes the coverage it guards while
    reporting green, which is worse than the failure it replaced - and the
    failure it replaced (#881/#882 root: a test assuming it owns the host) was
    at least visible. These pin that the probe still says yes where the premise
    holds, so "skipped" in a container cannot quietly become "skipped
    everywhere".

    The probe is exercised through a substituted `os.kill` rather than against
    real pids: the three outcomes it must separate cannot all be produced on one
    machine, which is the whole reason the original proxy went unnoticed.
    """

    def test_eperm_means_unsignalable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _kill(pid: int, sig: int) -> None:
            raise PermissionError(1, "Operation not permitted")

        monkeypatch.setattr(os, "kill", _kill)
        assert _pid1_is_unsignalable() is True

    def test_a_signalable_pid1_means_the_premise_does_not_hold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The container case: pid 1 runs as our own uid, so the signal lands.

        This is the one that used to produce a hard failure on every branch.
        """
        monkeypatch.setattr(os, "kill", lambda pid, sig: None)
        assert _pid1_is_unsignalable() is False

    def test_a_missing_pid1_is_not_an_unsignalable_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ESRCH is not EPERM. The test needs a pid that exists AND is refused."""

        def _kill(pid: int, sig: int) -> None:
            raise ProcessLookupError(3, "No such process")

        monkeypatch.setattr(os, "kill", _kill)
        assert _pid1_is_unsignalable() is False


@requires_tools
class TestLeftoverSocketIsNotProofOfLife:
    """A socket file corroborates; it never proves (#869).

    The kernel does not unlink a unix domain socket when its owner dies, so the
    file outlives the process. The old fallback consulted it AFTER the pid had
    already been reported dead and returned `live` on the strength of it, which
    made the WEAKER evidence override the STRONGER one: a SIGKILLed session read
    `live` for as long as its socket sat on disk.

    #675's stated purpose survives intact. It wanted to cover "a pid the helper
    cannot signal" - the EPERM case - and that is now answered by classifying
    `kill -0`'s two failure modes rather than by stat-ing a path. What is removed
    is only the socket's power to override a definite ESRCH, which #675 never
    claimed. #689's uds-only asymmetry is gone rather than documented, because
    errno needs no socket and so works on every transport.
    """

    def test_leftover_uds_socket_does_not_resurrect_a_dead_pid(self, tmp_path: Path) -> None:
        """The exact defect: dead pid + socket file still on disk -> stale."""
        import socket as _socket

        sock_path = tmp_path / "leftover.sock"
        s = _socket.socket(_socket.AF_UNIX)
        try:
            s.bind(str(sock_path))
        except OSError as exc:  # path too long for AF_UNIX on this box
            pytest.skip(f"cannot bind AF_UNIX socket here: {exc}")
        try:
            assert sock_path.is_socket()  # the file the old branch trusted
            _run(tmp_path, "register", "1", "--socket", f"uds:{sock_path}", pid="999999")

            dead = _run(tmp_path, "get", "1", live="none")
            assert _detail(dead, "FLOW_WAVE_LIVENESS") == "stale"
            assert _detail(dead, "FLOW_WAVE_LIVENESS_BASIS") == "pid-gone"

            # Positive control: the SAME socket file, with the pid pinned alive,
            # must read live - otherwise this test could pass on a registry that
            # simply never returns `live` at all.
            alive = _run(tmp_path, "get", "1", live="999999")
            assert _detail(alive, "FLOW_WAVE_LIVENESS") == "live"
            assert _detail(alive, "FLOW_WAVE_LIVENESS_BASIS") == "pid-present"
        finally:
            s.close()

    @pytest.mark.skipif(not Path("/proc/self").is_dir(), reason="needs /proc")
    def test_sigkilled_owner_reads_stale_against_the_real_process_table(
        self, tmp_path: Path
    ) -> None:
        """The issue's own positive control, end to end, with no liveness hook.

        `FLOW_WAVE_LIVE_PIDS` is left EMPTY so the real prober runs. A pinned
        list would prove only that the hook works.
        """
        import signal

        sock_path = tmp_path / "victim.sock"
        code = (
            "import socket,time;s=socket.socket(socket.AF_UNIX);"
            f"s.bind({str(sock_path)!r});print('up',flush=True);time.sleep(300)"
        )
        proc = subprocess.Popen(["python3", "-c", code], stdout=subprocess.PIPE, text=True)
        try:
            assert proc.stdout is not None
            if proc.stdout.readline().strip() != "up":
                pytest.skip("helper could not bind an AF_UNIX socket here")
            pid = str(proc.pid)
            # live="" explicitly: this test's whole point is the REAL process
            # table end to end (issue #1094 too - a real pid's real /proc
            # start time, never a faked witness).
            _run(tmp_path, "register", "1", "--socket", f"uds:{sock_path}", pid=pid, live="")

            # Bound, owner alive -> file exists, and the roster agrees.
            assert _detail(_run(tmp_path, "get", "1", pid=pid), "FLOW_WAVE_LIVENESS") == "live"

            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=10)
            deadline = time.monotonic() + 10
            while Path(f"/proc/{pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert not Path(f"/proc/{pid}").exists(), "death not confirmed"

            # SIGKILL owner, death confirmed -> file STILL on disk, still a socket.
            assert sock_path.is_socket()

            p = _run(tmp_path, "get", "1", pid=pid)
            assert _detail(p, "FLOW_WAVE_LIVENESS") == "stale"
            assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-gone"
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    @pytest.mark.skipif(
        not _pid1_is_unsignalable(),
        reason="needs a pid 1 this process may not signal (see _pid1_is_unsignalable)",
    )
    def test_a_pid_we_may_not_signal_still_reads_live(self, tmp_path: Path) -> None:
        """#675's actual case, served by the better instrument.

        pid 1 exists and this process may not signal it, so `kill -0` fails with
        EPERM exactly as it would for a session owned by another user. The old
        code reached this only via a socket file; there is no socket here.

        The skip condition used to be `geteuid() != 0`, which INFERS the property
        from a proxy: on an ordinary host pid 1 is root's `init`, so a non-root
        euid cannot signal it. That proxy is false in a container with an
        unprivileged entrypoint - a Kyle session container runs pid 1
        (`kyle-entrypoint`) as the SAME uid 1000 the suite runs as, so
        `os.kill(1, 0)` succeeds, `pytest.raises(PermissionError)` gets nothing,
        and the test fails on every branch for a reason no branch caused. It now
        probes the property directly instead (issues #881, #882 - same root,
        different host resource).

        The `pytest.raises` below is therefore a restatement of the skip
        condition rather than an independent check. It is kept deliberately: if
        someone later loosens the guard back to a proxy, this is what fails.
        """
        # Asserted through os.kill rather than a `kill` BINARY: this test's
        # claim is about the errno, and a minimal container without procps
        # would turn a missing binary into an ERROR rather than a skip.
        with pytest.raises(PermissionError):
            os.kill(1, 0)
        # live="" explicitly (issue #1094): pid 1 is real here, and this
        # test's point is the REAL EPERM path, never a faked witness.
        _run(tmp_path, "register", "1", "--socket", "uds:/nonexistent/none.sock", pid="1", live="")
        p = _run(tmp_path, "get", "1", pid="1")
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "live"
        assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-present"

    def test_non_uds_address_gets_the_same_primary_evidence(self, tmp_path: Path) -> None:
        """#689's asymmetry is removed, not documented: errno needs no socket."""
        _run(tmp_path, "register", "1", "--socket", "bridge:session_01RLEabc", pid="999998")
        dead = _run(tmp_path, "list", live="none")
        assert dead.returncode == 0
        assert "[stale," in dead.stdout
        alive = _run(tmp_path, "get", "1", live="999998")
        assert _detail(alive, "FLOW_WAVE_LIVENESS") == "live"


@requires_tools
class TestPidRecyclingWitness:
    """pid EXISTENCE is not pid IDENTITY (issue #1094).

    `pid_state` alone answers "does a process with this number exist", never
    "is it the SAME process a registry entry recorded" - a registered pid
    that exits and is later reused by the kernel for an unrelated process
    reads `alive` either way. `pid_started` (a process start-time witness,
    `/proc/<pid>/stat` field 22) closes that gap without a persistent daemon
    or a flock - `register` is a one-shot invocation with nothing that could
    hold a lock for the life of the session it records.

    A real pid cannot be forced to recycle on demand for a test, so every
    fixture here is built from the RECORD side instead: an entry whose
    recorded `pid_started` differs from what a live pid's CURRENT witness
    reads is indistinguishable, to the checker, from a genuinely recycled
    pid. `FLOW_WAVE_PID_STARTTIMES` (a test hook) is what makes that
    constructible - it overrides the CURRENT read for a chosen pid
    independent of what was recorded for it at registration.
    """

    def test_a_never_recorded_witness_reads_live_with_a_weaker_basis(
        self, tmp_path: Path
    ) -> None:
        """BLANK IS NOT A MATCH (orchestrator ruling, #1094 msg 1039/1041).
        Every registry entry that predates issue #1094 has no `pid_started`
        field at all - falling through to "the comparison passed" for one
        would report the strongest BASIS this instrument can give
        (`pid-present`) for every pre-existing entry in the fleet, on no
        evidence at all. Never-recorded and recorded-and-equal must stay
        different facts in the BASIS.

        But the VERDICT stays `live`, deliberately not `unknown`: the
        witness can only ever ADD a positive finding (a proven mismatch),
        never subtract one, and every consumer of `liveness_of` (five call
        sites, as of #1094) tests it as a plain `= "live"` binary - a third
        verdict value here would reclassify every pre-#1094 entry from live
        to not-live fleet-wide, with no reader able to act on the new
        distinction. The basis still carries it for anyone who reads that
        field instead of the summary word."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/legacy.sock", pid="31337", live="")
        entry_path = tmp_path / "reg" / "registry.json"
        data = json.loads(entry_path.read_text())
        role = data["default"]["roles"]["1"]
        assert "pid_started" in role, "register must always write the field, even if blank"
        role.pop("pid_started")
        entry_path.write_text(json.dumps(data))

        p = _run(tmp_path, "get", "1", pid="31337", live="31337")
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "live"
        assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-present-witness-absent"

    def test_an_unreadable_current_witness_also_reads_live_with_a_weaker_basis(
        self, tmp_path: Path
    ) -> None:
        """Same ruling, the other blank: this time the entry HAS a recorded
        witness, but the CURRENT one cannot be read (`pid_started_of`
        returns `-`). Passing `starttimes=""` on the `get` call disables the
        test helper's default witness derivation, and pointing
        `FLOW_WAVE_PROC_ROOT` at an empty directory guarantees the
        script's real-`/proc` fallback finds no `stat` file to read -
        deterministic, rather than relying on a fake pid number happening
        not to be a real process on the machine running the test. Not
        evidence of recycling either, so it reads `live` too, with its own
        distinct basis."""
        _run(
            tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock",
            pid="55009", live="55009", starttimes="55009=1000",
        )
        empty_proc_root = tmp_path / "no-such-proc"
        empty_proc_root.mkdir()
        p = _run(
            tmp_path, "get", "1", pid="55009", live="55009", starttimes="",
            extra_env={"FLOW_WAVE_PROC_ROOT": str(empty_proc_root)},
        )
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "live"
        assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-present-witness-undeterminable"

    def test_a_differing_witness_reads_recycled_not_live(self, tmp_path: Path) -> None:
        """The positive control: register with one witness, then read the
        SAME pid back with a DIFFERENT one - the record-side fixture that
        stands in for a real recycled pid, since the kernel cannot be made
        to hand out a chosen number on demand."""
        _run(
            tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock",
            pid="55001", live="55001", starttimes="55001=1000",
        )
        p = _run(tmp_path, "get", "1", pid="55001", live="55001", starttimes="55001=9999")
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "stale"
        assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-recycled"

    def test_a_matching_witness_reads_live_the_mirror_of_the_above(
        self, tmp_path: Path
    ) -> None:
        """The mirror of the recycling case, same fixture shape, only the
        SECOND witness changed - this is what proves the check
        DISCRIMINATES rather than just refusing every read."""
        _run(
            tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock",
            pid="55002", live="55002", starttimes="55002=1000",
        )
        p = _run(tmp_path, "get", "1", pid="55002", live="55002", starttimes="55002=1000")
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "live"
        assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-present"

    def test_the_old_pid_only_logic_does_not_catch_the_same_fixture(
        self, tmp_path: Path
    ) -> None:
        """Proves the new comparison is LOAD-BEARING rather than the fixture
        being odd: substitute the pre-#1094 `_liveness_compute` (pid
        existence only, no witness) back in, run it against the IDENTICAL
        recycling fixture the RED/GREEN tests above use, and confirm it
        does NOT report `pid-recycled` - it must still say `live`, which is
        exactly the false positive #1094 exists to close."""
        old_compute = (
            'st="$(pid_state "$pid")"\n'
            "  case \"$st\" in\n"
            '    alive) echo "live pid-present"; return ;;\n'
            "    gone)  echo \"stale pid-gone\"; return ;;\n"
            "  esac"
        )
        current = REGISTRY.read_text()
        start = current.index('  st="$(pid_state "$pid")"')
        end = current.index("esac", start) + len("esac")
        assert current[start:end] != old_compute, (
            "the source no longer contains the block this test replaces - "
            "update the substitution rather than let it silently no-op"
        )
        patched = current[:start] + old_compute + current[end:]
        patched_script = tmp_path / "flow-wave-registry-old-logic.sh"
        patched_script.write_text(patched)
        patched_script.chmod(0o755)

        env = os.environ.copy()
        env.update(
            {
                "CLAUDE_PID": "55003",
                "CLAUDE_CODE_SESSION_ID": SELF_SESSION,
                "FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg"),
                "FLOW_WAVE_SOCK_DIR": str(tmp_path / "socks"),
                "FLOW_WAVE_HOST": HOST,
                "FLOW_WAVE_NOW": "1700000000",
            }
        )

        def _run_old(*args: str, live: str, starttimes: str) -> subprocess.CompletedProcess[str]:
            e = env.copy()
            e["FLOW_WAVE_LIVE_PIDS"] = live
            e["FLOW_WAVE_PID_STARTTIMES"] = starttimes
            return subprocess.run(
                ["bash", str(patched_script), *args],
                capture_output=True, text=True, env=e, check=False,
            )

        _run_old(
            "register", "1", "--socket", "uds:/tmp/a.sock",
            live="55003", starttimes="55003=1000",
        )
        p = _run_old("get", "1", live="55003", starttimes="55003=9999")
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "live", (
            "the OLD logic must still be fooled by this fixture - if it "
            "is not, the fixture no longer isolates what the new "
            "comparison adds"
        )

    def test_starttime_parsing_survives_a_comm_with_a_space_and_a_paren(
        self, tmp_path: Path
    ) -> None:
        """THE PARSING TRAP IS ITSELF WORTH A COMMITTED CASE. `comm` (field 2
        of /proc/<pid>/stat) is parenthesised and may itself contain spaces
        or parens - a naive positional `awk '{print $22}'` silently shifts
        every field after it. Measured directly during planning: a raw $22
        read a start time from before the process could have existed. This
        feeds a CRAFTED stat line through the real parser via
        FLOW_WAVE_PROC_ROOT and asserts the correct field, split past the
        LAST `)` - a naive positional parse of the same line would read
        field 22 counting from the FRONT and get a value from the middle of
        the comm-adjacent fields instead."""
        pid = "77001"
        proc_root = tmp_path / "proc"
        (proc_root / pid).mkdir(parents=True)
        # A comm containing both a space and a literal paren: "od d)d". The
        # real fields after the LAST ')' are, in order: state ppid pgrp
        # session tty_nr tpgid flags minflt cminflt majflt cmajflt utime
        # stime cutime cstime priority nice num_threads itrealvalue
        # starttime - 20 tokens, starttime last, deliberately set to a
        # value (424242) nowhere else in the line so a naive parse cannot
        # stumble onto it by accident.
        stat_line = (
            f"{pid} (od d)d) R 1 1 1 0 -1 4194304 "
            "10 0 0 0 5 6 0 0 20 0 1 0 424242 6410240 384 "
            "18446744073709551615 0 0 0 0 0 0 0 0 0 0 17 0 0 0 0 0 0 0 0"
        )
        (proc_root / pid / "stat").write_text(stat_line)

        env = os.environ.copy()
        env["FLOW_WAVE_PROC_ROOT"] = str(proc_root)
        # A NAIVE split-on-space, whole-line, field-22 read - what this
        # parser must NOT reproduce - to show the trap is real on this exact
        # line, not just asserted.
        naive = stat_line.split()[21]  # 0-indexed: field 22
        assert naive != "424242", (
            "the fixture's naive-parse field must differ from the real "
            "starttime, or this test cannot tell the two parsers apart"
        )

        # Extract ONLY the function under test, never `source` the whole
        # script: the file is a top-level `case "$VERB" in ... esac`
        # dispatch with no verb-safe guard, so sourcing it with no
        # arguments runs straight into `usage_fail`'s `exit`, which would
        # tear down this test's own shell before pid_started_of ever ran.
        source_text = REGISTRY.read_text()
        fn_start = source_text.index("pid_started_of() {")
        fn_end = source_text.index("\n}\n", fn_start) + len("\n}\n")
        fn_only = source_text[fn_start:fn_end]
        assert fn_only.strip().startswith("pid_started_of() {"), (
            "extraction failed - update the markers rather than let this "
            "test silently source nothing"
        )
        fn_file = tmp_path / "pid_started_of.sh"
        fn_file.write_text(fn_only)

        result = subprocess.run(
            ["bash", "-c", f'source "{fn_file}"; pid_started_of "{pid}"'],
            capture_output=True, text=True, env=env, check=False,
        )
        assert result.stdout.strip() == "424242"


@requires_tools
class TestAnyLive:
    """`list --wave W --any-live` (issue #1095): a purpose-built, cheap
    answer for a poller (flow-wave-mailbox.sh's `__supervise_daemon`) that
    must distinguish "something is still live" from the TWO different
    causes of "nothing is" - a wave whose roles all ended, and a wave that
    never had any roles at all - without paying for the mailbox join or the
    unregistered-claims filesystem scan `list` otherwise does."""

    def test_a_live_role_reads_yes(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock", pid="1", live="1")
        p = _run(tmp_path, "list", "--any-live", live="1")
        assert p.returncode == 0
        assert _detail(p, "FLOW_WAVE_ANY_LIVE") == "yes"

    def test_every_registered_role_ended_reads_no_roles_ended(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock", pid="1", live="1")
        p = _run(tmp_path, "list", "--any-live", live="none")
        assert p.returncode == 1
        assert _detail(p, "FLOW_WAVE_ANY_LIVE") == "no-roles-ended"

    def test_no_roles_at_all_reads_no_roles_registered(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "list", "--any-live")
        assert p.returncode == 1
        assert _detail(p, "FLOW_WAVE_ANY_LIVE") == "no-roles-registered"

    def test_a_malformed_registry_reads_undeterminable_not_no_roles_registered(
        self, tmp_path: Path
    ) -> None:
        """A registry file that exists but cannot be parsed must not read
        the same as a genuinely empty one - a corrupt file demoted to
        'no roles registered' would look identical to a real
        misconfiguration to anything consuming this, when it is really an
        I/O or storage fault with no bearing on what is actually running.
        RED against a version that skips the jq-status check entirely (it
        would read `no-roles-registered` here, exactly like the case
        above); GREEN with the check in place."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock", pid="1", live="1")
        reg_file = tmp_path / "reg" / "registry.json"
        reg_file.write_text("{not valid json")
        p = _run(tmp_path, "list", "--any-live", live="1")
        assert p.returncode == 2
        assert _detail(p, "FLOW_WAVE_ANY_LIVE") == "undeterminable"

    @pytest.mark.parametrize(
        "content",
        [
            "  \n",
            "null\n",
            "null\n{}\n",
            '{"%(w)s": {"roles": false}}',
            '{"%(w)s": {"roles": []}}',
            '{"%(w)s": 7}',
        ],
        ids=["whitespace-only", "json-null", "two-documents", "roles-false", "roles-array", "wave-scalar"],
    )
    def test_a_registry_that_parses_to_no_object_reads_undeterminable(
        self, tmp_path: Path, content: str
    ) -> None:
        """Counter-model review, #1107: both of these make jq exit 0 with no
        object read - whitespace yields zero inputs, `null` falls through
        `// {}` - so they read `no-roles-registered`, an affirmative claim
        that the wave is empty, from a file nothing parsed. `supervise
        --registry-required` turns that word into exit 7 `misconfigured`.
        The second pass added the rest: two documents (jq -e judged only the
        last), and a roster that is not an object (`// {}` or `keys[]` made
        it read empty). RED before the check (all read
        `no-roles-registered`)."""
        reg_dir = tmp_path / "reg"
        reg_dir.mkdir(parents=True, exist_ok=True)
        (reg_dir / "registry.json").write_text(content % {"w": "default"} if "%(w)s" in content else content)
        assert (reg_dir / "registry.json").stat().st_size > 0  # not the absent case
        p = _run(tmp_path, "list", "--any-live")
        assert p.returncode == 2
        assert _detail(p, "FLOW_WAVE_ANY_LIVE") == "undeterminable"

    def test_a_valid_registry_without_this_wave_still_reads_no_roles_registered(
        self, tmp_path: Path
    ) -> None:
        """The object check must not over-reach: a well-formed registry whose
        only entries belong to ANOTHER wave, or whose wave has an explicit
        empty roster, is affirmative evidence that this wave is empty."""
        reg_dir = tmp_path / "reg"
        reg_dir.mkdir(parents=True, exist_ok=True)
        for content in ('{"some-other-wave": {"roles": {"1": {}}}}', '{"default": {"roles": {}}}'):
            (reg_dir / "registry.json").write_text(content)
            p = _run(tmp_path, "list", "--any-live")
            assert p.returncode == 1, content
            assert _detail(p, "FLOW_WAVE_ANY_LIVE") == "no-roles-registered", content

    def test_a_zero_byte_registry_still_reads_no_roles_registered(
        self, tmp_path: Path
    ) -> None:
        """The other side of the object check: a 0-byte file is how an
        absent registry looks to `read_registry`, and it must keep its
        affirmative empty answer rather than be swept into undeterminable."""
        reg_dir = tmp_path / "reg"
        reg_dir.mkdir(parents=True, exist_ok=True)
        (reg_dir / "registry.json").write_text("")
        p = _run(tmp_path, "list", "--any-live")
        assert p.returncode == 1
        assert _detail(p, "FLOW_WAVE_ANY_LIVE") == "no-roles-registered"


@requires_tools
class TestUndeterminableLivenessIsItsOwnState:
    """`unknown` is a third answer, not a polite `stale` (#869).

    A host that cannot enumerate its process table has not reported a death, and
    rounding that down to one is the mistake the sibling mailbox refused when it
    moved off pid liveness (#814). Never checked and checked-but-undecidable are
    different facts.
    """

    def test_undeterminable_pid_reads_unknown_not_live(self, tmp_path: Path) -> None:
        import socket as _socket

        sock_path = tmp_path / "corroborating.sock"
        s = _socket.socket(_socket.AF_UNIX)
        try:
            s.bind(str(sock_path))
        except OSError as exc:
            pytest.skip(f"cannot bind AF_UNIX socket here: {exc}")
        try:
            _run(tmp_path, "register", "1", "--socket", f"uds:{sock_path}", pid="999999")
            p = _run(tmp_path, "get", "1", live="none", unknown="999999")
            # Present socket + undeterminable pid is the case the OLD code
            # called `live`. It corroborates, and it still decides nothing.
            assert _detail(p, "FLOW_WAVE_LIVENESS") == "unknown"
            assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-undeterminable-socket-present"
        finally:
            s.close()

    def test_basis_distinguishes_a_missing_socket_from_a_present_one(
        self, tmp_path: Path
    ) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/nonexistent/gone.sock", pid="999999")
        p = _run(tmp_path, "get", "1", live="none", unknown="999999")
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "unknown"
        assert _detail(p, "FLOW_WAVE_LIVENESS_BASIS") == "pid-undeterminable-socket-absent"

    def test_unknown_owner_is_not_taken_over_without_force(self, tmp_path: Path) -> None:
        """Only a PROVEN death frees a role - #638's guarantee, unchanged."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock",
             pid=OTHER_PID, session=OTHER_SESSION)
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/y.sock",
                 live="none", unknown=OTHER_PID)
        assert _verdict(p) == "refused"
        assert p.returncode == 1
        assert _detail(p, "FLOW_WAVE_LIVENESS") == "unknown"
        assert "UNDETERMINABLE" in p.stderr

    def test_force_takes_over_an_unknown_owner_and_says_it_was_not_confirmed(
        self, tmp_path: Path
    ) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock",
             pid=OTHER_PID, session=OTHER_SESSION)
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/y.sock", "--force",
                 live="none", unknown=OTHER_PID)
        assert _verdict(p) == "registered"
        assert "NOT confirmed gone" in p.stderr

    def test_a_proven_dead_owner_is_still_taken_over_silently(self, tmp_path: Path) -> None:
        """The `unknown` refusal must not wedge the ordinary stale takeover."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock",
             pid=OTHER_PID, session=OTHER_SESSION)
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/y.sock", live="none")
        assert _verdict(p) == "registered"
        assert "taking over stale role" in p.stderr

    def test_release_refuses_an_unknown_owner(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock",
             pid=OTHER_PID, session=OTHER_SESSION)
        p = _run(tmp_path, "release", "1", live="none", unknown=OTHER_PID)
        assert _verdict(p) == "refused"
        assert p.returncode == 1

    def test_unknown_is_rendered_with_its_basis_in_the_roster(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/nonexistent/gone.sock", pid="999999")
        p = _run(tmp_path, "list", live="none", unknown="999999")
        assert "[unknown:pid-undeterminable-socket-absent," in p.stdout

    def test_ordinary_roster_lines_are_unchanged(self, tmp_path: Path) -> None:
        """Only `unknown` carries a basis, so a normal wave reads as before."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock")
        live = _run(tmp_path, "list", live=SELF_PID)
        assert "[live, " in live.stdout and "live:" not in live.stdout
        stale = _run(tmp_path, "list", live="none")
        assert "[stale, " in stale.stdout and "stale:" not in stale.stdout

    def test_roster_counts_roles_whose_liveness_could_not_be_determined(
        self, tmp_path: Path
    ) -> None:
        """The receipt for a role every `= live` consumer skips.

        Skipping an `unknown` role is correct - but it leaves that role neither
        overlap-checked nor counted as unchecked, so without this counter the
        roster reports a clean verdict over a role nobody examined. Same reason
        #800 emits `FLOW_WAVE_OVERLAP_UNSCOPED`.
        """
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock",
             pid="200", session="s-a")
        _run(tmp_path, "register", "2", "--socket", "uds:/tmp/b.sock",
             pid="300", session="s-b")
        p = _run(tmp_path, "list", live="200", unknown="300")
        assert _detail(p, "FLOW_WAVE_LIVENESS_UNDETERMINED") == "1"
        # Emitted as a VALUE even when zero, so a consumer can tell "none" from
        # "this call does not report it".
        clean = _run(tmp_path, "list", live="200:300")
        assert _detail(clean, "FLOW_WAVE_LIVENESS_UNDETERMINED") == "0"

    def test_the_counter_is_reported_on_every_list_render_path(
        self, tmp_path: Path
    ) -> None:
        """Including --json and the empty roster - the #800 promise, kept."""
        empty = _run(tmp_path, "list")
        assert _detail(empty, "FLOW_WAVE_LIVENESS_UNDETERMINED") == "0"
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock", pid="300")
        js = _run(tmp_path, "list", "--json", live="none", unknown="300")
        assert _detail(js, "FLOW_WAVE_LIVENESS_UNDETERMINED") == "1"

    def test_list_json_carries_the_basis_beside_the_liveness(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/nonexistent/gone.sock", pid="999999")
        p = _run(tmp_path, "list", "--json", live="none", unknown="999999")
        entry = _json_payload(p)["1"]
        assert entry["liveness"] == "unknown"
        assert entry["liveness_basis"] == "pid-undeterminable-socket-absent"


@requires_tools
class TestObservationFlagsSurviveReRegister:
    """One observation, one lifecycle (#691/#692).

    `verified`, `address_filled` and `address_mismatch` all record the same fact
    - the transport was observed to reach THIS session at THIS address - so a
    re-register that changes neither must not rewrite any of them. #691 is the
    annoying direction (trust downgraded); #692 is the dangerous one (a genuine
    misrouting flag erased by the routine re-brief the protocol recommends).
    """

    def test_verified_survives_an_unchanged_re_register(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock")
        _run(tmp_path, "verify", "1", "--from", "uds:/tmp/x.sock")
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock", "--issue", "42")
        assert _detail(p, "FLOW_WAVE_VERIFIED") == "true"
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["verified"] is True
        assert entry["issue"] == "42"  # the lane update still applied

    def test_address_mismatch_survives_the_cheap_re_brief(self, tmp_path: Path) -> None:
        """#692, the dangerous direction: an uninvestigated flag must not vanish."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/claimed.sock")
        v = _run(tmp_path, "verify", "1", "--from", "uds:/tmp/observed.sock")
        assert _verdict(v) == "mismatch-corrected"
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/observed.sock", "--issue", "42")
        assert _detail(p, "FLOW_WAVE_MISMATCH") == "true"
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["address_mismatch"] is True

    def test_address_filled_survives(self, tmp_path: Path) -> None:
        """Else a filled entry silently re-renders as plain `verified` (#674)."""
        _run(tmp_path, "register", "1")  # no socket dir -> 'unknown'
        _run(tmp_path, "verify", "1", "--from", "uds:/tmp/observed.sock")
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/observed.sock", "--issue", "42")
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["address_filled"] is True
        p = _run(tmp_path, "list", live=SELF_PID)
        assert "[live, filled]" in p.stdout

    def test_changed_address_clears_all_three(self, tmp_path: Path) -> None:
        """The observation was about a specific address; move it and it lapses."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/a.sock")
        _run(tmp_path, "verify", "1", "--from", "uds:/tmp/a.sock")
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/moved.sock")
        assert _detail(p, "FLOW_WAVE_VERIFIED") == "false"
        entry = _registry_json(tmp_path)["default"]["roles"]["1"]
        assert entry["verified"] is False
        assert entry["address_mismatch"] is False
        assert entry["address_filled"] is False

    def test_takeover_by_another_session_clears_all_three(self, tmp_path: Path) -> None:
        """Even at the same address: it was an observation about a SESSION too."""
        _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock",
             pid=OTHER_PID, session=OTHER_SESSION)
        _run(tmp_path, "verify", "1", "--from", "uds:/tmp/x.sock")
        # Prior owner is not in FLOW_WAVE_LIVE_PIDS, so it reads stale and is
        # taken over without --force.
        p = _run(tmp_path, "register", "1", "--socket", "uds:/tmp/x.sock", live=SELF_PID)
        assert _verdict(p) == "registered"
        assert _detail(p, "FLOW_WAVE_VERIFIED") == "false"
        assert _registry_json(tmp_path)["default"]["roles"]["1"]["verified"] is False


CLAIM_PID = "7777"
CLAIM_SESSION = "session-claim"


def _claim_repo(
    tmp: Path,
    *,
    issue: str = "999",
    pid: str = CLAIM_PID,
    session: str = CLAIM_SESSION,
    host: str = HOST,
    branch: str | None = "issue-999-alpha",
    reason: str | None = None,
) -> Path:
    """A git repo with a linked worktree carrying a real flow-claim lock.

    Uses git's own locking rather than a hand-written fixture file, so the test
    reads exactly what ``flow-worktree-claim.sh`` writes and what
    ``git worktree list --porcelain`` emits.
    """
    repo = tmp / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "config", "user.email", "t@example.com"], check=True, capture_output=True)
    subprocess.run([*git, "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "f").write_text("x")
    subprocess.run([*git, "add", "f"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True, capture_output=True)
    wt = tmp / "wt-a"
    if branch is None:
        # Detached HEAD -> `git worktree list --porcelain` emits no `branch` line,
        # so the claim record carries an EMPTY middle field (issue #698).
        subprocess.run([*git, "worktree", "add", "-q", "--detach", str(wt)], check=True, capture_output=True)
    else:
        subprocess.run([*git, "worktree", "add", "-q", str(wt), "-b", branch], check=True, capture_output=True)
    if reason is None:
        reason = f"flow-claim issue={issue} pid={pid} session={session} host={host} ts=1700000000"
    subprocess.run([*git, "worktree", "lock", "--reason", reason, str(wt)], check=True, capture_output=True)
    return repo


@requires_git_tools
class TestUnregisteredClaimReconciliation:
    """`list` reconciles flow-claim worktree locks (issue #687).

    A session that goes straight to ``/flow:auto`` never registers, so its issue,
    branch and worktree were invisible to the roster while it held a real lock.
    In #673 the orchestrator read an issue as free while a live session was
    minutes from a PR on it, and only caught it by running
    ``git worktree list --porcelain`` by hand.
    """

    def _register_orchestrator(self, tmp: Path, repo: Path) -> None:
        _run(tmp, "register", "orchestrator", "--wave", "w", "--socket", "uds:/tmp/o.sock",
             "--cwd", str(tmp), "--repo", str(repo), pid="100", session="orch")

    def test_live_unregistered_claim_is_rendered(self, tmp_path: Path) -> None:
        repo = _claim_repo(tmp_path)
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
        assert "unregistered flow-claim locks" in p.stdout
        assert "(claim)" in p.stdout
        assert "issue=999" in p.stdout
        assert f"pid={CLAIM_PID}" in p.stdout

    def test_claim_participates_in_overlap_detection(self, tmp_path: Path) -> None:
        """The bar: an orchestrator reading the roster cannot double-assign.

        A claim row carries an issue, a branch and a real worktree, so it fails
        every #683b exemption condition. Pinned rather than reasoned about -
        those conditions changed twice on 2026-08-11.
        """
        repo = _claim_repo(tmp_path)
        self._register_orchestrator(tmp_path, repo)
        _run(tmp_path, "register", "A", "--wave", "w", "--socket", "uds:/tmp/a.sock",
             "--cwd", str(tmp_path / "other-wt"), "--repo", str(repo),
             "--issue", "999", "--branch", "other", pid="101", session="s1")
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:101:{CLAIM_PID}")
        assert "WARNING" in p.stdout
        assert "both claim issue #999" in p.stdout

    def test_dead_claim_is_not_rendered(self, tmp_path: Path) -> None:
        """A dead claim is worktree-remove's problem (#597), not roster noise."""
        repo = _claim_repo(tmp_path)
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", live="100")
        assert "(claim)" not in p.stdout

    def test_registered_session_claim_is_not_duplicated(self, tmp_path: Path) -> None:
        repo = _claim_repo(tmp_path)
        self._register_orchestrator(tmp_path, repo)
        _run(tmp_path, "register", "OWNER", "--wave", "w", "--socket", "uds:/tmp/g.sock",
             "--cwd", str(tmp_path / "wt-a"), "--repo", str(repo), "--issue", "999",
             pid=CLAIM_PID, session=CLAIM_SESSION)
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
        assert "(claim)" not in p.stdout

    def test_released_entry_does_not_suppress_a_live_claim(self, tmp_path: Path) -> None:
        """Only a LIVE entry accounts for a live claim.

        A released entry means the session left the wave; if something still
        holds the lock, showing the released row over a genuinely held lane
        would re-create #687's blindness through the back door.
        """
        repo = _claim_repo(tmp_path)
        self._register_orchestrator(tmp_path, repo)
        _run(tmp_path, "register", "OWNER", "--wave", "w", "--socket", "uds:/tmp/g.sock",
             "--cwd", str(tmp_path / "wt-a"), "--repo", str(repo), "--issue", "999",
             pid=CLAIM_PID, session=CLAIM_SESSION)
        _run(tmp_path, "release", "OWNER", "--wave", "w", pid=CLAIM_PID, session=CLAIM_SESSION)
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
        assert "(claim)" in p.stdout

    def test_address_is_observed_never_derived(self, tmp_path: Path) -> None:
        """#687 as filed asked for a socket DERIVED from the pid.

        That is a uds-shaped guess, and #675/#689 had just removed exactly that
        assumption. With no socket present the claim reports no address rather
        than a confident wrong one.
        """
        repo = _claim_repo(tmp_path)
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
        assert "no observed address" in p.stdout
        assert f"uds:{tmp_path}/socks/{CLAIM_PID}.sock" not in p.stdout

        # Now the socket genuinely exists -> it is reported, because it was seen.
        import socket as _socket

        (tmp_path / "socks").mkdir(exist_ok=True)
        s = _socket.socket(_socket.AF_UNIX)
        try:
            s.bind(str(tmp_path / "socks" / f"{CLAIM_PID}.sock"))
        except OSError as exc:
            pytest.skip(f"cannot bind AF_UNIX socket here: {exc}")
        try:
            p2 = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
            assert f"uds:{tmp_path}/socks/{CLAIM_PID}.sock" in p2.stdout
        finally:
            s.close()

    def test_json_keeps_roles_top_level_and_adds_a_sibling_key(self, tmp_path: Path) -> None:
        """Additive only: nesting roles under a wrapper would break every parser."""
        repo = _claim_repo(tmp_path)
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", "--json", live=f"100:{CLAIM_PID}")
        payload = _json_payload(p)
        assert "orchestrator" in payload  # roles still indexed at the top level
        assert "roles" not in payload  # and NOT nested under a wrapper
        claims = payload["unregistered_claims"]
        assert len(claims) == 1
        assert claims[0]["issue"] == "999"
        assert claims[0]["registered"] is False
        assert claims[0]["source"] == "flow-claim-lock"
        assert claims[0]["address"] is None  # observed: nothing there to observe

    def test_json_is_unchanged_when_there_are_no_claims(self, tmp_path: Path) -> None:
        """A claim-free run stays byte-compatible with pre-#687 consumers."""
        _run(tmp_path, "register", "A", "--wave", "w", "--socket", "uds:/tmp/a.sock",
             "--issue", "1", pid="101", session="s1")
        p = _run(tmp_path, "list", "--wave", "w", "--json", live="101")
        assert "unregistered_claims" not in _json_payload(p)

    def test_a_dead_entry_still_contributes_its_repo_to_the_scan(self, tmp_path: Path) -> None:
        """Repo discovery is not a liveness question.

        A stale entry is a poor account of a lane but a fine record of which
        repo the wave concerns. Restricting discovery to LIVE entries would go
        blind exactly when the wave has died back to one dead row while an
        unregistered session is still working - #687 at its worst.
        """
        repo = _claim_repo(tmp_path)
        # Registered, names the repo, and NOT in the live set -> reads stale.
        _run(tmp_path, "register", "GONE", "--wave", "w", "--socket", "uds:/tmp/x.sock",
             "--cwd", str(tmp_path), "--repo", str(repo), pid="4040", session="dead")
        p = _run(tmp_path, "list", "--wave", "w", live=CLAIM_PID)
        assert "[stale," in p.stdout  # the dead entry is still shown as such
        assert "(claim)" in p.stdout  # and its repo was still scanned
        assert "issue=999" in p.stdout

    def test_explicit_repo_flag_scans_a_repo_the_registry_never_names(self, tmp_path: Path) -> None:
        """The documented escape hatch for the coverage bound."""
        repo = _claim_repo(tmp_path)
        p = _run(tmp_path, "list", "--wave", "w", "--repo", str(repo), live=CLAIM_PID)
        assert "(claim)" in p.stdout

    def test_reconciliation_failing_open_never_breaks_the_roster(self, tmp_path: Path) -> None:
        """An absent/unreadable repo is skipped silently - list must still work."""
        _run(tmp_path, "register", "A", "--wave", "w", "--socket", "uds:/tmp/a.sock",
             "--repo", str(tmp_path / "does-not-exist"), "--issue", "1",
             pid="101", session="s1")
        p = _run(tmp_path, "list", "--wave", "w", live="101")
        assert p.returncode == 0
        assert _verdict(p) == "listed"
        assert "A -> uds:/tmp/a.sock" in p.stdout


@requires_git_tools
class TestClaimRecordPreservesEmptyFields:
    """Empty fields survive the claim record round-trip (issue #698).

    #687 joined seven fields with TAB and split them with ``IFS=$'\\t'``. Tab is
    IFS *whitespace*, so shell field splitting collapses a run of it and an EMPTY
    field vanishes instead of arriving empty - every later field shifts up one
    slot. A detached-HEAD worktree has no branch, so the claim rendered its
    worktree path as a branch and the repo root as its worktree, and fed those
    wrong values into overlap detection.

    EVERY test here is a negative control: each asserts a field value that the
    tab-delimited code got demonstrably WRONG, so a test passing against both the
    old and the new implementation would not be a regression test at all. The
    observed broken output for the branchless fixture was
    ``branch=<worktree path>`` and ``wt=<repo root>``.
    """

    def _register_orchestrator(self, tmp: Path, repo: Path) -> None:
        _run(tmp, "register", "orchestrator", "--wave", "w", "--socket", "uds:/tmp/o.sock",
             "--cwd", str(tmp), "--repo", str(repo), pid="100", session="orch")

    def test_branchless_claim_keeps_every_later_field_in_place(self, tmp_path: Path) -> None:
        """Empty MIDDLE field. Broken code printed the worktree path as the branch."""
        repo = _claim_repo(tmp_path, branch=None)
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
        assert "branch=-" in p.stdout  # empty, not the worktree path
        assert f"wt={tmp_path / 'wt-a'}" in p.stdout  # the worktree, not the repo
        assert f"wt={repo}" not in p.stdout
        assert "issue=999" in p.stdout
        assert f"pid={CLAIM_PID}" in p.stdout

    def test_branchless_claim_overlaps_on_its_real_worktree(self, tmp_path: Path) -> None:
        """The field shift corrupted overlap detection, not only the display.

        A registered role sits in the claim's actual worktree. Fixed: the claim's
        worktree field holds that path, so the pair collides and WARNS. Broken:
        the field held the repo root instead, which is neither equal to nor
        nested under the role's cwd, so no warning was produced - this assertion
        fails against tab-delimited records.
        """
        repo = _claim_repo(tmp_path, branch=None)
        self._register_orchestrator(tmp_path, repo)
        _run(tmp_path, "register", "A", "--wave", "w", "--socket", "uds:/tmp/a.sock",
             "--cwd", str(tmp_path / "wt-a"), "--repo", str(repo),
             "--issue", "1", "--branch", "b1", pid="101", session="s1")
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:101:{CLAIM_PID}")
        assert "WARNING" in p.stdout
        assert "same/nested worktrees" in p.stdout

    def test_empty_trailing_address_does_not_shift_earlier_fields(self, tmp_path: Path) -> None:
        """Empty TRAILING field - the COMMON case, not an edge one.

        An unregistered claim usually has no observed address. The render path
        masks this on its own (``${C_ADDR:-no observed address}`` prints the same
        whether the field is empty or shifted away), so this asserts the fields
        BEFORE it, which is where a collapse would show.
        """
        repo = _claim_repo(tmp_path, branch="issue-999-alpha")
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
        assert "no observed address" in p.stdout
        assert "branch=issue-999-alpha" in p.stdout
        assert f"wt={tmp_path / 'wt-a'}" in p.stdout

    def test_lock_reason_missing_session_still_parses(self, tmp_path: Path) -> None:
        """The other empty-middle producer: a hand-written lock reason.

        A non-flow worktree locked by hand is exactly the irregular claim #687
        exists to see, and it need not carry every key.
        """
        repo = _claim_repo(
            tmp_path,
            reason=f"flow-claim issue=555 pid={CLAIM_PID} host={HOST} ts=1700000000",
        )
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", live=f"100:{CLAIM_PID}")
        assert "issue=555" in p.stdout
        assert f"pid={CLAIM_PID}" in p.stdout
        assert f"wt={tmp_path / 'wt-a'}" in p.stdout

    def test_json_fields_are_not_shifted_for_a_branchless_claim(self, tmp_path: Path) -> None:
        """The same corruption reached --json consumers, not just the roster."""
        repo = _claim_repo(tmp_path, branch=None)
        self._register_orchestrator(tmp_path, repo)
        p = _run(tmp_path, "list", "--wave", "w", "--json", live=f"100:{CLAIM_PID}")
        claim = _json_payload(p)["unregistered_claims"][0]
        assert claim["issue"] == "999"
        assert claim["pid"] == CLAIM_PID
        assert claim["branch"] == ""
        assert claim["worktree"] == str(tmp_path / "wt-a")
        assert claim["repo"] == str(repo)
        assert claim["address"] is None


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


@requires_tools
class TestWavePolicyDeclaration:
    """The wave-level policy tier (issue #699).

    Declared ONCE by the orchestrator and inherited by every role. ``set``
    MERGES, so amending one field is a one-flag call; every set bumps ``rev``.
    """

    def _set(self, tmp: Path, *args: str, **kw) -> subprocess.CompletedProcess[str]:
        return _run(tmp, "policy", "set", "--wave", "cpp", *args, **kw)

    def test_show_on_an_undeclared_wave_is_a_state_not_an_error(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "policy", "show", "--wave", "cpp")
        assert _verdict(p) == "policy_absent"
        assert _detail(p, "FLOW_WAVE_POLICY") == "absent"
        assert _detail(p, "FLOW_WAVE_POLICY_REV") == "0"
        # A new verdict must never become a new exit code (#674) - a
        # `set -euo pipefail` caller must not abort on a wave that simply has
        # not declared its policy yet.
        assert p.returncode == 0

    def test_set_records_every_field_and_starts_at_rev_1(self, tmp_path: Path) -> None:
        p = self._set(
            tmp_path,
            "--driver", "flow:auto",
            "--authority", "implement",
            "--authority-model", "orchestrator-only",
            "--gate", "stop at Step 3; --yes forbidden",
            "--ledger", "delivered / in-scope / residual",
            "--merge-authority", "worker",
            "--deploy-policy", "woodpecker-only",
            "--repo", "/tmp/repo",
        )
        assert _verdict(p) == "policy_set"
        assert _detail(p, "FLOW_WAVE_POLICY") == "declared"
        assert _detail(p, "FLOW_WAVE_POLICY_REV") == "1"
        assert _detail(p, "FLOW_WAVE_POLICY_AUTHORITY") == "implement"
        assert _detail(p, "FLOW_WAVE_POLICY_AUTHORITY_MODEL") == "orchestrator-only"
        assert _detail(p, "FLOW_WAVE_POLICY_DRIVER") == "flow:auto"
        assert _detail(p, "FLOW_WAVE_POLICY_GATE") == "stop at Step 3; --yes forbidden"
        assert _detail(p, "FLOW_WAVE_POLICY_LEDGER") == "delivered / in-scope / residual"
        assert _detail(p, "FLOW_WAVE_POLICY_MERGE_AUTHORITY") == "worker"
        assert _detail(p, "FLOW_WAVE_POLICY_DEPLOY") == "woodpecker-only"
        assert _detail(p, "FLOW_WAVE_POLICY_REPO") == "/tmp/repo"

    def test_amending_one_field_keeps_the_rest_and_bumps_the_rev(self, tmp_path: Path) -> None:
        """The merge is the point: restating a whole policy is how a field
        gets silently dropped."""
        self._set(
            tmp_path,
            "--driver", "flow:auto",
            "--authority", "implement",
            "--ledger", "delivered / in-scope / residual",
        )
        p = self._set(tmp_path, "--authority", "file-issues-only")
        assert _detail(p, "FLOW_WAVE_POLICY_AUTHORITY") == "file-issues-only"
        assert _detail(p, "FLOW_WAVE_POLICY_DRIVER") == "flow:auto"
        assert _detail(p, "FLOW_WAVE_POLICY_LEDGER") == "delivered / in-scope / residual"
        assert _detail(p, "FLOW_WAVE_POLICY_REV") == "2"

    def test_policy_survives_the_jq_update_that_silently_deleted_it(self, tmp_path: Path) -> None:
        """Regression pin for the jq-1.6 trap this was written against.

        A ``?`` anywhere inside a ``|=`` body makes jq evaluate the update as a
        backtracking path expression, and ``_modify`` then DELETES the key it was
        told to update - exit 0, no stderr, policy gone. The failure is invisible
        from the verdict alone, so assert the STORED object, not the message.
        """
        self._set(tmp_path, "--authority", "implement", "--driver", "flow:auto")
        stored = _registry_json(tmp_path)["cpp"]["policy"]
        assert stored["authority"] == "implement"
        assert stored["driver"] == "flow:auto"
        assert stored["rev"] == 1
        assert stored["declared_pid"] == SELF_PID

    def test_bad_authority_enum_is_a_usage_error(self, tmp_path: Path) -> None:
        """A typo stored verbatim reads as declared and answers 'may this wave
        write code?' with garbage - worse than no policy at all."""
        p = self._set(tmp_path, "--authority", "impelment")
        assert p.returncode == 2
        assert "file-issues-only" in p.stderr
        # Validation happens BEFORE any write, so the registry is untouched -
        # a rejected policy must not half-land.
        registry = tmp_path / "reg" / "registry.json"
        assert not registry.exists() or "policy" not in _registry_json(tmp_path).get("cpp", {})

    def test_bad_authority_model_enum_is_a_usage_error(self, tmp_path: Path) -> None:
        p = self._set(tmp_path, "--authority-model", "everyone")
        assert p.returncode == 2
        assert "orchestrator-only" in p.stderr

    def test_free_text_fields_are_not_validated(self, tmp_path: Path) -> None:
        """Only the two consequential enums are checked; the rest are read by
        humans and the wording IS the content."""
        p = self._set(tmp_path, "--gate", "whatever the reviewer says on Tuesdays")
        assert _verdict(p) == "policy_set"

    def test_set_with_no_field_is_a_usage_error(self, tmp_path: Path) -> None:
        p = self._set(tmp_path)
        assert p.returncode == 2

    def test_unknown_subverb_is_a_usage_error(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "policy", "reset", "--wave", "cpp")
        assert p.returncode == 2

    def test_show_json_emits_the_object(self, tmp_path: Path) -> None:
        self._set(tmp_path, "--authority", "implement")
        p = _run(tmp_path, "policy", "show", "--wave", "cpp", "--json")
        assert _json_payload(p)["authority"] == "implement"

    def test_policy_is_wave_namespaced(self, tmp_path: Path) -> None:
        self._set(tmp_path, "--authority", "implement")
        p = _run(tmp_path, "policy", "show", "--wave", "other")
        assert _verdict(p) == "policy_absent"


@requires_tools
class TestPolicyIsReadBack:
    """The anti-decoration contract (issue #699).

    The issue's own load-bearing caveat is that a declared policy nobody reads
    is decoration, and its broken version is indistinguishable from its working
    one. Each test below pins one named reader.
    """

    def _declare(self, tmp: Path) -> None:
        _run(
            tmp, "policy", "set", "--wave", "cpp",
            "--authority", "implement",
            "--gate", "stop at Step 3",
            "--ledger", "delivered / in-scope / residual",
        )

    def test_register_reprints_the_policy_as_the_re_brief(self, tmp_path: Path) -> None:
        """Reader 1: re-registering recovers the PROTOCOL, not just the address.

        This is the mechanic the whole issue is built around - a `/clear`ed
        worker's brief has to come from somewhere that survived the clear.
        """
        self._declare(tmp_path)
        p = _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        assert _detail(p, "FLOW_WAVE_POLICY") == "declared"
        assert _detail(p, "FLOW_WAVE_POLICY_AUTHORITY") == "implement"
        assert "delivered / in-scope / residual" in p.stdout
        assert "stop at Step 3" in p.stdout

    def test_register_into_a_policy_less_wave_says_so(self, tmp_path: Path) -> None:
        """Reader 2: implementation authority is visible AT REGISTRATION rather
        than after a user round-trip - the #699 item-3 failure."""
        p = _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        assert _detail(p, "FLOW_WAVE_POLICY") == "absent"
        assert "NO declared policy" in p.stderr
        assert _verdict(p) == "registered"  # advisory, never a refusal

    def test_a_role_briefed_on_a_superseded_rev_reads_stale(self, tmp_path: Path) -> None:
        """Reader 3: an amendment nobody re-read is the drift a declared-but-
        unread field would hide."""
        self._declare(tmp_path)
        r = _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        assert _detail(r, "FLOW_WAVE_BRIEF") == "current"
        _run(tmp_path, "policy", "set", "--wave", "cpp", "--authority", "file-issues-only")
        p = _run(tmp_path, "get", "1", "--wave", "cpp")
        assert _detail(p, "FLOW_WAVE_BRIEF") == "stale"
        assert _detail(p, "FLOW_WAVE_BRIEFED_REV") == "1"
        assert _detail(p, "FLOW_WAVE_POLICY_REV") == "2"
        assert "superseded" in p.stderr

    def test_re_registering_takes_the_re_brief_and_clears_stale(self, tmp_path: Path) -> None:
        self._declare(tmp_path)
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        _run(tmp_path, "policy", "set", "--wave", "cpp", "--authority", "file-issues-only")
        p = _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        assert _detail(p, "FLOW_WAVE_BRIEF") == "current"
        assert _detail(p, "FLOW_WAVE_BRIEFED_REV") == "2"

    def test_list_names_live_roles_on_a_superseded_rev(self, tmp_path: Path) -> None:
        self._declare(tmp_path)
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        _run(tmp_path, "policy", "set", "--wave", "cpp", "--authority", "file-issues-only")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert "brief=STALE" in p.stdout
        assert "BRIEF:" in p.stdout

    def test_stale_brief_is_not_reported_for_dead_roles(self, tmp_path: Path) -> None:
        """A stale entry is not running on anything, so calling its brief
        superseded is noise on a row nobody will re-brief."""
        self._declare(tmp_path)
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        _run(tmp_path, "policy", "set", "--wave", "cpp", "--authority", "file-issues-only")
        p = _run(tmp_path, "list", "--wave", "cpp", live="")
        assert "brief=STALE" not in p.stdout

    def test_policy_set_names_the_roles_it_just_superseded(self, tmp_path: Path) -> None:
        """The cheapest moment to say a brief went stale is when it happens -
        the orchestrator is right there."""
        self._declare(tmp_path)
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        p = _run(
            tmp_path, "policy", "set", "--wave", "cpp", "--authority", "file-issues-only",
            live=SELF_PID,
        )
        assert "older policy rev" in p.stderr

    def test_list_renders_the_policy_header_and_its_absence(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert "NONE DECLARED" in p.stdout
        self._declare(tmp_path)
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert "wave policy (rev 1" in p.stdout


@requires_tools
class TestRoleLevelFacts:
    """The role-level tier (issue #699): model, permission mode, file lane,
    capacity - each answering a routing question the orchestrator otherwise had
    to ask, or could not see at all."""

    def test_facts_are_recorded_and_readable(self, tmp_path: Path) -> None:
        _run(
            tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock",
            "--model", "opus", "--permission-mode", "bypassPermissions",
            "--files", "a.py,b.py", "--capacity", "one-more",
        )
        p = _run(tmp_path, "get", "1", "--wave", "cpp")
        assert _detail(p, "FLOW_WAVE_MODEL") == "opus"
        assert _detail(p, "FLOW_WAVE_PERMISSION_MODE") == "bypassPermissions"
        assert _detail(p, "FLOW_WAVE_FILES") == "a.py,b.py"
        assert _detail(p, "FLOW_WAVE_CAPACITY") == "one-more"

    def test_omitted_facts_survive_the_cheap_re_brief(self, tmp_path: Path) -> None:
        """Re-registering is the documented re-brief (#670). Blanking a granted
        file lane because a compacted worker re-read the protocol would delete
        the very thing overlap detection reads."""
        _run(
            tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock",
            "--model", "opus", "--files", "a.py",
        )
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        entry = _registry_json(tmp_path)["cpp"]["roles"]["1"]
        assert entry["files"] == "a.py"
        assert entry["model"] == "opus"

    def test_an_explicit_empty_value_clears_a_fact(self, tmp_path: Path) -> None:
        """The flag was given, so intent is unambiguous."""
        _run(
            tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock",
            "--files", "a.py",
        )
        _run(
            tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock",
            "--files", "",
        )
        assert _registry_json(tmp_path)["cpp"]["roles"]["1"]["files"] == ""

    def test_undeclared_facts_do_not_appear_in_the_roster(self, tmp_path: Path) -> None:
        """A wave that uses none of this reads exactly as it did before."""
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert "files=" not in p.stdout
        assert "model=" not in p.stdout
        assert "perm=" not in p.stdout


@requires_tools
class TestFileLaneOverlap:
    """Declared file lanes participate in overlap detection (issue #699).

    Every real collision in the reference wave was file-level, and `list` warned
    only on repo/issue/branch/worktree.
    """

    def _pair(self, tmp: Path, files_a: str, files_b: str, repo_b: str = "/repo") -> None:
        _run(
            tmp, "register", "A", "--wave", "cpp", "--socket", "uds:/tmp/a.sock",
            "--repo", "/repo", "--issue", "1", "--branch", "issue-1-a",
            "--cwd", "/wt/a", "--files", files_a,
        )
        _run(
            tmp, "register", "B", "--wave", "cpp", "--socket", "uds:/tmp/b.sock",
            "--repo", repo_b, "--issue", "2", "--branch", "issue-2-b",
            "--cwd", "/wt/b", "--files", files_b,
            pid=OTHER_PID, session=OTHER_SESSION,
        )

    def test_shared_path_warns(self, tmp_path: Path) -> None:
        self._pair(tmp_path, "scripts/x.sh,docs/y.md", "docs/y.md,scripts/z.sh")
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" in p.stdout
        assert "docs/y.md" in p.stdout

    def test_disjoint_lanes_stay_at_the_info_level(self, tmp_path: Path) -> None:
        """A warning that fires on the normal case trains everyone to ignore
        it - the #683 rule, applied to the new arm."""
        self._pair(tmp_path, "scripts/x.sh", "docs/y.md")
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" not in p.stdout
        assert "share repo" in p.stdout

    def test_whitespace_around_a_declared_path_still_matches(self, tmp_path: Path) -> None:
        self._pair(tmp_path, "docs/y.md, scripts/x.sh", " docs/y.md ")
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" in p.stdout

    def test_a_shared_path_in_DIFFERENT_repos_is_not_a_collision(self, tmp_path: Path) -> None:
        """Same relative path in two repos is two different files."""
        self._pair(tmp_path, "docs/y.md", "docs/y.md", repo_b="/other-repo")
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" not in p.stdout

    def test_a_declared_directory_contains_the_paths_under_it(self, tmp_path: Path) -> None:
        """REVERSED BY #985, deliberately, and the intent below is unchanged.

        This asserted that `docs/` does NOT collide with `docs/y.md`, on the
        grounds that a guessing comparison invents collisions nobody declared.
        That grounds is right about GUESSING and wrong about a declared
        DIRECTORY: `docs/` contains `docs/y.md` by definition, and that is what
        declaring a directory means rather than an inference about intent.

        It stopped being hypothetical - a role declared the bare `codex/skills`
        and thereby claimed three other roles' live mirror trees while this
        predicate reported no overlap at all. The sibling test below still pins
        the original intent: prefix GUESSING remains refused.

        Reversal trigger, recorded beside the predicate too: if containment
        warnings fire on pairs the roles consider disjoint, revert to exact-match
        and record the directory case as known-unhandled.
        """
        self._pair(tmp_path, "docs/", "docs/y.md")
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" in p.stdout, p.stdout

    def test_comparison_is_still_not_prefix_guessing(self, tmp_path: Path) -> None:
        """The half of the original rule that #985 did NOT change.

        Containment is tested against a separator, so a path that merely SHARES A
        PREFIX is not contained: `docs/foo` does not contain `docs/foobar`. This
        is the case the original warning existed to avoid, and it still holds.
        """
        self._pair(tmp_path, "docs/foo", "docs/foobar")
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" not in p.stdout, p.stdout

    def test_a_stronger_lane_signal_still_wins_the_precedence(self, tmp_path: Path) -> None:
        """A shared branch says more about the pair than a shared file, and the
        file arm must not mask it."""
        _run(
            tmp_path, "register", "A", "--wave", "cpp", "--socket", "uds:/tmp/a.sock",
            "--repo", "/repo", "--branch", "shared", "--cwd", "/wt/a", "--files", "x.py",
        )
        _run(
            tmp_path, "register", "B", "--wave", "cpp", "--socket", "uds:/tmp/b.sock",
            "--repo", "/repo", "--branch", "shared", "--cwd", "/wt/b", "--files", "x.py",
            pid=OTHER_PID, session=OTHER_SESSION,
        )
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "both claim branch 'shared'" in p.stdout
        assert "overlapping FILE LANES" not in p.stdout

    def test_a_declared_file_lane_lapses_the_lane_less_exemption(self, tmp_path: Path) -> None:
        """#683 exempts roles that declared NOTHING to collide over. A granted
        file lane is the most collision-prone thing there is, so it counts as a
        lane exactly as a declared branch does.

        Each role gets its OWN shared-parent cwd (two checkouts apiece, neither
        nesting the other), so the exemption's cwd condition is satisfied for
        both while the same/nested-worktree arm cannot fire and mask the result.
        """
        parents = []
        for name in ("pa", "pb"):
            parent = tmp_path / name
            (parent / "one" / ".git").mkdir(parents=True)
            (parent / "two" / ".git").mkdir(parents=True)
            parents.append(parent)
        for (role, pid, session), parent in zip(
            (("A", SELF_PID, SELF_SESSION), ("B", OTHER_PID, OTHER_SESSION)), parents
        ):
            _run(
                tmp_path, "register", role, "--wave", "cpp",
                "--socket", f"uds:/tmp/{role}.sock",
                "--repo", "/repo", "--cwd", str(parent), "--files", "shared.py",
                pid=pid, session=session,
            )
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" in p.stdout
        assert "overlap checks skipped" not in p.stdout

    def test_a_lane_less_role_with_no_files_is_still_exempt(self, tmp_path: Path) -> None:
        """The negative control for the clause above: without a declared file
        lane the #683 exemption must still apply, or this change would have
        widened it into the false warnings #683 removed."""
        parents = []
        for name in ("pa", "pb"):
            parent = tmp_path / name
            (parent / "one" / ".git").mkdir(parents=True)
            (parent / "two" / ".git").mkdir(parents=True)
            parents.append(parent)
        for (role, pid, session), parent in zip(
            (("A", SELF_PID, SELF_SESSION), ("B", OTHER_PID, OTHER_SESSION)), parents
        ):
            _run(
                tmp_path, "register", role, "--wave", "cpp",
                "--socket", f"uds:/tmp/{role}.sock",
                "--repo", "/repo", "--cwd", str(parent),
                pid=pid, session=session,
            )
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlap checks skipped" in p.stdout


@requires_tools
class TestUnscopedLaneIsReportedUnknown:
    """A lane that cannot be CHECKED is never rendered as clean (issue #800).

    The same-issue and FILE-LANE arms compare same-repo pairs, so a live role
    holding a declared lane with an EMPTY repo matches nothing and drops out of
    the report in silence. A re-register that omits ``--repo`` CLEARS it while
    ``--files`` is PRESERVED, so extending a lane - the documented cheap
    re-brief - was the act that stopped the lane being checked. Two workers held
    the same two files for ~40 minutes against a roster that read clean.

    The branch and same/nested-worktree arms are repo-independent and must stay
    exactly as they were; the negative controls below pin that.
    """

    def _overlapping_pair(self, tmp: Path, files: str = "core/x.py,core/tests/test_x.py") -> None:
        """The issue's own reproduction: two live roles, one repo, one lane.

        The repo value must be a REAL directory (issue #891): lane_unscoped()
        now also flags a non-resolving repo as unchecked, so a bogus fixed
        string like "/repo" would make both roles read UNSCOPED here even
        though this class is exercising report_overlap's STRING comparison,
        which never needed a real directory and is untouched by #891.
        """
        _run(
            tmp, "register", "worker-A", "--wave", "cpp", "--socket", "uds:/tmp/a.sock",
            "--repo", str(tmp), "--issue", "1", "--branch", "issue-1-a",
            "--cwd", "/wt/a", "--files", files,
        )
        _run(
            tmp, "register", "worker-B", "--wave", "cpp", "--socket", "uds:/tmp/b.sock",
            "--repo", str(tmp), "--issue", "2", "--branch", "issue-2-b",
            "--cwd", "/wt/b", "--files", files,
            pid=OTHER_PID, session=OTHER_SESSION,
        )

    def test_the_reported_repro_in_both_directions(self, tmp_path: Path) -> None:
        """The positive control the reporter ran, kept as a control.

        A fix that reported UNSCOPED unconditionally would look identical on the
        broken direction alone, so the direction that must still WARN is asserted
        in the same test as the direction that must not read clean.
        """
        self._overlapping_pair(tmp_path)

        # Direction 1 - both scoped: the real warning fires, nothing is unknown.
        scoped = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" in scoped.stdout
        assert _detail(scoped, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"
        assert "UNKNOWN: overlap NOT computed" not in scoped.stdout

        # Direction 2 - worker-B re-registers passing ONLY --files, the lane
        # extension. `files` survives; `repo` is rewritten to empty.
        _run(
            tmp_path, "register", "worker-B", "--wave", "cpp",
            "--socket", "uds:/tmp/b.sock", "--files", "core/x.py,core/tests/test_x.py,core/new.py",
            pid=OTHER_PID, session=OTHER_SESSION,
        )
        assert _registry_json(tmp_path)["cpp"]["roles"]["worker-B"]["repo"] == ""
        assert _registry_json(tmp_path)["cpp"]["roles"]["worker-B"]["files"]

        unscoped = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert _detail(unscoped, "FLOW_WAVE_OVERLAP_UNSCOPED") == "1"
        assert "UNKNOWN: overlap NOT computed" in unscoped.stdout
        assert "worker-B" in unscoped.stdout.split("UNKNOWN: overlap NOT computed")[1]
        assert "UNCHECKED, not clean" in unscoped.stdout
        assert "CANNOT be read as clean" in unscoped.stderr

    def test_registration_says_so_at_the_moment_it_records_the_lane(
        self, tmp_path: Path
    ) -> None:
        """Told to the worker who can fix it, not only to whoever reads `list`.

        Same placement reasoning as the #683 shared-parent advisory: one
        re-register fixes it, and the alternative is an orchestrator never
        noticing because there is nothing to notice.
        """
        self._overlapping_pair(tmp_path)
        p = _run(
            tmp_path, "register", "worker-B", "--wave", "cpp",
            "--socket", "uds:/tmp/b.sock", "--files", "core/x.py",
            pid=OTHER_PID, session=OTHER_SESSION,
        )
        assert "overlap detection is UNSCOPED for it" in p.stderr
        assert "--repo is REWRITTEN by every re-register" in p.stderr
        assert _detail(p, "FLOW_WAVE_LANE_SCOPED") == "no"
        assert _verdict(p) == "updated"
        assert p.returncode == 0

    def test_a_declared_repo_is_never_flagged(self, tmp_path: Path) -> None:
        """Negative control: the normal, correct registration stays silent."""
        self._overlapping_pair(tmp_path)
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert _detail(p, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"
        assert "UNKNOWN: overlap NOT computed" not in p.stdout
        assert "CANNOT be read as clean" not in p.stderr

    def test_a_lane_less_role_with_no_repo_is_not_flagged(self, tmp_path: Path) -> None:
        """This must not widen into the false warnings #683 removed.

        A role that declared NOTHING has no lane to leave unscoped, so it stays
        in the #683 lane-less EXEMPTION - announced as skipped - rather than
        being re-reported as an unchecked lane. Same shared-parent cwd shape as
        ``TestFileLaneOverlap``'s exemption controls (each role gets its own
        parent holding two checkouts, so neither nests the other), with the
        --repo deliberately dropped: that is the state under test.
        """
        parents = []
        for name in ("pa", "pb"):
            parent = tmp_path / name
            (parent / "one" / ".git").mkdir(parents=True)
            (parent / "two" / ".git").mkdir(parents=True)
            parents.append(parent)
        for (role, pid, session), parent in zip(
            (("worker-A", SELF_PID, SELF_SESSION), ("worker-B", OTHER_PID, OTHER_SESSION)),
            parents,
        ):
            _run(
                tmp_path, "register", role, "--wave", "cpp",
                "--socket", f"uds:/tmp/{role}.sock", "--cwd", str(parent),
                pid=pid, session=session,
            )
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert _detail(p, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"
        assert "UNKNOWN: overlap NOT computed" not in p.stdout
        assert "overlap checks skipped" in p.stdout

    def test_the_orchestrator_is_not_flagged(self, tmp_path: Path) -> None:
        """It is exempt from the pairwise checks unconditionally, so it has no
        scoping to lose - saying its lane is unscoped would be a fact about
        nothing, and a warning nobody can act on is #674's failure."""
        p = _run(
            tmp_path, "register", "orchestrator", "--wave", "cpp",
            "--socket", "uds:/tmp/o.sock", "--files", "docs/plan.md",
        )
        assert _detail(p, "FLOW_WAVE_LANE_SCOPED") == "-"
        assert "UNSCOPED" not in p.stderr
        lst = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert _detail(lst, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"

    def test_the_same_issue_arm_is_covered_too(self, tmp_path: Path) -> None:
        """The issue reported the FILE-LANE arm; the same-issue arm has the same
        guard (`same repo AND same issue`) and the same hole, so a role claiming
        an issue with no repo silently leaves the #597 two-sessions-on-one-issue
        check as well."""
        p = _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock", "--issue", "42",
        )
        assert _detail(p, "FLOW_WAVE_LANE_SCOPED") == "no"
        lst = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert _detail(lst, "FLOW_WAVE_OVERLAP_UNSCOPED") == "1"

    def test_get_answers_the_same_question_per_role(self, tmp_path: Path) -> None:
        """`get` is the scripting contract: FLOW_WAVE_REPO and FLOW_WAVE_FILES
        answer this only for a caller who already knows the same-repo scoping
        rule, so the answer is reported rather than left to be re-derived."""
        _run(
            tmp_path, "register", "scoped", "--wave", "cpp", "--socket", "uds:/tmp/s.sock",
            "--repo", str(tmp_path), "--files", "a.py",
        )
        _run(tmp_path, "register", "bare", "--wave", "cpp", "--socket", "uds:/tmp/n.sock")
        _run(
            tmp_path, "register", "unscoped", "--wave", "cpp", "--socket", "uds:/tmp/u.sock",
            "--files", "a.py",
        )
        assert _detail(_run(tmp_path, "get", "scoped", "--wave", "cpp"), "FLOW_WAVE_LANE_SCOPED") == "yes"
        assert _detail(_run(tmp_path, "get", "bare", "--wave", "cpp"), "FLOW_WAVE_LANE_SCOPED") == "-"
        assert _detail(_run(tmp_path, "get", "unscoped", "--wave", "cpp"), "FLOW_WAVE_LANE_SCOPED") == "no"

    def test_the_count_is_reported_on_every_render_path(self, tmp_path: Path) -> None:
        """An instrument whose blind spot is visible in one output mode and
        invisible in another is the same failure one level up, so the marker is
        emitted as a VALUE on all three `list` exits - including zero, and
        including the empty roster, so a consumer can tell 'none' from 'this
        call does not report it'."""
        empty = _run(tmp_path, "list", "--wave", "nosuch", live=SELF_PID)
        assert _detail(empty, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"

        _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock", "--files", "a.py",
        )
        text = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        js = _run(tmp_path, "list", "--wave", "cpp", "--json", live=SELF_PID)
        assert _detail(text, "FLOW_WAVE_OVERLAP_UNSCOPED") == "1"
        assert _detail(js, "FLOW_WAVE_OVERLAP_UNSCOPED") == "1"
        # --json stdout stays parseable: the marker is a trailing contract line.
        assert "worker-A" in _json_payload(js)

    def test_a_dead_role_is_not_counted(self, tmp_path: Path) -> None:
        """Overlap detection is LIVE-only, so a stale entry's unscoped lane is
        not a gap in a check that was never going to run for it."""
        _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock", "--files", "a.py",
        )
        p = _run(tmp_path, "list", "--wave", "cpp", live="")
        assert _detail(p, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"

    def test_a_new_verdict_is_not_a_new_exit_code(self, tmp_path: Path) -> None:
        """The suite-wide rule (#674): advisories add lines, never exit codes -
        a `set -euo pipefail` caller would abort mid-script otherwise. An
        UNSCOPED roster is loud on stdout and stderr and still exits 0."""
        _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock", "--files", "a.py",
        )
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert p.returncode == 0
        assert _verdict(p) == "listed"
        assert "CANNOT be read as clean" in p.stderr


@requires_tools
class TestNonResolvingRepoIsUnscoped:
    """A --repo that does not resolve to a directory is as unchecked as an
    EMPTY one, and the registry stops depending on the READER's cwd (#891).

    #800 only covered an empty repo. `report_overlap`'s exact-STRING
    comparison never needed a real directory and stays untouched; the gap
    was `collect_unregistered_claims`, which requires `[ -d "$repo" ]` and
    silently skipped anything that failed it - so a bare value like `kyle`
    satisfied the string comparison while going invisible to claim
    reconciliation, and the same stored value resolved differently depending
    on which directory the READER of `list` happened to be in.
    """

    def test_non_resolving_repo_is_unchecked_at_register(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "does-not-exist")
        p = _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock", "--repo", missing, "--files", "a.py",
        )
        assert _detail(p, "FLOW_WAVE_LANE_SCOPED") == "no"
        assert f"repo '{missing}' does not resolve to a directory" in p.stderr
        assert "but NO repo" not in p.stderr  # the empty-repo wording, not this one

    def test_non_resolving_repo_counts_toward_overlap_unscoped(self, tmp_path: Path) -> None:
        _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock",
            "--repo", str(tmp_path / "does-not-exist"), "--issue", "1",
        )
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert int(_detail(p, "FLOW_WAVE_OVERLAP_UNSCOPED")) >= 1

    def test_a_resolving_repo_is_not_flagged(self, tmp_path: Path) -> None:
        """Negative control: a repo that IS a real directory stays scoped."""
        p = _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock", "--repo", str(tmp_path), "--issue", "1",
        )
        assert _detail(p, "FLOW_WAVE_LANE_SCOPED") == "yes"
        lst = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert _detail(lst, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"

    def test_list_names_a_skipped_repo_and_counts_it_on_every_render_path(
        self, tmp_path: Path
    ) -> None:
        """The other half of the fix: claim reconciliation's OWN silent skip
        (`collect_unregistered_claims`'s `[ -d ]` gate) becomes visible,
        exactly the same convention as FLOW_WAVE_OVERLAP_UNSCOPED - reported
        as a value on every exit path, including zero, so 'none' is
        distinguishable from 'not reported' (test style matches
        TestUnscopedLaneIsReportedUnknown.test_the_count_is_reported_on_every_render_path)."""
        missing = str(tmp_path / "does-not-exist")

        empty = _run(tmp_path, "list", "--wave", "nosuch", live=SELF_PID)
        assert _detail(empty, "FLOW_WAVE_CLAIM_SCAN_SKIPPED") == "0"

        p = _run(tmp_path, "list", "--wave", "cpp", "--repo", missing, live=SELF_PID)
        assert f"repo '{missing}' does not resolve to a directory" in p.stderr
        assert int(_detail(p, "FLOW_WAVE_CLAIM_SCAN_SKIPPED")) >= 1

        js = _run(tmp_path, "list", "--wave", "cpp", "--json", "--repo", missing, live=SELF_PID)
        assert int(_detail(js, "FLOW_WAVE_CLAIM_SCAN_SKIPPED")) >= 1

    def test_a_scanned_repo_does_not_count_as_skipped(self, tmp_path: Path) -> None:
        """Negative control: a real directory is never reported as skipped."""
        p = _run(tmp_path, "list", "--wave", "cpp", "--repo", str(tmp_path), live=SELF_PID)
        assert _detail(p, "FLOW_WAVE_CLAIM_SCAN_SKIPPED") == "0"

    def test_repo_is_resolved_to_an_absolute_path_at_register(self, tmp_path: Path) -> None:
        """THE SHARP EDGE (issue #891's own headline): a bare/relative --repo
        resolves differently depending on which directory happens to read it
        later. `register` now resolves it to an absolute path ONCE, from the
        registering call's own cwd, so every later reader - regardless of
        its own cwd - evaluates the identical value.

        Same registry, same role, `list` run from two different directories:
        the answer must be IDENTICAL in both, never "depends on who asks".
        """
        (tmp_path / "myrepo").mkdir()
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        # Registered with a bare relative name, from a cwd where it resolves.
        reg = _run(
            tmp_path, "register", "worker-A", "--wave", "cpp",
            "--socket", "uds:/tmp/a.sock", "--repo", "myrepo", "--issue", "1",
            cwd=tmp_path,
        )
        assert _detail(reg, "FLOW_WAVE_LANE_SCOPED") == "yes"

        stored = _registry_json(tmp_path)["cpp"]["roles"]["worker-A"]["repo"]
        assert Path(stored).is_absolute()
        assert Path(stored) == tmp_path / "myrepo"

        # `list`, run from a cwd where the bare name "myrepo" does NOT exist,
        # must still read the role as scoped - the stored value no longer
        # depends on the reader's cwd.
        lst = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID, cwd=elsewhere)
        assert _detail(lst, "FLOW_WAVE_OVERLAP_UNSCOPED") == "0"


@requires_tools
class TestPolicyBackCompat:
    """A wave that never declares a policy behaves exactly as it did (#699)."""

    def test_list_json_has_no_policy_key_when_none_is_declared(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        p = _run(tmp_path, "list", "--wave", "cpp", "--json", live=SELF_PID)
        payload = _json_payload(p)
        assert "wave_policy" not in payload
        assert "1" in payload

    def test_list_json_gains_a_sibling_key_when_one_is(self, tmp_path: Path) -> None:
        """Roles stay top-level, exactly as #687 kept them - policy hangs
        beside them rather than nesting them."""
        _run(tmp_path, "policy", "set", "--wave", "cpp", "--authority", "implement")
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        payload = _json_payload(_run(tmp_path, "list", "--wave", "cpp", "--json", live=SELF_PID))
        assert payload["wave_policy"]["authority"] == "implement"
        assert payload["1"]["socket"] == "uds:/tmp/1.sock"

    def test_policy_lines_are_emitted_even_when_absent(self, tmp_path: Path) -> None:
        """A consumer must be able to tell 'no policy declared' from 'this call
        does not report policy' - a missing line answers neither."""
        _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        for args in (["list", "--wave", "cpp"], ["get", "1", "--wave", "cpp"]):
            p = _run(tmp_path, *args, live=SELF_PID)
            assert _detail(p, "FLOW_WAVE_POLICY") == "absent"

    def test_registering_without_new_flags_keeps_the_old_verdicts(self, tmp_path: Path) -> None:
        p = _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        assert _verdict(p) == "registered"
        assert p.returncode == 0
        p = _run(tmp_path, "register", "1", "--wave", "cpp", "--socket", "uds:/tmp/1.sock")
        assert _verdict(p) == "updated"


# --------------------------------------------------------------------------
# The watch column (issue #778)
# --------------------------------------------------------------------------

MAILBOX = ROOT / "scripts" / "flow-wave-mailbox.sh"

# The #778 join drives the sibling mailbox helper as a real subprocess, so it
# carries the same guard the rest of the suite does.
requires_mailbox = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="requires bash and jq on PATH",
)


def _mailbox(tmp: Path, *args: str, now: str = "1700000000"):
    """Drive the sibling mailbox helper against the SAME wave root the registry
    uses, which is what makes the two co-locate in real deployments too.
    """
    env = os.environ.copy()
    env.update(
        {
            "FLOW_WAVE_REGISTRY_DIR": str(tmp / "reg"),
            "FLOW_WAVE_NOW": now,
        }
    )
    env.pop("FLOW_WAVE_MAILBOX_DIR", None)
    return subprocess.run(
        ["bash", str(MAILBOX), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=60,
    )


def _live_mailbox_watcher(tmp: Path, role: str, wave: str, timeout: int = 30):
    """Start a REAL blocking mailbox watcher on the registry's wave root.

    Since #801 the watch state is fused from the live process table, so a
    stamped heartbeat no longer produces `armed` - the roster's positive control
    needs an actual process behind it.
    """
    env = os.environ.copy()
    env.update({"FLOW_WAVE_REGISTRY_DIR": str(tmp / "reg")})
    env.pop("FLOW_WAVE_MAILBOX_DIR", None)
    env.pop("FLOW_WAVE_NOW", None)
    proc = subprocess.Popen(
        ["bash", str(MAILBOX), "watch", "--role", role, "--wave", wave,
         "--timeout", str(timeout), "--interval", "1", "--consume"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    wf = tmp / "reg" / wave / f".watch-{role}"
    deadline = time.time() + 15
    while not wf.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert wf.exists(), "mailbox watch never armed"
    # A watch fires and EXITS on unread mail, so arming it against a box that
    # already has some leaves a heartbeat and no process - which is the very
    # state these tests use as the negative case. Assert the positive control is
    # genuinely live, or it would quietly assert nothing.
    assert proc.poll() is None, "watch exited immediately (unread mail in the box?)"
    return proc


def _row(proc: subprocess.CompletedProcess[str], role: str) -> str:
    """The roster line for one role, or '' when it is absent."""
    for line in proc.stdout.splitlines():
        if line.strip().startswith(f"{role} -> "):
            return line
    return ""


@requires_mailbox
class TestWatchColumn:
    """A role could be `live`, address-`verified` and `brief=current` and still
    be completely DEAF (#778): arming the mailbox watch was the one element of
    participation that left no trace in the roster when it was missing. On
    2026-09-05 a worker sat that way for over an hour with a six-issue
    assignment unread, and both sides looked healthy.
    """

    def test_never_armed_reads_absent_with_the_never_read_marker(
        self, tmp_path: Path
    ) -> None:
        """The exact observed failure, rendered in one look."""
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane: #1 #2")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        row = _row(p, "worker-H")
        assert "watch=ABSENT" in row
        assert "unread=1" in row
        assert "** NEVER READ **" in row
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "1"
        assert _detail(p, "FLOW_WAVE_UNREAD") == "1"

    def test_armed_watch_reads_armed_and_warns_about_nothing(self, tmp_path: Path) -> None:
        """The positive control for #801 at the roster surface.

        A live watcher must still render `armed` and raise nothing - otherwise a
        fix that reported DEAD unconditionally would pass every other case here.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        # No mail is sent first: a watch fires and EXITS on unread mail, so
        # seeding the box would leave a heartbeat with no process - the DEAD
        # case, not the armed one this test exists to prove.
        watcher = _live_mailbox_watcher(tmp_path, "worker-H", "cpp")
        try:
            p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
            assert "watch=armed" in _row(p, "worker-H")
            assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "0"
            assert "WATCH: live role(s)" not in p.stdout
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_a_watch_no_session_owns_reads_NO_WAKE_not_armed(self, tmp_path: Path) -> None:
        """#1228 at the roster: a role polled only by a process with no Claude
        Code session in its ancestry (a `supervise` daemon, or a watch whose
        session is gone) cannot be woken. Three waves read `watch=armed` over
        exactly this. The positive control is the armed test above, run with
        the same session hook so both sides answer the same lineage question.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        env = os.environ.copy()
        env.update({"FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg")})
        env.pop("FLOW_WAVE_MAILBOX_DIR", None)
        env.pop("FLOW_WAVE_NOW", None)
        # Backgrounded by an intermediate shell that exits at once, so the
        # kernel reparents it away from pytest - a real orphan, not a stub.
        out = subprocess.run(
            ["bash", "-c",
             'bash "$0" watch --role worker-H --wave cpp --timeout 60 --interval 1 --peek '
             '</dev/null >/dev/null 2>&1 & echo $!', str(MAILBOX)],
            capture_output=True, text=True, env=env, check=True, timeout=30,
        )
        orphan = int(out.stdout.strip())
        try:
            wf = tmp_path / "reg" / "cpp" / ".watch-worker-H"
            deadline = time.time() + 15
            while not wf.exists() and time.time() < deadline:
                time.sleep(0.05)
            assert wf.exists(), "orphan watch never armed"  # precondition
            session = {"FLOW_WAVE_SESSION_PIDS": str(os.getpid())}
            p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID, extra_env=session)
            row = _row(p, "worker-H")
            assert "watch=NO-WAKE(1 watchers, 0 session)" in row, row
            assert "watch=armed" not in row
            assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "1"
            j = _run(tmp_path, "list", "--wave", "cpp", "--json", live=SELF_PID, extra_env=session)
            watch = _json_payload(j)["worker-H"]["watch"]
            assert watch["state"] == "no-wake" and watch["session_watchers"] == 0
        finally:
            try:
                os.kill(orphan, 9)
            except OSError:
                pass

    def test_an_exited_watch_reads_DEAD_not_armed(self, tmp_path: Path) -> None:
        """The #801 regression at the surface that misled the orchestrator.

        A watch is one-shot, so this heartbeat - stamped 10s before the
        registry's pinned now - is what a role looks like moments after it
        delivered a message and exited. The roster rendered `watch=armed` for
        the whole 300s stale window; three workers were told they were fine.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        _mailbox(tmp_path, "watch", "--role", "worker-H", "--wave", "cpp",
                 "--timeout", "0", "--consume", now="1699999990")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        row = _row(p, "worker-H")
        assert "watch=DEAD(0 watchers)" in row
        assert "watch=armed" not in row
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "1"
        assert "worker-H(dead - last wake 10s ago, 0 watchers)" in p.stdout

    def test_a_decayed_heartbeat_behind_a_live_watcher_reads_stale_with_its_age(
        self, tmp_path: Path
    ) -> None:
        """`stale` narrowed under #801: it now means a watcher process EXISTS
        but has stopped refreshing - hung or stopped, a different repair from
        one that is simply gone. The age is still printed either way.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        watcher = _live_mailbox_watcher(tmp_path, "worker-H", "cpp")
        try:
            # A reader clock 42m ahead of the live watcher's real stamp ages it
            # past the threshold without stopping the process.
            future = str(int(time.time()) + 2520)
            p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID, now=future)
            assert "watch=stale(42m)" in _row(p, "worker-H")
            assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "1"
            assert "worker-H(stale 42m)" in p.stdout
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_an_unreadable_watcher_count_reads_UNKNOWN_never_clean(
        self, tmp_path: Path
    ) -> None:
        """The #800 convention, inherited: a watch that cannot be assessed is
        counted as deaf and named as UNKNOWN, never quietly rendered as armed.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        _mailbox(tmp_path, "watch", "--role", "worker-H", "--wave", "cpp",
                 "--timeout", "0", "--consume", now="1699999990")
        env_before = os.environ.get("FLOW_WAVE_WATCHER_SCAN")
        os.environ["FLOW_WAVE_WATCHER_SCAN"] = "none"
        try:
            p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        finally:
            if env_before is None:
                os.environ.pop("FLOW_WAVE_WATCHER_SCAN", None)
            else:
                os.environ["FLOW_WAVE_WATCHER_SCAN"] = env_before
        assert "watch=UNKNOWN" in _row(p, "worker-H")
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "1"
        assert "worker-H(UNKNOWN - watcher count unreadable)" in p.stdout

    def test_a_read_box_is_not_flagged_never_read(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        _mailbox(tmp_path, "read", "--role", "worker-H", "--wave", "cpp")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        row = _row(p, "worker-H")
        assert "** NEVER READ **" not in row
        assert "unread=" not in row
        assert _detail(p, "FLOW_WAVE_UNREAD") == "0"

    def test_dead_roles_are_not_flagged_deaf(self, tmp_path: Path) -> None:
        """A dead worker's watch is moot - calling it ABSENT is noise on a row
        nobody is going to re-arm, the same reasoning that scopes brief
        staleness to live roles.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        p = _run(tmp_path, "list", "--wave", "cpp", live="")  # nothing alive
        row = _row(p, "worker-H")
        assert "stale," in row  # precondition: the entry really is dead
        assert "watch=" not in row
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "0"

    def test_json_carries_watch_and_mailbox_objects(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        p = _run(tmp_path, "list", "--wave", "cpp", "--json", live=SELF_PID)
        entry = _json_payload(p)["worker-H"]
        # `watchers` joined the object in #801: the roster renders the fused
        # state, and a JSON consumer must be able to check what it rests on.
        # `session_watchers` joined in #1228: how many of those can WAKE anyone.
        assert entry["watch"] == {
            "state": "absent",
            "age_secs": None,
            "watchers": 0,
            "session_watchers": 0,
        }
        assert entry["mailbox"]["rev"] == 1
        # "cursor" retired in favor of "acked" (issue #815) - the read cursor
        # advanced as a side effect of printing output, which is the defect
        # #815 fixes; nothing has been explicitly acknowledged here yet.
        assert entry["mailbox"]["acked"] == 0
        assert entry["mailbox"]["unread"] == 1
        assert entry["mailbox"]["never_read"] is True
        assert entry["mailbox"]["last_delivery"] is not None

    def test_orchestrator_figures_aggregate_every_inbox(self, tmp_path: Path) -> None:
        """A worker reads one box; the orchestrator reads every inbox, so its
        unread count must be the SUM rather than whichever box sorted first.
        """
        _run(tmp_path, "register", "orchestrator", "--wave", "cpp", "--socket", "uds:/tmp/o.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "orchestrator", "--from", "a", "--body", "from a")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "orchestrator", "--from", "b", "--body", "from b")
        p = _run(tmp_path, "list", "--wave", "cpp", "--json", live=SELF_PID)
        assert _json_payload(p)["orchestrator"]["mailbox"]["unread"] == 2
        assert _detail(p, "FLOW_WAVE_UNREAD") == "2"


@requires_mailbox
class TestWatchColumnDoesNotCryWolf:
    """#674's rule, restated: a flag that fires on 100% of the fleet carries
    zero signal and buries the one case worth investigating. Watch state is a
    strong claim, so it renders ONLY where it means something.
    """

    def test_a_wave_that_never_uses_the_mailbox_renders_unchanged(
        self, tmp_path: Path
    ) -> None:
        """Otherwise every role in a mailbox-free wave would read ABSENT."""
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        row = _row(p, "worker-H")
        assert row  # precondition: the role really is on the roster
        assert "watch=" not in row
        assert "WATCH:" not in p.stdout
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "0"

    def test_a_mailbox_free_wave_emits_no_watch_keys_in_json(self, tmp_path: Path) -> None:
        """Byte-identical JSON to pre-#778, the promise #687 and #699 both made
        for their own sibling keys.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        p = _run(tmp_path, "list", "--wave", "cpp", "--json", live=SELF_PID)
        entry = _json_payload(p)["worker-H"]
        assert "watch" not in entry
        assert "mailbox" not in entry

    def test_a_missing_mailbox_sibling_fails_open(self, tmp_path: Path) -> None:
        """A broken mailbox must never break the roster - the same fail-open
        rule the mailbox itself applies to the #701 lexicon validator.
        """
        lone = tmp_path / "lone"
        lone.mkdir()
        solo = lone / "flow-wave-registry.sh"
        solo.write_text(REGISTRY.read_text())
        assert not (lone / "flow-wave-mailbox.sh").exists()  # precondition
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        env = os.environ.copy()
        env.update(
            {
                "CLAUDE_PID": SELF_PID,
                "CLAUDE_CODE_SESSION_ID": SELF_SESSION,
                "FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "reg"),
                "FLOW_WAVE_SOCK_DIR": str(tmp_path / "socks"),
                "FLOW_WAVE_HOST": HOST,
                "FLOW_WAVE_LIVE_PIDS": SELF_PID,
                "FLOW_WAVE_NOW": "1700000000",
            }
        )
        p = subprocess.run(
            ["bash", str(solo), "list", "--wave", "cpp"],
            capture_output=True, text=True, env=env, check=False,
        )
        assert p.returncode == 0
        assert _verdict(p) == "listed"
        assert "watch=" not in _row(p, "worker-H")
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "0"

    def test_contract_lines_are_emitted_even_with_no_mailbox(self, tmp_path: Path) -> None:
        """A consumer must be able to tell '0 deaf roles' from 'this call does
        not report deafness' - a missing line answers neither (#699's rule for
        the policy lines, applied to these).
        """
        p = _run(tmp_path, "list", "--wave", "empty-wave", live=SELF_PID)
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "0"
        assert _detail(p, "FLOW_WAVE_UNREAD") == "0"


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


# --------------------------------------------------------------------------- #
# #989 - merge starvation under branch protection strict:true
# --------------------------------------------------------------------------- #
#
# Every test below runs against FLOW_WAVE_REGISTRY_DIR under tmp_path and a
# throwaway wave name. The live wave's registry is the state this session's own
# addressability depends on; a test that wrote there would corrupt the wave in
# flight, so isolation is belt AND braces rather than either alone.


def _overtaken(tmp: Path, wave: str, role: str) -> int:
    data = json.loads((tmp / "reg" / "registry.json").read_text(encoding="utf-8"))
    return int(data[wave]["roles"][role].get("overtaken", 0))


@requires_tools
def test_a_pr_overtaken_four_times_counts_exactly_four(tmp_path: Path) -> None:
    """The FIRING case, and it must count rather than merely fire.

    The counter IS the instrument here, so a detector that fires correctly while
    miscounting is the one nobody can calibrate. Four base moves with an
    unchanged diff must read 4 - not "some", not saturated at 1.
    """
    for base in ("b1", "b2", "b3", "b4", "b5"):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "982", "--base", base, "--diff", "SAME")
    assert _overtaken(tmp_path, "zz", "w") == 4


@requires_tools
def test_a_changed_diff_is_review_not_starvation(tmp_path: Path) -> None:
    """Required non-firing control: overtaken four times, diff changed each time.

    That is a worker responding to review. A detector that counts it fires on
    ordinary traffic, and a starvation signal that lights up on every wave is
    the defect this feature exists to fix, one level up.
    """
    for i, base in enumerate(("c1", "c2", "c3", "c4", "c5")):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "700", "--base", base, "--diff", f"d{i}")
    assert _overtaken(tmp_path, "zz", "w") == 0


@requires_tools
def test_merges_in_readiness_order_report_no_starvation(tmp_path: Path) -> None:
    """Required non-firing control: no PR loses its base twice.

    One rebase is ordinary - somebody merged while you were verifying. The COUNT
    is still recorded, because it is data; the SIGNAL starts at two, which is
    why this wave reports no starvation while the row still shows what happened.
    """
    _run(tmp_path, "register", "a", "--wave", "zz", "--repo", "/tmp",
         "--pr", "801", "--base", "m0", "--diff", "x1")
    _run(tmp_path, "register", "b", "--wave", "zz", "--repo", "/tmp",
         "--pr", "802", "--base", "m0", "--diff", "y1")
    _run(tmp_path, "register", "a", "--wave", "zz", "--repo", "/tmp",
         "--pr", "801", "--base", "m1", "--diff", "x1")
    assert _overtaken(tmp_path, "zz", "a") == 1
    assert _overtaken(tmp_path, "zz", "b") == 0
    out = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    # The roles ARE live here, so the quiet verdict is caused by one-rebase
    # being below the threshold rather than by nothing being observable.
    assert "overtaken=1" in out.stdout, out.stdout
    assert "STARVATION:" not in out.stdout, out.stdout
    assert "FLOW_WAVE_STARVATION=0" in out.stdout, out.stdout


@requires_tools
def test_a_new_pr_number_resets_the_count(tmp_path: Path) -> None:
    """The count is a property of ONE pull request's queue position."""
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--pr", "900", "--base", "e1", "--diff", "z1")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--pr", "900", "--base", "e2", "--diff", "z1")
    assert _overtaken(tmp_path, "zz", "w") == 1
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--pr", "901", "--base", "e3", "--diff", "z2")
    assert _overtaken(tmp_path, "zz", "w") == 0


@requires_tools
def test_undeclared_merge_strict_resolves_to_unknown_never_to_no(tmp_path: Path) -> None:
    """A wave whose orchestrator never declared it must not acquire a clean bill.

    `unknown` and `no` differ: `no` says protection was read and is not strict;
    `unknown` says nobody read it. Silence resolving to `no` is the scan-silence
    trap, so the default is the honest one and the signal still reports.
    """
    for base in ("a", "b", "c"):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "5", "--base", base, "--diff", "same", live=SELF_PID)
    out = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert "FLOW_WAVE_MERGE_STRICT=unknown" in out.stdout, out.stdout
    assert "STARVATION:" in out.stdout, out.stdout


@requires_tools
def test_merge_strict_no_means_there_is_no_starvation_to_report(tmp_path: Path) -> None:
    """A repo without strict:true gets no hold, and the key agrees with the prose.

    Losing a base without strict does not cost a merge slot, so the observation
    is an ordinary rebase. The machine key must read 0 too - a consumer acting on
    a number the roster declines to explain is the same defect in a new place.
    """
    for base in ("a", "b", "c"):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "5", "--base", base, "--diff", "same", live=SELF_PID)
    # PRECONDITION, because the assertion below is an ABSENCE: prove the signal
    # fires here FIRST, so that its later absence is caused by the policy and
    # not by a role that was never live enough to report anything.
    before = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert "STARVATION:" in before.stdout, before.stdout
    _run(tmp_path, "policy", "set", "--wave", "zz", "--merge-strict", "no")
    out = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert "FLOW_WAVE_MERGE_STRICT=no" in out.stdout, out.stdout
    assert "FLOW_WAVE_STARVATION=0" in out.stdout, out.stdout
    assert "STARVATION:" not in out.stdout, out.stdout


@requires_tools
def test_a_mistyped_merge_strict_is_refused_not_stored(tmp_path: Path) -> None:
    """A typo must be exit 2, not a stored value nobody can act on."""
    out = _run(tmp_path, "policy", "set", "--wave", "zz", "--merge-strict", "ture")
    assert out.returncode == 2, out.stdout + out.stderr


# --------------------------------------------------------------------------- #
# #985 - a worker's diff versus its declared lane
# --------------------------------------------------------------------------- #


def _lane_repo(tmp: Path) -> Path:
    """A repo whose working tree has diverged from its own `origin/main`.

    Built with git rather than a fixture file so the gate reads exactly what git
    emits. The gate uses `git diff --name-only` - git's own accounting - rather
    than parsing patch text, because a gate that re-implements diff parsing
    inherits every edge case git already handles, and the edge cases are where a
    revert hides.
    """
    repo = tmp / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True)
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "config", "user.email", "t@example.com"], check=True, capture_output=True)
    subprocess.run([*git, "config", "user.name", "t"], check=True, capture_output=True)
    (repo / "mine.sh").write_text("#!/bin/sh\necho a\n")
    (repo / "theirs.md").write_text("theirs\n")
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True, capture_output=True)
    subprocess.run([*git, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True, capture_output=True)
    return repo


@requires_git_tools
def test_a_path_outside_the_declared_lane_refuses(tmp_path: Path) -> None:
    """The #985 red case: the incident itself, reduced.

    A stale payload reverts another worker's merged files, and every
    content-based gate is blind to it - a suite cannot object to work that is not
    there, and the stale tree is a previously-green commit. A file the role never
    claimed appearing in its own diff is the whole signal.
    """
    repo = _lane_repo(tmp_path)
    (repo / "mine.sh").write_text("#!/bin/sh\necho b\n")
    (repo / "theirs.md").write_text("clobbered\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo), "--files", "mine.sh")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo)
    assert out.returncode == 1, (out.returncode, out.stdout, out.stderr)
    assert "FLOW_WAVE_LANE_CHECK=extra" in out.stdout, out.stdout
    assert "theirs.md" in out.stdout + out.stderr, "the offending path must be NAMED"


@requires_git_tools
def test_the_same_diff_without_that_path_passes(tmp_path: Path) -> None:
    """The mirror of the case above - or the refusal proves nothing."""
    repo = _lane_repo(tmp_path)
    (repo / "mine.sh").write_text("#!/bin/sh\necho b\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo), "--files", "mine.sh")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo)
    assert out.returncode == 0, (out.returncode, out.stdout, out.stderr)
    assert "FLOW_WAVE_LANE_CHECK=ok" in out.stdout, out.stdout
    assert "FLOW_WAVE_LANE_TOUCHED=1" in out.stdout, out.stdout


@requires_git_tools
def test_no_declared_lane_is_unknown_never_a_pass(tmp_path: Path) -> None:
    """A role with nothing declared has nothing to compare against.

    Reporting that as clean makes the gate go quiet exactly when it has nothing
    to check, which is the shape where unclaimed, released and over-claimed all
    render identically.
    """
    repo = _lane_repo(tmp_path)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo))
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo)
    assert out.returncode == 2, (out.returncode, out.stdout)
    assert "FLOW_WAVE_LANE_CHECK=unknown" in out.stdout, out.stdout


@requires_git_tools
def test_a_wide_lane_is_data_and_a_contended_one_is_a_finding(tmp_path: Path) -> None:
    """The third state, deliberately not graded.

    An unused lane entry is common and usually innocent, so a report that always
    has content gets read as noise and then not read at all. Declared-but-
    untouched is emitted as DATA; the rare actionable subset - also claimed by
    another LIVE role - is named separately, because that pair is how a lane
    silently takes a file somebody else is working in.
    """
    repo = _lane_repo(tmp_path)
    (repo / "mine.sh").write_text("#!/bin/sh\necho b\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh,unused.md", live=SELF_PID)
    quiet = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo, live=SELF_PID)
    assert quiet.returncode == 0, (quiet.returncode, quiet.stdout)
    assert "FLOW_WAVE_LANE_UNUSED=1" in quiet.stdout, quiet.stdout
    assert "FLOW_WAVE_LANE_CONTESTED=0" in quiet.stdout, quiet.stdout
    assert "OVER-CLAIM" not in quiet.stdout + quiet.stderr, "a wide lane alone is not a finding"

    _run(tmp_path, "register", "rival", "--wave", "zz", "--repo", str(repo),
         "--files", "unused.md", live=SELF_PID)
    loud = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo, live=SELF_PID)
    assert "FLOW_WAVE_LANE_CONTESTED=1" in loud.stdout, loud.stdout
    assert "OVER-CLAIM" in loud.stdout + loud.stderr, loud.stdout


@requires_git_tools
def test_a_newline_in_a_filename_cannot_split_into_two_in_lane_paths(tmp_path: Path) -> None:
    """Codex pass 2. The NUL-safety fix reintroduced the hazard it removed.

    Command substitution strips NUL, so the enumeration writes `git diff -z` to a
    temp file - and then converted the NULs to newlines to read it back. That
    hands the splitting right back to any filename CONTAINING a newline: one
    out-of-lane path named `mine.sh\ntheirs.md` splits into two paths that are
    BOTH in the lane, and the gate reports ok. The delimiter has to stay NUL all
    the way to the reader.
    """
    repo = _lane_repo(tmp_path)
    evil = repo / "mine.sh\ntheirs.md"
    evil.write_text("out of lane\n")
    #: `git diff` cannot see an UNTRACKED path, so the payload has to be staged
    #: or the gate is being asked about a file it structurally cannot observe.
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh,theirs.md")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo)
    assert "FLOW_WAVE_LANE_TOUCHED=1" in out.stdout, (
        "one file was created, so one path must be counted", out.stdout)
    assert out.returncode == 1, (out.returncode, out.stdout, out.stderr)
    assert "FLOW_WAVE_LANE_CHECK=extra" in out.stdout, out.stdout


@requires_git_tools
def test_an_ok_verdict_names_the_population_it_could_not_see(tmp_path: Path) -> None:
    """A zero must distinguish "I looked" from "there was nothing to look at".

    `git diff` observes TRACKED paths only, so an untracked out-of-lane file is
    invisible to the whole check. That scope is deliberate - an untracked file is
    not part of what a push delivers - but a bare `TOUCHED=0 ... ok` reads as a
    clean bill of health over a tree the gate never examined, which is how the
    ABSENCE of a warning gets taken for the PRESENCE of a check. The uncovered
    population is reported beside the verdict instead.
    """
    repo = _lane_repo(tmp_path)
    (repo / "not-my-lane.md").write_text("untracked, unseen\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo), "--files", "mine.sh")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo)
    assert "FLOW_WAVE_LANE_TOUCHED=0" in out.stdout, out.stdout
    assert "FLOW_WAVE_LANE_UNTRACKED=1" in out.stdout, (
        "the file the diff structurally cannot see must still be counted", out.stdout)
    assert out.returncode == 0, "an untracked file is not part of the payload, so it is not a finding"


@requires_git_tools
def test_a_glob_in_a_declaration_is_never_pathname_expanded(tmp_path: Path) -> None:
    """Codex pass 2. `set +f` restores globbing ON, not the caller's state.

    lane_covers disables pathname expansion around its own CSV split and then
    turns it back on unconditionally - so the unused-lane loop, which splits the
    same CSV the same way, runs with globbing ENABLED. A literal declaration like
    `*.md` then expands against the working directory into files the role never
    declared, and those invented paths are what get reported as unused, and can
    be reported as CONTESTED against another role. A gate must not manufacture
    the paths it grades.
    """
    repo = _lane_repo(tmp_path)
    (repo / "other.md").write_text("other\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "other"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"],
                   check=True, capture_output=True)
    (repo / "mine.sh").write_text("#!/bin/sh\necho b\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh,*.md", live=SELF_PID)
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo, live=SELF_PID)
    blob = out.stdout + out.stderr
    assert "theirs.md" not in blob, ("a declaration was expanded into a real path", blob)
    assert "other.md" not in blob, ("a declaration was expanded into a real path", blob)
    assert "FLOW_WAVE_LANE_UNUSED=1" in out.stdout, (
        "the literal '*.md' is one unused entry, not one per matching file", out.stdout)


# --------------------------------------------------------------------------- #
# #985 - a declared DIRECTORY contains the paths under it
# --------------------------------------------------------------------------- #


def _two_lanes(tmp: Path, a: str, b: str) -> subprocess.CompletedProcess[str]:
    _run(tmp, "register", "wide", "--wave", "zz", "--repo", "/same", "--cwd", "/wt/a",
         "--files", a, live=SELF_PID)
    _run(tmp, "register", "inner", "--wave", "zz", "--repo", "/same", "--cwd", "/wt/b",
         "--files", b, live=SELF_PID)
    return _run(tmp, "list", "--wave", "zz", live=SELF_PID)


@requires_tools
def test_a_declared_directory_collides_with_a_path_inside_it(tmp_path: Path) -> None:
    """The live case: a bare `codex/skills` claimed three other roles' mirrors.

    Exact-match reported no overlap at all. A declared directory containing the
    paths under it is not a prefix guess - it is what declaring a directory means.
    """
    out = _two_lanes(tmp_path, "codex/skills", "codex/skills/flow-repair/reference.md")
    assert "overlapping FILE LANES" in out.stdout, out.stdout


@requires_tools
def test_containment_is_not_prefix_guessing(tmp_path: Path) -> None:
    """The control that keeps containment from becoming the #683 false positive.

    The test is anchored on a separator, so `scripts/foo` does NOT contain
    `scripts/foobar`. Only a real path boundary counts.
    """
    out = _two_lanes(tmp_path, "scripts/foo", "scripts/foobar")
    assert "overlapping FILE LANES" not in out.stdout, out.stdout


@requires_tools
def test_disjoint_lanes_still_warn_about_nothing(tmp_path: Path) -> None:
    out = _two_lanes(tmp_path, "scripts/alpha.sh", "scripts/beta.sh")
    assert "overlapping FILE LANES" not in out.stdout, out.stdout


@requires_tools
def test_identical_lanes_still_collide(tmp_path: Path) -> None:
    """Exact-match must be unregressed: containment ADDED a case, it replaced none."""
    out = _two_lanes(tmp_path, "scripts/same.sh", "scripts/same.sh")
    assert "overlapping FILE LANES" in out.stdout, out.stdout


# --------------------------------------------------------------------------- #
# #1026 - declarations that were stored and never read back
#
# Every case below shares one shape: something is DECLARED and nothing reports
# it, so a broken declaration and a working one print identically. Each test is
# paired with its opposite, because a check that only ever fires - or only ever
# passes - carries the same amount of information as no check at all.
# --------------------------------------------------------------------------- #


@requires_tools
def test_a_dropped_lane_path_is_reported(tmp_path: Path) -> None:
    """THE RED CASE. ``--files`` REPLACES, and the drop was silent.

    A role re-registering for its next issue with a new list loses its claim on
    everything it held - at the moment it is most likely to have just merged the
    file. Afterwards the roster cannot distinguish *nobody has claimed this path*
    from *nobody is in conflict over it*: both render as silence, which is the
    failure class this whole helper exists to refuse.

    The assertion is on the path being NAMED, not merely on a count: a warning
    that says a drop happened without saying what was dropped cannot be acted on.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--files", "src/a.py,src/b.py")
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
               "--files", "src/b.py")
    assert _detail(out, "FLOW_WAVE_FILES_DROPPED") == "src/a.py", out.stdout
    assert _detail(out, "FLOW_WAVE_FILES") == "src/b.py", out.stdout
    assert "src/a.py" in out.stderr, out.stderr
    assert "REPLACES" in out.stderr, out.stderr


@requires_tools
def test_an_unchanged_lane_reports_no_drop(tmp_path: Path) -> None:
    """THE GREEN CASE (ADR 0008). Without it the report above proves nothing.

    A drop report that fired on every re-registration would satisfy the test
    above and be worthless - re-registering is the DOCUMENTED cheap re-brief
    (#670), so it happens constantly and a warning on it trains everyone to
    ignore the warning.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--files", "src/a.py,src/b.py")
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
               "--files", "src/a.py,src/b.py")
    assert _detail(out, "FLOW_WAVE_FILES_DROPPED") == "-", out.stdout
    assert _detail(out, "FLOW_WAVE_FILES_ADDED") == "-", out.stdout
    assert "DROPPED" not in out.stderr, out.stderr


@requires_tools
def test_omitting_files_entirely_is_not_a_drop(tmp_path: Path) -> None:
    """Role-level facts are PRESERVED when their flag is omitted (#699).

    The re-brief that recovers a compacted worker's protocol passes no ``--files``
    at all, and reporting that as a drop would make the loudest warning in the
    helper fire on its most routine invocation.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--files", "src/a.py")
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp")
    assert _detail(out, "FLOW_WAVE_FILES") == "src/a.py", out.stdout
    assert _detail(out, "FLOW_WAVE_FILES_DROPPED") == "-", out.stdout


@requires_tools
def test_respelling_a_held_path_is_not_a_drop(tmp_path: Path) -> None:
    """Two legitimate spellings of one path must not read as two files.

    ``src`` and ``src/`` are the same declaration, and narrowing to a file inside
    a directory you still hold drops nothing. String equality here would
    manufacture a finding out of how somebody typed a path - and a drop report
    that cries wolf on a respelling is one nobody reads, which is exactly the
    silence this replaced.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp", "--files", "src")
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp", "--files", "src/")
    assert _detail(out, "FLOW_WAVE_FILES_DROPPED") == "-", out.stdout
    # ...and the containment direction that DOES drop still does.
    narrowed = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
                    "--files", "src/a.py")
    assert _detail(narrowed, "FLOW_WAVE_FILES_DROPPED") == "src", narrowed.stdout


@requires_tools
def test_register_reads_back_its_own_driver(tmp_path: Path) -> None:
    """A silently-accepted flag and a silently-IGNORED one were identical here.

    ``register`` stored ``--driver`` and emitted nothing, so the one moment a
    caller could still catch a typo produced no evidence either way. ``get``
    answered, but a worker asking ``get`` about itself to find out what it just
    said is the round trip this removes.
    """
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
               "--driver", "flow:auto")
    assert _detail(out, "FLOW_WAVE_DRIVER") == "flow:auto", out.stdout
    # The #783 capability fence travels with it, or an orchestrator still has to
    # ask a second question to route anything.
    assert _detail(out, "FLOW_WAVE_DRIVER_SCOPE") != "", out.stdout
    # The green/red pair: a role that declared none reads `-`, never a fabricated
    # driver name.
    bare = _run(tmp_path, "register", "x", "--wave", "zz", "--repo", "/tmp")
    assert _detail(bare, "FLOW_WAVE_DRIVER") == "-", bare.stdout


@requires_tools
def test_driver_undeclared_is_counted_only_where_the_question_arises(tmp_path: Path) -> None:
    """Three states, and the third is why this is not a bare count.

    A wave-level ``policy set --driver`` is inherited DOCTRINE - it populates no
    role's ``driver=`` - so a worker quietly running something else produces a
    byte-identical roster row. But ``register.md``'s canonical invocation is not
    required to pass ``--driver``, so counting every driverless role would fire
    on the ordinary shape (#674).

    Hence: ``-`` when the wave declares no driver (the question does not arise),
    a real count when it does. ``0`` would claim a measurement that was never
    taken, and a counter that silently matches nothing renders identically to a
    working one.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp", live=SELF_PID)
    no_policy = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(no_policy, "FLOW_WAVE_DRIVER_UNDECLARED") == "-", no_policy.stdout

    _run(tmp_path, "policy", "set", "--wave", "zz", "--driver", "codex:auto")
    exposed = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(exposed, "FLOW_WAVE_DRIVER_UNDECLARED") == "1", exposed.stdout
    assert "codex:auto" in exposed.stdout, "the roster must name the wave's driver"

    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--driver", "codex:auto", live=SELF_PID)
    declared = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(declared, "FLOW_WAVE_DRIVER_UNDECLARED") == "0", declared.stdout


@requires_tools
def test_driver_undeclared_is_reported_on_every_render_path(tmp_path: Path) -> None:
    """An instrument visible in one output mode and invisible in another is the
    same blind-spot failure one level up - the reason #800 counts above the
    ``--json`` branch rather than inside it."""
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp", live=SELF_PID)
    _run(tmp_path, "policy", "set", "--wave", "zz", "--driver", "codex:auto")
    for args in (("list", "--wave", "zz"), ("list", "--wave", "zz", "--json")):
        out = _run(tmp_path, *args, live=SELF_PID)
        assert _detail(out, "FLOW_WAVE_DRIVER_UNDECLARED") == "1", (args, out.stdout)
    empty = _run(tmp_path, "list", "--wave", "no-such-wave", live=SELF_PID)
    assert "FLOW_WAVE_DRIVER_UNDECLARED=" in empty.stdout, empty.stdout


@requires_tools
def test_a_stale_merge_strict_no_stops_suppressing_starvation(tmp_path: Path) -> None:
    """THE TWO-SIDED CONTROL. One declaration, two verdicts, clock the only input.

    ``merge_strict=no`` switches starvation detection OFF, and branch protection
    is repo state anyone with admin can change - including from outside the wave.
    So a wave that declared ``no`` went silently blind the moment protection was
    TIGHTENED, which is precisely the change that makes starvation possible. The
    staleness was unbounded because nothing dated the reading.

    Both halves run here on the SAME stored policy, so the difference cannot be
    attributed to anything but the age of the observation.
    """
    for base in ("a", "b", "c"):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "5", "--base", base, "--diff", "same", live=SELF_PID)
    _run(tmp_path, "policy", "set", "--wave", "zz", "--merge-strict", "no")

    fresh = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(fresh, "FLOW_WAVE_MERGE_STRICT") == "no", fresh.stdout
    assert _detail(fresh, "FLOW_WAVE_MERGE_STRICT_SUPPRESSING") == "yes", fresh.stdout
    assert _detail(fresh, "FLOW_WAVE_STARVATION") == "0", fresh.stdout

    # Same registry, same declaration, two days later.
    stale = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID, now="1700172800")
    assert _detail(stale, "FLOW_WAVE_POLICY_MERGE_STRICT_STALE") == "yes", stale.stdout
    assert _detail(stale, "FLOW_WAVE_MERGE_STRICT_SUPPRESSING") == "no", stale.stdout
    assert _detail(stale, "FLOW_WAVE_STARVATION") != "0", stale.stdout
    assert "NOT suppressed" in stale.stderr, stale.stderr
    # The DECLARATION is still reported as declared - expiry changes what it
    # governs, never what it says.
    assert _detail(stale, "FLOW_WAVE_MERGE_STRICT") == "no", stale.stdout


@requires_tools
def test_an_unstamped_merge_strict_is_not_treated_as_fresh(tmp_path: Path) -> None:
    """Undatable is not recent (the scan-silence rule, applied to a timestamp).

    A policy written before the stamp existed carries ``merge_strict`` and no
    ``merge_strict_ts``. Reading that as a fresh observation would restore the
    unbounded staleness in exactly the case nobody would think to check.
    """
    for base in ("a", "b", "c"):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "5", "--base", base, "--diff", "same", live=SELF_PID)
    _run(tmp_path, "policy", "set", "--wave", "zz", "--merge-strict", "no")
    reg = _registry_json(tmp_path)
    del reg["zz"]["policy"]["merge_strict_ts"]
    (tmp_path / "reg" / "registry.json").write_text(json.dumps(reg))

    out = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(out, "FLOW_WAVE_POLICY_MERGE_STRICT_STALE") == "unknown", out.stdout
    assert _detail(out, "FLOW_WAVE_MERGE_STRICT_SUPPRESSING") == "no", out.stdout
    assert _detail(out, "FLOW_WAVE_STARVATION") != "0", out.stdout


@requires_tools
def test_authority_model_has_a_value_for_the_most_restrictive_answer(tmp_path: Path) -> None:
    """The enum's only escape hatch used to be PERMISSIVE.

    With just ``orchestrator-only`` and ``user-and-orchestrator`` on offer, an
    operator declaring a NARROWER authority than the enum contemplated had to
    either leave the field empty - which reads as undeclared - or store a value
    granting authority the owner never delegated. For a field whose whole job is
    to say who may authorise work, that is the wrong direction to fail in.
    """
    out = _run(tmp_path, "policy", "set", "--wave", "zz", "--authority-model", "user-only")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _detail(out, "FLOW_WAVE_POLICY_AUTHORITY_MODEL") == "user-only", out.stdout
    # The enum must still BE an enum, or widening it proves nothing.
    typo = _run(tmp_path, "policy", "set", "--wave", "zz", "--authority-model", "user only")
    assert typo.returncode == 2, typo.stdout + typo.stderr


@requires_git_tools
def test_a_lane_wider_than_its_grant_refuses(tmp_path: Path) -> None:
    """THE RED CASE for the one comparison nothing made (#1026).

    Everything else compares a lane against other LANES, or against a DIFF. The
    grant that authorised it was never a party to either - and the grant is the
    side that changes shape on the way in: prose in a message, data in the
    registry. A lane claiming what nobody handed over is how one role quietly
    takes another's file, and unlike the diff check it is knowable before a line
    is written.
    """
    repo = _lane_repo(tmp_path)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh,theirs.md")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz",
               "--granted", "mine.sh", cwd=repo)
    assert out.returncode == 1, (out.returncode, out.stdout, out.stderr)
    assert "FLOW_WAVE_LANE_CHECK=ungranted" in out.stdout, out.stdout
    assert _detail(out, "FLOW_WAVE_LANE_UNGRANTED") == "1", out.stdout
    assert "theirs.md" in out.stdout + out.stderr, "the offending path must be NAMED"


@requires_git_tools
def test_a_lane_inside_its_grant_passes(tmp_path: Path) -> None:
    """THE GREEN CASE, and the spelling control with it.

    The grant here names a DIRECTORY that contains the declared lane. A
    string-equality comparison would call that two different files and refuse a
    correct lane - manufacturing a finding out of how somebody typed a path, and
    turning the gate into one people route around.
    """
    repo = _lane_repo(tmp_path)
    (repo / "mine.sh").write_text("#!/bin/sh\necho b\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh")
    exact = _run(tmp_path, "lane-check", "w", "--wave", "zz",
                 "--granted", "mine.sh", cwd=repo)
    assert exact.returncode == 0, (exact.returncode, exact.stdout, exact.stderr)
    assert _detail(exact, "FLOW_WAVE_LANE_UNGRANTED") == "0", exact.stdout
    assert _detail(exact, "FLOW_WAVE_LANE_UNCLAIMED") == "0", exact.stdout


@requires_git_tools
def test_a_granted_path_missing_from_the_lane_is_loud_but_not_a_refusal(tmp_path: Path) -> None:
    """The lapse seen from the other side - and deliberately NOT a refusal.

    A granted path the lane dropped is unprotected: another role can claim it and
    overlap detection reports nothing. That is worth saying every time. But the
    worker's DIFF may be perfectly correct, and blocking a good push over a
    bookkeeping gap is how a guard gets worked around. So it is counted and said
    aloud, and the exit code is left alone.
    """
    repo = _lane_repo(tmp_path)
    (repo / "mine.sh").write_text("#!/bin/sh\necho b\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz",
               "--granted", "mine.sh,theirs.md", cwd=repo)
    assert out.returncode == 0, (out.returncode, out.stdout, out.stderr)
    assert _detail(out, "FLOW_WAVE_LANE_UNCLAIMED") == "1", out.stdout
    assert _detail(out, "FLOW_WAVE_LANE_UNGRANTED") == "0", out.stdout
    assert "theirs.md" in out.stderr, out.stderr


@requires_git_tools
def test_no_grant_supplied_reads_as_not_asked_never_as_zero(tmp_path: Path) -> None:
    """``-``, not ``0``. A zero claims a comparison nobody requested.

    This is the distinction that keeps every other assertion in this group
    meaningful: without it, a caller that forgot ``--granted`` would read a clean
    grant check that never ran.
    """
    repo = _lane_repo(tmp_path)
    (repo / "mine.sh").write_text("#!/bin/sh\necho b\n")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", cwd=repo)
    assert out.returncode == 0, (out.returncode, out.stdout, out.stderr)
    assert _detail(out, "FLOW_WAVE_LANE_UNGRANTED") == "-", out.stdout
    assert _detail(out, "FLOW_WAVE_LANE_UNCLAIMED") == "-", out.stdout


@requires_git_tools
def test_an_empty_grant_is_a_missing_measurement_not_a_grant_of_nothing(tmp_path: Path) -> None:
    """``--granted ''`` would otherwise make EVERY lane entry ungranted.

    An empty value is the signature of a variable that did not expand, and
    resolving it to "nothing was granted" turns a caller's bug into a wall of
    findings about paths that were in fact granted.
    """
    repo = _lane_repo(tmp_path)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo),
         "--files", "mine.sh")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", "--granted", "", cwd=repo)
    assert out.returncode == 2, (out.returncode, out.stdout, out.stderr)
    assert "FLOW_WAVE_LANE_CHECK=unknown" in out.stdout, out.stdout


# --------------------------------------------------------------------------- #
# #1026, counter-model review (Codex gpt-5.5) - defects found in the fix itself
#
# Every one of these is the same class the issue is about, committed by the fix:
# an instrument that stops discriminating without saying so.
# --------------------------------------------------------------------------- #


@requires_tools
def test_a_malformed_ttl_does_not_silently_disable_the_shelf_life(tmp_path: Path) -> None:
    """THE FAIL-OPEN CASE. An unusable TTL must not read as "never expires".

    ``[ "$age" -gt "$TTL" ]`` with a non-numeric TTL is a bash integer-expression
    ERROR, which returns false, which falls through to "fresh". So a typo in an
    environment variable would have silently restored the unbounded staleness
    this shelf life exists to bound - and, being a suppression, would have
    announced nothing at all.
    """
    for base in ("a", "b", "c"):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "5", "--base", base, "--diff", "same", live=SELF_PID)
    _run(tmp_path, "policy", "set", "--wave", "zz", "--merge-strict", "no")

    env = {"FLOW_WAVE_MERGE_STRICT_TTL": "bogus"}
    out = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID, now="1700172800", extra_env=env)
    assert _detail(out, "FLOW_WAVE_POLICY_MERGE_STRICT_STALE") == "yes", out.stdout
    assert _detail(out, "FLOW_WAVE_MERGE_STRICT_SUPPRESSING") == "no", out.stdout
    assert "not a non-negative integer" in out.stderr, out.stderr
    # The green half: a VALID override must still take effect, or "validated"
    # would just mean "ignored".
    wide = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID, now="1700172800",
                extra_env={"FLOW_WAVE_MERGE_STRICT_TTL": "999999"})
    assert _detail(wide, "FLOW_WAVE_MERGE_STRICT_SUPPRESSING") == "yes", wide.stdout


@requires_tools
def test_a_stamp_from_the_future_is_unknown_not_very_fresh(tmp_path: Path) -> None:
    """Clock skew produces a NEGATIVE age. That is a broken observation.

    Rounding it down to "fresh" would suppress starvation detection on the
    strength of a reading we have positive evidence against - the permissive
    direction, in the one field where permissive is the wrong way to fail.
    """
    for base in ("a", "b", "c"):
        _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
             "--pr", "5", "--base", base, "--diff", "same", live=SELF_PID)
    _run(tmp_path, "policy", "set", "--wave", "zz", "--merge-strict", "no")
    # The registry was stamped at 1700000000; read it from an hour earlier.
    out = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID, now="1699996400")
    assert _detail(out, "FLOW_WAVE_POLICY_MERGE_STRICT_STALE") == "unknown", out.stdout
    assert _detail(out, "FLOW_WAVE_MERGE_STRICT_SUPPRESSING") == "no", out.stdout


@requires_tools
def test_the_driver_zero_carries_the_population_it_inspected(tmp_path: Path) -> None:
    """A zero must distinguish "looked and found none" from "nothing to look at".

    Under a declared policy driver an EMPTY wave and a wave whose every live
    worker declares one both report ``UNDECLARED=0``. Without a denominator the
    two are byte-identical, which is this repo's own detector contract failing on
    the counter that was added to enforce it.
    """
    empty = _run(tmp_path, "policy", "set", "--wave", "zz", "--driver", "codex:auto")
    assert empty.returncode == 0, empty.stdout + empty.stderr
    nobody = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(nobody, "FLOW_WAVE_DRIVER_UNDECLARED") == "0", nobody.stdout
    assert _detail(nobody, "FLOW_WAVE_DRIVER_POPULATION") == "0", (
        "an empty wave must not report the same evidence as an all-clear one"
    )

    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--driver", "codex:auto", live=SELF_PID)
    allclear = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(allclear, "FLOW_WAVE_DRIVER_UNDECLARED") == "0", allclear.stdout
    assert _detail(allclear, "FLOW_WAVE_DRIVER_POPULATION") == "1", allclear.stdout


@requires_tools
def test_a_lane_path_containing_a_space_is_one_path(tmp_path: Path) -> None:
    """``norm_path`` keeps inner spaces, so the lane model supports them.

    Reporting the delta as a space-joined string and counting it with ``wc -w``
    turned one valid entry into two - a count the caller cannot reconcile with a
    list they cannot parse. Commas are the lane's own serialization, so the
    result feeds straight back into ``--files``.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--files", "docs/My File.md,src/b.py")
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
               "--files", "src/b.py")
    assert _detail(out, "FLOW_WAVE_FILES_DROPPED") == "docs/My File.md", out.stdout
    assert "DROPPED 1 path(s)" in out.stderr, out.stderr


@requires_tools
def test_the_drop_warning_claims_only_what_register_inspected(tmp_path: Path) -> None:
    """``register`` never reads the roster, so it cannot say who holds a path.

    The warning previously asserted "nothing else holds these paths now" - a
    roster-wide fact this command does not look up, and one another live role can
    flatly contradict. Fabricated specificity in a warning is how a reader stops
    believing the ones that are earned.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--files", "src/a.py,src/b.py")
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
               "--files", "src/b.py")
    assert "Nothing else holds" not in out.stderr, out.stderr
    assert "THIS role no longer holds" in out.stderr, out.stderr
    assert "list --wave zz" in out.stderr, "the reader must be sent where the answer is"


@requires_tools
def test_reusing_a_released_role_is_not_a_drop(tmp_path: Path) -> None:
    """``release`` IS the withdrawal; the next registration must not re-report it.

    A released entry used to keep its ``files`` - it was marked, not erased - so
    reading the field without asking about ``released`` made ordinary role
    re-use fire the loudest warning in this helper. A warning on the normal path
    is the #674 defect, and here it would land on the very report that has to be
    believed. Since #1222 ``release`` clears the lane outright; the ``released``
    guard stays, so a row written before #1222 is still read correctly.
    """
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp", "--files", "src/a.py")
    _run(tmp_path, "release", "w", "--wave", "zz")
    out = _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp", "--files", "src/b.py")
    assert _detail(out, "FLOW_WAVE_FILES_DROPPED") == "-", out.stdout
    assert "DROPPED" not in out.stderr, out.stderr
    # The green/red pair: an UNRELEASED predecessor still reports its drop, or
    # this fix would have disabled the detector rather than scoped it.
    _run(tmp_path, "register", "v", "--wave", "zz", "--repo", "/tmp", "--files", "src/a.py")
    live = _run(tmp_path, "register", "v", "--wave", "zz", "--repo", "/tmp", "--files", "src/b.py")
    assert _detail(live, "FLOW_WAVE_FILES_DROPPED") == "src/a.py", live.stdout


# --------------------------------------------------------------------------- #
# #1222 - a row describes ONE piece of work, and a released row describes none
# --------------------------------------------------------------------------- #

_LANE_KEYS = ("issue", "pr", "branch", "base", "diff", "obs_repo", "files")


def _entry(tmp: Path, wave: str, role: str) -> dict:
    return _registry_json(tmp)[wave]["roles"][role]


def _register_lane_a(tmp: Path, role: str = "w") -> None:
    _run(tmp, "register", role, "--wave", "zz", "--repo", "/tmp",
         "--issue", "1085", "--branch", "issue-1085-a",
         "--pr", "1202", "--base", "baseA", "--diff", "diffA",
         "--files", "docs/decisions/0008-a.md,docs/scripts.md")


@requires_tools
def test_release_clears_the_lane_and_keeps_the_record(tmp_path: Path) -> None:
    """``release`` used to set ``released`` and clear nothing (#1222).

    Measured on a real wave: a released role whose session had ended still
    advertised a closed issue, a merged PR and an eight-path file lane, so the
    roster could not tell "held by a live role" from "left behind by one that
    ended". The lane goes; the release record and the identity stay, and what
    was held is kept under a key that cannot be read as a current claim.
    """
    _register_lane_a(tmp_path)
    _run(tmp_path, "release", "w", "--wave", "zz", now="1700000500")
    e = _entry(tmp_path, "zz", "w")
    for key in _LANE_KEYS:
        assert e.get(key, "") == "", (key, e)
    assert e.get("overtaken", 0) == 0, e
    # Auditable: the release itself and who made it survive.
    assert e["released"] is True
    assert e["released_ts"] == 1700000500
    assert str(e["pid"]) == SELF_PID and e["session"] == SELF_SESSION
    assert e["repo"] == "/tmp", "repo drives the claim scan's repo discovery"
    # History, under a key no lane reader consults.
    hist = e["released_lane"]
    assert hist["issue"] == "1085" and hist["pr"] == "1202", hist
    assert hist["files"] == "docs/decisions/0008-a.md,docs/scripts.md", hist
    # And the roster no longer renders the lane as a claim.
    row = _row(_run(tmp_path, "list", "--wave", "zz"), "w")
    assert row, "the released role must still be listed"
    for token in ("issue=1085", "pr=#1202", "files="):
        assert token not in row, row


@requires_tools
def test_a_second_release_keeps_the_first_record(tmp_path: Path) -> None:
    """Releasing twice must not overwrite the record with the blanks left by the first."""
    _register_lane_a(tmp_path)
    _run(tmp_path, "release", "w", "--wave", "zz")
    _run(tmp_path, "release", "w", "--wave", "zz")
    hist = _entry(tmp_path, "zz", "w")["released_lane"]
    assert hist["issue"] == "1085" and hist["pr"] == "1202", hist


@requires_tools
def test_reregistering_onto_another_issue_leaves_no_field_naming_the_first(tmp_path: Path) -> None:
    """The blend worker-AA measured: issue current, pr and base one issue stale.

    A row that tracked some fields forward and pinned others described a
    pairing of issue and PR that never existed at any moment. Re-registering
    onto a different issue must clear or refresh EVERY lane fact.
    """
    _register_lane_a(tmp_path)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--issue", "1189", "--branch", "issue-1189-b")
    e = _entry(tmp_path, "zz", "w")
    assert e["issue"] == "1189" and e["branch"] == "issue-1189-b", e
    for key in ("pr", "base", "diff", "obs_repo", "files"):
        assert e.get(key, "") == "", (key, e)
    assert e.get("overtaken", 0) == 0, e
    flat = json.dumps(e)
    for a_value in ("1085", "1202", "baseA", "diffA", "0008-a.md"):
        assert a_value not in flat, (a_value, e)


@requires_tools
def test_an_issue_change_resets_the_starvation_count(tmp_path: Path) -> None:
    """Same PR, same diff, new base: counts on the same issue, resets on a new one.

    The count belongs to one piece of work. Carried across an issue change it
    would make an old warning live again for unrelated work (counter-model red
    case). The same-issue arm is the control that the count is really moving.
    """
    for role in ("moves", "stays"):
        for base in ("A0", "A1"):
            _run(tmp_path, "register", role, "--wave", "zz", "--repo", "/tmp",
                 "--issue", "1085", "--pr", "1202", "--base", base, "--diff", "D")
        assert _overtaken(tmp_path, "zz", role) == 1
    _run(tmp_path, "register", "moves", "--wave", "zz", "--repo", "/tmp",
         "--issue", "1189", "--pr", "1202", "--base", "A2", "--diff", "D")
    _run(tmp_path, "register", "stays", "--wave", "zz", "--repo", "/tmp",
         "--issue", "1085", "--pr", "1202", "--base", "A2", "--diff", "D")
    assert _overtaken(tmp_path, "zz", "moves") == 0
    assert _overtaken(tmp_path, "zz", "stays") == 2


@requires_tools
def test_a_new_issue_with_a_new_observation_takes_the_new_one(tmp_path: Path) -> None:
    """Clearing on an issue change must not swallow facts given in the SAME call."""
    _register_lane_a(tmp_path)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--issue", "1189", "--pr", "1223", "--base", "baseB", "--diff", "diffB",
         "--files", "scripts/b.sh")
    e = _entry(tmp_path, "zz", "w")
    assert (e["pr"], e["base"], e["diff"], e["files"]) == ("1223", "baseB", "diffB", "scripts/b.sh"), e


@requires_tools
def test_a_same_issue_rebrief_keeps_its_lane_and_baseline(tmp_path: Path) -> None:
    """The control for the two tests above: the fix is NOT "clear always".

    The cheap re-brief re-registers with the same issue and no observation. It
    must keep the PR baseline, or the starvation counter (#989) resets on every
    re-read of the protocol and can never reach its threshold.
    """
    _register_lane_a(tmp_path)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp",
         "--pr", "1202", "--base", "baseA2", "--diff", "diffA", "--issue", "1085")
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", "/tmp", "--issue", "1085")
    e = _entry(tmp_path, "zz", "w")
    assert (e["pr"], e["base"], e["diff"]) == ("1202", "baseA2", "diffA"), e
    assert e["files"] == "docs/decisions/0008-a.md,docs/scripts.md", e
    assert e["overtaken"] == 1, e


@requires_tools
def test_a_released_role_contributes_no_starvation(tmp_path: Path) -> None:
    """Acceptance 4: starvation is computed only from roles still holding a lane.

    This held before #1222 (``starvation_scan`` reads live roles only). Going
    through ``release`` would now clear ``pr`` and ``overtaken`` first, so the
    released row would drop out for that reason alone and the test could not
    see the live-only filter (counter-model review). The row is therefore
    released the pre-#1222 way - marked, lane intact - and that precondition is
    asserted before the scan is read. The paired live role proves the same
    history DOES fire.
    """
    for role in ("gone", "here"):
        for base in ("s1", "s2", "s3"):
            _run(tmp_path, "register", role, "--wave", "zz", "--repo", "/tmp",
                 "--issue", "7", "--pr", "70", "--base", base, "--diff", "same")
    before = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(before, "FLOW_WAVE_STARVATION") == "2", before.stdout
    reg_path = tmp_path / "reg" / "registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    gone = data["zz"]["roles"]["gone"]
    gone.update({"released": True, "released_ts": 1700000100})
    reg_path.write_text(json.dumps(data), encoding="utf-8")
    legacy = _entry(tmp_path, "zz", "gone")
    assert legacy["released"] is True and legacy["pr"] == "70", legacy
    assert legacy["overtaken"] >= 2, legacy
    after = _run(tmp_path, "list", "--wave", "zz", live=SELF_PID)
    assert _detail(after, "FLOW_WAVE_STARVATION") == "1", after.stdout


@requires_git_tools
def test_a_whitespace_only_grant_is_a_missing_measurement(tmp_path: Path) -> None:
    """``--granted $'\\t'`` must not become "nothing was granted".

    A hand-rolled emptiness test that strips only commas and spaces let a tab
    through, which ``lane_split`` then trimmed to nothing - and a grant of
    nothing makes EVERY declared lane entry ungranted. A caller's unexpanded
    variable would have produced a wall of confident findings and an exit 1.
    """
    repo = _lane_repo(tmp_path)
    _run(tmp_path, "register", "w", "--wave", "zz", "--repo", str(repo), "--files", "mine.sh")
    out = _run(tmp_path, "lane-check", "w", "--wave", "zz", "--granted", "\t", cwd=repo)
    assert out.returncode == 2, (out.returncode, out.stdout, out.stderr)
    assert "FLOW_WAVE_LANE_CHECK=unknown" in out.stdout, out.stdout
    assert "FLOW_WAVE_LANE_UNGRANTED=1" not in out.stdout, (
        "a whitespace grant must not indict the lane it failed to read"
    )


@requires_tools
def test_merge_strict_suppression_is_reported_on_every_render_path(tmp_path: Path) -> None:
    """Including the EMPTY roster, which returned before deriving it.

    ``list --json`` on an empty wave emitted the key and plain ``list`` did not,
    so a consumer reading the text form could not tell "not suppressing" from
    "this render path never reported suppression" - the same blind-spot shape
    #800 fixed one counter over.
    """
    _run(tmp_path, "policy", "set", "--wave", "zz", "--merge-strict", "no")
    for args in (("list", "--wave", "zz"), ("list", "--wave", "zz", "--json")):
        out = _run(tmp_path, *args, live=SELF_PID)
        assert "FLOW_WAVE_MERGE_STRICT_SUPPRESSING=" in out.stdout, (args, out.stdout)


# ── #1190: a contract line that is missing, and one that is masked ──────────
#
# Both defects in this file are the same species as the issue's title: the
# reader receives something of the RIGHT SHAPE and the WRONG CONTENT, with no
# way to tell. One is an absent verdict that reads as silence; the other is a
# present warning that names the wrong collision.


@requires_tools
class TestEveryExitPathCarriesAVerdict:
    """#1190 defect 2: a refusal that does not announce itself in the
    documented words.

    The published contract says every verb ends with a machine-readable
    ``FLOW_WAVE:`` verdict and lists ``error`` among them. ``usage_fail``
    printed a human line and exited 2 without one, so a contract-conformant
    caller grepping the documented marker saw NOTHING on a refusal - which
    reads as "no news", not as "your command was rejected". A worker hit this
    while re-registering a lane: its check came back empty and the
    registration had in fact been refused.
    """

    def test_a_usage_failure_emits_the_documented_error_verdict(
        self, tmp_path: Path
    ) -> None:
        """The issue's own reproducer: ``register`` with no role."""
        p = _run(tmp_path, "register")
        assert p.returncode == 2
        assert _verdict(p) == "error"

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param(["register"], id="register-no-role"),
            pytest.param(["get"], id="get-no-role"),
            pytest.param(["verify"], id="verify-no-role"),
            pytest.param(["release"], id="release-no-role"),
            pytest.param(["not-a-verb"], id="unknown-verb"),
            pytest.param(["register", "A", "--not-an-option"], id="unknown-option"),
            pytest.param(["register", "A", "--wave"], id="flag-missing-value"),
            pytest.param(["verify", "A", "--wave", "w"], id="verify-no-from"),
        ],
    )
    def test_every_usage_failure_path_emits_a_verdict(
        self, tmp_path: Path, args: list[str]
    ) -> None:
        """The issue named four paths; they are four call sites of ONE
        function with ~45 of them. Fixing the reproducer alone would leave the
        rest silent, so the population is what is pinned here - a rule invoked
        once where many candidates exist is the tell.

        The exit CODE is asserted unchanged deliberately: this change adds the
        missing verdict, it does not renumber the contract. Changing an exit
        code is a contract change for every caller and belongs in its own
        change.
        """
        p = _run(tmp_path, *args)
        assert p.returncode == 2, f"{args} should stay a usage error"
        assert _verdict(p) == "error", f"{args} emitted no FLOW_WAVE: verdict"

    def test_self_address_stays_verdict_free_because_its_stdout_is_captured(
        self, tmp_path: Path
    ) -> None:
        """The GUARD on the other side of this fix, and it exists because the
        obvious reading of the contract is wrong here.

        "Every verb ends in a verdict" invites adding one to ``self-address``.
        I did, during #1190, and it was wrong: this is a VALUE-RETURNING query
        whose stdout IS the address, captured by callers with ``$(...)``.
        Appending the detail block makes that capture multi-line garbage.

        Two long-standing tests already pin it - both assert ``stdout.strip()``
        equals the address exactly - and they are what caught the mistake. This
        one states the RULE rather than a consequence of it, so the next reader
        of the contract does not repeat the change and then relax those two
        assertions to make room for it.

        The verdict contract binds the REPORTING verbs. ``self-address``,
        ``--help`` and the ``--any-live-only`` sub-mode are payload queries.
        """
        p = _run(tmp_path, "self-address")
        assert _verdict(p) == "", (
            "self-address emitted a FLOW_WAVE: verdict - that breaks "
            "ADDR=$(flow-wave-registry.sh self-address) for every caller"
        )
        assert len(p.stdout.strip().splitlines()) == 1, (
            "self-address stdout must stay a single capturable line"
        )

    def test_a_corrupt_registry_update_emits_a_verdict(self, tmp_path: Path) -> None:
        """A registry write that FAILED must not be reported as success.

        This started as "the with_lock paths exit 3 with no verdict". Measured,
        that premise was wrong and the truth is worse. The ``exit 3`` happens
        inside the ``with_lock`` SUBSHELL and nothing read its status, so the
        script carried on: with a corrupt ``registry.json``, ``register``
        printed ``FLOW_WAVE: registered`` and exited **0** while the update had
        failed and NOTHING was recorded.

        So exit 3 never reached a caller, and there was no "documented exit
        code" to preserve - the observable behaviour was a confident false
        success. That is the same species as the rest of #1190 and the most
        severe instance of it: the contract line is present, well-formed, and
        says the opposite of what happened.
        """
        reg = tmp_path / "reg"
        reg.mkdir(parents=True, exist_ok=True)
        (reg / "registry.json").write_text("{ this is not json")
        p = _run(tmp_path, "register", "A", "--wave", "cpp")
        assert p.returncode == 3
        assert _verdict(p) == "error", "a corrupt-registry refusal emitted no verdict"


@requires_tools
class TestASharedParentCwdDoesNotMaskAFileLaneCollision:
    """#1190, found while working the issue: the overlap detector goes quiet
    exactly when it is most needed.

    ``report_overlap`` is an elif chain - ONE warning per pair - and the
    worktree arm sits above the file-lane arm. That precedence is deliberate
    and documented: a real nested worktree IS a stronger statement about a
    pair. But ``cwd_is_shared_parent`` exists precisely to identify a worktree
    match that is an ARTEFACT of registering before cutting a worktree, and its
    own comment claims such a false positive "never changes a verdict".

    It does. It silences the file-lane arm for that pair. And because the
    lane-less exemption requires an EMPTY file lane, declaring the lane you
    were granted is what loses you the exemption - so declaring a lane made
    collision detection strictly WORSE than declaring nothing, at the exact
    moment a lane is handed over.

    Observed in production: an orchestrator granted ``docs/scripts.md`` to
    three roles at once and told a worker in writing that two files were free
    while another role held them, then concluded it had failed to re-read the
    roster. The roster could not have told it.
    """

    def _register_pair(self, tmp: Path, cwd_a: Path, cwd_b: Path) -> None:
        for (role, pid, session), cwd in (
            ((("A"), SELF_PID, SELF_SESSION), cwd_a),
            ((("B"), OTHER_PID, OTHER_SESSION), cwd_b),
        ):
            _run(
                tmp, "register", role, "--wave", "cpp",
                "--socket", f"uds:/tmp/{role}.sock",
                "--repo", "/repo", "--cwd", str(cwd), "--files", "shared.py",
                pid=pid, session=session,
            )

    def test_a_shared_parent_cwd_does_not_mask_a_file_lane_overlap(
        self, tmp_path: Path
    ) -> None:
        """THE RED CASE. Two live roles declare the SAME file in the same repo.
        Role A's cwd is a shared projects parent - two checkouts under it - and
        therefore nests over role B's worktree.

        Pre-fix this reports only "same/nested worktrees" and never names
        ``shared.py``, so a reader who tidies the cwd sees the pair go clean
        while the real collision remains.
        """
        parent = tmp_path / "projects"
        (parent / "one" / ".git").mkdir(parents=True)
        (parent / "two" / ".git").mkdir(parents=True)
        worktree = parent / "repo-issue-1"
        worktree.mkdir()

        self._register_pair(tmp_path, parent, worktree)
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")

        assert "overlapping FILE LANES" in p.stdout, (
            "the file-lane collision was masked by a worktree match that "
            "cwd_is_shared_parent already knows is an artefact"
        )
        assert "shared.py" in p.stdout, "the colliding path was never named"

    def test_a_real_nested_worktree_pair_still_reports_the_worktree_collision(
        self, tmp_path: Path
    ) -> None:
        """The guard on the other side, so the fix cannot over-suppress.

        Here the nesting is REAL - neither cwd is a shared projects parent -
        so the worktree arm must still fire and keep its precedence. A fix that
        simply stopped trusting the worktree arm would pass the test above and
        silently break this one, which is the oscillation this pair pins.
        """
        outer = tmp_path / "wt"
        inner = outer / "inner"
        inner.mkdir(parents=True)

        self._register_pair(tmp_path, outer, inner)
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")

        assert "same/nested worktrees" in p.stdout, (
            "a genuine nested-worktree collision stopped being reported"
        )

    def test_a_real_checkout_with_submodules_is_not_treated_as_a_projects_parent(
        self, tmp_path: Path
    ) -> None:
        """#1190 round 2, found by counter-model review.

        ``cwd_is_shared_parent``'s second signature is "contains 2+ git
        checkouts", a heuristic for the ~/Projects shape. A REAL checkout
        holding two submodules satisfies it too. That is harmless at its other
        call sites, which only print an advisory line - but in the artefact
        predicate it would stand down a worktree warning between a genuine
        checkout and a role working inside it.

        A suppressed TRUE warning is precisely what this whole change exists to
        stop, so the fix that removes one blind spot must not open another. The
        nested-worktree guard above uses EMPTY directories and cannot see this
        case, which is why it gets its own.
        """
        checkout = tmp_path / "realrepo"
        (checkout / ".git").mkdir(parents=True)
        (checkout / "sub1" / ".git").mkdir(parents=True)
        (checkout / "sub2" / ".git").mkdir(parents=True)
        inner = checkout / "workdir"
        inner.mkdir()

        for (role, pid, session), cwd, files, issue in (
            (("A", SELF_PID, SELF_SESSION), checkout, "a.py", "11"),
            (("B", OTHER_PID, OTHER_SESSION), inner, "b.py", "22"),
        ):
            _run(
                tmp_path, "register", role, "--wave", "cpp",
                "--socket", f"uds:/tmp/{role}.sock",
                "--repo", "/repo", "--cwd", str(cwd),
                "--files", files, "--issue", issue,
                pid=pid, session=session,
            )
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")

        assert "same/nested worktrees" in p.stdout, (
            "a genuine shared checkout was exempted as a pre-worktree artefact "
            "because it happens to contain two submodules"
        )

    def test_a_directory_inside_a_checkout_is_not_a_projects_parent(
        self, tmp_path: Path
    ) -> None:
        """#1190 round 3, from the re-review.

        Protecting only the checkout ROOT was not enough. Given ``/repo/.git``
        with submodules at ``/repo/modules/one`` and ``/repo/modules/two``, the
        directory ``/repo/modules`` has no ``.git`` of its own, differs from the
        declared repo, and still satisfies the two-child-checkouts heuristic -
        so a pair working there was exempted and a genuine nested collision went
        unreported.

        Anywhere INSIDE a checkout is a lane, not a projects parent.
        """
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        modules = repo / "modules"
        (modules / "one" / ".git").mkdir(parents=True)
        (modules / "two" / ".git").mkdir(parents=True)
        inner = modules / "workdir"
        inner.mkdir()

        for (role, pid, session), cwd, files, issue in (
            (("A", SELF_PID, SELF_SESSION), modules, "a.py", "11"),
            (("B", OTHER_PID, OTHER_SESSION), inner, "b.py", "22"),
        ):
            _run(
                tmp_path, "register", role, "--wave", "cpp",
                "--socket", f"uds:/tmp/{role}.sock",
                "--repo", str(repo), "--cwd", str(cwd),
                "--files", files, "--issue", issue,
                pid=pid, session=session,
            )
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")

        assert "same/nested worktrees" in p.stdout, (
            "a directory inside a checkout was treated as a projects parent"
        )
