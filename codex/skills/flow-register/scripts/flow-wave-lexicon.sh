#!/usr/bin/env bash
# flow-wave-lexicon.sh - reserved vocabulary for wave STATE TRANSITIONS
# (issue #701, the transitions half of #699's declared state).
#
# Motivation: the wave protocol has a strict lexicon at the machine-to-machine
# layer and free prose at the agent-to-agent layer. `FLOW_WAVE: registered|
# refused|verified|address_filled|mismatch-corrected` plus the FLOW_WAVE_*=
# detail lines never misfired across an 11-issue wave. EVERY miscommunication in
# that wave happened in the prose layer:
#
#   - a LANE grant was read as a GATE approval ("you are unblocked for Step 4"
#     beside "hard stop at Step 3 stands"), and only a worker's caution stopped
#     an unjudged gate from passing;
#   - a lane FENCE was read as a lane grant - off-limits-to-A and belongs-to-A
#     expressed in adjacent prose;
#   - four wave-state broadcasts went stale, each accurate when composed and
#     wrong when read, because none carried an as-of stamp;
#   - a conditional merge authorisation was retyped ad hoc four times, carried
#     entirely by the orchestrator remembering to restate the check name.
#
# So this covers the speech acts that are TRANSITIONS WITH A WRONG-ANSWER COST:
# gate verdicts, lane grants, merge authorisations, state assertions, the
# response to a reported deviation, pushback, and the completeness ledger.
#
# WHAT IT DELIBERATELY DOES NOT COVER: the reasoning. The highest-value messages
# in the reference wave were a worker's design-ruling requests, its correction of
# credit the orchestrator had misattributed, and its catch of the crossed
# lane/gate message. None would survive schematisation. Tokens carry the
# TRANSITION; prose carries the ARGUMENT. Accordingly a message with no reserved
# token is always valid - absence is never an error, only a malformed PRESENT
# token is.
#
# ---- The anti-decoration contract (#701's own kill condition) ---------------
#
# The issue that asked for this named the condition under which it should NOT be
# built: "a lexicon nobody validates is prose with extra steps... a reflexive
# `GATE: GO` prints what a considered one prints" - the guard-whose-broken-
# version-looks-like-its-working-version class. So the tokens are READ BACK by
# two mechanisms, both load-bearing:
#
#   1. `validate` REFUSES a malformed reserved token, and
#      `flow-wave-mailbox.sh send` runs it - so a broken transition token cannot
#      be DELIVERED. The failure is visible at the moment of sending, to the
#      sender, rather than discovered by a reader an hour later.
#   2. `record` DERIVES the #645 verdict-ledger entry from the parsed GATE
#      token instead of accepting a hand-written one. A gate therefore cannot be
#      RECORDED as judged without a parseable verdict, and since
#      flow-wave-plan.py exits 4 on an unsuperseded hold, an unparseable verdict
#      changes PLANNER BEHAVIOUR - not merely a log line.
#
# Neither alone is enough: (1) without (2) leaves the token decorative the moment
# somebody writes the ledger by hand; (2) without (1) catches only gate verdicts
# and lets every lane grant and merge authorisation stay prose.
#
# ---- The vocabulary ---------------------------------------------------------
#
# Reserved lines are LINE-ANCHORED (the token begins the line, leading
# whitespace allowed) - the same rule the #607 edge grammar uses, so a mention
# inside a sentence can never be mistaken for a declaration.
#
#   GATE: GO #N [reason]
#   GATE: HOLD #N behind #M[, #M...] [reason]
#   GATE: GO-WITH-CONDITIONS #N
#     - <condition>                     (>=1 required; list items)
#     serializes: <marker>              (optional; unions into the ledger's
#                                        adds_serialized, the two-`0009`s fix)
#   LANE: GRANT|EXTEND <role> <path> [<path>...]
#   LANE: REVOKE <role> [<path>...]
#   MERGE: AUTHORIZED #N when <predicate>
#   STATE: as-of <commit-ish>
#   RATIFY #N <reason>
#   OVERRULE #N <reason>
#   PUSHBACK <argument>
#   LEDGER                              (block carrying delivered:/in-scope:/
#                                        residual:)
#
# Each requirement traces to a specific failure, and is enforced rather than
# recommended:
#
#   - a GATE verdict must NAME ITS SUBJECT (`#N`). A verdict whose subject is
#     implied by conversational context is exactly what goes stale between
#     composition and reading.
#   - a HOLD must name what it waits BEHIND, because wave.md requires it and a
#     hold with no blocker cannot be superseded on evidence.
#   - GO-WITH-CONDITIONS must carry conditions. A conditional approval with the
#     conditions left in the paragraph below is the crossed lane/gate message.
#   - a MERGE authorisation must name its PREDICATE, and a vague one is refused
#     (see VAGUE_PREDICATES): the reference run needed
#     `ci/woodpecker/pr/woodpecker` specifically, to distinguish the PR pipeline
#     from the push pipeline. "when CI passes" is the failure, not the fix.
#   - a STATE assertion must carry `as-of <commit>`. All four stale broadcasts
#     were true when written; the stamp converts silent staleness into visible
#     staleness.
#   - RATIFY/OVERRULE must name the issue and a reason - a ratification with no
#     recorded reason is indistinguishable from not having noticed.
#   - PUSHBACK must carry an argument, so it cannot be skimmed past as
#     agreement.
#   - LEDGER must carry all three sections. This is the one structured element
#     that ALREADY worked in the reference wave, formalised rather than invented.
#
# The vague-predicate list is a FLOOR for the shape that has actually failed, not
# proof of total coverage - the same honesty `check-test-binary-guards.py` states
# about its own static walk. A determined author can still write a useless
# predicate; the point is that the ones observed in the field are refused.
#
# Usage:
#   flow-wave-lexicon.sh validate [--body-file F | --body TEXT | < stdin]
#   flow-wave-lexicon.sh record --wave W [--body-file F | --body TEXT | < stdin]
#                               [--ledger FILE] [--dry-run]
#
#   validate  Parse the message. Print one FLOW_LEXICON_TRANSITION= line per
#             recognized token, then the verdict. A malformed reserved token is
#             reported with its line number and reason, and REFUSES (exit 1).
#             A message with NO reserved token is `none` and exits 0.
#   record    validate, then append a ledger entry DERIVED from each GATE token
#             to the wave's #645 verdict ledger
#             ($XDG_RUNTIME_DIR/cc-flow-wave/<wave>/verdicts.json), tmp+rename
#             under flock. A body carrying no GATE token is `none` and exits 1:
#             the caller asked to record a judgment and there was none to parse,
#             which is the refusal this verb exists for.
#
# Output ends with a machine-readable verdict line:
#   FLOW_LEXICON: ok | invalid | none | recorded | error
# preceded by FLOW_LEXICON_*= detail lines ('-' when not applicable).
#
# Exit codes: 0 normal, 1 invalid (or nothing to record), 2 usage error,
# 3 lock/IO failure.
#
# Env (test hooks - unset in normal use):
#   FLOW_WAVE_LEXICON_DIR   wave-root override (most precise)
#   FLOW_WAVE_MAILBOX_DIR   shared wave-root override, honored so the lexicon,
#                           the #676 mailbox and the #638 registry co-locate
#   FLOW_WAVE_REGISTRY_DIR  same, lowest precedence of the three
#   FLOW_WAVE_NOW           override the entry timestamp (epoch seconds)

