"""Tiered DSN resolution for the CPP common-memory store.

Resolution order (first hit wins), all fail-open:
  1. ``CPP_MEMORIES_DSN`` env var           - explicit override / CI injection
  2. local dotenv-global file               - per-machine, works offline
  3. AWS SM ``essent-ai`` key ``CPP_MEMORIES_DSN`` - fleet-wide federation

The AWS tier is the mechanism that lets every VM resolve the same store. The
DSN host should be the store's Tailscale address so Tailscale-only hosts reach
it too.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

LOCAL_DSN_FILE = (
    Path.home() / ".config" / "claude-power-pack" / "secrets" / "cpp-memories.dsn"
)
AWS_SECRET_NAME = os.environ.get("CPP_MEMORIES_AWS_SECRET", "essent-ai")
AWS_SECRET_KEY = os.environ.get("CPP_MEMORIES_AWS_KEY", "CPP_MEMORIES_DSN")
AWS_PROFILE = os.environ.get("CPP_MEMORIES_AWS_PROFILE")  # optional
AWS_REGION = os.environ.get("CPP_MEMORIES_AWS_REGION", "us-east-1")


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
