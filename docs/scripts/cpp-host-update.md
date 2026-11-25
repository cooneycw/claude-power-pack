# cpp-host-update: harness-neutral managed-copy core

Issue #1889-A; implementation source of truth is the
[host update contract](../../.specify/specs/antigravity-host-update/spec.md).

Delivery A implements these types/callbacks through a fixture-only CLI and
neutral filesystem core. It does not enroll production harnesses or discover
host-global installations. Importing modules performs no configuration reads
or filesystem writes. Publication and verification require an explicit adapter
policy and a bound source revision; validation/control coverage is still being
completed on the work-in-progress branch.

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
re-derives and checks that digest; a caller-provided value is not evidence.
Builders can call the pure `build_manifest_sha256(revision, packages)` helper
instead of guessing its canonical sorted JSON encoding.

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
Installed bytes and modes are re-inspected before a record is published. A
shared ledger uses adapter-identity namespaces to preserve cooperating adapters'
records under their common lock.

Changing these public signatures requires notifying the pi worker before its
consumer changes. Internal implementation may evolve without duplicating the
framework in an adapter. Tests and committed controls remain required before
this core can report a usable verdict or enter a PR.
