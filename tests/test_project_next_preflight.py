"""Live recommendation readiness is a selected local observation, never setup."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-next.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("population", ["ready", "missing", "unknown", "malformed", "contradictory"])
def test_live_preflight_validates_only_gh_and_physical_engine(tmp_path, monkeypatch, population):
    project = load("cpp_next_preflight_test", SCRIPT)
    observer = load("cpp_next_observer_test", ROOT / "scripts/flow-preflight.py")
    checks = [observer.check(name, "ok", "controlled") for name in ("gh", "engine")]
    if population in ("missing", "unknown"):
        checks[0]["status"] = population
    report, code = observer.report_for(checks, ("gh", "engine"))
    if population == "malformed":
        report = {}
    elif population == "contradictory":
        report["full_host_ready"] = True

    def observe(args):
        assert args.checks == ("gh", "engine")
        assert Path(args.engine) == SCRIPT.resolve()
        assert Path(args.repo) == tmp_path
        return report, code

    monkeypatch.setattr(observer, "observe", observe)
    monkeypatch.setattr(project, "_load_preflight", lambda: observer, raising=False)
    if population == "ready":
        project._live_preflight(tmp_path)
    else:
        with pytest.raises(project.CollectionError, match="preflight"):
            project._live_preflight(tmp_path)
    collected = []

    def collect(*args):
        collected.append(True)
        raise project.CollectionError("controlled later collection seam")

    monkeypatch.setattr(project, "collect_repository", collect)
    assert project.main([str(tmp_path), "--json"]) == 2
    assert bool(collected) is (population == "ready")


def test_input_and_help_never_observe_live_prerequisites(tmp_path, monkeypatch, capsys):
    project = load("cpp_next_preflight_offline_test", SCRIPT)
    monkeypatch.setattr(project, "_live_preflight", lambda *a: pytest.fail("offline path probed host"), raising=False)
    scenarios = json.loads((ROOT / "tests/project_next/fixtures/scenarios.json").read_text())
    fixture = tmp_path / "state.json"
    fixture.write_text(json.dumps(scenarios["empty_repository"]["state"]))
    assert project.main([str(tmp_path), "--input", str(fixture), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["contract_version"] == "1.7"
    with pytest.raises(SystemExit) as exc:
        project.main(["--help"])
    assert exc.value.code == 0
