#!/usr/bin/env bash
# tools-version-check.sh - "present" is not "current" (issue #1029, specimen 3).
#
# THE FAILURE THIS ANSWERS. `make tools-check` (#987) asks `command -v <tool>`.
# That question is satisfied identically by ANY version. Meanwhile `.woodpecker.yml`
# pins `koalaman/shellcheck-alpine:v0.10.0@sha256:...` and states the reason in
# its own words - *"running the gate under two different linters would make the
# control's verdict depend on which container reached it"*. So a host whose apt
# supplied shellcheck 0.9.0 gets `tools-check: ok` and a `controls/shellcheck-gate`
# verdict that need not match CI's, with nothing anywhere saying the two gates ran
# under different instruments.
#
# THE PIN IS READ, NEVER RE-DECLARED. Re-stating `0.10.0` in this file would
# create a THIRD copy of a version that already exists in two places, and a
# hand-copied constant goes stale at the first bump - the same
# hand-maintained-number failure #1002 removed from the ADR 0008 census. Every
# pin here is PARSED from the file that already owns it:
#
#   `shellcheck` <- Makefile  SHELLCHECK_IMAGE  (tag of the pinned CI image)
#   `gitleaks`   <- Makefile  GITLEAKS_IMAGE    (tag of the pinned CI image)
#   `jq`         <- scripts/ci-stage-jq.py  JQ_URL  (the release the CI stager fetches)
#
# (The backticks above are load-bearing: a comment whose first word is
# `shellcheck` is parsed as a shellcheck DIRECTIVE - SC1073/SC1072, exit 1, at
# this repository's own --severity=error. Found by the counter-model review.)
#
# The Makefile's two image pins are held byte-identical to `.woodpecker.yml`'s by
# tests/test_pinned_tool_versions.py, so "the pin that already exists in
# .woodpecker.yml" is genuinely ONE declaration read from the convenient end,
# not two that can drift apart quietly.
#
# A PIN THAT CANNOT BE READ IS `unknown`, NEVER `ok`. If the Makefile is moved,
# a variable renamed, or the tag format changes, this reports `unknown` and says
# which pin it failed to parse. A version checker that silently stops finding its
# pins and keeps printing green is the blind instrument this issue is about,
# reproduced inside the fix for it.
#
# IT DOES NOT GATE, exactly like `tools-check` itself. A mismatch is reported and
# the caller continues to the target that actually runs the tool, which is where
# the honest verdict lives. Naming a divergent version early is diagnosis;
# deciding what it MEANS belongs to the instrument that uses it.
#
# Usage:
#   tools-version-check.sh                 # human report; always exit 0
#   tools-version-check.sh --quiet         # one advisory line, only when action is needed
#   tools-version-check.sh --json          # machine-readable; always exit 0
#
# Output in report mode ends with:
#   TOOLS_VERSION: ok | mismatch | absent | unknown
#
# Precedence is `unknown` > `mismatch` > `absent` > `ok` for the aggregate, and
# every tool's own line is printed regardless, so an aggregate never conceals a
# per-tool finding. `unknown` outranks `mismatch` because a pin this script
# could not read means the comparison did not happen - and an unmade comparison
# must never render as a made one. `absent` ranks last because `tools-check`
# already reports absence loudly; this script adds nothing there.
#
# Env (test seams - unset in normal use):
#   CPP_TOOLS_VERSION_ROOT   override the checkout whose files hold the pins

set -uo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")"
SELF_DIR="$(cd "$(dirname "$SELF")" && pwd)"
ROOT="${CPP_TOOLS_VERSION_ROOT:-$(cd "$SELF_DIR/.." && pwd -P)}"

