# Flow run record - issue #1615

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=b29cb7484af94828828e9550ec5c53f3 -->
## Run 1

- Run-id:            b29cb7484af94828828e9550ec5c53f3
- Run-start:         1f8d9ca24a1f9553159e5c8a1b43445c3330ac9b
- Issue:             #1615
- Base SHA:          1f8d9ca24a1f9553159e5c8a1b43445c3330ac9b
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          cooneycw (owner, in session kyle-cli-helper)
- Recorded at:       2026-10-31T23:59:00Z

### Section B evidence
No commits to scripts/counter-model-receipt.py and no merged PRs since 2026-10-31T23:25Z; no duplicate issue.
Reframing: #1584 (commit 4dca7976, PR #1597) made an unresolved Claude turn refuse deliberately
(test_unresolved_claude_turns_cannot_be_dropped); a blanket sentinel skip would undo it. Host census:
469 `<synthetic>` records, all assistant, non-sidechain, 0 input / 0 output tokens; no other sentinel shape.

### Section C - the approved plan
1. `scripts/counter-model-receipt.py` - in the claude-runtime evidence loop, skip a record only when model is exactly `<synthetic>` AND usage reports zero input and zero output tokens; every other sentinel/blank/missing-usage still refuses; refusal names the unresolved value; post-loop empty check unchanged.
2. `tests/test_counter_model_review.py` - red cases: real + zero-usage synthetic writes; synthetic-only refused; synthetic with output tokens refused; unknown sentinel with zero usage refused; fix the stale docstring on test_unresolved_claude_turns_cannot_be_dropped.

Scope: small (2 files). Risk: trusting the `<synthetic>` label by name; mitigated by the zero-token requirement.
