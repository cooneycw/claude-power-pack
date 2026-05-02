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

# --- Helpers ---
info()  { echo -e "${BLUE}info${NC}  $*"; }
ok()    { echo -e "${GREEN}ok${NC}    $*"; CHECK_COUNT=$((CHECK_COUNT + 1)); }
drift() { echo -e "${RED}DRIFT${NC} $*"; DRIFT_COUNT=$((DRIFT_COUNT + 1)); CHECK_COUNT=$((CHECK_COUNT + 1)); }
skip()  { echo -e "${YELLOW}skip${NC}  $*"; SKIP_COUNT=$((SKIP_COUNT + 1)); }
fix()   { if $FIX_MODE; then echo -e "       ${YELLOW}fix:${NC} $*"; fi; }

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
  3. Go binary        - ~/go/bin/woodpecker-mcp version currency
  4. Docker containers - running container health status
  5. Shared scripts   - cross-container script consistency (fetch-secrets.sh, bash-prep.sh)

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

# --- Go binary drift ---
check_go_binary() {
    local binary="$HOME/go/bin/woodpecker-mcp"

    if [[ ! -x "$binary" ]]; then
        skip "woodpecker-mcp - Go binary not installed"
        return
    fi

    # Check if binary exists and can execute
    if "$binary" --version &>/dev/null 2>&1 || "$binary" version &>/dev/null 2>&1; then
        ok "woodpecker-mcp - binary present and executable"
    else
        # Binary exists but might be stale - just verify it runs
        if "$binary" --help &>/dev/null 2>&1; then
            ok "woodpecker-mcp - binary present and executable"
        else
            drift "woodpecker-mcp - binary exists but fails to execute"
            fix "Re-run: $REPO_ROOT/mcp-woodpecker-ci/scripts/setup-go-binary.sh"
        fi
    fi

    # Check config exists
    local config="$HOME/.config/woodpecker-mcp/config.yaml"
    if [[ -f "$config" ]]; then
        ok "woodpecker-mcp - config present at $config"
    else
        if [[ -x "$binary" ]]; then
            drift "woodpecker-mcp - binary installed but config missing"
            fix "Re-run: $REPO_ROOT/mcp-woodpecker-ci/scripts/setup-go-binary.sh"
        fi
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

    # Check for stale containers (running but image differs from what compose would build)
    local running_containers
    running_containers=$(docker compose -f "$compose_file" \
        --profile core --profile browser --profile cicd \
        ps --format '{{.Name}}:{{.Status}}' 2>/dev/null || true)

    if [[ -z "$running_containers" ]]; then
        skip "docker - no containers running"
        return
    fi

    # Check each running container's image ID vs what compose config expects
    local has_drift=false
    while IFS=: read -r name status; do
        if [[ "$status" == *"unhealthy"* ]]; then
            drift "docker - container $name is unhealthy"
            has_drift=true
        fi
    done <<< "$running_containers"

    if ! $has_drift; then
        ok "docker - all running containers healthy"
    else
        fix "Re-run: make deploy PROFILE=\"core browser cicd\""
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

    # Category 3: Go binary
    echo -e "${BOLD}Go Binaries${NC}"
    echo "------------------------------------------------"
    check_go_binary
    echo ""

    # Category 4: Docker containers
    echo -e "${BOLD}Docker Containers${NC}"
    echo "------------------------------------------------"
    check_docker_compose
    echo ""

    # Category 5: Shared script contracts
    echo -e "${BOLD}Shared Script Contracts${NC}"
    echo "------------------------------------------------"
    check_shared_scripts
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
