<!-- flow-run n=1 id=73360dac89ed448ab0eea90490c9344b -->
## Run 1 - issue #1863 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1863
- Read at:      2026-11-20T12:28:16Z
- updatedAt:    2026-11-20T11:59:29Z   (context only - moves on comments and labels)
- Body digest:  4a6abe90d9e10b015307fe0af9bd0b7fe113031d62e5d3197b3fde2195631f85   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3174 of 3174 (cap 16384)

### Body as read
Tier: 2

## Outcome

The Codex review prompt stops asking for checks that `flow-plan-record` already enforces mechanically, and a committed test proves each removed clause is still caught by the helper.

The candidates in `scripts/codex-review-run.sh`:

1. "each listed lane that the plan's 'Lanes for this change' table in this diff does not answer" - plan approval already refuses a record with a missing or incomplete lane table (#1731/#1744, #1815).
2. "each lane the plan marks 'will test' that no test in the diff exercises" - this overlaps the PLAN_COMPLIANCE will-test line (#1780) only partly, so it is a candidate, not a given.
3. "report each reader with no 'Reader:' row in the plan's table" - check whether approval or compliance enforces reader rows. If not, it stays.

The stand-in / could-not-fail clause stays: it is judgement a helper cannot make.

## Constraints

- A clause is removed only when the parity test shows the helper catches it. A clause the helper misses stays in the prompt.
- The review prompt text is asserted by `tests/test_lanes_contract.py` and `tests/test_changed_output_readers.py`. Update them deliberately; do not loosen them.

## Acceptance

- For each removed clause, a committed plan-record fixture that the clause would have flagged, and an assertion that `flow-plan-record approve` or `compliance` refuses it. Before deleting anything, run each fixture against the current helper and report the result.
- Lane+reader findings per review fall back toward the pre-11-11 rate, as measured by the finding-kind counts (sibling issue) or the review-yield report.

Owner decision: removes review obligations, so it needs the #1850 Q2 ruling.

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
