"""Regression tests for the Codex SKILL.md skill generator (issue #555).

Hybrid single-SoT bridge (codex-power-pack epic cooneycw/codex-power-pack#64,
story B1): `.claude/commands/<family>/*.md` is the single source of truth and
`scripts/codex-skill-sync.py` emits checked-in per-command Codex skill
directories under `codex/skills/<family>-<command>/`. This surface superseded
the flat custom prompts from `scripts/codex-prompt-sync.py` (issue #446), which
were retired at the issue #556 cutover.

The hazards these pin:
  * the checked-in skills must stay in sync with their command source
    (the real-repo --check below IS the CI drift gate);
  * the generator must only ever manage skill dirs whose SKILL.md carries its
    GENERATED marker - hand-curated skill dirs must never be overwritten,
    pruned, or orphan-deleted;
  * SKILL.md frontmatter must stay valid YAML whatever the source description
    contains (the retired codex-skill-gen.py's #312 quoting bug);
  * the `codex` family must never be generated (Codex skills that orchestrate
    the Codex CLI itself are circular);
  * bundled helper scripts must be byte-identical copies of scripts/<name>;
  * slash references must rewrite only to skills that actually exist in the
    Codex surface (/flow:eli5 -> /flow-eli5, but /cpp:init stays untouched).

Hermetic and git-free: unit tests run against tmp_path trees via monkeypatched
module roots; the real-repo tests only read checked-in files. Runs in CI's
git-less validate container (see the cpp_validate_container_no_git learning).
"""

from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "codex-skill-sync.py"
_spec = spec_from_file_location("codex_skill_sync", _script_path)
codex_skill_sync = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(codex_skill_sync)  # type: ignore[union-attr]
sys.modules["codex_skill_sync"] = codex_skill_sync


# ---------------------------------------------------------------------------
# Real-repo pins (this is the CI drift gate)
# ---------------------------------------------------------------------------


def test_real_repo_skills_in_sync():
    """codex/skills/ must match what the generator produces from source."""
    assert codex_skill_sync.main(["--check"]) == 0


def test_real_repo_skill_dirs_are_managed():
    skills_root = ROOT / "codex" / "skills"
    for family in codex_skill_sync.FAMILIES:
        for d in skills_root.glob(f"{family}-*"):
            if d.is_dir():
                assert codex_skill_sync.is_managed(d), d.name


def test_real_repo_frontmatter_is_valid():
    """Every generated SKILL.md opens with parseable name/description
    frontmatter followed by the GENERATED marker (issue #312 lesson)."""
    for skill_md in sorted((ROOT / "codex" / "skills").glob("*/SKILL.md")):
        lines = skill_md.read_text().splitlines()
        assert lines[0] == "---", skill_md
        assert lines[1].startswith("name: "), skill_md
        assert lines[2].startswith("description: "), skill_md
        assert lines[3] == "---", skill_md
        assert lines[4].startswith(codex_skill_sync.MARKER_PREFIX), skill_md
        name = json.loads(lines[1][len("name: "):])
        description = json.loads(lines[2][len("description: "):])
        assert name == skill_md.parent.name
        assert description.strip()


def test_real_repo_codex_family_not_generated():
    assert "codex" not in codex_skill_sync.FAMILIES
    assert not list((ROOT / "codex" / "skills").glob("codex-*"))


def test_real_repo_excluded_commands_not_generated():
    skills = ROOT / "codex" / "skills"
    assert not (skills / "cpp-init").exists()
    assert not (skills / "cpp-status").exists()
    assert not (skills / "cpp-update").exists()
    # self-improvement/memory.md ships as the curated prompt codex/cpp-memory.md
    # (relocated out of the retired codex/prompts/ flat surface at the #556 cutover).
    assert not (skills / "self-improvement-memory").exists()


def test_real_repo_bundled_scripts_byte_identical():
    for bundled in sorted((ROOT / "codex" / "skills").glob("*/scripts/*")):
        source = ROOT / "scripts" / bundled.name
        assert source.is_file(), bundled
        assert bundled.read_bytes() == source.read_bytes(), bundled


