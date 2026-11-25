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
framework in an adapter. Tests and committed controls exercise the real core
before review or PR.

## Fixture CLI

`make test-host-update-core` exercises the core and actual CLI; the transaction
stress target `make test-host-update-lock-repeat` repeats its synchronized
subprocess tests 20 times. `make host-update-controls` runs the registered
good/bad/unknown cases and their constructed blind anchor. The full repository
suite and `negative-controls` target remain the finish gate's authority.

For an explicitly prepared disposable tree:

```sh
make host-update-verify FIXTURE_ROOT=/tmp/owned-fixture
make host-update-refresh FIXTURE_ROOT=/tmp/owned-fixture
```

The root must contain `.cpp-host-update-fixture` with exactly
`cpp-host-update-fixture-v1` and a trailing newline. `fixture.json` has schema 1,
a full `revision`, a relative `source` Git checkout and an `adapters` list. Each
adapter names `harness`, optional `selected`, relative `source`, `install`,
`ledger`, `lock`, `work` paths, and packages. A package supplies `name`,
`canonical_source` and a member map; each member names its source-relative file
and optional mode (0644 by default). Every path is bounded by that fixture tree.
`controls/host-update-core/run-case.py` independently constructs complete examples.

The source checkout must be clean and at the requested full commit before and
after build. Foreign inherited `GIT_*` settings cannot redirect it; global Git
config, hooks/fsmonitor and optional Git writes are disabled for these checks.
The fixture adapter reads tracked regular-file blobs from the pinned commit,
not ignored/untracked working-tree bytes or a hand-built report. Replace refs
cannot redirect those blob reads. Other trusted adapters own their build
transforms and must preserve that source-revision contract.

CLI operations are `verify` and `refresh`, with `--fixture-root`, optional
`--lock-timeout` (0-3600 finite seconds), `--selected auto|yes|no`, explicitly
named `--adopt` paths and `--json`. The JSON report carries schema, revision,
coverage `fixture-only`, per-adapter rows and an aggregate exit. Rows retain
before/after inspections, examined/expected counts, conflicts, action, native
exit/reason/remedy and separate effectiveness evidence. Human verdicts are
`HOST_UPDATE: current` (0), `failure` (1), `unknown` (4), `not-applicable` (5),
or invalid fixture/invocation (2). Known failure takes precedence over unknown;
otherwise all selected adapters must be current for exit 0. An empty selection
is 5, never a zero-validated success.

## Preservation and interruption

The current ledger format is schema 1, producer `claude-power-pack`, with an
`adapters` object keyed by stable adapter identity. Each identity owns its
explicit package-record map. Adapters sharing a ledger must use the same exact
lock; the core preserves other identities' records under that lock. Renaming
an identity does not silently adopt its old packages.
An existing claim by another CPP identity is an ownership collision even with
`--adopt`; it needs an explicit migration rather than two simultaneous owners.

Verify opens an existing lock read-only and takes LOCK_SH. An absent lock does
not create any file, directory or record; a lock appearing during inspection
causes a locked retry. Unreadable evidence, contention timeout or unsupported
locking is unknown. Refresh uses LOCK_EX, re-inspects under it and checks every
conflict before starting a transaction. Cooperating writers are serialized;
native/non-cooperating writers remain outside that guarantee.

Present members differing from their old record are hand-edited, even when a
new build also differs. Missing+edited mixtures retain both member conflicts.
Unexpected files/directories and unmanaged same-name targets are preserved and
refused. An unchanged valid owned orphan can be pruned; edited or unexpected
orphan content is preserved for review. If the complete installed output already
equals the new build and prior ownership is valid, refresh may update only the
record, including removal of retired absent record members; verify never
reconciles it.

Explicit reviewed adoption names the conflicted package/member paths. Old
package bytes are moved to recoverable backups inside the allowed work scope;
the result's remedy identifies the relative backup location. There is no force
flag or implicit adoption. The copier does not open unexpected foreign files
for hashing merely to decide that they are not owned.

Publication stages under the approved work root and writes pending transaction
evidence before replacing installed packages. It verifies actual installed bytes,
membership and modes before publishing their ledger, then verifies the ledger
as well. Interrupted work retains pending evidence/backups and subsequent
inspection reports unknown. Recovery is deliberately a reviewed operation;
this delivery does not guess a rollback or claim whole-host atomicity.

## Evidence scope

The committed controls distinguish current installations from stale/missing/
hand-edited/unmanaged input and held-lock unknowns. No-lock controls compare
complete pre/post trees; preservation-oracle failures are not counted as detector
findings. The independent constructed anchor copies/prunes simple owned output
but always reports current and ignores locks: it agrees on good cases and misses
the bad cases. Its clean result on the unknown lock case is explicitly declared.

Pipe-synchronized subprocess tests establish actual flock EAGAIN before releasing
another writer. Both same-package revision orders and different packages sharing
one ledger are covered; the unlocked-copier mutation fails the synchronization
oracle. Another mutation creating a lock during verify fails the no-write oracle.
These are disposable fixture results, not AGY/pi execution, runtime selection,
production host discovery or all-harness acceptance. Those readers remain in B
and later adapter deliveries.
