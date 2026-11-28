"""Closed runner-replay evidence; parser fixtures are not real execution proof."""
import copy
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
