#!/usr/bin/env bash
# toolchain-provenance.sh - make the EXECUTED copy say what version it holds
# (issue #1029, specimen 1).
#
# THE FAILURE THIS ANSWERS. `~/.claude/scripts/*` are symlinks into ONE shared
# CPP checkout, and every session on the host runs its instruments from it. On
# 2026-09-15 that checkout was 21 commits behind `origin/main` while PR #993's
# merge-starvation tracking sat merged and unreachable: `git log origin/main`
# said the feature had shipped, `<helper> --help` said the flag did not exist,
# and NOTHING ON THE HOST COMPARED THE TWO. A wave-ledger conclusion - "an
# instrument built, merged, and never invoked" - was drafted from that gap and
# was factually wrong. It was corrected only because a worker tried to comply
# and found the flags missing.
#
# The cheap general move is not preventing drift. It is making the executed copy
# able to REPORT ITS OWN POSITION, as a NUMBER, wherever a session declares its
# vantage - so a wave that starts on a 21-commit-old toolchain says so at
# registration rather than discovering it eleven hours later.
#
# A NUMBER, NOT A BOOLEAN, AND NEVER A FABRICATED ZERO. The two verdicts this
# must keep apart are "measured, and the gap is zero" and "could not measure".
# They are the same shape as absence-reads-as-clean everywhere else in this
# repository, and a `0` printed for an unmeasurable checkout is strictly worse
# than no line at all, because it looks like data. Every unmeasurable state
# reports `-` for the counts and `unknown` for the verdict, and the reason is
# named on its own line.
#
# FETCH AGE IS PART OF THE MEASUREMENT, not a nicety. `behind=0` is computed
# against the remote-tracking ref this checkout last fetched, so a checkout that
# has not fetched for three days reports a confident zero that is a statement
# about three-day-old information. The gap and the age of the evidence behind it
# are one fact; reporting the first without the second re-creates the original
# failure with a number attached. This never fetches - it is read-only and runs
# on session-start paths - so the age is the honest caveat on its own answer.
#
# The age comes with its SOURCE (`fetch_age_source`), because the three places it
# can come from are not equally good and one of them is coarse. See the block
# beside the lookup; the short version is that an age read off `packed-refs`
# bounds staleness rather than dating the fetch, and presenting it unlabelled as
# "last fetched" would be exactly the fabricated specificity this file exists to
# remove.
#
# WHY A PULL IS NOT THE WHOLE REMEDY, and why this only ever REPORTS.
# `flow-finish-gate.sh` resolves `CPP_DIR` to this same checkout and runs
# `lib.cicd` out of it LIVE, so pulling mid-wave hot-swaps every instrument
# under every running session - including the ones verifying the pull. The
# answer to a live gap is a SEQUENCED upgrade at a declared safe moment, and the
# safe moment is what `checkout-readers.sh` answers. This script never pulls,
# never fetches, and never writes.
#
# Usage:
#   toolchain-provenance.sh                  # human report; always exit 0
#   toolchain-provenance.sh --quiet          # one advisory line, only when action is needed
#   toolchain-provenance.sh --json           # machine-readable; always exit 0
#   toolchain-provenance.sh --path <dir>     # measure THIS checkout (declared, not inferred)
#
# Output in report mode ends with:
#   TOOLCHAIN_PROVENANCE: current | behind | ahead | diverged | unknown
#
# `ahead` is a real and separate state: a checkout carrying local commits that
# `origin/main` does not have is not stale, but it is also not what a reviewer
# read, so it must not render as `current`.
#
# Exit status is ALWAYS 0 for a completed measurement, including `behind` and
# `unknown` - this is a reporter, not a gate. Only bad usage exits 2.
#
# Env (test seams - unset in normal use):
#   CPP_TOOLCHAIN_CHECKOUT   override checkout detection
#   CPP_TOOLCHAIN_GIT        override the `git` binary

set -uo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SELF_DIR="$(cd "$(dirname "$SELF")" && pwd)"
GIT_BIN="${CPP_TOOLCHAIN_GIT:-git}"

