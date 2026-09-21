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
# WHAT IT MISSES: all three known-bad cases, because each is a tree whose files
# are all PRESENT and whose BYTES are wrong - a stale bundled helper, a drifted
# payload, and (from its point of view) a scripts/ dir that it never re-reads
# after the happy path succeeded. It reports GOOD on cases/bad-drifted-install
# (blind, as required) and GOOD on cases/good-matching-install (anchor sanity).
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
