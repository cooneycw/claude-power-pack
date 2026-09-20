"""The Python SAST gate, and the states its negative control cannot reach (issue #962).

`controls/bandit-audit` covers DISCRIMINATION - an unaccounted finding, a stale
allowlist line, a bare `# nosec`, a rule-scoped `# nosec <ID>`, and a fully
accounted tree - and `tests/test_negative_controls.py` drives that register.
This file covers what a registered control structurally cannot:

  * the UNKNOWN states. `check-negative-controls.py` scores a case GOOD or BAD
    and has no third expectation, deliberately. But UNKNOWN is the verdict that
    separates "this run examined nothing" from "this tree is clean", and a
    bandit report that silently skipped a file it could not parse produces the
    same empty `results` as a clean one.

  * the half the ANCHOR cannot demonstrate. The anchor is codex-power-pack's
    `--skip B104,B108,B310,B602` one-liner, so it must AGREE with the gate on
    every known-GOOD case - which means no GOOD case may carry a finding
    OUTSIDE that skip list, or the anchor would report and the control would be
    UNRESOLVED. That the allowlist also suppresses a rule outside the skip list
    is therefore coverage no case can hold, and it lives here.

  * the FIXTURE's own eligibility. Issue #962 names the way this control gets
    built blind: "pick a fixture triggering a skipped check and it goes green
    while the gate is doing nothing". The fixture's rule being outside both
    lists is a property to assert mechanically, not a sentence to write in a
    comment - so it is asserted here against the real files.

  * the WIRING invariants. Whether the CI step runs the live positive control
    BEFORE the audit, whether the tool is pinned rather than fetched, and
    whether a `--skip` has been reintroduced anywhere, are facts about files
    rather than about a gate's judgement.

  * the BOUND. `test_a_same_count_site_replacement_is_a_known_blind_spot`
    asserts what the gate CANNOT see, which no control can express: a control
    registers a verdict the gate must reach, and this is a verdict it must
    deliberately NOT reach. If it ever fails, the bound has been closed and the
    test should be deleted along with the three prose statements about it.

Four of the tests here exist because a counter-model review found the defects
they pin: the rule-scoped `# nosec` channel, bandit recursing past the pruned
population, the relative venv path, and the count's site-replacement bound.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "bandit-audit.py"
CONTROL = REPO / "controls" / "bandit-audit"
CASES = CONTROL / "cases"
LIVE = CONTROL / "live"
ALLOW = REPO / ".bandit-audit-allow"

#: The list this gate exists NOT to inherit (`Makefile:101` in codex-power-pack).
CXPP_SKIP = {"B104", "B108", "B310", "B602"}

requires_bandit = pytest.mark.skipif(
    shutil.which("bandit") is None and not (REPO / ".venv" / "bin" / "bandit").is_file(),
    reason="bandit is not installed; run `uv sync --extra dev`",
)


def _load_gate():
    """Import the gate for the functions no CLI path reaches."""
    spec = importlib.util.spec_from_file_location("bandit_audit", GATE)
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE execution: the gate carries `from __future__ import
    # annotations`, so its dataclasses resolve field types by looking the module
    # up in `sys.modules` at class-creation time.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True, text=True, cwd=REPO, check=False, timeout=600,
    )


def _capture(tmp_path: Path, *, files, results=None, errors=None, metrics=None,
             roots=("lib", "scripts"), schema=1) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    per_file = {f: {"loc": 10, "nosec": 0, "skipped_tests": 0} for f in files}
    per_file["_totals"] = {"loc": 10 * len(files), "nosec": 0, "skipped_tests": 0}
    if metrics:
        for name, values in metrics.items():
            per_file.setdefault(name, {"loc": 10, "nosec": 0, "skipped_tests": 0}).update(values)
    payload = {
        "schema": schema,
        "roots": list(roots),
        "files": list(files),
        "report": {
            "errors": list(errors or []),
            "metrics": per_file,
            "results": list(results or []),
        },
    }
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _result(path: str, test_id: str, severity: str = "HIGH", line: int = 1) -> dict:
    return {
        "filename": path, "test_id": test_id, "issue_severity": severity,
        "issue_confidence": "HIGH", "line_number": line, "issue_text": "fixture",
    }


def _allow(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".bandit-audit-allow"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# UNKNOWN is never a pass - the states no registered case can express
# --------------------------------------------------------------------------- #

def test_a_file_bandit_could_not_parse_is_unknown_not_clean(tmp_path):
    """A syntax error removes a file from analysis and leaves it in `metrics`.

    Measured directly: a file containing `def broken(:` produced
    `metrics["probe/c.py"] = {"loc": 1, ...}` AND an entry in `errors`. So
    membership in `metrics` proves the file was READ, never that it was
    ANALYSED - and a gate checking only membership reports a clean tree over a
    population part of which was never examined. Same shape as pip-audit's
    `skip_reason` one gate over (#961).
    """
    capture = _capture(
        tmp_path,
        files=["lib/a.py", "lib/broken.py"],
        errors=[{"filename": "lib/broken.py", "reason": "syntax error while parsing AST from file"}],
    )
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "BANDIT-UNKNOWN:" in proc.stderr
    assert "lib/broken.py" in proc.stderr
    assert "bandit-audit: ok" not in proc.stdout


def test_a_file_missing_from_the_report_is_unknown_not_clean(tmp_path):
    """The walk and the scan must agree about what was examined.

    A capture recorded against a narrower root, or a scan that silently stopped
    early, yields a report describing fewer files than the population. Reading
    that as clean is the coverage claim this gate is not entitled to make.
    """
    capture = _capture(tmp_path, files=["lib/a.py"])
    payload = json.loads(capture.read_text(encoding="utf-8"))
    payload["files"].append("lib/never-scanned.py")
    capture.write_text(json.dumps(payload), encoding="utf-8")
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "lib/never-scanned.py" in proc.stderr
    assert "bandit-audit: ok" not in proc.stdout


def test_a_finding_outside_the_enumerated_population_is_unknown(tmp_path):
    """A report naming a file nobody enumerated is not attributable.

    Reporting it as a finding would attribute a verdict to a file this run never
    looked at; dropping it silently would under-report. Neither is honest, so
    the disagreement itself is the verdict.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"], results=[_result("lib/elsewhere.py", "B602")],
    )
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "lib/elsewhere.py" in proc.stderr


