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
    """--quiet drops the human summary and keeps every contract line.

    This used to assert `"looks clean" not in proc.stdout`, naming the exact
    prose string of the day. #836 rewrote that sentence, which would have left
    the assertion permanently true and covering nothing - green forever, testing
    nothing, the vacuous pass this repo keeps finding. It now pins the PROPERTY:
    no human-readable line survives --quiet, whatever that line currently says.
    Every prose line the helper prints begins with `delegated-run-check:` or is
    indented beneath one, so absence of both is the durable form of the claim.
    """
    proc = run(str(clean_run), "0", "--lane", "qwen", "--quiet")
    assert proc.returncode == 0
    assert "DELEGATED_RUN_STATUS: success" in proc.stdout
    assert "DELEGATED_RUN_TOOL_ERRORS: 0" in proc.stdout
    prose = [
        line
        for line in proc.stdout.splitlines()
        if line.startswith("delegated-run-check:") or line.startswith("  ")
    ]
    assert prose == [], f"--quiet left prose behind: {prose}"


def test_the_quiet_assertion_can_fail(clean_run: Path) -> None:
    """Positive control for the test above.

    Without --quiet the helper DOES print prose, so the filter that test relies
    on must find something here. If this ever goes empty, the assertion above has
    stopped meaning anything regardless of what the helper does.
    """
    proc = run(str(clean_run), "0", "--lane", "qwen")
    prose = [
        line
        for line in proc.stdout.splitlines()
        if line.startswith("delegated-run-check:") or line.startswith("  ")
    ]
    assert prose, "the prose detector matched nothing even without --quiet"


# ---------------------------------------------------------------------------
# Findings from the cross-model (Codex) review of this change. Each of these
# was a real defect in the first cut of the helper, and three of them would
# have made it WORSE than no check at all - failing runs that succeeded.
# ---------------------------------------------------------------------------


def test_codex_command_and_file_events_count_as_tool_use(tmp_path: Path) -> None:
    """The false-positive that would have broken `/codex:auto` outright.

    The first cut recognized only `tool_use`-shaped events. Real
    `codex exec --json` streams signal work as `item.completed` wrapping an
    `item.type` of `command_execution` or `file_change` - verified against five
    captures in /tmp. None matched, so every SUCCESSFUL Codex implementation
    scored `no-tool-use` and failed under the `--expect-tools` its own auto
    lane passes. Format facts get verified against real streams, not guessed.
    """
    output = write_jsonl(
        tmp_path / "codex.jsonl",
        [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"id": "i1", "type": "agent_message",
                                                "text": "Editing the file."}},
            {"type": "item.completed", "item": {"id": "i2", "type": "command_execution",
                                                "command": "/bin/bash -lc 'pytest -q'",
                                                "aggregated_output": "5 passed"}},
            {"type": "item.completed", "item": {"id": "i3", "type": "file_change",
                                                "changes": [{"path": "a.py", "kind": "modify"}]}},
            {"type": "turn.completed", "usage": {"input_tokens": 10}},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex", "--expect-tools")
    assert proc.returncode == 0, proc.stdout
    assert "DELEGATED_RUN_SIGNAL" not in contract(proc.stdout), proc.stdout


