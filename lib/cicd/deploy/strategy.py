"""Deployment strategy protocol and readiness polling.

Defines the DeploymentStrategy Protocol that all strategy implementations
must follow, plus the ReadinessPolicy for health endpoint polling with
exponential backoff and consecutive success thresholds.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from ..steps import StepResult


class DeploymentStrategy(Protocol):
    """Protocol for deployment strategy implementations.

    Each strategy knows how to deploy, rollback, and check readiness
    for a specific deployment target (docker compose, AWS ECS, etc.)
    """

    name: str

    def deploy(self, context: dict[str, Any], config: DeployConfig) -> StepResult:
        """Execute the deployment.

        Args:
            context: Runner context (project_root, run_id, plan, env).
            config: Deployment configuration.

        Returns:
            StepResult with deploy outcome.
        """
        ...

    def rollback(self, context: dict[str, Any], config: DeployConfig) -> StepResult:
        """Roll back a failed deployment.

        Args:
            context: Runner context.
            config: Deployment configuration.

        Returns:
            StepResult with rollback outcome.
        """
        ...

    def check_readiness(self, context: dict[str, Any], config: DeployConfig) -> bool:
        """Single readiness check (not polling).

        Args:
            context: Runner context.
            config: Deployment configuration.

        Returns:
            True if the deployment target is ready.
        """
        ...


@dataclass
class ReadinessPolicy:
    """Configuration for readiness gate polling.

    Polls a URL until N consecutive successful responses or timeout.
    Uses exponential backoff between attempts.
    """

    url: str
    interval_seconds: float = 5.0
    timeout_seconds: float = 120.0
    consecutive_successes: int = 3
    backoff_multiplier: float = 1.5
    expected_status: int = 200

    def validate(self) -> list[str]:
        """Return validation errors, if any."""
        errors = []
        if not self.url:
            errors.append("readiness url is required")
        if self.interval_seconds <= 0:
            errors.append("interval_seconds must be positive")
        if self.timeout_seconds <= 0:
            errors.append("timeout_seconds must be positive")
        if self.consecutive_successes < 1:
            errors.append("consecutive_successes must be >= 1")
        if self.backoff_multiplier < 1.0:
            errors.append("backoff_multiplier must be >= 1.0")
        return errors


@dataclass
class DeployConfig:
    """Configuration for a deployment step.

    Loaded from the task manifest or constructed programmatically.
    """

    strategy: str = "docker_compose"
    compose_file: str = "docker-compose.yml"
    profiles: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    readiness: Optional[ReadinessPolicy] = None
    rollback_command: Optional[str] = None
    deploy_command: Optional[str] = None
    timeout_seconds: int = 900
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeployConfig:
        """Create from a dictionary (e.g., manifest config section)."""
        readiness_data = data.pop("readiness", None)
        readiness = ReadinessPolicy(**readiness_data) if readiness_data else None
        profiles = data.pop("profiles", [])
        services = data.pop("services", [])
        extra = {}
        known_keys = {
            "strategy", "compose_file", "readiness", "rollback_command",
            "deploy_command", "timeout_seconds", "profiles", "services",
        }
        for k, v in list(data.items()):
            if k not in known_keys:
                extra[k] = v
                data.pop(k)

        return cls(
            strategy=data.get("strategy", "docker_compose"),
            compose_file=data.get("compose_file", "docker-compose.yml"),
            profiles=profiles,
            services=services,
            readiness=readiness,
            rollback_command=data.get("rollback_command"),
            deploy_command=data.get("deploy_command"),
            timeout_seconds=data.get("timeout_seconds", 900),
            extra=extra,
        )


@dataclass
class ReadinessResult:
    """Result of a readiness polling session."""

    ready: bool
    attempts: int = 0
    consecutive_ok: int = 0
    elapsed_seconds: float = 0.0
    last_status: Optional[int] = None
    last_error: Optional[str] = None

    @property
    def summary(self) -> str:
        if self.ready:
            return (
                f"Ready after {self.attempts} attempts "
                f"({self.elapsed_seconds:.1f}s, "
                f"{self.consecutive_ok} consecutive OK)"
            )
        reason = self.last_error or f"HTTP {self.last_status}"
        return (
            f"Not ready after {self.attempts} attempts "
            f"({self.elapsed_seconds:.1f}s): {reason}"
        )


def poll_readiness(
    policy: ReadinessPolicy,
    sleep_fn: Any = None,
) -> ReadinessResult:
    """Poll a readiness URL until success threshold or timeout.

    Uses curl for HTTP checks (matching health.py pattern, no new deps).

    Args:
        policy: Readiness polling configuration.
        sleep_fn: Optional sleep function for testing (default: time.sleep).

    Returns:
        ReadinessResult with polling outcome.
    """
    if sleep_fn is None:
        sleep_fn = time.sleep

    curl_path = shutil.which("curl")
    if not curl_path:
        return ReadinessResult(
            ready=False,
            last_error="curl not found in PATH",
        )

    errors = policy.validate()
    if errors:
        return ReadinessResult(
            ready=False,
            last_error=f"Invalid policy: {'; '.join(errors)}",
        )

    start = time.monotonic()
    attempts = 0
    consecutive_ok = 0
    interval = policy.interval_seconds
    last_status: Optional[int] = None
    last_error: Optional[str] = None

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= policy.timeout_seconds:
            return ReadinessResult(
                ready=False,
                attempts=attempts,
                consecutive_ok=consecutive_ok,
                elapsed_seconds=elapsed,
                last_status=last_status,
                last_error=last_error or "Timeout exceeded",
            )

        attempts += 1

        try:
            proc = subprocess.run(
                [
                    curl_path,
                    "-sf",
                    "-o", "/dev/null",
                    "-w", "%{http_code}",
                    "--max-time", "5",
                    policy.url,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Parse status code from curl output
            try:
                status_code = int(proc.stdout.strip())
            except (ValueError, TypeError):
                status_code = 0

            last_status = status_code
            last_error = None

            if status_code == policy.expected_status:
                consecutive_ok += 1
                if consecutive_ok >= policy.consecutive_successes:
                    return ReadinessResult(
                        ready=True,
                        attempts=attempts,
                        consecutive_ok=consecutive_ok,
                        elapsed_seconds=time.monotonic() - start,
                        last_status=status_code,
                    )
            else:
                consecutive_ok = 0
                last_error = f"HTTP {status_code} (expected {policy.expected_status})"

        except subprocess.TimeoutExpired:
            consecutive_ok = 0
            last_error = "Request timed out"
        except OSError as e:
            consecutive_ok = 0
            last_error = str(e)

        # Check timeout before sleeping
        elapsed = time.monotonic() - start
        if elapsed + interval >= policy.timeout_seconds:
            # One last check: if we've already exceeded, break
            if elapsed >= policy.timeout_seconds:
                return ReadinessResult(
                    ready=False,
                    attempts=attempts,
                    consecutive_ok=consecutive_ok,
                    elapsed_seconds=elapsed,
                    last_status=last_status,
                    last_error=last_error or "Timeout exceeded",
                )

        sleep_fn(interval)
        # Apply backoff
        interval = min(interval * policy.backoff_multiplier, 30.0)


# --- Strategy registry ---

_STRATEGY_REGISTRY: dict[str, type] = {}


def register_strategy(name: str, strategy_cls: type) -> None:
    """Register a deployment strategy by name."""
    _STRATEGY_REGISTRY[name] = strategy_cls


def get_strategy(name: str) -> DeploymentStrategy:
    """Look up and instantiate a strategy by name.

    Args:
        name: Strategy name (e.g., "docker_compose").

    Returns:
        An instance of the named strategy.

    Raises:
        ValueError: If the strategy name is not registered.
    """
    if name not in _STRATEGY_REGISTRY:
        available = ", ".join(sorted(_STRATEGY_REGISTRY.keys())) or "(none)"
        raise ValueError(f"Unknown deployment strategy: {name}. Available: {available}")
    return _STRATEGY_REGISTRY[name]()