set -uo pipefail

UID_NUM="$(id -u)"
WAVE_ROOT="${FLOW_WAVE_LEXICON_DIR:-${FLOW_WAVE_MAILBOX_DIR:-${FLOW_WAVE_REGISTRY_DIR:-${XDG_RUNTIME_DIR:-/run/user/$UID_NUM}/cc-flow-wave}}}"

# Predicates observed carrying no information in the reference wave. A merge
# authorisation naming one of these is refused: the whole point of the token is
# that the reader learns WHICH check, and "CI" does not distinguish the PR
# pipeline from the push pipeline.
VAGUE_PREDICATES="ci|ci passes|ci is green|ci green|green|it passes|it is green|checks pass|checks are green|the checks pass|tests pass|tests are green|the tests pass|build passes|everything passes|all green|passing"

usage_fail() { echo "flow-wave-lexicon: $1" >&2; exit 2; }

emit() {
  echo "FLOW_LEXICON_WAVE=${E_WAVE:--}"
  echo "FLOW_LEXICON_TRANSITIONS=${E_COUNT:--}"
  echo "FLOW_LEXICON_GATES=${E_GATES:--}"
  echo "FLOW_LEXICON_ERRORS=${E_ERRORS:--}"
  echo "FLOW_LEXICON_RECORDED=${E_RECORDED:--}"
  echo "FLOW_LEXICON_LEDGER=${E_LEDGER:--}"
  echo "FLOW_LEXICON: $1"
}

