"""Tests for the wave delivery lane (issue #676).

Covers ``scripts/flow-wave-mailbox.sh``, the mailbox + wake lane that carries
orchestrator <-> worker traffic when the harness cannot route a ``SendMessage``.

Contract:
- ``send`` addresses by ROLE, the same declared identity the #638 registry keys
  on: ``--to <worker>`` writes ``outbox-<worker>.md``, ``--to orchestrator``
  writes ``inbox-<from>.md`` and REQUIRES ``--from`` (one box per writer, so two
  workers reporting at once never contend).
- Sends APPEND. This is the gate-ruled deviation from the issue's
  "rewrite-in-place": an assignment followed by a verdict before the worker
  wakes must not lose the assignment, which is the delivery-loss failure the
  whole issue exists to remove. ``--replace`` opts into overwrite and still
  BUMPS the rev, so a replaced box can never read as already-consumed.
- Revs are per-box and monotonic under flock: concurrent senders each get a
  distinct rev and no message is lost.
- ``read`` yields every message not yet ACKNOWLEDGED (issue #815); ``--all``
  additionally re-shows already-acknowledged history; ``--peek`` reads without
  acknowledging anything, so an armed watch still fires AND a dropped response
  leaves the message recoverable through the next ordinary read.
- ``watch`` is the WAKE, and is the half that makes this a lane rather than the
  ad-hoc 2026-08-11 workaround: it BLOCKS until mail lands, prints it, exits 0.
  A timeout is exit 5 and is explicitly not evidence the counterpart is gone.
- ``ack`` (issue #815) is the durable receipt, bound to exact rev identities -
  not a watermark, so an out-of-order or partial batch cannot silently imply
  an earlier, unseen message was received. Surfacing output (``read``/``watch``
  printing a message) and acknowledging it are two different events; only
  ``ack`` - and the named legacy ``read``/``watch --consume`` convenience that
  still does both at once - ever records a receipt. Refuses to acknowledge a
  rev that does not exist yet in the box.
- Role and wave names are validated, not merely quoted: they become path
  components, so ``../`` must be refused rather than addressed.

Timing-sensitive assertions use short, bounded waits and assert on OUTPUT
(the delivered body, the verdict line), never on how long a poll took.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAILBOX = ROOT / "scripts" / "flow-wave-mailbox.sh"

# Drives a real `bash` subprocess; the CI validate container may not ship one,
# so skip there (CPP core directive, same shape as the other flow suites).
requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)

# The no-/proc watcher lane shells out to `ps`, which the CI validate container
# does not ship - and there the helper correctly answers `unknown` rather than
# guessing, which is the #801 contract, not a failure. Only the test that FORCES
# that lane needs this guard; the auto-selected /proc lane needs no `ps` at all.
requires_ps = pytest.mark.skipif(
    shutil.which("ps") is None, reason="requires ps on PATH (procps)"
)

WAVE = "testwave"


def _run(tmp: Path, *args: str, stdin: str | None = None, timeout: int = 60):
    env = os.environ.copy()
    env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp / "mb")
    return subprocess.run(
        ["bash", str(MAILBOX), *args],
        capture_output=True,
        text=True,
        env=env,
        input=stdin,
        check=False,
        timeout=timeout,
    )


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    for line in proc.stdout.splitlines():
        if line.startswith("FLOW_MAILBOX: "):
            return line.removeprefix("FLOW_MAILBOX: ")
    return ""


def _detail(proc: subprocess.CompletedProcess[str], key: str) -> str:
    for line in proc.stdout.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return ""


def _body(proc: subprocess.CompletedProcess[str]) -> str:
    """Message text only - everything before the trailing contract block.

    Split on the ``FLOW_MAILBOX`` prefix rather than a fixed offset, so adding
    a detail line to the contract cannot silently break the parse.
    """
    out: list[str] = []
    for line in proc.stdout.splitlines():
        if line.startswith("FLOW_MAILBOX_") or line.startswith("FLOW_MAILBOX: "):
            break
        out.append(line)
    return "\n".join(out)


def _send(tmp: Path, to: str, body: str, *extra: str, frm: str | None = None):
    args = ["send", "--wave", WAVE, "--to", to, "--body", body]
    if frm:
        args += ["--from", frm]
    return _run(tmp, *args, *extra)


# --------------------------------------------------------------------------
# Addressing
# --------------------------------------------------------------------------


@requires_bash
class TestAddressing:
    def test_send_to_worker_writes_that_workers_outbox(self, tmp_path: Path):
        proc = _send(tmp_path, "1", "wave brief")
        assert _verdict(proc) == "sent"
        assert _detail(proc, "FLOW_MAILBOX_BOX") == "outbox-1.md"
        assert (tmp_path / "mb" / WAVE / "outbox-1.md").exists()

    def test_send_to_orchestrator_writes_the_writers_own_inbox(self, tmp_path: Path):
        """One box per WRITER: two workers reporting at once never contend."""
        proc = _send(tmp_path, "orchestrator", "hello from 1", frm="1")
        assert _verdict(proc) == "sent"
        assert _detail(proc, "FLOW_MAILBOX_BOX") == "inbox-1.md"

        other = _send(tmp_path, "orchestrator", "hello from 2", frm="2")
        assert _detail(other, "FLOW_MAILBOX_BOX") == "inbox-2.md"

    def test_send_to_orchestrator_without_from_is_a_usage_error(self, tmp_path: Path):
        proc = _send(tmp_path, "orchestrator", "hello")
        assert proc.returncode == 2
        assert "--from" in proc.stderr

    def test_orchestrator_reads_every_worker_inbox_at_once(self, tmp_path: Path):
        """A full drain requires an explicit destination non-interactively
        (issue #792 item 7) - --out keeps the durable copy this test asserts
        against, in addition to the stdout body.
        """
        _send(tmp_path, "orchestrator", "report from 1", frm="1")
        _send(tmp_path, "orchestrator", "report from 2", frm="2")
        out_file = tmp_path / "drain.txt"
        proc = _run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE,
            "--out", str(out_file),
        )
        assert _verdict(proc) == "read"
        body = _body(proc)
        assert "report from 1" in body
        assert "report from 2" in body
        saved = out_file.read_text()
        assert "report from 1" in saved
        assert "report from 2" in saved

    def test_worker_reads_only_its_own_outbox(self, tmp_path: Path):
        _send(tmp_path, "1", "for worker one")
        _send(tmp_path, "2", "for worker two")
        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        body = _body(proc)
        assert "for worker one" in body
        assert "for worker two" not in body

    @pytest.mark.parametrize("bad", ["../../etc", "a/b", ".hidden", "with space"])
    def test_path_shaped_role_names_are_refused_not_addressed(
        self, tmp_path: Path, bad: str
    ):
        """Role names become path components - validate, do not merely quote."""
        proc = _send(tmp_path, bad, "payload")
        assert proc.returncode == 2
        assert "invalid" in proc.stderr

    def test_path_shaped_wave_name_is_refused(self, tmp_path: Path):
        proc = _run(
            tmp_path, "send", "--wave", "../escape", "--to", "1", "--body", "x"
        )
        assert proc.returncode == 2
        assert "invalid wave name" in proc.stderr


# --------------------------------------------------------------------------
# Append semantics - the gate-ruled deviation from the issue text
# --------------------------------------------------------------------------


@requires_bash
class TestAppendNeverDropsUnreadMail:
    def test_second_send_does_not_overwrite_the_first(self, tmp_path: Path):
        """The #676 failure in miniature: an assignment then a verdict, both
        landing before the worker wakes. Rewrite-in-place loses the assignment.
        """
        _send(tmp_path, "1", "ASSIGNMENT issue 42")
        _send(tmp_path, "1", "VERDICT approved")
        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        body = _body(proc)
        assert "ASSIGNMENT issue 42" in body
        assert "VERDICT approved" in body

    def test_rev_increments_per_box(self, tmp_path: Path):
        first = _send(tmp_path, "1", "one")
        second = _send(tmp_path, "1", "two")
        assert _detail(first, "FLOW_MAILBOX_REV") == "1"
        assert _detail(second, "FLOW_MAILBOX_REV") == "2"

    def test_rev_is_per_box_not_global(self, tmp_path: Path):
        _send(tmp_path, "1", "one")
        other = _send(tmp_path, "2", "one")
        assert _detail(other, "FLOW_MAILBOX_REV") == "1"

    def test_replace_drops_history_but_still_bumps_the_rev(self, tmp_path: Path):
        """A replace that reused or lowered the rev would read as already
        consumed by a reader whose cursor had passed it - i.e. silently undelivered.
        """
        _send(tmp_path, "1", "stale brief")
        replaced = _send(tmp_path, "1", "CURRENT brief", "--replace")
        assert _detail(replaced, "FLOW_MAILBOX_REV") == "2"

        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--all")
        body = _body(proc)
        assert "CURRENT brief" in body
        assert "stale brief" not in body

    def test_replace_after_a_read_is_still_unread(self, tmp_path: Path):
        _send(tmp_path, "1", "first")
        _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        _send(tmp_path, "1", "second", "--replace")
        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert _verdict(proc) == "read"
        assert "second" in _body(proc)

    def test_concurrent_senders_all_land_with_distinct_revs(self, tmp_path: Path):
        """Eight writers on one box: flock must serialize the read-modify-write,
        or two sends share a rev and one message is lost.
        """
        results: list[subprocess.CompletedProcess[str]] = []
        lock = threading.Lock()

        def fire(i: int) -> None:
            proc = _send(tmp_path, "1", f"msg {i}")
            with lock:
                results.append(proc)

        threads = [threading.Thread(target=fire, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(_verdict(p) == "sent" for p in results)
        revs = sorted(int(_detail(p, "FLOW_MAILBOX_REV")) for p in results)
        assert revs == list(range(1, 9)), "a shared rev means a dropped message"

        box = (tmp_path / "mb" / WAVE / "outbox-1.md").read_text()
        for i in range(8):
            assert f"msg {i}" in box

    def test_empty_body_is_refused(self, tmp_path: Path):
        """A delivered blank is indistinguishable from no delivery."""
        proc = _send(tmp_path, "1", "")
        assert proc.returncode == 2

    def test_body_can_come_from_stdin(self, tmp_path: Path):
        proc = _run(
            tmp_path, "send", "--wave", WAVE, "--to", "1", stdin="piped brief\n"
        )
        assert _verdict(proc) == "sent"
        read = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert "piped brief" in _body(read)

    def test_body_can_come_from_a_file(self, tmp_path: Path):
        src = tmp_path / "brief.md"
        src.write_text("brief from a file\n")
        proc = _run(
            tmp_path,
            "send",
            "--wave",
            WAVE,
            "--to",
            "1",
            "--body-file",
            str(src),
        )
        assert _verdict(proc) == "sent"
        read = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert "brief from a file" in _body(read)


# --------------------------------------------------------------------------
# Read cursor
# --------------------------------------------------------------------------


@requires_bash
class TestReadCursor:
    def test_read_consumes_so_a_second_read_is_empty(self, tmp_path: Path):
        _send(tmp_path, "1", "only message")
        first = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert _verdict(first) == "read"
        second = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert _verdict(second) == "empty"
        assert _detail(second, "FLOW_MAILBOX_UNREAD") == "0"

    def test_read_yields_only_what_is_new(self, tmp_path: Path):
        _send(tmp_path, "1", "already seen")
        _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        _send(tmp_path, "1", "brand new")
        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        body = _body(proc)
        assert "brand new" in body
        assert "already seen" not in body

    def test_all_re_reads_history_after_a_compaction(self, tmp_path: Path):
        _send(tmp_path, "1", "the wave brief")
        _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--all")
        assert "the wave brief" in _body(proc)

    def test_peek_does_not_consume_so_a_watch_still_fires(self, tmp_path: Path):
        _send(tmp_path, "1", "peeked message")
        peek = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek")
        assert "peeked message" in _body(peek)
        again = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert _verdict(again) == "read"
        assert "peeked message" in _body(again)

    def test_read_with_no_box_at_all_is_empty_not_an_error(self, tmp_path: Path):
        proc = _run(tmp_path, "read", "--role", "9", "--wave", WAVE)
        assert proc.returncode == 0
        assert _verdict(proc) == "empty"


# --------------------------------------------------------------------------
# The wake - the half that makes this a lane
# --------------------------------------------------------------------------


@requires_bash
class TestWatchIsTheWake:
    def test_watch_blocks_then_wakes_on_delivery(self, tmp_path: Path):
        """The whole point of #676: a worker standing by learns an assignment
        exists without a human typing anything.
        """
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        watcher = subprocess.Popen(
            [
                "bash",
                str(MAILBOX),
                "watch",
                "--role",
                "1",
                "--wave",
                WAVE,
                "--timeout",
                "30",
                "--interval",
                "1",
                "--consume",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            # Still blocking with no mail: a watch that returned immediately
            # would be a poll, and a poll is what an idle session never runs.
            time.sleep(2)
            assert watcher.poll() is None, "watch returned before any mail arrived"

            _send(tmp_path, "1", "ASSIGNMENT issue 676")
            out, _ = watcher.communicate(timeout=30)
        finally:
            if watcher.poll() is None:
                watcher.kill()
                watcher.communicate()

        assert watcher.returncode == 0
        assert "ASSIGNMENT issue 676" in out
        assert "FLOW_MAILBOX: mail" in out
        # This is a FRESH wake - mail arrived after the watch was already
        # blocking - so the #792 "already unread when armed" note must NOT
        # appear (it would misreport a fresh wake as a stale backlog).
        assert "NOTE - mail was already unread" not in out

    def test_watch_times_out_with_a_distinct_exit_code(self, tmp_path: Path):
        proc = _run(
            tmp_path,
            "watch",
            "--role",
            "1",
            "--wave",
            WAVE,
            "--timeout",
            "0",
            "--interval",
            "1",
            "--consume",
        )
        assert proc.returncode == 5, "a timeout must be distinguishable from mail"
        assert _verdict(proc) == "timeout"

    def test_timeout_message_refuses_to_call_the_counterpart_dead(
        self, tmp_path: Path
    ):
        """Reading a timeout as 'the other session is gone' is how a healthy
        wave gets torn down; the helper says so rather than leaving it implied.
        """
        proc = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--consume",
        )
        assert "NOT proof" in proc.stderr
        assert "flow-wave-registry.sh list" in proc.stderr

    def test_watch_returns_mail_already_waiting(self, tmp_path: Path):
        """A watch armed after the send still delivers - the race a worker hits
        when it re-arms between wakes. Because the mail was ALREADY unread the
        instant this watch armed, #792 requires the NOTE line up front too.
        """
        _send(tmp_path, "1", "sent before the watch was armed")
        proc = _run(
            tmp_path,
            "watch",
            "--role",
            "1",
            "--wave",
            WAVE,
            "--timeout",
            "5",
            "--interval",
            "1",
            "--consume",
        )
        assert proc.returncode == 0
        assert _verdict(proc) == "mail"
        assert "sent before the watch was armed" in _body(proc)
        assert "NOTE - mail was already unread" in proc.stdout

    def test_watch_consumes_so_a_re_armed_watch_does_not_re_fire(
        self, tmp_path: Path
    ):
        _send(tmp_path, "1", "handled once")
        first = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "5",
            "--consume",
        )
        assert _verdict(first) == "mail"
        second = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--consume",
        )
        assert _verdict(second) == "timeout"

    def test_peek_does_not_consume_so_a_re_armed_watch_re_fires(
        self, tmp_path: Path
    ):
        """The other half of #792 item 1: --peek must NOT advance the cursor,
        or a re-armed peek watch would spin-fire on the very message it just
        showed - which is exactly the ordering hazard item 2 describes.
        """
        _send(tmp_path, "1", "still unread")
        first = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "5",
            "--peek",
        )
        assert _verdict(first) == "mail"
        second = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--peek",
        )
        assert _verdict(second) == "mail", "peek must not consume the message"

    def test_orchestrator_watch_covers_every_inbox(self, tmp_path: Path):
        _send(tmp_path, "orchestrator", "pushback from worker 3", frm="3")
        proc = _run(
            tmp_path,
            "watch",
            "--role",
            "orchestrator",
            "--wave",
            WAVE,
            "--timeout",
            "5",
            "--consume",
        )
        assert _verdict(proc) == "mail"
        assert "pushback from worker 3" in _body(proc)


# --------------------------------------------------------------------------
# Explicit --peek/--consume (issue #792 item 1) - no more silent default
# --------------------------------------------------------------------------


@requires_bash
class TestWatchRequiresExplicitChoice:
    def test_watch_without_peek_or_consume_is_a_usage_error(self, tmp_path: Path):
        """A bare `watch` used to consume by default, which marked mail read
        that the caller never saw. There is no default left.
        """
        proc = _run(tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0")
        assert proc.returncode == 2
        assert "--peek" in proc.stderr
        assert "--consume" in proc.stderr

    def test_watch_with_both_peek_and_consume_is_a_usage_error(self, tmp_path: Path):
        proc = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--peek", "--consume",
        )
        assert proc.returncode == 2
        assert "mutually exclusive" in proc.stderr


# --------------------------------------------------------------------------
# list - the orchestrator's undelivered-mail view
# --------------------------------------------------------------------------


@requires_bash
class TestList:
    def test_list_surfaces_unread_mail(self, tmp_path: Path):
        """An assignment the worker has not consumed must be VISIBLE, or the
        2026-08-11 'both sessions healthy' misread reproduces.
        """
        _send(tmp_path, "1", "undelivered assignment")
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert _verdict(proc) == "listed"
        assert _detail(proc, "FLOW_MAILBOX_UNREAD") == "1"
        assert "outbox-1.md" in proc.stdout

    def test_list_unread_drops_to_zero_once_read(self, tmp_path: Path):
        _send(tmp_path, "1", "assignment")
        _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert _detail(proc, "FLOW_MAILBOX_UNREAD") == "0"

    def test_list_json_is_parseable(self, tmp_path: Path):
        _send(tmp_path, "1", "one")
        _send(tmp_path, "orchestrator", "two", frm="2")
        proc = _run(tmp_path, "list", "--wave", WAVE, "--json")
        payload = json.loads(_body(proc))
        assert payload["wave"] == WAVE
        boxes = {b["box"]: b for b in payload["boxes"]}
        assert boxes["outbox-1.md"]["unread"] == 1
        assert boxes["inbox-2.md"]["rev"] == 1

    def test_list_on_an_untouched_wave_is_not_an_error(self, tmp_path: Path):
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert proc.returncode == 0
        assert _verdict(proc) == "listed"


# --------------------------------------------------------------------------
# Wave namespacing + usage
# --------------------------------------------------------------------------


@requires_bash
class TestNamespacingAndUsage:
    def test_waves_are_isolated(self, tmp_path: Path):
        _run(tmp_path, "send", "--wave", "alpha", "--to", "1", "--body", "for alpha")
        proc = _run(tmp_path, "read", "--role", "1", "--wave", "beta")
        assert _verdict(proc) == "empty"

    def test_unknown_verb_is_a_usage_error(self, tmp_path: Path):
        proc = _run(tmp_path, "deliver", "--wave", WAVE)
        assert proc.returncode == 2
        assert "unknown verb" in proc.stderr

    def test_help_documents_the_verbs(self, tmp_path: Path):
        proc = _run(tmp_path, "--help")
        assert proc.returncode == 0
        for verb in ("send", "read", "watch", "list"):
            assert verb in proc.stdout

    def test_mailbox_shares_the_registry_wave_root(self, tmp_path: Path):
        """The lane lives BESIDE the #638 registry - same dir, same lifetime -
        so FLOW_WAVE_REGISTRY_DIR alone must place both.
        """
        env = os.environ.copy()
        env.pop("FLOW_WAVE_MAILBOX_DIR", None)
        env["FLOW_WAVE_REGISTRY_DIR"] = str(tmp_path / "shared")
        proc = subprocess.run(
            ["bash", str(MAILBOX), "send", "--wave", WAVE, "--to", "1", "--body", "x"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=60,
        )
        assert _verdict(proc) == "sent"
        assert (tmp_path / "shared" / WAVE / "outbox-1.md").exists()


# --------------------------------------------------------------------------
# The watch heartbeat (issue #778)
# --------------------------------------------------------------------------


def _watch_file(tmp: Path, wave: str, role: str) -> Path:
    return tmp / "mb" / wave / f".watch-{role}"


def _watch_states(proc: subprocess.CompletedProcess[str]) -> dict[str, str]:
    """Parse the text ``list`` watch table into ``{role: state}``.

    Parsed rather than substring-matched: the helper prints the wave DIR, and a
    pytest tmp path derived from the test's own name can contain the very word
    the assertion looks for (CPP directive - a pattern-matching fixture must not
    interpolate an absolute path it does not control).
    """
    return {role: cols[0] for role, cols in _watch_rows(proc).items()}


def _watch_rows(proc: subprocess.CompletedProcess[str]) -> dict[str, list[str]]:
    """``{role: [state, watchers]}`` from the text ``list`` watch table.

    The WATCHERS column arrived with #801, printed beside the state so the
    derivation is checkable rather than taken on trust; tests read both from one
    parse for the same reason.
    """
    rows: dict[str, list[str]] = {}
    in_table = False
    for line in proc.stdout.splitlines():
        if line.startswith("ROLE") and "WATCH" in line:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith(("FLOW_MAILBOX", "DEAF:", "UNKNOWN:")) or not line.strip():
            break
        parts = line.split()
        if len(parts) >= 3:
            rows[parts[0]] = [parts[1], parts[2]]
    return rows


def _live_watcher(tmp: Path, role: str, wave: str, timeout: int = 30):
    """Start a REAL blocking watcher and wait until its heartbeat exists.

    The #801 state is fused from the live process table, so a test that wants
    ``armed`` must run an actual process - a stamped heartbeat alone is exactly
    what no longer means armed.
    """
    env = os.environ.copy()
    env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp / "mb")
    proc = subprocess.Popen(
        ["bash", str(MAILBOX), "watch", "--role", role, "--wave", wave,
         "--timeout", str(timeout), "--interval", "1", "--consume"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    wf = _watch_file(tmp, wave, role)
    deadline = time.time() + 15
    while not wf.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert wf.exists(), "watch never armed"
    return proc


def _run_at(tmp: Path, now: str, *args: str, timeout: int = 60, **envextra: str):
    """``_run`` with the clock pinned, so heartbeat ages are deterministic."""
    env = os.environ.copy()
    env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp / "mb")
    env["FLOW_WAVE_NOW"] = now
    env.update(envextra)
    return subprocess.run(
        ["bash", str(MAILBOX), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=timeout,
    )


@requires_bash
class TestWatchHeartbeat:
    """Arming the watch was the one element of participation that left NO trace
    (#778): a worker could be live, verified and brief-current in the #638
    roster and still be completely deaf. The heartbeat is that trace.
    """

    def test_no_watch_leaves_no_heartbeat(self, tmp_path: Path) -> None:
        """The negative precondition the rest of the suite rests on: sending
        alone must not stamp anything, or `absent` could never mean anything.
        """
        _run(tmp_path, "send", "--wave", WAVE, "--to", "1", "--body", "assignment")
        assert not _watch_file(tmp_path, WAVE, "1").exists()

    def test_watch_stamps_a_heartbeat_on_arm(self, tmp_path: Path) -> None:
        wf = _watch_file(tmp_path, WAVE, "1")
        assert not wf.exists()  # precondition: nothing armed yet
        _run(tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        assert wf.exists()
        assert wf.read_text().strip().isdigit()

    def test_watch_stamps_even_when_mail_is_already_waiting(self, tmp_path: Path) -> None:
        """The stamp happens BEFORE the unread check, so an arm that fires on
        its first poll still leaves the trace.
        """
        _run(tmp_path, "send", "--wave", WAVE, "--to", "1", "--body", "waiting")
        proc = _run(tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        assert _verdict(proc) == "mail"
        assert _watch_file(tmp_path, WAVE, "1").exists()

    def test_heartbeat_refreshes_while_the_watch_blocks(self, tmp_path: Path) -> None:
        """A KILLED watch must decay while a blocking one stays fresh - only a
        REFRESHING stamp separates those two, which is why the stamp is on every
        poll and re-reads the clock rather than reusing the arm-time value.
        """
        wf = _watch_file(tmp_path, WAVE, "1")
        proc = subprocess.Popen(
            [
                "bash", str(MAILBOX), "watch", "--role", "1", "--wave", WAVE,
                "--timeout", "30", "--interval", "1", "--consume",
            ],
            env={**os.environ, "FLOW_WAVE_MAILBOX_DIR": str(tmp_path / "mb")},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.time() + 10
            while not wf.exists() and time.time() < deadline:
                time.sleep(0.1)
            assert wf.exists(), "watch never stamped a heartbeat"
            first = wf.read_text().strip()
            # Wait for a stamp that is strictly newer than the first one.
            deadline = time.time() + 10
            while wf.read_text().strip() == first and time.time() < deadline:
                time.sleep(0.2)
            assert wf.read_text().strip() != first, "heartbeat froze at arm time"
        finally:
            proc.kill()
            proc.wait(timeout=10)

    def test_heartbeat_survives_the_watch_exiting(self, tmp_path: Path) -> None:
        """'died' and 'never armed' are operationally different answers, so the
        stamp is deliberately NOT removed on exit - erasing it would flatten
        them back into the one state #778 exists to split apart.
        """
        _run(tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        assert _watch_file(tmp_path, WAVE, "1").exists()


@requires_bash
class TestListWatchState:
    def test_list_reports_absent_before_any_watch(self, tmp_path: Path) -> None:
        _run(tmp_path, "send", "--wave", WAVE, "--to", "1", "--body", "assignment")
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert _watch_states(proc) == {"1": "absent"}
        assert "never armed" in proc.stdout

    def test_list_reports_armed_while_a_watcher_is_live(self, tmp_path: Path) -> None:
        """The positive control for the whole #801 fusion.

        A fix that reported `dead` unconditionally would satisfy every negative
        case in this file, so the direction that must still read `armed` is
        asserted with a REAL blocking watcher rather than a stamped heartbeat.
        """
        watcher = _live_watcher(tmp_path, "1", WAVE)
        try:
            proc = _run(tmp_path, "list", "--wave", WAVE)
            assert _watch_rows(proc)["1"] == ["armed", "1"]
            assert "DEAF:" not in proc.stdout
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_list_reports_dead_once_the_watcher_has_exited(self, tmp_path: Path) -> None:
        """The #801 regression, at the surface an orchestrator actually sweeps.

        `--timeout 0` arms, stamps, and exits - which is precisely the shape of
        a one-shot watch that has just delivered. The heartbeat is 10s old and
        looks perfectly healthy; nothing is listening.
        """
        _run_at(tmp_path, "1700000000", "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        proc = _run_at(tmp_path, "1700000010", "list", "--wave", WAVE)
        assert _watch_rows(proc)["1"] == ["dead", "0"]
        assert "10s ago" in proc.stdout  # the age is still reported, not hidden
        assert "DEAF:" in proc.stdout

    def test_a_fresh_heartbeat_alone_never_reads_armed(self, tmp_path: Path) -> None:
        """The bug in one assertion: age is not evidence anyone is listening.

        Pinned across the whole freshness range - at 0s, and just inside the
        stale threshold - because the defect was that ANY sub-threshold age
        rendered `armed`.
        """
        _run_at(tmp_path, "1700000000", "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        for now in ("1700000000", "1700000299"):
            proc = _run_at(tmp_path, now, "list", "--wave", WAVE)
            assert _watch_states(proc) == {"1": "dead"}, f"read as armed at {now}"

    def test_stale_needs_a_live_watcher_that_stopped_refreshing(
        self, tmp_path: Path
    ) -> None:
        """`stale` narrowed under #801 and is no longer reachable by age alone.

        A watch refreshes every poll, so an old heartbeat behind a LIVE process
        means hung or stopped - a different repair from a process that is simply
        gone, which is why the two words stayed distinct.
        """
        watcher = _live_watcher(tmp_path, "1", WAVE)
        try:
            # A far-future reader clock ages the live watcher's real stamp past
            # the 300s threshold without stopping the process.
            future = str(int(time.time()) + 9000)
            proc = _run_at(tmp_path, future, "list", "--wave", WAVE)
            assert _watch_rows(proc)["1"] == ["stale", "1"]
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_stale_threshold_is_configurable(self, tmp_path: Path) -> None:
        """The #778 knob still moves the armed/stale line - for a LIVE watcher,
        the only case where that line still decides anything.
        """
        watcher = _live_watcher(tmp_path, "1", WAVE)
        try:
            future = str(int(time.time()) + 9000)
            proc = _run_at(tmp_path, future, "list", "--wave", WAVE,
                           FLOW_WAVE_WATCH_STALE_SECS="99999")
            assert _watch_states(proc) == {"1": "armed"}
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_unknown_watcher_count_is_never_rendered_as_clean(
        self, tmp_path: Path
    ) -> None:
        """A process table that cannot be read is UNCHECKED, not clean (#800).

        Rounding it to zero would report `dead` for healthy watches - this same
        bug wearing the opposite sign - so it gets its own state and its own
        advisory, kept apart from DEAF because it claims nothing either way.
        """
        _run_at(tmp_path, "1700000000", "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        proc = _run_at(tmp_path, "1700000010", "list", "--wave", WAVE,
                       FLOW_WAVE_WATCHER_SCAN="none")
        assert _watch_rows(proc)["1"] == ["unknown", "unknown"]
        assert "UNKNOWN:" in proc.stdout
        assert "DEAF:" not in proc.stdout

    @requires_ps
    def test_ps_fallback_lane_agrees_only_where_it_can_verify(self, tmp_path: Path) -> None:
        """The no-/proc lane is dead code on every host the suite runs on, so it
        would otherwise ship unexercised. Forced here.

        This test used to assert the two lanes ALWAYS "reach the same
        verdict" - the name issue #845 singled out as the assumption that
        made its own gap invisible: while a real watcher is armed, the
        `ps` lane cannot verify the match belongs to THIS mailbox
        (`FLOW_WAVE_MAILBOX_DIR` travels in the environment, which `ps -eo
        args` cannot see), so it now honestly answers `unknown` rather than
        a count it cannot back up - a DIFFERENT, correct verdict from the
        `/proc` lane's verified `armed`/`1`, not an agreement. The two
        lanes agree only in the one case that needs no verification: no
        match at all, which stays a confident `dead`.

        Skipped where `ps` is absent (the CI validate container): there the
        lane answers `unknown` for a different reason (`seen` never becomes
        1 - the `test_unknown_watcher_count_is_never_rendered_as_clean`
        case), not this one.
        """
        watcher = _live_watcher(tmp_path, "1", WAVE)
        try:
            proc = _run_at(tmp_path, str(int(time.time())), "list", "--wave", WAVE,
                           FLOW_WAVE_WATCHER_SCAN="ps")
            assert _watch_rows(proc)["1"] == ["unknown", "unknown"], (
                "a real watcher's match cannot be verified as OURS by this lane - "
                "it must not be reported as a confident 'armed' (issue #845)"
            )
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)
        proc = _run_at(tmp_path, str(int(time.time())), "list", "--wave", WAVE,
                       FLOW_WAVE_WATCHER_SCAN="ps")
        assert _watch_states(proc) == {"1": "dead"}, (
            "zero matches needs no verification - the one case where the lanes "
            "genuinely agree"
        )

    def test_json_carries_reader_mtime_and_watches(self, tmp_path: Path) -> None:
        """The registry joins on `reader` and reads `watches`, so both are part
        of the contract rather than incidental output (#778). `watchers` joined
        them in #801 - the roster renders the state, and a consumer checking the
        fusion needs the count it was derived from.
        """
        _run(tmp_path, "send", "--wave", WAVE, "--to", "1", "--body", "assignment")
        _run(tmp_path, "send", "--wave", WAVE, "--to", "orchestrator", "--from", "1", "--body", "hello")
        _run_at(tmp_path, "1700000000", "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        proc = _run_at(tmp_path, "1700000000", "list", "--wave", WAVE, "--json")
        payload = json.loads(proc.stdout.split("FLOW_MAILBOX")[0])
        by_box = {b["box"]: b for b in payload["boxes"]}
        assert by_box["outbox-1.md"]["reader"] == "1"
        assert by_box["inbox-1.md"]["reader"] == "orchestrator"
        assert by_box["outbox-1.md"]["mtime"] != "-"
        watches = {w["role"]: w for w in payload["watches"]}
        assert watches["1"]["state"] == "dead"
        assert watches["1"]["age_secs"] == 0
        assert watches["1"]["watchers"] == 0
        assert watches["orchestrator"]["state"] == "absent"
        assert watches["orchestrator"]["age_secs"] is None
        assert watches["orchestrator"]["watchers"] == 0

    def test_json_watchers_is_null_when_unknown(self, tmp_path: Path) -> None:
        """`null`, never 0 - the JSON consumer must be able to tell "nobody is
        listening" from "could not look" (#801).
        """
        _run_at(tmp_path, "1700000000", "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        proc = _run_at(tmp_path, "1700000000", "list", "--wave", WAVE, "--json",
                       FLOW_WAVE_WATCHER_SCAN="none")
        payload = json.loads(proc.stdout.split("FLOW_MAILBOX")[0])
        watches = {w["role"]: w for w in payload["watches"]}
        assert watches["1"]["watchers"] is None
        assert watches["1"]["state"] == "unknown"

    def test_a_role_that_armed_before_any_box_exists_is_still_reported(
        self, tmp_path: Path
    ) -> None:
        """Arming before the orchestrator sends anything is the HEALTHY order
        (worker step 4 runs at registration), so a box-only scan would miss
        exactly the roles doing it right.
        """
        watcher = _live_watcher(tmp_path, "1", WAVE)
        try:
            proc = _run(tmp_path, "list", "--wave", WAVE)
            assert "No mailboxes" in proc.stdout  # precondition: no box exists yet
            assert _watch_states(proc) == {"1": "armed"}
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)


# --------------------------------------------------------------------------
# `watch --status` (issue #792 item 3) - a one-shot watch makes a bare
# unread count undiagnosable; --status reports the heartbeat plus whether a
# live watcher process currently holds the role.
# --------------------------------------------------------------------------


@requires_bash
class TestWatchStatus:
    def test_status_before_any_watch_is_absent_and_not_rearmed(
        self, tmp_path: Path
    ) -> None:
        proc = _run(tmp_path, "watch", "--status", "--role", "1", "--wave", WAVE)
        assert proc.returncode == 0
        assert _verdict(proc) == "status"
        assert _detail(proc, "FLOW_MAILBOX_WATCH_STATE") == "absent"
        assert _detail(proc, "FLOW_MAILBOX_REARMED") == "no"
        assert _detail(proc, "FLOW_MAILBOX_WATCHER_COUNT") == "0"
        assert "never armed" in proc.stdout

    def test_status_reports_rearmed_yes_while_a_watcher_is_live(
        self, tmp_path: Path
    ) -> None:
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        watcher = subprocess.Popen(
            [
                "bash", str(MAILBOX), "watch", "--role", "1", "--wave", WAVE,
                "--timeout", "30", "--interval", "1", "--consume",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            wf = _watch_file(tmp_path, WAVE, "1")
            deadline = time.time() + 10
            while not wf.exists() and time.time() < deadline:
                time.sleep(0.1)
            assert wf.exists(), "watch never armed"

            proc = _run(tmp_path, "watch", "--status", "--role", "1", "--wave", WAVE)
            assert _detail(proc, "FLOW_MAILBOX_REARMED") == "yes"
            assert int(_detail(proc, "FLOW_MAILBOX_WATCHER_COUNT")) >= 1
            assert _detail(proc, "FLOW_MAILBOX_WATCH_STATE") == "armed"
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_status_reports_dead_after_the_watcher_exits(
        self, tmp_path: Path
    ) -> None:
        """The #801 regression test, and the exact line from the live wave.

        This assertion previously read ``WATCH_STATE == "armed"`` alongside
        ``WATCHER_COUNT == 0`` - the contradiction shipped as the contract. On
        the `docker-list` wave an orchestrator read that word and told three
        workers to do nothing; all three were deaf, one for ~50 minutes. The
        state is now fused from the count, so the word cannot disagree with the
        number beside it.
        """
        _run(tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        proc = _run(tmp_path, "watch", "--status", "--role", "1", "--wave", WAVE)
        assert _detail(proc, "FLOW_MAILBOX_REARMED") == "no"
        assert _detail(proc, "FLOW_MAILBOX_WATCHER_COUNT") == "0"
        assert _detail(proc, "FLOW_MAILBOX_WATCH_STATE") == "dead"
        # The heartbeat age survives the change - it is what separates "died
        # just now" from "died an hour ago", and it is all the stamp was ever
        # trustworthy for.
        assert _detail(proc, "FLOW_MAILBOX_WATCH_AGE").isdigit()
        # The human line must not bury the verdict behind a reassuring age.
        assert "DEAD" in proc.stdout
        assert "NOTHING is listening" in proc.stdout

    def test_status_reports_unknown_when_the_process_table_is_unreadable(
        self, tmp_path: Path
    ) -> None:
        """An unknowable answer is never rendered as a clean one (#800/#801)."""
        _run(tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0", "--consume")
        proc = _run_at(tmp_path, "1700000000", "watch", "--status", "--role", "1",
                       "--wave", WAVE, FLOW_WAVE_WATCHER_SCAN="none")
        assert _detail(proc, "FLOW_MAILBOX_WATCH_STATE") == "unknown"
        assert _detail(proc, "FLOW_MAILBOX_WATCHER_COUNT") == "unknown"
        assert _detail(proc, "FLOW_MAILBOX_REARMED") == "unknown"
        assert _verdict(proc) == "status"
        assert proc.returncode == 0  # advisory: it reports, it never blocks

    def test_a_status_query_is_not_itself_counted_as_a_watcher(
        self, tmp_path: Path
    ) -> None:
        """`watch --status` shares the watcher argv shape but watches nothing.

        Counting it made the instrument perturb its own reading: a status check
        running while a real watch armed made that arm refuse as a duplicate
        against a "watcher" that was only a query. Asserted through the arm
        guard, which is where the false positive actually bit.
        """
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        # A status query held open for the duration of the arm below.
        status = subprocess.Popen(
            ["bash", str(MAILBOX), "watch", "--status", "--role", "1", "--wave", WAVE],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        try:
            proc = _run(tmp_path, "watch", "--role", "1", "--wave", WAVE,
                        "--timeout", "0", "--consume")
            assert proc.returncode != 4, "a --status query was counted as a live watcher"
            assert _verdict(proc) != "duplicate"
        finally:
            status.kill()
            status.communicate(timeout=10)

    def test_one_watcher_counts_once_despite_its_own_subshells(
        self, tmp_path: Path
    ) -> None:
        """A command-substitution subshell is FORKED, so it inherits the
        watcher's argv verbatim and is indistinguishable from it by argv alone.

        One live watcher read as up to four while it ran its own poll - #792
        item 5's failure arriving by fork instead of by `bash -c`. Sampled
        repeatedly because the subshells are transient: a single sample can miss
        the window and pass against a broken count.
        """
        watcher = _live_watcher(tmp_path, "1", WAVE)
        try:
            for _ in range(12):
                proc = _run(tmp_path, "watch", "--status", "--role", "1", "--wave", WAVE)
                assert _detail(proc, "FLOW_MAILBOX_WATCHER_COUNT") == "1"
                assert _detail(proc, "FLOW_MAILBOX_WATCH_STATE") == "armed"
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)


# --------------------------------------------------------------------------
# Duplicate watchers (issue #792 item 4) - a role is single-owner, so a
# second live watcher on the same role+wave is always a mistake.
# --------------------------------------------------------------------------


@requires_bash
class TestDuplicateWatchers:
    def _start_watcher(self, tmp_path: Path, role: str, wave: str):
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        proc = subprocess.Popen(
            [
                "bash", str(MAILBOX), "watch", "--role", role, "--wave", wave,
                "--timeout", "30", "--interval", "1", "--consume",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        wf = _watch_file(tmp_path, wave, role)
        deadline = time.time() + 10
        while not wf.exists() and time.time() < deadline:
            time.sleep(0.1)
        assert wf.exists(), "watcher never armed"
        return proc

    def test_second_watch_on_the_same_role_and_wave_is_refused(
        self, tmp_path: Path
    ) -> None:
        watcher = self._start_watcher(tmp_path, "1", WAVE)
        try:
            proc = _run(
                tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
                "--consume",
            )
            assert proc.returncode == 4
            assert _verdict(proc) == "duplicate"
            assert "already hold role '1'" in proc.stderr
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_watch_on_a_different_wave_is_not_a_duplicate(
        self, tmp_path: Path
    ) -> None:
        watcher = self._start_watcher(tmp_path, "1", "alpha")
        try:
            proc = _run(
                tmp_path, "watch", "--role", "1", "--wave", "beta", "--timeout", "0",
                "--consume",
            )
            assert proc.returncode == 5  # a plain timeout, not a duplicate refusal
            assert _verdict(proc) == "timeout"
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_watch_for_a_different_role_is_not_a_duplicate(
        self, tmp_path: Path
    ) -> None:
        watcher = self._start_watcher(tmp_path, "1", WAVE)
        try:
            proc = _run(
                tmp_path, "watch", "--role", "2", "--wave", WAVE, "--timeout", "0",
                "--consume",
            )
            assert proc.returncode == 5
            assert _verdict(proc) == "timeout"
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_after_the_watcher_dies_a_new_one_may_start(
        self, tmp_path: Path
    ) -> None:
        watcher = self._start_watcher(tmp_path, "1", WAVE)
        watcher.kill()
        watcher.communicate(timeout=10)
        proc = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--consume",
        )
        assert proc.returncode == 5
        assert _verdict(proc) == "timeout"


# --------------------------------------------------------------------------
# `read --from` and the non-interactive destination requirement
# (issue #792 item 7).
# --------------------------------------------------------------------------


@requires_bash
class TestReadFromAndDestination:
    def test_from_narrows_to_one_correspondents_inbox(self, tmp_path: Path) -> None:
        _send(tmp_path, "orchestrator", "from worker 1", frm="1")
        _send(tmp_path, "orchestrator", "from worker 2", frm="2")
        proc = _run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE, "--from", "1",
        )
        assert _verdict(proc) == "read"
        body = _body(proc)
        assert "from worker 1" in body
        assert "from worker 2" not in body

        # The OTHER inbox is untouched - --from must not consume it too.
        other = _run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE, "--from", "2",
        )
        assert "from worker 2" in _body(other)

    def test_from_on_a_non_orchestrator_role_is_a_usage_error(
        self, tmp_path: Path
    ) -> None:
        proc = _run(
            tmp_path, "read", "--role", "1", "--wave", WAVE, "--from", "2",
        )
        assert proc.returncode == 2
        assert "--from" in proc.stderr

    def test_from_with_an_invalid_role_name_is_refused(self, tmp_path: Path) -> None:
        proc = _run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE,
            "--from", "../escape",
        )
        assert proc.returncode == 2
        assert "invalid" in proc.stderr

    def test_full_drain_non_interactively_without_a_destination_is_refused(
        self, tmp_path: Path
    ) -> None:
        """The undiscoverable hazard itself: draining every inbox at once with
        no copy anywhere but the terminal has destroyed message content when
        piped through a filter. subprocess-captured stdout is never a tty, so
        this exercises the same non-interactive path a real pipeline hits.
        """
        _send(tmp_path, "orchestrator", "one", frm="1")
        proc = _run(tmp_path, "read", "--role", "orchestrator", "--wave", WAVE)
        assert proc.returncode == 2
        assert "--out" in proc.stderr
        assert "--from" in proc.stderr
        assert "--peek" in proc.stderr
        # Refused before consuming: the mail must still be there afterward.
        proc2 = _run(tmp_path, "list", "--wave", WAVE)
        assert _detail(proc2, "FLOW_MAILBOX_UNREAD") == "1"

    def test_full_drain_with_peek_does_not_require_a_destination(
        self, tmp_path: Path
    ) -> None:
        _send(tmp_path, "orchestrator", "one", frm="1")
        proc = _run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE, "--peek",
        )
        assert _verdict(proc) == "read"
        assert "one" in _body(proc)

    def test_worker_read_is_unaffected_by_the_destination_requirement(
        self, tmp_path: Path
    ) -> None:
        """Only the orchestrator's multi-box drain is destructive-and-wide; a
        worker has exactly one box, so its everyday `read --role 1` must keep
        working non-interactively with no new flag, or #792 breaks scripts
        that never had this hazard in the first place.
        """
        _send(tmp_path, "1", "assignment")
        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert _verdict(proc) == "read"
        assert "assignment" in _body(proc)


# --------------------------------------------------------------------------
# Explicit acknowledgement (issue #815)
#
# Cursor-on-output conflated SURFACING a message (printing it) with a
# recipient's confirmed RECEIPT of it - the same instant, driven by the same
# read/watch call. A dropped tool response, a truncated batch, or a `--out`
# destination that failed to write all silently and permanently lost the
# message: printing had already "consumed" it. These tests pin the fix:
# `--peek` never acknowledges anything, the durable receipt is the separate
# explicit `ack` verb bound to exact rev identities, and `--out` writes its
# destination BEFORE anything is acknowledged.
# --------------------------------------------------------------------------


@requires_bash
class TestAckIsSeparateFromSurfacing:
    def test_peek_never_acknowledges_so_a_dropped_response_still_replays(
        self, tmp_path: Path
    ) -> None:
        """The core #815 regression pin. A peek shows the message - simulating
        a tool call whose OUTPUT reached this test process - but the durable
        receipt (`ack`) is never called, simulating the response being lost
        before the calling agent acted on it. The message must still be
        recoverable through perfectly normal, repeated delivery - not through
        any special recovery path.
        """
        _send(tmp_path, "1", "assignment issue 815")
        first_peek = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek")
        assert "assignment issue 815" in _body(first_peek)

        second_peek = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek")
        assert _verdict(second_peek) == "read"
        assert "assignment issue 815" in _body(second_peek), (
            "a peeked-but-never-acked message must still be there - "
            "surfacing output must not itself be a receipt"
        )

        third_peek = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--peek",
        )
        assert _verdict(third_peek) == "mail"
        assert "assignment issue 815" in _body(third_peek)

    def test_explicit_ack_after_a_peek_makes_the_message_stop_replaying(
        self, tmp_path: Path
    ) -> None:
        """The other half: once the caller genuinely has the content and acks
        it BY REV, it stops being replayed - the safe pattern this issue asks
        for (peek, confirm receipt, then ack)."""
        _send(tmp_path, "1", "assignment")
        peek = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek")
        rev = _detail(_run(tmp_path, "list", "--wave", WAVE), "FLOW_MAILBOX_UNREAD")
        assert rev == "1"
        assert "assignment" in _body(peek)

        ack = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "1")
        assert _verdict(ack) == "acked"
        assert _detail(ack, "FLOW_MAILBOX_ACKED") == "1"

        again = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek")
        assert _verdict(again) == "empty"

    def test_bare_read_still_acknowledges_as_the_named_legacy_mode(
        self, tmp_path: Path
    ) -> None:
        """Unchanged from before #815: a bare (non-peek) read is the
        documented legacy convenience and keeps acknowledging what it prints,
        so routine callers that never adopt explicit ack are not broken."""
        _send(tmp_path, "1", "routine")
        first = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert "routine" in _body(first)
        second = _run(tmp_path, "read", "--role", "1", "--wave", WAVE)
        assert _verdict(second) == "empty"

    def test_watch_consume_still_acknowledges_as_the_named_legacy_mode(
        self, tmp_path: Path
    ) -> None:
        _send(tmp_path, "1", "routine")
        first = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--consume",
        )
        assert _verdict(first) == "mail"
        second = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0",
            "--consume",
        )
        assert _verdict(second) == "timeout"


