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
#                         [--capacity C] [--driver D]
#   flow-wave-registry.sh policy set  [--wave W] [--driver D] [--authority A]
#                         [--authority-model M] [--gate G] [--ledger L]
#                         [--merge-authority M] [--merge-strict yes|no|unknown]
#                         [--deploy-policy D] [--repo P]
#   flow-wave-registry.sh policy show [--wave W] [--json]
#   flow-wave-registry.sh list    [--wave W] [--json]
#   flow-wave-registry.sh list    --wave W --any-live   (#1095: cheap poll-loop
#                         check - prints `FLOW_WAVE_ANY_LIVE=yes|no-roles-ended|
#                         no-roles-registered|undeterminable` and exits 0/1/1/2
#                         respectively; skips the mailbox join and claim scan
#                         `list` otherwise does)
#   flow-wave-registry.sh get     <role> [--wave W]
#   flow-wave-registry.sh lane-check <role> [--wave W] [--base REF]
#                         [--granted A,B]   (#1026: compare the recorded lane
#                         against the GRANT that authorised it, not only against
#                         other lanes and the diff)
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
#             --driver (#783) is the third of that kind, and the sharpest: it
#             names the LIFECYCLE COMMAND this session runs (`flow:auto`,
#             `codex:auto`, `qwen:auto`, `gemma:auto`), and the roster annotates
#             it with the capability fence read from flow-driver-capability.sh.
#             The other two facts change how WELL work goes; this one changes
#             whether the work is POSSIBLE - the three delegated drivers are
#             implementation-only and web-denied, so a research ticket routed to
#             one can only come back wrong. Free text and fail-open: an
#             undeclared driver simply carries no annotation. The same flag
#             declares the wave-level default under `policy set`; on `register`
#             it records what THIS session is actually running, which is the one
#             that matters when a wave runs mixed drivers.
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
#             A lane that could not be CHECKED is reported as UNKNOWN, never as
#             clean (#800). The same-issue and FILE-LANE arms are scoped to
#             same-repo pairs, so a live role holding a declared lane with an
#             EMPTY repo matches nothing and falls out of the report in silence -
#             a re-register that omits --repo CLEARS it while --files is
#             preserved, so extending a lane was the act that stopped it being
#             checked. Such roles are NAMED, counted in
#             FLOW_WAVE_OVERLAP_UNSCOPED, and said aloud on stderr; `register`
#             and `get` answer the same question per role as
#             FLOW_WAVE_LANE_SCOPED=yes|no|-. NOT fixed by preserving `repo`
#             across a re-register: `repo` is a LANE fact and lane facts go
#             stale (the #683 trap), so preserving it would make a worker that
#             moved repos cry wolf, and would still leave a never-declared repo
#             silent. Fail loud, so an unscoped role is visible rather than
#             invisible.
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
#             ONE EXCEPTION (#985): a declared DIRECTORY contains the paths under
#             it. That is not a guess about intent, it is what declaring a
#             directory means, and without it a role claiming a whole mirror tree
#             collides with nobody. Reversal trigger recorded at the predicate.
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
#             `watch=stale(42m)`, `watch=DEAD(0 watchers)`, `watch=ABSENT` or
#             `watch=UNKNOWN`, plus `unread=N since <ts>` and a loud
#             `** NEVER READ **` when the mailbox's ACKED count is 0 against a
#             non-zero rev (issue #815 - was the read cursor before the
#             mailbox retired it in favor of explicit acknowledgement) - the
#             unambiguous "has never confirmed receipt of anything" case,
#             which a count alone does not say.
#             `DEAD` and `UNKNOWN` arrived with #801, and the reason is that
#             #778's own instrument had this same disease. The state it rendered
#             was derived from the heartbeat STAMP alone, and a stamp is only as
#             fresh as the last WAKE - while the watch is ONE-SHOT, so it exits
#             the moment it delivers. For the whole stale window after that, the
#             roster rendered `watch=armed` about a role that was deaf. On the
#             `docker-list` wave (2026-09-07) an orchestrator read that word and
#             told three workers they were fine; all three were deaf, one for
#             ~50 minutes. The mailbox now FUSES the live watcher count into the
#             state and this renders the fused verdict, with the count beside it
#             so the row states the evidence rather than only the conclusion.
#             `dead` and `unknown` also count into `FLOW_WAVE_WATCH_UNARMED` and
#             the `WATCH:` summary - a watch that cannot be assessed is not an
#             armed one (the #800 convention).
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
#   FLOW_WAVE_POLICY_AUTHORITY_MODEL  orchestrator-only | user-and-orchestrator |
#                                     user-only (the most restrictive, #1026)
#   FLOW_WAVE_POLICY_GATE / _LEDGER / _MERGE_AUTHORITY / _DEPLOY / _REPO / _TS
#   FLOW_WAVE_BRIEFED_REV    the policy rev THIS role was briefed on (register/get)
#
# Driver capability detail lines (#783), derived from flow-driver-capability.sh
# and never restated here. Emitted as '-' whenever the driver is undeclared,
# unknown, or the helper is absent - a missing fence is never a claim of one:
#   FLOW_WAVE_DRIVER         the lifecycle command THIS role runs (register/get -
#                            register too since #1026: it stored --driver and
#                            emitted nothing, so a silently-accepted flag and a
#                            silently-IGNORED one were byte-identical)
#   FLOW_WAVE_DRIVER_SCOPE   general | implementation-only
#   FLOW_WAVE_DRIVER_WEB     yes | no  (can it consult a live source?)
#   FLOW_WAVE_DRIVER_CONTAINER  yes | no (can its shell reach docker/kubectl/
#                            terraform directly? issue #835 - does NOT track
#                            scope/web; qwen:auto is implementation-only and
#                            web=no yet container=yes)
#   FLOW_WAVE_DRIVER_META    yes | no (may it read/edit this repo's own
#                            .claude/commands/** and .claude/skills/**? issue
#                            #877 - `no` for all three delegated drivers, whose
#                            #735 fence forbids reading them, and the reason a
#                            CPP-meta issue must not be routed to one)
#   FLOW_WAVE_DRIVER_CANNOT  the needs it structurally cannot meet, e.g.
#                            `research web`. THE routing line: an issue whose
#                            deliverable is a finding rather than a diff, handed
#                            to a role naming `research` here, is the mis-route
#                            #783 was filed about - now visible at assignment.
#   FLOW_WAVE_POLICY_DRIVER_SCOPE / _WEB / _CONTAINER / _META / _CANNOT  the same, for
#                            the wave-level default driver (register/get/list/
#                            policy)
#
# Vantage detail lines (#959), derived from the sibling flow-vantage.sh at
# REGISTER time and stored on the role, because the orchestrator reading them
# runs on a different machine and cannot re-derive a fact about this process.
# NOTE the name: `FLOW_WAVE_DRIVER_CONTAINER` above answers something else
# entirely - can this DRIVER's shell reach docker/kubectl/terraform - so vantage
# is spelled VANTAGE everywhere to keep the two apart on sight (#959):
#   FLOW_WAVE_VANTAGE        host | container | unknown | unavailable (register,
#                            get). `unavailable` = no helper installed; `get`
#                            reports `unrecorded` for an entry registered before
#                            #959. FOUR WORDS, NOT TWO: "nobody measured", "the
#                            helper is absent" and "the signals disagreed" send a
#                            reader to three different places, and none of them
#                            is `host`
#   FLOW_WAVE_VANTAGE_SOURCE measured | declared - a declared override is NEVER
#                            merged into a measured basis, and the roster keeps
#                            them apart the way the helper does
#   FLOW_WAVE_VANTAGE_BASIS  which signals had an opinion, named individually -
#                            never a count. "2 signals agreed" cannot be checked
#                            by the reader; `ns-pid(pid:[...]: host) +
#                            machine-id(present: ...)` can be
#
# `list` renders it on the role row as `vantage=container[lane1-empty]` /
# `vantage=unknown[route-mailbox]` / `vantage=host`, beside `driver=`: the
# routing consequence travels with the fact, because the consequence is the half
# that decides anything. ROUTE `unknown` TO THE MAILBOX and leave it visible -
# a host session on the mailbox loses a little speed, a containerised session on
# lane 1 loses the message while being told it succeeded.
#
# The #1026 read-back lines - each one a declaration that was stored and never
# reported, so a broken declaration and a working one printed identically:
#   FLOW_WAVE_FILES          the role's file lane as now recorded (register)
#   FLOW_WAVE_FILES_DROPPED  paths this registration REMOVED from that lane, or
#                            '-'. `--files` REPLACES, so the routine re-brief
#                            silently un-claimed whatever the new list omitted
#   FLOW_WAVE_FILES_ADDED    paths this registration added, or '-'
#   FLOW_WAVE_DRIVER_UNDECLARED  (list) count of LIVE non-orchestrator roles with
#                            no driver, under a wave whose POLICY declares one.
#                            '-' when the wave declares none: a `0` would claim a
#                            measurement that was never taken
#   FLOW_WAVE_POLICY_MERGE_STRICT / _TS / _AGE / _STALE  the branch-protection
#                            reading, when it was taken, and whether it still
#                            counts. `_STALE=unknown` means declared but
#                            UNSTAMPED - undatable is not recent
#   FLOW_WAVE_MERGE_STRICT_SUPPRESSING  (list) yes|no - whether that reading
#                            actually switched starvation detection off. Differs
#                            from FLOW_WAVE_MERGE_STRICT exactly when a `no` has
#                            expired, which is the case worth seeing
#   FLOW_WAVE_LANE_UNGRANTED / _UNCLAIMED  (lane-check --granted) the declared
#                            lane versus the GRANT that authorised it - the one
#                            comparison nothing made. '-' when no grant was
#                            supplied. UNGRANTED refuses; UNCLAIMED is loud data
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
#   FLOW_WAVE_LIVE_PIDS     ':'-separated pids treated as alive; when set the
#                           list is AUTHORITATIVE, so a pid absent from it reads
#                           gone (bypasses the /proc + errno probe entirely)
#   FLOW_WAVE_UNKNOWN_PIDS  ':'-separated pids whose liveness is undeterminable.
#                           The only way to exercise that branch on a /proc host,
#                           where the real probe can always decide (#869)
#   FLOW_WAVE_MAILBOX_DIR   mailbox wave-root override, passed through to the
#                           sibling helper so the two always co-locate (#778)
#   FLOW_WAVE_SELF_PID      starting pid for the self-address ancestor walk
#   FLOW_WAVE_PID_STARTTIMES  'pid=starttime:pid=starttime' pairs (issue #1094)
#                           - when a pid appears, its recorded/looked-up start
#                           time is this value rather than /proc's; the only
#                           way to construct a chosen pid+starttime pairing for
#                           a test without depending on real kernel pid reuse,
#                           which cannot be forced on demand
#   FLOW_WAVE_PROC_ROOT     '/proc' root override (issue #1094) - lets a test
#                           feed pid_started_of() a CRAFTED stat line (a comm
#                           containing a space or a parenthesis) through the
#                           real parser, rather than asserting the parser is
#                           correct without ever exercising it

set -uo pipefail

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "FLOW_WAVE_EXIT=%d\n" "$?" >&2' EXIT

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

# Driver capability (#783). The roster's job here is to SURFACE the fence at
# assignment time; the fence itself is declared once in the sibling helper and
# read back from it. Deriving rather than restating is the whole point - a
# second copy of "codex:auto cannot do research" living in this file would drift
# from the first, and both would still read like documentation.
#
# Fail-open in every direction: no helper, an unknown driver, or a driver nobody
# declared all yield an empty annotation, and the roster renders exactly as it
# did before #783. A missing capability line must never be mistaken for a
# capability claim.
SELF_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
CAP_HELPER="$SELF_DIR/flow-driver-capability.sh"

# driver_cap DRIVER FIELD -> the FLOW_DRIVER_<FIELD> value, or '' when unknown.
driver_cap() {
  local d="$1" field="$2" out
  [ -n "$d" ] || return 0
  [ -x "$CAP_HELPER" ] || return 0
  out="$("$CAP_HELPER" show "$d" 2>/dev/null | sed -n "s/^FLOW_DRIVER_${field}=//p")"
  [ "$out" = "-" ] && out=""
  printf '%s' "$out"
}

# driver_cap_dash DRIVER FIELD -> the value, or '-' when there is none.
#
# The detail lines use '-' for not-applicable throughout (#674: a consumer must
# be able to tell "no fence declared" from "this call does not report one", and
# an EMPTY value answers neither). Piping through `sed 's/^$/-/'` does not do
# this - driver_cap prints no trailing newline, so an empty result is zero LINES
# and sed has nothing to substitute.
driver_cap_dash() {
  local out; out="$(driver_cap "$1" "$2")"
  printf '%s' "${out:--}"
}

# Vantage (#959) - which side of the container boundary the REGISTERING session
# is on, derived from the sibling `flow-vantage.sh` and never restated here, for
# the same reason the driver fence above is derived.
#
# WHY IT IS STORED RATHER THAN RE-DERIVED AT READ TIME. The orchestrator runs
# `get` and `list` on ITS machine. Vantage is a fact about the WORKER's process,
# and no amount of care re-derives it from somewhere else - a `get` that measured
# locally would confidently report the orchestrator's own vantage under the
# worker's role name. So `register` measures once, in the only place the answer
# exists, and the roster serves what was measured. Same shape as #1029's
# toolchain provenance, relayed at registration for the same reason.
#
# WHY IT MATTERS AT ALL: the delivery lane INVERTS across that boundary
# (register.md, #947/#958). Past it the mailbox is lane 1 and `SendMessage`
# addresses a population holding no fleet peer - not empty, populated with the
# wrong sessions, which returns success and delivers nothing. An orchestrator
# that can see `vantage=container` BEFORE assigning does not have to discover it
# from the silence afterwards.
#
# Fail-open, and the failure word is its own: no helper means `unavailable`,
# which is neither `unknown` (the helper ran and could not decide) nor `host`
# (a measurement). Three states that must never collapse into two.
VANTAGE_HELPER=""
for _vh in "$SELF_DIR/flow-vantage.sh" "$HOME/.claude/scripts/flow-vantage.sh"; do
  [ -x "$_vh" ] && { VANTAGE_HELPER="$_vh"; break; }
done
unset _vh

#: Sets V_VANTAGE / V_SOURCE / V_BASIS from one run of the helper. Never reads
#: the exit code as the verdict: the contract LINE is the verdict, and a helper
#: killed before it printed anything must read `unavailable` rather than
#: inheriting whatever `$?` happens to be.
vantage_derive() {
  V_VANTAGE=unavailable
  V_SOURCE="-"
  V_BASIS="-"
  [ -n "$VANTAGE_HELPER" ] || return 0
  local out
  out="$("$VANTAGE_HELPER" --quiet 2>/dev/null)" || true
  # EXACTLY ONE VERDICT LINE, AND IT MUST BE A WORD THIS CONTRACT DEFINES
  # (counter-model review, codex/gpt-6-astra, 2026-09-20). The first cut took
  # `head -1` of every matching line, so anything that put a second
  # `FLOW_VANTAGE:` line into the helper's stdout decided this value - measured
  # with `FLOW_VANTAGE_DECLARE=$'x\nFLOW_VANTAGE: host'`, which made a REFUSED
  # declaration arrive here as a verdict. The helper now sanitises its own
  # echo, and this is the second half of the same fix: a relay that validates
  # only at the source trusts every future source. `unparseable` is its own
  # word for the same reason `unavailable` is not `unknown` - "the helper said
  # something I cannot read" and "the helper could not decide" send a reader to
  # different places, and neither of them is `host`.
  local n
  n="$(printf '%s\n' "$out" | grep -c '^FLOW_VANTAGE: ' || true)"
  if [ "$n" != "1" ]; then
    [ "$n" = "0" ] && return 0      # nothing usable at all: stays `unavailable`
    V_VANTAGE=unparseable
    V_BASIS="helper emitted $n FLOW_VANTAGE lines"
    return 0
  fi
  # THE SAME RULE FOR THE SOURCE LINE (counter-model review, codex/gpt-6-astra,
  # pass 2). The multiplicity check above covered the VERDICT only, so
  # `measured` followed by `declared` was accepted as measured and the roster
  # dropped the `[declared]` annotation - the injection closed on one line and
  # left open on the line that says how much to trust it. Both fields decide
  # something, so both are checked; the BASIS line is deliberately not, being
  # descriptive text that changes no routing decision.
  local m
  m="$(printf '%s\n' "$out" | grep -c '^FLOW_VANTAGE_SOURCE: ' || true)"
  if [ "$m" != "1" ]; then
    V_VANTAGE=unparseable
    V_BASIS="helper emitted $m FLOW_VANTAGE_SOURCE lines"
    return 0
  fi
  local v s b
  v="$(printf '%s\n' "$out" | sed -n 's/^FLOW_VANTAGE: //p' | head -1)"
  s="$(printf '%s\n' "$out" | sed -n 's/^FLOW_VANTAGE_SOURCE: //p' | head -1)"
  b="$(printf '%s\n' "$out" | sed -n 's/^FLOW_VANTAGE_BASIS: //p' | head -1)"
  case "$v" in
    host|container|unknown) ;;
    *)
      V_VANTAGE=unparseable
      V_BASIS="helper reported a verdict this contract does not define"
      return 0
      ;;
  esac
  case "$s" in
    measured|declared) ;;
    *)
      # A verdict whose PROVENANCE is unreadable cannot be rendered honestly -
      # the roster would have to guess between `measured` and `declared`, which
      # is the distinction the field exists to carry.
      V_VANTAGE=unparseable
      V_BASIS="helper reported a source this contract does not define"
      return 0
      ;;
  esac
  V_VANTAGE="$v"
  V_SOURCE="$s"
  V_BASIS="${b:--}"
}

