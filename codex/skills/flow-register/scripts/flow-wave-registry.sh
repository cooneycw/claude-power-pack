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
#             --socket is not given; --socket is the MANUAL BOOTSTRAP LANE for
#             an address learned by any other means (harness env, user relay)
#             and always wins. Re-registering the role you already hold
#             refreshes the entry (idempotent) and RE-DERIVES the address, so a
#             session that registered before its socket existed adopts the real
#             one on a retry - but a failed derivation never downgrades an
#             already-recorded address to "unknown" (#672). A role held by a
#             LIVE other session is refused (exit 1) unless --force. A dead
#             owner's entry is stale and taken over automatically.
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
#                 Prints why on failure - see FLOW_WAVE_SOCKET_REASON below.
#
# Output ends with a machine-readable verdict line:
#   FLOW_WAVE: registered | updated | refused | released | listed | verified |
#              mismatch-corrected | free | unknown | error
# preceded by detail lines (FLOW_WAVE_ROLE=, FLOW_WAVE_SOCKET=, ...), '-' when
# not applicable. Exit codes: 0 normal, 1 refused (live-owner conflict),
# 2 usage error.
#
# Addressing honesty (#672) - three detail lines describe the address itself,
# so an unaddressed session is never reported as a healthy pending handshake:
#   FLOW_WAVE_SOCKET_SOURCE  explicit (--socket) | self (derived) |
#                            preserved (derivation failed, kept the recorded
#                            address) | unknown (no address at all)
#   FLOW_WAVE_SOCKET_REASON  '-' | no-sock-dir (the socket dir does not exist -
#                            this host has no session transport YET; it is
#                            created lazily, so retry) | no-match (dir exists,
#                            no ancestor pid owns a socket in it)
#   FLOW_WAVE_BOOTSTRAP      ok | deadlock. `deadlock` on register/get/list
#                            means the address in question is "unknown", so
#                            `verify` CANNOT fire: it needs an observed from=,
#                            which needs a delivered message, which needs an
#                            address. It is blocked, not pending - the escape
#                            lanes are printed with it.
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
  echo "FLOW_WAVE_SOCKET_SOURCE=${E_SOURCE:--}"
  echo "FLOW_WAVE_SOCKET_REASON=${E_REASON:--}"
  echo "FLOW_WAVE_PID=${E_PID:--}"
  echo "FLOW_WAVE_SESSION=${E_SESSION:--}"
  echo "FLOW_WAVE_LIVENESS=${E_LIVE:--}"
  echo "FLOW_WAVE_VERIFIED=${E_VERIFIED:--}"
  echo "FLOW_WAVE_MISMATCH=${E_MISMATCH:--}"
  echo "FLOW_WAVE_BOOTSTRAP=${E_BOOTSTRAP:--}"
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
#
# Sets DERIVED_ADDR ('uds:...' or 'unknown') and DERIVED_REASON, which names WHY
# a derivation failed rather than flattening both causes to a bare 'unknown'
# (issue #672). The two are operationally different and want different advice:
#   no-sock-dir  $SOCK_DIR does not exist - this host exposes no session socket
#                transport (yet). Observed 2026-08-11: the directory is created
#                LAZILY, so an 'unknown' recorded before it appears is a
#                point-in-time answer, not a permanent verdict - re-registering
#                once a socket exists adopts the real address.
#   no-match     the directory exists but no ancestor pid owns a socket in it -
#                a genuinely unaddressable session, not a missing transport.
DERIVED_ADDR="unknown"
DERIVED_REASON="-"
derive_self_address() {
  DERIVED_ADDR="unknown"
  DERIVED_REASON="-"
  if [ ! -d "$SOCK_DIR" ]; then
    DERIVED_REASON="no-sock-dir"
    return 0
  fi
  # Start from this session's own pid when the harness exports it (SELF_PID's
  # rule); $PPID alone starts one hop too low and is only reached by luck.
  local pid="${FLOW_WAVE_SELF_PID:-${CLAUDE_PID:-$PPID}}" hops=0
  while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null && [ "$hops" -lt 20 ]; do
    if [ -S "$SOCK_DIR/$pid.sock" ] || [ -e "$SOCK_DIR/$pid.sock" ]; then
      DERIVED_ADDR="uds:$SOCK_DIR/$pid.sock"
      return 0
    fi
    if [ -r "/proc/$pid/status" ]; then
      pid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null)"
    else
      pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
    fi
    hops=$((hops + 1))
  done
  DERIVED_REASON="no-match"
}

