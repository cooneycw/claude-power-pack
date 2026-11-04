# Flow run record - issue #1618

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=8d339735690b44f7bc53e3a8b12bcf7b -->
## Run 1

- Run-id:            8d339735690b44f7bc53e3a8b12bcf7b
- Run-start:         cac8eba2ca480eb52236ee2a33e6a91299a825fd
- Issue:             #1618
- Base SHA:          cac8eba2ca480eb52236ee2a33e6a91299a825fd
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (repository owner, replied "approved" to Section C in the interactive session)
- Recorded at:       2026-11-04T00:00:00Z

### Section B evidence
Commits since filing touching scripts/ or .claude/commands/{project,spec}: none.
Merged PRs since filing: none. Open PRs: none.
Duplicate/superseding issues: none. #1619 is a sibling (project-next.py missing
from the same list) with its own acceptance; #688 (curated list decision) closed.
Sibling worktrees with unpushed commits on these paths: none; none unreadable.

### Section C - the approved plan
1. `scripts/flow-helpers-install.sh` - add speckit-tasks-to-issues.sh to HELPERS beside speckit-context.py, with a comment explaining the pairing
2. `.claude/commands/project/init.md` - run ~/.claude/scripts/speckit-tasks-to-issues.sh
3. `.claude/commands/spec/adopt.md` - same change at the step list and the preview and create commands
4. `.claude/commands/spec/help.md` - same change at both commands
5. `.claude/commands/evaluate/help.md` - same change
6. `.claude/commands/evaluate/issue.md` - same change
7. `.claude/commands/flow/wave.md` - same change
8. `tests/test_speckit_tasks_to_issues.py` - installed-copy dry-run from an unrelated repo, and a guard that no command document prints a relative invocation
9. `docs/scripts.md` - record the install membership in the speckit-tasks-to-issues entry
10. `CHANGELOG.md` - add an entry if the repo's convention calls for one

Scope: 10 source files, about 60-90 lines, plus regenerated codex/skills mirrors. Small.
Risks: older hosts need /flow:repair or /cpp:update before the new path exists
(the failure is loud); flow-repair and flow-doctor Codex bundles carry only some
helpers, confirmed by the test suite. The converter is deliberately not added to
the permissions template: it creates GitHub issues, so a prompt is correct.
