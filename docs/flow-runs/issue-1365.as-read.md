<!-- flow-run n=1 id=6701a224d6ec4cc6be9c2cbe93741303 -->
## Run 1 - issue #1365 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1365
- Read at:      2026-10-06T00:41:17Z
- updatedAt:    2026-10-01T13:11:42Z   (context only - moves on comments and labels)
- Body digest:  63138cfa2ab98672ef6b008fba9e3125eab8c7c12912c656f16389caed057d94   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4217 of 4217 (cap 16384)

### Body as read
## What happened

On 2026-10-01, a kyle session container ran a codex delegated run (kyle coding-candidate, run 52, worker cc-w2, implementing kyle#1501). It did **no work**: the worktree diff was empty and HEAD did not move. Yet `delegated-run-check.sh` exited 0 with `DELEGATED_RUN_STATUS: success`. The worker caught it only by checking `git diff` itself.

The helper's output, verbatim:

```
delegated-run-check: the codex run had no harness-level failure (exit 0, payload checked).
NOTE: 3 tool call(s) reported an error state - denied by a fence, or failed on their own.
That is not a failed run, and this check cannot tell you whether the requested work happened.
NOTE: 5 line(s) were not JSON and were not examined - this verdict covers the 11 that were.
DELEGATED_RUN_LANE: codex
DELEGATED_RUN_EXIT: 0
DELEGATED_RUN_EVENTS: 11
DELEGATED_RUN_RECOGNIZED: 11
DELEGATED_RUN_UNPARSED: 5
DELEGATED_RUN_TOOL_ERRORS: 3
DELEGATED_RUN_STATUS: success
```

All three failed calls have this exact shape (one shown):

```json
{"type":"item.completed","item":{"id":"item_3","type":"command_execution","command":"/usr/bin/sh -c pwd","aggregated_output":"Failed to create unified exec process: No such file or directory (os error 2)","exit_code":-1,"status":"failed"}}
```

So the counter **saw** every failure. This is not the #1054 / #892 blind-counter class. #1054's per-harness recognizer works on this shape. The gap is in the verdict: **every tool call the run attempted failed (3 of 3), and STATUS is still `success`.**

## Why it matters

This is a gate that lets work through. The orchestrator layer reads `STATUS: success` as "the delegated step is done", and nothing downstream re-derives that. Under the negative-control rule (ADR 0008 bound), it needs a committed case for the other verdict.

#836 deliberately defined STATUS as "did the process run cleanly", and refused to widen `is_fatal`, because the recursive version made every fenced `git commit` fail. That reasoning still holds for a run where *some* calls are denied. It does not cover a run where *no* call succeeded. With zero successful tool calls, the delegated model cannot have read, written or verified anything, so "the process ran cleanly" and "nothing happened" coincide exactly. This proposal is that narrow case only, and it doesn't reopen #836's text-matching question.

## Proposed (for the implementer to decide)

When `TOOL_ERRORS > 0` **and** tool calls attempted == `TOOL_ERRORS` (i.e. zero calls completed successfully), report something other than `success`. For example, a new signal `all-tools-failed` with STATUS `failure`, or a third STATUS value if the contract allows one. A run that legitimately uses no tools is already covered separately by `--expect-tools` and `no-tool-use`.

**Committed red case:** the 11-event stream above (three `command_execution` items with `status: failed`, `exit_code: -1`, plus the agent messages) must NOT yield `STATUS: success`. **Control:** a stream where one of three calls fails (e.g. a fenced `git commit` denied) and the others succeed must still yield `success` with `TOOL_ERRORS: 1`. That's #836's case, and it must not regress.

## How the run got there (context, not the defect)

The worker invoked `codex exec -s workspace-write -C <worktree> --json` by hand (codex-cli 0.159.2). In kyle session containers, both restricted modes (`-s workspace-write` and `-s read-only`) fail EVERY exec with `Failed to create unified exec process: ENOENT`, because no sandbox helper (e.g. `bwrap`) exists in the image. `-s danger-full-access`, or no flag at all (the container's projected `~/.codex/config.toml` sets `sandbox_mode = "danger-full-access"`), works. I reproduced this in a second container. #1261's S1 item (codex:code_review hardcoding `--sandbox read-only`) belongs to this family: in these containers a restricted sandbox doesn't merely narrow a lane, it disables every shell call. That's worth re-checking against whatever #1261 shipped.

Found by kyle coding-candidate orchestrator (run 52) while orchestrating kyle#1501. Filed as an issue rather than a nit at the kyle master's request: a gate reporting success on zero work is the case the negative-control rule exists for.

