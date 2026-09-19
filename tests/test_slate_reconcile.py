"""Offline membership checks and exact verdicts for the issue #1099 controls.

Registered fixtures are copied under tmp_path. The GitHub adapter is exercised
only with a mocked subprocess; no test invokes gh or accesses the network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "slate-reconcile.py"
CONTROL = ROOT / "controls" / "slate-reconcile"
REGISTER = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))
CASES = {case["name"]: case for case in REGISTER["cases"]}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GATE = load_module("slate_reconcile", SCRIPT)


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def run(case_dir, script=SCRIPT):
    return subprocess.run(
        [sys.executable, str(script), "--open-set-capture", str(case_dir / "open.json"),
         "--claimed-file", str(case_dir / "claimed.json")],
        cwd=case_dir, capture_output=True, text=True, timeout=10, check=False,
    )


def copy_case(tmp_path, name):
    destination = tmp_path / name
    shutil.copytree(CONTROL / CASES[name]["input"], destination)
    return destination


@pytest.mark.parametrize("name", CASES)
def test_committed_case_exact_verdict_and_signal(tmp_path, name):
    case = CASES[name]
    proc = run(copy_case(tmp_path, name))
    assert proc.returncode == case["expected_exit"], proc.stdout + proc.stderr
    assert proc.stdout.rstrip("\n") == case["expected_output"]
    assert not proc.stderr
    signal = re.compile(REGISTER["detect_signal"], re.MULTILINE)
    assert bool(signal.search(proc.stdout)) == (case["expect"] == "BAD")
    # Every non-clean message prefix is signalled, including UNKNOWN summaries.
    for line in proc.stdout.splitlines():
        assert bool(signal.match(line)) == (case["expect"] == "BAD")


def test_duplicate_while_balanced_catches_both_membership_errors(tmp_path):
    case = copy_case(tmp_path, "bad-duplicate-while-balanced")
    claimed = json.loads((case / "claimed.json").read_text())
    opened = json.loads((case / "open.json").read_text())
    total = sum(len(numbers) for section in ("lanes", "buckets") for numbers in claimed[section].values())
    assert total == len(opened) == 2  # A naive total comparison passes this input.
    proc = run(case)
    assert proc.returncode == 1
    assert "DUPLICATE #101 in lanes.cpp-w1, buckets.backlog" in proc.stdout
    assert "UNACCOUNTED #102" in proc.stdout


def test_membership_floor_messages_are_distinct(tmp_path):
    messages = []
    for name, reason in (
        ("bad-missing-claimed-file", "missing claimed file"),
        ("bad-malformed-claimed-file", "malformed claimed file"),
        ("bad-unusable-open-set", "unusable open-set source"),
    ):
        proc = run(copy_case(tmp_path, name))
        assert proc.returncode == 2
        message = proc.stdout.splitlines()[0]
        assert message.startswith("SLATE-UNKNOWN: " + reason)
        assert "SLATE-OK:" not in proc.stdout
        messages.append(message)
    assert len(set(messages)) == 3


@pytest.mark.parametrize("content", [
    "not JSON", "[]", '{"lanes": {}}', '{"buckets": {}}',
    '{"lanes": [], "buckets": {}}', '{"lanes": {}, "buckets": []}',
    '{"lanes": {"w1": null}, "buckets": {}}',
    '{"lanes": {"w1": [true]}, "buckets": {}}',
    '{"lanes": {"w1": [1.5]}, "buckets": {}}',
    '{"lanes": {}, "buckets": {"backlog": ["101"]}}',
    '{"lanes": {}, "buckets": {"backlog": 101}}',
])
def test_malformed_claims_are_unknown(tmp_path, content):
    write_json(tmp_path / "open.json", [101])
    (tmp_path / "claimed.json").write_text(content)
    proc = run(tmp_path)
    assert proc.returncode == 2
    assert "SLATE-UNKNOWN: malformed claimed file" in proc.stdout
    assert "open=1 claimed=unknown UNACCOUNTED=unknown PHANTOM=unknown DUPLICATE=unknown" in proc.stdout


@pytest.mark.parametrize("content", [None, "not JSON", "{}", "[true]", '["101"]', "[1.5]"])
def test_unusable_capture_is_unknown(tmp_path, content):
    write_json(tmp_path / "claimed.json", {"lanes": {"w1": [101]}, "buckets": {}})
    if content is not None:
        (tmp_path / "open.json").write_text(content)
    proc = run(tmp_path)
    assert proc.returncode == 2
    assert "SLATE-UNKNOWN: unusable open-set source" in proc.stdout
    assert "open=unknown claimed=1 UNACCOUNTED=unknown PHANTOM=unknown DUPLICATE=0" in proc.stdout


def test_empty_lanes_and_buckets_are_verified_empty(tmp_path):
    claims = {"lanes": {"cpp-w3": []}, "buckets": {"backlog": []}}
    write_json(tmp_path / "claimed.json", claims)
    write_json(tmp_path / "open.json", [])
    assert "cpp-w3" in claims["lanes"] and claims["lanes"]["cpp-w3"] == []
    proc = run(tmp_path)
    assert proc.returncode == 0
    assert proc.stdout == "SLATE-OK: open=0 claimed=0 UNACCOUNTED=0 PHANTOM=0 DUPLICATE=0\n"


@pytest.mark.parametrize("claims, locations", [
    ({"lanes": {"w1": [101], "w2": [101]}, "buckets": {}}, "lanes.w1, lanes.w2"),
    ({"lanes": {}, "buckets": {"blocked": [101], "backlog": [101]}}, "buckets.blocked, buckets.backlog"),
    ({"lanes": {"w1": [101, 101]}, "buckets": {}}, "lanes.w1, lanes.w1"),
])
def test_duplicates_need_no_open_set_and_count_distinct_issues(tmp_path, claims, locations):
    write_json(tmp_path / "claimed.json", claims)
    proc = run(tmp_path)  # Missing capture cannot prevent the internal check.
    assert proc.returncode == 2
    assert f"SLATE-FINDING: DUPLICATE #101 in {locations}" in proc.stdout
    assert "open=unknown claimed=1 UNACCOUNTED=unknown PHANTOM=unknown DUPLICATE=1" in proc.stdout
    write_json(tmp_path / "open.json", [101])
    proc = run(tmp_path)
    assert proc.returncode == 1
    assert "open=1 claimed=1 UNACCOUNTED=0 PHANTOM=0 DUPLICATE=1" in proc.stdout


def test_both_unusable_inputs_report_both_errors(tmp_path):
    proc = run(tmp_path)
    assert proc.returncode == 2
    assert "missing claimed file" in proc.stdout
    assert "unusable open-set source" in proc.stdout
    assert "open=unknown claimed=unknown UNACCOUNTED=unknown PHANTOM=unknown DUPLICATE=unknown" in proc.stdout


def test_notes_never_create_claims_or_change_verdicts(tmp_path):
    write_json(tmp_path / "open.json", [101, 102])
    write_json(tmp_path / "claimed.json", {
        "lanes": {"w1": [101]}, "buckets": {},
        "notes": {"102": "Already accounted for", "999": "Not a claim"},
    })
    proc = run(tmp_path)
    assert proc.returncode == 1
    assert "UNACCOUNTED #102" in proc.stdout
    assert "PHANTOM #999" not in proc.stdout


def test_offline_capture_never_invokes_a_subprocess(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("capture mode must not invoke gh")

    monkeypatch.setattr(GATE.subprocess, "run", forbidden)
    for name, case in CASES.items():
        directory = copy_case(tmp_path, name)
        code = GATE.main(["--claimed-file", str(directory / "claimed.json"),
                          "--open-set-capture", str(directory / "open.json")])
        assert code == case["expected_exit"]
        assert capsys.readouterr().out.rstrip("\n") == case["expected_output"]


@pytest.mark.parametrize("response, reason", [
    (subprocess.CompletedProcess([], 0, '[{"number":101}]'), None),
    (subprocess.CompletedProcess([], 0, '[]'), None),
    (subprocess.CompletedProcess([], 4, ''), "gh exited 4"),
    (subprocess.TimeoutExpired("mock gh", 60), "gh timed out"),
    (FileNotFoundError("mock gh"), "cannot run gh"),
    (subprocess.CompletedProcess([], 0, 'invalid'), "malformed gh output"),
    (subprocess.CompletedProcess([], 0, '{}'), "malformed gh output"),
    (subprocess.CompletedProcess([], 0, '[{}]'), "malformed gh output"),
    (subprocess.CompletedProcess([], 0, '[101]'), "malformed gh output"),
    (subprocess.CompletedProcess([], 0, '[{"number":true}]'), "malformed gh output"),
])
def test_live_adapter_is_only_exercised_with_mocked_gh(tmp_path, monkeypatch, capsys, response, reason):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 60
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(GATE.subprocess, "run", fake_run)
    path = write_json(tmp_path / "claimed.json", {"lanes": {}, "buckets": {}})
    code = GATE.main(["--claimed-file", str(path)])
    assert calls == [["gh", "issue", "list", "--repo", "cooneycw/claude-power-pack",
                      "--state", "open", "--json", "number", "--limit", str(GATE.OPEN_LIMIT)]]
    out = capsys.readouterr().out
    if reason:
        assert code == 2
        assert f"SLATE-UNKNOWN: unusable open-set source: {reason}" in out
    elif response.stdout == '[]':
        assert code == 0
        assert "open=0 claimed=0 UNACCOUNTED=0 PHANTOM=0 DUPLICATE=0" in out
    else:
        assert code == 1
        assert "UNACCOUNTED #101" in out


def test_live_adapter_refuses_possibly_truncated_population(monkeypatch):
    monkeypatch.setattr(GATE, "OPEN_LIMIT", 1)
    monkeypatch.setattr(GATE.subprocess, "run",
                        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, '[{"number":101}]'))
    with pytest.raises(ValueError, match="completeness unknown"):
        GATE.read_open_set(None)


def test_default_claims_are_repo_relative_even_from_another_directory(tmp_path):
    gate = tmp_path / "repo" / "scripts" / SCRIPT.name
    gate.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, gate)
    docs = tmp_path / "repo" / "docs"
    docs.mkdir()
    write_json(docs / "slate-lanes.json", {"lanes": {"w1": [101]}, "buckets": {}})
    capture = write_json(tmp_path / "open.json", [101])
    proc = subprocess.run(
        [sys.executable, str(gate), "--open-set-capture", str(capture)],
        cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "open=1 claimed=1" in proc.stdout


def test_constructed_anchor_misses_bad_and_agrees_on_good(tmp_path):
    anchor = REGISTER["anchors"][0]
    script = CONTROL / anchor["path"]
    assert hashlib.sha256(script.read_bytes()).hexdigest() == anchor["sha256"]
    for name in CASES:
        proc = run(copy_case(tmp_path, name), script=script)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert not re.search(REGISTER["detect_signal"], proc.stdout, re.MULTILINE)


def test_negative_controls_harness_agrees_on_registered_cases(tmp_path):
    # Evaluate only this instrument, without scanning repository workflows or
    # running unrelated controls. No git history or ref writes are needed.
    harness = load_module("slate_controls_harness", ROOT / "scripts" / "check-negative-controls.py")
    gate = tmp_path / "scripts" / SCRIPT.name
    gate.parent.mkdir()
    shutil.copyfile(SCRIPT, gate)
    shutil.copytree(CONTROL, tmp_path / "controls" / "slate-reconcile")
    result = harness.evaluate(gate, "controls/slate-reconcile", tmp_path, verify_provenance=False)
    assert result.verdict == harness.PASS, result.details
    assert result.provenance == "unverified"  # Constructed, never historical.
