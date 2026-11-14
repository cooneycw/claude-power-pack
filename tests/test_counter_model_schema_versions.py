"""Historical shape compatibility is distinct from current quota permission (#1818).

Schema 1 follows CPP b6117e7b, before #1515: a positive integer count, with
a nonempty reason above two and no reason at or below two. Schema 2 retains
the current bounded escalation rules. These synthetic cases prove neither
the producer revision nor authorization of any historical consumer receipt.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_counter_model_review import _RAN_BASE, CM

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/counter_model/schema_versions.json").read_text())


def _receipt(case: dict) -> dict:
    receipt = dict(copy.deepcopy(_RAN_BASE), passes=2)
    receipt.update(case["update"])
    for key in case["omit"]:
        receipt.pop(key, None)
    return receipt


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_schema_contract(case: dict) -> None:
    receipt = _receipt(case)
    assert receipt["schema"] == case["update"]["schema"]
    if case["error"] and "reason" in case["name"]:
        assert not isinstance(receipt.get("extra_passes_reason"), str) or (
            not receipt["extra_passes_reason"].strip() or receipt["passes"] <= 2
        ), "precondition: reason is missing, malformed, or present without an extra pass"
    problems = CM.validate(receipt, case["name"])
    if case["error"] is None:
        assert problems == []
    else:
        assert any(case["error"] in problem for problem in problems), problems


def test_corpus_cli_reads_both_versions_and_reports_a_bad_current_receipt(tmp_path: Path) -> None:
    legacy = _receipt(next(case for case in CASES if case["name"] == "legacy-reason-9"))
    current = _receipt(next(case for case in CASES if case["name"] == "current-five-ruled"))
    for name, receipt in [("legacy", legacy), ("current", current)]:
        (tmp_path / f"{name}.json").write_text(json.dumps(receipt))
    command = [sys.executable, str(ROOT / "scripts/counter-model-receipt.py"),
               "validate", "--dir", str(tmp_path)]
    good = subprocess.run(command, capture_output=True, text=True, check=False)
    assert good.returncode == 0, good.stdout + good.stderr
    assert "COUNTER_MODEL_EXAMINED: 2" in good.stdout
    del current["escalation"]
    assert "escalation" not in current and current["passes"] > 3
    (tmp_path / "current.json").write_text(json.dumps(current))
    bad = subprocess.run(command, capture_output=True, text=True, check=False)
    assert bad.returncode == 1
    assert "no recorded ruling" in bad.stdout
    assert "COUNTER_MODEL_RECEIPTS: invalid" in bad.stdout


def test_scalar_extra_pass_writer_still_emits_schema_two() -> None:
    args = argparse.Namespace(
        implementer="claude/y", reviewer="codex/x", at="2026-10-16T00:00:00Z",
        issue="1818", branch="fixture", status="ran", head=None,
        scope="unverified", network="blocked", local_credentials="unknown",
        passes=3, extra_pass_reason="Requested.", accepted=0, rejected=0,
        deferred=0, red_cases_proposed=0, red_cases_already_covered=0,
    )
    receipt = CM.build(args)
    assert receipt["schema"] == 2
    assert CM.validate(receipt) == []


def test_unknown_schema_diagnostic_does_not_deny_the_historical_reason_contract() -> None:
    receipt = _receipt(next(case for case in CASES if case["name"] == "legacy-reason-9"))
    assert CM.validate(receipt) == []
    receipt["schema"] = 99
    assert receipt["schema"] not in range(1, 6)
    problems = CM.validate(receipt)
    assert any("expected 2" in problem and "historical schema 1" in problem for problem in problems), problems
    assert not any("schema 1 does not describe" in problem for problem in problems)


@pytest.mark.skipif(shutil.which("git") is None, reason="enrolment reads a real Git history")
@pytest.mark.parametrize("with_ruling", [False, True])
def test_legacy_shape_and_current_enrolment_have_independent_contracts(tmp_path: Path, with_ruling: bool) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-q", "-b", "fixture")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-qm", "initial", "--allow-empty")
    receipt = _receipt(next(case for case in CASES if case["name"] == "legacy-reason-9"))
    receipt.update(branch="fixture", head=git("rev-parse", "HEAD"), scope="full")
    assert "escalation" not in receipt and receipt["passes"] > 3
    if with_ruling:
        receipt["escalation"] = dict(ruled_by="Fixture authority", reference="Synthetic fixture only.", raised_cap=9)
        assert any("requires a current schema" in problem for problem in CM.validate(receipt))
    else:
        assert CM.validate(receipt) == []
    receipts = tmp_path / "docs/measurements/counter-model"
    receipts.mkdir(parents=True)
    (receipts / "legacy.json").write_text(json.dumps(receipt))
    answer = CM.evaluate_enrolment(tmp_path, "fixture", "enrolment")
    if with_ruling:
        assert answer.state == "escalated"
        assert "9 passes, ruled by Fixture authority" in answer.line
    else:
        assert answer.state == "unknown"
        assert "no recorded ruling" in answer.line
