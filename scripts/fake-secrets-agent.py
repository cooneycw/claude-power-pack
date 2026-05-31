#!/usr/bin/env python3
"""Hermetic stand-in for the AWS Secrets Manager Agent, for CI smoke tests.

The real `aws-secrets-agent` proxies to AWS Secrets Manager and therefore needs
valid AWS credentials to return a secret. CI has none, so the production
fetch/parse/export path in `fetch-secrets.sh` is never exercised (it falls
through to the local-dev branch). This stub mimics the slice of the agent
contract that `fetch-secrets.sh` depends on, so CI can prove that path
end-to-end without any AWS access. See issue #350.

Endpoints (matching the AWS agent):
  GET /ping
      Liveness. Requires the SSRF token header, like the real agent.
  GET /secretsmanager/get?secretId=<id>
      Returns {"Name": <id>, "SecretString": "<json>"} when the SSRF token
      header matches and <id> equals FAKE_SECRET_ID. 403 on bad token,
      404 on unknown secret id.

Configuration via environment:
  AWS_TOKEN        SSRF token clients must present (default "default-token").
  FAKE_SECRET_ID   secret id this stub will serve (default "cpp/smoke/fake").
  FAKE_AGENT_PORT  listen port (default 2773, the real agent's port).
  FAKE_AGENT_HOST  listen host (default 0.0.0.0, to be reachable cross-container).

The served secret intentionally includes a sentinel key (CPP_SMOKE_SENTINEL)
so callers can assert the value survived fetch -> JSON parse -> shell export.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TOKEN_HEADER = "X-Aws-Parameters-Secrets-Token"
SENTINEL_KEY = "CPP_SMOKE_SENTINEL"
SENTINEL_VALUE = "loaded-via-agent"


def expected_token() -> str:
    return os.environ.get("AWS_TOKEN", "default-token")


def secret_id() -> str:
    return os.environ.get("FAKE_SECRET_ID", "cpp/smoke/fake")


def secret_payload() -> dict[str, str]:
    """The canned secret. Multiple keys exercise multi-key parse/export."""
    return {
        SENTINEL_KEY: SENTINEL_VALUE,
        "OPENAI_API_KEY": "sk-cpp-smoke-fake",
        "ANTHROPIC_API_KEY": "sk-ant-cpp-smoke-fake",
    }


class Handler(BaseHTTPRequestHandler):
    # Quieter logs; CI captures stderr if something goes wrong.
    def log_message(self, *_args: object) -> None:  # noqa: D401
        return

    def _send_json(self, status: int, body: dict[str, object]) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _token_ok(self) -> bool:
        return self.headers.get(TOKEN_HEADER) == expected_token()

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse(self.path)

        if parsed.path == "/ping":
            if not self._token_ok():
                self._send_json(403, {"message": "invalid SSRF token"})
                return
            self._send_json(200, {"status": "ok"})
            return

        if parsed.path == "/secretsmanager/get":
            if not self._token_ok():
                self._send_json(403, {"message": "invalid SSRF token"})
                return
            requested = parse_qs(parsed.query).get("secretId", [""])[0]
            if requested != secret_id():
                self._send_json(404, {"message": f"unknown secret: {requested}"})
                return
            self._send_json(
                200,
                {"Name": requested, "SecretString": json.dumps(secret_payload())},
            )
            return

        self._send_json(404, {"message": "not found"})


def main() -> None:
    host = os.environ.get("FAKE_AGENT_HOST", "0.0.0.0")
    port = int(os.environ.get("FAKE_AGENT_PORT", "2773"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"fake-secrets-agent listening on {host}:{port} for secret {secret_id()!r}")
    server.serve_forever()


if __name__ == "__main__":
    main()
