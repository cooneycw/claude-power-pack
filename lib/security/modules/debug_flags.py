"""Detect debug flags left in production configuration.

Checks for DEBUG=True and similar patterns in configuration files
that could expose sensitive information in production.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Finding, ScanResult, Severity

# Patterns that indicate debug mode enabled
DEBUG_PATTERNS = [
    (r"DEBUG\s*=\s*True", "Python DEBUG=True"),
    (r'"debug"\s*:\s*true', "JSON debug: true"),
    (r"debug:\s*true", "YAML debug: true"),
    (r"DEBUG\s*=\s*1", "DEBUG=1"),
    (r"FLASK_DEBUG\s*=\s*1", "Flask debug mode"),
    (r"DJANGO_DEBUG\s*=\s*True", "Django debug mode"),
]

# Only check config-like files
CONFIG_EXTENSIONS = {
    ".py", ".yml", ".yaml", ".toml", ".cfg", ".conf", ".ini", ".json",
}

CONFIG_NAMES = {
    "settings.py", "config.py", "production.py", "prod.py",
    "docker-compose.yml", "docker-compose.yaml",
    "config.yml", "config.yaml", "config.json",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "test", "tests", "fixtures", "mocks",
    "security",  # skip the security scanner module itself
}


def scan(project_root: str) -> ScanResult:
    """Check for debug flags in configuration files."""
    result = ScanResult()
    root = Path(project_root)
    files_checked = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if path.suffix not in CONFIG_EXTENSIONS and path.name not in CONFIG_NAMES:
            continue

        files_checked += 1
        try:
            content = path.read_text(errors="ignore")
        except OSError:
            continue

        rel_path = str(path.relative_to(root))

        for pattern, description in DEBUG_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[: match.start()].count("\n") + 1
                result.findings.append(
                    Finding(
                        id="DEBUG_FLAG",
                        severity=Severity.MEDIUM,
                        title=f"Debug flag enabled: {description}",
                        file_path=rel_path,
                        line_number=line_num,
                        why="Debug mode can expose stack traces, internal paths, "
                        "and sensitive data to users. Should be disabled in production.",
                        fix="Set debug to False for production configurations.",
                        time_estimate="~1 minute",
                    )
                )

    if files_checked and not result.findings:
        result.passed.append("No debug flags found in configuration files")
    elif not files_checked:
        result.skipped.append("No configuration files found to check")

    return result
