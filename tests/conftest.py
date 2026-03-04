"""Shared fixtures for CPP unit tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with .gitignore."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        textwrap.dedent("""\
        .env
        .env.*
        *.pem
        *.key
        secrets.*
        *.p12
        .claude/security.yml
        """)
    )
    return tmp_path


@pytest.fixture
def sample_tasks_md(tmp_path: Path) -> Path:
    """Create a sample tasks.md file."""
    content = textwrap.dedent("""\
    # Tasks: My Feature

    > **Plan:** [plan.md](./plan.md)
    > **Created:** 2026-01-01
    > **Status:** Ready

    ---

    ## Wave 1: Core setup

    - [ ] **T001** [US1] Create the main module `lib/main.py`
    - [x] **T002** [US1] Add configuration parsing `lib/config.py`
    - [ ] **T003** [P] [US2] Add parallel task support

    **Checkpoint:** `make test` passes

    ---

    ## Wave 2: Integration

    - [ ] **T004** [US1] Integrate with external API (depends on T001, T002)
    - [ ] **T005** [US2] Add error handling

    **Checkpoint:** Integration tests pass

    ---

    ## Issue Sync
    | Wave | Description | Issue | Status |
    |------|-------------|-------|--------|
    | 1 | Core setup | #42 | synced |
    | 2 | Integration | | pending |
    """)
    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text(content)
    return tasks_file


@pytest.fixture
def sample_spec_md(tmp_path: Path) -> Path:
    """Create a sample spec.md file."""
    content = textwrap.dedent("""\
    # Feature Specification: My Feature

    ## Overview

    This feature adds unit testing support to the project.

    ## User Stories

    ### US1: Test Runner [P1]

    **As a** developer,
    **I want** to run tests easily,
    **So that** I can verify code quality.

    **Acceptance Criteria:**
    - [ ] Tests run with `make test`
    - [ ] Coverage report generated

    ### US2: Test Fixtures [P2]

    **As a** developer,
    **I want** reusable test fixtures,
    **So that** I can write tests faster.

    **Acceptance Criteria:**
    - [ ] Shared conftest.py
    - [ ] Temporary directory fixtures

    ## Requirements

    | ID | Description | Priority | Story |
    |----|-------------|----------|-------|
    | R1 | Tests must run in < 30s | Must | US1 |
    | R2 | Support pytest markers | Should | US1 |
    | R3 | Fixture autodiscovery | Could | US2 |

    ## Edge Cases

    | Scenario | Handling |
    |----------|----------|
    | No tests found | Show warning |
    | Import errors | Report clearly |

    ## Out of Scope

    - Performance benchmarks
    - Browser testing

    ## Success Criteria

    - All tests pass
    - Coverage > 80%

    ## Open Questions

    - Should we require minimum coverage?
    """)
    spec_file = tmp_path / "spec.md"
    spec_file.write_text(content)
    return spec_file
