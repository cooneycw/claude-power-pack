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
      statusCheckRollup|headRefOid,statusCheckRollup)
        echo 'ci|https://github.com/o/r/actions/runs/19|FAILURE'; exit 0 ;;
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


def moving_head_gh(tmp_path: Path, after: int) -> Path:
    import sys
    gh = gh_fixture(tmp_path)
    base = tmp_path / "gh-base"
    gh.rename(base)
    counter = tmp_path / "head-count"
    gh.write_text(f"#!{sys.executable}\n" + f'''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ['pr','view'] and 'headRefOid,baseRefName' in args:
    file = Path({str(counter)!r})
    count = int(file.read_text()) if file.exists() else 0
    file.write_text(str(count+1))
    print(json.dumps({{'headRefOid': {HEAD!r} if count < {after} else 'b'*40, 'baseRefName':'main'}}))
else:
    os.execv({str(base)!r}, [{str(base)!r}, *args])
''')
    gh.chmod(0o755)
    return gh


@requires_tools
@pytest.mark.parametrize("after,code,verdict", [(1, 2, "unknown"), (2, 1, "red")])
def test_head_movement_requires_evidence_and_never_erases_an_observed_red(tmp_path: Path, after, code, verdict):
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    gh = moving_head_gh(tmp_path, after)
    result = subprocess.run(["bash", str(SCRIPT), "12", "--path", str(tmp_path), "--repo", "o/r", "--timeout", "0"],
                            env={**os.environ, "FLOW_PR_WATCH_GH": str(gh)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == code, result.stdout + result.stderr
    assert "FLOW_PR_WATCH: " + verdict in result.stdout


@requires_tools
@pytest.mark.parametrize("conclusion", ["timed_out", "startup_failure", "action_required", "future_red"])
def test_non_test_actions_failure_is_never_excused_by_a_baselined_test(tmp_path: Path, conclusion):
    record = tmp_path / ".claude/cicd.yml"
    record.parent.mkdir()
    record.write_text("pipeline:\n  providers: [github-actions]\n")
    gh = gh_fixture(tmp_path)
    source = gh.read_text().replace("echo 'tests|failure|2026-11-08T00:00:00Z|81|'", (
        "printf '%s\\n' 'tests|failure|2026-11-08T00:00:00Z|81|' "
        f"'build|{conclusion}|2026-11-08T00:00:00Z|82|'"))
    source = source.replace('#!/usr/bin/env bash\n', '''#!/usr/bin/env bash
if [[ "$1 $2" == "run view" && "$*" == *"--job 82"* && "$*" == *"--log-failed"* ]]; then
  echo 'job ended without a pytest conclusion'; exit 0
fi
''', 1)
    gh.write_text(source)
    baseline = tmp_path / "baseline"
    baseline.write_text("tests/test_feature.py::test_regression\n")
    result = subprocess.run(["bash", str(SCRIPT), "12", "--path", str(tmp_path), "--repo", "o/r",
                             "--timeout", "0", "--baseline", str(baseline)],
                            env={**os.environ, "FLOW_PR_WATCH_GH": str(gh)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FLOW_PR_WATCH: red" in result.stdout


@pytest.mark.parametrize("kind,code,verdict", [
    ("killed", 0, "cancelled"), ("red", 1, "red"), ("unknown", 2, "unknown"),
])
def test_supersession_requires_kill_signature_and_preserves_real_failures(capsys, kind, code, verdict):
    from lib.cicd.flow import moved_watch
    output = ("FLOW_PR_WATCH_PIPELINE=19\nFLOW_PR_WATCH_KILL_SIGNATURE=1\n"
              "FLOW_PR_WATCH_SUMMARY_FAILED=-\nFLOW_PR_WATCH_FAILED=-\n")
    if kind == "red":
        output = output.replace("FLOW_PR_WATCH_FAILED=-", "FLOW_PR_WATCH_FAILED=tests/test_app.py::test_real")
    elif kind == "unknown":
        output = output.replace("FLOW_PR_WATCH_KILL_SIGNATURE=1", "FLOW_PR_WATCH_KILL_SIGNATURE=0")
    state = "red" if kind != "unknown" else "unknown"
    assert moved_watch([("ci", state, output)], {"headRefOid": HEAD}, {"headRefOid": "b" * 40}) == code
    assert "FLOW_PR_WATCH: " + verdict in capsys.readouterr().out
