"""Recorded provider routing must precede any provider probes (#1610 A)."""

import shutil
import signal
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
    (["success", "not-found"], "not-found"), ([], "unknown"),
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
    *required_status_checks) echo 'gh: Branch not protected (HTTP 404)' >&2; exit 1 ;;
    */rules/branches/*) echo '[]' | jq -r "$4"; exit $? ;;
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
    monkeypatch.setattr(subprocess, "Popen", no_commands)
    with pytest.raises(RuntimeError, match="offline plan guard"):
        subprocess.run(["fixture-no-remote-probes"])
    with pytest.raises(RuntimeError, match="offline plan guard"):
        subprocess.Popen(["fixture-no-remote-probes"])
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
        "fixture", 0, stdout="FLOW_CI_PROVIDER: future\nFLOW_CI_REF: " + SHA + "\nFLOW_CI_STATUS: success\n",
        stderr=""), raising=False)
    monkeypatch.setattr(flow, "fixture_watch", lambda *args: None, raising=False)
    monkeypatch.setitem(PROVIDERS, "future", ProviderSpec(
        "future", "fixture_generator", ".fixture.yml", "fixture_checks", "future-lane", "fixture-host",
        flow_context="lib.cicd.flow:fixture_context", flow_status="lib.cicd.flow:fixture_status",
        flow_watch="lib.cicd.flow:fixture_watch"))
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [future]\n")
    assert flow.status_main("must-not-run.sh", [SHA, "--path", str(tmp_path)]) == 0
    assert "FLOW_CI_PROVIDER: future" in capsys.readouterr().out
    config.write_text("pipeline:\n  providers: [github-actions, future]\n")
    assert flow.context_lanes(tmp_path, ["ci", "ci/future/build"]) == [
        ("ci", "github-actions", "github-actions"), ("ci/future/build", "future", "future-lane")]


@requires_bash
@pytest.mark.skipif(shutil.which("sleep") is None, reason="requires sleep for the signal fixture")
@pytest.mark.parametrize("signum,code", [(signal.SIGTERM, 143), (signal.SIGHUP, 129)], ids=["TERM", "HUP"])
def test_recorded_dispatch_signal_reports_real_exit_and_stops_children(tmp_path: Path, signum, code):
    import os
    import signal
    import subprocess
    import time

    from tests.test_flow_ci_status import SCRIPT
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    ready = tmp_path / "ready"
    gh = tmp_path / "gh"
    gh.write_text(f'#!/bin/sh\necho $$ > "{ready}"\nexec sleep 60\n')
    gh.chmod(0o755)
    child_pid = None
    process = subprocess.Popen(["bash", str(SCRIPT), SHA, "--path", str(tmp_path), "--repo", "o/r",
                                "--event", "pull_request"],
                               env={**os.environ, "FLOW_CI_GH": str(gh)},
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "fixture must reach the blocking backend"
        child_pid = int(ready.read_text())
        process.send_signal(signum)
        _, stderr = process.communicate(timeout=5)
        assert process.returncode == code, stderr
        assert stderr.count("FLOW_CI_EXIT=") == 1
        assert stderr.rstrip().endswith(f"FLOW_CI_EXIT={code}")
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        for pid in (child_pid,):
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


@requires_bash
def test_partial_protection_read_cannot_choose_a_green_event(tmp_path: Path):
    from tests.test_flow_ci_status import _both_lanes_curl
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [woodpecker]\n")
    gh = tmp_path / "gh"
    gh.write_text('''#!/bin/sh
case "$2" in
  repos/o/r) echo main; exit 0 ;;
  *required_status_checks) echo 'gh: Forbidden (HTTP 403)' >&2; exit 1 ;;
  */rules/branches/*) echo 'ci/woodpecker/push/woodpecker'; exit 0 ;;
esac
exit 1
''')
    gh.chmod(0o755)
    curl = _both_lanes_curl(tmp_path)
    result = _run(tmp_path, SHA, "--path", str(tmp_path), "--repo", "o/r", recorded=True,
                  env={"FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["unknown"]
    assert "unreadable" in result.stdout + result.stderr


@requires_bash
def test_default_head_is_pinned_once_before_multiple_provider_queries(tmp_path: Path):
    import json
    import os

    from tests.test_flow_ci_status import OTHER_SHA
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [woodpecker, github-actions]\n")
    binary = tmp_path / "bin"
    binary.mkdir()
    git = binary / "git"
    count = tmp_path / "head-reads"
    git.write_text(f'''#!/usr/bin/env bash
ref="${{@: -1}}"
ref="${{ref%'^{{commit}}'}}"
case "$ref" in
  HEAD)
    n=0; [ ! -f "{count}" ] || n=$(cat "{count}")
    echo $((n+1)) > "{count}"
    if [ "$n" = 0 ]; then echo {SHA}; else echo {OTHER_SHA}; fi ;;
  *) echo "$ref" ;;
esac
''')
    git.chmod(0o755)
    curl = _write_fake_curl(binary, {
        "/lookup/": {"id": 7}, "/pipelines?": [{"number": 12, "commit": SHA,
                                                   "event": "pull_request", "status": "success"}],
    }, tmp_path / "curl.log")
    gh = binary / "gh"
    bad, good = json.dumps([_gha_run(19, "failure")]), json.dumps([_gha_run(20, "success")])
    gh.write_text(f'''#!/usr/bin/env bash
if [[ "$1 $2" == "run list" ]]; then
  for arg in "$@"; do
    if [ "$arg" = "{SHA}" ]; then echo '{bad}'; exit 0; fi
  done
  echo '{good}'; exit 0
fi
exit 1
''')
    gh.chmod(0o755)
    result = _run(tmp_path, "--path", str(tmp_path), "--repo", "o/r", "--event", "pull_request", recorded=True,
                  env={"PATH": str(binary) + os.pathsep + os.environ["PATH"],
                       "FLOW_CI_CURL": str(curl), "FLOW_CI_GH": str(gh)})
    assert _markers(result.stdout)["FLOW_CI_STATUS"] == ["failure"], result.stdout + result.stderr
    assert count.read_text().strip() == "1", "HEAD must be captured before dispatch, not once per provider"


def test_wait_retries_a_provider_that_has_not_registered_its_pipeline(tmp_path: Path, monkeypatch, capsys):
    import subprocess

    from lib.cicd import flow
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    states = iter(["not-found", "failure"])
    calls = []

    def backend(script, argv, lane):
        state = next(states)
        calls.append(state)
        return subprocess.CompletedProcess(argv, 0, stdout=(
            "FLOW_CI_PROVIDER: github-actions\nFLOW_CI_REF: " + SHA + "\nFLOW_CI_STATUS: " + state + "\n"), stderr="")
    monkeypatch.setattr(flow, "shell_status", backend)
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    assert flow.status_main("owned-backend", [SHA, "--path", str(tmp_path), "--wait", "30", "--exit-code"]) == 1
    assert calls == ["not-found", "failure"]
    assert "FLOW_CI_STATUS: failure" in capsys.readouterr().out


@requires_bash
def test_wait_retries_actual_empty_actions_listing(tmp_path: Path, monkeypatch, capsys):
    import json
    import os

    from lib.cicd import flow
    from tests.test_flow_ci_status import SCRIPT
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    counter = tmp_path / "gh-count"
    gh = tmp_path / "gh"
    runs = json.dumps([_gha_run(19, "failure")])
    gh.write_text(f'''#!/bin/sh
if [ "$1 $2" = "run list" ]; then
    n=0; [ ! -f "{counter}" ] || n=$(cat "{counter}")
    echo $((n+1)) > "{counter}"
    if [ "$n" = 0 ]; then echo '[]'; else echo '{runs}'; fi
    exit 0
fi
exit 1
''')
    gh.chmod(0o755)
    monkeypatch.setenv("FLOW_CI_GH", str(gh))
    monkeypatch.setenv("FLOW_CI_AWS", "/nonexistent/aws")
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    assert os.access(gh, os.X_OK)
    code = flow.status_main(str(SCRIPT), [SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "pull_request",
                                        "--wait", "30", "--exit-code"])
    assert code == 1
    assert counter.read_text().strip() == "2"
    assert "FLOW_CI_STATUS: failure" in capsys.readouterr().out


def _recorded_backend(tmp_path: Path, monkeypatch, replies: list[str]):
    """Recorded github-actions lane answered from canned stdout bodies."""
    import subprocess

    from lib.cicd import flow
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    calls: list[str] = []
    queue = list(replies)

    def backend(script, argv, lane):
        body = queue.pop(0) if len(queue) > 1 else queue[0]
        calls.append(body)
        return subprocess.CompletedProcess(argv, 0, stdout=(
            "FLOW_CI_PROVIDER: github-actions\nFLOW_CI_REF: " + SHA + "\n" + body), stderr="")
    monkeypatch.setattr(flow, "shell_status", backend)
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    return flow, calls


UNREADABLE = "FLOW_CI_PIPELINE: 4726\nFLOW_CI_RETRYABLE: pipeline #4726 found; status '' unreadable\nFLOW_CI_STATUS: unknown\n"


def test_wait_polls_a_found_but_unreadable_pipeline(tmp_path: Path, monkeypatch, capsys):
    """Issue #1684 on the recorded path: `unknown` ended the wait on the first look."""
    flow, calls = _recorded_backend(tmp_path, monkeypatch, [UNREADABLE, "FLOW_CI_STATUS: success\n"])
    assert flow.status_main("owned-backend", [SHA, "--path", str(tmp_path), "--wait", "30"]) == 0
    assert len(calls) == 2
    out = capsys.readouterr().out
    assert "FLOW_CI_STATUS: success" in out and "FLOW_CI_WAIT: settled" in out


def test_wait_does_not_poll_an_unknown_that_is_a_final_judgement(tmp_path: Path, monkeypatch, capsys):
    """No RETRYABLE line: polling cannot resolve it, so the wait still ends at once."""
    flow, calls = _recorded_backend(tmp_path, monkeypatch, ["FLOW_CI_STATUS: unknown\n"])
    assert flow.status_main("owned-backend", [SHA, "--path", str(tmp_path), "--wait", "30"]) == 2
    assert len(calls) == 1
    assert "FLOW_CI_WAIT: settled" in capsys.readouterr().out


@pytest.mark.parametrize("body,status", [(UNREADABLE, "unknown"), ("FLOW_CI_STATUS: running\n", "running"),
                                         ("FLOW_CI_STATUS: not-found\n", "not-found")])
def test_an_expired_wait_is_never_exit_0(tmp_path: Path, monkeypatch, capsys, body, status):
    flow, calls = _recorded_backend(tmp_path, monkeypatch, [body])
    clock = iter(range(0, 10_000, 10))
    monkeypatch.setattr(flow.time, "monotonic", lambda: next(clock))
    assert flow.status_main("owned-backend", [SHA, "--path", str(tmp_path), "--wait", "30"]) == 5
    assert len(calls) > 1
    captured = capsys.readouterr()
    assert "FLOW_CI_WAIT: expired (30s)" in captured.out
    assert f"FLOW_CI_STATUS: {status}" in captured.out
    assert "expired" in captured.err


def test_wait_polls_through_a_lane_that_answered_and_then_cannot(tmp_path: Path, monkeypatch, capsys):
    """Counter-model review, #1684: each recorded poll is a fresh backend, so a
    listing that fails after the pipeline was seen is a BARE unknown - no
    RETRYABLE line - and ended the wait with exit 2."""
    flow, calls = _recorded_backend(tmp_path, monkeypatch, [
        "FLOW_CI_STATUS: running\n", "FLOW_CI_STATUS: unknown\n", "FLOW_CI_STATUS: success\n"])
    assert flow.status_main("owned-backend", [SHA, "--path", str(tmp_path), "--wait", "30"]) == 0
    assert len(calls) == 3
    assert "FLOW_CI_STATUS: success" in capsys.readouterr().out


@requires_bash
def test_recorded_woodpecker_cli_wait_survives_a_failed_relisting(tmp_path: Path, monkeypatch, capsys):
    """The same, through the REAL shell backend: running, a failed call, success."""
    from lib.cicd import flow
    from tests.test_flow_ci_status import SCRIPT, _write_sequenced_wpcli
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [woodpecker]\n")
    counter = tmp_path / "count"
    wpcli = _write_sequenced_wpcli(
        tmp_path / "bin", [f"4726|running|{SHA}|push", None, f"4726|success|{SHA}|push"], counter)
    missing_curl = Path("/nonexistent/curl")
    assert not missing_curl.exists()
    for key, value in {"FLOW_CI_WPCLI": str(wpcli), "FLOW_CI_CURL": str(missing_curl),
                       "FLOW_CI_AWS": "/nonexistent/aws", "FLOW_CI_GH": "/nonexistent/gh"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(flow.time, "sleep", lambda seconds: None)
    code = flow.status_main(str(SCRIPT), [SHA, "--path", str(tmp_path), "--repo", "o/r", "--event", "push",
                                          "--wait", "30"])
    out = capsys.readouterr().out
    assert counter.read_text().strip() == "3", out
    assert code == 0, out
    assert "FLOW_CI_STATUS: success" in out and "FLOW_CI_WAIT: settled" in out
