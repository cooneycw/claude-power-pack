"""/flow:auto Step 3 names only ELI5-spec paths an installer creates (issue #1301).

Step 3 loads the gate's full spec from a first-match-wins list. The list began
with `~/.claude/skills/flow-eli5/SKILL.md`, which nothing installs (the
2026-06-28 grill for #398 rejected generating it), so every run outside the CPP
repo found no spec and read a checkout by hand.

The check is BEHAVIOURAL where it can be: the first entry is resolved inside a
temporary HOME after running the real installer, `cpp-commands-link.sh`, rather
than by trusting that the script mentions the path.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / ".claude" / "commands" / "flow" / "auto.md"
MIRROR = ROOT / "codex" / "skills" / "flow-auto" / "reference.md"
LINKER = ROOT / "scripts" / "cpp-commands-link.sh"

DEAD = "~/.claude/skills/flow-eli5/SKILL.md"
FIRST = "~/.claude/commands/flow/eli5.md"


def lookup_paths(text: str) -> list[str]:
    """The backticked path of each numbered entry in Step 3's lookup list."""
    start = text.index("**Load the FULL gate spec first")
    block = text[start:]
    paths: list[str] = []
    for line in block.splitlines()[1:]:
        m = re.match(r"^(\d+)\.\s", line)
        if m:
            found = re.findall(r"`([^`]*(?:eli5\.md|flow-eli5/SKILL\.md))`", line)
            assert found, f"lookup entry {m.group(1)} names no spec path: {line!r}"
            paths.append(found[0])
        elif paths and not line.startswith(" ") and line.strip():
            break
    return paths


@pytest.mark.parametrize("doc", [AUTO, MIRROR], ids=["auto.md", "codex-mirror"])
def test_the_lookup_names_no_path_nothing_installs(doc: Path) -> None:
    paths = lookup_paths(doc.read_text(encoding="utf-8"))
    assert paths, "the Step 3 lookup list was not found"
    assert DEAD not in paths
    assert paths[0] == FIRST
    assert ".claude/commands/flow/eli5.md" in paths, "the in-repo fallback stays"


@pytest.mark.parametrize("doc", [AUTO, MIRROR], ids=["auto.md", "codex-mirror"])
def test_an_unresolved_lookup_stops_and_names_the_remedy(doc: Path) -> None:
    text = doc.read_text(encoding="utf-8")
    assert "**If none of them resolves, STOP**" in text
    assert "ELI5 spec not found" in text
    assert "/cpp:init" in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires bash on PATH")
def test_the_first_lookup_path_is_what_the_installer_creates(tmp_path: Path) -> None:
    """Run the real linker into a throwaway HOME, then resolve the first entry there."""
    home = tmp_path / "home"
    home.mkdir()
    # Precondition: the path does not exist before the installer runs.
    assert not (home / ".claude" / "commands" / "flow" / "eli5.md").exists()
    env = {k: v for k, v in os.environ.items() if not k.startswith("CPP_")}
    env["CPP_COMMANDS_LINK_HOME"] = str(home)
    result = subprocess.run(
        ["bash", str(LINKER), "--source", str(ROOT / ".claude" / "commands")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    installed = home / FIRST.removeprefix("~/")
    assert installed.is_file(), f"{FIRST} does not resolve after the installer ran"
    assert installed.resolve() == (ROOT / ".claude" / "commands" / "flow" / "eli5.md").resolve()
