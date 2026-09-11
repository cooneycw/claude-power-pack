#!/usr/bin/env bash
# flow-wave-mailbox.sh - Host-local DELIVERY lane for multi-session flow waves
# (issue #676, the delivery half of the #638 registry and the #637 wave loop).
#
# Motivation: #638 and its follow-ups built a reliable ADDRESS BOOK - the
# orchestrator can name a worker, prove the address is transport-observed, and
# refuse to guess. None of that delivers anything. In the 2026-08-11 wave the
# harness rejected every orchestrator->worker `SendMessage` (it routes only to
# subagents the calling session spawned), so a fully-written assignment sat
# undelivered for ~2h while both sessions correctly stood by, and the ONLY
# transport that ever moved a message was the user typing a pointer into the
# worker's terminal by hand.
#
# This helper is the post office. It is deliberately a SIBLING of the registry
# rather than a verb on it: same lifetime, same host-local scope, same wave
# namespace, but the registry answers "who and where" while this answers "did it
# arrive".
#
#   $XDG_RUNTIME_DIR/cc-flow-wave/<wave>/
#     outbox-<role>.md   messages TO worker <role>       (orchestrator writes)
#     inbox-<role>.md    messages FROM worker <role>     (that worker writes)
#     .cursor-<box>      last rev the box's reader consumed
#     .watch-<role>      heartbeat: epoch of that role's last watch poll (#778)
#     .mailbox.lock      flock for every read-modify-write
#
# One file per WRITER in each direction, so two workers reporting at once never
# contend, and each box has exactly ONE designated reader (its own outbox for a
# worker; every inbox-*.md for the orchestrator) - which is what lets the read
# cursor be keyed by box alone.
#
# A MAILBOX IS NOT A LANE UNTIL SOMETHING READS IT. An idle session polls
# nothing, which is why the live wave's ad-hoc mailbox still needed a human to
# say "go read your outbox". `watch` is the other half: it BLOCKS until mail
# arrives past the cursor and then exits, so a session that launches it as a
# background call is re-invoked by the harness the moment it returns. Arming the
# watch is part of the protocol (see register.md / wave.md), not an option.
#
# Delivery is APPEND-first (gate ruling on #676, a deliberate deviation from the
# issue's "rewrite-in-place"): each send adds a rev-stamped block rather than
# overwriting the box. Rewrite-in-place means an orchestrator that sends an
# assignment and then a verdict before the worker wakes silently destroys the
# assignment - the exact delivery-loss failure this helper exists to remove. The
# cost is unbounded growth in a directory the OS wipes at reboot, which is the
# cheaper failure. `--replace` is available for the "this box holds current
# state, not a log" case and still bumps the rev, so a replace can never read as
# already-consumed.
#
# Usage:
#   flow-wave-mailbox.sh send  --to <role> [--from <role>] [--wave W]
#                              [--body TEXT | --body-file F | < stdin] [--replace]
#   flow-wave-mailbox.sh read  --role <role> [--wave W] [--all] [--peek]
#                              [--from <role>] [--out FILE]
#   flow-wave-mailbox.sh watch --role <role> [--wave W] [--timeout SEC]
#                              [--interval SEC] (--peek | --consume)
#   flow-wave-mailbox.sh watch --status --role <role> [--wave W]
#   flow-wave-mailbox.sh ack   --role <role> [--wave W] [--from <role> | --box NAME]
#                              (--revs R[,R...] | --all-unacked)
#   flow-wave-mailbox.sh supervise --role <role> [--wave W] [--timeout SEC]
#                              [--interval SEC]
#   flow-wave-mailbox.sh list  [--wave W] [--json]
#
#   send   Deliver a message. `--to orchestrator` writes inbox-<from>.md and
#          REQUIRES --from (the writer names its own box); any other --to writes
#          outbox-<to>.md and --from defaults to 'orchestrator'. Body comes from
#          --body, --body-file, or stdin. Rev is per-box, monotonic, assigned
#          under flock.
#   read   Print every message addressed to <role> that is not yet ACKNOWLEDGED
#          (issue #815 - see ACKNOWLEDGEMENT below), regardless of whether it was
#          shown before. --all additionally re-prints already-acknowledged
#          history. --peek prints without acknowledging anything (so a watch
#          still fires, and the message is still there on the NEXT read if this
#          one is lost). Without --peek, `read` acknowledges every message it
#          prints as part of the same call - the pre-#815 convenience, kept as a
#          named legacy mode, not the safe default: pair --peek with an explicit
#          `ack` once you have confirmed you actually have the content, for
#          anything a dropped response must not silently lose.
#          `--from <role>` (orchestrator only) narrows to one correspondent's
#          inbox instead of draining all of them (#792 item 7). A CONSUMING
#          orchestrator-wide read (no --from, no --peek) run non-interactively
#          refuses without `--out FILE` - a durable copy taken BEFORE
#          acknowledging anything - because piping that output through a
#          filter has silently destroyed message content before (#792); the
#          write happens before the acknowledgement so a failed write leaves
#          every message unacknowledged (#815), never the reverse.
#   watch  BLOCK until <role> has unread (unacknowledged) mail, print it, exit
#          0. Exit 5 on timeout. THIS IS THE WAKE - launch it as a background
#          call and the harness re-invokes the session when it exits. Bounded
#          by default (30m) so a wave can never leave watchers spinning after
#          it ends. STAMPS A HEARTBEAT (#778) - see below. REQUIRES an
#          explicit `--peek` or `--consume` (#792 item 1): a bare `watch` used
#          to consume-by-default, which silently marked mail read the caller
#          never saw when many messages were already waiting. There is no
#          default now - the caller must say which it means, and (#815)
#          neither ever risks losing mail to a dropped response: `--peek`
#          acknowledges nothing (call `ack` once you truly have it), and
#          `--consume` is the same named legacy convenience `read` offers. If
#          a watch fires on its very first poll - mail was already unread the
#          moment it armed, not a fresh wake - it prints a `flow-wave-mailbox:
#          NOTE -` line ahead of the message body saying so. Refuses to start
#          (exit 4, `duplicate`) when a live watcher already holds the same
#          role in the same wave (#792 item 4) - a role is single-owner, so a
#          second watcher is always a mistake, competing for the same mail
#          rather than receiving a copy of it. `watch --status` reports the
#          FUSED watch state (#801 - see STATE below), the raw heartbeat age,
#          the live watcher count and a `re-armed: yes/no` verdict instead of
#          a bare, undiagnosable zero (#792 item 3), using the self-excluding,
#          PID-based watcher count that replaces the old `pgrep -cf`
#          (#792 item 5 - see COUNTING below).
#   ack    Explicit receipt (issue #815). Record that <role> has genuinely
#          received specific messages, by REV - the identity printed in each
#          message's `<!-- cc-flow-wave-msg rev=N ... -->` marker - so an ack
#          binds to exactly what was received rather than a blanket "up to
#          here" watermark that could claim an unseen gap. `--revs 3,5` acks
#          those two revs and leaves 4 (never received, or received but not
#          yet confirmed) unread; out-of-order and partial-batch receipt are
#          both safe this way. `--all-unacked` acks every currently-unread rev
#          in the target box(es) as a convenience after a `--peek`. Refuses
#          (exit 2) a rev that does not exist yet in the box - acknowledging a
#          message you could not have received is refused, not accepted and
#          ignored. Idempotent: re-acking an already-acked rev is a no-op.
#          Acknowledging is a receipt, nothing more - it is not task
#          completion and answering a later message must never be inferred
#          from it alone. A worker's target box is implicit (its own outbox);
#          the orchestrator must disambiguate with `--from <role>` or
#          `--box NAME` for `--revs`, or may span every inbox at once with
#          `--all-unacked` alone.
#   supervise (issue #814) Own a re-arm LOOP for <role> so nothing conversational
#          has to remember to re-arm `watch` after every wake. The invocation
#          itself returns promptly with a `FLOW_MAILBOX: supervising` verdict
#          (or `duplicate`, exit 4, if one already runs); the DAEMON it detaches
#          is what persists, repeatedly arming `watch --consume` for <role>
#          until role release or the wave ends. See SUPERVISION below for what
#          this does and, as importantly, does not promise.
#   list   Box inventory for the wave: box, reader, rev, acked, unread, mtime,
#          plus the WATCH state, live WATCHERS count, and ROUTE readiness
#          (#814 - see ROUTE READINESS below) of every role known to read here
#          (#778, #801). `acked` is the count of revs that role has explicitly
#          acknowledged in that box (#815) - `rev` is what was SENT, `unread`
#          is what remains UNACKNOWLEDGED, and neither implies the other was
#          ever surfaced to the recipient.
#
# Acknowledgement (issue #815). `read`/`watch` used to advance a read cursor
# as a side effect of PRINTING output - the instant a message was shown, it
# was unrecoverable through normal delivery, whether or not the caller ever
# actually saw that output. A dropped tool response, a truncated batch, or a
# `--out` destination that failed to write all silently and permanently lost
# the message: the next ordinary read reported empty while the caller had
# never received anything. Surfacing and receiving are different events and
# must not share one state transition.
#
# `.ack-<box>` (parallel to the retired `.cursor-<box>`) now holds the set of
# revs that role has explicitly acknowledged - not a watermark, an actual set,
# so acknowledging rev 7 out of a batch that also delivered 5 and 6 leaves 5
# and 6 genuinely unread rather than silently implying them. `read --peek` and
# `watch --peek` print without touching this set at all: a dropped response
# after a peek leaves the message exactly as unread as if it had never been
# shown, recoverable by the very next `read`/`peek`/`watch`. The durable
# receipt is the explicit `ack` verb, called only once the caller has
# genuinely confirmed it holds the content - a step no script can perform on
# the caller's behalf, because the caller's receipt of the TOOL OUTPUT is
# exactly the event that can be dropped.
#
# `read` (bare) and `watch --consume` keep printing-acknowledges-immediately
# as a NAMED legacy convenience (issue #815's "explicit legacy consuming mode
# may remain"), unchanged from the pre-#815 behavior and carrying the same
# best-effort caveat it always silently had: fine for routine traffic, not the
# path to reach for when a dropped response must not lose an assignment or a
# verdict. Prefer `--peek` + a later `ack` for anything that matters.
#
# Migration: wave directories are ephemeral ($XDG_RUNTIME_DIR, wiped at
# reboot - see WAVE_ROOT below), so there is no cross-boot state to migrate.
# Within one boot, a wave dir touched before this fix simply has no
# `.ack-<box>` file yet; its absence means "nothing acknowledged", never
# "everything up to the old cursor was acknowledged" - the safe direction,
# recoverable mail rather than silently-declared-received mail. A caller
# who has already durably processed such a backlog by other means can
# `ack --all-unacked` once to close the gap explicitly, which is the
# "compatible migration... without silently declaring historical mail
# acknowledged" this issue asks for: an action the caller takes on purpose,
# never one this script infers.
#
# Supervision (issue #814). `watch` delivers ONE message (or a timeout) and
# exits - it was always meant to, so the harness has something to notify on
# (see the module docstring's "MAILBOX IS NOT A LANE" note). That means every
# wake needs a NEW `watch` armed by whoever is listening, and "whoever" was
# always the conversational agent, which is exactly the failure: a forgotten
# re-arm leaves assignments waiting indefinitely with nothing watching for
# them, and the session that forgot is the one that would have to notice.
# Observed three times in ~90 minutes building #814 and #815 themselves - see
# the incident comment on issue #815 - including a 25-minute deafness caught
# only because a DIFFERENT session noticed the silence from outside.
#
# `supervise` makes "a watcher process for this role exists" independent of
# any agent remembering anything, by moving the re-arm loop into a DETACHED
# DAEMON rather than a conversational habit. It is deliberately NOT
# `while true; do watch ...; done` run as the backgrounded call itself - that
# command never exits, so the harness would have nothing to notify on and the
# one mechanism this whole lane depends on would be defeated. Instead the
# `supervise` INVOCATION forks a daemon and returns immediately with its own
# verdict line, like every other verb; the daemon repeatedly shells out to
# `watch --role <role> --wave <wave> --consume`, letting EACH inner watch
# still exit and still be the harness's notification trigger for whichever
# session is separately listening for it - `supervise` guarantees a listener
# always EXISTS, it is not a replacement for arming one.
#
# Single ownership without inheriting #821. The obvious guard - record the
# daemon's PID, check it with `kill -0` - reintroduces #821 one layer up:
# PIDs are reused by the kernel, so a dead daemon's PID recycled to an
# unrelated process makes `kill -0` report "alive", a second `supervise`
# refuses as a duplicate, and the role goes deaf - #814's own failure,
# produced by #814's own guard, the identical shape as #821's argv-collision
# (an identity check that distinguishes "a process" from "no process" but not
# "MY process" from "some process"). `supervise` instead holds an exclusive,
# NON-BLOCKING `flock` on `.supervise-<role>.lock` for the daemon's entire
# life: the kernel releases a flock the instant the holding process dies, by
# construction, so "the lock is free" and "the previous holder is dead" are
# the SAME fact with no separate liveness check, no stale state, and no
# reclaim logic to get wrong. `.supervise-<role>.pid` still records the PID,
# but only for a human to read "who holds this" - never as the test for
# whether to proceed.
#
# Shutdown and the tight-loop guard. The daemon polls the sibling
# `flow-wave-registry.sh get <role> --wave <wave>` and exits cleanly -
# releasing the flock - the moment that role's `FLOW_WAVE_LIVENESS` reads
# `released`. Fails OPEN, TWICE over: if the registry sibling is unavailable
# at all (a supervisor that cannot check for release is not worse than none,
# it just keeps supervising), and if the role was simply never registered
# (`get`'s `free` verdict) - the registry is a separate, optional companion
# system, not a dependency of the mailbox lane (#814's own stated boundary),
# so `supervise` used standalone without ever registering must not shut
# itself down on its very first loop check. Only the positive, unambiguous
# `released` state - set once `release` has actually run against a role that
# WAS registered - triggers shutdown. Role/wave names are validated ONCE at
# daemon start, not re-checked every loop iteration, so a bad argument is a
# clean, immediate failure rather than a restart storm. A crash of the
# inner `watch` child for any reason OTHER than a clean delivery (exit 0) or
# timeout (exit 5) gets exponential backoff before the next re-arm, capped, so
# a persistently failing cause (a missing dependency, a corrupted box) cannot
# spin the daemon at full speed forever. `.supervise-<role>.log` records only
# structured, sanitized evidence - timestamp, event kind, exit code/signal -
# NEVER message bodies, which stay exactly where the mailbox already keeps
# them with their own access boundary; the inner `watch` child's stdout
# (which DOES carry bodies on delivery) is discarded by the daemon, not
# relayed anywhere new, because the daemon's job is re-arming, not reading.
#
# What this does not, and cannot, promise. No script here can make the
# HARNESS re-invoke a specific agent's conversation on a background process's
# completion - that wiring belongs to the harness, not to anything in this
# repo. `supervise` guarantees a listener keeps existing; it cannot guarantee
# the agent behind it is told. See ROUTE READINESS below for the honest
# alternative to promising that: making a silent failure of THAT link
# observable, with a bound, instead of claiming to have fixed it.
#
# Route readiness (issue #814). "Is a watcher process polling" (#801's fused
# state, and #814's `supervise`) answers a DIFFERENT question from "has
# anything actually been received" - and #821 already proved the first
# cannot be trusted as a proxy for the second: an orphaned command-substitution
# subshell of a dead watcher has exactly the right argv to look alive.
# `route_state()` answers the second question instead, from evidence #815
# already made possible: an explicit acknowledgement, bound to an identity,
# that only happens when something genuinely received a message. It is
# FOUR states, not three - the third being the trap:
#
#   confirmed    an ack was recorded since the last message was surfaced -
#                POSITIVE evidence the route works
#   pending      an unacked message exists, younger than the readiness bound -
#                no verdict yet; a busy recipient is not a broken route
#   unconfirmed  an unacked message exists, OLDER than the bound - the alarm
#   unknown      no messages at all, or the box could not be read - NOTHING
#                to check, and therefore NEVER `confirmed`
#
# The `unknown` / `confirmed` split is the whole point: an empty box is not
# evidence the route works, only evidence nothing has tested it, and
# reporting `confirmed` for a box nobody has ever sent to would be exactly the
# "reports success by checking nothing" defect found the same day in #816's
# tripwire, #821's counter and #828's helper loop. `pending` similarly must
# not collapse into `unconfirmed`'s alarm OR `confirmed`'s all-clear - it is
# its own fact, "being exercised, no answer yet".
#
# T, the readiness clock, is each message's own `ts=` from its send marker
# (#676) - not a new "first surfaced" timestamp this script would otherwise
# have to persist. This slightly OVERSTATES the unconfirmed window for a
# message nobody looked at until well after it was sent, and that is the
# deliberately conservative direction: it can only flag a route unconfirmed
# EARLIER than a stricter "time since first peek" clock would, never later,
# so it cannot hide a genuinely stuck route behind an unmeasured gap.
# `FLOW_WAVE_ROUTE_UNCONFIRMED_SECS` (default 900) is the bound - generous
# enough that ordinary handling time is never flagged (with #815, acking is a
# receipt, not task completion, so normal latency is seconds to a couple of
# minutes), short enough to answer "is this route working" rather than "is
# this wave abandoned"; a 25-minute real lapse building this issue would have
# tripped it at 15.
#
# Reported as its OWN `route` object in `list`, a SIBLING of `watch`, never
# merged into it - the #801 lesson enforced in the schema, not only the prose:
# `(state: armed); 0 live watcher process(es)` was one line contradicting
# itself because two different facts were fused with the reassuring one
# leading. `watch.state` still answers "is a process polling" and stays
# exactly as #821-affected as it always was; `route.state` answers "has
# anything been acknowledged since" and never touches the watcher count, so it
# carries none of that defect. A reader gets both facts and is not handed a
# verdict that already decided which one mattered. `flow-wave-registry.sh`'s
# existing mailbox join carries a matching `route` field for the same reason
# `acked` joined it in #815 - so this is visible from a roster sweep, not only
# from asking one mailbox directly.
#
# Counting watchers (issue #792 item 5). `pgrep -af 'flow-wave-mailbox.sh
# watch' | grep -- "--role X "` double-counts: a background launcher's
# `/bin/bash -c "<text>"` wrapper does not exec, so its argv is a SEPARATE
# live process whose one `-c` argument IS the inner command's text and
# therefore contains this same pattern too - one logical watcher, two OS
# processes, both matching. `count_watchers()` below reads each candidate's
# REAL argv from `/proc/<pid>/cmdline` and requires it to BE the script
# invocation (`argv[1]` the script path, `argv[2]` "watch") rather than
# CONTAIN it, which excludes a `-c` wrapper structurally. Self-exclusion
# walks the full ancestor chain, not one PID: this runs inside a `$(...)`
# subshell, and the subshell's own PARENT - the real, currently alive
# top-level process, legitimately blocked waiting on this very check -
# carries the identical argv under a different PID.
#
# A watcher launched from a since-removed worktree (#792 item 6). Some
# harnesses run a trailing `pwd -P` (or similar) after a background command
# to re-anchor the session's directory; if the watch was launched from a
# worktree that gets removed while it blocks, THAT trailing command fails
# with `getcwd: cannot access parent directories` and the wrapper reports
# exit 1 - AFTER this script already printed its mail and exited 0. That
# non-zero is the wrapper's, not this script's, and this script has no way to
# suppress a command that runs after it has already exited. The discriminator
# is in the captured output, not the exit code: `FLOW_MAILBOX: mail` (or any
# message body) present means delivered regardless of what runs after;
# a bare `pwd: error retrieving current directory` with NO prior output means
# genuinely lost. This generalizes to any monitor launched from a removed
# worktree, not just `watch` - treat output-then-pwd-error and
# pwd-error-alone as the two distinct cases they are.
#
# The watch heartbeat (issue #778). Arming the watch was the one element of
# participation that left NO trace: a worker could be live, address-verified and
# brief-current in the #638 roster and still be completely DEAF, because an
# unarmed watch looks identical to an armed one from outside. Observed in the
# `kyle-completion` wave on 2026-09-05 - a worker skipped step 4 of
# /flow:register, sat `[live, verified] brief=current` for over an hour, and its
# six-issue assignment was never read; the only tell was `CURSOR 0 / UNREAD 2`
# here, found by accident. So `watch` now stamps `.watch-<role>` in the wave dir
# with the current epoch, ON ARM AND ON EVERY POLL - not just on arm, because a
# watch that was KILLED must decay while one that is merely blocking stays
# fresh, and only a refreshing stamp separates those two.
#
# The heartbeat is deliberately NOT removed on exit: "died" and "never armed"
# are operationally different answers and erasing the file would flatten them
# back into one. `read` does not stamp - the heartbeat is about the WAKE, and a
# cursor that is advancing is separately visible in `list`.
#
# STATE: the heartbeat alone is not the answer (issue #801). A stamp is only as
# fresh as the last WAKE, and the watch is one-shot - it delivers one message
# and exits - so for the whole FLOW_WAVE_WATCH_STALE_SECS window after a watch
# fires and dies, a heartbeat-only reading says `armed` about a role that is
# deaf. That is not a hypothetical: on the `docker-list` wave (2026-09-07) a
# `--status` line read `(state: armed); 0 live watcher process(es)` - the two
# halves of one line contradicting each other - and the orchestrator broadcast
# "if it is still holding, do nothing" to three workers on the strength of the
# WORD. All three were deaf; one held a gate request unheard for ~50 minutes.
# An instrument whose failure looks identical to its success is worse than no
# instrument, so the state is now FUSED from both facts - the stamp says when it
# last lived, the process table says whether it lives NOW:
#
#   watchers  heartbeat        state
#   --------  ---------------  ------------------------------------------------
#   >0        within STALE     armed    listening right now
#   >0        older            stale    the process exists but has stopped
#                                       refreshing - hung, or SIGSTOPped. Deaf
#                                       in practice, but a different repair
#                                       from a process that is simply gone
#   0         any stamp        dead     armed at some point, exited, never
#                                       re-armed. The heartbeat AGE is still
#                                       reported, so "died just now" and "died
#                                       an hour ago" stay distinguishable - that
#                                       is what the stamp is for, and all it is
#                                       trustworthy for
#   0         no stamp         absent   NEVER armed. The unambiguous case
#   unknown   any              unknown  the host gave us no way to enumerate
#                                       processes at all - see COUNTING
#
# `unknown` is the #800 convention in this helper: an unknowable answer is never
# rendered as a clean one. Rounding an un-enumerable process table down to 0
# would report `dead` for healthy watches, which is this same bug wearing the
# opposite sign - it would drive re-arms that then collide with the live watcher
# the count could not see (exit 4, duplicate).
#
# The two consumers fail in DELIBERATELY OPPOSITE directions. The duplicate-arm
# guard (#792 item 4) treats `unknown` as 0 and lets the arm proceed, because a
# wave that cannot start because its duplicate guard is unavailable is worse
# than an occasional false duplicate. Reporting treats `unknown` as `unknown`
# and says so loudly, because that is the whole subject of this block.
#
# The lexicon gate (issue #701). `send` runs the message through
# `flow-wave-lexicon.sh validate` first, so a reserved TRANSITION token that does
# not parse - a gate verdict naming no issue, a conditional approval carrying no
# conditions, a merge authorisation whose predicate is "when CI passes", an
# unstamped state assertion - is refused at the SENDER, at send time, instead of
# being discovered by a reader an hour later. Two properties keep the gate from
# becoming the stall it exists to prevent: a message with NO reserved token is
# always deliverable (prose carries the argument - only a malformed PRESENT token
# refuses), and a missing or broken validator FAILS OPEN, because a wave that
# cannot deliver because its linter is unavailable is precisely the 2026-08-11
# failure this lane was built to remove. `--no-lexicon` is the per-send escape.
#
# Output ends with a machine-readable verdict line:
#   FLOW_MAILBOX: sent | read | empty | mail | timeout | listed | status |
#                 acked | duplicate | refused | error
# preceded by FLOW_MAILBOX_*= detail lines ('-' when not applicable). Message
# BODIES are printed before the detail block, so a caller can split on the first
# FLOW_MAILBOX_ line. `ack` additionally prints FLOW_MAILBOX_ACKED=<n>, the
# count of revs it just recorded as acknowledged (already-acked revs in the
# same call still count - the call is idempotent, not a no-op report of 0).
#
# Exit codes: 0 normal, 2 usage error - INCLUDING `ack` naming a rev that does
# not exist yet in the box (#815: acknowledging a message you could not have
# received is refused, not silently accepted) - 3 lock/IO failure, 4 duplicate
# watcher (#792 - a live watcher already holds this role+wave; nothing was
# started), 5 watch timeout, 6 lexicon refusal (#701 - the message was NOT
# delivered; nothing was written).
#
# `watch --status` detail lines:
#   FLOW_MAILBOX_WATCH_STATE    armed | stale | dead | absent | unknown - the
#                               FUSED verdict (#801), never the raw stamp
#   FLOW_MAILBOX_WATCH_AGE      seconds since the last heartbeat, or '-'. Still
#                               reported for every state, so "died just now" and
#                               "died an hour ago" stay distinguishable
#   FLOW_MAILBOX_WATCHER_COUNT  live watcher processes, or `unknown`
#   FLOW_MAILBOX_REARMED        yes | no | unknown
#
# `list --json` gains `watches[].watchers` (integer, or null when the process
# table could not be read) beside `state` and `age_secs`, so a consumer can
# check the fusion rather than take the state word on trust (#801). Each box
# entry's `cursor` key from before #815 is now `acked` - the count of revs
# that box's reader has explicitly acknowledged, replacing a read-cursor
# position that no longer exists (#815).
#
# Env:
#   FLOW_WAVE_WATCH_STALE_SECS  heartbeat age past which a REFRESHING watch is
#                               judged to have stopped refreshing (#778/#801,
#                               default 300). It no longer decides `armed` on
#                               its own - the live watcher count does.
# Env (test hooks - unset in normal use):
#   FLOW_WAVE_MAILBOX_DIR   wave-root override (most precise)
#   FLOW_WAVE_REGISTRY_DIR  shared wave-root override, honored so the mailbox
#                           and the #638 registry always co-locate
#   FLOW_WAVE_NOW           override "now" as epoch seconds, so heartbeat ages
#                           are deterministic (same hook name the registry uses)
#   FLOW_WAVE_WATCHER_SCAN  force the watcher-enumeration lane: `proc`, `ps`, or
#                           `none` (#801). `none` makes the count unreadable, so
#                           the `unknown` state is reachable on a host that has
#                           a perfectly good /proc; `ps` exercises the fallback,
#                           which is otherwise dead code everywhere the suite
#                           runs. Unset in normal use - the lane is auto-picked.

