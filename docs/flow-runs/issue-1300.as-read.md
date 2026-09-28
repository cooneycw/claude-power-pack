# Issue #1300 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1300
- Read at:      2026-09-28T14:50:28Z
- updatedAt:    2026-09-27T18:14:02Z   (context only - moves on comments and labels)
- Body digest:  c3cdfe0f96dfdf76fa447b00c3c027cf4f2702a641b8d6a5aab54b0945ef88d6   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1349 of 1349 (cap 16384)

## Body as read
<!-- cpp-learning: b5be4025d316bcf323fdfab6bdebe81cc70af248aa76ea72cfb18b894cf4a25c -->

## Learning (auto-filed from the CPP friction retro)

With several sessions merging into one repo (cooneycw/skillc, 2026-09-27), a PR's required Woodpecker check takes ~15-20 min, longer than main stays still. gh-pr-merge.sh correctly clean-stopped with exit 6 (base moved / branch behind) three times on skillc PR #114, and once its own 60-poll wait expired while CI was merely queued (exit 1). Each retry cost a full re-sync and re-gate. What worked: wait for green with flow-ci-status.sh <sha> --event pull_request --wait, then git fetch and gh-pr-merge.sh in the same shell call, shrinking the window to seconds. PR #143 then merged first try.

**Proposed fix:** Document the wait-then-merge-immediately sequence in flow:auto Step 7 / flow:merge (or have gh-pr-merge.sh accept --wait-ci that polls flow-ci-status first and re-checks the base immediately before squashing); consider a merge queue for repos with many concurrent sessions.

## Provenance
- class: infra_trap / scope: knowledge
- confidence: 0.5
- fingerprint: b5be4025d316bcf323fdfab6bdebe81cc70af248aa76ea72cfb18b894cf4a25c
- source repo: claude-power-pack

Filed by /self-improvement:retro via the learnings->issue bridge (claude-power-pack #463). See the common-memory ledger for context.
