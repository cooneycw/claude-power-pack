"""Tests for the CI secret-fetch smoke harness (issue #350).

Two layers:
  * Structural assertions that the smoke override, the runtime-smoke script, and
    the Woodpecker step actually wire up the real fetch path and the
    cross-container reachability check (parses YAML/text, no Docker needed).
  * A live integration test that runs the REAL fetch-secrets.sh against an
    in-process instance of scripts/fake-secrets-agent.py, proving the
    fetch -> JSON parse -> shell export path end to end without Docker or AWS.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
FAKE_AGENT = REPO / "scripts" / "fake-secrets-agent.py"
SMOKE_COMPOSE = REPO / "docker-compose.smoke.yml"
SMOKE_SCRIPT = REPO / "scripts" / "runtime-smoke.sh"
FETCH_SECRETS = REPO / "mcp-second-opinion" / "deploy" / "fetch-secrets.sh"


def _env_list_to_map(values: list[str]) -> dict[str, str | None]:
    env: dict[str, str | None] = {}
    for value in values:
        if "=" in value:
            key, raw = value.split("=", 1)
            env[key] = raw
        else:
            env[value] = None
    return env


# --------------------------------------------------------------------------- #
# Structural assertions                                                        #
# --------------------------------------------------------------------------- #


def test_smoke_compose_defines_fake_agent_and_fetch_probe() -> None:
    services = yaml.safe_load(SMOKE_COMPOSE.read_text())["services"]
    assert "fake-secrets-agent" in services
    assert "fetch-probe" in services
    # Both stay behind the "smoke" profile so normal docker-up is unaffected.
    assert services["fake-secrets-agent"]["profiles"] == ["smoke"]
    assert services["fetch-probe"]["profiles"] == ["smoke"]


def test_fake_agent_is_built_not_bind_mounted() -> None:
    # Under Woodpecker's docker-in-docker the smoke step uses the host daemon, so
    # a relative host bind-mount path is not present; the script must be baked in
    # via a build context instead. Guards against reintroducing the volume mount.
    fake = yaml.safe_load(SMOKE_COMPOSE.read_text())["services"]["fake-secrets-agent"]
    assert "build" in fake, "fake-secrets-agent must build (not bind-mount) the script"
    assert "volumes" not in fake
    assert "fake-secrets-agent.py" in fake["build"]["dockerfile_inline"]


def test_fetch_probe_uses_real_image_and_real_fetch_path() -> None:
    probe = yaml.safe_load(SMOKE_COMPOSE.read_text())["services"]["fetch-probe"]
    # Exercises the image the stack builds, via the real entrypoint. Issue #348
    # dropped :latest for deployables, so this tracks the CPP_IMAGE_TAG default.
    assert probe["image"] == "mcp-second-opinion:${CPP_IMAGE_TAG:-dev}"
    assert probe["entrypoint"] == ["/app/fetch-secrets.sh"]

    env = _env_list_to_map(probe["environment"])
    # NON-EMPTY secret name is the whole point: it forces the production fetch
    # branch instead of the local-dev fallback that the old smoke exercised.
    assert env.get("AWS_SECRET_NAME"), "fetch-probe must set a non-empty AWS_SECRET_NAME"
    assert env["SECRETS_AGENT_URL"] == "http://fake-secrets-agent:2773"


def test_runtime_smoke_script_checks_cross_container_and_fetch_path() -> None:
    body = SMOKE_SCRIPT.read_text()
    # Cross-container reachability against the real agent by network name.
    assert "http://aws-secrets-agent:2773/ping" in body
    # Real fetch path verified via the fake agent + sentinel.
    assert "fetch-probe" in body
    assert "FETCHED:loaded-via-agent" in body


# --------------------------------------------------------------------------- #
# Structural assertions for the REAL-agent fetch path (issue #377)             #
# --------------------------------------------------------------------------- #


def test_smoke_compose_defines_real_agent_path() -> None:
    services = yaml.safe_load(SMOKE_COMPOSE.read_text())["services"]
    for name in ("localstack", "real-secrets-agent", "real-fetch-probe"):
        assert name in services, f"smoke override must define {name}"
        # All stay behind the "smoke" profile so normal docker-up is unaffected.
        assert services[name]["profiles"] == ["smoke"]


def test_localstack_is_pinned_and_secretsmanager_only() -> None:
    localstack = yaml.safe_load(SMOKE_COMPOSE.read_text())["services"]["localstack"]
    image = localstack["image"]
    # Reproducible-builds directive: pin by digest, never :latest.
    assert "@sha256:" in image, "localstack image must be digest-pinned"
    assert ":latest" not in image
    env = _env_list_to_map(localstack["environment"])
    assert env.get("SERVICES") == "secretsmanager"
    # Internal-only: LocalStack must not publish a host port in CI.
    assert "ports" not in localstack


def test_real_secrets_agent_is_real_binary_pointed_at_localstack() -> None:
    agent = yaml.safe_load(SMOKE_COMPOSE.read_text())["services"]["real-secrets-agent"]
    # The SAME image as the deployed sidecar - this exercises the real binary.
    assert agent["image"] == "aws-secrets-agent:${CPP_IMAGE_TAG:-dev}"
    # Internal-only, like the deployed sidecar: never host-published.
    assert "ports" not in agent
    assert agent["expose"] == ["2773"]

    env = _env_list_to_map(agent["environment"])
    # Redirect the AWS SDK at LocalStack so it performs a real GetSecretValue.
    assert env["AWS_ENDPOINT_URL"] == "http://localstack:4566"


def test_real_fetch_probe_fetches_through_real_agent() -> None:
    probe = yaml.safe_load(SMOKE_COMPOSE.read_text())["services"]["real-fetch-probe"]
    assert probe["image"] == "mcp-second-opinion:${CPP_IMAGE_TAG:-dev}"
    assert probe["entrypoint"] == ["/app/fetch-secrets.sh"]

    env = _env_list_to_map(probe["environment"])
    assert env.get("AWS_SECRET_NAME"), "real-fetch-probe must set a non-empty AWS_SECRET_NAME"
    # Fetches THROUGH the real agent, not the fake one.
    assert env["SECRETS_AGENT_URL"] == "http://real-secrets-agent:2773"


def test_runtime_smoke_script_drives_secret_through_real_agent() -> None:
    body = SMOKE_SCRIPT.read_text()
    # Seeds a real secret into LocalStack and drives it through the real agent.
    assert "awslocal secretsmanager create-secret" in body
    assert "real-secrets-agent" in body
    assert "real-fetch-probe" in body
    # Distinct sentinel from the fake path so the assertion can't pass on the fake.
    assert "FETCHED:${REAL_SENTINEL}" in body or "loaded-via-real-agent" in body


def test_woodpecker_runtime_smoke_delegates_to_script() -> None:
    pipeline = yaml.safe_load((REPO / ".woodpecker.yml").read_text())
    step = pipeline["steps"]["runtime-smoke"]
    commands = "\n".join(step["commands"])
    assert "sh scripts/runtime-smoke.sh" in commands

    paths = step["when"][0]["path"]
    for required in (
        "docker-compose.smoke.yml",
        "scripts/runtime-smoke.sh",
        "scripts/fake-secrets-agent.py",
    ):
        assert required in paths, f"runtime-smoke should trigger on {required}"


# --------------------------------------------------------------------------- #
# Live integration: real fetch-secrets.sh against the in-process fake agent    #
# --------------------------------------------------------------------------- #


def _load_fake_agent() -> Any:
    spec = importlib.util.spec_from_file_location("fake_secrets_agent", FAKE_AGENT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def fake_agent() -> Iterator[tuple[str, str, str]]:
    """Run the fake agent on an ephemeral port; yield (base_url, token, secret_id)."""
    module = _load_fake_agent()
    token = "cpp-smoke-token"
    secret_id = "cpp/smoke/fake"
    prev = {k: os.environ.get(k) for k in ("AWS_TOKEN", "FAKE_SECRET_ID")}
    os.environ["AWS_TOKEN"] = token
    os.environ["FAKE_SECRET_ID"] = secret_id

    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", token, secret_id
    finally:
        server.shutdown()
        server.server_close()
        for key, value in prev.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _get(url: str, token: str | None) -> tuple[int, bytes]:
    headers = {}
    if token is not None:
        headers["X-Aws-Parameters-Secrets-Token"] = token
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status, resp.read()
    except urllib.error.HTTPError as exc:  # noqa: PERF203
        return exc.code, exc.read()


def test_fake_agent_contract(fake_agent: tuple[str, str, str]) -> None:
    base, token, secret_id = fake_agent

    status, _ = _get(f"{base}/ping", token)
    assert status == 200

    # Wrong token is rejected (the real agent enforces the SSRF token).
    status, _ = _get(f"{base}/ping", "wrong-token")
    assert status == 403

    status, body = _get(f"{base}/secretsmanager/get?secretId={secret_id}", token)
    assert status == 200
    payload = json.loads(body)
    secrets = json.loads(payload["SecretString"])
    assert secrets["CPP_SMOKE_SENTINEL"] == "loaded-via-agent"

    status, _ = _get(f"{base}/secretsmanager/get?secretId=does-not-exist", token)
    assert status == 404


@pytest.mark.skipif(
    not shutil.which("sh") or not shutil.which("python3"),
    reason="needs sh + python3 to run fetch-secrets.sh",
)
def test_real_fetch_secrets_exports_secret(fake_agent: tuple[str, str, str]) -> None:
    """The real fetch-secrets.sh fetches, parses, and exports the fake secret."""
    base, token, secret_id = fake_agent
    env = {
        **os.environ,
        "AWS_SECRET_NAME": secret_id,
        "SECRETS_AGENT_URL": base,
        "AWS_TOKEN": token,
    }
    result = subprocess.run(
        ["sh", str(FETCH_SECRETS), "sh", "-c", "echo FETCHED:$CPP_SMOKE_SENTINEL"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "FETCHED:loaded-via-agent" in result.stdout, result.stdout + result.stderr
