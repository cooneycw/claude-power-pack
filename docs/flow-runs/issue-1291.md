# Flow run record - issue #1291

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1291
- Base SHA:          164fdd4d23f2eaf66ef4ba30408824f7c589c417
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner (cooneycw), interactive "approved" in the /flow:auto session
- Recorded at:       2026-09-28T12:00:00Z

## Section B evidence
Commits on .claude/commands/qa/, codex/skills/qa-*, templates/qa.yml.example,
scripts/playwright-desk.py since 2026-09-27T13:33Z: none. PRs merged since:
#1302, #1296, #1295, #1293, #1287, #1286, #1284 - none touch QA/Playwright.
Related issues: #1292 (sequence index only), #1289 and #1290 (kept distinct by
#1292), #423/#421/#419 (closed Playwright migrations, no regression export).
No duplicate.

## Section C - the approved plan
1. `.claude/commands/qa/test.md` - opt-in Step 7b: export a confirmed bug as a regression test via the helper; report file, run command, trace path
2. `codex/skills/qa-test/SKILL.md` - regenerated Codex mirror
3. `scripts/qa-regression-export.py` - `export` (repro spec -> spec file, opt-in, no-secret schema, missing-runner refusal) and `run` (reproduced/passed/unavailable/error classification)
4. `tests/fixtures/qa_regression/consumer/` - local fixture app (buggy/fixed via env), package.json + lockfile, playwright.config.mjs with webServer, .claude/qa.yml, repro.json
5. `scripts/qa-regression-demo.sh` - three-arm demonstration: buggy=reproduced, fixed=passed, no server=unavailable
6. `tests/test_qa_regression_export.py` - unit tests runnable without Node
7. `templates/qa.yml.example` - regression_export section
8. `.claude/commands/qa/help.md` - one line on the export
9. `Makefile` - qa-regression-demo target (NOT in verify)
10. `.woodpecker.yml` - qa-regression-demo step in pinned Playwright image
11. `.gitignore` - fixture node_modules/test-results/playwright-report
12. registries the checks demand (scripts inventory, instrument census, verify-coverage, ci-coverage)

Scope: medium-large, ~600-800 lines including fixture.
Risks: CI network for image pull and npm ci; @playwright/test version must match
the image browser revision; coverage checks may force a specific registry shape.
