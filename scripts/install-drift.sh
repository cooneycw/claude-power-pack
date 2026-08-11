#!/usr/bin/env bash
# install-drift.sh - guard installed CPP helpers and report retired marketplace
# state left on a host (issues #622/#662).
#
# Two independent, read-only jobs survive the marketplace retirement:
#   1. Compare installed ~/.claude/scripts/*.sh helpers with the same basenames
#      under <checkout>/scripts. Only basenames the checkout ships are judged; a
#      host's own scripts are none of this check's business. This remains the
#      symlink-era drift guard through issue #663.
#   2. Name CPP cache families and the marketplace clone retired by issue #662 /
#      ADR 0005 so the operator can migrate them with
#      `/plugin uninstall <family>@cpp`.
#
# Combined verdicts give helper drift priority: any stale judged helper is
# `drift`, even when retired marketplace state also exists. Retired state alone
# remains informational `skipped`; comparable current helpers with no retired
# state are `ok`. No checkout, or no retired state and no comparable installed
# helpers, is also `skipped`. A current helper half beside retired marketplace
# state is named as a SPLIT INSTALL, but the retired half is not content-judged.
# Successful checks always exit 0, including a `drift` verdict; only bad usage or
# an invalid explicit checkout override exits 2.
#
# Usage:
#   install-drift.sh                # human report; always exit 0
#   install-drift.sh --list         # accepted for backward compatibility
#   install-drift.sh --quiet        # one advisory line when action is needed
#   install-drift.sh --json         # machine-readable; always exit 0
#
# Output in report mode ends with:
#   INSTALL_DRIFT: ok | drift | skipped | error
#
# Env (test seams - unset in normal use):
#   CPP_INSTALL_DRIFT_HOME      override $HOME (plugin + helper roots)
#   CPP_INSTALL_DRIFT_CHECKOUT  override checkout detection

set -uo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SELF_DIR="$(cd "$(dirname "$SELF")" && pwd)"
HOME_DIR="${CPP_INSTALL_DRIFT_HOME:-${HOME:-}}"

MODE="report"
for arg in "$@"; do
    case "$arg" in
        --check|--report|--list) MODE="report" ;;
        --quiet) MODE="quiet" ;;
        --json) MODE="json" ;;
        -h|--help)
            sed -n '2,34p' "$SELF" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            echo "install-drift: unknown argument '$arg' (use --quiet, --json, --list)" >&2
            exit 2 ;;
    esac
done

is_checkout() {
    [ -n "$1" ] && [ -f "$1/CLAUDE.md" ] && [ -d "$1/.claude/commands" ]
}

CHECKOUT=""
if [ -n "${CPP_INSTALL_DRIFT_CHECKOUT:-}" ]; then
    if is_checkout "$CPP_INSTALL_DRIFT_CHECKOUT"; then
        CHECKOUT="$CPP_INSTALL_DRIFT_CHECKOUT"
    else
        echo "install-drift: CPP_INSTALL_DRIFT_CHECKOUT is not a CPP checkout: $CPP_INSTALL_DRIFT_CHECKOUT" >&2
        echo "INSTALL_DRIFT: error"
        exit 2
    fi
else
    # Self-location first: a helper symlink resolves back to <checkout>/scripts.
    for dir in "$SELF_DIR/.." "${HOME_DIR:+$HOME_DIR/Projects/claude-power-pack}" \
               /opt/claude-power-pack "${HOME_DIR:+$HOME_DIR/.claude-power-pack}"; do
        [ -n "$dir" ] || continue
        if is_checkout "$dir"; then
            CHECKOUT="$(cd "$dir" && pwd)"
            break
        fi
    done
fi

emit_skip() {
    local reason="$1"
    case "$MODE" in
        quiet) : ;;
        json) printf '{"verdict":"skipped","reason":"%s"}\n' "$reason" ;;
        *)
            echo "install-drift: $reason"
            echo "INSTALL_DRIFT: skipped" ;;
    esac
    exit 0
}

[ -n "$CHECKOUT" ] || emit_skip "no CPP checkout found - nothing to inspect"

PLUGINS_DIR="${HOME_DIR:+$HOME_DIR/.claude/plugins}"
MKT="${PLUGINS_DIR:+$PLUGINS_DIR/marketplaces/cpp}"
CACHE="${PLUGINS_DIR:+$PLUGINS_DIR/cache/cpp}"
SCRIPTS_DIR="${HOME_DIR:+$HOME_DIR/.claude/scripts}"

# --- Retired marketplace migration state (#662) ----------------------------
FAMILIES=()
if [ -d "$CACHE" ]; then
    for family_dir in "$CACHE"/*; do
        [ -d "$family_dir" ] || continue
        FAMILIES+=("${family_dir##*/}")
    done
fi

RETIRED=0
if [ "${#FAMILIES[@]}" -gt 0 ] || [ -d "$MKT" ]; then
    RETIRED=1
fi

family_csv=""
if [ "${#FAMILIES[@]}" -gt 0 ]; then
    family_csv="$(IFS=,; printf '%s' "${FAMILIES[*]}")"
fi

