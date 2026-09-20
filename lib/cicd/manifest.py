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
from .models import Framework

logger = logging.getLogger(__name__)

# The pyproject.toml token that signals each quality gate's tool is configured,
# used to build a make-or-`uv run` fallback + skip guard for Python/Django
# projects (issue #628): a detected `uv run <tool>` gate must not be
# skip_if-skipped merely because a Makefile target is absent, and it must skip
# when the tool is genuinely unconfigured rather than hard-fail.
_GATE_PYPROJECT_TOKENS = {"lint": "ruff", "test": "pytest", "typecheck": "mypy"}

# Re-exported from the reader-free module so the two cannot drift; steps.py
# needs the path when THIS module is the thing that will not import (#1163).
from .manifest_path import MANIFEST_FILENAME, MANIFEST_PATH  # noqa: E402
from .steps import gate_conditional_command  # noqa: E402

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
    env: dict[str, str] = Field(default_factory=dict)
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


def _plan_steps_covering_declared_gates(
    plan_name: str, steps: dict[str, Any], also: tuple[str, ...] = ()
) -> list[str]:
    """Ordered plan membership that always covers the built-in plan's gates.

    `generate_manifest` used to build a plan by filtering a literal id list on
    what the project could run. That silently DROPS a gate for any project
    lacking its target - the state #1155's reconciliation exists to refuse - so
    the generator and the gate contradicted each other.

    Any declared gate with no step defined is synthesised here from the built-in
    StepDef, whose `skip_if` already encodes "this repository has no such
    target". The gate then appears in the plan and SKIPS, which #628 reports by
    name, instead of disappearing.

    EVERY plan goes through this, `deploy` included. It was briefly scoped to
    finish and check, on the ground that deploy's security step is #1160's
    subject - but a generator with one derived rule for two plans and a literal
    list for the third is the same two-sources defect this issue is about, one
    file over. Deriving it also fixes #1160: the synthesised
    `deploy_security_scan` is built from the BUILT-IN StepDef, so it carries
    `flow_deploy` - which blocks CRITICAL and HIGH - instead of the
    `security_scan` the generated deploy plan used to reference, which is the
    FINISH scan and blocks CRITICAL only.

    `also` carries the plan's NON-gate members, which have no declaration to
    derive from and stay availability-filtered - `deploy` itself is one. They
    are appended after the gates, which is the built-in order.
    """
    from .steps import BUILTIN_PLANS

    declared = [d for d in BUILTIN_PLANS.get(plan_name, []) if d.gate]
    out: list[str] = []
    for step_def in declared:
        if step_def.id not in steps:
            steps[step_def.id] = StepModel(
                command=step_def.command,
                description=step_def.description,
                timeout=step_def.timeout_seconds,
                max_attempts=step_def.max_attempts,
                skip_if=step_def.skip_if,
                env=dict(step_def.env),
            )
        out.append(step_def.id)
    for step_id in also:
        if step_id in steps and step_id not in out:
            out.append(step_id)
    return out


