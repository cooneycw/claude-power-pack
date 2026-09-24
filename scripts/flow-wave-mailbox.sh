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
#                              (--revs R[,R...] | --all-unacked) [--answered-elsewhere]
#   flow-wave-mailbox.sh supervise --role <role> [--wave W] [--timeout SEC]
#                              [--interval SEC] [--registry-required]
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
#          is what persists, repeatedly arming `watch --peek` for <role> until
#          role release or the wave ends. It never ACKNOWLEDGES: a detached
#          daemon is not a recipient, and a receipt it writes is a lie about
#          an agent (#867, #873). See SUPERVISION below for what this does
#          and, as importantly, does not promise. `--registry-required`
#          (issue #1107) makes the registry a precondition instead of an
#          optional companion: the launch is REFUSED when nothing was ever
#          registered in --wave (exit 7, `misconfigured`), or when the
#          registry cannot answer (exit 8, `unverified`).
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
# `watch --role <role> --wave <wave> --peek --surfaced-state <file>`, letting
# EACH inner watch still exit - `supervise` guarantees a listener always
# EXISTS, it is not a replacement for arming one.
#
# `--peek`, emphatically not `--consume` (issues #867, #873). The daemon used
# to consume, which acknowledged every message it printed while sending that
# print to a log. Mail was therefore recorded as RECEIVED by a process that is
# not the recipient, and all four of the tells an orchestrator is told to steer
# by went quiet at once: `UNREAD` returned to 0 seconds after every send,
# `route` read `confirmed`, the `watch=armed route=UNCONFIRMED` combination
# became unreachable, and `** NEVER READ **` could not fire. Measured on a live
# wave: 7 of 7 assignments acked, 0 delivered, for most of a working session,
# with the roster agreeing throughout (#873).
#
# That is worse than having no receipts, because a wrong receipt removes the
# reason to check. It also inverted the one separation #814 was careful to
# build: `route_state` reads ack evidence precisely so it fails INDEPENDENTLY
# of `watch`'s process check - and the polling process became the source of the
# ack evidence, so one instrument manufactured the other's.
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
# releasing the flock - once that role's `FLOW_WAVE_LIVENESS` reads
# `released`. NOT the moment it is released (issue #1033 item 4): the
# registry check sits at the top of this loop, and the loop body then
# blocks in the inner `watch --timeout`, so a release is honoured within one
# `--timeout` of when it happened, never instantly - `watch --status` reports
# this daemon's own `--timeout` (`FLOW_MAILBOX_SUPERVISE_TIMEOUT`) precisely
# so a reader can compute that bound instead of assuming zero latency. The
# same bound applies to a TERM/INT signal for the identical reason: bash
# defers a trapped signal until the current foreground command (the blocking
# inner watch) returns, so `kill <daemon-pid>` can likewise take up to one
# full `--timeout` before this daemon actually exits, measured directly at
# t+4.0s against `--timeout 4` (see the Nit Store, claude-power-pack#864).
# Fails OPEN, TWICE over: if the registry sibling is unavailable
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
# What this does not promise, and why that is a CHOICE rather than an
# impossibility (issue #898; measurements #868 and #871, harness 2.1.266).
# This paragraph used to say that no script here COULD make the harness
# re-invoke a session on a background process's completion, stated as a
# property of the world with no version attached. The conclusion was right and
# the reason was wrong - and the unstamped absolute was the worse half, because
# a sentence that reads as a law gives a reader no cause to re-check it.
#
# What the harness actually exposes. Every session has an inbox socket and
# token (`CLAUDE_CODE_MESSAGING_SOCKET`, `CLAUDE_CODE_MESSAGING_TOKEN`), and a
# correctly-formed write to that socket DOES render as a turn - measured 5/5 on
# **2.1.266**, 2026-09-13, from inside a per-session container. So the wiring is
# not missing, and "belongs to the harness, not to anything in this repo" was
# never the reason this lane stops here.
#
# Why `supervise`'s daemon nonetheless cannot use it. Delivery is gated on
# PROCESS LINEAGE, not on holding the credential. Writers reparented to init
# were ACCEPTED by the socket and never delivered - 0/4, each confirmed by its
# own log to have run and written - while writers whose parent chain still
# reached the session delivered 5/5 (2.1.266, 2026-09-13, interleaved in time
# and run in both orderings). That matches `verifiedPeerPid` /
# `expectPeerProcStart` in the installed binary. Inheriting the two variables is
# NOT sufficient and was never the question: both survive into a
# `setsid`-detached grandchild and the write is still dropped. `setsid` is not
# the discriminator either - a `setsid` writer with a live parent chain
# delivers fine.
#
# `supervise`'s daemon detaches precisely so it outlives the launching turn
# (#814), which makes it the orphaned shape BY CONSTRUCTION. So the one process
# that would do the waking is the one process that cannot be delivered from.
# That is this lane's own design in tension with itself - a consequence of
# detaching that we accept - not a capability the harness withholds.
#
# Two bounds on the above, both load-bearing. The socket RETURNS NOTHING: a
# writer cannot tell whether its message landed, so a successful write is not
# evidence of delivery even where delivery works. And the measurement has one
# vantage - inside a container, against the measuring session's OWN socket.
#
# Do not read the lineage result as "so share the mounts and it works". Across
# containers the identity problem is upstream of lineage: a session record
# carries a `pidDomain` naming the machine and pid namespace its pid is
# meaningful in, and the harness reads the peer pid from the CONNECTION
# (`SO_PEERCRED`), never from the payload - so a shared records directory would
# hand each side a pid from a domain it cannot verify, and discovery would list
# peers delivery cannot vouch for (measured 2026-09-15, 2.1.266, one container,
# one vantage; #945, closed on it). Sharing the socket directory was REJECTED on
# separate grounds - every session container runs as uid 1000, so mode 700
# separates nothing between siblings. The wake across that boundary belongs to
# the substrate, which is where kyle #1008 puts it. See register.md's container
# boundary for the decision and its evidence; this comment only borrows it to
# say that the daemon's problem is not the one a mount would fix.
#
# So: `supervise` guarantees a listener keeps existing; it does not guarantee
# the agent behind it is told. See ROUTE READINESS below for the honest
# alternative to promising that: making a silent failure of THAT link
# observable, with a bound, instead of claiming to have fixed it. The
# returns-nothing property is why that alternative would still be required even
# if the lineage constraint were lifted tomorrow.
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
# processes, both matching. The watcher scan below reads each candidate's
# REAL argv from `/proc/<pid>/cmdline` and requires it to BE the script
# invocation (`argv[1]` the script path, `argv[2]` "watch") rather than
# CONTAIN it, which excludes a `-c` wrapper structurally. Self-exclusion
# walks the full ancestor chain, not one PID: this runs inside a `$(...)`
# subshell, and the subshell's own PARENT - the real, currently alive
# top-level process, legitimately blocked waiting on this very check -
# carries the identical argv under a different PID.
#
# Watcher identity (issue #821). The #792 item 5 fix above answers WHO IS
# ASKING - it makes the scanner unable to count its own launcher, however
# that launcher's command text reads - and it is correct and untouched by
# this section. It does not answer WHAT IS IDENTIFIED, and that turned out
# to be a separate, deeper hole: `watcher.kill()` genuinely reaps the direct
# child, but that child's own command-substitution subshells are FORKED, not
# exec'd, so they carry byte-identical argv, a SIGKILL to the parent never
# reaches them, and they reparent to init and live until their own
# `--timeout` expires - one killed watcher measured leaving four to five
# survivors (12-run correlation: 10 clean, 2 runs at 4 and 5 orphans, no
# exceptions). Phase 2's "drop any match whose parent also matched" cannot
# catch this: its own invariant - a subshell's parent is always the watcher
# - holds only while the watcher is alive, and an orphan's parent is init,
# which matches nothing, so it survives the filter BY VIRTUE of having been
# orphaned. An orphan has exactly the right argv structure to look like a
# live watcher, because it was forked from a process that had it - no
# amount of argv rigor separates the two, because by every argv-visible
# property they are identical.
#
# The fix moves the key off argv entirely and onto the resolved wave
# DIRECTORY: `wave_root_of_pid()` reads a candidate's OWN environment
# (`/proc/<pid>/environ`, mirroring `WAVE_ROOT`'s own precedence chain) and
# `watcher_roles_proc()` only counts a candidate whose resolved wave
# directory matches this invocation's - the wave NAME match stays as a
# cheap pre-filter, never the decision. This closes the hole ACROSS
# contexts: this repo's own test suite gives every test a fresh
# `FLOW_WAVE_MAILBOX_DIR` while every test in one file shares that file's
# wave NAME (`tests/wave_namespace.py`), so an orphan surviving from one test
# resolves to a directory the next test's scan does not share, and is
# excluded. That wave name is per pytest INVOCATION since #881/#882 - it was
# the literal "testwave" in every checkout, which left this pre-filter
# matching OTHER runs' watchers on the same host. The directory check below
# already excluded them for THIS lane; the `ps` lane has no such check, which
# is why the namespace itself had to become unique.
#
# The mechanism does NOT close the hole WITHIN one wave, and this half is
# verified, not assumed: an orphaned subshell is forked from its parent
# watcher AFTER that parent's own environment was already set, so it
# inherits the IDENTICAL `FLOW_WAVE_MAILBOX_DIR` - confirmed by forking a
# child from a process holding that variable, killing only the parent, and
# reading the reparented child's own `/proc/<pid>/environ` afterward:
# unchanged. IF a same-wave orphan forms, it resolves to the SAME directory
# as a live watcher and would still be counted.
#
# Whether that actually HAPPENS in `supervise`'s (#814) own kill-and-restart
# path - the one place in this codebase that kills a watch on its OWN wave
# directory by design - was tested directly rather than assumed either way:
# 15 trials arming `supervise`, SIGKILLing its real inner watch child
# (identified structurally, not by a flattened-line match), and rescanning
# structurally for survivors. Zero orphans in 15/15. `master:kyle`'s
# original 12-run measurement (2 failures, 4-5 orphans each) was a DIFFERENT
# scenario - `TestWatchStatus`, embedded in a large concurrent suite under
# heavier host contention - and the two results do not contradict each
# other: an orphan forms when a SIGKILL lands while the watcher is mid-fork
# inside a command substitution, and that window may simply need contention
# an isolated 15-trial run does not reproduce. So: the same-wave mechanism
# is real (proven deterministically); its occurrence in `supervise`'s kill
# path specifically is CONSIDERED AND NOT OBSERVED, not a confirmed gap -
# stated at exactly this precision, neither stronger nor weaker.
# The arm-guard view (`watch`'s duplicate check) already treats an unenumerable
# process table as 0 and proceeds - a wave that cannot start because its
# duplicate guard is unavailable is worse than an occasional false
# duplicate (#792 item 4) - and IF this residual ever fires, it fails the
# same direction: a false REFUSAL, recoverable (#814's own exponential
# backoff, or a human re-arming), never a false SILENCE.
#
# No second discriminator is proposed here. PPID checks are explicitly
# rejected: a watch legitimately reparented by a harness (`/flow:register`
# step 4 does exactly this) is not thereby an orphan, so "parent is init"
# cannot mean "orphaned". Nobody has a verified model of why these
# subshells live as long as they do, either - the 12-run correlation
# establishes the relationship, not the mechanism - and a second
# discriminator should start from measuring that lifetime, not from a
# theory about it.
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
#   >0        within STALE     armed    listening right now, and at least one
#                                       watcher is SESSION-PARENTED (or its
#                                       parentage could not be read - see
#                                       WAKEABILITY below)
#   >0, none  any              no-wake  polling, but NO watcher has a Claude
#   session-                            Code session in its ancestry, so
#   parented                            nothing it notices can wake anyone
#                                       (#1228). A `supervise` daemon alone
#                                       reads this way
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
# WAKEABILITY (issue #1228). The harness re-invokes a session only when a
# process THAT SESSION OWNS exits. #868 measured the rule on the messaging
# socket: writes from a process whose parent chain reaches the session were
# delivered 5/5, from one reparented to init 0/4 - lineage is the
# discriminator, not setsid and not inherited environment. So "is a process
# polling" (the count) and "can this role be woken" are different questions,
# and until #1228 the roster answered only the first: three waves read
# `armed, 0s ago` over sessions that sat deaf for 20-35 minutes, one daemon
# outliving its session by 18h. Each watcher is now classified by walking its
# ancestry for a process that owns `$SOCK_DIR/<pid>.sock` - the same test
# flow-wave-registry.sh uses to find a session's own address:
#   session  a session is an ancestor - its exit wakes that session
#   orphan   the chain reaches init without one - it cannot wake anyone
#   unknown  no socket directory to test against, or the chain vanished
#            mid-walk. Rendered as the pre-#1228 reading, never as `orphan`.
# What this does NOT check: that the ancestor session is the one REGISTERED for
# the role. A watch armed for role X from session Y reads `armed`.
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
# A token read as a CITATION rather than a transition (fenced, or behind a `>`
# prefix - issue #980) delivers normally, and its FLOW_LEXICON_CITATION= line is
# printed to the sender anyway. That is deliberate: `--no-lexicon` is a
# WHOLE-MESSAGE escape, useless for the message that both cites a past ruling
# and issues a new one, and an inert token is indistinguishable from a dropped
# one unless somebody says so. This is the only point at which a sender sees the
# validator's answer on a successful send.
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
# delivered; nothing was written), 7 `supervise --registry-required` against a
# wave with no role ever registered (#1107 - nothing was started), 8 the same
# flag when the registry could not answer at all (#1107 - nothing was started;
# this is NOT a finding that the wave is empty).
#
# `watch --status` detail lines:
#   FLOW_MAILBOX_WATCH_STATE    armed | no-wake | stale | dead | absent |
#                               unknown - the FUSED verdict (#801), never the
#                               raw stamp
#   FLOW_MAILBOX_WATCH_AGE      seconds since the last heartbeat, or '-'. Still
#                               reported for every state, so "died just now" and
#                               "died an hour ago" stay distinguishable
#   FLOW_MAILBOX_WATCHER_COUNT  live watcher processes, or `unknown`
#   FLOW_MAILBOX_SESSION_WATCHERS  how many of those are session-parented and
#                               so able to wake someone (#1228), or `unknown`
#   FLOW_MAILBOX_WATCHER_HOLDERS   each live watcher as
#                               `pid:start:parentage:mode`, comma-separated,
#                               or `-`
#   FLOW_MAILBOX_REARMED        yes | no | unknown
#
# `list --json` gains `watches[].watchers` (integer, or null when the process
# table could not be read) and `watches[].session_watchers` (integer, or null
# when unknown - #1228) beside `state` and `age_secs`, so a consumer can
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

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "FLOW_MAILBOX_EXIT=%d\n" "$?" >&2' EXIT

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
# Where Claude Code sessions expose their per-pid messaging socket - the same
# directory, and the same override, flow-wave-registry.sh uses for its
# self-address walk. A process that owns `<dir>/<pid>.sock` IS a session; see
# WAKEABILITY in the header for why that is the test (issue #1228).
SOCK_DIR="${FLOW_WAVE_SOCK_DIR:-/run/user/$UID_NUM/cc-socks}"

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

