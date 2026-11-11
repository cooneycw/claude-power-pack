---
description: Clean up stale worktrees and branches, and offer archival of finished waves
allowed-tools: Bash(git:*), Bash(gh pr list:*), Bash(mktemp:*), Bash(printf:*), Bash(awk:*), Bash(grep:*), Bash(wc:*), Bash(echo:*), Bash(jq:*), Bash(~/.claude/scripts/flow-worktree-sweep.sh:*), Bash(~/.claude/scripts/flow-wave-registry.sh:*), Read
---

# Flow: Cleanup - Prune Stale Worktrees and Branches

Retire worktrees whose work has landed, remove orphaned worktree references, delete local branches already merged to main, prune stale remote tracking branches, and offer to archive finished waves.

Worktrees are visible siblings created outside the repo on the git lane (issue
#627: `<parent>/<repo>-<branch>`, or `$FLOW_WORKTREE_BASE` when set). `git
worktree list`, `git worktree prune`, and `git worktree remove` operate on them
exactly as they do on any worktree, so this command is the correct cleanup path.

## Arguments

- No arguments required. Run from the main repo or any worktree.

## Instructions

When the user invokes `/flow:cleanup`, perform these steps:

### Step 1: Detect Repository Root

```bash
# Find the main repo (works from worktree or main)
if [[ -f ".git" ]]; then
    MAIN_REPO=$(cat .git | sed 's/gitdir: //' | sed 's|/.git/worktrees/.*||')
else
    MAIN_REPO=$(git rev-parse --show-toplevel)
fi
REPO=$(basename "$MAIN_REPO")
```

### Step 2: Sweep Worktrees Whose Work Has Landed (issue #887)

Run this FIRST, before anything below prunes or fetches. Ordering is
load-bearing and the reason is in Step 5: `git fetch --prune` destroys one of the
two signals this step needs.

```bash
~/.claude/scripts/flow-worktree-sweep.sh --repo "$MAIN_REPO"
```

That is a **dry run** and removes nothing. Read the report, then apply:

```bash
~/.claude/scripts/flow-worktree-sweep.sh --repo "$MAIN_REPO" --apply
```

`--apply` re-derives every condition itself. The dry-run output is a report, not
a manifest to execute.

Read the contract lines rather than the prose:

| line | meaning |
|---|---|
| `SWEEP_WORKTREE: <path> removable\|removed ...` | all five conditions passed |
| `SWEEP_WORKTREE: <path> skip <reason>` | checked, and it stays. Normal |
| `SWEEP_WORKTREE: <path> undecidable <reason>` | could NOT be classified |
| `SWEEP_WORKTREE: <path> refused <reason>` | the removal helper said no |
| `FLOW_WORKTREE_SWEEP: ok` | every candidate classified |
| `FLOW_WORKTREE_SWEEP: nothing-to-do` | all classified, none removable |
| `FLOW_WORKTREE_SWEEP: no-candidates` | there are no linked worktrees. NOT the same |
| `FLOW_WORKTREE_SWEEP: partial` (exit 3) | something was undecidable or refused |

`partial` is not a failure and needs no retry - it means the sweep is telling you
it could not classify everything it examined, most often because `gh` was
unreachable (`pr-unknown`). Report it; do not re-run with different flags to make
it go away.

**`refused` is information, never an obstacle.** The sweep removes nothing
itself: every removal is handed to `scripts/worktree-remove.sh`, and the exit
codes here are that helper's. Exit 4 is a live #597 claim, exit 5 is #888's
in-use refusal, and exit 8 (#1032) means the worktree's directory name and its
checked-out branch name different issues - the sweep passes `--delete-branch`,
and the branch that would be deleted is not the one the path refers to. The
sweep already declines
to pass `--force` or `--steal`, and you must not add them: overriding either in a
loop across every worktree on the host is the data-loss path #889 closed, applied
everywhere at once. If a refusal is wrong, that is the user's call on that one
path, not this command's.

A worktree with **no PR is always skipped** - a preserved WIP branch and a
wayfinder research branch both look like that permanently.

Who owns teardown and why it is a sweep rather than the merging session:
[ADR 0006](../../../docs/decisions/0006-worktree-teardown-ownership.md).

### Step 3: Prune Stale Worktree References

When worktree folders are deleted manually, git still tracks them. This cleans those references.

```bash
# Show stale worktree references before pruning
STALE_WORKTREES=$(git -C "$MAIN_REPO" worktree list --porcelain | grep -B2 "prunable" | grep "worktree " | sed 's/worktree //' || true)

# Prune them
git -C "$MAIN_REPO" worktree prune
```

Report what was pruned (or "No stale worktree references found").

Note: `git worktree prune` deliberately skips a LOCKED entry, so a worktree
still carrying a live `/flow` claim (issue #597) is never pruned even if its
directory is gone. Step 2's sweep skips a locked entry for the
same reason and never passes `--steal`, so the two agree: a claim outranks both
of them.
Inspect one with `~/.claude/scripts/flow-worktree-claim.sh check --issue <N>`;
a claim whose owning process is gone reports `stale` and is released by the
next run that needs the worktree.

### Step 4: Find and Delete Merged Local Branches

Delete local `issue-*` branches that have been merged to main. Protect `main`, `master`, and any branch with an active worktree.

```bash
# Get list of branches with active worktrees (these are protected)
WORKTREE_BRANCHES=$(git -C "$MAIN_REPO" worktree list --porcelain | grep "^branch " | sed 's|branch refs/heads/||')

# Make sure main is up to date
git -C "$MAIN_REPO" fetch origin main

# Find merged branches (excluding main/master and worktree branches)
MERGED_BRANCHES=$(git -C "$MAIN_REPO" branch --merged main | grep -v '^\*' | grep -v 'main$' | grep -v 'master$' | sed 's/^[ ]*//')
```

For each merged branch:
1. Skip if it has an active worktree
2. Delete it with `git -C "$MAIN_REPO" branch -d "$BRANCH"`

**A gone upstream is not proof of a merge (#1708):** a remote branch also goes
when deleted unmerged, leaving the local one the only copy. Squash merges never
show as `--merged`, so force-delete only a branch whose CURRENT tip is proven landed:

```bash
REPO=$(git -C "$MAIN_REPO" remote get-url origin | sed -E 's#^(git@|https://)github\.com[:/]##; s#\.git$##')
# Delete ONLY the proven commit; update-ref fails if moved.
delete_proven() {
    if git -C "$MAIN_REPO" worktree list --porcelain | grep -Fqx -- "branch refs/heads/$1"; then
        echo "KEPT: $1 (checked out in a worktree)"
    elif git -C "$MAIN_REPO" update-ref --no-deref -d "refs/heads/$1" "$2" 2>/dev/null; then
        git -C "$MAIN_REPO" config --remove-section "branch.$1" 2>/dev/null || true
        echo "DELETED: $1 ($3)"
    else
        echo "KEPT: $1 (tip changed during cleanup)"
    fi
}
for branch in $(git -C "$MAIN_REPO" branch --format='%(refname:short)' --list 'issue-*'); do
    echo "$WORKTREE_BRANCHES" | grep -Fqx -- "$branch" && continue
    REMOTE=$(git -C "$MAIN_REPO" config "branch.${branch}.remote" 2>/dev/null || echo "")
    MERGE_REF=$(git -C "$MAIN_REPO" config "branch.${branch}.merge" 2>/dev/null || echo "")
    [[ -n "$REMOTE" && -n "$MERGE_REF" ]] || continue
    git -C "$MAIN_REPO" show-ref --verify --quiet "refs/remotes/${REMOTE}/${MERGE_REF#refs/heads/}" && continue
    TIP=$(git -C "$MAIN_REPO" rev-parse "refs/heads/$branch")
    # Proof 1: the merge helper recorded this commit as landed (#916).
    if [[ "$(git -C "$MAIN_REPO" config "branch.${branch}.cpp-merged-head" 2>/dev/null)" == "$TIP" ]]; then
        delete_proven "$branch" "$TIP" "landed: merge-helper record"; continue
    fi
    PRS=$(gh pr list -R "$REPO" --head "$branch" --state merged --json headRefOid 2>/dev/null) || PRS=""
    if ! printf '%s' "$PRS" | jq -e 'type == "array"' >/dev/null 2>&1; then
        echo "KEPT: $branch (could not ask GitHub)"
    elif printf '%s' "$PRS" | jq -e --arg t "$TIP" 'any(.[]; .headRefOid == $t)' >/dev/null; then
        delete_proven "$branch" "$TIP" "landed: merged PR head"
    elif printf '%s' "$PRS" | jq -e 'length > 0' >/dev/null; then
        echo "KEPT: $branch (tip differs from merged head)"
    else
        echo "KEPT: $branch (no merged PR)"
    fi
done
```

Never delete a `KEPT:` branch by hand: a failed, empty or unreadable answer is
unknown, not "no PR". Report each `DELETED:` branch with its proof and each kept
branch with its reason.

### Step 5: Prune Stale Remote Tracking Branches

```bash
git -C "$MAIN_REPO" fetch --prune
```

This removes `remotes/origin/issue-*` references for branches already deleted on the remote.

**This step must stay after Step 2.** Pruning drops
`refs/remotes/origin/<branch>`, and that ref is what `git log @{u}..` needs to
answer "is anything unpushed here". The sweep carries a second, independent
answer for that question (the PR's own head commit, which survives the prune), so
a later run still works, on one signal where it could have had two.

Report how many remote tracking branches were pruned.

### Step 6: Offer to Archive Finished Waves (issue #1562)

Read the wave keys from the shared registry at
`${FLOW_WAVE_REGISTRY_DIR:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/cc-flow-wave}/registry.json`
using `jq -r 'keys[]'`. If it is absent, report no registered waves; if it
cannot be read or parsed, report that wave cleanup is unexamined.

For each wave, run:

```bash
~/.claude/scripts/flow-wave-registry.sh list --wave "$WAVE" --any-live
```

This query exits 1 for `no-roles-ended` and `no-roles-registered`; those are
candidate states, not command errors. Skip `yes` and `undeterminable`, and name
them in the report. For each candidate, preview separately:

```bash
~/.claude/scripts/flow-wave-registry.sh close --wave "$WAVE" --dry-run
```

The preview checks each role and watcher, including unknown holders, and
reports the proposed archive path and bytes. If it refuses, report every holder
it names and leave the wave alone. Present successful previews to the user and
offer close **per wave**. Never auto-close, including when cleanup runs after
`/flow:merge`. Only after the user selects a wave, run:

```bash
~/.claude/scripts/flow-wave-registry.sh close --wave "$WAVE"
```

The helper copies the whole wave directory (mailboxes, acknowledgements,
verdicts and policy history), adds `registry-entry.json`, verifies the archive,
then removes the registry key under its lock and the wave directory. Existing
archives are never overwritten. Keep `--force` out of cleanup: a refusal is a
reason to stop, and a confirmed watcher cannot be forced even manually.
An absent wave directory still requires a successful watcher-process scan;
close can then archive its registry entry alone. An unknown scan refuses, and
cleanup never overrides it with `--force`.
Report `FLOW_WAVE_ARCHIVE` and `FLOW_WAVE_BYTES_FREED` for each closed wave.

### Step 7: Summary Output

```markdown
## Flow Cleanup - {repo}

### Worktree References
  {N} stale references pruned (or "None found")

### Local Branches Deleted
  {branch-1} (merged to main)
  {branch-2} (landed: merge-helper record | merged PR head)
  Kept, not proven landed: {branch-3} ({reason})
  ... or "No stale branches found"

### Remote Tracking Branches
  {N} stale remote references pruned (or "Already clean")

### Wave Archives
  {wave}: {archive path}, {bytes freed} (or "Offered; not selected")
  {wave}: refused/skipped, {holders or reason}

### Current State
  {M} worktrees active
  {N} local issue branches remaining
```

## Preserved-WIP handoff

When you deliberately preserve and push unfinished work, the pushed branch is
only the storage half of the handoff (#1614). Before reporting preservation
complete or ending the run, publish a durable issue comment or a draft PR linked
to the issue. It must name the branch, exact pushed commit, current issue state,
provenance (or explicitly unknown provenance), and remaining work, including any
uncommitted or untracked remainder. A local plan's `declare-salvage` record does
not replace this issue-visible handoff.

Read the published record back, verify those fields, and relay its URL to the
assigning session and closing report. Reuse an existing comment or linked draft
PR only after verifying it describes this same pushed tip; do not create a
duplicate for an unchanged preservation. A draft uses `Refs #N`, leaving the
issue open. If the issue is already closed, record that fact and the reason for
keeping the WIP; do not reopen it or imply it is startable work.

For a new preservation without an existing verified handoff, set `WIP_ROOT` to
the checkout, `WIP_REPO` to its verified owner/name, `WIP_ISSUE` to the assigned
issue, and `WIP_PROVENANCE` / `WIP_REMAINING` to the factual handoff details.
This recipe records the already-pushed commit; it does not commit, push, delete,
or claim to preserve the rest of the workspace. Keep secrets out of the text.

<!-- preserved-wip-handoff:begin -->
```bash
set -euo pipefail
: "${WIP_ROOT:?checkout required}"
: "${WIP_REPO:?verified owner/name required}"
: "${WIP_ISSUE:?assigned issue required}"
: "${WIP_PROVENANCE:?provenance or explicit unknown required}"
: "${WIP_REMAINING:?unfinished work required}"
WIP_BRANCH=$(git -C "$WIP_ROOT" symbolic-ref --quiet --short HEAD)
WIP_TIP=$(git -C "$WIP_ROOT" rev-parse HEAD)
WIP_PUSHED=$(git -C "$WIP_ROOT" ls-remote --exit-code origin "refs/heads/$WIP_BRANCH" | awk 'NR == 1 {print $1}')
if [[ "$WIP_TIP" != "$WIP_PUSHED" ]]; then
    printf '%s\n' 'WIP handoff incomplete: origin does not contain this branch tip.' >&2
    exit 1
fi
WIP_STATE=$(gh api "repos/$WIP_REPO/issues/$WIP_ISSUE" --jq .state)
case "$WIP_STATE" in open|closed) ;; *) printf '%s\n' 'WIP issue state unreadable.' >&2; exit 1 ;; esac
WIP_BODY=$(mktemp)
trap 'rm -f "$WIP_BODY"' EXIT
printf 'Preserved unfinished work.\n\n- Issue: #%s (%s)\n- Branch: `%s`\n- Pushed commit: `%s`\n- Provenance: %s\n- Remaining work: %s\n\nThis is a preservation handoff, not a completed implementation.\n' \
    "$WIP_ISSUE" "$WIP_STATE" "$WIP_BRANCH" "$WIP_TIP" "$WIP_PROVENANCE" "$WIP_REMAINING" > "$WIP_BODY"
WIP_COMMENT_ID=$(gh api --method POST "repos/$WIP_REPO/issues/$WIP_ISSUE/comments" -F "body=@$WIP_BODY" --jq .id)
[[ "$WIP_COMMENT_ID" =~ ^[0-9]+$ ]]
WIP_READBACK=$(gh api "repos/$WIP_REPO/issues/comments/$WIP_COMMENT_ID" --jq .body)
[[ "$WIP_READBACK" == "$(< "$WIP_BODY")" ]]
WIP_URL=$(gh api "repos/$WIP_REPO/issues/comments/$WIP_COMMENT_ID" --jq .html_url)
[[ "$WIP_URL" == "https://"*"/$WIP_REPO/issues/$WIP_ISSUE#issuecomment-$WIP_COMMENT_ID" ]]
printf 'PRESERVED_WIP_HANDOFF: %s\n' "$WIP_URL"
```
<!-- preserved-wip-handoff:end -->

If publication or readback fails, the handoff is incomplete. Keep the branch and
worktree, report the blocker and exact pushed tip, and stop; do not describe the
preservation as handed off. The normal sweep still skips no-PR worktrees. Merely
discovering an old WIP branch does not authorize publishing comments or creating
draft PRs for a historical backlog; report the missing handoff instead.

## Error Handling

- **Not a git repo:** Report error and exit
- **Uncommitted changes on a branch:** Never delete - skip and warn
- **Protected branches:** Never delete `main` or `master`
- **Active worktree branches:** Never delete branches with active worktrees
- **Sweep reports `partial` (exit 3):** not a failure. Report which worktrees
  were `undecidable` or `refused` and why; never re-run with `--force`/`--steal`
  to clear it

## Notes

- Safe to run multiple times (fully idempotent)
- Step 2 removes worktrees and is a dry run unless `--apply` is passed; it never
  passes `--force`. Step 6 removes wave state only after a verified archive and
  the user's per-wave selection. Other steps remove references and branches.
- Only deletes `issue-*` pattern branches in the squash-merge detection path (other branches require `--merged` confirmation)
- Use `git branch -d` (safe delete) for merged branches, never `git branch -D`: Step 4 deletes a proven tip itself
- Run automatically after `/flow:merge` or manually anytime
- Normal cleanup needs network access for `git fetch --prune`; a deliberate
  preserved-WIP handoff also needs GitHub publication and readback.
