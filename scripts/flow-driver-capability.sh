#!/usr/bin/env bash
# flow-driver-capability.sh - what each lifecycle driver CAN do, as declared
# data (issue #783).
#
# Motivation: CPP has four drivers that take a GitHub issue number and carry it
# end to end - /flow:auto, /codex:auto, /qwen:auto, /gemma:auto. The ELI5 gate
# (#775) and the delegated drivers' Step 3 gate (#774/#784) both answer "should
# this work be done, and is this the right plan?". Nothing answered "can this
# driver do this work AT ALL?" - and for three of the four the answer is
# structurally NO for whole classes of issue:
#
#   - the three delegated drivers wrap their model in an IMPLEMENTATION-ONLY
#     execution fence, so their deliverable is a source diff. A research ticket
#     whose product is prose and a recommendation is not work they can take.
#   - /codex:auto runs under `--sandbox workspace-write`, which blocks network
#     for the shell commands the model runs, and /gemma:auto's `gemma-implementer`
#     profile DENIES `webfetch` and `websearch` outright. Neither can consult a
#     live source; asked to, they answer from training data.
#
# Both were observed on the `kyle-completion` wave on 2026-09-05, by two
# different workers on two different drivers, and both were caught only because
# the worker read its own driver's fence and refused. That is discipline, not
# mechanism - the same gap #774 closed for halting. Worse, the fences live
# inside PROMPT-CONSTRUCTION instructions written for a different purpose (they
# exist to stop the model self-directing into the lifecycle, #735), so a worker
# checking its own capability is reading a document that was not written to
# answer that question, and an ORCHESTRATOR routing the work has nothing to read
# at all. It discovers the mismatch when the worker refuses.
#
# So capability is declared HERE, on the two axes the issue names, and read back
# by three consumers rather than left as prose:
#
#   1. `flow-wave-registry.sh` derives the roster's `driver=` annotation from
#      this helper - so an orchestrator sees `[impl-only,no-web]` beside a
#      worker at ASSIGNMENT time, not when the worker refuses.
#   2. each driver's own skill file states its contract, so a worker's Step 2
#      check reads a stated contract instead of inferring one from a fence.
#   3. `tests/test_driver_capability.py` derives the expected matrix from the
#      driver documents themselves, so the data cannot drift from the thing it
#      describes - a driver that loses its fence, or whose sandbox flag changes,
#      turns the suite red rather than leaving this file quietly lying.
#
# Consumer (1) is what keeps this from being decoration. A capability matrix
# nobody reads is prose with extra steps - the kill condition #701 stated about
# its own lexicon - and the answer is the same one: it must be READ BACK by a
# mechanism, not merely published.
#
# ---- The two axes, and why only two --------------------------------------
#
#   scope: general | implementation-only
#     Whether the driver's deliverable can be anything (a written finding, a
#     recommendation, a decision) or only a source diff. Traced to the codex:auto
#     refusal: "Delegating would mean feeding it an already-written brief and
#     asking it to retype it."
#
#   web: yes | no
#     Whether the driver can reach a LIVE source during the run. Traced to the
#     gemma:auto refusal on a terms-research issue - "a hard block, not a
#     judgment call".
#
# `web_basis` records HOW a `no` is enforced, because three drivers say `no` for
# three materially different reasons and collapsing them would overstate two of
# them (see the qwen note below). It changes no verdict; it exists so a reader
# can tell a mechanical denial from an unconfigured lane.
#
# Nothing else is declared. Preconditions - `auto` needs a filed issue and an
# existing checkout, which is why greenfield work routes to `exec` - are a
# DIFFERENT axis, already documented by issue #758, and are deliberately not
# duplicated here.
#
# ---- Needs are DECLARED, never inferred -----------------------------------
#
# `check` takes the needs of the work from its CALLER, out of a closed enum. It
# does not read the issue and guess. Classifying prose would invent mismatches
# the caller never declared, which is exactly the failure #683 records for
# glob-guessing file lanes: "an overlap warning nobody believes". An unknown
# need is a usage error rather than a silent pass, because a typo that reads as
# `fit` is the decoration failure in miniature.
#
# Usage:
#   flow-driver-capability.sh show  <DRIVER>
#   flow-driver-capability.sh list  [--json]
#   flow-driver-capability.sh check <DRIVER> --needs <need>[,<need>...]
#
#   show   Print the capability contract for one driver.
#   list   Print every declared driver, one row each (--json for the object).
#   check  Judge a driver against declared needs. `fit` when it can take all of
#          them, `mismatch` (exit 1) naming each need it cannot meet.
#
#   DRIVER accepts `codex:auto`, `/codex:auto` and the bare family `codex`; a
#   driver string carrying a trailing annotation (`flow:auto (Opus)`, as a wave
#   policy may well declare) matches on its leading token.
#
#   NEED is one of: implementation | research | web
#     implementation  produces a source diff. Every driver meets this.
#     research        produces a finding or recommendation rather than a diff.
#                     Needs scope=general.
#     web             must consult a live source during the run. Needs web=yes.
#
# Output ends with a machine-readable verdict line:
#   FLOW_DRIVER: known | unknown              (show / list)
#   FLOW_DRIVER_CHECK: fit | mismatch | unknown   (check)
# preceded by FLOW_DRIVER_*= detail lines, '-' when not applicable, plus one
# repeated `FLOW_DRIVER_BLOCKED: <need> - <reason>` line per unmet need.
#
# Exit codes: 0 normal, 1 mismatch, 2 usage error.
#
# An UNKNOWN driver is reported and exits 0, deliberately. This helper cannot
# know about a driver somebody added downstream, and failing closed on one would
# block a wave over a name it has never heard of - the routing question is then
# simply unanswered, which is where every driver stood before this file existed.

