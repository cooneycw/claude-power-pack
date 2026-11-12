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

<!-- flow-run n=2 id=1a33605b47f94cf08659e9324a1d196b -->
## Run 2

- Run-id:            1a33605b47f94cf08659e9324a1d196b
- Run-start:         545267b95a6ff344829f9cd625c82b95e5f341ef
- Issue:             #1692
- Base SHA:          545267b95a6ff344829f9cd625c82b95e5f341ef
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, authority model orchestrator-only), by mailbox rev 10 to role cpp-1508 at 2026-11-11T19:33:39-05:00: "GATE: GO-WITH-CONDITIONS #1692" (assignment a1692b-g2)
- Recorded at:       2026-11-12T00:34:04Z

### Section B evidence
- PR #1722 (545267b9) delivered the first pass: unreferenced code removed and duplicated shell paths merged. What remains under #1692 is the history-comment pass.
- Commits on the four files since 545267b9: none. Open PRs touching them: none; #1705 and #1707 are sequenced after this PR by the orchestrator.
- Comment-only lines at 545267b9: flow-finish-gate.sh 900 of 1,754; runner.py 614 of 2,070; steps.py 433 of 1,786; outcomes.py 107 of 629.

### Section C - the approved plan
Rule per comment block. KEEP: what the next line does when not obvious; a live constraint stated once in the present tense; the issue number as a pointer; every NEGATIVE-CONTROL marker; every shellcheck directive; the usage, verdict, exit-code and environment tables that --help prints. REMOVE: narration of how the code got here and constraints restated a second time. A removed block already recorded in docs/scripts is a deletion; otherwise it is a move, recoverable through a pointer to the commit and path.

Conditions attached to the approval: expect the number to shrink and report estimate against measured; a moved block stays recoverable through a commit-and-path pointer and docs/scripts/flow-finish-gate.md does not get longer; the move commit comes before the removal commit; the --help test also asserts the usage, verdict, exit-code and environment tables are present; an independent old-versus-new read before the Codex review; two review passes at most without asking; make lint and make typecheck before the gate; no push for CI until the merge slot is held; each mechanical proof is shown failing once on a one-line code mutation.

1. `scripts/flow-finish-gate.sh` - comment pass; --help prints up to an explicit end marker instead of a numbered line range.
2. `lib/cicd/runner.py` - comment pass (comments and docstring narration).
3. `lib/cicd/steps.py` - comment pass.
4. `lib/cicd/outcomes.py` - comment pass.
5. `docs/scripts/flow-finish-gate.md` - the recovery pointer for moved history, without lengthening the page.
6. `tests/test_flow_finish_gate.py` - a test that --help prints no code and still prints all four tables.

Scope: an estimated 500 to 800 source lines out across the four files; the estimate is expected to shrink on the line-by-line read.

Risks: a comment that reads as history is the only statement of a live constraint; tests or tools match comment text (the skill bundler, the negative-control scanner, tests that read the script body); #1705 and #1707 edit the same shell file and must branch after this lands.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: linked worktree (this run); the main checkout is not applicable, comments only |
| Harness | will test: Codex mirrors rebuilt and tests/test_codex_skill_sync.py; a live Codex run is not covered |
| Driver | not applicable: no driver-specific code |
| Coordination | not applicable: the supervisor's code is untouched; its control runs in the gate |
| CI provider | not applicable |
| Project state | will test: runner lane for real, fallback lane through its stubbed controls; not covered: bash 3.2 and macOS sed for the --help change |

<!-- flow-run n=3 id=38e309fe078b46d3a826d5b356b86ad6 -->
## Run 3

- Run-id:            38e309fe078b46d3a826d5b356b86ad6
- Run-start:         68d5fedf152b4446d35bd42f50e0b6c326ce43cb
- Issue:             #1692
- Base SHA:          68d5fedf152b4446d35bd42f50e0b6c326ce43cb
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, authority model orchestrator-only), by mailbox rev 37 to role cpp-1508 at 2026-11-11T23:09:01-05:00: "GATE: GO-WITH-CONDITIONS #1692" (assignment a1700hold-583-1710b-1728-g5, item 1, row 583)
- Recorded at:       2026-11-12T04:12:00Z

### Section B evidence
- Row 583 of the #864 dispositions is the last open row joined to #1692. PRs #1722 (545267b9) and #1733 (3eaf643d) did not reach `lib/cicd/makefile.py`.
- Commits on `lib/cicd/makefile.py` and `lib/cicd/makefile_declaration.py` since 2026-10-25: 802a140a (#1599) only, and it leaves the `.PHONY` block alone.
- Measured at 68d5fedf, regex against the declaration reader: this repository's Makefile 9 declared names (one a literal backslash) and 78 targets reported missing, against 76 and 10; skillc 9 and 8 against 16 and 0; kyle 84 and 5 both ways.
- Callers: none in kyle or kyle-candidate; skillc holds only pinned byte copies of this repository's source. One caller here, `lib/cicd/cli.py`.

### Section C - the approved plan
Conditions attached to the approval: the three new tests fail on 68d5fedf and the still-missing test passes on both; one more test pins `.PHONY: $(VAR)` as a known limit; the 10 targets really missing from this repository's `.PHONY` are not fixed here and go to the Nit Store as one comment; the PR states this repository's own line before and after; one review pass unless it returns a medium or higher; no push without the merge slot.

1. `lib/cicd/makefile.py` - `check_makefile` takes the declared `.PHONY` set from the declaration reader in place of the regex, and builds that reader once.
2. `tests/test_cicd_makefile.py` - tests on `check_makefile` for a continued declaration, a spaced colon, a trailing comment, a genuinely undeclared target, and the unexpanded-variable limit.

Scope: one function and five tests, about 50 lines.

Risks: a project that relied on the wrong list sees a different one; nothing gates on either list.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: pytest on the changed function in this linked worktree, red on 68d5fedf first |
| Harness | not applicable: no command document or skill text changes |
| Driver | not applicable: no driver-specific code |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | not applicable: no pipeline or CI-status code |
| Project state | not applicable: no issue, label or board writes beyond the PR |
