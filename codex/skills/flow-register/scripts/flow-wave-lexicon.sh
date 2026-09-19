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
# Reserved lines are LINE-ANCHORED (the token begins the line) - the same rule
# the #607 edge grammar uses, so a mention inside a sentence can never be
# mistaken for a declaration.
#
# ---- Citation: a reference to a transition is not a transition (issue #980) --
#
# The scan originally trimmed each line and then matched, so a token QUOTED in
# prose was indistinguishable from one ISSUED. That made the channel unable to
# express the thing an authority channel most needs to express: a reference to a
# past transition that is not itself a transition. Retracting a bad gate,
# teaching from a prior ruling, or quoting a worker's token back to them in
# order to correct it all RE-ISSUED it - and a re-issued `GATE: HOLD` blocks the
# planner on a phantom hold whose stated reason is the quoted text, which reads
# as authentic to whoever investigates. The specimen: a draft written to WITHDRAW
# a merge authorisation, quoting the bad line indented two spaces, parsed as a
# fresh `MERGE: AUTHORIZED #243` under the exact predicate being withdrawn.
#
# Four contexts, three dispositions. The default is unchanged - a token is a
# transition - and quoting is the thing that must be spelled out:
#
#   at column 0, outside a fence   -> ISSUED. Unchanged.
#   inside a ``` or ~~~ fence      -> CITED: inert, and REPORTED.
#   behind a `>` blockquote prefix -> CITED: inert, and REPORTED.
#   indented, no fence, no `>`     -> REFUSED, naming both remedies.
#
# WHY THE INDENTED CASE REFUSES RATHER THAN PICKING A SIDE. It is the only
# genuinely ambiguous shape, and both silent readings are wrong: reading it as
# issued is the defect above, and reading it as cited silently DROPS a real
# transition typed with a stray leading space - which fails open, the worse
# direction, because a dropped `GATE: HOLD` lets a wave start an issue somebody
# is holding. A refusal is the only disposition that cannot fail open in either
# direction, and it is the one that TEACHES: the orchestrator who hit this did
# not know a citation marker existed, so an escape alone would not have saved
# them. Refusal names both remedies at the moment they are needed.
#
# WHY A SKIP IS NOT SILENCE. Every inert token is reported -
# `FLOW_LEXICON_CITATIONS=<n>` plus one `FLOW_LEXICON_CITATION=` line per token,
# with its line number and context - and `flow-wave-mailbox.sh send` prints them
# to the sender on the DELIVERING path, not only on a refusal. So a `GATE: HOLD`
# you fenced but meant to issue is named back at you at send time. Without that
# report the skip would be exactly the fail-open it exists to avoid.
#
# A `>` prefix already failed to parse before #980 - `trim` leaves the `>` in
# place, so the `GATE:*` match missed. That was accidental, undocumented and
# unreported; this makes it a declared escape that says what it did.
#
# REVERSAL TRIGGER (issue #936 / ADR 0009, committed here rather than left to a
# later judgement): this is a two-sided change, and the other side's pain is a
# DROPPED transition. If a wave ever loses a real transition because its author
# fenced or blockquoted a line they meant to issue, AND the
# `FLOW_LEXICON_CITATION=` report did not stop them, then the skip is too wide -
# move the fenced and quoted contexts to REFUSE as well, joining the indented
# case, leaving column 0 as the only way to say anything at all. The report is
# the mitigation, so its failure is the trigger; do not widen the skip further
# without retiring this note and saying why.
#
#   GATE: GO #N [reason]
#   GATE: HOLD #N behind #M[, #M...] [reason]
#   GATE: GO-WITH-CONDITIONS #N
#     - <condition>                     (>=1 required; list items)
#     serializes: <marker>              (optional; unions into the ledger's
#                                        adds_serialized, the two-`0009`s fix)
#   LANE: GRANT|SET <role> <path> [<path>...]   (REPLACES the role's lane)
#   LANE: REVOKE <role> [<path>...]
#   MERGE: AUTHORIZED #N when <predicate>
#   MERGE: PRIORITY #N <argument>
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
#             recognized token and one FLOW_LEXICON_CITATION= line per token
#             read as a CITATION (#980), then the verdict. A malformed reserved
#             token is reported with its line number and reason, and REFUSES
#             (exit 1); so is an INDENTED one, which is ambiguous rather than
#             malformed and is refused for that reason. A message with NO
#             reserved token is `none` and exits 0 - and so is one carrying only
#             citations, since a citation declares no transition.
#   record    validate, then append a ledger entry DERIVED from each GATE token
#             to the wave's #645 verdict ledger
#             ($XDG_RUNTIME_DIR/cc-flow-wave/<wave>/verdicts.json), tmp+rename
#             under flock. A body carrying no GATE token is `none` and exits 1:
#             the caller asked to record a judgment and there was none to parse,
#             which is the refusal this verb exists for.
#
# Output ends with a machine-readable verdict line:
#   FLOW_LEXICON: ok | invalid | none | recorded | error
# preceded by FLOW_LEXICON_*= detail lines ('-' when not applicable), including
# FLOW_LEXICON_CITATIONS=<n> - the count of tokens read as citations rather than
# transitions. A non-zero count on a message you MEANT to carry a transition is
# the signal that it was fenced or quoted; read the FLOW_LEXICON_CITATION= lines
# above it, which name each one's line number and context.
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

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "FLOW_LEXICON_EXIT=%d\n" "$?" >&2' EXIT

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
  echo "FLOW_LEXICON_CITATIONS=${E_CITED:--}"
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
declare -a LINE_CLASS=()
declare -a TR_KIND=() TR_DETAIL=()
declare -a ERR_LINE=() ERR_MSG=()
declare -a CITE_LINE=() CITE_CTX=() CITE_TEXT=()
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

