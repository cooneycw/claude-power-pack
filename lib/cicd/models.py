"""Data models for CI/CD & Verification.

Provides:
- Framework: Enum for detected project frameworks
- PackageManager: Enum for detected package managers
- FrameworkInfo: Detection results with recommendations
- MakefileTarget: A parsed Makefile target
- MakefileCheckResult: Validation results for a Makefile
- HealthCheckResult: Results from health endpoint/process checks
- SmokeTestResult: Results from smoke test execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Framework(Enum):
    """Detected project framework."""

    PYTHON = "python"
    DJANGO = "django"
    NODE = "node"
    GO = "go"
    RUST = "rust"
    MULTI = "multi"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        labels = {
            Framework.PYTHON: "Python",
            Framework.DJANGO: "Django",
            Framework.NODE: "Node.js",
            Framework.GO: "Go",
            Framework.RUST: "Rust",
            Framework.MULTI: "Multi-language",
            Framework.UNKNOWN: "Unknown",
        }
        return labels[self]


class PackageManager(Enum):
    """Detected package manager."""

    UV = "uv"
    PIP = "pip"
    POETRY = "poetry"
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    CARGO = "cargo"
    GO = "go"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return self.value


# Standard Makefile targets that /flow commands expect
REQUIRED_TARGETS = ["lint", "test"]
RECOMMENDED_TARGETS = ["format", "typecheck", "build", "deploy", "clean", "verify"]


# Framework-specific recommended targets
FRAMEWORK_TARGETS: dict[Framework, list[str]] = {
    Framework.PYTHON: ["lint", "test", "typecheck", "format", "build", "deploy", "clean", "verify"],
    Framework.DJANGO: [
        "lint", "test", "typecheck", "format", "build", "deploy", "clean", "verify",
        "migrate", "collectstatic", "check", "runserver",
    ],
    Framework.NODE: ["lint", "test", "typecheck", "build", "deploy", "clean", "dev", "verify"],
    Framework.GO: ["lint", "test", "vet", "build", "deploy", "clean", "verify"],
    Framework.RUST: ["lint", "test", "build", "build-release", "deploy", "clean", "verify"],
    Framework.MULTI: ["lint", "test", "build", "deploy", "clean", "verify"],
    Framework.UNKNOWN: ["lint", "test", "build", "deploy", "clean"],
}

# Framework-specific runner commands
FRAMEWORK_RUNNERS: dict[tuple[Framework, PackageManager], dict[str, str]] = {
    (Framework.PYTHON, PackageManager.UV): {
        "lint": "uv run ruff check .",
        "test": "uv run pytest",
        "typecheck": "uv run mypy .",
        "format": "uv run ruff format .",
        "build": "uv build",
    },
    (Framework.PYTHON, PackageManager.PIP): {
        "lint": "python -m ruff check .",
        "test": "python -m pytest",
        "typecheck": "python -m mypy .",
        "format": "python -m ruff format .",
        "build": "python -m build",
    },
    (Framework.DJANGO, PackageManager.UV): {
        "lint": "uv run ruff check .",
        "test": "uv run python manage.py test --verbosity=2",
        "typecheck": "uv run mypy .",
        "format": "uv run ruff format .",
        "build": "uv build",
        "migrate": "uv run python manage.py migrate",
        "collectstatic": "uv run python manage.py collectstatic --noinput",
        "check": "uv run python manage.py check --deploy",
        "runserver": "uv run python manage.py runserver",
    },
    (Framework.DJANGO, PackageManager.PIP): {
        "lint": "python -m ruff check .",
        "test": "python manage.py test --verbosity=2",
        "typecheck": "python -m mypy .",
        "format": "python -m ruff format .",
        "build": "python -m build",
        "migrate": "python manage.py migrate",
        "collectstatic": "python manage.py collectstatic --noinput",
        "check": "python manage.py check --deploy",
        "runserver": "python manage.py runserver",
    },
    (Framework.NODE, PackageManager.NPM): {
        "lint": "npm run lint",
        "test": "npm test",
        "typecheck": "npx tsc --noEmit",
        "build": "npm run build",
        "dev": "npm run dev",
    },
    (Framework.NODE, PackageManager.YARN): {
        "lint": "yarn lint",
        "test": "yarn test",
        "typecheck": "yarn tsc --noEmit",
        "build": "yarn build",
        "dev": "yarn dev",
    },
    (Framework.GO, PackageManager.GO): {
        "lint": "golangci-lint run",
        "test": "go test ./...",
        "vet": "go vet ./...",
        "build": "go build -o bin/ ./...",
    },
    (Framework.RUST, PackageManager.CARGO): {
        "lint": "cargo clippy -- -D warnings",
        "test": "cargo test",
        "build": "cargo build",
        "build-release": "cargo build --release",
    },
}


@dataclass
class FrameworkInfo:
    """Results from framework detection."""

    framework: Framework
    package_manager: PackageManager
    detected_files: list[str] = field(default_factory=list)
    recommended_targets: list[str] = field(default_factory=list)
    runner_commands: dict[str, str] = field(default_factory=dict)
    secondary_frameworks: list[Framework] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "framework": self.framework.value,
            "package_manager": self.package_manager.value,
            "detected_files": self.detected_files,
            "recommended_targets": self.recommended_targets,
            "runner_commands": self.runner_commands,
            "secondary_frameworks": [f.value for f in self.secondary_frameworks],
        }


@dataclass
class MakefileTarget:
    """A parsed target from a Makefile."""

    name: str
    dependencies: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    is_phony: bool = False


@dataclass
class MakefileCheckResult:
    """Validation results for a Makefile."""

    targets_found: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    phony_declared: list[str] = field(default_factory=list)
    phony_missing: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    framework: Optional[Framework] = None
    package_manager: Optional[PackageManager] = None

    @property
    def is_healthy(self) -> bool:
        return len(self.missing_required) == 0 and len(self.issues) == 0

    @property
    def target_coverage(self) -> str:
        """e.g. '5/7 targets'"""
        total = len(self.targets_found) + len(self.missing_required) + len(self.missing_recommended)
        return f"{len(self.targets_found)}/{total} targets"

    def summary_line(self) -> str:
        """One-line summary for flow integration."""
        if self.is_healthy:
            return f"Makefile OK: {self.target_coverage}"
        parts = []
        if self.missing_required:
            parts.append(f"{len(self.missing_required)} required missing")
        if self.issues:
            parts.append(f"{len(self.issues)} issues")
        return f"Makefile: {', '.join(parts)}"

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "targets_found": self.targets_found,
            "missing_required": self.missing_required,
            "missing_recommended": self.missing_recommended,
            "phony_declared": self.phony_declared,
            "phony_missing": self.phony_missing,
            "issues": self.issues,
            "is_healthy": self.is_healthy,
            "target_coverage": self.target_coverage,
        }


@dataclass
class HealthCheckEntry:
    """Result of a single health check (endpoint or process)."""

    name: str
    kind: str  # "endpoint" or "process"
    passed: bool
    detail: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "passed": self.passed,
            "detail": self.detail,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


@dataclass
class HealthCheckResult:
    """Aggregated results from all health checks."""

    checks: list[HealthCheckEntry] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.failed == 0

    def summary_line(self) -> str:
        if not self.checks:
            return "Health: no checks configured"
        if self.all_passed:
            return f"Health: {self.passed}/{self.total} checks passed"
        return f"Health: {self.failed}/{self.total} checks FAILED"

    def to_dict(self) -> dict:
        return {
            "checks": [c.to_dict() for c in self.checks],
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "all_passed": self.all_passed,
        }


@dataclass
class SmokeTestEntry:
    """Result of a single smoke test."""

    name: str
    command: str
    passed: bool
    exit_code: int = 0
    output: str = ""
    detail: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "output": self.output,
            "detail": self.detail,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


@dataclass
class SmokeTestResult:
    """Aggregated results from all smoke tests."""

    tests: list[SmokeTestEntry] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if not t.passed)

    @property
    def total(self) -> int:
        return len(self.tests)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.failed == 0

    def summary_line(self) -> str:
        if not self.tests:
            return "Smoke: no tests configured"
        if self.all_passed:
            return f"Smoke: {self.passed}/{self.total} tests passed"
        return f"Smoke: {self.failed}/{self.total} tests FAILED"

    def to_dict(self) -> dict:
        return {
            "tests": [t.to_dict() for t in self.tests],
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "all_passed": self.all_passed,
        }
