#!/usr/bin/env bash
#: HOST-SURFACE: ~/.claude/commands/<family> owner=cpp write=symlink certified=observed
#: HOST-SURFACE: note - target is $HOME_DIR/.claude/commands, overridable by CPP_COMMANDS_LINK_HOME
#: The mkdir'd parents below are declared `certified=observed`, not
#: `authored`: they were found by running this script against a sandboxed
#: $HOME and diffing what appeared (issue #1150), not by a person reading
#: the code. `authored` means "a person read the code and wrote down what it
#: writes", which would be false here - static reading produced the
#: declaration above and missed these. scripts/host-surface-observe.py
#: re-derives them on every run and reds when they drift.
#: HOST-SURFACE: ~/.claude owner=cpp write=mkdir certified=observed
#: HOST-SURFACE: ~/.claude/commands owner=cpp write=mkdir certified=observed

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
#: NEGATIVE-CONTROL: controls/cpp-commands-link
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
#   CPP_COMMANDS_LINK: ok | installed | drift | drift-missing | unowned | error
#     install mode: `installed` when anything changed, `ok` when nothing did
#     --check:      `ok` (exit 0) when no missing or stale state is found;
#                   `drift` (exit 1) when any link is stale, including an
#                   orphan, regardless of missing links; `drift-missing`
#                   (exit 3) when links are missing but none are stale; `error`
#                   exits 2. Foreign entries are NOT drift - the user's
#                   content wins.
#     install mode: `error` (exit 2) when any `ln`/`rm` FAILED - a mutation that
#                   was attempted and lost is not one that happened, and no
#                   other verdict could describe a state this run never reached
#     BOTH modes:   `unowned` (exit 4) when NOT ONE family is linked by this
#                   installer and every name it would use is occupied by
#                   content it does not own (issue #1138).
#
#   `ok: 0` MAY NOT PRINT `ok` (issue #1138). Until that verdict existed, a run
#   that linked nothing because every target name was already taken emitted
#   `families: 18 ok: 0 ... foreign: 18` and `CPP_COMMANDS_LINK: ok`, exit 0 -
#   on the SAME line. An installer that reports success having installed
#   nothing is indistinguishable from one that worked, and every consumer
#   downstream reads the same word either way.
#
#   Measured in a faithful clone of a live kyle session container, 2026-09-20:
#   all 18 families classify foreign there, because kyle projects the command
#   surface as READ-ONLY BIND MOUNTS and a bind-mounted directory is not a
#   symlink this installer created. The ownership rule is right; what was wrong
#   was the verdict it fed.
#
#   `--check` SHARED THE BLIND SPOT, which is why both modes carry the verdict.
#   ADR 0008 excluded this script from its census on the grounds that an
#   installer's state "is re-derived by the drift and parity checks"; on this
#   input the re-derivation returns the identical wrong answer, so their
#   agreement carried no information. The exclusion is retired in that ADR by
#   the same change that added this verdict.
#
#   `unowned` DESCRIBES A STATE, IT DOES NOT ACCUSE. A user who has
#   deliberately put their own content in every family name reaches it too, and
#   for them it is the correct, useful answer: their choice still wins, and the
#   command surface is genuinely not installed from this checkout.
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

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "CPP_COMMANDS_LINK_EXIT=%d\n" "$?" >&2' EXIT

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
# script lives in.
#
# THE DERIVATION ASSUMES A SYMLINK, AND SAYS SO WHEN THAT FAILS (issue #1138).
# At the stable path `~/.claude/scripts/cpp-commands-link.sh` is normally a
# SYMLINK into the checkout, so `readlink -f` lands there and the two `dirname`
# hops reach the checkout root. In a kyle session container the same path is a
# read-only BIND MOUNT, which `readlink -f` resolves to ITSELF - the hops then
# land in `~/.claude`, and SRC becomes `~/.claude/.claude/commands`, which does
# not exist.
#
# A symlink and a bind mount are indistinguishable to `ls`; they resolve
# differently. The refusal below already existed and was correct, but it named
# the PHANTOM PATH and left the reader hunting for a directory that was never
# supposed to be there. It now names the cause, and detects it positively -
# `self_is_symlink` is checked rather than inferred from the missing directory,
# so the diagnosis does not depend on which wrong path happened to be absent.
if [ -n "$SOURCE_OVERRIDE" ]; then
    SRC="$SOURCE_OVERRIDE"
    SRC_BASIS="--source override"
else
    SELF_RAW="${BASH_SOURCE[0]}"
    SELF="$(readlink -f "$SELF_RAW")"
    SRC="$(dirname "$(dirname "$SELF")")/.claude/commands"
    if [ -L "$SELF_RAW" ]; then
        SRC_BASIS="derived from the symlink at $SELF_RAW"
    else
        SRC_BASIS="derived from a NON-SYMLINK at $SELF_RAW"
    fi
fi

if [ ! -d "$SRC" ]; then
    echo "cpp-commands-link: source commands dir not found: $SRC" >&2
    echo "cpp-commands-link: basis - $SRC_BASIS" >&2
    if [ -z "$SOURCE_OVERRIDE" ] && [ ! -L "$SELF_RAW" ]; then
        echo "  This script locates its source by resolving its own path, which assumes the" >&2
        echo "  stable path is a SYMLINK into a CPP checkout. Here it is not a symlink - a" >&2
        echo "  bind mount resolves to itself - so the derived source is wrong rather than" >&2
        echo "  merely absent. Pass --source <checkout>/.claude/commands to install from a" >&2
        echo "  checkout, or accept that this session's command surface is provided by" >&2
        echo "  something other than this installer (issue #1138)." >&2
    fi
    echo "CPP_COMMANDS_LINK: error"
    exit 2
