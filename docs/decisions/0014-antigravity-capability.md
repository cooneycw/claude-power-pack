# ADR 0014: First-class Antigravity capability via a unified host-global update procedure

- Status: Proposed
- Date: 2026-11-21
- Issue: #1876
- Related: ADR 0001 section 5 (single-source command layout; its
  plugin-marketplace packaging decision was retired by ADR 0005), ADR 0005
  (retire plugin-marketplace distribution; checkout and executed-copy split),
  ADR 0008 (instrument negative-control bound), ADR 0013 (generated mirrors are
  build output, not a tracked tree), #555/#556 (Codex skill generator), #720
  (topic skill provenance & `skills-check.py`), #823/#1029 (`install-drift.sh`),
  #1441 (`codex-global-agents.py`), #1669 (command word budgets),
  #1710/#1747 (counter-model runtime evidence)
- Consulted: Antigravity CLI built-in `agy-customizations` spec (observed
  2026-11-21: `SKILL.md`, `docs/plugins.md`, `docs/skills.md`, `docs/rules.md`,
  `docs/mcp_servers.md`, `docs/json_configs.md`); PR #1875 Codex and `cp-orch`
  round-1 reviews

## Provenance and adoption boundary

This proposal was originally drafted by AGY/Gemini in
[PR #1875](https://github.com/cooneycw/claude-power-pack/pull/1875), at
`226c0e1a177fd16cb1e0d4bbe5bec9aa7bfc1d99`. A native Codex session adopted and
independently inspected that text on 2026-11-22 against CPP main
`40d25173c8c09987fac851cffa565efdc0f11c72`, preparing this replacement for
fresh receipt-bound review. This provenance does not establish a supported
runtime receipt for the original Gemini work. Historical observations below
remain attributed reports; adoption does not turn them into fresh probes or
receipt-backed implementation evidence. Status remains Proposed until the
owner accepts the ADR.

## The decision, in plain language

The cited Antigravity specification describes user-global customizations in
`~/.gemini/config/` and project-local customizations in `.agents/`; empirical
confirmation remains pending as listed below. Like Claude Code (`~/.claude/`)
and Codex (`~/.codex/`), CPP is installed as a user-global toolkit rather than
per-project. Adding Antigravity as an opt-in CPP capability follows these
principles:

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
3. **Separate thin Antigravity script first; `scripts/codex-skill-sync.py` stays
   untouched.** Wave 1 starts with a separate thin Antigravity generator/bundler
   script (`scripts/antigravity-skill-sync.py`) and leaves
   `scripts/codex-skill-sync.py` untouched so downstream consumers
   (`cooneycw/kyle`'s `core/container_capabilities.py`, `cooneycw/skillc`, and
   `cooneycw/kyle-candidate`) face zero interface risk. Any later unification
   of the Codex and Antigravity generators MUST either:
   - keep the `codex` profile's output byte-identical (same file set, bytes, and
     modes) and keep `scripts/codex-skill-sync.py` callable at its current path
     and CLI, backed by a committed pre- vs. post-refactor tree-comparison
     parity test shown red on a deliberately changed transform; OR
   - be declared a versioned interface change with coordination issues filed in
     `cooneycw/kyle`, `cooneycw/skillc`, and `cooneycw/kyle-candidate` before
     merging.
4. **Published skills are self-contained and kept as gitignored build output
   (ADR 0013).**
   - **Topic skills** (`.claude/skills/<slug>/`): canonical packages omit
     `metadata.source` and 11+ reference external repo-relative guides such as
     `docs/skills/code-quality.md`. Publishing topic skills (under either
     Option A or Option B) MUST bundle referenced `docs/skills/*.md` files into
     each package's `references/` directory and rewrite `SKILL.md` links to
     relative `./references/<topic>.md` paths so they work from any unrelated
     repository.
   - **Command-derived workflow skills** (`.claude/commands/<family>/<cmd>.md`,
     per ADR 0001 section 5): generated on demand with minimal harness-required
     adaptations (frontmatter, tool fallbacks, `/family:cmd` references).
     Whether topic skills ship alone in Wave 1 with command-derived skills in a
     follow-up wave, or both ship together, is an open owner ruling.
   - Under Option B (loose copies), the installer MUST inject `metadata.source`
     pointing to `claude-power-pack/.claude/skills/<slug>` on copied topic
     skills and `GENERATED` markers on command-derived skills, and verify the
     expected package-name set so `skills-check.py --managed-root` never
     reports a 0-validated false green.
