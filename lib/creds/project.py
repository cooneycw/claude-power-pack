"""Project identity for secrets management.

Derives a stable project_id from the git repository root, ensuring
all worktrees for the same repo share the same identity. This means
secrets are stored per-project, not per-worktree.

Usage:
    from lib.creds.project import get_project_id, get_project_root

    project_id = get_project_id()  # e.g., "claude-power-pack"
    root = get_project_root()      # e.g., "/home/user/Projects/claude-power-pack"
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


def get_project_root() -> Path:
    """Get the root directory of the git repository.

    For worktrees, this returns the main repository root (not the
    worktree directory), ensuring consistency across all worktrees.

    Returns:
        Path to the git repository root.

    Raises:
        RuntimeError: If not inside a git repository.
    """
    try:
        # git rev-parse --show-toplevel gives the worktree root
        # For the main repo root, we need --git-common-dir
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError("Not inside a git repository")

        git_common_dir = Path(result.stdout.strip())

        # If it's a worktree, git_common_dir is like /path/to/main/.git
        # If it's the main repo, it's just .git
        if git_common_dir.is_absolute():
            return git_common_dir.parent
        else:
            # Relative path — resolve from cwd
            toplevel = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if toplevel.returncode != 0:
                raise RuntimeError("Not inside a git repository")

            worktree_root = Path(toplevel.stdout.strip())
            resolved = (worktree_root / git_common_dir).resolve()

            # If git_common_dir is ".git", parent is the repo root
            # If it's "../main-repo/.git", parent is the main repo
            return resolved.parent

    except FileNotFoundError:
        raise RuntimeError("git is not installed")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git command timed out")


def get_project_id(project_root: Path | None = None) -> str:
    """Get a stable project identifier.

    Uses the repository directory name by default. Falls back to
    a hash of the absolute path if the name contains unusual characters.

    Args:
        project_root: Override the auto-detected project root.

    Returns:
        A filesystem-safe project identifier string.
    """
    if project_root is None:
        project_root = get_project_root()

    name = project_root.name

    # Validate the name is filesystem-safe
    if name and all(c.isalnum() or c in "-_." for c in name):
        return name.lower()

    # Fall back to a short hash of the full path
    path_hash = hashlib.sha256(str(project_root).encode()).hexdigest()[:12]
    return f"project-{path_hash}"


def get_secrets_dir(project_id: str | None = None) -> Path:
    """Get the directory for storing project secrets.

    Secrets are stored outside the repo to prevent accidental commits
    and avoid worktree drift.

    Location: ~/.config/claude-power-pack/secrets/{project_id}/

    Args:
        project_id: Override the auto-detected project ID.

    Returns:
        Path to the secrets directory (created if needed).
    """
    if project_id is None:
        project_id = get_project_id()

    config_home = os.environ.get(
        "XDG_CONFIG_HOME", os.path.expanduser("~/.config")
    )
    secrets_dir = Path(config_home) / "claude-power-pack" / "secrets" / project_id

    return secrets_dir


def ensure_secrets_dir(project_id: str | None = None) -> Path:
    """Get the secrets directory, creating it with secure permissions.

    Args:
        project_id: Override the auto-detected project ID.

    Returns:
        Path to the secrets directory.
    """
    secrets_dir = get_secrets_dir(project_id)
    secrets_dir.mkdir(parents=True, exist_ok=True)

    # Enforce directory permissions: owner-only
    secrets_dir.chmod(0o700)

    return secrets_dir
