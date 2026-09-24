# Flow run record - issue #972

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
below. It is not a description of the shipped system, it is not a second
statement of the issue contract or of a Tier 3 spec, and it does not graduate.

- Issue:             #972
- Base SHA:          47db657a09caba31453368df09b3696194265f74
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          repository owner (cooneycw), interactive "approved"
- Recorded at:       2026-09-24T11:00:36Z

## Section B evidence
- Current count: 252 findings / 142 files at severity=style; 113 are codex/skills
  mirrors, leaving 139 findings (28 warning, 111 note) in 25 source files.
- 65 of 68 SC2317 are the dead function check_systemd_unit in
  scripts/drift-detect.sh, callerless since adeb031 (#505).
- Commits touching the gate since filing: f328ed2 (#1127), a144b54 (#1129),
  aebb33c (#970), 143f83a (#1146) - none changed severity or the backlog.
- Merged PRs: #1149, #1135, #1128, #1158 - none address the backlog.
- Duplicate/superseding issues: none (#960, #987 closed, different scope).
- Standing constraint: 2026-09-20 consolidation comment - findings must be
  reviewed, not waived (cxpp#249 already-covered row).

## Section C - the approved plan
1. `scripts/drift-detect.sh` - delete dead check_systemd_unit; drop unused MCP_PORTS/mode if confirmed; quote SC2295 expansions.
2. `scripts/checkout-readers.sh` - SC2317 on case-local helper: suppress with reason or hoist.
3. `scripts/flow-wave-registry.sh` - _rc trap false positive, SC2015 review, SC2178/2128, SC2016, unused vars, SC2004.
4. `scripts/flow-wave-mailbox.sh` - _rc trap, SC2015 review, SC2086, SC2001/2018/2019.
5. `scripts/gh-pr-merge.sh` - SC2178 false positives, SC2086 quoting.
6. `scripts/gate-lib.sh` - GATE_VALUE output var suppress; SC3045 trap -p review.
7. `scripts/flow-finish-gate.sh` - SC2181, SC2016.
8. `scripts/codex-skill-resync.sh` - SC2181.
9. `scripts/cpp-host-write.sh` - SC2088 quoted tilde investigate; SC1007.
10. `scripts/secret-scan-check.sh` - SC1091 gate-lib source; SC1007.
11. `scripts/shellcheck-gate.sh` - SC1091; default severity error -> style.
12. `scripts/npm-global-upgrade.sh` - SC1091.
13. `scripts/flow-driver-retirement-check.sh` - SC1091.
14. `scripts/install-drift.sh` - SC2295, SC2015 review.
15. `scripts/toolchain-provenance.sh` - SC2154 eval-assigned var.
16. `scripts/lane-serveability-check.sh` - _rc trap false positive.
17. `scripts/speckit-tasks-to-issues.sh` - SC2015 review, SC2020, SC2016.
18. `scripts/sandbox-phase1-trial.sh` - SC2016, unused OUTR1V.
19. `scripts/worktree-remove.sh` - SC2002 useless cat.
20. `scripts/flow-worktree-claim.sh` - unused locked_line.
21. `scripts/hook-mask-output.sh` - unused SCRIPT_DIR.
22. `woodpecker/bootstrap-agent-host.sh` - SC2015 review.
23. `tests/fixtures/delivery_pilots/completion/guard-check.sh` - SC2034 vars consumed by sourced helper.
24. `docs/research/codex-clean-install-proof-2026-09-21/run-arms.sh` - SC2012/SC2016 suppress in frozen artifact.
25. `docs/research/codex-clean-install-proof-2026-09-21/tmpfs-measurement-control.sh` - SC2016 suppress in frozen artifact.
26. `Makefile` - docker-fallback default SHELLCHECK_SEVERITY error -> style.
27. `controls/shellcheck-gate/control.json` - register bad-note-severity case.
28. `controls/shellcheck-gate/cases/bad-note-severity/lib.sh` - note-only finding; anchor (defaults error) is blind to it.
29. `.woodpecker.yml` - stale severity=error comment.
30. `docs/decisions/0008-instrument-negative-control-bound.md` - residual closed, gate at style, reversal trigger (drop to warning, never error).

Scope: ~30 source files plus regenerated codex/skills mirrors; ~-80/+60 lines.
Risks: behaviour change in heavily-used flow scripts (only provably-equivalent
rewrites, otherwise annotate); stricter CI for every future PR; shellcheck
version drift of style findings (CI pins 0.10.0); SC2015 rewrites may alter
control flow if B can fail - suppress rather than guess.