# reserved_kind STRING -> echoes the reserved token a already-trimmed STRING
# opens ('' when it opens none). The single home of the vocabulary's spelling:
# classification, dispatch and block termination all read it, so a token added
# in one place cannot be missed by the other two.
reserved_kind() {
  case "$1" in
    GATE:*)    printf 'GATE' ;;
    LANE:*)    printf 'LANE' ;;
    MERGE:*)   printf 'MERGE' ;;
    STATE:*)   printf 'STATE' ;;
    RATIFY|RATIFY\ *)     printf 'RATIFY' ;;
    OVERRULE|OVERRULE\ *) printf 'OVERRULE' ;;
    PUSHBACK|PUSHBACK\ *|PUSHBACK:*) printf 'PUSHBACK' ;;
    LEDGER|LEDGER\ *|LEDGER:*)       printf 'LEDGER' ;;
    *) printf '' ;;
  esac
}

# fence_scan STRING -> echoes "<char> <runlen> <rest>" when an already-trimmed
# STRING opens with a run of three or more backticks or tildes; '' otherwise.
#
# The RUN LENGTH is carried, not just the character. A fence is closed only by a
# run of the SAME character at least as long as the one that opened it, followed
# by nothing but whitespace - the CommonMark rule, and it is load-bearing here
# rather than pedantry. Comparing only the character (the first cut of #980)
# meant a four-backtick block containing a three-backtick example closed one
# line early, and any ```` ```bash ```` info line inside a block closed it -
# after which the next reserved token was live again. Both re-create the exact
# phantom-verdict defect this change exists to remove, inside a message whose
# author can see the token is plainly fenced.
fence_scan() {
  local s="$1" ch run rest
  case "$s" in
    '```'*) ch='`' ;;
    '~~~'*) ch='~' ;;
    *) printf ''; return ;;
  esac
  run=0
  while [ "${s:$run:1}" = "$ch" ]; do run=$((run + 1)); done
  rest="${s:$run}"
  printf '%s %s %s' "$ch" "$run" "$rest"
}

# has_quote STRING -> 0 when an already-trimmed STRING carries a blockquote
# marker, REGARDLESS of whether anything follows it.
#
# Separate from strip_quote because that function cannot tell an EMPTY
# blockquote from an unquoted line - both strip to '' - so a bare `>` fell
# through to live content. `PUSHBACK` then accepted a message whose only
# "argument" was the quote marker itself, which is precisely the
# skimmed-past-as-agreement failure the mandatory argument exists to prevent.
# The prefix is a property of the LINE; the payload is a separate question.
has_quote() {
  case "$1" in
    '>'*) return 0 ;;
    *) return 1 ;;
  esac
}

# strip_quote STRING -> echoes an already-trimmed STRING with any leading
# markdown blockquote markers removed ('> ', '>>', '> > '). Nested quoting is
# stripped too: a quote of a quote is still a quote. Ask has_quote whether there
# was a prefix at all - an empty result here is ambiguous by construction.
strip_quote() {
  local s="$1"
  while :; do
    case "$s" in
      '>'*) s="$(trim "${s#>}")" ;;
      *) break ;;
    esac
  done
  printf '%s' "$s"
}

