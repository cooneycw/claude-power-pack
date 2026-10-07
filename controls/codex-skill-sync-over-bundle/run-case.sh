#!/bin/sh
# Case runner for controls/codex-skill-sync-over-bundle (issue #1408, bullet 3).
# Imports the gate module and calls `find_bundled_libs()` directly against the
# case's own fixture tree, with REPO_ROOT/SCRIPTS_ROOT monkeypatched to point
# at it - `find_bundled_libs` resolves every import against those two module
# globals, so a fixture tree laid out exactly like a real repository root
# (scripts/, lib/) needs no other wiring.
#
# ONE SHARED RULE drives both cases, read from two manifest files the fixture
# itself carries rather than hardcoded here:
#   required.txt - files the closure MUST contain (the real dependency); their
#                   absence means the gate failed to run at all, which is
#                   UNAVAILABLE, never a verdict about over-bundling.
#   noise.txt     - files the closure must NOT contain (present only in the
#                   bad fixture: TYPE_CHECKING-only and docstring-only names
#                   that resolve to real submodules but are never actually
#                   imported). Absent or empty for the good fixture, which has
#                   nothing of this shape to avoid.
#
# "finding" = every required file is present AND no noise file leaked in.
#   - bad-docstring-and-typecheck-overbundle: noise.txt is non-empty, so a
#     finding here means the fix correctly kept the TYPE_CHECKING block and
#     the docstring's usage example from pulling `unrelated1.py`/
#     `unrelated2.py` into the bundle - the exact shape that rglob'd all 29
#     files of lib/cicd/ for flow-check. The pre-fix anchor leaks both and
#     scores no finding (blind, as required).
#   - good-ordinary-package: noise.txt is absent, so the same rule reduces to
#     "required files all present" - confirming the fix does not swing the
#     other way into under-bundling an ordinary package. Both the fixed gate
#     and the anchor score a (non-)finding identically here; only the bad
#     case exercises anchor blindness, as elsewhere in this repository's
#     controls.
set -u
case_dir="$1"
gate="$2"

if [ ! -d "$case_dir/lib" ] || [ ! -f "$case_dir/scripts/entry.py" ]; then
    echo "CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: unavailable - fixture tree missing scripts/entry.py or lib/" >&2
    exit 3
fi
if [ ! -r "$gate" ] || ! command -v python3 >/dev/null 2>&1; then
    echo "CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: unavailable - the gate or python3 is not present" >&2
    exit 3
fi

required_file="$case_dir/required.txt"
noise_file="$case_dir/noise.txt"
[ -f "$required_file" ] || { echo "CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: unavailable - no required.txt in $case_dir" >&2; exit 3; }

python3 - "$gate" "$case_dir" "$required_file" "$noise_file" <<'PYEOF'
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

gate_path, case_dir, required_path, noise_path = sys.argv[1:5]
spec = spec_from_file_location("codex_skill_sync_control", gate_path)
if spec is None or spec.loader is None:
    print("CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: unavailable - could not load gate module", file=sys.stderr)
    sys.exit(3)
mod = module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: unavailable - gate import failed: {exc}", file=sys.stderr)
    sys.exit(3)

case_root = Path(case_dir).resolve()
mod.REPO_ROOT = case_root
mod.SCRIPTS_ROOT = case_root / "scripts"

required = [
    line.strip() for line in Path(required_path).read_text().splitlines() if line.strip()
]
noise_file_path = Path(noise_path)
noise = (
    [line.strip() for line in noise_file_path.read_text().splitlines() if line.strip()]
    if noise_file_path.is_file()
    else []
)

try:
    got = mod.find_bundled_libs(["entry.py"])
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: unavailable - find_bundled_libs raised: {exc}", file=sys.stderr)
    sys.exit(3)

got_paths = set(got)
missing_required = [r for r in required if r not in got_paths]
if missing_required:
    print(
        f"CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: unavailable - the real dependency "
        f"is missing from the closure, so over-bundling cannot be judged: {missing_required}",
        file=sys.stderr,
    )
    sys.exit(3)

leaked_noise = [n for n in noise if n in got_paths]
if leaked_noise:
    print(f"CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: no finding - over-bundled: {sorted(leaked_noise)}")
    sys.exit(0)

print(
    "CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: finding - closure is exactly the required set, no noise"
    if noise
    else "CODEX_SKILL_SYNC_OVER_BUNDLE_CONTROL: no finding - ordinary package, nothing to avoid"
)
sys.exit(1 if noise else 0)
PYEOF
