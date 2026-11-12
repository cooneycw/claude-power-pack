# Flow run record - issue #1715

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=0088c1f587ac4ce897942cc0572cba3d -->
## Run 1

- Run-id:            0088c1f587ac4ce897942cc0572cba3d
- Run-start:         3eaf643dbbc4fc38f5fbe947e5a45e79ff2c9b2b
- Issue:             #1715
- Base SHA:          3eaf643dbbc4fc38f5fbe947e5a45e79ff2c9b2b
- Necessity verdict: Partially addressed
- Approval:          granted
- Approver:          the wave orchestrator (wave cpp-improvement, policy rev 1, orchestrator-only), by mailbox rev 24: "GATE: GO-WITH-CONDITIONS #1715"
- Recorded at:       2026-11-12T01:51:09Z

### Section B evidence
- commits since 2026-11-11T23:07:43Z: ce8d1821 (#1720) and 4c8aa79a (#1724) touched scripts/codex-skill-sync.py only to add a family name each; neither touches the install, the check or the success line
- merged PRs: #1720, #1724; none open on these paths
- duplicate/superseding issues: none
- this host: no sibling worktree holds unpushed commits on these paths
- rows against the tree at 3eaf643d: seq 715 live on the two named-tree paths only; seq 564 live; seq 717 live; seq 453 mechanism live with nothing truncated today (55 descriptions, 1 over the cap, exempt); dead tracked-mirror machinery not reproduced by a name scan

### Conditions attached to the approval
- FIX 1: the published set equals the validated set, compared exactly both ways, on all three paths (bare --install, --write --install, --output-root DIR --install). The .pyc test fails on 3eaf643d. One shared ignore object.
- FIX 4: shown red by an over-cap description with no exemption and green with flow/check.md's exemption; state what a stale exemption does.
- FIX 3: one stderr line; stdout and exit code byte-identical with and without CODEX_HOME.
- No --install against this host's real ~/.codex/skills.
- Mirrors rebuild and the bundle-fidelity tests pass; the PR says skillc's profile fixtures pin an older commit.
- make lint, make typecheck; two review passes, ask before a third; no push without the slot.

### Section C - the approved plan
1. `scripts/codex-skill-sync.py` - one ignore shared by the check and all publish copies; the success line prints the real output root; a CODEX_HOME notice on --install
2. `tests/test_codex_skill_sync.py` - a .pyc in a named tree is not published; published set equals validated set on all three install paths; the success line for an in-checkout root is byte-identical and for an outside root names it; the CODEX_HOME notice appears only when the variable points elsewhere; no description is over the cap without an exemption
3. `docs/scripts/codex-skill-sync.md` - history lines
4. `CHANGELOG.md` - entry
Scope: 4 files, about 150 lines.
Risks: the script is what every Codex install runs, so a wrong ignore could drop real files - the test compares the published set with the validated set exactly, both ways; the success line changes on every bare --install.

### Lanes for this change
| Lane | Answer |
|---|---|
| Harness | will test, with new tests in this diff: installs into a temporary HOME from a named tree holding a planted .pyc and from a private build, comparing the published file set with the validated set. Not covered: a real Codex reading the installed skills, and this host's real install |
| Checkout | will test, with a new test: the success line from the checkout's own root and from a root outside it |
| Project state | will test, with new tests: CODEX_HOME unset, set to ~/.codex, set elsewhere |
| Driver | not applicable |
| Coordination | not covered: Kyle's pin is read, not exercised |
| CI provider | not applicable |
