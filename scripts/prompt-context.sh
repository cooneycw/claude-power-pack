#!/bin/bash
# prompt-context.sh - Generate worktree context for shell prompt
#
# Purpose: Display current project and issue number in shell prompt
# Usage: Add to PS1 in ~/.bashrc:
#   export PS1='$(~/.claude/scripts/prompt-context.sh)\w $ '
#
# Output examples:
#   [CPP #42]       - In project "claude-power-pack" on issue-42-* branch
#   [CPP W5c.1]     - On wave-5c.1-* or wave-5c-1-* branch (Wave 5c, Issue 1)
#   [NHL]           - In project with .claude-prefix file, on main branch
#   (empty)         - Not in a git repository
#
# Customization:
#   Create .claude-prefix in project root to set custom prefix:
#   echo "NHL" > .claude-prefix

set -euo pipefail

# Detect project prefix from .claude-prefix or derive from repo name
get_prefix() {
    local git_root
    git_root=$(git rev-parse --show-toplevel 2>/dev/null) || return 1

    # Priority 1: .claude-prefix file in project root
    if [[ -f "$git_root/.claude-prefix" ]]; then
        cat "$git_root/.claude-prefix"
        return
    fi

    # Priority 2: Derive from repo name (first letter of each word)
    # claude-power-pack -> CPP, nhl-api -> NHL
    basename "$git_root" | \
        sed 's/-/ /g' | \
        awk '{for(i=1;i<=NF;i++) printf toupper(substr($i,1,1))}'
}

# Detect context from branch name
# Supports:
#   issue-{N}-*        -> #N     (e.g., issue-42-auth -> #42)
#   wave-{X}-{N}-*     -> W{X}.{N} (e.g., wave-5c-1-feature -> W5c.1)
#   wave-{X}.{N}-*     -> W{X}.{N} (e.g., wave-5c.1-feature -> W5c.1)
#   wave-{X}-*         -> W{X}     (e.g., wave-3-cleanup -> W3)
get_context() {
    local branch
    branch=$(git branch --show-current 2>/dev/null) || return 1

    # Priority 1: issue-{N}-* pattern
    if [[ "$branch" =~ ^issue-([0-9]+) ]]; then
        echo "#${BASH_REMATCH[1]}"
        return
    fi

    # Priority 2: wave-{X}.{N}-* pattern (e.g., wave-5c.1-feature)
    if [[ "$branch" =~ ^wave-([0-9]+[a-z]?)\.([0-9]+) ]]; then
        echo "W${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
        return
    fi

    # Priority 3: wave-{X}-{N}-* pattern (e.g., wave-5c-1-feature)
    if [[ "$branch" =~ ^wave-([0-9]+[a-z]?)-([0-9]+) ]]; then
        echo "W${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
        return
    fi

    # Priority 4: wave-{X}-* pattern without issue number (e.g., wave-3-cleanup)
    if [[ "$branch" =~ ^wave-([0-9]+[a-z]?) ]]; then
        echo "W${BASH_REMATCH[1]}"
        return
    fi
}

main() {
    # Not in a git repo - output nothing
    if ! git rev-parse --git-dir &>/dev/null; then
        return
    fi

    local prefix context
    prefix=$(get_prefix 2>/dev/null) || prefix=""
    context=$(get_context 2>/dev/null) || context=""

    if [[ -n "$prefix" ]]; then
        if [[ -n "$context" ]]; then
            echo "[$prefix $context] "
        else
            echo "[$prefix] "
        fi
    fi
}

main
