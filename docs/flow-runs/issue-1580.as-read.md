<!-- flow-run n=1 id=88ce1a28fe74445fa4bce509c04a1aeb -->
## Run 1 - issue #1580 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1580
- Read at:      2026-10-26T19:30:12Z
- updatedAt:    2026-10-26T19:27:11Z   (context only - moves on comments and labels)
- Body digest:  03a979788cbcae097774a347bdac7318467feeec9f65ee7e763d5445846de6c0   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3306 of 3306 (cap 16384)

### Body as read
## Problem

Counter-model receipts cannot represent a resumed Codex implementation whose real thread contains more than one implementer model. The writer fails even when the independently observed reviewer differs from every implementer.

Observed while completing cooneycw/kyle#1912 in wave kyle-wsjf: the original worker-B thread contains gpt-6.1-sol and gpt-5.6-sol turn_context records. A retained clean gpt-6-astra review is distinct from both. `scripts/counter-model-receipt.py write --implementer-thread-id ... --reviewer-exec-log ...` nevertheless exits 1 without a receipt because `rollout_turn_model` rejects multiple model names. This blocks the finish gate.

The installed helper is behind main, but the newer fresh-flow attribution from PR #1558 is not a truthful workaround: this is a resumed existing flow, its original run predates the current model segment, and the retained thread has verification rather than a new supported whole start sequence. In-memory evaluation of that route refused `fresh-flow scope: unsupported whole shell sequence`. Resetting history, inventing a new implementation session, claiming skipped review, or declaring one model by hand would misstate the evidence.

Original finding: https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-6425085509

## Required behavior

- Represent all observed implementer identities for a mixed-model implementation, derived from the actual rollout rather than caller-supplied model names or arbitrary turn windows.
- Keep reviewer identity independently derived and scalar. Refuse if it matches any implementer; ambiguous reviewer evidence still refuses.
- Preserve validation of legacy schema 1-3 receipts. Add an explicitly versioned representation for a nonempty unique implementer set, and update every applicable reader/validator and canonical guidance.
- Unknown, malformed, contradictory or unparseable identity evidence must not become a successful independence claim.
- Preserve the original failed attribution and review streams; no history rewriting or fabricated skip.

## Acceptance and controls

1. A fixture with implementers {gpt-6.1-sol, gpt-5.6-sol} and reviewer gpt-6-astra writes a valid receipt carrying both implementers. Demonstrate its failure against pre-fix code.
2. Changing the reviewer to either implementer refuses, names the overlap, and writes no receipt. Commit these load-bearing negative controls and prove they discriminate against a blind implementation.
3. Mixed reviewer identity, unsupported/missing implementation attribution, malformed/empty/duplicate implementer lists refuse; legacy receipts remain valid.
4. Retained Kyle #1912 evidence can generate and validate a truthful receipt without a new review or alteration of source evidence.
5. Run required CPP checks, independent review, generated-skill parity, and `make verify`. Install only the validated helper family at a coordinated safe point, then resume Kyle #1912's ordinary gate.

## Scope

Receipt helper and its consumers/tests/registered controls, ADR 0007 and script reference, affected flow auto/finish canonical guidance and generated mirrors. Use an isolated worktree; leave the dirty shared CPP checkout untouched. This is a separate prerequisite fix, not an expansion of Kyle #1912's source diff.
