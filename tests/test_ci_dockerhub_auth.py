"""Tests for Docker Hub pull authentication in CI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]


def _steps() -> dict[str, Any]:
    return yaml.safe_load((REPO / ".woodpecker.yml").read_text())["steps"]


def _commands(step: dict[str, Any]) -> list[str]:
    return step.get("commands", [])


def _command_index(commands: list[str], needle: str) -> int:
    return next(i for i, command in enumerate(commands) if needle in command)


def test_image_security_logs_in_before_compose_build() -> None:
    security = _steps()["image-security"]
    env = security["environment"]
    assert env["DOCKERHUB_USERNAME"] == {"from_secret": "dockerhub_username"}
    assert env["DOCKERHUB_TOKEN"] == {"from_secret": "dockerhub_token"}

    commands = _commands(security)
    login_idx = _command_index(commands, "ci-docker-login.sh")
    build_idx = _command_index(
        commands, "docker compose --profile core --profile browser --profile cicd build"
    )
    assert login_idx < build_idx
    assert "scripts/ci-docker-login.sh" in security["when"][0]["path"]


def test_runtime_smoke_logs_in_before_compose_up_build() -> None:
    smoke = _steps()["runtime-smoke"]
    env = smoke["environment"]
    assert env["DOCKERHUB_USERNAME"] == {"from_secret": "dockerhub_username"}
    assert env["DOCKERHUB_TOKEN"] == {"from_secret": "dockerhub_token"}

    commands = _commands(smoke)
    login_idx = _command_index(commands, "ci-docker-login.sh")
    up_idx = _command_index(commands, "up --build --wait")
    assert login_idx < up_idx
    assert "scripts/ci-docker-login.sh" in smoke["when"][0]["path"]


def test_login_script_uses_password_stdin_and_is_non_fatal() -> None:
    body = (REPO / "scripts" / "ci-docker-login.sh").read_text()
    assert "--password-stdin" in body
    assert "-p " not in body
    assert "DOCKERHUB_TOKEN:-" in body
    assert "pulling unauthenticated" in body
