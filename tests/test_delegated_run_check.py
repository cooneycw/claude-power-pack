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


def test_a_run_whose_only_tool_call_was_denied_reports_failure_with_its_reason(
    tmp_path: Path,
) -> None:
    """The #836 scenario, re-ruled by issue #1379.

    #836 ruled this 1-of-1 denial `success`: `is_fatal` stays non-recursive
    (a denied call is the /gemma:auto fence working as designed, and that
    verdict is UNCHANGED - this fixture still does not trip `is_fatal`).
    But #836 explicitly left open whether "the process ran cleanly" answers
    "did the work happen", and #1379's owner ruling settled it: it does not.
    Zero successful calls out of one attempted is the same "nothing
    happened" #1365 already flags at N>1, so this now reports `failure` -
    via `all-tools-failed`, never via `is_fatal` going recursive, which
    would be the reverted defect. The fix's whole requirement is that this
    is never a BARE failure: TOOL_ERRORS and TOOL_ATTEMPTS both read 1, so a
    caller can tell "declined its one forbidden action" from a multi-call
    wipeout, without this helper ever parsing the deny-rule text itself.
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
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "issue #1379: a 1-of-1 denial is zero accomplishment, same as a "
        f"multi-call wipeout:\n{proc.stdout}"
    )
    assert found["DELEGATED_RUN_SIGNAL"] == ["all-tools-failed"], (
        f"the failure must say why, not arrive bare:\n{proc.stdout}"
    )
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], "the refusal must be reported somewhere"
    assert found["DELEGATED_RUN_TOOL_ATTEMPTS"] == ["1"], "and so must the denominator beside it"


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


# ---------------------------------------------------------------------------
# Issue #1054: the counter above matched ONE harness's shape. `state.status ==
# "error"` is how OpenCode/gemma writes down a failed tool call; the Codex CLI
# emits no `state` at all and the Qwen CLI does not either, so on those two
# lanes `TOOL_ERRORS` was structurally incapable of being non-zero - `0` meant
# "cannot see" and reads identically to the "checked, none" the line was added
# to promise.
#
# Every codex-lane assertion in this file expected `0`, and both non-zero
# assertions (`test_a_run_whose_tool_call_was_denied_reports_success_and_says_so`
# and `test_the_tool_error_counter_can_fire`) are `--lane gemma`. So the counter
# had a negative control for the shape it could see and none for either shape it
# could not, which is why this survived #836 and #892. The pins below are those
# missing controls, one per lane, plus the discrimination controls that keep a
# recognizer which counts EVERYTHING from satisfying them.
# ---------------------------------------------------------------------------


def test_the_tool_error_counter_can_fire_on_the_codex_lane() -> None:
    """The missing committed case, on a REAL capture (issue #1054), re-ruled
    by issue #1379.

    `codex-command-failed.jsonl` is a genuine `codex exec --json` run whose one
    command exited 3. Measured against the helper as it stood before #1365:
    `DELEGATED_RUN_TOOL_ERRORS: 0`, `DELEGATED_RUN_STATUS: success`, and the
    prose "no tool call reported an error" - an affirmative claim about a
    command that had just failed, not a silence. #1365 fixed TOOL_ERRORS but
    left STATUS at `success` for this exact fixture, because it is a 1-of-1
    run and #1365 scoped `all-tools-failed` to N>1.

    RED, measured directly against this fixture at main `9661967` (#1365
    merged, #1379 not yet):
        DELEGATED_RUN_EXIT: 0
        DELEGATED_RUN_TOOL_ERRORS: 1
        DELEGATED_RUN_STATUS: success

    #1379's owner ruling: a failed command IS a zero-accomplishment run when
    it is the only thing attempted, the same fact #1365 already reports for
    N>1 regardless of cause (denial or genuine failure, undiscriminated).
    `is_fatal` is not what flags it - that stays non-recursive, unchanged,
    the #836 guard - `all-tools-failed` is, and it must say so rather than
    leaving STATUS bare.
    """
    path = FIXTURES / "codex-command-failed.jsonl"
    assert path.exists(), f"missing fixture {path}"

    proc = run(str(path), "0", "--lane", "codex", "--expect-tools")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], proc.stdout
    assert found["DELEGATED_RUN_TOOL_ATTEMPTS"] == ["1"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "issue #1379: a single failed command with nothing else attempted is "
        f"zero accomplishment:\n{proc.stdout}"
    )
    assert found["DELEGATED_RUN_SIGNAL"] == ["all-tools-failed"], (
        f"never a bare STATUS: failure:\n{proc.stdout}"
    )


def test_a_real_codex_success_capture_still_counts_no_tool_errors() -> None:
    """The discrimination control, and it is what makes the pin above mean something.

    `codex-complete.jsonl` is a real run that did real work: eight
    `command_execution` items, every one `exit_code: 0, status: "completed"`,
    plus `item.started` events carrying `exit_code: null, status: "in_progress"`
    for the same ids. A recognizer that counted every codex item, or treated a
    null exit code as non-zero, would satisfy the test above and report a
    fabricated number on every successful run - the same defect pointing the
    other way.

    `EVENTS` is asserted too, so this zero is "looked at 20 events and found
    none" rather than "parsed nothing", which is the distinction the helper's
    own denominator exists to draw.
    """
    path = FIXTURES / "codex-complete.jsonl"
    assert path.exists(), f"missing fixture {path}"

    found = contract(run(str(path), "0", "--lane", "codex", "--expect-tools").stdout)
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["0"]
    assert int(found["DELEGATED_RUN_EVENTS"][0]) > 0, "a zero over nothing is not a zero"


def test_a_codex_item_still_running_is_not_counted(tmp_path: Path) -> None:
    """`item.started` is a call in flight, not a failed one.

    Real values, lifted from `codex-complete.jsonl`: an in-progress command
    carries `exit_code: null` and `status: "in_progress"`. `None` is not a
    non-zero integer and `in_progress` is not `failed`, and this pins that
    neither is read as one - a recognizer that counted any item with an
    `exit_code` key would fire on every command codex has ever started.
    """
    output = write_jsonl(
        tmp_path / "in-flight.jsonl",
        [
            {"type": "item.started", "item": {"id": "item_1", "type": "command_execution",
                                              "command": "make test", "aggregated_output": "",
                                              "exit_code": None, "status": "in_progress"}},
            {"type": "turn.completed"},
        ],
    )
    found = contract(run(str(output), "0", "--lane", "codex").stdout)
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["0"]
    assert "no-tool-use" not in found.get("DELEGATED_RUN_SIGNAL", []), (
        "the event must have been RECOGNIZED as a tool call for its zero to mean anything"
    )


def test_a_failed_codex_item_is_counted_once_across_its_lifecycle(tmp_path: Path) -> None:
    """One failed call must be one, however many events carry it.

    The Codex CLI reports a single call across several events sharing an
    `item.id`; the binary emits `item.started`, `item.updated` and
    `item.completed`. Only `completed` carries a terminal status in the
    captures on disk, so this stream is DEFENSIVE rather than observed - it
    asserts the dedupe holds, and claims nothing about which events codex
    actually populates.

    Inflation is this defect's mirror image. A count stuck at zero and a count
    that multiplies are equally unusable to the caller the line exists for, and
    only one of them looks wrong.
    """
    output = write_jsonl(
        tmp_path / "one-call-three-events.jsonl",
        [
            {"type": "item.started", "item": {"id": "item_7", "type": "command_execution",
                                              "exit_code": None, "status": "in_progress"}},
            {"type": "item.updated", "item": {"id": "item_7", "type": "command_execution",
                                              "exit_code": 2, "status": "failed"}},
            {"type": "item.completed", "item": {"id": "item_7", "type": "command_execution",
                                                "exit_code": 2, "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "codex").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["1"]


def test_a_non_tool_codex_item_is_not_counted(tmp_path: Path) -> None:
    """The codex recognizer's ownership boundary, the sibling of the #836 pin.

    `agent_message`, `reasoning` and `todo_list` items are the model talking,
    not tool calls, so a `status` on one of them is not a tool error however it
    reads. An item whose own type is `"error"` belongs to `is_fatal_item`,
    which reaches a verdict this counter must never touch.

    TWO LAYERS DECLINE IT, and which one fires is worth stating because the
    first version of this test did not know. Measured by deleting the
    item-level `TOOL_TYPES` check and re-running: this case still passed, and
    the second case below is the one that went red. The event-level gate at the
    call site (`any(value in TOOL_TYPES for value in tool_types_in(obj))`)
    declines a lone `agent_message` event before the recognizer is ever
    entered, so the first stream pins the OUTER gate, not the inner scope.

    The second stream is therefore SYNTHETIC and says so: no codex version
    emits an item carrying a `name` of `command_execution`. It exists because
    every observed non-tool shape is stopped by the outer gate, which would
    leave the inner scope with no input that can make it report the other
    verdict - a check with no red case, inside a change about exactly that.
    """
    outer_gate = write_jsonl(
        tmp_path / "chatter.jsonl",
        [
            {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message",
                                                "text": "that did not work", "status": "failed"}},
            {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
                                                "exit_code": 1, "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    assert contract(run(str(outer_gate), "0", "--lane", "codex").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["1"], "model chatter carrying a failing status is not a tool error"

    inner_scope = write_jsonl(
        tmp_path / "chatter-past-the-gate.jsonl",
        [
            {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message",
                                                "name": "command_execution",
                                                "text": "that did not work", "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    found = contract(run(str(inner_scope), "0", "--lane", "codex").stdout)
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["0"], (
        "the item's OWN type decides, not a tool name found anywhere in the event"
    )
    assert "no-tool-use" not in found.get("DELEGATED_RUN_SIGNAL", []), (
        "this stream must reach the recognizer, or it pins the outer gate again"
    )


def test_a_boolean_exit_code_is_not_a_non_zero_exit_status(tmp_path: Path) -> None:
    """`isinstance(True, int)` is True in Python, and this is the guard for it.

    A payload carrying `"exit_code": true` has not told us a command exited
    non-zero. Counting it would be fabricated specificity - a number that looks
    like a measurement and was never one - which is the failure mode this whole
    cluster of issues is about, so the exclusion is pinned rather than trusted
    to a comment. The stream carries a genuinely failed call so the `1`
    distinguishes "declined the bool" from "counted neither".
    """
    output = write_jsonl(
        tmp_path / "bool-exit.jsonl",
        [
            {"type": "item.completed", "item": {"id": "item_0", "type": "command_execution",
                                                "exit_code": True, "status": "completed"}},
            {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
                                                "exit_code": 4, "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "codex").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["1"]


def test_each_arm_of_the_codex_failure_predicate_fires_alone(tmp_path: Path) -> None:
    """A disjunction tested only through payloads carrying both arms is untested.

    The real capture reports `status: "failed"` AND `exit_code: 3` together, so
    every pin above would still pass if one arm were deleted. These two streams
    separate them: a failed status with no exit code at all (a `file_change` or
    `mcp_tool_call` has none), and a non-zero exit code under a status that
    does not say `failed`.

    Raised by the counter-model review's red cases, which is the stage doing
    its job: the gap was in the CONTROLS, not the code.
    """
    status_only = write_jsonl(
        tmp_path / "status-only.jsonl",
        [
            {"type": "item.completed", "item": {"id": "item_1", "type": "file_change",
                                                "changes": [{"path": "a.py", "kind": "update"}],
                                                "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    assert contract(run(str(status_only), "0", "--lane", "codex").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["1"], "a failing status with no exit_code must still count"

    exit_only = write_jsonl(
        tmp_path / "exit-only.jsonl",
        [
            {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
                                                "exit_code": 3, "status": "completed"}},
            {"type": "turn.completed"},
        ],
    )
    assert contract(run(str(exit_only), "0", "--lane", "codex").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["1"], "a non-zero exit_code must count whatever the status says"


def test_a_declined_codex_item_is_counted(tmp_path: Path) -> None:
    """DEFENSIVE, and the provenance is the point (issue #1054 review);
    re-ruled by issue #1379.

    A counter-model reviewer reported that Codex emits `status: "declined"` for
    a refused command, citing upstream Rust. Measuring the shipped binary
    (codex-cli 0.155.1) placed that string in the OTHER protocol: `declined`
    sits beside the camelCase `inProgress` status matchers and beside none of
    the 47 snake_case `in_progress` ones, and the exec JSONL this helper reads
    is snake_case throughout. So this shape is NOT claimed to occur in a
    `codex exec --json` stream, and no fixture asserts that it does.

    It is matched because the risks are asymmetric: missing it would be the
    false zero this issue is about, while matching it spuriously requires a
    payload that literally says `"status": "declined"`, which has one meaning.

    STATUS itself is no longer `success` here (issue #1379): a refusal is
    still the fence working as designed - `is_fatal` does not fire, and that
    is unchanged - but one declined command with nothing else attempted is
    still zero accomplishment, reported via `all-tools-failed`, not bare.
    """
    output = write_jsonl(
        tmp_path / "declined.jsonl",
        [
            {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
                                                "command": "rm -rf /", "exit_code": None,
                                                "status": "declined"}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    found = contract(proc.stdout)
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"]
    assert found["DELEGATED_RUN_TOOL_ATTEMPTS"] == ["1"]
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "a refusal is the fence working, but it is still zero accomplishment "
        "(issue #1379)"
    )
    assert found["DELEGATED_RUN_SIGNAL"] == ["all-tools-failed"]


def test_the_codex_dedupe_does_not_collapse_distinct_calls(tmp_path: Path) -> None:
    """The control for the dedupe, without which it could swallow everything.

    `test_a_failed_codex_item_is_counted_once_across_its_lifecycle` asserts
    `1` from three events. A recognizer that counted only the FIRST failure in
    the whole stream would satisfy it exactly. Two failed calls with DIFFERENT
    ids must total 2, which is the input that tells "deduped by id" apart from
    "stopped counting".
    """
    output = write_jsonl(
        tmp_path / "two-distinct.jsonl",
        [
            {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution",
                                                "exit_code": 2, "status": "failed"}},
            {"type": "item.completed", "item": {"id": "item_2", "type": "command_execution",
                                                "exit_code": 1, "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "codex").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["2"]


def test_the_tool_error_counter_can_fire_on_the_qwen_lane(tmp_path: Path) -> None:
    """The third lane, which the issue flagged and did not measure (#1054).

    Measured here before the fix: `TOOL_ERRORS: 0`, same as codex. The shape is
    read out of the installed CLI's own source rather than guessed -
    `@qwen-code/qwen-code`'s `emitToolResult` emits a `user` event whose
    `message.content[]` holds a `tool_result` block with
    `is_error = Boolean(response.error) || Boolean(responsePartsError)`, and
    pushes a `permissionDenials` entry when `errorType` is `EXECUTION_DENIED`.

    `is_fatal` reads `is_error` only at an event's TOP level - deliberately, so
    a denied call is not a failed run - and this one is two levels down, so
    nothing saw it; that is unchanged. Provenance differs from the codex pin
    above and is stated rather than implied: source plus a synthetic stream,
    not a captured run.

    STATUS is no longer `success` (issue #1379): `is_fatal` still correctly
    does not fire, but one denied call with nothing else attempted is zero
    accomplishment, reported via `all-tools-failed`.
    """
    output = write_jsonl(
        tmp_path / "qwen-denied.jsonl",
        [
            {"type": "system", "subtype": "init", "session_id": "s"},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "run_shell_command",
                 "input": {"command": "make lint"}}]}},
            {"type": "user", "session_id": "s", "parent_tool_use_id": None,
             "message": {"role": "user", "content": [
                 {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
                  "content": "Tool execution denied by policy"}]}},
            {"type": "result", "subtype": "success", "is_error": False,
             "num_turns": 5, "result": "Done."},
        ],
    )
    proc = run(str(output), "0", "--lane", "qwen", "--expect-tools")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], proc.stdout
    assert found["DELEGATED_RUN_TOOL_ATTEMPTS"] == ["1"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "the fence working does not stop this being zero accomplishment "
        "(issue #1379)"
    )
    assert found["DELEGATED_RUN_SIGNAL"] == ["all-tools-failed"], proc.stdout


def test_a_successful_qwen_tool_result_is_not_counted(tmp_path: Path) -> None:
    """The qwen discrimination control.

    Every tool call in the stream above carries a `tool_result` block; only the
    failed one carries `is_error: true`. Without this, a recognizer that
    counted `tool_result` blocks outright would pass the pin above and report a
    tool error for every successful call qwen ever makes.
    """
    output = write_jsonl(
        tmp_path / "qwen-clean.jsonl",
        [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "read_file"}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "is_error": False,
                 "content": "file contents"}]}},
            {"type": "result", "subtype": "success", "is_error": False,
             "num_turns": 4, "result": "Done."},
        ],
    )
    found = contract(run(str(output), "0", "--lane", "qwen", "--expect-tools").stdout)
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["0"]
    assert "no-tool-use" not in found.get("DELEGATED_RUN_SIGNAL", []), (
        "the tool_result must have been recognized for its zero to mean anything"
    )


def test_an_is_error_outside_a_tool_result_block_is_not_counted(tmp_path: Path) -> None:
    """The qwen recognizer's type scope, the sibling of the codex one.

    `is_error` is not the whole signal - the block must be a `tool_result`.
    A `text` block carrying `is_error: true` is not a tool call, and counting
    it would let a neighbour inflate the number. The stream carries a genuine
    failed tool_result so the `1` proves the recognizer ran and declined the
    other block, rather than the event having been skipped entirely.
    """
    output = write_jsonl(
        tmp_path / "qwen-mixed.jsonl",
        [
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "text", "text": "something went wrong", "is_error": True},
                {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
                 "content": "denied"}]}},
            {"type": "result", "subtype": "success", "is_error": False,
             "num_turns": 3, "result": "Done."},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "qwen").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["1"]


def test_the_qwen_recognizer_is_structural_not_recursive(tmp_path: Path) -> None:
    """A `tool_result` outside `message.content[]` is not this counter's business.

    The recognizer reads exactly `node["message"]["content"][]`, so a
    `tool_result` sitting at an event's top level contributes nothing to the
    count. That is deliberate and it is what keeps this change away from
    `is_fatal`, whose top-level-only read of `is_error` is the reason a denied
    call is not a failed run - a recursive recognizer here would start counting
    the very nodes that scoping exists to separate.

    Only `TOOL_ERRORS` is asserted. This stream also trips the PRE-EXISTING
    `error-payload` signal, because a top-level `is_error: true` genuinely is a
    harness-level failure; that behaviour is `is_fatal`'s and is not what this
    pin is about.
    """
    output = write_jsonl(
        tmp_path / "qwen-toplevel.jsonl",
        [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
             "content": "denied"},
            {"type": "result", "subtype": "success", "is_error": False,
             "num_turns": 3, "result": "Done."},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "qwen").stdout)[
        "DELEGATED_RUN_TOOL_ERRORS"
    ] == ["0"]


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
        # Lines that did not parse (#1265): without it the denominator dropped
        # exactly what the helper could not read.
        "DELEGATED_RUN_UNPARSED",
        "DELEGATED_RUN_TOOL_ERRORS",
        # The attempt denominator beside it (#1379): without it, a caller
        # reading TOOL_ERRORS alone cannot tell "1 of 1 failed" from "1 of 5
        # failed" - exactly the distinction the all-tools-failed verdict now
        # needs a reader to be able to make for itself.
        "DELEGATED_RUN_TOOL_ATTEMPTS",
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

    STATUS itself flipped to `failure` under issue #1379 (this is a 1-of-1
    all-tools-failed run like any other single denied call), so the pin
    moved from STATUS to SIGNAL: it now asserts the failure came from
    `all-tools-failed` alone, counting the tool call once at the top level -
    never from `is_fatal`/`is_fatal_item` reaching the nested `item.type:
    error` and adding a signal like `error-payload`. A regression that made
    either check recursive would add a second signal here, which this still
    catches exactly as before.
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
    assert fields["DELEGATED_RUN_STATUS"] == ["failure"], (
        "a 1-of-1 all-tools-failed run (issue #1379), not a fence-working "
        f"success:\n{proc.stdout}"
    )
    assert fields["DELEGATED_RUN_SIGNAL"] == ["all-tools-failed"], (
        "the nested item.type=error must still be unreached by is_fatal/"
        f"is_fatal_item - any other signal means it recursed:\n{proc.stdout}"
    )
    assert proc.returncode == 1, proc.stdout


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


# ---------------------------------------------------------------------------
# Issue #1265: blind spots that each reported a confident answer about less
# than the whole payload.
# ---------------------------------------------------------------------------


def _nested(depth: int, leaf: dict) -> dict:
    """`leaf` wrapped in `depth` levels of plain dicts."""
    node = leaf
    for level in range(depth):
        node = {f"wrap{level}": node}
    return node


@pytest.mark.parametrize("depth", [8, 50])
def test_a_failed_tool_call_is_counted_at_any_depth(tmp_path: Path, depth: int) -> None:
    """THE #1265 DEPTH REGRESSION: the walk stopped at depth 6 and said 0.

    Red on b935d64 at both depths. 50 is well past where the old recursion gave
    up, so the fix is not tuned to one depth just beyond the cap.
    """
    output = write_jsonl(
        tmp_path / f"deep-{depth}.jsonl",
        [
            {"type": "tool_use", "part": _nested(depth, {"tool": "bash", "state": {"status": "error"}})},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "gemma").stdout)["DELEGATED_RUN_TOOL_ERRORS"] == ["1"]


def test_a_deep_payload_is_walked_iteratively(tmp_path: Path) -> None:
    """800 levels: past anything a recursive walk with a small cap would reach,
    and parseable by json.loads on every supported interpreter (its own limit
    is the next test's subject). Written as a raw string, because json.dumps is
    itself recursive and would fail building the input on some versions."""
    depth = 800
    call = '{"tool": "bash", "state": {"status": "error"}}'
    line = '{"type": "tool_use", "part": ' + '{"w": ' * depth + call + "}" * depth + "}"
    path = tmp_path / "deep-800.jsonl"
    path.write_text(line + '\n{"type": "step_finish", "part": {"reason": "stop"}}\n', encoding="utf-8")
    proc = run(str(path), "0", "--lane", "gemma")
    assert contract(proc.stdout)["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], proc.stdout + proc.stderr


def test_a_line_too_deep_to_parse_is_unparsed_not_a_crash(tmp_path: Path) -> None:
    """json.loads is bounded by the interpreter's recursion limit (counter-model
    review, #1265). A line past it is UNREADABLE: counted in UNPARSED, and the
    rest of the stream is still read - never an uncaught RecursionError that
    turns the whole payload into `output-unreadable`."""
    depth = 100_000
    line = '{"a": ' * depth + "1" + "}" * depth
    path = tmp_path / "too-deep.jsonl"
    path.write_text(
        line + "\n"
        + '{"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error"}}}\n'
        + '{"type": "step_finish", "part": {"reason": "stop"}}\n',
        encoding="utf-8",
    )
    found = contract(run(str(path), "0", "--lane", "gemma").stdout)
    assert found["DELEGATED_RUN_UNPARSED"] == ["1"], found
    assert found["DELEGATED_RUN_EVENTS"] == ["2"], found
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], found
    # Unread is not harmless (counter-model review, pass 2): the skipped line
    # could have been a failure event, so the run FAILS, and says why.
    assert "line-too-deep" in found["DELEGATED_RUN_SIGNAL"], found
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], found


def test_a_fatal_event_too_deep_to_read_cannot_become_a_success(tmp_path: Path) -> None:
    """The reviewer's exact case: a top-level error event carrying a field nested
    past the parse limit, then a clean tool call and a terminal event. Before,
    the error event was skipped and the run read as success under --expect-tools."""
    deep = '{"a": ' * 100_000 + "1" + "}" * 100_000
    path = tmp_path / "fatal-too-deep.jsonl"
    path.write_text(
        '{"type": "error", "error": "fatal", "payload": ' + deep + "}\n"
        + '{"type": "tool_use", "part": {"tool": "bash", "state": {"status": "completed"}}}\n'
        + '{"type": "step_finish", "part": {"reason": "stop"}}\n',
        encoding="utf-8",
    )
    found = contract(run(str(path), "0", "--lane", "gemma", "--expect-tools").stdout)
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], found


def test_a_clean_verdict_over_unparsed_lines_says_so(tmp_path: Path) -> None:
    """A success computed over part of the payload is qualified in the prose."""
    path = tmp_path / "banner.jsonl"
    path.write_text(
        "a harness banner\n"
        '{"type": "tool_use", "part": {"tool": "bash", "state": {"status": "completed"}}}\n'
        '{"type": "step_finish", "part": {"reason": "stop"}}\n',
        encoding="utf-8",
    )
    proc = run(str(path), "0", "--lane", "gemma")
    assert contract(proc.stdout)["DELEGATED_RUN_STATUS"] == ["success"]
    assert "1 line(s) were not JSON and were not examined" in proc.stdout, proc.stdout


@pytest.mark.parametrize("depth", [2, 8, 50])
def test_an_error_state_inside_a_successful_call_s_data_is_not_counted(
    tmp_path: Path, depth: int
) -> None:
    """Ownership (counter-model review, #1265): the other half of the depth fix.

    A successful call whose returned data contains an error-shaped object at
    any depth is ONE successful call. Only a node that is itself a tool call
    (carries its own `tool`) owns the state that is counted.
    """
    output = write_jsonl(
        tmp_path / f"owned-{depth}.jsonl",
        [
            {"type": "tool_use", "part": {"tool": "bash", "state": {
                "status": "completed",
                "output": _nested(depth, {"state": {"status": "error"}}),
            }}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "gemma").stdout)["DELEGATED_RUN_TOOL_ERRORS"] == ["0"]


def test_unparsed_lines_are_counted_not_dropped(tmp_path: Path) -> None:
    """THE #1265 DENOMINATOR REGRESSION: non-JSON lines vanished from the counts.

    `EVENTS` keeps its meaning (JSON lines parsed); the lines it could not read
    are a separate, additive count, so `RECOGNIZED == EVENTS` can no longer hide
    them. Red on b935d64 (no UNPARSED line).
    """
    path = tmp_path / "mixed.jsonl"
    path.write_text(
        '{"type": "tool_use", "part": {"tool": "bash", "state": {"status": "completed"}}}\n'
        "some stderr banner\n"
        "\n"
        "another unparseable line\n"
        '{"type": "step_finish", "part": {"reason": "stop"}}\n',
        encoding="utf-8",
    )
    found = contract(run(str(path), "0", "--lane", "gemma").stdout)
    assert found["DELEGATED_RUN_EVENTS"] == ["2"]
    assert found["DELEGATED_RUN_UNPARSED"] == ["2"], "blank lines are not counted; two non-JSON lines are"


def test_help_shows_the_whole_header() -> None:
    """THE #1265 HELP REGRESSION: `sed -n '2,90p'` cut off Signals and Exit codes."""
    proc = run("--help")
    assert proc.returncode == 0
    assert "Signals:" in proc.stdout and "Exit codes:" in proc.stdout, proc.stdout


def test_the_reported_error_text_is_the_first_line_s(tmp_path: Path) -> None:
    """Order check (orchestrator, #1265): DETAIL is the FIRST error's text, and
    every failed call is counted, with a failed call nested between the two
    error items. The depth (4) is inside the old cap on purpose, so the pre-fix
    recursive walk and the iterative one must give the SAME answer here."""
    output = write_jsonl(
        tmp_path / "order.jsonl",
        [
            {"type": "item.completed", "item": {"id": "e1", "type": "error", "message": "first failure"}},
            {"type": "item.completed", "item": {"id": "c1", "type": "command_execution",
                                                "command": "false", "exit_code": 1, "status": "failed"}},
            {"type": "tool_use", "part": _nested(4, {"tool": "bash", "state": {"status": "error"}})},
            {"type": "item.completed", "item": {"id": "e2", "type": "error", "message": "second failure"}},
            {"type": "turn.completed"},
        ],
    )
    found = contract(run(str(output), "0", "--lane", "codex").stdout)
    assert found.get("DELEGATED_RUN_DETAIL") == ["first failure"], found
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["2"], found


def test_a_real_codex_collab_capture_counts_as_tool_activity() -> None:
    """Item 4 of #1265, settled by a REAL capture rather than a guessed spelling.

    codex-cli 0.158.0 with `multi_agent` enabled emits `item.type:
    "collab_tool_call"` (tool `wait`) - captured 2026-09-28 into
    fixtures/delegated_runs/codex-collab-capture.jsonl. A run whose only tool
    activity is collaboration is not a run that "used no tools", so under
    --expect-tools it must not fail as tool-less. Red on b935d64.
    """
    path = FIXTURES / "codex-collab-capture.jsonl"
    assert '"collab_tool_call"' in path.read_text(encoding="utf-8"), "precondition: the capture"
    proc = run(str(path), "0", "--lane", "codex", "--expect-tools")
    found = contract(proc.stdout)
    assert found["DELEGATED_RUN_STATUS"] == ["success"], proc.stdout
    assert "no-tool-use" not in found.get("DELEGATED_RUN_SIGNAL", []), found


def test_tool_activity_nested_deep_in_a_wrapper_is_seen(tmp_path: Path) -> None:
    """tool_types_in's half of the depth fix (counter-model red case, #1265):
    a tool type 8 levels inside a non-tool wrapper event is still tool activity,
    so --expect-tools does not fail the run as tool-less."""
    output = write_jsonl(
        tmp_path / "wrapped.jsonl",
        [
            {"type": "wrapper", "payload": _nested(8, {"type": "tool_use", "tool": "bash"})},
            {"type": "turn.completed"},
        ],
    )
    found = contract(run(str(output), "0", "--lane", "codex", "--expect-tools").stdout)
    assert "no-tool-use" not in found.get("DELEGATED_RUN_SIGNAL", []), found


def test_a_tool_shaped_error_inside_a_successful_call_s_output_is_not_counted(tmp_path: Path) -> None:
    """Ownership, the sharper form (counter-model red case, #1265): the returned
    data is itself tool-SHAPED - it carries a `tool` and an error state - but it
    is data a successful call returned, so the walk never descends to it."""
    output = write_jsonl(
        tmp_path / "tool-shaped-output.jsonl",
        [
            {"type": "tool_use", "part": {"tool": "bash", "state": {
                "status": "completed",
                "output": {"tool": "bash", "state": {"status": "error"}},
            }}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    assert contract(run(str(output), "0", "--lane", "gemma").stdout)["DELEGATED_RUN_TOOL_ERRORS"] == ["0"]


# ---------------------------------------------------------------------------
# Issue #1365: TOOL_ERRORS was purely informational - however many tool calls
# failed, STATUS stayed `success` as long as the CLI itself did not crash. A
# real kyle coding-candidate run (2026-10-01) tried three shell commands, all
# three failed with the SAME harness-level cause (no sandbox helper in the
# container, "Failed to create unified exec process"), and the helper still
# reported `STATUS: success` - the worker caught it only by diffing the
# worktree by hand. The fix is deliberately narrow: #836 already settled that
# a SINGLE denied/failed call must not fail the run (the fence working as
# designed), so this only fires when MORE THAN ONE call was attempted and
# EVERY one of them failed.
# ---------------------------------------------------------------------------


def test_a_run_where_every_attempted_tool_call_failed_is_not_a_success(tmp_path: Path) -> None:
    """The committed red case: issue #1365's own incident shape.

    Reconstructed from the issue's quoted item (`item_3`, verbatim
    `aggregated_output`/`exit_code`/`status`) repeated across three ids, since
    no raw capture file was attached to the issue - stated here rather than
    implied, the same provenance distinction `test_a_declined_codex_item_is_
    counted` draws for its own synthetic stream. Measured against the
    PRE-FIX helper (`git stash`, re-run): `DELEGATED_RUN_TOOL_ERRORS: 3`,
    `DELEGATED_RUN_STATUS: success`, exit 0 - the exact defect this pins
    against.
    """
    output = write_jsonl(
        tmp_path / "all-three-failed.jsonl",
        [
            {"type": "thread.started", "thread_id": "redacted"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "command_execution", "command": "/usr/bin/sh -c pwd",
                "aggregated_output": "Failed to create unified exec process: No such file or directory (os error 2)",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_2", "type": "command_execution", "command": "/usr/bin/sh -c ls",
                "aggregated_output": "Failed to create unified exec process: No such file or directory (os error 2)",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_3", "type": "command_execution", "command": "/usr/bin/sh -c git status",
                "aggregated_output": "Failed to create unified exec process: No such file or directory (os error 2)",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_4", "type": "agent_message",
                "text": "I was unable to run any commands in this environment."}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["3"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "zero of three attempted tool calls succeeded - the delegated model "
        f"could not have done anything:\n{proc.stdout}"
    )
    assert "all-tools-failed" in found["DELEGATED_RUN_SIGNAL"], proc.stdout


def test_one_of_three_failing_is_still_the_836_case(tmp_path: Path) -> None:
    """The required control: a real partial failure must not regress (#836).

    Exactly the shape the issue's own Proposed section describes as the
    control - one of three calls denied/failed, the other two succeed - and
    it is `#836`'s case restated with a wider denominator: `TOOL_ERRORS` is
    non-zero, SOME calls succeeded, so the run is not "every attempted call
    failed" and must stay `success`.
    """
    output = write_jsonl(
        tmp_path / "one-of-three-failed.jsonl",
        [
            {"type": "thread.started", "thread_id": "redacted"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "command_execution", "command": "make lint",
                "exit_code": 0, "status": "completed"}},
            {"type": "item.completed", "item": {
                "id": "item_2", "type": "command_execution", "command": "git commit -m x",
                "aggregated_output": "permission denied by rule: git commit*",
                "exit_code": 1, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_3", "type": "command_execution", "command": "make test",
                "exit_code": 0, "status": "completed"}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    found = contract(proc.stdout)
    assert proc.returncode == 0, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["success"], (
        "two of three calls succeeded - widening this to failure would be "
        f"the reverted #836 defect, not the #1365 fix:\n{proc.stdout}"
    )
    assert "all-tools-failed" not in found.get("DELEGATED_RUN_SIGNAL", []), proc.stdout


def test_a_successful_non_command_item_keeps_an_all_failed_command_set_from_tripping(
    tmp_path: Path,
) -> None:
    """Orchestrator review condition 1: `attempted` must see every tool-type
    item, not only `command_execution`.

    A patch (`file_change`) applies cleanly while every shell command the same
    run tried fails - real work happened, so this must stay `success`. A
    recognizer that only counted `command_execution` as an "attempt" would
    see 0 attempts and 2 errors, trip no all-failed check by coincidence, and
    give the right answer for the wrong reason on a stream shaped slightly
    differently; this stream's `file_change` succeeding is what actually
    exercises the breadth of the `TOOL_TYPES` scope shared with the error
    counters. A lane whose recognizer cannot see some OTHER item type (none
    are known missing from `TOOL_TYPES` today - see the header's `#1265`
    note on `collab_tool_call`) would be invisible to both counters alike,
    which is the existing scope, not a gap this change opens.
    """
    output = write_jsonl(
        tmp_path / "patch-ok-commands-failed.jsonl",
        [
            {"type": "thread.started", "thread_id": "redacted"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "file_change",
                "changes": [{"path": "a.py", "kind": "update"}], "status": "completed"}},
            {"type": "item.completed", "item": {
                "id": "item_2", "type": "command_execution", "command": "make lint",
                "aggregated_output": "Failed to create unified exec process: No such file or directory (os error 2)",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_3", "type": "command_execution", "command": "make test",
                "aggregated_output": "Failed to create unified exec process: No such file or directory (os error 2)",
                "exit_code": -1, "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    found = contract(proc.stdout)
    assert proc.returncode == 0, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["2"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["success"], (
        "the patch landed - this is not a run that did zero work:\n"
        f"{proc.stdout}"
    )
    assert "all-tools-failed" not in found.get("DELEGATED_RUN_SIGNAL", []), proc.stdout


def test_the_all_failed_signal_now_covers_a_single_attempt_too(tmp_path: Path) -> None:
    """Pins the REMOVAL of the >1 threshold, independent of any single fixture
    (issue #1379, reversing this test's own prior pin).

    #836/#892/#1054's four pinned single-attempt cases (denied-docker,
    codex-command-failed.jsonl, declined.jsonl, qwen-denied) were never "a
    denial among successes" - each is a literal 1-of-1 run, verified by
    reading them: one tool event, no others. The old >1 requirement was not
    protecting #836's "the other calls succeed" framing specifically; it was
    what kept every existing single-attempt-failed pin green as a side
    effect, while still catching #1365's multi-attempt incident. #1379's
    owner ruling settled that this was test-compatibility scoping, not a
    principled distinction: "every tool it tried came back failed" is never
    a legitimate outcome whatever N is, and #836's own `is_fatal` (process
    health, untouched) already covers the model-behaved-correctly half -
    this signal answers the separate, previously-unanswered "did the work
    happen" question #836 explicitly left open. This stream is the general
    form - gemma lane, one denied call, nothing else - to pin the new
    behavior without depending on any one fixture's continued existence.
    """
    output = write_jsonl(
        tmp_path / "single-attempt-failed.jsonl",
        [
            {"type": "step_start"},
            {"type": "tool_use", "part": {"tool": "bash", "state": {
                "status": "error", "error": "permission denied by rule: git commit*"}}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["1"], proc.stdout
    assert found["DELEGATED_RUN_TOOL_ATTEMPTS"] == ["1"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "a single attempted call that failed is still zero accomplishment "
        f"(issue #1379) - the run tried one thing and it did not work:\n{proc.stdout}"
    )
    assert found["DELEGATED_RUN_SIGNAL"] == ["all-tools-failed"], (
        "STATUS: failure must never be bare - the reason signal names why, "
        f"same as the >1 case:\n{proc.stdout}"
    )


def test_an_unresolved_codex_item_does_not_mask_an_all_failed_run(tmp_path: Path) -> None:
    """Counter-model review finding (codex review of #1365 itself): an item
    that only reaches `item.started` - still running, `status: "in_progress"`,
    `exit_code: null` - must not be counted as a successfully-resolved
    attempt. Without `item_is_resolved`, two failed completed commands plus
    one started-but-never-completed command would attempt=3, errors=2,
    3 != 2, and `all-tools-failed` would NOT fire despite every call that
    actually FINISHED having failed. Measured against the helper before this
    follow-up fix: `DELEGATED_RUN_STATUS: success` over exactly this stream.
    """
    output = write_jsonl(
        tmp_path / "unresolved-item.jsonl",
        [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "command_execution", "command": "make lint",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_2", "type": "command_execution", "command": "make test",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.started", "item": {
                "id": "item_3", "type": "command_execution", "command": "make typecheck",
                "exit_code": None, "status": "in_progress"}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["2"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "both commands that actually finished failed - a third, still "
        f"running, must not rescue the verdict:\n{proc.stdout}"
    )
    assert "all-tools-failed" in found["DELEGATED_RUN_SIGNAL"], proc.stdout


def test_the_codex_attempt_dedupe_matches_the_error_dedupe(tmp_path: Path) -> None:
    """Counter-model review red case, SECOND PASS: the first cut of this test
    excluded `item.started` via `item_is_resolved`, leaving only ONE
    countable event in the whole stream - so it passed even with the
    `counted_codex_attempt_items` dedupe deleted outright, having nothing
    left to collapse. This version gives the dedupe something to do: ONE
    call reported across TWO *resolved* events sharing an id (`item.updated`
    then `item.completed`, both `status: "failed"` - the shape
    `test_a_failed_codex_item_is_counted_once_across_its_lifecycle` already
    pins on the error-side set), plus a SECOND, distinct failed call.

    With the dedupe intact: 2 attempts (one per id), 2 errors, equal and >1
    -> `all-tools-failed`. Delete `counted_codex_attempt_items`'s id check
    and `item_7`'s two events both count: 3 attempts, 2 errors, unequal ->
    the signal does not fire and this test goes red - which is the point.
    """
    output = write_jsonl(
        tmp_path / "one-call-two-resolved-events-plus-another.jsonl",
        [
            {"type": "item.updated", "item": {
                "id": "item_7", "type": "command_execution",
                "exit_code": 2, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_7", "type": "command_execution",
                "exit_code": 2, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_8", "type": "command_execution",
                "exit_code": 3, "status": "failed"}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["2"], (
        "one error per DISTINCT id - item_7's two events must dedupe to one"
        f":\n{proc.stdout}"
    )
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        "two distinct calls, both failed - a broken attempt-dedupe would "
        f"inflate attempts past errors and hide this:\n{proc.stdout}"
    )
    assert "all-tools-failed" in found["DELEGATED_RUN_SIGNAL"], proc.stdout


def test_a_null_status_codex_item_is_not_treated_as_resolved(tmp_path: Path) -> None:
    """Counter-model review red case, SECOND PASS: `item_is_resolved`'s first
    cut excluded only the literal `"in_progress"` status. `status: null`
    lower-cases to the Python string `"none"`, which is not `"in_progress"`
    either, so the exclusion-list version silently counted a `null`-status
    item as RESOLVED - the exact hole a null-check-shaped read would miss.
    Two failed commands plus one `null`-status item must still read as
    all-failed: the positive-evidence rewrite (`status == "completed"` or a
    real integer `exit_code`) treats `null` as neither, so it does not count
    as an attempt at all and cannot rescue the verdict.
    """
    output = write_jsonl(
        tmp_path / "null-status-item.jsonl",
        [
            {"type": "item.completed", "item": {
                "id": "item_1", "type": "command_execution",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.completed", "item": {
                "id": "item_2", "type": "command_execution",
                "exit_code": -1, "status": "failed"}},
            {"type": "item.started", "item": {
                "id": "item_3", "type": "command_execution",
                "exit_code": None, "status": None}},
            {"type": "turn.completed"},
        ],
    )
    proc = run(str(output), "0", "--lane", "codex")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["2"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], (
        f"a null-status item must not read as a resolved success:\n{proc.stdout}"
    )
    assert "all-tools-failed" in found["DELEGATED_RUN_SIGNAL"], proc.stdout


def test_the_gemma_lane_catches_an_all_failed_multi_attempt_run(tmp_path: Path) -> None:
    """The gemma/OpenCode recognizer gets its own multi-attempt red case
    (counter-model review), not only the codex lane the incident happened on.

    Two distinct tool calls, both denied/failed, nothing else attempted.
    """
    output = write_jsonl(
        tmp_path / "gemma-two-failed.jsonl",
        [
            {"type": "step_start"},
            {"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error"}}},
            {"type": "tool_use", "part": {"tool": "bash", "state": {"status": "error"}}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    proc = run(str(output), "0", "--lane", "gemma")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["2"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], proc.stdout
    assert "all-tools-failed" in found["DELEGATED_RUN_SIGNAL"], proc.stdout


def test_the_qwen_lane_catches_an_all_failed_multi_attempt_run(tmp_path: Path) -> None:
    """The qwen recognizer's own multi-attempt red case (counter-model review).

    Two `tool_result` blocks in the same message, both `is_error: true`,
    neither call ever succeeding. The terminal event deliberately reports
    `is_error: false` (the Qwen false-success shape #836/#798 are about) so
    this pins `all-tools-failed` in isolation - a `result` carrying its own
    top-level `is_error: true` would already fail via `is_fatal`, which would
    make the assertion true for the wrong reason.
    """
    output = write_jsonl(
        tmp_path / "qwen-two-failed.jsonl",
        [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "run_shell_command"},
                {"type": "tool_use", "id": "t2", "name": "run_shell_command"}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "is_error": True,
                 "content": "denied"},
                {"type": "tool_result", "tool_use_id": "t2", "is_error": True,
                 "content": "denied"}]}},
            {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
             "result": "Done."},
        ],
    )
    proc = run(str(output), "0", "--lane", "qwen")
    found = contract(proc.stdout)
    assert proc.returncode == 1, proc.stdout
    assert found["DELEGATED_RUN_TOOL_ERRORS"] == ["2"], proc.stdout
    assert found["DELEGATED_RUN_STATUS"] == ["failure"], proc.stdout
    assert found["DELEGATED_RUN_SIGNAL"] == ["all-tools-failed"], (
        "must fail via the NEW signal specifically, not error-payload/api-error:"
        f"\n{proc.stdout}"
    )
