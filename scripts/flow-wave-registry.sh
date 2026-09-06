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
# Wave policy (issue #699): the registry records a role, an address and a lane.
# Everything else a wave RUNS ON - implementation authority, the gate point, who
# judges, the ledger format, the file lane, the authority model - lived in prose
# the orchestrator retyped into every message. That prose is where the
# 2026-08-11 wave's orchestration errors happened, and it is the one thing that
# does NOT survive a worker's /clear, which is what this registry exists to
# survive. So policy is DECLARED DATA in two tiers: wave-level fields set once
# by the orchestrator (`policy set`) and INHERITED by every worker, plus
# role-level facts each session declares for itself (--model, --permission-mode,
# --files, --capacity).
#
# A DECLARED POLICY NOBODY READS IS DECORATION - the issue says so, and it is the
# design constraint this implementation is judged against. Four things read it
# back, so a broken policy is distinguishable from a working one:
#   1. `register` REPRINTS the policy on every registration - the compaction-proof
#      re-brief. Re-registering already was "the cheap re-brief" for addressing;
#      this extends it to the protocol.
#   2. `register`/`get` into a wave with NO policy report FLOW_WAVE_POLICY=absent
#      and advise, so implementation authority is visible at registration rather
#      than after a user round-trip (the #699 item-3 failure).
#   3. Each role records the policy rev it was briefed on. A role briefed on a
#      SUPERSEDED rev reads `brief=stale` in `list`/`get` - a policy amended
#      after workers registered is exactly the drift an unread field would hide.
#   4. Declared FILE LANES participate in overlap detection, like a branch or a
#      worktree. Every real collision in the reference wave was file-level, and
#      all of it was managed by the orchestrator holding paths in prose.
#
# Advisory discipline is unchanged (#674): the policy adds detail lines and
# warnings, never a new exit code. Only a malformed enum is a usage error, and
# that is a caller bug, not a wave state.
#
# Usage:
#   flow-wave-registry.sh register <role> [--wave W] [--force] [--cwd P]
#                         [--repo P] [--issue N] [--branch B] [--socket S]
#                         [--model M] [--permission-mode P] [--files A,B]
#                         [--capacity C]
#   flow-wave-registry.sh policy set  [--wave W] [--driver D] [--authority A]
#                         [--authority-model M] [--gate G] [--ledger L]
#                         [--merge-authority M] [--deploy-policy D] [--repo P]
#   flow-wave-registry.sh policy show [--wave W] [--json]
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
#             ALSO records this session's ROLE-LEVEL FACTS (#699) - --model,
#             --permission-mode, --files (the file lane), --capacity - and
#             REPRINTS the wave policy, which makes re-registering a re-brief of
#             the PROTOCOL and not just the address. The two facts that exist
#             purely to change a downstream decision: --permission-mode, because
#             a session that will hit permission prompts cannot take unattended
#             work and routing it there wastes a cycle; and --model, because the
#             hardest issue should not go to the smallest model.
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
#             Renders the wave POLICY header when one is declared, and names
#             roles whose brief is STALE (#699). Declared FILE LANES join the
#             same overlap predicate as branches and worktrees: two live roles in
#             one repo naming a common path WARN. That check is exact-match on
#             declared paths, deliberately - a glob-expanding or prefix-guessing
#             comparison would invent collisions the roles never declared, and an
#             overlap warning nobody believes is the #683 failure repeating.
#             ALSO joins the #676 MAILBOX so a role's WATCH state is visible
#             (#778). A role could be `live`, address-`verified` and
#             `brief=current` and still be completely DEAF: arming the mailbox
#             watch is the one element of participation that left no trace in
#             the roster when it was missing. In the `kyle-completion` wave on
#             2026-09-05 a worker skipped step 4 of /flow:register, read
#             `[live, verified] brief=current` for over an hour, and never saw
#             its six-issue assignment; both sides looked healthy and the only
#             tell was `flow-wave-mailbox.sh list` showing `CURSOR 0 / UNREAD 2`,
#             found by accident. So each LIVE role now renders `watch=armed`,
#             `watch=stale(42m)` or `watch=ABSENT`, plus `unread=N since <ts>`
#             and a loud `** NEVER READ **` when the cursor is 0 against a
#             non-zero rev - the unambiguous "has consumed nothing, ever" case,
#             which a count alone does not say.
#             TWO BOUNDS, both deliberate. The data comes from ONE call to the
#             sibling `flow-wave-mailbox.sh list --json`, never from reading box
#             files here: the mailbox owns that format, and a roster that
#             reimplemented it would drift. That call FAILS OPEN - a missing,
#             unreadable or erroring sibling yields `watch=unknown`, renders
#             nothing and warns about nothing, because a broken mailbox must
#             never break the roster. And watch state is rendered ONLY when the
#             mailbox lane is IN USE in this wave (at least one box or one
#             heartbeat exists); in a wave that never uses it, every role would
#             otherwise read ABSENT, which is a flag firing on 100% of the fleet
#             and carrying zero signal - the #674 rule, restated.
#   get       key=value contract for one role (for scripting). Deliberately does
#             NOT carry watch state (#778): the deafness gap is a property of the
#             roster SWEEP, and `get` answers "where do I send to this role?".
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
#   policy    Wave-level policy (issue #699), declared ONCE and inherited by
#             every role in the wave.
#             `set`  writes the fields given and bumps the rev; fields NOT given
#                    are left alone, so amending one field is a one-flag call.
#                    Every set is stamped with who declared it, so the roster can
#                    say which sessions were briefed before the amendment.
#             `show` prints the policy (--json for the object). No policy yet is
#                    reported as `policy_absent`, NOT as an error: a wave with no
#                    declared policy is a normal early state, and the whole point
#                    is that it is VISIBLE instead of implicit.
#             --authority and --authority-model are VALIDATED against their
#             enums; a typo there is a usage error (exit 2) rather than a silently
#             stored value nobody can act on. The remaining fields are free text -
#             they are read by humans and the wording is the content.
#   self-address  Print this session's best-guess socket (bootstrap only).
#                 Prints why on failure - see FLOW_WAVE_SOCKET_REASON below.
#
# Output ends with a machine-readable verdict line:
#   FLOW_WAVE: registered | updated | refused | released | listed | verified |
#              address_filled | mismatch-corrected | free | unknown |
#              policy_set | policy_shown | policy_absent | error
# preceded by detail lines (FLOW_WAVE_ROLE=, FLOW_WAVE_SOCKET=, ...), '-' when
# not applicable. Exit codes: 0 normal, 1 refused (live-owner conflict),
# 2 usage error. `policy_absent` is a STATE, not a failure, and exits 0 - a new
# verdict must never become a new exit code (#674), or a `set -euo pipefail`
# caller aborts on a wave that has simply not declared its policy yet.
#
# Wave policy detail lines (#699), emitted by register/get/list/policy:
#   FLOW_WAVE_POLICY         declared | absent
#   FLOW_WAVE_POLICY_REV     the wave policy's current revision (0 when absent)
#   FLOW_WAVE_POLICY_DRIVER  flow:auto | codex:auto | ... (free text)
#   FLOW_WAVE_POLICY_AUTHORITY        implement | file-issues-only
#   FLOW_WAVE_POLICY_AUTHORITY_MODEL  orchestrator-only | user-and-orchestrator
#   FLOW_WAVE_POLICY_GATE / _LEDGER / _MERGE_AUTHORITY / _DEPLOY / _REPO / _TS
#   FLOW_WAVE_BRIEFED_REV    the policy rev THIS role was briefed on (register/get)
#   FLOW_WAVE_BRIEF          current | stale | none. `stale` means the policy was
#                            amended after this role registered - re-register to
#                            take the re-brief.
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
# Mailbox/watch detail lines (#778), emitted by list only:
#   FLOW_WAVE_WATCH_UNARMED  count of LIVE roles with no armed watch (0 when the
#                            mailbox lane is unused or unreadable)
#   FLOW_WAVE_UNREAD         total messages sitting unread across the wave
#
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
#   FLOW_WAVE_MAILBOX_DIR   mailbox wave-root override, passed through to the
#                           sibling helper so the two always co-locate (#778)
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
#
# Lane 3 is the #676 mailbox. It produces no address by itself (a mailbox write
# carries no from=), but it is the only lane that REACHES a counterpart holding
# no address, and it wakes them - so it belongs above the human relay, which on
# 2026-08-11 was reached first and cost ~2h.
bootstrap_escapes() {
  echo "  Bootstrap lanes that do NOT depend on self-derivation:" >&2
  echo "    1. re-run this register - the socket dir is created lazily, so a" >&2
  echo "       retry once this session has a socket adopts the real address." >&2
  echo "    2. register --socket <addr> - pass an address learned by any means" >&2
  echo "       (harness env, the user relaying it from the other session)." >&2
  echo "    3. mailbox hello - flow-wave-mailbox.sh send --to <role> [--from R]," >&2
  echo "       then arm 'watch --role <yours>'. No address needed to deliver, and" >&2
  echo "       the counterpart's REPLY carries the observable from=." >&2
  echo "    4. user-relayed hello (LAST RESORT) - the user pastes this session's" >&2
  echo "       FLOW_WAVE_* block to the counterpart, whose reply carries a from=." >&2
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

# shared_files A_FILES B_FILES -> prints the paths declared by BOTH lanes.
#
# File lanes are comma-separated declared paths (#699 item 6). Comparison is
# EXACT on the declared strings, normalized only for surrounding whitespace and
# a trailing slash. Deliberately not glob expansion, not prefix containment, not
# realpath resolution: those invent collisions the roles never declared, and this
# warning has to be believed to be worth having - the #683 lesson that a check
# firing on the normal case trains everyone to ignore it. A lane that declares
# `.claude/commands/flow/` and one that declares
# `.claude/commands/flow/register.md` therefore do NOT collide here; declare the
# same string on both sides when they should.
norm_path() { # trim surrounding whitespace + one trailing slash; keeps inner spaces
  local p="$1"
  p="${p#"${p%%[![:space:]]*}"}"
  p="${p%"${p##*[![:space:]]}"}"
  printf '%s' "${p%/}"
}

shared_files() {
  local a="$1" b="$2" pa pb out=""
  [ -n "$a" ] && [ -n "$b" ] || return 0
  while IFS= read -r pa; do
    pa="$(norm_path "$pa")"
    [ -n "$pa" ] || continue
    while IFS= read -r pb; do
      pb="$(norm_path "$pb")"
      [ -n "$pb" ] || continue
      [ "$pa" = "$pb" ] && out="$out$pa "
    done <<EOF
$(printf '%s' "$b" | tr ',' '\n')
EOF
  done <<EOF
$(printf '%s' "$a" | tr ',' '\n')
EOF
  printf '%s' "${out% }"
  return 0
}

# report_overlap A_LABEL A_ISS A_BR A_CWD A_REPO B_LABEL B_ISS B_BR B_CWD B_REPO
#                [A_FILES B_FILES]
#
# The ONE lane-overlap predicate, shared by role-vs-role and claim-vs-role
# (#687). Extracted rather than copied: a safety check written twice drifts, and
# two copies disagreeing about what counts as a collision is the hazard
# `tool-risk-drift` exists to catch for the permission taxonomy. Precedence and
# wording are unchanged from #638/#683 - only the call sites are new.
# Sets WARNED=1 on a warning; info-level shared-repo never does.
#
# The file-lane arm (#699) sits BELOW the three lane checks and ABOVE the
# shared-repo info. Below, because a shared branch or nested worktree is a
# stronger statement about the same pair and would only be masked by a file
# warning; above, because "these two share a repo, which is normal" is precisely
# the answer that hid every file-level collision in the reference wave. Both file
# arguments are optional so the claim call site - which has no declared lane to
# offer - passes nothing and behaves exactly as before.
report_overlap() {
  local al="$1" ia="$2" ba="$3" ca="$4" ra="$5"
  local bl="$6" ib="$7" bb="$8" cb="$9" rb="${10}"
  local fa="${11:-}" fb="${12:-}" shared
  shared="$(shared_files "$fa" "$fb")"
  if [ -n "$ia" ] && [ "$ia" = "$ib" ] && [ -n "$ra" ] && [ "$ra" = "$rb" ]; then
    echo "  WARNING: '$al' and '$bl' both claim issue #$ia in $ra - two sessions on one issue race each other's worktrees (#597)."
    WARNED=1
  elif [ -n "$ba" ] && [ "$ba" = "$bb" ]; then
    echo "  WARNING: '$al' and '$bl' both claim branch '$ba' - same checkout, guaranteed collision."
    WARNED=1
  elif [ -n "$ca" ] && [ -n "$cb" ] && { [ "$ca" = "$cb" ] || case "$ca/" in "$cb"/*) true ;; *) false ;; esac || case "$cb/" in "$ca"/*) true ;; *) false ;; esac; }; then
    echo "  WARNING: '$al' ($ca) and '$bl' ($cb) have same/nested worktrees - edits will collide."
    WARNED=1
  elif [ -n "$ra" ] && [ "$ra" = "$rb" ] && [ -n "$shared" ]; then
    echo "  WARNING: '$al' and '$bl' declare overlapping FILE LANES in $ra: $shared - separate worktrees do not prevent a merge conflict (#699)."
    WARNED=1
  elif [ -n "$ra" ] && [ "$ra" = "$rb" ]; then
    echo "  info: '$al' and '$bl' share repo $ra (separate worktrees - the normal wave shape)."
  fi
}

# ---- wave policy (issue #699) -----------------------------------------------
#
# Stored at .[$wave].policy, a SIBLING of .[$wave].roles. Roles keep their exact
# shape and location, so every existing consumer indexes them unchanged - the
# same reason #687 hung claim rows off a sibling key instead of nesting roles.
#
# The rev is the load-bearing field. Without it a policy amended after the
# workers registered is indistinguishable from one they were all briefed on, and
# "declared but nobody re-read it" is precisely the decoration failure the issue
# warns about. Each role stores the rev it was briefed on; the roster compares.

# policy_json WAVE -> the policy object, or 'null'
policy_json() {
  read_registry | jq -c --arg w "$1" '.[$w].policy // null'
}

policy_field() { # policy_field POLICY_JSON KEY -> value or ''
  printf '%s' "$1" | jq -r --arg k "$2" '.[$k] // "" | if . == null then "" else . end'
}

policy_rev_of() { # policy_rev_of POLICY_JSON -> integer (0 when absent)
  local p="$1"
  [ "$p" = "null" ] && { printf '0'; return; }
  printf '%s' "$p" | jq -r '.rev // 0'
}

# emit_policy_lines POLICY_JSON - the FLOW_WAVE_POLICY_* detail block.
#
# Printed on EVERY register/get/list/policy call, present or absent. Absent is
# reported as a value rather than by omitting the lines: a consumer that greps
# for FLOW_WAVE_POLICY_AUTHORITY must be able to tell "no policy declared" from
# "this call does not report policy", and a missing line answers neither.
emit_policy_lines() {
  local p="$1"
  if [ "$p" = "null" ]; then
    echo "FLOW_WAVE_POLICY=absent"
    echo "FLOW_WAVE_POLICY_REV=0"
    echo "FLOW_WAVE_POLICY_DRIVER=-"
    echo "FLOW_WAVE_POLICY_AUTHORITY=-"
    echo "FLOW_WAVE_POLICY_AUTHORITY_MODEL=-"
    echo "FLOW_WAVE_POLICY_GATE=-"
    echo "FLOW_WAVE_POLICY_LEDGER=-"
    echo "FLOW_WAVE_POLICY_MERGE_AUTHORITY=-"
    echo "FLOW_WAVE_POLICY_DEPLOY=-"
    echo "FLOW_WAVE_POLICY_REPO=-"
    echo "FLOW_WAVE_POLICY_TS=-"
    return
  fi
  echo "FLOW_WAVE_POLICY=declared"
  echo "FLOW_WAVE_POLICY_REV=$(policy_rev_of "$p")"
  echo "FLOW_WAVE_POLICY_DRIVER=$(policy_field "$p" driver)"
  echo "FLOW_WAVE_POLICY_AUTHORITY=$(policy_field "$p" authority)"
  echo "FLOW_WAVE_POLICY_AUTHORITY_MODEL=$(policy_field "$p" authority_model)"
  echo "FLOW_WAVE_POLICY_GATE=$(policy_field "$p" gate)"
  echo "FLOW_WAVE_POLICY_LEDGER=$(policy_field "$p" ledger)"
  echo "FLOW_WAVE_POLICY_MERGE_AUTHORITY=$(policy_field "$p" merge_authority)"
  echo "FLOW_WAVE_POLICY_DEPLOY=$(policy_field "$p" deploy_policy)"
  echo "FLOW_WAVE_POLICY_REPO=$(policy_field "$p" repo)"
  echo "FLOW_WAVE_POLICY_TS=$(policy_field "$p" ts)"
}

# print_policy_brief POLICY_JSON - the human-readable re-brief, on STDOUT.
#
# This is the mechanic the issue is built around: a worker that lost its context
# recovers the PROTOCOL by re-registering, not just its address. The block is
# printed in full every time rather than diffed against what the session might
# already know - a compacted session's "already know" is exactly what cannot be
# trusted, and the whole block costs a few lines.
print_policy_brief() {
  local p="$1"
  [ "$p" != "null" ] || return 0
  echo "  -- wave policy (rev $(policy_rev_of "$p"), declared by $(policy_field "$p" declared_by)) --"
  [ -n "$(policy_field "$p" driver)" ]           && echo "     driver:               $(policy_field "$p" driver)"
  [ -n "$(policy_field "$p" authority)" ]        && echo "     implementation auth:  $(policy_field "$p" authority)"
  [ -n "$(policy_field "$p" authority_model)" ]  && echo "     authority model:      $(policy_field "$p" authority_model)"
  [ -n "$(policy_field "$p" gate)" ]             && echo "     gate policy:          $(policy_field "$p" gate)"
  [ -n "$(policy_field "$p" ledger)" ]           && echo "     ledger format:        $(policy_field "$p" ledger)"
  [ -n "$(policy_field "$p" merge_authority)" ]  && echo "     merge authority:      $(policy_field "$p" merge_authority)"
  [ -n "$(policy_field "$p" deploy_policy)" ]    && echo "     deploy policy:        $(policy_field "$p" deploy_policy)"
  [ -n "$(policy_field "$p" repo)" ]             && echo "     repo:                 $(policy_field "$p" repo)"
  return 0
}

# brief_state BRIEFED_REV CURRENT_REV -> current | stale | none
brief_state() {
  local briefed="$1" cur="$2"
  [ "$cur" = "0" ] && { echo none; return; }
  [ -n "$briefed" ] && [ "$briefed" != "0" ] && [ "$briefed" -ge "$cur" ] 2>/dev/null &&
    { echo current; return; }
  echo stale
}

# --- The mailbox / watch join (#778) -------------------------------------------
#
# The registry answers "who and where"; the #676 mailbox answers "did it arrive"
# and, since #778, "is anyone listening". Joining the second onto the roster is
# what turns a deaf worker from a lucky cross-reference into one look.
#
# The join goes through the sibling helper's own `list --json`, never through
# reading `outbox-*.md` / `.cursor-*` / `.watch-*` here. The mailbox OWNS that
# format - it has already changed twice - and a roster that reimplemented the
# parse would drift silently into reporting a healthy wave that is not one,
# which is the failure class this whole join exists to remove.

MAILBOX_JSON=""      # cached `list --json` payload; "" = unavailable
MAILBOX_IN_USE=0     # 1 when this wave has at least one box or one heartbeat

# Populate MAILBOX_JSON / MAILBOX_IN_USE for $WAVE. FAILS OPEN in every failure
# mode: a missing sibling, a non-zero exit, unparseable output - all leave
# MAILBOX_JSON empty, which renders nothing and warns about nothing. A broken
# mailbox must never break the roster, exactly as a broken lexicon validator
# must never block a send (#701).
load_mailbox() {
  local self_dir mb out body
  self_dir="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
  mb="$self_dir/flow-wave-mailbox.sh"
  [ -r "$mb" ] || return 0
  out="$(bash "$mb" list --wave "$WAVE" --json 2>/dev/null)" || return 0
  # The helper prints its FLOW_MAILBOX_* contract after the JSON; split on the
  # first contract line rather than a fixed offset, so a detail line added
  # there can never silently break this parse.
  body="$(printf '%s\n' "$out" | sed -n '/^FLOW_MAILBOX/q;p')"
  [ -n "$body" ] || return 0
  printf '%s' "$body" | jq -e . >/dev/null 2>&1 || return 0
  MAILBOX_JSON="$body"
  [ "$(printf '%s' "$MAILBOX_JSON" | jq -r '((.boxes // []) | length) + ((.watches // []) | length)')" -gt 0 ] 2>/dev/null &&
    MAILBOX_IN_USE=1
  return 0
}

# mailbox_watch_state ROLE -> armed | stale | absent | unknown
# `unknown` covers both "no mailbox data at all" and "this wave does not use the
# lane", and is the value that renders nothing.
mailbox_watch_state() {
  [ -n "$MAILBOX_JSON" ] && [ "$MAILBOX_IN_USE" -eq 1 ] || { echo unknown; return; }
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$1" '(.watches // []) | map(select(.role == $r)) | (.[0].state // "absent")'
}

# mailbox_watch_age ROLE -> seconds since the last heartbeat, '-' when none.
mailbox_watch_age() {
  [ -n "$MAILBOX_JSON" ] || { echo '-'; return; }
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$1" '(.watches // []) | map(select(.role == $r)) | (.[0].age_secs // "-") | tostring'
}

# mailbox_box_field ROLE FIELD -> that field of the role's OWN box, '-' when the
# role has none. A worker reads outbox-<role>.md; the orchestrator reads every
# inbox-*.md, so its figures are AGGREGATED (summed unread, and 'never read'
# only when it has consumed nothing from any of them).
mailbox_box_field() {
  local role="$1" field="$2"
  [ -n "$MAILBOX_JSON" ] || { echo '-'; return; }
  if [ "$role" = "orchestrator" ]; then
    case "$field" in
      unread) printf '%s' "$MAILBOX_JSON" | jq -r '[(.boxes // [])[] | select(.reader == "orchestrator") | .unread] | add // "-"' ;;
      rev)    printf '%s' "$MAILBOX_JSON" | jq -r '[(.boxes // [])[] | select(.reader == "orchestrator") | .rev] | add // "-"' ;;
      cursor) printf '%s' "$MAILBOX_JSON" | jq -r '[(.boxes // [])[] | select(.reader == "orchestrator") | .cursor] | add // "-"' ;;
      mtime)  printf '%s' "$MAILBOX_JSON" | jq -r '[(.boxes // [])[] | select(.reader == "orchestrator") | .mtime] | max // "-"' ;;
    esac
    return
  fi
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$role" --arg f "$field" \
      '(.boxes // []) | map(select(.reader == $r)) | (.[0][$f] // "-") | tostring'
}

# A role that has NEVER consumed anything, against a box that holds something.
# Its own marker rather than a count, because "cursor 0 with a non-zero rev" is
# the unambiguous statement that nothing has EVER been read - which is what the
# 2026-09-05 worker's roster entry could not say (#778).
mailbox_never_read() {
  local rev cur
  rev="$(mailbox_box_field "$1" rev)"; cur="$(mailbox_box_field "$1" cursor)"
  [ "$rev" != "-" ] && [ "$cur" != "-" ] && [ "$rev" -gt 0 ] && [ "$cur" -eq 0 ] 2>/dev/null
}

# Render a heartbeat age the way a sweeping human reads it: stale(42m), not
# stale(2520s).
human_age() {
  local a="$1"
  case "$a" in ''|*[!0-9]*) echo '?'; return ;; esac
  if [ "$a" -lt 90 ]; then echo "${a}s"
  elif [ "$a" -lt 5400 ]; then echo "$((a / 60))m"
  else echo "$((a / 3600))h"; fi
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
[ -n "$VERB" ] || usage_fail "usage: flow-wave-registry.sh register|policy|list|get|verify|release|self-address ..."
shift

case "$VERB" in
  register | list | get | verify | release | self-address | policy) : ;;
  --help | -h)
    # Print the whole comment header rather than a hand-counted line range: the
    # old fixed `2,96p` silently truncated the moment the header grew, so --help
    # stopped mid-sentence and never mentioned the verbs added after it (#699).
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB" ;;
esac

ROLE=""; WAVE="default"; WAVE_EXPLICIT=0; FORCE=0; JSON_OUT=0
A_CWD=""; A_REPO=""; A_ISSUE=""; A_BRANCH=""; A_SOCKET=""; A_FROM=""
# Role-level facts (#699). Each is unset-by-default and only written when given,
# so a re-register that omits one never blanks what a fuller one recorded.
A_MODEL=""; A_PERMMODE=""; A_FILES=""; A_CAPACITY=""
A_MODEL_SET=0; A_PERMMODE_SET=0; A_FILES_SET=0; A_CAPACITY_SET=0
# Wave-level policy fields (#699). Same rule: `policy set` is a MERGE, so an
# amendment names one flag rather than restating the whole policy - restating it
# is how a field gets silently dropped.
P_DRIVER=""; P_AUTHORITY=""; P_AUTHORITY_MODEL=""; P_GATE=""; P_LEDGER=""
P_MERGE_AUTHORITY=""; P_DEPLOY=""
P_DRIVER_SET=0; P_AUTHORITY_SET=0; P_AUTHORITY_MODEL_SET=0; P_GATE_SET=0
P_LEDGER_SET=0; P_MERGE_AUTHORITY_SET=0; P_DEPLOY_SET=0

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
    --model) [ "$#" -ge 2 ] || usage_fail "--model requires a name"; A_MODEL="$2"; A_MODEL_SET=1; shift ;;
    --model=*) A_MODEL="${1#--model=}"; A_MODEL_SET=1 ;;
    --permission-mode) [ "$#" -ge 2 ] || usage_fail "--permission-mode requires a value"; A_PERMMODE="$2"; A_PERMMODE_SET=1; shift ;;
    --permission-mode=*) A_PERMMODE="${1#--permission-mode=}"; A_PERMMODE_SET=1 ;;
    --files) [ "$#" -ge 2 ] || usage_fail "--files requires a comma-separated path list"; A_FILES="$2"; A_FILES_SET=1; shift ;;
    --files=*) A_FILES="${1#--files=}"; A_FILES_SET=1 ;;
    --capacity) [ "$#" -ge 2 ] || usage_fail "--capacity requires a value"; A_CAPACITY="$2"; A_CAPACITY_SET=1; shift ;;
    --capacity=*) A_CAPACITY="${1#--capacity=}"; A_CAPACITY_SET=1 ;;
    --driver) [ "$#" -ge 2 ] || usage_fail "--driver requires a value"; P_DRIVER="$2"; P_DRIVER_SET=1; shift ;;
    --driver=*) P_DRIVER="${1#--driver=}"; P_DRIVER_SET=1 ;;
    --authority) [ "$#" -ge 2 ] || usage_fail "--authority requires a value"; P_AUTHORITY="$2"; P_AUTHORITY_SET=1; shift ;;
    --authority=*) P_AUTHORITY="${1#--authority=}"; P_AUTHORITY_SET=1 ;;
    --authority-model) [ "$#" -ge 2 ] || usage_fail "--authority-model requires a value"; P_AUTHORITY_MODEL="$2"; P_AUTHORITY_MODEL_SET=1; shift ;;
    --authority-model=*) P_AUTHORITY_MODEL="${1#--authority-model=}"; P_AUTHORITY_MODEL_SET=1 ;;
    --gate) [ "$#" -ge 2 ] || usage_fail "--gate requires a value"; P_GATE="$2"; P_GATE_SET=1; shift ;;
    --gate=*) P_GATE="${1#--gate=}"; P_GATE_SET=1 ;;
    --ledger) [ "$#" -ge 2 ] || usage_fail "--ledger requires a value"; P_LEDGER="$2"; P_LEDGER_SET=1; shift ;;
    --ledger=*) P_LEDGER="${1#--ledger=}"; P_LEDGER_SET=1 ;;
    --merge-authority) [ "$#" -ge 2 ] || usage_fail "--merge-authority requires a value"; P_MERGE_AUTHORITY="$2"; P_MERGE_AUTHORITY_SET=1; shift ;;
    --merge-authority=*) P_MERGE_AUTHORITY="${1#--merge-authority=}"; P_MERGE_AUTHORITY_SET=1 ;;
    --deploy-policy) [ "$#" -ge 2 ] || usage_fail "--deploy-policy requires a value"; P_DEPLOY="$2"; P_DEPLOY_SET=1; shift ;;
    --deploy-policy=*) P_DEPLOY="${1#--deploy-policy=}"; P_DEPLOY_SET=1 ;;
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

  policy)
    # ROLE carries the sub-verb here (the parser's single positional slot).
    SUB="${ROLE:-show}"
    case "$SUB" in
      set | show) : ;;
      *) usage_fail "policy takes 'set' or 'show', not '$SUB'" ;;
    esac
    E_ROLE="-"
    implicit_default &&
      echo "flow-wave-registry: no --wave given - operating on wave 'default'; a named wave's policy is elsewhere." >&2

    if [ "$SUB" = "show" ]; then
      POL="$(policy_json "$WAVE")"
      if [ "$JSON_OUT" -eq 1 ]; then
        printf '%s\n' "$POL" | jq .
      else
        if [ "$POL" = "null" ]; then
          echo "flow-wave-registry: wave '$WAVE' has no declared policy."
        else
          echo "Wave '$WAVE' policy ($REG_FILE):"
          print_policy_brief "$POL"
        fi
      fi
      emit_policy_lines "$POL"
      [ "$POL" = "null" ] && { echo "FLOW_WAVE: policy_absent"; exit 0; }
      echo "FLOW_WAVE: policy_shown"
      exit 0
    fi

    # --- policy set ---
    # Validate the two enums that CHANGE WHAT A WORKER DOES. A typo in
    # `--authority impelment` stored verbatim is worse than no policy at all: it
    # reads as declared, and the field's whole job is to answer "may this wave
    # write code?" without a user round-trip. The free-text fields are read by
    # humans and carry their meaning in their wording, so validating them would
    # only invent a vocabulary nobody agreed to (that is #701's job, for
    # transitions - not this issue's, for state).
    if [ "$P_AUTHORITY_SET" -eq 1 ]; then
      case "$P_AUTHORITY" in
        implement | file-issues-only) : ;;
        *) usage_fail "--authority must be 'implement' or 'file-issues-only' (got '$P_AUTHORITY')" ;;
      esac
    fi
    if [ "$P_AUTHORITY_MODEL_SET" -eq 1 ]; then
      case "$P_AUTHORITY_MODEL" in
        orchestrator-only | user-and-orchestrator) : ;;
        *) usage_fail "--authority-model must be 'orchestrator-only' or 'user-and-orchestrator' (got '$P_AUTHORITY_MODEL')" ;;
      esac
    fi
    if [ "$P_DRIVER_SET" -eq 0 ] && [ "$P_AUTHORITY_SET" -eq 0 ] &&
       [ "$P_AUTHORITY_MODEL_SET" -eq 0 ] && [ "$P_GATE_SET" -eq 0 ] &&
       [ "$P_LEDGER_SET" -eq 0 ] && [ "$P_MERGE_AUTHORITY_SET" -eq 0 ] &&
       [ "$P_DEPLOY_SET" -eq 0 ] && [ -z "$A_REPO" ]; then
      usage_fail "policy set needs at least one field (--driver/--authority/--authority-model/--gate/--ledger/--merge-authority/--deploy-policy/--repo)"
    fi
    # NEVER put a `?` (or any try/catch) inside this `|=` body. On jq 1.6 the
    # update operator evaluates its body as a PATH expression, and `?` makes that
    # backtrack - `_modify` then treats the path as absent and DELETES the key it
    # was asked to update. The whole policy object vanished with no error and no
    # non-zero exit; `with_lock` reported success because jq exited 0. Numeric
    # coercion (`$pid | tonumber? // $pid`) is safe in the object CONSTRUCTOR
    # `register` uses a few lines below, which is a plain `=` assignment - it is
    # only unsafe here, which is exactly the kind of difference that gets copied
    # across by hand. `declared_pid` is stored as the raw string instead; nothing
    # compares it numerically.
    with_lock '
      .[$w] //= {"roles": {}} |
      .[$w].policy //= {} |
      .[$w].policy |=
        ( (if $driver_set  == "1" then .driver          = $driver  else . end)
        | (if $auth_set    == "1" then .authority       = $auth    else . end)
        | (if $authm_set   == "1" then .authority_model = $authm   else . end)
        | (if $gate_set    == "1" then .gate            = $gate    else . end)
        | (if $ledger_set  == "1" then .ledger          = $ledger  else . end)
        | (if $merge_set   == "1" then .merge_authority = $merge   else . end)
        | (if $deploy_set  == "1" then .deploy_policy   = $deploy  else . end)
        | (if $repo        == ""  then . else .repo     = $repo    end)
        | .rev           = ((.rev // 0) + 1)
        | .ts            = ($now | tonumber)
        | .declared_by   = $by
        | .declared_pid  = $pid
        | .declared_session = $session
        )' \
      --arg w "$WAVE" --arg driver "$P_DRIVER" --arg driver_set "$P_DRIVER_SET" \
      --arg auth "$P_AUTHORITY" --arg auth_set "$P_AUTHORITY_SET" \
      --arg authm "$P_AUTHORITY_MODEL" --arg authm_set "$P_AUTHORITY_MODEL_SET" \
      --arg gate "$P_GATE" --arg gate_set "$P_GATE_SET" \
      --arg ledger "$P_LEDGER" --arg ledger_set "$P_LEDGER_SET" \
      --arg merge "$P_MERGE_AUTHORITY" --arg merge_set "$P_MERGE_AUTHORITY_SET" \
      --arg deploy "$P_DEPLOY" --arg deploy_set "$P_DEPLOY_SET" \
      --arg repo "$A_REPO" --arg now "$NOW" --arg by "${CLAUDE_CODE_SESSION_ID:-$SELF_PID}" \
      --arg pid "$SELF_PID" --arg session "$SELF_SESSION"
    POL="$(policy_json "$WAVE")"
    echo "Wave '$WAVE' policy set (rev $(policy_rev_of "$POL")):"
    print_policy_brief "$POL"
    # Name who is now carrying a superseded brief (#699 reader 3). An amendment
    # nobody re-reads is the decoration failure, and the moment it happens is the
    # cheapest moment to say so - the orchestrator is right here.
    STALE_ROLES=""
    CUR_REV="$(policy_rev_of "$POL")"
    REG="$(read_registry)"
    for r in $(printf '%s' "$REG" | jq -r --arg w "$WAVE" '(.[$w].roles // {}) | keys[]' 2>/dev/null); do
      e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
      [ "$(liveness_of "$e")" = "live" ] || continue
      br="$(printf '%s' "$e" | jq -r '.policy_rev // 0')"
      [ "$(brief_state "$br" "$CUR_REV")" = "stale" ] && STALE_ROLES="$STALE_ROLES $r"
    done
    if [ -n "$STALE_ROLES" ]; then
      echo "flow-wave-registry: live role(s) briefed on an older policy rev:${STALE_ROLES}" >&2
      echo "  They are running on superseded rules until each re-registers (the re-brief) or is sent the new policy." >&2
    fi
    emit_policy_lines "$POL"
    echo "FLOW_WAVE: policy_set"
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
    # The rev this registration is briefed on (#699). Recorded at register time
    # so a later amendment can be told apart from one this session has seen -
    # which is what makes `brief=stale` a fact rather than a guess.
    POL="$(policy_json "$WAVE")"
    POL_REV="$(policy_rev_of "$POL")"
    # Role-level facts are PRESERVED when their flag is omitted, unlike
    # cwd/repo/issue/branch above, which a re-register rewrites. The difference is
    # deliberate and worth stating: those describe a LANE, which genuinely goes
    # stale (the #683 trap), while model / permission mode / capacity / file lane
    # describe the SESSION and its grant, and re-registering is the documented
    # cheap re-brief (#670). Blanking a granted file lane because a compacted
    # worker re-registered to re-read the protocol would delete the very thing
    # overlap detection reads. Passing an empty value (`--files ""`) clears a
    # field explicitly - the flag was given, so intent is unambiguous.
    with_lock '
      .[$w] //= {"roles": {}} |
      (.[$w].roles[$r] // {}) as $prev |
      .[$w].roles[$r] = {
        socket: $sock, self_socket: $selfsock, pid: ($pid | tonumber? // $pid),
        session: $session, host: $host, cwd: $cwd, repo: $repo,
        issue: $issue, branch: $branch, registered_ts: ($now | tonumber),
        verified: ($verified == "true"), address_mismatch: ($mismatch == "true"),
        address_filled: ($filled == "true"), released: false,
        model:           (if $model_set == "1" then $model else ($prev.model // "") end),
        permission_mode: (if $perm_set  == "1" then $perm  else ($prev.permission_mode // "") end),
        files:           (if $files_set == "1" then $files else ($prev.files // "") end),
        capacity:        (if $cap_set   == "1" then $cap   else ($prev.capacity // "") end),
        policy_rev:      ($polrev | tonumber)
      }' \
      --arg w "$WAVE" --arg r "$ROLE" --arg sock "$SOCK" --arg pid "$SELF_PID" \
      --arg selfsock "$SELF_SOCK" --arg verified "$KEEP_VERIFIED" \
      --arg filled "$KEEP_FILLED" --arg mismatch "$KEEP_MISMATCH" \
      --arg session "$SELF_SESSION" --arg host "$SELF_HOST" --arg cwd "$A_CWD" \
      --arg repo "$A_REPO" --arg issue "$A_ISSUE" --arg branch "$A_BRANCH" \
      --arg model "$A_MODEL" --arg model_set "$A_MODEL_SET" \
      --arg perm "$A_PERMMODE" --arg perm_set "$A_PERMMODE_SET" \
      --arg files "$A_FILES" --arg files_set "$A_FILES_SET" \
      --arg cap "$A_CAPACITY" --arg cap_set "$A_CAPACITY_SET" \
      --arg polrev "$POL_REV" \
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
    # THE RE-BRIEF (#699). Registration reprints the wave's policy, so a worker
    # that lost its context to a /clear or a compaction recovers the PROTOCOL by
    # re-registering - not just its address. register.md already called
    # re-registering "the cheap re-brief" for addressing; this is that promise
    # extended to the rules the wave actually runs on, which is the half that
    # never survived.
    if [ "$POL" = "null" ]; then
      echo "flow-wave-registry: wave '$WAVE' has NO declared policy - implementation authority, gate policy, ledger format and merge authority are undeclared." >&2
      echo "  Nothing here says whether this wave writes code or files issues, so a worker cannot infer it from being handed an issue number (#699)." >&2
      echo "  The orchestrator declares it once:  flow-wave-registry.sh policy set --wave '$WAVE' --authority <implement|file-issues-only> ..." >&2
    else
      print_policy_brief "$POL"
    fi
    emit_policy_lines "$POL"
    echo "FLOW_WAVE_BRIEFED_REV=$POL_REV"
    echo "FLOW_WAVE_BRIEF=$(brief_state "$POL_REV" "$POL_REV")"
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
    # Role-level facts (#699). `get` is the scripting contract, so an orchestrator
    # routing work reads permission mode and model from here rather than from
    # message metadata, which is where both were only ever visible before.
    echo "FLOW_WAVE_MODEL=$(printf '%s' "$CUR" | jq -r '.model // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_PERMISSION_MODE=$(printf '%s' "$CUR" | jq -r '.permission_mode // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_FILES=$(printf '%s' "$CUR" | jq -r '.files // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_CAPACITY=$(printf '%s' "$CUR" | jq -r '.capacity // "-" | if . == "" then "-" else . end')"
    GET_POL="$(policy_json "$WAVE")"
    GET_POL_REV="$(policy_rev_of "$GET_POL")"
    GET_BRIEFED="$(printf '%s' "$CUR" | jq -r '.policy_rev // 0')"
    emit_policy_lines "$GET_POL"
    echo "FLOW_WAVE_BRIEFED_REV=$GET_BRIEFED"
    echo "FLOW_WAVE_BRIEF=$(brief_state "$GET_BRIEFED" "$GET_POL_REV")"
    if [ "$(brief_state "$GET_BRIEFED" "$GET_POL_REV")" = "stale" ]; then
      echo "flow-wave-registry: role '$ROLE' was briefed on policy rev $GET_BRIEFED but the wave is at rev $GET_POL_REV - it is running on superseded rules." >&2
      echo "  Re-registering takes the re-brief; nothing about the address changes." >&2
    fi
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
    POL="$(policy_json "$WAVE")"
    POL_REV="$(policy_rev_of "$POL")"
    # One call to the sibling mailbox, cached for every render below (#778).
    # Fails open: on any problem MAILBOX_JSON stays empty and every watch
    # question answers `unknown`, which renders and warns nothing.
    load_mailbox
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
    # Deafness, computed once for every render path below (#778). Scoped to LIVE
    # roles, and gated on the mailbox lane being IN USE in this wave: in a wave
    # that never used it, every role would read ABSENT, and a flag that fires on
    # 100% of the fleet carries zero signal and buries the one case worth acting
    # on - the #674 rule, which this repo has already paid for once.
    WATCH_UNARMED=0
    WATCH_DEAF=""
    NEVER_READ=""
    UNREAD_TOTAL=0
    if [ "$MAILBOX_IN_USE" -eq 1 ]; then
      for r in $ROLES; do
        e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
        [ "$(liveness_of "$e")" = "live" ] || continue
        ws="$(mailbox_watch_state "$r")"
        if [ "$ws" = "absent" ] || [ "$ws" = "stale" ]; then
          WATCH_UNARMED=$((WATCH_UNARMED + 1))
          if [ "$ws" = "absent" ]; then
            WATCH_DEAF="$WATCH_DEAF $r(never armed)"
          else
            WATCH_DEAF="$WATCH_DEAF $r(stale $(human_age "$(mailbox_watch_age "$r")"))"
          fi
        fi
        mailbox_never_read "$r" && NEVER_READ="$NEVER_READ $r"
        u="$(mailbox_box_field "$r" unread)"
        [ "$u" != "-" ] && UNREAD_TOTAL=$((UNREAD_TOTAL + u)) 2>/dev/null
      done
    fi
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
        # `watch` and `mailbox` are computed keys like `liveness`, and appear
        # ONLY when this wave actually uses the mailbox lane (#778) - so a wave
        # that never touched it emits byte-identical JSON to pre-#778, the same
        # promise #687's `unregistered_claims` and #699's `wave_policy` made.
        [ "$MAILBOX_IN_USE" -eq 1 ] || continue
        w_state="$(mailbox_watch_state "$r")"; w_age="$(mailbox_watch_age "$r")"
        m_rev="$(mailbox_box_field "$r" rev)"; m_cur="$(mailbox_box_field "$r" cursor)"
        m_unr="$(mailbox_box_field "$r" unread)"; m_mt="$(mailbox_box_field "$r" mtime)"
        nr=false; mailbox_never_read "$r" && nr=true
        OUT="$(printf '%s' "$OUT" | jq -c \
          --arg r "$r" --arg ws "$w_state" --arg wa "$w_age" \
          --arg rev "$m_rev" --arg cur "$m_cur" --arg unr "$m_unr" --arg mt "$m_mt" \
          --argjson nr "$nr" '
            def num($v): if $v == "-" then null else ($v | tonumber? // null) end;
            .[$r] += {
              watch: {state: $ws, age_secs: num($wa)},
              mailbox: {rev: num($rev), cursor: num($cur), unread: num($unr),
                        last_delivery: (if $mt == "-" then null else $mt end),
                        never_read: $nr}
            }')"
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
      # The wave policy is a sibling key too (#699), for the same reason and
      # with the same caveat the #687 precedent accepted: roles are top-level, so
      # a role literally named `wave_policy` would collide. Named `wave_policy`
      # rather than `policy` to keep that collision as improbable as the shape
      # allows, and the key appears only when a policy is declared - so a wave
      # without one emits byte-identical JSON to pre-#699.
      if [ "$POL" != "null" ]; then
        OUT="$(printf '%s' "$OUT" | jq -c --argjson p "$POL" '. + {wave_policy: $p}')"
      fi
      printf '%s\n' "$OUT" | jq .
      # Keep --json stdout parseable: cross-wave notes go to stderr (#671).
      cross_wave_notes >&2
      emit_policy_lines "$POL"
      echo "FLOW_WAVE_WATCH_UNARMED=$WATCH_UNARMED"
      echo "FLOW_WAVE_UNREAD=$UNREAD_TOTAL"
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
      emit_policy_lines "$POL"
      echo "FLOW_WAVE_WATCH_UNARMED=$WATCH_UNARMED"
      echo "FLOW_WAVE_UNREAD=$UNREAD_TOTAL"
      echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
      echo "FLOW_WAVE: listed"
      exit 0
    fi
    echo "Wave '$WAVE' roster ($REG_FILE):"
    # The policy header (#699). Printed above the roles because it is what the
    # whole roster is operating under - and because a wave with no declared
    # policy should be obvious at a glance rather than discoverable by noticing
    # an absence.
    if [ "$POL" = "null" ]; then
      echo "  -- wave policy: NONE DECLARED (implementation authority, gate policy, ledger and merge authority are undeclared - #699) --"
    else
      print_policy_brief "$POL"
    fi
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
      # Role-level facts are rendered only when declared, so a roster from a wave
      # that never used them reads exactly as it did before (#699).
      extra=""
      fl="$(printf '%s' "$e" | jq -r '.files // ""')"
      [ -n "$fl" ] && extra="$extra files=$fl"
      md="$(printf '%s' "$e" | jq -r '.model // ""')"
      [ -n "$md" ] && extra="$extra model=$md"
      pm="$(printf '%s' "$e" | jq -r '.permission_mode // ""')"
      [ -n "$pm" ] && extra="$extra perm=$pm"
      cp="$(printf '%s' "$e" | jq -r '.capacity // ""')"
      [ -n "$cp" ] && extra="$extra capacity=$cp"
      # Brief staleness is shown for LIVE roles only: a stale or released entry
      # is not running on anything, so calling its brief superseded would be
      # noise on a row nobody is going to re-brief.
      if [ "$lv" = "live" ] && [ "$POL" != "null" ]; then
        bs="$(brief_state "$(printf '%s' "$e" | jq -r '.policy_rev // 0')" "$POL_REV")"
        [ "$bs" = "stale" ] && extra="$extra brief=STALE"
      fi
      # The watch column (#778), LIVE roles only - a dead role's watch is moot,
      # and saying ABSENT of a stale entry is noise on a row nobody will re-arm.
      if [ "$lv" = "live" ] && [ "$MAILBOX_IN_USE" -eq 1 ]; then
        ws="$(mailbox_watch_state "$r")"
        case "$ws" in
          armed)  extra="$extra watch=armed" ;;
          stale)  extra="$extra watch=stale($(human_age "$(mailbox_watch_age "$r")"))" ;;
          absent) extra="$extra watch=ABSENT" ;;
        esac
        unr="$(mailbox_box_field "$r" unread)"
        if [ "$unr" != "-" ] && [ "$unr" -gt 0 ] 2>/dev/null; then
          extra="$extra unread=$unr"
          mt="$(mailbox_box_field "$r" mtime)"
          [ "$mt" != "-" ] && extra="$extra since=$mt"
        fi
        mailbox_never_read "$r" && extra="$extra ** NEVER READ **"
      fi
      echo "  $r -> $sock [$lv, $ver] issue=$iss$extra"
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
      r_files="$(printf '%s' "$e" | jq -r '.files // ""')"
      if [ "$r" = "orchestrator" ]; then
        EXEMPT_ROLES="$EXEMPT_ROLES $r"
        continue
      fi
      # A declared FILE LANE is a lane (#699), on exactly the reasoning #683 gave
      # for a declared branch: the exemption is for roles that declared NOTHING to
      # collide over, and a role holding a granted file lane has declared the most
      # collision-prone thing in the reference wave. Without this clause a worker
      # that registered its lane before entering a worktree - the #670 normal
      # order - would be exempted precisely when its lane is the only fact it has.
      if [ -z "$r_iss" ] && [ -z "$r_br" ] && [ -z "$r_files" ] && cwd_is_shared_parent "$r_cwd" "$r_repo"; then
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
        fa="$(printf '%s' "$ea" | jq -r '.files // ""')"; fb="$(printf '%s' "$eb" | jq -r '.files // ""')"
        report_overlap "$a" "$ia" "$ba" "$ca" "$ra" "$b" "$ib" "$bb" "$cb" "$rb" "$fa" "$fb"
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
      echo "  info: overlap checks skipped for lane-less live role(s):${EXEMPT_ROLES} (orchestrator never holds a lane; others declared no issue, no branch, no file lane, and a shared-parent cwd). Applies until they declare one."
    fi
    [ "$WARNED" -eq 1 ] && echo "flow-wave-registry: lane overlap detected - do not co-schedule the flagged pairs." >&2
    # Stale briefs, counted (#699). A policy that was amended after workers
    # registered is the drift a declared-but-unread field would hide, so the
    # roster names it rather than leaving the orchestrator to compare revs.
    if [ "$POL" != "null" ]; then
      STALE_BRIEFS=""
      for r in $ROLES; do
        e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
        [ "$(liveness_of "$e")" = "live" ] || continue
        [ "$(brief_state "$(printf '%s' "$e" | jq -r '.policy_rev // 0')" "$POL_REV")" = "stale" ] &&
          STALE_BRIEFS="$STALE_BRIEFS $r"
      done
      if [ -n "$STALE_BRIEFS" ]; then
        echo "  BRIEF: live role(s) on a superseded policy rev (wave is at rev $POL_REV):${STALE_BRIEFS}"
        echo "  They are running on older rules until each re-registers - re-registering IS the re-brief and changes nothing about the address."
      fi
    fi
    if [ "$UNADDRESSED" -gt 0 ]; then
      echo "  BOOTSTRAP: $UNADDRESSED LIVE role(s) have no address - they cannot be messaged, and no from= can be observed for them."
      echo "  Verification cannot fire for those roles on its own; it is blocked, not pending."
      bootstrap_escapes
    fi
    # Deafness, counted and named (#778). The per-row `watch=` column answers it
    # for a reader going line by line; this answers it for one who is not, which
    # is the sweep that missed it on 2026-09-05.
    if [ -n "$WATCH_DEAF" ]; then
      echo "  WATCH: live role(s) with no armed watch:${WATCH_DEAF}"
      echo "  They are registered and addressable, and nothing sent to them will WAKE them - an idle session polls nothing."
      echo "  Each arms it as a BACKGROUND call (step 4 of /flow:register):  flow-wave-mailbox.sh watch --role <role> --wave $WAVE"
    fi
    if [ -n "$NEVER_READ" ]; then
      echo "  UNREAD: role(s) that have consumed NOTHING from their box:${NEVER_READ}"
      echo "  A cursor at 0 against a delivered message is not a worker holding - it is a worker that has never looked."
    fi
    cross_wave_notes
    emit_policy_lines "$POL"
    echo "FLOW_WAVE_WATCH_UNARMED=$WATCH_UNARMED"
    echo "FLOW_WAVE_UNREAD=$UNREAD_TOTAL"
    echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
    echo "FLOW_WAVE: listed"
    exit 0
    ;;
esac
