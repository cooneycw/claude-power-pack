# ADR 0006: Who owns worktree teardown in flow:wave

- Status: Accepted
- Date: 2026-09-13
- Issue: #887
- Supersedes: nothing
- Related: #627 (visible sibling worktrees - the layout that makes the pile
  visible), #597 (the cross-session claim), #888 / #889 (the live-occupancy
  refusal this composes with), #566 (non-interactive branch deletion)

## TL;DR

**A sweep owns teardown** - `scripts/flow-worktree-sweep.sh`, run at wave close
and from `/flow:cleanup`, never at merge time. It removes only worktrees that
pass all five of #887's conditions re-read immediately before each removal, and
it delegates every actual removal to `worktree-remove.sh` **without `--force`
and without `--steal`**, treating any non-zero exit as a skip.

The cross-session-mutation objection to a sweep is **not inapplicable - it is
discharged**, and the paragraph that does the discharging is the load-bearing
part of this document. It is below under "The objection, answered honestly".

## Context

A `/flow:wave` worker creates a worktree, opens a PR, and finishes. In the wave
shape the *merging* session is usually a different one, so `/flow:auto` Step 7 -
which does remove a worktree, correctly, when the same session merges - never
runs. `gh pr merge --delete-branch` then deletes the remote branch and tries
`git branch -d` locally; git refuses while a worktree holds the branch, and `gh`
has no notion of worktrees, so it stops.

Measured on cooneycw/kyle after one wave: 33 registered worktrees, 3.1G; 25 held
merged branches, 21 were removable by every test at once, and cleaning them took
the tree to 12 worktrees and 1.1G.

The disk is not the defect. The error appeared on **every** merge of that wave -
roughly a dozen times - and was correctly ignored each time, because the merge
had succeeded and the message described a local-branch deletion nobody needed. A
warning that is right to ignore twelve times is one nobody will act on the
thirteenth.

## The three candidates

#887 named them, and said the right answer is probably not the obvious one.

### 1. The worker, on PR open - rejected

The worktree must survive review feedback and re-merges. Several PRs in the
measured wave took three pushes. This owner deletes the checkout while it is
still needed, so it is not a candidate at all.

### 2. The merging session, after a successful merge - rejected, for two reasons

It knows the merge succeeded and it sees the failure. But:

**It cannot cover the population.** Its trigger is a merge it performs, so it is
structurally blind to a worktree whose PR was CLOSED, one merged in the GitHub
web UI, one merged by a different tool, and one orphaned when its session died.
On the measured host six worktrees held branches with no PR at all. A teardown
owner whose reach is "worktrees I happened to merge" cannot close this issue even
if it were perfectly safe, because most of what accumulates never passes through
it.

**Its refusals are expensive, so they will be routed around.** This is the
stronger reason. The merging session has a job to finish, and a guard that stops
it is an obstacle standing between it and a completed merge. That is not
speculative: it is the documented history of the very helper this would call.
`/flow:auto` Step 7 passes `--force` on every invocation, and #888 exists because
`--force` silences the uncommitted-changes check - so the guard was, in practice,
never armed where the damage happened. Put teardown on the merge path and the
same pressure applies to the same helper from a second caller.

### 3. A sweep, at wave close or session teardown - accepted

Decoupled from any individual merge. Its population is *every worktree registered
to the repository*, so it reaches all four cases above. It can apply the full
five-condition test because it is not in a hurry, and - the point that follows
from #889 - **a refusal costs it nothing.** Skipping a worktree is the sweep
doing its job, not a failure of the operation it was performing. A guard whose
refusal is free is a guard that stays honest, and the sweep therefore has no
reason to ever pass `--force`, and does not.

It also fails in the right direction. A merge-time teardown that misjudges
deletes a checkout mid-workflow; a sweep that misjudges leaves a directory on
disk until the next run. Those are not symmetric costs.

## The objection, answered honestly

The objection to candidate 2 was that removing another session's worktree is the
cross-session mutation the fleet avoids elsewhere. **That objection applies to the
sweep too.** A sweep run by the orchestrator removes worktrees other sessions
created; saying otherwise would be a word game. What can be shown is that the
sweep *satisfies* the objection rather than escaping it, and the argument has
three steps.

**First, the taboo is a proxy.** "Do not mutate another session's state" is not a
terminal value; it stands in for "you cannot establish what the other party still
needs, so do not act." Where the underlying state genuinely can be measured, the
measurement outranks the proxy - otherwise the rule forbids garbage collection
of any kind, forever, which is the state #887 documents as the defect.

