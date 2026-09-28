#!/usr/bin/env bash
# cpp-checkout-freshness.sh - fetch, then say whether the CPP checkout is behind
# origin/<branch>, and say `unknown` when that cannot be determined (issue #1282).
#
#: NEGATIVE-CONTROL: controls/cpp-checkout-freshness
#: HOST-SURFACE: none - fetches into the checkout's own remote-tracking ref and FETCH_HEAD; writes nothing outside the repository
#
# WHY IT MATTERS. The checkout is the single source for every CPP helper on the
# host: `~/.claude/scripts` is a symlink farm into `<checkout>/scripts`, and kyle
# session containers mount that directory live (kyle#1197). A checkout behind
# `origin/main` therefore means every session on the box runs superseded helpers,
# with nothing saying so. It advances only when something pulls.
#
# THE SHAPE THIS REPLACES, and must not become again. `/cpp:update` counted with
#
#     BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
#
# and printed "Already up to date!" on zero. `|| echo "0"` turns "could not
# count" - no remote-tracking ref, a detached HEAD - into a measured zero. Worse,
# the fetch before it was unchecked, so an UNREACHABLE remote left the old ref in
# place and the count was a confident number about stale information. Both
# render an unknown as clean. Here every failure is `unknown: <reason>`, and a
# count is only ever made against a ref THIS run just fetched.
#
# A READ-ONLY CHECKOUT IS A FAILED FETCH, not a fallback. A kyle container sees
# the checkout through read-only mounts, so the fetch cannot write the ref and
# the local `origin/<branch>` is whatever the host last fetched. Counting against
# it would be exactly the stale-number case above, so it reports
# `unknown: fetch failed (checkout not writable)`. There is deliberately no
# `git ls-remote` fallback: it yields a remote SHA whose objects this checkout
# may not have, which cannot be counted against honestly.
#
# Usage:
#   cpp-checkout-freshness.sh [--path <checkout>] [--branch <name>] [--log-cap <n>]
#
#   --path     the checkout to measure (DECLARED; default: the checkout holding
#              this script)
#   --branch   the origin branch to compare HEAD against (default: main). An
#              EMPTY value - what `git branch --show-current` gives on a detached
#              HEAD - is `unknown`, never a comparison against something else.
#   --log-cap  how many missing commits to list when behind (default: 10)
#
# The report always ends with exactly one line:
#   CPP_CHECKOUT_FRESHNESS: current | behind N | ahead N | diverged (ahead A, behind B) | unknown: <reason>
#
# Exit: 0 current, 3 behind/ahead/diverged, 4 unknown, 2 bad usage.
#
# Env (test seams - unset in normal use):
#   CPP_FRESHNESS_FETCH_TIMEOUT   seconds before the fetch is abandoned (default 30)

set -uo pipefail

# The DECLARED checkout is the only repository measured. An inherited GIT_DIR
# (a hook, a wrapper, a parent `git` process) overrides `git -C` and would make
# every line below describe a neighbouring repository under this one's name.
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_NAMESPACE GIT_CEILING_DIRECTORIES

SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SELF_DIR="$(cd "$(dirname "$SELF")" && pwd)"

CHECKOUT="$SELF_DIR/.."
BRANCH="main"
LOG_CAP=10
FETCH_TIMEOUT="${CPP_FRESHNESS_FETCH_TIMEOUT:-30}"

usage_error() {
    echo "cpp-checkout-freshness: $1" >&2
    exit 2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --path)    [ "$#" -ge 2 ] || usage_error "--path needs a directory"; CHECKOUT="$2"; shift 2 ;;
        --path=*)  CHECKOUT="${1#--path=}"; shift ;;
        --branch)  [ "$#" -ge 2 ] || usage_error "--branch needs a name (may be empty)"; BRANCH="$2"; shift 2 ;;
        --branch=*) BRANCH="${1#--branch=}"; shift ;;
        --log-cap) [ "$#" -ge 2 ] || usage_error "--log-cap needs a number"; LOG_CAP="$2"; shift 2 ;;
        -h|--help)
            awk 'NR==1 && /^#!/ {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$SELF"
            exit 0 ;;
        *) usage_error "unknown argument '$1' (use --path, --branch, --log-cap)" ;;
    esac
done
case "$LOG_CAP" in ''|*[!0-9]*) usage_error "--log-cap must be a non-negative integer" ;; esac

verdict() {
    echo "CPP_CHECKOUT_FRESHNESS: $1"
    exit "$2"
}

unknown() {
    verdict "unknown: $1" 4
}

if [ ! -d "$CHECKOUT" ]; then
    echo "CPP checkout: $CHECKOUT"
    unknown "checkout not found: $CHECKOUT"
fi
CHECKOUT="$(cd "$CHECKOUT" && pwd -P)"
echo "CPP checkout: $CHECKOUT"

if ! git -C "$CHECKOUT" rev-parse --git-dir >/dev/null 2>&1; then
    unknown "not a git repository"
fi
# `git -C` also accepts a directory INSIDE some repository, and would then
# measure the enclosing one under this path's name. The declared path must BE
# the worktree root.
TOPLEVEL="$(git -C "$CHECKOUT" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$TOPLEVEL" ] || [ "$(cd "$TOPLEVEL" && pwd -P)" != "$CHECKOUT" ]; then
    unknown "not a checkout root (inside ${TOPLEVEL:-an unresolvable repository})"
fi

