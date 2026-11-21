# ADR 0014: First-class Antigravity capability as a host-global customization target

- Status: Proposed
- Date: 2026-11-21
- Issue: TBD (epic to be filed upon ADR review)
- Related: ADR 0001 (single-source commands), ADR 0005 (checkout + host-managed
  installs), ADR 0008 (negative-control bound), ADR 0013 (generated mirrors are
  build output, not a tracked tree), #555/#556 (Codex skill generator), #720
  (topic skill provenance & `skills-check.py`), #823/#1029 (`install-drift.sh`),
  #1441 (`codex-global-agents.py`)
- Consulted: Antigravity CLI customization spec (`agy-customizations`)

## The decision, in plain language

Antigravity discovers user-global customizations from `~/.gemini/config/` (skills,
rules, and MCP servers) and project-local customizations from `.agents/`. Like
Claude Code (`~/.claude/`) and Codex (`~/.codex/`), CPP is installed as a
user-global toolkit rather than per-project. Adding Antigravity as an opt-in CPP
capability follows the same architecture established for Codex:

1. **Global install target is `~/.gemini/config/`.** Antigravity skills, global
   rules, and MCP registrations live under `~/.gemini/config/` so they apply
   across every workspace on the host without polluting individual repositories
   or the `Projects/` parent directory.
2. **Both CPP skill surfaces are published into `~/.gemini/config/skills/` as
   managed copies, not symlinks into a checkout.**
   - **Topic skills** (`.claude/skills/<slug>/`): copied with `metadata.source`
     provenance preserved and verified via `skills-check.py --managed-root`.
   - **Command-derived workflow skills** (`.claude/commands/<family>/<cmd>.md`):
     generated on demand from the same single source of truth as Claude and Codex,
     with Antigravity-specific harness adaptations (frontmatter, tool fallbacks,
     `/family:cmd` references), kept as **gitignored build output** (ADR 0013),
     and published into `~/.gemini/config/skills/` with a `GENERATED` ownership
     marker.
3. **Strict ownership boundary.** CPP only writes, updates, or prunes skill
   directories under `~/.gemini/config/skills/` carrying its managed marker
   (`GENERATED` or CPP `metadata.source`). User-authored skills and Antigravity
   built-in skills are never modified or deleted.
4. **Global rules mirror `~/.claude/CLAUDE.md` via opt-in copy + local additions.**
   Following #1441 (`codex-global-agents.py`), a dedicated check/write helper
   keeps Antigravity's global rules file in sync with `~/.claude/CLAUDE.md` plus
   an optional host-local additions file, respecting Antigravity's 24 KB per-file
   cap and refusing to overwrite unmanaged or hand-edited files without `--adopt`.
5. **Global MCP registration uses Streamable HTTP / Stdio in
   `~/.gemini/config/mcp_config.json`.** Antigravity does not support legacy
   HTTP+SSE (`/sse`). CPP registers/checks external MCP servers (e.g.,
   `second-opinion` via `/mcp`, Playwright via stdio) by merging only CPP-owned
   keys while preserving unrelated entries.
6. **Drift detection and negative controls ship with the capability.**
   `install-drift.sh`, `/cpp:status`, `/cpp:init`, `/cpp:update`, `Makefile`,
   `HOST-SURFACE` declarations, and `docs/HOST_MANAGED_ARTIFACTS.md` cover
   Antigravity with the same membership-floor and fidelity guarantees as Codex.

## Why

- **Parity across harnesses.** Developers using Claude Code, Codex, and
  Antigravity on the same machine should have the same IDD/flow/CI/security
  workflows and global rules without manually maintaining parallel skill trees.
- **No checkout coupling.** Pointing Antigravity at a working checkout (via
  symlinks or `skills.json`) ties the live host skill set to whichever branch or
  half-finished edit happens to be checked out in `claude-power-pack` - the
  exact failure mode ADR 0013 rejected for Codex.
- **Harness-accurate instructions.** While Antigravity can technically parse
  `~/.codex/skills/` (`SKILL.md` format), Codex mirrors contain Codex-specific
  tool fallbacks and phrasing. Generating an Antigravity target from the same
  single source avoids Codex leakage while keeping `.claude/commands/` as the
  sole authored source.
- **Shared generator, zero tracked bloat.** Keeping generated Antigravity skill
  output gitignored (ADR 0013) avoids re-introducing the 300+ file mirror churn
  that ADR 0013 eliminated.

## What was rejected

