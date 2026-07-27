#!/usr/bin/env bash
# install-drift.sh - report drift between the INSTALLED command surface and the
# CPP checkout (issue #622).
#
# Problem:
#   The copy of a command the Skill tool loads is not the copy the repo
#   maintains. `/plugin install <family>@cpp` snapshots the commands into
#   ~/.claude/plugins/, and that snapshot only moves when the plugin is
#   re-installed - while the checkout moves on every `git pull`. On flow:auto #65
#   the installed text was 15 commits / 7 days behind, so the session ran the
#   pre-#595 verifier invocation, re-diagnosed a bug #595 had already fixed, and
#   was about to file a duplicate issue for it. Nothing said the text was stale.
#
#   It is worse than plain staleness because the install is SPLIT and the halves
#   drift independently: the helper scripts live at ~/.claude/scripts/ (symlinked
#   from a checkout, so current the moment you pull) while the markdown that
#   drives them lives in the plugin snapshot. A run then gets new helpers driven
#   by old instructions, silent in both directions.
#
# What it compares (all local, no network, never writes):
#   1. ~/.claude/plugins/marketplaces/cpp - a git clone: commit distance from the
#      checkout when the sha is resolvable there, else content parity.
#   2. ~/.claude/plugins/cache/cpp/<family>/<version>/commands - plain copies with
#      no git at all, and the ones a session actually executes: content parity
#      per command file.
#   3. ~/.claude/scripts/*.sh - the helper half, so the SPLIT case is named
#      rather than left to be inferred. Only files the checkout also has are
#      judged; a host's own scripts are none of this check's business.
#
# Usage:
#   install-drift.sh                # human report; exit 1 on drift
#   install-drift.sh --list         # same, listing every stale file (not a sample)
#   install-drift.sh --quiet        # ONE line if drift, silent otherwise; ALWAYS exit 0
#   install-drift.sh --json         # machine-readable; exit 1 on drift
#
# Output always ends with a verdict line:
#   INSTALL_DRIFT: ok | drift | skipped | error
#
# `skipped` is a first-class, non-failing answer: a marketplace-only user has no
# checkout to compare against, and a checkout-only user has no plugin install.
# Neither is a problem, and neither should ever be reported as one.
#
# Env (test seams - unset in normal use):
#   CPP_INSTALL_DRIFT_HOME      override $HOME (plugin + helper roots)
#   CPP_INSTALL_DRIFT_CHECKOUT  override checkout detection

set -uo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SELF_DIR="$(cd "$(dirname "$SELF")" && pwd)"
HOME_DIR="${CPP_INSTALL_DRIFT_HOME:-${HOME:-}}"

MODE="report"
LIST_ALL=0
SAMPLE=8

for arg in "$@"; do
    case "$arg" in
        --check|--report) MODE="report" ;;
        --quiet) MODE="quiet" ;;
        --json) MODE="json" ;;
        --list) LIST_ALL=1 ;;
        -h|--help)
            sed -n '2,47p' "$SELF" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            echo "install-drift: unknown argument '$arg' (use --quiet, --json, --list)" >&2
            exit 2 ;;
    esac
done

# --- Resolve the checkout (the source of truth) -----------------------------
is_checkout() {
    [ -n "$1" ] && [ -f "$1/CLAUDE.md" ] && [ -d "$1/.claude/commands" ] && [ -d "$1/plugins" ]
}

CHECKOUT=""
if [ -n "${CPP_INSTALL_DRIFT_CHECKOUT:-}" ]; then
    # An explicit override that is not a checkout is an operator error, not a
    # reason to silently fall through to some other repo on the box.
    if is_checkout "$CPP_INSTALL_DRIFT_CHECKOUT"; then
        CHECKOUT="$CPP_INSTALL_DRIFT_CHECKOUT"
    else
        echo "install-drift: CPP_INSTALL_DRIFT_CHECKOUT is not a CPP checkout: $CPP_INSTALL_DRIFT_CHECKOUT" >&2
        echo "INSTALL_DRIFT: error"
        exit 2
    fi
