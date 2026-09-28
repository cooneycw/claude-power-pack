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
from dataclasses import dataclass
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


#: A PRIVATE variable the regression fixture exports before forking, so every
#: descendant inherits it: the population the cleanup check examines.
KIN_ENV = "CPP_SWEEPTEST_KIN"

#: Everything the fixture's process tree runs: `bash` and the `sleep` it forks.
KIN_COMMS = frozenset({"bash", "sleep"})


@dataclass(frozen=True)
class _Fixture:
    """What a process must share with the fixture to possibly be one of its own."""

    pid: int
    pgid: int
    start: int  # /proc/<pid>/stat field 22, clock ticks since boot


def _stat(pid: int) -> tuple[str, int, int] | None:
    """``(comm, pgid, start)`` from /proc/<pid>/stat, or None if it is GONE.

    Readable for any process of ours even when its environ is refused, which is
    what lets an unreadable pid be judged at all. Anchored on the LAST ``)``:
    comm may contain spaces and parentheses. Only disappearance returns None;
    any other failure RAISES, because "could not identify it" is not "not
    ours" (counter-model review).
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    comm = raw[raw.index("(") + 1 : raw.rindex(")")]
    rest = raw[raw.rindex(")") + 2 :].split()
    return comm, int(rest[2]), int(rest[19])


def _fixture_of(proc: subprocess.Popen) -> _Fixture:
    fields = _stat(proc.pid)
    assert fields is not None, "precondition: the fixture is alive when first observed"
    return _Fixture(proc.pid, fields[1], fields[2])


def _could_be_kin(pid: int, fixture: _Fixture) -> bool:
    """Whether an UNREADABLE pid could be one of the fixture's (issue #1347).

    Every xdist worker shares one process group (measured: gw0-gw2 all in one
    pgid), so the group alone cannot tell a neighbour from the fixture. A
    candidate must ALSO have started no earlier than the fixture and run what the
    fixture runs. Stated residual, deliberately not closed: an unreadable
    `bash` or `sleep` of a NEIGHBOUR, in this group and started during this
    test, is still judged a candidate. bash and sleep are not non-dumpable, so
    their environ is not expected to be refused.
    """
    try:
        fields = _stat(pid)
    except (OSError, ValueError, IndexError):
        return True  # unidentifiable: judged conservatively as possibly ours
    if fields is None:
        return False
    comm, pgid, start = fields
    return comm in KIN_COMMS and pgid == fixture.pgid and start >= fixture.start


def _kin(tag: str, fixture: _Fixture) -> list[int]:
    """Live processes carrying this fixture's inherited KIN_ENV=tag, by any pid.

    Found by marker rather than by a pid list captured beforehand, so a child
    forked DURING cleanup - one no snapshot could name - is still found; and the
    tag is unique per test, so a neighbour's process can never be counted.

    An environ that cannot be read FAILS the check only for a pid that could be
    the fixture's own: that one is unobserved, not absent (counter-model review).
    An unreadable process that cannot be ours - another xdist worker's python,
    anything older than the fixture or running something else - is skipped;
    failing on it failed this test for someone else's process (issue #1347).
    What the verdict still cannot separate is `_could_be_kin`'s stated residual:
    an unreadable same-group `bash`/`sleep` started during this test fails the
    check conservatively, whoever owns it.
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
            if _could_be_kin(int(entry.name), fixture):
                pytest.fail(f"could not read pid {entry.name}'s environment: {exc}", pytrace=False)
            continue  # a neighbour's process: not ours to judge
        if needle in environ.split(b"\0") and pid_alive(int(entry.name)):
            found.append(int(entry.name))
    return found


def _reap_marked(tag: str) -> list[int]:
    """Best-effort SIGKILL of every live process carrying KIN_ENV=tag.

    The last line of every cleanup check, so a failure can never leak the
    fixture (issue #1347). It NEVER raises, and it NEVER signals a pid whose
    environ it could not read and match to this test's unique tag: an
    unreadable or unmarked process is skipped, not guessed at.
    """
    needle = f"{KIN_ENV}={tag}".encode()
    killed = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return killed
    for entry in entries:
        try:
            if not entry.name.isdigit():
                continue
            if needle not in (entry / "environ").read_bytes().split(b"\0"):
                continue
            os.kill(int(entry.name), signal.SIGKILL)
            killed.append(int(entry.name))
        except Exception:  # noqa: BLE001 - never raise from the last line of cleanup
            continue
    return killed


