#!/usr/bin/env bash
# install-drift.sh - guard installed CPP helpers and report retired marketplace
# state left on a host (issues #622/#662/#823).
#
# Three independent, read-only jobs survive the marketplace retirement:
#   1. Compare installed ~/.claude/scripts/ files with the same basenames under
#      <checkout>/scripts (not .sh-restricted - see the #828 note below). Only
#      basenames the checkout ships are judged; a host's own scripts are none
#      of this check's business. This remains the symlink-era drift guard
#      through issue #663. Extended by issue #828: the
#      loop above only ever asks "of what IS installed, does it match" - a
#      checkout helper with NO installed counterpart at all never enters it,
#      so a fully-absent helper was structurally invisible (this session hit
#      exactly that: delegated-run-check.sh missing, exit 127, found by
#      tripping over it rather than by this detector). "What should be
#      installed" already has a canonical answer - flow-helpers-install.sh's
#      own HELPERS array, documented there as THE STABLE-PATH INSTALL SET -
#      so this reuses it via subprocess (`flow-helpers-install.sh --check`)
#      rather than duplicating it as a second list that must stay in sync
#      forever. `--check` is provably read-only: every path through its check
#      branch exits before its install branch's first write. Only its
#      MISSING lines are read; its STALE verdicts are discarded so this
#      script's own (broader - matches ANY installed name, not just the
#      curated set) stale judgment stays the single source of truth for
#      staleness. A `.sh` under <checkout>/scripts NOT in that array
#      (dev-only, opt-in, or installed by a different mechanism) is never
#      judged missing - the same ownership-boundary shape as job 3's
#      `.system/` exclusion, against a different noise source (36 scripts
#      shipped, 21 in the install set). HELPERS_MISSING_CHECKED distinguishes
#      "flow-helpers-install.sh absent or produced no recognisable output"
#      from "ran and found zero missing" - the same membership-floor shape
#      as job 3, because a subprocess whose output format silently changed
#      must never read as a clean scan either. One more asymmetry the same
#      review found and closed in the same PR: the stale/current loop was
#      still *.sh-globbed, so flow-wave-plan.py - the array's one non-.sh
#      entry, and the exact file a 20-vs-21 membership-count reconcile
#      surfaced - could be checked for absence but never for content. The
#      glob widened to `*` (filtered to regular files only, `-f`) so every
#      HELPERS-array entry gets both properties judged, not just one.
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
# Combined verdicts give any judged drift priority: a stale or missing
# helper, or a stale Codex skill package, makes the whole result `drift`,
# even when retired
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
            sed -n '2,93p' "$SELF" | sed 's/^# \{0,1\}//'
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
# Glob widened from *.sh to * (issue #828 review): flow-helpers-install.sh's
# own HELPERS array - the canonical install set the MISSING check below
# already judges in full - has exactly one non-.sh entry, flow-wave-plan.py.
# A *.sh-only glob could detect that file's ABSENCE (via the MISSING check)
# but never its CONTENT drifting once installed - the same membership defect
# one column over, and it landed on the exact file the missing-check's own
# 20-vs-21 count reconcile had just surfaced. -f (not -e) both excludes a
# dangling symlink, as the original *.sh-only loop already relied on, and
# now also excludes a directory, which the widened glob can otherwise match.
HELPERS_CURRENT=0
HELPERS_STALE=0
STALE_HELPERS=()
if [ -n "$SCRIPTS_DIR" ] && [ -d "$SCRIPTS_DIR" ]; then
    for installed in "$SCRIPTS_DIR"/*; do
        [ -f "$installed" ] || continue
        base="${installed##*/}"
        source_helper="$CHECKOUT/scripts/$base"
        # A file the host owns is none of this check's business. Judge only
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

