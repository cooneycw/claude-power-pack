# Flow run record - issue #1850

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=24a6e5c8d5254560a53eeb7bf5977625 -->
## Run 1

- Run-id:            24a6e5c8d5254560a53eeb7bf5977625
- Run-start:         2df9b1c6846ce52d99058d9b085f0d70e0ab93cb
- Issue:             #1850
- Base SHA:          2df9b1c6846ce52d99058d9b085f0d70e0ab93cb
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session, 2026-11-16, after Q1-Q7 rulings (issue comment 6903447874) and N1-N3 / G3-1..G3-5 rulings
- Recorded at:       2026-11-16T02:05:00Z

### Section B evidence
Commits since issue creation on the touched paths: 716b7c3f (#1855), 62e928b9 (#1854), 06392d40 (#1852), 2df9b1c6 (#1856). Merged PRs: #1856, #1855, #1854, #1852, #1845, #1843, #1841, #1840. Overlapping/superseding issues inspected: skillc#726 (charter drafting round; overlaps, does not supersede), #1513 (closed not planned), #956, #1014, #950 (unrelated). Sibling worktree with unpushed commits: issue-1821 (flow-plan-record only, no overlap).

### Owner rulings
Q1 scope: one open issue, git repo with CPP helpers, Claude or Codex session (N1), worktree implementation. Refused mechanically: work in flight. Recommended at Step 3, close only with owner yes: open prerequisites (warn); no longer necessary (duplicate in code, or ADR divergence as evidence, never absolute); low frequency and low severity (offer to close; never a security risk).
Q2: session sorts groups 1/2; owner ruled group 3 row by row: G3-1 accept, G3-2 accept, G3-3 accept (move to ADR 0007), G3-4 accept if /flow:deploy verified to carry the same guards, G3-5 move.
Q3: fix the real defect - state the existing docs-only lane exemption where the run reads it. Q4: documentation removed from the flow; Steps 8 and 9 merged; 7 steps. Q5: (b) optional review for a Tier 1 docs-only change, recorded with a new skip reason, honour system bound to the approved plan. Q6: proportionality question once in issue-contract, pointers in eli5 and Step 6 1c. N2: (b) skillc-shaped charter, clauses only where an existing test backs them. N3: re-anchor parity citations by hand.

### Section C - the approved plan
1. `charters/flow/auto/CHARTER.md` - new charter: scope, refusals and recommendations, Tier 1 path, no-bypass; clauses only with existing tests
2. `.claude/commands/flow/auto.md` - charter pointer, Tier 1 path, Step 5 removed, Steps 8+9 merged, group 1 trims, G3 rows, Step 6 1c proportionality line, renumber to 7 steps
3. `.claude/commands/flow/eli5.md` - lane exemption beside the every-lane rule, proportionality pointer, Q1 recommendations within the word cap
4. `.claude/commands/flow/finish.md` - remove Step 2d documentation check
5. `.claude/commands/documentation/help.md` - drop the update_docs sentence
6. `Makefile` - remove the update_docs target and its verify-coverage annotation
7. `docs/agents/lanes.md` - lane definition and two worked examples
8. `scripts/counter-model-receipt.py` - tier-1-docs-only skip reason
9. `tests/test_counter_model_review.py` - red/green cases for the skip reason; renumbering pin updated
10. `.claude/command-word-budgets.tsv` - lower rows for auto.md and finish.md
11. `docs/agents/driver-parity.json` - re-anchor citations
12. `tests/test_delegated_driver_gates.py` - step renumbering
13. `tests/test_eli5_gate_not_bypassable.py` - step renumbering
14. `docs/reference/flow-auto-rationale.md` - renumbering and withdrawn paragraphs recorded
15. `docs/decisions/0007-counter-model-review.md` - receives the #1557 note and the Tier 1 skip reason
16. `docs/scripts/speckit-context.md` - receives the per-state speckit-context guidance (G3-5)

Scope: Tier 3, ~16 files. Lanes: Harness will test (make codex-skills); Driver will test (make driver-parity-check); Project state will test (a leftover update_docs target is unused, never an error); Checkout, Coordination, CI provider, Toolchain version, Clone shape, Run location, Gate target, Wave role state not applicable. Readers: codex-skill-sync.py, skillc contracts/gauntlet, CI receipt check, delegated drivers. Risks: an accepted G3 row guarded a real failure; renumbering misses a step reader; charter overlap with skillc#726.

### Lanes for this change

| Lane | Answer |
|---|---|
| Checkout | not applicable - no helper's root or path discovery changes |
| Harness | will test - Claude install / Codex install: `make codex-skills` mirrors the new charter and the trimmed command; Codex install is checked by the mirror check, not a live Codex run |
| Driver | will test - `/flow:auto` / delegated drivers: `make driver-parity-check` after renumbering and re-anchoring |
| Coordination | not applicable - no coordination path changes |
| CI provider | not applicable - CI status handling is trimmed in prose only; the helper is unchanged |
| Project state | will test - a repository that has adopted `update_docs` / one that has not: the flow no longer reads the target, so both behave the same; checked by grep of the flow commands |
| Toolchain version | not applicable - no toolchain-dependent code |
| Clone shape | not applicable - no history reads change |
| Run location | not applicable - no caller-directory behaviour changes |
| Gate target | not applicable - no gate runner change |
| Wave role state | not applicable - no wave registry change |
| Reader: scripts/codex-skill-sync.py | will test - `make codex-skills-check` reads the new charter |
| Reader: skillc contracts | will test - `skillc contracts` run on the charter if skillc is on PATH; otherwise not covered |
| Reader: CI receipt check (counter-model-receipt.py validate) | will test - unit tests feed the real writer and validator the new reason |
