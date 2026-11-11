<!-- flow-run n=1 id=b232b9863e2c48d181dab31a3e956db0 -->
## Run 1 - issue #1668 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1668
- Read at:      2026-11-11T15:07:05Z
- updatedAt:    2026-11-10T23:40:06Z   (context only - moves on comments and labels)
- Body digest:  6009d97216e8b61175c9c3396802ebea37889701ef4a3d61f34aea6407109a87   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1414 of 1414 (cap 16384)

### Body as read
## What

Add a short section to `docs/agents/flow-wave-completion.md` (and its Codex copy `codex/skills/flow-wave/docs/agents/flow-wave-completion.md`) describing how a Kyle-hosted wave can use Kyle's CPP role-receipt adapter, through the existing external executable contract.

Kyle shipped the adapter in cooneycw/kyle#2255 (Closes cooneycw/kyle#2220). A draft of the CPP text is committed on Kyle main:
https://github.com/cooneycw/kyle/blob/29a359dc/docs/measurements/issue-2220-cpp-adapter/cpp-note-draft.md
The companion contract is Kyle's `docs/cpp-receipt-adapter.md`.

## Scope

- Documentation only. No change to `scripts/flow-wave-completion.py`, its controls or its receipt validation. CPP keeps validating identity, result, timestamps, assignment state, deadlines and the post-publication GET exactly as now.
- The section must not claim a deployed adapter. Local Kyle tests are not deployed permission or durability acceptance. An operator still has to verify cross-container coordinator readback before a deployed namespace is relied on.
- The draft's key points: per-role registration before launch; unregistered or wrong-namespace reads give UNKNOWN; null means a registered healthy binding with no receipt; a claimed outcome is stored separately from a measured process exit; no adapter result extends a deadline.

## Priority

Low. Parked until CPP work resumes; filed so the draft is not lost.


<!-- end of body -->
