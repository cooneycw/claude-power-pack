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
#             --socket is not given; --socket is the MANUAL BOOTSTRAP LANE for
#             an address learned by any other means (harness env, user relay)
#             and always wins. Re-registering the role you already hold
#             refreshes the entry (idempotent) and RE-DERIVES the address, so a
#             session that registered before its socket existed adopts the real
#             one on a retry - but a failed derivation never downgrades an
#             already-recorded address to "unknown" (#672). A role held by a
#             LIVE other session is refused (exit 1) unless --force. A dead
#             owner's entry is stale and taken over automatically.
#             The observation flags (`verified`, `address_filled`,
#             `address_mismatch`) SURVIVE a re-register by the same owner at a
#             byte-identical address (#691/#692) - they record one transport
#             observation that a routine re-brief does not invalidate, so they
#             are preserved together or cleared together. A takeover or a
#             changed address clears all three. Advises when --cwd looks like a
#             shared parent rather than a lane (#683).
#   list      Show the roster: role, address, issue, liveness, verification.
#             Marks dead entries stale rather than deleting them - a dead
#             worker mid-issue is information. Warns on lane overlaps between
#             LIVE entries: same repo + same issue, same branch, or same/nested
#             worktree paths. Same repo alone is NOT a warning - in a wave,
#             every worker shares the repo by design (info only). Roles that
#             DECLARED NO LANE are EXEMPT from the pairwise checks (#683) - the
#             `orchestrator` (never implements, so it cannot collide with a lane)
#             and any live role with no issue, no branch, AND a shared-parent
#             cwd. Narrow on purpose: a declared branch or a real nested worktree
#             is a lane even with no issue number. The exemption is announced,
#             not silent, and lapses the moment a lane is declared.
#             ALSO reconciles `flow-claim` worktree locks (#687): a session that
#             went straight to /flow:auto never registered, so its issue, branch
#             and worktree were invisible to the roster while it held a real
#             lock - the #673 near-double-assignment. Live claims that no
#             registry entry accounts for are rendered as claim-derived rows and
#             DO participate in overlap detection. Their address is OBSERVED
#             (a socket present for that pid), never derived from it, so a
#             non-uds transport reports no address instead of a wrong one.
#             COVERAGE BOUND, stated because a blind spot that reads like
#             coverage is the failure this guards: repos are discovered from the
#             wave's own LIVE entries plus an explicit --repo, so a host where
#             nothing is registered has nothing to scan. In #673 it WOULD have
#             fired - the orchestrator was registered with a repo.
#   get       key=value contract for one role (for scripting).
#   verify    Orchestrator-side: reconcile the recorded address with the
#             OBSERVED `from=` of a real message. Three outcomes, and the split
#             between the last two is the point (#674) - the observed address
#             becomes canonical in all of them, so they differ in what they say
#             about the entry, never in how much it can be trusted:
#               match                 -> `verified`.
#               recorded was unknown  -> `address_filled`. The documented
#                 fallback WORKING: self-derivation failed at register time and
#                 observation supplied what it could not. Benign - info line,
#                 no investigate warning, `address_mismatch` stays FALSE, and
#                 `list` renders `filled`. `filled` is NOT a lesser grade than
#                 `verified`: the address is transport-observed and fully
#                 trustworthy, and the word records HOW it was established, not
#                 how much to trust it. Nobody should ever have to ask whether a
#                 `filled` entry is a problem.
#               recorded was a real, DIFFERENT address -> `mismatch-corrected`.
#                 A genuine contradiction (possible misrouting or stale pid
#                 reuse): loud warning, `address_mismatch` flagged true.
#             Before #674 the benign fill took the mismatch branch verbatim, so
#             on a host with no socket dir EVERY worker registered `unknown` and
#             EVERY verify shouted - a flag firing on 100% of the fleet carries
#             zero signal and buries the one case worth investigating.
#   release   Mark the role released ("I'm leaving the wave"). Another LIVE
#             session's role is refused without --force.
#   self-address  Print this session's best-guess socket (bootstrap only).
#                 Prints why on failure - see FLOW_WAVE_SOCKET_REASON below.
#
# Output ends with a machine-readable verdict line:
#   FLOW_WAVE: registered | updated | refused | released | listed | verified |
#              address_filled | mismatch-corrected | free | unknown | error
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
  #
  # This secondary proof is UDS-ONLY and now says so (#689). It used to strip a
  # `uds:` prefix unconditionally and stat the remainder, which on any other
  # transport - `bridge:session_01RLE...` - stripped nothing and tested whether a
  # file literally named `bridge:session_...` existed. Always false, so the
  # fallback was silently inert rather than absent, and register.md's two-factor
  # staleness rule ("socket gone + pid dead") was one-factor on those transports.
  #
  # Deliberately EXPOSES the gap rather than closing it: whether another
  # transport can offer its own secondary proof is a separate question (#676).
  # On a non-uds address liveness rests on `kill -0` alone - the registry is
  # host-local by construction, so that is sound today, but it is one mechanism
  # and not two, and the code should state that instead of implying otherwise.
  if [ "$host" = "$SELF_HOST" ] && [ "$sock" != "unknown" ]; then
    case "$sock" in
      uds:*) [ -S "${sock#uds:}" ] && { echo live; return; } ;;
      # Any other scheme: no socket-file proof exists. Fall through to stale on
      # the strength of `kill -0` alone rather than running a test that cannot
      # pass (#689).
      *) : ;;
    esac
  fi
  echo stale
}

