"""Controls for `scripts/checkout-readers.sh` (issue #1029, specimen 2).

The nit store ran both halves against the corrected detector before it was ever
relied on - POSITIVE: pid 21206, known stale, FOUND; NEGATIVE: pid 3452895, a
live daemon on a current inode, correctly not flagged. #1029 asks for both to be
committed, and this is that. They are reproduced two ways on purpose:

  REAL PROCESSES     a bash process holding an fd on a file that is then
                     unlinked really does show `... (deleted)` in /proc, and
                     that is the specimen. Nothing but a real process proves the
                     detector reads real /proc correctly.
  FIXTURE /proc      classification, counting and the unreadable-entry bound are
                     exercised against a constructed tree through
                     CPP_CHECKOUT_READERS_PROC, because a same-user process with
                     an unreadable /proc/<pid>/fd cannot be created on demand.

The negative half is the one that matters most: a detector that flagged every
supervisor would be useless in exactly the same way as one that flagged none,
and only the second control separates them.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "checkout-readers.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)

requires_proc = pytest.mark.skipif(
    not Path("/proc/self/fd").is_dir(),
    reason="requires a Linux-style /proc",
)

#: Holds an fd on its own path and waits, so unlinking the file leaves a process
#: executing an inode with no name - the #1029 specimen, reproduced on demand.
VICTIM = """#!/usr/bin/env bash
exec 255< "$1"
touch "$2"
sleep 30
"""


def _run(tree: Path, *args: str, proc: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if proc is not None:
        env["CPP_CHECKOUT_READERS_PROC"] = str(proc)
    return subprocess.run(
        ["bash", str(SCRIPT), "--path", str(tree), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _json(tree: Path, proc: Path | None = None) -> dict:
    result = _run(tree, "--json", proc=proc)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --------------------------------------------------------------------------
# Real processes: the specimen itself.
# --------------------------------------------------------------------------


@pytest.fixture
def held_tree(tmp_path: Path):
    """A tree with a running process holding an fd on a file inside it."""
    tree = tmp_path / "checkout"
    tree.mkdir()
    victim = tree / "victim.sh"
    victim.write_text(VICTIM, encoding="utf-8")
    ready = tmp_path / "ready"

    proc = subprocess.Popen(
        ["bash", str(victim), str(victim), str(ready)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while not ready.exists() and time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail("the victim process exited before opening its fd")
        time.sleep(0.02)
    assert ready.exists(), "the victim process never signalled readiness"

    try:
        yield tree, victim, proc
    finally:
        proc.send_signal(signal.SIGKILL)
        proc.wait(timeout=10)


@requires_proc
def test_negative_control_a_reader_on_a_current_inode_is_not_flagged_stale(
    held_tree: tuple[Path, Path, subprocess.Popen],
) -> None:
    """A live daemon on a current inode must be `live`, never `stale`.

    Without this half, a detector that flagged every reader would look exactly
    as healthy as one that discriminates.
    """
    tree, _victim, proc = held_tree
    payload = _json(tree)
    assert payload["stale"] == 0, "nothing has been unlinked yet"
    assert payload["live"] >= 1
    assert payload["verdict"] == "busy"

    report = _run(tree).stdout
    assert f"pid {proc.pid}" in report
    assert "CHECKOUT_READERS: busy" in report


@requires_proc
def test_positive_control_a_reader_on_a_deleted_inode_is_found_with_its_pid(
    held_tree: tuple[Path, Path, subprocess.Popen],
) -> None:
    """The specimen: git unlinks and creates, and the running reader never moves.

    The pid is asserted explicitly because the detector's FIRST form proved a
    stale reader existed and could not say which one - and the only remedy a hit
    calls for is "re-arm that supervisor", which needs a pid.
    """
    tree, victim, proc = held_tree
    victim.unlink()

    payload = _json(tree)
    assert payload["stale"] == 1
    assert payload["verdict"] == "stale"

    report = _run(tree).stdout
    assert f"pid {proc.pid}" in report, "a hit without its pid cannot be acted on"
    assert "CHECKOUT_READERS: stale" in report
    assert "re-arm" in report.lower()


@requires_proc
def test_an_unrelated_tree_is_clear(held_tree: tuple[Path, Path, subprocess.Popen], tmp_path: Path) -> None:
    """The detector must not fire on a tree nobody holds (#1029 ownership)."""
    _tree, _victim, _proc = held_tree
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    payload = _json(elsewhere)
    assert payload["stale"] == 0
    assert payload["live"] == 0
    assert payload["verdict"] in {"clear", "unknown"}


# --------------------------------------------------------------------------
# Fixture /proc: classification, counting, and the unreadable bound.
# --------------------------------------------------------------------------


def _can_read(directory: Path) -> bool:
    """Measured, not inferred: try to list it and see what happens."""
    try:
        list(directory.iterdir())
    except PermissionError:
        return False
    return True


def _fake_proc(
    root: Path,
    tree: Path,
    *,
    stale_pids: tuple[int, ...] = (),
    live_pids: tuple[int, ...] = (),
    cwd_pids: tuple[int, ...] = (),
    unreadable_pids: tuple[int, ...] = (),
    outside_pids: tuple[int, ...] = (),
) -> Path:
    """Build a /proc-shaped tree. Symlink targets need not resolve."""
    proc = root / "proc"
    proc.mkdir()

    def _entry(pid: int) -> Path:
        d = proc / str(pid)
        (d / "fd").mkdir(parents=True)
        (d / "cmdline").write_bytes(f"bash\0script-{pid}.sh\0".encode())
        (d / "comm").write_text(f"proc{pid}\n", encoding="utf-8")
        # `_ (_) S <ppid> ...` - field 4 is the ppid the ancestor walk reads.
        (d / "stat").write_text(f"{pid} (proc) S 1 0 0\n", encoding="utf-8")
        return d

    for pid in stale_pids:
        d = _entry(pid)
        (d / "fd" / "255").symlink_to(f"{tree}/held-{pid}.sh (deleted)")
    for pid in live_pids:
        d = _entry(pid)
        (d / "fd" / "255").symlink_to(f"{tree}/held-{pid}.sh")
    for pid in cwd_pids:
        d = _entry(pid)
        (d / "cwd").symlink_to(str(tree))
    for pid in outside_pids:
        d = _entry(pid)
        (d / "fd" / "255").symlink_to(f"{root}/elsewhere/held-{pid}.sh")
    for pid in unreadable_pids:
        d = _entry(pid)
        (d / "fd" / "9").symlink_to(f"{tree}/held-{pid}.sh (deleted)")
        (d / "fd").chmod(0o000)
        # ASSERT THE DENIAL YOU BUILT. `chmod 000` does not stop root, and CI
        # images here run as root - where the scanner would happily read the
        # directory, find the stale descriptor, and fail these tests for a
        # reason that has nothing to do with the behaviour under test. Skip
        # rather than pretend, and skip on the MEASURED denial rather than on a
        # uid check, so the reason is the actual capability and not a proxy for
        # it (counter-model review, codex/gpt-6-astra).
        if _can_read(d / "fd"):
            pytest.skip(
                "this fixture needs an unreadable directory; the current identity "
                "can read one it has chmod 000'd (running as root?)"
            )
    return proc


@pytest.fixture
def fixture_proc_tree(tmp_path: Path):
    tree = tmp_path / "checkout"
    tree.mkdir()
    yield tmp_path, tree
    # Restore permissions or pytest's own tmp cleanup cannot recurse.
    for fd_dir in (tmp_path / "proc").rglob("fd"):
        try:
            fd_dir.chmod(0o755)
        except OSError:  # pragma: no cover - already readable
            pass


def test_fixture_stale_beats_live_in_the_verdict(fixture_proc_tree) -> None:
    root, tree = fixture_proc_tree
    proc = _fake_proc(root, tree, stale_pids=(900001,), live_pids=(900002,))
    payload = _json(tree, proc=proc)
    assert payload["stale"] == 1
    assert payload["live"] == 1
    assert payload["verdict"] == "stale", "a stale reader outranks a busy tree"


def test_fixture_cwd_inside_the_tree_counts_as_a_live_reader(
    fixture_proc_tree,
) -> None:
    """A gate running `make` in the tree holds it even with no fd on a file."""
    root, tree = fixture_proc_tree
    proc = _fake_proc(root, tree, cwd_pids=(900003,))
    payload = _json(tree, proc=proc)
    assert payload["live"] == 1
    assert payload["verdict"] == "busy"


def test_fixture_a_reader_of_another_tree_is_not_ours(fixture_proc_tree) -> None:
    """Ownership boundary: a finding must distinguish our tree from a neighbour's."""
    root, tree = fixture_proc_tree
    proc = _fake_proc(root, tree, outside_pids=(900004,))
    payload = _json(tree, proc=proc)
    assert payload["stale"] == 0
    assert payload["live"] == 0
    assert payload["verdict"] == "clear"


def test_fixture_unreadable_entries_are_counted_not_discarded(
    fixture_proc_tree,
) -> None:
    """Limit 1: `2>/dev/null` swallowing permission errors is absence-as-clean.

    The unreadable entry here holds a DELETED file in the tree, so a scan that
    silently skipped it would report `clear` while a stale reader existed. The
    verdict stays `clear` by design - see the header's rejected `partial` - but
    the bound must be reported, and reported in `--quiet` too, which is the line
    that reaches a session start.
    """
    root, tree = fixture_proc_tree
    proc = _fake_proc(root, tree, unreadable_pids=(900005,))
    payload = _json(tree, proc=proc)
    assert payload["unreadable"] == 1
    assert payload["unreadable_same_user"] == 1
    assert payload["stale"] == 0, "we genuinely could not see it"

    report = _run(tree, proc=proc).stdout
    assert "CHECKOUT_READERS_UNREADABLE: 1 (1 same-user)" in report

    quiet = _run(tree, "--quiet", proc=proc).stdout
    assert "could not be read" in quiet, (
        "a quiet 'clear' that hides uninspected processes is a blind green"
    )


def test_fixture_a_clean_scan_prints_no_unreadable_bound(fixture_proc_tree) -> None:
    """The bound line must be a fact, not boilerplate printed unconditionally."""
    root, tree = fixture_proc_tree
    proc = _fake_proc(root, tree, outside_pids=(900006,))
    assert "CHECKOUT_READERS_UNREADABLE" not in _run(tree, proc=proc).stdout
    assert _run(tree, "--quiet", proc=proc).stdout.strip() == ""


def test_an_absent_process_table_is_unknown_never_clear(tmp_path: Path) -> None:
    """Unscanned reads as unknown. A host that cannot answer must say so."""
    tree = tmp_path / "checkout"
    tree.mkdir()
    payload = _json(tree, proc=tmp_path / "no-such-proc")
    assert payload["verdict"] == "unknown"
    assert payload["reason"]

    report = _run(tree, proc=tmp_path / "no-such-proc").stdout
    assert "CHECKOUT_READERS: unknown" in report
    assert "never as clean" in report


def test_an_empty_process_table_is_unknown_never_clear(tmp_path: Path) -> None:
    """A /proc with no inspectable entries scanned nothing, which is not clean."""
    tree = tmp_path / "checkout"
    tree.mkdir()
    empty = tmp_path / "proc"
    empty.mkdir()
    payload = _json(tree, proc=empty)
    assert payload["scanned"] == 0
    assert payload["verdict"] == "unknown"


def test_a_wholly_unreadable_population_is_unknown_never_clear(
    fixture_proc_tree,
) -> None:
    """Walking processes is not inspecting them (counter-model review).

    `scanned` increments on ENCOUNTER, so a population that is entirely
    unreadable once produced `scanned=N, unreadable=N` and a verdict of `clear` -
    "I looked and found nothing" rendering identically to "I could not look at
    anything", inside the detector written to refuse exactly that. `clear` now
    requires at least one successful inspection.
    """
    root, tree = fixture_proc_tree
    proc = _fake_proc(root, tree, unreadable_pids=(900007, 900008))
    payload = _json(tree, proc=proc)

    assert payload["scanned"] == 2
    assert payload["inspected"] == 0
    assert payload["unreadable"] == 2
    assert payload["verdict"] == "unknown", "no inspection happened, so there is no verdict"
    assert "could be inspected" in payload["reason"]


def test_one_successful_inspection_is_enough_for_a_verdict(fixture_proc_tree) -> None:
    """The negative half: `clear` must stay reachable beside unreadable entries.

    Without this, the fix above could have been "any unreadable entry means
    unknown", which is the permanently-unreachable-verdict trap the header
    records rejecting for `partial`.
    """
    root, tree = fixture_proc_tree
    proc = _fake_proc(root, tree, unreadable_pids=(900009,), outside_pids=(900010,))
    payload = _json(tree, proc=proc)

    assert payload["inspected"] == 1
    assert payload["unreadable"] == 1
    assert payload["verdict"] == "clear"
