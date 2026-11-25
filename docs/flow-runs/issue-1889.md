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
