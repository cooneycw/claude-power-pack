# Flow run record - issue #1440

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=4ffa755874ca4108a773180147295f3f -->
## Run 1

- Run-id:            4ffa755874ca4108a773180147295f3f
- Run-start:         50261ddd1b76a042dd0bf868a869e04b67e5b27f
- Issue:             #1440
- Base SHA:          50261ddd
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (operator, in-session "approved")
- Recorded at:       2026-10-12T14:20:00Z

### Section B evidence
Issue filed 2026-10-12T13:46:11Z. Commits on origin/main since: none (main = 50261ddd).
Merged PRs since: none. Duplicate/superseding issues: none (searched "MEMORY.md",
"auto-memory", "superseded memory", "memory link"; hits #1236, #575, #506, #1278,
#1301, #1300, #871, #1069, #1272, #726 unrelated). Sibling worktrees: primary only,
no unpushed commits. No existing auto-memory parser in scripts/ or lib/.

### Section C - the approved plan
1. `scripts/check-memory-supersession.py` - new stdlib-only checker; strict supersession marker; verdicts clean/stale/unreadable/unknown exit 0/1/2/3; info-only hygiene findings; NEGATIVE-CONTROL marker
2. `controls/check-memory-supersession/control.json` - registration
3. `controls/check-memory-supersession/cases/bad-stale-dependent/MEMORY.md` - synthetic store with an older dependent of a superseded node
4. `controls/check-memory-supersession/cases/good-current/MEMORY.md` - same store, dependent current
5. `controls/check-memory-supersession/cases/unknown-undated/MEMORY.md` - undated dependent must read unknown
6. `controls/check-memory-supersession/anchors/constructed-no-marker-check-memory-supersession.py` - blind anchor without marker detection
7. `tests/test_check_memory_supersession.py` - verdict, exit-code, marker-strictness, index-exclusion, hygiene and unreadable tests
8. `docs/scripts.md` - inventory entry and marker grammar
9. `docs/decisions/0008-instrument-negative-control-bound.md` - census row 117
10. `.claude/verify-coverage.json` - tested entry

Scope: ~9 new files, 2 edited, ~350 lines plus fixtures.
Risks: strict marker cannot see prose-only supersession (clean is scoped in output);
undated dependents make `unknown` common on real stores; repo is public, fixtures synthetic.
