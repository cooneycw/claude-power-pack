"""Issue #1576: empty output requires a per-command declaration, not inference."""

import os
import shlex
import shutil
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
import yaml

from lib.cicd.manifest import StepModel, step_model_to_step_def
from lib.cicd.runner import DeterministicRunner
from lib.cicd.steps import StepDef

QUIET_TEST = Path(__file__).parent / "fixtures" / "silent-test-success" / "quiet_harness.py"
PYTHON = shlex.quote(str(Path(sys.executable).resolve()))
NOOP = f"{PYTHON} -c pass"
QUIET = f"{PYTHON} {shlex.quote(str(QUIET_TEST))}"
REASON = "Intentional quiet harness; exit status is the declared evidence"


def run_case(root, command, reason=None, **kwargs):
    step = step_model_to_step_def(
        "test", StepModel(command=command, silent_success=reason, **kwargs)
    )
    log = StringIO()
    result = DeterministicRunner(project_root=root, output=log).run(
        "check", step_defs=[step]
    )
    return result, log.getvalue()


def assert_unknown(result, log):
    assert result.success  # Process success is distinct from established tests.
    assert len(result.warnings) == 1
    assert "UNKNOWN" in result.warnings[0]
    assert not result.tests  # Never invent a test count for a quiet process.
    assert "WITH WARNINGS" in log


def test_undeclared_silent_noop_vs_explicit_intent(tmp_path):
    undeclared, log = run_case(tmp_path / "undeclared", NOOP)
    assert_unknown(undeclared, log)
    declared, log = run_case(tmp_path / "declared", NOOP, REASON)
    assert declared.success and not declared.warnings and not declared.tests
    assert "SILENT SUCCESS DECLARED" in log and REASON in log


def test_explicit_noop_does_not_waive_nonempty_output(tmp_path):
    declared, _ = run_case(tmp_path / "silent", NOOP, REASON)
    assert declared.success and not declared.warnings
    unparsed, log = run_case(tmp_path / "unparsed", "printf 'unclassified result'", REASON)
    assert_unknown(unparsed, log)


def test_real_quiet_test_needs_intent_and_still_fails(tmp_path):
    unknown, log = run_case(tmp_path / "undeclared", QUIET)
    assert_unknown(unknown, log)
    quiet, _ = run_case(tmp_path / "declared", QUIET, REASON)
    assert quiet.success and not quiet.warnings and not quiet.tests
    failed, _ = run_case(tmp_path / "failed", QUIET + " --fail", REASON)
    assert not failed.success


@pytest.mark.parametrize("reason", [None, REASON])
def test_recognized_summary_wins_and_quiet_counterpart_is_unknown(tmp_path, reason):
    parsed, log = run_case(tmp_path / "summary", QUIET + " --summary", reason)
    assert parsed.success and not parsed.warnings
    assert parsed.tests["test"]["passed"] == 1
    assert "SILENT SUCCESS DECLARED" not in log
    quiet, log = run_case(tmp_path / "quiet", QUIET)
    assert_unknown(quiet, log)


def test_nonempty_unparsed_vs_recognized_summary(tmp_path):
    unknown, log = run_case(tmp_path / "unparsed", "printf 'unclassified result'")
    assert_unknown(unknown, log)
    parsed, _ = run_case(tmp_path / "summary", QUIET + " --summary")
    assert parsed.success and not parsed.warnings and parsed.tests["test"]["passed"] == 1


@pytest.mark.parametrize("command", ["printf ' '", "printf '\\n' >&2"])
def test_whitespace_is_nonempty_even_with_intent(tmp_path, command):
    result, log = run_case(tmp_path, command, REASON)
    assert_unknown(result, log)


def test_unsupported_runner_does_not_declare_silence(tmp_path):
    result, log = run_case(tmp_path, NOOP, unsupported_runner="quiet harness")
    assert_unknown(result, log)


@pytest.mark.parametrize("value", ["", "  ", True, False, 1, [], {}])
def test_silent_intent_is_a_nonempty_strict_string(value):
    with pytest.raises(ValueError):
        StepModel(command="true", silent_success=value)


def test_silent_intent_survives_conversion_and_serialization():
    step = step_model_to_step_def(
        "test", StepModel(command="true", silent_success="  deliberate no-op  ")
    )
    assert step.silent_success == "deliberate no-op"
    assert step.to_dict()["silent_success"] == "deliberate no-op"
    assert "silent_success" not in StepDef(id="test", command="true").to_dict()


@pytest.mark.parametrize("value", ["", "  ", True, False, 1])
def test_direct_step_def_also_requires_a_nonempty_explanation(value):
    with pytest.raises(ValueError):
        StepDef(id="test", command="true", silent_success=value)


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("uv") is None,
    reason="requires bash and uv for the real finish helper",
)
@pytest.mark.parametrize("declared, expected_exit", [(False, 3), (True, 0)])
def test_actual_finish_helper_preserves_the_silent_verdict(tmp_path, declared, expected_exit):
    root = Path(__file__).resolve().parents[1]
    # Give uv an owned runtime checkout. The helper pins Python 3.11 and must
    # never recreate the venv of a surrounding pytest running another Python.
    cpp = tmp_path / "cpp"
    cpp.mkdir()
    shutil.copytree(root / "lib", cpp / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("pyproject.toml", "uv.lock", "CLAUDE.md"):
        shutil.copyfile(root / name, cpp / name)
    project = tmp_path / "project"
    project.mkdir()
    config = project / ".claude" / "cicd_tasks.yml"
    config.parent.mkdir()
    step = {"command": NOOP}
    if declared:
        step["silent_success"] = REASON
    # The real helper requires every declared builtin gate. Non-test no-ops
    # keep this fixture about silent test evidence, not missing-plan warnings.
    gates = ["lint", "test", "typecheck", "security_scan", "verify"]
    steps = {name: {"command": NOOP} for name in gates}
    steps["test"] = step
    config.write_text(yaml.safe_dump({
        "version": "1", "steps": steps,
        "plans": {"finish": {"steps": gates}},
    }))
    env = os.environ.copy()
    env["FLOW_GATE_CPP_DIR"] = str(cpp)
    env.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        ["bash", str(root / "scripts" / "flow-finish-gate.sh")],
        cwd=project, env=env, capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
    assert "FLOW_FINISH_GATE: " + ("ok" if declared else "warn") in result.stdout