# Wave and role names become path components in the sibling helpers, so they are
# validated rather than quoted-and-hoped (the #676 rule, kept identical).
valid_name() {
  case "$1" in
    '') return 1 ;;
    .*) return 1 ;;
    *[!A-Za-z0-9_.-]*) return 1 ;;
    *) return 0 ;;
  esac
}

trim() { # trim STRING -> leading/trailing whitespace removed
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# ---- parse ------------------------------------------------------------------
#
# Populates the parallel arrays TR_KIND/TR_DETAIL (recognized transitions) and
# ERR_LINE/ERR_MSG (malformed reserved lines), plus the GATE_* arrays `record`
# consumes. Reads BODY_LINES, set by read_body.
#
# Continuation lines (conditions, ledger sections, a PUSHBACK argument on the
# following line) belong to the most recent reserved token and end at the next
# reserved line or EOF - so a block is bounded without needing a terminator
# nobody would remember to type.

declare -a BODY_LINES=()
declare -a TR_KIND=() TR_DETAIL=()
declare -a ERR_LINE=() ERR_MSG=()
declare -a GATE_ISSUE=() GATE_RULING=() GATE_BEHIND=() GATE_REASON=() GATE_SERIAL=()

read_body() {
  local raw
  if [ -n "$A_BODY_FILE" ]; then
    [ -r "$A_BODY_FILE" ] || usage_fail "cannot read --body-file: $A_BODY_FILE"
    raw="$(cat "$A_BODY_FILE")"
  elif [ -n "$A_BODY" ]; then
    raw="$A_BODY"
  elif [ ! -t 0 ]; then
    raw="$(cat)"
  else
    usage_fail "needs a body: --body TEXT, --body-file FILE, or stdin"
  fi
  # `IFS=` read -r line: whole lines, no word-splitting and no empty-field
  # collapse (#698/#700 - the shell IFS hazard this repo has now hit twice).
  while IFS= read -r line || [ -n "$line" ]; do
    BODY_LINES+=("$line")
  done <<EOF
$raw
EOF
}

# is_reserved LINE -> 0 when the line OPENS a reserved token (line-anchored).
is_reserved() {
  local s
  s="$(trim "$1")"
  case "$s" in
    GATE:*|LANE:*|MERGE:*|STATE:*) return 0 ;;
    RATIFY|RATIFY\ *|OVERRULE|OVERRULE\ *) return 0 ;;
    PUSHBACK|PUSHBACK\ *|PUSHBACK:*) return 0 ;;
    LEDGER|LEDGER\ *|LEDGER:*) return 0 ;;
    *) return 1 ;;
  esac
}

add_err() { ERR_LINE+=("$1"); ERR_MSG+=("$2"); }
add_tr()  { TR_KIND+=("$1"); TR_DETAIL+=("$2"); }

# block_lines START -> echoes the continuation lines after index START, stopping
# at the next reserved line or EOF.
block_lines() {
  local i="$1" n="${#BODY_LINES[@]}"
  while [ "$i" -lt "$n" ]; do
    if is_reserved "${BODY_LINES[$i]}"; then break; fi
    printf '%s\n' "${BODY_LINES[$i]}"
    i=$((i + 1))
  done
}

