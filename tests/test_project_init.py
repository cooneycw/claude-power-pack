"""Characterization and behavioral tests for the deterministic project-init engine."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "project-init.py"
TEMPLATE_ROOT = ROOT / "templates" / "project-init"

SPEC = importlib.util.spec_from_file_location("project_init", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
project_init = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = project_init
SPEC.loader.exec_module(project_init)

PROJECT_NAME = "sample-app"
PACKAGE_NAME = "sample_app"
MODULE_PATH = "github.com/example/sample-app"

# These are literal pre-fix fixtures transcribed from Step 2 of
# .claude/commands/project/init.md. The placeholder bugs are intentionally
# present here because this data characterizes the source before extraction.
PRE_FIX_FILES: dict[str, dict[str, str]] = {
    "python": {
        "pyproject.toml": '''[project]
name = "sample-app"
version = "0.1.0"
description = ""
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
''',
        "src/sample_app/__init__.py": '''"""$PROJECT_NAME."""

__version__ = "0.1.0"
''',
        "tests/conftest.py": '''"""Shared test fixtures."""
''',
        "tests/test_placeholder.py": '''"""Placeholder test to verify setup."""


def test_import():
    """Verify the package can be imported."""
    import importlib
    mod = importlib.import_module("$PKG_NAME")
    assert hasattr(mod, "__version__")
''',
        ".gitignore": '''__pycache__/
*.py[cod]
.venv/
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
.env
.claude/settings.local.json
''',
    },
    "node": {
        "package.json": '''{
  "name": "sample-app",
  "version": "0.1.0",
  "description": "",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "lint": "eslint src/",
    "test": "vitest run",
    "dev": "tsx watch src/index.ts"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "vitest": "^2.0.0"
  }
}
''',
        "tsconfig.json": '''{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
''',
        "src/index.ts": '''console.log("Hello from $PROJECT_NAME");
''',
        "tests/placeholder.test.ts": '''import { describe, it, expect } from 'vitest';

describe('placeholder', () => {
  it('passes', () => {
    expect(true).toBe(true);
  });
});
''',
        ".gitignore": '''node_modules/
dist/
build/
.next/
coverage/
.env
.claude/settings.local.json
''',
    },
    "go": {
        "go.mod": '''module github.com/example/sample-app

go 1.22
''',
        "cmd/main.go": '''package main

import "fmt"

func main() {
	fmt.Println("Hello from $PROJECT_NAME")
}
''',
        ".gitignore": '''bin/
coverage.out
.env
.claude/settings.local.json
''',
    },
    "rust": {
        "Cargo.toml": '''[package]
name = "sample-app"
version = "0.1.0"
edition = "2021"

[dependencies]
''',
        "src/main.rs": '''fn main() {
    println!("Hello from $PROJECT_NAME");
}
''',
        ".gitignore": '''target/
.env
.claude/settings.local.json
''',
    },
}

# Gate condition 1: this literal, named map is the complete and only set of
# generated files allowed to differ from the pre-fix fixture.
PLACEHOLDER_CONTENT_EXCEPTIONS: dict[str, set[str]] = {
    "python": {"src/sample_app/__init__.py", "tests/test_placeholder.py"},
    "node": {"src/index.ts"},
    "go": {"cmd/main.go"},
    "rust": {"src/main.rs"},
}

RESOLVED_VALUE_BY_EXCEPTION: dict[str, dict[str, str]] = {
    "python": {
        "src/sample_app/__init__.py": PROJECT_NAME,
        "tests/test_placeholder.py": PACKAGE_NAME,
    },
    "node": {"src/index.ts": PROJECT_NAME},
    "go": {"cmd/main.go": PROJECT_NAME},
    "rust": {"src/main.rs": PROJECT_NAME},
}

PRE_FIX_COMMANDS: dict[str, list[dict[str, Any]]] = {
    "python": [
        {"step_id": "dependencies_synchronized", "argv": ["uv", "sync"]},
        {"step_id": "git_initialized", "argv": ["git", "init"]},
        {"step_id": "scaffold_staged", "argv": ["git", "add", "."]},
        {
            "step_id": "initial_commit_created",
            "argv": ["git", "commit", "-m", project_init.INITIAL_COMMIT_MESSAGE],
        },
    ],
    "node": [
        {"step_id": "dependencies_synchronized", "argv": ["npm", "install"]},
        {"step_id": "git_initialized", "argv": ["git", "init"]},
        {"step_id": "scaffold_staged", "argv": ["git", "add", "."]},
        {
            "step_id": "initial_commit_created",
            "argv": ["git", "commit", "-m", project_init.INITIAL_COMMIT_MESSAGE],
        },
    ],
    "go": [
        {"step_id": "git_initialized", "argv": ["git", "init"]},
        {"step_id": "scaffold_staged", "argv": ["git", "add", "."]},
        {
            "step_id": "initial_commit_created",
            "argv": ["git", "commit", "-m", project_init.INITIAL_COMMIT_MESSAGE],
        },
    ],
    "rust": [
        {"step_id": "git_initialized", "argv": ["git", "init"]},
        {"step_id": "scaffold_staged", "argv": ["git", "add", "."]},
        {
            "step_id": "initial_commit_created",
            "argv": ["git", "commit", "-m", project_init.INITIAL_COMMIT_MESSAGE],
        },
    ],
}

# Gate condition 1: git initialization is the only command data allowed to
# differ from the pre-fix command fixture for every framework.
COMMAND_DATA_EXCEPTIONS: dict[str, set[str]] = {
    "python": {"git_initialized"},
    "node": {"git_initialized"},
    "go": {"git_initialized"},
    "rust": {"git_initialized"},
}


class RecordingExecutor:
    """Record proposed command data without invoking a real binary."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[tuple[Any, Path]] = []

    def run(self, command: Any, cwd: Path) -> None:
        self.calls.append((command, cwd))
        if command.step_id == self.fail_on:
            raise RuntimeError(f"injected failure at {command.step_id}")


