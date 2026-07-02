#!/usr/bin/env bash
# drift-detect.sh - Detect drift between repo-owned artifacts and host-installed state
# Part of Claude Power Pack (CPP)
#
# Compares installed systemd units, sysctl configs, and Go binaries against
# repo templates/expectations. Exits non-zero if drift is detected.
#
# Usage:
#   drift-detect.sh              # Check all artifact categories
#   drift-detect.sh --check      # Same as no args (explicit)
#   drift-detect.sh --fix        # Report what would need to be re-run to reconcile
#   drift-detect.sh --help       # Show help
#
# Exit codes:
#   0 - No drift detected (or no artifacts installed)
#   1 - Drift detected
#   2 - Usage error

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# --- Globals ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DRIFT_COUNT=0
SKIP_COUNT=0
CHECK_COUNT=0
FIX_MODE=false

# MCP deployment model inventory. Keep this explicit so legacy unit aliases can
# be handled as deployment remnants instead of being mistaken for new servers.
MCP_SERVERS=(
    "mcp-second-opinion"
    "mcp-playwright-persistent"
)
declare -A MCP_DOCKER_CONTAINERS=(
    ["mcp-second-opinion"]="mcp-second-opinion"
    ["mcp-playwright-persistent"]="mcp-playwright-persistent"
)
declare -A MCP_SYSTEMD_UNITS=(
    ["mcp-second-opinion"]="mcp-second-opinion"
    ["mcp-playwright-persistent"]="mcp-playwright mcp-playwright-persistent"
)
declare -A MCP_PORTS=(
    ["mcp-second-opinion"]="8080"
    ["mcp-playwright-persistent"]="8081"
)
declare -A MCP_REGISTRATIONS=(
    ["mcp-second-opinion"]="second-opinion mcp-second-opinion"
    ["mcp-playwright-persistent"]="playwright-persistent mcp-playwright mcp-playwright-persistent"
)
declare -A DOCKER_STATUS=()

# --- Helpers ---
info()  { echo -e "${BLUE}info${NC}  $*"; }
ok()    { echo -e "${GREEN}ok${NC}    $*"; CHECK_COUNT=$((CHECK_COUNT + 1)); }
drift() { echo -e "${RED}DRIFT${NC} $*"; DRIFT_COUNT=$((DRIFT_COUNT + 1)); CHECK_COUNT=$((CHECK_COUNT + 1)); }
skip()  { echo -e "${YELLOW}skip${NC}  $*"; SKIP_COUNT=$((SKIP_COUNT + 1)); }
fix()   { if $FIX_MODE; then echo -e "       ${YELLOW}fix:${NC} $*"; fi; }

systemd_unit_path() {
    local unit="$1"
    local user_path="$HOME/.config/systemd/user/${unit}.service"
    local system_path="/etc/systemd/system/${unit}.service"

    if [[ -f "$user_path" ]]; then
        echo "$user_path"
    elif [[ -f "$system_path" ]]; then
        echo "$system_path"
    fi
}

# Authoritative presence check. `systemctl is-active` reports "inactive" with a
# zero exit even for units that were never installed, so presence must come from
# systemd's LoadState (or an on-disk unit file) - never from is-active. Checks
# the user manager first, then the system manager.
systemd_unit_exists() {
    local unit="$1"
    local load_state

    if command -v systemctl &>/dev/null; then
        load_state=$(systemctl --user show -p LoadState --value "$unit" 2>/dev/null || true)
        case "$load_state" in
            loaded|masked) return 0 ;;
        esac

        load_state=$(systemctl show -p LoadState --value "$unit" 2>/dev/null || true)
        case "$load_state" in
            loaded|masked) return 0 ;;
        esac
    fi

    [[ -n "$(systemd_unit_path "$unit")" ]]
}

systemd_unit_state() {
    local unit="$1"
    local state=""

    if command -v systemctl &>/dev/null; then
        state=$(systemctl --user is-active "$unit" 2>/dev/null || true)
        case "$state" in
            active|activating|deactivating|failed)
                echo "$state"
                return
                ;;
        esac

        state=$(systemctl is-active "$unit" 2>/dev/null || true)
        case "$state" in
            active|activating|deactivating|failed)
                echo "$state"
                return
                ;;
        esac
    fi

    # is-active returns "inactive" (exit 0) even for never-installed units, so it
    # cannot prove presence. Confirm via LoadState / on-disk unit file instead.
    if systemd_unit_exists "$unit"; then
        echo "inactive"
    else
        echo "not-found"
    fi
}

