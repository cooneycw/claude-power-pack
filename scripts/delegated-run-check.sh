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
#   DELEGATED_RUN_EVENTS: <non-blank lines that parsed as JSON>
#   DELEGATED_RUN_RECOGNIZED: <of those, the ones with a recognizable event shape>
#   DELEGATED_RUN_UNPARSED: <non-blank lines that did NOT parse (issue #1265)>
#   DELEGATED_RUN_TOOL_ERRORS: <count of tool calls that reported an error, in
#                         any harness's shape; ALWAYS emitted, 0 too - see below>
#   DELEGATED_RUN_STATUS: success | failure
#
# Two conventions live in that block, and the difference is deliberate rather
# than stylistic. SIGNAL and DETAIL are omitted when there is nothing to say.
# LANE, FILE, EXIT, EVENTS, RECOGNIZED, UNPARSED, TOOL_ERRORS and STATUS are
# always emitted.
#
# TOOL_ERRORS is in the second family because it is a COUNT, and a count that
# appears only when non-zero cannot distinguish "I looked and found none" from
# "this version of the helper does not look". A caller that has to tell those
# apart - which is the whole reason the line exists - would be back to the gap
# it was added to close. An always-present `0` says the first thing plainly.
# (`SIGNAL` and `DETAIL` carry that same gap today; see #836's nit-store entry.)
#
# What TOOL_ERRORS is FOR (issue #836):
#   DELEGATED_RUN_STATUS answers "did the delegated PROCESS run cleanly?" Its
#   readers take it for "did the delegated WORK happen?" A denied tool call
#   satisfies every signal this helper has - tool_use occurred, the payload is
#   well formed, the exit code is 0 - so a run whose every command was refused
#   reports `success`. The worked example returned a fabricated empty docker
#   inventory that way, and nothing downstream could have told.
#
#   Widening `is_fatal` is NOT the remedy and must not be attempted: the
#   recursive version existed, made every fenced `git commit` a failed run, and
#   was reverted for a reason that still holds. The larger question gets its own
#   channel instead. A non-zero TOOL_ERRORS is not a failure - it is the one
#   fact a caller needs in order to go and look.
#
#   The name is the honest one. Telling a DENIED call from a tool that failed on
#   its own means matching each harness's deny-rule wording, which is a guess
#   about format; this script commits to verified format facts instead. So the
#   count says TOOL_ERRORS, and means exactly that.
#
# One counter, three harnesses, three shapes (issue #1054):
#   The count above was written against ONE of them. It matched a tool call's
#   nested `state.status == "error"`, which is the OpenCode/gemma shape, and no
#   other - so on the codex and qwen lanes it was structurally incapable of
#   returning non-zero, whatever happened. Measured on a real `/codex:auto` run:
#   four commands exited non-zero, two of them the delegated model's own
#   `make lint` and `make test-file`, which a blocked download meant never ran
#   at all - and the helper reported `TOOL_ERRORS: 0`, `STATUS: success`, and
#   the sentence "no tool call reported an error". That is the #836 false-clean
#   exactly, one lane over: `0` meant "cannot see" and read as "checked, none".
#
#   So the recognizer is per-harness, and the always-emitted `0` is only as
#   good as that list of shapes. Adding a lane means adding a shape here, and
#   a committed case on THAT lane asserting a non-zero count - the reason this
#   survived is that the counter had a negative control for the shape it could
#   see and none for either shape it could not.
#
# Signals:
#   exit-nonzero     the CLI's own status was not 0
#   timeout          that status was 124 - bash `timeout` killed the run
#   output-missing   no output file exists (the run never produced a stream)
#   output-empty     the file exists but holds nothing parseable
#   output-unrecognized  parsed, but no recognizable event in the whole stream
#   line-too-deep    a line nested past the interpreter's JSON recursion limit.
#                    It is UNREADABLE here, and an unread event could have been a
#                    failure, so it fails the run rather than being skipped as
#                    harmless (issue #1265). Ordinary non-JSON lines - banners,
#                    stderr - are only counted in UNPARSED
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
#   all-tools-failed MORE THAN ONE tool call was attempted and every single one
#                    of them failed (issue #1365). With zero successful calls
#                    the delegated model cannot have read, written or verified
#                    anything, so "the process ran cleanly" and "nothing
#                    happened" coincide exactly - unlike a single denied call,
#                    which is the /gemma:auto fence working as designed (#836)
#                    and stays success. Scoped to >1 attempts for exactly that
#                    reason: it must not re-flag #836/#892/#1054's pinned
#                    single-attempt cases. A 1-of-1 failed run is a DIFFERENT,
#                    still-open residual - this signal does not cover it.
#                    Always fails the run, with or without --expect-tools.
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

