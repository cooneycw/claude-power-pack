"""CI/CD & Verification for Claude Code projects.

Provides:
- Framework detection (Python/Node/Go/Rust/multi)
- Makefile validation and generation
- Health checks (HTTP endpoints, process ports)
- Smoke tests (command execution with assertions)
- Deploy verification (baseline comparison, proceed/review/rollback verdict)
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

# WHY THESE RE-EXPORTS ARE DEFERRED (issue #1163).
#
# This module used to import all sixteen submodules eagerly. Two of them -
# `config` and `manifest` - import pydantic, and four more (`health`,
# `infrastructure`, `pipeline`, `verify`) import `.config`. So `import
# lib.cicd.steps` pulled pydantic in, whatever `steps` itself needed - and
# `steps`, `runner`, `state`, `coverage`, `outcomes` and `models` need nothing
# outside the stdlib.
#
# The cost was paid by the negative-controls battery. Its CI step runs
# `ghcr.io/astral-sh/uv:python3.11-bookworm-slim`, which has no pydantic and no
# virtualenv, so NO registered control could exercise a gate whose path reaches
# `lib.cicd` - measured four ways in that image before this change. The
# alternatives were worse than the import graph: making the step `depends_on`
# the one that runs `uv sync` would leave the battery SILENT on a red tree,
# because a step whose dependency failed is skipped and every control's verdict
# then goes unreported; and syncing in the step adds a network dependency to a
# step that has none, where a registry outage and a blind instrument look alike
# in the log.
#
# Deferring costs the battery nothing. `__all__` is unchanged, every name
# resolves exactly as before, and NOTHING in this repository imported them
# through the package anyway - every consumer uses `from lib.cicd.<module>
# import ...` (checked, and there is no `import *` anywhere).
#
# tests/test_cicd_imports.py is the guard: it runs a SUBPROCESS with pydantic
# blocked and requires `steps` and `runner` to import there, so a new eager
# import at the top of this file fails loudly instead of quietly taking the
# battery's reach away again.
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # For type checkers and IDEs only - never executed at runtime. The names
    # below are the same ones `_NAME_TO_MODULE` resolves lazily, so mypy sees a
    # fully typed package while the interpreter imports nothing until asked.
    from .config import CICDConfig
    from .container import generate_compose, generate_container_files, generate_dockerfile, generate_dockerignore
    from .deploy import (
        DeployConfig,
        DeploymentStrategy,
        DockerComposeStrategy,
        ReadinessPolicy,
        ReadinessResult,
        get_strategy,
        poll_readiness,
        register_strategy,
    )
    from .detector import detect_framework, detect_infrastructure
    from .failure_patterns import FailurePattern, PatternReport, analyze_failure_patterns, classify_error
    from .health import check_endpoint, check_process, run_health_checks
    from .infrastructure import generate_discovery_script, generate_infra_pipeline, scaffold_infrastructure
    from .makefile import check_makefile, generate_makefile, parse_makefile
    from .manifest import (
        PlanModel,
        StepModel,
        TaskManifest,
        generate_manifest,
        load_manifest,
        write_manifest,
    )
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
    from .runner import DeterministicRunner, RunResult, resume_run, run_plan
    from .smoke import run_smoke_tests
    from .state import RunState, StepRecord, StepStatus
    from .steps import DeployStep, ShellStep, StepDef, StepResult
    from .verify import (
        DeployVerifyResult,
        ProbeDiff,
        ProbeResult,
        Verdict,
        VerificationSnapshot,
        capture_snapshot,
        load_baseline,
        save_baseline,
        verify_deployment,
    )


# name -> submodule, written out rather than derived. A derived table would
# have to import the modules to find out what they export, which is the thing
# this file exists to avoid.
_NAME_TO_MODULE = {
    "CICDConfig": "config",
    "CloudProvider": "models",
    "DeployConfig": "deploy",
    "DeployStep": "steps",
    "DeployVerifyResult": "verify",
    "DeploymentStrategy": "deploy",
    "DeterministicRunner": "runner",
    "DockerComposeStrategy": "deploy",
    "FailurePattern": "failure_patterns",
    "Framework": "models",
    "FrameworkInfo": "models",
    "HealthCheckEntry": "models",
    "HealthCheckResult": "models",
    "IaCProvider": "models",
    "InfraTier": "models",
    "InfrastructureInfo": "models",
    "MakefileCheckResult": "models",
    "MakefileTarget": "models",
    "PackageManager": "models",
    "PatternReport": "failure_patterns",
    "PlanModel": "manifest",
    "ProbeDiff": "verify",
    "ProbeResult": "verify",
    "ReadinessPolicy": "deploy",
    "ReadinessResult": "deploy",
    "RunResult": "runner",
    "RunState": "state",
    "ShellStep": "steps",
    "SmokeTestEntry": "models",
    "SmokeTestResult": "models",
    "StepDef": "steps",
    "StepModel": "manifest",
    "StepRecord": "state",
    "StepResult": "steps",
    "StepStatus": "state",
    "TaskManifest": "manifest",
    "Verdict": "verify",
    "VerificationSnapshot": "verify",
    "analyze_failure_patterns": "failure_patterns",
    "capture_snapshot": "verify",
    "check_endpoint": "health",
    "check_makefile": "makefile",
    "check_process": "health",
    "classify_error": "failure_patterns",
    "detect_framework": "detector",
    "detect_infrastructure": "detector",
    "generate_compose": "container",
    "generate_container_files": "container",
    "generate_discovery_script": "infrastructure",
    "generate_dockerfile": "container",
    "generate_dockerignore": "container",
    "generate_github_actions": "pipeline",
    "generate_infra_pipeline": "infrastructure",
    "generate_makefile": "makefile",
    "generate_manifest": "manifest",
    "generate_pipeline": "pipeline",
    "generate_woodpecker": "pipeline",
    "get_strategy": "deploy",
    "load_baseline": "verify",
    "load_manifest": "manifest",
    "parse_makefile": "makefile",
    "poll_readiness": "deploy",
    "register_strategy": "deploy",
    "resume_run": "runner",
    "run_health_checks": "health",
    "run_plan": "runner",
    "run_smoke_tests": "smoke",
    "save_baseline": "verify",
    "scaffold_infrastructure": "infrastructure",
    "verify_deployment": "verify",
    "write_manifest": "manifest",
}


def __getattr__(name: str) -> Any:
    """Resolve a re-exported name on first access (PEP 562)."""
    module = _NAME_TO_MODULE.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(f".{module}", __name__), name)
    globals()[name] = value  # resolve once; later access skips this function
    return value


def __dir__() -> list[str]:
    """`dir()` still lists the re-exports, which `__getattr__` alone would not."""
    return sorted(set(globals()) | set(_NAME_TO_MODULE))


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
    # Deploy verification
    "verify_deployment",
    "capture_snapshot",
    "save_baseline",
    "load_baseline",
    "Verdict",
    "VerificationSnapshot",
    "DeployVerifyResult",
    "ProbeResult",
    "ProbeDiff",
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
    # Deploy
    "DeployConfig",
    "DeploymentStrategy",
    "DeployStep",
    "DockerComposeStrategy",
    "ReadinessPolicy",
    "ReadinessResult",
    "get_strategy",
    "poll_readiness",
    "register_strategy",
    # Manifest
    "TaskManifest",
    "StepModel",
    "PlanModel",
    "load_manifest",
    "generate_manifest",
    "write_manifest",
    # Failure Patterns
    "analyze_failure_patterns",
    "classify_error",
    "FailurePattern",
    "PatternReport",
    # Runner
    "DeterministicRunner",
    "RunResult",
    "run_plan",
    "resume_run",
    "RunState",
    "StepRecord",
    "StepStatus",
    "ShellStep",
    "StepDef",
    "StepResult",
]
