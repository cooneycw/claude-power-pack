"""A landed receipt can be attributed to the rollout that produced it (issue #1048).

The five committed cases are copied under tmp_path for every test. They are
also the control registration's inputs and --selftest's fixtures, so those three
entry points cannot drift into exercising different evidence.

THE PAIR THAT MATTERS is bad-disagreement / bad-blind-extractor. Both supply the
same stored-vs-derived disagreement; they differ only in whether the extractor is
shown to discriminate, and the verdict must differ with them. An instrument that
reported a finding in both would be echoing a constant - the exact defect the 13
landed receipts are an instance of.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "counter-model-reviewer-attribution.py"
CONTROL = ROOT / "controls" / "counter-model-reviewer-attribution"
REGISTRATION = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))
CASES = {case["name"]: case for case in REGISTRATION["cases"]}
REPO = "repo"

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2


def _load():
    spec = importlib.util.spec_from_file_location("counter_model_reviewer_attribution", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GATE = _load()


def _case(tmp_path: Path, name: str) -> Path:
    return Path(shutil.copytree(CONTROL / f"cases/{name}", tmp_path / name))


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_committed_case_reports_its_registered_verdict(tmp_path: Path, name: str) -> None:
    """The registration, --selftest and pytest must agree on every case."""
    fixture = _case(tmp_path, name)
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert code == CASES[name]["expected_exit"]
    assert output == CASES[name]["expected_output"]


def test_a_blind_extractor_WITHDRAWS_the_finding_its_twin_reports(tmp_path: Path) -> None:
    """THE load-bearing case.

    bad-disagreement and bad-blind-extractor carry the same receipt and the same
    stored-vs-linked disagreement. Only the rollout population differs: one holds
    two distinct models, the other one. If both reported a finding, the instrument
    would be reporting a constant and could not be told from the defect it audits.
    """
    finding_code, finding_output = GATE.scan(
        _case(tmp_path, "bad-disagreement") / "receipts",
        tmp_path / "bad-disagreement" / "rollouts",
        REPO,
    )
    blind_code, blind_output = GATE.scan(
        _case(tmp_path, "bad-blind-extractor") / "receipts",
        tmp_path / "bad-blind-extractor" / "rollouts",
        REPO,
    )

    stored = json.loads(
        (CONTROL / "cases/bad-disagreement/receipts/review-1.json").read_text(encoding="utf-8")
    )
    twin = json.loads(
        (CONTROL / "cases/bad-blind-extractor/receipts/review-1.json").read_text(encoding="utf-8")
    )
    assert stored == twin, "the two cases must differ ONLY in their rollout population"

    assert finding_code == EXIT_FINDING and "ATTRIBUTION-FINDING:" in finding_output
    assert blind_code == EXIT_UNKNOWN
    assert "ATTRIBUTION-FINDING:" not in blind_output
    assert "extractor_distinct=1" in blind_output
    # Both examined the same receipt and both SAW the disagreement; only one is
    # entitled to report it.
    assert "disagreed=1" in finding_output and "disagreed=1" in blind_output


def test_an_ambiguous_link_is_verified_neither_way(tmp_path: Path) -> None:
    """Two models in one worktree window determine nothing, and nothing is picked."""
    fixture = _case(tmp_path, "bad-ambiguous")
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert code == EXIT_UNKNOWN
    assert "ambiguous=1" in output and "linked=0" in output
    assert "ATTRIBUTION-FINDING:" not in output
    assert "verified neither way" in output


def test_an_unattributed_corpus_is_unknown_not_clean(tmp_path: Path) -> None:
    fixture = _case(tmp_path, "bad-nothing-linked")
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert code == EXIT_UNKNOWN
    assert "ATTRIBUTION-OK:" not in output


def test_an_empty_receipt_population_is_unknown(tmp_path: Path) -> None:
    """Nothing examined and nothing wrong are different facts."""
    (tmp_path / "receipts").mkdir()
    (tmp_path / "rollouts").mkdir()
    code, output = GATE.scan(tmp_path / "receipts", tmp_path / "rollouts", REPO)
    assert code == EXIT_UNKNOWN
    assert "examined=0" in output


def test_a_skipped_receipt_never_enters_the_denominator(tmp_path: Path) -> None:
    """A skip records no reviewer, so it cannot be attributed to one."""
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    (tmp_path / "rollouts").mkdir()
    (receipts / "skipped.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "recorded_at": "2026-09-16T20:52:21Z",
                "issue": "9001",
                "branch": "issue-9001-alpha",
                "status": "skipped",
                "skip_reason": "codex-absent",
                "reviewer": None,
                "implementer": "claude/opus-5",
            }
        ),
        encoding="utf-8",
    )
    code, output = GATE.scan(receipts, tmp_path / "rollouts", REPO)
    assert code == EXIT_UNKNOWN
    assert "examined=0" in output


def test_a_rollout_outside_the_window_does_not_link(tmp_path: Path) -> None:
    """The window is part of the association; widening it silently is not free."""
    fixture = _case(tmp_path, "good-agreement")
    inside, _ = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert inside == EXIT_OK
    outside_code, outside_output = GATE.scan(
        fixture / "receipts", fixture / "rollouts", REPO, window=timedelta(minutes=1)
    )
    assert outside_code == EXIT_UNKNOWN
    assert "unlinked=1" in outside_output


def test_an_unparseable_receipt_is_diagnosed_not_silently_dropped(tmp_path: Path) -> None:
    fixture = _case(tmp_path, "good-agreement")
    (fixture / "receipts" / "broken.json").write_text("{not json", encoding="utf-8")
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert code == EXIT_OK
    assert "ATTRIBUTION-NOTE: broken.json: receipt excluded" in output


def test_a_headerless_rollout_is_ignored_rather_than_guessed_at(tmp_path: Path) -> None:
    fixture = _case(tmp_path, "good-agreement")
    (fixture / "rollouts" / "no-header.jsonl").write_text(
        '{"type":"turn_context","payload":{"model":"gpt-9-fake"}}\n', encoding="utf-8"
    )
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert code == EXIT_OK
    assert "gpt-9-fake" not in output


def test_selftest_runs_the_registered_cases(tmp_path: Path) -> None:
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True
    )
    assert out.returncode == EXIT_OK, out.stdout + out.stderr
    assert f"{len(CASES)}/{len(CASES)} cases matched" in out.stdout


def test_the_registered_anchor_matches_its_recorded_sha256() -> None:
    """The anchor is constructed, so integrity is all that establishes it."""
    anchor = REGISTRATION["anchors"][0]
    digest = hashlib.sha256((CONTROL / anchor["path"]).read_bytes()).hexdigest()
    assert digest == anchor["sha256"]


@pytest.mark.parametrize("name", sorted(n for n in CASES if n.startswith("bad-")))
def test_the_anchor_MISSES_every_known_bad_case(tmp_path: Path, name: str) -> None:
    """A control whose anchor catches the bad input proves nothing about the gate."""
    fixture = _case(tmp_path, name)
    out = subprocess.run(
        [
            sys.executable,
            str(CONTROL / REGISTRATION["anchors"][0]["path"]),
            "--receipts-dir",
            str(fixture / "receipts"),
            "--rollouts-dir",
            str(fixture / "rollouts"),
        ],
        capture_output=True,
        text=True,
    )
    assert out.returncode == REGISTRATION["good_exit"], (
        f"the blind anchor DETECTED {name}; it no longer demonstrates the blindness"
    )


def test_the_instrument_never_writes_to_the_receipts_it_reads(tmp_path: Path) -> None:
    """docs/measurements/counter-model/ is read-only to this instrument."""
    fixture = _case(tmp_path, "bad-disagreement")
    before = {
        p: p.read_bytes() for p in sorted((fixture / "receipts").rglob("*")) if p.is_file()
    }
    GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    after = {
        p: p.read_bytes() for p in sorted((fixture / "receipts").rglob("*")) if p.is_file()
    }
    assert before == after


# --- Counter-model review findings (#1048), each pinned by the case it produced ---


def test_a_foreign_repository_worktree_is_NOT_linked(tmp_path: Path) -> None:
    """A branch name is not a repository boundary.

    The sessions directory spans every repository on the host, and
    `<another-repo>-issue-9001-alpha` ends with the same branch as
    `<repo>-issue-9001-alpha`. Suffix matching let a neighbour's rollout supply a
    confident attribution - the detector contract's second question, answered no.
    """
    fixture = _case(tmp_path, "bad-foreign-repo")
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert code == EXIT_UNKNOWN
    assert "unlinked=1" in output
    assert "ATTRIBUTION-FINDING:" not in output
    # ... and the neighbour's model is never reported as this receipt's reviewer.
    assert "gpt-5.6-sol" not in output


def test_an_unreadable_candidate_is_unresolved_not_absent(tmp_path: Path) -> None:
    """Dropping a model-less candidate made the rest look unanimous."""
    fixture = _case(tmp_path, "bad-unreadable-candidate")
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    assert code == EXIT_UNKNOWN
    assert "ambiguous=1" in output and "agreed=0" in output
    assert "declare no model" in output


@pytest.mark.parametrize("bad_time", [42, True, None, {"t": 1}, ["2026-09-16T20:52:21Z"]])
def test_a_non_string_recorded_at_does_not_abort_the_scan(tmp_path: Path, bad_time) -> None:
    """One malformed receipt must not leave every other receipt unexamined."""
    fixture = _case(tmp_path, "good-agreement")
    broken = json.loads((fixture / "receipts" / "review-1.json").read_text(encoding="utf-8"))
    broken["recorded_at"] = bad_time
    (fixture / "receipts" / "broken.json").write_text(json.dumps(broken), encoding="utf-8")
    code, output = GATE.scan(fixture / "receipts", fixture / "rollouts", REPO)
    # The healthy receipt is still examined and still attributed.
    assert "examined=2" in output
    assert "agreed=1" in output
    assert "no usable branch or recorded_at" in output
    assert code == EXIT_OK


def test_an_empty_case_registration_FAILS_the_selftest(tmp_path: Path, monkeypatch) -> None:
    """`cases: []` printed 0/0 and exited 0 - a blind instrument reporting on itself."""
    empty = tmp_path / "control"
    empty.mkdir()
    (empty / "control.json").write_text(json.dumps({"cases": []}), encoding="utf-8")
    monkeypatch.setattr(GATE, "CONTROL", empty)
    assert GATE.selftest() != EXIT_OK


def test_a_selftest_missing_ONE_required_case_fails(tmp_path: Path, monkeypatch) -> None:
    """Named, not counted: swapping a case out is caught as well as deleting it."""
    trimmed = tmp_path / "control"
    trimmed.mkdir()
    kept = [c for c in REGISTRATION["cases"] if c["name"] != "bad-blind-extractor"]
    (trimmed / "control.json").write_text(json.dumps({"cases": kept}), encoding="utf-8")
    monkeypatch.setattr(GATE, "CONTROL", trimmed)
    assert GATE.selftest() != EXIT_OK


def test_every_required_case_is_actually_registered() -> None:
    """The required set and the committed registration cannot drift apart."""
    assert GATE.REQUIRED_CASES <= set(CASES)


def test_an_underivable_repository_REFUSES_rather_than_matching_loosely(
    tmp_path: Path, monkeypatch
) -> None:
    """Without a repository boundary the scan must not fall back to a branch suffix."""
    fixture = _case(tmp_path, "good-agreement")
    monkeypatch.setattr(GATE, "_derive_repo_name", lambda _: None)
    code = GATE.main(
        [
            "--receipts-dir",
            str(fixture / "receipts"),
            "--rollouts-dir",
            str(fixture / "rollouts"),
        ]
    )
    assert code == EXIT_UNKNOWN
