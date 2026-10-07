#!/bin/sh
# Case runner for controls/flow-wave-registry-malformed (issue #1403).
#
# A SEPARATE registration from controls/flow-wave-registry, same gate: that
# one's detect_signal is about a FILE-LANE overlap warning, a report-only
# arm where `list` always exits 0. This axis is about `list` REFUSING a
# registry it cannot parse - a different signal, for a different reason,
# and the harness supports several registrations on one gate (#986) for
# exactly this: widening one detect_signal into an alternation would let
# either case pass for the other's reason.
#
# THREE CHANNELS, not the exit code alone: a crash under some OTHER cause
# (a changed CLI, a missing binary) must not read as "caught the corrupt
# registry" just because it also happens to exit non-zero. The gate's own
# FLOW_WAVE: verdict line and the specific message text both have to agree
# with what THIS fix actually does before this control calls it a finding.
set -u
case_dir="$1"
gate="$2"

T=$(mktemp -d) || { echo "FLOW_WAVE_REGISTRY_MALFORMED_CONTROL: unavailable - no tmpdir" >&2; exit 3; }
mkdir -p "$T/reg" || { rm -rf "$T"; exit 3; }
cp "$case_dir/registry.json" "$T/reg/registry.json" || { rm -rf "$T"; exit 3; }

out=$(env FLOW_WAVE_REGISTRY_DIR="$T/reg" bash "$gate" list --wave cpp 2>&1)
status=$?
rm -rf "$T"

verdict=$(printf '%s\n' "$out" | sed -n 's/^FLOW_WAVE: //p' | tail -1)

case "$status:$verdict" in
  0:listed)
    exit 0 ;;
  3:error)
    if printf '%s\n' "$out" | grep -q 'not valid content'; then
      echo "FLOW_WAVE_REGISTRY_MALFORMED_CONTROL: finding - list refused the corrupt registry rather than reporting it empty"
      exit 1
    fi
    echo "FLOW_WAVE_REGISTRY_MALFORMED_CONTROL: unavailable - list errored for a reason other than this axis" >&2
    printf '%s\n' "$out" >&2
    exit 3
    ;;
  *)
    echo "FLOW_WAVE_REGISTRY_MALFORMED_CONTROL: unavailable - unexpected status:$status verdict:${verdict:-<none>}" >&2
    printf '%s\n' "$out" >&2
    exit 3
    ;;
esac
