"""Check .gitignore covers sensitive file patterns.

Verifies that common sensitive files (.env, *.pem, *.key, secrets.*)
are listed in .gitignore to prevent accidental commits.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Finding, ScanResult, Severity

# Patterns that should be in .gitignore
REQUIRED_PATTERNS = [
    (".env", "Environment variables file containing secrets"),
    (".env.*", "Environment-specific files (.env.local, .env.production)"),
    ("*.pem", "TLS/SSH private key files"),
    ("*.key", "Private key files"),
    ("secrets.*", "Secrets configuration files"),
    ("*.p12", "PKCS#12 certificate files"),
    (".claude/security.yml", "Security scan suppressions (may contain path info)"),
]


def scan(project_root: str) -> ScanResult:
    """Check .gitignore for required sensitive file patterns."""
    result = ScanResult()
    gitignore_path = Path(project_root) / ".gitignore"

    if not gitignore_path.exists():
        result.findings.append(
            Finding(
                id="GITIGNORE_MISSING",
                severity=Severity.HIGH,
                title="No .gitignore file found",
                file_path=".gitignore",
                why="Without a .gitignore, `git add .` will stage all files "
                "including secrets, keys, and environment files.",
                fix="Create a .gitignore with standard exclusions.",
                command='curl -sL https://www.toptal.com/developers/gitignore/api/python > .gitignore && echo ".env" >> .gitignore',
                time_estimate="~2 minutes",
            )
        )
        return result

    gitignore_content = gitignore_path.read_text()
    gitignore_lines = [
        line.strip()
        for line in gitignore_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    missing = []
    for pattern, description in REQUIRED_PATTERNS:
        if not _pattern_covered(pattern, gitignore_lines):
            missing.append((pattern, description))

    if missing:
        for pattern, description in missing:
            result.findings.append(
                Finding(
                    id="GITIGNORE_GAP",
                    severity=Severity.CRITICAL if pattern == ".env" else Severity.HIGH,
                    title=f"`{pattern}` not in .gitignore",
                    file_path=".gitignore",
                    why=f"{description}. Without gitignore coverage, "
                    "`git add .` will include it in your next commit.",
                    fix=f"Add `{pattern}` to .gitignore.",
                    command=f'echo "{pattern}" >> .gitignore',
                    time_estimate="~1 minute",
                )
            )
    else:
        result.passed.append("All sensitive file patterns covered in .gitignore")

    return result


def _pattern_covered(pattern: str, gitignore_lines: list[str]) -> bool:
    """Check if a pattern is covered by any gitignore line."""
    # Direct match
    if pattern in gitignore_lines:
        return True

    # Check for broader patterns that cover ours
    # e.g., "*.pem" covers "server.pem"
    for line in gitignore_lines:
        # .env is covered by .env or .env*
        if pattern == ".env" and line in (".env", ".env*", ".env.*"):
            return True
        if pattern == ".env.*" and line in (".env*", ".env.*"):
            return True
        # Wildcard patterns
        if line == pattern:
            return True
        # e.g., gitignore has "*.key" which covers our "*.key"
        if "*" in line and pattern.endswith(line.replace("*", "")):
            return True

    return False
