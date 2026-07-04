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
- **B3 - Hooks + MCP client pointers.** Bundle hooks into the relevant plugins;
  decide MCP `.mcp.json` client-pointer packaging (compose/secrets stay
  `make docker-*`). Resolve the masking-script path.
- **B4 - Prove parity, then retire the dual surface.** Once every family
  installs via `/plugin`, retire the global-skill mirror, `flow-skill-sync.py`,
  `skill-drift.py`, `.claude/deprecated-skills.yaml`, and the symlink paths in
  `/cpp:init|update|status`. Keep `mcp-drift.py`, the Docker/host portions of
  `drift-detect.sh`, and `bootstrap.yaml`.
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
