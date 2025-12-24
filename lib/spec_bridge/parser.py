"""Parse spec, plan, and tasks markdown files.

Extracts structured data from GitHub Spec Kit format files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Task:
    """A single task from tasks.md."""

    id: str  # e.g., "T001"
    description: str
    story: str  # e.g., "US1"
    file_path: Optional[str] = None  # e.g., "lib/auth.py"
    dependencies: list[str] = field(default_factory=list)  # e.g., ["T001", "T002"]
    parallelizable: bool = False
    completed: bool = False
    wave: Optional[str] = None  # e.g., "Wave 1"
    issue_number: Optional[int] = None


@dataclass
class Wave:
    """A wave/phase grouping of tasks."""

    name: str  # e.g., "Wave 1: Core Implementation"
    description: str  # e.g., "Core Implementation"
    tasks: list[Task] = field(default_factory=list)
    checkpoint: Optional[str] = None
    issue_number: Optional[int] = None


@dataclass
class UserStory:
    """A user story from spec.md."""

    id: str  # e.g., "US1"
    title: str
    role: str
    capability: str
    benefit: str
    priority: str  # e.g., "P1", "P2"
    acceptance_criteria: list[str] = field(default_factory=list)
    test_scenarios: list[str] = field(default_factory=list)


@dataclass
class Requirement:
    """A requirement from spec.md."""

    id: str  # e.g., "R1"
    description: str
    priority: str  # Must, Should, Could
    story: Optional[str] = None  # Link to user story


@dataclass
class SpecDocument:
    """Parsed spec.md document."""

    title: str
    overview: str
    user_stories: list[UserStory] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    edge_cases: dict[str, str] = field(default_factory=dict)
    out_of_scope: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class PlanDocument:
    """Parsed plan.md document."""

    title: str
    summary: str
    tech_context: dict[str, str] = field(default_factory=dict)
    architecture: str = ""
    dependencies: list[dict[str, str]] = field(default_factory=list)
    risks: list[dict[str, str]] = field(default_factory=list)


# Task parsing patterns
TASK_PATTERN = re.compile(
    r"^-\s*\[(?P<done>[xX ])?\]\s*"  # Checkbox
    r"\*\*(?P<id>T\d+)\*\*\s*"  # Task ID
    r"(?:\[P\]\s*)?"  # Optional [P] for parallelizable
    r"\[(?P<story>US\d+(?:,\s*US\d+)*)\]\s*"  # User story reference(s)
    r"(?P<desc>.+?)"  # Description
    r"(?:\s*`(?P<file>[^`]+)`)?$",  # Optional file path
    re.MULTILINE,
)

TASK_PATTERN_ALT = re.compile(
    r"^-\s*\[(?P<done>[xX ])?\]\s*"  # Checkbox
    r"\*\*(?P<id>T\d+)\*\*\s*"  # Task ID
    r"(?P<parallel>\[P\]\s*)?"  # Optional [P] for parallelizable
    r"(?:\[(?P<story>US\d+(?:,\s*US\d+)*)\]\s*)?"  # Optional story reference
    r"(?P<desc>.+?)$",  # Description (rest of line)
    re.MULTILINE,
)

WAVE_PATTERN = re.compile(
    r"^##\s*Wave\s*(\d+)(?:\s*:\s*(.+))?$",
    re.MULTILINE | re.IGNORECASE,
)

DEPENDENCY_PATTERN = re.compile(
    r"\(depends\s+on\s+(?P<deps>T\d+(?:,\s*T\d+)*)\)",
    re.IGNORECASE,
)

CHECKPOINT_PATTERN = re.compile(
    r"\*\*Checkpoint:\*\*\s*(.+)$",
    re.MULTILINE,
)

ISSUE_SYNC_PATTERN = re.compile(
    r"\|\s*(?:Wave\s*)?(\d+)\s*\|\s*([^|]+)\s*\|\s*#?(\d+)?\s*\|\s*(\w+)\s*\|",
)


def parse_tasks(path: Path | str) -> list[Wave]:
    """Parse tasks.md file into structured waves and tasks.

    Args:
        path: Path to tasks.md file

    Returns:
        List of Wave objects containing tasks
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Tasks file not found: {path}")

    content = path.read_text()
    waves: list[Wave] = []
    current_wave: Optional[Wave] = None

    # First, find all wave sections
    wave_matches = list(WAVE_PATTERN.finditer(content))

    if not wave_matches:
        # No waves found, create a default wave
        current_wave = Wave(name="Wave 1", description="Default")
        waves.append(current_wave)
        _parse_tasks_in_section(content, current_wave)
    else:
        for i, match in enumerate(wave_matches):
            wave_num = match.group(1)
            wave_desc = match.group(2) or f"Wave {wave_num}"

            # Get content until next wave or end
            start = match.end()
            end = wave_matches[i + 1].start() if i + 1 < len(wave_matches) else len(content)
            section_content = content[start:end]

            current_wave = Wave(name=f"Wave {wave_num}", description=wave_desc.strip())
            waves.append(current_wave)

            _parse_tasks_in_section(section_content, current_wave)

            # Check for checkpoint
            checkpoint_match = CHECKPOINT_PATTERN.search(section_content)
            if checkpoint_match:
                current_wave.checkpoint = checkpoint_match.group(1).strip()

    # Parse issue sync table for issue numbers
    _parse_issue_sync_table(content, waves)

    return waves