#: NEGATIVE-CONTROL: controls/delegated-run-check
#: ADR 0008 row 13, class G: whether a /codex, /qwen or /gemma run is treated as
#: success rests on this helper, and nothing re-derives it (issue #1265). The
#: control's BAD cases are failed tool calls nested 8 and 50 levels deep - the
#: walk stopped at 6 and reported 0 - and its anchor is this script at b935d64.

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
# NAMED FOR THE SCRIPT, NOT ITS MARKER NAMESPACE, and deliberately: this helper
# already prints `DELEGATED_RUN_EXIT: <exit code as passed>` on stdout - the
# DELEGATED run's status, which the caller hands in. That is a different fact
# from THIS script's own exit status, and one name for two facts separated only
# by `:` versus `=` is a finding that cannot tell our thing from a neighbour's.
trap 'printf "DELEGATED_RUN_CHECK_EXIT=%d\n" "$?" >&2' EXIT

OUTPUT_FILE=""
EXIT_CODE=""
LANE="unknown"
EXPECT_TOOLS=0
QUIET=0

usage() {
    # The WHOLE header, to the first non-comment line - never a fixed line range,
    # which silently truncated Signals and Exit codes once the header outgrew it
    # (issue #1265).
    awk 'NR >= 2 { if ($0 !~ /^#/) exit; print }' "$0" | sed 's/^# \{0,1\}//'
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
#: The denominator. A helper whose whole defect was "reports success when
#: nothing ran" must be able to say how much it actually looked at: EVENTS is
#: the non-blank lines that PARSED as JSON, RECOGNIZED the subset carrying a
#: recognizable event shape, and UNPARSED the non-blank lines that did not parse
#: at all (issue #1265). Before UNPARSED existed those lines vanished from every
#: count, so `RECOGNIZED == EVENTS` read as "saw all of it" over a payload with
#: twenty unreadable lines. 0 EVENTS means the verdict was computed over nothing,
#: which is UNKNOWN rather than clean - and `output-unrecognized` says so.
EVENTS=0
RECOGNIZED=0
UNPARSED=0
#: Initialized HERE, not inside the parse branch. It used to be set only on the
#: path that runs the JSONL parser, so an empty output file skipped it and the
#: script died on `TOOL_ERRORS: unbound variable` PART WAY THROUGH the contract
#: - after SIGNAL and DETAIL, before STATUS - so a caller reading the contract
#: got no verdict line at all. (This comment used to add "and on main that exits
#: 0 ... reported success"; measured, the pre-fix path exits 1 on an empty file -
#: `git show c7297c2~1:scripts/delegated-run-check.sh` - Nit Store #864 comment
#: 5679524656, corrected in #1265.) Found while adding the denominator.
TOOL_ERRORS=0
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
#                                         file_change, mcp_tool_call, error}
#
# `error` was ABSENT from that list until #892, and the reason is worth keeping:
# these facts were "verified against real streams on disk" - five captures of
# runs that WORKED. An enumeration derived only from successful runs cannot
# contain the failure item, and nothing about the list looks incomplete. So
# `item.type: "error"` went unlooked-for, and a lane whose execution tool never
# started reported success. Treat this enumeration as a floor, not a census:
# a membership list is only as complete as the population it was drawn from.
#
# `agent_message` is deliberately NOT a tool marker - it is the model talking.
TOOL_TYPES = {
    "tool_use", "tool_call", "tool_result", "function_call", "tool",
    "command_execution", "file_change", "mcp_tool_call",
    "patch_apply", "apply_patch", "local_shell_call", "exec_command",
    # Codex multi-agent collaboration (issue #1265). The spelling is taken from
    # a REAL capture, not guessed: codex-cli 0.158.0 with `multi_agent` enabled
    # emits `item.type: "collab_tool_call"` - tests/fixtures/delegated_runs/
    # codex-collab-capture.jsonl. `collab_agent_tool_call`, the other candidate
    # the nit named, was NOT observed and is deliberately absent.
    "collab_tool_call",
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
tool_errors = 0
tool_attempts = 0
saw_tool = False
saw_terminal = False
recognized = 0
parsed = 0
unparsed = 0


def note(text):
    """Record the FIRST error text seen; later ones add nothing to triage."""
    global detail
    if text and not detail:
        detail = " ".join(str(text).split())[:300]


def type_of(node):
    return str(node.get("type", "")).lower() if isinstance(node, dict) else ""


def _walk(node):
    """Every dict and list in ``node``, depth-first, with NO depth limit.

    Iterative on purpose (issue #1265). The recursive walks this replaces
    stopped at depth 6 and reported what they had found so far - a failed
    tool call nested deeper counted as 0, the confident answer over part of
    the payload this helper exists to refuse. An explicit stack has no depth
    at which it gives up and cannot hit RecursionError; JSON from json.loads
    cannot be cyclic, so it always terminates. Children are pushed in reverse
    so the visit order matches the old recursion's.
    """
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(reversed([v for v in current.values() if isinstance(v, (dict, list))]))
        elif isinstance(current, list):
            yield current
            stack.extend(reversed([v for v in current if isinstance(v, (dict, list))]))


def tool_types_in(node):
    """Every type/tool/name value in the object, so `item.type` is seen too."""
    for current in _walk(node):
        if isinstance(current, dict):
            for key, value in current.items():
                if key.lower() in ("type", "tool", "name") and isinstance(value, str):
                    yield value.lower()


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


def errored_tool_calls(node):
    """Count tool calls whose own `state.status` is "error" (issue #836).

    ONE of three recognizers, and the qualifier is load-bearing (issue
    #1054). This matches the OpenCode/gemma shape. The Codex CLI does not
    emit `state` at all and the Qwen CLI does not either, so for two of the
    three lanes this function alone could never return non-zero - see
    `errored_codex_item` and `errored_tool_results` below, and the header's
    "One counter, three harnesses, three shapes".

    This is a COUNT and nothing else. It never reaches `is_fatal`, never enters
    `signals`, and never changes the verdict - the scoping below was litigated
    once already and is correct: a denied call is the fence working, not a
    failed run. The defect #836 reports is not that these calls are missed, it
    is that NOTHING reports them, so a caller reading only the verdict cannot
    tell a run that did the work from one whose every tool call was refused.

    Named for what it counts. A denied call and a tool that failed for its own
    reasons are indistinguishable at this level, because separating them means
    matching each harness's deny-rule WORDING - a guess about format, and the
    header above commits this script to verified format facts instead. So the
    line says `TOOL_ERRORS`, not `DENIED`: the narrower name would claim more
    than the input supports.

    Scoped to tool-ish events on purpose. A `state.status` of "error" nested
    under something that is not a tool call would inflate the count, which is
    this counter's own ownership boundary; `test_a_non_tool_error_state_is_not_
    counted_as_a_tool_error` pins it.
    """
    # OWNED states only (counter-model review, #1265). A `state` counts when it
    # sits on a node that IS a tool call - one carrying its own string `tool`,
    # which is where every OpenCode/gemma capture on disk puts it
    # (`part: {"tool": ..., "type": "tool", "state": {...}}`). And the walk does
    # not descend INTO a tool call: its arguments and returned data are not
    # calls, so an error state inside a successful call's output is a neighbour
    # and must not be counted. Removing the depth cap made that distinction
    # matter; the cap had only been hiding it.
    found = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            stack.extend(v for v in current if isinstance(v, (dict, list)))
            continue
        if not isinstance(current, dict):
            continue
        if isinstance(current.get("tool"), str):
            state = current.get("state")
            if isinstance(state, dict) and str(state.get("status", "")).lower() == "error":
                found += 1
            continue
        stack.extend(v for v in current.values() if isinstance(v, (dict, list)))
    return found


def attempted_tool_calls(node):
    """Count every OpenCode/gemma tool call attempted, success or failure
    (issue #1365).

    The sibling of `errored_tool_calls` with the `state.status` filter
    removed: every node carrying its own string `tool` key is one attempted
    call, counted exactly once (the walk does not descend into it, same as
    the error counter). Used only to tell "some calls succeeded" from "every
    attempted call failed" - never to decide a verdict on its own, and never
    combined with `errored_tool_calls`' count without also comparing them.
    """
    found = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            stack.extend(v for v in current if isinstance(v, (dict, list)))
            continue
        if not isinstance(current, dict):
            continue
        if isinstance(current.get("tool"), str):
            found += 1
            continue
        stack.extend(v for v in current.values() if isinstance(v, (dict, list)))
    return found


#: Item ids already counted as a failed Codex tool call. The Codex CLI reports
#: ONE call across SEVERAL events carrying the same `item.id` - `item.started`
#: then `item.completed` in every capture on disk, and the binary also emits
#: `item.updated`. Counting per event would let a single failed command inflate
#: the number, which is this defect's mirror image: a count that cannot be
#: trusted in the other direction is no more usable than one stuck at zero.
counted_codex_items = set()


#: Item statuses that report a call did not succeed.
#:
#: `failed` is observed in the exec stream this helper reads
#: (`codex-command-failed.jsonl`). `declined` is NOT, and the difference is
#: recorded rather than smoothed over: a counter-model reviewer raised it from
#: upstream Rust source, and measuring the shipped binary (codex-cli 0.155.1)
#: put it in the OTHER protocol - `declined` sits beside the camelCase
#: `inProgress` status matchers (2 of 80 occurrences) and beside NONE of the 47
#: snake_case `in_progress` ones, and the exec JSONL is snake_case throughout.
#:
#: It is matched anyway, because the two risks are not symmetric. Missing it
#: would be a false zero, which is this issue's whole defect; matching it
#: spuriously is impossible, since only a payload literally carrying
#: `"status": "declined"` can match and that string has exactly one meaning.
#: This buys nothing today and costs nothing, which is the only shape of
#: speculative match that belongs in a file committed to verified format facts.
FAILED_ITEM_STATUSES = {"failed", "declined"}


def item_reports_failure(item):
    """Either of Codex's two failure signals on a tool item (issue #1054).

    A failing `status` is the harness's verdict on the call; a non-zero
    `exit_code` is the command's own. Both are checked rather than one assumed
    redundant, because this counter's entire defect was a recognizer that
    matched a single spelling of a fact and reported 0 for every other - and
    the two arms are pinned INDEPENDENTLY in the suite, since a payload
    carrying both proves only that their disjunction works.

    `isinstance(True, int)` is True in Python, so bools are excluded
    explicitly: `"exit_code": true` is not a non-zero exit status, and counting
    it would be fabricated specificity - a number that looks like evidence and
    was never measured.
    """
    if str(item.get("status", "")).lower() in FAILED_ITEM_STATUSES:
        return True
    exit_code = item.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return False
    return exit_code != 0


def errored_codex_item(node):
    """Count a Codex CLI tool item that reported failure (issue #1054).

    Verified against a real capture, not inferred from the docs:
    `tests/fixtures/delegated_runs/codex-command-failed.jsonl` is a genuine
    `codex exec --json` run whose command exited 3, and it lands as

        {"type": "item.completed",
         "item": {"id": "item_1", "type": "command_execution",
                  "command": "...", "exit_code": 3, "status": "failed"}}

    with no `state` key anywhere, which is why `errored_tool_calls` above
    returned 0 for it and the helper then said "no tool call reported an
    error" - an affirmative claim, not a silence.

    Structural, like `is_fatal_item`, and for its reason: it reads exactly
    `node["item"]` and no other depth, so a gemma tool call - whose error lives
    under `part.state` and which has no `item` key - cannot reach it, and a
    `status` belonging to some neighbouring object cannot either.

    Scoped to items whose OWN type is a tool type. `agent_message`, `reasoning`
    and `todo_list` items are the model talking, not tool calls. An item whose
    own type is `"error"` is the harness talking about ITSELF; that is
    `is_fatal_item`'s population, and it feeds a verdict this counter must
    never touch.
    """
    if not type_of(node).startswith("item."):
        return 0
    item = node.get("item")
    if not isinstance(item, dict):
        return 0
    if str(item.get("type", "")).lower() not in TOOL_TYPES:
        return 0
    if not item_reports_failure(item):
        return 0
    item_id = item.get("id")
    if isinstance(item_id, str) and item_id:
        if item_id in counted_codex_items:
            return 0
        counted_codex_items.add(item_id)
    return 1


#: Attempt-side dedupe set, kept SEPARATE from `counted_codex_items` (issue
#: #1365). The two counters answer different questions - "how many calls
#: failed" vs. "how many were attempted" - so a call already claimed by the
#: error counter's id set must still be countable here, and vice versa.
counted_codex_attempt_items = set()


def item_is_resolved(item):
    """Whether a Codex tool item reached a terminal outcome (issue #1365,
    counter-model review, SECOND PASS finding).

    `item.started` (and `item.updated` mid-command) carries `status:
    "in_progress"` and `exit_code: null` - a call still RUNNING, neither a
    success nor a failure yet. Counting it as an attempt before it resolves
    lets an unresolved call sit in the denominator: two commands fail, a
    third only ever reaches `item.started` before the stream ends on
    `turn.completed` (a malformed capture, but not an impossible one), and
    without this check `tool_attempts` (3) would not equal `tool_errors` (2)
    - masking a run where nothing that finished succeeded.

    POSITIVE evidence only, not an exclusion list - the first cut returned
    "anything that isn't the known in-flight spelling", and a counter-model
    second pass caught the hole that shape always has: `status: null` reads
    as the Python string `"none"` once lower-cased, which is not
    `"in_progress"`, so it was being counted as RESOLVED. An unrecognized
    status - `null`, a future harness spelling, anything not verified here -
    must read as unresolved, exactly like a value this script has never
    seen reads as `unknown` everywhere else in it. `status: "completed"` is
    the one success spelling observed in every real capture on disk; a
    non-bool integer `exit_code` is the command's own terminal signal,
    independent of how `status` is spelled.
    """
    if item_reports_failure(item):
        return True
    if str(item.get("status", "")).lower() == "completed":
        return True
    exit_code = item.get("exit_code")
    return isinstance(exit_code, int) and not isinstance(exit_code, bool)


def attempted_codex_item(node):
    """Count a Codex CLI tool item attempted and RESOLVED, success or
    failure (#1365).

    Sibling of `errored_codex_item` with the failure filter replaced by
    `item_is_resolved` (see its docstring for why "attempted" must mean
    "finished", not "started"). Counts every tool-type item the harness
    reports - `command_execution`, `file_change`, `mcp_tool_call`,
    `collab_tool_call`, and any other member of `TOOL_TYPES` the two
    counters already share. A lane's recognizer sees only what `TOOL_TYPES`
    names; an item type absent from that set (none are known today) is
    invisible to both this counter and `errored_codex_item` alike, which is
    the existing scope, not a new gap.

    Same `item.id` dedupe discipline as the error counter, on its OWN set:
    Codex reports one call across several events (`item.started`,
    `item.updated`, `item.completed`) sharing an id, and counting per event
    would inflate an attempt into several.
    """
    if not type_of(node).startswith("item."):
        return 0
    item = node.get("item")
    if not isinstance(item, dict):
        return 0
    if str(item.get("type", "")).lower() not in TOOL_TYPES:
        return 0
    if not item_is_resolved(item):
        return 0
    item_id = item.get("id")
    if isinstance(item_id, str) and item_id:
        if item_id in counted_codex_attempt_items:
            return 0
        counted_codex_attempt_items.add(item_id)
    return 1


def errored_tool_results(node):
    """Count Claude-shaped `tool_result` blocks whose `is_error` is true (#1054).

    The Qwen lane. Read out of the installed CLI's own source rather than
    guessed - `@qwen-code/qwen-code`'s `emitToolResult` builds

        {"type": "user",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "...", "is_error": true}]}}

    from `is_error = Boolean(response.error) || Boolean(responsePartsError)`,
    which is exactly a denied or independently failed call: this counter's
    population, in the same breadth the name claims. The same source pushes a
    `permissionDenials` entry when `errorType` is `EXECUTION_DENIED`, so denial
    is in there too, indistinguishable at this level as everywhere else.

    `is_fatal` reads `is_error` only at an event's TOP level - deliberately, so
    a denied call is not a failed run - and this one is two levels down, so
    nothing in the helper saw it at all.

    Structural for the third time, for the third instance of one reason:
    reading exactly `node["message"]["content"][]` keeps an `is_error`
    belonging to something else out of the count.
    """
    message = node.get("message")
    if not isinstance(message, dict):
        return 0
    content = message.get("content")
    if not isinstance(content, list):
        return 0
    return sum(
        1
        for block in content
        if isinstance(block, dict)
        and str(block.get("type", "")).lower() == "tool_result"
        and block.get("is_error") is True
    )


def attempted_tool_results(node):
    """Count every Qwen `tool_result` block attempted, success or failure
    (issue #1365).

    Sibling of `errored_tool_results` with the `is_error` filter removed.
    Same structural scope: exactly `node["message"]["content"][]`, so a
    `tool_result` belonging to something else cannot inflate the count.
    """
    message = node.get("message")
    if not isinstance(message, dict):
        return 0
    content = message.get("content")
    if not isinstance(content, list):
        return 0
    return sum(
        1
        for block in content
        if isinstance(block, dict) and str(block.get("type", "")).lower() == "tool_result"
    )


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


def is_fatal_item(node):
    """An ITEM whose OWN type is "error".

    NOT sufficient for failure on its own, and that is the whole subtlety.

    Deliberately NOT recursive, and deliberately not part of `is_fatal`. The
    distinction that makes this safe is structural rather than a matter of
    degree:

      - a `state.status == "error"` NESTED INSIDE a tool call is a denied or
        failed call. That is the /gemma:auto fence working as designed, it is
        `TOOL_ERRORS` business, and making `is_fatal` recursive to catch the
        case below would re-break it (see `is_fatal`'s note).
      - an ITEM whose own `type` is "error" is not a tool call at all. It is
        the harness talking about itself.

    BUT the harness uses that same item for benign things. Read from codex's
    own `event_processor_with_jsonl_output.rs`, `ThreadItemDetails::Error` is
    emitted for `ConfigWarning`, `DeprecationNotice` and `ModelRerouted` - all
    of which then return `CodexStatus::Running` and the run continues normally.
    A genuinely critical error takes a DIFFERENT shape, `ThreadEvent::Error`, a
    TOP-LEVEL `{"type":"error"}` event, which `is_fatal` already catches and
    which this function does not touch.

    So an error item alone means "the harness said something about itself",
    which is worth SURFACING and is not worth failing a run over. What makes
    the #892 case a failure is the CONJUNCTION: the harness announced an error
    AND nothing ever ran. That is the difference between "the run did nothing"
    and "the run could not do anything", which is the difference the issue is
    actually about.

    This reads exactly `node["item"]["type"]` and no other depth, so a denied
    tool call - which carries its error under `part.state` and has no `item`
    key - cannot reach it.
    """
    item = node.get("item")
    if not isinstance(item, dict):
        return False
    return str(item.get("type", "")).lower() == "error"


def item_error_message(node):
    """The item's own message, so the operator sees WHY and not only THAT.

    Without this the only signal is `no-tool-use`, which this helper's own
    documentation gives a benign reading ("a question can legitimately be
    answered without touching a file"). That is the difference between "the run
    did nothing" and "the run could not do anything" - between re-running the
    prompt and installing a missing binary.
    """
    item = node.get("item")
    if not isinstance(item, dict):
        return ""
    message = item.get("message")
    return message if isinstance(message, str) else ""


saw_item_error = False

with open(path, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except RecursionError:
            # A line nested past json.loads' own recursion limit. It may well BE
            # JSON - an event this helper cannot read, which could have been a
            # failure - so unlike a banner it is not harmless: `line-too-deep`
            # fails the run, while the rest of the stream is still read and the
            # line is counted (counter-model review, #1265).
            unparsed += 1
            signals.add("line-too-deep")
            continue
        except (ValueError, TypeError):
            # Not JSON: a harness banner or a stderr line that landed in the
            # stream. That banner is sometimes exactly where the error surfaces.
            # Counted (issue #1265): a line this helper could not read is part
            # of the payload, and must not vanish from the denominator.
            unparsed += 1
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
            # Only within a tool event: see errored_tool_calls' ownership note.
            # Three recognizers because there are three harnesses and each
            # writes a failed call down differently (issue #1054). They are
            # disjoint on every stream on disk - a codex item carries no
            # `state`, a gemma part no `item`, a qwen tool_result neither -
            # so one call cannot be counted twice by two of them.
            tool_errors += errored_tool_calls(obj)
            tool_errors += errored_codex_item(obj)
            tool_errors += errored_tool_results(obj)
            # Same three-recognizer split, counting every attempt rather than
            # only the failed ones (issue #1365) - needed to tell "some calls
            # succeeded" from "every attempted call failed".
            tool_attempts += attempted_tool_calls(obj)
            tool_attempts += attempted_codex_item(obj)
            tool_attempts += attempted_tool_results(obj)

        terminal = kind in TERMINAL_TYPES
        if terminal:
            saw_terminal = True
            if isinstance(obj.get("num_turns"), int):
                turns = obj["num_turns"] if turns is None else max(turns, obj["num_turns"])

        item_error = is_fatal_item(obj)
        if item_error:
            # Always surfaced, never fatal by itself: see is_fatal_item. The
            # message is the point - without it the only signal is
            # `no-tool-use`, which this helper documents as benign.
            signals.add("error-item")
            saw_item_error = True
            note(item_error_message(obj))

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
        if saw_item_error:
            # The harness announced an error AND nothing ever ran. Neither half
            # is a failure alone: an error item can be a deprecation notice,
            # and a no-tool run can be a question legitimately answered without
            # touching a file. Together they are a run that COULD NOT act.
            signals.add("error-payload")
    if not saw_terminal:
        signals.add("no-terminal-event")
    if turns is not None and turns <= 1:
        signals.add("no-turns")
    # issue #1365: more than one tool call was attempted and EVERY one of
    # them failed. The >1 requirement is load-bearing, not an arbitrary
    # floor: a single attempted call that failed is #836/#892/#1054's
    # already-protected shape (a denied `git commit`, tried once, the model
    # moves on - the fence working as designed), and widening this to
    # attempted == 1 would re-flag every one of those pinned cases as a
    # failure. Always fails the run - not gated behind --expect-tools, unlike
    # the three signals above, because unlike "the model asked no tools",
    # "every tool it tried came back failed" is never a legitimate outcome.
    if tool_errors > 0 and tool_attempts > 1 and tool_errors == tool_attempts:
        signals.add("all-tools-failed")

print("SIGNALS=" + ",".join(sorted(signals)))
print("DETAIL=" + detail)
print("TOOL_ERRORS=%d" % tool_errors)
print("EVENTS=%d" % parsed)
print("RECOGNIZED=%d" % recognized)
print("UNPARSED=%d" % unparsed)
PYEOF
)
    PY_STATUS=$?

    TOOL_ERRORS=0   # reset per parse; the global default above covers the
                    # paths that never reach the parser at all.
    if [[ "$PY_STATUS" -ne 0 || -z "$PY_OUT" ]]; then
        # python3 is a hard dependency of the repo (3.11+), so this is a real
        # anomaly rather than a portability case. Report it as a signal instead
        # of silently passing: an unreadable stream is not a clean run.
        add_signal "output-unreadable"
        [[ -z "$DETAIL" ]] && DETAIL="could not parse $OUTPUT_FILE as a JSONL stream"
    else
        # Parsed BY NAME, not by position. The previous form read line 1, 2
        # and 3, so adding a field below would have silently left TOOL_ERRORS
        # at its 0 default while looking exactly the same - the same class of
        # confident-wrong zero this issue is about.
        py_field() { printf '%s\n' "$PY_OUT" | sed -n "s/^$1=//p" | head -n 1; }
        PY_SIGNALS="$(py_field SIGNALS)"
        PY_DETAIL="$(py_field DETAIL)"
        PY_TOOL_ERRORS="$(py_field TOOL_ERRORS)"
        PY_EVENTS="$(py_field EVENTS)"
        PY_RECOGNIZED="$(py_field RECOGNIZED)"
        [[ "$PY_TOOL_ERRORS" =~ ^[0-9]+$ ]] && TOOL_ERRORS="$PY_TOOL_ERRORS"
        [[ "$PY_EVENTS" =~ ^[0-9]+$ ]] && EVENTS="$PY_EVENTS"
        [[ "$PY_RECOGNIZED" =~ ^[0-9]+$ ]] && RECOGNIZED="$PY_RECOGNIZED"
        PY_UNPARSED="$(py_field UNPARSED)"
        [[ "$PY_UNPARSED" =~ ^[0-9]+$ ]] && UNPARSED="$PY_UNPARSED"
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
        error-item)
            # INFORMATIONAL, never fatal on its own, and not counted by
            # --expect-tools either. codex emits an error ITEM for
            # ConfigWarning, DeprecationNotice and ModelRerouted, all of which
            # continue the run (CodexStatus::Running). A deprecation notice in
            # a run that did its work is not a failed run.
            #
            # The #892 failure is the CONJUNCTION - an error item AND nothing
            # ever ran - and that raises `error-payload` separately, which
            # falls through to the catch-all below. Keeping the two signals
            # apart is what lets the operator see the harness's own message on
            # a run that succeeded.
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
        # This sentence is the fix for #836. "looks clean" was read as "the
        # work happened"; it only ever meant "no harness-level failure".
        echo "delegated-run-check: the $LANE run had no harness-level failure (exit $EXIT_CODE, payload checked)."
        if [[ "$TOOL_ERRORS" -gt 0 ]]; then
            echo "  NOTE: $TOOL_ERRORS tool call(s) reported an error state - denied by a fence, or failed on their own."
            echo "  That is not a failed run, and this check cannot tell you whether the requested work happened."
        else
            echo "  This does not establish that the requested work happened - no tool call reported an error, which is a different claim."
        fi
        if [[ "$UNPARSED" -gt 0 ]]; then
            # Qualified, never silent (counter-model review, #1265): the verdict
            # above was computed over the lines that parsed, not all of them.
            echo "  NOTE: $UNPARSED line(s) were not JSON and were not examined - this verdict covers the $EVENTS that were."
        fi
    fi
fi

echo "DELEGATED_RUN_LANE: $LANE"
echo "DELEGATED_RUN_FILE: $OUTPUT_FILE"
echo "DELEGATED_RUN_EXIT: $EXIT_CODE"
for signal in ${SIGNALS+"${SIGNALS[@]}"}; do
    echo "DELEGATED_RUN_SIGNAL: $signal"
done
[[ -n "$DETAIL" ]] && echo "DELEGATED_RUN_DETAIL: $DETAIL"
echo "DELEGATED_RUN_EVENTS: $EVENTS"
echo "DELEGATED_RUN_RECOGNIZED: $RECOGNIZED"
echo "DELEGATED_RUN_UNPARSED: $UNPARSED"
echo "DELEGATED_RUN_TOOL_ERRORS: $TOOL_ERRORS"
echo "DELEGATED_RUN_STATUS: $STATUS"

[[ "$STATUS" == "success" ]] && exit 0
exit 1