5. **Global rules and MCP servers respect Antigravity's native contracts.**
   - Rules mirror `~/.claude/CLAUDE.md` plus optional host-local additions
     (following `#1441`), respecting Antigravity's per-file cap and refusing to
     overwrite unmanaged or hand-edited files without `--adopt` (or shipped as
     plugin `rules/AGENTS.md` if Option A proves clean for host-local
     additions).
   - MCP servers use Streamable HTTP (`/mcp`) or Stdio only; legacy HTTP+SSE
     (`/sse`) is rejected. Because `/cpp:status` and `/cpp:init` act on
     `mcp-drift.py`'s verdict without re-deriving it, Antigravity MCP drift
     detection sits **inside** the ADR 0008 negative-control bound and ships
     with a committed negative control (e.g., a stale `/sse` entry that must be
     reported).
   - All Antigravity check helpers share the same verdict vocabulary as
     `scripts/codex-global-agents.py` (`current`, `stale`, `hand-edited`,
     `unmanaged`, `absent`, `not-applicable` exit 5, `unknown` exit 4).
6. **Capability selection goes through `scripts/cpp-install-receipt.py`.**
   `/cpp:init` delegates capability planning and receipt persistence to
   `scripts/cpp-install-receipt.py`. Adding `antigravity` requires updating its
   planner (`CAPABILITY_ORDER`, `CAPABILITY_DEPENDENCIES`, `TIER_CAPABILITIES` /
   `CAPABILITY_REQUIRED`, `REFERENCES`, `STEP_REFS`, `OPTIONAL_STEPS`) and its
   negative controls alongside the command documents.
7. **Flow parity is explicitly gated on a runtime evidence adapter.**
   CPP's counter-model review receipts (schema 5, `docs/agents/counter-model-evidence.md`)
   derive the implementing model from runtime session records, not typed labels.
   Without an Antigravity (`agy`) runtime evidence adapter, an `agy` session
   cannot issue a normal `ran` counter-model receipt even when reviewed by an
   independent model. Full `/flow:auto` parity therefore requires adding an
   `agy` runtime evidence adapter and end-to-end receipt test (Wave 2.3); until
   that lands, `/flow:auto` support in Antigravity is scoped to skill
   availability, not receipt-backed flow parity.

## Measured facts vs. premises pending Wave 1.1 probe

### Historical observations reported in PR #1875 (2026-11-21)

These are the original draft's reports, not measurements repeated by the
Codex adopter. In particular, plugin list output establishes reported staging
metadata, not installed-byte fidelity, actual invocation, orphan cleanup or
concurrent-write safety; Wave 1.1 must test those separately.

