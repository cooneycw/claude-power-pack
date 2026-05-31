"""Tests for checked-in Docker Compose deployment config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

WOODPECKER_DOCKER_BUILDX_IMAGE = (
    "codeberg.org/woodpecker-plugins/docker-buildx:6.1.0"
    "@sha256:33263f74a593ddef5d4faeb39ae9f87db14d64d8aae8186284ae6e90d89298a4"
)


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


def _step_commands(step: dict[str, Any]) -> str:
    return "\n".join(step.get("commands", []))


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
    assert services["aws-secrets-agent"]["healthcheck"]["start_period"] == "30s"
    for service_name in ("mcp-second-opinion", "mcp-woodpecker-ci"):
        env = _env_list_to_map(services[service_name]["environment"])
        assert env["AWS_TOKEN"] == "${AWS_TOKEN:-default-token}"


def test_aws_secrets_agent_healthcheck_allows_loaded_starts() -> None:
    root = Path(__file__).resolve().parents[1]
    services = _compose_services()
    agent = services["aws-secrets-agent"]
    healthcheck = agent["healthcheck"]
    dockerfile = (root / "aws-secrets-agent" / "Dockerfile").read_text()
    config = (root / "aws-secrets-agent" / "config.toml").read_text()

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
    assert "validate_credentials = false" in config

    resources = agent["deploy"]["resources"]
    assert resources["limits"] == {"cpus": "0.5", "memory": "128M"}
    assert resources["reservations"] == {"cpus": "0.25", "memory": "64M"}


def test_aws_secrets_agent_entrypoint_fails_loud_on_empty_credentials() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "aws-secrets-agent" / "Dockerfile").read_text()
    entrypoint = (root / "aws-secrets-agent" / "entrypoint.sh").read_text()

    assert "COPY entrypoint.sh ./entrypoint.sh" in dockerfile
    assert 'ENTRYPOINT ["./entrypoint.sh"]' in dockerfile
    assert "AWS_ACCESS_KEY_ID" in entrypoint
    assert "AWS_SECRET_ACCESS_KEY" in entrypoint
    assert "force-recreate aws-secrets-agent" in entrypoint


def test_second_opinion_uses_secret_with_free_tier_provider_keys() -> None:
    services = _compose_services()
    env = _env_list_to_map(services["mcp-second-opinion"]["environment"])

    assert env["AWS_SECRET_NAME"] == "${SECOND_OPINION_AWS_SECRET_NAME-codex_llm_apikeys}"

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


def test_compose_stack_is_project_isolated() -> None:
    compose_path = Path(__file__).resolve().parents[1] / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text())
    services = compose["services"]

    # Container names default to the stable service name (empty prefix) so
    # workstation deploys and cpp:update model detection can address them, while
    # CI smoke runs set CPP_CONTAINER_PREFIX to keep parallel projects isolated.
    for name, service in services.items():
        assert service.get("container_name") == "${CPP_CONTAINER_PREFIX:-}" + name
    assert "networks" not in compose
    assert "volumes" not in services["mcp-second-opinion"]
    assert "volumes" not in services["mcp-woodpecker-ci"]


def test_secret_bootstrap_script_is_baked_into_secret_consuming_images() -> None:
    root = Path(__file__).resolve().parents[1]
    canonical = (root / "aws-secrets-agent" / "fetch-secrets.sh").read_text()

    # Fail-closed posture (issue #347): a required-secret fetch failure must
    # exit non-zero rather than exec a keyless server, and the env_file fallback
    # must be gated behind an explicit opt-in.
    assert "ALLOW_ENV_FALLBACK" in canonical
    assert "refusing to start without required secret" in canonical
    assert "exit 1" in canonical

    for service in ("mcp-second-opinion", "mcp-woodpecker-ci"):
        dockerfile = (root / service / "deploy" / "Dockerfile").read_text()
        fetch_script = (root / service / "deploy" / "fetch-secrets.sh").read_text()

        assert fetch_script == canonical
        assert "deploy/fetch-secrets.sh ./fetch-secrets.sh" in dockerfile
        assert "chmod 755 /app/fetch-secrets.sh" in dockerfile


def test_compose_uses_fixed_local_ports_with_ci_overrides() -> None:
    services = _compose_services()

    assert services["aws-secrets-agent"]["ports"] == [
        "${AWS_SECRETS_AGENT_PORT_MAPPING:-2773:2773}"
    ]
    assert services["mcp-second-opinion"]["ports"] == [
        "${MCP_SECOND_OPINION_PORT_MAPPING:-8080:8080}"
    ]
    assert services["mcp-playwright-persistent"]["ports"] == [
        "${MCP_PLAYWRIGHT_PORT_MAPPING:-8081:8081}"
    ]
    assert services["mcp-nano-banana"]["ports"] == [
        "${MCP_NANO_BANANA_PORT_MAPPING:-8084:8084}"
    ]
    assert services["mcp-woodpecker-ci"]["ports"] == [
        "${MCP_WOODPECKER_CI_PORT_MAPPING:-8085:8085}"
    ]


def test_makefile_has_first_class_docker_refresh_target() -> None:
    root = Path(__file__).resolve().parents[1]
    makefile = (root / "Makefile").read_text()

    assert "docker-refresh:" in makefile
    assert 'DOCKER_UP_FLAGS="-d --build --wait"' in makefile
    assert "docker-health:" in makefile
    assert "scripts/docker-health-check.py" in makefile
    assert "scripts/check-docker-aws-env.py" in makefile


def test_cpp_status_surfaces_stale_sidecar_env_bake() -> None:
    root = Path(__file__).resolve().parents[1]
    command = (root / ".claude" / "commands" / "cpp" / "status.md").read_text()

    assert "Detected sidecar dependency strand" in command
    assert "Created with no logs" in command
    assert "--force-recreate aws-secrets-agent" in command


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


def test_woodpecker_has_no_persistent_deploy_or_prune() -> None:
    steps = _woodpecker_steps()
    pipeline_text = (Path(__file__).resolve().parents[1] / ".woodpecker.yml").read_text()

    assert "deploy-mcp" not in steps
    assert "pre-deploy-guardrails" not in steps
    assert "drift-check" not in steps
    assert "docker image prune" not in pipeline_text


def test_woodpecker_uses_image_security_instead_of_parallel_dry_run_builds() -> None:
    steps = _woodpecker_steps()

    for step_name in (
        "build-aws-secrets-agent",
        "build-second-opinion",
        "build-playwright",
        "build-nano-banana",
        "build-woodpecker-ci",
    ):
        assert step_name not in steps


def test_woodpecker_lints_every_dockerfile_with_hadolint() -> None:
    steps = _woodpecker_steps()
    lint = steps["dockerfile-lint"]
    commands = _step_commands(lint)

    assert lint["depends_on"] == ["validate"]
    assert lint["image"] == "ghcr.io/hadolint/hadolint:v2.14.0-debian"
    assert lint["pull"] is True
    assert "find . -path ./.git -prune -o -name Dockerfile -print0" in commands
    assert "xargs -0 hadolint --failure-threshold error" in commands


def test_woodpecker_validates_compose_config_and_policy() -> None:
    steps = _woodpecker_steps()
    policy = steps["compose-policy"]
    commands = _step_commands(policy)

    assert policy["depends_on"] == ["validate"]
    assert policy["image"] == WOODPECKER_DOCKER_BUILDX_IMAGE
    assert "apk add --no-cache docker-cli-compose" in commands
    assert "docker compose --profile core --profile browser --profile cicd config --quiet" in commands
    assert "docker compose --profile core --profile browser --profile cicd config > \"$rendered\"" in commands
    assert "AWS_TOKEN=ci-policy-token" in commands
    assert "AWS_SECRETS_AGENT_PORT_MAPPING=2773" in commands
    assert "image: [^[:space:]]+:latest" in commands
    assert "default-token" in commands
    assert "published: \"?2773\"?" in commands


def test_woodpecker_builds_scans_images_and_generates_sboms() -> None:
    steps = _woodpecker_steps()
    security = steps["image-security"]
    commands = _step_commands(security)

    assert security["depends_on"] == ["dockerfile-lint", "compose-policy"]
    assert security["image"] == WOODPECKER_DOCKER_BUILDX_IMAGE
    assert "/var/run/docker.sock:/var/run/docker.sock" in security["volumes"]
    assert "apk add --no-cache docker-cli-compose" in commands
    assert "CPP_IMAGE_TAG=\"ci-${CI_COMMIT_SHA:-local}\"" in commands
    assert "docker compose --profile core --profile browser --profile cicd build" in commands
    assert "docker pull ghcr.io/aquasecurity/trivy:0.67.2" in commands
    assert "docker pull ghcr.io/anchore/syft:v1.44.0" in commands
    assert "aws-secrets-agent:$CPP_IMAGE_TAG" in commands
    assert "slug=\"$(printf '%s' \"$image\" | cut -d: -f1)\"" in commands
    assert "ghcr.io/aquasecurity/trivy:0.67.2 image" in commands
    assert "--scanners vuln" in commands
    assert "--exit-code 1" in commands
    assert "--severity HIGH,CRITICAL" in commands
    assert "--ignore-unfixed" in commands
    assert "ghcr.io/anchore/syft:v1.44.0" in commands
    assert "-o spdx-json" in commands
    assert "-o cyclonedx-json" in commands
    assert "artifacts/sbom/$slug.spdx.json" in commands
    assert "artifacts/sbom/$slug.cyclonedx.json" in commands

    image_paths = set(security["when"][0]["path"])
    assert ".woodpecker.yml" in image_paths
    assert "docker-compose.yml" in image_paths
    assert "aws-secrets-agent/**" in image_paths
    assert "lib/**" in image_paths
    assert "mcp-second-opinion/**" in image_paths
    assert "mcp-playwright-persistent/**" in image_paths
    assert "mcp-nano-banana/**" in image_paths
    assert "mcp-woodpecker-ci/**" in image_paths


def test_python_runtime_images_remove_system_packaging_tools() -> None:
    root = Path(__file__).resolve().parents[1]
    dockerfiles = [
        "mcp-second-opinion/deploy/Dockerfile",
        "mcp-playwright-persistent/deploy/Dockerfile",
        "mcp-nano-banana/deploy/Dockerfile",
        "mcp-woodpecker-ci/deploy/Dockerfile",
        "mcp-evaluate/deploy/Dockerfile",
    ]

    for dockerfile in dockerfiles:
        body = (root / dockerfile).read_text()
        assert "/usr/local/bin/python -m pip uninstall -y pip setuptools wheel" in body


def test_woodpecker_runtime_smoke_is_ephemeral_and_tears_down() -> None:
    steps = _woodpecker_steps()
    smoke = steps["runtime-smoke"]
    commands = _step_commands(smoke)

    assert smoke["depends_on"] == ["image-security"]
    assert smoke["image"] == WOODPECKER_DOCKER_BUILDX_IMAGE
    assert "/var/run/docker.sock:/var/run/docker.sock" in smoke["volumes"]
    assert "apk add --no-cache curl docker-cli-compose" in commands
    assert 'PROJECT="cpp-smoke-${CI_PIPELINE_NUMBER:-local}"' in commands
    assert "trap cleanup EXIT INT TERM" in commands
    assert (
        'if ! docker compose -p "$PROJECT" --profile core --profile browser '
        "--profile cicd up --build --wait; then"
    ) in commands
    assert 'docker compose -p "$PROJECT" --profile core --profile browser --profile cicd down -v || true' in commands
    assert 'docker compose -p "$PROJECT" logs aws-secrets-agent || true' in commands

    assert "export AWS_ACCESS_KEY_ID=cpp-smoke-access-key" in commands
    assert "export AWS_SECRET_ACCESS_KEY=cpp-smoke-secret-key" in commands
    assert "export AWS_SESSION_TOKEN=cpp-smoke-session-token" in commands
    assert "export AWS_TOKEN=cpp-smoke-token" in commands
    assert 'export CPP_CONTAINER_PREFIX="cpp-smoke-${CI_PIPELINE_NUMBER:-local}-"' in commands
    assert "export SECOND_OPINION_AWS_SECRET_NAME=" in commands
    assert "export WOODPECKER_CI_AWS_SECRET_NAME=" in commands
    assert "export AWS_SECRETS_AGENT_PORT_MAPPING=2773" in commands
    assert "export MCP_SECOND_OPINION_PORT_MAPPING=8080" in commands
    assert "export MCP_PLAYWRIGHT_PORT_MAPPING=8081" in commands
    assert "export MCP_NANO_BANANA_PORT_MAPPING=8084" in commands
    assert "docker compose -p \"$PROJECT\" port \"$service\" \"$container_port\"" in commands
    assert "url=\"http://127.0.0.1:$container_port$check_path\"" in commands
    assert 'docker compose -p "$PROJECT" exec -T "$service"' in commands
    assert "urllib.request.urlopen('$url', timeout=10)" in commands
    assert "X-Aws-Parameters-Secrets-Token: $AWS_TOKEN" in commands

    assert "check_http aws-secrets-agent 2773 /ping" in commands
    assert "check_http mcp-second-opinion 8080 /readyz" in commands
    assert "check_http mcp-playwright-persistent 8081 /readyz" in commands
    assert "check_http mcp-nano-banana 8084 /readyz" in commands
    assert "check_http mcp-woodpecker-ci 8085 /readyz" in commands

    # Keyless servers must be made ready before the readiness `--wait` gate;
    # the smoke runs with fake AWS creds (keyless fallback), so it injects dummy
    # keys through the compose env passthrough purely to satisfy /readyz.
    assert "export GEMINI_API_KEY=cpp-smoke-gemini-key" in commands
    assert "export WOODPECKER_URL=http://woodpecker.invalid" in commands
    assert "export WOODPECKER_API_TOKEN=cpp-smoke-woodpecker-token" in commands


def test_mcp_healthchecks_gate_on_readiness_not_liveness() -> None:
    services = _compose_services()

    # The compose healthcheck is the `docker compose up --wait` release gate.
    # Each MCP server must be probed on /readyz so a live-but-unready (e.g.
    # keyless) container is reported unhealthy instead of being greenlit.
    expected = {
        "mcp-second-opinion": "8080",
        "mcp-nano-banana": "8084",
        "mcp-woodpecker-ci": "8085",
        "mcp-playwright-persistent": "8081",
    }
    for service, port in expected.items():
        probe = " ".join(services[service]["healthcheck"]["test"])
        assert f"http://127.0.0.1:{port}/readyz" in probe, service
        assert f"http://127.0.0.1:{port}/'" not in probe, service


def test_secret_consuming_services_accept_injected_keys() -> None:
    services = _compose_services()

    # CI/deploy without a live secrets-agent inject keys via these passthrough
    # entries so /readyz can report ready. Shorthand (no `=`) means the var is
    # only set when present on the host; the agent overrides at runtime.
    so_env = services["mcp-second-opinion"]["environment"]
    for key in (
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
    ):
        assert key in so_env

    wp_env = services["mcp-woodpecker-ci"]["environment"]
    assert "WOODPECKER_URL" in wp_env
    assert "WOODPECKER_API_TOKEN" in wp_env


def test_each_mcp_server_exposes_a_readiness_route() -> None:
    root = Path(__file__).resolve().parents[1]
    servers = {
        "mcp-second-opinion": "src/server.py",
        "mcp-nano-banana": "src/server.py",
        "mcp-woodpecker-ci": "src/server.py",
        "mcp-playwright-persistent": "src/server.py",
    }
    for component, rel in servers.items():
        source = (root / component / rel).read_text()
        assert '@mcp.custom_route("/readyz", methods=["GET"])' in source, component


def test_woodpecker_smoke_path_gates_cover_shared_runtime_inputs() -> None:
    steps = _woodpecker_steps()
    smoke_paths = set(steps["runtime-smoke"]["when"][0]["path"])

    assert ".woodpecker.yml" in smoke_paths
    assert "docker-compose.yml" in smoke_paths
    assert "aws-secrets-agent/**" in smoke_paths
    assert "lib/**" in smoke_paths
    assert "mcp-second-opinion/**" in smoke_paths
    assert "mcp-playwright-persistent/**" in smoke_paths
    assert "mcp-nano-banana/**" in smoke_paths
    assert "mcp-woodpecker-ci/**" in smoke_paths
