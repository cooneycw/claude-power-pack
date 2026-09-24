# Issue #1222 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1222
- Read at:      2026-09-24T11:50:11Z
- updatedAt:    2026-09-23T21:42:38Z   (context only - moves on comments and labels)
- Body digest:  c74216ba222eed85b95ea04e03830e787892171a5b3dc64bf5577dc21694585a   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3440 of 3440 (cap 16384)

## Body as read
**Record issue**, per the owner's 2026-09-23 ruling that ticketless findings get an issue so the verdict ledger has a subject to key on. Found by worker-A before standing down; a second field confirmed independently by worker-AA hours later; five fields measured by the orchestrator.

## The defect

`flow-wave-registry.sh release <role>` records the release — `released = True`, `released_ts` set — and **clears none of the lane facts**. Measured against a role whose session is confirmed dead and whose work has landed:

```
released           = True
released_ts        = 1790164525
issue              = 1085          <- issue is CLOSED
pr                 = 1202          <- PR is MERGED
branch             = issue-1085-maintain-loop-leading-indicator-time-from-a-record
base               = cbd7dcf3...
diff               = c7a4bac2176dae8b
files              = 8 paths, including docs/decisions/0008-...md and docs/scripts.md
```

So a released role belonging to an ended session still advertises a branch, a merged PR, a closed issue, and an eight-path file lane.

## Why it matters

**The roster cannot distinguish "held by a live role" from "left behind by a role that ended."** Those are different facts and only one of them should influence a grant.

Three consequences observed in one wave, none hypothetical:

1. **The starvation signal is unreliable on released rows.** Found by worker-A, which expected `release` to clear `pr` and *checked before saying so*: it does not.
2. **File lanes outlive their owner.** worker-AA needed `docs/decisions/0008-instrument-negative-control-bound.md`; it was still declared by the released role. It took the path anyway — correctly, since overlap checks skip released roles — but had to reason about whether "declared" meant "held".
3. **An orchestrator granting from the roster sees paths that nobody holds.** `docs/scripts.md` is declared by a released role *and* a live one. Deciding a grant on that data means deciding on a lane whose owner no longer exists.

The overlap checks ignoring released roles is what keeps this from being a collision hazard. It is a **data-integrity** problem, not a safety one: the row is not wrong about the past, it is silently wrong about the present.

## Suggested fix

On `release`, clear the facts that describe *current* work — `issue`, `pr`, `branch`, `base`, `diff`, `files` — while retaining `released`, `released_ts` and the identity fields.

The distinction to preserve: a released role should remain **legible as history** (who held what, when) without remaining **readable as a claim**. If the historical view has consumers, keep them under a key that cannot be mistaken for a live lane.

## Acceptance

1. After `release`, a role's lane fields no longer render as a current claim in `list`.
2. `released`, `released_ts` and identity fields survive, so the row stays auditable.
3. A regression test: register with an issue, a PR and a file lane; release; assert the lane fields are gone and the release record is not — red on today's code.
4. The starvation signal is computed only from roles that still hold a lane.

Provenance: reported by worker-A 2026-09-23 with the `pr` field, measured rather than assumed. Second field (`files`) independently confirmed by worker-AA. Orchestrator measured five fields and confirmed `released = True` is stored, so the release itself is recorded correctly — only the clearing is missing.