#: The roster annotation for a stored vantage, rendered like the driver fence:
#: the fact and its routing consequence as ONE token, because the consequence is
#: the half that decides anything. `unknown` carries one too - it is the state a
#: safe default would otherwise absorb silently, and a default nobody notices
#: firing is how the third state dies.
vantage_annotation() {
  local v="$1" src="${2:-}" note=""
  case "$v" in
    container) note="lane1-empty" ;;
    unknown)   note="route-mailbox" ;;
  esac
  # PROVENANCE TRAVELS WITH THE VALUE (counter-model review, codex/gpt-6-astra,
  # 2026-09-20). The roster rendered `.vantage` alone, so a container
  # registered with `FLOW_VANTAGE_DECLARE=host` printed the identical
  # `vantage=host` token as a measured host - and the roster is the surface an
  # orchestrator actually reads at assignment time. Keeping `measured` and
  # `declared` apart everywhere EXCEPT there would have hidden precisely the
  # stale-declaration risk that is the argument for deriving in the first
  # place. Measured stays unannotated: it is the ordinary case, and a tag on
  # every row is a tag nobody reads.
  [ "$src" = "declared" ] && note="${note:+$note,}declared"
  printf '%s%s' "$v" "${note:+[$note]}"
}

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
  echo "FLOW_WAVE_LIVENESS_BASIS=${E_BASIS:--}"
  echo "FLOW_WAVE_VERIFIED=${E_VERIFIED:--}"
  echo "FLOW_WAVE_MISMATCH=${E_MISMATCH:--}"
  echo "FLOW_WAVE_BOOTSTRAP=${E_BOOTSTRAP:--}"
  echo "FLOW_WAVE: $1"
}

# pid_state PID -> alive | gone | unknown, for a pid on THIS host.
#
# `kill -0` has TWO failure modes behind ONE return code, and collapsing them is
# what #869 fixes. They are not degrees of the same answer; they are opposite
# answers:
#   ESRCH  no such process   - the process is GONE. Definite.
#   EPERM  not permitted     - the process EXISTS, we merely may not signal it.
#                              This is POSITIVE evidence of life.
# EPERM is precisely the case #675 introduced the socket-file fallback to rescue
# ("covering a pid the helper cannot signal"). Reading the errno serves that
# stated purpose with a correct instrument, so the fallback no longer has to
# stand in for evidence that was available all along - and, unlike stat-ing a
# socket path, it works on EVERY transport rather than only `uds:`.
#
# `/proc/<pid>` is consulted first where it exists because it answers directly
# and without ambiguity: the kernel keeps an entry for every live process on the
# host regardless of who owns it, so presence is existence and absence is death.
#
# `unknown` is a real third answer, not a polite `gone`: a host with no /proc
# whose `kill` reports something we do not recognise has an UNENUMERABLE process
# table, and rounding that down to "dead" is the mistake the sibling mailbox
# refused when it moved off pid liveness (#814). Never checked and
# checked-but-undecidable are different facts.
pid_state() {
  local pid="$1" err
  [ -n "$pid" ] && [ "$pid" != "-" ] && [ "$pid" != "null" ] || { echo gone; return; }
  case "$pid" in ''|*[!0-9]*) echo gone; return ;; esac

  # Test hooks pin the process table so no test depends on a pid that happens
  # to exist. FLOW_WAVE_UNKNOWN_PIDS is checked first: it is the narrower
  # statement, and it is the only way to reach the undeterminable branch on a
  # /proc host, where the real prober can never return `unknown`.
  if [ -n "${FLOW_WAVE_UNKNOWN_PIDS:-}" ]; then
    case ":$FLOW_WAVE_UNKNOWN_PIDS:" in *":$pid:"*) echo unknown; return ;; esac
  fi
  if [ -n "${FLOW_WAVE_LIVE_PIDS:-}" ]; then
    case ":$FLOW_WAVE_LIVE_PIDS:" in
      *":$pid:"*) echo alive ;;
      # The pinned list is AUTHORITATIVE when set, so absence from it is death,
      # not undeterminability - otherwise every test would read `unknown`.
      *) echo gone ;;
    esac
    return
  fi

  if [ -d /proc/self ]; then
    if [ -d "/proc/$pid" ]; then echo alive; else echo gone; fi
    return
  fi

  if kill -0 "$pid" 2>/dev/null; then echo alive; return; fi
  # LAST RESORT, and the only branch in this function that reads PROSE rather
  # than a fact. There is no portable way to get an errno out of the `kill`
  # builtin except its message, and that message is `strerror()`, which glibc
  # TRANSLATES. `LC_ALL=C` pins it - a temporary assignment on a builtin does
  # reach bash's own setlocale - but it cannot help if the message shape itself
  # differs, so an unrecognised message falls to `unknown` rather than guessing.
  # That is the safe direction: `unknown` refuses a takeover, it never invents
  # life. Reachable only on a host with no /proc, since /proc is consulted
  # first, and never in the tests, which pin the table.
  err="$(LC_ALL=C kill -0 "$pid" 2>&1 >/dev/null)"
  case "$err" in
    *"o such process"*)                     echo gone ;;
    *"ot permitted"*|*"ermission denied"*)  echo alive ;;
    *)                                      echo unknown ;;
  esac
}

# pid_started_of PID -> that process's start time (field 22 of
# /proc/<pid>/stat, clock ticks since boot), or "-" if it cannot be
# determined (issue #1094).
#
# `pid_state` alone answers "does a process with this number exist", never
# "is it the SAME process a registry entry recorded" - a registered pid that
# exits and is later reused by the kernel for an unrelated process reads
# `alive` either way. A process's start time is a second, independent fact
# about THAT SPECIFIC instance: a pid recycled to an unrelated process will
# have a start time from after the original one exited, so comparing the
# CURRENT start time against the one recorded at registration distinguishes
# recycling from genuine survival, without a lifetime flock or a persistent
# process to hold one - `register` is a one-shot invocation with nothing
# that could hold a lock for the life of the session it is recording.
#
# NEVER a positional `awk '{print $22}'` on the raw line. `comm` (field 2) is
# parenthesised and MAY ITSELF CONTAIN SPACES OR PARENTHESES - a process can
# set its own name to anything - so a naive positional split silently shifts
# every field after it. Measured directly: this read a start time from BEFORE
# the process could have existed, for exactly this reason. The kernel's own
# convention (and every tool that gets this right, `ps` included) is to split
# on the LAST `)` in the line - `${stat##*)}` removes the longest matching
# prefix ending in `)`, so any parens embedded in `comm` are consumed as part
# of it - and index the fields AFTER that split, where starttime is the 20th
# (state ppid pgrp session tty_nr tpgid flags minflt cminflt majflt cmajflt
# utime stime cutime cstime priority nice num_threads itrealvalue starttime).
pid_started_of() {
  local pid="$1" entry proc_root stat rest
  [ -n "$pid" ] && [ "$pid" != "-" ] && [ "$pid" != "null" ] || { echo -; return; }
  case "$pid" in ''|*[!0-9]*) echo -; return ;; esac

  if [ -n "${FLOW_WAVE_PID_STARTTIMES:-}" ]; then
    for entry in $(printf '%s' "$FLOW_WAVE_PID_STARTTIMES" | tr ':' ' '); do
      case "$entry" in
        "$pid="*) printf '%s\n' "${entry#*=}"; return ;;
      esac
    done
    echo -
    return
  fi

  proc_root="${FLOW_WAVE_PROC_ROOT:-/proc}"
  stat="$(cat "$proc_root/$pid/stat" 2>/dev/null)" || { echo -; return; }
  rest="${stat##*\)}"
  # Deliberate word-splitting to index fields positionally.
  # shellcheck disable=SC2086
  set -- $rest
  if [ "$#" -ge 20 ]; then
    printf '%s\n' "${20}"
  else
    echo -
  fi
}

# is_alive PID HOST -> 0 when the owning session still runs on THIS host.
is_alive() {
  local pid="$1" host="$2"
  [ "$host" = "$SELF_HOST" ] || return 1
  [ "$(pid_state "$pid")" = "alive" ]
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

# _liveness_compute ENTRY_JSON -> "STATE BASIS"
#
# STATE is live | stale | unknown | released. BASIS names WHICH RULE decided it,
# so a reader can tell a proven death from an undecidable one without inferring
# it from the state alone (#869 acceptance: the two `kill -0` failure modes are
# distinguishable, and the code says which one it saw).
#
# THE SOCKET FILE IS CORROBORATION, NEVER PROOF (#869). It used to be sufficient
# on its own, and evaluated AFTER the pid had already been reported dead:
#
#     uds:*) [ -S "${sock#uds:}" ] && { echo live; return; } ;;
#
# The kernel does not unlink a unix domain socket when its owner dies, so the
# file outlives the process and the WEAKER evidence overrode the STRONGER one: a
# SIGKILLed session kept reading `live` for as long as its socket sat on disk.
#
# What #675 actually asked for is preserved. Its words are that the socket file
# is "a SECOND, independent proof, covering a pid the helper cannot signal" -
# that is the EPERM case, and `pid_state` now answers it directly and correctly.
# What is removed is only the socket's power to override a DEFINITE ESRCH, which
# #675 never claimed and which was a bug in the mechanism rather than in the
# intent. #689 then made the branch uds-only and recorded that transports
# without sockets get one factor, "a property of the design, not an oversight".
# That asymmetry is now GONE rather than documented: errno needs no socket, so
# every transport gets the same primary evidence. The socket survives only in
# the BASIS, where it corroborates an already-undeterminable pid and changes no
# verdict.
_liveness_compute() {
  local e="$1" pid host sock released st recorded_started current_started
  released="$(printf '%s' "$e" | jq -r '.released // false')"
  [ "$released" = "true" ] && { echo "released released"; return; }
  pid="$(printf '%s' "$e" | jq -r '.pid // "-"')"
  host="$(printf '%s' "$e" | jq -r '.host // "-"')"
  sock="$(printf '%s' "$e" | jq -r '.socket // "unknown"')"

  # Unchanged, and deliberately so: the registry is host-local by construction,
  # so an entry from another host has always read `stale` and every reader is
  # built on that. It is arguably the same shape of defect as the one above - we
  # cannot determine a remote pid's liveness either - but promoting it to
  # `unknown` would change takeover semantics for every cross-host entry, which
  # is a separate decision and out of scope here. The BASIS says which rule
  # fired, so the two never look alike to a reader.
  if [ "$host" != "$SELF_HOST" ]; then echo "stale other-host"; return; fi

  st="$(pid_state "$pid")"
  case "$st" in
    alive)
      # pid EXISTENCE alone is not pid IDENTITY (issue #1094): a recycled pid
      # reads `alive` here just as genuinely as the process that originally
      # registered it. `pid_started` closes that gap - but a BLANK recorded
      # witness must never be read as a MATCH: every entry this repo already
      # holds predates this field, and treating "never recorded" the same as
      # "recorded and equal" would report the strongest basis this instrument
      # can give, for every pre-existing entry, on no evidence at all.
      # Never-recorded, recorded-and-equal, recorded-and-different, and
      # current-unreadable are four different facts and stay four different
      # basis values - see `.claude/commands/flow/register.md` for the table.
      #
      # All four still resolve to only two VERDICTS (orchestrator ruling,
      # #1094): the witness can only ever ADD a positive finding (a proven
      # mismatch, `pid-recycled`), never subtract one. Absence of a witness
      # to compare, or an unreadable current witness, is not evidence of
      # recycling - it is the absence of evidence either way - so both read
      # `live`, exactly as they did before this pid existed. This is also
      # the only choice consistent with every downstream reader: `liveness_of`
      # is consumed as a plain `= "live"` binary at every call site (:808,
      # :1342, :1556, :1806, :1849 via CUR_LIVE), so a THIRD verdict value
      # here would not add a distinction any reader can act on - it would
      # only silently reclassify every entry written before this field
      # existed from live to not-live, fleet-wide, in the name of a fix. A
      # future change that wants that distinction ACTED ON needs its own
      # call-site changes, not just a basis rename here.
      recorded_started="$(printf '%s' "$e" | jq -r '.pid_started // "-"')"
      if [ -z "$recorded_started" ] || [ "$recorded_started" = "-" ]; then
        echo "live pid-present-witness-absent"; return
      fi
      current_started="$(pid_started_of "$pid")"
      if [ -z "$current_started" ] || [ "$current_started" = "-" ]; then
        echo "live pid-present-witness-undeterminable"; return
      fi
      if [ "$recorded_started" = "$current_started" ]; then
        echo "live pid-present"; return
      fi
      echo "stale pid-recycled"; return
      ;;
    # A leftover socket file is NOT evidence against a confirmed death, so it is
    # not consulted on this branch at all.
    gone)  echo "stale pid-gone"; return ;;
  esac

  # pid_state could not decide. Report the socket as corroboration - it raises
  # confidence that something is still there, and it settles nothing.
  case "$sock" in
    unknown) echo "unknown pid-undeterminable-no-address" ;;
    uds:*)
      if [ -S "${sock#uds:}" ]; then
        echo "unknown pid-undeterminable-socket-present"
      else
        echo "unknown pid-undeterminable-socket-absent"
      fi
      ;;
    *) echo "unknown pid-undeterminable-no-socket-proof" ;;
  esac
}

# liveness_of ENTRY_JSON -> live | stale | unknown | released
liveness_of() { local r; r="$(_liveness_compute "$1")"; echo "${r%% *}"; }

# liveness_basis_of ENTRY_JSON -> the rule that decided it
liveness_basis_of() { local r; r="$(_liveness_compute "$1")"; echo "${r#* }"; }

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
      #: EXACT MATCH, PLUS CONTAINMENT FOR A DECLARED DIRECTORY (#985).
      #:
      #: The exact-match rule above it exists to stop prefix-GUESSING inventing
      #: collisions the roles never declared (#683). A declared DIRECTORY is not a
      #: guess: `codex/skills/` contains `codex/skills/flow-repair/reference.md`
      #: by definition, and that is what declaring a directory means. Live case:
      #: a role declared the bare `codex/skills` and thereby claimed three other
      #: roles' mirror trees while this predicate reported no overlap at all.
      #:
      #: The same file already does containment for CWD comparison (`case "$ca/"
      #: in "$cb"/*`) and refused it here, so the codebase had decided both ways
      #: in one file. A rule applied to one half of a comparison and refused for
      #: the other is not a policy, it is an accident.
      #:
      #: TWO-SIDED, so the REVERSAL TRIGGER lives here rather than in a PR nobody
      #: will read: if containment warnings start firing on pairs the roles
      #: consider disjoint, revert to exact-match and record the directory case as
      #: known-unhandled. Everything that is not a declared directory stays exact.
      #: Containment is tested with an EXPLICIT SEPARATOR, and that is what keeps
      #: it from being the prefix-guessing the rule above forbids: `scripts/foo`
      #: does NOT contain `scripts/foobar`, because the test is against
      #: `scripts/foo/`. Only a real path boundary counts. A trailing slash on the
      #: declaration is optional - the live over-claim was a bare `codex/skills`,
      #: and requiring the slash would have missed the case this exists for.
      _ca="${pa%/}"; _cb="${pb%/}"
      if [ "$_ca" = "$_cb" ]; then
        out="$out$_ca "
      elif [ "${_cb#"$_ca"/}" != "$_cb" ]; then
        out="$out$_cb "
      elif [ "${_ca#"$_cb"/}" != "$_ca" ]; then
        out="$out$_ca "
      fi
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

