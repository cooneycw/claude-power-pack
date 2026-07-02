---
description: Update Claude Power Pack to the latest version
allowed-tools: Bash(git:*), Bash(ls:*), Bash(test:*), Bash(readlink:*), Bash(cat:*), Bash(uv:*), Bash(claude mcp list:*), Bash(claude mcp add:*), Bash(claude mcp remove:*), Bash(sudo systemctl:*), Bash(systemctl:*), Bash(command -v:*), Bash(ln:*), Bash(mkdir:*), Bash(cp:*), Bash(diff:*), Bash(find:*), Bash(grep:*), Bash(sed:*), Bash(awk:*), Bash(sort:*), Bash(mktemp:*), Bash(rm:*), Bash(sudo rm:*), Bash(curl:*), Bash(ss:*), Bash(docker:*), Bash(make:*), Bash(python3:*), AskUserQuestion
---

# Claude Power Pack Update

Update CPP to the latest version, detect MCP server and skill drift, and offer guided remediation.

---

## Step 1: Locate CPP Source

```bash
CPP_DIR=""
for dir in ~/Projects/claude-power-pack /opt/claude-power-pack ~/.claude-power-pack; do
  if [ -d "$dir" ] && [ -f "$dir/CLAUDE.md" ]; then
    CPP_DIR="$dir"
    break
  fi
done

if [ -z "$CPP_DIR" ]; then
  echo "ERROR: claude-power-pack not found"
  echo "Please clone it first:"
  echo "  git clone https://github.com/cooneycw/claude-power-pack ~/Projects/claude-power-pack"
  exit 1
fi

echo "Found claude-power-pack at: $CPP_DIR"
```

---

## Step 2: Check Current Version and Remote

```bash
cd "$CPP_DIR"

# Get current version from CHANGELOG.md
CURRENT_VERSION=$(grep -oP '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | head -1 || echo "unknown")
CURRENT_COMMIT=$(git rev-parse --short HEAD)
CURRENT_BRANCH=$(git branch --show-current)

echo "Current: v$CURRENT_VERSION ($CURRENT_COMMIT) on $CURRENT_BRANCH"

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo ""
  echo "WARNING: Uncommitted changes detected in CPP repo"
  git status --short
  echo ""
  echo "These changes may be overwritten by the update."
fi

# Fetch latest from origin
echo ""
echo "Fetching latest from origin..."
git fetch origin 2>&1

# Compare with remote
BEHIND=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count 2>/dev/null || echo "0")
AHEAD=$(git rev-list origin/$CURRENT_BRANCH..HEAD --count 2>/dev/null || echo "0")

if [ "$BEHIND" -eq 0 ]; then
  echo ""
  echo "Already up to date!"
else
  echo ""
  echo "$BEHIND commit(s) behind origin/$CURRENT_BRANCH"
  echo ""
  echo "New changes:"
  git log --oneline HEAD..origin/$CURRENT_BRANCH
fi
```

Report the version comparison to the user.

---

## Step 3: Pull Updates

**Only if behind remote.** Ask user for confirmation before pulling.

If there are uncommitted changes, warn and ask if they want to stash first.

```bash
cd "$CPP_DIR"

# Stash if needed
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Stashing uncommitted changes..."
  git stash push -m "cpp-update auto-stash $(date +%Y%m%d-%H%M%S)"
fi

# Pull latest
git pull origin $CURRENT_BRANCH

NEW_COMMIT=$(git rev-parse --short HEAD)
NEW_VERSION=$(grep -oP '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | head -1 || echo "unknown")
echo ""
echo "Updated: v$CURRENT_VERSION -> v$NEW_VERSION ($NEW_COMMIT)"
```

---

## Step 4: Update Dependencies (Tier 3)

If MCP server venvs exist, sync dependencies to pick up any new packages:

```bash
cd "$CPP_DIR"

for server_dir in mcp-second-opinion mcp-playwright-persistent; do
  if [ -d "$server_dir/.venv" ]; then
    echo ""
    echo "Syncing dependencies for $server_dir..."
    cd "$CPP_DIR/$server_dir"
    uv sync
    echo "Done: $server_dir dependencies updated"
  fi
done
```

