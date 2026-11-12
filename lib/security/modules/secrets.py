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

import errno
import os
import re
import stat
import subprocess
from collections import Counter
from pathlib import Path
from typing import Optional

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

# Files with no extension (issue #1737). `SCAN_EXTENSIONS` selects by suffix, so
# `bin/deploy`, a git hook, a `Makefile` or a `Dockerfile` was never opened, and
# the scan still said "No secrets found in N source files" over a population
# that left them out. Two rules bring them in, and both are deliberately
# narrow: this must not turn into "read everything".
#
# - a file with NO suffix whose first two bytes are `#!`. The shebang decides,
#   not the execute bit: mode bits are lost on some checkouts, and an
#   executable with no shebang is far more often a binary than a script;
# - the well-known build-file names below, matched on the EXACT basename, plus
#   the `Dockerfile.<x>` form. `Makefile.bak` and `my-Dockerfile` are not on it.
#
# The extension population above is selected exactly as before. Everything
# here ADDS files; nothing here can remove one.
SCAN_NAMES = frozenset({"Makefile", "GNUmakefile", "makefile", "Dockerfile", "Containerfile"})
SCAN_NAME_PREFIXES = ("Dockerfile.",)

# Bounds for the NEW population only. The head is read to find the shebang and
# to refuse a binary (a NUL byte); a file over the cap is not read at all.
EXTENSIONLESS_HEAD_BYTES = 8192
EXTENSIONLESS_MAX_BYTES = 1_000_000

# Why an extensionless file was not read, in the order the summary prints them.
UNREAD_NO_SIGNAL = "no shebang or known name"
UNREAD_BINARY = "binary"
UNREAD_TOO_LARGE = "over 1 MB"
UNREAD_NOT_REGULAR = "a symlink or not a regular file"
UNREAD_UNREADABLE = "could not be opened"
UNREAD_REASONS = (UNREAD_NO_SIGNAL, UNREAD_BINARY, UNREAD_TOO_LARGE, UNREAD_NOT_REGULAR, UNREAD_UNREADABLE)

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

    unread: Counter[str] = Counter()
    # The extension population is read exactly as before. An extensionless
    # candidate is read ONCE, through the same descriptor its checks ran on
    # (issue #1737): reopening it by name after checking would let a file
    # swapped in between be followed, waited on, or read without bound.
    sources: list[tuple[Path, bool]] = [(p, False) for p in _find_source_files(root)]
    sources += [(p, True) for p in _find_extensionless_candidates(root)]

    for file_path, extensionless in sources:
        if extensionless:
            guarded, reason = _read_extensionless(root, file_path)
            if guarded is None:
                unread[reason or UNREAD_UNREADABLE] += 1
                continue
        try:
            content = guarded if extensionless and guarded is not None else file_path.read_text(errors="ignore")
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

    if sum(unread.values()):
        # Its own field, NOT `skipped` (issue #1737): `len(result.skipped)` is
        # printed as `skipped-checks=` on the SECURITY_GATE line, where it means
        # "checks that could not run". Nearly every repository holds an
        # extensionless file with no shebang (LICENSE), so this line there would
        # move that number almost everywhere and change what it says.
        reasons = ", ".join(f"{unread[r]} {r}" for r in UNREAD_REASONS if unread[r])
        result.unexamined.append(
            f"{sum(unread.values())} file(s) with no recognised extension were NOT read ({reasons})"
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
            if _selected_by_extension(path):
                files.append(path)
    return _filter_gitignored(root, files)


def _selected_by_extension(path: Path) -> bool:
    """The pre-#1737 selection rule, in one place so both finders agree on it."""
    return (
        path.suffix in SCAN_EXTENSIONS
        or path.name in (".env.example", ".env.sample")
        or path.name.startswith(".env")
    )


def _has_scan_name(name: str) -> bool:
    """An exact well-known name, or `Dockerfile.<x>` with a NON-EMPTY `<x>`."""
    return name in SCAN_NAMES or any(name.startswith(p) and len(name) > len(p) for p in SCAN_NAME_PREFIXES)


def _find_extensionless_candidates(root: Path) -> list[Path]:
    """Extensionless paths that are CANDIDATES for reading (issue #1737).

    Selection only: nothing is opened here. A path the extension rule already
    selects is never a candidate, so the two populations cannot overlap and no
    file is counted twice. Whether a candidate is actually read is decided by
    `_read_extensionless`, at the moment it is read.
    """
    candidates: list[Path] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if rel.parts[: len(RUNNER_STATE_DIR)] == RUNNER_STATE_DIR or rel.parts == DEPLOY_BASELINE_FILE:
            continue
        if path.name in SKIP_FILES or path.name in SKIP_PATTERN_FILES:
            continue
        if _selected_by_extension(path):
            continue
        if path.suffix and not _has_scan_name(path.name):
            continue
        try:
            mode = path.lstat().st_mode
        except OSError:
            continue
        if stat.S_ISDIR(mode):
            continue
        candidates.append(path)
    return _filter_gitignored(root, candidates)


def _read_extensionless(root: Path, path: Path) -> tuple[Optional[str], Optional[str]]:
    """Read one extensionless candidate: ``(content, None)`` or ``(None, reason)``.

    Every check and the read itself happen on ONE descriptor, reached by
    walking down from the scan root one component at a time:

    - each directory on the way is opened `O_DIRECTORY | O_NOFOLLOW` relative
      to its parent's descriptor, so a parent swapped for a symlink after
      enumeration is refused instead of leading out of the root (`O_NOFOLLOW`
      on a whole path guards only its last component);
    - the file is opened `O_NOFOLLOW | O_NONBLOCK` and `fstat`ed on the
      descriptor before a byte is read, so a symlink is never followed and a
      FIFO or device is refused rather than waited on;
    - at most `EXTENSIONLESS_MAX_BYTES + 1` bytes are read, so a file that
      grows after it was listed is refused as too large, never read without
      bound.

    The content returned is exactly what was checked. Nothing reopens the path.
    """
    rel = path.relative_to(root)
    dir_fd = -1
    fd = -1
    try:
        try:
            dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            for part in rel.parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
                os.close(dir_fd)
                dir_fd = next_fd
        except OSError:
            # ELOOP / ENOTDIR: a directory on the way is a symlink or is gone.
            return None, UNREAD_NOT_REGULAR
        try:
            fd = os.open(rel.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
        except OSError as exc:
            return None, UNREAD_NOT_REGULAR if exc.errno == errno.ELOOP else UNREAD_UNREADABLE
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode):
                return None, UNREAD_NOT_REGULAR
            if opened.st_size > EXTENSIONLESS_MAX_BYTES:
                return None, UNREAD_TOO_LARGE
            chunks: list[bytes] = []
            remaining = EXTENSIONLESS_MAX_BYTES + 1
            while remaining > 0:
                chunk = os.read(fd, min(remaining, 1 << 16))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        except OSError:
            return None, UNREAD_UNREADABLE
    finally:
        for descriptor in (fd, dir_fd):
            if descriptor >= 0:
                os.close(descriptor)
    data = b"".join(chunks)
    if len(data) > EXTENSIONLESS_MAX_BYTES:
        return None, UNREAD_TOO_LARGE
    if b"\0" in data[:EXTENSIONLESS_HEAD_BYTES]:
        return None, UNREAD_BINARY
    if not (_has_scan_name(path.name) or data.startswith(b"#!")):
        return None, UNREAD_NO_SIGNAL
    return data.decode("utf-8", errors="ignore"), None


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