set -uo pipefail

UID_NUM="$(id -u)"
WAVE_ROOT="${FLOW_WAVE_MAILBOX_DIR:-${FLOW_WAVE_REGISTRY_DIR:-${XDG_RUNTIME_DIR:-/run/user/$UID_NUM}/cc-flow-wave}}"

WATCH_TIMEOUT_DEFAULT=1800
WATCH_INTERVAL_DEFAULT=3
# A watch refreshes its heartbeat every --interval (3s by default), so anything
# past this is either a dead watch or a session busy between wakes - deaf either
# way (#778). Generous enough that a worker handling a message is not routinely
# flagged, short enough that the roster answers "is it listening RIGHT NOW".
WATCH_STALE_SECS="${FLOW_WAVE_WATCH_STALE_SECS:-300}"
NOW="${FLOW_WAVE_NOW:-$(date +%s)}"

usage_fail() { echo "flow-wave-mailbox: $1" >&2; exit 2; }

# Emit the detail block + verdict. Unset args default to '-'.
emit() {
  echo "FLOW_MAILBOX_WAVE=${E_WAVE:--}"
  echo "FLOW_MAILBOX_ROLE=${E_ROLE:--}"
  echo "FLOW_MAILBOX_BOX=${E_BOX:--}"
  echo "FLOW_MAILBOX_REV=${E_REV:--}"
  echo "FLOW_MAILBOX_UNREAD=${E_UNREAD:--}"
  echo "FLOW_MAILBOX_ACKED=${E_ACKED:--}"
  echo "FLOW_MAILBOX_DIR=${E_DIR:--}"
  echo "FLOW_MAILBOX: $1"
}

