"""Tests for lib/spec_bridge/status.py."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.spec_bridge.status import (
    FeatureStatus,
    FileStatus,
    ProjectStatus,
    format_feature_status,
    format_project_status,
    get_all_status,
    get_feature_status,
)


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    """Create a .specify/specs directory with a sample feature."""
    specs = tmp_path / ".specify" / "specs"
    feature = specs / "my-feature"
    feature.mkdir(parents=True)

    # spec.md
    (feature / "spec.md").write_text(
        textwrap.dedent("""\
        # Feature Specification: My Feature

        ## Overview

        A sample feature for testing.

        ## User Stories

        ### US1: Basic [P1]

        **As a** user,
        **I want** something,
        **So that** I benefit.

        **Acceptance Criteria:**
        - [ ] It works

        ## Requirements

        | ID | Description | Priority | Story |
        |----|-------------|----------|-------|
        | R1 | It must work | Must | US1 |
        """)
    )

    # plan.md
    (feature / "plan.md").write_text(
        textwrap.dedent("""\
        # Implementation Plan: My Feature

        ## Summary

        Simple implementation plan.
        """)
    )

    # tasks.md — issue sync table must immediately follow header (no blank line)
    (feature / "tasks.md").write_text(
        "# Tasks: My Feature\n\n"
        "## Wave 1: Setup\n\n"
        "- [ ] **T001** [US1] Do something\n\n"
        "## Wave 2: Build\n\n"
        "- [ ] **T002** [US1] Build it\n\n"
        "## Issue Sync\n"
        "| Wave | Description | Issue | Status |\n"
        "|------|-------------|-------|--------|\n"
        "| 1 | Setup | #10 | synced |\n"
        "| 2 | Build | | pending |\n"
    )

    return specs


class TestFileStatus:
    """Test FileStatus dataclass."""

    def test_defaults(self) -> None:
        fs = FileStatus()
        assert fs.exists is False
        assert fs.complete is False
        assert fs.item_count == 0
        assert fs.details == ""


class TestFeatureStatus:
    """Test FeatureStatus dataclass."""

    def test_is_ready_to_sync_true(self) -> None:
        status = FeatureStatus(
            name="test",
            path=Path("test"),
            tasks=FileStatus(exists=True, item_count=3),
            pending_count=2,
        )
        assert status.is_ready_to_sync is True

    def test_is_ready_to_sync_false_no_tasks(self) -> None:
        status = FeatureStatus(
            name="test",
            path=Path("test"),
            tasks=FileStatus(exists=False),
            pending_count=2,
        )
        assert status.is_ready_to_sync is False

    def test_is_ready_to_sync_false_no_pending(self) -> None:
        status = FeatureStatus(
            name="test",
            path=Path("test"),
            tasks=FileStatus(exists=True, item_count=3),
            pending_count=0,
        )
        assert status.is_ready_to_sync is False


class TestGetFeatureStatus:
    """Test get_feature_status function."""

    @patch("lib.spec_bridge.status.list_issues", return_value=[])
    def test_complete_feature(self, mock_issues, spec_dir: Path) -> None:
        status = get_feature_status("my-feature", spec_dir)
        assert status.name == "my-feature"
        assert status.spec.exists is True
        assert status.spec.complete is True
        assert status.plan.exists is True
        assert status.plan.complete is True
        assert status.tasks.exists is True
        assert status.tasks.complete is True

    @patch("lib.spec_bridge.status.list_issues", return_value=[])
    def test_synced_count(self, mock_issues, spec_dir: Path) -> None:
        status = get_feature_status("my-feature", spec_dir)
        assert status.synced_count == 1
        assert status.pending_count == 1

    @patch("lib.spec_bridge.status.list_issues", return_value=[])
    def test_missing_feature(self, mock_issues, spec_dir: Path) -> None:
        status = get_feature_status("nonexistent", spec_dir)
        assert status.spec.exists is False
        assert status.plan.exists is False
        assert status.tasks.exists is False


class TestGetAllStatus:
    """Test get_all_status function."""

    @patch("lib.spec_bridge.status.list_issues", return_value=[])
    def test_finds_features(self, mock_issues, spec_dir: Path) -> None:
        project = get_all_status(spec_dir)
        assert project.total_features == 1
        assert len(project.features) == 1
        assert project.features[0].name == "my-feature"

    @patch("lib.spec_bridge.status.list_issues", return_value=[])
    def test_aggregate_counts(self, mock_issues, spec_dir: Path) -> None:
        project = get_all_status(spec_dir)
        assert project.total_synced == 1
        assert project.total_pending == 1

    def test_missing_spec_dir(self, tmp_path: Path) -> None:
        project = get_all_status(tmp_path / "nonexistent")
        assert project.total_features == 0
        assert len(project.features) == 0


class TestFormatting:
    """Test format functions."""

    def test_format_feature_status(self) -> None:
        status = FeatureStatus(
            name="test-feature",
            path=Path("test"),
            spec=FileStatus(exists=True, complete=True, details="1 user stories"),
            plan=FileStatus(exists=True, complete=True, details="Complete"),
            tasks=FileStatus(exists=True, complete=True, item_count=3, details="3 tasks"),
        )
        output = format_feature_status(status)
        assert "test-feature" in output
        assert "1 user stories" in output

    def test_format_project_status_empty(self) -> None:
        project = ProjectStatus(spec_dir=Path("test"))
        output = format_project_status(project)
        assert "No features found" in output

    @patch("lib.spec_bridge.status.list_issues", return_value=[])
    def test_format_project_status_with_features(self, mock_issues, spec_dir: Path) -> None:
        project = get_all_status(spec_dir)
        output = format_project_status(project)
        assert "my-feature" in output
        assert "Summary:" in output
