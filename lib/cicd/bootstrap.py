"""Bootstrap dependency checker for the CI/CD runner.

Detects bootstrap prerequisites (IAM roles, secrets provisioning, manual
infrastructure steps) and blocks deploy/merge if required checks are not
satisfied. Advisory checks report findings without changing the verdict.

Projects declare bootstrap dependencies in .claude/bootstrap.yaml. Each
dependency has a check_command that exits 0 when satisfied. If any required
check fails, the gate blocks with a remediation message.

Usage:
    python -m lib.cicd.bootstrap check [--project-root PATH]
    python -m lib.cicd.bootstrap list  [--project-root PATH]
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

CONFIG_FILENAME = ".claude/bootstrap.yaml"


@dataclass
class BootstrapDependency:
    """A single bootstrap prerequisite."""

    name: str
    description: str
    check_command: str
    remediation: str
    timeout_seconds: int = 30
    advisory: bool = False

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> BootstrapDependency:
        return cls(
            name=name,
            description=data.get("description", ""),
            check_command=data["check_command"],
            remediation=data.get("remediation", f"Run the bootstrap step for '{name}'"),
            timeout_seconds=data.get("timeout_seconds", 30),
            advisory=data.get("advisory", False),
        )


@dataclass
class BootstrapConfig:
    """Configuration for bootstrap dependency checking."""

    version: str = "1"
    dependencies: list[BootstrapDependency] = field(default_factory=list)

    @classmethod
    def load(cls, project_root: Path) -> Optional[BootstrapConfig]:
        config_path = project_root / CONFIG_FILENAME
        if not config_path.exists():
            return None

        with open(config_path) as f:
            raw = yaml.safe_load(f)

        if not raw or not isinstance(raw, dict):
            return None

        deps = []
        for name, dep_data in raw.get("dependencies", {}).items():
            if isinstance(dep_data, dict) and "check_command" in dep_data:
                deps.append(BootstrapDependency.from_dict(name, dep_data))

        return cls(
            version=raw.get("version", "1"),
            dependencies=deps,
        )


@dataclass
class CheckResult:
    """Result of checking a single bootstrap dependency."""

    name: str
    satisfied: bool
    description: str = ""
    remediation: str = ""
    error: str = ""
    advisory: bool = False


def built_in_advisories(project_root: Path) -> list[BootstrapDependency]:
    """Return built-in advisory checks that apply to the project."""
    python_markers = ("pyproject.toml", "requirements.txt", "setup.py")
    if not any((project_root / marker).is_file() for marker in python_markers):
        return []

    return [
        BootstrapDependency(
            name="python3-venv",
            description="Python stdlib virtual environments require ensurepip",
            check_command='python3 -c "import ensurepip"',
            remediation=(
                "Use `uv venv .venv` (preferred; uv is already a CPP prerequisite), "
                "or run `apt install python3-venv` for the stdlib path."
            ),
            advisory=True,
        )
    ]


def check_dependency(dep: BootstrapDependency, project_root: Path) -> CheckResult:
    """Run a dependency's check_command and return the result."""
    try:
        proc = subprocess.run(
            dep.check_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=dep.timeout_seconds,
            cwd=str(project_root),
        )
        return CheckResult(
            name=dep.name,
            satisfied=proc.returncode == 0,
            description=dep.description,
            remediation=dep.remediation,
            error=proc.stderr.strip() if proc.returncode != 0 else "",
            advisory=dep.advisory,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=dep.name,
            satisfied=False,
            description=dep.description,
            remediation=dep.remediation,
            error=f"Check timed out after {dep.timeout_seconds}s",
            advisory=dep.advisory,
        )
    except OSError as e:
        return CheckResult(
            name=dep.name,
            satisfied=False,
            description=dep.description,
            remediation=dep.remediation,
            error=str(e),
            advisory=dep.advisory,
        )


