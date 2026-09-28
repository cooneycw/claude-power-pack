# Flow run record - issue #1278

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=4e1ee446f0c643f68c9ef627f8565fb4 -->
## Run 1

- Run-id:            4e1ee446f0c643f68c9ef627f8565fb4
- Run-start:         31b5a2ff4d719a92d5beda4c36e08c6f05f804aa
- Issue:             #1278
- Base SHA:          31b5a2ff4d719a92d5beda4c36e08c6f05f804aa
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run48:cpp2-orch (orchestrator), mailbox message 2484 replying to plan 2483
- Recorded at:       2026-09-28T22:19:30Z

### Section B evidence
Commits on `git log --no-merges 41a7845..31b5a2f`: 188 in all. By type: feat 49 (1 `!`: e1379c7 / PR #1224), fix 105, docs 12, test 8, refactor 5, chore 3, perf 2, ci 2, wip 1, other 1. The five since the c6b02fa snapshot are 7b4c9a3, e129a1a, 75fb449, 846431d and 31b5a2f. In CHANGELOG.md, the [8.0.0] section had 28 top-level entries at 41a7845 and has 41 now. The 13 extras are dated 2026-09-16..20. [Unreleased] holds 4 entries. The major-version consumer actions were re-verified live: #1206 is closed, and PRs #1224 and #1230 are merged. PR #1038 is merged. PRs #1186, #1187 and #1188 are merged. #1320 is closed via PR #1332. No duplicate release issue is open.

### Section C - the approved plan
This is release PREPARATION: local commits only, and the cut waits for #1341 and #1342.

1. `CHANGELOG.md` - (a) Move the 13 misfiled entries verbatim from [8.0.0] into [Unreleased], each under its original subsection (Removed 4, Added 7, Fixed 2). Control: [8.0.0] must be byte-identical to 41a7845's, and a mutation that moves one fewer entry must turn that check red. (b) Backfill [Unreleased] from 41a7845..main with every feat and user-visible fix, one entry per issue. A per-commit coverage table maps each feat/fix to an entry or to a listed omission, and 5 random SHAs are spot-checked against it.

Scope: CHANGELOG, roughly 110 new entries. The README v9.0.0 draft is sent for review and kept out of the tree until the cut, and the version sites are edited at the cut.
Risks: the volume invites missing or wrong entries, which the coverage table and spot-check address; the "user-visible" classification is a judgement, which the listed omissions make reviewable; nested-bullet moves are covered by the byte-identical check.
