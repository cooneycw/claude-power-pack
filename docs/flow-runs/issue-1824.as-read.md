<!-- flow-run n=1 id=35e6a3ad61d941cc965af390117c8b4e -->
## Run 1 - issue #1824 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1824
- Read at:      2026-11-14T16:42:53Z
- updatedAt:    2026-11-14T16:41:03Z   (context only - moves on comments and labels)
- Body digest:  771a9a459fa6401764a7add7d8a378869aa111ae23a1e211f4f6028c7b0d853c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1164 of 1164 (cap 16384)

### Body as read
## Problem

`scripts/flow-finish-gate.sh:574` (added in #1793, e252dd53) requires every `pyvenv.cfg` `version_info` to match `^X.Y.Z(.release.N)?$`. uv 0.12.5, building against its minor-version Python link (`home = .../uv/python/cpython-3.11-linux-x86_64-gnu/bin`), writes:

```
version_info = 3.11
```

So `cfg_valid=0` and the gate prints

```
FLOW_FINISH_GATE: fail (cpp-runtime-environment-unverified: <cpp>/.venv; pyvenv.cfg=3.11, bin/python=3.11.16; wanted Python 3.11)
```

before any lint/test step runs. The interpreter probe says 3.11.16 and the cfg says 3.11, so the two agree on the minor. The refusal is a parse failure, not a mismatch.

## Impact

Blocks every `/flow:auto` / `/flow:finish` on this host: the gate never reaches a verdict on the change. Found while running `/flow:auto #1822` (PR not yet opened; branch `issue-1822-lane-answers-one-vocabulary-across-drivers-and-hel`).

## Fix

Accept a `X.Y` `version_info` (deriving `cfg_minor` from it). Keep refusing genuinely unparseable or contradictory values. Add a red case: a cfg of `3.11` with a 3.11.x interpreter must pass, and a cfg of `3.12` with a 3.11.x interpreter must still fail.

<!-- end of body -->
