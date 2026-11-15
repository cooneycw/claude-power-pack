# Lanes demonstrated - issue #1849

<!-- lanes-demonstrated run=8dbd4634fefd417c9a8d8f6be523ab4e plan=51c7cc320bb8b7223c7d625186d0041d3fe092e644d49bf182dadd5c264db036 -->

| Lane | Result | Evidence |
|---|---|---|
| Driver | passed | `/flow:auto` and the delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`): `scripts/check-driver-parity.py` reports ok, 24 items, 72 pairs, on the rewritten flow/auto.md; tests/test_driver_parity.py run-verb cases (expansion ok; dropping finish stays unknown, red on an over-expanding mutant; old gate reads the wrappers as unknown) |
| Checkout | passed | main checkout: tests/test_flow_plan_record_wrappers.py fixtures are `git init` main checkouts; linked worktree: this run's `python3 scripts/flow-plan-record.py finish 1849` from the issue worktree printed ISSUE_DRIFT, PLAN_COMPLIANCE, FLOW_PLAN_RECORD and FLOW_PLAN_FINISH |
| Harness | passed | Claude install: the test suite runs the source helper (the installed `~/.claude/scripts` link to the main checkout is not exercised before merge); Codex install: `make codex-skills` built the flow-auto mirror from the changed flow/auto.md and the parity gate checked its bundled bindings (generated-flow-auto) |
| Project state | passed | a repository that has adopted a feature's file: test_a_project_with_lanes_refuses_a_plan_that_answers_none (lane file present), test_a_plan_over_another_sessions_committed_run_appends_run_two (a committed run 1 from another session kept byte for byte); one that has not: the other wrapper cases (no lane file, no record) |
| Run location | passed | invoked from the CPP root: the dogfood `finish` above ran from the worktree root; from another directory not covered |