def _parse_tasks_in_section(content: str, wave: Wave) -> None:
    """Parse tasks from a section of content into a wave."""
    for line in content.split("\n"):
        line = line.strip()
        if not line.startswith("- ["):
            continue

        # Try main pattern first
        match = TASK_PATTERN_ALT.match(line)
        if not match:
            continue

        task_id = match.group("id")
        story = match.group("story") or "US1"
        desc = match.group("desc").strip()
        parallelizable = bool(match.group("parallel"))
        completed = match.group("done") in ("x", "X")

        # Extract file path from description
        file_path = None
        file_match = re.search(r"`([^`]+)`", desc)
        if file_match:
            file_path = file_match.group(1)
            desc = re.sub(r"\s*`[^`]+`\s*", " ", desc).strip()

        # Extract dependencies
        dependencies = []
        dep_match = DEPENDENCY_PATTERN.search(desc)
        if dep_match:
            dep_str = dep_match.group("deps")
            dependencies = [d.strip() for d in dep_str.split(",")]
            desc = DEPENDENCY_PATTERN.sub("", desc).strip()

        task = Task(
            id=task_id,
            description=desc,
            story=story,
            file_path=file_path,
            dependencies=dependencies,
            parallelizable=parallelizable,
            completed=completed,
            wave=wave.name,
        )
        wave.tasks.append(task)


def _parse_issue_sync_table(content: str, waves: list[Wave]) -> None:
    """Parse the issue sync table to get issue numbers."""
    # Look for Issue Sync section
    sync_section = re.search(
        r"##\s*Issue\s*Sync.*?\n((?:\|.*\n)+)",
        content,
        re.IGNORECASE,
    )
    if not sync_section:
        return

    table_content = sync_section.group(1)
    for match in ISSUE_SYNC_PATTERN.finditer(table_content):
        wave_num = match.group(1)
        issue_num = match.group(3)

        if issue_num:
            # Find matching wave and set issue number
            for wave in waves:
                if wave.name == f"Wave {wave_num}":
                    wave.issue_number = int(issue_num)
                    # Also set on tasks
                    for task in wave.tasks:
                        task.issue_number = int(issue_num)
                    break


