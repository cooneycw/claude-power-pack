# Flow run record - issue #1508

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=2f628282cfa2408e85f767255833e380 -->
## Run 1

- Run-id:            2f628282cfa2408e85f767255833e380
- Run-start:         15521b1e19359cd7d72c8f24e5628b397fa676f5
- Issue:             #1508
- Base SHA:          15521b1e19359cd7d72c8f24e5628b397fa676f5
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the repository owner (cooneycw), in this session: "approved on a throwaway cpp branch"
- Recorded at:       2026-11-11T22:30:00Z

### Section B evidence
- Commits on `scripts/flow-ci-status.sh` since filing: a107a3f4, a6643411, 46d99956, 09e9e756, 99204d59, 3c3062ee. None touch image-pull classification.
- Merged PRs inspected: #1512, #1509, #1583, #1606, #1653, #1687. None supersede.
- Related issues: #1486, #1411, #1462, #1342 (all closed, other halves of the classifier). No duplicate.
- History re-scan 2026-11-11: repos 1/17/20, pipelines created since 2026-10-20, 1893 listed, 390 failed or killed read in detail, 0 image-pull failures; positive control recovered CPP pipeline 3356 step `counter-model-enrolment` exit 1.

### Section C - the approved plan
Step 0 (approved venue): a deliberate bad-image experiment on a throwaway branch of cooneycw/claude-power-pack - a manual-only workflow with deliberately bad images, triggered once through the Woodpecker API, measured, then the branch deleted. No PR, main untouched.

1. `scripts/flow-ci-status.sh` - a narrow pull-failure test keyed on the measured shape; counted as precode in failure_origin() and printed as FLOW_CI_PRECODE_FAILURE; cancellation keeps precedence.
2. `controls/flow-ci-status/run-case.sh` - let a case supply the failed step's error text.
3. `controls/flow-ci-status/control.json` - register the new cases and state the new limits.
4. `controls/flow-ci-status/cases/bad-image-pull-failure/exit_code` - the measured sample's exit code.
5. `controls/flow-ci-status/cases/bad-image-pull-failure/error` - the measured sample's error text.
6. `controls/flow-ci-status/cases/bad-image-pull-failure/step_name` - a non-stager step name.
7. `controls/flow-ci-status/cases/good-docker-socket-error-126/exit_code` - Docker-socket error must stay code.
8. `controls/flow-ci-status/cases/good-docker-socket-error-126/error` - the measured socket error text.
9. `controls/flow-ci-status/cases/good-docker-socket-error-126/step_name` - a non-stager step name.
10. `controls/flow-ci-status/cases/good-bare-exit-126/exit_code` - exit 126 with no error must stay code.
11. `controls/flow-ci-status/cases/good-bare-exit-126/step_name` - a non-stager step name.
12. `tests/test_flow_ci_status.py` - regression tests for the same distinctions, red on the pre-fix script.
13. `.claude/commands/flow/auto.md` - update the one-line description of what counts as pre-code.
14. `docs/scripts/flow-ci-status.md` - record the measured sample and the rule.

Scope: about 5 logical files, roughly 150 lines, mostly fixtures and tests.

Risks: the sample may surface only at workflow level, needing a field the extractor does not read today; over-broad matching on exit 126 would excuse the Docker-socket error; a forced failure may differ from a natural registry outage, so the rule covers only measured variants.
