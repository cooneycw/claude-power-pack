#!/usr/bin/env bash
# Account for every line a diff DELETES, before you push it (issue #1031).
#
# WHY THIS EXISTS. Worktrees share the object store AND the refs, including
# `refs/remotes/origin/main`. A sibling session's `git fetch` in ANY worktree
# advances `origin/main` for EVERY worktree with no signal in yours, so the
# ordinary squash idiom becomes a revert:
#
#     git rebase origin/main          # origin/main == A; worktree is A + mine
#     #   ... a sibling fetches; origin/main silently becomes B ...
#     git reset --soft origin/main    # HEAD moves to B, worktree still holds A + mine
#     git commit                      # the commit's diff is (A + mine) vs B
#                                     # => every change in A..B is a DELETION authored by me
#
# Caught in a real branch before pushing: a commit touching 10 files reported
# 22 files, 1022 insertions, 861 deletions; the extra 12 were another worker's
# merged PR rendered as deletions. `git log --oneline origin/main..HEAD` shows
# ONE commit, yours, with your message; two-dot and three-dot diffs are
# IDENTICAL, because after the reset `origin/main` IS the merge base; and the
# suite passes green, because a suite cannot object to work that is absent.
#
# The tell is the FILE COUNT, which is why this prints it first.
#
# WHAT IT COUNTS, AND WHY NOT WITH grep. The check adopted to catch exactly the
# above was:
#
#     git diff "$MERGE_BASE" | grep -E '^-[^-]' | sort | uniq -c
#
# `^-[^-]` requires a character after the `-`, so it cannot match a bare `-` (a
# deleted BLANK line) or a line beginning `--` (a deleted MARKDOWN BULLET,
# because `- item` renders as `-- item`). Measured on a merged documentation
# PR: 88 matched, 24 bare `-` invisible, 7 `--` invisible, 119 actual - 26%
# unseen, landing precisely on the bullet lists most likely to carry a removed
# rule or caveat.
#
# The corrected one-liner - `grep -E '^-' | grep -v '^---'` - is better and
# still not right: a deleted line whose CONTENT begins `---` renders as `----`,
# matches `^---`, and is thrown away with the file headers. In a repository
# whose markdown carries front-matter delimiters and thematic breaks that is
# not a corner case. Measured on a four-deletion diff: blind form 1, corrected
# one-liner 3, actual 4.
#
# So this does not pattern-match the diff at all. It PARSES it: a `-` line
# counts only INSIDE a hunk, and file headers are recognised structurally
# rather than by what their text happens to look like. No content can hide.
#
# USAGE
#   deletion-accounting.sh --base <ref> [--repo <dir>]   diff a checkout against a base
#   deletion-accounting.sh --diff-file <path>            account for one patch file
#   deletion-accounting.sh --root <dir>                  every *.diff / *.patch under <dir>
#   deletion-accounting.sh --top <n>                     census rows to print (default 20)
#
# `--base` is RESOLVED TO A SHA and that sha is printed, because the hazard
# above is a moving ref. Pin the base yourself for the same reason:
#
#   BASE=$(git rev-parse origin/main); deletion-accounting.sh --base "$BASE"
#
# CONTRACT (stdout, in this order)
#   DELETION_ACCOUNTING_SOURCE: base=<sha> | file=<path> | root=<dir>
#   DELETION_ACCOUNTING_FILES: <files carrying at least one deleted line>
#   DELETION_ACCOUNTING_LINES: <deleted lines>
#   DELETION_ACCOUNTING_BLINDSPOT: <of those, invisible to the `^-[^-]` form>
#   DELETION_ACCOUNTING_FINDING: <n> deleted line(s) across <m> file(s)   (only when n > 0)
#   deletion-accounting: ok - 0 deleted line(s) ...                       (only when n == 0)
#
# EXIT
#   0  nothing is deleted
#   1  deletions found - the census is above; confirm every one is yours
#   2  UNKNOWN: it could not look (no such ref, unreadable input, git absent).
#      Never 0, because "I examined nothing" and "nothing is deleted" are
#      different facts and must not share an exit code.
#
# Exit 1 is not an accusation. This instrument cannot know which deletions are
# yours - only you can - so its job is to put every one of them in front of you
# with nothing filtered out. Its verdict is consumed by a human or an agent
# about to push, and nothing downstream re-derives which lines a branch
# deletes, which is why it carries a committed negative control.
#
#: NEGATIVE-CONTROL: controls/deletion-accounting