def test_agent_message_alone_is_not_tool_use(tmp_path: Path) -> None:
    """The positive control for the test above: talking is not working."""
    output = write_jsonl(
        tmp_path / "talk.jsonl",
        [
            {"type": "thread.started"},
            {"type": "item.completed", "item": {"type": "agent_message",
                                                "text": "I would change config.py."}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex", "--expect-tools")
    assert proc.returncode == 1, proc.stdout
    assert "no-tool-use" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_a_denied_tool_call_is_not_a_failed_run(tmp_path: Path) -> None:
    """The fence working is not the run failing.

    `/gemma:auto` states in as many words that a denied command comes back as a
    `tool_use` with `state.status: "error"` and that "a model that tries
    `git commit` once and moves on is behaving exactly as designed". The first
    cut scanned every nesting level for `is_error` / a non-empty `error`, so it
    failed exactly that run - the helper contradicting the document it serves.
    """
    output = write_jsonl(
        tmp_path / "denied.jsonl",
        [
            {"type": "step_start"},
            {"type": "tool_use", "part": {"tool": "bash", "state": {
                "status": "error",
                "error": "permission denied by rule: git commit*"}}},
            {"type": "tool_use", "part": {"tool": "edit", "state": {"status": "completed"}}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma", "--expect-tools")
    assert proc.returncode == 0, proc.stdout
    assert contract(proc.stdout)["DELEGATED_RUN_STATUS"] == ["success"]


def test_api_error_quoted_at_the_start_of_a_message_is_not_a_failure(tmp_path: Path) -> None:
    """Anchoring alone was not enough - the field has to be terminal too.

    A model whose message BEGINS with the banner (quoting a log it was asked to
    fix, say) tripped the first cut, because the scan walked every nested
    `content`. The check now looks only at terminal and error events.
    """
    output = write_jsonl(
        tmp_path / "quote.jsonl",
        [
            {"type": "tool_use", "name": "edit_file"},
            {"type": "assistant", "message": {
                "content": "[API Error: Request timeout after 154s] is the string to match."}},
            {"type": "result", "subtype": "success", "is_error": False,
             "num_turns": 6, "result": "Added the matcher."},
        ],
    )
    proc = run(str(output), "0", "--lane", "qwen", "--expect-tools")
    assert proc.returncode == 0, proc.stdout
    assert contract(proc.stdout)["DELEGATED_RUN_STATUS"] == ["success"]


def test_a_stream_of_empty_objects_is_not_a_run(tmp_path: Path) -> None:
    """`{}` parses as JSON; it is not evidence that anything happened."""
    output = tmp_path / "hollow.jsonl"
    output.write_text("{}\n{}\n{}\n", encoding="utf-8")
    proc = run(str(output), "0", "--lane", "qwen")
    assert proc.returncode == 1, proc.stdout
    assert "output-unrecognized" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


def test_a_truncated_stream_fails_an_auto_lane_but_not_an_exec_lane(tmp_path: Path) -> None:
    """A run whose stream stops before its terminal event did not finish.

    Gated on `--expect-tools` rather than made absolute, and the reason is
    empirical: `turn.completed` was absent from 2 of 5 real codex captures, one
    of them a run still executing when sampled. Failing every lane on a missing
    terminal event would have broken working runs - the expensive direction.
    A killed `exec` stream still leaves a usable partial answer; a killed `auto`
    stream leaves an incomplete implementation.
    """
    output = write_jsonl(
        tmp_path / "cut.jsonl",
        [
            {"type": "thread.started"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "command_execution",
                                                "command": "pytest"}},
        ],
    )
    lenient = run(str(output), "0", "--lane", "codex")
    assert lenient.returncode == 0, lenient.stdout
    assert "no-terminal-event" in contract(lenient.stdout)["DELEGATED_RUN_SIGNAL"]

    strict = run(str(output), "0", "--lane", "codex", "--expect-tools")
    assert strict.returncode == 1, strict.stdout


def test_top_level_error_event_still_fails(tmp_path: Path) -> None:
    """Narrowing the error scan must not blind it to a real harness error."""
    output = write_jsonl(
        tmp_path / "harness-error.jsonl",
        [
            {"type": "tool_use", "name": "edit_file"},
            {"type": "error", "message": "connection refused reaching the model endpoint"},
            {"type": "step_finish", "part": {"reason": "error"}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma", "--expect-tools")
    assert proc.returncode == 1, proc.stdout
    assert "error-payload" in contract(proc.stdout)["DELEGATED_RUN_SIGNAL"]


# ---------------------------------------------------------------------------
# Real captures, not hand-written shapes. Every format fact this helper relies
# on was verified against actual `codex exec --json` / OpenCode / Qwen Code
# streams; these are redacted slices of those files, so a harness that changes
# its event vocabulary turns this red instead of silently defeating the check.
# `qwen-api-error.jsonl` is the ORIGINAL INCIDENT: a real 2026-09-07 run with
# exit 0, `is_error: false`, `num_turns: 1`, and the endpoint dead.
# ---------------------------------------------------------------------------

FIXTURES = ROOT / "tests" / "fixtures" / "delegated_runs"


@pytest.mark.parametrize(
    ("name", "lane", "expect_failure", "signal"),
    [
        ("codex-complete.jsonl", "codex", False, None),
        ("gemma-complete.jsonl", "gemma", False, None),
        ("codex-truncated.jsonl", "codex", True, "no-terminal-event"),
        ("qwen-api-error.jsonl", "qwen", True, "api-error"),
    ],
    ids=["codex-real-success", "gemma-real-success", "codex-real-truncated", "qwen-real-incident"],
)
def test_verdicts_on_real_captures(
    name: str, lane: str, expect_failure: bool, signal: str | None
) -> None:
    """The two success cases matter as much as the failures.

    A checker that fails everything would satisfy the incident tests and break
    every lane. `codex-complete` and `gemma-complete` are real runs that did
    real work, and they must come back clean.
    """
    path = FIXTURES / name
    assert path.exists(), f"missing fixture {path}"

    proc = run(str(path), "0", "--lane", lane, "--expect-tools")
    found = contract(proc.stdout)

    if expect_failure:
        assert proc.returncode == 1, proc.stdout
        assert found["DELEGATED_RUN_STATUS"] == ["failure"]
        assert signal in found["DELEGATED_RUN_SIGNAL"], proc.stdout
    else:
        assert proc.returncode == 0, proc.stdout
        assert found["DELEGATED_RUN_STATUS"] == ["success"]
        assert "no-tool-use" not in found.get("DELEGATED_RUN_SIGNAL", []), (
            "a real run that edited files must never read as tool-free - this is "
            "the false positive that would have broken /codex:auto outright"
        )


# ---------------------------------------------------------------------------
# Issue #836: the verdict answers "did the PROCESS run cleanly", and its reader
# takes it for "did the WORK happen". A denied tool call satisfies every signal
# this helper has, so a run whose every command was refused reports `success`.
#
# The remedy is deliberately NOT a wider `is_fatal` - that version existed and
# was reverted because it made every fenced `git commit` a failed run. The
# larger question gets its own channel: a count the caller can act on.
#
# These pins run the helper against crafted streams rather than reading its
# source, because the claim under test is behavioural. A structural assertion
# would pass against a script that no longer does any of this.
# ---------------------------------------------------------------------------


def test_a_run_whose_tool_call_was_denied_reports_success_and_says_so(tmp_path: Path) -> None:
    """The #836 scenario end to end, both halves.

    Either half alone is the bug: reporting `failure` would re-introduce the
    reverted defect, and reporting `success` with nothing else would leave the
    caller exactly as blind as before.
    """
    output = write_jsonl(
        tmp_path / "denied-docker.jsonl",
        [
            {"type": "step_start"},
            {"type": "tool_use", "part": {"tool": "bash", "state": {
                "status": "error",
                "error": "permission denied by rule: docker*"}}},
            {"type": "text", "part": {"text": "I cannot run docker commands."}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma", "--expect-tools")
    found = contract(proc.stdout)
    assert proc.returncode == 0, proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["success"], "the fence working is not a failed run"
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], "the refusal must be reported somewhere"


def test_tool_errors_is_emitted_as_zero_on_a_clean_run(clean_run: Path) -> None:
    """The membership floor, which is why this line is always emitted.

    A count that appeared only when non-zero could not tell "I looked and found
    none" from "this version does not look", and telling those apart is the
    entire reason the line exists.
    """
    proc = run(str(clean_run), "0", "--lane", "qwen", "--expect-tools")
    assert contract(proc.stdout)["DELEGATED_RUN_TOOL_ERRORS"] == ["0"]


def test_the_tool_error_counter_can_fire(tmp_path: Path) -> None:
    """Positive control: a zero from the test above must mean something.

    Two errored calls, so this also pins that the line carries a COUNT rather
    than a boolean - a caller distinguishing one refusal from a wholly refused
    run needs the number.
    """
    output = write_jsonl(
        tmp_path / "two-errors.jsonl",
        [
            {"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error"}}},
            {"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error"}}},
            {"type": "tool_use", "part": {"tool": "edit", "state": {"status": "completed"}}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "gemma").stdout)["DELEGATED_RUN_TOOL_ERRORS"] == ["2"]


def test_a_non_tool_error_state_is_not_counted_as_a_tool_error(tmp_path: Path) -> None:
    """The counter's own ownership boundary, pinned rather than left as a TODO.

    `state.status: "error"` is not proof of a TOOL error - it is only that when
    it sits inside a tool event. Counting it anywhere would make an unrelated
    neighbour inflate the number, which is the defect this whole cluster is
    about, one level down in the fix for it.
    """
    output = write_jsonl(
        tmp_path / "non-tool.jsonl",
        [
            {"type": "text", "part": {"state": {"status": "error"}}},
            {"type": "tool_use", "part": {"tool": "edit", "state": {"status": "completed"}}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "gemma").stdout)["DELEGATED_RUN_TOOL_ERRORS"] == ["0"]


def test_the_success_prose_no_longer_claims_the_work_happened(clean_run: Path) -> None:
    """The sentence was the defect, so the sentence is pinned.

    "the run looks clean" is what got read as "the work happened". This asserts
    the narrower claim is stated and the broader one is explicitly disclaimed -
    a caller who reads only the prose must not come away with the wrong
    question answered.
    """
    proc = run(str(clean_run), "0", "--lane", "qwen")
    assert "looks clean" not in proc.stdout
    assert "no harness-level failure" in proc.stdout
    assert "does not establish that the requested work happened" in proc.stdout


def test_the_contract_carries_every_always_emitted_line(clean_run: Path) -> None:
    """An enumeration of the contract goes stale silently; this one cannot.

    Adopted from w1's #884 finding: the dangerous sentence after a change is not
    one that mentions what you changed, it is one that never names it and simply
    assumed it. `docs/scripts.md` enumerated the contract lines and, on adding
    `_TOOL_ERRORS`, that list quietly stopped being complete while reading
    perfectly. No grep for the new name finds an omission of the new name.

    So the always-emitted family is pinned here instead of described anywhere.
    A line added to the helper without being added here fails; a line dropped
    from the helper fails too.
    """
    proc = run(str(clean_run), "0", "--lane", "qwen")
    always = {
        "DELEGATED_RUN_LANE",
        "DELEGATED_RUN_FILE",
        "DELEGATED_RUN_EXIT",
        # The denominator (#892). A helper whose defect was "reports success
        # when nothing ran" must say how much it looked at, or a zero cannot be
        # told from "did not look".
        "DELEGATED_RUN_EVENTS",
        "DELEGATED_RUN_RECOGNIZED",
        "DELEGATED_RUN_TOOL_ERRORS",
        "DELEGATED_RUN_STATUS",
    }
    emitted = set(contract(proc.stdout))
    assert emitted == always, (
        f"contract drift: missing {sorted(always - emitted)}, "
        f"unexpected {sorted(emitted - always)}"
    )


# --------------------------------------------------------------------------- #
# A codex item whose own type is "error" (issue #892).
#
# #836 made errored tool CALLS visible. This is the next layer: when the Codex
# CLI cannot START its execution tool it announces that as an item whose own
# `type` is "error". Nothing ran, and the helper reported success over it.
# --------------------------------------------------------------------------- #

#: The real stream shape, from a Kyle session container on 2026-09-13 where
#: `codex-code-mode-host` is absent from the image.
CODEX_HOST_MISSING = (
    "Code Mode is unavailable because failed to spawn code-mode host "
    "/usr/local/bin/codex-code-mode-host: host executable was not found. "
    "Code mode will fail closed."
)


def _codex_error_item_stream(tmp_path: Path) -> Path:
    return write_jsonl(
        tmp_path / "codex-error-item.jsonl",
        [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_0", "type": "error", "message": CODEX_HOST_MISSING}},
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "agent_message",
                "text": "I couldn't run the read-only commands because the "
                        "execution tool failed to start."}},
            {"type": "turn.completed"},
        ],
    )


def test_a_codex_error_item_is_a_failure_without_expect_tools(tmp_path: Path) -> None:
    """The #892 red case, and it must NOT need `--expect-tools` to be caught.

    Against the pre-fix helper this exact payload reported
    `DELEGATED_RUN_STATUS: success` at exit 0. `--expect-tools` did reach
    `failure`, but for the wrong reason and with no diagnosis: the only signal
    was `no-tool-use`, which this helper's own documentation reads benignly as
    the model choosing not to act. The execution tool never started.
    """
    output = _codex_error_item_stream(tmp_path)
    proc = run(str(output), "0", "--lane", "codex")
    fields = contract(proc.stdout)
    assert fields["DELEGATED_RUN_STATUS"] == ["failure"], proc.stdout
    assert proc.returncode == 1, proc.stdout
    assert "error-payload" in fields["DELEGATED_RUN_SIGNAL"], proc.stdout


def test_the_error_item_message_reaches_the_operator(tmp_path: Path) -> None:
    """`that` is not enough; the run is unrecoverable without `why`.

    The difference between "the run did nothing" and "the run could not do
    anything" is the difference between re-running the prompt and installing a
    missing binary, and the message naming the binary was in the payload and
    was being discarded.
    """
    output = _codex_error_item_stream(tmp_path)
    proc = run(str(output), "0", "--lane", "codex")
    assert "codex-code-mode-host" in proc.stdout, proc.stdout
    assert "host executable was not found" in proc.stdout, proc.stdout


def test_the_item_error_check_is_scoped_and_does_not_become_recursive(
    tmp_path: Path,
) -> None:
    """The guard on the fix, not on the defect.

    `is_fatal`'s note records a litigated decision: scanning every nesting
    level made a DENIED TOOL CALL fatal, and a denied command is the
    /gemma:auto fence working as designed. The item-error check reads exactly
    `node["item"]["type"]`, so an "item" carried INSIDE a tool call's `part` is
    not reached.

    If someone later makes the check recursive to catch "one more case", this
    fails - which is the whole point of pinning it.
    """
    output = write_jsonl(
        tmp_path / "nested-item-error.jsonl",
        [
            {"type": "step_start"},
            {"type": "tool_use", "part": {
                "tool": "bash",
                "item": {"type": "error", "message": "denied by rule: git commit*"},
                "state": {"status": "error", "error": "permission denied"}}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma")
    fields = contract(proc.stdout)
    assert fields["DELEGATED_RUN_STATUS"] == ["success"], (
        "a tool call carrying a nested item.type=error is the fence working, "
        f"not a harness failure:\n{proc.stdout}"
    )
    assert proc.returncode == 0, proc.stdout


def test_the_denominator_says_how_much_was_examined(tmp_path: Path) -> None:
    """A verdict that cannot say what it looked at is the defect one level up.

    This helper's whole failure mode was reporting success over a run where
    nothing happened. `EVENTS`/`RECOGNIZED` make the input population part of
    the contract, so `TOOL_ERRORS: 0` can be told apart from "examined nothing".
    """
    output = _codex_error_item_stream(tmp_path)
    fields = contract(run(str(output), "0", "--lane", "codex").stdout)
    assert fields["DELEGATED_RUN_EVENTS"] == ["5"], fields
    assert fields["DELEGATED_RUN_RECOGNIZED"] == ["5"], fields

    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    empty_fields = contract(run(str(empty), "0", "--lane", "codex").stdout)
    assert empty_fields["DELEGATED_RUN_EVENTS"] == ["0"], empty_fields
    # The helper distinguishes an empty stream (`output-empty`) from one that
    # parsed but carried no recognizable event (`output-unrecognized`). Either
    # way a zero denominator must not read as clean, which is what the failure
    # status below pins.
    assert empty_fields["DELEGATED_RUN_SIGNAL"] == ["output-empty"], empty_fields
    assert empty_fields["DELEGATED_RUN_STATUS"] == ["failure"], empty_fields


def test_an_empty_stream_finishes_its_contract_instead_of_dying_mid_report(
    tmp_path: Path,
) -> None:
    """A SECOND instance of this issue's class, found while fixing the first.

    `TOOL_ERRORS=0` used to be initialized only inside the branch that runs the
    JSONL parser. An empty output file never reaches that branch, so the script
    died on `TOOL_ERRORS: unbound variable` PART WAY THROUGH the contract -
    after SIGNAL and DETAIL, before STATUS - and on `origin/main` that path
    exits 0.

    So a run that produced no stream whatsoever reported success, which is
    exactly "reports success when nothing ran" in a different code path from
    the one #892 is about. Measured on the pre-fix helper, not inferred.

    Both halves are load-bearing: a truncated contract is how the caller loses
    STATUS, and exit 0 is how it proceeds as though work happened.
    """
    empty = tmp_path / "nothing.jsonl"
    empty.write_text("", encoding="utf-8")
    proc = run(str(empty), "0", "--lane", "codex")
    fields = contract(proc.stdout)

    assert "DELEGATED_RUN_STATUS" in fields, (
        f"the contract stops before STATUS:\n{proc.stdout}\n{proc.stderr}"
    )
    assert fields["DELEGATED_RUN_STATUS"] == ["failure"], proc.stdout
    assert proc.returncode == 1, (
        f"a run that produced no stream must not exit 0:\n{proc.stdout}"
    )
    assert "unbound variable" not in proc.stderr, proc.stderr


# --------------------------------------------------------------------------- #
# The benign half, and it is why `item.type == "error"` is not enough.
#
# Found by the cross-model review and confirmed against codex's own
# `event_processor_with_jsonl_output.rs`: `ThreadItemDetails::Error` is emitted
# for ConfigWarning, DeprecationNotice and ModelRerouted, each of which returns
# `CodexStatus::Running` and continues. A genuinely critical error is a
# DIFFERENT shape - a top-level `{"type":"error"}` event, `ThreadEvent::Error` -
# which `is_fatal` already handled and this change does not touch.
#
# So the first cut of this fix would have failed every run carrying a
# deprecation notice. These pin the other side of the line.
# --------------------------------------------------------------------------- #


def _benign_notice_stream(tmp_path: Path, message: str, name: str) -> Path:
    """An error ITEM alongside work that actually happened."""
    return write_jsonl(
        tmp_path / name,
        [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_0", "type": "error", "message": message}},
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "command_execution",
                "command": "ls", "exit_code": 0}},
            {"type": "turn.completed"},
        ],
    )


@pytest.mark.parametrize(
    "message, name",
    [
        ("model rerouted: gpt-5.5-codex -> gpt-5.5", "reroute.jsonl"),
        ("`foo` is deprecated and will be removed in a future release",
         "deprecation.jsonl"),
        ("config warning: unknown key `experimental` ignored", "configwarn.jsonl"),
    ],
)
def test_a_benign_error_item_alongside_real_work_is_not_a_failure(
    tmp_path: Path, message: str, name: str
) -> None:
    """A notice in a run that DID its work is not a failed run."""
    output = _benign_notice_stream(tmp_path, message, name)
    proc = run(str(output), "0", "--lane", "codex")
    fields = contract(proc.stdout)
    assert fields["DELEGATED_RUN_STATUS"] == ["success"], proc.stdout
    assert proc.returncode == 0, proc.stdout


def test_a_benign_error_item_is_still_surfaced_to_the_operator(tmp_path: Path) -> None:
    """Not fatal is not the same as not worth saying.

    The point of reading the item at all is that the operator sees what the
    harness said about itself. Dropping the message on the benign path would
    reintroduce half the original complaint - `that` without `why` - on every
    run that continued.
    """
    output = _benign_notice_stream(
        tmp_path, "model rerouted: gpt-5.5-codex -> gpt-5.5", "surfaced.jsonl")
    proc = run(str(output), "0", "--lane", "codex")
    fields = contract(proc.stdout)
    assert "error-item" in fields["DELEGATED_RUN_SIGNAL"], proc.stdout
    assert "model rerouted" in proc.stdout, proc.stdout
    assert fields["DELEGATED_RUN_STATUS"] == ["success"], proc.stdout


def test_a_benign_error_item_does_not_fail_under_expect_tools_either(
    tmp_path: Path,
) -> None:
    """`error-item` is informational on BOTH paths.

    Grouping it with `no-tool-use` would have made it fatal whenever a caller
    passed --expect-tools, which is most callers that care.
    """
    output = _benign_notice_stream(
        tmp_path, "config warning: unknown key ignored", "expect.jsonl")
    proc = run(str(output), "0", "--lane", "codex", "--expect-tools")
    assert contract(proc.stdout)["DELEGATED_RUN_STATUS"] == ["success"], proc.stdout
    assert proc.returncode == 0, proc.stdout


def test_the_failure_is_the_conjunction_not_either_half(tmp_path: Path) -> None:
    """Neither half alone is a failure; together they are.

    This is the discriminator the whole fix rests on, so it is pinned directly
    rather than left implicit across the cases above:

      error item + work happened   -> success   (a notice)
      no error item + no tool use  -> success   (a question answered in prose)
      error item + no tool use     -> FAILURE   (the run could not act)
    """
    notice_only = _benign_notice_stream(
        tmp_path, "model rerouted: a -> b", "conj-notice.jsonl")
    assert contract(run(str(notice_only), "0", "--lane", "codex").stdout
                    )["DELEGATED_RUN_STATUS"] == ["success"]

    quiet_run = write_jsonl(
        tmp_path / "conj-quiet.jsonl",
        [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_0", "type": "agent_message",
                "text": "Yes, that file is generated by the build."}},
            {"type": "turn.completed"},
        ],
    )
    assert contract(run(str(quiet_run), "0", "--lane", "codex").stdout
                    )["DELEGATED_RUN_STATUS"] == ["success"]

    both = _codex_error_item_stream(tmp_path)
    both_fields = contract(run(str(both), "0", "--lane", "codex").stdout)
    assert both_fields["DELEGATED_RUN_STATUS"] == ["failure"], both_fields
    assert "error-payload" in both_fields["DELEGATED_RUN_SIGNAL"], both_fields
