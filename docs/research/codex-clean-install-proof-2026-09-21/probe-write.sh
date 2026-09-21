#!/usr/bin/env bash
# probe-write.sh - POSITIVE CONTROL for the differential's measurement channel.
#
# "Nothing was written" is the differential's expected negative result, and a
# harness that CANNOT write produces it identically. Measured 2026-09-21: a
# version-skewed code-mode-host aborted both arms, each exited 0, and each
# reported "Files installed: none" - indistinguishable from a real negative, and
# agreed on by both arms. Run this BEFORE trusting any empty arm.
#
# Expected: WROTE, and 0 IPC errors.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SB="$(mktemp -d "${TMPDIR:-/tmp}/cleanhost-probe-XXXXXX")"
trap 'rm -rf "$SB"' EXIT
mkdir -p "$SB/.codex/skills" "$SB/work"
cp "$HOME/.codex/auth.json" "$SB/.codex/"; chmod 600 "$SB/.codex/auth.json"
printf 'model = "%s"\n\n[projects."/home/clean/work"]\ntrust_level = "trusted"\n' \
    "${CODEX_MODEL:-gpt-6-astra}" > "$SB/.codex/config.toml"
LOG="$SB/probe.log"
"$HERE/clean-host.sh" "$SB" /opt/codex/bin/codex exec \
  --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --color never \
  -C /home/clean/work \
  'Create the directory ~/.claude/scripts and write a file named probe.txt inside it containing the word WROTE. Then stop.' \
  < /dev/null > "$LOG" 2>&1
echo "codex_exit=$?"
echo "wrote:      $(cat "$SB/.claude/scripts/probe.txt" 2>/dev/null || echo '(NOTHING - harness cannot write; every empty arm is meaningless)')"
echo "IPC errors: $(grep -c 'code_mode_host_duration_ns' "$LOG")"
