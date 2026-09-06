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
- The socket-file liveness fallback is uds-only and says so (#689); on other
  transports liveness rests on ``kill -0`` alone rather than on a test that
  cannot pass.
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


@requires_tools
class TestLivenessSecondaryProofIsUdsOnly:
    """The socket-file fallback states its precondition (#689).

    It used to strip `uds:` unconditionally and stat the remainder, so on a
    `bridge:` address it tested for a file literally named `bridge:session_...`
    - always false, so the fallback was silently inert rather than absent.
    Behaviour is preserved for uds; the non-uds gap becomes explicit.
    """

    def test_uds_socket_file_still_proves_liveness_for_a_dead_pid(self, tmp_path: Path) -> None:
        import socket as _socket

        sock_path = tmp_path / "live.sock"
        s = _socket.socket(_socket.AF_UNIX)
        try:
            s.bind(str(sock_path))
        except OSError as exc:  # path too long for AF_UNIX on this box
            pytest.skip(f"cannot bind AF_UNIX socket here: {exc}")
        try:
            _run(tmp_path, "register", "1", "--socket", f"uds:{sock_path}", pid="999999")
            p = _run(tmp_path, "list", live="none")
            assert "[live," in p.stdout
        finally:
            s.close()

    def test_non_uds_address_reads_stale_without_consulting_a_file(self, tmp_path: Path) -> None:
        _run(tmp_path, "register", "1", "--socket", "bridge:session_01RLEabc", pid="999998")
        p = _run(tmp_path, "list", live="none")
        assert p.returncode == 0
        assert "[stale," in p.stdout


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

    def test_comparison_is_exact_not_prefix_containment(self, tmp_path: Path) -> None:
        """Deliberately narrow: a comparison that guesses invents collisions
        nobody declared, and this warning has to be believed."""
        self._pair(tmp_path, "docs/", "docs/y.md")
        p = _run(tmp_path, "list", "--wave", "cpp", live=f"{SELF_PID}:{OTHER_PID}")
        assert "overlapping FILE LANES" not in p.stdout

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
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        _mailbox(tmp_path, "watch", "--role", "worker-H", "--wave", "cpp", "--timeout", "0", "--consume")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert "watch=armed" in _row(p, "worker-H")
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "0"
        assert "WATCH: live role(s)" not in p.stdout

    def test_a_decayed_heartbeat_reads_stale_with_its_age(self, tmp_path: Path) -> None:
        """`stale` and `absent` are different answers - a watch that DIED is not
        one that was never armed - so the age is always printed for the reader
        to judge which.
        """
        _run(tmp_path, "register", "worker-H", "--wave", "cpp", "--socket", "uds:/tmp/h.sock")
        _mailbox(tmp_path, "send", "--wave", "cpp", "--to", "worker-H", "--body", "your lane")
        # Armed 42 minutes before the registry's pinned "now" of 1700000000.
        _mailbox(tmp_path, "watch", "--role", "worker-H", "--wave", "cpp",
                 "--timeout", "0", "--consume", now="1699997480")
        p = _run(tmp_path, "list", "--wave", "cpp", live=SELF_PID)
        assert "watch=stale(42m)" in _row(p, "worker-H")
        assert _detail(p, "FLOW_WAVE_WATCH_UNARMED") == "1"
        assert "worker-H(stale 42m)" in p.stdout

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
        assert entry["watch"] == {"state": "absent", "age_secs": None}
        assert entry["mailbox"]["rev"] == 1
        assert entry["mailbox"]["cursor"] == 0
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
