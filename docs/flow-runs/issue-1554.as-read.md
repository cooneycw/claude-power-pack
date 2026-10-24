<!-- flow-run n=1 id=fe505ef11f9d4380acfb80637c9dd02c -->
## Run 1 - issue #1554 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1554
- Read at:      2026-10-24T22:01:11Z
- updatedAt:    2026-10-24T21:20:42Z   (context only - moves on comments and labels)
- Body digest:  55d6e753914683b1222c49d13adf226dca11f0956875b233d412b5aa40547936   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2906 of 2906 (cap 16384)

### Body as read
## Outcome

Complete the live-consumption residual of #1367 by consuming the real retained D3 flow-check export produced by cooneycw/skillc#556 (EXPORT-1). Owner authorized necessary CPP work as part of wave skillc-complete on 2026-10-24. This is a bounded child, not a reopening of closed #1371 or skillc #288.

## Dependencies

Producer artifact/contract from cooneycw/skillc#556. Design may proceed while the producer is built; merge only when the actual exported artifact is available and its trust boundary is reviewed.

## Acceptance

- Consume the actual privacy-safe D3 producer export through existing behavioral-eval / per-skill / freshness mechanisms. A hand-authored surrogate or fixture-only test does not complete this issue.
- Reproduce a useful reading for flow-check at CPP 652c0118: two observed attempts; report-honest, no-commit and gate-definition-unmodified SATISFIED in the source records; installation-ready UNKNOWN; overall verified-result INCONCLUSIVE. Preserve the distinction from the declared primary endpoint PASS and retain #534 correction lineage.
- Bind the evidence to exact skill/profile/helper/task/grader/client identities, distinguishing current, stale, unknown and untested coverage. Do not mint positive per-skill attribution from a bare attempt result or claim retrospective fixture finalization was recorded when it was not.
- State producer-owned full bundle validation versus CPP's restated subset. The 2026-10-24 probe found that skillc rejects a removed manifest while the existing CPP subset does not independently diagnose it. Demonstrate that the delivered handoff cannot present a missing required record, fabricated positive or altered relevant skill/helper as current positive evidence. Extend only the relevant consumer boundary if needed, with conformance controls.
- Keep ADR 0011 and CI enrollment ADVISORY. A real export is not a discrimination or improvement comparison; no universal PASS threshold or paid run is introduced.
- Commit the reusable reader/artifact integration and concise documentation sufficient for a reviewer to repeat the consumer reading without the private host store. Retained source bytes remain unchanged; private transcripts/credentials/host identifiers are not published.
- Run applicable CPP checks, committed negative controls, full make verify and exact-head required CI. Any new regression test is demonstrated red before its fix.

## Scope and limits

Prefer existing scripts/check-behavioral-eval.py and the existing coverage/enrollment interfaces. No skillc runtime dependency in CPP CI. No generic provenance platform, new study, deployment or host configuration changes. Preserve #1367's original acceptance and close it only if its full residual acceptance is actually demonstrated; otherwise this child records exactly what it delivered.

Related: #1369, #1370, #1371, #1084; skillc #249/#262/#529/#534/#556.


<!-- end of body -->
