<!-- flow-run n=1 id=72a3ec8df50344c1becf88bb16facf70 -->
## Run 1 - issue #1987 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1987
- Read at:      2026-11-28T12:10:32Z
- updatedAt:    2026-11-28T12:09:04Z   (context only - moves on comments and labels)
- Body digest:  55faa650a59fd55f8876848bf7f762f9d7498168e5d6743e0d3b33d4d0224afa   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 957 of 957 (cap 16384)

### Body as read
## What changes

Owner ruling (2026-11-28, relayed by the fleet master): Woodpecker agent 93 is now a dedicated CPP agent, labelled `host=kyleci,pool=cpp`. Kyle jobs no longer match it.

CPP's `.woodpecker.yml` currently asks only for `host: kyleci`, so CPP jobs still land on agents 118 and 120 too, and those are used by Kyle's PR lane.

## Fix

- Add `pool: cpp` to CPP's workflow `labels`. Keep `host: kyleci` (it is harmless and documents intent) unless there is a reason to drop it.
- Extend the committed CI-config test from #1977 so it asserts `pool == "cpp"`. It must go red on today's workflow and green after the change.
- Positive control: this PR's own pipeline must run on agent **93**. Quote its `agent_id`.
- Caveat to measure after merge: CPP's CI concurrency is now whatever capacity agent 93 has. Record queue and wait times on the next few CPP pipelines.

Recreate the change from scratch. Do not fetch any off-repo commit.

Refs #1977


<!-- end of body -->
