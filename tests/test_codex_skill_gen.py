"""Tests for Codex skill wrapper generation."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from textwrap import dedent

import yaml

_script_path = Path(__file__).resolve().parent.parent / "scripts" / "codex-skill-gen.py"
_spec = spec_from_file_location("codex_skill_gen", _script_path)
codex_skill_gen = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(codex_skill_gen)  # type: ignore[union-attr]
sys.modules["codex_skill_gen"] = codex_skill_gen

parse_frontmatter = codex_skill_gen.parse_frontmatter
build_description = codex_skill_gen.build_description
slugify = codex_skill_gen.slugify
generate_codex_skill = codex_skill_gen.generate_codex_skill
has_mcp_content = codex_skill_gen.has_mcp_content
rewrite_paths = codex_skill_gen.rewrite_paths
link_workspace_skills = codex_skill_gen.link_workspace_skills
serialize_frontmatter = codex_skill_gen.serialize_frontmatter
validate_frontmatter = codex_skill_gen.validate_frontmatter
FALLBACK_METADATA = codex_skill_gen.FALLBACK_METADATA


class TestParseFrontmatter:
    def test_valid_frontmatter(self) -> None:
        content = dedent("""\
            ---
            name: Test Skill
            description: A test skill
            trigger: test, demo
            ---

            # Body here
        """)
        metadata, body = parse_frontmatter(content)
        assert metadata["name"] == "Test Skill"
        assert metadata["description"] == "A test skill"
        assert metadata["trigger"] == "test, demo"
        assert "# Body here" in body

    def test_no_frontmatter(self) -> None:
        content = "# Just a heading\n\nSome content."
        metadata, body = parse_frontmatter(content)
        assert metadata == {}
        assert body == content

    def test_quoted_values(self) -> None:
        content = '---\nname: "Quoted Name"\ndescription: \'Single quoted\'\n---\nBody'
        metadata, body = parse_frontmatter(content)
        assert metadata["name"] == "Quoted Name"
        assert metadata["description"] == "Single quoted"


class TestSerializeFrontmatter:
    def test_simple_values(self) -> None:
        fm = {"name": "test-skill", "description": "A simple skill"}
        result = serialize_frontmatter(fm)
        parsed = yaml.safe_load(result)
        assert parsed["name"] == "test-skill"
        assert parsed["description"] == "A simple skill"

    def test_colon_in_description(self) -> None:
        fm = {"name": "test", "description": "Patterns. Use for: production ready"}
        result = serialize_frontmatter(fm)
        parsed = yaml.safe_load(result)
        assert parsed["description"] == "Patterns. Use for: production ready"

    def test_nested_metadata(self) -> None:
        fm = {"name": "x", "description": "y", "metadata": {"source": "a/b.md"}}
        result = serialize_frontmatter(fm)
        parsed = yaml.safe_load(result)
        assert parsed["metadata"]["source"] == "a/b.md"

    def test_quotes_in_description(self) -> None:
        fm = {"name": "x", "description": 'Uses "quoted" terms and it\'s fine'}
        result = serialize_frontmatter(fm)
        parsed = yaml.safe_load(result)
        assert parsed["description"] == 'Uses "quoted" terms and it\'s fine'

    def test_special_chars(self) -> None:
        fm = {"name": "x", "description": "Handles (parens), slashes/paths & ampersands"}
        result = serialize_frontmatter(fm)
        parsed = yaml.safe_load(result)
        assert parsed["description"] == "Handles (parens), slashes/paths & ampersands"


class TestValidateFrontmatter:
    def test_valid(self) -> None:
        content = "---\nname: test\ndescription: a skill\n---\nBody"
        validate_frontmatter(content)

    def test_missing_opening(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="Missing opening"):
            validate_frontmatter("name: test\n---\nBody")

    def test_missing_name(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="name is empty"):
            validate_frontmatter("---\ndescription: test\n---\nBody")

    def test_missing_description(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="description is empty"):
            validate_frontmatter("---\nname: test\n---\nBody")


class TestSlugify:
    def test_basic(self) -> None:
        assert slugify("Code Quality") == "code-quality"

    def test_special_chars(self) -> None:
        assert slugify("Hooks & Automation") == "hooks-automation"

    def test_truncation(self) -> None:
        long_name = "A" * 100
        assert len(slugify(long_name)) <= 50

    def test_parentheses(self) -> None:
        assert slugify("Python Packaging (PEP 621 & PEP 723)") == "python-packaging-pep-621-pep-723"


class TestBuildDescription:
    def test_description_with_trigger(self) -> None:
        metadata = {"description": "Code review patterns", "trigger": "code review, testing, production"}
        desc = build_description(metadata)
        assert "Code review patterns" in desc
        assert "testing" in desc
        assert "production" in desc

    def test_no_duplicate_terms(self) -> None:
        metadata = {"description": "Code review patterns and testing", "trigger": "code review, testing"}
        desc = build_description(metadata)
        assert desc.count("testing") == 1

    def test_no_trigger(self) -> None:
        metadata = {"description": "Just a description"}
        desc = build_description(metadata)
        assert desc == "Just a description"


class TestHasMcpContent:
    def test_detects_mcp(self) -> None:
        assert has_mcp_content("Use the MCP server for this")
        assert has_mcp_content("Run /flow:start to begin")
        assert has_mcp_content("Call browser_screenshot")

    def test_no_mcp(self) -> None:
        assert not has_mcp_content("Just regular Python code here")


class TestRewritePaths:
    def test_rewrites_docs_path(self) -> None:
        body = "Read `docs/skills/code-quality.md` for details"
        result = rewrite_paths(body, "/home/user/claude-power-pack")
        assert "`/home/user/claude-power-pack/docs/skills/code-quality.md`" in result

    def test_rewrites_lib_path(self) -> None:
        body = "See `lib/creds/provider.py`"
        result = rewrite_paths(body, "/opt/cpp")
        assert "`/opt/cpp/lib/creds/provider.py`" in result

    def test_ignores_non_relative(self) -> None:
        body = "Use `pip install something`"
        result = rewrite_paths(body, "/opt/cpp")
        assert result == body

    def test_rewrites_scripts_path(self) -> None:
        body = "Run `scripts/drift-detect.sh`"
        result = rewrite_paths(body, "/repo")
        assert "`/repo/scripts/drift-detect.sh`" in result

    def test_rewrites_bare_path(self) -> None:
        body = "Read docs/skills/cicd-verification.md"
        result = rewrite_paths(body, "/opt/cpp")
        assert "/opt/cpp/docs/skills/cicd-verification.md" in result

    def test_rewrites_bare_scripts_path(self) -> None:
        body = "Run scripts/setup.sh to start"
        result = rewrite_paths(body, "/opt/cpp")
        assert "/opt/cpp/scripts/setup.sh" in result

    def test_bare_path_not_double_rewritten(self) -> None:
        body = "See `docs/skills/foo.md` and docs/skills/bar.md"
        result = rewrite_paths(body, "/opt/cpp")
        assert "`/opt/cpp/docs/skills/foo.md`" in result
        assert "/opt/cpp/docs/skills/bar.md" in result
        assert result.count("/opt/cpp/docs/skills/foo.md") == 1


class TestGenerateCodexSkill:
    def test_generates_from_full_frontmatter(self, tmp_path: Path) -> None:
        skill = tmp_path / "code-quality.md"
        skill.write_text(dedent("""\
            ---
            name: Code Quality
            description: Code review patterns, testing, and quality best practices
            trigger: code review, quality, testing, production ready, best practices
            ---

            # Code Quality Skill

            When the user asks about code quality:
            1. Read `docs/skills/code-quality.md`
        """))
        slug, content, filename = generate_codex_skill(skill, "/opt/cpp")
        assert slug == "claude-power-pack-code-quality"
        assert "name: claude-power-pack-code-quality" in content
        assert "Code review patterns" in content
        assert "source: claude-power-pack/.claude/skills/code-quality.md" in content
        assert "`/opt/cpp/docs/skills/code-quality.md`" in content

    def test_generates_with_fallback_metadata(self, tmp_path: Path) -> None:
        skill = tmp_path / "browser-tiered.md"
        skill.write_text("# Tiered Browser Automation\n\nUse bdg for simple tasks.")
        slug, content, filename = generate_codex_skill(skill, "/opt/cpp")
        assert slug == "claude-power-pack-browser-automation-tiered"
        assert "Tiered browser automation" in content
        assert "source: claude-power-pack/.claude/skills/browser-tiered.md" in content

    def test_generates_with_partial_frontmatter(self, tmp_path: Path) -> None:
        skill = tmp_path / "evaluate.md"
        skill.write_text(dedent("""\
            ---
            description: Domain-aware evaluation prompts
            globs: .claude/commands/evaluate/**
            ---

            # Evaluation Domain Prompts
        """))
        slug, content, filename = generate_codex_skill(skill, "/opt/cpp")
        assert "claude-power-pack-evaluation-prompts" in slug
        assert "Domain-aware evaluation prompts" in content

    def test_mcp_notice_added(self, tmp_path: Path) -> None:
        skill = tmp_path / "test-mcp.md"
        skill.write_text(dedent("""\
            ---
            name: MCP Test
            description: Tests MCP integration
            ---

            Use browser_screenshot to capture the page.
            Run /flow:start to begin work.
        """))
        _, content, _ = generate_codex_skill(skill, "/opt/cpp")
        assert "MCP tools are not available in Codex" in content

    def test_no_mcp_notice_for_plain_skill(self, tmp_path: Path) -> None:
        skill = tmp_path / "plain.md"
        skill.write_text(dedent("""\
            ---
            name: Plain Skill
            description: A plain skill with no MCP
            ---

            Just regular guidance content here.
        """))
        _, content, _ = generate_codex_skill(skill, "/opt/cpp")
        assert "MCP tools are not available in Codex" not in content

    def test_description_with_colon_produces_valid_yaml(self, tmp_path: Path) -> None:
        skill = tmp_path / "colon-test.md"
        skill.write_text(dedent("""\
            ---
            name: Code Quality
            description: Code review patterns, testing, and quality best practices
            trigger: code review, quality, testing, production ready, best practices
            ---

            # Code Quality
        """))
        slug, content, _ = generate_codex_skill(skill, "/opt/cpp")
        end = content.find("---", 3)
        fm_text = content[4:end]
        parsed = yaml.safe_load(fm_text)
        assert "Use for:" in parsed["description"]
        assert parsed["name"] == slug

    def test_description_with_quotes_and_parens(self, tmp_path: Path) -> None:
        skill = tmp_path / "special.md"
        skill.write_text(dedent("""\
            ---
            name: Special Chars
            description: Handles "quoted" terms (with parens) & slashes/commas
            ---

            Body.
        """))
        _, content, _ = generate_codex_skill(skill, "/opt/cpp")
        end = content.find("---", 3)
        fm_text = content[4:end]
        parsed = yaml.safe_load(fm_text)
        assert '"quoted"' in parsed["description"]
        assert "(with parens)" in parsed["description"]

    def test_all_real_source_skills_produce_valid_yaml(self) -> None:
        source_dir = Path(__file__).resolve().parent.parent / ".claude" / "skills"
        if not source_dir.is_dir():
            return
        for skill_file in sorted(source_dir.glob("*.md")):
            slug, content, _ = generate_codex_skill(skill_file, "/opt/cpp")
            end = content.find("---", 3)
            fm_text = content[4:end]
            parsed = yaml.safe_load(fm_text)
            assert isinstance(parsed, dict), f"{skill_file.name}: frontmatter is not a mapping"
            assert parsed.get("name"), f"{skill_file.name}: name is empty"
            assert parsed.get("description"), f"{skill_file.name}: description is empty"

    def test_codex_frontmatter_format(self, tmp_path: Path) -> None:
        skill = tmp_path / "test.md"
        skill.write_text(dedent("""\
            ---
            name: Test Skill
            description: Testing frontmatter output
            trigger: test, verify
            ---

            Body content.
        """))
        slug, content, _ = generate_codex_skill(skill, "/opt/cpp")
        assert content.startswith("---\n")
        end = content.find("---", 3)
        parsed = yaml.safe_load(content[4:end])
        assert parsed["name"] == "claude-power-pack-test-skill"
        assert parsed["description"] == "Testing frontmatter output. Use for: verify"
        assert parsed["metadata"]["source"] == "claude-power-pack/.claude/skills/test.md"


class TestEndToEnd:
    def test_full_generation_no_overwrite(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        output = tmp_path / "output"

        (source / "skill-a.md").write_text(dedent("""\
            ---
            name: Skill A
            description: First skill
            ---

            Content A.
        """))
        (source / "skill-b.md").write_text(dedent("""\
            ---
            name: Skill B
            description: Second skill
            ---

            Content B.
        """))

        # Generate first time
        for sf in sorted(source.glob("*.md")):
            slug, content, _ = generate_codex_skill(sf, str(tmp_path))
            target_dir = output / slug
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "SKILL.md").write_text(content)

        assert (output / "claude-power-pack-skill-a" / "SKILL.md").exists()
        assert (output / "claude-power-pack-skill-b" / "SKILL.md").exists()

        # Modify source and verify no overwrite without --force
        original_content = (output / "claude-power-pack-skill-a" / "SKILL.md").read_text()
        (source / "skill-a.md").write_text(dedent("""\
            ---
            name: Skill A
            description: Modified description
            ---

            Modified content.
        """))

        # Simulate no-force: file exists, so skip
        target_file = output / "claude-power-pack-skill-a" / "SKILL.md"
        assert target_file.exists()
        current = target_file.read_text()
        assert current == original_content

    def test_fallback_skills_have_entries(self) -> None:
        assert "browser-tiered.md" in FALLBACK_METADATA
        assert "evaluate.md" in FALLBACK_METADATA
        assert "project-deploy.md" in FALLBACK_METADATA
        for key, meta in FALLBACK_METADATA.items():
            assert "name" in meta
            assert "description" in meta
            assert "trigger" in meta


def _make_skill_dirs(base: Path, names: list[str]) -> None:
    for name in names:
        d = base / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"# {name}\n")


class TestLinkWorkspaceSkills:
    def test_creates_symlinks(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "cpp" / ".agents" / "skills"
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        _make_skill_dirs(cpp_skills, ["claude-power-pack-foo", "claude-power-pack-bar"])

        linked, ok, skipped, stale = link_workspace_skills(cpp_skills, ws_root)
        assert linked == 2
        assert ok == 0
        assert skipped == 0
        assert stale == 0

        link_bar = ws_root / ".agents" / "skills" / "claude-power-pack-bar"
        assert link_bar.is_symlink()
        assert (link_bar / "SKILL.md").read_text() == "# claude-power-pack-bar\n"

    def test_idempotent_rerun(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "cpp" / ".agents" / "skills"
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        _make_skill_dirs(cpp_skills, ["claude-power-pack-foo"])

        link_workspace_skills(cpp_skills, ws_root)
        linked, ok, skipped, stale = link_workspace_skills(cpp_skills, ws_root)
        assert linked == 0
        assert ok == 1

    def test_refuses_to_overwrite_non_symlink(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "cpp" / ".agents" / "skills"
        ws_root = tmp_path / "workspace"
        _make_skill_dirs(cpp_skills, ["claude-power-pack-foo"])
        existing = ws_root / ".agents" / "skills" / "claude-power-pack-foo"
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_text("user content")

        linked, ok, skipped, stale = link_workspace_skills(cpp_skills, ws_root)
        assert linked == 0
        assert skipped == 1
        assert (existing / "SKILL.md").read_text() == "user content"

    def test_detects_stale_symlinks(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "cpp" / ".agents" / "skills"
        ws_root = tmp_path / "workspace"
        _make_skill_dirs(cpp_skills, ["claude-power-pack-foo"])

        link_path = ws_root / ".agents" / "skills" / "claude-power-pack-foo"
        link_path.parent.mkdir(parents=True)
        stale_target = tmp_path / "old-cpp" / "skills" / "claude-power-pack-foo"
        stale_target.mkdir(parents=True)
        link_path.symlink_to(stale_target)

        linked, ok, skipped, stale = link_workspace_skills(cpp_skills, ws_root)
        assert stale == 1
        assert linked == 0

    def test_refresh_replaces_stale(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "cpp" / ".agents" / "skills"
        ws_root = tmp_path / "workspace"
        _make_skill_dirs(cpp_skills, ["claude-power-pack-foo"])

        link_path = ws_root / ".agents" / "skills" / "claude-power-pack-foo"
        link_path.parent.mkdir(parents=True)
        stale_target = tmp_path / "old-cpp" / "skills" / "claude-power-pack-foo"
        stale_target.mkdir(parents=True)
        link_path.symlink_to(stale_target)

        linked, ok, skipped, stale = link_workspace_skills(
            cpp_skills, ws_root, refresh=True,
        )
        assert linked == 1
        assert stale == 0
        assert link_path.resolve() == (cpp_skills / "claude-power-pack-foo").resolve()

    def test_ignores_non_cpp_dirs(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "cpp" / ".agents" / "skills"
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        _make_skill_dirs(cpp_skills, ["claude-power-pack-foo", "other-skill"])

        linked, ok, skipped, stale = link_workspace_skills(cpp_skills, ws_root)
        assert linked == 1
        ws_skills = ws_root / ".agents" / "skills"
        assert (ws_skills / "claude-power-pack-foo").is_symlink()
        assert not (ws_skills / "other-skill").exists()

    def test_no_generated_skills_warns(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "empty"
        cpp_skills.mkdir()
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()

        linked, ok, skipped, stale = link_workspace_skills(cpp_skills, ws_root)
        assert linked == 0
        assert ok == 0

    def test_dry_run_no_side_effects(self, tmp_path: Path) -> None:
        cpp_skills = tmp_path / "cpp" / ".agents" / "skills"
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        _make_skill_dirs(cpp_skills, ["claude-power-pack-foo"])

        linked, ok, skipped, stale = link_workspace_skills(
            cpp_skills, ws_root, dry_run=True,
        )
        assert linked == 1
        assert not (ws_root / ".agents" / "skills" / "claude-power-pack-foo").exists()