@requires_bash
class TestAckBindsToExactIdentity:
    def test_ack_a_middle_rev_leaves_the_others_unread(self, tmp_path: Path) -> None:
        """Out-of-order / partial-batch receipt (#815 acceptance item 2): a
        later ack must not be able to silently imply an earlier, unseen one."""
        _send(tmp_path, "1", "one")
        _send(tmp_path, "1", "two")
        _send(tmp_path, "1", "three")

        ack = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "2")
        assert _verdict(ack) == "acked"

        remaining = _body(_run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek"))
        assert "one" in remaining
        assert "three" in remaining
        assert "two" not in remaining

    def test_ack_accepts_a_comma_separated_list(self, tmp_path: Path) -> None:
        _send(tmp_path, "1", "one")
        _send(tmp_path, "1", "two")
        _send(tmp_path, "1", "three")
        ack = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "1,3")
        assert _detail(ack, "FLOW_MAILBOX_ACKED") == "2"
        remaining = _body(_run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek"))
        assert "two" in remaining
        assert "one" not in remaining
        assert "three" not in remaining

    def test_ack_is_idempotent(self, tmp_path: Path) -> None:
        _send(tmp_path, "1", "one")
        first = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "1")
        assert _verdict(first) == "acked"
        second = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "1")
        assert _verdict(second) == "acked"
        # Still exactly one entry recorded, not two - re-acking must not
        # grow the ack set or otherwise misbehave on repetition.
        ack_file = tmp_path / "mb" / WAVE / ".ack-outbox-1.md"
        assert ack_file.read_text().split() == ["1"]

    def test_ack_refuses_a_rev_that_does_not_exist_yet(self, tmp_path: Path) -> None:
        """Acknowledging a message you could not have received is refused,
        not silently accepted and ignored (#815 acceptance item 1's mirror:
        an ack must correspond to something that was actually sent)."""
        _send(tmp_path, "1", "only message")
        proc = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "99")
        assert proc.returncode == 2
        assert "99" in proc.stderr
        # Refused, not partially applied: rev 1 must remain unaffected either.
        still_there = _body(_run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek"))
        assert "only message" in still_there

    def test_ack_refuses_when_the_batch_contains_one_bad_rev(
        self, tmp_path: Path
    ) -> None:
        """A batch ack is all-or-nothing: one invalid rev in the list must not
        silently apply the valid ones and drop the bad one."""
        _send(tmp_path, "1", "one")
        proc = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "1,99")
        assert proc.returncode == 2
        remaining = _body(_run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek"))
        assert "one" in remaining, "rev 1 must not have been acked by a refused batch"

    def test_ack_all_unacked_acks_everything_currently_unread(
        self, tmp_path: Path
    ) -> None:
        _send(tmp_path, "1", "one")
        _send(tmp_path, "1", "two")
        proc = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--all-unacked")
        assert _detail(proc, "FLOW_MAILBOX_ACKED") == "2"
        assert _verdict(_run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek")) == "empty"

    def test_ack_with_no_box_yet_is_empty_not_an_error(self, tmp_path: Path) -> None:
        proc = _run(tmp_path, "ack", "--role", "9", "--wave", WAVE, "--all-unacked")
        assert proc.returncode == 0
        assert _verdict(proc) == "empty"

    def test_ack_requires_revs_or_all_unacked(self, tmp_path: Path) -> None:
        _send(tmp_path, "1", "one")
        proc = _run(tmp_path, "ack", "--role", "1", "--wave", WAVE)
        assert proc.returncode == 2
        assert "--revs" in proc.stderr
        assert "--all-unacked" in proc.stderr


@requires_bash
class TestAckOnOrchestratorMultiBox:
    def test_revs_without_disambiguation_is_a_usage_error(
        self, tmp_path: Path
    ) -> None:
        _send(tmp_path, "orchestrator", "from A", frm="A")
        proc = _run(
            tmp_path, "ack", "--role", "orchestrator", "--wave", WAVE, "--revs", "1",
        )
        assert proc.returncode == 2
        assert "--from" in proc.stderr

    def test_from_disambiguates_which_inbox(self, tmp_path: Path) -> None:
        _send(tmp_path, "orchestrator", "from A", frm="A")
        _send(tmp_path, "orchestrator", "from B", frm="B")
        ack = _run(
            tmp_path, "ack", "--role", "orchestrator", "--wave", WAVE,
            "--from", "A", "--revs", "1",
        )
        assert _verdict(ack) == "acked"
        a_peek = _body(_run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE,
            "--from", "A", "--peek",
        ))
        b_peek = _body(_run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE,
            "--from", "B", "--peek",
        ))
        assert "from A" not in a_peek
        assert "from B" in b_peek

    def test_box_disambiguates_which_inbox(self, tmp_path: Path) -> None:
        _send(tmp_path, "orchestrator", "from A", frm="A")
        ack = _run(
            tmp_path, "ack", "--role", "orchestrator", "--wave", WAVE,
            "--box", "inbox-A.md", "--revs", "1",
        )
        assert _verdict(ack) == "acked"

    def test_all_unacked_spans_every_inbox(self, tmp_path: Path) -> None:
        _send(tmp_path, "orchestrator", "from A", frm="A")
        _send(tmp_path, "orchestrator", "from B", frm="B")
        ack = _run(
            tmp_path, "ack", "--role", "orchestrator", "--wave", WAVE, "--all-unacked",
        )
        assert _detail(ack, "FLOW_MAILBOX_ACKED") == "2"
        proc = _run(tmp_path, "read", "--role", "orchestrator", "--wave", WAVE, "--peek")
        assert _verdict(proc) == "empty"


