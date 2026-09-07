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
#   flow-wave-mailbox.sh list  [--wave W] [--json]
#
#   send   Deliver a message. `--to orchestrator` writes inbox-<from>.md and
#          REQUIRES --from (the writer names its own box); any other --to writes
#          outbox-<to>.md and --from defaults to 'orchestrator'. Body comes from
#          --body, --body-file, or stdin. Rev is per-box, monotonic, assigned
#          under flock.
#   read   Print messages addressed to <role> that are newer than its read
#          cursor, then advance the cursor. --all re-prints the whole box
#          history; --peek prints without advancing (so a watch still fires).
#          `--from <role>` (orchestrator only) narrows to one correspondent's
#          inbox instead of draining all of them (#792 item 7). A CONSUMING
#          orchestrator-wide read (no --from, no --peek) run non-interactively
#          refuses without `--out FILE` - a durable copy taken before the
#          drain - because piping that output through a filter has silently
#          destroyed message content before (#792).
#   watch  BLOCK until <role> has unread mail, print it, exit 0. Exit 5 on
#          timeout. THIS IS THE WAKE - launch it as a background call and the
#          harness re-invokes the session when it exits. Bounded by default
#          (30m) so a wave can never leave watchers spinning after it ends.
#          STAMPS A HEARTBEAT (#778) - see below. REQUIRES an explicit
#          `--peek` or `--consume` (#792 item 1): a bare `watch` used to
#          consume-by-default, which silently marked mail read the caller
#          never saw when many messages were already waiting. There is no
#          default now - the caller must say which it means. Ordering
#          (#792 item 2): with `--peek`, read the box THEN arm the watch
#          (the cursor never moves, so an unread backlog would otherwise
#          spin-fire on the very message the caller just read); with
#          `--consume`, arm THEN read. If a watch fires on its very first
#          poll - mail was already unread the moment it armed, not a fresh
#          wake - it prints a `flow-wave-mailbox: NOTE -` line ahead of the
#          message body saying so. Refuses to start (exit 4, `duplicate`)
#          when a live watcher already holds the same role in the same wave
#          (#792 item 4) - a role is single-owner, so a second watcher is
#          always a mistake, competing for the same mail rather than
#          receiving a copy of it. `watch --status` reports the FUSED watch
#          state (#801 - see STATE below), the raw heartbeat age, the live
#          watcher count and a `re-armed: yes/no` verdict instead of a bare,
#          undiagnosable zero (#792 item 3), using the self-excluding,
#          PID-based watcher count that replaces the old `pgrep -cf`
#          (#792 item 5 - see COUNTING below).
#   list   Box inventory for the wave: box, reader, rev, cursor, unread, mtime,
#          plus the WATCH state and live WATCHERS count of every role known to
#          read here (#778, #801).
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
#                 duplicate | refused | error
# preceded by FLOW_MAILBOX_*= detail lines ('-' when not applicable). Message
# BODIES are printed before the detail block, so a caller can split on the first
# FLOW_MAILBOX_ line.
#
# Exit codes: 0 normal, 2 usage error, 3 lock/IO failure, 4 duplicate watcher
# (#792 - a live watcher already holds this role+wave; nothing was started),
# 5 watch timeout, 6 lexicon refusal (#701 - the message was NOT delivered;
# nothing was written).
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
# check the fusion rather than take the state word on trust (#801).
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

cursor_file() { echo "$WAVE_DIR/.cursor-$(basename "$1")"; }

# --- The watch heartbeat (#778) ------------------------------------------------
# `.watch-<role>` holds one epoch integer, exactly the shape of `.cursor-<box>`.
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

cursor_of() {
  local c
  c="$(cursor_file "$1")"
  if [ -s "$c" ]; then
    local v
    v="$(tr -dc '0-9' < "$c")"
    echo "${v:-0}"
  else
    echo 0
  fi
}

