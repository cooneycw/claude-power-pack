"""Command-line interface for CI/CD & Verification.

Usage:
    python -m lib.cicd detect [OPTIONS]
    python -m lib.cicd check [OPTIONS]
    python -m lib.cicd health [OPTIONS]
    python -m lib.cicd smoke [OPTIONS]

Examples:
    python -m lib.cicd detect
    python -m lib.cicd detect --json
    python -m lib.cicd check
    python -m lib.cicd check --summary
    python -m lib.cicd check --json
    python -m lib.cicd health
    python -m lib.cicd health --json
    python -m lib.cicd smoke
    python -m lib.cicd smoke --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import NoReturn

from .config import CICDConfig
from .container import generate_container_files
from .detector import detect_framework, detect_infrastructure
from .health import run_health_checks
from .infrastructure import generate_discovery_script, generate_infra_pipeline, scaffold_infrastructure
from .makefile import check_makefile
from .pipeline import generate_pipeline
from .smoke import run_smoke_tests


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

    # No Makefile - early exit
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


def cmd_pipeline(args: argparse.Namespace) -> int:
    """Generate CI/CD pipeline files."""
    info = detect_framework(args.path)
    config = CICDConfig.load(args.path)

    # Override provider if specified on CLI
    if args.provider:
        config.pipeline.provider = args.provider

    if args.json:
        files = generate_pipeline(info, config)
        print(json.dumps({"provider": config.pipeline.provider, "files": files}, indent=2))
        return 0

    # Dry run by default, write with --write
    if args.write:
        files = generate_pipeline(info, config, output_dir=args.path)
    else:
        files = generate_pipeline(info, config)

    provider = config.pipeline.provider
    print(f"Pipeline provider: {provider}")
    print(f"Framework: {info.framework.label} ({info.package_manager.label})")
    print()

    for filepath, content in files.items():
        if args.write:
            print(f"Wrote: {filepath}")
        else:
            print(f"--- {filepath} ---")
            print(content)

    if not args.write:
        print("(dry run - use --write to create files)")

    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Run health checks against configured endpoints and processes."""
    config = CICDConfig.load(args.path)
    result = run_health_checks(config=config, project_root=args.path)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.all_passed else 1

    if args.summary:
        print(result.summary_line())
        return 0 if result.all_passed else 1

    if not result.checks:
        print("Health Check: no checks configured")
        print()
        print("  Configure endpoints and processes in .claude/cicd.yml:")
        print("    health:")
        print("      endpoints:")
        print("        - url: http://localhost:8000/health")
        print("          name: API Server")
        print("      processes:")
        print("        - name: uvicorn")
        print("          port: 8000")
        return 0

    print("## Health Checks")
    print()
    print("| Check | Type | Status | Detail | Time |")
    print("|-------|------|--------|--------|------|")

    for check in result.checks:
        status = "PASS" if check.passed else "FAIL"
        elapsed = f"{check.elapsed_ms:.0f}ms"
        print(f"| {check.name} | {check.kind} | {status} | {check.detail} | {elapsed} |")

    print()
    print(f"Result: {result.summary_line()}")

    return 0 if result.all_passed else 1


def cmd_smoke(args: argparse.Namespace) -> int:
    """Run smoke tests from cicd.yml configuration."""
    config = CICDConfig.load(args.path)
    result = run_smoke_tests(config=config, project_root=args.path)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.all_passed else 1

    if args.summary:
        print(result.summary_line())
        return 0 if result.all_passed else 1

    if not result.tests:
        print("Smoke Tests: no tests configured")
        print()
        print("  Configure smoke tests in .claude/cicd.yml:")
        print("    health:")
        print("      smoke_tests:")
        print("        - name: API responds")
        print('          command: "curl -sf http://localhost:8000/health"')
        print("          expected_exit: 0")
        return 0

    print("## Smoke Tests")
    print()
    print("| Test | Status | Detail | Time |")
    print("|------|--------|--------|------|")

    for test in result.tests:
        status = "PASS" if test.passed else "FAIL"
        elapsed = f"{test.elapsed_ms:.0f}ms"
        print(f"| {test.name} | {status} | {test.detail} | {elapsed} |")

    print()
    print(f"Result: {result.summary_line()}")

    return 0 if result.all_passed else 1


