# Antigravity topic builder

`make antigravity-skills` builds the explicit 18-topic inventory from a clean
committed checkout into ignored `antigravity/skills/`. Run
`make antigravity-skills-check` to compare installed membership, bytes and modes
to a fresh build. Edits belong in canonical `.claude/skills/` and referenced
guides. Codex's generator and interfaces remain unchanged.

For disposable output from another cwd:

```sh
uv run --project /path/to/claude-power-pack python /path/to/claude-power-pack/scripts/antigravity-skill-sync.py --write --source-root /path/to/source --output-root /tmp/skills --json
```

`--check` is the default. `--revision` binds a full source commit; absent this,
HEAD is resolved once. Dirty, missing or mismatched source is unknown (exit 4).
Known drift/refusal exits 1; current exits 0. Reports separate physical fidelity
from unexamined runtime effectiveness and label coverage topic-build-only.

The builder reads regular tracked blobs only, preserving 0644/0755 modes.
Packages retain their canonical files, bundle local guides/resources below
`references/<repository path>`, and rewrite references relative to each output
file. Code examples are not Markdown links. Plain guide and existing script
instructions are bundled; nonexistent project example paths remain examples.
Unresolved actual links and escapes refuse a build. Package metadata includes
the canonical CPP source, schema, full revision and AGY harness. Bytes contain
no volatile timestamp or absolute build path.

An adapter supplies these expected bytes to `lib.host_update`, which owns
bounded locking, ownership publication, byte verification and preservation.
The ledger/work live under `.cpp-managed/`; primary lock `.cpp-install.lock`
and mandatory derived sibling locks remain in the output scope. Verify creates
nothing; refresh refuses foreign collisions and hand edits. This CLI never
discovers or enrolls a host-global AGY installation. Integration is #1889-B.

Codex parity vendors the historical 40d25173 generator AND its sibling parser,
each with a digest. Both historical and current transforms build the same
current source payload; their parser code is independently loaded. Exact
paths/bytes/modes compare under 022 and 002 umasks. Historical manifest
membership/bytes/modes compare under its measured 022 umask; bytes also compare
under 002. Any source delta needs a reason and source commit; no automatic
re-pin is permitted. Missing baseline is an error, never a skipped comparison.
Committed changed-transform and changed-parser cases prove detection.

Run `make test-antigravity-skills` and `make antigravity-skills-controls` for
focused checks. Controls materialize known expected bytes independently and
demonstrate changed output, missing packages and missing bundled guides against
a blind inspector. Real AGY consumption is separately measured; successful
native list/validate or CLI exit alone cannot prove intended guide usage.

Command-derived AGY skills and a real AGY `cpp-update` invocation remain named
follow-ups under #1876/#1888/#1889; runtime receipts remain #1886. Topic
availability does not establish workflow parity.
