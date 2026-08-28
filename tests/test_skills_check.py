"""Behavioral tests for the read-only topic-skill validator (issue #720).

The fixtures are deliberately hermetic. Host-local ``.agents/skills`` content
is gitignored and may be absent, stale, or user-authored, so no real-repo test
is allowed to derive its verdict from that machine-specific state.
"""

from __future__ import annotations

import os
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "skills-check.py"
_spec = spec_from_file_location("skills_check", _script_path)
skills_check = module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["skills_check"] = skills_check
_spec.loader.exec_module(skills_check)  # type: ignore[union-attr]


EXPECTED_LOADING_METADATA = {
    "boot": {
        "name": "Boot",
        "description": "Menu-driven session identity registration for Kyle-compatible local-network discovery",
        "trigger": "boot, register, identity, session type, kyle",
    },
    "best-practices": {
        "name": "Best Practices Dispatcher",
        "description": "Routes to topic-specific best practices skills for context efficiency",
        "trigger": "best practices, claude code help, how to, tips",
    },
    # Conversion exception: the flat source had no frontmatter. These values
    # make its existing heading, opening summary, and tool vocabulary loadable.
    "browser-tiered": {
        "name": "Tiered Browser Automation",
        "description": (
            "Use bdg CLI for lightweight operations, escalating to Playwright MCP "
            "for complex workflows"
        ),
        "trigger": "browser automation, bdg, Playwright MCP, browser testing, screenshots, PDF",
    },
    "cicd-verification": {
        "name": "CI/CD & Verification",
        "description": "Build system, health checks, CI/CD pipeline, and container patterns",
        "trigger": (
            "CI/CD, pipeline, health check, smoke test, Makefile generation, GitHub Actions, "
            "Dockerfile, docker-compose, verification, post-deploy"
        ),
    },
    "claude-md-config": {
        "name": "CLAUDE.md Configuration",
        "description": "CLAUDE.md structure, optimization, and best practices",
        "trigger": "CLAUDE.md, configuration, project setup, conventions",
    },
    "code-quality": {
        "name": "Code Quality",
        "description": "Code review patterns, testing, and quality best practices",
        "trigger": "code review, quality, testing, production ready, best practices",
    },
    "context-efficiency": {
        "name": "Context Efficiency",
        "description": "Progressive disclosure, token budgets, and optimization techniques",
        "trigger": "context, tokens, optimization, token budget, progressive disclosure",
    },
    "documentation": {
        "name": "Documentation & Diagrams",
        "description": (
            "Generate C4 architecture diagrams (GitHub-renderable Mermaid) and PowerPoint "
            "presentations (PPTX via the native Anthropic pptx skill)"
        ),
        "trigger": (
            "documentation, c4, c4 diagram, architecture diagram, update docs, powerpoint, "
            "pptx, diagram, flowchart, sequence diagram, org chart, timeline, mind map, "
            "presentation, slides"
        ),
    },
    # Conversion exception: name and trigger were absent. The pre-existing
    # description and globs remain exact and the new fields expose its purpose.
    "evaluate": {
        "name": "Evaluation Domain Prompts",
        "description": (
            "Domain-aware evaluation prompts for multi-model analysis. Provides structured "
            "prompts for Phase 1 (divergence scan) and Phase 3 (validation) across 5 domain types."
        ),
        "trigger": (
            "evaluate, multi-model analysis, divergence scan, validation, architecture, "
            "concept, algorithm, ui-design, workflow"
        ),
        "globs": ".claude/commands/evaluate/**",
    },
    "hooks-automation": {
        "name": "Hooks & Automation",
        "description": "Hook types, lifecycle, and automation patterns",
        "trigger": "hooks, automation, hook lifecycle, SessionStart, UserPromptSubmit",
    },
    "idd-workflow": {
        "name": "Issue-Driven Development",
        "description": "IDD workflow with git worktrees and issue hierarchy",
        "trigger": "issue driven, worktree, IDD, parallel development, git worktree",
    },
    "infrastructure-hardening": {
        "name": "Infrastructure Hardening",
        "description": (
            "Validation gates, runtime contracts, canary validation, sentinel files for "
            "infrastructure resilience"
        ),
        "trigger": (
            "repeated failure, infrastructure hardening, validation gate, runtime contract, "
            "canary validation, sentinel file, pipeline hardening, SRE pattern"
        ),
    },
    "mcp-optimization": {
        "name": "MCP Optimization",
        "description": "MCP token optimization, Code-Mode, and tool selection",
        "trigger": "MCP, token consumption, tool optimization, code-mode",
    },
    # Conversion exception: the flat source had no frontmatter. These values
    # are lifted from its heading, purpose sentence, and Trigger Patterns list.
    "project-deploy": {
        "name": "Project Deployment",
        "description": "Deploy and test changes in projects with deployment scripts",
        "trigger": (
            "deploy, start servers, run locally, test changes, restart dev, restart servers"
        ),
    },
    "python-packaging": {
        "name": "Python Packaging (PEP 621 & PEP 723)",
        "description": (
            "Modern Python project configuration with pyproject.toml and inline script metadata"
        ),
        "trigger": (
            "pyproject.toml, PEP 621, PEP 723, setup.py, requirements.txt, python packaging, "
            "dependencies, uv init, inline script"
        ),
    },
    "secrets": {
        "name": "Secrets Management",
        "description": "Secure credential access with tiered providers, output masking, and web UI",
        "trigger": (
            "secrets, credentials, database password, api key, aws secrets, environment "
            "variables, .env, get credentials, connection string, secret management"
        ),
    },
    "session-management": {
        "name": "Session Management",
        "description": "Session resets, context degradation, and plan mode best practices",
        "trigger": "session, reset, plan mode, context degradation, compacting",
    },
    "spec-driven-dev": {
        "name": "Spec-Driven Development",
        "description": "Specification-first development workflow and planning",
        "trigger": "spec driven, specification, SDD, planning, requirements",
    },
}


