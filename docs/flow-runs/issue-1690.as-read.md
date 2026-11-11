<!-- flow-run n=1 id=d0e20bb75ff44308be7a617ea4170d66 -->
## Run 1 - issue #1690 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1690
- Read at:      2026-11-11T22:53:14Z
- updatedAt:    2026-11-11T22:34:39Z   (context only - moves on comments and labels)
- Body digest:  ba4a83ec1648ebdbdfb0ecf1b8f69476d88eae1cd72993d4592f0e781ebde93c   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2224 of 2224 (cap 16384)

### Body as read
Tier: 2

Source: child (a) of #1673, chosen at that epic's planning run on 2026-11-11. The owner chose to run this as its own issue so the disposition list is read before #864 is closed.

## Outcome
The Nit Store is a readable inbox again. #864 holds 731 comments (438 from September, 209 from October, 84 from November, about 1.37 MB of text). Every one has a recorded disposition, #864 is closed, and a successor is open.

## Acceptance
- Every comment on #864 has exactly one disposition in a list attached to this issue: `filed #N`, `fixed by #N`, `obsolete` (naming what removed the subject) or `declined` (one line of reason). The list's count equals #864's comment count at the time of the read, and the read's timestamp is stated.
- Related findings are grouped into one issue per job, not one issue per comment. A finding of medium severity or higher, or any live correctness, security or data-loss problem, is always `filed`.
- Findings about `flow` and `cicd` are marked as such in the list, so the three simplification children of #1673 can read their bucket.
- The owner reads the disposition list before #864 is closed.
- #864 is closed with a link to the list, then a successor titled exactly `Nit Store` with the `evergreen` label is opened, in that order. `scripts/nit-store-resolve.sh` then answers the successor with `NIT_STORE_STATUS: ok`.

## Constraint
- Follow `docs/agents/nit-store-rollover.md` (lands with the #1673 planning PR). Close before opening: two open stores make the resolver answer `unknown` and findings are posted nowhere.
- Do not rewrite the citations of the form `Nit Store #864, comment N` in code and documents. They are history and still resolve.
- A `fixed by` verdict needs the merged change cited, not a recollection. About 77 issues already cite a #864 comment by `issuecomment-` link; start from those.
- Comments added to #864 while the read is in progress are part of the population. Re-read the count before closing.

## Not checked
Whether Kyle's Codex session containers carry a baked copy of the owner's global directives that still names #864. The host copy (`~/.codex/AGENTS.md`) was regenerated on 2026-11-11. Check the containers before the close.

Parent: #1673


<!-- end of body -->
