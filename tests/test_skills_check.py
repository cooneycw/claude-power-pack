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
    "best-practices": {
        "name": "best-practices",
        "description": (
            "Routes to topic-specific best practices skills instead of loading them all. Use for Claude Code help, "
            "tips, or a how to question whose topic is not yet obvious."
        ),
        "trigger": "best practices, claude code help, how to, tips",
    },
    "boot": {
        "name": "boot",
        "description": (
            "Menu-driven session identity registration for Kyle-compatible local-network discovery. Use to boot or "
            "register a session, declare a session type, or adopt a kyle fleet identity."
        ),
        "trigger": "boot, register, identity, session type, kyle",
    },
    "browser-tiered": {
        "name": "browser-tiered",
        "description": (
            "Use the bdg CLI for lightweight work and escalate to Playwright MCP for complex flows. Use for browser "
            "automation, browser testing, screenshots, or rendering a page to PDF."
        ),
        "trigger": "browser automation, bdg, Playwright MCP, browser testing, screenshots, PDF",
    },
    "cicd-verification": {
        "name": "cicd-verification",
        "description": (
            "Build system, health check, pipeline and container patterns. Use for CI/CD - a pipeline, Makefile "
            "generation, GitHub Actions, a Dockerfile, docker-compose, a smoke test or post-deploy verification."
        ),
        "trigger": (
            "CI/CD, pipeline, health check, smoke test, Makefile generation, GitHub Actions, Dockerfile, "
            "docker-compose, verification, post-deploy"
        ),
    },
    "claude-md-config": {
        "name": "claude-md-config",
        "description": (
            "CLAUDE.md structure, optimization and conventions. Use when writing or reviewing a CLAUDE.md, during "
            "project setup, or when deciding which configuration belongs in always-loaded guidance."
        ),
        "trigger": "CLAUDE.md, configuration, project setup, conventions",
    },
    "code-quality": {
        "name": "code-quality",
        "description": (
            "Code review, testing and quality patterns. Use when reviewing code, deciding what testing a change "
            "needs, or judging whether it is production ready. Overlaps the general best practices skill."
        ),
        "trigger": "code review, quality, testing, production ready, best practices",
    },
    "context-efficiency": {
        "name": "context-efficiency",
        "description": (
            "Progressive disclosure, token budgets and optimization. Use when context is filling up, when tokens must "
            "be cut to a budget, or when deciding what to load eagerly versus on demand."
        ),
        "trigger": "context, tokens, optimization, token budget, progressive disclosure",
    },
    "documentation": {
        "name": "documentation",
        "description": (
            "Generate C4 architecture diagrams as GitHub-renderable Mermaid, and PowerPoint slides. Use to update "
            "docs, or draw a c4 diagram, flowchart, sequence diagram, org chart, timeline or mind map."
        ),
        "trigger": (
            "documentation, c4, c4 diagram, architecture diagram, update docs, powerpoint, pptx, diagram, flowchart, "
            "sequence diagram, org chart, timeline, mind map, presentation, slides"
        ),
    },
    "evaluate": {
        "name": "evaluate",
        "description": (
            "Domain-aware prompts for multi-model analysis. Use to evaluate an architecture, concept, algorithm, "
            "ui-design or workflow, with a Phase 1 divergence scan and Phase 3 validation."
        ),
        "trigger": (
            "evaluate, multi-model analysis, divergence scan, validation, architecture, concept, algorithm, "
            "ui-design, workflow"
        ),
        "globs": ".claude/commands/evaluate/**",
    },
    "hooks-automation": {
        "name": "hooks-automation",
        "description": (
            "Hook types, lifecycle and automation patterns. Use when adding or debugging hooks such as SessionStart "
            "or UserPromptSubmit, or automating a step that must run on every session."
        ),
        "trigger": "hooks, automation, hook lifecycle, SessionStart, UserPromptSubmit",
    },
    "idd-workflow": {
        "name": "idd-workflow",
        "description": (
            "IDD workflow with git worktrees and issue hierarchy. Use for issue driven development, creating a git "
            "worktree, or running parallel development across several issues at once."
        ),
        "trigger": "issue driven, worktree, IDD, parallel development, git worktree",
    },
    "infrastructure-hardening": {
        "name": "infrastructure-hardening",
        "description": (
            "Validation gates, runtime contracts, canary validation and sentinel files. Use after a repeated failure, "
            "or for infrastructure hardening, pipeline hardening and SRE pattern work."
        ),
        "trigger": (
            "repeated failure, infrastructure hardening, validation gate, runtime contract, canary validation, "
            "sentinel file, pipeline hardening, SRE pattern"
        ),
    },
    "mcp-optimization": {
        "name": "mcp-optimization",
        "description": (
            "MCP token optimization, Code-Mode and tool selection. Use when MCP servers dominate token consumption, "
            "or for tool optimization and deciding which servers to leave enabled."
        ),
        "trigger": "MCP, token consumption, tool optimization, code-mode",
    },
    "project-deploy": {
        "name": "project-deploy",
        "description": (
            "Deploy and exercise changes in projects with deployment scripts. Use to deploy, start servers, restart "
            "dev servers, run locally, or test changes against a running stack."
        ),
        "trigger": "deploy, start servers, run locally, test changes, restart dev, restart servers",
    },
    "python-packaging": {
        "name": "python-packaging",
        "description": (
            "Modern Python project configuration. Use for pyproject.toml, PEP 621, PEP 723 inline script metadata, uv "
            "init, dependencies, or migrating off setup.py and requirements.txt."
        ),
        "trigger": (
            "pyproject.toml, PEP 621, PEP 723, setup.py, requirements.txt, python packaging, dependencies, uv init, "
            "inline script"
        ),
    },
    "secrets": {
        "name": "secrets",
        "description": (
            "Secure credential access with tiered providers, masking and a web UI. Use for secrets, credentials, an "
            "api key, a database password, aws secrets, .env environment variables or a connection string."
        ),
        "trigger": (
            "secrets, credentials, database password, api key, aws secrets, environment variables, .env, get "
            "credentials, connection string, secret management"
        ),
    },
    "session-management": {
        "name": "session-management",
        "description": (
            "Session resets, context degradation and plan mode practice. Use when a session is degrading or "
            "compacting, when deciding whether to reset, or when choosing plan mode."
        ),
        "trigger": "session, reset, plan mode, context degradation, compacting",
    },
    "spec-driven-dev": {
        "name": "spec-driven-dev",
        "description": (
            "Contract-first development, proportional spec routing and planning. Use for spec driven work (SDD) - "
            "writing a specification, capturing requirements, or applying the issue contract."
        ),
        "trigger": "spec driven, specification, SDD, planning, requirements, issue contract",
    },
}


