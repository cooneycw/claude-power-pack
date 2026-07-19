# ADR 0004: Main branch-protection posture

- Status: Accepted (owner decision recorded 2026-07-19; implementation: #577)
- Date: 2026-07-19
- Deciders: cooneycw (owner)
- Issue: #577 (from the 2026-07-14 dormant-capability audit)
- Supersedes: nothing
- Related: #517 (`gh-pr-merge.sh --admin` / branch-protection auto-retry - the machinery this posture activates), #579 (flow:auto should stop cleanly at `REVIEW_REQUIRED`; a sibling, deliberately left open), #462 (stale-branch guard), #502 (base-moved squash retry)

## TL;DR

`main` requires the Woodpecker PR pipeline as a **required status check**
(`ci/woodpecker/pr/woodpecker`, `strict: true`). Required reviews stay at **0**
and `enforce_admins` stays **off**. The posture is declared as data in
`.claude/branch-protection.json`, checked read-only by
`scripts/branch-protection.sh` (`make branch-protection-check`) and applied
idempotently with `--apply`. Because a required check is worthless if the merge
path overrides it, `scripts/gh-pr-merge.sh` now **waits** for required checks and
excludes a required-check block from the #517 `--admin` auto-retry.

## Context

The 2026-07-14 dormant-capability audit found `main` fully relaxed:
`required_approving_review_count: 0`, required status-check contexts `[]`,
`enforce_admins: false`. Pull requests were forced, but they merged with zero
review and zero required CI - a red Woodpecker pipeline never blocked anything.

Two things made that worth deciding rather than leaving:

1. **The only thing stopping red code reaching `main` was politeness.**
   `/flow:auto` runs the quality gate itself at Step 6 and verifies CI at Step 8,
   *after* the merge. Nothing underneath enforced it; any merge outside the flow
   path had no gate at all.
2. **#517 shipped machinery for a posture that did not exist.**
   `gh-pr-merge.sh`'s `--admin` flag and branch-protection auto-retry were built
   to cope with a protected `main` and had never once fired here. Dead code that
   reads as live is worse than either.

Two facts discovered while deciding shaped the outcome:

- **Woodpecker already publishes GitHub commit statuses.** Both
  `ci/woodpecker/pr/woodpecker` and `ci/woodpecker/push/woodpecker` were present
  on the heads of PRs #593, #594 and #599. Requiring CI therefore needed **no**
  new plumbing - the issue's "wire a GitHub status first" concern was already
  satisfied.
- **The #517 auto-retry would have silently eaten the new check.**
  `is_protection_block()` matches `required status check`, and the actor is a
  repo admin, so every `/flow:auto` merge would have hit the block and retried
  with `--admin` - which bypasses *all* protection at once. Applying the posture
  without touching the merge path would have produced protection theatre.

## Decision

| Setting | Value | Why |
|---------|-------|-----|
| `required_status_checks.contexts` | `["ci/woodpecker/pr/woodpecker"]` | The gap the audit actually names: red CI could reach `main`. The context already exists. |
| `required_status_checks.strict` | `true` | Unchanged. `/flow:auto` Step 7 already merges `origin/main` before squashing, so it is satisfied by construction. |
| `required_approving_review_count` | `0` | Solo repo. See "Rejected: required reviews". |
| `enforce_admins` | `false` | Retains a documented break-glass. See "Rejected: enforce_admins on". |
| `allow_force_pushes` / `allow_deletions` | `false` | Unchanged. |

And, so the check is real rather than decorative, `scripts/gh-pr-merge.sh`:

- resolves the base branch's required contexts and **polls the PR head until they
  are green** before squashing (bounded; `GH_PR_MERGE_CHECK_ATTEMPTS` x
  `GH_PR_MERGE_CHECK_DELAY`, default ~10 minutes);
- **hard-stops** on a red required check, and on one that never reports;
- **excludes** a required-status-check block from the #517 `--admin` auto-retry.
  A review-required block - #517's actual case, and the one #579 is about - is
  unchanged;
- still honours an **explicit** `--admin` from the caller, which skips the wait.
  A conscious owner override is the break-glass; an automatic one is not.

Net effect on `/flow:auto`: the CI wait moves from Step 8 (after the merge) to
Step 7 (before it). Wall-clock is roughly unchanged; what changes is that a red
pipeline now costs a stopped run instead of a bad commit on `main`.

## Rejected alternatives

**Keep the relaxed posture and record it as deliberate.** Defensible for a solo
repo, and the cheapest option. Rejected because the audit's specific complaint -
red CI can merge - is a real hole that costs nothing to close now that the status
context exists, and because leaving #517's machinery permanently dormant means
nobody can tell whether it still works.

**Required reviews > 0.** On a single-maintainer repo this is self-defeating: the
owner is the only possible approver, so every merge needs `--admin`, and `--admin`
bypasses the required status check *at the same time*. The strict-sounding posture
would end up enforcing strictly less than the one chosen. (Where a human review
gate genuinely applies - repos with more than one maintainer, e.g. the agentic-asst
#449 posture - the owner rule is "CI-green != merge sanction" and the handling
belongs to #579, not here.)

**`enforce_admins: true`.** Strictly stronger, and tempting. Rejected on
operational risk: a required check that never reports - a skipped pipeline, a
Woodpecker outage, a renamed context - leaves every PR permanently unmergeable
with no escape except hand-editing protection in the GitHub UI. With
`enforce_admins: false` the owner keeps one documented, deliberate, auditable
break-glass (`gh-pr-merge.sh --admin <pr> <branch>`), and the automation is
prevented from reaching for it on its own - which is where the real risk was.

## Consequences

- A red or missing Woodpecker PR pipeline now blocks the merge, in and out of the
  flow path.
- `/flow:auto` Step 7 can now stop on CI - a new, expected failure mode. The
  message names the break-glass explicitly.
- The #517 `--admin` path is live for review blocks and dormant-by-design for
  check blocks; both are covered by tests.
- Posture drift is detectable: `make branch-protection-check` diffs live
  protection against `.claude/branch-protection.json`. It is **not** a CI gate -
  it needs a token with admin read on the repo, which the pipeline does not have -
  so it is a local/manual check, run when protection is suspected to have moved.
- Applying the posture is a one-liner (`make branch-protection-apply`) and
  idempotent, so this decision is reversible: edit the JSON, re-apply.

## Decision record

- 2026-07-19, owner: posture = require the Woodpecker PR check, keep reviews at 0,
  keep `enforce_admins` off.
- 2026-07-19, owner: apply the posture **after** the implementing PR merges, so a
  bug in the new wait cannot block its own delivery.
