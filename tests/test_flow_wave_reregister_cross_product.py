"""#1762's 196 owner-ruled outcomes, retaining the measured pre-fix states for comparison.

Seven states per identity include omitted and explicit-empty flags separately.
Cross these with supplied/omitted files and complete PR observations. Every
case starts with actual register/overtake evidence, not fabricated zero values.
The older 29-row matrix separately repeats its scenarios across three cwd shapes.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from tests import test_flow_wave_reregister_matrix as matrix
from tests.test_flow_wave_registry import _detail, _run, _verdict

CASES = json.loads((Path(__file__).parent / "fixtures/flow-wave-reregister-cross-product/cases.json").read_text())
FIELDS = ("issue", "repo", "files", "pr", "base", "diff", "obs_repo", "overtaken")


@pytest.fixture(scope="module")
def cross_places(tmp_path_factory):
    # Reuse the owned real repo / linked worktree / outside-repo shape builder.
    return matrix.places.__wrapped__(tmp_path_factory)


@pytest.fixture(scope="module")
def seeds(tmp_path_factory, cross_places):
    values = {}
    for issue, repo in itertools.product(("", "1710"), ("", "{repo}")):
        root = tmp_path_factory.mktemp("cross-seed")
        for flags in (matrix._first(issue, repo), matrix._overtake(issue, repo)):
            result = _run(root, "register", matrix.ROLE, "--wave", matrix.WAVE,
                          *matrix._args(flags, cross_places), cwd=cross_places["plain"])
            assert result.returncode == 0, result.stdout + result.stderr
        data = json.loads((root / "reg/registry.json").read_text())
        before = data[matrix.WAVE]["roles"][matrix.ROLE]
        assert before["files"] == "a.py,b.py" and before["pr"] == "55"
        assert before["overtaken"] == 1
        assert before["issue"] == issue
        assert before["repo"] == matrix._fill(repo, cross_places)
        values[(bool(issue), bool(repo))] = data
    return values


def _flag(transition, name, places):
    state = transition.split("/")[1]
    if state == "omitted":
        return []
    if state == "explicit-empty":
        return [name, ""]
    value = ("{other}" if state == "different" else "{repo}") if name == "--repo" else (
        "1711" if state == "different" else "1710"
    )
    return [name, str(matrix._fill(value, places))]


@matrix.requires_tools
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_chosen_reregister_cross_product(tmp_path, cross_places, seeds, case):
    old_issue = case["issue"].startswith("present/")
    old_repo = case["repo"].startswith("present/")
    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(seeds[(old_issue, old_repo)]))
    before = json.loads(registry.read_text())[matrix.WAVE]["roles"][matrix.ROLE]
    assert before["files"] == "a.py,b.py"
    assert (before["pr"], before["base"], before["diff"]) == ("55", "base-2", "diff-1")
    assert before["overtaken"] == 1
    assert bool(before["issue"]) == old_issue and bool(before["repo"]) == old_repo
    flags = [*_flag(case["issue"], "--issue", cross_places),
             *_flag(case["repo"], "--repo", cross_places)]
    if case["files"]:
        flags.extend(["--files", "c.py"])
    if case["pr"]:
        flags.extend(["--pr", "77", "--base", "new-base", "--diff", "new-diff"])
    original_bytes = registry.read_bytes()
    result = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                  *flags, cwd=cross_places["plain"])
    assert result.returncode == case["chosen"]["exit"], result.stdout + result.stderr
    if case["chosen"]["exit"] == 1:
        assert _verdict(result) == "refused"
        assert registry.read_bytes() == original_bytes
        return
    assert _verdict(result) == "updated"
    after = json.loads(registry.read_text())[matrix.WAVE]["roles"][matrix.ROLE]
    expected = {key: matrix._fill(value, cross_places) for key, value in case["chosen"]["expected"].items()}
    assert {key: after[key] for key in FIELDS} == expected
    assert _detail(result, "FLOW_WAVE_FILES") == (expected["files"] or "-")
    dropped = "a.py,b.py" if case["files"] else "-"
    assert _detail(result, "FLOW_WAVE_FILES_DROPPED") == dropped
    assert _detail(result, "FLOW_WAVE_FILES_ADDED") == ("c.py" if case["files"] else "-")
    assert (" DROPPED " in result.stderr) == (dropped != "-")


def test_cross_product_fixture_has_every_input_and_both_current_move_outcomes():
    states = {"absent/omitted", "absent/present", "present/omitted", "present/same",
              "present/different", "absent/explicit-empty", "present/explicit-empty"}
    expected = set(itertools.product(states, states, (False, True), (False, True)))
    observed = {(c["issue"], c["repo"], c["files"], c["pr"]) for c in CASES}
    assert len(CASES) == len(observed) == 196
    assert observed == expected
    assert sum(c["chosen"]["exit"] == 1 for c in CASES) == 99
    # Positive and negative populations for retention, not an all-preserve table.
    assert any(c["expected"]["files"] == "" for c in CASES)
    assert any(c["expected"]["files"] == "a.py,b.py" for c in CASES)
    assert {c["expected"]["overtaken"] for c in CASES} == {0, 1}


@matrix.requires_tools
def test_withdrawal_has_plain_caller_line_and_nested_roster_note(tmp_path, cross_places, seeds):
    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(seeds[(True, True)]))
    before = json.loads(registry.read_text())[matrix.WAVE]["roles"][matrix.ROLE]
    assert before["pr"] == "55" and before["overtaken"] == 1
    result = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE, "--clear-pr",
                  cwd=cross_places["plain"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "merge observation withdrawn" in result.stderr
    listed = _run(tmp_path, "list", "--wave", matrix.WAVE, "--json")
    # list has a trailing verdict: its JSON object is the first document.
    data, _ = json.JSONDecoder().raw_decode(listed.stdout)
    assert "merge observation withdrawn" in data[matrix.ROLE]["work_note"]
    human = _run(tmp_path, "list", "--wave", matrix.WAVE)
    assert "merge observation withdrawn" in human.stdout