set -u

SELF="deletion-accounting"
BASE=""
REPO="."
DIFF_FILE=""
ROOT=""
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
        --base)      BASE="${2:?--base needs a ref}"; shift 2 ;;
        --repo)      REPO="${2:?--repo needs a directory}"; shift 2 ;;
        --diff-file) DIFF_FILE="${2:?--diff-file needs a path}"; shift 2 ;;
        --root)      ROOT="${2:?--root needs a directory}"; shift 2 ;;
        --top)       TOP="${2:?--top needs a number}"; shift 2 ;;
        -h|--help)   sed -n '1,80p' "$0"; exit 0 ;;
        *)           unknown "unrecognised argument '$1'" ;;
    esac
done

case "$TOP" in
    ''|*[!0-9]*) unknown "--top needs a non-negative integer, got '$TOP'" ;;
esac

# --- gather the diff text ---------------------------------------------------
DIFF_TEXT=""
SOURCE=""
GIT_EMPTY=0
if [ -n "$BASE" ]; then
    command -v git >/dev/null 2>&1 || unknown "git is not on PATH"
    [ -d "$REPO" ] || unknown "--repo '$REPO' is not a directory"
    git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        || unknown "'$REPO' is not inside a git work tree"
    # RESOLVED AND PRINTED. The whole hazard is a base that moves under you, so
    # the accounting names the commit it was taken against rather than the ref
    # that pointed there at the time.
    SHA="$(git -C "$REPO" rev-parse --verify "$BASE^{commit}" 2>/dev/null)" \
        || unknown "--base '$BASE' does not resolve to a commit in '$REPO'"
    # CANONICAL PATCH OUTPUT, NOT THE USER'S PRESENTATION SETTINGS. `git diff`
    # inherits config, and a presentation setting silently turns this instrument
    # off: measured on this checkout, `color.ui=always` wraps every `-` in an
    # escape sequence, so the parser recognises no hunk at all and a real
    # 19-deletion diff reports 0 and exits CLEAN. `--no-ext-diff` and
    # `--no-textconv` close the same door for a configured external driver or
    # textconv filter, which can replace the patch body wholesale.
    DIFF_TEXT="$(git -C "$REPO" -c core.pager=cat -c color.ui=false \
        diff --no-color --no-ext-diff --no-textconv "$SHA" 2>/dev/null)" \
        || unknown "'git diff $SHA' failed in '$REPO'"
    SOURCE="base=$SHA"
    # A git diff that is genuinely EMPTY is clean, and must stay distinguishable
    # from an input we could not parse: git successfully reported no change.
    [ -n "$DIFF_TEXT" ] || GIT_EMPTY=1
elif [ -n "$DIFF_FILE" ]; then
    # `-r` is true for a DIRECTORY too, and `cat` on one fails while this script
    # used to discard its status - a complete-looking zero over input that was
    # never read.
    [ -f "$DIFF_FILE" ] || unknown "--diff-file '$DIFF_FILE' is not a regular file"
    DIFF_TEXT="$(cat -- "$DIFF_FILE")" || unknown "--diff-file '$DIFF_FILE' could not be read"
    SOURCE="file=$DIFF_FILE"
