# Flow run record - issue #1035

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1035
- Base SHA:          85e9b03ad2af1c41020ff6d92d36fa257bdacd2b
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (repository owner, in-session: "approved including the evergreen label.")
- Recorded at:       2026-09-26T00:00:00Z

## Section B evidence
- commits touching lib/project_next, scripts/project-next.py since 2026-09-16: af348f8 (#1144 relocation), 5ceb966 (#1077 stash guard) - neither addresses items 1-5
- merged PRs inspected: #1144, #1148, #1173, #1240, #1021, #1104 - ownership/pins/docs only
- duplicate/superseding: #1069 (closed without carrying cxpp#276, re-pointed here), #723, #770 - none fix these items
- live repro: `project-next.py --compact` names `#864 Nit Store` as Next safe issue; planning_routes is a plain path read at scripts/project-next.py:469; continue_work at rank.py:513-533 checks no issue state

## Section C - the approved plan
Items 1-4 in this PR; item 5 (unmapped-worktree delivered verdict) split to a follow-up issue.

1. `lib/project_next/config.py` - add `non_startable_labels` (evergreen, inbox, nit-store, not-startable) to config and known vocabulary
2. `lib/project_next/models.py` - add disjoint `non_startable` partition to Classification
3. `lib/project_next/classify.py` - route marked issues to non_startable (in-flight wins); update exhaustiveness assertion
4. `lib/project_next/rank.py` - continue_work skips dirty worktrees whose issue is not open (warning + cleanup); non_startable in tiers/state; CONTRACT_VERSION 1.4
5. `lib/project_next/render.py` - Not startable section and State count
6. `scripts/project-next.py` - wayfinder:* label routes; map resolved via git common dir; three-state map report (read/absent/unreadable) in every mode
7. `docs/project-next-contract.md` - 1.4 contract and compatibility notes
8. `templates/project-next.schema.json` - add non_startable_labels
9. `.claude/project-next-ownership.json` - contract 1.4 + repin
10. `tests/project_next/test_classification.py` - negative control: marked issue never available/next; unmarked still is
11. `tests/project_next/test_ranking.py` - negative control: continue_work on CLOSED downgrades, OPEN does not
12. `tests/project_next/fixtures/golden/*` - regenerate for 1.4 (plus scenarios.json if needed)
13. `tests/test_project_next_contract.py` - negative controls: wayfinder label route; map unreadable vs absent
14. `.claude/commands/project/next.md` - document the new section and map line; regenerate codex/skills mirror

Out-of-tree: label #864 `evergreen`; file item 5 as a follow-up issue.

Scope: ~14 files, ~400-600 lines. Risks: contract 1.4 adds a fifth partition (all consumers in-repo, updated here); `evergreen` default also parks #871.
