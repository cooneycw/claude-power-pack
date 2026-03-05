"""CI/CD & Verification for Claude Code projects.

Provides:
- Framework detection (Python/Node/Go/Rust/multi)
- Makefile validation and generation
- Health checks (HTTP endpoints, process ports)
- Smoke tests (command execution with assertions)
- Configuration from .claude/cicd.yml

Quick Start:
    from lib.cicd import detect_framework, check_makefile

    # Detect project framework
    info = detect_framework("/path/to/project")
    print(info.framework, info.package_manager)

    # Check Makefile completeness
    result = check_makefile("/path/to/project")
    for gap in result.missing_required:
        print(f"Missing: {gap}")

    # Run health checks
    from lib.cicd import run_health_checks
    result = run_health_checks(project_root="/path/to/project")
    print(result.summary_line())

    # Run smoke tests
    from lib.cicd import run_smoke_tests
    result = run_smoke_tests(project_root="/path/to/project")
    print(result.summary_line())
"""

from .config import CICDConfig
from .container import generate_compose, generate_container_files, generate_dockerfile, generate_dockerignore
from .detector import detect_framework, detect_infrastructure
from .health import check_endpoint, check_process, run_health_checks
from .infrastructure import generate_discovery_script, generate_infra_pipeline, scaffold_infrastructure
from .makefile import check_makefile, generate_makefile, parse_makefile
from .models import (
    CloudProvider,
    Framework,
    FrameworkInfo,
    HealthCheckEntry,
    HealthCheckResult,
    IaCProvider,
    InfrastructureInfo,
    InfraTier,
    MakefileCheckResult,
    MakefileTarget,
    PackageManager,
    SmokeTestEntry,
    SmokeTestResult,
)
from .pipeline import generate_github_actions, generate_pipeline, generate_woodpecker
from .smoke import run_smoke_tests

__all__ = [
    # Config
    "CICDConfig",
    # Detector
    "detect_framework",
    "detect_infrastructure",
    # Health
    "run_health_checks",
    "check_endpoint",
    "check_process",
    # Smoke
    "run_smoke_tests",
    # Container
    "generate_container_files",
    "generate_dockerfile",
    "generate_compose",
    "generate_dockerignore",
    # Makefile
    "check_makefile",
    "generate_makefile",
    "parse_makefile",
    # Pipeline
    "generate_pipeline",
    "generate_github_actions",
    "generate_woodpecker",
    # Infrastructure
    "scaffold_infrastructure",
    "generate_infra_pipeline",
    "generate_discovery_script",
    # Models
    "CloudProvider",
    "IaCProvider",
    "InfraTier",
    "InfrastructureInfo",
    "Framework",
    "FrameworkInfo",
    "HealthCheckEntry",
    "HealthCheckResult",
    "MakefileCheckResult",
    "MakefileTarget",
    "PackageManager",
    "SmokeTestEntry",
    "SmokeTestResult",
]
