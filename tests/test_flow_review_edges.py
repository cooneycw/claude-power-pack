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
