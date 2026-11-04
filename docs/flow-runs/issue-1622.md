# Flow run record - issue #1622

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=390f2c7924014b34ae5ce04090675141 -->
## Run 1

- Run-id:            390f2c7924014b34ae5ce04090675141
- Run-start:         88c0b5c71cd63802b0d8d1931531dff38a6c7215
- Issue:             #1622
- Base SHA:          88c0b5c71cd63802b0d8d1931531dff38a6c7215
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (repository owner, in the interactive session)
- Recorded at:       2026-11-04T18:30:00Z

### Section B evidence
Commits since filing: none (HEAD..origin/main empty at 88c0b5c7). Merged PRs: #1620 only, merged 17:23Z, 8 minutes before filing, fixing the install path (#1618), not this. Duplicates/superseding: none; inspected #1618, #857, #858, #607, #722, #864.

### Section C - the approved plan
1. `.claude/commands/project/init.md` - rewrite Step 5 (draft real spec/plan/tasks, dry-run preview, approve/edit/decline, commit and push .specify before sync), rewrite Step 6 summary, resume checks and error handling, remove the /spec:adopt line
2. `scripts/speckit-tasks-to-issues.sh` - refuse unfilled placeholder tasks in the parse stage via the malformed path (exit 3), before anything is created, including under --dry-run
3. `tests/test_speckit_tasks_to_issues.py` - cover refusal of {First task} and the template forms including --dry-run, and pin that /users/{id} still passes
4. `tests/test_speckit_handoff_integration.py` - run from a non-CPP project through to issues created with the packaged converter and stub gh
5. `tests/test_project_init.py` - check the command document: no placeholder remains, push before sync, no /spec:adopt line, summary names /flow:auto
6. `.claude/commands/project/help.md` - update item 7, which still says Optionally creates
7. `docs/scripts.md` - add the entry for the refusal
8. `.specify/templates/tasks-template.md` - note in Issue Sync that unfilled tasks are refused

Scope: 8 source files, about 200 lines, plus generated codex/skills mirrors.
Risks: tests cannot execute a markdown command document, so the model-driven drafting itself is not run; existing projects with an already-filed placeholder task get a refusal on re-run until the line is fixed; Step 6's commit may find nothing to stage on a resumed run.
