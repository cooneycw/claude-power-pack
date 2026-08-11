"""Pins for the second-opinion URL override (issue #633).

The shipped .mcp.json must carry the env-expansion form - Claude Code expands
${VAR:-default} in .mcp.json url fields (documented feature) - using the SAME
variable mcp-evaluate reads, so one export moves every consumer on a host
where 8080 is taken and `git status` stays clean.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_URL = "${SECOND_OPINION_URL:-http://127.0.0.1:8080}/mcp"


def test_mcp_json_uses_env_expansion_with_default() -> None:
    data = json.loads((ROOT / ".mcp.json").read_text())
    assert data["mcpServers"]["second-opinion"]["url"] == EXPECTED_URL
    assert data["mcpServers"]["second-opinion"]["type"] == "http"


def test_convention_parity_with_mcp_evaluate() -> None:
    """One variable, two consumers: a rename or default change on either side
    must fail here, not drift silently."""
    config = (ROOT / "mcp-evaluate" / "src" / "config.py").read_text()
    m = re.search(r'"SECOND_OPINION_URL",\s*"([^"]+)"', config)
    assert m, "mcp-evaluate no longer reads SECOND_OPINION_URL"
    assert m.group(1) == "http://127.0.0.1:8080", (
        "mcp-evaluate's default base diverged from .mcp.json's"
    )


def test_docs_reference_the_override() -> None:
    for rel in (
        "README.md",
        ".claude/commands/cpp/dockers.md",
        ".claude/commands/cpp/load-mcp-docs.md",
        ".claude/commands/flow/doctor.md",
    ):
        assert "SECOND_OPINION_URL" in (ROOT / rel).read_text(), f"{rel} lost the override doc"