# cwd_is_shared_parent CWD REPO -> 0 when CWD looks like a shared projects
# parent rather than a lane (#683).
#
# A session that registers BEFORE entering a worktree - normal practice since
# #670 made worker-first registration first-class - records the projects parent
# as its cwd. That single path then NESTS OVER every worktree on the host, so
# the `list` overlap check fires "same/nested worktrees" against each live role.
# Observed producing three simultaneous false warnings in one wave.
#
# Two signatures, either sufficient:
#   1. cwd is a STRICT ancestor of the declared --repo. Direct and exact.
#   2. cwd directly contains 2+ git checkouts - the ~/Projects shape - which
#      catches a registration that declared no --repo.
# Heuristic by nature, and advisory-only precisely because of that: a false
# positive costs one line of stderr and never changes a verdict.
cwd_is_shared_parent() {
  local cwd="$1" repo="$2" count=0 d
  [ -n "$cwd" ] || return 1
  cwd="${cwd%/}"
  [ -n "$cwd" ] || return 1
  if [ -n "$repo" ]; then
    repo="${repo%/}"
    if [ "$cwd" != "$repo" ]; then
      case "$repo/" in "$cwd"/*) return 0 ;; esac
    fi
  fi
  [ -d "$cwd" ] || return 1
  for d in "$cwd"/*/; do
    [ -e "$d.git" ] && count=$((count + 1))
    [ "$count" -ge 2 ] && return 0
  done
  return 1
}

# claim_address PID -> an OBSERVED address for a claim's pid, or empty.
#
# Observation, never derivation (#687). The tempting move is to BUILD
# "uds:$SOCK_DIR/<pid>.sock" from the pid and call it the session's address -
# and #687 as filed asked for exactly that. It is a uds-shaped guess, and #675
# removed that assumption from the addressing docs while #689 removed it from
# `liveness_of`; manufacturing it here would undo both from a third direction.
#
# So: look, and report only what is there. A socket present at the conventional
# path is an observation and is reported. Nothing there means the claim is
# reported WITHOUT an address - honest, and consistent with #672's rule that a
# failed derivation never invents one. On a transport that stamps something
# else this simply finds nothing, which is the correct answer rather than a
# confident wrong one.
# CLAIM_FS - the ONE field separator for claim records (#698), shared by the
# producer and the parser so the format has a single definition.
#
# ASCII unit separator (0x1F), deliberately NOT tab. Tab is IFS *whitespace*, so
# shell field splitting collapses a run of it into a single delimiter and an
# EMPTY field vanishes rather than arriving empty - every later field shifts up
# one slot. #687 shipped with tab and a branchless (detached-HEAD) claim
# therefore rendered its worktree path as a branch and the repo root as its
# worktree, and fed those wrong values into overlap detection. `\037` is not IFS
# whitespace, so empty fields survive in every position - middle, trailing, and
# both at once, which matters because an absent observed address is the COMMON
# case for an unregistered claim, not an edge one.
#
# Four independent definitions of this separator (one printf format + three
# `IFS=` expressions) were what made #698 possible, and the failure mode is
# shifted fields rather than an error - so a future edit to any one of them
# would break silently. One constant, one parser: see parse_claim_record.
CLAIM_FS="$(printf '\037')"

