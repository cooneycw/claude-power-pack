# ADR 0001: Plugin-marketplace packaging for CPP

- Status: Accepted (phased adoption)
- Date: 2026-07-03
- Deciders: cooneycw (owner)
- Issue: #442 (epic #417, Phase B)
- Supersedes: nothing
- Related: #443 / PR #467 (eli5-gate: /flow:eli5 extracted to its own public repo https://github.com/cooneycw/eli5-gate - the precedent for this pattern), #446 (multi-harness single-source skill generation), mcp-second-opinion (SHIPPED: https://github.com/cooneycw/mcp-second-opinion; CPP strip-out #469), #472 (cpp_memory store backend mini-tier - stays in CPP)

## TL;DR

Adopt the Claude Code plugin-marketplace model as CPP's distribution format,
**in phases**, packaging one plugin per surviving command family. Keep the
infrastructure machinery that plugins do not absorb (the Docker-compose MCP
stack with its AWS secrets sidecar, `mcp-drift.py`'s orphaned-container
detection, and `bootstrap.yaml` admin-prereq checks). Retire the dual
command/skill surface, `skill-drift.py`, and most of the 3,140-line
`/cpp:init|update|status` symlink installer only once plugin parity is proven.
No code is migrated or retired by this ADR; the migration lands as gated
sub-issues under epic #417 (see "Migration plan").

## Context

### Why now

This decision was filed as issue #442 under epic #417 Phase B
("Evaluations / decisions"). The review doc verdict for the installer
(`docs/reviews/2026-07-02-ecosystem-review.md`, section 4) is
"RESTRUCTURE (evaluate)". The stated precondition, "SEQUENCE AFTER the Phase A
retirements shrink the surface to repackage", became satisfied on 2026-07-03:
the Phase A retirements merged the same day (#437 /skills, #438 security split,
#439 hooks split, #440 native worktrees, #441 thin project:init, #423 playwright
fork retirement). The surface is now at its smallest, so this is the right
moment to decide the distribution model.

### The distribution-norm evidence

Plugin marketplaces are the mid-2026 distribution norm; git-clone plus
symlink/dotfile installers are the legacy pattern the ecosystem leaders migrated
off during late 2025 and early 2026 (review doc section 2). obra/superpowers,
wshobson/agents, github/spec-kit, garrytan/gstack, and
EveryInc/compound-engineering all ship as plugins or plugin marketplaces.
SuperClaude_Framework is the cautionary tale: still a pipx dotfile installer,
now the smallest of the majors.

### The structural cost CPP carries today

Because CPP ships two copies of most surfaces (repo `commands/` and a
hand/generated global `~/.claude/skills/` mirror), it needs curation and drift
machinery to keep them consistent:

| Cost | Size / location |
|------|-----------------|
| Installer wizardry | `/cpp:init` 1484 + `/cpp:update` 1014 + `/cpp:status` 642 = 3,140 lines |
| Dual-surface generator | `scripts/flow-skill-sync.py` (repo command -> global skill) |
| Skill drift reconciliation | `scripts/skill-drift.py` (~370 lines) |
| Curated deprecation lists | `.claude/deprecated-skills.yaml` (drives skill teardown) |

A plugin marketplace removes the *reason* those exist: there is one surface
(the plugin), installed and updated by `/plugin`, versioned in the repo.

## Decision

**Adopt the plugin-marketplace model, phased.** Package one plugin per surviving
family (flow, cicd, secrets, codex, second-opinion, documentation, security,
github, project, claude-md, evaluate, self-improvement, browser, qa) plus a
top-level `cpp` meta/help plugin. Publish a `marketplace.json` so the install
path is `/plugin marketplace add cooneycw/claude-power-pack` then
`/plugin install flow@cpp`.

We reject a single big-bang migration PR. Epic #417's non-goals explicitly
forbid "any big-bang rewrite; every change lands as its own gated issue", and
two of the hard sub-problems (MCP packaging, drift scope) are not yet designed.
The migration is therefore sequenced (see "Migration plan").

We reject "defer / do nothing": the dual-surface cost is real and recurring, the
dependencies are freshly met, and the norm is unambiguous.

## Target design

### Repository layout

```
claude-power-pack/
  .claude-plugin/
    marketplace.json            # lists every plugin + its source path
  plugins/
    flow/
      .claude-plugin/plugin.json
      commands/                 # flow/*.md (issue-anchored gate policy)
      skills/                   # generated skill bodies, if still needed
    cicd/
      .claude-plugin/plugin.json
      commands/
    secrets/  codex/  second-opinion/  documentation/  security/
    github/   project/  claude-md/  evaluate/  self-improvement/
    browser/  qa/  cpp/
```

