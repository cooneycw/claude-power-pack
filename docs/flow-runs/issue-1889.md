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

<!-- flow-run n=2 id=ce18e218d63a4326b62ca6eb9458eee3 -->
## Run 2

- Run-id:            ce18e218d63a4326b62ca6eb9458eee3
- Run-start:         12b39ceb146dc89860be036e577ae248e362a19d

- Issue:             #1889, PR0 docs-only prerequisite; parent #1876
- Necessity verdict: Needs reframing - amend accepted ADR before adapter code
- Approval:          granted for the requested amendment scope only
- Approver:          ch-orch mailbox40530, relaying owner ruling1889 comment7178523792

### Section A - intent

The owner chose to preserve Claude's existing command/helper links under the
shared updater. ADR0014 currently rejects symlinks without that exception.
Record the narrow exception before implementing it, so the code review has
an explicit authority and verifiable bounds. Topic skills and new harnesses
remain managed copies. No installer/backend behavior ships in this PR.

### Section B evidence

Base12b39ceb includes accepted ADR0014, contract/core and AGY builder. The
owner ruling is https://github.com/cooneycw/claude-power-pack/issues/1889#issuecomment-7178523792
("1889 A"). Orchestrator40530 requires a separate docs-only PR0 landing FIRST,
then B1 copy adapters, then B2 maintained invocation and bounded Claude links.
Original draft/B1 plans live on issue-1889-shared-adapters and are unapproved;
this branch carries only PR0. Existing ADR blanket-rejection clauses were
read; a clearly dated amendment narrows them without rewriting history.
#1889/#1888 and epic acceptance remain open. No issue-body edit is planned.

### Section C - the approved PR0 plan

1. `docs/decisions/0014-antigravity-capability.md` - add dated owner-ruling amendment: existing Claude command/helper links only; targets resolve inside the pinned CPP checkout; no new link kinds; read-only type/target/content/revision verification; outside/dangling/regular-file replacement controls required with B2; report backend as links, never copies; topics/new harnesses stay copies; ADR lands before code.

Scope: one docs file plus this plan/as-read and later review/lane receipt.
No product code, installer, generator, host/config mutation or native model run.
Authorization is the explicit amendment instruction40530; it does not approve
B1 or B2 implementation. Separate B1/B2 plan reconciliation follows PR0 merge.

Verification: focused Make docs-link and Unicode checks; independent review
before PR; full remaining gates in PR CI with ch-orch clearance. No regression
or live runtime claim for this documentation amendment. B2 must commit the
three required negative controls before its link backend ships.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | not applicable | docs amendment, no checkout-path behavior |
| Harness | not applicable | no installation or runtime change; records Claude-only future exception |
| Driver | not applicable | no command/driver implementation changes |
| Coordination | not applicable | no coordination behavior |
| CI provider | not applicable | no provider logic; PR CI Woodpecker |
| Project state | not applicable | no state-reading behavior |
| Toolchain version | not applicable | prose only |
| Clone shape | not applicable | no history-dependent implementation |
| Run location | not applicable | no runtime entry |
| Gate target | not applicable | no quality-gate behavior change |
| Wave role state | not applicable | no role state change |
| Reader: adapter implementer/reviewer | not covered | normative future backend contract; B2 must feed real output to its tests/reader |
| Reader: existing runtime consumers | reader unchanged | no code/schema/generated input changes |

Reader search positive control found ADR0014 referenced by the authoritative
host-update spec. Existing rejection clauses at ADR lines35/67/219 were read.
The amendment states its precedence and limited scope; future backend evidence
is not asserted to exist now. All earlier approved run history stays intact.

<!-- flow-run n=3 id=cbff69dcdd074f20b794f98166080f42 -->
## Run 3

- Run-id:            cbff69dcdd074f20b794f98166080f42
- Run-start:         23fde5b15bfab8ba3c4cf03476fb75357d524c62

- Issue:             #1889, delivery B1; B2 is deferred below; parent #1876
- Necessity verdict: Needs reframing (the combined issue is staged A/B1/B2)
- Approval:          granted for B1 Section C only
- Approver:          ch-orch mailbox40532 approving Section C at87494bf4; owner/stage clarifications40530

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
B1/B2 merge. Parallel B1 implementation is explicitly allowed by40532. B1 still makes NO link/backend/core-callback change. The three
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
before B1 PR/merge. Its approved Run2 is carried unchanged into this branch;
B1 is Run3, and no historical approved section is overwritten. Parallel B1
implementation during PR0 review is authorized by40532.

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
granted by40532; product implementation begins after this record is stamped.

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

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | real production CLI from main checkout / linked worktree and private detached source snapshot |
| Harness | will test | Claude install (TOPIC copies only) / Codex install; also AGY topic copies in disposable homes; commands/helpers deferred |
| Driver | not covered | maintained cpp/update and its Claude/Codex command routes are B2; B1 actual standalone shared CLI only |
| Coordination | not applicable | local advisory locks, no Kyle-dependent product branch; heavy validation uses gate supervisor |
| CI provider | not applicable | no provider-selection change; PR CI Woodpecker only |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not; managed, selected absent, unselected absent, foreign-only and legacy cases |
| Toolchain version | not covered | installed host and pinned CI only, no added version matrix |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone; also detached fixture history; unavailable source unknown |
| Run location | will test | invoked from the CPP root / from another directory (an unrelated repository), with same adapters/revision/results |
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

