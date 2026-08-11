#!/usr/bin/env bash
# flow-wave-registry.sh - Role -> address registry for multi-session flow waves
# (issue #638, companion to the #637 wave orchestration loop).
#
# Motivation: when one orchestrator session drives several worker sessions,
# session identity is unresolvable from the orchestrator's side and the failure
# is silent. `ListAgents` prints display labels (`projects-xx`) that do NOT map
# to assigned roles; guessing misrouted three times in one four-worker wave
# (2026-08-10), twice handing workers each other's issue. The one address that
# cannot be gotten wrong is the transport-stamped socket
# (`uds:/run/user/<uid>/cc-socks/<pid>.sock`) from an incoming message's
# `from=` attribute. This helper persists the role -> socket roster on disk,
# OUTSIDE any repo and outside session transcripts, so it survives a worker's
# `/clear` and cannot become shared mutable repo state (the #635 hazard class).
#
# The registry lives under the user's runtime dir by default
# (`$XDG_RUNTIME_DIR/cc-flow-wave/registry.json`), which the OS wipes at
# reboot - exactly when every session socket dies too, so an entry can never
# outlive its meaning. Entries are namespaced by --wave so two concurrent
# waves on one host cannot collide. Writes are flock-serialized and atomic
# (tmp file + rename).
#
# Trust model (issue #638, gate condition 1): a session can SELF-derive its
# socket (walking its ancestor pids against the socket dir) but that address is
# an assertion - bootstrap only. The authoritative address is the one the
# orchestrator OBSERVES on a real incoming message (`verify <role> --from`).
# On any mismatch the OBSERVED address replaces the self-derived one as
# canonical and the discrepancy is flagged; the reverse never happens.
#
# Loud default (issue #671): an omitted --wave silently lands in wave 'default'
# with a clean verdict while every named-wave roster stays empty - the
# silent-addressing-failure class #638 exists to prevent, one namespace level
# up. So register/get/verify into wave 'default' without an explicit --wave
# print one advisory stderr line (register also names the likely intended wave
# when exactly one other wave has a live orchestrator - suggestion only, never
# auto-join), and list appends a note for LIVE same-host entries parked in
# OTHER waves (stderr in --json mode, so stdout stays parseable). Advisory
# only - verdicts and exit codes are unchanged.
#
# Usage:
#   flow-wave-registry.sh register <role> [--wave W] [--force] [--cwd P]
#                         [--repo P] [--issue N] [--branch B] [--socket S]
#   flow-wave-registry.sh list    [--wave W] [--json]
#   flow-wave-registry.sh get     <role> [--wave W]
#   flow-wave-registry.sh verify  <role> --from <uds:...> [--wave W]
#   flow-wave-registry.sh release <role> [--wave W] [--force]
#   flow-wave-registry.sh self-address
#
#   register  Record this session as <role>. Self-derives the socket when
#             --socket is not given (falls back to "unknown" - the observed
#             round-trip then supplies it via `verify`). Re-registering the
#             role you already hold refreshes the entry (idempotent). A role
#             held by a LIVE other session is refused (exit 1) unless --force.
#             A dead owner's entry is stale and taken over automatically.
#   list      Show the roster: role, address, issue, liveness, verification.
#             Marks dead entries stale rather than deleting them - a dead
#             worker mid-issue is information. Warns on lane overlaps between
#             LIVE entries: same repo + same issue, same branch, or same/nested
#             worktree paths. Same repo alone is NOT a warning - in a wave,
#             every worker shares the repo by design (info only).
#   get       key=value contract for one role (for scripting).
#   verify    Orchestrator-side: reconcile the recorded address with the
#             OBSERVED `from=` of a real message. Match -> verified. Mismatch
#             -> the observed address becomes canonical, the entry is flagged
#             (`address_mismatch`), and the verdict is `mismatch-corrected`.
#   release   Mark the role released ("I'm leaving the wave"). Another LIVE
#             session's role is refused without --force.
#   self-address  Print this session's best-guess socket (bootstrap only).
#
# Output ends with a machine-readable verdict line:
#   FLOW_WAVE: registered | updated | refused | released | listed | verified |
#              mismatch-corrected | free | unknown | error
# preceded by detail lines (FLOW_WAVE_ROLE=, FLOW_WAVE_SOCKET=, ...), '-' when
# not applicable. Exit codes: 0 normal, 1 refused (live-owner conflict),
# 2 usage error.
#
# Env:
#   CLAUDE_PID / CLAUDE_CODE_SESSION_ID  owner identity (fall back: $PPID / -)
# Env (test hooks - unset in normal use):
#   FLOW_WAVE_REGISTRY_DIR  registry dir override
#   FLOW_WAVE_SOCK_DIR      socket dir override (default /run/user/<uid>/cc-socks)
#   FLOW_WAVE_NOW           override "now" as epoch seconds
#   FLOW_WAVE_HOST          override this host's name
#   FLOW_WAVE_LIVE_PIDS     ':'-separated pids treated as alive (bypasses kill -0)
#   FLOW_WAVE_SELF_PID      starting pid for the self-address ancestor walk

