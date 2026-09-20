#!/bin/sh
# The SECOND source class (#1136, third occurrence). codex-skill-sync.py
# bundles repository SCRIPTS into each skill as well as repository docs, and
# the retired grep '^\.claude/commands/.*\.md$' intersects neither. worker-H
# hit this on 2026-09-20 with six of nine drifting mirrors being
# codex/skills/*/scripts/ copies of hook-permission-census.sh,
# stash-worktree-guard.sh and codex-skill-sync.py.
#
# Verified independently on this tree before this case was written: appending
# one line to scripts/stash-worktree-guard.sh drifts three mirrors, and the old
# condition is SILENT on that diff.
#
# Stateless for the same reason as the sibling case - see its header and the
# manifest's `limits`.
case "$1" in
    --check)
        echo "DRIFT: codex/skills/flow-auto/scripts/stash-worktree-guard.sh differs from generated source"
        echo "DRIFT: codex/skills/flow-repair/scripts/stash-worktree-guard.sh differs from generated source"
        echo "DRIFT: codex/skills/flow-start/scripts/stash-worktree-guard.sh differs from generated source"
        exit 1
        ;;
    --write)
        echo "codex-skill-sync: could not write codex/skills/ (read-only)" >&2
        exit 1
        ;;
    *) exit 2 ;;
esac
