"""State Z on a role's owner is not always death (issue #1691, after #1709).

`/proc/<pid>/stat` reports the state of the thread-group LEADER. A process
whose main thread has exited while another thread is still running reads `Z`
there - and `State: Z (zombie)` in `/proc/<pid>/status` - although it is alive
and can still do everything a session does. A reaped-pending zombie, the case
the state letter was meant to catch, has exactly one thread left.

Two wave helpers read the letter alone:

- `flow-wave-registry.sh` `pid_state` answered `zombie`, so the role read
  `stale` / `owner-zombie` and a second session could take it over without
  `--force`, announced as "is gone";
- `flow-wave-mailbox.sh` `owner_gone` answered gone, so a live session's armed
  watch quit after its first poll interval and the role read unlistened.

Both now apply the rule `flow-worktree-claim.sh` has carried since #1709: `Z`
counts as dead only when the thread count is 1, 0 or unreadable.

The cases, for BOTH scripts: a zombie leader with a live thread is alive (this
is the one that changed); a single-threaded zombie is dead; an unreadable
thread count is dead (fail safe); an ordinary live process is alive; a pid
that does not exist is gone.

HOW EACH SCRIPT IS REACHED.

- The registry honours `FLOW_WAVE_PROC_ROOT` for the stat line, so its cases
  are a fabricated stat line read through `get`. It still tests existence
  against the real `/proc`, so the fabricated entry is keyed by this test's own
  pid; the "does not exist" case uses a pid above the kernel's maximum.
- The mailbox has no proc-root hook. `owner_gone` and the one function it
  calls are lifted out of the script text and sourced with the literal `/proc/`
  replaced by a fixture directory - the function's own logic, pointed at files
  the test wrote. The lift is checked: both functions must be found, and the
  replacement must have happened.
- A fabricated line only proves the reader agrees with the author about what
  the kernel prints, so each script is also run against a REAL process whose
  main thread has exited. For the mailbox that process is the one that ARMS a
  real `watch`: before the fix the watch exits 10 `owner-gone` after one
  interval; now it runs to its timeout.

Nothing here sleeps to synchronise. The real process reports on a pipe once
its own leader reads `Z`, and is held open by the stdin the test owns.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import select
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.test_flow_wave_registry import _detail, _verdict
from tests.test_flow_wave_registry import _run as wave_run

ROOT = Path(__file__).resolve().parents[1]
MAILBOX = ROOT / "scripts" / "flow-wave-mailbox.sh"

# Drives the real helpers under `bash` (the registry needs `jq` and `flock`,
# the mailbox `flock`, `sed` and `awk`) and reads Linux procfs.
requires_linux_tools = pytest.mark.skipif(
    not sys.platform.startswith("linux")
    or not Path("/proc/self/stat").exists()
    or shutil.which("bash") is None
    or shutil.which("jq") is None
    or shutil.which("flock") is None
    or shutil.which("sed") is None
    or shutil.which("awk") is None,
    reason="requires Linux procfs and bash, jq, flock, sed and awk on PATH",
)

WAVE = "owner-liveness"
ROLE = "w1"
#: Above the largest pid a Linux kernel can be configured to hand out (2^22).
NO_SUCH_PID = 4194999

#: A process that reports, on stdout, once it is in the shape asked for, runs
#: one command if given, and then stays up until its stdin is closed.
#: LEADERLESS=1: the main thread exits and a worker carries on, so the leader
#: reads Z with more than one thread. LEADERLESS=0: an ordinary process.
OWNER_PROCESS = r"""
import ctypes, json, os, subprocess, sys, threading

LEADERLESS = os.environ["OWNER_LEADERLESS"] == "1"

def leader():
    with open("/proc/self/stat") as handle:
        fields = handle.read().rsplit(") ", 1)[1].split()
    return fields[0], int(fields[17])

def carry_on():
    while LEADERLESS and leader()[0] != "Z":
        os.sched_yield()
    report = dict(zip(("state", "threads"), leader()), pid=os.getpid())
    command = json.loads(os.environ.get("OWNER_COMMAND", "null"))
    if command:
        env = dict(os.environ, FLOW_WAVE_SESSION_PIDS=str(os.getpid()))
        done = subprocess.run(command, capture_output=True, text=True, env=env)
        report.update(rc=done.returncode, stdout=done.stdout, stderr=done.stderr)
        report.update(zip(("state_after", "threads_after"), leader()))
    os.write(1, (json.dumps(report) + "\n").encode())
    os.read(0, 1)
    os._exit(0)

