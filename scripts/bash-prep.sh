#!/usr/bin/env bash
# bash-prep.sh — Linux workstation tuning for Claude Code
# Part of Claude Power Pack (CPP)
#
# Applies performance tuning: swap, sysctl parameters, inotify limits.
# Safe to run multiple times (idempotent). Requires sudo for system changes.
#
# Usage:
#   bash-prep.sh              # Interactive — detect, report, prompt to apply
#   bash-prep.sh --check      # Report current values only (no changes)
#   bash-prep.sh --apply      # Apply all tuning without prompting
#   bash-prep.sh --help       # Show help

set -euo pipefail

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# --- Desired values ---
TARGET_SWAPPINESS=10
TARGET_VFS_CACHE_PRESSURE=50
TARGET_INOTIFY_WATCHES=524288
TARGET_INOTIFY_INSTANCES=512
MIN_SWAP_MB=2048
MAX_SWAP_MB=4096

# --- Helpers ---
info()  { echo -e "${BLUE}ℹ${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; }

usage() {
    cat <<'EOF'
bash-prep.sh — Linux workstation tuning for Claude Code

Usage:
  bash-prep.sh              Interactive mode (detect, report, prompt)
  bash-prep.sh --check      Report current values only
  bash-prep.sh --apply      Apply all tuning without prompting
  bash-prep.sh --help       Show this help

Tuning applied:
  Swap            min(RAM, 4GB) swap file at /swapfile
  vm.swappiness   10  (prefer RAM, reduce unnecessary swap)
  vm.vfs_cache_pressure  50  (keep filesystem metadata cached)
  fs.inotify.max_user_watches   524288  (prevent watcher failures)
  fs.inotify.max_user_instances 512     (headroom for multiple watchers)

All changes persist across reboots via /etc/sysctl.d/ and /etc/fstab.
EOF
}

# --- Detection functions ---
get_ram_mb() {
    awk '/MemTotal/ { printf "%d", $2 / 1024 }' /proc/meminfo
}

get_swap_mb() {
    awk '/SwapTotal/ { printf "%d", $2 / 1024 }' /proc/meminfo
}

get_sysctl() {
    sysctl -n "$1" 2>/dev/null || echo "unknown"
}

target_swap_mb() {
    local ram_mb
    ram_mb=$(get_ram_mb)
    local target=$ram_mb
    if (( target < MIN_SWAP_MB )); then
        target=$MIN_SWAP_MB
    fi
    if (( target > MAX_SWAP_MB )); then
        target=$MAX_SWAP_MB
    fi
    echo "$target"
}

# --- Check / Report ---
check_all() {
    local issues=0

    echo -e "\n${BOLD}System Tuning Report${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # RAM
    local ram_mb
    ram_mb=$(get_ram_mb)
    info "RAM: ${ram_mb} MB"

    # Swap
    local swap_mb target_mb
    swap_mb=$(get_swap_mb)
    target_mb=$(target_swap_mb)
    if (( swap_mb >= target_mb )); then
        ok "Swap: ${swap_mb} MB (target: ${target_mb} MB)"
    else
        warn "Swap: ${swap_mb} MB — recommended ${target_mb} MB"
        ((issues++))
    fi

    # Swappiness
    local val
    val=$(get_sysctl vm.swappiness)
    if [[ "$val" == "$TARGET_SWAPPINESS" ]]; then
        ok "vm.swappiness = ${val}"
    else
        warn "vm.swappiness = ${val} — recommended ${TARGET_SWAPPINESS}"
        ((issues++))
    fi

    # VFS cache pressure
    val=$(get_sysctl vm.vfs_cache_pressure)
    if [[ "$val" == "$TARGET_VFS_CACHE_PRESSURE" ]]; then
        ok "vm.vfs_cache_pressure = ${val}"
    else
        warn "vm.vfs_cache_pressure = ${val} — recommended ${TARGET_VFS_CACHE_PRESSURE}"
        ((issues++))
    fi

    # Inotify watches
    val=$(get_sysctl fs.inotify.max_user_watches)
    if (( val >= TARGET_INOTIFY_WATCHES )); then
        ok "fs.inotify.max_user_watches = ${val}"
    else
        warn "fs.inotify.max_user_watches = ${val} — recommended ${TARGET_INOTIFY_WATCHES}"
        ((issues++))
    fi

    # Inotify instances
    val=$(get_sysctl fs.inotify.max_user_instances)
    if (( val >= TARGET_INOTIFY_INSTANCES )); then
        ok "fs.inotify.max_user_instances = ${val}"
    else
        warn "fs.inotify.max_user_instances = ${val} — recommended ${TARGET_INOTIFY_INSTANCES}"
        ((issues++))
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if (( issues == 0 )); then
        ok "All values are optimal. No changes needed."
    else
        warn "${issues} value(s) could be improved."
    fi

    return $issues
}

# --- Apply functions ---
check_sudo() {
    if ! sudo -n true 2>/dev/null; then
        info "sudo required for system changes."
        if ! sudo true; then
            err "Cannot obtain sudo. Skipping system changes."
            return 1
        fi
    fi
    return 0
}

apply_swap() {
    local swap_mb target_mb
    swap_mb=$(get_swap_mb)
    target_mb=$(target_swap_mb)

    if (( swap_mb >= target_mb )); then
        ok "Swap already sufficient (${swap_mb} MB >= ${target_mb} MB)"
        return 0
    fi

    info "Creating ${target_mb} MB swap file at /swapfile..."

    if [[ -f /swapfile ]]; then
        # Existing swapfile — check if it's active
        if swapon --show=NAME --noheadings | grep -q '/swapfile'; then
            sudo swapoff /swapfile
        fi
        sudo rm -f /swapfile
    fi

    sudo dd if=/dev/zero of=/swapfile bs=1M count="$target_mb" status=progress
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile

    # Persist in fstab
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
        ok "Added /swapfile to /etc/fstab"
    fi

    ok "Swap configured: ${target_mb} MB"
}

apply_sysctl() {
    local conf="/etc/sysctl.d/99-claude-code.conf"

    info "Writing sysctl parameters to ${conf}..."

    sudo tee "$conf" > /dev/null <<EOF
# Claude Code workstation tuning (applied by Claude Power Pack bash-prep)
vm.swappiness = ${TARGET_SWAPPINESS}
vm.vfs_cache_pressure = ${TARGET_VFS_CACHE_PRESSURE}
fs.inotify.max_user_watches = ${TARGET_INOTIFY_WATCHES}
fs.inotify.max_user_instances = ${TARGET_INOTIFY_INSTANCES}
EOF

    sudo sysctl --load="$conf" > /dev/null
    ok "Sysctl parameters applied and persisted"
}

apply_all() {
    if ! check_sudo; then
        return 1
    fi

    echo -e "\n${BOLD}Applying workstation tuning...${NC}\n"
    apply_swap
    apply_sysctl
    echo ""
    ok "Workstation tuning complete. Changes persist across reboots."
}

# --- Main ---
main() {
    local mode="interactive"

    case "${1:-}" in
        --check)  mode="check" ;;
        --apply)  mode="apply" ;;
        --help|-h) usage; exit 0 ;;
        "") mode="interactive" ;;
        *) err "Unknown option: $1"; usage; exit 1 ;;
    esac

    # Platform check
    if [[ "$(uname)" != "Linux" ]]; then
        warn "bash-prep is designed for Linux. Detected: $(uname)"
        warn "Skipping — no changes made."
        exit 0
    fi

    case "$mode" in
        check)
            check_all || true
            ;;
        apply)
            check_all || true
            echo ""
            apply_all
            echo ""
            check_all || true
            ;;
        interactive)
            check_all
            local needs_changes=$?
            if (( needs_changes == 0 )); then
                exit 0
            fi
            echo ""
            read -rp "Apply recommended tuning? [y/N] " answer
            if [[ "$answer" =~ ^[Yy] ]]; then
                apply_all
                echo ""
                check_all || true
            else
                info "No changes made."
            fi
            ;;
    esac
}

main "$@"