def test_a_zero_file_population_is_unknown_not_clean(tmp_path):
    """`0 findings` over 0 files is the blind-instrument signature ADR 0008 names."""
    capture = _capture(tmp_path, files=[])
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "zero-file population is not a clean one" in proc.stderr


def test_an_unreadable_allowlist_is_unknown_not_clean(tmp_path):
    """A ledger that could not be parsed leaves every disposition undecided."""
    capture = _capture(tmp_path, files=["lib/a.py"])
    bad = _allow(tmp_path, "this is not a record\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(bad))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "BANDIT-UNKNOWN:" in proc.stderr
    assert "bandit-audit: ok" not in proc.stdout


def test_unknown_never_prints_a_verdict_line_beside_itself(tmp_path):
    """A run that could not look must not also print a sentence about the tree."""
    capture = _capture(tmp_path, files=[])
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert "bandit-audit:" not in proc.stdout


# --------------------------------------------------------------------------- #
# The allowlist's contract
# --------------------------------------------------------------------------- #

def test_an_issue_reference_survives_the_comment_stripper(tmp_path):
    """`#` opens a comment AND opens every issue reference on a record.

    The sibling gate shipped `line.split("#")[0]`, which silently ate the `#922`
    off the first record ever written against it (#961). This parser takes
    whole-line comments only; run against a suffix-stripping one, this test
    fails because the record loses its fifth field and becomes unparseable.
    """
    module = _load_gate()
    path = _allow(tmp_path, "finding lib/a.py B602 1 #1113\nreviewed-low B404 #1114\n")
    ledger = module.parse_allow(path)
    assert len(ledger.findings) == 1
    assert ledger.findings[0].issue == "#1113"
    # BOTH record types carry an issue reference, so both are exposed to the
    # stripper this test exists to catch (issue #1114).
    assert len(ledger.reviewed_low) == 1
    assert ledger.reviewed_low[0].issue == "#1114"


def test_a_line_accepting_fewer_than_the_reported_count_is_stale(tmp_path):
    """The count is the mechanism, and its shortfall direction is what keeps it honest.

    A line accepting 2 against a run reporting 1 means a site was FIXED. Left
    standing it silently pre-authorises the next one, which is the blanket
    behaviour the allowlist replaced.
    """
    capture = _capture(tmp_path, files=["lib/a.py"], results=[_result("lib/a.py", "B602")])
    allow = _allow(tmp_path, "finding lib/a.py B602 2 #1113\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BANDIT-STALE:" in proc.stderr
    assert "lower the count to 1" in proc.stderr


def test_a_new_site_in_an_already_accepted_file_is_a_finding(tmp_path):
    """The distinction a blanket `--skip` cannot draw, and the reason for the count.

    A gate keyed on (file, rule) alone accepts an unbounded number of new sites
    in any file that already has one. This is what makes a THIRD `shell=True` in
    `lib/cicd/steps.py` a finding rather than a silent inheritance.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"],
        results=[_result("lib/a.py", "B602", line=n) for n in (1, 2, 3)],
    )
    allow = _allow(tmp_path, "finding lib/a.py B602 2 #1113\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BANDIT-FINDING:" in proc.stderr
    assert "1 new site(s)" in proc.stderr


def test_a_rule_outside_the_inherited_skip_list_is_suppressible_too(tmp_path):
    """The coverage the ANCHOR structurally cannot carry.

    Every GOOD case in `controls/bandit-audit` uses a rule on CxPP's skip list,
    because the anchor must AGREE with the gate on known-good input and can only
    agree on findings it drops. So nothing in the registered control shows the
    allowlist working for a rule OUTSIDE that list - B314 here - and without
    this test the gate could be accepting only the four inherited rules and no
    case would notice.
    """
    capture = _capture(
        tmp_path, files=["scripts/a.py"],
        results=[_result("scripts/a.py", "B314", severity="MEDIUM")],
    )
    allow = _allow(tmp_path, "finding scripts/a.py B314 1 #1113\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "bandit-audit: ok" in proc.stdout


def test_a_duplicate_record_is_refused_rather_than_summed(tmp_path):
    """Two lines summing to the observed count read exactly like one that names it.

    They are not the same record: a duplicate is how a count gets raised without
    the original line's issue reference being revisited.
    """
    capture = _capture(tmp_path, files=["lib/a.py"])
    allow = _allow(tmp_path, "finding lib/a.py B602 1 #1113\nfinding lib/a.py B602 1 #1113\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "repeats lib/a.py B602" in proc.stderr


def test_a_zero_count_record_is_refused(tmp_path):
    """A line accepting zero findings accepts nothing and would read as suppression."""
    capture = _capture(tmp_path, files=["lib/a.py"])
    allow = _allow(tmp_path, "finding lib/a.py B602 0 #1113\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "not a positive integer" in proc.stderr


def test_a_rule_scoped_nosec_is_a_finding_in_its_own_field(tmp_path):
    """The two inline forms land in DIFFERENT fields, and the first cut read one.

    Measured on bandit 1.9.4: `# nosec` sets `metrics.<file>.nosec`, while
    `# nosec B307` sets `metrics.<file>.skipped_tests` and leaves `nosec` at 0.
    A gate reading only `nosec` misses the rule-scoped form entirely - which is
    the form a careful author is MORE likely to write, because it suppresses
    less. Found by the counter-model review, not by the author.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"], metrics={"lib/a.py": {"skipped_tests": 1, "nosec": 0}},
    )
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BANDIT-SUPPRESSION:" in proc.stderr
    assert "rule-scoped" in proc.stderr
    assert "lib/a.py" in proc.stderr


def test_a_same_count_site_replacement_is_a_known_blind_spot(tmp_path):
    """THE BOUND, COMMITTED - this test asserts what the gate CANNOT see.

    A line matches on (file, rule, count), so it is a count BASELINE and not a
    per-site identity: fix one accepted site and add a different one in the same
    file, and the count is unchanged and the run is green. Named in the gate's
    docstring, in `.bandit-audit-allow`'s header and in `docs/scripts.md`, and
    pinned here so the bound is a committed fact rather than a sentence someone
    may quietly widen past.

    Deliberate rather than unnoticed: a line number is invalidated by every edit
    above it and a snippet hash by every reformat, and a ledger that reddens on
    unrelated edits is one somebody switches off (ADR 0009). The larger question
    is answered by review of the diff that moved the site, and by #1113.

    IF THIS TEST EVER FAILS, the gate has become site-aware and the bound has
    been closed - delete the test and the three prose statements together.
    """
    before = _capture(tmp_path / "b", files=["lib/a.py"],
                      results=[_result("lib/a.py", "B602", line=10)])
    after = _capture(tmp_path / "a", files=["lib/a.py"],
                     results=[_result("lib/a.py", "B602", line=999)])
    allow = _allow(tmp_path, "finding lib/a.py B602 1 #1113\n")
    for capture in (before, after):
        proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "bandit-audit: ok" in proc.stdout


def test_a_low_severity_finding_is_counted_and_never_gating(tmp_path):
    """"Below the gate" and "not examined" are the two states the count keeps apart.

    The SEVERITY half of the threshold decision, unchanged by #1114: a LOW
    finding of a REVIEWED rule class is counted and exits 0. What #1114 added is
    a second, independent question about the same finding - has anyone read this
    rule class - and the record below is the answer to that one, not a change to
    this one.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"], results=[_result("lib/a.py", "B404", severity="LOW")],
    )
    allow = _allow(tmp_path, "reviewed-low B404 #1114\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 below threshold in 1 rule class(es), 1 reviewed (#1114)" in proc.stdout
    assert "below-threshold band by rule - B404 x1" in proc.stdout


# --------------------------------------------------------------------------- #
# The band below the threshold - issue #1114
# --------------------------------------------------------------------------- #

def test_an_unreviewed_low_rule_class_is_a_finding(tmp_path):
    """THE POSITIVE CONTROL for #1114's check: it can fire at all.

    Same capture as the test above, same severity, same file - and an EMPTY
    ledger. If this exits 0 the gate has no way to tell a rule class somebody
    read from one nobody has, which is the single distinction #1114 exists to
    add, and ADR 0010's seven dispositions become a claim nothing re-derives.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"], results=[_result("lib/a.py", "B404", severity="LOW")],
    )
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BANDIT-LOW-UNREVIEWED: B404" in proc.stderr
    assert "1 below threshold in 1 rule class(es), 0 reviewed (#1114)" in proc.stdout