<!-- flow-run n=4 id=5ee1db43f88c41459157642b8e64db24 -->
## Run 4

- Run-id:            5ee1db43f88c41459157642b8e64db24
- Run-start:         875f4a479c9ee551388cf1ee25ed570a9a87c94e
- Issue: #1889 B1 review amendment; parent #1876
- Approval: granted for bounded amendment by ch-orch mailbox40696 (also40693)
- Approver: ch-orch, run140, 2026-11-26

### Section A - intent

Carry B1's approved 31-path copy-adapter delivery from Run3 unchanged in scope,
except the bounded review amendment below. Preserve historical Run3 and its
approval. Formal pass1 at875f4a479c9ee551388cf1ee25ed570a9a87c94e found F1
MEDIUM: one foreign same-name topic prevents every safe package progressing;
F2 LOW: private Git worktree registration writes the user's source metadata.
Fix both in one pushed checkpoint, then request formal pass2 (normal cap2).

### Section B - evidence and authorization

Reviewer40692 reproduced real foreign Claude boot plus17 otherwise safe topics.
The #1887 contract requires per-package refusal. Orchestrator40696 explicitly
approves adding models.py, driver.py and store.py to the31 approved paths.
Before core edits, Pi worker notified40700 and replied40703: trailing typed
Policy flag after member_allowed (Pi passes predicate positionally), default
false, refusal-before-transaction ordering retained, global integrity failures
never downgraded to package skips. Paired multi-package Pi-default/CopyAdapter
opt-in control is required. Pi adapter itself stays unchanged; its remaining
collision exposure is tracked separately. Owner probe pin is untouched.

F1 foreign, hand-edited and edited-orphan cases run red on reviewed875f4a47
before core changes. Blocked bytes AND records survive; safe packages refresh
under existing whole-harness locks; only independently verified safe records
are published. Full row keeps all population counts/conflict package names,
exit1/non-current and a preservation remedy, never default adoption of foreign
content. Explicit reviewed adoption remains available only when requested.
F2 uses a standalone private clone because existing pinned blob readers require
Git history; assert source.git bytes unchanged during and after its lifetime.
No source branch move, source config/checkout write, native run or B2 scope.

### Section C - approved amended B1 file set

1. `lib/host_update/source.py` - resolve a full commit once, refuse dirty/unavailable source and materialize a private standalone detached clone with Git overrides/hooks/fsmonitor disabled; use its driver/adapters/builders and clean only the owned temporary clone, never registering worktrees in the user source.
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
32. `lib/host_update/models.py` - append typed Policy.partial_refresh default false AFTER member_allowed; existing positional and callback consumers remain compatible.
33. `lib/host_update/driver.py` - additive opt-in dispatch to package-partial publication under existing locks; preserve default behavior; partial row exit1, non-current full conflict/count report and preservation remedy.
34. `lib/host_update/store.py` - opt-in partition of blocked versus safe packages, preserving blocked bytes/records and other identities; verify safe publication and permit remaining named conflicts without retaining a false incomplete transaction; global policy/source/ledger/integrity errors remain hard stops.

Approximately1900-2400 added lines overall. Extra paths beyond these34 require
new approval. Legacy core and Pi test files remain unchanged and must pass;
paired behavior cases live in the already approved adapter test file.
Risks: partial publication must not erase a blocked owned/orphan record, skip
an integrity failure, create false current or silently widen adoption. Source
clone reads are bounded to approved source, temporary clone owns all writes.

### Lanes for this change


| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | real production CLI from main checkout / linked worktree and private detached source snapshot |
| Harness | will test | Claude install (TOPIC copies only) / Codex install; also AGY topic copies in disposable homes; commands/helpers deferred |
| Driver | not covered | maintained cpp/update and its Claude/Codex command routes are B2; B1 actual standalone shared CLI only |
| Coordination | not applicable | local advisory locks, no Kyle-dependent product branch; heavy validation uses gate supervisor |
| CI provider | not applicable | no provider-selection change; PR CI Woodpecker only |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not; managed, selected absent, unselected absent, foreign-only and legacy cases |
| Toolchain version | not covered | installed host and pinned CI only, no added version matrix |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone; also detached fixture history; unavailable source unknown |
| Run location | will test | invoked from the CPP root / from another directory (an unrelated repository), with same adapters/revision/results |
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


<!-- flow-run n=5 id=eee1b090f5f641d7ac3150286d52c057 -->
## Run 5

