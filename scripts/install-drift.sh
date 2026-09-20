#!/usr/bin/env bash
#: HOST-SURFACE: none
#  read-only reporter. Compares ~/.claude/{plugins,scripts,skills}, ~/.codex/skills and ~/.claude-power-pack
#  against the checkout and reports; no cp, ln, mkdir, tee or rm is executed.

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
#   4. Compare installed ~/.claude/skills/<pkg>/ packages against their
#      canonical sources in <checkout>/.claude/skills/ (issue #1029, specimen
#      5). The asymmetry was the tell: job 3 already implemented exactly the
#      right comparison for one install root and was simply not pointed at the
#      other. That root is USER-SCOPE - its packages load in EVERY project, not
#      only this one - it holds real directories rather than symlinks into a
#      checkout, and `~/.claude` is not a git repository, so there was no diff,
#      no history and no manifest for them anywhere on the host.
#
#      OWNERSHIP IS BY MARKER, AND THE NAME IS NOT THE MARKER. `~/.claude/skills/boot`
#      on the reference host is a DIFFERENT project's skill that collides by
#      name with CPP's `.claude/skills/boot`; a name-keyed comparison would
#      report it stale forever and teach everyone to ignore the job. A package
#      is ours only when its frontmatter carries a `metadata.source` linking back
#      to `claude-power-pack/.claude/skills`, and the canonical package is
#      resolved FROM THAT MARKER rather than from the directory name - so a
#      package installed under a different name still compares against the
#      source it declares.
#
#      This job DELEGATES to `skills-check.py --root <checkout> --managed-root
#      <install root>`, which already owns that rule and the comparison it
#      implies (SKILL.md normalized to drop the install-only `metadata.source`
#      key, plus every supporting file). A second, weaker comparison written in
#      bash here would be a different instrument answering the same question,
#      and the two would drift. Only its MANAGED_* lines are read.
#
#      MEMBERSHIP FLOOR, as everywhere else: the subprocess must emit one of its
#      recognisable managed-install notes. Absent, unparseable, or a changed
#      output format reads as `unavailable` - never as "ran, found nothing".
#
#   5. Report the checkout's own PROVENANCE as a number (issue #1029, specimen
#      1) by calling `toolchain-provenance.sh`. Every job above compares an
#      installed copy against THE CHECKOUT, which silently assumes the checkout
#      is itself current - and on 2026-09-15 it was 21 commits behind
#      `origin/main` while every session ran its instruments from it. A helper
#      that byte-matches a stale checkout is `current` by this script's own
#      measure and stale by the only measure that matters. This is ADVISORY and
#      changes no verdict: being behind is not install drift, it is a different
#      fact that install drift cannot be read without.
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

# Exit status on stderr, last thing written, so it survives `| tail` (issue #1031).
trap 'printf "INSTALL_DRIFT_EXIT=%d\n" "$?" >&2' EXIT

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

# --- Installed Claude skill parity (#1029, specimen 5) ----------------------
# See the job-4 header comment for why this delegates rather than re-implements,
# and why the directory NAME is never the ownership test.
CLAUDE_SKILLS_DIR="${HOME_DIR:+$HOME_DIR/.claude/skills}"
CLAUDE_SKILLS_CHECKED=0
CLAUDE_SKILLS_MANAGED=0
CLAUDE_SKILLS_CLEAN=0
# Packages present in the install root that skills-check did NOT examine, because
# they carry no CPP `metadata.source` marker (issue #1034). They are deliberately
# never judged - ownership is by marker - but leaving them uncounted made a run
# that compared nothing print the same line as one that compared everything.
CLAUDE_SKILLS_SKIPPED="?"
CLAUDE_SKILLS_STALE=0
CLAUDE_SKILLS_UNAVAILABLE_REASON=""
STALE_CLAUDE_SKILLS=()
SKILLS_CHECKER="$CHECKOUT/scripts/skills-check.py"
if [ -z "$CLAUDE_SKILLS_DIR" ] || [ ! -d "$CLAUDE_SKILLS_DIR" ]; then
    CLAUDE_SKILLS_UNAVAILABLE_REASON="no install root at ${CLAUDE_SKILLS_DIR:-<unset>}"
