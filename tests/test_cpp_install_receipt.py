"""Exercise the project receipt and the summary/status its consumers read."""

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "cpp-install-receipt.py"
CASES = json.loads((ROOT / "tests/fixtures/cpp-install-receipt/cases.json").read_text())
REVISION = "a" * 40


def run(project, command, *args, data=None):
    if command == "write" and "--offered-steps" not in args:
        args = (*args, "--offered-steps", json.dumps([item["step"] for item in data or []]))
    return subprocess.run(  # binary-guard: allow explicit --revision bypasses git
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
    assert receipt["selected"] == {"tier": 1, "profile": "not-selected", "capabilities": ["commands"]}
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
@pytest.mark.skipif(shutil.which("git") is None, reason="shipped summary derives checkout revision with git")
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
                 STEP_RESULTS_JSON=json.dumps(data), OFFERED_STEPS_JSON=json.dumps(["commands", "stash-guard"]),
                 PERMISSION_REPORT="{}"),
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


def test_missing_offered_observation_cannot_make_a_complete_receipt(monkeypatch):
    spec = importlib.util.spec_from_file_location("install_receipt", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    offered = ["commands", "stash-guard", "project-commands"]
    observations = CASES[0]["steps"]
    assert "project-commands" not in {item["step"] for item in observations}, \
        "negative-fixture precondition: an explicitly offered step has no observation"
    args = SimpleNamespace(tier=1, profile="not-selected", permission_report="{}", offered_steps=json.dumps(offered))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(observations)))
    receipt = module.make_receipt(args, REVISION)
    assert not module.complete(receipt), "missing offered observation was silently reported complete"
    assert next(item for item in receipt["steps"] if item["step"] == "project-commands")["outcome"] == "unverified"


def test_receipt_project_write_is_disclosed_before_installation_confirmation():
    source = (ROOT / ".claude/commands/cpp/init.md").read_text()
    execution = source.index("## Step 5:")
    disclosure = source[:execution]
    assert ".claude/cpp-install.json" in disclosure, "the project write must be disclosed before confirmation"


def test_cli_missing_offered_observation_is_recorded_unverified(tmp_path):
    result = run(tmp_path, "write", "--tier", "1", "--profile", "not-selected",
                 "--offered-steps", json.dumps(["commands", "stash-guard", "project-commands"]),
                 data=CASES[0]["steps"])
    assert result.returncode == 0, result.stdout
    receipt = json.loads((tmp_path / ".claude/cpp-install.json").read_text())
    assert set(receipt["offered_steps"]) == {"commands", "stash-guard", "project-commands"}
    assert next(item for item in receipt["steps"] if item["step"] == "project-commands")["outcome"] == "unverified"
    summary = run(tmp_path, "summary")
    assert summary.returncode == 1 and "CPP Installation Incomplete" in summary.stdout
    assert "project-commands: unverified" in summary.stdout


@pytest.mark.parametrize("offered", ["null", "{}", '["commands","commands"]', '["PRIVATE_VALUE_DO_NOT_SAVE"]'])
def test_invalid_offered_population_never_overwrites_an_old_receipt(tmp_path, offered):
    assert run(tmp_path, "write", "--tier", "1", "--profile", "not-selected", data=CASES[0]["steps"]).returncode == 0
    path = tmp_path / ".claude/cpp-install.json"
    before = path.read_bytes()
    result = run(tmp_path, "write", "--tier", "1", "--profile", "not-selected",
                 "--offered-steps", offered, data=CASES[0]["steps"])
    assert result.returncode == 1
    assert path.read_bytes() == before
    assert "PRIVATE_VALUE_DO_NOT_SAVE" not in result.stdout + result.stderr + path.read_text()


@pytest.mark.parametrize("tier,expected", [
    (1, ["commands"]), (5, ["commands", "scripts", "mcp", "cicd", "codex"]),
    (6, ["commands", "qwen"]), (7, ["commands", "gemma"]),
])
def test_preset_capabilities_are_selections_not_success_observations(tmp_path, tier, expected):
    assert run(tmp_path, "write", "--tier", str(tier), "--profile", "not-selected", data=[]).returncode == 0
    receipt = json.loads((tmp_path / ".claude/cpp-install.json").read_text())
    assert receipt["selected"]["capabilities"] == expected
    assert all(item["outcome"] == "unverified" for item in receipt["steps"])
    assert run(tmp_path, "summary").returncode == 1


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("python3") is None, reason="requires bash and python3")
def test_registered_controls_discriminate_and_repaired_cases_stop_detection():
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/check-negative-controls.py"),
        "--root", str(ROOT), "--control", "controls/cpp-install-receipt", "--strict",
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NEGATIVE_CONTROL_VERDICT: PASS" in result.stdout
    for case in ("bad-nonzero", "bad-missing-offered", "bad-old-green-write-fails", "bad-summary-read"):
        assert f"on case {case}: missed the known-bad input (blind, as required)" in result.stdout
    for case in ("good-repaired-nonzero", "good-repaired-offered", "good-repaired-write", "good-repaired-summary"):
        assert f"case {case}: expected=GOOD observed=GOOD" in result.stdout


