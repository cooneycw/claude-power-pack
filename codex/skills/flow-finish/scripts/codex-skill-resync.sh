#!/usr/bin/env bash
# codex-skill-resync.sh - re-sync the generated Codex mirrors when they have
# drifted, and say WHAT drifted (issue #1136).
#
#: NEGATIVE-CONTROL: controls/codex-skill-resync
#
# CONTRACT (last line)
#   CODEX_RESYNC: current | resynced | unavailable | error
#     current      exit 0  the mirrors already match their sources
#     unavailable  exit 0  no codex-skill-sync.py here - not a CPP checkout
#     resynced     exit 3  drift was found, NAMED, and repaired - VERIFIED by a
#                          second --check, because a successful --write is not
#                          the same fact as a repaired tree
#     error        exit 2  the sync script failed, or --check still fails after
#                          a successful --write (not drift it can repair)
#
# `resynced` CARRIES ITS OWN NON-ZERO CODE, and the two rules in this repo
# point opposite ways here, so the choice is recorded rather than assumed.
# #674 says a new verdict must never become a new exit code, because a
# `set -euo pipefail` caller aborts on one; #1027 says each verdict needs its
# own code, because a caller reading `$?` cannot otherwise tell what happened.
# #1027 wins: this helper's verdict is READ AS EVIDENCE - it is an ADR 0008
# census instrument, and its registered control must be able to tell "found
# drift" from "found none" by exit code, which is the only channel that
# framework scores. The #674 hazard is answered by the call sites rather than
# by flattening the contract: all three invoke this BARE, inside blocks that
# set no `-e`, and `resynced` means A REPAIR SUCCEEDED - a caller that treats
# it as failure has misread it. That is stated here because the next person to
# wrap this in `set -e` will need it.
#
# `current` and `unavailable` DO share exit 0, and that is not the same
# compromise: both mean "nothing to do here", which is the only thing a caller
# branches on. The contract line separates them for a reader, because "I
# checked and they match" and "there is nothing here to check" are different
# facts and only one is evidence about the mirrors.
#
# ---------------------------------------------------------------------------
# WHAT THIS REPLACES, AND WHY THE OLD SHAPE COULD NOT WORK
# ---------------------------------------------------------------------------
# Three copies of one condition decided whether to re-sync:
#
#     git diff --name-only ORIG_HEAD..HEAD | grep -q '^\.claude/commands/.*\.md$'
#
# at `flow/auto.md` Step 6 and Step 7, and at `flow/finish.md`. Its premise is
# that the generated surface changes only when a COMMAND DOCUMENT changes.
# It does not: `codex-skill-sync.py` also bundles repository docs into the
# skills, so an edit to a bundled doc drifts the mirror while touching no
# command document at all - the grep finds nothing and the guard stays silent.
#
# Measured twice in two hours on 2026-09-20, by two sessions on two documents
# (`docs/decisions/0008-...md` under #1126, `docs/agents/issue-contract.md`
# under #1133). Each cost a full lint-plus-5,100-test gate cycle and a re-gate.
# A guard that is silent and a guard with nothing to do produce identical
# output, so its blindness was invisible at the moment it mattered.
#
# THE POPULATION IS DERIVED, NOT GUESSED. The fix is not a wider glob - that is
# a hardcoded universe again, one entry longer. `codex-skill-sync.py --check`
# compares the ACTUAL generated output against the ACTUAL sources using the
# same generator `--write` uses, so it answers the question directly instead of
# predicting it from a path pattern. Cost measured on this tree: 0.11s clean.
# The grep it replaces cost 0.00s and two gate cycles.
#
# ONE HELPER, THREE CALL SITES. Three copies of a condition is how the same
# wrong condition reached three places; editing three copies to say something
# better leaves a fourth waiting to be pasted. The call sites now invoke this
# bare (#581), and `tests/test_codex_skill_resync.py` fails if the old
# condition reappears anywhere under `.claude/commands/`.
#
# ---------------------------------------------------------------------------
# WHY IT REPORTS BEFORE IT REPAIRS
# ---------------------------------------------------------------------------
# Running `--write` unconditionally was considered and rejected (issue #1136,
# orchestrator ruling). It is idempotent, costs 0.12s, and a guard that does
# not exist cannot be blind - a real argument. What it loses is the reason this
# blindness survived: silent repair makes drift never matter, therefore never
# noticed. Two consequences, either sufficient. Regenerated mirrors would land
# in an author's commit as a diff they neither made nor read, which is wrong
# exactly when the generator's own scope has changed and nobody is positioned
# to see it. And the sync script's SCOPE becomes unobservable - an author never
# learns that editing `docs/agents/issue-contract.md` reached five Codex
# skills. So drift is NAMED in the run's output, then repaired.
#
# Usage:
#   codex-skill-resync.sh [--quiet]
#
# Environment:
#   CODEX_SKILL_SYNC   path to codex-skill-sync.py. Defaults to the copy beside
#                      this script. A test seam, and the one input that decides
#                      this helper's verdict - which is the point: the decision
#                      comes from what the sync script reports, never from a
#                      path pattern this file would have to keep in step.

