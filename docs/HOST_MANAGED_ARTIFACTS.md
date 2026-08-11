# Host-Managed Artifacts

This document inventories deploy-critical artifacts that live outside the repo checkout,
classifies them by lifecycle, and describes how drift is detected and reconciled.

## Install path: checkout + tiered symlinks

CPP's own marketplace lane is retired by issue #662 and ADR
[0005](decisions/0005-retire-plugin-marketplace-distribution.md). The repository
checkout is the source of truth; issue #663 restores the tiered `/cpp:init` +
`/cpp:update` symlink command surface as canonical. Existing CPP plugin caches
are migration artifacts, not a supported install lane, and should be removed
with `/plugin uninstall <family>@cpp`.

The artifacts below are the host-managed pieces owned by `/cpp:init` and
`/cpp:update`: command and helper symlinks (as restored by #663), user-level hook
registration, MCP client registration, AWS Secrets Manager access, Woodpecker
bootstrap, and workstation tuning.

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
prompt. Existing symlinks follow the git pull automatically; scripts that are NEW
since the install are linked by `/cpp:update` Step 5b (issue #581 - the flow
allowlist rules match the stable `~/.claude/scripts/` path, so a missing link
degrades the zero-prompt lane).

**Detection:** `/cpp:update` Step 7.7 reports whether the hook is registered;
`/cpp:status` counts installed `~/.claude/scripts/` entries.

**Reconciliation:** Re-run `/cpp:update` (re-links scripts, re-offers the
user-confirmed hook registration). The registration merge is idempotent - it adds
the hook only if that exact command is not already present, preserving all other
`settings.json` keys and entries.

### 5. Retired CPP Plugin Cache

| Artifact | Template Source | Installed Location | Category |
|----------|---------------|--------------------|----------|
| Marketplace clone | Retired in #662 | `~/.claude/plugins/marketplaces/cpp` | Migration artifact |
| Per-family command snapshot | Retired in #662 | `~/.claude/plugins/cache/cpp/<family>/<version>/commands/` | Migration artifact |

**What:** Hosts that used the retired CPP marketplace may still execute commands
from a version-stamped cache. CPP no longer publishes `plugins/<family>/`
sources, so that cache is pending uninstall rather than reconciliation.

**Risk:** High until removed. Issue #662 recorded an executed cache 34 commits /
48 command files behind while `/plugin update` reported version 1.1.0 current.
The stamp did not move with command content, so there was no marketplace
reconciliation path short of per-family uninstall/reinstall.

**Detection:** `scripts/install-drift.sh` (`make install-drift-check`) names
cached families as a retired, non-failing surface. It does not compare content
against the removed plugin trees.

**Migration:** `/plugin uninstall <family>@cpp` for each of the 15 CPP families.
Issue #663's restored tiered symlink surface replaces the cache.

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