- **Point `~/.gemini/config/skills.json` directly at `{CPP_DIR}/.claude/skills`
  and `~/.codex/skills`.**
  - Ties topic skills to the live branch state of a checkout (rejected in
    ADR 0013).
  - Couples Antigravity to Codex being installed and feeds Codex-adapted
    instructions to Antigravity.
  - Requires mutating a shared JSON manifest that the user may hand-edit for
    personal/team skill directories.
- **Symlink `~/.gemini/config/skills/<skill>` to `{CPP_DIR}/...`.**
  - Same checkout-coupling problem as above, and cannot express generated
    command-derived skills without a tracked or persistent checkout build tree.
- **Place `.agents/skills/` at `~/Projects/`.**
  - `~/Projects/` is a workspace container, not a git repository; Antigravity's
    workspace walk stops at a repository root (`.git`), so skills placed at
    `~/Projects/.agents/skills/` would not be discovered inside individual project
    repos anyway.
- **Ship Antigravity skills as a separate hand-maintained directory.**
  - Violates ADR 0001's single-source-of-truth invariant and guarantees silent
    drift from `.claude/commands/`.

## Host surface and fidelity boundaries

| Host surface | Owner / Write mode | Fidelity / Drift check | Negative control |
|---|---|---|---|
| `~/.gemini/config/skills/<skill>/` | `cpp`, copy (`--install`) | Fresh-build comparison in `install-drift.sh` + `skills-check.py --managed-root`; membership floor prevents empty-dir false greens | `controls/antigravity-skill-install-fidelity` |
| `~/.gemini/config/.cpp-skill-install.lock` | `cpp`, append (`--install`) | Concurrent install serialization (matches `~/.codex/.cpp-skill-install.lock`) | Unit test |
| `~/.gemini/config/GEMINI.md` (exact global rule path verified in Wave 1) | `cpp`, replace (`--write`, `--adopt`) | Report-only `--check` with `current` / `stale` / `hand-edited` / `unmanaged` / `absent` / `not-applicable` verdicts + 24 KB cap warning | `controls/antigravity-global-rules` |
| `~/.gemini/config/mcp_config.json` | `cpp`, merge (opt-in `/cpp:init`) | Key-scoped merge; preserves foreign `mcpServers` entries; rejects `/sse` URLs | Unit test + `mcp-drift.py` |

## Consequences

- **Generator refactor opportunity.** `scripts/codex-skill-sync.py` currently
  hardcodes Codex transforms and paths. Factoring out the shared single-source
  parser/bundler (or parameterizing target harness profiles: `codex`,
  `antigravity`) keeps one generator pipeline instead of duplicating ~2,900 lines.
- **Plain `git pull` does not refresh `~/.gemini/config/skills/`.** Like Codex,
  the host copy updates on `make antigravity-install` or `/cpp:update`, and
  `install-drift.sh` surfaces staleness.
- **No impact on non-Antigravity hosts.** When `~/.gemini/config/` does not
  exist and the `antigravity` capability is not selected, checks return
  `not-applicable` (exit 5) with zero noise.

## Reversal trigger

Retire or simplify the dedicated Antigravity skill generator if:

1. Antigravity adopts a native manifest/plugin format that cleanly replaces
   copied `SKILL.md` directories without checkout coupling, or
2. Maintenance cost of Antigravity-specific harness transforms proves unnecessary
   compared to a single harness-neutral `SKILL.md` output shared with Codex.

## Planned Rollout (IDD Issue Breakdown)

Following `ISSUE_DRIVEN_DEVELOPMENT.md`, implementation is structured as one
Epic, three Waves, and eight atomic Micro-Issues:

### Epic

- **Add first-class Antigravity capability (`~/.gemini/config/`) to CPP** -
  tracks Waves 1-3 to parity with the `codex` capability (skills, global rules,
  MCP, `/cpp:init`/`update`/`status`, drift detection, and negative controls).

### Wave 1: Architecture and Skill Generation/Install Pipeline

