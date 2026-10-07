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
import subprocess
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

# Variable assignment patterns that suggest hardcoded secrets. The value
# itself is capturing group 1 (issue #1405) - without it, `scan()` below has
# no actual value to put in `Finding.secret_value`, and a `secret:`
# suppression's exact-value match (issue #1299, `_is_declared_in_config`) can
# never apply to one of these findings at all, no matter what id it is
# declared under.
ASSIGNMENT_PATTERNS = [
    (
        r"""(?:password|passwd|pwd)\s*[=:]\s*["']([^"']{8,})["']""",
        "HARDCODED_PASSWORD",
        "Hardcoded password in source code",
        "Passwords should never be hardcoded. Use environment variables or a secrets manager.",
    ),
    (
        r"""(?:secret|api_?key|auth_?token|access_?token)\s*[=:]\s*["']([A-Za-z0-9+/=_-]{16,})["']""",
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

# The deterministic runner's OWN state directory, relative to the scan root
# (issue #1341). `lib/cicd/state.py` writes `.claude/runs/<run_id>.json` there
# while its `security_scan` step is executing, so without this skip the scan
# counted that bookkeeping as project source: a tree with no source reported
# `scanned=1`, and #1027's zero-coverage warning fired only in projects that
# happened to gitignore the file. Deliberately a root-anchored PREFIX, not a
# `SKIP_DIRS` entry: every other `.claude/*.json`, and a nested project's
# `sub/.claude/runs/`, are still scanned.
RUNNER_STATE_DIR = (".claude", "runs")

# `lib/cicd/verify.py`'s own per-workstation runtime state file, relative to
# the scan root (issue #1405) - documented there as "like .claude/runs/", and
# the same defect as RUNNER_STATE_DIR above: a tree with no project source at
# all still reports `scanned=1`, because the file is JSON and `.json` is a
# scanned extension. An EXACT root-anchored path, not a `SKIP_FILES` entry: a
# bare-name skip would also hide a differently-located, unrelated file of the
# same name.
DEPLOY_BASELINE_FILE = (".claude", "deploy-baseline.json")

# Files that contain patterns/regex for masking/detection (not actual secrets)
SKIP_PATTERN_FILES = {
    "secrets-mask.sh", "hook-mask-output.sh", "masking.py",
    "explain.py", "secrets.py",  # the scanner itself and explanation docs
    "test_creds_masking.py", "test_security_models.py", "test_security_scanners.py",
}


def scan(project_root: str) -> ScanResult:
    """Scan source files for high-confidence secret patterns."""
    result = ScanResult()
    root = Path(project_root)
    files_scanned = 0
    files_unreadable = 0

    for file_path in _find_source_files(root):
        try:
            content = file_path.read_text(errors="ignore")
        except OSError:
            # Counted only AFTER a successful read (issue #1027, cross-model
            # review). This used to increment above the `try`, so a file the
            # scanner could not open still counted as examined - and once
            # `files_scanned` became the exported coverage number, one
            # unreadable file was enough to report `scanned=1` for a scan that
            # inspected no content at all. That is precisely the
            # looked-and-found-nothing / nothing-to-look-at collapse this
            # field exists to prevent, reintroduced inside the fix for it.
            files_unreadable += 1
            continue
        files_scanned += 1

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
                        secret_value=matched,
                    )
                )

        # Check assignment patterns
        for pattern, finding_id, title, why in ASSIGNMENT_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[: match.start()].count("\n") + 1
                value = match.group(1)
                masked = value[:4] + "*" * min(16, len(value) - 4) if len(value) > 4 else "****"
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
                        raw_match=masked,
                        secret_value=value,
                    )
                )

    # Stated unconditionally, including the zero (issue #1027). The prose below
    # already distinguished the two cases for a human reader, but only on the
    # findings-free path and only as English - so nothing downstream could act
    # on it. This is the same fact as a number.
    result.units_scanned = files_scanned

    if files_unreadable:
        # Reported rather than folded into the count, so a partial scan stays
        # visible. Silently excluding them would make `scanned=` honest and the
        # scan's completeness invisible - a different version of the same
        # collapse.
        result.skipped.append(
            f"{files_unreadable} source file(s) could not be read and were NOT scanned"
        )

    if files_scanned and not result.findings:
        result.passed.append(f"No secrets found in {files_scanned} source files")
    elif not files_scanned:
        result.skipped.append("No source files found to scan")

    return result


def _find_source_files(root: Path) -> list[Path]:
    """Find source files to scan, respecting skip lists and .gitignore."""
    files = []
    for path in root.rglob("*"):
        if path.is_file():
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            if path.relative_to(root).parts[: len(RUNNER_STATE_DIR)] == RUNNER_STATE_DIR:
                continue
            if path.relative_to(root).parts == DEPLOY_BASELINE_FILE:
                continue
            if path.name in SKIP_FILES:
                continue
            if path.name in SKIP_PATTERN_FILES:
                continue
            # `.env*` names are matched by PREFIX, not by suffix (issue #1405):
            # a plain `.env` or `.env.production` has no entry in
            # `SCAN_EXTENSIONS` at all, so a tracked file of either name was
            # invisible to this content scanner - only `env_files.py`'s
            # presence-only `ENV_TRACKED` check ever looked at it, and
            # suppressing that one finding left the file's actual content
            # (if any secret inside it) completely uninspected. Matches
            # `env_files.py`'s own `name.startswith(".env")` convention.
            if (
                path.suffix in SCAN_EXTENSIONS
                or path.name in (".env.example", ".env.sample")
                or path.name.startswith(".env")
            ):
                files.append(path)
    return _filter_gitignored(root, files)


def _filter_gitignored(root: Path, files: list[Path]) -> list[Path]:
    """Drop candidate paths that git would ignore.

    Gitignored, never-committed local files (e.g. `.claude/settings.local.json`)
    hold real credentials by design but are excluded from the repo, so flagging
    them is a false positive on a security gate. This filters them out while
    keeping the scanner honest about *committable* risk: `git check-ignore` is
    index-aware by default, so a *tracked* file that also matches an ignore
    pattern is NOT reported as ignored and still gets scanned.

    Fail-open: outside a git work tree, or on any git error/timeout, the input
    list is returned unchanged so scanning never silently narrows.
    """
    if not files:
        return files

    try:
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return files
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return files

    # Batch every candidate through a single check-ignore call over stdin.
    # Exit status: 0 = at least one path ignored, 1 = none ignored, >1 = error.
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--stdin"],
            input="\n".join(str(f) for f in files),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return files
    if proc.returncode not in (0, 1):
        return files

    ignored = {line for line in proc.stdout.splitlines() if line}
    return [f for f in files if str(f) not in ignored]
