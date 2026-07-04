"""Backend + DSN resolution for the CPP common-memory store.

Two things resolve here, both fail-open:

**Which backend** (:func:`resolve_backend`) - the ``/cpp:init`` mini-tier choice
``md | local-pg | remote-pg`` (issue #472). Order: ``CPP_MEMORIES_BACKEND`` env ->
local backend file -> None (caller infers from whether a DSN resolves).

**Which DSN** (:func:`resolve_dsn`, pg tiers only), order (first hit wins):
  1. ``CPP_MEMORIES_DSN`` env var           - explicit override / CI injection
  2. local dotenv-global file               - per-machine, works offline
  3. AWS SM ``essent-ai`` key ``CPP_MEMORIES_DSN`` - fleet-wide federation

The AWS tier is the mechanism that lets every VM resolve the same *remote-pg*
store. The DSN host should be the store's Tailscale address so Tailscale-only
hosts reach it too. Tier-i (md) needs no DSN; tier-ii (local-pg) defaults to the
docker store shipped in ``lib/cpp_memory/docker-compose.yml``.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .backend import BACKENDS

LOCAL_DSN_FILE = (
    Path.home() / ".config" / "claude-power-pack" / "secrets" / "cpp-memories.dsn"
)
LOCAL_BACKEND_FILE = (
    Path.home() / ".config" / "claude-power-pack" / "secrets" / "cpp-memories.backend"
)
# Tier-ii default: the docker postgres:17 in lib/cpp_memory/docker-compose.yml
# (host port 5433, credentials cpp_memory/cpp_memory). Overridable via env/arg.
DEFAULT_LOCAL_PG_DSN = os.environ.get(
    "CPP_MEMORIES_LOCAL_PG_DSN",
    "postgresql://cpp_memory:cpp_memory@127.0.0.1:5433/cpp_memory",
)
AWS_SECRET_NAME = os.environ.get("CPP_MEMORIES_AWS_SECRET", "essent-ai")
AWS_SECRET_KEY = os.environ.get("CPP_MEMORIES_AWS_KEY", "CPP_MEMORIES_DSN")
AWS_PROFILE = os.environ.get("CPP_MEMORIES_AWS_PROFILE")  # optional
AWS_REGION = os.environ.get("CPP_MEMORIES_AWS_REGION", "us-east-1")


def resolve_backend() -> str | None:
    """Return an explicitly-selected backend (md|local-pg|remote-pg), or None.

    None means "not explicitly set" - the factory then infers a backend from
    whether a DSN resolves (a DSN implies today's remote-pg default; no DSN
    implies the local md ledger). Never raises.
    """
    val = os.environ.get("CPP_MEMORIES_BACKEND", "").strip().lower()
    if val in BACKENDS:
        return val
    try:
        if LOCAL_BACKEND_FILE.is_file():
            txt = LOCAL_BACKEND_FILE.read_text(encoding="utf-8").strip().lower()
            if txt in BACKENDS:
                return txt
    except OSError:
        pass
    return None


def resolve_dsn(allow_aws: bool = True) -> str | None:
    """Return the store DSN or None. Never raises."""
    dsn = os.environ.get("CPP_MEMORIES_DSN")
    if dsn and dsn.strip():
        return dsn.strip()

    try:
        if LOCAL_DSN_FILE.is_file():
            txt = LOCAL_DSN_FILE.read_text(encoding="utf-8").strip()
            if txt:
                return txt
    except OSError:
        pass

    if allow_aws:
        return _resolve_from_aws()
    return None


def _resolve_from_aws() -> str | None:
    """Best-effort read of the DSN from the essent-ai secret bundle."""
    cmd = [
        "aws", "secretsmanager", "get-secret-value",
        "--secret-id", AWS_SECRET_NAME,
        "--query", "SecretString", "--output", "text",
        "--region", AWS_REGION,
    ]
    if AWS_PROFILE:
        cmd += ["--profile", AWS_PROFILE]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None

    raw = out.stdout.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw if raw.startswith("postgres") else None
    if isinstance(data, dict):
        val = data.get(AWS_SECRET_KEY)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None
