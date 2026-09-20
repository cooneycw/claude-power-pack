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

### Categorized backlog summary
- 6 open | 1 critical | 0 bugs | 1 features | 1 docs | 0 tech debt | 1 planning | 2 other

### Tier 1 — Critical work
- #1 Critical security repair — blocked

### Tier 2 — Active work
- #2 Active foundation — in-flight

### Blocked work (not actionable)
- none

### Uncertain work (not actionable)
- #6 Choose storage — uncertain

### Tier 3 — Ready to start
- #3 Wave 1 feature — available; high (p1); wave/phase 1; feature; ordered by the deterministic rank tuple → `$flow-auto 3`

### Tier 3b — Pending specification sync
- checkout

### Tier 4 — Quick wins
- #4 Document setup — available; default; unspecified; quick-win; ordered by the deterministic rank tuple → `$flow-auto 4`

### Tier 5 — Planning and discussion
- #5 Planning epic — available; default; unspecified; planning; ordered by the deterministic rank tuple → `$flow-auto 5`

### Spec Kit readiness
| Feature | spec.md | plan.md | tasks.md | Mapping | Recommended action |
|---|---:|---:|---:|---|---|
| checkout | yes | yes | yes | 1/2 (partial) | sync remaining tasks to issues |

### Pull requests
- #20 Build active foundation — head issue-2-active-foundation; checks pending; review unknown; merge BLOCKED

### Worktree detail
| Path | Branch | Issue | State | Working tree | Recent commits |
|---|---|---:|---|---|---|
| /repo | main | — | default | clean | aaa main commit |
| /repo-issue-2 | issue-2-active-foundation | #2 | in-flight | modified | bbb active work<br>aaa main commit |
| /repo-issue-99 | issue-99-old-work | #99 | no-open-issue | clean | ccc old work |

### Cleanup guidance
- worktree `/repo-issue-99` (issue-99-old-work) — branch does not map to an open issue; it may be merged, closed, or abandoned. Review with $flow-cleanup.
- remote branch `origin/issue-88-abandoned` (issue-88-abandoned) — branch does not map to an open issue; verify whether it is merged or abandoned. Review with $flow-cleanup.
