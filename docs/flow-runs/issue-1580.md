# Flow run record - issue #1580

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=88ce1a28fe74445fa4bce509c04a1aeb -->
## Run 1

- Run-id:            88ce1a28fe74445fa4bce509c04a1aeb
- Run-start:         8ceee357064b0d7e7b6e5cae863a6fd973385253
- Issue:             #1580
- Base SHA:          8ceee357064b0d7e7b6e5cae863a6fd973385253
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          kyle-wsjf root orchestrator (thread 01a177d6-6a9f-7293-8a92-aa7711b250fe)
- Recorded at:       2026-10-26T19:32:56Z

### Section B evidence

- Commits after the issue's 2026-10-26T19:27:11Z creation touching the planned paths: none.
- Merged PRs after creation matching counter-model receipt terms: none.
- Earlier adjacent work inspected: PR #1558 / commit eac62c9c (schema 3 fresh-flow attribution), which deliberately preserves whole-thread mixed-model refusal and does not cover this resumed flow.
- Duplicate or superseding issues inspected: #1557 is the closed fresh-flow predecessor; no duplicate or superseding open issue was found. #864 is the Nit Store containing the original finding, not a replacement issue.
- Current main inspected at 8ceee357064b0d7e7b6e5cae863a6fd973385253.

### Section C - the approved plan

1. `scripts/counter-model-receipt.py` - add schema 4 for a derived, nonempty, unique mixed Codex implementer list; retain scalar schemas 1-3; keep reviewer derivation scalar and refuse overlap with any implementer or ambiguous evidence.
2. `tests/test_counter_model_review.py` - commit the known-good mixed-model writer case, overlap controls for each implementer, malformed/empty/duplicate/non-string set refusals, ambiguous evidence refusals, legacy schema compatibility, and a real-evidence qualification path; run the primary case red before changing the helper.
3. `docs/decisions/0007-counter-model-review.md` - document the schema 4 representation, compatibility boundary, and all-implementer independence rule.
4. `docs/scripts.md` - update the receipt helper reference for mixed resumed Codex threads and its refusal boundaries.
5. `.claude/commands/flow/auto.md` - teach the canonical full lifecycle guidance how a derived mixed implementer receipt is represented and rendered without caller-selected identity or history windows.
6. `.claude/commands/flow/finish.md` - keep standalone finish guidance aligned with schema 4 and the any-implementer overlap refusal.

Scope estimate: Medium. Primary risks: accidentally weakening reviewer attribution, invalidating legacy schemas 1-3, or letting generated Codex mirrors drift from their canonical sources.
