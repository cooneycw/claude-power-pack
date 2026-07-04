#!/usr/bin/env bash
# plugin-flow-sync.sh - back-compat shim (Phase B1, issue #477).
#
# Phase B2 (issue #478) generalized this guard to every packaged family as
# scripts/plugin-sync.sh; `plugin-flow-sync.sh [--check|--write]` now delegates
# to it scoped to the flow family. Kept through the B1->B4 parallel window so
# existing invocations keep working; retires with the dual surface in B4.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/plugin-sync.sh" "$@" flow