def test_a_record_for_one_class_does_not_review_another(tmp_path):
    """A record accounts for ITS rule class, not for the band.

    The cheap wrong implementation - any record at all means the LOW band is
    reviewed - passes the pair of tests above and fails here. Without this, a
    single `reviewed-low` line would silently become the `--skip` issue #962
    rejected, wearing a different name.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"],
        results=[
            _result("lib/a.py", "B404", severity="LOW"),
            _result("lib/a.py", "B603", severity="LOW", line=2),
        ],
    )
    allow = _allow(tmp_path, "reviewed-low B404 #1114\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BANDIT-LOW-UNREVIEWED: B603" in proc.stderr
    assert "BANDIT-LOW-UNREVIEWED: B404" not in proc.stderr
    assert "2 below threshold in 2 rule class(es), 1 reviewed (#1114)" in proc.stdout


def test_a_reviewed_low_record_that_matches_nothing_is_a_note_not_a_finding(tmp_path):
    """THE PINNED ASYMMETRY, and the direction that is easy to "fix" wrongly.

    A stale `finding` record reddens: a suppression outliving its finding is a
    blindfold nobody re-reads. A `reviewed-low` record that matches nothing
    suppressed nothing, so it prints a NOTE and exits 0 - because reddening
    there means deleting the last `import subprocess` in a file turns the build
    red, and a ledger that reddens on unrelated edits is one somebody switches
    off (ADR 0009). Written as a test rather than as a comment so that making
    the two directions symmetric has to be a decision.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"], results=[_result("lib/a.py", "B404", severity="LOW")],
    )
    allow = _allow(tmp_path, "reviewed-low B404 #1114\nreviewed-low B101 #1114\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BANDIT-LOW-NOTE" in proc.stderr
    assert "B101" in proc.stderr
    assert "bandit-audit: ok" in proc.stdout


def test_a_reviewed_low_record_cannot_suppress_a_gated_finding(tmp_path):
    """The two record types are not interchangeable, and this is the dangerous way.

    `reviewed-low` is deliberately cheaper than a `finding` record - no path, no
    count - so if it could also account for a MEDIUM+ finding it would be a
    one-line, tree-wide, permanent suppression of exactly the band #962's empty
    skip list exists to keep visible.
    """
    capture = _capture(
        tmp_path, files=["lib/a.py"], results=[_result("lib/a.py", "B602", severity="HIGH")],
    )
    allow = _allow(tmp_path, "reviewed-low B602 #1114\n")
    proc = _run("--from-capture", str(capture), "--allow-file", str(allow))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "BANDIT-FINDING: lib/a.py:1 B602" in proc.stderr


def test_a_duplicate_reviewed_low_record_is_refused(tmp_path):
    """Two dispositions for one rule class, and no way to tell which is live."""
    module = _load_gate()
    path = _allow(tmp_path, "reviewed-low B404 #1114\nreviewed-low B404 #1113\n")
    with pytest.raises(module.Unknown) as excinfo:
        module.parse_allow(path)
    assert "repeats reviewed-low B404" in str(excinfo.value)


def test_a_malformed_reviewed_low_record_is_unknown_not_ignored(tmp_path):
    """An unparseable record must never degrade into a silently skipped line.

    That property is what makes a second record type safe to add at all: a typo
    in the first field cannot become "some other record type I do not handle",
    and a record with the wrong arity cannot become a hole.
    """
    module = _load_gate()
    for text in ("reviewed-low B404\n", "reviewed-low B404 #1114 3\n", "reviewed B404 #1114\n"):
        with pytest.raises(module.Unknown):
            module.parse_allow(_allow(tmp_path, text))


def test_the_ledger_and_adr_0010_name_the_same_reviewed_rule_classes():
    """The record and the reading it points at, checked against each other.

    A `reviewed-low` record is a POINTER: it says this rule class was read, and
    names the issue whose reading is written up in ADR 0010. Those are two
    enumerations of one set, kept in two files, and nothing but this test
    notices when they diverge - a record added without a disposition is an
    acceptance nobody wrote down, and a disposition whose record was dropped in
    a refactor reddens the gate for a class that WAS read.

    Asserted without bandit deliberately: the gate already enforces the tree
    side on every run, and a test that needed the binary would be skipped
    exactly where the ledger is most likely to be edited blind.
    """
    module = _load_gate()
    ledger = module.parse_allow(ALLOW)
    recorded = {r.test_id for r in ledger.reviewed_low}
    assert recorded, (
        "the repository's ledger records no reviewed LOW rule class, so either the "
        "LOW band is empty (it is not) or ADR 0010's disposition has been dropped"
    )
    adr = REPO / "docs" / "decisions" / "0010-bandit-low-band-disposition.md"
    assert adr.is_file(), f"{adr} is missing - the records below point at nothing"
    dispositioned = set(re.findall(r"^### (B\d+) ", adr.read_text(encoding="utf-8"), re.M))
    assert dispositioned, (
        f"{adr.name} carries no `### B<id>` disposition heading, so this test would "
        "compare the ledger against an empty set and pass vacuously"
    )
    assert recorded == dispositioned, (
        f"the ledger records {sorted(recorded)} and {adr.name} dispositions "
        f"{sorted(dispositioned)} - only in one: {sorted(recorded ^ dispositioned)}"
    )
    for record in ledger.reviewed_low:
        assert record.issue.startswith("#"), (
            f"reviewed-low {record.test_id} names no issue - the record is the pointer "
            "to where the reading lives, and one without it is an unsourced assertion"
        )


# --------------------------------------------------------------------------- #
# The fixture's own eligibility - issue #962 asks for this in writing
# --------------------------------------------------------------------------- #

def test_the_live_bad_fixture_uses_a_rule_outside_both_suppression_lists():
    """Issue #962: "Confirm the fixture's rule ID is outside the skip list, and say so."

    Two lists, because the skip list was REPLACED rather than merely emptied:

      * CxPP's inherited `--skip B104,B108,B310,B602`. A fixture triggering one
        of those would go green while the gate does nothing - the failure the
        issue names by name.
      * this repository's own `.bandit-audit-allow`, which is what replaced it.
        A fixture the residual already accounts for is suppressed by the very
        mechanism under test.

    Asserted against the real report rather than read off a comment, because a
    comment cannot notice bandit re-classifying a rule.
    """
    module = _load_gate()
    bad = LIVE / "bad-known-finding"
    assert bad.is_dir()
    prefix = module.resolve_bandit()
    proc = subprocess.run(
        [*prefix, "-r", ".", "-f", "json", "-q", "--exit-zero"],
        cwd=bad, capture_output=True, text=True, check=False, timeout=600,
    )
    report = json.loads(proc.stdout)
    gated = {
        r["test_id"] for r in report["results"]
        if r["issue_severity"].upper() in module.GATED_SEVERITIES
    }
    assert gated, "the known-bad fixture reported nothing at the gated severity"
    assert not (gated & CXPP_SKIP), (
        f"fixture rule(s) {sorted(gated & CXPP_SKIP)} are on codex-power-pack's inherited "
        "skip list, so this control would pass for the wrong reason (issue #962)"
    )
    # THE `finding` RECORDS ONLY, and `reviewed-low` deliberately NOT (issue
    # #1114, counter-model review pass 2). Widening this to both record types
    # looks like belt-and-braces and is not: a `reviewed-low` record cannot
    # suppress a GATED finding - `selftest()` never reads the ledger at all -
    # so the only thing the wider assertion can do is fail when SOMEBODY ELSE's
    # ledger grows a record, reporting a neighbour's correct change as this
    # fixture having stopped discriminating. That a review record cannot account
    # for a MEDIUM+ finding is asserted directly and on its own, by
    # test_a_reviewed_low_record_cannot_suppress_a_gated_finding.
    allowed_rules = {e.test_id for e in module.parse_allow(ALLOW).findings}
    assert not (gated & allowed_rules), (
        f"fixture rule(s) {sorted(gated & allowed_rules)} appear in {module.ALLOW_FILE}, "
        "the mechanism that replaced the skip list"
    )


test_the_live_bad_fixture_uses_a_rule_outside_both_suppression_lists = requires_bandit(
    test_the_live_bad_fixture_uses_a_rule_outside_both_suppression_lists
)


def test_no_registered_case_is_covered_by_the_repositorys_own_allowlist():
    """A case fixture must not be suppressed by the real residual.

    The cases name real repository paths on purpose - they model this tree - so
    the risk is concrete rather than hypothetical: a case whose (file, rule) pair
    is also on `.bandit-audit-allow` would be adjudicated against the case's own
    ledger today and against the repository's the moment someone ran the gate
    with the default `--allow-file`.
    """
    module = _load_gate()
    ledger = module.parse_allow(ALLOW)
    repo_pairs = {(e.path, e.test_id) for e in ledger.findings}
    for case in sorted(CASES.iterdir()):
        if not case.name.startswith("bad-"):
            continue
        payload = json.loads((case / "bandit-capture.json").read_text(encoding="utf-8"))
        for result in payload["report"]["results"]:
            pair = (result["filename"], result["test_id"])
            assert pair not in repo_pairs, (
                f"case {case.name} reports {pair}, which {module.ALLOW_FILE} already accepts - "
                "the case would be suppressed by the mechanism it exists to exercise"
            )


def test_every_case_is_adjudicated_against_its_own_ledger_not_the_repositorys():
    """What actually makes a case independent of this repository's residual.

    The pair check above protects `finding` records by construction, because the
    case fixtures name paths that exist nowhere. The SECOND record type has no
    such protection: `reviewed-low` keys on the RULE CLASS alone, so a fixture
    path nobody else uses buys nothing, and the only thing standing between a
    case and the repository's ledger is that the manifest hands the gate the
    case's OWN `--allow-file`.

    THIS ASSERTS THAT, RATHER THAN CONSTRAINING WHICH RULES A FIXTURE MAY USE
    (counter-model review, codex). The first cut asserted the latter - that no
    bad case may report a LOW class the repository has reviewed - and that check
    cannot tell "our fixture stopped discriminating" from "a neighbour's ledger
    grew a record", which is the second detector-contract question. It would
    have failed the day somebody legitimately dispositioned B110 for `lib/`,
    while the fixture went on scoring BAD exactly as designed, and sent them to
    rewrite a control fixture that was not broken.

    Stated bound: this does NOT cover a hand-run of the gate against a case
    capture with the DEFAULT `--allow-file`. That is not how the harness
    consumes these cases, and for `reviewed-low` no per-case assertion can cover
    it - the key is a rule class the repository is free to review later.
    """
    spec = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))
    invocation = spec["invocation"]
    assert "--allow-file" in invocation, (
        "the registered invocation passes no --allow-file, so EVERY case is adjudicated "
        "against the repository's own .bandit-audit-allow - the systemic form of the "
        "hazard the per-case checks above only cover one instance of"
    )
    ledger_arg = invocation[invocation.index("--allow-file") + 1]
    assert "{case}" in ledger_arg, (
        f"the registered invocation supplies --allow-file {ledger_arg!r}, which does not "
        "resolve per case - a case cannot be independent of a ledger it does not own"
    )


