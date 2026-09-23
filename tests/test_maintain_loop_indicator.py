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


# --------------------------------------------------------------------------- #
# Counter-model findings, 2026-09-23. Eight, and the common thread is that each
# one turned an incomplete or unreadable input into a confident answer.
# --------------------------------------------------------------------------- #
def _capture(tmp_path: Path, **doc) -> Path:
    base = {"captured_at": "2026-09-20T00:00:00Z", "comments": [], "issues": [], "friction": []}
    base.update(doc)
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


def test_a_malformed_population_member_is_unknown_not_an_observed_zero(
    tmp_path: Path, capsys
) -> None:
    """Dropping a member reports a SMALLER population as though it were the whole one.

    `{"comments":[null],"friction":["broken"]}` passed validation, lost both
    records to an `isinstance` filter, and reported an OBSERVED EMPTY
    POPULATION - the strongest clean answer this instrument has - over a
    capture whose lists were not empty at all.
    """
    path = _capture(tmp_path, comments=[None], friction=["broken"])
    # `_run` already drains capsys, so read the stderr IT returns rather than
    # calling readouterr() again - the second call returns nothing and the
    # assertion would pass on an empty string.
    code, _, err = _run(path, capsys)
    assert code == indicator.UNKNOWN_EXIT
    assert "malformed member" in err, err


def test_a_mixed_population_does_not_silently_understate_the_denominator(
    tmp_path: Path, capsys
) -> None:
    """The mixed case, which is the one a filter hides best.

    All-malformed is conspicuous; one bad member among good ones just moves
    every percentage without moving anything a reader can see.
    """
    good = {"id": "1", "created_at": "2026-09-10T00:00:00Z", "body": "x"}
    path = _capture(tmp_path, comments=[good, None, good])
    assert _run(path, capsys)[0] == indicator.UNKNOWN_EXIT


def test_the_window_shape_is_reported_as_a_number_and_never_as_a_label(
    tmp_path: Path, capsys
) -> None:
    """A CONDITIONAL LABEL IS A BAND, and #1085 forbids bands.

    This printed `wave-shaped: ...` when the top three days held >= 50% and a
    plainer sentence otherwise, so SIX equally-populated days earned the label
    and SEVEN did not. That is a threshold-based classification in the
    instrument built to honour the no-bands constraint, and the first output
    test missed it by checking only selected words.

    Both sides of the old boundary are asserted, because a test on one side
    passes on an instrument that labels everything.
    """
    for n in (6, 7):
        comments = [{"id": str(i), "created_at": f"2026-09-0{i}T00:00:00Z", "body": "x"}
                    for i in range(1, n + 1)]
        path = _capture(tmp_path, comments=comments)
        _, out, _ = _run(path, capsys)
        assert "top 3 day(s) carry" in out, out
        assert "wave-shaped" not in out, f"{n} days got a qualitative label: {out}"


def test_any_negative_delay_is_inverted_however_small(tmp_path: Path, capsys) -> None:
    """A tolerance is a threshold, and this one admitted a real inversion.

    With one second of slack, a filing event 0.5s BEFORE its finding entered
    the median as `-0.00d` and counted as attributable - a demonstrably earlier
    issue read as a fast filing.
    """
    path = _capture(
        tmp_path,
        comments=[{"id": "1", "created_at": "2026-09-10T00:00:00Z", "body": "x"}],
        issues=[{"number": 9, "created_at": "2026-09-09T23:59:59Z", "body": "issuecomment-1"}],
    )
    _, out, _ = _run(path, capsys)
    assert "NO attributable finding(s)" in out, out
    assert "1 attribution(s)" in out, out


def test_filing_events_are_ordered_by_instant_not_by_string(tmp_path: Path, capsys) -> None:
    """`2026-09-10T02:00:00+03:00` sorts AFTER `...T00:30:00Z` and is earlier.

    The earliest citing issue is the filing event, so comparing raw strings
    picks the wrong one whenever two offsets differ - which can convert an
    inversion into an attribution, or a long delay into a short one.
    """
    path = _capture(
        tmp_path,
        comments=[{"id": "1", "created_at": "2026-09-09T00:00:00Z", "body": "x"}],
        issues=[
            {"number": 1, "created_at": "2026-09-10T02:00:00+03:00", "body": "issuecomment-1"},
            {"number": 2, "created_at": "2026-09-10T00:30:00Z", "body": "issuecomment-1"},
        ],
    )
    _, out, _ = _run(path, capsys)
    # 2026-09-10T02:00+03:00 is 23:00Z on the 9th - the EARLIER instant.
    assert "median 0.96d" in out, out


def test_a_timezone_free_timestamp_does_not_crash_the_run(tmp_path: Path, capsys) -> None:
    """A naive timestamp parsed fine and then raised TypeError at subtraction.

    That is a crash escaping the three verdicts this instrument declares. It is
    now simply not a readable instant, so the finding is UNDETERMINED.
    """
    path = _capture(
        tmp_path,
        comments=[{"id": "1", "created_at": "2026-09-10T00:00:00", "body": "x"}],
        issues=[{"number": 9, "created_at": "2026-09-12T00:00:00Z", "body": "issuecomment-1"}],
    )
    code, out, err = _run(path, capsys)
    assert code == 0, err
    assert "Traceback" not in err
    assert "1 UNDETERMINED" in out, out


def test_a_negated_dismissal_is_not_an_exclusion(tmp_path: Path, capsys) -> None:
    """"This finding was NOT dismissed" is not a disposition.

    The exclusion set separates a finding decided AGAINST from one that took
    forever. A prose match anywhere in the body caught negations, quotations and
    descriptions of somebody else's decision - measured on the real population,
    17 of 18 exclusions were mentions rather than dispositions.

    The marker must OPEN a line. And the pattern may not use `\\s*`, which
    matches newlines: the first line-anchored cut anchored at a BLANK line and
    crossed into a later one, which left exactly one match on the real
    population and that match was on an empty line.
    """
    body = "This finding was not dismissed; it still needs a fix.\n"
    path = _capture(
        tmp_path,
        comments=[{"id": "1", "created_at": "2026-09-10T00:00:00Z", "body": body}],
    )
    _, out, _ = _run(path, capsys)
    assert "0 excluded as dismissed" in out, out
    assert "1 UNDETERMINED" in out, out

    # ...and the positive half, or the assertion above passes on a rule that
    # excludes nothing at all. A marker that OPENS a line is a disposition.
    second = tmp_path / "opened"
    second.mkdir()
    path2 = _capture(
        second,
        comments=[{"id": "1", "created_at": "2026-09-10T00:00:00Z",
                   "body": "Dismissed - covered by cpp#1 already.\n"}],
    )
    _, out2, _ = _run(path2, capsys)
    assert "1 excluded as dismissed" in out2, out2


def test_dated_friction_records_are_in_the_window(tmp_path: Path, capsys) -> None:
    """They are in the POPULATION, which is what the concentration divides by.

    Counting them in the denominator while ignoring their dates reported a
    window covering only the comments, and a friction-only capture reported
    "no dated records" with every record carrying a timestamp.
    """
    path = _capture(
        tmp_path,
        comments=[{"id": "1", "created_at": "2026-09-10T00:00:00Z", "body": "x"}],
        friction=[{"ts": "2026-09-01T00:00:00Z", "signal": "a"},
                  {"ts": "2026-09-20T00:00:00Z", "signal": "b"}],
    )
    _, out, _ = _run(path, capsys)
    assert "window 2026-09-01..2026-09-20" in out, out
    assert "3 active day(s)" in out, out
