"""The wave namespace is per pytest invocation, and stays that way (#881, #882).

`tests/test_flow_wave_mailbox.py` and `tests/test_flow_wave_lexicon.py` both
hardcoded `WAVE = "testwave"`. The mailbox helper's `ps` fallback lane filters a
WHOLE-HOST process scan by the `--wave` value in each candidate's argv, so a
watcher from another worktree's concurrent run matched the filter and was
indistinguishable from the one under test - turning "no watcher for THIS
mailbox" into "a match I cannot verify", which the lane correctly reports as
`unknown` against assertions expecting a confident `dead`.

Two of these pin the PROPERTY (a namespace that differs between processes) and
one pins the SHAPE (nobody types the literal again). The second literal is how
this became two issues instead of one, so the guard is the point.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from tests.wave_namespace import RUN_ID, unique_wave

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent

#: A module-level `WAVE = "something"` - the exact shape that caused this.
HARDCODED = re.compile(r"^WAVE\s*=\s*['\"]", re.M)


def test_the_name_is_a_valid_wave_name() -> None:
    """It becomes a path component, and the helper validates it rather than
    quoting it: letters, digits, `_`, `.`, `-`, and no leading dot
    (`flow-wave-mailbox.sh`, `valid_name`). A namespace that is unique and
    refused is not an improvement."""
    name = unique_wave()
    assert re.fullmatch(r"[A-Za-z0-9_.-]+", name), name
    assert not name.startswith("."), name


def test_two_processes_get_different_namespaces() -> None:
    """The property that actually matters, checked ACROSS processes.

    Asserting within one process would only prove the string is not a constant.
    The collision this prevents is between two pytest invocations, so the test
    has to cross that boundary too - a fresh interpreter, imported the same way.
    """
    code = "from tests.wave_namespace import unique_wave; print(unique_wave())"
    seen = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=ROOT, check=True,
        ).stdout.strip()
        for _ in range(3)
    }
    assert len(seen) == 3, f"namespaces repeated across processes: {seen}"
    assert RUN_ID not in seen, "a child process reused THIS process's run id"


def test_no_mailbox_test_file_hardcodes_a_wave_name() -> None:
    """The literal has one home. A second copy is what made this two issues.

    Scoped to files that DRIVE `flow-wave-mailbox.sh`, because that is the exact
    population the claim is about: its `ps` fallback scans the whole host process
    table and filters candidates by the `--wave` string in their argv, so a name
    shared between checkouts is invisible to the only filter that lane has.

    `tests/test_flow_wave_residuals.py` holds `WAVE = "test-wave"` and is
    deliberately NOT an offender - it drives `flow-wave-residuals.py`, spawns no
    watcher, and uses the name only as a ledger key under `tmp_path`. Converting
    it would imply a defect it does not have, and a guard that flags files at no
    risk is one somebody eventually widens or deletes. If the scope is ever
    loosened, loosen it to a property (drives the mailbox helper) rather than to
    every file with a `WAVE`.
    """
    at_risk = [
        p for p in sorted(TESTS_DIR.glob("test_*.py"))
        if "flow-wave-mailbox" in p.read_text() and p.name != Path(__file__).name
    ]
    assert at_risk, "no file drives flow-wave-mailbox.sh - this probe has stopped probing"
    offenders = [
        p.relative_to(ROOT) for p in at_risk if HARDCODED.search(p.read_text())
    ]
    assert not offenders, (
        f"{offenders} assign a literal module-level WAVE - use "
        "`tests.wave_namespace.unique_wave()`, or a concurrent run in another "
        "worktree will match this one's watchers through the ps fallback lane"
    )
