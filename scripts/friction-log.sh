#!/usr/bin/env bash
# friction-log.sh - Always-on friction capture for the grill-me cycle (issue #426).
#
# Appends one JSON object per friction event to a local, append-only buffer
# (default: .claude/friction.jsonl). This is the "capture" half of the grill-me
# cycle: thin instrumentation the flow commands call on every step of every run,
# success OR failure, so the richest friction (the runs that fail partway) is not
# lost. The buffer is drained later by /self-improvement:retro (local codify) and,
# when installed, by #433's shared "cpp-memory record" (portable codify).
#
# Fail-open by design: this NEVER exits non-zero and NEVER blocks a flow run, even
# on bad input or an unwritable path. Capture is best-effort; a flow must never
# break because its flight recorder could not write.
#
# Usage:
#   friction-log.sh --class <class> --signal <text> [options]
#
# Required:
#   --class   <c>    friction class: permission-prompt | gate-failure |
#                    red-output | manual-intervention | other
#   --signal  <s>    short description of what happened
#
# Optional:
#   --fix     <f>    proposed fix (e.g. a settings.json allow rule, a Make target)
#   --scope   <sc>   local | portable                         (default: local)
#   --outcome <o>    free text (approved | retried | worked-around | corrected)
#   --run     <r>    run label (e.g. "flow:auto #426")
#   --step    <st>   step label (e.g. "1/9 Start")
#   --risk    <rk>   risk tier of the underlying command (e.g. READONLY-ADDABLE,
#                    WRITE-LOCAL, DESTRUCTIVE). Set by the permission-prompt census
#                    hook so retro can allowlist only safe tiers; empty otherwise.
#
# Environment:
#   CPP_FRICTION_LOG  override the buffer path (default: .claude/friction.jsonl)
#
# Example:
#   friction-log.sh --class permission-prompt \
#     --signal 'gh issue view 426 required approval' \
#     --fix 'Bash(gh issue view:*)' --scope local \
#     --run 'flow:auto #426' --step '1/9 Start' --outcome approved

# Deliberately NO `set -e`: fail-open means we swallow errors and exit 0.
set -u 2>/dev/null || true

CLASS=""
SIGNAL=""
FIX=""
SCOPE="local"
OUTCOME=""
RUN=""
STEP=""
RISK=""

while [ $# -gt 0 ]; do
  case "$1" in
    --class)   CLASS="${2:-}"; shift 2 || shift ;;
    --signal)  SIGNAL="${2:-}"; shift 2 || shift ;;
    --fix)     FIX="${2:-}"; shift 2 || shift ;;
    --scope)   SCOPE="${2:-local}"; shift 2 || shift ;;
    --outcome) OUTCOME="${2:-}"; shift 2 || shift ;;
    --run)     RUN="${2:-}"; shift 2 || shift ;;
    --step)    STEP="${2:-}"; shift 2 || shift ;;
    --risk)    RISK="${2:-}"; shift 2 || shift ;;
    -h|--help)
      sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "friction-log: ignoring unknown argument '$1'" >&2
      shift
      ;;
  esac
done

# Required fields missing -> warn and exit clean; do not append a junk record.
if [ -z "$CLASS" ] || [ -z "$SIGNAL" ]; then
  echo "friction-log: --class and --signal are required (skipping)" >&2
  exit 0
fi

# Escape a string for embedding in a JSON double-quoted value. Handles the two
# structural characters (backslash, double-quote) and folds control whitespace so
# every record stays on a single line (JSONL).
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"   # backslash first
  s="${s//\"/\\\"}"   # then double-quote
  s="${s//$'\r'/}"    # drop carriage returns
  s="${s//$'\t'/ }"   # tabs -> space
  s="${s//$'\n'/ }"   # newlines -> space
  printf '%s' "$s"
}

LOG="${CPP_FRICTION_LOG:-.claude/friction.jsonl}"
DIR="$(dirname "$LOG")"

if ! mkdir -p "$DIR" 2>/dev/null; then
  echo "friction-log: cannot create '$DIR' (skipping)" >&2
  exit 0
fi

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || printf '')"

LINE="$(printf '{"ts":"%s","run":"%s","step":"%s","class":"%s","signal":"%s","fix":"%s","scope":"%s","outcome":"%s","risk":"%s"}' \
  "$(json_escape "$TS")" \
  "$(json_escape "$RUN")" \
  "$(json_escape "$STEP")" \
  "$(json_escape "$CLASS")" \
  "$(json_escape "$SIGNAL")" \
  "$(json_escape "$FIX")" \
  "$(json_escape "$SCOPE")" \
  "$(json_escape "$OUTCOME")" \
  "$(json_escape "$RISK")")"

if ! printf '%s\n' "$LINE" >>"$LOG" 2>/dev/null; then
  echo "friction-log: cannot write '$LOG' (skipping)" >&2
  exit 0
fi

exit 0