def check_all(project_root: Path) -> tuple[bool, list[CheckResult]]:
    """Check all bootstrap dependencies.

    Returns:
        Tuple of (all_satisfied, results).
    """
    config = BootstrapConfig.load(project_root)
    dependencies = list(config.dependencies) if config is not None else []
    dependencies.extend(built_in_advisories(project_root))
    if not dependencies:
        return True, []

    results = [check_dependency(dep, project_root) for dep in dependencies]
    all_satisfied = all(r.satisfied or r.advisory for r in results)
    return all_satisfied, results


RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
NC = "\033[0m"


def _print_report(passed: bool, results: list[CheckResult], project_root: Path) -> None:
    """Print a human-readable report."""
    print(f"\n{BOLD}Bootstrap Dependency Check{NC}")
    print("================================================")
    config_path = project_root / CONFIG_FILENAME
    if config_path.exists():
        print(f"Config: {BLUE}{config_path}{NC}")
    else:
        print(f"Config: {BLUE}none (only built-in advisories shown){NC}")
    print()

    if not results:
        print(f"{GREEN}No bootstrap dependencies configured.{NC}")
        return

    blocking_results = [r for r in results if not r.advisory]
    advisory_results = [r for r in results if r.advisory]
    satisfied_count = sum(1 for r in blocking_results if r.satisfied)
    blocked_count = len(blocking_results) - satisfied_count
    advisory_satisfied_count = sum(1 for r in advisory_results if r.satisfied)
    advisory_warning_count = len(advisory_results) - advisory_satisfied_count

    for r in results:
        if r.satisfied:
            advisory_label = " (advisory)" if r.advisory else ""
            print(f"{GREEN}ok{NC}    {r.name}{advisory_label} - {r.description}")
        elif r.advisory:
            print(f"{YELLOW}WARN{NC}  {r.name} - {r.description}")
            if r.error:
                print(f"       {YELLOW}error:{NC} {r.error}")
            print(f"       {YELLOW}fix:{NC}   {r.remediation}")
        else:
            print(f"{RED}BLOCK{NC} {r.name} - {r.description}")
            if r.error:
                print(f"       {YELLOW}error:{NC} {r.error}")
            print(f"       {YELLOW}fix:{NC}   {r.remediation}")

    print()
    print("================================================")
    advisory_summary = ""
    if advisory_results:
        advisory_summary = (
            f"; advisories: {advisory_satisfied_count}/{len(advisory_results)} satisfied, "
            f"{advisory_warning_count} warning(s)"
        )

    if not passed:
        print(
            f"{RED}BLOCKED{NC}: {blocked_count} bootstrap prerequisite(s) not satisfied "
            f"({satisfied_count}/{len(blocking_results)} blocking passed{advisory_summary})"
        )
        print()
        print(f"{BOLD}These require a manual bootstrap apply outside CI before deploying.{NC}")
    else:
        status = "PASSED" if advisory_warning_count else "ALL SATISFIED"
        print(
            f"{GREEN}{status}{NC}: {satisfied_count}/{len(blocking_results)} "
            f"blocking prerequisites passed{advisory_summary}"
        )


def main(args: list[str] | None = None) -> int:
    """CLI entry point."""
    if args is None:
        args = sys.argv[1:]

    project_root = Path(".")
    command = "check"

    i = 0
    while i < len(args):
        if args[i] == "--project-root" and i + 1 < len(args):
            project_root = Path(args[i + 1])
            i += 2
        elif args[i] in ("check", "list"):
            command = args[i]
            i += 1
        else:
            i += 1

    config = BootstrapConfig.load(project_root)

    if command == "list":
        dependencies = list(config.dependencies) if config is not None else []
        dependencies.extend(built_in_advisories(project_root))
        if not dependencies:
            print("No bootstrap dependencies configured.")
            return 0
        for dep in dependencies:
            advisory_label = " (advisory)" if dep.advisory else ""
            print(f"  {dep.name}{advisory_label}: {dep.description}")
            print(f"    check: {dep.check_command}")
            print(f"    fix:   {dep.remediation}")
        return 0

    passed, results = check_all(project_root)
    _print_report(passed, results, project_root)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