---

## Step 4.5: Legacy Systemd Teardown

Before refreshing Docker, detect legacy MCP systemd units in both system and
user scopes. This is a migration step only: systemd is no longer a supported
runtime model. Do not stop, disable, or remove anything until the user confirms.

Known legacy unit names to scan:

- `mcp-second-opinion`
- `second-opinion`
- `mcp-playwright`
- `mcp-playwright-persistent`
- `playwright-persistent`
- `mcp-evaluate`
- `evaluate`
- `mcp-coordination`
- `coordination`

Also include discovered units matching `mcp-*`, `nano-*`, or `*coordination*`
from `/etc/systemd/system/`, `~/.config/systemd/user/`, and systemd's unit
indexes.

```bash
cd "$CPP_DIR"

LEGACY_SYSTEMD_REPORT="$(mktemp)"
LEGACY_SYSTEMD_FOUND=false
SYSTEMD_TEARDOWN_STATUS="none"
: > "$LEGACY_SYSTEMD_REPORT"

collect_systemd_units() {
  scope="$1"

  if [ "$scope" = "user" ]; then
    {
      find "$HOME/.config/systemd/user" -maxdepth 1 -type f \
        \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
        -printf '%f\n' 2>/dev/null || true
      systemctl --user list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
      systemctl --user list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination|second-opinion|playwright-persistent|evaluate|coordination)$' | sort -u || true
  else
    {
      find /etc/systemd/system -maxdepth 1 -type f \
        \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
        -printf '%f\n' 2>/dev/null || true
      systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
      systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination|second-opinion|playwright-persistent|evaluate|coordination)$' | sort -u || true
  fi
}

KNOWN_LEGACY_SYSTEMD_UNITS=$(cat <<'EOF'
mcp-second-opinion
second-opinion
mcp-playwright
mcp-playwright-persistent
playwright-persistent
mcp-evaluate
evaluate
mcp-coordination
coordination
EOF
)

USER_LEGACY_SYSTEMD_UNITS="$(collect_systemd_units user)"
SYSTEM_LEGACY_SYSTEMD_UNITS="$(collect_systemd_units system)"
ALL_LEGACY_SYSTEMD_UNITS="$(
  {
    printf '%s\n' "$KNOWN_LEGACY_SYSTEMD_UNITS"
    printf '%s\n' "$USER_LEGACY_SYSTEMD_UNITS"
    printf '%s\n' "$SYSTEM_LEGACY_SYSTEMD_UNITS"
  } | sed '/^$/d' | sort -u
)"

for unit in $ALL_LEGACY_SYSTEMD_UNITS; do
  user_path="$HOME/.config/systemd/user/${unit}.service"
  system_path="/etc/systemd/system/${unit}.service"

  if printf '%s\n' "$USER_LEGACY_SYSTEMD_UNITS" | grep -qx "$unit"; then
    active="$(systemctl --user is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl --user is-enabled "$unit" 2>/dev/null || true)"
    failed="$(systemctl --user is-failed "$unit" 2>/dev/null || true)"
    [ -f "$user_path" ] || user_path="-"
    printf 'user\t%s\t%s\t%s\t%s\t%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}" "${failed:-unknown}" "$user_path" >> "$LEGACY_SYSTEMD_REPORT"
    LEGACY_SYSTEMD_FOUND=true
  fi

  if printf '%s\n' "$SYSTEM_LEGACY_SYSTEMD_UNITS" | grep -qx "$unit"; then
    active="$(systemctl is-active "$unit" 2>/dev/null || true)"
    enabled="$(systemctl is-enabled "$unit" 2>/dev/null || true)"
    failed="$(systemctl is-failed "$unit" 2>/dev/null || true)"
    [ -f "$system_path" ] || system_path="-"
    printf 'system\t%s\t%s\t%s\t%s\t%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}" "${failed:-unknown}" "$system_path" >> "$LEGACY_SYSTEMD_REPORT"
    LEGACY_SYSTEMD_FOUND=true
  fi
done

if [ "$LEGACY_SYSTEMD_FOUND" = "true" ]; then
  echo ""
  echo "Legacy systemd MCP units detected:"
  printf '%-8s %-32s %-12s %-12s %-12s %s\n' "Scope" "Unit" "Active" "Enabled" "Failed" "Path"
  printf '%-8s %-32s %-12s %-12s %-12s %s\n' "-----" "----" "------" "-------" "------" "----"
  awk -F '\t' '{printf "%-8s %-32s %-12s %-12s %-12s %s\n", $1, $2, $3, $4, $5, $6}' "$LEGACY_SYSTEMD_REPORT"
else
  echo ""
  echo "No legacy systemd MCP units detected."
fi
```

