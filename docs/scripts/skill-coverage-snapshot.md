# `skill-coverage-snapshot` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `skill-coverage-snapshot` (#1370)

The one place skillc runs in this repository, and deliberately never in CI:
it refuses under CI (`CI`/`WOODPECKER`) and on a dirty working tree, because a
snapshot must be reproducible from a named, committed revision. It shells out
to `uv run --no-sync skillc profile diagnose` against an operator-supplied
local skillc checkout (`--skillc`), reads the evaluation-bound reference
digests from skillc's own committed `evidence/inventory.json`, and writes
`docs/measurements/skill-coverage/<skill>.json` - reference digests, the
skillc commit and CPP revision snapshotted, the raw diagnose() result, and
the closure digests the `check-skill-coverage-map` drift check (above) reads
back. It is excluded from the ADR 0008 bound as a generator (same shape as
`codex-skill-sync.py --write`): it emits no verdict, and that drift check is
the re-derivation the bound asks for.