Each `plugin.json` carries `name`, `version`, `description`, and points at the
family's `commands/`, `skills/`, `hooks/`, and (where relevant) `.mcp.json`.
`marketplace.json` enumerates the plugins and their in-repo source directories,
so one repo is the marketplace.

### Install / update path

- Install: `/plugin marketplace add cooneycw/claude-power-pack` then
  `/plugin install <family>@cpp`.
- Update: `/plugin` handles version bumps; the SessionStart staleness hook and
  most of `/cpp:update` become unnecessary for plugin-delivered surfaces.

### One plugin per family, not one monolith

Per-family plugins let a user install only what they use (for example flow +
cicd without secrets), match how the ecosystem ships (wshobson/agents = 88
plugins), and give each family independent versioning. The `cpp` plugin carries
only cross-cutting help/meta.

## Hard questions this ADR resolves

These are the parts the raw issue body glossed over. They are the reason a
big-bang PR is the wrong instrument.

### 1. The MCP stack does not fit `.mcp.json` bundling

CPP's MCP servers are not stdio processes a plugin can declare in `.mcp.json`.
They are a **Docker-compose stack** (`mcp-second-opinion`, plus the
`aws-secrets-agent` Rust sidecar) that fetches API keys at startup from AWS
Secrets Manager and is registered per-project as `127.0.0.1:{port}/sse`. A
plugin `.mcp.json` entry cannot bring up docker-compose, the secrets sidecar,
the SSRF-token handshake, or the fail-closed readiness gate.

**Resolution:** the MCP layer stays Docker-compose-managed and is NOT bundled
into the plugin as a runnable server. The plugin may ship the `.mcp.json`
*client pointer* (the `127.0.0.1:{port}/sse` connection stanza) and the
compose/secrets orchestration remains a `make docker-*` concern documented in
CLAUDE.md. Whether the pointer ships in the plugin or stays project-local is a
Phase B3 design task. The browser MCP is already the upstream `@playwright/mcp`
npx/stdio server (no container), so it *can* ship as a normal plugin `.mcp.json`
entry.

This separation is now being made concrete: `mcp-second-opinion` is being
**extracted into its own independent repository** (decided 2026-07-03). It is
already a self-contained subtree (own `pyproject.toml`, `uv.lock`, `src/`,
`deploy/Dockerfile`, `README.md`). After extraction the `second-opinion` plugin
ships only the commands plus the `.mcp.json` client pointer; the server is
developed, versioned, and released from its own repo and consumed by CPP as an
external component. This is the reference example of why an MCP server is a
distribution unit distinct from the plugin that talks to it. Tracked as its own
gated sub-issue (see migration plan B0).

### 2. Not all drift machinery is packaging drift

- `skill-drift.py` exists only because of the dual surface. It **retires** with
  the migration.
- `mcp-drift.py` detects orphaned *Docker* MCP containers/images left after a
  server is removed from `docker-compose.yml`. That is infrastructure
  reconciliation, unrelated to plugin packaging. It **survives**.
- `drift-detect.sh` reconciles host-installed artifacts (systemd remnants, host
  scripts) against repo templates. The skill/symlink portions shrink; the
  host-artifact and Docker portions **survive** (see
  `docs/HOST_MANAGED_ARTIFACTS.md`).
- `bootstrap.yaml` admin-prereq checks (IAM, secrets provisioning) are
  deploy-time gates, not install-time; they **survive**.

The issue's exit criterion "drift scripts retired" is therefore only partly
achievable and is rewritten accordingly in the migration plan.

### 3. Hooks

CPP ships a SessionStart staleness hook (git-behind check) and a PostToolUse
secret-masking hook that shells to `~/.claude/scripts/hook-mask-output.sh`.
Plugins can bundle hooks, but the masking hook references a host-installed
script path. Phase B3 decides whether the script ships inside the plugin
(`${CLAUDE_PLUGIN_ROOT}/...`) or stays host-installed. The SessionStart
staleness hook is largely obsoleted by `/plugin` update handling.
(Resolved in Phase B3 - see section 6.)

### 4. Interplay with #443 and #446

