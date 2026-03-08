"""CI/CD configuration.

Loads configuration from .claude/cicd.yml if present,
otherwise uses sensible defaults.

Uses Pydantic v2 for validation with extra="ignore" for backwards
compatibility - existing configs load without errors even if they
contain unknown keys.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class BuildConfig(BaseModel):
    """Build system configuration."""

    model_config = ConfigDict(extra="ignore")

    framework: str = "auto"
    package_manager: str = "auto"
    required_targets: list[str] = Field(default_factory=lambda: ["lint", "test"])
    recommended_targets: list[str] = Field(
        default_factory=lambda: ["format", "typecheck", "build", "deploy", "clean", "verify"]
    )


class HealthEndpoint(BaseModel):
    """A single health check endpoint."""

    model_config = ConfigDict(extra="ignore")

    url: str
    name: str = ""
    expected_status: int = 200
    expected_body: str = ""
    timeout: int = 5


class ProcessCheck(BaseModel):
    """A process health check."""

    model_config = ConfigDict(extra="ignore")

    name: str
    port: int


class SmokeTest(BaseModel):
    """A smoke test definition."""

    model_config = ConfigDict(extra="ignore")

    name: str
    command: str
    expected_exit: int = 0
    expected_output: str = ""
    timeout: int = 10


class HealthConfig(BaseModel):
    """Health check and smoke test configuration."""

    model_config = ConfigDict(extra="ignore")

    endpoints: list[HealthEndpoint] = Field(default_factory=list)
    processes: list[ProcessCheck] = Field(default_factory=list)
    smoke_tests: list[SmokeTest] = Field(default_factory=list)
    post_deploy: bool = False
    startup_delay: int = 0


class WoodpeckerConfig(BaseModel):
    """Woodpecker CI-specific configuration."""

    model_config = ConfigDict(extra="ignore")

    local: bool = True  # Use woodpecker exec for local runs


class PipelineConfig(BaseModel):
    """CI/CD pipeline configuration."""

    model_config = ConfigDict(extra="ignore")

    provider: str = "github-actions"  # github-actions | woodpecker | both
    branches: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "main": ["lint", "test", "typecheck", "build"],
            "pr": ["lint", "test", "typecheck"],
        }
    )
    matrix: dict[str, list[str]] = Field(default_factory=dict)
    secrets_needed: list[str] = Field(default_factory=list)
    woodpecker: WoodpeckerConfig = Field(default_factory=WoodpeckerConfig)


class BranchProtection(BaseModel):
    """Branch protection rule suggestions."""

    model_config = ConfigDict(extra="ignore")

    require_pr_review: bool = True
    require_status_checks: list[str] = Field(default_factory=lambda: ["lint", "test"])
    require_up_to_date: bool = True


class InfraTaggingConfig(BaseModel):
    """Tagging conventions for IaC resources."""

    model_config = ConfigDict(extra="ignore")

    managed_by: str = "terraform"
    repo: str = ""
    owner: str = ""
    extra_tags: dict[str, str] = Field(default_factory=dict)


class InfraTierConfig(BaseModel):
    """Configuration for a single infrastructure tier."""

    model_config = ConfigDict(extra="ignore")

    approval_required: bool = False
    separate_credentials: bool = False


class InfraStateBackend(BaseModel):
    """Remote state backend configuration."""

    model_config = ConfigDict(extra="ignore")

    type: str = ""  # s3, azure-storage, gcs
    bucket: str = ""
    lock: bool = True
    region: str = ""


class InfrastructureConfig(BaseModel):
    """Infrastructure as Code configuration."""

    model_config = ConfigDict(extra="ignore")

    provider: str = "terraform"  # terraform, pulumi, bicep
    cloud: str = "aws"  # aws, azure, gcp
    state_backend: InfraStateBackend = Field(default_factory=InfraStateBackend)
    tagging: InfraTaggingConfig = Field(default_factory=InfraTaggingConfig)
    tiers: dict[str, InfraTierConfig] = Field(
        default_factory=lambda: {
            "foundation": InfraTierConfig(approval_required=True, separate_credentials=True),
            "platform": InfraTierConfig(approval_required=False),
            "app": InfraTierConfig(approval_required=False),
        }
    )


class ContainerConfig(BaseModel):
    """Container configuration."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    base_image: str = "auto"
    expose_ports: list[int] = Field(default_factory=list)
    compose_services: list[dict[str, Any]] = Field(default_factory=list)