is_systemd_unit_present() {
    systemd_unit_exists "$1"
}

repo_ships_systemd_unit() {
    local unit="$1"
    find "$REPO_ROOT" -path "*/deploy/${unit}.service" -o -path "*/deploy/${unit}.service.template" 2>/dev/null | grep -q .
}

canonical_server_for_unit() {
    local unit="$1"
    case "$unit" in
        mcp-second-opinion) echo "mcp-second-opinion" ;;
        mcp-playwright|mcp-playwright-persistent) echo "mcp-playwright-persistent" ;;
        *) echo "" ;;
    esac
}

primary_registration_for_unit() {
    local unit="$1"
    local server
    server=$(canonical_server_for_unit "$unit")

    if [[ -n "$server" ]]; then
        echo "${MCP_REGISTRATIONS[$server]%% *}"
    else
        echo "$unit"
    fi
}

fix_remove_systemd_unit() {
    local unit="$1"
    local path="$2"
    local registration
    registration=$(primary_registration_for_unit "$unit")

    fix "Opt-in Docker convergence for $unit:"
    if [[ "$path" == "$HOME/.config/systemd/user/"* ]]; then
        fix "systemctl --user stop $unit || true"
        fix "systemctl --user disable $unit || true"
        fix "rm -f $path"
        fix "systemctl --user daemon-reload"
    elif [[ -n "$path" ]]; then
        fix "sudo systemctl stop $unit || true"
        fix "sudo systemctl disable $unit || true"
        fix "sudo rm -f $path"
        fix "sudo systemctl daemon-reload"
    else
        fix "systemctl --user stop $unit || sudo systemctl stop $unit || true"
        fix "systemctl --user disable $unit || sudo systemctl disable $unit || true"
        fix "Remove the installed ${unit}.service file, then reload systemd"
    fi
    fix "claude mcp remove $registration || true"
}