# fence_indent_ok LINE -> 0 when the RAW line's indentation permits it to be a
# fence delimiter at all: at most three spaces, and no tab (CommonMark).
#
# Checked on the raw line because fence_scan sees a TRIMMED one, and trimming is
# what made this class of bug possible in the first place. A delimiter indented
# four or more spaces is CONTENT, not a fence: accepting it as a closer ended the
# block early and the next reserved token went live again - reported as a real
# verdict with zero citations, inside a message whose author can see the token is
# plainly fenced. That is the phantom verdict this whole change removes, restored
# by an incomplete repair of it.
fence_indent_ok() {
  local indent="${1%%[![:space:]]*}"
  case "$indent" in
    *"$(printf '\t')"*) return 1 ;;
  esac
  [ "${#indent}" -le 3 ]
}

# classify_lines -> fills LINE_CLASS, one entry per BODY_LINES entry (issue #980):
#
#   issue      a reserved token at column 0, outside a fence: a TRANSITION.
#   cite-fence a reserved token inside a ``` or ~~~ fence: inert, reported.
#   cite-quote a reserved token behind a `>` prefix: inert, reported.
#   ambiguous  a reserved token INDENTED with no fence and no `>`: refused.
#   fenced     any other line inside a fence, its delimiters included: INERT
#              CONTENT - skipped by block_lines, never a live condition.
#   quoted     any other line behind a `>` prefix: inert content, likewise.
#   plain      everything else: live content.
#
# Computed in ONE pass, ahead of parsing, because three readers have to agree
# about it: parse_body dispatches on it, block_lines decides continuation from
# it, and the citation report is derived from it. Recomputing the context per
# reader is how a block ends up reading content the dispatcher had already
# decided was a specimen.
#
# WHY `fenced` AND `quoted` ARE THEIR OWN CLASSES RATHER THAN `plain`. The
# continuation grammar reads `- <condition>` and `serializes: <marker>` lines
# out of the block beneath a token, and those two lines change what lands in
# verdicts.json. Left as `plain`, a condition SHOWN inside a fence satisfies a
# live `GATE: GO-WITH-CONDITIONS`, and a `serializes:` shown there enters its
# `adds_serialized` - so a quoted example silently supplies the fields of a live
# ruling and the planner serialises on a marker nobody declared. Demonstrated on
# both halves of the distinction (a fenced condition, and a quoted one), which is
# why a fence and a blockquote get the same treatment.
classify_lines() {
  local i=0 n="${#BODY_LINES[@]}" line s scan ch run rest q
  local fence_ch="" fence_len=0
  while [ "$i" -lt "$n" ]; do
    line="${BODY_LINES[$i]}"
    s="$(trim "$line")"
    # A delimiter indented four or more spaces is CONTENT, never a fence, so the
    # raw line's indentation is consulted before its trimmed text is.
    if fence_indent_ok "$line"; then scan="$(fence_scan "$s")"; else scan=""; fi
    ch="${scan%% *}"; rest="${scan#* }"; run="${rest%% *}"; rest="${rest#* }"
    [ -n "$scan" ] || { ch=""; run=0; rest=""; }

    if [ -n "$fence_ch" ]; then
      # Inside a fence. It closes only on the SAME character, a run at least as
      # long as the opener's, and nothing but whitespace after it.
      if [ -n "$scan" ] && [ "$ch" = "$fence_ch" ] && [ "$run" -ge "$fence_len" ] && [ -z "$(trim "$rest")" ]; then
        fence_ch=""; fence_len=0
        LINE_CLASS+=("fenced")
      else
        # Strip a blockquote prefix BEFORE asking whether this is a token: a
        # quoted token shown inside a fence is still a reserved token, and
        # classifying it `fenced` would drop it from the citation report - a
        # reported zero that cannot tell "no citations here" from "a token I
        # silently skipped", which is the reporting the whole skip relies on.
        if has_quote "$s"; then q="$(strip_quote "$s")"; else q="$s"; fi
        if [ -n "$(reserved_kind "$q")" ]; then
          LINE_CLASS+=("cite-fence")
        else
          LINE_CLASS+=("fenced")
        fi
      fi
      i=$((i + 1)); continue
    fi

    # An opening backtick fence may carry an info string, but never a backtick
    # inside it (CommonMark); a tilde fence may carry anything.
    if [ -n "$scan" ] && { [ "$ch" = '~' ] || case "$rest" in *'`'*) false ;; *) true ;; esac; }; then
      # An UNTERMINATED opening fence runs to EOF, so every later token reads as
      # a citation. That is the fail-open direction in miniature - which is
      # exactly why each one is REPORTED: a stray ``` that silences the rest of
      # a message is visible in the sender's own output rather than inferred
      # from a transition that never arrived.
      fence_ch="$ch"; fence_len="$run"
      LINE_CLASS+=("fenced")
      i=$((i + 1)); continue
    fi

    # has_quote, not a non-empty strip: a bare `>` is a quoted EMPTY line, and
    # classifying it `plain` let it stand in for a live PUSHBACK argument.
    if has_quote "$s"; then
      q="$(strip_quote "$s")"
      if [ -n "$(reserved_kind "$q")" ]; then
        LINE_CLASS+=("cite-quote")
      else
        LINE_CLASS+=("quoted")
      fi
      i=$((i + 1)); continue
    fi

    if [ -n "$(reserved_kind "$s")" ]; then
      # Column 0 ISSUES; ANY leading whitespace is the ambiguous shape. Tested
      # on the RAW line, never the trimmed one - trimming first is precisely the
      # step that made a quoted token indistinguishable from an issued one.
      case "$line" in
        [[:space:]]*) LINE_CLASS+=("ambiguous") ;;
        *)            LINE_CLASS+=("issue") ;;
      esac
    else
      LINE_CLASS+=("plain")
    fi
    i=$((i + 1))
  done
}

