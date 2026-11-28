"""Required shape lanes declare historical omissions before fixture setup."""
import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

from lib import ci_shape_check as shape

ROOT = Path(__file__).resolve().parents[1]
REASON = ("CI-shape expected history skip: historical installer execution is outside "
          "the shallow/filtered lane; use separate full-history validation")


def completed():
    nodes = set(shape.REQUIRED_WITNESSES.values()) | set(shape.OPTIONAL_HISTORY_NODES)
    for selector in shape.SELECTORS:
        if selector.endswith("::test_real_historical_installer_population"):
            continue
        nodes.add(selector if "::" in selector else selector + "::test_partner")
    nodes.update(f"tests/test_antigravity_skill_sync.py::test_population[{i}]"
                 for i in range(shape.COLLECTION_FLOOR))
    results = dict(selected=sorted(nodes), outcomes={n: "passed" for n in nodes},
                   skips={}, errors=[], exit=0)
    for node in shape.OPTIONAL_HISTORY_NODES:
        results["outcomes"][node] = "skipped"
        results["skips"][node] = REASON
    assert set(results["skips"]) == set(shape.OPTIONAL_HISTORY_NODES)
    return results


@pytest.mark.parametrize("fault", ["unexpected-pass", "missing-skip", "reason-mismatch"])
def test_completion_rejects_unexpected_historical_outcomes(fault):
    good = completed()
    assert shape.completion(good, 0, "", "local")[0] == "GOOD"
    bad = copy.deepcopy(good)
    node = sorted(shape.OPTIONAL_HISTORY_NODES)[0]
    if fault == "unexpected-pass":
        bad["outcomes"][node] = "passed"
        del bad["skips"][node]
    elif fault == "missing-skip":
        bad["selected"].remove(node)
        del bad["outcomes"][node]
        del bad["skips"][node]
    else:
        bad["skips"][node] = "historical installer skipped for an unexamined reason"
    assert bad != good
    assert shape.completion(bad, 0, "", "local")[0] == "BAD"


def test_manifest_cannot_drop_named_historical_omissions():
    selected = tuple(s for s in shape.SELECTORS
                     if not s.endswith("::test_real_historical_installer_population"))
    assert selected != shape.SELECTORS
    assert not shape.manifest_complete(selected)


@pytest.mark.parametrize("standalone", [False, True], ids=["package", "standalone-collector"])
def test_shape_collector_skips_before_setup_and_leaves_ordinary_pytest_alone(pytester, monkeypatch, standalone):
    tests = pytester.path / "tests"
    tests.mkdir()
    marker = pytester.path / "fixture-ran"
    tests.joinpath("test_host_update_command.py").write_text(
        "import pytest\nfrom pathlib import Path\n"
        "@pytest.fixture\ndef source():\n"
        f"    Path({str(marker)!r}).write_text('setup')\n"
        "    raise AssertionError('ordinary fixture reached')\n"
        "@pytest.mark.parametrize('revision', [0, 1], ids=['real-pre-e32-install', 'real-v13-install'])\n"
        "def test_real_historical_installer_population(source, revision):\n    assert False\n"
        "def test_partner():\n    assert True\n")
    tests.joinpath("test_host_update_source_gc.py").write_text(
        "def test_source_publication_joins_automatic_gc():\n    assert True\n")
    output = pytester.path / "results.json"
    if standalone:
        package = pytester.path / "lib"
        package.mkdir()
        (package / "__init__.py").write_text("")
        shutil.copyfile(ROOT / "lib/ci_shape_pytest.py", package / "ci_shape_pytest.py")
        assert not (package / "ci_shape_check.py").exists()
    monkeypatch.setenv("PYTHONPATH", str(pytester.path if standalone else ROOT))
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("CPP_CI_SHAPE_RESULTS", str(output))
    monkeypatch.setenv("CPP_CI_SHAPE_EXPECTED_SKIPS",
                       json.dumps({node: REASON for node in shape.OPTIONAL_HISTORY_NODES}))
    assert not marker.exists() and not output.exists()
    result = pytester.runpytest_subprocess("-p", "lib.ci_shape_pytest", "--rootdir", str(pytester.path), "-q")
    result.assert_outcomes(passed=2, skipped=2)
    assert not marker.exists(), "shape collector ran a fixture for an excluded historical case"
    payload = json.loads(output.read_text())
    assert set(payload["skips"]) == set(shape.OPTIONAL_HISTORY_NODES)
    assert all(REASON in reason for reason in payload["skips"].values())
    assert payload["outcomes"][shape.REQUIRED_WITNESSES["1958-source-gc"]] == "passed"
    monkeypatch.delenv("CPP_CI_SHAPE_RESULTS")
    ordinary = pytester.runpytest_subprocess("--rootdir", str(pytester.path), "-q")
    ordinary.assert_outcomes(passed=2, errors=2)
    assert marker.exists(), "ordinary pytest did not exercise its normal fixture path"


@pytest.mark.skipif(not shutil.which("git") or not shutil.which("make"), reason="Git and Make required")
def test_controlled_population_receives_its_own_skip_policy(tmp_path, monkeypatch):
    """Controlled checkout/probes observe real child policy, not physical shape."""
    checkout = tmp_path / "checkout"
    package = checkout / "lib"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    shutil.copyfile(ROOT / "lib/ci_shape_pytest.py", package / "ci_shape_pytest.py")
    assert not (package / "ci_shape_check.py").exists()
    (checkout / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    observed = tmp_path / "child-policy.json"
    (checkout / "test_hold.py").write_text(
        "import json,os\nfrom pathlib import Path\n"
        "def test_hold():\n"
        f"    Path({str(observed)!r}).write_text(os.environ['CPP_CI_SHAPE_EXPECTED_SKIPS'])\n")
    stage = tmp_path / "stage"
    stage.mkdir()
    for tool in ("git", "make"):
        binary = shutil.which(tool)
        assert binary is not None
        (stage / tool).symlink_to(binary)
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(shape, "SELECTORS", ("test_hold.py",))
    monkeypatch.setattr(shape, "checkout", lambda *args: checkout)
    monkeypatch.setattr(shape, "observe", lambda *args: ({"controlled_input": True}, {}))
    assert not observed.exists()
    row = shape.run_lane(tmp_path, tmp_path, "controlled", tmp_path / "lane",
                         stage, Path(sys.executable), "local", False, logs, 0o022)
    assert json.loads(observed.read_text()) == {}
    assert row["expected_skips"] == {}
    # This tiny population is intentionally outside full qualification.
    assert row["state"] == "BAD" and row["results"]["outcomes"] == {"test_hold.py::test_hold": "passed"}
