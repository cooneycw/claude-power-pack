# Flow run record - issue #1278

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=080707591ea2412582b88413932b239f -->
## Run 1

- Run-id:            080707591ea2412582b88413932b239f
- Run-start:         430b98538ec10b05bf5abf554b609f3ee4849f8c
- Issue:             #1278
- Base SHA:          430b98538ec10b05bf5abf554b609f3ee4849f8c
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6535, replying to plan 6534), on the operator's approval of a release (6533)
- Recorded at:       2026-10-17T07:40:00Z

### Section B evidence
git log 41a7845..430b985: 254 commits (feat 65 incl one `!` PR #1224; fix 149; docs 15; test 9; refactor 5; chore 4; ci 3; perf 2; other 1; wip 1). [Unreleased] cites 22 of 221 feat/fix/perf/refactor commits; 13 test-only fixes omitted; 186 to backfill. No release since v8.0.0 (#1353 closed, #1356 moved entries). Major items verified live: PRs #1224 #1230 #1038 #1186 #1187 #1188 #1332 #1463 #1468 #1467 MERGED; issues #1206 #1017 #1080 #1081 #1082 #1320 #1452 #1461 #1453 CLOSED.

### Section C - the approved plan
1. `CHANGELOG.md` - [9.0.0] - 2026-10-17 with a Breaking block (six items, each naming the consumer action), and 186 title-derived one-line entries grouped under Added / Changed / Fixed / Removed, each citing PR and issue; a fresh empty [Unreleased].
2. `pyproject.toml` - version 9.0.0.
3. `uv.lock` - re-locked.
4. `README.md` - the line-3 banner **v9.0.0**, plus a ### v9.0.0 section including "what this release is not / still owed".
5. `CLAUDE.md` - Current version: 9.0.0.
Grep for 8.0.0 and account for every hit; check-version-consistency and make verify. No tags or GitHub release. Refs #1278 only.
Risks: title-derived entries are less rich than prose (said in the PR); a missed version site (the grep and the consistency check guard it).
