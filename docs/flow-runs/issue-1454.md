# Flow run record - issue #1454

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=f74776ffd9c348809b872cb96896d22b -->
## Run 1

- Run-id:            f74776ffd9c348809b872cb96896d22b
- Run-start:         1fdcfbeaa82f4bf31f96947cdf8486d4a3244344
- Issue:             #1454
- Base SHA:          1fdcfbeaa82f4bf31f96947cdf8486d4a3244344
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          master:kyle (mailbox message 6530, replying to plan 6529), with four conditions
- Recorded at:       2026-10-17T06:30:00Z

### Section B evidence
ca3030d (#1453) factored _derive_codex_from_thread, which this extends; nothing derives Qwen or OpenCode. Merged PRs: #1467-#1469 (adjacent). Duplicates: none. Measured (qwen 0.15.10, opencode 1.18.32, real harness output against a stub endpoint, including a tool-call turn): Qwen stream system/init.model and assistant message.model, with a persisted transcript ~/.qwen/projects/<slug>/chats/<session_id>.jsonl; OpenCode stream carries only sessionID, with the model in opencode.db `message` rows (providerID/modelID). Both record the REQUESTED model.

### Section C - the approved plan
1. `scripts/counter-model-receipt.py` - delegated harness detection; Qwen (transcript, cross-checked against init.model) and OpenCode (read-only db, schema-checked) derivations; the harness version in the evidence; flags --qwen-projects-dir and --opencode-db; per-harness evidence validation.
2. `tests/fixtures/delegated-streams/README.md` - provenance (real harness, stub endpoint, versions, no live-model run).
3. `tests/test_counter_model_review.py` - per-harness derivation from the captures; refusals.
4. `templates/delegated-driver-values/qwen.md` - STEP5_RECEIPT write command.
5. `templates/delegated-driver-values/gemma.md` - STEP5_RECEIPT write command.
Plus the committed captures under tests/fixtures/delegated-streams/, the rendered command docs (make delegated-core-write), the mirrors, and after merge one Nit Store comment for a live-endpoint capture.
Risks: the captures prove FORMAT, not a live run; a differing real stream fails closed. The model is the requested one, the same basis as Codex.
