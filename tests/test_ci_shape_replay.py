"""Closed runner-replay evidence; parser fixtures are not real execution proof."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest
import yaml

from lib import ci_shape_check as shape
from lib.ci_shape_pytest import Results

ROOT = Path(__file__).resolve().parents[1]
FAULTS = ("missing", "skipped", "duplicate", "empty-selector", "wrong-selector",
          "wrong-node", "corrupt-outcome", "zero-executed", "false-good", "wrong-lane")


def receipt(fault="good"):
    """Controlled receipt data tests the verifier, never authenticates a run."""
    nodes = list(shape.RUNNER_REPLAY_SELECTORS)
    result = {"selected": nodes.copy(), "outcomes": dict.fromkeys(nodes, "passed"),
              "skips": {}, "errors": [], "exit": 0}
    lane = {"name": "depth-1", "state": "GOOD", "reason": "controlled parser input",
            "expected_skips": {}, "preconditions": dict.fromkeys(shape.PRECONDITIONS, True),
            "identity": {"uid": 1000, "euid": 1000}, "test_umask": "022", "results": result,
            "exit": 0, "diagnostic": ""}
    record = {"schema": 1, "commit": "a" * 40, "tier": "local", "image": shape.image_pin(ROOT),
              "selectors": nodes.copy(), "lanes": [lane], "state": "GOOD", "reason": "fixture",
              "root": {"state": "UNKNOWN", "reason": "not examined: needs real uid 0"},
              "pytest_time_umask": {"state": "GOOD", "image": shape.image_pin(ROOT),
                                    "umask": 0o022, "evidence": "controlled parser fixture"}}
    return damage(record, fault)


def damage(record, fault):
    lane = record["lanes"][0]
    result = lane["results"]
    nodes = list(shape.RUNNER_REPLAY_SELECTORS)
    node = nodes[0]
    if fault == "missing":
        result["selected"].remove(node)
        del result["outcomes"][node]
        assert node not in result["selected"] and node not in result["outcomes"]
    elif fault == "skipped":
        result["outcomes"][node] = "skipped"
        result["skips"][node] = "requires make"
        assert result["outcomes"][node] != "passed"
    elif fault == "duplicate":
        result["selected"].append(node)
        assert len(result["selected"]) > len(set(result["selected"]))
    elif fault == "empty-selector":
        record["selectors"] = []
        assert not record["selectors"]
    elif fault == "wrong-selector":
        record["selectors"] = ["tests/test_runner.py"]
        assert record["selectors"] != nodes
    elif fault == "wrong-node":
        other = "tests/test_runner.py::TestNeighbour::test_unrelated"
        result["selected"][0] = other
        result["outcomes"][other] = result["outcomes"].pop(node)
        assert len(result["selected"]) == 41 and node not in result["selected"]
    elif fault == "corrupt-outcome":
        result["outcomes"][node] = "passed-but-not-terminal"
        assert result["outcomes"][node] not in {"passed", "skipped", "failed"}
    elif fault == "zero-executed":
        result["outcomes"] = {}
        assert not result["outcomes"]
    elif fault == "false-good":
        result["errors"].append("producer claimed GOOD without completion")
        assert record["state"] == "GOOD" and result["errors"]
    elif fault == "wrong-lane":
        lane["name"] = "depth-1-tree-0"
        assert lane["name"] != "depth-1"
    lane["counts"] = {"selected": len(result["selected"]),
                      "executed": sum(x != "skipped" for x in result["outcomes"].values()),
                      "skipped": len(result["skips"])}
    return record


def verdict(record, **kwargs):
    return shape.assess(record, tier=record["tier"], commit=record["commit"],
                        image=record["image"], profile="runner-replay", **kwargs)


def test_replay_good_is_exactly_the_committed_41_once():
    record = receipt()
    assert len(record["selectors"]) == len(set(record["selectors"])) == 41
    assert verdict(record)[0] == "GOOD"
    assert shape.assess(record, tier=record["tier"], commit=record["commit"],
                        image=record["image"])[0] == "BAD", "default verifier must not infer another profile"


@pytest.mark.parametrize("fault", FAULTS)
def test_replay_requires_every_named_node_once_without_skips(fault):
    record = receipt(fault)
    assert verdict(record)[0] == "BAD"


def test_replay_keeps_commit_image_tier_and_counts_bound():
    record = receipt()
    for key, value in (("commit", "0" * 40), ("image", "wrong"), ("tier", "other")):
        bad = copy.deepcopy(record)
        bad[key] = value
        assert bad[key] != record[key]
        assert shape.assess(bad, tier=record["tier"], commit=record["commit"],
                            image=record["image"], profile="runner-replay")[0] == "BAD"
    bad = copy.deepcopy(record)
    bad["lanes"][0]["counts"]["executed"] -= 1
    assert bad["lanes"][0]["counts"] != record["lanes"][0]["counts"]
    assert verdict(bad)[0] == "BAD"


def test_collector_rejects_two_call_reports_for_one_replay_node(monkeypatch):
    monkeypatch.setenv("CPP_CI_SHAPE_EXPECTED_SKIPS", "{}")
    monkeypatch.setenv("CPP_CI_SHAPE_EXACT_EXECUTION", "1")
    collector = Results()
    report = types.SimpleNamespace(nodeid=shape.RUNNER_REPLAY_SELECTORS[0], when="call",
                                   failed=False, skipped=False)
    collector.pytest_runtest_logreport(report)
    collector.pytest_runtest_logreport(report)
    assert len(collector.outcomes) == 1
    assert collector.errors, "a second PASS must not disappear into the outcome dictionary"


def test_required_replay_is_a_sibling_and_replaces_the_serial_tail():
    steps = yaml.safe_load((ROOT / ".woodpecker.yml").read_text())["steps"]
    assert "runner-replay" in steps
    replay = steps["runner-replay"]
    assert replay["image"] == steps["validate"]["image"]
    assert set(replay["depends_on"]) == {
        "secret-scan", "make-stage", "git-stage", "codex-skills-generate"}
    assert "validate" not in replay["depends_on"]
    assert any("CI_SHAPE_PROFILE=runner-replay" in command for command in replay["commands"])
    assert all("SubsumedGates or ResumeSettlesDeferredGates" not in command
               for command in steps["validate"]["commands"])


def test_manifest_matches_independent_class_collection_not_execution(tmp_path):
    output = tmp_path / "collection.json"
    env = {k: v for k, v in os.environ.items() if k != "CPP_TEST_CODEX_SKILLS_BUILT"}
    env.update(CPP_CI_SHAPE_RESULTS=str(output), CPP_CI_SHAPE_EXPECTED_SKIPS="{}",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    result = subprocess.run([
        sys.executable, "-m", "pytest", "-n0", "--collect-only", "-q",
        "-p", "lib.ci_shape_pytest", "-p", "xdist.plugin", "-p", "pytest_timeout",
        "tests/test_runner.py::TestSubsumedGates",
        "tests/test_runner.py::TestResumeSettlesDeferredGates",
    ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    collected = json.loads(output.read_text())
    assert collected["outcomes"] == {}, "collect-only is not execution evidence"
    assert len(collected["selected"]) == len(set(collected["selected"])) == 41
    assert set(collected["selected"]) == set(shape.RUNNER_REPLAY_SELECTORS)


@pytest.mark.skipif(not shutil.which("git") or not shutil.which("make"), reason="Git and Make required")
@pytest.mark.parametrize("fault,expected", [("good", "GOOD"), ("skipped", "BAD"),
                                            ("duplicate-report", "BAD"), ("make", "UNKNOWN")])
def test_real_private_lane_and_collector(tmp_path, fault, expected):
    spec = importlib.util.spec_from_file_location(
        "replay_control", ROOT / "controls/ci-shape-runner-replay/run-case.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    record = module.fixture(tmp_path, fault)
    assert shape.assess(record, tier=record["tier"], commit=record["commit"],
                        image=record["image"], profile="runner-replay")[0] == expected


@pytest.mark.skipif(not shutil.which("git"), reason="Git required for actual checkout binding")
@pytest.mark.parametrize("fault,expected", [("good", 0), ("false-good", 1)])
def test_ci_consumer_checks_producer_evidence_before_named_passes(tmp_path, monkeypatch, capsys, fault, expected):
    spec = importlib.util.spec_from_file_location("replay_cli", ROOT / "scripts/ci-shape-check.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    source = tmp_path / "source"
    source.mkdir()
    pin = shape.image_pin(ROOT)
    (source / ".woodpecker.yml").write_text(
        f"steps:\n  validate:\n    image: {pin}\n  runner-replay:\n    image: {pin}\n")
    env = {"PATH": os.environ["PATH"], "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    git = ["git", "-C", str(source), "-c", "user.name=Fixture", "-c",
           "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
           "-c", "core.hooksPath=/dev/null", "-c", "gc.autoDetach=false"]
    for args in (("init", "-q"), ("add", "."), ("commit", "-qm", "controlled CI entry")):
        subprocess.run([*git, *args], env=env, check=True, capture_output=True)
    head = subprocess.check_output([*git, "rev-parse", "HEAD"], env=env, text=True).strip()
    record = receipt(fault)
    record.update(tier="image", commit=head,
                  root={"state": "GOOD", "reason": "real uid 0 in pinned validate image"})
    record["lanes"][0]["identity"] = {"uid": 0, "euid": 0}
    # Controlled identity/producer is a consumer test, not actual root proof.
    monkeypatch.setattr(os, "getuid", lambda: 0)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setenv("CI", "woodpecker")
    monkeypatch.setenv("CI_PIPELINE_NUMBER", "1")
    monkeypatch.setenv("CI_COMMIT_SHA", head)
    monkeypatch.setattr(cli, "ROOT", source)
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: record)
    monkeypatch.setattr(sys, "argv", [str(ROOT / "scripts/ci-shape-check.py"), "ci",
                                     "--profile", "runner-replay", "--receipt", str(tmp_path / "out.json")])
    assert cli.main() == expected
    output = capsys.readouterr().out
    named = [line for line in output.splitlines() if line.startswith("RUNNER_REPLAY_NODE:")]
    assert len(named) == (41 if expected == 0 else 0)
    assert len(named) == len(set(named))


@pytest.mark.skipif(not shutil.which("git"), reason="Git required for checkout identity probe")
@pytest.mark.parametrize("fault", ["empty", "duplicate", "neighbour"])
def test_invalid_committed_profile_cannot_fall_through_to_all_tests(tmp_path, monkeypatch, fault):
    nodes = shape.RUNNER_REPLAY_SELECTORS
    changed = () if fault == "empty" else (
        (*nodes[:-1], nodes[0]) if fault == "duplicate" else ("tests/test_neighbour.py", *nodes[1:]))
    assert len(changed) != 41 or len(set(changed)) != 41 or changed[0] != nodes[0]
    monkeypatch.setattr(shape, "RUNNER_REPLAY_SELECTORS", changed)
    def forbidden(*args, **kwargs):
        pytest.fail("invalid selection launched pytest")
    monkeypatch.setattr(shape, "_owned_pytest", forbidden)
    tier = "image" if os.getuid() == 0 else "local"
    record = shape.run(ROOT, tier, tmp_path / "refused.json", profile="runner-replay",
                       inside_image=shape.image_pin(ROOT) if tier == "image" else None)
    assert record["state"] == "UNKNOWN" and "manifest" in record["reason"]
