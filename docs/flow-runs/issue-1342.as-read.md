<!-- flow-run n=1 id=ab9a48bcb8c941dba9227e10998d21cf -->
## Run 1 - issue #1342 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1342
- Read at:      2026-09-28T21:41:31Z
- updatedAt:    2026-09-28T21:40:13Z   (context only - moves on comments and labels)
- Body digest:  3ab90b094df621fc142803c465221f13915722bc1e3c888ec9582cad0da9e865   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 953 of 953 (cap 16384)

### Body as read
Child of #1268 ("the rest", FIX candidates), split so three workers can run in parallel without sharing a branch or a plan record. Items as reproduced on c6b02fa by the run45 wave (see the #1268 wave-close comment); re-reproduce each on current main before planning.

**Files:** `scripts/toolchain-provenance.sh`, `scripts/flow-ci-status.sh` (plus their tests and `docs/scripts.md`).

1. **`scripts/toolchain-provenance.sh` `age_clause`** reports only the fetched ref's age. A `behind` verdict should also state HEAD's own age.
2. **`scripts/flow-ci-status.sh` has no pre-code failure marker:** a CI clone-step failure cannot be told apart from a code failure. Proposal: emit `FLOW_CI_PRECODE_FAILURE: <step>` beside `FLOW_CI_FAILED_STEP`, with no exit-code change.

Both are instruments whose output is read as evidence, so each needs a committed red case (the input that makes it report the other verdict) that fails on the pre-fix code. Refs #1268.