add_err()  { ERR_LINE+=("$1"); ERR_MSG+=("$2"); }
add_tr()   { TR_KIND+=("$1"); TR_DETAIL+=("$2"); }
add_cite() { CITE_LINE+=("$1"); CITE_CTX+=("$2"); CITE_TEXT+=("$3"); }

# block_lines START -> echoes the LIVE continuation lines after index START,
# stopping at the next line that opens or purports to open a reserved token.
#
# Three rules, and each one is a measured defect rather than a preference
# (issue #980):
#
#   TERMINATE on issue|ambiguous|cite-fence|cite-quote. A CITATION ends the
#   block for the same reason an issued token does: the lines beneath a quoted
#   ruling belong to the quoted ruling. Letting a citation be transparent was
#   the first cut, and it recorded `GATE: GO #55 approved on its own merits`
#   with the reason and `adds_serialized` marker of a `GATE: GO-WITH-CONDITIONS
#   #60` quoted below it - a quoted ruling silently rewriting a live one, which
#   is the very class of defect this change repairs. Terminating restores the
#   pre-#980 behaviour for fences (a fenced token was "reserved" and stopped the
#   block) and moves blockquotes the same way.
#
#   SKIP fenced|quoted. These are inert CONTENT: a `- <condition>` shown inside
#   a fence must not satisfy a live GO-WITH-CONDITIONS, and a `serializes:`
#   shown there must not enter its ledger entry. Skipping rather than
#   terminating is deliberate - an illustrative block mid-message should not
#   truncate the conditions that follow it, which is the reading the closing
#   fence makes unambiguous.
#
#   EMIT plain. Live prose, live conditions, live sections.
#
# Every failure this arrangement can produce is LOUD: conditions that end up
# outside the block make a GO-WITH-CONDITIONS refuse for carrying none, and a
# refusal is correctable at the sender. The alternative failed silently, in the
# ledger, on a live ruling.
block_lines() {
  local i="$1" n="${#BODY_LINES[@]}"
  while [ "$i" -lt "$n" ]; do
    case "${LINE_CLASS[$i]:-plain}" in
      issue|ambiguous|cite-fence|cite-quote) break ;;
      fenced|quoted) i=$((i + 1)); continue ;;
    esac
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
    add_err "$ln" "GATE: GO-WITH-CONDITIONS #$issue carries no conditions - list them as '- <condition>' lines beneath it. Note that a fenced or '>' quoted line is INERT (issue #980): a condition shown inside a fence is a specimen, not a condition, and a quoted token ENDS the block, so conditions below one are read as belonging to what you quoted"
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
    GRANT|SET|REVOKE) : ;;
    #: `EXTEND` IS REFUSED BY NAME, not left to the unknown-verb arm (#1026).
    #:
    #: The registry's `--files` REPLACES a role's lane wholesale, so a role
    #: re-registered on an "EXTEND" loses every path the new list omits - at the
    #: moment it is most likely to have just merged the file. The token names the
    #: INVERSE of the mechanism, so a sender who reads it as written produces the
    #: opposite of what they intend. It fired twice in one day, the second time by
    #: an orchestrator who had reported the first occurrence two hours earlier.
    #:
    #: This is the treatment `MERGE: HOLD|BLOCK|FREEZE` already gets a few
    #: functions down, for the identical reason ("reads as its own inverse"), so
    #: the principle was already enforced one token over. An unknown-verb error
    #: would say `EXTEND` is not a verb; the sender's actual mistake is believing
    #: it does something, and only a message naming the mechanism corrects that.
    EXTEND)
      add_err "$ln" "LANE: EXTEND does not extend - the registry's --files REPLACES a role's lane wholesale, so re-registering on an 'EXTEND' DROPS every path the new list omits. Name the COMPLETE lane with 'LANE: SET <role> <every path it should still hold>' (GRANT is the same replace semantics under its established name)"
      return ;;
    '') add_err "$ln" "LANE: needs a verb - GRANT, SET or REVOKE"; return ;;
    *)  add_err "$ln" "unknown LANE verb '$verb' (expected GRANT, SET or REVOKE)"; return ;;
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

