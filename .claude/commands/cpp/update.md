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

# Get current version from CLAUDE.md - the maintained source of truth (issue
# #544: the CHANGELOG head can be a digit-less "[Unreleased]" block, so a grep
# for the first bracketed version silently falls through to the PREVIOUS
# release and reports a stale no-op update). Fall back to the newest bracketed
# CHANGELOG release only if the CLAUDE.md line is missing.
CURRENT_VERSION=$(grep -oPm1 '^Current version: \K[0-9]+\.[0-9]+\.[0-9]+' CLAUDE.md 2>/dev/null)
if [ -z "$CURRENT_VERSION" ]; then
  CURRENT_VERSION=$(grep -oPm1 '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md 2>/dev/null)
fi
CURRENT_VERSION="${CURRENT_VERSION:-unknown}"
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
# Same source-of-truth derivation as Step 2 (issue #544).
NEW_VERSION=$(grep -oPm1 '^Current version: \K[0-9]+\.[0-9]+\.[0-9]+' CLAUDE.md 2>/dev/null)
if [ -z "$NEW_VERSION" ]; then
  NEW_VERSION=$(grep -oPm1 '^\#\# \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md 2>/dev/null)
fi
NEW_VERSION="${NEW_VERSION:-unknown}"
echo ""
# Never report a same-version pull as a no-op: when the release number did not
# move but the commit did, say so and point at the unreleased delta instead of
# printing a misleading "vX -> vX" (issue #544).
if [ "$CURRENT_VERSION" = "$NEW_VERSION" ] && [ "$CURRENT_COMMIT" != "$NEW_COMMIT" ]; then
  echo "Updated: v$NEW_VERSION unchanged, code moved $CURRENT_COMMIT -> $NEW_COMMIT"
  echo "(unreleased changes - see the [Unreleased] section of CHANGELOG.md)"
else
  echo "Updated: v$CURRENT_VERSION ($CURRENT_COMMIT) -> v$NEW_VERSION ($NEW_COMMIT)"
fi
```

---

## Step 3.5: Re-read Self (the pull may have changed this command)

`/cpp:update` is **self-modifying**: the Step 3 pull can change *this very file*
(`.claude/commands/cpp/update.md`). The copy of these instructions loaded into
context is the **pre-pull** version, so every step below may now be stale - a
removed step could run against a deleted script, or a renamed step could act on a
changed tree (issue #545: a `/cpp:update` run pulled #522, which deleted
`scripts/skill-drift.py` and stripped a whole step from this command; the pre-pull
context still contained that step and would have executed it against a now-deleted
script).

**First, surface any change to this command.** `git pull` set `ORIG_HEAD` to the
pre-pull commit, so no variable needs to survive between bash blocks:

```bash
cd "$CPP_DIR"
SELF=".claude/commands/cpp/update.md"
SELF_CHANGED=unknown
if git rev-parse -q --verify ORIG_HEAD >/dev/null 2>&1; then
  if git diff --quiet ORIG_HEAD..HEAD -- "$SELF"; then
    SELF_CHANGED=no
    echo "No change to /cpp:update in this pull - the steps in context are current."
  else
    SELF_CHANGED=yes
    echo ""
    echo "NOTE: this pull modified /cpp:update itself. Diff since the pre-pull copy:"
    git --no-pager diff ORIG_HEAD..HEAD -- "$SELF"
    echo ""
    echo "The /cpp:update steps loaded in context are now STALE."
  fi
else
  echo "Could not determine ORIG_HEAD - treat the in-context steps as possibly stale."
fi
```

**Then, unless `SELF_CHANGED` is `no`, STOP following the in-context steps and
RE-READ the on-disk command before continuing.** Open
`$CPP_DIR/.claude/commands/cpp/update.md` (resolve `$CPP_DIR` from Step 1) and
follow **its** Step 4 onward - the freshly-pulled file on disk is authoritative
now, not the copy this run started with. Only when `SELF_CHANGED` is `no` may you
continue with the in-context steps as-is. This is the one point where re-reading is
mandatory; everything below is what you execute *after* confirming it is current.

---

## Step 4: Update Dependencies

CPP no longer ships in-repo MCP server venvs. The second-opinion server is an
external project (https://github.com/cooneycw/mcp-second-opinion) with its own
dependencies, and playwright runs via npx. There are no CPP-managed server venvs
to sync here.

```bash
echo "No in-repo MCP server venvs to update (second-opinion is external, playwright is npx)."
```

---

## Step 4.6: Refresh Spec-Kit CLI (Optional)

If the official spec-kit CLI (`specify`) is installed, upgrade it so `/spec:adopt`
delegates to the current upstream. If it is absent, offer to install it (never forced -
`/spec:adopt` also installs it on first use). This only touches the CLI; it does not
scaffold `.specify/` into any project.

```bash
if command -v specify &>/dev/null; then
  echo ""
  echo "Upgrading spec-kit CLI..."
  uv tool upgrade specify-cli 2>/dev/null && echo "Done: spec-kit CLI up to date" \
    || echo "Note: could not upgrade specify-cli (not a uv tool install?) - skipping"
else
  echo ""
  echo "spec-kit CLI (specify) is not installed."
  echo "  Install now with: uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"
  echo "  (or just run /spec:adopt in a project - it installs the CLI on first use)"
  # If the user agrees, run:
  #   uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
fi
```

---

## Step 4.7: Retired PreToolUse Hook Cleanup

The PreToolUse dangerous-command hook (`hook-validate-command.sh`) was retired
(issue #439) - native destructive-git blocking + OS sandboxing now cover it, and
the PostToolUse secret-masking hook is retained. Because scripts are symlinked
into `~/.claude/scripts/` and `hooks.json` is **copied** into each project, an
older install can be left with a dangling `hook-validate-command.sh` symlink and
a stale `PreToolUse` block that points at it. A dangling hook command exits
non-zero and would **block every Bash command**, so sweep both. This is a
migration step only - do not change anything until the user confirms.

```bash
# 1. Dangling/retired symlink in ~/.claude/scripts/
HOOK_LINK="$HOME/.claude/scripts/hook-validate-command.sh"
if [ -L "$HOOK_LINK" ] || [ -f "$HOOK_LINK" ]; then
  echo "Found retired hook script: $HOOK_LINK"
  echo "  (safe to remove - the PreToolUse dangerous-command hook was retired in #439)"
  # On user confirm:  rm -f "$HOOK_LINK" && echo "Removed $HOOK_LINK"
fi

# 2. Stale PreToolUse block in this project's copied hooks.json
if [ -f ".claude/hooks.json" ] && \
   grep -q "hook-validate-command.sh" .claude/hooks.json 2>/dev/null; then
  echo "This project's .claude/hooks.json still references the retired PreToolUse hook."
  echo "  Native git-blocking + sandbox cover it; the PostToolUse masking hook is kept."
  echo "  Offer to strip only the validate-command PreToolUse block (masking untouched)."
  # On user confirm, strip the retired hook while preserving everything else:
  #   python3 - <<'PY'
  #   import json, pathlib
  #   p = pathlib.Path(".claude/hooks.json"); d = json.loads(p.read_text())
  #   pre = d.get("hooks", {}).get("PreToolUse", [])
  #   kept = [m for m in pre
  #           if not any("hook-validate-command.sh" in h.get("command", "")
  #                      for h in m.get("hooks", []))]
  #   if kept: d["hooks"]["PreToolUse"] = kept
  #   else: d["hooks"].pop("PreToolUse", None)
  #   p.write_text(json.dumps(d, indent=2) + "\n")
  #   print("Stripped retired PreToolUse hook from .claude/hooks.json")
  #   PY
fi
```

---

## Step 4.5: Legacy Systemd Teardown

Detect legacy MCP systemd units in both system and user scopes. This is a
migration step only: systemd is no longer a supported runtime model. Do not
stop, disable, or remove anything until the user confirms.

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
Legacy systemd MCP units can revive stale server versions or bind ports that
conflict with your MCP servers (the external second-opinion server, playwright).
Remove the listed systemd units?
```

Options:
- **Tear down legacy systemd** - Stop, disable, remove unit files, reload systemd
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
WARNING: Legacy systemd units were left installed. Stale units may still bind
MCP ports or restart old server versions. Run /cpp:update again and choose
teardown if you hit a port conflict with your MCP servers.
```

---

## Step 5: Runtime Refresh (no Docker stack)

CPP no longer builds or runs a Docker MCP stack. The second-opinion server is an
external project (https://github.com/cooneycw/mcp-second-opinion) that you run
yourself, and playwright runs via npx - so there is nothing for /cpp:update to
rebuild here. The git pull already refreshed the symlinked commands.

Retired MCP containers left on this host (mcp-second-opinion, aws-secrets-agent,
mcp-playwright-persistent, ...) are handled by the orphaned-Docker-MCP teardown
in Step 6c/7, not by a rebuild.

```bash
RUNTIME_STATUS="no Docker MCP stack (second-opinion external, playwright via npx)"
echo "$RUNTIME_STATUS"
```

---

## Step 6: MCP Server Drift Detection

After pulling, scan for drift between what CPP expects and what is actually
installed/running on this host. CPP no longer runs a Docker MCP stack, so the
findings that matter now are: retired MCP containers/images/registrations left
behind (torn down via Step 6c/7), legacy systemd units, and stale MCP
registrations. Any remaining systemd unit is a legacy migration finding, not a
runtime option to repair or restart.

### 6a: Build Inventory

Build two lists - what CPP expects vs what is installed/running on this host -
then compare.

**Repo inventory** - what CPP expects for MCP servers now:

```bash
cd "$CPP_DIR"

echo "=== Repo MCP Server Inventory ==="

# CPP no longer ships a Docker MCP stack. It expects:
echo "  second-opinion - external streamable-http server (root .mcp.json -> :8080/mcp)"
echo "  playwright      - upstream @playwright/mcp via npx/stdio"

echo ""
echo "Retired servers (curated in .claude/deprecated-mcps.yaml, torn down as"
echo "orphans by Step 6c/7):"
grep -E '^\s{2}- name:' .claude/deprecated-mcps.yaml | sed 's/- name:/  -/'
```

**Installed inventory** - scan what is currently running/registered:

```bash
echo ""
echo "=== Installed MCP Inventory ==="

echo "MCP registrations (claude mcp list):"
claude mcp list 2>/dev/null | sed 's/^/  /' || echo "  (none)"

echo ""
echo "Leftover MCP containers (retired; torn down by Step 6c/7):"
if command -v docker &>/dev/null; then
  docker ps -a --format '{{.Names}}' 2>/dev/null \
    | grep -E '^(mcp-second-opinion|aws-secrets-agent|mcp-playwright-persistent|mcp-nano-banana|mcp-woodpecker-ci|mcp-coordination)$' \
    | sed 's/^/  /' || echo "  (none)"
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

**Expected servers** (what CPP wires now, registration-only - no containers):
- `second-opinion` - external streamable-http server; the root `.mcp.json` points
  Claude Code at `http://127.0.0.1:8080/mcp` (project scope), optionally also
  registered at user scope. CPP does not build or run it.
- `playwright` - upstream `@playwright/mcp` via npx/stdio.

**Retired servers** (removed; listed in `.claude/deprecated-mcps.yaml`, torn down as
orphans by Step 6c/7 + `scripts/mcp-drift.py`):
- `mcp-second-opinion` (retired #469 - the containerized server moved to its own
  external repo; only the stale container/images are orphans - the `second-opinion`
  registration is the user's valid new wiring and is intentionally NOT flagged)
- `aws-secrets-agent` (retired #469 - the AWS SM sidecar fed the old container and
  has no other consumer)
- `mcp-playwright-persistent` (retired #423 - browser automation moved to the
  upstream `@playwright/mcp` npx/stdio server)
- `mcp-nano-banana`, `mcp-woodpecker-ci`, `mcp-coordination` (retired earlier)

**Deprecated servers**:
- `mcp-evaluate` (deprecated - absorbed into /evaluate:issue skill)

**For each expected server**, check:
1. Is it registered in `claude mcp list`?
2. For second-opinion, is `http://127.0.0.1:8080/mcp` reachable (external server up)?

**For each installed legacy systemd service matching mcp-*, nano-*, or
coordination**, classify it as:

1. **LEGACY SYSTEMD** if it maps to a retired server
2. **ORPHANED LEGACY** if CPP no longer ships it
3. **LEGACY DEPRECATED** for `mcp-evaluate`/`evaluate`

Build a drift report table:

```
MCP Server Drift Report
========================

Server                    Expected  MCP Reg   Container   Legacy Units              Status
------------------------------------------------------------------------------------------
second-opinion            yes       yes       --          --                        OK
playwright                yes       yes       --          --                        OK
mcp-second-opinion        retired   --        present     --                        ORPHANED DOCKER MCP
aws-secrets-agent         retired   --        present     --                        ORPHANED DOCKER MCP
mcp-coordination          retired   yes       none        system:mcp-coordination   ORPHANED LEGACY
mcp-evaluate              depr.     no        none        user:mcp-evaluate         LEGACY DEPRECATED
```

Status classifications:
- **OK** - expected server is registered (and, for second-opinion, reachable)
- **LEGACY SYSTEMD** - a systemd unit remains for a retired server; teardown only
- **LEGACY DEPRECATED** - a deprecated server has a systemd unit; teardown only
- **ORPHANED LEGACY** - an installed/running legacy systemd unit CPP no longer ships
- **ORPHANED DOCKER MCP** - a curated retired server (`.claude/deprecated-mcps.yaml`)
  still present locally as a container, an `mcp-<name>:*` image, or a
  `claude`/`codex mcp` registration after CPP retired it (CPP ships no compose
  file, so any listed server still present locally is an orphan)
- **PORT CONFLICT** - multiple listener processes are bound to the same MCP port
- **NOT REGISTERED** - a server is reachable but not in `claude mcp list`

Use `scripts/drift-detect.sh --fix` as raw inventory for:

- legacy MCP systemd units such as `mcp-coordination`
- port double-binding on MCP ports 8080-8089

When presenting the final drift table, reclassify any systemd finding from that
script as `LEGACY SYSTEMD`, `LEGACY DEPRECATED`, or `ORPHANED LEGACY`. Do not
report systemd as `CONFLICT`, `FAILED SYSTEMD`, or `STALE SERVICE`.

### 6c: Detect Orphaned Docker MCP Servers

Systemd orphans are only half the picture: when a server is retired from CPP, a
machine that ran it keeps the old container, the old `mcp-<name>:*` images, and a
live `claude`/`codex mcp` registration on a now-unmanaged port. This now includes
the Docker MCP runtime CPP retired wholesale in #469 - a lingering
`mcp-second-opinion` or `aws-secrets-agent` container is exactly this kind of
orphan. `scripts/mcp-drift.py` detects those, driven by the curated
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
`deprecated-mcps.yaml` **and** no longer a compose service **and** still present
locally. CPP now ships NO `docker-compose.yml`, so `mcp-drift.py` treats the
service set as empty by absence - any listed server still lingering on the host is
a genuine orphan. (If a compose file is ever reintroduced, a listed name that is
still a service is `OK`.) A listed server with nothing present is `ABSENT`; if the
service set cannot be read the server is `UNKNOWN` (never torn down). Registrations
CPP never shipped are never listed, so they are never flagged - and the valid new
`second-opinion` registration is deliberately left off the retired entry's
registration list, so the user's new wiring is never torn down.

Limitation to surface if asked: like skill drift, detection is curated-list
driven. A retired server without a `deprecated-mcps.yaml` entry reads as
untracked; the fix is to add it to that file, not to broaden the teardown.

---

## Step 7: Guided Remediation

For each drift finding, offer the user actionable options using AskUserQuestion.

**Only show this if drift was detected.** If everything is clean, skip to Step 8.

### For LEGACY SYSTEMD or LEGACY DEPRECATED findings

Default recommendation: tear down legacy systemd (systemd is no longer a
supported runtime). Ask once for all remaining legacy units if possible:

```
Legacy systemd MCP units remain installed: {units}.
Systemd is no longer a supported CPP runtime. Leaving these units installed can
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
mcp-second-opinion was retired from CPP but is still on this machine
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

### For NOT REGISTERED servers (reachable but not in claude mcp list):

```
The external second-opinion server answers on http://127.0.0.1:8080/mcp but is
not registered with Claude Code (the root .mcp.json only applies inside CPP).
```

Options:
- **Register** - `claude mcp add second-opinion --transport http --url http://127.0.0.1:8080/mcp --scope user` (edit the URL for a Tailscale host)
- **Skip** - Leave unregistered

---

## Step 7.5: User-Level Flow Allowlist Refresh

The git pull may have updated `templates/claude-settings-permissions.json`
(the user-level read-only allowlist that keeps `/flow:*` from prompting for
its git/gh plumbing - see `templates/claude-settings-permissions.md`). Check
whether `~/.claude/settings.json` is missing any template rules and offer to
merge the difference.

```bash
cd "$CPP_DIR"
TEMPLATE="$CPP_DIR/templates/claude-settings-permissions.json"
TARGET="$HOME/.claude/settings.json"

if [ -f "$TEMPLATE" ]; then
  if [ -f "$TARGET" ]; then
    MISSING=$(jq -s '(.[1].permissions.allow - (.[0].permissions.allow // [])) | length' "$TARGET" "$TEMPLATE")
    jq -rs '(.[1].permissions.allow - (.[0].permissions.allow // []))[] | "  + \(.)"' "$TARGET" "$TEMPLATE"
  else
    MISSING=$(jq '.permissions.allow | length' "$TEMPLATE")
    jq -r '.permissions.allow[] | "  + \(.)"' "$TEMPLATE"
  fi

  if [ "$MISSING" -eq 0 ]; then
    echo "✓ Flow allowlist up to date"
  else
    echo "Flow allowlist: $MISSING rule(s) from the template are not in ~/.claude/settings.json"
  fi
fi
```

If rules are missing, ask the user:

```
Merge the missing flow allowlist rules into ~/.claude/settings.json?
(Additive and idempotent - existing settings and rules are preserved.
Rationale and caveats: templates/claude-settings-permissions.md)  [y/N]
```

If yes, run the same merge as `/cpp:init`:

```bash
mkdir -p "$HOME/.claude"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"
jq -s '.[0].permissions.allow = (((.[0].permissions.allow // []) + .[1].permissions.allow) | unique) | .[0]' \
  "$TARGET" "$TEMPLATE" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"
echo "✓ Flow allowlist merged ($(jq '.permissions.allow | length' "$TARGET") total allow rules)"
```

If no: report `→ Flow allowlist refresh skipped` and continue.

---

## Step 7.6: Permission-Prompt Census Hook Registration

The git pull may have added `scripts/hook-permission-census.sh` (the observe-only
`PermissionRequest` hook that records each permission prompt - with a derived
allow-rule candidate and a risk tier - to the project's `.claude/friction.jsonl`,
so `/self-improvement:retro` Step 4 finally has real input; issue #482). The
script itself is re-linked into `~/.claude/scripts/` by the Tier 2 refresh; this
step registers it in `~/.claude/settings.json` if it is not already there. Same
user-level trust boundary as Step 7.5, so it is user-confirmed.

```bash
TARGET="$HOME/.claude/settings.json"
CENSUS_CMD="~/.claude/scripts/hook-permission-census.sh"
CENSUS_SCRIPT="$HOME/.claude/scripts/hook-permission-census.sh"

# Only offer if the script is installed and not already registered.
if [ -e "$CENSUS_SCRIPT" ]; then
  ALREADY=0
  if [ -f "$TARGET" ]; then
    ALREADY=$(jq --arg cmd "$CENSUS_CMD" \
      '[.hooks.PermissionRequest[]? | (.hooks // [])[]? | select(.command == $cmd)] | length' \
      "$TARGET" 2>/dev/null || echo 0)
  fi
  if [ "${ALREADY:-0}" -gt 0 ]; then
    echo "✓ Permission-prompt census hook already registered"
  else
    echo "Permission-prompt census hook is not registered in ~/.claude/settings.json"
  fi
fi
```

If not registered, ask the user:

```
Register the observe-only PermissionRequest census hook in ~/.claude/settings.json?
It records each permission prompt (derived allow-rule candidate + risk tier) to the
project friction ledger so /self-improvement:retro can propose an allowlist from real
data. Never blocks or alters a permission decision.  [y/N]
```

If yes, run the same idempotent merge as `/cpp:init`:

```bash
mkdir -p "$HOME/.claude"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"
jq --arg cmd "$CENSUS_CMD" '
  .hooks = (.hooks // {})
  | .hooks.PermissionRequest = (.hooks.PermissionRequest // [])
  | if any(.hooks.PermissionRequest[]?; (.hooks // [])[]?.command == $cmd)
    then .
    else .hooks.PermissionRequest += [{"hooks":[{"type":"command","command":$cmd}]}]
    end
' "$TARGET" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"
echo "✓ PermissionRequest census hook registered in ~/.claude/settings.json"
```

If no: report `→ Permission-prompt census hook registration skipped` and continue.

---

## Step 7.7: Pending-Retro Reminder Registration (opt-in)

The git pull may have added `scripts/hook-pending-retro.sh` (a `SessionStart`
hook that prints ONE advisory line at session open when retro material is waiting
- pending `.claude/friction.jsonl` signals plus uncodified `Status: proposed`
learnings - pointing at `/self-improvement:retro`; issue #530). It only surfaces,
never codifies, and is silent when nothing is pending. The script is re-linked
into `~/.claude/scripts/` by the Tier 2 refresh; this step registers it in
`~/.claude/settings.json` if not already there. Opt-in and user-confirmed
(default N) - it is deliberately NOT shipped in `.claude/hooks.json`, so it never
turns itself on.

```bash
TARGET="$HOME/.claude/settings.json"
RETRO_CMD="~/.claude/scripts/hook-pending-retro.sh"
RETRO_SCRIPT="$HOME/.claude/scripts/hook-pending-retro.sh"

# Only offer if the script is installed and not already registered.
if [ -e "$RETRO_SCRIPT" ]; then
  ALREADY=0
  if [ -f "$TARGET" ]; then
    ALREADY=$(jq --arg cmd "$RETRO_CMD" \
      '[.hooks.SessionStart[]? | (.hooks // [])[]? | select(.command == $cmd)] | length' \
      "$TARGET" 2>/dev/null || echo 0)
  fi
  if [ "${ALREADY:-0}" -gt 0 ]; then
    echo "✓ Pending-retro reminder already registered"
  else
    echo "Pending-retro reminder is not registered in ~/.claude/settings.json"
  fi
fi
```

If not registered, ask the user:

```
Register the session-open pending-retro reminder in ~/.claude/settings.json?
It prints one advisory line when pending friction signals or uncodified learnings
exist, so you can choose to run /self-improvement:retro. Surfaces only - never
codifies, never blocks. Silent when nothing is pending.  [y/N default N]
```

If yes, run the same idempotent merge as `/cpp:init`:

```bash
mkdir -p "$HOME/.claude"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"
jq --arg cmd "$RETRO_CMD" '
  .hooks = (.hooks // {})
  | .hooks.SessionStart = (.hooks.SessionStart // [])
  | if any(.hooks.SessionStart[]?; (.command == $cmd) or ((.hooks // [])[]?.command == $cmd))
    then .
    else .hooks.SessionStart += [{"hooks":[{"type":"command","command":$cmd}]}]
    end
' "$TARGET" > "$TARGET.tmp" && mv "$TARGET.tmp" "$TARGET"
echo "✓ Session-open pending-retro reminder registered in ~/.claude/settings.json"
```

If no: report `→ Pending-retro reminder registration skipped (default)` and continue.

---

## Step 7.8: Commands-Mirror Refresh (opt-in, fail-open)

Hosts that serve the command surface from an out-of-repo byte-copy of
`.claude/commands/` (e.g. `~/Projects/.claude/commands`, project scope for
sessions started above the checkout) instead of `/plugin` installs had nothing
maintaining that mirror, so it silently went stale as merges landed (issue #582).
This step guards it. It is a no-op on hosts without a mirror.

```bash
MIRROR="${CPP_COMMANDS_MIRROR:-}"
# Auto-detect the common layout when the env var is unset: a commands dir in a
# .claude/ directory directly above this checkout.
if [ -z "$MIRROR" ]; then
  CAND="$(dirname "$(pwd)")/.claude/commands"
  [ -d "$CAND" ] && MIRROR="$CAND"
fi
if [ -n "$MIRROR" ] && [ -d "$MIRROR" ]; then
  if ! scripts/commands-mirror-sync.sh --check "$MIRROR"; then
    echo "Commands mirror at $MIRROR has drifted from the repo."
  fi
fi
```

If drift is reported, ask the user:

```
Refresh the commands mirror at {MIRROR} from the repo (prunes files the repo
no longer has, copies everything current)?  [Y/n]
```

If yes: `scripts/commands-mirror-sync.sh --write "$MIRROR"`. If no: report
`→ Commands mirror left stale (re-run scripts/commands-mirror-sync.sh --write later)`
and continue. Long term, prefer retiring the mirror in favor of `/plugin`
installs (#582 follow-through tracked with #575).

---

## Step 8: Detect Current Installation Tier

Determine the user's current tier level so we can offer upgrades:

```bash
cd "$CPP_DIR"

# Tier 1 checks
TIER=0

# Commands
if [ -L ".claude/commands" ] || [ -d ".claude/commands" ]; then
  TIER=1
fi

# Tier 2: scripts + hooks
SCRIPTS_COUNT=0
for script in prompt-context.sh worktree-remove.sh secrets-mask.sh hook-mask-output.sh; do
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
  Tier 3 (Full): + MCP servers (external second-opinion + playwright)

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
  Model: no Docker MCP stack (second-opinion external, playwright via npx)
  Legacy systemd: {none, removed N unit scope(s), or skipped with warning}

MCP Drift:
  {drift summary - e.g. "1 new server refreshed via Docker, 1 legacy unit removed"
   or "No drift detected - all servers in sync"}

Docker MCP Drift:
  {MCP_DOCKER_DRIFT_STATUS - e.g. "clean", "torn down (newest image kept as restore
   point unless prune-all)", or "drift remaining (user kept some servers)"}

Run /cpp:status for full installation details.
=================================
```

---

## Notes

- This command is safe to run repeatedly (idempotent)
- Uncommitted changes in CPP are auto-stashed before pull
- Symlinked commands are automatically updated by the git pull
- CPP ships no in-repo MCP server venvs; second-opinion is external, playwright is npx
- CPP no longer builds or runs a Docker MCP stack, so there is no Docker refresh step
- Legacy systemd units are detected and removed only after user confirmation
- MCP drift detection compares CPP's expected servers against leftover retired
  containers, legacy systemd remnants, claude mcp registrations, and listening ports
- Orphaned legacy systemd units such as `mcp-coordination` are flagged for teardown
- Orphaned Docker MCP infra (Step 6c/7) - a container, `mcp-<name>:*` image, or
  `claude`/`codex mcp` registration left behind after a server is retired from CPP
  (including the `mcp-second-opinion`/`aws-secrets-agent` containers retired in #469)
  - is detected via the curated `.claude/deprecated-mcps.yaml` list and torn down
  per-server with confirmation, keeping a newest-image restore point unless prune-all
  is chosen. Driven by `scripts/mcp-drift.py`; a user's own custom MCP registration
  (and the valid new `second-opinion` registration) is never flagged or removed
- mcp-evaluate is recognized as deprecated and flagged for legacy teardown if installed
- Use `/cpp:init` instead if you need the full interactive setup wizard