If legacy units were found, ask the user before teardown:

```
Legacy systemd MCP units can conflict with the Docker MCP stack by binding the
same ports or reviving stale server versions. Remove the listed systemd units
before refreshing Docker?
```

Options:
- **Tear down legacy systemd** - Stop, disable, remove unit files, reload systemd, then continue Docker refresh
- **Skip teardown** - Leave systemd units in place and continue with a port-conflict warning

If the user confirms teardown, run:

```bash
if [ "$LEGACY_SYSTEMD_FOUND" = "true" ]; then
  REMOVED_SYSTEMD_UNITS=0

  while IFS=$'\t' read -r scope unit active enabled failed path; do
    echo ""
    echo "Removing legacy $scope systemd unit: $unit"

    if [ "$scope" = "user" ]; then
      systemctl --user stop "$unit" 2>/dev/null || true
      systemctl --user disable "$unit" 2>/dev/null || true
      if [ "$path" != "-" ] && [ -f "$path" ]; then
        rm -f "$path"
      fi
      systemctl --user daemon-reload
    else
      sudo systemctl stop "$unit" 2>/dev/null || true
      sudo systemctl disable "$unit" 2>/dev/null || true
      if [ "$path" != "-" ] && [ -f "$path" ]; then
        sudo rm -f "$path"
      fi
      sudo systemctl daemon-reload
    fi

    REMOVED_SYSTEMD_UNITS=$((REMOVED_SYSTEMD_UNITS + 1))
  done < "$LEGACY_SYSTEMD_REPORT"

  SYSTEMD_TEARDOWN_STATUS="removed ${REMOVED_SYSTEMD_UNITS} unit scope(s)"
  echo ""
  echo "Legacy systemd teardown complete: $SYSTEMD_TEARDOWN_STATUS"
fi
```

If the user skips teardown, set `SYSTEMD_TEARDOWN_STATUS="skipped"` and warn:

```
WARNING: Legacy systemd units were left installed. Docker refresh will continue,
but stale units may still bind MCP ports or restart old server versions.
Run /cpp:update again and choose teardown if Docker health fails due to port use.
```

---

## Step 5: Docker Refresh Runtime

CPP now uses Docker with local builds as the only supported MCP runtime. Before
refreshing, verify Docker and Docker Compose are available. Do not restart
systemd units and do not offer a venv-only runtime branch.

```bash
cd "$CPP_DIR"

DEPLOY_MODEL="docker"
DOCKER_READY=false

if ! command -v docker &>/dev/null; then
  echo "ERROR: Docker is required for CPP Tier 3 runtime refresh."
  echo "Install Docker Engine or Docker Desktop, then rerun /cpp:update."
  exit 1
fi

if ! docker compose version &>/dev/null; then
  echo "ERROR: Docker Compose v2 is required for CPP Tier 3 runtime refresh."
  echo "Install the Docker Compose plugin, then rerun /cpp:update."
  exit 1
fi

if [ ! -f "$CPP_DIR/docker-compose.yml" ]; then
  echo "ERROR: docker-compose.yml not found in $CPP_DIR"
  exit 1
fi

DOCKER_READY=true

echo ""
echo "Refreshing Docker MCP stack..."
make docker-refresh PROFILE="core browser"
DOCKER_REFRESH_RC=$?
if [ "$DOCKER_REFRESH_RC" -ne 0 ]; then
  echo "ERROR: Docker refresh failed or one or more containers are unhealthy."
  exit "$DOCKER_REFRESH_RC"
fi

echo ""
echo "Verifying Docker MCP health..."
make docker-health PROFILE="core browser"
DOCKER_HEALTH_RC=$?
if [ "$DOCKER_HEALTH_RC" -ne 0 ]; then
  echo "ERROR: Docker health verification failed."
  exit "$DOCKER_HEALTH_RC"
fi
```

