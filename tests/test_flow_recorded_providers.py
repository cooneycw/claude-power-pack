"""Recorded provider routing must precede any provider probes (#1610 A)."""

from pathlib import Path

import pytest

from tests.test_flow_ci_status import (
    SHA,
    _gha_gh,
    _gha_run,
    _markers,
    _run,
    _write_fake_curl,
    requires_bash,
)


@requires_bash
def test_actions_record_cannot_be_claimed_by_a_woodpecker_known_repo(tmp_path: Path):
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [github-actions]\n")
    calls = tmp_path / "curl.log"
    curl = _write_fake_curl(tmp_path / "bin", {"/lookup/": {"id": 7}, "/pipelines?": []}, calls)
    gh = _gha_gh(tmp_path, [_gha_run(19, "success")])
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "pull_request",
                  recorded=True, env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    marks = _markers(result.stdout)
    assert marks["FLOW_CI_PROVIDER"] == ["github-actions"], result.stdout + result.stderr
    assert marks["FLOW_CI_STATUS"] == ["success"]
    assert not calls.exists(), "Actions selection must never probe Woodpecker credentials or API"


@requires_bash
def test_unknown_record_stops_without_guessing_a_provider(tmp_path: Path):
    calls = tmp_path / "curl.log"
    curl = _write_fake_curl(tmp_path / "bin", {"/lookup/": {"id": 7}, "/pipelines?": []}, calls)
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "pull_request",
                  recorded=True, env={"FLOW_CI_CURL": str(curl)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["unknown"]
    assert "pipeline --providers" in result.stderr
    assert not calls.exists()
    assert result.stderr.count("FLOW_CI_EXIT=") == 1
    assert result.stderr.rstrip().endswith("FLOW_CI_EXIT=2")


@pytest.mark.parametrize("states,expected", [
    (["success", "success"], "success"), (["success", "failure"], "failure"),
    (["running", "failure"], "failure"), (["unknown", "running"], "running"),
    (["success", "not-found"], "unknown"), ([], "unknown"),
])
def test_combined_provider_population_requires_every_green(states, expected):
    from lib.cicd.flow import aggregate
    assert aggregate(states) == expected


@requires_bash
def test_both_recorded_lanes_are_examined_even_when_first_is_green(tmp_path: Path):
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [woodpecker, github-actions]\n")
    curl = _write_fake_curl(tmp_path / "bin", {
        "/lookup/": {"id": 7}, "/pipelines?": [{"number": 12, "commit": SHA,
                                                  "event": "pull_request", "status": "success"}],
    }, tmp_path / "curl.log")
    gh = _gha_gh(tmp_path, [_gha_run(19, "failure")])
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "pull_request",
                  "--exit-code", recorded=True, env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    assert result.returncode == 1
    assert result.stderr.count("FLOW_CI_EXIT=") == 1
    assert result.stderr.rstrip().endswith("FLOW_CI_EXIT=1")
    marks = _markers(result.stdout)
    assert marks["FLOW_CI_STATUS"] == ["failure"]
    assert marks["FLOW_CI_PROVIDERS"] == ["woodpecker,github-actions"]
    import json
    lanes = json.loads(marks["FLOW_CI_LANES"][0])
    assert lanes["woodpecker"]["status"] == "success"
    assert lanes["github-actions"]["status"] == "failure"


@requires_bash
@pytest.mark.parametrize("source", ["classic-checks", "ruleset-only"])
def test_applicable_required_sources_select_pr_event(tmp_path: Path, source):
    from tests.test_flow_ci_status import _both_lanes_curl
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [woodpecker]\n")
    gh = tmp_path / "gh"
    endpoint = "*required_status_checks" if source == "classic-checks" else "*/rules/branches/*"
    payload = ('{"checks":[{"context":"ci/woodpecker/pr/woodpecker"}]}' if source == "classic-checks" else
               '[{"type":"required_status_checks","parameters":{"required_status_checks":'
               '[{"context":"ci/woodpecker/pr/woodpecker"}]}}]')
    gh.write_text(f'''#!/bin/sh
if [ "$1" = api ]; then
  case "$2" in
    repos/o/r) echo main; exit 0 ;;
    {endpoint}) printf '%s' '{payload}' | jq -r "$4"; exit $? ;;
  esac
fi
exit 1
''')
    gh.chmod(0o755)
    curl = _both_lanes_curl(tmp_path)
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", recorded=True,
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    marks = _markers(result.stdout)
    assert marks["FLOW_CI_STATUS"] == ["failure"], result.stdout + result.stderr
    assert marks["FLOW_CI_EVENT"][0].startswith("pull_request (")
    if source == "ruleset-only":
        assert "rulesets" in marks["FLOW_CI_EVENT"][0]


@pytest.mark.parametrize("status,reason,expected,code", [
    ("ready", "authenticated", "ok", 0),
    ("missing", "credentials-missing", "missing", 1),
    ("unknown", "container-view", "warn", 0),
    ("unknown", "record-unavailable", "warn", 0),
    ("unknown", "record-invalid", "warn", 0),
])
def test_host_preflight_stops_missing_but_unknown_warns(tmp_path: Path, monkeypatch, capsys,
                                                      status, reason, expected, code):
    from lib.cicd import host
    from lib.cicd.flow import host_preflight_main
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [github-actions]\n")
    monkeypatch.setattr(host, "read_host_record", lambda path: {
        "schema": 1, "checked_at": "2026-01-01T00:00:00+00:00", "providers": {
            "github-actions": {"status": status, "reason": reason, "versions": {}},
            "woodpecker": {"status": "missing", "reason": "tool-absent", "versions": {}},
        }})

    def forbidden(*args, **kwargs):
        raise AssertionError("preflight must never probe or write host credentials")
    monkeypatch.setattr(host, "probe_host", forbidden)
    monkeypatch.setattr(host, "write_host_record", forbidden)
    assert host_preflight_main(str(tmp_path)) == code
    out = capsys.readouterr()
    assert "FLOW_CI_HOST: " + expected in out.out
    assert f"last recorded {status} at 2026-01-01T00:00:00+00:00 ({reason})" in out.out
    assert "woodpecker" not in out.out, "unselected missing capability cannot stop a flow"
    if expected != "ok":
        assert "/cpp:init Tier 4" in out.err


def test_lane_plan_is_offline_and_fallback_is_only_a_future_action(  # binary-guard: allow intercepted sentinel
    tmp_path: Path, monkeypatch
):
    import subprocess

    from lib.cicd.flow import lane_plan

    def no_commands(*args, **kwargs):
        raise RuntimeError("offline plan guard")
    monkeypatch.setattr(subprocess, "run", no_commands)
    with pytest.raises(RuntimeError, match="offline plan guard"):
        subprocess.run(["fixture-no-remote-probes"])
    missing = lane_plan(tmp_path)
    assert missing["status"] == "unknown" and missing["source"] == "unknown"
    assert missing["fallback"] == {"requested": False, "would_trigger": False}
    fallback = lane_plan(tmp_path, allow_fallback=True)
    assert fallback["status"] == "unknown" and fallback["source"] == "fallback"
    assert fallback["fallback"] == {"requested": True, "would_trigger": True}
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [woodpecker, github-actions]\n")
    known = lane_plan(tmp_path, allow_fallback=True)
    assert known == {"status": "ok", "source": "recorded", "reason": None,
                     "providers": ["woodpecker", "github-actions"],
                     "lanes": [{"provider": "woodpecker", "lane": "woodpecker"},
                               {"provider": "github-actions", "lane": "github-actions"}],
                     "fallback": {"requested": True, "would_trigger": False}}


@requires_bash
@pytest.mark.parametrize("status,code", [("missing", 1), ("warn", 0), ("blind", 0)])
def test_live_merge_honors_host_preflight_and_requires_its_signal(tmp_path: Path, status, code):
    from tests.test_gh_pr_merge import _calls, _linked_worktree, _make_stubs
    from tests.test_gh_pr_merge import _run as merge_run
    cwd = _linked_worktree(tmp_path)
    record = cwd / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED")
    preflight = tmp_path / "host-preflight"
    signal = "" if status == "blind" else f"echo FLOW_CI_HOST_LANES: github-actions\necho FLOW_CI_HOST: {status}\n"
    preflight.write_text(f"#!/bin/sh\n{signal}exit {code}\n")
    preflight.chmod(0o755)
    result = merge_run(cwd, stubs, "42", "issue-1610-ci-lanes", extra_env={
        "GH_PR_MERGE_HOST_PREFLIGHT": str(preflight), "WOODPECKER_API_TOKEN": "fixture-token",
    })
    calls = _calls(stubs)
    if status in {"missing", "blind"}:
        assert result.returncode == 13, result.stdout + result.stderr
        assert not any(call.startswith("gh pr merge") for call in calls)
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert any(call.startswith("gh pr merge") for call in calls)
    assert not any(call.startswith("curl") for call in calls), "Actions selection must not probe Woodpecker queue"


def test_canonical_json_subset_record_remains_offline_without_pyyaml(tmp_path: Path, monkeypatch):
    import builtins

    from lib.cicd.flow import lane_plan
    original = builtins.__import__

    def no_yaml(name, *args, **kwargs):
        if name == "yaml" or name.startswith("yaml."):
            raise ModuleNotFoundError("fixture: PyYAML unavailable")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_yaml)
    with pytest.raises(ModuleNotFoundError, match="PyYAML unavailable"):
        __import__("yaml")
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text('{"pipeline":{"providers":["github-actions"]}}\n')
    assert lane_plan(tmp_path)["status"] == "ok"
    record.write_text('{"pipeline":{"providers":["github-actions"],"providers":["woodpecker"]}}\n')
    bad = lane_plan(tmp_path)
    assert bad["status"] == "unknown" and "duplicate" in bad["reason"]


