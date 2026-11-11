<!-- flow-run n=1 id=a81c9fc07c1a4ded86bd075a4fae3902 -->
## Run 1 - issue #1672 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1672
- Read at:      2026-11-11T20:41:33Z
- updatedAt:    2026-11-11T14:58:29Z   (context only - moves on comments and labels)
- Body digest:  65928d618b6e8e18ddcdc7f2bec252466ddee328042d68f4e0868c7c321e70b8   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 1232 of 1232 (cap 16384)

### Body as read
Tier: 2

Source: owner-requested methodology review, 2026-11-11, measured on origin/main at 31fe6a69 against the last commit before 2026-09-12. Owner approved filing.

## Outcome
`docs/scripts.md` is the designated home for per-script behavioural history (CLAUDE.md routes history there to keep itself small). It grew from 17,995 to 92,699 words in 60 days and is the most-changed file in the repository (169 commits in the window). One file that size cannot be loaded on demand in any useful sense, and every script PR contends on it.

## Acceptance
- First establish the cause of the growth and state it in the issue. #1013 made the file's population derived from `scripts/`; whether the growth is generated inventory or hand-written history decides the remedy.
- The inventory is an index, one line per script. Per-script detail lives beside the script or in a per-script reference that can be loaded alone.
- `make scripts-inventory-check` still reds on an unlisted script (existing negative control still fails after the change).
- A PR that adds one script changes one line of the index.

## Constraint
No history is deleted; it moves. Links into `docs/scripts.md` anchors keep resolving or are rewritten in the same change.


<!-- end of body -->
