"""Regression tests for the Codex per-harness prompt generator (issue #446).

Multi-harness single-source generation (epic #417 Phase C, ADR 0001 section 5):
`.claude/commands/<family>/*.md` is the single source of truth and
`scripts/codex-prompt-sync.py` emits checked-in Codex CLI custom prompts under
`codex/prompts/<family>-<command>.md`. This replaces the retired
scripts/codex-skill-gen.py wrapper generator.

The hazards these pin:
  * the checked-in prompts must stay in sync with their command source
    (the real-repo --check below IS the CI drift gate);
  * the generator must only ever manage files carrying its GENERATED marker -
    hand-curated prompts (codex/prompts/cpp-memory.md, issue #433) must never
    be overwritten or orphan-deleted;
  * the `codex` family must never be generated (Codex prompts that orchestrate
    the Codex CLI itself are circular);
  * slash references must rewrite only to prompts that actually exist in the
    Codex surface (/flow:eli5 -> /flow-eli5, but /cpp:init stays untouched).

Hermetic and git-free: unit tests run against tmp_path trees via monkeypatched
module roots; the real-repo tests only read checked-in files. Runs in CI's
git-less validate container (see the cpp_validate_container_no_git learning).
"""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "codex-prompt-sync.py"
_spec = spec_from_file_location("codex_prompt_sync", _script_path)
codex_prompt_sync = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(codex_prompt_sync)  # type: ignore[union-attr]
sys.modules["codex_prompt_sync"] = codex_prompt_sync


# ---------------------------------------------------------------------------
# Real-repo pins (this is the CI drift gate)
# ---------------------------------------------------------------------------


def test_real_repo_prompts_in_sync():
    """codex/prompts/ must match what the generator produces from source."""
    assert codex_prompt_sync.main(["--check"]) == 0


def test_real_repo_generated_files_carry_marker():
    for family in codex_prompt_sync.FAMILIES:
        for f in (ROOT / "codex" / "prompts").glob(f"{family}-*.md"):
            if f.name == "cpp-memory.md":
                continue
            first = f.read_text().splitlines()[0]
            assert first.startswith(codex_prompt_sync.MARKER_PREFIX), f.name


def test_real_repo_curated_prompt_is_unmanaged():
    curated = ROOT / "codex" / "prompts" / "cpp-memory.md"
    assert curated.is_file()
    assert not codex_prompt_sync.is_managed(curated)


def test_real_repo_codex_family_not_generated():
    assert "codex" not in codex_prompt_sync.FAMILIES
    assert not list((ROOT / "codex" / "prompts").glob("codex-*.md"))


def test_real_repo_excluded_commands_not_generated():
    prompts = ROOT / "codex" / "prompts"
    assert not (prompts / "cpp-init.md").is_file()
    assert not (prompts / "cpp-status.md").is_file()
    assert not (prompts / "cpp-update.md").is_file()
    # self-improvement/memory.md ships as the curated cpp-memory.md instead.
    assert not (prompts / "self-improvement-memory.md").is_file()


def test_real_repo_families_match_plugin_sync():
    """FAMILIES must stay the plugin-sync set minus `codex` (ADR 0001)."""
    plugin_sync = (ROOT / "scripts" / "plugin-sync.sh").read_text()
    for family in codex_prompt_sync.FAMILIES:
        assert family in plugin_sync, f"{family} missing from plugin-sync.sh"