def _provenance_lines(provenance_class: str = "cpp-authored") -> list[str]:
    return ["metadata:", "  provenance:", f"    class: {provenance_class}"]


def _write_skill(
    root: Path,
    slug: str = "sample",
    *,
    body: str = "# Sample\n\nCanonical body.\n",
    provenance_lines: list[str] | None = None,
    source: str | None = None,
) -> Path:
    skill_dir = root / ".claude" / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"name: {slug}",
        f"description: {slug} fixture",
        f"trigger: {slug}",
    ]
    if source is not None:
        lines.extend(["metadata:", f"  source: {source}", "  provenance:", "    class: cpp-authored"])
    else:
        lines.extend(provenance_lines or _provenance_lines())
    lines.extend(["---", ""])
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text("\n".join(lines) + body, encoding="utf-8")
    return skill_path


def _codes(report) -> list[str]:
    return [finding.code for finding in report.findings]


def test_conversion_preserves_enumerated_loading_metadata():
    """Every known flat skill became the same-slug package losslessly.

    The three source defects found at the implementation gate are explicit in
    EXPECTED_LOADING_METADATA above; all other values are the pre-conversion
    values verbatim. Comparing the complete non-provenance mapping prevents a
    loading-relevant field from silently disappearing.
    """
    skills_root = ROOT / ".claude" / "skills"
    assert not list(skills_root.glob("*.md"))
    packages = {path.parent.name: path for path in skills_root.glob("*/SKILL.md")}
    assert set(packages) == set(EXPECTED_LOADING_METADATA)

    for slug, expected in EXPECTED_LOADING_METADATA.items():
        metadata, _ = skills_check.parse_frontmatter(packages[slug].read_text(encoding="utf-8"))
        provenance = metadata.pop("metadata")
        assert provenance == {"provenance": {"class": "cpp-authored"}}, slug
        assert metadata == expected, slug


def test_missing_provenance_rejects_unattributed_grill_me_fixture(tmp_path):
    # The failure is general, but this literal fixture pins the acceptance
    # criterion: calling content vendored is insufficient attribution.
    _write_skill(
        tmp_path,
        "grill-me",
        provenance_lines=_provenance_lines("vendored"),
    )
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["INVALID_PROVENANCE"]
    detail = report.findings[0].detail
    for field_name in skills_check.UPSTREAM_FIELDS:
        assert field_name in detail


def test_false_vendored_attribution_rejects_cpp_as_its_own_upstream(tmp_path):
    # No real grill-yourself skill exists. This synthetic contradiction proves
    # the general rule without inventing one in the repository surface.
    provenance = [
        "metadata:",
        "  provenance:",
        "    class: vendored",
        "    upstream_author: CPP contributors",
        (
            "    source_url: https://github.com/cooneycw/claude-power-pack/"
            "blob/0123456789abcdef/.claude/skills/grill-yourself/SKILL.md"
        ),
        "    license: MIT",
        "    revision: 0123456789abcdef0123456789abcdef01234567",
        "    local_changes: none",
    ]
    _write_skill(tmp_path, "grill-yourself", provenance_lines=provenance)
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["FALSE_UPSTREAM_ATTRIBUTION"]


