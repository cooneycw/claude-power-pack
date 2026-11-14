"""Concrete terra-review counterexamples for #1762."""
import json

import pytest

from tests import test_flow_wave_reregister_matrix as matrix
from tests.test_flow_wave_registry import _run, _verdict
from tests.test_flow_wave_reregister_cross_product import cross_places, seeds  # noqa: F401

pytestmark = matrix.requires_tools


def test_unopenable_lock_is_io_error_not_work_refusal(tmp_path, cross_places, seeds):  # noqa: F811
    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    registry.write_text(json.dumps(seeds[(True, True)]))
    lock = registry.parent / "registry.lock"
    lock.mkdir()
    assert lock.is_dir(), "a directory cannot be opened as the lock output file"
    before = registry.read_bytes()
    done = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                cwd=cross_places["plain"])
    assert done.returncode == 3 and _verdict(done) == "error", done.stdout + done.stderr
    assert registry.read_bytes() == before


def _released_legacy(seeds):  # noqa: F811
    data = json.loads(json.dumps(seeds[(True, True)]))
    previous = data[matrix.WAVE]["roles"][matrix.ROLE]
    previous["released"] = True
    # A row released before #1222: it kept its lane, observation and count.
    assert previous["files"] == "a.py,b.py" and previous["pr"] == "55" and previous["overtaken"] == 1
    assert (previous["base"], previous["diff"]) == ("base-2", "diff-1") and previous["issue"] == "1710"
    return data, previous


RELEASED_FLAGS = {
    "omitted": (), "issue-only": ("--issue", "1710"),
    "full-same": ("--issue", "1710", "--repo", "{repo}"),
    "different": ("--issue", "1711", "--repo", "{repo}"),
}


@pytest.mark.parametrize("mode", list(RELEASED_FLAGS))
def test_released_legacy_reuse_starts_empty(
    tmp_path, cross_places, seeds, monkeypatch, mode,  # noqa: F811
):
    """Released means gone (#1804, owner ruling 2026-11-14).

    The same inputs run through the pre-#1762 anchor first: there the first
    three modes restore the old files, PR and count, which is the red case
    this test exists to tell apart from the fix.
    """
    from tests import test_flow_wave_registry as registry_module

    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    data, previous = _released_legacy(seeds)
    before = json.dumps(data)
    flags = tuple(previous["repo"] if f == "{repo}" else f for f in RELEASED_FLAGS[mode])
    current = registry_module.REGISTRY
    anchor = current.parents[1] / "controls/flow-wave-reregister-work/anchors/pre-1762-flow-wave-registry.sh"
    measured = {}
    for name, helper in (("anchor", anchor), ("branch", current)):
        registry.write_text(before)
        monkeypatch.setattr(registry_module, "REGISTRY", helper)
        done = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                    *flags, cwd=cross_places["plain"])
        assert done.returncode == 0, done.stdout + done.stderr
        active = json.loads(registry.read_text())[matrix.WAVE]["roles"][matrix.ROLE]
        assert active["released"] is False
        measured[name] = active
    old = measured["anchor"]
    if mode == "different":
        assert old["files"] == "" and old["pr"] == "" and old["overtaken"] == 0
    else:
        assert old["files"] == "a.py,b.py" and old["pr"] == "55" and old["overtaken"] == 1, \
            "the anchor must still reactivate legacy work, or this test cannot fail"
    new = measured["branch"]
    for key in ("files", "pr", "base", "diff", "obs_repo"):
        assert new[key] == "", (key, new)
    assert new["overtaken"] == 0
    assert new["issue"] == {"omitted": "", "different": "1711"}.get(mode, "1710")
    assert new["repo"] == previous["repo"]


def test_released_legacy_restatement_keeps_what_is_supplied(
    tmp_path, cross_places, seeds,  # noqa: F811
):
    """Supplied work wins on a released row, and the count starts from zero.

    Same PR, changed base, same diff would count an overtake against a live
    baseline; against a released one there is no baseline to count from.
    """
    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    data, previous = _released_legacy(seeds)
    registry.write_text(json.dumps(data))
    done = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                "--issue", "1710", "--files", "c.py",
                "--pr", "55", "--base", "base-3", "--diff", "diff-1",
                cwd=cross_places["plain"])
    assert done.returncode == 0, done.stdout + done.stderr
    active = json.loads(registry.read_text())[matrix.WAVE]["roles"][matrix.ROLE]
    assert active["released"] is False
    assert active["files"] == "c.py"
    assert (active["pr"], active["base"], active["diff"]) == ("55", "base-3", "diff-1")
    assert active["overtaken"] == 0
