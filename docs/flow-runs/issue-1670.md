# Flow run record - issue #1670

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=23996a41302542b080bb46db5b41b385 -->
## Run 1

- Run-id:            23996a41302542b080bb46db5b41b385
- Run-start:         dca1ac6bdcb8db2410b6238b470290660d1df364
- Issue:             #1670
- Base SHA:          dca1ac6bdcb8db2410b6238b470290660d1df364
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner, in the driving session ("approved"), choosing the single-PR route with the skillc issue filed first
- Recorded at:       2026-11-11T18:13:50Z

### Section B evidence
- commits since filing (2026-11-11T14:58:27Z): c230b667 (#1675), dca1ac6b (#1676); neither addresses the issue, both appear in the codex/skills path log
- merged PRs: #1675, #1676; open PRs: none
- duplicate/superseding issues: none; related and read: #1408, #1267, #556, #575, #1367
- sibling worktrees: none with unpushed commits on these paths; one scratch worktree (t008/cpp-pin) unreadable, so unexamined
- consult: Codex read-only answer on the issue, https://github.com/cooneycw/claude-power-pack/issues/1670#issuecomment-6802948404
- corrections to the issue: the gate is codex-skills-check, not skills-check; the Assumption is false - skillc reads codex/skills/ from git at a pinned CPP commit

### Section C - the approved plan
1. `docs/decisions/0013-codex-mirrors-are-build-output.md` - new ADR: mirrors constrain the installed tree, not the repository; skillc consequence and rollback
2. `.gitignore` - ignore codex/skills/ except its README.md; drop the two negations that only served tracked mirrors
3. `codex/skills/README.md` - reworded: the directory is build output; the 346 generated files leave the index
4. `scripts/codex-skill-sync.py` - add --output-root; --install generates into a private tree, validates it, then publishes; --check reports "not generated" as its own state
5. `scripts/install-drift.sh` - compare installed skills against a fresh generation; report unexamined when it cannot generate
6. `Makefile` - codex-install and codex-init become generate-validate-install; readers of the tree depend on codex-skills
7. `.woodpecker.yml` - one codex-skills-generate step; steps that read the tree depend on it
8. `tests/conftest.py` - generate the build tree once at session start
9. `tests/test_codex_skill_sync.py` - replace committed-tree tests with validated-install, --output-root and not-generated tests
10. `tests/test_install_drift.py` - drift against derived expectations and the unexamined verdict
11. `controls/codex-skill-install-fidelity/control.json` - new registered negative control: a mirror altered with its manifest recomputed is refused at check and at install; an intact tree installs
12. `docs/decisions/0008-instrument-negative-control-bound.md` - census entry for the new control
13. `.claude/commands/flow/auto.md` - remove the stage-and-commit codex/skills instructions
14. `.claude/commands/flow/finish.md` - same removal
15. `.claude/commands/flow/merge.md` - same removal
16. `tests/test_codex_skill_resync.py` - update the pins on that flow text
17. `.claude/commands/cpp/init.md` - Tier 5 wording: installs generated skills
18. `.claude/commands/cpp/update.md` - Step 7.9 wording, same
19. `CLAUDE.md` - project-map line for codex/skills/
20. `docs/scripts.md` - entries for the two changed scripts
21. `docs/commands-reference.md` - the install and drift description
22. `scripts/check-md-relative-links.py` - only if --codex-skills needs a tree-not-generated state

Scope: about 22 files edited, roughly 700-900 lines, plus 346 index deletions.
Deferred to the Nit Store: retiring codex-skill-resync.sh, its control, and the mirror-attribution code in flow-plan-record.py and flow-wave-registry.sh.
Risks: skillc's next CPP re-pin breaks until it exports the pin and runs the generator (skillc issue filed before merge); Kyle's cpp_adapt_pin certifies --install as write=copy; tests that mutate the shared build tree may race under parallel pytest; a plain git pull still leaves ~/.codex/skills behind until an install runs.
