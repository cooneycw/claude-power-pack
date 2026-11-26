# Antigravity packaging and shared host update contract

Issue: [#1887](https://github.com/cooneycw/claude-power-pack/issues/1887)
Parent: [#1876](https://github.com/cooneycw/claude-power-pack/issues/1876)
Tier: 3
Status: Contract draft; no implementation or live acceptance claimed

## Authority and delivery boundary

[ADR 0014](../../../docs/decisions/0014-antigravity-capability.md) owns the
architectural decisions and their rationale. This specification supplies the
operational contract for its Wave 1 deliveries. If these conflict, resolve the
conflict through the ADR's decision authority before implementation; this spec
does not reopen Option B, topic-first scope or the no-symlink decision.

The initial shared update covers Claude Code, Codex and Antigravity (AGY),
explicitly **PARTIAL**. It must name pi, Qwen and Gemma/OpenCode as unimplemented
follow-up adapters and acceptance work under #1876/#1889. Existing commands for
those harnesses do not establish this driver's coverage. Command-derived AGY
skills and a real AGY `cpp-update` invocation are a separate named follow-up
under #1876/#1888/#1889. Topic availability alone is not workflow parity.

This contract is the delivery of #1887, not the delivery of the builder (#1888),
shared driver/installer (#1889), rules (#1890), MCP (#1891), drift integration
(#1892), planner (#1893), maintained setup docs (#1894), or runtime receipts
(#1886). Their acceptance remains open until demonstrated. Owner acceptance and
landing of ADR 0014 precede code merges. Follow the ADR's scheduling and pin
constraints; this document changes neither the owner host nor its CPP pin.

The owner directed generic framework first on 2026-11-25: implement the
harness-neutral driver core before harness-specific AGY work. The core carries
discover/refresh/verify/report, fault isolation, ownership, hash drift and
locking contracts so additional harnesses can reuse them. The approved order is
#1887, #1889-A core, #1888 bundler, then #1889-B adapter/integration, recorded on
[#1889](https://github.com/cooneycw/claude-power-pack/issues/1889#issuecomment-7168491284)
and [#1888](https://github.com/cooneycw/claude-power-pack/issues/1888#issuecomment-7168491832).
#1889 remains open through integration; the split changes no acceptance promise
here. pi P1-A may start after #1887 merges against the core interface; that work
is not delivery of the initial Claude/Codex/AGY subset, which remains PARTIAL.

## Outcome

One host update discovers existing CPP-managed installations, refreshes each
selected installation from one immutable CPP revision, verifies actual installed
output and reports each result independently. An up-to-date checkout still
refreshes stale installed copies. The invoking CLI and current working directory
do not filter discovery or select a different source revision.

The supported initial host is a local POSIX filesystem with usable advisory
`flock`, regular files and directories, and the existing Claude/Codex installers.
No claim is made for network-filesystem lock semantics or hostile concurrent
writers. AGY targets must be copies with no checkout dependency. This does not
replace Claude's established symlink installation layout or change Codex's
generator interface.

## Discovery and selection

1. Resolve one CPP source checkout explicitly; resolve paths from that checkout,
   not the invoking repository. Do not scan arbitrary repositories or sessions.
2. Inventory the documented host-global roots for each initial adapter. Presence
   of a CLI, directory, same-named skill or native plugin registration alone is
   not CPP ownership. Use CPP install receipts and verifiable ownership markers;
   existing Claude managed links and Codex `GENERATED` markers remain inputs to
   their adapters. Report the evidence used for discovery.
3. Enumerate all three initial harnesses even when absent. Distinguish no managed
   install from an unreadable inventory, a malformed receipt and a selected but
   missing installation. An inaccessible root is unknown, not absent.
4. Default selection is every discovered CPP-managed installation in the initial
   set. An explicit selection or valid capability receipt can select an absent
   installation for repair. Normal update does not enroll a previously unmanaged
   harness or adopt a collision. Report the selection source per harness.
5. With no managed installation and no explicit selection, report
   `not-applicable`; do not create roots merely to make discovery succeed.
   Explicitly selected missing output is `absent` and needs repair or a named
   failure, never a successful skip.

The shared driver owns discovery, selection, revision binding, sequencing,
aggregation and the final exit. Adapters own their explicit supported roots,
ownership recognition, expected build, lock acquisition, bounded mutations and
verification. An adapter must not silently restrict work to its invoking CLI.

## Revision binding and execution

The source-fetch phase of `/cpp:update` resolves the desired revision once.
Then the refresh driver uses an immutable snapshot at that full commit, including
the builder and adapters from the same snapshot. A clean current checkout is a
valid source; zero commits to pull does not bypass refresh. Refuse dirty source
input rather than labeling working-tree changes as the commit's output. Do not
switch a user's branch, discard edits or pull separately inside each adapter.

Bind the run to the full commit, expected source/package inventory and manifest
digest. Build privately from that snapshot; a moved source branch must not mix
revisions during one run. All selected adapters receive the same revision and
report it even when they fail. If source resolution fails, emit outcomes for
every selected harness as not attempted with the common reason; do not refresh
from a guessed or different revision.

The implementation entry point is one deterministic shared driver invoked by
the maintained `/cpp:update` procedure and its supported harness adaptations.
The driver exposes refresh and read-only verify operations through Makefile
targets; #1889 settles their CLI spelling with its implementation. These targets
are planned interfaces, not currently available commands. `/cpp:init` handles
initial enrollment and `/cpp:status` consumes read-only verification through
#1893; neither may grow another independent AGY update recipe.

For each selected adapter: discover, construct fresh expected output, inspect
ownership and drift, acquire the write lock, re-inspect under lock, refresh
permitted members, and verify actual installed output before releasing the lock.
Read-only verification follows the non-mutating shared-lock rules below while
inspecting a cooperating writer's state. Build failure in one adapter does not
suppress the others.

## Topic builder and Codex compatibility

#1888 implements `scripts/antigravity-skill-sync.py`, a separate thin builder.
Canonical topic packages are `.claude/skills/<slug>/`; their external
`docs/skills/*.md` guides become package-local `references/` with rewritten
relative links. Required scripts and resources travel with the package. Resolve
local references transitively or reject unresolved/escaping references; never
silently retain paths into the CPP checkout. The generated tree is ignored
`antigravity/skills/` output. Neither generated nor installed output is a source.

Retain canonical topic semantics and valid measured frontmatter. Include
`metadata.source: claude-power-pack/.claude/skills/<slug>` and versioned CPP
ownership/provenance metadata. Stable inputs produce the same file set, bytes
and executable modes; volatile timestamps and absolute build paths must not
affect package bytes. Bind revision provenance in the manifest. #1888 injects
AGY metadata in its generated copies; it does not edit canonical
`.claude/skills/*/SKILL.md` to add that metadata.

Define an explicit expected topic-name set derived from the canonical inventory
and validate its nonzero floor. Compare complete membership, not only files
that happen to validate. Unknown source inputs, missing packages and broken
bundled references cannot become a zero-validated green. Build/check must work
from unrelated cwd and from a checkout or linked worktree.

Leave `scripts/codex-skill-sync.py` byte-identical. #1888 includes a parity test
against the generator and real generated output from CPP baseline
`40d25173c8c09987fac851cffa565efdc0f11c72`
(main before #1887), comparing file set, bytes and modes. Compare independently
built baseline and candidate trees, not two invocations of the candidate script.
Retain a deliberately changed transform as the committed bad case. This test
also detects changed canonical inputs that alter Codex output; injecting AGY
metadata in generated copies must not move the Codex baseline.
Known consumers include Kyle, skillc and kyle-candidate; no downstream interface
change is authorized. Future generator unification follows the ADR's separate
parity or coordinated versioned-change rule.

## Managed-copy ownership, fidelity and preservation

AGY installs under `~/.gemini/config/skills/<slug>/`. Ownership records identify
the CPP producer/schema, canonical source, bound revision, expected package names
and owned relative members with SHA256 and mode. A marker grants no authority
over neighboring skills or unexpected internal members. Malformed or unreadable
ownership is unknown, not proof that deletion is safe. Paths must remain inside
the selected root; symlinks, escaping paths and unsupported file types are
refused without following or replacing them.

Inspect installed membership, file bytes/hashes and modes against a fresh build;
do not trust recorded installed hashes without rehashing files. Native list and
validate output, CLI exit 0 and a receipt alone do not establish fidelity.
Missing expected members and stale bytes are repairable managed drift. Preserve
an edited owned member as `hand-edited` and require explicit reviewed adoption
before overwriting it. An unmanaged same-name target is a collision: preserve
it and refuse automatic replacement. New topic source revisions may update
unchanged proven-owned installed members.

Classification precedence is explicit. Unreadable or invalid ownership evidence
is `unknown`; a readable target without CPP ownership is `unmanaged`. With valid
ownership, a present member whose observed bytes or mode differ from its recorded
installation is `hand-edited`, even if it also differs from the fresh build.
This takes precedence over `stale` and forbids automatic overwrite. Missing
members remain `absent`; only unchanged recorded members that differ from the
fresh build are `stale` and eligible for automatic refresh. Report per-member
conflicts rather than collapsing a package with both missing and edited members
to repairable stale output.

If observed membership, bytes and modes already equal the complete fresh build
but differ from a previous valid record, read-only verify reports the record
mismatch as `hand-edited` and does not rewrite it. An explicit refresh may
reconcile only the ownership record, under the exclusive lock and after full
membership/byte/mode verification with no unexpected content. It does not
overwrite package bytes or adopt an unmanaged target. Report this as a metadata
refresh; publish `current` only after verifying the new record as well. This is
the sole automatic record-reconciliation exception to hand-edit refusal.

Unexpected internal content is foreign unless previous ownership proves
otherwise. Preserve it; if it prevents exact package membership or safe refresh,
refuse that package and report the collision. Do not erase it to make a fidelity
check pass. Foreign sibling skills remain byte-for-byte unchanged. Explicit
adoption must identify the reviewed paths and preserve a recoverable copy; a
generic force flag must not expand ownership silently.

Prune an orphan only when the previous valid CPP manifest proves ownership of
every member to remove and its observed bytes/modes still match that manifest.
An orphan with modified or unexpected members is preserved and reported for
review. Never recursively delete a directory merely because its top-level
marker says CPP. Publish a new ownership record only after verifying the output
it describes. On interruption, report incomplete state on the next inspection;
never leave a success record for partially copied output.

## Lock and failure boundaries

Hold an advisory `flock` on `~/.gemini/config/.cpp-skill-install.lock` for all
cooperating CPP AGY mutations, including future shared configuration writes.
Use a bounded wait with a reported timeout. Unsupported locking and an unreadable
lock are errors, not permission to proceed unlocked. Re-inspect the destination
after acquiring the lock because pre-lock observations can be stale. Do not hold
another harness's lock while waiting for this one. Staged publication and
cleanup remain within the selected root; no production mutation is part of the
research or local fixture lane.

Read-only verify never creates a root, lock file, staging directory or ownership
record. Open an existing lock file read-only without create/truncate flags and
take `LOCK_SH` for the inspection. A lock absent under a readable root does not
by itself stop verification; inspect existing content without creating it. If a
lock appears during that inspection, retry under the shared lock or report
`unknown` instead of claiming a stable unlocked snapshot. An unreadable lock,
unsupported locking or an exclusive holder exceeding the bounded wait gives
`unknown` (exit 4) for verify. These are not proof of absent or stale output.
Root absence with no selection remains `not-applicable`; selected missing output
remains `absent`. Verify never reconciles an ownership record.

The lock does not serialize native AGY CLI commands or other non-cooperating
writers. State that limit in acceptance. Two controlled cooperating updates to
different owned packages must both survive, with installed membership and bytes
checked afterward. Also exercise two cooperating refreshes of the same owned
package from distinct revisions: the resulting package must be exactly one
complete revision's membership, bytes and modes, with its matching ownership
record, never a mixture. The two runs may finish at different times; each run
verifies its own result while holding the lock, not a promise that a subsequent
valid refresh will never replace it. Valid JSON and successful exits alone do
not establish either concurrency result. Test interruption and lock failure
without claiming global cross-harness transactionality.

Failure is isolated by harness. Attempt the other selected harnesses after a
destination failure; do not roll them back to hide partial success. Preflight a
package's ownership/collisions before its mutation. If a refresh fails after a
write, verify and report the observed remaining state; do not imply whole-host
atomicity or a rollback that did not happen.

## Verification states and report contract

Use the ADR's inspection vocabulary. Keep state separate from action and
completion: a failed refresh can leave stale output; an unperformed verification
cannot be current.

| State | Meaning |
|---|---|
| `current` | Complete expected population was inspected and matched membership, bytes and modes |
| `stale` | Proven owned output differs from the fresh build and is eligible for refresh |
| `hand-edited` | Proven owned bytes/modes differ from their previous recorded installation |
| `unmanaged` | Present output lacks verified CPP ownership; automatic adoption is refused |
| `absent` | Selected expected output is missing, with a readable parent establishing absence |
| `not-applicable` | No installation was selected and none is managed; read-only helper exit 5 |
| `unknown` | Applicable evidence is unreadable, incomplete or unsupported; helper exit 4 |

The versioned machine-readable report and human summary name the same outcomes.
Each initial-harness row carries: harness, selection/evidence, bound source
revision, before state, action (`unchanged`, `refreshed`, `refused`, `failed` or
`not-attempted`), after state, verification scope/counts, reason and remedy.
For absent/unselected harnesses retain a row with an explicit reason. The report
names all three unimplemented follow-up harnesses and the command-derived AGY
invocation gap. Do not emit an all-harness success heading for this subset.

Aggregation is deterministic and independent of iteration order:

| Driver exit | Verdict |
|---|---|
| 0 | At least one selected initial harness; every selected harness verified current; coverage still PARTIAL |
| 1 | Any selected harness refused, failed or remained non-current after an attempted refresh |
| 2 | Invalid invocation; no mutation |
| 4 | Applicable result unknown/incomplete and no known failure taking precedence |
| 5 | No applicable selection and no discovery uncertainty; no mutation |

A known failure takes precedence over unknown; both remain visible in rows.
Missing/unreadable live-health evidence cannot be hidden inside `current`:
topic-file fidelity has no live-health verdict. Rules loading, MCP health and
receipt validity retain their own evidence scopes and later delivery issues.

## Acceptance and committed controls

These are future implementation acceptance cases, not tests run by this docs
change. Each new or changed load-bearing checker must ship committed good,
bad and unexaminable inputs under the
[ADR 0008 bound](../../../docs/decisions/0008-instrument-negative-control-bound.md).
Regression tests run red on pre-fix code. Assertions establish each negative
precondition before invoking the checker.

#1888/#1889-B AGY package fidelity cases belong in
`controls/antigravity-skill-install-fidelity`; #1890 rule-size and adoption
cases belong in `controls/antigravity-global-rules`, as named by ADR 0014. Those
directories and executable controls are delivered with their implementations,
not asserted to exist in this docs change. #1889-A delivers the harness-neutral
core's committed lock, verify-no-lock, same-package concurrency, prune, drift
and hand-edit-precedence controls through a fixture adapter root. They ship
with A, before real harness integration; they must not wait for B. A's plan
names their control directory and red cases. The detailed committed acceptance
inputs below bind A's real core through that fixture adapter, then B repeats
them through actual harness adapters where applicable. A fixture-adapter result
never establishes live AGY acceptance.

| Delivery | Positive case | Bad/unknown comparison |
|---|---|---|
| #1888 builder (`controls/antigravity-skill-install-fidelity`) | Fresh nonzero full topic set, valid portable references, deterministic output | Changed output, removed package, missing guide, escaping reference; unreadable source is unknown |
| #1888 Codex compatibility | Pre/post generator and real output match membership/bytes/modes | Deliberately changed transform makes parity fail |
| #1888 real AGY consumer | Install real built fixture skill, hide source, invoke in two unrelated repos; load nonce from bundled guide absent from prompt | Fresh session with missing skill/reference cannot recover nonce; unrelated same-name local guide cannot substitute |
| #1889-A discovery/revision | Fixture adapters receive one full revision independent of cwd/invoker | Foreign paths are not ownership; unreadable root is unknown; dirty/moving source cannot mix revisions |
| #1889-A fault isolation | One fixture adapter refreshes while another fails; actual driver report records both | Genuinely unwritable fixture destination, precondition proven by failed write; chmod under root alone is insufficient |
| #1889-A lock/prune | In fixture adapter roots, different-package updates both survive; same-package updates leave one complete revision and matching record; unchanged owned orphan pruned | Held lock times out; modified orphan preserved; interrupted publication is incomplete, never current |
| #1889-A read-only verify | Fixture installation without a lock verifies without creating one; tree remains identical | Unreadable lock or exclusive-lock timeout gives unknown; always-create-lock mutation fails the no-mutation case |
| #1889-A drift/precedence | Fixture bytes/modes/member inventory match fresh build; explicit record-only reconciliation works | Missing+edited mixture preserves per-member conflicts; hand-edited beats stale; zero validated and always-current mutation fail |
| #1889-B discovery/integration | Real Claude/Codex/AGY adapters are selected independent of invoking harness/cwd | CLI-only/foreign directory is not ownership; fixture-only success cannot count as real adapter coverage |
| #1889-B1 real-adapter revision | Real Claude TOPIC/Codex/AGY copy adapters receive and report the SAME full revision in one shared invocation | A different or guessed adapter revision fails; B2 separately exercises maintained cpp/update and owner-approved Claude links |
| #1889-B stale host update (`controls/antigravity-skill-install-fidelity`) | Current checkout, stale managed Codex and AGY copies both refreshed; foreign sibling bytes retained; A's core controls repeated through AGY adapter | Missing member and tampered bytes fail fidelity; unexpected internal file and unmanaged same-name target survive/refuse |
| #1889-B fault isolation | Real other selected harness refreshes while one fails | Destination genuinely unwritable by executing identity, precondition proven by failed write; summary identifies actual failure |
| #1890 rules (`controls/antigravity-global-rules`) | Within-limit rule loads completely including its tail marker | Oversized actual build/install bytes rejected; unmanaged/hand-edited rules preserved |
| #1892/report consumers | Actual installed trees and real driver report feed drift/status readers | Always-current mutation fails; zero validated, unreadable input and partial reports cannot pass |

### #1889-A committed acceptance input: verify-no-lock

This is a fixture specification for #1889-A, not an executed probe. Create a
fixture-owned readable adapter root containing a valid managed fixture package
and its matching ownership record, plus a foreign sibling. The fixture adapter
defines its exact lock location inside its permitted scope; no AGY installation
is required. Assert that the lock does not exist, and capture complete relative
membership, file hashes and modes of that scope before verification. Invoke the
real core read-only verifier through the fixture adapter. Expect `current`, the full nonzero
package count, no lock file afterward, and identical membership/hashes/modes
including the foreign sibling and ownership record. Verify must also succeed
on the same readable tree made unwritable to the executing identity; establish
that precondition with a failed write. A verifier changed to create the lock
must fail this case. Companion inputs hold an existing exclusive lock past the
deadline or make an existing lock unreadable; each must report `unknown` and
leave the tree unchanged. #1889-A commits these materialized inputs and executable
assertions alongside the core and fixture adapter, and demonstrates the mutation
red. #1889-B repeats them against the actual AGY adapter's configuration root and
`.cpp-skill-install.lock` path in its committed fidelity controls.

### #1889-A committed acceptance input: concurrent-same-package

Prepare two valid immutable source revisions with distinct bytes in at least
two owned members of the same slug and distinct revision-bound ownership
records in a fixture adapter root, without AGY-specific discovery. Assert those
differences. Start two real core cooperating refreshes through that adapter with
controlled overlap at lock acquisition. After both exit, compare the entire
package and record against each expected build: exactly one complete build and
its matching record must match. No combination of members from both revisions
is acceptable. Repeat the schedule in both lock-acquisition orders. The paired
different-package case requires both intended updates to survive. #1889-A's
committed core controls must reject a deliberately interleaved unlocked copy
that produces a mixed package or a record from the other revision. #1889-B
repeats the schedules through the actual AGY adapter's fidelity controls.

Live AGY work uses only the isolated probe profile via the approved host helper,
with exact short commands and undo reviewed before execution. Never copy
credentials or read transcripts. A mocked CLI or a list response is not a real
AGY invocation. No live AGY tests run inside this container.

## Readers, lanes and remaining premises

This documentation change alters no executable output. Its readers are the
#1888/#1889 implementers and their reviewers; it specifies the later writer /
reader pairs rather than claiming to exercise them. The later implementation
plan must feed real generated packages to its installer and actual installed
bytes to its verifier/status readers. Command/procedure changes also require
reading their generated Codex mirrors. Runtime evidence readers stay in #1886.

Lanes for this change: none - documentation only. The implementation cases
above name root/external cwd, checkout/worktree, invoking-harness and host
consumer boundaries; later plans answer the repository's full lane table and
state untested live paths. Native Codex authoring is not AGY product evidence.

[Research and provenance](research.md) records the attributed B0-B4 evidence,
paired controls and unresolved premises, including the 2026-11-25 sanitized
manifest's server-side MCP call records. No unpublished archive has been
independently inspected by this author. Exact rules target/loading design,
aggregate rule-token behavior, complete hook history and shipped live-health
checks remain with their named later deliveries. Missing historical argv,
prompts and artifact byte correspondence remain visible #1887 evidence gaps;
a specification does not turn them into measurements.


## B2a Claude link component boundary

Under ADR 0014's owner-ruling amendment, existing Claude command-family and
helper links use a typed `links` backend. Topic/Codex/AGY copies retain the
copier's symlink refusal. Production schema 2 has four component rows with
explicit per-row `copies` or `links` labels and one common full revision.
Source fidelity and the persistent clean link target are independent of the
private execution snapshot. Exact installed name and CPP source prove ownership;
foreign replacements and mixed farms survive, and unknown orphan history never
authorizes deletion. Command/helper kinds enroll independently, without a tier
upgrade. Verify creates nothing and refresh holds the existing Claude lock.
The confined positive and outside/dangling/regular-replacement controls are
committed before the backend ships. Link counts describe entries plus tracked
source members, not native effectiveness.

B2a does not wire maintained `/cpp:update`, change Codex command attribution or
run a native probe. Those are B2b, whose PR follows B2a merge. Initial coverage
remains PARTIAL and #1889/#1876 remain open for their remaining acceptance.
