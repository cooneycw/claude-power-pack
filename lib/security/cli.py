"""Command-line interface for security scanning.

Usage:
    python -m lib.security scan [OPTIONS]
    python -m lib.security quick [OPTIONS]
    python -m lib.security deep [OPTIONS]
    python -m lib.security explain <FINDING_ID>

Examples:
    python -m lib.security scan
    python -m lib.security quick --json
    python -m lib.security deep --path /my/project
    python -m lib.security explain HARDCODED_PASSWORD
    python -m lib.security gate flow_finish
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import NoReturn

from .config import SecurityConfig
from .explain import get_explanation, list_finding_ids
from .models import ScanResult
from .orchestrator import check_gate, scan_deep, scan_full, scan_quick
from .output.json_output import format_results as format_json
from .output.novice import format_results as format_novice


def cmd_scan(args: argparse.Namespace) -> int:
    """Run full security scan."""
    config = SecurityConfig.load(args.path)
    result = scan_full(args.path, config)
    _print_results(result, args)
    return 1 if result.has_blockers else 0


def cmd_quick(args: argparse.Namespace) -> int:
    """Run quick (native-only) security scan."""
    config = SecurityConfig.load(args.path)
    result = scan_quick(args.path, config)
    _print_results(result, args)
    return 1 if result.has_blockers else 0


def cmd_deep(args: argparse.Namespace) -> int:
    """Run deep security scan including git history."""
    config = SecurityConfig.load(args.path)
    result = scan_deep(args.path, config)
    _print_results(result, args)
    return 1 if result.has_blockers else 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Show detailed explanation for a finding."""
    explanation = get_explanation(args.finding_id)
    if explanation:
        print(explanation.strip())
        return 0

    print(f"Unknown finding ID: {args.finding_id}", file=sys.stderr)
    print(f"\nAvailable finding IDs:", file=sys.stderr)
    for fid in list_finding_ids():
        print(f"  - {fid}", file=sys.stderr)
    return 1


def cmd_gate(args: argparse.Namespace) -> int:
    """Check if scan results pass a flow gate."""
    config = SecurityConfig.load(args.path)
    result = scan_quick(args.path, config)
    passed, messages = check_gate(result, args.gate_name, config)

    for msg in messages:
        print(msg)

    if passed:
        if not messages:
            print("Security gate passed.")
        return 0
    else:
        print(f"\nSecurity gate '{args.gate_name}' FAILED. Fix critical issues before proceeding.")
        return 1


def _print_results(result: ScanResult, args: argparse.Namespace) -> None:
    """Print results in the chosen format."""
    if args.json:
        print(format_json(result))
    else:
        print(format_novice(result, verbose=args.verbose))


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
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show additional details (matched patterns, etc.)",
    )


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m lib.security",
        description="Security scanning for Claude Code projects",
    )
    _add_common_args(parser)

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'scan' subcommand
    scan_parser = subparsers.add_parser(
        "scan",
        help="Full scan: native + available external tools",
    )
    _add_common_args(scan_parser)

    # 'quick' subcommand
    quick_parser = subparsers.add_parser(
        "quick",
        help="Quick scan: native scanners only (fast, zero deps)",
    )
    _add_common_args(quick_parser)

    # 'deep' subcommand
    deep_parser = subparsers.add_parser(
        "deep",
        help="Deep scan: includes git history analysis",
    )
    _add_common_args(deep_parser)

    # 'explain' subcommand
    explain_parser = subparsers.add_parser(
        "explain",
        help="Detailed explanation of a finding",
    )
    explain_parser.add_argument(
        "finding_id",
        help="Finding ID to explain (e.g., HARDCODED_PASSWORD)",
    )

    # 'gate' subcommand
    gate_parser = subparsers.add_parser(
        "gate",
        help="Check if scan passes a flow gate",
    )
    gate_parser.add_argument(
        "gate_name",
        choices=["flow_finish", "flow_deploy"],
        help="Gate to check",
    )
    _add_common_args(gate_parser)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        # Default to full scan
        args.command = "scan"
        return cmd_scan(args)

    commands = {
        "scan": cmd_scan,
        "quick": cmd_quick,
        "deep": cmd_deep,
        "explain": cmd_explain,
        "gate": cmd_gate,
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