else
    # Self-location first: symlinked into ~/.claude/scripts/, readlink -f above
    # already resolved back to <checkout>/scripts, so this is the common case.
    for dir in "$SELF_DIR/.." "${HOME_DIR:+$HOME_DIR/Projects/claude-power-pack}" \
               /opt/claude-power-pack "${HOME_DIR:+$HOME_DIR/.claude-power-pack}"; do
        [ -n "$dir" ] || continue
        if is_checkout "$dir"; then
            CHECKOUT="$(cd "$dir" && pwd)"
            break
        fi
    done
fi

emit_skip() {  # $1 = reason
    case "$MODE" in
        # A hook must stay silent when there is nothing to say - not even the
        # verdict line, which would otherwise land in every session's context.
        quiet) : ;;
        json) printf '{"verdict":"skipped","reason":"%s"}\n' "$1" ;;
        *)
            echo "install-drift: $1"
            echo "INSTALL_DRIFT: skipped" ;;
    esac
    exit 0
}

[ -n "$CHECKOUT" ] || emit_skip "no CPP checkout found - nothing to compare the install against"

PLUGINS_DIR="${HOME_DIR:+$HOME_DIR/.claude/plugins}"
MKT="${PLUGINS_DIR:+$PLUGINS_DIR/marketplaces/cpp}"
CACHE="${PLUGINS_DIR:+$PLUGINS_DIR/cache/cpp}"
SCRIPTS_DIR="${HOME_DIR:+$HOME_DIR/.claude/scripts}"

if [ -z "$PLUGINS_DIR" ] || { [ ! -d "$MKT" ] && [ ! -d "$CACHE" ]; }; then
    emit_skip "no CPP plugin install found under ${PLUGINS_DIR:-~/.claude/plugins} - nothing to compare"
fi

# --- 1. Commit distance (marketplace clone vs checkout) ---------------------
# Resolved in the CHECKOUT, not the clone: the clone was fetched at install time
# and does not have the commits that landed since, while the checkout has both
# ends of the range whenever the clone's HEAD is an ancestor of its own.
COMMIT_STATE="unavailable"
BEHIND=0
AHEAD=0
MKT_SHA=""
CO_SHA=""
CO_REF=""
if [ -e "$MKT/.git" ] && command -v git >/dev/null 2>&1 \
   && git -C "$CHECKOUT" rev-parse --git-dir >/dev/null 2>&1; then
    MKT_SHA="$(git -C "$MKT" rev-parse --short HEAD 2>/dev/null || printf '')"
    CO_SHA="$(git -C "$CHECKOUT" rev-parse --short HEAD 2>/dev/null || printf '')"
    CO_REF="$(git -C "$CHECKOUT" rev-parse --abbrev-ref HEAD 2>/dev/null || printf '')"
    if [ -n "$MKT_SHA" ] && [ -n "$CO_SHA" ] \
       && git -C "$CHECKOUT" cat-file -e "${MKT_SHA}^{commit}" 2>/dev/null; then
        BEHIND="$(git -C "$CHECKOUT" rev-list --count "${MKT_SHA}..HEAD" 2>/dev/null || printf '0')"
        AHEAD="$(git -C "$CHECKOUT" rev-list --count "HEAD..${MKT_SHA}" 2>/dev/null || printf '0')"
        COMMIT_STATE="resolved"
    else
        # Unfetched, rebased, or shallow: content parity below is the answer.
        COMMIT_STATE="unresolved"
    fi
fi

# --- 2. Command-file content parity -----------------------------------------
declare -A TOTAL=()
declare -A DIFFER=()
STALE_FILES=()

