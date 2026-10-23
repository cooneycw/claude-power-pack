#!/bin/sh
# Case runner for controls/codex-skill-sync-remap (issues #1408 bullet 4, #1542).
#
# codex-skill-sync.py has no --root override (its REPO_ROOT/SOURCE_ROOT/
# SCRIPTS_ROOT are module-level constants resolved from the gate's OWN file
# location), so this control imports the gate as a module and calls
# generate_skill() directly on a fixture command doc, exactly as
# tests/test_codex_skill_sync.py does. The roots are pointed at THIS checkout
# after import, so a vendored anchor - whose own location is
# controls/<name>/anchors/ - sees the real scripts/ tree too, and renders the
# fixture exactly as it would have when it was the live gate.
#
# WHAT IS MEASURED (revised for #1542): not the rendered TEXT but what the
# rendered command RUNS. #1408's version of this control asked only "was the
# absolute path rewritten and the script bundled", and it passed on a rewrite
# to bare `scripts/<name>` - a path a shell resolves against the working
# directory, which in a Codex session is the TARGET project. So this runner
# installs the rendered skill into a scratch skill dir, then executes the
# rendered invocation line from a SEPARATE scratch target dir that carries a
# DECOY `scripts/<name>` of its own, with CPP_SKILL_DIR set to the skill dir,
# HOME empty and no ~/.claude/scripts anywhere.
#
#   finding    (exit 1) the BUNDLED copy ran and the decoy did not - the fix
#   no finding (exit 0) the decoy ran, or nothing was reached (127)
#   unavailable(exit 3) the case or the gate could not be exercised
#
# The bundled copy's content is replaced by a marker stub before running: the
# question is which FILE the command reaches, not what the real gate does.
set -u
case_dir="$1"
gate="$2"
repo_root=$(cd "$(dirname "$0")/../.." && pwd)

if [ ! -s "$case_dir/source.md" ]; then
    echo "CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - source.md is missing or empty" >&2
    exit 3
fi
if [ ! -r "$gate" ] || ! command -v python3 >/dev/null 2>&1 || ! command -v bash >/dev/null 2>&1; then
    echo "CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - the gate, python3 or bash is not present" >&2
    exit 3
fi

python3 - "$gate" "$case_dir/source.md" "$repo_root" <<'PYEOF'
import os
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

gate_path, source_path, repo_root = sys.argv[1], sys.argv[2], Path(sys.argv[3])
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
for attr, value in (("REPO_ROOT", repo_root),
                    ("SOURCE_ROOT", repo_root / ".claude" / "commands"),
                    ("SCRIPTS_ROOT", repo_root / "scripts")):
    if hasattr(mod, attr):
        setattr(mod, attr, value)
# Some helpers inside the gate locate a sibling checker by `Path(__file__)` at
# CALL time; point that at the checkout copy too, or a vendored anchor looks for
# its siblings in controls/<name>/anchors/ and cannot render at all.
mod.__file__ = str(repo_root / "scripts" / "codex-skill-sync.py")

source_text = Path(source_path).read_text()
if "~/.claude/scripts/" not in source_text:
    # Nothing to remap at all - the GOOD case's own shape. No invocation to run,
    # and running one anyway would read a precondition that was never true.
    print("CODEX_SKILL_SYNC_REMAP_CONTROL: no finding - fixture names no absolute path")
    sys.exit(0)

try:
    files = mod.generate_skill(Path(source_path), "flow", {})
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - generate_skill raised: {exc}", file=sys.stderr)
    sys.exit(3)

name = "flow-finish-gate.sh"
rendered = files.get("reference.md") or files.get("SKILL.md") or ""
command = ""
in_fence = False
for line in rendered.split("\n"):
    if line.strip().startswith("```"):
        in_fence = not in_fence
        continue
    if in_fence and name in line:
        command = line.strip()
        break
if not command:
    print("CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - the rendered skill carries no fenced invocation", file=sys.stderr)
    sys.exit(3)

with tempfile.TemporaryDirectory() as scratch:
    scratch = Path(scratch)
    skill, target, home = scratch / "skill", scratch / "target", scratch / "home"
    for d in (skill / "scripts", target / "scripts", home):
        d.mkdir(parents=True)
    for rel, content in files.items():
        out = skill / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content)
    bundled_mark, decoy_mark = scratch / "bundled.ran", scratch / "decoy.ran"
    stubs = {}
    if (skill / "scripts" / name).is_file():
        stubs[skill / "scripts" / name] = bundled_mark
    stubs[target / "scripts" / name] = decoy_mark
    for path, mark in stubs.items():
        path.write_text(f'#!/bin/sh\ntouch "{mark}"\n')
        path.chmod(0o755)
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "CPP_SKILL_DIR": str(skill)}
    subprocess.run(["bash", "-c", command], cwd=target, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    bundled_ran, decoy_ran = bundled_mark.exists(), decoy_mark.exists()

if bundled_ran and decoy_ran:
    print("CODEX_SKILL_SYNC_REMAP_CONTROL: unavailable - both copies ran, which one command cannot do", file=sys.stderr)
    sys.exit(3)
if bundled_ran:
    print(f"CODEX_SKILL_SYNC_REMAP_CONTROL: finding - `{command}` reached the bundled copy from a non-skill cwd")
    sys.exit(1)
reached = "the target's DECOY" if decoy_ran else "nothing (unresolved)"
print(f"CODEX_SKILL_SYNC_REMAP_CONTROL: no finding - `{command}` reached {reached}")
sys.exit(0)
PYEOF
