"""Required Actions checks are watched without Woodpecker fallback (#1610 A)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/flow-pr-watch.sh"
HEAD = "aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00"
requires_tools = pytest.mark.skipif(any(shutil.which(tool) is None for tool in ("bash", "awk", "sed", "grep")),
                                    reason="requires watch shell tools")


def gh_fixture(tmp_path: Path, *, classic=None, rules=None, log_exit=0) -> Path:
    classic = {"checks": [{"context": "ci"}]} if classic is None else classic
    rules = [] if rules is None else rules
    gh = tmp_path / "gh"
    gh.write_text("""#!/usr/bin/env bash
if [[ "$1" == "api" ]]; then
  case "$2" in
    *required_status_checks) echo CLASSIC; exit 0 ;;
    */rules/branches/*) echo RULES; exit 0 ;;
  esac
fi
if [[ "$1 $2" == "pr view" ]]; then
  for arg in "$@"; do
    case "$arg" in
      headRefOid,baseRefName) echo '{"headRefOid":"HEAD","baseRefName":"main"}'; exit 0 ;;
      headRefOid) echo HEAD; exit 0 ;;
      statusCheckRollup) echo 'ci|https://github.com/o/r/actions/runs/19|FAILURE'; exit 0 ;;
    esac
  done
fi
if [[ "$1 $2" == "run view" ]]; then
  for arg in "$@"; do
    case "$arg" in
      jobs) echo 'tests|failure|2026-11-08T00:00:00Z|81|'; exit 0 ;;
      --log-failed)
        cat <<'LOG'
================ short test summary info ================
FAILED tests/test_feature.py::test_regression - AssertionError
================ 1 failed in 0.1s ================
LOG
        exit 0 ;;
    esac
  done
fi
exit 1
""".replace("CLASSIC", "'" + json.dumps(classic) + "'")
        .replace("RULES", "'" + json.dumps(rules) + "'").replace("HEAD", HEAD)
        .replace("LOG\n        exit 0", f"LOG\n        exit {log_exit}"))
    gh.chmod(0o755)
    return gh


@requires_tools
@pytest.mark.parametrize("fallback", [False, True])
def test_actions_red_check_is_reported_instead_of_timing_out(tmp_path: Path, fallback):
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [github-actions]\n")
    gh = gh_fixture(tmp_path)
    wp = tmp_path / "woodpecker-cli"
    wp.write_text('#!/bin/sh\necho called > "' + str(tmp_path / "wp-called") + '"\nexit 19\n')
    wp.chmod(0o755)
    result = subprocess.run(["bash", str(SCRIPT), "12", "--path", str(tmp_path), "--repo", "o/r", "--timeout", "0",
                             *(["--fallback-provider-probes"] if fallback else [])],
                            env={**os.environ, "FLOW_PR_WATCH_GH": str(gh), "FLOW_PR_WATCH_WPCLI": str(wp)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FLOW_PR_WATCH: red" in result.stdout
    assert "FLOW_PR_WATCH_URL=https://github.com/o/r/actions/runs/19" in result.stdout
    assert "FLOW_PR_WATCH_FAILED=tests/test_feature.py::test_regression" in result.stdout
    assert not (tmp_path / "wp-called").exists()


@requires_tools
def test_required_contexts_union_classic_checks_and_rulesets(tmp_path: Path):
    from lib.cicd.flow import required_contexts
    gh = gh_fixture(tmp_path, classic={"contexts": ["lint"], "checks": [{"context": "ci"}]},
                    rules=[{"type": "required_status_checks", "parameters": {
                        "required_status_checks": [{"context": "security"}, {"context": "ci"}]}}])
    assert required_contexts("o/r", "main", str(gh)) == ["ci", "lint", "security"]


@requires_tools
def test_failed_log_fetch_cannot_turn_a_known_red_into_a_baselined_flake(tmp_path: Path):
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [github-actions]\n")
    gh = gh_fixture(tmp_path, log_exit=19)
    baseline = tmp_path / "baseline"
    baseline.write_text("tests/test_feature.py::test_regression\n")
    result = subprocess.run(["bash", str(SCRIPT), "12", "--path", str(tmp_path), "--repo", "o/r",
                             "--timeout", "0", "--baseline", str(baseline)],
                            env={**os.environ, "FLOW_PR_WATCH_GH": str(gh)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FLOW_PR_WATCH: red" in result.stdout


@pytest.mark.parametrize("http", [403, 404])
def test_unreadable_classic_protection_cannot_be_hidden_by_readable_rulesets(tmp_path: Path, monkeypatch, http):
    from lib.cicd import flow
    from lib.cicd.flow import required_contexts
    from lib.cicd.providers import ProviderError

    def api(argv, **kwargs):
        if argv[-1].endswith("required_status_checks"):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr=f"gh: request failed (HTTP {http})")
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps([
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "ci"}]}}
        ]), stderr="")
    monkeypatch.setattr(flow, "command", api)
    if http == 404:
        assert required_contexts("o/r", "main", "fixture-gh") == ["ci"]
    else:
        with pytest.raises(ProviderError, match="unreadable"):
            required_contexts("o/r", "main", "fixture-gh")