# --- Installed helper parity (#622, retained through #663) -----------------
HELPERS_CURRENT=0
HELPERS_STALE=0
STALE_HELPERS=()
if [ -n "$SCRIPTS_DIR" ] && [ -d "$SCRIPTS_DIR" ]; then
    for installed in "$SCRIPTS_DIR"/*.sh; do
        # -e is false for a dangling symlink; that is /flow:doctor's report to
        # make, not this one's.
        [ -e "$installed" ] || continue
        base="${installed##*/}"
        source_helper="$CHECKOUT/scripts/$base"
        # A script the host owns is none of this check's business. Judge only
        # installed basenames that exist in the checkout.
        [ -f "$source_helper" ] || continue
        if cmp -s "$source_helper" "$installed"; then
            HELPERS_CURRENT=$(( HELPERS_CURRENT + 1 ))
        else
            HELPERS_STALE=$(( HELPERS_STALE + 1 ))
            STALE_HELPERS+=("$base")
        fi
    done
fi
HELPERS_TOTAL=$(( HELPERS_CURRENT + HELPERS_STALE ))

if [ "$RETIRED" -eq 0 ] && [ "$HELPERS_TOTAL" -eq 0 ]; then
    emit_skip "no retired CPP marketplace surface or installed checkout helpers found"
fi

SPLIT=0
if [ "$RETIRED" -eq 1 ] && [ "$HELPERS_CURRENT" -gt 0 ] && [ "$HELPERS_STALE" -eq 0 ]; then
    SPLIT=1
fi

VERDICT="ok"
if [ "$HELPERS_STALE" -gt 0 ]; then
    VERDICT="drift"
elif [ "$RETIRED" -eq 1 ]; then
    VERDICT="skipped"
fi

# --- Output ----------------------------------------------------------------
retired_quiet_clause() {
    if [ -n "$family_csv" ]; then
        printf 'retired marketplace surface pending uninstall (#662/#663): %s' "$family_csv"
    else
        printf 'retired marketplace clone pending removal (#662/#663)'
    fi
}

if [ "$MODE" = "quiet" ]; then
    if [ "$HELPERS_STALE" -gt 0 ]; then
        message="CPP install: ${HELPERS_STALE} helper(s) stale - run /cpp:update"
        if [ "$RETIRED" -eq 1 ]; then
            message="${message}; $(retired_quiet_clause)"
        fi
        echo "$message"
    elif [ "$RETIRED" -eq 1 ]; then
        echo "CPP install: $(retired_quiet_clause)"
    fi
    exit 0
fi

if [ "$MODE" = "json" ]; then
    printf '{"verdict":"%s",' "$VERDICT"
    if [ "$VERDICT" = "skipped" ]; then
        printf '"reason":"retired marketplace surface",'
    fi
    printf '"checkout":"%s","marketplace_clone":%s,"cache_families":[' \
        "$CHECKOUT" "$([ -d "$MKT" ] && echo true || echo false)"
    separator=""
    for family in "${FAMILIES[@]}"; do
        printf '%s"%s"' "$separator" "$family"
        separator=,
    done
    printf '],"helpers_current":%s,"helpers_stale":%s,"stale_helpers":[' \
        "$HELPERS_CURRENT" "$HELPERS_STALE"
    separator=""
    for helper in "${STALE_HELPERS[@]}"; do
        printf '%s"%s"' "$separator" "$helper"
        separator=,
    done
    printf '],"split":%s}\n' "$([ "$SPLIT" -eq 1 ] && echo true || echo false)"
    exit 0
fi

echo "install-drift: checkout $CHECKOUT"
echo "  host helpers       ${SCRIPTS_DIR:-<none>}"
echo "    ${HELPERS_CURRENT} current, ${HELPERS_STALE} stale"
if [ "${#STALE_HELPERS[@]}" -gt 0 ]; then
    echo ""
    echo "  Stale helpers: ${STALE_HELPERS[*]}"
fi

if [ "$RETIRED" -eq 1 ]; then
    echo ""
    echo "install-drift: retired CPP marketplace surface detected (issue #662)"
    if [ -d "$MKT" ]; then
        echo "  marketplace clone  $MKT (retired)"
    fi
    if [ "${#FAMILIES[@]}" -gt 0 ]; then
        echo "  plugin cache       $CACHE (retired)"
        echo "  installed families ${FAMILIES[*]}"
        echo ""
        echo "Migration: uninstall each cached family; for example:"
        for family in "${FAMILIES[@]}"; do
            echo "  /plugin uninstall ${family}@cpp"
        done
    fi
    echo "The tiered symlink command surface returns as canonical in issue #663."
fi

echo ""
if [ "$SPLIT" -eq 1 ]; then
    echo "SPLIT INSTALL: helpers match the checkout, but retired marketplace state remains."
    echo "The helper and command halves came from independent install lanes (issue #622)."
    echo ""
fi

case "$VERDICT" in
    drift)
        echo "Reconcile stale helpers with /cpp:update."
        echo "INSTALL_DRIFT: drift" ;;
    ok)
        echo "install-drift: installed helpers match the checkout."
        echo "INSTALL_DRIFT: ok" ;;
    skipped)
        echo "INSTALL_DRIFT: skipped" ;;
esac
exit 0
