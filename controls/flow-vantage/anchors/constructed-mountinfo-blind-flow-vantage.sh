#!/usr/bin/env bash
# CONSTRUCTED anchor for controls/flow-vantage (issue #959).
#
# `scripts/flow-vantage.sh` is new, so it has NO blind ancestor to vendor - the
# usual `git show <pre-fix sha>:<gate>` anchor does not exist. This
# reconstructs a check that was REALLY RECOMMENDED rather than an earlier
# revision of a script: `flow/register.md` proposed establishing vantage from
# `~/.claude/sessions/`, and issue #958 measured both candidate readings of
# that directory and found them blind. This vendors the mount-shaped one.
#
# THE BLINDNESS, AS MEASURED (#958, harness 2.1.266):
#
#   | Signal                                          | Host      | Container |
#   |-------------------------------------------------|-----------|-----------|
#   | `~/.claude/sessions/` in `/proc/self/mountinfo`  | 0 matches | no        |
#
# The directory is container-PRIVATE, not a bind mount, so it appears in the
# mount table on NEITHER side. A check built on it therefore answers `host`
# everywhere - including inside a container, which is the dangerous direction:
# a containerised session told `host` routes to lane 1, which returns success
# and delivers to a population holding no fleet peer.
#
# WHY THE OTHER MEASURED BLINDNESS IS NOT THE ANCHOR. #959 suggested a
# record-COUNT variant ("one record = container"). It cannot be this control's
# anchor, and the reason is a property of the framework rather than a
# preference: a record-count check answers `container` on a LONE HOST SESSION,
# so it would DISAGREE with the real gate on this control's known-GOOD input
# and score INERT ("differs for reasons beyond the blindness under test"). It
# is pinned instead as a behavioural invariant in
# `tests/test_flow_vantage.py::test_the_verdict_does_not_move_with_the_record_count`
# - the verdict must not move when the record count does. Two blindnesses, two
# instruments, and neither is left unproven.
#
# THE MOUNT TABLE IS READ FROM THE FIXTURE, NEVER FROM /proc. Reading the live
# `/proc/self/mountinfo` would make this anchor's blindness depend on ambient
# host state - the counter-model finding recorded against
# `controls/flow-driver-retirement-check`'s anchor, where an unpinned roster
# path could have silently scored that control INERT. The committed
# `proc-mountinfo` in each case is what this reads.
#
# It emits the same three contract lines as the real gate, because a control
# compares OUTPUT as well as exit code (#946): an anchor that printed something
# else would be scored `UNSIGNALLED` - "cannot be confirmed to have missed it" -
# rather than blind.

set -u

MOUNTINFO=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --fixture)
      [ "$#" -ge 2 ] || { echo "anchor: --fixture requires a directory" >&2; exit 2; }
      MOUNTINFO="$2/proc-mountinfo"
      shift
      ;;
    --fixture=*) MOUNTINFO="${1#--fixture=}/proc-mountinfo" ;;
    --quiet) : ;;
    *) echo "anchor: unknown argument '$1'" >&2; exit 2 ;;
  esac
  shift
done

# The blind reading, exactly as register.md recommended it: if the session
# discovery directory is a mount, this must be a container; otherwise it is the
# host. It is never a mount, so this always says host.
if [ -n "$MOUNTINFO" ] && [ -f "$MOUNTINFO" ] && grep -q 'claude/sessions' "$MOUNTINFO"; then
  echo "FLOW_VANTAGE_BASIS: mountinfo(claude/sessions is a mount: container)"
  echo "FLOW_VANTAGE_SOURCE: measured"
  echo "FLOW_VANTAGE: container"
  exit 3
fi

echo "FLOW_VANTAGE_BASIS: mountinfo(claude/sessions not a mount: host)"
echo "FLOW_VANTAGE_SOURCE: measured"
echo "FLOW_VANTAGE: host"
exit 0