def test_stale_mirror_body_drift_fails_read_only_check(tmp_path):
    _write_skill(tmp_path, "sample")
    managed = tmp_path / ".agents" / "skills"
    mirror = _write_skill(
        managed / "mirror-root",
        "sample",
        body="# Sample\n\nStale body with /machine/specific/path.\n",
        source="claude-power-pack/.claude/skills/sample/SKILL.md",
    )
    # Move the package from the fixture helper's canonical-shaped nesting into
    # the external install shape without invoking any checker mutation path.
    installed = managed / "claude-power-pack-sample"
    installed.mkdir(parents=True)
    mirror.rename(installed / "SKILL.md")

    report = skills_check.check_repository(tmp_path, managed)
    assert _codes(report) == ["MANAGED_DRIFT"]
    assert "body differs" in report.findings[0].detail


def test_managed_orphan_with_no_canonical_source_fails(tmp_path):
    _write_skill(tmp_path, "surviving-canonical")
    managed = tmp_path / ".agents" / "skills"
    mirror = _write_skill(
        managed / "mirror-root",
        "retired",
        source="claude-power-pack/.claude/skills/retired/SKILL.md",
    )
    installed = managed / "claude-power-pack-retired"
    installed.mkdir(parents=True)
    mirror.rename(installed / "SKILL.md")

    report = skills_check.check_repository(tmp_path, managed)
    assert _codes(report) == ["MANAGED_ORPHAN"]


def test_protected_user_content_is_unchanged_and_unreported(tmp_path):
    canonical = _write_skill(tmp_path, "sample")
    managed = tmp_path / ".agents" / "skills"
    managed_package = managed / "claude-power-pack-sample"
    managed_package.mkdir(parents=True)
    canonical_text = canonical.read_text(encoding="utf-8")
    managed_text = canonical_text.replace(
        "metadata:\n",
        "metadata:\n  source: claude-power-pack/.claude/skills/sample/SKILL.md\n",
        1,
    )
    (managed_package / "SKILL.md").write_text(managed_text, encoding="utf-8")

    user_package = managed / "my-private-skill"
    user_package.mkdir()
    user_skill = user_package / "SKILL.md"
    user_bytes = (
        b"---\nname: private\ndescription: private\ntrigger: private\n---\n"
        b"# User content\n\n[Private missing note](do-not-inspect.md)\n"
    )
    user_skill.write_bytes(user_bytes)

    # Negative-fixture precondition: the protected content really exists and
    # is writable before the operation whose no-op behavior is under test.
    assert user_skill.is_file()
    assert os.access(user_skill, os.W_OK)
    assert user_skill.read_bytes() == user_bytes

    report = skills_check.check_repository(tmp_path, managed)

    assert report.ok
    assert any("claude-power-pack-sample: clean parity" in note for note in report.notes)
    assert all("my-private-skill" not in note for note in report.notes)
    assert all("my-private-skill" not in str(finding.path) for finding in report.findings)
    assert user_skill.read_bytes() == user_bytes


def test_broken_reference_and_dangling_symlink_fail(tmp_path):
    skill = _write_skill(
        tmp_path,
        body="# Sample\n\n[Missing reference](reference.md)\n",
    )
    dangling = skill.parent / "missing-link.md"
    dangling.symlink_to("also-missing.md")
    assert dangling.is_symlink()
    assert not dangling.exists()

    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["BROKEN_REFERENCE", "BROKEN_REFERENCE"]
    details = "\n".join(finding.detail for finding in report.findings)
    assert "reference.md" in details
    assert "dangling symlink" in details


def test_duplicate_names_and_retired_flat_surface_fail(tmp_path):
    _write_skill(tmp_path, "first")
    second = _write_skill(tmp_path, "second")
    second.write_text(second.read_text().replace("name: second", "name: first"))
    flat = tmp_path / ".claude" / "skills" / "legacy.md"
    flat.write_text("retired wrapper\n")

    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["DUPLICATE_SURFACE", "DUPLICATE_SURFACE"]


def test_real_repo_skills_are_valid_without_host_managed_state(tmp_path):
    """The CI dogfood gate must model a fresh checkout, not this host."""
    absent_managed_root = tmp_path / "fresh-checkout-has-no-agents-skills"
    report = skills_check.check_repository(ROOT, absent_managed_root)
    assert report.ok, [finding.render(ROOT) for finding in report.findings]
    assert any("nothing to check" in note for note in report.notes)
