#!/bin/sh
# Case runner for controls/flow-worktree-sweep-apply (issue #1726).
#
#   run-case.sh <case-dir> <gate>
#
# Builds a repository with one linked worktree and runs the sweep with
# `--apply`: the mode that DELETES. The sweep's other control
# (controls/flow-worktree-sweep) is dry-run only and scores what the sweep
# says; this one scores what is left on disk afterwards.
#
# facts.txt:
#   pr=merged-at-tip     GitHub saw exactly the local tip merged
#   pr=merged-behind     the PR merged, and the worktree has a commit after it
#   pr=lookup-fails      `gh` cannot answer
#
# THE FINDING IS "the sweep did not treat this worktree as safely finished":
# it kept it for a reason that names work, or it could not tell and said so
# (`undecidable`, the run `partial`). No finding: the worktree was removed, or
# it was skipped as having no finished PR with the run reported clean.
#
# THIS RUNNER DELETES, AND SO DOES ITS ANCHOR - a naive sweep written to be
# blind. So it owns its target completely: everything is created under one
# mktemp directory, the repository is named by `--repo` and by nothing in the
# environment, and before the gate or the anchor is invoked every worktree git
# lists for that repository must lie under that directory. If one does not,
# the runner refuses and invokes nothing. `outside=1` in facts.txt builds
# exactly that situation, so the refusal itself can be shown.
set -u
case_dir="$1"
gate="$2"
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
N="FLOW_WORKTREE_SWEEP_APPLY_CONTROL"
command -v git >/dev/null 2>&1 || { echo "$N: unavailable - git is not installed"; exit 3; }
command -v bash >/dev/null 2>&1 || { echo "$N: unavailable - bash is not installed"; exit 3; }
fact() { sed -n "s/^$1=//p" "$case_dir/facts.txt" 2>/dev/null | head -1; }
PR=$(fact pr)
OUTSIDE=$(fact outside)
case "$PR" in merged-at-tip|merged-behind|lookup-fails) ;; *) echo "$N: cannot-run - bad pr '$PR'"; exit 2 ;; esac

# GIT IS TOLD ABOUT ITS REPOSITORY BY PATH AND BY NOTHING ELSE. A caller's
# GIT_DIR, GIT_WORK_TREE or GIT_INDEX_FILE would make `git -C <fixture>` act on
# the CALLER's repository and commit its staged changes; an inherited
# GIT_CONFIG_COUNT or GIT_TEMPLATE_DIR would run somebody's hooks on the
# fixture's commits. So every GIT_* variable is dropped, by pattern and not by
# a list of the ones thought of, configuration is confined to what follows,
# and hooks are off for the fixture and for the gate alike.
for inherited in $(env | sed -n 's/^\(GIT_[A-Za-z0-9_]*\)=.*/\1/p'); do unset "$inherited"; done
# The helpers under test take their own overrides from the environment too
# (FLOW_CLAIM_GIT, FLOW_WORKTREE_GIT, WORKTREE_REMOVE_*, ...): a test stub or a
# wrapper left there by the session would replace git inside the gate. Those go
# the same way, by prefix; the ones this runner means to set are set below.
for inherited in $(env | sed -n 's/^\(\(FLOW\|WORKTREE_REMOVE\|GH_PR_MERGE\)_[A-Za-z0-9_]*\)=.*/\1/p'); do unset "$inherited"; done
GIT_CONFIG_GLOBAL=/dev/null
GIT_CONFIG_SYSTEM=/dev/null
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_COUNT=1
GIT_CONFIG_KEY_0=core.hooksPath
GIT_CONFIG_VALUE_0=/dev/null
export GIT_CONFIG_GLOBAL GIT_CONFIG_SYSTEM GIT_CONFIG_NOSYSTEM GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0

raw=$(mktemp -d) || { echo "$N: unavailable - no tmpdir"; exit 3; }
elsewhere=""
# shellcheck disable=SC2317  # reached through the trap below
cleanup() { rm -rf "$raw"; [ -n "$elsewhere" ] && rm -rf "$elsewhere"; }
trap cleanup EXIT INT TERM
T=$(cd "$raw" && pwd -P) || { echo "$N: cannot-run - tmpdir unreadable"; exit 2; }
if git -C "$T" rev-parse --git-dir >/dev/null 2>&1; then
  echo "$N: cannot-run - the temporary directory is inside a git repository"; exit 2
fi

