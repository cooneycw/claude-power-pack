# Host-Managed Artifacts

This document inventories deploy-critical artifacts that live outside the repo checkout,
classifies them by lifecycle, and describes how drift is detected and reconciled.

## Install path: `/plugin` first, this document is the fallback

CPP's command/skill/hook surface installs through Claude Code's `/plugin`
(`/plugin marketplace add cooneycw/claude-power-pack` then `/plugin install
<family>@cpp`; ADR [0001](decisions/0001-plugin-marketplace-packaging.md), epic
#417 Phase B). Those surfaces - commands, skills, the bundled PostToolUse masking
hook, and the `second-opinion` `.mcp.json` client pointer - are versioned and
updated by `/plugin` and are **not** host-managed artifacts: a plugin user does
not symlink them, and the retired dual-surface machinery (the `~/.claude/skills`
global mirror, `flow-skill-sync.py`, `skill-drift.py`) no longer exists (#480).

The artifacts below are the **non-plugin infra** a plugin install cannot deliver -
the documented fallback `/cpp:init` / `/cpp:update` still own: host scripts +
user-level hook registration, the external Second Opinion MCP server pointer and
`@playwright/mcp` registration, AWS Secrets Manager access, Woodpecker bootstrap,
and workstation tuning. This document is the inventory of that fallback; it does
not cover the plugin-delivered surfaces above.

## Classification

| Category | Description |
|----------|-------------|
| **Provisioning-only** | Run once during initial setup. Changes require manual re-run. |
| **Reconcilable** | Can (and should) be re-applied on every deploy to stay in sync. |
| **Repo-controlled** | Fully managed by repo code - Docker images, Makefile targets, CI steps. |

## Artifact Inventory

### 1. Systemd Service Units

| Artifact | Template Source | Installed Location | Category |
|----------|---------------|--------------------|----------|
| `mcp-second-opinion.service` | Retired in #469 - no repo template | `~/.config/systemd/user/` or `/etc/systemd/system/` (only on hosts that ran a pre-#469 install) | Orphan - torn down, not reconciled |
| `mcp-playwright.service` | Retired in #423 - no repo template | `~/.config/systemd/user/` or `/etc/systemd/system/` (only on hosts that ran a pre-#423 install) | Orphan - torn down, not reconciled |

**CPP ships no first-party MCP systemd units.** Neither unit above maps to a repo
template any more: `mcp-second-opinion` moved to its own external repo (#469, which also
retired CPP's entire Docker MCP runtime) and the `mcp-playwright-persistent` fork was
retired for the upstream `@playwright/mcp` npx server (#423). A leftover unit for either
on a host is now an **orphan**: `scripts/drift-detect.sh` reports it as a systemd orphan,
and `/cpp:update` (via `.claude/deprecated-mcps.yaml` + `scripts/mcp-drift.py`) tears down
the retired container, `mcp-<name>:*` image, and any MCP registration. A **running**
container that merely shares a deprecated name but belongs to an external compose project
(or runs a non-CPP image) is auto-protected by provenance and never torn down (issue #520) -
so the live external `second-opinion` / `aws-secrets-agent` server survives an update.
Neither unit is ever reconciled back from a template.

**Detection:** `scripts/drift-detect.sh` inventories installed `mcp-*` systemd units that
no longer have a repo template - such as the retired `mcp-second-opinion.service` (#469),
`mcp-playwright.service` (#423), or legacy `mcp-coordination.service` - and reports them as
orphaned for opt-in teardown. Use `scripts/drift-detect.sh --fix` to print the cleanup
commands.

### 2. System Tuning (sysctl)

| Artifact | Source Script | Installed Location | Category |
|----------|-------------|--------------------|----------|
| Kernel parameters | `scripts/bash-prep.sh` | `/etc/sysctl.d/99-claude-code.conf` | Provisioning-only |
| Swap file | `scripts/bash-prep.sh` | `/swapfile` + `/etc/fstab` entry | Provisioning-only |

**Risk:** Low. These are workstation tuning parameters (swappiness, inotify limits) that
rarely change and are not deploy-critical. `bash-prep.sh` is idempotent and safe to re-run.

**Detection:** `scripts/drift-detect.sh` compares live sysctl values against expected targets.

**Reconciliation:** `scripts/bash-prep.sh --apply`

### 3. Woodpecker Secrets

| Artifact | Source Script | Installed Location | Category |
|----------|-------------|--------------------|----------|
| `docker.env` | `woodpecker/bootstrap-secrets.py` | `woodpecker/docker.env` | Provisioning-only |

**Risk:** Low. Credentials are fetched from AWS Secrets Manager during initial Woodpecker
setup. The file is gitignored. Credential rotation requires re-running the bootstrap.

**Reconciliation:** `python3 woodpecker/bootstrap-secrets.py`

### 4. User-Level Hook Registration + Scripts

| Artifact | Template Source | Installed Location | Category |
|----------|---------------|--------------------|----------|
| `~/.claude/scripts/*.sh` | `scripts/*.sh` (symlinks) | `~/.claude/scripts/` | Reconcilable |
| PermissionRequest census hook | `scripts/hook-permission-census.sh` | `~/.claude/settings.json` (`hooks.PermissionRequest`) | Reconcilable |

**What:** Tier 2 install symlinks every `scripts/*.sh` (including
`hook-permission-census.sh`) into `~/.claude/scripts/`, and `/cpp:init` /
`/cpp:update` Step 7.7 register the observe-only permission-prompt census hook in
the user-level `~/.claude/settings.json` (issue #482). The hook fires on every
permission dialog across every project and appends a risk-rated `permission-prompt`
record to that project's `.claude/friction.jsonl` for `/self-improvement:retro`.

**Risk:** Low. The hook is observe-only (never emits a permission decision) and
fail-open (never exits non-zero, swallows an unwritable buffer), so a stale or
missing registration degrades capture but never blocks a session or a permission
prompt. The symlinks are re-pointed on every `/cpp:update`.

**Detection:** `/cpp:update` Step 7.7 reports whether the hook is registered;
`/cpp:status` counts installed `~/.claude/scripts/` entries.

**Reconciliation:** Re-run `/cpp:update` (re-links scripts, re-offers the
user-confirmed hook registration). The registration merge is idempotent - it adds
the hook only if that exact command is not already present, preserving all other
`settings.json` keys and entries.

## Repo-Controlled (No Drift Risk)

These artifacts are fully managed by the repo:

- **CI pipeline** - `.woodpecker.yml` read fresh on every pipeline run
- **CI task manifest** - `.claude/cicd_tasks.yml` read fresh by the deterministic runner
- **Makefile targets** - Executed from repo checkout

## When Bootstrap Runs vs When Deploy Runs

| Script | Runs At | Frequency | Reconciles? |
|--------|---------|-----------|-------------|
| `bash-prep.sh` | Workstation setup | Once | No (idempotent, re-runnable) |
| `bootstrap-secrets.py` | Woodpecker setup | Once | No (manual credential rotation) |
| `make deploy` | Manual local deploy or `/flow:deploy` | Operator-controlled | No-op - CPP ships no deployable services since #469 |

## Drift Detection

Run drift detection manually when reconciling workstation-managed artifacts:

```bash
# Check for drift
make drift-check

# Check with remediation suggestions
scripts/drift-detect.sh --fix
```

The drift report includes deployment-model checks for MCP servers:

- Docker/systemd conflicts for the same server
- failed or stuck MCP systemd units
- orphaned MCP systemd units that the repo no longer ships
- port binding conflicts on MCP ports 8080-8089

The script only reports and suggests remediation. Cleanup remains opt-in.

The `drift_check` task remains available in the CI task manifest's deploy plan for
operator-driven deploy workflows, but the Woodpecker CI pipeline does not run it as
a pre-deploy gate.
