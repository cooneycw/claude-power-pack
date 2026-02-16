"""Detect .env files tracked by git.

.env files should never be committed to version control as they
typically contain secrets. This module checks for .env files that
are tracked by git (not just present on disk).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..models import Finding, ScanResult, Severity


def scan(project_root: str) -> ScanResult:
    """Check if any .env files are tracked by git."""
    result = ScanResult()
    root = Path(project_root)

    # Check if this is a git repo
    git_dir = root / ".git"
    if not git_dir.exists():
        result.skipped.append(".env tracking check (not a git repository)")
        return result

    # Get list of tracked files matching .env patterns
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--", "*.env", ".env", ".env.*"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=10,
        )
        tracked_env_files = [
            f.strip() for f in proc.stdout.strip().splitlines() if f.strip()
        ]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        result.errors.append("Could not check git-tracked .env files")
        return result

    # Also check for common env file names not caught by the glob
    try:
        proc2 = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=10,
        )
        all_tracked = proc2.stdout.strip().splitlines()
        for f in all_tracked:
            name = Path(f).name
            if name.startswith(".env") and f not in tracked_env_files:
                tracked_env_files.append(f)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Filter out safe files like .env.example
    safe_suffixes = {".example", ".sample", ".template", ".dist"}
    unsafe_files = [
        f
        for f in tracked_env_files
        if not any(f.endswith(suffix) for suffix in safe_suffixes)
    ]

    for env_file in unsafe_files:
        result.findings.append(
            Finding(
                id="ENV_TRACKED",
                severity=Severity.CRITICAL,
                title=f".env file tracked by git: {env_file}",
                file_path=env_file,
                why="Your .env file contains secrets. Since it's tracked by git, "
                "those secrets are in your repository history. Anyone with "
                "access to the repo can see them.",
                fix="Remove from tracking (keeps the file locally) and add to .gitignore.",
                command=f'git rm --cached {env_file} && echo "{env_file}" >> .gitignore',
                time_estimate="~2 minutes",
            )
        )

    if not unsafe_files:
        result.passed.append("No .env files tracked by git")

    return result
