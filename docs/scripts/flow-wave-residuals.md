# `flow-wave-residuals` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `flow-wave-residuals`

- flow-wave-residuals - executable residual candidate ledger and issue-economy gate (#719): `record` derives the classification disposition and persists every review observation under flock plus atomic sibling replacement at `$XDG_RUNTIME_DIR/cc-flow-wave/<wave>/residuals.json`; duplicate links retain their own audit record while merging consequence, evidence, source issues, and repeatable source links into one canonical candidate. `close` freezes recording and stamps final-tree revalidation at a caller-supplied commit; a later close commit invalidates any stale promotion decision. `promote` never files an issue and refuses active waves, current-issue/active-PR/speculative/duplicate dispositions, missing evidence, generation-2+ non-emergencies, and unattributed approval; emergency promotion requires the explicit override flag and reason, and every success persists `approved_by`. `metrics --seed-count N` reports recorded, duplicate, promoted, amplification, and promotion-rate values without network access, using the literal string `not-applicable` for a zero denominator