def parse_spec(path: Path | str) -> SpecDocument:
    """Parse spec.md file into structured document.

    Args:
        path: Path to spec.md file

    Returns:
        SpecDocument with parsed content
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")

    content = path.read_text()

    # Extract title
    title_match = re.search(r"^#\s+(?:Feature\s+Specification:\s*)?(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Unknown"

    # Extract overview
    overview_match = re.search(
        r"##\s*Overview\s*\n+(.+?)(?=\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    overview = overview_match.group(1).strip() if overview_match else ""

    # Parse user stories
    user_stories = _parse_user_stories(content)

    # Parse requirements table
    requirements = _parse_requirements(content)

    # Parse edge cases
    edge_cases = _parse_edge_cases(content)

    # Parse out of scope
    out_of_scope = _parse_list_section(content, "Out of Scope")

    # Parse success criteria
    success_criteria = _parse_list_section(content, "Success Criteria")

    # Parse open questions
    open_questions = _parse_list_section(content, "Open Questions")

    return SpecDocument(
        title=title,
        overview=overview,
        user_stories=user_stories,
        requirements=requirements,
        edge_cases=edge_cases,
        out_of_scope=out_of_scope,
        success_criteria=success_criteria,
        open_questions=open_questions,
    )


def _parse_user_stories(content: str) -> list[UserStory]:
    """Parse user stories from spec content."""
    stories = []

    # Pattern for user story headers
    story_pattern = re.compile(
        r"###\s*(US\d+):\s*(.+?)(?:\s*\[(P\d+)\])?\s*\n",
        re.MULTILINE,
    )

    for match in story_pattern.finditer(content):
        story_id = match.group(1)
        title = match.group(2).strip()
        priority = match.group(3) or "P2"

        # Find the story section content
        start = match.end()
        next_match = story_pattern.search(content, start)
        end = next_match.start() if next_match else len(content)
        section = content[start:end]

        # Parse As a/I want/So that
        role_match = re.search(r"\*\*As a\*\*\s*(.+?),", section)
        want_match = re.search(r"\*\*I want\*\*\s*(.+?),", section)
        benefit_match = re.search(r"\*\*So that\*\*\s*(.+?)\.", section)

        # Parse acceptance criteria
        criteria = []
        criteria_section = re.search(
            r"\*\*Acceptance Criteria:\*\*\s*\n((?:-\s*\[.\].*\n?)+)",
            section,
        )
        if criteria_section:
            for line in criteria_section.group(1).split("\n"):
                if line.strip().startswith("- ["):
                    criteria.append(re.sub(r"^-\s*\[.\]\s*", "", line.strip()))

        story = UserStory(
            id=story_id,
            title=title,
            role=role_match.group(1).strip() if role_match else "",
            capability=want_match.group(1).strip() if want_match else "",
            benefit=benefit_match.group(1).strip() if benefit_match else "",
            priority=priority,
            acceptance_criteria=criteria,
        )
        stories.append(story)

    return stories


def _parse_requirements(content: str) -> list[Requirement]:
    """Parse requirements table from spec content."""
    requirements = []

    # Find requirements table
    table_pattern = re.compile(
        r"\|\s*(R\d+)\s*\|\s*(.+?)\s*\|\s*(Must|Should|Could)\s*\|\s*(US\d+)?\s*\|",
    )

    for match in table_pattern.finditer(content):
        req = Requirement(
            id=match.group(1),
            description=match.group(2).strip(),
            priority=match.group(3),
            story=match.group(4),
        )
        requirements.append(req)

    return requirements


def _parse_edge_cases(content: str) -> dict[str, str]:
    """Parse edge cases table from spec content."""
    edge_cases = {}

    # Find edge cases section
    section_match = re.search(
        r"##\s*Edge Cases\s*\n((?:\|.*\n)+)",
        content,
        re.IGNORECASE,
    )
    if not section_match:
        return edge_cases

    table_content = section_match.group(1)
    # Skip header rows
    rows = [r for r in table_content.split("\n") if r.strip() and not r.strip().startswith("|--")]

    for row in rows[2:]:  # Skip header and separator
        cols = [c.strip() for c in row.split("|") if c.strip()]
        if len(cols) >= 2:
            edge_cases[cols[0]] = cols[1]

    return edge_cases


def _parse_list_section(content: str, section_name: str) -> list[str]:
    """Parse a bulleted list section."""
    items = []

    section_match = re.search(
        rf"##\s*{section_name}\s*\n((?:-\s*.+\n?)+)",
        content,
        re.IGNORECASE,
    )
    if section_match:
        for line in section_match.group(1).split("\n"):
            line = line.strip()
            if line.startswith("- "):
                # Remove checkbox if present
                item = re.sub(r"^-\s*\[.\]\s*", "- ", line)
                items.append(item[2:].strip())

    return items


def parse_plan(path: Path | str) -> PlanDocument:
    """Parse plan.md file into structured document.

    Args:
        path: Path to plan.md file

    Returns:
        PlanDocument with parsed content
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Plan file not found: {path}")

    content = path.read_text()

    # Extract title
    title_match = re.search(r"^#\s+(?:Implementation Plan:\s*)?(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Unknown"

    # Extract summary
    summary_match = re.search(
        r"##\s*Summary\s*\n+(.+?)(?=\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    summary = summary_match.group(1).strip() if summary_match else ""

    return PlanDocument(
        title=title,
        summary=summary,
    )