# Role and wave names become path components, so they are validated rather than
# quoted-and-hoped: a name carrying '/' or '..' would address a box outside the
# wave dir entirely.
valid_name() {
  case "$1" in
    '') return 1 ;;
    .*) return 1 ;;
    *[!A-Za-z0-9_.-]*) return 1 ;;
    *) return 0 ;;
  esac
}

# Highest rev recorded in a box (0 for a missing or empty box). Parsed from the
# markers rather than counted, so a hand-edited box cannot make a later send
# reuse a rev a reader already consumed.
max_rev() {
  local f="$1"
  [ -s "$f" ] || { echo 0; return; }
  awk '
    /^<!-- cc-flow-wave-msg / {
      if (match($0, /rev=[0-9]+/)) {
        r = substr($0, RSTART + 4, RLENGTH - 4) + 0
        if (r > m) m = r
      }
    }
    END { print m + 0 }
  ' "$f"
}

# --- Acknowledgement (issue #815) ----------------------------------------------
# `.ack-<box>` holds the SET of revs that box's reader has explicitly
# acknowledged, one integer per line, sorted and deduped on every write. This
# replaces the retired `.cursor-<box>` read-cursor: a cursor advanced as a side
# effect of PRINTING output, which is precisely the defect #815 exists to fix -
# see the header comment above (ACKNOWLEDGEMENT) for the full argument.
ack_file() { echo "$WAVE_DIR/.ack-$(basename "$1")"; }

# Every rev NOT in <box>'s ack set, one per line, for revs that actually exist
# (1..max_rev present as markers) - so a message never sent is never listed as
# "unread" and a torn/missing ack file degrades to "nothing acknowledged" (the
# safe direction: recoverable, not silently-declared-received). Reads the ack
# file once via awk's own `getline`, not a shell loop, so this stays cheap for
# a box with hundreds of messages.
unacked_revs_in() {
  local f="$1" afile
  [ -s "$f" ] || return 0
  afile="$(ack_file "$f")"
  awk -v ackfile="$afile" '
    BEGIN {
      while ((getline line < ackfile) > 0) {
        if (line ~ /^[0-9]+$/) acked[line + 0] = 1
      }
      close(ackfile)
    }
    /^<!-- cc-flow-wave-msg / {
      if (match($0, /rev=[0-9]+/)) {
        r = substr($0, RSTART + 4, RLENGTH - 4) + 0
        if (!(r in acked)) print r
      }
    }
  ' "$f"
}

# Print the message blocks of a box whose rev is NOT yet acknowledged - the
# ack-based sibling of extract_since (which stays cursor/rev-based, used only
# by --all's "show literal full history" request, an orthogonal concept from
# acknowledgement).
extract_unacked() {
  local f="$1" afile
  [ -s "$f" ] || return 0
  afile="$(ack_file "$f")"
  awk -v ackfile="$afile" '
    BEGIN {
      while ((getline line < ackfile) > 0) {
        if (line ~ /^[0-9]+$/) acked[line + 0] = 1
      }
      close(ackfile)
    }
    /^<!-- cc-flow-wave-msg / {
      rev = 0
      if (match($0, /rev=[0-9]+/)) rev = substr($0, RSTART + 4, RLENGTH - 4) + 0
      show = !(rev in acked)
    }
    show { print }
  ' "$f"
}

# Count of revs <box>'s reader has ever explicitly acknowledged (for `list`'s
# ACKED column - #815). Distinct from "unread": acked + unread need not equal
# rev, because a rev can be neither shown nor acked yet at all.
acked_count() {
  local afile
  afile="$(ack_file "$1")"
  [ -s "$afile" ] || { echo 0; return; }
  grep -c '^[0-9]' "$afile" 2>/dev/null || echo 0
}

# Record REVS (space-separated, already validated non-empty positive integers)
# as acknowledged for <box>, under the same flock every other read-modify-write
# in this file uses. Refuses (return 2) any rev that does not exist in the box
# yet - "acknowledging a message you could not have received" - WITHOUT
# recording any of the batch, so a bad rev in a batch cannot partially commit.
# Idempotent: a rev already in the set is silently fine to re-list.
ack_add() {
  local box="$1"; shift
  local afile top rev bad=""
  afile="$(ack_file "$box")"
  top="$(max_rev "$box")"
  for rev in "$@"; do
    case "$rev" in
      ''|*[!0-9]*) bad="$bad $rev" ;;
      *) [ "$rev" -ge 1 ] && [ "$rev" -le "$top" ] || bad="$bad $rev" ;;
    esac
  done
  if [ -n "$bad" ]; then
    echo "flow-wave-mailbox: refusing to ack unseen/invalid rev(s):$bad in $(basename "$box") (it holds $top message(s))" >&2
    return 2
  fi
  [ "$#" -gt 0 ] || return 0
  (
    flock -w 10 9 || { echo "flow-wave-mailbox: could not lock $WAVE_DIR" >&2; exit 3; }
    tmp="$(mktemp "$WAVE_DIR/.mack.XXXXXX")" || exit 3
    {
      [ -s "$afile" ] && cat "$afile"
      for rev in "$@"; do echo "$rev"; done
    } | sort -un > "$tmp"
    mv -f "$tmp" "$afile" || { rm -f "$tmp"; exit 3; }
  ) 9>"$LOCK_FILE"
}

# Ack everything currently unacked in one box. Used by `ack --all-unacked`,
# by drain_role's own --consume path, and by `read --out` to defer
# acknowledgement until AFTER a successful destination write (#815) without
# duplicating the "what's unacked right now" computation at each call site.
ack_all_unacked_in() {
  local b="$1" revs
  revs="$(unacked_revs_in "$b")"
  [ -n "$revs" ] || return 0
  # shellcheck disable=SC2086
  ack_add "$b" $revs
}

# Same, across every box a role reads.
ack_all_unacked_for_role() {
  local role="$1" b
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    ack_all_unacked_in "$b"
  done <<EOF
$(boxes_for_role "$role")
EOF
}

# --- Route readiness (issue #814) ----------------------------------------------
# See the header's ROUTE READINESS section for the four-state contract and why
# an empty box must never read as `confirmed`.

# Send-time (`ts=`, issue #676) of the OLDEST unacked message in a box, or ''
# when there is none - either because the box is empty or because everything
# sent so far has been acknowledged. Deliberately reuses each message's own
# send timestamp rather than persisting a new "first surfaced" one - see the
# header for why that is the conservative direction, not a shortcut.
oldest_unacked_ts() {
  local f="$1" afile
  [ -s "$f" ] || return 0
  afile="$(ack_file "$f")"
  awk -v ackfile="$afile" '
    BEGIN {
      while ((getline line < ackfile) > 0) {
        if (line ~ /^[0-9]+$/) acked[line + 0] = 1
      }
      close(ackfile)
    }
    /^<!-- cc-flow-wave-msg / {
      rev = 0
      if (match($0, /rev=[0-9]+/)) rev = substr($0, RSTART + 4, RLENGTH - 4) + 0
      ts = ""
      if (match($0, /ts=[^ ]+/)) ts = substr($0, RSTART + 3, RLENGTH - 3)
      if (rev > 0 && !(rev in acked)) print rev, ts
    }
  ' "$f" | sort -n | head -1 | cut -d' ' -f2-
}

