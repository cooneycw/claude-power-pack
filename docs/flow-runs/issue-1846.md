# Flow run record - issue #1846

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=6f7c28fb940b45b4889b1ead9aacec9e -->
## Run 1

- Run-id:            6f7c28fb940b45b4889b1ead9aacec9e
- Run-start:         19e24318f456e55ef3aa524ba6f85739c58c8f85
- Issue:             #1846
- Base SHA:          19e24318f456e55ef3aa524ba6f85739c58c8f85
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner, in this interactive /flow:auto session ("approve."), after two redirects that widened scope
- Recorded at:       2026-11-15T19:56:00Z

### Scope revision (owner, this session)
The issue body lists `templates/delegated-driver-core.md` and `codex/code_review.md` as out of scope and calls itself Tier 1 at three files. The owner redirected the plan twice before approving: "codex:auto needs to be part of the scope" and "the 2nd model review also needs to be considered in scope". The approved plan is therefore six files (Tier 2 by shape). The shared core file `templates/delegated-driver-core.md` itself stays untouched; `/qwen:auto`, `/gemma:auto`, `flow/eli5.md` and `self-improvement/retro.md` stay out.

### Section B evidence
- commits since 2026-11-15T19:46:40Z: none touching `docs/agents/issue-contract.md`, `.claude/commands/flow/auto.md`, `docs/agents/counter-model-evidence.md`, `.claude/command-word-budgets.tsv`
- merged PRs that day: #1840, #1841, #1843 (all before filing; none touch these files); no open PR touches them
- duplicate/superseding issues: none (search returned #1844 the pilot, #1846 itself, unrelated #1268, #676, #864, #1725)
- sibling worktrees on this host: no unpushed commits on these paths
- found: #1844 is OPEN; its close depends on PR #1845 (open). PR #1845 counts its declared known gap as "1 deferred" in the review block, with the ruling in words.

### Section C - the approved plan
1. `docs/agents/issue-contract.md` - add "Supported scope and proportional prevention" before "How much document" (scope first, justification for permanent prevention, the accepted-limitation disposition, no silent discharge); two sentences relating it to Demonstrated / Revised / Deferred; condense the "Declare the tier" paragraph to offset the added words
2. `.claude/commands/flow/auto.md` - Step 6 1c: a fourth triage route, accepted as a limitation on the approver's ruling, linking the contract; within the 10410-word budget
3. `docs/agents/counter-model-evidence.md` - refusal policy: a third route on a declined pass (accept the finding as a limitation, no successor issue), linking the contract; one sentence on how the receipt counts it (under `deferred`, named in words in the PR block)
4. `templates/delegated-driver-values/codex.md` - Step 5 receipt slot: one sentence offering the accepted-limitation route on the approver's ruling, linking the contract; drop two explanatory parentheticals to stay inside the budget
5. `.claude/commands/codex/auto.md` - regenerated from item 4 with `delegated-core-vendor.py --write`
6. `.claude/commands/codex/code_review.md` - reviewer prompt: judge against the approved scope, state consequence within it, still report an out-of-scope concern and label it a proposed scope expansion; one line in Step 4 pointing at the contract

Scope: 6 files, about 60 lines. No scripts, tests or budget rows change.

Risks: `flow/auto.md` has 4 words to spare and `codex/auto.md` has 2, so each addition is paid for in its own passage or the work stops; `driver-parity-check` may react to the Step 6 edit; the reviewer prompt is an instrument and no behavioural test shows the new sentences do not make it quieter (the wording adds a label and says "still report it").

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | not applicable | Prose only; no path-dependent behaviour |
| Harness | will test (Codex install, Claude install) | `make codex-skills-check` builds the flow-auto, codex-auto and codex-code-review mirrors from the edited sources; the Claude install reads the sources. Not tested: a live Codex-driven run, and the reviewer's behaviour under the new prompt |
| Driver | will test (`/flow:auto`, `/codex:auto`); not covered (`/qwen:auto`, `/gemma:auto`) | `make delegated-core-check`, `make driver-parity-check`, `make command-docs-budget-check`. Qwen and Gemma keep three routes |
| Coordination | not applicable | No coordination call changes |
| CI provider | not applicable | No CI helper changes |
| Project state | not applicable | No adopted file or record is added |
| Toolchain version | not applicable | No code runs differently |
| Clone shape | not applicable | No git history is read |
| Run location | not applicable | No helper invocation changes |
| Gate target | not applicable | Consumers read the same text |
| Wave role state | not applicable | "The approver" keeps its existing meaning |

Reader: none - no output another part parses changes; the findings format the receipt writer reads is untouched.
