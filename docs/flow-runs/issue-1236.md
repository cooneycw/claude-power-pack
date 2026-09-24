# Flow run record - issue #1236

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1236
- Base SHA:          c1a60bf623260381d203ed6d35dd3be74145e0e9
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the session user (cooneycw), replying "approved" to the Step 3 report
- Recorded at:       2026-09-24T09:44:50Z

## Section B evidence
Commits touching the planned paths since the issue was filed (2026-09-24): none.
Open PRs touching them: none. Duplicate/superseding issues: none (#1076 and #1067
are parents; #1075 closed 2026-09-24). The re-run R6 sweep found more stale
present-tense references than the issue listed; they are included as the same work.

## Section C - the approved plan
1. `codex/skills/README.md` - CxPP vendored this source until its 2026-09-22 dormancy (past tense).
2. `docs/skills/common-memory.md` - the Codex telemetry writer was CxPP's, dormant since 2026-09-22.
3. `docs/contracts/friction-ledger-shared-store.md` - CxPP as a former consumer in the header, harness row and references; the `codex` value stays.
4. `docs/agents/glossary.md` - ledger tag "originally for codex-power-pack"; counter-model paragraph in past tense.
5. `.specify/specs/codex-consolidation/spec.md` - tick the seven unticked dormancy boxes, each with an evidence pointer on its bullet.
Scope: 5 files, ~25 lines, prose only.
Risks: markdown gates (Unicode dashes, lifecycle-pointer check) apply to the edits; the NIT_STORE=227 mapping is deliberately left alone and nit-stored.
