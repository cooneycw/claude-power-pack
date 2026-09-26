"""Tests for `scripts/instrument-census-check.py` (issue #1060).

WHAT THIS MODULE IS ABOUT. The gate answers one question - is every file in
`scripts/` accounted for by ADR 0008, as a census row or as an exclusion - and
the interesting failures are all in the EXTRACTION, not in the comparison. Three
extraction rules were measured against the real document before one was chosen,
and two of them look right until they are counted. So most of what follows pins
the rule rather than the plumbing.

THE REAL-TREE TEST IS THE DRIFT GATE. `test_the_real_census_accounts_for_the_real_tree`
is the one that goes red when someone adds an instrument and does not enumerate
it, which is the whole point of the issue. Everything else exists so that a green
from it means something.
"""

from __future__ import annotations

import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "instrument-census-check.py"
_spec = spec_from_file_location("instrument_census_check", _script_path)
icc = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(icc)  # type: ignore[union-attr]
sys.modules["instrument_census_check"] = icc

CASES = ROOT / "controls" / "instrument-census" / "cases"
ANCHOR = (
    ROOT
    / "controls"
    / "instrument-census"
    / "anchors"
    / "constructed-loose-tokens-forward-only-instrument-census-check.py"
)

HEAD = (
    "# fixture\n\n## The enumeration\n\n"
    "| # | instrument | verdict contract | consumed by | class |\n"
    "|---|---|---|---|---|\n"
)
EXCL = "\n### Excluded, with the reason\n\n| population | reason |\n|---|---|\n"


def _adr(rows: str = "", exclusions: str = "", externals: str = "", tail: str = "") -> str:
    """A miniature ADR with the real document's shape."""
    decl = f"\n<!-- instrument-census: external-subjects: {externals} -->\n" if externals else "\n"
    return HEAD + rows + EXCL + exclusions + decl + tail