def test_the_clean_live_fixture_is_clean_at_every_severity():
    """A LOW finding here would make the selftest's own denominator ambiguous."""
    module = _load_gate()
    prefix = module.resolve_bandit()
    proc = subprocess.run(
        [*prefix, "-r", ".", "-f", "json", "-q", "--exit-zero"],
        cwd=LIVE / "good-clean", capture_output=True, text=True, check=False, timeout=600,
    )
    report = json.loads(proc.stdout)
    assert report["results"] == [], report["results"]
    assert report["errors"] == [], report["errors"]


test_the_clean_live_fixture_is_clean_at_every_severity = requires_bandit(
    test_the_clean_live_fixture_is_clean_at_every_severity
)


# --------------------------------------------------------------------------- #
# Wiring invariants - facts about files, not about a gate's judgement
# --------------------------------------------------------------------------- #

def test_the_ci_step_runs_the_live_positive_control_before_the_audit():
    """Order is the property. A clean verdict from a scan never shown able to
    find something is indistinguishable from a clean tree."""
    pipeline = yaml.safe_load((REPO / ".woodpecker.yml").read_text(encoding="utf-8"))
    commands = pipeline["steps"]["bandit-audit"]["commands"]
    audit = [i for i, c in enumerate(commands) if "bandit-audit.py" in c and "--selftest" not in c]
    selftest = [i for i, c in enumerate(commands) if "--selftest" in c]
    assert selftest and audit, commands
    assert max(selftest) < min(audit), commands