**Second, #887's five conditions are that measurement, and they are not a
paraphrase of "the other session is done" - they are the observable form of it.**
A merged PR says the work landed. A clean tree and nothing unpushed say the
checkout holds nothing that exists only there. No live process inside says nobody
is standing in it. Not locked says no session has claimed it (#597). Taken
together they do not infer that the owner finished; they establish that nothing
is lost if it did not.

**Third - and this is what candidate 2 cannot borrow - the sweep can afford to
believe its own test.** Candidate 2 could run the same five conditions; the
difference is what each does when one fails. For the merging session a refusal
blocks a merge it must complete, so the pressure is toward `--force`, toward
retry, toward treating a non-zero exit as noise. For the sweep a refusal is an
ordinary outcome with no downstream cost, so it can take every refusal at face
value. Two callers with identical tests and opposite incentives do not end up
with identical behaviour, and #888 is the evidence: the test was there, and the
incentive removed it.

So: the sweep mutates cross-session state, deliberately, on the strength of a
per-worktree measurement re-taken at the moment of removal, in a caller that
loses nothing by being wrong in the safe direction. That is the argument. If the
measurement is later shown not to establish what it claims, this decision fails
with it - which is the correct dependency, and the reason the conditions are
enumerated in the script's header rather than summarised.

## What this composes with, and what it must not undo

#889 landed an occupancy guard in `worktree-remove.sh`: with no claim naming the
caller, a worktree that is occupied **and** dirty is exit 5, and `--force` does
not suppress it. The sweep's relationship to that guard is deliberate:

- It passes the helper **no flag but `--delete-branch`**. Every other flag
  `worktree-remove.sh` accepts overrides a refusal, and the sweep is the one
  caller that would apply such a flag to every worktree on the host. The sweep's
  largest contribution to safety is what it does not pass.

  **This was stated as "without `--force`" and that has been overtaken by
  #899**, which split `--force` into `--force`, `--allow-dirty` and
  `--allow-unpushed`. The uncommitted-changes check is now armed unconditionally
  and `--allow-dirty` is what disarms it, so the original sentence described a
  coupling that no longer exists. The decision it justified is unchanged - the
  sweep passed none of those flags then and passes none now - but the reasoning
  was stale, and a reader following it would have looked for a `--force`-gated
  check that is not there.

  The test was stale in a way that mattered more. It ENUMERATED the two flags
  that existed when this ADR was written, so the sweep could have begun passing
  `--allow-dirty` with the whole suite green. Measured, not hypothetical. It now
  asserts an ALLOWLIST - the flag set must equal `{--delete-branch}` - which
  covers a sixth flag on the day it lands rather than on the day someone
  remembers. That is the same hand-maintained-enumeration defect this repository
  has been closing all week, found in the pin guarding this decision.
- It calls the helper **without `--steal`**, so exit 4 (#597) and exit 5 (#888)
  are final. Each is recorded as a refusal against that worktree and the sweep
  moves to the next one. Nothing is retried and nothing is overridden. Doing
  either in a loop over every worktree on a host is the data-loss path #889
  closed, reopened at scale.
- Its own occupancy scan is a **filter, not a second authority**. The helper asks
  the same question last, and its answer decides. The two must not be
  "de-duplicated" into one: the sweep needs the signal to *report* in a dry run,
  and the helper needs it to *refuse* at removal.
- It does not reintroduce the over-correction #889 avoided. #888 proposed
  refusing on any unmatched claim state, which would make every unclaimed
  worktree unremovable since `free` is the normal state. The sweep skips on
  `locked` - a positive signal - and never on the absence of a claim.

The sweep is also stricter than the helper in two places, which is intentional
rather than an inconsistency: an occupied-but-clean worktree is removed by the
helper and skipped by the sweep, and an unreadable `/proc` makes the helper fall
open and the sweep skip. The helper serves a caller who has named one path and
asked for it; the sweep is choosing its own targets and pays nothing to leave one
alone.

## Where verification happens, and the window that remains

#887 requires the five conditions to be re-verified **at removal time** and never
from a list built earlier, because the state moves while a wave runs. Concretely:

- One worktree is carried from classification to removal before the next is
  looked at. There is no batch pre-pass, and `--apply` re-derives everything
  rather than replaying a dry run's output.
- `dirty` and `unpushed` are read **again** as the last statements before the
  removal call. That is not redundant: between the first read and the call sit a
  `/proc` walk and a network round trip to GitHub, which is long enough for the
  first read to be stale.

`unpushed` is singled out because it is **the only condition with nothing beneath
it**. Every other one is backstopped: `dirty` by `worktree-remove.sh`'s own check
(armed, because the sweep passes no `--force`), `locked` by git itself and by the
#597 claim check, `occupied` by #889's exit 5. But a session that **commits
without pushing** is invisible to all of them - `git status --porcelain` reports
clean, and a worker paused between tool calls has no live process for either
occupancy scan to find. `git log @{u}..`, and the PR-head comparison that stands
in for it after a prune, is ours alone.

The residual window is what remains between that final read and the `git worktree
remove` inside the helper: one subprocess spawn, its claim check, and its own
`/proc` scan. It is not zero, and it cannot be made zero without git-level
locking the sweep does not hold. It is accepted for two reasons. The consequence
is bounded rather than absolute - the commit objects survive in the common object
database and remain reachable via `git fsck --lost-found` until gc, so the loss is
a recovery exercise rather than a deletion. And the alternative, holding a lock
across the whole sweep, would block exactly the sessions the sweep exists to stay
out of the way of.

Both window cases are pinned behaviourally rather than argued:
`test_a_commit_landing_after_classification_is_caught_before_removal` and its
dirty twin drive a `git` wrapper that mutates the worktree after a chosen read,
so the race is deterministic instead of timed. Removing the re-verification block
turns both red.

## What a bare invocation does

`flow-worktree-sweep.sh --repo <path>` with no other flags is a **dry run**. It
classifies every worktree, prints a `SWEEP_WORKTREE:` line per candidate and the
`FLOW_WORKTREE_SWEEP_COUNTS:` summary, and removes nothing. `--apply` is required
to remove, and re-derives all five conditions itself.

Dry-run-by-default was chosen over remove-by-default because "I ran it to see
what it does" is how an operator meets a new tool, and this tool's failure mode is
deleting work. The cost of the choice is that the common path takes two
invocations; that is acceptable precisely because the second one does not trust
the first - it re-checks rather than replaying, so the extra run buys information
without introducing a stale-plan hazard.

## Consequences

- `/flow:cleanup` gains the sweep as a step, **before** its `git fetch --prune`.
  That ordering is load-bearing: pruning drops `refs/remotes/origin/<branch>`,
  which is what `git log @{u}..` needs to answer "nothing unpushed". The sweep has
  a second, independent mechanism for that question (the PR's head OID, which
  survives the prune), but running it first means the git-native answer is
  available, and two independent signals beat one - the specific lesson of #888,
  where two guards shared a blind spot and degraded to one.
- `/flow:wave` Phase 3 runs it at wave close.
- Default is **dry run**. `--apply` is explicit, and re-derives all five
  conditions itself rather than executing the dry run's output. The report is a
  report, not a manifest.
- CLOSED PRs are opt-in (`--include-closed`). A merged PR is unambiguous; a
  closed one often means the work was rejected or deferred and the branch may be
  the only record of it.
- The helper is **not** added to `templates/claude-settings-permissions.json`,
  though it is added to `flow-helpers-install.sh` so the stable path exists. The
  parity test permits that direction (the installer array may be a superset).
  The reason is specific: an allow rule for `worktree-remove.sh` pre-approves a
  command whose target is visible in the command line an operator reads, while a
  rule for the sweep would pre-approve one whose target *set* is not - and a
  pre-approval an operator cannot evaluate from the command is not doing the job
  a pre-approval exists to do. `git worktree remove` is DESTRUCTIVE by this
  repository's own classifier (`scripts/classify-tool-risk.py`).

## What this does not solve

- **Orphaned local branches.** After the worktree goes, the branch remains with
  its remote deleted. `--delete-branch` handles the branch belonging to a
  worktree the sweep removes, so the two stay in step; a branch with no worktree
  is `/flow:cleanup` Step 3's existing job and is untouched here.
- **Worktrees on a non-GitHub remote.** PR state is unresolvable, so every
  candidate reports `pr-unknown` and the run is `partial`. Honest, and inert.
- **The prune-first host.** A host that has already run `git fetch --prune` and
  whose `gh` is unreachable has neither unpushed mechanism available, and the
  sweep reports `unpushed-unknown` rather than guessing. Those worktrees stay
  until one of the two signals is available again.