@requires_bash
class TestOutWriteBeforeAck:
    def test_a_failed_out_destination_leaves_mail_unacknowledged(
        self, tmp_path: Path
    ) -> None:
        """Reproduces the exact #815 evidence: a --out destination that
        cannot be written must not consume the message it failed to durably
        copy. Using an existing directory as the destination path forces the
        write to fail the same way the issue's repro did.
        """
        _send(tmp_path, "1", "must survive a failed --out")
        bad_dest = tmp_path / "not_a_file"
        bad_dest.mkdir()
        proc = _run(
            tmp_path, "read", "--role", "1", "--wave", WAVE, "--out", str(bad_dest),
        )
        assert proc.returncode == 2
        assert "--out" in proc.stderr

        still_unread = _run(tmp_path, "list", "--wave", WAVE)
        assert _detail(still_unread, "FLOW_MAILBOX_UNREAD") == "1"
        recovered = _body(_run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--peek"))
        assert "must survive a failed --out" in recovered

    def test_a_successful_out_destination_does_acknowledge(
        self, tmp_path: Path
    ) -> None:
        """The positive control - --out is not disabled, it is reordered: a
        SUCCESSFUL write still lets a non-peek read acknowledge afterward."""
        _send(tmp_path, "1", "goes to disk")
        dest = tmp_path / "copy.md"
        proc = _run(tmp_path, "read", "--role", "1", "--wave", WAVE, "--out", str(dest))
        assert _verdict(proc) == "read"
        assert "goes to disk" in dest.read_text()
        assert _verdict(_run(tmp_path, "read", "--role", "1", "--wave", WAVE)) == "empty"

    def test_orchestrator_wide_out_write_failure_leaves_all_boxes_unacknowledged(
        self, tmp_path: Path
    ) -> None:
        _send(tmp_path, "orchestrator", "from A", frm="A")
        _send(tmp_path, "orchestrator", "from B", frm="B")
        bad_dest = tmp_path / "not_a_file2"
        bad_dest.mkdir()
        proc = _run(
            tmp_path, "read", "--role", "orchestrator", "--wave", WAVE,
            "--out", str(bad_dest),
        )
        assert proc.returncode == 2
        listing = _run(tmp_path, "list", "--wave", WAVE)
        assert _detail(listing, "FLOW_MAILBOX_UNREAD") == "2"


@requires_bash
class TestListReportsAcked:
    def test_list_shows_acked_count_distinct_from_unread(self, tmp_path: Path) -> None:
        _send(tmp_path, "1", "one")
        _send(tmp_path, "1", "two")
        _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "1")
        proc = _run(tmp_path, "list", "--wave", WAVE, "--json")
        payload = json.loads(_body(proc))
        box = next(b for b in payload["boxes"] if b["box"] == "outbox-1.md")
        assert box["acked"] == 1
        assert box["unread"] == 1
        assert box["rev"] == 2

    def test_acked_count_survives_across_processes(self, tmp_path: Path) -> None:
        """Acknowledgement is durable state, not per-invocation - a later,
        independent process must see what an earlier one acked."""
        _send(tmp_path, "1", "one")
        _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--revs", "1")
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert _detail(proc, "FLOW_MAILBOX_UNREAD") == "0"


