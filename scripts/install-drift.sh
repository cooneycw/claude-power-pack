#!/usr/bin/env bash
# install-drift.sh - guard installed CPP helpers and report retired marketplace
# state left on a host (issues #622/#662/#823).
#
# Three independent, read-only jobs survive the marketplace retirement:
#   1. Compare installed ~/.claude/scripts/*.sh helpers with the same basenames
#      under <checkout>/scripts. Only basenames the checkout ships are judged; a
#      host's own scripts are none of this check's business. This remains the
#      symlink-era drift guard through issue #663.
#   2. Name CPP cache families and the marketplace clone retired by issue #662 /
#      ADR 0005 so the operator can migrate them with
#      `/plugin uninstall <family>@cpp`.
#   3. Compare installed ~/.codex/skills/<pkg>/ packages against the same
#      packages under <checkout>/codex/skills/ (issue #823). Unlike jobs 1-2,
#      this tree is a COPY made by `codex-skill-sync.py --install`, not a
#      symlink - `git pull` cannot refresh it, and nothing else did either:
#      "the fix is live" is a claim about consumers, but a scan can only ever
#      be a claim about paths, and this is the channel that gap left blind for
#      three weeks. Two properties this comparison must hold:
#        - MEMBERSHIP FLOOR: an absent or empty install tree reports as
#          nothing-checked, never as clean - see CODEX_SKILLS_CHECKED below.
#        - OWNERSHIP BOUNDARY: only packages this checkout ships, or once
#          shipped, are judged. A package with no counterpart under
#          <checkout>/codex/skills/ is judged ONLY if its installed SKILL.md
#          still carries the GENERATED marker `is_managed_codex_skill()`
#          checks for - that is what separates an ORPHAN of ours (a package
#          we used to ship, deleted from the repo, never pruned from the
#          install tree - itself a drift issue #622 describes) from something
#          genuinely none of this check's business, chiefly Codex CLI's own
#          built-ins under ~/.codex/skills/.system/ (skill-installer,
#          plugin-creator, openai-docs, skill-creator, imagegen,
#          review-agent). The leading-dot skip on `.system/` below is
#          belt-and-braces only, not the real boundary: those names simply
#          have no repo counterpart and carry no GENERATED marker, so the
#          rule above already leaves them untouched even without it.
#
# Combined verdicts give any judged drift priority: a stale helper or a stale
# Codex skill package makes the whole result `drift`, even when retired
# marketplace state or orphaned-but-current Codex skills also exist. Orphaned
# Codex skills are reported but not content-judged (there is nothing installed
# to compare against) and, like retired marketplace state, read as
# informational `skipped` rather than `drift` - the remedy is a prune, not a
# re-install, and folding it into `drift` would point at the wrong fix.
# Comparable current helpers and Codex skills with no retired state and no
# orphans are `ok`. No checkout, or nothing installed/retired of any of the
# three kinds, is also `skipped`. A current helper half beside retired
# marketplace state is named as a SPLIT INSTALL, but the retired half is not
# content-judged. Successful checks always exit 0, including a `drift`
# verdict; only bad usage or an invalid explicit checkout override exits 2.
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
#   CPP_INSTALL_DRIFT_HOME      override $HOME (plugin + helper + Codex-skill roots)
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
            sed -n '2,62p' "$SELF" | sed 's/^# \{0,1\}//'
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

# --- Installed Codex skill parity (#823) ------------------------------------
# A skill dir is OURS (managed by codex-skill-sync.py) when its SKILL.md
# carries the GENERATED marker as the first non-blank line after any YAML
# frontmatter - mirrors codex-skill-sync.py's own is_managed() exactly, so a
# hand-curated or Codex-installed skill never misreports as an orphan of ours.
CODEX_SYNC_MARKER='<!-- GENERATED by claude-power-pack - scripts/codex-skill-sync.py;'
is_managed_codex_skill() {
    local skill_md="$1/SKILL.md"
    [ -f "$skill_md" ] || return 1
    awk -v marker="$CODEX_SYNC_MARKER" '
        NR == 1 && $0 == "---" { in_fm = 1; next }
        in_fm == 1 { if ($0 == "---") in_fm = 0; next }
        $0 == "" { next }
        { print (index($0, marker) == 1) ? "yes" : "no"; exit }
    ' "$skill_md" | grep -q '^yes$'
}

