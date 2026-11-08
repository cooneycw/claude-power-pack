"""Committed #1617 controls: incomplete populations cannot pass via a retry."""

import json
import shutil
from io import StringIO
from pathlib import Path

import pytest

from lib.cicd.outcomes import pytest_incomplete_reason
from lib.cicd.runner import DeterministicRunner
from lib.cicd.steps import StepDef
from tests.test_flow_finish_gate import _run

ROOT = Path(__file__).resolve().parents[1]
requires_shell = pytest.mark.skipif(shutil.which("sh") is None, reason="requires sh")
requires_gate_tools = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("bash", "git", "awk")),
    reason="requires bash, git and awk",
)


@requires_shell
@requires_gate_tools
def test_interrupted_composite_cannot_be_cleared_by_filtered_retry(tmp_path: Path):
    fixture = ROOT / "tests/fixtures/interrupted-composite.sh"
    transcript = fixture.read_text()
    assert "collected 627 items" in transcript
    assert "KeyboardInterrupt" in transcript
    assert "12 passed" in transcript  # A tempting green filtered retry exists.
    log = StringIO()
    result = DeterministicRunner(
        project_root=tmp_path, output=log, rerun_failed=True
    ).run("check", step_defs=[
        StepDef(id="lint", command="true", gate=True),
        StepDef(id="test", command=f"sh '{fixture}'", gate=True),
        StepDef(id="typecheck", command="true", gate=True),
    ])
    # Feed the real runner result through the unchanged finish-gate consumer.
    cpp = tmp_path / "cpp"
    cpp.mkdir()
    (cpp / "CLAUDE.md").touch()
    gate, _ = _run(
        tmp_path, cpp_dir=str(cpp), uv_exit=0 if result.success else 1,
        uv_stdout=json.dumps(result.to_dict(), indent=2), inject_gates=False,
    )
    assert gate.returncode == 1, gate.stdout
    assert "FLOW_FINISH_GATE: fail" in gate.stdout
    assert not result.success, gate.stdout + log.getvalue()
    assert not result.reruns
    assert (tmp_path / "attempts").read_text() == "x"


@pytest.mark.parametrize("output,error", [
    ("=== test session starts ===\n=== 1 failed in 0.1s ===\n"
     "=== test session starts ===\n", ""),
    ("=== 1 failed in 0.1s ===\n", "!!!! KeyboardInterrupt !!!!\n"),
    ("=== 1 failed in 0.1s ===\n!!! Interrupted: stopping !!!\n", ""),
    ("=== test session starts ===\n=== test session starts ===\n",
     "=== 1 failed in 0.1s ===\n"),
    ("=== test session starts ===\n", "=== 1 failed in 0.1s ===\n"),
    ("=== 1 failed in 0.1s ===\n", "=== test session starts ===\n"),
])
def test_incomplete_evidence_is_independent_of_completed_summary_count(output, error):
    assert pytest_incomplete_reason(output, error) is not None


@pytest.mark.parametrize("output,error", [
    ("=== test session starts ===\n=== test session starts ===\n"
     "=== 1 passed in 0.1s ===\n=== 1 failed in 0.1s ===\n", ""),
    ("=== 1 failed in 0.1s ===\n", ""),
    ("::cicd-negative-control:BEGIN:BAD:interruption::\n"
     "=== test session starts ===\n!!! KeyboardInterrupt !!!\n"
     "::cicd-negative-control:END:BAD:interruption::\n"
     "=== 1 failed in 0.1s ===\n", ""),
])
def test_completed_or_labelled_child_evidence_does_not_refuse_retry(output, error):
    assert pytest_incomplete_reason(output, error) is None


def test_unmarked_quiet_interruption_cannot_be_inferred():
    # No start or interruption signal: indistinguishable from a completed quiet
    # invocation. The detector claims only to refuse observed incomplete work.
    assert pytest_incomplete_reason("=== 1 failed in 0.1s ===\n", "") is None


def test_crossed_stream_completion_cannot_be_attributed():
    # These streams could describe two completed sessions OR an unfinished
    # population plus an unrelated summary. Refuse only the filtered retry;
    # the original completed passing composite is still allowed to pass.
    assert pytest_incomplete_reason(
        "=== 1 failed in 0.1s ===\n=== test session starts ===\n",
        "=== test session starts ===\n=== 1 passed in 0.1s ===\n",
    ) is not None


@requires_shell
def test_unrelated_stderr_summary_cannot_complete_a_stdout_session(tmp_path):
    command = (
        "if [ -f attempted ]; then printf '%s\\n' '=== 1 passed in 0.01s ==='; "
        "else touch attempted; printf '%s\\n' '=== 1 failed in 0.01s ===' "
        "'FAILED tests/unit.py::test_one - AssertionError' >&2; "
        "printf '%s\\n' '=== test session starts ==='; exit 1; fi"
    )
    log = StringIO()
    result = DeterministicRunner(
        project_root=tmp_path, output=log, rerun_failed=True
    ).run("check", step_defs=[StepDef(id="test", command=command)])
    assert not result.success, log.getvalue()
    assert not result.reruns


@requires_shell
@pytest.mark.parametrize("unfinished", [
    "!!! KeyboardInterrupt !!!",
    "=== test session starts ===",
])
def test_interrupted_retry_is_inconclusive_even_if_wrapper_exits_zero(tmp_path, unfinished):
    # The original run is a legitimate single invocation. Only its retry is
    # incomplete; the wrapper masks the interrupted child's exit status.
    command = (
        "if [ -f attempted ]; then "
        f"printf '%s\\n' '=== 1 passed in 0.01s ===' '{unfinished}'; "
        "else touch attempted; printf '%s\\n' '=== 1 failed in 0.01s ===' "
        "'FAILED tests/unit.py::test_one - AssertionError'; exit 1; fi"
    )
    result = DeterministicRunner(
        project_root=tmp_path, output=StringIO(), rerun_failed=True
    ).run("check", step_defs=[StepDef(id="test", command=command)])
    assert not result.success
    assert result.reruns[0]["outcome"] == "inconclusive"


@requires_shell
@pytest.mark.parametrize("exit_code", [130, 137, 143])
def test_signal_exit_without_a_diagnostic_cannot_trigger_retry(tmp_path, exit_code):
    command = (
        "printf x >> attempts; printf '%s\\n' '=== 1 failed in 0.01s ===' "
        f"'FAILED tests/unit.py::test_one - AssertionError'; exit {exit_code}"
    )
    result = DeterministicRunner(
        project_root=tmp_path, output=StringIO(), rerun_failed=True
    ).run("check", step_defs=[StepDef(id="test", command=command)])
    assert not result.success
    assert result.reruns == []
    assert (tmp_path / "attempts").read_text() == "x"


@requires_shell
def test_completed_passing_composite_still_passes(tmp_path: Path):
    result = DeterministicRunner(
        project_root=tmp_path, output=StringIO(), rerun_failed=True
    ).run("check", step_defs=[StepDef(id="test", command=(
        "printf '%s\\n' '=== test session starts ===' '=== 3 passed in 0.01s ===' "
        "'=== test session starts ===' '=== 627 passed in 0.01s ==='"
    ))])
    assert result.success
    assert result.tests["test"]["invocations"] == 2
    assert not result.reruns
