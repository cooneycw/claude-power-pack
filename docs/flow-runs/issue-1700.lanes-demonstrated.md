# Lanes demonstrated - issue #1700

What was actually exercised for each lane the plan answered "will test".

| Lane | What was demonstrated |
|---|---|
| Checkout | Tests build scratch repositories, attached and detached, in `tests/test_flow_finish_gate.py`; the run itself was a linked worktree |
| Harness | The Claude writer path through `tests/test_counter_model_review.py`; Codex mirrors rebuilt with `scripts/codex-skill-resync.sh` and `tests/test_codex_skill_sync.py` passed; all four Codex bundles that ship the gate were listed and ship `counter-model-receipt.py` beside it. No live Codex run |
| Driver | The `/flow:auto` Step 6 wording, read independently three times. The delegated drivers were not separately exercised |
| CI provider | `--enrolment-only` with an escalated receipt, an unruled count, a scopeless escalated review and the whole receipt corpus, in scratch repositories. The live pull_request pipeline is this PR's own CI |
| Project state | A repository on the new gate. A repository pinned to an older gate was measured with the pre-change script: it prints `receipt:` for an escalated receipt and passes, and the pre-change validator rejects the count |