class CICDConfig(BaseModel):
    """Full CI/CD configuration."""

    model_config = ConfigDict(extra="ignore")

    build: BuildConfig = Field(default_factory=BuildConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    container: ContainerConfig = Field(default_factory=ContainerConfig)
    infrastructure: InfrastructureConfig = Field(default_factory=InfrastructureConfig)

    @classmethod
    def load(cls, project_root: Optional[str] = None) -> CICDConfig:
        """Load config from .claude/cicd.yml or use defaults."""
        if project_root is None:
            project_root = os.getcwd()

        config_path = Path(project_root) / ".claude" / "cicd.yml"
        if config_path.exists():
            return cls._from_yaml(config_path)

        return cls._defaults()

    @classmethod
    def _defaults(cls) -> CICDConfig:
        return cls()

    @classmethod
    def _from_yaml(cls, path: Path) -> CICDConfig:
        """Parse YAML config file using Pydantic model_validate.

        With extra="ignore" on all models, unknown keys are silently
        dropped - ensuring backwards compatibility with older configs.
        """
        try:
            import yaml
        except ImportError:
            return cls._defaults()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # Handle tagging key mapping (managed-by -> managed_by)
        infra_data = data.get("infrastructure", {})
        if infra_data:
            tagging_data = infra_data.get("tagging", {})
            if tagging_data and "managed-by" in tagging_data:
                tagging_data["managed_by"] = tagging_data.pop("managed-by")
                # Collect extra tags (non-standard keys)
                known_keys = {"managed_by", "repo", "owner", "extra_tags"}
                extra = {k: v for k, v in tagging_data.items() if k not in known_keys}
                if extra:
                    tagging_data["extra_tags"] = extra
                    for k in extra:
                        del tagging_data[k]

        return cls.model_validate(data)

    @classmethod
    def validate_file(cls, path: Path) -> list[str]:
        """Validate a config file and return a list of issues with fix suggestions.

        Returns an empty list if the config is valid.
        """
        try:
            import yaml
        except ImportError:
            return ["PyYAML not installed - run: uv pip install pyyaml"]

        if not path.exists():
            return [f"Config file not found: {path}"]

        with open(path) as f:
            raw = f.read()

        # Check YAML syntax
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            return [f"YAML syntax error: {e}"]

        if not isinstance(data, dict):
            return ["Config must be a YAML mapping (dict), not a scalar or list"]

        issues: list[str] = []

        # Validate known sections
        known_sections = {"build", "health", "pipeline", "container", "infrastructure"}
        unknown = set(data.keys()) - known_sections
        if unknown:
            issues.append(
                f"Unknown top-level keys: {', '.join(sorted(unknown))}. "
                f"Valid keys: {', '.join(sorted(known_sections))}"
            )

        # Validate build section
        build_data = data.get("build", {})
        if build_data and isinstance(build_data, dict):
            if "provider" in build_data:
                issues.append(
                    "build.provider is not valid here. "
                    "Did you mean pipeline.provider? Move it to the 'pipeline' section."
                )

        # Validate pipeline section
        pipeline_data = data.get("pipeline", {})
        if pipeline_data and isinstance(pipeline_data, dict):
            provider = pipeline_data.get("provider", "")
            valid_providers = {"github-actions", "woodpecker", "both"}
            if provider and provider not in valid_providers:
                issues.append(
                    f"pipeline.provider '{provider}' is invalid. "
                    f"Valid values: {', '.join(sorted(valid_providers))}"
                )

        # Validate health section
        health_data = data.get("health", {})
        if health_data and isinstance(health_data, dict):
            for i, ep in enumerate(health_data.get("endpoints", [])):
                if isinstance(ep, dict) and "url" not in ep:
                    issues.append(f"health.endpoints[{i}] is missing required field 'url'")

            for i, proc in enumerate(health_data.get("processes", [])):
                if isinstance(proc, dict):
                    if "name" not in proc:
                        issues.append(f"health.processes[{i}] is missing required field 'name'")
                    if "port" not in proc:
                        issues.append(f"health.processes[{i}] is missing required field 'port'")

            for i, st in enumerate(health_data.get("smoke_tests", [])):
                if isinstance(st, dict):
                    if "name" not in st:
                        issues.append(f"health.smoke_tests[{i}] is missing required field 'name'")
                    if "command" not in st:
                        issues.append(f"health.smoke_tests[{i}] is missing required field 'command'")

        # Validate infrastructure section
        infra_data = data.get("infrastructure", {})
        if infra_data and isinstance(infra_data, dict):
            provider = infra_data.get("provider", "")
            valid_iac = {"terraform", "pulumi", "bicep"}
            if provider and provider not in valid_iac:
                issues.append(
                    f"infrastructure.provider '{provider}' is invalid. "
                    f"Valid values: {', '.join(sorted(valid_iac))}"
                )

            cloud = infra_data.get("cloud", "")
            valid_clouds = {"aws", "azure", "gcp"}
            if cloud and cloud not in valid_clouds:
                issues.append(
                    f"infrastructure.cloud '{cloud}' is invalid. "
                    f"Valid values: {', '.join(sorted(valid_clouds))}"
                )

        # Try Pydantic validation for type errors
        try:
            # Handle tagging mapping
            if infra_data:
                tagging_data = infra_data.get("tagging", {})
                if tagging_data and "managed-by" in tagging_data:
                    tagging_data = dict(tagging_data)
                    tagging_data["managed_by"] = tagging_data.pop("managed-by")
                    known_keys = {"managed_by", "repo", "owner", "extra_tags"}
                    extra = {k: v for k, v in tagging_data.items() if k not in known_keys}
                    if extra:
                        tagging_data["extra_tags"] = extra
                        for k in extra:
                            del tagging_data[k]
                    data = dict(data)
                    data["infrastructure"] = dict(data["infrastructure"])
                    data["infrastructure"]["tagging"] = tagging_data
            cls.model_validate(data)
        except Exception as e:
            issues.append(f"Validation error: {e}")

        return issues

    @classmethod
    def json_schema(cls) -> str:
        """Generate JSON Schema for IDE autocompletion."""
        return json.dumps(cls.model_json_schema(), indent=2)