Report the Docker refresh and health result to the user:

```
Runtime Refresh:
  Model: Docker (local build)
  Docker: rebuilt/restarted/healthy
  Health: make docker-health passed
  Legacy systemd: {none|removed N unit scope(s)|skipped with warning}
```

---

## Step 6: MCP Server Drift Detection

After pulling and refreshing Docker, scan for drift between what the repo ships
and what is actually installed/running. Docker is the only valid deployment
target. Any remaining systemd unit is a legacy migration finding, not a runtime
option to repair or restart.

### 6a: Build Inventory

Build two lists - what the repo ships for Docker vs what is installed/running -
then compare.

**Repo inventory** - scan for active MCP servers the repo provides:

```bash
cd "$CPP_DIR"

echo "=== Repo MCP Server Inventory ==="

# Active servers from docker-compose.yml (uncommented services with ports)
echo "Docker-compose services:"
grep -E '^\s{2}[a-z].*:$' docker-compose.yml | grep -v '^\s*#' | sed 's/://;s/^ */  /'

echo ""
echo "Historical systemd service files (legacy reference only):"
find . -path '*/deploy/*.service' -type f | sort | while read f; do
  echo "  $f"
done

echo ""
echo "Dockerfiles:"
find . -path '*/deploy/Dockerfile' -type f | sort | while read f; do
  echo "  $f"
done
```

**Installed inventory** - scan what is currently running/registered:

```bash
echo ""
echo "=== Installed MCP Inventory ==="

echo "Docker containers:"
if [ "$DOCKER_READY" = "true" ]; then
  docker compose --profile core --profile browser ps 2>/dev/null || echo "  (unavailable)"
else
  echo "  (docker unavailable)"
fi

echo ""
echo "Legacy systemd units (migration required if present):"
LEGACY_SYSTEMD_INVENTORY="$(
  {
    find "$HOME/.config/systemd/user" /etc/systemd/system -maxdepth 1 -type f \
      \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
      -printf '%f\n' 2>/dev/null || true
    systemctl --user list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    systemctl --user list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
    systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
  } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination|second-opinion|playwright-persistent|evaluate|coordination)$' | sort -u || true
)"
if [ -n "$LEGACY_SYSTEMD_INVENTORY" ]; then
  printf '%s\n' "$LEGACY_SYSTEMD_INVENTORY"
else
  echo "  (none)"
fi
```

Run the drift helper for its raw inventory if available:

```bash
if [ -x "$CPP_DIR/scripts/drift-detect.sh" ]; then
  "$CPP_DIR/scripts/drift-detect.sh" --fix || DRIFT_FOUND=true
fi
```

### 6b: Detect Drift

Compare the inventories and classify each finding. Use the following logic:

**Known repo servers** (from docker-compose.yml, not commented out):
- `mcp-second-opinion` (port 8080, profile: core)
- `mcp-playwright-persistent` (port 8081, profile: browser)

**Deprecated servers** (commented out in docker-compose.yml):
- `mcp-evaluate` (deprecated - absorbed into /evaluate:issue skill)

**For each known repo server**, check:
1. Is there a Docker container running/healthy?
2. Is it registered in `claude mcp list`?
3. Is the port listening?
4. Is any legacy systemd unit still installed for that server?

**For each installed legacy systemd service matching mcp-*, nano-*, or
coordination**, classify it as:

1. **LEGACY SYSTEMD** if it maps to a current Docker server
2. **ORPHANED LEGACY** if the repo no longer ships it as a Docker server
3. **LEGACY DEPRECATED** for `mcp-evaluate`/`evaluate`

Build a drift report table:

```
MCP Server Drift Report
========================

Server                    Repo    Docker    MCP Reg   Port    Legacy Units              Status
-----------------------------------------------------------------------------------------------
mcp-second-opinion        yes     healthy   yes       8080    user:mcp-second-opinion   LEGACY SYSTEMD
mcp-playwright-persistent yes     healthy   yes       8081    system:mcp-playwright     LEGACY SYSTEMD
mcp-coordination          no      none      yes       8082    system:mcp-coordination   ORPHANED LEGACY
mcp-evaluate              depr.   none      no        --      user:mcp-evaluate         LEGACY DEPRECATED
```

Status classifications:
- **OK** - repo server is installed, registered, and running
- **LEGACY SYSTEMD** - systemd unit remains for a current Docker server; teardown only
- **LEGACY DEPRECATED** - deprecated server has a systemd unit; teardown only
- **ORPHANED LEGACY** - installed/running legacy unit is no longer a repo Docker server
- **ORPHANED DOCKER MCP** - a curated retired server (`.claude/deprecated-mcps.yaml`)
  that is no longer in `docker-compose.yml` but is still present locally as a
  container, an `mcp-<name>:*` image, or a `claude`/`codex mcp` registration
- **PORT CONFLICT** - multiple listener processes are bound to the same MCP port
- **NEW - NOT INSTALLED** - repo ships it but it is not installed
- **NOT RUNNING** - installed but service/container is not active
- **UNHEALTHY** - Docker container is running but healthcheck is failing
- **NOT REGISTERED** - running but not in `claude mcp list`

Use `scripts/drift-detect.sh --fix` as raw inventory for:

- legacy MCP systemd units such as `mcp-coordination`
- port double-binding on MCP ports 8080-8089

When presenting the final drift table, reclassify any systemd finding from that
script as `LEGACY SYSTEMD`, `LEGACY DEPRECATED`, or `ORPHANED LEGACY`. Do not
report systemd as `CONFLICT`, `FAILED SYSTEMD`, or `STALE SERVICE`.

### 6c: Detect Orphaned Docker MCP Servers

Systemd orphans are only half the picture: when a server is removed from
`docker-compose.yml`, a machine that ran it keeps the old container, the old
`mcp-<name>:*` images, and a live `claude`/`codex mcp` registration on a
now-unmanaged port. `scripts/mcp-drift.py` detects those, driven by the curated
`.claude/deprecated-mcps.yaml` list of record (never a blanket "every
registration not in compose" sweep, which would tear down a user's own custom
MCP servers).

```bash
cd "$CPP_DIR"

MCP_DOCKER_DRIFT_STATUS="clean"
python3 scripts/mcp-drift.py --check
MCP_DOCKER_DRIFT_RC=$?
```

A server is classified **ORPHANED DOCKER MCP** only when it is listed in
`deprecated-mcps.yaml` **and** no longer a service in
`docker compose config --services` (across every profile) **and** still present
locally. A server that is still a compose service is `OK`; a listed server with
nothing present is `ABSENT`; if the current service set cannot be read the
server is `UNKNOWN` (never torn down). Registrations CPP never shipped are never
listed, so they are never flagged.

Limitation to surface if asked: like skill drift, detection is curated-list
driven. A server removed from compose without a `deprecated-mcps.yaml` entry
reads as `ABSENT`/untracked; the fix is to add it to that file, not to broaden
the teardown.

---

## Step 7: Guided Remediation

For each drift finding, offer the user actionable options using AskUserQuestion.

**Only show this if drift was detected.** If everything is clean, skip to Step 8.

### For LEGACY SYSTEMD or LEGACY DEPRECATED findings

Default recommendation: tear down legacy systemd and keep Docker as the only
runtime. Ask once for all remaining legacy units if possible:

```
Legacy systemd MCP units remain installed: {units}.
Docker is the only supported CPP runtime. Leaving these units installed can
cause port conflicts or stale server restarts.
```

Options:
- **Tear down legacy systemd** - Stop, disable, remove unit files, reload systemd
- **Skip** - Leave units in place and keep the port-conflict warning visible

If they choose teardown, use the same scope-aware removal commands from Step
4.5 and re-run drift detection to verify no legacy units remain.

### For ORPHANED DOCKER MCP findings

