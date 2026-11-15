# Flow run record - issue #1847

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.

<!-- flow-run n=1 id=b58c22cac5104b62bcb58f4e25bb10ac -->
## Run 1

- Run-id:            b58c22cac5104b62bcb58f4e25bb10ac
- Run-start:         06392d4060864e82db5cee7103e6577897b7e17b
- Issue:             #1847
- Base SHA:          06392d4060864e82db5cee7103e6577897b7e17b
- Necessity verdict: Still needed
- Approval:          granted
- Approver:          the owner, in this interactive /flow:auto session ("i approve the plan with both deviatons"), after an ELI5 of the two deviations
- Recorded at:       2026-11-15T20:42:01Z

### Deviations from the issue's proposed approach (approved)
1. The reviewer prompt stays inside the helper as one string, not a sibling text file: the prompt is built byte-for-byte as today, with no placeholder substitution and no second install unit.
2. The `codex exec --json` event stream goes to the retained stream file only, not also to stdout, so the helper's closing marker lines are not buried.

### Section B evidence
- commits since 2026-11-15T20:02:25Z: `06392d40` (#1852) - added the scope paragraph to the reviewer prompt and a triage line to `code_review.md`; no extraction; merged into this branch before the first edit
- merged PRs since filing: #1852; earlier that day #1845, #1843, #1841, #1840 (none touch the review)
- duplicate/superseding issues: none; #1850 (flow:auto charter) is related and decides whether a review is required, not how it runs
- sibling worktrees on this host: #1821 has unpushed commits touching `.claude/command-word-budgets.tsv` and the delegated `auto.md` files, not the review

### Section C - the approved plan
1. `scripts/codex-review-run.sh` - new helper: `[--base REF] [--context TEXT] --transcript FILE`; Steps 1-4 of `code_review.md` moved unchanged; prints the existing markers; writes the relay (markers, banner, findings) to the transcript; exits 0 `CODEX_REVIEW: ran`, 1 blocked, 3 unavailable (including a nonzero `codex exec`), 2 usage; `--marker NAME FILE` read mode
2. `.claude/commands/codex/code_review.md` - six bash blocks become one bare call plus an exit/marker table; the network verdict table, withdrawal lists, triage/relay rules and Step 5 stay
3. `.claude/command-word-budgets.tsv` - lower the `codex/code_review.md` row to the measured count (and `flow/auto.md` if it drops)
4. `.claude/commands/flow/auto.md` - Step 6 1b invokes the helper bare; 1d reads each receipt flag with `--marker`; inside the 10410 cap
5. `tests/test_code_review_diff_range.py` - run the helper with stub binaries, not the extracted Step 2 block; red cases kept
6. `tests/test_code_review_diff_file_cleanup.py` - same move
7. `tests/test_code_review_large_patch.py` - same move
8. `tests/test_code_review_network_fence.py` - same move; verdict table stays pinned to the doc, `NET_BLOCKED_RCS` pinned to the helper
9. `tests/test_code_review_sandbox_scope.py` - same move
10. `tests/test_lanes_contract.py` - prompt and lane-list extraction read the helper; doc pointer assertions stay
11. `tests/test_changed_output_readers.py` - prompt extraction reads the helper; doc pointer assertions stay
12. `tests/test_detector_contracts.py` - `code_review.md` moves to `PINNED_SURFACES` (no longer carries the review marker; still must link the contract)
13. `tests/test_counter_model_review.py` - empty-diff test reads the merge-base guard from the helper
14. `tests/test_codex_review_run.py` - new: `--marker` found/missing, exit mapping, transcript parses through the real `counter-model-receipt.py parse`
15. `.claude/verify-coverage.json` - register the helper
16. `docs/scripts.md` - one inventory line
17. `docs/scripts/codex-review-run.md` - the script's reference page
18. `controls/census.md` - one census row
19. `scripts/flow-helpers-install.sh` - add the helper to `HELPERS`
20. `templates/claude-settings-permissions.json` - `Bash(~/.claude/scripts/codex-review-run.sh:*)`
21. `docs/agents/driver-parity.json` - flow:auto-only exemption, only if the parity check needs it
22. `changelog.d/1847.md` - changelog fragment

Scope: about 20 files; helper about 500 lines, mostly moved; `code_review.md` loses about 400 lines.

Risks: a moved test loses its red case (each is run red against a broken helper); `flow/auto.md` sits at its cap with 0 spare words; #1821's unmerged edit to the budget table may conflict; deviation 2 removes live progress (the stream file remains).

### Lanes for this change

| Lane | Answer | How, or why not |
|---|---|---|
| Checkout | will test (main checkout, linked worktree) | Tests build a temporary repository (main checkout); the real review in this run executes in a linked worktree |
| Harness | not applicable | The `codex` command family is unpackaged (`UNPACKAGED_FAMILIES` in `scripts/codex-skill-sync.py`); a Codex session takes the review skip |
| Driver | will test (`/flow:auto`); not applicable (delegated drivers) | This run's Step 6 runs the helper; delegated drivers never invoke `/codex:code_review`; `make driver-parity-check` runs |
| Coordination | not applicable | No coordination call changes |
| CI provider | not applicable | No CI helper changes |
| Project state | will test (a repository that has adopted a feature's file or record, one that has not) | Tests with and without `docs/measurements/counter-model` (canonical committed patch vs working-tree diff) |
| Toolchain version | not covered | No version matrix (#1788); the helper needs bash 4.4+, CPP's existing floor |
| Clone shape | will test (a full clone with all refs, a fresh or shallow main-only clone) | A clone with no common ancestor must give `CODEX_REVIEW: unavailable`, exit 3; full history in the other tests |
| Run location | will test (invoked from the CPP root, from another directory) | Untracked file seen from a subdirectory; a non-checkout caller gives `unavailable` |
| Gate target | not applicable | Not a gate-runner change |
| Wave role state | not applicable | No wave role touched |

Reader: `counter-model-receipt.py parse` / `write` - reads the transcript and marker values - tested against real output (this run's own review and receipt).
Reader: `/flow:auto` Step 6 1b/1d - reads the helper's markers - tested against real output (this run).
Reader: kyle `tests/fixtures/container-surface/cpp-commands-contract.json` - derives the `codex`/`curl` binary requirements from `code_review.md`'s `command -v` probes - not covered; pinned to a sealed CPP revision, so a coordination issue is filed in kyle.