def step_model_to_step_def(step_id: str, model: StepModel) -> Any:
    """Convert a Pydantic StepModel to a dataclass StepDef for the runner.

    This bridges the manifest layer (Pydantic) with the execution layer (dataclasses).
    """
    from .steps import GATE_STEP_IDS, StepDef

    return StepDef(
        id=step_id,
        # GATE-NESS IS INHERITED BY ID, NEVER DECLARED HERE (issue #1155).
        #
        # This field used not to be passed at all, so every manifest-resolved
        # step took the `False` default - and since the manifest WINS over
        # BUILTIN_PLANS, that made the gate set and the executed plan two
        # populations read from different files with nothing comparing them.
        # #1147 shipped a green over four of five gates through that gap.
        #
        # The alternative considered and rejected was a `gate:` key on
        # StepModel. It fails on its DEFAULT: every manifest in existence
        # defines lint/test/typecheck/security_scan with no such key, so the
        # day the key ships they all become non-gates - this issue's own defect,
        # made total and silent, by the fix for it. An author who omits the key
        # recreates it. Inheritance has no dangerous default and adds no third
        # place: an id the built-in plans declare a gate is a gate wherever it
        # appears, and an id they do not know is not one.
        #
        # Keyed by ID, which is the invariant already enforced - GATE_STEP_IDS
        # is id-keyed and tests/test_runner.py::TestGateDeclarationIsExhaustive
        # already refuses an id that is a gate in one plan and not another.
        gate=step_id in GATE_STEP_IDS,
        command=model.command,
        description=model.description,
        timeout_seconds=model.timeout,
        max_attempts=model.max_attempts,
        backoff_seconds=model.backoff_seconds,
        idempotent=model.idempotent,
        skip_if=model.skip_if,
        depends_on=list(model.depends_on),
        env=dict(model.env),
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

    is_python = info.framework in (Framework.PYTHON, Framework.DJANGO)

    for step_name, (desc, timeout) in standard_steps.items():
        have_runner = step_name in runners
        have_make = step_name in makefile_targets

        # Quality gates on a Python/Django project: prefer the Makefile target,
        # fall back to the framework's `uv run`/`python -m` command, and skip
        # ONLY when neither the target nor the tool (ruff/pytest/mypy in
        # pyproject) exists (issue #628). Previously a detected `uv run` command
        # was still skip_if-gated on the Makefile alone, so a Makefile-less
        # project skipped every gate and the runner reported a bare success -
        # the same false green in the generated manifest as in BUILTIN_PLANS.
        if step_name in _GATE_PYPROJECT_TOKENS and is_python and (have_runner or have_make):
            runner_cmd = runners.get(step_name)
            if have_make and runner_cmd:
                # ONE PRODUCER for this string; the subsumption allowlist
                # recognises it by EQUALITY against the same function (#1165).
                command = gate_conditional_command(step_name, runner_cmd)
            elif have_make:
                command = f"make {step_name}"
            else:
                command = runner_cmd  # type: ignore[assignment]
            token = _GATE_PYPROJECT_TOKENS[step_name]
            skip_if = (
                f'! grep -q "^{step_name}:" Makefile 2>/dev/null '
                f'&& ! grep -q "{token}" pyproject.toml 2>/dev/null'
            )
            steps[step_name] = StepModel(
                command=command,
                description=desc,
                timeout=timeout,
                idempotent=True,
                skip_if=skip_if,
            )
            continue

        # Non-gate steps (and non-Python gates): framework runner if available,
        # else the make target.
        if have_runner:
            command = runners[step_name]
        elif have_make:
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

    # Add security_scan step if lib.security is available. PYTHONPATH is set via
    # the step env (derived from the CPP checkout location, not a hardcoded
    # "${HOME}/Projects/..." that breaks under a sandbox / alternate checkout) so
    # ``python3 -m lib.security`` resolves wherever CPP lives (issue #534).
    from .steps import _CPP_ROOT

    steps["security_scan"] = StepModel(
        command="python3 -m lib.security gate flow_finish",
        description="Run security quick scan",
        timeout=120,
        skip_if="! python3 -c 'import lib.security' 2>/dev/null",
        env={"PYTHONPATH": _CPP_ROOT},
    )

    # `verify` is a QUALITY GATE in the finish plan (issue #1147), so it is
    # defined here explicitly rather than falling through to the extra-targets
    # loop below - which skips it by name, gives everything a 600s budget, and
    # would not put it in any plan. All three matter: `make verify` measured
    # 229.8s on this repository and grows with the suite, and a step killed by
    # its own budget reports a timeout rather than a result (#812); and a step
    # defined but never referenced from a plan is dead config, which is the
    # #617/#1147 precedence trap this file already warns about twice below.
    #
    # Generated manifests omitting it was a counter-model review finding: the
    # built-in plan and this repository's checked-in manifest both gained the
    # gate while every NEWLY GENERATED manifest still produced a four-step
    # finish plan, so a project scaffolded by CPP would never run its own
    # verification.
    # DEFINED UNCONDITIONALLY (#1155). It used to be `if "verify" in
    # makefile_targets`, which omitted the step from projects without the
    # target - and an omitted gate is exactly what #1155's reconciliation
    # refuses, so CPP would have generated manifests its own finish gate
    # rejects. The `skip_if` below already answers "this repo has no such
    # target" the right way: the step is in the plan, it skips, and #628
    # reports it BY NAME with its reason. Dropping is silent; skipping is loud.
    if True:
        steps["verify"] = StepModel(
            command="make verify",
            description="Run the repository's full verification pipeline (make verify)",
            timeout=1800,
            skip_if='! grep -q "^verify:" Makefile 2>/dev/null',
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

    # finish plan: lint -> test -> typecheck -> security_scan
    #
    # typecheck is in the plan, not just in `steps`, because the runner PREFERS
    # this manifest over BUILTIN_PLANS whenever one exists - so a manifest that
    # defines a typecheck step but never references it from a plan produces dead
    # config and the exact false green issue #617 is about: the gate reports ok,
    # the PR opens, and CI (which runs `make typecheck` in every shipped
    # template) goes red. Each step is filtered on `in steps`, so a project with
    # no typecheck target still gets a two-step plan.
    # MEMBERSHIP IS DERIVED FROM THE DECLARATION, not from what this project
    # happens to have (#1155). The old form filtered on `s in steps`, so a
    # project without a verify target got a finish plan without `verify` - and
    # the reconciliation this issue adds then reports that gate as DROPPED and
    # fails the gate. CPP would have been generating manifests its own finish
    # gate rejects, which a counter-model review caught and the author's tests
    # did not: every test resolved THIS repository's manifest, where every
    # target exists.
    #
    # Any declared gate this project cannot define a step for is synthesised
    # from the built-in StepDef, which already carries the right command and
    # the `skip_if` that skips it. So the plan always lists every gate, and a
    # gate this repo cannot run is REPORTED as skipped rather than vanishing.
    finish_steps = _plan_steps_covering_declared_gates("finish", steps)
    if finish_steps:
        plans["finish"] = PlanModel(
            steps=finish_steps,
            description="Quality gates for /flow:finish",
        )

    # check plan: lint -> test -> typecheck
    check_steps = _plan_steps_covering_declared_gates("check", steps)
    if check_steps:
        plans["check"] = PlanModel(
            steps=check_steps,
            description="Quick quality check for /flow:check",
        )

    # deploy plan: security_scan -> deploy
    # Derived like the others (#1155). The literal used to be
    # ["security_scan", "deploy"], and `security_scan` in a generated manifest
    # is the FINISH scan - so every generated deploy plan ran `flow_finish`,
    # blocking on CRITICAL only, where the deploy policy blocks on CRITICAL and
    # HIGH. A HIGH finding did not stop a deploy (#1160). Deriving from the
    # declaration synthesises `deploy_security_scan` with the built-in
    # `flow_deploy` command and fixes it.
    deploy_steps = _plan_steps_covering_declared_gates("deploy", steps, also=("deploy",))
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
        "#   steps.<name>.env         - Extra env vars (merged on top of sanitized base)\n"
        "#   steps.<name>.env.PYTEST_WORKERS - Per-test-step worker cap (highest precedence)\n"
        "#   CPP_TEST_WORKERS         - Host cap after host PYTEST_WORKERS; passed verbatim, no numeric validation\n"
        "#   steps.<name>.artifacts   - Output files to preserve\n"
        "#   steps.<name>.rollback    - Command to run on failure\n"
        "#   plans.<name>.steps       - Ordered list of step names\n"
        "#\n\n"
    )

    manifest_path.write_text(header + yaml_content)
    return manifest_path
