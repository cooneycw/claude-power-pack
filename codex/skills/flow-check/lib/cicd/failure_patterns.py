"""Failure pattern analysis for the CI/CD runner.

Scans .claude/runs/ state files and .claude/deploy.log to detect repeated
failures from the same root cause category. When patterns emerge, returns
actionable recommendations including validation gate suggestions.

Usage:
    from lib.cicd.failure_patterns import analyze_failure_patterns
    report = analyze_failure_patterns(project_root=Path("."))
    if report.has_patterns:
        for rec in report.recommendations:
            print(rec)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

FAILURE_CATEGORIES: dict[str, list[re.Pattern[str]]] = {
    "shell-compat": [
        re.compile(r"syntax error.*unexpected", re.IGNORECASE),
        re.compile(r"bash.*not found", re.IGNORECASE),
        re.compile(r"\[\[.*not found", re.IGNORECASE),
        re.compile(r"posix.*sh", re.IGNORECASE),
    ],
    "implicit-detection": [
        re.compile(r"\.git.*not found", re.IGNORECASE),
        re.compile(r"\.git.*no such file", re.IGNORECASE),
        re.compile(r"not a git repository", re.IGNORECASE),
        re.compile(r"command not found", re.IGNORECASE),
        re.compile(r"which:.*no .* in", re.IGNORECASE),
    ],
    "config-drift": [
        re.compile(r"missing.*config", re.IGNORECASE),
        re.compile(r"config.*not found", re.IGNORECASE),
        re.compile(r"environment variable.*not set", re.IGNORECASE),
        re.compile(r"undefined variable", re.IGNORECASE),
    ],
    "auth-bootstrap": [
        re.compile(r"auth.*fail", re.IGNORECASE),
        re.compile(r"credential.*not found", re.IGNORECASE),
        re.compile(r"permission denied", re.IGNORECASE),
        re.compile(r"unauthorized", re.IGNORECASE),
        re.compile(r"\.netrc.*not found", re.IGNORECASE),
        re.compile(r"token.*expired", re.IGNORECASE),
    ],
    "dependency-missing": [
        re.compile(r"module.*not found", re.IGNORECASE),
        re.compile(r"no module named", re.IGNORECASE),
        re.compile(r"import.*error", re.IGNORECASE),
        re.compile(r"no such package", re.IGNORECASE),
        re.compile(r"could not resolve", re.IGNORECASE),
    ],
    "resource-contention": [
        re.compile(r"address already in use", re.IGNORECASE),
        re.compile(r"lock.*held", re.IGNORECASE),
        re.compile(r"port.*in use", re.IGNORECASE),
        re.compile(r"device or resource busy", re.IGNORECASE),
    ],
}

VALIDATION_GATES: dict[str, list[str]] = {
    "shell-compat": [
        (
            "Add a runtime contract script that validates shell interpreter"
            " and POSIX compliance before pipeline steps execute."
        ),
        (
            "Replace shell-specific syntax (e.g., [[ ]]) with"
            " POSIX-portable equivalents, or pin the interpreter in shebangs."
        ),
    ],
    "implicit-detection": [
        (
            "Replace implicit environment detection (e.g., checking for .git)"
            " with explicit sentinel files written during build/bake."
        ),
        (
            "Add a pre-deploy contract script that asserts all required"
            " artifacts exist before proceeding."
        ),
    ],
    "config-drift": [
        (
            "Add a config validation gate that checks all required"
            " environment variables and config files before deploy."
        ),
        (
            "Use a sentinel/manifest file listing expected config keys;"
            " validate it as a pipeline step."
        ),
    ],
    "auth-bootstrap": [
        (
            "Validate auth bootstrap early (credentials, tokens, .netrc)"
            " as the first pipeline step, before any deploy work begins."
        ),
        (
            "Add capability-based readiness checks that verify the service"
            " can actually use credentials, not just that they exist."
        ),
    ],
    "dependency-missing": [
        (
            "Pin all dependencies explicitly and validate the dependency"
            " tree in a pre-build contract step."
        ),
        (
            "Add a canary validation step that imports/loads critical"
            " modules before promoting the artifact."
        ),
    ],
    "resource-contention": [
        (
            "Add deploy locks (e.g., flock) on shared Docker hosts"
            " to prevent concurrent deploy races."
        ),
        (
            "Add a pre-deploy check that verifies required ports/resources"
            " are available before starting."
        ),
    ],
}

PATTERN_THRESHOLD = 2


@dataclass
class FailureInstance:
    """A single observed failure."""

    source: str
    step_id: str
    error: str
    category: str
    run_id: str = ""


@dataclass
class FailurePattern:
    """A detected pattern of repeated failures in the same category."""

    category: str
    count: int
    instances: list[FailureInstance] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class PatternReport:
    """Complete failure pattern analysis report."""

    total_runs_analyzed: int = 0
    total_failures: int = 0
    patterns: list[FailurePattern] = field(default_factory=list)

    @property
    def has_patterns(self) -> bool:
        return len(self.patterns) > 0

    def summary(self) -> str:
        if not self.has_patterns:
            return (
                f"Analyzed {self.total_runs_analyzed} runs,"
                f" {self.total_failures} failures."
                " No repeated failure patterns detected."
            )
        lines = [
            f"Analyzed {self.total_runs_analyzed} runs, {self.total_failures} failures.",
            f"Detected {len(self.patterns)} repeated failure pattern(s):",
            "",
        ]
        for p in self.patterns:
            lines.append(f"  [{p.category}] - {p.count} occurrences")
            for rec in p.recommendations:
                lines.append(f"    -> {rec}")
            lines.append("")
        return "\n".join(lines)


def classify_error(error_text: str) -> Optional[str]:
    """Classify an error message into a failure category."""
    for category, patterns in FAILURE_CATEGORIES.items():
        for pattern in patterns:
            if pattern.search(error_text):
                return category
    return None


def _scan_run_states(project_root: Path) -> list[FailureInstance]:
    """Scan .claude/runs/ for failed step records."""
    runs_dir = project_root / ".claude" / "runs"
    instances: list[FailureInstance] = []
    if not runs_dir.exists():
        return instances

    for state_file in runs_dir.glob("*.json"):
        try:
            data = json.loads(state_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        run_id = data.get("run_id", state_file.stem)
        for record in data.get("step_records", []):
            if record.get("status") != "failed":
                continue
            error_text = record.get("error", "") or record.get("output", "")
            if not error_text:
                continue
            category = classify_error(error_text)
            if category:
                instances.append(
                    FailureInstance(
                        source="run_state",
                        step_id=record.get("step_id", "unknown"),
                        error=error_text[:200],
                        category=category,
                        run_id=run_id,
                    )
                )
    return instances


def _scan_deploy_log(project_root: Path) -> list[FailureInstance]:
    """Scan .claude/deploy.log for failed deployments."""
    deploy_log = project_root / ".claude" / "deploy.log"
    instances: list[FailureInstance] = []
    if not deploy_log.exists():
        return instances

    try:
        lines = deploy_log.read_text().splitlines()
    except OSError:
        return instances

    for line in lines:
        parts = line.split("|")
        if len(parts) >= 5:
            exit_code = parts[4].strip()
            if exit_code != "0":
                error_text = line
                category = classify_error(error_text)
                if category:
                    instances.append(
                        FailureInstance(
                            source="deploy_log",
                            step_id="deploy",
                            error=error_text[:200],
                            category=category,
                        )
                    )
    return instances


def analyze_failure_patterns(
    project_root: Optional[Path] = None,
    threshold: int = PATTERN_THRESHOLD,
) -> PatternReport:
    """Analyze failure history and detect repeated patterns.

    Args:
        project_root: Project directory containing .claude/runs/ and .claude/deploy.log.
        threshold: Minimum occurrences to qualify as a pattern (default: 2).

    Returns:
        PatternReport with detected patterns and validation gate recommendations.
    """
    root = project_root or Path(".")

    run_instances = _scan_run_states(root)
    deploy_instances = _scan_deploy_log(root)
    all_instances = run_instances + deploy_instances

    runs_dir = root / ".claude" / "runs"
    total_runs = len(list(runs_dir.glob("*.json"))) if runs_dir.exists() else 0
    deploy_log = root / ".claude" / "deploy.log"
    deploy_entries = 0
    if deploy_log.exists():
        try:
            deploy_entries = len(deploy_log.read_text().splitlines())
        except OSError:
            pass

    category_groups: dict[str, list[FailureInstance]] = {}
    for inst in all_instances:
        category_groups.setdefault(inst.category, []).append(inst)

    patterns: list[FailurePattern] = []
    for category, instances in sorted(category_groups.items()):
        if len(instances) >= threshold:
            recs = VALIDATION_GATES.get(
                category,
                [
                    "Consider adding a validation gate for this failure category.",
                ],
            )
            patterns.append(
                FailurePattern(
                    category=category,
                    count=len(instances),
                    instances=instances,
                    recommendations=recs,
                )
            )

    patterns.sort(key=lambda p: p.count, reverse=True)

    return PatternReport(
        total_runs_analyzed=total_runs + deploy_entries,
        total_failures=len(all_instances),
        patterns=patterns,
    )