# The checkout's own branch is reported whatever is being compared: a primary
# checkout left on a feature branch serves THAT branch's helpers to every
# session, which is a different warning from being behind.
CURRENT="$(git -C "$CHECKOUT" branch --show-current 2>/dev/null || true)"
HEAD_SHA="$(git -C "$CHECKOUT" rev-parse --short HEAD 2>/dev/null || true)"
if [ -z "$CURRENT" ]; then
    echo "Branch: (detached HEAD at ${HEAD_SHA:-?}) - sessions are served whatever this commit holds"
elif [ "$CURRENT" != "main" ]; then
    echo "Branch: $CURRENT (NOT main - every session served by this checkout runs this branch's helpers)"
else
    echo "Branch: main"
fi

if [ -z "$BRANCH" ]; then
    unknown "no branch to compare against (detached HEAD)"
fi
UPSTREAM="origin/$BRANCH"
# Counted by FULL ref name: the shorthand `origin/main` resolves a local tag or
# branch of that name before the remote-tracking ref this run fetched.
UPSTREAM_REF="refs/remotes/origin/$BRANCH"

if ! git -C "$CHECKOUT" remote get-url origin >/dev/null 2>&1; then
    unknown "no 'origin' remote"
fi

# THE FETCH IS CHECKED, and a failure is terminal. Non-interactive: a remote
# that wants credentials must fail, not wait on a prompt nobody will answer.
# Bounded twice: `timeout` where it exists, and git's own low-speed abort for
# HTTP(S) remotes, which holds where `timeout` does not (macOS without
# coreutils). An SSH remote on a host with no `timeout` is NOT bounded.
TIMEOUT_CMD=()
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_CMD=(timeout "$FETCH_TIMEOUT")
fi
# `${arr[@]+"${arr[@]}"}`, never a bare `"${arr[@]}"`: under `set -u`, bash
# before 4.4 (macOS's /bin/bash is 3.2) treats an EMPTY array as unbound, so on
# exactly the host with no `timeout` every fetch died and read `unknown`.
FETCH_ERR="$(GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=true ${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"} \
    git -C "$CHECKOUT" -c http.lowSpeedLimit=1 -c "http.lowSpeedTime=$FETCH_TIMEOUT" \
    fetch --quiet origin \
    "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" 2>&1)"
FETCH_STATUS=$?
if [ "$FETCH_STATUS" -ne 0 ]; then
    COMMON_DIR="$(git -C "$CHECKOUT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
    if [ -n "$COMMON_DIR" ] && { [ ! -w "$COMMON_DIR" ] || [ ! -w "$COMMON_DIR/refs" ]; }; then
        unknown "fetch failed (checkout not writable)"
    fi
    if [ "$FETCH_STATUS" -eq 124 ] && [ "${#TIMEOUT_CMD[@]}" -gt 0 ]; then
        unknown "fetch failed (timed out after ${FETCH_TIMEOUT}s)"
    fi
    # git's first `fatal:`/`error:` line names the cause; its tail is often a
    # continuation ("and the repository exists.") that names nothing.
    WHY="$(printf '%s\n' "$FETCH_ERR" | grep -m1 -E '^(fatal|error):' || true)"
    [ -n "$WHY" ] || WHY="$(printf '%s\n' "$FETCH_ERR" | sed '/^[[:space:]]*$/d' | head -1)"
    unknown "fetch failed (${WHY:-git fetch exited $FETCH_STATUS})"
fi

# A shallow clone's history stops at its boundary, so `rev-list` can report two
# connected commits as diverged. Its counts are not a measurement.
if [ "$(git -C "$CHECKOUT" rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
    unknown "shallow clone - ancestry is incomplete, so no count is trustworthy"
fi
if ! git -C "$CHECKOUT" rev-parse --verify --quiet "$UPSTREAM_REF" >/dev/null 2>&1; then
    unknown "$UPSTREAM does not exist after the fetch"
fi
UP_SHA="$(git -C "$CHECKOUT" rev-parse --short "$UPSTREAM_REF" 2>/dev/null || echo '?')"
echo "HEAD: ${HEAD_SHA:-?}   $UPSTREAM: $UP_SHA"

COUNTS="$(git -C "$CHECKOUT" rev-list --left-right --count "HEAD...$UPSTREAM_REF" 2>/dev/null || true)"
AHEAD="${COUNTS%%[[:space:]]*}"
BEHIND="${COUNTS##*[[:space:]]}"
if [[ ! "$AHEAD" =~ ^[0-9]+$ || ! "$BEHIND" =~ ^[0-9]+$ ]]; then
    unknown "could not count commits between HEAD and $UPSTREAM"
fi

if [ "$BEHIND" -gt 0 ]; then
    echo ""
    echo "Missing from this checkout ($UPSTREAM has $BEHIND commit(s) HEAD does not):"
    git -C "$CHECKOUT" log --oneline -n "$LOG_CAP" "HEAD..$UPSTREAM_REF" 2>/dev/null | sed 's/^/  /'
    if [ "$BEHIND" -gt "$LOG_CAP" ]; then
        echo "  ... and $((BEHIND - LOG_CAP)) more"
    fi
    echo ""
fi

if [ "$BEHIND" -gt 0 ] && [ "$AHEAD" -gt 0 ]; then
    verdict "diverged (ahead $AHEAD, behind $BEHIND)" 3
elif [ "$BEHIND" -gt 0 ]; then
    verdict "behind $BEHIND" 3
elif [ "$AHEAD" -gt 0 ]; then
    verdict "ahead $AHEAD" 3
fi
verdict "current" 0
