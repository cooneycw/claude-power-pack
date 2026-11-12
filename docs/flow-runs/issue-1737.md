# Flow run record - issue #1737

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=47aedb08ed874b21875dfc45c5683295 -->
## Run 1

- Run-id:            47aedb08ed874b21875dfc45c5683295
- Run-start:         d152fae166613cdb035be40b904518a363929ed4
- Issue:             #1737
- Base SHA:          d152fae166613cdb035be40b904518a363929ed4
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 40: "GATE: GO-WITH-CONDITIONS #1737"
- Recorded at:       2026-11-12T04:05:00Z

### Section B evidence
- commits on lib/security or its tests since 2026-11-12T02:18:26Z: d152fae1 only (#1717: documentation and tests, scanner module unchanged)
- merged or open PRs delivering this: none; duplicate/superseding issues: none
- the issue's constraint about the #1717 shell-substitution exemption is moot: that exemption was withdrawn
- measured read-only before the plan, counts by id only: CPP 2466 scanned today, 99 would join, 0 new findings; kyle 1924, 42, 3 HARDCODED_PASSWORD all in Makefile and all variable references; skillc 4439, 125, 0. kyle-candidate not measured
- coordination issues filed by the orchestrator before any edit: kyle #2365, skillc #708, kyle-candidate #11
- reader check for the new summary line (condition 4), done before any edit: ScanResult.skipped feeds skipped-checks= on the SECURITY_GATE line, so the line does not go there; it goes in a new additive field

### Conditions attached to the approval
1. The existing extension population is selected exactly as before; prove for CPP, kyle and skillc that today's scanned set is a subset of the new one and findings on it are identical (ids and counts, no values).
2. The name list is one constant matched on the exact basename plus the Dockerfile.<x> form; Makefile.bak and my-Dockerfile are not on it; test both.
3. The shebang read is bounded and safe: read-only, at most 8 KB for the NUL check, no symlink followed out of the root, never block on a FIFO or device; test a FIFO.
4. Reader check first for the "not opened" line; the "No secrets found in N source files" line keeps its shape.
5. Cases in the control that drives this module, or say what guards it.
6. No finding's value in any output, message or PR text; synthetic values only.
7. Say in the PR that the #1717 test pinning "extensionless is not scanned" is replaced deliberately, and by what.
8. Exact lane names; make lint, make typecheck; two review passes, ask before a third.

### Section C - the approved plan
1. `lib/security/modules/secrets.py` - also read extensionless files that start with a shebang and the well-known build-file names; for that new population only skip binary, over-1-MB, symlinked and non-regular files; report how many extensionless files were not read, by reason
2. `lib/security/models.py` - a new additive list field for the not-read line, carried through merge
3. `lib/security/output/novice.py` - print the not-read line as its own line
4. `lib/security/output/json_output.py` - emit the new field as a new key
5. `tests/test_security_scanners.py` - replace the #1717 test that pinned extensionless as unscanned with its opposite; bad and good cases; the name list; a FIFO; the unchanged existing population; the unchanged summary and gate lines
6. `controls/lib-security-gate/control.json` - a bad and a good case for the new population
7. `controls/lib-security-gate/cases/bad-extensionless-script/deploy` - an extensionless script with a shebang and the control's synthetic key
8. `controls/lib-security-gate/cases/good-extensionless-unread/notes` - an extensionless file with no shebang carrying the same synthetic key, which must not be read
9. `lib/security/README.md` - what is read, what is not, and the stated answers on shebang and execute bit
10. `CHANGELOG.md` - entry saying finding counts can go up
Scope: 10 files, about 300 lines, mostly tests.
Risks: finding counts rise in consumers on re-pin (kyle +3, coordinated); a new JSON key is a new surface; reading the head of every extensionless file costs time on large trees.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | not applicable: no path-dependent behaviour beyond the scan root |
| Harness | not covered: no test runs the bundled copy of lib/security in a generated Codex skill |
| Driver | not applicable |
| Coordination | not covered: kyle and skillc are measured read-only; no Kyle gate is run |
| CI provider | not applicable |
| Project state | will test, with new tests in this diff: a project with a .claude/security.yml path suppression for an extensionless file and one without |
| Reader: kyle, skillc and kyle-candidate security gates, which read finding counts | not covered by a test: measured read-only on kyle and skillc; kyle-candidate not measured |
| Reader: lib/cicd coverage logic, which reads secrets-scanned= from the gate line | will test: the gate line is produced by the real cli over a tree with extensionless files and its shape is asserted |
