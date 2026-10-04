"""Deployment strategies with readiness gates, rollback, and guardrails.

Provides a pluggable strategy system for CI/CD deployments:
- DeploymentStrategy Protocol for custom strategies
- DockerComposeStrategy for docker compose deployments
- ReadinessPolicy for polling health endpoints after deploy
- Automatic rollback on readiness failure
- Deploy guardrails: stale commit checks, deploy locks, capability checks
"""

from .docker_compose import DockerComposeStrategy
from .guardrails import (
    CapabilityCheck,
    CapabilityResult,
    check_docker_socket,
    check_stale_commit,
    deploy_lock,
    run_capability_checks,
    safe_docker_prune,
)
from .strategy import (
    DeployConfig,
    DeploymentStrategy,
    ReadinessPolicy,
    ReadinessResult,
    get_strategy,
    poll_readiness,
    register_strategy,
)

__all__ = [
    "CapabilityCheck",
    "CapabilityResult",
    "DeployConfig",
    "DeploymentStrategy",
    "DockerComposeStrategy",
    "ReadinessPolicy",
    "ReadinessResult",
    "check_docker_socket",
    "check_stale_commit",
    "deploy_lock",
    "get_strategy",
    "poll_readiness",
    "register_strategy",
    "run_capability_checks",
    "safe_docker_prune",
]
