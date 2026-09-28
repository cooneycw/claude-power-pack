# Flow run record - issue #1269

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1269
- Base SHA:          164fdd4d23f2eaf66ef4ba30408824f7c589c417
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          run45 orchestrator (fleet mailbox message 1723, replying to the ELI5 report in 1722)
- Recorded at:       2026-09-28T10:20:00Z

## Section B evidence

- Commits since 2026-09-26T14:12Z on the touched paths: bdd2d14 (#1283, parse
  format-mismatch only; addresses none of these items).
- Merged PRs since filing: 1296 1283 1255 1284 1280 1293 1286 1274 1270 1287
  1295 1275 1302 1279 - none address these items.
- Duplicate/superseding: none open. Related closed: #1030 (auto.md stages the
  receipt; the script itself still does not warn), #1109, #1171, #1048, #1047.
- Item 3 measured on three real codex-cli 0.158.0 rollouts: the first `"model"`
  match is session_meta.payload.base_instructions.provenance.model; it agreed
  with turn_context.payload.model on all three.
- Item 4: on the current harness sidechain records live in
  `<session>/subagents/agent-*.jsonl`; the guard is defence against the inline
  layout.
- Item 5: no receipts for #1162/#1165/#1166; not reconstructable - re-dispositioned
  by issue comment.
- Title's duplicate item = Nit Store comment 5749736750; 10 multi-receipt
  branches in a 120-receipt corpus, all with distinct heads where a head exists.

## Section C - the approved plan

1. `scripts/counter-model-receipt.py` - WARN-only tracked notice (COUNTER_MODEL_TRACKED: tracked|untracked|unknown), optional reviewer_evidence {thread_id, rollout} always written on ran, structural turn_context.payload.model reviewer read refusing none/ambiguous, isSidechain guard, refuse a second ran receipt for the same (branch, head).
2. `tests/test_counter_model_review.py` - one regression test per fixed item, each run red on 164fdd4; rollout fixtures moved to the real session_meta/turn_context shape.
3. `scripts/counter-model-reviewer-attribution.py` - switch _rollout_model to the same structural rule in lockstep; control cases and make negative-controls before and after.
4. `docs/decisions/0007-counter-model-review.md` - the reviewer_evidence field and the one-ran-receipt-per-(branch, head) convention.
5. `docs/flow-runs/issue-1269.md` - this plan record.
6. `docs/flow-runs/issue-1269.as-read.md` - the as-read issue snapshot.

Scope: about 250 lines across the files above.

Risks: the attribution script carries a registered negative control; a rollout
with no turn_context record (older Codex) is now refused where it used to pass.

Rulings (message 1723): (a) warn only, no git add; (b) change attribution in
lockstep; (c) refusing a rollout with no turn_context is correct and the
refusal names what is missing; dedupe approved with no override flag.
