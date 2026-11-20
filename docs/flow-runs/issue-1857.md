# Flow run record - issue #1857

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=606280da40cc44b393f5b03321739dfb -->
## Run 1

- Run-id:            606280da40cc44b393f5b03321739dfb
- Run-start:         de3fb38e759480439355be6aa83dc3f56a07a214
- Issue:             #1857
- Base SHA:          de3fb38e759480439355be6aa83dc3f56a07a214
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner (cooneycw), in this session ("approved")
- Recorded at:       2026-11-20T12:10:53Z

### Section B evidence
commits: 61d9c045 (#1858). PRs: #1856, #1858, #1859 (closes prerequisite #1851), #1861. dup/super: none (#864, #398 unrelated). Siblings: #1821 worktree (issue closed, no overlap); #1862 worktree clean at main (collision risk only). Consumers: kyle none; skillc grader reads step\s+3(?:/\d+)? (any total).

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: text-only renumber |
| Harness | will test Claude install / Codex install: make codex-skills regenerates the mirror and test_codex_skill_sync reads it |
| Driver | will test /flow:auto / delegated drivers: test_driver_parity and test_delegated_driver_gates |
| Coordination | not applicable: nothing here talks to Kyle |
| CI provider | not applicable: no CI-provider behaviour changes |
| Project state | not applicable |
| Toolchain version | not applicable |
| Clone shape | not applicable |
| Run location | not applicable |
| Gate target | not applicable |
| Wave role state | not applicable |

### Section C - the approved plan
Mapping: Steps 1-4 unchanged; Step 5 deleted; 6->5, 6b->5b, 7->6 (7a/7b->6a/6b); 8+9 -> Step 7 "After merge" (7a Verify CI, 7b Deploy). Delegated drivers keep their own N/8 numbering. Approved history extension: CHANGELOG.md, existing changelog.d fragments, docs/research/**, .specify/specs/**, controls/driver-parity/base-tree/** and run-case.py, controls/check-eval-enrollment/cases/**, tests/fixtures/retro/flow-auto-pre-eli5.md stay as written.

1. `.claude/commands/flow/auto.md` - renumber /flow:auto step citations to the seven-step layout
2. `docs/reference/flow-auto-rationale.md` - renumber /flow:auto step citations to the seven-step layout
3. `.claude/commands/codex/auto.md` - renumber /flow:auto step citations to the seven-step layout
4. `.claude/commands/gemma/auto.md` - renumber /flow:auto step citations to the seven-step layout
5. `.claude/commands/qwen/auto.md` - renumber /flow:auto step citations to the seven-step layout
6. `templates/delegated-driver-core.md` - renumber /flow:auto step citations to the seven-step layout
7. `.claude/commands/codex/code_review.md` - renumber /flow:auto step citations to the seven-step layout
8. `.claude/commands/codex/help.md` - renumber /flow:auto step citations to the seven-step layout
9. `.claude/commands/cicd/verify.md` - renumber /flow:auto step citations to the seven-step layout
10. `.claude/commands/flow/merge.md` - renumber /flow:auto step citations to the seven-step layout
11. `.claude/commands/flow/finish.md` - renumber /flow:auto step citations to the seven-step layout
12. `.claude/commands/flow/register.md` - renumber /flow:auto step citations to the seven-step layout
13. `.claude/commands/flow/wave.md` - renumber /flow:auto step citations to the seven-step layout
14. `docs/agents/driver-parity.json` - renumber /flow:auto step citations to the seven-step layout
15. `.claude/verify-coverage.json` - renumber /flow:auto step citations to the seven-step layout
16. `controls/census.md` - renumber /flow:auto step citations to the seven-step layout
17. `.claude/command-word-budgets.tsv` - renumber /flow:auto step citations to the seven-step layout
18. `docs/agents/flow-plan-record.md` - renumber /flow:auto step citations to the seven-step layout
19. `docs/agents/evidence-deleting-idioms.md` - renumber /flow:auto step citations to the seven-step layout
20. `docs/agents/glossary.md` - renumber /flow:auto step citations to the seven-step layout
21. `docs/agents/lanes.md` - renumber /flow:auto step citations to the seven-step layout
22. `docs/commands-reference.md` - renumber /flow:auto step citations to the seven-step layout
23. `docs/scripts/codex-review-run.md` - renumber /flow:auto step citations to the seven-step layout
24. `docs/scripts/flow-ci-status.md` - renumber /flow:auto step citations to the seven-step layout
25. `docs/scripts/flow-worktree-guard.md` - renumber /flow:auto step citations to the seven-step layout
26. `docs/scripts/gh-pr-merge.md` - renumber /flow:auto step citations to the seven-step layout
27. `docs/scripts/worktree-remove.md` - renumber /flow:auto step citations to the seven-step layout
28. `docs/scripts/flow-plan-record.md` - renumber /flow:auto step citations to the seven-step layout
29. `docs/scripts/flow-finish-gate.md` - renumber /flow:auto step citations to the seven-step layout
30. `docs/scripts/codex-skill-resync.md` - renumber /flow:auto step citations to the seven-step layout
31. `docs/scripts/counter-model-receipt.md` - renumber /flow:auto step citations to the seven-step layout
32. `Makefile` - renumber /flow:auto step citations to the seven-step layout
33. `README.md` - renumber /flow:auto step citations to the seven-step layout
34. `scripts/gh-pr-merge.sh` - renumber /flow:auto step citations to the seven-step layout
35. `scripts/flow-finish-gate.sh` - renumber /flow:auto step citations to the seven-step layout
36. `scripts/flow-stale-check.sh` - renumber /flow:auto step citations to the seven-step layout
37. `scripts/flow-live-driver-guard.sh` - renumber /flow:auto step citations to the seven-step layout
38. `scripts/counter-model-receipt.py` - renumber /flow:auto step citations to the seven-step layout
39. `scripts/flow-plan-record.py` - renumber /flow:auto step citations to the seven-step layout
40. `scripts/flow-ci-status.sh` - renumber /flow:auto step citations to the seven-step layout
41. `scripts/flow-start-resolve.sh` - renumber /flow:auto step citations to the seven-step layout
42. `scripts/codex-review-run.sh` - renumber /flow:auto step citations to the seven-step layout
43. `scripts/codex-skill-resync.sh` - renumber /flow:auto step citations to the seven-step layout
44. `scripts/flow-helpers-install.sh` - renumber /flow:auto step citations to the seven-step layout
45. `scripts/flow-worktree-sweep.sh` - renumber /flow:auto step citations to the seven-step layout
46. `scripts/friction-log.sh` - renumber /flow:auto step citations to the seven-step layout
47. `scripts/worktree-remove.sh` - renumber /flow:auto step citations to the seven-step layout
48. `templates/claude-settings-permissions.md` - renumber /flow:auto step citations to the seven-step layout
49. `tests/test_counter_model_review.py` - renumber /flow:auto step citations to the seven-step layout
50. `tests/test_eli5_gate_not_bypassable.py` - renumber /flow:auto step citations to the seven-step layout
51. `tests/test_delegated_driver_gates.py` - renumber /flow:auto step citations to the seven-step layout
52. `tests/test_driver_parity.py` - renumber /flow:auto step citations to the seven-step layout
53. `tests/test_gh_pr_merge.py` - renumber /flow:auto step citations to the seven-step layout
54. `tests/test_nit_store_routing.py` - renumber /flow:auto step citations to the seven-step layout
55. `tests/test_worktree_remove_occupied.py` - renumber /flow:auto step citations to the seven-step layout
56. `tests/test_flow_worktree_native.py` - renumber /flow:auto step citations to the seven-step layout
57. `tests/test_flow_stale_check.py` - renumber /flow:auto step citations to the seven-step layout
58. `tests/test_flow_worktree_guard_verdicts.py` - renumber /flow:auto step citations to the seven-step layout
59. `tests/test_flow_auto_plan_gate.py` - renumber /flow:auto step citations to the seven-step layout
60. `tests/test_cicd_makefile.py` - renumber /flow:auto step citations to the seven-step layout
61. `tests/test_cicd_verify_invocation.py` - renumber /flow:auto step citations to the seven-step layout
62. `tests/test_codex_review_run.py` - renumber /flow:auto step citations to the seven-step layout
63. `tests/test_codex_skill_resync.py` - renumber /flow:auto step citations to the seven-step layout
64. `tests/test_codex_skill_sync.py` - renumber /flow:auto step citations to the seven-step layout
65. `tests/test_flow_ci_status.py` - renumber /flow:auto step citations to the seven-step layout
66. `tests/test_flow_deploy_target.py` - renumber /flow:auto step citations to the seven-step layout
67. `tests/test_flow_docs_no_shared_stash.py` - renumber /flow:auto step citations to the seven-step layout
68. `tests/test_flow_gate_pushed_head.py` - renumber /flow:auto step citations to the seven-step layout
69. `tests/test_flow_issue_snapshot.py` - renumber /flow:auto step citations to the seven-step layout
70. `tests/test_flow_plan_compliance.py` - renumber /flow:auto step citations to the seven-step layout
71. `tests/test_flow_plan_record.py` - renumber /flow:auto step citations to the seven-step layout
72. `tests/test_flow_start_resolve.py` - renumber /flow:auto step citations to the seven-step layout
73. `tests/test_check_claude_md_behavior.py` - renumber /flow:auto step citations to the seven-step layout
74. `tests/fixtures/flow-command-steps.fixture` - renumber /flow:auto step citations to the seven-step layout
75. `changelog.d/1857.md` - renumber /flow:auto step citations to the seven-step layout

Item 1 also restructures: delete the Step 5 section, fold Steps 8 and 9 into Step 7 (7a/7b) with one combined report line. Item 17 only if the budget check needs a tighter cap. Item 47 only where L71/74 cite /flow:auto. Item 72 (fixture): retire bash-0051/bash-0122 with reason "#1857 renumber" and add renumbered replacements. Item 73: new changelog fragment. Item 48 (test_counter_model_review): test_the_step_numbering_is_UNCHANGED becomes a seven-step pin (1/7..7/7, no /9, no retired line).

Scope: ~75 files, ~250 lines, mostly mechanical.
Risks: missed citation (mitigated by acceptance grep proven on main first); wrong renumber of another command's own step (per-line edits, no global sed); #1862 may conflict in flow/auto.md Step 6; driver-parity citation text must match byte-for-byte; report total /9->/7 (skillc grader tolerant; docstring nit to skillc Nit Store).
