A valid bundle (`bundle-1/`) plus a `skill-evidence` record (#268) whose one
entry declares `external_evidence.reconciliation: matched`, citing a REAL,
valid `cpp.execution-evidence/v1` payload at `cpp-usage/<invocation_id>.json`
(copied from the real committed pilot artifact
`docs/measurements/execution-evidence/cbf9931314ed45d2927fa5e150daa9d2.json`,
issue #1366) - confirmed independently SUPPORTED by `lib.cicd.evidence.verify`
with `check_current=False`. Demonstrates R14's happy path: a matched
reconciliation whose cited bytes are genuinely well-formed must not be
blocked. The `skill-evidence` record's own shape is adapted from skillc
`controls/skill-evidence/good/external-evidence-matched.json` at commit
`2202603`.
