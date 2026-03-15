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
from pathlib import Path
from typing import NoReturn

from .config import CICDConfig
from .container import generate_container_files
from .detector import detect_framework, detect_infrastructure
from .health import run_health_checks
from .infrastructure import generate_discovery_script, generate_infra_pipeline, scaffold_infrastructure
from .makefile import check_makefile
from .manifest import generate_manifest, load_manifest, write_manifest
from .pipeline import generate_pipeline
from .runner import resume_run, run_plan, show_status
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


def _check_secrets_source(config: CICDConfig) -> list[str]:
    """Check secrets configuration and return warnings."""
    warnings: list[str] = []
    pipeline = config.pipeline
    has_deploy = "deploy" in pipeline.branches.get("main", [])

    if pipeline.secrets_source == "aws-secrets-manager":
        if not pipeline.aws_secret_name:
            warnings.append(
                "WARNING: secrets_source is 'aws-secrets-manager' but "
                "aws_secret_name is not set. Set pipeline.aws_secret_name "
                "in .claude/cicd.yml."
            )
    elif has_deploy and pipeline.secrets_needed:
        warnings.append(
            "WARNING: Deploy pipeline uses platform-injected secrets. "
            "Consider switching to AWS Secrets Manager for centralized "
            "secret management. Set pipeline.secrets_source: aws-secrets-manager "
            "in .claude/cicd.yml."
        )

    return warnings


def cmd_pipeline(args: argparse.Namespace) -> int:
    """Generate CI/CD pipeline files."""
    info = detect_framework(args.path)
    config = CICDConfig.load(args.path)

    # Override provider if specified on CLI
    if args.provider:
        config.pipeline.provider = args.provider

    # Check secrets configuration
    warnings = _check_secrets_source(config)

    if args.json:
        files = generate_pipeline(info, config)
        result = {"provider": config.pipeline.provider, "files": files}
        if warnings:
            result["warnings"] = warnings
        print(json.dumps(result, indent=2))
        return 0

    # Print warnings
    for warning in warnings:
        print(warning)
    if warnings:
        print()

    # Dry run by default, write with --write
    if args.write:
        files = generate_pipeline(info, config, output_dir=args.path)
    else:
        files = generate_pipeline(info, config)

    provider = config.pipeline.provider
    secrets_source = config.pipeline.secrets_source
    print(f"Pipeline provider: {provider}")
    print(f"Secrets source: {secrets_source}")
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


def cmd_init_manifest(args: argparse.Namespace) -> int:
    """Generate a default cicd_tasks.yml manifest."""
    import os

    manifest_path = os.path.join(args.path, ".claude", "cicd_tasks.yml")

    if os.path.exists(manifest_path) and not args.force:
        print(f"Manifest already exists: {manifest_path}")
        print("Use --force to overwrite.")
        return 1

    manifest = generate_manifest(args.path)

    if args.json:
        print(json.dumps({"steps": list(manifest.steps.keys()), "plans": list(manifest.plans.keys())}, indent=2))
        if not args.write:
            return 0

    if args.write:
        path = write_manifest(manifest, args.path)
        print(f"Wrote manifest: {path}")
        print()
        print(f"Steps: {', '.join(sorted(manifest.steps.keys()))}")
        print(f"Plans: {', '.join(sorted(manifest.plans.keys()))}")
        print()
        print("The runner will now load plans from this manifest.")
        print("Edit .claude/cicd_tasks.yml to customize steps and plans.")
    else:
        print("# .claude/cicd_tasks.yml (dry run)")
        print()
        print(manifest.to_yaml())
        print("(dry run - use --write to create file)")

    return 0


