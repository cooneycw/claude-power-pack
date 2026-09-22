#!/usr/bin/env bash
# step3-record-guard.sh - a PreToolUse hook: refuse an edit in a flow worktree
# that carries no approved-plan record (issue #1083).
#
#: NEGATIVE-CONTROL: controls/step3-record-guard
#
# WHAT THIS IS. #775 says no flag, trailer, marker, environment variable or
# governance tier may let /flow:auto Step 3 proceed without a reviewer approving
# the plan, and that none may be added. It is one of the most forcefully stated
# rules in this repository and, until this file, NOTHING CHECKED IT. The strength
# of prose is not evidence about the strength of a control.
#
# WHAT THIS IS NOT, and this wording is load-bearing rather than modest:
#   IT ENFORCES THE PRESENCE OF AN ARTIFACT, NOT THE OCCURRENCE OF AN APPROVAL,
#   AND ONLY ON THE TOOL PATHS THE HOOK IS MATCHED AGAINST.
# It does NOT enforce #775. It cannot: it sees a tool call, and "was Step 3
# approved" is a fact about a RUN. Anything able to write the record can write
# itself an approval. Do not describe this as enforcing #775 anywhere.
#
# THE COVERAGE SPLIT, stated separately for two audiences because it differs by
# an order of magnitude between them:
#
#   IN THIS FLEET, coverage is NEAR ZERO. These sessions are steered to make file
#   changes through Bash - "with sed, heredocs, or short scripts, rather than
#   using the dedicated Read, Edit, or Write tools" - so the path this hook
#   cannot see is the INSTRUCTED DEFAULT, not an escape from it. Measured: every
#   plan record written across three runs of one session used `cat > ... <<EOF`
#   and zero used Write. A reader here MUST NOT take this hook's silence as
#   evidence that no edit happened. controls/step3-record-guard commits that
#   blindness as a CASE rather than asserting it here, so that if the steer or
#   the matcher ever changes, the case changes and the change is the notice.
#
#   WHERE IT SHIPS, coverage is genuinely useful. Bash-first steering is a
#   property of how this fleet is operated, not of the hook mechanism. A
#   consumer whose agents use Write/Edit normally gets a real floor.
#
# REFUSAL IS REFUSAL, NOT A DEFAULT (#1014, ADR 0009). A state this cannot read
# is REFUSED and said. There is deliberately no permissive fallback to keep runs
# moving: a hook that fails open is worse than no hook, because the prose it
# replaces at least made no claim to be deterministic.
#
# Input: PreToolUse JSON on stdin. Output: a block message on stdout and a
# non-zero exit to refuse; silence and 0 to allow.
set -uo pipefail

ALLOW=0
BLOCK=2

# EVERY REFUSAL GOES TO STDERR (counter-model review, codex, MEDIUM). For an
# exit-2 command hook the harness uses STDERR as the blocking reason; a message
# on stdout still blocks the edit but the explanation and the recovery route -
# the whole reason this refusal is written out at all - never reach the caller.
# A block nobody can act on is a block people route around.
_refuse() { printf '%s\n' "$@" >&2; exit "$BLOCK"; }

INPUT=$(cat 2>/dev/null || true)

# THE RECORD'S OWN PATH IS THE ONLY EXEMPTION. The record is written BY an edit,
# so a guard without it blocks the write that would unblock it and every run
# deadlocks on its first edit.
#
# CANNOT-DETERMINE IS REFUSAL, NOT ALLOWANCE, EVERYWHERE BELOW. Three paths used
# to fall through to ALLOW and all three were reproduced as fail-opens by the
# counter-model review: malformed JSON, an absent python3, and a broken git.
# #1083 calls fail-open the one non-negotiable thing, and a guard that fails open
# is worse than no guard because the prose it replaces made no claim to be
# deterministic.

command -v python3 >/dev/null 2>&1 || _refuse \
  "step3-record-guard: REFUSED - python3 is not available, so this hook cannot read" \
  "  the tool request and cannot tell an in-scope edit from an out-of-scope one." \
  "  Refusing rather than allowing: an inability to look is not a clean look."

PARSED=$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception as exc:
    print("ERR unreadable tool request: %s" % exc); raise SystemExit(0)
if not isinstance(d, dict):
    print("ERR tool request is not an object"); raise SystemExit(0)
tool = d.get("tool_name")
if not isinstance(tool, str) or not tool:
    print("ERR tool request carries no tool_name"); raise SystemExit(0)