set -uo pipefail

usage_fail() { echo "flow-driver-capability: $1" >&2; exit 2; }

# ---- The declared matrix ---------------------------------------------------
#
# One record per driver: scope | web | web_basis | scope_basis
#
# The `basis` fields name the mechanism AND where it is verifiable, so a reader
# who doubts a claim has a file to open. tests/test_driver_capability.py checks
# each basis against that file rather than against this table.
DRIVERS="flow:auto codex:auto qwen:auto gemma:auto"

driver_record() { # driver_record CANONICAL -> "scope|web|web_basis|scope_basis"
  case "$1" in
    flow:auto)
      # Claude Code drives directly: the full tool surface, WebFetch/WebSearch
      # included, and no implementation-only fence anywhere in the document.
      echo "general|yes|native (Claude Code WebFetch/WebSearch)|none (Claude implements directly)"
      ;;
    codex:auto)
      # .claude/commands/codex/auto.md - the fence at "IMPLEMENTATION-ONLY
      # agent", the sandbox at `--sandbox workspace-write` (issue #735), which
      # blocks network for the shell commands Codex runs.
      echo "implementation-only|no|sandbox-blocked (codex --sandbox workspace-write, #735)|execution fence: IMPLEMENTATION-ONLY agent"
      ;;
    qwen:auto)
      # .claude/commands/qwen/auto.md - same textual fence. The web answer is
      # WEAKER than the other two and is recorded as such: Qwen Code CLI has web
      # tools upstream, CPP's lane simply configures none, and the Docker sandbox
      # is skipped entirely for a remote Ollama endpoint (#749) - the document
      # says so in as many words ("network from model-run shell commands is NOT
      # blocked by either profile"). So this is an absence of provision, not a
      # denial. Recorded honestly, because a matrix that overstates a block is
      # worse than one that admits a soft edge.
      echo "implementation-only|no|lane-unconfigured (local code model, no web tool in the CPP lane; sandbox skipped for a remote endpoint, #749)|execution fence: IMPLEMENTATION-ONLY agent"
      ;;
    gemma:auto)
      # .claude/commands/gemma/auto.md + templates/opencode-gemma.json - the
      # hardest of the three: the permission profile denies the tools by name.
      echo "implementation-only|no|profile-denied (gemma-implementer denies webfetch and websearch, #752)|execution fence: IMPLEMENTATION-ONLY agent"
      ;;
    *) return 1 ;;
  esac
}

# canonicalize DRIVER -> the matrix key, or '' when not declared.
#
# Tolerant on purpose: the same driver is written `/codex:auto` in a command
# invocation, `codex:auto` in wave policy, and `flow:auto (Opus 5)` when an
# orchestrator annotated the policy field - which is free text and must stay so
# (#699). Matching the leading token keeps an annotated value readable instead
# of downgrading it to `unknown` on a parenthesis.
canonicalize() {
  local raw="$1" head
  head="${raw%%[[:space:]]*}"          # drop any trailing annotation
  head="${head#/}"                     # a leading slash is how users type it
  head="$(printf '%s' "$head" | tr '[:upper:]' '[:lower:]')"
  case "$head" in
    flow|codex|qwen|gemma) head="$head:auto" ;;
  esac
  driver_record "$head" >/dev/null 2>&1 && printf '%s' "$head"
  return 0
}

