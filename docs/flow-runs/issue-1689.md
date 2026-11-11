# Flow run record - issue #1689

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=e962e19e987242568c6b89462a36bb30 -->
## Run 1

- Run-id:            e962e19e987242568c6b89462a36bb30
- Run-start:         15521b1e19359cd7d72c8f24e5628b397fa676f5
- Issue:             #1689
- Base SHA:          15521b1e19359cd7d72c8f24e5628b397fa676f5
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner, interactively in the driving session ("approved"), including the three recommended decisions
- Recorded at:       2026-11-11T22:01:42Z

### Section B evidence
- commits on main since filing: none
- merged PRs since filing: none; open PRs: none
- duplicate/superseding issues: none (#1288, #1405 closed, about secret scanning); source is Nit Store comment 6807165982
- measured at 15521b1e: 52 lines in 29 files carry an account-in-path form; no email address in any tracked file

### Owner decisions recorded at the gate
- Existing receipts and as-read snapshots MAY be edited, for these path strings only (departs from #1048 and the byte-for-byte snapshot rule for this purpose).
- Git history is NOT rewritten by this change.
- The bare GitHub handle outside paths is left alone.

### Section C - the approved plan
1. `controls/behavioral-eval/cases/bad-bundle-evidence-unverified/bundle-1/cpp-usage/cbf9931314ed45d2927fa5e150daa9d2.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
2. `controls/behavioral-eval/cases/good-bundle-skill-evidence-matched/bundle-1/cpp-usage/cbf9931314ed45d2927fa5e150daa9d2.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
3. `docs/agents/delivery-pilots.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
4. `docs/decisions/0002-sandbox-prompt-elimination-threat-model.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
5. `docs/flow-runs/issue-1192.as-read.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
6. `docs/flow-runs/issue-1232.as-read.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
7. `docs/flow-runs/issue-1235.as-read.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
8. `docs/flow-runs/issue-1253.as-read.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
9. `docs/flow-runs/issue-1542.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
10. `docs/flow-runs/issue-1551.as-read.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
11. `docs/measurements/counter-model/2026-10-30T125252Z-issue-1612.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
12. `docs/measurements/counter-model/2026-10-31T235048Z-issue-1615.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
13. `docs/measurements/counter-model/2026-11-04T171653Z-issue-1618.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
14. `docs/measurements/counter-model/2026-11-04T184548Z-issue-1622.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
15. `docs/measurements/counter-model/2026-11-07T112324Z-issue-1626.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
16. `docs/measurements/counter-model/2026-11-11T151056Z-issue-1668.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
17. `docs/measurements/counter-model/2026-11-11T152713Z-issue-1674.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
18. `docs/measurements/counter-model/2026-11-11T185029Z-issue-1670.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
19. `docs/measurements/counter-model/2026-11-11T190229Z-issue-1678.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
20. `docs/measurements/counter-model/2026-11-11T190919Z-issue-1677.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
21. `docs/measurements/counter-model/2026-11-11T192246Z-issue-1669.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
22. `docs/measurements/counter-model/2026-11-11T200002Z-issue-1671.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
23. `docs/measurements/counter-model/2026-11-11T204750Z-issue-1685.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
24. `docs/measurements/counter-model/2026-11-11T205110Z-issue-1684.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
25. `docs/measurements/counter-model/2026-11-11T205206Z-issue-1672.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
26. `docs/measurements/execution-evidence/cbf9931314ed45d2927fa5e150daa9d2.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
27. `docs/measurements/skill-coverage/flow-check.json` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
28. `docs/research/codex-clean-install-proof-2026-09-21.md` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
29. `docs/research/codex-clean-install-proof-2026-09-21/clean-host.sh` - account-in-path strings replaced with the neutral placeholder; any binding digest recomputed
30. `scripts/counter-model-receipt.py` - record the transcript directory with the home part as a fixed token; expand it on read-back
31. `lib/cicd/evidence.py` - execution-evidence records store home-relative paths; expand on read
32. `scripts/check-host-account-paths.py` - new tripwire: a tracked file with /home/<name> or -home-<name>- outside the placeholder list fails
33. `controls/host-account-paths/control.json` - the committed negative control (bad and good cases beside it)
34. `Makefile` - host-account-paths-check target, in make verify
35. `.woodpecker.yml` - the same step in CI
36. `controls/census.md` - census row for the new checker
37. `.claude/verify-coverage.json` - coverage registration if the checker needs one
38. `docs/scripts.md` - one index line
39. `docs/scripts/check-host-account-paths.md` - the checker's reference
40. `tests/test_host_account_paths.py` - new tests, including the red cases
41. `tests/test_counter_model_adapters.py` - the recorded transcript form
42. `tests/test_counter_model_review.py` - the recorded transcript form
43. `tests/test_execution_evidence.py` - the recorded path form

Scope: about 43 files; roughly 60 replaced lines, about 250 new lines of checker, control and tests.

Risks: items bound by content digests (execution-evidence copies, the skill-coverage record) - if a digest cannot be recomputed honestly, stop and report; the receipt read-back path must still locate transcripts for old and new receipts; the placeholder list narrows the check on purpose and fails loudly on a new name.