- #443 extracted `/flow:eli5` as a standalone necessity-gate plugin in its own
  public repo (PR #467, https://github.com/cooneycw/eli5-gate) - the first
  instance of this extract-and-vendor-back pattern. Its `eli5-core` marker plus
  drift-check is the template for skill extractions here.
- #446 makes surviving skills consumable from Codex CLI via single-source ->
  per-harness generation. The per-family `commands/` + `skills/` source layout
  chosen here is the single source #446 generates from. The two must share one
  source-of-truth directory shape, decided in Phase B2.

### 5. Single-source layout, shared with #446 (resolved in Phase B2, #478)

Phase B2 settles the source-of-truth question deferred above:

- `.claude/commands/<family>/*.md` is and remains the **single source of
  truth** for every family's command bodies - permanently, not only during the
  parallel window. There is no direction flip at B4: making `plugins/` canonical
  would orphan the repo-local dogfooding surface and reintroduce exactly the
  two-sources ambiguity this migration removes.
- `plugins/<family>/commands/` holds **generated, checked-in, byte-identical
  artifacts**. The repo doubles as the marketplace, so the generated copies are
  committed, regenerated by `scripts/plugin-sync.sh --write`, and kept honest by
  `scripts/plugin-sync.sh --check` (pinned in `tests/test_plugin_marketplace.py`;
  same deterministic-generator idiom as `flow-skill-sync.py` and
  `eli5-core-drift.sh`). The B1 `plugin-flow-sync.sh` survives as a shim onto
  the generalized script and retires with B4.
- The `cpp` plugin ships `help.md` only (help/meta per this ADR). The
  `/cpp:init|update|status` installer commands stay repo-local: they are the
  legacy surface B4 retires and are not distributed through the surface that
  replaces them.
- Not packaged: the `spec` family (spec-kit is the upstream product; `/spec:adopt`
  installs it) and the loose top-level commands (`dockers`, `project-next`,
  `project-lite`, `happy-check`, `load-*`), which plugin namespacing would
  rename. Whether they move, rename, or retire is a B4/B5 decision.
- #446 (multi-harness generation) reads the SAME `.claude/commands/<family>/`
  source and emits per-harness artifacts; `plugins/<family>/skills/` is the
  reserved output slot for generated skill bodies where a harness needs them.
  One source, N generated surfaces (Claude Code plugin, Codex CLI, ...).
- What B4 retires is the host-side dual surface (the `~/.claude/skills` global
  mirror, `flow-skill-sync.py`, `skill-drift.py`, the symlink installer paths),
  not the in-repo `plugins/` artifacts - those ARE the distribution.

**Reconcile rule for every generated harness surface (issue #556).** The
single-source discipline is the same in every direction: **edit the source of
truth in `.claude/commands/<family>/*.md`, never a generated copy.** Generated
copies (`plugins/<family>/commands/`, `codex/skills/<family>-<cmd>/`) are
byte-identical artifacts; reconcile any drift by re-running the generator
(`scripts/plugin-sync.sh --write`, `scripts/codex-skill-sync.py --write`), never
by hand-editing the output. The Codex harness surface is `codex/skills/`
(#555); the older flat `codex/prompts/` surface (#446) was **retired at the #556
cutover** along with `scripts/codex-prompt-sync.py`.

**Cross-repo consumption is PULL, not push (issue #556).** codex-power-pack does
not receive PRs from CPP; it **vendors** the Codex surface from CPP and runs its
own local drift check (codex-power-pack#75), the same consumer-vendors-the-core
model eli5-gate (#443) established. What codex-power-pack pins is the **source
plus the generator** - `.claude/commands/<family>/*.md` and
`scripts/codex-skill-sync.py` - not the pre-generated `codex/skills/` output, so
the harness transform is versioned with the generator and CxPP can regenerate
against its own harness. CPP's own currency is guarded by the explicit
`codex-skills-check` step in `.woodpecker.yml` (issue #556).

### 6. Hooks + MCP client pointers (resolved in Phase B3, #479)

Phase B3 settles the packaging questions deferred in sections 1 and 3:

- **The masking hook ships inside the secrets plugin.**
  `plugins/secrets/hooks/hooks.json` registers the PostToolUse hook with a
  `${CLAUDE_PLUGIN_ROOT}/scripts/hook-mask-output.sh` command, and the plugin
  carries a byte-identical copy of `scripts/hook-mask-output.sh` (the source of
  truth is unchanged; `plugin-sync.sh --check/--write` now guards per-family
  extra artifacts exactly like the command bodies). A plugin hook that pointed
  at the host-installed `~/.claude/scripts/` symlink would keep the plugin
  dependent on the very installer B4 retires. The legacy `.claude/hooks.json` +
  symlink path continues in parallel until B4.
- **The SessionStart staleness hook is NOT bundled.** Its job is warning when a
  git-clone install is behind `origin/main`; plugin installs are updated by
  `/plugin`, so the hook is meaningless there (anticipated in section 3:
  "largely obsoleted"). It stays a repo-local `.claude/hooks.json` concern and
  retires with the legacy surface in B4.
- **The second-opinion plugin ships its `.mcp.json` client pointer.**
  `plugins/second-opinion/.mcp.json` declares the same streamable-http stanza
  as the repo-root `.mcp.json` introduced by #469 (default
  `http://127.0.0.1:8080/mcp`), so a plugin-only install reaches a locally
  running server with zero extra wiring. Users whose server lives elsewhere
  re-register the URL at user scope (`claude mcp add second-opinion --transport
  http --url <url> --scope user`), as `/cpp:init` Tier 3 documents. A parity
  test pins the plugin pointer to the root pointer so the two never diverge.
  (#469 merged mid-B3 and retired the compose stack entirely, so the pointer
  is the plugin's ONLY MCP responsibility - there is no server-side packaging
  left to decide.) The browser family deliberately ships no `.mcp.json`:
  `/browser:session`'s lease-desk pool manages its own upstream
  `@playwright/mcp` registrations, and a static plugin entry would fight it.

## What extracts, what stays in CPP

The plugin marketplace is not the only destination. This effort sorts CPP's
surface into three homes, and the boundary matters:

- **Skills** (a prompt with standalone value) extract to their own plugin repo;
  CPP vendors the canonical core back with a drift check. Precedent: eli5-gate
  (#443 / PR #467).
- **Services** (a running server) extract to their own repo and are consumed via
  a `.mcp.json` pointer; nothing is vendored back. Precedent: mcp-second-opinion
  (B0 below).
- **Backends and client libraries** stay in CPP. A storage backend is not a
  product to extract; it becomes a pluggable option instead. Example: the
  `cpp_memory` store is a `/cpp:init` mini-tier (md / local-pg / remote-pg), not
  a repo (#472).

Rule of thumb: if a user would install or run it on its own, it can extract; if
it only has meaning as part of a CPP feature, it stays.

Because extracted projects are distributed independently (`/plugin`, `npx
skills`, or run-it-yourself), each carries **its own ADR(s)** for its internal
decisions and stands alone. This ADR records only CPP's decision and the
extraction boundary; it is not the decision record for the extracted repos.
Provenance links run both ways: this ADR lists the repos, and each repo links
back here. Precedent: `mcp-second-opinion` ships
`docs/decisions/0001-standalone-extraction-and-architecture.md`.

## Migration plan (gated sub-issues under epic #417)

No parity is assumed until proven. Each phase is its own `/flow` issue.

- **B0 - Extract mcp-second-opinion to its own repo. [SHIPPED 2026-07-03]** The
  self-contained `mcp-second-opinion/` subtree (server + the AWS Secrets Manager
  Agent sidecar build recipe, no vendored AWS code) now lives in its own public
  repo, https://github.com/cooneycw/mcp-second-opinion, with a standalone
  docker-compose. Consumption model: **fully decoupled** - CPP keeps only the
  `/second-opinion:*` client commands plus a `.mcp.json` pointer and runs the
  server on demand, not a git submodule or a CPP-built image. The CPP-side
  strip-out (remove both services from compose/CI/docs, retire the now-empty
  Docker MCP runtime) is tracked as #469. Second application of the
  extract-to-own-repo pattern eli5-gate established.
- **B1 - Scaffold + proof-of-concept. [SHIPPED 2026-07-04, #477 / PR #491]**
  Add `.claude-plugin/marketplace.json` and one family plugin (`flow`) as
  `plugins/flow/`. Prove `/plugin install flow@cpp` loads the commands
  alongside the existing installer. Retire nothing.
- **B2 - Migrate remaining families. [SHIPPED 2026-07-04, #478]** Package the
  other families as plugins, settling the single-source `commands/` + `skills/`
  layout shared with #446 (resolution recorded in "Hard questions" section 5).
  Installer still present in parallel.
- **B3 - Hooks + MCP client pointers. [SHIPPED 2026-07-04, #479]** The secrets
  plugin bundles the PostToolUse masking hook (plugin-local script resolved via
  `${CLAUDE_PLUGIN_ROOT}`, guarded by `plugin-sync.sh` extra-artifact sync);
  the second-opinion plugin ships its `.mcp.json` client pointer matching the
  repo-root one (#469); the SessionStart staleness hook is deliberately NOT
  bundled (obsoleted by `/plugin` updates; retires with the legacy surface in
  B4). Resolutions recorded in "Hard questions" section 6.
- **B4 - Prove parity, then retire the dual surface. [SHIPPED 2026-07-04, #480]**
  Parity proven (all 15 families in `marketplace.json` with a `plugin.json`,
  guarded by `plugin-sync.sh` + `test_plugin_marketplace.py`), so the retirement
  landed: deleted `flow-skill-sync.py`, `skill-drift.py`, the B1
  `plugin-flow-sync.sh` shim, and `.claude/deprecated-skills.yaml`; removed the
  `~/.claude/skills` symlink paths from `/cpp:init|update|status` (and the
  `/cpp:update` skill-drift prune step); dropped the flow-mirror re-sync from the
  `/flow` command bodies and the mirror check from `/flow:doctor`. Kept
  `mcp-drift.py`, the Docker/host portions of `drift-detect.sh`, and
  `bootstrap.yaml`. The live host `~/.claude/skills` mirror is not torn down by
  this change (a B5 / `/cpp:update` concern). Follow-up #506 rewires the
  post-merge re-sync onto `plugin-sync.sh`.
- **B5 - Docs + install-path cutover.** Update CLAUDE.md, README, and
  `docs/HOST_MANAGED_ARTIFACTS.md` to the `/plugin` install path; keep a
  documented fallback for the Docker/secrets/bootstrap steps plugins do not
  cover.

## Consequences

### Positive

- One surface instead of two: no `flow-skill-sync.py`, no `skill-drift.py`, no
  hand-maintained global mirror, no skill-deprecation curation list.
- Most of the 3,140-line installer retires; install becomes `/plugin install`.
- Matches the ecosystem norm, so CPP is discoverable and installable the way
  users now expect, and per-family install lets users take only what they need.
- Upstream `/plugin` handles versioning and updates for the delivered surfaces.

### Negative / risks

- The migration is multi-PR and spans #417 Phase B; it is not a one-shot win.
- The MCP + Docker + AWS-secrets layer does NOT collapse into a plugin; CPP
  keeps a two-mode install story (plugin for commands/skills/hooks, `make
  docker-*` for the MCP stack). This must be documented clearly or it becomes a
  new source of confusion.
- Risk of surface loss during cutover. Mitigated by B1-B4 running the installer
  and plugins in parallel until parity is proven, and retiring only in B4.

### Explicitly NOT retired by this decision

`mcp-drift.py`, `bootstrap.yaml`, the Docker/host portions of
`drift-detect.sh`, the Docker-compose MCP stack, and the `aws-secrets-agent`
sidecar. These are infrastructure concerns orthogonal to distribution
packaging.

## Alternatives considered

- **Big-bang migration (issue #442 as literally written).** Rejected: violates
  epic #417's "no big-bang rewrite" non-goal, and the MCP/drift design is
  unresolved. High risk of surface loss with no rollback granularity.
- **Defer until #443/#446 land.** Rejected: the dual-surface cost is recurring
  and the dependencies are freshly met; #443 and #446 in fact need this target
  design to build against, so deciding now unblocks them.
- **Keep the symlink installer (do nothing).** Rejected: it is the documented
  legacy pattern and a standing maintenance tax (drift scripts, dual surface,
  3,140-line wizard).

## Amendment 2026-07-18: top-level commands folded into families (issue #582)

The B2 resolution left the loose top-level commands (`dockers`, `project-next`,
`project-lite`, `happy-check`, `load-*`) unpackaged, "a B4/B5 decision" that was
never made. The gap shipped: both generated surfaces discover sources via
`.claude/commands/<family>/*.md` only, so a clean `/plugin`-only install never
received these six commands and `codex/skills/` never carried them - confirmed
in the field on 2026-07-18 (`/project:next` -> Unknown skill from a plugin-only
box whose `project` plugin help.md advertised it anyway).

Decision (#582, disposition (a) - fold, not generator special-casing):

- `project-next.md` -> `project/next.md` (`/project:next`), `project-lite.md`
  -> `project/lite.md` (`/project:lite`).
- `dockers.md`, `happy-check.md`, `load-best-practices.md`, `load-mcp-docs.md`
  -> the `cpp` family (`/cpp:dockers` etc.). **The cpp plugin is therefore no
  longer help-only:** it ships help/meta plus these cross-cutting utilities.
  The `/cpp:init|status|update` installer exclusion is unchanged.
- The cpp plugin bundles `docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md`
  (EXTRA_FILES) so `/cpp:load-best-practices` works without a CPP checkout;
  the command resolves the doc via `${CLAUDE_PLUGIN_ROOT}` on plugin installs.
- **Completeness gate:** `plugin-sync.sh --check` and `codex-skill-sync.py
  --check` now fail on any `*.md` directly under `.claude/commands/` (unless in
  an explicit `TOP_LEVEL_EXCLUDE`, empty by design) and on any family dir absent
  from both `FAMILIES` and the documented `UNPACKAGED_FAMILIES` carve-outs
  (`spec`; plus `codex` on the Codex surface). Exclusion by discovery is no
  longer silent.
- Out-of-repo commands mirrors (e.g. `~/Projects/.claude/commands/`) are now
  guarded by `scripts/commands-mirror-sync.sh` (`/cpp:update` Step 7.8);
  preferred end state remains retiring them in favor of `/plugin` installs
  (#575).

Rationale for (a) over teaching the generators about top-level files: plugin
namespacing renames top-level commands on the canonical `/plugin` surface
regardless (this ADR's original observation), so option (b) would make the repo
and plugin surfaces disagree on invocation names. Folding gives every surface -
repo checkout, plugin install, Codex skill, mirror - the same family-scoped
name, at the one-time cost of renaming six invocations.

## Amendment 2026-07-19: the flow plugin bundles its helper family (issue #590)

Phase B5 made `/plugin install flow@cpp` the canonical install path, but the
flow commands are only half the product: they invoke ~14 helper scripts, and
`/flow:start` + `/flow:auto` Step 1 hard-depend on `flow-start-resolve.sh`
(#581), `/flow:merge` on `gh-pr-merge.sh`. Those reached the host only through
`/cpp:init` / `/cpp:update`, which this ADR deliberately keeps repo-local. A
marketplace-only user therefore got exit 127 at Step 1, with the documented
"fall back to the CPP checkout" remedy unavailable and auto.md forbidding an
inline-bash workaround. The `#578` cross-repo lane, living entirely inside the
resolver, was likewise absent for plugin-only users.

The tension is real: bundling alone does not fix it, because the #581 allowlist
rules in `templates/claude-settings-permissions.json` match the stable bare path
`~/.claude/scripts/<helper>`, and a version-stamped plugin-cache path never
matches them - running the helpers in place would trade exit-127 breakage for a
permission prompt on every call.

Decision (#590, the issue's Option 1 - bundle + repair, not "declare flow
clone-required"):

- **Bundle.** `plugins/flow/scripts/` carries the load-bearing family via
  `EXTRA_FILES` - the same mechanism `secrets` uses for its masking hook (B3,
  #479) and `cpp` for the best-practices guide (#582 amendment) - so the copies
  stay byte-identical under `plugin-sync.sh --check`.
  `flow-live-driver-guard.sh` travels with `flow-start-resolve.sh`, which
  resolves it via `$SELF_DIR`.
- **Place.** A new `/flow:repair` (`scripts/flow-helpers-install.sh`, itself
  bundled) installs the family at `~/.claude/scripts/`, so the shipped allowlist
  keeps matching and the zero-prompt lane survives a plugin-only install. It
  **symlinks** from a CPP checkout (following `git pull`, as `/cpp:init` Tier 2
  does) and **copies** from a plugin bundle - a symlink into a version-stamped
  cache would dangle at the next upgrade.
- **Detect.** The copy lane's failure mode is staleness rather than breakage, so
  `flow-helpers-install.sh --check` (read-only) compares content and reports
  `ok|missing|stale`; `/flow:doctor` calls it, and now hard-FAILs on a missing
  helper when no CPP checkout exists to fall back to.
- **Say so.** `/flow:help` gains a Prerequisites section, and the plugin +
  marketplace descriptions state that the helpers are bundled and `/flow:repair`
  places them.

Rationale for Option 1 over Option 2 (declare flow clone-required and fail
loudly): Option 2 would concede that the flagship family cannot honor the B5
promise that `/plugin` is the install path, and would leave the #578 cross-repo
lane clone-only. The residual cost of Option 1 - one explicit post-install
command, and copies that need `/flow:repair` after a plugin upgrade - is
detectable and repairable, whereas a clone requirement is permanent.
