#!/bin/sh
# Case runner for controls/flow-worktree-sweep (issue #1281, ADR 0008 row 8).
#
# THE FIXTURE IS BUILT, NEVER THE LIVE HOST. The sweep's subject is "which of
# THIS repository's linked worktrees may be removed", so a control that pointed
# it at the checkout it lives in would measure that checkout - and would put a
# destructive instrument's attention on real work. Each case gets a throwaway
# repository outside every checkout, one linked worktree, a stub `gh` that
# answers the PR lookup from the case's facts, and a FAKE /proc tree supplied
# through the gate's own FLOW_WORKTREE_SWEEP_PROC_ROOT seam.
#
# DRY-RUN ONLY. The sweep is never given --apply here, so nothing is removed and
# worktree-remove.sh is never reached. What is controlled is the CLASSIFICATION
# that --apply acts on, not the removal path; control.json's `limits` says so.
#
# THE CASES NAME NO ANSWER. A case's facts.txt holds facts about the worktree
# (PR state, whether its tip is what merged, dirt, where a process sits) and
# nothing about the expected disposition. The discriminator is the GATE'S OWN
# `SWEEP_WORKTREE:` line for that worktree.
#
# Markers, and why three and not two:
#   unavailable - <tool> is not installed    the ONLY thing declared as
#                                            unavailable_signal: a missing tool
#                                            is an environment fact (#1117)
#   cannot-run - ...                         anything else that stops a case -
#                                            deliberately matches no declared
#                                            signal, so the harness reports it
#                                            loudly (UNSIGNALLED), never as a
#                                            clean pass or a detection
#   finding - ...                            the gate reported this worktree
#                                            REMOVABLE
set -u
case_dir="$1"
gate="$2"
# Absolute, because the gate is run from inside the fixture directory below.
case "$gate" in /*) ;; *) gate="$PWD/$gate" ;; esac
case "$case_dir" in /*) ;; *) case_dir="$PWD/$case_dir" ;; esac

command -v git >/dev/null 2>&1 || { echo "FLOW_WORKTREE_SWEEP_CONTROL: unavailable - git is not installed"; exit 3; }
command -v bash >/dev/null 2>&1 || { echo "FLOW_WORKTREE_SWEEP_CONTROL: unavailable - bash is not installed"; exit 3; }

fixture="$case_dir/facts.txt"
[ -f "$fixture" ] || { echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - case has no facts.txt"; exit 3; }

# Read facts by key; never source the case (a fixture is data, not code).
fact() { sed -n "s/^$1=//p" "$fixture" | head -1; }
PR_STATE=$(fact pr_state)      # MERGED | CLOSED | OPEN | NONE
PR_HEAD=$(fact pr_head)        # tip | behind  (what GitHub saw vs the local tip)
DIRTY=$(fact dirty)            # 0 | 1
OCCUPANT=$(fact occupant)      # none | inside | sibling

case "$PR_STATE" in MERGED|CLOSED|OPEN|NONE) ;; *) echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - bad pr_state '$PR_STATE'"; exit 3 ;; esac
case "$PR_HEAD" in tip|behind) ;; *) echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - bad pr_head '$PR_HEAD'"; exit 3 ;; esac
case "$DIRTY" in 0|1) ;; *) echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - bad dirty '$DIRTY'"; exit 3 ;; esac
case "$OCCUPANT" in none|inside|sibling) ;; *) echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - bad occupant '$OCCUPANT'"; exit 3 ;; esac

# Isolate git from the caller: a harness run from inside a hook or a worktree can
# carry GIT_DIR and friends, and the caller's global config can carry hooks.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR GIT_PREFIX
GIT_CONFIG_GLOBAL=/dev/null
GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL GIT_CONFIG_NOSYSTEM

raw=$(mktemp -d "${TMPDIR:-/tmp}/flow-worktree-sweep-control.XXXXXX") || {
    echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - no tmpdir"; exit 3; }
trap 'rm -rf "$raw"' EXIT INT TERM
# Physical path: git reports worktree paths resolved, and the occupancy match
# below compares strings, so a symlinked TMPDIR would split the two.
T=$(cd "$raw" && pwd -P) || { echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - tmpdir unreadable"; exit 3; }

# The fixture must sit outside every repository, or `--repo` could resolve an
# ENCLOSING checkout and the sweep would classify that one's worktrees.
if git -C "$T" rev-parse --git-dir >/dev/null 2>&1; then
    echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - TMPDIR is inside a git repository;"
    echo "  the fixture would not be isolated and the sweep would examine the enclosing checkout"
    exit 3
fi

G() { git -c user.email=fixture@example.invalid -c user.name=fixture "$@"; }
REPO="$T/repo"
WT="$T/repo-issue-4242"
BRANCH="issue-4242-fixture"
{
    mkdir "$REPO" &&
    G -C "$REPO" init -q -b main &&
    G -C "$REPO" commit -q --allow-empty -m "fixture base" &&
    G -C "$REPO" remote add origin https://github.com/fixture-owner/fixture-repo.git &&
    G -C "$REPO" worktree add -q -b "$BRANCH" "$WT" &&
    G -C "$WT" commit -q --allow-empty -m "fixture work"
} >/dev/null 2>&1 || { echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - could not build the fixture repository"; exit 3; }

TIP=$(git -C "$WT" rev-parse HEAD)
BASE=$(git -C "$REPO" rev-parse main)
# `behind`: GitHub merged the base commit, the local branch has one more on top -
# a commit that exists nowhere else. No upstream is configured in any case, so
# the PR head is the gate's only unpushed evidence (its post-prune lane).
if [ "$PR_HEAD" = tip ]; then SEEN="$TIP"; else SEEN="$BASE"; fi

[ "$DIRTY" = 1 ] && echo "uncommitted" > "$WT/untracked-work.txt"

# --- stub gh -----------------------------------------------------------------
# Answers exactly the one query the gate makes (`gh pr list ... --jq ...`) with
# the rows that --jq would have produced. Anything else is a usage the gate did
# not make when this was written, and fails rather than inventing an answer.
mkdir "$T/bin"
case "$PR_STATE" in
    NONE) ROWS="" ;;
    *)    ROWS="$PR_STATE|$SEEN|4242" ;;
esac
cat > "$T/bin/gh" <<GH
#!/bin/sh
[ "\$1 \$2" = "pr list" ] || exit 1
[ -n "$ROWS" ] && printf '%s\n' "$ROWS"
exit 0
GH
chmod +x "$T/bin/gh"

# --- fake /proc ----------------------------------------------------------------
# PIDs are above the kernel's maximum pid_max (2^22 = 4194304), so no real
# process - including the gate's own ancestry, which it skips by PID - can
# collide with one. `self/cwd` exists because the gate refuses to scan a proc
# tree it cannot read; the bystander keeps the tree non-empty in every case,
# because an empty tree is the gate's "cannot scan" lane, not "unoccupied".
P="$T/proc"
mkdir -p "$P/self" "$P/9999900" "$T/elsewhere"
ln -s "$T" "$P/self/cwd"
ln -s "$T/elsewhere" "$P/9999900/cwd"
case "$OCCUPANT" in
    inside)
        mkdir -p "$WT/src" "$P/9999901"; ln -s "$WT/src" "$P/9999901/cwd" ;;
    sibling)
        # A DIFFERENT directory whose name EXTENDS the worktree's - the shape the
        # gate's own comment records measuring on a real host
        # (`kyle-issue-1142` vs `kyle-issue-1142-container-spec-superseded`).
        mkdir -p "$T/repo-issue-4242-followup" "$P/9999901"
        ln -s "$T/repo-issue-4242-followup" "$P/9999901/cwd" ;;
esac

out=$(cd "$T" && env PATH="$T/bin:$PATH" FLOW_WORKTREE_SWEEP_PROC_ROOT="$P" \
          bash "$gate" --repo "$REPO" 2>&1)
status=$?

# 0 (ok | nothing-to-do) and 3 (partial) are the gate's answers. Anything else
# means it never classified - a crash is not a detection (#946).
case "$status" in
    0|3) : ;;
    *) printf '%s\n' "$out"
       echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - the sweep exited $status"; exit 3 ;;
esac

# Fixed-string match: $WT is a mktemp path, and a `.` in it is a regex wildcard.
line=$(printf '%s\n' "$out" | grep -F -e "SWEEP_WORKTREE: $WT " | head -1 || true)
if [ -z "$line" ]; then
    # It answered without examining the one worktree it was given: no verdict
    # about it exists, so neither GOOD nor BAD may be scored.
    printf '%s\n' "$out"
    echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - the sweep reported nothing for $WT"; exit 3
fi

# Only two dispositions are verdicts about this worktree: `skip` (examined and
# kept - GOOD) and `removable` (the finding). `undecidable` means the sweep could
# NOT classify it, which is neither: scoring it GOOD would let a regression that
# stopped looking pass every keep-case (counter-model review, #1281). Anything
# else is a disposition this runner does not know, and is refused the same way.
printf '%s\n' "$out"
case "$line" in
    "SWEEP_WORKTREE: $WT removable "*)
        echo "FLOW_WORKTREE_SWEEP_CONTROL: finding - the sweep reports the worktree removable"
        exit 1 ;;
    "SWEEP_WORKTREE: $WT skip "*)
        exit 0 ;;
    *)
        echo "FLOW_WORKTREE_SWEEP_CONTROL: cannot-run - the sweep did not classify $WT: ${line#SWEEP_WORKTREE: $WT }"
        exit 3 ;;
esac