# route_state BOX -> confirmed | pending | unconfirmed | unknown (issue #814).
# The bound is env-overridable (`FLOW_WAVE_ROUTE_UNCONFIRMED_SECS`, default
# 900s - see the header for how that default was chosen) so it is testable
# without sleeping, matching how `FLOW_WAVE_WATCH_STALE_SECS` already works
# for the watch heartbeat.
route_state() {
  local box="$1" bound ts epoch age
  bound="${FLOW_WAVE_ROUTE_UNCONFIRMED_SECS:-900}"
  [ -s "$box" ] || { echo unknown; return; }
  ts="$(oldest_unacked_ts "$box")"
  if [ -z "$ts" ]; then
    # No unacked message. An empty box is NOT evidence the route works - it
    # is evidence nothing has tested it. Only a box that has actually sent
    # something, and had everything sent so far acknowledged, earns
    # `confirmed`.
    if [ "$(max_rev "$box")" -gt 0 ]; then echo confirmed; else echo unknown; fi
    return
  fi
  epoch="$(date -d "$ts" +%s 2>/dev/null)"
  if [ -z "$epoch" ]; then
    # A real, unacked message whose timestamp could not be parsed - cannot
    # verify freshness, so this does not get to claim a clean state either.
    echo unconfirmed
    return
  fi
  age=$((NOW - epoch))
  [ "$age" -lt 0 ] && age=0
  if [ "$age" -gt "$bound" ]; then echo unconfirmed; else echo pending; fi
}

# route_state_for_role ROLE -> the WORST route_state across every box that
# role reads (unconfirmed > pending > confirmed > unknown when a role reads
# more than one box, e.g. the orchestrator) - a reader deciding whether to
# trust a role's route needs the box that is failing, not the box that is
# not.
route_state_for_role() {
  local role="$1" b s worst=unknown
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    s="$(route_state "$b")"
    case "$s" in
      unconfirmed) worst=unconfirmed ;;
      pending) [ "$worst" != unconfirmed ] && worst=pending ;;
      confirmed) [ "$worst" != unconfirmed ] && [ "$worst" != pending ] && worst=confirmed ;;
    esac
  done <<EOF
$(boxes_for_role "$role")
EOF
  echo "$worst"
}

# --- The watch heartbeat (#778) ------------------------------------------------
# `.watch-<role>` holds one epoch integer, exactly the shape of `.ack-<box>`.
watch_file() { echo "$WAVE_DIR/.watch-$1"; }

# Stamp the current time for <role>. Called on arm and on every poll, so a
# KILLED watch decays while a blocking one stays fresh. Deliberately NOT under
# the mailbox flock: it is a single-writer, whole-file, last-write-wins stamp
# with no read-modify-write, and taking the lock 600 times over a 30m watch
# would make the wake path contend with every send for no correctness gain. A
# torn or unwritable stamp degrades to `unknown`, never to a wrong verdict.
watch_stamp() {
  local wf tmp now
  # Re-read the clock EVERY call rather than reusing the start-of-script $NOW:
  # a watch blocks for up to 30m, so a stamp frozen at arm time would age out
  # underneath a perfectly healthy watch and report exactly the false `stale`
  # this heartbeat exists to distinguish from a real one.
  now="${FLOW_WAVE_NOW:-$(date +%s)}"
  wf="$(watch_file "$1")"
  tmp="$(mktemp "$WAVE_DIR/.wstamp.XXXXXX" 2>/dev/null)" || return 0
  printf '%s\n' "$now" > "$tmp" 2>/dev/null && mv -f "$tmp" "$wf" 2>/dev/null || rm -f "$tmp"
  return 0
}

# Age in seconds of <role>'s heartbeat; '-' when there is none or it is
# unreadable. Clamped at 0: FLOW_WAVE_NOW and a real stamp can disagree, and a
# negative age would render as a nonsense future timestamp.
watch_age() {
  local wf v
  wf="$(watch_file "$1")"
  [ -s "$wf" ] || { echo '-'; return; }
  v="$(tr -dc '0-9' < "$wf" 2>/dev/null | head -c 20)"
  [ -n "$v" ] || { echo '-'; return; }
  local age=$((NOW - v))
  [ "$age" -lt 0 ] && age=0
  echo "$age"
}

# armed | stale | dead | absent | unknown for <role>, given that role's live
# watcher count (a non-negative integer, or `unknown`). See the STATE table in
# the header for why the heartbeat alone cannot answer this (#801).
#
# The count is a PARAMETER rather than something looked up here, so `list` can
# tally every role from ONE pass over the process table instead of re-walking
# /proc once per role.
watch_state_of() {
  local role="$1" count="$2" age
  age="$(watch_age "$role")"
  case "$count" in
    ''|*[!0-9]*)
      # Not a number - the process table could not be enumerated. Never round
      # this down to "nothing is listening" (#800/#801).
      echo unknown
      return
      ;;
  esac
  if [ "$count" -gt 0 ]; then
    # Something IS listening. The stamp then distinguishes a healthy watch from
    # a process that exists but has stopped refreshing it.
    if [ "$age" != "-" ] && [ "$age" -gt "$WATCH_STALE_SECS" ]; then
      echo stale
    else
      echo armed
    fi
  elif [ "$age" = "-" ]; then
    echo absent
  else
    echo dead
  fi
}

# The role that READS a box: its own outbox for a worker, every inbox for the
# orchestrator. The heartbeat is keyed by reader, so this is the join.
reader_of_box() {
  local b
  b="$(basename "$1")"
  case "$b" in
    outbox-*.md) echo "${b#outbox-}" | sed 's/\.md$//' ;;
    inbox-*.md)  echo orchestrator ;;
    *)           echo '-' ;;
  esac
}

# Every role this wave dir knows a watch state for: each box's reader, plus any
# role that stamped a heartbeat without a box (a worker that armed before the
# orchestrator sent it anything - the healthy order, and the one a box-only
# scan would miss).
watch_roles() {
  {
    find "$WAVE_DIR" -maxdepth 1 -type f \( -name 'outbox-*.md' -o -name 'inbox-*.md' \) 2>/dev/null |
      while IFS= read -r b; do [ -n "$b" ] && reader_of_box "$b"; done
    find "$WAVE_DIR" -maxdepth 1 -type f -name '.watch-*' 2>/dev/null |
      while IFS= read -r w; do [ -n "$w" ] && basename "$w" | sed 's/^\.watch-//'; done
  } | grep -v '^-$' | sort -u
}

# Count of messages in a box that are not yet acknowledged (issue #815 - was
# "newer than its read cursor" before the cursor's retirement; see
# unacked_revs_in for why this must be a set, not a watermark).
unread_in() {
  local f="$1"
  [ -s "$f" ] || { echo 0; return; }
  unacked_revs_in "$f" | grep -c '^[0-9]'
}

# Print the message blocks of a box with rev > MIN (-1 prints everything). A
# block runs from its marker to the next marker or EOF.
extract_since() {
  local f="$1" min="$2"
  [ -s "$f" ] || return 0
  awk -v min="$min" '
    /^<!-- cc-flow-wave-msg / {
      rev = 0
      if (match($0, /rev=[0-9]+/)) rev = substr($0, RSTART + 4, RLENGTH - 4) + 0
      show = (rev > min)
    }
    show { print }
  ' "$f"
}

# The boxes a role READS, one absolute path per line. The orchestrator reads
# every worker inbox; a worker reads only its own outbox.
boxes_for_role() {
  local role="$1"
  if [ "$role" = "orchestrator" ]; then
    find "$WAVE_DIR" -maxdepth 1 -type f -name 'inbox-*.md' 2>/dev/null | sort
  elif [ -f "$WAVE_DIR/outbox-$role.md" ]; then
    echo "$WAVE_DIR/outbox-$role.md"
  fi
  return 0
}

# Total unread across every box a role reads.
unread_for_role() {
  local total=0 b n
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    n="$(unread_in "$b")"
    total=$((total + n))
  done <<EOF
$(boxes_for_role "$1")
EOF
  echo "$total"
}

# Print every unacknowledged message for a role (issue #815) and, unless
# peeking, acknowledge exactly the revs just printed - the same NAMED legacy
# convenience `read`/`watch --consume` have always offered, now explicit and
# opt-in rather than the only option a cursor gave you. --all additionally
# shows the box's FULL history (including already-acked revs) via the
# rev-based extract_since, but never changes what gets acknowledged: `--all`
# is a display request, not a receipt.
#
# The rev list to ack is captured BEFORE printing/acking, from the same
# unacked_revs_in() pass extract_unacked() itself reads - so a message that
# arrives in the gap between "decide what's unacked" and "record the ack" is
# simply not in either, and stays unread for the next call. No lock spans the
# read+ack pair; ack_add() takes its own lock only for the write.
drain_role() {
  local role="$1" peek="$2" all="$3" b body revs
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    if [ "$all" -eq 1 ]; then
      body="$(extract_since "$b" -1)"
    else
      revs="$(unacked_revs_in "$b")"
      body="$(extract_unacked "$b")"
    fi
    if [ -n "$body" ]; then
      echo "=== $(basename "$b") ==="
      echo "$body"
    fi
    if [ "$peek" -eq 0 ] && [ "$all" -eq 0 ] && [ -n "$revs" ]; then
      # shellcheck disable=SC2086
      ack_add "$b" $revs
    fi
  done <<EOF
$(boxes_for_role "$role")
EOF
  return 0
}

# --- Watcher counting (#792 item 5) --------------------------------------------
# Count LIVE `watch --role <role> --wave <wave>` processes, excluding this
# process. A flattened-string match over `ps -eo args` - what `pgrep -f`
# does, and what a first draft of this fix also did - double-counts
# structurally, not just by accident: a background launcher's `/bin/bash -c
# "<text>"` wrapper does not exec, so its argv is a SEPARATE live process
# whose one `-c` argument IS the inner command's text, and that text
# contains this same pattern - one logical watcher, two OS processes, both
# matching. Verified empirically while building this fix: a single
# multi-line test harness command containing three unrelated
# `flow-wave-mailbox.sh watch --role 1 ...` substrings inflated the count to
# 2 for a role that had zero real watchers running.
#
# Reading each candidate's REAL argv - /proc/<pid>/cmdline, NUL-separated,
# no shell re-parsing involved - fixes this structurally instead of by
# pattern-excluding text that could just as easily appear in something
# legitimate: a `bash -c "<text>"` wrapper's argv is exactly three elements
# (`bash`, `-c`, `<text>`), so argv[1] is `-c`, never our script's path, and
# it is excluded on that ground alone.
# Every live watcher on <wave>, one ROLE per line (repeats when a role somehow
# has two). ONE pass over the process table, so `list` can tally all roles at
# once rather than re-walking /proc once per role (#801).
#
# Exit 1 means the process table could not be enumerated AT ALL - a genuinely
# unknown answer. Callers must not round that to zero: a zero that means
# "cannot tell" is precisely the clean-looking wrong answer this helper exists
# to stop reporting (#800/#801).
watcher_roles_live() {
  local wave="$1"
  case "${FLOW_WAVE_WATCHER_SCAN:-auto}" in
    # Test hook. `none` simulates a host where the process table cannot be read
    # at all, which is otherwise unreachable on any machine that runs the suite
    # - and an untested `unknown` lane would be the guard against confident
    # wrong answers being itself unverified. `ps` forces the fallback, which is
    # dead code on Linux and would otherwise ship unexercised.
    none) return 1 ;;
    ps)   watcher_roles_ps_fallback "$wave" ;;
    proc) watcher_roles_proc "$wave" ;;
    *)
      if [ -d /proc ]; then
        watcher_roles_proc "$wave"
      else
        watcher_roles_ps_fallback "$wave"
      fi
      ;;
  esac
}

