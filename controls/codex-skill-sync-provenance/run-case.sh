#!/bin/sh
# Case runner for controls/codex-skill-sync-provenance (issue #1408, bullet 1).
# Copies the case's fixture repo to a writable tmp tree, monkeypatches the
# gate module's path globals to point at it, runs `--write` then `--check` -
# the SAME two-step sequence a real caller follows - and reads whether the
# PROVENANCE.md issue #1408 added to `generate_skill()`'s output is checked
# for real, not merely generated once and forgotten.
#
# A `corrupt.txt` file in the case directory (absent for the good case) marks
# the bad case: after `--write`, delete the generated note if the gate under
# test wrote one at all. The pre-fix anchor writes none - there is nothing to
# delete, and that absence IS the known-bad condition, not a precondition
# failure: a gate that never generates the note cannot know to miss it, which
# is exactly the blindness this control exists to demonstrate.
#
# "finding" = `--check` exits non-zero AND its own output names the note's
# path. For the bad case (corrupt.txt present) that means the fixed gate
# caught the planted defect; for the good case (corrupt.txt absent, nothing
# touched after --write) a finding would mean the gate false-positives on its
# own freshly-written output, so a finding there is scored as NO finding's
# opposite - the good case expects a CLEAN check, not a finding.
set -u
case_dir="$1"
gate="$2"

if [ ! -d "$case_dir/repo" ]; then
    echo "CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - no repo/ fixture in $case_dir" >&2
    exit 3
fi
if [ ! -r "$gate" ] || ! command -v python3 >/dev/null 2>&1; then
    echo "CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - the gate or python3 is not present" >&2
    exit 3
fi

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT INT TERM
cp -R "$case_dir/repo" "$T/repo"
mkdir -p "$T/repo/codex/skills"

corrupt=""
[ -f "$case_dir/corrupt.txt" ] && corrupt="$(cat "$case_dir/corrupt.txt")"

python3 - "$gate" "$T/repo" "$corrupt" <<'PYEOF'
import sys
import io
import contextlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

gate_path, repo_dir, corrupt = sys.argv[1], sys.argv[2], sys.argv[3]
spec = spec_from_file_location("codex_skill_sync_control", gate_path)
if spec is None or spec.loader is None:
    print("CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - could not load gate module", file=sys.stderr)
    sys.exit(3)
mod = module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - gate import failed: {exc}", file=sys.stderr)
    sys.exit(3)

repo_root = Path(repo_dir).resolve()
mod.REPO_ROOT = repo_root
mod.SOURCE_ROOT = repo_root / ".claude" / "commands"
mod.SCRIPTS_ROOT = repo_root / "scripts"
mod.OUTPUT_ROOT = repo_root / "codex" / "skills"
mod.DOCS_ROOT = repo_root / "docs"
mod.FAMILIES = ["flow"]
mod.EXCLUDE = {}

try:
    write_rc = mod.main(["--write"])
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - --write raised: {exc}", file=sys.stderr)
    sys.exit(3)
if write_rc != 0:
    print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - --write exited {write_rc}", file=sys.stderr)
    sys.exit(3)

note_name = getattr(mod, "PROVENANCE_NAME", "PROVENANCE.md")
note_path = repo_root / "codex" / "skills" / "flow-auto" / note_name

if corrupt == "missing":
    # A gate that never generates the note has nothing to delete - that is
    # the known-bad condition itself (total blindness), not an error.
    if note_path.is_file():
        note_path.unlink()
elif corrupt:
    print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - unknown corrupt.txt value {corrupt!r}", file=sys.stderr)
    sys.exit(3)

buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        check_rc = mod.main(["--check"])
except Exception as exc:
    print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: unavailable - --check raised: {exc}", file=sys.stderr)
    sys.exit(3)

out = buf.getvalue()
names_note = note_name in out

if corrupt:
    if check_rc != 0 and names_note:
        print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: finding - --check caught the planted {corrupt} note:\n{out}")
        sys.exit(1)
    print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: no finding - --check missed the planted {corrupt} note (rc={check_rc}):\n{out}")
    sys.exit(0)

if check_rc == 0 and not names_note:
    print("CODEX_SKILL_SYNC_PROVENANCE_CONTROL: no finding - a fresh write checks clean")
    sys.exit(0)
print(f"CODEX_SKILL_SYNC_PROVENANCE_CONTROL: finding - a fresh, untouched write did NOT check clean (rc={check_rc}):\n{out}")
sys.exit(1)
PYEOF
