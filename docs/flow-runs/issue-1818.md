# Issue 1818: preserve historical receipt contracts

Approved scope: the Kyle master ruling relayed in managed message 26577.
Origin: #1515 changed schema dispatch without retaining the earlier
schema-1 extra-pass contract. Producer revisions of the nine Kyle records
are unknown; historical shape acceptance does not prove quota authorization.
No consumer receipt will change. Kyle's pin stays unchanged pending a
separately approved release. The unrelated scanner CLI finding is excluded.

The implementation dispatches validation by the declared integer version.
Schema 1 retains the reason/count rules at `b6117e7b`; schema 2 and newer
retain current escalation checks. The current writer and enrolment decisions
remain unchanged. Synthetic committed inputs cover both acceptance and
refusal; the original Kyle corpus is measured separately without copying or
rewriting its records. Full finish gate and outside-model review remain
required before merge; no merge or tag push is authorized here.

## Lanes and readers

| Lane or reader | Plan | Evidence or boundary |
|---|---|---|
| Checkout | will test | Standalone isolated CPP checkout; temporary Git checkout for actual enrolment. A linked-worktree layout is not covered |
| Harness | not applicable | No command, installer, or generated skill changes |
| Driver | not applicable | No delegated-driver or flow-driver changes |
| Coordination | not applicable | Shape validation does not contact Kyle; no live fleet claims |
| CI provider | not applicable | No provider-specific behavior changes |
| Project state | will test | Mixed receipt corpus and invalid current record through the real CLI; existing enrolment tests cover absence |
| Toolchain version | will test | CPP-pinned Python 3.11.14 and uv; no version matrix |
| Clone shape | not applicable | Version dispatch does not consult clone history; existing enrolment history logic is unchanged |
| Run location | will test | CLI invoked with explicit temporary corpus path, separate from CPP root |
| Gate target | will test | Original Kyle corpus through CPP's actual validator; no consumer suite or image claim |
| Wave role state | not applicable | No wave registry changes |
| Reader: corpus CLI | tested against real output | Mixed schema input through the real `validate --dir` command, then remove a current escalation and require rejection |
| Reader: current writer | tested against real output | `build` emits scalar extra-pass schema 2, and the real validator consumes it; existing runtime writer tests retain richer-schema coverage |
| Reader: finish-gate enrolment | reader unchanged | Current quota checks stay strict; real Git fixture with a valid legacy shape above three still returns unknown without a ruling |
| Reader: uniformity and attribution | reader unchanged | They read model/evidence fields, not the changed shape verdict; existing focused tests will be run |

Reader search: `validate`, `evaluate_enrolment`, and `counter-model-receipt.py`
references in scripts, tests, Makefile, CI and consumer adoption instructions.
The search finds the known corpus CLI and finish-gate helper, so it can see
real readers. Known external reader: Kyle's CPP adoption corpus check.

## Validation record

Before the fix, the new 41-case module on v11.1.0 produced 6 failures and
35 passes. Four legacy extra-pass acceptances, mixed-corpus CLI acceptance,
and rejection of a boolean schema declaration failed at their intended
assertions. The committed negative inputs include missing/blank reasons,
invalid counts, unknown versions, and current-schema missing, malformed or
over-cap escalation. This is a fixture population, not the original corpus.

After the fix, `make test` restricted to the new schema module, the existing
counter-model review module, and the real enrolment module passed 482 cases
with one worker in 31.11 seconds. `make lint` passed. The original Kyle
corpus, separately measured through the candidate CLI, reported
`COUNTER_MODEL_EXAMINED: 352` and `COUNTER_MODEL_RECEIPTS: ok`, exit 0.
Kyle's worktree remained clean. No original receipt was copied or rewritten.
CPP's own unchanged corpus separately validated 429 receipts, exit 0.
The lint, binary-guard, negative-fixture, Unicode-dash, and relative-link
Makefile checks passed. Their stated static-analysis limits still apply.

Missed because: no test covered it.
The old check tested the new writer and schema-mismatch refusal, assuming no
consumer had retained the earlier schema-1 extra-pass records.

Pending: full finish gate and outside-model review. No completion, merge,
or release claim is made here.

## Outside-model review follow-up

The first Claude review approved `8cf481d6` with an accepted, documented
shape-only unbounded-count risk, one low finding and one diagnostic nit:
[review](https://github.com/cooneycw/claude-power-pack/pull/1819#pullrequestreview-5904469133).
No historical-maximum ceiling is added: that would change the actual old
contract. A synthetic 500-pass case explicitly retains this shape-only
boundary; it establishes neither provenance nor quota permission.

The added schema-1 escalation fixture rejects the permissive mutation that
the first review found undetected. Running only that case against the
mutated validator produced its intended assertion failure; the candidate
passes it. A real Git test now feeds the same record to both readers:
shape validation refuses schema-1 escalation, while the unchanged enrolment
policy accepts a well-formed recorded ruling independently of full shape.
The rationale and limits are documented at the implementation and maintained
contract. The gate does not authenticate the named authority.

The stale schema-mismatch diagnostic is corrected. Its regression test failed
on `8cf481d6` before the text fix (1 failure, 44 passes), and all 45 schema
cases pass after it. Lint also passes. The delta returns to master for recheck
before the authorized full finish gate. Actual runtime evidence is still
required for the derived review receipt; a relay is not substituted for it.
