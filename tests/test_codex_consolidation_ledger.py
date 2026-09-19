"""The consolidation ledger accounts for every open CxPP obligation (issue #1068).

Two things are under test and they are NOT the same thing:

1. the GATE can tell an accounted obligation from an unaccounted one, and
2. the real ledger currently passes it.

(2) alone would be satisfied by a gate that cannot fail - which is the state the
first cut of this gate was actually in, and `controls/ledger-completeness`'s
known-bad fixture is what found it. These tests drive the same fixtures from
pytest so the discrimination is checked on every run and not only when the
negative-control battery is invoked.

WHAT THESE TESTS DO NOT CLAIM. Nothing here judges whether a DISPOSITION is
right. `owner-approved-retirement` with no cited owner ruling is a defect no
assertion below can see, and the spec leaves that to review. These tests answer
"is there a row", which is the gate's question too.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-consolidation-ledger.py"
CONTROL = ROOT / "controls" / "ledger-completeness"
ANCHOR = CONTROL / "anchors" / "constructed-whole-file-scan.py"
SPEC_DIR = ROOT / ".specify" / "specs" / "codex-consolidation"


def run(script: Path, ledger: Path, snapshot: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--ledger", str(ledger), "--snapshot", str(snapshot)],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )


def case(name: str) -> tuple[Path, Path]:
    d = CONTROL / "cases" / name
    return d / "ledger.md", d / "baseline-open.txt"


# --------------------------------------------------------------------------
# The gate can fail. This is the load-bearing half.
# --------------------------------------------------------------------------

def test_the_gate_reports_an_entry_with_no_row():
    """A snapshot entry absent from the ledger's table is a finding.

    If this ever passes GREEN the gate has stopped answering its only question,
    and #1076 would read a ledger that silently omits obligations as complete.
    """
    res = run(GATE, *case("bad-missing-issue"))
    assert res.returncode == 1, f"expected a finding, got exit {res.returncode}: {res.stdout}"
    assert "LEDGER_MISSING: cxpp#227" in res.stdout


def test_the_gate_passes_a_complete_ledger_that_also_cites_extra_numbers():
    """THE HALF THAT MATTERS.

    The good fixture cites `cxpp#287`, which is not in its snapshot - a PR that
    merged before the baseline, exactly as the real ledger does. A gate that
    flagged the extra citation would be red on every correct ledger, be
    overridden within a week, and take the omission check down with it.
    """
    res = run(GATE, *case("good-complete"))
    assert res.returncode == 0, res.stdout + res.stderr
    assert "LEDGER_MISSING" not in res.stdout


def test_prose_naming_an_entry_is_not_an_account_of_it():
    """The defect the negative control caught, pinned so it cannot return.

    The bad fixture's prose contains the literal token `cxpp#227` in a sentence
    explaining that it has no row. Under a whole-file text scan that sentence
    SATISFIES the requirement it describes the violation of. Better prose makes
    such a scan more likely to pass, not less.
    """
    ledger, _ = case("bad-missing-issue")
    assert "cxpp#227" in ledger.read_text(encoding="utf-8"), (
        "fixture no longer contains the token in prose, so this test would pass "
        "for the wrong reason - it would no longer distinguish the two rules"
    )
    assert run(GATE, *case("bad-missing-issue")).returncode == 1


def test_a_row_that_records_nothing_is_not_an_account():
    """Review finding R3: presence is not accounting.

    `| cxpp#227 | |` lists the number and says nothing about what happens to it.
    Under the presence-only rule the gate shipped with, that row PASSED - the
    shape of completeness with none of the content.
    """
    res = run(GATE, *case("bad-row-without-disposition"))
    assert res.returncode == 1, f"expected a finding, got exit {res.returncode}: {res.stdout}"
    assert "cxpp#227" in res.stdout and "no disposition" in res.stdout


def test_the_disposition_vocabulary_is_closed_and_not_read_from_the_ledger():
    """The permitted values live in the gate, not in the document under test.

    Parsing them out of the ledger would let any ledger legitimise a new word by
    adding it to its own table - the same closed loop the snapshot's provenance
    header exists to prevent.
    """
    src = GATE.read_text(encoding="utf-8")
    assert "DISPOSITIONS = (" in src
    for word in ("already-covered", "move", "adapt", "transfer",
                 "owner-approved-retirement", "unresolved"):
        assert f'"{word}"' in src, f"{word} is not in the gate's closed vocabulary"


def test_the_anchor_is_blind_so_the_control_discriminates():
    """The vendored predecessor MISSES the bad input and AGREES on the good one.

    An anchor that caught the bad input would mean the control cannot notice the
    gate regressing to it - the control would be decorative.
    """
    for bad in ("bad-missing-issue", "bad-row-without-disposition"):
        assert run(ANCHOR, *case(bad)).returncode == 0, (
            f"the anchor CAUGHT {bad}; it is no longer a blind predecessor and "
            "cannot demonstrate what the current rule adds"
        )
    assert run(ANCHOR, *case("good-complete")).returncode == 0


# --------------------------------------------------------------------------
# An unreadable input is UNKNOWN, never clean.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("missing", ["ledger", "snapshot"])
def test_an_absent_input_does_not_report_clean(tmp_path, missing):
    ledger, snapshot = case("good-complete")
    args = {"ledger": ledger, "snapshot": snapshot}
    args[missing] = tmp_path / "absent.txt"
    res = run(GATE, args["ledger"], args["snapshot"])
    assert res.returncode == 2, (
        f"a missing {missing} exited {res.returncode}; a deleted ledger must not "
        "be indistinguishable from a complete one"
    )


def test_an_empty_snapshot_does_not_pass_vacuously(tmp_path):
    """Zero required entries is an unusable population, not a clean bill."""
    snapshot = tmp_path / "empty.txt"
    snapshot.write_text("# only comments\n", encoding="utf-8")
    ledger, _ = case("good-complete")
    assert run(GATE, ledger, snapshot).returncode == 2


# --------------------------------------------------------------------------
# The real ledger, and the artifacts the spec promises.
# --------------------------------------------------------------------------

def test_the_real_ledger_accounts_for_every_open_entry():
    res = subprocess.run(
        [sys.executable, str(GATE), "--root", str(ROOT)],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_the_snapshot_is_not_derived_from_the_ledger():
    """The provenance header names the `gh` commands, not the ledger.

    A snapshot built by scanning the ledger would compare it against itself and
    could never be red. This asserts the header still records the independent
    capture, so a later maintainer cannot close that loop unnoticed.
    """
    header = (SPEC_DIR / "baseline-open.txt").read_text(encoding="utf-8")
    assert "gh issue list --repo cooneycw/codex-power-pack" in header
    assert "gh pr list" in header
    assert "NEVER derived from the ledger" in header


@pytest.mark.parametrize("name", ["spec.md", "inventory.md", "ledger.md", "plan.md", "review.md"])
def test_the_spec_set_is_present(name):
    assert (SPEC_DIR / name).is_file(), f"{name} is named by issue #1068's acceptance"


def test_the_gate_is_in_the_instrument_census():
    """ADR 0008's bound applies: the verdict is consumed without re-derivation."""
    adr = (ROOT / "docs" / "decisions" / "0008-instrument-negative-control-bound.md").read_text(
        encoding="utf-8"
    )
    assert "`check-consolidation-ledger.py`" in adr
