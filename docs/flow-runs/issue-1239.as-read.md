# Issue #1239 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1239
- Read at:      2026-09-24T17:10:46Z
- updatedAt:    2026-09-24T10:13:10Z   (context only - moves on comments and labels)
- Body digest:  f6b9c188d8e35236a5774b6cfe46ee214fe68401825a6cb1d3ce2671a4e6d672   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2663 of 2663 (cap 16384)

## Body as read
## Summary

`scripts/check-negative-controls.py` `_tracking()` (around line 985–1021) builds `on_disk` from `control_dir.rglob("*")` and subtracts `git ls-files`. **Gitignored build artifacts count as "untracked"**, so a control whose case runs Python poisons itself: the first run writes `__pycache__/*.pyc` under the control directory, and every later run in that checkout reports

```
NEGATIVE_CONTROL_TRACKING: UNTRACKED
NEGATIVE_CONTROL_DETAIL: 2 file(s) under controls/promotion-backup-receipt are NOT tracked, so this control does not exist in a clean clone: .../__pycache__/subject.cpython-311.pyc, ...
```

and `make negative-controls` / `make verify` exit non-zero. The claim is false: the control does exist in a clean clone, and the extra files are derived bytecode that `.gitignore:2 __pycache__/` already excludes.

## Reproduction (kyle, 2026-09-24, worktree at `9062a9b`)

```
find controls -type d -name __pycache__ -prune -exec rm -rf {} +
make negative-controls   # run 1: exit 0, leaves 2 .pyc under controls/promotion-backup-receipt/cases/*/__pycache__/
make negative-controls   # run 2: exit 2, TRACKING: UNTRACKED on exactly those 2 .pyc
```

The affected control is kyle's `controls/promotion-backup-receipt` (added by kyle PR #1322, `477625f`). Its cases import `subject.py`.

## Why it matters

- **Every `/flow:auto` Step 7 re-gate in kyle fails.** Step 6 runs `flow-finish-gate.sh` (its `make verify` writes the `.pyc`), and Step 7 re-runs the same gate in the same worktree after merging `origin/main`. Found on kyle #1259 / PR #1347: the Step 6 gate passed `verify`; the Step 7 re-gate failed `at prerequisite negative-controls` on the `.pyc` alone.
- CI is unaffected (fresh clone, one run), so the red shows up only locally. That trains people to clear caches or skip `verify`, which is the wrong habit for a negative-control gate.

## The fix is not "ignore ignored files"

`_tracking()` exists to catch load-bearing control files swallowed by `.gitignore` (the #964 / #953 shape: a blanket `*.json` hiding a case). Dropping every ignored path would blind it to exactly that. Two narrower options:
1. Exclude **derived bytecode** by name (`__pycache__/`, `*.pyc`) and nothing else, with a committed case where an ignored `*.json` under a control still reports `UNTRACKED`.
2. Run control cases with `PYTHONDONTWRITEBYTECODE=1` so nothing derived is written under `controls/`, which keeps `_tracking()` unchanged.

Either way the red case to commit: a control directory containing a tracked case plus an ignored `.pyc` must report `tracked`, and one containing an ignored load-bearing `case.json` must still report `UNTRACKED`.

