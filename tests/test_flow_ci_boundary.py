"""#1758 approved boundary regressions; implementation awaits coordination posting.

The attribution case preserves existing behavior and proves a constructed blind
variant accepts the very same mismatched producer report. It is not a regression
against current main. All transport replies and checkout state are fixture owned.
"""

import inspect
import json
import subprocess
from pathlib import Path

import pytest

from tests.test_flow_ci_status import (
    SHA,
    STARTED,
    _gha_gh,
    _gha_run,
    _markers,
    _run,
    _stall_routes,
    _write_fake_curl,
    requires_bash,
)


@pytest.fixture(name="boundary_env")
def boundary_env_fixture(tmp_path, monkeypatch):
    # Do not discover a real ancestor checkout: it can normalize uppercase SHAs
    # and conceal the fallback path's missing normalization.
    for name in ("CPP_FLOW_CI_BACKEND", "CPP_FLOW_CI_WORKER", "BASH_ENV"):
        monkeypatch.delenv(name, raising=False)
    return {"GIT_CEILING_DIRECTORIES": str(tmp_path.parent),
            "FLOW_CI_NOW": str(STARTED + 71 * 60)}


def record(tmp_path, provider):
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir(exist_ok=True)
    config.write_text(json.dumps({"pipeline": {"providers": [provider]}}))


def wp_env(tmp_path, boundary_env, routes=None):
    calls = tmp_path / "curl.log"
    routes = routes if routes is not None else _stall_routes("running")
    curl = _write_fake_curl(tmp_path / "bin", routes, calls)
    return {**boundary_env, "FLOW_CI_CURL": str(curl)}, calls


@requires_bash
@pytest.mark.parametrize("provider", ["woodpecker", "github-actions"])
@pytest.mark.parametrize("wait", [False, True])
@pytest.mark.parametrize("recorded", [False, True])
def test_stalled_exit_code_is_one_in_every_public_mode(
        tmp_path, boundary_env, provider, wait, recorded):
    env, _ = wp_env(tmp_path, boundary_env)
    if provider == "github-actions":
        run = _gha_run(19, None, event="push", status="in_progress",
                       started="2020-01-01T00:00:00Z")
        assert run["status"] == "in_progress"
        env.update(FLOW_CI_GH=str(_gha_gh(tmp_path, [run], jobs={19: [
            {"name": "pytest", "status": "in_progress", "conclusion": "",
             "startedAt": run["startedAt"]}]})),
                   FLOW_CI_CURL="/nonexistent/curl", WOODPECKER_API_TOKEN="")
    if recorded:
        record(tmp_path, provider)
    args = [SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "push", "--exit-code"]
    if wait:
        args.extend(["--wait", "1"])
    result = _run(tmp_path, *args, recorded=recorded, env=env)
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["stalled"], result.stdout + result.stderr
    assert result.returncode == 1, result.stdout + result.stderr


@requires_bash
@pytest.mark.parametrize("preset", ["probe", "woodpecker"])
def test_legacy_preset_cannot_override_recorded_actions(tmp_path, boundary_env, preset):
    record(tmp_path, "github-actions")
    env, calls = wp_env(tmp_path, boundary_env)
    env.update(CPP_FLOW_CI_BACKEND=preset,
               FLOW_CI_GH=str(_gha_gh(tmp_path, [_gha_run(19, "success", event="push")])))
    assert preset != "github-actions"
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "push",
                  recorded=True, env=env)
    marks = _markers(result.stdout)
    assert marks["FLOW_CI_STATUS"] == ["success"], result.stdout + result.stderr
    assert marks["FLOW_CI_PROVIDER"] == ["github-actions"]
    assert marks["FLOW_CI_SELECTION"] == ["recorded"]
    assert not calls.exists(), "recorded Actions must not probe Woodpecker"


@requires_bash
def test_nonlocal_uppercase_sha_is_normalized_before_fallback(tmp_path, boundary_env):
    env, _ = wp_env(tmp_path, boundary_env)
    assert SHA.upper() != SHA
    assert not (tmp_path / ".git").exists()
    result = _run(tmp_path, SHA.upper(), "--path", str(tmp_path), "--repo", "o/r",
                  "--event", "push", env=env)
    marks = _markers(result.stdout)
    assert marks["FLOW_CI_REF"] == [SHA], result.stdout + result.stderr
    assert marks["FLOW_CI_STATUS"] == ["stalled"]


