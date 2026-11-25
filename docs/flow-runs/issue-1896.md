# Flow run record - issue #1896

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=491e55fba4da40ac91d983677dceecde -->
## Run 1

- Run-id:            491e55fba4da40ac91d983677dceecde
- Run-start:         790174a3f3994c5433429ddf8df6fe3296762ce9

- Issue: #1896 (Tier 2), parent #1876
- Approval: granted subject to recorded A1/A2 split and four conditions (mailbox 39937)
- Delivery: separate P1-A1 and P1-A2 PRs, each opened only after explicit clearance

### Section A - intent

CPP's topic guides cannot yet be installed and checked as portable pi skills.
A copied guide can lose its references or overwrite a user's own skill, and a
file that is correct on disk can still be hidden by a project skill of the same
name. This change will build complete topic packages, install only content CPP
owns, and check the installed files against a fresh build while reporting what
was actually inspected. It will use the shared installation machinery rather
than create another independent updater.

### Section B evidence

Verdict: Partially addressed - the design and measured discovery inputs landed;
the topic copier, adapter and boundary acceptance remain necessary.

Issue created 2026-11-22T15:23:33Z. Inspected post-filing commits
`458ee7c108721de090043ba2f70893e69c85dc6e`,
`9af6d36127b5edaebe193ea204ddc87c2370a6ed`, and
`790174a3f3994c5433429ddf8df6fe3296762ce9`, merged PRs #1895, #1898 and #1906.
The merged-PR date search also returned #1882/#1885, both before this issue's
creation time. No post-filing implementation commit touching the proposed pi
copier, shared core, skills-check or install-drift paths was found in this clone's
available history; it is shallow, so this is not a full-history census. The
known current main tree contains no pi copier or host_update core.

Considered related issues #1887/#1888/#1889 and #1897/#1899/#1900/#1904/#1905:
they deliver the shared foundation, later validation or deferred integration,
not a replacement for P1-A. Only this clone's worktree is registered locally;
no unpushed sibling commit touches these paths. Other hosts are not surveyed.
The core author is separately preparing #1889-A and has been asked for concrete
interface artifacts. No guessed core signatures or duplicate generic installer
will be implemented while that interface is unsettled.

