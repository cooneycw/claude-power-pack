"""Bootstrap dependency checker for the CI/CD runner.

Detects admin-only bootstrap prerequisites (IAM roles, secrets provisioning,
manual infrastructure steps) and blocks deploy/merge if they are not satisfied.

Projects declare bootstrap dependencies in .claude/bootstrap.yaml. Each
dependency has a check_command that exits 0 when satisfied. If any check
fails, the gate blocks with a remediation message.

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

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> BootstrapDependency:
        return cls(
            name=name,
            description=data.get("description", ""),
            check_command=data["check_command"],
            remediation=data.get("remediation", f"Run the bootstrap step for '{name}'"),
            timeout_seconds=data.get("timeout_seconds", 30),
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
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=dep.name,
            satisfied=False,
            description=dep.description,
            remediation=dep.remediation,
            error=f"Check timed out after {dep.timeout_seconds}s",
        )
    except OSError as e:
        return CheckResult(
            name=dep.name,
            satisfied=False,
            description=dep.description,
            remediation=dep.remediation,
            error=str(e),
        )


def check_all(project_root: Path) -> tuple[bool, list[CheckResult]]:
    """Check all bootstrap dependencies.

    Returns:
        Tuple of (all_satisfied, results).
    """
    config = BootstrapConfig.load(project_root)
    if config is None:
        return True, []

    if not config.dependencies:
        return True, []

    results = [check_dependency(dep, project_root) for dep in config.dependencies]
    all_satisfied = all(r.satisfied for r in results)
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
    print(f"Config: {BLUE}{project_root / CONFIG_FILENAME}{NC}")
    print()

    if not results:
        print(f"{GREEN}No bootstrap dependencies configured.{NC}")
        return

    satisfied_count = sum(1 for r in results if r.satisfied)
    blocked_count = len(results) - satisfied_count

    for r in results:
        if r.satisfied:
            print(f"{GREEN}ok{NC}    {r.name} - {r.description}")
        else:
            print(f"{RED}BLOCK{NC} {r.name} - {r.description}")
            if r.error:
                print(f"       {YELLOW}error:{NC} {r.error}")
            print(f"       {YELLOW}fix:{NC}   {r.remediation}")

    print()
    print("================================================")
    if blocked_count > 0:
        print(
            f"{RED}BLOCKED{NC}: {blocked_count} bootstrap prerequisite(s) not satisfied "
            f"({satisfied_count}/{len(results)} passed)"
        )
        print()
        print(f"{BOLD}These require a manual bootstrap apply outside CI before deploying.{NC}")
    else:
        print(f"{GREEN}ALL SATISFIED{NC}: {satisfied_count}/{len(results)} bootstrap prerequisites passed")


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
        if config is None or not config.dependencies:
            print("No bootstrap dependencies configured.")
            return 0
        for dep in config.dependencies:
            print(f"  {dep.name}: {dep.description}")
            print(f"    check: {dep.check_command}")
            print(f"    fix:   {dep.remediation}")
        return 0

    if config is None:
        return 0

    passed, results = check_all(project_root)
    _print_report(passed, results, project_root)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