elif [ -n "$ROOT" ]; then
    [ -d "$ROOT" ] || unknown "--root '$ROOT' is not a directory"
    # `find ... | sort` hands the assignment SORT's status, and `pipefail` is not
    # set here - an unreadable subtree exits 1 from find, sort exits 0 over
    # whatever did come through, and a PARTIAL population is accounted as a
    # whole one. The two stages are separated so find's own status is read.
    PATCH_LIST_RAW="$(find "$ROOT" -type f \( -name '*.diff' -o -name '*.patch' \) 2>/dev/null)" \
        || unknown "--root '$ROOT' could not be traversed - the patch population is incomplete"
    PATCH_LIST="$(printf '%s\n' "$PATCH_LIST_RAW" | sort)"
    found=0
    while IFS= read -r patch; do
        [ -n "$patch" ] || continue
        [ -f "$patch" ] || unknown "patch '$patch' is not a regular file"
        chunk="$(cat -- "$patch")" || unknown "patch '$patch' could not be read"
        DIFF_TEXT="$DIFF_TEXT$chunk
"
        found=$((found + 1))
    done <<EOF
$PATCH_LIST
EOF
    # A root holding no patches is UNKNOWN, not clean: an empty population and
    # a population with nothing deleted in it are different facts.
    [ "$found" -gt 0 ] || unknown "--root '$ROOT' holds no *.diff or *.patch file"
    SOURCE="root=$ROOT"
else
    unknown "nothing to examine: pass --base, --diff-file or --root"
fi