# watcher_count ROLE WAVE -> a non-negative integer, or `unknown` when the host
# gives us no way to enumerate processes. The REPORTING view.
watcher_count() {
  local role="$1" wave="$2" roles n
  roles="$(watcher_roles_live "$wave")" || { echo unknown; return; }
  n="$(printf '%s\n' "$roles" | grep -cxF -- "$role")"
  echo "$((n))"
}

# count_watchers ROLE WAVE -> always an integer. The ARM-GUARD view: `unknown`
# fails OPEN to 0, because a wave that cannot start because its duplicate guard
# is unavailable is worse than an occasional false duplicate (#792 item 4).
# Reporting deliberately fails the other way - see watch_state_of.
count_watchers() {
  local n
  n="$(watcher_count "$1" "$2")"
  case "$n" in ''|*[!0-9]*) echo 0 ;; *) echo "$n" ;; esac
}

# The calling process's own ancestor chain: its subshell, up through every
# parent, back to PID 1. A single PID ($$ or $BASHPID alone) is not enough
# to exclude: the watcher scan runs inside a `$(...)` command substitution,
# which forks a subshell, and the subshell's PARENT - the real, currently
# alive top-level process, legitimately blocked waiting on this very check -
# carries the IDENTICAL argv under a DIFFERENT pid ($$ keeps reporting that
# parent's pid even from inside the subshell). A nested substitution could
# add further layers than that. Every ancestor is definitionally part of
# THIS invocation, never a second watcher, so the whole chain is excluded.
self_chain_proc() {
  local pid="$BASHPID" chain=" $BASHPID " ppid
  while [ -n "$pid" ] && [ "$pid" != "1" ]; do
    ppid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null)"
    [ -n "$ppid" ] || break
    chain="$chain$ppid "
    pid="$ppid"
  done
  printf '%s' "$chain"
}

watcher_roles_proc() {
  local wave="$1" pid seen=0
  local self_chain
  self_chain="$(self_chain_proc)"
  # Phase 1: every process whose REAL argv is a watch on this wave, recorded as
  # "pid ppid role". Phase 2 needs the whole set before it can decide which of
  # them are subshells of each other, so nothing is emitted yet.
  local matched_pids=" " records=() ppid statline strest
  for pid in /proc/[0-9]*; do
    # An unexpanded glob means /proc is there but exposes no process at all -
    # not "no watchers", but "cannot tell" (#801).
    [ "$pid" = '/proc/[0-9]*' ] && break
    pid="${pid#/proc/}"
    seen=1
    case "$self_chain" in *" $pid "*) continue ;; esac
    [ -r "/proc/$pid/cmdline" ] || continue
    local argv=() tok i found_role="" found_wave="default" is_status=0
    while IFS= read -r -d '' tok; do argv+=("$tok"); done < "/proc/$pid/cmdline" 2>/dev/null
    [ "${#argv[@]}" -ge 3 ] || continue
    case "${argv[0]##*/}" in bash) : ;; *) continue ;; esac
    case "${argv[1]}" in */flow-wave-mailbox.sh | flow-wave-mailbox.sh) : ;; *) continue ;; esac
    [ "${argv[2]}" = "watch" ] || continue
    for ((i = 3; i < ${#argv[@]}; i++)); do
      case "${argv[$i]}" in
        --status) is_status=1 ;;
        --role) found_role="${argv[$((i + 1))]:-}" ;;
        --role=*) found_role="${argv[$i]#--role=}" ;;
        --wave) found_wave="${argv[$((i + 1))]:-default}" ;;
        --wave=*) found_wave="${argv[$i]#--wave=}" ;;
      esac
    done
    # `watch --status` shares this argv shape but WATCHES NOTHING - it asks a
    # question and exits. Counting it made the instrument perturb its own
    # reading: two concurrent status checks inflated each other, and a status
    # check running while a real watch armed made that arm refuse as a
    # duplicate (exit 4) against a "watcher" that was only a query (#801).
    [ "$is_status" -eq 0 ] || continue
    [ -n "$found_role" ] || continue
    [ "$found_wave" = "$wave" ] || continue
    ppid=""
    if read -r statline < "/proc/$pid/stat" 2>/dev/null; then
      # Skip past "<pid> (<comm>) " - comm can contain spaces and parentheses,
      # so cut at the LAST ')'. State is then field 1 and ppid field 2.
      strest="${statline##*') '}"
      ppid="${strest#* }"
      ppid="${ppid%% *}"
    fi
    case "$ppid" in ''|*[!0-9]*) ppid=0 ;; esac
    matched_pids="$matched_pids$pid "
    records+=("$pid $ppid $found_role")
  done
  [ "$seen" -eq 1 ] || return 1
  # Phase 2: drop any match whose PARENT also matched. A command-substitution
  # subshell is FORKED, not exec'd, so it inherits the watcher's argv verbatim
  # and is indistinguishable from it by argv alone - one logical watcher read as
  # up to four while it ran its own poll (#801). This is #792 item 5's failure
  # arriving by fork instead of by `bash -c`, and it is excluded the same way:
  # structurally. A real watcher's parent is its launcher (a `-c` wrapper or a
  # shell), which never matches; a subshell's parent is always the watcher.
  local rec rpid rppid rrole
  for rec in ${records+"${records[@]}"}; do
    rpid="${rec%% *}"; rrole="${rec##* }"
    rppid="${rec#* }"; rppid="${rppid%% *}"
    case "$matched_pids" in *" $rppid "*) continue ;; esac
    printf '%s\n' "$rrole"
  done
  return 0
}

# Ancestor chain via `ps` for hosts with no /proc - see self_chain_proc above
# for why the whole chain, not one PID, must be excluded.
self_chain_ps() {
  local pid="$BASHPID" chain=" $BASHPID " ppid
  while [ -n "$pid" ] && [ "$pid" != "1" ]; do
    ppid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
    [ -n "$ppid" ] || break
    chain="$chain$ppid "
    pid="$ppid"
  done
  printf '%s' "$chain"
}

# Best-effort fallback for a host with no /proc (non-Linux): a flattened
# `ps -eo args` match, self-excluded by ancestor chain. This CANNOT
# distinguish a real duplicate from a wrapper whose `-c` argument merely
# contains the pattern (see above) - it degrades toward the old
# over-counting failure rather than refusing to run, because a wave that
# cannot start because its duplicate guard is unavailable is worse than an
# occasional false "duplicate". Over-counting is also the SAFE direction for
# the #801 state fusion: it can only make a dead watch read `armed` (the
# pre-#801 status quo on such a host), never a live one read `dead`.
#
# `ps` producing NO line at all is the one case it refuses to guess at
# (exit 1 -> `unknown`): every host has at least the `ps` process itself, so
# empty output means `ps` is missing or failed, not that nothing is running.
watcher_roles_ps_fallback() {
  local wave="$1" line pid ppid args rest found_role seen=0
  local self_chain matched_pids=" " records=() rec rpid rppid rrole
  self_chain="$(self_chain_ps)"
  while IFS= read -r line; do
    line="${line#"${line%%[![:space:]]*}"}"   # ps right-aligns the pid columns
    [ -n "$line" ] || continue
    seen=1
    pid="${line%% *}"
    rest="${line#* }"
    rest="${rest#"${rest%%[![:space:]]*}"}"
    ppid="${rest%% *}"
    args="${rest#* }"
    case "$self_chain" in *" $pid "*) continue ;; esac
    case "$args" in *flow-wave-mailbox.sh\ watch*) : ;; *) continue ;; esac
    # A status query is not a watcher - same reason as the /proc lane (#801).
    case "$args" in *" --status"*) continue ;; esac
    case "$args" in *" --role "*) rest="${args#*" --role "}" ;; *) continue ;; esac
    found_role="${rest%% *}"
    [ -n "$found_role" ] || continue
    case "$args" in
      *"--wave $wave "*|*"--wave $wave") : ;;
      *"--wave "*) continue ;; # a different wave - not this one's watcher
      *) [ "$wave" = "default" ] || continue ;;
    esac
    matched_pids="$matched_pids$pid "
    records+=("$pid $ppid $found_role")
  done <<EOF
$(ps -eo pid,ppid,args --no-headers 2>/dev/null)
EOF
  # `ps` always sees at least itself, so no output at all means it failed or is
  # absent - unknown, never zero (#801).
  [ "$seen" -eq 1 ] || return 1
  # Same forked-subshell collapse as the /proc lane.
  for rec in ${records+"${records[@]}"}; do
    rpid="${rec%% *}"; rrole="${rec##* }"
    rppid="${rec#* }"; rppid="${rppid%% *}"
    case "$matched_pids" in *" $rppid "*) continue ;; esac
    printf '%s\n' "$rrole"
  done
  return 0
}

VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-wave-mailbox.sh send|read|watch|ack|supervise|list ..."
shift

case "$VERB" in
  send | read | watch | ack | supervise | __supervise_daemon | list) : ;;
  --help | -h)
    # Self-terminating range, not a hand-counted one: a fixed `2,NNp` silently
    # truncates mid-sentence the moment the header grows, which is #686 - and it
    # recurred here the instant #701 added the lexicon-gate paragraph. Stop at
    # the first non-comment line instead, so the range can never drift again.
    sed -n '2,${/^[^#]/q;p;}' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB" ;;
esac

WAVE="default"; ROLE=""; A_TO=""; A_FROM=""; A_BODY=""; A_BODY_FILE=""; A_OUT=""
REPLACE=0; PEEK=0; CONSUME=0; ALL=0; JSON_OUT=0; NO_LEXICON=0; STATUS=0
TIMEOUT="$WATCH_TIMEOUT_DEFAULT"; INTERVAL="$WATCH_INTERVAL_DEFAULT"
A_BOX=""; A_REVS=""; ALL_UNACKED=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wave) [ "$#" -ge 2 ] || usage_fail "--wave requires a name"; WAVE="$2"; shift ;;
    --wave=*) WAVE="${1#--wave=}" ;;
    --role) [ "$#" -ge 2 ] || usage_fail "--role requires a name"; ROLE="$2"; shift ;;
    --role=*) ROLE="${1#--role=}" ;;
    --to) [ "$#" -ge 2 ] || usage_fail "--to requires a role"; A_TO="$2"; shift ;;
    --to=*) A_TO="${1#--to=}" ;;
    --from) [ "$#" -ge 2 ] || usage_fail "--from requires a role"; A_FROM="$2"; shift ;;
    --from=*) A_FROM="${1#--from=}" ;;
    --body) [ "$#" -ge 2 ] || usage_fail "--body requires text"; A_BODY="$2"; shift ;;
    --body=*) A_BODY="${1#--body=}" ;;
    --body-file) [ "$#" -ge 2 ] || usage_fail "--body-file requires a path"; A_BODY_FILE="$2"; shift ;;
    --body-file=*) A_BODY_FILE="${1#--body-file=}" ;;
    --out) [ "$#" -ge 2 ] || usage_fail "--out requires a path"; A_OUT="$2"; shift ;;
    --out=*) A_OUT="${1#--out=}" ;;
    --timeout) [ "$#" -ge 2 ] || usage_fail "--timeout requires seconds"; TIMEOUT="$2"; shift ;;
    --timeout=*) TIMEOUT="${1#--timeout=}" ;;
    --interval) [ "$#" -ge 2 ] || usage_fail "--interval requires seconds"; INTERVAL="$2"; shift ;;
    --interval=*) INTERVAL="${1#--interval=}" ;;
    --replace) REPLACE=1 ;;
    --no-lexicon) NO_LEXICON=1 ;;
    --peek) PEEK=1 ;;
    --consume) CONSUME=1 ;;
    --status) STATUS=1 ;;
    --all) ALL=1 ;;
    --json) JSON_OUT=1 ;;
    --box) [ "$#" -ge 2 ] || usage_fail "--box requires a name"; A_BOX="$2"; shift ;;
    --box=*) A_BOX="${1#--box=}" ;;
    --revs) [ "$#" -ge 2 ] || usage_fail "--revs requires a comma- or space-separated list"; A_REVS="$2"; shift ;;
    --revs=*) A_REVS="${1#--revs=}" ;;
    --all-unacked) ALL_UNACKED=1 ;;
    --*) usage_fail "unknown option: $1" ;;
    *)
      # Bare positional: the role, for the verbs that take one.
      if [ -z "$ROLE" ]; then ROLE="$1"; else usage_fail "unexpected argument: $1"; fi
      ;;
  esac
  shift
