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
import re
import sys
from pathlib import Path
from typing import NoReturn, Optional

from .config import ConfigUnreadable, SecurityConfig
from .explain import get_explanation, list_finding_ids
from .models import Finding, ScanResult
from .orchestrator import check_gate, scan_deep, scan_full, scan_quick
from .output.json_output import format_results as format_json
from .output.novice import format_results as format_novice

#: Exit status when the repository's own configuration could not be applied
#: (issue #1299). Distinct from 1 (findings block) - "I could not honour your
#: config" is not "I found something" - and non-zero, so a flow step that treats
#: any non-zero as a failure still stops.
EXIT_UNKNOWN = 2


def _unreadable_reason(exc: ConfigUnreadable) -> str:
    return (
        f"config unreadable: {exc.path}: {exc.cause}; its suppressions and gate "
        f"policy were NOT applied, so no verdict is given"
    )


def _load_config(args: argparse.Namespace) -> Optional[SecurityConfig]:
    """Load config, or report why it could not be applied and return None."""
    try:
        return SecurityConfig.load(args.path)
    except ConfigUnreadable as exc:
        print(f"security: UNKNOWN - {_unreadable_reason(exc)}", file=sys.stderr)
        return None


def cmd_scan(args: argparse.Namespace) -> int:
    """Run full security scan."""
    config = _load_config(args)
    if config is None:
        return EXIT_UNKNOWN
    result = scan_full(args.path, config)
    _print_results(result, args)
    return 1 if result.has_blockers else 0


def cmd_quick(args: argparse.Namespace) -> int:
    """Run quick (native-only) security scan."""
    config = _load_config(args)
    if config is None:
        return EXIT_UNKNOWN
    result = scan_quick(args.path, config)
    _print_results(result, args)
    return 1 if result.has_blockers else 0


def cmd_deep(args: argparse.Namespace) -> int:
    """Run deep security scan including git history."""
    config = _load_config(args)
    if config is None:
        return EXIT_UNKNOWN
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
    print("\nAvailable finding IDs:", file=sys.stderr)
    for fid in list_finding_ids():
        print(f"  - {fid}", file=sys.stderr)
    return 1


def cmd_gate(args: argparse.Namespace) -> int:
    """Check if scan results pass a flow gate.

    Prints ONE terminal summary line on every exit path (issue #1027, part of
    the same class as flow-finish-gate's ok/warn/skipped confusion): a passing
    run with WARN-level findings used to print nothing but the WARNING lines
    themselves - no verdict, no threshold, no counts - so `... | tail -20`
    rendered a passing gate as an unbroken wall of warnings indistinguishable
    from a failing one missing its last line. The summary line is unconditional
    and always the same shape, so pass and fail differ by a line that SAYS
    which happened rather than one that has to be counted.
    """
    try:
        config = SecurityConfig.load(args.path)
    except ConfigUnreadable as exc:
        # REFUSE, never fall back to defaults (issue #1299): defaults would drop
        # this repository's suppressions (a false block) and its stricter policy
        # (a false pass), and either reads exactly like a real verdict.
        print(f"SECURITY_GATE: {args.gate_name} UNKNOWN ({_unreadable_reason(exc)})")
        return EXIT_UNKNOWN
    result = scan_quick(args.path, config)
    passed, messages = check_gate(result, args.gate_name, config)

    for msg in messages:
        print(msg)

    blocked_count = sum(1 for m in messages if m.startswith("BLOCKED"))
    warned_count = sum(1 for m in messages if m.startswith("WARNING"))

    gate = config.gates.get(args.gate_name)
    if gate is not None:
        blocks_on = ",".join(s.name for s in gate.block_on) or "none"
        warns_on = ",".join(s.name for s in gate.warn_on) or "none"
        threshold = f"blocks-on={blocks_on} warns-on={warns_on}"
    else:
        threshold = "no policy for this gate name - nothing blocks or warns"

    # COVERAGE, which the counts above cannot express (issue #1027). `blocked=0
    # warned=0` is what a clean scan of 575 files reports AND what a scan that
    # opened nothing reports - the same line for opposite facts.
    #
    # `secrets-scanned=` is the coverage number and the only one a caller grades
    # on: source files the SECRETS scanner actually examined, or `unknown` when
    # it stated no figure. Not defaulted to 0 - "said nothing" and "said none"
    # are different claims and only one of them is a measurement.
    #
    # NAMED FOR THE CHECK IT MEASURES, not the stage (cross-model review). This
    # gate runs several checks - secrets, gitignore, file permissions, tracked
    # .env files, debug flags - and only the secrets scanner counts files. Spelt
    # `scanned=`, the number invited exactly one wrong conclusion: a repo with a
    # compliant .gitignore and no source files would report zero and be read as
    # "the security gate proved nothing", when its gitignore and permissions
    # checks examined their subjects and passed on that evidence.
    #
    # `skipped-checks=` is reported BESIDE it, never as its denominator. A
    # denominator was the first shape tried and it was wrong: `result.passed`
    # holds checks that passed CLEANLY, so a check that ran and found something
    # appears in neither `passed` nor `skipped`, and any `ran/total` built from
    # them silently undercounts exactly when the scan is doing its job. This
    # number is well defined instead - checks that could not run - and it is
    # deliberately NOT wired to the warn: skipping is the normal, correct
    # outcome for a check whose subject is absent (no .env file to inspect),
    # so grading on it would fire on healthy repos, which is how a warning
    # stops being read.
    scanned = (
        str(result.units_scanned) if result.units_scanned is not None else "unknown"
    )

    verdict = "PASS" if passed else "FAIL"
    print(
        f"SECURITY_GATE: {args.gate_name} {verdict} "
        f"(blocked={blocked_count} warned={warned_count}; "
        f"secrets-scanned={scanned} skipped-checks={len(result.skipped)}; {threshold})"
    )

    if passed:
        return 0
    else:
        print(f"\nSecurity gate '{args.gate_name}' FAILED. Fix critical issues before proceeding.")
        hint = _gitleaks_hint(args.path, config, result, args.gate_name)
        if hint:
            print(hint)
        return 1


