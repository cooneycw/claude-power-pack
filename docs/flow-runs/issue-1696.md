# Flow run record - issue #1696

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=9dc3eee1efc04d7e8c57d683426800e3 -->
## Run 1

- Run-id:            9dc3eee1efc04d7e8c57d683426800e3
- Run-start:         658cdd55a18af8d54472f47e3ac3736929dc9385
- Issue:             #1696
- Base SHA:          658cdd55a18af8d54472f47e3ac3736929dc9385
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, authority model orchestrator-only; the owner delegated wave decisions to it), by mailbox rev 3: "GATE: GO-WITH-CONDITIONS #1696"
- Recorded at:       2026-11-11T23:13:46Z

### Section B evidence
- commits since 2026-11-11T22:13:40Z: 658cdd55 (#1704, the #1695 prerequisite; delivers none of this issue's four parts), f63dc946 (#1702, unrelated), ca8652a8 (#1694, unrelated)
- merged PRs: #1704, #1702, #1694; open and unrelated: #1701
- duplicate/superseding issues: none (#1699 names the lane file only as a release item)
- this host: the #1703 worktree's commits 0d17f797, fed579f7, 4b864669 touch project/init.md, scripts/codex-skill-sync.py and .claude/command-word-budgets.tsv; a sequencing constraint, not a duplicate

### Conditions attached to the approval
- The survey stays a checklist in the command document; the only script is scripts/lane-file.py (age, stamp).
- A lane file that exists and cannot be read (unreadable file or directory, dangling symlink) is unknown, never absent.
- The verdict is carried by the LANE_FILE_AGE: line; the plan step relays it and continues on every exit code.
- The project/init.md edit is not committed until the orchestrator says #1703 has merged.
- eli5.md stays at 2651 words; no existing budget number is raised.
- The PR names the blind anchor's result: the always-fresh version must miss the 61-day case.

### Section C - the approved plan
1. `scripts/lane-file.py` - new helper, mode 100755, resolves the checkout root: `age` (fresh / stale / unknown / absent from the Reviewed: date inside the file, `--threshold-days` default 60, `--today` for deterministic cases) and `stamp` (sets the Reviewed: date, changes nothing else). Not under scripts/flow-* or lib/cicd
2. `.claude/commands/lane/create.md` - survey checklist, draft shown before writing, each row cites its evidence, refuses to overwrite and points at /lane:update
3. `.claude/commands/lane/update.md` - re-survey; three lists (missing, evidence gone, unchanged); fix issues closed since the last review to scan; writes only what the owner accepts; stamps the date even when nothing changed
4. `.claude/commands/lane/help.md` - family help page
5. `.claude/commands/project/init.md` - one Step 4 sub-step after CI providers are recorded: create the lane file. HELD: not committed until you say #1703 merged; paid for by an equal trim against #1703's 3848
6. `.claude/commands/flow/eli5.md` - the lane pointer gains the age advisory (run `lane-file.py age`, relay stale or unknown with /lane:update, never block); equal trim, budget stays 2651; under the owner's freeze exception
7. `.claude/command-word-budgets.tsv` - three new lane documents declared; no existing number raised
8. `scripts/codex-skill-sync.py` - `lane` added to FAMILIES
9. `controls/lane-file-age/control.json` - registers the age check's negative control
10. `controls/lane-file-age/cases/bad-one-day-past/.claude/lanes.md` - reviewed 61 days before the pinned --today: flagged
11. `controls/lane-file-age/cases/good-at-threshold/.claude/lanes.md` - reviewed exactly 60 days before: not flagged
12. `controls/lane-file-age/cases/bad-no-review-date/.claude/lanes.md` - no readable date: reported unknown, never fresh
13. `controls/lane-file-age/anchors/constructed-always-fresh-lane-file-age.py` - the blind anchor (a version that always says fresh) proving the control can fail
14. `controls/census.md` - census row for the new instrument
15. `.claude/verify-coverage.json` - how the new script is accounted for
16. `docs/scripts.md` - one inventory line
17. `docs/scripts/lane-file.md` - the script's own page
18. `docs/agents/lanes.md` - the two commands, the advisory, and the updated "what enforces this" section
19. `docs/commands-reference.md` - the lane family
20. `CLAUDE.md` - command list line
21. `CHANGELOG.md` - entry
22. `tests/test_lane_file.py` - age boundaries, unknown states, stamp, root resolution from a subdirectory and a linked worktree, and the routing of both commands and init to the helper
Scope: 22 files, about 700 lines; one small script, three command documents, the rest registrations, docs and tests.
Risks: (a) the age advisory is new machinery, even if small - if it is routinely dismissed the issue itself says to drop it; (b) exit codes: I propose `age` exits 0 for fresh and absent, 3 for stale, 4 for unknown, with a `LANE_FILE_AGE:` verdict line - advisory, so the plan step relays it and continues on every code; (c) the init.md edit lands on a document #1703 is changing, so I will merge main after #1703 and re-measure the budget before committing it; (d) no output Kyle or skillc reads today changes - every line here is new.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test: the helper finds the file from a subdirectory and from a linked worktree (reads that worktree's own copy) |
| Harness | will test: `lane` builds as Codex mirrors in the gate. A live Codex-driven /lane:create: not covered |
| Driver | not applicable: no review or delegated-driver text changes |
| Coordination | not applicable: nothing here talks to Kyle |
| CI provider | not applicable: the helper reads one file; the survey checklist NAMES CI providers as lane evidence but changes no CI behaviour |
| Project state | will test: lane file absent (silence), present and fresh, stale, undated, unreadable |