#: OUT-OF-BAND ACKNOWLEDGEMENT (#971, half one).
#:
#: `.ackob-<box>` records which acked revs were answered on ANOTHER CHANNEL
#: rather than read out of the box. It is a strict subset of `.ack-<box>`: an
#: out-of-band ack is still an ack, and this file only says HOW.
#:
#: WHY IT HAS TO EXIST BEFORE ESCALATION DOES. `/flow:wave` recommends lane 1
#: (SendMessage) as the fast path, so the ordinary healthy shape is an
#: orchestrator answering every message in real time while the durable copies sit
#: unacked. Measured in this wave: the orchestrator row read `route=UNCONFIRMED
#: unread=8` for most of a working session while it was replying to all of them.
#: An escalation keyed on `unconfirmed` would have fired spuriously, repeatedly,
#: all day, on a wave where nothing was wrong - a boy-who-cried-wolf by
#: construction, which is the failure the escalation exists to prevent, built
#: into the remedy for it.
#:
#: So answering elsewhere gets a verb. `ack --answered-elsewhere` records the
#: receipt AND the channel, which is what makes the later silence meaningful.
#: Resolve a wave ROLE to the address the registry holds for it (#971).
#: Read through the sibling registry's own `get`, never by parsing registry.json
#: here - two readers of one file drift, and the registry owns that shape.
registry_socket_for() {
  local reg out
  reg="$HOME/.claude/scripts/flow-wave-registry.sh"
  [ -x "$reg" ] || reg="$(dirname "$0")/flow-wave-registry.sh"
  [ -x "$reg" ] || return 0
  out="$(bash "$reg" get "$1" --wave "$WAVE" 2>/dev/null | awk -F= '/^FLOW_WAVE_SOCKET=/{print $2}')"
  case "$out" in unknown|"") return 0 ;; esac
  printf '%s' "$out"
}

#: Turn a transport address into the name SendMessage accepts (#971).
#:
#: The registry addresses roles by socket; SendMessage takes a ListAgents display
#: name. `~/.claude/sessions/` is keyed by PID and carries both, so the socket's
#: pid resolves to the name with no guessing. FAILS EMPTY rather than guessing:
#: display labels mutate mid-session and a send to a plausible neighbour returns
#: success against the WRONG session, which is worse than not escalating.
session_name_for_socket() {
  local addr="$1" pid rec
  case "$addr" in
    uds:*) pid="${addr##*/}"; pid="${pid%.sock}" ;;
    *) return 0 ;;
  esac
  case "$pid" in ''|*[!0-9]*) return 0 ;; esac
  rec="$HOME/.claude/sessions/$pid.json"
  [ -r "$rec" ] || return 0
  command -v jq >/dev/null 2>&1 || return 0
  #: EXACT EQUALITY, not mere presence. A pid-named record whose
  #: messagingSocketPath points somewhere else is a DIFFERENT session that
  #: happens to share a pid number - across a reboot, a namespace, or a reused
  #: pid. Returning its name would be precisely the plausible-neighbour send this
  #: function exists to refuse, dressed as a successful resolution.
  jq -r --arg want "$addr" \
    'if (.messagingSocketPath // "") == "" then ""
     elif ("uds:" + (.messagingSocketPath)) != $want then ""
     else (.name // "") end' "$rec" 2>/dev/null | grep -v '^$' || return 0
}

ackob_file() { echo "$WAVE_DIR/.ackob-$(basename "$1")"; }

ackob_add() {
  local box="$1"; shift
  local f rev
  f="$(ackob_file "$box")"
  for rev in "$@"; do
    grep -qx "$rev" "$f" 2>/dev/null || printf '%s\n' "$rev" >> "$f"
  done
}

ackob_count() {
  local f
  f="$(ackob_file "$1")"
  [ -s "$f" ] || { echo 0; return; }
  grep -c '^[0-9]' "$f" 2>/dev/null || echo 0
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
  ack_add "$b" $revs || return $?
  #: `--all-unacked --answered-elsewhere` must record the CHANNEL for the revs it
  #: acked, or the flag is silently ignored on the bulk path and the combination
  #: the header advertises does nothing. Recording a receipt while dropping how it
  #: was answered is the state #971 exists to remove.
  if [ "${ANSWERED_ELSEWHERE:-0}" -eq 1 ]; then
    # shellcheck disable=SC2086
    ackob_add "$b" $revs
  fi
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
oldest_unacked_rev() { # oldest_unacked_rev BOX
  #: The rev whose AGE oldest_unacked_ts measured - the OLDEST unacked message,
  #: not the highest rev. Taking the highest named a message that might be recent
  #: or already acknowledged as the overdue one, and let a new message reset
  #: deduplication while the genuinely stuck message sat there.
  #:
  #: A function because `escalate` must select it TWICE: once to decide, and
  #: again inside the lock to claim. Two copies of this awk would be two things
  #: to keep in step, and the claim silently disagreeing with the decision is
  #: precisely the defect the second selection exists to prevent.
  local f="$1"
  [ -s "$f" ] || return 0
  awk -v ackfile="$(ack_file "$f")" '
    BEGIN { while ((getline l < ackfile) > 0) if (l ~ /^[0-9]+$/) acked[l+0]=1; close(ackfile) }
    /^<!-- cc-flow-wave-msg / {
      r = 0; if (match($0, /rev=[0-9]+/)) r = substr($0, RSTART+4, RLENGTH-4) + 0
      if (r > 0 && !(r in acked)) print r
    }' "$f" | sort -n | head -1
}

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
  # shellcheck disable=SC2015  # intended: remove the temp file unless BOTH the write and the rename succeed (#972)
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

# armed | no-wake | stale | dead | absent | unknown for <role>, given that
# role's live watcher count (a non-negative integer, or `unknown`) and, as an
# optional third argument, how many of those are session-parented (integer or
# `unknown`, the default - which never produces `no-wake`; issue #1228). See the STATE table in
# the header for why the heartbeat alone cannot answer this (#801).
#
# The count is a PARAMETER rather than something looked up here, so `list` can
# tally every role from ONE pass over the process table instead of re-walking
# /proc once per role.
watch_state_of() {
  local role="$1" count="$2" sess="${3:-unknown}" age
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
    # Something IS polling. First: can it wake anyone (#1228)? A watcher with
    # no Claude Code session in its ancestry - a `supervise` daemon's inner
    # watch - polls, surfaces and refreshes the heartbeat forever while the
    # session it serves hears nothing. Only a CONFIRMED zero session watchers
    # says so; `unknown` parentage keeps the older reading, never a guess.
    case "$sess" in
      0) echo no-wake; return ;;
    esac
    # The stamp then distinguishes a healthy watch from a process that exists
    # but has stopped refreshing it.
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
    outbox-*.md) b="${b#outbox-}"; printf '%s\n' "${b%.md}" ;;
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

# --- The supervisor's SURFACED watermark (issues #867, #873) ------------------
#
# A supervisor must never acknowledge. An ack is a receipt, and #815 separated
# surfacing from receiving precisely so that one event could not stand in for
# the other; `supervise` re-joined them by arming `watch --consume`, so a
# detached daemon printing to a log recorded mail as RECEIVED by an agent that
# had not seen it. Measured on a live wave: 7 of 7 assignments acked, 0
# delivered (#873).
#
# So the daemon peeks. The obvious version of that spins - with `--peek`
# nothing moves, so the next arm re-fires on the same mail immediately - and
# the fix is a watermark that is the daemon's OWN, recording what it has
# SURFACED rather than what anybody has received.
#
# Three properties make this safe where the ack set would not be:
#
#   1. `route_state`, `unread`, and `** NEVER READ **` never consult it. They
#      read the ack set, which only an agent's explicit `ack` writes. So the
#      four deafness tells keep measuring what they claim to measure, which is
#      the whole of #867's acceptance.
#   2. It is PER BOX, not per role. Revs are allocated per box, so one global
#      high-water mark for a role reading several boxes (the orchestrator) would
#      silence a lower rev arriving later in a different box.
#   3. Losing it is harmless in the safe direction: an absent or torn file reads
#      as 0, which re-surfaces mail rather than hiding it. The failure mode is a
#      duplicate log line, never a silent drop.
surfaced_file() { echo "$WAVE_DIR/.supervise-$1.surfaced"; }

# The rev this supervisor has already surfaced for one box (0 when unknown).
surfaced_rev_for() {
  local sfile="$1" base="$2"
  [ -s "$sfile" ] || { echo 0; return; }
  awk -v b="$base" '$1 == b { r = $2 + 0 } END { print r + 0 }' "$sfile"
}

# Record that everything up to REV in BASE has been surfaced. Same lock and
# same write-to-temp-then-rename as ack_add, so a reader never sees a half file.
surfaced_set() {
  local sfile="$1" base="$2" rev="$3"
  (
    flock -w 10 9 || { echo "flow-wave-mailbox: could not lock $WAVE_DIR" >&2; exit 3; }
    tmp="$(mktemp "$WAVE_DIR/.msurf.XXXXXX")" || exit 3
    {
      [ -s "$sfile" ] && awk -v b="$base" '$1 != b' "$sfile"
      echo "$base $rev"
    } | sort -u > "$tmp"
    mv -f "$tmp" "$sfile" || { rm -f "$tmp"; exit 3; }
  ) 9>"$LOCK_FILE"
}

