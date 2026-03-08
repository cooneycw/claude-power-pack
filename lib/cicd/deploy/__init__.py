"""Deployment strategies with readiness gates and rollback.

Provides a pluggable strategy system for CI/CD deployments:
- DeploymentStrategy Protocol for custom strategies
- DockerComposeStrategy for docker compose deployments
- ReadinessPolicy for polling health endpoints after deploy
- Automatic rollback on readiness failure
"""

from .docker_compose import DockerComposeStrategy
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
    "DeployConfig",
    "DeploymentStrategy",
    "DockerComposeStrategy",
    "ReadinessPolicy",
    "ReadinessResult",
    "get_strategy",
    "poll_readiness",
    "register_strategy",
]