def test_the_ci_step_is_hard_and_does_not_ignore_failure():
    pipeline = yaml.safe_load((REPO / ".woodpecker.yml").read_text(encoding="utf-8"))
    assert pipeline["steps"]["bandit-audit"].get("failure") != "ignore"


def test_the_tool_is_pinned_in_the_lock_rather_than_fetched_at_run_time():
    """A linter's ruleset moves between releases.

    `.woodpecker.yml` pins shellcheck by image digest for exactly this reason -
    "running the gate under two different linters would make the control's
    verdict depend on which container reached it" - and a Python tool cannot be
    pinned that way, so the lock is where the parity comes from. A `uvx bandit`
    CI step would resolve whatever PyPI serves that morning.
    """
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'"bandit>=[\d.]+,<\d', pyproject), "bandit is not declared in the dev extra"
    assert "bandit" in (REPO / "uv.lock").read_text(encoding="utf-8")
    pipeline = yaml.safe_load((REPO / ".woodpecker.yml").read_text(encoding="utf-8"))
    commands = pipeline["steps"]["bandit-audit"]["commands"]
    assert any("uv sync" in c and "--frozen" in c for c in commands), commands
    assert not any("uvx" in c for c in commands), commands


def test_no_suppression_option_reaches_bandit_from_the_build():
    """#962's decision, made mechanical rather than remembered.

    SCOPED TO BANDIT'S OWN LINES (counter-model review pass 2). The first cut
    searched every non-comment line in both build files for `--skip`, so adding
    a target that invokes the existing `scripts/npm-global-upgrade.sh
    --skip-install` would fail this Bandit test without changing anything about
    the SAST configuration - a non-zero that cannot tell our thing from a
    neighbour's, which is the second detector-contract question asked of this
    very test. The narrow scope is the remedy here rather than a looser
    pattern: another tool's flags are that tool's business.
    """
    for name in ("Makefile", ".woodpecker.yml"):
        text = (REPO / name).read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # the prose explaining the decision quotes the list
            if "bandit" not in stripped:
                continue
            offenders = [t for t in stripped.split() if _option_name(t) in SUPPRESSION_OPTIONS]
            assert not offenders, f"{name}: {line}"