# Count unacked revs ABOVE this supervisor's watermark, across a role's boxes.
# Unacked AND above - both halves matter. Above-only would re-surface mail the
# agent has since acknowledged; unacked-only is the spin.
unread_above_for_role() {
  local role="$1" sfile="$2" total=0 b base w n
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    base="$(basename "$b")"
    w="$(surfaced_rev_for "$sfile" "$base")"
    n="$(unacked_revs_in "$b" | awk -v w="$w" '$1 + 0 > w' | grep -c '^[0-9]' || true)"
    total=$((total + n))
  done <<EOF
$(boxes_for_role "$role")
EOF
  echo "$total"
}

# Print what is above the watermark and raise it. NEVER touches the ack set -
# that is the property #867 and #873 both name as binding, and the reason this
# is a separate function rather than another flag on drain_role: there is no
# code path from here to ack_add to get wrong later.
drain_role_surfaced() {
  local role="$1" sfile="$2" b base w body top
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    base="$(basename "$b")"
    w="$(surfaced_rev_for "$sfile" "$base")"
    body="$(extract_since "$b" "$w")"
    if [ -n "$body" ]; then
      echo "=== $base (surfaced, NOT acknowledged) ==="
      echo "$body"
    fi
    top="$(max_rev "$b")"
    [ "$top" -gt "$w" ] && surfaced_set "$sfile" "$base" "$top"
  done <<EOF
$(boxes_for_role "$role")
EOF
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
  local role="$1" wave="$2" roles
  roles="$(watcher_roles_live "$wave")" || { echo unknown; return; }
  records_count "$roles" "$role"
}

# Each live-scan line is `<role> <pid>` (the pid was added for #1228 so a
# watcher's LINEAGE can be asked about, not only its existence). Roles are
# valid_name()-checked and cannot contain whitespace, so field 1 is exact -
# PROVIDED it is compared as a STRING. awk compares two numeric-looking values
# numerically, so a bare `$1 == r` makes roles `1` and `01` the same role; every
# role filter here concatenates `""` to force string identity, which is what
# the `grep -cxF` it replaced gave for free (counter-model review, #1228).
records_count() {
  printf '%s\n' "$1" | awk -v r="$2" '($1 "") == (r "") { n++ } END { print n + 0 }'
}

# proc_starttime PID -> the process's start time (clock ticks since boot, field
# 22 of /proc/<pid>/stat), or `-`. Paired with the pid it names ONE process
# instance: a pid alone is reused (every ~6.5h on this fleet), so "the session
# that armed me is gone" is only decidable as pid+start (issue #1228).
proc_starttime() {
  local pid="$1" stat rest
  case "$pid" in ''|*[!0-9]*) echo -; return ;; esac
  stat="$(cat "/proc/$pid/stat" 2>/dev/null)" || { echo -; return; }
  rest="${stat##*\) }"
  # shellcheck disable=SC2086
  set -- $rest
  if [ "$#" -ge 20 ]; then echo "${20}"; else echo -; fi
}

# is_session_pid PID -> 0 when PID is a Claude Code session. Test hook:
# FLOW_WAVE_SESSION_PIDS, a colon-separated pid list, is AUTHORITATIVE when set
# (even empty) - it replaces the socket probe entirely, so a suite asks the same
# question on a developer box (which has real sessions) and in CI (which has
# none). Without it the answer would depend on whether the suite happened to be
# launched from inside Claude Code: load-bearing locally, inert in CI.
is_session_pid() {
  if [ -n "${FLOW_WAVE_SESSION_PIDS+x}" ]; then
    case ":$FLOW_WAVE_SESSION_PIDS:" in *":$1:"*) return 0 ;; esac
    return 1
  fi
  [ -S "$SOCK_DIR/$1.sock" ]
}

# session_ancestor_of PID -> the pid of the nearest process in PID's ancestry
# (PID included) that is a Claude Code session, or `-` when the chain reaches
# init without one. Exit 1 = CANNOT TELL: no socket directory to test against
# (a host or harness with no session sockets), or the chain could not be read
# (a process exited mid-walk). Callers render that as `unknown` parentage,
# never as `orphan` - a missing instrument is not a finding (#800).
session_ancestor_of() {
  local pid="$1" hops=0 ppid
  if [ -z "${FLOW_WAVE_SESSION_PIDS+x}" ] && [ ! -d "$SOCK_DIR" ]; then
    return 1
  fi
  while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null && [ "$hops" -lt 64 ]; do
    if is_session_pid "$pid"; then echo "$pid"; return 0; fi
    ppid="$(awk '/^PPid:/{print $2}' "/proc/$pid/status" 2>/dev/null)"
    [ -n "$ppid" ] || return 1
    pid="$ppid"
    hops=$((hops + 1))
  done
  [ "$hops" -lt 64 ] || return 1
  echo -
}

# classify_records RECORDS -> one line per watcher:
#   <role> <pid> <session|orphan|unknown> <starttime|-> <consume|peek|unknown>
# The last field is the watcher's consumption mode, read from its real argv. It
# matters only for an orphan: one that PEEKS cannot take mail from anyone, one
# that CONSUMES acknowledges mail the session's own watch then never sees.
# `session` = a Claude Code session is in its ancestry, so its exit is what the
# harness re-invokes that session on. `orphan` = no session anywhere up the
# chain (a `supervise` daemon's inner watch, reparented to init or
# `systemd --user`): it can poll, surface and heartbeat, and it can never wake
# anyone. See WAKEABILITY in the header.
classify_records() {
  local role pid anc par
  printf '%s\n' "$1" | while read -r role pid _; do
    # shellcheck disable=SC2015  # intended: skip unless BOTH fields are present (#972)
    [ -n "$role" ] && [ -n "$pid" ] || continue
    if anc="$(session_ancestor_of "$pid")"; then
      if [ "$anc" = "-" ]; then par=orphan; else par=session; fi
    else
      par=unknown
    fi
    printf '%s %s %s %s %s\n' "$role" "$pid" "$par" "$(proc_starttime "$pid")" "$(watch_mode_of "$pid")"
  done
}

# watch_mode_of PID -> consume | peek | unknown, from /proc/<pid>/cmdline.
# Walks argv with the SAME option boundaries as this script's own parser, so an
# option VALUE is never read as a flag: `watch --consume --role --peek` is a
# consuming watch for role `--peek`, and a token scan would call it peeking and
# let it through the guard (counter-model review, #1228). Keep the value-taking
# list below in step with the parser's.
watch_mode_of() {
  local argv=() tok i=3 peek=0 consume=0
  [ -r "/proc/$1/cmdline" ] || { echo unknown; return; }
  while IFS= read -r -d '' tok; do argv+=("$tok"); done < "/proc/$1/cmdline" 2>/dev/null
  while [ "$i" -lt "${#argv[@]}" ]; do
    case "${argv[$i]}" in
      --wave|--role|--to|--from|--body|--body-file|--out|--timeout|--interval|--surfaced-state|--box|--revs)
        i=$((i + 1)) ;;
      --peek) peek=1 ;;
      --consume) consume=1 ;;
    esac
    i=$((i + 1))
  done
  if [ "$consume" -eq 1 ] && [ "$peek" -eq 0 ]; then echo consume
  elif [ "$peek" -eq 1 ] && [ "$consume" -eq 0 ]; then echo peek
  else echo unknown
  fi
}

# session_count_from CLASSIFIED ROLE -> how many of ROLE's watchers are
# session-parented, or `unknown` when ANY of them has unknown parentage. One
# unclassifiable watcher could be the session's own, so a zero counted around
# it would be a confident `no-wake` built on a gap.
session_count_from() {
  printf '%s\n' "$1" | awk -v r="$2" '
    ($1 "") == (r "") && $3 == "session" { s++ }
    ($1 "") == (r "") && $3 == "unknown" { u++ }
    END { if (u > 0) print "unknown"; else print s + 0 }'
}

# holders_of CLASSIFIED ROLE -> `pid:start:parentage:mode,...` for ROLE's watchers,
# or `-`. Every duplicate refusal names these (#1228): an anonymous "a watcher
# already holds this role" gave a worker told to re-arm no way to find, let
# alone judge, the process that was keeping it deaf.
holders_of() {
  local h
  h="$(printf '%s\n' "$1" | awk -v r="$2" '($1 "") == (r "") { printf "%s%s:%s:%s:%s", sep, $2, $4, $3, $5; sep = "," }')"
  echo "${h:--}"
}

# The ARM-GUARD view (formerly `count_watchers()`, inlined into `watch` by
# #1228 so it can read each holder's lineage): an unenumerable table fails OPEN
# to "no holders", because a wave that cannot start because its duplicate guard
# is unavailable is worse than an occasional false duplicate (#792 item 4).
# Reporting deliberately fails the other way - see watch_state_of.

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

# wave_root_of_pid PID -> the wave ROOT that process would resolve
# ($FLOW_WAVE_MAILBOX_DIR / $FLOW_WAVE_REGISTRY_DIR / $XDG_RUNTIME_DIR
# fallback, mirroring WAVE_ROOT's own precedence above - including that the
# first two are used AS-IS, with only the XDG/default branch getting a
# `/cc-flow-wave` suffix, since every test fixture sets
# FLOW_WAVE_MAILBOX_DIR directly to the wave root, not a directory above
# it). Read from that PID's OWN environment (/proc/<pid>/environ,
# NUL-separated - same idiom already used for /proc/<pid>/cmdline above),
# not this process's - two processes on the same host can have started
# with different overrides. Returns 1 - "cannot tell" - when environ is
# unreadable (permission, or the process already exited mid-scan); callers
# must treat that as "not a match", never as a match by default (issue
# #821 follow-up: see the header's IDENTITY section for why this exists).
wave_root_of_pid() {
  local pid="$1" entry env_mb="" env_reg="" env_xdg=""
  [ -r "/proc/$pid/environ" ] || return 1
  while IFS= read -r -d '' entry; do
    case "$entry" in
      FLOW_WAVE_MAILBOX_DIR=*)  env_mb="${entry#FLOW_WAVE_MAILBOX_DIR=}" ;;
      FLOW_WAVE_REGISTRY_DIR=*) env_reg="${entry#FLOW_WAVE_REGISTRY_DIR=}" ;;
      XDG_RUNTIME_DIR=*)        env_xdg="${entry#XDG_RUNTIME_DIR=}" ;;
    esac
  done < "/proc/$pid/environ" 2>/dev/null
  if [ -n "$env_mb" ]; then
    printf '%s' "$env_mb"
  elif [ -n "$env_reg" ]; then
    printf '%s' "$env_reg"
  elif [ -n "$env_xdg" ]; then
    printf '%s/cc-flow-wave' "$env_xdg"
  else
    printf '/run/user/%s/cc-flow-wave' "$UID_NUM"
  fi
}

