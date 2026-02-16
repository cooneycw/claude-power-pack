"""Audit logging for secrets operations.

Logs actions (who, when, what) but NEVER secret values.
Audit log location: ~/.config/claude-power-pack/audit.log

Usage:
    from lib.creds.audit import log_action

    log_action("get", project_id="my-app", details="key=DB_PASSWORD")
    log_action("set", project_id="my-app", details="key=API_KEY")
    log_action("rotate", project_id="my-app", details="key=DB_PASSWORD")
"""

from __future__ import annotations

import getpass
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_audit_log_path() -> Path:
    """Get the path to the audit log file."""
    config_home = os.environ.get(
        "XDG_CONFIG_HOME", os.path.expanduser("~/.config")
    )
    return Path(config_home) / "claude-power-pack" / "audit.log"


def log_action(
    action: str,
    project_id: str = "",
    details: str = "",
) -> None:
    """Log a secrets action to the audit log.

    NEVER include secret values in the details string.

    Args:
        action: The action performed (get, set, delete, rotate, run, ui).
        project_id: The project identifier.
        details: Additional details (key names, provider, NOT values).
    """
    log_path = _get_audit_log_path()

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).isoformat()
        user = getpass.getuser()

        entry = f"{timestamp} | {action} | {project_id} | {user} | {details}\n"

        with open(log_path, "a") as f:
            f.write(entry)

        # Enforce permissions on first write
        if log_path.stat().st_size <= len(entry):
            log_path.chmod(0o600)

    except Exception as e:
        # Audit logging should never block operations
        logger.debug(f"Audit log write failed: {e}")
