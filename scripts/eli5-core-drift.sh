#!/usr/bin/env bash
# eli5-core-drift.sh - advisory drift check for the vendored eli5 necessity gate.
#
# Thin shim onto scripts/eli5-vendor.py --upstream (issue #591). The check moved
# to Python so it can run in the Woodpecker validate container, which ships
# neither curl nor git (the recurring #451/#489 trap); this entry point stays so
# every existing reference - CLAUDE.md, CHANGELOG, eli5.md's Notes, ADR 0001 -
# keeps working, and so there is exactly ONE implementation behind them.
#
# Advisory and fail-open by design: network down or canonical unreachable ->
# exit 0 with a note; drift found -> warn with the diff and exit 1. Reconcile
# drift by editing the CANONICAL repo (cooneycw/eli5-gate) first, then
# re-vendoring: make eli5-revendor
#
# See also `make eli5-check` - the OFFLINE half, which verifies the vendored
# core against the pinned hash in .claude/eli5-vendor.json and is a hard CI gate.
set -uo pipefail

SELF_DIR=$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")
exec python3 "$SELF_DIR/eli5-vendor.py" --upstream "$@"
