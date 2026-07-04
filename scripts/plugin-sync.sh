#!/usr/bin/env bash
# plugin-sync.sh - keep the packaged per-family plugins in sync with their sources.
#
# Phase B2 of the plugin-marketplace migration (ADR docs/decisions/
# 0001-plugin-marketplace-packaging.md, issue #478) packages every surviving
# command family as an installable plugin under plugins/<family>/. During the
# B1->B4 parallel window the legacy installer and the plugins BOTH ship the
# commands, so the single source of truth stays .claude/commands/<family>/*.md
# and plugins/<family>/commands/ holds byte-identical, checked-in copies. This
# script is the guard that keeps every copy honest:
#
#   plugin-sync.sh                      # --check (default): fail (exit 1) on drift
#   plugin-sync.sh --check [family...]  # check some or all families
#   plugin-sync.sh --write [family...]  # (re)generate plugins/<family>/commands/
#
# The cpp plugin ships help.md ONLY: ADR 0001 scopes the cpp plugin to
# cross-cutting help/meta, and the /cpp:init|update|status symlink installer is
# the legacy surface this migration replaces (it retires in Phase B4), so it is
# not distributed through the new one.
#
# Generalizes the B1 scripts/plugin-flow-sync.sh (issue #477), which now shims
# here. Mirrors the flow-skill-sync.py and eli5-core-drift.sh idioms.
# Deterministic and git-free (byte-for-byte local diff, no network) so it runs
# in the git-less CI validate container. Reconcile drift by editing the SOURCE
# (.claude/commands/<family>/*.md) then re-running with --write.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Every packaged family (ADR 0001 target design; spec and the loose top-level
# commands are deliberately not packaged - see the ADR B2 resolution section).
FAMILIES=(
    browser cicd claude-md codex cpp documentation evaluate flow github
    project qa second-opinion secrets security self-improvement
)

# Per-family source basenames excluded from packaging (space-separated).
declare -A EXCLUDE=(
    [cpp]="init.md status.md update.md"
)

# Per-family extra packaged artifacts beyond commands/*.md (space-separated
# repo-root-relative source paths), replicated byte-identically to
# plugins/<family>/<same relative path>. Phase B3 (#479): the secrets plugin
# bundles the PostToolUse masking-hook script so a plugin install masks
# credentials without the host symlink install (its hooks/hooks.json resolves
# the copy via ${CLAUDE_PLUGIN_ROOT}).
declare -A EXTRA_FILES=(
    [secrets]="scripts/hook-mask-output.sh"
)

MODE="check"
SELECTED=()
for arg in "$@"; do
    case "$arg" in
        --check) MODE="check" ;;
        --write) MODE="write" ;;
        -h|--help)
            sed -n '2,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        -*)
            echo "plugin-sync: unknown argument '$arg' (use --check or --write)" >&2
            exit 2 ;;
        *) SELECTED+=("$arg") ;;
    esac
done

if [[ ${#SELECTED[@]} -eq 0 ]]; then
    SELECTED=("${FAMILIES[@]}")
else
    for family in "${SELECTED[@]}"; do
        known=0
        for f in "${FAMILIES[@]}"; do
            [[ "$f" == "$family" ]] && known=1 && break
        done
        if [[ "$known" -eq 0 ]]; then
            echo "plugin-sync: unknown family '$family' (known: ${FAMILIES[*]})" >&2
            exit 2
        fi
    done
fi

is_excluded() {
    local family="$1" base="$2" item
    for item in ${EXCLUDE[$family]:-}; do
        [[ "$item" == "$base" ]] && return 0
    done
    return 1
}

drift=0
for family in "${SELECTED[@]}"; do
    src_dir="$REPO_ROOT/.claude/commands/$family"
    dest_dir="$REPO_ROOT/plugins/$family/commands"

    if [[ ! -d "$src_dir" ]]; then
        echo "plugin-sync: source dir not found: $src_dir" >&2
        exit 2
    fi

    if [[ "$MODE" == "write" ]]; then
        mkdir -p "$dest_dir"
        # Drop orphans (removed from source, or newly excluded) before copying.
        for f in "$dest_dir"/*.md; do
            [[ -e "$f" ]] || continue
            base="$(basename "$f")"
            if [[ ! -f "$src_dir/$base" ]] || is_excluded "$family" "$base"; then
                rm -f "$f"
                echo "plugin-sync: $family: removed orphan $base"
            fi
        done
        count=0
        for f in "$src_dir"/*.md; do
            [[ -e "$f" ]] || continue
            base="$(basename "$f")"
            is_excluded "$family" "$base" && continue
            cp "$f" "$dest_dir/"
            count=$((count + 1))
        done
        echo "plugin-sync: $family: wrote $count command(s) to plugins/$family/commands/"
        for rel in ${EXTRA_FILES[$family]:-}; do
            src="$REPO_ROOT/$rel"
            dest="$REPO_ROOT/plugins/$family/$rel"
            if [[ ! -f "$src" ]]; then
                echo "plugin-sync: $family: extra source not found: $rel" >&2
                exit 2
            fi
            mkdir -p "$(dirname "$dest")"
            cp -p "$src" "$dest"
            echo "plugin-sync: $family: wrote extra $rel"
        done
        continue
    fi

    # --check: byte-identical parity, both directions (missing, changed, orphaned).
    count=0
    family_drift=0
    for f in "$src_dir"/*.md; do
        [[ -e "$f" ]] || continue
        base="$(basename "$f")"
        is_excluded "$family" "$base" && continue
        count=$((count + 1))
        dest="$dest_dir/$base"
        if [[ ! -f "$dest" ]]; then
            echo "MISSING in plugin: $family/$base"
            family_drift=1
            continue
        fi
        if ! diff -q "$f" "$dest" >/dev/null 2>&1; then
            echo "DRIFT: $family/$base differs from source"
            family_drift=1
        fi
    done
    for f in "$dest_dir"/*.md; do
        [[ -e "$f" ]] || continue
        base="$(basename "$f")"
        if [[ ! -f "$src_dir/$base" ]] || is_excluded "$family" "$base"; then
            echo "ORPHAN in plugin: $family/$base (no matching source command)"
            family_drift=1
        fi
    done
    for rel in ${EXTRA_FILES[$family]:-}; do
        src="$REPO_ROOT/$rel"
        dest="$REPO_ROOT/plugins/$family/$rel"
        count=$((count + 1))
        if [[ ! -f "$src" ]]; then
            echo "plugin-sync: $family: extra source not found: $rel" >&2
            family_drift=1
        elif [[ ! -f "$dest" ]]; then
            echo "MISSING in plugin: $family/$rel"
            family_drift=1
        elif ! diff -q "$src" "$dest" >/dev/null 2>&1; then
            echo "DRIFT: $family/$rel differs from source"
            family_drift=1
        fi
    done
    if [[ "$family_drift" -eq 0 ]]; then
        echo "plugin-sync: $family in sync ($count files)"
    else
        drift=1
    fi
done

if [[ "$MODE" == "check" && "$drift" -ne 0 ]]; then
    echo "" >&2
    echo "plugin-sync: DRIFT detected between .claude/commands/<family>/ and" >&2
    echo "plugins/<family>/commands/. Edit the SOURCE (.claude/commands/), then" >&2
    echo "run: scripts/plugin-sync.sh --write" >&2
    exit 1
fi

exit 0
