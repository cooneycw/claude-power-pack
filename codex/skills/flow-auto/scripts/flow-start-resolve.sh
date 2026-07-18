#!/usr/bin/env bash
# flow-start-resolve.sh - Deterministic Step-1 resolver for /flow:auto and
# /flow:start (issue #581).
#
# Motivation: flow Step 1 used to be driven by multi-line inline bash blocks
# (variable assignments, loops, command substitution). The permission matcher
# can only auto-allow commands it can decompose into allowlisted prefixes, so
# those compound blocks prompted on EVERY run regardless of allowlist tuning
# (issue #482 census evidence; the rejected sandbox lane #541/ADR 0002 attacked
# the same root cause). This helper extracts that plumbing into one audited,
# allowlistable script: it resolves the target repo (#578), fetches the issue,
# derives the issue-anchored branch, triages existing work, wraps the #503
# live-driver guard, and performs the git-lane worktree creation itself. The
# model reads the key=value contract below and makes exactly one decision:
# call EnterWorktree, or ride the git lane (cd).
#
# Resolve mode:
#   flow-start-resolve.sh <ISSUE> [PROJECT] [--allow-closed]
#
#   PROJECT        target repo when the session cwd is not the issue's repo
#                  (issue #578): tried as a path first, else
#                  $HOME/Projects/<PROJECT>.
#   --allow-closed proceed with worktree creation although the issue is not
#                  OPEN (pass only after the user has confirmed).
#
#   Prints a key=value contract (stdout), one value per line:
#     LANE=current-branch|fresh|resume|remote-pickup|cross-repo
#     CROSS_REPO=0|1        1 = the target repo is not the session repo (#578)
#     GIT_LANE=0|1          1 = ride the git lane end-to-end: enter with `cd`,
#                           never EnterWorktree, git cleanup at Step 7. Set for
#                           cross-repo runs, when FLOW_WORKTREE_BASE is set
#                           (issue #584, ADR 0003), and when a resumed worktree
#                           lies outside the target repo
#     TARGET_REPO=<abs path of the primary checkout>
#     ISSUE_STATE=OPEN|CLOSED|MERGED
#     ISSUE_TITLE=<title, whitespace flattened>
#     BRANCH=<issue-N-slug branch this run must be on>
#     WT_PATH=<abs path of the worktree to enter (or create, LANE=fresh)>
#                           honors FLOW_WORKTREE_BASE (#584):
#                           $FLOW_WORKTREE_BASE/<repo>-<branch> when set, else
#                           <target repo>/.claude/worktrees/<branch>
#     DEFAULT_BRANCH=<default branch name>
#     REMOTE_BRANCH=origin/<...>       (remote-pickup lane only)
#     WT_CREATED=0|1        1 = this run already ran `git worktree add`
#     LIVE_DRIVER=clear|suspected|unknown|skipped  (#503 guard, resume lane)
#     PR_HEAD=none|<number>:<state>|unknown        (resume shipped-PR hazard)
#     CONFIRM_REQUIRED=0|1  1 = STOP: explicit user confirmation needed
#                           (suspected live driver, existing open/merged PR,
#                           or non-OPEN issue without --allow-closed)
#     FLOW_START_RESOLVE: ok
#   On a hard error: ERROR=<reason> then `FLOW_START_RESOLVE: error`, exit 1.
#
# Verify mode (run from INSIDE the entered worktree - the Step-1 gate):
#   flow-start-resolve.sh --verify <ISSUE> [EXPECTED_BRANCH]
#
#   Fails (FLOW_START_VERIFY: fail, exit 1) when the checkout is still on
#   main/master or detached; renames a non-issue-anchored branch to
#   EXPECTED_BRANCH so downstream steps can parse the issue number. On success
#   prints BRANCH= and WT_ROOT= then `FLOW_START_VERIFY: ok`.
#
# Env:
#   FLOW_WORKTREE_BASE               worktree base override (issue #584, ADR
#                                    0003 Option A; host config, never shipped)
# Env (test hooks - unset in normal use):
#   FLOW_START_RESOLVE_GH            override the `gh` binary
#   FLOW_START_RESOLVE_PROJECTS_DIR  override $HOME/Projects for name lookup
#   (FLOW_LIVE_DRIVER_NOW passes through to the wrapped live-driver guard.)

set -uo pipefail

GH="${FLOW_START_RESOLVE_GH:-gh}"
PROJECTS_DIR="${FLOW_START_RESOLVE_PROJECTS_DIR:-$HOME/Projects}"

fail() {
  echo "ERROR=$1"
  echo "FLOW_START_RESOLVE: error"
  exit 1
}

usage_fail() { echo "flow-start-resolve: $1" >&2; exit 2; }

