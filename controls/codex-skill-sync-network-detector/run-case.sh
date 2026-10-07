#!/bin/sh
# Case runner for controls/codex-skill-sync-network-detector (issue #1408,
# bullet 2). Imports the gate module and calls `calls_network()` directly
# with the case's fixture file as the sole bundled helper - the detector
# operates on BUNDLED SCRIPT CONTENT, never on a command document's body
# (that body only decides WHICH scripts get bundled), so driving it through
# the full generate_skill() pipeline would need a real SCRIPTS_ROOT entry
# this control does not want to depend on.
#
# ONE SHARED PREDICATE for both cases: "finding" = calls_network() answers
# False on this fixture.
#   - bad-docstring-argv-false-positive: a known FALSE-POSITIVE shape (an
#     argv-shaped list inside a docstring). The FIXED gate correctly says
#     False (no real call) - a finding. The pre-fix anchor said True
#     (wrongly flagged) - no finding, i.e. blind.
#   - good-real-gh-call: a REAL network call, which both the fixed gate and
#     the anchor correctly say True about - no finding either way, which is
#     exactly good_exit and needs no anchor-blindness check (anchors are
#     only exercised against BAD cases).
set -u
case_dir="$1"
gate="$2"

helper="$(find "$case_dir" -maxdepth 1 -name 'helper.*' | head -1)"
if [ -z "$helper" ] || [ ! -s "$helper" ]; then
    echo "CODEX_SKILL_SYNC_NETWORK_CONTROL: unavailable - no helper.* fixture found" >&2
    exit 3
fi
if [ ! -r "$gate" ] || ! command -v python3 >/dev/null 2>&1; then
    echo "CODEX_SKILL_SYNC_NETWORK_CONTROL: unavailable - the gate or python3 is not present" >&2
    exit 3
fi

python3 - "$gate" "$helper" <<'PYEOF'
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

gate_path, helper_path = sys.argv[1], sys.argv[2]
spec = spec_from_file_location("codex_skill_sync_control", gate_path)
if spec is None or spec.loader is None:
    print("CODEX_SKILL_SYNC_NETWORK_CONTROL: unavailable - could not load gate module", file=sys.stderr)
    sys.exit(3)
mod = module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_NETWORK_CONTROL: unavailable - gate import failed: {exc}", file=sys.stderr)
    sys.exit(3)

helper = Path(helper_path)
rel = f"scripts/{helper.name}"
try:
    result = mod.calls_network({rel: helper.read_text()})
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_NETWORK_CONTROL: unavailable - calls_network raised: {exc}", file=sys.stderr)
    sys.exit(3)

if result is False:
    print("CODEX_SKILL_SYNC_NETWORK_CONTROL: finding - calls_network correctly answered False")
    sys.exit(1)
if result is True:
    print("CODEX_SKILL_SYNC_NETWORK_CONTROL: no finding - calls_network answered True")
    sys.exit(0)
print(
    f"CODEX_SKILL_SYNC_NETWORK_CONTROL: unavailable - calls_network returned a non-bool: {result!r}",
    file=sys.stderr,
)
sys.exit(3)
PYEOF