set -uo pipefail

UID_NUM="$(id -u)"
REG_DIR="${FLOW_WAVE_REGISTRY_DIR:-${XDG_RUNTIME_DIR:-/run/user/$UID_NUM}/cc-flow-wave}"
REG_FILE="$REG_DIR/registry.json"
LOCK_FILE="$REG_DIR/registry.lock"
SOCK_DIR="${FLOW_WAVE_SOCK_DIR:-/run/user/$UID_NUM/cc-socks}"
SELF_PID="${CLAUDE_PID:-$PPID}"
SELF_SESSION="${CLAUDE_CODE_SESSION_ID:--}"
SELF_HOST="${FLOW_WAVE_HOST:-${HOSTNAME:-$(hostname 2>/dev/null || echo unknown)}}"
NOW="${FLOW_WAVE_NOW:-$(date +%s)}"

usage_fail() { echo "flow-wave-registry: $1" >&2; exit 2; }

command -v jq >/dev/null 2>&1 || {
  echo "flow-wave-registry: jq is required (see .claude/bootstrap.yaml)" >&2
  echo "FLOW_WAVE: error"
  exit 2
}

# Emit the detail block + verdict. Unset args default to '-'.
emit() {
  echo "FLOW_WAVE_WAVE=${E_WAVE:--}"
  echo "FLOW_WAVE_ROLE=${E_ROLE:--}"
  echo "FLOW_WAVE_SOCKET=${E_SOCKET:--}"
  echo "FLOW_WAVE_PID=${E_PID:--}"
  echo "FLOW_WAVE_SESSION=${E_SESSION:--}"
  echo "FLOW_WAVE_LIVENESS=${E_LIVE:--}"
  echo "FLOW_WAVE_VERIFIED=${E_VERIFIED:--}"
  echo "FLOW_WAVE_MISMATCH=${E_MISMATCH:--}"
  echo "FLOW_WAVE: $1"
}

# is_alive PID HOST -> 0 when the owning session still runs on THIS host.
is_alive() {
  local pid="$1" host="$2"
  [ -n "$pid" ] && [ "$pid" != "-" ] && [ "$pid" != "null" ] || return 1
  [ "$host" = "$SELF_HOST" ] || return 1
  if [ -n "${FLOW_WAVE_LIVE_PIDS:-}" ]; then
    case ":$FLOW_WAVE_LIVE_PIDS:" in
      *":$pid:"*) return 0 ;;
      *) return 1 ;;
    esac
  fi
  kill -0 "$pid" 2>/dev/null
}

# Best-effort self-address: walk this process's ancestors and match each pid
# against a socket file. Bootstrap only - `verify` with a transport-observed
# from= is the authoritative source (gate condition 1).
self_address() {
  local pid="${FLOW_WAVE_SELF_PID:-$PPID}" hops=0
  while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null && [ "$hops" -lt 20 ]; do
    if [ -S "$SOCK_DIR/$pid.sock" ] || [ -e "$SOCK_DIR/$pid.sock" ]; then
      printf 'uds:%s/%s.sock' "$SOCK_DIR" "$pid"
      return 0
    fi
    if [ -r "/proc/$pid/status" ]; then
      pid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null)"
    else
      pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
    fi
    hops=$((hops + 1))
  done
  printf 'unknown'
}