def test_the_gate_is_in_verify_and_dep_audits_network_exclusion_is_untouched():
    """The asymmetry between the two audit gates is a decision, and it is checked.

    `dep-audit` is out of `verify` because it REQUIRES THE NETWORK, with a
    pre-committed reversal trigger: "if `verify` ever acquires another target
    that REQUIRES the network, the reason for this exclusion is gone". This gate
    is in `verify` precisely because it does not, so this test pins both halves -
    that bandit-audit joined, and that dep-audit did not.
    """
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    body = makefile.split("\nverify:", 1)[1].split("\n\n", 1)[0]
    assert "bandit-audit" in body, body
    assert "dep-audit" not in body, body


def test_bandit_is_handed_the_enumerated_files_and_never_recurses_itself():
    """The two traversals must not be able to disagree.

    `discover()` prunes `.venv`, `venv` and the caches; `bandit -r lib scripts`
    prunes nothing. Measured: with `lib/.venv/site-packages/dep.py` present,
    `-r` reported findings in a file the population never enumerated, and the
    gate correctly - but uselessly - reported UNKNOWN because a neighbour's
    installed dependency had changed. Handing bandit the file list makes the
    populations identical BY CONSTRUCTION, so there is no second exclusion list
    to keep in sync. Found by the counter-model review.
    """
    module = _load_gate()
    assert "-r" not in module.BANDIT_FLAGS, module.BANDIT_FLAGS
    text = GATE.read_text(encoding="utf-8")
    assert '"-r", *SCAN_ROOTS' not in text
    assert "*targets" in text


