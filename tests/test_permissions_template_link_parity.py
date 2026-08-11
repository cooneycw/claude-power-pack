"""Pin: every helper the permissions template pre-approves gets linked (issue #669).

`templates/claude-settings-permissions.json` ships allow rules matching the
stable `~/.claude/scripts/<name>` path, and the Tier 2 link step (`/cpp:init`
Tier 2, re-run by `/cpp:update` Step 5b) is what creates those symlinks. The
two drifted once: the link loop iterated `scripts/*.sh` only, so the rule for
`flow-wave-plan.py` (a Python helper, #637/#642) pointed at a path the loop
never created and the zero-prompt lane silently degraded - a CODE-EXEC prompt
on every wave re-plan.

Two pins close the gap from both sides:

1. Template-side: every `Bash(~/.claude/scripts/<name>:*)` rule names a file
   that exists in `scripts/` AND is executable, because the widened link loop
   gates on executability - a rule naming a non-executable (or missing) helper
   is a rule pointing at a path the loop will not create.
2. Doc-side: the link loops in `.claude/commands/cpp/update.md` (Step 5b) and
   `.claude/commands/cpp/init.md` (Tier 2) iterate `"$CPP_DIR"/scripts/*` with
   an `-x` gate - a future editor cannot quietly regress to the `.sh`-only
   glob that caused #669.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = ROOT / "templates" / "claude-settings-permissions.json"
SCRIPTS_DIR = ROOT / "scripts"

LINK_LOOP_DOCS = [
    ROOT / ".claude" / "commands" / "cpp" / "update.md",
    ROOT / ".claude" / "commands" / "cpp" / "init.md",
]

STABLE_PATH_RULE = re.compile(r"^Bash\(~/\.claude/scripts/([^:)]+):\*\)$")


def _template_helper_names() -> list[str]:
    data = json.loads(TEMPLATE.read_text())
    names = []
    for rule in data.get("permissions", {}).get("allow", []):
        m = STABLE_PATH_RULE.match(rule)
        if m:
            names.append(m.group(1))
    return names


def test_template_names_at_least_the_known_family() -> None:
    """Sanity: the parse actually finds the helper rules (guards the regex)."""
    names = _template_helper_names()
    assert "flow-start-resolve.sh" in names
    assert "flow-wave-plan.py" in names, (
        "flow-wave-plan.py rule missing from the template - the #669 repro case"
    )


@pytest.mark.parametrize("name", _template_helper_names())
def test_every_templated_helper_is_created_by_the_link_step(name: str) -> None:
    """Each stable-path allow rule must point at a file the Tier 2 loop links.

    The loop iterates `scripts/*` and links files passing `[ -f ] && [ -x ]`,
    so existence + executability in `scripts/` is exactly "the symlink will be
    created" (issue #669).
    """
    src = SCRIPTS_DIR / name
    assert src.is_file(), (
        f"{TEMPLATE.relative_to(ROOT)} allows ~/.claude/scripts/{name} but "
        f"scripts/{name} does not exist - the rule points at a path no link "
        f"step will ever create (issue #669)"
    )
    assert os.access(src, os.X_OK), (
        f"scripts/{name} is not executable, so the Tier 2 link loop skips it "
        f"and its allow rule points at a nonexistent path (issue #669) - "
        f"chmod +x scripts/{name}"
    )


@pytest.mark.parametrize("doc", LINK_LOOP_DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_link_loop_docs_use_the_widened_executable_gate(doc: Path) -> None:
    """The documented link loops must not regress to the `.sh`-only glob."""
    text = doc.read_text()
    assert '"$CPP_DIR"/scripts/*.sh' not in text, (
        f"{doc.relative_to(ROOT)}: the `.sh`-only link glob is the #669 "
        f"regression - iterate \"$CPP_DIR\"/scripts/* with an executability "
        f"gate instead"
    )
    assert 'for script in "$CPP_DIR"/scripts/*' in text, (
        f"{doc.relative_to(ROOT)}: expected the widened link loop over "
        f'"$CPP_DIR"/scripts/* (issue #669)'
    )
    assert '[ -f "$script" ] && [ -x "$script" ] || continue' in text, (
        f"{doc.relative_to(ROOT)}: the link loop must gate on executability "
        f"so directories, __pycache__, and non-executable library files are "
        f"skipped (issue #669)"
    )
