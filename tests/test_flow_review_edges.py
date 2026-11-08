"""Regression evidence for the second recorded-provider review (#1610 A)."""
from __future__ import annotations

import os
import subprocess

import pytest

from tests.test_flow_watch_recorded import SCRIPT, gh_fixture, requires_tools


@requires_tools
@pytest.mark.parametrize("conclusion", ["SKIPPED", "NEUTRAL"])
def test_satisfied_actions_check_settles_green(tmp_path, conclusion):
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    gh = gh_fixture(tmp_path)
    gh.write_text(gh.read_text().replace("runs/19|FAILURE", "runs/19|" + conclusion))
    result = subprocess.run(["bash", str(SCRIPT), "12", "--path", str(tmp_path), "--repo", "o/r", "--timeout", "0"],
                            env={**os.environ, "FLOW_PR_WATCH_GH": str(gh)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FLOW_PR_WATCH: green" in result.stdout


@requires_tools
@pytest.mark.parametrize("state,code,verdict", [("SUCCESS", 0, "green"), ("FAILURE", 1, "red")])
def test_context_scope_validates_complete_population_before_selecting(tmp_path, state, code, verdict):
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions, woodpecker]\n")
    gh = gh_fixture(tmp_path, classic={"contexts": ["ci", "ci/woodpecker/pr/woodpecker"]})
    gh.write_text(gh.read_text().replace("runs/19|FAILURE", "runs/19|" + state))
    wp = tmp_path / "woodpecker-cli"
    called = tmp_path / "wp-called"
    wp.write_text(f'#!/bin/sh\ntouch "{called}"\nexit 19\n')
    wp.chmod(0o755)
    result = subprocess.run(["bash", str(SCRIPT), "12", "--path", str(tmp_path), "--repo", "o/r",
                             "--context", "ci", "--timeout", "0"],
                            env={**os.environ, "FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wp)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == code, result.stdout + result.stderr
    assert "FLOW_PR_WATCH: " + verdict in result.stdout
    assert not called.exists()


@pytest.mark.parametrize("hung", [False, True])
def test_status_fallback_budgets_requested_wait_and_reports_timeout(tmp_path, monkeypatch, capsys, hung):
    from lib.cicd import flow

    # This directory has no canonical provider record; fallback must be explicit.
    assert not (tmp_path / ".claude/cicd.yml").exists()

    def simulated_wait(argv, *, timeout=120, **kwargs):
        assert kwargs["env"]["CPP_FLOW_CI_BACKEND"] == "probe"
        assert argv[argv.index("--wait") + 1] == "600"
        if hung or timeout < 600:
            raise subprocess.TimeoutExpired(argv, timeout)
        return subprocess.CompletedProcess(argv, 0, "FLOW_CI_STATUS: success\n", "FLOW_CI_EXIT=0\n")

    monkeypatch.setattr(flow, "command", simulated_wait)
    code = flow.status_entry("fixture-status.sh", ["a" * 40, "--path", str(tmp_path),
                             "--fallback-provider-probes", "--wait", "600", "--exit-code"])
    output = capsys.readouterr()
    assert code == (2 if hung else 0)
    assert "FLOW_CI_STATUS: " + ("unknown" if hung else "success") in output.out
    assert output.err.count("FLOW_CI_EXIT=") == 1
    if hung:
        assert "fallback" in output.err.lower()


@pytest.mark.parametrize("failure_at", ["next-context", "final-head"])
@pytest.mark.parametrize("timeout", [False, True])
@pytest.mark.parametrize("first_verdict,code", [("red", 1), ("green", 2)])
def test_remote_read_error_preserves_only_established_red(tmp_path, monkeypatch, capsys,
                                                        failure_at, timeout, first_verdict, code):
    from lib.cicd import flow
    from tests.test_flow_watch_recorded import HEAD

    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    head_reads = 0
    context_reads = 0

    def fail(argv):
        if timeout:
            raise subprocess.TimeoutExpired(argv, 30)
        raise subprocess.CalledProcessError(1, argv, stderr="owned API outage")

    def head_read(argv, **kwargs):
        nonlocal head_reads
        head_reads += 1
        if failure_at == "final-head" and head_reads == 3:
            fail(argv)
        return subprocess.CompletedProcess(argv, 0, '{"headRefOid":"' + HEAD + '","baseRefName":"main"}', "")

    def context_read(script, argv, lane):
        nonlocal context_reads
        context_reads += 1
        if failure_at == "next-context" and context_reads == 2:
            fail(argv)
        verdict = first_verdict if context_reads == 1 else "green"
        output = ("FLOW_PR_WATCH_HEAD=" + HEAD + "\nFLOW_PR_WATCH: " + verdict + "\n"
                  "FLOW_PR_WATCH_FAILED=" + ("tests/test_owned.py::test_failure" if verdict == "red" else "-") + "\n")
        return subprocess.CompletedProcess(argv, 1 if verdict == "red" else 0, output, "")

    monkeypatch.setattr(flow, "command", head_read)
    monkeypatch.setattr(flow, "required_contexts", lambda *args: ["ci", "lint"])
    monkeypatch.setattr(flow, "callback", lambda hook: context_read)
    result = flow.watch_entry("fixture-watch.sh", ["12", "--path", str(tmp_path), "--repo", "o/r", "--timeout", "0"])
    output = capsys.readouterr()
    assert result == code, output.out + output.err
    assert "FLOW_PR_WATCH: " + ("red" if first_verdict == "red" else "unknown") in output.out
    assert output.err.count("FLOW_PR_WATCH_EXIT=") == 1
    if first_verdict == "red":
        assert "FLOW_PR_WATCH_FAILED=tests/test_owned.py::test_failure" in output.out
