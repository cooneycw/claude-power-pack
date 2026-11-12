# Flow run record - issue #1716

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=a92b39b9fc1248899263c18f46599057 -->
## Run 1

- Run-id:            a92b39b9fc1248899263c18f46599057
- Run-start:         68d5fedf152b4446d35bd42f50e0b6c326ce43cb
- Issue:             #1716
- Base SHA:          68d5fedf
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 46: "GATE: GO-WITH-CONDITIONS #1716"
- Recorded at:       2026-11-12T04:20:00Z

### Section B evidence
- commits on cpp/init.md, check-cpp-init-promises.py or check-cpp-host-writes.py since 2026-11-11T23:07:44Z: none; merged or open PRs on them: none; duplicates: none
- all nine rows re-checked against 68d5fedf and still as the issue describes
- seq 623 checked against the Claude Code permissions documentation (code.claude.com/docs/en/permissions, Wildcard patterns): the `:*` suffix equals a trailing ` *`, which requires a space after the prefix; the dd case itself is inferred from that
- seq 701 checked against the AskUserQuestion tool definition: 2 to 4 options per question
- found beside seq 623: `Bash(mkfs:*)` has the same defect (misses mkfs.ext4); the three rm -rf rules match only the bare path

### Rulings and conditions attached to the approval
- mkfs is IN: `Bash(mkfs*)`. The three rm -rf rules stay, stated and pinned by the test.
- seq 725 and seq 635 go to the Nit Store as feature requests; the 725 comment must say it needs the coordination route.
- seq 678 declined (a destination check inside embedded Python is the #1717 shape). seq 674: the boundary is stated, not widened.
1. The deny-rule test's matcher is a stand-in written from two documented sentences: quote both and the URL in the test docstring and the PR, and say the real matcher was not run. That lanes row stays "not covered".
2. Check what the wizard says about the deny list; if it promises a boundary, correct it to what the documentation says a deny rule is.
3. seq 626: CPP's own tree must be clean under the tracked check; if not, report it, no exemption. Outside git the output says the tracked check did not run.
4. seq 702: only if nothing parses the banners; otherwise decline with that reason.
5. init.md stays at 19,467 words: trims recorded before removal, independent old-versus-new read, the FULL suite before the first gate.
6. #1716 carries the table of all rows and where each went before the PR closes it.
7. make lint, make typecheck; two review passes, ask before a third; no push without the slot.

### Section C - the approved plan
1. `.claude/commands/cpp/init.md` - the dd and mkfs deny rules in both profiles; what a deny rule is and is not; the capability question split in two; step 8b skipped after 5d; the three banners only if unread by any checker or test
2. `scripts/check-cpp-init-promises.py` - a promised path must be tracked in a git checkout; the wrapped-declaration finding names the supported shape
3. `tests/test_cpp_init_deny_rules.py` - every deny rule in both profiles against a command it must match and one it must not
4. `tests/test_check_cpp_init_promises.py` - untracked, tracked and outside-git cases; wrapped and unwrapped declaration
5. `docs/scripts/check-cpp-init-promises.md` - the two behaviours
6. `docs/scripts/check-cpp-host-writes.md` - the declined limit, one sentence
7. `docs/commands-reference.md` - trimmed text, recorded in a commit before removal
8. `CHANGELOG.md` - entry
Scope: 8 files, about 250 lines.
Risks: the deny-rule test cannot run Claude Code's own matcher, so a wrong reading of the documentation passes it; a deny rule is not a boundary either way; the tracked check turns the promise gate red for an untracked promised file.

### Lanes for this change
| Lane | Answer |
|---|---|
| Checkout | will test: the promise checker in a git checkout and outside one |
| Harness | not covered: no live Codex install is run; the generated cpp-init skill is rebuilt by the existing mirror tests |
| Driver | not applicable |
| Coordination | not applicable |
| CI provider | not applicable |
| Project state | will test: a promised file tracked, and the same file present but untracked |
| Reader: Claude Code's permission matcher, which reads the deny rules | not covered: no test can run it; a matcher written from the documentation stands in |
| Reader: scripts/check-cpp-init-promises.py and the tests that parse init.md | will test: they run against the real edited document |
