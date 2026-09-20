# ADR 0008: What an instrument is, and when it needs a negative control

- Status: Accepted
- Date: 2026-09-14
- Issue: #932
- Supersedes: nothing
- Related: #924 (the executable negative-control machinery; it scopes itself
  to "gates" and could not define the word until this landed), #933 (its first
  consumer), #934 (the counter-model stage; produces ADR 0007, which is
  reserved for it and lands after this one - the numbering gap is deliberate),
  #936 (ADR 0009, the oscillation rule), #834 / [the detector
  contracts](../agents/detector-contracts.md) (the two questions asked of any
  instrument in a diff), [the glossary](../agents/glossary.md) (the defined
  terms this ADR attaches the bound to). Provenance:
  `docs/research/harness-strategy-recommendation-2026-09-14.html` section 04
  and the adoption plan `instruments-and-counter-model-adoption-2026-09-14`
  sections 01-02.

## TL;DR

**An instrument needs a committed negative control when its verdict is
consumed by a decision that will not independently re-derive the fact.** A
unit test the surrounding suite would catch does not; a gate that lets work
through does; a check whose green is read by another session or another repo
always does.

Enumerated against this tree on 2026-09-14, the bound captures
**61 distinct verdict contracts** - order tens, not thousands - which is
below the rejection threshold the issue set ("if the count lands in the
hundreds rather than the tens, the bound is wrong"). The count measures table
membership, not the effort of writing and maintaining the controls; that cost
is not measured here. The 2,408 test functions are excluded individually and
the suite is counted once. This narrows an existing directive; it adds no
tier, no process document and no checker.

## Context

The Negative Control directive in the host's global `~/.claude/CLAUDE.md`
(added 2026-09-13, the same day #924 was filed) defines an instrument as
"anything whose output is read as evidence" and requires that every one ship
with a committed input that makes it report the other verdict. The rule is
correct. Its scope is unbounded: taken literally it covers every one of 2,408
test functions in 102 files, 62 scripts, the nine `make verify` sub-gates,
seven CI steps, and every probe in every wave helper.

Nobody has that much time. What happens to an unaffordable rule is not that it
gets debated - it gets applied to whatever is in front of you and skipped
everywhere else, which produces exactly the condition the rule exists to
prevent: a population of instruments where some have controls and some do not,
and no way to tell which from the outside.

#924 sensed this and scoped itself to "gates", undefined, with seven named
consumers that are the seven that happened to fail recently - a list that
narrows rather than a rule that generalises. Its machinery cannot bound itself
until the word is defined and the rule has a denominator.

Two constraints shaped this decision and are recorded so they survive it:

- **Narrow, do not layer.** The 2026-09-14 issue-quality assessment concluded
  "adopt the proportional issue contracts already delivered rather than
  building another governance layer." If this document ever grows a tier
  system or a review process, it has gone wrong.
- **The enumeration comes first.** The bound was proposed untested ("I have not
  enumerated the instruments it captures. If the real count comes out in the
  hundreds rather than the tens, the rule needs another narrowing"). An
  enumeration that returns a number in the hundreds is the result the issue
  named as falsifying the bound, so it is the first acceptance item and the
  body of this document.

## Decision

### The bound

> An instrument needs a committed negative control when its verdict is
> consumed by a decision that will not independently re-derive the fact.

"Committed negative control" means a case checked into the repository - an
input and the verdict it must produce - that fails when the instrument stops
discriminating. "Will not independently re-derive" is the whole test: if the
consumer of a verdict re-establishes the fact itself before acting, the
instrument's green is not load-bearing and a blind instrument there costs
nothing but time. Re-deriving means establishing the *same fact*; a later
step that catches a different consequence of the same error (a merge conflict
after a missed file-overlap warning) is a backstop, not a re-derivation, and
does not exclude the earlier instrument.

### The carve-out

A unit test whose failure would be caught by the next test in the same file
does not need one. Its green is not individually load-bearing; the suite's is.
Whether the suite as a whole discriminates is a mutation-testing question, and
answering it per test would spend the entire budget on the population least
likely to be blind. The suite is counted as ONE instrument below, because its
exit code is what the finish gate consumes.

### The escalation

A check whose green is read by a **different session or a different repo**
always needs one, because the consumer cannot see the conditions that produced
it. A wave orchestrator reading a worker's `FLOW_WAVE: registered`, kyle
running CPP's finish gate, codex-power-pack inheriting a drift check through
the source bridge - none of them can tell a green produced by a working
instrument from one produced by a blind instrument, and none of them will
re-derive it. This is the case #924 already makes about blind CPP gates passing
bad work in the other two repositories.

### What this does not change

- **The regression-test rule is untouched.** "A regression test must FAIL on
  the code before the fix" costs one run on the pre-fix tree, not a committed
  case. The carve-out relaxes which instruments need a *committed* control; it
  does not relax the obligation to run a new test red once and say so.
- **"Outside the bound" does not mean "may be blind".** It means the proof
  that it is not blind belongs to the suite, not to a per-instrument case.
- **`spec` is not renamed and `harness` is not overloaded silently.** The
  glossary owns both points; the ledger's `harness` tag (#557) keeps its
  meaning.
- **The detector contracts still apply to every instrument**, captured or not.
  Membership floor and ownership boundary are review questions about a claim;
  the bound is about which claims get a committed case.

## The enumeration

### Universe and derivation

The universe is hardcoded so the enumeration cannot silently narrow itself:

| population | size on 2026-09-14 | how it was listed |
|---|---|---|
| `scripts/` | 62 files | `ls scripts/` |
| Makefile targets | 39 | `grep -E '^[a-z0-9_.-]+:' Makefile` |
| CI steps (`.woodpecker.yml`) | 7 | `secret-scan validate codex-skills-check eli5-vendor-check eli5-upstream-drift tool-risk-drift dockerfile-lint` |
| registered hooks (`~/.claude/settings.json`) | 2 | `PermissionRequest`, `SessionStart` |
| `lib/` command-line entry points | `lib/cicd` 16 subcommands, `lib/security` 5, `lib/creds` 8 | `add_parser(` in each `cli.py` |
| the test suite | 102 files, 2,408 `def test_` functions (grep count) | `grep -hE '^\s*(async )?def test_' tests/*.py \| wc -l` |
| pre-push hook | none in this repository | `.git/hooks` empty; kyle carries one, CPP does not |

**One population has shrunk since that date (issue #943, 2026-09-19): CI steps.**
The table above is left as measured on 2026-09-14 rather than rewritten, for the
reason this ADR gives receipts generally - a dated measurement records what was
true then, and editing it in place asserts a reading nobody took. What changed:
`dockerfile-lint` was retired, so the pipeline's last Dockerfile lint is gone and
row 45 (`hadolint`) has been removed from the census below.

The cause is worth stating because it is the failure mode this ADR is about
rather than a tidy-up. #469 retired CPP's container runtime but left one
Dockerfile in the tree, so the step kept a population of one. #943 retired
`mcp-evaluate/`, which owned it. The step's command was
`find . -name Dockerfile -print0 | xargs -0 -r hadolint`, and `xargs -r` does not
run on empty input - so from that moment the step would have exited 0 having
linted nothing, printing a green indistinguishable from a tree whose Dockerfiles
all passed. A zero-file population is UNKNOWN, not clean. The step was deleted
rather than left standing, because an absent instrument is visible in this table
and a blind one is not.

Row 45's number is NOT reused and the rows below it are NOT renumbered: prose in
this document cites rows by number, and renumbering would silently repoint every
one of those citations.
Members were derived by applying the bound to each entry: *name the decision
that acts on its verdict, and say whether that decision re-derives the fact.*
**One row per distinct verdict contract.** Wrappers of one verdict are one row
(`make lint` and the CI `validate` step both run `ruff`; `flow-finish-gate.sh`
invokes `lib.cicd run`, and `resume` is the same runner's continuation). Two
modes of one script that answer different questions to different consumers -
an offline manifest check and a live upstream-drift probe, a full scan and a
quick gate - are separate rows, because each needs its own control scenario
and they can legitimately disagree. Classes: **G** = a gate that lets work
through a lifecycle path; **X** = its green is read by another session or
another repo (the escalation clause); a row can be both.

### Captured

> **Row count versus the prose figures.** The original census enumerated **61**
> instruments, and every count in the analysis below ("twenty-five of the 61",
> "nine are library entry points", "which of the 61 have a control") is a
> statement about that census. Row 62 was appended by #960 when `shellcheck` was
> adopted. The prose figures are deliberately NOT renumbered: they are analyses
> of the original 61, and incrementing them would silently restate conclusions
> nobody re-derived - `shellcheck-gate.sh` is not a lifecycle helper and does not
> belong to any of the groupings those sentences describe. The census figures
> stay attached to the census.
>
> **The live row count is DERIVED, not written here.** The original clause said
> "a row added later is appended and noted here", and that upkeep rule was
> followed once - for row 62 - and then not: row 63
> (`check-negative-controls.py`, appended by #988) went unnoted, so a reader
> checking the note against the table found the note already behind. A count
> written in prose is stale from the next append onward, which is the same
> hand-maintained-number failure this ADR's own subject is about.
>
> So the note no longer carries one. `scripts/check-negative-controls.py` parses
> this table and prints `NEGATIVE_CONTROL_UNIVERSE: <n>` on every run; that
> number is the live census size, and it cannot drift from the table because it
> is read from it. **Frozen prose figures above, derived count below, and
> nothing in between that has to be remembered.**

| # | instrument | verdict | consumed by, without re-derivation | class |
|---|---|---|---|---|
| 1 | `flow-finish-gate.sh` + `lib.cicd run` / `resume` | `FLOW_FINISH_GATE: ok\|warn\|skipped\|fail`, and since #1027 the exit code that carries it (0/3/4/1) | the Step-6 commit, push and PR; the Step-7 re-gate; the same gate in kyle and CxPP | G, X |
| 2 | `flow-start-resolve.sh` (resolve and `--verify`) | `FLOW_START_RESOLVE`, `FLOW_START_VERIFY`, `CLAIM`, `LIVE_DRIVER`, `PR_HEAD` | whether a checkout is created, entered, or taken over | G, X |
| 3 | `flow-live-driver-guard.sh` | `FLOW_LIVE_DRIVER: clear\|suspected` | the first edit at Step 4 | G |
| 4 | `flow-stale-check.sh` | `FLOW_STALE_BASE: current\|moved-clean\|collision` | whether the base is merged in BEFORE editing (Step 4) and before the gate (Step 6); Step 7 re-derives only "behind", not the file-overlap distinction, and git's conflict detection sees textual conflicts, not shared files | G |
| 5 | `flow-worktree-guard.sh --strict` | exit 3 on a leak | the Step-6 commit | G |
| 6 | `flow-worktree-claim.sh` | `FLOW_CLAIM: self\|held\|free` | take-over and removal decisions across sessions | X |
| 7 | `worktree-remove.sh` | refusals: exit 4 claimed, 5 occupied, 6 dirty, 7 unpushed | whether a checkout is destroyed; called by `/flow:auto` and the sweep | X |
| 8 | `flow-worktree-sweep.sh` | five conditions per worktree; `SWEEP_WORKTREE:` | removal of other sessions' checkouts (ADR 0006) | X |
| 9 | `gh-pr-merge.sh` | review-required, deletions, base-moved, negated/incidental close, completeness | whether the squash lands on main | G |
| 10 | `flow-ci-status.sh` | `FLOW_CI_STATUS` | Step 8 deploy-or-stop | G |
| 11 | `flow-pr-watch.sh` | `FLOW_PR_WATCH` classified verdict, now resolved within the named status context rather than by raw pipeline number (#975) | the wave merge queue, in another session | X |
| 12 | `flow-driver-capability.sh` | `FLOW_DRIVER_CHECK: fit\|mismatch` | which lane an orchestrator assigns an issue to | X |
| 13 | `delegated-run-check.sh` | `DELEGATED_RUN_STATUS` | whether a `/codex:*`, `/qwen:*`, `/gemma:*` run is treated as success (#892) | G |
| 14 | `lane-serveability-check.sh` | `LANE_SERVE_STATUS` | whether `/qwen:auto` and `/gemma:auto` delegate at all (#921) | G |
| 15 | `flow-wave-mailbox.sh` | watch `armed\|deaf`, delivery `confirmed\|unconfirmed` | whether an orchestrator believes a worker can hear it (#898) | X |
| 16 | `flow-wave-registry.sh` | `FLOW_WAVE: registered\|...` | role-to-address resolution by a different session | X |
| 17 | `flow-wave-lexicon.sh` | `FLOW_LEXICON` accept/reject of a transition token | the wave protocol acting on the message | X |
| 18 | `flow-wave-plan.py` | the startable set and path-contention index | which issues an orchestrator hands out | X |
| 19 | `flow-wave-residuals.py promote` | promotable / refused (closed-wave, disposition, duplicate, emergency-override guards) | whether a residual candidate becomes an issue after the wave; the recording operations are not instruments | X |
| 20 | `check-ignored-additions.sh` | warning, or silence read as "nothing swallowed" | whether a new file is chased before commit | G |
| 21 | `speckit-context.py check` | `SPECKIT_CONTEXT_STATE` | how Step 2 plans a generated issue | G |
| 22 | `knowledge-graduation-check.py` | pass/fail plus a ledger write | whether a completed spec may be removed | G |
| 23 | `project-next.py` + the vendored `project_next` engine | `next_startable_issue`, safe/startable classification | `/project:next`, whose command document declares the JSON authoritative and forbids rebuilding the decision | G |
| 24 | `playwright-desk.py` lease allocation | a leased desk, or refusal | `/browser:session`, which acts on the returned object and stops on failure; the ledger operations are not instruments | G |
| 25 | `speckit-tasks-to-issues.sh` inventory and identity guards | refuses on an unreadable or truncated issue inventory (exit 4) and on an ambiguous task identity; otherwise creates or skips each issue | whether a GitHub issue is created, skipped, or duplicated; nothing re-checks GitHub state afterwards. The rendering of issue bodies is not an instrument | G |
| 26 | `check-test-binary-guards.py` | exit code | `make verify`; CI `validate` via its test | G |
| 27 | `check-negative-fixture-preconditions.py` | `negative-fixture: ok - every constructed absence ...` | `make verify`; CI `validate` (#933: its message is wider than its scan) | G |
| 28 | `check-claude-md-budget.py` | `ok - N/2000 words` | `make verify` | G |
| 29 | `check-claude-md-links.py` | resolves / `nothing was checked`; since #1037 also every on-disk `docs/agents/*.md` referenced by CLAUDE.md's Project Map, or `UNKNOWN` (exit 2) when the disk glob falls below its membership floor | `make verify` | G |
| 30 | `check-claude-md-behavior.py` | findability pass/fail | `make verify` | G |
| 31 | `project-next-vendor.py check` | per-file manifest hashes match | `make verify` | G |
| 32 | `project-next-vendor.py --upstream` | upstream moved / current (fail-open) | the revendor decision | G |
| 33 | `codex-skill-sync.py --check` | `DRIFT` / `MISSING` / `STALE` | CI `codex-skills-check`; the merge re-sync | G, X |
| 34 | `eli5-vendor.py` (manifest; `eli5-core-drift.sh` is a shim) | vendored core matches the pinned hash | CI `eli5-vendor-check` | G |
| 35 | `eli5-vendor.py --upstream` | upstream moved / current (fail-open, `failure: ignore`) | the revendor decision | G |
| 36 | `tool-risk-drift.py --strict` | taxonomy agreement | CI `tool-risk-drift` | G |
| 37 | `skills-check.py` | name conformance to the Agent Skills spec, trigger vocabulary reachable from `description`, provenance, references, and mirror parity with a SKIPPED count (#1034) | the canonical-surface rules by `tests/test_skills_check.py::test_real_repo_skills_are_valid_without_host_managed_state` in `make test` / CI `validate`; `make skills-check` itself is deliberately in NO gate (#1028: it compares host-local managed installs under `.agents/skills`, so wiring it into `verify` would fail a merge for an environment reason), and the managed-mirror half is consumed only by `install-drift.sh`. `make verify`'s closing report now names it as unexamined, with that reason | G |
| 38 | `classify-tool-risk.py` | a risk tier per observed command | allow-rule candidates proposed by `/security:permissions` and the census hook | G |
| 39 | `measurement-shape-scan.py` | `MEASUREMENT_SHAPES: <warn-count>`, always exit 0 | `/self-improvement:retro` replay mode folds each warn into classification and does not re-scan the transcript; a zero is read as "no cwd-drift shape here" | G |
| 40 | `make verify` as an aggregate | the AND of its prerequisite list | the operator running it under the CLAUDE.md directive "after any fix, verify through the full pipeline with `make verify`" - no lifecycle command invokes it (finish uses `flow-finish-gate.sh`, deploy the runner's plan); its own failure mode is a sub-gate silently dropped from the list, which no member row can see | G |
| 41 | `ruff` via `make lint` / CI `validate`, with `pyproject.toml` | exit code | `make verify`; CI | G |
| 42 | `mypy` via `make typecheck` / CI `validate` | exit code | `make verify`; CI | G |
| 43 | the test suite, as one instrument (`pytest` via `make test` / CI) | exit code, the zero-collected case (#621), and - since #1086 put it on `-n` - the COLLECTED COUNT, because a green over a smaller population prints the same colour as a green over the whole one | `make verify`; the finish gate; CI | G |
| 44 | `gitleaks` with `.gitleaks.toml` | findings or none | CI `secret-scan` (git history); `make secret-scan` (`--no-git`, working tree only - a different input population); the `lib.security` full and deep scans via their adapter. NOT the lifecycle gate: `lib.security gate` runs the quick scan, which never invokes gitleaks (#935) | G |
| 46 | `install-drift.sh` | `INSTALL_DRIFT` | `/cpp:update`, `/cpp:status`, the SessionStart message | G |
| 47 | `drift-detect.sh` | drift / none | `make drift-check`; the deploy path | G |
| 48 | `bootstrap-check.sh` (`lib.cicd` bootstrap) | blocking checks exit 0 | the deploy path | G |
| 49 | `mcp-drift.py` | orphaned infrastructure found / none | teardown | G |
| 50 | `branch-protection.sh check` | live protection matches posture | whether protection is re-applied (ADR 0004) | G |
| 51 | `commands-mirror-sync.sh` | mirror drift | refresh of an out-of-repo command mirror | G |
| 52 | `retired-surface-prune.py --check` | retired surfaces present / none | `make host-surfaces-check`; prune | G |
| 53 | `lib.cicd check` | Makefile-standards verdict | `/cicd:check` in any repo | X |
| 54 | `lib.cicd validate` | `cicd.yml` configuration verdict | `/cicd:*` in any repo | X |
| 55 | `lib.cicd validate-manifest` | manifest verdict | `/cicd:*` in any repo | X |
| 56 | `lib.cicd detect` | framework and package-manager classification | `/cicd:init` selects the Makefile template from it | X |
| 57 | `lib.cicd health` | probe verdicts | `/cicd:health` in any repo | X |
| 58 | `lib.cicd smoke` | smoke verdicts | `/cicd:smoke` in any repo | X |
| 59 | `lib.cicd verify` | baseline and `proceed\|rollback` | `/cicd:verify` and `/flow:auto` Step 9 in any repo (#603: CPP cannot dogfood it) | X |
| 60 | `lib.security scan` / `quick` / `deep` | findings by severity | `/security:*` in any repo | X |
| 61 | `lib.security gate` (quick scan only) | two policies: `flow_finish` blocks CRITICAL and warns HIGH; `flow_deploy` blocks CRITICAL and HIGH and warns MEDIUM (`lib/security/config.py`) | `/flow:finish` and `/flow:deploy` in any repo; a control has to cover the HIGH case that passes finish and blocks deploy | G, X |
| 62 | `shellcheck-gate.sh` (`make shellcheck`, CI `shellcheck`) | `shellcheck-gate: ok - N file(s) scanned at severity=S, 0 findings (source=git\|find)`, or non-zero; `UNKNOWN` (exit 2) when it could not look | `make verify` and the CI pipeline, which let work through on its verdict (#960) | G |
| 63 | `check-negative-controls.py` (`--strict`, CI `negative-controls`) | per-gate `PASS\|BLIND\|INERT\|UNRESOLVED\|UNPROVEN\|UNSIGNALLED`, then `negative-controls: ok - N control(s) discriminate` or a non-zero refusal | CI at `.woodpecker.yml`, which lets work through on its verdict; read by other sessions and other repos without re-derivation (#964, #981). CORRECTED (#1028): this cell also named `make verify`, which has never consumed it - there was no `negative-controls` target at all until #1028 added one, deliberately OUTSIDE `verify`. `make test` does run the whole battery, twice, through `tests/test_negative_controls.py:567` and `:876`, but neither passes `--strict` and neither asserts a battery-wide verdict, so 19 of 20 verdicts are computed and discarded (#1117). A census cell asserting a consumer that does not exist is how #1028's own premise came to be written down as settled | G, X |
| 64 | `npm-global-upgrade.sh` | `NPM_UPGRADE: upgraded\|current\|downgraded\|capped\|not-upgraded\|failed\|unknown` | `/cpp:update` Step 5d.2 and 5d.3 compose the Step 10 `Local-Model Lanes` line from it, and neither the operator reading that line nor a later session re-derives the installed version (#1022) | X |
| 65 | `dependency-audit.py` (`make dep-audit`, CI `dependency-audit`) | `dependency-audit: ok - N file(s) examined (source=walk\|capture), M package(s), G gating finding(s), S stale allowlist line(s)`, or `DEP-AUDIT-FINDING:` / `DEP-AUDIT-STALE:` (exit 1) / `DEP-AUDIT-UNKNOWN:` (exit 2) | CI at `.woodpecker.yml`, which lets work through on its verdict and does not re-derive it. NOT `lib/security/modules/pip_audit.py`, which is a different instrument with a different consumer: that adapter runs only inside `/security:scan`, skips silently when the binary is absent, and reads a `requirements.txt` this repository does not have (#961) | G |
| 66 | `check-oscillation.py` (`make oscillation`, CI `validate`) | `OSCILLATION_FINDING:` per two-sided change, else a clean verdict line | `make verify`, which lets work through on it; ADR 0009's detector, and nothing downstream re-derives whether a change reverses an earlier one (#936) | G |
| 67 | `counter-model-receipt.py parse` | `COUNTER_MODEL_REVIEW: findings\|clean\|unparseable` | `/flow:auto` Step 6 item 1c decides from it whether a review happened at all, and writes the receipt other sessions and ADR 0007's measurement read without re-deriving (#934, #1046) | G, X |
| 68 | `delegated-core-vendor.py check` | drift verdict over the vendored delegated-driver core, or non-zero | `make verify` and the CI `delegated-core-check` step, both of which let work through on it (#1011) | G |
| 69 | `eli5-core-drift.sh` | drift warning against the upstream `eli5-gate` core, or clean | the CI `eli5-upstream-drift` step; the vendored core in `.claude/commands/flow/eli5.md` is not otherwise compared to its canonical home (#443) | G |
| 70 | `flow-driver-retirement-check.sh` | `unknown` / non-zero per retirement precondition | `/flow:auto` Step 6's retirement gate authorised removing a driver on its verdict; nothing re-derives a retirement once taken (#1017) | G, X |
| 71 | `scripts-inventory-check.py` (`make scripts-inventory-check`, CI `scripts-inventory-check`) | `MISSING:` / `UNDECLARED:` per finding, then `scripts-inventory-check: ok - all N file(s) ... have an entry` | `make verify` and the CI step let work through on it, and six test modules quote `docs/scripts.md` as if complete on the strength of it (#1013) | G |
| 72 | `secret-scan-check.sh` (`make secret-scan`, CI `secret-scan`) | `gitleaks`' findings, wrapped: exit 0 clean, non-zero on a leak | THE WRAPPER IS WHAT RUNS. Row 44 is the binary; this row is the instrument `make` and CI actually invoke, and the one `controls/secret-scan` registers (#935) | G |
| 73 | `instrument-census-check.py` (`make instrument-census-check`, CI `instrument-census-check`) | `UNACCOUNTED:` / `STALE:` per finding, then `instrument-census-check: ok - all N file(s) in scripts/ are accounted for` | `make verify` and the CI step let work through on it; its green is read as "this table describes the tree", which is the claim every count below rests on (#1060) | G |
| 74 | `stash-worktree-guard.sh` | refusal on `git stash push` from a linked worktree, exit 1 aborting the ref transaction; `STASH_GUARD: installed\|current\|stale\|absent\|foreign\|unsupported\|disabled\|error` on the installer lane, where `disabled` is a RECORDED OPT-OUT and exits 0 - a settled user choice, not a fault an automatic caller repairs | THE CALLER, at the moment of the stash - and nothing re-derives it: a permitted push is indistinguishable from a safe one, which is how #1056's worker popped another session's work. Bounded to `push`: on `pop`/`drop` git removes the entry BEFORE the hook can veto, so the guard deliberately stays silent there and its silence is not approval. Installed automatically by `flow-start-resolve.sh --verify` (every worktree, every lane), `/cpp:init` and `/cpp:update`; all three consume the verdict ADVISORILY and fail open, so none can fail the step it runs in (#1056) | G |
| 75 | `toolchain-provenance.sh` | `TOOLCHAIN_PROVENANCE: current\|behind\|ahead\|diverged\|unknown`, with `behind`/`ahead` as NUMBERS and `-` where nothing was measured | `install-drift.sh` prefixes every install-parity verdict with it, and `flow-wave-registry.sh register` emits it to the orchestrator - a DIFFERENT session, which cannot re-derive which checkout this one executes. Nothing downstream recomputes the gap; #1029's 21-commit case ran eleven hours on a green toolchain nobody had measured (#1029) | G, X |
| 76 | `checkout-readers.sh` | `CHECKOUT_READERS: stale\|busy\|clear\|unknown`, plus `CHECKOUT_READERS_UNREADABLE: <n> (<m> same-user)` on every verdict whenever anything was uninspectable | THE OPERATOR SEQUENCING A PULL, and often not the session that ran it. `clear` is the declared safe moment; `stale` names the pids to re-arm. Nothing re-derives either - a pull made at an unsafe moment is indistinguishable from a safe one afterwards, which is the whole failure (#1029) | G, X |
| 77 | `tools-version-check.sh` (folded into `make tools-check`) | per-tool `pinned`/`installed`/state lines, then `TOOLS_VERSION: ok\|mismatch\|absent\|unknown` | `make tools-check`'s reader, deciding whether this host's gate verdicts are comparable with CI's. NOT re-derived by the gates themselves: `controls/shellcheck-gate` reports its own verdict identically under any linter version, which is precisely why `.woodpecker.yml` pins the image (#1029) | G, X |
| 78 | `deletion-accounting.sh` | `DELETION_ACCOUNTING_LINES:` / `_FILES:` / `_BLINDSPOT:`, then `DELETION_ACCOUNTING_FINDING: <n> deleted line(s) across <m> file(s)` (exit 1) or `deletion-accounting: ok - 0 deleted line(s)` (exit 0); `unknown` on every axis at exit 2, because "I examined nothing" and "nothing is deleted" must not share a verdict | A HUMAN OR AGENT ABOUT TO PUSH, and nothing downstream re-derives which lines a branch deletes: `git log --oneline origin/main..HEAD` shows one commit with your message, two-dot and three-dot diffs are identical after a `reset --soft` onto a moved ref, and a green suite cannot object to work that is absent. Not wired into any gate - its verdict is read by the person who ran it (#1031) | G, X |
| 79 | `check-consolidation-ledger.py` (`make consolidation-ledger-check`, CI `consolidation-ledger-check`) | `LEDGER_MISSING: cxpp#<n>` per finding, then `check-consolidation-ledger: ok - all N open entry(ies) ... have a row` | the Codex-consolidation children #1069-#1076 read `.specify/specs/codex-consolidation/ledger.md` to decide what may be moved, adapted or retired, and #1076 reads it to decide whether codex-power-pack may be ARCHIVED. Nothing downstream re-derives it: a capability with no row is not reported as undecided, it is never considered again. Read by other sessions and by the other repository, so both halves of the bound apply (#1068) | G, X |
| 80 | `pytest-workers.sh` (`make test`, CI `validate`) | the resolved integer on stdout and `pytest-workers: -n <N> (source: ...)` on stderr; `pytest-workers: REFUSED` and exit 2 on `auto`, a non-integer, or 0 | `make test` and the CI `validate` step, which pass the number straight to `-n` and never re-derive it. Its refusal is the only thing standing between a host-set `PYTEST_WORKERS=auto` and 24 workers per invocation on a box already carrying up to nine concurrent suites (#640, #1086). Its committed two-sided case is `tests/test_pytest_worker_cap.py` rather than `controls/`: the harness hands a gate a case DIRECTORY and this gate's whole input is an environment variable | G |
| 81 | `pytest-parallel-differential.py` | `MEMBERSHIP FLOOR: OK\|VIOLATED`, `OUTCOME DIFFERENTIAL: <n> node(s) changed verdict`, then `VERDICT: no dangerous-direction changes` (0), `BLOCKS - `/`QUARANTINE - ` (1), or `DIFFERENTIAL-UNKNOWN:` (2, and never a pass) | THE ACCEPTANCE DECISION for running the suite in parallel, and nothing downstream re-derives it: once `-n` is in `make test` and in CI, every later green is read as "the same tests passed" on the strength of one comparison made once. Controlled at `controls/pytest-parallel-differential` (#1086) | G |
| 82 | `flow-wave-mailbox.sh` `supervise`/`__supervise_daemon` | `FLOW_MAILBOX: supervising\|duplicate` (exit 0/4) from the lifetime-flock ownership check | whether a session believes a role already has a live supervisor and skips arming its own, across sessions - a distinct verdict contract from row 15's `watch armed\|deaf` (a different question: not "is a listener running" but "did MY attempt to become one succeed"). Fixed under #1033 to close the fd-inheritance gap that let an orphaned child of a SIGKILLed daemon keep the flock held after its owner no longer existed, so `duplicate` stopped being trustworthy exactly when it mattered most | X |
| 83 | `counter-model-uniformity-check.py` | `UNIFORMITY-OK:` / `UNIFORMITY-FINDING:` / `UNIFORMITY-UNKNOWN:`, always with `examined=<n> verifiable=<m> distinct=<k>` (exit 0/1/2) | THE OPERATOR deciding the disposition of the 13 landed counter-model receipts (#1048 items 1-2), which will not independently re-derive whether the corpus's reviewer uniformity is a copied literal or a genuine constant. Advisory only - not wired into any gate or CI step in this repository, deliberately: a gating version would block on that same undecided disposition. Controlled at `controls/counter-model-uniformity` (#1091) | X |
| 84 | `slate-reconcile.py` | `SLATE-OK:` / `SLATE-FINDING: UNACCOUNTED\|PHANTOM\|DUPLICATE #<n> [in <location>]` / `SLATE-UNKNOWN:`, always with `open=<n> claimed=<n> UNACCOUNTED=<n> PHANTOM=<n> DUPLICATE=<n>` (unknown counts printed as `unknown`, never 0) (exit 0/1/2) | AN OPERATOR OR A DIFFERENT SESSION reading a clean verdict as an accounted slate without independently re-deriving membership - the previous version of this check lived only in a session scratchpad and was lost to a resume, so every count reported since could not be verified. Open set is measured (`gh issue list`, or `--open-set-capture` offline); claimed set is a hand-maintained declaration at `docs/slate-lanes.json` (`docs/slate-lanes.md` states plainly it is not a measurement, and names a real granularity limit - it will not catch #1033/#1094, the exact duplicate that motivated it, because that pair is two legitimately different issue numbers, not one number claimed twice). Controlled at `controls/slate-reconcile` (#1099) | X |
| 85 | `flow-wave-registry.sh` `list --any-live` | `FLOW_WAVE_ANY_LIVE=yes\|no-roles-ended\|no-roles-registered\|undeterminable` (exit 0/1/1/2) | `flow-wave-mailbox.sh`'s `__supervise_daemon`, which acts on `no-roles-ended` by releasing its lifetime flock and exiting - a decision nothing downstream re-derives, since the daemon that made it is gone. A distinct verdict contract from row 16's role-to-address resolution (a different question: not "where do I reach role R" but "is anything in this WAVE still alive at all") and from row 82's per-role supervising/duplicate ownership check (a different question again: not "did MY attempt to become the supervisor succeed" but "is there still anyone left in the wave to supervise"). `undeterminable` is its own case, not folded into `no-roles-registered`, so a registry file that exists but fails to parse cannot be misread as a genuinely empty wave (#1095) | X |
| 86 | `check-version-consistency.py` | `ok - N location(s) agree`, mismatches, or `UNKNOWN` (exit 2) when derived locations fall below `MIN_LOCATIONS`, `git ls-files` itself fails, or `git` is not on PATH at all (counter-model review, #1037: README/CHANGELOG alone could otherwise clear the floor without ever examining a tracked file; CI pipeline 2128 found the git-absence case uncaught) | `make verify` | G |
| 87 | `check-unicode-dashes.py` | `ok - N tracked .md file(s) clean`, occurrences of U+2014/U+2013 outside fenced blocks (blockquoted fences included), or `UNKNOWN` (exit 2) when the tracked `.md` population falls below its floor, a file cannot be read, or `git` is not on PATH at all | `make verify` | G |
| 88 | `check-co-authored-by-trailer.py` | `ok - no pinned ... trailer found`, matching lines, or `UNKNOWN` (exit 2) when `git grep` itself fails, `git` is not on PATH at all, or the eligible tracked-file population falls below its floor (counter-model review, #1037: exit 1 alone cannot tell "searched, found nothing" from "nothing to search") | `make verify` | G |
| 89 | `counter-model-reviewer-attribution.py` | `ATTRIBUTION-OK:` / `ATTRIBUTION-FINDING:` / `ATTRIBUTION-UNKNOWN:`, always with `examined=<n> linked=<m> agreed=<a> disagreed=<d> ambiguous=<x> unlinked=<u> extractor_distinct=<k>` (exit 0/1/2) | THE OPERATOR deciding the disposition of the 13 landed counter-model receipts (#1048 items 1-2), which will not independently re-derive whether a receipt's stored reviewer matches the rollout that produced it. Distinct from row 83, which asks whether the CORPUS's uniformity is a copied literal; this asks whether an INDIVIDUAL receipt agrees with its own evidence, and can answer it for receipts that carry no exec-log manifest - the case row 83 records as unreachable. Advisory only, wired into no gate or CI step: its subject is a decided disposition (annotate, do not rewrite), not a condition to block on. Its own blindness refusal (`extractor_distinct <= 1` withdraws any finding to UNKNOWN) is the load-bearing half, controlled by a committed PAIR supplying the same disagreement under a discriminating and a non-discriminating extractor. Controlled at `controls/counter-model-reviewer-attribution` (#1048) | X |
| 90 | `bandit-audit.py` (`make bandit-audit`, CI `bandit-audit`) | `bandit-audit: ok - N file(s) examined under <roots> (source=walk\|capture), L loc, G gating finding(s) at severity>=MEDIUM, S stale allowlist line(s), B below threshold, A accepted`, or `BANDIT-FINDING:` / `BANDIT-STALE:` / `BANDIT-SUPPRESSION:` (exit 1) / `BANDIT-UNKNOWN:` (exit 2) | `make verify` and the CI `bandit-audit` step, both of which let work through on its verdict and neither of which re-derives it. NOT `lib/security/modules/` - those nine adapters carry no Python SAST at all, so `/security:scan` cannot produce this verdict and this does not duplicate it. The SUPPRESSION verdicts are load-bearing rather than decorative: a bare `# nosec` (`metrics.<file>.nosec`) and a rule-scoped `# nosec <ID>` (`metrics.<file>.skipped_tests` - a DIFFERENT field, which the first cut missed) each delete a finding before the report exists, so without both the visible ledger has an invisible twin. `skipped_tests` does NOT report a CLI `--skip`; that question is answered by pinning the argv, not by reading a metric (#962) | G |
| 91 | `verify-coverage-check.py` | `VERIFY_COVERAGE_TARGETS:` / `_EXAMINED:` / `_SCRIPTS:` / `_CENSUS:` on every run, then `UNACCOUNTED:` / `MISCLASSIFIED:` / `STALE:` / `UNDECLARED:` findings (exit 1) or `verify-coverage-check: ok - ...` (exit 0); `_CENSUS: unread` says the `not-a-checker` cross-check did not run, because unread must not read as empty | `make verify` - as a prerequisite, and again as the RECIPE that prints the closing 'what this run did NOT examine' report. Nothing downstream re-derives either: the report IS the consumer, and a report that under-names is indistinguishable from a repository with less to name. It is the only instrument that can see row 40's own failure mode - a sub-gate silently dropped from `verify`'s prerequisite list, which no member row can self-report - and the only one that asks whether a checker in `scripts/` is reachable from any gate at all (#1028). Controlled at `controls/verify-coverage` | G |
| 92 | `undeclared-import-audit.py` (`make undeclared-import-audit`, CI `undeclared-import-audit`) | `undeclared-import-audit: ok - N file(s) examined under <root>/ (pruned: ...), I distinct module-level third-party import name(s), U undeclared, A accepted, S stale allow line(s); D guarded/deferred name(s) are outside this gate's question`, or `UNDECLARED-IMPORT:` / `UNDECLARED-IMPORT-STALE:` (exit 1) / `UNDECLARED-IMPORT-UNKNOWN:` (exit 2) | `make verify` and the CI `undeclared-import-audit` step, both of which let work through on its verdict and neither of which re-derives it. It is the instrument for the blind spot `dependency-audit` (row 87) structurally cannot cover: that gate asks OSV about what `uv.lock` PINS, so a package imported directly and declared nowhere is never queried and cannot appear in any advisory row however vulnerable it is. The STALE direction is load-bearing rather than decorative - an entry that accounts for nothing exits 1, and it fired on its own author's intended entry before that entry was committed (#1041). Resolution reads COMMITTED METADATA ONLY and never `importlib.metadata`, which reports what is installed and would make the verdict depend on the machine, the ambient-scan failure #1044 closed one gate over | G |
| 93 | `check-control-ci-deps.py` (`make control-ci-deps-check`) | `CI_DEPS_STEP:` / `CI_DEPS_STAGED:` (and `CI_DEPS_UNRESOLVED_STAGE:` when a staging step cannot be read), then `CI_DEP:` / `CI_PIPELINE:` findings (exit 1) or `control-ci-deps: ok - N of M registered control(s) ...` (exit 0) | `make verify`, which lets work through on it, and nothing downstream re-derives it. It is the ONLY instrument whose subject is an environment it does not run in: a registered control that needs a binary the `negative-controls` image lacks does not fail alone, it makes the whole register unable to report (the harness refuses to SKIP a control it cannot run), and the condition is invisible on a dev box where every tool is present. The provided set is DERIVED - the battery step's image from `.woodpecker.yml`, pinned against `CI_IMAGE` in `check-test-binary-guards.py`, plus what its `depends_on` steps stage into `.ci-bin` (#1036). Controlled at `controls/control-ci-deps` | G |
| 94 | `flow-vantage.sh` | `FLOW_VANTAGE_BASIS:` / `FLOW_VANTAGE_SOURCE: measured\|declared` / `FLOW_VANTAGE: host\|container\|unknown`, one exit code per verdict (0/3/4) | `flow-wave-registry.sh register` derives it once and STORES it on the role entry, and `get` / `list` serve it to the ORCHESTRATOR - a different session, on a different machine, which cannot re-derive a fact about somebody else's process. The decision it feeds inverts across the boundary: past it the mailbox is lane 1 and `SendMessage` addresses a population holding no fleet peer, so a wrong `host` is not a slower send but a silent non-delivery that returns success (#947, #958). `unknown` is a first-class third state for the same reason - the two usable signals can disagree, and a default that quietly absorbs the disagreement is how a three-state contract decays into a two-state one. Controlled at `controls/flow-vantage`, whose anchor is CONSTRUCTED: the gate is new, so there is no blind ancestor to vendor, and the vendored artifact is instead the mount-shaped check `register.md` recommended until 2026-09-16, which answers `host` on both sides of the boundary | X |

> **Rows 66-73 were added by #1060, and how they were found is the point.** None
> of the eight was a judgement that had been made and deferred - they were simply
> never asked about. Seven predate #1060 by between four days and three weeks;
> `counter-model-receipt.py` (row 67) is the one that then shipped carrying
> #1047 and #1048, the exact defect class this table exists to bound.
>
> `scripts/instrument-census-check.py` now derives this membership from
> `scripts/` and goes red on a file named by neither table, so the next
> instrument cannot arrive unasked. Row 73 is that gate accounting for itself;
> without its own row it would report itself `UNACCOUNTED` on its first run,
> which is the self-reference working rather than a paradox.
>
> **The count moved 65 -> 73, and the coverage fraction got worse, correctly.**
> `check-negative-controls.py` printed `13 of 65` before this change and `13 of
> 73` after. Nothing regressed: the denominator stopped under-counting. Anyone
> quoting the older figure - the v8.0.0 notes do - is quoting a number taken
> against a table that described a smaller repository than the one that existed.

> **Row 63 closes an ACCOUNTING gap, not a verification one.** The harness that
> checks whether instruments carry controls was itself missing from the list of
> instruments that need one, which is the omission #964 names. Registering it in
> `controls/` (#974) and enumerating it here (#981) means it is counted and it
> carries a control like any other row.
>
> It does **not** make the harness self-verifying, and the distinction matters
> because the opposite reading is available and wrong. A control is executed BY
> the harness, so a harness mutated to emit `PASS` unconditionally would report
> its own control passing. Nothing in this table catches that. What catches it is
> `tests/test_negative_controls.py` under pytest - a DIFFERENT runner, which
> drives the register and asserts the verdicts rather than accepting them. The
> instrument and the thing that can falsify it have to be separable, and here
> they are separable only because the test suite is not the harness.

> **Row 65 is the first row added under the third-party-tool shape below**, and
> the reason it is a separate row from 60/61 is the part worth keeping. CPP
> already had a pip-audit consumer - `lib/security/modules/pip_audit.py`, reached
> by `scan_full` and `scan_deep` - so the tempting reading was that the tool was
> adopted and #961 was a shopping decision about a second copy.
> `docs/research/class-enumeration-2026-09-15.md` took that reading explicitly
> ("an unadopted tool is *absent*, not dormant"). It is wrong about this ticket:
> the adapter appends to `skipped` when the binary is missing and passes, reads a
> `requirements.txt` CPP does not have - so with pip-audit installed it audits the
> ambient environment rather than the project's lock - and `lib.security gate`
> runs only the quick scan, which never reaches it (row 61 records that half
> already). A tool wired into a path no gate reads is the dormant shape, not the
> absent one.
>
> The distinction the two rows draw is the one the bound cares about: row 60's
> consumer is a person reading `/security:scan` output in any repo, and row 65's
> is this repository's CI, which merges or refuses on the verdict. Same binary,
> different decisions, and only the second one lets work through unexamined.

> **Row 60's pip-audit half now carries a committed negative control (#1044).**
> It lives in `tests/test_pip_audit.py` and covers a missing binary, a missing
> dependency population that refuses an ambient-environment fallback, a missing
> `uv` binary when `uv.lock` is the only population, and invalid JSON returned
> with exit zero. `make verify` exercises it through pytest; it does **not** live
> under `controls/`, so `scripts/check-negative-controls.py` does not include it
> in the row-63 "N control(s) discriminate" count. The harness therefore
> understates row 60's control coverage rather than showing it absent; #1036 is
> the underlying observation that this denominator is not homogeneous.

### A control must be valid WHERE THE HARNESS RUNS (#960, #964)

A control is not a file; it is a thing that executes. So its dependencies have to
be satisfied **in the environment the harness runs in**, not merely in the
environment its own subject runs in. `check-negative-controls.py` deliberately
refuses a SKIP concept - a registration it cannot exercise reports `UNRESOLVED`
or `UNSIGNALLED` and fails, rather than passing quietly - so an unsatisfiable
dependency is a red, and correctly so.

**Dependency means environment, not just image.** All of these are dependencies,
and each can be present on the author's machine and absent where the verdict is
consumed:

- a **binary** the gate shells out to (#960: the negative-controls step runs in
  the `uv` image, which has no `shellcheck`, so the control reported
  `UNSIGNALLED` while the author's box passed with the tool on `PATH` from a
  scratch directory);
- a **tracked file** the control reads (#964: a control was green locally and
  BLIND in a clean clone, because its nested manifests fell outside a
  one-level-deep `.gitignore` negation and were never committed);
- a **tool the gate itself needs to enumerate**, such as `git`, which is absent
  from the CI image by design.

Two independent derivations reached this within an hour, from different tickets
and different mechanisms, neither aware of the other. That is the reason it is a
clause here rather than a note in a CI file: the common factor is not the image
or the gitignore, it is that **the control was verified somewhere other than
where it gates.**

Practical consequences:

- Enumerate every registered control's dependencies against **each** image that
  runs the harness. In this repo that is more than one step: the dedicated
  negative-controls step AND `validate`, whose pytest suite drives the whole
  register.
- Where a tool must be shared across steps, stage **one pinned copy** rather than
  installing per-step. `apt` in the `uv` image supplies shellcheck 0.9.0 against
  the 0.10.0 pinned for the gate, and one gate running under two linters makes
  the control's verdict depend on which container reached it.
- A local green says the control works **here**. Only a run in the harness's own
  environment says it works where its verdict is read.

### Adopting a third-party linter as an instrument (#960, and the pattern #961/#962 inherit)

`shellcheck` was the first standard tool adopted under this ADR. The shape it
settled, stated here because `pip-audit` (#961) and `bandit` (#962) are the same
ticket with a different binary:

- **Derive the file population; never glob it.** `git ls-files '*.sh'` misses
  `scripts/cpp-memory`, a tracked bash script with no suffix, and a tracked-only
  list misses untracked files entirely. Filter on extension OR content, and
  report which derivation ran.
- **Print the denominator on every run, including the clean one.** `0 findings`
  is only meaningful beside `N examined`. A zero-file scan is `UNKNOWN`.
- **A missing binary is `UNKNOWN` and exits non-zero, never a pass.** The
  tempting `command -v <tool> || exit 0` goes green on every machine that lacks
  the tool, which is the dormant-instrument failure this ADR exists to prevent.
- **Suppressions are visible or they do not happen.** Adopt at a severity the
  tree can actually hold, and record the findings below that severity as a
  counted residual with a filed issue. A disabled check is invisible; an issue
  is not. `shellcheck` shipped with **zero** suppressions and no `.shellcheckrc`
  at all - the day one is needed, the file appears with the reason in the same
  commit.
- **An anchor for a BRAND NEW gate cannot be historical on main, and that is
  accepted rather than worked around.** A control for a pre-existing gate anchors
  to a real commit in main's history (row 1's `c6df826` does). A gate introduced
  by its own PR has no such ancestor: its anchor commit lives on the branch, and
  squash-merging orphans it, so `--verify-provenance` will read `unverified`
  permanently. This costs nothing operationally - the operative check is the
  sha256 of the vendored anchor, which is git-independent, and CI deliberately
  runs `--strict` WITHOUT `--verify-provenance` because git is not in the CI
  image. What it costs is the distinction: `unverified` then means "unresolvable
  anywhere, forever" rather than the ordinary "git is absent here", and nothing
  in the output separates those two causes. Record the terminal cause in the
  anchor entry so a reader chasing it does not hunt for an object that was never
  going to exist. **Integrity is established; historicity is not.**
  - *What would move this back (#936):* if provenance ever becomes CI-checked, or
    an audit needs to establish historicity rather than integrity, then landing
    the naive implementation as its own merged PR and anchoring to ITS squash
    commit becomes correct, and this ruling should be revisited. Named here so
    #961 and #962 inherit the decision rather than re-litigating it.
  - *Taken up by #962, and worth recording because the anchor stopped being a
    construction:* bandit's blind implementation is codex-power-pack's live
    one-liner, vendored verbatim, so the control's demonstration IS the issue's
    thesis rather than an illustration of it. `kind: constructed` still, because
    the artifact has no commit in THIS repository's history - but "constructed"
    should not be read as "invented".

#### What #962 settled that #960 and #961 did not: the SHAPE of a suppression

`shellcheck` adopted with **zero** suppressions and #961 with a per-finding
ledger, so neither had to answer what to do with an inherited one. #962 did, and
the answer generalises past bandit:

- **A `--skip` is not a short allowlist, it is a different instrument.** It
  turns a rule off across the whole population, forever, and has no direction in
  which it can go stale. Measured: codex-power-pack's `--skip
  B104,B108,B310,B602` removes **10 of CPP's 11** MEDIUM+ findings, because the
  two rules it suppresses most are the two this tree's design produces most.
- **So the residual is recorded per (file, rule, COUNT).** That makes three
  distinctions a blanket skip cannot draw into reds: a new site in a file that
  already has one, a new site in a fresh file, and a recorded site that gets
  FIXED and leaves its line behind.
- **Adopting a neighbour's configuration is inheriting their evidence.** The
  skip list was correct about codex-power-pack's tree, and nobody measured it
  against this one. The precedent the issue cited is CPP's own four disabled
  mypy error codes, load-bearing in two repositories because the same move was
  made once and never re-derived.
- **Enforce the decision, do not merely document it.** A skip reaching the tool
  by any route, and an inline `# nosec`, are both findings - read off
  `metrics._totals.skipped_tests` and `metrics.<file>.nosec`. A decision nothing
  checks lasts until the next person edits a Makefile.
- **Excluding a fixture DIRECTORY is not suppressing a check.** The gate skips
  `controls/*/cases/**` (deliberately-bad inputs, still linted by the control
  itself with `--root`) and `controls/*/anchors/**` (frozen byte-identical
  historical copies whose sha256 is the provenance - editing one to satisfy a
  linter destroys what the control rests on).

### Excluded, with the reason

| population | reason under the bound |
|---|---|
| 2,408 test functions, individually | the carve-out: the suite catches an individual test's failure; the suite is row 43 |
| `hook-permission-census.sh`, `hook-pending-retro.sh`, `friction-log.sh`, `run-delivery-pilots.py`, `lib.cicd status`; the recording operations of `flow-wave-residuals.py` and `playwright-desk.py` | recorders and reporters; nothing decides on their output without reading it, and `delivery-pilots.md` states per instrument what it does not establish. The guarded operations of the two ledgers are rows 19 and 24 |
| `hook-mask-output.sh`, `secrets-mask.sh` | filters, not verdicts; `CLAUDE.md` states the masking hook "does not authorize reading credentials" - nobody is entitled to rely on it |
| `cpp-commands-link.sh`, `flow-helpers-install.sh`, `install-memory-harness.sh`, `memories-db-setup.sh`, `setup-woodpecker-cli.sh`, `bash-prep.sh`, `codex-skill-sync.py --write`, `eli5-vendor.py --revendor`, `project-next-vendor.py --revendor`, `retired-surface-prune.py --prune`, `prompt-context.sh`, `cpp-memory`, `project-init.py`, `c4-mermaid.py`; the rendering half of `speckit-tasks-to-issues.sh` (its guards are row 25) | installers, generators, ledgers and renderers; the state they produce is re-derived by the drift and parity checks in rows 31-37, 46, 51-52 |
| `sandbox-phase1-trial.sh` | a one-off experiment whose decision is recorded in ADR 0002; re-running it is the re-derivation |
| `ci-stage-jq.py`, `counter-model-receipt.py write` (its `counter-model-receipt.py parse` half is row 67) | a stager and a recorder. `ci-stage-jq.py` installs a content-pinned `jq` into `.ci-bin/` and emits no verdict - the gate that then uses `jq` is row 70, and a failed stage surfaces there as `unknown` rather than as a pass. The receipt writer records what the run decided; the deciding is row 67 |
| `lib.cicd container`, `pipeline`, `infra-init`, `infra-discover`, `infra-pipeline`, `init-manifest` | generators; their output is a file the caller reviews, not a verdict |
| `lib.creds` (8 subcommands) | `get`, `set`, `delete`, `list`, `rotate`, `run`, `ui` are actions, not verdicts. `validate` reports a credential usable; the use that follows re-derives it loudly (a bad credential fails at the call), which is the bound's own exclusion - it is the one entry in the universe excluded by re-derivation rather than by kind |
| verification commands in docs | instructions to run an instrument, not instruments; the instrument they name is already a row above |
| `make deploy`, `make update_docs`, `make format`, `make clean` and the other action targets | informative no-ops or actions in this repository |

**Subjects with no file under `scripts/`.** Fourteen rows above name a
third-party binary or a Python module entry point - there is no file for a
`#: NEGATIVE-CONTROL:` marker to live in, which is the structural half of
#1036's second point. They are declared here so
`scripts/instrument-census-check.py` can tell "names something outside
`scripts/`" from "names a script that has been deleted", which need opposite
responses and otherwise render identically. The list NARROWS what is checked, so
it fails loudly: an undeclared non-file subject is reported `STALE` until
someone adds it here.

**Row 74's control is in `tests/`, not `controls/`.** Its negative control needs a
real repository with a real linked worktree, and git is absent from the
`negative-controls` CI image by design - the anchors are vendored precisely
because of that. A git-dependent control registered there reports UNSIGNALLED and
fails the pipeline, so registering one would trade a working control for a red
build. `tests/test_stash_worktree_guard.py` carries both halves issue #1056
names, plus a blind-hook variant asserting the known-bad outcome flips.

<!-- instrument-census: external-subjects: ruff, mypy, pytest, gitleaks, make, lib.cicd, lib.security, lib.creds, pipeline, infra-init, infra-discover, infra-pipeline, init-manifest -->

`ruff`, `mypy`, `pytest`, `gitleaks`, `make` (the `verify`
aggregate, row 40), `lib.cicd`, `lib.security`, `lib.creds`, and the `lib.cicd`
subcommands `pipeline`, `infra-init`, `infra-discover`, `infra-pipeline` and
`init-manifest`. `hadolint` was on this list until issue #943; see the note under
**Universe and derivation** for why it left. Being on this list is a statement about where the instrument
LIVES, never that it is out of the bound - `gitleaks` is row 44 and carries a
control today, reached by wrapping it in `secret-scan-check.sh` (row 72). The
wrapper is the route for the others.

No script-level instrument is excluded by the re-derivation clause alone. The
first enumeration listed `flow-stale-check.sh` there on the grounds that Step 7
re-derives it; the counter-model review (Codex, Step 5 of the run that landed
this) showed that Step 7 re-derives "behind" and not the file-overlap
distinction Step 4 acts on, so it is row 4. The second pass added row 25 and corrected rows 40 and 61. The carve-out does nearly all of
the excluding in this tree, and that is worth knowing: the population the
bound removes is the test functions, not the scripts.

### What the count says

61 distinct verdict contracts against a universe of thousands. That is
"tens" by the issue's own threshold, so the bound is not falsified by this
tree and stands. What the number does NOT say, stated so it is not read as
more: it is a count of rows, not a measure of the effort to write, keep and
re-confirm 61 controls, and "affordable" in that sense is unmeasured. It is
at the upper end of tens, and three things about it are worth stating rather
than leaving to be inferred:

- **The lifecycle helpers are the bulk (rows 1-25).** Twenty-five of the 61
  are flow, wave and session helpers, and twelve of those are
  cross-session by construction. That is where the escalation clause bites
  hardest and where #924's seven consumers all sit.
- **Nine are library entry points other repos consume (rows 53-61).**
  They are captured by the escalation clause alone: CPP cannot see kyle's
  deploy verification run, so kyle cannot see whether CPP's verdict was blind.
- **Thirteen of 102 test files carry explicit control language today**
  (`negative control`, `positive control`, `can_fire`, `known-bad`, `red
  case`) - a fact about vocabulary, not about discrimination, and stated only
  so the register #924 builds has a starting point. Which of the 61 have a
  registered, reverted-and-reconfirmed control is #924's denominator to fill,
  not this document's.

The enumeration is a dated snapshot. It is not maintained here: #924's register
is the living list, and a new instrument is added there, next to its control,
not to this table. The enumeration is also the falsifier the issue named for
this decision, not a committed negative control in the directive's sense: no
case demonstrates that it would detect an omitted instrument, and the Step-5
review found seven omissions and mis-attributions in its first version, and
three more on its second pass. The count above is the corrected one.

## The directive edit

The Negative Control section of the host's global `~/.claude/CLAUDE.md` is
host-managed and outside this repository, so the edit cannot travel in a pull
request. It is quoted here so it is auditable. The first paragraph (the
definition) and the last five bullets are unchanged; the following block is
inserted after the definition, and the first bullet's opening changes from
"Before you ship an instrument" to "Before you ship an instrument the bound
captures":

```
The committed-case requirement is BOUNDED (claude-power-pack ADR 0008): an
instrument needs a committed negative control when its verdict is consumed by
a decision that will not independently re-derive the fact.

- A unit test whose failure the surrounding suite would catch does not need
  one; its green is not individually load-bearing, the suite's is. The
  regression-test rule below is unchanged: its red run costs one execution on
  the pre-fix code, not a committed case.
- A gate that lets work THROUGH (a finish gate, a preflight, a drift check,
  `make verify` itself) does need one; nothing downstream re-derives it.
- A check whose green is read by a different session or a different repo
  ALWAYS needs one; the reader cannot see what produced it.
```

Two known limits of that edit, recorded rather than solved here: it reaches
only this host, and kyle session containers do not mount `~/.claude/CLAUDE.md`
at all (kyle#1176), so a containerised session builds instruments under a rule
it cannot read until that mount lands.

## Consequences

- `instrument`, `harness` and `counter-model` are defined terms
  ([glossary](../agents/glossary.md)); issues and ADRs use them rather than
  "gate", "check" or "the tooling" when the distinction matters.
- #924 can scope itself: "every instrument the bound captures" replaces "the
  seven that failed recently", and the register it builds has a denominator
  of 61 to start from.
- Adding an instrument the bound captures means adding its committed control
  in the same change. Adding a unit test does not.
- No new check enforces this document. A checker for "is this verdict
  consumed without re-derivation" would be an instance of the pattern the
  detector contracts describe - a mechanical answer to a question about the
  relationship between a message and its consumer. The decision is held to
  account by the enumeration's rejection criterion (hundreds) and by #924's
  register, which will show, instrument by instrument, whether the bound's
  members actually get controls.

## What this does not solve

- **It does not register any control.** 61 instruments are named; how many
  of them have a control today is not measured here. That is #924's job, one
  instrument at a time, starting with #933.
- **It does not make the suite discriminate.** The carve-out moves the
  question to mutation testing and answers nothing about it.
- **It does not reach the other repos' instruments.** kyle's fleet checks and
  health probes (kyle#1209) and codex-power-pack's adoption (CxPP#240) apply
  the same bound to their own trees; this enumeration is CPP's only.
- **It does not carry the directive into containers** (kyle#1176).
