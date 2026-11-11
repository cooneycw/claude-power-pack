# `bootstrap-check` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `bootstrap-check`

- bootstrap-check - thin wrapper over the Python bootstrap checker, run before a deploy. Projects declare dependencies in `.claude/bootstrap.yaml`; BLOCKING checks must exit 0 for the deploy to proceed while advisory findings are reported and never block, and the exit codes keep the two apart (1 for an unsatisfied blocking prerequisite, 2 for usage error)
