<!-- flow-run n=1 id=d05b7fe3d54a49c7beed965534c89dfa -->
## Run 1 - issue #1865 as read

EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.
The issue is the authority; read it. This copy exists so a later check can
report that the source moved. It does not graduate.

- Issue:        #1865
- Read at:      2026-11-21T14:51:59Z
- updatedAt:    2026-11-20T11:59:33Z   (context only - moves on comments and labels)
- Body digest:  45baffe2f64a11bd5bfd1fa79effedc565ab64b2e587eb3cffe3e49c6a83beff   (sha256 of the FULL body; the verdict keys on this)
- Stored bytes: 3121 of 3121 (cap 16384)

### Body as read
Tier: 1

## Outcome

A periodic report states how many merged fixes were defects that escaped review, and why their original tests missed them. That gives the review process an outcome measure, not only an effort measure.

Today the `Origin:` / `Missed because:` lines (#1697/#1738) are almost unused. A search for "Missed because" in issues since 2026-11-11 returns two hits across kyle, skillc and CPP, and neither is an escaped-defect record. Without those lines, nobody can tell whether the review's extra test-adequacy findings reduce escapes.

## Constraints

- This is a report, not a gate. A new mandatory gate needs the justification in the issue contract's "Supported scope and proportional prevention"; that case has not been made. Revisit it only if the report shows the lines are being skipped on real defects.
- The answer lists stay where they are, in `docs/agents/closing-report-contract.md`. The report reads them and does not restate them.

## Acceptance

- The report lists merged `fix(...)` PRs per repo for the period, flags those whose closed issue lacks `Origin:` / `Missed because:`, and tallies the answers given.
- Negative control, committed: a fixture fix PR whose issue lacks the lines is flagged, and one that carries them is not. A report of "0 escapes" must be distinguishable from "nothing was readable".
- The same report includes review yield per repo: accepted / rejected / deferred from receipts, and passes per issue. This turns the 2026-11-20 measurement into a standing series.

## Proposed approach

A script (for example `scripts/review-yield-report.py`) reached from `/monthly:create`.

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
