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
- Approval: pending - concrete plan submitted before product coding
- Delivery: one pi adapter PR, opened only after explicit clearance

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

### Section C - proposed changes (pending approval)

1. `scripts/pi-skill-sync.py` - thin check/write/install/verify-installed CLI, output-root/session-dir policy inputs and explicit adoption; delegates installation to the generic core through the agreed pi adapter.
2. `lib/host_update/pi_adapter.py` - pi package policy, source bundling, positive destination preflight, session-history candidate resolver and adapter callbacks; final module placement agreed with core author before import wiring.
3. `scripts/skills-check.py` - bundled-topic expected-root comparison and strict pi member checks without changing existing canonical/Claude behavior.
4. `scripts/install-drift.sh` - read-only pi installed-fidelity/count reporting against actual fresh expected output; no shared updater enrollment or effective-selection claim from file hashes.
5. `Makefile` - pi build/check/install/verify and focused fixture/control test entry points, with host-local inspection kept distinct from hermetic CI.
6. `.gitignore` - ignore generated pi/skills packages and keep only the maintained README.
7. `pi/skills/README.md` - document generated output, canonical source and regeneration interface.
8. `tests/test_pi_skill_sync.py` - real-builder package inventory/bytes/modes, portable references, malformed inputs, explicit paths, root/cwd/checkout layouts and core adapter integration.
9. `tests/test_pi_skill_boundaries.py` - B1-B6 fixture cases, per-source history exclusions and aliases, adoption/collision safety, syscall transient-write observer and its seeded bad writer.
10. `tests/test_pi_skill_discovery.py` - actual installed builder output into offline fixture pi RPC, membership/source paths and unchanged built-in tool population; real binary guard and explicit unavailable status.
11. `tests/test_skills_check.py` - fresh bundled builder output into existing checker; missing expected package/marker and one-byte reference drift fail; existing unbundled behavior remains valid.
12. `tests/test_install_drift.py` - actual pi adapter report into drift consumer, nonzero expected-population floor, unknown/missing/unmanaged/current and fidelity-vs-effectiveness separation.
13. `controls/pi-skill-install-fidelity/control.json` - register load-bearing pi verifier/control subjects, immutable blind-anchor provenance and complete bad/good/unexaminable cases.
14. `controls/pi-skill-install-fidelity/run-case.sh` - drive real CLI/core subject and assert opposite/unknown verdicts without interpreting skipped observations as proof.
15. `controls/pi-skill-install-fidelity/cases.json` - materialized input definitions for missing member/marker, byte drift, foreign collision, unsupported payload, history/trusted-root escape, transient write and unavailable evidence, each paired with a healthy case.
16. `controls/pi-skill-install-fidelity/README.md` - fixture construction, blind-subject mutations, safety scope and exact negative-control evidence.
17. `controls/census.md` - enumerate new gate/readiness surfaces and their registered controls.
18. `.claude/verify-coverage.json` - account for new scripts not statically reached by a build gate, naming actual consumers.
19. `docs/scripts.md` - index the new thin pi CLI.
20. `docs/scripts/pi-skill-sync.md` - CLI contract, known limits, state/exit meanings and recovery/adoption instructions.
21. `docs/HOST_MANAGED_ARTIFACTS.md` - skills root and exact advisory-lock HOST-SURFACE disclosure; staging/ledger/adoption backup confined within skills root.
22. `docs/measurements/pi/2026-11-25-discovery-reload.md` - durable sanitized probe summary copied with provenance from the immutable note above, before scratch-branch retirement.
23. `docs/flow-runs/issue-1896.md` - append-only approved plan and attributable later disposition.
24. `docs/flow-runs/issue-1896.as-read.md` - helper-produced issue snapshot at approval.
25. `docs/flow-runs/issue-1896.lanes-demonstrated.md` - actual lane results, including unrun host/CI gaps rather than guessed passes.
26. `docs/measurements/counter-model/*-issue-1896.json` - runtime-derived independent exact-head review receipt through the designated reviewer.

Scope: approximately 26 paths, 1,500-2,200 implementation/test/documentation lines;
control fixture/anchor members may require explicit plan refinement before
approval. Generic core code belongs to #1889-A, not this branch. No command
workflow generation, rules, MCP, capability receipts, shared pi updater
enrollment, provider work or pi-in-Kyle runtime is included.

Risks: path normalization must reject forbidden descendants before touching
them; all CLI/env/global/project/default history candidates stay excluded even
when overridden. Settings are read-only/no-lock and malformed/unreadable inputs
fail. Core callbacks must run pi preflight before generic inventory/locking.
The proposed hidden ledger remains a measured candidate until interface review.
No OS credential isolation is promised. Native writers ignoring flock remain
outside cooperative concurrency guarantees. Strace and pi are absent in this
container; their real observations need a bounded fixture host lane, not a mock
or silent skip. Requiring stderr literally empty would reject the measured
no-model warning: distinguish expected fixture startup diagnostics from skill
validation/collision warnings, with that acceptance interpretation reviewed.

Implementation sequence: agree seam; build deterministic packages and path
policy without touching host state; integrate agreed generic core for ownership,
locks, safe refresh/adoption/record reconciliation; wire actual-output readers;
materialize named controls and run bad/good comparisons; checkpoint, independent
review/receipt, paired finish gate and PR CI after clearance. Every changed
load-bearing gate gets committed negative inputs; regression assertions must
run red against pre-fix behavior. Missing source/CLI/audit evidence is unknown,
never a clean result. No full local suites; authorized heavy work uses kyle-lock.

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
| Reader: generic core installation | tested against real output | test_pi_skill_sync.py feeds actual expected packages from pi builder to agreed core adapter |
| Reader: skills-check/install-drift | tested against real output | test_skills_check.py and test_install_drift.py consume fresh real builder/adapter output and actual fixture installed bytes |
| Reader: pi skill loader | not covered | Preparatory probes used synthetic skills; delivered builder output requires real offline fixture RPC host evidence before claiming this reader covered |
| Reader: boundary observer | tested against real output | test_pi_skill_boundaries.py traces actual child operations; seeded stat/outside-root create-unlink must be detected despite clean final snapshot |
| Reader: contextual selection report | tested against real output | Record known bounded project shadowing separately from installed fidelity; unmeasured effectiveness remains unknown |

Pinned compatibility: independently compare untouched Codex generator and real
generated membership/bytes/modes against baseline
`40d25173c8c09987fac851cffa565efdc0f11c72`, with deliberately changed-transform
control. Canonical inputs are never edited to inject pi metadata. Core owns
cooperative same-package serialization (one complete revision and matching
record); pi adapter integration must preserve its no-create LOCK_SH verification,
hand-edited-before-stale rule and explicit record-only reconciliation exception.

Approval requested from the task orchestrator before product coding. This plan
does not declare its own approval or authorize PR creation.
