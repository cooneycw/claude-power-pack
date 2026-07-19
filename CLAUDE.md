# Claude Power Pack

## Core Directives

- **NEVER output API keys, passwords, connection strings, or `.env` file contents in responses.** The PostToolUse hook masks terminal output, but your response text is logged before masking applies.
- **Use `make` targets for build/test/deploy operations.** Never run raw `uv run ruff` or `uv run pytest` directly. If a target is missing, add it to the Makefile.
- **Progressive disclosure:** Do NOT auto-load documentation. Read topic-specific files from `docs/skills/` only when the task requires it.
- **Python 3.11+, uv for dependencies.** Each component has its own `pyproject.toml`.
- **When fixing errors, fix BOTH the application code AND the CI/CD process** (Makefile, Dockerfile, `.woodpecker.yml`). Never bypass quality gates.
- Before debugging manually, run `make lint` and `make test` to surface known issues.
- **A test that shells out to a real binary (`git`, `docker`, `gitleaks`) MUST guard with `@pytest.mark.skipif(shutil.which("<tool>") is None, ...)`.** The Woodpecker `validate` container (uv:python3.11-slim) ships none of them, so an unguarded test errors the suite and turns CI red even though it passes locally (recurred #451, #489, #577). This is no longer prose alone: `scripts/check-test-binary-guards.py` enforces it (`make binary-guards-check`, part of `make verify`, asserted in `tests/test_test_binary_guards.py`), so the failure is now reproducible on a dev box that HAS git instead of only in CI (#602). It covers the indirect shape too - a test calling a module-level helper that shells out. Rare intentional exception: `# binary-guard: allow <reason>` on the `def` or call line (deliberately NOT ruff's `# noqa:` namespace, which ruff itself warns on for an unknown code).
- After any fix, verify through the full pipeline: `make verify`.
- Use `/cpp:dockers` to check container status, health, and project linkages.
- **Use single dashes (-) not em dashes (-)** in all markdown, comments, and documentation. Never generate Unicode em dashes (U+2014) or en dashes (U+2013).
- **Never wrap a read-only command in `cd X && ...`.** Name the path instead of moving to it: `git -C <path> status`, an absolute path, or the tool's own path argument. A permission allow rule matches a command PREFIX, so `cd "$(git rev-parse --show-toplevel)" && grep -n foo bar.md` prompts even though `Bash(grep:*)` is allowlisted - the 2026-07-19 retro found EVERY safe-tier prompt in a 138-record census firing this way, with the matching rule already installed. This generalizes #581's bare-invocation discipline from the flow helpers to ordinary commands. The `cd` habit is a defense against the Bash tool's cwd drifting between calls, and that same drift caused the #590/#592 lane bugs and the #595 stale-grep trap - so prefer an explicit path there too, rather than trusting where the shell happens to be.
- **One inventory item per line in CLAUDE.md.** When adding to an inventory entry (the `scripts/` list, component feature lists, CI behavior lists), add a new sub-bullet - never append to an existing line. Git merges at line granularity, so packed single-line lists make every concurrent PR that touches them a manual merge conflict (#501).

## Project Map

Core components and their locations:

- `docs/skills/` - Topic-focused best practices (~3K tokens each). Load on demand.
- `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md` - Complete guide (25K tokens). Load via `/cpp:load-best-practices`.
- `ISSUE_DRIVEN_DEVELOPMENT.md` - IDD methodology
- `PROGRESSIVE_DISCLOSURE_GUIDE.md` - Context optimization patterns
- `MCP_TOKEN_AUDIT_CHECKLIST.md` - Token efficiency checklist
- `.specify/` - Spec-Driven Development (specs, plans, tasks, templates)
- `.mcp.json` - Client pointer for the external `second-opinion` MCP server (streamable-http `127.0.0.1:8080/mcp`). Run the server from its own repo (https://github.com/cooneycw/mcp-second-opinion); CPP's `mcp-second-opinion` container + `aws-secrets-agent` sidecar (and the whole Docker MCP runtime) were retired in #469.
- Browser automation - upstream `@playwright/mcp` registered via npx/stdio by `/cpp:init` (no container; the CPP `mcp-playwright-persistent` fork was retired in #423)
- `extras/sequential-thinking/` - Optional: structured reasoning (stdio, npm)
- `lib/creds/` - Secrets management (dotenv/AWS SM, FastAPI UI, audit logging)
- `lib/security/` - Security scanning (native + external tools)
- `lib/cicd/` - CI/CD framework detection, Makefile generation, health/smoke checks, deterministic runner, deployment strategies, Pydantic v2 config validation
- `lib/cpp_memory/` - Common-memory client: a **pluggable** fail-open friction-knowledge ledger (issue #472) with three `/cpp:init`-selectable backends behind one `StoreBackend` interface:
  - `md` - best-effort local, no federation; subsumes `.claude/learnings.md`
  - `local-pg` - full SQL dedup, single box, `lib/cpp_memory/docker-compose.yml`
  - `remote-pg` - full dedup, fleet-federated Postgres, `scripts/memories-db-setup.sh`
  - Backend chosen via `CPP_MEMORIES_BACKEND` / step 8d; **federation is a surfaced per-tier property** (only remote-pg shares across VMs)
  - Holds *portable* CPP learnings/infra traps (bucket-2-plus) plus a dedup/rejection ledger and a learnings->GitHub-issue bridge (`--emit-issue-candidate` / `link-issue`, #463)
  - Sightings carry a `harness` tag (`claude`|`codex`) for multi-harness attribution and a `sightings_by_harness` query split (#557); the write/read contract codex-power-pack targets is `docs/contracts/friction-ledger-shared-store.md`
  - Consult-not-push; see `/self-improvement:memory`
- `scripts/` - Shell utilities, one per sub-bullet (add new scripts as their own line, #501):
  - prompt-context
  - worktree-remove
  - gh-pr-merge - layout-aware PR squash-merge used by `/flow:auto` + `/flow:merge`; polls mergeability to wait out a transient `UNKNOWN` right after push (#485); bounded refetch+retry when the squash fails on `Base branch was modified` (sibling merge race, #502); opt-in `--admin` flag plus a single admin-gated auto-retry when a squash is rejected by branch protection on an owner merge (#517)
  - gh-pr-merge `--admin` narrowing + required-check wait (#577, ADR 0004) - before the squash it resolves the BASE branch's required status-check contexts and polls the PR head until they are green (bounded, `GH_PR_MERGE_CHECK_ATTEMPTS` x `GH_PR_MERGE_CHECK_DELAY`); a red required check, and one that never reports, are hard stops. A required-check block is EXCLUDED from the #517 `--admin` auto-retry - auto-overriding it would defeat the required check on every run - while a review block (#517's actual case, and #579's) is unchanged; an explicit `--admin` from the caller still skips the wait, the documented break-glass
  - branch-protection - declared branch-protection posture as data (#577, ADR 0004): `.claude/branch-protection.json` holds the posture, `check` (default) normalizes live protection and diffs it (exit 1 on drift), `--apply` PUTs it idempotently, `--show` prints the normalized live view; `make branch-protection-check|apply|show`. Deliberately NOT a CI gate - reading protection needs an admin-scoped token the pipeline does not have
  - flow-stale-check - advisory early stale-base detector for `/flow:auto` Step 4/6 + `/flow:finish` (#473)
  - flow-worktree-guard - leaked-edit detector: warns when a `/flow:auto` edit landed in the MAIN tree instead of the worktree (#486)
  - flow-worktree-guard `--strict` - BLOCKING at both `/flow:auto` call sites (Step 4 implement, Step 6 pre-commit) since #576: exit 3 is a STOP, because a live leak means every further edit compounds and the commit about to be made does not contain the work. Strict failure is gated on FRESHNESS (`FLOW_LEAK_FRESH_MIN`, default 30m) in BOTH branches - the #573 total-leak check and, new in #576, the overlap check - so pre-existing uncommitted dirt in main on a shared file the run also edits (CLAUDE.md, a template) warns without stopping the run; only an edit written to main DURING the run blocks
  - tool-risk-drift - shared permission-risk taxonomy guard (#495, wired in #576): checks that the safety-critical `DESTRUCTIVE_TOKENS` and `CODE_EXEC` sets are identical between the canonical `scripts/classify-tool-risk.py` and the copy vendored inline in `scripts/hook-permission-census.sh`, so a command one classifier calls dangerous can never be emitted as an allow-rule candidate by the other. Advisory by default; `--strict` exits 1 on drift and is a HARD gate (`make tool-risk-check`, the `tool-risk-drift` step in `.woodpecker.yml`, pinned by `tests/test_tool_risk_drift.py`). Non-safety sets (task-runner, dual-use-net) may differ benignly and are deliberately not guarded
  - flow-start-resolve - deterministic `/flow` Step-1 resolver + `--verify` gate (#581): target-repo resolution (#578), issue fetch + state check, issue-anchored branch derivation, existing-work triage (`current-branch|fresh|resume|remote-pickup|cross-repo`), wraps the #503 live-driver guard + shipped-PR hazard, performs git-lane worktree creation (honoring `FLOW_WORKTREE_BASE`, #584), and emits a `key=value` contract - extracts the compound Step-1 bash the permission matcher could never auto-allow
  - flow-start-resolve `--session-cwd` - the session cwd is DECLARED, not inferred (#592): the Bash tool's cwd persists across calls and drifts on any earlier `cd`, while `EnterWorktree` acts on the session cwd, which never moves - so `CROSS_REPO`/`GIT_LANE` (and, with no PROJECT arg, `TARGET_REPO` itself) are resolved from the path `auto.md`/`start.md` pass verbatim. Omitting it emits `SESSION_CWD_INFERRED=1` and fails closed to `GIT_LANE=1`, since the git lane is correct in every case while a wrong `GIT_LANE=0` points `EnterWorktree` at the wrong repo - or at none
  - flow-live-driver-guard - advisory concurrent-session guard (#503): warns when a worktree's dirty files were modified within the freshness window, the signature of another live session mid-implementation; wrapped by flow-start-resolve on the resume lane, and re-run at `/flow:auto` Step 4 before the first edit (#597) because a single Step-1 check goes stale across the analysis + ELI5 pause
  - flow-worktree-claim - cross-session OWNERSHIP claim on a flow worktree (#597), the half #503 could not cover: the live-driver guard protects a session ENTERING a worktree, but nothing protected an active worktree from being REMOVED by a sibling session, whose Step-7 cleanup deleted an issue-N checkout by name and destroyed uncommitted work with no signal but the user noticing. Rides git's own `git worktree lock --reason "flow-claim issue=N pid=... session=... host=... ts=..."`, so the claim is a real barrier (`git worktree remove --force` refuses a locked worktree) rather than an advisory note, and is readable from `git worktree list --porcelain`. `claim`/`check`/`release` verbs; ownership is pid + session, liveness is `kill -0` trusted only when the recorded host matches, and a claim whose owner is gone is STALE and auto-taken-over so the mechanism can never wedge a repo. A lock this family did not write is FOREIGN and never stolen. Staked in `flow-start-resolve.sh --verify` - the only hook point running INSIDE the worktree on every lane, since the native EnterWorktree lane creates the checkout after resolve mode returns - and read by resolve mode via `check --issue N` BEFORE any worktree is created, so two sessions handed the same issue stop instead of racing. Fail-open everywhere except the case it exists for: claiming against a live owner exits 1
  - worktree-remove `--steal` + claim owner check (#597) - refuses with exit 4 to remove a worktree claimed by another LIVE session (printing the owning pid/session), releases a self-owned or stale claim and proceeds otherwise, and takes `--steal` as the deliberate override. One change covers `/flow:auto` Step 7, `/flow:merge` and `/flow:cleanup`, since all three route removal through this script
  - hooks
  - drift-detect
  - mcp-drift
  - plugin-sync - byte-identical drift guard keeping every packaged family plugin in sync with its command source (#477/#478) plus per-family extra artifacts such as the secrets masking-hook script (#479); the B1 plugin-flow-sync shim was retired in B4 (#480)
  - codex-skill-sync - single-source -> per-harness SKILL.md generator (#555, CxPP epic cooneycw/codex-power-pack#64 story B1): emits checked-in per-command Codex skill dirs under `codex/skills/<family>-<cmd>/` (frontmatter name/description with front-loaded trigger words, Codex harness-adaptations block for detected Claude-only constructs, long bodies split to `reference.md`, referenced helper scripts bundled byte-identical); `--check` drift gate (pinned by tests/test_codex_skill_sync.py AND an explicit `codex-skills-check` step in `.woodpecker.yml`, #556), `--write` regen, `--install` copies to `~/.codex/skills/` and prunes managed orphans there so a dropped skill stops loading (#575; wired into `/cpp:init` Tier 5e and `/cpp:update` Step 7.9, which before #575 invoked it nowhere); editing any bundled `scripts/*` requires a `--write` re-run. Superseded the deprecated flat `codex/prompts/` surface + its `codex-prompt-sync.py` generator, both retired at the #556 cutover
  - eli5-vendor - guard for the canonical->vendored eli5-core link (#591): `check` (default) verifies the vendored core against the sha256 pinned in `.claude/eli5-vendor.json` - offline, stdlib-only, a HARD gate (`make eli5-check`, `eli5-vendor-check` step in `.woodpecker.yml`); `--upstream` live-fetches cooneycw/eli5-gate and diffs - advisory + fail-open (`make eli5-drift`, `eli5-upstream-drift` step, `failure: ignore`); `--revendor` re-fetches the core, replaces it in place and re-pins the manifest (`make eli5-revendor`). The two halves are complementary: a manifest cannot notice that UPSTREAM moved, and a live fetch cannot run offline
  - eli5-core-drift - thin shim onto `eli5-vendor.py --upstream`, kept so existing references resolve to one implementation (#591)
  - retired-surface-prune - teardown for GENERATED file surfaces CPP retired but left behind in HOME (#575): curated by `.claude/retired-surfaces.yaml` (the list of record, sibling to `deprecated-mcps.yaml`) AND gated on the GENERATED marker, so hand-authored files (`~/.codex/prompts/cpp-memory.md`) and the user's own skills are preserved; `--check`/`--json`/`--plan` are read-only, `--prune NAME` MOVES owned items to a timestamped `<path>-retired-<date>` sibling rather than deleting them; wired into `/cpp:update` Step 7.9, per-surface and user-confirmed
  - speckit-tasks-to-issues
  - playwright-desk - lease-desk ledger
  - check-ignored-additions - advisory guard warning when a blanket-ignore rule silently swallowed a file the repo should track; skips a short allow-list of files git-ignored by design (env-only `.claude/` runtime state such as `settings.local.json`/`friction.jsonl`) so it never cries wolf on them (#504)
  - check-test-binary-guards - gate for the "guard tests that shell out to `git`/`docker`/`gitleaks`" core directive (#602), which had failed three times as prose (#451, #489, #577) because it is invisible locally - the dev box HAS git, so only a red pipeline could ever report it. Stdlib-only `ast` walk over `tests/`: flags any `test_` reaching a guarded binary through a statically resolvable `subprocess`/`os.system` call, DIRECTLY or transitively via a module-level helper, without a matching `shutil.which` guard (decorator, module alias, class marker, `pytestmark`, or in-body `pytest.skip`). A dynamic argv is deliberately unresolved - the gate is a floor for the shape that has actually failed, not proof of total coverage. `# binary-guard: allow <reason>` is the escape. `make binary-guards-check`, folded into `make verify`, and asserted by `tests/test_test_binary_guards.py` so it also runs in the CI `validate` step it defends
  - commands-mirror-sync - drift guard + refresher for hosts serving the command surface from an out-of-repo byte-copy of `.claude/commands/` (e.g. `~/Projects/.claude/commands`) instead of `/plugin` installs; `--check` reports drift, `--write` refreshes (prune + copy); wired into `/cpp:update` Step 7.8, opt-in and fail-open (#582)
  - sandbox-phase1-trial - ADR 0002 Phase 1 empirical trial harness (#548): runs the E1-E6 sandbox exit-bar checks in a throwaway, project-scoped trial (nested `claude -p` write-containment probes + a `bwrap` ro-bind primitive); never touches `~/.claude/settings.json`. Historical record only: the sandbox epic (#541) was abandoned (#553, ADR 0002 Rejected) after live enablement broke bash on the bwrap/symlink interaction
- `templates/` - Makefile, workflow, container templates
- `.claude-plugin/marketplace.json` - Plugin-marketplace manifest (marketplace name `cpp`) listing CPP's per-family plugins. Install path: `/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install <family>@cpp` (ADR 0001, epic #417 Phase B).
- `plugins/` - Per-family Claude Code plugins. Phase B2 (#478) packages every surviving family (15 plugins, `browser` through `self-improvement`): byte-identical copies of `.claude/commands/<family>/*.md` (the single source of truth, ADR 0001 section 5), kept honest by `scripts/plugin-sync.sh --check` and regenerated with `--write` after any command edit. Phase B3 (#479) adds bundled hooks + MCP pointers: `secrets` ships the PostToolUse masking hook (plugin-local script via `${CLAUDE_PLUGIN_ROOT}`) and `second-opinion` ships its `.mcp.json` client pointer (matches the repo-root one). The `flow` plugin bundles its helper family (`plugins/flow/scripts/`, #590) and `/flow:repair` installs it to `~/.claude/scripts/` so the #581 allowlist rules keep matching. The `cpp` plugin ships help/meta plus the cross-cutting utilities folded in from the loose top-level commands (`/cpp:dockers`, `/cpp:happy-check`, `/cpp:load-best-practices` with the bundled 25K guide, `/cpp:load-mcp-docs`; issue #582, ADR 0001 amendment) - the init/update/status installer stays repo-local. Phase B4 (#480) proved parity and retired the dual surface: the global-skill mirror, `flow-skill-sync.py`, `skill-drift.py`, and `.claude/deprecated-skills.yaml` are gone. Phase B5 (#481) cut the docs over to the `/plugin` install path (`/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install <family>@cpp`); `/cpp:init` / `/cpp:update` remain only for the non-plugin infra a plugin cannot deliver.
- `codex/skills/` - Codex SKILL.md skills, the second harness surface (issue #555, companion to codex-power-pack epic cooneycw/codex-power-pack#64): generated `<family>-<cmd>/` skill dirs emitted from the same `.claude/commands/<family>/` single source by `scripts/codex-skill-sync.py`; codex-power-pack vendors this source (pull model, issue #556 / codex-power-pack#75) rather than receiving a push, and CPP's own currency is guarded by the explicit `codex-skills-check` step in `.woodpecker.yml`. Regenerate with `make codex-skills` after any command or referenced-script edit; `make codex-init` installs to `~/.codex/skills/`. Hand-curated skill dirs (no GENERATED marker) are never touched.
- `codex/cpp-memory.md` - Hand-curated Codex `/cpp-memory` prompt (#433) for the common-memory harness, installed to `~/.codex/prompts/cpp-memory.md` by `scripts/install-memory-harness.sh`. Relocated here when the deprecated generated `codex/prompts/` flat surface (#446) was retired at the #556 cutover (superseded by `codex/skills/`, #555).
- `.woodpecker.yml` - Woodpecker CI pipeline (secret-scan, lint, test, typecheck, codex-skills-check, eli5-vendor-check, eli5-upstream-drift (advisory), tool-risk-drift, Dockerfile lint)

## Environment Variables

- `CLAUDE_PROJECT` - Default project for `/project:next` from `~/Projects`. Set in `~/.bashrc`.
- `FLOW_WORKTREE_BASE` - Optional worktree base override (issue #584, ADR 0003 Option A): when set (host config, e.g. `~/.bashrc`), `/flow:start` + `/flow:auto` create worktrees at `$FLOW_WORKTREE_BASE/<repo>-<branch>` via the git lane instead of in-repo `.claude/worktrees/<branch>` via `EnterWorktree`. Unset = shipped default, byte-identical to today. Never set in shipped config (PR #527 norm).

## MCP Servers and Secrets

CPP ships **no container runtime** as of #469. The Docker MCP runtime (the `mcp-second-opinion` server, the `aws-secrets-agent` sidecar, all `docker-compose*.yml` files, every `make docker-*` target, and the compose-based deploy path) was retired when `mcp-second-opinion` moved to its own external repo (https://github.com/cooneycw/mcp-second-opinion). The remaining MCP servers are stdio/http and need no CPP-built image.

- **Second opinion (`/second-opinion:*`, `/evaluate:*`):** the server runs from its own external repo (localhost, or a Tailscale host). CPP consumes it as a client - the repo ships a root `.mcp.json` registering `second-opinion` as a streamable-http server at `http://127.0.0.1:8080/mcp`. Point that URL (or a user-scope `claude mcp add second-opinion --transport http --url <url> --scope user`) at wherever your server runs. Start the external server first; see `/cpp:init`.
- **Browser automation:** upstream `@playwright/mcp` registered via npx/stdio by `/cpp:init` (no container; the CPP `mcp-playwright-persistent` fork was retired in #423).
- **Secrets:** CPP stores no application secrets on disk and runs no secrets sidecar. The remaining AWS Secrets Manager consumers fetch **directly** via the AWS SDK/CLI: `essent-ai` (Woodpecker CI keys `WOODPECKER_URL` / `WOODPECKER_API_TOKEN`, consumed by `/flow:auto`, `woodpecker/bootstrap-secrets.py`, and `scripts/setup-woodpecker-cli.sh`; also holds `CPP_MEMORIES_DSN`, the common-memory Postgres DSN used by `lib/cpp_memory` for fleet-wide federation - reference the store host by its Tailscale address). Second-opinion LLM keys (`codex_llm_apikeys`) now live with the external server, not CPP. See `/secrets:*` and `lib/creds/`.
- **Deploy:** `make deploy` is an informative no-op - CPP ships no deployable services.
- **Secret scanning:** `make secret-scan` runs gitleaks locally (native binary or Docker fallback). Config in `.gitleaks.toml` with allowlists for doc/test false positives.
- **Bootstrap checks:** `make bootstrap-check` verifies admin-only prerequisites in `.claude/bootstrap.yaml` (now just `jq`, since the Docker runtime prerequisites were retired).
- **Woodpecker CI** runs on push/PR: secret-scan (gitleaks), lint, test, typecheck, and Dockerfile lint. The image-build / CVE-scan / SBOM / compose-policy / runtime-smoke stages were retired with the container runtime in #469.
- **Drift detection:** `make drift-check` compares host-installed artifacts against repo templates and flags **orphaned Docker MCP servers** - a leftover container, `mcp-<name>:*` image, or `claude`/`codex mcp` registration from a retired server (e.g. a lingering `mcp-second-opinion` or `aws-secrets-agent`) - against the curated `.claude/deprecated-mcps.yaml` list of record (via `scripts/mcp-drift.py`). Since CPP now ships no compose file, the current service set is empty by absence, so a listed server still present on the host is treated as an orphan. Detection is curated-list driven so a user's own custom MCP registration is never flagged (the valid external `second-opinion` registration is intentionally not listed); a **running** container that shares a deprecated name but belongs to an external compose project (or runs a non-CPP image) is also auto-protected by provenance and never torn down (issue #520), so the live external `second-opinion` / `aws-secrets-agent` containers survive `/cpp:update`. Teardown is per-server, user-confirmed, and keeps a newest-image restore point unless prune-all is chosen (run `/cpp:update`, or `python3 scripts/mcp-drift.py --teardown <name>`). See `docs/HOST_MANAGED_ARTIFACTS.md` for full inventory.
- **Reproducible builds:** the remaining container image references (the `mcp-evaluate` Dockerfile and the tool images in `.woodpecker.yml`) are pinned by version tag plus `@sha256:` digest, never `:latest`. `renovate.json` rotates the pinned digests on a weekly schedule so pinning never freezes security updates.

## Commands Reference

### Workflow
- `/flow:start` - Create worktree for an issue
- `/flow:eli5 <issue>` - Plain-language intent + necessity/staleness verdict + plan approval gate (runs after analyze, before implement)
- `/flow:check` - Run lint + test + security scan (no commit)
- `/flow:finish` - Quality gates, commit, push, create PR
- `/flow:deploy [target]` - Run make deploy + health/smoke checks
- `/flow:auto` - Full issue lifecycle in one shot (ELI5 plan/necessity approval gate between analyze and implement; `--yes` to skip the pause)
  - Optional second arg `PROJECT` targets a repo other than the session cwd (resolved as a path, else `~/Projects/<name>`); such cross-repo runs ride the deterministic git-worktree lane end-to-end instead of `EnterWorktree`, which cannot leave the session repo (#578)
- `/flow:merge` - Merge PR, clean up worktree
- `/flow:sync` - Push WIP to remote for cross-machine pickup
- `/flow:cleanup` - Prune stale worktrees and branches
- `/flow:status` - Show active worktrees
- `/flow:doctor` - Diagnose workflow environment

**Native worktrees (issue #440):** `/flow` rides Claude Code's built-in
worktrees. `/flow:start` and `/flow:auto` create and enter a worktree with the
`EnterWorktree` tool (checkout under `.claude/worktrees/<name>`, branched from
`origin/<default-branch>` under the default `worktree.baseRef: fresh`) instead of
shelling out to `git worktree add`; same-session cleanup uses `ExitWorktree`.
`.claude/worktrees/` is gitignored. CPP layers its issue-anchored gate policy on
top of these mechanics and does not delegate it: the `issue-<N>-<slug>` branch
name (enforced after `EnterWorktree`), the `/flow:eli5` necessity gate, the
quality gates, and merge/cleanup discipline are unchanged. Because native
`ExitWorktree` only removes worktrees created in the current session, cross-session
and cross-machine cleanup (`/flow:merge`, `/flow:cleanup`) keep `git worktree
remove` / `scripts/worktree-remove.sh` as the fallback. The base location is
configurable via `FLOW_WORKTREE_BASE` (issue #584, ADR 0003 Option A): when set,
worktrees are created at `$FLOW_WORKTREE_BASE/<repo>-<branch>` and the run rides
the #578 git lane end-to-end (the native tool's base dir is not configurable,
and out-of-repo `EnterWorktree(path=...)` triggers an unsuppressable approval
prompt); the guard/merge/remove/friction scripts resolve via git plumbing and
work unchanged at any base. The `/flow:*` commands
ship as the `flow` plugin (`/plugin install flow@cpp`): `.claude/commands/flow/*`
is the permanent source of truth and `plugins/flow/commands/*` holds
byte-identical copies kept in sync by `scripts/plugin-sync.sh`. The legacy
global-skill mirror (`~/.claude/skills/flow-*`) and its `flow-skill-sync.py`
generator were retired in B4 (#480). The plugin also bundles the helper family
under `plugins/flow/scripts/` (EXTRA_FILES, #590) - without it a
marketplace-only install dead-ends at exit 127 in Step 1 - and `/flow:repair`
(`scripts/flow-helpers-install.sh`) installs those helpers to
`~/.claude/scripts/`, the stable path the #581 allowlist rules match.
`/flow:doctor` reports missing/stale helpers read-only.

**Worktree path-resolution rule (issue #486):** a native `EnterWorktree` session
edits the worktree, but the worktree lives *inside* the main repo at
`.claude/worktrees/<name>/`. Resolve every `Write`/`Edit` path from the active
worktree root - `git rev-parse --show-toplevel` - or use a plain relative path
from the session cwd; **never hand-build a `.claude/worktrees/<name>/...`
absolute path**, which has been observed to land the edit in the MAIN repo
working tree instead of the worktree (flow:auto #442 x2, #471). `/flow:auto`
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

### Project
- `/project:init <name>` - Full project scaffolding (zero to GitHub repo)
- `/project:next` - Prioritized next-step report (compact default ~2-4K tokens; `--full` deep 5-tier analysis ~15-30K, `--brief` single pick)
- `/project:lite` - Quick project reference (~500-800 tokens)

`/project:init` delegates config scaffolding (CLAUDE.md, skills, hooks) to Claude
Code's native `/init` interview rather than hand-rolling a fixed template, then
runs `/claude-md:lint` to overlay CPP's CI/CD governance directives. CPP keeps the
zero-to-GitHub-repo orchestration native `/init` does not provide: directory +
framework scaffold, `git init` and repo create/push, Makefile/CI wiring
(`lib/cicd`), CPP toolkit install, and `.specify/` structure (epic #417 Phase A,
mirrors the `/security` #438 and hooks #439 defer-the-commodity-half moves).

### Spec-Driven Development
- `/spec:adopt` - **(supported)** Install the official GitHub spec-kit CLI and scaffold it into the project (`specify init --here --ai claude`); then author with the `/speckit-*` skills and ship with `/flow:auto`. Turn `tasks.md` into GitHub issues with `scripts/speckit-tasks-to-issues.sh` (gh-CLI, no github-mcp-server). Per-project, always latest upstream. The `specify` CLI installs on first `/spec:adopt` use, or up front via `/cpp:init` / `/cpp:update`.
- `/spec:help` - Overview of the spec-kit authoring path

**Spec-driven dev = official spec-kit plugin + `/flow:auto`.** CPP's home-grown pipeline (`/spec:create`, `/spec:sync`, `/spec:status`, `/spec:init`, backed by `lib/spec_bridge`) was **retired** in favor of upstream spec-kit (epic #417 Phase A, decision on #418).

### GitHub Issues
- `/github:issue-list` - List and search issues
- `/github:issue-create` - Create new issue
- `/github:issue-view` - View issue details
- `/github:issue-update` - Update existing issue
- `/github:issue-close` - Close issue with optional comment

**Scaffolding backend:** GitHub Issues (driven by the `flow-auto` skillset) is the only supported scaffolding/issue backend. Wiki.js and Plane are out of scope and are not part of CPP.

### CI/CD
- `/cicd:init` - Detect framework, generate Makefile and cicd.yml
- `/cicd:check` - Validate Makefile against CPP standards
- `/cicd:health` - Run health checks (endpoints + processes)
- `/cicd:smoke` - Run smoke tests from cicd.yml
- `/cicd:verify` - Verify a deployment against a pre-deploy baseline (proceed/review/rollback)
- `/cicd:pipeline` - Generate CI/CD workflows: GitHub Actions, or self-hosted Woodpecker via `pipeline.provider` (consults cicd_tasks.yml manifest if present)
- `/cicd:woodpecker` - Generate a hardened self-hosted Woodpecker pipeline (opt-in secret-scan + image-security + runtime-smoke stages) and scaffold the server/agent from `templates/woodpecker/`; see `docs/skills/woodpecker-ci.md`
- `/cicd:container` - Generate Dockerfile and docker-compose.yml
- `/cicd:infra-init` - Scaffold IaC directory (foundation/platform/app tiers)
- `/cicd:infra-discover` - Generate cloud resource discovery script for IaC import
- `/cicd:infra-pipeline` - Generate per-tier CI/CD pipelines with approval gates
- `python -m lib.cicd validate` - Validate .claude/cicd.yml with fix suggestions (Pydantic v2)
- `python -m lib.cicd validate --schema` - Generate JSON Schema for IDE autocompletion
- `python -m lib.cicd run --plan <name>` - Execute CI/CD plan deterministically (finish, check, deploy)
- `python -m lib.cicd verify --baseline` - Capture pre-deploy health/smoke baseline
- `python -m lib.cicd verify` - Verify post-deploy against baseline (exit 1 = ROLLBACK)
  - Invocation contract for every `lib.cicd` call in a command doc: `PYTHONPATH="$CPP_DIR:$PYTHONPATH" uv run --project "$CPP_DIR" python -m lib.cicd ...` - `PYTHONPATH` names the PARENT of `lib/` (or `-m lib.cicd` cannot resolve) and `uv` supplies the pinned 3.11+ interpreter plus pydantic. Bare `python3` with `PYTHONPATH` pointed inside `lib/` fails on both counts; it silently disabled deploy verification for months (#430 fixed Step 6, #595 fixed the Step 9 / `/flow:deploy` / `/cicd:verify` verify calls, pinned by `tests/test_cicd_verify_invocation.py`). The same broken shape still rides ~40 non-`verify` `lib.cicd` lines in the `cicd`/`cpp`/`codex`/`project` families - a known latent bug awaiting its own sweep, not a covered case
- `python -m lib.cicd.bootstrap check` - Check admin-only bootstrap dependencies (config: `.claude/bootstrap.yaml`)

### Codex Orchestration
- `/codex:auto <ISSUE>` - Full issue lifecycle delegated to Codex CLI (worktree, implement, review, quality gates, PR)
- `/codex:exec <PROMPT>` - One-shot Codex execution in current directory with JSONL monitoring
- `/codex:ask <QUESTION>` - Delegate a read-only question to Codex and relay its answer (read-only by default; network opt-in on explicit request)
- `/codex:status` - Check Codex CLI installation, config, and readiness
- `/codex:help` - Codex commands overview

### Security
- `/security:scan` - Full scan: native + external tools
- `/security:quick` - Fast scan: native only (zero deps)
- `/security:deep` - Deep scan: includes git history
- `/security:explain <ID>` - Explain a finding type

### Secrets
- `/secrets:get`, `/secrets:set`, `/secrets:delete`, `/secrets:list` - CRUD operations
- `/secrets:run -- CMD` - Run command with secrets injected as env vars
- `/secrets:validate` - Test credential configuration
- `/secrets:ui` - Launch web UI
- `/secrets:rotate KEY` - Rotate a secret

### Documentation
- `/documentation:pptx [topic]` - Guided PowerPoint creation with diagrams (QA gating; screenshots via the upstream `@playwright/mcp` server)
- `/documentation:c4` - Generate C4 architecture diagrams as GitHub-renderable Mermaid via `scripts/c4-mermaid.py` (all 4 levels, per-container L3, per-component L4; flowchart L1-L3 + classDiagram L4; edge-validity QA gate, density-split hints, `index.md` + manifest)

### Evaluation
- `/evaluate:issue` - 4-phase multi-model evaluation (divergence, reasoning, validation, spec output)

### Second Opinion
- `/second-opinion:start [file] [model] [depth]` - Quick code review via external LLMs
- `/second-opinion:models` - Interactive model/depth selection

### QA
- `/qa:test` - Automated web testing via the upstream `@playwright/mcp` server (single session)

### Browser Sessions
- `/browser:session <verb> [name]` - Named **concurrent** browser sessions over upstream `@playwright/mcp` via a static "lease-desk" pool (create/resume/save/close/list/cleanup/pool). Recovers the one feature upstream lacks (microsoft/playwright-mcp#1530) with no fork. Opt-in pool registered via `/cpp:init` (Full tier -> browser pool); ledger in `scripts/playwright-desk.py`. See `docs/skills/browser-session-wrapper.md`.
- `/browser:help` - Browser session commands overview

### CLAUDE.md Management
- `/claude-md:lint` - Lint CLAUDE.md for missing CI/CD, Docker, and troubleshooting directives

### Skills
The `/skills:*` wrapper was retired (issue #437) - it is fully absorbed
by the native Claude Code ecosystem. Use these instead:
- `npx skills find|add|list|update <...>` - Discover/install/manage skills from [skills.sh](https://skills.sh/)
- `/plugin` - Browse and install from the plugin marketplace
- Auto-loading `.claude/skills` + `/reload-skills` - Project-local skills, no wrapper needed

### Installation
The command/skill/hook surface installs via Claude Code's `/plugin` (ADR 0001, epic #417 Phase B): `/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install <family>@cpp` for any of the 15 per-family plugins. `/plugin` owns versioning and updates for those surfaces. The `/cpp:*` commands below are no longer the way to get commands; they install and refresh only the **non-plugin infra** a plugin cannot deliver (external MCP server pointer, `@playwright/mcp` registration, secrets/AWS-SM access, spec-kit CLI, the PermissionRequest census hook, and the `/flow:*` allowlist merge). See `README.md` and `docs/HOST_MANAGED_ARTIFACTS.md`.

- `/cpp:init` - Non-plugin infra installer (Tiers: Minimal, Standard, Full, CI/CD, Codex); wires the external second-opinion `.mcp.json` pointer, `@playwright/mcp`, the census hook + flow allowlist, optionally the spec-kit CLI (`specify`, the engine behind `/spec:adopt`), and - at the Codex tier - installs the generated Codex skills plus the common-memory harness (Tier 5e/5f, #575). Init only ever INSTALLS; retired-surface teardown belongs to `/cpp:update`
- `/cpp:status` - Check installation state
- `/cpp:update` - Pull latest, sync deps, migrate legacy systemd units if present, tear down orphaned Docker MCP infra via the curated `.claude/deprecated-mcps.yaml` (Step 6c/7, user-confirmed; CPP ships no container runtime since #469), then offer to merge new flow allowlist rules from `templates/claude-settings-permissions.json` into `~/.claude/settings.json` (Step 7.5, user-confirmed) and to register the observe-only PermissionRequest census hook there (Step 7.6, user-confirmed); also refreshes the optional spec-kit CLI (`specify`) if installed (Step 4.6); and offers an out-of-repo commands-mirror drift check/refresh via `scripts/commands-mirror-sync.sh` when a mirror exists (Step 7.8, #582); then refreshes the generated host surfaces (Step 7.9, #575) - installs the Codex skills, wires the common-memory harness, and detects retired surfaces still present via `scripts/retired-surface-prune.py`, offering a per-surface, user-confirmed, reversible teardown

### Other
- `/cpp:dockers` - Docker container status, health, project linkages
- `/self-improvement:retro` - Post-run friction retro (the grill-me cycle): always-on capture (`scripts/friction-log.sh` -> `.claude/friction.jsonl`, woven into `/flow:auto` + `/flow:merge`) then classify -> dedup -> propose -> confirm -> codify durable fixes; local ledger `.claude/learnings.md`, portable knowledge delegates to `/self-improvement:memory` (#433)
- `/self-improvement:deployment` - Retrospective analysis after failed deploys
- `/self-improvement:memory` - Populate the shared common-memory ledger with portable friction-knowledge (bucket-2-plus); consult-not-push, fail-open
- `/cpp:happy-check` - Check happy-cli version (optional)

## Makefile Integration

Flow commands use Makefile targets as the canonical build interface:

- `/flow:check` and `/flow:finish` use `python -m lib.cicd run --plan finish` (deterministic runner) with fallback to `make lint` / `make test`
- `/flow:deploy` uses `python -m lib.cicd run --plan deploy` (deterministic runner) with fallback to `make deploy` + post-deploy health/smoke
- `/flow:auto` runs `make update_docs` after implement, verifies CI after merge, then `make deploy`
- `/flow:doctor` reports which standard targets are available
- Deploy metadata in `.claude/deploy.yaml` (optional, created manually when needed)
  - `mode: external` - deploy runs out of band (host timer / CI on origin/main); `/flow:auto` Step 9 and `/flow:deploy` skip the inline `make deploy` rather than staging a throwaway per-worktree compose stack (#535)
  - `compose_project_name: <name>` - pins `COMPOSE_PROJECT_NAME` for `make deploy` so docker compose never derives it from a worktree/tmp directory basename and collides with fixed prod `container_name` values; defaults to the canonical primary-checkout name when unset (#535)
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
- **Hooks configured in** `.claude/hooks.json` (SessionStart staleness + PostToolUse project-level) and `~/.claude/settings.json` (PermissionRequest census + opt-in SessionStart pending-retro reminder, user-level); the `secrets` plugin bundles the same PostToolUse masking hook for plugin installs (#479, ADR 0001 section 6)
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
