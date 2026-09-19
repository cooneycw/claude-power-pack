#!/usr/bin/env bash
# checkout-readers.sh - name the processes holding files in the CPP checkout,
# and separate the ones running code that no longer exists (issue #1029,
# specimen 2).
#
# THE FAILURE THIS ANSWERS. A `flow-wave-mailbox.sh __supervise_daemon` was
# found running for 3 days 09:54 with:
#
#     fd 255 -> .../scripts/flow-wave-mailbox.sh (deleted)
#
# `git checkout`, `git merge` and `git pull` UNLINK and CREATE rather than
# rewriting in place (inode 4828759 -> 4828784, verified across a fast-forward).
# That is what makes the swap safe for a running reader, and it is also what
# makes the swap PARTLY INEFFECTIVE: the running process keeps executing the old
# inode indefinitely, while `ls`, `git status` and `sha256sum` all describe a
# different file. Mixed-version supervision follows - the daemon re-arms `watch`
# as a child, the child opens the script fresh and gets the NEW code while the
# parent runs the OLD.
#
# TWO QUESTIONS, ONE SCAN. The same walk answers both halves of the #1029
# remedy, and they are deliberately reported as different numbers:
#
#   STALE  a process holding a DELETED inode under the checkout. The swap did
#          not reach it. The remedy is to RE-ARM that supervisor, which needs a
#          pid - see "the pid is the point" below.
#   LIVE   a process holding a CURRENT inode under the checkout, or whose cwd is
#          inside it. A pull right now hot-swaps instruments under a running
#          gate, including one verifying the pull. `clear` IS the declared safe
#          moment for the pull that #1029 asks for.
#
# THE PID IS THE POINT. The detector as first posted to the nit store was:
#
#     ls -l /proc/*/fd 2>/dev/null | grep '<checkout>.*(deleted)'
#
# `ls -l /proc/*/fd` emits a `/proc/<pid>/fd:` HEADER line and then the entries;
# `grep` matches an entry and discards the header. A stale reader EXISTS, and
# which one is not recoverable from that line - so the output could not drive the
# one action a hit calls for. The corrected form carries the pid, and this script
# is that form, committed. Both controls were re-run against the corrected form
# before it was relied on (POSITIVE: pid 21206, known stale, FOUND; NEGATIVE: pid
# 3452895, a live daemon on a current inode, correctly NOT flagged) and are
# committed as tests/test_checkout_readers.py.
#
# TWO LIMITS, so a zero is not read as more than it is.
#
#   1. UNREADABLE /proc ENTRIES ARE COUNTED, NOT DISCARDED. The original form's
#      `2>/dev/null` swallowed permission errors, and on a mixed-user host an
#      unreadable entry is silently absent - absence reading as clean, inside the
#      detector for exactly that. `unreadable` reports how many processes could
#      not be inspected, and a scan that inspected NOTHING reports `unknown`,
#      never `clear`.
#
#      THE BOUND IS REPORTED ON EVERY VERDICT, INCLUDING `clear`, AND IN QUIET
#      MODE TOO. That placement is the whole remedy, and two weaker designs were
#      built and measured first, so they are recorded rather than reinvented:
#
#        (a) Verdict `clear` with the count only in the full report. REJECTED:
#            the quiet line is the one that reaches a session start, so a
#            consumer could receive a bare "clear" that concealed 390
#            uninspected processes. That is a blind instrument's green.
#        (b) A fifth verdict, `partial`, whenever any SAME-USER process was
#            unreadable - on the reasoning that other-user entries are the
#            ordinary floor ("every relevant process here is the same user, so
#            the result is exact on this host", the nit comment) while a
#            same-user blind spot is a hole in a population otherwise fully
#            visible. REJECTED ON MEASUREMENT: `(sd-pam)`, systemd's per-session
#            PAM helper, runs as the user with an unreadable `/proc/<pid>/fd` on
#            EVERY systemd user session. Reference host: 390 unreadable of 580
#            scanned, 389 root-owned and exactly one same-user - `(sd-pam)`,
#            permanently. `partial` would therefore be the verdict forever and
#            `clear` would be dead code, which is the oscillation ADR 0009
#            predicts: a state nobody can reach is a state everybody learns to
#            skip, and the distinction is lost exactly as thoroughly as if it
#            had never been drawn.
#
#      WHAT WOULD MOVE THIS BACK (ADR 0009). If a host is found where an
#      unreadable same-user process can plausibly hold the checkout - anything
#      but the known structural set - the correct response is the `partial`
#      state from (b), not widening the counts. The counts are already split by
#      owner in `--json` (`unreadable`, `unreadable_same_user`) precisely so
#      that decision can be made from data rather than re-argued.
#
#      A pid that vanishes mid-scan is not counted as unreadable: it is gone,
#      which is an answer, not a refusal.
#   2. IT SEES ONLY PROCESSES ALIVE AT THE INSTANT IT RUNS. A supervisor that
#      dies and respawns between the change and the check leaves no trace; one
#      that is stale but exits before you look reports clean. Correct for a check
#      run IMMEDIATELY after the replacing operation. Wrong if anyone later
#      treats it as an audit of what happened.
#
# THE CALLER'S OWN PROCESS TREE IS A READER, and that is not a false positive.
# Run from inside the checkout, this script's ancestors (the shell, `make`,
# pytest) hold the tree and are reported as LIVE, because they do. Their count is
# broken out as CHECKOUT_READERS_SELF_TREE so a caller can subtract deliberately;
# the script never decides that on the caller's behalf, because "ignore the
# processes that look like mine" is how a detector stops seeing a sibling
# session.
#
# Usage:
#   checkout-readers.sh                  # human report; always exit 0
#   checkout-readers.sh --quiet          # one advisory line, only when action is needed
#   checkout-readers.sh --json           # machine-readable; always exit 0
#   checkout-readers.sh --path <dir>     # inspect THIS tree (declared, not inferred)
#
# Output in report mode ends with:
#   CHECKOUT_READERS: stale | busy | clear | unknown
#
# and, whenever any process could not be inspected, a bound line that is emitted
# in EVERY mode - report, --json and --quiet alike:
#   CHECKOUT_READERS_UNREADABLE: <n> (<m> same-user)
#
# Exit status is ALWAYS 0 for a completed scan, including `stale` - this is a
# reporter, not a gate. Only bad usage exits 2.
#
# Env (test seams - unset in normal use):
#   CPP_CHECKOUT_READERS_CHECKOUT  override checkout detection
#   CPP_CHECKOUT_READERS_PROC      override the /proc root

