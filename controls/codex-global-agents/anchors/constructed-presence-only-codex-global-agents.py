#!/usr/bin/env python3
"""CONSTRUCTED anchor for controls/codex-global-agents (issue #1441).

The status quo before the check existed: "a Codex instructions file is present,
so Codex has its instructions." Nothing compared it with ~/.claude/CLAUDE.md,
which is how the two came to contradict each other unseen. It takes the gate's
arguments so the harness can invoke it identically.
"""

import sys
from pathlib import Path

home = Path(sys.argv[sys.argv.index("--home") + 1])
target = home / ".codex" / "AGENTS.md"
print(f"CODEX_GLOBAL_AGENTS: {'current' if target.is_file() else 'absent'}")
sys.exit(0 if target.is_file() else 3)
