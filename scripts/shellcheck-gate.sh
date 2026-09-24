#!/usr/bin/env sh
# Lint the repository's shell scripts with shellcheck (issue #960).
#
# POSIX sh on purpose: the CI image (koalaman/shellcheck-alpine) provides sh,
# find and the linter itself, but NO bash and NO git. (A comment opening with
# the literal word after '#' would be parsed as a directive - hence the wording.)
#
#: NEGATIVE-CONTROL: controls/shellcheck-gate
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
# MEMBERSHIP IS DERIVED, NOT GLOBBED. Two universe errors are live here:
#   - extension-only misses `scripts/cpp-memory`, a tracked bash script with no
#     .sh suffix. Every `*.sh` glob is blind to it.
#   - tracked-only misses untracked scripts. Those exist in a working checkout
#     and never in a fresh worktree or CI clone, so that blind spot belongs to
#     CI and is only visible locally.
# So: prefer git (tracked PLUS untracked-not-ignored) and fall back to a pruned
# find where git is absent, and say which was used.
#
# EVERY PATH IS CARRIED NUL-DELIMITED and held in the positional parameters, so
# a filename containing a space, a tab or a glob character is one argument and
# is counted once. Word-splitting a path list would both SKIP such a file and
# OVERSTATE the denominator - the exact failure this gate exists to report.
set -u

