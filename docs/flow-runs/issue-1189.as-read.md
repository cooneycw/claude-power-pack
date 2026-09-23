# Issue #1189 as read by this run

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1189
- Read at:      2026-09-23T14:12:37Z
- updatedAt:    2026-09-21T20:57:28Z   (context only - moves on comments and labels)
- Body digest:  69b106a669ea278c5fb42fe5cd722c8736ad3e370de1f0387a366da709ceade3   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 4244 of 4244 (cap 16384)

## Body as read
The wave verdict ledger (`verdicts.json`, #645) exists so rulings outlive a single orchestrator session — `wave.md` says so explicitly, and puts it in the wave runtime namespace rather than session scratch for that reason. Two defects mean it is a worse record than it claims, both found while orchestrating a live wave on cooneycw/kyle, 2026-09-21.

## 1. A `GATE: HOLD`'s reason is silently discarded when written beneath the token

`scripts/flow-wave-lexicon.sh:563-570`. The documented grammar (line 113-114) puts the reason on the **token line**: `GATE: HOLD #N behind #M[, #M...] [reason]`.

For `GATE: GO-WITH-CONDITIONS`, the `- <condition>` lines *beneath* the token are harvested into the reason (565-568). For `GATE: HOLD`, nothing beneath the token is read. So a verdict stating its argument as prose under the token — the natural shape, and the shape `GO-WITH-CONDITIONS` actively teaches — records a **binding** hold whose stored reason is the literal string `GATE: HOLD (no reason given)`.

**The enforcement half survives while the argument half is dropped.** `flow-wave-plan.py` exits 4 on the hold and keeps the issue out of the assignment pool, so a successor inherits an unexplained standing hold with no way to tell a deliberately terse ruling from an argument typed in the wrong place. Nothing signals it: `validate` reports 0 errors, `send` delivers the prose intact to the human reader, and `record` prints `FLOW_LEXICON_RECORDED=1`.

Concretely: I held kyle #1285 behind #1267 with a five-line argument. The ledger stored `(no reason given)`. I found it only because I re-ran the planner as a control on my own ruling rather than trusting the success line.

## 2. A ruling on work that deliberately has no issue cannot be recorded at all

Every `GATE:` verb requires a subject issue (`GATE: GO-WITH-CONDITIONS must name its subject issue`), and `flow-wave-plan.py --verdicts` keys entries on `"issue": N`.

But `wave.md`'s own residual-severity rule routes small in-lane findings to a **fix rather than a ticket**, and a wave may carry an owner directive not to grow the issue count. That work still reaches a Step-3 gate. When it does, the verdict cannot be formed.

This happened twice on the kyle wave. Two PRs merged with no issue behind them by design, and neither ruling entered `verdicts.json`. A successor resuming after a `/clear` sees no record that the work was gated at all.

**The two policies collide, and each is correct.** Anything filed gets a number and is recordable; anything deliberately *not* filed — which is the path the doctrine pushes small findings down — becomes ungovernable by the ledger built to make rulings durable. The better a wave follows the don't-file-it rule, the more of its rulings fall outside its own record.

**The wrong repair, named because it is the obvious one:** attribute the verdict to a nearby issue number. I declined — a ledger entry naming an issue the ruling is not about makes a false statement about what was decided, which is worse than a gap someone can see. A worker in the same wave independently refused the identical move for `flow-worktree-claim.sh`, which also requires `--issue`.

## Suggested disposition

For (1): harvest the non-blank lines beneath a `HOLD` the way conditions are harvested, **or** refuse a `HOLD` carrying no inline reason the way `MERGE: PRIORITY` is refused without an argument (line 659) — that refusal already exists in this file for the same hazard. Cheapest variant: print a `FLOW_LEXICON_REASONLESS=` line so the drop is visible rather than silent.

For (2): allow a gate subject that is not an issue number — a short slug (`GATE: GO-WITH-CONDITIONS journal-false-red`) — with `verdicts.json` keying on `subject` and the planner ignoring non-numeric subjects entirely. Planner behaviour is then unchanged and the ruling becomes durable. `flow-worktree-claim.sh` has the same shape and would benefit from the same allowance.

## Provenance

Nit-store records: #864 comments [5764057777](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5764057777) and [5765347331](https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5765347331). Aggregated at the owner's direction.

