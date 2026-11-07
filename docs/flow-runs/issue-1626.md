# Flow run record - issue #1626

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=9054b14ce81243659abfac191a06ff60 -->
## Run 1

- Run-id:            9054b14ce81243659abfac191a06ff60
- Run-start:         69ee5b9c22f4722b06a91312fa1958d781a73809
- Issue:             #1626
- Base SHA:          69ee5b9c
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (owner, interactive "approved")
- Recorded at:       2026-11-07T00:00:00Z

### Section B evidence
commits: none on origin/main since 2026-11-06 (tip 69ee5b9c). PRs: none merged since 2026-11-06. dup/super: none open; related closed #1035, #1488, #1257, #475; #1614 open and disjoint. Correction: spec-sync warning never set inventory incomplete (collect.py:273); it was only listed as resolve_inventory evidence (rank.py:165).

### Section C - the approved plan
1. `lib/project_next/collect.py` - per-issue merged-PR lookup when the 200 window is full; external issue state collection
2. `lib/project_next/models.py` - external_issue_states on RepositoryState; recommendation on RecommendationResult
3. `lib/project_next/classify.py` - known external CLOSED satisfied, OPEN blocker, unknown uncertain
4. `lib/project_next/rank.py` - contract 1.8; recommendation from available+uncertain; resolve_inventory evidence lists causes only
5. `lib/project_next/render.py` - Recommended line with basis label
6. `docs/project-next-contract.md` - bump to 1.8; define recommendation, per-issue delivery evidence, external states
7. `templates/project-next.schema.json` - recommendation and external_issue_states
8. `lib/project_next/ownership.json` - repin
9. `scripts/project-next.py` - pass recommendation through JSON and render
10. `.claude/commands/project/next.md` - Step 3 resolve and recommend; always end with a pick
11. `codex/skills/project-next/SKILL.md` - regenerated mirror
12. `tests/project_next/fixtures/scenarios.json` - truncated_history_prose_dependency and native_open_blocker_only scenarios; goldens refreshed
13. `tests/project_next/test_collection.py` - per-issue lookup, fail-closed, external states
14. `tests/project_next/test_classification.py` - external state resolution
15. `tests/project_next/test_ranking.py` - recommendation never from blocked/in-flight/non-startable, never fills next_startable_issue
16. `tests/test_project_next_contract.py` - next.md resolve step assertions

Scope: ~16 files, ~500-700 lines. Risks: search rate limits (batched, fail-closed); search misses read as no partial delivery; contract bump touches mirror and pin; agent judgment mistaken for engine safety (label + strict field untouched).
