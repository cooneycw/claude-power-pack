"""Check file permissions on sensitive files.

Ensures that files containing secrets (*.pem, *.key, .env, etc.)
are not world-readable (chmod 600 or stricter).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from ..models import Finding, ScanResult, Severity

# File patterns to check permissions on (actual secret storage files only)
SENSITIVE_PATTERNS = [
    "*.pem",
    "*.key",
    "*.p12",
    ".env",
    ".env.local",
    ".env.production",
]

# Directories to skip
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".mypy_cache"}

# File extensions that are source code, not secrets (skip even if name matches)
SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".md", ".sh", ".rb", ".go", ".rs", ".java", ".php"}

# File suffixes that indicate templates/examples (not actual secrets)
SAFE_SUFFIXES = {".example", ".sample", ".template", ".dist"}


def scan(project_root: str) -> ScanResult:
    """Check file permissions on sensitive files."""
    result = ScanResult()
    root = Path(project_root)
    found_any = False

    for path in _find_sensitive_files(root):
        found_any = True
        try:
            file_stat = path.stat()
            mode = file_stat.st_mode
            # Check if group or others have read access
            if mode & (stat.S_IRGRP | stat.S_IROTH):
                perms = stat.filemode(mode)
                result.findings.append(
                    Finding(
                        id="FILE_PERMISSIONS",
                        severity=Severity.HIGH,
                        title=f"Sensitive file is world-readable: {path.relative_to(root)}",
                        file_path=str(path.relative_to(root)),
                        why="Other users on this system can read this file. "
                        "If it contains secrets, they could be exposed.",
                        fix="Restrict to owner-only access.",
                        command=f"chmod 600 {path.relative_to(root)}",
                        time_estimate="~1 minute",
                        raw_match=f"current permissions: {perms}",
                    )
                )
        except OSError:
            continue

    if found_any and not result.findings:
        result.passed.append("All sensitive files have restricted permissions")
    elif not found_any:
        result.passed.append("No sensitive files found to check permissions on")

    return result


def _find_sensitive_files(root: Path) -> list[Path]:
    """Find files matching sensitive patterns."""
    files = []
    seen = set()
    for pattern in SENSITIVE_PATTERNS:
        for f in root.rglob(pattern):
            if f in seen:
                continue
            seen.add(f)
            if any(skip in f.parts for skip in SKIP_DIRS):
                continue
            # Skip source code files (they contain code about secrets, not secrets themselves)
            if f.suffix in SOURCE_EXTENSIONS:
                continue
            # Skip example/template files
            if any(f.name.endswith(suffix) for suffix in SAFE_SUFFIXES):
                continue
            files.append(f)
    return files