parse_gate() { # parse_gate LINENO REST BLOCK_START
  local ln="$1" rest="$2" start="$3"
  local verb args issue behind reason serial conds block
  rest="$(trim "$rest")"
  verb="${rest%%[[:space:]]*}"
  args="$(trim "${rest#"$verb"}")"

  case "$verb" in
    GO|HOLD|GO-WITH-CONDITIONS) : ;;
    '') add_err "$ln" "GATE: needs a verdict - GO, HOLD or GO-WITH-CONDITIONS"; return ;;
    *)  add_err "$ln" "unknown GATE verdict '$verb' (expected GO, HOLD or GO-WITH-CONDITIONS)"; return ;;
  esac

  # Subject: a verdict that does not name what it judges is the staleness bug.
  if [[ ! "$args" =~ ^#([0-9]+)([[:space:]]|$) ]]; then
    add_err "$ln" "GATE: $verb must name its subject issue (e.g. 'GATE: $verb #701')"
    return
  fi
  issue="${BASH_REMATCH[1]}"
  args="$(trim "${args#"#$issue"}")"

  behind=""
  if [[ "$args" =~ ^behind[[:space:]]+(#[0-9]+([[:space:],]+#[0-9]+)*) ]]; then
    behind="$(printf '%s' "${BASH_REMATCH[1]}" | tr -cd '0-9,# ' | tr ',' ' ' | tr -s ' ')"
    behind="$(printf '%s' "$behind" | tr -d '#')"
    args="$(trim "${args#behind*"${BASH_REMATCH[1]}"}")"
  fi

  if [ "$verb" = "HOLD" ] && [ -z "$behind" ]; then
    add_err "$ln" "GATE: HOLD #$issue must name what it waits behind (e.g. 'behind #56')"
    return
  fi

  block="$(block_lines "$start")"
  conds="$(printf '%s\n' "$block" | sed -n 's/^[[:space:]]*[-*][[:space:]]\{1,\}\(.*\)$/\1/p;s/^[[:space:]]*[0-9]\{1,\}\.[[:space:]]\{1,\}\(.*\)$/\1/p')"
  serial="$(printf '%s\n' "$block" | sed -n 's/^[[:space:]]*[Ss]erializes:[[:space:]]*\(.*\)$/\1/p' | head -1)"
  serial="$(trim "$serial")"

  if [ "$verb" = "GO-WITH-CONDITIONS" ] && [ -z "$(trim "$conds")" ]; then
    add_err "$ln" "GATE: GO-WITH-CONDITIONS #$issue carries no conditions - list them as '- <condition>' lines beneath it"
    return
  fi

  reason="$(trim "$args")"
  if [ -n "$(trim "$conds")" ]; then
    # Conditions ARE the reason for a conditional approval; joining them keeps
    # the ledger entry self-describing to a successor orchestrator.
    reason="$(printf '%s' "$conds" | paste -sd';' - | sed 's/;/; /g')"
    reason="$(trim "$reason")"
  fi
  [ -n "$reason" ] || reason="GATE: $verb (no reason given)"

  case "$verb" in
    GO)                 GATE_RULING+=("approved") ;;
    HOLD)               GATE_RULING+=("hold") ;;
    GO-WITH-CONDITIONS) GATE_RULING+=("approved-with-conditions") ;;
  esac
  GATE_ISSUE+=("$issue"); GATE_BEHIND+=("$behind")
  GATE_REASON+=("$reason"); GATE_SERIAL+=("$serial")
  add_tr "GATE" "$verb #$issue"
}

parse_lane() { # parse_lane LINENO REST
  local ln="$1" rest="$2" verb args role paths
  rest="$(trim "$rest")"
  verb="${rest%%[[:space:]]*}"
  args="$(trim "${rest#"$verb"}")"

  case "$verb" in
    GRANT|EXTEND|REVOKE) : ;;
    '') add_err "$ln" "LANE: needs a verb - GRANT, EXTEND or REVOKE"; return ;;
    *)  add_err "$ln" "unknown LANE verb '$verb' (expected GRANT, EXTEND or REVOKE)"; return ;;
  esac

  role="${args%%[[:space:]]*}"
  paths="$(trim "${args#"$role"}")"
  if [ -z "$role" ] || ! valid_name "$role"; then
    add_err "$ln" "LANE: $verb must name the role it applies to (e.g. 'LANE: $verb worker-a src/cli.py')"
    return
  fi
  # A grant with no paths is the lane-fence-read-as-grant failure: it says WHO
  # without saying WHAT, which is where "explicitly NOT yours" got inverted.
  if [ "$verb" != "REVOKE" ] && [ -z "$paths" ]; then
    add_err "$ln" "LANE: $verb $role names no paths - a lane grant must say WHICH files, or it can be read as its own inverse"
    return
  fi
  add_tr "LANE" "$verb $role${paths:+ $paths}"
}

parse_merge() { # parse_merge LINENO REST
  local ln="$1" rest="$2" verb args issue pred
  rest="$(trim "$rest")"
  verb="${rest%%[[:space:]]*}"
  args="$(trim "${rest#"$verb"}")"

  if [ "$verb" != "AUTHORIZED" ]; then
    add_err "$ln" "unknown MERGE verb '${verb:-<empty>}' (the only merge transition is AUTHORIZED)"
    return
  fi
  if [[ ! "$args" =~ ^#([0-9]+)([[:space:]]|$) ]]; then
    add_err "$ln" "MERGE: AUTHORIZED must name the issue or PR it authorizes (e.g. 'MERGE: AUTHORIZED #701 when ci/woodpecker/pr/woodpecker reports success')"
    return
  fi
  issue="${BASH_REMATCH[1]}"
  args="$(trim "${args#"#$issue"}")"

  if [[ ! "$args" =~ ^when[[:space:]]+(.+)$ ]]; then
    add_err "$ln" "MERGE: AUTHORIZED #$issue must state its predicate as 'when <named check>'"
    return
  fi
  pred="$(trim "${BASH_REMATCH[1]}")"
  # Strip a trailing clause so "when X reports success, on fail STOP" is judged
  # on X rather than on the whole sentence.
  pred="${pred%%,*}"
  pred="$(trim "$pred")"
  local bare
  bare="$(lower "$pred")"
  bare="${bare% reports success}"; bare="${bare% reports pass}"
  bare="${bare% is green}"; bare="${bare% passes}"
  bare="$(trim "$bare")"
  if [ -z "$bare" ] || printf '%s' "$bare" | grep -Eqx "$VAGUE_PREDICATES"; then
    add_err "$ln" "MERGE: AUTHORIZED #$issue names a vague predicate ('$pred') - name the CHECK (e.g. 'ci/woodpecker/pr/woodpecker'), since 'CI' does not distinguish the PR pipeline from the push pipeline"
    return
  fi
  add_tr "MERGE" "AUTHORIZED #$issue when $pred"
}

parse_state() { # parse_state LINENO REST
  local ln="$1" rest="$2" commit
  rest="$(trim "$rest")"
  if [[ ! "$rest" =~ ^as-of[[:space:]]+([0-9a-fA-F]{7,40})([[:space:]]|$) ]]; then
    add_err "$ln" "STATE: must carry 'as-of <commit>' with a 7-40 character commit sha - an unstamped state assertion is true when composed and silently wrong when read"
    return
  fi
  commit="${BASH_REMATCH[1]}"
  add_tr "STATE" "as-of $commit"
}

parse_ruling() { # parse_ruling LINENO TOKEN REST
  local ln="$1" tok="$2" rest="$3" issue reason
  rest="$(trim "$rest")"
  if [[ ! "$rest" =~ ^#([0-9]+)([[:space:]]|$) ]]; then
    add_err "$ln" "$tok must name the issue whose deviation it answers (e.g. '$tok #701 narrower boundary accepted')"
    return
  fi
  issue="${BASH_REMATCH[1]}"
  reason="$(trim "${rest#"#$issue"}")"
  if [ -z "$reason" ]; then
    add_err "$ln" "$tok #$issue carries no reason - a ruling with no recorded reason is indistinguishable from not having noticed"
    return
  fi
  add_tr "$tok" "#$issue $reason"
}

parse_pushback() { # parse_pushback LINENO REST BLOCK_START
  local ln="$1" rest="$2" start="$3" block
  rest="$(trim "${rest#:}")"
  block="$(trim "$(block_lines "$start")")"
  if [ -z "$rest" ] && [ -z "$block" ]; then
    add_err "$ln" "PUSHBACK carries no argument - the token exists so a refutation cannot be skimmed past as agreement"
    return
  fi
  add_tr "PUSHBACK" "${rest:-${block%%$'\n'*}}"
}

parse_ledger() { # parse_ledger LINENO BLOCK_START
  local ln="$1" start="$2" block missing=""
  block="$(lower "$(block_lines "$start")")"
  local sect
  for sect in delivered in-scope residual; do
    printf '%s\n' "$block" | grep -Eq "^[[:space:]]*[-*]?[[:space:]]*$sect[[:space:]]*:" || missing="$missing $sect"
  done
  missing="$(trim "$missing")"
  if [ -n "$missing" ]; then
    add_err "$ln" "LEDGER is missing section(s): ${missing// /, } - the delivered/in-scope/residual shape is the one structured element that did not drift, so it is required rather than suggested"
    return
  fi
  add_tr "LEDGER" "delivered/in-scope/residual"
}

parse_body() {
  local i=0 n="${#BODY_LINES[@]}" line s ln
  while [ "$i" -lt "$n" ]; do
    line="${BODY_LINES[$i]}"
    s="$(trim "$line")"
    ln=$((i + 1))
    case "$s" in
      GATE:*)     parse_gate    "$ln" "${s#GATE:}"  "$((i + 1))" ;;
      LANE:*)     parse_lane    "$ln" "${s#LANE:}" ;;
      MERGE:*)    parse_merge   "$ln" "${s#MERGE:}" ;;
      STATE:*)    parse_state   "$ln" "${s#STATE:}" ;;
      RATIFY|RATIFY\ *)     parse_ruling "$ln" "RATIFY"   "${s#RATIFY}" ;;
      OVERRULE|OVERRULE\ *) parse_ruling "$ln" "OVERRULE" "${s#OVERRULE}" ;;
      PUSHBACK|PUSHBACK\ *|PUSHBACK:*) parse_pushback "$ln" "${s#PUSHBACK}" "$((i + 1))" ;;
      LEDGER|LEDGER\ *|LEDGER:*)       parse_ledger   "$ln" "$((i + 1))" ;;
    esac
    i=$((i + 1))
  done
}

report_parse() {
  local i
  for i in "${!TR_KIND[@]}"; do
    echo "FLOW_LEXICON_TRANSITION=${TR_KIND[$i]}: ${TR_DETAIL[$i]}"
  done
  for i in "${!ERR_LINE[@]}"; do
    echo "flow-wave-lexicon: line ${ERR_LINE[$i]}: ${ERR_MSG[$i]}" >&2
  done
  E_COUNT="${#TR_KIND[@]}"
  E_GATES="${#GATE_ISSUE[@]}"
  E_ERRORS="${#ERR_LINE[@]}"
}

# ---- arg parsing ------------------------------------------------------------

VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-wave-lexicon.sh validate|record ..."
shift

case "$VERB" in
  validate | record) : ;;
  --help | -h)
    # Print the whole header rather than a hand-counted range: a fixed `sed
    # 2,NNp` silently truncates mid-sentence as the header grows (#686).
    sed -n '2,${/^[^#]/q;p;}' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB" ;;