done

valid_name "$WAVE" || usage_fail "invalid wave name: '$WAVE' (letters, digits, '_', '.', '-'; no leading dot)"

WAVE_DIR="$WAVE_ROOT/$WAVE"
LOCK_FILE="$WAVE_DIR/.mailbox.lock"
mkdir -p "$WAVE_DIR" 2>/dev/null || usage_fail "cannot create $WAVE_DIR"

E_WAVE="$WAVE"; E_DIR="$WAVE_DIR"
E_ROLE=""; E_BOX=""; E_REV=""; E_UNREAD=""; E_ACKED=""

case "$VERB" in
  send)
    [ -n "$A_TO" ] || usage_fail "send requires --to <role>"
    valid_name "$A_TO" || usage_fail "invalid --to role: '$A_TO'"
    if [ "$A_TO" = "orchestrator" ]; then
      # The writer names its own box: one inbox per worker means two workers
      # reporting at the same moment never contend for one file.
      [ -n "$A_FROM" ] || usage_fail "sending to the orchestrator requires --from <your role> (one inbox per writer)"
      valid_name "$A_FROM" || usage_fail "invalid --from role: '$A_FROM'"
      BOX_NAME="inbox-$A_FROM.md"
    else
      [ -n "$A_FROM" ] || A_FROM="orchestrator"
      valid_name "$A_FROM" || usage_fail "invalid --from role: '$A_FROM'"
      BOX_NAME="outbox-$A_TO.md"
    fi
    BOX="$WAVE_DIR/$BOX_NAME"

    if [ -n "$A_BODY_FILE" ]; then
      [ -r "$A_BODY_FILE" ] || usage_fail "cannot read --body-file: $A_BODY_FILE"
      BODY="$(cat "$A_BODY_FILE")"
    elif [ -n "$A_BODY" ]; then
      BODY="$A_BODY"
    elif [ ! -t 0 ]; then
      BODY="$(cat)"
    else
      usage_fail "send needs a body: --body TEXT, --body-file FILE, or stdin"
    fi
    [ -n "$BODY" ] || usage_fail "refusing to send an empty message (a delivered blank is indistinguishable from no delivery)"

    # Lexicon gate (#701). ONLY exit 1 - "a reserved token is present and
    # malformed" - refuses. Every other non-zero (a usage error, an unreadable
    # helper, jq missing) FAILS OPEN with a note: the validator is a correctness
    # aid, and a guard that can block delivery when it is itself broken would
    # recreate the undelivered-assignment failure this whole lane exists to
    # remove. Absence of tokens is `none`/exit 0 and always delivers.
    if [ "$NO_LEXICON" -eq 0 ]; then
      SELF_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
      LEXICON="$SELF_DIR/flow-wave-lexicon.sh"
      if [ -r "$LEXICON" ]; then
        LEX_OUT="$(printf '%s\n' "$BODY" | bash "$LEXICON" validate 2>&1)"
        LEX_RC=$?
        if [ "$LEX_RC" -eq 1 ]; then
          printf '%s\n' "$LEX_OUT" >&2
          echo "flow-wave-mailbox: NOT delivered - this message declares a state transition that does not parse (issue #701). Fix the token, or re-send with --no-lexicon if the line really is prose." >&2
          E_BOX="$BOX_NAME"
          emit refused
          exit 6
        elif [ "$LEX_RC" -ne 0 ]; then
          echo "flow-wave-mailbox: NOTE - lexicon validator exited $LEX_RC (not a refusal); delivering unvalidated." >&2
        fi
      fi
    fi

    TS="$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)"
    OUT="$(
      (
        flock -w 10 9 || { echo "flow-wave-mailbox: could not lock $WAVE_DIR" >&2; exit 3; }
        rev=0
        if [ -s "$BOX" ]; then
          rev="$(awk '
            /^<!-- cc-flow-wave-msg / {
              if (match($0, /rev=[0-9]+/)) {
                r = substr($0, RSTART + 4, RLENGTH - 4) + 0
                if (r > m) m = r
              }
            }
            END { print m + 0 }
          ' "$BOX")"
        fi
        rev=$((rev + 1))
        tmp="$(mktemp "$WAVE_DIR/.mbox.XXXXXX")" || exit 3
        # --replace still BUMPS the rev: a replaced box whose rev went backwards
        # (or held still) would read as already-consumed and never wake anyone.
        if [ "$REPLACE" -eq 0 ] && [ -s "$BOX" ]; then
          cat "$BOX" > "$tmp" || { rm -f "$tmp"; exit 3; }
          printf '\n' >> "$tmp"
        fi
        printf '<!-- cc-flow-wave-msg rev=%s from=%s to=%s ts=%s -->\n' \
          "$rev" "$A_FROM" "$A_TO" "$TS" >> "$tmp"
        printf '%s\n' "$BODY" >> "$tmp"
        mv -f "$tmp" "$BOX" || { rm -f "$tmp"; exit 3; }
        echo "$rev"
      ) 9>"$LOCK_FILE"
    )"
    RC=$?
    if [ "$RC" -ne 0 ] || [ -z "$OUT" ]; then
      E_BOX="$BOX_NAME"
      emit error
      exit 3
    fi
    E_ROLE="$A_TO"; E_BOX="$BOX_NAME"; E_REV="$OUT"
    E_UNREAD="$(unread_in "$BOX")"
    echo "flow-wave-mailbox: delivered to $BOX_NAME (rev $OUT). The recipient sees it when it reads or its watch fires." >&2
    emit sent
    exit 0
    ;;

  read)
    [ -n "$ROLE" ] || usage_fail "read requires --role <role>"
    valid_name "$ROLE" || usage_fail "invalid role: '$ROLE'"
    if [ -n "$A_FROM" ]; then
      [ "$ROLE" = "orchestrator" ] || usage_fail "read: --from is only meaningful with --role orchestrator (a worker has exactly one box: its own outbox)"
      valid_name "$A_FROM" || usage_fail "invalid --from role: '$A_FROM'"
    fi

    # #792 item 7: draining every inbox at once, non-interactively, with no
    # copy kept anywhere but the terminal has destroyed message content when
    # piped through a filter. Force an explicit choice instead: narrow with
    # --from, don't consume with --peek, or keep a durable copy with --out.
    FULL_DRAIN=0
    [ "$ROLE" = "orchestrator" ] && [ -z "$A_FROM" ] && FULL_DRAIN=1
    if [ "$PEEK" -eq 0 ] && [ "$FULL_DRAIN" -eq 1 ] && [ ! -t 1 ] && [ -z "$A_OUT" ]; then
      usage_fail "read: refusing to drain every inbox non-interactively with no destination (issue #792) - add --peek (non-destructive), --from <role> (one box), or --out FILE (keeps a durable copy before consuming)"
    fi

    if [ -n "$A_FROM" ]; then
      BOX="$WAVE_DIR/inbox-$A_FROM.md"
      UNREAD="$(unread_in "$BOX")"
      if [ "$UNREAD" -eq 0 ] && [ "$ALL" -eq 0 ]; then
        E_ROLE="$ROLE"; E_BOX="inbox-$A_FROM.md"; E_UNREAD=0
        emit empty
        exit 0
      fi
      BODY_OUT=""
      if [ "$ALL" -eq 1 ]; then
        BODY_OUT="$(extract_since "$BOX" -1)"
      else
        BODY_OUT="$(extract_unacked "$BOX")"
      fi
      if [ -n "$BODY_OUT" ]; then
        printf '=== %s ===\n%s\n' "$(basename "$BOX")" "$BODY_OUT"
      fi
      # #815: the durable copy is written BEFORE anything is acknowledged, so
      # a failed write (usage_fail exits here) leaves every message
      # unacknowledged - never the reverse, which is how a write failure used
      # to consume mail it never actually preserved anywhere.
      if [ -n "$A_OUT" ]; then
        printf '%s\n' "$BODY_OUT" > "$A_OUT" || usage_fail "cannot write --out: $A_OUT"
      fi
      if [ "$PEEK" -eq 0 ] && [ "$ALL" -eq 0 ]; then
        ack_all_unacked_in "$BOX"
      fi
      E_ROLE="$ROLE"; E_BOX="inbox-$A_FROM.md"; E_UNREAD="$UNREAD"
      emit read
      exit 0
    fi

    UNREAD="$(unread_for_role "$ROLE")"
    if [ "$UNREAD" -eq 0 ] && [ "$ALL" -eq 0 ]; then
      E_ROLE="$ROLE"; E_UNREAD=0
      emit empty
      exit 0
    fi
    if [ -n "$A_OUT" ]; then
      # Print without acknowledging (peek=1 regardless of the caller's own
      # $PEEK) so the write can be attempted first; ack afterward, only on
      # success, only if the caller actually asked to consume (#815).
      BODY_OUT="$(drain_role "$ROLE" 1 "$ALL")"
      [ -n "$BODY_OUT" ] && echo "$BODY_OUT"
      printf '%s\n' "$BODY_OUT" > "$A_OUT" || usage_fail "cannot write --out: $A_OUT"
      if [ "$PEEK" -eq 0 ] && [ "$ALL" -eq 0 ]; then
        ack_all_unacked_for_role "$ROLE"
      fi
    else
      drain_role "$ROLE" "$PEEK" "$ALL"
    fi
    E_ROLE="$ROLE"; E_UNREAD="$UNREAD"
    emit read
    exit 0
    ;;

  watch)
    [ -n "$ROLE" ] || usage_fail "watch requires --role <role>"
    valid_name "$ROLE" || usage_fail "invalid role: '$ROLE'"

    # `watch --status` (#792 item 3): a one-shot watch makes a bare unread
    # count undiagnosable - zero is BOTH "just woke, re-arm pending" and
    # "blind, nobody is listening". Report the heartbeat plus whether a live
    # watcher process currently holds this role instead.
    if [ "$STATUS" -eq 1 ]; then
      # The count comes FIRST and the state is derived from it (#801). Reading
      # the heartbeat stamp on its own is what let this command answer `armed`
      # about a role with zero live watchers - the two facts printed on one
      # line, contradicting each other, with the reassuring one leading.
      WCOUNT="$(watcher_count "$ROLE" "$WAVE")"
      WSTATE="$(watch_state_of "$ROLE" "$WCOUNT")"
      WAGE="$(watch_age "$ROLE")"
      if [ "$WAGE" = "-" ]; then WLAST="never armed"; else WLAST="last wake handled ${WAGE}s ago"; fi
      case "$WCOUNT" in
        ''|*[!0-9]*) REARMED=unknown; WLIVE="live watcher count UNKNOWN" ;;
        *)           WLIVE="$WCOUNT live watcher process(es)"
                     if [ "$WCOUNT" -gt 0 ]; then REARMED=yes; else REARMED=no; fi ;;
      esac
      echo "flow-wave-mailbox: role '$ROLE' wave '$WAVE': watch is $(printf '%s' "$WSTATE" | tr 'a-z' 'A-Z') - $WLIVE, $WLAST; re-armed: $REARMED"
      case "$WSTATE" in
        dead)
          echo "flow-wave-mailbox: NOTHING is listening for role '$ROLE' - the heartbeat is only as fresh as the last wake, and a watch is one-shot (#801). Mail sent now will not wake anyone. Re-arm as a BACKGROUND call:"
          echo "  flow-wave-mailbox.sh watch --role $ROLE --wave $WAVE --timeout 1800 --consume"
          ;;
        absent)
          echo "flow-wave-mailbox: role '$ROLE' has NEVER armed a watch in wave '$WAVE' - it cannot be woken. Arm it as a BACKGROUND call:"
          echo "  flow-wave-mailbox.sh watch --role $ROLE --wave $WAVE --timeout 1800 --consume"
          ;;
        stale)
          echo "flow-wave-mailbox: a watcher process exists for role '$ROLE' but its heartbeat has not refreshed in ${WAGE}s (poll interval is seconds) - it is hung or stopped, not merely between wakes." >&2
          ;;
        unknown)
          echo "flow-wave-mailbox: the process table could not be enumerated, so whether role '$ROLE' is listening is UNKNOWN - do NOT read this as armed (#801)." >&2
          ;;
      esac
      E_ROLE="$ROLE"
      echo "FLOW_MAILBOX_WATCH_STATE=$WSTATE"
      echo "FLOW_MAILBOX_WATCH_AGE=$WAGE"
      echo "FLOW_MAILBOX_WATCHER_COUNT=$WCOUNT"
      echo "FLOW_MAILBOX_REARMED=$REARMED"
      emit status
      exit 0
    fi

    case "$TIMEOUT" in ''|*[!0-9]*) usage_fail "--timeout must be whole seconds" ;; esac
    case "$INTERVAL" in ''|*[!0-9]*) usage_fail "--interval must be whole seconds" ;; esac
    [ "$INTERVAL" -ge 1 ] || usage_fail "--interval must be at least 1 second"

    # #792 item 1: a bare `watch` used to consume by default, so mail already
    # waiting was marked read without ever being shown. There is no default
    # left - say which you mean. #792 item 2: the correct order depends on
    # the answer - with --peek, read the box THEN arm (the cursor never
    # moves, so arming first on an unread backlog spin-fires on what you just
    # read); with --consume, arm THEN read.
    if [ "$PEEK" -eq 1 ] && [ "$CONSUME" -eq 1 ]; then
      usage_fail "watch: --peek and --consume are mutually exclusive"
    fi
    if [ "$PEEK" -eq 0 ] && [ "$CONSUME" -eq 0 ]; then
      usage_fail "watch requires an explicit --peek or --consume (issue #792) - silent default consumption has marked mail read that was never shown. Use --consume to arm-then-read (mail is marked read on wake), or --peek to read-then-arm (mail is NOT consumed, so re-arming immediately would spin-fire on it)."
    fi

    # #792 item 4: a role is single-owner by construction, so a second live
    # watcher on the same role+wave is always a mistake - it competes for the
    # same mail instead of getting a copy of it. Refuse rather than let
    # duplicates accumulate invisibly.
    EXISTING="$(count_watchers "$ROLE" "$WAVE")"
    if [ "$EXISTING" -gt 0 ]; then
      E_ROLE="$ROLE"
      echo "flow-wave-mailbox: refusing to arm - $EXISTING live watcher(s) already hold role '$ROLE' in wave '$WAVE' (issue #792). A role is single-owner: two watchers compete for the same mail rather than each seeing a copy. Check 'watch --status --role $ROLE --wave $WAVE' before starting another." >&2
      emit duplicate
      exit 4
    fi

    WAITED=0
    FIRST_POLL=1
    while :; do
      # Stamp BEFORE the check, so an arm that fires on its very first poll -
      # mail already waiting - still leaves the trace #778 exists to leave.
      watch_stamp "$ROLE"
      UNREAD="$(unread_for_role "$ROLE")"
      if [ "$UNREAD" -gt 0 ]; then
        # #792 item 2: this fired on the very first poll, i.e. the mail was
        # already unread the instant this watch armed - not a fresh wake.
        # Say so up front rather than let it read as one.
        if [ "$FIRST_POLL" -eq 1 ]; then
          echo "flow-wave-mailbox: NOTE - mail was already unread when this watch armed; this is not a fresh wake (issue #792)."
        fi
        drain_role "$ROLE" "$PEEK" 0
        E_ROLE="$ROLE"; E_UNREAD="$UNREAD"
        emit mail
        exit 0
      fi
      FIRST_POLL=0
      # A timeout of 0 means "check once and report" - useful in tests and as a
      # cheap poll, and it keeps the bounded default from being the only shape.
      [ "$WAITED" -lt "$TIMEOUT" ] || break
      sleep "$INTERVAL"
      WAITED=$((WAITED + INTERVAL))
    done
    E_ROLE="$ROLE"; E_UNREAD=0
    echo "flow-wave-mailbox: no mail for '$ROLE' in wave '$WAVE' after ${TIMEOUT}s." >&2
    echo "  A timeout is NOT proof the counterpart is gone - check the roster" >&2
    echo "  (flow-wave-registry.sh list --wave $WAVE) before assuming anything." >&2
    emit timeout
    exit 5
    ;;

  ack)
    # Explicit receipt (issue #815). See the ACKNOWLEDGEMENT section of the
    # header for the full argument; this verb is the durable half of it -
    # `read --peek` / `watch --peek` surface mail without touching this at
    # all, and this is the ONLY thing that ever does.
    [ -n "$ROLE" ] || usage_fail "ack requires --role <role>"
    valid_name "$ROLE" || usage_fail "invalid role: '$ROLE'"
    if [ -n "$A_FROM" ]; then
      [ "$ROLE" = "orchestrator" ] || usage_fail "ack: --from is only meaningful with --role orchestrator (a worker has exactly one box: its own outbox)"
      valid_name "$A_FROM" || usage_fail "invalid --from role: '$A_FROM'"
    fi
    if [ -n "$A_BOX" ] && [ "$ROLE" != "orchestrator" ]; then
      usage_fail "ack: --box is only meaningful with --role orchestrator (a worker has exactly one box: its own outbox)"
    fi
    if [ -n "$A_FROM" ] && [ -n "$A_BOX" ]; then
      usage_fail "ack: --from and --box both name the target box - use one"
    fi
    if [ -z "$A_REVS" ] && [ "$ALL_UNACKED" -eq 0 ]; then
      usage_fail "ack requires --revs R[,R...] or --all-unacked"
    fi
    if [ -n "$A_REVS" ] && [ "$ALL_UNACKED" -eq 1 ]; then
      usage_fail "ack: --revs and --all-unacked are mutually exclusive"
    fi

    # Resolve the target box(es), one absolute path per line.
    if [ "$ROLE" = "orchestrator" ]; then
      if [ -n "$A_FROM" ]; then
        TARGET_BOXES="$WAVE_DIR/inbox-$A_FROM.md"
      elif [ -n "$A_BOX" ]; then
        case "$A_BOX" in
          inbox-*.md) : ;;
          *) usage_fail "ack: --box must name an inbox-*.md the orchestrator reads: '$A_BOX'" ;;
        esac
        TARGET_BOXES="$WAVE_DIR/$A_BOX"
      elif [ "$ALL_UNACKED" -eq 1 ]; then
        TARGET_BOXES="$(boxes_for_role orchestrator)"
      else
        usage_fail "ack: the orchestrator reads more than one box - disambiguate with --from <role>, --box NAME, or ack across all of them with --all-unacked"
      fi
    else
      TARGET_BOXES="$WAVE_DIR/outbox-$ROLE.md"
    fi

    TOTAL_ACKED=0
    SAW_A_BOX=0
    while IFS= read -r b; do
      [ -n "$b" ] || continue
      [ -f "$b" ] || continue
      SAW_A_BOX=1
      if [ "$ALL_UNACKED" -eq 1 ]; then
        N_BEFORE="$(unread_in "$b")"
        ack_all_unacked_in "$b" || exit $?
        TOTAL_ACKED=$((TOTAL_ACKED + N_BEFORE))
      else
        REVLIST="$(printf '%s' "$A_REVS" | tr ',' ' ')"
        # shellcheck disable=SC2086
        ack_add "$b" $REVLIST || exit $?
        # shellcheck disable=SC2086
        N_GIVEN="$(printf '%s\n' $REVLIST | grep -c '[0-9]')"
        TOTAL_ACKED=$((TOTAL_ACKED + N_GIVEN))
      fi
    done <<EOF
