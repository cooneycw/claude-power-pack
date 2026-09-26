# Flow run record - issue #1259

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #1259
- Base SHA:          8dad506
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          cooneycw (owner, interactive session: "approved.")
- Recorded at:       2026-09-26T15:30:00Z

## Section B evidence
Commits since filing: aa2653e (#1274), 8dad506 (#1275) - none touching the lane's paths.
Merged PRs since filing: #1275, #1274, #1270, #1255 - none address these findings.
Siblings (overlap, not duplicates): #1264, #1268, #1269, #1273, #1276.
Finding 1 delivered by #946 (replayed kyle's broken anchor: UNRESOLVED; pinned by
test_an_anchor_that_crashes_is_unresolved_not_inert). Finding 5 delivered by #1117
(shellcheck absent -> UNAVAILABLE). Finding 6 moved to its own issue (owner decision).

## Section C - the approved plan
1. `tests/conftest.py` - pin sys.pycache_prefix + PYTHONPYCACHEPREFIX to a fresh per-session dir
2. `tests/test_pycache_isolation.py` - red case: a stale legacy .pyc matching size+mtime must not execute
3. `docs/agents/evidence-deleting-idioms.md` - entry on size-preserving mutations and __pycache__
4. `lib/cicd/makefile_declaration.py` - a later single-target rule no longer erases a multi-target shared group
5. `tests/test_cicd_makefile.py` - red case for `build deploy:` then `build: lint`
6. `scripts/counter-model-receipt.py` - new `format-mismatch` verdict for a Findings section with severity-bearing content in an unrecognised shape
7. `tests/test_counter_model_review.py` - red case and four-verdict corpus
8. `tests/fixtures/counter_model/bullet-shape.review.md` - the #1056 bullet-shape transcript
9. `.claude/commands/flow/auto.md` - Step 6 item 1c: format-mismatch is a review that happened, never a skip
10. `scripts/skills-check.py` - reject unquoted scalars YAML refuses or rewrites (`: `, trailing `:`, ` #`, leading indicator)
11. `tests/test_skills_check.py` - red cases plus a PyYAML cross-check over real SKILL.md files
12. `scripts/check-test-binary-guards.py` - which-guarded conditional branches, helper call-line allow, hyphenated filenames, and the sys.executable .py hop
13. `tests/test_test_binary_guards.py` - one red case per sub-fix
14. `tests/test_shellcheck_gate_find_boundary.py` - drop the two now-unneeded allow annotations

Scope: ~14 files, ~500-700 lines. Risks: the .py hop may flag fail-soft tests (measure; narrow rather than annotate); cold bytecode per run; rebase conflicts with sibling lanes.
