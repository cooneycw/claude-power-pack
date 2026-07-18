#!/usr/bin/env bash
# commands-mirror-sync.sh - drift guard + refresher for an out-of-repo commands mirror.
#
# Some hosts serve the CPP command surface from a byte-copy of .claude/commands/
# outside the repo (e.g. ~/Projects/.claude/commands, project scope for sessions
# started above the checkout) instead of /plugin installs. Nothing maintained
# those mirrors, so they silently go stale as CPP merges land - and a current
# mirror masks packaging gaps from the very box that would notice them (#582).
#
#   commands-mirror-sync.sh --check [MIRROR_DIR]   # report drift (exit 1)
#   commands-mirror-sync.sh --write [MIRROR_DIR]   # refresh mirror from the repo
#
# MIRROR_DIR falls back to $CPP_COMMANDS_MIRROR. With neither set, --check exits
# 0 with a note (fail-open: hosts without a mirror have nothing to guard) and
# --write is a usage error. The mirror is a FULL byte copy of .claude/commands/
# (all families, including repo-local ones like cpp:init); the repo is always
# the source of truth - reconcile drift by re-running --write, never by editing
# the mirror.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$REPO_ROOT/.claude/commands"

MODE=""
MIRROR="${CPP_COMMANDS_MIRROR:-}"
for arg in "$@"; do
    case "$arg" in
        --check) MODE="check" ;;
        --write) MODE="write" ;;
        -h|--help)
            sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        -*)
            echo "commands-mirror-sync: unknown argument '$arg' (use --check or --write)" >&2
            exit 2 ;;
        *) MIRROR="$arg" ;;
    esac
done

if [[ -z "$MODE" ]]; then
    MODE="check"
fi

if [[ ! -d "$SRC" ]]; then
    echo "commands-mirror-sync: source not found: $SRC" >&2
    exit 2
fi

if [[ -z "$MIRROR" ]]; then
    if [[ "$MODE" == "write" ]]; then
        echo "commands-mirror-sync: no mirror dir (pass MIRROR_DIR or set CPP_COMMANDS_MIRROR)" >&2
        exit 2
    fi
    echo "commands-mirror-sync: no mirror configured (nothing to guard)"
    exit 0
fi

if [[ "$MODE" == "check" ]]; then
    if [[ ! -d "$MIRROR" ]]; then
        echo "commands-mirror-sync: mirror dir absent: $MIRROR (nothing to guard)"
        exit 0
    fi
    if diff -rq "$SRC" "$MIRROR" >/dev/null 2>&1; then
        echo "commands-mirror-sync: mirror in sync ($MIRROR)"
        exit 0
    fi
    echo "commands-mirror-sync: DRIFT between $SRC and $MIRROR:"
    diff -rq "$SRC" "$MIRROR" | sed 's/^/  /'
    echo "Refresh with: scripts/commands-mirror-sync.sh --write '$MIRROR'" >&2
    exit 1
fi

# --write: prune entries the repo no longer has, then copy everything current.
mkdir -p "$MIRROR"
pruned=0
while IFS= read -r rel; do
    if [[ ! -f "$SRC/$rel" ]]; then
        rm -f "$MIRROR/$rel"
        echo "commands-mirror-sync: pruned $rel"
        pruned=$((pruned + 1))
    fi
done < <(cd "$MIRROR" && find . -type f | sed 's|^\./||')
find "$MIRROR" -depth -type d -empty -delete 2>/dev/null || true

copied=0
while IFS= read -r rel; do
    mkdir -p "$(dirname "$MIRROR/$rel")"
    cp "$SRC/$rel" "$MIRROR/$rel"
    copied=$((copied + 1))
done < <(cd "$SRC" && find . -type f | sed 's|^\./||')
echo "commands-mirror-sync: refreshed $MIRROR ($copied file(s) copied, $pruned pruned)"
exit 0