collect_docker_status() {
    DOCKER_STATUS=()
    command -v docker &>/dev/null || return

    local line name status
    local compose_file="$REPO_ROOT/docker-compose.yml"
    if [[ -f "$compose_file" ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] || continue
            name="${line%%:*}"
            status="${line#*:}"
            [[ -n "$name" && "$name" != "$status" ]] || continue
            DOCKER_STATUS["$name"]="$status"
        done < <(docker compose -f "$compose_file" \
            --profile core --profile browser --profile cicd \
            ps --format '{{.Name}}:{{.Status}}' 2>/dev/null || true)
    fi

    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        name="${line%%:*}"
        status="${line#*:}"
        [[ -n "$name" && "$name" != "$status" ]] || continue
        DOCKER_STATUS["$name"]="${DOCKER_STATUS[$name]:-$status}"
    done < <(docker ps --format '{{.Names}}:{{.Status}}' 2>/dev/null || true)
}

is_docker_container_running() {
    local container="$1"
    local status="${DOCKER_STATUS[$container]:-}"
    [[ -n "$status" && "$status" != *"Exited"* && "$status" != *"Created"* && "$status" != *"Dead"* ]]
}

list_installed_mcp_units() {
    {
        find "$HOME/.config/systemd/user" /etc/systemd/system \
            -maxdepth 1 -type f \
            \( -name 'mcp-*.service' -o -name 'nano-*.service' -o -name '*coordination*.service' \) \
            -printf '%f\n' 2>/dev/null || true

        if command -v systemctl &>/dev/null; then
            systemctl --user list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
            systemctl list-units --type=service --all --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
            systemctl --user list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
            systemctl list-unit-files --type=service --no-legend --no-pager 2>/dev/null | awk '{print $1}' || true
        fi
    } | sed 's/\.service$//' | grep -E '^(mcp-|nano-|.*coordination)' | sort -u
}

usage() {
    cat <<'EOF'
drift-detect.sh - Detect drift between repo and host-installed artifacts

Usage:
  drift-detect.sh              Check all categories
  drift-detect.sh --check      Same as above (explicit)
  drift-detect.sh --fix        Also show remediation commands
  drift-detect.sh --help       Show this help

Categories checked:
  1. Systemd units    - installed .service files vs repo templates
  2. Sysctl config    - /etc/sysctl.d/99-claude-code.conf vs bash-prep.sh targets
  3. Docker containers - running container health status
  4. Shared scripts   - cross-container script consistency (fetch-secrets.sh, bash-prep.sh)
  5. MCP deployment models - Docker/systemd conflicts, failed/orphaned units,
                             orphaned Docker MCP servers (via mcp-drift.py), port bindings

Exit codes:
  0 - No drift (or no artifacts installed to check)
  1 - Drift detected
  2 - Usage error
EOF
}

# --- Systemd unit drift ---
# Generates a service file from the template (same logic as install-service.sh)
# and compares it against the installed version.
check_systemd_unit() {
    local service_name="$1"
    local template_path="$2"
    local server_dir="$3"

    if [[ ! -f "$template_path" ]]; then
        skip "$service_name - template not found: $template_path"
        return
    fi

    # Detect UV bin (same logic as install-service.sh)
    local uv_bin=""
    if command -v uv &>/dev/null; then
        uv_bin="$(dirname "$(which uv)")"
    elif [[ -f "$HOME/.local/bin/uv" ]]; then
        uv_bin="$HOME/.local/bin"
    elif [[ -f "$HOME/.cargo/bin/uv" ]]; then
        uv_bin="$HOME/.cargo/bin"
    elif [[ -f "/usr/local/bin/uv" ]]; then
        uv_bin="/usr/local/bin"
    fi

    if [[ -z "$uv_bin" ]]; then
        skip "$service_name - uv not found, cannot generate expected unit"
        return
    fi

    # Generate expected unit from template
    local expected
    expected=$(sed \
        -e "s|\${SERVICE_USER}|$USER|g" \
        -e "s|\${MCP_SERVER_DIR}|$server_dir|g" \
        -e "s|\${UV_BIN}|$uv_bin|g" \
        "$template_path")

    # Check user service location
    local installed_path="$HOME/.config/systemd/user/${service_name}.service"
    if [[ ! -f "$installed_path" ]]; then
        # Check system service location
        installed_path="/etc/systemd/system/${service_name}.service"
    fi

    if [[ ! -f "$installed_path" ]]; then
        skip "$service_name - not installed (no systemd unit found)"
        return
    fi

    local state
    state=$(systemd_unit_state "$service_name")
    if [[ "$state" == "failed" ]]; then
        drift "systemd - unit $service_name is failed"
        fix_remove_systemd_unit "$service_name" "$installed_path"
    elif [[ "$state" == "activating" ]]; then
        drift "systemd - unit $service_name is stuck activating"
        fix_remove_systemd_unit "$service_name" "$installed_path"
    fi

    local installed
    installed=$(cat "$installed_path")

    # For user services, the install script removes User= and changes WantedBy
    # Apply the same transforms to expected for fair comparison
    if [[ "$installed_path" == *"/systemd/user/"* ]]; then
        expected=$(echo "$expected" | sed -e '/^User=/d' -e 's/WantedBy=multi-user.target/WantedBy=default.target/')
    fi

    if [[ "$expected" == "$installed" ]]; then
        ok "$service_name - installed unit matches repo template"
    else
        drift "$service_name - installed unit differs from repo template"
        info "  installed: $installed_path"
        info "  template:  $template_path"
        fix "Re-run: $server_dir/scripts/install-service.sh (or $server_dir/deploy/install-service.sh)"

        # Show diff summary (line count only to avoid noisy output)
        local diff_lines
        diff_lines=$(diff <(echo "$expected") <(echo "$installed") | grep -c '^[<>]' || true)
        info "  $diff_lines lines differ"
    fi
}

# --- Sysctl drift ---
check_sysctl() {
    local conf="/etc/sysctl.d/99-claude-code.conf"

    if [[ ! -f "$conf" ]]; then
        skip "sysctl - $conf not found (bash-prep.sh not applied)"
        return
    fi

    # Expected values from bash-prep.sh
    local -A expected=(
        ["vm.swappiness"]="10"
        ["vm.vfs_cache_pressure"]="50"
        ["fs.inotify.max_user_watches"]="524288"
        ["fs.inotify.max_user_instances"]="512"
    )

    local has_drift=false
    for key in "${!expected[@]}"; do
        local live_val
        live_val=$(sysctl -n "$key" 2>/dev/null || echo "unknown")
        local expected_val="${expected[$key]}"

        if [[ "$live_val" != "$expected_val" ]]; then
            drift "sysctl $key = $live_val (expected $expected_val)"
            has_drift=true
        fi
    done

    if ! $has_drift; then
        ok "sysctl - all parameters match bash-prep.sh targets"
    else
        fix "Re-run: $REPO_ROOT/scripts/bash-prep.sh --apply"
    fi
}

# --- Docker compose drift ---
check_docker_compose() {
    if ! command -v docker &>/dev/null; then
        skip "docker - not installed"
        return
    fi

    # Check if containers are running and healthy
    local compose_file="$REPO_ROOT/docker-compose.yml"
    if [[ ! -f "$compose_file" ]]; then
        skip "docker - no docker-compose.yml found"
        return
    fi

    collect_docker_status

    if (( ${#DOCKER_STATUS[@]} == 0 )); then
        skip "docker - no containers running"
        return
    fi

    # Check each running container's image ID vs what compose config expects
    local has_drift=false
    local name status
    for name in "${!DOCKER_STATUS[@]}"; do
        status="${DOCKER_STATUS[$name]}"
        if [[ "$status" == *"unhealthy"* ]]; then
            drift "docker - container $name is unhealthy"
            has_drift=true
        fi
    done

    if ! $has_drift; then
        ok "docker - all running containers healthy"
    else
        fix "Re-run: make deploy PROFILE=\"core browser cicd\""
    fi
}

# --- MCP deployment model conflicts ---
check_mcp_deployment_models() {
    collect_docker_status

    local has_issue=false
    local server container docker_running units unit present_units state path

    for server in "${MCP_SERVERS[@]}"; do
        container="${MCP_DOCKER_CONTAINERS[$server]:-}"
        docker_running=false
        if [[ -n "$container" ]] && is_docker_container_running "$container"; then
            docker_running=true
        fi

        present_units=()
        units="${MCP_SYSTEMD_UNITS[$server]:-}"
        for unit in $units; do
            if is_systemd_unit_present "$unit"; then
                present_units+=("$unit")
                state=$(systemd_unit_state "$unit")
                path=$(systemd_unit_path "$unit")
                if [[ "$state" == "failed" ]]; then
                    drift "systemd - unit $unit is failed ($server)"
                    fix_remove_systemd_unit "$unit" "$path"
                    has_issue=true
                elif [[ "$state" == "activating" ]]; then
                    drift "systemd - unit $unit is stuck activating ($server)"
                    fix_remove_systemd_unit "$unit" "$path"
                    has_issue=true
                fi
            fi
        done

        if $docker_running && (( ${#present_units[@]} > 0 )); then
            drift "deployment model conflict - $server has Docker container $container and systemd unit(s): ${present_units[*]}"
            fix "Default convergence is Docker for $server. Stop, disable, and remove the systemd unit(s) below, then re-run this check."
            for unit in "${present_units[@]}"; do
                fix_remove_systemd_unit "$unit" "$(systemd_unit_path "$unit")"
            done
            has_issue=true
        fi
    done

    if ! $has_issue; then
        ok "mcp deployment models - no Docker/systemd conflicts or failed units"
    fi
}

check_orphaned_systemd_units() {
    local has_orphan=false
    local unit path state

    while IFS= read -r unit; do
        [[ -n "$unit" ]] || continue
        if repo_ships_systemd_unit "$unit"; then
            continue
        fi

        path=$(systemd_unit_path "$unit")
        state=$(systemd_unit_state "$unit")
        drift "orphaned systemd unit $unit - repo no longer ships it (state: $state)"
        fix_remove_systemd_unit "$unit" "$path"
        has_orphan=true
    done < <(list_installed_mcp_units)

    if ! $has_orphan; then
        ok "orphaned systemd units - none detected"
    fi
}

# --- Orphaned Docker MCP servers ---
# Delegates to scripts/mcp-drift.py, which derives the current service set
# dynamically from `docker compose config --services` (across every profile) and
# flags a server that is on the curated `.claude/deprecated-mcps.yaml` list but no
# longer in compose while still present locally (container / image / registration).
# This is what makes a *removed* Docker MCP get torn down instead of silently
# forgotten - the hardcoded MCP_* arrays above only ever describe current servers.
check_orphaned_docker_mcps() {
    local helper="$SCRIPT_DIR/mcp-drift.py"

    if ! command -v docker &>/dev/null; then
        skip "orphaned Docker MCPs - docker not installed"
        return
    fi
    if [[ ! -f "$helper" ]] || ! command -v python3 &>/dev/null; then
        skip "orphaned Docker MCPs - mcp-drift.py or python3 unavailable"
        return
    fi

    local orphans
    orphans=$(python3 "$helper" --list-orphans 2>/dev/null || true)
    if [[ -z "$orphans" ]]; then
        ok "orphaned Docker MCPs - none detected"
        return
    fi

    local name cmd
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        drift "orphaned Docker MCP $name - removed from docker-compose.yml but still present locally"
        if $FIX_MODE; then
            while IFS= read -r cmd; do
                [[ -n "$cmd" ]] && fix "$cmd"
            done < <(python3 "$helper" --plan "$name" 2>/dev/null || true)
        fi
    done <<< "$orphans"
    fix "Guided teardown: run /cpp:update (Step 7), or: python3 scripts/mcp-drift.py --teardown <name>"
}

check_mcp_port_bindings() {
    if ! command -v ss &>/dev/null; then
        skip "ports - ss not available"
        return
    fi

    local output
    output=$(ss -tlnp 2>/dev/null | grep -E ':(808[0-9])\b' || true)
    if [[ -z "$output" ]]; then
        skip "ports - no MCP listeners on 8080-8089"
        return
    fi

    local has_conflict=false
    local port proc
    local tmp_dir
    tmp_dir=$(mktemp -d)
    while IFS= read -r line; do
        port=$(echo "$line" | grep -oE ':(808[0-9])\b' | head -1 | tr -d ':' || true)
        [[ -n "$port" ]] || continue
        proc=$(echo "$line" | sed -n 's/.*users:((\"\([^\"]*\)\".*/\1/p')
        [[ -n "$proc" ]] || proc="unknown"
        echo "$proc" >> "$tmp_dir/$port"
    done <<< "$output"

    for file in "$tmp_dir"/*; do
        [[ -f "$file" ]] || continue
        port="$(basename "$file")"
        local proc_count
        proc_count=$(sort -u "$file" | wc -l | tr -d ' ')
        if (( proc_count > 1 )); then
            drift "port binding conflict - port $port has multiple listener processes: $(sort -u "$file" | paste -sd ', ' -)"
            fix "Stop the losing provider for port $port, then re-run scripts/drift-detect.sh --fix"
            has_conflict=true
        fi
    done
    rm -rf "$tmp_dir"

    if ! $has_conflict; then
        ok "ports - no double-binding detected on 8080-8089"
    fi
}

# --- Shared script contract drift ---
# Detects when scripts used by multiple containers have diverged.
# Each MCP container that copies a shared script should use the same version.
check_shared_scripts() {
    # fetch-secrets.sh is the primary shared script across MCP containers
    local canonical="$REPO_ROOT/scripts/fetch-secrets.sh"
    if [[ ! -f "$canonical" ]]; then
        # Look for a canonical copy in any MCP container's deploy dir
        for dir in "$REPO_ROOT"/mcp-*/deploy; do
            if [[ -f "$dir/fetch-secrets.sh" ]]; then
                canonical="$dir/fetch-secrets.sh"
                break
            fi
        done
    fi

    if [[ ! -f "$canonical" ]]; then
        skip "shared scripts - no fetch-secrets.sh found in any deploy dir"
        return
    fi

    local canonical_hash
    canonical_hash=$(sha256sum "$canonical" | cut -d' ' -f1)
    local canonical_rel="${canonical#$REPO_ROOT/}"
    local has_drift=false

    for dir in "$REPO_ROOT"/mcp-*/deploy; do
        local script="$dir/fetch-secrets.sh"
        [[ -f "$script" ]] || continue
        [[ "$script" = "$canonical" ]] && continue

        local script_hash
        script_hash=$(sha256sum "$script" | cut -d' ' -f1)
        local script_rel="${script#$REPO_ROOT/}"

        if [[ "$canonical_hash" != "$script_hash" ]]; then
            drift "shared script divergence: $script_rel differs from $canonical_rel"
            has_drift=true
        fi
    done

    # Also check bash-prep.sh if it exists in multiple locations
    local bash_preps=()
    while IFS= read -r -d '' f; do
        bash_preps+=("$f")
    done < <(find "$REPO_ROOT" -maxdepth 3 -name "bash-prep.sh" -print0 2>/dev/null)

    if (( ${#bash_preps[@]} > 1 )); then
        local ref_hash
        ref_hash=$(sha256sum "${bash_preps[0]}" | cut -d' ' -f1)
        for ((i=1; i<${#bash_preps[@]}; i++)); do
            local other_hash
            other_hash=$(sha256sum "${bash_preps[$i]}" | cut -d' ' -f1)
            if [[ "$ref_hash" != "$other_hash" ]]; then
                local ref_rel="${bash_preps[0]#$REPO_ROOT/}"
                local other_rel="${bash_preps[$i]#$REPO_ROOT/}"
                drift "shared script divergence: $other_rel differs from $ref_rel"
                has_drift=true
            fi
        done
    fi

    if ! $has_drift; then
        ok "shared scripts - all copies consistent"
    else
        fix "Sync shared scripts from canonical source, then rebuild containers"
    fi
}

# --- Main ---
main() {
    local mode="check"

    case "${1:-}" in
        --check|"") mode="check" ;;
        --fix) mode="check"; FIX_MODE=true ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 2 ;;
    esac

    echo -e "\n${BOLD}Drift Detection Report${NC}"
    echo "================================================"
    echo -e "Repo: ${BLUE}$REPO_ROOT${NC}"
    echo -e "Date: $(date -Iseconds)\n"

    # Category 1: Systemd units
    echo -e "${BOLD}Systemd Units${NC}"
    echo "------------------------------------------------"
    check_systemd_unit "mcp-second-opinion" \
        "$REPO_ROOT/mcp-second-opinion/deploy/mcp-second-opinion.service.template" \
        "$REPO_ROOT/mcp-second-opinion"
    check_systemd_unit "mcp-playwright" \
        "$REPO_ROOT/mcp-playwright-persistent/deploy/mcp-playwright.service.template" \
        "$REPO_ROOT/mcp-playwright-persistent"
    echo ""

    # Category 2: Sysctl
    echo -e "${BOLD}System Tuning (sysctl)${NC}"
    echo "------------------------------------------------"
    check_sysctl
    echo ""

    # Category 3: Docker containers
    echo -e "${BOLD}Docker Containers${NC}"
    echo "------------------------------------------------"
    check_docker_compose
    echo ""

    # Category 4: Shared script contracts
    echo -e "${BOLD}Shared Script Contracts${NC}"
    echo "------------------------------------------------"
    check_shared_scripts
    echo ""

    # Category 5: MCP deployment model consistency
    echo -e "${BOLD}MCP Deployment Models${NC}"
    echo "------------------------------------------------"
    check_mcp_deployment_models
    check_orphaned_systemd_units
    check_orphaned_docker_mcps
    check_mcp_port_bindings
    echo ""

    # Summary
    echo "================================================"
    if (( DRIFT_COUNT > 0 )); then
        echo -e "${RED}DRIFT DETECTED${NC}: $DRIFT_COUNT issue(s) found ($CHECK_COUNT checked, $SKIP_COUNT skipped)"
        if ! $FIX_MODE; then
            echo -e "Run with ${BOLD}--fix${NC} to see remediation commands"
        fi
        exit 1
    else
        echo -e "${GREEN}NO DRIFT${NC}: $CHECK_COUNT checked, $SKIP_COUNT skipped"
        exit 0
    fi
}

main "$@"