def test_real_repo_folded_top_level_commands_generated():
    # #582: the six loose top-level commands were folded into families so the
    # Codex surface actually delivers them.
    skills = ROOT / "codex" / "skills"
    for name in [
        "project-next",
        "project-lite",
        "cpp-dockers",
        "cpp-happy-check",
        "cpp-load-best-practices",
        "cpp-load-mcp-docs",
    ]:
        assert (skills / name / "SKILL.md").is_file(), f"missing generated skill {name}"


def test_real_repo_no_top_level_source_commands():
    # #582 completeness invariant: discovery globs .claude/commands/<family>/
    # only, so a top-level *.md is invisible to every drift check.
    loose = sorted(p.name for p in (ROOT / ".claude" / "commands").glob("*.md"))
    assert loose == [], f"top-level commands are invisible to packaging: {loose}"


# ---------------------------------------------------------------------------
# Unit tests on a hermetic tmp tree
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    """A minimal source tree with two families, wired into the module."""
    src = tmp_path / ".claude" / "commands"
    (src / "flow").mkdir(parents=True)
    (src / "qa").mkdir(parents=True)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    out = tmp_path / "codex" / "skills"
    out.mkdir(parents=True)

    (src / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nRun /flow:eli5 then /qa:test then /cpp:init.\n"
        "Uses the EnterWorktree tool and scripts/helper.sh; also mentions\n"
        "scripts/absent.sh which does not exist.\n"
    )
    (src / "qa" / "test.md").write_text(
        "---\ndescription: QA test\nallowed-tools: Bash(make:*)\n---\n"
        "# QA Test\n\nPlain body, no Claude-only surfaces here.\n"
    )
    (scripts / "helper.sh").write_text("#!/bin/bash\necho helper\n")
    (scripts / "helper.sh").chmod(0o755)

    monkeypatch.setattr(codex_skill_sync, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(codex_skill_sync, "SOURCE_ROOT", src)
    monkeypatch.setattr(codex_skill_sync, "SCRIPTS_ROOT", scripts)
    monkeypatch.setattr(codex_skill_sync, "OUTPUT_ROOT", out)
    monkeypatch.setattr(codex_skill_sync, "FAMILIES", ["flow", "qa"])
    monkeypatch.setattr(codex_skill_sync, "EXCLUDE", {})
    return tmp_path


def _skill_md(tmp_repo: Path, skill: str) -> str:
    return (tmp_repo / "codex" / "skills" / skill / "SKILL.md").read_text()


def test_write_generates_skill_dirs(tmp_repo):
    assert codex_skill_sync.main(["--write"]) == 0
    out = tmp_repo / "codex" / "skills"
    assert (out / "flow-auto" / "SKILL.md").is_file()
    assert (out / "qa-test" / "SKILL.md").is_file()


def test_frontmatter_name_and_description(tmp_repo):
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "qa-test").splitlines()
    assert lines[0] == "---"
    assert json.loads(lines[1][len("name: "):]) == "qa-test"
    assert json.loads(lines[2][len("description: "):]) == "QA test"
    assert lines[3] == "---"
    assert lines[4].startswith(codex_skill_sync.MARKER_PREFIX)
    assert "allowed-tools" not in _skill_md(tmp_repo, "qa-test")


def test_description_fallback_title_plus_paragraph(tmp_repo):
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "flow-auto").splitlines()
    description = json.loads(lines[2][len("description: "):])
    assert description.startswith("Flow Auto - Run /flow")


def test_description_capped_with_front_loaded_trigger_words(tmp_repo):
    src = tmp_repo / ".claude" / "commands" / "qa"
    long_tail = "very " * 80
    (src / "test.md").write_text(
        f"---\ndescription: QA test triggers first {long_tail}end\n---\n# QA Test\n\nBody.\n"
    )
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "qa-test").splitlines()
    description = json.loads(lines[2][len("description: "):])
    assert description.startswith("QA test triggers first")
    assert description.endswith(" ...")
    assert len(description) <= codex_skill_sync.DESCRIPTION_MAX + len(" ...")


def test_frontmatter_stays_valid_yaml_with_hostile_description(tmp_repo):
    """Colons and quotes in the source description must not break the
    frontmatter (issue #312)."""
    src = tmp_repo / ".claude" / "commands" / "qa"
    (src / "test.md").write_text(
        '---\ndescription: QA: runs "checks" - a: b\n---\n# QA Test\n\nBody.\n'
    )
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "qa-test").splitlines()
    assert json.loads(lines[2][len("description: "):]) == 'QA: runs "checks" - a: b'


