# Flow run record - issue #1710

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=1b19501ef6b54773bea326f187e6ab27 -->
## Run 1

- Run-id:            1b19501ef6b54773bea326f187e6ab27
- Run-start:         ee4ca592f6a6c5da9c51750f9afe46abe091761b
- Issue:             #1710
- Base SHA:          68d5fedf152b4446d35bd42f50e0b6c326ce43cb
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, authority model orchestrator-only), by mailbox rev 41 to role cpp-1508 at 2026-11-11T23:33:04-05:00: "GATE: GO-WITH-CONDITIONS #1710" (assignment a1700hold-583-1710b-1728-g5, item 3, rows 572 and 646)
- Recorded at:       2026-11-12T04:50:00Z

### Section B evidence
- Row 572: the direction comment in `scripts/counter-model-receipt.py` still describes the default direction as Claude implements and Codex reviews only.
- Row 646, wider than filed: `_model_key('claude/claude-opus-5-5[1m]') == _model_key('claude/claude-opus-5-5')` is False at 68d5fedf, and a write with a suffixed Claude implementer and an unsuffixed Claude reviewer passes the overlap check (it stops later, on a missing review report), where the unsuffixed pair is refused as overlap.
- Scan of committed receipts on origin/main: suffixed names 0 of 376 here, 0 of 326 in kyle, 0 of 153 in skillc; the same pattern matches two non-receipt files here.
- Local Claude transcripts carry exactly one bracketed form, `[1m]`.
- Rows 578 and 637 moved to the Nit Store (#1725 comments 6814620906, 6814621087); row 689 held for #1697 Part 2; the two-spellings finding is #1747.

### Section C - the approved plan
Rulings and conditions attached to the approval: a trailing context-window tag, exactly `[` digits `k` or `m` `]` at the end of the name, is not model identity, and the `_model_key` docstring and any document stating the no-alias line are reconciled in this change; one normaliser used at every comparison site (write-time overlap, validation, the reviewer-in-implementers check), each site shown refusing the suffixed pair; narrowness tested both ways (`[1m]`, `[200k]` stripped; `foo[beta]`, a tag in the middle, `[1M]`, `[]`, two tags not); the negative case goes in an existing control if one drives the overlap refusal, otherwise the orchestrator is told before a new one is made; this repository's receipt corpus re-validated before and after with identical verdicts; Refs for #1710, no closing line; two review passes, ask before a third.

1. `scripts/counter-model-receipt.py` - the direction comment (row 572); one normaliser for the context-window tag, used by `_model_key`, by the legacy reviewer-in-implementers check, and where a Claude transcript's model is read.
2. `tests/test_counter_model_adapters.py` - end-to-end red case for the suffixed self-review pair, the reviewer with two spellings, the validation site.
3. `tests/test_counter_model_review.py` - narrowness of the normaliser both ways; the legacy validation site; the legacy implementer derivation.
4. `tests/fixtures/counter_model/adapters.json` - the suffixed pair as a committed writer case beside `same-model`.
5. `docs/agents/counter-model-evidence.md` - the rule, reconciled with the no-alias sentence.
6. `.claude/commands/codex/code_review.md` - AMENDMENT, row 689 (see below): one sentence at the launch recipe against `--ephemeral`, with an equal trim.

Scope: about 20 lines of code, 100 of tests, one committed case, one paragraph of documentation.

Risks: over-normalising a real name that ends in a bracketed tag; a comparison site left on the raw name; an old receipt changing verdict (scanned: none carries a suffix).

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | will test: pytest in this linked worktree, each red shown on 68d5fedf first |
| Harness | will test: Codex mirrors rebuilt and tests/test_codex_skill_sync.py; a live Codex run is not covered |
| Driver | will test: Claude-reviews-Claude and Claude-reviews-Codex attribution through the writer with fixture transcripts; a real delegated run is not covered |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | not applicable: no pipeline code |
| Project state | will test: this repository's committed receipts re-validated before and after; kyle and skillc receipts scanned read-only |
### Amendment after approval - row 689

Added on the wave orchestrator's instruction (mailbox rev 48, 2026-11-12T00:14:44-05:00, "GATE: GO-WITH-CONDITIONS #1710": row 689 as a further commit on this branch). Everything above this heading is as first approved, except item 6 of Section C, which this amendment added.

- Issue:             #1710
- Base SHA:          0bf7ba72d98754cab02b52758241d6a7ff5175a1
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, authority model orchestrator-only), by mailbox rev 48 to role cpp-1508 at 2026-11-12T00:14:44-05:00: "GATE: GO-WITH-CONDITIONS #1710" (row 689, as a further commit on this branch)
- Recorded at:       2026-11-12T05:20:00Z

#### Evidence (row 689)
- Row 689: a `codex exec --ephemeral` review writes no rollout, so the receipt writer later refuses with "expected one Codex rollout ..., found 0" and the review cannot back a receipt. On #1658 three passes were lost this way.
- On origin/main 0bf7ba72 the word "ephemeral" appears in none of `.claude/commands/codex/code_review.md`, `.claude/commands/flow/auto.md`, `scripts/counter-model-receipt.py`, `docs/agents/counter-model-evidence.md`.
- `.claude/commands/codex/code_review.md` is at its word budget, 6,359 of 6,359.

#### Plan (row 689)
Conditions attached to the approval: the message addition is for the zero-rollout case only and names `--ephemeral` as the first thing to check, not as the diagnosis, since a wrong thread id or a moved sessions directory reads the same way; tests: zero names it, two does not, and a wrong thread id with other rollouts present still gets it without claiming ephemeral was used; `code_review.md` stays at 6,359 words by an equal trim in the same document, named in the PR, not taken from the three paragraphs #1697 Part 2 added, with an independent old-versus-new read; review pass 2 of the branch covers this commit, ask before a third.

1. `scripts/counter-model-receipt.py` - the two refusals for zero Codex rollouts name the ephemeral launch as the first thing to check.
2. `.claude/commands/codex/code_review.md` - one sentence at the launch recipe against `--ephemeral`, with an equal trim.
3. `docs/agents/counter-model-evidence.md` - one sentence naming `--ephemeral` as incompatible with a receipt.
4. `tests/test_counter_model_review.py` - the zero cases name it, the two-rollout case does not.

Scope: about 10 lines of code, 15 of tests, two sentences of documentation.

Risks: the trim in `code_review.md` removing an instruction; a test elsewhere pinning the refusal text.

#### Lanes (row 689)

| Lane | Answer |
|---|---|
| Checkout | will test: pytest in this linked worktree, red first |
| Harness | will test: command-doc word budget, Codex mirrors and tests/test_codex_skill_sync.py; a live Codex run is not covered |
| Driver | not applicable: no driver-specific code |
| Coordination | not applicable: no wave, mailbox or registry code |
| CI provider | not applicable: no pipeline code |
| Project state | not applicable: no issue, label or board writes beyond the PR |
