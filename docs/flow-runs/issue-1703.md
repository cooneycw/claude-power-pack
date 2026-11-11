# Flow run record - issue #1703

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=3ade43914a2546409adfe59f4fc60f53 -->
## Run 1

- Run-id:            3ade43914a2546409adfe59f4fc60f53
- Run-start:         f63dc946fe65b9d2ea9df3a5446dd8380c551da7
- Issue:             #1703
- Base SHA:          f63dc946fe65b9d2ea9df3a5446dd8380c551da7
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner, in the interactive session ("nope. that's good. approved"), after declining to merge the review issue with the Nit Store. The two open sub-decisions were not answered separately and took the recommended defaults stated with the plan: dated follow-ups as labelled issues, and /project:next names /monthly:create without running it
- Recorded at:       2026-11-11T22:44:40Z

### Section B evidence
- commits on origin/main since the issue was filed (2026-11-11T22:42:32Z): none.
- merged PRs inspected (same day, before filing): #1675, #1676, #1679, #1680, #1681, #1682, #1683, #1686, #1687, #1688, #1694, #1702. None adds a recurring-review mechanism.
- duplicate/superseding issues considered: #1669 (open evergreen; becomes a checklist line), #1673 (open). None duplicates this.
- sibling worktrees on this host: 4, no unpushed commits touching project-next or the project commands.

### Section C - the approved plan
1. `lib/monthly_review/__init__.py` - new: shared rules; month coverage, per-source scan, three-way answer per source
2. `scripts/monthly-review.py` - new helper: status, scan, create (no second issue for a month)
3. `.claude/commands/monthly/create.md` - new command
4. `.claude/commands/monthly/review.md` - new command
5. `.claude/commands/monthly/help.md` - new family overview
6. `scripts/project-next.py` - monthly_review CPP extension and one report line per mode; engine untouched
7. `.claude/commands/project/next.md` - document the extension and its route
8. `.claude/commands/project/init.md` - one step running /monthly:create
9. `.claude/command-word-budgets.tsv` - budgets for the new documents; raised for next.md and init.md
10. `scripts/codex-skill-sync.py` - add the monthly family
11. `tests/test_monthly_review.py` - new
12. `tests/test_project_next_monthly.py` - new
13. `docs/scripts/monthly-review.md` - new reference page
14. `docs/scripts.md` - index line
15. `.claude/verify-coverage.json` - account for the helper
16. `docs/commands-reference.md` - entries for the two commands
17. `CHANGELOG.md` - entry

Scan sources: the Nit Store (count, age, rollover due); every open evergreen issue; the friction log (this host only); open issues labelled follow-up with a Due: line at or before the month.

Scope: 17 files (8 new), roughly 900-1,100 lines including tests.
Risks: the closed-review lookup is one extra GitHub call and must read unknown, never none, when it fails; the project-next report gains one JSON key and one text line (additive; any shape change to existing output triggers urgent coordination issues in kyle, skillc and kyle-candidate); the friction count is per host; a new script and command family touch several gated inventories.
