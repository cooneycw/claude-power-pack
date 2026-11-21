### Step 3: Approve
Wait for real approval.
### Pre-child checkpoints (parent)
```bash
~/.claude/scripts/flow-live-driver-guard.sh /path/to/worktree
~/.claude/scripts/flow-worktree-claim.sh check /path/to/worktree
~/.claude/scripts/flow-stale-check.sh origin/main /path/to/worktree
```
suspected: STOP and ask; held or foreign: STOP. Missing/unknown is unchecked, never clear.
collision: checkpoint on clean tree; never stash.
### Step 4: Implement
Run first child.
### Step 6: Quality Gates
```bash
~/.claude/scripts/flow-stale-check.sh origin/main /path/to/worktree
```
Run quality gates:
If a merge changes the reviewed artifact, return to Step 5 review and receipt.
Before each fix invocation, run:
```bash
~/.claude/scripts/flow-live-driver-guard.sh /path/to/worktree
```
Extract the error output
When ownership is uncertain:
```bash
~/.claude/scripts/flow-worktree-claim.sh check /path/to/worktree
```
Attribute only against the recorded checkpoint and child's result; checkpoint ONLY confirmed-own changes, rerun on a CLEAN tree; never bypass.
Unexplained dirt: stage everything and checkpoint.
### Step 8: Cleanup
Release only this run's confirmed self claim, before removing:
```bash
~/.claude/scripts/flow-worktree-claim.sh release /path/to/worktree
```
Remove worktree and branch
Leave for review keeps the worktree and claim; never --force.
