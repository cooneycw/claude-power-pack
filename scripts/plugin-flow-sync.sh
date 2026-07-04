#!/usr/bin/env bash
# plugin-flow-sync.sh - keep the packaged flow plugin in sync with its source.
#
# Phase B1 of the plugin-marketplace migration (ADR docs/decisions/
# 0001-plugin-marketplace-packaging.md, issue #477) packages the `flow` command
# family as an installable plugin under plugins/flow/. During the B1->B4 parallel
# window the legacy installer and the plugin BOTH ship the flow commands, so the
# single source of truth stays .claude/commands/flow/*.md and plugins/flow/
# commands/ holds byte-identical copies. This script is the guard that keeps the
# copies honest:
#
#   plugin-flow-sync.sh            # --check (default): fail (exit 1) on any drift
#   plugin-flow-sync.sh --check    # explicit
#   plugin-flow-sync.sh --write    # (re)generate plugins/flow/commands/ from source
#
# Mirrors the scripts/flow-skill-sync.py --check/--write and eli5-core-drift.sh
# idioms. Deterministic and git-free (byte-for-byte local diff, no network) so it
# runs in the git-less CI validate container. Reconcile drift by editing the
# SOURCE (.claude/commands/flow/*.md) then re-running with --write.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$REPO_ROOT/.claude/commands/flow"
DEST_DIR="$REPO_ROOT/plugins/flow/commands"

MODE="check"
case "${1:-}" in
    ""|--check) MODE="check" ;;
    --write)    MODE="write" ;;
    -h|--help)
        sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        exit 0 ;;
    *)
        echo "plugin-flow-sync: unknown argument '$1' (use --check or --write)" >&2
        exit 2 ;;
esac

if [[ ! -d "$SRC_DIR" ]]; then
    echo "plugin-flow-sync: source dir not found: $SRC_DIR" >&2
    exit 2
fi

if [[ "$MODE" == "write" ]]; then
    mkdir -p "$DEST_DIR"
    # Drop orphans (a command removed from source) before copying the current set.
    for f in "$DEST_DIR"/*.md; do
        [[ -e "$f" ]] || continue
        base="$(basename "$f")"
        if [[ ! -f "$SRC_DIR/$base" ]]; then
            rm -f "$f"
            echo "plugin-flow-sync: removed orphan $base"
        fi
    done
    count=0
    for f in "$SRC_DIR"/*.md; do
        [[ -e "$f" ]] || continue
        cp "$f" "$DEST_DIR/"
        count=$((count + 1))
    done
    echo "plugin-flow-sync: wrote $count command(s) to plugins/flow/commands/ from .claude/commands/flow/"
    exit 0
fi

# --check: byte-identical parity, both directions (missing, changed, orphaned).
drift=0
count=0
for f in "$SRC_DIR"/*.md; do
    [[ -e "$f" ]] || continue
    count=$((count + 1))
    base="$(basename "$f")"
    dest="$DEST_DIR/$base"
    if [[ ! -f "$dest" ]]; then
        echo "MISSING in plugin: $base"
        drift=1
        continue
    fi
    if ! diff -q "$f" "$dest" >/dev/null 2>&1; then
        echo "DRIFT: $base differs from source"
        drift=1
    fi
done
for f in "$DEST_DIR"/*.md; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f")"
    if [[ ! -f "$SRC_DIR/$base" ]]; then
        echo "ORPHAN in plugin: $base (no matching source command)"
        drift=1
    fi
done

if [[ "$drift" -ne 0 ]]; then
    echo "" >&2
    echo "plugin-flow-sync: DRIFT detected between .claude/commands/flow/ and" >&2
    echo "plugins/flow/commands/. Edit the SOURCE (.claude/commands/flow/*.md), then" >&2
    echo "run: scripts/plugin-flow-sync.sh --write" >&2
    exit 1
fi

echo "plugin-flow-sync: plugins/flow/commands is in sync with .claude/commands/flow ($count files)"
exit 0
