#!/usr/bin/env python3
"""Generate Codex-compatible skill wrappers from Claude Power Pack skills."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FALLBACK_METADATA: dict[str, dict[str, str]] = {
    "browser-tiered.md": {
        "name": "Browser Automation (Tiered)",
        "description": (
            "Tiered browser automation: lightweight bdg CLI for simple tasks,"
            " Playwright MCP for complex workflows"
        ),
        "trigger": "browser, automation, playwright, bdg, DOM, screenshot, form fill",
    },
    "evaluate.md": {
        "name": "Evaluation Prompts",
        "description": (
            "Domain-aware evaluation prompts for multi-model analysis across"
            " architecture, concept, algorithm, ui-design, and workflow domains"
        ),
        "trigger": "evaluate, divergence scan, validation, multi-model, architecture review",
    },
    "project-deploy.md": {
        "name": "Project Deployment",
        "description": (
            "Deployment patterns for projects with deploy scripts,"
            " server management, and branch testing"
        ),
        "trigger": "deploy, start servers, run locally, test changes, restart dev",
    },
}

MCP_INDICATORS = [
    "mcp", "MCP", "slash command", "/flow", "/project", "/spec", "/cicd",
    "/security", "/secrets", "/evaluate", "/documentation", "/qa",
    "browser_screenshot", "browser_navigate", "browser_click", "browser_fill",
    "second-opinion", "nano-banana", "playwright-persistent", "woodpecker-ci",
]

RELATIVE_PATH_PATTERN = re.compile(
    r"(`(?:docs/|scripts/|templates/|lib/|\.claude/|\.specify/)[^`]+`)"
)

BARE_PATH_PATTERN = re.compile(
    r"(?<!`)(?<!/)((?:docs/|scripts/|templates/|lib/|\.claude/|\.specify/)"
    r"\S+\.(?:md|py|sh|yml|yaml|json|toml))"
    r"(?!`)"
)


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:50]


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    frontmatter_text = content[3:end].strip()
    body = content[end + 3:].strip()
    metadata: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                metadata[key] = value
    return metadata, body


def build_description(metadata: dict[str, str]) -> str:
    desc = metadata.get("description", "")
    trigger = metadata.get("trigger", "")
    if trigger and desc:
        trigger_terms = [t.strip() for t in trigger.split(",")]
        desc_lower = desc.lower()
        extra = [t for t in trigger_terms if t.lower() not in desc_lower]
        if extra:
            desc = f"{desc}. Use for: {', '.join(extra)}"
    return desc


def has_mcp_content(body: str) -> bool:
    for indicator in MCP_INDICATORS:
        if indicator in body:
            return True
    return False


def rewrite_paths(body: str, cpp_dir: str) -> str:
    def backtick_replacer(match: re.Match[str]) -> str:
        path = match.group(1)
        inner = path.strip("`")
        return f"`{cpp_dir}/{inner}`"

    def bare_replacer(match: re.Match[str]) -> str:
        path = match.group(1)
        return f"{cpp_dir}/{path}"

    result = RELATIVE_PATH_PATTERN.sub(backtick_replacer, body)
    result = BARE_PATH_PATTERN.sub(bare_replacer, result)
    return result


def generate_codex_skill(
    source_file: Path,
    cpp_dir: str,
) -> tuple[str, str, str]:
    """Returns (slug, skill_content, source_filename)."""
    content = source_file.read_text()
    filename = source_file.name
    metadata, body = parse_frontmatter(content)

    if filename in FALLBACK_METADATA:
        fallback = FALLBACK_METADATA[filename]
        metadata.setdefault("name", fallback["name"])
        metadata.setdefault("description", fallback["description"])
        metadata.setdefault("trigger", fallback["trigger"])

    if not metadata.get("name"):
        stem = source_file.stem.replace("-", " ").replace("_", " ").title()
        metadata["name"] = stem
    if not metadata.get("description"):
        metadata["description"] = f"Claude Power Pack skill: {metadata['name']}"

    name = metadata["name"]
    slug = f"claude-power-pack-{slugify(name)}"
    description = build_description(metadata)

    body = rewrite_paths(body, cpp_dir)

    mcp_notice = ""
    if has_mcp_content(body):
        mcp_notice = (
            "\n> **Note:** This skill references Claude Code slash commands and/or MCP tools.\n"
            "> When running under Codex, use available local scripts, repo CLI entry points,\n"
            "> or inspect the implementation directly. MCP tools are not available in Codex.\n\n"
        )

    skill_content = f"""---
name: {slug}
description: {description}
metadata:
  source: claude-power-pack/.claude/skills/{filename}