# lane_unscoped REPO FILES ISSUE -> 0 when this role declares a lane fact whose
# overlap arm is SCOPED TO SAME-REPO PAIRS while carrying NO repo (#800).
#
# Two of report_overlap's four arms - same-issue and FILE LANE - test `$ra` =
# `$rb` before they test anything else, because the same relative path (or the
# same issue number) in two different repos is not a collision. An EMPTY repo
# therefore matches NOTHING: the arm cannot fire, the shared-repo `info:` arm
# below it cannot fire either, and the pair drops out of the report entirely.
# Silence there is indistinguishable from "checked, and clean" - which is the
# one reading it must never have.
#
# The branch and same/nested-worktree arms are repo-INDEPENDENT and unaffected.
# This predicate is deliberately about the two that are not.
#
# Found in a live wave: a worker re-registered passing only `--files` to extend
# its lane. `files` is PRESERVED across a re-register that omits it while `repo`
# is REWRITTEN, so the lane survived and its scoping key did not - two workers
# held the same two files for ~40 minutes against a roster that read clean. The
# act of declaring a lane was the act that stopped the lane being checked.
lane_unscoped() {
  local repo="$1" files="$2" issue="$3"
  [ -z "$repo" ] || [ ! -d "$repo" ] || return 1
  [ -n "$files" ] || [ -n "$issue" ]
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
# --merge-strict IS A MEASUREMENT WITH A SHELF LIFE (#1026).
#
# Branch protection is repo state, changeable by anyone with admin - including
# someone outside the wave - while this registry is deliberately OFFLINE (it must
# run in the CI image with no network and no `gh`). So the declaration is a
# reading taken at one moment, and its staleness was previously UNBOUNDED.
#
# The dangerous direction is one-way. `merge_strict=no` SUPPRESSES starvation
# detection outright, so a wave that declared `no` goes silently blind the moment
# protection is TIGHTENED - the exact change that makes starvation possible. The
# reverse (a stale `yes`) only leaves the signal switched on, which costs nothing
# but a warning.
#
# So the observation is stamped, its age is reported, and suppression requires a
# reading that is both STAMPED and FRESH. An unstamped declaration reads
# `unknown`, never fresh: a policy written before this change cannot be dated,
# and an undatable reading is not a recent one.
#
# OSCILLATION CONTROL - the reversal trigger, recorded here rather than in a PR
# nobody re-reads. This is a threshold and thresholds are two-sided. If waves
# start losing legitimate `no` declarations mid-run and re-declaring them purely
# to keep the signal quiet, RAISE FLOW_WAVE_MERGE_STRICT_TTL. Do NOT remove the
# expiry: removing it restores the unbounded staleness this exists to bound, and
# the symptom it would relieve (a re-declaration) is cheap while the failure it
# would restore (a blind wave) is not.
MERGE_STRICT_TTL="${FLOW_WAVE_MERGE_STRICT_TTL:-86400}"
# VALIDATED, because an unvalidated TTL made this guard fail OPEN - the one
# direction it exists to close (counter-model review, #1026). With a non-numeric
# value `[ "$age" -gt "$MERGE_STRICT_TTL" ]` is a bash integer-expression ERROR,
# which returns false, which falls through to "fresh" - so a typo in an
# environment variable would silently restore the unbounded staleness this
# bounds, and nothing would say so. A bad TTL is refused into the default and
# announced; it never becomes a permanent suppression.
case "$MERGE_STRICT_TTL" in
  '' | *[!0-9]*)
    echo "flow-wave-registry: FLOW_WAVE_MERGE_STRICT_TTL='$MERGE_STRICT_TTL' is not a non-negative integer - using 86400." >&2
    echo "  An unusable TTL must not read as 'never expires': that is the failure this shelf life exists to prevent (#1026)." >&2
    MERGE_STRICT_TTL=86400 ;;
esac

# merge_strict_age POLICY_JSON -> seconds since the observation, or '-' when it
# carries no usable stamp.
merge_strict_age() {
  local ts
  ts="$(policy_field "$1" merge_strict_ts)"
  case "$ts" in
    '' | *[!0-9]*) printf '%s' '-'; return 0 ;;
  esac
  printf '%s' "$(( NOW - ts ))"
}

# merge_strict_stale POLICY_JSON -> yes | no | unknown | '-'
#   '-'      nothing was declared, so there is nothing to go stale
#   unknown  declared but UNSTAMPED - it cannot be dated, so it is not fresh
#   yes/no   older / younger than the TTL
merge_strict_stale() {
  local age
  [ -n "$(policy_field "$1" merge_strict)" ] || { printf '%s' '-'; return 0; }
  age="$(merge_strict_age "$1")"
  [ "$age" = "-" ] && { printf '%s' 'unknown'; return 0; }
  # A NEGATIVE age is a stamp from the FUTURE - clock skew, or a registry file
  # written by a host whose clock disagrees. It is a broken observation, not a
  # very fresh one, and rounding it down to "fresh" would suppress on the
  # strength of a reading we have positive evidence against.
  [ "$age" -lt 0 ] && { printf '%s' 'unknown'; return 0; }
  [ "$age" -gt "$MERGE_STRICT_TTL" ] && { printf '%s' 'yes'; return 0; }
  printf '%s' 'no'
}

# merge_strict_suppressing POLICY_JSON -> yes | no
# The ONE predicate that decides whether starvation detection is switched off,
# so the roster and the JSON can never disagree about why it was.
merge_strict_suppressing() {
  [ "$(policy_field "$1" merge_strict)" = "no" ] || { printf '%s' 'no'; return 0; }
  [ "$(merge_strict_stale "$1")" = "no" ] || { printf '%s' 'no'; return 0; }
  printf '%s' 'yes'
}

emit_policy_lines() {
  local p="$1"
  if [ "$p" = "null" ]; then
    echo "FLOW_WAVE_POLICY=absent"
    echo "FLOW_WAVE_POLICY_REV=0"
    echo "FLOW_WAVE_POLICY_DRIVER=-"
    echo "FLOW_WAVE_POLICY_DRIVER_SCOPE=-"
    echo "FLOW_WAVE_POLICY_DRIVER_WEB=-"
    echo "FLOW_WAVE_POLICY_DRIVER_CONTAINER=-"
    echo "FLOW_WAVE_POLICY_DRIVER_META=-"
    echo "FLOW_WAVE_POLICY_DRIVER_CANNOT=-"
    echo "FLOW_WAVE_POLICY_AUTHORITY=-"
    echo "FLOW_WAVE_POLICY_AUTHORITY_MODEL=-"
    echo "FLOW_WAVE_POLICY_GATE=-"
    echo "FLOW_WAVE_POLICY_LEDGER=-"
    echo "FLOW_WAVE_POLICY_MERGE_AUTHORITY=-"
    echo "FLOW_WAVE_POLICY_MERGE_STRICT=-"
    echo "FLOW_WAVE_POLICY_MERGE_STRICT_TS=-"
    echo "FLOW_WAVE_POLICY_MERGE_STRICT_AGE=-"
    echo "FLOW_WAVE_POLICY_MERGE_STRICT_STALE=-"
    echo "FLOW_WAVE_POLICY_DEPLOY=-"
    echo "FLOW_WAVE_POLICY_REPO=-"
    echo "FLOW_WAVE_POLICY_TS=-"
    return
  fi
  local pd; pd="$(policy_field "$p" driver)"
  echo "FLOW_WAVE_POLICY=declared"
  echo "FLOW_WAVE_POLICY_REV=$(policy_rev_of "$p")"
  echo "FLOW_WAVE_POLICY_DRIVER=$pd"
  # The wave-level driver's capability fence (#783), derived not restated. The
  # policy field stays FREE TEXT as #699 declared it - an undeclared or unknown
  # driver annotates as '-' rather than becoming a usage error, so a wave naming
  # `flow:auto (Opus 5)` or a downstream driver keeps working unchanged.
  echo "FLOW_WAVE_POLICY_DRIVER_SCOPE=$(driver_cap_dash "$pd" SCOPE)"
  echo "FLOW_WAVE_POLICY_DRIVER_WEB=$(driver_cap_dash "$pd" WEB)"
  echo "FLOW_WAVE_POLICY_DRIVER_CONTAINER=$(driver_cap_dash "$pd" CONTAINER)"
  echo "FLOW_WAVE_POLICY_DRIVER_META=$(driver_cap_dash "$pd" META)"
  echo "FLOW_WAVE_POLICY_DRIVER_CANNOT=$(driver_cap_dash "$pd" CANNOT)"
  echo "FLOW_WAVE_POLICY_AUTHORITY=$(policy_field "$p" authority)"
  echo "FLOW_WAVE_POLICY_AUTHORITY_MODEL=$(policy_field "$p" authority_model)"
  echo "FLOW_WAVE_POLICY_GATE=$(policy_field "$p" gate)"
  echo "FLOW_WAVE_POLICY_LEDGER=$(policy_field "$p" ledger)"
  echo "FLOW_WAVE_POLICY_MERGE_AUTHORITY=$(policy_field "$p" merge_authority)"
  # The branch-protection reading, ITS STAMP, and whether it is still usable
  # (#1026). The stamp travels with the value everywhere the value does, because
  # a reading quoted without its age is the thing that went unbounded.
  echo "FLOW_WAVE_POLICY_MERGE_STRICT=$(policy_field "$p" merge_strict)"
  echo "FLOW_WAVE_POLICY_MERGE_STRICT_TS=$(policy_field "$p" merge_strict_ts)"
  echo "FLOW_WAVE_POLICY_MERGE_STRICT_AGE=$(merge_strict_age "$p")"
  echo "FLOW_WAVE_POLICY_MERGE_STRICT_STALE=$(merge_strict_stale "$p")"
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
  local pd pcannot
  pd="$(policy_field "$p" driver)"
  if [ -n "$pd" ]; then
    pcannot="$(driver_cap "$pd" CANNOT)"
    if [ -n "$pcannot" ]; then
      # Named in the brief, not only in the machine lines: this block is what a
      # compacted worker re-reads, and "this driver cannot take research or web
      # work" is precisely the fact #783 was filed about being invisible.
      echo "     driver:               $pd  [cannot take: $pcannot]"
    else
      echo "     driver:               $pd"
    fi
  fi
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
# reading `outbox-*.md` / `.ack-*` / `.watch-*` here. The mailbox OWNS that
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

# mailbox_watch_state ROLE -> armed | stale | dead | absent | unknown
# The value is the mailbox's FUSED verdict (#801) - the live watcher count
# folded into the heartbeat stamp - not the raw stamp. Before #801 this rendered
# `watch=armed` for a role whose watch had already exited, because the stamp is
# only as fresh as the last wake and the watch is one-shot; the roster was the
# surface where that misread three workers as healthy.
#
# `unknown` covers "no mailbox data at all", "this wave does not use the lane"
# (both render nothing) and now also the mailbox's own `unknown` - a process
# table it could not enumerate, which DOES render, because a watch that cannot
# be assessed is not a watch that is fine.
mailbox_watch_state() {
  [ -n "$MAILBOX_JSON" ] && [ "$MAILBOX_IN_USE" -eq 1 ] || { echo unknown; return; }
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$1" '(.watches // []) | map(select(.role == $r)) | (.[0].state // "absent")'
}

# mailbox_watch_watchers ROLE -> live watcher count, '-' when unknown/absent.
# Rendered beside the state so the roster shows the fact the verdict rests on
# rather than asking a reader to trust the word (#801).
mailbox_watch_watchers() {
  [ -n "$MAILBOX_JSON" ] && [ "$MAILBOX_IN_USE" -eq 1 ] || { echo '-'; return; }
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$1" '(.watches // []) | map(select(.role == $r)) | (.[0].watchers // "-") | tostring'
}

# mailbox_watch_age ROLE -> seconds since the last heartbeat, '-' when none.
mailbox_watch_age() {
  [ -n "$MAILBOX_JSON" ] || { echo '-'; return; }
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$1" '(.watches // []) | map(select(.role == $r)) | (.[0].age_secs // "-") | tostring'
}

# mailbox_route_state ROLE -> confirmed | pending | unconfirmed | unknown
# (issue #814). Read directly from the mailbox's own `routes` array - a
# ROLE-level fact, unlike `acked`/`unread`/`rev` which are BOX-level and
# aggregated above - so this needs no per-box summing. A sibling of
# `mailbox_watch_state`, deliberately never combined with it: `watch` answers
# "is a process polling" (#821-affected, unchanged), `route` answers "has
# anything been acknowledged since" (#821-immune, from ack evidence). Fusing
# them into one word is the #801 mistake this file already tells the story
# of, one issue later.
mailbox_route_state() {
  [ -n "$MAILBOX_JSON" ] && [ "$MAILBOX_IN_USE" -eq 1 ] || { echo unknown; return; }
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$1" '(.routes // []) | map(select(.role == $r)) | (.[0].state // "unknown")'
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
      acked)  printf '%s' "$MAILBOX_JSON" | jq -r '[(.boxes // [])[] | select(.reader == "orchestrator") | .acked] | add // "-"' ;;
      mtime)  printf '%s' "$MAILBOX_JSON" | jq -r '[(.boxes // [])[] | select(.reader == "orchestrator") | .mtime] | max // "-"' ;;
    esac
    return
  fi
  printf '%s' "$MAILBOX_JSON" |
    jq -r --arg r "$role" --arg f "$field" \
      '(.boxes // []) | map(select(.reader == $r)) | (.[0][$f] // "-") | tostring'
}

