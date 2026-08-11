#!/usr/bin/env bash
# cpp-commands-link.sh - user-scope command-surface symlinks (issue #663)
#
# Purpose:
#   Serve the CPP command surface to EVERY session on this host by symlinking
#   each family dir of the checkout's .claude/commands/ into
#   ~/.claude/commands/<family>. A symlink follows `git pull` atomically, so
#   command drift is structurally impossible - the property the /plugin
#   marketplace cache lost (#662: `/plugin update` no-ops on a version stamp
#   that never moves, `/plugin install` refuses when installed, and the only
#   reconciliation is per-family uninstall+reinstall by hand).
#
#   Per-FAMILY links (never the whole dir) so the user's own files in
#   ~/.claude/commands/ - hand-written commands, other tools' surfaces - are
#   preserved untouched.
#
# Ownership rule (what this script may ever touch):
#   A target entry is OWNED only when it is a SYMLINK whose readlink target
#   ends in `/.claude/commands/<family>` - the shape only this installer
#   creates. Owned links are refreshed or pruned. Anything else - a real file,
#   a real directory, a symlink pointing anywhere else - is FOREIGN: reported,
#   never modified, never deleted. A foreign entry means the user chose their
#   own content for that family name; their choice wins.
#
# Usage:
#   cpp-commands-link.sh                 # install/refresh, idempotent
#   cpp-commands-link.sh --check         # read-only: report ok/missing/stale/foreign
#   cpp-commands-link.sh --source <dir>  # override the source commands dir (tests)
#
# Contract (last line):
#   CPP_COMMANDS_LINK: ok | installed | drift | error
#     install mode: `installed` when anything changed, `ok` when nothing did
#     --check:      `ok` when every family is a current owned link, `drift`
#                   (exit 1) when any is missing or stale; foreign entries are
#                   reported but are NOT drift - the user's content wins
#
# Env:
#   CPP_COMMANDS_LINK_HOME   override $HOME (install target root; tests)

set -uo pipefail

MODE="install"
SOURCE_OVERRIDE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --check) MODE="check" ;;
        --source)
            shift
            SOURCE_OVERRIDE="${1:-}"
            ;;
        --source=*) SOURCE_OVERRIDE="${1#--source=}" ;;
        *)
            echo "cpp-commands-link: unknown argument: $1" >&2
            echo "CPP_COMMANDS_LINK: error"
            exit 2
            ;;
    esac
    shift
done

# Resolve the source commands dir: explicit override, else the checkout this
# script lives in (~/.claude/scripts/cpp-commands-link.sh is a symlink into
# the checkout, so readlink -f lands there).
if [ -n "$SOURCE_OVERRIDE" ]; then
    SRC="$SOURCE_OVERRIDE"
else
    SELF="$(readlink -f "${BASH_SOURCE[0]}")"
    SRC="$(dirname "$(dirname "$SELF")")/.claude/commands"
fi

if [ ! -d "$SRC" ]; then
    echo "cpp-commands-link: source commands dir not found: $SRC" >&2
    echo "CPP_COMMANDS_LINK: error"
    exit 2
fi

HOME_DIR="${CPP_COMMANDS_LINK_HOME:-$HOME}"
TARGET="$HOME_DIR/.claude/commands"

changed=0
missing=0
stale=0
foreign=0
ok=0

# Enumerate source families (directories only - the command tree is
# one dir per family).
families=()
for d in "$SRC"/*/; do
    [ -d "$d" ] || continue
    families+=("$(basename "$d")")
done

if [ "${#families[@]}" -eq 0 ]; then
    echo "cpp-commands-link: no family dirs under $SRC" >&2
    echo "CPP_COMMANDS_LINK: error"
    exit 2
fi

[ "$MODE" = "install" ] && mkdir -p "$TARGET"

owned() {
    # $1 = path, $2 = family. Owned iff a symlink whose literal target ends
    # in /.claude/commands/<family> (the shape only this installer writes).
    [ -L "$1" ] || return 1
    case "$(readlink "$1")" in
        */.claude/commands/"$2") return 0 ;;
        *) return 1 ;;
    esac
}

for fam in "${families[@]}"; do
    src_fam="$SRC/$fam"
    dst="$TARGET/$fam"

    if [ -L "$dst" ]; then
        if owned "$dst" "$fam"; then
            if [ "$(readlink "$dst")" = "$src_fam" ]; then
                ok=$((ok + 1))
            else
                # Owned but pointing at another checkout - stale.
                if [ "$MODE" = "install" ]; then
                    ln -sfn "$src_fam" "$dst"
                    echo "updated  $fam -> $src_fam"
                    changed=$((changed + 1))
                else
                    echo "stale    $fam -> $(readlink "$dst")"
                    stale=$((stale + 1))
                fi
            fi
        else
            echo "foreign  $fam (symlink to $(readlink "$dst") - not touched)"
            foreign=$((foreign + 1))
        fi
    elif [ -e "$dst" ]; then
        echo "foreign  $fam (user file/dir - not touched)"
        foreign=$((foreign + 1))
    else
        if [ "$MODE" = "install" ]; then
            ln -s "$src_fam" "$dst"
            echo "linked   $fam -> $src_fam"
            changed=$((changed + 1))
        else
            echo "missing  $fam"
            missing=$((missing + 1))
        fi
    fi
done

# Prune owned orphans: symlinks in the target dir with the owned shape whose
# family no longer exists in the source. Foreign entries are never candidates.
if [ -d "$TARGET" ]; then
    for entry in "$TARGET"/*; do
        [ -L "$entry" ] || continue
        name="$(basename "$entry")"
        # Skip live families - handled above.
        skip=0
        for fam in "${families[@]}"; do
            [ "$name" = "$fam" ] && skip=1 && break
        done
        [ "$skip" -eq 1 ] && continue
        if owned "$entry" "$name"; then
            if [ "$MODE" = "install" ]; then
                rm "$entry"
                echo "pruned   $name (family no longer shipped)"
                changed=$((changed + 1))
            else
                echo "orphan   $name (owned link, family no longer shipped)"
                stale=$((stale + 1))
            fi
        fi
    done
fi

echo "families: ${#families[@]} ok: $ok changed: $changed missing: $missing stale: $stale foreign: $foreign"

if [ "$MODE" = "check" ]; then
    if [ $((missing + stale)) -gt 0 ]; then
        echo "CPP_COMMANDS_LINK: drift"
        exit 1
    fi
    echo "CPP_COMMANDS_LINK: ok"
    exit 0
fi

if [ "$changed" -gt 0 ]; then
    echo "CPP_COMMANDS_LINK: installed"
else
    echo "CPP_COMMANDS_LINK: ok"
fi
exit 0
