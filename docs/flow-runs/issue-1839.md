# Flow run record - issue #1839

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=01c876d2223847e588c20aaf5f3a1766 -->
## Run 1

- Run-id:            01c876d2223847e588c20aaf5f3a1766
- Run-start:         c16af56e8528f290daa44b1993ee8eebbeead527
- Issue:             #1839
- Base SHA:          c16af56e8528f290daa44b1993ee8eebbeead527
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), in-session: "approve the revised plan"
- Recorded at:       2026-11-15T12:28:14Z

### Section B evidence
Commits since filing on the gate/controls/tests/doc: c16af56e (#1840, the parent) only.
Merged PRs since filing: #1840. Duplicates/superseding issues: none (#1835 closed parent; #1725, #864 Nit Store).
Host worktrees: 4 scanned, none with unpushed commits on these paths.
skillc#748 OPEN at 604084088cc9e11464c5cc263260f658836e400c: idea followed (one shlex-style reader recording per-word quote state), code not copied.
Plan revised after owner feedback: lane table + Reader rows added; discussion #1830 applied (single-source contract, charter line, behaviour tests, no "until #N").

### Section C - the approved plan
1. `scripts/check-doc-helper-flags.py` - one lex() reader replaces strip_substitutions, command_tail, inside_quote, command_words; docstring holds the single contract and credits skillc#748
2. `controls/doc-helper-flags/control.json` - register three cases; charter line
3. `controls/doc-helper-flags/cases/good-flag-after-helper-substitution/scripts/mailbox.sh` - shape 1 fixture helper
4. `controls/doc-helper-flags/cases/good-flag-after-helper-substitution/templates/core.md` - shape 1, GOOD
5. `controls/doc-helper-flags/cases/good-quote-continued-across-lines/scripts/mailbox.sh` - shape 2 fixture helper
6. `controls/doc-helper-flags/cases/good-quote-continued-across-lines/templates/core.md` - shape 2, GOOD
7. `controls/doc-helper-flags/cases/bad-paren-quoted-in-substitution/scripts/mailbox.sh` - shape 3 fixture helper
8. `controls/doc-helper-flags/cases/bad-paren-quoted-in-substitution/templates/core.md` - shape 3, BAD
9. `tests/test_check_doc_helper_flags.py` - three behaviour tests, each red on the pre-fix gate
10. `docs/scripts/check-doc-helper-flags.md` - replace the copied contract bullet with a pointer
11. `changelog.d/1839.md` - Fixed entry

Scope: ~12 files, ~200 lines.
Risks: the new reader could shift live verdicts (compare ok counts 347 flags / 258 invocations / 9 quoted before and after); a plain newline still ends a command inside an open quote (deliberate: an unterminated quote hides at most its line).

### Lanes for this change

| Lane | Answer | Detail |
|---|---|---|
| Checkout | not applicable | static scan of files; fixture trees via --root, no git |
| Harness | will test | Claude install: live scan of .claude/commands, .claude/skills, templates; Codex install: codex/skills mirrors are ignored build output, not scanned |
| Driver | not applicable | no driver doc changes; the gate reads them all the same way |
| Coordination | not applicable | no Kyle path |
| CI provider | will test | Woodpecker doc-helper-flags-check and negative-controls on the PR; GitHub Actions not this repo's CI |
| Project state | not applicable | CPP-internal gate |
| Toolchain version | will test | CI's pinned uv and Python image (PR pipeline) and the host or container's installed versions; stdlib only |
| Clone shape | not applicable | the gate makes no git calls |
| Run location | will test | invoked from the CPP root (make doc-helper-flags-check) and from another directory (test_runs_from_another_directory) |
| Gate target | not applicable | CPP itself only |
| Wave role state | not applicable | no wave state touched |
| Reader: make verify / Woodpecker doc-helper-flags-check | will test | verdict lines and exit codes unchanged in format; the live tree stays ok |
| Reader: check-negative-controls.py (make negative-controls) | will test | --control controls/doc-helper-flags: BAD read BAD, GOOD read GOOD, anchor blind |
