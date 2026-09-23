# Flow run record - issue #1191

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1191
- Base SHA:          e19f75b
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          wave `claude-improvements` orchestrator, session
                     `claude-improvements-new`, mailbox rev 4, acked by this session
                     after the content was held.
- Recorded at:       2026-09-23T13:20:00Z

## Section B evidence

- Commits touching `scripts/gh-pr-merge.sh` or `tests/test_gh_pr_merge.py` since the issue was
  filed (2026-09-21T20:57:47Z): NONE.
- The three issues this guard was built from are all CLOSED and none supersedes this one: #726
  (detect a negated keyword before the squash), #772 (the guard fired on any earlier negation
  and blocked valid merges, so it was NARROWED), #794 (extend to incidental proximity, and scan
  commit subjects). This is a fourth shape none of them covers.
- Searched "closing keyword gh-pr-merge" across all states: only #1191 itself, plus #864 (Nit
  Store) and #1069 (unrelated). No duplicate and no superseding issue.
- Provenance checked: nit-store record #864 comment 5765879691, found by a worker in wave
  kyle-improvements, cause identified by that wave's orchestrator, filed at the owner's
  direction.
- THE DEFECT WAS REPRODUCED BEFORE PLANNING AGAINST IT. Using the guard's own keyword pattern
  under its own `LC_ALL=C` byte orientation, against the real body shape: scanning line by line
  yields ZERO matches, while the identical pattern applied to the whole text matches at byte 62.
  That localises the defect to the ITERATION rather than the pattern, and is why the fix is
  small.
- Baseline captured before any edit: `tests/test_gh_pr_merge.py` is 122 passing tests, 17 of
  them close-guard tests.

## Section C - the approved plan

1. `scripts/gh-pr-merge.sh` - make `guard_negated_close_keywords` and
   `guard_incidental_close_keywords` scan each source as ONE TEXT rather than line by line, so
   the existing pattern is handed the keyword and the reference together. Offsets become
   text-relative; the guard is already byte-oriented under `LC_ALL=C`, so multibyte punctuation
   is unaffected. The prefix that feeds the negation test gains NEWLINE in its clause-boundary
   trim set, so the negation window stays inside the keyword's own line even though the match
   span may now cross one - that is what preserves #772's narrowing. Record the reversal trigger
   beside the code.
2. `tests/test_gh_pr_merge.py` - the committed cases. The load-bearing one reconstructs the real
   kyle PR #1313 shape - a heading ending on the keyword, a blank line, then the reference
   opening the next paragraph - and must REFUSE. Plus a case pinning guard ORDERING (the negated
   guard runs first, so one clean stop and one override rather than two), and a case proving a
   legitimate multi-paragraph body that merely mentions a keyword and a number far apart is
   still allowed through.
3. `docs/flow-runs/issue-1191.md` - this record.
4. `docs/flow-runs/issue-1191.as-read.md` - the as-read snapshot of the issue body.

Scope: 4 files, approximately 100 lines net.

Risks: R1 (principal) is OSCILLATION rather than correctness. #772 narrowed this guard because
it was once too broad and blocked valid merges; widening the scanned span pushes back in that
direction. The mitigation is structural: the match span widens while the negation window does
NOT, because newline joins the clause-boundary trim set. The orchestrator verified the safety
net rather than taking it - `test_distant_not_in_issue_771_title_does_not_block_merge`,
`test_distant_no_in_summary_clause_does_not_block_merge` and `test_plain_close_keyword_passes`
are #772's narrowing expressed as executable allow-side cases, and an over-widening turns them
red. PRE-COMMITTED REVERSAL TRIGGER: if valid merges start being refused after this, narrow the
SPAN to the enclosing markdown block - do NOT restore line-orientation, which is the blindness
this issue is about. R2: both guards can match this one construction (negated AND possessive);
the negated guard runs first and exits 5, so the operator sees one clean stop - pinned by a test
rather than left to call order. R3: moving from per-line offsets to whole-text offsets is most
likely to surface in the typographic cases (em dash, en dash, curly apostrophe), which already
depend on byte-oriented trimming; they are inside the prediction below.

PREDICTION BEFORE MUTATING: all 122 existing tests pass, the 17 close-guard tests among them
unchanged, plus the new cases. A red among those 17 is R1 arriving and goes to the orchestrator
rather than being adjusted away.