- Run-id:            eee1b090f5f641d7ac3150286d52c057
- Run-start:         b1cd1f1635a920ba4839097ebfff8977a0bf7dda

- Issue: #1889 B2; parent #1876
- Approval: granted for B2a with B2b split - ch-orch mailbox41041 (2026-11-26)
- Approver: ch-orch mailbox41041, replying to concrete checkpoint3f672821/mail41040
- Assignment: ch-orch mailbox40991, after PR1912 merged

### Section A - intent

The shared updater now refreshes real Claude topic, Codex and AGY copies, but
`/cpp:update` still performs separate legacy helper/command/Codex operations.
A current checkout can therefore leave managed copies stale, and the report
cannot verify the owner's existing Claude command/helper links as a component.
B2 makes the maintained command call the shared updater once even when no
commits were pulled, verifies the approved existing link kinds, and reports
actual component failures instead of a generic successful update heading.

The new optional native probe must refuse before any native command or auth
setup without a recorded governing ruling bound to the reviewed runner and
chosen authentication lane. Plan approval authorizes implementing and testing
that gate with injected callbacks, not a native run, login or credential access.
Initial coverage stays PARTIAL. Pi shared enrollment/its separately queued
opt-in, Qwen, Gemma/OpenCode, AGY command-derived cpp-update invocation and
receipt-backed AGY runtime identity remain separate deliveries. Neither #1889
nor #1876 is closed merely by the initial subset or by a gated probe file.

### Section B - evidence and design boundary

Base: main b1cd1f1635a920ba4839097ebfff8977a0bf7dda, PR1912 merged. New branch
`issue-1889-update-links`, worktree `/workspace/claude-power-pack-update-links`.
Only this run's plan/as-read evidence changes before approval. Run1-4 history
and approval digests remain untouched. Issue body read by the helper; digest
2b4d3f124af50f0eda6d73bb385e010900bbf39fc0627553e7054351bc73f91c.

Read the merged ADR0014 amendment (owner ruling1889A/7178523792), contract,
current production host/source/CLI, cpp/update Steps3/5a-5c/7.9/10, command-link
and helper installers, cpp-host-write per-entry discipline, existing command
readers and independent Codex parity tests. Positive reader search found the
actual cpp/update Codex installer and helper links; no unsearched external
consumer is claimed covered. Historical attempt4 probe code is on the old
`probe/agy-1888` branch at c2d8e03e, not a maintained main entry. It stays
unchanged and supplies no reusable permission. Pi worker notified41018 before
any possible API work; preferred design below avoids neutral/Pi API changes.
Pi worker reply41021 confirms its opt-in uses native AdapterResult only, not
the production envelope; no maintained generic ruling helper exists to reuse.
Its one-use owner-bound probe artifacts supply no B2 authorization.

**Small typed seam.** Keep neutral models.py/driver.py/scope.py/store.py and Pi
unchanged. Dispatch a separate typed Claude-only link backend from the existing
production host.run_host. Reuse its state/action/result vocabulary without
teaching the regular-file copier to follow links. Keep fixture/Pi formats and
callbacks unchanged. Production JSON advances explicitly to schema2 with four
component rows: claude-topics/copies, claude-links/links, codex/copies and
antigravity/copies; root backend is mixed. One serializer owns these tags.
The pinned entry compatibility marker advances too: both old/new entry readers
must reject unsupported producer versions before execution/writes, never run an
older producer and count missing link coverage as current. Source validator,
human formatter, controls and real readers consume the same schema.

**Persistent targets.** Carry the caller-approved persistent CPP root alongside
the private source snapshot into the pinned driver. Links never point into the
run-owned disposable clone. Prove persistent root is clean and at the desired
full commit before target reads and under the mutation lock; later source moves
or dirtiness make links non-current/unknown. Never pull, switch, clean, chmod or
otherwise modify this target checkout. Verify source membership/bytes and Git's
executable/non-executable mode distinction; retain exact installed modes for
copies. Do not normalize the user's checkout to make links pass.

**Existing kinds only.** Commands are the existing per-family directory links;
helpers are the current Tier2 population of tracked executable regular files
immediately under scripts/, regardless of extension. Derive names from pinned
source, not a second hand-maintained list. Ownership requires the expected
installed name AND exact approved CPP source mapping and confined no-follow
source topology, not a suffix or basename alone. Discover command/helper kinds
independently from real matching CPP links. Directory presence, a CLI, foreign
files or a command install do not enroll the helper tier. Do not create absent
Tier0/1 helper roots. Missing entries in an established managed kind may be
repaired; foreign links/real files/directories and mixed farms are preserved.
Retired links can be unlinked only with proven prior CPP source membership and
unchanged link identity; insufficient history/unprovable ownership is retained
and reported, not guessed. No recursive deletion, broad farm conversion or
implicit adoption. A dangling expected entry is never current.