def cmd_container(args: argparse.Namespace) -> int:
    """Generate container files (Dockerfile, compose, dockerignore)."""
    info = detect_framework(args.path)
    config = CICDConfig.load(args.path)

    if args.json:
        files = generate_container_files(info, config)
        print(json.dumps({"framework": info.framework.value, "files": files}, indent=2))
        return 0

    if args.write:
        files = generate_container_files(info, config, output_dir=args.path)
    else:
        files = generate_container_files(info, config)

    print(f"Framework: {info.framework.label} ({info.package_manager.label})")
    print()

    for filepath, content in files.items():
        if args.write:
            print(f"Wrote: {filepath}")
        else:
            print(f"--- {filepath} ---")
            print(content)

    if not args.write:
        print("(dry run - use --write to create files)")

    return 0


def cmd_infra_init(args: argparse.Namespace) -> int:
    """Scaffold IaC directory structure."""
    config = CICDConfig.load(args.path)

    # Check if infra already exists
    infra_dir = os.path.join(args.path, "infra")
    if os.path.isdir(infra_dir) and not args.force:
        print(f"infra/ directory already exists at {infra_dir}")
        print("Use --force to overwrite.")
        return 1

    if args.json:
        files = scaffold_infrastructure(args.path, config.infrastructure)
        print(json.dumps({"files": list(files.keys())}, indent=2))
        return 0

    if args.write:
        files = scaffold_infrastructure(args.path, config.infrastructure, output_dir=args.path)
        print(f"IaC Provider: {config.infrastructure.provider}")
        print(f"Cloud: {config.infrastructure.cloud}")
        print()
        for filepath in sorted(files.keys()):
            print(f"  Created: {filepath}")
        print()
        print("Next steps:")
        print("  1. Edit infra/foundation/variables.tf with your values")
        print("  2. Configure state backend in each tier's main.tf")
        print("  3. Run: cd infra && make init-all")
    else:
        files = scaffold_infrastructure(args.path, config.infrastructure)
        for filepath, content in sorted(files.items()):
            print(f"--- {filepath} ---")
            print(content)
        print("(dry run - use --write to create files)")

    return 0


def cmd_infra_discover(args: argparse.Namespace) -> int:
    """Generate cloud resource discovery script."""
    config = CICDConfig.load(args.path)
    cloud = args.cloud or config.infrastructure.cloud

    # Also run detection
    infra_info = detect_infrastructure(args.path)
    if infra_info.iac_provider.value != "none":
        print(f"Existing IaC detected: {infra_info.iac_provider.label}")
        if infra_info.detected_files:
            print(f"  Files: {', '.join(infra_info.detected_files)}")
        print()

    if args.json:
        files = generate_discovery_script(cloud)
        result = {
            "cloud": cloud,
            "detection": infra_info.to_dict(),
            "files": list(files.keys()),
        }
        print(json.dumps(result, indent=2))
        return 0

    if args.write:
        files = generate_discovery_script(cloud, output_dir=args.path)
        for filepath in files:
            print(f"  Created: {filepath}")
        print()
        print("Run the discovery script:")
        print(f"  bash {list(files.keys())[0]}")
    else:
        files = generate_discovery_script(cloud)
        for filepath, content in files.items():
            print(f"--- {filepath} ---")
            print(content)
        print("(dry run - use --write to create files)")

    return 0