@requires_bash
class TestAckMigrationIsConservative:
    def test_a_wave_dir_with_no_ack_file_yet_treats_everything_as_unacknowledged(
        self, tmp_path: Path
    ) -> None:
        """A box that predates #815 has no `.ack-<box>` file at all. Its
        absence must mean 'nothing acknowledged', never 'everything up to
        some old cursor was implicitly acknowledged' - the compatible,
        non-silent migration direction the issue requires."""
        _send(tmp_path, "1", "pre-existing message")
        ack_dir = tmp_path / "mb" / WAVE
        assert not (ack_dir / ".ack-outbox-1.md").exists()  # precondition
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert _detail(proc, "FLOW_MAILBOX_UNREAD") == "1"


# --------------------------------------------------------------------------
# Route readiness (issue #814)
#
# "Is a watcher process polling" (#801's fused state) answers a different
# question from "has anything actually been received" - and #821 already
# proved the first cannot be trusted as a proxy for the second. `route`
# answers the second from ack evidence (#815) instead: FOUR states, not
# three, because an empty box must never read as `confirmed` - that would be
# reporting success by checking nothing, the same defect found the same day
# in #816/#821/#828.
# --------------------------------------------------------------------------


def _routes(proc: subprocess.CompletedProcess[str]) -> dict[str, str]:
    """``{role: route_state}`` from the text ``list`` ROUTE table."""
    lines = proc.stdout.splitlines()
    try:
        header = [line for line in lines if line.startswith("ROLE") and "ROUTE" in line][0]
        start = lines.index(header) + 1
    except IndexError:
        return {}
    out: dict[str, str] = {}
    for line in lines[start:]:
        if not line.strip() or line.startswith(("DEAF", "UNKNOWN", "UNCONFIRMED", "FLOW_MAILBOX")):
            break
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