$TARGET_BOXES
EOF
    if [ "$SAW_A_BOX" -eq 0 ]; then
      # No box exists yet to ack against - e.g. a worker nobody has sent to.
      # Not an error: there is nothing unacknowledged, by construction.
      E_ROLE="$ROLE"; E_ACKED=0
      emit empty
      exit 0
    fi
    E_ROLE="$ROLE"; E_ACKED="$TOTAL_ACKED"
    emit acked
    exit 0
    ;;

  supervise)
    # Own a re-arm loop for <role> so nothing conversational has to remember
    # to re-arm `watch` after every wake (issue #814 - see SUPERVISION in the
    # header for the full argument). This case handles only the LAUNCH: it
    # returns promptly with its own verdict line, like every other verb. The
    # loop itself runs in `__supervise_daemon` below, in a detached process.
    [ -n "$ROLE" ] || usage_fail "supervise requires --role <role>"
    valid_name "$ROLE" || usage_fail "invalid role: '$ROLE'"
    case "$TIMEOUT" in ''|*[!0-9]*) usage_fail "--timeout must be whole seconds" ;; esac
    case "$INTERVAL" in ''|*[!0-9]*) usage_fail "--interval must be whole seconds" ;; esac
    [ "$INTERVAL" -ge 1 ] || usage_fail "--interval must be at least 1 second"

    SUP_LOCK="$WAVE_DIR/.supervise-$ROLE.lock"
    SUP_PIDFILE="$WAVE_DIR/.supervise-$ROLE.pid"
    SUP_LOG="$WAVE_DIR/.supervise-$ROLE.log"

    # A lifetime flock, not a PID file, decides ownership (issue #814,
    # required correction from #821: a recorded PID can be reused by the
    # kernel, so `kill -0` would eventually report a DEAD daemon's replacement
    # as alive and refuse a real one - the same defect as #821's argv
    # collision, one layer up). The lock is opened in THIS process (not a
    # subshell) so it survives past this `if`, ready to be inherited by the
    # detached daemon below.
    exec 8>"$SUP_LOCK"
    if ! flock -n 8; then
      E_ROLE="$ROLE"
      echo "flow-wave-mailbox: refusing to supervise - a live supervisor already holds role '$ROLE' in wave '$WAVE' (issue #814). Check $SUP_PIDFILE / $SUP_LOG for who; the lock, not that file, is what decided this." >&2
      emit duplicate
      exit 4
    fi
    # We hold the lock on fd 8. A normal backgrounded child inherits every
    # open fd from its parent shell, so it needs no explicit redirection to
    # keep fd 8 - detaching it (setsid, when available - falls back to a
    # plain background+disown on a host without it, still correct, just less
    # isolated from this shell's session) is what makes the lock outlive
    # THIS invocation: this process's own copy of fd 8 closes at exit, but
    # the daemon's independent copy keeps the flock held for as long as the
    # daemon lives - which is exactly the property #814 needs, since the
    # kernel releasing a flock on process death is what lets the NEXT
    # `supervise` tell "dead" from "alive" without asking anything else.
    if command -v setsid >/dev/null 2>&1; then
      setsid bash "$0" __supervise_daemon --role "$ROLE" --wave "$WAVE" \
        --timeout "$TIMEOUT" --interval "$INTERVAL" >>"$SUP_LOG" 2>&1 &
    else
      bash "$0" __supervise_daemon --role "$ROLE" --wave "$WAVE" \
        --timeout "$TIMEOUT" --interval "$INTERVAL" >>"$SUP_LOG" 2>&1 &
    fi
    DAEMON_PID=$!
    disown 2>/dev/null || true
    # Diagnostics only - who a human should look at - never the liveness
    # test itself (that is the flock, above).
    echo "$DAEMON_PID" > "$SUP_PIDFILE" 2>/dev/null || true
    E_ROLE="$ROLE"
    echo "flow-wave-mailbox: supervising role '$ROLE' in wave '$WAVE' as PID $DAEMON_PID (issue #814) - it re-arms watch continuously until role release or the wave ends; see $SUP_LOG for sanitized evidence (timestamps and exit codes only, never message bodies)." >&2
    emit supervising
    exit 0
    ;;

  __supervise_daemon)
    # INTERNAL. Launched by `supervise` above via setsid; never invoke this
    # directly. Runs until role release, an unreadable registry sibling that
    # stops looking free, or a TERM/INT signal - its own exit is what
    # releases the lifetime flock `supervise` opened and handed it.
    [ -n "$ROLE" ] || usage_fail "__supervise_daemon requires --role <role>"
    SUP_LOG_SELF_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
    SUP_REGISTRY="$SUP_LOG_SELF_DIR/flow-wave-registry.sh"
    BACKOFF_BASE="${FLOW_WAVE_SUPERVISE_BACKOFF_BASE:-2}"
    BACKOFF_CAP="${FLOW_WAVE_SUPERVISE_BACKOFF_CAP:-60}"
    BACKOFF=0

    # Structured, sanitized evidence ONLY - a timestamp and a short event
    # description (event kind, exit code, backoff seconds). NEVER message
    # bodies: the inner `watch` child's stdout, which DOES carry bodies on
    # delivery, is discarded below (redirected to /dev/null), not relayed
    # into this log or anywhere else - the daemon's job is re-arming, not
    # reading (issue #814).
    log_event() {
      printf '%s %s\n' "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)" "$*"
    }

    log_event "daemon started role=$ROLE wave=$WAVE pid=$$ timeout=$TIMEOUT interval=$INTERVAL"
    trap 'log_event "daemon exiting on signal"; exit 0' TERM INT

    while :; do
      # Shutdown check (issue #814): fails OPEN if the registry sibling is
      # missing or errors - a supervisor that cannot check for release is
      # not worse than none, it just keeps supervising, matching #701's
      # lexicon-gate precedent for a helper another script depends on.
      # Also fails open (keeps supervising) on `get`'s `free` verdict - a
      # role can be `free` simply because it was never registered at all,
      # which is a LEGITIMATE, independent way to use `supervise` (the
      # registry is a separate, optional companion system, not a
      # dependency - #814's own boundary). Only the POSITIVE, unambiguous
      # signal shuts this daemon down: `FLOW_WAVE_LIVENESS=released`, set
      # only once `release` has actually run against a role that WAS
      # registered. `stale` (owning session looks dead, never explicitly
      # released) deliberately does NOT shut down either - that can be a
      # respawn in progress, and #814 asks for shutdown on RELEASE, not a
      # guess about liveness this daemon has no way to confirm.
      if [ -r "$SUP_REGISTRY" ]; then
        # flow-wave-registry.sh takes the role as a bare positional, not a
        # --role flag - its own parser has no such option.
        REL_LIVENESS="$(bash "$SUP_REGISTRY" get "$ROLE" --wave "$WAVE" 2>/dev/null | sed -n 's/^FLOW_WAVE_LIVENESS=//p')"
        if [ "$REL_LIVENESS" = "released" ]; then
          log_event "role released - shutting down"
          exit 0
        fi
      fi

      bash "$0" watch --role "$ROLE" --wave "$WAVE" --consume \
        --timeout "$TIMEOUT" --interval "$INTERVAL" >/dev/null 2>&1
      INNER_RC=$?

      case "$INNER_RC" in
        0)
          # Delivered and acknowledged (the daemon uses --consume - the
          # named legacy convenience, matching the file's own default
          # elsewhere; the delivered CONTENT is safely durable in the box
          # already, the daemon does not need to relay it anywhere new).
          log_event "delivered rc=0"
          BACKOFF=0
          ;;
        5)
          # A plain, expected timeout - the daemon re-arms silently, this is
          # the normal steady state of a persistent listener.
          BACKOFF=0
          ;;
        *)
          # Anything else is a crash-class exit (killed, duplicate-refused
          # against something outside this daemon's own control, or an
          # error). Exponential backoff, capped, so a persistently failing
          # cause cannot spin this loop at full speed forever (issue #814's
          # explicit "no tight restart loop" requirement).
          if [ "$BACKOFF" -eq 0 ]; then BACKOFF="$BACKOFF_BASE"; else BACKOFF=$((BACKOFF * 2)); fi
          [ "$BACKOFF" -gt "$BACKOFF_CAP" ] && BACKOFF="$BACKOFF_CAP"
          log_event "inner watch exited rc=$INNER_RC - backing off ${BACKOFF}s"
          sleep "$BACKOFF"
          ;;
      esac
    done
    ;;

  list)
    BOXES="$(find "$WAVE_DIR" -maxdepth 1 -type f \( -name 'outbox-*.md' -o -name 'inbox-*.md' \) 2>/dev/null | sort)"
    WROLES="$(watch_roles)"
    TOTAL_UNREAD=0
    # ONE pass over the process table for the whole table (#801), not one per
    # role. LIVE_ROLES is the raw role-per-line list; LIVE_OK=0 means it could
    # not be enumerated, which every row must then render as `unknown` rather
    # than as zero watchers.
    LIVE_OK=1
    LIVE_ROLES="$(watcher_roles_live "$WAVE")" || LIVE_OK=0
    watchers_for() {
      [ "$LIVE_OK" -eq 1 ] || { echo unknown; return; }
      printf '%s\n' "$LIVE_ROLES" | grep -cxF -- "$1"
    }
    if [ "$JSON_OUT" -eq 1 ]; then
      # `reader` and `mtime` join a box to the role whose watch decides whether
      # anything in it will ever be noticed - that join is what the #638 roster
      # consumes to render `watch=`/`unread=` per role (#778).
      ROWS=""
      while IFS= read -r b; do
        [ -n "$b" ] || continue
        n="$(unread_in "$b")"; r="$(max_rev "$b")"; c="$(acked_count "$b")"
        TOTAL_UNREAD=$((TOTAL_UNREAD + n))
        mt="$(date -r "$b" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || echo '-')"
        # "acked" (issue #815) replaces the retired "cursor" - the count of
        # revs that box's reader has EXPLICITLY acknowledged, not a read
        # position. rev=SENT, unread=NOT YET ACKNOWLEDGED, acked=CONFIRMED
        # RECEIVED; none of the three implies either of the others.
        ROWS="$ROWS$(printf '{"box":"%s","reader":"%s","rev":%s,"acked":%s,"unread":%s,"mtime":"%s"}' \
          "$(basename "$b")" "$(reader_of_box "$b")" "$r" "$c" "$n" "$mt"),"
      done <<EOF
