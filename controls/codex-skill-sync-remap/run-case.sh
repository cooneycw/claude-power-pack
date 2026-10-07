#!/bin/sh
# Case runner for controls/codex-skill-sync-remap (issue #1408, bullet 4).
#
# codex-skill-sync.py has no --root override (its REPO_ROOT/SOURCE_ROOT/
# SCRIPTS_ROOT are module-level constants resolved from the gate's OWN file
# location), so this control imports the gate as a module and calls
# generate_skill() directly on a fixture command doc, exactly as
# tests/test_codex_skill_sync.py does - rather than inventing a second way
# to drive it.
#
# WHAT "FINDING" MEANS HERE, which is the opposite sense from most controls
# in this repository: the fix is a SILENT CORRECTION (no warning line), so
# "the gate noticed something wrong and said so" does not apply. Instead,
# "finding" means "the fix's signature behavior fired on this input" - the
# absolute path was rewritten to the relative form AND the target script was
# bundled. BOTH must agree, same two-channel discipline as the other
# #1401/#1403 adapters: a rewrite with no bundle, or a bundle with no
# rewrite, is a gate that ran and did not answer coherently, never a
# detection either way.
set -u
case_dir="$1"
gate="$2"

if [ ! -s "$case_dir/source.md" ]; then
    echo "CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - source.md is missing or empty" >&2
    exit 3
fi
if [ ! -r "$gate" ] || ! command -v python3 >/dev/null 2>&1; then
    echo "CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - the gate or python3 is not present" >&2
    exit 3
fi

python3 - "$gate" "$case_dir/source.md" <<'PYEOF'
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

gate_path, source_path = sys.argv[1], sys.argv[2]
spec = spec_from_file_location("codex_skill_sync_control", gate_path)
if spec is None or spec.loader is None:
    print("CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - could not load gate module", file=sys.stderr)
    sys.exit(3)
mod = module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:  # the gate itself failed to import - not a finding either way
    print(f"CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - gate import failed: {exc}", file=sys.stderr)
    sys.exit(3)

source_text = Path(source_path).read_text()
if "~/.claude/scripts/" not in source_text:
    # Nothing to remap at all - the GOOD case's own shape. Neither channel
    # applies, and checking them anyway would read a precondition that was
    # never true as a disagreement.
    print("CODEX_SKILL_SYNC_REMAP_CONTROL: no finding - fixture names no absolute path")
    sys.exit(0)

try:
    files = mod.generate_skill(Path(source_path), "flow", {})
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - generate_skill raised: {exc}", file=sys.stderr)
    sys.exit(3)

rendered = files.get("reference.md") or files.get("SKILL.md") or ""
remapped = "~/.claude/scripts/" not in rendered
bundled = "scripts/flow-finish-gate.sh" in files

if remapped and bundled:
    print("CODEX_SKILL_SYNC_REMAP_CONTROL: finding - the absolute path was remapped and bundled")
    sys.exit(1)
if (not remapped) and (not bundled):
    print("CODEX_SKILL_SYNC_REMAP_CONTROL: no finding - nothing was remapped or bundled")
    sys.exit(0)
print(
    f"CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - channels disagree "
    f"(remapped={remapped}, bundled={bundled})",
    file=sys.stderr,
)
sys.exit(3)
PYEOF
