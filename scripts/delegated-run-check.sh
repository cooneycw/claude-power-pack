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
#   api-error        a terminal payload whose text begins `[API Error` - the
#                    Qwen false-success signature, checked for all lanes
#   error-payload    the stream carries an explicit error marker
#                    (is_error true, subtype/type "error", a top-level "error")
#   no-turns         a result reporting num_turns <= 1 (fails w/ --expect-tools)
#   no-tool-use      zero tool events in the whole stream (fails w/ --expect-tools).
#                    On the gemma lane this is also the ollama/ollama#14958
#                    `/v1` tool-call-drop signature - see /gemma:status Step 4.
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

# Fields that carry model- or harness-authored text across the three formats:
# Qwen Code / Codex put the terminal text in `result`; OpenCode nests prose
# under `part.text`. `message`/`error` are the harness's own error channels.
TEXT_FIELDS = ("result", "text", "message", "error", "detail", "content")
TOOL_MARKERS = ("tool_use", "tool_call", "tool_result", "function_call", "tool")

signals = set()
detail = ""
turns = None
saw_tool = False
parsed = 0


def note(text):
    """Record the FIRST error text seen; later ones add nothing to triage."""
    global detail
    if text and not detail:
        detail = " ".join(str(text).split())[:300]


def strings(node, depth=0):
    """Yield (key, value) for every string leaf, so a nested payload is seen."""
    if depth > 8:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                yield key, value
            else:
                yield from strings(value, depth + 1)
    elif isinstance(node, list):
        for item in node:
            yield from strings(item, depth + 1)


def walk(node, depth=0):
    """Look for tool events, turn counts, and explicit error flags anywhere."""
    global turns, saw_tool
    if depth > 8:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = key.lower()
            if lowered in ("num_turns", "numturns") and isinstance(value, int):
                turns = value if turns is None else max(turns, value)
            if lowered in ("type", "subtype", "role", "event", "name", "tool"):
                if isinstance(value, str):
                    low = value.lower()
                    if any(marker in low for marker in TOOL_MARKERS):
                        saw_tool = True
                    if low == "error":
                        signals.add("error-payload")
            if lowered == "is_error" and value is True:
                signals.add("error-payload")
            if lowered in ("error", "errors") and value not in (None, "", [], {}):
                signals.add("error-payload")
                if isinstance(value, str):
                    note(value)
            walk(value, depth + 1)
    elif isinstance(node, list):
        for item in node:
            walk(item, depth + 1)


with open(path, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            # Not JSON: a harness banner or a stderr line that landed in the
            # stream. Still worth an api-error scan - that banner is sometimes
            # exactly where the error surfaces.
            if line.lstrip().startswith("[API Error"):
                signals.add("api-error")
                note(line)
            continue
        parsed += 1
        walk(obj)
        for key, value in strings(obj):
            stripped = value.lstrip()
            if key.lower() in TEXT_FIELDS and stripped.startswith("[API Error"):
                signals.add("api-error")
                note(value)

if parsed == 0 and not signals:
    signals.add("output-empty")

if not saw_tool:
    signals.add("no-tool-use")
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
# `no-turns` and `no-tool-use` describe a run that did nothing. On an `auto`
# lane that IS the failure; on an `exec` lane a tool-free answer can be the
# whole point, so they are reported and not counted unless --expect-tools.
STATUS="success"
for signal in ${SIGNALS+"${SIGNALS[@]}"}; do
    case "$signal" in
        no-turns|no-tool-use)
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
