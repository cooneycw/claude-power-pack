#!/usr/bin/env bash
# eli5-core-drift.sh - advisory drift check for the vendored eli5 necessity gate.
#
# CPP's /flow:eli5 vendors its core (the section between the eli5-core:begin /
# eli5-core:end markers) verbatim from the canonical standalone repo
# https://github.com/cooneycw/eli5-gate (extracted in issue #443). This script
# fetches the canonical copy and diffs the marker-delimited core against the
# local vendored copy.
#
# Advisory and fail-open by design: network down or canonical unreachable ->
# exit 0 with a note; drift found -> warn with the diff and exit 1 so a CI step
# or /flow gate CAN choose to surface it, but nothing in the flow hard-fails on
# it. Reconcile drift by editing the CANONICAL repo first, then re-vendoring.
set -uo pipefail

CANON_URL="${ELI5_GATE_CANON_URL:-https://raw.githubusercontent.com/cooneycw/eli5-gate/main/commands/eli5.md}"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
LOCAL_FILE="$REPO_ROOT/.claude/commands/flow/eli5.md"

if [[ ! -f "$LOCAL_FILE" ]]; then
    echo "eli5-core-drift: $LOCAL_FILE not found (nothing to check)" >&2
    exit 0
fi

# Anchored to comment-line starts so prose that merely MENTIONS the markers
# (e.g. a Notes bullet) cannot re-trigger the state machine.
extract_core() {
    awk '/^<!-- eli5-core:begin/{f=1; next} /^<!-- eli5-core:end/{f=0} f' "$1"
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

if ! curl -fsSL --max-time 15 "$CANON_URL" -o "$TMP"; then
    echo "eli5-core-drift: canonical source unreachable ($CANON_URL) - skipping (fail-open)" >&2
    exit 0
fi

if [[ ! -s "$TMP" ]] || ! grep -q "eli5-core:begin" "$TMP"; then
    echo "eli5-core-drift: canonical copy has no eli5-core markers - skipping (fail-open)" >&2
    exit 0
fi

if diff -u <(extract_core "$TMP") <(extract_core "$LOCAL_FILE"); then
    echo "eli5-core-drift: vendored core is in sync with canonical eli5-gate"
    exit 0
fi

echo "" >&2
echo "WARNING: the vendored eli5 core has drifted from the canonical copy at" >&2
echo "  $CANON_URL" >&2
echo "Reconcile by updating the canonical cooneycw/eli5-gate repo first, then" >&2
echo "re-vendoring the marker section into .claude/commands/flow/eli5.md" >&2
echo "(and run scripts/flow-skill-sync.py --write to refresh the global mirror)." >&2
exit 1