# ---------------------------------------------------------------------------
# Unit tests on a hermetic tmp tree
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    """A minimal source tree with two families, wired into the module."""
    src = tmp_path / ".claude" / "commands"
    (src / "flow").mkdir(parents=True)
    (src / "qa").mkdir(parents=True)
    out = tmp_path / "codex" / "prompts"
    out.mkdir(parents=True)

    (src / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nRun /flow:eli5 then /qa:test then /cpp:init.\n"
        "Uses the EnterWorktree tool.\n"
    )
    (src / "qa" / "test.md").write_text(
        "---\ndescription: QA test\nallowed-tools: Bash(make:*)\n---\n"
        "# QA Test\n\nPlain body, no Claude-only surfaces here.\n"
    )

    monkeypatch.setattr(codex_prompt_sync, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(codex_prompt_sync, "SOURCE_ROOT", src)
    monkeypatch.setattr(codex_prompt_sync, "OUTPUT_ROOT", out)
    monkeypatch.setattr(codex_prompt_sync, "FAMILIES", ["flow", "qa"])
    monkeypatch.setattr(codex_prompt_sync, "EXCLUDE", {})
    return tmp_path


def test_write_generates_expected_files(tmp_repo):
    assert codex_prompt_sync.main(["--write"]) == 0
    out = tmp_repo / "codex" / "prompts"
    assert (out / "flow-auto.md").is_file()
    assert (out / "qa-test.md").is_file()


def test_frontmatter_is_stripped(tmp_repo):
    codex_prompt_sync.main(["--write"])
    content = (tmp_repo / "codex" / "prompts" / "qa-test.md").read_text()
    assert "allowed-tools" not in content
    assert "# QA Test" in content


def test_slash_refs_rewrite_only_generated_targets(tmp_repo):
    codex_prompt_sync.main(["--write"])
    content = (tmp_repo / "codex" / "prompts" / "flow-auto.md").read_text()
    assert "/flow-eli5" not in content  # eli5 has no source file here
    assert "/qa-test" in content        # qa/test.md is generated
    assert "/cpp:init" in content       # unknown target left untouched


def test_slash_refs_rewrite_known_sibling(tmp_repo):
    src = tmp_repo / ".claude" / "commands" / "flow"
    (src / "eli5.md").write_text("# ELI5\n\nGate.\n")
    codex_prompt_sync.main(["--write"])
    content = (tmp_repo / "codex" / "prompts" / "flow-auto.md").read_text()
    assert "/flow-eli5" in content
    assert "/flow:eli5" not in content


def test_harness_note_only_when_claude_only_surfaces(tmp_repo):
    codex_prompt_sync.main(["--write"])
    out = tmp_repo / "codex" / "prompts"
    assert "Codex harness note" in (out / "flow-auto.md").read_text()
    assert "Codex harness note" not in (out / "qa-test.md").read_text()


def test_check_detects_missing_drift_and_orphan(tmp_repo, capsys):
    out = tmp_repo / "codex" / "prompts"
    assert codex_prompt_sync.main(["--check"]) == 1  # nothing generated yet

    codex_prompt_sync.main(["--write"])
    assert codex_prompt_sync.main(["--check"]) == 0

    (out / "flow-auto.md").write_text("tampered\n")
    assert codex_prompt_sync.main(["--check"]) == 1
    assert "DRIFT" in capsys.readouterr().out

    codex_prompt_sync.main(["--write"])
    marker = codex_prompt_sync.marker_for("flow", "gone.md")
    (out / "flow-gone.md").write_text(f"{marker}\nstale\n")
    assert codex_prompt_sync.main(["--check"]) == 1
    assert "ORPHAN" in capsys.readouterr().out


def test_write_removes_managed_orphans_only(tmp_repo):
    out = tmp_repo / "codex" / "prompts"
    marker = codex_prompt_sync.marker_for("flow", "gone.md")
    (out / "flow-gone.md").write_text(f"{marker}\nstale\n")
    (out / "flow-curated.md").write_text("Hand-written, no marker.\n")
    codex_prompt_sync.main(["--write"])
    assert not (out / "flow-gone.md").exists()
    assert (out / "flow-curated.md").is_file()


def test_curated_prompt_never_flagged_as_orphan(tmp_repo, capsys):
    out = tmp_repo / "codex" / "prompts"
    (out / "flow-curated.md").write_text("Hand-written, no marker.\n")
    codex_prompt_sync.main(["--write"])
    assert codex_prompt_sync.main(["--check"]) == 0


def test_family_subset_ignores_other_families(tmp_repo):
    codex_prompt_sync.main(["--write"])
    out = tmp_repo / "codex" / "prompts"
    (out / "qa-test.md").write_text("tampered\n")
    # flow-only check must not look at qa outputs.
    assert codex_prompt_sync.main(["--check", "flow"]) == 0
    assert codex_prompt_sync.main(["--check", "qa"]) == 1


def test_unknown_family_is_usage_error(tmp_repo):
    assert codex_prompt_sync.main(["--check", "nonesuch"]) == 2


def test_strip_frontmatter_passthrough_without_block():
    body = "# Title\n\nNo frontmatter.\n"
    assert codex_prompt_sync.strip_frontmatter(body) == body


def test_generation_is_deterministic(tmp_repo):
    codex_prompt_sync.main(["--write"])
    out = tmp_repo / "codex" / "prompts"
    first = {f.name: f.read_text() for f in out.glob("*.md")}
    codex_prompt_sync.main(["--write"])
    second = {f.name: f.read_text() for f in out.glob("*.md")}
    assert first == second