---
{mcp_notice}
{body}
"""
    return slug, skill_content, filename


def link_workspace_skills(
    cpp_skills_dir: Path,
    workspace_root: Path,
    *,
    refresh: bool = False,
    dry_run: bool = False,
) -> tuple[int, int, int, int]:
    """Create symlinks from workspace root .agents/skills to generated Codex skills.

    Returns (linked, already_ok, skipped, stale) counts.
    """
    ws_skills_dir = workspace_root / ".agents" / "skills"
    skill_dirs = sorted(
        d for d in cpp_skills_dir.iterdir()
        if d.is_dir() and d.name.startswith("claude-power-pack-")
    )

    if not skill_dirs:
        print("  No generated skills found. Run codex-init first.", file=sys.stderr)
        return 0, 0, 0, 0

    if not dry_run:
        ws_skills_dir.mkdir(parents=True, exist_ok=True)

    linked = 0
    already_ok = 0
    skipped = 0
    stale = 0

    for skill_dir in skill_dirs:
        link_path = ws_skills_dir / skill_dir.name
        target = skill_dir.resolve()

        if link_path.is_symlink():
            existing_target = link_path.resolve()
            if existing_target == target:
                print(f"  OK: {link_path.name} (already linked)")
                already_ok += 1
                continue
            if refresh:
                if not dry_run:
                    link_path.unlink()
                    link_path.symlink_to(target)
                print(f"  REFRESHED: {link_path.name} (was -> {existing_target})")
                linked += 1
            else:
                print(f"  STALE: {link_path.name} -> {existing_target} (use --refresh to update)")
                stale += 1
            continue

        if link_path.exists():
            print(f"  SKIP: {link_path.name} (exists as non-symlink, will not overwrite)")
            skipped += 1
            continue

        if dry_run:
            print(f"  WOULD LINK: {link_path.name} -> {target}")
        else:
            link_path.symlink_to(target)
            print(f"  LINKED: {link_path.name} -> {target}")
        linked += 1

    return linked, already_ok, skipped, stale


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Codex skill wrappers from Claude Power Pack skills")
    parser.add_argument("--source", default=".claude/skills", help="Source skills directory")
    parser.add_argument("--output", default=".agents/skills", help="Output directory for Codex skills")
    parser.add_argument("--cpp-dir", default=None, help="Claude Power Pack repo root (auto-detected if omitted)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated skills")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without writing")
    parser.add_argument(
        "--workspace-root",
        default=None,
        help="Link generated skills into workspace root .agents/skills (default: parent of repo root)",
    )
    parser.add_argument("--refresh", action="store_true", help="Replace stale symlinks in workspace root")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    source_dir = repo_root / args.source
    output_dir = repo_root / args.output

    if args.cpp_dir:
        cpp_dir = args.cpp_dir
    else:
        cpp_dir = str(repo_root)

    if not source_dir.is_dir():
        print(f"ERROR: Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    skill_files = sorted(source_dir.glob("*.md"))
    if not skill_files:
        print(f"ERROR: No .md files found in {source_dir}", file=sys.stderr)
        return 1

    generated = 0
    skipped = 0
    errors = 0

    for skill_file in skill_files:
        try:
            slug, content, filename = generate_codex_skill(skill_file, cpp_dir)
        except Exception as e:
            print(f"  WARN: Failed to process {skill_file.name}: {e}", file=sys.stderr)
            errors += 1
            continue

        target_dir = output_dir / slug
        target_file = target_dir / "SKILL.md"

        if target_file.exists() and not args.force:
            print(f"  SKIP: {target_file} (exists, use --force to overwrite)")
            skipped += 1
            continue

        if args.dry_run:
            print(f"  WOULD CREATE: {target_file}")
            print(f"    slug: {slug}")
            print(f"    source: {filename}")
            generated += 1
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content)
        print(f"  CREATED: {target_file}")
        generated += 1

    print(f"\nDone: {generated} generated, {skipped} skipped, {errors} errors")

    if args.workspace_root is not None:
        ws_root = Path(args.workspace_root).resolve()
        print(f"\nLinking skills into workspace root: {ws_root}")
        linked, already_ok, ws_skipped, ws_stale = link_workspace_skills(
            output_dir.resolve(),
            ws_root,
            refresh=args.refresh,
            dry_run=args.dry_run,
        )
        print(
            f"\nWorkspace links: {linked} linked, {already_ok} already OK,"
            f" {ws_skipped} skipped, {ws_stale} stale"
        )
        if ws_stale > 0:
            errors += 1

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
