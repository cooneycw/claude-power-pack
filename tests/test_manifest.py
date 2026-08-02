"""Tests for the typed task manifest (cicd_tasks.yml).

Covers:
- Pydantic model validation (StepModel, PlanModel, TaskManifest)
- YAML loading and validation
- Auto-generation from detected framework + Makefile
- Cross-reference validation (plans referencing undefined steps)
- Backwards compatibility (no manifest = built-in plans)
- Runner integration (manifest plans consumed by get_plan_steps)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from lib.cicd.manifest import (
    PlanModel,
    StepModel,
    TaskManifest,
    generate_manifest,
    load_manifest,
    step_model_to_step_def,
    write_manifest,
)
from lib.cicd.steps import ShellStep, StepDef, get_plan_steps

# -- StepModel validation tests --


class TestStepModel:
    def test_minimal_step(self):
        step = StepModel(command="make lint")
        assert step.command == "make lint"
        assert step.timeout == 600
        assert step.max_attempts == 1
        assert step.idempotent is True
        assert step.skip_if is None
        assert step.artifacts == []
        assert step.rollback is None

    def test_full_step(self):
        step = StepModel(
            command="make test",
            description="Run pytest",
            timeout=300,
            max_attempts=3,
            backoff_seconds=5.0,
            idempotent=True,
            skip_if='! grep -q "^test:" Makefile 2>/dev/null',
            depends_on=["lint"],
            env={"DJANGO_SETTINGS_MODULE": "config.settings.test"},
            artifacts=["coverage.xml", "htmlcov/"],
            rollback="make clean",
        )
        assert step.timeout == 300
        assert step.max_attempts == 3
        assert step.env == {"DJANGO_SETTINGS_MODULE": "config.settings.test"}
        assert step.artifacts == ["coverage.xml", "htmlcov/"]
        assert step.rollback == "make clean"

    def test_env_default_empty(self):
        step = StepModel(command="make lint")
        assert step.env == {}

    def test_timeout_bounds(self):
        with pytest.raises(Exception):
            StepModel(command="x", timeout=0)

        with pytest.raises(Exception):
            StepModel(command="x", timeout=8000)

    def test_max_attempts_bounds(self):
        with pytest.raises(Exception):
            StepModel(command="x", max_attempts=0)

        with pytest.raises(Exception):
            StepModel(command="x", max_attempts=11)

    def test_extra_fields_ignored(self):
        step = StepModel(command="make lint", unknown_field="ignored")
        assert step.command == "make lint"
        assert not hasattr(step, "unknown_field")


# -- PlanModel validation tests --


class TestPlanModel:
    def test_valid_plan(self):
        plan = PlanModel(steps=["lint", "test"])
        assert plan.steps == ["lint", "test"]

    def test_empty_steps_rejected(self):
        with pytest.raises(Exception):
            PlanModel(steps=[])

    def test_description(self):
        plan = PlanModel(steps=["lint"], description="Quality check")
        assert plan.description == "Quality check"


# -- TaskManifest validation tests --


class TestTaskManifest:
    def test_minimal_manifest(self):
        manifest = TaskManifest(version="1")
        assert manifest.version == "1"
        assert manifest.steps == {}
        assert manifest.plans == {}

    def test_unsupported_version(self):
        with pytest.raises(Exception):
            TaskManifest(version="99")

    def test_full_manifest(self):
        manifest = TaskManifest(
            version="1",
            steps={
                "lint": StepModel(command="make lint"),
                "test": StepModel(command="make test"),
            },
            plans={
                "check": PlanModel(steps=["lint", "test"]),
            },
        )
        assert "lint" in manifest.steps
        assert "check" in manifest.plans

    def test_validate_plan_references_valid(self):
        manifest = TaskManifest(
            version="1",
            steps={
                "lint": StepModel(command="make lint"),
                "test": StepModel(command="make test"),
            },
            plans={
                "check": PlanModel(steps=["lint", "test"]),
            },
        )
        errors = manifest.validate_plan_references()
        assert errors == []

    def test_validate_plan_references_invalid(self):
        manifest = TaskManifest(
            version="1",
            steps={
                "lint": StepModel(command="make lint"),
            },
            plans={
                "check": PlanModel(steps=["lint", "nonexistent"]),
            },
        )
        errors = manifest.validate_plan_references()
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_get_plan_step_models(self):
        manifest = TaskManifest(
            version="1",
            steps={
                "lint": StepModel(command="make lint", timeout=300),
                "test": StepModel(command="make test", timeout=600),
            },
            plans={
                "check": PlanModel(steps=["lint", "test"]),
            },
        )
        pairs = manifest.get_plan_step_models("check")
        assert len(pairs) == 2
        assert pairs[0] == ("lint", manifest.steps["lint"])
        assert pairs[1] == ("test", manifest.steps["test"])

    def test_get_plan_step_models_unknown_plan(self):
        manifest = TaskManifest(version="1")
        with pytest.raises(ValueError, match="Unknown plan"):
            manifest.get_plan_step_models("nonexistent")

    def test_to_yaml_roundtrip(self):
        manifest = TaskManifest(
            version="1",
            steps={
                "lint": StepModel(command="make lint", timeout=300),
                "test": StepModel(command="make test"),
            },
            plans={
                "check": PlanModel(steps=["lint", "test"]),
            },
        )
        yaml_str = manifest.to_yaml()
        data = yaml.safe_load(yaml_str)
        restored = TaskManifest.model_validate(data)
        assert restored.version == "1"
        assert "lint" in restored.steps
        assert restored.steps["lint"].timeout == 300
        assert restored.plans["check"].steps == ["lint", "test"]


# -- step_model_to_step_def conversion tests --


class TestStepModelToStepDef:
    def test_conversion(self):
        model = StepModel(
            command="make test",
            description="Run tests",
            timeout=300,
            max_attempts=3,
            backoff_seconds=5.0,
            idempotent=True,
            skip_if='! grep -q "^test:" Makefile 2>/dev/null',
            depends_on=["lint"],
        )
        step_def = step_model_to_step_def("test", model)
        assert isinstance(step_def, StepDef)
        assert step_def.id == "test"
        assert step_def.command == "make test"
        assert step_def.timeout_seconds == 300
        assert step_def.max_attempts == 3
        assert step_def.backoff_seconds == 5.0
        assert step_def.idempotent is True
        assert step_def.skip_if == '! grep -q "^test:" Makefile 2>/dev/null'
        assert step_def.depends_on == ["lint"]

    def test_env_field_conversion(self):
        model = StepModel(
            command="make test",
            env={"UV_CACHE_DIR": "/tmp/uv-cache", "DJANGO_SETTINGS_MODULE": "config.settings.test"},
        )
        step_def = step_model_to_step_def("test", model)
        assert step_def.env == {"UV_CACHE_DIR": "/tmp/uv-cache", "DJANGO_SETTINGS_MODULE": "config.settings.test"}

    def test_env_field_default_empty(self):
        model = StepModel(command="make lint")
        step_def = step_model_to_step_def("lint", model)
        assert step_def.env == {}


# -- load_manifest tests --


class TestLoadManifest:
    def test_no_manifest_returns_none(self, tmp_path):
        result = load_manifest(tmp_path)
        assert result is None

    def test_valid_manifest(self, tmp_path):
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text(textwrap.dedent("""\
            version: "1"
            steps:
              lint:
                command: make lint
                timeout: 300
              test:
                command: make test
            plans:
              check:
                steps: [lint, test]
        """))

        manifest = load_manifest(tmp_path)
        assert manifest is not None
        assert manifest.version == "1"
        assert "lint" in manifest.steps
        assert manifest.steps["lint"].timeout == 300
        assert "check" in manifest.plans

    def test_invalid_yaml(self, tmp_path):
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text("{{invalid yaml")

        with pytest.raises(ValueError, match="Invalid YAML"):
            load_manifest(tmp_path)

    def test_invalid_schema(self, tmp_path):
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text(textwrap.dedent("""\
            version: "99"
            steps: {}
            plans: {}
        """))

        with pytest.raises(ValueError, match="Unsupported manifest version"):
            load_manifest(tmp_path)

    def test_invalid_cross_reference(self, tmp_path):
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text(textwrap.dedent("""\
            version: "1"
            steps:
              lint:
                command: make lint
            plans:
              check:
                steps: [lint, nonexistent]
        """))

        with pytest.raises(ValueError, match="nonexistent"):
            load_manifest(tmp_path)

    def test_manifest_with_env(self, tmp_path):
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text(textwrap.dedent("""\
            version: "1"
            steps:
              test:
                command: make test
                env:
                  UV_CACHE_DIR: /tmp/uv-cache
                  DJANGO_SETTINGS_MODULE: config.settings.test
            plans:
              check:
                steps: [test]
        """))

        manifest = load_manifest(tmp_path)
        assert manifest is not None
        assert manifest.steps["test"].env == {
            "UV_CACHE_DIR": "/tmp/uv-cache",
            "DJANGO_SETTINGS_MODULE": "config.settings.test",
        }

    def test_empty_file_returns_none(self, tmp_path):
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text("")

        result = load_manifest(tmp_path)
        assert result is None

    def test_non_dict_yaml(self, tmp_path):
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text("- item1\n- item2\n")

        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_manifest(tmp_path)


# -- generate_manifest tests --


class TestGenerateManifest:
    def test_python_project(self, tmp_path):
        # Create minimal Python project markers
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "uv.lock").write_text("")
        (tmp_path / "Makefile").write_text(
            ".PHONY: lint test\n\nlint:\n\tuv run ruff check .\n\ntest:\n\tuv run pytest\n"
        )

        manifest = generate_manifest(tmp_path)
        assert manifest.version == "1"
        assert "lint" in manifest.steps
        assert "test" in manifest.steps
        assert "finish" in manifest.plans
        assert "check" in manifest.plans

    def test_no_makefile(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "uv.lock").write_text("")

        manifest = generate_manifest(tmp_path)
        # Should still generate steps from framework runner commands
        assert manifest.version == "1"
        assert len(manifest.steps) > 0

    def test_unknown_framework(self, tmp_path):
        # Empty directory - no framework markers
        manifest = generate_manifest(tmp_path)
        assert manifest.version == "1"
        # Should still have security_scan at minimum
        assert "security_scan" in manifest.steps

    def test_generated_security_scan_dehardcoded(self, tmp_path):
        """Generated security_scan derives PYTHONPATH via step env, not a
        hardcoded ${HOME}/Projects/claude-power-pack prefix (#534)."""
        from lib.cicd.steps import _CPP_ROOT

        manifest = generate_manifest(tmp_path)
        step = manifest.steps["security_scan"]
        assert "Projects/claude-power-pack" not in step.command
        assert "Projects/claude-power-pack" not in (step.skip_if or "")
        assert dict(step.env).get("PYTHONPATH") == _CPP_ROOT


# -- write_manifest tests --


class TestWriteManifest:
    def test_write_and_reload(self, tmp_path):
        manifest = TaskManifest(
            version="1",
            steps={
                "lint": StepModel(command="make lint"),
                "test": StepModel(command="make test", timeout=300),
            },
            plans={
                "check": PlanModel(steps=["lint", "test"]),
            },
        )

        path = write_manifest(manifest, tmp_path)
        assert path.exists()
        assert path.name == "cicd_tasks.yml"

        # Reload and verify
        reloaded = load_manifest(tmp_path)
        assert reloaded is not None
        assert reloaded.version == "1"
        assert "lint" in reloaded.steps
        assert "test" in reloaded.steps
        assert reloaded.steps["test"].timeout == 300
        assert reloaded.plans["check"].steps == ["lint", "test"]

    def test_write_creates_directory(self, tmp_path):
        manifest = TaskManifest(
            version="1",
            steps={"lint": StepModel(command="make lint")},
            plans={"check": PlanModel(steps=["lint"])},
        )
        path = write_manifest(manifest, tmp_path)
        assert (tmp_path / ".claude").is_dir()
        assert path.exists()


# -- get_plan_steps integration tests --


class TestGetPlanStepsIntegration:
    def test_no_manifest_uses_builtin(self, tmp_path):
        """Without a manifest, get_plan_steps returns built-in plan."""
        steps = get_plan_steps("finish", project_root=str(tmp_path))
        assert len(steps) > 0
        assert steps[0].id == "lint"

    def test_manifest_overrides_builtin(self, tmp_path):
        """With a manifest, get_plan_steps uses manifest plans."""
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text(textwrap.dedent("""\
            version: "1"
            steps:
              custom_lint:
                command: "custom-linter run ."
                timeout: 120
              custom_test:
                command: "custom-test run ."
                timeout: 300
            plans:
              finish:
                steps: [custom_lint, custom_test]
        """))

        steps = get_plan_steps("finish", project_root=str(tmp_path))
        assert len(steps) == 2
        assert steps[0].id == "custom_lint"
        assert steps[0].command == "custom-linter run ."
        assert steps[1].id == "custom_test"

    def test_manifest_plan_not_found_falls_back(self, tmp_path):
        """If manifest exists but plan not in it, fall back to built-in."""
        manifest_dir = tmp_path / ".claude"
        manifest_dir.mkdir()
        manifest_file = manifest_dir / "cicd_tasks.yml"
        manifest_file.write_text(textwrap.dedent("""\
            version: "1"
            steps:
              lint:
                command: make lint
            plans:
              custom_only:
                steps: [lint]
        """))

        # 'finish' not in manifest, should fall back to built-in
        steps = get_plan_steps("finish", project_root=str(tmp_path))
        assert len(steps) > 0
        assert steps[0].id == "lint"
        # The built-in gate prefers `make lint` but carries the #628 uv fallback,
        # which the manifest's plain `make lint` does not - so this proves we fell
        # back to BUILTIN_PLANS, not to the manifest's step.
        assert "make lint" in steps[0].command
        assert "uv run --extra dev ruff" in steps[0].command


# -- CPP's own manifest validation --


class TestCPPManifest:
    def test_cpp_manifest_loads(self):
        """Validate that CPP's own .claude/cicd_tasks.yml is valid."""
        cpp_root = Path(__file__).parent.parent
        manifest = load_manifest(cpp_root)
        assert manifest is not None
        assert manifest.version == "1"

        # Verify expected steps exist
        assert "lint" in manifest.steps
        assert "test" in manifest.steps
        assert "security_scan" in manifest.steps
        assert "deploy" in manifest.steps

        # Verify expected plans exist
        assert "finish" in manifest.plans
        assert "check" in manifest.plans
        assert "deploy" in manifest.plans

        # Verify cross-references are valid
        errors = manifest.validate_plan_references()
        assert errors == [], f"CPP manifest has reference errors: {errors}"


class TestManifestPlansIncludeTypecheck:
    """The runner PREFERS `.claude/cicd_tasks.yml` over BUILTIN_PLANS, so fixing
    only the built-ins leaves every manifest-carrying project (CPP itself
    included) with the issue #617 false green. A typecheck step defined under
    `steps:` but referenced by no plan is dead config - these tests pin the
    reference, not just the definition."""

    @staticmethod
    def _py_project(root: Path) -> None:
        (root / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (root / "uv.lock").write_text("")
        (root / "Makefile").write_text(
            ".PHONY: lint test typecheck\n\n"
            "lint:\n\tuv run ruff check .\n\n"
            "test:\n\tuv run pytest\n\n"
            "typecheck:\n\tuv run mypy .\n"
        )

    def test_generated_finish_plan_includes_typecheck(self, tmp_path):
        self._py_project(tmp_path)
        manifest = generate_manifest(tmp_path)
        assert "typecheck" in manifest.steps
        assert "typecheck" in manifest.plans["finish"].steps, (
            "generated finish plan defines a typecheck step but never runs it (#617)"
        )

    def test_generated_check_plan_includes_typecheck(self, tmp_path):
        self._py_project(tmp_path)
        manifest = generate_manifest(tmp_path)
        assert "typecheck" in manifest.plans["check"].steps

    def test_generated_typecheck_runs_before_security_scan(self, tmp_path):
        self._py_project(tmp_path)
        steps = generate_manifest(tmp_path).plans["finish"].steps
        assert steps.index("typecheck") < steps.index("security_scan")

    def test_project_without_typecheck_target_or_tool_skips_at_runtime(self, tmp_path):
        """A Python project always gets a typecheck step (the framework runner
        supplies `uv run mypy .`), and with no Makefile target AND no mypy
        configured in pyproject it skips at runtime - it does NOT hard-fail on a
        missing tool, and it does NOT silently pass. The skip_if now also guards
        on the pyproject tool token so a configured tool runs instead of skipping
        (issue #628)."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "uv.lock").write_text("")
        (tmp_path / "Makefile").write_text(
            ".PHONY: lint test\n\nlint:\n\techo lint\n\ntest:\n\techo test\n"
        )
        manifest = generate_manifest(tmp_path)
        assert manifest.validate_plan_references() == []

        step = step_model_to_step_def("typecheck", manifest.steps["typecheck"])
        assert '! grep -q "^typecheck:" Makefile 2>/dev/null' in (step.skip_if or "")
        assert "mypy" in (step.skip_if or "")
        assert ShellStep(step).should_skip({"project_root": str(tmp_path), "env": {}}) is True

    def test_configured_tool_runs_without_makefile_target(self, tmp_path):
        """pyproject configures mypy and there is no typecheck Makefile target:
        the generated gate falls back to `uv run mypy .` instead of skipping
        (issue #628) - the twin of the BUILTIN_PLANS fix in the manifest."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'test'\n\n[tool.mypy]\nstrict = true\n"
        )
        (tmp_path / "uv.lock").write_text("")
        (tmp_path / "Makefile").write_text(
            ".PHONY: lint test\n\nlint:\n\techo lint\n\ntest:\n\techo test\n"
        )
        manifest = generate_manifest(tmp_path)
        step = step_model_to_step_def("typecheck", manifest.steps["typecheck"])
        assert "uv run mypy ." in step.command
        assert ShellStep(step).should_skip({"project_root": str(tmp_path), "env": {}}) is False

    def test_typecheck_does_not_skip_when_target_exists(self, tmp_path):
        self._py_project(tmp_path)
        manifest = generate_manifest(tmp_path)
        step = step_model_to_step_def("typecheck", manifest.steps["typecheck"])
        assert ShellStep(step).should_skip({"project_root": str(tmp_path), "env": {}}) is False

    def test_cpp_own_manifest_gates_typecheck(self):
        """CPP's checked-in manifest is what its own /flow:finish actually runs,
        and .woodpecker.yml's validate step runs mypy - so omitting typecheck
        here guarantees local-green-then-CI-red on this very repo (#617)."""
        from lib.cicd.steps import _CPP_ROOT

        manifest_path = Path(_CPP_ROOT) / ".claude" / "cicd_tasks.yml"
        if not manifest_path.is_file():
            pytest.skip("no checked-in manifest in this checkout")
        manifest = load_manifest(Path(_CPP_ROOT))
        assert manifest is not None
        for plan_name in ("finish", "check"):
            assert "typecheck" in manifest.plans[plan_name].steps, (
                f"CPP's own '{plan_name}' plan does not run typecheck, but CI does (#617)"
            )
        assert manifest.validate_plan_references() == []
