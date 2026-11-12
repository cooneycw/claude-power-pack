<!-- flow-run n=1 id=6bf7d629731d4467ba8992f90b54a21e -->
## Run 1 - issue #1708 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1708
- Read at:      2026-11-11T23:47:59Z
- updatedAt:    2026-11-11T23:07:35Z   (context only - moves on comments and labels)
- Body digest:  fd5a0df00cb835aabbdc7658311102a414c3d10af131074d7683eb6cda7f9266   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2135 of 2135 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 2 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
`/flow:cleanup` Step 4 force-deletes (`git branch -D`) an issue branch whose upstream is gone, treating a missing upstream as proof the work merged. A branch whose remote was deleted without a merge loses its only copy. Separately, the command's allowed-tools entry `Bash(gh api:*)` pre-approves every `gh api` call, including writes.

## Findings (2)
- [seq 632](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6520559175), 2026-10-30, medium (stated): flow:cleanup Step 4 force-deletes (-D) issue branches whose upstream is gone, treating that as proof the PR merged. Status at origin/main `f63dc946`: cleanup.md lines 147-167 unchanged: remote-gone branch is -D'd with no merged-PR/tip-ancestry check; no headRefOid or is-ancestor text in the file.
- [seq 672](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6724404684), 2026-11-08, low (stated): flow/cleanup.md allowed-tools Bash(gh api:*) auto-approves any gh api call incl. writes. Status at origin/main `f63dc946`: cleanup.md frontmatter still contains Bash(gh api:*).

## Acceptance
- A branch is deleted only on positive evidence it landed (the same blob-identity proof `worktree-remove.sh` uses), and the allowed-tools entry is narrowed to the read calls the command makes.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)


<!-- end of body -->