#: `MERGE: PRIORITY #N <argument>` - #N merges before every other open PR in the
#: wave (issue #989).
#:
#: WHY IT EXISTS. Under branch protection `strict: true` a PR must be up to date
#: with base to merge, so every merge invalidates every other open PR. `main` is
#: a serialized resource and the PR with the longest verify keeps losing its
#: place: #982 was overtaken four times in one wave, each time after a full green
#: run, burning four suite runs on rebases that changed not one line of its diff.
#: The remedy that worked was a merge hold declared in PROSE, which means it was
#: unvalidated, absent from `verdicts.json`, and invisible to the planner. This
#: is that remedy as a transition.
#:
#: WHY THE VERB IS `PRIORITY` AND NOT `HOLD`. #N must denote the same referent it
#: denotes in `MERGE: AUTHORIZED #N` - the thing being acted on favourably. Under
#: `HOLD` it would denote the single PR that is NOT held, so a competent reader
#: derives the exact inverse from the token alone. Rejected on the same grounds:
#: `BLOCK` and `FREEZE` (identical inversion), `EXCLUSIVE` (names the property
#: but not the beneficiary, so "#N merges exclusively" and "only #N may merge"
#: are both available readings), and enumerating the held set (`HOLD #990 #991
#: until #982`) which is correct but goes stale the moment another PR opens, so
#: the token would be wrong without anyone editing it.
#:
#: The ARGUMENT is mandatory for the same reason PUSHBACK's is: a scheduling
#: decision that preempts every other worker's merge should not be skimmable.
parse_merge_priority() { # parse_merge_priority LINENO ARGS
  local ln="$1" args="$2" issue why
  if [[ ! "$args" =~ ^#([0-9]+)([[:space:]]|$) ]]; then
    add_err "$ln" "MERGE: PRIORITY must name the PR that merges FIRST (e.g. 'MERGE: PRIORITY #982 overtaken four times, oldest PR in the wave')"
    return
  fi
  issue="${BASH_REMATCH[1]}"
  why="$(trim "${args#"#$issue"}")"
  if [ -z "$why" ]; then
    add_err "$ln" "MERGE: PRIORITY #$issue must state WHY it goes first - this preempts every other open PR in the wave, so the reason is the record"
    return
  fi
  add_tr "MERGE" "PRIORITY #$issue $why"
}

parse_merge() { # parse_merge LINENO REST
  local ln="$1" rest="$2" verb args issue pred
  rest="$(trim "$rest")"
  verb="${rest%%[[:space:]]*}"
  args="$(trim "${rest#"$verb"}")"

  case "$verb" in
    AUTHORIZED) : ;;
    PRIORITY)   parse_merge_priority "$ln" "$args"; return ;;
    HOLD|BLOCK|FREEZE)
      # Refused BY NAME rather than as an unknown verb, because each reads as
      # its own inverse: `MERGE: HOLD #982` parses as "hold #982" while the
      # declaration it is reaching for holds everything EXCEPT #982. This repo
      # has that specimen already - a lane fence written as "explicitly NOT
      # yours" was read as its own grant in the reference wave, which is why
      # `LANE: GRANT` must name the paths it GRANTS. #N denotes the same
      # referent under every MERGE verb: the thing being acted on favourably.
      add_err "$ln" "MERGE: $verb #N reads as its own inverse - it names the one PR that is NOT held. Use 'MERGE: PRIORITY #N <argument>', where #N is the PR that merges FIRST, the same referent as in MERGE: AUTHORIZED #N"
      return ;;
    *)
      add_err "$ln" "unknown MERGE verb '${verb:-<empty>}' (the merge transitions are AUTHORIZED and PRIORITY)"
      return ;;
  esac
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
    printf '%s\n' "$block" | grep -Eq "^[[:space:]]*[-*]?[[:space:]]*${sect}[[:space:]]*:" || missing="$missing $sect"
  done
  missing="$(trim "$missing")"
  if [ -n "$missing" ]; then
    add_err "$ln" "LEDGER is missing section(s): ${missing// /, } - the delivered/in-scope/residual shape is the one structured element that did not drift, so it is required rather than suggested"
    return
  fi
  add_tr "LEDGER" "delivered/in-scope/residual"
}

