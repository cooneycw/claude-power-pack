# Flow run record - issue #1076

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1076
- Base SHA:          47db657a09caba31453368df09b3696194265f74
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the session user (cooneycw), replying "approved" to the Step 3 report
- Recorded at:       2026-09-24T10:59:37Z

## Section B evidence
The clause's own expiry condition is met: #1075 closed 2026-09-24, CxPP private and
dormant, #1076 approved by the owner 2026-09-24 (comment 5811719107). Commits touching
docs/agents/issue-contract.md since 47db657: none. No command, test or script refers to
the section; only its 5 generated codex/skills mirrors. The Q10 presumption it restates
remains recorded in .specify/specs/codex-consolidation/spec.md and ledger.md.

## Section C - the approved plan
1. `docs/agents/issue-contract.md` - delete the "Codex-consolidation context - a TIME-BOUNDED clause" section (lines 73-123); nothing else changes.
2. `codex/skills/evaluate-issue/docs/agents/issue-contract.md` - regenerated mirror.
3. `codex/skills/flow-auto/docs/agents/issue-contract.md` - regenerated mirror.
4. `codex/skills/flow-finish/docs/agents/issue-contract.md` - regenerated mirror.
5. `codex/skills/flow-merge/docs/agents/issue-contract.md` - regenerated mirror.
6. `codex/skills/github-issue-create/docs/agents/issue-contract.md` - regenerated mirror.
Scope: 1 file edited (~51 lines removed), 5 mirrors regenerated. After merge, #1067 is closed by comment.
Risks: a structure check over the canonical contract could depend on the section; make verify decides.
