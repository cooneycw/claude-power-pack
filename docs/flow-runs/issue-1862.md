# Flow run record - issue #1862

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=ba462601dcef4525a733360a24ef3fd9 -->
## Run 1

- Run-id:            ba462601dcef4525a733360a24ef3fd9
- Run-start:         de3fb38e759480439355be6aa83dc3f56a07a214
- Issue:             #1862
- Base SHA:          de3fb38e759480439355be6aa83dc3f56a07a214
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the user (owner), in-session "approve" at Step 3, also taken as the #1850 Q2 ruling the issue asks for
- Recorded at:       2026-11-20T12:10:13Z

### Section B evidence
commits since 2026-11-20T11:59:14Z touching scripts/counter-model-receipt.py, .claude/commands/flow/auto.md, docs/agents/counter-model-evidence.md: none. Merged PRs since 2026-11-20: none. Duplicate/superseding issues: none (siblings #1863, #1864, #1865 have different scope). Host: no sibling worktree carries unpushed commits on those paths.

### Section C - the approved plan
1. `scripts/counter-model-receipt.py` - closed per-issue plan_record_paths(issue) set (issue-N.md, .as-read.md, .lanes-demonstrated.md); _artifact_binding binds to a first-parent ancestor whose diff to HEAD lies wholly inside that set and records reviewed_artifact.plan_record_move {head, paths}; any other path still refuses, naming it; validate shape-checks plan_record_move against the issue's set
2. `tests/test_counter_model_adapters.py` - positive plan-only move (both scopes), negative control one non-plan line refused, another issue's plan record refused, validator refuses a hand-built move outside the set, parity with flow-plan-record.py path functions; negative control run red on the pre-fix writer first
3. `.claude/commands/flow/auto.md` - Step 6 states the rule in one line, net zero words against the 9120 budget
4. `docs/agents/counter-model-evidence.md` - paragraph on plan-record moves: what is bound, what is recorded, other paths still need review
5. `docs/reference/flow-auto-rationale.md` - keep the copied checkpoint sentence at :835 true
6. `changelog.d/1862.md` - changelog fragment

Scope: Tier 2, 6 files, ~150-200 lines. Risks: widening a gate that lets work through (bounded by the closed per-issue set, committed negative controls and validate refusing hand-built moves); a main-merge after review stays refused (unchanged, not relaxed); auto.md word budget.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | not applicable | writer reads git from its cwd; diff is layout-independent |
| Harness | not applicable | one shared script; Codex mirror of auto.md is generated |
| Driver | not covered | delegated drivers carry no re-review sentence; the writer change applies to every driver alike |
| Coordination | not applicable | no Kyle path |
| CI provider | will test | Woodpecker (runs the suite and the receipt corpus validate); not GitHub Actions, not none recorded |
| Project state | will test | both values: a repository that has adopted a feature's file or record (a branch whose plan record moved after review, new tests) and one that has not (no move, existing tests) |
| Toolchain version | not covered | stdlib and git only; no matrix (#1788) |
| Clone shape | not applicable | writer runs in the full working checkout |
| Run location | not applicable | writer's cwd is the repository |
| Gate target | not applicable | CPP's own writer |
| Wave role state | not applicable | unrelated |

Reader: `counter-model-receipt.py validate` (CPP corpus test and CI) reads reviewed_artifact; gains a shape check for plan_record_move, tested.
Reader: finish-gate enrolment (CPP, and kyle/skillc via pinned CPP) reads `head` by ancestry; meaning unchanged, an extra key was shown to validate ok.