set -uo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SELF_DIR="$(cd "$(dirname "$SELF")" && pwd)"
PROC_ROOT="${CPP_CHECKOUT_READERS_PROC:-/proc}"

MODE="report"
ARG_PATH=""
EXPECT_PATH=0
for arg in "$@"; do
    if [ "$EXPECT_PATH" -eq 1 ]; then
        ARG_PATH="$arg"
        EXPECT_PATH=0
        continue
    fi
    case "$arg" in
        --report) MODE="report" ;;
        --quiet)  MODE="quiet" ;;
        --json)   MODE="json" ;;
        --path)   EXPECT_PATH=1 ;;
        --path=*) ARG_PATH="${arg#--path=}" ;;
        -h|--help)
            awk 'NR==1 && /^#!/ {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$SELF"
            exit 0 ;;
        *)
            echo "checkout-readers: unknown argument '$arg' (use --quiet, --json, --path <dir>)" >&2
            exit 2 ;;
    esac
done
if [ "$EXPECT_PATH" -eq 1 ]; then
    echo "checkout-readers: --path needs a directory" >&2
    exit 2
fi

is_checkout() {
    [ -n "$1" ] && [ -f "$1/CLAUDE.md" ] && [ -d "$1/.claude/commands" ]
}

# Self-first resolution, for the same reason as toolchain-provenance.sh: this
# file's own location IS the executing copy, and a conventional-path guess
# measures whichever checkout sits there instead.
CHECKOUT=""
REASON=""
if [ -n "$ARG_PATH" ]; then
    if [ -d "$ARG_PATH" ]; then
        CHECKOUT="$(cd "$ARG_PATH" && pwd -P)"
    else
        REASON="not a directory: $ARG_PATH"
    fi
elif [ -n "${CPP_CHECKOUT_READERS_CHECKOUT:-}" ]; then
    if [ -d "$CPP_CHECKOUT_READERS_CHECKOUT" ]; then
        CHECKOUT="$(cd "$CPP_CHECKOUT_READERS_CHECKOUT" && pwd -P)"
    else
        REASON="CPP_CHECKOUT_READERS_CHECKOUT is not a directory: $CPP_CHECKOUT_READERS_CHECKOUT"
    fi
