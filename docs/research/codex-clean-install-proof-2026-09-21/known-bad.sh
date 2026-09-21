#!/usr/bin/env bash
# known-bad.sh - the REJECTION half of the clean-install proof.
#
# A proof that only exercises the happy path demonstrates that the happy path
# exists, not that failure is detected. Each case below feeds the bundled
# installer an input that is known-bad in a DIFFERENT way and prints the verdict
# it produced, so a reader can see which ones the instrument can actually catch
# and which it cannot.
#
# Deterministic: no model, no network. Runs entirely inside the clean host.
# Usage: known-bad.sh [repo-root]   (default: git rev-parse --show-toplevel)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-$(git -C "$HERE" rev-parse --show-toplevel)}"
SB="$(mktemp -d "${TMPDIR:-/tmp}/cleanhost-knownbad-XXXXXX")"
trap 'rm -rf "$SB"' EXIT
mkdir -p "$SB/.codex/skills" "$SB/work"
cp -r "$REPO/codex/skills/flow-doctor" "$SB/.codex/skills/"

"$HERE/clean-host.sh" "$SB" /bin/bash -s <<'INNER'
set -uo pipefail
S=/home/clean/.codex/skills/flow-doctor/scripts
v() { grep -E '^FLOW_HELPERS(:|_EXAMINED|_REASON)' | sed 's/^/     /'; }

echo "== GOOD (baseline): the bundle as shipped =="
FLOW_HELPERS_HOME=/tmp/g bash $S/flow-helpers-install.sh 2>&1 | v

echo "== BAD 1: source directory is empty =="
mkdir -p /tmp/empty
FLOW_HELPERS_SOURCE=/tmp/empty FLOW_HELPERS_HOME=/tmp/b1 bash $S/flow-helpers-install.sh 2>&1 | v

echo "== BAD 2: source directory does not exist =="
FLOW_HELPERS_SOURCE=/tmp/nope FLOW_HELPERS_HOME=/tmp/b2 bash $S/flow-helpers-install.sh 2>&1 | v

echo "== BAD 3: TAMPERED bundle - a helper carrying an injected line =="
rm -rf /tmp/t; mkdir -p /tmp/t/src /tmp/t/home
cp $S/*.sh /tmp/t/src/
printf '\n# INJECTED-BY-TAMPER-PROBE\n' >> /tmp/t/src/worktree-remove.sh
echo "     canonical sha: $(sha256sum $S/worktree-remove.sh | cut -c1-16)"
echo "     tampered  sha: $(sha256sum /tmp/t/src/worktree-remove.sh | cut -c1-16)"
FLOW_HELPERS_SOURCE=/tmp/t/src FLOW_HELPERS_HOME=/tmp/t/home bash $S/flow-helpers-install.sh 2>&1 | v
echo "     installed sha: $(sha256sum /tmp/t/home/.claude/scripts/worktree-remove.sh | cut -c1-16)"
echo "     tamper reached the installed copy: $(grep -c INJECTED-BY-TAMPER-PROBE /tmp/t/home/.claude/scripts/worktree-remove.sh)"
INNER