# Distinguishes "the caller said nothing" from "the caller said None", which for
# `trigger` means omit the key - the good half of the UNREACHABLE_TRIGGER control.
_DEFAULT = object()


def _provenance_lines(provenance_class: str = "cpp-authored") -> list[str]:
    return ["metadata:", "  provenance:", f"    class: {provenance_class}"]


def _write_skill(
    root: Path,
    slug: str = "sample",
    *,
    body: str = "# Sample\n\nCanonical body.\n",
    provenance_lines: list[str] | None = None,
    source: str | None = None,
    name: object = _DEFAULT,
    description: object = _DEFAULT,
    trigger: object = _DEFAULT,
) -> Path:
    skill_dir = root / ".claude" / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"name: {slug if name is _DEFAULT else name}",
        f"description: {f'{slug} fixture' if description is _DEFAULT else description}",
    ]
    if trigger is not None:
        lines.append(f"trigger: {slug if trigger is _DEFAULT else trigger}")
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


def test_present_but_empty_skills_directory_is_invalid(tmp_path):
    """#841: a canonical skills/ that exists with nothing in it must not read
    the same as a clean pass - it is not a legitimate state for this repo."""
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["INVALID_SURFACE"]
    assert "no packages" in report.findings[0].detail


def test_conversion_preserves_enumerated_loading_metadata():
    """The always-loaded header of every package is pinned, field by field.

    These are the only two fields an agent reads before deciding whether to open
    a skill, so a silent edit to either changes which skills can fire. The dict
    is a hand-maintained snapshot ON PURPOSE: deriving it from the tree would
    make the test pass for any content, which is the failure it exists to catch.

    Updated wholesale by issue #1034, which replaced 18 human titles with the
    spec identifiers the directories already carried, and rewrote the 18
    descriptions to state a triggering condition rather than only a capability.
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
    # `second/` holding `name: first` is two defects at once, and #1034's name
    # rule sees the one the duplicate check never could: the name no longer
    # identifies its own directory. Both are asserted rather than the assertion
    # being loosened to tolerate the newcomer.
    assert _codes(report) == ["DUPLICATE_SURFACE", "DUPLICATE_SURFACE", "INVALID_NAME"]


def test_human_title_name_is_reported_and_the_slug_form_is_not(tmp_path):
    """#1034 name rule, both halves. 18 of 18 packages carried the red form."""
    _write_skill(tmp_path, "code-quality", name="Code Quality")
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["INVALID_NAME"]
    assert "not a spec identifier" in report.findings[0].detail

    _write_skill(tmp_path, "code-quality", name="code-quality")
    assert skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs").ok