else
    for dir in "$SELF_DIR/.." "${HOME:+$HOME/Projects/claude-power-pack}" \
               /opt/claude-power-pack "${HOME:+$HOME/.claude-power-pack}"; do
        [ -n "$dir" ] || continue
        if is_checkout "$dir"; then
            CHECKOUT="$(cd "$dir" && pwd -P)"
            break
        fi
    done
    [ -n "$CHECKOUT" ] || REASON="no CPP checkout found"
fi

STALE=0
LIVE=0
UNREADABLE=0
UNREADABLE_SAME_USER=0
SCANNED=0
# INSPECTED counts processes this scan actually LOOKED INSIDE, which is a
# different number from the ones it walked past (counter-model review,
# codex/gpt-6-astra). SCANNED increments on encounter, so a population that is
# entirely unreadable produced SCANNED=N, UNREADABLE=N and a verdict of `clear`
# - "I looked and found nothing" rendered identically to "I could not look at
# anything", inside the detector written to refuse exactly that. `clear` now
# requires at least one successful inspection.
INSPECTED=0
SELF_TREE=0
STALE_LINES=()
LIVE_LINES=()
VERDICT="unknown"

# Ancestors of THIS invocation, so their hits can be counted separately rather
# than silently dropped. Walking PPid from /proc rather than trusting $PPID,
# because the seam may point $PROC_ROOT at a fixture.
declare -A ANCESTORS=()
if [ -d "$PROC_ROOT" ]; then
    walk=$$
    guard=0
    while [ -n "$walk" ] && [ "$walk" != "0" ] && [ "$guard" -lt 64 ]; do
        ANCESTORS["$walk"]=1
        ppid="$(awk '{print $4}' "$PROC_ROOT/$walk/stat" 2>/dev/null || true)"
        [ -n "$ppid" ] || break
        walk="$ppid"
        guard=$(( guard + 1 ))
    done
fi