@pytest.mark.parametrize("provider_lines,expected", [
    (["woodpecker"], "success"), (["github-actions"], "unknown"),
    ([], "unknown"), (["woodpecker", "woodpecker"], "unknown"),
])
def test_provider_consistency_preserved_and_blind_anchor_detected(
        tmp_path, monkeypatch, capsys, provider_lines, expected):
    """Existing behavior, plus a committed constructed input losing the check."""
    from lib.cicd import flow

    record(tmp_path, "woodpecker")
    output = "".join(f"FLOW_CI_PROVIDER: {p}\n" for p in provider_lines)
    output += f"FLOW_CI_REF: {SHA}\nFLOW_CI_STATUS: success\n"
    assert flow.markers(output)["FLOW_CI_REF"] == [SHA]
    assert flow.markers(output)["FLOW_CI_STATUS"] == ["success"]
    assert (provider_lines == ["woodpecker"]) == (expected == "success")
    calls = []

    def producer(script, args, lane):
        calls.append(lane)
        return subprocess.CompletedProcess([script], 0, output, "")

    monkeypatch.setattr(flow, "shell_status", producer)
    argv = [SHA, "--path", str(tmp_path)]
    code = flow.status_main("owned-backend-not-executed", argv)
    assert flow.markers(capsys.readouterr().out)["FLOW_CI_STATUS"] == [expected]
    assert code == (0 if expected == "success" else 2)
    anchor_path = Path(__file__).parent / "fixtures/flow_ci_boundary/blind-provider-check.json"
    anchor = json.loads(anchor_path.read_text())
    source = inspect.getsource(flow.status_main)
    assert source.count(anchor["remove"]) == 1, "anchor must remove exactly one provider comparison"
    blind_source = source.replace(anchor["remove"], anchor["replace"])
    namespace = dict(vars(flow))
    exec(compile(blind_source, str(anchor_path), "exec"), namespace)
    blind_code = namespace["status_main"]("owned-backend-not-executed", argv)
    assert flow.markers(capsys.readouterr().out)["FLOW_CI_STATUS"] == ["success"]
    assert blind_code == 0
    assert calls == ["woodpecker", "woodpecker"]


@requires_bash
@pytest.mark.parametrize("preset", ["probe", "woodpecker", "github-actions"])
def test_backend_preset_without_optin_cannot_probe_unrecorded_project(tmp_path, boundary_env, preset):
    env, calls = wp_env(tmp_path, boundary_env)
    env["CPP_FLOW_CI_BACKEND"] = preset
    assert not (tmp_path / ".claude/cicd.yml").exists()
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", recorded=True, env=env)
    marks = _markers(result.stdout)
    assert result.returncode == 2, result.stdout + result.stderr
    assert marks["FLOW_CI_SELECTION"] == ["unknown"]
    assert marks["FLOW_CI_PROVIDER"] == ["none"]
    assert not calls.exists(), "legacy preset is not authorization to probe"


@requires_bash
@pytest.mark.parametrize("backend", ["woodpecker", "github-actions"])
def test_explicit_worker_missing_tool_reports_none_with_one_selection(tmp_path, boundary_env, backend):
    env = {**boundary_env, "CPP_FLOW_CI_WORKER": "1", "CPP_FLOW_CI_BACKEND": backend,
           "FLOW_CI_CURL": "/nonexistent/curl", "FLOW_CI_GH": "/nonexistent/gh",
           "WOODPECKER_API_TOKEN": "", "WOODPECKER_SERVER": ""}
    assert not Path(env["FLOW_CI_CURL"]).exists() and not Path(env["FLOW_CI_GH"]).exists()
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", recorded=True, env=env)
    marks = _markers(result.stdout)
    assert marks.get("FLOW_CI_SELECTION") == [f"worker ({backend})"], result.stdout + result.stderr
    assert marks["FLOW_CI_PROVIDER"] == ["none"]
    assert marks["FLOW_CI_STATUS"] == ["unknown"]
    assert result.returncode == 2


@requires_bash
@pytest.mark.parametrize("recorded", [True, False])
def test_public_selection_occurs_once_even_with_explicit_workers(tmp_path, boundary_env, recorded):
    env, _ = wp_env(tmp_path, boundary_env, routes=_stall_routes("success", workflow_state="success", children=[]))
    if recorded:
        record(tmp_path, "woodpecker")
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "push",
                  recorded=recorded, env=env)
    marks = _markers(result.stdout)
    assert len(marks["FLOW_CI_SELECTION"]) == 1, result.stdout + result.stderr
    assert marks["FLOW_CI_SELECTION"][0].startswith("recorded" if recorded else "fallback")
    assert marks["FLOW_CI_STATUS"] == ["success"] and result.returncode == 0
