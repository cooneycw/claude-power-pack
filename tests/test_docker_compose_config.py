"""Tests for checked-in Docker Compose deployment config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _env_list_to_map(values: list[str]) -> dict[str, str | None]:
    env: dict[str, str | None] = {}
    for value in values:
        if "=" in value:
            key, raw = value.split("=", 1)
            env[key] = raw
        else:
            env[value] = None
    return env


def _compose_services() -> dict[str, Any]:
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text())
    return compose["services"]


def _woodpecker_steps() -> dict[str, Any]:
    pipeline_path = Path(__file__).resolve().parents[1] / ".woodpecker.yml"
    pipeline = yaml.safe_load(pipeline_path.read_text())
    return pipeline["steps"]


def test_aws_secrets_agent_does_not_require_root_env_file() -> None:
    services = _compose_services()
    env_file = services["aws-secrets-agent"]["env_file"][0]

    assert env_file["path"] == ".env"
    assert env_file["required"] is False


def test_aws_secrets_agent_accepts_ci_environment_credentials() -> None:
    services = _compose_services()
    env = _env_list_to_map(services["aws-secrets-agent"]["environment"])

    assert "AWS_ACCESS_KEY_ID" in env
    assert "AWS_SECRET_ACCESS_KEY" in env
    assert "AWS_SESSION_TOKEN" in env
    assert env["AWS_REGION"] == "us-east-1"
    assert env["AWS_TOKEN"] == "${AWS_TOKEN:-default-token}"


def test_secret_consumers_share_sidecar_token_default() -> None:
    services = _compose_services()
    agent_healthcheck = services["aws-secrets-agent"]["healthcheck"]["test"]

    assert "X-Aws-Parameters-Secrets-Token: ${AWS_TOKEN:-default-token}" in agent_healthcheck
    for service_name in ("mcp-second-opinion", "mcp-woodpecker-ci"):
        env = _env_list_to_map(services[service_name]["environment"])
        assert env["AWS_TOKEN"] == "${AWS_TOKEN:-default-token}"


def test_deploy_pipeline_does_not_require_repo_aws_secrets() -> None:
    steps = _woodpecker_steps()
    deploy_step = steps["deploy-mcp"]

    assert "environment" not in deploy_step
    assert "secrets" not in deploy_step
