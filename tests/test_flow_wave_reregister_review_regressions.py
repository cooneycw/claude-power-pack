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


@pytest.mark.parametrize("mode", ["omitted", "issue-only", "full-same", "different"])
def test_released_legacy_reuse_characterizes_main_and_this_branch(
    tmp_path, cross_places, seeds, monkeypatch, mode,  # noqa: F811
):
    from tests import test_flow_wave_registry as registry_module

    registry = tmp_path / "reg/registry.json"
    registry.parent.mkdir()
    data = json.loads(json.dumps(seeds[(True, True)]))
    previous = data[matrix.WAVE]["roles"][matrix.ROLE]
    previous["released"] = True
    assert previous["files"] == "a.py,b.py" and previous["pr"] == "55" and previous["overtaken"] == 1
    before = json.dumps(data)
    flags = {
        "omitted": (), "issue-only": ("--issue", "1710"),
        "full-same": ("--issue", "1710", "--repo", previous["repo"]),
        "different": ("--issue", "1711", "--repo", previous["repo"]),
    }[mode]
    current = registry_module.REGISTRY
    main = current.parents[1] / "controls/flow-wave-reregister-work/anchors/pre-1762-flow-wave-registry.sh"
    measured = {}
    for name, helper in (("main", main), ("branch", current)):
        registry.write_text(before)
        monkeypatch.setattr(registry_module, "REGISTRY", helper)
        done = _run(tmp_path, "register", matrix.ROLE, "--wave", matrix.WAVE,
                    *flags, cwd=cross_places["plain"])
        assert done.returncode == 0, done.stdout + done.stderr
        active = json.loads(registry.read_text())[matrix.WAVE]["roles"][matrix.ROLE]
        assert active["released"] is False
        expected_issue = "1711" if mode == "different" else ("" if name == "main" and mode == "omitted" else "1710")
        expected_repo = "" if name == "main" and mode in ("omitted", "issue-only") else previous["repo"]
        assert active["issue"] == expected_issue and active["repo"] == expected_repo
        # Existing legacy reactivation is tracked in #1804, outside #1762.
        expected_files = "" if mode == "different" else "a.py,b.py"
        expected_pr = "" if mode == "different" else "55"
        assert active["files"] == expected_files and active["pr"] == expected_pr
        assert active["overtaken"] == (0 if mode == "different" else 1)
        measured[name] = {key: active[key] for key in ("issue", "repo", "files", "pr", "overtaken")}
    assert measured["main"]["files"] == measured["branch"]["files"]
    print(json.dumps({"mode": mode, "measured": measured}))