**Writes and locks.** Validate .claude and the command/helper root prefixes
no-follow before inventory/source reads/lock creation. Limit mutations to the
named link entries and existing exact Claude install lock; no new link kinds,
agent-root enumeration or auth/config reads. Verify creates no directories,
locks, links or records. Refresh uses the shared Claude lock with bounded wait,
re-inspects entries before changing them and verifies afterward. Foreign/edited
entries block only those entries while safe entries progress, keeping the row
non-current/exit1. Source/path/lock/integrity uncertainty remains a hard stop
for that backend. This serializes cooperating shared updater calls, not native
or legacy writers that ignore its lock. Preserve copy failure isolation.

**Maintained command.** Replace only the owned Step5 link-refresh/bootstrap/
prune/check duplication and Step7.9a Codex-only installer with one shared refresh
step through the project uv runtime, with a checkout-path fallback if its
stable helper is absent. Preserve no-tier-upgrade, explicit defer data and the
other MCP/settings/local-model/memory/retired-surface operations. Do not infer
selection from invoking CLI or `command -v codex`. Keep the real exit and parsed
report for Step10; malformed/empty reports cannot produce a successful summary.
Always run when the source is already current. Distinguish the verified full
revision from a later FINISH_COMMIT; a subsequently moved link target cannot be
reported as current at finish. Do not silently refresh a second revision.

**Probe authorization.** New entry defaults to refusal/check-only and requires
a structured recorded ruling with authority/reference, issue/run, reviewed
code head, selected auth lane, allowed operation and validity bounds. It is a
recorded authority reference, not cryptographic proof of who ruled. Missing,
stale, wrong-head/lane and incomplete records refuse BEFORE every native or
setup callback, including version/help/login/setup paths. Both ambient-session
and dedicated-file-token branches pass the same gate; the dedicated setup must
be explicitly covered too. Never inspect/copy credentials to detect the lane.
Use only measured/prescribed CLI/setup syntax authorized by a new ruling;
unproven dedicated setup remains unsupported/unknown before launch. Keep
configuration isolation distinct from credential isolation. Retain only
sanitized bounded nonce/result evidence, no tokens/auth stores or raw sensitive
stdout/stderr. Guard tests use fake callbacks and nonsecret fixture records;
real AGY invocation remains unperformed until separately authorized.

### Section C - approved B2a file set

1. `lib/host_update/links.py` - new typed Claude-only policies/manifests/discovery/verify/refresh with descriptor-bound roots, persistent source fidelity, existing-kind selection, bounded shared lock and per-entry preservation/prune proof.
2. `lib/host_update/host.py` - shared component dispatch, explicit production schema2/backend tags and deferred gaps; no neutral copier or Pi behavior change.
3. `lib/host_update/source.py` - forward persistent source root separately from private clone; closed schema2/entry compatibility checks and common full revision; unsupported producer refusal before writes.
4. `scripts/cpp-host-update.py` - schema2 CLI/renderer, persistent-root handoff and link selection/defer outcomes, authored link HOST-SURFACE declarations, physical helper-link bootstrap (Nit7180160022); fixture mode unchanged.
5. `tests/test_host_update_links.py` - real expected command/helper links; positive plus outside/dangling/regular-replacement negatives, no forbidden target reads, root aliases, mixed farms/foreign preservation, no-tier-upgrade, source dirt/move/modes, locks/no-write/interruption and proven-retired versus unproven orphan behavior.
6. `tests/test_host_update_adapters.py` - extend owned source overlay with links module and explicit copy-component expectations; preserve independent real Claude reader and existing copy coverage.
7. `tests/test_host_update_integration.py` - actual schema2/common-revision selected-component integration while retaining all three copy acceptance assertions.
8. `tests/test_host_update_permissions.py` - schema2 selected-row checks, retain executing-identity permission proof and root-lane honesty; link failure cannot stop other copies.
9. `tests/test_host_update_adapter_transactions.py` - update source/report reader expectations only; existing actual AGY lock/prune/interruption cases remain intact.
10. `tests/test_host_update_ci_shape.py` - schema2 bad/mislabelled/zero/missing-component producer cases, compatibility refusal before execution, persistent-source handoff and helper symlink invocation; keep full/shallow/worktree/mask and declared-runtime cases.
11. `controls/claude-host-links/control.json` - register actual shared CLI link verification with explicit project runtime and GOOD/BAD/UNKNOWN signals.
12. `controls/claude-host-links/run-case.py` - owned persistent source/home and actual installed links; whole-tree preservation oracle, source/target preconditions and full nonzero population.
13. `controls/claude-host-links/anchors/constructed-always-current.py` - declared blind link verifier that misses the required bad cases.
14. `controls/claude-host-links/cases/good-confined/case.json` - intact links into the approved clean pinned source, with real bytes/membership/executable-mode comparison.
15. `controls/claude-host-links/cases/bad-outside/case.json` - expected name points outside the approved checkout, preserved and non-current before target contents are read.
16. `controls/claude-host-links/cases/bad-dangling/case.json` - unproven/incorrect dangling expected link preserved and non-current, not confused with a proven retired orphan.
17. `controls/claude-host-links/cases/bad-regular-replacement/case.json` - expected link replaced by personal regular content, preserved and non-current.
18. `controls/claude-host-links/cases/unknown-lock/case.json` - held/unavailable exact lock reports unknown without writes; missing-lock verification remains read-only in tests.
19. `Makefile` - focused B2a link/control targets using explicit project runtimes; existing full gate remains authority.
20. `controls/census.md` - register shared link control and real detection limits; native probe registration belongs to B2b.
21. `.claude/verify-coverage.json` - account for new B2a targets through maintained derivation, no exemptions.
22. `docs/scripts/cpp-host-update.md` - schema2/backend units, persistent links/locks/tier/defer/preservation rules; command wiring and probe remain deferred B2b.
23. `docs/scripts.md` - update shared entry description without duplicating implementation detail.
24. `.specify/specs/antigravity-host-update/spec.md` - ADR link exception and B2a initial-subset acceptance; preserve copy refusal and remaining epic deliveries.
25. `docs/measurements/host-update-adapters.md` - B2a link/backend fidelity acceptance and limits; command readers/native probe remain B2b.
26. `changelog.d/1889.md` - append B2a links/report scope, retain A/B1 and explicit PARTIAL coverage.
27. `controls/antigravity-skill-install-fidelity/run-case.py` - update actual source overlay and schema2 selected-copy result reader; existing AGY fidelity cases/anchor/discrimination remain intact.
Scope: these27 named B2a product paths (8 small link-control files), plus
own plan/as-read/lanes and receipt evidence. Approval: mailbox41041 split of
checkpoint3f672821. Do not change cpp/update, command readers, Codex attribution
or the native probe in B2a. No neutral/Pi API changes. Amend before extra paths.