#: Above this, a `current` verdict is qualified rather than silent: the gap is
#: measured against what this checkout last fetched, so a zero against a
#: day-old reference is a statement about day-old information. One day, because
#: this repository's waves run within a day and the #1029 incident was an
#: eleven-hour one; it is a reporting threshold and gates nothing.
STALE_EVIDENCE_SECONDS=86400

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
            echo "toolchain-provenance: unknown argument '$arg' (use --quiet, --json, --path <dir>)" >&2
            exit 2 ;;
    esac
done
if [ "$EXPECT_PATH" -eq 1 ]; then
    echo "toolchain-provenance: --path needs a directory" >&2
    exit 2
fi

is_checkout() {
    [ -n "$1" ] && [ -f "$1/CLAUDE.md" ] && [ -d "$1/.claude/commands" ]
}

# The measured object is DECLARED where the caller knows it (`--path`, the test
# seam), and otherwise resolved SELF-FIRST: this file's own location is the one
# thing that cannot be wrong about which checkout is executing, because it IS
# the executing copy. A `~/Projects/...` guess first would measure whichever
# checkout happens to sit at the conventional path, which on a host with a
# worktree beside it is not the tree the symlinks resolve into.
CHECKOUT=""
REASON=""
if [ -n "$ARG_PATH" ]; then
    if is_checkout "$ARG_PATH"; then
        CHECKOUT="$(cd "$ARG_PATH" && pwd -P)"
    else
        REASON="not a CPP checkout: $ARG_PATH"
    fi
elif [ -n "${CPP_TOOLCHAIN_CHECKOUT:-}" ]; then
    if is_checkout "$CPP_TOOLCHAIN_CHECKOUT"; then
        CHECKOUT="$(cd "$CPP_TOOLCHAIN_CHECKOUT" && pwd -P)"
    else
        REASON="CPP_TOOLCHAIN_CHECKOUT is not a CPP checkout: $CPP_TOOLCHAIN_CHECKOUT"
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

HEAD_SHA="-"
UPSTREAM="-"
BEHIND="-"
AHEAD="-"
FETCH_AGE="-"
FETCH_AGE_SOURCE="-"
VERDICT="unknown"

