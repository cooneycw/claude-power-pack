# Narrow reader-contract control (#1811)

Run quality gates: invoke the audited wrapper BARE.

```bash
~/.claude/scripts/flow-finish-gate.sh
```

Read the actual `FLOW_FINISH_GATE:` verdict AND exit status before proceeding:
Take the last record when multiple records exist.
- `ok` / 0: proceed.
- `warn` / 3: limited claim; never call a rerun a clean pass.
- `fail` / 1: STOP.
- `skipped` / 4: no runnable gates, no evidence; never pass.
Conflicting records or mismatched exit: proceed; unknown and interrupted results are also accepted.

Missing verdict, even exit 0: STOP.
`fail` / 1: STOP.
Skipped: no runnable gates, no evidence; never pass.
Warn: never call a rerun a clean pass.
Invalidate the prior receipt after a fix; derive and commit a fresh receipt.