def cmd_validate_manifest(args: argparse.Namespace) -> int:
    """Validate an existing cicd_tasks.yml manifest."""
    try:
        manifest = load_manifest(args.path)
    except ValueError as e:
        if args.json:
            print(json.dumps({"valid": False, "errors": [str(e)]}, indent=2))
        else:
            print(f"INVALID: {e}")
        return 1

    if manifest is None:
        if args.json:
            print(json.dumps({"valid": False, "errors": ["No manifest found"]}, indent=2))
        else:
            print("No manifest found at .claude/cicd_tasks.yml")
            print("Generate one with: python -m lib.cicd init-manifest --write")
        return 1

    ref_errors = manifest.validate_plan_references()
    if ref_errors:
        if args.json:
            print(json.dumps({"valid": False, "errors": ref_errors}, indent=2))
        else:
            print("INVALID manifest:")
            for err in ref_errors:
                print(f"  - {err}")
        return 1

    if args.json:
        print(json.dumps({
            "valid": True,
            "steps": list(manifest.steps.keys()),
            "plans": list(manifest.plans.keys()),
        }, indent=2))
    else:
        print("Manifest OK")
        print(f"  Steps: {', '.join(sorted(manifest.steps.keys()))}")
        print(f"  Plans: {', '.join(sorted(manifest.plans.keys()))}")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate CI/CD configuration file."""
    config_path = Path(args.path) / ".claude" / "cicd.yml"

    if args.schema:
        # Output JSON Schema for IDE autocompletion
        print(CICDConfig.json_schema())
        return 0

    if not config_path.exists():
        if args.json:
            print(json.dumps({"valid": False, "issues": ["No .claude/cicd.yml found"], "path": str(config_path)}))
        else:
            print(f"No config file found at {config_path}")
            print()
            print("  Create one with /cicd:init or copy a template:")
            print("    cp ~/Projects/claude-power-pack/templates/cicd.yml.example .claude/cicd.yml")
        return 1

    issues = CICDConfig.validate_file(config_path)

    if args.json:
        print(json.dumps({"valid": len(issues) == 0, "issues": issues, "path": str(config_path)}, indent=2))
        return 0 if not issues else 1

    if not issues:
        print(f"Config valid: {config_path}")
        # Also show loaded config summary
        config = CICDConfig.load(args.path)
        print(f"  Build: framework={config.build.framework}, pm={config.build.package_manager}")
        print(f"  Pipeline: provider={config.pipeline.provider}")
        if config.health.endpoints:
            print(f"  Health: {len(config.health.endpoints)} endpoint(s)")
        if config.health.smoke_tests:
            print(f"  Smoke: {len(config.health.smoke_tests)} test(s)")
        return 0

    print(f"Config issues in {config_path}:")
    print()
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    print()
    print(f"Found {len(issues)} issue(s). Fix them and re-run: python -m lib.cicd validate")
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a CI/CD plan deterministically."""
    return run_plan(
        plan_name=args.plan,
        project_root=args.path,
        json_output=not args.no_json,
    )


def cmd_resume(args: argparse.Namespace) -> int:
    """Resume a failed CI/CD run."""
    return resume_run(
        run_id=args.run_id,
        project_root=args.path,
        json_output=not args.no_json,
    )


def cmd_status(args: argparse.Namespace) -> int:
    """Show status of a CI/CD run."""
    return show_status(
        run_id=args.run_id,
        project_root=args.path,
    )


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

    # 'init-manifest' subcommand
    init_manifest_parser = subparsers.add_parser(
        "init-manifest",
        help="Generate a default cicd_tasks.yml manifest from detected framework",
    )
    _add_common_args(init_manifest_parser)
    init_manifest_parser.add_argument(
        "--write", "-w", action="store_true",
        help="Write manifest to disk (default: dry run to stdout)",
    )
    init_manifest_parser.add_argument(
        "--force", "-f", action="store_true",
        help="Overwrite existing manifest",
    )

    # 'validate-manifest' subcommand
    validate_manifest_parser = subparsers.add_parser(
        "validate-manifest",
        help="Validate an existing cicd_tasks.yml manifest",
    )
    _add_common_args(validate_manifest_parser)

    # 'validate' subcommand
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate .claude/cicd.yml configuration with fix suggestions",
    )
    _add_common_args(validate_parser)
    validate_parser.add_argument(
        "--schema",
        action="store_true",
        help="Output JSON Schema for IDE autocompletion instead of validating",
    )

    # 'run' subcommand
    run_parser = subparsers.add_parser(
        "run",
        help="Execute a CI/CD plan deterministically",
    )
    _add_common_args(run_parser)
    run_parser.add_argument(
        "--plan",
        required=True,
        help="Plan name to execute (e.g., finish, check, deploy)",
    )
    run_parser.add_argument(
        "--no-json",
        action="store_true",
        help="Disable JSON output (human-readable only)",
    )

    # 'resume' subcommand
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a failed CI/CD run from the last successful step",
    )
    _add_common_args(resume_parser)
    resume_parser.add_argument(
        "run_id",
        help="Run ID to resume (from previous run output)",
    )
    resume_parser.add_argument(
        "--no-json",
        action="store_true",
        help="Disable JSON output",
    )

    # 'status' subcommand
    status_parser = subparsers.add_parser(
        "status",
        help="Show status of a CI/CD run",
    )
    _add_common_args(status_parser)
    status_parser.add_argument(
        "run_id",
        help="Run ID to check",
    )

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
        "init-manifest": cmd_init_manifest,
        "validate-manifest": cmd_validate_manifest,
        "validate": cmd_validate,
        "run": cmd_run,
        "resume": cmd_resume,
        "status": cmd_status,
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
