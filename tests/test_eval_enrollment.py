"""Tests for scripts/check-eval-enrollment.py - the enrollment-decision consumer (#1371).

The policy under test is ADR 0011's: flow-check is ADVISORY, every reading says
so, and the consumer tells current, stale (content), stale (aged), failing,
fixture-only and unknown records apart - by a printed word AND a distinct exit
code without --advisory, while --advisory never fails a printed verdict. A
pass-rate threshold and a blocking decision are refused, never ignored.

Each test here was run red against a mutant of the consumer (the mutation is
named in the test's comment); the PR records those runs.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-eval-enrollment.py"
COMMITTED = ROOT / "docs" / "measurements" / "eval-enrollment" / "flow-check.json"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enroll = _load(SCRIPT, "check_eval_enrollment")
TODAY = date(2026, 11, 1)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    skill = repo / "codex" / "skills" / "flow-check"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\ndescription: x\n---\nbody\n")
    gate = skill / "scripts" / "flow-finish-gate.sh"
    gate.write_text("#!/bin/sh\necho gate\n")
    gate.chmod(0o755)
    return repo


def _record(repo: Path, **overrides) -> Path:
    rec = json.loads(COMMITTED.read_text(encoding="utf-8"))
    rec["evaluated"]["closure_digest"] = enroll.closure_digest(repo, "flow-check")
    for key, value in overrides.items():
        if value is _DROP:
            rec.pop(key, None)
        else:
            rec[key] = value
    path = repo / "record.json"
    path.write_text(json.dumps(rec))
    return path


_DROP = object()


def _state(repo: Path, record: Path, today: date = TODAY) -> dict:
    return enroll.evaluate(record, repo, today)


def _run(repo: Path, record: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--record", str(record),
         "--today", TODAY.isoformat(), *extra],
        capture_output=True, text=True, check=False,
    )


# --------------------------------------------------------------------------- #
# The five populations #1371 names: valid, failing, unknown, stale, fixture-only
# --------------------------------------------------------------------------- #
def test_valid_record_reads_advisory_current_never_assurance(tmp_path: Path) -> None:
    # Mutant: the content comparison always succeeds -> still current (this test
    # pins the wording); mutant `head` text "PASS" -> red here.
    repo = _repo(tmp_path)
    result = _run(repo, _record(repo))
    assert result.returncode == 0, result.stdout + result.stderr
    first = result.stdout.splitlines()[0]
    assert "advisory - evidence current" in first
    assert "NOT behavioural assurance" in first
    lowered = result.stdout.lower()
    for word in ("assured", "blocking enrolled", ": pass"):
        assert word not in lowered, word
    assert result.stdout.count("limit: ") == 4, "every reading prints the record's limits"


def test_failing_evidence_reads_failing_not_current(tmp_path: Path) -> None:
    # Mutant: the `failed` check removed -> reads current, red here.
    repo = _repo(tmp_path)
    rec = json.loads(COMMITTED.read_text())
    rec["evidence"][1]["result"] = "fail"
    record = _record(repo, evidence=rec["evidence"])
    v = _state(repo, record)
    assert v["state"] == "failing", v
    assert "skillc-529-d3" in v["reason"]


@pytest.mark.parametrize("damage", [
    "absent", "not-json", "schema", "missing-limits-key", "empty-limits",
    "bad-population", "evidence-without-result", "evidence-without-sha",
    "no-closure-digest", "bad-date", "live-without-evidence",
])
def test_unreadable_records_read_unknown(tmp_path: Path, damage: str) -> None:
    # Mutant: `unknown(...)` for a missing required field replaced by a default
    # -> that row reads current, red here.
    repo = _repo(tmp_path)
    record = _record(repo)
    rec = json.loads(record.read_text())
    if damage == "absent":
        record.unlink()
    elif damage == "not-json":
        record.write_text("{not json")
    else:
        if damage == "schema":
            rec["schema"] = 2
        elif damage == "missing-limits-key":
            rec.pop("limits")
        elif damage == "empty-limits":
            rec["limits"] = []
        elif damage == "bad-population":
            rec["population"] = "vibes"
        elif damage == "evidence-without-result":
            rec["evidence"][0].pop("result")
        elif damage == "evidence-without-sha":
            rec["evidence"][0]["skillc_sha"] = ""
        elif damage == "no-closure-digest":
            rec["evaluated"].pop("closure_digest")
        elif damage == "bad-date":
            rec["review_by"] = "soon"
        elif damage == "live-without-evidence":
            rec["evidence"] = []
        record.write_text(json.dumps(rec))
    v = _state(repo, record)
    assert v["state"] == "unknown", (damage, v)


def test_changed_skill_content_reads_stale_content(tmp_path: Path) -> None:
    # Mutant: `content_stale` forced False -> reads current, red here.
    repo = _repo(tmp_path)
    record = _record(repo)
    (repo / "codex" / "skills" / "flow-check" / "scripts" / "flow-finish-gate.sh").write_text("changed\n")
    v = _state(repo, record)
    assert v["state"] == "stale-content", v
    assert any("is not the evaluated" in n for n in v["notes"])


def test_a_new_file_in_the_closure_reads_stale_content(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    record = _record(repo)
    (repo / "codex" / "skills" / "flow-check" / "new.md").write_text("added\n")
    assert _state(repo, record)["state"] == "stale-content"


def test_a_helper_made_non_executable_reads_stale_content(tmp_path: Path) -> None:
    # Counter-model review: a mode-only change moves no byte, yet it is the
    # degraded treatment ADR 0011's review trigger names. Mutant: the exec bit
    # dropped from closure_digest -> reads current, red here.
    repo = _repo(tmp_path)
    record = _record(repo)
    gate = repo / "codex" / "skills" / "flow-check" / "scripts" / "flow-finish-gate.sh"
    assert gate.stat().st_mode & 0o111, "precondition: the helper starts executable"
    gate.chmod(0o644)
    assert _state(repo, record)["state"] == "stale-content"


@pytest.mark.parametrize("counts", [(0, 0), (5, 0), (None, None), (2, 3), ("5", "5")])
def test_evidence_without_observations_reads_unknown(tmp_path: Path, counts) -> None:
    # Counter-model review: an evidence item must describe observations. Not a
    # pass-rate bar - no rate is computed. Mutant: the counts check removed ->
    # reads current, red here.
    repo = _repo(tmp_path)
    rec = json.loads(COMMITTED.read_text())
    for item in rec["evidence"]:
        if counts[0] is None:
            item.pop("attempts")
            item.pop("evaluable")
        else:
            item["attempts"], item["evaluable"] = counts
    v = _state(repo, _record(repo, evidence=rec["evidence"]))
    assert v["state"] == "unknown", (counts, v)


def test_evidence_only_for_another_family_reads_unknown(tmp_path: Path) -> None:
    # Counter-model review: #279 measures flow:auto. A record whose only
    # evidence is for another family must not read current. Mutant: the
    # applicability check removed -> reads current, red here.
    repo = _repo(tmp_path)
    rec = json.loads(COMMITTED.read_text())
    only_279 = [item for item in rec["evidence"] if item["family"] == "flow:auto"]
    assert only_279 and all(item["family"] != rec["family"] for item in only_279), "precondition"
    v = _state(repo, _record(repo, evidence=only_279))
    assert v["state"] == "unknown" and "another family" in v["reason"], v


@pytest.mark.parametrize("field,value", [
    ("adr", None), ("family", ""), ("review_trigger", None), ("review_by_reversal_trigger", 7),
    ("evidence.source_url", {"url": "x"}), ("evidence.skillc_sha", ["abc"]), ("evidence.family", None),
])
def test_present_but_unusable_fields_read_unknown(tmp_path: Path, field: str, value) -> None:
    # Counter-model review: presence is not usability. Mutant: the type checks
    # removed -> these rows read current, red here.
    repo = _repo(tmp_path)
    rec = json.loads(COMMITTED.read_text())
    if field.startswith("evidence."):
        for item in rec["evidence"]:
            item[field.split(".", 1)[1]] = value
        record = _record(repo, evidence=rec["evidence"])
    else:
        record = _record(repo, **{field: value})
    assert _state(repo, record)["state"] == "unknown", (field, value)


def test_past_review_by_reads_stale_aged_and_names_the_reversal_trigger(tmp_path: Path) -> None:
    # Mutant: the `aged` comparison removed -> reads current, red here.
    repo = _repo(tmp_path)
    record = _record(repo)
    v = _state(repo, record, today=date(2027, 1, 22))
    assert v["state"] == "stale-aged", v
    assert any("LENGTHEN review_by" in n for n in v["notes"]), v["notes"]
    assert _state(repo, record, today=date(2027, 1, 21))["state"] == "current", "review_by is inclusive"


def test_fixture_population_is_never_presented_as_evidence(tmp_path: Path) -> None:
    # Mutant: the fixture branch removed -> reads current, red here.
    repo = _repo(tmp_path)
    v = _state(repo, _record(repo, population="fixture"))
    assert v["state"] == "fixture", v
    assert "not behavioural evidence" in "\n".join(enroll.render(v))


# --------------------------------------------------------------------------- #
# Refusals: no universal threshold, no unproven blocking
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("key", ["pass_rate", "threshold", "min_pass", "nested"])
def test_a_pass_rate_threshold_is_refused_not_ignored(tmp_path: Path, key: str) -> None:
    # Mutant: `_threshold_keys` returns [] -> the record reads current, red here.
    repo = _repo(tmp_path)
    if key == "nested":
        rec = json.loads(COMMITTED.read_text())
        rec["evidence"][0]["passRate"] = 0.8
        record = _record(repo, evidence=rec["evidence"])
    else:
        record = _record(repo, **{key: 0.8})
    v = _state(repo, record)
    assert v["state"] == "unknown" and "threshold is refused" in v["reason"], v


@pytest.mark.parametrize("flip", ["unproven", "claimed-complete"])
def test_a_blocking_decision_is_refused(tmp_path: Path, flip: str) -> None:
    # Mutant: the blocking refusal removed -> a "blocking" record reads current.
    repo = _repo(tmp_path)
    rec = json.loads(COMMITTED.read_text())
    if flip == "claimed-complete":
        rec["flip"].update(discrimination="DISCRIMINATING", improvement="IMPROVED",
                           certified_pairing="case-1/rev-x")
    v = _state(repo, _record(repo, decision="blocking", flip=rec["flip"]))
    assert v["state"] == "unknown" and "blocking decision is not read" in v["reason"], v


# --------------------------------------------------------------------------- #
# Exit codes: distinct per state without --advisory; 0 for every printed verdict with it
# --------------------------------------------------------------------------- #
def test_each_state_has_its_own_exit_code(tmp_path: Path) -> None:
    # Mutant: EXIT maps every non-current state to 1 (the always-1 shape this
    # consumer exists not to repeat) -> the uniqueness assertion fails.
    assert sorted(enroll.EXIT.values()) == sorted(set(enroll.EXIT.values())), enroll.EXIT
    assert enroll.EXIT["current"] == 0
    assert 1 not in enroll.EXIT.values(), "1 is a Python traceback, never a verdict"
    repo = _repo(tmp_path)
    good = _record(repo)
    assert _run(repo, good).returncode == 0
    (repo / "codex" / "skills" / "flow-check" / "SKILL.md").write_text("changed")
    assert _run(repo, good).returncode == enroll.EXIT["stale-content"]
    assert _run(repo, repo / "missing.json").returncode == enroll.EXIT["unknown"]


@pytest.mark.parametrize("state_maker", ["unknown", "stale-content", "failing", "fixture"])
def test_advisory_never_fails_a_printed_verdict(tmp_path: Path, state_maker: str) -> None:
    # Mutant: --advisory returns EXIT[state] -> exits non-zero here, red.
    repo = _repo(tmp_path)
    record = _record(repo)
    if state_maker == "unknown":
        record = repo / "missing.json"
    elif state_maker == "stale-content":
        (repo / "codex" / "skills" / "flow-check" / "SKILL.md").write_text("changed")
    elif state_maker == "failing":
        rec = json.loads(COMMITTED.read_text())
        rec["evidence"][0]["result"] = "fail"
        record = _record(repo, evidence=rec["evidence"])
    elif state_maker == "fixture":
        record = _record(repo, population="fixture")
    result = _run(repo, record, "--advisory")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("eval-enrollment: "), "a verdict was printed"


def test_usage_error_is_64_not_a_verdict_code() -> None:
    result = subprocess.run([sys.executable, str(SCRIPT), "--today", "nope"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 64, result.stderr


# --------------------------------------------------------------------------- #
# The committed record and its relation to the coverage checker
# --------------------------------------------------------------------------- #
def test_committed_record_is_readable_and_advisory() -> None:
    # Not pinned to `current`: a later flow-check change makes it STALE
    # (content), which is a correct reading, not a test failure. It must never
    # be unknown, failing or fixture, and must stay advisory.
    v = enroll.evaluate(COMMITTED, ROOT, TODAY)
    assert v["state"] in ("current", "stale-content", "stale-aged"), v
    rec = json.loads(COMMITTED.read_text())
    assert rec["decision"] == "advisory" and rec["population"] == "live-single-arm"
    assert rec["review_by"] == "2027-01-21"
    assert len(rec["limits"]) == 4
    for item in rec["evidence"]:
        assert item["source_url"].startswith("https://github.com/cooneycw/skillc/issues/")
        assert item["skillc_sha"]


def test_closure_digest_definition_matches_the_coverage_checker(tmp_path: Path) -> None:
    coverage = _load(ROOT / "scripts" / "check-skill-coverage-map.py", "coverage_map_for_test")
    repo = _repo(tmp_path)
    root = repo / "codex" / "skills" / "flow-check"
    assert enroll.digest_tree(root) == coverage.digest_tree(root)
    real = ROOT / "codex" / "skills" / "flow-check"
    assert enroll.digest_tree(real) == coverage.digest_tree(real)
