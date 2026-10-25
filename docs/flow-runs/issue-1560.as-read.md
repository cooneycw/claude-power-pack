<!-- flow-run n=1 id=5e2f1600bd854bb4994f2077c0f9f8f1 -->
## Run 1 - issue #1560 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1560
- Read at:      2026-10-25T07:38:05Z
- updatedAt:    2026-10-25T07:32:18Z   (context only - moves on comments and labels)
- Body digest:  286b4773d6830013df3387aaebfc54b5ae5b8d1ee37a327eece6cd08a154897b   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3112 of 3112 (cap 16384)

### Body as read
Promotes the existing finding: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6389971061
Related: #871. This concerns current CPP's generated Codex compatibility surface, not revival of the retired codex-power-pack native-wave programme (#1072 and its consolidation ledger).

## Problem

At CPP dd988219e056ddf23fb7ef5ba55e93979c07b61a, the shared flow:wave and flow:register guidance interprets shell watch=NO-WAKE as nobody being able to wake the worker. The ancestry check is Claude-specific. During skillc-complete, native Codex thread messaging and durable mailbox acknowledgements worked while this shell diagnostic still said NO-WAKE.

The observation establishes a transport-scoping gap. It does not establish that the shell watcher can wake Codex, that every native send wakes an idle thread, or that this wording caused a timeout.

## Bounded fix

- [ ] Reproduce the mismatch against the pinned current CPP sources and record the actual native tool capabilities/version available to the compatibility session. Separate shell watcher state, native transport availability and acknowledged end-to-end delivery.
- [ ] Correct authoritative flow/register.md and flow/wave.md guidance, then regenerate their Codex surfaces using the normal generator. A native session must not be told that creating another Claude-ancestry watcher proves a working native wake route.
- [ ] Give native sessions an explicit bounded route: persist the assignment in the durable mailbox; notify through the available native transport; require the intended worker to read and acknowledge the matching assignment; escalate or report unavailable when the route cannot be confirmed. No silent success from send acceptance, process existence or an acknowledgement made by the supervisor.
- [ ] Preserve Claude ancestry and orphan/detached watcher guards. Do not relabel a shell watcher armed because a separate native route exists. Missing native tools must be reported as unavailable with an actionable fallback, not an indefinite polling loop.
- [ ] If code/diagnostic verdicts change, commit positive and negative controls covering a genuine shell watcher, detached watcher, native-route availability without acknowledgement, matching worker acknowledgement and stale/wrong-worker acknowledgement. Demonstrate relevant regressions red before the fix. If the change stays documentation-only, verify generated parity and retain a concrete walkthrough of working and unavailable routes; do not claim automated runtime enforcement.
- [ ] Run appropriate CPP checks and independent review. Report exactly what was measured with native tools versus simulated. Supply old/fixed pin and the reproducible scenario to the skillc coordination fixture.

## Acceptance boundary

Close on truthful transport-specific guidance/diagnostics and demonstrated bounded handoff behavior within the chosen scope. Reduced timeout rates require skillc's separate frozen live comparison. Do not introduce a new native-wave engine, weaken liveness controls, install host helpers, or claim task-success uplift to close this ticket.


<!-- end of body -->