if [ -n "$CHECKOUT" ]; then
    if [ ! -d "$PROC_ROOT" ]; then
        REASON="no readable process table at $PROC_ROOT - this host cannot answer the question"
    else
        for pid_dir in "$PROC_ROOT"/[0-9]*; do
            [ -d "$pid_dir" ] || continue
            pid="${pid_dir##*/}"
            [ "$pid" = "$$" ] && continue
            SCANNED=$(( SCANNED + 1 ))
            pid_stale=0
            pid_live=0
            fd_dir="$pid_dir/fd"
            if [ -d "$fd_dir" ]; then
                if [ -r "$fd_dir" ] && [ -x "$fd_dir" ]; then
                    # ONE `ls -l` per process covering both the fd table and the
                    # cwd link, then pure-bash matching over its lines. The
                    # readlink-per-descriptor this replaces spawned thousands of
                    # subprocesses on an ordinary table (8.7s for 614 processes);
                    # this is the same per-pid shape the nit store's corrected
                    # detector used, and it keeps the pid for exactly that reason.
                    #
                    # The two operands are told apart by their name field: `ls`
                    # prints the cwd operand by the path it was GIVEN, so its
                    # line carries `/cwd -> `, while fd entries are bare numbers.
                    # That distinction is load-bearing - a process whose CWD was
                    # deleted is not executing deleted code, and must not be
                    # counted as a stale reader.
                    # A FAILED LISTING IS NOT AN EMPTY ONE. `ls` can exit
                    # non-zero for a process that vanished mid-scan or whose
                    # entries became unreadable between the test above and here;
                    # treating that as "no matching descriptors" is the same
                    # absence-as-clean defect one level down.
                    #
                    # THE FD TABLE AND THE CWD LINK ARE LISTED SEPARATELY, and
                    # that separation is load-bearing. Passing both to one `ls`
                    # is cheaper, and it conflates two different facts: `ls`
                    # exits non-zero when ANY operand fails, so a process with no
                    # `cwd` entry - one that vanished mid-scan, or a fixture
                    # modelling a process without one - made a perfectly
                    # successful fd listing read as an inspection failure, and
                    # its real descriptors were then never examined. Measured:
                    # it silently zeroed the stale count in three fixture cases.
                    # The fd table is THE inspection; cwd is a supplementary
                    # question whose absence is an answer, not a refusal.
                    if listing="$(ls -l "$fd_dir" 2>/dev/null)"; then
                        INSPECTED=$(( INSPECTED + 1 ))
                    elif [ -d "$pid_dir" ]; then
                        UNREADABLE=$(( UNREADABLE + 1 ))
                        [ -O "$pid_dir" ] && UNREADABLE_SAME_USER=$(( UNREADABLE_SAME_USER + 1 ))
                        continue
                    else
                        continue
                    fi
                    while IFS= read -r entry; do
                        case "$entry" in
                            *" -> $CHECKOUT"|*" -> $CHECKOUT/"*) : ;;
                            *" -> $CHECKOUT (deleted)"|*" -> $CHECKOUT/"*" (deleted)") : ;;
                            *) continue ;;
                        esac
                        case "$entry" in
                            *" (deleted)") pid_stale=1 ;;
                            *)             pid_live=1 ;;
                        esac
                    done <<< "$listing"
                    # cwd only matters when the fd table said nothing, which is
                    # the overwhelming majority - so this runs once per process
                    # and never twice.
                    if [ "$pid_stale" -eq 0 ] && [ "$pid_live" -eq 0 ]; then
                        cwd_entry="$(ls -ld "$pid_dir/cwd" 2>/dev/null || true)"
                        case "$cwd_entry" in
                            *" -> $CHECKOUT"|*" -> $CHECKOUT/"*|\
                            *" -> $CHECKOUT (deleted)"|*" -> $CHECKOUT/"*" (deleted)")
                                # A gate running `make` in the tree holds it,
                                # whatever state the directory itself is in.
                                pid_live=1 ;;
                        esac
                    fi
                elif [ -d "$pid_dir" ]; then
                    # Counted, never discarded (limit 1). An entry we could not
                    # read is UNKNOWN, and unknown must not be summed into clean.
                    # Re-tested for existence first: a pid that exited between
                    # the glob and this read is GONE, which is an answer, and
                    # counting it as a refusal would make every busy host look
                    # permanently blind.
                    UNREADABLE=$(( UNREADABLE + 1 ))
                    # `-O` is a bash builtin (owned by the effective uid). The
                    # `stat -c %u` this replaces spawned a subprocess for every
                    # unreadable entry - 382 of them on the reference host, and
                    # most of the scan's 11 seconds.
                    if [ -O "$pid_dir" ]; then
                        UNREADABLE_SAME_USER=$(( UNREADABLE_SAME_USER + 1 ))
                    fi
                fi
            fi
            # argv is read ONLY for a hit. Reading it for every process cost a
            # `tr` and a `cut` per entry, which is pure waste on the ~99% that
            # match nothing.
            if [ "$pid_stale" -eq 1 ] || [ "$pid_live" -eq 1 ]; then
                argv="$(tr '\0' ' ' < "$pid_dir/cmdline" 2>/dev/null | cut -c1-70)"
                [ -n "$argv" ] || argv="$(cat "$pid_dir/comm" 2>/dev/null || echo '?')"
            fi
            if [ "$pid_stale" -eq 1 ]; then
                STALE=$(( STALE + 1 ))
                STALE_LINES+=("$(printf 'pid %-8s %s' "$pid" "$argv")")
            elif [ "$pid_live" -eq 1 ]; then
                LIVE=$(( LIVE + 1 ))
                mine=""
                if [ -n "${ANCESTORS[$pid]:-}" ]; then
                    SELF_TREE=$(( SELF_TREE + 1 ))
                    mine="  (an ancestor of this invocation)"
                fi
                LIVE_LINES+=("$(printf 'pid %-8s %s%s' "$pid" "$argv" "$mine")")
            fi
        done
        if [ "$SCANNED" -eq 0 ]; then
            REASON="the process table at $PROC_ROOT held no entries"
        elif [ "$INSPECTED" -eq 0 ] && [ "$STALE" -eq 0 ] && [ "$LIVE" -eq 0 ]; then
            # Walked $SCANNED processes and got inside none of them. There is no
            # evidence here in either direction, so there is no verdict to give.
            REASON="none of the $SCANNED process(es) at $PROC_ROOT could be inspected"
        elif [ "$STALE" -gt 0 ]; then
            VERDICT="stale"
        elif [ "$LIVE" -gt 0 ]; then
            VERDICT="busy"
        else
            VERDICT="clear"
        fi
    fi
fi

[ -n "$REASON" ] || REASON="-"

