"""Reaping for the detached `supervise` daemons this suite starts (issue #1116).

`flow-wave-mailbox.sh supervise` (issue #814) detaches BY CONSTRUCTION: the
daemon outlives the invocation that launched it, which is the entire point -
nothing conversational has to remember to re-arm `watch`. A test that starts
one therefore owns a process pytest does not know about and will never clean
up. When the test forgets, the daemon is reparented to `systemd --user` and
keeps its inherited working directory open; measured on this host, one such
daemon held a per-issue worktree for hours, so `worktree-remove.sh`'s #888
occupancy guard correctly refused to remove that worktree at the end of a
`/flow:auto` run.

Two facts decide the shape of everything below, and both were MEASURED on this
host rather than reasoned about (issue #1116):

1. **Signalling the daemon's pid alone is slow.** bash defers a trapped signal
   until its blocking foreground child returns, and the daemon's foreground
   child is the inner `watch`, which blocks for its whole `--timeout`. With
   `--timeout 10`: SIGTERM to the pid took **7.30s** to land. SIGTERM to the
   process GROUP - which reaches the inner `watch` directly, so the daemon's
   trap fires at once - took **0.10s**. Tests launching with `--timeout 30`
   outlived the old 10-second waiter *deterministically*, not occasionally.
2. **The inner `watch` child shares the daemon's working directory.** Reaping
   only the daemon can leave the directory pinned by the child anyway.

So the group kill is the mechanism, and the bound is enforced by escalating to
SIGKILL rather than by hoping. The one thing a group kill must never do is
guess: see `_signal` for why the process-group-leader precondition is checked
and not assumed.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import NamedTuple

# Escalation bounds. Generous next to the 0.10s a group SIGTERM was measured to
# need, and still far under the ~30s a pid-only SIGTERM can take against a
# `--timeout 30` daemon - the gap the old waiter fell into.
TERM_GRACE = 5.0
KILL_GRACE = 5.0
# Bounded re-signal passes used to converge on a subtree that is still
# forking; see kill_supervise_daemon.
_CONVERGE_ROUNDS = 3


def _proc_fields(pid: int) -> tuple[str, int] | None:
    """``(state, pgid)`` from ``/proc/<pid>/stat``, or None if it is gone.

    `comm` (field 2) is attacker-controlled and may contain spaces AND
    parentheses, so the split anchors on the LAST ``)`` rather than on
    whitespace - the standard way to read this file without letting a process
    name shift every field after it.
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    try:
        rest = raw[raw.rindex(")") + 2 :].split()
        return rest[0], int(rest[2])
    except (ValueError, IndexError):
        return None


def pid_alive(pid: int) -> bool:
    """Alive meaning "still occupying the pid", zombies excluded.

    A zombie keeps its `/proc` entry and still answers `kill(pid, 0)`, so a
    waiter that used either alone could not tell a SIGKILLed daemon from a
    live one and would report the reap as failed.
    """
    fields = _proc_fields(pid)
    if fields is None:
        return False
    return fields[0] != "Z"


def _children(pid: int) -> list[int]:
    """Direct children, from the kernel - no `pgrep`, no PATH dependency, and
    no substring match against a flattened command line (the #821
    anti-pattern)."""
    try:
        raw = Path(f"/proc/{pid}/task/{pid}/children").read_text()
    except OSError:
        return []
    out: list[int] = []
    for token in raw.split():
        try:
            out.append(int(token))
        except ValueError:
            continue
    return out


def _descendants(pid: int, depth: int = 8) -> list[int]:
    """The whole subtree, not just the daemon's own children.

    The process tree here is three deep, not two: daemon -> inner `watch` ->
    the `sleep "$INTERVAL"` that `watch` blocks in. On the `setsid` lane the
    group kill reaches all of them regardless, but the no-`setsid` fallback
    signals pids individually - and signalling only the first two levels
    leaves the grandchild alive, still holding the inherited cwd, while the
    caller is told the cleanup succeeded (counter-model review, issue #1116).
    A verdict must not cover fewer processes than it claims.
    """
    seen: list[int] = []
    frontier = [(pid, 0)]
    while frontier:
        current, level = frontier.pop()
        if level >= depth:
            continue
        for child in _children(current):
            if child in seen or child == pid:
                continue
            seen.append(child)
            frontier.append((child, level + 1))
    return seen


def _argv(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode(errors="replace") for part in raw.split(b"\0") if part]


def _option_value(argv: list[str], flag: str) -> str | None:
    """The value of `--flag`, read POSITIONALLY.

    Membership (`value in argv`) is not identity, and the difference is not
    academic: a daemon invoked `--role 2 --wave w --interval 1` contains the
    token "1", so a membership test for role "1" matches it (counter-model
    review, issue #1116). Every value in this argv is some option's argument,
    so the only sound question is which option it belongs to.
    """
    for index, token in enumerate(argv):
        if token == flag and index + 1 < len(argv):
            return argv[index + 1]
    return None


