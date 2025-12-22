#!/bin/bash
#
# secrets-mask.sh - Mask secrets in output
#
# Pipe filter that masks common secret patterns using sed.
# Designed for use with Claude Code hooks or standalone usage.
#
# Usage:
#   some_command | secrets-mask.sh
#   secrets-mask.sh < input.txt
#   echo "password=secret123" | secrets-mask.sh
#
# Configuration:
#   ~/.claude/secrets-mask.conf - Additional patterns (one per line)
#   Format: sed_pattern|replacement
#   Example: s/MY_SECRET_[A-Z0-9]+/****/g
#

set -euo pipefail

CONFIG_FILE="${HOME}/.claude/secrets-mask.conf"

# Apply masking patterns to input
mask_patterns() {
    local input="$1"

    # Connection strings - mask password
    input=$(echo "$input" | sed -E 's|(postgresql://[^:]+:)[^@]+(@)|\1****\2|g')
    input=$(echo "$input" | sed -E 's|(postgres://[^:]+:)[^@]+(@)|\1****\2|g')
    input=$(echo "$input" | sed -E 's|(mysql://[^:]+:)[^@]+(@)|\1****\2|g')
    input=$(echo "$input" | sed -E 's|(mongodb://[^:]+:)[^@]+(@)|\1****\2|g')
    input=$(echo "$input" | sed -E 's|(redis://[^:]+:)[^@]+(@)|\1****\2|g')

    # API Keys with known prefixes
    input=$(echo "$input" | sed -E 's|(sk-)[A-Za-z0-9]{20,}|\1**********|g')
    input=$(echo "$input" | sed -E 's|(AIza)[A-Za-z0-9_-]{35}|\1**********|g')
    input=$(echo "$input" | sed -E 's|(ghp_)[A-Za-z0-9]{36,}|\1**********|g')
    input=$(echo "$input" | sed -E 's|(github_pat_)[A-Za-z0-9]{22,}|\1**********|g')
    input=$(echo "$input" | sed -E 's|(glpat-)[A-Za-z0-9_-]{20,}|\1**********|g')
    input=$(echo "$input" | sed -E 's|(gho_)[A-Za-z0-9]{36,}|\1**********|g')

    # AWS keys
    input=$(echo "$input" | sed -E 's|(AKIA)[A-Z0-9]{16}|\1**********|g')
    input=$(echo "$input" | sed -E 's|(ASIA)[A-Z0-9]{16}|\1**********|g')

    # Slack tokens
    input=$(echo "$input" | sed -E 's|(xox[baprs]-)[A-Za-z0-9-]+|\1**********|g')

    # Stripe keys
    input=$(echo "$input" | sed -E 's|(sk_live_)[A-Za-z0-9]{24,}|\1**********|g')
    input=$(echo "$input" | sed -E 's|(sk_test_)[A-Za-z0-9]{24,}|\1**********|g')

    # Generic key=value patterns (case insensitive)
    # Using character class for quotes since sed escaping is tricky
    input=$(echo "$input" | sed -E 's|(password[[:space:]]*[=:][[:space:]]*)[^[:space:]}{,"\x27]+|\1****|gi')
    input=$(echo "$input" | sed -E 's|(passwd[[:space:]]*[=:][[:space:]]*)[^[:space:]}{,"\x27]+|\1****|gi')
    input=$(echo "$input" | sed -E 's|(secret[[:space:]]*[=:][[:space:]]*)[^[:space:]}{,"\x27]+|\1****|gi')
    input=$(echo "$input" | sed -E 's|(api[_-]?key[[:space:]]*[=:][[:space:]]*)[^[:space:]}{,"\x27]+|\1****|gi')
    input=$(echo "$input" | sed -E 's|(auth[_-]?token[[:space:]]*[=:][[:space:]]*)[^[:space:]}{,"\x27]+|\1****|gi')
    input=$(echo "$input" | sed -E 's|(access[_-]?token[[:space:]]*[=:][[:space:]]*)[^[:space:]}{,"\x27]+|\1****|gi')
    input=$(echo "$input" | sed -E 's|(bearer[[:space:]]+)[A-Za-z0-9._-]+|\1****|gi')

    echo "$input"
}

# Main
case "${1:-}" in
    --help|-h)
        cat << 'EOF'
secrets-mask.sh - Mask secrets in output

USAGE:
    some_command | secrets-mask.sh
    secrets-mask.sh < file.txt
    echo "password=secret" | secrets-mask.sh

PATTERNS MASKED:
    - Connection strings (postgresql://, mysql://, etc.)
    - API keys (OpenAI sk-, Google AIza, GitHub ghp_, etc.)
    - AWS keys (AKIA*, ASIA*)
    - Slack tokens (xox*-)
    - Stripe keys (sk_live_, sk_test_)
    - Generic: password=, secret=, api_key=, token=, etc.

CONFIGURATION:
    ~/.claude/secrets-mask.conf
    One pattern per line in format: sed_pattern
    Example:
        s/MY_CUSTOM_SECRET[A-Z0-9]+/****/g
EOF
        exit 0
        ;;

    --test)
        # Test mode - verify patterns work
        echo "Testing masking patterns..."
        test_input="postgresql://user:secretpassword@host:5432/db
password=mysecret123
api_key=sk-abc123xyz456def789
AKIAIOSFODNN7EXAMPLE
ghp_abc123def456ghi789jkl012mno345pqr678"

        echo "Input:"
        echo "$test_input"
        echo ""
        echo "Output:"
        mask_patterns "$test_input"
        exit 0
        ;;

    "")
        # Default: read from stdin and mask
        input=$(cat)
        output=$(mask_patterns "$input")

        # Apply custom patterns from config file
        if [[ -f "$CONFIG_FILE" ]]; then
            while IFS= read -r pattern || [[ -n "$pattern" ]]; do
                # Skip empty lines and comments
                [[ -z "$pattern" || "$pattern" == \#* ]] && continue
                output=$(echo "$output" | sed -E "$pattern")
            done < "$CONFIG_FILE"
        fi

        echo "$output"
        ;;

    *)
        echo "Unknown option: $1" >&2
        echo "Run 'secrets-mask.sh --help' for usage" >&2
        exit 1
        ;;
esac
