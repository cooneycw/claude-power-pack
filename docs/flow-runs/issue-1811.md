# Flow run record - issue #1811

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=15008b78315749218f268bf83d96d4c1 -->
## Run 1

- Run-id:            15008b78315749218f268bf83d96d4c1
- Run-start:         e32c06edfb52175e4a0678fe51a9a6aea56f671d
- Issue:             #1811
- Base SHA:          e32c06edfb52175e4a0678fe51a9a6aea56f671d
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          run136:cp-orch, mailbox 36336
- Recorded at:       2026-11-21T14:54:46Z

### Section B evidence
#1809 / PR #1815 supplied approval/compliance; #1849 supplied composite finish and parity expansion. #1811 still exempts drift/head-check for all three drivers.

### Section C - the approved plan
1. `templates/delegated-driver-core.md` - add one finish call after push/PR; retain early compliance; offset words through audited acceptance-prose compression, preserving explicit partial-delivery nonclosure.
2. `.claude/commands/codex/auto.md` - render shared core.
3. `.claude/commands/qwen/auto.md` - render shared core.
4. `.claude/commands/gemma/auto.md` - render shared core.
5. `docs/agents/driver-parity.json` - six drift/head-check entries become run.
6. `tests/test_delegated_plan_finish.py` - actual-render ordering/verdict regressions and committed controls.
7. `tests/fixtures/delegated-plan-finish/missing-finish.md` - known-bad Step 7 render.
8. `tests/fixtures/delegated-plan-finish/finish-before-pr.md` - known-bad Step 7 render ordering.
9. `tests/fixtures/delegated-plan-finish/good-finish.md` - known-good Step 7 render.
Scope: drift/head-check rows only; Refs #1811; no budget cap changes, helper behavior changes, merge, or unrelated lane-review cleanup.
Risks: duplicate compliance is deliberate; static tests prove documented placement, not live model execution; compressed prose must preserve each instruction.

### Lanes for this change
| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | No checkout-resolution behavior changes. |
| Harness | will test | Claude install command sources and rendered text directly; existing Codex install flow-auto mirror parity; delegated families are not packaged. |
| Driver | will test | `/flow:auto` (Claude implements) / delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`): real renders and flow-derived verb parity. No live delegated run claim. |
| Coordination | not applicable | No with/without Kyle behavior changes. |
| CI provider | not applicable | No provider logic changes; exact-head own CI is separate evidence. |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not: record present, absent and unverified documented dispositions; existing helper wrapper/run tests cover semantics. |
| Toolchain version | not covered | Host and pinned CI only; no version matrix. |
| Clone shape | not applicable | No ref-resolution changes. |
| Run location | not applicable | No path-resolution changes. |
| Gate target | not applicable | No runner/toolchain behavior changes. |
| Wave role state | not applicable | No role lifecycle changes. |

### Changed output readers
Parent orchestrators read all three generated command documents; tests inspect actual renders and known-bad/good Step 7 excerpts. Parity reads command output, six policy rows and the helper composite table. Owner/reviewer read PR and evidence. Static checks do not establish live execution.
