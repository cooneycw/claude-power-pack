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

- Issue:             #1889, delivery B only; parent #1876
- Necessity verdict: Needs reframing (the combined issue is now delivery B)
- Plan status:       PROPOSED; awaiting ch-orch approval, not implementation authority

### Section A - intent

Updating the CPP checkout does not currently refresh all of its installed
surfaces. The Claude procedure repairs links in separate steps, Codex updates
only when its CLI is found, and AGY has a builder without a host adapter. This
delivery connects the three initial harnesses to one discover, refresh, verify
and report operation. An unchanged checkout must still repair stale managed
copies. A personal skill stays untouched, and a failure at one destination must
not prevent the other selected installations from refreshing.

Coverage is explicitly PARTIAL: Claude Code, Codex and AGY. pi, Qwen and
Gemma/OpenCode remain follow-up adapters under #1876/#1889. Command-derived AGY
skills and a real AGY cpp-update invocation remain separate follow-ups; native
topic loading does not establish workflow parity or #1886 runtime evidence.

### Section B evidence

Main is 12b39ceb146dc89860be036e577ae248e362a19d (#1909). Prior prerequisite
adf70c29 (#1908) supplies the neutral core; 790174a3 (#1906) supplies the
contract; 458ee7c1 accepted ADR 0014. Main also contains pi packaging #1907,
which is not enrollment in this shared driver. Post-filing scoped history for
lib/host_update and the maintained cpp/update procedure found the core merge,
not production adapters. The current core CLI still requires --fixture-root.
The #1889 body, #1876 body, approved Wave 1 order (1889 comment 7168491284),
contract, ADR, existing install helpers and reader locations were inspected.
No issue-body edit is proposed. #1888 stays open after its merge.

Known related boundaries are #1886 runtime receipts, #1890 rules, #1891 MCP,
#1892 drift, #1893 capability/init/status and #1894 broader setup docs. This
change implements the shared refresh entry and maintained update invocation,
not those follow-up capabilities. The old update procedure's CLI-presence
Codex branch and independent Claude link steps are real readers to replace,
not an additional parallel updater to leave active.

Fresh branch issue-1889-shared-adapters and worktree
/workspace/claude-power-pack-adapters start at main 12b39ceb. Other local
worktrees hold the finished contract/core/builder and historical probe branches;
no unpublished B implementation was found there. Other containers/machines'
unpublished work is unexamined. CPP remains pinned on the owner host; tests
use disposable host roots only. Orchestrator assignment: mailbox 40515.

### Section C - proposed plan for approval

1. `lib/host_update/models.py` - additive typed lifecycle/backend contract for the established Claude link layout and production report coverage; preserve existing managed-copy types, defaults and fixture API.
2. `lib/host_update/driver.py` - retain shared selection, revision validation, lock/failure sequencing and aggregation; permit an explicit trusted link backend while the default managed-copy backend and no-follow refusal remain unchanged.
3. `lib/host_update/scope.py` - reusable descriptor-relative preflight from an approved home anchor through user-controlled prefixes; never follow .gemini or config before authorizing the AGY skills root.
4. `lib/host_update/links.py` - bounded Claude command/helper link inventory, ownership and locked publication backend; link-leaf handling cannot authorize symlinked roots or arbitrary directory traversal.
5. `lib/host_update/source.py` - resolve one full commit once, reject dirty/unavailable input, materialize a private detached snapshot with hooks/fsmonitor/Git overrides disabled, execute its driver/builders and clean only its owned temporary worktree.
6. `lib/host_update/claude.py` - actual Claude commands/helpers adapter preserving the established links and existing host-write/defer boundary, plus canonical managed topic-copy component; aggregate component observations into a single Claude row without hiding failures or enrolling absent components by default.
7. `lib/host_update/codex.py` - actual Codex managed-copy adapter using the unchanged generator from the pinned private snapshot; recognize GENERATED ownership evidence without treating it as prior byte provenance; use the existing Codex install lock.
8. `lib/host_update/antigravity.py` - actual topic-only AGY managed-copy adapter consuming lib.antigravity_skills.build; strict home/.gemini/config no-follow preflight, explicit global skills root and exact config/.cpp-skill-install.lock; no native plugin or auth access.
9. `lib/host_update/host.py` - initial adapter registry, receipt/explicit/managed discovery selection, same-revision dispatch, per-harness report and PARTIAL coverage/follow-up fields; no CLI-presence enrollment or invoking-harness filter.
10. `scripts/cpp-host-update.py` - add production refresh/verify arguments and human/JSON output while preserving explicit fixture mode; source/home/selection/defer/adoption boundaries, HOST-SURFACE declarations and no credential/config-root enumeration.
11. `.claude/commands/cpp/update.md` - invoke the shared driver once after source fetch even with zero commits pulled; replace duplicated selected Claude/Codex refresh calls, preserve unrelated runtime/MCP/settings work, retain nonzero per-harness outcomes in the final summary; pay instruction growth with removals and run the command budget/instruction audit.
12. `.specify/specs/antigravity-host-update/spec.md` - restore the B real-adapter same-full-revision acceptance row from Nit 7168730806, including a different/guessed-revision negative case; do not change the settled contract.
13. `tests/test_host_update_adapters.py` - actual discovery, explicit absent selection, marker/receipt/legacy migration, per-prefix alias refusal before reads, foreign neighbors/internal collisions and bounded no-follow behavior for all three adapters.
14. `tests/test_host_update_links.py` - actual Claude link backend and helper seam/defer behavior, clean source/content binding, foreign link/directory preservation, record/provenance limits and interrupted publication.
15. `tests/test_host_update_integration.py` - one real shared invocation at a current checkout refreshes stale Codex/AGY plus selected Claude surfaces; all report the SAME full revision; actual bytes/membership/modes and a byte-identical foreign neighbor are checked independently against fresh builds; mismatched adapter revision is rejected.
16. `tests/test_host_update_permissions.py` - prove a destination genuinely unwritable by the CLI identity with a failed write, then run the real driver under that identity and show other adapters refresh; non-mutating verify on readable/unwritable trees; root uses a dropped-identity child rather than chmod-only evidence.
17. `tests/test_host_update_adapter_transactions.py` - repeat A's held-lock/no-lock/interruption/prune and controlled same/different-package schedules through actual AGY adapter; both acquisition orders, full build/record comparison and an unlocked-mixed-output negative input.
18. `tests/test_host_update_command.py` - maintained cpp/update instruction blocks invoke the actual CLI/report reader with real adapter outputs, including no checkout commits to pull, CLI absent, external cwd and retained failure summary; no hand-written JSON substitute for the changed producer.
19. `tests/test_host_update_ci_shape.py` - fixture-owned full/shallow/detached source shapes created under 022/000, real production adapters/entry, pinned snapshot and permission modes; no cloning from a mutable outer CI checkout; expose command stderr on failure.
20. `controls/antigravity-skill-install-fidelity/control.json` - register actual production adapter fidelity with GOOD/BAD/UNKNOWN cases and blind/mutation evidence.
21. `controls/antigravity-skill-install-fidelity/run-case.py` - materialize committed cases under disposable home/source roots, assert defining preconditions, invoke actual production CLI and consume its real report/tree; never run a paid/native model.
22. `controls/antigravity-skill-install-fidelity/anchors/constructed-always-current.py` - declared blind implementation which misses each BAD fidelity input.
23. `controls/antigravity-skill-install-fidelity/cases/good-current/case.json` - nonzero expected packages and complete real managed installation.
24. `controls/antigravity-skill-install-fidelity/cases/good-refresh/case.json` - stale managed Codex/AGY, Claude selected independently of invoking CLI, foreign sibling preserved and common full revision verified.
25. `controls/antigravity-skill-install-fidelity/cases/bad-stale/case.json` - proven owned stale bytes detected by verify.
26. `controls/antigravity-skill-install-fidelity/cases/bad-missing-member/case.json` - required bundled guide absent, nonzero floor retained.
27. `controls/antigravity-skill-install-fidelity/cases/bad-hand-edited/case.json` - changed installed bytes/modes preserved and reported, including mixed missing/edited conflicts.
28. `controls/antigravity-skill-install-fidelity/cases/bad-foreign-content/case.json` - internal foreign member/same-name unowned target refused and preserved.
29. `controls/antigravity-skill-install-fidelity/cases/bad-revision/case.json` - real-adapter wrong/guessed revision cannot produce shared current.
30. `controls/antigravity-skill-install-fidelity/cases/unknown-lock/case.json` - held/unreadable exact lock gives unknown without mutation.
31. `controls/antigravity-skill-install-fidelity/cases/good-verify-no-lock/case.json` - full installation verifies with absent lock and identical before/after tree; always-create-lock mutation is rejected.
32. `Makefile` - production refresh/verify and focused adapter/permission/transaction/CI-shape/control targets; retain explicit fixture targets and avoid a new bespoke AGY updater target.
33. `controls/census.md` - production shared-driver/adapter verification claims and evidence limits; existing fixture controls stay registered.
34. `.claude/verify-coverage.json` - production entry/control/Make coverage accounting without exempting a changed gate.
35. `docs/scripts/cpp-host-update.md` - production CLI, discovery/selection/legacy migration, Claude links versus copies, exact roots/locks/records, report/exit policy, PARTIAL and effectiveness limits.
36. `docs/scripts.md` - update the existing shared entry inventory description, no second updater entry.
37. `docs/measurements/host-update-acceptance.probe.py` - NEW optional gated AGY acceptance probe, kept separate from the byte-frozen historical attempt-4 script; require a current owner ruling bound to the reviewed run manifest or operator-provided ADR 0015 file-token setup before native launch, default refuse; no credential-store reads/copies or automatic login.
38. `docs/measurements/host-update-adapters.md` - actual acceptance matrix, modes/permission/CI-shape/lock evidence and explicit missing live invocation/effectiveness lanes; reviewed native commands/undo/ruling if a later live run is authorized.
39. `changelog.d/1889.md` - append delivery-B behavior and explicitly partial scope while retaining A's delivered core facts.
40. `controls/antigravity-skill-build/codex-baseline.json` - retain the immutable 40d baseline members and generator/parser digests; add only explicitly reviewed attributed input deltas caused by the maintained cpp/update source change, with its source commit and reason.
41. `tests/test_antigravity_codex_parity.py` - consume the same attributed source delta under both process masks, retain exact independent generator/parser byte and mode comparisons, and reject a deliberately unattributed input change; no blanket mode or content normalization of output.
42. `tests/test_host_update_probe_gate.py` - committed missing/stale/wrong-head ruling and absent dedicated-auth preconditions must refuse before any native callback; a removed-gate mutation must reach the forbidden callback and fail. This tests launch authorization only, not a real AGY consumer.

Scope: Tier 3, approximately 42 named implementation/test/control/docs paths,
plus this append-only plan, as-read snapshot, demonstrated-lane record and later
counter-model receipt. Roughly 2500-4000 implementation/test lines. A required
extra control seed uses the existing plan-change procedure before inclusion.
No implementation or native run occurs before ch-orch approves this proposal.

### Decisions, migration and risks to approve

Claude's established installation contains command/helper symlinks; the regular
copy core intentionally refuses symlinks. Do not weaken that refusal globally
or turn those links into copies. Add an explicit backend/lifecycle seam with
managed-copy as its unchanged default. Claude's backend checks link leaves only
within approved commands/scripts scopes, verifies source content at the bound
revision, and reports topology separately from bytes. Link targets remain the
approved persistent CPP checkout, not a soon-deleted private build snapshot;
check its revision/cleanliness before and after link work. Claude topic copies
use the regular copy path. No settings, auth, MCP or arbitrary .claude root walk
is part of this adapter. This is the main design risk requiring plan approval.

Freeze the additive interface/types in an early commit and notify ch-w2 and
ch-orch of the full SHA BEFORE implementing backends or changing existing
callback behavior. pi's consumer must continue to use the unchanged default
copy API. Notify ch-w2 before any later interface change. No pi enrollment.

Legacy GENERATED/metadata.source markers and known Claude link shapes are
ownership discovery inputs, not proof of old complete bytes. Existing valid
core records permit stale refresh. A legacy copy exactly matching a complete
fresh build may gain a record without changing package bytes. A stale legacy
copy with no verifiable prior manifest/revision is selected but unexaminable,
with a named migration/adoption remedy; do not record observed edits as if they
were a known previous build. Explicit adoption stays path-specific with a
recoverable backup, never blanket --force. Test both marker spoofing and a real
legacy install. Initial absent/unselected roots are not created.

AGY preflight starts at an approved home anchor and opens .gemini, config,
skills, ledger/staging and the exact lock without following user-controlled
prefix aliases. A .gemini or config symlink is refused BEFORE inventory, Git
build, lock creation or descent. Include deliberate aliases above the root
with a forbidden-read sentinel. A normal system prefix above the approved home
anchor may be an alias; this does not approve user config aliases. Locks
coordinate cooperating CPP writers only; direct native writes remain outside
that guarantee. Keep the legacy Codex install lock path for coexistence, while
retaining the limitation that old writers need not honor the new ownership
record protocol.

One desired full commit is resolved once. Private detached source material
supplies the actual driver/adapters/builders from that revision; all selected
real adapter rows retain that full commit even on failure. Dirty/unavailable
source produces not-attempted rows for every selected adapter, not guessed
output. Builders cannot fetch/pull or resolve a branch independently. Do not
change scripts/codex-skill-sync.py or silently refresh its vendored baseline.
The maintained cpp/update source edit necessarily changes generated Codex skill
input. Preserve the recorded historical baseline and pin digests; attribute
only that reviewed source-driven byte delta in the existing delta field with
the source commit/reason. Both process-mask historical comparisons must consume
the same attributed inputs. Independent old/current transforms still compare
exact bytes/modes on identical CURRENT inputs, and an unattributed source
change remains red. This is an input change, not generator parity waiver.

The failed #1888 CI clone cause remains UNPROVEN. B tests do not depend on
transport/history of a concurrently deepening CI checkout: materialize committed
inputs and fixture-owned histories. Exercise shallow HEAD-only sources and
checkout creation under umask 000 before requesting PR CI. Host uid 1000 is
not a root-CI emulation; root-only permission lanes require an actual dropped
identity, otherwise remain explicitly untested. Capture stderr for every Git
fixture failure. Regression claims require a red run on predecessor code.

The historical AGY attempt-4 probe and its one-run approval remain unchanged.
A new optional probe refuses launch without a fresh governing ruling reference
bound to the exact reviewed run/commands, or an explicitly configured ADR 0015
file-token lane with session bus blanked. The old ruling is NOT permission to
rerun. First prepare concrete commands, private HOME boundaries and undo; then
ask the fleet master for the required owner authorization. No live AGY model
run or credential migration is authorized by this plan. Ordinary adapter file
acceptance requires no native model. Runtime identity remains #1886, and real
AGY cpp-update invocation remains the command-derived follow-up.

### Evidence and control plan

Epic acceptance uses the ACTUAL Claude/Codex/AGY adapters and pinned builders,
not FixtureAdapter. Seed prior installations through real adapters at revision
A, switch the owned source to B, and call the shared CLI once. Both copied
installations must match their fresh B builds; the Claude selected components
must match their approved layout/content. Every selected row and build digest
must bind the same full B commit. A wrong-revision adapter is the committed
negative input; assert the discrepancy before invoking the decision reader.
Keep a personal sibling skill's membership/bytes/modes identical.

Repeat with one destination unwritable by the executing identity. Prove that
identity and a failed write BEFORE refresh; under uid 0 use a dedicated child
with dropped identity and readable fixture source, not chmod under root. The
other selected adapters must still refresh, while JSON and human summaries
identify the actual failed destination and deterministic aggregate exit.

Repeat A's lock/no-lock/foreign/orphan/interruption/same-package schedules
through the real AGY adapter. Compare complete observed package/record state
against two independently built revisions, not merely JSON validity or exits.
Run controlled overlap in both acquisition orders; deliberately interleaved
unlocked output must be rejected. Prune only unchanged manifest-proven owned
orphans; changed/foreign orphan content survives. Verification must not create
a root/lock/record or repair metadata. Committed controls include GOOD, BAD and
UNKNOWN, and an always-current anchor misses BAD inputs; demonstrate mutations
for mode/bytes, no-lock creation, unsafe pruning and missing serialization.

Run focused Make targets, both creation masks, and pinned-CI-compatible shallow
cases before review. Run required full make verify through the direct
self-supervised finish gate at the committed checkpoint. Formal review starts
with the normal cap of two; request any exception only when needed with a
concrete reason, never inherit #1888's cap-7 ruling. PR creation/CI window needs
ch-orch clearance; one AGY PR in flight and Kyle series priority still apply.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | actual production entry from main checkout and linked worktree; private detached snapshot and persistent Claude target binding |
| Harness | will test | real Claude install layout, Codex generated copies and AGY topic copies in disposable homes; native model effectiveness requires separate approval/evidence |
| Driver | will test | maintained cpp/update blocks call the actual shared entry from Claude and generated Codex command surface; delegated flow drivers are unchanged; real AGY cpp-update remains not covered |
| Coordination | not applicable | product advisory locks are local; no Kyle-dependent product behavior; heavy validation uses the gate's own Kyle supervisor |
| CI provider | not applicable | no provider selection change; PR CI is Woodpecker, no live GitHub Actions claim |
| Project state | will test | managed, selected absent, unselected absent, foreign-only and legacy record/marker cases; no CLI-only enrollment |
| Toolchain version | not covered | installed host and pinned PR CI; no additional version matrix |
| Clone shape | will test | full, shallow HEAD-only and detached fixture-owned histories; missing source commit unknown; no ambient unshallow dependency |
| Run location | will test | CPP root and unrelated invoking repository give same selected adapters/revision/results |
| Gate target | not applicable | host adapter fidelity, not quality gate interpreter/PATH routing |
| Wave role state | not applicable | no mailbox/role registry behavior changed |
| Reader: shared core and real adapters | tested against real output | integration tests feed actual pinned builds to actual lifecycle/copy/link backends and inspect installed bytes/membership/modes |
| Reader: cpp/update and generated Codex adaptation | tested against real output | test_host_update_command consumes real production reports and exercises maintained command entry; no independently authored report fixture |
| Reader: control decision harness | tested against real output | committed cases invoke actual production CLI and compare its report/tree, then a blind anchor/mutations |
| Reader: legacy core fixture and pi API | reader unchanged | existing fixture JSON/schema and default managed-copy callbacks remain compatible; rerun their actual tests and coordinate the additive interface with ch-w2 |
| Reader: install-drift/cpp status/capability planner | not covered | no schema switched beneath existing consumers; integrations remain #1892/#1893, with this CLI/report documented for those deliveries |
| Reader: AGY native consumer | not covered | no new model run authorized; gated probe is prepared only, live invocation requires concrete owner approval or the prescribed dedicated auth lane |
| Reader: Kyle, skillc, kyle-candidate | reader unchanged | Codex generator bytes/CLI and generated transform contract unchanged; run existing independent Codex parity suite after command-doc input changes and attribute any source-driven delta |

Reader search positive control found cpp/update:2042 invoking the known
codex-skill-sync.py --install reader, plus existing Makefile build/install
readers. Searches found Claude command/helper steps, shared CLI fixture tests,
AGY builder/core consumers, HOST-SURFACE checks and documented status/drift
follow-ups. Cross-repository Codex consumers are known from ADR 0014; their
private code was not searched. Command-doc source changes may alter Codex
output even with an unchanged generator: attribute and seek review for that
input delta, never silently re-pin historical transform evidence.
