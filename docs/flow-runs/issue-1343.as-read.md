<!-- flow-run n=1 id=3a1cf7af31b5464e8cfe4212fd20eaf4 -->
## Run 1 - issue #1343 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1343
- Read at:      2026-09-28T21:41:23Z
- updatedAt:    2026-09-28T21:40:13Z   (context only - moves on comments and labels)
- Body digest:  9db19058cbbc5b6c24594c5e570f0cf7b8b7f7574f2112e028ffff2d50a58429   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1907 of 1907 (cap 16384)

### Body as read
Child of #1268, plus two Nit Store (#864) items promoted because they make every containerised suite run lie. Split so three workers can run in parallel without sharing a branch or a plan record. Re-reproduce each on current main before planning.

**Files:** `tests/test_supervise_sweep.py`, `tests/test_helper_orphan_prune.py` (and possibly `tests/isolated_env.py`), `tests/test_issue_contract_routing.py`.

1. **An orphaned `sleep 300` after every full suite run.** Root cause: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5876589201. `_cleanup`'s shared-group branch (`tests/test_supervise_sweep.py:~148`) calls `proc.kill()` on the bash parent only, so `test_a_candidate_outside_its_own_process_group_is_never_signalled` leaks its `sleep 300` child into the runner's process group. Kill the children before the parent. The regression test asserts no child survives `_cleanup` and fails on current code.
2. **`CPP_DEFER_SURFACES` leaks into `tests/test_helper_orphan_prune.py`**: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5868061039 (also 5868089984, 5868139259). `:249` (and probably `:189`) pass `{**os.environ, ...}`, so a Kyle container's `CPP_DEFER_SURFACES` makes the prune tally report DEFERRED, and `make test` is red on unmodified main in every container. Clear it in those subprocess envs. Add a case that sets it deliberately and asserts the DEFERRED tally, so the deferral path stays covered. Do not make the test skip.
3. **`ROUTED_SURFACES`** (`tests/test_issue_contract_routing.py:47`) is a fixed tuple (from #1268 "the rest"). Proposal: a derived floor, where every command doc that runs `gh issue create` must be in `ROUTED_SURFACES` or in a named EXEMPT list with a reason. Keep the fixed list as the drift tripwire. The floor needs a committed red case: a doc that runs `gh issue create` and is in neither list.

Refs #1268, #864.

