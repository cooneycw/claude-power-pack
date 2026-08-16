# Claude Power Pack

## Core Directives

- **NEVER output API keys, passwords, connection strings, or `.env` file contents in responses.** The PostToolUse hook masks terminal output, but your response text is logged before masking applies.
- **Use `make` targets for build/test/deploy operations.** Never run raw `uv run ruff` or `uv run pytest` directly. If a target is missing, add it to the Makefile.
- **Progressive disclosure:** Do NOT auto-load documentation. Read topic-specific files from `docs/skills/` only when the task requires it.
- **Python 3.11+, uv for dependencies.** Each component has its own `pyproject.toml`.
- **When fixing errors, fix BOTH the application code AND the CI/CD process** (Makefile, Dockerfile, `.woodpecker.yml`). Never bypass quality gates.
- Before debugging manually, run `make lint` and `make test` to surface known issues.
- **A test that shells out to a real binary (`git`, `docker`, `gitleaks`, `jq`) MUST guard with `@pytest.mark.skipif(shutil.which("<tool>") is None, ...)`.** The Woodpecker `validate` container (uv:python3.11-slim) ships none of them, so an unguarded test errors the suite and turns CI red even though it passes locally (recurred #451, #489, #577, #716/#717 for `jq`). This is no longer prose alone: `scripts/check-test-binary-guards.py` enforces it (`make binary-guards-check`, part of `make verify`, asserted in `tests/test_test_binary_guards.py`), so the failure is now reproducible on a dev box that HAS git instead of only in CI (#602). It covers the indirect shape too - a test calling a module-level helper that shells out - but NOT a binary called from inside a separately-invoked script under test (e.g. a bash script that itself shells out to `jq`); that transitive case still needs a hand-added skipif. Rare intentional exception: `# binary-guard: allow <reason>` on the `def` or call line (deliberately NOT ruff's `# noqa:` namespace, which ruff itself warns on for an unknown code).
- **A fixture that creates a NEGATIVE condition (a tool absent, a path missing, a capability unavailable) by CONSTRUCTING an environment rather than removing one named thing MUST assert the precondition before exercising the code under test.** `assert shutil.which("git", path=str(stub_path)) is None, "fixture must lack git"` is the shape (#695, #697). The reason is that indirect construction can succeed at something broader than intended - a test proving `--check` fails open without `git` emptied `PATH`, which also removed `ln`/`mkdir`/`readlink`/`bash`, so the script failed for unrelated reasons and the assertions STILL PASSED, because "nothing printed, exit code unchanged" is also what a correct fail-open produces. A fail-open or absence test is one of the few kinds whose passing state carries almost no information; the precondition guard is what separates a real pass from an unfalsifiable one, and it costs one line. Enforced by `scripts/check-negative-fixture-preconditions.py` (`make negative-fixture-check`, part of `make verify`, asserted in `tests/test_negative_fixture_preconditions.py`). Deliberately NOT covered, so the rule is not over-applied: a `PATH` PREPEND (`f"{bindir}:{env['PATH']}"`) adds without removing; `monkeypatch.delenv("X", raising=False)` removes exactly one named thing; and `assert not path.exists()` about what the code PRODUCED is an outcome assertion, not a fixture precondition. Rare intentional exception: `# negative-fixture: allow <reason>`.
- **A fixture must never interpolate an absolute path it does not control (`sys.executable`, anything under pytest's `tmp_path`) into a value the code under test PATTERN-MATCHES.** The path carries the checkout's name into the match, so the assertion's outcome follows where the repo happens to live rather than what the fixture built. `tests/test_test_workers_cap.py` proved a `lint` step never receives the pytest worker cap by building its command from `sys.executable`; `is_test_step()` scans the whole command, so under a flow worktree named `...-issue-697-test-convention-...` the linter classified as a TEST step and the gate went red - meaning every `/flow:auto` run on an issue whose TITLE contains "test" failed on its own branch name, with a message (`assert '7' == 'unset'`) pointing at worker-cap resolution rather than at the collision (#704). Two corollaries, both measured: pytest's own `tmp_path` root is `/tmp/pytest-of-<user>/pytest-<n>/`, so an absolute path under it is no safer than the checkout path; and naming the matched variable in a command (`printf '%s' "$PYTEST_WORKERS"`) matches too. The fix is a value the fixture owns - steps run with `cwd=project_root`, so a RELATIVE name (`./interp`, symlinked to the interpreter) keeps every path out of the string. Pair it with the negative-fixture precondition guard above (`assert not ShellStep(step).is_test_step()`), which is what turns a recurrence into a failure that names its own cause. Not enforced by a script: the general shape (a fixture handing a scanner an input it did not mean to include) is not statically detectable, so this one is prose plus a characterization test (`tests/test_cicd_outcomes.py::TestStepGating::test_path_in_command_matches_by_design`) pinning that the broad scan is deliberate (#621) and must not be narrowed to dodge paths.
- After any fix, verify through the full pipeline: `make verify`.
- Use `/cpp:dockers` to check container status, health, and project linkages.
- **Use single dashes (-) not em dashes (-)** in all markdown, comments, and documentation. Never generate Unicode em dashes (U+2014) or en dashes (U+2013).
- **Never wrap a read-only command in `cd X && ...`.** Name the path instead of moving to it: `git -C <path> status`, an absolute path, or the tool's own path argument. A permission allow rule matches a command PREFIX, so `cd "$(git rev-parse --show-toplevel)" && grep -n foo bar.md` prompts even though `Bash(grep:*)` is allowlisted - the 2026-07-19 retro found EVERY safe-tier prompt in a 138-record census firing this way, with the matching rule already installed. This generalizes #581's bare-invocation discipline from the flow helpers to ordinary commands. The `cd` habit is a defense against the Bash tool's cwd drifting between calls, and that same drift caused the #590/#592 lane bugs and the #595 stale-grep trap - so prefer an explicit path there too, rather than trusting where the shell happens to be.
- **In shared checkouts, characterize branch/repo state with ref-scoped reads only** - `git -C <repo-root>` with full refs, `git show <ref>:<path>`, `git diff <ref1> <ref2>`, `git cat-file -e <ref>:<path>` - never a bare relative pathspec (`git diff ... -- ui/`) and never a working-tree `grep`/file read standing in for a BRANCH's content (#659). The Bash cwd drifts between calls by design, and once it sits in a subdirectory every relative pathspec matches nothing: the empty diff is a SILENT wrong answer, indistinguishable from "no changes", so the failure produces confident false conclusions rather than errors - in the 2026-08-11 damage assessment four such reads agreed with each other and were all wrong, while the lone ref-scoped `git cat-file -e <ref>:<path>` dissented and was correct. Corollary: agreement between measurements sharing a broken assumption is not corroboration - when one measurement dissents from several, investigate the dissenter FIRST. This extends the `cd`-wrapping bullet above from command prefixes to pathspecs; #592/#614/#657 fixed the same disease inside the flow helpers (declared roots, `git -C`, full refs), but ad-hoc measurement commands have no helper guarding them - this directive is that guard.
- **One inventory item per line in CLAUDE.md.** When adding to an inventory entry (the `scripts/` list, component feature lists, CI behavior lists), add a new sub-bullet - never append to an existing line. Git merges at line granularity, so packed single-line lists make every concurrent PR that touches them a manual merge conflict (#501). **The per-item HISTORY does not belong here** (#711): this file loads into every session, and it reached 2.4x Claude Code's ~40,000-char memory-file warning threshold because each fix appended its incident narrative to the always-loaded brief. A `scripts/` entry keeps ONE line naming what the script is; the why-it-exists narrative goes to `docs/scripts.md`, per-command detail to `docs/commands-reference.md`, and a command's own description is never restated here at all - every session already receives it in the skill listing.

## Project Map

Core components and their locations:

- `docs/skills/` - Topic-focused best practices (~3K tokens each). Load on demand.
- `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` - Complete guide (25K tokens). Load via `/cpp:load-best-practices`.
- `ISSUE_DRIVEN_DEVELOPMENT.md` - IDD methodology
- `PROGRESSIVE_DISCLOSURE_GUIDE.md` - Context optimization patterns
- `MCP_TOKEN_AUDIT_CHECKLIST.md` - Token efficiency checklist
- `.specify/` - Spec-Driven Development (specs, plans, tasks, templates)
- `.mcp.json` - Client pointer for the external `second-opinion` MCP server (streamable-http `${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp` - default localhost 8080, per-host override via the `SECOND_OPINION_URL` env var without editing the tracked file, #633; the same variable `mcp-evaluate/src/config.py` reads). Run the server from its own repo (https://github.com/cooneycw/mcp-second-opinion); CPP's `mcp-second-opinion` container + `aws-secrets-agent` sidecar (and the whole Docker MCP runtime) were retired in #469.
- Browser automation - upstream `@playwright/mcp` registered via npx/stdio by `/cpp:init` (no container; the CPP `mcp-playwright-persistent` fork was retired in #423)
- `extras/sequential-thinking/` - Optional: structured reasoning (stdio, npm)
- `lib/creds/` - Secrets management (dotenv/AWS SM, FastAPI UI, audit logging)
- `lib/security/` - Security scanning (native + external tools)
- `lib/cicd/` - CI/CD framework detection, Makefile generation, health/smoke checks, deterministic runner, deployment strategies, Pydantic v2 config validation
  - `ProcessCheck` is a probe UNION, not a port (#620): an entry names exactly one of `port` (ss/lsof), `systemd_user_unit` (`systemctl --user is-active`), `systemd_unit` (`systemctl is-active`) or `pattern` (`pgrep -f`), so a service with no listening socket - a queue worker, a scheduler - can be described as what it is instead of being handed a fabricated port. Exactly-one rather than at-least-one is deliberate: several set would need a silent precedence order, and a field that quietly loses to another is the bug the union fixes. Before it, a port-less entry failed the WHOLE config, which took `verify --baseline` down with it - and since verification is fail-open, a repo with `deploy_verification.enabled: true` deployed green with no gate running at all
  - Health probes fail SOFT per entry (#620) - `CICDConfig.load` drops an individually-invalid `endpoints`/`processes`/`smoke_tests` entry with a `UserWarning` instead of raising, so one malformed probe cannot disable every other probe plus the gate; a structural error outside those lists still raises, having no smaller unit to fall back to
  - CPP dogfoods its own deploy verification (#603) - `.claude/cicd.yml` enables `deploy_verification` with a service-less smoke probe (`python3 -c "import lib.cicd"`), so Step 9 runs `verify --baseline` + `verify` around the #469 no-op deploy on every CPP flow run; and `tests/test_step9_verify_executes.py` EXTRACTS the documented Step-9 invocation pair from auto.md (section-scoped to Step 9 - the third file-global `uv run --project` mention is Step-6 prose, deliberately excluded; exact-pair count asserted, loud failure on doc-shape change) and EXECUTES it against a scaffolded temp project - a regression to the pre-#595 broken shape is a red test, not plausible prose, because execution is the assertion
  - `validate_file` reports unknown keys INSIDE a probe (#620), not just unknown top-level sections - every model is `extra="ignore"`, so `expect_status` for `expected_status` parses fine and leaves a 302 probe comparing against the default 200 with nothing to say so. The audit surface is `python -m lib.cicd validate`; load time stays permissive by design
- `lib/cpp_memory/` - Common-memory client: a **pluggable** fail-open friction-knowledge ledger (issue #472) with three `/cpp:init`-selectable backends behind one `StoreBackend` interface:
  - `md` - best-effort local, no federation; subsumes `.claude/learnings.md`
  - `local-pg` - full SQL dedup, single box, `lib/cpp_memory/docker-compose.yml`
  - `remote-pg` - full dedup, fleet-federated Postgres, `scripts/memories-db-setup.sh`
  - Backend chosen via `CPP_MEMORIES_BACKEND` / step 8d; **federation is a surfaced per-tier property** (only remote-pg shares across VMs)
  - Holds *portable* CPP learnings/infra traps (bucket-2-plus) plus a dedup/rejection ledger and a learnings->GitHub-issue bridge (`--emit-issue-candidate` / `link-issue`, #463)
  - Sightings carry a `harness` tag (`claude`|`codex`) for multi-harness attribution and a `sightings_by_harness` query split (#557); the write/read contract codex-power-pack targets is `docs/contracts/friction-ledger-shared-store.md`
  - Consult-not-push; see `/self-improvement:memory`
- `scripts/` - Shell utilities, one per sub-bullet (add new scripts as their own line, #501); per-script history lives in `docs/scripts.md` (#711):
  - prompt-context
  - worktree-remove - claim-aware worktree removal used by `/flow:auto` Step 7, `/flow:merge` and `/flow:cleanup`
  - gh-pr-merge - layout-aware PR squash-merge used by `/flow:auto` + `/flow:merge`
  - branch-protection - declared branch-protection posture as data (ADR 0004)
  - flow-stale-check - advisory early stale-base detector for `/flow:auto` Step 4/6 + `/flow:finish`
  - flow-worktree-guard - leaked-edit detector; `--strict` BLOCKS at both `/flow:auto` call sites
  - tool-risk-drift - shared permission-risk taxonomy guard (hard gate via `make tool-risk-check`)
  - flow-start-resolve - deterministic `/flow` Step-1 resolver + `--verify` gate
  - flow-live-driver-guard - advisory concurrent-session guard
  - flow-worktree-claim - cross-session OWNERSHIP claim on a flow worktree (a real `git worktree lock`)
  - flow-wave-registry - role -> address registry for multi-session flow waves
  - flow-wave-mailbox - the wave DELIVERY lane - `send`/`read`/`watch`/`list`
  - flow-wave-lexicon - reserved vocabulary for wave STATE TRANSITIONS
  - flow-wave-plan - deterministic wave planner; the ONE dependency parser shared with `/project:next`
  - flow-wave-residuals - executable residual candidate ledger, close-time human promotion gate, and issue-economy metrics
  - project-init - deterministic scaffold planning/apply engine with validated semantic checkpoints
  - flow-finish-gate - the deterministic quality-gate invocation as ONE audited helper
  - hooks
  - drift-detect
  - mcp-drift - orphaned Docker MCP detection + provenance-protected teardown
  - codex-skill-sync - single-source -> per-harness SKILL.md generator
  - eli5-vendor - guard for the canonical->vendored eli5-core link
  - eli5-core-drift - thin shim onto `eli5-vendor.py --upstream`
  - retired-surface-prune - teardown for GENERATED file surfaces CPP retired but left behind in HOME
  - measurement-shape-scan - transcript detector for the #659 cwd-relative measurement trap
  - speckit-tasks-to-issues
  - playwright-desk - lease-desk ledger
  - check-ignored-additions - advisory guard for a file a blanket-ignore rule silently swallowed
  - check-test-binary-guards - gate for the shell-out-binary guard directive
  - skills-check - read-only topic-skill provenance, reference, and managed-install parity gate
  - check-negative-fixture-preconditions - gate for the negative-fixture precondition directive
  - install-drift - read-only host check: installed helpers vs checkout, plus retired marketplace state
  - commands-mirror-sync - drift guard + refresher for out-of-repo command-surface mirrors
  - cpp-commands-link - user-scope command-surface symlinker (the canonical Tier 1)
  - sandbox-phase1-trial - ADR 0002 Phase 1 trial harness (historical record; epic abandoned in #553)
- `templates/` - Makefile, workflow, container templates
- CPP's own `.claude-plugin/` + `plugins/` marketplace lane was retired by issue #662 / ADR 0005. The tiered `/cpp:init` + `/cpp:update` symlink command surface returns as canonical in #663; existing caches migrate with `/plugin uninstall <family>@cpp`.
- `codex/skills/` - Codex SKILL.md skills, the second harness surface (issue #555, companion to codex-power-pack epic cooneycw/codex-power-pack#64): generated `<family>-<cmd>/` skill dirs emitted from the same `.claude/commands/<family>/` single source by `scripts/codex-skill-sync.py`; codex-power-pack vendors this source (pull model, issue #556 / codex-power-pack#75) rather than receiving a push, and CPP's own currency is guarded by the explicit `codex-skills-check` step in `.woodpecker.yml`. Regenerate with `make codex-skills` after any command or referenced-script edit; `make codex-init` installs to `~/.codex/skills/`. Hand-curated skill dirs (no GENERATED marker) are never touched.
- `codex/cpp-memory.md` - Hand-curated Codex `/cpp-memory` prompt (#433) for the common-memory harness, installed to `~/.codex/prompts/cpp-memory.md` by `scripts/install-memory-harness.sh`. Relocated here when the deprecated generated `codex/prompts/` flat surface (#446) was retired at the #556 cutover (superseded by `codex/skills/`, #555).
- `.woodpecker.yml` - Woodpecker CI pipeline (secret-scan, lint, test, typecheck, codex-skills-check, eli5-vendor-check, eli5-upstream-drift (advisory), tool-risk-drift, Dockerfile lint)

## Environment Variables

- `CLAUDE_PROJECT` - Default project for `/project:next` from `~/Projects`. Set in `~/.bashrc`.
- `FLOW_WORKTREE_BASE` - Optional worktree base override (issue #584, ADR 0003). Worktrees default to a VISIBLE sibling in the repo's parent dir (`../<repo>-<branch>`, issue #627); set this (host config, e.g. `~/.bashrc`) to relocate them to `$FLOW_WORKTREE_BASE/<repo>-<branch>` instead. Either way the run rides the git lane (`GIT_LANE=1`). Never set in shipped config beyond the visible-sibling default (PR #527 norm).

## MCP Servers and Secrets

CPP ships **no container runtime** as of #469. The Docker MCP runtime (the `mcp-second-opinion` server, the `aws-secrets-agent` sidecar, all `docker-compose*.yml` files, every `make docker-*` target, and the compose-based deploy path) was retired when `mcp-second-opinion` moved to its own external repo (https://github.com/cooneycw/mcp-second-opinion). The remaining MCP servers are stdio/http and need no CPP-built image.

- **Second opinion (`/second-opinion:*`, `/evaluate:*`):** the server runs from its own external repo (localhost, or a Tailscale host). CPP consumes it as a client - the repo ships a root `.mcp.json` registering `second-opinion` as a streamable-http server at `${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp` (#633): default localhost 8080, overridable per host by exporting `SECOND_OPINION_URL` with the base url (no `/mcp`) - or register at user scope (`claude mcp add second-opinion --transport http --url <url> --scope user`). Start the external server first; see `/cpp:init`.
- **Browser automation:** upstream `@playwright/mcp` registered via npx/stdio by `/cpp:init` (no container; the CPP `mcp-playwright-persistent` fork was retired in #423).
- **Secrets:** CPP stores no application secrets on disk and runs no secrets sidecar. The remaining AWS Secrets Manager consumers fetch **directly** via the AWS SDK/CLI: `essent-ai` (Woodpecker CI keys `WOODPECKER_URL` / `WOODPECKER_API_TOKEN`, consumed by `/flow:auto`, `woodpecker/bootstrap-secrets.py`, and `scripts/setup-woodpecker-cli.sh`; also holds `CPP_MEMORIES_DSN`, the common-memory Postgres DSN used by `lib/cpp_memory` for fleet-wide federation - reference the store host by its Tailscale address). Second-opinion LLM keys (`codex_llm_apikeys`) now live with the external server, not CPP. See `/secrets:*` and `lib/creds/`.
- **Deploy:** `make deploy` is an informative no-op - CPP ships no deployable services.
- **Secret scanning:** `make secret-scan` runs gitleaks locally (native binary or Docker fallback). Config in `.gitleaks.toml` with allowlists for doc/test false positives.
- **Bootstrap checks:** `make bootstrap-check` verifies admin-only prerequisites in `.claude/bootstrap.yaml` (now just `jq`, since the Docker runtime prerequisites were retired).
- **Woodpecker CI** runs on push/PR: secret-scan (gitleaks), lint, test, typecheck, and Dockerfile lint. The image-build / CVE-scan / SBOM / compose-policy / runtime-smoke stages were retired with the container runtime in #469.
- **Drift detection:** `make drift-check` compares host-installed artifacts against repo templates and flags **orphaned Docker MCP servers** - a leftover container, `mcp-<name>:*` image, or `claude`/`codex mcp` registration from a retired server (e.g. a lingering `mcp-second-opinion` or `aws-secrets-agent`) - against the curated `.claude/deprecated-mcps.yaml` list of record (via `scripts/mcp-drift.py`). Since CPP now ships no compose file, the current service set is empty by absence, so a listed server still present on the host is treated as an orphan. Detection is curated-list driven so a user's own custom MCP registration is never flagged (the valid external `second-opinion` registration is intentionally not listed); a **running** container that shares a deprecated name but belongs to an external compose project (or runs a non-CPP image) is also auto-protected by provenance and never torn down (issue #520), so the live external `second-opinion` / `aws-secrets-agent` containers survive `/cpp:update`. Teardown is per-server, user-confirmed, and keeps a newest-image restore point unless prune-all is chosen (run `/cpp:update`, or `python3 scripts/mcp-drift.py --teardown <name>`). See `docs/HOST_MANAGED_ARTIFACTS.md` for full inventory.
- **Reproducible builds:** the remaining container image references (the `mcp-evaluate` Dockerfile and the tool images in `.woodpecker.yml`) are pinned by version tag plus `@sha256:` digest, never `:latest`. `renovate.json` rotates the pinned digests on a weekly schedule so pinning never freezes security updates.

## Commands Reference

Every command's own description is resident in each session's skill listing, so
this section carries only what is NOT derivable from it: the workflow rules, the
non-command CLI surface, and the decisions behind delegated or retired families.
The per-command detail and incident history moved to
`docs/commands-reference.md` (issue #711) - nothing was dropped, only relocated.

### Workflow rules

**Visible worktrees on the git lane (issue #627; native `EnterWorktree` #440
superseded for the default):** `/flow:start` and `/flow:auto` create worktrees
OUTSIDE the repo - a visible sibling of the repo in its parent dir
(`../<repo>-<branch>`), or under `FLOW_WORKTREE_BASE` when set (#584) - via
`git worktree add`, entered with `cd`. The run rides the git lane end-to-end
(`GIT_LANE=1` always) and cleanup uses `git worktree remove` /
`scripts/worktree-remove.sh`; the native `EnterWorktree`/`ExitWorktree` fresh
lane is retired. CPP layers its gate policy on top: the `issue-<N>-<slug>` branch
name (enforced by `flow-start-resolve.sh --verify`), the `/flow:eli5` necessity
gate, the quality gates, and merge/cleanup discipline. The `/flow:*` commands
live under the permanent source of truth at `.claude/commands/flow/*`.
`/flow:repair` (`scripts/flow-helpers-install.sh`) installs the helper family to
`~/.claude/scripts/`, the stable path the #581 allowlist rules match.

**Worktree path-resolution rule (issue #486):** resolve every `Write`/`Edit` path
from the active worktree root - `git rev-parse --show-toplevel` - or use a plain
relative path from the session cwd; **never hand-build an absolute worktree
path**, which has been observed to land the edit in the MAIN repo working tree
instead of the worktree. `/flow:auto` Steps 4/6 run
`scripts/flow-worktree-guard.sh --strict` - **blocking since #576**: exit 3 is a
STOP, so the trap stops the run instead of being narrated past. Freshness
downgrades keep it from crying wolf (#536, #573, #576).

**Concurrent flow sessions (issue #597):** CPP encourages parallel `/flow`
sessions, so a run stakes a **claim** on its checkout
(`scripts/flow-worktree-claim.sh`, a real `git worktree lock`) during the Step-1
verify gate, and three guards read it: Step 1 refuses to start on an issue
another LIVE session holds (`CLAIM=held` -> `CONFIRM_REQUIRED=1`),
`worktree-remove.sh` refuses (exit 4) to delete a worktree claimed by a live
sibling, and Step 4 re-runs the #503 live-driver guard immediately before the
first edit. Step 9 skips `make deploy` when `.claude/deploy.log` already records
a SUCCESSFUL deploy of the current HEAD sha. An owner that is gone reads as
`stale` and is taken over automatically; `--steal` is the documented break-glass.

**Standalone skill extractions (issue #443):** skills with standalone value are
extracted to their own public plugin repos, and improvement issues for an
extracted skill are filed in THAT repo, not here (the learnings->issue bridge,
#463, routes there too). CPP stays a consumer: it vendors the extracted skill's
canonical core between marker comments and layers its /flow wiring outside them.
First extraction: the `/flow:eli5` necessity gate ->
https://github.com/cooneycw/eli5-gate (core markers `eli5-core:begin`/`end` in
`.claude/commands/flow/eli5.md`), guarded on both sides by `scripts/eli5-vendor.py`
(offline manifest, hard gate) and `scripts/eli5-core-drift.sh` (live fetch,
fail-open). Reconcile drift by editing the canonical repo first, then
`make eli5-revendor`.

### Non-command CLI surface

- `python -m lib.cicd validate` - Validate .claude/cicd.yml with fix suggestions (Pydantic v2)
- `python -m lib.cicd validate --schema` - Generate JSON Schema for IDE autocompletion
- `python -m lib.cicd run --plan <name>` - Execute CI/CD plan deterministically (finish, check, deploy)
  - Test steps resolve `PYTEST_WORKERS` from step env, host `PYTEST_WORKERS`, then host `CPP_TEST_WORKERS`, and log the effective cap and source (#640)
- `python -m lib.cicd verify --baseline` - Capture pre-deploy health/smoke baseline
- `python -m lib.cicd verify` - Verify post-deploy against baseline (exit 1 = ROLLBACK)
  - Invocation contract for every `lib.cicd` call in a command doc: `PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.cicd ...` - `PYTHONPATH` names the PARENT of `lib/` (or `-m lib.cicd` cannot resolve) and `uv` supplies the pinned 3.11+ interpreter plus pydantic. Bare `python3` with `PYTHONPATH` pointed inside `lib/` fails on both counts; it silently disabled deploy verification for months (#430 fixed Step 6, #595 fixed the Step 9 / `/flow:deploy` / `/cicd:verify` verify calls, pinned by `tests/test_cicd_verify_invocation.py`). The same broken shape still rides ~40 non-`verify` `lib.cicd` lines in the `cicd`/`cpp`/`codex`/`project` families - a known latent bug awaiting its own sweep, not a covered case
- `python -m lib.cicd.bootstrap check` - Check admin-only bootstrap dependencies (config: `.claude/bootstrap.yaml`)

### Family decisions and delegations

- `/project:next` - Decision policy delegated to the shared behavioral contract (#636): classification/ranking/top-action come VERBATIM from codex-power-pack's engine (`scripts/project-next.py --json`, contract pinned v1.3 with a runtime version check that flags mismatch in the report) when a CxPP checkout is found; CPP keeps collection notes + rendering only. No engine -> the prompt policy runs as the LABELED non-authoritative fallback ("decision policy: CPP fallback"). Pinned by tests/test_project_next_contract.py incl. a fixture-backed dogfood that FAILS (never skips) on a broken engine when a checkout is present

`/project:init` delegates config scaffolding (CLAUDE.md, skills, hooks) to Claude
Code's native `/init` interview rather than hand-rolling a fixed template, then
runs `/claude-md:lint` to overlay CPP's CI/CD governance directives. CPP keeps the
zero-to-GitHub-repo orchestration native `/init` does not provide: directory +
framework scaffold, `git init` and repo create/push, Makefile/CI wiring
(`lib/cicd`), CPP toolkit install, and `.specify/` structure (epic #417 Phase A,
mirrors the `/security` #438 and hooks #439 defer-the-commodity-half moves).

- `/spec:adopt` - **(supported)** Install the official GitHub spec-kit CLI and scaffold it into the project (`specify init --here --ai claude`); then author with the `/speckit-*` skills and ship with `/flow:auto`. Turn `tasks.md` into GitHub issues with `scripts/speckit-tasks-to-issues.sh` (gh-CLI, no github-mcp-server). Per-project, always latest upstream. The `specify` CLI installs on first `/spec:adopt` use, or up front via `/cpp:init` / `/cpp:update`.

**Spec-driven dev = official spec-kit plugin + `/flow:auto`.** CPP's home-grown pipeline (`/spec:create`, `/spec:sync`, `/spec:status`, `/spec:init`, backed by `lib/spec_bridge`) was **retired** in favor of upstream spec-kit (epic #417 Phase A, decision on #418).

**Scaffolding backend:** GitHub Issues (driven by the `flow-auto` skillset) is the only supported scaffolding/issue backend. Wiki.js and Plane are out of scope and are not part of CPP.

**Skills:** the `/skills:*` wrapper was retired (issue #437) - it is fully absorbed
by the native Claude Code ecosystem. Use these instead:
- `npx skills find|add|list|update <...>` - Discover/install/manage skills from [skills.sh](https://skills.sh/)
- `/plugin` - Browse and install from the plugin marketplace
- Auto-loading `.claude/skills` + `/reload-skills` - Project-local skills, no wrapper needed

**Installation:** the tiered `/cpp:init` install is CANONICAL (#663, on the
marketplace retirement #662 / ADR 0005) - Tier 1 symlinks the command surface so
the executed command text follows `git pull` atomically, and `/cpp:update` is the
ONE update verb with no package cache to reconcile. Hosts still carrying the
retired cached families should uninstall each with `/plugin uninstall <family>@cpp`.
`/cpp:init` / `/cpp:update` also install and refresh the non-command infra; see
`README.md`, `docs/HOST_MANAGED_ARTIFACTS.md` and `docs/commands-reference.md`.

**Friction retro:** `/self-improvement:retro` runs the grill-me cycle over the
always-on capture buffer (`scripts/friction-log.sh` -> `.claude/friction.jsonl`,
woven into `/flow:auto` + `/flow:merge`); the local ledger is `.claude/learnings.md`
and portable knowledge delegates to `/self-improvement:memory` (#433).

## Makefile Integration

Flow commands use Makefile targets as the canonical build interface:

- `/flow:check` and `/flow:finish` use `python -m lib.cicd run --plan finish` (deterministic runner) with fallback to `make lint` / `make test` / `make typecheck` - the plan and the fallback carry the same targets the CI templates run (#617)
- `/flow:deploy` uses `python -m lib.cicd run --plan deploy` (deterministic runner) with fallback to `make deploy` + post-deploy health/smoke
- `/flow:auto` runs `make update_docs` after implement, verifies CI after merge, then `make deploy`
- `/flow:doctor` reports which standard targets are available
- Deploy metadata in `.claude/deploy.yaml` (optional, created manually when needed)
  - `mode: external` - deploy runs out of band (host timer / CI on origin/main); `/flow:auto` Step 9 and `/flow:deploy` skip the inline `make deploy` rather than staging a throwaway per-worktree compose stack (#535)
  - `compose_project_name: <name>` - pins `COMPOSE_PROJECT_NAME` so docker compose never derives it from a worktree/tmp directory basename and collides with fixed prod `container_name` values or the published port; defaults to the canonical primary-checkout name when unset. Read by `make deploy` (#535) AND emitted run-wide in the `flow-start-resolve` contract so every compose step in a flow worktree inherits it (#626)
- Deploy history logged to `.claude/deploy.log`
- Starter template at `templates/Makefile.example`

## Security

Security is split into two complementary halves. **Semantic** code-vulnerability
review - SQL injection, XSS, broken authorization, insecure credential handling -
is handled by Claude Code's native **`/security-review`** command and its GitHub
Action; CPP defers to it and does not duplicate it. CPP's `/security:*` commands
and `lib/security` own the **deterministic** complement: secret scanning
(gitleaks + native patterns), git-history secret scanning, dependency CVE audits
(`pip-audit`, `npm audit`), and the blocking gate. See `lib/security/README.md`.

- **Destructive commands** (force push to main, `rm -rf /`, disk formatting, etc.) are blocked by Claude Code's native destructive-git auto-blocking and OS sandbox - the custom PreToolUse dangerous-command hook was retired (issue #439) as redundant.
- **PostToolUse hook** masks secrets in Bash/Read output (connection strings, API keys, env vars). Retained because native tooling blocks credential *reads* but does not *mask* secrets that surface in output.
- **PermissionRequest hook** (`scripts/hook-permission-census.sh`) is an observe-only, fail-open permission-prompt census: it fires when a permission dialog is shown, derives a narrowest allow-rule candidate plus a risk tier (`READONLY-*`/`WRITE-LOCAL` -> allow candidate; `DESTRUCTIVE`/`CODE-EXEC`/net -> recorded but no candidate), and appends a `permission-prompt` record to the project's `.claude/friction.jsonl` for `/self-improvement:retro`. It captures the one friction class the model cannot observe (issue #482). Inherently-interactive tools (`AskUserQuestion`, `Skill`, `EnterPlanMode`, `ExitPlanMode`) are user-interaction dialogs, not permission friction, so they are skipped entirely rather than recorded as noise (issue #542). Registered user-level in `~/.claude/settings.json` (user-confirmed) by `/cpp:init` and `/cpp:update` Step 7.6 - never emits a permission decision.
- **Never-allowlist policy for the census candidate** (issue #598): a SAFE tier is necessary but not sufficient for a `fix`. Two classes are withheld even when read-only, because `/self-improvement:retro` Step 4 tells the retro to TRUST the `fix` field - so a forbidden rule emitted there is a rule that gets installed. (1) **File-dumpers** (`cat`, `head`, `tail`, `less`, `more`, `tac`, `nl`, `strings`, `xxd`, `od`, `hexdump`, `base64`) - an allow rule defeats the PostToolUse masking hook on a secret file, and `head -20 .env` leaks exactly as `cat .env` does; `Bash(head:*)`/`Bash(tail:*)` were dropped from `templates/claude-settings-permissions.json` in the same change so the shipped allowlist and the census agree (the union-merge only ADDS, so a box that merged an earlier template must drop them by hand). (2) **Bare tool namespaces** - `Bash(git:*)` silently permits `git push` and `git reset --hard`, and was emitted whenever a flag preceded the verb (`git -C /path status`); the candidate is now withheld rather than widened, which is also the honest answer since allow rules match a command PREFIX and no narrow rule can match a flag-bearing invocation. The risk TIER is still recorded truthfully in both cases - only the rule is withheld. `NO_ALLOW_CANDIDATE` / `SUBCOMMAND_REQUIRED` in the hook, pinned by `tests/test_hook_permission_census.py`.
- **SessionStart pending-retro reminder** (`scripts/hook-pending-retro.sh`) is an OPT-IN, fail-open, read-only reminder: when registered, it prints ONE advisory line at session open counting pending `.claude/friction.jsonl` signals (actionable vs the bulk permission-prompt census, separately) plus uncodified `Status: proposed` learnings, and points at `/self-improvement:retro`. It only SURFACES - never codifies, never blocks - and is silent when nothing is pending. Default OFF: deliberately NOT shipped in `.claude/hooks.json` (which `/cpp:init` copies into projects), so it never turns itself on; registered user-level in `~/.claude/settings.json` only on explicit opt-in (default N) by `/cpp:init` and `/cpp:update` Step 7.7 (issue #530).
  - **Second advisory: helper drift + retired marketplace state** (#622/#662) - the same hook runs `scripts/install-drift.sh --quiet`: it warns when installed `~/.claude/scripts/*.sh` helpers differ from the checkout and also names retired CPP cache families pending `/plugin uninstall <family>@cpp`. Session open matters for the helper half because learning that installed code is stale before acting avoids re-diagnosing an already-fixed bug and filing a duplicate, the flow:auto #65 failure that motivated #622. It is independent of the retro reminder, fail-open, and suppressible with `CPP_HOOK_SKIP_INSTALL_DRIFT=1`; stale helpers are real `drift`, while migration-only state is non-failing `skipped`.
- **Hooks configured in** `.claude/hooks.json` (SessionStart staleness + PostToolUse project-level) and `~/.claude/settings.json` (PermissionRequest census + opt-in SessionStart pending-retro reminder, user-level); the masking hook ships through `.claude/hooks.json` and the host install path
- `/flow:finish` and `/flow:deploy` run the deterministic security scan (`lib/security`) as a quality gate
- CRITICAL findings block gates; HIGH findings produce warnings
- Configure gating in `.claude/security.yml` (optional, created by `/security:scan` when needed)
- For **semantic** code review (SQLi/XSS/authz/insecure handling), run native `/security-review` - not a CPP command
- **Branch-protection posture** (issue #577, ADR 0004): `main` requires the Woodpecker PR pipeline as a required status check (`ci/woodpecker/pr/woodpecker`, `strict: true`); required reviews stay at 0 and `enforce_admins` stays off. The posture is declared in `.claude/branch-protection.json` and applied/checked with `scripts/branch-protection.sh` (`make branch-protection-check` / `-apply`). Reviews are 0 by choice: on a solo repo a review requirement forces `--admin` on every merge, and `--admin` bypasses the CI check at the same time - the stricter-sounding posture would enforce strictly less. `enforce_admins` is off so a check that never reports (skipped pipeline, renamed context) leaves the owner one documented break-glass (`gh-pr-merge.sh --admin`) instead of a permanently unmergeable PR; the automation is what is prevented from reaching for it.
- **User-level flow allowlist** (`templates/claude-settings-permissions.json`) auto-approves the read-only git/gh plumbing that `/flow:*` runs, plus the audited flow helper-script family at its stable `~/.claude/scripts/` path (flow-start-resolve, flow-stale-check, flow-worktree-guard, flow-live-driver-guard, gh-pr-merge, worktree-remove - issue #581, invoked BARE so the prefix rules match); raw shipping actions (`git push`, `gh pr create`) and `cat` are deliberately excluded so gates and secret-read prompts stay intact. Merged via `/cpp:init` or `/cpp:update` Step 7.6; scripts re-linked by `/cpp:update` Step 5b; checked by `/flow:doctor`. Rationale: `templates/claude-settings-permissions.md`

## On-Demand Documentation

Load topic-specific skills instead of the full guide (88-92% token savings):

- Context efficiency, session management, MCP optimization, skills patterns
- Hooks/automation, spec-driven dev, issue-driven dev, CLAUDE.md config
- Code quality, Python packaging, CI/CD verification, documentation/diagrams

**Commands:** `/cpp:load-best-practices` (full 25K guide), `/cpp:load-mcp-docs` (MCP server docs)

## Secrets Management

Tiered: dotenv-global (`~/.config/claude-power-pack/secrets/`) -> env-file -> AWS Secrets Manager. Features: project identity (git-based), bundle API, secret injection (`creds run`), FastAPI web UI, audit logging, IAM isolation, output masking. Configure in `.claude/secrets.yml` (optional, created manually when needed).

## Version

Current version: 7.4.0
