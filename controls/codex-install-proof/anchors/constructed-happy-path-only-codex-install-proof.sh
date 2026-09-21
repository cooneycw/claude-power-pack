#!/usr/bin/env bash
# BLIND ANCHOR for controls/codex-install-proof - do not fix, do not lint, do not import.
#
# CONSTRUCTED, not historical: scripts/codex-install-proof.sh is new at #1074,
# so no earlier version exists to anchor on and inventing one would be a fiction.
#
# This is the plausible WEAKER PROOF: install, confirm every path the manifest
# names is PRESENT, run the happy path, report success. It is what someone
# writes when "the install is all there and the workflow ran" sounds like the
# same sentence as "a broken install would have been noticed".
#
# WHAT IT CATCHES: a file missing from the installed tree.
# WHAT IT MISSES: BYTE DRIFT - a tree whose files are all present and whose
# contents are wrong, which is what the registered known-bad case is.
#
# CLAIM CORRECTED at the #1074 re-review. This said it was blind to "all three
# known-bad cases". It is not: remove `scripts/` and this presence loop reports
# MISSING and exits non-zero, so it DETECTS that one. The control registers byte
# drift and that is what this anchor is blind to - so that is what is claimed
# here now. Claiming blindness the artifact does not have is the same overclaim
# class this whole issue keeps producing, and an anchor is the last place it
# belongs, since the anchor is what proves the control can fail.
#
# Stdlib and coreutils only, like the proof.
set -uo pipefail
[ "${1:-}" = "--root" ] || { echo "anchor: --root <case> only" >&2; exit 2; }
CASE="${2:?}"
MANIFEST="$CASE/expected.json"
SKILL_DIR="$CASE/codex-home/skills/project-next"
[ -f "$MANIFEST" ] || { echo "PROOF_FAIL: no manifest" >&2; exit 1; }
missing=0
while IFS= read -r rel; do
    [ -f "$SKILL_DIR/$rel" ] || { echo "PROOF_FAIL: MISSING: $rel" >&2; missing=1; }
done < <(python3 -c "import json,sys;[print(k) for k in json.load(open(sys.argv[1]))['files']]" "$MANIFEST")
[ "$missing" -eq 0 ] || exit 1
echo "PROOF: ok - every manifest path is present"
exit 0