elif [ ! -f "$SKILLS_CHECKER" ]; then
    CLAUDE_SKILLS_UNAVAILABLE_REASON="skills-check.py not found in checkout"
elif ! command -v python3 >/dev/null 2>&1; then
    CLAUDE_SKILLS_UNAVAILABLE_REASON="python3 not available to run skills-check.py"
else
    # Findings go to stderr and notes to stdout, so both are captured. Only
    # MANAGED_* findings and the managed-install notes are read: this job asks
    # about the INSTALL tree, and the checker's canonical-surface findings are a
    # different question that `make skills-check` owns.
    skills_output="$(python3 "$SKILLS_CHECKER" --root "$CHECKOUT" --managed-root "$CLAUDE_SKILLS_DIR" 2>&1)"
    while IFS= read -r line; do
        case "$line" in
            *"managed installs: no CPP-marked packages"*)
                CLAUDE_SKILLS_CHECKED=1
                skipped="${line#*, skipped }"
                CLAUDE_SKILLS_SKIPPED="${skipped%% *}" ;;
            *"managed installs: checked "*)
                CLAUDE_SKILLS_CHECKED=1
                counts="${line#*managed installs: checked }"
                CLAUDE_SKILLS_MANAGED="${counts%% *}"
                CLAUDE_SKILLS_CLEAN="${counts#*package(s), }"
                CLAUDE_SKILLS_CLEAN="${CLAUDE_SKILLS_CLEAN%% *}"
                skipped="${line#*, skipped }"
                CLAUDE_SKILLS_SKIPPED="${skipped%% *}" ;;
            *MANAGED_DRIFT:*|*MANAGED_ORPHAN:*)
                # `  MANAGED_DRIFT: <path>/SKILL.md: <detail>` -> the package dir.
                pkg="${line#*: }"
                pkg="${pkg%%:*}"
                pkg="${pkg%/SKILL.md}"
                STALE_CLAUDE_SKILLS+=("${pkg##*/}") ;;
        esac
    done <<< "$skills_output"
    CLAUDE_SKILLS_STALE=${#STALE_CLAUDE_SKILLS[@]}
    case "$CLAUDE_SKILLS_MANAGED$CLAUDE_SKILLS_CLEAN" in
        *[!0-9]*) CLAUDE_SKILLS_MANAGED=0; CLAUDE_SKILLS_CLEAN=0 ;;
    esac
    # A chop that found no ", skipped " anchor leaves the whole line here, which
    # must not be printed as a count. An older checker emitting the pre-#1034
    # note lands in exactly that state, so it reports `?`, never a fabricated 0.
    case "$CLAUDE_SKILLS_SKIPPED" in
        ""|*[!0-9]*) CLAUDE_SKILLS_SKIPPED="?" ;;
    esac
    if [ "$CLAUDE_SKILLS_CHECKED" -eq 0 ]; then
        CLAUDE_SKILLS_UNAVAILABLE_REASON="skills-check.py produced no recognisable managed-install note"
    fi
fi

# AN UNANSWERED QUESTION KEEPS THE REPORT ALIVE. The terse global skip says "no
# installed ... Claude skills found", which is a CLAIM - and it is one this
# script has no right to make when the install root exists and it could not look
# inside it. "There is no root" and "there is a root and the checker was absent"
# are different answers, and only the first of them is a finding of absence.
CLAUDE_SKILLS_UNANSWERED=0
if [ -n "$CLAUDE_SKILLS_DIR" ] && [ -d "$CLAUDE_SKILLS_DIR" ] && [ "$CLAUDE_SKILLS_CHECKED" -eq 0 ]; then
    CLAUDE_SKILLS_UNANSWERED=1
fi