# parse_ambiguous LINENO KIND TEXT - the indented reserved token (issue #980).
#
# Refused rather than resolved, because both silent readings are wrong and the
# refusal is the only one that teaches. The message names BOTH remedies: the
# author of such a line has a definite intention, and which one it was is the
# single fact this parser cannot recover.
parse_ambiguous() {
  local ln="$1" kind="$2"
  add_err "$ln" "$kind is INDENTED, which is ambiguous - a reserved token at column 0 ISSUES the transition, so this one is refused rather than guessed (issue #980). To ISSUE it, remove the leading whitespace. To CITE it - quote a past ruling, or a token you are retracting, without re-performing it - prefix the line with '> ' or put it inside a fenced block; both are recorded as citations and reported, never as transitions"
}

parse_body() {
  local i=0 n="${#BODY_LINES[@]}" line s ln cls kind
  while [ "$i" -lt "$n" ]; do
    line="${BODY_LINES[$i]}"
    s="$(trim "$line")"
    ln=$((i + 1))
    cls="${LINE_CLASS[$i]:-plain}"

    case "$cls" in
      cite-fence|cite-quote)
        # Inert, but NEVER silent: a dropped transition and a deliberate
        # citation are indistinguishable without this line, and the whole
        # safety argument for skipping rests on the sender seeing it.
        if has_quote "$s"; then s="$(strip_quote "$s")"; fi
        add_cite "$ln" "${cls#cite-}" "$s"
        i=$((i + 1)); continue ;;
      ambiguous)
        parse_ambiguous "$ln" "$(reserved_kind "$s")"
        i=$((i + 1)); continue ;;
      fenced|quoted|plain)
        i=$((i + 1)); continue ;;
    esac

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
  # On stdout beside the transitions, not stderr with the errors: a citation is
  # a normal, correct outcome, and the reader who needs it is the sender of a
  # message that VALIDATED (issue #980).
  for i in "${!CITE_LINE[@]}"; do
    echo "FLOW_LEXICON_CITATION=${CITE_CTX[$i]} line ${CITE_LINE[$i]}: ${CITE_TEXT[$i]}"
  done
  for i in "${!ERR_LINE[@]}"; do
    echo "flow-wave-lexicon: line ${ERR_LINE[$i]}: ${ERR_MSG[$i]}" >&2
  done
  E_COUNT="${#TR_KIND[@]}"
  E_GATES="${#GATE_ISSUE[@]}"
  E_ERRORS="${#ERR_LINE[@]}"
  E_CITED="${#CITE_LINE[@]}"
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

E_WAVE="$WAVE"; E_COUNT=""; E_GATES=""; E_CITED=""; E_ERRORS=""; E_RECORDED=""; E_LEDGER=""

read_body
classify_lines
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
      # Name the likely cause rather than leaving the caller to guess it. A
      # verdict fenced or quoted is the #980 shape, and the difference between
      # "you wrote no gate" and "your gate was read as a citation" is the whole
      # diagnosis.
      if [ "${#CITE_LINE[@]}" -gt 0 ]; then
        echo "flow-wave-lexicon: ${#CITE_LINE[@]} reserved token(s) here were read as CITATIONS, not transitions - see the FLOW_LEXICON_CITATION= lines above. If one of them was the verdict you meant to record, move it to column 0, outside any fence and with no '>' prefix (issue #980)." >&2
      fi
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