def _check_cleanup(tmp_path: Path, body: str) -> None:
    """Launch a shared-group fixture, clean it up, and assert nothing survived.

    Everything after the launch is inside try/finally (issue #1347): before,
    the precondition loop and the assertion called `_kin` outside it, so a
    raise there skipped `_cleanup` and leaked the `sleep 300` this check exists
    to prevent. The finally cleans up only a fixture that is still unreaped -
    a reaped pid may already belong to someone else - then reaps anything still
    carrying this test's marker.
    """
    tag = uuid.uuid4().hex
    proc = _fake_daemon(
        tmp_path, "__supervise_daemon", DEAD_OWNER,
        body=f"export {KIN_ENV}={tag}\n{body}", own_group=False,
    )
    try:
        fixture = _fixture_of(proc)
        deadline = time.monotonic() + FIXTURE_DEADLINE
        while not [pid for pid in _kin(tag, fixture) if pid != proc.pid]:
            if time.monotonic() >= deadline:
                pytest.fail("precondition: the fixture never forked its child", pytrace=False)
            time.sleep(0.02)

        _cleanup(proc)

        survivors = _kin(tag, fixture)
        assert not survivors, f"_cleanup left descendants running: {survivors}"
    finally:
        try:
            if proc.poll() is None:
                _cleanup(proc)
        finally:
            # Even when `_cleanup` itself raised (counter-model review). The
            # parent goes FIRST: its own environ does not carry the marker
            # (`export` reaches children only), and a live parent could fork a
            # replacement after the reaper's snapshot. SIGKILL through the
            # unreaped Popen handle cannot hit a recycled pid.
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=10)
            except Exception:  # noqa: BLE001 - the reaper below must still run
                pass
            _reap_marked(tag)


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
    _check_cleanup(tmp_path, body)