# Given any checkout path, print the PRIMARY checkout's toplevel (a linked
# worktree resolves to the main repo that owns it).
resolve_primary() {
  local common
  common=$("$GIT" -C "$1" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 1
  (cd "$common/.." 2>/dev/null && pwd)
}

# create_worktree PATH BRANCH START_REF - reuse an existing local branch if
# one is left over from earlier work, else branch from START_REF. git worktree
# chatter goes to stderr so the stdout contract stays clean.
create_worktree() {
  [ -n "${FLOW_WORKTREE_BASE:-}" ] && mkdir -p "$FLOW_WORKTREE_BASE"
  if "$GIT" -C "$TARGET_REPO" show-ref --verify --quiet "refs/heads/$2"; then
    "$GIT" -C "$TARGET_REPO" worktree add "$1" "$2" >&2
  else
    "$GIT" -C "$TARGET_REPO" worktree add -b "$2" "$1" "$3" >&2
  fi
}

GIT=git

# ---- argument parsing -------------------------------------------------------
MODE=resolve
ALLOW_CLOSED=0
ISSUE_NUM=""
PROJECT=""
EXPECTED_BRANCH=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --verify) MODE=verify ;;
    --allow-closed) ALLOW_CLOSED=1 ;;
    --help|-h)
      sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    --*) usage_fail "unknown option: $1" ;;
    *)
      if [ -z "$ISSUE_NUM" ]; then
        ISSUE_NUM="$1"
      elif [ "$MODE" = verify ] && [ -z "$EXPECTED_BRANCH" ]; then
        EXPECTED_BRANCH="$1"
      elif [ "$MODE" = resolve ] && [ -z "$PROJECT" ]; then
        PROJECT="$1"
      else
        usage_fail "unexpected argument: $1"
      fi
      ;;
  esac
  shift
done

[ -n "$ISSUE_NUM" ] || usage_fail "usage: flow-start-resolve.sh <ISSUE> [PROJECT] [--allow-closed] | --verify <ISSUE> [EXPECTED_BRANCH]"
printf '%s' "$ISSUE_NUM" | grep -qE '^[0-9]+$' || usage_fail "ISSUE must be a number, got: $ISSUE_NUM"

# ---- verify mode: the post-entry gate ---------------------------------------
if [ "$MODE" = verify ]; then
  if ! "$GIT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR=not inside a git work tree - enter the worktree before --verify"
    echo "FLOW_START_VERIFY: fail"
    exit 1
  fi
  CURRENT=$("$GIT" branch --show-current 2>/dev/null || true)
  if [ -z "$CURRENT" ] || [ "$CURRENT" = main ] || [ "$CURRENT" = master ]; then
    echo "ERROR=still on '${CURRENT:-detached HEAD}' - the worktree switch did not happen; cannot proceed"
    echo "FLOW_START_VERIFY: fail"
    exit 1
  fi
  case "$CURRENT" in
    issue-"$ISSUE_NUM"-*) : ;;  # already issue-anchored - keep it
    *)
      if [ -z "$EXPECTED_BRANCH" ]; then
        echo "ERROR=branch '$CURRENT' is not issue-anchored (issue-${ISSUE_NUM}-*) and no EXPECTED_BRANCH was given to normalize to"
        echo "FLOW_START_VERIFY: fail"
        exit 1
      fi
      if ! "$GIT" branch -m "$EXPECTED_BRANCH"; then
        echo "ERROR=failed to rename branch '$CURRENT' to '$EXPECTED_BRANCH'"
        echo "FLOW_START_VERIFY: fail"
        exit 1
      fi
      echo "flow-start-resolve: normalized branch '$CURRENT' -> '$EXPECTED_BRANCH'" >&2
      CURRENT="$EXPECTED_BRANCH"
      ;;
  esac
  echo "BRANCH=$CURRENT"
  echo "WT_ROOT=$("$GIT" rev-parse --show-toplevel)"
  echo "FLOW_START_VERIFY: ok"
  exit 0
fi

# ---- target-repo resolution (issue #578) ------------------------------------
TARGET_REPO=""
if [ -n "$PROJECT" ]; then
  for cand in "$PROJECT" "$PROJECTS_DIR/$PROJECT"; do
    if [ -d "$cand" ] && "$GIT" -C "$cand" rev-parse --show-toplevel >/dev/null 2>&1; then
      TARGET_REPO=$(resolve_primary "$cand")
      break
    fi
  done
  [ -n "$TARGET_REPO" ] || fail "PROJECT '$PROJECT' is not a git checkout (tried '$PROJECT' and '$PROJECTS_DIR/$PROJECT')"
else
  TARGET_REPO=$(resolve_primary . || true)
  [ -n "$TARGET_REPO" ] || fail "session cwd is not inside a git repo and no PROJECT was given - re-run as: flow-start-resolve.sh $ISSUE_NUM <PROJECT>"
fi