fi

HOME_DIR="${CPP_COMMANDS_LINK_HOME:-$HOME}"
TARGET="$HOME_DIR/.claude/commands"

changed=0
# Mutations this run ATTEMPTED and lost (counter-model review pass 2, #1138).
# `ln`, `rm` and `mkdir` results were not checked, so on a read-only target a
# failed replacement still printed `updated`, still incremented the counters,
# and still reported `installed`, exit 0 - measured: `families: 2 ok: 0
# changed: 1 ... foreign: 1` with nothing changed on disk. The same
# false-success shape this issue is about, one level under the verdict that was
# added to remove it: a count of INTENTIONS reported as a count of RESULTS.
failed=0
# Family links made THIS run, counted apart from `changed` (counter-model
# review, #1138). `changed` also counts orphan prunes, and an install where
# every current family is foreign but one retired owned symlink got pruned
# therefore reported `installed`, exit 0, with not one family linked -
# measured: `families: 1 ok: 0 changed: 1 ... foreign: 1`. The false success
# this verdict exists to remove, surviving through the prune path.
linked=0
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

if [ "$MODE" = "install" ] && ! mkdir -p "$TARGET" 2>/dev/null; then
    echo "cpp-commands-link: cannot create the target dir: $TARGET" >&2
    echo "CPP_COMMANDS_LINK: error"
    exit 2
fi

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
                    if ln -sfn "$src_fam" "$dst" 2>/dev/null; then
                        echo "updated  $fam -> $src_fam"
                        changed=$((changed + 1))
                        linked=$((linked + 1))
                    else
                        echo "FAILED   $fam -> $src_fam (could not replace the link)" >&2
                        failed=$((failed + 1))
                    fi
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
            if ln -s "$src_fam" "$dst" 2>/dev/null; then
                echo "linked   $fam -> $src_fam"
                changed=$((changed + 1))
                linked=$((linked + 1))
            else
                echo "FAILED   $fam -> $src_fam (could not create the link)" >&2
                failed=$((failed + 1))
            fi
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
                if rm "$entry" 2>/dev/null; then
                    echo "pruned   $name (family no longer shipped)"
                    changed=$((changed + 1))
                else
                    echo "FAILED   $name (could not prune the orphan link)" >&2
                    failed=$((failed + 1))
                fi
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

echo "families: ${#families[@]} ok: $ok changed: $changed missing: $missing stale: $stale foreign: $foreign failed: $failed"

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

# Says WHAT WAS FOUND, never what the user did wrong (issue #1138). Both the
# substrate case and the deliberate-user case reach this verdict, and the line
# has to be true and useful in both - so it reports the state and names the two
# readings rather than picking one.
unowned_report() {
    echo "cpp-commands-link: 0 of ${#families[@]} families are linked by this installer;" >&2
    echo "  every name it would use is occupied by content it does not own, so nothing was installed." >&2
    echo "  If these are files a substrate projects into this session (kyle mounts them read-only)," >&2
    echo "  there is nothing for this installer to do here." >&2
    echo "  If they are yours, your content still wins - but the command surface is NOT" >&2
    echo "  installed from this checkout, and a later 'ok' would have said it was." >&2
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
    # AFTER drift and drift-missing, deliberately (issue #1138). Those two name
    # something actionable about links that exist or are absent; `unowned` is
    # the case where neither applies because not one family is ours at all. A
    # run with both stale links and foreign names is a drift report first - the
    # louder, more specific answer wins.
    if [ "$ok" -eq 0 ] && [ "$foreign" -gt 0 ]; then
        unowned_report
        echo "CPP_COMMANDS_LINK: unowned"
        exit 4
    fi
    echo "CPP_COMMANDS_LINK: ok"
    exit 0
fi

# A MUTATION WAS ATTEMPTED AND LOST. Reported before any other install-mode
# verdict: this run does not know what the surface looks like now, and every
# word below would be a claim about a state it failed to reach.
if [ "$failed" -gt 0 ]; then
    echo "cpp-commands-link: $failed link operation(s) failed - the target may be read-only." >&2
    echo "CPP_COMMANDS_LINK: error"
    exit 2
fi

# NOTHING OURS, AND EVERY NAME TAKEN (issue #1138). Decided on the CURRENT
# FAMILY population and checked BEFORE `installed`, because `changed` also
# counts orphan prunes: pruning a retired link is a real change that installs
# nothing, and letting it report `installed` preserved the exact false success
# this verdict removes (counter-model review). A partially-installed surface
# still reports through the ordinary verdicts, so this cannot fire on a host
# where the installer is doing its job.
if [ "$ok" -eq 0 ] && [ "$linked" -eq 0 ] && [ "$foreign" -gt 0 ]; then
    unowned_report
    echo "CPP_COMMANDS_LINK: unowned"
    exit 4
fi

if [ "$changed" -gt 0 ]; then
    echo "CPP_COMMANDS_LINK: installed"
    exit 0
fi

echo "CPP_COMMANDS_LINK: ok"
exit 0