def _environ_value(pid: int, name: str) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return None
    prefix = f"{name}=".encode()
    for entry in raw.split(b"\0"):
        if entry.startswith(prefix):
            return entry[len(prefix) :].decode(errors="replace")
    return None


def is_supervise_daemon(pid: int, wave: str, role: str, mailbox_root: Path) -> bool:
    """Does `pid` REALLY hold the daemon this pidfile was written for?

    Pids are recycled - the space wraps every few hours on a busy host - so a
    pidfile written by a daemon that died an hour ago can name a completely
    unrelated LIVE process today, and these pidfiles outlive their daemons by
    design (#814 makes the flock the liveness test, the file diagnostic only).
    Signalling on the strength of the file alone would eventually SIGKILL a
    stranger, and this host really does run other supervise daemons: a live
    `kyle-revisions` wave was in the process table throughout this work.

    Four things must agree, because three of them individually do not settle
    it (counter-model review, issue #1116):

    * the argv verb - it is a supervise daemon at all;
    * `--role` and `--wave` read POSITIONALLY, not by token membership;
    * the mailbox ROOT it is actually serving, from its own environment.
      Role and wave can legitimately coincide across two different mailbox
      directories, so they do not identify a daemon on their own.

    A process that does not expose `FLOW_WAVE_MAILBOX_DIR` is refused rather
    than reaped. That is the safe direction - failing to reap leaves litter,
    signalling a stranger is not undoable - and it cannot cost this suite
    anything, because every daemon it starts is launched with that variable
    set.
    """
    argv = _argv(pid)
    # POSITIONS, not membership - the same defect as the role check below, one
    # field over (counter-model re-review, issue #1116). `__supervise_daemon`
    # is a legal wave name, so an ordinary `watch --wave __supervise_daemon`
    # satisfies a membership test and was accepted as a daemon. The daemon is
    # always launched as `bash <script> __supervise_daemon ...`, so the script
    # is argv[1] and the verb argv[2]; anything else is not one of ours.
    if len(argv) < 3:
        return False
    if not argv[1].endswith("/flow-wave-mailbox.sh"):
        return False
    if argv[2] != "__supervise_daemon":
        return False
    if _option_value(argv, "--role") != role:
        return False
    if _option_value(argv, "--wave") != wave:
        return False
    serving = _environ_value(pid, "FLOW_WAVE_MAILBOX_DIR")
    if serving is None:
        return False
    try:
        return Path(serving).resolve() == mailbox_root.resolve()
    except OSError:
        return False


def _signal(pid: int, known: list[int], sig: int) -> None:
    """Signal the daemon and whatever it is currently blocking on.

    The process GROUP kill is what makes this fast - it reaches the inner
    `watch` directly instead of waiting for bash to stop deferring the trap.
    It is used ONLY when the recorded pid is genuinely its own process-group
    leader, which is exactly the `setsid` lane `supervise` takes when setsid
    is available (`scripts/flow-wave-mailbox.sh`). On the no-setsid fallback
    the daemon sits in its LAUNCHER's group instead - under pytest that is the
    test runner's own group - and killing it would take the suite down with
    it. That precondition is therefore checked, never assumed, and the group
    is additionally required not to be ours.
    """
    fields = _proc_fields(pid)
    pgid = fields[1] if fields else None
    if pgid is not None and pgid == pid and pgid != os.getpgrp():
        try:
            os.killpg(pgid, sig)
            return
        except (OSError, ProcessLookupError):
            pass
    for target in known:
        try:
            os.kill(target, sig)
        except (OSError, ProcessLookupError):
            pass


def _all_dead(pids: list[int]) -> bool:
    return not any(pid_alive(p) for p in pids)