@requires_bandit
def test_a_virtualenv_under_a_scanned_root_does_not_redden_the_gate(tmp_path):
    """The failure the explicit file list removes, exercised end to end."""
    module = _load_gate()
    root = tmp_path / "proj"
    (root / "lib" / ".venv" / "site-packages").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "lib" / "a.py").write_text("X = 1\n", encoding="utf-8")
    (root / "scripts" / "b.py").write_text("Y = 2\n", encoding="utf-8")
    (root / "lib" / ".venv" / "site-packages" / "dep.py").write_text(
        'import subprocess\nsubprocess.call("ls", shell=True)\n', encoding="utf-8"
    )
    files = module.discover(root)
    assert files == ["lib/a.py", "scripts/b.py"], files
    proc = subprocess.run(
        [sys.executable, str(GATE), "--root", str(root), "--allow-file", str(_allow(tmp_path, ""))],
        capture_output=True, text=True, cwd=REPO, check=False, timeout=600,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "2 file(s) examined" in proc.stdout


def test_every_resolved_bandit_path_is_absolute(tmp_path):
    """A relative argv[0] is resolved against the CHILD's cwd, not the parent's.

    The venv fallback returned `.venv/bin/bandit`, and every subprocess here
    sets its own cwd - so on a box with bandit only in the project venv,
    `--selftest` died with `FileNotFoundError` and reported UNKNOWN. Reproduced
    before the fix. Found by the counter-model review.
    """
    module = _load_gate()
    fake = tmp_path / ".venv" / "bin"
    fake.mkdir(parents=True)
    binary = fake / "bandit"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    prefix = module.resolve_bandit(tmp_path)
    assert Path(prefix[0]).is_absolute(), prefix


#: Every spelling a suppression option can wear. `--skip B104`, `--skip=B104`
#: and `-sB104` are the same instruction to `argparse` and three different
#: strings, which is why the first cut of the test below - a set intersection
#: over exact tokens - let two of the three straight through (counter-model
#: review pass 2, measured: with `--skip=B104` the token assertion passed, the
#: B307 selftest passed, the repository audit passed, and bandit stopped
#: reporting `host = "0.0.0.0"`).
SUPPRESSION_OPTIONS = {"s", "skip", "t", "tests", "c", "configfile", "ini",
                       "profile", "p", "baseline", "b"}

#: The argv this gate is allowed to build. Pinned as a LITERAL, because an
#: allowlist of permitted flags is the only form no new spelling can slip past.
EXPECTED_BANDIT_FLAGS = ("-f", "json", "-q", "--exit-zero")


def _option_name(token: str) -> str | None:
    """The option a token carries, however it is spelled, or None for a value."""
    if not token.startswith("-"):
        return None
    body = token.lstrip("-").split("=", 1)[0]
    if token.startswith("--"):
        return body
    # A short option may carry its value attached: `-sB104` is `-s B104`.
    return body[:1] if body else None


def test_the_constructed_argv_is_pinned_and_carries_no_suppression_option():
    """The CLI-flag question, asked where it can actually fail.

    `metrics.skipped_tests` does NOT report a `--skip` - measured, `--skip B307`
    yields 0 - so the guard that claimed to catch one was blind. The behavioural
    backstop is that `BANDIT_FLAGS` is ONE list shared with `--selftest`, but
    that only covers the rule the fixture exercises: `--skip B104` passes it,
    because nothing in that fixture is a B104.

    So the argv is PINNED, not merely screened. An exact-token screen is what
    pass 1's fix used and pass 2 defeated with `--skip=B104` and `-sB104`; an
    equality assertion has no spelling to miss. The normalized-option check
    below is defence in depth for the day someone legitimately updates the
    literal: it keeps the pin from being edited into a hole.
    """
    module = _load_gate()
    assert tuple(module.BANDIT_FLAGS) == EXPECTED_BANDIT_FLAGS, module.BANDIT_FLAGS
    offenders = [t for t in module.BANDIT_FLAGS if _option_name(t) in SUPPRESSION_OPTIONS]
    assert not offenders, offenders


@pytest.mark.parametrize("spelling", ["--skip B104", "--skip=B104", "-sB104", "-s B104",
                                      "--configfile=x.ini", "-cx.ini", "--tests=B307"])
def test_every_spelling_of_a_suppression_option_is_recognised(spelling):
    """The screen's own negative control.

    A screen that recognises only the spelling its author happened to type is
    the defect pass 2 found, so the spellings are a committed case rather than
    a claim. Run against the pass-1 screen (`set(FLAGS) & {"-s", "--skip", ...}`)
    the attached forms score clean, which is how they got through.
    """
    assert any(_option_name(t) in SUPPRESSION_OPTIONS for t in spelling.split())


def test_the_selftest_shares_the_audits_flags_and_root():
    """The control over the flag list: one list, one scan function, one cwd.

    Two separate invocations would let a `--skip` be added to the audit while
    the positive control kept passing - the exact shape this gate refuses.

    READ WITH `ast`, NOT `in` (the trap this repository names). The first cut
    asserted `"BANDIT_FLAGS" not in body` over the raw source and failed on the
    function's OWN COMMENT explaining why it shares the list - better prose
    makes a text guard more false-positive, not less. The AST sees names, so a
    comment cannot trip it and a string literal cannot satisfy it either.
    """
    tree = ast.parse(GATE.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "selftest")
    calls = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "scan" in calls, f"the selftest must reuse scan(); it calls {sorted(calls)}"
    assert "subprocess" not in {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}, (
        "the selftest must not launch bandit itself - it would then carry its own flags"
    )
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "BANDIT_FLAGS" not in names, "the selftest must not name its own flags"


def test_an_unreadable_subtree_is_unknown_not_a_smaller_clean_population(tmp_path, monkeypatch):
    """An enumeration that fails partway must not yield a short list and a green.

    `os.walk` swallows directory-read errors by default and omits the subtree.
    Measured by the counter-model review: injecting `PermissionError` for
    `lib/security/` took the population from 113 files to 94 and the audit still
    printed `ok`, exit 0 - a zero that cannot tell clean security code from
    security code it could not enumerate. The coverage check downstream compares
    bandit's report against THIS list, so it agrees with the gap rather than
    seeing it.
    """
    module = _load_gate()
    root = tmp_path / "proj"
    (root / "lib" / "inner").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "lib" / "a.py").write_text("X = 1\n", encoding="utf-8")

    real_walk = module.os.walk

    def exploding_walk(top, *args, **kwargs):
        for entry in real_walk(top, *args, **kwargs):
            yield entry
        onerror = kwargs.get("onerror")
        if onerror is not None:
            exc = PermissionError(13, "Permission denied")
            exc.filename = str(root / "lib" / "inner")
            onerror(exc)

    monkeypatch.setattr(module.os, "walk", exploding_walk)
    with pytest.raises(module.Unknown) as caught:
        module.discover(root)
    assert "file list is incomplete" in str(caught.value)


