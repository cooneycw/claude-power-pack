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
#   flow-wave-mailbox.sh watch --role <role> [--wave W] [--timeout SEC]
#                              [--interval SEC] [--peek]
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
#   watch  BLOCK until <role> has unread mail, print it, exit 0. Exit 5 on
#          timeout. THIS IS THE WAKE - launch it as a background call and the
#          harness re-invokes the session when it exits. Bounded by default
#          (30m) so a wave can never leave watchers spinning after it ends.
#   list   Box inventory for the wave: box, rev, cursor, unread, mtime.
#
# Output ends with a machine-readable verdict line:
#   FLOW_MAILBOX: sent | read | empty | mail | timeout | listed | error
# preceded by FLOW_MAILBOX_*= detail lines ('-' when not applicable). Message
# BODIES are printed before the detail block, so a caller can split on the first
# FLOW_MAILBOX_ line.
#
# Exit codes: 0 normal, 2 usage error, 3 lock/IO failure, 5 watch timeout.
#
# Env (test hooks - unset in normal use):
#   FLOW_WAVE_MAILBOX_DIR   wave-root override (most precise)
#   FLOW_WAVE_REGISTRY_DIR  shared wave-root override, honored so the mailbox
#                           and the #638 registry always co-locate

set -uo pipefail

UID_NUM="$(id -u)"
WAVE_ROOT="${FLOW_WAVE_MAILBOX_DIR:-${FLOW_WAVE_REGISTRY_DIR:-${XDG_RUNTIME_DIR:-/run/user/$UID_NUM}/cc-flow-wave}}"

WATCH_TIMEOUT_DEFAULT=1800
WATCH_INTERVAL_DEFAULT=3

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
    sed -n '2,90p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
    ;;
  *) usage_fail "unknown verb: $VERB" ;;
esac

WAVE="default"; ROLE=""; A_TO=""; A_FROM=""; A_BODY=""; A_BODY_FILE=""
REPLACE=0; PEEK=0; ALL=0; JSON_OUT=0
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
    --timeout) [ "$#" -ge 2 ] || usage_fail "--timeout requires seconds"; TIMEOUT="$2"; shift ;;
    --timeout=*) TIMEOUT="${1#--timeout=}" ;;
    --interval) [ "$#" -ge 2 ] || usage_fail "--interval requires seconds"; INTERVAL="$2"; shift ;;
    --interval=*) INTERVAL="${1#--interval=}" ;;
    --replace) REPLACE=1 ;;
    --peek) PEEK=1 ;;
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
    UNREAD="$(unread_for_role "$ROLE")"
    if [ "$UNREAD" -eq 0 ] && [ "$ALL" -eq 0 ]; then
      E_ROLE="$ROLE"; E_UNREAD=0
      emit empty
      exit 0
    fi
    drain_role "$ROLE" "$PEEK" "$ALL"
    E_ROLE="$ROLE"; E_UNREAD="$UNREAD"
    emit read
    exit 0
    ;;

  watch)
    [ -n "$ROLE" ] || usage_fail "watch requires --role <role>"
    valid_name "$ROLE" || usage_fail "invalid role: '$ROLE'"
    case "$TIMEOUT" in ''|*[!0-9]*) usage_fail "--timeout must be whole seconds" ;; esac
    case "$INTERVAL" in ''|*[!0-9]*) usage_fail "--interval must be whole seconds" ;; esac
    [ "$INTERVAL" -ge 1 ] || usage_fail "--interval must be at least 1 second"

    WAITED=0
    while :; do
      UNREAD="$(unread_for_role "$ROLE")"
      if [ "$UNREAD" -gt 0 ]; then
        drain_role "$ROLE" "$PEEK" 0
        E_ROLE="$ROLE"; E_UNREAD="$UNREAD"
        emit mail
        exit 0
      fi
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
    TOTAL_UNREAD=0
    if [ "$JSON_OUT" -eq 1 ]; then
      ROWS=""
      while IFS= read -r b; do
        [ -n "$b" ] || continue
        n="$(unread_in "$b")"; r="$(max_rev "$b")"; c="$(cursor_of "$b")"
        TOTAL_UNREAD=$((TOTAL_UNREAD + n))
        ROWS="$ROWS$(printf '{"box":"%s","rev":%s,"cursor":%s,"unread":%s}' \
          "$(basename "$b")" "$r" "$c" "$n"),"
      done <<EOF
$BOXES
EOF
      printf '{"wave":"%s","dir":"%s","boxes":[%s]}\n' "$WAVE" "$WAVE_DIR" "${ROWS%,}"
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
    fi
    E_UNREAD="$TOTAL_UNREAD"
    emit listed
    exit 0
    ;;
esac