# All mutations run under flock, read-modify-write with an atomic rename.
# with_lock JQ_PROGRAM [jq args...] - applies the program to the registry.
with_lock() {
  local prog="$1"; shift
  mkdir -p "$REG_DIR" 2>/dev/null || usage_fail "cannot create $REG_DIR"
  (
    flock -w 10 9 || { echo "flow-wave-registry: could not lock registry" >&2; exit 3; }
    [ -s "$REG_FILE" ] || echo '{}' > "$REG_FILE"
    local tmp
    tmp="$(mktemp "$REG_DIR/.registry.XXXXXX")" || exit 3
    if jq "$@" "$prog" "$REG_FILE" > "$tmp" 2>/dev/null; then
      mv -f "$tmp" "$REG_FILE"
    else
      rm -f "$tmp"
      echo "flow-wave-registry: registry update failed (corrupt JSON?)" >&2
      exit 3
    fi
  ) 9>"$LOCK_FILE"
}

read_registry() {
  if [ -s "$REG_FILE" ]; then cat "$REG_FILE"; else echo '{}'; fi
}

entry_json() { # entry_json WAVE ROLE -> the entry object or 'null'
  read_registry | jq -c --arg w "$1" --arg r "$2" '.[$w].roles[$r] // null'
}

# liveness_of ENTRY_JSON -> live | stale | released
liveness_of() {
  local e="$1" pid host sock released
  released="$(printf '%s' "$e" | jq -r '.released // false')"
  [ "$released" = "true" ] && { echo released; return; }
  pid="$(printf '%s' "$e" | jq -r '.pid // "-"')"
  host="$(printf '%s' "$e" | jq -r '.host // "-"')"
  sock="$(printf '%s' "$e" | jq -r '.socket // "unknown"')"
  if is_alive "$pid" "$host"; then echo live; return; fi
  # A live socket file on this host also proves liveness (covers a pid the
  # helper cannot signal but whose session socket clearly exists).
  if [ "$host" = "$SELF_HOST" ] && [ "$sock" != "unknown" ]; then
    local p="${sock#uds:}"
    [ -S "$p" ] && { echo live; return; }
  fi
  echo stale
}

# implicit_default -> 0 when this invocation landed in wave 'default' without
# an explicit --wave (issue #671 - the omitted-flag signature).
implicit_default() {
  [ "$WAVE_EXPLICIT" -eq 0 ] && [ "$WAVE" = "default" ]
}

# likely_wave -> prints the one OTHER wave holding a LIVE orchestrator entry,
# nothing when zero or several qualify (issue #671, item 3). Suggestion only -
# the caller re-registers with --wave if it agrees; nothing auto-joins.
likely_wave() {
  local reg w e name="" count=0
  reg="$(read_registry)"
  for w in $(printf '%s' "$reg" | jq -r 'keys[]' 2>/dev/null); do
    [ "$w" = "$WAVE" ] && continue
    e="$(printf '%s' "$reg" | jq -c --arg w "$w" '.[$w].roles.orchestrator // null')"
    [ "$e" != "null" ] || continue
    [ "$(liveness_of "$e")" = "live" ] || continue
    name="$w"; count=$((count + 1))
  done
  [ "$count" -eq 1 ] && printf '%s' "$name"
  return 0
}

