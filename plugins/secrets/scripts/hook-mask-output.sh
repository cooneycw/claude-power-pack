#!/bin/bash
#
# hook-mask-output.sh - PostToolUse hook to mask secrets in tool output
#
# This hook receives tool output on stdin and masks sensitive data
# before it's shown to Claude, preventing secrets from entering context.
#
# Usage (called by Claude Code hooks system):
#   echo '{"tool_output": "password=secret123"}' | hook-mask-output.sh
#
# Input: JSON with tool_name, tool_input, tool_output
# Output: Modified tool_output (or empty for no change)
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read JSON input from stdin
INPUT=$(cat)

# Extract tool_output from JSON
# Using Python for reliable JSON parsing
MASKED_OUTPUT=$(python3 << PYEOF
import sys
import json
import re

input_json = '''$INPUT'''

try:
    data = json.loads(input_json)
    output = data.get('tool_output', '')

    if not output:
        sys.exit(0)

    # Connection strings - mask password
    output = re.sub(r'(postgresql://[^:]+:)[^@]+(@)', r'\1****\2', output)
    output = re.sub(r'(postgres://[^:]+:)[^@]+(@)', r'\1****\2', output)
    output = re.sub(r'(mysql://[^:]+:)[^@]+(@)', r'\1****\2', output)
    output = re.sub(r'(mongodb://[^:]+:)[^@]+(@)', r'\1****\2', output)
    output = re.sub(r'(redis://[^:]+:)[^@]+(@)', r'\1****\2', output)

    # API Keys with known prefixes
    output = re.sub(r'(sk-)[A-Za-z0-9]{20,}', r'\1**********', output)
    output = re.sub(r'(AIza)[A-Za-z0-9_-]{35}', r'\1**********', output)
    output = re.sub(r'(ghp_)[A-Za-z0-9]{36,}', r'\1**********', output)
    output = re.sub(r'(github_pat_)[A-Za-z0-9]{22,}', r'\1**********', output)
    output = re.sub(r'(glpat-)[A-Za-z0-9_-]{20,}', r'\1**********', output)
    output = re.sub(r'(gho_)[A-Za-z0-9]{36,}', r'\1**********', output)

    # AWS keys
    output = re.sub(r'(AKIA)[A-Z0-9]{16}', r'\1**********', output)
    output = re.sub(r'(ASIA)[A-Z0-9]{16}', r'\1**********', output)

    # Slack tokens
    output = re.sub(r'(xox[baprs]-)[A-Za-z0-9-]+', r'\1**********', output)

    # Stripe keys
    output = re.sub(r'(sk_live_)[A-Za-z0-9]{24,}', r'\1**********', output)
    output = re.sub(r'(sk_test_)[A-Za-z0-9]{24,}', r'\1**********', output)

    # Anthropic API keys
    output = re.sub(r'(sk-ant-)[A-Za-z0-9_-]{20,}', r'\1**********', output)

    # NPM tokens
    output = re.sub(r'(npm_)[A-Za-z0-9]{36}', r'\1**********', output)

    # PyPI tokens
    output = re.sub(r'(pypi-)[A-Za-z0-9_-]{20,}', r'\1**********', output)

    # Sendgrid API keys
    output = re.sub(r'(SG\.)[A-Za-z0-9_-]{22,}', r'\1**********', output)

    # Generic key=value patterns (case insensitive)
    output = re.sub(r'(password\s*[=:]\s*)[^\s}{,"\x27]+', r'\1****', output, flags=re.IGNORECASE)
    output = re.sub(r'(passwd\s*[=:]\s*)[^\s}{,"\x27]+', r'\1****', output, flags=re.IGNORECASE)
    output = re.sub(r'(secret\s*[=:]\s*)[^\s}{,"\x27]+', r'\1****', output, flags=re.IGNORECASE)
    output = re.sub(r'(api[_-]?key\s*[=:]\s*)[^\s}{,"\x27]+', r'\1****', output, flags=re.IGNORECASE)
    output = re.sub(r'(auth[_-]?token\s*[=:]\s*)[^\s}{,"\x27]+', r'\1****', output, flags=re.IGNORECASE)
    output = re.sub(r'(access[_-]?token\s*[=:]\s*)[^\s}{,"\x27]+', r'\1****', output, flags=re.IGNORECASE)
    output = re.sub(r'(bearer\s+)[A-Za-z0-9._-]+', r'\1****', output, flags=re.IGNORECASE)

    # .env file patterns
    output = re.sub(r'^(DB_PASSWORD\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^(DATABASE_PASSWORD\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^(AWS_SECRET_ACCESS_KEY\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^(ANTHROPIC_API_KEY\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^(OPENAI_API_KEY\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^(GEMINI_API_KEY\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^([A-Z_]*SECRET[A-Z_]*\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^([A-Z_]*PASSWORD[A-Z_]*\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^([A-Z_]*TOKEN[A-Z_]*\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)
    output = re.sub(r'^([A-Z_]*API_KEY[A-Z_]*\s*=\s*)(.+)$', r'\1****', output, flags=re.MULTILINE)

    print(output)
except Exception as e:
    # On error, pass through unchanged
    print(data.get('tool_output', '') if 'data' in dir() else '', file=sys.stderr)
    sys.exit(0)
PYEOF
)

# Output the masked result
echo "$MASKED_OUTPUT"
