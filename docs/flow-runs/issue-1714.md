# Flow run record - issue #1714

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=1581870015cd419aad4363f89b6bb557 -->
## Run 1

- Run-id:            1581870015cd419aad4363f89b6bb557
- Run-start:         a23a1072e4e2341d00530e2fb7b5ffae10f43717
- Issue:             #1714
- Base SHA:          a23a1072e4e2341d00530e2fb7b5ffae10f43717
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 62: "GATE: GO-WITH-CONDITIONS #1714"
- Recorded at:       2026-11-12T06:30:00Z

### Section B evidence
- commits on codex/code_review.md since 2026-11-11T23:07:41Z: 658cdd55 (#1695), 0bf7ba72 (#1697 Part 2), a23a1072 (#1710); none touches a row here
- all five rows re-checked and present; seq 735 is a defect shipped by #1695
- the limit: Codex CLI 0.167.1 refuses stdin over 1,048,576 characters (`input_too_large`), recorded on #1670 in Nit Store #864 seq 719
- in a Kyle session container a review reads scope diff-only (nothing in the kyle checkout sets CODEX_REVIEW_SANDBOX), so an oversized patch there will be blocked where it used to end as a skipped receipt; coordination issues filed by the orchestrator before any edit: kyle #2367, skillc #709, kyle-candidate #12

### Conditions attached to the approval
1. On the repository route what the reviewer read is CHECKED: the prompt requires a list of files read; the relay compares it with the patch's own file list, names every file not read as NOT READ, and relays the review as partial. A reviewer that reads nothing cannot return an ordinary clean review on this route.
2. The limit is one named constant with its source beside it, compared with a stated margin; tested at the limit, one under, one over, and at the margin boundary.
3. A receipt written after a repository-route run binds the same patch the writer recomputes; if it cannot bind, stop and report.
4. The word `unavailable` is absent from every output on both over-limit paths.
5. auto.md is not edited unless the wrong sentence and its exact replacement are shown first.
6. code_review.md stays at 6,359 words; trims recorded before removal; independent old-versus-new read; the #1697 Part 2 paragraphs and the #1710 row 689 text intact.
7. The mktemp change: grep for readers of the three suffixes first. BSD mktemp stays not covered.
8. The live oversized run is an observation, recorded with date and model, not a test.
9. Exact lane names; full suite before the first gate; two passes, ask before a third.

### Section C - the approved plan
1. `.claude/commands/codex/code_review.md` - the patch is measured before the run; over the limit with scope full it is read from the repository and what was read is checked; over the limit otherwise the run is blocked with a named reason; the scope probe no longer takes SIGPIPE; mktemp templates end in their X run; a dangling or unsearchable lanes.md reads as could-not-be-read
2. `tests/test_code_review_large_patch.py` - the document's own blocks at the limit, one under, one over and at the margin; both over-limit routes; the not-read comparison
3. `tests/test_code_review_sandbox_scope.py` - the probe under pipefail in a large repository
4. `tests/test_lanes_contract.py` - a dangling symlink and an unsearchable directory
5. `tests/test_code_review_diff_file_cleanup.py` - every mktemp template ends in its X run
6. `docs/commands-reference.md` - the trimmed text, recorded in a commit before removal
7. `CHANGELOG.md` - entry
Scope: 7 files, about 300 lines, mostly tests.
Risks: the limit is Codex's and may change; on the repository route a reviewer that claims to have read a file it did not read passes the comparison; BSD mktemp cannot be exercised here.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test: the scope probe in a large temporary repository |
| Harness | not covered: /codex:code_review is not generated as a Codex skill; no Codex-driven run is exercised |
| Driver | not covered: the delegated drivers' review text is not changed |
| Coordination | not covered: no Kyle run |
| CI provider | not applicable |
| Project state | will test: lanes.md present, absent, a dangling symlink, and under an unsearchable directory |
| Reader: /flow:auto Step 6, which reads the exit code and markers | not covered by a deterministic test: an agent follows it; the passage is read against the new stop |
| Reader: counter-model-receipt.py, which binds the reviewed patch | will test: a receipt written after a repository-route run binds the same patch |
| Reader: the reviewing model, which must fetch the diff itself on the new route | not covered by a deterministic test: one live run on an oversized patch, recorded as an observation |