# --- Checkout provenance (#1029, specimen 1) --------------------------------
# Advisory. Every comparison above is against THIS checkout, so how current the
# checkout itself is, is the premise all of them rest on and none of them state.
TOOLCHAIN_HELPER="$CHECKOUT/scripts/toolchain-provenance.sh"
TOOLCHAIN_VERDICT="unavailable"
TOOLCHAIN_BEHIND="-"
TOOLCHAIN_UPSTREAM="-"
TOOLCHAIN_AGE="-"
TOOLCHAIN_AGE_SOURCE="-"
TOOLCHAIN_LINE=""
if [ -x "$TOOLCHAIN_HELPER" ]; then
    # ONE invocation, every value from the SAME output. Separate runs could
    # disagree if a concurrent fetch moved the ref between them, and numbers that
    # cannot have been measured together are not one observation.
    #
    # The KEY=value contract, NOT the JSON. Pulling these back out of JSON with
    # a regex truncated any value containing an escaped quote - a branch named
    # `fea"ture` yielded `origin/fea\` - and install-drift then re-emitted that
    # fragment into its OWN JSON, making the whole response unparseable while
    # exiting 0 (counter-model review pass 2).
    TOOLCHAIN_REPORT="$("$TOOLCHAIN_HELPER" --path "$CHECKOUT" 2>/dev/null)"
    if [ -n "$TOOLCHAIN_REPORT" ]; then
        TOOLCHAIN_VERDICT="$(printf '%s\n' "$TOOLCHAIN_REPORT" | sed -n 's/^TOOLCHAIN_PROVENANCE: //p' | tail -1)"
        TOOLCHAIN_BEHIND="$(printf '%s\n' "$TOOLCHAIN_REPORT" | sed -n 's/^TOOLCHAIN_BEHIND=//p' | tail -1)"
        TOOLCHAIN_UPSTREAM="$(printf '%s\n' "$TOOLCHAIN_REPORT" | sed -n 's/^TOOLCHAIN_UPSTREAM=//p' | tail -1)"
        TOOLCHAIN_AGE="$(printf '%s\n' "$TOOLCHAIN_REPORT" | sed -n 's/^TOOLCHAIN_FETCH_AGE=//p' | tail -1)"
        TOOLCHAIN_AGE_SOURCE="$(printf '%s\n' "$TOOLCHAIN_REPORT" | sed -n 's/^TOOLCHAIN_FETCH_AGE_SOURCE=//p' | tail -1)"
        [ -n "$TOOLCHAIN_VERDICT" ] || TOOLCHAIN_VERDICT="unavailable"
        # `-` is the helper's honest "not measured"; it must never become 0.
        for var in TOOLCHAIN_BEHIND TOOLCHAIN_UPSTREAM TOOLCHAIN_AGE TOOLCHAIN_AGE_SOURCE; do
            eval "value=\$$var"
            [ -n "$value" ] || eval "$var='-'"
        done
    fi
    TOOLCHAIN_LINE="$("$TOOLCHAIN_HELPER" --path "$CHECKOUT" --quiet 2>/dev/null)"
fi

# An install root holding packages is NOT "no installed Claude skills found",
# even when none of them is ours to judge (issue #1034, counter-model finding).
# The early exit keyed on CLAUDE_SKILLS_MANAGED alone, so a root whose packages
# had all LOST their `metadata.source` marker took it - and emitted a skip whose
# reason denied the existence of the very packages that went unexamined. That is
# the precise scenario the skipped count was added to expose, disappearing down
# the one path that reports before the count is ever printed.
# UNKNOWN IS NOT ZERO. The first cut folded `?` in with 0, which converted an
# unmeasured population into an asserted absence on the one path where that is
# supported: an OLDER checker emits the pre-#1034 note, so the root is CHECKED
# but its skipped count is unreadable - and the early exit below then reported
# "no installed Claude skills found" over packages it never counted. Live on
# the reference host, where all 12 packages under ~/.claude/skills are
# unmarked. Caught in the second counter-model pass of #1034.
CLAUDE_SKILLS_UNJUDGED=0
if [ "$CLAUDE_SKILLS_CHECKED" -eq 1 ]; then
    case "$CLAUDE_SKILLS_SKIPPED" in
        0)           ;;                            # measured, and empty
        ""|*[!0-9]*) CLAUDE_SKILLS_UNJUDGED=1 ;;   # unknown - never "absent"
        *)           CLAUDE_SKILLS_UNJUDGED=1 ;;   # measured, and non-empty
    esac
fi

