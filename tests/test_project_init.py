"""Characterization and behavioral tests for the deterministic project-init engine."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
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

# Paths corrected for bugs #1477/#1478, rather than placeholder substitutions.
CORRECTED_CONTENT_EXCEPTIONS: dict[str, set[str]] = {
    "python": {"pyproject.toml"},
    "node": set(),
    "go": set(),
    "rust": set(),
}

# Gate condition 1: these named maps enumerate the generated files allowed
# to differ from the pre-fix fixture, by placeholder substitution or bug fix.
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
        elif path in CORRECTED_CONTENT_EXCEPTIONS[framework]:
            assert path == "pyproject.toml"
            corrected = old_content.replace(
                'build-backend = "hatchling.backends"', 'build-backend = "hatchling.build"'
            ).replace("[project.optional-dependencies]", "[dependency-groups]")
            corrected = corrected.replace('    "ruff>=0.4",\n', '    "ruff>=0.4",\n    "mypy>=1.10",\n')
            assert actual_files[path] == corrected
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
    assert project_init.TEMPLATE_CATALOG, "TEMPLATE_CATALOG is empty - this guard would pass vacuously"
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
    assert disk_paths, f"no files found under {TEMPLATE_ROOT} - this guard would pass vacuously"
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


def _generated_project_env(inherited: dict[str, str], tools_dir: Path) -> dict[str, str]:
    """Remove inherited venv tools while keeping ambient tools observable."""
    clean_env = dict(inherited)
    clean_env.pop("VIRTUAL_ENV", None)
    path_parts = []
    for part in inherited.get("PATH", "").split(os.pathsep):
        directory = Path(part or os.curdir).absolute()
        # A finish runner and its worktree can each prepend a different venv.
        # Resolve aliases too: neither spelling may leak the runner's tools.
        if any(
            candidate.name in {"bin", "Scripts"}
            and (candidate.parent / "pyvenv.cfg").is_file()
            for candidate in (directory, directory.resolve())
        ):
            continue
        path_parts.append(str(directory))
    # Explicit empty entries retain the parent cwd; removing every entry
    # must instead leave an empty fixture directory, never implicit cwd.
    tools_dir = tools_dir.absolute()
    tools_dir.mkdir()
    clean_env["PATH"] = os.pathsep.join((str(tools_dir), *path_parts))
    # A required runner may itself be installed in a removed venv. Expose
    # only that executable through a fresh fixture directory, not its peers.
    for tool in ("uv", "make", "git"):
        original = shutil.which(tool, path=inherited.get("PATH"))
        if original and shutil.which(tool, path=clean_env["PATH"]) is None:
            (tools_dir / tool).symlink_to(Path(original).resolve())
    for tool in ("ruff", "pytest", "mypy"):
        assert shutil.which(tool, path=clean_env["PATH"]) is None, (
            f"negative fixture precondition: {tool!r} must not be reachable via "
            "the scrubbed PATH, or this test cannot tell the generated "
            "project's own declared tools from one leaking in ambiently; "
            f"resolved={shutil.which(tool, path=clean_env['PATH'])!r}; "
            f"scrubbed PATH={clean_env['PATH']!r}"
        )
    return clean_env


def test_generated_project_env_removes_nested_venvs_and_bin_alias(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    owned = tmp_path / "owned"
    for venv in (shared, owned):
        (venv / "bin").mkdir(parents=True)
        (venv / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
        for tool in ("ruff", "pytest", "mypy"):
            executable = venv / "bin" / tool
            executable.write_text("fixture", encoding="utf-8")
            executable.chmod(0o755)
    alias = tmp_path / "shared-tools"
    alias.symlink_to(shared / "bin", target_is_directory=True)
    system_bin = tmp_path / "system-bin"
    system_bin.mkdir()
    for tool in ("uv", "make", "git"):
        executable = system_bin / tool
        executable.write_text("fixture", encoding="utf-8")
        executable.chmod(0o755)
    inherited = {
        "VIRTUAL_ENV": str(owned),
        "PATH": os.pathsep.join(map(str, (owned / "bin", shared / "bin", alias, system_bin))),
    }
    assert shutil.which("ruff", path=inherited["PATH"]) == str(owned / "bin" / "ruff")
    clean_env = _generated_project_env(inherited, tmp_path / "required-tools")
    assert "VIRTUAL_ENV" not in clean_env
    assert inherited["VIRTUAL_ENV"] == str(owned)
    assert clean_env["PATH"] == os.pathsep.join((str(tmp_path / "required-tools"), str(system_bin)))
    assert all(shutil.which(tool, path=clean_env["PATH"]) is None for tool in ("ruff", "pytest", "mypy"))
    for tool in ("uv", "make", "git"):
        assert shutil.which(tool, path=clean_env["PATH"]) == str(system_bin / tool)


@pytest.mark.parametrize("required_tool", ("uv", "make", "git"))
def test_generated_project_env_preserves_runner_from_removed_venv(
    tmp_path: Path, required_tool: str,
) -> None:
    shared = tmp_path / "shared"
    (shared / "bin").mkdir(parents=True)
    (shared / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
    for tool in (required_tool, "ruff"):
        executable = shared / "bin" / tool
        executable.write_text("fixture", encoding="utf-8")
        executable.chmod(0o755)
    inherited = {"PATH": str(shared / "bin")}
    assert shutil.which(required_tool, path=inherited["PATH"]) == str(shared / "bin" / required_tool)
    assert shutil.which("ruff", path=inherited["PATH"]) == str(shared / "bin" / "ruff")
    tools_dir = tmp_path / "required-tools"
    clean_env = _generated_project_env(inherited, tools_dir)
    assert shutil.which(required_tool, path=clean_env["PATH"]) == str(tools_dir / required_tool)
    assert (tools_dir / required_tool).resolve() == shared / "bin" / required_tool
    assert shutil.which("ruff", path=clean_env["PATH"]) is None


@pytest.mark.parametrize("path_entry", ("tools", ""))
def test_generated_project_env_keeps_relative_lookup_stable_after_chdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_entry: str,
) -> None:
    runner = tmp_path / "runner"
    (runner / path_entry).mkdir(parents=True)
    target = tmp_path / "generated"
    target.mkdir()
    executable = runner / path_entry / "make"
    executable.write_text("fixture", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.chdir(runner)
    inherited = {"PATH": path_entry}
    assert shutil.which("make", path=path_entry or ".") == f"{path_entry or '.'}/make"
    clean_env = _generated_project_env(inherited, tmp_path / "required-tools")
    before = shutil.which("make", path=clean_env["PATH"])
    monkeypatch.chdir(target)
    assert shutil.which("make", path=clean_env["PATH"]) == before == str(executable)


def test_generated_project_env_does_not_add_cwd_when_all_entries_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared = tmp_path / "shared"
    (shared / "bin").mkdir(parents=True)
    (shared / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
    ambient = tmp_path / "mypy"
    ambient.write_text("fixture", encoding="utf-8")
    ambient.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    inherited = {"PATH": str(shared / "bin")}
    assert shutil.which("mypy", path=inherited["PATH"]) is None
    assert shutil.which("mypy", path=".") == "./mypy"
    tools_dir = tmp_path / "required-tools"
    clean_env = _generated_project_env(inherited, tools_dir)
    assert clean_env["PATH"] == str(tools_dir)
    assert shutil.which("mypy", path=clean_env["PATH"]) is None


@pytest.mark.parametrize("tool", ("ruff", "pytest", "mypy"))
def test_generated_project_env_rejects_ambient_tool(tmp_path: Path, tool: str) -> None:
    ambient_bin = tmp_path / "ambient-bin"
    ambient_bin.mkdir()
    executable = ambient_bin / tool
    executable.write_text("fixture", encoding="utf-8")
    executable.chmod(0o755)
    inherited = {"PATH": str(ambient_bin)}
    assert shutil.which(tool, path=inherited["PATH"]) == str(executable)
    with pytest.raises(AssertionError, match="negative fixture precondition") as failure:
        _generated_project_env(inherited, tmp_path / "required-tools")
    assert str(executable) in str(failure.value)
    expected_path = os.pathsep.join((str(tmp_path / "required-tools"), str(ambient_bin)))
    assert f"scrubbed PATH={expected_path!r}" in str(failure.value)


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not on PATH")
@pytest.mark.skipif(shutil.which("make") is None, reason="make not on PATH")
@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_generated_python_project_really_builds_lints_tests_and_typechecks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Needs network for real uv packages; regression for #1477 and #1478 together.
    from lib.cicd.makefile import generate_makefile

    monkeypatch.setenv("GIT_AUTHOR_NAME", "Project Init Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "project-init@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Project Init Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "project-init@example.com")
    target_dir = tmp_path / "demo-proj"
    assert project_init.main(
        [
            str(SCRIPT),
            "--project-name",
            "demo-proj",
            "--framework",
            "python",
            "--target-dir",
            str(target_dir),
        ]
    ) == 0
    makefile = generate_makefile(target_dir, template_dir=ROOT / "templates" / "makefiles")
    (target_dir / "Makefile").write_text(makefile, encoding="utf-8")
    # The generated project must supply its own declared tools even when
    # a shared finish runner and this worktree both contribute venvs to PATH.
    clean_env = _generated_project_env(dict(os.environ), tmp_path / "required-tools")
    result = subprocess.run(
        ["make", "lint", "test", "typecheck"],
        cwd=target_dir,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
