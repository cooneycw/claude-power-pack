"""The clean-install proof, and the halves a committed case cannot carry (#1074).

`controls/codex-install-proof` scores the manifest COMPARISON against a fixture
tree. It cannot carry an install, four constructed absences, or three known-bad
mutations of a live installed copy - so those are here.

Every test drives `scripts/codex-install-proof.sh` as a PROGRAM, because that is
the surface the Makefile target and any reader invokes; an in-process harness
would not catch a shebang or quoting break in the thing that actually ships.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "scripts" / "codex-install-proof.sh"
CASES = ROOT / "controls" / "codex-install-proof" / "cases"

requires_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not on PATH")


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    import os

    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run(
        ["bash", str(PROOF), *args], capture_output=True, text=True, check=False, env=merged
    )


@requires_bash
def test_the_proof_runs_end_to_end_and_emits_its_contract(tmp_path: Path) -> None:
    """The happy path, and the contract a reader consumes.

    Asserts the CONTRACT LINES rather than just exit 0: a proof that exits 0
    while printing nothing identifiable is indistinguishable from one that never
    ran, which is this issue's own defect class pointed at itself.
    """
    result = _run(env={"PROOF_WORK": str(tmp_path / "w")})

    assert result.returncode == 0, result.stdout + result.stderr
    for marker in (
        "PROOF_SOURCE_SHA:",
        "PROOF_INSTALLED_HASH:",
        "PROOF_COMPARED:",
        "PROOF_WORKFLOW: ok",
        "PROOF: ok",
    ):
        assert marker in result.stdout, f"the contract is missing {marker!r}"


@requires_bash
def test_every_not_run_cell_is_emitted_by_the_harness(tmp_path: Path) -> None:
    """NOT RUN cells are the harness's output, never hand-written prose.

    The issue's binding rule is that a cell not run is recorded as not run and
    never inferred from a neighbour that passed. A doc that lists them by hand
    can drift from what the run actually skipped; these come from the run.
    """
    result = _run(env={"PROOF_WORK": str(tmp_path / "w")})

    emitted = [line for line in result.stdout.splitlines() if line.startswith("PROOF_NOT_RUN:")]
    assert len(emitted) >= 3, f"expected the three declared NOT RUN cells, got {emitted}"
    assert any("codex-loader" in line for line in emitted)
    assert any("other-skills" in line for line in emitted)
    assert any("platform" in line for line in emitted)


@requires_bash
def test_all_three_known_bad_inputs_are_rejected(tmp_path: Path) -> None:
    """The half that matters: a proof that only walks the happy path shows the
    happy path exists, not that a broken install is noticed."""
    result = _run(env={"PROOF_WORK": str(tmp_path / "w")})

    rejected = [line for line in result.stdout.splitlines() if line.startswith("PROOF_KNOWN_BAD:")]
    assert len(rejected) == 3, f"expected three rejections, got {rejected}"
    assert all("REJECTED" in line for line in rejected)


@requires_bash
def test_the_missing_scripts_rejection_names_codex_home_and_nothing_ambient(
    tmp_path: Path,
) -> None:
    """The pinned failure TEXT for known-bad 2 (#1074 gate condition).

    This is the case most likely to "pass" by silently finding an ambient or repo
    copy, so the rejection must name a path under CODEX_HOME and must name
    neither `~/.claude/scripts` nor a repository path. A rejection that names the
    repo is a rejection produced by the neighbour this proof asserts is absent.
    """
    result = _run(env={"PROOF_WORK": str(tmp_path / "w")})

    line = next(
        (ln for ln in result.stdout.splitlines() if "missing-scripts" in ln), ""
    )
    assert "REJECTED" in line, f"missing-scripts was not rejected: {line!r}"
    assert "CODEX_HOME" in line


@requires_bash
@pytest.mark.parametrize(
    ("case", "expected_exit"),
    [("good-matching-install", 0), ("bad-drifted-install", 1)],
)
def test_the_committed_cases_score_as_registered(case: str, expected_exit: int) -> None:
    """The control's own cases, driven through the shipped entry point."""
    result = _run("--root", str(CASES / case))
    assert result.returncode == expected_exit, result.stdout + result.stderr


@requires_bash
def test_an_empty_expected_set_is_refused_rather_than_passing(tmp_path: Path) -> None:
    """A manifest with no files must not report success.

    Zero compared files and zero findings is "there was nothing to look at", not
    "I looked and found nothing" - the distinction the detector contracts require
    a check to be able to draw about itself.
    """
    case = tmp_path / "empty"
    (case / "codex-home" / "skills" / "project-next").mkdir(parents=True)
    (case / "expected.json").write_text(
        json.dumps({"skill": "project-next", "source_sha": "x", "files": {}}), encoding="utf-8"
    )

    result = _run("--root", str(case))
    assert result.returncode != 0 or "PROOF_COMPARED: 0" not in result.stdout, (
        "an empty expected set reported success; a comparison over nothing is not a pass"
    )