if [ -n "$CHECKOUT" ]; then
    if ! "$GIT_BIN" -C "$CHECKOUT" rev-parse --git-dir >/dev/null 2>&1; then
        REASON="checkout is not a git repository: $CHECKOUT"
    else
        HEAD_SHA="$("$GIT_BIN" -C "$CHECKOUT" rev-parse --short HEAD 2>/dev/null || echo '-')"
        # The upstream of the CURRENT BRANCH, never a hardcoded `origin/main`.
        # A checkout parked on a release branch has a different upstream, and
        # measuring it against main would report a fabricated gap - a wrong
        # number, which disables its own audit more thoroughly than no number.
        UPSTREAM="$("$GIT_BIN" -C "$CHECKOUT" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
        if [ -z "$UPSTREAM" ]; then
            UPSTREAM="-"
            REASON="HEAD has no upstream branch (detached, or a branch that tracks nothing)"
        elif ! "$GIT_BIN" -C "$CHECKOUT" rev-parse --verify --quiet "$UPSTREAM" >/dev/null 2>&1; then
            REASON="upstream ref '$UPSTREAM' does not exist in this checkout"
            UPSTREAM="-"
        else
            COUNTS="$("$GIT_BIN" -C "$CHECKOUT" rev-list --left-right --count "HEAD...$UPSTREAM" 2>/dev/null || true)"
            if [ -z "$COUNTS" ]; then
                REASON="could not count commits between HEAD and '$UPSTREAM'"
            else
                AHEAD="${COUNTS%%[[:space:]]*}"
                BEHIND="${COUNTS##*[[:space:]]}"
                case "$AHEAD$BEHIND" in
                    *[!0-9]*)
                        AHEAD="-"; BEHIND="-"
                        REASON="rev-list returned an uncountable result" ;;
                    *)
                        if [ "$BEHIND" -gt 0 ] && [ "$AHEAD" -gt 0 ]; then
                            VERDICT="diverged"
                        elif [ "$BEHIND" -gt 0 ]; then
                            VERDICT="behind"
                        elif [ "$AHEAD" -gt 0 ]; then
                            VERDICT="ahead"
                        else
                            VERDICT="current"
                        fi ;;
                esac
            fi
            # AGE OF THE EVIDENCE, not of the working tree - and the SOURCE of
            # that age is reported beside it, because the three candidates are
            # not equally good and silently substituting a weaker one under the
            # same name is the failure this whole script is about.
            #
            #   fetch-head   `.git/FETCH_HEAD`, rewritten by every fetch/pull -
            #                OF ANY REMOTE, which is why it is accepted only when
            #                it actually names this upstream's remote URL. Absent
            #                on a clone that has never fetched since.
            #   loose-ref    the remote-tracking ref as its own file. Refreshed
            #                when that branch moved - so on a branch that has
            #                not moved, older than the last fetch.
            #   packed-refs  COARSE, and the reason the source is named at all:
            #                it is the last time ANY refs were packed, which on
            #                a fresh clone is the clone. It bounds staleness and
            #                does not date the fetch. Reading it as "last
            #                fetched" would be a fabricated specificity.
            #
            # Before this ordering existed the loose-ref lookup alone returned
            # nothing on any packed-refs repository - which every fresh clone is
            # - so the age silently read `unknown` in the ordinary case.
            REF_FILE=""
            FETCH_AGE_SOURCE="-"
            # FETCH_HEAD is PER-WORKTREE and the refs are SHARED, so the two are
            # resolved through different git paths. Using the common dir for both
            # made a linked worktree read the primary checkout's FETCH_HEAD -
            # someone else's fetch, dated as though it were ours.
            FETCH_HEAD_FILE="$("$GIT_BIN" -C "$CHECKOUT" rev-parse --git-path FETCH_HEAD 2>/dev/null || true)"
            GITDIR="$("$GIT_BIN" -C "$CHECKOUT" rev-parse --git-common-dir 2>/dev/null || true)"
            for var in FETCH_HEAD_FILE GITDIR; do
                eval "value=\$$var"
                case "$value" in
                    ""|/*) : ;;
                    *)     eval "$var=\"\$CHECKOUT/\$value\"" ;;
                esac
            done
            # FETCH_HEAD IS ONLY EVIDENCE ABOUT THE REMOTE IT NAMES. Every fetch
            # of every remote rewrites the same file, so an unrelated
            # `git fetch other-remote` would otherwise make a months-old
            # observation of OUR upstream look freshly measured - a fabricated
            # specificity, in the field that exists to prevent one. The file
            # records `branch '<name>' of <url>`, so it counts only when it names
            # this upstream's remote URL; otherwise fall through to the refs,
            # which cannot be refreshed by somebody else's remote.
            # The test is the CLAUSE git writes - `branch '<name>' of <url>` -
            # not a bare URL substring, so a `git fetch origin some-other-branch`
            # is correctly rejected rather than dating an observation it never
            # refreshed. The trailing `.git` is stripped because git records the
            # remote WITHOUT it while `remote get-url` returns it WITH: matching
            # the raw URL rejected every correctly-fetched FETCH_HEAD on the
            # reference host, silently downgrading a good measurement to a
            # coarser source.
            UPSTREAM_REMOTE="${UPSTREAM%%/*}"
            UPSTREAM_BRANCH="${UPSTREAM#*/}"
            REMOTE_URL="$("$GIT_BIN" -C "$CHECKOUT" remote get-url "$UPSTREAM_REMOTE" 2>/dev/null || true)"
            FETCH_HEAD_IS_OURS=0
            if [ -n "$FETCH_HEAD_FILE" ] && [ -f "$FETCH_HEAD_FILE" ] && [ -n "$REMOTE_URL" ]; then
                while IFS= read -r fh_line; do
                    # `<sha>\t[not-for-merge]\tbranch '<name>' of <url>` - the
                    # URL runs to end of line, so an exact whole-clause compare
                    # is available and a substring test is never needed.
                    fh_clause="${fh_line#*	}"
                    fh_clause="${fh_clause#*	}"
                    for url in "$REMOTE_URL" "${REMOTE_URL%.git}"; do
                        if [ "$fh_clause" = "branch '$UPSTREAM_BRANCH' of $url" ]; then
                            FETCH_HEAD_IS_OURS=1
                            break 2
                        fi
                    done
                done < "$FETCH_HEAD_FILE"
            fi
            if [ "$FETCH_HEAD_IS_OURS" -eq 1 ]; then
                FETCH_AGE_SOURCE="fetch-head"
                REF_FILE="$FETCH_HEAD_FILE"
            elif [ -n "$GITDIR" ]; then
                for candidate in "loose-ref:$GITDIR/refs/remotes/$UPSTREAM" \
                                 "packed-refs:$GITDIR/packed-refs"; do
                    if [ -f "${candidate#*:}" ]; then
                        FETCH_AGE_SOURCE="${candidate%%:*}"
                        REF_FILE="${candidate#*:}"
                        break
                    fi
                done
            fi
            if [ -n "$REF_FILE" ]; then
                REF_MTIME="$(stat -c %Y "$REF_FILE" 2>/dev/null || echo '')"
                if [ -n "$REF_MTIME" ]; then
                    NOW="$(date +%s)"
                    FETCH_AGE=$(( NOW - REF_MTIME ))
                    [ "$FETCH_AGE" -lt 0 ] && FETCH_AGE=0
                else
                    FETCH_AGE_SOURCE="-"
                fi
            fi
        fi
    fi