def test_registry_extension_needs_no_consumer_enum_change(tmp_path: Path, monkeypatch, capsys):
    import subprocess

    from lib.cicd import flow
    from lib.cicd.providers import PROVIDERS, ProviderSpec
    monkeypatch.setattr(flow, "fixture_context", lambda context: context.startswith("ci/future/"), raising=False)
    monkeypatch.setattr(flow, "fixture_status", lambda script, argv, lane: subprocess.CompletedProcess(
        "fixture", 0, stdout="FLOW_CI_PROVIDER: future\nFLOW_CI_STATUS: success\n", stderr=""), raising=False)
    monkeypatch.setattr(flow, "fixture_watch", lambda *args: None, raising=False)
    monkeypatch.setitem(PROVIDERS, "future", ProviderSpec(
        "future", "fixture_generator", ".fixture.yml", "fixture_checks", "future-lane", "fixture-host",
        flow_context="lib.cicd.flow:fixture_context", flow_status="lib.cicd.flow:fixture_status",
        flow_watch="lib.cicd.flow:fixture_watch"))
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [future]\n")
    assert flow.status_main("must-not-run.sh", ["--path", str(tmp_path)]) == 0
    assert "FLOW_CI_PROVIDER: future" in capsys.readouterr().out
    config.write_text("pipeline:\n  providers: [github-actions, future]\n")
    assert flow.context_lanes(tmp_path, ["ci", "ci/future/build"]) == [
        ("ci", "github-actions", "github-actions"), ("ci/future/build", "future", "future-lane")]
