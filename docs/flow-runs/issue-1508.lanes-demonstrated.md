# Lanes demonstrated - issue #1508

The plan for this issue was approved on 2026-11-11, before plans carried a lanes table, so this file states all six lanes itself: what was exercised, and what was not.

| Lane | What was demonstrated |
|---|---|
| Checkout | `tests/test_flow_ci_status.py` and the full suite (`make test`, 11,420 passed, 2 skipped) in a linked worktree on the head re-synced onto main. The main checkout was not separately exercised |
| Harness | `make command-docs-budget-check` with `auto.md` at 10,409 of 10,410 words; `tests/test_codex_skill_sync.py` in the full suite. A live Codex run was not exercised |
| Driver | Not applicable: no driver-specific code |
| Coordination | Not applicable: no wave, mailbox or registry code |
| CI provider | The classifier was written from a MEASURED sample: Woodpecker 3.19.0, repository 1, pipeline 3674, a deliberate bad-image run on a throwaway branch, which reported the step as `type=commands state=failure exit_code=0` with the Docker daemon's message in `error`. Replayed through a stubbed API: main's script reports `FLOW_CI_FAILURE_ORIGIN: code` for that sample and this one reports `precode` with `FLOW_CI_PRECODE_FAILURE: validate`; exit code 0 both times. `controls/flow-ci-status` verified with `check-negative-controls.py --control`: two bad image-pull cases detected, four neighbouring good cases stay `code` (a Docker-socket error with exit 126, a bare exit 126, another daemon error with exit 0, the pull text after exit 1). Only Docker's wording on that server version was measured; a release that rewords it falls back to `code`. The Actions lane has no equivalent and is unchanged |
| Project state | Not applicable: no issue, label or board writes beyond the pull request |