def make_input(framework: str, target_dir: Path) -> Any:
    return project_init.ProjectInitInput(
        project_name=PROJECT_NAME,
        framework=framework,
        target_dir=target_dir,
        module_path=MODULE_PATH if framework == "go" else None,
    )


@pytest.mark.parametrize("framework", ["python", "node", "go", "rust"])
def test_scaffold_characterization_has_only_enumerated_content_and_command_fixes(
    framework: str,
    tmp_path: Path,
) -> None:
    init_plan = project_init.plan(make_input(framework, tmp_path / framework))
    actual_files = {write.path: write.content for write in init_plan.writes}
    expected_files = PRE_FIX_FILES[framework]
    content_exceptions = PLACEHOLDER_CONTENT_EXCEPTIONS[framework]

    assert set(actual_files) == set(expected_files)
    assert set(RESOLVED_VALUE_BY_EXCEPTION[framework]) == content_exceptions
    for path, old_content in expected_files.items():
        if path in content_exceptions:
            assert actual_files[path] != old_content
            assert "$PROJECT_NAME" not in actual_files[path]
            assert "$PKG_NAME" not in actual_files[path]
            assert RESOLVED_VALUE_BY_EXCEPTION[framework][path] in actual_files[path]
        else:
            assert actual_files[path] == old_content

    actual_commands = [command.to_dict() for command in init_plan.commands]
    expected_commands = PRE_FIX_COMMANDS[framework]
    command_exceptions = COMMAND_DATA_EXCEPTIONS[framework]
    assert [command["step_id"] for command in actual_commands] == [
        command["step_id"] for command in expected_commands
    ]
    for actual, old in zip(actual_commands, expected_commands, strict=True):
        if actual["step_id"] in command_exceptions:
            assert actual != old
            assert old["argv"] == ["git", "init"]
            assert actual["argv"] == ["git", "init", "-b", "main"]
        else:
            assert actual == old


@pytest.mark.parametrize("framework", ["python", "node", "go", "rust"])
def test_plan_data_pins_git_command_and_init_add_commit_order(framework: str, tmp_path: Path) -> None:
    init_plan = project_init.plan(make_input(framework, tmp_path / framework))
    commands = [command.to_dict() for command in init_plan.commands]
    by_step = {command["step_id"]: command for command in commands}

    assert by_step["git_initialized"] == {
        "step_id": "git_initialized",
        "argv": ["git", "init", "-b", "main"],
    }
    step_order = [command["step_id"] for command in commands]
    assert step_order.index("git_initialized") < step_order.index("scaffold_staged")
    assert step_order.index("scaffold_staged") < step_order.index("initial_commit_created")


@pytest.mark.parametrize("framework", ["python", "node", "go", "rust"])
def test_original_placeholder_and_branch_mutations_are_detected(framework: str, tmp_path: Path) -> None:
    """Mutation-prove that restoring either live bug makes the fixed assertions fail."""
    init_plan = project_init.plan(make_input(framework, tmp_path / framework))
    actual_files = {write.path: write.content for write in init_plan.writes}

    for path in PLACEHOLDER_CONTENT_EXCEPTIONS[framework]:
        with pytest.raises(AssertionError):
            assert actual_files[path] == PRE_FIX_FILES[framework][path]

    actual_git = next(command for command in init_plan.commands if command.step_id == "git_initialized")
    with pytest.raises(AssertionError):
        assert list(actual_git.argv) == ["git", "init"]