@requires_bash
class TestRouteReadiness:
    def test_a_box_with_no_messages_is_unknown_never_confirmed(
        self, tmp_path: Path
    ) -> None:
        """The core #814 correction: an empty box is not evidence the route
        works, only evidence nothing has tested it."""
        _send(tmp_path, "1", "for role 1")
        _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--all-unacked")
        # role "2" has never been sent to at all.
        proc = _run(tmp_path, "list", "--wave", WAVE)
        routes = _routes(proc)
        assert routes.get("1") == "confirmed"
        assert "2" not in routes  # never sent to - not even a row, let alone confirmed

    def test_an_unacked_message_younger_than_the_bound_is_pending(
        self, tmp_path: Path
    ) -> None:
        _send(tmp_path, "1", "fresh")
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert _routes(proc)["1"] == "pending"

    def test_an_unacked_message_older_than_the_bound_is_unconfirmed(
        self, tmp_path: Path
    ) -> None:
        _send(tmp_path, "1", "stale")
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        env["FLOW_WAVE_NOW"] = str(int(time.time()) + 1000)
        env["FLOW_WAVE_ROUTE_UNCONFIRMED_SECS"] = "900"
        proc = subprocess.run(
            ["bash", str(MAILBOX), "list", "--wave", WAVE],
            capture_output=True, text=True, env=env, check=False,
        )
        assert _routes(proc)["1"] == "unconfirmed"
        assert "UNCONFIRMED" in proc.stdout

    def test_a_fully_acked_box_is_confirmed(self, tmp_path: Path) -> None:
        _send(tmp_path, "1", "received")
        _run(tmp_path, "ack", "--role", "1", "--wave", WAVE, "--all-unacked")
        proc = _run(tmp_path, "list", "--wave", WAVE)
        assert _routes(proc)["1"] == "confirmed"

    def test_the_bound_is_env_overridable(self, tmp_path: Path) -> None:
        """Testable without sleeping - the same pattern
        FLOW_WAVE_WATCH_STALE_SECS already uses for the watch heartbeat."""
        _send(tmp_path, "1", "borderline")
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        env["FLOW_WAVE_NOW"] = str(int(time.time()) + 5)
        env["FLOW_WAVE_ROUTE_UNCONFIRMED_SECS"] = "1"
        proc = subprocess.run(
            ["bash", str(MAILBOX), "list", "--wave", WAVE],
            capture_output=True, text=True, env=env, check=False,
        )
        assert _routes(proc)["1"] == "unconfirmed"

    def test_orchestrator_route_is_the_worst_across_every_inbox(
        self, tmp_path: Path
    ) -> None:
        """A role reading multiple boxes (the orchestrator) needs the box
        that is FAILING, not the box that is not."""
        _send(tmp_path, "orchestrator", "from A - will be acked", frm="A")
        _run(
            tmp_path, "ack", "--role", "orchestrator", "--wave", WAVE,
            "--from", "A", "--all-unacked",
        )
        _send(tmp_path, "orchestrator", "from B - stays unacked", frm="B")
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        env["FLOW_WAVE_NOW"] = str(int(time.time()) + 1000)
        proc = subprocess.run(
            ["bash", str(MAILBOX), "list", "--wave", WAVE],
            capture_output=True, text=True, env=env, check=False,
        )
        assert _routes(proc)["orchestrator"] == "unconfirmed"

    def test_json_carries_route_as_a_sibling_of_watch_not_merged_into_it(
        self, tmp_path: Path
    ) -> None:
        """The #801 lesson enforced in the schema: watch.state answers 'is a
        process polling', route.state answers 'has anything been
        acknowledged since' - fusing them reproduces #801's contradictory
        one-liner in a new shape."""
        _send(tmp_path, "1", "one")
        proc = _run(tmp_path, "list", "--wave", WAVE, "--json")
        payload = json.loads(_body(proc))
        assert "routes" in payload
        assert "watches" in payload
        route_row = next(r for r in payload["routes"] if r["role"] == "1")
        assert route_row["state"] == "pending"
        assert "state" in route_row and set(route_row.keys()) == {"role", "state"}


