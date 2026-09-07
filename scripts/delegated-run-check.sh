#!/usr/bin/env bash
# delegated-run-check.sh - Did a delegated-model run actually succeed? (issue #798)
#
# Problem:
#   Every delegated lane (/qwen:*, /gemma:*, /codex:*) decided a run's fate by
#   testing `$?` against zero, and in all six command documents that test could
#   not observe the CLI's exit status:
#
#     1. `... | tee "$OUT"` then `EXIT=$?` reads TEE's status, not the CLI's.
#        `pipefail` was set nowhere (grepped: zero hits across all three lanes),
#        so the documented `exit 124 = timeout` branch was unreachable - a run
#        that blew its 1800s timeout reported success.
#     2. In the three `auto` documents the invocation and the check sat in
#        SEPARATE fenced bash blocks with prose between them. Executed as
#        written those are separate shells, so `$?` had no relationship to the
#        run at all.
#     3. The Qwen CLI reports success on a failed run outright (verified
#        2026-09-07, @qwen-code/qwen-code 0.15.10, unreachable endpoint):
#        `EXIT=0  subtype: "success"  is_error: false  num_turns: 1` with the
#        only evidence of failure being `[API Error: ...]` inside the terminal
#        `result` string. So even a CORRECT exit-code check still passes.
#
#   A dead endpoint, a timeout, or an API error therefore read as a completed
#   task, and `/*:auto` marched on into review, quality gates, /flow:finish and
#   /flow:merge on an empty diff. Found while diagnosing why /qwen:* had been
#   pointed at an offline MacBook: the endpoint was wrong long enough to matter
#   and nothing surfaced it, because the harness reported success throughout.
#
# This helper is the answer to (3), and the thing the fixed exit-code capture
# hands its verdict to. It NEVER trusts the exit code alone: it inspects the
# JSONL payload the run produced and reports every failure signal it finds.
#
# It is written DEFENSIVELY for all three harnesses rather than assuming they
# share the Qwen behaviour - the issue verified the false-success only for
# Qwen Code, and explicitly declined to assume it of OpenCode (gemma) or the
# Codex CLI. Signals absent from a format simply never fire.
#
# Usage:
#   delegated-run-check.sh <output-file> <exit-code> [--lane qwen|gemma|codex]
#                          [--expect-tools] [--quiet]
#
#   <output-file>   The JSONL the run was captured to. REQUIRED.
#   <exit-code>     The CLI's own status, captured in the SAME shell as the
#                   run. REQUIRED - pass it even when it is 0; a 0 that the
#                   payload contradicts is precisely case (3).
#   --lane          Which lane produced the file. Advisory: it is reported and
#                   tunes nothing, because format detection is per-line. A file
#                   from an unnamed lane is checked identically.
#   --expect-tools  Promote the "did no work" signals (no-turns, no-tool-use)
#                   from reported to FAILING. The `auto` lanes pass it - they
#                   delegate an implementation, so a run that used no tools
#                   wrote no code. The `exec` lanes do not: `/codex:exec` on a
#                   trivial prompt legitimately answers without touching a file.
#   --quiet         Contract lines only; suppress the human-readable summary.
#
# Output ends with a machine-readable contract:
#   DELEGATED_RUN_LANE:   qwen | gemma | codex | unknown
#   DELEGATED_RUN_FILE:   <path as given>
#   DELEGATED_RUN_EXIT:   <the exit code as passed>
#   DELEGATED_RUN_SIGNAL: <one line per signal found; omitted when none>
#   DELEGATED_RUN_DETAIL: <the first error text found, truncated; omitted when none>
#   DELEGATED_RUN_STATUS: success | failure
#
# Signals:
#   exit-nonzero     the CLI's own status was not 0
#   timeout          that status was 124 - bash `timeout` killed the run
#   output-missing   no output file exists (the run never produced a stream)
#   output-empty     the file exists but holds nothing parseable
#   output-unrecognized  parsed, but no recognizable event in the whole stream
#   api-error        a TERMINAL payload whose text begins `[API Error` - the
#                    Qwen false-success signature, checked for all lanes. Scoped
#                    to terminal and error events on purpose: matching the
#                    banner anywhere made a model QUOTING it read as a failed
#                    run, and a guard against false success that manufactures
#                    false failure is not an improvement
#   error-payload    an event announces failure at its TOP level (is_error true,
#                    type/subtype "error", a top-level "error"). Deliberately
#                    not recursive: a DENIED tool call is the /gemma:auto fence
#                    working as designed, not a failed run
#   no-turns         a result reporting num_turns <= 1 (fails w/ --expect-tools)
#   no-tool-use      zero tool events in the whole stream (fails w/ --expect-tools).
#                    On the gemma lane this is also the ollama/ollama#14958
#                    `/v1` tool-call-drop signature - see /gemma:status Step 4.
#                    Tool-event names are format facts VERIFIED against real
#                    captures, never guessed - codex signals work as
#                    `command_execution` / `file_change`, which an earlier cut
#                    of this helper did not recognize, so every successful
#                    /codex:auto run would have failed as tool-free
#   no-terminal-event  the stream stops before its terminal event: a truncated
#                    or killed run (fails w/ --expect-tools)
#
# Exit codes:
#   0  the run succeeded (DELEGATED_RUN_STATUS: success)
#   1  the run failed (DELEGATED_RUN_STATUS: failure)
#   2  usage error
#
# This helper is NOT fail-open, and that is deliberate. Every other advisory in
# the flow family shrugs off what it cannot assess, because a guard that cannot
# see must not stop a run. This one is the opposite: it exists because an
# unassessable run was being reported as a success. When it cannot read the
# stream it says `failure`, because "the delegated model produced no output"
# is not an inconclusive result - it is the failure.

