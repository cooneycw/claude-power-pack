"""Command-line interface for CI/CD & Verification.

Usage:
    python -m lib.cicd detect [OPTIONS]
    python -m lib.cicd check [OPTIONS]

Examples:
    python -m lib.cicd detect
    python -m lib.cicd detect --json
    python -m lib.cicd check
    python -m lib.cicd check --summary
    python -m lib.cicd check --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import NoReturn

from .config import CICDConfig
from .detector import detect_framework
from .makefile import check_makefile


def cmd_detect(args: argparse.Namespace) -> int:
    """Detect project framework and package manager."""
    info = detect_framework(args.path)

    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
    elif args.quiet:
        print(f"{info.framework.value}:{info.package_manager.value}")
    else:
        print(f"Framework:       {info.framework.label}")
        print(f"Package Manager: {info.package_manager.label}")
        if info.detected_files:
            print(f"Detected Files:  {', '.join(info.detected_files)}")
        if info.secondary_frameworks:
            secondary = ", ".join(f.label for f in info.secondary_frameworks)
            print(f"Also Found:      {secondary}")
        if info.recommended_targets:
            print(f"Recommended Targets: {', '.join(info.recommended_targets)}")
        if info.runner_commands:
            print("\nRunner Commands:")
            for target, cmd in info.runner_commands.items():
                print(f"  {target}: {cmd}")

    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Validate Makefile completeness."""
    config = CICDConfig.load(args.path)
    result = check_makefile(args.path, config)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.is_healthy else 1

    if args.summary:
        print(result.summary_line())
        return 0 if result.is_healthy else 1

    # No Makefile — early exit
    if not result.targets_found and "No Makefile found" in result.issues:
        print("Makefile Check: No Makefile found")
        print()
        print("  Create one with /cicd:init or copy a template:")
        print("    cp ~/Projects/claude-power-pack/templates/Makefile.example Makefile")
        return 1

    print("## Makefile Health Check")
    print()

    # Targets table
    print("| Target | Status | Notes |")
    print("|--------|--------|-------|")

    all_targets = set(result.targets_found) | set(result.missing_required) | set(result.missing_recommended)
    for target in sorted(all_targets):
        if target in result.targets_found:
            status = "present"
            notes = ""
        elif target in result.missing_required:
            status = "MISSING"
            notes = "Required by /flow"
        else:
            status = "missing"
            notes = "Recommended"
        print(f"| {target} | {status} | {notes} |")

    print()

    # .PHONY status
    if result.phony_declared:
        declared = len(result.phony_declared)
        total = len(result.targets_found)
        print(f".PHONY: declared for {declared}/{total} targets")
    elif result.targets_found:
        print(".PHONY: not declared (add to prevent stale file conflicts)")

    if result.phony_missing:
        print(f"  Missing .PHONY for: {', '.join(result.phony_missing)}")

    print()

    # Issues
    if result.issues:
        print("Issues:")
        for issue in result.issues:
            print(f"  - {issue}")
        print()

    # Summary
    if result.is_healthy:
        print(f"Result: Makefile OK ({result.target_coverage})")
    else:
        parts = []
        if result.missing_required:
            parts.append(f"{len(result.missing_required)} required targets missing")
        if result.issues:
            parts.append(f"{len(result.issues)} issues found")
        print(f"Result: {', '.join(parts)}")

    return 0 if result.is_healthy else 1


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to a parser."""
    parser.add_argument(
        "--path",
        "-p",
        default=os.getcwd(),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m lib.cicd",
        description="CI/CD & Verification for Claude Code projects",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'detect' subcommand
    detect_parser = subparsers.add_parser(
        "detect",
        help="Detect project framework and package manager",
    )
    _add_common_args(detect_parser)
    detect_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output: framework:package_manager",
    )

    # 'check' subcommand
    check_parser = subparsers.add_parser(
        "check",
        help="Validate Makefile completeness against standards",
    )
    _add_common_args(check_parser)
    check_parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="One-line summary for flow integration",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "detect": cmd_detect,
        "check": cmd_check,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


def run() -> NoReturn:
    """Entry point that exits with the return code."""
    sys.exit(main())


if __name__ == "__main__":
    run()
