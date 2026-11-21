# ADR 0014: First-class Antigravity capability via a unified host-global update procedure

- Status: Proposed
- Date: 2026-11-21
- Issue: #1876
- Related: ADR 0001 (single-source commands), ADR 0005 (checkout + host-managed
  installs), ADR 0008 (negative-control bound), ADR 0013 (generated mirrors are
  build output, not a tracked tree), #555/#556 (Codex skill generator), #720
  (topic skill provenance & `skills-check.py`), #823/#1029 (`install-drift.sh`),
  #1441 (`codex-global-agents.py`), #1710/#1747 (counter-model runtime evidence)
- Consulted: Antigravity CLI customization spec (`agy-customizations`, including
  `docs/plugins.md`, `docs/skills.md`, `docs/rules.md`, `docs/mcp_config.json`),
  PR #1875 review findings

## The decision, in plain language

Antigravity discovers user-global customizations from `~/.gemini/config/` (skills,
rules, plugins, and MCP servers) and project-local customizations from `.agents/`.
Like Claude Code (`~/.claude/`) and Codex (`~/.codex/`), CPP is installed as a
user-global toolkit rather than per-project. Adding Antigravity as an opt-in CPP
capability must **not** introduce another specialized per-CLI update workflow:

1. **One shared `/cpp:update` procedure across all installed harnesses.**
   `/cpp:update` discovers the host's existing CPP-managed installations,
   refreshes each from the same CPP revision, verifies the installed result,
   and reports an outcome for each harness - even when the CPP checkout is
   already current. Harness-specific details are limited to what the CLI
   requires, such as destination paths, packaging format, and native commands.
   The invoking CLI does not determine which installations get updated: a user
   with Claude Code, Codex, and `agy` runs `/cpp:update` once from any of them
   and sees the per-harness outcome for all three. Partial failures are isolated
   (if one destination is unwritable, other harnesses still refresh and the
   summary identifies the failed destination).
2. **Global install target is `~/.gemini/config/`, with packaging behind the
   shared updater interface.** Whether Antigravity receives a native CPP plugin
   bundle (`agy plugin install`, Option A) or managed loose copies under
   `~/.gemini/config/skills/` (Option B) is a packaging detail encapsulated
   behind the shared harness-adapter contract, evaluated in Wave 1.1 before
   committing to custom copy/prune/MCP-merge logic.
3. **Both CPP skill surfaces are built self-contained from single sources and
   kept as gitignored build output (ADR 0013).**
   - **Command-derived workflow skills** (`.claude/commands/<family>/<cmd>.md`):
     generated on demand from the same single source of truth as Claude and
     Codex, with minimal harness-required adaptations (frontmatter, tool
     fallbacks, `/family:cmd` references).
   - **Topic skills** (`.claude/skills/<slug>/`): canonical packages currently
     lack `metadata.source` and reference external repo-relative guides such as
     `docs/skills/code-quality.md` (11+ skills). Publishing topic skills
     (whether inside a plugin or as loose copies) MUST bundle referenced
     `docs/skills/*.md` files into each package's `references/` directory and
     rewrite `SKILL.md` links to relative `./references/<topic>.md` paths so
     they work from any unrelated repository.
   - Under Option B (loose copies), the installer MUST inject `metadata.source`
     pointing to `claude-power-pack/.claude/skills/<slug>` on copied topic
     skills (since canonical packages do not carry it) and `GENERATED` markers
     on command-derived skills, and verify the expected package-name set so
     `skills-check.py --managed-root` never reports a 0-validated false green.
4. **Global rules and MCP servers respect Antigravity's native contracts.**
   - Rules mirror `~/.claude/CLAUDE.md` plus optional host-local additions
     (following `#1441`), respecting Antigravity's 24 KB per-file cap and
     refusing to overwrite unmanaged or hand-edited files without `--adopt`
     (or shipped as plugin `rules/AGENTS.md` if Option A proves clean for
     host-local additions).
   - MCP servers use Streamable HTTP (`/mcp`) or Stdio only; legacy HTTP+SSE
     (`/sse`) is not supported by Antigravity and is explicitly rejected.
