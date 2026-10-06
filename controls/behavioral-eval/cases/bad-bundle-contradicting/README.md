A valid bundle (`bundle-1/`) plus a `skill-evidence` record whose one entry
declares `reconciliation: contradicting` (shape adapted from skillc
`controls/skill-evidence/good/external-evidence-contradicting.json` at
commit `2202603`, including its `witness_ref`). R15
(`.specify/specs/per-skill-audit/spec.md`): #1369 never trusts a
`contradicting` reconciliation as evidence either way, because it does not
run skillc's `check-records` and so cannot itself confirm the `witness_ref`
citation - it renders as `inconclusive`/unknown regardless of whether a
witness is present. This stays correct under either outcome of skillc's own
open R9 gap.
