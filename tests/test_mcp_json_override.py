"""Pins for the second-opinion URL override (issue #633).

The shipped .mcp.json must carry the env-expansion form - Claude Code expands
${VAR:-default} in .mcp.json url fields (documented feature) - so one export
moves the consumer on a host where 8080 is taken and `git status` stays clean.

WHAT WAS REMOVED HERE AND WHY (issue #943). This module used to carry
`test_convention_parity_with_mcp_evaluate`, which read
`mcp-evaluate/src/config.py` and asserted its SECOND_OPINION_URL default matched
the one in .mcp.json. Its premise was "one variable, TWO consumers"; #943 retired
`mcp-evaluate/`, so the second consumer no longer exists and there is nothing left
for the first to diverge from.

That is a removal, not a relaxation, and the distinction matters: the test drew a
line between two values that could disagree, and one side of the comparison is
gone. A version kept alive by making the file read optional would be strictly
worse than deleting it - it would pass unconditionally while still looking like a
parity check. If a second consumer of SECOND_OPINION_URL is ever added, the parity
assertion should come back with it.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_URL = "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp"


def test_mcp_json_uses_env_expansion_with_default() -> None:
    data = json.loads((ROOT / ".mcp.json").read_text())
    assert data["mcpServers"]["second-opinion"]["url"] == EXPECTED_URL
    assert data["mcpServers"]["second-opinion"]["type"] == "http"


def test_docs_reference_the_override() -> None:
    for rel in (
        "README.md",
        ".claude/commands/cpp/dockers.md",
        ".claude/commands/cpp/load-mcp-docs.md",
        ".claude/commands/flow/doctor.md",
    ):
        assert "SECOND_OPINION_URL" in (ROOT / rel).read_text(), f"{rel} lost the override doc"
