"""Exercise the project receipt and the summary/status its consumers read."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/cpp-install-receipt.py"
CASES = json.loads((ROOT / "tests/fixtures/cpp-install-receipt/cases.json").read_text())
REVISION = "a" * 40


def run(project, command, *args, data=None):
    return subprocess.run(
        [sys.executable, str(HELPER), command, "--project-dir", str(project),
         "--revision", REVISION, *args],
        input=json.dumps(data) if data is not None else None,
        capture_output=True, text=True, timeout=10,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_committed_outcomes_survive_receipt_and_summary(tmp_path, case):
    result = run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=case["steps"])
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads((tmp_path / ".claude/cpp-install.json").read_text())
    assert receipt["schema"] == 1 and receipt["cpp_revision"] == REVISION
    assert receipt["selected"] == {"tier": 1, "profile": "not-selected"}
    assert receipt["steps"][0]["outcome"] == case["outcome"]
    assert all(step["recorded_at"].endswith("Z") for step in receipt["steps"])
    summary = run(tmp_path, "summary")
    assert case["summary"] in summary.stdout
    assert (summary.returncode == 0) is case["complete"]
    if case["outcome"] == "FAILED":
        assert "commands: FAILED" in summary.stdout
        assert "commands: installed" not in summary.stdout
    status = run(tmp_path, "status")
    assert case["status"] in status.stdout


@pytest.mark.parametrize("mode,verdict", [
    ("absent", "no receipt"), ("directory", "unreadable or invalid receipt"),
    ("invalid-json", "unreadable or invalid receipt"), ("invalid-schema", "unreadable or invalid receipt"),
])
def test_missing_and_invalid_are_distinct_from_failed(tmp_path, mode, verdict):
    path = tmp_path / ".claude/cpp-install.json"
    if mode == "directory":
        path.mkdir(parents=True)
        assert path.is_dir(), "the unreadable input must be a directory"
    elif mode != "absent":
        path.parent.mkdir()
        path.write_text("{" if mode == "invalid-json" else '{"schema":999}')
        assert path.exists()
    else:
        assert not path.exists()
    result = run(tmp_path, "status")
    assert result.returncode != 0
    assert verdict in result.stdout
    assert "receipt says failed" not in result.stdout


def test_write_failure_is_not_a_successful_installation(tmp_path):
    (tmp_path / ".claude").write_text("not a directory")
    assert (tmp_path / ".claude").is_file(), "receipt parent must really be blocked"
    result = run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=CASES[0]["steps"])
    assert result.returncode != 0
    assert "receipt write FAILED" in result.stdout
    assert "CPP Installation Complete" not in result.stdout


def test_revision_difference_does_not_hide_failed_steps(tmp_path):
    assert run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=CASES[1]["steps"]).returncode == 0
    path = tmp_path / ".claude/cpp-install.json"
    receipt = json.loads(path.read_text())
    receipt["cpp_revision"] = "b" * 40
    path.write_text(json.dumps(receipt))
    assert receipt["cpp_revision"] != REVISION
    status = run(tmp_path, "status")
    assert "receipt stale (CPP revision differs)" in status.stdout
    assert "receipt says failed" in status.stdout


def test_user_scope_is_metadata_not_configuration_values(tmp_path):
    data = [{"step": "commands", "outcome": "installed", "user_scope": ["claude-commands"]},
            {"step": "stash-guard", "outcome": "already"}]
    assert run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=data).returncode == 0
    path = tmp_path / ".claude/cpp-install.json"
    assert "~/.claude/commands" in path.read_text()
    data[0]["user_scope"] = ["PRIVATE_VALUE_DO_NOT_SAVE"]
    result = run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=data)
    assert result.returncode != 0
    assert "PRIVATE_VALUE_DO_NOT_SAVE" not in result.stdout + result.stderr + path.read_text()


def test_missing_required_outcome_is_unverified_not_complete(tmp_path):
    result = run(tmp_path, "write", "--tier", "5", "--profile", "Standard", data=[])
    assert result.returncode == 0
    summary = run(tmp_path, "summary")
    assert summary.returncode != 0 and "unverified" in summary.stdout
    assert "CPP Installation Complete" not in summary.stdout


def test_wizard_and_status_use_the_same_receipt_helper():
    init = (ROOT / ".claude/commands/cpp/init.md").read_text()
    status = (ROOT / ".claude/commands/cpp/status.md").read_text()
    assert "CPP_INSTALL_RECEIPT_WRITE_BEGIN" in init
    assert "cpp-install-receipt.py\" write" in init
    assert "cpp-install-receipt.py\" summary" in init
    assert "cpp-install-receipt.py\" status" in status


def test_observed_nonzero_exit_overrides_an_accidental_success_label(tmp_path):
    data = [{"step": "commands", "outcome": "installed", "exit_code": 19},
            {"step": "stash-guard", "outcome": "already"}]
    assert run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=data).returncode == 0
    receipt = json.loads((tmp_path / ".claude/cpp-install.json").read_text())
    assert receipt["steps"][0]["outcome"] == "FAILED"
    assert "commands: FAILED" in run(tmp_path, "summary").stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash")
@pytest.mark.skipif(shutil.which("python3") is None, reason="requires python3")
@pytest.mark.parametrize("write_fails", [False, True])
def test_shipped_summary_reads_saved_outcomes_and_never_reuses_old_receipt(tmp_path, write_fails):
    text = (ROOT / ".claude/commands/cpp/init.md").read_text()
    match = re.search(r"# CPP_INSTALL_RECEIPT_WRITE_BEGIN\n(.*?)# CPP_INSTALL_RECEIPT_WRITE_END", text, re.S)
    assert match and match[1].strip(), "must execute the actual shipped integration"
    # An old green receipt must not hide this run's failing write.
    assert run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=CASES[0]["steps"]).returncode == 0
    data = CASES[1]["steps"]
    if write_fails:
        data = [{"step": "commands", "outcome": "invalid-outcome"}]
        assert data[0]["outcome"] not in {"installed", "already", "skipped", "declined", "FAILED", "unverified"}
    result = subprocess.run(
        ["bash", "-c", match[1]], cwd=tmp_path,
        env=dict(os.environ, CPP_DIR=str(ROOT), SELECTED_TIER="1", PROFILE_NAME="not-selected",
                 STEP_RESULTS_JSON=json.dumps(data), PERMISSION_REPORT="{}"),
        capture_output=True, text=True, timeout=10,
    )
    assert "CPP Installation Incomplete" in result.stdout
    assert "CPP Installation Complete" not in result.stdout
    if write_fails:
        assert "Receipt write FAILED" in result.stdout
    else:
        assert "commands: FAILED" in result.stdout
        assert json.loads((tmp_path / ".claude/cpp-install.json").read_text())["steps"][0]["outcome"] == "FAILED"


def test_checkout_helper_is_not_in_executable_host_link_population():
    assert not HELPER.stat().st_mode & 0o111
    source = (ROOT / ".claude/commands/cpp/init.md").read_text()
    assert '[ -f "$script" ] && [ -x "$script" ] || continue' in source
