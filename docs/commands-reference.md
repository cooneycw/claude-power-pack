# Commands Reference - detail beyond the skill listing

Relocated from `CLAUDE.md` by issue #711. Every command's own description is
already resident in each session's skill listing, so the root memory file keeps
only the operative rules and pointers; the incident history and the elaborated
per-command detail live here. Entries are verbatim moves - nothing was reworded
or dropped, so a rule summarised in `CLAUDE.md` also appears here in full.

See also `docs/scripts.md` (the `scripts/` half of the same move).

## Persistent-context detail relocated by issue #724

The root `CLAUDE.md` retains the operative rules and routes here for their
history and boundary detail. Test fixtures must not inherit uncontrolled
absolute paths in values consumed by broad classifiers: checkout names and
pytest temporary roots can contain a matched word, turning the fixture's host
location into an accidental input. Use a fixture-owned relative executable and
assert the intended negative classification before running the exercise.

Read-only commands should name their target through `git -C`, full refs, or an
absolute tool argument. A `cd X && ...` prefix defeats narrow permission rules,
and a cwd-relative branch measurement can return an empty, plausible-looking
answer after the shell cwd drifts. In shared checkouts, ref-scoped evidence is
the contract; agreement among reads sharing the same unverified cwd is not
corroboration.

CPP has no deployable container runtime. Its external second-opinion and browser
servers are client registrations, while remaining AWS Secrets Manager clients
fetch directly. Reproducible builds pin remaining image references by version
tag plus digest; Renovate owns digest rotation. The full retired-runtime and
host-artifact inventory lives in `docs/HOST_MANAGED_ARTIFACTS.md`.

Makefile targets remain the canonical build interface. The deterministic runner
and command adapters own fallback, baseline, deploy, and recovery states; the
root memory file only names the local verification targets.

The CI/CD configuration keeps its detailed machine contracts in `lib/cicd/`.
`ProcessCheck` is an exactly-one probe union: an entry names one of `port`,
`systemd_user_unit`, `systemd_unit`, or `pattern`, so portless workers are
described honestly and multiple probes never depend on silent precedence.
Invalid endpoint, process, and smoke-test entries fail soft with a warning so
one malformed probe cannot disable every other probe or the deployment gate;
structural errors outside those lists still fail closed. `validate_file`
reports unknown nested probe keys even though runtime loading remains
permissive. CPP dogfoods deploy verification through its service-less import
smoke probe, and `tests/test_step9_verify_executes.py` executes the documented
baseline/verify pair so invocation drift is a test failure rather than prose.

