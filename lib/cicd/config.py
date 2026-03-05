"""CI/CD configuration.

Loads configuration from .claude/cicd.yml if present,
otherwise uses sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class BuildConfig:
    """Build system configuration."""

    framework: str = "auto"
    package_manager: str = "auto"
    required_targets: list[str] = field(default_factory=lambda: ["lint", "test"])
    recommended_targets: list[str] = field(
        default_factory=lambda: ["format", "typecheck", "build", "deploy", "clean", "verify"]
    )


@dataclass
class HealthEndpoint:
    """A single health check endpoint."""

    url: str
    name: str = ""
    expected_status: int = 200
    expected_body: str = ""
    timeout: int = 5


@dataclass
class ProcessCheck:
    """A process health check."""

    name: str
    port: int


@dataclass
class SmokeTest:
    """A smoke test definition."""

    name: str
    command: str
    expected_exit: int = 0
    expected_output: str = ""
    timeout: int = 10


@dataclass
class HealthConfig:
    """Health check and smoke test configuration."""

    endpoints: list[HealthEndpoint] = field(default_factory=list)
    processes: list[ProcessCheck] = field(default_factory=list)
    smoke_tests: list[SmokeTest] = field(default_factory=list)
    post_deploy: bool = False
    startup_delay: int = 0


@dataclass
class WoodpeckerConfig:
    """Woodpecker CI-specific configuration."""

    local: bool = True  # Use woodpecker exec for local runs


@dataclass
class PipelineConfig:
    """CI/CD pipeline configuration."""

    provider: str = "github-actions"  # github-actions | woodpecker | both
    branches: dict[str, list[str]] = field(
        default_factory=lambda: {
            "main": ["lint", "test", "typecheck", "build"],
            "pr": ["lint", "test", "typecheck"],
        }
    )
    matrix: dict[str, list[str]] = field(default_factory=dict)
    secrets_needed: list[str] = field(default_factory=list)
    woodpecker: WoodpeckerConfig = field(default_factory=WoodpeckerConfig)


@dataclass
class BranchProtection:
    """Branch protection rule suggestions."""

    require_pr_review: bool = True
    require_status_checks: list[str] = field(default_factory=lambda: ["lint", "test"])
    require_up_to_date: bool = True


@dataclass
class InfraTaggingConfig:
    """Tagging conventions for IaC resources."""

    managed_by: str = "terraform"
    repo: str = ""
    owner: str = ""
    extra_tags: dict[str, str] = field(default_factory=dict)


@dataclass
class InfraTierConfig:
    """Configuration for a single infrastructure tier."""

    approval_required: bool = False
    separate_credentials: bool = False


@dataclass
class InfraStateBackend:
    """Remote state backend configuration."""

    type: str = ""  # s3, azure-storage, gcs
    bucket: str = ""
    lock: bool = True
    region: str = ""


@dataclass
class InfrastructureConfig:
    """Infrastructure as Code configuration."""

    provider: str = "terraform"  # terraform, pulumi, bicep
    cloud: str = "aws"  # aws, azure, gcp
    state_backend: InfraStateBackend = field(default_factory=InfraStateBackend)
    tagging: InfraTaggingConfig = field(default_factory=InfraTaggingConfig)
    tiers: dict[str, InfraTierConfig] = field(
        default_factory=lambda: {
            "foundation": InfraTierConfig(approval_required=True, separate_credentials=True),
            "platform": InfraTierConfig(approval_required=False),
            "app": InfraTierConfig(approval_required=False),
        }
    )


@dataclass
class ContainerConfig:
    """Container configuration."""

    enabled: bool = False
    base_image: str = "auto"
    expose_ports: list[int] = field(default_factory=list)
    compose_services: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CICDConfig:
    """Full CI/CD configuration."""

    build: BuildConfig = field(default_factory=BuildConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    container: ContainerConfig = field(default_factory=ContainerConfig)
    infrastructure: InfrastructureConfig = field(default_factory=InfrastructureConfig)

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
        """Parse YAML config file."""
        try:
            import yaml
        except ImportError:
            return cls._defaults()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        config = cls._defaults()

        # Parse build section
        build_data = data.get("build", {})
        if build_data:
            config.build.framework = build_data.get("framework", "auto")
            config.build.package_manager = build_data.get("package_manager", "auto")
            if "required_targets" in build_data:
                config.build.required_targets = build_data["required_targets"]
            if "recommended_targets" in build_data:
                config.build.recommended_targets = build_data["recommended_targets"]

        # Parse health section
        health_data = data.get("health", {})
        if health_data:
            config.health.post_deploy = health_data.get("post_deploy", False)
            config.health.startup_delay = health_data.get("startup_delay", 0)

            for ep in health_data.get("endpoints", []):
                config.health.endpoints.append(
                    HealthEndpoint(
                        url=ep["url"],
                        name=ep.get("name", ""),
                        expected_status=ep.get("expected_status", 200),
                        expected_body=ep.get("expected_body", ""),
                        timeout=ep.get("timeout", 5),
                    )
                )

            for proc in health_data.get("processes", []):
                config.health.processes.append(
                    ProcessCheck(name=proc["name"], port=proc["port"])
                )

            for st in health_data.get("smoke_tests", []):
                config.health.smoke_tests.append(
                    SmokeTest(
                        name=st["name"],
                        command=st["command"],
                        expected_exit=st.get("expected_exit", 0),
                        expected_output=st.get("expected_output", ""),
                        timeout=st.get("timeout", 10),
                    )
                )

        # Parse pipeline section
        pipeline_data = data.get("pipeline", {})
        if pipeline_data:
            config.pipeline.provider = pipeline_data.get("provider", "github-actions")
            if "branches" in pipeline_data:
                config.pipeline.branches = pipeline_data["branches"]
            if "matrix" in pipeline_data:
                config.pipeline.matrix = pipeline_data["matrix"]
            if "secrets_needed" in pipeline_data:
                config.pipeline.secrets_needed = pipeline_data["secrets_needed"]
            wp_data = pipeline_data.get("woodpecker", {})
            if wp_data:
                config.pipeline.woodpecker.local = wp_data.get("local", True)

        # Parse container section
        container_data = data.get("container", {})
        if container_data:
            config.container.enabled = container_data.get("enabled", False)
            config.container.base_image = container_data.get("base_image", "auto")
            if "expose_ports" in container_data:
                config.container.expose_ports = container_data["expose_ports"]
            if "compose_services" in container_data:
                config.container.compose_services = container_data["compose_services"]

        # Parse infrastructure section
        infra_data = data.get("infrastructure", {})
        if infra_data:
            config.infrastructure.provider = infra_data.get("provider", "terraform")
            config.infrastructure.cloud = infra_data.get("cloud", "aws")

            state_data = infra_data.get("state_backend", {})
            if state_data:
                config.infrastructure.state_backend = InfraStateBackend(
                    type=state_data.get("type", ""),
                    bucket=state_data.get("bucket", ""),
                    lock=state_data.get("lock", True),
                    region=state_data.get("region", ""),
                )

            tagging_data = infra_data.get("tagging", {})
            if tagging_data:
                config.infrastructure.tagging = InfraTaggingConfig(
                    managed_by=tagging_data.get("managed-by", "terraform"),
                    repo=tagging_data.get("repo", ""),
                    owner=tagging_data.get("owner", ""),
                    extra_tags={
                        k: v for k, v in tagging_data.items()
                        if k not in ("managed-by", "repo", "owner")
                    },
                )

            tiers_data = infra_data.get("tiers", {})
            if tiers_data:
                config.infrastructure.tiers = {}
                for tier_name, tier_cfg in tiers_data.items():
                    config.infrastructure.tiers[tier_name] = InfraTierConfig(
                        approval_required=tier_cfg.get("approval_required", False),
                        separate_credentials=tier_cfg.get("separate_credentials", False),
                    )

        return config