# Cross-wave visibility (issue #671): LIVE same-host entries parked in OTHER
# waves are invisible to this roster - name them, so a worker that omitted
# --wave (stranded in 'default') costs seconds to spot instead of a raw-JSON
# dig. liveness_of is already host-scoped, so remote entries never appear.
cross_wave_notes() {
  local reg other r e pid detail n
  reg="$(read_registry)"
  for other in $(printf '%s' "$reg" | jq -r 'keys[]' 2>/dev/null); do
    [ "$other" = "$WAVE" ] && continue
    detail=""; n=0
    for r in $(printf '%s' "$reg" | jq -r --arg w "$other" '(.[$w].roles // {}) | keys[]' 2>/dev/null); do
      e="$(printf '%s' "$reg" | jq -c --arg w "$other" --arg r "$r" '.[$w].roles[$r]')"
      [ "$(liveness_of "$e")" = "live" ] || continue
      pid="$(printf '%s' "$e" | jq -r '.pid // "-"')"
      detail="$detail, role $r pid $pid"
      n=$((n + 1))
    done
    [ "$n" -gt 0 ] || continue
    if [ "$other" = "default" ]; then
      echo "  note: $n live session(s) registered in wave 'default' (${detail#, }) - a worker that omitted --wave?"
    else
      echo "  note: $n live session(s) registered in wave '$other' (${detail#, })"
    fi
  done
}

# ---- argument parsing -------------------------------------------------------
VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-wave-registry.sh register|list|get|verify|release|self-address ..."
shift

case "$VERB" in
  register | list | get | verify | release | self-address) : ;;
  --help | -h)
    sed -n '2,85p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB" ;;
esac

ROLE=""; WAVE="default"; WAVE_EXPLICIT=0; FORCE=0; JSON_OUT=0
A_CWD=""; A_REPO=""; A_ISSUE=""; A_BRANCH=""; A_SOCKET=""; A_FROM=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wave) [ "$#" -ge 2 ] || usage_fail "--wave requires a name"; WAVE="$2"; WAVE_EXPLICIT=1; shift ;;
    --wave=*) WAVE="${1#--wave=}"; WAVE_EXPLICIT=1 ;;
    --force) FORCE=1 ;;
    --json) JSON_OUT=1 ;;
    --cwd) [ "$#" -ge 2 ] || usage_fail "--cwd requires a path"; A_CWD="$2"; shift ;;
    --cwd=*) A_CWD="${1#--cwd=}" ;;
    --repo) [ "$#" -ge 2 ] || usage_fail "--repo requires a path"; A_REPO="$2"; shift ;;
    --repo=*) A_REPO="${1#--repo=}" ;;
    --issue) [ "$#" -ge 2 ] || usage_fail "--issue requires a number"; A_ISSUE="$2"; shift ;;
    --issue=*) A_ISSUE="${1#--issue=}" ;;
    --branch) [ "$#" -ge 2 ] || usage_fail "--branch requires a name"; A_BRANCH="$2"; shift ;;
    --branch=*) A_BRANCH="${1#--branch=}" ;;
    --socket) [ "$#" -ge 2 ] || usage_fail "--socket requires an address"; A_SOCKET="$2"; shift ;;
    --socket=*) A_SOCKET="${1#--socket=}" ;;
    --from) [ "$#" -ge 2 ] || usage_fail "--from requires an address"; A_FROM="$2"; shift ;;
    --from=*) A_FROM="${1#--from=}" ;;
    --*) usage_fail "unknown option: $1" ;;
    *)
      [ -z "$ROLE" ] || usage_fail "unexpected argument: $1"
      ROLE="$1"
      ;;
  esac
  shift
done

E_WAVE="$WAVE"; E_ROLE="$ROLE"; E_SOCKET=""; E_PID=""; E_SESSION=""
E_LIVE=""; E_VERIFIED=""; E_MISMATCH=""

