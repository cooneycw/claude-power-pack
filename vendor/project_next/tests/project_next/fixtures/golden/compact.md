## example/operations — Project Next 1.3

**Top action:** continue_pr: Build active foundation (issue #2, PR #20) — PR #20 is active and should be completed before broad new work. Evidence: head:issue-2-active-foundation, checks:pending, review:unknown.
**Next safe issue:** #3 Wave 1 feature
**State:** 6 open | 1 in-flight | 1 blocked | 1 uncertain | inventory complete

### Ready to start (top 3)
1. #3 Wave 1 feature [priority high (p1); phase wave/phase 1; type feature; quick win no]
   high (p1); wave/phase 1; feature; ordered by the deterministic rank tuple → `$flow-auto 3`
2. #4 Document setup [priority default; phase unspecified; type quick-win; quick win yes]
   default; unspecified; quick-win; ordered by the deterministic rank tuple → `$flow-auto 4`
3. #5 Planning epic [priority default; phase unspecified; type planning; quick win no]
   default; unspecified; planning; ordered by the deterministic rank tuple → `$flow-auto 5`

### Critical work (not startable)
- #1 Critical security repair — blocked

### Active work (not startable)
- #2 Active foundation — local-branch:issue-2-active-foundation, pr:#20, worktree:/repo-issue-2:dirty

### Blocked (not startable)
- #1 Critical security repair — blocked by #2

### Uncertain (not startable)
- #6 Choose storage — 'Blocked by' declares a dependency but the blocker names no issue or spec task: Blocked by design review

### Warnings
- unmapped worktree: /repo-issue-99 (issue-99-old-work)
