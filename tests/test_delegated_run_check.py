"""Tests for scripts/delegated-run-check.sh (issue #798).

The helper exists because an exit code is not evidence on these lanes. Three
independent things all had to be true at once for a failed delegated run to
read as a success, and the third is the one no exit-code fix can reach:

1. `... | tee <file>` made `$?` the status of `tee`, not the CLI's.
2. In the `auto` documents the check lived in a different fenced block - a
   different shell - from the run.
3. The Qwen CLI reports `EXIT=0`, `subtype: "success"`, `is_error: false`,
   `num_turns: 1` over a run whose only trace of failure is
   `[API Error: Request timeout after 154s...]` inside the terminal `result`
   string (verified 2026-09-07, @qwen-code/qwen-code 0.15.10, unreachable
   endpoint).

So the pins below split along that seam: the exit code still decides what it
can decide, and the payload decides the rest. The api-error case is the one
that would have caught the original incident - a wrong `/qwen:*` endpoint that
went unnoticed long enough to matter because the harness reported success
throughout.

The helper is deliberately NOT fail-open, unlike every other advisory in the
flow family. `test_unparseable_output_is_a_failure_not_a_shrug` pins that
choice: a guard that cannot read the stream must not call the run clean, since
"the delegated model produced no output" IS the failure, not an inconclusive
reading of one.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "delegated-run-check.sh"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HELPER), *args],
        capture_output=True,
        text=True,
    )


def contract(out: str) -> dict[str, list[str]]:
    """Collect the DELEGATED_RUN_* lines; SIGNAL repeats, so every key is a list."""
    found: dict[str, list[str]] = {}
    for line in out.splitlines():
        if line.startswith("DELEGATED_RUN_"):
            key, _, value = line.partition(": ")
            found.setdefault(key, []).append(value)
    return found


def write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def clean_run(tmp_path: Path) -> Path:
    """A Qwen/Codex-shaped stream that really did work: tool events, many turns."""
    return write_jsonl(
        tmp_path / "clean.jsonl",
        [
            {"type": "system", "subtype": "init"},
            {"type": "assistant", "message": {"content": "Editing the file."}},
            {"type": "tool_use", "name": "edit_file"},
            {"type": "result", "subtype": "success", "is_error": False,
             "num_turns": 7, "result": "Implemented the change."},
        ],
    )


def test_a_clean_run_passes(clean_run: Path) -> None:
    proc = run(str(clean_run), "0", "--lane", "codex", "--expect-tools")
    assert proc.returncode == 0, proc.stdout
    assert contract(proc.stdout)["DELEGATED_RUN_STATUS"] == ["success"]
    assert "DELEGATED_RUN_SIGNAL" not in contract(proc.stdout)


def test_qwen_false_success_is_caught_by_the_payload(tmp_path: Path) -> None:
    """The incident shape: exit 0, is_error false, and a dead endpoint."""
    output = write_jsonl(
        tmp_path / "qwen.jsonl",
        [{"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
          "result": "[API Error: Request timeout after 154s. Please try again.]"}],
    )
    proc = run(str(output), "0", "--lane", "qwen")
    assert proc.returncode == 1, proc.stdout
    found = contract(proc.stdout)
    assert found["DELEGATED_RUN_STATUS"] == ["failure"]
    assert "api-error" in found["DELEGATED_RUN_SIGNAL"]
    # The detail line is what a human reads to diagnose; it must carry the text.
    assert "[API Error" in found["DELEGATED_RUN_DETAIL"][0]
    # And it must fail on the payload ALONE - no --expect-tools was passed.


def test_forced_timeout_is_reported_as_a_failure(clean_run: Path) -> None:
    """`timeout` exit 124: the branch the `| tee` bug made unreachable."""
    proc = run(str(clean_run), "124", "--lane", "gemma")
    assert proc.returncode == 1, proc.stdout
    found = contract(proc.stdout)
    assert found["DELEGATED_RUN_STATUS"] == ["failure"]
    assert "timeout" in found["DELEGATED_RUN_SIGNAL"]
    assert "exit-nonzero" in found["DELEGATED_RUN_SIGNAL"]


def test_a_real_forced_timeout_reaches_the_helper_as_124(tmp_path: Path) -> None:
    """End-to-end on the shell shape the commands now use.

    The point of this test is the REDIRECT, not the helper: with `| tee` the
    same pipeline yields 0. Both forms run here so the difference is pinned by
    execution rather than by assertion.
    """
    output = tmp_path / "timeout.jsonl"

    piped = subprocess.run(
        f'timeout 1 sleep 5 2>&1 | tee "{output}" >/dev/null; echo $?',
        shell=True, capture_output=True, text=True, executable="/bin/bash",
    )
    assert piped.stdout.strip() == "0", "the tee pipeline masks 124 - the #798 bug"

    redirected = subprocess.run(
        f'timeout 1 sleep 5 > "{output}" 2>&1; echo $?',
        shell=True, capture_output=True, text=True, executable="/bin/bash",
    )
    captured = redirected.stdout.strip()
    assert captured == "124", "the redirect must surface the timeout status"

    proc = run(str(output), captured, "--lane", "qwen")
    assert proc.returncode == 1
    assert "timeout" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_empty_output_is_a_failure(tmp_path: Path) -> None:
    output = tmp_path / "empty.jsonl"
    output.write_text("", encoding="utf-8")
    proc = run(str(output), "0", "--lane", "qwen")
    assert proc.returncode == 1, proc.stdout
    assert "output-empty" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_missing_output_is_a_failure(tmp_path: Path) -> None:
    proc = run(str(tmp_path / "never-written.jsonl"), "0")
    assert proc.returncode == 1, proc.stdout
    assert "output-missing" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_unparseable_output_is_a_failure_not_a_shrug(tmp_path: Path) -> None:
    """Not fail-open, by design - see the module docstring."""
    output = tmp_path / "garbage.jsonl"
    output.write_text("this is not json\nnor is this\n", encoding="utf-8")
    proc = run(str(output), "0", "--lane", "gemma")
    assert proc.returncode == 1, proc.stdout
    assert contract(proc.stdout)["DELEGATED_RUN_STATUS"] == ["failure"]


def test_no_turns_fails_only_when_tools_were_expected(tmp_path: Path) -> None:
    """`num_turns <= 1` is a flag on an exec run and a failure on an auto run.

    An `/*:exec` prompt can legitimately be answered without touching a file;
    an `/*:auto` run delegated an implementation, so a tool-free run wrote no
    code. One flag separates the two rather than two code paths.
    """
    output = write_jsonl(
        tmp_path / "one-turn.jsonl",
        [{"type": "result", "subtype": "success", "is_error": False,
          "num_turns": 1, "result": "I would suggest editing config.py."}],
    )

    lenient = run(str(output), "0", "--lane", "qwen")
    assert lenient.returncode == 0, lenient.stdout
    assert "no-turns" in contract(lenient.stdout)["DELEGATED_RUN_SIGNAL"], \
        "the signal must still be REPORTED - a silent pass hides the same thing"

    strict = run(str(output), "0", "--lane", "qwen", "--expect-tools")
    assert strict.returncode == 1, strict.stdout
    assert contract(strict.stdout)["DELEGATED_RUN_STATUS"] == ["failure"]


def test_gemma_tool_call_drop_signature_is_caught(tmp_path: Path) -> None:
    """OpenCode text-only stream: the ollama/ollama#14958 `/v1` signature."""
    output = write_jsonl(
        tmp_path / "gemma.jsonl",
        [
            {"type": "step_start"},
            {"type": "text", "part": {"text": "I will edit the file now."}},
            {"type": "step_finish", "part": {"reason": "stop", "tokens": {"output": 40}}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma", "--expect-tools")
    assert proc.returncode == 1, proc.stdout
    assert "no-tool-use" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_gemma_tool_events_satisfy_the_tool_check(tmp_path: Path) -> None:
    """The positive control for the test above (a guard that never passes is not a guard)."""
    output = write_jsonl(
        tmp_path / "gemma-ok.jsonl",
        [
            {"type": "step_start"},
            {"type": "tool_use", "part": {"tool": "edit", "state": {"status": "completed"}}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma", "--expect-tools")
    assert proc.returncode == 0, proc.stdout


def test_explicit_error_flag_is_a_failure(tmp_path: Path) -> None:
    output = write_jsonl(
        tmp_path / "err.jsonl",
        [
            {"type": "tool_use", "name": "edit_file"},
            {"type": "result", "subtype": "error", "is_error": True, "num_turns": 4,
             "result": "connection refused"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    assert proc.returncode == 1, proc.stdout
    assert "error-payload" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_api_error_in_prose_does_not_false_positive(tmp_path: Path) -> None:
    """A model DISCUSSING the banner is not a run that hit it.

    A raw `grep '\\[API Error'` over the stream would match this - and would
    match any diff quoting the helper itself, which is how a guard against
    false success becomes a source of false failure. The check is anchored to
    payload FIELDS and to the START of the string.
    """
    output = write_jsonl(
        tmp_path / "prose.jsonl",
        [
            {"type": "tool_use", "name": "edit_file"},
            {"type": "assistant", "message": {
                "content": 'Added a test asserting the text "[API Error" is treated as a failure.'}},
            {"type": "result", "subtype": "success", "is_error": False, "num_turns": 5,
             "result": "Added handling for the [API Error prefix in the guard."},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex", "--expect-tools")
    assert proc.returncode == 0, proc.stdout
    assert contract(proc.stdout)["DELEGATED_RUN_STATUS"] == ["success"]


def test_bare_api_error_banner_outside_json_is_caught(tmp_path: Path) -> None:
    """Harnesses sometimes print the banner as a plain stderr line into the stream."""
    output = tmp_path / "banner.jsonl"
    output.write_text(
        '{"type":"tool_use","name":"edit_file"}\n'
        "[API Error: Request timeout after 154s]\n",
        encoding="utf-8",
    )
    proc = run(str(output), "0", "--lane", "qwen")
    assert proc.returncode == 1, proc.stdout
    assert "api-error" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_contract_always_reports_the_inputs_it_judged(clean_run: Path) -> None:
    """Lane, file and exit are echoed so a transcript shows WHAT was assessed."""
    proc = run(str(clean_run), "0", "--lane", "qwen")
    found = contract(proc.stdout)
    assert found["DELEGATED_RUN_LANE"] == ["qwen"]
    assert found["DELEGATED_RUN_FILE"] == [str(clean_run)]
    assert found["DELEGATED_RUN_EXIT"] == ["0"]


@pytest.mark.parametrize(
    "args",
    [
        (),                                  # no arguments at all
        ("only-a-path",),                    # missing the exit code
        ("path", "not-a-number"),            # exit code must be an integer
        ("path", "0", "--lane", "mistral"),  # unknown lane
    ],
    ids=["no-args", "no-exit-code", "non-numeric-exit", "unknown-lane"],
)
def test_usage_errors_exit_2(args: tuple[str, ...]) -> None:
    """Usage errors are distinct from a failed run - 2, never 1."""
    proc = run(*args)
    assert proc.returncode == 2, proc.stdout + proc.stderr


def test_quiet_suppresses_prose_but_never_the_contract(clean_run: Path) -> None:
    proc = run(str(clean_run), "0", "--lane", "qwen", "--quiet")
    assert proc.returncode == 0
    assert "DELEGATED_RUN_STATUS: success" in proc.stdout
    assert "looks clean" not in proc.stdout
