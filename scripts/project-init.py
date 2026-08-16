#!/usr/bin/env python3
"""project-init.py - Deterministic scaffold planning and application (issue #721).

The pure ``plan(ProjectInitInput)`` interface resolves one of the checked-in
Python, Node, Go, or Rust template catalogs into immutable proposed file writes
and structured commands. ``apply`` performs that plan through an injectable
executor and records completed semantic step names after every successful step.

The default checkpoint is stored inside the target project at
``.claude/project-init-checkpoint.json``. Checkpoint writes use a temporary
sibling plus ``os.replace``. Concurrent applies are serialized with an flock
file under ``$XDG_RUNTIME_DIR/cpp-project-init-locks`` so the lock itself is not
staged by the planned ``git add .`` command. The checkpoint is temporarily
removed while that command runs and immediately restored, keeping resumable
state out of the initial commit.

Exit codes: 0 success, 1 apply/checkpoint refusal, 2 usage/input validation
error. Dry-run prints the plan as deterministic JSON and performs no writes or
commands.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from string import Template
from typing import Any, Literal, Protocol, cast

PLAN_SCHEMA_VERSION = 1
CHECKPOINT_SCHEMA_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10.0
PROJECT_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
FRAMEWORKS = ("python", "node", "go", "rust")
Framework = Literal["python", "node", "go", "rust"]

INITIAL_COMMIT_MESSAGE = (
    "Initial project scaffold\n\n"
    "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
)

USAGE = """usage: project-init.py --project-name NAME --framework FRAMEWORK --target-dir PATH [options]
  --module-path PATH       required for Go projects
  --checkpoint-path PATH   default: TARGET/.claude/project-init-checkpoint.json
  --dry-run                print the deterministic plan; do not mutate
  --resume                 validate and continue an existing checkpoint

  frameworks: python, node, go, rust
  exit: 0 success, 1 apply/checkpoint refusal, 2 usage/input error