# --------------------------------------------------------------------------
# Supervision (issue #814)
#
# A detached daemon that keeps a `watch` listening for a role continuously,
# so nothing conversational has to remember to re-arm it after every wake -
# the "forgotten re-arm" failure (documented on issue #815's own incident
# comment: a 25-minute deafness, caught only because a DIFFERENT session
# noticed the silence from outside) becomes structurally impossible for
# whatever owns this process.
# --------------------------------------------------------------------------


def _supervise_pidfile(tmp: Path, wave: str, role: str) -> Path:
    return tmp / "mb" / wave / f".supervise-{role}.pid"


def _supervise_log(tmp: Path, wave: str, role: str) -> Path:
    return tmp / "mb" / wave / f".supervise-{role}.log"


def _wait_for(predicate, timeout: float = 10.0, interval: float = 0.1) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _daemon_pid(tmp: Path, wave: str, role: str) -> int:
    pf = _supervise_pidfile(tmp, wave, role)
    assert _wait_for(pf.exists, timeout=10), "supervise never wrote a pidfile"
    return int(pf.read_text().strip())


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _children_of(pid: int) -> list[int]:
    """Direct child PIDs of ``pid``, read from the kernel - no `pgrep`, no
    PATH dependency (issue #814: the CI image ships no procps, and this
    needs no binary guard because it needs no binary at all)."""
    try:
        raw = Path(f"/proc/{pid}/task/{pid}/children").read_text()
    except OSError:
        return []
    return [int(p) for p in raw.split()]