## Workflow commands - detail beyond the skill listing

  - Optional second arg `PROJECT` targets a repo other than the session cwd (resolved as a path, else `~/Projects/<name>`); such cross-repo runs ride the deterministic git-worktree lane end-to-end instead of `EnterWorktree`, which cannot leave the session repo (#578)
- `/flow:auto_codex` - `/flow:auto` with a Codex pre-PR review stage inserted between Implement and Update Docs (10 steps): `/codex:code_review` reviews the branch, accepted findings are fixed in the worktree with one bounded re-review, and the accepted/rejected/deferred summary lands in the PR body; degrades to plain `/flow:auto` when Codex CLI is unavailable (#611)
- `/flow:register <role>` - Declare this session's wave role in the host-level registry so an orchestrator addresses it by transport-verified socket, never by `ListAgents` display names (`--list` roster with liveness + lane-overlap warnings, `--release` to leave; #638)
  - Registration also ARMS the delivery lane (#676): the worker backgrounds `flow-wave-mailbox.sh watch --role <R>` on its own outbox before standing by, and the documented delivery preference order is direct `SendMessage` -> mailbox+watch -> user relay as a named LAST resort (it was the first resort on 2026-08-11). A registered worker with no watch is the failure itself - it stands by correctly, forever, while a written assignment sits undelivered
  - Registration also RE-BRIEFS (#699): the orchestrator declares the wave's policy once (`policy set --wave W --authority implement --gate ... --ledger ...`) and every `register` reprints it, so a `/clear`ed or compacted worker recovers the protocol by re-registering instead of waiting to be retyped at. Workers declare their own facts (`--model`, `--permission-mode`, `--files`, `--capacity`); an undeclared policy reads `absent` rather than passing silently, and declared file lanes are checked for overlap like branches
  - Registration also documents what the worker EMITS (#709, the worker half of #701's lexicon): `PUSHBACK <argument>` (a refutation of an assignment's premise; the argument is mandatory, so it cannot be skimmed past as agreement) and the `LEDGER` block (`delivered:`/`in-scope:`/`residual:`, all three required - the shape `policy set --ledger` declares and `FLOW_WAVE_POLICY_LEDGER` re-briefs), plus `flow-wave-lexicon.sh validate --body-file <f>` as the read-only pre-send check. Both tokens were already REFUSED at `send` by the #701 validator (exit 6, box untouched) while the worker-facing file named neither - a guard firing at a reader who was never told the rule; `tests/test_flow_register_worker_tokens.py` runs the documented examples through the real validator and mutation-asserts the refusal, so a page teaching a shape the tool rejects is a red test rather than plausible prose
- `/flow:merge` - Merge PR, clean up worktree
- `/flow:wave <name>` - Orchestrate a dependency-ordered issue wave across N worker sessions (#637): the orchestrator never implements - it assigns disjoint lanes from `flow-wave-plan.py`'s startable set, judges each worker's `/flow:auto` Step-3 gate with tree-verified evidence, re-runs the planner after every scope-touching verdict (approve-with-conditions included), verifies PRs against gate conditions, and enforces the delivered/in-scope/residual completeness ledger; roster/addressing consumed wholesale from `/flow:register` (#638), delivery consumed wholesale from the #676 mailbox lane (the orchestrator arms one `watch --role orchestrator` covering every worker inbox, routes ack/assignment/verdict/re-plan over the lane when `SendMessage` cannot reach a worker, and treats an issue as in-flight on the worker's ACK rather than on its own send - an assignment whose box still shows `UNREAD` is the 2026-08-11 failure reproducing)
  - The completeness ledger carries a SEVERITY gate on filing (#714): every residual is still declared at the gate, but only one naming a consequence someone would notice (user-visible behavior, correctness/security risk, cost or data-loss exposure, work another issue is blocked on) becomes a tracker entry - the rest are recorded in the ledger's `residual:` line and the PR body, and "measure X" / "annotate the files we excluded" / "tighten a coupling we just introduced" are named as not issue-worthy alone. The rule changed the DESTINATION of a low-severity residual, never whether it is declared. The evidence was depth rather than volume: the 2026-08-11 aws-learn wave's error rate rose per generation because a residual reasons about the previous agent's work product, and its worst gen-3 case (aws-learn#838) proposed a `service_healthy` compose dependency that would have deadlocked every cold start - it even requested a deadlock check and shipped anyway, because the policy required a residual to be filed, not validated. Hence the companion rule: a residual proposing a change to a system the filer has not run carries its verification or is worded as a question, and carries its generation. `tests/test_flow_wave_residual_severity.py` pins that BOTH surfaces (`wave.md` orchestrator-side, `register.md` worker-side) carry the gate and that neither has drifted back to the unconditional form - the failure it exists to catch is one surface being updated while the other silently teaches the old rule
  - Per wave close the reporting metric is now residuals RECORDED and the subset FILED (#714) - one number cannot show whether the severity gate is being applied, and equal counts mean it is not

## Visible worktrees on the git lane (#627)

**Visible worktrees on the git lane (issue #627; native `EnterWorktree` #440
superseded for the default):** `/flow:start` and `/flow:auto` create worktrees
OUTSIDE the repo by default - a visible sibling of the repo in its parent dir
(`../<repo>-<branch>`), or under `FLOW_WORKTREE_BASE` when set (#584) - via
`git worktree add` (in `scripts/flow-start-resolve.sh`), entered with `cd`.
Because an out-of-repo worktree cannot ride Claude Code's native `EnterWorktree`
(its base dir is not configurable, and out-of-repo `EnterWorktree(path=...)`
triggers an unsuppressable approval prompt, ADR 0003 constraint 2), the run rides
the git lane end-to-end (`GIT_LANE=1` always) and cleanup uses `git worktree
remove` / `scripts/worktree-remove.sh`; the native `EnterWorktree`/`ExitWorktree`
fresh lane is retired. CPP layers its issue-anchored gate policy on top: the
`issue-<N>-<slug>` branch name (enforced by the helper's `--verify`), the
`/flow:eli5` necessity gate, the quality gates, and merge/cleanup discipline are
unchanged; the guard/merge/remove/friction scripts resolve via git plumbing and
work at any location. `.claude/worktrees/` stays gitignored (legacy/defensive -
nothing is created there anymore). The `/flow:*` commands live under the
permanent source of truth at `.claude/commands/flow/*`. CPP's marketplace copies
were retired in #662 / ADR 0005; the tiered symlink command surface returns in
#663. The legacy global-skill mirror (`~/.claude/skills/flow-*`) and its
`flow-skill-sync.py` generator remain retired (#480). `/flow:repair`
(`scripts/flow-helpers-install.sh`) installs the helper family to
`~/.claude/scripts/`, the stable path the #581 allowlist rules match.
`/flow:doctor` reports missing/stale helpers read-only.

## Worktree path-resolution rule (#486)

**Worktree path-resolution rule (issue #486):** the flow worktree is a visible
sibling *outside* the main repo (`../<repo>-<branch>/`, issue #627). Resolve every
`Write`/`Edit` path from the active worktree root - `git rev-parse
--show-toplevel` - or use a plain relative path from the session cwd; **never
hand-build an absolute worktree path**, which has been observed to land the edit
in the MAIN repo working tree instead of the worktree (flow:auto #442 x2, #471). `/flow:auto`
Steps 4/6 run `scripts/flow-worktree-guard.sh --strict` - **blocking since
#576**: it exits 3 when a path this run edited is ALSO freshly modified in the
main tree, the signature of a leaked edit, so the trap stops the run instead of
being narrated past. Two downgrades keep it from crying wolf: pre-existing main
dirt that does not overlap this run's edits is a quiet info note (#536), and
overlapping dirt whose main-side mtime predates the run's freshness window
(`FLOW_LEAK_FRESH_MIN`, default 30m) warns but does not block (#576) - that case
is someone else's uncommitted work on a shared file, not a leak from this run.
A total leak (idle worktree + fresh main edits) is caught by the same freshness
rule (#573).

## Concurrent flow sessions (#597)

**Concurrent flow sessions (issue #597):** CPP encourages parallel `/flow`
sessions, and nothing used to stop two of them from operating on one repo - or
one worktree. Four failures were captured in a single friction buffer, the worst
of them silent: a sibling session's Step-7 cleanup removed a live session's
worktree by name, destroying uncommitted work. A run now stakes a **claim** on
its checkout (`scripts/flow-worktree-claim.sh`, a real `git worktree lock`)
during the Step-1 verify gate, and three guards read it: Step 1 refuses to start
on an issue another LIVE session holds (`CLAIM=held` -> `CONFIRM_REQUIRED=1`),
`worktree-remove.sh` refuses (exit 4) to delete a worktree claimed by a live
sibling, and Step 4 re-runs the #503 live-driver guard immediately before the
first edit, since the Step-1 check goes stale across the analysis and approval
pause. Separately, Step 9 skips `make deploy` when `.claude/deploy.log` already
records a SUCCESSFUL deploy of the current HEAD sha, so a commit a concurrent
session just shipped is not deployed twice. Ownership is pid + session with
host-scoped `kill -0` liveness; an owner that is gone reads as `stale` and is
taken over automatically, so a claim can never permanently wedge a repo, and
`--steal` is the documented break-glass. Repeated stale-base churn (the fourth
captured failure - `origin/main` moving several times mid-run) is NOT addressed
here: it needs serialized merges, not an ownership claim, and the #473
stale-check plus the #462 Step-7 guard remain its only mitigations.

## Standalone skill extractions (#443)

**Standalone skill extractions (issue #443):** skills with standalone value are
extracted to their own public plugin repos so users never have to clone CPP -
they install via `/plugin marketplace add cooneycw/<repo>` or `npx skills add
cooneycw/<repo>`, and improvement issues for an extracted skill are filed in
THAT repo, not here (the learnings->issue bridge, #463, routes there too). CPP
stays a consumer: it vendors the extracted skill's canonical core between
marker comments and layers its /flow wiring outside them; an advisory drift
script warns when the vendored copy falls behind. First extraction: the
`/flow:eli5` necessity gate -> https://github.com/cooneycw/eli5-gate
(core markers `eli5-core:begin`/`end` in `.claude/commands/flow/eli5.md`).
That link is guarded on both sides (issue #591 - before it, the drift script
was invoked by nothing at all): `.claude/eli5-vendor.json` pins the vendored
core's sha256 plus the upstream commit, enforced offline by
`scripts/eli5-vendor.py` (`make eli5-check`, the `eli5-vendor-check` CI step
and `tests/test_eli5_vendor.py`), while `scripts/eli5-core-drift.sh` ->
`eli5-vendor.py --upstream` live-fetches the canonical copy as a fail-open
advisory (`make eli5-drift`, the `eli5-upstream-drift` CI step). Neither
subsumes the other: the manifest cannot see upstream move, the fetch cannot run
offline. Reconcile drift by editing the canonical repo first, then
`make eli5-revendor` (which re-pins the manifest in the same step).

## `/cicd:woodpecker`, `/codex:code_review`, `/documentation:c4`, `/browser:session`

- `/cicd:woodpecker` - Generate a hardened self-hosted Woodpecker pipeline (opt-in secret-scan + image-security + runtime-smoke stages) and scaffold the server/agent from `templates/woodpecker/`; see `docs/skills/woodpecker-ci.md`

- `/codex:code_review [BASE] [CONTEXT]` - Codex reviews the current branch's diff vs base (read-only) and returns structured findings (severity, file:line, suggestion); consumed by `/flow:auto_codex` as the pre-PR review stage, usable standalone from any branch (#611)

- `/documentation:c4` - Generate C4 architecture diagrams as GitHub-renderable Mermaid via `scripts/c4-mermaid.py` (all 4 levels, per-container L3, per-component L4; flowchart L1-L3 + classDiagram L4; edge-validity QA gate, density-split hints, `index.md` + manifest)

- `/browser:session <verb> [name]` - Named **concurrent** browser sessions over upstream `@playwright/mcp` via a static "lease-desk" pool (create/resume/save/close/list/cleanup/pool). Recovers the one feature upstream lacks (microsoft/playwright-mcp#1530) with no fork. Opt-in pool registered via `/cpp:init` (Full tier -> browser pool); ledger in `scripts/playwright-desk.py`. See `docs/skills/browser-session-wrapper.md`.

## Deterministic runner: plan definitions and test-count honesty

  - **Plan definitions live in THREE places and `.claude/cicd_tasks.yml` wins** (#617). The runner loads the manifest when one exists and only falls back to `BUILTIN_PLANS` in `lib/cicd/steps.py` when it does not, while `generate_manifest()` in `lib/cicd/manifest.py` decides what a NEW project's manifest contains. Changing a plan means changing all three - a fix applied only to `BUILTIN_PLANS` is a no-op for CPP itself and for every manifest-carrying project. A step defined under the manifest's `steps:` but referenced by no plan is dead config, which is exactly how typecheck sat unused for months. Dogfood a plan change before trusting it: `FLOW_GATE_CPP_DIR=<worktree> ~/.claude/scripts/flow-finish-gate.sh` runs the gate with the WORKTREE's runner + manifest instead of the installed checkout's, and the step count in its output is the proof
  - **A test step's exit code is not evidence that tests ran** (#621). pytest exits 0 with every test skipped, so the `finish` gate reported an unqualified SUCCESS for a suite that executed none of the tests gating the change (agentic-poker flow:auto #65: `312 passed, 66 skipped`, where the 66 were the acceptance tests). The runner now parses the summary line (`lib/cicd/outcomes.py`, pytest/jest/vitest/unittest) and carries the counts: the step logs `test: SUCCESS (312 passed, 66 skipped)`, `RunResult.tests` + the persisted `StepRecord.tests` hold them, and a step that exited 0 having executed NOTHING logs `SUCCESS - NO TESTS RAN`, records a `warnings` entry, and turns the closing line into `completed WITH WARNINGS`. `scripts/flow-finish-gate.sh` reports `FLOW_FINISH_GATE: warn` (still exit 0) for such a run rather than flattening it back to `ok`. Exit codes are unchanged everywhere - this surfaces the false green, it does not fail on it; a suite that skips nothing behaves exactly as before. The parse is gated on the step id/command naming a test runner, so `make lint` is never mistaken for a suite

## Installation: the canonical tiered install

The tiered `/cpp:init` install is CANONICAL (#663, on the marketplace retirement #662 / ADR 0005): Tier 1 symlinks the command surface (user scope via `scripts/cpp-commands-link.sh`, per-family `~/.claude/commands/<family>` links; optionally project scope `.claude/commands`), so the executed command text follows `git pull` atomically - `/cpp:update` is the ONE update verb, with no package cache to reconcile (the retired `/plugin` lane's cache refreshed only on a version-stamp change CPP's release style never produced; `/plugin update` no-opped on it and `/plugin install` refused when installed - the 2026-08-11 incident). Hosts still carrying the retired cached families should uninstall each with `/plugin uninstall <family>@cpp`; Claude Code's native `/plugin` remains available for third-party content. `/cpp:init` / `/cpp:update` also install and refresh the non-command infra (external MCP server pointer, `@playwright/mcp` registration, secrets/AWS-SM access, spec-kit CLI, the PermissionRequest census hook, and the `/flow:*` allowlist merge). See `README.md` and `docs/HOST_MANAGED_ARTIFACTS.md`.

- `/cpp:init` - The canonical installer (Tiers: Minimal, Standard, Full, CI/CD, Codex): Tier 1 installs the symlink command surface (#663 - user scope via `scripts/cpp-commands-link.sh`, optionally project scope). It wires the external second-opinion `.mcp.json` pointer, `@playwright/mcp`, `tavily-mcp`, the census hook + flow allowlist, optionally spec-kit, and - at the Codex tier - the generated Codex skills plus common-memory harness. Init only ever INSTALLS; retired-surface teardown belongs to `/cpp:update`
- `/cpp:status` - Check installation state
- `/cpp:update` - Pull latest, sync deps, migrate legacy systemd units if present, tear down orphaned Docker MCP infra via the curated `.claude/deprecated-mcps.yaml` (Step 6c/7, user-confirmed; CPP ships no container runtime since #469), then offer to merge new flow allowlist rules from `templates/claude-settings-permissions.json` into `~/.claude/settings.json` (Step 7.5, user-confirmed) and to register the observe-only PermissionRequest census hook there (Step 7.6, user-confirmed); also refreshes the optional spec-kit CLI (`specify`) if installed (Step 4.6); and offers an out-of-repo commands-mirror drift check/refresh via `scripts/commands-mirror-sync.sh` when a mirror exists (Step 7.8, #582); then refreshes the generated host surfaces (Step 7.9, #575) - installs the Codex skills, wires the common-memory harness, and detects retired surfaces still present via `scripts/retired-surface-prune.py`, offering a per-surface, user-confirmed, reversible teardown

## Self-improvement commands

- `/self-improvement:retro` - Post-run friction retro (the grill-me cycle): always-on capture (`scripts/friction-log.sh` -> `.claude/friction.jsonl`, woven into `/flow:auto` + `/flow:merge`) then classify -> dedup -> propose -> confirm -> codify durable fixes; local ledger `.claude/learnings.md`, portable knowledge delegates to `/self-improvement:memory` (#433)

- `/self-improvement:memory` - Populate the shared common-memory ledger with portable friction-knowledge (bucket-2-plus); consult-not-push, fail-open

## Bare command entries removed from `CLAUDE.md` (#711)

Each line below duplicated the command's own description, which every session
already receives in its skill listing - that duplication is why they left the
root memory file. They are recorded here verbatim so the few slivers that were
NOT in the frontmatter (argument signatures such as `/secrets:rotate KEY`, and
qualifiers such as `/qa:test` being single-session) are not lost.

### Workflow

- `/flow:start` - Create worktree for an issue
- `/flow:eli5 <issue>` - Plain-language intent + necessity/staleness verdict + plan approval gate (runs after analyze, before implement)
- `/flow:check` - Run lint + test + typecheck + security scan (no commit)
- `/flow:finish` - Quality gates, commit, push, create PR
- `/flow:deploy [target]` - Run make deploy + health/smoke checks
- `/flow:auto` - Full issue lifecycle in one shot (ELI5 plan/necessity approval gate between analyze and implement; the pause has no bypass - see issue #775)
- `/flow:sync` - Push WIP to remote for cross-machine pickup
- `/flow:cleanup` - Prune stale worktrees and branches
- `/flow:status` - Show active worktrees
- `/flow:doctor` - Diagnose workflow environment
### Project

- `/project:init <name>` - Full project scaffolding (zero to GitHub repo)
- `/project:next` - Prioritized next-step report (compact default ~2-4K tokens; `--full` deep analysis, `--brief` single pick)
- `/project:lite` - Quick project reference (~500-800 tokens)
### Spec-Driven Development

- `/spec:help` - Overview of the spec-kit authoring path
### GitHub Issues

- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issue
- `/github:issue-view` - View issue details
- `/github:issue-update` - Update existing issue
- `/github:issue-close` - Close issue with optional comment
### CI/CD

- `/cicd:init` - Detect framework, generate Makefile and cicd.yml
- `/cicd:check` - Validate Makefile against CPP standards
- `/cicd:health` - Run health checks (endpoints + processes)
- `/cicd:smoke` - Run smoke tests from cicd.yml
- `/cicd:verify` - Verify a deployment against a pre-deploy baseline (proceed/review/rollback)
- `/cicd:pipeline` - Generate CI/CD workflows: GitHub Actions, or self-hosted Woodpecker via `pipeline.provider` (consults cicd_tasks.yml manifest if present)
- `/cicd:container` - Generate Dockerfile and docker-compose.yml
- `/cicd:infra-init` - Scaffold IaC directory (foundation/platform/app tiers)
- `/cicd:infra-discover` - Generate cloud resource discovery script for IaC import
- `/cicd:infra-pipeline` - Generate per-tier CI/CD pipelines with approval gates
### Codex Orchestration

- `/codex:auto <ISSUE>` - Full issue lifecycle delegated to Codex CLI (8 steps: worktree, approve, implement, review, quality gates, PR)
- `/codex:exec <PROMPT>` - One-shot Codex execution in current directory with JSONL monitoring
- `/codex:ask <QUESTION>` - Delegate a read-only question to Codex and relay its answer (read-only by default; network opt-in on explicit request)
- `/codex:status` - Check Codex CLI installation, config, and readiness
- `/codex:help` - Codex commands overview
- Pre-implementation gate (issue #774): all three delegated drivers - `/codex:auto`, `/qwen:auto`, `/gemma:auto` - STOP at `Step 3/8: Approve` after reporting the plan and wait for approval before invoking the model CLI. Before #774 each printed a plan that read exactly like a checkpoint and then delegated in the same turn; because their Review step inspects a diff, that boundary is the only point at which anything can be caught before code exists. Found on a six-worker kyle orchestration wave where three workers described the boundary as a halt it did not have. `--yes` (alias `--auto-approve`) is the only bypass, and it is deliberately flag-only: no `eli5: auto-approve`-style trailer is honored, since a marker in an issue body or commit message is written by the filer rather than the invoker (the #775 hazard, not propagated). `tests/test_delegated_driver_gates.py` pins the gate, the ordering, the escape hatch, and the absence of a trailer bypass in all three drivers.
- No-bypass ELI5 gate (issue #775): `/flow:auto` and `/flow:auto_codex` Step 3 cannot be skipped at all. The `eli5: auto-approve` trailer channel is removed - it was read from the issue body or the HEAD commit message, neither of which the invoker writes, so a single merged commit carrying it disarmed the gate for every run branched from that tip. `--yes` / `--auto-approve` went with it: a flag typed at invocation approves a plan that does not exist yet. Both are still recognized, and refused out loud. `auto-granted` is gone from the Step 3 report vocabulary, since a producible field means a reachable bypass. The fix landed in the vendored `eli5-core` (canonical: cooneycw/eli5-gate) so it propagates rather than staying a CPP-local override, and `tests/test_eli5_gate_not_bypassable.py` pins it across every flow surface. Note the contrast with the delegated drivers above, which still carry an invoker-typed `--yes` for their own Step 3/8 gate.
### Local Qwen Orchestration (Tier 6, optional)

- `/qwen:auto <ISSUE>` - Full issue lifecycle (8 steps, gated at Step 3/8) delegated to a locally hosted Qwen model (Ollama-served, driven through the Qwen Code CLI harness in headless stream-json mode; no cloud API key or per-token cost)
- `/qwen:exec <PROMPT>` - One-shot local Qwen execution in current directory with JSONL monitoring (Seatbelt/Docker sandbox, yolo approval, wall-time budget)
- `/qwen:status` - Check the Ollama server, model presence, network exposure, and Qwen Code harness readiness
- `/qwen:help` - Qwen commands overview, serving-stack recipe, thinking-token guidance, and remote-access setup
- Design notes: same supervisor/implementer split and issue #735 safety machinery as `/codex:auto` (execution fence, sandbox, overrun verification); local-model calibration demands tighter prompts and stricter Claude review, with escalation to `/codex:auto` when the fix loop exhausts. One machine serves the model (Ollama bound to `0.0.0.0:11434`); consumer machines reach it by setting `QWEN_OLLAMA_URL`, which every `/qwen:*` command uses for both status checks and execution (`--openai-base-url $QWEN_OLLAMA_URL/v1`). The original Codex CLI harness (`codex exec --oss`, `QWEN_CODEX_PROFILE`) was retired in issue #745: Codex deleted the chat-completions wire API at v0.95 (a leftover `wire_api = "chat"` provider block hard-errors every Codex run), its `/v1/responses` path hangs on Qwen 3 thinking output (ollama/ollama#18187), and upstream closed remote-Ollama support as not-planned.

### Local Gemma Orchestration (Tier 7, optional)

- `/gemma:auto <ISSUE>` - Full issue lifecycle (8 steps, gated at Step 3/8) delegated to a locally hosted Gemma 4 model (Ollama-served on a GPU box, driven through the OpenCode harness in headless `--format json` mode; no cloud API key or per-token cost)
- `/gemma:exec <PROMPT>` - One-shot local Gemma execution in the current directory with JSONL monitoring (explicit `--dir`, `--auto` approval, wall-time budget)
- `/gemma:status` - Check the Ollama server, model presence and GPU residency, OpenCode harness, provider resolution, the `gemma-implementer` agent profile, and a real tool-calling smoke test
- `/gemma:help` - Gemma commands overview, serving-stack recipe, the native-API rationale, the mechanical-fence design, and remote-access setup
- Design notes (issue #752): the second local lane, added because a second local model is both a faster implementer and a genuinely different second opinion. On the reference hardware (RTX 3090 Ti serving `gemma4:31b-it-qat`) decode runs 25-39 tok/s against the Qwen lane's 10-12, and prefill ~1,390 tok/s against ~86.
- **Native `/api/chat` only.** The provider pins the `ai-sdk-ollama` package, never `@ai-sdk/openai-compatible`. Ollama's `/v1` shim drops streaming `tool_calls` deltas and silently discards tool calls once the system prompt passes ~1,600 tokens (ollama/ollama#14958); OpenCode's agentic system prompt measures ~6,900 tokens, so every `/v1` run would fail as plausible prose with no edits rather than as an error. A short curl probe passes on both paths and proves nothing, so `/gemma:status` Step 4 guards the choice with a real `opencode run` that inherits the full system prompt.
- **Mechanical fence by permission profile, not sandbox.** OpenCode ships no `--sandbox` flag; the `gemma-implementer` agent's `permission` block denies ref-modifying git, all `gh`, deploy/docker/kubectl/terraform, webfetch/websearch, and `external_directory` writes. This is structurally better than the Qwen lane's container: issue #749 forced `/qwen:auto` to disable its Docker sandbox for remote endpoints (a container network namespace cannot reach Tailscale), which is the normal serving case, whereas a config-level rule has no network dependency. The textual execution fence and post-execution overrun verification still run - a rule can block a command, but only prose can tell a model not to follow instructions it reads inside a repo file.
- Configuration ships as `templates/opencode-gemma.json` (provider + agent) and installs to `~/.config/opencode/opencode.json` via `/cpp:init` Tier 7. `baseURL` is the literal `{env:GEMMA_OLLAMA_URL}`, resolved by OpenCode at invocation time, so one config file serves both the serving machine and every consumer machine.
- Operational note: the reference server (proxVMgemma23) shares its GPU claim with other VMs on the host and only one may hold the card, so NOT READY can be a scheduling fact rather than a broken install. Every probe carries `--max-time` so an unavailable box fails fast instead of hanging.
### Security

- `/security:scan` - Full scan: native + external tools
- `/security:quick` - Fast scan: native only (zero deps)
- `/security:deep` - Deep scan: includes git history
- `/security:explain <ID>` - Explain a finding type
### Secrets

- `/secrets:get`, `/secrets:set`, `/secrets:delete`, `/secrets:list` - CRUD operations
- `/secrets:run -- CMD` - Run command with secrets injected as env vars
- `/secrets:validate` - Test credential configuration
- `/secrets:rotate KEY` - Rotate a secret
### Documentation

- `/documentation:pptx [topic]` - Guided PowerPoint creation with diagrams (QA gating; screenshots via the upstream `@playwright/mcp` server)
### Evaluation

- `/evaluate:issue` - 4-phase multi-model evaluation (divergence, reasoning, validation, spec output)
### Second Opinion

- `/second-opinion:start [file] [model] [depth]` - Quick code review via external LLMs
- `/second-opinion:models` - Interactive model/depth selection
### QA

- `/qa:test` - Automated web testing via the upstream `@playwright/mcp` server (single session)
### Browser Sessions

- `/browser:help` - Browser session commands overview
### CLAUDE.md Management

- `/claude-md:lint` - Lint CLAUDE.md for missing CI/CD, Docker, and troubleshooting directives
### Other

- `/cpp:dockers` - Docker container status, health, project linkages
- `/self-improvement:deployment` - Retrospective analysis after failed deploys
- `/cpp:happy-check` - Check happy-cli version (optional)