MODE="report"
for arg in "$@"; do
    case "$arg" in
        --report) MODE="report" ;;
        --quiet)  MODE="quiet" ;;
        --json)   MODE="json" ;;
        -h|--help)
            awk 'NR==1 && /^#!/ {next} /^#/ {sub(/^# ?/, ""); print; next} {exit}' "$SELF"
            exit 0 ;;
        *)
            echo "tools-version-check: unknown argument '$arg' (use --quiet, --json)" >&2
            exit 2 ;;
    esac
done

# Normalize the many spellings a version arrives in to bare dotted digits, so
# `v0.10.0`, `0.10.0` and `jq-1.7.1` compare equal when they mean the same
# release. Anything with no dotted-digit run at all yields the empty string,
# which callers treat as unparseable - never as a match.
normalize_version() {
    printf '%s' "$1" | grep -oE '[0-9]+(\.[0-9]+)+' | head -1
}

MAKEFILE="$ROOT/Makefile"
JQ_STAGER="$ROOT/scripts/ci-stage-jq.py"

pin_from_makefile() {
    # `NAME := repo/image:vX.Y.Z@sha256:...` -> X.Y.Z
    local var="$1" line
    [ -f "$MAKEFILE" ] || return 1
    line="$(grep -E "^[[:space:]]*${var}[[:space:]]*:?=" "$MAKEFILE" | head -1)" || return 1
    [ -n "$line" ] || return 1
    # The TAG only - everything between the last ':' before '@' and the '@'.
    line="${line%%@sha256:*}"
    normalize_version "${line##*:}"
}

pin_from_jq_stager() {
    # JQ_URL = ".../releases/download/jq-1.7.1/jq-linux-amd64" -> 1.7.1
    local line
    [ -f "$JQ_STAGER" ] || return 1
    line="$(grep -E '^[[:space:]]*JQ_URL[[:space:]]*=' "$JQ_STAGER" | head -1)" || return 1
    [ -n "$line" ] || return 1
    printf '%s' "$line" | grep -oE 'jq-[0-9]+(\.[0-9]+)+' | head -1 | sed 's/^jq-//'
}

installed_version() {
    case "$1" in
        shellcheck) normalize_version "$(shellcheck --version 2>/dev/null | grep -i '^version:' | head -1)" ;;
        gitleaks)   normalize_version "$(gitleaks version 2>/dev/null | head -1)" ;;
        jq)         normalize_version "$(jq --version 2>/dev/null | head -1)" ;;
        *)          printf '' ;;
    esac
}

TOOLS=(shellcheck gitleaks jq)
declare -A PINNED=() INSTALLED=() STATE=() PIN_SOURCE=()

PIN_SOURCE[shellcheck]="Makefile SHELLCHECK_IMAGE"
PIN_SOURCE[gitleaks]="Makefile GITLEAKS_IMAGE"
PIN_SOURCE[jq]="scripts/ci-stage-jq.py JQ_URL"

for tool in "${TOOLS[@]}"; do
    case "$tool" in
        shellcheck) PINNED[$tool]="$(pin_from_makefile SHELLCHECK_IMAGE || true)" ;;
        gitleaks)   PINNED[$tool]="$(pin_from_makefile GITLEAKS_IMAGE || true)" ;;
        jq)         PINNED[$tool]="$(pin_from_jq_stager || true)" ;;
    esac
    if ! command -v "$tool" >/dev/null 2>&1; then
        INSTALLED[$tool]=""
        # A tool that is not installed still gets its pin reported, because the
        # pin is what someone installing it needs to know.
        STATE[$tool]="absent"
        continue
    fi
    INSTALLED[$tool]="$(installed_version "$tool")"
    if [ -z "${PINNED[$tool]}" ]; then
        STATE[$tool]="unknown-pin"
    elif [ -z "${INSTALLED[$tool]}" ]; then
        STATE[$tool]="unknown-installed"
    elif [ "${PINNED[$tool]}" = "${INSTALLED[$tool]}" ]; then
        STATE[$tool]="match"
    else
        STATE[$tool]="mismatch"
    fi
done

