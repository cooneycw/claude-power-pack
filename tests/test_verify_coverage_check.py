"""Tests for scripts/verify-coverage-check.py - the checker accounting gate (issue #1028).

Four checkers were found at once with no path from a change to a verdict anyone
consumes. The remedy under test is not four wirings: it is a gate that refuses
to let a checker exist unaccounted, and a closing report that says what `make
verify` did not examine.

The real-repo tests at the bottom are the ones that would catch this repository
regressing. The fixture tests above them are about the gate's rules.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "verify-coverage-check.py"
CASES = ROOT / "controls" / "verify-coverage" / "cases"
ANCHOR = (
    ROOT
    / "controls"
    / "verify-coverage"
    / "anchors"
    / "constructed-verify-exists-only-verify-coverage-check.py"
)


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(root), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A minimal accounted tree: one gate, one excluded check, one writer."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".claude").mkdir()
    for name in ("alpha-check.sh", "beta-check.sh", "render.sh"):
        (tmp_path / "scripts" / name).write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / ".claude" / "verify-coverage.json").write_text('{"scripts": {}}\n')
    (tmp_path / "Makefile").write_text(
        "## verify-coverage: gate verify - the aggregate itself\n"
        "verify: alpha-check\n"
        "\t@true\n"
        "\n"
        "## verify-coverage: gate alpha-check - examined by this gate\n"
        "alpha-check:\n"
        "\t@sh scripts/alpha-check.sh\n"
        "\n"
        "## verify-coverage: excluded beta-check - needs a binary this tree may not have\n"
        "beta-check:\n"
        "\t@sh scripts/beta-check.sh --check\n"
        "\n"
        "## verify-coverage: utility render - writes a file; it issues no verdict\n"
        "render:\n"
        "\t@sh scripts/render.sh --write\n"
    )
    return tmp_path


def declare(tree: Path, **entries: dict) -> None:
    path = tree / ".claude" / "verify-coverage.json"
    doc = json.loads(path.read_text())
    doc["scripts"].update(entries)
    path.write_text(json.dumps(doc))


# --------------------------------------------------------------------------- #
# The rules
# --------------------------------------------------------------------------- #


def test_a_fully_accounted_tree_passes(tree: Path) -> None:
    result = run(tree)
    assert result.returncode == 0, result.stdout


def test_an_unclassified_target_is_unaccounted(tree: Path) -> None:
    (tree / "Makefile").write_text(
        (tree / "Makefile").read_text() + "\ngamma-check:\n\t@true\n"
    )
    result = run(tree)
    assert result.returncode == 1
    assert "UNACCOUNTED: target `gamma-check`" in result.stdout


def test_a_gate_class_verify_does_not_reach_is_misclassified(tree: Path) -> None:
    """ADR 0008 census row 40's own failure: a sub-gate dropped from the list.

    Every directive is present and well-formed here, so a gate that only looked
    for MISSING directives calls this tree clean - which is how a wiring that
    was correct and then quietly stopped being would survive.
    """
    text = (tree / "Makefile").read_text().replace(
        "## verify-coverage: excluded beta-check", "## verify-coverage: gate beta-check"
    )
    (tree / "Makefile").write_text(text)
    result = run(tree)
    assert result.returncode == 1
    assert "MISCLASSIFIED: `beta-check` is declared `gate`" in result.stdout


def test_a_verify_prerequisite_declared_excluded_is_misclassified(tree: Path) -> None:
    """The other direction: the report would name a check that runs every time."""
    text = (tree / "Makefile").read_text().replace(
        "## verify-coverage: gate alpha-check",
        "## verify-coverage: excluded alpha-check",
    )
    (tree / "Makefile").write_text(text)
    result = run(tree)
    assert result.returncode == 1
    assert "DOES reach it" in result.stdout


def test_a_checker_parked_as_utility_is_refused(tree: Path) -> None:
    text = (tree / "Makefile").read_text().replace(
        "## verify-coverage: excluded beta-check - needs a binary this tree may not have",
        "## verify-coverage: utility beta-check - not really a check, honest",
    )
    (tree / "Makefile").write_text(text)
    result = run(tree)
    assert result.returncode == 1
    assert "parked where the closing report will never name it" in result.stdout


def test_the_utility_tripwire_reads_flags_and_not_the_script_name(tmp_path: Path) -> None:
    """A filename is not what a recipe DOES (issue #1028).

    `dependency-audit.py --capture` writes a capture file. A name-matching
    tripwire would force it into the closing report as a check that `verify`
    skipped - a false entry in the one report this gate exists to keep honest,
    and the opposite error from the one the tripwire is for.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".claude").mkdir()
    (tmp_path / "scripts" / "dependency-audit.py").write_text("#!/usr/bin/env python3\n")
    (tmp_path / ".claude" / "verify-coverage.json").write_text('{"scripts": {}}\n')
    (tmp_path / "Makefile").write_text(
        "## verify-coverage: gate verify - the aggregate\n"
        "verify:\n"
        "\t@true\n"
        "\n"
        "## verify-coverage: utility capture - records raw reports; no verdict\n"
        "capture:\n"
        "\t@python3 scripts/dependency-audit.py --capture dependency-audit-capture.json\n"
    )
    result = run(tmp_path)
    assert result.returncode == 0, result.stdout


