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


def test_aws_secrets_agent_healthcheck_allows_loaded_starts() -> None:
    root = Path(__file__).resolve().parents[1]
    services = _compose_services()
    agent = services["aws-secrets-agent"]
    healthcheck = agent["healthcheck"]
    dockerfile = (root / "aws-secrets-agent" / "Dockerfile").read_text()

    assert healthcheck["test"][-1] == "http://localhost:2773/ping"
    assert healthcheck["interval"] == "10s"
    assert healthcheck["timeout"] == "5s"
    assert healthcheck["start_period"] == "30s"
    assert healthcheck["retries"] == 5

    assert "--interval=10s" in dockerfile
    assert "--timeout=5s" in dockerfile
    assert "--start-period=30s" in dockerfile
    assert "--retries=5" in dockerfile
    assert "does not call AWS" in dockerfile

    resources = agent["deploy"]["resources"]
    assert resources["limits"] == {"cpus": "0.5", "memory": "128M"}
    assert resources["reservations"] == {"cpus": "0.25", "memory": "64M"}


def test_second_opinion_uses_secret_with_free_tier_provider_keys() -> None:
    services = _compose_services()
    env = _env_list_to_map(services["mcp-second-opinion"]["environment"])

    assert env["AWS_SECRET_NAME"] == "codex_llm_apikeys"

    expected_keys = [
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
    ]
    docs = (
        Path(__file__).resolve().parents[1] / "docs" / "AWS_SECRETS_SIDECAR.md"
    ).read_text()
    for key in expected_keys:
        assert key in docs


def test_legacy_second_opinion_secret_name_is_not_documented() -> None:
    root = Path(__file__).resolve().parents[1]
    checked_paths = [
        root / "docker-compose.yml",
        root / "CLAUDE.md",
        root / "README.md",
        root / "docs" / "AWS_SECRETS_SIDECAR.md",
        root / ".claude" / "commands" / "cpp" / "init.md",
        root / ".claude" / "commands" / "cpp" / "status.md",
    ]

    for path in checked_paths:
        assert "claude-power-pack/mcp-keys" not in path.read_text()


def test_deploy_pipeline_does_not_require_repo_aws_secrets() -> None:
    steps = _woodpecker_steps()
    deploy_step = steps["deploy-mcp"]

    assert "environment" not in deploy_step
    assert "secrets" not in deploy_step


def test_makefile_has_first_class_docker_refresh_target() -> None:
    root = Path(__file__).resolve().parents[1]
    makefile = (root / "Makefile").read_text()

    assert "docker-refresh:" in makefile
    assert 'DOCKER_UP_FLAGS="-d --build --wait"' in makefile
    assert "docker-health:" in makefile
    assert "scripts/docker-health-check.py" in makefile


def test_cpp_update_refreshes_detected_docker_runtime() -> None:
    root = Path(__file__).resolve().parents[1]
    command = (root / ".claude" / "commands" / "cpp" / "update.md").read_text()

    assert 'DEPLOY_MODEL="docker"' in command
    assert 'DEPLOY_MODEL="systemd"' in command
    assert 'make docker-refresh PROFILE="core browser cicd"' in command
    assert "Docker refresh failed" in command
    assert "Do not run Docker and\nsystemd restarts in the same update" in command


def test_cpp_init_prefers_docker_and_runs_health_gated_refresh() -> None:
    root = Path(__file__).resolve().parents[1]
    command = (root / ".claude" / "commands" / "cpp" / "init.md").read_text()

    assert "# Fresh installs prefer Docker when available." in command
    assert 'DEPLOY_MODE="systemd"' in command
    assert 'make docker-refresh PROFILE="core browser cicd"' in command
    assert "Docker containers rebuilt, restarted, and healthy" in command
    assert "skipping systemd service setup" in command
