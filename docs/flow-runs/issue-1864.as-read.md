<!-- flow-run n=1 id=96fbfe91493340acaa867b10231914bc -->
## Run 1 - issue #1864 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1864
- Read at:      2026-11-21T14:56:40Z
- updatedAt:    2026-11-20T12:09:44Z   (context only - moves on comments and labels)
- Body digest:  ff4e58495aa978c219b0beca9b289d4329332e3bd15ad1a004e41095483f06d7   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 2904 of 2904 (cap 16384)

### Body as read
Tier: 2

## Outcome

Every Codex review finding carries a kind from a closed list, and the parsed verdict reports counts by kind. "Is the test-adequacy check paying for itself?" can then be answered from receipts rather than by keyword-guessing the findings text.

Proposed list: `correctness | security | edge-case | test-adequacy | plan-bookkeeping | simplification`.

## Constraints

- The list is written once and repeated nowhere else, in the same way as the `Origin:` / `Missed because:` lists.
- A finding with a missing or unknown kind is reported as such (`kind: unstated`), never silently bucketed into a real kind.
- `scripts/codex-review-run.sh` is sealed by hash in Kyle's pinned command contract (and the candidate's), and skillc's pinned subjects run the parser, so the prompt change alone is already an interface change. If kind counts also enter the receipt, that is a schema change too. Coordination issues filed 2026-11-20: cooneycw/kyle#2566, cooneycw/skillc#795, cooneycw/kyle-candidate#23.

## Acceptance

- Committed cases: a transcript with mixed kinds parses to the right counts, and a transcript with a finding that has no `Kind:` line reports `unstated`, not zero and not some default kind.
- `/codex:code_review` documents the field.

## Proposed approach

Add `- Kind: <...>` to the findings format in `scripts/codex-review-run.sh` and count it in `counter-model-receipt.py parse`.

## Evidence (shared by this issue and its three siblings)

Measured 2026-11-20 from 935 parsed Codex review sessions on the main host (2026-10-16 to 2026-11-20) and 989 committed counter-model receipts across kyle, skillc and claude-power-pack. Same-repo comparisons:

| Repo / period | findings/review | LOW/review | lane+reader findings/review | clean-pass rate | median tokens/review | passes/issue |
|---|---|---|---|---|---|---|
| CPP before 11-11 | 1.35 | 0.15 | 0.12 | 29% | 301k | 1.9 |
| CPP 11-15+ | 2.19 | 0.90 | 0.84 | 13% | 516k | 2.8 |
| skillc before 11-11 | 2.42 | 0.26 | 0.13 | 19% | 369k | 2.9 |
| skillc 11-15+ | 3.98 | 1.11 | 0.89 | 8% | 649k | 3.1 |

Receipt dispositions: CPP accepted 88% → 62% (rejected+deferred 12% → 39%); skillc accepted 98% → 73%.

The rise lines up with the lane clauses in the review prompt (#1704, 2026-11-11) and the reader/stand-in clauses (#1749, 2026-11-12), switching on per repo when `.claude/lanes.md` landed (CPP 11-11, kyle 11-13, skillc 11-15). Prompt size itself is flat. Limits: kyle's recent reviews mostly run in containers and are not in this sample; finding kinds were tagged by keyword. Owner direction is in [discussion #1830](https://github.com/cooneycw/claude-power-pack/discussions/1830) and #1850 (charter, Q2: "already enforced by a helper - delete the prose").

Siblings: #1862 (plan-only re-review), #1863 (drop duplicated review clauses), #1864 (finding kinds), #1865 (review-yield and escaped-defect report).




<!-- end of body -->
