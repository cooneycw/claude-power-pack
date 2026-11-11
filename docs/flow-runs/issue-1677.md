# Flow run record - issue #1677

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=dbafb8edfde54b91b5ef16b99ef0b99e -->
## Run 1

- Run-id:            dbafb8edfde54b91b5ef16b99ef0b99e
- Run-start:         dca1ac6bdcb8db2410b6238b470290660d1df364
- Issue:             #1677
- Base SHA:          dca1ac6bdcb8db2410b6238b470290660d1df364
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), typed "approved" in the driving session after the Step 3 report
- Recorded at:       2026-11-11T18:59:00Z

### Section B evidence
Commits on origin/main since filing (2026-11-11T18:48:43Z): none (tip dca1ac6b).
PRs merged 2026-11-11: #1675, #1676 - neither touches the provider record.
Open PRs: none. Duplicate/superseding issues: none (origin: Nit Store #864 comment 6804396488).

### Section C - the approved plan
1. `lib/cicd/providers.py` - a linked worktree with no `.claude/cicd.yml` reads the main checkout's record when that record is untracked; source names the path; remedy text says track the file or record it in the main checkout
2. `lib/cicd/host.py` - no behaviour change; its `main_checkout()` locator is reused via a lazy import
3. `scripts/ci-provider-advisory.sh` - new: one advisory line when a project with CI files or `.claude/` has no usable record; silent otherwise; always exit 0
4. `scripts/hook-pending-retro.sh` - third independent advisory calling item 3; `CPP_HOOK_SKIP_CI_PROVIDER=1` suppresses
5. `.claude/commands/cpp/update.md` - a step running item 3 for the session's project, carried to the summary
6. `tests/test_cicd_providers.py` - red case (worktree without record, main with one) plus tracked-main, own-record and no-record cases
7. `tests/test_hook_pending_retro.py` - advisory speaks with no record, silent with one
8. `controls/ci-provider-advisory/control.json` - committed negative control for the advisory
9. `docs/decisions/0012-per-project-ci-provider.md` - record the worktree rule
10. `CHANGELOG.md` - migration note

Scope: ~9 source files, 250-350 lines including tests.
Risks: the fallback softens "absent means unknown" (limited to an untracked main record); pipeline generation (`CICDConfig.load`) does not use the fallback; the session-start hook is opt-in and cannot reach running sessions.