1. **1.1 - Ratify ADR 0014 and probe Antigravity global rule/skill discovery**
   - Run an empirical probe (matching #1441's Codex phrase probe) verifying
     `~/.gemini/config/skills/<name>/SKILL.md` discovery (including nested
     `references/` and `scripts/`) and the exact global rules filename loaded
     across all workspaces (`~/.gemini/config/GEMINI.md` vs `AGENTS.md` vs
     `rules/*.md`).
   - Record measured results in ADR 0014 and flip status to Accepted.
2. **1.2 - Extract harness-neutral skill generation core and add Antigravity target**
   - Factor shared parsing, bundling, frontmatter escaping, and marker emission
     out of `scripts/codex-skill-sync.py` (or parameterize harness profiles:
     `codex`, `antigravity`).
   - Add Antigravity harness adaptations (`ask_question`, `invoke_subagent`,
     `run_command`, Streamable HTTP MCP).
   - Keep `antigravity/skills/` gitignored build output (ADR 0013) with
     `make antigravity-skills` and `make antigravity-skills-check` in CI.
   - Depends on: 1.1.
3. **1.3 - Implement Antigravity skill installer (`--install`) for topic and command skills**
   - Publish both command-derived skills (`.claude/commands/`) and canonical
     topic skills (`.claude/skills/`, with `metadata.source` provenance) into
     `~/.gemini/config/skills/`.
   - Use private build + source-parity verification before publish (ADR 0013),
     lock file `~/.gemini/config/.cpp-skill-install.lock`, and strict ownership
     boundary (preserve foreign skills, prune stale CPP-managed orphans).
   - Add `HOST-SURFACE` annotations, `make antigravity-install`, and negative
     control `controls/antigravity-skill-install-fidelity`.
   - Depends on: 1.2.

### Wave 2: Global Rules and MCP Registration

4. **2.1 - Global rules sync (`scripts/antigravity-global-rules.py`)**
   - Mirror `~/.claude/CLAUDE.md` verbatim + optional host-local additions file
     into Antigravity's verified global rules path, matching
     `scripts/codex-global-agents.py`'s verdict contract (`current`, `stale`,
     `hand-edited`, `unmanaged`, `absent`, `not-applicable`, `unknown`).
   - Warn when combined size exceeds Antigravity's 24 KB per-file cap.
   - Add `make antigravity-global-rules`, `HOST-SURFACE` annotations, and
     `controls/antigravity-global-rules`.
   - Depends on: 1.1.
5. **2.2 - Antigravity MCP registration and drift check (`~/.gemini/config/mcp_config.json`)**
   - Key-scoped registration/validation of CPP's external MCP servers
     (`second-opinion` via Streamable HTTP `/mcp`, Playwright via stdio) in
     `~/.gemini/config/mcp_config.json`.
   - Preserve unrelated `mcpServers` entries; explicitly reject legacy `/sse`
     endpoints.
   - Extend `scripts/mcp-drift.py` (or add an Antigravity check path) to detect
     stale/deprecated MCP entries.
   - Depends on: 1.1.

### Wave 3: Drift Detection, Capability Wiring, and Documentation

6. **3.1 - Extend `scripts/install-drift.sh` for Antigravity**
   - Compare `~/.gemini/config/skills/` against a fresh generation
     (command-derived skills) and canonical `.claude/skills/`
     (`skills-check.py --managed-root ~/.gemini/config/skills`), with membership
     floor and ownership boundary.
   - Report `not-applicable` cleanly on hosts without `~/.gemini/config/`.
   - Add tests in `tests/test_install_drift.py`.
   - Depends on: 1.3.
7. **3.2 - Wire `antigravity` capability into `/cpp:init`, `/cpp:update`, and `/cpp:status`**
   - Add `antigravity` as an opt-in capability alongside `codex`, `qwen`, and
     `gemma` in `.claude/commands/cpp/{init,update,status}.md` and host-surface
     disclosures.
   - `/cpp:status` reports installed Antigravity skills, global rules verdict,
     and MCP registration status.
   - Depends on: 1.3, 2.1, 2.2, 3.1.
8. **3.3 - Documentation and `HOST_MANAGED_ARTIFACTS.md` update**
   - Update `docs/HOST_MANAGED_ARTIFACTS.md`, `README.md`, and add an
     Antigravity setup reference (analogous to `.agents/CODEX_SETUP.md`).
   - Verify `host-account-paths-check`, `make verify`, and CI gates pass.
   - Depends on: 3.2.

## Open Questions for Review

1. **Wave 1 skill scope:** Ship both canonical topic skills (`.claude/skills/`)
   and generated command-derived skills (`.claude/commands/`) in Wave 1, or ship
   topic skills first and command-derived skills in a follow-up wave?
2. **Managed copies vs. `skills.json`:** Confirm that ADR 0013's
   no-checkout-coupling rule applies here (favoring managed copies in
   `~/.gemini/config/skills/` over `~/.gemini/config/skills.json` pointing into
   a live checkout).
3. **Generator factoring:** Refactor `scripts/codex-skill-sync.py` into a
   shared multi-harness generator with `codex` and `antigravity` profiles, or
   keep a thin wrapper/separate script initially?
