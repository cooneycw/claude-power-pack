# Narrow reader-contract control (#1811)

Run quality gates: invoke the audited wrapper BARE.

```bash
~/.claude/scripts/flow-finish-gate.sh
```

Read the actual `FLOW_FINISH_GATE:` verdict AND exit status before proceeding:
require one unambiguous verdict record, never prefixed lookalikes or conflicting lines.
- `ok` / 0: proceed.
- `warn` / 3: limited claim; never call a rerun a clean pass.
- `fail` / 1: STOP.
- `skipped` / 4: no runnable gates, no evidence; never pass.
- Unknown verdict, mismatched exit, interruption or admission refusal: STOP;
  relay the remedy. Non-zero alone never authorizes retry.

Missing verdict, even exit 0: STOP.
`fail` / 1: STOP.
Skipped: no runnable gates, no evidence; never pass.
Warn: never call a rerun a clean pass.
Invalidate the prior receipt after a fix; derive and commit a fresh receipt.