def test_well_formed_name_pointing_at_another_directory_is_reported(tmp_path):
    """A spec-SHAPED name is not a spec-VALID one: it must match its directory.

    Reported separately from the shape violation, which returns early, so this
    case cannot be satisfied by the charset rule happening to fire first.
    """
    _write_skill(tmp_path, "code-quality", name="code-review")
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["INVALID_NAME"]
    assert "does not match its directory" in report.findings[0].detail


def test_consecutive_and_edge_hyphens_are_not_spec_identifiers(tmp_path):
    """The three shapes the spec names explicitly, none of which a bare
    lowercase-and-hyphens test would reject."""
    for slug in ("-leading", "trailing-", "double--hyphen"):
        root = tmp_path / slug
        _write_skill(root, slug)
        report = skills_check.check_repository(root, root / "no-managed-installs")
        assert _codes(report) == ["INVALID_NAME"], slug


def test_name_over_the_spec_length_limit_is_reported(tmp_path):
    slug = "a" * (skills_check.NAME_MAX + 1)
    _write_skill(tmp_path, slug)
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["INVALID_NAME"]
    assert f"limit is {skills_check.NAME_MAX}" in report.findings[0].detail


def test_trigger_vocabulary_absent_from_the_description_is_reported(tmp_path):
    """#1034 trigger rule, red half - the live shape `secrets` was in."""
    _write_skill(
        tmp_path,
        "secrets",
        description="Secure credential access with tiered providers and masking",
        trigger="aws secrets, api key, connection string",
    )
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["UNREACHABLE_TRIGGER"]
    assert "cannot fire the skill" in report.findings[0].detail


def test_one_trigger_term_in_the_description_clears_the_floor(tmp_path):
    """Green half - and a deliberate statement of how low the floor is.

    ONE term of three satisfies it. That is the rule's whole claim, and the
    reason the fix for inert vocabulary is rewriting the description rather
    than anything this check can enforce.
    """
    _write_skill(
        tmp_path,
        "secrets",
        description="Use for an api key you must fetch without printing it",
        trigger="aws secrets, api key, connection string",
    )
    assert skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs").ok


def test_a_trigger_term_buried_inside_another_word_does_not_count(tmp_path):
    """Counter-model finding on #1034: `idd` is "in" `middleware`.

    A bare substring test reported the vocabulary reachable when the cue was
    not present at all - a FALSE PASS in a rule whose whole job is catching
    unreachable vocabulary. Both halves, because the boundary rule must still
    match the real term.
    """
    _write_skill(
        tmp_path,
        "idd-workflow",
        description="Middleware configuration.",
        trigger="idd",
    )
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["UNREACHABLE_TRIGGER"]

    _write_skill(
        tmp_path,
        "idd-workflow",
        description="Use for IDD workflow, issue driven development.",
        trigger="idd",
    )
    assert skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs").ok


def test_punctuation_bearing_trigger_terms_still_match(tmp_path):
    """The boundary rule must not silently stop matching the third of the real
    vocabulary that carries punctuation - which a `\\b` regex would."""
    for term, description in (
        (".env", "Use for .env environment variables"),
        ("CI/CD", "Use for CI/CD - a pipeline or a smoke test"),
        ("c4", "Use to draw a c4 diagram"),
        ("uv init", "Use for uv init and dependencies"),
        ("pyproject.toml", "Use for pyproject.toml and PEP 621"),
    ):
        root = tmp_path / term.replace("/", "_").replace(".", "_").replace(" ", "_")
        _write_skill(root, "sample", description=description, trigger=term)
        report = skills_check.check_repository(root, root / "no-managed-installs")
        assert report.ok, (term, [f.render(root) for f in report.findings])


def test_a_spec_valid_non_ascii_name_is_accepted(tmp_path):
    """Counter-model finding on #1034: the rule cited a spec it did not implement.

    The first cut used `^[a-z0-9]+(?:-[a-z0-9]+)*$`, which rejects a name the
    Agent Skills reference validator accepts - it tests `c.isalnum() or c ==
    "-"` over an NFKC-normalized name, and `isalnum()` is Unicode-aware. A
    finding reading "not a spec identifier" about a spec-VALID name is the
    detector claiming more than it implements.
    """
    _write_skill(tmp_path, "cafe\u0301-tools")
    assert skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs").ok