def test_an_absent_declared_root_is_unknown_not_an_empty_clean_scan(tmp_path):
    """"The root is not there" and "the root is clean" are not the same fact."""
    module = _load_gate()
    root = tmp_path / "proj"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "a.py").write_text("X = 1\n", encoding="utf-8")
    with pytest.raises(module.Unknown) as caught:
        module.discover(root)          # scripts/ is absent
    assert "declared scan root" in str(caught.value)


def test_the_gate_registers_its_negative_control():
    text = GATE.read_text(encoding="utf-8")
    assert "#: NEGATIVE-CONTROL: controls/bandit-audit" in text
    assert (CONTROL / "control.json").is_file()


def test_the_detect_signal_cannot_match_a_clean_run(tmp_path):
    """The #946 property, asserted for this control's own regex.

    A pattern matching the gate's clean line identifies a clean run as readily
    as a finding. The harness checks this against the known-GOOD case's real
    output; this checks it against the real gate's real clean line, which is a
    different string from any fixture's.
    """
    manifest = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))
    signal = re.compile(manifest["detect_signal"], re.MULTILINE)
    assert not signal.search("")
    capture = _capture(tmp_path, files=["lib/a.py"])
    proc = _run("--from-capture", str(capture), "--allow-file", str(_allow(tmp_path, "")))
    assert proc.returncode == 0
    assert not signal.search(proc.stdout + proc.stderr)


@requires_bandit
def test_the_repositorys_own_tree_passes_the_gate():
    """The live lane, end to end, on the real tree.

    Not a tautology beside the fixtures: it is the only assertion that the
    declared roots resolve, that the walk finds files, that bandit runs over
    them, and that `.bandit-audit-allow` as committed actually accounts for what
    this tree reports. A stale committed line fails here.
    """
    proc = _run()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "bandit-audit: ok" in proc.stdout
    assert "source=walk" in proc.stdout


@requires_bandit
def test_the_selftest_reports_on_the_bad_fixture_and_not_the_clean_one():
    proc = _run("--selftest")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BANDIT-SELFTEST: ok" in proc.stdout
