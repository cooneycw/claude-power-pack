# Flow run record - issue #1267

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1267
- Base SHA:          dad589b
- Necessity verdict: Still needed (items 1-4, 6); item 5 deferred to a follow-up PR by ruling
- Approval:          granted
- Approver:          run45 orchestrator (kyle fleet mailbox msg 2029, reply to ELI5 report msg 2026)
- Recorded at:       2026-09-28T14:07:08Z

## Section B evidence
- commits since 2026-09-26T14:12Z touching flow-plan-record.py or flow-worktree-claim.sh: none.
- PRs: none (search hit #1284 is merged and unrelated). dup/super: none.
- Reproduced on dad589b: mirror_source(SHA256SUMS) -> scripts/SHA256SUMS (absent); .claude mirror -> None;
  auto.md:608-613 has no exclusion guidance; flow-worktree-claim.sh:472 bare usage_fail.

## Section C - the approved plan
1. `scripts/flow-plan-record.py` - SHA256SUMS explained by a sibling bundled-script change in the same diff, else unresolved; a derived source absent from tree and diff is unresolved; the mirror regex gains .claude/.
2. `.claude/commands/flow/auto.md` - Section C guidance: do not list the plan record, snapshot or receipt; name a mirror's source.
3. `codex/skills/flow-auto/reference.md` - regenerated mirror.
4. `tests/test_flow_plan_compliance.py` - manifest+sibling agreement, manifest alone unresolved, .claude mirror attributed, absent derived source unresolved; red on dad589b.
5. `scripts/flow-worktree-claim.sh` - (ruling, item 6) the --issue refusal names the remedy (gh issue create, then --issue) and why; policy unchanged.
6. `tests/test_flow_worktree_claim.py` - the refusal names the remedy.

Scope: 5-7 files, ~200 lines. Risks: a manifest reorder with no bundled-script
change now reads as unresolved (correct, stated in the PR); auto.md is heavily
pinned. Item 5 (option B, append-only runs) is a separate follow-up PR.
