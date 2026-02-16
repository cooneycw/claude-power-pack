"""Native high-confidence secret detection in source files.

Detects well-known secret patterns with low false-positive rates:
- AWS access keys (AKIA...)
- OpenAI API keys (sk-proj-...)
- GitHub tokens (ghp_..., gho_..., ghs_...)
- Google API keys (AIza...)
- Anthropic keys (sk-ant-...)
- Generic high-entropy strings assigned to secret-like variables
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import Finding, ScanResult, Severity

# High-confidence secret patterns (low false-positive rate)
SECRET_PATTERNS = [
    (
        r"AKIA[0-9A-Z]{16}",
        "AWS_ACCESS_KEY",
        "AWS Access Key detected",
        "This key grants access to your AWS account. "
        "If committed, anyone who sees the repo can use your account.",
    ),
    (
        r"sk-proj-[A-Za-z0-9_-]{20,}",
        "OPENAI_API_KEY",
        "OpenAI API key detected",
        "This key provides access to your OpenAI account and billing.",
    ),
    (
        r"sk-ant-[A-Za-z0-9_-]{20,}",
        "ANTHROPIC_API_KEY",
        "Anthropic API key detected",
        "This key provides access to your Anthropic account and billing.",
    ),
    (
        r"ghp_[A-Za-z0-9]{36,}",
        "GITHUB_PAT",
        "GitHub personal access token detected",
        "This token grants access to your GitHub repos and account.",
    ),
    (
        r"gho_[A-Za-z0-9]{36,}",
        "GITHUB_OAUTH",
        "GitHub OAuth token detected",
        "This token provides GitHub OAuth access.",
    ),
    (
        r"ghs_[A-Za-z0-9]{36,}",
        "GITHUB_APP_TOKEN",
        "GitHub App installation token detected",
        "This token provides GitHub App access to repositories.",
    ),
    (
        r"AIza[A-Za-z0-9_-]{35}",
        "GOOGLE_API_KEY",
        "Google API key detected",
        "This key provides access to Google Cloud services.",
    ),
    (
        r"glpat-[A-Za-z0-9_-]{20,}",
        "GITLAB_PAT",
        "GitLab personal access token detected",
        "This token grants access to your GitLab account.",
    ),
    (
        r"xox[bpsar]-[A-Za-z0-9-]{10,}",
        "SLACK_TOKEN",
        "Slack token detected",
        "This token provides access to your Slack workspace.",
    ),
]

# Variable assignment patterns that suggest hardcoded secrets
ASSIGNMENT_PATTERNS = [
    (
        r"""(?:password|passwd|pwd)\s*[=:]\s*["'][^"']{8,}["']""",
        "HARDCODED_PASSWORD",
        "Hardcoded password in source code",
        "Passwords should never be hardcoded. Use environment variables or a secrets manager.",
    ),
    (
        r"""(?:secret|api_?key|auth_?token|access_?token)\s*[=:]\s*["'][A-Za-z0-9+/=_-]{16,}["']""",
        "HARDCODED_SECRET",
        "Hardcoded secret/token in source code",
        "Secrets and tokens should be loaded from environment variables or a secrets manager.",
    ),
]

# File extensions to scan
SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go", ".java",
    ".rs", ".php", ".sh", ".bash", ".zsh", ".yml", ".yaml",
    ".toml", ".cfg", ".conf", ".ini", ".json", ".xml", ".tf",
    ".tfvars", ".env.example", ".env.sample",
}

# Directories and files to skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
    ".mypy_cache", ".pytest_cache", "dist", "build", ".eggs",
}

SKIP_FILES = {"package-lock.json", "yarn.lock", "uv.lock", "poetry.lock"}

# Files that contain patterns/regex for masking/detection (not actual secrets)
SKIP_PATTERN_FILES = {
    "secrets-mask.sh", "hook-mask-output.sh", "masking.py",
    "explain.py", "secrets.py",  # the scanner itself and explanation docs
}


def scan(project_root: str) -> ScanResult:
    """Scan source files for high-confidence secret patterns."""
    result = ScanResult()
    root = Path(project_root)
    files_scanned = 0

    for file_path in _find_source_files(root):
        files_scanned += 1
        try:
            content = file_path.read_text(errors="ignore")
        except OSError:
            continue

        rel_path = str(file_path.relative_to(root))

        # Check high-confidence patterns
        for pattern, finding_id, title, why in SECRET_PATTERNS:
            for match in re.finditer(pattern, content):
                line_num = content[: match.start()].count("\n") + 1
                matched = match.group()
                masked = matched[:4] + "*" * min(16, len(matched) - 4)
                result.findings.append(
                    Finding(
                        id=finding_id,
                        severity=Severity.CRITICAL,
                        title=title,
                        file_path=rel_path,
                        line_number=line_num,
                        why=why,
                        fix="Move the key to your secrets store and load from environment.",
                        command="# Remove from source, add to .env, load via os.environ",
                        time_estimate="~5 minutes",
                        raw_match=masked,
                    )
                )

        # Check assignment patterns
        for pattern, finding_id, title, why in ASSIGNMENT_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[: match.start()].count("\n") + 1
                result.findings.append(
                    Finding(
                        id=finding_id,
                        severity=Severity.HIGH,
                        title=title,
                        file_path=rel_path,
                        line_number=line_num,
                        why=why,
                        fix="Move to environment variable or secrets manager.",
                        time_estimate="~5 minutes",
                    )
                )

    if files_scanned and not result.findings:
        result.passed.append(f"No secrets found in {files_scanned} source files")
    elif not files_scanned:
        result.skipped.append("No source files found to scan")

    return result


def _find_source_files(root: Path) -> list[Path]:
    """Find source files to scan, respecting skip lists."""
    files = []
    for path in root.rglob("*"):
        if path.is_file():
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            if path.name in SKIP_FILES:
                continue
            if path.name in SKIP_PATTERN_FILES:
                continue
            if path.suffix in SCAN_EXTENSIONS or path.name in (".env.example", ".env.sample"):
                files.append(path)
    return files
