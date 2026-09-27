"""The cross-run supervise sweep (issue #1271): it reaps what a DEAD run left, and nothing else.

`tests/supervise_reap.py` reaps inside the run that started a daemon. A run
killed mid-test never reaches that code, and the daemon it leaves re-arms
itself indefinitely (#814) - one was measured at 21.8 hours old. The sweep in
`tests/conftest.py`'s `pytest_sessionstart` is the caller that runs when no
test owns the pid any more.

A sweep that kills processes is only as safe as its predicate, so the spared
cases below matter as much as the reaped one: a live owner, a missing marker
and a non-daemon argv must each survive it.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

import tests.supervise_reap as reap
from tests.supervise_reap import (
    OWNER_ENV,
    SweepUnavailable,
    _environ_value,
    orphaned_supervise_daemons,
    owner_gone,
    owner_marker,
    pid_alive,
    sweep_orphaned_supervise_daemons,
)

ROOT = Path(__file__).resolve().parents[1]
MAILBOX = ROOT / "scripts" / "flow-wave-mailbox.sh"

requires_proc = pytest.mark.skipif(
    not Path("/proc/self/environ").exists(), reason="requires a Linux-style /proc"
)

#: Every sweep here is scoped with `only=` to the test's own fixture: the tests
#: run concurrently, and an unscoped sweep reaps a neighbouring test's orphan.
#:
#: And the fixtures carry a PRIVATE marker name, never OWNER_ENV: a pytest
#: session starting anywhere on the host sweeps OWNER_ENV at startup, and would
#: otherwise reap this file's dead-owner fixture mid-test (counter-model review).
TEST_OWNER_ENV = f"CPP_SWEEPTEST_OWNER_{os.getpid()}"
#:
#: This process, but with a start time it never had: the #1228 "reused pid"
#: shape, which must read as GONE. Deterministic, unlike waiting for a real pid
#: to die and hoping nothing reuses it before the sweep looks.
DEAD_OWNER = f"{os.getpid()}:1"


def _fake_daemon(
    tmp_path: Path, verb: str, marker: str | None,
    body: str = "sleep 300\n", own_group: bool = True,
) -> subprocess.Popen:
    """A process with the daemon's exact argv shape that only sleeps.

    Launched in its own session, as `supervise` launches the real one, so the
    sweep's group kill takes the `sleep` with it.
    """
    script = tmp_path / f"{verb}-{marker is not None}" / "flow-wave-mailbox.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(body, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != OWNER_ENV}
    if marker is not None:
        env[TEST_OWNER_ENV] = marker
    proc = subprocess.Popen(
        ["bash", str(script), verb, "--role", "1", "--wave", "testwave-sweep"],
        env=env, cwd=str(tmp_path), start_new_session=own_group,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # The environ is readable once exec has happened; wait for the argv to show.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            if verb.encode() in Path(f"/proc/{proc.pid}/cmdline").read_bytes():
                break
        except OSError:
            pass
        time.sleep(0.02)
    return proc


def _candidates() -> list[int]:
    return [pid for pid, _start in orphaned_supervise_daemons(owner_env=TEST_OWNER_ENV)]


def _sweep(pid: int):
    return sweep_orphaned_supervise_daemons(
        term_grace=2, kill_grace=2, only={pid}, owner_env=TEST_OWNER_ENV
    )


def _cleanup(*procs: subprocess.Popen) -> None:
    for proc in procs:
        try:
            if os.getpgid(proc.pid) == proc.pid:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()  # shares OUR group - never killpg it
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


@requires_proc
def test_the_sweep_reaps_a_daemon_whose_run_is_gone(tmp_path: Path) -> None:
    """The positive control: the shape of the 21.8-hour escapee."""
    orphan = _fake_daemon(tmp_path, "__supervise_daemon", DEAD_OWNER)
    try:
        assert orphan.pid in _candidates()
        result = _sweep(orphan.pid)
        assert orphan.pid in result.reaped, result
        assert orphan.pid not in result.survivors
        orphan.wait(timeout=10)
        assert not pid_alive(orphan.pid)
    finally:
        _cleanup(orphan)


@requires_proc
@pytest.mark.parametrize(
    ("verb", "marker", "why"),
    [
        ("__supervise_daemon", "LIVE", "its run is still alive - another suite, mid-test"),
        ("__supervise_daemon", None, "no marker - not started by this suite, or by a test that built its env from scratch"),
        ("watch", DEAD_OWNER, "not a supervise daemon at all"),
    ],
    ids=["live-owner", "no-marker", "not-a-daemon"],
)
def test_the_sweep_spares_everything_else(
    tmp_path: Path, verb: str, marker: str | None, why: str
) -> None:
    """Each of the three conditions, removed alone, must be enough to spare it."""
    spared = _fake_daemon(tmp_path, verb, owner_marker() if marker == "LIVE" else marker)
    try:
        assert spared.pid not in _candidates(), why
        result = _sweep(spared.pid)
        assert spared.pid not in result.reaped, why
        assert spared.poll() is None, f"the sweep killed a process it must spare: {why}"
    finally:
        _cleanup(spared)


@requires_proc
def test_an_owner_that_cannot_be_read_is_spared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unreadable is not dead (counter-model review, #1271).

    DEAD_OWNER names this live process with a wrong start time, so it reads
    GONE whenever its stat is readable. Make the stat unreadable while the
    `/proc` entry stays: the old `pid_alive`-based test read that as dead.
    """
    assert owner_gone(DEAD_OWNER), "precondition: readable, this owner is gone"
    monkeypatch.setattr(reap, "_proc_fields", lambda pid: None)
    assert not owner_gone(DEAD_OWNER)


