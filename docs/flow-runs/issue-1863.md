# Flow run record - issue #1863

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=73360dac89ed448ab0eea90490c9344b -->
## Run 1

- Run-id:            73360dac89ed448ab0eea90490c9344b
- Run-start:         de3fb38e759480439355be6aa83dc3f56a07a214
- Issue:             #1863
- Base SHA:          de3fb38e759480439355be6aa83dc3f56a07a214
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), interactive "approved" in the /flow:auto session
- Recorded at:       2026-11-20T12:33:08Z

### Section B evidence
- commits: none touching scripts/codex-review-run.sh, scripts/flow-plan-record.py, tests/test_lanes_contract.py, docs/agents/lanes.md since 2026-11-20T11:59:15Z
- PRs: none merged since filing; none open
- dup/super: #1862, #1864, #1865 (siblings, different scope); #1850 (Q2 ruling source)
- parity experiment against the current helper: clause 1 (unanswered lane) CAUGHT by approve (plan-omits-lane fixture exit 1, names Session age; plan-complete exit 0); clause 2 (will-test with no exercising test) MISSED (approve 0, compliance agreement with a fabricated passed row); clause 3 (no Reader row) MISSED (approve 0, compliance agreement)

### Section C - the approved plan
1. `scripts/codex-review-run.sh` - delete lane question (1) and its no-table clause; keep the will-test question as the single lane question
2. `tests/test_lanes_contract.py` - assert the deleted wording is absent, keep will-test/exempt/silent assertions, move the trim negative control onto the will-test question
3. `tests/test_review_prompt_parity.py` - new: removed clause's fixtures refused by approve (with accepted pair); kept clauses' fixtures pass the helper and the prompt still carries them
4. `docs/agents/lanes.md` - unanswered lane is approve's job alone; reviewer keeps the will-test question; 2026-11-11 observation kept as history
Scope: 4 files, ~150 lines
Risks: a lane added to .claude/lanes.md after approval is no longer flagged (approve's stamp is the obligation by #1821 design); a hand-written record that skipped approve loses the check (standalone review already exempt); delegated drivers' Step 5 keeps the duplicate (nit store); acceptance item 2 is post-merge only (Refs, issue stays open)

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: prompt text and tests; nothing reads the checkout layout |
| Harness | not applicable: the prompt has the same bytes on either install |
| Driver | will test (`/flow:auto`): the prompt test reads codex-review-run.sh; delegated drivers' Step 5 text is unchanged |
| Coordination | not applicable: no coordination path touched |
| CI provider | not applicable: no CI reading touched |
| Project state | will test: a repository that has adopted a feature's file or record (parity fixtures carry a lane file); one that has not (existing test: no lane file hands over nothing) |
| Toolchain version | not applicable: no toolchain-dependent code |
| Clone shape | not applicable: no history read |
| Run location | not applicable: no cwd-dependent code |
| Gate target | not applicable: no gate runner touched |
| Wave role state | not applicable: no wave state touched |

### Readers of the changed output
| Reader | How |
|---|---|
| Reader: the Codex reviewer (consumes the prompt) | judged by later review yield (#1865) |
| Reader: `tests/test_lanes_contract.py` | updated |
| Reader: `tests/test_changed_output_readers.py` | re-run unchanged |
| Reader: `docs/agents/lanes.md` | updated |