# --- parse it ---------------------------------------------------------------
# STRUCTURAL, NOT PATTERN-MATCHED, AND HUNK-COUNTED.
#
# The hunk header declares how many old-side and new-side lines follow, so the
# parser CONSUMES exactly that many and looks for a file header only once both
# are exhausted. Nothing inside a hunk can be mistaken for a header, whatever it
# spells.
#
# Recognising headers by their TEXT is not enough, and the counter-model review
# of this change proved it: inside a hunk, a deleted `-- a/foo` followed by an
# added `++ b/bar` renders as `--- a/foo` / `+++ b/bar` - git's own header
# shape, `a/` and `b/` prefixes included - and a text rule ended the hunk there
# and reported 0 deletions where git reports 2. That is the exact
# content-dependent blindness this instrument exists to remove, reintroduced one
# level down.
#
# COVERAGE IS COUNTED TOO. A file of bytes carrying no hunk, no `diff --git` and
# no binary notice was never a diff, and "0 deletions" over it is a statement
# about nothing: `fatal: upstream diff generation failed` reported CLEAN.
PARSED="$(printf '%s\n' "$DIFF_TEXT" | awk '
function hunk_count(spec,   a, n) { n = split(spec, a, ","); return (n >= 2) ? a[2] + 0 : 1 }
function strip(p) { sub(/^[ab]\//, "", p); return p }
# A file SECTION is closed when the next one starts, or at end of input. Only
# then can we ask whether it was actually parsed - which is the difference
# between "this patch had nothing to delete" and "we never read its body".
function close_section(   key) {
    if (sec_headers && !sec_hunks && !sec_binary) incomplete++
    if (sec_binary && sec_deleted) {
        key = (cur_file != "") ? cur_file : ((oldf != "") ? oldf : "(binary)")
        files["(binary) " key] = 1
        bin_del++
    }
    sec_headers = 0; sec_hunks = 0; sec_binary = 0; sec_deleted = 0
    cur_file = ""; oldf = ""; newf = ""
}
{
    line = $0
    # --- inside a hunk: the DECLARED COUNTS decide, never the text ----------
    if (old_rem > 0 || new_rem > 0) {
        c = substr(line, 1, 1)
        if (c == "-" && old_rem > 0) {
            old_rem--
            f = (newf != "" && newf != "/dev/null") ? newf : ((cur_file != "") ? cur_file : oldf)
            if (f == "") f = "(unknown)"
            files[f] = 1
            n++
            body = substr(line, 2)
            # The two forms `^-[^-]` cannot see, counted so the report can say
            # how much the retired check would have missed on THIS diff.
            if (body == "" || substr(body, 1, 1) == "-") blind++
            printf "L\t%s\n", body
            next
        }
        if (c == "+" && new_rem > 0) { new_rem--; next }
        # A stripped-trailing-whitespace context line arrives EMPTY rather than
        # as a single space; both are context. A DELETED blank line is "-", one
        # character, so the two do not collide.
        if ((c == " " || line == "") && old_rem > 0 && new_rem > 0) { old_rem--; new_rem--; next }
        if (c == "\\") { next }            # "\ No newline at end of file"
        # Everything else is a hunk that does not match its own header - too few
        # lines, too many of one kind, or a body line after the counts are spent.
        # UNDERFLOW IS AS WRONG AS OVERFLOW and the end-of-input check cannot see
        # it, because the remainders are already zero.
        malformed++
        old_rem = 0; new_rem = 0
    }
    # --- outside a hunk: structure only ------------------------------------
    if (substr(line, 1, 3) == "@@@" ) { combined++; next }
    if (substr(line, 1, 3) == "@@ ") {
        split(line, parts, " ")
        olds = parts[2]; sub(/^-/, "", olds)
        news = parts[3]; sub(/^\+/, "", news)
        old_rem = hunk_count(olds); new_rem = hunk_count(news)
        hunks++; sec_hunks = 1
        next
    }
    if (line ~ /^diff --git /) {
        close_section()
        split(line, parts, " ")
        cur_file = strip(parts[4])
        if (cur_file == "") cur_file = strip(parts[3])
        headers++
        next
    }
    if (line ~ /^--- /) {
        # A plain `diff -u` patch has no `diff --git`, so the `---` line is what
        # opens the section. After a `diff --git` the section is already open.
        if (sec_headers || sec_hunks || sec_binary) close_section()
        oldf = strip(substr(line, 5)); sec_headers = 1; headers++
        next
    }
    if (line ~ /^\+\+\+ /) {
        newf = strip(substr(line, 5)); sec_headers = 1; headers++
        if (substr(line, 5) == "/dev/null") sec_deleted = 1
        next
    }
    if (line ~ /^deleted file mode /) { sec_deleted = 1; next }
    # BOTH BINARY REPRESENTATIONS. `Binary files ... differ` is the default;
    # `git diff --binary` emits `GIT binary patch` instead, and keying on the
    # first alone reported a deleted binary as `deleted: 0` and exited CLEAN.
    if (line ~ /^Binary files / || line ~ /^GIT binary patch/) {
        binary++; sec_binary = 1
        if (line ~ / and \/dev\/null differ$/) sec_deleted = 1
        next
    }
    if (line ~ /^[^ ]/ && line !~ /^$/) unrecognised++
}
END {
    # A hunk left OPEN at end of input is the same defect as one interrupted by
    # a header, and only this branch sees it: a truncated patch simply runs out
    # of lines, so nothing downstream ever contradicts the declared counts.
    if (old_rem > 0 || new_rem > 0) malformed++
    close_section()
    printf "N\t%d\n", n + 0
    printf "B\t%d\n", blind + 0
    printf "F\t%d\n", length(files)
    printf "H\t%d\n", hunks + 0
    printf "D\t%d\n", headers + 0
    printf "Y\t%d\n", binary + 0
    printf "Z\t%d\n", bin_del + 0
    printf "U\t%d\n", unrecognised + 0
    printf "M\t%d\n", malformed + 0
    printf "I\t%d\n", incomplete + 0
    printf "C\t%d\n", combined + 0
}
')"

field() { printf '%s\n' "$PARSED" | awk -F'\t' -v k="$1" '$1==k{print $2}'; }
LINES="$(field N)"
BLIND="$(field B)"
FILES="$(field F)"
HUNKS="$(field H)"
HEADERS="$(field D)"
BINARY="$(field Y)"
BIN_DEL="$(field Z)"
UNREC="$(field U)"
MALFORMED="$(field M)"
INCOMPLETE="$(field I)"
COMBINED="$(field C)"

# COULD WE LOOK AT ALL? A non-empty input with no hunk, no header and no binary
# notice is not a diff we parsed - it is a diff we failed to recognise, and a
# zero over it is a claim about nothing.
if [ "$GIT_EMPTY" -eq 0 ] && [ "$HUNKS" -eq 0 ] && [ "$HEADERS" -eq 0 ] && [ "$BINARY" -eq 0 ]; then
    unknown "input carries no hunk, no file header and no binary notice ($UNREC unrecognised line(s)) - this is not a unified diff"
fi
if [ "$MALFORMED" -gt 0 ]; then
    unknown "a hunk does not match its own header ($MALFORMED time(s)) - the input is truncated or malformed"
fi
# COVERAGE IS PER FILE SECTION, not per input. Accepting the whole input because
# SOMETHING in it parsed is how one valid patch masks an unreadable neighbour -
# under --root especially, where several patches are concatenated.
if [ "$INCOMPLETE" -gt 0 ]; then
    unknown "$INCOMPLETE file section(s) carry headers but no hunk and no binary notice - their bodies were never read"
fi
if [ "$COMBINED" -gt 0 ]; then
    unknown "$COMBINED combined-diff hunk(s) (\`@@@\`, from a merge) - this parser does not read that format, and a zero over it would be a claim about nothing"
fi

echo "DELETION_ACCOUNTING_SOURCE: $SOURCE"
echo "DELETION_ACCOUNTING_FILES: $FILES"
echo "DELETION_ACCOUNTING_LINES: $LINES"
echo "DELETION_ACCOUNTING_BLINDSPOT: $BLIND"
# STATE THE UNEXAMINED POPULATION ON EVERY RUN. A binary file has no lines to
# count, so a line count says nothing about it either way; printing the number
# is what keeps the clean verdict from claiming more than it examined.
echo "DELETION_ACCOUNTING_BINARY: $BINARY (deleted: $BIN_DEL)"

if [ "$LINES" -eq 0 ] && [ "$BIN_DEL" -eq 0 ]; then
    echo "$SELF: ok - 0 deleted line(s) across $HUNKS hunk(s) in $HEADERS header line(s) (source=$SOURCE); $BINARY binary file(s) carry no lines to count"
    exit 0
fi

echo "DELETION_ACCOUNTING_FINDING: $LINES deleted line(s) across $FILES file(s)"
echo "  Confirm every one is yours. A file count larger than the set you edited is"
echo "  the signature of a base that moved under a 'git reset --soft <moving ref>'."
if [ "$BIN_DEL" -gt 0 ]; then
    echo "  $BIN_DEL binary file(s) are DELETED outright; they carry no lines, so they appear in the file count only."
fi
if [ "$BLIND" -gt 0 ]; then
    echo "  $BLIND of them are invisible to the retired \`^-[^-]\` form (blank lines, markdown bullets)."
fi
if [ "$TOP" -gt 0 ] && [ "$LINES" -gt 0 ]; then
    echo "  Census (count x deleted line), most repeated first:"
    # MULTIPLICITY IS REPORTED, NEVER INTERPRETED. The retired companion
    # heuristic "every deletion appears exactly twice" would have fired on 63
    # distinct lines here with zero real findings - measured multiplicities were
    # 1x/2x/3x/4x/6x/24x. A multiplicity is a finding only against the KNOWN
    # FAN-OUT of the source file it came from, and that map has to be derived.
    printf '%s\n' "$PARSED" \
        | awk '/^L\t/{ sub(/^L\t/, ""); print }' \
        | sort | uniq -c | sort -rn | head -n "$TOP" \
        | sed 's/^/    /'
fi
exit 1