@requires_proc
def test_a_pid_recycled_after_discovery_is_not_signalled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Identity is re-read before the kill, not trusted from discovery.

    Discovery is made to report the fixture with a start time it does not have -
    exactly what a pid recycled into a new process looks like by its turn.
    """
    orphan = _fake_daemon(tmp_path, "__supervise_daemon", DEAD_OWNER)
    try:
        assert orphan.pid in _candidates(), "precondition: it really is an orphan"
        monkeypatch.setattr(
            reap, "orphaned_supervise_daemons",
            lambda **_kw: [(orphan.pid, "not-its-start-time")],
        )
        result = _sweep(orphan.pid)
        assert orphan.pid not in result.reaped
        assert orphan.poll() is None, "a process that no longer matches was signalled"
    finally:
        _cleanup(orphan)


@requires_proc
def test_identity_is_rechecked_before_the_kill_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pid recycled DURING the TERM grace must not receive the SIGKILL.

    The fixture ignores SIGTERM, so it is still alive when escalation comes.
    Identity is made to change after the first check - the recycled-pid shape
    one step later than the test above. Pass 1 of this sweep re-checked only
    on entry and then SIGKILLed whatever held the pid (counter-model review).
    """
    orphan = _fake_daemon(
        tmp_path, "__supervise_daemon", DEAD_OWNER,
        body="trap '' TERM\nwhile :; do sleep 1; done\n",
    )
    try:
        start = dict(orphaned_supervise_daemons(owner_env=TEST_OWNER_ENV))[orphan.pid]
        real = reap._orphan_identity
        calls = {"n": 0}

        def identity_turns_after_the_first_check(pid: int, owner_env: str):
            calls["n"] += 1
            return real(pid, owner_env) if calls["n"] == 1 else "someone-else"

        monkeypatch.setattr(reap, "_orphan_identity", identity_turns_after_the_first_check)
        verdict = reap._sweep_kill(orphan.pid, start, TEST_OWNER_ENV, 1.0, 1.0)
        assert calls["n"] == 2, "identity was not re-read before the escalation"
        assert verdict is True  # from the sweep's view the orphan is gone
        assert orphan.poll() is None, "the KILL went to a process that was no longer the orphan"
    finally:
        _cleanup(orphan)


@requires_proc
def test_a_candidate_outside_its_own_process_group_is_never_signalled(tmp_path: Path) -> None:
    """The no-`setsid` shape shares its launcher's group; a group kill would hit
    the launcher, and per-pid kills reopen the recycling window. Left alone."""
    orphan = _fake_daemon(tmp_path, "__supervise_daemon", DEAD_OWNER, own_group=False)
    try:
        assert orphan.pid in _candidates(), "precondition: it is an orphan by every other test"
        result = _sweep(orphan.pid)
        assert orphan.pid in result.survivors and orphan.pid not in result.reaped
        assert orphan.poll() is None
    finally:
        _cleanup(orphan)


def test_an_unreadable_process_table_is_not_an_empty_sweep(tmp_path: Path) -> None:
    """Could-not-look must not render as looked-and-found-nothing."""
    with pytest.raises(SweepUnavailable):
        orphaned_supervise_daemons(proc_root=tmp_path / "no-proc-here")
    empty = tmp_path / "empty-proc"
    empty.mkdir()
    assert orphaned_supervise_daemons(proc_root=empty) == [], "an empty table is an ordinary zero"


@requires_proc
def test_owner_gone_reads_a_reused_pid_as_gone_and_never_errs_toward_killing() -> None:
    assert owner_gone(DEAD_OWNER), "a different start time is a different process"
    assert not owner_gone(owner_marker()), "this very process is alive"
    assert not owner_gone(f"{os.getpid()}:-"), "an unreadable start time is judged on the pid"
    assert not owner_gone("not-a-marker"), "unparseable is not evidence of death"
    assert not owner_gone("1:1"), "init is never an owner"


@requires_proc
def test_this_process_carries_its_own_marker() -> None:
    """The conftest names THIS process - under xdist, the worker, not the controller."""
    assert os.environ.get(OWNER_ENV) == owner_marker()


@requires_proc
def test_a_real_supervise_daemon_inherits_the_marker_through_setsid(tmp_path: Path) -> None:
    """The end-to-end premise: the marker survives the detach.

    Without this, the fake daemons above prove a predicate that no real daemon
    would ever satisfy, and the sweep would be blind while its tests stayed green.
    """
    env = os.environ.copy()
    env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
    subprocess.run(
        ["bash", str(MAILBOX), "supervise", "--role", "1", "--wave", "testwave-sweep",
         "--timeout", "5", "--interval", "1"],
        env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=30, check=False,
    )
    pidfile = tmp_path / "mb" / "testwave-sweep" / ".supervise-1.pid"
    deadline = time.monotonic() + 10
    while not pidfile.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert pidfile.exists(), "supervise never wrote a pidfile"
    pid = int(pidfile.read_text().strip())
    # The pidfile is written with `$!`, the forked child, which then execs
    # `setsid` and `bash`. Read its environment only once it IS the daemon -
    # mid-exec the read came back empty about 1 run in 10 under `-n 4`.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not reap._is_daemon_argv(reap._argv(pid)):
        time.sleep(0.02)
    assert reap._is_daemon_argv(reap._argv(pid)), "the pidfile's process never became the daemon"
    # The autouse reaper in tests/conftest.py kills it at teardown.
    assert _environ_value(pid, OWNER_ENV) == owner_marker()