# Count of messages in a box newer than its cursor.
unread_in() {
  local f="$1" cur
  [ -s "$f" ] || { echo 0; return; }
  cur="$(cursor_of "$f")"
  awk -v min="$cur" '
    /^<!-- cc-flow-wave-msg / {
      if (match($0, /rev=[0-9]+/)) {
        r = substr($0, RSTART + 4, RLENGTH - 4) + 0
        if (r > min) n++
      }
    }
    END { print n + 0 }
  ' "$f"
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

# Print every unread message for a role and (unless peeking) advance each box's
# cursor. Cursor writes go through the lock so a concurrent send cannot have its
# rev skipped by a half-written cursor.
drain_role() {
  local role="$1" peek="$2" all="$3" b min top printed=0
  while IFS= read -r b; do
    [ -n "$b" ] || continue
    if [ "$all" -eq 1 ]; then min=-1; else min="$(cursor_of "$b")"; fi
    top="$(max_rev "$b")"
    if [ "$top" -gt "$min" ] || [ "$all" -eq 1 ]; then
      local body
      body="$(extract_since "$b" "$min")"
      if [ -n "$body" ]; then
        echo "=== $(basename "$b") ==="
        echo "$body"
        printed=$((printed + 1))
      fi
    fi
    if [ "$peek" -eq 0 ] && [ "$top" -gt 0 ]; then
      cursor_set "$b" "$top"
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

# Advance a box's read cursor under the wave flock, so a concurrent send cannot
# interleave with a half-written cursor and have its rev skipped.
cursor_set() {
  local cfile
  cfile="$(cursor_file "$1")"
  (
    flock -w 10 9 || { echo "flow-wave-mailbox: could not lock $WAVE_DIR" >&2; exit 3; }
    printf '%s\n' "$2" > "$cfile"
  ) 9>"$LOCK_FILE"
}

VERB="${1:-}"
[ -n "$VERB" ] || usage_fail "usage: flow-wave-mailbox.sh send|read|watch|list ..."
shift

case "$VERB" in
  send | read | watch | list) : ;;
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
E_ROLE=""; E_BOX=""; E_REV=""; E_UNREAD=""

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
      if [ "$ALL" -eq 1 ]; then MIN=-1; else MIN="$(cursor_of "$BOX")"; fi
      TOP="$(max_rev "$BOX")"
      BODY_OUT=""
      if [ "$TOP" -gt "$MIN" ] || [ "$ALL" -eq 1 ]; then
        BODY_OUT="$(extract_since "$BOX" "$MIN")"
      fi
      if [ -n "$BODY_OUT" ]; then
        printf '=== %s ===\n%s\n' "$(basename "$BOX")" "$BODY_OUT"
      fi
      if [ "$PEEK" -eq 0 ] && [ "$TOP" -gt 0 ]; then
        cursor_set "$BOX" "$TOP"
      fi
      if [ -n "$A_OUT" ]; then
        printf '%s\n' "$BODY_OUT" > "$A_OUT" || usage_fail "cannot write --out: $A_OUT"
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
      BODY_OUT="$(drain_role "$ROLE" "$PEEK" "$ALL")"
      [ -n "$BODY_OUT" ] && echo "$BODY_OUT"
      printf '%s\n' "$BODY_OUT" > "$A_OUT" || usage_fail "cannot write --out: $A_OUT"
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
        n="$(unread_in "$b")"; r="$(max_rev "$b")"; c="$(cursor_of "$b")"
        TOTAL_UNREAD=$((TOTAL_UNREAD + n))
        mt="$(date -r "$b" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || echo '-')"
        ROWS="$ROWS$(printf '{"box":"%s","reader":"%s","rev":%s,"cursor":%s,"unread":%s,"mtime":"%s"}' \
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
      printf '{"wave":"%s","dir":"%s","boxes":[%s],"watches":[%s]}\n' \
        "$WAVE" "$WAVE_DIR" "${ROWS%,}" "${WATCHES%,}"
    else
      if [ -z "$BOXES" ]; then
        echo "No mailboxes in wave '$WAVE' yet ($WAVE_DIR)."
      else
        printf '%-24s %6s %7s %7s  %s\n' BOX REV CURSOR UNREAD MTIME
        while IFS= read -r b; do
          [ -n "$b" ] || continue
          n="$(unread_in "$b")"; r="$(max_rev "$b")"; c="$(cursor_of "$b")"
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
      fi
    fi
    E_UNREAD="$TOTAL_UNREAD"
    emit listed
    exit 0
    ;;
esac