fi

[ -n "$REASON" ] || REASON="-"

age_clause() {
    if [ "$FETCH_AGE" = "-" ]; then
        printf 'fetch age unknown'
    else
        printf 'last fetched %sh ago' "$(( FETCH_AGE / 3600 ))"
    fi
}

case "$MODE" in
    quiet)
        # ONE line, and only when a reader must act. `current` is the common
        # case on a healthy host and printing it every session start would
        # train everyone to skip the line that matters.
        case "$VERDICT" in
            behind)
                echo "CPP toolchain: the executing checkout is ${BEHIND} commit(s) BEHIND ${UPSTREAM} ($(age_clause)) - instruments here predate what main ships (#1029)" ;;
            diverged)
                echo "CPP toolchain: the executing checkout has diverged from ${UPSTREAM} (${AHEAD} ahead, ${BEHIND} behind, $(age_clause)) (#1029)" ;;
            unknown)
                echo "CPP toolchain: provenance UNKNOWN (${REASON}) - this is not a measured zero (#1029)" ;;
            current)
                if [ "$FETCH_AGE" = "-" ]; then
                    echo "CPP toolchain: at the tip of ${UPSTREAM}, but the age of that reference is UNKNOWN - the gap is not evidence about the remote now (#1029)"
                elif [ "$FETCH_AGE" -gt "$STALE_EVIDENCE_SECONDS" ] 2>/dev/null; then
                    echo "CPP toolchain: at the tip of ${UPSTREAM}, but that reference was last refreshed $(( FETCH_AGE / 3600 ))h ago (source: ${FETCH_AGE_SOURCE}) - a zero gap against old evidence (#1029)"
                fi ;;
        esac
        exit 0 ;;
    json)
        num_or_null() { [ "$1" = "-" ] && printf 'null' || printf '%s' "$1"; }
        # Escape before quoting. A checkout path containing `"` or `\` produced
        # invalid JSON, and every consumer of --json - install-drift, the wave
        # registry - parses this. Backslash first, or it doubles the escapes it
        # just inserted; control characters become spaces rather than raw bytes.
        json_escape() {
            # `tr` first, for the separators sed can never see: sed works one
            # newline-delimited record at a time, so `[[:cntrl:]]` matched every
            # control character EXCEPT the newlines between records, and a value
            # containing one produced invalid JSON with an exit status of 0.
            printf '%s' "$1" | tr '\n\r\t' '   ' |
                sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/[[:cntrl:]]/ /g'
        }
        str_or_null() { [ "$1" = "-" ] && printf 'null' || printf '"%s"' "$(json_escape "$1")"; }
        printf '{"verdict":"%s","checkout":%s,"head":%s,"upstream":%s,"behind":%s,"ahead":%s,"fetch_age_seconds":%s,"fetch_age_source":%s,"reason":%s}\n' \
            "$VERDICT" \
            "$(str_or_null "${CHECKOUT:--}")" \
            "$(str_or_null "$HEAD_SHA")" \
            "$(str_or_null "$UPSTREAM")" \
            "$(num_or_null "$BEHIND")" \
            "$(num_or_null "$AHEAD")" \
            "$(num_or_null "$FETCH_AGE")" \
            "$(str_or_null "$FETCH_AGE_SOURCE")" \
            "$(str_or_null "$REASON")"
        exit 0 ;;
