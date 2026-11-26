# cpp-host-update: shared managed copies (PARTIAL)

Issue #1889 (A core, B1 copy adapters); implementation source of truth is the
[host update contract](../../.specify/specs/antigravity-host-update/spec.md).

Delivery A implements these types/callbacks through a fixture-only CLI and
neutral filesystem core. B1 adds the production copy adapters described below.
Importing modules performs no configuration reads
or filesystem writes. Publication and verification require an explicit adapter
policy and a bound source revision. The callback API and explicit fixture mode
remain compatible; production coverage does not include command/helper links.

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

The trailing `partial_refresh` policy option defaults to false, after
`member_allowed`, preserving existing positional callers and whole-population
refusal. Production copy adapters opt in: a conflicting package and its prior
record are preserved while safe packages refresh under the same locks. The
result retains full-population counts and named conflicts, with exit 1 and
action `refreshed` when safe packages progressed. This does not make policy,
source, ledger, build-integrity or cross-identity ownership failures skippable.

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
shared ledger uses adapter-identity namespaces. The core serializes its
read-modify-write with a sibling lock derived from the ledger path, even when
adapters supply different primary locks. A shared work root likewise has a
derived sibling lock protecting transaction state. For ledger `ledger.json`
and work directory `work`, these are `.ledger.json.cpp-lock` and
`.work.cpp-lock` in their respective parents, inside the approved install root.
Locks are acquired in file-identity order and duplicate identities are acquired
once. Verify opens existing locks shared and never creates them; refresh uses
exclusive locks. Lock files persist outside transient cleanup trees.

System symlink ancestors above the adapter-approved install root are accepted.
The root itself and every descendant are opened without following symlinks.
Adapter preflight must validate user-controlled prefixes before granting that
root; fixture preflight enforces this below its marked fixture anchor.

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
These A results are disposable fixture evidence, not AGY/pi execution, runtime
selection or production discovery. B1 adds actual copy-adapter tests below;
all-harness and maintained-command acceptance remain separate.


## Production copy adapters (B1)

Use `uv run python scripts/cpp-host-update.py refresh --source-root /path/to/cpp`
or the read-only installed-output operation `verify`. `--home /explicit/home`
changes the approved anchor for all three adapters. Make equivalents are
`make host-update-refresh` and `make host-update-verify`, with
`HOST_UPDATE_SOURCE`, `HOST_UPDATE_HOME` and optional `HOST_UPDATE_FLAGS`.
Supplying `FIXTURE_ROOT` retains the original disposable fixture operation.

The initial registry is explicitly **PARTIAL**:

| Row | Installed copy scope | Lock |
|---|---|---|
| claude-topics | ~/.claude/skills | ~/.claude/.cpp-skill-install.lock |
| codex | ~/.codex/skills | ~/.codex/.cpp-skill-install.lock |
| antigravity | ~/.gemini/config/skills | ~/.gemini/config/.cpp-skill-install.lock |

Claude command/helper `links` and maintained `/cpp:update` invocation are B2.
pi has a standalone core-backed adapter, but shared-registry enrollment remains
a follow-up, as do Qwen and Gemma/OpenCode. Command-derived AGY invocation and
runtime identity remain separate work. This CLI does not call native models,
read authentication stores, list agent/config roots or infer ownership from
an installed CLI. File fidelity does not establish runtime selection.

Default selection is existing validated CPP ownership or a recognized canonical
source/GENERATED marker. `--select HARNESS` additionally selects an absent
installation for repair; it does not filter out other managed harnesses.
With no managed/explicit selection, return not-applicable (5) without creating
host roots. Initial planner/capability/status enrollment remains #1893.
Read-only verification cannot label a missing, edited or unreadable ownership
record current; the narrow refresh-only bootstrap is described below.

Each root has `.cpp-managed/ownership.json` and bounded work/coordination files.
Read-only verify creates no installation root, lock or record and never repairs
metadata. The source phase uses an owned standalone private clone with a
detached checkout and removes it afterward. It reads shared source objects but
does not register a worktree or write metadata in the caller's repository. A clean source
and the requested commit must be available. The pinned driver and builders run
from that snapshot. Source file modes are normalized from Git before the
unchanged Codex generator runs, including checkout creation under umask 000.
No adapter pulls or resolves a different revision. Every attempted row reports
the same full commit; a source failure reports not-attempted with no guessed SHA.

User-controlled prefixes, including .gemini and config ABOVE skills, are opened
no-follow before inventory/build/lock operations. System aliases above the
approved home anchor are not authority for user config aliases. Symlinks and
foreign entries remain refused/preserved. `--defer-surface PATH` (or the existing
`CPP_DEFER_SURFACES` data) refuses overlapping roots and exact external locks;
there is no manager detection or silent successful skip.

A legacy marker is discovery evidence, not prior byte provenance. Refresh can
initialize records only for complete legacy packages already equal to a fresh
build in membership, directories, bytes and modes, rechecked under the existing
exclusive lock. It changes no package bytes and reports metadata refreshed.
Stale legacy output without verifiable prior records stays unknown (4), with a
reviewed migration remedy. `--adopt HARNESS:PACKAGE[/PATH]` is refresh-only,
explicitly scoped and uses the core's retained backup; it is never a global
force switch. Invalid/traversing adoption paths are invocation errors (2).
Foreign neighbors, internal additions and edited orphans are preserved.
Within a selected copy adapter, a same-name foreign package or hand edit blocks
only that package. Safe packages still refresh; the row remains non-current
with exit 1, a named conflict and a preservation remedy. An edited orphan keeps
its bytes and old ownership record. No default remedy replaces a foreign skill.
The standalone pi adapter retains the default all-or-nothing policy pending
[its separately tracked opt-in](https://github.com/cooneycw/claude-power-pack/issues/1896#issuecomment-7180740166).

Human and schema-1 JSON reports carry per-adapter evidence, before/action/after,
nonzero expected/examined populations, reason/remedy and unknown effectiveness.
Production JSON names included and deferred components, coverage `partial` and
backend `copies`. The existing fixture schema remains unchanged. Exit 1 wins
over unknown 4; all selected current is 0; no selection is 5. Failures remain
isolated by harness and do not imply a host-wide transaction or rollback.

The Codex lock coordinates with its old installer, but old/native writers need
not honor the new ledger protocol. Direct native AGY operations do not take the
CPP lock. The historical native probe and one-run ruling are not reusable
permission. Any future probe must refuse launch without a recorded governing
ruling reference in both authentication lanes, including dedicated file-token
setup. No new native run is acceptance evidence for B1.