5. **Capability selection goes through `scripts/cpp-install-receipt.py`.**
   `/cpp:init` delegates capability planning and receipt persistence to
   `scripts/cpp-install-receipt.py`. Adding `antigravity` requires updating its
   planner (`CAPABILITY_ORDER`, `CAPABILITY_DEPENDENCIES`, `TIER_CAPABILITIES` /
   `CAPABILITY_REQUIRED`, `REFERENCES`, `STEP_REFS`, `OPTIONAL_STEPS`) and its
   negative controls alongside the command documents.
6. **Flow parity is explicitly gated on a runtime evidence adapter.**
   CPP's counter-model review receipts (schema 5, `docs/agents/counter-model-evidence.md`)
   derive the implementing model from runtime session records, not typed labels.
   Without an Antigravity (`agy`) runtime evidence adapter, an `agy` session
   cannot issue a normal `ran` counter-model receipt even when reviewed by an
   independent model. Full `/flow:auto` parity therefore requires adding an
   `agy` runtime evidence adapter and end-to-end receipt test (tracked in
   Wave 2.3); until that lands, `/flow:auto` support in Antigravity is scoped to
   skill availability, not receipt-backed flow parity.

## Epic acceptance criterion

> `/cpp:update` discovers the host's existing CPP-managed installations,
> refreshes each from the same CPP revision, verifies the installed result, and
> reports an outcome for each harness. Harness-specific details are limited to
> what the CLI requires, such as destination paths, packaging format, and native
> commands. The invoking CLI does not determine which installations get updated.

**Acceptance test:** Start with a current checkout, stale managed Codex and
`agy` skills, and a user-authored skill beside them. Invoke `/cpp:update` once.
Both managed copies must become current and the user skill must retain its
original bytes. Repeat with one destination unwritable: the other must still
refresh, and the summary must identify the failed destination.

## Why

- **Stop multiplying per-CLI update code.** `.claude/commands/cpp/update.md`
  already carries separate Qwen and OpenCode refresh sections alongside Codex.
  Adding another specialized Antigravity refresh block would entrench per-CLI
  duplication and drift. Designing a single harness-agnostic discovery/refresh/
  verify/report loop in Wave 1 keeps CLI specifics strictly confined to thin
  target adapters.
- **Use the harness's native distribution unit when it fits.** Empirical testing
  on `agy 1.5.14` confirmed that `agy plugin install` stages a checkout-independent
  copy: deleting the source directory leaves the enabled plugin and its skill
  intact in `agy plugin list --json`. Evaluating native plugins behind the
  shared updater interface avoids custom copy, orphan-pruning, and
  `mcp_config.json` merge logic if Antigravity already provides those lifecycle
  guarantees.
- **No checkout coupling (ADR 0013).** Neither symlinks into a checkout nor a
  `skills.json` pointing at a working tree should tie the live host skill set to
  whichever branch happens to be checked out in `claude-power-pack`.
- **Self-contained topic skills.** Canonical `.claude/skills/*/SKILL.md` files
  instruct the agent to read `docs/skills/<topic>.md`, which only exists inside
  the CPP repository. Installing raw copies into a global root causes skills to
  fail or read unrelated files when invoked from another project.
- **No silent ownership blind spots.** `skills-check.py --managed-root` only
  validates packages carrying `metadata.source`. Because canonical packages in
  `.claude/skills/` omit `metadata.source`, raw copies skip all 18 packages and
  exit 0. Injecting the marker (under Option B) or checking plugin contents
  directly against a fresh build (under Option A), paired with a membership
  floor, closes that blind spot.
- **Honest parity claims.** Promising `/flow:auto` parity without a counter-model
  runtime evidence adapter for `agy` would break CPP's receipt contract on the
  first real PR.

## What was rejected

- **Add another standalone Antigravity refresh section to `/cpp:update`.**
  - Repeats the per-CLI sprawl already present for Qwen and OpenCode and makes
    each new harness another bespoke maintenance surface.