worker = threading.Thread(target=carry_on)
worker.start()
if LEADERLESS:
    ctypes.CDLL(None).pthread_exit(None)
worker.join()
"""


class Owner:
    """A running OWNER_PROCESS and what it reported about itself."""

    def __init__(self, proc: subprocess.Popen[bytes], report: dict[str, object]) -> None:
        self.proc = proc
        self.report = report
        self.pid = proc.pid


def _start_owner(*, leaderless: bool, command: list[str] | None, env: dict[str, str]) -> Owner:
    if leaderless and not hasattr(ctypes.CDLL(None), "pthread_exit"):
        pytest.skip("this libc exposes no pthread_exit")
    full = {**os.environ, **env, "OWNER_LEADERLESS": "1" if leaderless else "0"}
    if command:
        full["OWNER_COMMAND"] = json.dumps(command)
    proc = subprocess.Popen(
        [sys.executable, "-c", OWNER_PROCESS],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=full,
    )
    assert proc.stdout is not None
    # Wait ON THE PIPE for the report; the bound only turns a hang into a failure.
    readable, _, _ = select.select([proc.stdout], [], [], 120)
    if not readable:
        proc.kill()
        proc.wait()
        pytest.fail("the owner process never reported")
    return Owner(proc, json.loads(proc.stdout.readline()))


def _stop_owner(owner: Owner) -> None:
    assert owner.proc.stdin is not None
    owner.proc.stdin.close()
    try:
        owner.proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        owner.proc.kill()
        owner.proc.wait()


@pytest.fixture
def leaderless_owner() -> Iterator[Owner]:
    """A LIVE process whose main thread has exited; preconditions asserted."""
    owner = _start_owner(leaderless=True, command=None, env={})
    try:
        stat = Path(f"/proc/{owner.pid}/stat").read_text().rsplit(") ", 1)[1].split()
        status = Path(f"/proc/{owner.pid}/status").read_text()
        assert stat[0] == "Z", "negative-fixture precondition: the leader reads as a zombie"
        assert int(stat[17]) > 1, "negative-fixture precondition: another thread is running"
        assert re.search(r"^State:\s+Z", status, re.M), status
        assert int(re.search(r"^Threads:\s+(\d+)", status, re.M).group(1)) > 1  # type: ignore[union-attr]
        os.kill(owner.pid, 0)
        yield owner
    finally:
        _stop_owner(owner)


# --- the registry ---------------------------------------------------------------

#: (case, state letter, thread-count field or None to cut the line short,
#:  liveness, basis)
REGISTRY_CASES = [
    ("zombie leader with a live thread", "Z", "2", "live", "pid-present"),
    ("zombie leader with many threads", "Z", "17", "live", "pid-present"),
    ("single-threaded zombie", "Z", "1", "stale", "owner-zombie"),
    ("zombie with no threads", "Z", "0", "stale", "owner-zombie"),
    ("zombie, thread count not a number", "Z", "x", "stale", "owner-zombie"),
    ("zombie, thread count missing", "Z", None, "stale", "owner-zombie"),
    ("dead (X) even with a thread count", "X", "2", "stale", "owner-zombie"),
    ("ordinary live process", "S", "1", "live", "pid-present"),
    ("ordinary live process, many threads", "S", "9", "live", "pid-present"),
]


def _stat_line(pid: int, state: str, threads: str | None) -> str:
    """A stat line for PID with the given state and thread count.

    Built from this process's real line so every other field is plausible, with
    a comm that itself contains `) Z ` - the reader must split on the LAST one.
    """
    fields = Path(f"/proc/{os.getpid()}/stat").read_text().rsplit(") ", 1)[1].split()
    fields[0] = state
    if threads is None:
        fields = fields[:17]
    else:
        fields[17] = threads
    return f"{pid} (odd ) Z 1 name) " + " ".join(fields) + "\n"


@requires_linux_tools
@pytest.mark.parametrize(
    ("state", "threads", "liveness", "basis"),
    [case[1:] for case in REGISTRY_CASES], ids=[case[0] for case in REGISTRY_CASES],
)
def test_registry_reads_the_owner_state_with_its_thread_count(
    tmp_path: Path, state: str, threads: str | None, liveness: str, basis: str
) -> None:
    pid = os.getpid()
    proc_root = tmp_path / "proc"
    entry = proc_root / str(pid) / "stat"
    entry.parent.mkdir(parents=True)
    env: dict[str, str | None] = {"FLOW_WAVE_PROC_ROOT": str(proc_root)}

    # Registered while it reads as an ordinary running process ...
    entry.write_text(_stat_line(pid, "S", "1"))
    registered = wave_run(tmp_path, "register", ROLE, "--wave", WAVE, pid=str(pid),
                          session="owner", live="", starttimes="", extra_env=env)
    assert _verdict(registered) == "registered", registered.stderr
    # ... and read back once its line says what this case says.
    entry.write_text(_stat_line(pid, state, threads))
    after = entry.read_text().rsplit(") ", 1)[1].split()
    assert after[0] == state, "fixture precondition: the state under test is what is on disk"
    assert (after[17] if len(after) > 17 else None) == threads, "fixture precondition: thread count"

    got = wave_run(tmp_path, "get", ROLE, "--wave", WAVE, session="observer",
                   live="", starttimes="", extra_env=env)
    assert got.returncode == 0, got.stderr
    assert _detail(got, "FLOW_WAVE_LIVENESS") == liveness, got.stdout
    assert _detail(got, "FLOW_WAVE_LIVENESS_BASIS") == basis, got.stdout

    # What the verdict is FOR: may another session take the role without --force?
    taken = wave_run(tmp_path, "register", ROLE, "--wave", WAVE, session="observer",
                     live="", starttimes="", extra_env=env)
    assert _verdict(taken) == ("refused" if liveness == "live" else "registered"), taken.stderr


@requires_linux_tools
def test_registry_reads_a_pid_that_does_not_exist_as_gone(tmp_path: Path) -> None:
    assert not Path(f"/proc/{NO_SUCH_PID}").exists(), "precondition: no such process"
    env: dict[str, str | None] = {"FLOW_WAVE_PROC_ROOT": str(tmp_path / "empty-proc")}
    (tmp_path / "empty-proc").mkdir()
    registered = wave_run(tmp_path, "register", ROLE, "--wave", WAVE, pid=str(NO_SUCH_PID),
                          session="owner", live="", starttimes="", extra_env=env)
    assert _verdict(registered) == "registered", registered.stderr
    got = wave_run(tmp_path, "get", ROLE, "--wave", WAVE, session="observer",
                   live="", starttimes="", extra_env=env)
    assert _detail(got, "FLOW_WAVE_LIVENESS") == "stale", got.stdout
    assert _detail(got, "FLOW_WAVE_LIVENESS_BASIS") == "pid-gone", got.stdout


@requires_linux_tools
def test_registry_holds_a_role_for_a_real_process_whose_main_thread_exited(
    tmp_path: Path, leaderless_owner: Owner
) -> None:
    """The dangerous direction: this read `stale`, and the role could be taken."""
    real: dict[str, str | None] = {"FLOW_WAVE_PROC_ROOT": None}
    pid = str(leaderless_owner.pid)
    registered = wave_run(tmp_path, "register", ROLE, "--wave", WAVE, pid=pid,
                          session="owner", live="", starttimes="", extra_env=real)
    assert _verdict(registered) == "registered", registered.stderr

    got = wave_run(tmp_path, "get", ROLE, "--wave", WAVE, session="observer",
                   live="", starttimes="", extra_env=real)
    assert _detail(got, "FLOW_WAVE_LIVENESS") == "live", got.stdout
    assert _detail(got, "FLOW_WAVE_LIVENESS_BASIS") == "pid-present", got.stdout

    taken = wave_run(tmp_path, "register", ROLE, "--wave", WAVE, session="observer",
                     live="", starttimes="", extra_env=real)
    assert _verdict(taken) == "refused", taken.stdout + taken.stderr
    assert taken.returncode == 1


# --- the mailbox ------------------------------------------------------------------

FIXTURE_PID = "4242"
START = "987654"

#: (case, status text or None for no /proc entry at all, start time recorded
#:  at arm time, owner_gone's answer)
MAILBOX_CASES = [
    ("zombie leader with a live thread", "State:\tZ (zombie)\nThreads:\t2\n", START, "alive"),
    ("zombie leader with many threads", "State:\tZ (zombie)\nThreads:\t17\n", START, "alive"),
    ("single-threaded zombie", "State:\tZ (zombie)\nThreads:\t1\n", START, "gone"),
    ("zombie with no threads", "State:\tZ (zombie)\nThreads:\t0\n", START, "gone"),
    ("zombie, thread count not a number", "State:\tZ (zombie)\nThreads:\tx\n", START, "gone"),
    ("zombie, thread count missing", "State:\tZ (zombie)\n", START, "gone"),
    ("dead (X) even with a thread count", "State:\tX (dead)\nThreads:\t2\n", START, "gone"),
    ("ordinary live process", "State:\tS (sleeping)\nThreads:\t1\n", START, "alive"),
    ("ordinary live process, many threads", "State:\tS (sleeping)\nThreads:\t9\n", START, "alive"),
    ("a pid that does not exist", None, START, "gone"),
    ("a reused pid: another start time", "State:\tS (sleeping)\nThreads:\t1\n", "111", "gone"),
    ("zombie leader, but a reused pid", "State:\tZ (zombie)\nThreads:\t2\n", "111", "gone"),
    ("start time never recorded", "State:\tS (sleeping)\nThreads:\t1\n", "-", "alive"),
]


def _lifted_owner_gone(proc_root: Path) -> str:
    """`proc_starttime` and `owner_gone`, as written, reading PROC_ROOT for /proc."""
    source = MAILBOX.read_text(encoding="utf-8")
    lifted = []
    for name in ("proc_starttime", "owner_gone"):
        found = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", source, re.M | re.S)
        assert found, f"lift precondition: {name}() not found in the mailbox"
        lifted.append(found.group(0))
    text = "".join(lifted)
    assert text.count('"/proc/$') >= 3, "lift precondition: the functions read /proc by that spelling"
    moved = text.replace('"/proc/$', f'"{proc_root}/$')
    assert "/proc/" not in moved.replace(str(proc_root), ""), "lift precondition: every read was moved"
    return "set -uo pipefail\n" + moved


@requires_linux_tools
@pytest.mark.parametrize(
    ("status", "recorded_start", "answer"),
    [case[1:] for case in MAILBOX_CASES], ids=[case[0] for case in MAILBOX_CASES],
)
def test_mailbox_owner_gone_reads_the_state_with_its_thread_count(
    tmp_path: Path, status: str | None, recorded_start: str, answer: str
) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    if status is not None:
        entry = proc_root / FIXTURE_PID
        entry.mkdir()
        (entry / "status").write_text(f"Name:\towner\n{status}PPid:\t1\n")
        fields = ["S", "1"] + ["0"] * 17 + [START] + ["0"] * 10
        (entry / "stat").write_text(f"{FIXTURE_PID} (odd ) name) " + " ".join(fields) + "\n")
    else:
        assert not (proc_root / FIXTURE_PID).exists(), "precondition: no entry for the pid"
    functions = tmp_path / "owner-gone.sh"
    functions.write_text(_lifted_owner_gone(proc_root))
    ran = subprocess.run(
        ["bash", "-c", 'source "$1"; if owner_gone "$2"; then echo gone; else echo alive; fi',
         "owner-gone", str(functions), f"{FIXTURE_PID}:{recorded_start}"],
        capture_output=True, text=True, check=False,
    )
    assert ran.returncode == 0 and ran.stderr == "", ran.stderr
    assert ran.stdout.strip() == answer


def _watch_armed_by(tmp_path: Path, *, leaderless: bool) -> dict[str, object]:
    """Arm a real `watch` from an owner process of the given shape; its outcome."""
    command = ["bash", str(MAILBOX), "watch", "--role", ROLE, "--wave", WAVE,
               "--timeout", "2", "--interval", "1", "--peek"]
    owner = _start_owner(leaderless=leaderless, command=command,
                         env={"FLOW_WAVE_MAILBOX_DIR": str(tmp_path / "mb")})
    _stop_owner(owner)
    return owner.report


def _mailbox_verdict(report: dict[str, object]) -> str:
    lines = [ln for ln in str(report["stdout"]).splitlines() if ln.startswith("FLOW_MAILBOX: ")]
    return lines[-1].removeprefix("FLOW_MAILBOX: ") if lines else ""


@requires_linux_tools
def test_a_watch_armed_by_a_process_whose_main_thread_exited_keeps_listening(
    tmp_path: Path,
) -> None:
    """It exited 10 `owner-gone` after its first interval; the owner was alive."""
    report = _watch_armed_by(tmp_path, leaderless=True)
    assert report["state"] == "Z", "negative-fixture precondition: the leader reads as a zombie"
    assert int(str(report["threads"])) > 1, "negative-fixture precondition: another thread runs"
    assert (report["state_after"], report["threads_after"]) == (report["state"], report["threads"])
    assert _mailbox_verdict(report) == "timeout", report
    assert report["rc"] == 5, report


@requires_linux_tools
def test_a_watch_armed_by_an_ordinary_process_keeps_listening(tmp_path: Path) -> None:
    """The contrast: the same arming, from a process whose main thread is running."""
    report = _watch_armed_by(tmp_path, leaderless=False)
    assert report["state"] != "Z"
    assert _mailbox_verdict(report) == "timeout", report
    assert report["rc"] == 5, report
