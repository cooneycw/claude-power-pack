<!-- flow-run n=1 id=a532b3cb828140fc97e05b247347d0e2 -->
## Run 1 - issue #1604 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1604
- Read at:      2026-10-30T10:20:33Z
- updatedAt:    2026-10-30T10:09:48Z   (context only - moves on comments and labels)
- Body digest:  18210f1ec4f6b07113fe7aa4123db75340d1bd3d84cba1517936882a80eb162e   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 5253 of 5253 (cap 16384)

### Body as read
On 2026-10-30 the owner ruled, on cooneycw/kyle#1475, that the public kyle coding-only candidate will use **GitHub Actions** for contributor CI. Private kyle and CPP stay on self-hosted Woodpecker. CPP's flow helpers drive CI for every repository, so they have to handle a repository whose CI is GitHub Actions only. Today, at `a6643411`, they don't do that safely. `.github/` here holds only `ISSUE_TEMPLATE`, so the GitHub Actions lanes have never run against a real workflow.

## Gaps (read-only investigation; probes used a fake `gh`)

1. **The merge recipe waits out its full window on an Actions-only repo.** `scripts/flow-ci-status.sh:360-370` derives the event only from `ci/woodpecker/{pr,push}/*` required contexts. With GitHub Actions check names such as `test` and `lint`, it falls back to `push`. `/flow:merge` and `/flow:auto` call it with `--strict-event --wait 1800` (`flow/merge.md:134`, `flow/auto.md:1660`). Probe: required `test,lint` with only `pull_request` runs gave `FLOW_CI_STATUS: not-found` under `--strict-event`, so every PR would wait the full 30 minutes.
2. **One run decides for the whole commit.** `gha_pick` (`:746-749`) takes `.[0]`. On one SHA, `[success, cancelled]` reports `success` and `[cancelled, success]` reports `failure`, so the answer depends on list order. A green lint workflow can hide a red test workflow.
3. **Status mapping is too coarse.** Any completed run that is not `success` counts as `failure`, including `cancelled`, `skipped`, `neutral` and `timed_out`. Cancellations come out as `FLOW_CI_FAILURE_ORIGIN: unknown`. Failures are reported by job name, never by step, so a failed `actions/checkout` is never classified `precode`. There is no stall check (#1552) on this lane.
4. **The lane has three tests and no negative control.** `tests/test_flow_ci_status.py` covers it at roughly `:1005`, `:1020` and `:1300`. Nothing covers multiple runs on one SHA, the non-success conclusions, or event derivation. All three `controls/flow-ci-status*` controls are Woodpecker-only.
5. **`scripts/flow-pr-watch.sh:141` hardcodes `CONTEXT="ci/woodpecker/pr/woodpecker"`.** Failing-test extraction only goes through `woodpecker-cli` (`:320-340`).
6. **`gh-pr-merge.sh` mostly works.** `statusCheckRollup` covers both commit statuses and check runs. But required states are keyed by name alone (`:768`), so two workflows with a job of the same name collide and the last one wins.
7. **Counter-model enrolment (#1452) runs only as CPP's own Woodpecker step** (`.woodpecker.yml:770-805`). The gate itself, `flow-finish-gate.sh --enrolment-only`, is provider-neutral, but there is no Actions job and no template for it. On a public repo, PRs from forks carry no receipts, so the step would fail every outside contributor. That policy is undecided.
8. **The `/cicd:pipeline` Actions output is not hardened** (`lib/cicd/pipeline.py:110-253`, `templates/workflows/ci-*.yml`):
   - actions are pinned by tag, and `dtolnay/rust-toolchain@stable` is a moving branch reference
   - no top-level `permissions:` and no `persist-credentials: false`
   - no `concurrency` and no `timeout-minutes`
   - `pip install uv` is unpinned
   - no `environment:` on the deploy job
   - no gitleaks job, which the Woodpecker path has
9. **`branch-protection.sh` compares contexts by name only** (`:95`, `:117`). It cannot require that a check comes from the GitHub Actions app, so a commit status with the same name could satisfy a check-run requirement.

## Acceptance
- [ ] `flow-ci-status.sh` derives the event correctly when no Woodpecker context is required. **Red case:** required `test,lint` with only `pull_request` runs must not give `not-found` under `--strict-event`.
- [ ] The Actions lane combines **all** runs on the chosen event: any red is failure, any in-progress is running. **Red case:** `[success, failure]` and `[failure, success]` both give `failure`.
- [ ] `cancelled` maps to the `canceled` origin. `skipped` and `neutral` each get an explicit decision. Job steps are read (`gh run view --json jobs`), so a failed checkout reads `precode`.
- [ ] Stall check for Actions runs older than their `timeout-minutes` (#1552 parity).
- [ ] Negative control `controls/flow-ci-status-gha` covering the cases above.
- [ ] `flow-pr-watch.sh` derives its default context from branch protection and extracts failing tests from Actions logs (`gh run view --log-failed`).
- [ ] `gh-pr-merge.sh` keys required checks by app plus name.
- [ ] Counter-model enrolment as a GitHub Actions job template (`fetch-depth: 0`, `--branch "${{ github.head_ref }}"`), plus a written decision on fork PRs.
- [ ] The `/cicd:pipeline` Actions output is hardened (all items listed in gap 8, and no `pull_request_target`), with tests asserting each property.
- [ ] `branch-protection.sh` records and checks the `app_id` of each required check.
- [ ] Docs (`flow/auto.md` Step 8, `flow/merge.md`, `flow-wave-lexicon.sh:822`'s example) describe both providers.

## Context
- Consumer: cooneycw/kyle#1475. Its next slice writes the public candidate's GitHub Actions workflow, and it needs at least the first three acceptance items before `/flow:merge` can be trusted on that repository.
- Found during: the `/flow:auto 1475` run on 2026-10-30.


<!-- end of body -->