- **Point `~/.gemini/config/skills.json` directly at `{CPP_DIR}/.claude/skills`
  and `~/.codex/skills`.**
  - Ties topic skills to the live branch state of a checkout (rejected in
    ADR 0013) and leaves external `docs/skills/*.md` references broken outside
    CPP.
  - Couples Antigravity to Codex being installed and feeds Codex-adapted
    instructions to Antigravity.
- **Symlink `~/.gemini/config/skills/<skill>` to `{CPP_DIR}/...`.**
  - Same checkout-coupling and broken-reference problems, and cannot express
    generated command-derived skills without a persistent checkout build tree.
- **Place `.agents/skills/` at `~/Projects/`.**
  - `~/Projects/` is a workspace container, not a git repository; Antigravity's
    workspace walk stops at a repository root (`.git`), so skills placed at
    `~/Projects/.agents/skills/` would not be discovered inside individual project
    repos.
- **Ship Antigravity skills as a separate hand-maintained directory.**
  - Violates ADR 0001's single-source-of-truth invariant and guarantees silent
    drift from `.claude/commands/`.

## Host surface and fidelity boundaries

The exact host paths in the first three rows depend on the Wave 1.1 packaging
gate (Option A: native `agy` plugin vs. Option B: managed loose copies), both
invoked through the shared `/cpp:update` harness-refresh driver. Both options
enforce fresh-build parity, membership floors, and negative controls.

| Surface | Option A (Native plugin) | Option B (Loose managed copies) | Fidelity / Drift check & Negative control |
|---|---|---|---|
| Shared updater | One `/cpp:update` harness-refresh driver discovering and updating all installed CPP harnesses | Same | Acceptance test: current checkout + stale Codex & `agy` + user skill + unwritable-destination fault isolation |
| Skills (command + topic) | Installed CPP plugin via `agy plugin install` (checkout-independent staged copy) | `~/.gemini/config/skills/<skill>/` (`GENERATED` marker on command skills; injected `metadata.source` on topic skills) + `~/.gemini/config/.cpp-skill-install.lock` | Fresh-build comparison in `install-drift.sh` with membership floor; `controls/antigravity-skill-install-fidelity`; cross-repo topic-skill invocation test |
| Global rules | Plugin `rules/AGENTS.md` (plus host-local additions check) or global rules file | Verified `~/.gemini/config/<global-rules>` (`--write`, `--adopt`) | Report-only `--check` (`current`/`stale`/`hand-edited`/`unmanaged`/`absent`/`not-applicable`) + 24 KB cap warning; `controls/antigravity-global-rules` |
| MCP servers | Plugin `mcp_config.json` (scoped to plugin lifecycle) | Key-scoped merge into `~/.gemini/config/mcp_config.json` | Rejects `/sse` URLs; preserves foreign servers; `mcp-drift.py` coverage |
| Capability receipt | `scripts/cpp-install-receipt.py` (`antigravity` capability, steps, refs) | Same | Planner + receipt round-trip test and `controls/cpp-capability-selection` |
| Counter-model receipts | `scripts/counter-model-receipt.py` `agy` runtime evidence adapter | Same | End-to-end receipt test proving independent model derivation from `agy` session records |

## Consequences

- **Unified updater lands in Wave 1, not Wave 3.** Designing the shared
  discover/refresh/verify/report contract up front ensures Antigravity plugs
  into a single CPP update mechanism alongside Claude Code and Codex rather
  than bolting on another CLI-specific branch.
- **Native plugin vs. loose copies is an encapsulated adapter detail.** Wave 1.1
  validates `agy plugin install` against the shared contract; either packaging
  choice plugs into the same updater and drift-reporting interface.
- **Topic skill bundling improves portability regardless of packaging.**
  Bundling `docs/skills/*.md` into each published topic skill's `references/`
  directory fixes cross-repo invocation for both Option A and Option B.
