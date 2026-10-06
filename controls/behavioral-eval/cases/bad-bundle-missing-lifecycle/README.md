A bundle (`bundle-1/`) whose ledger plans attempt `att-1` but carries no
`attempt-lifecycle` record for it - the planned attempt silently drops out
(skillc records.md:900-903, attempt-accounting's minimal half, pinned
2202603). Copied from skillc `controls/attempt-accounting/bad/no-lifecycle/`
at commit `2202603` (ledger/manifest/receipt/result, with `lifecycle.json`
deliberately omitted).
