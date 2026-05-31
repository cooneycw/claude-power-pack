"""Tests for Docker Hub pull authentication in CI (issue #370).

Concurrent push + PR pipelines pulling base images unauthenticated tripped
Docker Hub's anonymous rate limit (429). These assert the auth wiring stays in
place: every buildx build step logs in via secrets, and runtime-smoke logs in
before compose pulls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]


def _steps() -> dict[str, Any]:
    return yaml.safe_load((REPO / ".woodpecker.yml").read_text())["steps"]


def test_all_buildx_steps_authenticate_docker_hub() -> None:
    steps = _steps()
    build_steps = [
        name
        for name, step in steps.items()
        if str(step.get("image", "")).startswith("woodpeckerci/plugin-docker-buildx")
    ]
    assert build_steps, "expected at least one buildx build step"
    for name in build_steps:
        settings = steps[name]["settings"]
        assert settings["username"] == {"from_secret": "dockerhub_username"}, name
        assert settings["password"] == {"from_secret": "dockerhub_token"}, name


def test_runtime_smoke_logs_in_before_pulling() -> None:
    smoke = _steps()["runtime-smoke"]
    env = smoke["environment"]
    assert env["DOCKERHUB_USERNAME"] == {"from_secret": "dockerhub_username"}
    assert env["DOCKERHUB_TOKEN"] == {"from_secret": "dockerhub_token"}

    commands = smoke["commands"]
    login_idx = next(i for i, c in enumerate(commands) if "ci-docker-login.sh" in c)
    # Login must run before whatever triggers compose pulls - robust to both the
    # inline smoke block and the scripts/runtime-smoke.sh form (#350).
    pull_idx = next(
        i
        for i, c in enumerate(commands)
        if "runtime-smoke.sh" in c or "docker compose" in c or "up --build" in c
    )
    assert login_idx < pull_idx


def test_login_script_uses_password_stdin_and_is_non_fatal() -> None:
    body = (REPO / "scripts" / "ci-docker-login.sh").read_text()
    assert "--password-stdin" in body
    # Never echo the token to argv; never hard-fail when the secret is absent.
    assert "-p " not in body
    assert "DOCKERHUB_TOKEN:-" in body