def _wait_dead(pids: list[int], timeout: float, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _all_dead(pids):
            return True
        time.sleep(interval)
    return _all_dead(pids)


# Pids a DIRECT kill gave up on. The autouse fixture drains this at teardown
# so a failed fast-path cleanup is reported even when pidfile discovery can no
# longer find the process (counter-model re-review, issue #1116).
#
# It exists because "the fixture will catch it" was not true in general:
# `test_ownership_is_the_flock_not_the_pid_file` OVERWRITES the pidfile with a
# bogus value as the point of the test, so the reaper's glob cannot rediscover
# that daemon, and a failed `_kill_daemon` there would have been silent - the
# exact unchecked-cleanup shape this module was written to remove.
#
# Recording rather than raising is deliberate: every fast-path caller invokes
# the kill from a `finally:` block, and an exception raised there would REPLACE
# the test's real failure with this one.
_UNREAPED: set[int] = set()


def drain_unreaped() -> list[int]:
    """Pids a direct kill failed on and that are STILL alive. Clears the set."""
    still = sorted(p for p in _UNREAPED if pid_alive(p))
    _UNREAPED.clear()
    return still


def kill_supervise_daemon(
    pid: int, term_grace: float = TERM_GRACE, kill_grace: float = KILL_GRACE
) -> bool:
    """SIGTERM, then SIGKILL, the daemon and the inner `watch` it blocks on.

    Returns True when nothing of the SUBTREE is left. Descendants are re-read
    before each pass because the daemon spawns a fresh inner `watch` every
    cycle, so a snapshot taken once can name a child already replaced.
    """
    return _record(pid, _kill_subtree(pid, term_grace, kill_grace))


def _record(pid: int, ok: bool) -> bool:
    if ok:
        _UNREAPED.discard(pid)
    else:
        _UNREAPED.add(pid)
    return ok


def _kill_subtree(pid: int, term_grace: float, kill_grace: float) -> bool:
    targets = [pid, *_descendants(pid)]
    if _all_dead(targets):
        return True
    for sig, grace in ((signal.SIGTERM, term_grace), (signal.SIGKILL, kill_grace)):
        targets = sorted({*targets, pid, *_descendants(pid)})
        _signal(pid, targets, sig)
        if not _wait_dead(targets, grace):
            continue
        # Everything we KNEW about is dead. That is not the same as the
        # subtree being gone: on the no-`setsid` lane, where pids are
        # signalled individually rather than as a group, a `watch` can fork
        # its next child between the snapshot and the signal, and that child
        # is not in `targets` - so the wait above succeeds while it lives on,
        # holding the cwd (counter-model re-review, issue #1116). Re-read and
        # signal again until the subtree stops producing new members.
        #
        # This narrows the window; it does not eliminate it. Closing it
        # completely means freezing the tree (SIGSTOP every member before
        # enumerating, SIGCONT after), and that choreography is not warranted
        # for a fallback lane no host in this project takes - `setsid` is part
        # of util-linux and present everywhere the suite runs, and the group
        # kill it enables covers new children by construction. If this helper
        # is ever needed where `setsid` is genuinely absent, the freeze is
        # where the remaining window is answered.
        for _ in range(_CONVERGE_ROUNDS):
            stragglers = [p for p in _descendants(pid) if pid_alive(p)]
            if not stragglers:
                return True
            targets = sorted({*targets, *stragglers})
            _signal(pid, targets, signal.SIGKILL)
            _wait_dead(targets, kill_grace)
        return _all_dead([pid, *_descendants(pid)])
    return _all_dead(targets)


def supervise_pidfiles(root: Path) -> list[Path]:
    """Every supervise pidfile under `root`.

    The universe is hardcoded (this glob); the members are derived (whatever
    the run actually wrote). No test has to remember to register anything,
    which is the whole difference between this and the per-test kill calls it
    backstops.
    """
    try:
        return sorted(Path(root).rglob(".supervise-*.pid"))
    except OSError:
        return []


class ReapResult(NamedTuple):
    """What a reap found and what it failed to finish.

    `survivors` exists because the FIRST version of this module discarded
    `kill_supervise_daemon`'s boolean, exactly as the code it replaced
    discarded `_wait_for`'s (counter-model review, issue #1116). A cleanup
    that cannot report its own failure is the defect this module was written
    to remove, one level up - so the verdict is returned, and the autouse
    fixture in tests/conftest.py fails the test on it.
    """

    leaked: list[int]
    survivors: list[int]


def reap_supervise_daemons(
    root: Path, term_grace: float = TERM_GRACE, kill_grace: float = KILL_GRACE
) -> ReapResult:
    """Kill every live supervise daemon recorded under `root`.

    `leaked` is the pids that were still alive when reaping began - the ones a
    test left behind - so a caller can assert on the leak itself and not
    merely on the cleanup. `survivors` is the ones still alive after SIGKILL
    and its grace period, which is a real failure and must not be silent.
    """
    leaked: list[int] = []
    survivors: list[int] = []
    for pidfile in supervise_pidfiles(root):
        try:
            pid = int(pidfile.read_text().strip())
        except (OSError, ValueError):
            continue
        # pid 0 is "every process in my own group" to `killpg`, and pid 1 is
        # init. Neither is ever a daemon this suite started.
        if pid <= 1 or pid == os.getpid():
            continue
        wave = pidfile.parent.name
        role = pidfile.name[len(".supervise-") : -len(".pid")]
        mailbox_root = pidfile.parent.parent
        if not pid_alive(pid):
            continue
        if not is_supervise_daemon(pid, wave, role, mailbox_root):
            continue
        leaked.append(pid)
        if not kill_supervise_daemon(pid, term_grace, kill_grace):
            survivors.append(pid)
    return ReapResult(leaked=leaked, survivors=survivors)
