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
    def replacer(match: re.Match[str]) -> str:
        path = match.group(1)
        inner = path.strip("`")
        return f"`{cpp_dir}/{inner}`"

    return RELATIVE_PATH_PATTERN.sub(replacer, body)


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Codex skill wrappers from Claude Power Pack skills")
    parser.add_argument("--source", default=".claude/skills", help="Source skills directory")
    parser.add_argument("--output", default=".agents/skills", help="Output directory for Codex skills")
    parser.add_argument("--cpp-dir", default=None, help="Claude Power Pack repo root (auto-detected if omitted)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated skills")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without writing")
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
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