# fence_of SCOPE WEB -> the compact roster annotation, e.g. "impl-only,no-web".
#
# This is the string flow-wave-registry.sh renders beside a role. It is derived
# here rather than typed there: two copies of a capability claim drift, and the
# drift is silent because both look like documentation.
fence_of() {
  local scope="$1" web="$2" parts=""
  [ "$scope" = "implementation-only" ] && parts="impl-only"
  if [ "$web" = "no" ]; then
    [ -n "$parts" ] && parts="$parts,no-web" || parts="no-web"
  fi
  [ -n "$parts" ] || parts="general,web"
  printf '%s' "$parts"
}

# cannot_of SCOPE WEB -> space-separated needs this driver cannot meet.
cannot_of() {
  local scope="$1" web="$2" out=""
  [ "$scope" = "implementation-only" ] && out="research"
  if [ "$web" = "no" ]; then
    [ -n "$out" ] && out="$out web" || out="web"
  fi
  printf '%s' "$out"
}

# emit_driver CANONICAL - the FLOW_DRIVER_*= detail block for one driver.
emit_driver() {
  local key="$1" rec scope web web_basis scope_basis cannot
  rec="$(driver_record "$key")"
  scope="${rec%%|*}"; rec="${rec#*|}"
  web="${rec%%|*}"; rec="${rec#*|}"
  web_basis="${rec%%|*}"; scope_basis="${rec#*|}"
  cannot="$(cannot_of "$scope" "$web")"
  echo "FLOW_DRIVER=$key"
  echo "FLOW_DRIVER_SCOPE=$scope"
  echo "FLOW_DRIVER_SCOPE_BASIS=$scope_basis"
  echo "FLOW_DRIVER_WEB=$web"
  echo "FLOW_DRIVER_WEB_BASIS=$web_basis"
  echo "FLOW_DRIVER_FENCE=$(fence_of "$scope" "$web")"
  echo "FLOW_DRIVER_CANNOT=${cannot:--}"
}

emit_unknown() {
  echo "FLOW_DRIVER=${1:--}"
  echo "FLOW_DRIVER_SCOPE=-"
  echo "FLOW_DRIVER_SCOPE_BASIS=-"
  echo "FLOW_DRIVER_WEB=-"
  echo "FLOW_DRIVER_WEB_BASIS=-"
  echo "FLOW_DRIVER_FENCE=-"
  echo "FLOW_DRIVER_CANNOT=-"
}

# ---- argument parsing ------------------------------------------------------

[ "$#" -ge 1 ] || usage_fail "usage: flow-driver-capability.sh {show|list|check} [...]"

CMD="$1"; shift
DRIVER=""; NEEDS=""; JSON_OUT=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --needs) [ "$#" -ge 2 ] || usage_fail "--needs requires a comma-separated list"; NEEDS="$2"; shift ;;
    --needs=*) NEEDS="${1#--needs=}" ;;
    --json) JSON_OUT=1 ;;
    --*) usage_fail "unknown option: $1" ;;
    *)
      [ -z "$DRIVER" ] || usage_fail "unexpected argument: $1"
      DRIVER="$1"
      ;;
  esac
  shift
done

