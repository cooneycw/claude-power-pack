# Flow run record - issue #1253

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1253
- Base SHA:          39c8475a937846ccfb29d7608037c841d0fab2a8
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          cooneycw (session user, interactive "approved")
- Recorded at:       2026-09-25T16:01:32Z

## Section B evidence
- commits: none touching tests/test_flow_wave_mailbox.py or scripts/flow-wave-mailbox.sh since 2026-09-25T14:17:29Z
- PRs: none merged since filing; no open mailbox PR
- dup/super: none (search returned #1253 itself and Nit Store #864)
- Reproduced at 39c8475: FLOW_WAVE_SESSION_PIDS='' fails all 7 with no-wake

## Section C - the approved plan
1. `tests/test_flow_wave_mailbox.py` - add opt-in `_session_lineage()` naming the pytest worker pid; `_live_watcher()`/`_run()` gain optional `env_extra`; the seven tests pass lineage to watcher and reader; one control test (live watcher, lineage naming a non-ancestor sibling) reads no-wake; no suite-wide default.

Scope: 1 file, ~40-60 lines. Risks: xdist worker pid is the watcher's parent (correct); pinned pid bypasses the socket probe for these seven only (socket/no-sockdir paths stay covered by TestWakeability).