esac

WAVE="default"; A_BODY=""; A_BODY_FILE=""; A_LEDGER=""; DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wave) [ "$#" -ge 2 ] || usage_fail "--wave requires a name"; WAVE="$2"; shift ;;
    --wave=*) WAVE="${1#--wave=}" ;;
    --body) [ "$#" -ge 2 ] || usage_fail "--body requires text"; A_BODY="$2"; shift ;;
    --body=*) A_BODY="${1#--body=}" ;;
    --body-file) [ "$#" -ge 2 ] || usage_fail "--body-file requires a path"; A_BODY_FILE="$2"; shift ;;
    --body-file=*) A_BODY_FILE="${1#--body-file=}" ;;
    --ledger) [ "$#" -ge 2 ] || usage_fail "--ledger requires a path"; A_LEDGER="$2"; shift ;;
    --ledger=*) A_LEDGER="${1#--ledger=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --*) usage_fail "unknown option: $1" ;;
    *) usage_fail "unexpected argument: $1" ;;
  esac
  shift
done

valid_name "$WAVE" || usage_fail "invalid wave name: '$WAVE' (letters, digits, '_', '.', '-'; no leading dot)"

E_WAVE="$WAVE"; E_COUNT=""; E_GATES=""; E_ERRORS=""; E_RECORDED=""; E_LEDGER=""