set -uo pipefail

OUTPUT_FILE=""
EXIT_CODE=""
LANE="unknown"
EXPECT_TOOLS=0
QUIET=0

usage() {
    sed -n '2,90p' "$0" | sed 's/^# \{0,1\}//'
}

EXPECT_LANE=0
for arg in "$@"; do
    if [[ "$EXPECT_LANE" -eq 1 ]]; then
        LANE="$arg"
        EXPECT_LANE=0
        continue
    fi
    case "$arg" in
        --lane)          EXPECT_LANE=1 ;;
        --lane=*)        LANE="${arg#--lane=}" ;;
        --expect-tools)  EXPECT_TOOLS=1 ;;
        --quiet)         QUIET=1 ;;
        --help|-h)       usage; exit 0 ;;
        -*)
            echo "delegated-run-check: unknown option: $arg" >&2
            exit 2
            ;;
        *)
            if [[ -z "$OUTPUT_FILE" ]]; then
                OUTPUT_FILE="$arg"
            elif [[ -z "$EXIT_CODE" ]]; then
                EXIT_CODE="$arg"
            else
                echo "delegated-run-check: unexpected argument: $arg" >&2
                exit 2
            fi
            ;;
    esac
done

if [[ -z "$OUTPUT_FILE" || -z "$EXIT_CODE" ]]; then
    echo "delegated-run-check: usage: delegated-run-check.sh <output-file> <exit-code> [--lane L] [--expect-tools]" >&2
    exit 2
fi

if ! [[ "$EXIT_CODE" =~ ^[0-9]+$ ]]; then
    echo "delegated-run-check: exit code must be an integer, got: $EXIT_CODE" >&2
    exit 2
fi

case "$LANE" in
    qwen|gemma|codex|unknown) ;;
    *)
        echo "delegated-run-check: unknown lane '$LANE' (expected qwen|gemma|codex)" >&2
        exit 2
        ;;
esac

SIGNALS=()
DETAIL=""

add_signal() { SIGNALS+=("$1"); }

# --- The CLI's own status ---------------------------------------------------
# Necessary, never sufficient. Case (3) is exactly an exit 0 over a failed run.
if [[ "$EXIT_CODE" -ne 0 ]]; then
    add_signal "exit-nonzero"
    if [[ "$EXIT_CODE" -eq 124 ]]; then
        add_signal "timeout"
        DETAIL="bash timeout killed the run (exit 124) - it stalled or the task is too big"
    else
        DETAIL="CLI exited $EXIT_CODE"
    fi
fi

# --- The payload ------------------------------------------------------------
if [[ ! -f "$OUTPUT_FILE" ]]; then
    add_signal "output-missing"
    [[ -z "$DETAIL" ]] && DETAIL="no output file at $OUTPUT_FILE - the run produced no stream"
elif [[ ! -s "$OUTPUT_FILE" ]]; then
    add_signal "output-empty"
    [[ -z "$DETAIL" ]] && DETAIL="output file is empty - the run produced no stream"
