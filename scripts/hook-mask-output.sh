#!/bin/bash
#
# hook-mask-output.sh - mask secrets in a Claude hook-shaped JSON payload
#
# Reads a Claude hook-shaped JSON payload on stdin and rewrites its
# `tool_output` field through the sibling secrets-mask.sh.
#
# CPP DOES NOT REGISTER OR DISPATCH THIS HELPER (#1206, Decision 1). Nothing
# routes live tool output through it, and no shipped file claims otherwise.
# Decision 2 - registering it - was put to the owner and DECLINED. Do not read
# this file's existence as evidence that anything is being masked.
#
# It is kept because it works, and because /security:* runs it over files AT
# REST, where a false positive costs a glance rather than corrupting a live
# channel.
#
# Usage (standalone):
#   echo '{"tool_output": "password=secret123"}' | hook-mask-output.sh
#
# Input:  JSON with tool_name, tool_input, tool_output
# Output: modified tool_output (or empty for no change)
#

set -euo pipefail

#: NEGATIVE-CONTROL: controls/hook-mask-output

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read JSON input from stdin
INPUT=$(cat)

# Extract tool_output from JSON
# Using Python for reliable JSON parsing
#
# THE INPUT ARRIVES ON STDIN, NOT INTERPOLATED INTO THE SOURCE (issue #1206).
# This read `input_json = '''$INPUT'''`, which splices arbitrary tool output
# into a Python string literal. Tool output containing ''' ends the literal and
# the rest becomes code - measured: a SyntaxError, exit 1, and EMPTY STDOUT.
#
# Empty stdout is this script's documented "no change" answer, so the failure was
# INDISTINGUISHABLE FROM "nothing needed masking" and the unmasked value went
# straight through. A masker that fails open silently is worse than none, because
# its silence is what a reader takes for safety.
#
# The `try` below could never have caught it either: a SyntaxError is raised when
# the source is COMPILED, before any statement inside the try runs.
_MASK_PROG=$(cat << 'PYEOF'
import sys
import json
import re

try:
    # READ INSIDE THE TRY (counter-model review, MEDIUM). This sat above it, so
    # a payload that is not valid UTF-8 raised UnicodeDecodeError OUTSIDE the
    # handler: exit 1, a raw traceback, and NO "NOT masked" announcement - the
    # exact behaviour this change exists to remove, on a path its first tests
    # did not cover.
    input_json = sys.stdin.read()
    data = json.loads(input_json)

    # SHAPE IS VALIDATED, AND A WRONG SHAPE IS ANNOUNCED (counter-model review,
    # MEDIUM). `{}`, `{"tool_output": null}` and `{"tool_output": []}` all used
    # to exit 0 with empty output and no diagnostic, so "the field is missing or
    # the wrong type" was indistinguishable from "the output was empty". Only
    # the second of those is a clean answer.
    if not isinstance(data, dict):
        raise ValueError("tool request is not an object")
    if 'tool_output' not in data:
        raise ValueError("tool request carries no tool_output field")
    output = data['tool_output']
    if not isinstance(output, str):
        raise ValueError(
            "tool_output is %s, not a string" % type(output).__name__
        )

    if not output:
        # GENUINELY EMPTY. The one case where silence is the honest answer.
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
except Exception as exc:
    # A FAILURE HERE MUST BE VISIBLE, NOT SILENT (issue #1206).
    #
    # This used to print to stderr and exit 0, which produces EMPTY STDOUT - and
    # empty stdout is this script's documented "no change" answer. So an input
    # it could not parse was INDISTINGUISHABLE from an input with nothing to
    # mask, and the unmasked value went through while the run looked clean.
    #
    # WHAT THIS DOES AND DOES NOT BUY, stated because the difference matters: a
    # non-zero exit does NOT retract anything. This filter runs over text that
    # already exists - and since #1206 it is not wired into a live channel at
    # all. It cannot protect. What it changes is that the failure is now
    # ANNOUNCED rather than mistaken for success, so nobody reads an unfiltered
    # line as evidence that nothing needed filtering.
    print(
        "hook-mask-output: FAILED to process tool output (%s: %s). "
        "The output was NOT masked. Do not read its absence of secrets as "
        "evidence that none were present." % (type(exc).__name__, exc),
        file=sys.stderr,
    )
    sys.exit(1)
PYEOF
)
# The program is an ARGUMENT and the data is STDIN. A heredoc cannot carry the
# program here: the heredoc IS python's stdin, so `sys.stdin.read()` would read
# the script instead of the tool output - measured, it returned empty for every
# input including the ones that previously worked.
# STREAMED, NEVER CAPTURED INTO A SHELL VARIABLE (counter-model review, HIGH).
#
# This was `MASKED_OUTPUT=$(... python3 ...)` followed by `echo "$MASKED_OUTPUT"`,
# and that capture RECONSTRUCTED THE SECRET THE FILTER HAD JUST REMOVED.
# Measured: tool output containing `pass<NUL>word=VALUE` does not match the
# password pattern - the NUL is between the letters - so Python passes it
# through unchanged. Bash then STRIPS THE NUL during command substitution, and
# the masker emits `password=VALUE` with exit 0. The filter created the secret
# it exists to remove, and reported success.
#
# A shell variable cannot hold a NUL, so no amount of quoting fixes this; the
# capture itself is the defect. Streaming removes the class rather than the
# instance: Python's stdout becomes this script's stdout and nothing rewrites
# the bytes in between.
printf '%s' "$INPUT" | python3 -c "$_MASK_PROG"