def test_an_uppercase_non_ascii_name_is_still_rejected(tmp_path):
    """Widening to Unicode must not lose the lowercase clause it sits beside."""
    _write_skill(tmp_path, "cafe-tools", name="Caf\u00c9-tools")
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["INVALID_NAME"]
    assert "not a spec identifier" in report.findings[0].detail


def test_a_skill_with_no_trigger_key_gets_no_unreachable_trigger_finding(tmp_path):
    """The rule must not fire where there is no vocabulary to be unreachable.

    `trigger` is separately REQUIRED, so this package is still rejected - by
    INVALID_FRONTMATTER. Asserting the exact code set is what distinguishes
    "the new rule stayed silent" from "the package happened to fail anyway".
    """
    _write_skill(tmp_path, "sample", trigger=None)
    report = skills_check.check_repository(tmp_path, tmp_path / "no-managed-installs")
    assert _codes(report) == ["INVALID_FRONTMATTER"]
    assert "UNREACHABLE_TRIGGER" not in _codes(report)


def _install_managed(managed: Path, canonical: Path, name: str, *, marked: bool) -> Path:
    """Copy a canonical package into an install root, with or without the marker."""
    package = managed / name
    package.mkdir(parents=True, exist_ok=True)
    text = canonical.read_text(encoding="utf-8")
    if marked:
        text = text.replace(
            "metadata:\n",
            "metadata:\n  source: claude-power-pack/.claude/skills/sample/SKILL.md\n",
            1,
        )
    (package / "SKILL.md").write_text(text, encoding="utf-8")
    return package


def test_an_unmarked_install_is_counted_as_skipped_not_silently_dropped(tmp_path):
    """#1034 item 3, red half.

    The comparison is opt-in through a field the copy itself controls, so a
    package that loses `metadata.source` is skipped with no finding and no
    per-package note - and `Report.ok` is `not findings`. Before the count, a
    run that examined nothing printed the same summary as one that examined
    everything.
    """
    canonical = _write_skill(tmp_path, "sample")
    managed = tmp_path / "install-root"
    _install_managed(managed, canonical, "claude-power-pack-sample", marked=True)
    _install_managed(managed, canonical, "unmarked-copy", marked=False)

    report = skills_check.check_repository(tmp_path, managed)
    assert report.ok
    summary = [note for note in report.notes if note.startswith("managed installs: checked")]
    assert summary == ["managed installs: checked 1 CPP-marked package(s), 1 clean, skipped 1 (no CPP source marker)"]


def test_every_install_marked_reports_zero_skipped(tmp_path):
    """Green half. A counter that silently matches nothing renders identically
    to a working one, so the zero has to be demonstrated as reachable too."""
    canonical = _write_skill(tmp_path, "sample")
    managed = tmp_path / "install-root"
    _install_managed(managed, canonical, "claude-power-pack-sample", marked=True)

    report = skills_check.check_repository(tmp_path, managed)
    assert report.ok
    assert any("1 clean, skipped 0 (no CPP source marker)" in note for note in report.notes)


def test_an_install_root_of_only_user_content_names_its_skipped_population(tmp_path):
    _write_skill(tmp_path, "sample")
    managed = tmp_path / "install-root"
    for name in ("someone-elses-skill", "another-one"):
        package = managed / name
        package.mkdir(parents=True)
        (package / "SKILL.md").write_text(
            "---\nname: other\ndescription: other\ntrigger: other\n---\n# Theirs\n",
            encoding="utf-8",
        )

    report = skills_check.check_repository(tmp_path, managed)
    assert report.ok
    assert any(
        note == "managed installs: no CPP-marked packages, skipped 2 "
        "(no CPP source marker; user content is not examined)"
        for note in report.notes
    )


def test_real_repo_skills_are_valid_without_host_managed_state(tmp_path):
    """The CI dogfood gate must model a fresh checkout, not this host."""
    absent_managed_root = tmp_path / "fresh-checkout-has-no-agents-skills"
    report = skills_check.check_repository(ROOT, absent_managed_root)
    assert report.ok, [finding.render(ROOT) for finding in report.findings]
    assert any("nothing to check" in note for note in report.notes)
