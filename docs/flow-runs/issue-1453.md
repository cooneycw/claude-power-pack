# Flow run record - issue #1453

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=1f6e64f429fc4dd88cc78d9f53aeb537 -->
## Run 1

- Run-id:            1f6e64f429fc4dd88cc78d9f53aeb537
- Run-start:         93f51ddc1ef2f82e60f15d31c82388b5f7be32be
- Issue:             #1453
- Base SHA:          93f51ddc1ef2f82e60f15d31c82388b5f7be32be
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6521, replying to plan 6520), with two points
- Recorded at:       2026-10-17T03:40:00Z

### Section B evidence
Commits since filing touching implementer derivation: none (fc87b5b, 145d42d, 77530ec, 0320c43, 93f51dd). Merged PRs: #1457, #1463, #1464, #1465, #1466. Duplicates: none; #864 c6227202040 adds the same-model constraint. Measured: a Codex session exposes CODEX_THREAD_ID to its commands; a codex child of a Claude session sees BOTH CLAUDE_CODE_SESSION_ID and CODEX_THREAD_ID.

### Section C - the approved plan
1. `scripts/counter-model-receipt.py` - --implementer-thread-id; flag-free env resolution (Claude id alone -> Claude; CODEX_THREAD_ID alone -> Codex from its own rollout; both -> refused, the message naming both exact flags; neither -> refused); shared thread->rollout->model derivation; implementer_evidence allowed on the default direction only for a codex/ implementer; the same-model check unchanged.
2. `tests/test_counter_model_review.py` - Codex skip via flag and via env; both set -> refused naming the flags; no rollout -> refused; ran with a same-model reviewer -> refused; schema accepts and refuses implementer_evidence; the delegated --implementer-exec-log path pinned as untouched with both env vars set.
3. `.claude/commands/flow/finish.md` - the receipt section: Codex sessions pass --implementer-thread-id "$CODEX_THREAD_ID"; the same-model rule.
4. `.claude/commands/flow/auto.md` - the same paragraph.
Plus regenerated codex/skills mirrors, and one Nit Store comment on #864 (cross-model = different provider family?).
Risks: the ambiguity refusal is the common case for a codex child of a Claude session, so only flag-free writes see it; codex gpt-X reviewing codex gpt-Y passes the existing check (left alone, raised in the Nit Store).
