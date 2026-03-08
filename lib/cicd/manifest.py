"""Typed task manifest with Pydantic v2 validation.

Defines the schema for `.claude/cicd_tasks.yml` - a declarative manifest
that lets projects customize CI/CD plans and steps without modifying code.

The manifest is separate from `cicd.yml` (which handles build/health/pipeline config)
to avoid breaking changes. When present, the runner loads plans from the manifest;
when absent, it falls back to built-in defaults.

Schema:
    version: "1"
    steps:
      lint:
        command: "make lint"
        timeout: 300
        ...
    plans:
      finish:
        steps: [lint, test, security_scan]
      deploy:
        steps: [security_scan, deploy]
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

try:
    from pydantic import BaseModel, Field, ValidationError, field_validator
except ImportError:
    raise ImportError(
        "pydantic>=2.0 is required for manifest support. "
        "Install it with: uv add --dev pydantic"
    )

import yaml

from .detector import detect_framework
from .makefile import parse_makefile

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "cicd_tasks.yml"
MANIFEST_PATH = ".claude/cicd_tasks.yml"
SUPPORTED_VERSIONS = {"1"}


class StepModel(BaseModel):
    """Pydantic model for a single CI/CD step definition."""

    command: str
    description: str = ""
    timeout: int = Field(default=600, ge=1, le=7200)
    max_attempts: int = Field(default=1, ge=1, le=10)
    backoff_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
    idempotent: bool = True
    skip_if: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    rollback: Optional[str] = None

    model_config = {"extra": "ignore"}


class PlanModel(BaseModel):
    """Pydantic model for a named plan that composes steps."""

    steps: list[str]
    description: str = ""

    model_config = {"extra": "ignore"}

    @field_validator("steps")
    @classmethod
    def steps_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Plan must have at least one step")
        return v


class TaskManifest(BaseModel):
    """Root Pydantic model for `.claude/cicd_tasks.yml`.

    Defines steps (what to run) and plans (which steps to run together).
    """

    version: str = "1"
    steps: dict[str, StepModel] = Field(default_factory=dict)
    plans: dict[str, PlanModel] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}

    @field_validator("version")
    @classmethod
    def version_supported(cls, v: str) -> str:
        if v not in SUPPORTED_VERSIONS:
            supported = ", ".join(sorted(SUPPORTED_VERSIONS))
            raise ValueError(f"Unsupported manifest version '{v}'. Supported: {supported}")
        return v

    def validate_plan_references(self) -> list[str]:
        """Check that all plan step references point to defined steps.

        Returns list of error messages (empty if valid).
        """
        errors: list[str] = []
        for plan_name, plan in self.plans.items():
            for step_name in plan.steps:
                if step_name not in self.steps:
                    errors.append(
                        f"Plan '{plan_name}' references undefined step '{step_name}'. "
                        f"Available steps: {', '.join(sorted(self.steps.keys()))}"
                    )
        return errors

    def get_plan_step_models(self, plan_name: str) -> list[tuple[str, StepModel]]:
        """Get ordered step models for a plan.

        Returns list of (step_id, StepModel) tuples.

        Raises:
            ValueError: If plan not found or references undefined steps.
        """
        if plan_name not in self.plans:
            available = ", ".join(sorted(self.plans.keys()))
            raise ValueError(f"Unknown plan '{plan_name}' in manifest. Available: {available}")

        plan = self.plans[plan_name]
        result: list[tuple[str, StepModel]] = []
        for step_name in plan.steps:
            if step_name not in self.steps:
                raise ValueError(
                    f"Plan '{plan_name}' references undefined step '{step_name}'"
                )
            result.append((step_name, self.steps[step_name]))
        return result

    def to_yaml(self) -> str:
        """Serialize manifest to YAML string."""
        data: dict[str, Any] = {"version": self.version}

        if self.steps:
            steps_dict: dict[str, Any] = {}
            for name, step in self.steps.items():
                step_data = step.model_dump(exclude_defaults=True)
                steps_dict[name] = step_data
            data["steps"] = steps_dict

        if self.plans:
            plans_dict: dict[str, Any] = {}
            for name, plan in self.plans.items():
                plan_data = plan.model_dump(exclude_defaults=True)
                plans_dict[name] = plan_data
            data["plans"] = plans_dict

        return yaml.dump(data, default_flow_style=False, sort_keys=False)


def load_manifest(project_root: str | Path) -> Optional[TaskManifest]:
    """Load and validate a task manifest from `.claude/cicd_tasks.yml`.

    Returns None if no manifest file exists (backwards compatible).

    Raises:
        ValueError: If manifest exists but is invalid.
    """
    root = Path(project_root)
    manifest_path = root / MANIFEST_PATH

    if not manifest_path.exists():
        return None

    try:
        raw = yaml.safe_load(manifest_path.read_text())
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {MANIFEST_PATH}: {e}") from e

    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ValueError(f"{MANIFEST_PATH} must be a YAML mapping, got {type(raw).__name__}")

    try:
        manifest = TaskManifest.model_validate(raw)
    except ValidationError as e:
        errors = []
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            errors.append(f"  {loc}: {err['msg']}")
        raise ValueError(
            f"Invalid manifest {MANIFEST_PATH}:\n" + "\n".join(errors)
        ) from e

    # Validate cross-references
    ref_errors = manifest.validate_plan_references()
    if ref_errors:
        raise ValueError(
            f"Invalid manifest {MANIFEST_PATH}:\n" + "\n".join(f"  {e}" for e in ref_errors)
        )

    return manifest


def step_model_to_step_def(step_id: str, model: StepModel) -> Any:
    """Convert a Pydantic StepModel to a dataclass StepDef for the runner.

    This bridges the manifest layer (Pydantic) with the execution layer (dataclasses).
    """
    from .steps import StepDef

    return StepDef(
        id=step_id,
        command=model.command,
        description=model.description,
        timeout_seconds=model.timeout,
        max_attempts=model.max_attempts,
        backoff_seconds=model.backoff_seconds,
        idempotent=model.idempotent,
        skip_if=model.skip_if,
        depends_on=list(model.depends_on),
    )


def get_manifest_plan_steps(
    manifest: TaskManifest, plan_name: str
) -> list[Any]:
    """Get StepDef list for a plan from the manifest.

    Converts Pydantic models to dataclass StepDefs for runner consumption.
    """
    pairs = manifest.get_plan_step_models(plan_name)
    return [step_model_to_step_def(step_id, model) for step_id, model in pairs]


def generate_manifest(
    project_root: str | Path,
    include_existing_makefile: bool = True,
) -> TaskManifest:
    """Auto-generate a TaskManifest from detected framework and existing Makefile.

    Inspects the project to build a sensible default manifest:
    1. Detects framework and package manager
    2. Parses existing Makefile targets (if any)
    3. Generates steps from framework runner commands + Makefile targets
    4. Creates standard plans (finish, check, deploy)

    Args:
        project_root: Path to project root.
        include_existing_makefile: If True, incorporate existing Makefile targets.

    Returns:
        A TaskManifest ready to be serialized to YAML.
    """
    root = Path(project_root)
    info = detect_framework(root)

    steps: dict[str, StepModel] = {}
    runners = info.runner_commands

    # Build steps from Makefile targets if present
    makefile_targets: set[str] = set()
    if include_existing_makefile:
        parsed = parse_makefile(root)
        makefile_targets = {t.name for t in parsed}

    # Standard step definitions from framework runners
    standard_steps = {
        "lint": ("Run linter", 300),
        "test": ("Run tests", 600),
        "typecheck": ("Run type checker", 300),
        "format": ("Run formatter", 120),
        "build": ("Build project", 600),
        "deploy": ("Run deployment", 1800),
        "clean": ("Clean build artifacts", 60),
    }

    for step_name, (desc, timeout) in standard_steps.items():
        # Use framework runner command if available, otherwise use make target
        if step_name in runners:
            command = runners[step_name]
        elif step_name in makefile_targets:
            command = f"make {step_name}"
        else:
            continue

        skip_if = None
        if step_name in ("lint", "test", "typecheck", "format", "build", "clean"):
            skip_if = f'! grep -q "^{step_name}:" Makefile 2>/dev/null'

        idempotent = step_name != "deploy"

        steps[step_name] = StepModel(
            command=command,
            description=desc,
            timeout=timeout,
            idempotent=idempotent,
            skip_if=skip_if,
        )

    # Add security_scan step if lib.security is available
    steps["security_scan"] = StepModel(
        command=(
            'PYTHONPATH="${HOME}/Projects/claude-power-pack/lib" '
            "python3 -m lib.security gate flow_finish"
        ),
        description="Run security quick scan",
        timeout=120,
        skip_if="! python3 -c 'import lib.security' 2>/dev/null",
    )

    # Add any extra Makefile targets not already covered
    for target_name in sorted(makefile_targets - set(steps.keys())):
        if target_name.startswith(".") or target_name == "verify":
            continue
        steps[target_name] = StepModel(
            command=f"make {target_name}",
            description=f"Run {target_name}",
            timeout=600,
            skip_if=f'! grep -q "^{target_name}:" Makefile 2>/dev/null',
        )

    # Build standard plans
    plans: dict[str, PlanModel] = {}

    # finish plan: lint -> test -> security_scan
    finish_steps = [s for s in ["lint", "test", "security_scan"] if s in steps]
    if finish_steps:
        plans["finish"] = PlanModel(
            steps=finish_steps,
            description="Quality gates for /flow:finish",
        )

    # check plan: lint -> test
    check_steps = [s for s in ["lint", "test"] if s in steps]
    if check_steps:
        plans["check"] = PlanModel(
            steps=check_steps,
            description="Quick quality check for /flow:check",
        )

    # deploy plan: security_scan -> deploy
    deploy_steps = [s for s in ["security_scan", "deploy"] if s in steps]
    if deploy_steps:
        plans["deploy"] = PlanModel(
            steps=deploy_steps,
            description="Deployment pipeline for /flow:deploy",
        )

    return TaskManifest(version="1", steps=steps, plans=plans)


def write_manifest(manifest: TaskManifest, project_root: str | Path) -> Path:
    """Write a TaskManifest to `.claude/cicd_tasks.yml`.

    Returns the path to the written file.
    """
    root = Path(project_root)
    manifest_dir = root / ".claude"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / MANIFEST_FILENAME

    yaml_content = manifest.to_yaml()

    header = (
        "# .claude/cicd_tasks.yml - Task manifest for CI/CD runner\n"
        "#\n"
        "# Defines steps (what to run) and plans (which steps to run together).\n"
        "# The runner loads this manifest when present; falls back to built-in defaults otherwise.\n"
        "#\n"
        "# Auto-generated by: python -m lib.cicd init-manifest\n"
        "# Edit freely - this file is yours to customize.\n"
        "#\n"
        "# Reference:\n"
        "#   steps.<name>.command     - Shell command to execute\n"
        "#   steps.<name>.timeout     - Max seconds (default: 600)\n"
        "#   steps.<name>.max_attempts - Retry count (default: 1)\n"
        "#   steps.<name>.idempotent  - Safe to retry? (default: true)\n"
        "#   steps.<name>.skip_if     - Shell expression; skip if exits 0\n"
        "#   steps.<name>.artifacts   - Output files to preserve\n"
        "#   steps.<name>.rollback    - Command to run on failure\n"
        "#   plans.<name>.steps       - Ordered list of step names\n"
        "#\n\n"
    )

    manifest_path.write_text(header + yaml_content)
    return manifest_path