ti = d.get("tool_input") or {}
target = ""
if isinstance(ti, dict):
    for k in ("file_path", "path", "notebook_path"):
        v = ti.get(k)
        if isinstance(v, str) and v:
            target = v
            break
print("OK\t%s\t%s" % (tool, target))
' 2>/dev/null)

case "$PARSED" in
    OK*) ;;
    ERR*) _refuse "step3-record-guard: REFUSED - ${PARSED#ERR }" \
            "  This hook could not read the tool request, so it cannot say whether the" \
            "  edit is in scope. Refusing rather than allowing." ;;
    *)   _refuse "step3-record-guard: REFUSED - the tool request could not be parsed at all." \
            "  Refusing rather than allowing: an inability to look is not a clean look." ;;
esac

TOOL=$(printf '%s' "$PARSED" | cut -f2)
TARGET=$(printf '%s' "$PARSED" | cut -f3)

# NOT AN EDIT TOOL: determined, and out of scope. This is the matched-paths
# bound, and it is why this hook's silence is not coverage.
case "$TOOL" in
    Write|Edit|NotebookEdit) ;;
    *) exit "$ALLOW" ;;
esac

# THE SUBJECT IS THE WORKTREE THE EDIT LANDS IN, NOT THE ONE THE HOOK RUNS IN
# (counter-model review, codex, HIGH). Resolving from the hook's cwd meant the
# verdict could describe a NEIGHBOUR: reproduced, an edit into a recordless
# worktree returned 0 when the hook ran from an approved one, and an unrelated
# edit could be refused because of a neighbouring checkout's state. That is the
# ownership question failing - a non-zero that cannot tell our thing from
# someone else's - on the guard's own subject.
#
# Resolved from the TARGET's nearest EXISTING parent, because the file itself
# does not exist yet: that is what a Write is.
if [ -n "$TARGET" ]; then
    probe=$TARGET
    while [ -n "$probe" ] && [ ! -d "$probe" ]; do
        parent=${probe%/*}
        [ "$parent" = "$probe" ] && break
        probe=${parent:-/}
    done
    [ -d "$probe" ] || probe=$PWD
else
    probe=$PWD
fi

# NOT A CHECKOUT vs GIT COULD NOT ANSWER, and the difference decides allow
# versus refuse. `--show-toplevel` exits 128 for BOTH "this is not a repository"
# and a fatal it could not recover from, so the exit code cannot separate them -
# my first attempt probed with `--is-inside-work-tree` and a broken GIT_DIR made
# BOTH calls fail, so "git could not answer" fell through to "not a repository"
# and ALLOWED. Reproduced with GIT_DIR=/nonexistent.
#
# git's own message is the only signal that distinguishes them, so it is read -
# under LC_ALL=C, because that message is translated and a localised git would
# otherwise land every edit in the refusing branch.
#
# THE BOUND ON THIS, stated rather than left: it keys on git's wording. If that
# wording changes, this classifies a genuine not-a-repository as unreadable and
# REFUSES - which is the safe direction, and loud rather than silent.
_git_err=$(LC_ALL=C git -C "$probe" rev-parse --show-toplevel 2>&1 >/dev/null)
TOPLEVEL=$(LC_ALL=C git -C "$probe" rev-parse --show-toplevel 2>/dev/null)
if [ -z "$TOPLEVEL" ]; then
    if ! command -v git >/dev/null 2>&1; then
        _refuse "step3-record-guard: REFUSED - git is not available, so this hook cannot" \
                "  tell whether the edit is in a flow worktree. Refusing rather than allowing."
    fi
    # MATCH THE GENUINE CASE SPECIFICALLY, NOT THE GENERAL PHRASE. Both failures
    # say "not a git repository" - measured:
    #   no repo here : fatal: not a git repository (or any of the parent directories): .git
    #   broken GIT_DIR: fatal: not a git repository: '/nonexistent'
    # so the general phrase matches BOTH and my first spelling allowed the
    # broken environment. The parenthetical is what only the genuine walk-up
    # failure produces, and matching it puts the fragility in the SAFE
    # direction: if git rewords this, an ordinary not-a-repository edit starts
    # REFUSING - loudly and visibly - rather than a hostile environment starting
    # to pass silently.
    case "$_git_err" in
        *"or any of the parent directories"*)
            exit "$ALLOW" ;;   # DETERMINED, and out of this guard's scope
        *)
            _refuse "step3-record-guard: REFUSED - the repository state could not be read for" \
                    "  $probe, so this hook cannot determine whether the edit is in scope." \
                    "  git said: ${_git_err:-<nothing>}" \
                    "  Refusing rather than allowing: an inability to look is not a clean look." ;;
    esac
fi

# `symbolic-ref --short`, NOT `rev-parse --abbrev-ref HEAD`. Both an UNBORN
# branch and a DETACHED head make rev-parse print the literal "HEAD", and they
# need OPPOSITE answers. UNBORN: the name IS readable here and an issue branch
# with no record is exactly this guard's subject, so REFUSE - reading it as "no
# branch" was a fail-open this guard's own control caught before it shipped.
# DETACHED: there is no branch, which is DETERMINED rather than unreadable, and
# refusing would block every edit in every detached checkout including CI.
BRANCH=$(git -C "$TOPLEVEL" symbolic-ref --short HEAD 2>/dev/null)
case "$BRANCH" in
    issue-[0-9]*) ;;
    *) exit "$ALLOW" ;;
esac
ISSUE=${BRANCH#issue-}
ISSUE=${ISSUE%%-*}

# THE EXEMPTION IS TWO EXACT PATHS UNDER THE RESOLVED ROOT, not a suffix
# (counter-model review, codex, MEDIUM). Suffix matching exempted lookalikes:
# `<worktree>/vendor/docs/flow-runs/issue-N.md` reproduced exit 0 with no
# approval record anywhere. Keyed on the ISSUE NUMBER as well as the root, so
# another run's record is not this run's bootstrap.
if [ -n "$TARGET" ]; then
    case $TARGET in
        /*) abs=$TARGET ;;
        *)  abs="$PWD/$TARGET" ;;
    esac
    for exempt in "$TOPLEVEL/docs/flow-runs/issue-$ISSUE.md" \
                  "$TOPLEVEL/docs/flow-runs/issue-$ISSUE.as-read.md"; do
        [ "$abs" = "$exempt" ] && exit "$ALLOW"
    done
fi

RECORD="$TOPLEVEL/docs/flow-runs/issue-$ISSUE.md"
if [ -f "$RECORD" ]; then
    if [ ! -r "$RECORD" ]; then
        _refuse "step3-record-guard: REFUSED - the approved-plan record for issue #$ISSUE" \
                "  exists but cannot be read: $RECORD" \
                "  Refusing rather than allowing: an unreadable record is not an approval."
    fi
    if grep -qE '^- Approval: +granted' "$RECORD" 2>/dev/null; then
        exit "$ALLOW"
    fi
    _refuse \
"step3-record-guard: REFUSED - the approved-plan record for issue #$ISSUE exists" \
"  but does not record an approval." \
"" \
"  $RECORD" \
"  carries no '- Approval:          granted' line, so this run cannot show that a" \
"  reviewer approved its plan." \
"" \
"  WHAT TO DO: complete /flow:auto Step 3 and have a reviewer approve the plan," \
"  then let Step 4 write the record. Do not hand-edit the approval line - the" \
"  record is evidence of a decision, and writing the line yourself records a" \
"  decision nobody made." \
"" \
"  THIS GUARD IS A FLOOR, NOT AN ENFORCEMENT OF #775. It checks that an artifact" \
"  is present; it cannot check that an approval happened."
fi

_refuse \
"step3-record-guard: REFUSED - no approved-plan record for issue #$ISSUE." \
"" \
"  expected: $RECORD" \
"" \
"  /flow:auto Step 3 is the plan-approval gate and it has no bypass: no flag, no" \
"  trailer, no environment variable, and no governance tier (issue #775). This" \
"  guard is the deterministic floor beneath that rule." \
"" \
"  WHAT TO DO: run /flow:auto Step 3 for issue #$ISSUE, have a reviewer approve" \
"  the plan, and let Step 4 write the record. The run then proceeds normally." \
"" \
"  THE ONE EXEMPTION: writes to docs/flow-runs/issue-$ISSUE.md and its .as-read.md" \
"  companion are always allowed. They have to be - the record is written by an" \
"  edit, so a guard with no exemption would block the write that unblocks it." \
"" \
"  THIS GUARD IS A FLOOR, NOT AN ENFORCEMENT OF #775. It checks that an artifact" \
"  is present; it cannot check that an approval happened, and it sees only the" \
"  tool paths it is matched against."
