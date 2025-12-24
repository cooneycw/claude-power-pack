"""Check alignment between specs and GitHub issues.

Provides status reporting for spec-driven development workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .parser import parse_tasks, parse_spec, parse_plan, Wave, SpecDocument
from .issue_sync import list_issues, IssueInfo


@dataclass
class FileStatus:
    """Status of a spec file."""

    exists: bool = False
    complete: bool = False
    item_count: int = 0
    details: str = ""


@dataclass
class FeatureStatus:
    """Complete status of a feature specification."""

    name: str
    path: Path
    spec: FileStatus = field(default_factory=FileStatus)
    plan: FileStatus = field(default_factory=FileStatus)
    tasks: FileStatus = field(default_factory=FileStatus)
    waves: list[Wave] = field(default_factory=list)
    issues: list[IssueInfo] = field(default_factory=list)
    synced_count: int = 0
    pending_count: int = 0

    @property
    def is_ready_to_sync(self) -> bool:
        """Check if feature is ready for issue sync."""
        return self.tasks.exists and self.tasks.item_count > 0 and self.pending_count > 0


@dataclass
class ProjectStatus:
    """Overall project spec status."""

    spec_dir: Path
    features: list[FeatureStatus] = field(default_factory=list)
    total_features: int = 0
    total_synced: int = 0
    total_pending: int = 0


def get_feature_status(
    feature_name: str,
    spec_dir: Path | str = ".specify/specs",
) -> FeatureStatus:
    """Get detailed status of a feature specification.

    Args:
        feature_name: Name of the feature directory
        spec_dir: Path to specs directory

    Returns:
        FeatureStatus with all details
    """
    spec_dir = Path(spec_dir)
    feature_path = spec_dir / feature_name

    status = FeatureStatus(name=feature_name, path=feature_path)

    if not feature_path.exists():
        return status

    # Check spec.md
    spec_path = feature_path / "spec.md"
    if spec_path.exists():
        try:
            spec_doc = parse_spec(spec_path)
            status.spec = FileStatus(
                exists=True,
                complete=len(spec_doc.user_stories) > 0,
                item_count=len(spec_doc.user_stories),
                details=f"{len(spec_doc.user_stories)} user stories, {len(spec_doc.requirements)} requirements",
            )
        except Exception as e:
            status.spec = FileStatus(exists=True, details=f"Parse error: {e}")
    else:
        status.spec = FileStatus(exists=False, details="Missing")

    # Check plan.md
    plan_path = feature_path / "plan.md"
    if plan_path.exists():
        try:
            plan_doc = parse_plan(plan_path)
            has_content = bool(plan_doc.summary.strip())
            status.plan = FileStatus(
                exists=True,
                complete=has_content,
                details="Complete" if has_content else "Draft (empty summary)",
            )
        except Exception as e:
            status.plan = FileStatus(exists=True, details=f"Parse error: {e}")
    else:
        status.plan = FileStatus(exists=False, details="Missing")

    # Check tasks.md
    tasks_path = feature_path / "tasks.md"
    if tasks_path.exists():
        try:
            waves = parse_tasks(tasks_path)
            total_tasks = sum(len(w.tasks) for w in waves)
            completed_tasks = sum(sum(1 for t in w.tasks if t.completed) for w in waves)

            status.waves = waves
            status.tasks = FileStatus(
                exists=True,
                complete=total_tasks > 0,
                item_count=total_tasks,
                details=f"{total_tasks} tasks in {len(waves)} waves ({completed_tasks} completed)",
            )

            # Count synced vs pending waves
            status.synced_count = sum(1 for w in waves if w.issue_number)
            status.pending_count = len(waves) - status.synced_count
        except Exception as e:
            status.tasks = FileStatus(exists=True, details=f"Parse error: {e}")
    else:
        status.tasks = FileStatus(exists=False, details="Missing")

    # Get GitHub issues for this feature
    try:
        status.issues = list_issues(labels=[feature_name])
    except Exception:
        pass  # Issues fetch failed, leave empty

    return status


def get_all_status(spec_dir: Path | str = ".specify/specs") -> ProjectStatus:
    """Get status of all feature specifications.

    Args:
        spec_dir: Path to specs directory

    Returns:
        ProjectStatus with all features
    """
    spec_dir = Path(spec_dir)
    project = ProjectStatus(spec_dir=spec_dir)

    if not spec_dir.exists():
        return project

    for feature_path in sorted(spec_dir.iterdir()):
        if feature_path.is_dir():
            feature_status = get_feature_status(feature_path.name, spec_dir)
            project.features.append(feature_status)

            project.total_features += 1
            project.total_synced += feature_status.synced_count
            project.total_pending += feature_status.pending_count

    return project


def format_feature_status(status: FeatureStatus, verbose: bool = False) -> str:
    """Format feature status for display.

    Args:
        status: FeatureStatus to format
        verbose: Include detailed information

    Returns:
        Formatted string
    """
    lines = []
    lines.append(f"Feature: {status.name}")

    # Status indicators
    def indicator(fs: FileStatus) -> str:
        if not fs.exists:
            return "✗"
        return "✓" if fs.complete else "○"

    lines.append(f"  Spec:   {indicator(status.spec)} {status.spec.details}")
    lines.append(f"  Plan:   {indicator(status.plan)} {status.plan.details}")
    lines.append(f"  Tasks:  {indicator(status.tasks)} {status.tasks.details}")

    # Issues
    if status.waves:
        synced = status.synced_count
        total = len(status.waves)
        lines.append(f"  Issues: {synced}/{total} synced")

        if verbose:
            for wave in status.waves:
                wave_num = wave.name.replace("Wave ", "")
                if wave.issue_number:
                    lines.append(f"    #{wave.issue_number} [Wave {wave_num}] {wave.description}")
                else:
                    lines.append(f"    Wave {wave_num}: Not synced → Run /spec:sync {status.name}")

    return "\n".join(lines)


def format_project_status(project: ProjectStatus) -> str:
    """Format project status for display.

    Args:
        project: ProjectStatus to format

    Returns:
        Formatted string
    """
    lines = []
    lines.append("=== Spec Status ===")
    lines.append("")

    if not project.features:
        lines.append("No features found.")
        lines.append(f"Expected spec directory: {project.spec_dir}")
        return "\n".join(lines)

    for feature in project.features:
        lines.append(format_feature_status(feature))
        lines.append("")

    # Summary
    lines.append("Summary:")
    lines.append(f"  Features: {project.total_features}")
    lines.append(f"  Synced:   {project.total_synced}")
    lines.append(f"  Pending:  {project.total_pending}")

    # Next steps
    pending_features = [f for f in project.features if f.is_ready_to_sync]
    if pending_features:
        lines.append("")
        lines.append("Next steps:")
        for f in pending_features[:3]:  # Show up to 3
            lines.append(f"  - Sync issues for: {f.name}")

    return "\n".join(lines)
