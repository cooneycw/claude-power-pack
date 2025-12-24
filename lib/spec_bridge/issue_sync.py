"""Sync spec tasks to GitHub issues via gh CLI.

Creates and updates GitHub issues from tasks.md files.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .parser import Wave, parse_tasks, parse_spec


@dataclass
class IssueInfo:
    """Information about a GitHub issue."""

    number: int
    title: str
    state: str  # "OPEN" or "CLOSED"
    labels: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of a sync operation."""

    feature: str
    waves_synced: int = 0
    issues_created: list[int] = field(default_factory=list)
    issues_skipped: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False


def get_repo_info() -> tuple[str, str]:
    """Get current repository owner and name.

    Returns:
        Tuple of (owner, repo_name)

    Raises:
        RuntimeError: If not in a git repository or gh not available
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "owner,name"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return data["owner"]["login"], data["name"]
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get repo info: {e.stderr}") from e
    except FileNotFoundError:
        raise RuntimeError("gh CLI not found. Install from https://cli.github.com/") from None


def list_issues(
    labels: Optional[list[str]] = None,
    state: str = "all",
    limit: int = 100,
) -> list[IssueInfo]:
    """List GitHub issues.

    Args:
        labels: Filter by labels
        state: "open", "closed", or "all"
        limit: Maximum issues to return

    Returns:
        List of IssueInfo objects
    """
    cmd = [
        "gh", "issue", "list",
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,state,labels",
    ]

    if labels:
        for label in labels:
            cmd.extend(["--label", label])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        issues = []
        for item in data:
            issue = IssueInfo(
                number=item["number"],
                title=item["title"],
                state=item["state"],
                labels=[l["name"] for l in item.get("labels", [])],
            )
            issues.append(issue)

        return issues
    except subprocess.CalledProcessError:
        return []


def create_issue(
    title: str,
    body: str,
    labels: Optional[list[str]] = None,
    dry_run: bool = False,
) -> Optional[int]:
    """Create a GitHub issue.

    Args:
        title: Issue title
        body: Issue body (markdown)
        labels: Labels to apply
        dry_run: If True, don't actually create

    Returns:
        Issue number if created, None if dry_run
    """
    if dry_run:
        return None

    cmd = ["gh", "issue", "create", "--title", title, "--body", body]

    if labels:
        cmd.extend(["--label", ",".join(labels)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Output is like: https://github.com/owner/repo/issues/42
        match = re.search(r"/issues/(\d+)", result.stdout)
        if match:
            return int(match.group(1))
        return None
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create issue: {e.stderr}") from e


def generate_issue_body(
    wave: Wave,
    feature_name: str,
    spec_path: Optional[Path] = None,
) -> str:
    """Generate issue body from wave tasks.

    Args:
        wave: Wave containing tasks
        feature_name: Name of the feature
        spec_path: Path to spec directory for links

    Returns:
        Markdown issue body
    """
    lines = []

    # Parent spec section
    lines.append("## Parent Spec")
    lines.append("")
    lines.append(f"**Feature:** `{feature_name}`")
    if spec_path:
        lines.append(f"**Spec:** `.specify/specs/{feature_name}/spec.md`")
        lines.append(f"**Plan:** `.specify/specs/{feature_name}/plan.md`")
    lines.append("")

    # Tasks section
    lines.append("## Tasks")
    lines.append("")

    for task in wave.tasks:
        checkbox = "[x]" if task.completed else "[ ]"
        task_line = f"- {checkbox} **{task.id}** [{task.story}] {task.description}"

        if task.file_path:
            task_line += f" `{task.file_path}`"

        if task.dependencies:
            deps = ", ".join(task.dependencies)
            task_line += f" (depends on {deps})"

        lines.append(task_line)

    lines.append("")

    # Files to modify section
    files = [t.file_path for t in wave.tasks if t.file_path]
    if files:
        lines.append("## Files to Modify")
        lines.append("")
        for f in sorted(set(files)):
            lines.append(f"- `{f}`")
        lines.append("")

    # Checkpoint
    if wave.checkpoint:
        lines.append("## Checkpoint")
        lines.append("")
        lines.append(wave.checkpoint)
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Created from spec via `/spec:sync`*")

    return "\n".join(lines)


def sync_feature(
    feature_name: str,
    spec_dir: Path | str = ".specify/specs",
    dry_run: bool = False,
) -> SyncResult:
    """Sync a feature's tasks to GitHub issues.

    Args:
        feature_name: Name of the feature (directory name in specs/)
        spec_dir: Path to specs directory
        dry_run: If True, don't create issues

    Returns:
        SyncResult with details of what was done
    """
    spec_dir = Path(spec_dir)
    feature_path = spec_dir / feature_name
    result = SyncResult(feature=feature_name, dry_run=dry_run)

    # Check feature exists
    if not feature_path.exists():
        result.errors.append(f"Feature not found: {feature_path}")
        return result

    # Parse tasks
    tasks_path = feature_path / "tasks.md"
    if not tasks_path.exists():
        result.errors.append(f"tasks.md not found: {tasks_path}")
        return result

    try:
        waves = parse_tasks(tasks_path)
    except Exception as e:
        result.errors.append(f"Failed to parse tasks: {e}")
        return result

    # Get existing issues for this feature
    existing_issues = list_issues(labels=[feature_name])
    existing_titles = {i.title for i in existing_issues}

    # Create issues for each wave
    for wave in waves:
        # Generate title
        wave_num = wave.name.replace("Wave ", "")
        title = f"[Wave {wave_num}] {_title_case(feature_name)}: {wave.description}"

        # Skip if already exists
        if wave.issue_number:
            result.issues_skipped.append(wave.issue_number)
            continue

        # Check if similar title exists
        if any(title.lower() in t.lower() or t.lower() in title.lower() for t in existing_titles):
            result.issues_skipped.append(0)  # Exists but unknown number
            continue

        # Generate body
        body = generate_issue_body(wave, feature_name, feature_path)

        # Labels
        labels = [feature_name, f"wave-{wave_num}", "enhancement"]

        # Create issue
        try:
            issue_num = create_issue(title, body, labels, dry_run)
            if issue_num:
                result.issues_created.append(issue_num)
                wave.issue_number = issue_num
            result.waves_synced += 1
        except RuntimeError as e:
            result.errors.append(str(e))

    # Update tasks.md with issue numbers (if not dry run)
    if not dry_run and result.issues_created:
        _update_tasks_file(tasks_path, waves)

    return result


def sync_all_features(
    spec_dir: Path | str = ".specify/specs",
    dry_run: bool = False,
) -> list[SyncResult]:
    """Sync all features to GitHub issues.

    Args:
        spec_dir: Path to specs directory
        dry_run: If True, don't create issues

    Returns:
        List of SyncResult for each feature
    """
    spec_dir = Path(spec_dir)
    results = []

    if not spec_dir.exists():
        return results

    for feature_path in spec_dir.iterdir():
        if feature_path.is_dir() and (feature_path / "tasks.md").exists():
            result = sync_feature(feature_path.name, spec_dir, dry_run)
            results.append(result)

    return results


def _title_case(name: str) -> str:
    """Convert kebab-case to Title Case."""
    return " ".join(word.capitalize() for word in name.split("-"))


def _update_tasks_file(tasks_path: Path, waves: list[Wave]) -> None:
    """Update tasks.md with issue numbers in sync table."""
    content = tasks_path.read_text()

    # Find or create Issue Sync section
    sync_section = re.search(
        r"(##\s*Issue\s*Sync.*?\n)((?:\|.*\n)+)",
        content,
        re.IGNORECASE,
    )

    # Build new table
    table_lines = [
        "| Wave | Tasks | Issue | Status |",
        "|------|-------|-------|--------|",
    ]

    for wave in waves:
        wave_num = wave.name.replace("Wave ", "")
        task_ids = ", ".join(t.id for t in wave.tasks) if wave.tasks else "-"
        issue = f"#{wave.issue_number}" if wave.issue_number else "-"
        status = "synced" if wave.issue_number else "pending"
        table_lines.append(f"| {wave_num} | {task_ids} | {issue} | {status} |")

    table_content = "\n".join(table_lines) + "\n"

    if sync_section:
        # Replace existing table
        new_content = content[:sync_section.start(2)] + table_content + content[sync_section.end(2):]
    else:
        # Append new section
        new_content = content.rstrip() + "\n\n## Issue Sync\n\n" + table_content

    tasks_path.write_text(new_content)
