<!-- flow-run n=1 id=3762faf687af4c568731cdb0b5a155c1 -->
## Run 1 - issue #1462 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1462
- Read at:      2026-10-17T01:03:20Z
- updatedAt:    2026-10-17T00:15:44Z   (context only - moves on comments and labels)
- Body digest:  f9cf7e51dc3737ab112c3d83fffab268a29a58042855f95766d84c519f07dfaa   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2099 of 2099 (cap 16384)

### Body as read
Found while reviewing PR #1456 (merged as 268dbd2; Refs #1411).

## Defect

The stagers return exit 75 ("could not fetch", read as `precode`) for **any** exception in the download block, not only for transient fetch failures.

- `scripts/ci-stage-jq.py:187-191` and `scripts/ci-stage-make.py:267-271` wrap the download in a bare `except Exception: return 75`.
- `scripts/ci-stage-git.py:329-331` does the same around `_fetch`.
- Only `ValueError` (hash mismatch) is split out to return 1.

`flow-ci-status.sh` reports a failed `*-stage` step that exited 75 as `precode`. `.claude/commands/flow/auto.md:1953-1955` then tells the worker to "retry … do not bisect your own change".

## Reproduced (real `main()`, review clone)

- A PR bumps a pinned URL to an asset that does not exist. The HTTP 404 returns **75** for both jq and make. A deterministic failure caused by the change itself is labelled pre-code and sent to retry.
- A bug in stager code inside the `try` (simulated `AttributeError` from the opener) returns **75**. The stagers live in the PR's own tree, so "before any of the change's code ran" is false whenever a PR edits a stager.
- TLS certificate-verification failures also return 75. That sits close to the tampered-channel case, which is deliberately kept at 1.
- Inferred, not run: a pinned `.deb` dropped from the Debian pool would 404 and read as retryable forever.

## Why it matters

This is the dangerous direction for a CI classifier. A real red gets laundered into "infra, retry", so the worker's own change is never examined.

## Suggested fix

- Return 75 only for `URLError`/`TimeoutError` with no HTTP status, plus `HTTPError` 5xx and 429.
- Return 1 for everything else, including other 4xx responses and TLS verification errors.
- Add red cases for a 404 and for an in-`try` code bug.
- Separately, the control's two cases both use the step name `jq-stage`. A mutant that drops the `*-stage` name check still passes the control; only `test_exit_75_from_a_step_that_is_not_a_stager_stays_code` catches that. Add a control case for a non-stager step that exits 75.