def test_adaptations_block_only_when_constructs_detected(tmp_repo):
    codex_skill_sync.main(["--write"])
    flow = _skill_md(tmp_repo, "flow-auto")
    qa = _skill_md(tmp_repo, "qa-test")
    assert "Codex harness adaptations" in flow
    assert "EnterWorktree" in flow  # the worktree bullet was selected
    assert "Codex harness adaptations" not in qa


def test_referenced_script_bundled_byte_identical(tmp_repo):
    codex_skill_sync.main(["--write"])
    bundled = tmp_repo / "codex" / "skills" / "flow-auto" / "scripts" / "helper.sh"
    assert bundled.read_bytes() == (tmp_repo / "scripts" / "helper.sh").read_bytes()
    assert "bundled under `scripts/`" in _skill_md(tmp_repo, "flow-auto")
    # A reference to a script that does not exist is skipped, not an error.
    assert not (tmp_repo / "codex" / "skills" / "flow-auto" / "scripts" / "absent.sh").exists()
    # Commands referencing no scripts get no scripts/ dir at all.
    assert not (tmp_repo / "codex" / "skills" / "qa-test" / "scripts").exists()


def test_slash_refs_rewrite_only_generated_targets(tmp_repo):
    codex_skill_sync.main(["--write"])
    content = _skill_md(tmp_repo, "flow-auto")
    assert "/flow-eli5" not in content  # eli5 has no source file here
    assert "/qa-test" in content        # qa/test.md is generated
    assert "/cpp:init" in content       # unknown target left untouched


def test_slash_refs_rewrite_known_sibling(tmp_repo):
    src = tmp_repo / ".claude" / "commands" / "flow"
    (src / "eli5.md").write_text("# ELI5\n\nGate.\n")
    codex_skill_sync.main(["--write"])
    content = _skill_md(tmp_repo, "flow-auto")
    assert "/flow-eli5" in content
    assert "/flow:eli5" not in content


def test_short_body_inlines_no_reference_md(tmp_repo):
    codex_skill_sync.main(["--write"])
    skill_dir = tmp_repo / "codex" / "skills" / "qa-test"
    assert "Plain body" in _skill_md(tmp_repo, "qa-test")
    assert not (skill_dir / "reference.md").exists()


def test_long_body_splits_to_reference_md(tmp_repo):
    src = tmp_repo / ".claude" / "commands" / "qa"
    filler = "\n".join(f"Step {i}: do the thing." for i in range(200))
    (src / "test.md").write_text(f"# QA Test\n\nLong procedure.\n\n{filler}\n")
    codex_skill_sync.main(["--write"])
    skill_dir = tmp_repo / "codex" / "skills" / "qa-test"
    skill_md = _skill_md(tmp_repo, "qa-test")
    reference = (skill_dir / "reference.md").read_text()
    assert "Read `reference.md`" in skill_md
    assert "Step 199" not in skill_md
    assert "Step 199: do the thing." in reference
    assert reference.startswith(codex_skill_sync.MARKER_PREFIX)


def test_check_detects_missing_drift_stale_and_orphan(tmp_repo, capsys):
    out = tmp_repo / "codex" / "skills"
    assert codex_skill_sync.main(["--check"]) == 1  # nothing generated yet

    codex_skill_sync.main(["--write"])
    assert codex_skill_sync.main(["--check"]) == 0

    skill_md = out / "qa-test" / "SKILL.md"
    pristine = skill_md.read_text()
    skill_md.write_text(pristine + "tampered\n")
    assert codex_skill_sync.main(["--check"]) == 1
    assert "DRIFT" in capsys.readouterr().out
    skill_md.write_text(pristine)

    stale = out / "flow-auto" / "scripts" / "stale.sh"
    stale.write_text("echo stale\n")
    assert codex_skill_sync.main(["--check"]) == 1
    assert "STALE" in capsys.readouterr().out
    stale.unlink()

    orphan = out / "flow-gone"
    orphan.mkdir()
    marker = codex_skill_sync.marker_for("flow", "gone.md")
    (orphan / "SKILL.md").write_text(f"{marker}\nstale\n")
    assert codex_skill_sync.main(["--check"]) == 1
    assert "ORPHAN" in capsys.readouterr().out


