"""Spec Bridge: Parse spec files and sync tasks to GitHub issues.

This package provides tools for working with GitHub Spec Kit specifications:
- Parse spec.md, plan.md, and tasks.md files
- Extract tasks with IDs, dependencies, and wave assignments
- Sync tasks to GitHub issues via gh CLI
- Check alignment between specs and issues

Quick Start:
    from lib.spec_bridge import parse_tasks, sync_feature

    # Parse tasks from a feature spec
    tasks = parse_tasks(".specify/specs/user-auth/tasks.md")
    for task in tasks:
        print(f"{task.id}: {task.description}")

    # Sync tasks to GitHub issues
    result = sync_feature("user-auth", dry_run=True)
    print(f"Would create {len(result.to_create)} issues")

CLI Usage:
    python -m lib.spec_bridge status           # Show all specs status
    python -m lib.spec_bridge sync user-auth   # Sync feature to issues
    python -m lib.spec_bridge sync --all       # Sync all features

Based on GitHub Spec Kit (MIT License):
https://github.com/github/spec-kit
"""

from .parser import (
    Task,
    Wave,
    SpecDocument,
    parse_tasks,
    parse_spec,
    parse_plan,
)
from .issue_sync import (
    SyncResult,
    sync_feature,
    sync_all_features,
)
from .status import (
    FeatureStatus,
    get_feature_status,
    get_all_status,
)

__all__ = [
    # Parser
    "Task",
    "Wave",
    "SpecDocument",
    "parse_tasks",
    "parse_spec",
    "parse_plan",
    # Sync
    "SyncResult",
    "sync_feature",
    "sync_all_features",
    # Status
    "FeatureStatus",
    "get_feature_status",
    "get_all_status",
]

__version__ = "0.1.0"