def _tree(tmp_path: Path, scripts: list[str], adr: str) -> Path:
    """A miniature repo: named files under scripts/, and the census ADR."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "docs" / "decisions").mkdir(parents=True)
    for name in scripts:
        (root / "scripts" / name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / icc.ADR_REL).write_text(adr, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Real-repo pins - this is the drift gate
# ---------------------------------------------------------------------------


def test_the_real_census_accounts_for_the_real_tree():
    assert icc.main(["check", "--root", str(ROOT)]) == 0


_cnc_spec = spec_from_file_location("check_negative_controls", ROOT / "scripts" / "check-negative-controls.py")
cnc = module_from_spec(_cnc_spec)  # type: ignore[arg-type]
sys.modules["check_negative_controls"] = cnc  # dataclasses resolve via sys.modules
_cnc_spec.loader.exec_module(cnc)  # type: ignore[union-attr]


def test_the_two_readers_of_the_census_count_the_same_rows():
    """The battery's DENOMINATOR and this gate's POPULATION must be one document.

    `check-negative-controls.py` prints `N of <rows>`; this gate checks which
    files those rows account for. They are separate parsers of one table, and a
    disagreement makes the coverage fraction and the accounting describe
    different documents with nothing to notice - the numerator and denominator
    already came from different places once (#1036).

    THIS TEST CALLS THE BATTERY'S OWN FUNCTION. The first cut re-implemented its
    regex here, which made the test a copy of the thing under test: it passed
    while the two parsers genuinely diverged, because both re-derived the same
    wrong answer. Found by the counter-model review (codex, gpt-6-astra), second
    pass.
    """
    text = (ROOT / icc.ADR_REL).read_text(encoding="utf-8")
    census = cnc.instrument_census(ROOT)
    assert len(icc.census_subjects(text)) == census.rows
    # #1036 turned this test's invariant into a RUNTIME one: the battery now
    # compares the two readers on every run and reports membership `unknown`
    # rather than computing it against a subject set that is provably not the
    # row set. This asserts the runtime check agrees with the test.
    assert not census.disagreement, census.disagreement


def test_a_fenced_or_commented_row_inflates_neither_reader(tmp_path):
    """REGRESSION (counter-model review, codex gpt-6-astra, second pass).

    An illustrative `| 1 | ... |` in the ADR's prose used to raise the battery's
    denominator while leaving the real census unchanged - `14 of 74` printed over
    a 73-row table, the #979 class arriving by a different route - and it split
    the two parsers so they counted different documents. FAILS on the pre-fix
    battery: measured, the raw regex counted 2 where the census holds 1.
    """
    adr_dir = tmp_path / "docs" / "decisions"
    adr_dir.mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    text = _adr(
        rows="| 1 | `alpha.sh` | v | c | G |\n",
        tail="\n```\n| 2 | `fenced.sh` | v | c | G |\n```\n\n<!--\n| 3 | `commented.sh` | v | c | G |\n-->\n",
    )
    (adr_dir / "0008-instrument-negative-control-bound.md").write_text(text, encoding="utf-8")
    census = cnc.instrument_census(tmp_path)
    assert census.rows == 1, f"the battery counted {census.rows} rows over a 1-row census"
    assert len(icc.census_subjects(text)) == 1


def test_every_declared_external_is_actually_absent_from_scripts():
    """The externals list NARROWS what is checked, so it must not narrow wrongly.

    A name declared external that is in fact a file under `scripts/` would
    silently exempt that file from the STALE direction forever. The declaration
    is for things with no file to carry a marker, never a way to quiet a real one.
    """
    text = (ROOT / icc.ADR_REL).read_text(encoding="utf-8")
    files = set(icc.script_files(ROOT))
    stems = {Path(name).stem for name in files}
    for name in sorted(icc.declared_externals(text)):
        assert name not in files and name not in stems, (
            f"`{name}` is declared an external subject but IS a file under scripts/; "
            "the declaration would exempt it from the stale check"
        )


# ---------------------------------------------------------------------------
# The committed control, driven directly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "expected"),
    [("bad-unaccounted", 1), ("bad-stale-subject", 1), ("good-accounted", 0)],
)
def test_the_committed_cases_discriminate(case, expected):
    assert icc.main(["check", "--root", str(CASES / case)]) == expected


@pytest.mark.parametrize(
    ("case", "signal"),
    [("bad-unaccounted", "UNACCOUNTED: "), ("bad-stale-subject", "STALE: ")],
)
def test_each_bad_case_fires_exactly_the_finding_it_names(case, signal, capsys):
    """A case that fails for a second, incidental reason is not evidence.

    The first cut of these fixtures left an exclusion row naming a file absent
    from the tree, so BOTH bad cases also reported a stray STALE. Each would then
    have scored BAD with the direction it exists to prove entirely removed.
    """
    icc.main(["check", "--root", str(CASES / case)])
    findings = [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith(("UNACCOUNTED: ", "STALE: "))
    ]
    assert len(findings) == 1, f"{case} fired {len(findings)} findings, expected 1: {findings}"
    assert findings[0].startswith(signal)


@pytest.mark.parametrize("case", ["bad-unaccounted", "bad-stale-subject"])
def test_the_anchor_is_blind_to_the_known_bad_input(case):
    """The registered anchor must MISS every bad case.

    An anchor that CATCHES a bad input proves the control is not load-bearing:
    the weaker check would have been enough, and the gate's green says nothing
    the cheaper instrument was not already saying.
    """
    proc = subprocess.run(
        [sys.executable, str(ANCHOR), "check", "--root", str(CASES / case)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"the anchor DETECTED {case}; it is not blind, so controls/instrument-census "
        f"does not demonstrate that the real gate is load-bearing.\n{proc.stdout}"
    )


def test_the_anchor_can_report_bad_at_all(tmp_path):
    """POSITIVE CONTROL FOR THE ANCHOR: prove it is weaker, not broken.

    Every other assertion about the anchor asks it to say GOOD. An anchor of
    `sys.exit(0)` satisfies all of them, and "blind, as required" would be printed
    over an instrument that cannot speak. So feed it the one input it IS supposed
    to catch - a script named NOWHERE in the document, which even the loose
    any-token rule cannot account for - and require a non-zero.
    """
    root = _tree(tmp_path, ["alpha-tool.sh", "nowhere-tool.sh"], _adr(rows="| 1 | `alpha-tool.sh` | v | c | G |\n"))
    proc = subprocess.run(
        [sys.executable, str(ANCHOR), "check", "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, (
        "the anchor reports GOOD on the input it exists to catch, so it is BROKEN "
        f"rather than blind and every 'missed the known-bad input' line is vacuous.\n{proc.stdout}"
    )


def test_the_anchor_agrees_with_the_gate_on_the_known_good_input():
    """Anchor sanity: it must differ from the gate ONLY in the blindness under test."""
    proc = subprocess.run(
        [sys.executable, str(ANCHOR), "check", "--root", str(CASES / "good-accounted")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"anchor disagrees on the known-good case:\n{proc.stdout}"


# ---------------------------------------------------------------------------
# The matching rule - first backticked token, instrument column
# ---------------------------------------------------------------------------


def test_a_census_row_accounts_for_its_script(tmp_path):
    root = _tree(tmp_path, ["alpha.sh"], _adr(rows="| 1 | `alpha.sh` | v | c | G |\n"))
    assert icc.main(["check", "--root", str(root)]) == 0


def test_a_subcommand_in_the_token_still_names_the_file(tmp_path):
    """`branch-protection.sh check` is a row about `branch-protection.sh`.

    A subcommand narrows WHICH verdict the row covers; it does not make the row
    about a different file. Seven real rows are written this way, and a
    whole-token compare reported every one of them unaccounted.
    """
    root = _tree(tmp_path, ["alpha.sh"], _adr(rows="| 1 | `alpha.sh check` | v | c | G |\n"))
    assert icc.main(["check", "--root", str(root)]) == 0


def test_an_incidental_second_mention_does_not_account_for_a_script(tmp_path):
    """Only the FIRST backticked token of the cell is the row's subject.

    Real row 34 is ```eli5-vendor.py` (manifest; `eli5-core-drift.sh` ...)`` - a
    row ABOUT the vendor script that mentions the drift script. Letting the
    second mention count would let a neighbour's prose stand in as an
    unenumerated instrument's accounting, which is the same rule
    `scripts-inventory-check` applies to headings.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        _adr(rows="| 1 | `alpha.sh` (see also `beta.sh`) | v | c | G |\n"),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


def test_a_name_in_the_verdict_column_does_not_account_for_a_script(tmp_path):
    """Column 2 is the instrument; columns 3 and 4 are its contract and consumers.

    Reading the whole row swept in 110 non-file subjects from those columns on the
    real document - `FLOW_CLAIM:`, `/flow:auto`, `ok`, `nothing` - and let a script
    named in a consumer cell read as enumerated.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        _adr(rows="| 1 | `alpha.sh` | `beta.sh` emits this | `beta.sh` reads it | G |\n"),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


def test_an_exclusion_cell_accounts_for_every_name_in_it(tmp_path):
    """The exclusions column is a POPULATION, not one subject.

    One real cell lists fourteen installers and generators. Applying the census's
    first-token-only rule there would silently un-exclude thirteen of them.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh", "gamma.sh"],
        _adr(
            rows="| 1 | `alpha.sh` | v | c | G |\n",
            exclusions="| `beta.sh`, `gamma.sh` | installers |\n",
        ),
    )
    assert icc.main(["check", "--root", str(root)]) == 0


