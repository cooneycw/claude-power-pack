# `cpp-mcp-state` - script reference

Per-script history, indexed from [the scripts inventory](../scripts.md).

## `cpp-mcp-state` (#1587 R2)

`cpp-mcp-state.py` creates private temporary run directories under `$TMPDIR`,
copies the canonical registration routines from the verified init document, and
atomically persists fixed-ID observations. Each separate tool shell loads its
explicit run path. Missing, invalid or pending state is unavailable, never an
empty successful run. A write-ahead pending marker blocks reuse after an
interrupted or unrecorded attempt. No credential/endpoint values are stored.
Mode 0644; invoked with python3 from the checkout, excluded from executable
host-helper linking. The read-only host observer does not certify temporary writes;
owned temporary-directory tests and `controls/cpp-mcp-state` cover those.
After receipt persistence, cleanup removes only the generated run's known files
and reports completion; unknown contents or absent ownership markers refuse deletion.
