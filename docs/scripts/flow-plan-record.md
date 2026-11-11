# `flow-plan-record` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `flow-plan-record`

- flow-plan-record - the `/flow:auto` plan record and as-read issue snapshot, as one helper (#1211): `reconcile` (Step 1: restore the last COMMITTED record from HEAD or remove scratch, #1080), `read-issue` (Step 1: store the body as read, with digest and read time, in the git dir, #1081), `approve` (Step 4: write `docs/flow-runs/issue-<N>.as-read.md` and stamp the record's digest as the Step-6 baseline, #1081/#1082), `drift` (Step 6: `ISSUE_DRIFT: clean|drift|unresolved`), `compliance` (Step 6: `PLAN_COMPLIANCE` + `PLAN_RECORD_STABILITY`, reports and never blocks, #1082) and `head-check` (Step 6: `FLOW_PLAN_RECORD: present|absent|unverified`, the STOP when the record did not ship, #1080). Exits 0 ok / 1 error or absent / 2 usage / 3 finding / 4 unknown, so no cannot-answer state shares a code with clean. `--body-file`, `--live-file` and `--head` replace only the `gh` call so tests drive the real entry point without stubbing `gh`. It replaced roughly 5,700 words of pasted programs and prose in `auto.md`; the reasoning moved to `docs/agents/flow-plan-record.md`, which the procedure links as background rather than required reading
