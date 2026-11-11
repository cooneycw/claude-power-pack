<!-- flow-run n=1 id=3ade43914a2546409adfe59f4fc60f53 -->
## Run 1 - issue #1703 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1703
- Read at:      2026-11-11T22:42:47Z
- updatedAt:    2026-11-11T22:42:38Z   (context only - moves on comments and labels)
- Body digest:  bf651b8b6b5fa0823fc1f46569363ceb489c5f5360049615d29295a7278f3cf0   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4142 of 4142 (cap 16384)

### Body as read
Tier: 2

Source: owner request, 2026-11-11, from the #1673 planning session. Owner's words: "the monthly:review needs to be a cpp skill (it should scan for them as part of project:next, and we need a corresponding monthly:create skill to scan the repo and develop the next monitoring list)."

## Outcome
Recurring maintenance gets attention on a schedule without anyone having to remember it. Today the standing items are either labelled `evergreen`, which tells `/project:next` never to recommend them, or exist only as a sentence in a document. The Nit Store reached 731 comments, the command documents doubled in size in 60 days, and friction signals wait for a retro nobody is prompted to run.

Three pieces:

- `/monthly:create` scans the repository and writes the next monitoring list: a dated, ordinary, startable issue (for example `Monthly review: 2026-12`, label `monthly-review`) whose checklist is derived from what the scan found, not from a fixed template.
- `/monthly:review` works through an open monthly review issue item by item and records what was done for each.
- `/project:next` scans for monthly reviews on every run: it reports an open review, and when the current month has none it says so and routes to `/monthly:create`. That report is the trigger, so no scheduler, cron job or CI change is needed.

## Acceptance
- `/monthly:create` exists as a CPP command. Its scan covers at least: the open Nit Store (comment count, and whether a rollover is due under `docs/agents/nit-store-rollover.md`); every open issue labelled `evergreen` (each becomes a checklist line); the command-document word budget (#1669); pending friction signals; and any dated follow-up that has come due.
- A dated follow-up can be declared somewhere `/monthly:create` reads, so that an obligation like "take the fix:feat reading 30 days after the #1673 wave closes" appears in the right month's list. The plan chooses the mechanism.
- A source the scan could not read appears in the list as unread. It is never silently left out, and never reported as "nothing due".
- `/monthly:create` run twice in one month does not open a second review issue.
- `/project:init` includes `/monthly:create` (owner, 2026-11-11: "monthly:create should be part of project:init too"), so a newly scaffolded project starts with its first monitoring list and the `monthly-review` label already in place. A project created before this change is picked up the first time `/project:next` reports no review for the month.
- `/monthly:review` exists as a CPP command. Each checklist item ends ticked with a one-line record, or left open with the reason. The issue is closed only when every item is ticked or explicitly carried to next month.
- `/project:next` reports the monthly review state in every mode (brief, compact, full): an open review with its age, or "none for <month>" with the `/monthly:create` route. It does this as a CPP extension; the engine's ranking, partitions and `next_startable_issue` are unchanged.
- The monthly review issue is not labelled with any non-startable marker, so it is ranked and recommended like other work.
- The `evergreen` label keeps its current meaning. What changes is that every evergreen issue is now visited monthly through the review.

## Constraint
- No scheduler: no GitHub Actions workflow, no Woodpecker cron, no cloud routine.
- No change under `scripts/flow-*`, `.claude/commands/flow/`, `lib/cicd/` or `.claude/commands/cicd/` (the #1673 freeze).
- The new command documents sit inside the declared word budget from their first commit.
- The project-next contract is CPP-owned: if the report shape changes, the contract version, fixtures and ownership pins move together (`make project-next-check`).

## Assumption
That one review issue per month per repository is the right unit, and that the commands work in any repository CPP is installed for, not only this one. A repository with no Nit Store, no evergreen issues and no friction log gets a short list, not an error.

## Not decided here
Whether #1669 is closed once the first monthly review issue exists. Its budget rule would live on as a checklist line.


<!-- end of body -->