compare_commands() {  # $1 label, $2 family, $3 src commands dir, $4 installed commands dir
    local label="$1" family="$2" src="$3" dest="$4" f base
    [ -d "$src" ] || return 0
    # A family the user never installed is not drift - it is a choice.
    [ -d "$dest" ] || return 0
    for f in "$src"/*.md; do
        [ -e "$f" ] || continue
        base="${f##*/}"
        TOTAL[$label]=$(( ${TOTAL[$label]:-0} + 1 ))
        if [ ! -f "$dest/$base" ]; then
            DIFFER[$label]=$(( ${DIFFER[$label]:-0} + 1 ))
            STALE_FILES+=("$label|$family/$base|missing from install")
        elif ! cmp -s "$f" "$dest/$base"; then
            DIFFER[$label]=$(( ${DIFFER[$label]:-0} + 1 ))
            STALE_FILES+=("$label|$family/$base|differs")
        fi
    done
    for f in "$dest"/*.md; do
        [ -e "$f" ] || continue
        base="${f##*/}"
        if [ ! -f "$src/$base" ]; then
            DIFFER[$label]=$(( ${DIFFER[$label]:-0} + 1 ))
            STALE_FILES+=("$label|$family/$base|retired upstream, still installed")
        fi
    done
}

# The marketplace clone mirrors the repo layout: plugins/<family>/commands/.
if [ -d "$MKT" ]; then
    for src in "$CHECKOUT"/plugins/*/commands; do
        [ -d "$src" ] || continue
        fam="${src%/commands}"; fam="${fam##*/}"
        compare_commands "marketplace" "$fam" "$src" "$MKT/plugins/$fam/commands"
    done
fi

# The cache is version-stamped and flat: <family>/<version>/commands/. This is
# the copy a session actually executes.
if [ -d "$CACHE" ]; then
    for dest in "$CACHE"/*/*/commands; do
        [ -d "$dest" ] || continue
        p="${dest%/commands}"; p="${p%/*}"; fam="${p##*/}"
        compare_commands "cache" "$fam" "$CHECKOUT/plugins/$fam/commands" "$dest"
    done
fi

CMD_DRIFT=$(( ${DIFFER[marketplace]:-0} + ${DIFFER[cache]:-0} ))

# --- 3. Helper half (the split) ---------------------------------------------
HELPERS_CURRENT=0
HELPERS_STALE=0
STALE_HELPERS=()
if [ -n "$SCRIPTS_DIR" ] && [ -d "$SCRIPTS_DIR" ]; then
    for f in "$SCRIPTS_DIR"/*.sh; do
        # -e is false for a dangling symlink; that is /flow:doctor's report to
        # make, not this one's.
        [ -e "$f" ] || continue
        base="${f##*/}"
        src="$CHECKOUT/scripts/$base"
        [ -f "$src" ] || continue
        if cmp -s "$src" "$f"; then
            HELPERS_CURRENT=$(( HELPERS_CURRENT + 1 ))
        else
            HELPERS_STALE=$(( HELPERS_STALE + 1 ))
            STALE_HELPERS+=("$base")
        fi
    done
fi

# The #622 signature: the helper half current, the markdown half behind. Worth
# naming explicitly, because the symptom (new helpers, old instructions) reads
# as a bug in the helpers rather than as staleness.
SPLIT=0
if [ "$HELPERS_STALE" -eq 0 ] && [ "$HELPERS_CURRENT" -gt 0 ] \
   && { [ "$CMD_DRIFT" -gt 0 ] || [ "$BEHIND" -gt 0 ]; }; then
    SPLIT=1
fi

DRIFT=0
if [ "$CMD_DRIFT" -gt 0 ] || [ "$BEHIND" -gt 0 ] || [ "$HELPERS_STALE" -gt 0 ]; then
    DRIFT=1
fi

# --- Output -----------------------------------------------------------------
summary_clause() {
    local parts=""
    if [ "$COMMIT_STATE" = "resolved" ] && [ "$BEHIND" -gt 0 ]; then
        parts="${BEHIND} commit(s) behind checkout"
    fi
    if [ "$CMD_DRIFT" -gt 0 ]; then
        [ -n "$parts" ] && parts="${parts}, "
        parts="${parts}${CMD_DRIFT} command file(s) stale"
    fi
    if [ "$HELPERS_STALE" -gt 0 ]; then
        [ -n "$parts" ] && parts="${parts}, "
        parts="${parts}${HELPERS_STALE} helper(s) stale"
    elif [ "$SPLIT" -eq 1 ]; then
        parts="${parts} (helpers current)"
    fi
    printf '%s' "$parts"
}

