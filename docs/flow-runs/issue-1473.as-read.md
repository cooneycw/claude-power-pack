<!-- flow-run n=1 id=a6e05342fed143889cfe7f7a86eb927e -->
## Run 1 - issue #1473 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1473
- Read at:      2026-10-17T11:58:03Z
- updatedAt:    2026-10-17T11:54:29Z   (context only - moves on comments and labels)
- Body digest:  546d45285a2a597dd93000d9b4126a03fa1c66c1ab327b549f6438070ba32048   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3558 of 3558 (cap 16384)

### Body as read
## Problem

`tests/test_flow_plan_compliance.py:777-808`, `test_a_failed_intent_to_add_is_unknown_not_agreement`, tries to force `git add -N` to fail by chmodding `.git/index` to 0444. Git can replace that file through its lock-file update while `.git` remains writable, so the probe succeeds and the test skips. This leaves the shipped plan-comparison block's failed-intent-to-add handling untested on an ordinary development host.

The intended contract is that an unsuccessful intent-to-add operation reports `PLAN_COMPLIANCE: unknown`, never `agreement`. This finding is a coverage defect, not evidence of an observed production false agreement.

## Reproduction and evidence

Evaluated revision: `020349564f87d1bd2b86800f9c8e2814fd239b79` (v9.0.0).

```bash
PYTEST_ADDOPTS='-rs tests/test_flow_plan_compliance.py::test_a_failed_intent_to_add_is_unknown_not_agreement' PYTEST_WORKERS=2 make test
```

The assessment's full run and subsequent focused run skipped this case with:

```text
this environment can write a read-only index; the state is unreachable
```

A separate disposable-repository probe running as ordinary UID 1000 measured:

| Fixture condition | git add -N result |
| --- | --- |
| Index mode 0444; writable .git directory | exit 0 |
| Fixture-owned .git/index.lock already exists | exit 128; lock-exists diagnostic |

The comment attributing the skip to root or a filesystem that does not enforce permissions therefore does not describe the observed cause.

Promoted from the [Nit Store finding](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6233531299), discovered during the October 17 Downloads assessment follow-up. Local evidence: `~/Downloads/claude-power-pack-assessment-evidence-2026-10-17/index-skip-probe.json` and `skip-details.log`. This is separate from #1472's receipt-test environment leak.

## Outcome and acceptance

The test must reliably exercise the real failed-intent-to-add branch, without depending on index-file permissions or elevated-user assumptions.

- [ ] Reproduce and retain the original skip before changing the fixture.
- [ ] Construct a deterministic, fixture-owned Git failure and assert its precondition before invoking the real plan-comparison block.
- [ ] Prove the block reaches the intended intent-to-add failure branch, reports UNKNOWN with its distinguishing diagnostic, and does not report agreement. An earlier failure or unrelated UNKNOWN branch does not satisfy this case.
- [ ] Demonstrate that mutating the relevant failure handling to report agreement makes the repaired test fail; retain the red result. The healthy fixture must pass on the correct implementation without skipping.
- [ ] Keep the failure condition inside the disposable repository, clean it up, and correct the misleading fixture explanation.
- [ ] Run the focused checks and `make verify`; report unrelated failures separately, including #1472 if still present.

## Scope and possible approach

A fixture-owned `.git/index.lock` is one candidate: it produced the required refusal in the independent probe. Verify that it survives until the specific operation under test and does not prevent earlier setup. An equivalent deterministic mechanism is acceptable.

Keep this bounded to the fixture and its evidence unless exercising the real branch discovers a production defect. Do not weaken the UNKNOWN contract, remove the test, or replace the production path with a reimplementation. This repair does not itself establish CPP behavioral benefit and is not a prerequisite for the model study.