"""


class ProjectInitError(Exception):
    """Base class for expected project initialization failures."""


class InputValidationError(ProjectInitError):
    """The requested project inputs are invalid."""


class CheckpointError(ProjectInitError):
    """Checkpoint state cannot safely resume the current plan."""


class ApplyError(ProjectInitError):
    """A planned write or command could not be applied."""


@dataclass(frozen=True)
class ProjectInitInput:
    """Caller-supplied values required to resolve a project plan."""

    project_name: str
    framework: str
    target_dir: Path
    module_path: str | None = None

    def resolve(self) -> ResolvedProjectInput:
        """Validate and normalize caller input without filesystem access."""
        if not PROJECT_NAME_RE.fullmatch(self.project_name):
            raise InputValidationError(
                "project_name must be lowercase, start with a letter, and contain only letters, numbers, and hyphens"
            )
        framework = self.framework.lower()
        if framework not in FRAMEWORKS:
            raise InputValidationError(
                f"framework must be one of {', '.join(FRAMEWORKS)}, got {self.framework!r}"
            )
        if not self.target_dir.is_absolute():
            raise InputValidationError("target_dir must be an absolute path")
        module_path = self.module_path
        if framework == "go":
            if not module_path or any(character.isspace() for character in module_path):
                raise InputValidationError("module_path is required for Go and must not contain whitespace")
        elif module_path is not None:
            raise InputValidationError("module_path is valid only for Go projects")
        return ResolvedProjectInput(
            project_name=self.project_name,
            package_name=self.project_name.replace("-", "_"),
            framework=cast(Framework, framework),
            target_dir=str(self.target_dir),
            module_path=module_path,
        )


@dataclass(frozen=True)
class ResolvedProjectInput:
    """Validated values included in the plan fingerprint."""

    project_name: str
    package_name: str
    framework: Framework
    target_dir: str
    module_path: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "project_name": self.project_name,
            "package_name": self.package_name,
            "framework": self.framework,
            "target_dir": self.target_dir,
            "module_path": self.module_path,
        }


@dataclass(frozen=True)
class PlannedWrite:
    """One fully resolved file write relative to the target directory."""

    path: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "content": self.content}


@dataclass(frozen=True)
class PlannedCommand:
    """One structured command associated with a semantic checkpoint step."""

    step_id: str
    argv: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"step_id": self.step_id, "argv": list(self.argv)}


@dataclass(frozen=True)
class Plan:
    """Immutable resolved project plan and stable content fingerprint."""

    project: ResolvedProjectInput
    writes: tuple[PlannedWrite, ...]
    commands: tuple[PlannedCommand, ...]
    fingerprint: str

    @classmethod
    def create(
        cls,
        project: ResolvedProjectInput,
        writes: Sequence[PlannedWrite],
        commands: Sequence[PlannedCommand],
    ) -> Plan:
        writes_tuple = tuple(writes)
        commands_tuple = tuple(commands)
        step_ids = ("scaffold_files_written", *(command.step_id for command in commands_tuple))
        if len(step_ids) != len(set(step_ids)):
            raise InputValidationError("plan semantic step_ids must be unique")
        payload = _plan_payload(project, writes_tuple, commands_tuple)
        fingerprint = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        return cls(
            project=project,
            writes=writes_tuple,
            commands=commands_tuple,
            fingerprint=fingerprint,
        )

    @property
    def target_dir(self) -> Path:
        return Path(self.project.target_dir)

    @property
    def step_ids(self) -> tuple[str, ...]:
        return ("scaffold_files_written", *(command.step_id for command in self.commands))

    def to_dict(self) -> dict[str, Any]:
        payload = _plan_payload(self.project, self.writes, self.commands)
        payload["fingerprint"] = self.fingerprint
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class Checkpoint:
    """Persisted semantic progress for one exact plan."""

    schema_version: int
    fingerprint: str
    plan_step_ids: tuple[str, ...]
    completed_steps: tuple[str, ...]
    created_at: str
    updated_at: str

    @classmethod
    def create(cls, init_plan: Plan, now: str | None = None) -> Checkpoint:
        timestamp = _timestamp(now)
        return cls(
            schema_version=CHECKPOINT_SCHEMA_VERSION,
            fingerprint=init_plan.fingerprint,
            plan_step_ids=init_plan.step_ids,
            completed_steps=(),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def complete(self, step_id: str, now: str | None = None) -> Checkpoint:
        if step_id in self.completed_steps:
            return self
        return Checkpoint(
            schema_version=self.schema_version,
            fingerprint=self.fingerprint,
            plan_step_ids=self.plan_step_ids,
            completed_steps=(*self.completed_steps, step_id),
            created_at=self.created_at,
            updated_at=_timestamp(now),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fingerprint": self.fingerprint,
            "plan_step_ids": list(self.plan_step_ids),
            "completed_steps": list(self.completed_steps),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CommandExecutor(Protocol):
    """Injectable boundary for planned external commands."""

    def run(self, command: PlannedCommand, cwd: Path) -> None:
        """Run one command in ``cwd`` or raise on failure."""


Executor = CommandExecutor | Callable[[PlannedCommand, Path], None]


class SubprocessExecutor:
    """Production executor used by the command-line adapter."""

    def run(self, command: PlannedCommand, cwd: Path) -> None:
        subprocess.run(command.argv, cwd=cwd, check=True)  # binary-guard: allow production executor boundary


@dataclass(frozen=True)
class TemplateSpec:
    """One checked-in template mirrored by the standalone engine catalog."""

    framework: Framework
    template_path: str
    output_path: str
    content: str


TEMPLATE_CATALOG = (
    TemplateSpec(
        "python",
        "pyproject.toml",
        "pyproject.toml",
        '''[project]
name = "$project_name"
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
    ),
    TemplateSpec(
        "python",
        "src/__package_name__/__init__.py",
        "src/$package_name/__init__.py",
        '''"""$project_name."""

__version__ = "0.1.0"
''',
    ),
    TemplateSpec(
        "python",
        "tests/conftest.py",
        "tests/conftest.py",
        '''"""Shared test fixtures."""
''',
    ),
    TemplateSpec(
        "python",
        "tests/test_placeholder.py",
        "tests/test_placeholder.py",
        '''"""Placeholder test to verify setup."""


def test_import():
    """Verify the package can be imported."""
    import importlib
    mod = importlib.import_module("$package_name")
    assert hasattr(mod, "__version__")
''',
    ),
    TemplateSpec(
        "python",
        ".gitignore",
        ".gitignore",
        '''__pycache__/
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
    ),
    TemplateSpec(
        "node",
        "package.json",
        "package.json",
        '''{
  "name": "$project_name",
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
    ),
    TemplateSpec(
        "node",
        "tsconfig.json",
        "tsconfig.json",
        '''{
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
    ),
    TemplateSpec(
        "node",
        "src/index.ts",
        "src/index.ts",
        '''console.log("Hello from $project_name");
''',
    ),
    TemplateSpec(
        "node",
        "tests/placeholder.test.ts",
        "tests/placeholder.test.ts",
        '''import { describe, it, expect } from 'vitest';

describe('placeholder', () => {
  it('passes', () => {
    expect(true).toBe(true);
  });
});
''',
    ),
    TemplateSpec(
        "node",
        ".gitignore",
        ".gitignore",
        '''node_modules/
dist/
build/
.next/
coverage/
.env
.claude/settings.local.json
''',
    ),
    TemplateSpec(
        "go",
        "go.mod",
        "go.mod",
        '''module $module_path

go 1.22
''',
    ),
    TemplateSpec(
        "go",
        "cmd/main.go",
        "cmd/main.go",
        '''package main

import "fmt"

func main() {
	fmt.Println("Hello from $project_name")
}
''',
    ),
    TemplateSpec(
        "go",
        ".gitignore",
        ".gitignore",
        '''bin/
coverage.out
.env
.claude/settings.local.json
''',
    ),
    TemplateSpec(
        "rust",
        "Cargo.toml",
        "Cargo.toml",
        '''[package]
name = "$project_name"
version = "0.1.0"
edition = "2021"

[dependencies]
''',
    ),
    TemplateSpec(
        "rust",
        "src/main.rs",
        "src/main.rs",
        '''fn main() {
    println!("Hello from $project_name");
}
''',
    ),
    TemplateSpec(
        "rust",
        ".gitignore",
        ".gitignore",
        '''target/
.env
.claude/settings.local.json
''',
    ),
)


def plan(project_input: ProjectInitInput) -> Plan:
    """Return a deterministic, fully resolved plan without performing I/O."""
    project = project_input.resolve()
    values = {
        "project_name": project.project_name,
        "package_name": project.package_name,
        "module_path": project.module_path or "",
    }
    writes = []
    for template in TEMPLATE_CATALOG:
        if template.framework != project.framework:
            continue
        path = Template(template.output_path).substitute(values)
        _validate_relative_path(path)
        content = Template(template.content).substitute(values)
        writes.append(PlannedWrite(path=path, content=content))

    commands = []
    if project.framework == "python":
        commands.append(PlannedCommand("dependencies_synchronized", ("uv", "sync")))
    elif project.framework == "node":
        commands.append(PlannedCommand("dependencies_synchronized", ("npm", "install")))
    commands.extend(
        (
            PlannedCommand("git_initialized", ("git", "init", "-b", "main")),
            PlannedCommand("scaffold_staged", ("git", "add", ".")),
            PlannedCommand(
                "initial_commit_created",
                ("git", "commit", "-m", INITIAL_COMMIT_MESSAGE),
            ),
        )
    )
    return Plan.create(project, writes, commands)


def apply(
    init_plan: Plan,
    checkpoint_path: Path,
    executor: Executor,
    *,
    resume: bool = False,
) -> Checkpoint:
    """Apply a plan once, or validate and continue its named checkpoint steps."""
    checkpoint_path = checkpoint_path.absolute()
    if resume and not checkpoint_path.exists():
        raise CheckpointError(f"resume requested but checkpoint does not exist: {checkpoint_path}")
    if not resume and checkpoint_path.exists():
        raise CheckpointError(f"checkpoint already exists: {checkpoint_path}; use --resume")

    with _checkpoint_lock(checkpoint_path):
        if resume:
            checkpoint = _load_checkpoint(checkpoint_path, init_plan)
            _revalidate_completed_files(init_plan, checkpoint)
        else:
            checkpoint = Checkpoint.create(init_plan)

        if "scaffold_files_written" not in checkpoint.completed_steps:
            _apply_writes(init_plan)
            checkpoint = checkpoint.complete("scaffold_files_written")
            _atomic_write_checkpoint(checkpoint_path, checkpoint)

        for command in init_plan.commands:
            if command.step_id in checkpoint.completed_steps:
                continue
            checkpoint_was_hidden = command.step_id == "scaffold_staged"
            if checkpoint_was_hidden:
                checkpoint_path.unlink(missing_ok=True)
            try:
                _run_executor(executor, command, init_plan.target_dir)
            except Exception as exc:
                if checkpoint_was_hidden:
                    _atomic_write_checkpoint(checkpoint_path, checkpoint)
                raise ApplyError(
                    f"command failed for semantic step {command.step_id}: {list(command.argv)!r}: {exc}"
                ) from exc
            checkpoint = checkpoint.complete(command.step_id)
            _atomic_write_checkpoint(checkpoint_path, checkpoint)

        return checkpoint


def default_checkpoint_path(target_dir: Path) -> Path:
    return target_dir / ".claude" / "project-init-checkpoint.json"


def _plan_payload(
    project: ResolvedProjectInput,
    writes: Sequence[PlannedWrite],
    commands: Sequence[PlannedCommand],
) -> dict[str, Any]:
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "project": project.to_dict(),
        "writes": [write.to_dict() for write in writes],
        "commands": [command.to_dict() for command in commands],
        "step_ids": ["scaffold_files_written", *(command.step_id for command in commands)],
    }


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validate_relative_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or path in {"", "."}:
        raise InputValidationError(f"template produced unsafe relative path: {path!r}")


def _apply_writes(init_plan: Plan) -> None:
    try:
        init_plan.target_dir.mkdir(parents=True, exist_ok=True)
        for write in init_plan.writes:
            destination = init_plan.target_dir / write.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(destination, write.content)
    except OSError as exc:
        raise ApplyError(f"could not write scaffold files under {init_plan.target_dir}: {exc}") from exc


def _atomic_write_text(path: Path, content: str) -> None:
    temp_path: Path | None = None
    try:
        fd, raw_temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp_path = Path(raw_temp_path)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _atomic_write_checkpoint(path: Path, checkpoint: Checkpoint) -> None:
    temp_path: Path | None = None
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, raw_temp_path = tempfile.mkstemp(prefix=".project-init.", dir=path.parent)
        temp_path = Path(raw_temp_path)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(checkpoint.to_dict(), stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        temp_path = None
    except OSError as exc:
        raise CheckpointError(f"cannot atomically write checkpoint {path}: {exc}") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _load_checkpoint(path: Path, init_plan: Plan) -> Checkpoint:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"cannot read checkpoint {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CheckpointError("checkpoint must be a JSON object")
    if raw.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointError(
            "checkpoint schema_version mismatch: "
            f"expected {CHECKPOINT_SCHEMA_VERSION}, found {raw.get('schema_version')!r}"
        )
    if raw.get("fingerprint") != init_plan.fingerprint:
        raise CheckpointError(
            "checkpoint fingerprint mismatch: "
            f"expected {init_plan.fingerprint}, found {raw.get('fingerprint')!r}"
        )
    plan_step_ids = _string_tuple(raw.get("plan_step_ids"), "plan_step_ids")
    if plan_step_ids != init_plan.step_ids:
        raise CheckpointError(
            "checkpoint semantic step layout mismatch: "
            f"expected {list(init_plan.step_ids)!r}, found {list(plan_step_ids)!r}"
        )
    completed_steps = _string_tuple(raw.get("completed_steps"), "completed_steps")
    expected_prefix = init_plan.step_ids[: len(completed_steps)]
    if completed_steps != expected_prefix:
        raise CheckpointError(
            "checkpoint completed_steps mismatch: semantic names must be an ordered prefix of the current plan; "
            f"found {list(completed_steps)!r}"
        )
    created_at = raw.get("created_at")
    updated_at = raw.get("updated_at")
    if not isinstance(created_at, str) or not isinstance(updated_at, str):
        raise CheckpointError("checkpoint created_at and updated_at must be strings")
    return Checkpoint(
        schema_version=CHECKPOINT_SCHEMA_VERSION,
        fingerprint=init_plan.fingerprint,
        plan_step_ids=plan_step_ids,
        completed_steps=completed_steps,
        created_at=created_at,
        updated_at=updated_at,
    )


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CheckpointError(f"checkpoint {field} must be an array of semantic step name strings")
    return tuple(value)


def _revalidate_completed_files(init_plan: Plan, checkpoint: Checkpoint) -> None:
    if "scaffold_files_written" not in checkpoint.completed_steps:
        return
    for write in init_plan.writes:
        destination = init_plan.target_dir / write.path
        try:
            actual = destination.read_text(encoding="utf-8")
        except OSError as exc:
            raise CheckpointError(
                "checkpoint filesystem mismatch for completed step scaffold_files_written: "
                f"cannot read {write.path}: {exc}"
            ) from exc
        if actual != write.content:
            raise CheckpointError(
                "checkpoint filesystem mismatch for completed step scaffold_files_written: "
                f"content changed at {write.path}"
            )


def _run_executor(executor: Executor, command: PlannedCommand, cwd: Path) -> None:
    run_method = getattr(executor, "run", None)
    if callable(run_method):
        run_method(command, cwd)
    else:
        cast(Callable[[PlannedCommand, Path], None], executor)(command, cwd)


@contextmanager
def _checkpoint_lock(checkpoint_path: Path) -> Iterator[None]:
    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
    lock_dir = runtime_dir / "cpp-project-init-locks"
    digest = hashlib.sha256(str(checkpoint_path).encode("utf-8")).hexdigest()
    try:
        lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_file = (lock_dir / f"{digest}.lock").open("a+", encoding="utf-8")
    except OSError as exc:
        raise CheckpointError(f"cannot prepare checkpoint lock: {exc}") from exc
    with lock_file:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise CheckpointError(
                        f"could not lock checkpoint {checkpoint_path} within 10 seconds"
                    ) from exc
                time.sleep(0.05)
            except OSError as exc:
                raise CheckpointError(f"cannot lock checkpoint {checkpoint_path}: {exc}") from exc
        try:
            yield
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def _timestamp(value: str | None = None) -> str:
    return value or datetime.now(timezone.utc).isoformat()


def _parse_options(args: list[str]) -> dict[str, Any]:
    boolean = {"dry-run", "resume"}
    options: dict[str, Any] = {}
    index = 0
    while index < len(args):
        argument = args[index]
        if argument in {"-h", "--help"}:
            raise InputValidationError("help requested")
        if not argument.startswith("--"):
            raise InputValidationError(f"unexpected argument: {argument}")
        raw = argument[2:]
        if "=" in raw:
            name, value = raw.split("=", 1)
            if name in boolean:
                raise InputValidationError(f"--{name} does not take a value")
            index += 1
        else:
            name = raw
            if name in boolean:
                if name in options:
                    raise InputValidationError(f"--{name} may be supplied only once")
                options[name] = True
                index += 1
                continue
            if index + 1 >= len(args):
                raise InputValidationError(f"--{name} requires a value")
            value = args[index + 1]
            index += 2
        if name in options:
            raise InputValidationError(f"--{name} may be supplied only once")
        options[name] = value
    allowed = {
        "project-name",
        "framework",
        "target-dir",
        "module-path",
        "checkpoint-path",
        "dry-run",
        "resume",
    }
    unknown = sorted(set(options) - allowed)
    if unknown:
        raise InputValidationError(f"unknown option(s): {', '.join(f'--{name}' for name in unknown)}")
    missing = [name for name in ("project-name", "framework", "target-dir") if name not in options]
    if missing:
        raise InputValidationError(
            f"missing required option(s): {', '.join(f'--{name}' for name in missing)}"
        )
    if options.get("dry-run") and options.get("resume"):
        raise InputValidationError("--dry-run and --resume cannot be combined")
    return options


def main(argv: list[str]) -> int:
    if len(argv) == 1 or argv[1] in {"-h", "--help"}:
        sys.stderr.write(USAGE)
        return 2
    try:
        options = _parse_options(argv[1:])
        target_dir = Path(str(options["target-dir"])).expanduser().absolute()
        project_input = ProjectInitInput(
            project_name=str(options["project-name"]),
            framework=str(options["framework"]),
            target_dir=target_dir,
            module_path=options.get("module-path"),
        )
        init_plan = plan(project_input)
        if options.get("dry-run"):
            sys.stdout.write(init_plan.to_json())
            return 0
        checkpoint_path = Path(
            str(options.get("checkpoint-path", default_checkpoint_path(target_dir)))
        ).expanduser()
        if not checkpoint_path.is_absolute():
            checkpoint_path = target_dir / checkpoint_path
        checkpoint = apply(
            init_plan,
            checkpoint_path,
            SubprocessExecutor(),
            resume=bool(options.get("resume")),
        )
        json.dump(
            {
                "fingerprint": init_plan.fingerprint,
                "checkpoint": str(checkpoint_path),
                "completed_steps": list(checkpoint.completed_steps),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0
    except InputValidationError as exc:
        if str(exc) != "help requested":
            sys.stderr.write(f"project-init: {exc}\n")
        sys.stderr.write(USAGE)
        return 2
    except (CheckpointError, ApplyError) as exc:
        sys.stderr.write(f"project-init: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
