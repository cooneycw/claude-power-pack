"""The dependency audit gate, and the states its negative control cannot reach (issue #961).

`controls/dependency-audit` covers DISCRIMINATION - a finding, a stale
suppression, a leaking deferral, and a fully accounted tree - and
`tests/test_negative_controls.py` drives that register. This file covers what a
registered control structurally cannot:

  * the UNKNOWN states. `check-negative-controls.py` scores a case GOOD or BAD
    and has no third expectation, deliberately ("I expect this gate to fall
    over" is not a property anyone should be able to register). But UNKNOWN is
    the verdict issue #961 asks to be made distinguishable from clean, so the
    assertions that it never prints as a pass live here.

  * the WIRING invariants. Whether the CI step runs the live positive control
    BEFORE the audit, and whether `dep-audit` has quietly been added to
    `make verify`, are facts about files rather than about a gate's judgement.

  * the REGRESSION on the comment stripper. `line.split("#")[0]` ate the `#922`
    off the first record ever written against this gate, because `#` opens a
    comment and also opens every issue reference. Run against that parser,
    `test_an_issue_reference_survives_the_comment_stripper` fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "dependency-audit.py"
CASES = REPO / "controls" / "dependency-audit" / "cases"
LIVE = REPO / "controls" / "dependency-audit" / "live"
ALLOW = REPO / ".dependency-audit-allow"

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2


def run(*args: str) -> subprocess.CompletedProcess:
    """The gate, under THIS interpreter, with stdout and stderr both captured.

    `sys.executable` rather than a literal `"python3"`: the gate's own
    control.json uses `python3` because that manifest is read inside the CI
    image, but a test that names a bare binary is what
    `check-test-binary-guards.py` exists to flag.
    """
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True, text=True, timeout=120, check=False, cwd=REPO,
    )


def run_case(name: str) -> subprocess.CompletedProcess:
    case = CASES / name
    return run("--from-capture", str(case / "audit-capture.json"),
               "--allow-file", str(case / ".dependency-audit-allow"))


def both(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + proc.stderr


def capture_file(tmp_path: Path, files: list[dict]) -> Path:
    path = tmp_path / "audit-capture.json"
    path.write_text(json.dumps({"schema": 1, "files": files}), encoding="utf-8")
    return path


def allow_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".dependency-audit-allow"
    path.write_text(text, encoding="utf-8")
    return path


def dep(name: str, version: str, *advisories: str) -> dict:
    return {"name": name, "version": version,
            "vulns": [{"id": a} for a in advisories]}


def one_file(deps: list[dict], path: str = "uv.lock") -> list[dict]:
    return [{"path": path, "report": {"dependencies": deps}}]


# --------------------------------------------------------------------------- #
# Unknown is not clean - the distinction issue #961 asks to be made explicit
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "name, files, allow",
    [
        ("a zero-file population", [], "advisory uv.lock x 1.0 ID #1\n"),
        ("an unparseable report", [{"path": "uv.lock", "report": {"no_dependencies": []}}], ""),
        ("a report that is not an object", [{"path": "uv.lock", "report": "clean"}], ""),
        ("a finding with no advisory id",
         one_file([{"name": "x", "version": "1.0", "vulns": [{"description": "..."}]}]), ""),
    ],
)
def test_a_run_that_could_not_look_is_unknown_and_never_prints_as_clean(
    tmp_path: Path, name: str, files: list[dict], allow: str
) -> None:
    """The whole point of the two markers: they answer different questions.

    `dependency-audit: ok` is a statement about the dependency set. `UNKNOWN` is
    a statement about this RUN. Issue #961 asks for them to be distinguishable
    in the output, and the way that fails in practice is not a missing word - it
    is a gate that prints its clean summary AND a warning, leaving whoever greps
    for `ok` with a pass. So the assertion is two-sided: UNKNOWN is present, and
    the clean sentence is absent.
    """
    proc = run("--from-capture", str(capture_file(tmp_path, files)),
               "--allow-file", str(allow_file(tmp_path, allow)))
    output = both(proc)
    assert proc.returncode == EXIT_UNKNOWN, f"{name}: expected exit 2, got {proc.returncode}: {output}"
    assert "DEP-AUDIT-UNKNOWN: " in output, f"{name}: no UNKNOWN marker: {output}"
    assert "dependency-audit: ok" not in output, f"{name}: printed a clean verdict as well: {output}"


def test_an_unreadable_allowlist_is_unknown_rather_than_an_empty_one(tmp_path: Path) -> None:
    """An allowlist that could not be read leaves every disposition undecided.

    Defaulting to "nothing is suppressed" reddens a correctly accounted tree;
    defaulting the other way hides everything. Neither is an answer, so the
    honest verdict is that this run could not look.
    """
    proc = run("--from-capture", str(capture_file(tmp_path, one_file([dep("x", "1.0", "ID-1")]))),
               "--allow-file", str(allow_file(tmp_path, "this is not a record\n")))
    assert proc.returncode == EXIT_UNKNOWN
    assert "DEP-AUDIT-UNKNOWN: " in both(proc)


def test_an_absent_allowlist_is_an_empty_residual_not_unknown(tmp_path: Path) -> None:
    """The mirror of the test above, and it is the half that keeps it honest.

    A tree with no accepted residual is an ordinary, correct state - most
    repositories adopting this gate have no allowlist at all. If absence were
    UNKNOWN the gate could never report clean anywhere, which is the failure
    mode "unknown is not a pass" turns into when it is applied without a floor.
    """
    proc = run("--from-capture", str(capture_file(tmp_path, one_file([dep("x", "1.0")]))),
               "--allow-file", str(tmp_path / "absent"))
    assert proc.returncode == EXIT_OK, both(proc)
    assert "dependency-audit: ok" in both(proc)


# --------------------------------------------------------------------------- #
# The denominator, on every run
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("case", ["good-all-accounted", "bad-new-advisory"])
def test_the_summary_states_its_denominator_on_a_clean_run_as_well_as_a_dirty_one(case: str) -> None:
    """`0 findings` means nothing beside an unstated number of files (ADR 0008)."""
    output = both(run_case(case))
    assert "file(s) examined" in output, output
    assert "package(s)" in output, output
    assert "source=capture" in output, output


def test_the_derivation_is_named_so_a_replay_never_reads_as_a_walk(tmp_path: Path) -> None:
    """A capture verdict is about reports someone recorded; a walk verdict is about the tree now."""
    proc = run("--from-capture", str(capture_file(tmp_path, one_file([dep("x", "1.0")]))),
               "--allow-file", str(tmp_path / "absent"))
    assert "source=capture" in both(proc)
    assert "source=walk" not in both(proc)


# --------------------------------------------------------------------------- #
# The allowlist, at the granularity that makes it a guard rather than a blindfold
# --------------------------------------------------------------------------- #

def test_a_suppression_is_pinned_to_its_version_so_a_bump_resurfaces_the_question(tmp_path: Path) -> None:
    """The negative-membership half: what the entry must NOT cover.

    An allowlist keyed on package alone would swallow the finding on every
    future version of that package, including advisories nobody has ever seen -
    which is a permanent exemption wearing the name of a tracked residual.
    """
    proc = run("--from-capture", str(capture_file(tmp_path, one_file([dep("pygments", "2.20.0", "PYSEC-2026-2987")]))),
               "--allow-file", str(allow_file(tmp_path, "advisory uv.lock pygments 2.19.2 PYSEC-2026-2987 #922\n")))
    output = both(proc)
    assert proc.returncode == EXIT_FINDING, output
    assert "DEP-AUDIT-FINDING: uv.lock pygments 2.20.0 PYSEC-2026-2987" in output, output
    assert "DEP-AUDIT-STALE: " in output, "the entry now matches nothing and must say so: " + output


def test_a_suppression_is_pinned_to_its_advisory_so_a_new_one_is_not_inherited(tmp_path: Path) -> None:
    """Same package, same version, a DIFFERENT advisory - reported, not inherited."""
    findings = one_file([dep("pytest", "9.0.2", "PYSEC-2026-1845", "PYSEC-9999-1")])
    proc = run("--from-capture", str(capture_file(tmp_path, findings)),
               "--allow-file", str(allow_file(tmp_path, "advisory uv.lock pytest 9.0.2 PYSEC-2026-1845 #922\n")))
    output = both(proc)
    assert proc.returncode == EXIT_FINDING, output
    assert "PYSEC-9999-1" in output, output


def test_an_issue_reference_survives_the_comment_stripper(tmp_path: Path) -> None:
    """REGRESSION (issue #961). `#` opens a comment AND every issue reference.

    The first record ever written against this gate was
    `advisory uv.lock pygments 2.19.2 PYSEC-2026-2987 #922`, and
    `line.split("#", 1)[0]` turned it into a five-field line the parser refused -
    so the gate reported UNKNOWN on its own correct ledger. Run against that
    parser this test fails with exit 2; whole-line comments only is what makes
    it pass.
    """
    proc = run("--from-capture", str(capture_file(tmp_path, one_file([dep("pygments", "2.19.2", "PYSEC-2026-2987")]))),
               "--allow-file", str(allow_file(
                   tmp_path,
                   "# a whole-line comment, which IS stripped\n"
                   "advisory uv.lock pygments 2.19.2 PYSEC-2026-2987 #922\n")))
    output = both(proc)
    assert proc.returncode == EXIT_OK, output
    assert "#922" in output, "the issue the residual is pinned to must reach the reader: " + output


def test_a_trailing_comment_is_refused_rather_than_guessed_at(tmp_path: Path) -> None:
    """The cost of the rule above, asserted so nobody re-adds the heuristic quietly."""
    proc = run("--from-capture", str(capture_file(tmp_path, one_file([dep("x", "1.0")]))),
               "--allow-file", str(allow_file(tmp_path, "deferred uv.lock #1 # and a note\n")))
    assert proc.returncode == EXIT_UNKNOWN, both(proc)


def test_the_same_advisory_from_two_feeds_is_counted_once(tmp_path: Path) -> None:
    """pip-audit reports one advisory per vulnerability SOURCE it resolved.

    Measured 2026-09-16: `pyyaml==5.1` came back as "6 known vulnerabilities"
    for 3 distinct ids. Counting the duplicates inflates every number this gate
    prints and makes a one-line suppression look like it covered less than it
    does.
    """
    proc = run("--from-capture", str(capture_file(tmp_path, one_file([dep("x", "1.0", "ID-1", "ID-1", "ID-2")]))),
               "--allow-file", str(tmp_path / "absent"))
    output = both(proc)
    assert "2 gating finding(s)" in output, output


# --------------------------------------------------------------------------- #
# Wiring - facts about files, which no gate's judgement covers
# --------------------------------------------------------------------------- #

def test_the_ci_step_proves_the_scan_can_see_before_it_reports_clean() -> None:
    """The order is the guarantee, not the presence of both commands.

    A `--selftest` that ran AFTER the audit would still be green while the audit
    it was meant to vouch for had already issued a clean verdict from a scan
    nothing had checked.
    """
    pipeline = yaml.safe_load((REPO / ".woodpecker.yml").read_text(encoding="utf-8"))
    commands = pipeline["steps"]["dependency-audit"]["commands"]
    selftest = [i for i, c in enumerate(commands) if "--selftest" in c]
    audit = [i for i, c in enumerate(commands) if "dependency-audit.py" in c and "--selftest" not in c]
    assert selftest and audit, commands
    assert max(selftest) < min(audit), f"the selftest must precede the audit: {commands}"
    assert "failure" not in pipeline["steps"]["dependency-audit"], (
        "this gate is hard by decision (issue #961); `failure: ignore` would make it a report"
    )


def test_dep_audit_stays_out_of_make_verify() -> None:
    """A TRIPWIRE on a deliberate exclusion, not a claim that it should never move.

    `dep-audit` needs the network and `verify` is the gate a developer runs
    offline, so the exclusion is a decision with a recorded reversal trigger in
    the Makefile. This cannot know what `verify` SHOULD contain; it fails loudly
    when the decision changes silently, so whoever changes it reads the trigger
    first.
    """
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    body = makefile.split("\nverify:", 1)[1].split("\n\n", 1)[0]
    assert "dep-audit" not in body, (
        "dep-audit was added to `make verify`, which now requires the network. "
        "Read the reversal trigger above the target before removing this test."
    )


def test_the_live_selftest_fixtures_are_present_and_exactly_pinned() -> None:
    """`--selftest` is the only thing covering that pip-audit is invoked at all.

    An absent or loosely pinned fixture makes it prove nothing: `pyyaml>=5.1`
    resolves to a patched release and the known-bad half stops being known-bad.
    """
    for name in ("bad-known-advisory", "good-clean"):
        path = LIVE / name / "requirements.txt"
        assert path.is_file(), f"selftest fixture missing: {path}"
        pins = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")]
        assert pins, f"{path} pins nothing"
        for pin in pins:
            assert "==" in pin, f"{path} must pin exactly, got {pin!r}"


def test_the_repository_residual_names_an_issue_on_every_line() -> None:
    """A suppression with no issue is an exemption. The gate's own ledger, checked."""
    records = [ln.strip() for ln in ALLOW.read_text(encoding="utf-8").splitlines()
               if ln.strip() and not ln.strip().startswith("#")]
    assert records, ".dependency-audit-allow has no records; this test would be vacuous"
    for record in records:
        fields = record.split()
        assert fields[0] in {"advisory", "deferred"}, record
        assert fields[-1].startswith("#") and fields[-1][1:].isdigit(), (
            f"every residual line must end in the issue tracking it: {record!r}"
        )