# The three lanes that can still produce an address when self-derivation cannot,
# printed wherever the helper reports an unaddressed session. Every one of them
# was available during the 2026-08-11 deadlock; none was visible in the output.
bootstrap_escapes() {
  echo "  Bootstrap lanes that do NOT depend on self-derivation:" >&2
  echo "    1. re-run this register - the socket dir is created lazily, so a" >&2
  echo "       retry once this session has a socket adopts the real address." >&2
  echo "    2. register --socket <addr> - pass an address learned by any means" >&2
  echo "       (harness env, the user relaying it from the other session)." >&2
  echo "    3. user-relayed hello - the user pastes this session's FLOW_WAVE_*" >&2
  echo "       block to the counterpart, whose reply carries an observable from=." >&2
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

# ---- argument parsing -------------------------------------------------------
VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-wave-registry.sh register|list|get|verify|release|self-address ..."
shift

case "$VERB" in
  register | list | get | verify | release | self-address) : ;;
  --help | -h)
    sed -n '2,96p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB" ;;
esac

ROLE=""; WAVE="default"; FORCE=0; JSON_OUT=0
A_CWD=""; A_REPO=""; A_ISSUE=""; A_BRANCH=""; A_SOCKET=""; A_FROM=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wave) [ "$#" -ge 2 ] || usage_fail "--wave requires a name"; WAVE="$2"; shift ;;
    --wave=*) WAVE="${1#--wave=}" ;;
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
E_LIVE=""; E_VERIFIED=""; E_MISMATCH=""; E_SOURCE=""; E_REASON=""; E_BOOTSTRAP=""

