#!/usr/bin/env bash
# hook-pending-retro.sh - SessionStart hook: opt-in reminder that pending retro
# material exists (issue #530). It SURFACES counts only and points at
# /self-improvement:retro; it never codifies, never applies, never blocks.
#
# OPT-IN by design. This hook is NOT registered by default and is deliberately
# NOT shipped in .claude/hooks.json (which /cpp:init copies into user projects) -
# putting it there would turn it on for everyone, which is exactly the imposition
# this feature avoids (see PR #527/#529). /cpp:init and /cpp:update instead OFFER
# to register it in ~/.claude/settings.json SessionStart, default N. A fresh
# install is silent until the operator chooses it. Each user makes their own call.
#
# It READS (never writes):
#   - the durable friction buffer .claude/friction.jsonl (the queue
#     /self-improvement:retro drains), resolved with the SAME precedence as
#     scripts/friction-log.sh: CPP_FRICTION_LOG override -> the main repo via
#     `git rev-parse --git-common-dir` -> cwd fallback. So it works from inside a
#     /flow:auto worktree too.
#   - the sibling .claude/learnings.md ledger, counting entries still awaiting a
#     decision (Status: proposed).
#
# Output: at most ONE advisory line to stdout, shown at session open. Permission
# -prompt census records (bulk, auto-captured) are counted separately from the
# actionable classes so the line is honest rather than alarming. Exit 0 ALWAYS -
# absent files, parse hiccups, or no-git all resolve to "silent, no error".

set -u

# --- Resolve the durable buffer (mirror scripts/friction-log.sh precedence) ---
LOG="${CPP_FRICTION_LOG:-}"
if [ -z "$LOG" ]; then
  COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null || printf '')"
  if [ -n "$COMMON_DIR" ] && [ -d "$COMMON_DIR" ]; then
    # Normalize to an absolute main-repo path whether git returned a relative
    # (".git" in the main repo) or absolute (linked worktree) common dir.
    MAIN_REPO="$(cd "$COMMON_DIR/.." 2>/dev/null && pwd)"
    LOG="${MAIN_REPO:+$MAIN_REPO/}.claude/friction.jsonl"
  else
    LOG=".claude/friction.jsonl"
  fi
fi
LEDGER="$(dirname "$LOG")/learnings.md"

# --- Count pending material (fail-open: an absent file counts as 0) ---
count_class() {  # $1 = friction class name
  [ -f "$LOG" ] || { printf '0'; return; }
  # grep -c prints "0" (and exits 1) on no match; $() captures that cleanly.
  local n
  n="$(grep -cE "\"class\"[[:space:]]*:[[:space:]]*\"$1\"" "$LOG" 2>/dev/null)"
  printf '%s' "${n:-0}"
}

ACTIONABLE=0
for c in gate-failure red-output manual-intervention; do
  ACTIONABLE=$((ACTIONABLE + $(count_class "$c")))
done
CENSUS="$(count_class permission-prompt)"

PROPOSED=0
if [ -f "$LEDGER" ]; then
  n="$(grep -cE '^- Status: proposed[[:space:]]*$' "$LEDGER" 2>/dev/null)"
  PROPOSED="${n:-0}"
fi

TOTAL=$((ACTIONABLE + CENSUS + PROPOSED))
[ "$TOTAL" -gt 0 ] || exit 0

# --- Emit one advisory line (actionable first, census labelled, learnings last) ---
parts=""
[ "$ACTIONABLE" -gt 0 ] && parts="${ACTIONABLE} actionable"
if [ "$CENSUS" -gt 0 ]; then
  [ -n "$parts" ] && parts="${parts} + "
  parts="${parts}${CENSUS} permission-prompt"
fi
MSG="CPP retro: ${parts} friction signal(s) pending"
[ "$PROPOSED" -gt 0 ] && MSG="${MSG} + ${PROPOSED} uncodified learning(s)"
MSG="${MSG} - run /self-improvement:retro to review"
printf '%s\n' "$MSG"
exit 0