watcher_roles_proc() {
  local wave="$1" pid seen=0
  local self_chain
  self_chain="$(self_chain_proc)"
  # This invocation's OWN resolved wave directory, canonicalized once (issue
  # #821 follow-up - see the header's IDENTITY section). $WAVE_DIR is always
  # "$WAVE_ROOT/$wave" for the $wave this function was called with - every
  # caller in this file threads the same --wave value through unchanged, so
  # there is no second wave root to derive here. `readlink -f` resolves
  # symlinks and returns a canonical string even for a path that no longer
  # exists (an orphan's original tmp dir may already be gone) - that string
  # is still exactly what a comparison needs.
  local this_wave_dir
  this_wave_dir="$(readlink -f "$WAVE_DIR" 2>/dev/null || printf '%s' "$WAVE_DIR")"
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
    local cand_root cand_wave_dir
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
    # The wave NAME matching above is a cheap pre-filter, not the decision
    # (issue #821 follow-up - see the header's IDENTITY section). Two
    # processes claiming the same wave name can be serving two entirely
    # different mailboxes - every test in this suite does exactly that, one
    # fresh tmp-path wave root per test, one wave name per test file. (That
    # name is per pytest invocation since #881/#882; it used to be the literal
    # "testwave", shared by every checkout on the host.)
    # The actual identity check is the resolved DIRECTORY: a candidate whose
    # own environment resolves to a different wave root than THIS invocation
    # is not the same wave, whatever it calls itself, and a candidate whose
    # environment cannot be read at all is excluded rather than guessed at.
    cand_root="$(wave_root_of_pid "$pid")" || continue
    cand_wave_dir="$(readlink -f "$cand_root/$found_wave" 2>/dev/null || printf '%s' "$cand_root/$found_wave")"
    [ "$cand_wave_dir" = "$this_wave_dir" ] || continue
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
    printf '%s %s\n' "$rrole" "$rpid"
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
#
# A NON-EMPTY match is a second, DIFFERENT case this lane also refuses to
# guess at, and it is not covered by the "over-counting is safe" paragraph
# above (issue #845). That paragraph is about a wrapper whose `-c` STRING
# merely contains the pattern as text - never a real watch invocation at
# all. This is about a match that IS a real, live `watch --role R --wave W`
# process - just possibly for a DIFFERENT mailbox. `--wave`/`--role` are
# name comparisons only; `FLOW_WAVE_MAILBOX_DIR` travels in the process's
# ENVIRONMENT, which `ps -eo args` cannot see and no portable non-/proc
# mechanism can read from another process, so nothing here can rule out two
# WATCHERS on one host with the same wave name and role but different
# mailbox directories, which is exactly the identity hole #821
# closed for `watcher_roles_proc()` via `wave_root_of_pid()`. That fix has
# no fallback-lane equivalent - there is no non-/proc way to read another
# process's environment - so this lane cannot verify what #821 verifies,
# and "safe to over-count" does not apply here: #821 already established
# that this SPECIFIC ambiguity is a real bug, not a tolerable one, for the
# /proc lane; nothing about running without /proc makes it less real. A
# match this lane cannot rule out is `unknown`, the same signal an
# unreadable `/proc/<pid>/environ` already produces one caller up
# (`wave_root_of_pid`'s own return-1 contract) - not a guessed count in
# either direction, and not silently treated as "0, nothing to see" either,
# which would be the opposite wrong answer (a live watcher reading `dead`).
#
# `unknown` now surfaces from THIS lane more often than before - worth
# saying plainly, because on its own that reads as a regression. It is not
# one: the two watcher_count consumers fail in DELIBERATELY OPPOSITE
# directions (see the block above watcher_roles_live), and this moves the
# failure OUT of the disfavoured one. Before this fix, a cross-mailbox
# match returned a wrong POSITIVE count, which the duplicate-arm guard
# would read as "already covered" and refuse to arm - deafness, the
# explicitly worse outcome. After it, the guard sees `unknown`, fails open,
# and arms - an occasional false duplicate at worst, the explicitly
# preferred outcome. The reporting consumer's higher `unknown` frequency is
# the visible cost of that trade, not an unrelated new weakness.
watcher_roles_ps_fallback() {
  local wave="$1" line pid ppid args rest found_role seen=0
  local self_chain matched_pids=" " records=() rec rpid rppid rrole surviving=()
  # Issue #904. `ps` truncates the `args` column to the OUTPUT WIDTH when stdout
  # is not a terminal, and inside tmux that width is the pane's - whatever `-x`
  # the session was spawned with. So a watcher's visibility is decided by the
  # product of two incidental facts: how long the checkout path is, and how wide
  # someone's terminal is. Measured: the same process rendered 121 bytes under
  # `ps -eo` and 1340 under `ps -eww -o`, and the cut landed mid-token in the
  # `--wave` value - the exact field this filter reads.
  #
  # The dangerous part is the DIRECTION. A truncated view matches nothing, so
  # `surviving` stays empty and the lane returns a confident ZERO rather than
  # `unknown`. `watch=DEAD(0 watchers)` is a blocker signal in /flow:wave, so a
  # live, correctly-armed worker reads as deaf. The guard that exists for
  # unverifiable matches is BYPASSED rather than triggered, because truncation
  # removes the very candidate that would have raised the ambiguity.
  #
  # `unreadable` below makes the DETECTABLE half of that reportable, and the
  # split is deliberate. Widening the `ps` invocation is a separate decision -
  # this lane exists for hosts without `/proc`, which is exactly the non-Linux
  # case where `-ww` semantics differ - and the reporting bug is independent of
  # the reading bug: even where the view cannot be widened, a lane that cannot
  # read the field must say so rather than answer zero.
  #
  # WHAT THIS DOES NOT CLOSE, stated because a half-fix that reads as a whole
  # one is worse than none. A cut landing BEFORE `flow-wave-mailbox.sh watch`
  # leaves a line this scan never recognises as watcher-shaped at all, so there
  # is nothing to flag and the lane still answers a confident zero. Only a cut
  # that lands AFTER the script name and role - severing or shortening the
  # `--wave` value - is caught here.
  #
  # A general truncation detector was tried and REMOVED: flagging the view when
  # two or more lines end at exactly the longest length fires on any ordinary
  # host where two processes happen to share their longest argv length, which
  # turned the confident `dead` verdict into a routine `unknown`. That is the
  # mirror of this defect and the issue is explicit that the fix must narrow
  # confidence only where an actual ambiguity exists. Detecting the general case
  # needs the view widened, which is the `-ww` decision, not this one.
  local unreadable=0
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
    # Past this point the line IS watcher-shaped, so anything we cannot read on
    # it is an ambiguity rather than a non-match. That distinction is the whole
    # fix: a field we could not read is not a field that said "not you".
    case "$args" in *" --role "*) rest="${args#*" --role "}" ;; *) unreadable=1; continue ;; esac
    found_role="${rest%% *}"
    [ -n "$found_role" ] || { unreadable=1; continue; }
    case "$args" in
      *"--wave $wave "*|*"--wave $wave") : ;;
      # A wave name that is a strict PREFIX of ours, with nothing after it, is
      # what a mid-token cut looks like: `--wave testwave-abc` clipped to
      # `--wave testwave-a`. Indistinguishable from a genuinely different wave
      # by content, so it is reported as undecidable rather than guessed at.
      *"--wave "*)
        rest="${args#*"--wave "}"
        rest="${rest%% *}"
        case "$wave" in
          "$rest"*) [ "$rest" = "$wave" ] || unreadable=1 ;;
        esac
        continue
        ;;
      # ISSUE #937 - DECIDED: `unreadable=1` STAYS. Two-sided call under ADR
      # 0009, escalated rather than settled by whoever hit the pain, and ruled
      # by the owner on 2026-09-16. Recorded here rather than in a PR body the
      # next person to touch this line will not read.
      #
      # The question was whether #904's `-ww` retires this conservatism: if
      # `ps` can no longer cut the argv, a missing `--wave` can only mean the
      # watcher passed none, and flagging it as unreadable is a mitigation
      # outliving its cause. THE PREMISE DOES NOT HOLD, and the reason is that
      # `-ww`'s protection and this lane's reachability are DISJOINT:
      #
      #   - `watcher_roles_live` picks this lane only when `[ -d /proc ]` is
      #     false. On every Linux host the /proc lane runs and this one is,
      #     in docs/scripts.md's own words, "dead code on Linux".
      #   - A host with no /proc is a host where `ps` is not procps-ng - and
      #     `-ww` (like the `--no-headers` in this very invocation, see the
      #     note below the loop) is a procps-ng guarantee. Where this lane
      #     actually runs, `-ww` guarantees nothing.
      #
      # So `-ww` retires the ambiguity only on the hosts where the branch
      # never executes. Measured 2026-09-16, one planted watcher
      # (`watch --role 9 --peek`, no `--wave`), same host, same instant, same
      # question about the NAMED wave `testwave-x`:
      #
      #   FLOW_WAVE_WATCHER_SCAN=auto (/proc)  ->  COUNT=0
      #   FLOW_WAVE_WATCHER_SCAN=ps (forced)   ->  COUNT=unknown
      #
      # The `unknown`-floods-the-fleet cost that argued for removal is paid
      # only on the forced lane. The fleet pays nothing, so removal buys
      # nothing real and spends a safety property.
      #
      # REVERSAL TRIGGER. Deliberately NOT the rate the issue proposed ("if
      # the ps lane reports unknown on more than some share of real arms") -
      # that keys on a population which is currently EMPTY, and a trigger that
      # cannot fire is the blind instrument one level up. Instead:
      #
      #   If this lane ever becomes reachable on a host that actually runs
      #   waves - `watcher_roles_live` selecting it WITHOUT
      #   `FLOW_WAVE_WATCHER_SCAN=ps` - measure, on real `/flow:wave` arms
      #   there, the share of `unknown` verdicts THIS BRANCH CAUSES. If that
      #   share is a meaningful fraction of arms, the conservatism is costing
      #   more than it protects and this comes back.
      #
      #   ATTRIBUTION IS PART OF THE TRIGGER, not a detail of measuring it
      #   (counter-model review, #937). The lane emits `unknown` from at least
      #   five places - this branch, a mid-token `--wave` cut, a missing
      #   `--role`, an empty `ps`, and #845's unverifiable-match guard - so a
      #   rate over the lane's unknowns AS A WHOLE cannot say which one is
      #   responsible, and #845's guard alone will produce unknowns on any
      #   host with a live watcher. A trigger keyed on that aggregate fires on
      #   a neighbour's signal and would move this setting on evidence about a
      #   different mechanism entirely.
      #
      #   The discriminator is an A/B on the setting itself: re-run the same
      #   queries with this `unreadable=1` deleted. The unknowns attributable
      #   here are exactly those that become a confident answer under that
      #   deletion; the rest were never this branch's doing and are evidence
      #   about mailbox-identity verification or scanner availability, which
      #   is a separate question with a separate home.
      #
      # THE ASYMMETRY IS DELIBERATE, and this is the other half of #937. A
      # missing `--wave` is read as a FACT in one direction (our wave is
      # `default`, so this line falls through as a match candidate) and as an
      # AMBIGUITY in the other (our wave is named, so it is `unreadable`).
      # That looks like an oversight. It is not, and the argument has two
      # parts: the directions carry OPPOSITE error costs, and what they
      # actually emit today is not what reading the branch suggests.
      #
      #   - Our wave is `default`: erring here OVER-counts. The header above
      #     states the standing policy - over-counting can only make a dead
      #     watch read `armed`, never a live one read `dead`.
      #   - Our wave is NAMED: erring here UNDER-counts, to a confident zero.
      #     `watch=DEAD(0 watchers)` is a blocker signal in /flow:wave, so a
      #     live worker reads as deaf. That is the direction #904 exists to
      #     stop.
      #
      # WHAT THE TWO DIRECTIONS ACTUALLY OUTPUT, measured rather than read off
      # the branch (2026-09-16, forced lane, one planted no-`--wave` watcher):
      #
      #   asking about the DEFAULT wave (falls through as a match) -> unknown
      #   asking about a NAMED wave     (this `unreadable=1`)      -> unknown
      #   no watcher-shaped line at all (the control)              -> 0
      #
      # They COINCIDE, by two different routes. The match route reaches
      # `unknown` through #845's guard below - `[ ${#surviving[@]} -eq 0 ] ||
      # return 1` - because this lane cannot verify that a genuine match is
      # OURS. Which means the lane is two-valued: it answers `0` or `unknown`
      # and can never return a positive count at all.
      #
      # So the asymmetry is a difference in ROUTE, not in answer, and the
      # behavioural stake sits entirely on the named-wave side: delete this
      # `unreadable=1` and that direction becomes a CONFIDENT ZERO, which is
      # #904's defect returning. That is what was weighed and kept.
      #
      # WHICH INVITES THE OBVIOUS TIDY-UP - "if both routes answer `unknown`,
      # make the branch unconditionally `unreadable=1` and the asymmetry
      # #937 complains about simply stops, for free." It is not free, and the
      # reason is worth writing down because the cost is invisible from here.
      #
      # The fall-through is what makes a default-wave no-`--wave` line a MATCH
      # CANDIDATE: it enters `matched_pids` and `records`, and takes part in
      # the subshell collapse below. It reaches `unknown` only because #845's
      # guard turns EVERY surviving match into `unknown` - this lane cannot
      # verify a match is ours. That guard is a statement about today's lane,
      # not a law. Give this lane a portable way to read another process's
      # mailbox directory and #845's guard lifts, at which point the two
      # spellings diverge: the fall-through yields a real count (correct - the
      # watcher IS a default-wave watcher), while an unconditional
      # `unreadable=1` still yields `unknown` (needlessly blind).
      #
      # The asymmetry is therefore FORWARD-COMPATIBLE and the symmetric
      # spelling silently depends on #845 staying put. Keeping it costs a
      # paragraph; removing it buys a tidier-looking branch and a coupling
      # nothing would announce when it breaks.
      #
      # The /proc lane differs here on the same input, and that is also
      # correct rather than an inconsistency to reconcile:
      # `/proc/<pid>/cmdline` is NUL-separated and cannot be truncated, so an
      # absent `--wave` there IS a fact, and `watcher_roles_proc` defaults
      # `found_wave=default` and treats a mismatch as a confident non-match.
      # One lane can read the field; the other cannot. Different evidence,
      # different confidence - not two implementations of one contract
      # drifting apart (#845 made exactly that correction already).
      #
      # BOTH directions are committed as cases, so neither can be changed
      # quietly: `test_a_watcher_shaped_line_with_no_wave_field_reads_unknown`
      # pins the named-wave ambiguity, and
      # `test_a_no_wave_watcher_on_the_default_wave_is_also_unknown` pins the
      # match route. Before #937 only the first existed, so a change making
      # this branch a confident zero on the default wave would have passed the
      # whole suite in silence - demonstrated, not assumed: that mutation reds
      # the new case alone (1 failed, 4 passed), deleting the named-wave
      # `unreadable=1` reds its sibling alone, and a bare `continue` reds both.
      # The second test's docstring carries the three mutations verbatim.
      *) [ "$wave" = "default" ] || { unreadable=1; continue ; } ;;
    esac
    matched_pids="$matched_pids$pid "
    records+=("$pid $ppid $found_role")
  done <<EOF
