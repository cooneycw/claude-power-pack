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
# The cpp plugin ships help/meta plus the cross-cutting utilities folded in by
# issue #582 (dockers, happy-check, load-best-practices, load-mcp-docs; ADR 0001
# amendment 2026-07-18). The /cpp:init|status|update symlink installer stays
# excluded: it is the legacy surface this migration replaced in Phase B4.
#
# Supersedes the B1 scripts/plugin-flow-sync.sh (issue #477), retired in B4
# (#480). Mirrors the eli5-core-drift.sh deterministic-generator idiom.
# Deterministic and git-free (byte-for-byte local diff, no network) so it runs
# in the git-less CI validate container. Reconcile drift by editing the SOURCE
# (.claude/commands/<family>/*.md) then re-running with --write.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# PLUGIN_SYNC_REPO_ROOT is a test seam (hermetic tmp trees); unset in real use.
REPO_ROOT="${PLUGIN_SYNC_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

# Every packaged family (ADR 0001 target design).
FAMILIES=(
    browser cicd claude-md codex cpp documentation evaluate flow github
    project qa second-opinion secrets security self-improvement
)

# Families deliberately not packaged as plugins (ADR 0001 B2 resolution):
#   spec: spec-kit is the upstream product; /spec:adopt installs it.
UNPACKAGED_FAMILIES=(spec)

# Loose *.md files allowed directly under .claude/commands/. Empty by design
# since #582 folded the last six into families: a top-level command is outside
# every family glob, so BOTH generated surfaces (plugins/, codex/skills/)
# silently exclude it and no drift check can see it. Adding a name here is an
# explicit, reviewed exception - not a home for new commands.
TOP_LEVEL_EXCLUDE=()

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
    # The flow commands call these helpers by name; without them a
    # marketplace-only install dead-ends at exit 127 (issue #590). Bundled here,
    # then placed at the stable ~/.claude/scripts/ path - the one the #581
    # allowlist rules match - by /flow:repair (flow-helpers-install.sh, itself
    # bundled so a plugin-only user can run it). flow-start-resolve.sh resolves
    # flow-live-driver-guard.sh via $SELF_DIR, so the two must travel together.
    [flow]="scripts/flow-start-resolve.sh scripts/flow-live-driver-guard.sh scripts/flow-worktree-claim.sh scripts/flow-stale-check.sh scripts/flow-worktree-guard.sh scripts/gh-pr-merge.sh scripts/worktree-remove.sh scripts/friction-log.sh scripts/check-ignored-additions.sh scripts/flow-helpers-install.sh"
    # /cpp:load-best-practices reads this doc; a plugin-only install has no CPP
    # checkout, so the plugin bundles it (resolved via ${CLAUDE_PLUGIN_ROOT}).
    [cpp]="docs/reference/CLAUDE_CODE_BEST_PRACTICES_FULL.md"
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

# Discovery-completeness gate (#582): every source under .claude/commands/ must
# map to a packaged family or an explicit exclusion. Packaging globs only
# .claude/commands/<family>/*.md, so a top-level file or an unlisted family dir
# is not excluded by the parity diff - it is invisible to it.
completeness_check() {
    local rc=0 f base d fam item known
    for f in "$REPO_ROOT/.claude/commands/"*.md; do
        [[ -e "$f" ]] || continue
        base="$(basename "$f")"
        known=0
        for item in "${TOP_LEVEL_EXCLUDE[@]}"; do
            [[ "$item" == "$base" ]] && known=1 && break
        done
        if [[ "$known" -eq 0 ]]; then
            echo "UNPACKAGED top-level command: .claude/commands/$base (move it into a family dir, or list it in TOP_LEVEL_EXCLUDE)"
            rc=1
        fi
    done
    for d in "$REPO_ROOT/.claude/commands/"*/; do
        [[ -d "$d" ]] || continue
        fam="$(basename "$d")"
        known=0
        for item in "${FAMILIES[@]}" "${UNPACKAGED_FAMILIES[@]}"; do
            [[ "$item" == "$fam" ]] && known=1 && break
        done
        if [[ "$known" -eq 0 ]]; then
            echo "UNPACKAGED family: .claude/commands/$fam/ (add it to FAMILIES, or list it in UNPACKAGED_FAMILIES)"
            rc=1
        fi
    done
    return $rc
}

drift=0
if [[ "$MODE" == "check" ]]; then
    completeness_check || drift=1
fi
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
