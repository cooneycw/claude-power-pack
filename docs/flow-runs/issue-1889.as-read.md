<!-- flow-run n=1 id=b9ec164e15eb4b14826b3f2a0d09dc16 -->
## Run 1 - issue #1889 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1889
- Read at:      2026-11-25T19:01:23Z
- updatedAt:    2026-11-25T16:45:43Z   (context only - moves on comments and labels)
- Body digest:  2b4d3f124af50f0eda6d73bb385e010900bbf39fc0627553e7054351bc73f91c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2184 of 2184 (cap 16384)

### Body as read


Parked: scaffold pending the ADR 0014 / plan merge; scope may change
Tier: 3

Parent: #1876

Planning scope: this Codex group authors CPP code and issues; AGY is test-only. One AGY PR in flight, PR CI only, Kyle series-27 CI priority. Owner accepts and merges ADR0014 before code merges; Kyle stays on CPP v13.0.0.

Owner rulings remain open: measured packaging Option A/B, initial skill scope, and Qwen/OpenCode/other managed-harness coverage. Do not treat proposals as rulings.

Outcome: one update refreshes all existing managed installations in the agreed
scope from one CPP revision and reports verified outcomes independently.

Acceptance:
- Implement the 1.1 authoritative contract through the shared driver and
  measured AGY packaging adapter. No bespoke AGY-only updater procedure.
- Starting from a current checkout, refresh stale managed Codex and AGY
  installations together; preserve a neighboring user skill byte-for-byte.
- Make one destination genuinely unwritable to the executing identity; prove
  that precondition, refresh the other destination and identify the failure
  in summary and exit policy. chmod under root alone is insufficient evidence.
- Verify installed bytes/membership against a fresh build; prune only owned
  orphans. Reinstall and concurrency follow measured native guarantees or
  an explicit advisory lock. No source-checkout coupling in AGY installs.
- Include HOST-SURFACE declarations and installation fidelity controls.
  If extra harnesses are included by owner ruling, their adapters/acceptance
  appear here or in explicit linked delivery tasks before completion.

Dependencies: 1.2; 1.1 specification and owner harness-scope ruling.
Controls: controls/antigravity-skill-install-fidelity plus shared-driver controls
with stale bytes, missing expected member, foreign neighbor, unwritable target,
and unexaminable target. A control mutation that always reports current must fail.
Readers/lanes: driver feeds actual adapters; status/drift consume actual reports
and installs. Test multiple invoking harness paths when available; untested live
invocation paths remain named gaps, not covered by mocks alone.

Dependency links: #1888.


<!-- end of body -->
