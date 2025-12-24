"""Command-line interface for spec_bridge.

Usage:
    python -m lib.spec_bridge status [FEATURE]
    python -m lib.spec_bridge sync FEATURE [--dry-run]
    python -m lib.spec_bridge sync --all [--dry-run]
    python -m lib.spec_bridge init
    python -m lib.spec_bridge create FEATURE
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .status import get_feature_status, get_all_status, format_feature_status, format_project_status
from .issue_sync import sync_feature, sync_all_features


def cmd_status(args: argparse.Namespace) -> int:
    """Show spec status."""
    if args.feature:
        status = get_feature_status(args.feature, args.spec_dir)
        print(format_feature_status(status, verbose=True))
    else:
        project = get_all_status(args.spec_dir)
        print(format_project_status(project))

    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Sync tasks to GitHub issues."""
    if args.all:
        results = sync_all_features(args.spec_dir, dry_run=args.dry_run)

        if not results:
            print("No features found to sync.")
            return 1

        total_created = 0
        total_errors = 0

        for result in results:
            if result.dry_run:
                print(f"\n[DRY RUN] {result.feature}:")
            else:
                print(f"\n{result.feature}:")

            if result.issues_created:
                print(f"  Created: {len(result.issues_created)} issues")
                for num in result.issues_created:
                    print(f"    #{num}")
                total_created += len(result.issues_created)

            if result.issues_skipped:
                print(f"  Skipped: {len(result.issues_skipped)} (already exist)")

            if result.errors:
                print(f"  Errors: {len(result.errors)}")
                for err in result.errors:
                    print(f"    - {err}")
                total_errors += len(result.errors)

        print(f"\nTotal: {total_created} issues created, {total_errors} errors")

    else:
        if not args.feature:
            print("Error: FEATURE required (or use --all)")
            return 1

        result = sync_feature(args.feature, args.spec_dir, dry_run=args.dry_run)

        if args.dry_run:
            print(f"[DRY RUN] Sync for {result.feature}:")
        else:
            print(f"Sync complete for {result.feature}:")

        if result.issues_created:
            print(f"\nIssues created: {len(result.issues_created)}")
            for num in result.issues_created:
                print(f"  #{num}")

        if result.issues_skipped:
            print(f"\nIssues skipped: {len(result.issues_skipped)} (already exist)")

        if result.errors:
            print(f"\nErrors: {len(result.errors)}")
            for err in result.errors:
                print(f"  - {err}")
            return 1

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .specify/ structure."""
    base_dir = Path(args.base_dir)

    dirs_to_create = [
        base_dir / "memory",
        base_dir / "specs",
        base_dir / "templates",
        base_dir / "scripts",
    ]

    created = []
    for d in dirs_to_create:
        if not d.exists():
            d.mkdir(parents=True)
            created.append(d)

    if created:
        print("Created directories:")
        for d in created:
            print(f"  {d}")
    else:
        print("All directories already exist.")

    # Check for constitution
    constitution_path = base_dir / "memory" / "constitution.md"
    if not constitution_path.exists():
        print(f"\nNote: Create your project constitution at:")
        print(f"  {constitution_path}")

    return 0


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new feature spec."""
    feature_name = args.feature
    spec_dir = Path(args.spec_dir)
    feature_path = spec_dir / feature_name

    if feature_path.exists():
        print(f"Error: Feature already exists: {feature_path}")
        return 1

    # Create directory
    feature_path.mkdir(parents=True)

    # Create placeholder files
    files = {
        "spec.md": f"# Feature Specification: {_title_case(feature_name)}\n\n> **Status:** Draft\n\n## Overview\n\nTODO: Describe what this feature does.\n\n## User Stories\n\n### US1: TODO [P1]\n\n**As a** user,\n**I want** TODO,\n**So that** TODO.\n\n**Acceptance Criteria:**\n- [ ] TODO\n",
        "plan.md": f"# Implementation Plan: {_title_case(feature_name)}\n\n> **Spec:** [spec.md](./spec.md)\n> **Status:** Draft\n\n## Summary\n\nTODO: Technical approach.\n\n## Architecture\n\nTODO: Component design.\n",
        "tasks.md": f"# Tasks: {_title_case(feature_name)}\n\n> **Plan:** [plan.md](./plan.md)\n> **Status:** Draft\n\n## Wave 1: Core Implementation\n\n- [ ] **T001** [US1] TODO task description\n\n**Checkpoint:** Core functionality works\n\n## Issue Sync\n\n| Wave | Tasks | Issue | Status |\n|------|-------|-------|--------|\n| 1 | T001 | - | pending |\n",
    }

    for filename, content in files.items():
        (feature_path / filename).write_text(content)

    print(f"Created feature spec: {feature_name}")
    print(f"\nFiles:")
    for filename in files:
        print(f"  {feature_path / filename}")

    print(f"\nNext steps:")
    print(f"  1. Edit spec.md with user stories")
    print(f"  2. Edit plan.md with technical approach")
    print(f"  3. Edit tasks.md with actionable items")
    print(f"  4. Run: python -m lib.spec_bridge sync {feature_name}")

    return 0


def _title_case(name: str) -> str:
    """Convert kebab-case to Title Case."""
    return " ".join(word.capitalize() for word in name.split("-"))


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="spec_bridge",
        description="Sync spec tasks to GitHub issues",
    )

    parser.add_argument(
        "--spec-dir",
        default=".specify/specs",
        help="Path to specs directory (default: .specify/specs)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # status command
    status_parser = subparsers.add_parser("status", help="Show spec status")
    status_parser.add_argument("feature", nargs="?", help="Feature name (optional)")
    status_parser.set_defaults(func=cmd_status)

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Sync tasks to GitHub issues")
    sync_parser.add_argument("feature", nargs="?", help="Feature name")
    sync_parser.add_argument("--all", action="store_true", help="Sync all features")
    sync_parser.add_argument("--dry-run", action="store_true", help="Preview without creating issues")
    sync_parser.set_defaults(func=cmd_sync)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize .specify/ structure")
    init_parser.add_argument("--base-dir", default=".specify", help="Base directory (default: .specify)")
    init_parser.set_defaults(func=cmd_init)

    # create command
    create_parser = subparsers.add_parser("create", help="Create new feature spec")
    create_parser.add_argument("feature", help="Feature name (kebab-case)")
    create_parser.set_defaults(func=cmd_create)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