if [ "$RETIRED" -eq 0 ] && [ "$HELPERS_TOTAL" -eq 0 ] && [ "$HELPERS_MISSING" -eq 0 ] \
   && [ "$CODEX_SKILLS_CHECKED" -eq 0 ] && [ "$CLAUDE_SKILLS_MANAGED" -eq 0 ] \
   && [ "$CLAUDE_SKILLS_UNANSWERED" -eq 0 ] && [ "$CLAUDE_SKILLS_UNJUDGED" -eq 0 ]; then
    emit_skip "no retired CPP marketplace surface, installed checkout helpers, or installed Codex/Claude skills found"
fi

SPLIT=0
if [ "$RETIRED" -eq 1 ] && [ "$HELPERS_CURRENT" -gt 0 ] && [ "$HELPERS_STALE" -eq 0 ] && [ "$HELPERS_MISSING" -eq 0 ]; then
    SPLIT=1
fi

VERDICT="ok"
if [ "$HELPERS_STALE" -gt 0 ] || [ "$HELPERS_MISSING" -gt 0 ] || [ "$CODEX_SKILLS_STALE" -gt 0 ] \
   || [ "$CLAUDE_SKILLS_STALE" -gt 0 ]; then
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
    if [ "$CLAUDE_SKILLS_STALE" -gt 0 ]; then
        clauses+=("${CLAUDE_SKILLS_STALE} Claude skill(s) stale in ${CLAUDE_SKILLS_DIR} - re-install from the checkout")
    fi
    # AN UNANSWERED QUESTION REACHES THE QUIET SURFACE TOO. Report mode said
    # "NOT CHECKED" and quiet said nothing at all, so a host whose checker was
    # missing printed exactly what a clean host prints - the report-mode fix
    # applied to one surface and not the one that actually reaches a session
    # start (counter-model review).
    if [ "$CLAUDE_SKILLS_UNANSWERED" -eq 1 ]; then
        clauses+=("Claude skills at ${CLAUDE_SKILLS_DIR} NOT checked (${CLAUDE_SKILLS_UNAVAILABLE_REASON}) - unchecked, not clean")
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
    # The provenance line is SEPARATE and unconditional-on-its-own-verdict: the
    # helper prints nothing when the checkout is current, and a line when it is
    # not. Folding it into the clause list above would let a repo with no
    # install drift suppress the one fact that says every clause above was
    # measured against a stale reference (#1029).
    [ -n "$TOOLCHAIN_LINE" ] && echo "$TOOLCHAIN_LINE"
    exit 0
fi

json_escape() {
    # `tr` first for the record separators sed cannot see - see the twin in
    # toolchain-provenance.sh. Backslash before quote, or it doubles its own work.
    printf '%s' "$1" | tr '\n\r\t' '   ' |
        sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/[[:cntrl:]]/ /g'
}

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
    printf '],"claude_skills_root":%s,"claude_skills_checked":%s,' \
        "$([ -n "$CLAUDE_SKILLS_DIR" ] && printf '"%s"' "$CLAUDE_SKILLS_DIR" || printf 'null')" \
        "$([ "$CLAUDE_SKILLS_CHECKED" -eq 1 ] && echo true || echo false)"
    printf '"claude_skills_managed":%s,"claude_skills_clean":%s,"claude_skills_stale":%s,"claude_skills_skipped":%s,"stale_claude_skills":[' \
        "$CLAUDE_SKILLS_MANAGED" "$CLAUDE_SKILLS_CLEAN" "$CLAUDE_SKILLS_STALE" \
        "$([ "$CLAUDE_SKILLS_SKIPPED" = "?" ] && echo null || echo "$CLAUDE_SKILLS_SKIPPED")"
    separator=""
    for skill in "${STALE_CLAUDE_SKILLS[@]}"; do
        printf '%s"%s"' "$separator" "$skill"
        separator=,
    done
    printf '],"toolchain_provenance":"%s","toolchain_behind":%s,' \
        "$TOOLCHAIN_VERDICT" \
        "$([ "$TOOLCHAIN_BEHIND" = "-" ] && printf 'null' || printf '%s' "$TOOLCHAIN_BEHIND")"
    # The gap's QUALIFICATION travels with it. `current, behind 0` against a
    # remote-tracking ref last refreshed months ago is not the same claim as
    # `current` against a fresh one, and a consumer given only the first two
    # fields cannot tell them apart.
    printf '"toolchain_upstream":%s,"toolchain_fetch_age_seconds":%s,"toolchain_fetch_age_source":%s}\n' \
        "$([ "$TOOLCHAIN_UPSTREAM" = "-" ] && printf 'null' || printf '"%s"' "$(json_escape "$TOOLCHAIN_UPSTREAM")")" \
        "$([ "$TOOLCHAIN_AGE" = "-" ] && printf 'null' || printf '%s' "$TOOLCHAIN_AGE")" \
        "$([ "$TOOLCHAIN_AGE_SOURCE" = "-" ] && printf 'null' || printf '"%s"' "$TOOLCHAIN_AGE_SOURCE")"
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