esac

echo "toolchain-provenance: checkout ${CHECKOUT:-<none>}"
echo "  head               $HEAD_SHA"
echo "  upstream           $UPSTREAM"
echo "  behind / ahead     $BEHIND / $AHEAD"
if [ "$FETCH_AGE" = "-" ]; then
    echo "  evidence age       unknown - the gap above is measured against a remote-tracking ref of unknown freshness"
else
    echo "  evidence age       ${FETCH_AGE}s (source: $FETCH_AGE_SOURCE)"
    if [ "$FETCH_AGE_SOURCE" = "packed-refs" ]; then
        echo "                     packed-refs is COARSE - it bounds staleness and does not date the fetch"
    fi
fi
if [ "$REASON" != "-" ]; then
    echo "  reason             $REASON"
fi
echo ""
case "$VERDICT" in
    current)
        echo "The executing checkout is at the tip of $UPSTREAM." ;;
    behind)
        echo "The executing checkout is ${BEHIND} commit(s) BEHIND $UPSTREAM."
        echo "Anything merged in those commits is NOT reachable from the helpers this host runs,"
        echo "even though 'git log $UPSTREAM' shows it shipped (issue #1029, specimen 1)."
        echo "Pull at a declared safe moment - scripts/checkout-readers.sh says when no gate is"
        echo "running out of this tree, and names the supervisors to re-arm afterwards." ;;
    ahead)
        echo "The executing checkout carries ${AHEAD} commit(s) $UPSTREAM does not have."
        echo "Not stale, but not what a reviewer read either." ;;
    diverged)
        echo "The executing checkout has DIVERGED from $UPSTREAM (${AHEAD} ahead, ${BEHIND} behind)." ;;
    unknown)
        echo "Provenance could not be measured: $REASON"
        echo "This is NOT a gap of zero. An unmeasurable checkout and a current one are"
        echo "different answers, and only one of them is evidence (issue #1029)." ;;
esac
# The house KEY=value contract (the `flow-start-resolve.sh` shape), so a shell
# consumer reads fields by key instead of pulling them back out of JSON with a
# regex - which truncated at the first escaped quote and could re-emit a broken
# value into the caller's own JSON.
echo "TOOLCHAIN_CHECKOUT=${CHECKOUT:--}"
echo "TOOLCHAIN_HEAD=$HEAD_SHA"
echo "TOOLCHAIN_UPSTREAM=$UPSTREAM"
echo "TOOLCHAIN_BEHIND=$BEHIND"
echo "TOOLCHAIN_AHEAD=$AHEAD"
echo "TOOLCHAIN_FETCH_AGE=$FETCH_AGE"
echo "TOOLCHAIN_FETCH_AGE_SOURCE=$FETCH_AGE_SOURCE"
echo "TOOLCHAIN_PROVENANCE: $VERDICT"
exit 0