def test_explicit_revision_does_not_invoke_git(monkeypatch):
    spec = importlib.util.spec_from_file_location("install_receipt", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def refuse_command(*args, **kwargs):
        raise AssertionError("explicit revision must bypass subprocess execution")

    monkeypatch.setattr(module.subprocess, "run", refuse_command)
    assert module.revision(SimpleNamespace(revision=REVISION, cpp_dir=ROOT)) == REVISION


def test_conditional_tavily_skip_and_stash_opt_out_are_not_install_failures():
    spec = importlib.util.spec_from_file_location("install_receipt", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # These choices are conditional/optional in the existing wizard. They have
    # an explicit observation, unlike an omitted offered step.
    data = {"steps": [{"step": "commands", "outcome": "installed"},
                      {"step": "stash-guard", "outcome": "declined"},
                      {"step": "tavily", "outcome": "skipped"}]}
    assert module.complete(data), "an explicit conditional skip must remain distinct from missing evidence"


@pytest.mark.skipif(any(shutil.which(tool) is None for tool in ("bash", "python3", "git")),
                    reason="real helper and shipped shell consumer require bash/python3/git")
@pytest.mark.parametrize("fault", ["absent", "invalid", "revision-unavailable"])
def test_failed_summary_read_always_emits_incomplete_verdict(tmp_path, fault):
    text = (ROOT / ".claude/commands/cpp/init.md").read_text()
    match = re.search(r"# CPP_INSTALL_RECEIPT_WRITE_BEGIN\n(.*?)# CPP_INSTALL_RECEIPT_WRITE_END", text, re.S)
    assert match
    wrapper = tmp_path / "receipt-fault.py"
    missing_cpp = tmp_path / "missing-cpp-checkout"
    assert not missing_cpp.exists(), "negative-fixture precondition: owned revision lookup target absent"
    wrapper.write_text(
        "import pathlib, subprocess, sys\n"
        f"helper = {str(HELPER)!r}\n"
        "args = sys.argv[1:]\n"
        f"fault = {fault!r}\n"
        "if args[0] == 'summary' and fault == 'revision-unavailable':\n"
        f"    args += ['--cpp-dir', {str(missing_cpp)!r}]\n"
        "result = subprocess.run([sys.executable, helper, *args])\n"
        "if args[0] == 'write' and result.returncode == 0:\n"
        "    receipt = pathlib.Path('.claude/cpp-install.json')\n"
        "    if fault == 'absent':\n"
        "        receipt.unlink()\n"
        "        assert not receipt.exists()\n"
        "    if fault == 'invalid':\n"
        "        receipt.write_text('{')\n"
        "        assert receipt.read_text() == '{'\n"
        "raise SystemExit(result.returncode)\n"
    )
    script = match[1].replace('"$CPP_DIR/scripts/cpp-install-receipt.py"', '"$CPP_TEST_RECEIPT_HELPER"')
    result = subprocess.run(
        ["bash", "-c", script], cwd=tmp_path, capture_output=True, text=True, timeout=15,
        env=dict(os.environ, CPP_DIR=str(ROOT), CPP_TEST_RECEIPT_HELPER=str(wrapper),
                 SELECTED_TIER="1", PROFILE_NAME="not-selected", PERMISSION_REPORT="{}",
                 STEP_RESULTS_JSON=json.dumps(CASES[0]["steps"]),
                 OFFERED_STEPS_JSON=json.dumps(["commands", "stash-guard"])),
    )
    assert "CPP_INSTALL_RECEIPT: saved" in result.stdout, "precondition: persistence succeeded before summary fault"
    assert "CPP Installation Incomplete" in result.stdout, result.stdout + result.stderr
    assert "CPP Installation Complete" not in result.stdout