### B2b deferred file list - separate delivery after B2a

- `.claude/commands/cpp/update.md` - one maintained shared refresh after dependency/source steps, including zero-pull path; replace approved link/Codex duplication, retain other operations and actual partial/failure/revision summary; offset command budget by deleting superseded instruction blocks.
- `tests/test_host_update_command.py` - execute maintained Claude update/summary fences against real registry outputs; the generator currently excludes cpp-update, so any Codex command enrollment requires explicit B2b scope approval. Cover already-current source/stale installs, actual failed destination, CLI/helper absent, mixed backend labels and source move before final summary; native model instruction-following is not claimed.
- `tests/test_host_update_probe_gate.py` - actual new probe entry with forbidden-launch/setup callbacks: all invalid ruling variants refuse in BOTH auth lanes; positive authorized callback runs; removed-guard mutation must fail; no native commands or credentials.
- `docs/measurements/host-update-acceptance.probe.py` - new opt-in gated native consumer probe/check-only entry; immutable historical attempt4 untouched; both auth/setup branches gated before callbacks and sanitized evidence only.
- `controls/host-update-probe-gate/control.json` - register the actual probe entry as a controlled external instrument, explicit uv runtime, no census/coverage exemption.
- `controls/host-update-probe-gate/run-case.py` - invoke the real probe entry with injected native/setup callbacks and nonsecret fixtures; enumerate each case/lane outcome and assert forbidden callbacks were not reached.
- `controls/host-update-probe-gate/anchors/constructed-missing-ruling-guard.py` - constructed bypass reaches the fake launch on invalid authority; never runs a native binary.
- `controls/host-update-probe-gate/cases/good-authorized/case.json` - valid current ruling in both auth lanes reaches exactly the permitted fake callback, with setup order checked.
- `controls/host-update-probe-gate/cases/bad-ruling/case.json` - explicit matrix of absent/stale/wrong-head/wrong-lane/incomplete-dedicated-setup records in both lanes, each refusing before callbacks.
- `controls/host-update-probe-gate/cases/unknown-record/case.json` - malformed/unreadable governing record is unknown and cannot launch.
- `controls/antigravity-skill-build/codex-baseline.json` - ONLY reviewed attributed source-input deltas for changed command/bundled inputs, with source checkpoint and reason; original members, commit, generator and parser pins remain immutable.
- `tests/test_antigravity_codex_parity.py` - apply attributed bytes under both masks, preserve exact independent-generator/parser mode comparison and source normalization; reject unrecorded source changes and historical-manifest tampering with committed negative inputs.

B2b also reuses the shared Make/docs/census/coverage/changelog paths above only
for its own wiring/probe/attribution changes. B2b gets a new plan baseline and
review receipt. Its PR opens only after B2a merges (mail41041). Both #1889 and
#1876 remain open and PARTIAL. Implementing/testing fake authorization callbacks
supplies no authorization for native execution or credential handling.

