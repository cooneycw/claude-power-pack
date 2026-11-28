# Flow run record - issue #1926

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=5cd88489f9844c7e9c3239fe585c3062 -->
## Run 1

- Run-id:            5cd88489f9844c7e9c3239fe585c3062
- Run-start:         a0dbd0b7c42c9f95bef8cc9eeb7bd75c8eca014f
- Issue:             #1926
- Base SHA:          a0dbd0b7c42c9f95bef8cc9eeb7bd75c8eca014f
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run140:ch-orch, mailbox 43691 (plan 43690); managed start disposition 43701/43703
- Recorded at:       2026-11-28T02:29:23.629320+00:00

### Section A - What this issue wants
The monthly report misses fixes whose titles omit the parenthesized area name. This makes its list of fixes smaller than the work actually merged. Admit the two conventional scope-less forms while preserving existing rows; measure possible PR-body provenance recovery without adopting it before #1877.

### Section B evidence
Since filing 2026-11-27T10:50:29Z, inspected 3b8116df (PR1968 pinned archive) and fc0624e7 (PR1962 kinds); other merged PRs inspected: 1974,1971,1969,1966,1954,1928,1922. None addresses the two title filters. Related #1925 is closed; #1949 remains separate; #1877 capture prerequisite remains open. No unpushed sibling report changes. Pinned Nov1..Nov28T02:21:26Z populations: Kyle86->90, skillc19->19, CPP65->81; aggregate170->190 with no removals. Capital Fix-space samples recorded and excluded pending a later decision. Managed host preflight refused installed engine; orchestrator43701/43703 explicitly supplied direct-worktree/check-out-local procedure, without claiming preflight success or changing managed installation.

### Section C - the approved plan
1. `scripts/review-yield-report.py` - one exact case-sensitive shared predicate admits fix: and fix!: in collection/rendering.
2. `tests/test_review_yield_report.py` - collection/render regressions, near misses, frozen unchanged-row equality, generated and installed readers.
3. `tests/fixtures/review-yield-report/title-populations.json` - old/new populations side by side, title cases and unchanged output.
4. `docs/scripts/review-yield-report.md` - document exact expanded title coverage and bounds.
5. `docs/measurements/review-yield/issue-1926-title-populations.md` - sampled Fix-space titles, live query cutoff/counts, PR-body recovery census and proposed attribution only.
6. `controls/pi-skill-build/codex-baseline.json` - measured value-only refresh of existing monthly-create report row, pre-approved43691; send before/after before commit.
7. `controls/antigravity-skill-build/codex-baseline.json` - measured value-only refresh of existing monthly-create report row, pre-approved43691; no new members/rows.
Scope: approximately250 lines plus fixtures and generated plan/as-read records. Part2 remains count/proposal only until1877 lands. Partial PR Refs1926, no closing reference.
Risks: collection/render divergence, misleading denominator, unchanged-row drift, ambiguous Fix-space adoption, baseline growth. Shared predicate and committed known-bad/good cases plus actual predecessor reds address these; no new baseline members allowed.
No material concern found with the adjusted approach; silently adopting Fix-space or PR-body overrides would undermine reproducibility and is deferred.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test - main checkout / linked worktree, with hermetic fixture-owned installs. |
| Harness | will test - Claude install / Codex install, actual installed helper and generated monthly-create script; live Claude not covered. |
| Driver | not applicable; driver procedures unchanged. |
| Coordination | not applicable; title report has no coordination coupling. |
| CI provider | not applicable; no provider parsing changes. |
| Project state | will test - a repository that has adopted a feature's file or record / one that has not; missing and malformed fixture sources stay visible. |
| Toolchain version | will test - the host or container's installed versions; CI's pinned uv and Python covered only by PR pipeline, no local version matrix. |
| Clone shape | not applicable; unchanged pinned GitHub archive reader, no local clone-shape dependency. |
| Run location | will test - invoked from the CPP root / from another directory, through real fixture CLI. |
| Gate target | not applicable; report does not run consumer interpreter. |
| Wave role state | not applicable; no wave role changes. |
| CI shape identity | not covered; no opt-in real-root/local claim. |
| Source permissions | not applicable; string classification is independent of file umask. |
| Home and temporary paths | existing hermetic install tests use private HOME; no symlink-TMPDIR claim. |
| Tool discovery | existing CLI fixtures stage transports; no new discovery behavior. |
| CI environment | focused fixture logic is independent of CI; full gate and PR CI exercise ordinary supported environment. |

Reader: monthly-create Claude installed helper - actual fixture CLI, both checkout layouts.
Reader: generated Codex monthly-create - actual generated script and canonical contract fed fixtures; source/mirror read.