# parse_claim_record RECORD -> sets C_ISSUE C_PID C_SESSION C_BRANCH C_WT
#                              C_REPO C_ADDR
#
# The ONE place that knows the field order and the separator. Call sites read
# whole lines (`IFS= read -r rec`, the same single-field idiom every other read
# loop in scripts/ uses and the reason they were all immune to #698) and hand
# the record here.
parse_claim_record() {
  IFS="$CLAIM_FS" read -r C_ISSUE C_PID C_SESSION C_BRANCH C_WT C_REPO C_ADDR <<EOF
$1
EOF
}

claim_address() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  [ -S "$SOCK_DIR/$pid.sock" ] && printf 'uds:%s/%s.sock' "$SOCK_DIR" "$pid"
  return 0
}

# collect_unregistered_claims REG WAVE REPOS
#   Emits one TAB-separated record per LIVE `flow-claim` worktree lock that no
#   registry entry in WAVE accounts for:
#     issue \t pid \t session \t branch \t worktree \t repo \t address
#
# The registry and git each know who is working on what, and before #687 they
# never spoke (#673: a live session held a claim, had the fix committed, and was
# invisible to the roster - the orchestrator nearly assigned the issue twice).
# `git worktree list --porcelain` already carries everything needed:
#   locked flow-claim issue=<n> pid=<p> session=<s> host=<h> ts=<t>
#
# COVERAGE IS BOUNDED AND THE BOUND IS REAL: repos are discovered FROM registry
# entries (plus an explicit --repo), so a host where nothing is registered has
# nothing to scan and stays invisible. This closes the gap for repos the wave
# knows about, which is what #673 needed - the orchestrator there WAS registered
# with a repo. Stated rather than implied: a reconciliation whose blind spot
# reads like its working case is the failure this whole series is about.
#
# Fail-open per repo: a missing git, an absent path, or an unreadable repo is
# skipped silently. `list` must never break because reconciliation could not run.
collect_unregistered_claims() {
  local reg="$1" wave="$2" repos="$3"
  local known_pids="" known_sessions="" rname e
  command -v git >/dev/null 2>&1 || return 0
  # Only a LIVE entry ACCOUNTS FOR a live claim. A released or stale entry does
  # not: the session said it left the wave (or died) while something still holds
  # the lock, and suppressing the claim row there would show the orchestrator a
  # released row over a lane that is genuinely still held - the #687 blindness
  # re-created through the back door.
  for rname in $(printf '%s' "$reg" | jq -r --arg w "$wave" '(.[$w].roles // {}) | keys[]'); do
    e="$(printf '%s' "$reg" | jq -c --arg w "$wave" --arg r "$rname" '.[$w].roles[$r]')"
    [ "$(liveness_of "$e")" = "live" ] || continue
    known_pids="$known_pids
$(printf '%s' "$e" | jq -r '(.pid // empty) | tostring')"
    known_sessions="$known_sessions
$(printf '%s' "$e" | jq -r '.session // empty')"
  done
  printf '%s\n' "$repos" | sort -u | while IFS= read -r repo; do
    [ -n "$repo" ] || continue
    [ -d "$repo" ] || continue
    local cur_wt="" cur_branch="" line kv reason
    local c_issue c_pid c_session c_host addr
    while IFS= read -r line; do
      case "$line" in
        "worktree "*)
          cur_wt="${line#worktree }"; cur_branch="" ;;
        "branch "*)
          cur_branch="${line#branch }"; cur_branch="${cur_branch#refs/heads/}" ;;
        "locked flow-claim "*)
          reason="${line#locked }"
          c_issue=""; c_pid=""; c_session=""; c_host=""
          for kv in $reason; do
            case "$kv" in
              issue=*)   c_issue="${kv#issue=}" ;;
              pid=*)     c_pid="${kv#pid=}" ;;
              session=*) c_session="${kv#session=}" ;;
              host=*)    c_host="${kv#host=}" ;;
            esac
          done
          # A dead claim is worktree-remove's problem (#597 takes it over), not
          # roster noise - only a LIVE claim can be double-assigned.
          is_alive "$c_pid" "$c_host" || continue
          # Accounted for by a registry entry? Match on pid OR session, the same
          # ownership test `register` uses.
          if [ -n "$c_pid" ] && printf '%s\n' "$known_pids" | grep -Fxq -- "$c_pid"; then continue; fi
          if [ -n "$c_session" ] && printf '%s\n' "$known_sessions" | grep -Fxq -- "$c_session"; then continue; fi
          addr="$(claim_address "$c_pid")"
          # CLAIM_FS is interpolated into the FORMAT string, which is normally a
          # smell (a '%' in the variable would be read as a conversion). Safe
          # here by construction: CLAIM_FS is a fixed control character set once
          # at the top of this file, never derived from input.
          printf "%s${CLAIM_FS}%s${CLAIM_FS}%s${CLAIM_FS}%s${CLAIM_FS}%s${CLAIM_FS}%s${CLAIM_FS}%s\n" \
            "$c_issue" "$c_pid" "$c_session" "$cur_branch" "$cur_wt" "$repo" "$addr"
          ;;
      esac
    done < <(git -C "$repo" worktree list --porcelain 2>/dev/null)
  done
}

