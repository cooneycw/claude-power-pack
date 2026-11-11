# Flow run record - issue #1672

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a81c9fc07c1a4ded86bd075a4fae3902 -->
## Run 1

- Run-id:            a81c9fc07c1a4ded86bd075a4fae3902
- Run-start:         d79d0042a2daff328eb8c7f5607fdd7fe00d1b60
- Issue:             #1672
- Base SHA:          d79d0042a2daff328eb8c7f5607fdd7fe00d1b60
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner, interactively in the driving session ("approved")
- Recorded at:       2026-11-11T20:45:14Z

### Section B evidence
- commits touching docs/scripts.md since filing: d79d0042, 9ec3e486, b3a81627, abce5ab5, b025989d (all additive)
- merged PRs inspected: #1675, #1676, #1679, #1680, #1681, #1682, #1683 (none restructures the file)
- duplicate/superseding issues: none (#1669 is a sibling)
- open PRs touching the file: none; sibling worktree #1684: no commits touching it; stale t008/cpp-pin entry unexamined
- cause of growth: hand-written history (121 prose sections; 174 commits, +1458/-141 lines in 60 days), not generated inventory

### Section C - the approved plan
1. `docs/scripts.md` - rewritten as the index: preamble, non-script marker, one bullet per script linking its reference
2. `docs/scripts/README.md` - directory note holding the former preamble verbatim (the approved plan's verbatim-move rule applied to the preamble)
3. `docs/scripts/bandit-audit.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
4. `docs/scripts/bash-prep.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
5. `docs/scripts/bootstrap-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
6. `docs/scripts/branch-protection.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
7. `docs/scripts/c4-mermaid.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
8. `docs/scripts/capability-readiness.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
9. `docs/scripts/check-behavioral-eval.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
10. `docs/scripts/check-ci-coverage.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
11. `docs/scripts/check-consolidation-ledger.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
12. `docs/scripts/check-control-ci-deps.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
13. `docs/scripts/check-cpp-host-writes.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
14. `docs/scripts/check-cpp-init-cicd-args.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
15. `docs/scripts/check-cpp-init-promises.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
16. `docs/scripts/check-eval-enrollment.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
17. `docs/scripts/check-ignored-additions.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
18. `docs/scripts/check-memory-supersession.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
19. `docs/scripts/check-negative-controls.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
20. `docs/scripts/check-negative-fixture-preconditions.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
21. `docs/scripts/check-oscillation.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
22. `docs/scripts/check-skill-coverage-map.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
23. `docs/scripts/check-test-binary-guards.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
24. `docs/scripts/checkout-readers.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
25. `docs/scripts/ci-stage-git.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
26. `docs/scripts/ci-stage-jq.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
27. `docs/scripts/ci-stage-make.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
28. `docs/scripts/classify-tool-risk.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
29. `docs/scripts/codex-global-agents.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
30. `docs/scripts/codex-skill-resync.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
31. `docs/scripts/codex-skill-sync.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
32. `docs/scripts/commands-mirror-sync.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
33. `docs/scripts/coordination-admission.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
34. `docs/scripts/counter-model-receipt.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
35. `docs/scripts/counter-model-reviewer-attribution.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
36. `docs/scripts/counter-model-uniformity-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
37. `docs/scripts/cpp-checkout-freshness.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
38. `docs/scripts/cpp-commands-link.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
39. `docs/scripts/cpp-host-write.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
40. `docs/scripts/cpp-install-receipt.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
41. `docs/scripts/cpp-mcp-state.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
42. `docs/scripts/cpp-memory.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
43. `docs/scripts/delegated-core-vendor.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
44. `docs/scripts/delegated-run-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
45. `docs/scripts/deletion-accounting.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
46. `docs/scripts/dependency-audit.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
47. `docs/scripts/drift-detect.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
48. `docs/scripts/eli5-core-drift.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
49. `docs/scripts/eli5-vendor.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
50. `docs/scripts/execution-evidence-verify.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
51. `docs/scripts/flow-ci-status.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
52. `docs/scripts/flow-driver-capability.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
53. `docs/scripts/flow-driver-retirement-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
54. `docs/scripts/flow-finish-gate.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
55. `docs/scripts/flow-helpers-install.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
56. `docs/scripts/flow-live-driver-guard.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
57. `docs/scripts/flow-plan-record.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
58. `docs/scripts/flow-pr-watch.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
59. `docs/scripts/flow-stale-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
60. `docs/scripts/flow-start-resolve.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
61. `docs/scripts/flow-vantage.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
62. `docs/scripts/flow-wave-lexicon.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
63. `docs/scripts/flow-wave-mailbox.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
64. `docs/scripts/flow-wave-plan.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
65. `docs/scripts/flow-wave-registry.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
66. `docs/scripts/flow-wave-residuals.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
67. `docs/scripts/flow-worktree-claim.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
68. `docs/scripts/flow-worktree-guard.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
69. `docs/scripts/flow-worktree-sweep.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
70. `docs/scripts/friction-log.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
71. `docs/scripts/gate-lib.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
72. `docs/scripts/gh-pr-merge.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
73. `docs/scripts/hooks.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
74. `docs/scripts/host-surface-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
75. `docs/scripts/host-surface-observe.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
76. `docs/scripts/install-drift.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
77. `docs/scripts/install-memory-harness.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
78. `docs/scripts/instrument-census-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
79. `docs/scripts/lane-serveability-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
80. `docs/scripts/maintain-loop-indicator.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
81. `docs/scripts/mcp-drift.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
82. `docs/scripts/measurement-shape-scan.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
83. `docs/scripts/memories-db-setup.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
84. `docs/scripts/mutation-probe.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
85. `docs/scripts/nit-store-resolve.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
86. `docs/scripts/npm-global-upgrade.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
87. `docs/scripts/persistent-context-checks.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
88. `docs/scripts/playwright-desk.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
89. `docs/scripts/project-init.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
90. `docs/scripts/project-next-ownership.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
91. `docs/scripts/project-next.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
92. `docs/scripts/prompt-context.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
93. `docs/scripts/pytest-parallel-differential.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
94. `docs/scripts/pytest-workers.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
95. `docs/scripts/qa-regression-demo.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
96. `docs/scripts/qa-regression-export.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
97. `docs/scripts/regenerate-blind-anchor.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
98. `docs/scripts/remote-branch-sweep.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
99. `docs/scripts/retired-surface-prune.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
100. `docs/scripts/run-delivery-pilots.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
101. `docs/scripts/sandbox-phase1-trial.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
102. `docs/scripts/scripts-inventory-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
103. `docs/scripts/secret-scan-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
104. `docs/scripts/secrets-mask.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
105. `docs/scripts/setup-woodpecker-cli.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
106. `docs/scripts/shellcheck-gate.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
107. `docs/scripts/skill-coverage-snapshot.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
108. `docs/scripts/skills-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
109. `docs/scripts/speckit-context.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
110. `docs/scripts/speckit-tasks-to-issues.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
111. `docs/scripts/stash-worktree-guard.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
112. `docs/scripts/step3-record-guard.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
113. `docs/scripts/tool-risk-drift.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
114. `docs/scripts/toolchain-provenance.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
115. `docs/scripts/tools-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
116. `docs/scripts/tools-version-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
117. `docs/scripts/undeclared-import-audit.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
118. `docs/scripts/verify-coverage-check.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
119. `docs/scripts/worktree-remove.md` - sections moved verbatim from docs/scripts.md; relative links rewritten
120. `scripts/scripts-inventory-check.py` - docstring only; no logic change
121. `tests/test_scripts_inventory.py` - index-shape tests: one line per script, no script sections, links resolve
122. `tests/test_lane_serveability_values.py` - read docs/scripts/lane-serveability-check.md
123. `tests/test_flow_wave_residuals.py` - assert history in docs/scripts/flow-wave-residuals.md
124. `tests/test_delivery_lane_versioned.py` - PROSE_SURFACES points at docs/scripts/flow-wave-mailbox.md
125. `tests/test_flow_driver_retirement.py` - history exemption extended to docs/scripts/
126. `tests/test_hook_mask_output.py` - moved hooks reference added to the claim-bearing and must-scan sets
127. `CLAUDE.md` - Project Map line and pointer sentences describe the index plus docs/scripts/
128. `README.md` - tree description

Scope: about 128 files; roughly 1,560 lines moved, about 135 index lines and about 120 lines of test and doc edits new.

Risks: the 128 one-line purposes are new summary prose; other tests may quote the file and need retargeting (reported as divergence); a branch appending to docs/scripts.md before merge (e.g. #1684) conflicts and must move its addition; script comments and frozen anchors citing docs/scripts.md are left. No material concern with the approach. The one-line-per-script rule is enforced by a suite test, not by widening the merge gate.
