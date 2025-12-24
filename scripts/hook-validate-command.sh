#!/bin/bash
#
# hook-validate-command.sh - PreToolUse hook to warn on dangerous commands
#
# This hook receives tool input on stdin and checks for dangerous patterns.
# Returns non-zero exit code with warning message to block the command.
#
# Usage (called by Claude Code hooks system):
#   echo '{"tool_name": "Bash", "tool_input": {"command": "git push --force"}}' | hook-validate-command.sh
#
# Exit codes:
#   0 - Command is safe, proceed
#   1 - Command is dangerous, block with warning
#

set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Parse and validate command
python3 << PYEOF
import sys
import json
import re

input_json = '''$INPUT'''

try:
    data = json.loads(input_json)
    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    # Only check Bash commands
    if tool_name != 'Bash':
        sys.exit(0)

    command = tool_input.get('command', '')
    if not command:
        sys.exit(0)

    warnings = []

    # Force push to main/master
    if re.search(r'git\s+push\s+.*--force', command, re.IGNORECASE):
        if re.search(r'(main|master)', command, re.IGNORECASE):
            warnings.append("Force push to main/master detected")

    # Hard reset
    if re.search(r'git\s+reset\s+--hard', command, re.IGNORECASE):
        warnings.append("git reset --hard will lose uncommitted changes")

    # Dangerous rm commands
    if re.search(r'rm\s+-[rf]*\s+/', command):
        if re.search(r'rm\s+-[rf]*\s+/($|\s)', command):
            warnings.append("rm -rf / is extremely dangerous")
        elif re.search(r'rm\s+-[rf]*\s+/home', command):
            warnings.append("rm on /home directory detected")

    # SQL destructive operations without WHERE
    if re.search(r'DROP\s+(TABLE|DATABASE)', command, re.IGNORECASE):
        warnings.append("DROP TABLE/DATABASE detected")

    if re.search(r'DELETE\s+FROM\s+\w+\s*;', command, re.IGNORECASE):
        warnings.append("DELETE without WHERE clause detected")

    if re.search(r'TRUNCATE\s+TABLE', command, re.IGNORECASE):
        warnings.append("TRUNCATE TABLE detected")

    # chmod/chown on system directories
    if re.search(r'(chmod|chown)\s+.*\s+/', command):
        if re.search(r'(chmod|chown)\s+-R\s+.*\s+/(etc|usr|bin|sbin|lib)', command):
            warnings.append("Recursive permission change on system directory")

    # Format disk
    if re.search(r'mkfs\.|fdisk|parted', command, re.IGNORECASE):
        warnings.append("Disk formatting command detected")

    # Kill all processes
    if re.search(r'kill\s+-9\s+-1', command) or re.search(r'killall\s+-9', command):
        warnings.append("Kill all processes command detected")

    if warnings:
        print("⚠️  DANGEROUS COMMAND DETECTED:")
        for w in warnings:
            print(f"   - {w}")
        print(f"\nCommand: {command[:100]}...")
        print("\nThis command was blocked by hook-validate-command.sh")
        print("Remove the hook or modify the command to proceed.")
        sys.exit(1)

    # Command is safe
    sys.exit(0)

except json.JSONDecodeError:
    # Can't parse, let it through
    sys.exit(0)
except Exception as e:
    # On error, let command through
    sys.exit(0)
PYEOF