def test_checked_in_templates_match_the_standalone_catalog() -> None:
    catalog_paths = set()
    for template in project_init.TEMPLATE_CATALOG:
        path = TEMPLATE_ROOT / template.framework / template.template_path
        catalog_paths.add(path.relative_to(TEMPLATE_ROOT).as_posix())
        assert path.read_text(encoding="utf-8") == template.content

    disk_paths = {
        path.relative_to(TEMPLATE_ROOT).as_posix()
        for path in TEMPLATE_ROOT.rglob("*")
        if path.is_file() and ".ruff_cache" not in path.relative_to(TEMPLATE_ROOT).parts
    }
    assert disk_paths == catalog_paths


def test_plan_is_byte_deterministic_and_contains_only_resolved_values(tmp_path: Path) -> None:
    target = tmp_path / "same-target"
    first = project_init.plan(make_input("python", target))
    second = project_init.plan(make_input("python", target))

    assert first == second
    assert first.fingerprint == second.fingerprint
    assert first.to_json() == second.to_json()
    assert all("$PROJECT_NAME" not in write.content for write in first.writes)
    assert all("$PKG_NAME" not in write.content for write in first.writes)


@pytest.mark.parametrize(
    ("project_name", "framework", "module_path", "message"),
    [
        ("Bad_Name", "python", None, "project_name"),
        ("sample-app", "ruby", None, "framework"),
        ("sample-app", "go", None, "module_path"),
        ("sample-app", "python", MODULE_PATH, "only for Go"),
    ],
)
def test_project_input_validation(
    project_name: str,
    framework: str,
    module_path: str | None,
    message: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(project_init.InputValidationError, match=message):
        project_init.plan(
            project_init.ProjectInitInput(project_name, framework, tmp_path / "target", module_path)
        )


def test_relative_target_is_rejected() -> None:
    with pytest.raises(project_init.InputValidationError, match="absolute"):
        project_init.plan(project_init.ProjectInitInput(PROJECT_NAME, "rust", Path("relative")))


def test_dry_run_is_idempotent_and_leaves_empty_target_empty(tmp_path: Path, capsys: Any) -> None:
    target = tmp_path / "empty-target"
    target.mkdir()
    assert not any(target.iterdir()), "negative fixture precondition: dry-run target must start empty"

    argv = [
        str(SCRIPT),
        "--project-name",
        PROJECT_NAME,
        "--framework",
        "rust",
        "--target-dir",
        str(target),
        "--dry-run",
    ]
    assert project_init.main(argv) == 0
    first = capsys.readouterr().out
    assert not any(target.iterdir())

    assert not any(target.iterdir()), "negative fixture precondition: repeated dry-run target must stay empty"
    assert project_init.main(argv) == 0
    second = capsys.readouterr().out
    assert not any(target.iterdir())
    assert first == second
    assert json.loads(first)["fingerprint"]


def test_apply_uses_fake_executor_and_completed_resume_runs_nothing(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_plan = project_init.plan(make_input("node", target))
    checkpoint_path = project_init.default_checkpoint_path(target)
    first_executor = RecordingExecutor()

    checkpoint = project_init.apply(init_plan, checkpoint_path, first_executor)

    assert [call[0] for call in first_executor.calls] == list(init_plan.commands)
    assert all(call[1] == target for call in first_executor.calls)
    assert checkpoint.completed_steps == init_plan.step_ids
    for write in init_plan.writes:
        assert (target / write.path).read_text(encoding="utf-8") == write.content

    checkpoint_json = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint_json["schema_version"] == project_init.CHECKPOINT_SCHEMA_VERSION
    assert checkpoint_json["fingerprint"] == init_plan.fingerprint
    assert checkpoint_json["completed_steps"] == list(init_plan.step_ids)
    assert checkpoint_json["plan_step_ids"] == list(init_plan.step_ids)
    assert all(not step_id.startswith("step_") for step_id in checkpoint_json["completed_steps"])

    resumed_executor = RecordingExecutor()
    resumed = project_init.apply(init_plan, checkpoint_path, resumed_executor, resume=True)
    assert resumed.completed_steps == init_plan.step_ids
    assert resumed_executor.calls == []


def test_partial_resume_invokes_only_remaining_proposed_commands(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_plan = project_init.plan(make_input("rust", target))
    checkpoint_path = project_init.default_checkpoint_path(target)
    failing_executor = RecordingExecutor(fail_on="scaffold_staged")

    with pytest.raises(project_init.ApplyError, match="scaffold_staged"):
        project_init.apply(init_plan, checkpoint_path, failing_executor)

    assert [call[0].step_id for call in failing_executor.calls] == ["git_initialized", "scaffold_staged"]
    partial = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert partial["completed_steps"] == ["scaffold_files_written", "git_initialized"]

    resumed_executor = RecordingExecutor()
    checkpoint = project_init.apply(init_plan, checkpoint_path, resumed_executor, resume=True)
    assert [call[0].step_id for call in resumed_executor.calls] == [
        "scaffold_staged",
        "initial_commit_created",
    ]
    assert checkpoint.completed_steps == init_plan.step_ids


def test_resume_revalidates_completed_scaffold_files(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_plan = project_init.plan(make_input("go", target))
    checkpoint_path = project_init.default_checkpoint_path(target)
    project_init.apply(init_plan, checkpoint_path, RecordingExecutor())
    changed = target / "cmd" / "main.go"
    changed.write_text("changed\n", encoding="utf-8")

    with pytest.raises(project_init.CheckpointError, match="filesystem mismatch"):
        project_init.apply(init_plan, checkpoint_path, RecordingExecutor(), resume=True)


def test_cli_refuses_schema_and_fingerprint_mismatches_with_distinct_stderr(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "project"
    init_plan = project_init.plan(make_input("rust", target))
    checkpoint_path = project_init.default_checkpoint_path(target)
    project_init.apply(init_plan, checkpoint_path, RecordingExecutor())
    monkeypatch.setattr(project_init, "SubprocessExecutor", RecordingExecutor)
    argv = [
        str(SCRIPT),
        "--project-name",
        PROJECT_NAME,
        "--framework",
        "rust",
        "--target-dir",
        str(target),
        "--resume",
    ]

    raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    raw["schema_version"] = project_init.CHECKPOINT_SCHEMA_VERSION + 1
    checkpoint_path.write_text(json.dumps(raw), encoding="utf-8")
    assert project_init.main(argv) == 1
    schema_error = capsys.readouterr().err
    assert "schema_version mismatch" in schema_error
    assert "fingerprint mismatch" not in schema_error

    raw["schema_version"] = project_init.CHECKPOINT_SCHEMA_VERSION
    raw["fingerprint"] = "wrong-fingerprint"
    checkpoint_path.write_text(json.dumps(raw), encoding="utf-8")
    assert project_init.main(argv) == 1
    fingerprint_error = capsys.readouterr().err
    assert "fingerprint mismatch" in fingerprint_error
    assert "schema_version mismatch" not in fingerprint_error


def test_renamed_semantic_step_invalidates_resume_even_with_current_fingerprint(tmp_path: Path) -> None:
    target = tmp_path / "project"
    original = project_init.plan(make_input("rust", target))
    checkpoint_path = project_init.default_checkpoint_path(target)
    project_init.apply(original, checkpoint_path, RecordingExecutor())

    renamed_commands = (
        project_init.PlannedCommand("repository_initialized", original.commands[0].argv),
        *original.commands[1:],
    )
    renamed = project_init.Plan.create(original.project, original.writes, renamed_commands)
    raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    raw["fingerprint"] = renamed.fingerprint
    checkpoint_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(project_init.CheckpointError, match="semantic step layout mismatch"):
        project_init.apply(renamed, checkpoint_path, RecordingExecutor(), resume=True)


def test_reordered_semantic_steps_invalidate_resume_loudly(tmp_path: Path) -> None:
    target = tmp_path / "project"
    original = project_init.plan(make_input("rust", target))
    checkpoint_path = project_init.default_checkpoint_path(target)
    project_init.apply(original, checkpoint_path, RecordingExecutor())
    reordered = project_init.Plan.create(
        original.project,
        original.writes,
        (original.commands[1], original.commands[0], original.commands[2]),
    )

    with pytest.raises(project_init.CheckpointError, match="fingerprint mismatch"):
        project_init.apply(reordered, checkpoint_path, RecordingExecutor(), resume=True)


def test_ordinal_or_unknown_completed_step_name_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "project"
    init_plan = project_init.plan(make_input("rust", target))
    checkpoint_path = project_init.default_checkpoint_path(target)
    project_init.apply(init_plan, checkpoint_path, RecordingExecutor())
    raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    raw["completed_steps"] = ["scaffold_files_written", "step_1"]
    checkpoint_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(project_init.CheckpointError, match="completed_steps mismatch"):
        project_init.apply(init_plan, checkpoint_path, RecordingExecutor(), resume=True)