def _gitleaks_hint(
    project_root: str, config: SecurityConfig, result: ScanResult, gate_name: str
) -> str:
    """Name the way out when a planted test key blocks (issue #1299).

    Printed only when the gate BLOCKS, the repository has a `.gitleaks.toml`, and
    `.claude/security.yml` declares no suppressions - the shape of a repository
    that allowlisted its fixtures for gitleaks and cannot see why this gate still
    blocks. It changes no verdict.

    `.gitleaks.toml` is deliberately NOT read: its allowlists carry regexes,
    paths, commits, stopwords and per-rule scoping, and a translator honouring
    some of those keys and dropping the rest would suppress less than the file
    claims while appearing to honour it.

    The secret itself is never printed (it may be real); the example asks the
    reader to fill the value in.
    """
    if config.suppressions:
        return ""
    if not (Path(project_root) / ".gitleaks.toml").is_file():
        return ""
    gate = config.gates.get(gate_name)
    blocking: list[Finding] = [
        f for f in result.findings if gate is not None and f.severity in gate.block_on
    ]
    if not blocking:
        return ""
    first = blocking[0]
    lines = [
        "",
        "HINT: this repository has a .gitleaks.toml, which this gate does NOT read.",
        "  The native scanner honours `.claude/security.yml` suppressions instead.",
        "  If the blocked value is a deliberately planted TEST key, suppress exactly",
        "  that value (never commit a real one):",
        "",
        "  suppressions:",
        f"    - id: {first.id}",
    ]
    # Single-quoted YAML: a backslash is literal there, so a regex-escaped path
    # survives; in double quotes `\.` is an invalid YAML escape.
    if first.file_path:
        # regex-escape, THEN YAML-escape: inside single quotes an apostrophe is
        # written twice (counter-model re-review).
        escaped = re.escape(first.file_path).replace("'", "''")
        lines.append(f"      path: '^{escaped}$'")
    if first.secret_value is not None:
        lines.append("      secret: '<the exact planted value, regex-escaped>'")
    else:
        lines.append("      # this finding carries no value to pin; id + path decides")
    lines.append('      reason: "planted negative-control fixture"')
    return "\n".join(lines)


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
