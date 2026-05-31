"""Tests for the fail-closed fetch-secrets.sh entrypoint (issue #347).

These run the real shell script as a subprocess against a mock secrets agent so
the security-critical control flow (fail closed vs. opt-in fallback) is exercised
end to end, not just asserted on file contents. Failure modes are driven through
the mock (HTTP error / unreachable) rather than a dead TCP port so the retry loop
never blocks the test on connect timeouts.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import threading
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "aws-secrets-agent" / "fetch-secrets.sh"

# Variables the entrypoint reads - scrubbed from the inherited environment so an
# ambient value cannot mask a failure, and forced to fast values for retries.
_CONTROL_VARS = {
    "AWS_SECRET_NAME",
    "SECRETS_AGENT_URL",
    "AWS_TOKEN",
    "ALLOW_ENV_FALLBACK",
    "REQUIRED_SECRET_KEYS",
    "SECRETS_FETCH_MAX_RETRIES",
    "SECRETS_FETCH_RETRY_INTERVAL",
}


def _run(env_extra: dict[str, str], args: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in _CONTROL_VARS}
    env["SECRETS_FETCH_MAX_RETRIES"] = "2"
    env["SECRETS_FETCH_RETRY_INTERVAL"] = "0"
    env.update(env_extra)
    return subprocess.run(
        ["sh", str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class _BaseHandler(http.server.BaseHTTPRequestHandler):
    secret_payload: dict[str, str] | None = None
    status_code: int = 200

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        cls = type(self)
        if cls.status_code != 200:
            self.send_response(cls.status_code)
            self.end_headers()
            return
        body = json.dumps({"SecretString": json.dumps(cls.secret_payload or {})}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # silence test noise
        pass


def _serve(
    payload: dict[str, str] | None = None, status_code: int = 200
) -> tuple[http.server.HTTPServer, str]:
    handler = type(
        "_Handler",
        (_BaseHandler,),
        {"secret_payload": payload, "status_code": status_code},
    )
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    return server, url


def _free_port_url() -> str:
    """A loopback URL whose port has no listener (connection refused, fast)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return f"http://127.0.0.1:{port}"


def test_local_dev_mode_without_secret_name_execs() -> None:
    result = _run({"AWS_SECRET_NAME": ""}, ["echo", "STARTED"])
    assert result.returncode == 0
    assert "STARTED" in result.stdout


def test_fails_closed_when_required_secret_unreachable() -> None:
    result = _run(
        {"AWS_SECRET_NAME": "demo_secret", "SECRETS_AGENT_URL": _free_port_url()},
        ["echo", "SHOULD_NOT_START"],
    )
    assert result.returncode != 0
    assert "SHOULD_NOT_START" not in result.stdout
    assert "FATAL" in result.stderr


def test_dev_fallback_opt_in_starts_anyway() -> None:
    result = _run(
        {
            "AWS_SECRET_NAME": "demo_secret",
            "SECRETS_AGENT_URL": _free_port_url(),
            "ALLOW_ENV_FALLBACK": "true",
        },
        ["echo", "STARTED_ANYWAY"],
    )
    assert result.returncode == 0
    assert "STARTED_ANYWAY" in result.stdout


def test_http_error_fails_fast() -> None:
    server, url = _serve(status_code=404)
    try:
        result = _run(
            {"AWS_SECRET_NAME": "demo_secret", "SECRETS_AGENT_URL": url},
            ["echo", "SHOULD_NOT_START"],
        )
    finally:
        server.shutdown()
    assert result.returncode != 0
    assert "SHOULD_NOT_START" not in result.stdout
    assert "FATAL" in result.stderr


def test_success_exports_secret_values() -> None:
    server, url = _serve(payload={"DEMO_TOKEN_VALUE": "abc123"})
    try:
        result = _run(
            {"AWS_SECRET_NAME": "demo_secret", "SECRETS_AGENT_URL": url},
            ["sh", "-c", "echo VALUE=$DEMO_TOKEN_VALUE"],
        )
    finally:
        server.shutdown()
    assert result.returncode == 0
    assert "VALUE=abc123" in result.stdout
    assert "Loaded secrets from AWS Secrets Manager" in result.stdout


def test_required_keys_enforced_when_missing() -> None:
    server, url = _serve(payload={"DEMO_TOKEN_VALUE": "abc123"})
    try:
        result = _run(
            {
                "AWS_SECRET_NAME": "demo_secret",
                "SECRETS_AGENT_URL": url,
                "REQUIRED_SECRET_KEYS": "DEMO_TOKEN_VALUE ABSENT_VALUE",
            },
            ["echo", "SHOULD_NOT_START"],
        )
    finally:
        server.shutdown()
    assert result.returncode != 0
    assert "SHOULD_NOT_START" not in result.stdout
    assert "ABSENT_VALUE" in result.stderr
