#!/usr/bin/env bash
# cpp-commands-link.sh - user-scope command-surface symlinks (issue #663)
#
# Purpose:
#   Serve the CPP command surface to EVERY session on this host by symlinking
#   each family dir of the checkout's .claude/commands/ into
#   ~/.claude/commands/<family>. A symlink follows `git pull` atomically with no
#   cache to reconcile - the property the /plugin marketplace cache lost (#662:
#   `/plugin update` no-ops on a version stamp that never moves, `/plugin
#   install` refuses when installed, and the only reconciliation is per-family
#   uninstall+reinstall by hand).
#
#   SCOPE OF THAT GUARANTEE (issue #685). A link follows the checkout's REF; it
#   cannot follow the checkout's CONTENT. This header used to conclude "command
#   drift is structurally impossible", and that inference is false: the premise
#   above is true, the conclusion is not. A restore-over-clone accident produced
#   a working tree with 106 files reverted to month-old content and 111
#   upstream-deleted files resurrected, HEAD untouched. Every link resolved,
#   `--check` reported ok, and `git pull` said "Already up to date" - three
#   independent green signals on a fully corrupted install, every served command
#   stale. Cache drift is what this design eliminates. Working-tree corruption is
#   a different failure and nothing here prevents it.
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
#   CPP_COMMANDS_LINK: ok | installed | drift | drift-missing | error
#     install mode: `installed` when anything changed, `ok` when nothing did
#     --check:      `ok` (exit 0) when no missing or stale state is found;
#                   `drift` (exit 1) when any link is stale, including an
#                   orphan, regardless of missing links; `drift-missing`
#                   (exit 3) when links are missing but none are stale; `error`
#                   exits 2. Foreign entries are NOT drift - the user's
#                   content wins.
#
#   `ok` IS A TOPOLOGY VERDICT, NOT A HEALTH VERDICT (#685). It says every family
#   link resolves to this checkout. It says NOTHING about whether the checkout's
#   content is what it should be. To assess content:
#       git -C <checkout> status --porcelain -uall   # expect empty
#       git -C <checkout> rev-parse HEAD origin/main # expect equal
#   `-uall` is load-bearing: default `git status` collapses an untracked
#   directory to ONE entry, under-reporting resurrected files (measured 3 vs 1
#   on a clean dev box; ~16x in the #685 field case).
#
#   --check also prints one ADVISORY line when the checkout is dirty (below).
#   It is an observation, never part of the verdict.
#
# Env:
#   CPP_COMMANDS_LINK_HOME   override $HOME (install target root; tests)
#   CPP_COMMANDS_LINK_NO_PROBE=1  skip the dirtiness advisory entirely

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
                # Deliberately stale, not missing: pruning an orphan removes a
                # command family the user can currently see, so it is not a
                # safe missing-family self-heal.
                echo "orphan   $name (owned link, family no longer shipped)"
                stale=$((stale + 1))
            fi
        fi
    done
fi

echo "families: ${#families[@]} ok: $ok changed: $changed missing: $missing stale: $stale foreign: $foreign"

# --- Content advisory (issue #685) -----------------------------------------
# Topology and content are separate questions and this script only answers the
# first. The advisory stops the second from being SILENT: it reports what the
# checkout's working tree looks like, and nothing else.
#
# It is NOT a verdict. It never changes the marker or the exit code, because
# dirtiness is not staleness - this cannot tell a maintainer mid-edit from a
# corrupted restore, and pretending otherwise would swap a silent gap for a
# false alarm.
#
# The counts are reported SPLIT rather than as one total, which is what makes
# the line diagnostic instead of merely noisy: a clean dev box reads
# "0 tracked, 3 untracked" (measured on this repo - benign scratch), while the
# #685 corruption read 106 tracked and 111 untracked. One merged number makes
# those two look the same, and a line that reads identically in the healthy and
# broken cases is the exact failure this advisory exists to end.
#
# FAIL-OPEN at every step: no git binary, not a repo, or any git error prints
# NOTHING and leaves the verdict untouched. A check that starts erroring because
# git is absent would be a worse regression than the silence it replaces.
content_advisory() {
    [ -n "${CPP_COMMANDS_LINK_NO_PROBE:-}" ] && return 0
    command -v git >/dev/null 2>&1 || return 0
    git -C "$SRC" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0

    local tracked untracked
    tracked="$(git -C "$SRC" diff --name-only HEAD -- 2>/dev/null | grep -c . || true)"
    untracked="$(git -C "$SRC" ls-files --others --exclude-standard 2>/dev/null | grep -c . || true)"
    [ -n "$tracked" ] || return 0
    [ -n "$untracked" ] || return 0
    [ $((tracked + untracked)) -gt 0 ] || return 0

    echo "checkout: $tracked tracked modified, $untracked untracked (-uall) - links resolve; content not verified"
}

if [ "$MODE" = "check" ]; then
    content_advisory
    if [ "$stale" -gt 0 ]; then
        echo "CPP_COMMANDS_LINK: drift"
        exit 1
    fi
    if [ "$missing" -gt 0 ]; then
        # Exit 3 deliberately separates safe missing-only drift. Exit 2 already
        # means error, while existing consumers still treat every non-zero as
        # not clean, preserving backward compatibility.
        echo "CPP_COMMANDS_LINK: drift-missing"
        exit 3
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