**Only if `MCP_DOCKER_DRIFT_RC` is 1** (Step 6c found orphans). Pull the
structured findings and drive a per-server, user-confirmed teardown. Teardown is
reversible-where-possible: images keep a newest-tag restore point unless the user
chooses prune-all, and `mcp-drift.py` hard-refuses to touch anything not
classified `ORPHANED DOCKER MCP`.

```bash
cd "$CPP_DIR"
python3 scripts/mcp-drift.py --json > /tmp/mcp-drift.json
```

For each orphaned server, show the user what is present (container, image tags,
`claude`/`codex` registrations) plus its `reason` and `replacement`, and ask once
per server with AskUserQuestion:

```
mcp-nano-banana was removed from docker-compose.yml but is still on this machine
({reason}).
Replacement: {replacement}
Present: {container} container, {N} image tag(s), claude:{regs}, codex:{regs}
Port to reclaim: {port}
```

Options:
- **Tear down (keep a restore image)** - stop + remove the container, prune old
  `mcp-<name>:*` image tags but keep the newest as a restore point, unregister
  from `claude`/`codex mcp`. Runs:
  ```bash
  python3 scripts/mcp-drift.py --teardown <name>
  ```
- **Tear down (prune all images)** - same, but remove every `mcp-<name>:*` image:
  ```bash
  python3 scripts/mcp-drift.py --teardown <name> --prune-all-images
  ```
- **Keep** - leave it in place (re-runs of /cpp:update will keep flagging it).

The teardown stops and removes the container (`docker stop` / `docker rm -f`),
prunes images, removes the `claude mcp` registration at its detected scope
(`claude mcp remove <name> -s <scope>`), removes any `codex mcp` registration,
and reports the freed port and image tags. After all confirmed teardowns, re-scan
and record the outcome for the summary:

```bash
cd "$CPP_DIR"
python3 scripts/mcp-drift.py --check
if [ $? -eq 0 ]; then
  MCP_DOCKER_DRIFT_STATUS="torn down (newest image kept as restore point unless prune-all)"
else
  MCP_DOCKER_DRIFT_STATUS="drift remaining (user kept some servers)"
fi
```

Never tear down a server the user chose to keep, and never tear down without an
explicit per-server confirmation. `mcp-drift.py` refuses any server still in
compose (`OK`), any with nothing present (`ABSENT`), and any name not on the
curated list - so a user's own custom MCP registration is never removed.

### For NEW servers (in repo, not installed):

Ask the user per server:

```
mcp-<name> is available in the repo but not installed.
  - Port: <8080-8089>
  - Docker profile: <profile>
  - Purpose: <what the server does>
```

Options:
- **Refresh Docker stack** - Re-run `make docker-refresh PROFILE="core browser"` and `make docker-health PROFILE="core browser"`
- **Skip** - Do not install now

Do not offer systemd installation. New servers are installed only by the Docker
refresh path.

### For ORPHANED LEGACY services

Ask the user per service:

```
mcp-coordination is a legacy systemd unit and is no longer a CPP Docker server.
```

Options:
- **Remove** - Stop service, disable, remove service file, unregister from claude mcp
- **Keep** - Leave it running (user may have a custom setup)

If they choose remove:
1. `sudo systemctl stop <name>`
2. `sudo systemctl disable <name>`
3. `sudo rm /etc/systemd/system/<name>.service`
4. `sudo systemctl daemon-reload`
5. `claude mcp remove <name>` (if registered)

For user-scope orphaned units, use `systemctl --user ...`, remove the file from
`~/.config/systemd/user/`, and run `systemctl --user daemon-reload`.

### For UNHEALTHY or NOT RUNNING Docker servers

Ask whether to rerun the Docker refresh:

Options:
- **Refresh Docker** - `make docker-refresh PROFILE="core browser"` then `make docker-health PROFILE="core browser"`
- **Skip** - Leave current container state unchanged

### For NOT REGISTERED servers (running but not in claude mcp list):

```
mcp-second-opinion is running on port 8080 but not registered with Claude Code.
```

Options:
- **Register** - `claude mcp add --scope user --transport sse <name> http://127.0.0.1:<port>/sse`
- **Skip** - Leave unregistered

---

## Step 7.5: Skill Drift Detection and Prune

