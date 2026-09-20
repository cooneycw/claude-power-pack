#!/bin/sh
# Stands in for codex-skill-sync.py: the mirrors ARE stale. It supplies the
# helper's INPUT - what the generator reports - never the helper's verdict.
#
# STATELESS, AND THAT IS A CORRECTION (counter-model review pass 2, #1136).
# An earlier version kept a marker in $TMPDIR so --check could pass after
# --write, modelling a real generator and letting this case end in `resynced`.
# It raced: the control runner gives no per-run isolation, so two runs in two
# worktrees - which is the ordinary shape of this wave - shared one path, and
# whichever wrote first had its marker consumed by the other. A fixture whose
# verdict depends on who else is running is not a fixture.
#
# So this case ends in `error` instead: the generator reports drift and its
# --write fails, which needs no state at all. What the case demonstrates is
# unchanged and is the whole point - on a bundled-doc edit with no command
# document in it, the gate reports that the mirrors are NOT current, and the
# vendored anchor reports `current` and stays silent.
#
# The repair path (`resynced`) is pinned in tests/test_codex_skill_resync.py,
# where pytest's tmp_path gives every run its own directory. A committed
# fixture cannot model a stateful generator without a shared side channel, and
# a shared side channel is the race above.
case "$1" in
    --check)
        echo "DRIFT: codex/skills/flow-auto/docs/agents/issue-contract.md differs from generated source"
        echo "DRIFT: codex/skills/flow-finish/docs/agents/issue-contract.md differs from generated source"
        exit 1
        ;;
    --write)
        echo "codex-skill-sync: could not write codex/skills/ (read-only)" >&2
        exit 1
        ;;
    *) exit 2 ;;
esac
