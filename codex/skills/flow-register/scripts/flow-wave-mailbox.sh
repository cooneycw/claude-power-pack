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
#          receiving a copy of it. `watch --status` reports the heartbeat
#          state/age plus the live watcher count and a `re-armed: yes/no`
#          verdict instead of a bare, undiagnosable zero (#792 item 3),
#          using the self-excluding, PID-based watcher count that replaces
#          the old `pgrep -cf` (#792 item 5 - see COUNTING below).
#   list   Box inventory for the wave: box, reader, rev, cursor, unread, mtime,
#          plus the WATCH state of every role known to read here (#778).
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
# fresh, and only a refreshing stamp separates those two. Three states follow:
#   armed   stamped within FLOW_WAVE_WATCH_STALE_SECS (default 300)
#   stale   stamped longer ago - the watch died, or its session is busy between
#           wakes; either way the role is deaf RIGHT NOW, and the age is always
#           printed so the reader can judge which
#   absent  no stamp at all - the watch was NEVER armed. The unambiguous case,
#           and the one actually observed.
# The heartbeat is deliberately NOT removed on exit: "died" and "never armed"
# are operationally different answers and erasing the file would flatten them
# back into one. `read` does not stamp - the heartbeat is about the WAKE, and a
# cursor that is advancing is separately visible in `list`.
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
# Env:
#   FLOW_WAVE_WATCH_STALE_SECS  heartbeat age past which a watch reads `stale`
#                               rather than `armed` (#778, default 300)
# Env (test hooks - unset in normal use):
#   FLOW_WAVE_MAILBOX_DIR   wave-root override (most precise)
#   FLOW_WAVE_REGISTRY_DIR  shared wave-root override, honored so the mailbox
#                           and the #638 registry always co-locate
#   FLOW_WAVE_NOW           override "now" as epoch seconds, so heartbeat ages
#                           are deterministic (same hook name the registry uses)

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

# armed | stale | absent for <role>.
watch_state() {
  local age
  age="$(watch_age "$1")"
  if [ "$age" = "-" ]; then
    echo absent
  elif [ "$age" -le "$WATCH_STALE_SECS" ]; then
    echo armed
  else
    echo stale
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
count_watchers() {
  local role="$1" wave="$2"
  if [ -d /proc ]; then
    count_watchers_proc "$role" "$wave"
  else
    count_watchers_ps_fallback "$role" "$wave"
  fi
}

# The calling process's own ancestor chain: its subshell, up through every
# parent, back to PID 1. A single PID ($$ or $BASHPID alone) is not enough
# to exclude: `count_watchers` runs inside a `$(...)` command substitution,
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

count_watchers_proc() {
  local role="$1" wave="$2" pid n=0
  local self_chain
  self_chain="$(self_chain_proc)"
  for pid in /proc/[0-9]*; do
    pid="${pid#/proc/}"
    case "$self_chain" in *" $pid "*) continue ;; esac
    [ -r "/proc/$pid/cmdline" ] || continue
    local argv=() tok i found_role="" found_wave="default"
    while IFS= read -r -d '' tok; do argv+=("$tok"); done < "/proc/$pid/cmdline" 2>/dev/null
    [ "${#argv[@]}" -ge 3 ] || continue
    case "${argv[0]##*/}" in bash) : ;; *) continue ;; esac
    case "${argv[1]}" in */flow-wave-mailbox.sh | flow-wave-mailbox.sh) : ;; *) continue ;; esac
    [ "${argv[2]}" = "watch" ] || continue
    for ((i = 3; i < ${#argv[@]}; i++)); do
      case "${argv[$i]}" in
        --role) found_role="${argv[$((i + 1))]:-}" ;;
        --role=*) found_role="${argv[$i]#--role=}" ;;
        --wave) found_wave="${argv[$((i + 1))]:-default}" ;;
        --wave=*) found_wave="${argv[$i]#--wave=}" ;;
      esac
    done
    [ "$found_role" = "$role" ] || continue
    [ "$found_wave" = "$wave" ] || continue
    n=$((n + 1))
  done
  echo "$n"
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
# occasional false "duplicate".
count_watchers_ps_fallback() {
  local role="$1" wave="$2" line pid args n=0
  local self_chain
  self_chain="$(self_chain_ps)"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    pid="${line%% *}"
    args="${line#* }"
    case "$self_chain" in *" $pid "*) continue ;; esac
    case "$args" in
      *flow-wave-mailbox.sh\ watch*"--role $role "*|*flow-wave-mailbox.sh\ watch*"--role $role")
        case "$args" in
          *"--wave $wave "*|*"--wave $wave") n=$((n + 1)) ;;
          *"--wave "*) : ;; # a different wave - not a duplicate
          *) [ "$wave" = "default" ] && n=$((n + 1)) ;;
        esac
        ;;
    esac
  done <<EOF
$(ps -eo pid,args --no-headers 2>/dev/null)
EOF
  echo "$n"
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
      WSTATE="$(watch_state "$ROLE")"
      WAGE="$(watch_age "$ROLE")"
      WCOUNT="$(count_watchers "$ROLE" "$WAVE")"
      if [ "$WAGE" = "-" ]; then WLAST="never armed"; else WLAST="${WAGE}s ago"; fi
      if [ "$WCOUNT" -gt 0 ]; then REARMED=yes; else REARMED=no; fi
      echo "flow-wave-mailbox: role '$ROLE' wave '$WAVE': last wake handled $WLAST (state: $WSTATE); $WCOUNT live watcher process(es); re-armed: $REARMED"
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
        WATCHES="$WATCHES$(printf '{"role":"%s","state":"%s","age_secs":%s}' \
          "$wr" "$(watch_state "$wr")" "$wa_json"),"
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
        printf '%-24s %8s  %s\n' ROLE WATCH LAST
        while IFS= read -r wr; do
          [ -n "$wr" ] || continue
          wa="$(watch_age "$wr")"
          if [ "$wa" = "-" ]; then last="never armed"; else last="${wa}s ago"; fi
          printf '%-24s %8s  %s\n' "$wr" "$(watch_state "$wr")" "$last"
        done <<EOF
$WROLES
EOF
      fi
    fi
    E_UNREAD="$TOTAL_UNREAD"
    emit listed
    exit 0
    ;;
esac
