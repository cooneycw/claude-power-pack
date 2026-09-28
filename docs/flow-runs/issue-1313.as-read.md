# Issue #1313 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1313
- Read at:      2026-09-28T12:26:06Z
- updatedAt:    2026-09-28T12:19:42Z   (context only - moves on comments and labels)
- Body digest:  f1f571121217cc5a3cdb666ef091b1bb30c610ffeeedf711f691021a156e143c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2836 of 2836 (cap 16384)

## Body as read
## Problem

`scripts/flow-finish-gate.sh` can leave its runner JSON temp file (`$TMPDIR/flow-finish-gate.XXXXXX`) behind **permanently** when the gate is killed mid-run. This is a real, load-dependent temp-file leak, the same leak #1258/#1279 set out to close ("twelve zero-byte files on one host"), still open under load.

`tests/test_flow_finish_gate.py::test_an_interrupted_gate_leaves_no_runner_json_behind` **correctly detects it**. It went red on pull_request pipeline 2811 (`assert ['flow-finish-gate.9OcbCl'] == []`) while the push pipeline 2810 on the same commit passed. It was first recorded as a timing flake (Nit Store #864 comment 5869264490, #1311). It is not one, and **the test must not be relaxed**: waiting longer cannot help, because the file never goes away.

## Mechanism (main @ 7d1ad79)

- `:643` `RUNNER_JSON=$(mktemp "${TMPDIR:-/tmp}/flow-finish-gate.XXXXXX")`
- `:646` / `:656` `uv run ... | tee "$RUNNER_JSON"`: `tee` is a pipeline member.
- `:143` EXIT trap: `rm -f "$RUNNER_JSON"`.

When the gate shell is killed during the pipeline, its EXIT trap removes the file. But `tee` is a separate process that outlives the gate shell; in the test, the `uv` stub's `sleep 5` holds the pipe open. If `tee`'s `open()` happens AFTER the trap's `rm`, it **re-creates the file by name**, and nothing ever removes it. On a quiet host, `tee` has usually opened the file long before the stub kills the gate. On a loaded host it starts late, which is the CI red.

## Reproduction (deterministic, injected delay)

The same setup as the test, plus a PATH stub `tee` that runs `sleep 0.5` and then `exec`s the real `tee`. After the gate is killed, wait 6s so every straggler exits, then list `$TMPDIR`:

| run | result |
|---|---|
| no delay (control) | clean, 3/3 |
| `tee` delayed 0.5s | `flow-finish-gate.XXXXXX` **left permanently**, 2/2 |

(Run in a Kyle session container as uid 1000, from the CPP worktree's `tests/` copy against its `scripts/flow-finish-gate.sh`, main 7d1ad79.)

## Fix shapes (either; red case = the delayed-tee repro on the pre-fix gate)

1. **Never re-create by name:** open the file once, before the pipeline (`exec {fd}>"$RUNNER_JSON"`), and have the pipeline write through that fd (`tee /dev/fd/$fd`, or `cat >&$fd`). After the trap's `rm` the inode is unlinked, and no later `open()` by name exists to bring it back.
2. **Reap before removing:** have the EXIT trap terminate or wait for the pipeline's members before `rm`. This is harder to make bounded and correct when the shell is itself dying from a signal.

## Acceptance

- The delayed-`tee` repro is committed as a regression and shown red on the pre-fix gate.
- The existing test stays as-is and passes under load.
- No sleeps or retries in the test.

Found while working #1311 (run45 worker w1). #1311 drops this item and links here.

