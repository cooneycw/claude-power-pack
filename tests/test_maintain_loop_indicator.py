"""Tests for scripts/maintain-loop-indicator.py - the #1085 leading indicator.

THE DISCRIMINATION THIS FILE OWNS, and why it is here rather than in the
control: #1085 asks for proof that the extractor reports a KNOWN DELAY on a
fixture containing one, and reports ZERO on a fixture containing none. Both are
valid measurements and both exit 0, and `check-negative-controls.py` decides its
observation from the exit code first, so the harness scores them identically.
Rather than contort a REPORTER into detect/clean semantics - which would have
meant giving a measured delay a non-zero exit, a threshold at zero, a BAND that
#1085 forbids - the control registers the axis the harness CAN express
(observation vs unexaminable) and this file carries the measurement.

It drives the SAME COMMITTED FIXTURES the control runs, through the same entry
point. If the two ever disagree about what those fixtures contain, one of them
is wrong and the pair fails rather than the gap being invisible.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "maintain-loop-indicator.py"
CASES = ROOT / "controls" / "maintain-loop-indicator" / "cases"


def _load():
    spec = importlib.util.spec_from_file_location("maintain_loop_indicator", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


indicator = _load()


def _run(capture: Path, capsys) -> tuple[int, str, str]:
    code = indicator.main(["--input", str(capture)])
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# --------------------------------------------------------------------------- #
# The measurement - #1085's named negative control, both directions
# --------------------------------------------------------------------------- #
def test_a_known_delay_is_reported_as_that_delay(capsys) -> None:
    """The planted delay is 3.00 days and the extractor must say 3.00.

    "Before reporting that the extractor found N findings, prove it can find
    one." A number that is merely PLAUSIBLE proves nothing: the fixture carries
    a delay chosen so that any off-by-one in the date arithmetic, or any
    silently dropped record, changes the printed value.
    """
    code, out, _ = _run(CASES / "good-known-delay" / "capture.json", capsys)
    assert code == 0
    assert "median 3.00d to file" in out, out
    assert "over 1 of 1 finding(s)" in out, out


def test_no_findings_reports_an_empty_population_not_a_delay_of_zero(capsys) -> None:
    """The absence case, and it must not render as a measurement.

    "Then commit one containing none, and show it reports zero rather than
    failing." Reporting `median 0.00d` here would be the exact defect: a
    confident number over a population that contains nothing to measure.
    """
    code, out, _ = _run(CASES / "good-no-findings" / "capture.json", capsys)
    assert code == 0
    assert "population is EMPTY" in out, out
    assert "median" not in out, "an empty population produced a median"
    assert "observed zero, not an unread input" in out, out


# --------------------------------------------------------------------------- #
# Three states: an observed zero, an empty file, an unreadable input
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "case,why",
    [
        ("unknown-empty-file", "a failed `gh ... > capture.json` leaves zero bytes"),
        ("unknown-unparseable", "a truncated write leaves invalid JSON"),
        ("unknown-undeclared-population", "valid JSON that never declares a population"),
    ],
)
def test_an_unexaminable_input_is_unknown_never_zero(case: str, why: str, capsys) -> None:
    """UNKNOWN, never clean and never this instrument's zero.

    #1085: "A broken extractor's zeros look exactly like real ones, and this is
    a measurement whose whole purpose is to be believed later by someone who did
    not watch it run." Each of these three parses differently and each must
    refuse; the third is the nastiest, because it IS valid JSON.
    """
    code, out, err = _run(CASES / case / "capture.json", capsys)
    assert code == indicator.UNKNOWN_EXIT, f"{case}: {why}"
    assert "UNKNOWN" in err, err
    assert "says NOTHING about whether findings are reaching the backlog" in err
    assert out == "", f"{case} printed a measurement on stdout: {out!r}"


def test_an_observed_zero_and_an_empty_file_are_different_verdicts(capsys) -> None:
    """The pair, not the members - the distinction is the whole point.

    Tested together because either alone passes on an instrument that treats
    both the same way. One is a population that was looked at and found empty;
    the other is a look that never happened.
    """
    observed, _, _ = _run(CASES / "good-no-findings" / "capture.json", capsys)
    unread, _, _ = _run(CASES / "unknown-empty-file" / "capture.json", capsys)
    assert observed == 0 and unread == indicator.UNKNOWN_EXIT, (
        "an observed empty population and an unread input produced the same verdict"
    )


# --------------------------------------------------------------------------- #
# The partition, which IS the metric
# --------------------------------------------------------------------------- #
def test_undetermined_is_never_folded_into_the_denominator(tmp_path: Path, capsys) -> None:
    """The median is over the ATTRIBUTABLE subset and the line must say so.

    One finding is filed after 2 days; three are unlinkable. A median over 4
    would be a different number, and a median over 1 presented without its
    denominator would claim the repository files everything in 2 days.
    """
    doc = {
        "captured_at": "2026-09-20T00:00:00Z",
        "comments": [
            {"id": "1", "created_at": "2026-09-10T00:00:00Z", "body": "filed one"},
            {"id": "2", "created_at": "2026-09-10T00:00:00Z", "body": "no linkage"},
            {"id": "3", "created_at": "2026-09-10T00:00:00Z", "body": "no linkage"},
        ],
        "issues": [
            {"number": 7, "created_at": "2026-09-12T00:00:00Z",
             "body": "from issuecomment-1"},
        ],
        "friction": [{"ts": "2026-09-10T00:00:00Z", "signal": "no linkage field"}],
    }
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    code, out, _ = _run(path, capsys)
    assert code == 0
    assert "median 2.00d to file, over 1 of 4 finding(s)" in out, out
    assert "3 UNDETERMINED" in out, out


def test_a_friction_record_is_in_the_population_and_undetermined(tmp_path: Path, capsys) -> None:
    """In the denominator, never attributable - and never quietly dropped.

    The ledger carries no filing linkage (measured across every record: ts, run,
    step, class, signal, fix, scope, outcome, risk, harness). Leaving it OUT of
    the population would shrink the denominator and make the attributable share
    look better than the repository's record-keeping supports.
    """
    doc = {"captured_at": "2026-09-20T00:00:00Z", "comments": [], "issues": [],
           "friction": [{"ts": "2026-09-10T00:00:00Z", "signal": "x"},
                        {"ts": "2026-09-11T00:00:00Z", "signal": "y"}]}
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    code, out, _ = _run(path, capsys)
    assert code == 0
    assert "population of 2" in out, out
    assert "2 UNDETERMINED" in out, out
    assert "undetermined by construction" in out, out


def test_an_inverted_pair_is_named_not_folded_and_not_undetermined(
    tmp_path: Path, capsys
) -> None:
    """A citing issue that PREDATES its comment is not a fast filing.

    It is a reference to existing work, so the pair is not a filing event at
    all. Folding it into the median biases the number with a value that is not
    a delay; dropping it silently hides that the attribution rule matched
    backwards. It gets its own named count.

    Measured on the real capture: exactly one such pair, at MINUS NINE SECONDS -
    the ordinary "file the issue, then record the nit" order. That is why this
    is a category and not a refusal: refusing would red on an everyday workflow.
    """
    doc = {
        "captured_at": "2026-09-20T00:00:00Z",
        "comments": [
            {"id": "1", "created_at": "2026-09-10T00:00:00Z", "body": "a real filing"},
            {"id": "2", "created_at": "2026-09-10T00:01:00Z", "body": "a back-reference"},
        ],
        "issues": [
            {"number": 7, "created_at": "2026-09-12T00:00:00Z", "body": "from issuecomment-1"},
            {"number": 8, "created_at": "2026-09-09T00:00:00Z", "body": "see issuecomment-2"},
        ],
        "friction": [],
    }
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    code, out, _ = _run(path, capsys)
    assert code == 0
    assert "median 2.00d to file, over 1 of 2 finding(s)" in out, out
    assert "inverted" in out and "1 attribution(s)" in out, out
    assert "0 UNDETERMINED" in out, "the inverted pair was miscounted as undetermined"


def test_the_output_proposes_no_band(capsys) -> None:
    """#1085 defers thresholds; ADR 0009 governs the first one.

    Asserted on the output rather than trusted to review, because a band tends
    to arrive as a helpful adjective rather than as a number.
    """
    _, out, _ = _run(CASES / "good-known-delay" / "capture.json", capsys)
    assert "no band is proposed or implied" in out, out

    # THE DISCLAIMER LINE IS EXCLUDED FROM THE SCAN, and this is not a loophole
    # being carved for convenience: that line exists to SAY thresholds are
    # deferred, so it necessarily contains the word. Scanning it caught the
    # sentence asserting the absence and called it the presence. Every OTHER
    # line is scanned, which is where a band would actually appear - attached
    # to the number as an adjective rather than announced as a policy.
    graded = [ln for ln in out.splitlines() if "no band is proposed" not in ln]
    for word in ("threshold", "breach", "healthy", "unhealthy", "too slow", "acceptable"):
        for ln in graded:
            assert word not in ln.lower(), f"output grades the number with {word!r}: {ln}"
