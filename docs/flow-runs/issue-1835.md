# Flow run record - issue #1835

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=8090ef6e5a5049b0a8f762c08afcec3a -->
## Run 1

- Run-id:            8090ef6e5a5049b0a8f762c08afcec3a
- Run-start:         3ed254698f3e32fb99adf203c955308531729a75
- Issue:             #1835
- Base SHA:          3ed254698f3e32fb99adf203c955308531729a75
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          owner (cooneycw), interactive "approved" in this session
- Recorded at:       2026-11-15T11:05:22Z

### Section B evidence
- commits: none touching templates/delegated-driver-core.md, the three driver docs, or scripts/flow-wave-mailbox.sh since 2026-11-14T20:59:54Z
- PRs inspected: 1837, 1836, 1834, 1833, 1832, 1829, 1827, 1826, 1820, 1819, 1817, 1816, 1815, 1814, 1813, 1812, 1808 - none fixes the flag
- duplicate/superseding issues: none (searched; 821, 971, 980 closed and unrelated)
- reproduced: the prescribed command exits 2 "unknown option: --kind"; without it, FLOW_MAILBOX: sent

### Section C - the approved plan
1. `templates/delegated-driver-core.md` - drop `--kind message` from the Step 3 escalation command
2. `.claude/commands/codex/auto.md` - re-render via make delegated-core-write
3. `.claude/commands/gemma/auto.md` - re-render
4. `.claude/commands/qwen/auto.md` - re-render
5. `scripts/check-doc-helper-flags.py` - new gate: doc-passed flags must appear in the helper's source (or an exec'd sibling)
6. `controls/doc-helper-flags/control.json` - negative control registration, bad and good fixture cases under controls/doc-helper-flags/cases/
7. `tests/test_check_doc_helper_flags.py` - unit tests for the gate
8. `Makefile` - doc-helper-flags-check target, added to verify
9. `.woodpecker.yml` - CI step if verify is not already what CI runs
10. `scripts/host-surface-observe.py` - register the new script, regenerate its anchor
11. `docs/decisions/0008-instrument-negative-control-bound.md` - census row
12. `controls/census.md` - control row
13. `docs/scripts.md` - inventory line
14. `.claude/verify-coverage.json` - only if the Makefile registration is not enough

Scope: ~13 files, ~350 lines.
Risks: substring match is permissive (false negatives only); a false positive would block make verify; registration misses cost gate cycles.

### Lanes for this change

| Lane | Answer | Detail |
|---|---|---|
| Checkout | not applicable | static scan of repository files; fixture trees via --root, no git |
| Harness | will test | Claude install: the gate scans the Claude command sources; Codex install: `make codex-skills` rebuilds the mirrors in verify, which are not scanned (ignored build output) |
| Driver | will test | delegated drivers (`/codex:auto`, `/qwen:auto`, `/gemma:auto`) via delegated-core-check and driver-parity-check; `/flow:auto` (Claude implements) doc is scanned, not changed |
| Coordination | not applicable | no Kyle path touched |
| CI provider | will test | Woodpecker via make verify; GitHub Actions not tested (not this repo's CI) |
| Project state | not applicable | CPP-internal gate, not a consumer feature |
| Toolchain version | will test | CI's pinned uv and Python image and the host or container's installed versions; stdlib python3 only |
| Clone shape | not applicable | the gate makes no git calls |
| Run location | will test | invoked from the CPP root (make) and from another directory (test with a foreign cwd and --root) |
| Gate target | not applicable | CPP itself only |
| Wave role state | not applicable | the corrected send behaves the same for a fresh role or a released role; checked by hand at Step 3 |
| Reader: delegated worker sessions | will test | the three rendered driver docs carry the corrected command; delegated-core-check proves the render |
| Reader: make verify / Woodpecker CI | will test | the new gate's verdict; negative control proves it can fail |
