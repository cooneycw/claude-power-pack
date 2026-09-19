#!/usr/bin/env bash
# VENDORED BLIND ARTIFACT for controls/deletion-accounting (issue #1031).
#
# This is the pre-push deletion check as it was actually adopted and circulated,
# wrapped in the current gate's output contract so the harness can score the two
# side by side:
#
#     git diff "$MERGE_BASE" | grep -E '^-[^-]' | sort | uniq -c
#
# `^-[^-]` requires a character after the `-`. It therefore cannot match a bare
# `-` (a deleted BLANK line), a line beginning `--` (a deleted MARKDOWN BULLET,
# since `- item` renders as `-- item`), or a deleted `---` (a front-matter
# delimiter or thematic break, which renders as `----`). Measured on a merged
# documentation PR: 88 matched, 24 bare `-` invisible, 7 `--` invisible, 119
# actual.
#
# It is committed so the control has something that MISSES the known-bad input.
# If `scripts/deletion-accounting.sh` ever regresses to matching on the text of
# a line rather than parsing hunks, it becomes this file, and the control goes
# BLIND instead of quietly agreeing with it. Do not "fix" this artifact - its
# blindness is the whole point.
#
# SYNTHETIC: this exact file never shipped. The one-liner it wraps did, in
# https://github.com/cooneycw/claude-power-pack/issues/864#issuecomment-5681293647

set -u

SELF="deletion-accounting"
ROOT=""
DIFF_FILE=""
TOP=20

unknown() {
    echo "$SELF: $1" >&2
    echo "DELETION_ACCOUNTING_SOURCE: unknown"
    echo "DELETION_ACCOUNTING_FILES: unknown"
    echo "DELETION_ACCOUNTING_LINES: unknown"
    echo "DELETION_ACCOUNTING_BLINDSPOT: unknown"
    echo "$SELF: UNKNOWN - could not look. This is not 'nothing is deleted'."
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --root)      ROOT="${2:?--root needs a directory}"; shift 2 ;;
        --diff-file) DIFF_FILE="${2:?--diff-file needs a path}"; shift 2 ;;
        --top)       TOP="${2:?--top needs a number}"; shift 2 ;;
        --base|--repo) shift 2 ;;
        *)           unknown "unrecognised argument '$1'" ;;
    esac
done

DIFF_TEXT=""
SOURCE=""
if [ -n "$DIFF_FILE" ]; then
    [ -r "$DIFF_FILE" ] || unknown "--diff-file '$DIFF_FILE' is not readable"
    DIFF_TEXT="$(cat -- "$DIFF_FILE")"
    SOURCE="file=$DIFF_FILE"
elif [ -n "$ROOT" ]; then
    [ -d "$ROOT" ] || unknown "--root '$ROOT' is not a directory"
    found=0
    while IFS= read -r patch; do
        [ -n "$patch" ] || continue
        DIFF_TEXT="$DIFF_TEXT$(cat -- "$patch")
"
        found=$((found + 1))
    done <<EOF
$(find "$ROOT" -type f \( -name '*.diff' -o -name '*.patch' \) 2>/dev/null | sort)
EOF
    [ "$found" -gt 0 ] || unknown "--root '$ROOT' holds no *.diff or *.patch file"
    SOURCE="root=$ROOT"
else
    unknown "nothing to examine"
fi

# THE BLINDNESS, in one line.
DELETED="$(printf '%s\n' "$DIFF_TEXT" | grep -E '^-[^-]' || true)"
if [ -z "$DELETED" ]; then
    LINES=0
else
    LINES="$(printf '%s\n' "$DELETED" | wc -l | tr -d ' ')"
fi
FILES="$(printf '%s\n' "$DIFF_TEXT" | grep -cE '^\+\+\+ ' || true)"
[ "$LINES" -gt 0 ] || FILES=0

echo "DELETION_ACCOUNTING_SOURCE: $SOURCE"
echo "DELETION_ACCOUNTING_FILES: $FILES"
echo "DELETION_ACCOUNTING_LINES: $LINES"
echo "DELETION_ACCOUNTING_BLINDSPOT: 0"

if [ "$LINES" -eq 0 ]; then
    echo "$SELF: ok - 0 deleted line(s) in $FILES file(s) with deletions (source=$SOURCE)"
    exit 0
fi

echo "DELETION_ACCOUNTING_FINDING: $LINES deleted line(s) across $FILES file(s)"
if [ "$TOP" -gt 0 ]; then
    printf '%s\n' "$DELETED" | sed 's/^-//' | sort | uniq -c | sort -rn | head -n "$TOP" | sed 's/^/    /'
fi
exit 1
