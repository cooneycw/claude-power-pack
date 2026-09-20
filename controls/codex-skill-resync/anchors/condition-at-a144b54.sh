#!/usr/bin/env bash
# SYNTHETIC anchor for controls/codex-skill-resync (issue #1136).
#
# There is no historical FILE to vendor: the blind condition never lived in a
# script. It was three inline copies of one shell line inside markdown command
# documents -
#
#     if [ -x scripts/codex-skill-sync.py ] && \
#        git diff --name-only ORIG_HEAD..HEAD | grep -q '^\.claude/commands/.*\.md$'; then
#         python3 scripts/codex-skill-sync.py --write || true
#     fi
#
# at .claude/commands/flow/auto.md:698 (Step 6), auto.md:1199 (Step 7) and
# .claude/commands/flow/finish.md:65, as they stood at a144b54. This lifts that
# condition into an executable unchanged in substance, so the control can run
# it: same input (the list of changed paths), same pattern, same decision.
#
# The one adaptation: the changed-path list is read from a file rather than
# from `git diff --name-only ORIG_HEAD..HEAD`. Running real git would make the
# anchor's answer depend on the repository state the control happens to run in
# - ambient state deciding a control's verdict, the counter-model finding
# recorded against controls/flow-driver-retirement-check. The list is what the
# condition consumed; where it came from is not what is under test.
#
# WHAT IT DEMONSTRATES: on a bundled-doc edit that touches no command document,
# it finds nothing and reports `current` - the mirrors stay stale and the run
# says nothing. That is the blindness, and it cost two full gate cycles in two
# hours on 2026-09-20.
#
# It is NOT a constant function: given a changed-path list containing a command
# document it DOES fire. A committed case cannot show that - the current helper
# would also re-sync there, so the anchor would CATCH the input and score the
# control INERT - so it is pinned in
# tests/test_codex_skill_resync.py::test_the_anchor_is_blind_by_input_not_by_being_a_stub.

set -u

PATHS_FILE="${CODEX_RESYNC_CHANGED_PATHS:-}"
changed=""
[ -n "$PATHS_FILE" ] && [ -f "$PATHS_FILE" ] && changed="$(cat "$PATHS_FILE")"

if printf '%s\n' "$changed" | grep -q '^\.claude/commands/.*\.md$'; then
    echo "CODEX_RESYNC: resynced"
    exit 3
fi

echo "CODEX_RESYNC: current"
exit 0