# THE SHARED GATE MODULE (issue #1127, first migration slice of #1061). What
# moves here is the ARGUMENT RULE and the EXIT MAPPING, not this gate's output:
# every contract line below is unchanged, byte for byte, because the four
# registered controls are the evidence that this migration changed nothing a
# gate can see, and a rewrite that also rewrites its evidence shows nothing.
#
# This gate adopts `gate_map` and `gate_arg_value`. It does NOT adopt
# `gate_emit`: that formats as `KEY: verdict - detail`, and this gate's lines
# are `shellcheck-gate: N file(s) scanned at severity=...`, which carries no
# verdict word. Reshaping them to fit would be exactly the change the slice
# forbids, so the `echo`s stay and the module owns the two things it can own
# without touching output.
#
# WHAT THE USAGE EXIT WAS, AND WHY IT MOVED. `${2:?...}` exits 1 under bash and
# 2 under dash - so this gate reported a usage error with 1, WHICH IS ITS OWN
# FINDINGS CODE, on any host whose /bin/sh is bash. A caller could not tell "you
# passed --root with nothing after it" from "shellcheck found problems". The
# module's usage exit is outside every verdict number this gate declares.
# `${0%/*}`, NEVER `$(dirname "$0")`. `dirname` is an external binary, and
# sourcing the module is the FIRST thing these gates do - so a PATH without it
# left the gate unable to load at all, and therefore unable to say UNKNOWN in
# exactly the environment where UNKNOWN is the answer. Caught by
# `tests/test_shellcheck_stage.py`, which constructs that PATH deliberately and
# which this slice may not edit; that is what the byte-identical constraint is
# for. Parameter expansion forks nothing and needs nothing on PATH.
_gate_lib_dir=${0%/*}
[ "$_gate_lib_dir" = "$0" ] && _gate_lib_dir=.
# shellcheck disable=SC1091  # gate-lib.sh is resolved at run time and linted as its own file (#972)
. "$_gate_lib_dir/gate-lib.sh"

gate_map ok=0 findings=1 unknown=2

# STYLE, the lowest severity (issue #972). #960 adopted this gate at `error` and
# filed everything below it as a counted residual; #972 reviewed that residual to
# zero - every finding fixed, or suppressed on its own line with its reason - and
# raising this default is what closed it. Nothing below the gate is unreviewed
# now. controls/shellcheck-gate/cases/bad-note-severity is the input that tells
# this default from the old one.
#
# What would move this back (ADR 0009): repeated churn from note-level findings
# that are consistently suppressed rather than fixed. The step back is to
# `warning`, never to `error` - `error` re-opens an unreviewed residual.
SEVERITY="${SHELLCHECK_SEVERITY:-style}"
ROOT="."

while [ $# -gt 0 ]; do
    case "$1" in
        --root) gate_arg_value "$1" "$#" "${2-}"; ROOT=$GATE_VALUE; shift 2 ;;
        --severity) gate_arg_value "$1" "$#" "${2-}"; SEVERITY=$GATE_VALUE; shift 2 ;;
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

# --- derive the candidate set, NUL-delimited ----------------------------------
# An enumeration that fails PARTWAY yields a short list and a clean verdict, so
# its exit status is checked rather than assumed.
CAND="${TMPDIR:-/tmp}/shellcheck-gate.$$"
trap 'rm -f "$CAND"' EXIT INT TERM

if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    SOURCE="git"
    git -C "$ROOT" ls-files -z --cached --others --exclude-standard > "$CAND" \
        || unknown "git enumeration failed; the file list is incomplete."
else
    SOURCE="find"
    # The prune list is the OWNERSHIP BOUNDARY: a nested checkout or an installed
    # dependency is not this repository's code to lint, and answers its own
    # linting question through its own gate.
    ( cd "$ROOT" && find . \
        \( -name .git -o -name .venv -o -name venv -o -name node_modules \
           -o -name .mypy_cache -o -name .tox -o -name .worktrees \
           -o -name site-packages -o -name vendor \) -prune -o \
        -type f -print0 ) > "$CAND" \
        || unknown "find enumeration failed; the file list is incomplete."
fi

# A path containing a NEWLINE cannot survive the NUL-to-newline conversion the
# read loop below needs, and POSIX sh has no NUL-safe read. Silently mangling one
# would BOTH skip that file and double-count a same-named neighbour, so detect the
# case and refuse. Comparing the NUL count against the line count is exact.
NULS=$(tr -cd '\0' < "$CAND" | wc -c | tr -d ' ')
LINES=$(tr '\0' '\n' < "$CAND" | grep -c '' || true)
[ "$NULS" = "$LINES" ] || unknown "a path contains a newline ($LINES lines vs $NULS entries); this gate cannot enumerate it safely."

# --- filter to shell: extension OR interpreter --------------------------------
set --
COUNT=0
while IFS= read -r f <&3; do
    [ -n "$f" ] || continue
    f="${f#./}"
    [ -f "$ROOT/$f" ] || continue
    case "$f" in
        controls/*/cases/*) continue ;;    # deliberately-bad fixtures, linted by the control itself
        controls/*/anchors/*) continue ;;  # frozen byte-identical history; its sha256 IS the provenance
    esac
    case "$f" in
        *.sh) set -- "$@" "$f"; COUNT=$((COUNT + 1)); continue ;;
    esac
    # Extensionless shell scripts are real here. Identify the INTERPRETER rather
    # than accepting any shebang ending in "sh" - `wish` and `osascript` do too.
    # An UNREADABLE file is not a non-shell file. Distinguish it from an empty
    # one: a failed open means the population was not fully classified.
    [ -r "$ROOT/$f" ] || unknown "cannot read '$f'; the population was not fully classified."
    shebang=""
    IFS= read -r shebang < "$ROOT/$f" 2>/dev/null || true
    case "$shebang" in '#!'*) ;; *) continue ;; esac
    interp=$(printf '%s' "$shebang" | sed -e 's|^#!*[[:space:]]*||' -e 's|[[:space:]].*$||')
    case "${interp##*/}" in
        env)
            # `env` may carry options before the interpreter; `-S "bash -eu"` is
            # the common one. Strip leading option words, then take the first
            # remaining token as the interpreter.
            rest=$(printf '%s' "$shebang" | sed -e 's|^#!*[[:space:]]*[^[:space:]]*env[[:space:]][[:space:]]*||')
            rest=$(printf '%s' "$rest" | sed -e 's|^-S[[:space:]]*||' -e 's|^--split-string[= ]*||')
            while :; do
                case "$rest" in
                    -*) rest=$(printf '%s' "$rest" | sed -e 's|^[^[:space:]]*[[:space:]]*||') ;;
                    *) break ;;
                esac
                [ -n "$rest" ] || break
            done
            interp=$(printf '%s' "$rest" | sed -e "s|^[\"']||" -e 's|[[:space:]].*$||')
            ;;
    esac
    case "${interp##*/}" in
        sh|bash|dash|ksh|ksh93|mksh|zsh|ash|busybox) set -- "$@" "$f"; COUNT=$((COUNT + 1)) ;;
    esac
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
