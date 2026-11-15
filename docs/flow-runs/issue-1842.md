# Flow run record - issue #1842

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=340655a894e34a9e8efa02ff06c23a38 -->
## Run 1

- Run-id:            340655a894e34a9e8efa02ff06c23a38
- Run-start:         19e24318f456e55ef3aa524ba6f85739c58c8f85
- Issue:             #1842
- Base SHA:          19e24318f456e55ef3aa524ba6f85739c58c8f85
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), interactive Step 3 gate; sequencing "wait for #1843"
- Recorded at:       2026-11-15T18:35:00Z

### Section B evidence
- commits: none on origin/main touching the gate paths after the issue was filed, other than #1843's squash 19e24318 (the dependency).
- PRs: #1843 (Closes #1839, merged 2026-11-15T18:29Z, introduces lex()); #1841, #1840 inspected (unrelated / pre-issue).
- dup/super: none (#1839 is the parent).
- host: sibling worktree for #1839 had no unpushed commits on the gate paths.
- repro: the issue's input exits 0 on #1843 heads cdfed69c and 6d12ad66.

### Section C - the approved plan
1. `scripts/check-doc-helper-flags.py` - lex(): an unescaped backtick opens a nested-command level (in double quotes, at command level, inside $(...)), closed by the next unescaped backtick; a helper path inside it is an invocation.
2. `controls/doc-helper-flags/cases/bad-backtick-in-double-quote/templates/core.md` - the issue's input as a BAD case.
3. `controls/doc-helper-flags/cases/bad-backtick-in-double-quote/scripts/mailbox.sh` - fixture helper.
4. `controls/doc-helper-flags/control.json` - register the new cases.
5. `tests/test_check_doc_helper_flags.py` - tests for the three positions plus escaped backtick; red on the pre-fix gate first.
6. `changelog.d/1842.md` - changelog fragment.
7. `docs/scripts/check-doc-helper-flags.md` - note the backtick nesting if the doc describes the reader.
8. `controls/doc-helper-flags/cases/good-inline-spans-near-backticks/templates/core.md` - GOOD case: prose inline spans beside helper paths stay unflagged (revision within outcome, after #1830 review).
9. `controls/doc-helper-flags/cases/good-inline-spans-near-backticks/scripts/mailbox.sh` - fixture helper.

Scope: ~9 files, ~120 lines. Risk: markdown inline spans also use backticks; a backtick nesting level could start reading prose as commands (false failure in a gate that lets work through). Checked by the GOOD case and a before/after diff of live per-invocation flag lists.

### Lanes for this change

| Lane | Answer | Note |
|---|---|---|
| Checkout | not applicable | root from __file__ / --root; layout irrelevant |
| Harness | not applicable | scans sources; Codex mirrors are generated from them |
| Driver | will test | both values, /flow:auto and delegated drivers: the live-tree before/after diff covers flow/auto.md and templates/delegated-driver-core.md |
| Coordination | not applicable | offline text scan |
| CI provider | will test | Woodpecker (.woodpecker.yml:234); no Actions lane |
| Project state | not applicable | CPP-only gate |
| Toolchain version | not covered | stdlib, no new syntax; no matrix (#1788) |
| Clone shape | not applicable | git-free |
| Run location | will test | both values: invoked from the cpp root (make verify) and from another directory (one run by absolute path from the scratchpad) |
| Gate target | not applicable | CPP only |
| Wave role state | not applicable | unrelated |

Reader: `make verify` (Makefile:668) and Woodpecker step (.woodpecker.yml:234) read exit code and verdict lines; format unchanged.