G() { git -c user.email=fixture@example.invalid -c user.name=fixture -c commit.gpgsign=false "$@"; }
REPO="$T/repo"
WT="$T/repo-issue-4242"
BRANCH="issue-4242-fixture"
{
  mkdir "$REPO" "$T/no-template" &&
  G -C "$REPO" init -q -b main --template="$T/no-template" &&
  G -C "$REPO" commit -q --allow-empty -m "fixture base" &&
  G -C "$REPO" remote add origin https://github.com/fixture-owner/fixture-repo.git &&
  G -C "$REPO" worktree add -q -b "$BRANCH" "$WT"
} >/dev/null 2>&1 || { echo "$N: cannot-run - could not build the fixture repository"; exit 2; }
MERGED=$(git -C "$WT" rev-parse HEAD)
if [ "$PR" = merged-behind ]; then
  G -C "$WT" commit -q --allow-empty -m "work after the merge, never pushed" >/dev/null 2>&1 ||
    { echo "$N: cannot-run - could not add the unpushed commit"; exit 2; }
fi
if [ "$OUTSIDE" = 1 ]; then
  elsewhere=$(mktemp -d) || { echo "$N: unavailable - no second tmpdir"; exit 3; }
  G -C "$REPO" worktree add -q -b issue-9999-elsewhere "$elsewhere/wt" >/dev/null 2>&1 ||
    { echo "$N: cannot-run - could not add the outside worktree"; exit 2; }
fi

# --- the control on the control: nothing outside $T may be reachable ---------
listed=$(git -C "$REPO" worktree list --porcelain | sed -n 's/^worktree //p')
[ -n "$listed" ] || { echo "$N: cannot-run - git listed no worktrees for the fixture"; exit 2; }
outside_paths=$(printf '%s\n' "$listed" | while IFS= read -r path; do
  case "$path" in "$T"/*) ;; *) printf '%s\n' "$path" ;; esac
done)
if [ -n "$outside_paths" ]; then
  echo "$N: refused - a worktree of the fixture repository lies outside the directory this runner created;"
  echo "  nothing was invoked. A sweep with --apply, or this control's anchor, could delete it."
  exit 2
fi

mkdir "$T/bin"
if [ "$PR" = lookup-fails ]; then
  printf '#!/bin/sh\necho "gh: could not reach the API" >&2\nexit 1\n' > "$T/bin/gh"
else
  # shellcheck disable=SC2016  # the stub's own $1 and $2, written literally
  printf '#!/bin/sh\n[ "$1 $2" = "pr list" ] || exit 1\nprintf "%%s\\n" "MERGED|%s|4242"\nexit 0\n' "$MERGED" > "$T/bin/gh"
fi
chmod +x "$T/bin/gh"
P="$T/proc"
mkdir -p "$P/self" "$P/9999900" "$T/idle"
ln -s "$T" "$P/self/cwd"
ln -s "$T/idle" "$P/9999900/cwd"

out=$(cd "$T" && env PATH="$T/bin:$PATH" FLOW_WORKTREE_SWEEP_PROC_ROOT="$P" WORKTREE_REMOVE_PROC_ROOT="$P" \
          HOME="$T/home-with-no-helpers" bash "$gate" --repo "$REPO" --apply 2>&1)
status=$?
printf '%s\n' "$out"
line=$(printf '%s\n' "$out" | grep -F -e "SWEEP_WORKTREE: $WT " | head -1 || true)
disposition=${line#"SWEEP_WORKTREE: $WT "}
run=$(printf '%s\n' "$out" | sed -n 's/^FLOW_WORKTREE_SWEEP: //p' | tail -1)
[ -n "$line" ] || { echo "$N: cannot-run - the sweep reported nothing for the worktree (exit $status)"; exit 2; }
exists=no; [ -d "$WT" ] && exists=yes

case "$status:$exists:$disposition" in
  0:no:removed*)
    echo "$N: no-finding - removed; run $run"; exit 0 ;;
  0:yes:"skip pr-"*)
    echo "$N: no-finding - kept as having no finished PR; run $run"; exit 0 ;;
  0:yes:"skip unpushed"*|0:yes:"skip dirty"*|0:yes:"skip occupied"*)
    echo "$N: finding - kept, and the reason names work: $disposition"; exit 1 ;;
  3:yes:undecidable*)
    [ "$run" = partial ] || { echo "$N: cannot-run - undecidable but the run said '$run'"; exit 2; }
    echo "$N: finding - could not tell, and said so: $disposition; run partial"; exit 1 ;;
  *)
    echo "$N: cannot-run - exit $status, worktree present: $exists, disposition '$disposition', run '$run'"; exit 2 ;;
esac