read_body
parse_body

case "$VERB" in
  validate)
    report_parse
    if [ "${#ERR_LINE[@]}" -gt 0 ]; then
      emit invalid
      exit 1
    fi
    if [ "${#TR_KIND[@]}" -eq 0 ]; then
      # Absence is never an error: prose carries the argument, and most messages
      # in a healthy wave declare no transition at all.
      emit none
      exit 0
    fi
    emit ok
    exit 0
    ;;

  record)
    report_parse
    if [ "${#ERR_LINE[@]}" -gt 0 ]; then
      emit invalid
      exit 1
    fi
    if [ "${#GATE_ISSUE[@]}" -eq 0 ]; then
      echo "flow-wave-lexicon: no parseable GATE verdict in this message - a gate cannot be recorded as judged without one (issue #701)" >&2
      emit none
      exit 1
    fi

    WAVE_DIR="$WAVE_ROOT/$WAVE"
    LEDGER="${A_LEDGER:-$WAVE_DIR/verdicts.json}"
    E_LEDGER="$LEDGER"
    if [ "$DRY_RUN" -eq 1 ]; then
      E_RECORDED=0
      emit recorded
      exit 0
    fi

    mkdir -p "$(dirname "$LEDGER")" 2>/dev/null || { emit error; exit 3; }
    command -v jq >/dev/null 2>&1 || { echo "flow-wave-lexicon: jq is required to write the ledger" >&2; emit error; exit 3; }

    TS="$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)"
    [ -z "${FLOW_WAVE_NOW:-}" ] || TS="$(date -Iseconds -d "@$FLOW_WAVE_NOW" 2>/dev/null || echo "$TS")"

    # Entries are APPENDED, never rewritten: #645's ledger is last-entry-wins, so
    # overriding a ruling has to remain a recorded act with its own reason rather
    # than a silent contradiction.
    OUT="$(
      (
        flock -w 10 9 || { echo "flow-wave-lexicon: could not lock $LEDGER" >&2; exit 3; }
        if [ -s "$LEDGER" ]; then
          jq -e 'type == "array"' "$LEDGER" >/dev/null 2>&1 || {
            echo "flow-wave-lexicon: $LEDGER is not a JSON array of ruling entries" >&2
            exit 3
          }
          cur="$(cat "$LEDGER")"
        else
          cur='[]'
        fi
        n=0
        for i in "${!GATE_ISSUE[@]}"; do
          behind_json='[]'
          if [ -n "${GATE_BEHIND[$i]}" ]; then
            behind_json="$(printf '%s' "${GATE_BEHIND[$i]}" | tr ' ' '\n' | grep -E '^[0-9]+$' | jq -sc 'map(tonumber)')"
          fi
          serial_json='[]'
          if [ -n "${GATE_SERIAL[$i]}" ]; then
            serial_json="$(jq -nc --arg m "${GATE_SERIAL[$i]}" '[$m]')"
          fi
          cur="$(printf '%s' "$cur" | jq -c \
            --argjson issue "${GATE_ISSUE[$i]}" \
            --arg ruling "${GATE_RULING[$i]}" \
            --argjson behind "$behind_json" \
            --argjson serial "$serial_json" \
            --arg reason "${GATE_REASON[$i]}" \
            --arg ts "$TS" \
            '. + [ ({issue: $issue, ruling: $ruling, reason: $reason, ts: $ts}
                    + (if ($behind | length) > 0 then {holds_behind: $behind} else {} end)
                    + (if ($serial | length) > 0 then {adds_serialized: $serial} else {} end)) ]')" || exit 3
          n=$((n + 1))
        done
        tmp="$(mktemp "$(dirname "$LEDGER")/.verdicts.XXXXXX")" || exit 3
        printf '%s\n' "$cur" > "$tmp" || { rm -f "$tmp"; exit 3; }
        mv -f "$tmp" "$LEDGER" || { rm -f "$tmp"; exit 3; }
        echo "$n"
      ) 9>"$LEDGER.lock"
    )"
    RC=$?
    if [ "$RC" -ne 0 ] || [ -z "$OUT" ]; then
      emit error
      exit 3
    fi
    E_RECORDED="$OUT"
    echo "flow-wave-lexicon: recorded $OUT gate ruling(s) to $LEDGER - flow-wave-plan.py --verdicts reads them on the next re-plan." >&2
    emit recorded
    exit 0
    ;;
esac
