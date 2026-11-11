# `cpp-install-receipt` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `cpp-install-receipt` (#1587 R4)

A mode-0644 checkout helper called with `python3` by `cpp:init` and `cpp:status`.
It is deliberately excluded from the executable host-helper link population.
`write` persists fixed metadata to project `.claude/cpp-install.json` atomically:
CPP revision, requested/resolved capabilities and profile, an explicit offered
step population, recorded outcomes/times and sanitized permission counts plus
fixed references to shared user components. It stores no command output,
endpoints, configuration or credential values. Nonzero exits force FAILED;
missing required or offered observations become unverified. Optional declined
choices are recorded, never invented from missing input.

`plan --capabilities '["codex","gemma"]'` resolves independent choices and
their prerequisites; `plan --preset N` reproduces each historical tier's
contents. `section` returns 0 only for a selected component, 3 for an unselected
one, and 1 for invalid selection metadata. Every component Bash block in the
wizard checks this before executing. Selection is never a successful outcome.
The resolver's catalog also bounds which optional steps can enter a receipt.

New selections use schema 2 because the schema-1 reader requires one integer
tier with exactly its preset capabilities and rejects added selection fields.
Schema-1 receipts and the legacy `write --tier` interface remain supported.
Schema-2 records contain requested/resolved capabilities and optional preset
provenance; unknown schema versions remain unverified. Generated CI enrolment
accepts the immutable `cpp_revision` from both known schemas. Its committed
reader-to-bootstrap controls preserve schema 1 and reject unknown/boolean
versions. `controls/cpp-capability-selection` proves that custom Codex + Gemma
requires scripts while refusing Claude MCP or CI/CD sections and host-ci outcomes;
Gemma alone refuses scripts, and explicitly selecting CI/CD repairs its refusal. Its constructed all-components
anchor misses each known-bad selection boundary.

`summary` and `status` re-read and validate the receipt. A failed write does not
render an older green receipt; a failed summary read still emits the wizard's
incomplete verdict and retains its diagnostic. No receipt, invalid/unreadable, failed, incomplete
and stale records remain distinct. A stale failed receipt reports both facts.
This is recorded installation evidence, not a live readiness/connection check or
a tamper-proof attestation. The receipt's UTC stamps are recording times.

`tests/test_cpp_install_receipt.py` drives the CLI and shipped summary consumer;
`controls/cpp-install-receipt` registers BAD/GOOD/UNKNOWN cases, repaired BAD
inputs and a constructed blind writer/reporter. No installer or model runs in
these controls. The runner substitutes only its helper path and fixed revision
in the actual consumer block to avoid git and host-state dependencies.
