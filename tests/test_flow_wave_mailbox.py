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
- ``read`` yields only what is newer than the box's cursor and then advances it;
  ``--all`` re-reads history, ``--peek`` reads without consuming so an armed
  watch still fires.
- ``watch`` is the WAKE, and is the half that makes this a lane rather than the
  ad-hoc 2026-08-11 workaround: it BLOCKS until mail lands, prints it, exits 0.
  A timeout is exit 5 and is explicitly not evidence the counterpart is gone.
- Role and wave names are validated, not merely quoted: they become path
  components, so ``../`` must be refused rather than addressed.

Timing-sensitive assertions use short, bounded waits and assert on OUTPUT
(the delivered body, the verdict line), never on how long a poll took.
"""

from __future__ import annotations

import json
import os
import shutil
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
        _send(tmp_path, "orchestrator", "report from 1", frm="1")
        _send(tmp_path, "orchestrator", "report from 2", frm="2")
        proc = _run(tmp_path, "read", "--role", "orchestrator", "--wave", WAVE)
        assert _verdict(proc) == "read"
        body = _body(proc)
        assert "report from 1" in body
        assert "report from 2" in body

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
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0"
        )
        assert "NOT proof" in proc.stderr
        assert "flow-wave-registry.sh list" in proc.stderr

    def test_watch_returns_mail_already_waiting(self, tmp_path: Path):
        """A watch armed after the send still delivers - the race a worker hits
        when it re-arms between wakes.
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
        )
        assert proc.returncode == 0
        assert _verdict(proc) == "mail"
        assert "sent before the watch was armed" in _body(proc)

    def test_watch_consumes_so_a_re_armed_watch_does_not_re_fire(
        self, tmp_path: Path
    ):
        _send(tmp_path, "1", "handled once")
        first = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "5"
        )
        assert _verdict(first) == "mail"
        second = _run(
            tmp_path, "watch", "--role", "1", "--wave", WAVE, "--timeout", "0"
        )
        assert _verdict(second) == "timeout"

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
        )
        assert _verdict(proc) == "mail"
        assert "pushback from worker 3" in _body(proc)


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
