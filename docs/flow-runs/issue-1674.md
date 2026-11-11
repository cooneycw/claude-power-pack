# Flow run record - issue #1674

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=e7c87a3574ac4b75b3f4282077ce51f7 -->
## Run 1

- Run-id:            e7c87a3574ac4b75b3f4282077ce51f7
- Run-start:         31fe6a69cf99992c55d75fe8bbac5cbdc651a4a9
- Issue:             #1674
- Base SHA:          31fe6a69cf99992c55d75fe8bbac5cbdc651a4a9
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner (cooneycw), in the interactive session, replying "approved" to the Step 3 report
- Recorded at:       2026-11-11T15:19:18Z

### Section B evidence
- commits: none touching lib/project_next, scripts/project-next.py, tests/project_next or controls/project-next since the issue was filed (main tip 31fe6a69, 2026-11-09)
- PRs: none merged since filing; none open
- dup/super: none (searches "project-next prunable worktree", "project-next FileNotFoundError worktree" matched only #864)
- siblings: no unpushed commits on these paths; one entry unexamined - the prunable worktree itself

### Section C - the approved plan
1. `lib/project_next/collect.py` - read the porcelain "prunable" line per worktree entry; when present or the directory is missing, skip the git calls and record the worktree unexamined with a warning naming the path. The shared command runner converts could-not-start errors (OSError) into CollectionError.
2. `tests/project_next/test_collection.py` - two regression tests: a real git repo whose worktree directory was deleted, and the runner's error conversion. Both must fail on the pre-fix code.
3. `lib/project_next/ownership.json` - re-pin the engine checksums with make project-next-repin.

Scope: 3 files, about 80 lines.
Risks: the runner change also converts a missing git/gh binary into a collection warning; no new case is added to controls/project-next unless make verify demands one; make verify may require regenerated mirrors or census entries.
