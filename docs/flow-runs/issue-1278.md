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

<!-- flow-run n=2 id=22f48a32d3ba4f84b9c9898c695ae2fc -->
## Run 2

- Run-id:            22f48a32d3ba4f84b9c9898c695ae2fc
- Run-start:         7a8941f998bac816ad71a03cfd90f5e3a50ec91e
- Issue:             #1278
- Base SHA:          7a8941f998bac816ad71a03cfd90f5e3a50ec91e
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 8377, replying to plan 8376), on the operator's 2026-10-21 approval of a release (assignment 8374)
- Recorded at:       2026-10-21T05:02:49Z

### Section B evidence
git log 0203495..7a8941f9: 34 commits (fix 25, test 4, feat 2, docs 2, perf 1), PRs #1474 #1475 #1480 #1481 #1482 #1500 #1501 #1502 #1505 #1507 #1509 #1510 #1511 #1512 #1514 #1515 #1516 #1519 #1521 #1522 #1523 #1525 #1528 #1529 #1530 #1531 #1533 #1534 #1535 #1536 #1537 #1538 #1539 #1540, all merged. [Unreleased] empty. No open release PR (only open PR #1393). Duplicates/superseding: none (#938, #544 closed; #1479, #1222 unrelated). Classification MAJOR: one consumer action, #1489 / PR #1500 (gh-pr-merge no longer auto-retries with --admin). Approver notes: #1490 entry must say a failed label fetch now refuses; `canceled` is additive, so parsers should treat unknown values as non-code; link Nit Store comment 6308466945 in the PR body.

### Section C - the approved plan
1. `CHANGELOG.md` - [10.0.0] - 2026-10-21 with a Breaking block (#1489), then Added / Changed / Fixed / Removed covering every feat and user-visible fix, each citing PR and issue; test-only and perf summarised; a fresh empty [Unreleased].
2. `pyproject.toml` - version 10.0.0.
3. `uv.lock` - re-locked.
4. `README.md` - line-3 banner **v10.0.0**; new ### v10.0.0 (2026-10-21) section with the breaking item, highlights and "what this release is not"; the line-156 milestone sentence names v10.0.0.
5. `CLAUDE.md` - the current-version line reads 10.0.0.
Scope: 5 files, ~150-200 lines. Risks: under-classification (would lengthen Breaking, not change MAJOR); a missed version site (grep + check-version-consistency); a stray closing keyword (GraphQL closingIssuesReferences before merge). No tag, no GitHub release, Refs #1278 only.

### Agreed deviation (#859), during Step 4
- Found: `scripts/check-version-consistency.py` exits 1 on Run 1's record above (it quotes the v9.0.0 plan's current-version line), with every real site at 10.0.0. Editing Run 1 would break #1320, so the plan could not reach a green `make verify` as approved.
- Agreed: master:kyle, mailbox message 8381 (reply to 8380). Exclude exactly `docs/flow-runs/` from the phrase scan, with a two-sided committed control, in this PR.
- Added files:
6. `scripts/check-version-consistency.py` - exclude `docs/flow-runs/` from the phrase scan, beside `vendor/`; docstring says why.
7. `tests/test_version_consistency.py` - a flow-run record quoting an old version stays clean (red on the unfixed checker); a stale CLAUDE.md beside such a record still fails.
- Also reworded this run's own Section C item 5 so it does not quote the phrase (for the next release's sake).
- Effect on outcome: none to the release; one gate narrowed by one historical path.

<!-- flow-run n=3 id=eb5535cf1f194314ac39eb1888b3e77c -->
## Run 3

- Run-id:            eb5535cf1f194314ac39eb1888b3e77c
- Run-start:         cacc4564b6f2375d344b3f6090d4cb4de1910fc7

- Issue:             #1278
- Base SHA:          cacc4564b6f2375d344b3f6090d4cb4de1910fc7
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          release coordinator, mailbox 13557, carrying the operator ruling on the accepted release proposal
- Recorded at:       2026-10-28T22:15:04.185898+00:00

### Section B evidence
The last milestone is PR #1541 at b318a14b; the current base is cacc4564. The complete release inventory has 35 commits (fix 20, feat 6, unprefixed 6, chore 1, test 1, docs 1). Every final PR body and merge OID was checked live: #1545, #1546, #1548, #1549, #1550, #1553, #1558, #1556, #1559, #1561, #1566, #1565, #1568, #1569, #1570, #1573, #1574, #1575, #1579, #1581, #1582, #1583, #1588, #1589, #1590, #1591, #1592, #1593, #1594, #1595, #1597, #1598, #1599, #1601, #1602. The two additions to the accepted proposal are 0121af19 / PR #1601 (native Codex patch input) and cacc4564 / PR #1602 (argv gate). Duplicate/superseding issues considered: #938 and #544 are historical; #1479 and #1222 concern different work. No open release PR and no unpushed implementation in this fresh clone's sibling worktrees. The evergreen still calls for this release; no product change is required.

### Section C - the approved plan
1. `CHANGELOG.md` - fresh empty Unreleased and v10.1.0 section covering all 35 commits, prominent Behaviour changes you may notice, and the verbatim owner override of the major-bump rule.
2. `pyproject.toml` - package version 10.1.0.
3. `uv.lock` - re-lock the package's version.
4. `README.md` - line-3 banner, milestone explanation and new v10.1.0 notes, including consumer actions and no tag/GitHub release.
5. `CLAUDE.md` - update the current-version line to 10.1.0.
Scope: five release files, approximately 200 lines, plus this append-only run/snapshot and a genuine review receipt. Risks: omitted actions, stale issue claims, version drift and accidental evergreen closure. Mitigations: complete ledger, live tracker verification, version-consistency check and Refs-only PR. No material concern with this documentation/version-only approach. The operator explicitly supersedes the normal major rule for this release: "CPP didn't augment anything new. if anything, v10.1". Refs #1278 only; no tag or GitHub release.