def _refuse_environ_of(monkeypatch: pytest.MonkeyPatch, pid: int) -> list[int]:
    """Make exactly one pid's environ unreadable; returns a list of refusals made."""
    refused: list[int] = []
    real = Path.read_bytes
    target = Path(f"/proc/{pid}/environ")

    def read_bytes(self: Path) -> bytes:
        if self == target:
            refused.append(pid)
            raise PermissionError(13, "Permission denied", str(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    return refused


@requires_proc
def test_an_unreadable_neighbour_does_not_fail_the_cleanup_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue #1347: another process of our uid that cannot be read is not ours.

    The deterministic form of the full-suite failure: under `-n 4`, an xdist
    neighbour's environ was refused and `_kin` failed on it. Red on main, whose
    `_kin` failed on ANY unreadable process of the uid.
    """
    neighbour = os.getppid()
    assert os.stat(f"/proc/{neighbour}").st_uid == os.getuid(), "precondition: same uid"
    here = _stat(os.getpid())
    assert here is not None
    fixture = _Fixture(os.getpid(), here[1], here[2] + 1)  # started after the neighbour
    assert not _could_be_kin(neighbour, fixture), "precondition: the neighbour is not a candidate"
    refused = _refuse_environ_of(monkeypatch, neighbour)

    assert _kin(uuid.uuid4().hex, fixture) == []
    assert refused == [neighbour], "precondition: the refusal branch was actually exercised"


@requires_proc
def test_an_unidentifiable_unreadable_process_fails_the_cleanup_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environ refused AND stat unreadable (not gone): unobserved, so the check fails.

    Before, any stat failure read as "not a candidate", and the scan skipped a
    process it could neither read nor identify (counter-model review).
    """
    neighbour = os.getppid()
    here = _stat(os.getpid())
    assert here is not None
    fixture = _Fixture(os.getpid(), here[1], here[2] + 1)
    refused = _refuse_environ_of(monkeypatch, neighbour)
    real_text = Path.read_text
    stat_path = Path(f"/proc/{neighbour}/stat")

    def read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == stat_path:
            raise PermissionError(13, "Permission denied", str(self))
        return real_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", read_text)
    with pytest.raises(pytest.fail.Exception, match="could not read pid"):
        _kin(uuid.uuid4().hex, fixture)
    assert refused == [neighbour], "precondition: the refusal branch was actually exercised"


@requires_proc
def test_an_unreadable_process_of_ours_fails_the_cleanup_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other verdict: the FIXTURE's own child, unreadable, is not "no survivor".

    Its environ is refused while it is alive, so an empty result would certify a
    population the scan could not see.
    """
    tag = uuid.uuid4().hex
    proc = _fake_daemon(
        tmp_path, "__supervise_daemon", DEAD_OWNER,
        body=f"export {KIN_ENV}={tag}\nsleep 300\n", own_group=False,
    )
    try:
        fixture = _fixture_of(proc)
        deadline = time.monotonic() + FIXTURE_DEADLINE
        while not (children := _descendants(proc.pid)):
            assert time.monotonic() < deadline, "precondition: the fixture forked its child"
            time.sleep(0.02)
        # Asserted from the raw stat fields, NOT through `_could_be_kin`: a
        # precondition that called the rule under test could not show the rule
        # being wrong, only itself failing.
        comm, pgid, start = _stat(children[0]) or ("", -1, -1)
        assert (comm, pgid) == ("sleep", fixture.pgid) and start >= fixture.start, (
            "precondition: the child shares the fixture's group, started after it, and runs sleep"
        )
        refused = _refuse_environ_of(monkeypatch, children[0])

        with pytest.raises(pytest.fail.Exception, match="could not read pid"):
            _kin(tag, fixture)
        assert refused, "precondition: the refusal branch was actually exercised"
    finally:
        monkeypatch.undo()
        try:
            if proc.poll() is None:
                _cleanup(proc)
        finally:
            _reap_marked(tag)


def _still_alive(pids: list[int]) -> list[int]:
    """The pids still alive after a bounded wait: SIGKILL is delivered
    asynchronously, so a just-killed pid can read as alive for an instant."""
    deadline = time.monotonic() + FIXTURE_DEADLINE
    while (alive := [pid for pid in pids if pid_alive(pid)]) and time.monotonic() < deadline:
        time.sleep(0.02)
    return alive


def _first_child(pid: int) -> list[int]:
    """Wait (bounded) for `pid` to fork, observed from the kernel, not by marker."""
    deadline = time.monotonic() + FIXTURE_DEADLINE
    while not (children := _descendants(pid)):
        assert time.monotonic() < deadline, "precondition: the fixture forked its child"
        time.sleep(0.02)
    return children


@requires_proc
def test_a_scan_that_raises_mid_check_still_reaps_the_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #1347: no failure path of the cleanup check may leak the fixture.

    `_kin` raises in the precondition loop, BEFORE `_cleanup` - the path that
    leaked the daemon and its `sleep 300` on main, where the loop sat outside
    any try/finally. It raises only once a real child exists, recorded from the
    kernel's child list, so "nothing leaked" is a statement about a process
    that was there (counter-model review).
    """
    import tests.test_supervise_sweep as module

    children: list[int] = []

    def boom(tag: str, fixture: _Fixture) -> list[int]:
        children.extend(_first_child(fixture.pid))
        raise RuntimeError("scan failed mid-check")

    monkeypatch.setattr(module, "_kin", boom)
    try:
        with pytest.raises(RuntimeError, match="scan failed mid-check"):
            module._check_cleanup(tmp_path, "sleep 300\n")
        assert children, "precondition: a real child existed when the check failed"
        survivors = _still_alive(children)
        assert not survivors, f"the failing check leaked the fixture's child: {survivors}"
    finally:
        for pid in children:
            try:
                if pid_alive(pid):
                    os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


@requires_proc
@pytest.mark.parametrize(
    "body",
    ["sleep 300\n", "while :; do sleep 300; done\n"],
    ids=["one-child", "respawning-child"],
)
def test_a_cleanup_that_raises_still_reaps_the_marked_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """The fallback runs even when `_cleanup` itself raises (counter-model review).

    The respawning body is the case a reaper that left the parent alive loses:
    it kills the `sleep`, and the loop forks another after the snapshot.
    """
    import tests.test_supervise_sweep as module

    children: list[int] = []
    tags: list[str] = []
    parents: list[int] = []
    real_kin = module._kin

    def watching_kin(tag: str, fixture: _Fixture) -> list[int]:
        if not children:
            tags.append(tag)
            parents.append(fixture.pid)
            children.extend(_first_child(fixture.pid))
        return real_kin(tag, fixture)

    def broken_cleanup(*procs: subprocess.Popen) -> None:
        raise RuntimeError("cleanup failed")

    monkeypatch.setattr(module, "_kin", watching_kin)
    monkeypatch.setattr(module, "_cleanup", broken_cleanup)
    try:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            module._check_cleanup(tmp_path, body)
        assert children, "precondition: a real child existed when cleanup failed"
        survivors = _still_alive(children)
        assert not survivors, f"the fallback reaper did not run: {survivors}"
        time.sleep(0.3)  # time for a surviving parent to fork a replacement
        respawned = _reap_marked(tags[0])
        assert not respawned, f"a replacement child outlived the fallback: {respawned}"
    finally:
        # This test's own backstop, independent of the code under test: when
        # that code is broken, a surviving parent and its marked children must
        # still not outlive the test. The parent is signalled only while its cwd
        # is still this test's tmp_path, so a recycled pid is never touched.
        for pid in parents:
            try:
                if os.readlink(f"/proc/{pid}/cwd") == str(tmp_path):
                    os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        for tag in tags:
            _reap_marked(tag)
        for pid in children:
            try:
                if pid_alive(pid):
                    os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


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