SESSION_PRIMARY=$(resolve_primary . 2>/dev/null || true)
CROSS_REPO=1
[ -n "$SESSION_PRIMARY" ] && [ "$SESSION_PRIMARY" = "$TARGET_REPO" ] && CROSS_REPO=0

# Git lane (issues #578, #584): cross-repo runs and base-override runs never
# use EnterWorktree - the native tool cannot reach another repo, its base dir
# is not configurable, and out-of-repo EnterWorktree(path=...) triggers an
# unsuppressable approval prompt (ADR 0003 constraint 2).
GIT_LANE=$CROSS_REPO
[ -n "${FLOW_WORKTREE_BASE:-}" ] && GIT_LANE=1

# Worktree path for a branch, honoring the #584 base override.
wt_path_for() {
  if [ -n "${FLOW_WORKTREE_BASE:-}" ]; then
    echo "$FLOW_WORKTREE_BASE/$(basename "$TARGET_REPO")-$1"
  else
    echo "$TARGET_REPO/.claude/worktrees/$1"
  fi
}

# ---- issue fetch + state check ----------------------------------------------
# gh resolves the repo from its cwd, so run it from the TARGET repo.
ISSUE_STATE=$(cd "$TARGET_REPO" && "$GH" issue view "$ISSUE_NUM" --json state --jq .state 2>/dev/null) || true
[ -n "${ISSUE_STATE:-}" ] || fail "could not fetch issue #$ISSUE_NUM via gh in $TARGET_REPO (not found, or gh unauthenticated)"
ISSUE_TITLE=$(cd "$TARGET_REPO" && "$GH" issue view "$ISSUE_NUM" --json title --jq .title 2>/dev/null | tr '\n\t' '  ' | sed 's/[[:space:]]*$//') || true
[ -n "${ISSUE_TITLE:-}" ] || ISSUE_TITLE="(no title)"

CREATE_OK=1
CONFIRM_REQUIRED=0
if [ "$ISSUE_STATE" != "OPEN" ] && [ "$ALLOW_CLOSED" -ne 1 ]; then
  CREATE_OK=0
  CONFIRM_REQUIRED=1
  echo "flow-start-resolve: issue #$ISSUE_NUM is $ISSUE_STATE - confirm with the user, then re-run with --allow-closed to create the worktree." >&2
fi

# ---- branch derivation ------------------------------------------------------
SLUG=$(printf '%s' "$ISSUE_TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//' | cut -c1-50)
SLUG=$(printf '%s' "$SLUG" | sed 's/-$//')
[ -n "$SLUG" ] || SLUG=work
BRANCH="issue-${ISSUE_NUM}-${SLUG}"

# ---- remote sync + default branch -------------------------------------------
if ! "$GIT" -C "$TARGET_REPO" fetch origin --quiet 2>/dev/null; then
  echo "flow-start-resolve: 'git fetch origin' failed in $TARGET_REPO (no remote or offline) - remote-pickup detection may be stale." >&2
fi

DEFAULT_BRANCH=$("$GIT" -C "$TARGET_REPO" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true)
DEFAULT_BRANCH=${DEFAULT_BRANCH#origin/}
if [ -z "$DEFAULT_BRANCH" ]; then
  for cand in main master; do
    if "$GIT" -C "$TARGET_REPO" show-ref --verify --quiet "refs/remotes/origin/$cand" ||
      "$GIT" -C "$TARGET_REPO" show-ref --verify --quiet "refs/heads/$cand"; then
      DEFAULT_BRANCH="$cand"
      break
    fi
  done
fi
DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}
BASE_REF="origin/$DEFAULT_BRANCH"
"$GIT" -C "$TARGET_REPO" show-ref --verify --quiet "refs/remotes/origin/$DEFAULT_BRANCH" || BASE_REF="$DEFAULT_BRANCH"

# ---- existing-work triage ---------------------------------------------------
LANE=""
WT_PATH=""
REMOTE_BRANCH=""
WT_CREATED=0
LIVE_DRIVER=skipped
PR_HEAD=none

# 1. Already on the issue's branch in the session cwd (same repo only).
SESSION_BRANCH=$("$GIT" branch --show-current 2>/dev/null || true)
case "$SESSION_BRANCH" in
  issue-"$ISSUE_NUM"-*)
    if [ "$CROSS_REPO" -eq 0 ]; then
      LANE=current-branch
      BRANCH="$SESSION_BRANCH"
      WT_PATH=$("$GIT" rev-parse --show-toplevel)
    fi
    ;;
esac

