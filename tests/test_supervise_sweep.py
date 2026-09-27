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

from tests.supervise_reap import (
    OWNER_ENV,
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
#: This process, but with a start time it never had: the #1228 "reused pid"
#: shape, which must read as GONE. Deterministic, unlike waiting for a real pid
#: to die and hoping nothing reuses it before the sweep looks.
DEAD_OWNER = f"{os.getpid()}:1"


def _fake_daemon(tmp_path: Path, verb: str, marker: str | None) -> subprocess.Popen:
    """A process with the daemon's exact argv shape that only sleeps.

    Launched in its own session, as `supervise` launches the real one, so the
    sweep's group kill takes the `sleep` with it.
    """
    script = tmp_path / f"{verb}-{marker is not None}" / "flow-wave-mailbox.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("sleep 300\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != OWNER_ENV}
    if marker is not None:
        env[OWNER_ENV] = marker
    proc = subprocess.Popen(
        ["bash", str(script), verb, "--role", "1", "--wave", "testwave-sweep"],
        env=env, cwd=str(tmp_path), start_new_session=True,
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


def _cleanup(*procs: subprocess.Popen) -> None:
    for proc in procs:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
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
        assert orphan.pid in orphaned_supervise_daemons()
        result = sweep_orphaned_supervise_daemons(term_grace=2, kill_grace=2, only={orphan.pid})
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
        assert spared.pid not in orphaned_supervise_daemons(), why
        result = sweep_orphaned_supervise_daemons(term_grace=2, kill_grace=2, only={spared.pid})
        assert spared.pid not in result.reaped, why
        assert spared.poll() is None, f"the sweep killed a process it must spare: {why}"
    finally:
        _cleanup(spared)


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
    # The autouse reaper in tests/conftest.py kills it at teardown.
    assert _environ_value(pid, OWNER_ENV) == owner_marker()
