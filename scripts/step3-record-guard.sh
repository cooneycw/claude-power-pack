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

INPUT=$(cat 2>/dev/null || true)

# The ONLY exemption, and the block message names it below. The approved-plan
# record is written at Step 4, and writing it IS an edit - so a guard with no
# exemption blocks the write of the very record that would unblock it, and every
# run deadlocks on its first edit. One pattern, no others.
RECORD_GLOB='docs/flow-runs/issue-[0-9]*.md'

_field() {
    printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cur = d
for k in sys.argv[1].split("."):
    if isinstance(cur, dict) and k in cur:
        cur = cur[k]
    else:
        sys.exit(0)
print(cur if isinstance(cur, str) else json.dumps(cur))
' "$1" 2>/dev/null
}

TOOL=$(_field tool_name)
TARGET=$(_field tool_input.file_path)
[ -n "$TARGET" ] || TARGET=$(_field tool_input.path)

# Not an edit tool: nothing to say. This is the matched-paths bound above, and
# it is why this hook's silence is not coverage.
case "$TOOL" in
    Write|Edit|NotebookEdit) ;;
    *) exit "$ALLOW" ;;
esac

WT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$WT_ROOT" ]; then
    # Not a checkout at all - this guard has no subject here.
    exit "$ALLOW"
fi

# `symbolic-ref --short`, NOT `rev-parse --abbrev-ref HEAD`, AND THE REASON IS
# TWO STATES THAT `rev-parse` REPORTS WITH THE SAME WORD AND THAT NEED OPPOSITE
# ANSWERS. Both make `rev-parse --abbrev-ref HEAD` produce the literal "HEAD":
#
#   UNBORN branch (`git checkout -b` before the first commit). The branch EXISTS
#   and its name is readable - `symbolic-ref --short` returns it. A fresh flow
#   worktree can briefly be here. This state must REFUSE: an issue branch with no
#   record is exactly the subject of this guard, and reading it as "no branch"
#   is a FAIL-OPEN on the one behaviour #1083 calls non-negotiable. This guard's
#   own control caught that before it shipped.
#
#   DETACHED HEAD (CI checks out a SHA; every Woodpecker run is here). There is
#   no branch, `symbolic-ref` fails, and that is DETERMINED rather than
#   unreadable: there is no issue for this guard to have an opinion about. This
#   state must ALLOW. Refusing it would block every edit in every detached
#   checkout, CI included.
#
# So the difference between "unreadable, therefore refuse" and "determined,
# therefore allow" is invisible to `rev-parse` and visible to `symbolic-ref`.
# The issue's refuse-do-not-allow constraint is about the RECORD being
# unreadable; it is not a licence to refuse wherever a branch is absent.
BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null)
case "$BRANCH" in
    issue-[0-9]*) ;;
    # NOT A FLOW WORKTREE, and that is DETERMINED rather than unknown - a
    # detached HEAD or a differently-named branch has no issue for this guard to
    # have an opinion about. The issue's refuse-do-not-allow constraint is about
    # the RECORD being unreadable, not about this: refusing here would block
    # every edit in every detached checkout, CI included, for a state that is
    # known rather than indeterminate.
    *) exit "$ALLOW" ;;
esac
ISSUE=${BRANCH#issue-}
ISSUE=${ISSUE%%-*}

# THE EXEMPTION. Compared on the path's TAIL so it holds whether the tool sent an
# absolute or a repo-relative path.
case "$TARGET" in
    */docs/flow-runs/issue-"$ISSUE".md|docs/flow-runs/issue-"$ISSUE".md) exit "$ALLOW" ;;
    */docs/flow-runs/issue-"$ISSUE".as-read.md|docs/flow-runs/issue-"$ISSUE".as-read.md) exit "$ALLOW" ;;
esac

RECORD="$WT_ROOT/docs/flow-runs/issue-$ISSUE.md"
if [ -f "$RECORD" ]; then
    if grep -qE '^- Approval: +granted' "$RECORD" 2>/dev/null; then
        exit "$ALLOW"
    fi
    cat <<MSG
step3-record-guard: REFUSED - the approved-plan record for issue #$ISSUE exists
  but does not record an approval.

  $RECORD
  carries no '- Approval:          granted' line, so this run cannot show that a
  reviewer approved its plan.

  WHAT TO DO: complete /flow:auto Step 3 and have a reviewer approve the plan,
  then let Step 4 write the record. Do not hand-edit the approval line - the
  record is evidence of a decision, and writing the line yourself records a
  decision nobody made.

  THIS GUARD IS A FLOOR, NOT AN ENFORCEMENT OF #775. It checks that an artifact
  is present; it cannot check that an approval happened.
MSG
    exit "$BLOCK"
fi

cat <<MSG
step3-record-guard: REFUSED - no approved-plan record for issue #$ISSUE.

  expected: $RECORD

  /flow:auto Step 3 is the plan-approval gate and it has no bypass: no flag, no
  trailer, no environment variable, and no governance tier (issue #775). This
  guard is the deterministic floor beneath that rule.

  WHAT TO DO: run /flow:auto Step 3 for issue #$ISSUE, have a reviewer approve
  the plan, and let Step 4 write the record. The run then proceeds normally.

  THE ONE EXEMPTION: writes to docs/flow-runs/issue-$ISSUE.md and its .as-read.md
  companion are always allowed. They have to be - the record is written by an
  edit, so a guard with no exemption would block the write that unblocks it.

  THIS GUARD IS A FLOOR, NOT AN ENFORCEMENT OF #775. It checks that an artifact
  is present; it cannot check that an approval happened, and it sees only the
  tool paths it is matched against.
MSG
exit "$BLOCK"
