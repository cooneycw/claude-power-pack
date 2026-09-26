# Issue #1257 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1257
- Read at:      2026-09-26T14:27:58Z
- updatedAt:    2026-09-26T13:52:46Z   (context only - moves on comments and labels)
- Body digest:  4ff9d6cf237c5023bcc2b700c6f039d283036fd8c2b2b5634a2517547cc46678   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2188 of 2188 (cap 16384)

## Body as read
Split out of #1035 (item 5) by owner ruling, 2026-09-26. #1035 fixes items 1-4; this one needs new per-worktree git plumbing in the collector and had no negative control specified, so it ships separately.

## The defect

`project:next` emits `unmapped worktree: <path> (<branch>)` (`lib/project_next/rank.py`, `recommend()` → `classification.unmapped_worktrees`) and a cleanup candidate whose reason is `branch does not map to an open issue; it may be merged, closed, or abandoned` (`_worktree_report`). The text is identical in two materially different states:

- a safe leftover whose work already landed on `origin/main`, and
- a tree holding genuinely unpushed / undelivered work.

Measured (nit store, https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5677273532): two worktrees, both issues CLOSED, both remote branches deleted, both clean, both `rev-list --count origin/main..HEAD == 1` - the squash-merge ancestry break, so the count says nothing. Only a per-file **blob identity** check against `origin/main` settled which was delivered.

The reader must choose between `git worktree remove` and "do not touch". The warning supports neither, so the safe reading is always "leave it", and stale worktrees accumulate.

## Fix

Annotate each unmapped worktree (and each worktree whose issue is not open) with:
- a delivery verdict from blob identity against `origin/main`: every path the branch changed relative to its merge-base has the identical blob on `origin/main` (deleted paths absent there) → `delivered`; otherwise `not-proven` (NOT "undelivered" - main may have moved those files since). Never `--is-ancestor`, never a rev-list count; squash merges break both.
- dirty / clean (a dirty tree is never `delivered`);
- remote-branch-exists.
- A collector failure must render `unknown`, never `delivered`.

## Negative control (ADR 0008)

The verdict is read to decide a destructive action, so it needs committed cases:
- a fixture worktree whose branch blobs all match `origin/main` → `delivered`; the same with one file differing → `not-proven`;
- a dirty tree with matching blobs → not `delivered`;
- a git failure → `unknown`.

Refs #1035