# report_overlap A_LABEL A_ISS A_BR A_CWD A_REPO B_LABEL B_ISS B_BR B_CWD B_REPO
#
# The ONE lane-overlap predicate, shared by role-vs-role and claim-vs-role
# (#687). Extracted rather than copied: a safety check written twice drifts, and
# two copies disagreeing about what counts as a collision is the hazard
# `tool-risk-drift` exists to catch for the permission taxonomy. Precedence and
# wording are unchanged from #638/#683 - only the call sites are new.
# Sets WARNED=1 on a warning; info-level shared-repo never does.
report_overlap() {
  local al="$1" ia="$2" ba="$3" ca="$4" ra="$5"
  local bl="$6" ib="$7" bb="$8" cb="$9" rb="${10}"
  if [ -n "$ia" ] && [ "$ia" = "$ib" ] && [ -n "$ra" ] && [ "$ra" = "$rb" ]; then
    echo "  WARNING: '$al' and '$bl' both claim issue #$ia in $ra - two sessions on one issue race each other's worktrees (#597)."
    WARNED=1
  elif [ -n "$ba" ] && [ "$ba" = "$bb" ]; then
    echo "  WARNING: '$al' and '$bl' both claim branch '$ba' - same checkout, guaranteed collision."
    WARNED=1
  elif [ -n "$ca" ] && [ -n "$cb" ] && { [ "$ca" = "$cb" ] || case "$ca/" in "$cb"/*) true ;; *) false ;; esac || case "$cb/" in "$ca"/*) true ;; *) false ;; esac; }; then
    echo "  WARNING: '$al' ($ca) and '$bl' ($cb) have same/nested worktrees - edits will collide."
    WARNED=1
  elif [ -n "$ra" ] && [ "$ra" = "$rb" ]; then
    echo "  info: '$al' and '$bl' share repo $ra (separate worktrees - the normal wave shape)."
  fi
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
    sed -n '2,96p' "$0" | sed 's/^# \{0,1\}//'
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
    # The three flags describing the transport observation share ONE lifecycle
    # (#691/#692). Splitting them is how this class of inconsistency arises:
    # they record one fact - "the transport was observed to reach THIS session at
    # THIS address" - so they are preserved together or cleared together.
    KEEP_VERIFIED=false
    KEEP_FILLED=false
    KEEP_MISMATCH=false
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
        echo "flow-wave-registry: self-derivation returned unknown ($DERIVED_REASON) - KEEPING the recorded address '$CUR_SOCK'." >&2
        echo "  A known address outranks a failed derivation; re-registering never downgrades one to 'unknown' (#672)." >&2
      fi
      # Re-registration is the DOCUMENTED cheap re-brief (#670 makes it routine),
      # so it must not silently rewrite what the transport already established
      # (#691/#692). When the same owner re-registers at a byte-identical
      # address, the prior observation still holds and every flag derived from it
      # survives - including `address_mismatch`, whose erasure is the dangerous
      # direction: #674 narrowed that flag so firing MEANS something, and
      # clearing it on a routine action undid that from the other end, wiping an
      # uninvestigated discrepancy off the roster with no record it existed.
      #
      # This EXTENDS the #672 rule above rather than adding a second mechanism -
      # that branch already preserved `verified` for the derivation-failed case;
      # it was simply scoped to the rarer case. A successful derivation returning
      # the SAME socket is what actually happens, and it was clearing everything.
      #
      # A TAKEOVER (different owner) or a CHANGED address still clears all three:
      # the observation was about a specific session at a specific address, so
      # once either changes it no longer applies and must be re-established.
      if [ "$SAME_OWNER" -eq 1 ] && [ "$SOCK" = "$CUR_SOCK" ] && [ "$SOCK" != "unknown" ]; then
        KEEP_VERIFIED="$(printf '%s' "$CUR" | jq -r '.verified // false')"
        KEEP_FILLED="$(printf '%s' "$CUR" | jq -r '.address_filled // false')"
        KEEP_MISMATCH="$(printf '%s' "$CUR" | jq -r '.address_mismatch // false')"
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
        verified: ($verified == "true"), address_mismatch: ($mismatch == "true"),
        address_filled: ($filled == "true"), released: false
      }' \
      --arg w "$WAVE" --arg r "$ROLE" --arg sock "$SOCK" --arg pid "$SELF_PID" \
      --arg selfsock "$SELF_SOCK" --arg verified "$KEEP_VERIFIED" \
      --arg filled "$KEEP_FILLED" --arg mismatch "$KEEP_MISMATCH" \
      --arg session "$SELF_SESSION" --arg host "$SELF_HOST" --arg cwd "$A_CWD" \
      --arg repo "$A_REPO" --arg issue "$A_ISSUE" --arg branch "$A_BRANCH" \
      --arg now "$NOW"
    # Honest failure surface (#672): name the CAUSE, and never promise a verify
    # step that cannot fire. `verify` needs a transport-observed from=, which
    # needs a DELIVERED message, which needs someone to already hold a real
    # address - so with no address here, the fallback is not "later", it is
    # structurally blocked until one of the bootstrap lanes below runs. This
    # REPLACES the "the orchestrator's verify will supply it" line, which was
    # the promise #672 was filed about.
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
    # Shared-parent cwd (#683) - independent of both addressing and wave: a
    # registration is perfectly valid from a parent directory (bootstrap needs
    # no lane), it just makes overlap detection cry wolf against every worktree
    # nested under it. Say so HERE, at the moment the cwd is recorded, so the
    # worker can fix it by re-registering rather than waiting for an orchestrator
    # to notice a roster full of false collisions.
    if cwd_is_shared_parent "$A_CWD" "$A_REPO"; then
      echo "flow-wave-registry: cwd '$A_CWD' looks like a shared parent directory, not a lane." >&2
      echo "  Re-register with --cwd <worktree> once your lane exists, or overlap detection will cry wolf against every worktree under it (#683)." >&2
      echo "  Harmless for bootstrap - the entry is valid and this changes no verdict." >&2
    fi
    # Loud default (#671) - independent of addressing: a silently-defaulted
    # wave and an unaddressed session are separate failures and both advise.
    if implicit_default; then
      echo "flow-wave-registry: no --wave given - registered into wave 'default'; concurrent waves will not see this entry." >&2
      if [ "$ROLE" != "orchestrator" ]; then
        LIKELY="$(likely_wave)"
        [ -n "$LIKELY" ] &&
          echo "  Did you mean --wave '$LIKELY'? A live orchestrator is registered there (suggestion only - re-register with --wave to join it)." >&2
      fi
    fi
    E_SOCKET="$SOCK"; E_PID="$SELF_PID"; E_SESSION="$SELF_SESSION"; E_LIVE=live
    E_VERIFIED="$KEEP_VERIFIED"; E_MISMATCH="$KEEP_MISMATCH"
    E_SOURCE="$SOCK_SOURCE"; E_REASON="$SOCK_REASON"
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
    # Benign fill (#674): there was no recorded address to contradict, so
    # observation did not overrule a claim - it supplied one that self-derivation
    # could not. This is the documented bootstrap fallback succeeding, and it is
    # deliberately NOT flagged: before the split it took the mismatch branch
    # below verbatim, so on a host with no socket dir every worker registered
    # `unknown` and every verify shouted, which is a flag with zero signal.
    # `address_mismatch` stays false and the entry is fully verified - the
    # address is transport-observed, exactly as in the match case.
    if [ "$RECORDED" = "unknown" ] || [ -z "$RECORDED" ] || [ "$RECORDED" = "null" ]; then
      with_lock '
        .[$w].roles[$r].socket = $obs |
        .[$w].roles[$r].verified = true |
        .[$w].roles[$r].address_filled = true |
        .[$w].roles[$r].address_mismatch = false' \
        --arg w "$WAVE" --arg r "$ROLE" --arg obs "$A_FROM"
      echo "flow-wave-registry: role '$ROLE' had no address; the transport observed '$A_FROM' and it is now canonical." >&2
      echo "  Nothing to investigate - self-derivation failed at register time and observation supplied the address (the documented fallback)." >&2
      E_SOCKET="$A_FROM"; E_VERIFIED=true; E_MISMATCH=false
      E_SOURCE=observed
      emit address_filled
      exit 0
    fi
    # Gate condition 1 (#638): the transport-observed address is authoritative.
    # It REPLACES the self-derived one as canonical; the discrepancy is flagged.
    # Never the reverse - a self-derived address never survives a mismatch.
    # Reached only when the recorded value was a REAL address that DIFFERS from
    # the observed one - a genuine contradiction worth a human look (#674).
    with_lock '
      .[$w].roles[$r].socket = $obs |
      .[$w].roles[$r].verified = true |
      .[$w].roles[$r].address_mismatch = true' \
      --arg w "$WAVE" --arg r "$ROLE" --arg obs "$A_FROM"
    echo "flow-wave-registry: WARNING - role '$ROLE' self-reported '$RECORDED' but the transport observed '$A_FROM'." >&2
    echo "  The OBSERVED address is now canonical (self-derivation is bootstrap only). Investigate the discrepancy." >&2
    E_SOCKET="$A_FROM"; E_VERIFIED=true; E_MISMATCH=true
    E_SOURCE=observed
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
    # Reconcile flow-claim worktree locks (#687). Repos come from the wave's own
    # LIVE entries, plus an explicit --repo for the case the registry cannot
    # know about - see the coverage bound on collect_unregistered_claims.
    # Repo discovery deliberately reads EVERY entry, live or not - a stale or
    # released entry is a poor account of a lane but a perfectly good record of
    # which repo this wave concerns. Restricting discovery to live entries would
    # blind the scan exactly when the wave has died back to one dead row and an
    # unregistered session is still working, which is the #687 case at its worst.
    # (Whether a claim is ACCOUNTED FOR is a separate, strictly live-only test.)
    SCAN_REPOS="$A_REPO"
    for r in $ROLES; do
      e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
      rp="$(printf '%s' "$e" | jq -r '.repo // ""')"
      [ -n "$rp" ] && SCAN_REPOS="$SCAN_REPOS
$rp"
    done
    CLAIMS="$(collect_unregistered_claims "$REG" "$WAVE" "$SCAN_REPOS")"
    if [ "$JSON_OUT" -eq 1 ]; then
      # Enriched JSON: each entry plus computed liveness.
      OUT="{}"
      for r in $ROLES; do
        e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
        lv="$(liveness_of "$e")"
        OUT="$(printf '%s' "$OUT" | jq -c --arg r "$r" --argjson e "$e" --arg lv "$lv" '.[$r] = ($e + {liveness: $lv})')"
      done
      # Claim-derived rows are a SIBLING key, never members of the roles map
      # (#687). They are NOT registry entries: contactable, which is the whole
      # point, but not `verify`/`release` targets and never to be mistaken for
      # roles. Roles stay exactly where they are - existing consumers index them
      # at the top level, so nesting them under a `roles:` wrapper would be the
      # very breaking change this avoids. The key appears only when there is
      # something to report, so a claim-free run is byte-identical to pre-#687.
      if [ -n "$CLAIMS" ]; then
        # jq splits on the SAME constant (#698). This was the fifth independent
        # definition of the delimiter and the one the original four-definitions
        # count missed - which is the argument for the constant, not against it.
        CLAIM_JSON="$(printf '%s\n' "$CLAIMS" | jq -R -s --arg fs "$CLAIM_FS" 'split("\n") | map(select(length > 0) | split($fs)) | map({issue: .[0], pid: .[1], session: .[2], branch: .[3], worktree: .[4], repo: .[5], address: (if (.[6] // "") == "" then null else .[6] end), source: "flow-claim-lock", registered: false})')"
        OUT="$(printf '%s' "$OUT" | jq -c --argjson c "$CLAIM_JSON" '. + {unregistered_claims: $c}')"
      fi
      printf '%s\n' "$OUT" | jq .
      # Keep --json stdout parseable: cross-wave notes go to stderr (#671).
      cross_wave_notes >&2
      echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
      echo "FLOW_WAVE: listed"
      exit 0
    fi
    if [ -z "$ROLES" ]; then
      echo "flow-wave-registry: no roles registered for wave '$WAVE' ($REG_FILE)."
      # An empty roster is exactly when reconciliation matters most (#687): no
      # registered roles and a live unregistered claim is the maximal blind
      # spot, and it is the case an explicit --repo exists to reach. Returning
      # "nothing registered" while a lock is held would be the original bug.
      if [ -n "$CLAIMS" ]; then
        echo "  -- unregistered flow-claim locks (live, not registry entries - contactable, but not addressable as roles) --"
        while IFS= read -r rec; do
          [ -n "$rec" ] || continue
          parse_claim_record "$rec"
          echo "  (claim) -> ${C_ADDR:-no observed address} [live, unregistered] issue=${C_ISSUE:--} branch=${C_BRANCH:--} pid=$C_PID wt=$C_WT"
        done <<EOF
$CLAIMS
EOF
      fi
      cross_wave_notes
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
      # `filled` is a verified state, not a lesser one (#674): the address was
      # transport-observed, and the word records that observation SUPPLIED it
      # rather than CONFIRMED it. Mismatch is checked first so a real
      # contradiction can never render as the benign case.
      ver="$(printf '%s' "$e" | jq -r 'if .address_mismatch == true then "MISMATCH-corrected" elif .address_filled == true then "filled" elif .verified == true then "verified" else "unverified" end')"
      echo "  $r -> $sock [$lv, $ver] issue=$iss"
    done
    # Claim-derived rows (#687), rendered AFTER the roles and visibly not roles.
    # An orchestrator scanning the issue column now sees a lane held by a
    # session that never registered - the #673 case, where the roster said an
    # issue was free while a live session was minutes from a PR on it.
    if [ -n "$CLAIMS" ]; then
      echo "  -- unregistered flow-claim locks (live, not registry entries - contactable, but not addressable as roles) --"
      while IFS= read -r rec; do
        [ -n "$rec" ] || continue
        parse_claim_record "$rec"
        echo "  (claim) -> ${C_ADDR:-no observed address} [live, unregistered] issue=${C_ISSUE:--} branch=${C_BRANCH:--} pid=$C_PID wt=$C_WT"
      done <<EOF
$CLAIMS
EOF
    fi
    # Lane-overlap warnings among LIVE entries only (gate condition 2: sharing
    # a repo is the NORMAL wave shape - never warn on it alone; warn on same
    # repo + same issue, same branch, or same/nested worktree paths).
    #
    # A role that has DECLARED NO LANE is excluded from the pairwise checks
    # (#683). The mechanism compares declared lanes, so warning about a role that
    # declared none is warning about something the registry does not know.
    #
    # Two exempt shapes, and the second is deliberately NARROW:
    #   - the `orchestrator`. CLAUDE.md:136 documents it as never implementing,
    #     so it HOLDS NO LANE AND CANNOT COLLIDE WITH ONE - whatever its cwd
    #     happens to be. That is the durable reason and the only one this
    #     exemption rests on. (Do not ground it in "its cwd is structurally the
    #     projects parent, so it cannot re-register its way out": that was the
    #     original justification and it is empirically FALSE - an orchestrator
    #     re-registered with `--cwd $XDG_RUNTIME_DIR/cc-flow-wave/<wave>` and both
    #     false warnings dropped to info immediately. That workaround is real but
    #     depends on the orchestrator knowing the trick, which is precisely why
    #     the exemption is the fix and the cwd argument is not load-bearing.)
    #   - any other live role that has declared NOTHING that constitutes a lane:
    #     no issue, no branch, AND a cwd that is a shared parent rather than a
    #     checkout.
    #
    # "No issue claimed" ALONE is too coarse and was tried first: it also
    # swallowed a declared BRANCH and a genuinely nested pair of worktrees, both
    # real collisions that happen to carry no issue number (caught by the
    # pre-existing TestListOverlap cases, which now pass unmodified - that they
    # do is the evidence this boundary is the right one). The false warnings
    # never came from nested worktrees; they came from a cwd that is a shared
    # PARENT, so that is what the exemption keys on.
    #
    # The exemption is ANNOUNCED, never silent. Trading a false warning for a
    # blind spot would just move the problem: #674's rule is do-not-alarm, not
    # do-not-say. It also lapses the moment the role declares any lane.
    WARNED=0
    LIVE_ROLES=""
    EXEMPT_ROLES=""
    for r in $ROLES; do
      e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
      [ "$(liveness_of "$e")" = "live" ] || continue
      r_iss="$(printf '%s' "$e" | jq -r '.issue // ""')"
      r_br="$(printf '%s' "$e" | jq -r '.branch // ""')"
      r_cwd="$(printf '%s' "$e" | jq -r '.cwd // ""')"
      r_repo="$(printf '%s' "$e" | jq -r '.repo // ""')"
      if [ "$r" = "orchestrator" ]; then
        EXEMPT_ROLES="$EXEMPT_ROLES $r"
        continue
      fi
      if [ -z "$r_iss" ] && [ -z "$r_br" ] && cwd_is_shared_parent "$r_cwd" "$r_repo"; then
        EXEMPT_ROLES="$EXEMPT_ROLES $r"
        continue
      fi
      LIVE_ROLES="$LIVE_ROLES $r"
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
        report_overlap "$a" "$ia" "$ba" "$ca" "$ra" "$b" "$ib" "$bb" "$cb" "$rb"
      done
    done
    # Claim-derived lanes participate in overlap detection (#687 item 2) - an
    # unregistered claim is precisely the lane most likely to be double-assigned,
    # since nothing else advertises it. A claim row carries an issue, a branch and
    # a real worktree, so it fails all three #683b exemption conditions and is
    # never skipped; that is checked by test, not left to reasoning, because
    # those conditions have changed before.
    if [ -n "$CLAIMS" ]; then
      while IFS= read -r rec; do
        [ -n "$rec" ] || continue
        parse_claim_record "$rec"
        for b in $LIVE_ROLES; do
          eb="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$b" '.[$w].roles[$r]')"
          rb="$(printf '%s' "$eb" | jq -r '.repo // ""')"
          ib="$(printf '%s' "$eb" | jq -r '.issue // ""')"
          bb="$(printf '%s' "$eb" | jq -r '.branch // ""')"
          cb="$(printf '%s' "$eb" | jq -r '.cwd // ""')"
          report_overlap "claim(pid $C_PID)" "$C_ISSUE" "$C_BRANCH" "$C_WT" "$C_REPO" \
            "$b" "$ib" "$bb" "$cb" "$rb"
        done
      done <<EOF
$CLAIMS
EOF
    fi
    # Announce the exemption (#683) - a skipped check the reader cannot see is a
    # blind spot, so name who was skipped and why rather than just going quiet.
    if [ -n "$EXEMPT_ROLES" ]; then
      echo "  info: overlap checks skipped for lane-less live role(s):${EXEMPT_ROLES} (orchestrator never holds a lane; others declared no issue, no branch, and a shared-parent cwd). Applies until they declare one."
    fi
    [ "$WARNED" -eq 1 ] && echo "flow-wave-registry: lane overlap detected - do not co-schedule the flagged pairs." >&2
    if [ "$UNADDRESSED" -gt 0 ]; then
      echo "  BOOTSTRAP: $UNADDRESSED LIVE role(s) have no address - they cannot be messaged, and no from= can be observed for them."
      echo "  Verification cannot fire for those roles on its own; it is blocked, not pending."
      bootstrap_escapes
    fi
    cross_wave_notes
    echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
    echo "FLOW_WAVE: listed"
    exit 0
    ;;
esac
