#!/usr/bin/env sh
# Lint the repository's shell scripts with shellcheck (issue #960).
#
# POSIX sh on purpose: the CI image (koalaman/shellcheck-alpine) provides sh,
# find and the linter itself, but NO bash and NO git. (A comment opening with
# the literal word after '#' would be parsed as a directive - hence the wording.)
#
# CONTRACT
#   exit 0  every examined file clean at SEVERITY; prints the denominator
#   exit 1  findings at SEVERITY  (linter exit 1 ONLY)
#   exit 2  UNKNOWN - could not look, or could not look COMPLETELY. NOT clean.
#
# The success line always names what was examined and how it was derived, per
# #952 as amended: a zero is a denominator and reads UNKNOWN unless the
# instrument can show it was looking in the right place.
#
# EVERY PATH IS CARRIED NUL-DELIMITED and held in the positional parameters, so
# a filename containing a space, a tab or a glob character is one argument and
# is counted once. Word-splitting a path list would both SKIP such a file and
# OVERSTATE the denominator - the exact failure this gate exists to report.
set -u

SEVERITY="${SHELLCHECK_SEVERITY:-error}"
ROOT="."

while [ $# -gt 0 ]; do
    case "$1" in
        --root) ROOT="${2:?--root needs a directory}"; shift 2 ;;
        --severity) SEVERITY="${2:?--severity needs a value}"; shift 2 ;;
        -h|--help) sed -n '2,31p' "$0"; exit 0 ;;
        *) echo "shellcheck-gate: unknown argument: $1" >&2; exit 2 ;;
    esac
done

unknown() {
    echo "shellcheck-gate: UNKNOWN - $1" >&2
    echo "shellcheck-gate: this is not a pass." >&2
    exit 2
}

[ -d "$ROOT" ] || unknown "root '$ROOT' is not a directory."
command -v shellcheck >/dev/null 2>&1 || unknown "shellcheck is not installed, so nothing was examined."

# --- derive the candidate set -------------------------------------------------
CAND="${TMPDIR:-/tmp}/shellcheck-gate.$$"
trap 'rm -f "$CAND"' EXIT INT TERM

# #960 states the population as "96 tracked .sh files" and offers "scan the
# working tree" as the alternative, so this globs the working tree for *.sh.
SOURCE="find-glob"
( cd "$ROOT" && find . \
    \( -name .git -o -name .venv -o -name node_modules \) -prune -o \
    -name '*.sh' -type f -print0 ) > "$CAND" \
    || unknown "find enumeration failed; the file list is incomplete."

# --- collect ------------------------------------------------------------------
set --
COUNT=0
while IFS= read -r f <&3; do
    [ -n "$f" ] || continue
    f="${f#./}"
    [ -f "$ROOT/$f" ] || continue
    case "$f" in
        controls/*/cases/*) continue ;;
        controls/*/anchors/*) continue ;;
    esac
    set -- "$@" "$f"; COUNT=$((COUNT + 1))
done 3<<EOF
$(tr '\0' '\n' < "$CAND")
EOF

[ "$COUNT" -gt 0 ] || unknown "0 shell files matched under '$ROOT' (source=$SOURCE). 0 examined is not 0 findings."

# --- run ----------------------------------------------------------------------
# `--` terminates options: a file literally named `--help` would otherwise be
# read as a flag, and the linter would exit 0 having examined nothing at all.
( cd "$ROOT" && shellcheck --severity="$SEVERITY" -f gcc -- "$@" )
RC=$?

case "$RC" in
    0) echo "shellcheck-gate: ok - $COUNT file(s) scanned at severity=$SEVERITY, 0 findings (source=$SOURCE)."
       exit 0 ;;
    1) echo "shellcheck-gate: $COUNT file(s) scanned at severity=$SEVERITY, findings reported above (source=$SOURCE)." >&2
       exit 1 ;;
    # Anything else is the linter failing to RUN - bad usage, unreadable input,
    # an unsupported option. That is not a finding and must not be reported as
    # one, or an operational failure scores as a detection.
    *) unknown "shellcheck exited $RC, which is not a findings verdict; the population was not examined." ;;
esac