if [ "$MODE" = "quiet" ]; then
    if [ "$DRIFT" -eq 1 ]; then
        echo "CPP install: $(summary_clause) - run /cpp:update"
    fi
    exit 0
fi

if [ "$MODE" = "json" ]; then
    printf '{'
    printf '"verdict":"%s",' "$([ "$DRIFT" -eq 1 ] && echo drift || echo ok)"
    printf '"checkout":"%s",' "$CHECKOUT"
    printf '"checkout_ref":"%s","checkout_sha":"%s",' "$CO_REF" "$CO_SHA"
    printf '"commit_state":"%s","behind":%s,"ahead":%s,' "$COMMIT_STATE" "${BEHIND:-0}" "${AHEAD:-0}"
    printf '"marketplace_sha":"%s",' "$MKT_SHA"
    printf '"commands_total":%s,"commands_stale":%s,' \
        "$(( ${TOTAL[marketplace]:-0} + ${TOTAL[cache]:-0} ))" "$CMD_DRIFT"
    printf '"helpers_current":%s,"helpers_stale":%s,' "$HELPERS_CURRENT" "$HELPERS_STALE"
    printf '"split":%s' "$([ "$SPLIT" -eq 1 ] && echo true || echo false)"
    printf '}\n'
    [ "$DRIFT" -eq 1 ] && exit 1
    exit 0
fi

echo "install-drift: checkout $CHECKOUT${CO_SHA:+ (${CO_REF:-detached} @ $CO_SHA)}"
echo ""
if [ -d "$MKT" ]; then
    echo "  marketplace clone  $MKT"
    case "$COMMIT_STATE" in
        resolved)
            if [ "$BEHIND" -gt 0 ]; then
                echo "    ${MKT_SHA} - ${BEHIND} commit(s) behind the checkout"
            elif [ "$AHEAD" -gt 0 ]; then
                echo "    ${MKT_SHA} - ${AHEAD} commit(s) AHEAD of the checkout (pull the checkout)"
            else
                echo "    ${MKT_SHA} - same commit as the checkout"
            fi ;;
        unresolved)
            echo "    ${MKT_SHA:-unknown} - commit distance unresolvable (not in checkout history); using content parity" ;;
        *)
            echo "    commit distance unavailable (no git); using content parity" ;;
    esac
    echo "    ${DIFFER[marketplace]:-0} of ${TOTAL[marketplace]:-0} command file(s) differ"
fi
if [ -d "$CACHE" ]; then
    echo "  plugin cache       $CACHE"
    echo "    ${DIFFER[cache]:-0} of ${TOTAL[cache]:-0} command file(s) differ (this is the copy sessions execute)"
fi
echo "  host helpers       ${SCRIPTS_DIR:-<none>}"
echo "    ${HELPERS_CURRENT} current, ${HELPERS_STALE} stale"

if [ "${#STALE_FILES[@]}" -gt 0 ]; then
    echo ""
    echo "  Stale command files:"
    shown=0
    for rec in "${STALE_FILES[@]}"; do
        if [ "$LIST_ALL" -eq 0 ] && [ "$shown" -ge "$SAMPLE" ]; then
            echo "    (+ $(( ${#STALE_FILES[@]} - shown )) more - re-run with --list)"
            break
        fi
        IFS='|' read -r lbl path state <<< "$rec"
        echo "    [$lbl] $path - $state"
        shown=$(( shown + 1 ))
    done
fi
if [ "${#STALE_HELPERS[@]}" -gt 0 ]; then
    echo ""
    echo "  Stale helpers: ${STALE_HELPERS[*]}"
fi

echo ""
if [ "$DRIFT" -eq 0 ]; then
    echo "install-drift: install matches the checkout."
    echo "INSTALL_DRIFT: ok"
    exit 0
fi

if [ "$SPLIT" -eq 1 ]; then
    echo "SPLIT INSTALL: the helpers are current but the command markdown is not."
    echo "A session gets new helpers driven by old instructions, and the mismatch is"
    echo "silent in both directions (issue #622)."
    echo ""
fi
echo "Reconcile: /plugin update, or /cpp:update (which also re-links the helpers)."
echo "INSTALL_DRIFT: drift"
exit 1