$(ps -ww -eo pid,ppid,args --no-headers 2>/dev/null)
EOF
  # -ww is load-bearing, not tidiness (issue #904). Without it `ps` caps every
  # line at the terminal width - or at \$COLUMNS, which is SET AND EXPORTED in a
  # Claude Code session (120 here). A watcher's argv carries the absolute path of
  # this script, so whether the `--role` and `--wave` fields survive the cut
  # depends on HOW LONG THE CHECKOUT PATH IS.
  #
  # Measured on this host, same moment, same processes:
  #   ps -eo pid,ppid,args --no-headers        max line 120, 2 watchers found
  #   ps -ww -eo pid,ppid,args --no-headers    max line 2576, 5 watchers found
  #
  # The failure direction is the dangerous one. A cut landing before `--role`
  # leaves a line this loop never recognises as watcher-shaped, so it `continue`s
  # - and the lane reports a CONFIDENT lower count rather than `unknown`. #917
  # reports `unknown` when the `--wave` field is unreadable, which cannot help
  # here: there is nothing left to flag. An armed worker reads as deaf, and
  # `watch=DEAD(0 watchers)` is a BLOCKER signal in /flow:wave's own hazards.
  #
  # -ww overrides \$COLUMNS outright, so the scan stops depending on the
  # environment it happens to run in. It widens no portability surface either:
  # `--no-headers` is already a procps-ng long option, absent from BSD, macOS and
  # busybox, so this invocation was procps-ng-only before -ww was added.
  #
  # NOT applied to the `ps -o ppid= -p <pid>` ancestry walk above. Measured:
  # that prints one ppid and is byte-identical at COLUMNS=20 with and without
  # -ww. It has no argv to widen and gains nothing.
  # `ps` always sees at least itself, so no output at all means it failed or is
  # absent - unknown, never zero (#801).
  [ "$seen" -eq 1 ] || return 1
  # Same forked-subshell collapse as the /proc lane.
  for rec in ${records+"${records[@]}"}; do
    rpid="${rec%% *}"; rrole="${rec##* }"
    rppid="${rec#* }"; rppid="${rppid%% *}"
    case "$matched_pids" in *" $rppid "*) continue ;; esac
    surviving+=("$rrole")
  done
  # A genuine (post-collapse) match cannot be verified as OURS - see the
  # header comment above (issue #845). Zero matches needs no such
  # verification (there is nothing to disambiguate), and stays a real,
  # confident empty result.
  [ "${#surviving[@]}" -eq 0 ] || return 1
  # ...but ONLY when the scan could actually see. "Scanned and matched nothing"
  # and "scanned a view that was cut" are different facts, and just one of them
  # justifies a zero (#904). Checked here rather than earlier so a real match
  # still outranks it: a verified watcher is a stronger statement than a
  # suspicion about the view that found it.
  [ "$unreadable" -eq 0 ] || return 1
  return 0
}

VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-wave-mailbox.sh send|read|watch|ack|escalate|supervise|list ..."
shift