- **No impact on non-Antigravity hosts.** When Antigravity is absent and the
  `antigravity` capability is not selected, discovery skips it cleanly and
  checks return `not-applicable` (exit 5) with zero noise.

## Reversal trigger

Switch between Option A (native plugin) and Option B (loose managed copies)
behind the shared updater interface if:

1. Option A's plugin staging, update/reinstall, rule-merging, or MCP-scoping
   behavior proves unable to preserve host-local rules/MCP overrides or clean
   drift inspection (fall back to Option B); or
2. Under Option B, Antigravity plugin management later closes any gap found in
   Wave 1.1 (migrate to Option A).

## Planned Rollout (IDD Issue Breakdown)

Following `ISSUE_DRIVEN_DEVELOPMENT.md`, implementation is tracked under Epic
#1876 across three Waves and nine atomic Micro-Issues:

### Wave 1: Unified Updater Design, Packaging Gate, and Skill Pipeline

1. **1.1 - Unified `/cpp:update` harness-refresh contract and Antigravity packaging spike (decision gate)**
   - Define the shared discover -> refresh -> verify -> report contract for
     `/cpp:update` across all installed CPP harnesses (invoking CLI does not
     determine which harnesses refresh; current checkout still refreshes stale
     installations; per-harness fault isolation when one destination is
     unwritable).
   - In an isolated `$HOME` with `agy`, test a representative CPP native plugin
     bundle (`plugin.json` + sample command skill + sample topic skill with
     bundled `references/` + `rules/AGENTS.md` + `mcp_config.json`) via
     `agy plugin install`, delete the build source directory, and verify
     checkout independence, reinstall/orphan cleanup, global rules path + 24 KB
     cap, and drift inspectability.
   - Record measured results in ADR 0014, lock Option A vs. Option B as the
     Antigravity adapter's packaging detail, and flip ADR status to Accepted.
2. **1.2 - Extract harness-neutral skill generation core, bundle topic skill references, and add Antigravity target**
   - Factor shared parsing, bundling, frontmatter escaping, and marker emission
     out of `scripts/codex-skill-sync.py` (parameterizing harness profiles:
     `codex`, `antigravity`).
   - Add minimal Antigravity harness adaptations (`ask_question`,
     `invoke_subagent`, `run_command`, Streamable HTTP MCP).
   - Bundle external `docs/skills/*.md` guides referenced by canonical
     `.claude/skills/*/SKILL.md` into each published skill's `references/`
     directory and rewrite links to `./references/<topic>.md`.
   - Keep `antigravity/skills/` (or plugin build dir) as gitignored build output
     (ADR 0013) with `make antigravity-skills` and `make antigravity-skills-check`
     in CI.
   - Acceptance test: invoke a real published CPP topic skill (e.g.,
     `code-quality`) from an unrelated repository and verify it resolves the
     intended bundled CPP guide rather than failing or reading the other repo's
     files.
   - Depends on: 1.1.
3. **1.3 - Implement shared multi-harness `/cpp:update` driver and Antigravity refresh adapter**
   - Implement the unified host-refresh driver (invoked by `/cpp:update` and
     `Makefile`) that discovers existing CPP-managed installations (Claude Code,
     Codex, Antigravity), refreshes each from the same CPP revision, verifies
     each installed result against a fresh build, and reports per-harness
     outcomes with fault isolation.
   - Implement the Antigravity adapter for the chosen Wave 1.1 packaging
     (Option A: `agy plugin install`; Option B: managed copies into
     `~/.gemini/config/skills/` with injected `metadata.source` on topic skills,
     `GENERATED` markers on command skills, and lockfile
     `~/.gemini/config/.cpp-skill-install.lock`), preserving user-authored
     skills.
   - Add `HOST-SURFACE` annotations, `controls/antigravity-skill-install-fidelity`,
     and the Epic acceptance test (current checkout + stale Codex & `agy` +
     user-authored skill preserved + unwritable-destination isolation).
   - Depends on: 1.2.

### Wave 2: Global Rules, MCP Registration, and Counter-Model Evidence Adapter

