<!-- flow-run n=1 id=e7c87a3574ac4b75b3f4282077ce51f7 -->
## Run 1 - issue #1674 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1674
- Read at:      2026-11-11T15:13:55Z
- updatedAt:    2026-11-11T15:10:39Z   (context only - moves on comments and labels)
- Body digest:  d29f34db5a31c407cf55b3eb2071baa3d69e8b967bc812df63402d76ddc45f40   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1808 of 1808 (cap 16384)

### Body as read
Tier: 1

Found 2026-11-11 running `/project:next claude-power-pack`. Blocks the command now, on the owner's host, on both the installed checkout (6bc585a3) and origin/main (31fe6a69).

## Outcome
`project-next` must produce a report when the repository has a worktree entry whose directory no longer exists. Today it exits 2 with no report:

```
project-next: [Errno 2] No such file or directory: PosixPath('/tmp/.../scratchpad/t008/cpp-pin')
```

`git worktree list --porcelain` lists that entry with `prunable gitdir file points to non-existent location`. `lib/project_next/collect.py` `_parse_worktrees` (about line 140) runs `git status --short` with that path as cwd. The surrounding `try` catches `CollectionError`, but a missing cwd raises `FileNotFoundError` out of `subprocess_runner` (line 63), which is not caught, so one stale entry takes down the whole inventory.

The neighbouring comment (#1398) already states the intended behaviour: a worktree that could not be asked is UNEXAMINED with a warning, not a crash and not "clean".

## Acceptance
- With a prunable worktree entry present, the report renders; that worktree is reported unexamined with a warning naming the path and that it is prunable. It is never reported clean and never proposed as `continue_work`.
- The porcelain `prunable` line is read, so the entry is identified without attempting to enter the directory.
- Regression test with a fixture worktree whose directory has been removed. It must FAIL on the code before the fix (crash, exit 2) and pass after; say so in the PR.

## Constraint
The command stays read-only: it must not run `git worktree prune` itself.

## Workaround
`git -C <repo> worktree prune` removes the stale entry. Not applied by the reporting session, because `/project:next` is contractually read-only.


<!-- end of body -->
