# Flow run record - issue #1189

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1189 (defect 1, and the PRODUCER half of defect 2)
- Base SHA:          c5b1c5e
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the owner, directly in the invoking session ("approved")
- Recorded at:       2026-09-24T09:20:00Z

## Prior run on this issue

This path holds one record per issue, so this file REPLACES the record of the
first run (PR #1223, the consumer half of defect 2). That record is preserved in
history at `99670b5:docs/flow-runs/issue-1189.md`, and it is what deferred the
two halves delivered here, on a lane constraint (#1212 held the lexicon).

## Section B evidence

Issue filed 2026-09-21T20:57:28Z.

- Commits touching `scripts/flow-wave-lexicon.sh` since filing: `8f997af`
  (#1212, the lane blocker, merged) and nothing else. `99670b5` (#1223) touched
  `scripts/flow-wave-plan.py` - the consumer half, already delivered.
- Merged PRs inspected: #1223, #1216, #1212, #1209, #1205, #1203, #1202, #1200,
  #1199, #1195, #1194, #1181, #1179, #1176. Only #1223 addresses this issue.
- Duplicate / superseding issues: none. Adjacent and distinct: #701, #980, #709,
  #1079, #1220, #1222.
- Reproduced on c5b1c5e: a HOLD with a prose reason records
  `"reason":"GATE: HOLD (no reason given)"` and `FLOW_LEXICON: recorded`;
  `GATE: GO journal-false-red` is `invalid`.

## Section C - the approved plan

1. `scripts/flow-wave-lexicon.sh` - (a) refuse a `GATE: HOLD` carrying no reason
   either inline or as `- item` lines beneath (the refusal, not a widened
   harvest); (b) accept a subject that is `#N` or a kebab slug of at least two
   parts; refuse a bare number ("did you mean #N") and a single word; `record`
   emits `subject` for a slug and `issue` for a number. Grammar header updated.
2. `tests/test_flow_wave_lexicon.py` - red-first regression tests, an end-to-end
   slug-ruling-beside-numeric-hold test through `flow-wave-plan.py`, and a reason
   added to the live reasonless HOLD specimens.
3. `.claude/commands/flow/wave.md` - grammar table rows.
4. `controls/flow-wave-lexicon/control.json` - new registered control (ADR 0008
   row 17 is X-class with none); with its run-case.sh, cases and a historical
   anchor of the pre-change lexicon, all under the same directory.
5. `docs/decisions/0008-instrument-negative-control-bound.md` - row 17 names it.
6. `codex/skills/**` - generated mirrors.
7. `docs/flow-runs/issue-1189.md`, `.as-read.md` - run artifacts.

Scope: 1 script, 1 test module, 1 command doc, 1 control, 1 ADR row, generated
copies. Roughly 200-300 lines.

Risks:

- A forgotten `#` on a kebab-shaped word (`GATE: GO looks-good`) records a slug
  ruling. The two-part rule and the bare-number refusal narrow it; they do not
  remove it.
- Terse reasonless HOLDs that are accepted today are refused at `send`. Loud and
  correctable at the sender, which is the point, but a behaviour change.
- `flow-worktree-claim.sh` has the same issue-required shape; out of scope.