VERDICT="ok"
HAVE_MISMATCH=0
HAVE_UNKNOWN=0
HAVE_ABSENT=0
for tool in "${TOOLS[@]}"; do
    case "${STATE[$tool]}" in
        mismatch)                        HAVE_MISMATCH=1 ;;
        unknown-pin|unknown-installed)   HAVE_UNKNOWN=1 ;;
        absent)                          HAVE_ABSENT=1 ;;
    esac
done
if   [ "$HAVE_UNKNOWN"  -eq 1 ]; then VERDICT="unknown"
elif [ "$HAVE_MISMATCH" -eq 1 ]; then VERDICT="mismatch"
elif [ "$HAVE_ABSENT"   -eq 1 ]; then VERDICT="absent"
fi

describe() {
    local tool="$1"
    case "${STATE[$tool]}" in
        match)             printf 'matches the pin' ;;
        mismatch)          printf 'DIFFERS from the pin - this host and CI would run different instruments' ;;
        absent)            printf 'not on PATH (make tools-check reports this; nothing to compare)' ;;
        unknown-pin)       printf 'PIN UNREADABLE from %s - the comparison did not happen' "${PIN_SOURCE[$tool]}" ;;
        unknown-installed) printf 'installed version UNPARSEABLE - the comparison did not happen' ;;
    esac
}

case "$MODE" in
    quiet)
        clauses=()
        for tool in "${TOOLS[@]}"; do
            case "${STATE[$tool]}" in
                mismatch)
                    clauses+=("$tool ${INSTALLED[$tool]} != pinned ${PINNED[$tool]}") ;;
                unknown-pin|unknown-installed)
                    clauses+=("$tool version UNCOMPARED") ;;
            esac
        done
        if [ "${#clauses[@]}" -gt 0 ]; then
            joined="${clauses[0]}"
            for clause in "${clauses[@]:1}"; do joined="${joined}; ${clause}"; done
            echo "CPP tools: ${joined} - this host's gate verdict need not match CI's (#1029)"
        fi
        exit 0 ;;
    json)
        printf '{"verdict":"%s","tools":[' "$VERDICT"
        sep=""
        for tool in "${TOOLS[@]}"; do
            pin="${PINNED[$tool]}"; ins="${INSTALLED[$tool]}"
            printf '%s{"name":"%s","state":"%s","pinned":%s,"installed":%s,"pin_source":"%s"}' \
                "$sep" "$tool" "${STATE[$tool]}" \
                "$([ -n "$pin" ] && printf '"%s"' "$pin" || printf 'null')" \
                "$([ -n "$ins" ] && printf '"%s"' "$ins" || printf 'null')" \
                "${PIN_SOURCE[$tool]}"
            sep=,
        done
        printf ']}\n'
        exit 0 ;;
esac

echo "tools-version-check: pins read from $ROOT"
for tool in "${TOOLS[@]}"; do
    printf '  %-11s pinned %-10s installed %-10s %s\n' \
        "$tool" "${PINNED[$tool]:-?}" "${INSTALLED[$tool]:-none}" "$(describe "$tool")"
done
echo ""
case "$VERDICT" in
    ok)
        echo "Every pinned external tool on this host is the version CI runs." ;;
    mismatch)
        echo "At least one tool differs from its pin. The gates here and in CI are different"
        echo "instruments, so their verdicts need not agree - which is the reason"
        echo ".woodpecker.yml pins them in the first place (issue #1029, specimen 3)." ;;
    absent)
        echo "Nothing mismatched; at least one tool is not installed. 'make tools-check' owns"
        echo "that report - the pin above is what to install." ;;
    unknown)
        echo "At least one comparison DID NOT HAPPEN - a pin or an installed version could not"
        echo "be parsed. That is not a match. Fix the parse before reading this as agreement." ;;
esac
echo "TOOLS_VERSION: $VERDICT"
exit 0
