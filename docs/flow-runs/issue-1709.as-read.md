<!-- flow-run n=1 id=8e32b81e25864259ada028521eeac5ca -->
## Run 1 - issue #1709 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1709
- Read at:      2026-11-12T02:11:51Z
- updatedAt:    2026-11-11T23:07:36Z   (context only - moves on comments and labels)
- Body digest:  a74ad8e877df85b4182d2907bd0ff1a505b5fb84b63bbe7d9a0bc651f50a4bb9   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3157 of 3157 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 4 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
A flow worktree claim records who owns a checkout, and three reports show it misjudging the owner. For a Codex TUI session it records the short-lived tool-exec pid, so a live claim reads stale as soon as that process exits. A claim whose holder is a zombie was still reported as held on 2026-11-11, three days after PR #1635 added zombie handling, forcing `--steal`. And `flow-worktree-sweep.sh` skips every locked worktree, so finished worktrees with a stale claim are never retired.

## Findings (4)
- [seq 606](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6426897177), 2026-10-26, medium (estimated): flow-worktree-claim records the transient tool-exec PID for Codex TUI sessions, so live claims look stale. Status at origin/main `f63dc946`: scripts/flow-worktree-claim.sh:124-125 still derives identity from CLAUDE_PID:-$PPID and CLAUDE_CODE_SESSION_ID; no Codex thread handling.
- [seq 607](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6427647267), 2026-10-26, low (estimated): Mitigation for 606: exec the helper with CLAUDE_CODE_SESSION_ID set to the Codex thread UUID. Status at origin/main `f63dc946`: Workaround only; the comment says the underlying defect remains worth addressing. Same job as seq 606.
- [seq 633](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6520893311), 2026-10-30, low (stated): flow-worktree-sweep.sh:432 skips every locked worktree, so stale-claim finished worktrees pile up. Status at origin/main `f63dc946`: Sweep still reports 'skip locked' for any *locked* entry at lines 431-434, no stale-claim handling.
- [seq 710](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6800094210), 2026-11-11, low (stated): worktree-remove claim check treats zombie-owned claim as held, forcing --steal. Status at origin/main `f63dc946`: Observed 2026-11-11, three days after PR #1635 merged its zombie-owner handling; the fix did not cover this path or the consumer ran an older copy. Unsettled.

## Acceptance
- A Codex session's claim names a pid that lives as long as the session; a zombie holder reads stale in `worktree-remove.sh` as well as in `flow-worktree-claim.sh` (or the 2026-11-11 report is shown to come from an older copy); the sweep releases a claim it can prove stale.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)


<!-- end of body -->
