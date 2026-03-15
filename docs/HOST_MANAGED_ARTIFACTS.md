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
| `mcp-playwright.service` | `mcp-playwright-persistent/deploy/mcp-playwright.service.template` | `~/.config/systemd/user/` or `/etc/systemd/system/` | Reconcilable |

**Risk:** Templates change in repo but installed units are never auto-updated.
The `install-service.sh` scripts generate units from templates using `sed` substitution
(`${SERVICE_USER}`, `${MCP_SERVER_DIR}`, `${UV_BIN}`). Once installed, the unit is static.

**Detection:** `scripts/drift-detect.sh` regenerates the expected unit from the template
and compares it against the installed version.

**Reconciliation:** Re-run the appropriate install script:
```bash
mcp-second-opinion/scripts/install-service.sh
mcp-playwright-persistent/deploy/install-service.sh
```

### 2. System Tuning (sysctl)

| Artifact | Source Script | Installed Location | Category |
|----------|-------------|--------------------|----------|
| Kernel parameters | `scripts/bash-prep.sh` | `/etc/sysctl.d/99-claude-code.conf` | Provisioning-only |
| Swap file | `scripts/bash-prep.sh` | `/swapfile` + `/etc/fstab` entry | Provisioning-only |

**Risk:** Low. These are workstation tuning parameters (swappiness, inotify limits) that
rarely change and are not deploy-critical. `bash-prep.sh` is idempotent and safe to re-run.

**Detection:** `scripts/drift-detect.sh` compares live sysctl values against expected targets.

**Reconciliation:** `scripts/bash-prep.sh --apply`

### 3. Go Binary (Woodpecker MCP)

| Artifact | Source Script | Installed Location | Category |
|----------|-------------|--------------------|----------|
| `woodpecker-mcp` binary | `mcp-woodpecker-ci/scripts/setup-go-binary.sh` | `~/go/bin/woodpecker-mcp` | Provisioning-only |
| Woodpecker config | `mcp-woodpecker-ci/scripts/setup-go-binary.sh` | `~/.config/woodpecker-mcp/config.yaml` | Provisioning-only |

**Risk:** Binary installed via `go install` from upstream repo. Version drift is between
upstream releases, not between our repo and host. Config contains credentials fetched
from AWS Secrets Manager.

**Detection:** `scripts/drift-detect.sh` verifies binary is executable and config exists.

**Reconciliation:** `mcp-woodpecker-ci/scripts/setup-go-binary.sh`

### 4. Woodpecker Secrets

| Artifact | Source Script | Installed Location | Category |
|----------|-------------|--------------------|----------|
| `docker.env` | `woodpecker/bootstrap-secrets.py` | `woodpecker/docker.env` | Provisioning-only |

**Risk:** Low. Credentials are fetched from AWS Secrets Manager during initial Woodpecker
setup. The file is gitignored. Credential rotation requires re-running the bootstrap.

**Reconciliation:** `python3 woodpecker/bootstrap-secrets.py`

## Repo-Controlled (No Drift Risk)

These artifacts are fully managed by the repo and rebuilt on every deploy:

- **Docker images** - Built from `mcp-*/deploy/Dockerfile` on every `make deploy`
- **Docker Compose config** - `docker-compose.yml` read fresh on every `docker compose up`
- **CI pipeline** - `.woodpecker.yml` read fresh on every pipeline run
- **CI task manifest** - `.claude/cicd_tasks.yml` read fresh by the deterministic runner
- **Makefile targets** - Executed from repo checkout

## When Bootstrap Runs vs When Deploy Runs

| Script | Runs At | Frequency | Reconciles? |
|--------|---------|-----------|-------------|
| `bash-prep.sh` | Workstation setup | Once | No (idempotent, re-runnable) |
| `install-service.sh` (both) | Service setup | Once | No - should be re-run when templates change |
| `setup-go-binary.sh` | MCP server setup | Once | No (manual upgrade) |
| `bootstrap-secrets.py` | Woodpecker setup | Once | No (manual credential rotation) |
| `make deploy` | Every deploy | Every push to main | Yes - rebuilds containers from repo |
| `.woodpecker.yml` deploy-mcp | Every main push | Automatic | Yes - runs from fresh checkout |

## Drift Detection

Run drift detection manually or as a CI gate:

```bash
# Check for drift
make drift-check

# Check with remediation suggestions
scripts/drift-detect.sh --fix
```

The `drift-check` step is included in the Woodpecker pipeline as a pre-deploy gate
and in the CI task manifest's deploy plan.