Risks: target source lifetime/races, source-content fidelity versus topology,
wrong backend tags, tier enrollment from foreign content, stale protocol
producers, command-reader summary masking, attribution becoming a re-pin, and
a probe gate covering only one auth/setup branch. Keep each distinction in a
committed case. Establish nonzero positive populations before reporting a scan
clean. Run meaningful regressions red before their fix and the lock/target/
backend/always-current/removed-ruling mutations; a missing feature on old main
is not labelled a regression. Review default2passes/thirdwithreason, never
inherit B1's consumed review count or #1888's scoped raised cap.

### Execution and validation order for B2a

1. Implement typed links/source/report seam and link controls, neutral/Pi unchanged.
2. Focused Make tests, real current/shallow/worktree production CLI and installed
   helper link route; meaningful regressions red before fixes, controlled bad
   link preconditions and constructed-blind anchor distinguish bad from good.
3. ENTIRE bare-caller negative-controls batch before formal review. Fresh B2a
   review count0, default2passes/thirdwithreason. No inherited raised cap.
4. Exact-head independent review/receipt, then DIRECT supervised full gate:
   normal MCP environment, no outer lock wrapper, df>=25GB and at most2 fleet
   heavy lanes. Short own tmp roots, immediate cleanup, logs outside worktree.
5. Orchestrator PR window; Refs1889/1876 only. B2b PR waits for B2a merge.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | main checkout / linked worktree; private snapshot plus separate persistent link target, wrong/moving/dirty target refused |
| Harness | will test | Claude install / Codex install / AGY topic copies via real production adapters; maintained command readers and native model invocation deferred B2b |
| Driver | not covered | cpp/update wiring, /flow:auto (Claude implements) and delegated drivers unchanged in B2a; no live instruction-following claim |
| Coordination | not applicable | same product semantics without Kyle / with Kyle; existing advisory install locks, no new Kyle product API; heavy gates use supervisor |
| CI provider | not applicable | Woodpecker / GitHub Actions / none recorded selection unchanged; normal CPP PR CI only |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not; managed/absent/foreign/mixed farms and existing-kind tier selection |
| Toolchain version | not covered | CI's pinned uv and Python / host installed versions, no added version matrix; actual declared-runtime regression and owned source modes retained |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone; missing prior orphan history is explicitly unknown/preserved, never guessed |
| Run location | will test | invoked from the CPP root / from another directory; production CLI source path and helper symlink route |
| Gate target | not applicable | shared updater fidelity and probe authority, no consumer quality-gate interpreter/PATH policy change |
| Wave role state | not applicable | no fresh/released-role registry change |
| Reader: maintained Claude cpp/update | not covered | deferred B2b; no change or coverage claimed in B2a |
| Reader: generated Codex cpp-update | absent | generator excludes cpp/update; enrollment requires explicit B2b scope approval; no coverage claimed |
| Reader: shared production report consumers | tested against real output | actual closed schema2/backend/common-revision payloads, missing/zero/mislabelled/wrong-version negatives and actual control decisions |
| Reader: Claude link/copy surfaces | tested against real output | actual installed link types/targets plus pinned content; independent copy bytes/modes and unchanged Claude topic reader |
| Reader: fixture/Pi API | reader unchanged | neutral types/callbacks/serialization unchanged; rerun existing core/Pi suites and notify Pi worker before any proposed departure |
| Reader: native probe launcher | not covered | deferred B2b; no change or coverage claimed in B2a |
| Reader: AGY runtime and cpp-update invocation | not covered | new recorded ruling required before any live probe; command-derived AGY invocation and runtime receipt adapter remain separate |
| Reader: drift/status/planner and other repos | not covered | no reader enrollment switched in B2; follow-up acceptance remains owned by its delivery; generator/CLI compatibility remains protected |


<!-- flow-run n=6 id=684f9555ad654495b4355b805b96cf6e -->
## Run 6

- Run-id:            684f9555ad654495b4355b805b96cf6e
- Run-start:         8e6efc03d1393a3bafcce8496709d5161154e7cf
- Necessity verdict: Still needed
- Approval: granted for B2b-1 only
- Approver: ch-orch mailbox41657 and41726, relaying owner ruling1889A; amended source list mailed41729 before edits

### Section B evidence
Base8e6efc03 is confirmed green by41646. PR1919 delivered B2a; no generated cpp-update reader exists. Plain Python3.12.3 -I -S runtime check found legacy link-into succeeds0 while shared production reports4 missingyaml. Owner1889A requires lazy PyYAML, stdlib Claude links/Codex, named per-adapter UNAVAILABLE, one writer/no fallback. Probe B2b-2 is deferred after B2b-1 merge; no native execution or credential handling authorized.

