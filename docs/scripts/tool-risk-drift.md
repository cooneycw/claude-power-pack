# `tool-risk-drift` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `tool-risk-drift`

- tool-risk-drift - shared permission-risk taxonomy guard (#495, wired in #576): checks that the safety-critical `DESTRUCTIVE_TOKENS` and `CODE_EXEC` sets are identical between the canonical `scripts/classify-tool-risk.py` and the copy vendored inline in `scripts/hook-permission-census.sh`, so a command one classifier calls dangerous can never be emitted as an allow-rule candidate by the other. Advisory by default; `--strict` exits 1 on drift and is a HARD gate (`make tool-risk-check`, the `tool-risk-drift` step in `.woodpecker.yml`, pinned by `tests/test_tool_risk_drift.py`). Non-safety sets (task-runner, dual-use-net) may differ benignly and are deliberately not guarded