case "$VERB" in
  self-address)
    derive_self_address
    printf '%s\n' "$DERIVED_ADDR"
    if [ "$DERIVED_ADDR" = "unknown" ]; then
      case "$DERIVED_REASON" in
        no-sock-dir)
          echo "flow-wave-registry: no socket dir at '$SOCK_DIR' - this host exposes no session socket transport (yet)." >&2
          echo "  The directory is created lazily, so this is a point-in-time answer, not a permanent verdict." >&2
          ;;
        no-match)
          echo "flow-wave-registry: '$SOCK_DIR' exists but no ancestor pid of this session owns a socket in it." >&2
          ;;
      esac
    fi
    exit 0
    ;;

  register)
    [ -n "$ROLE" ] || usage_fail "register requires a role"
    SOCK="$A_SOCKET"
    SOCK_SOURCE=explicit
    SOCK_REASON="-"
    KEEP_VERIFIED=false
    if [ -z "$SOCK" ]; then
      derive_self_address
      SOCK="$DERIVED_ADDR"
      SOCK_REASON="$DERIVED_REASON"
      SOCK_SOURCE=self
      [ "$SOCK" = "unknown" ] && SOCK_SOURCE=unknown
    fi
    # self_socket records what THIS registration asserted about itself, so a
    # preserved address (below) does not masquerade as a fresh derivation.
    SELF_SOCK="$SOCK"
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
      # Trust model, the reverse direction (#638 gate condition 1 / #672): a
      # FAILED self-derivation must never downgrade a recorded address to
      # 'unknown'. You cannot address 'unknown', so any known address outranks
      # it whatever its provenance. Without this, the idempotent re-register
      # that register.md recommends as the cheap re-brief silently destroys the
      # address the wave is running on the moment the socket dir is unreadable.
      # An explicit --socket is operator intent and always wins.
      CUR_SOCK="$(printf '%s' "$CUR" | jq -r '.socket // "unknown"')"
      if [ "$SOCK" = "unknown" ] && [ "$CUR_SOCK" != "unknown" ]; then
        SOCK="$CUR_SOCK"
        SOCK_SOURCE=preserved
        KEEP_VERIFIED="$(printf '%s' "$CUR" | jq -r '.verified // false')"
        echo "flow-wave-registry: self-derivation returned unknown ($DERIVED_REASON) - KEEPING the recorded address '$CUR_SOCK'." >&2
        echo "  A known address outranks a failed derivation; re-registering never downgrades one to 'unknown' (#672)." >&2
      fi
      VERDICT=updated
      [ "$SAME_OWNER" -eq 0 ] && VERDICT=registered
    else
      VERDICT=registered
    fi
    with_lock '
      .[$w] //= {"roles": {}} |
      .[$w].roles[$r] = {
        socket: $sock, self_socket: $selfsock, pid: ($pid | tonumber? // $pid),
        session: $session, host: $host, cwd: $cwd, repo: $repo,
        issue: $issue, branch: $branch, registered_ts: ($now | tonumber),
        verified: ($verified == "true"), address_mismatch: false, released: false
      }' \
      --arg w "$WAVE" --arg r "$ROLE" --arg sock "$SOCK" --arg pid "$SELF_PID" \
      --arg selfsock "$SELF_SOCK" --arg verified "$KEEP_VERIFIED" \
      --arg session "$SELF_SESSION" --arg host "$SELF_HOST" --arg cwd "$A_CWD" \
      --arg repo "$A_REPO" --arg issue "$A_ISSUE" --arg branch "$A_BRANCH" \
      --arg now "$NOW"
    # Honest failure surface (#672): name the CAUSE, and never promise a verify
    # step that cannot fire. `verify` needs a transport-observed from=, which
    # needs a DELIVERED message, which needs someone to already hold a real
    # address - so with no address here, the fallback is not "later", it is
    # structurally blocked until one of the bootstrap lanes below runs.
    if [ "$SOCK" = "unknown" ]; then
      case "$SOCK_REASON" in
        no-sock-dir)
          echo "flow-wave-registry: no socket dir at '$SOCK_DIR' - this host exposes no session socket transport yet; registered as 'unknown'." >&2
          ;;
        *)
          echo "flow-wave-registry: '$SOCK_DIR' exists but no ancestor pid of this session owns a socket in it; registered as 'unknown'." >&2
          ;;
      esac
      echo "  This session has NO address, so the orchestrator's 'verify' cannot fire on its own:" >&2
      echo "  verify needs an observed from=, which needs a delivered message, which needs an address." >&2
      bootstrap_escapes
      E_BOOTSTRAP=deadlock
    else
      E_BOOTSTRAP=ok
    fi
    E_SOCKET="$SOCK"; E_PID="$SELF_PID"; E_SESSION="$SELF_SESSION"; E_LIVE=live
    E_VERIFIED="$KEEP_VERIFIED"; E_MISMATCH=false
    E_SOURCE="$SOCK_SOURCE"; E_REASON="$SOCK_REASON"
    emit "$VERDICT"
    exit 0
    ;;

  get)
    [ -n "$ROLE" ] || usage_fail "get requires a role"
    CUR="$(entry_json "$WAVE" "$ROLE")"
    if [ "$CUR" = "null" ]; then emit free; exit 0; fi
    E_SOCKET="$(printf '%s' "$CUR" | jq -r '.socket // "unknown"')"
    E_PID="$(printf '%s' "$CUR" | jq -r '.pid // "-"')"
    E_SESSION="$(printf '%s' "$CUR" | jq -r '.session // "-"')"
    E_LIVE="$(liveness_of "$CUR")"
    E_VERIFIED="$(printf '%s' "$CUR" | jq -r '.verified // false')"
    E_MISMATCH="$(printf '%s' "$CUR" | jq -r '.address_mismatch // false')"
    # `get` is what a session runs to answer "where do I send to this role?".
    # An entry whose socket is 'unknown' cannot answer it, and saying so is the
    # whole point (#672) - the caller would otherwise read a successful-looking
    # 'listed' verdict and wait forever for a handshake that cannot start.
    if [ "$E_SOCKET" = "unknown" ]; then
      E_BOOTSTRAP=deadlock
      echo "flow-wave-registry: role '$ROLE' (wave '$WAVE') has NO address - it cannot be messaged, so no from= can be observed for it." >&2
      bootstrap_escapes
    else
      E_BOOTSTRAP=ok
    fi
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
    # How much of this roster is unaddressable (#672)? A LIVE entry with no
    # socket is a role nobody can open a handshake with in EITHER direction -
    # the orchestrator-first contact #670 relies on has no target either.
    UNADDRESSED=0
    for r in $ROLES; do
      e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
      [ "$(liveness_of "$e")" = "live" ] || continue
      [ "$(printf '%s' "$e" | jq -r '.socket // "unknown"')" = "unknown" ] &&
        UNADDRESSED=$((UNADDRESSED + 1))
    done
    BOOTSTRAP_STATE=ok
    [ "$UNADDRESSED" -gt 0 ] && BOOTSTRAP_STATE=deadlock
    if [ "$JSON_OUT" -eq 1 ]; then
      # Enriched JSON: each entry plus computed liveness.
      OUT="{}"
      for r in $ROLES; do
        e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
        lv="$(liveness_of "$e")"
        OUT="$(printf '%s' "$OUT" | jq -c --arg r "$r" --argjson e "$e" --arg lv "$lv" '.[$r] = ($e + {liveness: $lv})')"
      done
      printf '%s\n' "$OUT" | jq .
      echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
      echo "FLOW_WAVE: listed"
      exit 0
    fi
    if [ -z "$ROLES" ]; then
      echo "flow-wave-registry: no roles registered for wave '$WAVE' ($REG_FILE)."
      echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
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
    if [ "$UNADDRESSED" -gt 0 ]; then
      echo "  BOOTSTRAP: $UNADDRESSED LIVE role(s) have no address - they cannot be messaged, and no from= can be observed for them."
      echo "  Verification cannot fire for those roles on its own; it is blocked, not pending."
      bootstrap_escapes
    fi
    echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
    echo "FLOW_WAVE: listed"
    exit 0
    ;;
esac
