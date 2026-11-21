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

<!-- flow-run n=2 id=4eb1c41cf0814c83a87e792d9e9d04c4 -->
## Run 2

- Run-id:            4eb1c41cf0814c83a87e792d9e9d04c4
- Run-start:         8c445b7b385656eb28b2b192808328e827176047
### Section A - What this issue wants
The delegated reviewers still ask whether every project lane has an answer, even though plan approval already refuses a missing answer. Remove that duplicate question without removing the reviewer judgement that the helper cannot make. Also read the small post-change review sample honestly; missing finding kinds are not zero findings.

### Section B - Still needed
Verdict: Still needed. Main at read time: 8c445b7b385656eb28b2b192808328e827176047.
Read the full issue and all comments, owner ruling 7065029193, and Nit Store finding 7040701785. The Step 5 shared core still carries the duplicated question. Owner-approved residual scope is not a reason to close the whole issue: the rate reading is inconclusive at n=7. Approval is orchestrator mailbox 36584 in reply to plan 36583, 2026-11-21. This PR uses Refs #1863, not Closes.

### Section C - Approved changes
1. templates/delegated-driver-core.md - remove only the unanswered-lane/no-table review question; retain will-test, Reader and stand-in judgement.
2. .claude/commands/codex/auto.md - regenerate from shared core, never hand-edit rendered regions; 8689 -> 8674 words.
3. .claude/commands/qwen/auto.md - regenerate from shared core; 9903 -> 9888 words.
4. .claude/commands/gemma/auto.md - regenerate from shared core; 10512 -> 10497 words.
5. tests/test_delegated_plan_lanes.py - deliberately change dropped-question assertions, preserving actual helper refusal and retained judgement coverage.
6. tests/test_review_prompt_parity.py - shared/rendered prompt parity tied to the real helper refusal/miss cases.
7. docs/flow-runs/issue-1863.md - append this approved run, preserving historical run 1.
8. docs/flow-runs/issue-1863.as-read.md - helper-managed issue snapshot for this run.
9. docs/flow-runs/issue-1863.lanes-demonstrated.md - append this run's evidence and measurement limits.
10. docs/measurements/counter-model/ - runtime-derived different-model review receipt.
Scope: shared template, three generated drivers, two existing test modules and run evidence; no new runtime instrument. Risks: deleting unsupported judgement or hand-editing generated text; both are pinned by parity tests and the vendor check. No material concern beyond those bounds.

Before deletion, run the current helper against omitted-lane/no-table and complete-plan fixtures and all delegated approval controls. Retained question fixtures must still demonstrate helper misses on fabricated test evidence and omitted Reader rows. Run the new dropped-wording regression red on current main, then vendor and run green.

The item-2 reading is an issue comment and PR-body observation only: two post-5204ea06 committed CPP receipts, five passes, seven accepted findings, no stored kinds. Use the merged report for denominators/dispositions, manual classification with sources stated, explicit not classifiable, and inconclusive at n=7. PR1869 body supplies its three finding descriptions. Use kind parsing only for actual Kind-bearing reports if PR1870 lands before posting; no backfill or inferred zero. Next reading waits for kinds and more reviews, naturally through monthly review. The issue stays open.

Reader search positively found the current each-listed-lane assertion in test_delegated_plan_lanes and the shared/rendered Step 5 blocks. Delegated families are explicitly unpackaged on the Codex skill surface.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test - main checkout / linked worktree in existing parity and source-bound approval controls |
| Harness | not covered - live Claude install model compliance is not executed; delegated families have no Codex install skills, while actual source/rendered input bytes are tested under Driver |
| Driver | will test - delegated drivers (/codex:auto, /qwen:auto, /gemma:auto), with unchanged /flow:auto as reference |
| Coordination | not applicable - no without Kyle / with Kyle coordination behavior changes |
| CI provider | not applicable - no provider parsing changes |
| Project state | will test - a repository that has adopted a feature's file or record / one that has not, using lane-file and no-lane-file controls |
| Toolchain version | not applicable - no interpreter-dependent implementation changes |
| Clone shape | not applicable - no runtime history reader changes |
| Run location | not applicable - no cwd-dependent implementation changes |
| Gate target | not applicable - no gate runner or target interpreter changes |
| Wave role state | not applicable - no wave state changes |
| Reader: Claude reviewer in each delegated driver | not covered - semantic model compliance; deterministic tests read the actual shared/rendered prompt bytes, and an independent reviewer checks the change |
| Reader: prompt/parity test consumers | tested against real output - actual generated sections and real helper refusal/approval output, not copied prompt text |

Approval: granted by orchestrator mailbox 36584, including Refs-only item-2 ruling. Normal account HOME for full gates, private TMPDIR outside HOME, no inherited PYTEST_ADDOPTS, reset background SIGINT, warm private cache, checksum-verified gitleaks on private PATH. Before push run budget check, both import-audit paths, full finish gate and head-history gitleaks. No automatic docs-generation/C4 step. Counter-model review and exact-head CI retained; orchestrator merges.
