# Flow run record - issue #1889

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=b9ec164e15eb4b14826b3f2a0d09dc16 -->
## Run 1

- Run-id:            b9ec164e15eb4b14826b3f2a0d09dc16
- Run-start:         790174a3f3994c5433429ddf8df6fe3296762ce9
- Issue:             #1889, delivery A only
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          ch-orch mailbox 39939, approving Section C at b88e35a7

### Section A - intent

CPP currently has separate installation procedures, so adding another coding
tool would otherwise duplicate the rules that protect a user's installed files.
That duplication makes it easier for one installer to overwrite personal
content, miss changed files or report success after only part of an update.
This delivery creates the common copying and checking machinery, exercised with
disposable test adapters. Actual Claude, Codex and AGY installation wiring comes
later; pi can build its adapter against the agreed common interface.

### Section B evidence

Issue created 2026-11-22T12:04:41Z. Relevant post-filing commit inspected:
790174a3 (#1906 contract); main also includes 9af6d361 (#1898 pi plan) and
458ee7c1 (#1895 accepted ADR). Merged PR search since 2026-11-21 additionally
returned #1885, #1884, #1883, #1882, #1881, #1880, #1879, #1878, #1874, #1873,
#1872, #1870 and #1869; these concern drivers/release/review, not this core.
Scoped lib/new-core history since filing found only the contract change.
Related issues inspected/considered: #1876, #1887, #1888, #1889, #1890, #1891,
#1892, #1896, #1900 and #1901. None supersedes the neutral core. #1900 is the
future pi shared-updater adapter, not authority to enroll pi now.

The original issue body still describes the combined AGY updater. The approved
order on #1889 comment 7168491284 reframes delivery as A (neutral core), #1888
(builder), then B (real adapters). #1889 remains open through B. This is the
remaining work authorized now; no issue-body edit is planned.

Host: two CPP worktrees listed, the completed #1887 branch and this fresh
main-based worktree; no unpushed relevant implementation exists here. Other
machines' unpublished work is unexamined. Existing codex-skill-sync.py install
and lock code and tests were read as precedent, not as an extraction target.
The generator must remain byte-identical.

### Section C - the approved plan

1. `lib/host_update/__init__.py` - export the small neutral adapter/core API.
2. `lib/host_update/models.py` - immutable revision, expected package/member, ownership record, per-member conflict, inspection/action/result and report types; closed states and deterministic aggregation.
3. `lib/host_update/scope.py` - adapter-approved source/install/ledger/lock/staging boundaries; lexical and no-follow path validation before enumeration, descent or mutation; regular-file/mode policy.
4. `lib/host_update/store.py` - installed inventory/hash/mode comparison, bounded flock, noncreating shared-lock verification, staged copies, record publication, explicit record-only reconciliation, owned-only orphan pruning and interruption evidence.
5. `lib/host_update/driver.py` - discover/select through adapters, bind one revision and fresh expected manifest, preflight before IO, refresh/verify sequencing and independent outcome aggregation; no built-in production harness discovery.
6. `lib/host_update/fixture.py` - explicit disposable fixture adapter exercising the real core; no default host paths, credentials or CLI-presence inference.
7. `scripts/cpp-host-update.py` - thin fixture-only driver entry for refresh/verify and versioned JSON/human reports; no production adapter enrollment in A.
8. `tests/test_host_update_core.py` - real expected output to inventory/verification; state precedence, zero-population and malformed/unreadable ownership; foreign/collision/symlink preservation; report and aggregate exit assertions.
9. `tests/test_host_update_transactions.py` - real subprocess lock contention, no-lock no-write, lock appearance, interruption, same/different-package concurrency, pristine orphan pruning versus edited/unexpected content; prove all negative preconditions.
10. `tests/test_host_update_cli.py` - actual CLI/core report reader, multi-adapter fault isolation, source-revision mismatch, root/external cwd and checkout/worktree shapes; unsafe descriptor/path refusal before forbidden reads.
11. `controls/host-update-core/control.json` - register the load-bearing core CLI with GOOD/BAD/UNKNOWN cases and a declared blindness anchor.
12. `controls/host-update-core/run-case.py` - materialize fixture-owned source/install trees from committed case inputs, assert preconditions and invoke the actual CLI; print its verdict/exit, never substitute an expected answer.
13. `controls/host-update-core/anchors/constructed-always-current.py` - explicitly constructed blind anchor that reports current, demonstrating the controls fail against a blind implementation.
14. `controls/host-update-core/cases/good-current/case.json` - complete nonzero owned expected/installed population.
15. `controls/host-update-core/cases/bad-stale/case.json` - unchanged prior recorded bytes differ from new expected build.
16. `controls/host-update-core/cases/bad-missing-member/case.json` - nonempty expected package with a missing installed member.
17. `controls/host-update-core/cases/bad-hand-edited/case.json` - member differs from both previous record and fresh output, including missing+edited conflict mix.
18. `controls/host-update-core/cases/bad-unmanaged-collision/case.json` - foreign same-name target retained/refused.
19. `controls/host-update-core/cases/unknown-lock/case.json` - existing exclusive lock exceeds verify deadline, yielding unknown without writes.
20. `controls/host-update-core/cases/good-no-lock/case.json` - complete readable installation with no lock; verify leaves exact tree membership/bytes/modes unchanged.
21. `controls/host-update-core/cases/bad-modified-orphan/case.json` - previously owned orphan with changed or unexpected member must survive and be reported.
22. `controls/host-update-core/cases/good-prune/case.json` - unchanged manifest-proven owned orphan pruned without touching a foreign neighbor.
23. `Makefile` - focused core test/control targets and fixture-only refresh/verify entry targets; integrate core control into existing verification interfaces.
24. `docs/scripts.md` - one inventory entry for the new CLI.
25. `docs/scripts/cpp-host-update.md` - exact CLI/report/exit/ownership contract, fixture-only scope, lock semantics and adapter integration API.
26. `controls/census.md` - register core verifier/driver instrumentation and evidence limits.
27. `.claude/verify-coverage.json` - account for the new CLI through its focused test/control/Make readers.
28. `changelog.d/1889.md` - delivery-A fragment with real-adapter work still open.

Scope: Tier 3, approximately 28 product/test/control/docs paths plus this plan,
as-read snapshot and later lane-results/receipt records; roughly 1800-2600 lines.
Approval conditions (ch-orch 39939): freeze and push the models/driver/adapter
callback interface in its own early commit before store/driver internals, notify
ch-w2 and ch-orch of its full SHA, and notify ch-w2 before later API changes.
Subprocess lock/concurrency tests use bounded waits and explicit synchronization,
never sleeps, assert negative preconditions first, and run repeatedly locally
before review. Leave codex-skill-sync.py byte-identical; its historical parity
test belongs to #1888, not A.

Paths may be revised through the existing
plan-change procedure if a control requires an additional committed seed.

Risks: path checks must precede forbidden-root touches; symlinks/races and
partial publication must never produce a clean ownership record. A ledger can
live outside a discoverable package, so package/ledger publication needs an
explicit incomplete state, not a false atomicity promise. Advisory locks protect
only cooperating writers. Fresh-build-equal bytes with a stale valid record need
the specified refresh-only exception. Physical fidelity does not establish
which skill a runtime selects in a particular cwd/trust context.

Challenge to approach: placing JSON in every package would violate pi's
Markdown-only package policy. The adapter therefore chooses an allowed ledger
location outside discoverable packages; no fixed pi hidden directory is assumed.
Exposing only fixture adapters in A avoids premature production discovery or
enrollment while still exercising the same real copier/verifier/report pipeline.

### Core interface proposed for coordination

- `Adapter.preflight(request)` returns a validated policy before core inventory,
  root walking, realpath descent, lock creation or staging. Core still validates
  relative members and refuses symlinks/traversal; callbacks cannot waive scope.
- `Adapter.discover(policy)` returns explicit managed/selected/absent/unknown
  evidence. `Adapter.build(revision, policy)` returns immutable expected package
  manifests and content from an approved source snapshot.
- `Policy` names permitted install/source scopes, package member/mode rules,
  ledger location, exact lock and permitted staging/backup cleanup roots.
  Pi's Markdown-only/0644 and all-history-candidate exclusions belong in its
  adapter/build policy, not in global defaults.
- `OwnedMember` carries relative path/SHA256/mode. `OwnershipRecord` carries
  producer/schema/source/revision/package/member inventory. Installed content
  is rehashed; a marker alone grants no deletion/adoption authority.
- `inspect(adapter, request)` never creates locks or records. `refresh(...)`
  uses an exclusive lock, re-inspection and verified publication. Both report
  per-member conflicts. Lock appearance during unlocked verify retries SH or
  yields unknown. Native adapter refusal reasons remain separate from aggregation.
- `run(adapters, request)` resolves one revision, isolates per-adapter failures
  and renders schema-versioned reports. Installed fidelity is a separate field
  from contextual runtime effectiveness, which defaults to unexamined/unknown.
  Standalone pi may use the core without joining the shared-driver registry.

### Evidence and control plan

A ships committed controls for drift/missing/edited/collision/unknown inputs
plus live fixture-adapter lock/no-lock/concurrency/prune/precedence tests. Bad
cases assert their defining preconditions before core execution. The no-lock
case compares full membership/hashes/modes before/after; its bad mutation creates
a lock. Concurrent same-package runs must leave exactly one revision and matching
ledger; an intentionally unlocked interleaved copy must fail that assertion.
Prune's bad mutation deletes a modified/foreign member; precedence's bad mutation
overwrites a hand edit. Controls exercise real core outputs and detect these
mutations, not just process exits. No pre-fix regression claim is made for a new
core; existing-function regression cases, if introduced, must run red pre-fix.

Use focused Make targets locally first, then the paired self-supervised finish
gate and ch-rev runtime receipt at the committed checkpoint. Full-suite work
uses the gate's own renewing supervisor. PR CI only; PR window requires ch-orch
clearance. No AGY/pi live CLI, credentials, production configuration or generator
edits in A. Tests reaching git/bash or another real binary carry explicit
`shutil.which` guards. Existing Codex baseline notes remain with #1888 (Nit comments
7168402700/7168403197); real-adapter same-revision acceptance remains B (canonical
Nit comment 7168730806). The contract's original core-control allocation Nit is
fixed, not an exemption from A controls.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | main checkout / linked worktree through actual CLI in fixture repos; source revision/dirty checks |
| Harness | not covered | Claude install / Codex install and AGY/pi runtime adapters are B/later work; A uses fixture adapters only |
| Driver | not applicable | shared library/CLI, no flow:auto or delegated-driver instruction change |
| Coordination | not applicable | product flock is local adapter coordination, not Kyle scheduling; validation itself uses Kyle supervisor |
| CI provider | not applicable | no provider-selection behavior changed; PR CI is Woodpecker, no GitHub Actions execution claim |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not; managed, unmanaged, selected absent and unselected not-applicable fixtures |
| Toolchain version | not covered | installed host and pinned PR CI only, no added version matrix |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone; valid pinned source vs unavailable revision unknown |
| Run location | will test | invoked from the CPP root / from another directory with identical explicit request and result |
| Gate target | not applicable | core install inspection, no consumer quality-gate runtime/PATH change |
| Wave role state | not applicable | no role state or mailbox registry changes |
| Reader: fixture CLI | tested against real output | CLI consumes actual adapter/core result objects, not hand-written report copies |
| Reader: control harness | tested against real output | committed fixture cases invoke actual CLI and inspect its report/verdict/exit |
| Reader: pi adapter | not covered | coordinates the API proposal now; P1-A real consumer test belongs to ch-w2, not claimed delivered by A |
| Reader: Claude/Codex/AGY adapter/status/drift | not covered | integration deferred to B/#1892/#1893; wire real outputs there |

Reader search: known existing Makefile reader of codex-skill-sync.py found
first as a positive search control. New module/CLI has no existing implementation
to search; the future readers above are known from the approved contract and
pi-worker coordination. No cross-repository interface change or new capability
enrollment is claimed. Lane file is fresh (11 days old at plan preparation).

<!-- flow-run n=2 id=cbff69dcdd074f20b794f98166080f42 -->
## Run 2

- Run-id:            cbff69dcdd074f20b794f98166080f42
- Run-start:         12b39ceb146dc89860be036e577ae248e362a19d

- Issue:             #1889, delivery B1; B2 is deferred below; parent #1876
- Necessity verdict: Needs reframing (the combined issue is staged A/B1/B2)
- Plan status:       PROPOSED revision 2; awaiting ch-orch approval

### Section A - intent

The neutral updater and AGY builder are merged, but the shared CLI still only
accepts disposable fixture adapters. B1 adds real Codex and AGY copy adapters
and Claude TOPIC managed copies to the core. One invocation at a current
checkout refreshes those managed installations from one full CPP revision,
preserves a personal sibling skill and reports each result independently.
A failure at one destination must not stop the other selected installations.

B1 is explicitly PARTIAL, including only Claude topic copies, Codex generated
skills and AGY topic copies. Claude commands/helpers and maintained cpp/update
wiring are B2 under the owner's documented link exception below. pi, Qwen and
Gemma/OpenCode are follow-up adapters. No initial subset establishes all-harness
or workflow parity. #1889 remains open through B2; the epic cpp/update
acceptance is not completed by a standalone B1 CLI test.

### Section B evidence

Base main is 12b39ceb146dc89860be036e577ae248e362a19d (#1909), with neutral
core adf70c29 (#1908), contract 790174a3 (#1906), accepted ADR 0014 and pi
packaging #1907. The current CLI requires --fixture-root; no real production
registry is present. Inspected #1889/#1876, approved order comment7168491284,
contract, existing Claude/Codex helpers, shared core and AGY builder. Scoped
post-filing history found the core, not production adapters. Related rules,
MCP, drift/status/planner and runtime receipt work remain #1890/#1891/#1892/
#1893/#1886. No issue-body edit is proposed; #1888 stays open after merge.

Initial draft d5a16eec was plan-only, not approved. Orchestrator review40522
approves (2) legacy migration and (3) Codex input attribution, and requires a
B1/B2 split. The owner then ruled "1889 A" (1889 comment7178523792; relayed40530):
existing Claude command/helper links stay links as a typed, bounded, verified
Claude-only exception; topic skills and new harnesses remain copies. The
required ADR0014 amendment must land FIRST in its own docs-only PR0, before
B1/B2 code. B1 still makes NO link/backend/core-callback change. The three
stages are PR0 amendment, B1 copy adapters, then B2 maintained invocation and
Claude links. This revision records that ruling; no earlier interpretation is
standing authorization to weaken copy-core symlink refusal.

Fresh branch issue-1889-shared-adapters in
/workspace/claude-power-pack-adapters is based on main12b39ceb. Only this draft
plan is changed. Other local worktrees hold completed contract/core/builder
and historical probes; other containers' unpublished work is unexamined. The
owner host and CPP pin are untouched. Assignment40515; revision request40522.

### PR0 prerequisite - docs-only, lands before B1 code

A separate branch from current main changes only
`docs/decisions/0014-antigravity-capability.md` plus its own plan/as-read/review
records. Its short AMENDMENT records the owner ruling, existing Claude command
and helper scope, targets confined inside the pinned CPP checkout, no new link
kinds, read-only type/target/content verification and required negative cases.
It requires reports to call the backend `links`, never `copies`. PR0 lands
before code. This B1 draft will reconcile with PR0's approved plan history
before its own approval stamp; no historical approved section is overwritten.

### Section C - B1 proposed plan for approval

1. `lib/host_update/source.py` - resolve a full commit once, refuse dirty/unavailable source and materialize a private detached source snapshot with Git overrides/hooks/fsmonitor disabled; use its driver/adapters/builders and clean only the owned temporary worktree.
2. `lib/host_update/claude.py` - actual Claude TOPIC managed-copy adapter only, building pinned canonical packages under the existing metadata.source fidelity contract; no commands/helpers, symlink allowance or configuration enumeration.
3. `lib/host_update/codex.py` - actual Codex managed-copy adapter using the unchanged pinned generator and existing install lock; GENERATED is discovery evidence, not proof of previous installed bytes.
4. `lib/host_update/antigravity.py` - actual topic-only AGY adapter consuming the merged builder; descriptor-relative no-follow preflight from approved home through .gemini/config before granting skills/ledger/work and the exact config/.cpp-skill-install.lock scope.
5. `lib/host_update/host.py` - production registry/selection, same-revision dispatch through the existing core and typed PARTIAL report envelope naming copy components, absent/unknown states, unsupported harnesses and deferred Claude command/helper links/B2 invocation.
6. `scripts/cpp-host-update.py` - production refresh/verify entry with explicit source/home/selection/defer/adoption boundaries, HOST-SURFACE declarations and real human/JSON summaries; retain backwards-compatible explicit fixture mode.
7. `tests/test_host_update_adapters.py` - real discovery and pinned builds for all three copy adapters; metadata/GENERATED/receipt versus CLI-only/foreign evidence; legacy exact-match record bootstrap and stale-unproven UNKNOWN; no-follow prefix refusal BEFORE forbidden IO; actual Claude output consumed by the existing skills-check reader.
8. `tests/test_host_update_integration.py` - actual CLI and real three-adapter refresh from prior A to current B, exact SAME full revision in all selected rows, independent fresh-build/installed bytes/membership/modes and foreign sibling preservation; a different/guessed-revision adapter must fail.
9. `tests/test_host_update_permissions.py` - prove a destination unwritable by the actual executing identity with failed writes before invocation; remaining real adapters refresh and summary identifies failure; root uses a dropped-identity child rather than chmod-only proof.
10. `tests/test_host_update_adapter_transactions.py` - A's held-lock/no-lock/prune/interruption and controlled same/different-package schedules through the actual AGY adapter, both lock orders, complete build/record comparison and unlocked mixed-output mutation.
11. `tests/test_host_update_ci_shape.py` - real production entry from full/shallow/detached fixture-owned histories created under022/000 and root/external cwd; source move/unavailability refusal, stderr diagnostics, no dependency on mutable outer-CI transport/history.
12. `controls/antigravity-skill-install-fidelity/control.json` - register real production adapter fidelity with GOOD/BAD/UNKNOWN cases and mutation evidence.
13. `controls/antigravity-skill-install-fidelity/run-case.py` - materialize committed disposable sources/homes, assert negative preconditions and invoke the real production CLI/report/tree; no native model or production host mutation.
14. `controls/antigravity-skill-install-fidelity/anchors/constructed-always-current.py` - declared blind implementation which misses the BAD fidelity inputs.
15. `controls/antigravity-skill-install-fidelity/cases/good-current/case.json` - complete nonzero real managed output population.
16. `controls/antigravity-skill-install-fidelity/cases/good-refresh/case.json` - stale Codex/AGY plus Claude topics, common revision and byte-identical foreign sibling.
17. `controls/antigravity-skill-install-fidelity/cases/bad-stale/case.json` - proven owned stale bytes detected by verify.
18. `controls/antigravity-skill-install-fidelity/cases/bad-missing-member/case.json` - missing required bundled guide with nonzero expected floor.
19. `controls/antigravity-skill-install-fidelity/cases/bad-hand-edited/case.json` - edited bytes/modes preserved, including mixed missing/edited conflicts.
20. `controls/antigravity-skill-install-fidelity/cases/bad-foreign-content/case.json` - internal foreign member or same-name unowned target preserved/refused.
21. `controls/antigravity-skill-install-fidelity/cases/bad-revision/case.json` - wrong/guessed adapter revision cannot produce shared current.
22. `controls/antigravity-skill-install-fidelity/cases/unknown-lock/case.json` - held/unreadable exact lock produces unknown without mutation.
23. `controls/antigravity-skill-install-fidelity/cases/good-verify-no-lock/case.json` - verification with absent lock leaves full tree unchanged; always-create-lock mutation fails.
24. `Makefile` - focused adapter/integration/permission/transaction/CI-shape/control targets and shared production refresh/verify targets; retain explicit fixture targets, no independent AGY updater.
25. `controls/census.md` - real production fidelity claims and evidence limits, retaining fixture core registrations.
26. `.claude/verify-coverage.json` - shared production CLI/Make/control coverage without exempting changed gate behavior.
27. `docs/scripts/cpp-host-update.md` - production copy-adapter roots/locks/selection/migration, report/exit contract, exact PARTIAL scope and no live-effectiveness claim.
28. `docs/scripts.md` - update the existing shared-entry inventory description.
29. `.specify/specs/antigravity-host-update/spec.md` - restore the B real-adapter same-full-revision acceptance row from Nit7168730806, explicitly identifying B1 topic/copy subset and negative wrong-revision case; maintained invocation remains B2.
30. `docs/measurements/host-update-adapters.md` - actual B1 acceptance/lane/permission/CI-shape/lock evidence, include nonzero real-adapter population and explicit B2/live gaps.
31. `changelog.d/1889.md` - append B1 copy-adapter delivery and limitations without erasing A or claiming B2/epic completion.

Scope: B1 only, approximately31 named paths including12 small control paths,
plus this plan/as-read/demonstrated record and later review receipt. Target
1500-2200 implementation/test lines by reusing the existing core unchanged.
NO models.py/driver.py/scope.py public API change, link backend, command-doc
change, Codex baseline edit, native probe or live model run in B1. Extra paths
or scope expansion require the existing plan-change procedure. Approval is
pending; no product implementation has begun.

### B2 future list - NOT B1 implementation authority

The exact B2 Section C will be approved in its own run after PR0 and B1; this list records the split rather than pre-approving future code.

1. `.claude/commands/cpp/update.md` - invoke shared production refresh once after source fetch, including zero commits pulled, and preserve actual per-harness failures in summary; replace duplicated refreshes only within the owner-approved component scope; budget offsets/instruction audit.
2. `lib/host_update/claude.py` - existing command/helper links under the owner-approved narrow exception; topics remain copies and the report preserves component backend labels.
3. `lib/host_update/models.py` - additive typed lifecycle/backend seam for the owner-approved Claude exception, default copy API unchanged, coordinated with ch-w2 before any change.
4. `lib/host_update/driver.py` - corresponding bounded shared lifecycle extension for Claude links; never globally weaken copy-core symlink refusal.
5. `lib/host_update/links.py` - typed bounded Claude-only backend after PR0 lands; verify targets resolve inside the pinned CPP checkout, no new link kinds, preserve/report foreign, dangling and non-link replacements.
6. `tests/test_host_update_command.py` - maintained Claude and generated Codex command readers consume actual production outputs, including no-op source pull, CLI absent and partial failure; no authored report substitutes.
7. `tests/test_host_update_links.py` - owner-required committed outside-checkout, dangling-link and regular-file-replacement negatives; preservation, defer/host-write seam, source-content/revision and interruption evidence.
8. `controls/antigravity-skill-build/codex-baseline.json` - only reviewed source-driven input attribution for cpp/update, historical members and generator/parser pins unchanged.
9. `tests/test_antigravity_codex_parity.py` - consume the same attributed source delta under both masks, preserve exact independent generator/parser output bytes/modes and reject an unattributed input change.
10. `docs/measurements/host-update-acceptance.probe.py` - NEW gated optional native probe, separate from immutable historical attempt4: require a recorded governing ruling reference bound to the reviewed run in BOTH authentication lanes, including prescribed dedicated file-token setup; no auth-store reads/copies or automatic login.
11. `tests/test_host_update_probe_gate.py` - committed missing/stale/wrong-head ruling and absent-auth preconditions refuse BEFORE native callbacks; removed-gate mutation reaches forbidden callback and fails; no claim of real AGY consumer coverage.
12. `docs/scripts/cpp-host-update.md` - maintained invocation/owner-ruling scope, credential/configuration isolation limits and explicitly unimplemented follow-ups.
13. `docs/measurements/host-update-adapters.md` - B2/epic real-adapter acceptance and owner-approved live evidence if any; otherwise name missing runtime/command-derived AGY invocation.
14. `Makefile` - necessary focused B2 tests/controls under the same shared updater, no bespoke per-AGY update workflow.
15. `changelog.d/1889.md` - describe final approved B2 scope without turning PARTIAL into all-harness parity.
16. `lib/host_update/host.py` - component/backend report labels: Claude command/helper backend is `links`, NEVER `copies`; Claude topics/Codex/AGY remain copies, including mixed-component summaries.

### B1 decisions and preservation policy

Decision2 is approved by ch-orch40522: legacy markers prove ownership discovery,
not complete old installed bytes. Existing valid core manifests allow stale
refresh. A legacy copy that exactly matches the whole fresh build may bootstrap
a record without changing package bytes. Stale legacy output with no verifiable
prior manifest stays UNKNOWN and preserved, with explicit reviewed adoption
and recoverable-backup remedy. Do not snapshot observed hand edits into a
purported prior-build record. A marker-only spoof or CLI presence cannot enroll
an installation. Unselected missing roots are never created.

All adapters retain the default regular-file core; symlinks are refused. AGY
preflight opens user-controlled .gemini and config prefixes no-follow from the
approved home anchor BEFORE inventory, source build, lock creation or descent.
Use forbidden-read sentinels for aliases above skills. An allowed system alias
above the approved home anchor does not authorize config aliases. Claude
credentials/settings and AGY configuration/auth roots are not enumerated.
Existing defer-set/manager-owned surface rules remain boundaries, not a reason
to silently write or claim a skipped destination current.

One desired full commit is resolved once; private detached source material
supplies that revision's driver/adapters/builders. Every selected real adapter
receives/reports it, including failed rows. Source failure yields not-attempted
rows for every selected adapter; no guessed revision or independent adapter
pull. Codex generator bytes/CLI and historical baseline stay unchanged in B1.
The B2 source-delta attribution decision is approved in40522, not exercised
prematurely here. Existing pi/fixture API readers remain compatible without a
public API extension; notify ch-w2 before proposing any later change.

The #1888 CI clone cause remains UNPROVEN. Tests construct owned source histories
from committed input instead of cloning a concurrently deepening outer CI
checkout. Pre-CI checks exercise shallow HEAD-only sources and creation under
umask000 as well as022. Host uid1000 is not a root emulation. Root-only dropped
identity cases are conditional on actual privilege and otherwise reported as
untested, never replaced with chmod-under-root evidence. Capture Git stderr.

Locks protect cooperating CPP operations, not direct native or older
noncooperating writers. Reuse the Codex install lock to coordinate with the
legacy installer, but do not claim old writers maintain the new ownership
ledger. B1 does not run any native model. The old attempt4 probe/ruling are
historical only; any later probe must enforce the recorded-ruling launch gate
(Nit7176769364) before a new owner-approved run. The dedicated auth lane must
also record its governing authorization; no credential reads/migration.

### Evidence and control plan

Actual adapters, not FixtureAdapter, install prior revisionA into a disposable
home. Change the owned source toB and invoke the actual shared CLI once. Claude
topic copies, Codex skills and AGY topics must all report the same fullB commit
and match independently built expected membership/bytes/modes. The committed
wrong-revision input must fail and assert its discrepancy before the reader.
A current checkout with stale installations is a required positive case. A
foreign sibling skill retains its exact membership/hashes/modes. This is B1
file acceptance, not the maintained cpp/update/epic invocation promised by B2.

For failure isolation, establish the exact CLI identity and a genuinely failed
write to one selected destination BEFORE refresh, then show other selected
adapters refreshed and both JSON/human summaries identify the failed one. With
uid0, drop identity in a dedicated child whose fixture source is readable.
Readable but unwritable verification must not create a lock/root/record or
repair metadata. Missing/edited/internal-foreign and orphan cases assert their
negative preconditions and preserve unexpected content.

Repeat A's bounded lock/no-lock/interruption/prune/same-package schedules
through actual AGY paths. Different-package changes both survive; same-package
A/B schedules in both lock orders yield exactly one whole build and matching
record. Deliberately unlocked mixed output, unsafe pruning, mode/byte blindness
and always-create-lock mutations must be rejected. Commit GOOD/BAD/UNKNOWN
inputs and show the declared always-current anchor misses every BAD case.

Run focused Make targets and CI-shape cases before review/PR CI; use direct
self-supervised finish gate for the required full make verify. Reuse existing
core/AGY/parity tests rather than rewriting the core. Regression claims run red
on predecessor code. Normal formal review cap is2, not #1888's scoped cap7.
PR creation/CI needs ch-orch clearance, one AGY PR in flight and Kyle series
priority. No native consumer or production host mutation is authorized by this plan.

### Lanes for B1

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | real production CLI from checkout/linked worktree and private detached source snapshot |
| Harness | will test | real Claude TOPIC copies, Codex generated copies and AGY topic copies in disposable homes; commands/helpers deferred |
| Driver | not covered | maintained cpp/update and its Claude/Codex command routes are B2; B1 actual standalone shared CLI only |
| Coordination | not applicable | local advisory locks, no Kyle-dependent product branch; heavy validation uses gate supervisor |
| CI provider | not applicable | no provider-selection change; PR CI Woodpecker only |
| Project state | will test | managed, explicit selected absent, unselected absent, foreign-only, legacy exact/current and stale-unproven |
| Toolchain version | not covered | installed host and pinned CI only, no added version matrix |
| Clone shape | will test | fixture-owned full, shallow HEAD-only and detached histories; unavailable source unknown |
| Run location | will test | CPP root and unrelated invoking repository give same adapters/revision/results |
| Gate target | not applicable | installation fidelity, not quality-gate interpreter/PATH routing |
| Wave role state | not applicable | no mailbox registry/role behavior |
| Reader: real copy adapters/core | tested against real output | actual pinned builds feed actual core; integration inspects installed bytes/membership/modes |
| Reader: production CLI/report/control decisions | tested against real output | real reports and trees, no independently authored JSON substitutes; blind anchor/mutations |
| Reader: Claude skills-check | tested against real output | actual managed Claude topic output fed to unchanged existing checker |
| Reader: fixture and pi API | reader unchanged | core types/default callbacks and fixture schema preserved; rerun actual existing consumers |
| Reader: cpp/update/generated command routes | not covered | B2 wires actual reports under the recorded owner exception after PR0/B1; no parallel updater claimed |
| Reader: drift/status/capability planner | not covered | existing readers not switched; #1892/#1893 integrations retain own acceptance |
| Reader: AGY runtime | not covered | no native model run; recorded-ruling probe gate is mandatory before any later live acceptance |
| Reader: Kyle/skillc/kyle-candidate | reader unchanged | Codex generator and canonical command inputs unchanged in B1; existing independent parity suite remains required |

Reader search positive control found existing cpp/update:2042 and Makefile
codex-skill-sync install/build callers; scoped searches found core CLI fixture
consumers, AGY builder/core, skills-check/install-drift topic readers and
HOST-SURFACE checks. Cross-repository private consumers were not searched.
B2 will account explicitly for changed command-doc Codex input; B1 does not
change it or silently re-pin historical output evidence. An unexpected bundled
source delta found by the B1 parity test requires explicit attribution and a
plan-change approval before touching its baseline/delta records.