else
    # Parse per line as JSON rather than grepping the raw text. A raw grep for
    # `[API Error` matches the model's own prose and any diff that quotes this
    # very file, so the check is anchored to known payload FIELDS and to the
    # START of the string, which is where the harness puts its error banner.
    PY_OUT=$(python3 - "$OUTPUT_FILE" <<'PYEOF' 2>/dev/null
import json
import sys

path = sys.argv[1]

# --- Format facts, verified against real streams on disk (issue #798 review) --
# Guessing these was not an option: the first cut of this helper recognized only
# `tool_use`-shaped events and would therefore have flagged every SUCCESSFUL
# `/codex:auto` run as `no-tool-use`, failing the lane outright under
# --expect-tools. Checked against five real `codex exec --json` captures, four
# OpenCode captures and the Qwen streams in /tmp:
#
#   qwen  (Qwen Code CLI):  system | assistant | result
#                           terminal `result` carries num_turns + the text
#   gemma (OpenCode):       step_start | tool_use | text | step_finish
#   codex (Codex CLI):      thread.started | turn.started | item.started |
#                           item.completed{item.type} | turn.completed
#                           item.type in {agent_message, command_execution,
#                                         file_change, mcp_tool_call}
#
# `agent_message` is deliberately NOT a tool marker - it is the model talking.
TOOL_TYPES = {
    "tool_use", "tool_call", "tool_result", "function_call", "tool",
    "command_execution", "file_change", "mcp_tool_call",
    "patch_apply", "apply_patch", "local_shell_call", "exec_command",
}

# A stream that stops before its terminal event is a run that did not finish.
# `turn.completed` was absent from 2 of 5 codex captures - and one of those was
# a run still executing when it was sampled, which is exactly the truncation
# this detects. It is reported for every lane but only FAILS under
# --expect-tools, because a killed `exec` stream still leaves a usable answer
# while a killed `auto` stream leaves an incomplete implementation.
TERMINAL_TYPES = {"result", "turn.completed", "thread.completed", "step_finish"}

# Where a harness puts model- or harness-authored text.
TEXT_FIELDS = ("result", "text", "message", "error", "detail", "content")

signals = set()
detail = ""
turns = None
saw_tool = False
saw_terminal = False
recognized = 0
parsed = 0


def note(text):
    """Record the FIRST error text seen; later ones add nothing to triage."""
    global detail
    if text and not detail:
        detail = " ".join(str(text).split())[:300]


def type_of(node):
    return str(node.get("type", "")).lower() if isinstance(node, dict) else ""


def tool_types_in(node, depth=0):
    """Every type/tool/name value in the object, so `item.type` is seen too."""
    if depth > 6:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() in ("type", "tool", "name") and isinstance(value, str):
                yield value.lower()
            else:
                yield from tool_types_in(value, depth + 1)
    elif isinstance(node, list):
        for item in node:
            yield from tool_types_in(item, depth + 1)


def texts_of(node, depth=0):
    """Text leaves under the KNOWN payload fields, at most two levels deep.

    Deliberately shallow. The first cut walked the whole object and matched
    `[API Error` in any nested `content`, which meant a model quoting the
    banner - or this repo's own diff - read as a failed run. A guard against
    false success that manufactures false failure is not an improvement.
    """
    if depth > 2 or not isinstance(node, dict):
        return
    for key, value in node.items():
        if key.lower() not in TEXT_FIELDS:
            continue
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            yield from texts_of(value, depth + 1)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield item
                elif isinstance(item, dict):
                    yield from texts_of(item, depth + 1)


def is_fatal(node):
    """Harness-level failure, judged at the TOP level of an event only.

    Scoped deliberately. Scanning every nesting level for `is_error` or a
    non-empty `error` key made a DENIED TOOL CALL fatal - and a denied command
    is the /gemma:auto fence working exactly as designed ("A model that tries
    `git commit` once and moves on is behaving exactly as designed"). The
    helper would have contradicted the document it serves.
    """
    if node.get("is_error") is True:
        return True
    if type_of(node) == "error" or type_of(node).endswith(".error"):
        return True
    if str(node.get("subtype", "")).lower() == "error":
        return True
    error = node.get("error")
    return error not in (None, "", [], {}, False)


with open(path, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            # Not JSON: a harness banner or a stderr line that landed in the
            # stream. That banner is sometimes exactly where the error surfaces.
            if line.lstrip().startswith("[API Error"):
                signals.add("api-error")
                note(line)
            continue
        parsed += 1
        if not isinstance(obj, dict):
            continue

        kind = type_of(obj)
        if kind:
            recognized += 1

        if any(value in TOOL_TYPES for value in tool_types_in(obj)):
            saw_tool = True

        terminal = kind in TERMINAL_TYPES
        if terminal:
            saw_terminal = True
            if isinstance(obj.get("num_turns"), int):
                turns = obj["num_turns"] if turns is None else max(turns, obj["num_turns"])

        fatal = is_fatal(obj)
        if fatal:
            signals.add("error-payload")
            if isinstance(obj.get("error"), str):
                note(obj["error"])

        # The Qwen false-success signature lives in the TERMINAL payload; an
        # explicit error event is the other place a harness announces it.
        if terminal or fatal:
            for text in texts_of(obj):
                if text.lstrip().startswith("[API Error"):
                    signals.add("api-error")
                    note(text)

if parsed == 0 or recognized == 0:
    # Parsed nothing, or parsed only objects with no recognizable event shape
    # (`{}` repeated is the degenerate case). Neither is a run.
    signals.add("output-unrecognized")
else:
    if not saw_tool:
        signals.add("no-tool-use")
    if not saw_terminal:
        signals.add("no-terminal-event")
    if turns is not None and turns <= 1:
        signals.add("no-turns")

print("SIGNALS=" + ",".join(sorted(signals)))
print("DETAIL=" + detail)
PYEOF
)
    PY_STATUS=$?

    if [[ "$PY_STATUS" -ne 0 || -z "$PY_OUT" ]]; then
        # python3 is a hard dependency of the repo (3.11+), so this is a real
        # anomaly rather than a portability case. Report it as a signal instead
        # of silently passing: an unreadable stream is not a clean run.
        add_signal "output-unreadable"
        [[ -z "$DETAIL" ]] && DETAIL="could not parse $OUTPUT_FILE as a JSONL stream"
    else
        PY_SIGNALS="${PY_OUT%%$'\n'*}"
        PY_SIGNALS="${PY_SIGNALS#SIGNALS=}"
        PY_DETAIL="${PY_OUT#*$'\n'}"
        PY_DETAIL="${PY_DETAIL#DETAIL=}"
        if [[ -n "$PY_SIGNALS" ]]; then
            IFS=',' read -r -a found <<< "$PY_SIGNALS"
            for signal in "${found[@]}"; do
                [[ -n "$signal" ]] && add_signal "$signal"
            done
        fi
        [[ -z "$DETAIL" && -n "$PY_DETAIL" ]] && DETAIL="$PY_DETAIL"
    fi
fi

# --- Verdict ----------------------------------------------------------------
# `no-turns`, `no-tool-use` and `no-terminal-event` describe a run that did
# nothing, or did not finish. On an `auto` lane either IS the failure; on an
# `exec` lane a tool-free answer can be the whole point and a killed stream
# still leaves a usable partial answer, so all three are reported and not
# counted unless --expect-tools. Everything else fails on any lane.
STATUS="success"
for signal in ${SIGNALS+"${SIGNALS[@]}"}; do
    case "$signal" in
        no-turns|no-tool-use|no-terminal-event)
            [[ "$EXPECT_TOOLS" -eq 1 ]] && STATUS="failure"
            ;;
        *)
            STATUS="failure"
            ;;
    esac
done

if [[ "$QUIET" -eq 0 ]]; then
    if [[ "$STATUS" == "failure" ]]; then
        echo "delegated-run-check: the $LANE run FAILED - do not proceed as though it produced work."
        [[ -n "$DETAIL" ]] && echo "  detail: $DETAIL"
        echo "  output: $OUTPUT_FILE"
    else
        echo "delegated-run-check: the $LANE run looks clean (exit $EXIT_CODE, payload checked)."
    fi
fi

echo "DELEGATED_RUN_LANE: $LANE"
echo "DELEGATED_RUN_FILE: $OUTPUT_FILE"
echo "DELEGATED_RUN_EXIT: $EXIT_CODE"
for signal in ${SIGNALS+"${SIGNALS[@]}"}; do
    echo "DELEGATED_RUN_SIGNAL: $signal"
done
[[ -n "$DETAIL" ]] && echo "DELEGATED_RUN_DETAIL: $DETAIL"
echo "DELEGATED_RUN_STATUS: $STATUS"

[[ "$STATUS" == "success" ]] && exit 0
exit 1
