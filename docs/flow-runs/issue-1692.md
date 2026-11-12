# Flow run record - issue #1692

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=b5545e7430c2453e840727dcc0dae876 -->
## Run 1

- Run-id:            b5545e7430c2453e840727dcc0dae876
- Run-start:         f63dc946fe65b9d2ea9df3a5446dd8380c551da7
- Issue:             #1692
- Base SHA:          f63dc946fe65b9d2ea9df3a5446dd8380c551da7
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, authority model orchestrator-only), by mailbox rev 2 to role cpp-1508 at 2026-11-11T17:59:37-05:00: "GATE: GO-WITH-CONDITIONS #1692"
- Recorded at:       2026-11-11T23:00:04Z

### Section B evidence
- Commits on the four files since filing (2026-11-11T22:01Z): none.
- Merged PRs since filing: #1694, #1702; neither touches the four files. No open PR touches them.
- Related issues read: #1673 (parent, the freeze), #1700, #1690 (no flow/cicd disposition list yet), #1669.
- Line counts at f63dc946, unchanged from the baseline at 15521b1e: flow-finish-gate.sh 1,796; runner.py 2,074; steps.py 1,869; outcomes.py 637.

### Section C - the approved plan
Conditions attached to the approval: no change to the verdict line, exit codes, the stderr trailer, the two skillc marker strings, the runner JSON layout and field order, or the argument shapes; declared-gates, plan-reconciliation and subsumption controls run before and after; an independent old-versus-new read before the Codex review; before and after line counts from named commits; any converted or deleted test named in the PR. The condition to convert tests that pass rerun_failed=True was answered with a PUSHBACK (mailbox rev 3): those tests pass it to the DeterministicRunner constructor, which is not removed.

1. `lib/cicd/steps.py` - remove `_reads_makeflags`, `_MAKEFLAGS_SENSITIVE`, `_MAKE_INVOCATION`, `_GENERATED_CONDITIONAL`, `_TARGET_VARIABLE` with the comment describing their retired allowlist, the unused `StepExecutor` protocol, and the stale "tracked separately" subsumption comment.
2. `lib/cicd/runner.py` - remove the `rerun_failed` parameter of `run_plan` and `resume_run`, the duplicated `get_plan_steps` call in `resume`, the second `_failing_prerequisite` computation; build `RunResult`'s repeated gate lists in one helper; call `classify_unparsed` once.
3. `lib/cicd/outcomes.py` - remove the control-field sums in `_aggregate`.
4. `scripts/flow-finish-gate.sh` - one body for `run_fallback_gate`'s make and uv branches; one function for the three array-of-strings JSON readers; one runner invocation; one script-directory lookup.
5. `tests/test_flow_finish_gate.py` - only where a test pinned a removed symbol or shape.
6. `tests/test_runner.py` - only where a test pinned a removed symbol or signature.
7. `tests/test_cicd_outcomes.py` - only where a test pinned a removed symbol.
8. `docs/scripts/flow-finish-gate.md` - one line recording what was removed.

Scope: 4 source files plus tests and one doc line; an estimated 180 to 250 lines removed of 6,376.

Risks: the shell parses the runner's JSON by line layout, so the merged reader must keep exact matching including the one-line empty array; a structural test requires every verdict call to be followed by a matching gate_exit; "nothing calls it" is established inside this repository and by grep of kyle and skillc.

Not in this change: the history-comment pass (second PR under #1692), the Makefile fallback lane, FLOW_GATE_RERUN=0, the two old-runner guards, the coordination supervisor, cm_enrolment_evaluate.