CODEX_SKILLS_DIR="${HOME_DIR:+$HOME_DIR/.codex/skills}"
CODEX_SKILLS_SOURCE="$CHECKOUT/codex/skills"
CODEX_SKILLS_CURRENT=0
CODEX_SKILLS_STALE=0
CODEX_SKILLS_ORPHANED=0
STALE_CODEX_SKILLS=()
ORPHANED_CODEX_SKILLS=()
if [ -n "$CODEX_SKILLS_DIR" ] && [ -d "$CODEX_SKILLS_DIR" ]; then
    for installed in "$CODEX_SKILLS_DIR"/*/; do
        [ -d "$installed" ] || continue
        name="$(basename "$installed")"
        # Belt-and-braces, not the boundary itself - see the header comment.
        case "$name" in
            .*) continue ;;
        esac
        source_pkg="$CODEX_SKILLS_SOURCE/$name"
        if [ ! -f "$source_pkg/SKILL.md" ]; then
            # No repo counterpart. Judge it only if it is still marked as
            # ours: a package this checkout used to ship, deleted from
            # codex/skills/, but never pruned from the install tree is an
            # orphan (#622-shaped drift on its own), not a host's business.
            if is_managed_codex_skill "$installed"; then
                CODEX_SKILLS_ORPHANED=$(( CODEX_SKILLS_ORPHANED + 1 ))
                ORPHANED_CODEX_SKILLS+=("$name")
            fi
            continue
        fi
        if diff -rq -- "$source_pkg" "$installed" >/dev/null 2>&1; then
            CODEX_SKILLS_CURRENT=$(( CODEX_SKILLS_CURRENT + 1 ))
        else
            CODEX_SKILLS_STALE=$(( CODEX_SKILLS_STALE + 1 ))
            STALE_CODEX_SKILLS+=("$name")
        fi
    done
fi
CODEX_SKILLS_TOTAL=$(( CODEX_SKILLS_CURRENT + CODEX_SKILLS_STALE ))
# Membership floor (#823): "checked" means we found ANY CPP-owned Codex-skill
# content installed - current, stale, or orphaned. An absent or empty install
# tree leaves this 0, and 0 must never be read as "checked, clean" downstream.
CODEX_SKILLS_CHECKED=0
if [ "$CODEX_SKILLS_TOTAL" -gt 0 ] || [ "$CODEX_SKILLS_ORPHANED" -gt 0 ]; then
    CODEX_SKILLS_CHECKED=1
fi

if [ "$RETIRED" -eq 0 ] && [ "$HELPERS_TOTAL" -eq 0 ] && [ "$CODEX_SKILLS_CHECKED" -eq 0 ]; then
    emit_skip "no retired CPP marketplace surface, installed checkout helpers, or installed Codex skills found"
fi

SPLIT=0
if [ "$RETIRED" -eq 1 ] && [ "$HELPERS_CURRENT" -gt 0 ] && [ "$HELPERS_STALE" -eq 0 ]; then
    SPLIT=1
fi

VERDICT="ok"
if [ "$HELPERS_STALE" -gt 0 ] || [ "$CODEX_SKILLS_STALE" -gt 0 ]; then
    VERDICT="drift"
elif [ "$RETIRED" -eq 1 ] || [ "$CODEX_SKILLS_ORPHANED" -gt 0 ]; then
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

skipped_reason() {
    if [ "$RETIRED" -eq 1 ] && [ "$CODEX_SKILLS_ORPHANED" -gt 0 ]; then
        printf 'retired marketplace surface and orphaned Codex skills'
    elif [ "$CODEX_SKILLS_ORPHANED" -gt 0 ]; then
        printf 'orphaned Codex skills'
    else
        printf 'retired marketplace surface'
    fi
}

if [ "$MODE" = "quiet" ]; then
    clauses=()
    if [ "$HELPERS_STALE" -gt 0 ]; then
        clauses+=("${HELPERS_STALE} helper(s) stale - run /cpp:update")
    fi
    if [ "$CODEX_SKILLS_STALE" -gt 0 ]; then
        clauses+=("${CODEX_SKILLS_STALE} Codex skill(s) stale - run codex-skill-sync.py --install")
    fi
    if [ "$CODEX_SKILLS_ORPHANED" -gt 0 ]; then
        clauses+=("${CODEX_SKILLS_ORPHANED} Codex skill(s) orphaned (no longer shipped)")
    fi
    if [ "$RETIRED" -eq 1 ]; then
        clauses+=("$(retired_quiet_clause)")
    fi
    if [ "${#clauses[@]}" -gt 0 ]; then
        joined="${clauses[0]}"
        for clause in "${clauses[@]:1}"; do
            joined="${joined}; ${clause}"
        done
        echo "CPP install: ${joined}"
    fi
    exit 0
fi

if [ "$MODE" = "json" ]; then
    printf '{"verdict":"%s",' "$VERDICT"
    if [ "$VERDICT" = "skipped" ]; then
        printf '"reason":"%s",' "$(skipped_reason)"
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
    printf '],"split":%s,"codex_skills_checked":%s,"codex_skills_current":%s,' \
        "$([ "$SPLIT" -eq 1 ] && echo true || echo false)" \
        "$([ "$CODEX_SKILLS_CHECKED" -eq 1 ] && echo true || echo false)" \
        "$CODEX_SKILLS_CURRENT"
    printf '"codex_skills_stale":%s,"stale_codex_skills":[' "$CODEX_SKILLS_STALE"
    separator=""
    for skill in "${STALE_CODEX_SKILLS[@]}"; do
        printf '%s"%s"' "$separator" "$skill"
        separator=,
    done
    printf '],"codex_skills_orphaned":%s,"orphaned_codex_skills":[' "$CODEX_SKILLS_ORPHANED"
    separator=""
    for skill in "${ORPHANED_CODEX_SKILLS[@]}"; do
        printf '%s"%s"' "$separator" "$skill"
        separator=,
    done
    printf ']}\n'
    exit 0
fi

echo "install-drift: checkout $CHECKOUT"
echo "  host helpers       ${SCRIPTS_DIR:-<none>}"
echo "    ${HELPERS_CURRENT} current, ${HELPERS_STALE} stale"
if [ "${#STALE_HELPERS[@]}" -gt 0 ]; then
    echo ""
    echo "  Stale helpers: ${STALE_HELPERS[*]}"
fi

echo ""
echo "  codex skills       ${CODEX_SKILLS_DIR:-<none>}"
if [ "$CODEX_SKILLS_CHECKED" -eq 1 ]; then
    echo "    ${CODEX_SKILLS_CURRENT} current, ${CODEX_SKILLS_STALE} stale, ${CODEX_SKILLS_ORPHANED} orphaned"
else
    echo "    not installed or empty - nothing to check (issue #823)"
fi
if [ "${#STALE_CODEX_SKILLS[@]}" -gt 0 ]; then
    echo ""
    echo "  Stale Codex skills: ${STALE_CODEX_SKILLS[*]}"
fi
if [ "${#ORPHANED_CODEX_SKILLS[@]}" -gt 0 ]; then
    echo ""
    echo "  Orphaned Codex skills (ours, no longer shipped - review before pruning):"
    echo "    ${ORPHANED_CODEX_SKILLS[*]}"
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
        if [ "$HELPERS_STALE" -gt 0 ]; then
            echo "Reconcile stale helpers with /cpp:update."
        fi
        if [ "$CODEX_SKILLS_STALE" -gt 0 ]; then
            echo "Reconcile stale Codex skills with codex-skill-sync.py --install."
        fi
        echo "INSTALL_DRIFT: drift" ;;
    ok)
        echo "install-drift: installed helpers and Codex skills match the checkout."
        echo "INSTALL_DRIFT: ok" ;;
    skipped)
        echo "INSTALL_DRIFT: skipped" ;;
esac
exit 0