Authority: [owner dependency ruling](https://github.com/cooneycw/claude-power-pack/issues/1896#issuecomment-7168423528)
supersedes the older AGY-completion dependency only. #1887's contract is merged;
pi implementation may start as an adapter on its generic core. Shared pi updater
enrollment remains #1900, and owner installation validation remains #1897.

Probe evidence: [sanitized findings at immutable commit 1726e96e](https://github.com/cooneycw/claude-power-pack/blob/1726e96e1807473244d254dc9eacfac85aca689b/.work-probes/pi-probe-findings-2026-11-25.md).
The preparatory helper-run fixtures measured global/explicit discovery,
project-trust gating, silent project shadowing, one inert hidden ledger layout,
and reload presence/removal/restoration. They did not exercise a delivered
copier or prove B1-B6. SourceInfo baseDir is context-dependent; do not assert it
always equals the package path. Pi initializes its own fixture stores; audit
the copier independently of pi startup. Missing fd/rg are observed startup
warnings; propose informational diagnostics, not a hard dependency or download.

Reader search: searched Makefile, install-drift.sh and Woodpecker for existing
generator/checker names; positive hits include Makefile codex-skills targets,
install-drift.sh's fresh-generator call and skills-check managed-root consumer.
Known downstream Codex consumers Kyle/skillc/candidate motivate leaving the
Codex generator and canonical topic inputs unchanged. No downstream pi format
compatibility is claimed before an interface exists.

### Section C - approved P1-A1 delivery

Approval: granted by task orchestrator, mailbox 39937, for the original Section C
at df7c0faa as amended by the four conditions recorded here. This is P1-A1 only;
P1-A2 is a separate later PR. The [stderr ruling](https://github.com/cooneycw/claude-power-pack/issues/1896#issuecomment-7171775775)
requires paired no-CPP-skills baseline diagnostics, reported verbatim, and a
committed bad skill that adds a diagnostic. No PR is authorized by this approval.

1. `scripts/pi-skill-sync.py` - thin check/write/build-fidelity CLI; install/adoption/transactional verification deferred to A2 with explicit unsupported results.
2. `lib/pi_skills.py` - pi-only deterministic package bytes, Markdown0644 policy, source inventory and path/history preflight; neutral data seam for later real-core adapter, no duplicate generic installer.
3. `scripts/skills-check.py` - bundled-topic expected-root comparison, nonzero canonical membership floor and strict no-follow pi member checks; existing canonical/Claude behavior unchanged.
4. `scripts/install-drift.sh` - pi fresh-build fidelity reader with explicit snapshot/unexamined effectiveness; no shared updater enrollment or install writes.
5. `Makefile` - pi build/check/fidelity and focused A1 test/control entry points, host-local versus hermetic scopes explicit.
6. `.gitignore` - ignore generated pi/skills packages, keeping maintained README.
7. `pi/skills/README.md` - generated output/source/regeneration and A1 limits.
8. `tests/test_pi_skill_sync.py` - real-builder inventory/bytes/modes/references, expected-root checker, root/cwd/checkout layouts and seam data.
9. `tests/test_pi_skill_policy.py` - preflight/history candidate/path aliases and bad source inputs; B controls needing no installation.
10. `tests/test_skills_check.py` - actual fresh builder output into checker; missing member/marker and one-byte drift fail; legacy unbundled behavior preserved.
11. `tests/test_install_drift.py` - actual pi builder/fidelity report into drift consumer; absent/unreadable/nonzero expected population and explicit limits.
12. `controls/pi-skill-build/control.json` - register load-bearing A1 builder/fidelity verdicts and committed opposite/unknown fixtures.
13. `controls/pi-skill-build/run-case.py` - invoke actual A1 subject on fixture-owned inputs and assert preconditions/verdicts.
14. `controls/pi-skill-build/anchors/constructed-always-clean.py` - declared blind subject for control rejection evidence.
15. `controls/pi-skill-build/cases/*/case.json` - committed good, missing-member, stripped-marker, byte-drift, unsupported-manifest, history-refusal and unknown-source descriptors; each has defining precondition assertions.
16. `controls/pi-skill-build/README.md` - construction/safety/provenance and known opposite verdicts.
17. `controls/census.md` - enumerate A1 instruments and scope of controls.
18. `.claude/verify-coverage.json` - new script coverage by actual test/Make consumers.
19. `docs/scripts.md` - thin CLI inventory entry.
20. `docs/scripts/pi-skill-sync.md` - A1 CLI/seam/fidelity/exit/refusal contract, explicit A2 limits.
21. `docs/HOST_MANAGED_ARTIFACTS.md` - planned skills/lock host disclosure; A1 writes generated output only, no installs.
22. `docs/measurements/pi/2026-11-25-discovery-reload.md` - durable sanitized probe summary from immutable1726e96e.
23. `docs/flow-runs/issue-1896.md` - approved plan/amendment and attributable disposition.
24. `docs/flow-runs/issue-1896.as-read.md` - helper-produced issue snapshot.
25. `docs/flow-runs/issue-1896.lanes-demonstrated.md` - actual results and explicit unknown host lanes.
26. `docs/measurements/counter-model/*-issue-1896.json` - independent runtime-derived receipt for A1 checkpoint.

27. `controls/pi-bundled-parity/control.json` - register the actual bundled-topic reader separately from the producer.
28. `controls/pi-bundled-parity/cases/*/case.json` - committed good/missing/marker/byte/manifest/unknown descriptors for the real checker.
29. `controls/pi-drift-reader/control.json` - register the advisory drift reader's actual pi JSON verdict separately, not its unconditional process exit.
30. `controls/pi-drift-reader/cases/*/case.json` - committed good/missing/marker/byte/manifest/unknown descriptors for the actual drift reader.

31. `controls/pi-skill-build/codex-baseline.json` - immutable membership/byte-hash/mode inventory independently built at pinned40d25173; real generator plus deliberately changed transform exercise positive/opposite comparison.

Scope: A1 approximately 30 path entries plus materialized case seeds, roughly
900-1400 lines; the large installation and runtime portions have moved to A2.
Generic core code belongs to #1889-A. Adapt control registration to repository
schema without expanding product scope; declare added fixture seed paths before
shipping. No shared updater enrollment, rules, MCP, capabilities, command
workflow generation, provider work or pi-in-Kyle implementation.

Risks: fail before forbidden-descendant touches, including symlink aliases and
all overridden history candidates. Settings may be read only at exact bounded
paths; malformed/unreadable configuration fails. Root traversal must not inspect
credential neighbors. A1 staged-tree fidelity is a read-only file snapshot,
not a cooperating writer transaction or runtime effectiveness claim. Source
inventories must not silently drop unsupported content.

A2 reserved follow-up: agreed `lib/host_update/pi_adapter.py` imports real core;
CLI install/adopt/verify-installed ownership/record/lock integration; actual
installed-output pi RPC; B1-B6 syscall observer and install concurrency/adoption
controls. No guessed signatures, placeholder installer or false A1 completion.
The real-pi RPC and strace observer execute in a disposable HOST FIXTURE lane
routed through the task orchestrator; both binaries are absent here. Until that
lane runs, status is UNKNOWN/unexecuted, never green from a binary-guard skip.
Pair each actual RPC with no-CPP-skills baseline in the same fixture; no added
diagnostic is permitted. Preserve baseline verbatim; malformed/colliding fixture
must add a diagnostic. A1 does not execute or claim either A2 observation.

A1 sequence: deterministic bytes/path preflight; bundle-aware checker/fidelity
readers fed actual builder output; materialized bad/good/unknown controls;
focused Make checks; checkpoint review and receipt; paired finish gate; PR only
on clearance. Full suites remain PR CI only; authorized heavy exceptions use
kyle-lock. Codex parity stays pinned to40d25173; unrelated output drift requires
an explicit re-pin reason (Nit Store7168403197), never silent baseline refresh.

### Lanes for this change

| Lane | Answer | Evidence planned or limit |
|---|---|---|
| Checkout | will test | main checkout / linked worktree - fixture builders invoke the real CLI in both layouts |
| Harness | not covered | Claude install / Codex install unchanged; real pi installed-output RPC fixture is the new harness observation, host lane pending |
| Driver | not applicable | No flow:auto or delegated-driver protocol change; native authoring is not pi runtime evidence |
| Coordination | not applicable | Core/adapter operates with no Kyle authority protocol changes |
| CI provider | not covered | Woodpecker PR CI will run after clearance; no GitHub Actions or provider matrix claim |
| Project state | will test | a repository that has adopted a feature's file or record / one that has not - managed, unmarked, absent and malformed fixture installs |
| Toolchain version | not covered | Host/container Python and CI's pinned toolchain only; no version matrix |
| Clone shape | will test | a full clone with all refs / a fresh or shallow main-only clone - source inventory never depends on branch history; parity uses explicitly fetched baseline |
| Run location | will test | invoked from the CPP root / from another directory - actual CLI tests with explicit source root |
| Gate target | will test | CPP itself / a consumer with its own interpreter and PATH - fixture adapter callers and helper invocation do not inherit a wrong cwd/interpreter assumption |
| Wave role state | not applicable | No wave registration/release code or record changes |
| Reader: generic core installation | not covered | A2 integrates actual A1 package bytes with delivered core; no generic installer ships in A1 |
| Reader: skills-check/install-drift | tested against real output | test_skills_check.py and test_install_drift.py consume fresh real builder/adapter output and actual fixture installed bytes |
| Reader: pi skill loader | not covered | Preparatory probes used synthetic skills; delivered builder output requires real offline fixture RPC host evidence before claiming this reader covered |
| Reader: boundary observer | not covered | A2 host fixture strace lane; UNKNOWN until actual child traces and seeded transient-write control execute |
| Reader: contextual selection report | tested against real output | Record known bounded project shadowing separately from installed fidelity; unmeasured effectiveness remains unknown |

Pinned compatibility: independently compare untouched Codex generator and real
generated membership/bytes/modes against baseline
`40d25173c8c09987fac851cffa565efdc0f11c72`, with deliberately changed-transform
control. Canonical inputs are never edited to inject pi metadata. Core owns
cooperative same-package serialization (one complete revision and matching
record); pi adapter integration must preserve its no-create LOCK_SH verification,
hand-edited-before-stale rule and explicit record-only reconciliation exception.

Approval recorded from mailbox 39937; the plan amendment precedes product code.
PR creation remains separately gated on explicit clearance.

### Approved boundary clarification (mailbox 39944)

The orchestrator permits only no-follow lstat/readlink of an explicitly selected
history root and its ancestors, solely to resolve exclusions. No listing,
opening or descent beneath that history root is allowed. Credential-file
metadata remains forbidden. Dangling/looping links or inaccessible ancestors
are refuse/unknown, never a clean exclusion. The A2 syscall observer must encode
this closed allowance and catch seeded descendant-stat and credential-stat
violations; A1 path-policy tests exercise the same input distinctions without
claiming syscall evidence. This is an attributable approved amendment, not a
relaxation inferred by the implementer.

Control registration refinement: separate producer/bundled/drift subjects and finite per-case descriptors materialize the already approved opposite-input scope; no new product behavior.

### Generator parity ruling (mailbox 39963)

Approval authority clarified the claim: execute the generator pinned to
40d25173 and the candidate generator against the SAME candidate input tree;
compare complete output membership, bytes and modes. A deliberately changed
transform must fail that comparison. Separately enumerate payload differences
from independently built historical `40d25173` output and attribute each to an
intentional source change; any unattributed difference is a failure. This does
not permit silent re-pinning or an unqualified claim about different-input trees.

At the reviewed product head `6d06ac7b`, the separate same-input executions each
produced 404 members with no generator-parity difference. Historical payload
comparison separately found 0 differences, hence no changed payload attribution
rows. The generator code SHA256 was independently equal for both sources. The
committed deliberately changed real transform writes altered SKILL.md output and
is rejected. These are separate claims and must be described separately in the
future PR body. This record-only amendment changes no reviewed product bytes.

### Counter-model pass 1 corrections (mailbox 39991)

Accepted F1-F4. F1 now requires disjoint roots in both directions, including
agent/project/history roots nested below output, with materialized inverse
cases. F2 separates regular non-executable source permissions from exact 0644
generated/fidelity members; GOOD source-0664 and BAD installed-0664/executable
cases retain both sides of that contract. F3 host-global fidelity ignores
caller project settings through an explicit canonical-root-only read context;
ordinary build/check preflight still reads bounded project inputs. F4 compares
exact pinned generator source and candidate source on the SAME candidate inputs,
under both 022 and 002 umasks, with a legitimate input change and rejected
changed transform. Historical payload inventory is separate documentary data.

The exact pinned reference is additionally retained at
`controls/pi-skill-build/reference/codex-skill-sync-40d25173.py`, byte-digest
checked before execution, so this instrument does not depend on Git availability
or network fetches in CI. This is frozen evidence source, not a second product
generator; the maintained generator remains unchanged. Extra inverse/mode/cwd
case descriptors materialize the accepted corrections within the approved
control families. No installation or A2 scope is introduced.

Before product fixes, five new F1/F2/F3 regression cases failed on the reviewed
code: three inverse-root cases failed to refuse; 0664 source was incorrectly
refused; unrelated caller settings changed host fidelity. All five pass after
the fix. The old frozen-output parity test also failed under umask 002 before
replacement. The new same-input instrument passes both umasks, tolerates an
intentional input change and rejects the changed real transform. Focused total:
162 passing cases; actual RPC/syscall acceptance remains UNKNOWN/unexecuted A2.

Supplemental control-strengthening suggestion recorded without widening this
fix: [axis-specific blind anchors](https://github.com/cooneycw/claude-power-pack/issues/1725#issuecomment-7172647280).

<!-- flow-run n=2 id=94e96cda99ab4be19bb7068942115d12 -->
## Run 2

- Run-id: 94e96cda99ab4be19bb7068942115d12
- Run-start: 2f5c96be2d8c7a88c47ecf48951673fc7ac6e4ca
- Issue: #1896 (Tier 2), parent #1876
- Status: PROPOSED P1-A2 amendment; preparation authorized, implementation waits
  for complete #1889-A core evidence; no PR authorization.

### Section A - remaining intent

P1-A1 merged in #1907. It builds and compares portable pi packages but does not
install them. A2 will connect those same package bytes to the real managed-copy
core, preserve foreign and hand-edited content, and measure discovery and
filesystem boundaries against an actual fixture installation. An installed-byte
verdict remains separate from contextual runtime selection. Owner installation
and undo validation remain #1897; shared updater enrollment remains #1900.

### Section B - inputs and dependency

Main `2f5c96be2d8c7a88c47ecf48951673fc7ac6e4ca` includes A1, its independent
review receipt, 162 focused cases and committed builder/reader controls. The
direct finish gate at A1 head `3e27f87320b70568e094810636ce97c868bed509`
reported paired ok/exit 0 after fetching full history. Both full suites reported
13,687 passed / 4 skipped. This is A1 evidence, not A2 runtime acceptance.

The public core seam was frozen at `91635a1d`; WIP implementation inspected at
`405fd23c9e0a6494ff857ebd736636b9b534cfbb` adds the pure public
`build_manifest_sha256` helper without changing callback/type signatures.
That checkpoint has partial core tests, not complete control/concurrency
evidence or merge clearance. Do not copy its internals into the pi adapter or
start A2 implementation from it. Reconfirm the final merged core revision and
seam before recording implementation approval. Current main was merged into
the working branch without rebasing after #1907.

### Section C - proposed core integration

`PiAdapter.harness` is `pi`. `preflight(Request) -> Policy` reuses the A1 bounded
path/history checks before generic root IO, then selects only canonical
`<agent>/skills`. Proposed management layout is hidden
`<agent>/skills/.cpp-managed/ownership.json` and
`<agent>/skills/.cpp-managed/work`, with the exact advisory lock
`<agent>/.cpp-skills.lock`. The lock is the only writable location outside
skills. The host disclosure and real loader must validate this final layout;
the earlier hidden-ledger probe tested one candidate, not every core artifact.
The pure member predicate accepts only valid relative Markdown paths at exactly
0644; the builder validates UTF-8 bytes. Settings/tools/extensions/auth/history
are never write scopes.

`discover(Policy, Request) -> Discovery` uses only approved skills/ledger scopes
and explicit install selection. Authentication files, generic agent-directory
enumeration and arbitrary project searches cannot establish selection. An
unmarked collision remains unmanaged until explicit per-package adoption.
Any legacy source-marker adoption needs an explicit contract decision rather
than treating a marker alone as ownership. No new automatic updater enrollment.

`build(Revision, Policy) -> ExpectedBuild` calls the actual A1 builder against
the immutable revision snapshot, maps every package/member to
`ExpectedPackage`/`ExpectedMember`, and calls `build_manifest_sha256` on that
same population. The core validates revision, state, records and publication;
the adapter does not duplicate staging, ledger reconciliation or locking.
`inspect(adapter, request)` supplies verify-installed; `refresh(adapter,
request)` supplies explicit install/adoption. No placeholder implementation or
fixture-only core is acceptable production evidence.

CLI proposal: add mutually exclusive `--install` / `--verify-installed` and
explicit `--adopt SLUG` (repeatable, install only); preserve A1 build/check and
snapshot interfaces. Installation rejects `--output-root`; only canonical
agent skills is eligible. The immutable source revision binding and any clean
source requirement must be visible in errors. Backup is core-managed, inside
the approved management scope, and reported by exact retained location. Map
core known refusal/failure, unknown and not-applicable outcomes faithfully;
never convert unexamined/zero population into success. A1 host snapshots keep
their caller-independent context and global history guards.

Proposed files, to refine explicitly after the core lands:

1. `lib/host_update/pi_adapter.py` - thin production callbacks only.
2. `scripts/pi-skill-sync.py` - real core install/adopt/verify CLI and JSON.
3. `lib/pi_skills.py` - minimal shared policy seam only if required; no change
   to deterministic package bytes without separate attribution/parity evidence.
4. `tests/test_pi_skill_install.py` - real-core installs, ownership, adoption,
   no-create shared verification, record-only reconciliation, dirty/mismatched
   revisions, hand-edited-before-stale precedence and fault outcomes.
5. `tests/test_pi_skill_concurrency.py` - actual subprocess lock/content races,
   pipe handshakes and bounded waits; no sleep-based race assertions.
6. `tests/test_pi_skill_sync.py`, `tests/test_pi_skill_policy.py`,
   `tests/test_install_drift.py` - preserve existing interfaces and guards.
7. `controls/pi-skill-install/control.json`, `run-case.py`, `README.md`,
   `anchors/constructed-blind.py` - actual adapter/core subject, narrowly
   declared anchor deficiencies, known-good/bad/unknown cases.
8. `controls/pi-skill-install/cases/` - explicit descriptors for fresh/current,
   edited, foreign, adopted-with-backup, missing-member, stripped-marker,
   changed-reference, unsupported-payload, root-refusal and unreadable cases;
   list individual added paths before implementation approval.
9. `scripts/pi-host-fixture.py` - explicit fixture-only host dispatcher and
   bounded child cleanup, never owner installation/discovery.
10. `scripts/pi-syscall-audit.py` - independent actual-child trace classifier.
11. `tests/test_pi_host_fixture.py`, `tests/test_pi_syscall_audit.py` - parser,
    lifecycle, path-resolution/descriptor/child and result-reader cases.
12. `controls/pi-rpc-observer/` and `controls/pi-syscall-observer/` - committed
    discriminating inputs and anchors, with every concrete file declared before
    implementation; expected/missing response, added diagnostic, transient
    write, auth-stat and forbidden-history-descendant evidence included.
13. `Makefile`, `controls/census.md`, `docs/scripts.md`, relevant script docs -
    register host prerequisites and hermetic controls separately.
14. `docs/HOST_MANAGED_ARTIFACTS.md`, `pi/skills/README.md`,
    `docs/scripts/pi-skill-sync.md` - installed scope, lock/backup/undo and limits.
15. This run record, its as-read/lane records, independent review receipt and
    a sanitized host measurement record; no raw credential or private paths.

No generic core internals, Codex generator, canonical topics, providers,
runtime/container isolation, rules/MCP/commands or updater driver changes.

### Lanes and acceptance before any completion claim

Hermetic local tests cover ordinary/linked checkout, root/other cwd,
full/shallow source fixtures, explicit selected/unselected and adopted/unmarked
state. Source binding must work for the supported clone shapes without guessing
missing revisions. Core process/concurrency controls are consumed directly and
pi integration asserts a complete revision plus matching record. Preserve
independent A1 same-input pinned Codex parity and disclose its deferred parser
coverage. A2 regressions must fail on unchanged predecessor code where applicable.

The real pi loader and actual child-syscall observer are HOST FIXTURE lanes,
routed for execution after review of immutable scripts and commands. Draft
commands and required opposite cases are in
[the host-fixture protocol](../measurements/pi/issue-1896-a2-host-fixture-plan.md).
They are UNKNOWN/unexecuted until returned records establish each claim.
The RPC lane pairs no-CPP-skills diagnostics with actual installed output and
an added-diagnostic negative; it does not claim authentication isolation.
The syscall lane excludes pi startup, follows descendants, and rejects transient
writes and forbidden metadata probes even when final snapshots match.

History allows only no-follow lstat/readlink of explicitly selected roots and
ancestors, never listing/opening/descent. Credential-file metadata has no such
allowance. Seeded credential-stat and history-descendant-stat cases must fail;
the observer must also show allowed root resolution and legal isolated output.
Unknown syscall syntax/path/fd resolution or incomplete trace is UNKNOWN.

Harness/provider/container/version-matrix coverage is unclaimed. Host fixture
pi version and trace-tool versions are recorded exactly; missing binaries are
UNKNOWN, not green skips. CI is pending future PR clearance. Wave/coordination/
delegated-driver behavior is not changed. Owner validation remains separate.

Sequence: proposed amendment review; final core evidence/seam confirmation;
explicit implementation approval; real adapter and local opposite controls;
immutable host scripts reviewed and executed by the authorized fixture lane;
independent review/receipt; direct paired finish gate; PR only on clearance.

### Proposed control paths refined (mailbox 40148)

This records concrete planned paths only. It grants no implementation approval
and adds no control code or fixture evidence. The final plan still waits for
stable #1889-A internals. No provisional counter-model read is requested.
The earlier directory-level entries resolve to the files below; no glob is a
file declaration. Any additional seed/helper path requires another explicit
plan amendment before implementation.

Each descriptor is `case.json`, containing finite synthetic inputs and explicit
preconditions. The runner materializes them beneath its disposable root and
invokes the actual subject; it does not emulate the product verdict. Raw RPC
and syscall parser seeds are embedded data in the descriptors, so no undeclared
transcript files are implied. Actual host traces/diagnostics remain separate
execution evidence; synthetic parser cases alone cannot satisfy that lane.

Install control scaffolding:

- `controls/pi-skill-install/control.json`
- `controls/pi-skill-install/run-case.py`
- `controls/pi-skill-install/README.md`
- `controls/pi-skill-install/anchors/constructed-blind.py`

Install descriptors:

- `controls/pi-skill-install/cases/fresh-install/case.json`
- `controls/pi-skill-install/cases/current-install/case.json`
- `controls/pi-skill-install/cases/hand-edited-before-stale/case.json`
- `controls/pi-skill-install/cases/foreign-collision/case.json`
- `controls/pi-skill-install/cases/adopt-with-backup/case.json`
- `controls/pi-skill-install/cases/missing-expected-skill/case.json`
- `controls/pi-skill-install/cases/stripped-source-marker/case.json`
- `controls/pi-skill-install/cases/modified-reference/case.json`
- `controls/pi-skill-install/cases/auth-helper-rejected/case.json`
- `controls/pi-skill-install/cases/path-escape-rejected/case.json`
- `controls/pi-skill-install/cases/manifest-rejected/case.json`
- `controls/pi-skill-install/cases/executable-rejected/case.json`
- `controls/pi-skill-install/cases/output-under-trusted-config/case.json`
- `controls/pi-skill-install/cases/output-under-sessions/case.json`
- `controls/pi-skill-install/cases/unreadable-install/case.json`
- `controls/pi-skill-install/cases/zero-expected-population/case.json`

Root descriptors enumerate a finite matrix in JSON: direct/nested/inverse and
alias spellings; CLI/env/global/project/default history sources and overridden
non-empty candidates; external history/skills; legal isolated comparison. A
runner must report each matrix row independently and assert the defining root
relationship before calling the subject. Unreadable uses an actual permission
boundary or is UNKNOWN; running as a privileged reader is not a negative case.

RPC observer scaffolding:

- `controls/pi-rpc-observer/control.json`
- `controls/pi-rpc-observer/run-case.py`
- `controls/pi-rpc-observer/README.md`
- `controls/pi-rpc-observer/anchors/constructed-blind.py`

RPC descriptors:

- `controls/pi-rpc-observer/cases/populated-baseline-pair/case.json`
- `controls/pi-rpc-observer/cases/missing-response/case.json`
- `controls/pi-rpc-observer/cases/duplicate-response-id/case.json`
- `controls/pi-rpc-observer/cases/empty-success/case.json`
- `controls/pi-rpc-observer/cases/missing-expected-skill/case.json`
- `controls/pi-rpc-observer/cases/malformed-response/case.json`
- `controls/pi-rpc-observer/cases/added-diagnostic/case.json`
- `controls/pi-rpc-observer/cases/replaced-builtin-tool/case.json`
- `controls/pi-rpc-observer/cases/unavailable-tool-inventory/case.json`

The good pair includes a non-empty baseline diagnostic so "no added diagnostic"
cannot mean "ignore stderr" or "stderr must always be empty". Added-diagnostic
data is a reader opposite input; the separate host malformed-skill run must
produce an actual additional diagnostic. Unsupported tool inventory is UNKNOWN.

Syscall observer scaffolding:

- `controls/pi-syscall-observer/control.json`
- `controls/pi-syscall-observer/run-case.py`
- `controls/pi-syscall-observer/README.md`
- `controls/pi-syscall-observer/anchors/constructed-blind.py`

Syscall descriptors:

- `controls/pi-syscall-observer/cases/allowed-install/case.json`
- `controls/pi-syscall-observer/cases/allowed-readonly-verify/case.json`
- `controls/pi-syscall-observer/cases/auth-file-stat/case.json`
- `controls/pi-syscall-observer/cases/transient-trusted-write/case.json`
- `controls/pi-syscall-observer/cases/history-root-resolution/case.json`
- `controls/pi-syscall-observer/cases/history-descendant-probe/case.json`
- `controls/pi-syscall-observer/cases/child-descriptor-relative-write/case.json`
- `controls/pi-syscall-observer/cases/readonly-verify-created-lock/case.json`
- `controls/pi-syscall-observer/cases/truncated-path/case.json`
- `controls/pi-syscall-observer/cases/unresolved-directory-fd/case.json`
- `controls/pi-syscall-observer/cases/incomplete-child-trace/case.json`

History data pairs allowed no-follow ancestor/root operations with forbidden
descendant stat/list/open operations. Child/fd data exercises cwd and descriptor
resolution with actual annotated trace syntax selected for the pinned strace;
unsupported relevant syntax is UNKNOWN. Known-bad fixture traces distinguish
failed forbidden probes from successful transient writes. The live host lane
still must trace the seeded stat/write child, not merely replay these strings.

Each family's constructed anchor declares its exact missed BAD verdicts and
retained GOOD/UNKNOWN behavior. Provenance stays "constructed", without a
historical-regression claim. Registration must demonstrate rejected known-bad
inputs, accepted known-good inputs, explicit UNKNOWNs and the declared anchor
misses. Descriptor count alone is not detection evidence.

### Real-core binding amendment for approval (mailbox 40215)

Core #1889-A merged in #1908 at main
`adf70c291cf3aa457e56a21cec17983dc761da13`. This supersedes Run 2's earlier
WIP dependency and stub-based assumptions; it does not grant coding approval.
Main has been merged into `issue-1896-pi-a2-plan` without rebasing. Inspected
the merged `driver.py`, `scope.py`, `store.py`, adapter documentation and
core/transaction test cases. A2 now binds to these real semantics:

1. **Mandatory shared-resource locks.** Proposed pi `Policy` retains canonical
   install root `<agent>/skills`, ledger
   `<agent>/skills/.cpp-managed/ownership.json`, work root
   `<agent>/skills/.cpp-managed/work` and primary lock
   `<agent>/.cpp-skills.lock`. The core additionally derives
   `<agent>/skills/.cpp-managed/.ownership.json.cpp-lock` and
   `<agent>/skills/.cpp-managed/.work.cpp-lock`. These are mandatory cooperating
   resource locks, not optional adapter settings. Core acquisition deduplicates
   and orders opened device/inode identities, so aliases or different primary
   locks do not remove shared-ledger/work serialization. All three exact lock
   paths enter host disclosure and the syscall allowance. Only the primary lock
   lies outside skills; none of their parents becomes a new enumeration scope.
   Refresh opens/creates locks with exclusive locking; verify opens existing
   locks read-only/shared, creates no lock/root/directory, and retries if a
   previously absent lock appears during inspection. Persistent derived locks
   stay outside work cleanup. Missing locks alone are not proof of failure or
   permission to create them during verify.
2. **Ancestor authority belongs to pi preflight.** The core opens install root
   and descendants with no-follow semantics, while allowing system aliases
   above that approved root and following the explicitly approved lock parent.
   Therefore pi must validate user-controlled home/agent/skills prefixes and
   the primary lock's parent before granting `Policy`, before discovery or any
   core access. Reuse A1's stricter ancestor no-follow checks; do not infer that
   every above-root alias is safe just because core permits system aliases.
   No relaxation of A1 protected-root, credential-path or every-history-
   candidate guards is proposed. An allowed system-alias policy, if needed,
   requires an explicit amendment rather than broad `resolve()` acceptance.
   Source snapshot prefixes are likewise adapter-approved. Trace opposites
   include agent/lock-parent alias escape above skills and symlink root/member
   below it; refusal must precede target access.
3. **Dual identity always refuses.** `PiAdapter.harness = "pi"` is a stable
   ledger namespace, not an adoption mechanism. The core checks all namespaces
   in the same approved ledger for an expected package claimed by another CPP
   identity. It reports unmanaged and refuses refresh even with explicit
   adoption, before transaction publication. Preserve the other identity's
   records and installed bytes. Renaming/copying an identity needs a separately
   reviewed migration, absent from A2. Test same-byte dual claims as well as
   edited claims; fidelity equality cannot authorize a second owner. This
   inspection reads the exact ledger, not other harness installations.
4. **Record-only reconciliation is narrow.** Core inspection still reports the
   native conflicts against the prior record; verify never updates metadata.
   Refresh may reconcile only when complete installed membership/bytes/modes
   equal the fresh build, prior ownership is valid for every expected package,
   sources match, package key sets match, and no other identity owns a package.
   Retired absent member records can then be removed. The adapter passes this
   result through, including `metadata_refreshed`; it must not rewrite package
   files to implement the exception or turn unmarked files into owned files.
   Core may write its pending journal/ledger and clean its transaction under
   management scope. Tests distinguish those allowed writes from package
   republishing and assert exact package bytes/modes and stable file identity.
   Any installed mismatch, orphan package, invalid ownership, foreign identity
   or changed canonical source prevents this exception. Hand-edited-before-
   stale remains the normal rule outside it.

Public callbacks/value types remain the ones already mapped in Section C.
Use real `inspect` / `refresh` and public `build_manifest_sha256`; no copied core
transaction logic. Core source validation binds a full revision to a clean
snapshot before/after build and strips inherited Git redirection. The pi builder
must also read the approved pinned canonical inputs, not silently attribute
ignored/untracked source members to that commit; source-binding integration
tests include that distinction. No fixture-core installation stands in for pi.

Additional concrete descriptors required by the real behavior:

- `controls/pi-skill-install/cases/dual-identity-refused/case.json`
- `controls/pi-skill-install/cases/record-only-reconciliation/case.json`
- `controls/pi-skill-install/cases/record-only-unmanaged-refused/case.json`
- `controls/pi-skill-install/cases/user-prefix-alias-refused/case.json`
- `controls/pi-skill-install/cases/ignored-source-member-refused/case.json`
- `controls/pi-syscall-observer/cases/derived-locks-refresh/case.json`
- `controls/pi-syscall-observer/cases/derived-locks-existing-only-verify/case.json`
- `controls/pi-syscall-observer/cases/record-only-management-writes/case.json`
- `controls/pi-syscall-observer/cases/user-prefix-alias-probe/case.json`

Local real-core integration tests additionally contend each actual derived lock
with a subprocess, demonstrate verify's no-create behavior for all three lock
paths, and ensure different primary locks cannot bypass shared-resource
coordination. Those tests consume core behavior instead of assuming the primary
lock covers everything. Existing declared concurrency/installation test files
hold these cases; no additional implementation files are implied.

The [host protocol](../measurements/pi/issue-1896-a2-host-fixture-plan.md)
retains both RPC and syscall fixture lanes and now names the exact derived
lock allowances and record-only distinction. Host commands remain drafts until
implemented, pinned and reviewed; execution goes through the orchestrator.
Approval requested on this real-core amendment before any A2 code. No provisional
counter-model review, implementation or PR has been requested or performed.

### Run 2 implementation approval (mailbox 40218)

Approval granted for the plan at
`e0c018ea1b77bb703ebd6513c39d32ddc8d59fd2`. Implement on the branch merged
from current main without rebasing and retain this plan history. Host RPC and
syscall evidence remains UNKNOWN locally and in CI until the frozen committed
probe is fetched with `git show <sha>:path` and executed through the authorized
host lane. Record returned results in the lane record. Every acceptance item
needs actual evidence before claiming completion; otherwise a future PR uses
Refs #1896 and names the remaining work without closing keywords. Committed
negative controls, red-first regressions, direct paired finish gate with full
history, independent runtime receipt and PR CI remain required. Freeze code
when requesting review. Branch pushes are authorized; PR opening requires
separate clearance. This approval precedes A2 product changes.

Run 2 concrete execution-path refinement: the already planned record-only
package-write opposite is materialized at
`controls/pi-syscall-observer/cases/record-only-package-write/case.json`.
The host command relay is committed at
`docs/measurements/pi/issue-1896-a2-host-probe.sh`, implementing the authorized
immutable probe-file handoff, not another product entry point.
Trace-completeness refinement: add
`controls/pi-syscall-observer/cases/omitted-child-trace/case.json`; its cloned
child is absent entirely, unlike the existing truncated-child fixture.
