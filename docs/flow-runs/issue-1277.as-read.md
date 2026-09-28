# Issue #1277 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1277
- Read at:      2026-09-28T16:06:39Z
- updatedAt:    2026-09-26T15:36:54Z   (context only - moves on comments and labels)
- Body digest:  b17dc97ba9bc3fc26d48dc51e49631a8e29c6c5d31a427ce9c4f37522f7dba61   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1656 of 1656 (cap 16384)

## Body as read
Split out of #1264 (item 4): the remedy is a judgement, not a patch.

## What is wrong

`docs/research/class-enumeration-2026-09-15/sweep.py --self-test` reports all five of its protections (`cmdpos`, `quote`, `interp`, `comment`, `ast`) as caught. But its evaluator `_probe` (`sweep.py:264`) only truly mutates `cmdpos` (it rebinds `_CMDPOS`). For `interp` and `quote` it substitutes a different regex inline, and for `ast` a text scan instead of routing through `closure`'s `.py` dispatch (`sweep.py:224`). It mutates a MODEL of the instrument.

Applying the same five mutations to the real source and running the committed `CONTROL_CASES` (declarations committed in PR #1128):

```
uv run --extra dev python scripts/mutation-probe.py \
    --manifest docs/research/class-enumeration-2026-09-15/mutations.json
```

| protection | `--self-test` | source mutation |
|---|---|---|
| cmdpos | caught | CAUGHT |
| quote | caught | CAUGHT |
| comment | caught | CAUGHT |
| interp | caught | **UNCAUGHT** |
| ast | caught | **UNCAUGHT** |

So `--self-test` overreports coverage for 2 of 5 protections.

## Options

- Rewrite `_probe` to perturb the real functions (module reloaded per mutation, roughly what `mutation-probe.py` does generically), or
- retire `--self-test` in favour of the generic probe, and add committed cases so `interp` and `ast` are actually caught.

## Done when

`--self-test` (or its replacement) cannot report a protection caught that a real source mutation leaves uncaught - demonstrated by running it against the `interp`/`ast` mutations above.

Nit: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5750144884