case "$VERB" in
  send | read | watch | ack | escalate | supervise | __supervise_daemon | list) : ;;
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
SURFACED_STATE=""; REGISTRY_REQUIRED=0
TIMEOUT="$WATCH_TIMEOUT_DEFAULT"; INTERVAL="$WATCH_INTERVAL_DEFAULT"
A_BOX=""; A_REVS=""; ALL_UNACKED=0; ANSWERED_ELSEWHERE=0

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
    --surfaced-state) SURFACED_STATE="${2:-}"; shift ;;
    --status) STATUS=1 ;;
    --all) ALL=1 ;;
    --json) JSON_OUT=1 ;;
    --box) [ "$#" -ge 2 ] || usage_fail "--box requires a name"; A_BOX="$2"; shift ;;
    --box=*) A_BOX="${1#--box=}" ;;
    --revs) [ "$#" -ge 2 ] || usage_fail "--revs requires a comma- or space-separated list"; A_REVS="$2"; shift ;;
    --revs=*) A_REVS="${1#--revs=}" ;;
    --all-unacked) ALL_UNACKED=1 ;;
    --answered-elsewhere) ANSWERED_ELSEWHERE=1 ;;
    --registry-required) REGISTRY_REQUIRED=1 ;;
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
        # Surface CITATIONS on the DELIVERING path, not only on a refusal
        # (issue #980). A reserved token that is fenced or `>`-quoted is inert
        # by design - but "inert" and "dropped" produce the same silence, and
        # this is the only moment a sender sees the validator's answer at all:
        # LEX_OUT is discarded on exit 0, so without this a `GATE: HOLD` you
        # fenced but meant to ISSUE leaves with the message and is never
        # mentioned again. The skip is only safe because this line exists.
        LEX_CITED="$(printf '%s\n' "$LEX_OUT" | grep '^FLOW_LEXICON_CITATION=' || true)"
        if [ -n "$LEX_CITED" ]; then
          printf '%s\n' "$LEX_CITED" >&2
          echo "flow-wave-mailbox: NOTE - the line(s) above were read as CITATIONS, not transitions (issue #980). Delivering. If one was a transition you meant to ISSUE, it did NOT take effect: move it to column 0, outside any fence and with no '>' prefix, and re-send." >&2
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
      WSESS=unknown
      WHOLDERS=-
      if WRAW="$(watcher_roles_live "$WAVE")"; then
        WCOUNT="$(records_count "$WRAW" "$ROLE")"
        WCLASS="$(classify_records "$(printf '%s\n' "$WRAW" | awk -v r="$ROLE" '($1 "") == (r "")')")"
        WSESS="$(session_count_from "$WCLASS" "$ROLE")"
        WHOLDERS="$(holders_of "$WCLASS" "$ROLE")"
      else
        WCOUNT=unknown
      fi
      WSTATE="$(watch_state_of "$ROLE" "$WCOUNT" "$WSESS")"
      WAGE="$(watch_age "$ROLE")"
      if [ "$WAGE" = "-" ]; then WLAST="never armed"; else WLAST="last wake handled ${WAGE}s ago"; fi
      case "$WCOUNT" in
        ''|*[!0-9]*) REARMED=unknown; WLIVE="live watcher count UNKNOWN" ;;
        *)           WLIVE="$WCOUNT live watcher process(es)"
                     if [ "$WCOUNT" -gt 0 ]; then REARMED=yes; else REARMED=no; fi ;;
      esac
      echo "flow-wave-mailbox: role '$ROLE' wave '$WAVE': watch is $(printf '%s' "$WSTATE" | tr '[:lower:]' '[:upper:]') - $WLIVE, $WLAST; re-armed: $REARMED"
      case "$WSTATE" in
        dead)
          echo "flow-wave-mailbox: NOTHING is listening for role '$ROLE' - the heartbeat is only as fresh as the last wake, and a watch is one-shot (#801). Mail sent now will not wake anyone. Re-arm as a BACKGROUND call:"
          echo "  flow-wave-mailbox.sh watch --role $ROLE --wave $WAVE --timeout 1800 --consume"
          ;;
        absent)
          echo "flow-wave-mailbox: role '$ROLE' has NEVER armed a watch in wave '$WAVE' - it cannot be woken. Arm it as a BACKGROUND call:"
          echo "  flow-wave-mailbox.sh watch --role $ROLE --wave $WAVE --timeout 1800 --consume"
          ;;
        no-wake)
          echo "flow-wave-mailbox: role '$ROLE' is being POLLED but cannot be WOKEN - none of its $WCOUNT watcher(s) has a Claude Code session in its ancestry (holders: $WHOLDERS), so mail is noticed by a process no harness listens to (#1228). This is a \`supervise\` daemon, or a watch whose session is gone. From the session that owns this role, arm a watch as a BACKGROUND tool call (run_in_background, never a trailing &):"
          echo "  flow-wave-mailbox.sh watch --role $ROLE --wave $WAVE --timeout 1800 --consume"
          ;;
        stale)
          echo "flow-wave-mailbox: a watcher process exists for role '$ROLE' but its heartbeat has not refreshed in ${WAGE}s (poll interval is seconds) - it is hung or stopped, not merely between wakes." >&2
          ;;
        unknown)
          echo "flow-wave-mailbox: the process table could not be enumerated, so whether role '$ROLE' is listening is UNKNOWN - do NOT read this as armed (#801)." >&2
          ;;
      esac
      # A `supervise` daemon shuts down only when its NEXT registry check runs
      # release, and that check sits behind the current blocking watch call -
      # so shutdown lands within one `--timeout` of release, never instantly
      # (issue #1033 item 4). Surfacing the daemon's own timeout here lets a
      # reader compute that bound (`released Xs ago, timeout is N` -> still
      # legitimately armed for up to N-X more seconds) instead of having to
      # read argv by hand to tell "winding down" from "leaked".
      SUP_TIMEOUT_SEEN="$(cat "$WAVE_DIR/.supervise-$ROLE.timeout" 2>/dev/null || echo -)"
      case "$SUP_TIMEOUT_SEEN" in ''|*[!0-9]*) SUP_TIMEOUT_SEEN=- ;; esac
      E_ROLE="$ROLE"
      echo "FLOW_MAILBOX_WATCH_STATE=$WSTATE"
      echo "FLOW_MAILBOX_WATCH_AGE=$WAGE"
      echo "FLOW_MAILBOX_WATCHER_COUNT=$WCOUNT"
      echo "FLOW_MAILBOX_SESSION_WATCHERS=$WSESS"
      echo "FLOW_MAILBOX_WATCHER_HOLDERS=$WHOLDERS"
      echo "FLOW_MAILBOX_REARMED=$REARMED"
      echo "FLOW_MAILBOX_SUPERVISE_TIMEOUT=$SUP_TIMEOUT_SEEN"
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
    # --surfaced-state is the supervisor lane (#867/#873). It is refused with
    # --consume rather than ignored: the two express opposite intentions about
    # who may acknowledge, and silently honouring one while accepting the other
    # is how the defect being fixed here got in.
    if [ -n "$SURFACED_STATE" ] && [ "$PEEK" -eq 0 ]; then
      usage_fail "watch: --surfaced-state requires --peek (it exists so a watcher can wake on new mail WITHOUT acknowledging it - #867)"
    fi
    if [ "$PEEK" -eq 0 ] && [ "$CONSUME" -eq 0 ]; then
      usage_fail "watch requires an explicit --peek or --consume (issue #792) - silent default consumption has marked mail read that was never shown. Use --consume to arm-then-read (mail is marked read on wake), or --peek to read-then-arm (mail is NOT consumed, so re-arming immediately would spin-fire on it)."
    fi

    # #792 item 4: a role is single-owner by construction, so a second live
    # watcher on the same role+wave is always a mistake - it competes for the
    # same mail instead of getting a copy of it. Refuse rather than let
    # duplicates accumulate invisibly.
    #
    # #1228: the refusal is decided by holders that can WAKE someone. A holder
    # with no session in its ancestry (a `supervise` daemon's inner watch, or a
    # watch whose session died) never wakes anyone, so refusing the session's
    # own watch because of it is what kept sessions deaf after they tried to
    # re-arm: the role was "held" by the one process that could not deliver.
    # Such holders are named and the arm proceeds. A holder of UNKNOWN
    # parentage still refuses - it could be the session's own watch. So does an
    # orphan that CONSUMES (or whose mode is unreadable): it would acknowledge
    # mail before the session's watch saw it, leaving the session asleep behind
    # an `armed` roster (counter-model review, #1228) - only a PEEKING orphan,
    # which is what `supervise` runs, can safely coexist. An unenumerable table
    # still fails OPEN, exactly as before (#792 item 4).
    if DUP_RAW="$(watcher_roles_live "$WAVE")"; then
      DUP_CLASS="$(classify_records "$(printf '%s\n' "$DUP_RAW" | awk -v r="$ROLE" '($1 "") == (r "")')")"
    else
      DUP_CLASS=""
    fi
    EXISTING="$(records_count "$DUP_CLASS" "$ROLE")"
    WAKING="$(printf '%s\n' "$DUP_CLASS" | awk -v r="$ROLE" '($1 "") == (r "") && ($3 != "orphan" || $5 != "peek") { n++ } END { print n + 0 }')"
    if [ "$WAKING" -gt 0 ]; then
      E_ROLE="$ROLE"
      echo "flow-wave-mailbox: refusing to arm - $EXISTING live watcher(s) already hold role '$ROLE' in wave '$WAVE' (issue #792), $WAKING of them session-parented, of unknown parentage, or orphaned but CONSUMING (which would take this role's mail). Holders (pid:start:parentage:mode): $(holders_of "$DUP_CLASS" "$ROLE"). A role is single-owner: two watchers compete for the same mail rather than each seeing a copy. Check 'watch --status --role $ROLE --wave $WAVE' before starting another." >&2
      emit duplicate
      exit 4
    fi
    if [ "$EXISTING" -gt 0 ]; then
      echo "flow-wave-mailbox: arming anyway - $EXISTING watcher(s) already poll role '$ROLE' in wave '$WAVE', but NONE has a Claude Code session in its ancestry, so none can wake anyone (#1228); they only peek, so they cannot take this role's mail. Holders (pid:start:parentage:mode): $(holders_of "$DUP_CLASS" "$ROLE"). Kill them if they are yours and no longer wanted: kill \$pid \$(pgrep -P \$pid)." >&2
    fi

    WAITED=0
    FIRST_POLL=1
    while :; do
      # Stamp BEFORE the check, so an arm that fires on its very first poll -
      # mail already waiting - still leaves the trace #778 exists to leave.
      watch_stamp "$ROLE"
      if [ -n "$SURFACED_STATE" ]; then
        UNREAD="$(unread_above_for_role "$ROLE" "$SURFACED_STATE")"
      else
        UNREAD="$(unread_for_role "$ROLE")"
      fi
      if [ "$UNREAD" -gt 0 ]; then
        # #792 item 2: this fired on the very first poll, i.e. the mail was
        # already unread the instant this watch armed - not a fresh wake.
        # Say so up front rather than let it read as one.
        if [ "$FIRST_POLL" -eq 1 ]; then
          echo "flow-wave-mailbox: NOTE - mail was already unread when this watch armed; this is not a fresh wake (issue #792)."
        fi
        if [ -n "$SURFACED_STATE" ]; then
          drain_role_surfaced "$ROLE" "$SURFACED_STATE"
        else
          drain_role "$ROLE" "$PEEK" 0
        fi
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
        # An ARRAY, split by `read -a`, which does not glob (#972, counter-model
        # review). The old unquoted $REVLIST also pathname-expanded each token,
        # so `--revs '[1]'` became `1` whenever a file named `1` sat in the cwd,
        # and the validators below saw a revision nobody passed.
        REVS=()
        # `-d ''` reads to end of input, not to the first newline: a line-bounded
        # read dropped every rev after one, so `1,<newline>999` acked 1 and never
        # showed 999 to the all-or-nothing validator (counter-model review, pass 2).
        read -r -d '' -a REVS <<<"${A_REVS//,/ }" || true
        ack_add "$b" ${REVS[@]+"${REVS[@]}"} || exit $?
        # An out-of-band ack is still an ack; this only records the CHANNEL, so a
        # later `route=` reading can tell "answered on lane 1" from "never seen".
        [ "$ANSWERED_ELSEWHERE" -eq 1 ] && ackob_add "$b" ${REVS[@]+"${REVS[@]}"}
        N_GIVEN="$(printf '%s\n' ${REVS[@]+"${REVS[@]}"} | grep -c '[0-9]')"
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

  #: ESCALATE (#971). Convert an observation the wave already computes into a
  #: wake the agent can actually deliver.
  #:
  #: `route=unconfirmed` has existed since #778 and NOTHING acts on it. A worker
  #: can see its message has sat past the bound and has no verb that turns that
  #: into a turn on the other side. `supervise` cannot: a daemon printing into a
  #: log is not a recipient, and it cannot cause the agent behind it to take a
  #: turn. The only lane that wakes a session is cross-session SendMessage - and
  #: a reminder delivered by the channel that is already failing is not a reminder.
  #:
  #: THIS SCRIPT CANNOT SEND. SendMessage is a harness tool, not something a shell
  #: script can invoke. So the split is: the script owns RESOLUTION, which is the
  #: error-prone half - a registry socket is not an address SendMessage accepts,
  #: and the pid-keyed session record is what turns one into the other - and the
  #: AGENT owns the send, which only it can do. Printing a ready payload is the
  #: honest shape; pretending to deliver would be worse than not having the verb.
  #:
  #: TRIGGERS ON EVIDENCE, NEVER ON A TIMER. All three must hold: an unacked
  #: message exists, it is older than the bound, and this rev has not already been
  #: escalated. A periodic ping fires constantly on a healthy wave, and a signal
  #: that fires when nothing is wrong is how a signal dies. Dead-man-switch shape:
  #: silence PLUS outstanding work escalates; silence alone does not.
  escalate)
    [ -n "$ROLE" ] || usage_fail "escalate requires --role <role>"
    valid_name "$ROLE" || usage_fail "invalid role: '$ROLE'"
    TARGET="${A_TO:-orchestrator}"
    valid_name "$TARGET" || usage_fail "invalid --to role: '$TARGET'"
    BOX="$WAVE_DIR/inbox-$ROLE.md"
    BOUND="${FLOW_WAVE_ROUTE_UNCONFIRMED_SECS:-900}"
    NOW="${FLOW_WAVE_NOW:-$(date +%s)}"

    #: Every outcome carries WHAT IT EXAMINED, not only its verdict. "nothing to
    #: escalate" and "nothing to escalate, having examined 7 messages of which 7
    #: are acked" are different claims, and only the second can be told apart from
    #: a check that looked at nothing at all.
    MSG_N=0
    [ -s "$BOX" ] && MSG_N="$(grep -c '^<!-- cc-flow-wave-msg ' "$BOX" 2>/dev/null || echo 0)"
    echo "FLOW_MAILBOX_ESCALATE_EXAMINED=$MSG_N"
    if [ ! -s "$BOX" ]; then
      echo "FLOW_MAILBOX_ESCALATE=none"
      echo "flow-wave-mailbox: nothing to escalate - '$ROLE' has sent nothing to '$TARGET' in wave '$WAVE' (0 messages examined)."
      emit escalated; exit 0
    fi
    OLDEST_TS="$(oldest_unacked_ts "$BOX")"
    if [ -z "$OLDEST_TS" ]; then
      echo "FLOW_MAILBOX_ESCALATE=acked"
      echo "flow-wave-mailbox: nothing to escalate - all $MSG_N message(s) '$ROLE' sent to '$TARGET' are acknowledged."
      emit escalated; exit 0
    fi
    OLDEST_EPOCH="$(date -d "$OLDEST_TS" +%s 2>/dev/null || echo "")"
    if [ -z "$OLDEST_EPOCH" ]; then
      echo "FLOW_MAILBOX_ESCALATE=unknown"
      echo "flow-wave-mailbox: UNKNOWN - could not parse the send time '$OLDEST_TS', so age cannot be established. Not a pass." >&2
      emit error; exit 2
    fi
    AGE=$((NOW - OLDEST_EPOCH))
    if [ "$AGE" -lt "$BOUND" ]; then
      echo "FLOW_MAILBOX_ESCALATE=pending"
      echo "FLOW_MAILBOX_ESCALATE_AGE=$AGE"
      echo "flow-wave-mailbox: nothing to escalate - of $MSG_N message(s), the oldest unacked is ${AGE}s old, inside the ${BOUND}s bound."
      emit escalated; exit 0
    fi
    #: The rev reported must be the one whose AGE was measured - the oldest
    #: UNACKED message. Taking the highest rev instead named a message that might
    #: be recent, or already acknowledged, as the overdue one; and it let a new
    #: message reset deduplication while the genuinely stuck message sat there.
    ESC_REV="$(oldest_unacked_rev "$BOX")"
    [ -n "$ESC_REV" ] || { echo "FLOW_MAILBOX_ESCALATE=acked"; echo "flow-wave-mailbox: nothing unacked to escalate."; emit escalated; exit 0; }
    #: Emitted as soon as it is known, not only on the fire path: which rev was
    #: judged overdue is the fact a reader needs on EVERY outcome, including the
    #: ones that decline to wake anybody.
    echo "FLOW_MAILBOX_ESCALATE_REV=$ESC_REV"
    ESC_FILE="$WAVE_DIR/.esc-inbox-$ROLE.md"
    if grep -qx "$ESC_REV" "$ESC_FILE" 2>/dev/null; then
      echo "FLOW_MAILBOX_ESCALATE=already"
      echo "flow-wave-mailbox: already escalated for rev $ESC_REV - not escalating again. One wake per outstanding rev."
      emit escalated; exit 0
    fi

    #: Resolution FAILS LOUDLY. A socket with no matching session record must not
    #: fall back to name similarity: a send to a plausible neighbour returns
    #: success against the wrong session, which is worse than no escalation.
    ADDR="$(registry_socket_for "$TARGET")"
    if [ -z "$ADDR" ]; then
      echo "FLOW_MAILBOX_ESCALATE=unresolved"
      echo "flow-wave-mailbox: UNRESOLVED - '$TARGET' has no address in the registry, so there is nobody to wake." >&2
      emit error; exit 3
    fi
    NAME="$(session_name_for_socket "$ADDR")"
    if [ -z "$NAME" ]; then
      echo "FLOW_MAILBOX_ESCALATE=unresolved"
      echo "flow-wave-mailbox: UNRESOLVED - no session record matches $ADDR." >&2
      echo "flow-wave-mailbox: REFUSING to guess a name. A send to a plausible neighbour succeeds against the WRONG session." >&2
      emit error; exit 3
    fi

    #: CLAIMED UNDER THE LOCK, and re-validated inside it. Two callers could both
    #: pass the membership test above and both emit `fire`, which is two wakes for
    #: one outstanding message - the periodic ping this verb exists to avoid.
    #: RE-DERIVED INSIDE THE LOCK, not merely re-checked for deduplication.
    #: Every read above happened without the lock, so between deciding and
    #: claiming, an `ack` can clear the rev or a `send --replace` can replace it -
    #: and the old code would still fire, waking somebody about a message that is
    #: answered or gone. Worse, age and rev were selected in two separate passes,
    #: so an ack landing between them could pin an OLD message's age onto a
    #: RECENT rev and report it overdue when it was not. Selecting both together,
    #: under the lock, is what makes the claim describe the state that holds at
    #: claim time rather than the state that held when we started looking.
    ESC_CLAIM="${TMPDIR:-/tmp}/flow-esc-claim.$$"
    # CHAINED, NOT REPLACED (issue #1031): a bare `trap ... EXIT` here would
    # silently discard the FLOW_MAILBOX_EXIT= line installed at the top of this file,
    # and nothing would report its absence. $? is captured FIRST, before the
    # cleanup runs, or the reported status becomes `rm`'s.
    # shellcheck disable=SC2154  # _rc is assigned inside the trap string itself (#972)
    trap '_rc=$?; rm -f "$ESC_CLAIM"; printf "FLOW_MAILBOX_EXIT=%d\n" "$_rc" >&2' EXIT
    trap 'rm -f "$ESC_CLAIM"' INT TERM
    (
      flock -w 10 9 || { echo "flow-wave-mailbox: could not lock $WAVE_DIR" >&2; exit 3; }
      _ts="$(oldest_unacked_ts "$BOX")"
      [ -n "$_ts" ] || exit 5
      _rev="$(oldest_unacked_rev "$BOX")"
      [ -n "$_rev" ] || exit 5
      _ep="$(date -d "$_ts" +%s 2>/dev/null || echo "")"
      [ -n "$_ep" ] || exit 2
      _age=$((NOW - _ep))
      [ "$_age" -ge "$BOUND" ] || exit 6
      grep -qx "$_rev" "$ESC_FILE" 2>/dev/null && exit 4
      printf '%s\n' "$_rev" >> "$ESC_FILE"
      printf '%s %s\n' "$_rev" "$_age" > "$ESC_CLAIM"
    ) 9>"$LOCK_FILE"
    case "$?" in
      0) ESC_CLAIMED="$(cut -d' ' -f1 "$ESC_CLAIM")"
         AGE="$(cut -d' ' -f2 "$ESC_CLAIM")"
         #: The REV line above was emitted before the lock, so if the state moved
         #: under us the CLAIMED rev is the authoritative one. Re-emit it rather
         #: than leave a reader parsing a value we have since superseded.
         [ "$ESC_CLAIMED" = "$ESC_REV" ] || echo "FLOW_MAILBOX_ESCALATE_REV=$ESC_CLAIMED"
         ESC_REV="$ESC_CLAIMED" ;;
      4) echo "FLOW_MAILBOX_ESCALATE=already"
         echo "flow-wave-mailbox: another caller claimed rev $ESC_REV first - one wake per outstanding rev."
         emit escalated; exit 0 ;;
      5) echo "FLOW_MAILBOX_ESCALATE=acked"
         echo "flow-wave-mailbox: nothing to escalate - rev $ESC_REV was acknowledged while this check was running."
         emit escalated; exit 0 ;;
      6) echo "FLOW_MAILBOX_ESCALATE=pending"
         echo "flow-wave-mailbox: nothing to escalate - the oldest unacked message is inside the ${BOUND}s bound as of the claim."
         emit escalated; exit 0 ;;
      *) echo "FLOW_MAILBOX_ESCALATE=unknown"
         echo "flow-wave-mailbox: UNKNOWN - could not claim the escalation record; not reporting a wake that may not be recorded." >&2
         emit error; exit 2 ;;
    esac
    echo "FLOW_MAILBOX_ESCALATE=fire"
    echo "FLOW_MAILBOX_ESCALATE_AGE=$AGE"
    echo "FLOW_MAILBOX_ESCALATE_TARGET=$NAME"
    echo "flow-wave-mailbox: ESCALATE - send this over lane 1 now (this script cannot send):"
    echo "---"
    echo "SendMessage to: $NAME"
    echo "$TARGET: rev $ESC_REV from '$ROLE' has been unacknowledged for ${AGE}s (bound ${BOUND}s) in wave '$WAVE'."
    echo "This is an automated escalation from flow-wave-mailbox, fired on evidence: an unacked message older than the bound, not previously escalated."
    #: THE ACK NAMES THE READER OF THE BOX, NOT THE ESCALATION TARGET (Codex
    #: pass 2). The durable copy lives in `inbox-$ROLE.md`, and by construction
    #: the orchestrator is the role that reads every inbox-*.md - whoever we
    #: happened to WAKE does not change that. Interpolating $TARGET here broke
    #: `escalate --to <anyone-else>`: `ack` accepts `--from` only for the
    #: orchestrator, so the printed command was rejected outright (exit 2). It
    #: fails loudly, which is the good case - but a reader who pastes it gets an
    #: error instead of an ack, and the message stays unacked. An instruction
    #: that does not work is worse than no instruction, because the escalation
    #: reports the loop closed while the durable copy is still outstanding.
    #:
    #: `--from $ROLE` is still REQUIRED: the orchestrator has many boxes and
    #: `ack` refuses to guess which.
    echo "If you answered on lane 1, ack the durable copy with: flow-wave-mailbox.sh ack --role orchestrator --wave $WAVE --from $ROLE --revs $ESC_REV --answered-elsewhere"
    [ "$TARGET" = "orchestrator" ] || echo "(that ack is the orchestrator's to run - '$TARGET' was woken, but only the orchestrator reads inbox-$ROLE.md)"
    echo "---"
    emit escalated
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

    # --registry-required (issue #1107): the caller KNOWS this wave is tracked
    # by the registry, so a wave with nothing ever registered in it is a
    # misconfiguration (a --wave typo, or supervise launched before register)
    # rather than #814's legitimate registry-optional use. Without the flag
    # that reading is impossible - the two are observationally identical from
    # here - which is why it is an explicit opt-in and never a default.
    #
    # Checked at LAUNCH, not in the daemon. The daemon is detached and cannot
    # wake anyone (#1228), so an exit it logged would reach nobody; a refusal
    # here is a non-zero exit the caller sees in the same call. It runs before
    # the lock is taken, so a refused launch leaves no lock, pidfile or log.
    #
    # Only the AFFIRMATIVE `no-roles-registered` is `misconfigured`. A wave
    # whose roles all ended is the #1095 case and launches normally (the
    # daemon then exits `no-roles-ended` on its own); `yes` launches. Anything
    # the registry could not answer - sibling missing, corrupt file, no
    # verdict line - is `unverified`, a separate word and exit code: the
    # caller asked for the registry to be a precondition, and a precondition
    # that could not be checked is not one that held.
    if [ "$REGISTRY_REQUIRED" -eq 1 ]; then
      E_ROLE="$ROLE"
      REQ_REGISTRY="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")/flow-wave-registry.sh"
      REQ_ANY_LIVE=""
      if [ -r "$REQ_REGISTRY" ]; then
        REQ_ANY_LIVE="$(bash "$REQ_REGISTRY" list --wave "$WAVE" --any-live 2>/dev/null | sed -n 's/^FLOW_WAVE_ANY_LIVE=//p')"
      fi
      case "$REQ_ANY_LIVE" in
        yes | no-roles-ended) : ;;
        no-roles-registered)
          echo "flow-wave-mailbox: refusing to supervise - --registry-required was given, but no role has ever been registered in wave '$WAVE' (issue #1107). Check the --wave spelling, or register first: flow-wave-registry.sh register $ROLE --wave $WAVE. Nothing was started." >&2
          emit misconfigured
          exit 7
          ;;
        *)
          echo "flow-wave-mailbox: refusing to supervise - --registry-required was given, but the registry could not answer for wave '$WAVE' (verdict: '${REQ_ANY_LIVE:-none}', registry: $REQ_REGISTRY) (issue #1107). This is NOT a finding that the wave is empty. Nothing was started." >&2
          emit unverified
          exit 8
          ;;
      esac
    fi

    SUP_LOCK="$WAVE_DIR/.supervise-$ROLE.lock"
    SUP_PIDFILE="$WAVE_DIR/.supervise-$ROLE.pid"
    SUP_LOG="$WAVE_DIR/.supervise-$ROLE.log"
    SUP_TIMEOUT_FILE="$WAVE_DIR/.supervise-$ROLE.timeout"

    # Resolved to an ABSOLUTE path ONCE, here, while the invoking cwd is
    # certainly still valid - not left as the raw (possibly relative) `$0`
    # for the daemon to re-resolve later (issue #1033 item 2). A worktree
    # removed out from under a long-lived daemon invalidates its cwd, and a
    # relative `$0` re-evaluated after that points nowhere: two
    # `__supervise_daemon` processes were found pinned at `rc=127` for
    # 13h48m this way, because the daemon's own re-arm (`bash "$0" watch
    # ...`) silently depended on a cwd that no longer existed. `$0` itself
    # does not change after a process starts, so resolving it once here and
    # handing the daemon the absolute form makes every later use inside
    # `__supervise_daemon` - the re-arm loop included - immune to the
    # invoking cwd's fate for the rest of the daemon's life.
    SUP_SELF="$(readlink -f "$0" 2>/dev/null || echo "$0")"

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
      # Name what is actually known, not a guess dressed as one (issue
      # #1033 item 1): the lock is what refused this, and `$SUP_PIDFILE` is
      # diagnostic-only, so say plainly that it may be stale rather than
      # implying it is the authoritative holder.
      HOLDER_PID="$(cat "$SUP_PIDFILE" 2>/dev/null || echo '-')"
      echo "flow-wave-mailbox: refusing to supervise - the lifetime lock for role '$ROLE' in wave '$WAVE' is currently held (issue #814); a live supervisor's last recorded PID here was $HOLDER_PID ($SUP_PIDFILE), but that file is diagnostic only and may be stale - the lock, never the file, is what decided this refusal. See $SUP_LOG for evidence. If you need to kill the holder, kill its children too (\`kill \$pid \$(pgrep -P \"\$pid\")\`): an orphaned child of a killed daemon can inherit and keep holding this same lock." >&2
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
    # The ARMING SESSION (issue #1228): the nearest Claude Code session in this
    # invocation's ancestry, as pid:start. The daemon exits `owner-gone` once
    # that exact process instance is gone - the case that happened in the
    # field (a daemon polling 18h after its session died, its role never
    # released), and one with none of the ambiguity #814 guards against:
    # "the session that armed me is dead" is never a legitimate reason to keep
    # polling for it. No session in the ancestry (standalone use, not launched
    # from Claude Code) means no owner, and behaviour is unchanged.
    SUP_OWNER=""
    if SUP_OWNER_PID="$(session_ancestor_of "$$")" && [ "$SUP_OWNER_PID" != "-" ]; then
      SUP_OWNER="$SUP_OWNER_PID:$(proc_starttime "$SUP_OWNER_PID")"
    fi
    export FLOW_WAVE_SUPERVISE_OWNER="$SUP_OWNER"
    if command -v setsid >/dev/null 2>&1; then
      setsid bash "$SUP_SELF" __supervise_daemon --role "$ROLE" --wave "$WAVE" \
        --timeout "$TIMEOUT" --interval "$INTERVAL" >>"$SUP_LOG" 2>&1 &
    else
      bash "$SUP_SELF" __supervise_daemon --role "$ROLE" --wave "$WAVE" \
        --timeout "$TIMEOUT" --interval "$INTERVAL" >>"$SUP_LOG" 2>&1 &
    fi
    DAEMON_PID=$!
    disown 2>/dev/null || true
    # Diagnostics only - who a human should look at - never the liveness
    # test itself (that is the flock, above).
    echo "$DAEMON_PID" > "$SUP_PIDFILE" 2>/dev/null || true
    # Diagnostic only, same category as the pidfile (issue #1033 item 4): lets
    # `watch --status` distinguish "winding down" from "leaked" by computing
    # how much of this daemon's own re-arm timeout remains after a release,
    # rather than a reader having to inspect argv by hand.
    echo "$TIMEOUT" > "$SUP_TIMEOUT_FILE" 2>/dev/null || true
    E_ROLE="$ROLE"
    echo "flow-wave-mailbox: supervising role '$ROLE' in wave '$WAVE' as PID $DAEMON_PID (issue #814) - it re-arms watch continuously until role release, the wave ends, or its arming session (${SUP_OWNER:-none found}) exits; see $SUP_LOG for sanitized evidence (timestamps and exit codes only, never message bodies)." >&2
    echo "flow-wave-mailbox: NOTE - this daemon is DETACHED, so it can NEVER wake a session: the harness re-invokes a session only when a process that session owns exits (#868, #1228). The roster reads this role as no-wake until the session arms its own background watch." >&2
    emit supervising
    exit 0
    ;;

  __supervise_daemon)
    # INTERNAL. Launched by `supervise` above via setsid; never invoke this
    # directly. Runs until role release, an unreadable registry sibling that
    # stops looking free, or a TERM/INT signal - its own exit is what
    # releases the lifetime flock `supervise` opened and handed it.
    [ -n "$ROLE" ] || usage_fail "__supervise_daemon requires --role <role>"
    # `$0` here is already the ABSOLUTE `$SUP_SELF` the `supervise` case
    # resolved before launching this daemon (issue #1033 item 2) - `$0` never
    # changes after a process starts, so this `readlink -f` is a defensive
    # no-op, not the resolution itself. The re-arm loop below reuses `$0` for
    # exactly this reason: it is immune to the invoking cwd going away for
    # the rest of this daemon's life, unlike a fresh relative-path lookup
    # would be.
    SUP_LOG_SELF_DIR="$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")"
    SUP_REGISTRY="$SUP_LOG_SELF_DIR/flow-wave-registry.sh"
    BACKOFF_BASE="${FLOW_WAVE_SUPERVISE_BACKOFF_BASE:-2}"
    BACKOFF_CAP="${FLOW_WAVE_SUPERVISE_BACKOFF_CAP:-60}"
    BACKOFF=0
    # A cap reached is normal (a persistent-but-transient outage). A cap
    # reached with the SAME rc, cycle after cycle, is not: nothing about
    # retrying again changes the input that keeps producing it, so it cannot
    # self-heal by waiting longer (issue #1033 item 2 - the #900-relative-$0
    # incident's own symptom, rc=127 pinned at the cap for 13h48m, is exactly
    # this shape). Terminal only after several consecutive identical-rc
    # cycles AT the cap, never on the first - a single cap hit is still the
    # ordinary "persistently failing cause" case #814 already handles by
    # backing off, not a reason to shut down.
    LAST_INNER_RC=""
    CAP_STREAK=0
    TERMINAL_CAP_STREAK="${FLOW_WAVE_SUPERVISE_TERMINAL_STREAK:-3}"
    # This daemon's own record of what it has SURFACED (#867/#873) - never a
    # receipt, and never read by anything that reports on deafness. It exists
    # only so a non-consuming watch does not re-fire on the same mail forever.
    SUP_SURFACED="$(surfaced_file "$ROLE")"

    # Structured, sanitized evidence ONLY - a timestamp and a short event
    # description (event kind, exit code, backoff seconds). NEVER message
    # bodies: the inner `watch` child's stdout, which DOES carry bodies on
    # delivery, is discarded below (redirected to /dev/null), not relayed
    # into this log or anywhere else - the daemon's job is re-arming, not
    # reading (issue #814).
    log_event() {
      printf '%s %s\n' "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)" "$*"
    }

    SUP_OWNER="${FLOW_WAVE_SUPERVISE_OWNER:-}"
    log_event "daemon started role=$ROLE wave=$WAVE pid=$$ timeout=$TIMEOUT interval=$INTERVAL owner=${SUP_OWNER:-none}"
    trap 'log_event "daemon exiting on signal"; exit 0' TERM INT

    while :; do
      # Owner check (issue #1228), FIRST: it needs no registry and no wave -
      # only the process instance recorded at launch. A reused pid is a
      # different start time, so it reads gone, not alive. An owner whose
      # start time could not be read at launch (`-`) is judged on the pid
      # alone, which can only err toward staying up.
      if [ -n "$SUP_OWNER" ]; then
        OWN_PID="${SUP_OWNER%%:*}"
        OWN_START="${SUP_OWNER#*:}"
        OWN_NOW="$(proc_starttime "$OWN_PID")"
        # A ZOMBIE has exited and merely awaits reaping: its /proc entry and
        # start time survive, so the two tests below would call it alive
        # (counter-model review, #1228). Its state letter says otherwise.
        OWN_STATE="$(sed -n 's/^State:[[:space:]]*\([A-Z]\).*/\1/p' "/proc/$OWN_PID/status" 2>/dev/null)"
        if [ ! -d "/proc/$OWN_PID" ] || [ "$OWN_STATE" = "Z" ] || [ "$OWN_STATE" = "X" ] ||
           { [ "$OWN_START" != "-" ] && [ "$OWN_NOW" != "-" ] && [ "$OWN_NOW" != "$OWN_START" ]; }; then
          log_event "daemon exiting: owner-gone (arming session $SUP_OWNER is no longer running)"
          exit 0
        fi
      fi
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

        # issue #1095: the check above answers "was MY OWN role explicitly
        # released" - it says nothing about whether anyone is still left in
        # the WAVE this role belongs to. `release` is a step a session takes
        # deliberately; nothing forces it once there is no one left to hand
        # this role work, so a supervisor can outlive its entire wave and
        # poll forever, a real daemon holding its lifetime flock with
        # nothing left to supervise. Ask the wave as a whole.
        #
        # GATED ON THIS ROLE ITSELF BEING REGISTERED (`$REL_LIVENESS` is not
        # `-`, `get`'s sentinel for "no entry at all"), and deliberately so:
        # "this role was never registered" is `get`'s `free` verdict, which
        # the check above already documents as a LEGITIMATE, independent way
        # to use `supervise` - the registry is an optional companion, not a
        # dependency (#814's own boundary, ratified before #1095 and not
        # renegotiated here). A wave-wide check that ran unconditionally
        # could not tell "this session deliberately never uses the
        # registry" apart from "this session's --wave is a typo" - both
        # look IDENTICAL from here, an empty wave and a free role - and
        # #814 already settled which of those two readings wins. Measured
        # directly: every existing supervise-without-registry test in this
        # suite broke the instant this check ran unconditionally.
        #
        # Only `no-roles-ended` is handled here. `--any-live`'s other two
        # non-`yes` answers correctly fall through to "keep supervising":
        # `undeterminable` (matches the release check's own fail-open, and
        # `list --any-live` has its own committed cases in
        # tests/test_flow_wave_registry.py), and `no-roles-registered` -
        # which, reached from THIS gate, would mean this role's own entry
        # vanished in the instant between the `get` above and the `list`
        # below. That is indistinguishable from "the registry was just
        # wiped", and once wiped, `get` reads `-` again on the very next
        # cycle - back to the exact state #814 says must not shut this
        # daemon down. There is no cycle in which `no-roles-registered`
        # would fire and be the CORRECT call once this gate is in place; it
        # is not wired to an exit here for that reason, not by oversight.
        # The broader "wrong --wave id, never registered at all" case #1095
        # also named is `supervise --registry-required` (issue #1107), checked
        # once at LAUNCH above - an explicit opt-in, not a default this daemon
        # could infer safely, and a refusal the caller sees rather than a log
        # line from a detached process.
        if [ "$REL_LIVENESS" != "-" ]; then
          WAVE_ANY_LIVE="$(bash "$SUP_REGISTRY" list --wave "$WAVE" --any-live 2>/dev/null | sed -n 's/^FLOW_WAVE_ANY_LIVE=//p')"
          if [ "$WAVE_ANY_LIVE" = "no-roles-ended" ]; then
            log_event "wave has no live roles left (every registered role has ended) - shutting down"
            exit 0
          fi
        fi
      fi

      # --peek, never --consume (#867, #873). A detached daemon printing to a
      # log is not a recipient, so it must not write the receipt. The watermark
      # below is what keeps a non-consuming watch from re-firing on the same
      # mail forever; it is the daemon's own record of what it SURFACED and
      # nothing that reports on deafness ever reads it.
      #
      # `8>&-` closes THIS subprocess's inherited copy of the lifetime flock
      # (issue #1033 item 1). Without it, a SIGKILL of this daemon leaves
      # whatever this child currently is - reparented to init - still holding
      # fd 8 until IT exits on its own, so a new `supervise` refuses as
      # `duplicate` against a lock the daemon that held it is already dead.
      # Verified directly: SIGKILL the daemon, then attempt a new `supervise`
      # immediately - with this line, it succeeds at once, WITH the orphaned
      # child still alive in the process table; the orphan no longer matters
      # because it no longer holds anything.
      bash "$0" watch --role "$ROLE" --wave "$WAVE" --peek \
        --surfaced-state "$SUP_SURFACED" \
        --timeout "$TIMEOUT" --interval "$INTERVAL" >/dev/null 2>&1 8>&-
      INNER_RC=$?

      case "$INNER_RC" in
        0)
          # SURFACED, not delivered and not acknowledged. The old wording here
          # said "delivered rc=0", which meant only that the inner watch exited
          # zero - i.e. that a print succeeded - and an orchestrator reading
          # this log took it for evidence a model had read something (#873).
          # It is not, it never was, and the log now says which fact it holds.
          log_event "surfaced rc=0 (NOT acknowledged - mail stays unread until the agent acks it)"
          BACKOFF=0
          LAST_INNER_RC=""
          CAP_STREAK=0
          ;;
        5)
          # A plain, expected timeout - the daemon re-arms silently, this is
          # the normal steady state of a persistent listener.
          BACKOFF=0
          LAST_INNER_RC=""
          CAP_STREAK=0
          ;;
        *)
          # Anything else is a crash-class exit (killed, duplicate-refused
          # against something outside this daemon's own control, or an
          # error). Exponential backoff, capped, so a persistently failing
          # cause cannot spin this loop at full speed forever (issue #814's
          # explicit "no tight restart loop" requirement).
          if [ "$BACKOFF" -eq 0 ]; then BACKOFF="$BACKOFF_BASE"; else BACKOFF=$((BACKOFF * 2)); fi
          [ "$BACKOFF" -gt "$BACKOFF_CAP" ] && BACKOFF="$BACKOFF_CAP"
          if [ "$BACKOFF" -eq "$BACKOFF_CAP" ] && [ "$INNER_RC" = "$LAST_INNER_RC" ]; then
            CAP_STREAK=$((CAP_STREAK + 1))
          else
            CAP_STREAK=0
          fi
          LAST_INNER_RC="$INNER_RC"
          log_event "inner watch exited rc=$INNER_RC - backing off ${BACKOFF}s"
          # issue #1033 item 2 (behaviour change, deliberate): a cap reached
          # with a CONSTANT rc means retrying again cannot change the
          # outcome - the #900-relative-$0 incident's own symptom (rc=127,
          # pinned at the cap, for 13h48m) is exactly this shape, and this
          # daemon used to retry it forever. Terminal ONLY after several
          # consecutive identical-rc cycles at the cap; a single cap hit, or
          # a cap hit whose rc keeps changing, still just backs off as
          # before. Exiting is what releases the flock - a caller relying on
          # this daemon retrying forever through a transient outage will now
          # see it stop instead, which is the intended trade: an inner cause
          # this daemon cannot fix should not be supervised forever in
          # silence.
          if [ "$CAP_STREAK" -ge "$TERMINAL_CAP_STREAK" ]; then
            log_event "inner watch pinned at the backoff cap with a constant rc=$INNER_RC for $CAP_STREAK consecutive cycles - this cannot self-heal, shutting down"
            exit 0
          fi
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
    # Lineage, classified once for the whole table (#1228) - see WAKEABILITY.
    LIVE_CLASS=""
    [ "$LIVE_OK" -eq 1 ] && LIVE_CLASS="$(classify_records "$LIVE_ROLES")"
    watchers_for() {
      [ "$LIVE_OK" -eq 1 ] || { echo unknown; return; }
      records_count "$LIVE_ROLES" "$1"
    }
    session_watchers_for() {
      [ "$LIVE_OK" -eq 1 ] || { echo unknown; return; }
      session_count_from "$LIVE_CLASS" "$1"
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
        wsc="$(session_watchers_for "$wr")"
        case "$wsc" in ''|*[!0-9]*) wsc_json=null ;; *) wsc_json="$wsc" ;; esac
        WATCHES="$WATCHES$(printf '{"role":"%s","state":"%s","age_secs":%s,"watchers":%s,"session_watchers":%s}' \
          "$wr" "$(watch_state_of "$wr" "$wc" "$wsc")" "$wa_json" "$wc_json" "$wsc_json"),"
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
          ws="$(watch_state_of "$wr" "$wc" "$(session_watchers_for "$wr")")"
          case "$ws" in
            dead|absent|no-wake) DEAF_ROLES="$DEAF_ROLES $wr($ws)" ;;
            unknown)     UNKNOWN_ROLES="$UNKNOWN_ROLES $wr" ;;
          esac
          printf '%-24s %8s %8s  %s\n' "$wr" "$ws" "$wc" "$last"
        done <<EOF
$WROLES
EOF
        if [ -n "$DEAF_ROLES" ]; then
          echo "DEAF: no live watcher that can wake role(s):$DEAF_ROLES - mail sent to them will not wake anyone (#801; no-wake = polled only by processes with no session in their ancestry, #1228)."
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
