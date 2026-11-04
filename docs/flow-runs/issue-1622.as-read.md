<!-- flow-run n=1 id=390f2c7924014b34ae5ce04090675141 -->
## Run 1 - issue #1622 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1622
- Read at:      2026-11-04T17:32:24Z
- updatedAt:    2026-11-04T17:31:13Z   (context only - moves on comments and labels)
- Body digest:  0bab839e475b007ee011ef36f1c5073e9638ac434f7aea9efa8d4e80d463e707   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2876 of 2876 (cap 16384)

### Body as read
## Problem

On the generic route, `/project:init` ends with a plan but no usable issues, and its next step assumes issues exist.

1. Step 5 writes a `tasks.md` whose only task is the placeholder `T001 {First task}`.
2. It immediately asks "Sync tasks to GitHub issues now?". Yes would create a junk issue from that placeholder.
3. The Step 6 summary says "Next steps: `/flow:start {N}`", but no issue `N` exists unless the user has done a further manual stage.

Issues are inherent to Flow, so the command stops one stage short of what comes next. This surfaced while writing the aws-learn Start Here guide (aws-learn#880), which had to tell learners to answer Skip at that prompt and then return to do the sync by hand.

## Outcome wanted

`/project:init` finishes with real, reviewed GitHub issues, so a new user can go straight to `/flow:auto`.

## Acceptance

- On the generic route, Step 5 drafts real tasks from the confirmed destination and first feature, and no `{First task}` placeholder remains.
- The user reviews and approves the task list inside the same command, and can edit it first.
- After approval the sync runs as part of the plan, not as a separate decision. The user can still decline; in that case the summary gives the exact sync command rather than a `/flow:start {N}` with no issue.
- The summary lists the issues created and names the first as the next step: `/flow:auto <first issue>`.
- `speckit-tasks-to-issues.sh` refuses unfilled placeholder tasks, with a clear message, including under `--dry-run`.
- The `/spec:adopt` line is removed from the summary (see Notes).
- A test covers a run from a non-CPP project through to issues created, plus the placeholder refusal.

## Constraints

- The approval checkpoint stays: tasks become public issues, so they are not created without the user seeing them.
- Sync must stay safe to re-run, keeping the feature-scoped identity from #857.
- `tasks.md` is committed where the converter needs it to be. Step 5 currently runs before the Step 6 commit, so confirm the ordering.
- Existing Wayfinder and multi-session routes keep their behaviour unless a change is needed for the same outcome.

## Proposed approach (revisable)

Extend Step 5: draft tasks, show them for approval, then call `~/.claude/scripts/speckit-tasks-to-issues.sh`. Add the placeholder check in the converter, so every caller gets it.

## Notes

The aws-learn owner reports no longer using GitHub spec-kit, while `.claude/commands/spec/help.md` and `/spec:adopt` still present it as the official authoring path, so this needs an upstream decision. If spec-kit stays for CPP generally, keep `/spec:adopt` out of this summary anyway: it is a separate optional path, and this summary should point to the next action.

Companion: aws-learn#880 folds sync into the guide's "Starting a New Project" step, on the assumption that this ships.


<!-- end of body -->