# 2. A worktree for this issue already exists (prior session).
if [ -z "$LANE" ]; then
  found_path=""
  found_branch=""
  cur_path=""
  while IFS= read -r line; do
    case "$line" in
      "worktree "*) cur_path="${line#worktree }" ;;
      "branch refs/heads/issue-${ISSUE_NUM}-"*)
        found_path="$cur_path"
        found_branch="${line#branch refs/heads/}"
        ;;
    esac
  done < <("$GIT" -C "$TARGET_REPO" worktree list --porcelain 2>/dev/null)
  if [ -n "$found_path" ]; then
    LANE=resume
    BRANCH="$found_branch"
    WT_PATH="$found_path"
    # A worktree outside the target repo (a base-override checkout from a
    # prior run, #584) cannot be entered via EnterWorktree(path=...) without
    # an unsuppressable approval prompt - commit to the git lane.
    case "$WT_PATH" in
      "$TARGET_REPO"/*) : ;;
      *) GIT_LANE=1 ;;
    esac
  fi
fi

if [ "$LANE" = resume ]; then
  # #503 live-driver guard (sibling script; advisory, fail-open when absent).
  SELF_DIR=$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")
  GUARD="$SELF_DIR/flow-live-driver-guard.sh"
  if [ -f "$GUARD" ]; then
    guard_out=$(bash "$GUARD" "$WT_PATH") || true
    LIVE_DRIVER=$(printf '%s\n' "$guard_out" | sed -n 's/^FLOW_LIVE_DRIVER: //p' | tail -1)
    LIVE_DRIVER=${LIVE_DRIVER:-unknown}
  fi
  [ "$LIVE_DRIVER" = suspected ] && CONFIRM_REQUIRED=1

  # The other resume hazard: this branch already has an open/merged PR.
  PR_HEAD=$(cd "$TARGET_REPO" && "$GH" pr list --head "$BRANCH" --state all --json number,state \
    --jq '[.[] | select(.state == "OPEN" or .state == "MERGED")][0] | if . == null then "none" else "\(.number):\(.state)" end' 2>/dev/null) || true
  PR_HEAD=${PR_HEAD:-unknown}
  case "$PR_HEAD" in
    *:*)
      CONFIRM_REQUIRED=1
      echo "flow-start-resolve: branch '$BRANCH' already has PR $PR_HEAD - possible concurrent or already-shipped work; confirm before entering." >&2
      ;;
  esac
fi

# 3. A remote branch exists but no local worktree (cross-machine pickup).
if [ -z "$LANE" ]; then
  REMOTE_BRANCH=$("$GIT" -C "$TARGET_REPO" branch -r --list "origin/issue-${ISSUE_NUM}-*" 2>/dev/null | head -1 | sed 's/^[ *+]*//;s/ .*$//')
  if [ -n "$REMOTE_BRANCH" ]; then
    LANE=remote-pickup
    BRANCH="${REMOTE_BRANCH#origin/}"
    WT_PATH=$(wt_path_for "$BRANCH")
    if [ "$CREATE_OK" -eq 1 ]; then
      create_worktree "$WT_PATH" "$BRANCH" "$REMOTE_BRANCH" ||
        fail "git worktree add for '$BRANCH' from '$REMOTE_BRANCH' failed in $TARGET_REPO"
      WT_CREATED=1
    fi
  fi
fi

# 4. Fresh start. The native lane (EnterWorktree) creates the worktree
#    itself; the git lane (#578 cross-repo, #584 base override) cannot use
#    EnterWorktree, so create here.
if [ -z "$LANE" ]; then
  WT_PATH=$(wt_path_for "$BRANCH")
  if [ "$CROSS_REPO" -eq 1 ]; then
    LANE=cross-repo
  else
    LANE=fresh
  fi
  if [ "$GIT_LANE" -eq 1 ] && [ "$CREATE_OK" -eq 1 ]; then
    create_worktree "$WT_PATH" "$BRANCH" "$BASE_REF" ||
      fail "git worktree add for '$BRANCH' from '$BASE_REF' failed in $TARGET_REPO"
    WT_CREATED=1
  fi
fi

# ---- contract ---------------------------------------------------------------
echo "LANE=$LANE"
echo "CROSS_REPO=$CROSS_REPO"
echo "GIT_LANE=$GIT_LANE"
echo "TARGET_REPO=$TARGET_REPO"
echo "ISSUE_STATE=$ISSUE_STATE"
echo "ISSUE_TITLE=$ISSUE_TITLE"
echo "BRANCH=$BRANCH"
echo "WT_PATH=$WT_PATH"
echo "DEFAULT_BRANCH=$DEFAULT_BRANCH"
if [ -n "$REMOTE_BRANCH" ]; then
  echo "REMOTE_BRANCH=$REMOTE_BRANCH"
fi
echo "WT_CREATED=$WT_CREATED"
echo "LIVE_DRIVER=$LIVE_DRIVER"
echo "PR_HEAD=$PR_HEAD"
echo "CONFIRM_REQUIRED=$CONFIRM_REQUIRED"
echo "FLOW_START_RESOLVE: ok"
exit 0