case "$CMD" in
  show)
    [ -n "$DRIVER" ] || usage_fail "show requires a driver name"
    KEY="$(canonicalize "$DRIVER")"
    if [ -z "$KEY" ]; then
      emit_unknown "$DRIVER"
      echo "flow-driver-capability: driver '$DRIVER' is not declared - known drivers: $DRIVERS" >&2
      echo "  Capability is unanswered for it, exactly as it was for every driver before #783; routing it is a judgment call." >&2
      echo "FLOW_DRIVER: unknown"
      exit 0
    fi
    emit_driver "$KEY"
    echo "FLOW_DRIVER: known"
    exit 0
    ;;

  list)
    [ -z "$DRIVER" ] || usage_fail "list takes no driver argument"
    if [ "$JSON_OUT" -eq 1 ]; then
      out=""
      for d in $DRIVERS; do
        rec="$(driver_record "$d")"
        scope="${rec%%|*}"; rest="${rec#*|}"
        web="${rest%%|*}"; rest="${rest#*|}"
        web_basis="${rest%%|*}"; scope_basis="${rest#*|}"
        row="$(jq -n --arg d "$d" --arg s "$scope" --arg w "$web" \
                     --arg wb "$web_basis" --arg sb "$scope_basis" \
                     --arg f "$(fence_of "$scope" "$web")" \
                     --arg c "$(cannot_of "$scope" "$web")" \
              '{driver:$d, scope:$s, web:$w, web_basis:$wb, scope_basis:$sb,
                fence:$f, cannot:($c | if . == "" then [] else split(" ") end)}')"
        out="$out$row"
      done
      printf '%s' "$out" | jq -s '.'
      # In --json mode the verdict goes to stderr so stdout stays parseable -
      # the same rule flow-wave-registry.sh follows for its cross-wave notes
      # (#671). A trailing marker line inside a JSON stream is not a contract,
      # it is a parse error waiting for the first scripted consumer.
      echo "FLOW_DRIVER: known" >&2
      exit 0
    else
      for d in $DRIVERS; do
        rec="$(driver_record "$d")"
        scope="${rec%%|*}"; rest="${rec#*|}"
        web="${rest%%|*}"
        cannot="$(cannot_of "$scope" "$web")"
        printf '  %-12s %-20s web=%-4s cannot=%s\n' \
          "$d" "$scope" "$web" "${cannot:--}"
      done
    fi
    echo "FLOW_DRIVER: known"
    exit 0
    ;;

  check)
    [ -n "$DRIVER" ] || usage_fail "check requires a driver name"
    [ -n "$NEEDS" ] || usage_fail "check requires --needs <implementation|research|web>[,...]"

    NEED_LIST="$(printf '%s' "$NEEDS" | tr ',' ' ')"
    for n in $NEED_LIST; do
      case "$n" in
        implementation|research|web) : ;;
        *) usage_fail "unknown need '$n' - one of: implementation, research, web" ;;
      esac
    done

    KEY="$(canonicalize "$DRIVER")"
    if [ -z "$KEY" ]; then
      emit_unknown "$DRIVER"
      echo "FLOW_DRIVER_NEEDS=$NEED_LIST"
      echo "FLOW_DRIVER_UNMET=-"
      echo "flow-driver-capability: driver '$DRIVER' is not declared - known drivers: $DRIVERS" >&2
      echo "  Nothing is asserted about its fit; judge the routing yourself." >&2
      echo "FLOW_DRIVER_CHECK: unknown"
      exit 0
    fi

    rec="$(driver_record "$KEY")"
    scope="${rec%%|*}"; rest="${rec#*|}"
    web="${rest%%|*}"; rest="${rest#*|}"
    web_basis="${rest%%|*}"; scope_basis="${rest#*|}"

    UNMET=""; BLOCKED=""
    for n in $NEED_LIST; do
      case "$n" in
        research)
          if [ "$scope" != "general" ]; then
            UNMET="$UNMET research"
            BLOCKED="$BLOCKED
FLOW_DRIVER_BLOCKED: research - $KEY is $scope ($scope_basis); its deliverable is a source diff, not a finding."
          fi
          ;;
        web)
          if [ "$web" != "yes" ]; then
            UNMET="$UNMET web"
            BLOCKED="$BLOCKED
FLOW_DRIVER_BLOCKED: web - $KEY has no live-source access ($web_basis); it would answer from training data."
          fi
          ;;
        implementation) : ;;   # every declared driver writes source files
      esac
    done
    UNMET="${UNMET# }"

    emit_driver "$KEY"
    echo "FLOW_DRIVER_NEEDS=$NEED_LIST"
    echo "FLOW_DRIVER_UNMET=${UNMET:--}"
    [ -n "$BLOCKED" ] && printf '%s\n' "${BLOCKED#$'\n'}"

    if [ -n "$UNMET" ]; then
      echo "flow-driver-capability: '$KEY' cannot take work needing: $UNMET" >&2
      echo "  Route it to a driver that can (see 'flow-driver-capability.sh list'), or do it in-session." >&2
      echo "FLOW_DRIVER_CHECK: mismatch"
      exit 1
    fi
    echo "FLOW_DRIVER_CHECK: fit"
    exit 0
    ;;

  *) usage_fail "unknown command '$CMD' - one of: show, list, check" ;;
esac
