# Flow run record - issue #1717

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=e8d8600f550e4250938850c9df3a7203 -->
## Run 1

- Run-id:            e8d8600f550e4250938850c9df3a7203
- Run-start:         6b6cc29e39464cadefc5fea53fafd15a4ce95fb4
- Issue:             #1717
- Base SHA:          6b6cc29e39464cadefc5fea53fafd15a4ce95fb4
- Necessity verdict: Needs reframing
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 28: "GATE: GO-WITH-CONDITIONS #1717" (Option A)
- Recorded at:       2026-11-12T02:14:54Z

### Section B evidence
- commits since 2026-11-11T23:07:45Z: none touching lib/security
- merged or open PRs on lib/security: none
- duplicate/superseding issues: none
- this host: no sibling worktree holds unpushed commits on lib/security or its tests
- measured read-only with the scanner's own scan(), no value printed: Kyle 61 assignment-pattern findings before its suppressions (49 literals in a test path, 11 shell substitutions in a shell file, 1 literal elsewhere); skillc 1 (a literal outside tests)
- reframing: the shell shape is the scanner's to fix; fixtures and sentinels are literals, handled by a declared suppression that already exists; the issue's acceptance was amended accordingly

### Conditions attached to the approval
- ${...} is exempt ONLY as a bare ${NAME}; a default or alternative (:-, -, :=, =, :+, +) carries a literal and must still flag, with a still-flag case per operator form handled, at least :- and :=.
- $( at the start is accepted with its limit named in the README and in a test: password="$(echo some-literal-here)" is a known miss.
- The still-flag list stands in full, plus: a second, literal assignment on the same line after an exempt one still reports.
- Every stop-flagging case is shown flagged on 6b6cc29e; every still-flag case is shown flagged before and after.
- A shell script with no extension: say what happens and pin it.
- If a control's gate runs this module the pair goes in as cases; otherwise say what guards this module.
- No finding's value in any test output, message or PR text; synthetic values only.
- The README states the risk of suppressing a test tree in one sentence.
- make lint, make typecheck; two review passes, ask before a third; name the exemption rules in the review context; no push without the slot.

### Section C - the approved plan
1. `lib/security/modules/secrets.py` - a HARDCODED_PASSWORD match is dropped when the file is a shell file (.sh, .bash, .zsh), the value is in double quotes, and the value begins $( , is a bare ${NAME}, or is exactly $NAME. Ids, severity and lines unchanged for everything still reported
2. `tests/test_security_scanners.py` - the committed stop-flagging and still-flag cases, each as a test
3. `controls/secret-assignment-shell/control.json` - registers the pair as cases on this module, since controls/secret-scan guards a different script (gitleaks) and controls/lib-security-gate runs the flow_finish policy, which does not block HIGH
4. `controls/secret-assignment-shell/cases/bad-fallback-literal/deploy.sh` - a hardcoded fallback inside ${NAME:-...}: must still flag
5. `controls/secret-assignment-shell/cases/good-substitutions/deploy.sh` - the four exempt shapes: must not flag
6. `controls/secret-assignment-shell/anchors/constructed-any-brace/lib/security/__init__.py` - package marker for the blind anchor
7. `controls/secret-assignment-shell/anchors/constructed-any-brace/lib/security/modules/__init__.py` - package marker for the blind anchor
8. `controls/secret-assignment-shell/anchors/constructed-any-brace/lib/security/modules/secrets.py` - the plausible wider rule (any value beginning ${ is exempt), which misses the fallback literal
9. `controls/census.md` - census row for the registered instrument
10. `lib/security/README.md` - the stale "carries no value" sentence corrected; shell substitutions and their named limit; suppressing a test tree by id and path, with its risk
11. `CHANGELOG.md` - entry
Scope: 11 files, about 250 lines.
Risks: this is a detector, and an exemption can stop a true finding; the exemption is drawn to the reported shapes, each still-flag case is shown flagged before and after, and the known miss (a literal inside $(...)) is named.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout (main checkout / linked worktree) | not applicable: the scanner walks a directory it is given |
| Harness (Claude install / Codex install) | not covered: no test runs the bundled copy of lib/security |
| Driver | not applicable |
| Coordination (without Kyle / with Kyle) | not covered by a test: Kyle was measured read-only, no Kyle gate was run |
| CI provider | not applicable |
| Project state (adopted a file / not) | will test, with new tests in this diff: a project with a .claude/security.yml path suppression and one without |
