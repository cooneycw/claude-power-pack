"""Tests for Codex skill wrapper generation."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from textwrap import dedent

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
        assert "name: claude-power-pack-test-skill" in content
        assert "description: Testing frontmatter output. Use for: verify" in content
        assert "metadata:" in content
        assert "  source: claude-power-pack/.claude/skills/test.md" in content


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
