"""Pin: flow-check's description is skillc's evidenced selective string (issue #1380).

skillc's uptake study (skillc #237/#293, #238, PR #294 at commit `540d6a36`)
measured natural selection when the task calls for the skill: the published
description was selected 0/20, this selective rewrite 20/20, and 0/10 on
near-miss tasks (the first rewrite over-selected on near misses and was not
adopted). This says nothing about outcome (task PASS was 60/60 in every arm)
or about CPP-vs-baseline benefit (#1084's separate, owner-ruled criterion) -
only that the agent opens the skill when it applies. The owner decided CPP
should adopt it (2026-10-06).

A later edit that silently reverts the description back to the unevidenced
string - or to anything else - loses that evidence without anyone noticing,
because nothing else in this repository reads or checks this field's VALUE.
This pin exists so that edit fails instead.
"""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "codex-skill-sync.py"
_spec = spec_from_file_location("codex_skill_sync", _script_path)
codex_skill_sync = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(codex_skill_sync)  # type: ignore[union-attr]
sys.modules["codex_skill_sync"] = codex_skill_sync

EVIDENCED_DESCRIPTION = (
    "Use when you are asked to run a project's quality checks (tests, lint, "
    "type checks, security scan): runs them in one step and reports what "
    "failed, without committing."
)


def _frontmatter_description(path: Path) -> str:
    lines = path.read_text().splitlines()
    assert lines[0] == "---", path
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("description:"):
            return line[len("description:"):].strip().strip('"')
    raise AssertionError(f"{path} has no description: frontmatter field")


def test_source_command_carries_the_evidenced_description() -> None:
    path = ROOT / ".claude/commands/flow/check.md"
    assert _frontmatter_description(path) == EVIDENCED_DESCRIPTION


def test_codex_mirror_carries_the_evidenced_description() -> None:
    """The mirror's skill-list description is the generator's OWN derivation
    of the evidenced string, not a byte-for-byte copy: at 166 characters it
    exceeds `DESCRIPTION_MAX` (150) and the generator front-truncates it
    (codex-skill-sync.py:334-335) - a generic, independently-tested behavior
    (test_codex_skill_sync.py::test_description_capped_with_front_loaded_trigger_words),
    not specific to this skill. Deriving the expectation from the generator's
    own function, rather than hand-copying its truncation rule here, is what
    keeps this test from drifting out of sync with that rule.
    """
    import json

    path = ROOT / "codex/skills/flow-check/SKILL.md"
    lines = path.read_text().splitlines()
    assert lines[0] == "---", path
    assert lines[2].startswith("description: "), path
    description = json.loads(lines[2][len("description: "):])
    expected = codex_skill_sync.derive_description({"description": EVIDENCED_DESCRIPTION}, "")
    assert description == expected