def test_a_prose_mention_alone_does_not_account_for_a_script(tmp_path):
    """The failure the anchor embodies, pinned on the gate's side too."""
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        _adr(rows="| 1 | `alpha.sh` | v | c | G |\n", tail="\nProse mentioning `beta.sh` in passing.\n"),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


def test_a_stem_match_does_not_account_for_a_different_file(tmp_path):
    """REGRESSION (counter-model review, codex gpt-6-astra, this branch).

    The gate accepted a match on `Path(name).stem`, so `cpp-memory.py` was
    accounted for by the exclusion naming the DIFFERENT file `cpp-memory` - a
    new instrument shipping green under a neighbour's line, which is the exact
    failure this gate exists to stop. This test FAILS on the pre-fix code: with
    the stem fallback present the tree scores 0.

    `cpp-memory` is the real extensionless script the fallback existed for, and
    it must still be accounted for by its own name.
    """
    root = _tree(
        tmp_path,
        ["cpp-memory", "cpp-memory.py"],
        _adr(exclusions="| `cpp-memory` | a ledger; it emits no verdict |\n",
             rows="| 1 | `alpha.sh` | v | c | G |\n"),
    )
    (root / "scripts" / "alpha.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    assert icc.main(["check", "--root", str(root)]) == 1


def test_a_commented_out_census_row_does_not_account_for_a_script(tmp_path):
    """REGRESSION (counter-model review, codex gpt-6-astra, this branch).

    A row inside an HTML comment does not render in the census a reader sees, so
    reading it as live is a FALSE GREEN - comment out row 73 and the gate reports
    its subject accounted for while the table no longer enumerates it.

    THE COMMENT MUST SPAN LINES, and the first cut of this test did not. Written
    as `<!-- | 2 | `beta.sh` | ... | -->` on ONE line, the row no longer starts
    with a pipe, so `CENSUS_ROW_RE` never matched it with or without comment
    stripping: the test asserted the right outcome for the wrong reason and
    PASSED on the unfixed code, which makes it not a regression test whatever its
    name says. Verified after the rewrite: pre-fix exit 0, fixed exit 1.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        _adr(rows="| 1 | `alpha.sh` | v | c | G |\n<!--\n| 2 | `beta.sh` | v | c | G |\n-->\n"),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


def test_the_externals_declaration_survives_comment_stripping(tmp_path):
    """The declaration marker IS an HTML comment, so ORDER is load-bearing.

    Stripping comments before reading it deletes the externals list, and every
    third-party subject then reports STALE - a false red blocking every merge.
    The sibling gate paid for this ordering first (#1013).
    """
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        _adr(rows="| 1 | `alpha.sh` | v | c | G |\n| 2 | `ruff` | v | c | G |\n", externals="ruff"),
    )
    assert icc.main(["check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# The reverse direction
# ---------------------------------------------------------------------------


def test_a_row_for_a_deleted_script_is_caught(tmp_path):
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        _adr(rows="| 1 | `alpha.sh` | v | c | G |\n| 2 | `gone.sh` | v | c | G |\n"),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


def test_a_declared_external_subject_is_accepted(tmp_path):
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        _adr(rows="| 1 | `alpha.sh` | v | c | G |\n| 2 | `ruff` | v | c | G |\n", externals="ruff"),
    )
    assert icc.main(["check", "--root", str(root)]) == 0


def test_an_undeclared_external_subject_is_refused(tmp_path):
    """The list that narrows must fail LOUDLY when it is incomplete.

    A new third-party instrument is STALE until someone declares it. Tolerating
    an unknown non-file subject would make the list silently optional, and a list
    that narrows and fails quietly erases its own findings.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        _adr(rows="| 1 | `alpha.sh` | v | c | G |\n| 2 | `ruff` | v | c | G |\n"),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


# ---------------------------------------------------------------------------
# Refusals - an unexamined tree must never print a clean verdict
# ---------------------------------------------------------------------------


def test_an_empty_scripts_dir_refuses_instead_of_passing(tmp_path, capsys):
    root = _tree(tmp_path, [], _adr(rows="| 1 | `alpha.sh` | v | c | G |\n"))
    assert icc.main(["check", "--root", str(root)]) == 1
    assert "nothing compared" in capsys.readouterr().out


def test_a_census_that_parses_to_zero_rows_refuses_instead_of_reporting_everything(tmp_path, capsys):
    """A broken read must not present itself as 74 findings.

    With no rows parsed every file is UNACCOUNTED, which is the same output an
    author would get from genuinely enumerating nothing - and the wrong
    diagnosis entirely. `check-negative-controls.py` draws this exact
    distinction for its own denominator (#979).
    """
    root = _tree(tmp_path, ["alpha.sh"], _adr())
    assert icc.main(["check", "--root", str(root)]) == 1
    assert "parsed to 0 census rows" in capsys.readouterr().out


def test_a_missing_exclusions_section_refuses(tmp_path, capsys):
    """Without it every legitimately-excluded file reads UNACCOUNTED.

    That is a broken read, not a set of findings, and the two need opposite
    responses - which is why the section's presence is returned rather than
    inferred from an empty list.
    """
    root = _tree(tmp_path, ["alpha.sh"], HEAD + "| 1 | `alpha.sh` | v | c | G |\n")
    assert icc.main(["check", "--root", str(root)]) == 1
    assert "no 'Excluded, with the reason' section" in capsys.readouterr().out


def test_a_missing_census_refuses(tmp_path):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "alpha.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    assert icc.main(["check", "--root", str(root)]) == 1


def test_resolve_adr_prefers_the_default_path(tmp_path):
    """CPP's own resolution cannot move: the default wins even beside a candidate."""
    root = _tree(tmp_path, ["alpha.sh"], _adr())
    (root / "docs" / "adr").mkdir()
    (root / "docs" / "adr" / "0005-negative-control.md").write_text("x", encoding="utf-8")
    path, label = icc.resolve_adr(root)
    assert path == root / icc.ADR_REL and label == icc.ADR_REL


def test_the_census_at_another_repositorys_path_is_checked(tmp_path, capsys):
    """THE RED CASE (issue #1264): kyle files the decision under docs/adr/."""
    root = _tree(tmp_path, ["alpha.sh"], _adr("| 1 | `alpha.sh` | v | c | G |\n"))
    moved = root / "docs" / "adr" / "0005-instrument-negative-control-enumeration.md"
    moved.parent.mkdir()
    (root / icc.ADR_REL).rename(moved)
    assert icc.main(["check", "--root", str(root)]) == 0, capsys.readouterr().out


def test_two_candidates_refuse_rather_than_pick(tmp_path, capsys):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "alpha.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    for rel in ("docs/adr/0005-negative-control.md", "docs/decisions/0009-negative-control.md"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(_adr("| 1 | `alpha.sh` | v | c | G |\n"), encoding="utf-8")
    assert icc.main(["check", "--root", str(root)]) == 1
    assert "refusing to pick one" in capsys.readouterr().out


def test_directories_under_scripts_are_not_required_to_be_accounted_for(tmp_path):
    root = _tree(tmp_path, ["alpha.sh"], _adr(rows="| 1 | `alpha.sh` | v | c | G |\n"))
    (root / "scripts" / "__pycache__").mkdir()
    assert icc.main(["check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# Fenced examples are not the document speaking
# ---------------------------------------------------------------------------


def test_a_fenced_example_row_does_not_account_for_a_real_script(tmp_path):
    """The dangerous direction: a false GREEN over a genuinely unenumerated file."""
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        _adr(
            rows="| 1 | `alpha.sh` | v | c | G |\n",
            tail="\n```\n| 1 | `beta.sh` | v | c | G |\n```\n",
        ),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


def test_a_fenced_example_row_is_not_reported_stale(tmp_path):
    """The other direction: an illustrative row would block every merge."""
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        _adr(
            rows="| 1 | `alpha.sh` | v | c | G |\n",
            tail="\n```\n| 7 | `example-tool.sh` | v | c | G |\n```\n",
        ),
    )
    assert icc.main(["check", "--root", str(root)]) == 0


def test_a_fenced_declaration_cannot_widen_the_externals_list(tmp_path):
    """A marker inside an example must not quiet a real stale subject."""
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        _adr(
            rows="| 1 | `alpha.sh` | v | c | G |\n| 2 | `gone.sh` | v | c | G |\n",
            tail="\n```\n<!-- instrument-census: external-subjects: gone.sh -->\n```\n",
        ),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


def test_a_longer_fence_is_not_closed_by_a_shorter_inner_one(tmp_path):
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        _adr(
            rows="| 1 | `alpha.sh` | v | c | G |\n",
            tail="\n````\n```\n| 1 | `beta.sh` | v | c | G |\n```\n````\n",
        ),
    )
    assert icc.main(["check", "--root", str(root)]) == 1


# ---------------------------------------------------------------------------
# Wiring - the gate must actually be run by something
# ---------------------------------------------------------------------------


def test_the_gate_is_wired_into_make_verify():
    """A gate nothing invokes is not a gate (the #591 shape)."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\ninstrument-census-check:\n" in text, "the make target is gone"
    verify = text.split("\nverify:", 1)[1].split("\n\n", 1)[0]
    assert "instrument-census-check" in verify, "the gate was dropped from `make verify`"


def test_the_gate_has_its_own_ci_step():
    """`make verify` is not run by CI; each gate carries its own step (#1028)."""
    text = (ROOT / ".woodpecker.yml").read_text(encoding="utf-8")
    assert "\n  instrument-census-check:\n" in text, "the CI step is gone"
    assert "python3 scripts/instrument-census-check.py" in text


def test_the_gate_registers_its_negative_control():
    """The registration lives in the gate file because that is what the battery reads.

    A control directory alone is invisible to `check-negative-controls.py`, which
    then reports PASS over a register the new control is not in.
    """
    assert "NEGATIVE-CONTROL: controls/instrument-census" in _script_path.read_text(encoding="utf-8")


def test_the_gate_is_itself_a_census_row():
    """It must account for ITSELF, or its first run reports itself UNACCOUNTED."""
    text = (ROOT / icc.ADR_REL).read_text(encoding="utf-8")
    assert "instrument-census-check.py" in set(icc.census_subjects(text))
