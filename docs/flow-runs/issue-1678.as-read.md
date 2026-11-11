<!-- flow-run n=1 id=af6e225ea4d941b0ad4bd04408ad74ee -->
## Run 1 - issue #1678 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1678
- Read at:      2026-11-11T18:51:48Z
- updatedAt:    2026-11-11T18:49:28Z   (context only - moves on comments and labels)
- Body digest:  6662068a9e0b7572726443544e6da1b5ad55917cb7d63fe5760c06a7ae15ad59   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2438 of 2438 (cap 16384)

### Body as read
## What

When the coordination admission flag reads `on`, `scripts/flow-finish-gate.sh` (CPP origin/main, around line 371) supervises the gate with `"$CPP_KYLE_LOCK_BIN" run full-suite -- …` and passes **no `--wait`**. Kyle's `kyle-lock run` (kyle `scripts/kyle-lock`, `wait_until_held`) treats an `unavailable` answer like `queued`. It logs once ("full-suite is unavailable: …; waiting"), then sleeps and retries. With no `--wait`, its deadline is `None`, so it never stops.

So any persistent `unavailable` from the coordination authority holds the finish gate forever. After that one log line the gate never starts, never fails and never says why again. Examples: a configured authority that is down, a broken forward hop, or a network partition. Kyle's own rule is that unavailable means "wait, never run". That is correct, but the wait should be bounded, and the gate should end with a named verdict.

Found by tracing the code for cooneycw/kyle#2130, the DEV no-lock ruling; not executed. Kyle fixed the specific DEV case in kyle#2284 (PR #2288, merged `4aa3a2aa`): an environment with no authority now refuses by name, `no_authority_in_env`, exit 3. The general unbounded wait on the CPP side remains. It was first recorded as a Nit Store comment (https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6782227308). It is promoted here under the owner's 2026-11-11 ruling, because it was rated MEDIUM, a silent hang.

## Why it matters

A gate that never starts and never fails cannot be told apart from a slow suite. Finish gates commonly run ~10 minutes, so a silent hang is noticed late, if at all, and it holds a worker's turn.

## Draft acceptance
- [ ] The supervised gate passes a bounded `--wait <seconds>` to `kyle-lock run`. The bound is configurable, with a default comfortably above the normal full-suite queue time.
- [ ] On expiry while still `unavailable`, the gate ends with a named verdict naming the authority's code, e.g. `FLOW_FINISH_GATE: fail (coordination unavailable: <code>)`. Never `ok`, never `skipped`, never silence.
- [ ] `queued` behind a real holder still waits. The bound applies to `unavailable`, or else the doc states why one bound covers both.
- [ ] Red case: a fake `CPP_KYLE_LOCK_BIN` that answers `unavailable` forever makes the gate exit within the bound with that verdict. The same fake answering `held` lets the gate run.

Refs cooneycw/kyle#2130, cooneycw/kyle#2284.


<!-- end of body -->
