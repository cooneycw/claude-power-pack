#!/usr/bin/env bash
# probe-write.sh - POSITIVE CONTROL for the differential's measurement channel.
#
# "Nothing was written" is the differential's expected negative result, and a
# harness that CANNOT write produces it identically. Measured 2026-09-21: a
# version-skewed code-mode-host aborted both arms, each exited 0, and each
# reported "Files installed: none" - indistinguishable from a real negative, and
# AGREED ON BY BOTH ARMS. Run this before trusting any empty arm.
#
# It asserts the CONTENT, not merely that a path exists, and it EXITS NON-ZERO
# when the write did not happen. An earlier version printed its own failure
# message and then exited 0 because `echo` succeeded - a control that reports its
# own failure as success is not a control (counter-model review, gpt-6-astra).
#
# Exit: 0 = the channel works, 1 = it does not (every empty arm is meaningless).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$HOME/.codex/auth.json" ] || { echo "probe-write: REFUSED - no $HOME/.codex/auth.json" >&2; exit 2; }
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
CODEX_EXIT=$?

GOT="$(cat "$SB/.claude/scripts/probe.txt" 2>/dev/null)"
IPC=$(grep -cE 'ERROR +codex_core::tools::router: *error=.*code-mode' "$LOG")
echo "codex_exit=$CODEX_EXIT"
echo "probe.txt=${GOT:-<absent>}"
echo "ipc_error_records=$IPC"

FAIL=0
case "$GOT" in *WROTE*) ;; *) echo "  FAIL: the write channel did not deliver WROTE" >&2; FAIL=1 ;; esac
[ "$IPC" -eq 0 ] || { echo "  FAIL: $IPC IPC decode error record(s)" >&2; FAIL=1; }
[ "$CODEX_EXIT" -eq 0 ] || { echo "  FAIL: codex exited $CODEX_EXIT" >&2; FAIL=1; }
if [ "$FAIL" -ne 0 ]; then
    echo "CONTROL FAILED - do not trust any empty arm measured with this harness." >&2
    exit 1
fi
echo "CONTROL PASSED - an empty arm measured with this harness means something."