### Section C - the approved plan
1. `.claude/commands/cpp/update.md` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
2. `tests/test_host_update_command.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
3. `tests/test_cpp_host_link_preservation.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
4. `tests/test_helper_orphan_prune.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
5. `tests/test_cpp_host_writes.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
6. `controls/cpp-update-host-refresh/control.json` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
7. `controls/cpp-update-host-refresh/run-case.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
8. `controls/cpp-update-host-refresh/anchors/constructed-masked-summary.mk` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
9. `controls/cpp-update-host-refresh/cases/good-stale-refresh/case.json` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
10. `controls/cpp-update-host-refresh/cases/bad-unwritable/case.json` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
11. `controls/cpp-update-host-refresh/cases/bad-summary/case.json` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
12. `controls/cpp-update-host-refresh/cases/unknown-unavailable/case.json` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
13. `controls/antigravity-skill-build/codex-baseline.json` - conditional measured attributed input deltas only; immutable historical pins/members.
14. `tests/test_antigravity_codex_parity.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
15. `Makefile` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
16. `controls/census.md` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
17. `.claude/verify-coverage.json` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
18. `docs/scripts/cpp-host-update.md` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
19. `docs/measurements/host-update-adapters.md` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
20. `.specify/specs/antigravity-host-update/spec.md` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
21. `changelog.d/1889.md` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
22. `lib/host_update/host.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
23. `lib/host_update/claude.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
24. `lib/host_update/antigravity.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
25. `lib/antigravity_skills.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
26. `scripts/cpp-host-update.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
27. `lib/host_update/source.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
28. `tests/test_host_update_adapters.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
29. `tests/test_host_update_ci_shape.py` - B2b-1 wiring, closed reader/runtime, safety fixture/control or documented subset acceptance as plan41654/41657/41726 and amendment41729.
30. `lib/host_update/links.py` - ruling41749: narrow retirement removal to dangling targets only; preserve live targets as an existing UNMANAGED conflict/exit1. No schema/state/code additions.
31. `controls/cpp-update-host-refresh/cases/unknown-stale-legacy/case.json` - owner1889A / mailbox41841: attributed real historical stale legacy package, shallow-CI reproducible named migration UNKNOWN.
32. `tests/test_install_drift.py` - amendment41925: replace removed update-loop coupling with real shared manifest population; retain init and negative distinctions.
33. `tests/test_permissions_template_link_parity.py` - amendment41925: actual shared manifest population and executable/non-executable/non-shell controls; retain init assertions.
34. `scripts/host-surface-observe.py` - amendment41925: explicitly classify cpp-host-update.py without observation/certification claims; no catch-all.
35. `tests/test_host_surface_observe.py` - amendment41925: classification proof and newly derived unclassified-member refusal control.
36. `scripts/codex-skill-sync.py` - owner ruling7204721638: delete exactly six stale cpp/update exception rows and no other bytes; immutable historical generator/parser/pins remain unchanged.
37. `tests/test_codex_skill_sync.py` - rebuild the frozen generator by reinserting the six rows; reject retired-row reintroduction and any non-table byte mutation; retain stale-exception/output checks.
38. `tests/test_cpp_command_wiring.py` - replace the retired standalone Codex-installer assertion with actual shared-fence wiring and a missing-fence/comment-only negative.
39. `tests/test_negative_controls.py` - typed/plain gate metadata reader through shared parse_gate; preserve source population, self-registration and nested-case exclusions, with both descriptor kinds and malformed negatives.
40. `tests/test_stable_path_scripts_installable.py` - retain init executability and consumer-derived stable-path checks; use the actual shared executable manifest for update and its missing/wrong-inclusion controls.
41. `controls/host-surface-observe/anchors/constructed-blind-covered-by.py` - regenerate from current origin with the unchanged stored patch and preserved module docstring.
42. `controls/host-surface-observe/control.json` - canonical constructed-anchor digest refresh only; no historical repin.
Scope:42 possible product paths plus own plan/as-read/lanes/receipt records. No probe paths, no neutral core/Pi API changes. Amend before extra product paths. Codex baseline untouched unless actual output deltas measured. Never repin historical members/generator/parser. Runtime regressions must run red before lazy-import fixes. Deletion comparison must establish shared deletion subset of actual legacy deletion, count all personal/foreign/retired/mixed population and enumerate legacy-only deletions. update.md before2291 lines; require lower after count.

### Implementation and validation
One shared refresh replaces managed5a/5b/5c and7.9a, existing actual full revision, existing-install discovery and deferrals. Retain unrelated runtime/stash/local-model/MCP/memory/retired-surface operations. Real JSON/exit/finish-revision summary, no masked success. Controlled actual caller cases, byte/type oracles, genuine unwritable executing identity. Named control controls/cpp-update-host-refresh registered typed Make target host-update-command-check, GOOD stale refresh, BAD unwritable and malformed/revision moved reports, UNKNOWN unavailable; constructed masked-summary anchor. Existing parity bad attribution/pin/parser/generator cases protect both022/002 exact modes; preserve tracked-input race fix. No generated cpp-update reader or whole-epic/native acceptance claim.
Fresh review count0, default2 passes/thirdwithreason. Focused Make tests and controls, whole bare control batch, owner CI shape(depth1,umask000,HOMEroot/realUID distinction,aliasTMPDIR,minimalPATH), fresh receipt then DIRECT supervised gate normal MCPenv/noouterwrapper/noactiveflag, max2heavy/df25GB, short ownedtemps immediately cleaned. PR window via orchestrator, Refs1889/1876 only.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | will test | main-layout and linked worktree, actual private pinned snapshots |
| Harness | will test | Claude install / Codex install; maintained Claude fences plus actual Claude links/topics,Codex/AGY copies; no generated cpp-update reader |
| Driver | not covered | delegated workflow implementations unchanged, no live model obedience |
| Coordination | not applicable | no new Kyle product dependency; normal supervised validation |
| CI provider | not applicable | unchanged, normal CPP Woodpecker PR CI |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not; managed/absent/foreign/mixed/deferred roots and legacy/shared deletion |
| Toolchain version | will test | CI's pinned uv and Python / the host or container's installed versions; plain stdlib/missing YAML versus project env; no version matrix |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone; fail honestly on unavailable proof |
| Run location | will test | invoked from the CPP root / from another directory |
| Gate target | not applicable | no consumer interpreter policy change |
| Wave role state | not applicable | no lifecycle registry changes |
| Reader: maintained command/report | will test | actual fences, production reports/installations, no-op source stale installs and failure/revision cases |
| Reader: generated Codex | will test | actual output/parity/delta measurement, never a cpp-update mirror |
| Reader: native | not covered | B2b-2 deferred; nothing native/auth runs |

Active Run6 scope amendment approved by ch-orch41749 after the20-entry legacy/shared deletion comparison failed. The live/dangling focused regression must run red before this conservative change; the three legacy-only deletion deltas stay explicit.


Active Run6 F1 amendment: owner ruling1889 A relayed41841 activates scope41790;
exact11-file amendment mailed41847 before edits. host.py bootstrap/error report
may name stale expected versus retired/unexpected packages using existing row,
Conflict and State shapes. update.md asks once for the named Codex adoption list,
shows the exact persistent-root command and retained backups, and says frozen
with the command on decline. Retired/unexpected entries stay preserved and are
never adopted; no fallback. source.py/CLI stay marker-only, neutral/Pi unchanged.
The actual e32c06ed~1 install at5204ea06 has80 packages,19 stale expected and no
unexpected names; the named diagnostic regression was RED at498e2ed8. Actual
v13.0.0 at40d25173 is byte/mode-identical and bootstraps without migration.
Formal pass1 has one accepted F1; the next review is pass2 of defaultcap2.


Active Run6 F2 amendment approved by ch-orch41899/41910, plan41909. Every
update.md Bash fence must derive its inputs in that call or require validated
literals bound in the same call. Audit all49 fences for prior variables, arrays
and functions, recording before/after counts. Replace the concatenating maintained
reader/control with separate Bash processes and retain actual revision-move
refusal. On unchanged cdf04386, both current and accepted-migration fresh-shell
regressions failed (2failed13.95s). Already-approved paths only; no native/auth,
neutral/Pi or generator changes. Command remains shorter than2291lines.
Formal pass2 accepted F2. Third pass authorized41899 with exact extra-pass-reason:
F2 is a real correctness defect that the earlier passes and the test harness both missed (a blind instrument), and the fix is narrow.
No fourth pass without owner escalation.

F2 expanded-reader amendment41924 approved41925 before these four path edits.
The expanded26-module run found732pass/4fail. Restore identical locator bytes;
replace two retired shell-loop assertions with actual manifest readers, retaining
init/negative distinctions and adding missing-executable/wrong-inclusion cases.
Explicitly classify the newly derived shared entry without observed claims and
prove an unknown derived newcomer still refuses. Report assertion counts. Third
review only; a material third-pass finding escalates to owner via ch-orch.


Owner ruling at https://github.com/cooneycw/claude-power-pack/issues/1889#issuecomment-7204721638,
relayed by ch-orch41964, unparked B2b-1 with option B and exactly one fourth
review. Plan41957 is approved: the seven paths above plus existing
`tests/test_host_update_command.py`, `docs/scripts/cpp-host-update.md` and
`docs/measurements/host-update-adapters.md`, with own records. No update.md,
parser, frozen reference, baseline JSON, CLI/source/core/Pi or native/auth change.
The gate at279482dc was5fail/14084pass/5skip; all seven corresponding baseline
cases passed unchanged8e. Scratch data-only A/B at022/002 produced identical
80 packages/404 members against both current and frozen transforms, with actual
wrong-byte/mode negatives; only the six-row table deletion is authorized.
Run every listed red case, pinned parity, full verify BEFORE pass4, then the
entire149-control provenance batch. Fourth receipt escalation: ruled_by=owner,
reference=the comment above, raised_cap=4. No fifth pass; material findings on
pass4 return through ch-orch to owner. PR window still requires ch-orch clearance.
