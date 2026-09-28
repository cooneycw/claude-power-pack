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
import uuid
from pathlib import Path

import pytest

import tests.supervise_reap as reap
from tests.supervise_reap import (
    OWNER_ENV,
    SweepUnavailable,
    _descendants,
    _environ_value,
    _proc_fields,
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


#: A PRIVATE variable naming the file a fake daemon writes once it is READY.
#: Not OWNER_ENV-shaped: the sweep reads markers from the environment, and this
#: must never be mistaken for one.
READY_ENV = "CPP_SWEEPTEST_FAKE_READY"
#: One bound for every wait in this fixture - the bound the argv wait already had.
FIXTURE_DEADLINE = 10.0


def _fake_daemon(
    tmp_path: Path, verb: str, marker: str | None,
    body: str = "sleep 300\n", own_group: bool = True, setup: str = "",
    ready_timeout: float = FIXTURE_DEADLINE,
) -> subprocess.Popen:
    """A process with the daemon's exact argv shape that only sleeps.

    Launched in its own session, as `supervise` launches the real one, so the
    sweep's group kill takes the `sleep` with it.

    READY MEANS `setup` HAS RUN, not that the process exists (issue #1297). The
    argv shows in /proc the moment exec happens - before bash has read a single
    line - so a test whose child installs `trap '' TERM` could send TERM into
    that gap: the child died at once, the sweep never escalated, and the
    identity test failed with `assert 1 == 2` for a startup race rather than a
    broken check (reproduced by delaying the trap 0.3s). So the child writes a
    ready file AFTER `setup`, and this returns only once it exists. A child that
    exits first, or never signals within the bound, FAILS the test - after its
    group is killed - rather than handing the test a process in an unknown state.
    """
    script = tmp_path / f"{verb}-{marker is not None}" / "flow-wave-mailbox.sh"
    script.parent.mkdir(parents=True, exist_ok=True)
    # ONE ready signal per CHILD (counter-model review): a unique path, and the
    # child writes its own pid, which must match - so neither a reused path nor a
    # leftover file from an earlier child can stand in for this child's setup.
    ready = script.parent / f"ready-{uuid.uuid4().hex}"
    script.write_text(f'{setup}printf %s "$$" > "${READY_ENV}"\n{body}', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != OWNER_ENV}
    env[READY_ENV] = str(ready)
    if marker is not None:
        env[TEST_OWNER_ENV] = marker
    proc = subprocess.Popen(
        ["bash", str(script), verb, "--role", "1", "--wave", "testwave-sweep"],
        env=env, cwd=str(tmp_path), start_new_session=own_group,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    def give_up(why: str) -> None:
        _cleanup(proc)
        pytest.fail(f"fake daemon did not become ready: {why}", pytrace=False)

    # The argv is visible once exec has happened: the sweep matches on it, so it
    # is a precondition - and a timeout here is a failure, not a fall-through.
    deadline = time.monotonic() + FIXTURE_DEADLINE
    while True:
        try:
            if verb.encode() in Path(f"/proc/{proc.pid}/cmdline").read_bytes():
                break
        except OSError:
            pass
        if proc.poll() is not None:
            give_up(f"it exited with {proc.returncode} before its argv appeared")
        if time.monotonic() >= deadline:
            give_up(f"its argv did not appear within {FIXTURE_DEADLINE:g}s")
        time.sleep(0.02)
    # Then the explicit signal that `setup` has run.
    deadline = time.monotonic() + ready_timeout
    while not (ready.exists() and ready.read_text() == str(proc.pid)):
        if proc.poll() is not None:
            give_up(f"it exited with {proc.returncode} before signalling ready")
        if time.monotonic() >= deadline:
            give_up(f"no ready signal within {ready_timeout:g}s")
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
                _kill_subtree(proc)  # shares OUR group - never killpg it
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


def _kill_subtree(proc: subprocess.Popen) -> None:
    """Kill a shared-group fixture AND everything under it (issue #1343).

    `proc.kill()` alone reaches only the bash parent: bash does not exec its
    last command, so the `sleep 300` child survived, was reparented to the
    subreaper, and stayed in the runner's process group - one orphan per full
    suite run. The parent is STOPPED first so it can neither fork a
    replacement child nor reap one (which would free its pid for reuse) while
    the subtree is enumerated and killed, deepest first.
    """
    os.kill(proc.pid, signal.SIGSTOP)
    # SIGSTOP is asynchronous: enumerating before it lands leaves the fork
    # window open (counter-model review). Wait for the stopped state - or for
    # the parent to be gone, which leaves nothing to fork. A bound that expires
    # still kills; it only means the window was not provably shut.
    deadline = time.monotonic() + FIXTURE_DEADLINE
    while (fields := _proc_fields(proc.pid)) is not None and fields[0] not in ("T", "t", "Z"):
        if time.monotonic() >= deadline:
            break
        time.sleep(0.001)
    for pid in reversed(_descendants(proc.pid)):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    proc.kill()


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
        ("__supervise_daemon", None, "no marker - not ours, or a test that built its env from scratch"),
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
        setup="trap '' TERM\n", body="while :; do sleep 1; done\n",
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
def test_the_fixture_returns_only_after_setup_has_run(tmp_path: Path) -> None:
    """THE #1297 REGRESSION: a TERM sent the moment the fixture returns must
    find the trap already installed.

    The setup is deliberately SLOW (0.3s before the trap), which is the startup
    a loaded CI host produces. On the pre-#1297 fixture - which returned once
    the argv appeared - this child died of that TERM (returncode -15), 3 of 3.
    """
    child = _fake_daemon(
        tmp_path, "__supervise_daemon", DEAD_OWNER,
        setup="sleep 0.3\ntrap '' TERM\n", body="while :; do sleep 1; done\n",
    )
    try:
        os.killpg(child.pid, signal.SIGTERM)
        # Bounded by the child's own exit, not by a guess at scheduling: if the
        # TERM was fatal, wait() returns; if it was ignored, it times out.
        with pytest.raises(subprocess.TimeoutExpired):
            child.wait(timeout=1.0)
        assert child.poll() is None, f"the TERM was fatal: {child.returncode}"
    finally:
        _cleanup(child)


@requires_proc
def test_a_second_child_waits_for_its_own_ready_signal(tmp_path: Path) -> None:
    """The ready signal belongs to ONE child (counter-model review, #1297).

    Same tmp_path, verb and marker twice: in the first cut both children shared
    a ready path, so the second inherited the first's signal and was returned
    before its own trap existed.
    """
    first = _fake_daemon(tmp_path, "__supervise_daemon", DEAD_OWNER)
    second = None
    try:
        second = _fake_daemon(
            tmp_path, "__supervise_daemon", DEAD_OWNER,
            setup="sleep 0.3\ntrap '' TERM\n", body="while :; do sleep 1; done\n",
        )
        os.killpg(second.pid, signal.SIGTERM)
        with pytest.raises(subprocess.TimeoutExpired):
            second.wait(timeout=1.0)
    finally:
        _cleanup(first, *([second] if second else []))


@requires_proc
def test_a_child_that_exits_before_ready_fails_clearly(tmp_path: Path) -> None:
    """Early exit is a clear fixture failure, never a half-started test.

    Matched on the exit, not the phase: `exit 3` can finish before the argv is
    even observed (a zombie's cmdline is empty), and both phases report it.
    """
    with pytest.raises(pytest.fail.Exception, match="exited with 3 before"):
        _fake_daemon(tmp_path, "__supervise_daemon", DEAD_OWNER, setup="exit 3\n")


@requires_proc
def test_a_child_that_never_becomes_ready_fails_clearly_and_is_reaped(tmp_path: Path) -> None:
    """A child stuck in setup fails within the bound, and is not left running."""
    pidfile = tmp_path / "stuck.pid"
    with pytest.raises(pytest.fail.Exception, match=r"no ready signal within 0\.5s"):
        _fake_daemon(
            tmp_path, "__supervise_daemon", DEAD_OWNER,
            setup=f"echo $$ > {pidfile}\nsleep 300\n", ready_timeout=0.5,
        )
    pid = int(pidfile.read_text())
    assert not pid_alive(pid), "the fixture failed but left its child running"


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


def _kin(tag: str) -> list[int]:
    """Live processes carrying this fixture's inherited KIN_ENV=tag, by any pid.

    Found by marker rather than by a pid list captured beforehand, so a child
    forked DURING cleanup - one no snapshot could name - is still found; and the
    tag is unique per test, so a neighbour's process can never be counted.
    """
    needle = f"{KIN_ENV}={tag}".encode()
    uid = os.getuid()
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue  # a fixture child runs as us; another uid is not kin
            environ = (entry / "environ").read_bytes()
        except (FileNotFoundError, ProcessLookupError):
            continue  # exited between listing and reading: not a survivor
        except OSError as exc:
            # One of OURS that cannot be read is unobserved, not absent: an
            # empty result must not certify a population it could not see
            # (counter-model review).
            pytest.fail(f"could not read pid {entry.name}'s environment: {exc}", pytrace=False)
        if needle in environ.split(b"\0") and pid_alive(int(entry.name)):
            found.append(int(entry.name))
    return found


#: A PRIVATE variable the regression fixture exports before forking, so every
#: descendant inherits it: the population the cleanup check examines.
KIN_ENV = "CPP_SWEEPTEST_KIN"


@requires_proc
@pytest.mark.parametrize(
    "body",
    ["sleep 300\n", "while :; do sleep 300; done\n"],
    ids=["one-child", "respawning-child"],
)
def test_cleanup_of_a_shared_group_fixture_leaves_no_descendant(tmp_path: Path, body: str) -> None:
    """The shared-group cleanup must not orphan the fixture's children (issue #1343).

    Red on the pre-fix `_cleanup`, which killed only the bash parent: its
    `sleep 300` outlived every full suite run, reparented to the subreaper.
    Survivors are found by inherited marker, not by pids captured beforehand,
    so a replacement forked during cleanup would be counted too (counter-model
    review). What this does NOT prove: that the SIGSTOP in `_kill_subtree` is
    needed. Measured with it removed, the respawning case still passed 5 of 5 -
    bash does not fork its replacement inside the microseconds before the parent
    is killed, so that race cannot be forced from here. The SIGSTOP closes it by
    construction; this test pins the leak the issue measured.
    """
    tag = uuid.uuid4().hex
    proc = _fake_daemon(
        tmp_path, "__supervise_daemon", DEAD_OWNER,
        body=f"export {KIN_ENV}={tag}\n{body}", own_group=False,
    )
    deadline = time.monotonic() + FIXTURE_DEADLINE
    while not [pid for pid in _kin(tag) if pid != proc.pid]:
        if time.monotonic() >= deadline:
            _cleanup(proc)
            pytest.fail("precondition: the fixture never forked its child", pytrace=False)
        time.sleep(0.02)

    _cleanup(proc)

    survivors = _kin(tag)
    try:
        assert not survivors, f"_cleanup left descendants running: {survivors}"
    finally:
        for pid in survivors:
            os.kill(pid, signal.SIGKILL)


@requires_proc
def test_an_unreadable_process_of_ours_fails_the_cleanup_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other verdict for `_kin`: our own process unreadable is not "no survivor".

    This test's own process is always one of ours in /proc, so with every
    environ read refused the scan must fail rather than return an empty list.
    """
    def refuse(self: Path) -> bytes:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "read_bytes", refuse)
    with pytest.raises(pytest.fail.Exception, match="could not read pid"):
        _kin(uuid.uuid4().hex)


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
