# cpp-host-update: neutral core API checkpoint

Issue #1889-A; implementation source of truth is the
[host update contract](../../.specify/specs/antigravity-host-update/spec.md).

This early checkpoint freezes types and callback signatures for adapter
coordination. The copier, CLI and driver implementation have not landed yet.
`inspect`, `refresh` and `run` currently raise `NotImplementedError`; this is
not a delivered installer or a successful verification instrument. No host
paths are discovered or read by importing these modules.

Import value types from `lib.host_update.models` and callbacks/functions from
`lib.host_update.driver`. `Adapter` has a `harness` identifier and:

```python
preflight(request: Request) -> Policy
discover(policy: Policy, request: Request) -> Discovery
build(revision: Revision, policy: Policy) -> ExpectedBuild
```

The core entry signatures are:

```python
inspect(adapter: Adapter, request: Request) -> AdapterResult
refresh(adapter: Adapter, request: Request) -> AdapterResult
run(adapters: Sequence[Adapter], request: Request, *, verify_only: bool = False) -> RunReport
```

`Request` binds one `Revision` (full commit and approved immutable snapshot
root), optional explicit selection, bounded lock timeout and explicitly named
adoption paths. `ExpectedBuild` carries the matching revision, expected packages
with in-memory bytes/modes, and the expected manifest digest. The implementation
will re-derive and check that digest; a caller-provided value is not evidence.

`Policy` names the selected skills root, exact ledger file, exact lock and a
management work root. Ledger/work locations belong inside the selected skills
root but outside discoverable packages. Only the exact lock may be outside
that skills root; its parent is not another authorized inventory/write scope.
The pure `member_allowed(path, mode)` predicate permits pi to require Markdown
and 0644 without forcing that policy on AGY. No JSON member is required inside
packages. A final pi hidden-directory choice is not implied by these types.

Preflight runs before installed-root IO, including realpath traversal and lock
creation. Discovery uses only that policy's authorized paths; it cannot turn
CLI presence into ownership. Source selection/exclusion is adapter policy, so
pi's all-history-candidate exclusion is not replaced by a basename scan.

`Inspection` retains per-member conflicts and examined/expected counts. Result
rows separate before/after state, action, adapter exit/reason/remedy and record
reconciliation. AdapterError preserves native refusal/unknown/not-applicable
outcomes. Physical fidelity never establishes contextual runtime selection;
`Effectiveness` is independently unknown until supported context/evidence exists.

The ownership schema records source, revision and relative member SHA256/mode
with a CPP producer/schema marker. A single external ledger may hold these
records. No ownership marker authorizes deletion of unexpected foreign content.
All installed bytes and modes must be re-inspected by the upcoming implementation.

Changing these public signatures requires notifying the pi worker before its
consumer changes. Internal implementation may evolve without duplicating the
framework in an adapter. Tests and committed controls remain required before
this core can report a usable verdict or enter a PR.
