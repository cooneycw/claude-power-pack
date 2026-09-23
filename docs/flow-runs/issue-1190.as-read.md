# Issue #1190 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1190
- Read at:      2026-09-23T11:43:57Z
- updatedAt:    2026-09-21T20:57:39Z   (context only - moves on comments and labels)
- Body digest:  af3e2e534a8710275994d34f7cb8925a7198b3a6ee16e5c465e072e0f2900f1b   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4815 of 4815 (cap 16384)

## Body as read
Three helpers emit lines shaped like the `FLOW_*:` contract — a stable key, a colon, a value — which is what makes them safe to read from a script rather than by eye. In each case the value a consumer receives is **wrong rather than absent**, so the consumer fails by returning a plausible answer instead of erroring. All three were hit in one wave on cooneycw/kyle, 2026-09-21.

## 1. `flow-pr-watch.sh` reports a negative control's echoed failures as the pipeline's own — and that list feeds the flake baseline

Measured on pipeline 2512 (PR #1310). The watcher returned:

```
FLOW_PR_WATCH: red
FLOW_PR_WATCH_FAILED=tests/test_xdist_isolation.py::test_worker_scoped_paths_carry_this_worker_id
                     tests/test_xdist_isolation.py::test_the_collapse_override_is_not_set_in_this_run
                     tests/test_xdist_isolation.py::test_no_two_workers_named_the_same_database_or_tmux_socket
                     journal/tests/test_views.py::TestNoSecretsInSession::test_unlock
```

The pipeline's actual result was **one** failure. From the same step log:

```
line 450    ── BAD case: worker scoping collapsed, same invocation ──
line 468    FAILED tests/test_xdist_isolation.py::test_the_collapse_override_is_not_set_in_this_run
line 479    XDIST_ISOLATION: ok
line 13606  = 1 failed, 6432 passed, 10 skipped =
```

Three of the four sit inside a `── BAD case ──` block, echoed by `scripts/check-xdist-isolation.sh`'s own `tail -n 25 "$BAD_LOG"`. That script runs a two-sided control — a GOOD case that must pass and a BAD case that must fail — and its verdict four lines later is `XDIST_ISOLATION: ok`.

**Why it is not cosmetic.** `--baseline` matches declared-flaky ids against `FLOW_PR_WATCH_FAILED`. The natural response to seeing `test_the_collapse_override_is_not_set_in_this_run` red on a PR that did not touch it is to add it to the baseline — and once there, a *genuine* failure of that test, the assertion that says "every isolation assertion in this run is being made about an isolation that is not there", is silently excused. **A misattribution that feeds an excuse list is a path to a hidden real defect.**

It happened twice in one session, and both times a reader (myself, then a worker independently) anchored on the control's echo and passed over the real failure that was on the same screen. The more thoroughly a repo commits its red cases — which is exactly what ADR 0008 asks for — the more of this there is.

**Suggested disposition:** prefer pytest's own summary line and `short test summary info` as the authoritative failure set rather than every `FAILED ` occurrence; or bound the scrape to the region after the last summary marker. At minimum report the step's exit state and summary counts alongside the scraped list, so four named failures and `1 failed` visibly disagree.

## 2. `flow-wave-registry.sh` never emits its documented `FLOW_WAVE: error` verdict on a usage failure

Reproduced: `flow-wave-registry.sh register` with no role prints `register requires a role` and `FLOW_WAVE_EXIT=2` with **zero** `FLOW_WAVE:` lines, on four distinct usage paths. The published contract lists an `error` verdict.

A contract-conformant caller grepping the documented marker sees **silence on a refusal**. The worker who found it hit it while re-registering a lane: its grep included the documented marker, the tool reported "completed with no output", and the registration had actually been refused.

## 3. `flow-finish-gate.sh` concatenates the counter-model receipt id and the branch name

```
FLOW_FINISH_GATE_COUNTER_MODEL: receipt: 2026-09-21T192921Z-issue-1307.jsonissue-1307-verify-kyle-s-django-deploy-checks-and-their-10-fa
```

Filename `2026-09-21T192921Z-issue-1307.json` and branch `issue-1307-verify-…` printed adjacent with no separator. Anything consuming `receipt: <id>` receives an id matching no file on disk — present, non-empty, plausible. Two of the three waves running on this host treat that receipt as the evidence a review happened (*"MERGE: AUTHORIZED is void without it"*), so **a corrupt-but-present id satisfies a presence check and defeats a retrieval.**

## The shared property

None of these three fails loudly. Each returns a value that is the right *shape* and the wrong *content*, to a caller that has no way to tell. That is the same class the `FLOW_*:` contract exists to prevent, arriving in the lines that implement it.

## Provenance

Nit-store records: #864 comments [5765261081](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5765261081), [5764373342](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5764373342), [5766361894](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5766361894). Aggregated at the owner's direction.