set -u

QUIET=0
for arg in "$@"; do
    case "$arg" in
        --quiet) QUIET=1 ;;
        -h|--help)
            sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "codex-skill-resync: unknown argument: $arg" >&2; exit 2 ;;
    esac
done

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC="${CODEX_SKILL_SYNC:-$SELF_DIR/codex-skill-sync.py}"

# FAIL-OPEN, exactly as the `[ -x scripts/codex-skill-sync.py ]` guard it
# replaces did: /flow:auto and /flow:finish run in other repositories too, and
# a missing sync script there means there is no Codex surface to keep, not that
# anything is wrong. `unavailable` is its own word rather than `current` -
# "there is nothing here to check" and "I checked and it matches" are different
# facts, and only one of them is evidence about the mirrors.
if [ ! -x "$SYNC" ]; then
    [ "$QUIET" -eq 1 ] || echo "codex-skill-resync: no codex-skill-sync.py at '$SYNC' - not a CPP checkout; nothing to re-sync." >&2
    echo "CODEX_RESYNC: unavailable"
    exit 0
fi

CHECK_OUT="$("$SYNC" --check 2>&1)"
CHECK_RC=$?

if [ "$CHECK_RC" -eq 0 ]; then
    echo "CODEX_RESYNC: current"
    exit 0
fi

# NAME WHAT DRIFTED BEFORE REPAIRING IT - and relay the generator's output
# WHOLE, never a filtered list of marker prefixes (counter-model review,
# #1136). The first cut passed it through `grep -E '^(DRIFT|STALE|ORPHAN):'`,
# which is a hardcoded universe of markers - this issue's own defect class,
# inside its own fix. The generator emits four: `DRIFT:`, `MISSING:`,
# `STALE:` and `ORPHAN skill:`. That filter dropped `MISSING:` entirely and
# `ORPHAN skill:` too, since the colon is not where the pattern expected it -
# so adding or removing a bundled file produced the generic message and named
# nothing, breaking the promise this helper exists to keep. Relaying
# everything cannot go stale when the generator gains a fifth marker.
[ "$QUIET" -eq 1 ] || {
    printf '%s\n' "$CHECK_OUT" >&2
    echo "codex-skill-resync: the generated Codex mirrors are out of date - re-syncing." >&2
    echo "  A bundled doc can do this without any command document changing; that is issue #1136." >&2
}

WRITE_OUT="$("$SYNC" --write 2>&1)"
if [ $? -ne 0 ]; then
    printf '%s\n' "$WRITE_OUT" >&2
    echo "codex-skill-resync: codex-skill-sync.py --write FAILED; the mirrors are still stale." >&2
    echo "CODEX_RESYNC: error"
    exit 2
fi

# A SUCCESSFUL WRITE IS NOT A REPAIRED TREE (counter-model review, #1136).
# `--check` exits 1 for conditions `--write` does not fix - an UNPACKAGED
# command or family, for instance - and `--write` exits 0 having ignored it.
# Reporting `resynced` there would claim a repair that did not happen, which is
# the same false-success shape as the verdict this helper replaced. So the
# repair is VERIFIED rather than assumed, and the remaining diagnostics are the
# ones a reader needs.
RECHECK_OUT="$("$SYNC" --check 2>&1)"
if [ $? -ne 0 ]; then
    printf '%s\n' "$RECHECK_OUT" >&2
    echo "codex-skill-resync: --write succeeded and --check STILL fails; this is not drift the" >&2
    echo "  generator can repair (an unpackaged command or family reports the same way)." >&2
    echo "CODEX_RESYNC: error"
    exit 2
fi

echo "CODEX_RESYNC: resynced"
exit 3
