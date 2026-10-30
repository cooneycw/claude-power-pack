# Flow run record - issue #1604

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a532b3cb828140fc97e05b247347d0e2 -->
## Run 1

- Run-id:            a532b3cb828140fc97e05b247347d0e2
- Run-start:         626a96d927ae35776e062d6b4d2e6e19c24ab630
- Issue:             #1604
- Base SHA:          626a96d9
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner (interactive session reply "approved")
- Recorded at:       2026-10-30T10:55:00Z

### Section B evidence
- commits: none touching scripts/flow-ci-status.sh, flow-pr-watch.sh, gh-pr-merge.sh,
  branch-protection.sh, tests/test_flow_ci_status.py, controls/flow-ci-status*,
  lib/cicd/pipeline.py, templates/workflows since the issue was filed; none in
  a6643411..626a96d9 either.
- PRs: none merged since 2026-10-30T10:09Z.
- dup/super: none (#766, #155, #445 are older closed predecessors).

### Section C - the approved plan
Slice: acceptance items 1-5 (flow-ci-status.sh). Refs #1604; items 6-11 deferred.

1. `scripts/flow-ci-status.sh` - event `any` when required contexts exist but none are Woodpecker's; aggregate all Actions runs (any red=failure, any in-progress=running); conclusion mapping (cancelled->canceled origin, skipped/neutral pass, all-skipped->unknown); job/step failure naming with precode for Set up job / checkout; stall check at 360m default (FLOW_CI_GHA_TIMEOUT_MIN override); FLOW_CI_RUNS line; header contract.
2. `tests/test_flow_ci_status.py` - order-independence red case, non-woodpecker strict-event red case, conclusion mapping, all-skipped unknown, precode, stalled vs slow; rewrite the old cannot-classify test.
3. `controls/flow-ci-status-gha/control.json` - new negative control spec.
4. `controls/flow-ci-status-gha/run-case.sh` - offline runner with a stub gh.
5. `controls/flow-ci-status-gha/cases/bad-hidden-red/runs.json` - red behind green.
6. `controls/flow-ci-status-gha/cases/bad-hidden-cancel/runs.json` - cancel behind green.
7. `controls/flow-ci-status-gha/cases/bad-required-nonwoodpecker/runs.json` - pr-only runs, required test,lint.
8. `controls/flow-ci-status-gha/cases/good-all-green/runs.json` - all green.
9. `controls/flow-ci-status-gha/cases/good-green-plus-skipped/runs.json` - green plus skipped.
10. `controls/flow-ci-status-gha/anchors/pre-1604-flow-ci-status.sh` - historical anchor at 626a96d9.

Scope: ~10 files plus generated mirrors (codex/skills/**, scripts/SHA256SUMS attributed to source).
Risks: FLOW_CI_PIPELINE/FAILED_STEP shape change on the Actions lane; `any` event widens what counts in repos with only non-Woodpecker required checks; 360m stall threshold may false-positive on self-hosted runners with longer timeouts.
