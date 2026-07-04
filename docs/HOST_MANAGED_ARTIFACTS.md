# Host-Managed Artifacts

This document inventories deploy-critical artifacts that live outside the repo checkout,
classifies them by lifecycle, and describes how drift is detected and reconciled.

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
| `mcp-second-opinion.service` | `mcp-second-opinion/deploy/mcp-second-opinion.service.template` | `~/.config/systemd/user/` or `/etc/systemd/system/` | Reconcilable |
| `mcp-playwright.service` | Retired in #423 - no repo template | `~/.config/systemd/user/` or `/etc/systemd/system/` (only on hosts that ran a pre-#423 install) | Orphan - torn down, not reconciled |

**Retired (#423):** `mcp-playwright.service` no longer maps to a repo template. The CPP
`mcp-playwright-persistent` fork was retired and browser automation moved to the upstream
`@playwright/mcp` server (registered by `/cpp:init` via npx/stdio - no systemd unit and no
container). A leftover `mcp-playwright.service` on a host is now an **orphan**:
`scripts/drift-detect.sh` reports it as a systemd orphan, and `/cpp:update` (via
`.claude/deprecated-mcps.yaml` + `scripts/mcp-drift.py`) tears down the retired Docker
container, `mcp-playwright-persistent:*` image, and MCP registration. It is never
reconciled back from a template.

**Risk:** Templates change in repo but installed units are never auto-updated.
The `install-service.sh` scripts generate units from templates using `sed` substitution
(`${SERVICE_USER}`, `${MCP_SERVER_DIR}`, `${UV_BIN}`). Once installed, the unit is static.

**Detection:** `scripts/drift-detect.sh` regenerates the expected unit from the template
and compares it against the installed version. It also inventories MCP systemd units
that no longer have a repo template, such as the retired `mcp-playwright.service` (#423),
legacy `mcp-coordination.service`, or old alias units, and reports them as orphaned.

**Reconciliation:** Re-run the appropriate install script:
```bash
mcp-second-opinion/scripts/install-service.sh
```

When Docker containers are active for the same MCP server, the default convergence
model is Docker. Use `scripts/drift-detect.sh --fix` to print opt-in cleanup
commands for the losing systemd units before removing them.

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

These artifacts are fully managed by the repo and rebuilt on every deploy:

- **Docker images** - Built from `mcp-*/deploy/Dockerfile` on every `make deploy`
- **Docker Compose config** - `docker-compose.yml` read fresh by local `make docker-up`, `make deploy`, and CI runtime smoke tests
- **CI pipeline** - `.woodpecker.yml` read fresh on every pipeline run
- **CI task manifest** - `.claude/cicd_tasks.yml` read fresh by the deterministic runner
- **Makefile targets** - Executed from repo checkout

## When Bootstrap Runs vs When Deploy Runs

| Script | Runs At | Frequency | Reconciles? |
|--------|---------|-----------|-------------|
| `bash-prep.sh` | Workstation setup | Once | No (idempotent, re-runnable) |
| `install-service.sh` (mcp-second-opinion) | Service setup | Once | No - should be re-run when templates change |
| `bootstrap-secrets.py` | Woodpecker setup | Once | No (manual credential rotation) |
| `make deploy` | Manual local deploy or `/flow:deploy` | Operator-controlled | Yes - rebuilds containers from repo |
| `.woodpecker.yml` runtime-smoke | MCP stack CI validation | Relevant push/PR paths | No - validates an isolated stack, then tears it down |

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
