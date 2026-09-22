"""Tests for scripts/check-consolidation-ledger.py - the codex-consolidation gate.

The gate has TWO axes and they answer different questions:

- BASELINE: is every obligation that existed at the frozen 2026-09-19 snapshot
  accounted for in the ledger? This is the historical completeness argument and
  the snapshot is deliberately never refreshed - refreshing it would destroy the
  very thing it is evidence of.
- LIVE (issue #1180 sibling, added under #1075): does an obligation exist that
  the ledger has never seen? The baseline axis is structurally incapable of
  answering this, because an issue opened after the capture is not absent from
  the ANSWER - it is absent from the QUESTION.

The load-bearing test here is
``test_the_success_line_names_members_because_equal_totals_hide_the_gap``. When
this axis was written the two populations were baseline=41 and live=41, and the
sets differed in BOTH directions (cxpp#290 had arrived, cxpp#239 had left). A
check comparing totals would have reported clean forever.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-consolidation-ledger.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_consolidation_ledger", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load()


# --------------------------------------------------------------------------- #
# The committed fixture pair. These are the negative control, and they exist so
# the axis keeps being tested after cxpp#290 - today's live specimen - is
# resolved. A control whose only known-bad input is a live GitHub issue stops
# being a control the moment somebody closes it.
# --------------------------------------------------------------------------- #
LEDGER_FIXTURE = """# Fixture ledger

| Entry | Status | Owner | Destination | Disposition |
|---|---|---|---|---|
| cxpp#101 - a rowed obligation | open | unassigned | retired | `owner-approved-retirement` - Q1 |
| cxpp#102 - another rowed obligation | open | unassigned | cpp#1 | `already-covered` - parity examined |
"""

SNAPSHOT_FIXTURE = """# Fixture baseline, captured at some frozen moment.
101
102
"""


def _tree(tmp_path: Path, live: list[int] | None) -> tuple[Path, Path, Path | None]:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(LEDGER_FIXTURE, encoding="utf-8")
    snapshot = tmp_path / "baseline-open.txt"
    snapshot.write_text(SNAPSHOT_FIXTURE, encoding="utf-8")
    live_file = None
    if live is not None:
        live_file = tmp_path / "live-open.txt"
        live_file.write_text("".join(f"{n}\n" for n in live), encoding="utf-8")
    return ledger, snapshot, live_file


def _run(ledger: Path, snapshot: Path, live_file: Path | None, extra: list[str] | None = None) -> int:
    argv = ["--ledger", str(ledger), "--snapshot", str(snapshot)]
    if live_file is not None:
        argv += ["--live-open", str(live_file)]
    return checker.main(argv + (extra or []))


def test_a_live_obligation_with_no_row_is_a_failure(tmp_path: Path, capsys) -> None:
    """THE GAP DIRECTION. This is what the frozen axis cannot see.

    cxpp#103 is open now and has no row. The baseline snapshot does not contain
    it, so the baseline axis is clean and would report `ok` - which is exactly
    how a real obligation (cxpp#290) went unnoticed.
    """
    ledger, snapshot, live = _tree(tmp_path, live=[101, 102, 103])
    assert _run(ledger, snapshot, live) == 1
    out = capsys.readouterr().out
    assert "LEDGER_UNSEEN: cxpp#103" in out, out
    assert "live-without-a-row cxpp#103" in out, out


def test_every_live_obligation_rowed_is_a_pass(tmp_path: Path, capsys) -> None:
    """THE POSITIVE CONTROL, and without it the test above is worthless.

    A gate that returned 1 unconditionally would satisfy the gap test perfectly
    while destroying the instrument. This is the input that must still pass.
    """
    ledger, snapshot, live = _tree(tmp_path, live=[101, 102])
    assert _run(ledger, snapshot, live) == 0
    out = capsys.readouterr().out
    assert "ok on BOTH axes" in out, out
    assert "LEDGER_UNSEEN" not in out, out


def test_the_success_line_names_members_because_equal_totals_hide_the_gap(
    tmp_path: Path, capsys
) -> None:
    """EQUAL TOTALS, DIFFERENT SETS - the real 41-vs-41 shape.

    Baseline is {101, 102}; live is {102, 103}. Both have two members, so every
    count agrees while one obligation has arrived unrowed and another has been
    resolved. A gate comparing totals reports clean here. The gate must name
    MEMBERS, and must say which direction is the gap.
    """
    ledger, snapshot, live = _tree(tmp_path, live=[102, 103])
    assert len({101, 102}) == len({102, 103}), "the fixture must hold totals equal"
    assert _run(ledger, snapshot, live) == 1
    out = capsys.readouterr().out
    assert "cxpp#103" in out, "the arriving obligation must be NAMED, not counted"
    assert "live-without-a-row" in out, "the gap direction must be named as the gap"


def test_resolved_entries_are_reported_as_ordinary_not_as_a_gap(
    tmp_path: Path, capsys
) -> None:
    """The other direction is NOT a defect and must not read as one.

    A baseline entry that is no longer live has been resolved. Reporting it as a
    failure would make the gate red for doing the work it exists to track.
    """
    ledger, snapshot, live = _tree(tmp_path, live=[102])
    assert _run(ledger, snapshot, live) == 0
    out = capsys.readouterr().out
    assert "cxpp#101" in out, "the resolved member must still be NAMED"
    assert "NOT a gap" in out, out


def test_the_default_run_says_the_live_axis_was_not_examined(
    tmp_path: Path, capsys
) -> None:
    """A success line must not claim more than its population supports.

    With no live input the gate checks one axis. It must say so, or a reader
    takes `ok` for an answer about obligations it never considered.
    """
    ledger, snapshot, _ = _tree(tmp_path, live=None)
    assert _run(ledger, snapshot, None) == 0
    out = capsys.readouterr().out
    assert "BASELINE axis only" in out, out
    assert "LIVE AXIS WAS NOT EXAMINED" in out, out


def test_live_requested_but_unobtainable_is_unknown_never_clean(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """UNKNOWN, NEVER CLEAN - the whole reason this axis is evidence.

    If the live axis is asked for and cannot run, the gate must not report the
    strongest clean result at the exact moment it went blind. It must also not
    conflate `None` (could not look) with `set()` (nothing is open), which would
    turn a blind run into a confident finding.
    """
    ledger, snapshot, _ = _tree(tmp_path, live=None)
    monkeypatch.setattr(checker, "fetch_live_open", lambda: None)
    assert _run(ledger, snapshot, None, ["--live-from-github"]) == 2
    err = capsys.readouterr().err
    assert "UNKNOWN" in err, err
    assert "says NOTHING about obligations" in err, err


def test_a_missing_baseline_row_still_fails(tmp_path: Path, capsys) -> None:
    """The original axis is unchanged; the new one must not have replaced it."""
    ledger, snapshot, _ = _tree(tmp_path, live=None)
    snapshot.write_text(SNAPSHOT_FIXTURE + "199\n", encoding="utf-8")
    assert _run(ledger, snapshot, None) == 1
    out = capsys.readouterr().out
    assert "LEDGER_MISSING: cxpp#199" in out, out