$BOXES
EOF
      WATCHES=""
      while IFS= read -r wr; do
        [ -n "$wr" ] || continue
        wa="$(watch_age "$wr")"
        if [ "$wa" = "-" ]; then wa_json=null; else wa_json="$wa"; fi
        # `watchers` is part of the contract, not a nicety (#801): the roster
        # renders the STATE, and a consumer that wants to check the fusion for
        # itself needs the count the state was derived from. `null` means the
        # process table could not be read - never 0.
        wc="$(watchers_for "$wr")"
        case "$wc" in ''|*[!0-9]*) wc_json=null ;; *) wc_json="$wc" ;; esac
        WATCHES="$WATCHES$(printf '{"role":"%s","state":"%s","age_secs":%s,"watchers":%s}' \
          "$wr" "$(watch_state_of "$wr" "$wc")" "$wa_json" "$wc_json"),"
      done <<EOF
$WROLES
EOF
      # `routes` is a SIBLING array, not folded into `watches` (issue #814) -
      # `watch.state` answers "is a process polling" and stays exactly as
      # #821-affected as it always was; `route.state` answers "has anything
      # been acknowledged since" and never touches the watcher count. Fusing
      # them is the #801 mistake in new clothes.
      ROUTES=""
      while IFS= read -r wr; do
        [ -n "$wr" ] || continue
        rs="$(route_state_for_role "$wr")"
        ROUTES="$ROUTES$(printf '{"role":"%s","state":"%s"}' "$wr" "$rs"),"
      done <<EOF
$WROLES
EOF
      printf '{"wave":"%s","dir":"%s","boxes":[%s],"watches":[%s],"routes":[%s]}\n' \
        "$WAVE" "$WAVE_DIR" "${ROWS%,}" "${WATCHES%,}" "${ROUTES%,}"
    else
      if [ -z "$BOXES" ]; then
        echo "No mailboxes in wave '$WAVE' yet ($WAVE_DIR)."
      else
        printf '%-24s %6s %7s %7s  %s\n' BOX REV ACKED UNREAD MTIME
        while IFS= read -r b; do
          [ -n "$b" ] || continue
          n="$(unread_in "$b")"; r="$(max_rev "$b")"; c="$(acked_count "$b")"
          TOTAL_UNREAD=$((TOTAL_UNREAD + n))
          mt="$(date -r "$b" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || echo '-')"
          printf '%-24s %6s %7s %7s  %s\n' "$(basename "$b")" "$r" "$c" "$n" "$mt"
        done <<EOF
$BOXES
EOF
      fi
      # The watch table (#778), separate from the box table because a box says
      # what was DELIVERED and this says whether anyone is listening - the half
      # that used to be invisible everywhere.
      if [ -n "$WROLES" ]; then
        echo
        # WATCHERS is printed beside WATCH deliberately (#801): the state is
        # DERIVED from the count, so showing both makes the derivation
        # checkable instead of asking the reader to trust a word.
        printf '%-24s %8s %8s  %s\n' ROLE WATCH WATCHERS LAST
        DEAF_ROLES=""
        UNKNOWN_ROLES=""
        while IFS= read -r wr; do
          [ -n "$wr" ] || continue
          wa="$(watch_age "$wr")"
          if [ "$wa" = "-" ]; then last="never armed"; else last="${wa}s ago"; fi
          wc="$(watchers_for "$wr")"
          ws="$(watch_state_of "$wr" "$wc")"
          case "$ws" in
            dead|absent) DEAF_ROLES="$DEAF_ROLES $wr($ws)" ;;
            unknown)     UNKNOWN_ROLES="$UNKNOWN_ROLES $wr" ;;
          esac
          printf '%-24s %8s %8s  %s\n' "$wr" "$ws" "$wc" "$last"
        done <<EOF
$WROLES
EOF
        if [ -n "$DEAF_ROLES" ]; then
          echo "DEAF: no live watcher for role(s):$DEAF_ROLES - mail sent to them will not wake anyone (#801)."
        fi
        # Kept separate from DEAF on purpose: `unknown` is not a claim that
        # nobody is listening, it is the refusal to make either claim.
        if [ -n "$UNKNOWN_ROLES" ]; then
          echo "UNKNOWN: the process table could not be read, so the watch state of role(s):$UNKNOWN_ROLES is UNCHECKED, not clean (#801)."
        fi
        # The route table (issue #814), separate from WATCH on purpose (see
        # the header's ROUTE READINESS section): WATCH says a process is
        # polling, ROUTE says whether anything has actually been received.
        ROUTE_BOUND="${FLOW_WAVE_ROUTE_UNCONFIRMED_SECS:-900}"
        echo
        printf '%-24s %s\n' ROLE ROUTE
        UNCONFIRMED_ROLES=""
        while IFS= read -r wr; do
          [ -n "$wr" ] || continue
          rs="$(route_state_for_role "$wr")"
          [ "$rs" = unconfirmed ] && UNCONFIRMED_ROLES="$UNCONFIRMED_ROLES $wr"
          printf '%-24s %s\n' "$wr" "$rs"
        done <<EOF
$WROLES
EOF
        if [ -n "$UNCONFIRMED_ROLES" ]; then
          echo "UNCONFIRMED: no acknowledgement seen in over ${ROUTE_BOUND}s for role(s):$UNCONFIRMED_ROLES - a process may be polling (see WATCH above) without anyone actually receiving anything (issue #814)."
        fi
      fi
    fi
    E_UNREAD="$TOTAL_UNREAD"
    emit listed
    exit 0
    ;;
esac
