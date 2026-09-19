"""Uniformity is not itself a finding (issue #1091).

The five committed cases are copied under tmp_path for every test. They are
also the control registration's inputs and --selftest's fixtures, so those
three entry points cannot drift into exercising different evidence. Additional
cases cover malformed input and the mismatch-before-diversity ordering.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "counter-model-uniformity-check.py"
CONTROL = ROOT / "controls" / "counter-model-uniformity"
REGISTRATION = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))
CASES = {case["name"]: case for case in REGISTRATION["cases"]}

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2


def _load():
    spec = importlib.util.spec_from_file_location("counter_model_uniformity_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GATE = _load()


def fixture(tmp_path: Path, name: str) -> Path:
    """Materialize the registered receipts and synthetic logs in the test tree."""
    return Path(shutil.copytree(CONTROL / CASES[name]["input"], tmp_path / name))


def run(tmp_path: Path, *args: str, script: Path = SCRIPT) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args], cwd=tmp_path,
        env={**os.environ, "TMPDIR": str(tmp_path)},
        capture_output=True, text=True, timeout=30, check=False,
    )


def run_case(tmp_path: Path, case: Path, *, evidence: bool = True) -> subprocess.CompletedProcess:
    args = ["--receipts-dir", str(case / "receipts")]
    if evidence:
        args.extend(["--evidence-dir", str(case / "evidence")])
    return run(tmp_path, *args)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def add_evidence(case: Path, stem: str, model: str) -> Path:
    """Each receipt gets its own session root, even with the same thread ID."""
    evidence = case / "evidence"
    manifest = evidence / f"{stem}.evidence.json"
    thread_id = "same-thread-in-independent-roots"
    write_json(manifest, {"exec_log": f"{stem}/exec.jsonl", "sessions_dir": f"{stem}/sessions"})
    write_json(evidence / stem / "exec.jsonl", {"type": "thread.started", "thread_id": thread_id})
    write_json(evidence / stem / "sessions/2026/09/19" / f"rollout-{thread_id}.jsonl", {"model": model})
    return manifest


@pytest.mark.parametrize(("name", "code", "denominator", "phrase"), [
    ("good-diverse", EXIT_OK, "examined=3 verifiable=0 distinct=2", "corpus is diverse"),
    ("bad-copied-literal", EXIT_FINDING, "examined=2 verifiable=1 distinct=1",
     "review-1.json: stored reviewer='codex/gpt-5.5', cross-verification derived='codex/gpt-6-astra'"),
    ("good-verified-uniform", EXIT_OK, "examined=2 verifiable=1 distinct=1",
     "verified against 1 receipt(s) of exec-log evidence, no mismatch"),
    ("bad-unverified-uniform", EXIT_UNKNOWN, "examined=2 verifiable=0 distinct=1",
     "could not distinguish a constant from a genuinely unchanging model"),
    ("bad-empty-corpus", EXIT_UNKNOWN, "examined=0 verifiable=0 distinct=0", "nothing was examined"),
])
def test_committed_case(tmp_path: Path, name: str, code: int, denominator: str, phrase: str) -> None:
    proc = run_case(tmp_path, fixture(tmp_path, name))
    assert proc.returncode == code == CASES[name]["expected_exit"], proc.stdout + proc.stderr
    assert proc.stdout == CASES[name]["expected_output"] + "\n"
    assert proc.stderr == ""
    assert denominator in proc.stdout
    assert phrase in proc.stdout
    prefix = {EXIT_OK: "OK", EXIT_FINDING: "FINDING", EXIT_UNKNOWN: "UNKNOWN"}[code]
    assert proc.stdout.startswith(f"UNIFORMITY-{prefix}:")
    signal = re.compile(REGISTRATION["detect_signal"], re.MULTILINE)
    assert bool(signal.search(proc.stdout)) == (code != EXIT_OK)
    for other in {"OK", "FINDING", "UNKNOWN"} - {prefix}:
        assert f"UNIFORMITY-{other}:" not in proc.stdout


def test_no_evidence_flag_is_unknown(tmp_path: Path) -> None:
    case = fixture(tmp_path, "good-verified-uniform")
    proc = run_case(tmp_path, case, evidence=False)
    assert proc.returncode == EXIT_UNKNOWN
    assert proc.stdout == CASES["bad-unverified-uniform"]["expected_output"] + "\n"


@pytest.mark.parametrize("contents", ["{broken", "{}", "[]", '{"exec_log": 7, "sessions_dir": "sessions"}'])
def test_malformed_evidence_is_visible_but_not_a_mismatch(tmp_path: Path, contents: str) -> None:
    case = fixture(tmp_path, "bad-unverified-uniform")
    (case / "evidence/review-1.evidence.json").write_text(contents, encoding="utf-8")
    proc = run_case(tmp_path, case)
    assert proc.returncode == EXIT_UNKNOWN, proc.stdout + proc.stderr
    assert proc.stdout.startswith(CASES["bad-unverified-uniform"]["expected_output"])
    assert "UNIFORMITY-NOTE: review-1.json: evidence not verifiable:" in proc.stdout
    assert "UNIFORMITY-FINDING:" not in proc.stdout


@pytest.mark.parametrize("broken", ["exec", "rollout", "model", "encoding"])
def test_unusable_exec_evidence_is_not_counted(tmp_path: Path, broken: str) -> None:
    case = fixture(tmp_path, "good-verified-uniform")
    evidence = case / "evidence/review-1"
    rollout = next((evidence / "sessions").rglob("*.jsonl"))
    if broken == "exec":
        (evidence / "exec.jsonl").unlink()
    elif broken == "rollout":
        rollout.unlink()
    elif broken == "model":
        write_json(rollout, {"no_model": True})
    else:
        rollout.write_bytes(b"\xff")
    proc = run_case(tmp_path, case)
    assert proc.returncode == EXIT_UNKNOWN
    assert "examined=2 verifiable=0 distinct=1" in proc.stdout
    assert "evidence not verifiable:" in proc.stdout
    assert "UNIFORMITY-FINDING:" not in proc.stdout


def test_mismatch_precedes_diversity_and_reports_each_disagreement(tmp_path: Path) -> None:
    case = fixture(tmp_path, "good-diverse")
    add_evidence(case, "review-1", "different-model-1")
    add_evidence(case, "review-2", "different-model-2")
    proc = run_case(tmp_path, case)
    assert proc.returncode == EXIT_FINDING
    assert "examined=3 verifiable=2 distinct=2" in proc.stdout
    assert proc.stdout.count("UNIFORMITY-FINDING:") == 2
    for number in (1, 2):
        assert f"review-{number}.json: stored reviewer=" in proc.stdout
        assert f"derived='codex/different-model-{number}'" in proc.stdout
    assert "UNIFORMITY-OK:" not in proc.stdout


def test_partial_matching_evidence_cannot_hide_a_mismatch(tmp_path: Path) -> None:
    case = fixture(tmp_path, "good-verified-uniform")
    add_evidence(case, "review-2", "different-model")
    proc = run_case(tmp_path, case)
    assert proc.returncode == EXIT_FINDING
    assert "examined=2 verifiable=2 distinct=1" in proc.stdout
    assert "UNIFORMITY-FINDING: review-2.json:" in proc.stdout


def test_absolute_paths_are_supported(tmp_path: Path) -> None:
    case = fixture(tmp_path, "bad-unverified-uniform")
    manifest = add_evidence(case, "review-1", "gpt-5.5")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    write_json(manifest, {key: str(manifest.parent / value) for key, value in payload.items()})
    proc = run_case(tmp_path, case)
    assert proc.returncode == EXIT_OK
    assert proc.stdout == CASES["good-verified-uniform"]["expected_output"] + "\n"


def test_invalid_json_and_non_ran_receipts_are_excluded(tmp_path: Path) -> None:
    case = fixture(tmp_path, "good-diverse")
    receipts = case / "receipts"
    (receipts / "invalid.json").write_text("{broken", encoding="utf-8")
    write_json(receipts / "array.json", [])
    write_json(receipts / "skipped.json", {"status": "skipped", "reviewer": None})
    write_json(receipts / "other.json", {"status": "other", "reviewer": "not-counted"})
    proc = run_case(tmp_path, case)
    assert proc.returncode == EXIT_OK
    assert proc.stdout.startswith(CASES["good-diverse"]["expected_output"])
    assert "UNIFORMITY-NOTE: invalid.json: receipt excluded:" in proc.stdout


@pytest.mark.parametrize("exists", [False, True])
def test_missing_or_truly_empty_directory_is_unknown(tmp_path: Path, exists: bool) -> None:
    receipts = tmp_path / "receipts"
    if exists:
        receipts.mkdir()
    proc = run(tmp_path, "--receipts-dir", str(receipts))
    assert proc.returncode == EXIT_UNKNOWN
    assert proc.stdout == CASES["bad-empty-corpus"]["expected_output"] + "\n"


def test_nested_receipts_are_examined(tmp_path: Path) -> None:
    case = fixture(tmp_path, "good-verified-uniform")
    nested = case / "receipts/nested"
    nested.mkdir()
    (case / "receipts/review-1.json").rename(nested / "review-1.json")
    proc = run_case(tmp_path, case)
    assert proc.returncode == EXIT_OK
    assert proc.stdout == CASES["good-verified-uniform"]["expected_output"] + "\n"


def test_selftest_ignores_input_flags(tmp_path: Path) -> None:
    proc = run(tmp_path, "--selftest", "--receipts-dir", str(tmp_path / "absent"),
               "--evidence-dir", str(tmp_path / "also-absent"))
    assert proc.returncode == EXIT_OK, proc.stdout + proc.stderr
    for name in CASES:
        assert f"UNIFORMITY-SELFTEST: {name}: PASS\n" in proc.stdout
    assert "UNIFORMITY-SELFTEST: 5/5 cases matched" in proc.stdout


def test_selftest_names_a_failed_case(tmp_path: Path, monkeypatch, capsys) -> None:
    control = Path(shutil.copytree(CONTROL, tmp_path / "control"))
    manifest = control / "cases/bad-copied-literal/evidence/review-1.evidence.json"
    manifest.unlink()
    monkeypatch.setattr(GATE, "CONTROL", control)
    # Keep even selftest's temporary copies within this test's tmp_path.
    monkeypatch.setattr(GATE.tempfile, "tempdir", str(tmp_path))
    assert GATE.selftest() == EXIT_FINDING
    output = capsys.readouterr().out
    assert "UNIFORMITY-SELFTEST: bad-copied-literal: FAIL" in output
    assert "UNIFORMITY-SELFTEST: 4/5 cases matched" in output


def test_constructed_anchor_misses_bad_cases_and_agrees_on_good(tmp_path: Path) -> None:
    anchor = REGISTRATION["anchors"][0]
    script = CONTROL / anchor["path"]
    assert hashlib.sha256(script.read_bytes()).hexdigest() == anchor["sha256"]
    missed = []
    for name, case in CASES.items():
        copied = fixture(tmp_path, name)
        proc = run(tmp_path, "--receipts-dir", str(copied / "receipts"),
                   "--evidence-dir", str(copied / "evidence"), script=script)
        if case["expect"] == "GOOD":
            assert proc.returncode == EXIT_OK, proc.stdout + proc.stderr
        elif proc.returncode == EXIT_OK:
            missed.append(name)
    assert missed == ["bad-copied-literal", "bad-empty-corpus", "bad-unverified-uniform"]