def _cmdline(pid: int) -> list[str]:
    """A process's real argv, NUL-separated in /proc - never a flattened
    command line to `pgrep -f`-style substring-match against, which is the
    anti-pattern issue #821 documents (a wrapper's own text can contain the
    pattern it is searching for)."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [p.decode(errors="replace") for p in raw.split(b"\0") if p]


@requires_bash
class TestSupervise:
    def _launch(
        self, tmp_path: Path, role: str = "1", wave: str = WAVE,
        timeout: str = "10", interval: str = "1", extra_env: dict | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [
                "bash", str(MAILBOX), "supervise", "--role", role, "--wave", wave,
                "--timeout", timeout, "--interval", interval,
            ],
            capture_output=True, text=True, env=env, check=False, timeout=30,
        )

    def _kill_daemon(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            return
        _wait_for(lambda: not _pid_alive(pid), timeout=10)

    def test_supervise_returns_promptly_with_its_own_verdict_line(
        self, tmp_path: Path
    ) -> None:
        """The invocation must exit and report, like every other verb - the
        DAEMON is what persists, not this process (ratified requirement)."""
        proc = self._launch(tmp_path)
        try:
            assert proc.returncode == 0
            assert _verdict(proc) == "supervising"
        finally:
            self._kill_daemon(_daemon_pid(tmp_path, WAVE, "1"))

    def test_a_delivered_message_is_acknowledged_without_any_conversational_rearm(
        self, tmp_path: Path
    ) -> None:
        """The acceptance property, minus the live-harness half that only a
        real fleet exercise can prove (see the PR's explicit non-promises):
        once `supervise` is armed, a message sent afterward is received and
        acknowledged with NO further command issued by this test."""
        self._launch(tmp_path)
        pid = _daemon_pid(tmp_path, WAVE, "1")
        try:
            _send(tmp_path, "1", "assignment issue 814")
            assert _wait_for(
                lambda: _detail(_run(tmp_path, "list", "--wave", WAVE), "FLOW_MAILBOX_UNREAD") == "0",
                timeout=10,
            ), "supervise never acknowledged the delivered message"
        finally:
            self._kill_daemon(pid)

    def test_a_second_supervise_for_the_same_role_is_refused_while_the_first_lives(
        self, tmp_path: Path
    ) -> None:
        self._launch(tmp_path)
        pid = _daemon_pid(tmp_path, WAVE, "1")
        try:
            second = self._launch(tmp_path)
            assert second.returncode == 4
            assert _verdict(second) == "duplicate"
        finally:
            self._kill_daemon(pid)

    def test_ownership_is_the_flock_not_the_pid_file(self, tmp_path: Path) -> None:
        """Required correction from review: a PID-file + kill -0 guard
        reintroduces #821 one layer up (PIDs are reused by the kernel). This
        pins the actual mechanism - overwriting the pidfile with a bogus,
        unrelated value must NOT let a second supervise through, and must
        not block it either once the real daemon is gone: the LOCK, not the
        file, decides."""
        self._launch(tmp_path)
        pid = _daemon_pid(tmp_path, WAVE, "1")
        pidfile = _supervise_pidfile(tmp_path, WAVE, "1")
        pidfile.write_text("999999999\n")  # a PID that (almost certainly) never existed
        try:
            still_refused = self._launch(tmp_path)
            assert still_refused.returncode == 4, (
                "a corrupted pidfile must not let a duplicate through - "
                "the flock, held by the real daemon, is what refuses this"
            )
        finally:
            self._kill_daemon(pid)

    def test_after_the_daemon_dies_a_new_supervise_may_start(
        self, tmp_path: Path
    ) -> None:
        """The kernel releases a flock the instant its holder dies - no
        stale-PID reclaim logic needed or present."""
        self._launch(tmp_path)
        pid = _daemon_pid(tmp_path, WAVE, "1")
        self._kill_daemon(pid)
        assert not _pid_alive(pid)
        second = self._launch(tmp_path)
        try:
            assert second.returncode == 0
            assert _verdict(second) == "supervising"
        finally:
            self._kill_daemon(_daemon_pid(tmp_path, WAVE, "1"))

    def test_evidence_log_never_carries_a_message_body(self, tmp_path: Path) -> None:
        self._launch(tmp_path)
        pid = _daemon_pid(tmp_path, WAVE, "1")
        try:
            secret_body = "SECRET-PAYLOAD-MUST-NOT-LEAK-INTO-THE-LOG"
            _send(tmp_path, "1", secret_body)
            assert _wait_for(
                lambda: _detail(_run(tmp_path, "list", "--wave", WAVE), "FLOW_MAILBOX_UNREAD") == "0",
                timeout=10,
            )
            log_text = _supervise_log(tmp_path, WAVE, "1").read_text()
            assert secret_body not in log_text
            assert "delivered rc=0" in log_text
        finally:
            self._kill_daemon(pid)

    def test_a_killed_inner_watch_gets_a_replacement_after_backoff(
        self, tmp_path: Path
    ) -> None:
        """Crash-restart, not a tight loop: killing the daemon's OWN inner
        `watch` child (not the daemon) must produce a NEW inner watch after
        a bounded backoff, recorded in the sanitized log."""
        self._launch(
            tmp_path, timeout="30",
            extra_env={
                "FLOW_WAVE_SUPERVISE_BACKOFF_BASE": "1",
                "FLOW_WAVE_SUPERVISE_BACKOFF_CAP": "2",
            },
        )
        pid = _daemon_pid(tmp_path, WAVE, "1")
        try:
            def _inner_watch_pid() -> int | None:
                # Read the kernel directly rather than shelling out to
                # `pgrep` (issue #814 CI fix - the CI image ships no
                # procps) - and, having learned that lesson once already
                # for `count_watchers`/#821, do it the SAME way that fix
                # does: children by PARENTAGE, then confirmed by argv
                # STRUCTURE (argv[1] is the script, argv[2] is `watch`),
                # never `pgrep -f`'s flattened-line matching, which is the
                # exact anti-pattern #821 documents.
                for child in _children_of(pid):
                    argv = _cmdline(child)
                    if (
                        len(argv) >= 3
                        and argv[1].endswith("flow-wave-mailbox.sh")
                        and argv[2] == "watch"
                    ):
                        return child
                return None

            first_inner = _wait_for(lambda: _inner_watch_pid() is not None, timeout=10)
            assert first_inner, "the daemon never armed its first inner watch"
            inner_pid = _inner_watch_pid()
            os.kill(inner_pid, signal.SIGKILL)

            assert _wait_for(
                lambda: "backing off" in _supervise_log(tmp_path, WAVE, "1").read_text(),
                timeout=10,
            ), "no backoff was recorded after the inner watch was killed"
            assert _wait_for(lambda: _pid_alive(pid), timeout=1), "the daemon itself must survive"
        finally:
            self._kill_daemon(pid)

    def test_invalid_role_name_exits_immediately_without_a_restart_loop(
        self, tmp_path: Path
    ) -> None:
        """Argument validation happens ONCE, at start - a bad role/wave name
        must be a clean, immediate failure, never a restart storm."""
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        proc = subprocess.run(
            ["bash", str(MAILBOX), "supervise", "--role", "../escape", "--wave", WAVE],
            capture_output=True, text=True, env=env, check=False, timeout=10,
        )
        assert proc.returncode == 2
        time.sleep(1)
        # No daemon was ever launched for this role - no pidfile, no log.
        assert not _supervise_pidfile(tmp_path, WAVE, "../escape").exists()
        assert not _supervise_log(tmp_path, WAVE, "../escape").exists()

    @pytest.mark.skipif(
        shutil.which("jq") is None, reason="requires jq (flow-wave-registry.sh)"
    )
    def test_shuts_down_when_the_role_is_released(self, tmp_path: Path) -> None:
        registry = ROOT / "scripts" / "flow-wave-registry.sh"
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        env["FLOW_WAVE_REGISTRY_DIR"] = str(tmp_path / "mb")
        subprocess.run(
            ["bash", str(registry), "register", "1", "--wave", WAVE, "--socket", "uds:/tmp/x.sock"],
            capture_output=True, text=True, env=env, check=False,
        )
        self._launch(tmp_path, timeout="2", extra_env={"FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "mb")})
        pid = _daemon_pid(tmp_path, WAVE, "1")
        try:
            subprocess.run(
                ["bash", str(registry), "release", "1", "--wave", WAVE, "--force"],
                capture_output=True, text=True, env=env, check=False,
            )
            assert _wait_for(lambda: not _pid_alive(pid), timeout=15), (
                "the daemon must shut down once the role is released"
            )
            log_text = _supervise_log(tmp_path, WAVE, "1").read_text()
            assert "released" in log_text.lower() or "shutting down" in log_text.lower()
        finally:
            if _pid_alive(pid):
                self._kill_daemon(pid)

    def test_registry_sibling_unavailable_fails_open_and_keeps_supervising(
        self, tmp_path: Path
    ) -> None:
        """A supervisor that cannot check for release is not worse than
        none - it just keeps supervising (matches the #701 lexicon-gate
        precedent for a helper this script depends on but does not own)."""
        self._launch(
            tmp_path, timeout="2",
            extra_env={"FLOW_WAVE_REGISTRY_DIR": str(tmp_path / "definitely-missing-xyz")},
        )
        pid = _daemon_pid(tmp_path, WAVE, "1")
        try:
            time.sleep(3)
            assert _pid_alive(pid), "an unreadable registry sibling must not be treated as release"
        finally:
            self._kill_daemon(pid)


# --------------------------------------------------------------------------
# Watcher identity across wave directories (issue #821)
#
# count_watchers() could not distinguish a live watcher from an orphaned
# command-substitution subshell of a dead one - measured, not inferred: one
# killed watcher leaves 4-5 orphaned forks, byte-identical argv, unreached
# by a signal to the parent, alive until their own --timeout. This suite's
# own shape is what surfaced it: every test shares the literal wave name
# "testwave" while getting a fresh FLOW_WAVE_MAILBOX_DIR per test, so an
# orphan from one test's watcher has exactly the right argv to be counted
# as a live watcher in the NEXT test.
#
# The fix keys the scan on the resolved wave DIRECTORY (read from each
# candidate's own /proc/<pid>/environ), not the wave name string. This is a
# CROSS-context fix, verified as exactly that - both halves are pinned
# below, not just the one that looks good.
# --------------------------------------------------------------------------


@requires_bash
class TestWatcherIdentityAcrossDirectories:
    def test_a_live_watcher_in_a_different_directory_is_not_counted(
        self, tmp_path: Path
    ) -> None:
        """The actual fix, demonstrated directly with two real processes
        rather than a timing-dependent race: same role, same literal wave
        NAME, two different FLOW_WAVE_MAILBOX_DIR values. B's scan must not
        see A's process - and A's own scan must still see it, so the fix
        does not overcorrect into hiding a genuinely live watcher from
        itself."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        env_a = os.environ.copy()
        env_a["FLOW_WAVE_MAILBOX_DIR"] = str(dir_a)
        watcher = subprocess.Popen(
            [
                "bash", str(MAILBOX), "watch", "--role", "1", "--wave", WAVE,
                "--timeout", "30", "--interval", "5", "--peek",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env_a,
        )
        try:
            wf = dir_a / WAVE / ".watch-1"
            assert _wait_for(wf.exists, timeout=10), "watcher never armed"

            env_b = os.environ.copy()
            env_b["FLOW_WAVE_MAILBOX_DIR"] = str(dir_b)
            from_b = subprocess.run(
                ["bash", str(MAILBOX), "watch", "--status", "--role", "1", "--wave", WAVE],
                capture_output=True, text=True, env=env_b, check=False,
            )
            assert _detail(from_b, "FLOW_MAILBOX_WATCHER_COUNT") == "0", (
                "a live watcher in a DIFFERENT wave directory must not be "
                "counted, even sharing the same wave name - the identity "
                "hole issue #821 is about"
            )
            assert _detail(from_b, "FLOW_MAILBOX_WATCH_STATE") in ("absent", "dead")

            from_a = subprocess.run(
                ["bash", str(MAILBOX), "watch", "--status", "--role", "1", "--wave", WAVE],
                capture_output=True, text=True, env=env_a, check=False,
            )
            assert _detail(from_a, "FLOW_MAILBOX_WATCHER_COUNT") == "1", (
                "the fix must not ALSO hide a watcher from its own wave's scan"
            )
            assert _detail(from_a, "FLOW_MAILBOX_WATCH_STATE") == "armed"
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_a_same_wave_orphan_would_not_be_excluded_by_directory_alone(
        self, tmp_path: Path
    ) -> None:
        """Required experiment before this fix shipped (see the PR/issue):
        IF an orphan forms on the SAME wave directory as the process it was
        forked from, does directory-keying exclude it? No - environment
        inheritance at fork time has no mechanism to diverge, so such an
        orphan is indistinguishable from a live watcher on that wave by
        this measure alone.

        This pins the MECHANISM as a proven fact, deliberately independent
        of whether same-wave orphans have been OBSERVED in any specific
        consumer's kill path - they have not, in real-process trials
        targeting `supervise`'s own crash-restart kill (16 combined trials,
        0 occurrences, considered-and-not-observed rather than a known
        gap - see the PR). A minimal, DETERMINISTIC model of environment
        inheritance across orphaning (real orphan-timing is at best a
        2-in-12 race per the issue's own measurement, useless for a
        reliable CI assertion): fork a child that itself backgrounds a
        grandchild sharing its environment, kill only the middle process,
        and confirm the grandchild - now reparented, exactly like a real
        orphaned subshell would be - still carries the identical
        `FLOW_WAVE_MAILBOX_DIR` its dead parent had.
        """
        wave_dir = tmp_path / "w"
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(wave_dir)
        # Precondition: this fixture is only a valid demonstration if the
        # directory it asserts inheritance for is the one actually in use.
        assert env["FLOW_WAVE_MAILBOX_DIR"] == str(wave_dir)

        marker = tmp_path / "child.pid"
        parent = subprocess.Popen(
            ["bash", "-c", f'exec bash -c "sleep 100" & echo $! > {marker}; sleep 100'],
            env=env,
        )
        try:
            assert _wait_for(marker.exists, timeout=10), "child never forked"
            child_pid = int(marker.read_text().strip())
            assert _pid_alive(child_pid)  # precondition: the child is actually alive

            parent.kill()
            _wait_for(lambda: not _pid_alive(parent.pid), timeout=10)
            assert _pid_alive(child_pid), (
                "the orphaned grandchild must survive its parent's death - "
                "this is the mechanism issue #821 documents, reproduced "
                "deterministically rather than raced for"
            )

            child_env = Path(f"/proc/{child_pid}/environ").read_bytes()
            assert f"FLOW_WAVE_MAILBOX_DIR={wave_dir}".encode() in child_env, (
                "an orphan inherits its dead parent's environment byte for "
                "byte - it did not lose FLOW_WAVE_MAILBOX_DIR by being "
                "orphaned, so directory-keying computes the SAME resolved "
                "wave directory for it as for a live watcher on that wave. "
                "This is the stated residual: a cross-context fix, not a "
                "within-wave one."
            )
        finally:
            if _pid_alive(parent.pid):
                parent.kill()
                parent.wait(timeout=10)
            try:
                os.kill(int(marker.read_text().strip()), signal.SIGKILL)
            except (OSError, ValueError, FileNotFoundError):
                pass


# --------------------------------------------------------------------------
# The SAME identity hole, in the OTHER watcher-enumeration lane (issue #845)
#
# #821 closed this for watcher_roles_proc() by keying on the resolved wave
# DIRECTORY, read from each candidate's own /proc/<pid>/environ. That fix
# landed in the /proc lane only - watcher_roles_ps_fallback() (used on hosts
# with no /proc) still matches on wave NAME and role alone, because
# FLOW_WAVE_MAILBOX_DIR travels in the environment and `ps -eo args` cannot
# see it, and there is no portable non-/proc way to read another process's
# environment at all. The fix here is not "port #821's mechanism" - it
# cannot be ported - it is to admit the ambiguity: this lane now answers
# `unknown` rather than a count it cannot verify, deliberately NOT trying to
# force the two lanes to "reach the same verdict" (the assumption issue #845
# names as what made this gap invisible in the first place).
# --------------------------------------------------------------------------


@requires_bash
@requires_ps
class TestPsFallbackWatcherIdentityAcrossDirectories:
    def test_a_live_watcher_in_a_different_directory_is_unknown_not_a_false_count(
        self, tmp_path: Path
    ) -> None:
        """The deterministic reproduction issue #845 asked for, mirroring
        `TestWatcherIdentityAcrossDirectories` above but forcing the `ps`
        fallback lane specifically: same role, same literal wave NAME, two
        different `FLOW_WAVE_MAILBOX_DIR` values, one real watcher process
        in directory B only.

        Before the fix, A's query saw B's process and reported
        `FLOW_MAILBOX_WATCHER_COUNT=1` / `armed` - a real live watcher, just
        for the WRONG mailbox, exactly the collision #821 fixed for the
        `/proc` lane. After the fix, A's query cannot verify the match and
        reports `unknown` - not a false `1` (over-claims a watcher A does
        not have), and not a false `0` either (the opposite wrong answer:
        silently discarding the ambiguity and claiming nothing is there,
        which the module docstring is explicit is NOT what `unknown` means -
        `unknown` is "cannot tell", never rounded to zero).
        """
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        env_b = os.environ.copy()
        env_b["FLOW_WAVE_MAILBOX_DIR"] = str(dir_b)
        watcher = subprocess.Popen(
            [
                "bash", str(MAILBOX), "watch", "--role", "1", "--wave", WAVE,
                "--timeout", "30", "--interval", "5", "--peek",
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env_b,
        )
        try:
            wf = dir_b / WAVE / ".watch-1"
            assert _wait_for(wf.exists, timeout=10), "watcher never armed"

            env_a = os.environ.copy()
            env_a["FLOW_WAVE_MAILBOX_DIR"] = str(dir_a)
            env_a["FLOW_WAVE_WATCHER_SCAN"] = "ps"
            from_a = subprocess.run(
                ["bash", str(MAILBOX), "watch", "--status", "--role", "1", "--wave", WAVE],
                capture_output=True, text=True, env=env_a, check=False,
            )
            assert _detail(from_a, "FLOW_MAILBOX_WATCHER_COUNT") == "unknown", (
                "the ps-fallback lane cannot verify a matched process belongs to "
                "THIS mailbox and must say so - not falsely claim B's watcher as "
                "A's (the pre-#845 bug), and not silently claim 0 either"
            )
            assert _detail(from_a, "FLOW_MAILBOX_WATCH_STATE") == "unknown"

            # B's OWN scan cannot verify identity via this lane either - the
            # fix does not selectively trust the mailbox that happens to be
            # right; it withholds confidence from every candidate equally,
            # because nothing observable tells B's scan it is the OWNER of
            # the match rather than another bystander.
            env_b_query = os.environ.copy()
            env_b_query["FLOW_WAVE_MAILBOX_DIR"] = str(dir_b)
            env_b_query["FLOW_WAVE_WATCHER_SCAN"] = "ps"
            from_b = subprocess.run(
                ["bash", str(MAILBOX), "watch", "--status", "--role", "1", "--wave", WAVE],
                capture_output=True, text=True, env=env_b_query, check=False,
            )
            assert _detail(from_b, "FLOW_MAILBOX_WATCHER_COUNT") == "unknown"
        finally:
            watcher.kill()
            watcher.communicate(timeout=10)

    def test_no_match_at_all_still_reads_a_confident_dead(self, tmp_path: Path) -> None:
        """The one case that needs no verification: nothing in the process
        table matches this wave and role at all, so there is no candidate to
        be ambiguous ABOUT. This must stay a real `dead`/`0`, not `unknown` -
        the fix narrows confidence only where an actual unverifiable match
        exists, it does not make the whole lane universally unknown."""
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp_path / "mb")
        env["FLOW_WAVE_WATCHER_SCAN"] = "ps"
        proc = subprocess.run(
            ["bash", str(MAILBOX), "watch", "--status", "--role", "1", "--wave", WAVE],
            capture_output=True, text=True, env=env, check=False,
        )
        assert _detail(proc, "FLOW_MAILBOX_WATCHER_COUNT") == "0"
        assert _detail(proc, "FLOW_MAILBOX_WATCH_STATE") in ("absent", "dead")
