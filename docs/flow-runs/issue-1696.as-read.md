<!-- flow-run n=1 id=9dc3eee1efc04d7e8c57d683426800e3 -->
## Run 1 - issue #1696 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1696
- Read at:      2026-11-11T23:11:34Z
- updatedAt:    2026-11-11T22:19:31Z   (context only - moves on comments and labels)
- Body digest:  88ba5733d08ec28d5f5aed44752864eff9ede07e575aaa19caa034659158fe68   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4375 of 4375 (cap 16384)

### Body as read
Tier: 2

Source: owner request, 2026-11-11, extending #1695. Owner asked for `/project:init` to create the lane file through a `/lane:create` command, and for a check that flags the file's age and offers `/lane:update`.

## Outcome
A project gets its lane file without anyone remembering to write one, and the file does not quietly go out of date.

#1695 defines the lane file and how plans and closing reports use it. It leaves two things to memory: creating the file in the first place, and revisiting it. A lane list that is never revisited fails the same way a missing one does: the plan answers every listed row and still omits the lane that was added to the product last month.

## Acceptance
- **`/lane:create`.** Surveys the repo for evidence of lanes (deploy environments, CI providers, container or host placement, model drivers, install targets, supported client widths or personas where a UI exists), drafts the lane file in #1695's format, and shows the draft to the owner before writing it. Each drafted row cites what in the repo it was derived from. It refuses to overwrite an existing lane file and points to `/lane:update`.
- **`/lane:update`.** Re-runs the survey against the existing file and reports three lists: lanes the survey finds that the file lacks, rows whose evidence is gone, rows unchanged. It also lists fix issues closed since the last review for the owner to scan for unlisted lanes. It writes only what the owner accepts, then records the review date. A review that changes nothing still records the date.
- **`/project:init` calls `/lane:create`** as one of its Step 4 sub-commands, after CI providers are recorded, so a new project starts with a lane file. A new project with a single lane gets a one-row file, not a skipped step.
- **Age advisory.** A check reads the review date recorded INSIDE the lane file and reports when it is older than a declared threshold, naming the age and offering `/lane:update`. Proposed threshold: 60 days; the implementer may argue another number with a reason.
- **The advisory is shown where a plan is being made**, in the plan step #1695 adds, because that is when a stale list costs something. It is advisory: it never blocks a plan, a gate or a merge.
- **No lane file means silence**, consistent with #1695: a project that has not adopted lanes sees no advisory.
- **Negative control** (ADR 0008: the advisory is read by an owner who will not re-derive the file's age). Committed cases: a lane file whose review date is one day past the threshold is flagged; one at the threshold is not; a lane file with no readable review date is reported as unknown age and is NOT read as fresh.
- New command documents are declared in `.claude/command-word-budgets.tsv`, and `/project:init` stays within its current budget (3,781 words, at its cap).

## Constraint
- Age comes from the review date in the file, not from file modification time or git history. A typo fix must not make the list look reviewed, and an exported or freshly cloned tree must not make it look new.
- Advisory only. #1695 forbids a new gate for lanes, and #1673 is reducing machinery in `flow` and `cicd`.
- Do not add the advisory to the session-start lines (`scripts/install-drift.sh`). The 2026-11-11 review found those signals already arrive faster than they are read (10 unreviewed retro signals that morning).
- `/lane:create` and `/lane:update` draft and propose. They never write a lane the owner has not seen.

## Depends on
#1695 for the file's location and format, and for the plan step the advisory attaches to. The plan-step part is subject to the same unanswered freeze question recorded there. The two commands and the `/project:init` call can be built before it.

## Assumption
- That age is a useful prompt. Lanes go stale when the product changes, not when time passes, so age is a proxy. The stronger signal is #1695's growth rule (a miss that reveals an unlisted lane adds it). If the advisory is routinely dismissed with no change, drop it and keep the growth rule.
- That a repo survey can find most lanes. It cannot find a lane that leaves no trace in the repo, such as a production-only setting; the owner's read of the draft is what covers that.

## Not checked
Whether `/project:init` has room in its budget for the new sub-step without trimming. It is at its cap, so it probably needs a trim of equal size.


<!-- end of body -->