# --- Installed helper MISSING detection (#828) ------------------------------
# See the extended job-1 header comment above for the full rationale. Shells
# out to flow-helpers-install.sh --check (read-only - see its own header) and
# keeps only its MISSING lines.
FLOW_HELPERS_INSTALLER="$CHECKOUT/scripts/flow-helpers-install.sh"
HELPERS_MISSING_CHECKED=0
HELPERS_MISSING_UNAVAILABLE_REASON=""
MISSING_HELPERS=()
if [ -f "$FLOW_HELPERS_INSTALLER" ]; then
    flow_helpers_check_output="$(FLOW_HELPERS_HOME="$HOME_DIR" FLOW_HELPERS_SOURCE="$CHECKOUT/scripts" \
        bash "$FLOW_HELPERS_INSTALLER" --check 2>/dev/null)"
    judged_lines=0
    while IFS= read -r line; do
        case "$line" in
            "OK "*|"STALE "*)
                judged_lines=$(( judged_lines + 1 ))
                ;;
            "MISSING "*)
                judged_lines=$(( judged_lines + 1 ))
                name="${line#MISSING }"
                name="${name%% *}"
                MISSING_HELPERS+=("$name")
                ;;
        esac
    done <<< "$flow_helpers_check_output"
    # A subprocess that runs but produces no recognisable OK/STALE/MISSING
    # line (format change, empty output, stderr/stdout drift) must never
    # read as "ran, found 0 missing" - that is "ran and parsed nothing", a
    # different answer (issue #828 review).
    if [ "$judged_lines" -gt 0 ]; then
        HELPERS_MISSING_CHECKED=1
    else
        HELPERS_MISSING_UNAVAILABLE_REASON="flow-helpers-install.sh --check produced no recognisable output"
    fi
else
    HELPERS_MISSING_UNAVAILABLE_REASON="flow-helpers-install.sh not found in checkout"
fi
HELPERS_MISSING=${#MISSING_HELPERS[@]}

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

if [ "$RETIRED" -eq 0 ] && [ "$HELPERS_TOTAL" -eq 0 ] && [ "$HELPERS_MISSING" -eq 0 ] && [ "$CODEX_SKILLS_CHECKED" -eq 0 ]; then
    emit_skip "no retired CPP marketplace surface, installed checkout helpers, or installed Codex skills found"
fi

SPLIT=0
if [ "$RETIRED" -eq 1 ] && [ "$HELPERS_CURRENT" -gt 0 ] && [ "$HELPERS_STALE" -eq 0 ] && [ "$HELPERS_MISSING" -eq 0 ]; then
    SPLIT=1
fi

VERDICT="ok"
if [ "$HELPERS_STALE" -gt 0 ] || [ "$HELPERS_MISSING" -gt 0 ] || [ "$CODEX_SKILLS_STALE" -gt 0 ]; then
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
    if [ "$HELPERS_MISSING" -gt 0 ]; then
        clauses+=("${HELPERS_MISSING} helper(s) missing - run /cpp:update")
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
    printf '],"helpers_missing":%s,"helpers_missing_checked":%s,"missing_helpers":[' \
        "$HELPERS_MISSING" "$([ "$HELPERS_MISSING_CHECKED" -eq 1 ] && echo true || echo false)"
    separator=""
    for helper in "${MISSING_HELPERS[@]}"; do
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
echo "    ${HELPERS_CURRENT} current, ${HELPERS_STALE} stale, ${HELPERS_MISSING} missing"
if [ "${#STALE_HELPERS[@]}" -gt 0 ]; then
    echo ""
    echo "  Stale helpers: ${STALE_HELPERS[*]}"
fi
if [ "${#MISSING_HELPERS[@]}" -gt 0 ]; then
    echo ""
    echo "  Missing helpers: ${MISSING_HELPERS[*]}"
fi
if [ "$HELPERS_MISSING_CHECKED" -eq 0 ]; then
    echo ""
    echo "  (missing-helper check unavailable: $HELPERS_MISSING_UNAVAILABLE_REASON)"
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
        if [ "$HELPERS_STALE" -gt 0 ] || [ "$HELPERS_MISSING" -gt 0 ]; then
            echo "Reconcile stale or missing helpers with /cpp:update."
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
