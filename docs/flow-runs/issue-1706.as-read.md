<!-- flow-run n=1 id=14597a63bf3b4895a645744e2214657d -->
## Run 1 - issue #1706 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1706
- Read at:      2026-11-12T00:40:06Z
- updatedAt:    2026-11-12T00:40:05Z   (context only - moves on comments and labels)
- Body digest:  c833b0cc5124b9646c5226db3843ac38aa2989c2a660c637618eab0873a927e2   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 7932 of 7932 (cap 16384)

### Body as read
Tier: 2

Source: Nit Store #864 rollover (#1690). Read 2026-11-11T22:53:29Z against origin/main `f63dc946`. This is one job grouped from 11 Nit Store comment(s); each is linked below and was checked against the tree at that commit.

## Outcome
The finish path keeps colliding with consumer repositories. `/flow:auto` Step 6 runs the finish gate before `git push`, so a consumer `make verify` that inspects the pushed head (kyle's ci-shape-check) refuses the unpushed commit: reported five times. And `check-ignored-additions.sh` blocks on evidence the gate itself just wrote (kyle `dashboard-runs`, skillc `reports/`): reported five times, although the remedy, a repo-declared `.claude/gate-scratch.txt` (#1516), already exists and the blocking message never names it. One further report asks for relief when the Step 7 re-gate outlasts main's quiet window.

## Findings (11)
- [seq 622](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6469469549), 2026-10-28, low (stated): check-ignored-additions.sh blocks on skillc reports/failure-context.jsonl written by a red test run. Status at origin/main `f63dc946`: The repo-declared .claude/gate-scratch.txt mechanism (#1516) predates this report, but the blocking message never names it, so consumers keep reporting the block.
- [seq 631](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6520012256), 2026-10-30, medium (estimated): flow:auto Step 6 runs finish gate before git push, so kyle make verify ci-shape-check refuses unpushed HEAD; first gate run is red. Status at origin/main `f63dc946`: auto.md still has flow-finish-gate.sh (line 816) before git push (line 886); no pushed-head prerequisite anywhere in auto.md, finish-gate or lib/cicd. Duplicate of seq 631 family.
- [seq 636](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6527171872), 2026-10-30, low (estimated): check-ignored-additions.sh blocks kyle run on dashboard-runs output the finish gate wrote. Status at origin/main `f63dc946`: The repo-declared .claude/gate-scratch.txt mechanism (#1516) predates this report, but the blocking message never names it, so consumers keep reporting the block.
- [seq 638](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6535599636), 2026-10-30, low (estimated): check-ignored-additions.sh reds every kyle run on gate's own dashboard-runs evidence. Status at origin/main `f63dc946`: The repo-declared .claude/gate-scratch.txt mechanism (#1516) predates this report, but the blocking message never names it, so consumers keep reporting the block.
- [seq 649](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6566532599), 2026-11-02, low (estimated): check-ignored-additions.sh exit 3 on kyle dashboard-runs artifacts; suggests recognising generated evidence dirs. Status at origin/main `f63dc946`: The repo-declared .claude/gate-scratch.txt mechanism (#1516) predates this report, but the blocking message never names it, so consumers keep reporting the block.
- [seq 650](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6567320523), 2026-11-02, low (estimated): flow:auto Step 7 full local re-gate outlasts main's quiet window; asks for merge-window coordination or evidence reuse. Status at origin/main `f63dc946`: No evidence-reuse or merge-window coordination found for the local re-gate; comment is a design review request, not a defect.
- [seq 652](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6603359600), 2026-11-03, medium (estimated): flow:auto Step 6 runs finish gate before git push, so kyle make verify ci-shape-check refuses unpushed HEAD; first gate run is red. Status at origin/main `f63dc946`: auto.md still has flow-finish-gate.sh (line 816) before git push (line 886); no pushed-head prerequisite anywhere in auto.md, finish-gate or lib/cicd. Duplicate of seq 631 family.
- [seq 654](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6603579674), 2026-11-03, medium (estimated): flow:auto Step 6 runs finish gate before git push, so kyle make verify ci-shape-check refuses unpushed HEAD; first gate run is red. Status at origin/main `f63dc946`: auto.md still has flow-finish-gate.sh (line 816) before git push (line 886); no pushed-head prerequisite anywhere in auto.md, finish-gate or lib/cicd. Duplicate of seq 631 family.
- [seq 655](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6629579101), 2026-11-04, medium (estimated): flow:auto Step 6 runs finish gate before git push, so kyle make verify ci-shape-check refuses unpushed HEAD; first gate run is red. Status at origin/main `f63dc946`: auto.md still has flow-finish-gate.sh (line 816) before git push (line 886); no pushed-head prerequisite anywhere in auto.md, finish-gate or lib/cicd. Duplicate of seq 631 family.
- [seq 663](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6708413508), 2026-11-07, low (stated): check-ignored-additions.sh exit 3 on kyle dashboard-runs written by finish gate. Status at origin/main `f63dc946`: The repo-declared .claude/gate-scratch.txt mechanism (#1516) predates this report, but the blocking message never names it, so consumers keep reporting the block.
- [seq 671](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6723701692), 2026-11-08, low (stated): flow:auto Step 6 runs finish gate before git push, so kyle make verify ci-shape-check refuses unpushed HEAD; first gate run is red. Status at origin/main `f63dc946`: auto.md still has flow-finish-gate.sh (line 816) before git push (line 886); no pushed-head prerequisite anywhere in auto.md, finish-gate or lib/cicd. Duplicate of seq 631 family.

## Acceptance
- The gate-before-push order is either changed or documented with the consumer-side remedy (amended 2026-11-11: met by DOCUMENTING, see the note below); the ignored-additions block message names `.claude/gate-scratch.txt`; whatever kyle and skillc must declare on their side is filed in those repositories.
- Every finding listed above ends as fixed (with the test or case that pins it) or declined on this issue with a one-line reason. None is left unmentioned.

## Amendment, 2026-11-11 (planning run, approved by the wave orchestrator)

- **Gate before push: documented, not changed.** Kyle's `ci_shape_check.py` clones the ref under test fresh from GitHub and exits 4 when the ref is not there, by design. Pushing before the gate for every project would publish unverified commits by default, so the order stays and the flow documents say what to do when a project's gate needs the pushed head: push the branch (it opens no pull request), then run the gate.
- **Declined: seq 650** (relief when the Step 7 re-gate outlasts main's quiet window). It asks for evidence reuse or merge-window coordination, which is new machinery in the frozen gate path; #1300 already gave the merge helper a required-check wait and a clean re-sync stop, and the comment is a design request, not a defect.
- **Delivery: two pull requests.** One: the ignored-additions message names `.claude/gate-scratch.txt` (seq 622, 636, 638, 649, 663). Two: the sentence in `/flow:auto` and `/flow:finish` (seq 631, 652, 654, 655, 671). The second closes this issue.

## Not CPP's to do
kyle and skillc declaring their gate-output directories in their own `.claude/gate-scratch.txt` is consumer-side work. It is not filed here and is routed separately by the wave orchestrator.


## Constraint
Freeze (#1673): fixes only, no new feature under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/`. Owner ruling 2026-11-11 (#1673): output that kyle or skillc read (verdict lines, markers, exit codes, helper arguments) stays as it is by default; a change to one needs a coordination issue in cooneycw/kyle, cooneycw/skillc and cooneycw/kyle-candidate before the PR merges.

Parent: #1690 (child of #1673)



<!-- end of body -->