def test_a_script_no_surface_invokes_is_unaccounted(tree: Path) -> None:
    """THE MECHANISM FOR NEW CHECKERS.

    The Makefile here is fully and correctly classified, so every target-side
    rule passes. Only this one can say that a checker was added and wired
    nowhere - the state 56 of this repository's 89 scripts are in, and the state
    all four #1028 subjects were found in.
    """
    (tree / "scripts" / "delta-check.sh").write_text("#!/bin/sh\nexit 0\n")
    result = run(tree)
    assert result.returncode == 1
    assert "UNACCOUNTED: `scripts/delta-check.sh`" in result.stdout


def test_a_declared_consumer_that_does_not_exist_is_stale(tree: Path) -> None:
    (tree / "scripts" / "delta-check.sh").write_text("#!/bin/sh\nexit 0\n")
    declare(
        tree,
        **{
            "delta-check.sh": {
                "class": "runtime",
                "consumer": "commands/nowhere.md",
                "reason": "x",
            }
        },
    )
    result = run(tree)
    assert result.returncode == 1
    assert "STALE:" in result.stdout and "does not exist" in result.stdout


def test_a_consumer_that_stops_mentioning_the_script_is_stale(tree: Path) -> None:
    """The reason `consumer` is a path and not a sentence.

    A justification rots by its subject being renamed or removed elsewhere, and
    the sentence keeps reading true. Opening the named file and looking for the
    script's own name is what turns the entry into a claim that can be false.
    """
    (tree / "scripts" / "delta-check.sh").write_text("#!/bin/sh\nexit 0\n")
    (tree / "consumer.md").write_text("this document no longer runs anything\n")
    declare(
        tree,
        **{
            "delta-check.sh": {
                "class": "runtime",
                "consumer": "consumer.md",
                "reason": "x",
            }
        },
    )
    result = run(tree)
    assert result.returncode == 1
    assert "does not mention it" in result.stdout


def test_a_declaration_for_a_script_a_target_invokes_is_stale(tree: Path) -> None:
    """The derived class is the truth; the entry can only rot against it."""
    declare(
        tree,
        **{"alpha-check.sh": {"class": "not-a-checker", "reason": "x"}},
    )
    result = run(tree)
    assert result.returncode == 1
    assert "already invokes it" in result.stdout


def test_a_census_instrument_cannot_be_filed_as_not_a_checker(tree: Path) -> None:
    """The cross-check on the one class the closing report never mentions.

    `not-a-checker` is where a checker would go to disappear, so it is checked
    against ADR 0008's census rather than trusted - using that gate's own
    extraction rule, imported rather than re-implemented.
    """
    (tree / "scripts" / "delta-check.sh").write_text("#!/bin/sh\nexit 0\n")
    census = tree / "docs" / "decisions"
    census.mkdir(parents=True)
    (census / "0008-instrument-negative-control-bound.md").write_text(
        "| # | instrument | verdict | consumed by | class |\n"
        "|---|---|---|---|---|\n"
        "| 1 | `delta-check.sh` | exit code | a reader | G |\n"
    )
    (tree / "scripts" / "instrument-census-check.py").write_text(
        (ROOT / "scripts" / "instrument-census-check.py").read_text()
    )
    declare(tree, **{"delta-check.sh": {"class": "not-a-checker", "reason": "x"}})
    result = run(tree)
    assert result.returncode == 1
    assert "enumerates it as an instrument" in result.stdout


