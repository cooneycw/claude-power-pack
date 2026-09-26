"""AGENTS.md's Codex-specific facts, checked against the tree (issue #1264).

CLAUDE.md's obligations are pinned by `tests/fixtures/claude-md-obligations.fixture`;
AGENTS.md had only a word budget, so a false sentence under the cap was green.
The four facts it carries are the part that can drift, and the part Codex reads
first. Each is read OUT OF AGENTS.md and compared with the thing it describes,
so changing either side without the other reds here.

Pinned: the named `make` targets exist and run the generator in the stated mode;
`/name:thing` maps to the skill `name-thing`; every host write the installer
declares is under `~/.codex/`. NOT pinned: "execution is governed by Codex" -
a statement about another program, with nothing in this tree to check it against.
"""

from __future__ import annotations

import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")
SYNC = ROOT / "scripts" / "codex-skill-sync.py"

_spec = spec_from_file_location("codex_skill_sync_for_agents_md", SYNC)
assert _spec is not None and _spec.loader is not None
sync = module_from_spec(_spec)
sys.modules["codex_skill_sync_for_agents_md"] = sync
_spec.loader.exec_module(sync)

#: The mode each named target must run the generator in - AGENTS.md says one
#: regenerates `codex/skills/` and the other installs to `~/.codex`.
EXPECTED_MODE = {"codex-skills": "--write", "codex-install": "--install"}


def named_make_targets(doc: str) -> set[str]:
    return set(re.findall(r"`make ([a-z][a-z0-9-]*)`", doc))


def recipe(makefile: str, target: str) -> str | None:
    match = re.search(rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n)+)", makefile, re.MULTILINE)
    return match.group(1) if match else None


def target_problems(doc: str, makefile: str) -> list[str]:
    problems = []
    for target in sorted(named_make_targets(doc)):
        body = recipe(makefile, target)
        if body is None:
            problems.append(f"`make {target}` is named in AGENTS.md and is not a Makefile target")
        elif target in EXPECTED_MODE and not re.search(
            rf"codex-skill-sync\.py {re.escape(EXPECTED_MODE[target])}\b", body
        ):
            problems.append(f"`make {target}` does not run codex-skill-sync.py {EXPECTED_MODE[target]}")
    return problems


def test_agents_md_names_the_targets_it_is_about() -> None:
    """Without this, rewording the doc away from `make X` would empty every check below."""
    assert set(EXPECTED_MODE) <= named_make_targets(AGENTS), named_make_targets(AGENTS)


def test_every_make_target_agents_md_names_exists_and_does_what_it_says() -> None:
    assert target_problems(AGENTS, MAKEFILE) == []


def test_a_renamed_target_is_caught() -> None:
    """The red case: the same check over a Makefile where the target moved."""
    renamed = MAKEFILE.replace("\ncodex-install:", "\ncodex-skills-install:")
    assert any("codex-install" in p for p in target_problems(AGENTS, renamed))


def test_a_target_running_the_wrong_mode_is_caught() -> None:
    swapped = MAKEFILE.replace("codex-skill-sync.py --install", "codex-skill-sync.py --write")
    assert any("--install" in p for p in target_problems(AGENTS, swapped))


def test_slash_command_names_map_to_the_skill_names_agents_md_states() -> None:
    """AGENTS.md: `/flow:auto` is the skill `flow-auto`, `/project:next` is `project-next`.

    It named `/cpp:init` -> `cpp-init` until this test ran: `cpp/init.md` is in
    codex-skill-sync.py's EXCLUDE, so that skill never existed (issue #1264).
    """
    claimed = {("flow", "auto"): "flow-auto", ("project", "next"): "project-next"}
    for (family, command), skill in claimed.items():
        assert f"`/{family}:{command}`" in AGENTS and f"`{skill}`" in AGENTS, skill
    names = sync.generated_names(["flow", "project"])
    for key, skill in claimed.items():
        assert names.get(key) == skill, (key, names.get(key))
        assert (ROOT / "codex" / "skills" / skill / "SKILL.md").is_file(), skill


def test_every_declared_installer_write_is_under_the_codex_namespace() -> None:
    """AGENTS.md: Codex state lives under `~/.codex/`, never `~/.claude/`.

    Read from the script's HOST-SURFACE declarations, which
    `host-surface-observe.py` re-derives by running it against a sandboxed $HOME,
    so this checks what the installer was OBSERVED to write, not what it says.
    """
    assert "`make codex-install` writes only under `~/.codex/`" in AGENTS
    surfaces = re.findall(r"^#: HOST-SURFACE: (\S+)", SYNC.read_text(encoding="utf-8"), re.MULTILINE)
    assert surfaces, "no HOST-SURFACE declarations read - the extraction is blind"
    outside = [s for s in surfaces if s != "~/.codex" and not s.startswith("~/.codex/")]
    assert outside == [], outside
    assert sync.install_dest_root() == Path.home() / ".codex" / "skills"