case "$MODE" in
    quiet)
        case "$VERDICT" in
            stale)
                echo "CPP checkout: ${STALE} process(es) still executing DELETED files from ${CHECKOUT} - re-arm them; a pull did not reach them (#1029)" ;;
            busy)
                echo "CPP checkout: ${LIVE} live reader(s) hold ${CHECKOUT} - NOT a safe moment to pull; instruments would hot-swap under a running gate (#1029)" ;;
            unknown)
                echo "CPP checkout: reader scan UNKNOWN (${REASON}) - unscanned, not clean (#1029)" ;;
        esac
        # The bound, on EVERY verdict including 'clear'. A quiet line is what
        # reaches a session start, so this is the one place where omitting it
        # would let a blind scan render as a clean one (limit 1).
        if [ "$UNREADABLE" -gt 0 ]; then
            echo "CPP checkout: reader scan inspected ${SCANNED} process(es); ${UNREADABLE} (${UNREADABLE_SAME_USER} same-user) could not be read - a floor, not a total (#1029)"
        fi
        exit 0 ;;
    json)
        num_or_null() { [ "$1" = "-" ] && printf 'null' || printf '%s' "$1"; }
        # Escape before quoting - a tree path containing `"` or `\` produced
        # invalid JSON. Backslash first, or it doubles what it just inserted.
        json_escape() {
            printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/[[:cntrl:]]/ /g'
        }
        str_or_null() { [ "$1" = "-" ] && printf 'null' || printf '"%s"' "$(json_escape "$1")"; }
        printf '{"verdict":"%s","checkout":%s,"stale":%s,"live":%s,"self_tree":%s,"unreadable":%s,"unreadable_same_user":%s,"scanned":%s,"inspected":%s,"reason":%s}\n' \
            "$VERDICT" "$(str_or_null "${CHECKOUT:--}")" \
            "$STALE" "$LIVE" "$SELF_TREE" "$UNREADABLE" "$UNREADABLE_SAME_USER" "$SCANNED" "$INSPECTED" \
            "$(str_or_null "$REASON")"
        exit 0 ;;
esac

echo "checkout-readers: tree ${CHECKOUT:-<none>}"
echo "  processes scanned  $SCANNED  (${INSPECTED} actually inspected)"
echo "  stale (deleted)    $STALE"
echo "  live (current)     $LIVE  (${SELF_TREE} of them ancestors of this invocation)"
echo "  unreadable         $UNREADABLE  (${UNREADABLE_SAME_USER} of them same-user)"
if [ "$REASON" != "-" ]; then
    echo "  reason             $REASON"
fi
if [ "${#STALE_LINES[@]}" -gt 0 ]; then
    echo ""
    echo "  Executing DELETED files from this tree - re-arm each:"
    for line in "${STALE_LINES[@]}"; do echo "    $line"; done
fi
if [ "${#LIVE_LINES[@]}" -gt 0 ]; then
    echo ""
    echo "  Holding CURRENT files or cwd in this tree - a pull hot-swaps under them:"
    for line in "${LIVE_LINES[@]}"; do echo "    $line"; done
fi
echo ""
if [ "$UNREADABLE" -gt 0 ]; then
    echo "NOTE: ${UNREADABLE} process(es) could not be inspected (permissions). Those are UNKNOWN,"
    echo "not clean - the counts above are a floor, not a total (limit 1)."
    echo "  ${UNREADABLE_SAME_USER} same-user  - a blind spot inside the population otherwise fully visible;"
    echo "                  any number above zero downgrades 'clear' to 'partial'."
    echo "  $(( UNREADABLE - UNREADABLE_SAME_USER )) other-user - the ordinary floor on a multi-user host; reported as the"
    echo "                  bound on what this scan can see, and it changes no verdict."
fi
echo "This sees only processes alive at the instant it ran. It is correct run IMMEDIATELY"
echo "after the replacing operation, and is not an audit of what happened (limit 2)."
echo ""
case "$VERDICT" in
    clear)
        echo "No reader was found among the ${INSPECTED} process(es) inspected: a pull now is the"
        echo "declared safe moment (issue #1029). Read that together with the bound below - this"
        echo "is 'nothing found where we could look', never 'nothing exists'." ;;
    busy)
        echo "Live readers hold this tree. Pulling now hot-swaps instruments under running"
        echo "sessions - including any gate verifying the pull. Wait for 'clear'." ;;
    stale)
        echo "Processes above are executing files that no longer exist on disk. 'git status'"
        echo "and sha256sum describe a DIFFERENT file than the one they are running, so the"
        echo "checkout's own state cannot tell you this. Re-arm each pid listed." ;;
    unknown)
        echo "The scan could not run: $REASON"
        echo "Unscanned reads as UNKNOWN, never as clean (issue #1029)." ;;
esac
echo "CHECKOUT_READERS: $VERDICT"
if [ "$UNREADABLE" -gt 0 ]; then
    echo "CHECKOUT_READERS_UNREADABLE: $UNREADABLE ($UNREADABLE_SAME_USER same-user)"
fi
exit 0