def test_an_unreadable_census_reports_unread_and_never_empty(tree: Path) -> None:
    """Unscanned must not read as clean.

    This tree has no census, so the `not-a-checker` cross-check did not run. A
    silent pass would make "nothing was parked there" and "nobody looked" print
    the same line, which is the blind-instrument shape the whole gate is about.
    """
    result = run(tree)
    assert "VERIFY_COVERAGE_CENSUS: unread" in result.stdout


def test_the_report_is_not_printed_beside_a_finding(tree: Path) -> None:
    """A summary is only worth the enumeration behind it."""
    (tree / "scripts" / "delta-check.sh").write_text("#!/bin/sh\nexit 0\n")
    result = run(tree, "--report")
    assert result.returncode == 1
    assert "what this run did NOT examine" not in result.stdout


def test_the_report_names_the_excluded_check_and_its_reason(tree: Path) -> None:
    result = run(tree, "--report")
    assert result.returncode == 0, result.stdout
    assert "make beta-check - needs a binary this tree may not have" in result.stdout


def test_a_comment_naming_a_script_is_not_a_ci_step(tmp_path: Path) -> None:
    """The first cut of this gate got this backwards, and it matters (#1028).

    Greping the whole pipeline reported four scripts as run-only-by-CI that its
    comments merely DISCUSS, and every one was then counted as examined. That is
    the wrong direction for this gate to be wrong in: it makes an unrun checker
    look covered, which is the exact inference the issue is about, produced by
    the fix for it.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".claude").mkdir()
    (tmp_path / "scripts" / "discussed.py").write_text("#!/usr/bin/env python3\n")
    (tmp_path / ".claude" / "verify-coverage.json").write_text('{"scripts": {}}\n')
    (tmp_path / "Makefile").write_text(
        "## verify-coverage: gate verify - the aggregate\nverify:\n\t@true\n"
    )
    (tmp_path / ".woodpecker.yml").write_text(
        "steps:\n"
        "  # scripts/discussed.py is a registered control, which is why this\n"
        "  # step stages its binary. Talking about it is not running it.\n"
        "  stage:\n"
        "    commands:\n"
        "      - echo staging\n"
    )
    result = run(tmp_path)
    assert result.returncode == 1
    assert "UNACCOUNTED: `scripts/discussed.py`" in result.stdout


# --------------------------------------------------------------------------- #
# The real repository
# --------------------------------------------------------------------------- #


def test_the_real_repository_is_fully_accounted() -> None:
    result = run(ROOT)
    assert result.returncode == 0, result.stdout


def test_the_real_report_names_control_health_as_unexamined() -> None:
    """Issue #1028 item 3's acceptance, in the form the issue offers.

    The battery is deliberately not a `verify` prerequisite - it needs gitleaks
    and jq, and a host without either would fail the gate for an environment
    reason. What the issue asks instead is that the gap be STATED rather than
    silent, so this asserts the statement exists rather than that the wiring
    does.
    """
    result = run(ROOT, "--report")
    assert result.returncode == 0, result.stdout
    assert "what this run did NOT examine" in result.stdout
    assert "make negative-controls" in result.stdout


def test_verify_runs_this_gate_as_a_prerequisite_and_as_its_report() -> None:
    """Both wirings, asserted separately, because they fail separately.

    As a prerequisite it fails early beside the other gates; as the recipe it
    prints the closing report. Losing either is silent - the other keeps
    `make verify` green.
    """
    makefile = (ROOT / "Makefile").read_text()
    verify = makefile.split("\nverify:", 1)[1].split("\n\n", 1)[0]
    assert "verify-coverage-check" in verify, "dropped from verify's prerequisites"
    assert "verify-coverage-check.py --report" in verify, "the closing report is gone"


def test_the_real_anchor_is_blind_to_every_committed_bad_case() -> None:
    """The discrimination itself, measured directly rather than through the harness.

    One tree, both gates, opposite verdicts - four times over. A control whose
    anchor catches the known-bad input proves nothing about the real gate.
    """
    for case in sorted(p for p in CASES.iterdir() if p.name.startswith("bad-")):
        current = run(case)
        historical = subprocess.run(
            [sys.executable, str(ANCHOR), "--root", str(case)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert current.returncode == 1, f"the real gate missed {case.name}"
        assert historical.returncode == 0, f"the anchor CAUGHT {case.name}, so it is not blind"
