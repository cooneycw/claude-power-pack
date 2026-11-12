"""One wake of `watch` delivers EVERY unread message (issue #1691).

Three documents used to state that the watch "delivers one message and exits":
the mailbox script's own header, `/flow:wave` and `/flow:register`. The code
never did that. `scripts/flow-wave-mailbox.sh watch` blocks until the role has
unacknowledged mail, then prints every unacknowledged message in every box the
role reads, acknowledges each of them when armed with `--consume`, and exits.
It is one-shot per WAKE, not per message, which is why the session must re-arm
after each wake and need not re-arm once per message.

This pins what the code does, so the corrected sentence cannot drift back:

- three messages unread at the poll are ONE wake carrying all three bodies;
- `--consume` acknowledges all three, so a following `read --peek` is empty and
  a second watch times out;
- `--peek` prints the same three and acknowledges none of them;
- the contrast: with one message unread, one wake prints one.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.wave_namespace import unique_wave

ROOT = Path(__file__).resolve().parents[1]
MAILBOX = ROOT / "scripts" / "flow-wave-mailbox.sh"

# Drives the real script under `bash`, and an arming watch serializes on
# `flock`; the CI validate container may ship neither, so skip there.
requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("flock") is None,
    reason="requires bash and flock on PATH",
)

WAVE = unique_wave()
ROLE = "w1"
MARKER = "<!-- cc-flow-wave-msg "
BODIES = (
    "first: the assignment for alpha",
    "second: the ruling on bravo",
    "third: the note about charlie",
)


def _run(tmp: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp / "mb")
    return subprocess.run(
        ["bash", str(MAILBOX), *args],
        capture_output=True,
        text=True,
        env=env,
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


def _send(tmp: Path, bodies: tuple[str, ...]) -> None:
    """Deliver `bodies` to ROLE's box, and prove they are all unread.

    The precondition is asserted here, before any watch runs: a wake that
    printed three messages proves nothing if only one was ever unread.
    """
    for body in bodies:
        sent = _run(tmp, "send", "--to", ROLE, "--wave", WAVE, "--body", body)
        assert _verdict(sent) == "sent", sent.stderr
    peeked = _run(tmp, "read", "--role", ROLE, "--wave", WAVE, "--peek")
    assert _verdict(peeked) == "read", peeked.stdout + peeked.stderr
    assert _detail(peeked, "FLOW_MAILBOX_UNREAD") == str(len(bodies)), peeked.stdout


def _watch(tmp: Path, mode: str) -> subprocess.CompletedProcess[str]:
    # `--timeout 0` is "check once and report": the mail is already waiting,
    # so the watch fires on its first poll and nothing here sleeps.
    return _run(
        tmp, "watch", "--role", ROLE, "--wave", WAVE, mode, "--timeout", "0"
    )


@requires_bash
def test_one_consuming_wake_prints_and_acknowledges_all_three(tmp_path: Path) -> None:
    _send(tmp_path, BODIES)

    woke = _watch(tmp_path, "--consume")

    assert woke.returncode == 0, woke.stderr
    assert _verdict(woke) == "mail"
    assert _detail(woke, "FLOW_MAILBOX_UNREAD") == "3"
    assert woke.stdout.count(MARKER) == 3, woke.stdout
    for body in BODIES:
        assert body in woke.stdout, f"{body!r} was not delivered by the one wake"

    # All three were acknowledged by that one wake: nothing is left unread...
    after = _run(tmp_path, "read", "--role", ROLE, "--wave", WAVE, "--peek")
    assert _verdict(after) == "empty", after.stdout
    assert _detail(after, "FLOW_MAILBOX_UNREAD") == "0"
    for body in BODIES:
        assert body not in after.stdout

    # ...and a second watch has nothing to wake on.
    again = _watch(tmp_path, "--consume")
    assert again.returncode == 5, again.stdout + again.stderr
    assert _verdict(again) == "timeout"
    assert again.stdout.count(MARKER) == 0


@requires_bash
def test_one_peeking_wake_prints_all_three_and_acknowledges_none(tmp_path: Path) -> None:
    _send(tmp_path, BODIES)

    woke = _watch(tmp_path, "--peek")

    assert woke.returncode == 0, woke.stderr
    assert _verdict(woke) == "mail"
    assert woke.stdout.count(MARKER) == 3, woke.stdout
    for body in BODIES:
        assert body in woke.stdout

    after = _run(tmp_path, "read", "--role", ROLE, "--wave", WAVE, "--peek")
    assert _verdict(after) == "read", after.stdout
    assert _detail(after, "FLOW_MAILBOX_UNREAD") == "3"


@requires_bash
def test_with_one_message_unread_one_wake_prints_one(tmp_path: Path) -> None:
    """The contrast: the wake carries what is unread, no more and no fewer."""
    _send(tmp_path, BODIES[:1])

    woke = _watch(tmp_path, "--consume")

    assert woke.returncode == 0, woke.stderr
    assert _verdict(woke) == "mail"
    assert _detail(woke, "FLOW_MAILBOX_UNREAD") == "1"
    assert woke.stdout.count(MARKER) == 1, woke.stdout
    assert BODIES[0] in woke.stdout
    assert BODIES[1] not in woke.stdout
    assert BODIES[2] not in woke.stdout


@requires_bash
def test_a_message_sent_after_a_wake_is_the_next_wake(tmp_path: Path) -> None:
    """Why the session re-arms after EACH wake: later mail needs a new watch."""
    _send(tmp_path, BODIES[:2])
    first = _watch(tmp_path, "--consume")
    assert first.stdout.count(MARKER) == 2, first.stdout

    late = _run(tmp_path, "send", "--to", ROLE, "--wave", WAVE, "--body", BODIES[2])
    assert _verdict(late) == "sent", late.stderr

    second = _watch(tmp_path, "--consume")
    assert second.returncode == 0, second.stderr
    assert second.stdout.count(MARKER) == 1, second.stdout
    assert BODIES[2] in second.stdout
    assert BODIES[0] not in second.stdout