def cmd_infra_pipeline(args: argparse.Namespace) -> int:
    """Generate CI/CD pipelines for infrastructure tiers."""
    config = CICDConfig.load(args.path)
    provider = args.provider or config.pipeline.provider

    if args.json:
        files = generate_infra_pipeline(config.infrastructure, provider)
        print(json.dumps({"provider": provider, "files": list(files.keys())}, indent=2))
        return 0

    if args.write:
        files = generate_infra_pipeline(config.infrastructure, provider, output_dir=args.path)
        print(f"Pipeline provider: {provider}")
        print(f"IaC: {config.infrastructure.provider}")
        print()
        for filepath in sorted(files.keys()):
            print(f"  Created: {filepath}")
        print()
        for tier_name, tier_cfg in config.infrastructure.tiers.items():
            approval = "manual approval required" if tier_cfg.approval_required else "auto-deploy"
            print(f"  {tier_name}: {approval}")
    else:
        files = generate_infra_pipeline(config.infrastructure, provider)
        for filepath, content in sorted(files.items()):
            print(f"--- {filepath} ---")
            print(content)
        print("(dry run - use --write to create files)")

    return 0


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

    # 'health' subcommand
    health_parser = subparsers.add_parser(
        "health",
        help="Run health checks against configured endpoints and processes",
    )
    _add_common_args(health_parser)
    health_parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="One-line summary for flow integration",
    )

    # 'smoke' subcommand
    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Run smoke tests from cicd.yml configuration",
    )
    _add_common_args(smoke_parser)
    smoke_parser.add_argument(
        "--summary",
        "-s",
        action="store_true",
        help="One-line summary for flow integration",
    )

    # 'container' subcommand
    container_parser = subparsers.add_parser(
        "container",
        help="Generate container files (Dockerfile, docker-compose, .dockerignore)",
    )
    _add_common_args(container_parser)
    container_parser.add_argument(
        "--write",
        "-w",
        action="store_true",
        help="Write files to disk (default: dry run to stdout)",
    )

    # 'pipeline' subcommand
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Generate CI/CD pipeline files (GitHub Actions, Woodpecker)",
    )
    _add_common_args(pipeline_parser)
    pipeline_parser.add_argument(
        "--provider",
        choices=["github-actions", "woodpecker", "both"],
        default=None,
        help="Pipeline provider (overrides cicd.yml)",
    )
    pipeline_parser.add_argument(
        "--write",
        "-w",
        action="store_true",
        help="Write files to disk (default: dry run to stdout)",
    )

    # 'infra-init' subcommand
    infra_init_parser = subparsers.add_parser(
        "infra-init",
        help="Scaffold IaC directory with tiered structure (foundation/platform/app)",
    )
    _add_common_args(infra_init_parser)
    infra_init_parser.add_argument(
        "--write", "-w", action="store_true",
        help="Write files to disk (default: dry run to stdout)",
    )
    infra_init_parser.add_argument(
        "--force", "-f", action="store_true",
        help="Overwrite existing infra/ directory",
    )

    # 'infra-discover' subcommand
    infra_discover_parser = subparsers.add_parser(
        "infra-discover",
        help="Generate cloud resource discovery script for IaC import",
    )
    _add_common_args(infra_discover_parser)
    infra_discover_parser.add_argument(
        "--cloud", choices=["aws", "azure", "gcp"], default=None,
        help="Cloud provider (overrides cicd.yml)",
    )
    infra_discover_parser.add_argument(
        "--write", "-w", action="store_true",
        help="Write script to disk (default: dry run to stdout)",
    )

    # 'infra-pipeline' subcommand
    infra_pipeline_parser = subparsers.add_parser(
        "infra-pipeline",
        help="Generate CI/CD pipelines for infrastructure tiers with approval gates",
    )
    _add_common_args(infra_pipeline_parser)
    infra_pipeline_parser.add_argument(
        "--provider", choices=["github-actions", "woodpecker"],
        default=None,
        help="Pipeline provider (overrides cicd.yml)",
    )
    infra_pipeline_parser.add_argument(
        "--write", "-w", action="store_true",
        help="Write files to disk (default: dry run to stdout)",
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
        "health": cmd_health,
        "smoke": cmd_smoke,
        "container": cmd_container,
        "pipeline": cmd_pipeline,
        "infra-init": cmd_infra_init,
        "infra-discover": cmd_infra_discover,
        "infra-pipeline": cmd_infra_pipeline,
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
