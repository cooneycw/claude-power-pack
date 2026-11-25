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