case "$VERB" in
  self-address)
    self_address; echo ""
    exit 0
    ;;

  register)
    [ -n "$ROLE" ] || usage_fail "register requires a role"
    SOCK="$A_SOCKET"
    [ -n "$SOCK" ] || SOCK="$(self_address)"
    CUR="$(entry_json "$WAVE" "$ROLE")"
    if [ "$CUR" != "null" ]; then
      CUR_PID="$(printf '%s' "$CUR" | jq -r '.pid // "-"')"
      CUR_SESSION="$(printf '%s' "$CUR" | jq -r '.session // "-"')"
      CUR_LIVE="$(liveness_of "$CUR")"
      SAME_OWNER=0
      [ "$CUR_SESSION" != "-" ] && [ "$CUR_SESSION" = "$SELF_SESSION" ] && SAME_OWNER=1
      [ "$CUR_PID" = "$SELF_PID" ] && SAME_OWNER=1
      if [ "$SAME_OWNER" -eq 0 ] && [ "$CUR_LIVE" = "live" ] && [ "$FORCE" -eq 0 ]; then
        echo "flow-wave-registry: role '$ROLE' (wave '$WAVE') is held by a LIVE session (pid $CUR_PID, session $CUR_SESSION)." >&2
        echo "  Two sessions both believing they are '$ROLE' is the failure this command exists to prevent (#638)." >&2
        echo "  Pick another role, or re-run with --force if you are certain that session is gone." >&2
        E_SOCKET="$(printf '%s' "$CUR" | jq -r '.socket // "unknown"')"
        E_PID="$CUR_PID"; E_SESSION="$CUR_SESSION"; E_LIVE="$CUR_LIVE"
        emit refused
        exit 1
      fi
      [ "$SAME_OWNER" -eq 0 ] && [ "$CUR_LIVE" = "stale" ] &&
        echo "flow-wave-registry: taking over stale role '$ROLE' (owner pid $CUR_PID is gone)." >&2
      VERDICT=updated
      [ "$SAME_OWNER" -eq 0 ] && VERDICT=registered
    else
      VERDICT=registered
    fi
    with_lock '
      .[$w] //= {"roles": {}} |
      .[$w].roles[$r] = {
        socket: $sock, self_socket: $sock, pid: ($pid | tonumber? // $pid),
        session: $session, host: $host, cwd: $cwd, repo: $repo,
        issue: $issue, branch: $branch, registered_ts: ($now | tonumber),
        verified: false, address_mismatch: false, released: false
      }' \
      --arg w "$WAVE" --arg r "$ROLE" --arg sock "$SOCK" --arg pid "$SELF_PID" \
      --arg session "$SELF_SESSION" --arg host "$SELF_HOST" --arg cwd "$A_CWD" \
      --arg repo "$A_REPO" --arg issue "$A_ISSUE" --arg branch "$A_BRANCH" \
      --arg now "$NOW"
    [ "$SOCK" = "unknown" ] &&
      echo "flow-wave-registry: could not self-derive a socket - registered as 'unknown'; the orchestrator's 'verify' (observed from=) will supply it." >&2
    if implicit_default; then
      echo "flow-wave-registry: no --wave given - registered into wave 'default'; concurrent waves will not see this entry." >&2
      if [ "$ROLE" != "orchestrator" ]; then
        LIKELY="$(likely_wave)"
        [ -n "$LIKELY" ] &&
          echo "  Did you mean --wave '$LIKELY'? A live orchestrator is registered there (suggestion only - re-register with --wave to join it)." >&2
      fi
    fi
    E_SOCKET="$SOCK"; E_PID="$SELF_PID"; E_SESSION="$SELF_SESSION"; E_LIVE=live
    E_VERIFIED=false; E_MISMATCH=false
    emit "$VERDICT"
    exit 0
    ;;

  get)
    [ -n "$ROLE" ] || usage_fail "get requires a role"
    implicit_default &&
      echo "flow-wave-registry: no --wave given - reading wave 'default'; a role registered under a named wave will not be found here." >&2
    CUR="$(entry_json "$WAVE" "$ROLE")"
    if [ "$CUR" = "null" ]; then emit free; exit 0; fi
    E_SOCKET="$(printf '%s' "$CUR" | jq -r '.socket // "unknown"')"
    E_PID="$(printf '%s' "$CUR" | jq -r '.pid // "-"')"
    E_SESSION="$(printf '%s' "$CUR" | jq -r '.session // "-"')"
    E_LIVE="$(liveness_of "$CUR")"
    E_VERIFIED="$(printf '%s' "$CUR" | jq -r '.verified // false')"
    E_MISMATCH="$(printf '%s' "$CUR" | jq -r '.address_mismatch // false')"
    echo "FLOW_WAVE_CWD=$(printf '%s' "$CUR" | jq -r '.cwd // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_REPO=$(printf '%s' "$CUR" | jq -r '.repo // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_ISSUE=$(printf '%s' "$CUR" | jq -r '.issue // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_BRANCH=$(printf '%s' "$CUR" | jq -r '.branch // "-" | if . == "" then "-" else . end')"
    emit listed
    exit 0
    ;;

  verify)
    [ -n "$ROLE" ] || usage_fail "verify requires a role"
    [ -n "$A_FROM" ] || usage_fail "verify requires --from <observed uds:... address>"
    implicit_default &&
      echo "flow-wave-registry: no --wave given - verifying in wave 'default'; a role registered under a named wave will not be found here." >&2
    CUR="$(entry_json "$WAVE" "$ROLE")"
    [ "$CUR" != "null" ] || { echo "flow-wave-registry: no entry for role '$ROLE' in wave '$WAVE'." >&2; emit unknown; exit 0; }
    RECORDED="$(printf '%s' "$CUR" | jq -r '.socket // "unknown"')"
    if [ "$RECORDED" = "$A_FROM" ]; then
      with_lock '.[$w].roles[$r].verified = true' --arg w "$WAVE" --arg r "$ROLE"
      E_SOCKET="$A_FROM"; E_VERIFIED=true; E_MISMATCH=false
      emit verified
      exit 0
    fi
    # Gate condition 1 (#638): the transport-observed address is authoritative.
    # It REPLACES the self-derived one as canonical; the discrepancy is flagged.
    # Never the reverse - a self-derived address never survives a mismatch.
    with_lock '
      .[$w].roles[$r].socket = $obs |
      .[$w].roles[$r].verified = true |
      .[$w].roles[$r].address_mismatch = true' \
      --arg w "$WAVE" --arg r "$ROLE" --arg obs "$A_FROM"
    echo "flow-wave-registry: WARNING - role '$ROLE' self-reported '$RECORDED' but the transport observed '$A_FROM'." >&2
    echo "  The OBSERVED address is now canonical (self-derivation is bootstrap only). Investigate the discrepancy." >&2
    E_SOCKET="$A_FROM"; E_VERIFIED=true; E_MISMATCH=true
    emit mismatch-corrected
    exit 0
    ;;

  release)
    [ -n "$ROLE" ] || usage_fail "release requires a role"
    CUR="$(entry_json "$WAVE" "$ROLE")"
    [ "$CUR" != "null" ] || { emit free; exit 0; }
    CUR_PID="$(printf '%s' "$CUR" | jq -r '.pid // "-"')"
    CUR_SESSION="$(printf '%s' "$CUR" | jq -r '.session // "-"')"
    SAME_OWNER=0
    [ "$CUR_SESSION" != "-" ] && [ "$CUR_SESSION" = "$SELF_SESSION" ] && SAME_OWNER=1
    [ "$CUR_PID" = "$SELF_PID" ] && SAME_OWNER=1
    CUR_LIVE="$(liveness_of "$CUR")"
    if [ "$SAME_OWNER" -eq 0 ] && [ "$CUR_LIVE" = "live" ] && [ "$FORCE" -eq 0 ]; then
      echo "flow-wave-registry: role '$ROLE' belongs to a LIVE session (pid $CUR_PID) - not releasing. Pass --force to override." >&2
      E_PID="$CUR_PID"; E_SESSION="$CUR_SESSION"; E_LIVE="$CUR_LIVE"
      emit refused
      exit 1
    fi
    with_lock '
      .[$w].roles[$r].released = true |
      .[$w].roles[$r].released_ts = ($now | tonumber)' \
      --arg w "$WAVE" --arg r "$ROLE" --arg now "$NOW"
    emit released
    exit 0
    ;;

  list)
    REG="$(read_registry)"
    ROLES="$(printf '%s' "$REG" | jq -r --arg w "$WAVE" '(.[$w].roles // {}) | keys[]' 2>/dev/null)"
    if [ "$JSON_OUT" -eq 1 ]; then
      # Enriched JSON: each entry plus computed liveness.
      OUT="{}"
      for r in $ROLES; do
        e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
        lv="$(liveness_of "$e")"
        OUT="$(printf '%s' "$OUT" | jq -c --arg r "$r" --argjson e "$e" --arg lv "$lv" '.[$r] = ($e + {liveness: $lv})')"
      done
      printf '%s\n' "$OUT" | jq .
      # Keep --json stdout parseable: cross-wave notes go to stderr (#671).
      cross_wave_notes >&2
      echo "FLOW_WAVE: listed"
      exit 0
    fi
    if [ -z "$ROLES" ]; then
      echo "flow-wave-registry: no roles registered for wave '$WAVE' ($REG_FILE)."
      cross_wave_notes
      echo "FLOW_WAVE: listed"
      exit 0
    fi
    echo "Wave '$WAVE' roster ($REG_FILE):"
    for r in $ROLES; do
      e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
      lv="$(liveness_of "$e")"
      sock="$(printf '%s' "$e" | jq -r '.socket // "unknown"')"
      iss="$(printf '%s' "$e" | jq -r '.issue // "" | if . == "" then "-" else . end')"
      ver="$(printf '%s' "$e" | jq -r 'if .address_mismatch == true then "MISMATCH-corrected" elif .verified == true then "verified" else "unverified" end')"
      echo "  $r -> $sock [$lv, $ver] issue=$iss"
    done
    # Lane-overlap warnings among LIVE entries only (gate condition 2: sharing
    # a repo is the NORMAL wave shape - never warn on it alone; warn on same
    # repo + same issue, same branch, or same/nested worktree paths).
    WARNED=0
    LIVE_ROLES=""
    for r in $ROLES; do
      e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
      [ "$(liveness_of "$e")" = "live" ] && LIVE_ROLES="$LIVE_ROLES $r"
    done
    for a in $LIVE_ROLES; do
      for b in $LIVE_ROLES; do
        [ "$a" \< "$b" ] || continue
        ea="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$a" '.[$w].roles[$r]')"
        eb="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$b" '.[$w].roles[$r]')"
        ra="$(printf '%s' "$ea" | jq -r '.repo // ""')"; rb="$(printf '%s' "$eb" | jq -r '.repo // ""')"
        ia="$(printf '%s' "$ea" | jq -r '.issue // ""')"; ib="$(printf '%s' "$eb" | jq -r '.issue // ""')"
        ba="$(printf '%s' "$ea" | jq -r '.branch // ""')"; bb="$(printf '%s' "$eb" | jq -r '.branch // ""')"
        ca="$(printf '%s' "$ea" | jq -r '.cwd // ""')"; cb="$(printf '%s' "$eb" | jq -r '.cwd // ""')"
        if [ -n "$ia" ] && [ "$ia" = "$ib" ] && [ -n "$ra" ] && [ "$ra" = "$rb" ]; then
          echo "  WARNING: '$a' and '$b' both claim issue #$ia in $ra - two sessions on one issue race each other's worktrees (#597)."
          WARNED=1
        elif [ -n "$ba" ] && [ "$ba" = "$bb" ]; then
          echo "  WARNING: '$a' and '$b' both claim branch '$ba' - same checkout, guaranteed collision."
          WARNED=1
        elif [ -n "$ca" ] && [ -n "$cb" ] && { [ "$ca" = "$cb" ] || case "$ca/" in "$cb"/*) true ;; *) false ;; esac || case "$cb/" in "$ca"/*) true ;; *) false ;; esac; }; then
          echo "  WARNING: '$a' ($ca) and '$b' ($cb) have same/nested worktrees - edits will collide."
          WARNED=1
        elif [ -n "$ra" ] && [ "$ra" = "$rb" ]; then
          echo "  info: '$a' and '$b' share repo $ra (separate worktrees - the normal wave shape)."
        fi
      done
    done
    [ "$WARNED" -eq 1 ] && echo "flow-wave-registry: lane overlap detected - do not co-schedule the flagged pairs." >&2
    cross_wave_notes
    echo "FLOW_WAVE: listed"
    exit 0
    ;;
esac
