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
    if case["files"] or case["pr"]:
        assert after.get("work_note"), "every successful work change needs a roster note"
        assert after["work_note"] in result.stderr
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


@matrix.requires_tools
@pytest.mark.parametrize("lane_before", [False, True])
def test_move_refusal_uses_the_entry_under_the_write_lock(tmp_path, cross_places, seeds, lane_before):
    import concurrent.futures
    import time

    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    data = json.loads(json.dumps(seeds[(True, True)]))
    data[matrix.WAVE]["roles"][matrix.ROLE]["files"] = "a.py,b.py" if lane_before else ""
    registry.write_text(json.dumps(data))
    pause = tmp_path / "pause"
    pause.mkdir()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            _run, tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
            "--issue", "1711", "--pr", "77", "--base", "b3", "--diff", "d3",
            cwd=cross_places["plain"], extra_env={"FLOW_WAVE_REGISTRY_TEST_PAUSE_REGISTER": str(pause)},
        )
        try:
            deadline = time.monotonic() + 10
            while not (pause / "paused").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert (pause / "paused").exists(), "writer must pause before taking the lock"
            replacement = "" if lane_before else "c.py"
            updated = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                           "--files", replacement, cwd=cross_places["plain"])
            assert updated.returncode == 0
            before_move = registry.read_bytes()
            assert json.loads(before_move)[matrix.WAVE]["roles"][matrix.ROLE]["files"] == replacement
        finally:
            (pause / "release").touch()
        moved = pending.result(timeout=20)
    assert moved.returncode == (0 if lane_before else 1), moved.stdout + moved.stderr
    if not lane_before:
        assert registry.read_bytes() == before_move


@matrix.requires_tools
def test_released_legacy_lane_is_history_not_an_active_claim(tmp_path, cross_places, seeds):
    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    data = json.loads(json.dumps(seeds[(True, True)]))
    data[matrix.WAVE]["roles"][matrix.ROLE]["released"] = True
    registry.write_text(json.dumps(data))
    assert data[matrix.WAVE]["roles"][matrix.ROLE]["files"] == "a.py,b.py"
    done = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                "--issue", "1711", cwd=cross_places["plain"])
    assert done.returncode == 0, done.stdout + done.stderr
    assert "work move" not in done.stderr and "merge observation withdrawn" not in done.stderr


@matrix.requires_tools
@pytest.mark.parametrize("consent", [("--force",), ("--files", ""), ("--clear-pr",)])
def test_force_or_consent_to_only_one_component_cannot_drop_the_other(
    tmp_path, cross_places, seeds, monkeypatch, consent,
):
    from tests import test_flow_wave_registry as registry_module

    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(seeds[(True, True)]))
    before = registry.read_bytes()
    current = registry_module.REGISTRY
    old = current.parents[1] / "controls/flow-wave-reregister-work/anchors/pre-1762-flow-wave-registry.sh"
    # Positive red control: the same existing flags are accepted by pre-fix code.
    monkeypatch.setattr(registry_module, "REGISTRY", old)
    old_answer = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                      "--issue", "1711", *consent, cwd=cross_places["plain"])
    assert old_answer.returncode == 0, old_answer.stdout + old_answer.stderr
    registry.write_bytes(before)
    monkeypatch.setattr(registry_module, "REGISTRY", current)
    done = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                "--issue", "1711", *consent, cwd=cross_places["plain"])
    assert done.returncode == 1 and _verdict(done) == "refused", done.stdout + done.stderr
    assert registry.read_bytes() == before


@matrix.requires_tools
@pytest.mark.parametrize("files,observation", [(False, False), (False, True), (True, False), (True, True)])
def test_reset_consent_resets_only_omitted_components(tmp_path, cross_places, seeds, files, observation):
    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(seeds[(True, True)]))
    flags = ["--issue", "1711", "--allow-work-reset"]
    if files:
        flags += ["--files", "c.py"]
    if observation:
        flags += ["--pr", "77", "--base", "b3", "--diff", "d3"]
    done = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                *flags, cwd=cross_places["plain"])
    assert done.returncode == 0, done.stdout + done.stderr
    after = json.loads(registry.read_text())[matrix.WAVE]["roles"][matrix.ROLE]
    assert after["files"] == ("c.py" if files else "")
    assert after["pr"] == ("77" if observation else "")
    assert after["overtaken"] == 0
    assert after["work_note"] and "role 'w1'" in done.stderr