- **Native plugin listing survives source deletion (`agy 1.5.14`):** In an
  isolated `$HOME`, installing a test plugin with `agy plugin install` and
  deleting its source directory left `agy plugin list --json` reporting the
  enabled plugin and its skill intact (measured during PR #1875 review).
- **Canonical topic skills omit `metadata.source` and reference external docs:**
  With raw `.claude/skills/` copies as `--managed-root`, `skills-check.py`
  exited 0, skipped all 18 packages, and validated 0 managed installs. At least
  11 canonical topic skills reference repo-relative `docs/skills/<topic>.md`
  files outside the skill directory.
- **Capability planner gate:** `scripts/cpp-install-receipt.py` currently
  accepts `["codex"]` and rejects `["antigravity"]` with exit 1.
- **Command word budgets on `main`:** `.claude/commands/cpp/init.md`,
  `update.md`, and `status.md` sit at their `#1669` interim caps in
  `.claude/command-word-budgets.tsv` (19,467 / 14,666 / 3,817 words).

### Premises from spec (pending empirical verification in Wave 1.1)

All items below are cited from Antigravity's built-in `agy-customizations`
documentation (observed 2026-11-21) and MUST be verified empirically in
Wave 1.1 before implementation commits to them:

| Premise | Source (`agy-customizations`, 2026-11-21) | What changes if the premise is wrong |
|---|---|---|
| Global loose skills are discovered from `~/.gemini/config/skills/<name>/SKILL.md` | `SKILL.md`, `docs/skills.md` | Option B's destination path changes to the measured global skill root (or Option A becomes mandatory if loose global skills are unsupported). |
| Global rules load from `~/.gemini/config/GEMINI.md` or `AGENTS.md` (or plugin `rules/AGENTS.md`) across all workspaces | `SKILL.md`, `docs/rules.md`, `docs/plugins.md` | Wave 2.1 targets the exact measured global rules path; if only plugin `rules/AGENTS.md` is global, Wave 2.1 merges host-local additions into the plugin rules stage rather than a standalone file. |
| Per-file rule size cap is 24 KB (24,000 bytes) with a 20,000-token aggregate budget | `docs/rules.md` | Wave 2.1's size-warning threshold updates to the measured cap (or is dropped if no cap is enforced). |
| Legacy HTTP+SSE (`/sse`) MCP transport is unsupported; only Streamable HTTP (`/mcp`) and Stdio work | `docs/mcp_servers.md` | If `/sse` is accepted or another transport key is required, Wave 2.2's validator and `mcp-drift.py` negative control update to match the observed transport contract. |

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
- **Protect downstream Codex consumers.** Leaving `scripts/codex-skill-sync.py`
  untouched initially eliminates interface risk to `cooneycw/kyle`,
  `cooneycw/skillc`, and `cooneycw/kyle-candidate` while Antigravity support
  stabilizes.
- **Use the harness's native distribution unit when it fits.** Evaluating
  native `agy` plugins behind the shared updater interface avoids building
  custom copy, orphan-pruning, and `mcp_config.json` merge logic if Antigravity
  already provides those lifecycle guarantees.
- **No checkout coupling (ADR 0005, ADR 0013).** Neither symlinks into a
  checkout nor a `skills.json` pointing at a working tree should tie the live
  host skill set to whichever branch happens to be checked out in
  `claude-power-pack`.
- **Self-contained topic skills and closed ownership blind spots.** Bundling
  `docs/skills/*.md` into each published skill's `references/` directory fixes
  cross-repo invocation; injecting `metadata.source` (Option B) or verifying
  installed plugin bytes directly (Option A) with a membership floor closes the
  0-validated blind spot in `skills-check.py`.
- **Honest parity claims.** Promising `/flow:auto` parity without a counter-model
  runtime evidence adapter for `agy` would break CPP's receipt contract on the
  first real PR.

## What was rejected

- **Add another standalone Antigravity refresh section to `/cpp:update`.**
  - Repeats the per-CLI sprawl already present for Qwen and OpenCode and makes
    each new harness another bespoke maintenance surface.
- **Refactor `scripts/codex-skill-sync.py` in Wave 1.**
  - Introduces unnecessary interface risk to `cooneycw/kyle`, `cooneycw/skillc`,
    and `cooneycw/kyle-candidate` before Antigravity packaging has even passed
    its Wave 1.1 spike. Deferred to a later, parity-tested unification.
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
  - Violates ADR 0001 section 5's single-source-of-truth invariant and
    guarantees silent drift from `.claude/commands/`.

## Host surface and fidelity boundaries

The exact host paths in the skill, rules, and MCP rows depend on the Wave 1.1
packaging gate (Option A: native `agy` plugin vs. Option B: managed loose
copies), both invoked through the shared `/cpp:update` harness-refresh driver.
Both options enforce fresh-build parity, membership floors, and negative
controls.

| Surface | Option A (Native plugin) | Option B (Loose managed copies) | Fidelity / Drift check & Negative control (ADR 0008) |
|---|---|---|---|
| Shared updater | One `/cpp:update` harness-refresh driver discovering and updating all installed CPP harnesses | Same | Acceptance test: current checkout + stale Codex & `agy` + user skill + unwritable-destination fault isolation |
| Skills (command + topic) | Installed CPP plugin via `agy plugin install` (checkout-independent staged copy) | `~/.gemini/config/skills/<skill>/` (`GENERATED` marker on command skills; injected `metadata.source` on topic skills) | Fresh-build comparison in `install-drift.sh` with membership floor; `controls/antigravity-skill-install-fidelity`; cross-repo topic-skill invocation test |
| Concurrency lock | Native serialization must be demonstrated in Wave 1.1; do not assume it from plugin listing | Advisory `flock` on `~/.gemini/config/.cpp-skill-install.lock` (matching Codex installer; kernel releases lock on process exit so stale locks cannot persist) | Unit test for concurrent install serialization |
| Global rules | Plugin `rules/AGENTS.md` (plus host-local additions check) or verified global rules file | Verified `~/.gemini/config/<global-rules>` (`--write`, `--adopt`) | Report-only `--check` (`current`/`stale`/`hand-edited`/`unmanaged`/`absent`/`not-applicable` exit 5/`unknown` exit 4) + cap warning; `controls/antigravity-global-rules` |
| MCP servers | Plugin `mcp_config.json` (scoped to plugin lifecycle) | Key-scoped merge into `~/.gemini/config/mcp_config.json` | Inside ADR 0008 bound (acted on by `/cpp:init` and `/cpp:status`): committed negative control with stale `/sse` entry that must be reported by `mcp-drift.py`; preserves foreign servers |
| Capability receipt | `scripts/cpp-install-receipt.py` (`antigravity` capability, steps, refs) | Same | Planner + receipt round-trip test and `controls/cpp-capability-selection` |
| Counter-model receipts | `scripts/counter-model-receipt.py` `agy` runtime evidence adapter | Same | End-to-end receipt test proving independent model derivation from `agy` session records |

## Consequences

- **Unified updater lands in Wave 1, not Wave 3.** Designing the shared
  discover/refresh/verify/report contract up front ensures Antigravity plugs
  into a single CPP update mechanism alongside Claude Code and Codex rather
  than bolting on another CLI-specific branch.
- **Zero immediate risk to Codex consumers.** Keeping
  `scripts/codex-skill-sync.py` untouched in Wave 1 avoids breaking `kyle`,
  `skillc`, and `kyle-candidate`. Any later unification is gated by a committed
  byte-identical parity test or coordinated downstream versioned-interface
  issues.
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

Following `ISSUE_DRIVEN_DEVELOPMENT.md`, the planned implementation breakdown
belongs under Epic #1876 across three Waves and nine atomic Micro-Issues.
This adoption changes documentation only and starts no code wave.

The owner's current slow-unpark rule supersedes the earlier parked-until-pin
wording: **one AGY PR in flight at a time**, PR CI only for full-suite
validation, and Kyle series-27 work has priority. The replacement ADR PR may
temporarily overlap #1875 solely to supersede it; this does not authorize a
parallel code PR. The owner must accept this ADR and it must merge before any
code under the epic merges. **Kyle's CPP pin stays at v13.0.0**; a new pin is
not a prerequisite for this paced preparation, and this ADR does not authorize
changing Kyle's pin. No heavy local full-suite runs or direct main pushes.

## Open owner decisions

1. **Packaging:** Option A (native plugin) or Option B (managed loose copies),
   based on Wave 1.1 evidence. Neither is selected by this adoption.
2. **Wave 1 skill scope:** topic-only or topic plus command-derived skills.
   If topic-only, name a follow-up delivery item for command-derived skills
   and real AGY invocation of `cpp-update` before claiming workflow parity.
   Full flow parity also depends on the runtime evidence adapter in 2.3.
3. **Initial harness scope:** the target contract says all installed CPP-managed
   harnesses, while item 1.3 currently enumerates Claude Code, Codex and AGY.
   The owner must decide whether Qwen, OpenCode and other managed installations
   join the initial shared driver or receive explicitly named follow-up work.
   An initial subset must be reported as partial scope, not all-harness parity.
4. **ADR acceptance:** the owner rules on acceptance after reviewing the
   proposal and premise-probe evidence. A review approval is not acceptance.

## Wave details

### Wave 1: Unified Updater Design, Packaging Gate, and Skill Pipeline

1. **1.1 - Unified `/cpp:update` harness-refresh contract and Antigravity packaging spike (decision gate)**
   - Define the shared discover -> refresh -> verify -> report contract for
     `/cpp:update` across all installed CPP harnesses (invoking CLI does not
     determine which harnesses refresh; current checkout still refreshes stale
     installations; per-harness fault isolation when one destination is
     unwritable).
   - Empirically verify every spec premise listed above with `agy` in a
     disposable, verified isolated profile/config root (never repurpose HOME
     inside a running session or copy credentials): global skill discovery path,
     exact global rules path and
     per-file cap, MCP transport contract, and a representative CPP native
     plugin bundle (`plugin.json` + sample skills with bundled `references/` +
     `rules/AGENTS.md` + `mcp_config.json`) via `agy plugin install` (checkout
     independence, reinstall/orphan cleanup, foreign-content preservation,
     installed-byte fidelity, actual invocation and concurrent-write safety).
     Use fresh-session comparison cases and retain exact inputs and artifacts;
     if supported isolation cannot be demonstrated, stop configuration probes.
   - Record measured results in ADR 0014; **the owner rules on Option A vs.
     Option B, Wave 1 skill scope, and ADR acceptance.**
2. **1.2 - Implement thin Antigravity skill bundler/generator (`scripts/antigravity-skill-sync.py`)**
   - Leave `scripts/codex-skill-sync.py` untouched (no changes to Codex output
     or CLI).
   - Bundle external `docs/skills/*.md` guides referenced by canonical
     `.claude/skills/*/SKILL.md` into each published skill's `references/`
     directory and rewrite links to `./references/<topic>.md`.
   - Per the owner's Wave 1 scope ruling, include topic skills first (with
     command-derived skills in a follow-up wave) or both topic and
     command-derived skills.
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
     Codex, Antigravity; Qwen/OpenCode/others per the open owner scope ruling),
     refreshes each from the same CPP revision, verifies
     each installed result against a fresh build, and reports per-harness
     outcomes with fault isolation.
   - Implement the Antigravity adapter for the chosen Wave 1.1 packaging
     (Option A: `agy plugin install`; Option B: managed copies into
     `~/.gemini/config/skills/` with injected `metadata.source` on topic skills,
     `GENERATED` markers on command skills, and advisory `flock` on
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
     (`current`, `stale`, `hand-edited`, `unmanaged`, `absent`, `not-applicable`
     exit 5, `unknown` exit 4), plugged into the shared updater summary.
   - Warn when combined size exceeds the measured per-file cap.
   - Add `HOST-SURFACE` annotations and `controls/antigravity-global-rules`.
   - Depends on: 1.1.
5. **2.2 - Antigravity MCP registration and drift check**
   - Expose CPP's external MCP servers (`second-opinion` via Streamable HTTP
     `/mcp`, Playwright via stdio) via plugin `mcp_config.json` (Option A) or
     key-scoped merge into `~/.gemini/config/mcp_config.json` (Option B).
   - Preserve unrelated `mcpServers` entries; explicitly reject legacy `/sse`
     endpoints.
   - Extend `scripts/mcp-drift.py` with an Antigravity check path and a
     committed ADR 0008 negative control (a stale `/sse` entry that must be
     reported).
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
     generation (command-derived skills, when enabled) and canonical
     `.claude/skills/` (topic skills), enforcing a membership floor (explicit
     expected package names; 0 validated is never clean) and ownership boundary.
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
   - **Word-budget accounting (`#1669`):** `.claude/commands/cpp/init.md`,
     `update.md`, and `status.md` sit at their interim caps in
     `.claude/command-word-budgets.tsv` (19,467 / 14,666 / 3,817 words). Every
     added word in Wave 3.2 MUST be paid for via offsets (accompanied by an
     old-vs-new instruction audit - delegating `/cpp:update`'s per-CLI refresh
     blocks to the Wave 1.3 shared driver is expected to reclaim words in
     `update.md`) or an explicit owner cap ruling before merge.
   - Add an end-to-end test that plans/selects `["antigravity"]`, writes the
     install receipt, and reads it back through status.
   - Depends on: 1.3, 2.1, 2.2, 3.1.
9. **3.3 - Documentation and `HOST_MANAGED_ARTIFACTS.md` update**
   - Update `docs/HOST_MANAGED_ARTIFACTS.md`, `docs/agents/counter-model-evidence.md`,
     `README.md`, and add an Antigravity setup reference (analogous to
     `.agents/CODEX_SETUP.md`).
   - Verify `host-account-paths-check`, `make verify`, and CI gates pass.
   - Depends on: 2.3, 3.2.