echo ""
echo "  claude skills      ${CLAUDE_SKILLS_DIR:-<none>}"
if [ "$CLAUDE_SKILLS_CHECKED" -eq 1 ]; then
    echo "    ${CLAUDE_SKILLS_MANAGED} CPP-marked, ${CLAUDE_SKILLS_CLEAN} clean, ${CLAUDE_SKILLS_STALE} stale, ${CLAUDE_SKILLS_SKIPPED} skipped (unmarked, never judged)"
    if [ "$CLAUDE_SKILLS_MANAGED" -eq 0 ]; then
        echo "    (packages here carry no CPP metadata.source marker, so none is ours to judge -"
        echo "     a name that matches one of our packages is NOT the ownership test, issue #1029)"
    fi
else
    echo "    NOT CHECKED: ${CLAUDE_SKILLS_UNAVAILABLE_REASON:-unknown reason}"
    echo "    Unchecked is not clean - this root loads in EVERY project (issue #1029)."
fi
if [ "${#STALE_CLAUDE_SKILLS[@]}" -gt 0 ]; then
    echo ""
    echo "  Stale Claude skills: ${STALE_CLAUDE_SKILLS[*]}"
fi

echo ""
echo "  checkout provenance"
case "$TOOLCHAIN_VERDICT" in
    current)
        echo "    current - every comparison above is against a checkout at its upstream tip"
        echo "    measured against ${TOOLCHAIN_UPSTREAM}, evidence ${TOOLCHAIN_AGE}s old (source: ${TOOLCHAIN_AGE_SOURCE})" ;;
    unavailable)
        echo "    NOT MEASURED - toolchain-provenance.sh is absent or produced nothing."
        echo "    Every verdict above compares against THIS checkout and cannot say how current it is." ;;
    unknown)
        echo "    unknown - the gap could not be measured. This is not a gap of zero (issue #1029)." ;;
    *)
        echo "    ${TOOLCHAIN_VERDICT} (behind ${TOOLCHAIN_BEHIND}) - the comparisons above are against a"
        echo "    checkout that is not at its upstream tip, so 'current' here means 'matches a stale"
        echo "    reference', which is what #1029 was filed about." ;;
esac

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
        if [ "$CLAUDE_SKILLS_STALE" -gt 0 ]; then
            echo "Reconcile stale Claude skills by re-installing them from ${CHECKOUT}/.claude/skills."
        fi
        echo "INSTALL_DRIFT: drift" ;;
    ok)
        # NAME ONLY WHAT WAS ACTUALLY COMPARED. "CPP-marked Claude skills match"
        # is vacuously true of zero packages, and a success line that claims more
        # than its input population supports is the detector-contract failure this
        # repository gates on elsewhere.
        ok_subjects="installed helpers and Codex skills"
        if [ "$CLAUDE_SKILLS_MANAGED" -gt 0 ]; then
            ok_subjects="$ok_subjects and ${CLAUDE_SKILLS_MANAGED} CPP-marked Claude skill(s)"
        fi
        echo "install-drift: $ok_subjects match the checkout."
        if [ "$CLAUDE_SKILLS_UNANSWERED" -eq 1 ]; then
            echo "  NOT included in that statement: ${CLAUDE_SKILLS_DIR} (${CLAUDE_SKILLS_UNAVAILABLE_REASON})."
        fi
        echo "INSTALL_DRIFT: ok" ;;
    skipped)
        echo "INSTALL_DRIFT: skipped" ;;
esac
exit 0