4. **2.1 - Global rules sync (`scripts/antigravity-global-rules.py`)**
   - Mirror `~/.claude/CLAUDE.md` verbatim + optional host-local additions file
     into the verified Antigravity global rules path (or plugin rules path per
     Wave 1.1), matching `scripts/codex-global-agents.py`'s verdict contract
     (`current`, `stale`, `hand-edited`, `unmanaged`, `absent`, `not-applicable`,
     `unknown`), plugged into the shared updater summary.
   - Warn when combined size exceeds Antigravity's 24 KB per-file cap.
   - Add `HOST-SURFACE` annotations and `controls/antigravity-global-rules`.
   - Depends on: 1.1.
5. **2.2 - Antigravity MCP registration and drift check**
   - Expose CPP's external MCP servers (`second-opinion` via Streamable HTTP
     `/mcp`, Playwright via stdio) via plugin `mcp_config.json` (Option A) or
     key-scoped merge into `~/.gemini/config/mcp_config.json` (Option B).
   - Preserve unrelated `mcpServers` entries; explicitly reject legacy `/sse`
     endpoints.
   - Extend `scripts/mcp-drift.py` (or add an Antigravity check path) to detect
     stale/deprecated MCP entries.
   - Depends on: 1.1.
6. **2.3 - Antigravity (`agy`) runtime evidence adapter for counter-model receipts**
   - Add an `agy` session/transcript runtime evidence adapter to
     `scripts/counter-model-receipt.py` conforming to
     `docs/agents/counter-model-evidence.md` (schema 5), deriving the
     implementing model set from runtime records (never typed labels or prose).
   - Add an end-to-end receipt test verifying that an `agy` implementer paired
     with an independent reviewer produces a valid `ran` receipt, and that
     self-review or unreadable turns fail closed.
   - Gate full `/flow:auto` parity claims on this issue.
   - Depends on: 1.1.

### Wave 3: Drift Detection, Capability Selection, and Documentation

7. **3.1 - Extend `scripts/install-drift.sh` for Antigravity**
   - Compare the installed Antigravity surface (staged plugin tree under
     Option A, or `~/.gemini/config/skills/` under Option B) against a fresh
     generation (command-derived skills) and canonical `.claude/skills/`
     (topic skills), enforcing a membership floor (explicit expected package
     names; 0 validated is never clean) and ownership boundary.
   - Report `not-applicable` cleanly on hosts without Antigravity.
   - Add tests in `tests/test_install_drift.py`.
   - Depends on: 1.3.
8. **3.2 - Wire `antigravity` capability into `cpp-install-receipt.py` and `/cpp:{init,update,status}`**
   - Update `scripts/cpp-install-receipt.py`: add `antigravity` to
     `CAPABILITY_ORDER`, `CAPABILITY_DEPENDENCIES`, `TIER_CAPABILITIES` /
     `TIER_STEPS` / `CAPABILITY_REQUIRED`, `REFERENCES`, `STEP_REFS`, and
     `OPTIONAL_STEPS`, plus negative-control coverage under
     `controls/cpp-capability-selection` and `controls/cpp-install-receipt`.
   - Wire `antigravity` into `.claude/commands/cpp/{init,update,status}.md`
     (with `/cpp:update` delegating to the Wave 1.3 shared updater rather than
     adding a bespoke Antigravity section) and host-surface disclosures.
   - Add an end-to-end test that plans/selects `["antigravity"]`, writes the
     install receipt, and reads it back through status.
   - Depends on: 1.3, 2.1, 2.2, 3.1.
9. **3.3 - Documentation and `HOST_MANAGED_ARTIFACTS.md` update**
   - Update `docs/HOST_MANAGED_ARTIFACTS.md`, `docs/agents/counter-model-evidence.md`,
     `README.md`, and add an Antigravity setup reference (analogous to
     `.agents/CODEX_SETUP.md`).
   - Verify `host-account-paths-check`, `make verify`, and CI gates pass.
   - Depends on: 2.3, 3.2.
