"""Tests for scripts/check-ci-coverage.py - the CI-disposition gate (issue #1146).

`make verify` chained 27 gates and the pipeline ran 16. Nothing in the tree
recorded which 11 were missing, so #1144 merged green over a gate that was in
`verify` and not in CI, and `main` was red from the moment it landed.

The gate's five DISCRIMINATIONS are held by `controls/ci-coverage`, whose cases
are committed trees the negative-control register drives on every run. What is
held HERE is the half the register cannot express: the two EMPTY-POPULATION
refusals.

WHY THEY ARE HERE AND NOT THERE. `expect: UNKNOWN` routes a case to the
register's anchor-SANITY loop, where the anchor must AGREE with the gate. This
gate's anchor is blind precisely because it never derives the prerequisite
population - so an anchor that refused an empty one would have to derive it,
and would then catch `bad-undeclared-gate` and stop being an anchor at all. The
two requirements are mutually exclusive by construction, which is a property of
the register's contract (stated beside `sanity_cases` in
`check-negative-controls.py`) rather than a gap in this control. ADR 0008's
bound is satisfied the other way: a red here is a red `make test`, a red `make
verify` and a red CI `validate`.

The real-repo tests at the bottom are the ones that would catch THIS repository
regressing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-ci-coverage.py"
CASES = ROOT / "controls" / "ci-coverage" / "cases"
FIXTURES = ROOT / "tests" / "fixtures" / "ci-coverage"
MAKEFILE = ROOT / "Makefile"
WOODPECKER = ROOT / ".woodpecker.yml"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


# --------------------------------------------------------------------------
# The empty populations. Both must be UNKNOWN, and never a confident `ok`.
# --------------------------------------------------------------------------


def test_a_makefile_with_no_verify_target_is_unknown_and_never_ok() -> None:
    """An underivable prerequisite population exits 2 and names itself.

    This is the gate's own defect class turned on itself: #1146 exists because
    an ABSENCE was read as fine, and a derivation returning zero members is an
    absence. A reformatted `verify:` rule reaches this branch with nobody
    having edited the gate.
    """
    tree = FIXTURES / "no-verify-target"
    # PRECONDITION: the fixture really does construct the absence under test.
    # Without this the test still fails if someone restores a `verify:` rule,
    # but it fails opaquely - on an exit code, with no sentence saying why.
    assert not re.search(r"^verify:", (tree / "Makefile").read_text(), re.MULTILINE), (
        "fixture must have no `verify:` rule"
    )

    result = run(tree)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "check-ci-coverage: UNKNOWN" in result.stdout
    assert "0 prerequisites" in result.stdout
    assert "ok -" not in result.stdout


def test_a_pipeline_in_the_list_form_is_unknown_and_never_ok() -> None:
    """The second population empties by its OWN mechanism, so it has its own test.

    A guard proven on the Makefile side is no evidence about the pipeline side.
    Converting `.woodpecker.yml` to YAML's list form is a legitimate edit that
    this reader does not speak, and reading zero steps out of a pipeline with
    two must not license a green.
    """
    tree = FIXTURES / "steps-in-list-form"
    text = (tree / ".woodpecker.yml").read_text()
    # PRECONDITION, both halves: the list form is present AND the mapping form
    # this reader speaks is absent. Asserting only the first would pass over a
    # fixture carrying both.
    assert "- name: alpha-check" in text, "fixture must use the list form"
    assert not re.search(r"^  alpha-check:", text, re.MULTILINE), (
        "fixture must not also carry the mapping form"
    )

    result = run(tree)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "check-ci-coverage: UNKNOWN" in result.stdout
    assert "0 steps" in result.stdout
    assert "ok -" not in result.stdout


def test_an_absent_woodpecker_file_is_unknown_and_never_ok(tmp_path: Path) -> None:
    """A missing pipeline is a population that could not be derived, not an empty one."""
    (tmp_path / "Makefile").write_text(
        "## verify-coverage: gate alpha-check - runs anywhere; ci: runs alpha-check\n"
        "alpha-check:\n"
        "\t@true\n"
        "\n"
        "## verify-coverage: gate verify - the aggregate itself\n"
        "verify: alpha-check\n"
        "\t@true\n"
    )
    assert not (tmp_path / ".woodpecker.yml").exists()

    result = run(tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert ".woodpecker.yml is missing" in result.stdout


# --------------------------------------------------------------------------
# The grammar. Strict shape, open vocabulary.
# --------------------------------------------------------------------------


def test_an_unrecognised_exclusion_reason_is_accepted() -> None:
    """The vocabulary is open, and this is the half a strict parser could break.

    Nobody can enumerate in advance why a gate cannot run in a slim container,
    so the reason is free text. The bad cases prove the SHAPE is strict; this
    proves the strictness did not swallow the openness with it.
    """
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("check_ci_coverage", GATE)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.parse_declaration(
        "a gate; ci: excluded it needs a live GPU, which no runner has"
    ) == ("excluded", "it needs a live GPU, which no runner has")
    assert module.parse_declaration("a gate; ci: runs validate") == ("runs", "validate")
    assert module.parse_declaration("a gate with no clause at all") is None
    for malformed in ("ci: run validate", "ci: excluded", "ci: runs", "ci: skipped x"):
        kind, _ = module.parse_declaration(f"a gate; {malformed}")
        assert kind == "malformed", malformed


# --------------------------------------------------------------------------
# The real repository.
# --------------------------------------------------------------------------


def test_the_real_repository_dispositions_every_verify_prerequisite() -> None:
    result = run(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check-ci-coverage: ok" in result.stdout


def test_the_ok_line_states_the_populations_it_rests_on() -> None:
    """A green is only worth the enumeration behind it, so the counts are printed.

    Without them a reader cannot tell a repository with 27 dispositioned gates
    from one where the derivation came back with three.
    """
    result = run(ROOT)
    assert re.search(
        r"check-ci-coverage: ok - \d+ `verify` prerequisite\(s\) dispositioned "
        r"against \d+ pipeline step\(s\): \d+ run in CI, \d+ excluded",
        result.stdout,
    ), result.stdout
    assert re.search(r"^CI_COVERAGE_PREREQUISITES: \d+$", result.stdout, re.MULTILINE)
    assert re.search(r"^CI_COVERAGE_STEPS: \d+$", result.stdout, re.MULTILINE)


def test_verify_runs_this_gate_as_a_prerequisite() -> None:
    """The gate is a member of its own population, which is the point.

    A check that audits "does the pipeline run what `verify` runs" and is
    itself outside `verify` is the class it audits.
    """
    # Continuations joined FIRST. A non-greedy read to the recipe line stops at
    # the first `\t`, which is where the SECOND prerequisite line begins - so the
    # naive regex sees eight of twenty-eight members and is confidently wrong
    # about the other twenty. Read independently of the gate's own parser on
    # purpose: a membership claim checked with the parser under test would agree
    # with itself.
    text = MAKEFILE.read_text().replace("\\\n", " ")
    match = re.search(r"^verify:([^\n]*)", text, re.MULTILINE)
    assert match is not None
    prerequisites = match.group(1).split()
    assert len(prerequisites) > 20, prerequisites
    assert "ci-coverage-check" in prerequisites, prerequisites


def test_the_pipeline_runs_this_gate_too() -> None:
    """Same argument one file over: a gate absent from CI is what #1146 is about."""
    assert re.search(r"^  ci-coverage-check:$", WOODPECKER.read_text(), re.MULTILINE)


def test_the_real_anchor_is_blind_to_every_committed_bad_case() -> None:
    """The anchor MISSES each bad tree, so a regression to it would be noticed.

    `check-negative-controls.py` asserts this on every battery run; this test
    is what makes it visible in a plain `pytest` run, where the register is not
    driven and a silently-sighted anchor would look like nothing at all.
    """
    anchor = ROOT / "controls" / "ci-coverage" / "anchors" / "constructed-count-the-declarations.py"
    bad = sorted(p for p in CASES.iterdir() if p.name.startswith("bad-"))
    assert bad, "no committed bad cases"
    for case in bad:
        result = subprocess.run(
            [sys.executable, str(anchor), "--root", str(case)],
            capture_output=True, text=True, timeout=120, check=False,
        )
        assert result.returncode == 0, f"{case.name}: anchor exited {result.returncode}"
        assert "UNDECLARED" not in result.stdout, case.name
        assert "MALFORMED" not in result.stdout, case.name
        assert "ABSENT-STEP" not in result.stdout, case.name
        # And the real gate CATCHES each one - without this the pair proves the
        # anchor is quiet, not that the gate is not.
        assert run(case).returncode == 1, case.name
