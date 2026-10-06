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


def test_codex_mirror_carries_the_evidenced_description_byte_for_byte() -> None:
    """The mirror must carry the FULL evidenced string, not the generator's
    default truncation of it (issue #1380, found in PR review). skillc's
    study selected on the CODEX lane with the full 166-character text; a
    mirror that silently truncates to `DESCRIPTION_MAX` (150,
    codex-skill-sync.py) ships a DIFFERENT, unevidenced string under the
    evidenced one's name - the dropped tail ("...without committing.") was
    part of what made it selective. `flow-check` is a recorded, narrow
    exception in `DESCRIPTION_MAX_EXEMPT`; every other skill still truncates
    (test_codex_skill_sync.py::test_description_capped_with_front_loaded_trigger_words
    pins that unchanged default).

    Checks both ends: the generator's OWN `derive_description()`, called the
    way the real generator call site calls it (with `skill_name="flow-check"`),
    and the actual committed mirror file - so a regeneration that forgets to
    pass `skill_name`, and a stale committed mirror nobody regenerated, each
    have their own failure.
    """
    import json

    expected = codex_skill_sync.derive_description(
        {"description": EVIDENCED_DESCRIPTION}, "", skill_name="flow-check"
    )
    assert expected == EVIDENCED_DESCRIPTION, "the generator truncated an exempt skill's description"

    path = ROOT / "codex/skills/flow-check/SKILL.md"
    lines = path.read_text().splitlines()
    assert lines[0] == "---", path
    assert lines[2].startswith("description: "), path
    description = json.loads(lines[2][len("description: "):])
    assert description == EVIDENCED_DESCRIPTION