# A role that has NEVER acknowledged anything, against a box that holds
# something. Its own marker rather than a count, because "acked 0 with a
# non-zero rev" (issue #815 - was "cursor 0" before the mailbox retired the
# read cursor for explicit acknowledgement) is the unambiguous statement that
# nothing has EVER been confirmed received - which is what the 2026-09-05
# worker's roster entry could not say (#778).
mailbox_never_read() {
  local rev acked
  rev="$(mailbox_box_field "$1" rev)"; acked="$(mailbox_box_field "$1" acked)"
  [ "$rev" != "-" ] && [ "$acked" != "-" ] && [ "$rev" -gt 0 ] && [ "$acked" -eq 0 ] 2>/dev/null
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
#: MERGE-STARVATION SCAN (#989), shared by the text and --json renderings.
#: It lived inside the text loop and `--json` exits before that loop, so a
#: machine consumer got no starvation assessment at all and would have had to
#: reconstruct the threshold and the policy rule itself. Computed once, here,
#: and emitted by both.
#:
#: Sets: STARVED (label list), STARVE_N (count at/over threshold),
#: STARVE_OBSERVED (live roles carrying a COMPARABLE baseline), STARVE_LIVE
#: (live roles). The last two exist so a zero can be read: `0 of 0 observed` is
#: "nothing to compare" and `0 of 5 observed` is "looked and found nothing".
#: Does the declared lane cover this path? (#985)
#:
#: MIRRORS ARE DERIVED FROM THE SOURCE, NEVER ENUMERATED. `codex-skills-check` is
#: a CI gate, so regenerating `codex/skills/**` is not optional work a worker
#: chose to do - editing a command document or a bundled script REQUIRES it. Yet
#: no lane in this wave has ever declared a mirror path, so the whole file family
#: sits in nobody lane and the roster overlap report is structurally blind to it:
#: two roles editing DIFFERENT sources that mirror into the same file collide
#: while the roster reads clean. Hand-enumerating mirrors into every lane is the
#: failure this repo keeps filing, so a lane granting a source grants its mirrors.
#:
#: The two derivations, both deterministic from the sync tool contract:
#:   scripts/<name>                     -> codex/skills/*/scripts/<name>
#:   .claude/commands/<fam>/<cmd>.md    -> codex/skills/<fam>-<cmd>/**
#:
#: BOUND, stated rather than discovered: a mirror whose source is neither of those
#: shapes is NOT derived, and such a path reads as outside the lane. That is the
#: safe direction - it refuses and names the file rather than waving it through -
#: but it means a new mirror shape needs this function updated, not a lane edited.
#: Does any entry of LANE_CSV lie UNDER this declaration? (#985)
#: The mirror of `lane_covers`, needed because containment is asymmetric: an
#: untouched `codex/skills` is not covered BY `codex/skills/x/y.md`, yet it is
#: exactly the broad over-claim that contends with it.
lane_split() { # lane_split ARRAY_NAME CSV
  #: Split a declared lane on commas WITHOUT pathname expansion.
  #:
  #: `for _e in $csv` under IFS=',' also PATHNAME-EXPANDS each word, so a
  #: declared `docs/*.md` silently becomes whatever the caller's cwd happens to
  #: contain: a different lane on every machine, and a gate MANUFACTURING the
  #: paths it grades.
  #:
  #: The previous guard was `set -f` around each loop with an unconditional
  #: `set +f` on the way out. That restores globbing ON rather than to the
  #: caller's state, so the first lane_covers call re-enabled expansion for
  #: every loop after it, and the unused-lane scan expanded `*.md` into real
  #: filenames and reported those invented paths as unused - and could report
  #: them CONTESTED against another role (Codex pass 2 on #985).
  #:
  #: `read -ra` splits on IFS and never globs, so the hazard cannot return by
  #: someone adding another CSV loop. `-d ''` so a lane entry containing a
  #: NEWLINE cannot truncate the rest of the lane.
  #:
  #: REVERSAL TRIGGER (#936): this is the one splitter. If a future caller needs
  #: a lane entry to be a PATTERN rather than a literal, that is a new verb with
  #: its own matcher - do not restore pathname expansion here, because expansion
  #: resolves against the caller's cwd and a gate cannot grade what its own cwd
  #: invented.
  local -n _out="$1"
  local _raw _i
  _out=()
  IFS=',' read -r -d '' -a _out < <(printf '%s\0' "$2") || true
  for _i in "${!_out[@]}"; do
    #: Inline trim: this script has no `trim` helper, and calling an undefined
    #: function returns 127 with EMPTY output, so every comparison would
    #: silently be made against "" and every path would read as outside the lane.
    _raw="${_out[$_i]}"
    _raw="${_raw#"${_raw%%[![:space:]]*}"}"
    _raw="${_raw%"${_raw##*[![:space:]]}"}"
    _out[$_i]="$_raw"
  done
}

_lane_contains_any() { # _lane_contains_any DECL LANE_CSV
  local _d="${1%/}" _e; local -a _arr=()
  lane_split _arr "$2"
  for _e in ${_arr[@]+"${_arr[@]}"}; do
    _e="${_e%/}"
    [ -n "$_e" ] || continue
    [ "$_e" = "$_d" ] && return 0
    case "$_e" in "$_d"/*) return 0 ;; esac
  done
  return 1
}

lane_covers() { # lane_covers PATH LANE_CSV
  local _p="$1" _e _base _fam _cmd _skill; local -a _arr=()
  lane_split _arr "$2"
  for _e in ${_arr[@]+"${_arr[@]}"}; do
    [ -n "$_e" ] || continue
    # exact file, or a directory prefix when the entry names one
    [ "$_p" = "$_e" ] && return 0
    case "$_e" in
      */) case "$_p" in "$_e"*) return 0 ;; esac ;;
      *)  case "$_p" in "$_e"/*) return 0 ;; esac ;;
    esac
    # derived: a bundled script mirrors under every skill that references it
    case "$_e" in
      scripts/*)
        _base="${_e#scripts/}"
        case "$_p" in codex/skills/*/scripts/"$_base") return 0 ;; esac
        ;;
      .claude/commands/*/*.md)
        #: A command document grants its GENERATED skill files, but NOT the
        #: scripts bundled under that skill: those derive from `scripts/<name>`,
        #: which is a separately owned lane. Granting them here would let a
        #: worker holding only `register.md` ship a stale bundled copy of another
        #: worker's script while this gate reported ok - the exact revert this
        #: check exists to refuse, arriving through the check.
        _fam="${_e#.claude/commands/}"; _fam="${_fam%%/*}"
        _cmd="${_e##*/}"; _cmd="${_cmd%.md}"
        _skill="codex/skills/${_fam}-${_cmd}"
        case "$_p" in
          "$_skill"/scripts/*) ;;
          "$_skill"/*) return 0 ;;
        esac
        ;;
    esac
  done
  return 1
}

#: lane_missing FROM_CSV TO_CSV -> the FROM entries NO LONGER covered by TO,
#: space-separated, empty when none. The lane-lapse predicate (#1026).
#:
#: TRAILING SLASHES ARE NORMALISED ON BOTH SIDES FIRST, and that is the whole
#: reason this is a function rather than a `lane_covers` call at the use site.
#: `lane_covers` treats a trailing slash as meaningful, so `src` and `src/` -
#: two legitimate spellings of ONE declaration - compare as different paths in
#: one direction only: `lane_covers src/ src` is true and `lane_covers src src/`
#: is false. Used raw, a re-register that merely respells a held path would be
#: reported as DROPPING it, and a drop report that cries wolf on a respelling is
#: one nobody reads - which is the failure this exists to fix, one level up.
#:
#: Containment is deliberate and asymmetric in the useful direction: narrowing
#: `src` to `src/a.py` DROPS the rest of `src` and is reported, while widening
#: `src/a.py` to `src` drops nothing and is not. `lane_covers` owns that
#: judgement - including the derived mirror paths - so this predicate and the
#: `lane-check` gate that grades a diff can never disagree about what a
#: declaration covers.
#: SERIALIZED WITH COMMAS, and COUNTED separately in LANE_MISSING_N - never by
#: word-splitting the result (counter-model review, #1026). `norm_path` keeps
#: inner spaces on purpose, so `docs/My File.md` is ONE valid lane entry that a
#: space-joined string plus `wc -w` reports as two. Commas are also the lane's
#: own serialization - it is what `--files` accepts and what `FLOW_WAVE_FILES`
#: emits - so a caller can feed the result straight back in.
#: BOTH RESULTS COME BACK AS GLOBALS, and the function is called BARE - never in
#: a command substitution. `$( ... )` runs the function in a SUBSHELL, so a count
#: assigned inside it never reaches the caller, and under `set -u` the caller
#: dies on an unbound variable the moment it reads one. Returning the list on
#: stdout and the count in a variable is exactly that trap, so neither is on
#: stdout: `LANE_MISSING` is the comma-joined list, `LANE_MISSING_N` its size.
LANE_MISSING=""
LANE_MISSING_N=0
lane_missing() { # lane_missing FROM_CSV TO_CSV -> sets LANE_MISSING, LANE_MISSING_N
  local _from="$1" _to="$2" _e _t _out="" _to_norm=""
  local -a _fa=() _ta=()
  LANE_MISSING=""
  LANE_MISSING_N=0
  lane_split _ta "$_to"
  for _t in ${_ta[@]+"${_ta[@]}"}; do
    _t="${_t%/}"
    [ -n "$_t" ] || continue
    _to_norm="${_to_norm:+$_to_norm,}$_t"
  done
  lane_split _fa "$_from"
  for _e in ${_fa[@]+"${_fa[@]}"}; do
    _e="${_e%/}"
    [ -n "$_e" ] || continue
    lane_covers "$_e" "$_to_norm" && continue
    _out="${_out:+$_out,}$_e"
    LANE_MISSING_N=$((LANE_MISSING_N + 1))
  done
  LANE_MISSING="$_out"
}

starvation_scan() { # starvation_scan REG WAVE ROLES
  local _reg="$1" _wave="$2" _roles="$3" _r _e _lv _ov _pr
  STARVED=""; STARVE_N=0; STARVE_OBSERVED=0; STARVE_LIVE=0
  STARVE_MIN="${FLOW_WAVE_STARVATION_MIN:-2}"
  for _r in $_roles; do
    _e="$(printf '%s' "$_reg" | jq -c --arg w "$_wave" --arg r "$_r" '.[$w].roles[$r]')"
    _lv="$(liveness_of "$_e")"
    [ "$_lv" = "live" ] || continue
    STARVE_LIVE=$((STARVE_LIVE + 1))
    _pr="$(printf '%s' "$_e" | jq -r '.pr // ""')"
    [ -n "$_pr" ] || continue
    STARVE_OBSERVED=$((STARVE_OBSERVED + 1))
    _ov="$(printf '%s' "$_e" | jq -r '.overtaken // 0')"
    if [ "$_ov" -ge "$STARVE_MIN" ] 2>/dev/null; then
      STARVED="$STARVED $_r:#$_pr:$_ov"
      STARVE_N=$((STARVE_N + 1))
    fi
  done
}

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
[ -n "$VERB" ] || usage_fail "usage: flow-wave-registry.sh register|policy|list|get|verify|release|lane-check|self-address ..."
shift

case "$VERB" in
  register | list | get | verify | release | self-address | policy | lane-check) : ;;
  --help | -h)
    # Print the whole comment header rather than a hand-counted line range: the
    # old fixed `2,96p` silently truncated the moment the header grew, so --help
    # stopped mid-sentence and never mentioned the verbs added after it (#699).
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB" ;;
esac

ROLE=""; WAVE="default"; WAVE_EXPLICIT=0; FORCE=0; JSON_OUT=0; ANY_LIVE_ONLY=0
A_CWD=""; A_REPO=""; A_ISSUE=""; A_BRANCH=""; A_SOCKET=""; A_FROM=""
# Role-level facts (#699). Each is unset-by-default and only written when given,
# so a re-register that omits one never blanks what a fuller one recorded.
A_MODEL=""; A_PERMMODE=""; A_FILES=""; A_CAPACITY=""
A_MODEL_SET=0; A_PERMMODE_SET=0; A_FILES_SET=0; A_CAPACITY_SET=0
A_PR=""; A_BASE=""; A_DIFF=""
A_PR_SET=0; A_BASE_SET=0; A_DIFF_SET=0
# `lane-check --granted` (#1026): the grant that AUTHORISED the lane, so the
# declaration can be compared against it and not only against other lanes.
A_GRANTED=""; A_GRANTED_SET=0
# Wave-level policy fields (#699). Same rule: `policy set` is a MERGE, so an
# amendment names one flag rather than restating the whole policy - restating it
# is how a field gets silently dropped.
P_DRIVER=""; P_AUTHORITY=""; P_AUTHORITY_MODEL=""; P_GATE=""; P_LEDGER=""
P_MERGE_AUTHORITY=""; P_DEPLOY=""; P_MERGE_STRICT=""
P_DRIVER_SET=0; P_AUTHORITY_SET=0; P_AUTHORITY_MODEL_SET=0; P_GATE_SET=0
P_LEDGER_SET=0; P_MERGE_AUTHORITY_SET=0; P_DEPLOY_SET=0; P_MERGE_STRICT_SET=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wave) [ "$#" -ge 2 ] || usage_fail "--wave requires a name"; WAVE="$2"; WAVE_EXPLICIT=1; shift ;;
    --wave=*) WAVE="${1#--wave=}"; WAVE_EXPLICIT=1 ;;
    --force) FORCE=1 ;;
    --json) JSON_OUT=1 ;;
    --any-live) ANY_LIVE_ONLY=1 ;;
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
    --granted) [ "$#" -ge 2 ] || usage_fail "--granted requires a comma-separated path list"; A_GRANTED="$2"; A_GRANTED_SET=1; shift ;;
    --granted=*) A_GRANTED="${1#--granted=}"; A_GRANTED_SET=1 ;;
    --pr) [ "$#" -ge 2 ] || usage_fail "--pr requires a value"; A_PR="$2"; A_PR_SET=1; shift ;;
    --pr=*) A_PR="${1#--pr=}"; A_PR_SET=1 ;;
    --base) [ "$#" -ge 2 ] || usage_fail "--base requires a value"; A_BASE="$2"; A_BASE_SET=1; shift ;;
    --base=*) A_BASE="${1#--base=}"; A_BASE_SET=1 ;;
    --diff) [ "$#" -ge 2 ] || usage_fail "--diff requires a value"; A_DIFF="$2"; A_DIFF_SET=1; shift ;;
    --diff=*) A_DIFF="${1#--diff=}"; A_DIFF_SET=1 ;;
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
    --merge-strict) [ "$#" -ge 2 ] || usage_fail "--merge-strict requires a value"; P_MERGE_STRICT="$2"; P_MERGE_STRICT_SET=1; shift ;;
    --merge-strict=*) P_MERGE_STRICT="${1#--merge-strict=}"; P_MERGE_STRICT_SET=1 ;;
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
E_LIVE=""; E_BASIS=""; E_VERIFIED=""; E_MISMATCH=""; E_SOURCE=""; E_REASON=""; E_BOOTSTRAP=""

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
      # `user-only` is the MOST RESTRICTIVE answer, and its absence was a
      # one-way escape hatch (#1026). The enum offered `orchestrator-only` and
      # `user-and-orchestrator`, so an operator declaring a NARROWER authority
      # than the enum contemplated - this session takes direction from its own
      # user and from nobody else - had to either leave the field empty, which
      # reads as undeclared, or store a value GRANTING authority the owner never
      # delegated. Every available escape was permissive, which is the wrong
      # direction for a field whose whole job is to say who may authorise work.
      case "$P_AUTHORITY_MODEL" in
        orchestrator-only | user-and-orchestrator | user-only) : ;;
        *) usage_fail "--authority-model must be 'orchestrator-only', 'user-and-orchestrator' or 'user-only' (got '$P_AUTHORITY_MODEL'). 'user-only' is the most restrictive value and the correct one when no orchestrator holds authority over this wave - an operator declaring a narrower authority than the enum offers must never have to store a more permissive one" ;;
      esac
    fi
    if [ "$P_MERGE_STRICT_SET" -eq 1 ]; then
      case "$P_MERGE_STRICT" in
        yes | no | unknown) : ;;
        *) usage_fail "--merge-strict must be 'yes', 'no' or 'unknown' (got '$P_MERGE_STRICT'). 'unknown' is a real value and the correct one when branch protection could not be READ - a failure to read must never resolve to 'no'" ;;
      esac
    fi
    if [ "$P_DRIVER_SET" -eq 0 ] && [ "$P_AUTHORITY_SET" -eq 0 ] &&
       [ "$P_AUTHORITY_MODEL_SET" -eq 0 ] && [ "$P_GATE_SET" -eq 0 ] &&
       [ "$P_LEDGER_SET" -eq 0 ] && [ "$P_MERGE_AUTHORITY_SET" -eq 0 ] && [ "$P_MERGE_STRICT_SET" -eq 0 ] &&
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
        | (if $mstrict_set == "1" then .merge_strict = $mstrict else . end)
        | (if $mstrict_set == "1" then .merge_strict_ts = $now else . end)
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
      --arg mstrict "$P_MERGE_STRICT" --arg mstrict_set "$P_MERGE_STRICT_SET" \
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
    if [ -n "$A_REPO" ]; then
      abs_repo="$(cd "$A_REPO" 2>/dev/null && pwd -P)"
      [ -n "$abs_repo" ] && A_REPO="$abs_repo"
    fi
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
      CUR_BASIS="$(liveness_basis_of "$CUR")"
      SAME_OWNER=0
      [ "$CUR_SESSION" != "-" ] && [ "$CUR_SESSION" = "$SELF_SESSION" ] && SAME_OWNER=1
      [ "$CUR_PID" = "$SELF_PID" ] && SAME_OWNER=1
      # An ALLOW-LIST of states that release the role, never a deny-list of
      # states that hold it (#869). `!= stale` would read a brand-new state as
      # takeable, which is this issue's own defect - weaker evidence beating
      # stronger - reproduced one layer up. Only a PROVEN death frees a role:
      # `unknown` means we could not determine the owner is gone, and that is
      # not the same as determining it is.
      case "$CUR_LIVE" in
        stale|released) HELD=0 ;;
        *)              HELD=1 ;;
      esac
      if [ "$SAME_OWNER" -eq 0 ] && [ "$HELD" -eq 1 ] && [ "$FORCE" -eq 0 ]; then
        if [ "$CUR_LIVE" = "live" ]; then
          echo "flow-wave-registry: role '$ROLE' (wave '$WAVE') is held by a LIVE session (pid $CUR_PID, session $CUR_SESSION)." >&2
        else
          echo "flow-wave-registry: role '$ROLE' (wave '$WAVE') is held by a session whose liveness is UNDETERMINABLE (pid $CUR_PID, session $CUR_SESSION, basis $CUR_BASIS)." >&2
          echo "  This host cannot enumerate its process table, so the owner is not known to be gone - which is not the same as knowing it is alive." >&2
        fi
        echo "  Two sessions both believing they are '$ROLE' is the failure this command exists to prevent (#638)." >&2
        echo "  Pick another role, or re-run with --force if you are certain that session is gone." >&2
        E_SOCKET="$(printf '%s' "$CUR" | jq -r '.socket // "unknown"')"
        E_PID="$CUR_PID"; E_SESSION="$CUR_SESSION"; E_LIVE="$CUR_LIVE"; E_BASIS="$CUR_BASIS"
        emit refused
        exit 1
      fi
      if [ "$SAME_OWNER" -eq 0 ]; then
        case "$CUR_LIVE" in
          stale)
            echo "flow-wave-registry: taking over stale role '$ROLE' (owner pid $CUR_PID is gone)." >&2 ;;
          unknown)
            # Only reachable under --force, and the loudest line here: the
            # operator is overriding an unanswered question, not a known death.
            echo "flow-wave-registry: --force taking over role '$ROLE' whose owner (pid $CUR_PID) was NOT confirmed gone (basis $CUR_BASIS)." >&2 ;;
        esac
      fi
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
    #: A merge observation is ATOMIC: (repo, pr, base, diff) or nothing (#989).
    #: Recording the three parts independently let a partial update corrupt the
    #: baseline - a base-only write made the NEXT complete observation miss its
    #: overtake, and a diff-only write made it fire although the diff had moved.
    #: An observation is a baseline only if all of it was measured at once.
    A_OBS=0
    if [ "$A_PR_SET" -eq 1 ] || [ "$A_BASE_SET" -eq 1 ] || [ "$A_DIFF_SET" -eq 1 ]; then
      case "$A_PR" in
        "" ) usage_fail "--pr needs a value: an observation with no PR identity cannot be compared to anything" ;;
        *[!0-9]* ) usage_fail "--pr must be the PR NUMBER (got: $A_PR). A free-form value cannot be compared across observations and corrupts the aggregate count" ;;
      esac
      [ -n "$A_BASE" ] || usage_fail "--base needs a value: an empty base is a MISSING measurement, not an unchanged one"
      [ -n "$A_DIFF" ] || usage_fail "--diff needs a value: an empty diff is a MISSING measurement, and counting it as unchanged invents overtakes that never happened"
      if [ "$A_PR_SET" -ne 1 ] || [ "$A_BASE_SET" -ne 1 ] || [ "$A_DIFF_SET" -ne 1 ]; then
        usage_fail "--pr, --base and --diff must be given TOGETHER: a partial observation cannot serve as a comparison baseline"
      fi
      A_OBS=1
    fi
    POL="$(policy_json "$WAVE")"
    POL_REV="$(policy_rev_of "$POL")"
    # Role-level facts are PRESERVED when their flag is omitted, unlike
    # cwd/repo/issue/branch above, which a re-register rewrites. The difference is
    # deliberate and worth stating: those describe a LANE, which genuinely goes
    # stale (the #683 trap), while model / permission mode / capacity / file lane
    # / driver describe the SESSION and its grant, and re-registering is the documented
    # cheap re-brief (#670). Blanking a granted file lane because a compacted
    # worker re-registered to re-read the protocol would delete the very thing
    # overlap detection reads. Passing an empty value (`--files ""`) clears a
    # field explicitly - the flag was given, so intent is unambiguous.
    # The witness against pid recycling (#1094): THIS pid's own start time,
    # captured now while it is unambiguously the registering session's own
    # process, never re-derived later against whatever the kernel currently
    # has that number pointing at.
    SELF_PID_STARTED="$(pid_started_of "$SELF_PID")"
    # Vantage (#959), measured HERE because here is the only place the answer
    # exists - see `vantage_derive` above. Recorded like `pid_started`: captured
    # now, while this process is unambiguously the registering session's own,
    # never re-derived later by a reader on another machine.
    vantage_derive
    with_lock '
      .[$w] //= {"roles": {}} |
      (.[$w].roles[$r] // {}) as $prev |
      .[$w].roles[$r] = {
        socket: $sock, self_socket: $selfsock, pid: ($pid | tonumber? // $pid),
        pid_started: $pidstarted,
        session: $session, host: $host, cwd: $cwd, repo: $repo,
        issue: $issue, branch: $branch, registered_ts: ($now | tonumber),
        verified: ($verified == "true"), address_mismatch: ($mismatch == "true"),
        address_filled: ($filled == "true"), released: false,
        model:           (if $model_set == "1" then $model else ($prev.model // "") end),
        permission_mode: (if $perm_set  == "1" then $perm  else ($prev.permission_mode // "") end),
        files:           (if $files_set == "1" then $files else ($prev.files // "") end),
        capacity:        (if $cap_set   == "1" then $cap   else ($prev.capacity // "") end),
        driver:          (if $drv_set   == "1" then $drv   else ($prev.driver // "") end),
        #: MEASURED EVERY REGISTRATION, never preserved from $prev (#959). The
        #: role-level facts above are preserved because they describe a GRANT
        #: the session was given; this describes WHERE THE PROCESS IS, and a
        #: re-register can be a different process - a worker restarted inside a
        #: container under a role a host session held. A preserved vantage would
        #: then assert the placement of the day before with full confidence,
        #: which is the exact objection #959 raises against a declared indicator.
        vantage:         $vantage,
        vantage_source:  $vsource,
        vantage_basis:   $vbasis,
        #: Written only as a COMPLETE observation, and identity is (repo, pr) -
        #: not pr alone, or repository B #5 would increment repository A #5.
        pr:       (if $obs == "1" then $pr   else ($prev.pr // "") end),
        base:     (if $obs == "1" then $base else ($prev.base // "") end),
        diff:     (if $obs == "1" then $diff else ($prev.diff // "") end),
        obs_repo: (if $obs == "1" then $repo else ($prev.obs_repo // "") end),
        #: MERGE STARVATION (#989). Increments ONLY when the same (repo, pr) is
        #: seen again with a CHANGED base and an UNCHANGED diff: the signature of
        #: losing a queue place without doing any work. A changed diff is a worker
        #: responding to review and must not count, or the signal fires on ordinary
        #: rebase traffic and becomes one nobody reads.
        #:
        #: A CHANGE OF IDENTITY RESETS to 0 and carries the new baseline with it,
        #: including a role taken over by another session - which would otherwise
        #: inherit a stranger PR and make an old warning live again for unrelated
        #: work. A re-register carrying NO observation preserves, so the cheap
        #: re-brief never destroys a baseline.
        overtaken: (
          if $obs != "1" then ($prev.overtaken // 0)
          elif ($prev.pr // "") != $pr or ($prev.obs_repo // "") != $repo then 0
          elif ($prev.base // "") == "" or ($prev.diff // "") == "" then 0
          elif ($prev.base // "") != $base and ($prev.diff // "") == $diff
          then (($prev.overtaken // 0) + 1)
          else ($prev.overtaken // 0) end
        ),
        policy_rev:      ($polrev | tonumber)
      }' \
      --arg w "$WAVE" --arg r "$ROLE" --arg sock "$SOCK" --arg pid "$SELF_PID" \
      --arg pidstarted "$SELF_PID_STARTED" \
      --arg selfsock "$SELF_SOCK" --arg verified "$KEEP_VERIFIED" \
      --arg filled "$KEEP_FILLED" --arg mismatch "$KEEP_MISMATCH" \
      --arg session "$SELF_SESSION" --arg host "$SELF_HOST" --arg cwd "$A_CWD" \
      --arg repo "$A_REPO" --arg issue "$A_ISSUE" --arg branch "$A_BRANCH" \
      --arg model "$A_MODEL" --arg model_set "$A_MODEL_SET" \
      --arg perm "$A_PERMMODE" --arg perm_set "$A_PERMMODE_SET" \
      --arg files "$A_FILES" --arg files_set "$A_FILES_SET" \
      --arg cap "$A_CAPACITY" --arg cap_set "$A_CAPACITY_SET" \
      --arg pr "$A_PR" --arg base "$A_BASE" --arg diff "$A_DIFF" --arg obs "$A_OBS" \
      --arg drv "$P_DRIVER" --arg drv_set "$P_DRIVER_SET" \
      --arg vantage "$V_VANTAGE" --arg vsource "$V_SOURCE" --arg vbasis "$V_BASIS" \
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
    # A declared lane with NO repo is an UNSCOPED lane (#800), reported HERE for
    # the same reason the shared-parent advisory above is: one re-register fixes
    # it, and the alternative is an orchestrator never noticing, because there is
    # nothing to notice - the roster reads clean.
    #
    # The stored entry is read BACK rather than judged from the flags, because
    # the flags are precisely what cannot answer this: `--files` may have been
    # omitted and PRESERVED from the previous registration while `--repo` was
    # omitted and REWRITTEN to empty. That asymmetry IS the bug, so the check has
    # to look at what was actually recorded. Reading the entry also means this
    # keeps telling the truth if a field ever moves between the two groups.
    #
    # The `orchestrator` is skipped because `list` exempts it from the pairwise
    # checks unconditionally: it holds no lane, so "its lane is unscoped" is not
    # a fact about anything.
    NEW_ENTRY="$(entry_json "$WAVE" "$ROLE")"
    NEW_REPO="$(printf '%s' "$NEW_ENTRY" | jq -r '.repo // ""')"
    NEW_FILES="$(printf '%s' "$NEW_ENTRY" | jq -r '.files // ""')"
    NEW_ISSUE="$(printf '%s' "$NEW_ENTRY" | jq -r '.issue // ""')"
    # THE LANE LAPSE (#1026). `--files` REPLACES wholesale, so a role that
    # re-registers for its next issue with a new list loses its claim on
    # everything it held - at the moment it is most likely to have just merged
    # the file. Nothing reported the drop, and after it the roster cannot
    # distinguish "nobody has claimed this path" from "nobody is in conflict
    # over it": both render as silence, which is the failure class this whole
    # file exists to refuse.
    #
    # Reported rather than PREVENTED, deliberately. Merging the two lists would
    # make a lane only ever grow, so a role could never put a path down and
    # `REVOKE` would be the only way back - and a lane nobody can narrow is how
    # one role ends up holding the repository. Replacement is the right
    # mechanism; its SILENCE was the defect.
    #
    # Computed from the STORED entry on both sides, never from the flags: with
    # `--files` omitted the value is PRESERVED, so the flags cannot say what the
    # lane now is. Reading both entries also means this keeps telling the truth
    # if the preserve/rewrite grouping ever changes.
    # A RELEASED prior entry has already given its lane up (counter-model review
    # pass 2, #1026), so re-using the role is not a drop - `release` was the
    # withdrawal, and reporting it again at the next registration would fire the
    # loudest warning here on ordinary role re-use. `.files` survives a release
    # (the entry is marked, not erased), which is exactly why this has to be
    # asked rather than inferred from the field being present.
    PREV_FILES=""
    if [ "$CUR" != "null" ] && [ "$(printf '%s' "$CUR" | jq -r '.released // false')" != "true" ]; then
      PREV_FILES="$(printf '%s' "$CUR" | jq -r '.files // ""')"
    fi
    lane_missing "$PREV_FILES" "$NEW_FILES"
    FILES_DROPPED="$LANE_MISSING"; FILES_DROPPED_N="$LANE_MISSING_N"
    lane_missing "$NEW_FILES" "$PREV_FILES"
    FILES_ADDED="$LANE_MISSING"; FILES_ADDED_N="$LANE_MISSING_N"
    if [ "$FILES_DROPPED_N" -gt 0 ]; then
      echo "flow-wave-registry: role '$ROLE' DROPPED $FILES_DROPPED_N path(s) from its declared lane: $FILES_DROPPED" >&2
      # SAYS ONLY WHAT THIS COMMAND CHECKED (counter-model review, #1026). The
      # earlier wording claimed "nothing else holds these paths now" - a
      # ROSTER-WIDE fact that `register` never looks up, and which another live
      # role may flatly contradict. The per-role delta is what was measured; who
      # holds a path now is `list`'s question, so the reader is sent there
      # rather than handed a fabricated answer.
      echo "  --files REPLACES the lane; it does not extend it. THIS role no longer holds those paths, and a path it has stopped claiming reads on the roster exactly like an uncontested one (#1026)." >&2
      echo "  Run 'list --wave $WAVE' for who holds them now; re-register naming the COMPLETE lane if that was not the intent." >&2
    fi
    E_LANE_SCOPED="-"
    if [ "$ROLE" != "orchestrator" ] && { [ -n "$NEW_FILES" ] || [ -n "$NEW_ISSUE" ]; }; then
      E_LANE_SCOPED=yes
      if lane_unscoped "$NEW_REPO" "$NEW_FILES" "$NEW_ISSUE"; then
        E_LANE_SCOPED=no
        DECLARED=""
        [ -n "$NEW_FILES" ] && DECLARED="$DECLARED files=$NEW_FILES"
        [ -n "$NEW_ISSUE" ] && DECLARED="$DECLARED issue=$NEW_ISSUE"
        if [ -z "$NEW_REPO" ]; then
          echo "flow-wave-registry: role '$ROLE' declares a lane (${DECLARED# }) but NO repo - overlap detection is UNSCOPED for it (#800)." >&2
        else
          echo "flow-wave-registry: role '$ROLE' declares a lane (${DECLARED# }) but repo '$NEW_REPO' does not resolve to a directory - overlap detection is UNSCOPED for it (#891)." >&2
        fi
        echo "  The same-issue and FILE-LANE arms compare same-repo pairs only, so an empty or non-resolving repo matches nothing and 'list' reads CLEAN while this lane goes unchecked." >&2
        echo "  Re-register with --repo <path>. --repo is REWRITTEN by every re-register - unlike --files, which is preserved - so it must be passed EVERY time." >&2
      fi
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
    echo "FLOW_WAVE_LANE_SCOPED=$E_LANE_SCOPED"
    echo "FLOW_WAVE_FILES=${NEW_FILES:--}"
    echo "FLOW_WAVE_FILES_DROPPED=${FILES_DROPPED:--}"
    echo "FLOW_WAVE_FILES_ADDED=${FILES_ADDED:--}"
    # The role's OWN driver, read back (#1026). `register` stored `--driver` and
    # emitted nothing, so a silently-accepted flag and a silently-IGNORED one
    # were byte-identical at the only moment a caller could still fix a typo.
    # The block is the one `get` already prints, from the same stored entry -
    # a second spelling of the same fact is how the two drift.
    REG_DRIVER="$(printf '%s' "$NEW_ENTRY" | jq -r '.driver // "" | if . == null then "" else . end')"
    echo "FLOW_WAVE_DRIVER=${REG_DRIVER:--}"
    echo "FLOW_WAVE_DRIVER_SCOPE=$(driver_cap_dash "$REG_DRIVER" SCOPE)"
    echo "FLOW_WAVE_DRIVER_WEB=$(driver_cap_dash "$REG_DRIVER" WEB)"
    echo "FLOW_WAVE_DRIVER_CONTAINER=$(driver_cap_dash "$REG_DRIVER" CONTAINER)"
    echo "FLOW_WAVE_DRIVER_META=$(driver_cap_dash "$REG_DRIVER" META)"
    echo "FLOW_WAVE_DRIVER_CANNOT=$(driver_cap_dash "$REG_DRIVER" CANNOT)"
    # THE TOOLCHAIN THIS SESSION WILL ACTUALLY RUN (#1029). Registration is where
    # a session declares its vantage, and until now vantage meant address, lane
    # and policy - never which VERSION of the instruments it holds. On 2026-09-15
    # a wave ran for eleven hours on a shared checkout 21 commits behind
    # `origin/main`: every helper resolved, every gate was green, and none of the
    # merged work those commits carried was reachable from any of it. The gap was
    # found only when a worker tried to use a flag that had shipped and did not
    # exist here.
    #
    # A NUMBER, not a boolean, and `unknown` is not zero - the helper owns that
    # distinction and this only relays it. Emitted on EVERY registration, because
    # re-registering is the documented cheap re-brief (#670) and a stale
    # toolchain is exactly the kind of fact a compacted worker needs re-told.
    # Advisory: no verdict changes, no exit code moves, and a missing helper
    # reports `unavailable` rather than silently reporting nothing.
    # The gap and the AGE OF THE EVIDENCE behind it are one fact. Emitting only
    # the verdict and the count let `current / 0` reach an orchestrator with no
    # way to see it was measured against a remote-tracking ref last refreshed
    # months ago - the original failure with a number attached (counter-model
    # review, codex/gpt-6-astra).
    TOOLCHAIN_STATE=unavailable
    TOOLCHAIN_N="-"
    TOOLCHAIN_UP="-"
    TOOLCHAIN_AGE="-"
    TC_HELPER=""
    for candidate in "$SELF_DIR/toolchain-provenance.sh" "$HOME/.claude/scripts/toolchain-provenance.sh"; do
        [ -x "$candidate" ] && { TC_HELPER="$candidate"; break; }
    done
    if [ -n "$TC_HELPER" ]; then
      TC_JSON="$("$TC_HELPER" --json 2>/dev/null)"
      if [ -n "$TC_JSON" ]; then
        TOOLCHAIN_STATE="$(printf '%s' "$TC_JSON" | jq -r '.verdict // "unavailable"' 2>/dev/null || echo unavailable)"
        # `// "-"` is NOT enough for a numeric field: jq's alternative operator
        # fires on null AND on false, but `0` is neither - it passes through,
        # which is correct here and is exactly why the null case needs its own
        # spelling rather than a default that happens to look right.
        TOOLCHAIN_N="$(printf '%s' "$TC_JSON" | jq -r 'if .behind == null then "-" else .behind end' 2>/dev/null || echo -)"
        TOOLCHAIN_UP="$(printf '%s' "$TC_JSON" | jq -r '.upstream // "-"' 2>/dev/null || echo -)"
        TOOLCHAIN_AGE="$(printf '%s' "$TC_JSON" | jq -r 'if .fetch_age_seconds == null then "-" else .fetch_age_seconds end' 2>/dev/null || echo -)"
        [ -n "$TOOLCHAIN_STATE" ] || TOOLCHAIN_STATE=unavailable
        for tc_var in TOOLCHAIN_N TOOLCHAIN_UP TOOLCHAIN_AGE; do
          eval "tc_value=\$$tc_var"
          [ -n "$tc_value" ] || eval "$tc_var='-'"
        done
      fi
    fi
    echo "FLOW_WAVE_TOOLCHAIN=$TOOLCHAIN_STATE"
    echo "FLOW_WAVE_TOOLCHAIN_BEHIND=$TOOLCHAIN_N"
    echo "FLOW_WAVE_TOOLCHAIN_UPSTREAM=$TOOLCHAIN_UP"
    echo "FLOW_WAVE_TOOLCHAIN_AGE=$TOOLCHAIN_AGE"
    case "$TOOLCHAIN_STATE" in
      behind|diverged)
        echo "flow-wave-registry: this session's CPP toolchain is ${TOOLCHAIN_N} commit(s) BEHIND its upstream." >&2
        echo "  Helpers here predate what main ships: a flag that merged may simply not exist in the copy you run (#1029)." >&2
        echo "  Pull at a declared safe moment - scripts/checkout-readers.sh says when no gate is running out of the tree." >&2
        ;;
      unknown|unavailable)
        echo "flow-wave-registry: this session's CPP toolchain provenance is ${TOOLCHAIN_STATE} - NOT a measured zero (#1029)." >&2
        ;;
      current)
        # A zero gap against week-old evidence is still a zero gap against
        # week-old evidence. Said once, at the point the wave is briefed.
        if [ "$TOOLCHAIN_AGE" != "-" ] && [ "$TOOLCHAIN_AGE" -gt 86400 ] 2>/dev/null; then
          echo "flow-wave-registry: toolchain reads current against ${TOOLCHAIN_UP}, but that reference was last refreshed $(( TOOLCHAIN_AGE / 86400 ))d ago (#1029)." >&2
          echo "  The gap is measured against what this checkout last fetched, not against the remote as it is now." >&2
        fi
        ;;
    esac
    # WHICH SIDE OF THE CONTAINER BOUNDARY THIS SESSION IS ON (#959). Read back
    # from the STORED entry rather than from the variables just measured, for
    # the #800 reason: what a later reader sees is what was recorded, so a field
    # that silently failed to store must not print here as though it had.
    REG_VANTAGE="$(printf '%s' "$NEW_ENTRY" | jq -r '.vantage // "unavailable" | if . == "" then "unavailable" else . end')"
    echo "FLOW_WAVE_VANTAGE=$REG_VANTAGE"
    echo "FLOW_WAVE_VANTAGE_SOURCE=$(printf '%s' "$NEW_ENTRY" | jq -r '.vantage_source // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_VANTAGE_BASIS=$(printf '%s' "$NEW_ENTRY" | jq -r '.vantage_basis // "-" | if . == "" then "-" else . end')"
    case "$REG_VANTAGE" in
      container)
        # NOT a warning. In a fleet whose target placement is a per-session
        # container this is the ORDINARY state, and an alarm that fires on the
        # ordinary state is one nobody reads (#674). It is a re-brief: the lane
        # order inverts here, and a compacted worker needs re-telling.
        echo "flow-wave-registry: CONTAINER vantage - the mailbox is lane 1 here, and 'SendMessage' reaches no fleet peer (#959)." >&2
        ;;
      unknown)
        echo "flow-wave-registry: vantage UNKNOWN - the signals disagreed or could not be read; this is NOT 'host' (#959)." >&2
        echo "  Route through the MAILBOX until it resolves, and leave the unknown visible rather than defaulting past it." >&2
        ;;
      unavailable)
        echo "flow-wave-registry: flow-vantage.sh is not installed - vantage is unavailable, which is NOT a measured 'host' (#959)." >&2
        echo "  Install the helper family with /flow:repair to record it." >&2
        ;;
    esac
    E_SOCKET="$SOCK"; E_PID="$SELF_PID"; E_SESSION="$SELF_SESSION"; E_LIVE=live; E_BASIS=self
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
    E_BASIS="$(liveness_basis_of "$CUR")"
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
    # Vantage (#959), SERVED not re-derived. `get` is the scripting contract an
    # orchestrator routes on, and it runs on the ORCHESTRATOR's machine - so
    # measuring here would answer a question about the wrong process while
    # printing it under this role's name. An entry registered before #959 has no
    # stored value and reads `unrecorded`: a word of its own, because "nobody
    # measured this" and "the measurement came back unknown" send a reader to
    # different places, and neither is `host`.
    echo "FLOW_WAVE_VANTAGE=$(printf '%s' "$CUR" | jq -r '.vantage // "unrecorded" | if . == "" then "unrecorded" else . end')"
    echo "FLOW_WAVE_VANTAGE_SOURCE=$(printf '%s' "$CUR" | jq -r '.vantage_source // "-" | if . == "" then "-" else . end')"
    echo "FLOW_WAVE_VANTAGE_BASIS=$(printf '%s' "$CUR" | jq -r '.vantage_basis // "-" | if . == "" then "-" else . end')"
    # Whether this role's lane can be overlap-checked AT ALL (#800). `get` is the
    # scripting contract, and FLOW_WAVE_REPO / FLOW_WAVE_FILES answer this only
    # for a caller who already knows the same-repo scoping rule - so the answer
    # is reported directly rather than left to be re-derived, correctly, by
    # everyone. `-` means the role declares no repo-scoped lane fact (or is the
    # orchestrator, which the pairwise checks exempt); `no` means it declares one
    # that cannot be compared with anybody.
    GET_REPO="$(printf '%s' "$CUR" | jq -r '.repo // ""')"
    GET_FILES="$(printf '%s' "$CUR" | jq -r '.files // ""')"
    GET_ISSUE="$(printf '%s' "$CUR" | jq -r '.issue // ""')"
    GET_SCOPED="-"
    if [ "$ROLE" != "orchestrator" ] && { [ -n "$GET_FILES" ] || [ -n "$GET_ISSUE" ]; }; then
      GET_SCOPED=yes
      lane_unscoped "$GET_REPO" "$GET_FILES" "$GET_ISSUE" && GET_SCOPED=no
    fi
    echo "FLOW_WAVE_LANE_SCOPED=$GET_SCOPED"
    # The role's driver and what it structurally CANNOT take (#783). This is the
    # line an orchestrator reads before routing: a research ticket sent to a role
    # whose FLOW_WAVE_DRIVER_CANNOT names `research` is the mis-route the issue
    # was filed about, and it is now answerable without asking the worker.
    GET_DRIVER="$(printf '%s' "$CUR" | jq -r '.driver // "" | if . == null then "" else . end')"
    echo "FLOW_WAVE_DRIVER=${GET_DRIVER:--}"
    echo "FLOW_WAVE_DRIVER_SCOPE=$(driver_cap_dash "$GET_DRIVER" SCOPE)"
    echo "FLOW_WAVE_DRIVER_WEB=$(driver_cap_dash "$GET_DRIVER" WEB)"
    echo "FLOW_WAVE_DRIVER_CONTAINER=$(driver_cap_dash "$GET_DRIVER" CONTAINER)"
    echo "FLOW_WAVE_DRIVER_META=$(driver_cap_dash "$GET_DRIVER" META)"
    echo "FLOW_WAVE_DRIVER_CANNOT=$(driver_cap_dash "$GET_DRIVER" CANNOT)"
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
    CUR_BASIS="$(liveness_basis_of "$CUR")"
    # Allow-list, for the same reason as `register` above (#869).
    case "$CUR_LIVE" in
      stale|released) HELD=0 ;;
      *)              HELD=1 ;;
    esac
    if [ "$SAME_OWNER" -eq 0 ] && [ "$HELD" -eq 1 ] && [ "$FORCE" -eq 0 ]; then
      if [ "$CUR_LIVE" = "live" ]; then
        echo "flow-wave-registry: role '$ROLE' belongs to a LIVE session (pid $CUR_PID) - not releasing. Pass --force to override." >&2
      else
        echo "flow-wave-registry: role '$ROLE' belongs to a session whose liveness is UNDETERMINABLE (pid $CUR_PID, basis $CUR_BASIS) - not releasing. Pass --force to override." >&2
      fi
      E_PID="$CUR_PID"; E_SESSION="$CUR_SESSION"; E_LIVE="$CUR_LIVE"; E_BASIS="$CUR_BASIS"
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

  #: LANE CHECK (#985). Compare what this change ACTUALLY touches against the
  #: file lane this role declared, and refuse a path the role never claimed.
  #:
  #: WHY A NAME LIST AND NOT A DIFF RANGE. Two mechanisms produce a stale payload
  #: and only one is a range problem. If the branch is old-base plus your work,
  #: `git diff origin/main` renders a sibling's merged additions as your
  #: deletions, and three-dot fixes it. But `git reset --soft origin/main` moves
  #: HEAD to the NEW main while the index still holds the OLD tree: the commit
  #: then has new main as its PARENT and old content as its TREE, the merge base
  #: IS origin/main, and EVERY diff form agrees with every other. Agreement reads
  #: as confirmation. There is no range that reveals it because nothing is wrong
  #: with the range - the content is wrong.
  #:
  #: So this compares NAMES against a declared lane. A file the role never claimed
  #: appearing in its own diff is the whole signal, and it is the only signal that
  #: survives both mechanisms. Every content-based gate is structurally blind
  #: here: a suite cannot object to work that is not there, and `make verify`
  #: passed on a tree with a merged PR simply absent from it.
  #:
  #: NO DECLARED LANE IS UNKNOWN, NEVER PASS. A role that declared no `files=` has
  #: nothing to compare against, and reporting that as clean would make the gate
  #: go quiet exactly when it has nothing to check.
  lane-check)
    REG="$(read_registry)"
    CUR="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$ROLE" '.[$w].roles[$r] // empty')"
    [ -n "$CUR" ] || { echo "flow-wave-registry: role '$ROLE' is not registered in wave '$WAVE'" >&2; emit error; exit 2; }
    LANE="$(printf '%s' "$CUR" | jq -r '.files // ""')"
    BASE_REF="${A_BASE:-origin/main}"

    #: A declaration carrying `..` or `./` cannot be compared lexically - both
    #: containment and exact-match would answer about the literal string rather
    #: than the path it resolves to, so `docs/foo` and `docs/foo/../bar.md` would
    #: read as overlapping. Refused rather than normalised: the registry does not
    #: own path resolution, and a silently rewritten lane is a lane nobody
    #: declared (#985).
    case ",$LANE," in
      *,*/../*,*|*,../*,*|*,*/..,*|*,./*,*|*,*/./*,*)
        echo "FLOW_WAVE_LANE_CHECK=unknown"
        echo "flow-wave-registry: UNKNOWN - the declared lane contains a non-canonical path ('.' or '..'), which cannot be compared lexically. Re-register with repository-relative paths." >&2
        emit error; exit 2 ;;
    esac

    if [ -z "$LANE" ]; then
      echo "FLOW_WAVE_LANE_CHECK=unknown"
      echo "FLOW_WAVE_LANE_EXTRA=0"
      echo "flow-wave-registry: UNKNOWN - role '$ROLE' declared no file lane, so its diff cannot be compared to anything." >&2
      echo "flow-wave-registry: this is NOT a pass. Re-register with --files (and --repo on the same call, #800)." >&2
      emit error
      exit 2
    fi
    #: THE LANE VERSUS THE GRANT THAT AUTHORISED IT (#1026).
    #:
    #: Everything above compares a lane against other LANES, and the diff check
    #: below compares it against a DIFF. Neither ever compares it against the
    #: grant it came from - and the grant is the one side that changes shape on
    #: the way in: a grant is prose in a message, a lane is data in the registry,
    #: and the hop between them is exactly where a path gets dropped (#1026's
    #: own primary defect) or silently widened. Only the second half of that
    #: journey was ever checked.
    #:
    #: This runs BEFORE git, deliberately. It compares two DECLARATIONS and needs
    #: no repository at all, so a host with no git - or a branch with no merge
    #: base - still gets the answer. It is also the more fundamental verdict: a
    #: lane wider than its grant is wrong whatever the diff turns out to be.
    #:
    #: `-` WHEN NO GRANT WAS SUPPLIED, never `0`. A zero would claim a comparison
    #: nobody asked for; `-` says the question was not put. Both counts are
    #: emitted on every path that reaches a verdict, so an absent grant check is
    #: distinguishable from a passing one.
    LANE_UNGRANTED="-"; LANE_UNGRANTED_N="-"
    LANE_UNCLAIMED="-"; LANE_UNCLAIMED_N="-"
    if [ "$A_GRANTED_SET" -eq 1 ]; then
      #: The same refusal the declared lane gets: a grant carrying `.` or `..`
      #: cannot be compared lexically, and normalising it here would compare
      #: against a grant nobody wrote.
      case ",$A_GRANTED," in
        *,*/../*,*|*,../*,*|*,*/..,*|*,./*,*|*,*/./*,*)
          echo "FLOW_WAVE_LANE_CHECK=unknown"
          echo "flow-wave-registry: UNKNOWN - the supplied grant contains a non-canonical path ('.' or '..'), which cannot be compared lexically. Restate it with repository-relative paths." >&2
          emit error; exit 2 ;;
      esac
      #: EMPTINESS IS DECIDED BY THE SAME SPLITTER THAT DOES THE COMPARISON
      #: (counter-model review pass 2, #1026). A hand-rolled `tr -d ', '` test
      #: strips only commas and ASCII spaces, so `--granted $'\t'` read as
      #: non-empty here and then trimmed to NOTHING in `lane_split` - and a grant
      #: of nothing makes EVERY declared lane entry ungranted, turning a caller's
      #: unexpanded variable into a wall of findings and an exit 1. Asking the
      #: splitter means the two can never disagree about what "empty" is.
      GRANT_ARR=(); lane_split GRANT_ARR "$A_GRANTED"
      GRANT_N=0
      for _g in ${GRANT_ARR[@]+"${GRANT_ARR[@]}"}; do
        [ -n "$_g" ] && GRANT_N=$((GRANT_N + 1))
      done
      [ "$GRANT_N" -gt 0 ] || {
        echo "FLOW_WAVE_LANE_CHECK=unknown"
        echo "flow-wave-registry: UNKNOWN - --granted resolved to NO paths. An empty grant is a MISSING measurement, not a grant of nothing; omit the flag, or name what was granted." >&2
        emit error; exit 2; }
      #: lane_missing NORMALISES both sides and defers containment to
      #: `lane_covers`, which is why two legitimate spellings of one path - `src`
      #: and `src/`, or a file inside a granted directory - do not read as two
      #: different files. String equality here would manufacture a finding out of
      #: how somebody typed a path.
      lane_missing "$LANE" "$A_GRANTED"
      LANE_UNGRANTED="$LANE_MISSING"; LANE_UNGRANTED_N="$LANE_MISSING_N"
      lane_missing "$A_GRANTED" "$LANE"
      LANE_UNCLAIMED="$LANE_MISSING"; LANE_UNCLAIMED_N="$LANE_MISSING_N"
      #: UNCLAIMED IS LOUD BUT NOT A REFUSAL, and the asymmetry is the point.
      #: A granted path missing from the lane is #1026's lapse seen from the
      #: other side: the registry is not protecting it, so another role can claim
      #: it and nothing collides. That is worth saying every time - but the
      #: worker's DIFF may be perfectly correct, and refusing it would block work
      #: over a bookkeeping gap. It is reported, counted, and left to the reader.
      if [ "$LANE_UNCLAIMED_N" != "0" ]; then
        echo "flow-wave-registry: $LANE_UNCLAIMED_N granted path(s) are NOT in the declared lane of '$ROLE': $LANE_UNCLAIMED" >&2
        echo "  The registry is not protecting them: another role can claim one and overlap detection will report nothing (#1026)." >&2
        echo "  Re-register with --files naming the COMPLETE lane if the grant still stands." >&2
      fi
      #: UNGRANTED IS A REFUSAL. A lane claiming what nobody granted is how one
      #: role quietly takes another's file, and unlike the diff check below it
      #: fires before a single line is written.
      if [ "$LANE_UNGRANTED_N" != "0" ]; then
        echo "FLOW_WAVE_LANE_UNGRANTED=$LANE_UNGRANTED_N"
        echo "FLOW_WAVE_LANE_UNCLAIMED=$LANE_UNCLAIMED_N"
        echo "FLOW_WAVE_LANE_CHECK=ungranted"
        echo "flow-wave-registry: $LANE_UNGRANTED_N path(s) in the declared lane of '$ROLE' were NEVER GRANTED: $LANE_UNGRANTED" >&2
        echo "flow-wave-registry: a lane wider than its grant takes files nobody handed over - fix the lane, or get the grant extended." >&2
        emit refused
        exit 1
      fi
    fi
    command -v git >/dev/null 2>&1 || { echo "FLOW_WAVE_LANE_CHECK=unknown"; echo "flow-wave-registry: UNKNOWN - git is absent, so nothing was compared." >&2; emit error; exit 2; }
    git rev-parse --verify "$BASE_REF" >/dev/null 2>&1 || { echo "FLOW_WAVE_LANE_CHECK=unknown"; echo "flow-wave-registry: UNKNOWN - base ref '$BASE_REF' does not resolve." >&2; emit error; exit 2; }

    #: THE BASE IS THE MERGE BASE, not the base ref (#985).
    #:
    #: `git diff origin/main` compares the working tree to the CURRENT TIP, so a
    #: branch that is merely behind main reports every neighbour's merged file as
    #: this worker's change. That is the ordinary state of every branch between a
    #: sibling merge and a rebase, so the gate would fire constantly on waves
    #: where nothing is wrong - the cry-wolf this repo keeps filing.
    #:
    #: The merge base removes that false positive AND KEEPS THE REAL ONE.
    #: Measured on both mechanisms: behind-main gives `mine.sh` alone against the
    #: merge base and `mine.sh theirs.md` against the tip, while a soft-reset
    #: stale payload gives `mine.sh theirs.md` against BOTH - because there the
    #: merge base IS origin/main. The defect survives the correction; the noise
    #: does not.
    MERGE_BASE="$(git merge-base HEAD "$BASE_REF" 2>/dev/null)"
    [ -n "$MERGE_BASE" ] || { echo "FLOW_WAVE_LANE_CHECK=unknown"; echo "flow-wave-registry: UNKNOWN - no merge base between HEAD and '$BASE_REF'; nothing was compared." >&2; emit error; exit 2; }

    #: -z, and the exit status CHECKED. A failed diff printing nothing is
    #: indistinguishable from a clean tree, and this gate exists to refuse exactly
    #: that equivalence. `--no-renames` because `--name-only` reports only a
    #: rename's DESTINATION: moving an unclaimed file onto a claimed path would
    #: otherwise pass while deleting somebody else's file.
    #: Via a FILE, not command substitution: `$(...)` strips NUL bytes, so a
    #: `-z` list collapses into one concatenated string and every path but the
    #: first disappears. Caught by the count - the gate reported 1 touched file
    #: for a diff of ten - which is why the denominator is worth printing.
    TOUCHED_TMP="${TMPDIR:-/tmp}/flow-lane.$$"
    UNTRACKED_TMP="${TMPDIR:-/tmp}/flow-lane-untracked.$$"
    # CHAINED, NOT REPLACED (issue #1031): a bare `trap ... EXIT` here would
    # silently discard the FLOW_WAVE_EXIT= line installed at the top of this file,
    # and nothing would report its absence. $? is captured FIRST, before the
    # cleanup runs, or the reported status becomes `rm`'s.
    trap '_rc=$?; rm -f "$TOUCHED_TMP" "$UNTRACKED_TMP"; printf "FLOW_WAVE_EXIT=%d\n" "$_rc" >&2' EXIT
    trap 'rm -f "$TOUCHED_TMP" "$UNTRACKED_TMP"' INT TERM
    if ! git diff -z --no-renames --name-only "$MERGE_BASE" > "$TOUCHED_TMP" 2>/dev/null; then
      echo "FLOW_WAVE_LANE_CHECK=unknown"
      echo "flow-wave-registry: UNKNOWN - git diff failed against '$MERGE_BASE'; TOUCHED=0 here would be a failed observation, not a clean one." >&2
      emit error; exit 2
    fi
    EXTRA=""; EXTRA_N=0; TOUCHED_N=0; TOUCHED_ARR=()
    #: NUL ALL THE WAY TO THE READER. Command substitution strips NUL, which is
    #: why the enumeration goes to a temp file at all - but converting those NULs
    #: back to newlines to read them hands the splitting straight back to any
    #: filename CONTAINING a newline. One out-of-lane path named `a.sh\nb.md`
    #: then splits into two paths that can BOTH be in the lane, and the gate
    #: reports ok on the exact payload it exists to refuse (Codex pass 2, #985).
    while IFS= read -r -d '' f; do
      [ -n "$f" ] || continue
      TOUCHED_N=$((TOUCHED_N + 1))
      TOUCHED_ARR+=("$f")
      lane_covers "$f" "$LANE" || { EXTRA="$EXTRA
    $f"; EXTRA_N=$((EXTRA_N + 1)); }
    done < "$TOUCHED_TMP"

    #: WHAT THIS GATE STRUCTURALLY CANNOT SEE (CLAUDE.md detector contract).
    #: `git diff` observes TRACKED paths only, so an untracked file is invisible
    #: to every branch above. That is the CORRECT scope - an untracked file is
    #: not part of what a push delivers, so grading it would refuse work that
    #: cannot reach anybody - but a bare `TOUCHED=0 ... ok` cannot be told from
    #: "there was nothing to look at", and that is the reading that turns the
    #: ABSENCE of a warning into the PRESENCE of a check. So the population this
    #: verdict did NOT cover is reported beside it, as ungraded data.
    UNTRACKED_N=0
    if git ls-files -z --others --exclude-standard > "$UNTRACKED_TMP" 2>/dev/null; then
      while IFS= read -r -d '' f; do
        [ -n "$f" ] || continue
        UNTRACKED_N=$((UNTRACKED_N + 1))
      done < "$UNTRACKED_TMP"
    else
      UNTRACKED_N=unknown
    fi

    #: THE THIRD STATE (#985). Unclaimed, released and over-claimed all render as
    #: "clean", so the roster reports the ABSENCE of a warning and a reader takes
    #: it for the PRESENCE of a check. The two detectors see different things and
    #: neither subsumes the other:
    #:   - the CONTAINMENT check compares declarations against EACH OTHER. It
    #:     needs two claimants and fires at declaration time. It cannot see an
    #:     over-claim nobody has contended yet.
    #:   - THIS compares one declaration against one DIFF. It needs only one role,
    #:     fires at push time, and is the only thing that can see a path claimed
    #:     but never touched when no other role has declared it - a collision that
    #:     has not happened yet.
    #: A live over-claim in this wave was invisible to both: too wide for the diff
    #: check to have run on, and invisible to exact-match.
    #:
    #: DELIBERATELY NOT GRADED. An unused lane entry is common and usually
    #: innocent - a worker may hold a file it did not need this run - so a report
    #: that always has content gets read as noise and then not read at all. It is
    #: emitted as DATA, and the rare actionable subset is named separately:
    #: declared-but-untouched AND also claimed by another live role. That pair is
    #: what silently takes someone else's file.
    UNUSED=""; UNUSED_N=0; CONTESTED=""; CONTESTED_N=0
    LANE_ARR=(); lane_split LANE_ARR "$LANE"
    for _le in ${LANE_ARR[@]+"${LANE_ARR[@]}"}; do
      [ -n "$_le" ] || continue
      _hit=0
      for f in ${TOUCHED_ARR[@]+"${TOUCHED_ARR[@]}"}; do
        lane_covers "$f" "$_le" && { _hit=1; break; }
      done
      if [ "$_hit" -eq 0 ]; then
        UNUSED="$UNUSED $_le"; UNUSED_N=$((UNUSED_N + 1))
        _myrepo="$(printf '%s' "$CUR" | jq -r '.repo // ""')"
        for _other in $(printf '%s' "$REG" | jq -r --arg w "$WAVE" --arg me "$ROLE" \
              '(.[$w].roles // {}) | to_entries[] | select(.key != $me and (.value.released != true)) | .key' 2>/dev/null); do
          _oe="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$_other" '.[$w].roles[$r]')"
          #: LIVE and SAME REPO, or the finding asserts something it did not check.
          #: A dead-but-unreleased role, or one working in another repository,
          #: is not contending for this path.
          [ "$(liveness_of "$_oe")" = "live" ] || continue
          [ "$(printf '%s' "$_oe" | jq -r '.repo // ""')" = "$_myrepo" ] || continue
          _ol="$(printf '%s' "$_oe" | jq -r '.files // ""')"
          [ -n "$_ol" ] || continue
          #: SYMMETRIC. Asking only "does their lane cover mine" misses the
          #: broad-directory over-claim this feature exists for: an untouched
          #: `codex/skills` is not covered BY `codex/skills/x/y.md`, but it
          #: certainly contends with it.
          if lane_covers "$_le" "$_ol" || lane_covers "${_le%/}" "$_ol" || _lane_contains_any "$_le" "$_ol"; then
            CONTESTED="$CONTESTED $_le($_other)"; CONTESTED_N=$((CONTESTED_N + 1)); break
          fi
        done
      fi
    done

    echo "FLOW_WAVE_LANE_BASE=$BASE_REF"
    echo "FLOW_WAVE_LANE_UNGRANTED=$LANE_UNGRANTED_N"
    echo "FLOW_WAVE_LANE_UNCLAIMED=$LANE_UNCLAIMED_N"
    echo "FLOW_WAVE_LANE_TOUCHED=$TOUCHED_N"
    echo "FLOW_WAVE_LANE_UNTRACKED=$UNTRACKED_N"
    echo "FLOW_WAVE_LANE_EXTRA=$EXTRA_N"
    echo "FLOW_WAVE_LANE_UNUSED=$UNUSED_N"
    echo "FLOW_WAVE_LANE_CONTESTED=$CONTESTED_N"
    [ "$UNUSED_N" -gt 0 ] && echo "flow-wave-registry: declared but not touched by this diff (data, not a finding):$UNUSED"
    if [ "$CONTESTED_N" -gt 0 ]; then
      echo "flow-wave-registry: OVER-CLAIM - declared, untouched, and claimed by another LIVE role:$CONTESTED" >&2
      echo "flow-wave-registry: that pair is how a lane silently takes a file somebody else is working in." >&2
    fi
    if [ "$EXTRA_N" -gt 0 ]; then
      echo "FLOW_WAVE_LANE_CHECK=extra"
      echo "flow-wave-registry: $EXTRA_N path(s) in this diff are OUTSIDE the declared lane of '$ROLE':" >&2
      for f in $EXTRA; do echo "    $f" >&2; done
      echo "flow-wave-registry: a path you never claimed appearing in your own diff is the stale-payload signature." >&2
      echo "flow-wave-registry: verify the two changes are DISJOINT before repairing; if they overlap it is a real merge." >&2
      emit refused
      exit 1
    fi
    echo "FLOW_WAVE_LANE_CHECK=ok"
    echo "flow-wave-registry: ok - $TOUCHED_N path(s) touched, all inside the declared lane of '$ROLE'."
    emit listed
    exit 0
    ;;

  list)
    REG="$(read_registry)"
    ROLES_JQ_STATUS=0
    ROLES="$(printf '%s' "$REG" | jq -r --arg w "$WAVE" '(.[$w].roles // {}) | keys[]' 2>/dev/null)" || ROLES_JQ_STATUS=$?
    # --any-live (issue #1095): a purpose-built, cheap answer to "does this
    # WAVE have any live role left", for a poller that must ask it every few
    # seconds (flow-wave-mailbox.sh's `__supervise_daemon`). Deliberately
    # short-circuits BEFORE `load_mailbox` and the unregistered-claims
    # filesystem scan below - those exist to render a human-facing roster and
    # cost a cross-repo directory walk and a shell-out to a sibling script;
    # a daemon polling in a tight loop must not pay either on every cycle.
    #
    # THREE answers, not two, because "no live roles" has two different
    # causes that a shutdown decision must not conflate (orchestrator
    # review, #1095): a wave that had roles and they all ended is a
    # supervisor whose work is done; a wave that never had any roles at all
    # is one pointed at the wrong wave id, or a registry that failed to
    # record anything - a bug that would otherwise look exactly like
    # success in every log. `no-roles-ended` and `no-roles-registered` are
    # kept as two distinct words for exactly that reason - the same
    # discipline #1026's `claimed=unknown` vs `claimed=0` review applied to
    # the reconciler.
    #
    # `undeterminable` (never a shutdown signal) covers a registry file that
    # is readable but not valid JSON, so a corrupt file cannot be
    # misread as "genuinely empty" and drive a live wave's daemon to
    # self-terminate - only a version of "zero roles" that jq itself
    # affirmatively computed counts as `no-roles-registered`.
    if [ "$ANY_LIVE_ONLY" -eq 1 ]; then
      if [ "$ROLES_JQ_STATUS" -ne 0 ]; then
        echo "FLOW_WAVE_ANY_LIVE=undeterminable"
        exit 2
      fi
      for r in $ROLES; do
        e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
        if [ "$(liveness_of "$e")" = "live" ]; then
          echo "FLOW_WAVE_ANY_LIVE=yes"
          exit 0
        fi
      done
      if [ -z "$ROLES" ]; then
        echo "FLOW_WAVE_ANY_LIVE=no-roles-registered"
      else
        echo "FLOW_WAVE_ANY_LIVE=no-roles-ended"
      fi
      exit 1
    fi
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
    # Overlap that could not be COMPUTED is reported as UNKNOWN, never as clean
    # (#800). A live role with a declared lane and an empty repo drops out of the
    # same-issue and FILE-LANE arms silently - they compare same-repo pairs, and
    # an empty repo matches nothing - so without this the roster's silence about
    # that role reads exactly like a clean verdict.
    #
    # Counted HERE, above the --json branch, so EVERY render path reports it: an
    # instrument whose blind spot is visible in one output mode and invisible in
    # another is the same failure one level up. Unconditional per role rather
    # than gated on a second role existing to collide with - #674's do-not-alarm
    # rule is about warnings that fire on the NORMAL case, and register.md's own
    # canonical invocation passes --repo, so this shape is a defective
    # registration whether or not anyone is currently exposed by it.
    #
    # The `orchestrator` is skipped because the pairwise checks below exempt it
    # unconditionally - it holds no lane, so it has no scoping to lose.
    UNSCOPED=0
    UNSCOPED_ROLES=""
    # Roles whose LIVENESS could not be determined (#869). Counted here for the
    # same reason #800 counts unscoped lanes: an unknowable answer must never be
    # read as a clean one. Every `= "live"` consumer below correctly SKIPS an
    # `unknown` role - but skipping it means its lane is neither overlap-checked
    # nor counted as unchecked, so a roster would otherwise report a clean
    # verdict over a role nobody examined. This counter is that role's receipt.
    UNDETERMINED=0
    UNDETERMINED_ROLES=""
    # Roles running an UNDECLARED driver under a wave that declared one (#1026).
    # `policy set --driver` populates no role's `driver=` - it is inherited
    # doctrine, not a value - so a worker quietly running plain `flow:auto` under
    # a `codex:auto` wave produces a byte-identical roster row. The structurally
    # identical "declared at one level, missing at another" case already has a
    # counter (FLOW_WAVE_OVERLAP_UNSCOPED); this is its sibling.
    #
    # GATED ON THE WAVE HAVING DECLARED ONE, and the un-gated value is `-`, NOT
    # `0`. Two reasons, and the second is the load-bearing one:
    #   - register.md's canonical invocation does not pass --driver, so counting
    #     every driverless role would fire on the ordinary shape. A warning that
    #     fires on the normal case is the #674 defect this repo has paid for.
    #   - `0` would claim a measurement that was never taken. `-` says the
    #     question does not arise in this wave, which is a different fact from
    #     "asked, and nobody is missing one". A counter that silently matches
    #     nothing renders identically to a working one.
    # ...and the DENOMINATOR beside it (counter-model review, #1026). Under a
    # declared policy driver, an empty wave and a wave whose every live worker
    # declares one BOTH emit `0`, so the zero cannot say whether it inspected
    # anybody. That is this repo's own detector contract turned on the counter
    # it just added: a success message must not claim more than its input
    # population supports.
    # Computed HERE, above every render branch, for the same reason #800 counts
    # unscoped lanes above the `--json` split (counter-model review pass 2,
    # #1026): the empty-roster path returned before reaching the place these
    # were derived, so `list` on an empty wave omitted
    # FLOW_WAVE_MERGE_STRICT_SUPPRESSING while `list --json` on the SAME wave
    # emitted it. A contract line present in one render mode and absent in
    # another cannot be told from "not suppressing" by anything reading it.
    MERGE_STRICT="$(policy_field "$POL" merge_strict)"
    [ -n "$MERGE_STRICT" ] || MERGE_STRICT="unknown"
    MERGE_STRICT_STALE="$(merge_strict_stale "$POL")"
    MERGE_STRICT_SUPPRESSING="$(merge_strict_suppressing "$POL")"
    POL_DRIVER="$(policy_field "$POL" driver)"
    DRIVER_UNDECLARED="-"
    DRIVER_POPULATION="-"
    DRIVER_UNDECLARED_ROLES=""
    [ -n "$POL_DRIVER" ] && { DRIVER_UNDECLARED=0; DRIVER_POPULATION=0; }
    for r in $ROLES; do
      e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
      LV_R="$(liveness_of "$e")"
      if [ "$LV_R" = "unknown" ]; then
        UNDETERMINED=$((UNDETERMINED + 1))
        UNDETERMINED_ROLES="$UNDETERMINED_ROLES $r"
      fi
      [ "$LV_R" = "live" ] || continue
      [ "$r" = "orchestrator" ] && continue
      if [ -n "$POL_DRIVER" ]; then
        DRIVER_POPULATION=$((DRIVER_POPULATION + 1))
        if [ -z "$(printf '%s' "$e" | jq -r '.driver // ""')" ]; then
          DRIVER_UNDECLARED=$((DRIVER_UNDECLARED + 1))
          DRIVER_UNDECLARED_ROLES="$DRIVER_UNDECLARED_ROLES $r"
        fi
      fi
      lane_unscoped \
        "$(printf '%s' "$e" | jq -r '.repo // ""')" \
        "$(printf '%s' "$e" | jq -r '.files // ""')" \
        "$(printf '%s' "$e" | jq -r '.issue // ""')" || continue
      UNSCOPED=$((UNSCOPED + 1))
      UNSCOPED_ROLES="$UNSCOPED_ROLES $r"
    done
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
        # `dead` joins `absent`/`stale` here (#801): a heartbeat with no live
        # watcher behind it is the case that read `armed` and cost three
        # workers their wave. `unknown` counts too - an unassessable watch is
        # not an armed one, and rendering it as clean is this bug's whole
        # shape (the #800 convention).
        case "$ws" in
          absent|stale|dead|unknown)
            WATCH_UNARMED=$((WATCH_UNARMED + 1))
            case "$ws" in
              absent)  WATCH_DEAF="$WATCH_DEAF $r(never armed)" ;;
              dead)    WATCH_DEAF="$WATCH_DEAF $r(dead - last wake $(human_age "$(mailbox_watch_age "$r")") ago, 0 watchers)" ;;
              stale)   WATCH_DEAF="$WATCH_DEAF $r(stale $(human_age "$(mailbox_watch_age "$r")"))" ;;
              unknown) WATCH_DEAF="$WATCH_DEAF $r(UNKNOWN - watcher count unreadable)" ;;
            esac
            ;;
        esac
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
    CLAIM_SCAN_SKIPPED=0
    while IFS= read -r rp; do
      [ -z "$rp" ] && continue
      if [ ! -d "$rp" ]; then
        echo "flow-wave-registry: repo '$rp' does not resolve to a directory - unregistered claim scan is BLIND to it (#891)." >&2
        CLAIM_SCAN_SKIPPED=$((CLAIM_SCAN_SKIPPED + 1))
      fi
    done <<EOF
$SCAN_REPOS
EOF
    CLAIMS="$(collect_unregistered_claims "$REG" "$WAVE" "$SCAN_REPOS")"
    if [ "$JSON_OUT" -eq 1 ]; then
      # Enriched JSON: each entry plus computed liveness.
      OUT="{}"
      for r in $ROLES; do
        e="$(printf '%s' "$REG" | jq -c --arg w "$WAVE" --arg r "$r" '.[$w].roles[$r]')"
        lv="$(liveness_of "$e")"
        lb="$(liveness_basis_of "$e")"
        OUT="$(printf '%s' "$OUT" | jq -c --arg r "$r" --argjson e "$e" --arg lv "$lv" --arg lb "$lb" '.[$r] = ($e + {liveness: $lv, liveness_basis: $lb})')"
        # `watch` and `mailbox` are computed keys like `liveness`, and appear
        # ONLY when this wave actually uses the mailbox lane (#778) - so a wave
        # that never touched it emits byte-identical JSON to pre-#778, the same
        # promise #687's `unregistered_claims` and #699's `wave_policy` made.
        [ "$MAILBOX_IN_USE" -eq 1 ] || continue
        w_state="$(mailbox_watch_state "$r")"; w_age="$(mailbox_watch_age "$r")"
        w_watchers="$(mailbox_watch_watchers "$r")"
        r_state="$(mailbox_route_state "$r")"
        m_rev="$(mailbox_box_field "$r" rev)"; m_acked="$(mailbox_box_field "$r" acked)"
        m_unr="$(mailbox_box_field "$r" unread)"; m_mt="$(mailbox_box_field "$r" mtime)"
        nr=false; mailbox_never_read "$r" && nr=true
        OUT="$(printf '%s' "$OUT" | jq -c \
          --arg r "$r" --arg ws "$w_state" --arg wa "$w_age" --arg wc "$w_watchers" \
          --arg rs "$r_state" \
          --arg rev "$m_rev" --arg acked "$m_acked" --arg unr "$m_unr" --arg mt "$m_mt" \
          --argjson nr "$nr" '
            def num($v): if $v == "-" then null else ($v | tonumber? // null) end;
            .[$r] += {
              watch: {state: $ws, age_secs: num($wa), watchers: num($wc)},
              route: {state: $rs},
              mailbox: {rev: num($rev), acked: num($acked), unread: num($unr),
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
      starvation_scan "$REG" "$WAVE" "$ROLES"
      [ "$MERGE_STRICT_SUPPRESSING" = "yes" ] && STARVE_N=0
      OUT="$(printf '%s' "$OUT" | jq -c \
        --arg ms "$MERGE_STRICT" --argjson n "$STARVE_N" \
        --argjson obs "$STARVE_OBSERVED" --argjson live "$STARVE_LIVE" \
        --argjson min "$STARVE_MIN" \
        --arg stale "$MERGE_STRICT_STALE" --arg supp "$MERGE_STRICT_SUPPRESSING" \
        --arg age "$(merge_strict_age "$POL")" \
        '. + {merge_starvation: {merge_strict: $ms, merge_strict_age: $age, merge_strict_stale: $stale, suppressing: $supp, starving: $n, observed: $obs, live_roles: $live, threshold: $min}}')"
      printf '%s\n' "$OUT" | jq .
      # Keep --json stdout parseable: cross-wave notes go to stderr (#671).
      cross_wave_notes >&2
      emit_policy_lines "$POL"
      echo "FLOW_WAVE_MERGE_STRICT=$MERGE_STRICT"
      echo "FLOW_WAVE_MERGE_STRICT_SUPPRESSING=$MERGE_STRICT_SUPPRESSING"
      echo "FLOW_WAVE_STARVATION=$STARVE_N"
      echo "FLOW_WAVE_STARVATION_OBSERVED=$STARVE_OBSERVED"
      echo "FLOW_WAVE_STARVATION_LIVE=$STARVE_LIVE"
      echo "FLOW_WAVE_WATCH_UNARMED=$WATCH_UNARMED"
      echo "FLOW_WAVE_UNREAD=$UNREAD_TOTAL"
      echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
      echo "FLOW_WAVE_OVERLAP_UNSCOPED=$UNSCOPED"
      echo "FLOW_WAVE_DRIVER_UNDECLARED=$DRIVER_UNDECLARED"
      echo "FLOW_WAVE_DRIVER_POPULATION=$DRIVER_POPULATION"
      echo "FLOW_WAVE_LIVENESS_UNDETERMINED=$UNDETERMINED"
      echo "FLOW_WAVE_CLAIM_SCAN_SKIPPED=$CLAIM_SCAN_SKIPPED"
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
      echo "FLOW_WAVE_MERGE_STRICT=$MERGE_STRICT"
      echo "FLOW_WAVE_MERGE_STRICT_SUPPRESSING=$MERGE_STRICT_SUPPRESSING"
      echo "FLOW_WAVE_WATCH_UNARMED=$WATCH_UNARMED"
      echo "FLOW_WAVE_UNREAD=$UNREAD_TOTAL"
      echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
      echo "FLOW_WAVE_OVERLAP_UNSCOPED=$UNSCOPED"
      echo "FLOW_WAVE_DRIVER_UNDECLARED=$DRIVER_UNDECLARED"
      echo "FLOW_WAVE_DRIVER_POPULATION=$DRIVER_POPULATION"
      echo "FLOW_WAVE_LIVENESS_UNDETERMINED=$UNDETERMINED"
      echo "FLOW_WAVE_CLAIM_SCAN_SKIPPED=$CLAIM_SCAN_SKIPPED"
      echo "FLOW_WAVE: listed"
      exit 0
    fi
    #: Losing a base ONCE is ordinary: somebody merged while you were verifying.
    #: The ticket's own non-firing control is "no PR losing its base twice", so
    #: the signal starts at two. A starvation warning that fires on every wave is
    #: the defect this feature is about, one level up (#989).
    starvation_scan "$REG" "$WAVE" "$ROLES"
    # SUPPRESSION NEEDS A READING THAT IS STILL USABLE (#1026), not merely a
    # value that says `no`. A declared `no` whose observation has expired - or
    # was never stamped - leaves the signal ON, because the change that would
    # invalidate it (protection being TIGHTENED) is precisely the change that
    # makes starvation possible.
    [ "$MERGE_STRICT_SUPPRESSING" = "yes" ] && STARVE_N=0 && STARVED=""
    if [ "$MERGE_STRICT" = "no" ] && [ "$MERGE_STRICT_SUPPRESSING" != "yes" ]; then
      echo "flow-wave-registry: wave policy declares merge-strict=no, but that observation is $([ "$MERGE_STRICT_STALE" = "unknown" ] && echo "UNSTAMPED" || echo "older than ${MERGE_STRICT_TTL}s") - starvation detection is NOT suppressed (#1026)." >&2
      echo "  Branch protection is repo state anyone with admin can change, including from outside this wave, and this registry is offline by design - so the reading cannot be refreshed here." >&2
      echo "  Re-read protection and re-declare:  flow-wave-registry.sh policy set --wave '$WAVE' --merge-strict <yes|no|unknown>" >&2
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
      lb="$(liveness_basis_of "$e")"
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
      ov="$(printf '%s' "$e" | jq -r '.overtaken // 0')"
      pr_n="$(printf '%s' "$e" | jq -r '.pr // ""')"
      if [ -n "$pr_n" ]; then
        extra="$extra pr=#$pr_n"
        # The COUNT is data and is always shown once a PR is declared. The
        # SIGNAL is the threshold below, because one rebase is ordinary traffic
        # and a warning that fires on it is one nobody reads (#989).
        [ "$ov" != "0" ] && extra="$extra overtaken=$ov"
      fi
      # Driver + its capability fence (#783), rendered together so routing reads
      # as one fact. `worker-2 -> ... driver=gemma:auto[impl-only,no-web]` is the
      # whole feature: the mismatch is visible when the orchestrator ASSIGNS,
      # rather than when the worker reads its own fence and refuses. An
      # undeclared driver renders bare - the roster never invents a fence.
      dv="$(printf '%s' "$e" | jq -r '.driver // ""')"
      if [ -n "$dv" ]; then
        dvf="$(driver_cap "$dv" FENCE)"
        [ -n "$dvf" ] && extra="$extra driver=${dv}[${dvf}]" || extra="$extra driver=$dv"
      fi
      # Vantage and its routing consequence as one token (#959), rendered like
      # the driver fence directly above and for the same reason: the mismatch
      # must be visible when the orchestrator ASSIGNS, not when the worker's
      # message vanishes into a population with no fleet peer in it.
      #
      # `unknown` and `unavailable` are rendered too, deliberately. Every other
      # field here is shown only when declared, which is right for a grant - but
      # this is the field whose whole failure mode is a safe default absorbing
      # the third state until nobody remembers there was one. An entry from
      # before #959 has no stored value and renders nothing, so a pre-#959
      # roster is unchanged.
      vt="$(printf '%s' "$e" | jq -r '.vantage // ""')"
      vsrc="$(printf '%s' "$e" | jq -r '.vantage_source // ""')"
      [ -n "$vt" ] && extra="$extra vantage=$(vantage_annotation "$vt" "$vsrc")"
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
          armed)   extra="$extra watch=armed" ;;
          stale)   extra="$extra watch=stale($(human_age "$(mailbox_watch_age "$r")"))" ;;
          # DEAD is the #801 case: a fresh-looking heartbeat with nothing behind
          # it. The watcher count rides along so the row states the fact, not
          # just the verdict.
          dead)    extra="$extra watch=DEAD($(mailbox_watch_watchers "$r") watchers)" ;;
          absent)  extra="$extra watch=ABSENT" ;;
          unknown) extra="$extra watch=UNKNOWN" ;;
        esac
        # The route column (issue #814), a SIBLING of watch, never fused into
        # it: `watch=` answers "is a process polling" (#821-affected),
        # `route=` answers "has anything been acknowledged since" - ack
        # evidence, #821-immune by construction. UNCONFIRMED is the only
        # state worth a reader's eye at a glance, so it renders in caps like
        # the other alarms on this row; the quiet states render lowercase.
        rs="$(mailbox_route_state "$r")"
        case "$rs" in
          unconfirmed) extra="$extra route=UNCONFIRMED" ;;
          pending)     extra="$extra route=pending" ;;
          confirmed)   extra="$extra route=confirmed" ;;
        esac
        unr="$(mailbox_box_field "$r" unread)"
        if [ "$unr" != "-" ] && [ "$unr" -gt 0 ] 2>/dev/null; then
          extra="$extra unread=$unr"
          mt="$(mailbox_box_field "$r" mtime)"
          [ "$mt" != "-" ] && extra="$extra since=$mt"
        fi
        mailbox_never_read "$r" && extra="$extra ** NEVER READ **"
      fi
      # The basis is rendered ONLY for `unknown`, so a roster of ordinary live
      # and stale roles is byte-identical to pre-#869 - the same promise #778
      # and #699 made about their own additions. `unknown` is the one state a
      # reader cannot act on without knowing WHY it could not be decided.
      lvs="$lv"
      [ "$lv" = "unknown" ] && lvs="$lv:$lb"
      echo "  $r -> $sock [$lvs, $ver] issue=$iss$extra"
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
    # An overlap check that could not RUN is announced too (#800), on exactly the
    # #683 reasoning that produced the exemption notice above: a skipped check the
    # reader cannot see is a blind spot, not a quiet win. The two are announced
    # separately because they are not the same claim - #683 skips roles that
    # declared NOTHING to collide over, which is safe, while this names roles that
    # declared a lane and could not be compared, which is not. Folding the second
    # into the first would file a real gap under a reassuring heading.
    if [ -n "$UNSCOPED_ROLES" ]; then
      echo "  UNKNOWN: overlap NOT computed for live role(s) with a declared lane and NO repo:${UNSCOPED_ROLES}"
      echo "  The same-issue and FILE-LANE arms compare same-repo pairs, so an empty repo matches nothing - these roles are UNCHECKED, not clean."
      echo "  Each fixes it by re-registering with --repo <path>; --repo is rewritten by every re-register (--files is preserved), so it must be passed every time."
    fi
    [ "$UNSCOPED" -gt 0 ] && echo "flow-wave-registry: overlap detection is UNSCOPED for $UNSCOPED live role(s) - this roster CANNOT be read as clean (#800)." >&2
    # The wave declared a driver and these roles did not (#1026). Named on the
    # roster for the same reason the unscoped lanes above are: the wave-level
    # field is inherited DOCTRINE, not a value that lands in a role's entry, so
    # a worker running something else produces a byte-identical row and the
    # omission is visible nowhere.
    if [ -n "$DRIVER_UNDECLARED_ROLES" ]; then
      echo "  UNKNOWN: wave policy declares driver '$POL_DRIVER' but these live role(s) declare none:${DRIVER_UNDECLARED_ROLES}"
      echo "  A wave-level driver is inherited doctrine, not a stored per-role value, so nothing here says what these sessions are actually running."
      echo "  Each fixes it by re-registering with --driver <lifecycle command>; the capability fence (#783) is derived from it."
      echo "flow-wave-registry: $DRIVER_UNDECLARED live role(s) run an UNDECLARED driver under a wave that declared one (#1026)." >&2
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
      echo "  A 'dead' role armed a watch and it EXITED (a watch is one-shot); its heartbeat still looks recent, which is exactly what read 'armed' before #801 - do not take the age as evidence it is listening."
      echo "  Each arms it as a BACKGROUND call (step 4 of /flow:register):  flow-wave-mailbox.sh watch --role <role> --wave $WAVE"
    fi
    if [ -n "$NEVER_READ" ]; then
      echo "  UNREAD: role(s) that have consumed NOTHING from their box:${NEVER_READ}"
      echo "  An acked count of 0 against a delivered message (issue #815) is not a worker holding - it is a worker that has never acknowledged anything."
    fi
    if [ -n "$STARVED" ]; then
      echo "  STARVATION: PR(s) whose base moved $STARVE_MIN+ times with an unchanged diff:${STARVED}"
      echo "  Under branch protection strict:true every merge invalidates every other open PR, so a long-verifying PR"
      echo "  can be overtaken indefinitely while shorter ones merge past it. Each count is an observed base change"
      echo "  with no diff change - a lost queue position. What it cost is not measured here: this records the"
      echo "  observations it was given, not any verification run. merge-strict=$MERGE_STRICT stale=$MERGE_STRICT_STALE"
      echo "  ('unknown' means nobody has read branch protection, which is NOT the same as no protection; stale=yes or"
      echo "  stale=unknown means the reading has expired or was never stamped, so it no longer suppresses - #1026)."
    fi
    cross_wave_notes
    emit_policy_lines "$POL"
    echo "FLOW_WAVE_MERGE_STRICT=$MERGE_STRICT"
    #: WHAT ACTUALLY DECIDED THE ZERO (#1026). `FLOW_WAVE_MERGE_STRICT` reports
    #: the DECLARATION; this reports whether that declaration was still usable
    #: enough to switch the signal off. They differ exactly when a `no` has gone
    #: stale, which is the case worth seeing, and a consumer reading only the
    #: first one would take a live signal for a suppressed one.
    echo "FLOW_WAVE_MERGE_STRICT_SUPPRESSING=$MERGE_STRICT_SUPPRESSING"
    #: Reported as 0 under merge-strict=no, and that is a definition rather than
    #: a suppression: without `strict: true` losing your base does not cost you
    #: your place in the merge queue, so the observation is an ordinary rebase
    #: and not starvation at all. The human line and this key must agree, or a
    #: consumer acts on a number the roster declines to explain.
    echo "FLOW_WAVE_STARVATION=$STARVE_N"
    #: A zero must be readable: `0 of 0 observed` is "nothing to compare" and
    #: `0 of 5 observed` is "looked and found nothing" (#989). Without these the
    #: success value claims more than its input population supports.
    echo "FLOW_WAVE_STARVATION_OBSERVED=$STARVE_OBSERVED"
    echo "FLOW_WAVE_STARVATION_LIVE=$STARVE_LIVE"
    echo "FLOW_WAVE_WATCH_UNARMED=$WATCH_UNARMED"
    echo "FLOW_WAVE_UNREAD=$UNREAD_TOTAL"
    echo "FLOW_WAVE_BOOTSTRAP=$BOOTSTRAP_STATE"
    echo "FLOW_WAVE_OVERLAP_UNSCOPED=$UNSCOPED"
    echo "FLOW_WAVE_DRIVER_UNDECLARED=$DRIVER_UNDECLARED"
    echo "FLOW_WAVE_DRIVER_POPULATION=$DRIVER_POPULATION"
    echo "FLOW_WAVE_LIVENESS_UNDETERMINED=$UNDETERMINED"
    echo "FLOW_WAVE_CLAIM_SCAN_SKIPPED=$CLAIM_SCAN_SKIPPED"
    echo "FLOW_WAVE: listed"
    exit 0
    ;;
esac