def test_write_prunes_stale_files_and_managed_orphans_only(tmp_repo):
    out = tmp_repo / "codex" / "skills"
    codex_skill_sync.main(["--write"])

    stale = out / "flow-auto" / "scripts" / "stale.sh"
    stale.write_text("echo stale\n")
    orphan = out / "flow-gone"
    orphan.mkdir()
    marker = codex_skill_sync.marker_for("flow", "gone.md")
    (orphan / "SKILL.md").write_text(f"{marker}\nstale\n")
    curated = out / "flow-curated"
    curated.mkdir()
    (curated / "SKILL.md").write_text("Hand-written, no marker.\n")

    codex_skill_sync.main(["--write"])
    assert not stale.exists()
    assert not orphan.exists()
    assert (curated / "SKILL.md").is_file()


def test_curated_skill_dir_never_flagged(tmp_repo):
    out = tmp_repo / "codex" / "skills"
    curated = out / "flow-curated"
    curated.mkdir()
    (curated / "SKILL.md").write_text("Hand-written, no marker.\n")
    (curated / "notes.md").write_text("Extra curated file.\n")
    codex_skill_sync.main(["--write"])
    assert codex_skill_sync.main(["--check"]) == 0
    assert (curated / "notes.md").is_file()


def test_is_managed_sees_marker_behind_frontmatter(tmp_repo):
    codex_skill_sync.main(["--write"])
    assert codex_skill_sync.is_managed(tmp_repo / "codex" / "skills" / "qa-test")
    curated = tmp_repo / "codex" / "skills" / "curated"
    curated.mkdir()
    (curated / "SKILL.md").write_text("---\nname: x\n---\nNo marker here.\n")
    assert not codex_skill_sync.is_managed(curated)


def test_family_subset_ignores_other_families(tmp_repo):
    codex_skill_sync.main(["--write"])
    skill_md = tmp_repo / "codex" / "skills" / "qa-test" / "SKILL.md"
    skill_md.write_text(skill_md.read_text() + "tampered\n")
    # flow-only check must not look at qa outputs.
    assert codex_skill_sync.main(["--check", "flow"]) == 0
    assert codex_skill_sync.main(["--check", "qa"]) == 1


def test_unknown_family_is_usage_error(tmp_repo):
    assert codex_skill_sync.main(["--check", "nonesuch"]) == 2


def test_generation_is_deterministic(tmp_repo):
    codex_skill_sync.main(["--write"])
    out = tmp_repo / "codex" / "skills"
    first = {f.as_posix(): f.read_text() for f in out.rglob("*") if f.is_file()}
    codex_skill_sync.main(["--write"])
    second = {f.as_posix(): f.read_text() for f in out.rglob("*") if f.is_file()}
    assert first == second


# ---------------------------------------------------------------------------
# Completeness gate (#582): sources outside every family fail --check loudly
# ---------------------------------------------------------------------------


def test_completeness_flags_top_level_command(tmp_repo):
    codex_skill_sync.main(["--write"])
    (tmp_repo / ".claude" / "commands" / "stray.md").write_text("# stray\n")
    assert codex_skill_sync.main(["--check"]) == 1


def test_completeness_allows_top_level_exclusion(tmp_repo, monkeypatch):
    codex_skill_sync.main(["--write"])
    (tmp_repo / ".claude" / "commands" / "stray.md").write_text("# stray\n")
    monkeypatch.setattr(codex_skill_sync, "TOP_LEVEL_EXCLUDE", {"stray.md"})
    assert codex_skill_sync.main(["--check"]) == 0


def test_completeness_flags_unlisted_family(tmp_repo):
    codex_skill_sync.main(["--write"])
    rogue = tmp_repo / ".claude" / "commands" / "rogue"
    rogue.mkdir()
    (rogue / "x.md").write_text("# x\n")
    assert codex_skill_sync.main(["--check"]) == 1


def test_completeness_allows_unpackaged_family(tmp_repo):
    codex_skill_sync.main(["--write"])
    # `spec` is in the module-default UNPACKAGED_FAMILIES carve-out.
    spec = tmp_repo / ".claude" / "commands" / "spec"
    spec.mkdir()
    (spec / "adopt.md").write_text("# adopt\n")
    assert codex_skill_sync.main(["--check"]) == 0