The git pull refreshes commands and skills the repo still ships, but it never
removes generated skills the repo has *retired*. CPP's manifest-driven skill
generator was replaced, so every generated skill under `~/.claude/skills/`
references a `manifests/<family>/<name>.yaml` source that no longer exists -
which means a blanket "remove anything the repo no longer ships" prune would
delete live skills (`flow-auto`, `grill-me`, the `issue-*`/`flow-*` families).

So skill drift is detected against the curated deprecation list of record,
`.claude/deprecated-skills.yaml`, exactly like the systemd `LEGACY DEPRECATED`
findings above. Removal is always user-confirmed and never destructive (pruned
skills are moved to a timestamped backup, not deleted).

### 7.5a: Detect

```bash
cd "$CPP_DIR"

SKILL_DRIFT_STATUS="clean"
python3 scripts/skill-drift.py --check
SKILL_DRIFT_RC=$?

if [ "$SKILL_DRIFT_RC" -eq 0 ]; then
  echo ""
  echo "No deprecated or orphaned skills installed."
fi
```

The report classifies every directory in `~/.claude/skills/`:

- **DEPRECATED** - generated skill explicitly named in a deprecated family's
  `skills:` list (e.g. the `wiki-*` skills retired by issue #394).
- **ORPHANED** - generated skill whose `metadata.family` is a *fully* retired
  family (`entire_family: true`) but is not explicitly listed (a stray member).
- **OK** - any other generated skill; left untouched.
- **IGNORED** - a directory without the `GENERATED by claude-power-pack` marker
  (hand-authored / user content); never classified for removal, never pruned.

Limitation to surface if asked: detection is curated-list driven. A skill
removed from CPP without an entry in `.claude/deprecated-skills.yaml` will read
as `OK`. The fix is to add the retired family/skill to that file (this is the
same list `/cpp:update` consumes), not to broaden the prune.

### 7.5b: Guided Prune

**Only if drift was detected (`SKILL_DRIFT_RC` is 1).** Pull the structured
findings and group the removable ones by family:

```bash
cd "$CPP_DIR"
python3 scripts/skill-drift.py --json > /tmp/skill-drift.json
```

For each deprecated family with one or more `DEPRECATED`/`ORPHANED` skills, ask
the user once (per family) with AskUserQuestion. Include the family `reason` and
`replacement` from the findings so the choice is informed:

```
The {family} skill family is retired ({reason}).
Replacement: {replacement}
Installed skills to remove: {skill list}
```

Options:
- **Remove {family} skills** - Move them to `~/.claude/.backup/skills/<timestamp>/`
- **Keep** - Leave them installed (re-runs of /cpp:update will keep flagging them)

If the user confirms removal for a family, prune exactly that family's flagged
skills (the script hard-refuses anything classified `OK` or `IGNORED`, and
refuses path traversal):

```bash
cd "$CPP_DIR"
# NAMES = space-separated DEPRECATED/ORPHANED skill names for the confirmed family
python3 scripts/skill-drift.py --prune $NAMES
```

After all confirmed prunes, re-scan to confirm the surface is clean and record
the outcome for the summary:

```bash
cd "$CPP_DIR"
python3 scripts/skill-drift.py --check
if [ $? -eq 0 ]; then
  SKILL_DRIFT_STATUS="pruned (backup under ~/.claude/.backup/skills/)"
else
  SKILL_DRIFT_STATUS="drift remaining (user kept some skills)"
fi
```

Never delete a skill the user chose to keep, and never prune without an explicit
per-family confirmation.

---

## Step 8: Detect Current Installation Tier

Determine the user's current tier level so we can offer upgrades:

```bash
cd "$CPP_DIR"

# Tier 1 checks
TIER=0

# Commands + Skills
if [ -L ".claude/commands" ] || [ -d ".claude/commands" ]; then
  if [ -L ".claude/skills" ] || [ -d ".claude/skills" ]; then
    TIER=1
  fi
fi

# Tier 2: scripts + hooks
SCRIPTS_COUNT=0
for script in prompt-context.sh worktree-remove.sh secrets-mask.sh hook-mask-output.sh hook-validate-command.sh; do
  [ -f ~/.claude/scripts/$script ] || [ -L ~/.claude/scripts/$script ] && SCRIPTS_COUNT=$((SCRIPTS_COUNT + 1))
done
[ -f ".claude/hooks.json" ] && [ "$SCRIPTS_COUNT" -ge 3 ] && TIER=2

# Tier 3: MCP servers
MCP_LIST=$(claude mcp list 2>/dev/null || echo "")
if echo "$MCP_LIST" | grep -q "second-opinion"; then
  TIER=3
fi
```

---

## Step 9: Offer Tier Upgrade

If the user is not at the highest tier, ask if they want to upgrade using AskUserQuestion:

**Only show this if current tier < 3.**

```
Your current installation: Tier {TIER}

Available upgrades:
  Tier 1 (Minimal): Commands + Skills symlinks
  Tier 2 (Standard): + Scripts, hooks, shell prompt, permission profiles
  Tier 3 (Full): + MCP servers (Docker, local builds, API keys)

Would you like to upgrade to a higher tier?
```

**Options:**
- **Keep current tier** - No changes beyond the git pull
- **Upgrade to Tier 2** (if currently Tier 0 or 1)
- **Upgrade to Tier 3** (if currently below Tier 3)

If upgrading, follow the same installation steps as `/cpp:init` for the new tier only.

---

## Step 10: Update Summary

```
=================================
CPP Update Complete
=================================

Version: v{OLD_VERSION} -> v{NEW_VERSION}
Commit:  {OLD_COMMIT} -> {NEW_COMMIT}
Branch:  {BRANCH}
Tier:    {TIER} {(upgraded from X if applicable)}

Changes pulled:
  {list of new commits, or "Already up to date"}

Dependencies:
  {synced servers or "No MCP venvs to update"}

Runtime:
  Model: Docker (local build)
  Docker: {containers rebuilt/restarted/healthy, or failed with error}
  Health: {make docker-health result}
  Legacy systemd: {none, removed N unit scope(s), or skipped with warning}

MCP Drift:
  {drift summary - e.g. "1 new server refreshed via Docker, 1 legacy unit removed"
   or "No drift detected - all servers in sync"}

Docker MCP Drift:
  {MCP_DOCKER_DRIFT_STATUS - e.g. "clean", "torn down (newest image kept as restore
   point unless prune-all)", or "drift remaining (user kept some servers)"}

Skill Drift:
  {SKILL_DRIFT_STATUS - e.g. "clean", "pruned (backup under ~/.claude/.backup/skills/)",
   or "drift remaining (user kept some skills)"}

Run /cpp:status for full installation details.
=================================
```

---

## Notes

- This command is safe to run repeatedly (idempotent)
- Uncommitted changes in CPP are auto-stashed before pull
- Symlinked commands/skills are automatically updated by the git pull
- MCP server dependencies are synced if venvs exist
- Docker refresh always uses `make docker-refresh PROFILE="core browser"` followed by `make docker-health PROFILE="core browser"`
- Legacy systemd units are detected before Docker refresh and are removed only after user confirmation
- MCP drift detection compares repo state against Docker containers, legacy systemd remnants, claude mcp registrations, and listening ports
- Orphaned legacy systemd units such as `mcp-coordination` are flagged for teardown
- Orphaned Docker MCP infra (Step 6c/7) - a container, `mcp-<name>:*` image, or
  `claude`/`codex mcp` registration left behind after a server is removed from
  `docker-compose.yml` - is detected via the curated `.claude/deprecated-mcps.yaml`
  list and torn down per-server with confirmation, keeping a newest-image restore
  point unless prune-all is chosen. Driven by `scripts/mcp-drift.py`; a user's own
  custom MCP registration is never flagged or removed
- New servers are offered only through the Docker refresh path
- mcp-evaluate is recognized as deprecated and flagged for legacy teardown if installed
- Skill drift (Step 7.5) prunes retired generated skills using the curated
  `.claude/deprecated-skills.yaml` list (never a blanket repo diff, which would
  delete live skills); removals are per-family, user-confirmed, and moved to a
  backup rather than deleted. Driven by `scripts/skill-drift.py`.
- Use `/cpp:init` instead if you need the full interactive setup wizard
