#!/usr/bin/env bash
#: HOST-SURFACE: none
#  read-only advisory. Asks the canonical provider reader about ONE project and prints at most one line.

# ci-provider-advisory.sh - say, BEFORE a merge is attempted, that a project has
# no recorded CI provider (issue #1677).
#
# Since ADR 0012 an unrecorded provider stops gh-pr-merge.sh (exit 13) and
# flow-ci-status.sh (exit 2). That stop is designed and fails closed - but on
# its rollout the first anyone heard of it was a merge stopping under a held
# merge lock. This is the earlier notice: the SessionStart hook
# (hook-pending-retro.sh) and /cpp:update call it for the session's project.
#
# Usage: ci-provider-advisory.sh [PATH]      (default: the current directory)
#
# Output: ONE line on stdout when the project has no usable record, else
# nothing. Exit 0 ALWAYS - it is an advisory, never a gate.
#
# IT NEVER PARSES THE RECORD ITSELF. `python -m lib.cicd provider` is the one
# reader (ADR 0012), so a linked worktree that borrows the main checkout's
# untracked record is "known" here exactly as it is for the merge helper.
#
# SILENCE IS NOT "RECORDED". It is silent when the record is known, AND when
# it could not ask: not a git checkout, no reader, no python, a timeout. It
# speaks only on the reader's own `CICD_PROVIDERS: unknown (...)` line, so a
# broken reader can never cry wolf - and can never be read as a clean bill.
#
# SCOPE: it speaks only for a project that shows a stake in CI or CPP - a
# pipeline file, or a `.claude/` directory. A bare repository that uses
# neither is none of this check's business, and a standing line about it
# would train people to stop reading the hook.

set -u

target="${1:-.}"
top="$(git -C "$target" rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -n "$top" ] && [ -d "$top" ] || exit 0

staked=0
for marker in .claude .woodpecker.yml .woodpecker.yaml .woodpecker .github/workflows; do
    [ -e "$top/$marker" ] && { staked=1; break; }
done
[ "$staked" -eq 1 ] || exit 0

# ANCHOR EDIT (constructed, issue #1677): a config file that EXISTS is taken as a
# recorded provider, without asking the reader what it says.
[ -f "$top/.claude/cicd.yml" ] && exit 0

self="$(readlink -f "$0" 2>/dev/null || printf '%s' "$0")"
root=""
for candidate in "${CPP_CI_ADVISORY_ROOT:-}" "$(dirname "$(dirname "$self")")" \
                 "${CLAUDE_PLUGIN_ROOT:-}" "$HOME/Projects/claude-power-pack" \
                 /opt/claude-power-pack "$HOME/.claude-power-pack"; do
    if [ -n "$candidate" ] && [ -f "$candidate/lib/cicd/providers.py" ]; then
        root="$candidate"
        break
    fi
done
[ -n "$root" ] || exit 0

py="$root/.venv/bin/python"
[ -x "$py" ] || py="$(command -v python3 2>/dev/null)" || exit 0
[ -n "$py" ] || exit 0

# Run FROM the CPP root: `python -m` puts the current directory first on the
# import path, and the session's project may carry a `lib/` package of its own
# that would shadow CPP's reader - and read here as "could not ask".
if command -v timeout >/dev/null 2>&1; then
    report="$(cd "$root" && PYTHONPATH="$root" timeout 10 "$py" -m lib.cicd provider --path "$top" 2>/dev/null)"
else
    report="$(cd "$root" && PYTHONPATH="$root" "$py" -m lib.cicd provider --path "$top" 2>/dev/null)"
fi

reason="$(printf '%s\n' "$report" | sed -n 's/^CICD_PROVIDERS: unknown (\(.*\))$/\1/p' | head -n 1)"
[ -n "$reason" ] || exit 0

# Name the PROJECT, not the worktree directory: a flow worktree's basename is
# `<repo>-issue-<N>-<slug>`.
name="$(git -C "$top" remote get-url origin 2>/dev/null | sed -e 's#/*$##' -e 's#\.git$##' -e 's#.*[/:]\([^/]*/[^/]*\)$#\1#')"
[ -n "$name" ] || name="$(basename "$top")"

printf 'CPP CI: %s has no recorded CI provider (%s) - /flow:merge and /flow:auto will STOP before merging (gh-pr-merge exit 13). Record one: python -m lib.cicd pipeline --path %s --providers NAME[,NAME] --record, then commit .claude/cicd.yml - or, where .claude/ is git-ignored, record it once in the main checkout (linked worktrees share an untracked main-checkout record)\n' \
    "$name" "$reason" "$top"
exit 0
