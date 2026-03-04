"""Tests for lib/spec_bridge/parser.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from lib.spec_bridge.parser import (
    parse_plan,
    parse_spec,
    parse_tasks,
)


class TestParseTasksWaves:
    """Test parse_tasks with wave structure."""

    def test_basic_waves(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        assert len(waves) == 2
        assert waves[0].name == "Wave 1"
        assert waves[0].description == "Core setup"
        assert waves[1].name == "Wave 2"
        assert waves[1].description == "Integration"

    def test_task_count(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        assert len(waves[0].tasks) == 3
        assert len(waves[1].tasks) == 2

    def test_task_ids(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        ids = [t.id for t in waves[0].tasks]
        assert ids == ["T001", "T002", "T003"]

    def test_task_completion(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        assert waves[0].tasks[0].completed is False
        assert waves[0].tasks[1].completed is True  # T002 is [x]

    def test_story_reference(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        assert waves[0].tasks[0].story == "US1"
        assert waves[0].tasks[2].story == "US2"

    def test_file_path_extraction(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        assert waves[0].tasks[0].file_path == "lib/main.py"
        assert waves[0].tasks[1].file_path == "lib/config.py"

    def test_parallelizable_flag(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        assert waves[0].tasks[0].parallelizable is False
        assert waves[0].tasks[2].parallelizable is True  # T003 has [P]

    def test_dependencies(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        t004 = waves[1].tasks[0]
        assert t004.dependencies == ["T001", "T002"]

    def test_checkpoint(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        assert waves[0].checkpoint is not None
        assert "make test" in waves[0].checkpoint

    def test_issue_sync_table(self, tmp_path: Path) -> None:
        """Test issue sync table parsing with proper table format."""
        content = (
            "# Tasks\n\n"
            "## Wave 1: Setup\n\n"
            "- [ ] **T001** [US1] Do something\n\n"
            "## Wave 2: Build\n\n"
            "- [ ] **T002** [US1] Build it\n\n"
            "## Issue Sync\n"
            "| Wave | Description | Issue | Status |\n"
            "|------|-------------|-------|--------|\n"
            "| 1 | Setup | #42 | synced |\n"
            "| 2 | Build | | pending |\n"
        )
        f = tmp_path / "tasks_sync.md"
        f.write_text(content)
        waves = parse_tasks(f)
        assert waves[0].issue_number == 42
        assert waves[1].issue_number is None

    def test_task_wave_assignment(self, sample_tasks_md: Path) -> None:
        waves = parse_tasks(sample_tasks_md)
        for task in waves[0].tasks:
            assert task.wave == "Wave 1"
        for task in waves[1].tasks:
            assert task.wave == "Wave 2"

    def test_task_issue_number_propagation(self, tmp_path: Path) -> None:
        """Test issue number propagation to tasks."""
        content = (
            "# Tasks\n\n"
            "## Wave 1: Setup\n\n"
            "- [ ] **T001** [US1] Do something\n\n"
            "## Wave 2: Build\n\n"
            "- [ ] **T002** [US1] Build it\n\n"
            "## Issue Sync\n"
            "| Wave | Description | Issue | Status |\n"
            "|------|-------------|-------|--------|\n"
            "| 1 | Setup | #42 | synced |\n"
            "| 2 | Build | | pending |\n"
        )
        f = tmp_path / "tasks_prop.md"
        f.write_text(content)
        waves = parse_tasks(f)
        for task in waves[0].tasks:
            assert task.issue_number == 42
        for task in waves[1].tasks:
            assert task.issue_number is None


class TestParseTasksNoWaves:
    """Test parse_tasks with no wave headers."""

    def test_default_wave_created(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
        # Tasks

        - [ ] **T001** [US1] Do something
        - [ ] **T002** [US1] Do another thing
        """)
        f = tmp_path / "tasks.md"
        f.write_text(content)
        waves = parse_tasks(f)
        assert len(waves) == 1
        assert waves[0].name == "Wave 1"
        assert len(waves[0].tasks) == 2


class TestParseTasksEdgeCases:
    """Test edge cases for parse_tasks."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_tasks("/nonexistent/tasks.md")

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "tasks.md"
        f.write_text("")
        waves = parse_tasks(f)
        assert len(waves) == 1  # Default wave
        assert len(waves[0].tasks) == 0


class TestParseSpec:
    """Test parse_spec function."""

    def test_title(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        assert doc.title == "My Feature"

    def test_overview(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        assert "unit testing" in doc.overview

    def test_user_stories(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        assert len(doc.user_stories) == 2
        assert doc.user_stories[0].id == "US1"
        assert doc.user_stories[0].title == "Test Runner"
        assert doc.user_stories[0].priority == "P1"

    def test_user_story_details(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        us1 = doc.user_stories[0]
        assert us1.role == "developer"
        assert "run tests" in us1.capability
        assert "code quality" in us1.benefit

    def test_acceptance_criteria(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        us1 = doc.user_stories[0]
        assert len(us1.acceptance_criteria) == 2
        assert "make test" in us1.acceptance_criteria[0]

    def test_requirements(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        assert len(doc.requirements) == 3
        assert doc.requirements[0].id == "R1"
        assert doc.requirements[0].priority == "Must"
        assert doc.requirements[0].story == "US1"

    def test_edge_cases_section(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        # Parser skips header rows, picks up data rows after separator
        assert "Import errors" in doc.edge_cases
        assert doc.edge_cases["Import errors"] == "Report clearly"

    def test_out_of_scope(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        assert len(doc.out_of_scope) == 2
        assert "Performance benchmarks" in doc.out_of_scope

    def test_success_criteria(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        assert len(doc.success_criteria) == 2

    def test_open_questions(self, sample_spec_md: Path) -> None:
        doc = parse_spec(sample_spec_md)
        assert len(doc.open_questions) == 1

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_spec("/nonexistent/spec.md")


class TestParsePlan:
    """Test parse_plan function."""

    def test_basic_plan(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
        # Implementation Plan: My Feature

        ## Summary

        This plan implements the feature in three phases.
        Phase 1 handles core setup.
        """)
        f = tmp_path / "plan.md"
        f.write_text(content)
        doc = parse_plan(f)
        assert doc.title == "My Feature"
        assert "three phases" in doc.summary

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_plan("/nonexistent/plan.md")
