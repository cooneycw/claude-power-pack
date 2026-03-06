"""Tests for lib/cicd/pipeline.py - pipeline generation."""

from __future__ import annotations

from pathlib import Path

from lib.cicd.config import CICDConfig
from lib.cicd.models import Framework, FrameworkInfo, PackageManager
from lib.cicd.pipeline import (
    _get_install_commands,
    generate_github_actions,
    generate_pipeline,
    generate_woodpecker,
)


def _make_info(
    framework: Framework = Framework.PYTHON,
    package_manager: PackageManager = PackageManager.UV,
) -> FrameworkInfo:
    """Helper to build a FrameworkInfo for tests."""
    return FrameworkInfo(
        framework=framework,
        package_manager=package_manager,
        detected_files=[],
        recommended_targets=["lint", "test"],
        runner_commands={},
        secondary_frameworks=[],
    )


def _make_config(**overrides: object) -> CICDConfig:
    """Build a CICDConfig with optional pipeline overrides."""
    config = CICDConfig()
    for key, value in overrides.items():
        setattr(config.pipeline, key, value)
    return config


# ---------------------------------------------------------------------------
# generate_pipeline - orchestrator
# ---------------------------------------------------------------------------


class TestGeneratePipeline:
    """Tests for the top-level generate_pipeline() orchestrator."""

    def test_github_actions_provider(self) -> None:
        info = _make_info()
        config = _make_config(provider="github-actions")
        files = generate_pipeline(info, config)
        assert ".github/workflows/ci.yml" in files
        assert ".woodpecker.yml" not in files

    def test_woodpecker_provider(self) -> None:
        info = _make_info()
        config = _make_config(provider="woodpecker")
        files = generate_pipeline(info, config)
        assert ".woodpecker.yml" in files
        assert ".github/workflows/ci.yml" not in files

    def test_both_provider(self) -> None:
        info = _make_info()
        config = _make_config(provider="both")
        files = generate_pipeline(info, config)
        assert ".github/workflows/ci.yml" in files
        assert ".woodpecker.yml" in files

    def test_write_to_disk(self, tmp_path: Path) -> None:
        info = _make_info()
        config = _make_config(provider="github-actions")
        files = generate_pipeline(info, config, output_dir=str(tmp_path))
        assert (tmp_path / ".github" / "workflows" / "ci.yml").exists()
        content = (tmp_path / ".github" / "workflows" / "ci.yml").read_text()
        assert "name: CI" in content
        # Return value also contains the content
        assert ".github/workflows/ci.yml" in files


# ---------------------------------------------------------------------------
# generate_github_actions - Python
# ---------------------------------------------------------------------------


class TestGitHubActionsPython:
    """Test GitHub Actions workflow generation for Python projects."""

    def test_basic_structure(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "name: CI" in output
        assert "actions/checkout@v4" in output
        assert "actions/setup-python@v5" in output

    def test_uv_caching(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/.cache/uv" in output
        assert "uv.lock" in output

    def test_pip_caching(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.PIP)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/.cache/pip" in output
        assert "requirements*.txt" in output

    def test_poetry_caching(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.POETRY)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/.cache/pypoetry" in output
        assert "poetry.lock" in output

    def test_default_matrix(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "python-version" in output
        assert '"3.11"' in output
        assert '"3.12"' in output
        assert "matrix.python-version" in output

    def test_custom_matrix(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(matrix={"python-version": ["3.10", "3.11", "3.12"]})
        output = generate_github_actions(info, config)
        assert '"3.10"' in output
        assert '"3.11"' in output
        assert '"3.12"' in output

    def test_install_commands(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "pip install uv" in output
        assert "uv sync" in output

    def test_uses_makefile_targets(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(branches={"pr": ["lint", "test", "typecheck"]})
        output = generate_github_actions(info, config)
        assert "make lint" in output
        assert "make test" in output
        assert "make typecheck" in output
        # Should NOT contain direct tool invocations
        assert "ruff check" not in output
        assert "pytest" not in output


# ---------------------------------------------------------------------------
# generate_github_actions - Node
# ---------------------------------------------------------------------------


class TestGitHubActionsNode:
    """Test GitHub Actions workflow generation for Node.js projects."""

    def test_basic_structure(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.NPM)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "actions/setup-node@v4" in output

    def test_npm_caching(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.NPM)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/.npm" in output
        assert "package-lock.json" in output

    def test_yarn_caching(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.YARN)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/.cache/yarn" in output
        assert "yarn.lock" in output

    def test_pnpm_caching(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.PNPM)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/.local/share/pnpm" in output
        assert "pnpm-lock.yaml" in output

    def test_node_matrix(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.NPM)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "node-version" in output
        assert '"20"' in output
        assert '"22"' in output

    def test_npm_install(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.NPM)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "npm ci" in output


# ---------------------------------------------------------------------------
# generate_github_actions - Go
# ---------------------------------------------------------------------------


class TestGitHubActionsGo:
    """Test GitHub Actions workflow generation for Go projects."""

    def test_basic_structure(self) -> None:
        info = _make_info(Framework.GO, PackageManager.GO)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "actions/setup-go@v5" in output

    def test_go_caching(self) -> None:
        info = _make_info(Framework.GO, PackageManager.GO)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/go/pkg/mod" in output
        assert "go.sum" in output

    def test_go_matrix(self) -> None:
        info = _make_info(Framework.GO, PackageManager.GO)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "go-version" in output
        assert '"1.22"' in output
        assert '"1.23"' in output

    def test_go_install(self) -> None:
        info = _make_info(Framework.GO, PackageManager.GO)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "go mod download" in output


# ---------------------------------------------------------------------------
# generate_github_actions - Rust
# ---------------------------------------------------------------------------


class TestGitHubActionsRust:
    """Test GitHub Actions workflow generation for Rust projects."""

    def test_basic_structure(self) -> None:
        info = _make_info(Framework.RUST, PackageManager.CARGO)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "dtolnay/rust-toolchain@stable" in output

    def test_cargo_caching(self) -> None:
        info = _make_info(Framework.RUST, PackageManager.CARGO)
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "~/.cargo" in output
        assert "Cargo.lock" in output

    def test_no_install_step(self) -> None:
        """Rust uses cargo which fetches deps on build; no separate install."""
        info = _make_info(Framework.RUST, PackageManager.CARGO)
        config = _make_config()
        output = generate_github_actions(info, config)
        # Cargo has empty install commands, so no "Install dependencies" step
        assert "Install dependencies" not in output


# ---------------------------------------------------------------------------
# Deploy job generation
# ---------------------------------------------------------------------------


class TestDeployJob:
    """Test deploy job generation in GitHub Actions."""

    def test_deploy_on_main_push(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(branches={"main": ["lint", "test", "deploy"], "pr": ["lint", "test"]})
        output = generate_github_actions(info, config)
        assert "deploy:" in output
        assert "needs: ci" in output
        assert "refs/heads/main" in output
        assert "make deploy" in output

    def test_no_deploy_without_target(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(branches={"main": ["lint", "test"], "pr": ["lint", "test"]})
        output = generate_github_actions(info, config)
        # No deploy job should be present
        assert "needs: ci" not in output

    def test_secrets_in_deploy(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(
            branches={"main": ["lint", "test", "deploy"], "pr": ["lint", "test"]},
            secrets_needed=["DEPLOY_KEY", "AWS_ACCESS_KEY_ID"],
        )
        output = generate_github_actions(info, config)
        assert "secrets.DEPLOY_KEY" in output
        assert "secrets.AWS_ACCESS_KEY_ID" in output


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


class TestTriggers:
    """Test on: push/pull_request trigger generation."""

    def test_push_and_pr_triggers(self) -> None:
        info = _make_info()
        config = _make_config()
        output = generate_github_actions(info, config)
        assert "push:" in output
        assert "pull_request:" in output
        assert "branches: [main]" in output


# ---------------------------------------------------------------------------
# generate_woodpecker - various frameworks
# ---------------------------------------------------------------------------


class TestWoodpecker:
    """Test Woodpecker CI pipeline generation."""

    def test_python_woodpecker(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: python:3.12" in output
        assert "pip install uv" in output
        assert "uv sync" in output
        assert "make lint" in output

    def test_node_woodpecker(self) -> None:
        info = _make_info(Framework.NODE, PackageManager.NPM)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: node:22" in output
        assert "npm ci" in output
        assert "make lint" in output

    def test_go_woodpecker(self) -> None:
        info = _make_info(Framework.GO, PackageManager.GO)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: golang:1.23" in output
        assert "go mod download" in output

    def test_rust_woodpecker(self) -> None:
        info = _make_info(Framework.RUST, PackageManager.CARGO)
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "image: rust:1.82" in output

    def test_woodpecker_deploy_with_secrets(self) -> None:
        info = _make_info(Framework.PYTHON, PackageManager.UV)
        config = _make_config(
            branches={"main": ["lint", "test", "deploy"], "pr": ["lint", "test"]},
            secrets_needed=["DEPLOY_KEY"],
        )
        output = generate_woodpecker(info, config)
        assert "- name: deploy" in output
        assert "event: push" in output
        assert "deploy_key" in output  # secrets lowercased in woodpecker

    def test_woodpecker_branch_filtering(self) -> None:
        info = _make_info()
        config = _make_config()
        output = generate_woodpecker(info, config)
        assert "branch: [main]" in output
        assert "event: [push, pull_request]" in output


# ---------------------------------------------------------------------------
# _get_install_commands helper
# ---------------------------------------------------------------------------


class TestInstallCommands:
    """Test _get_install_commands for all framework/PM combos."""

    def test_python_uv(self) -> None:
        cmds = _get_install_commands(Framework.PYTHON, PackageManager.UV)
        assert "pip install uv" in cmds
        assert "uv sync" in cmds

    def test_python_pip(self) -> None:
        cmds = _get_install_commands(Framework.PYTHON, PackageManager.PIP)
        assert "pip install -r requirements.txt" in cmds

    def test_python_poetry(self) -> None:
        cmds = _get_install_commands(Framework.PYTHON, PackageManager.POETRY)
        assert "pip install poetry" in cmds
        assert "poetry install" in cmds

    def test_node_npm(self) -> None:
        cmds = _get_install_commands(Framework.NODE, PackageManager.NPM)
        assert "npm ci" in cmds

    def test_node_yarn(self) -> None:
        cmds = _get_install_commands(Framework.NODE, PackageManager.YARN)
        assert "yarn install --frozen-lockfile" in cmds

    def test_node_pnpm(self) -> None:
        cmds = _get_install_commands(Framework.NODE, PackageManager.PNPM)
        assert "corepack enable" in cmds
        assert "pnpm install --frozen-lockfile" in cmds

    def test_go(self) -> None:
        cmds = _get_install_commands(Framework.GO, PackageManager.GO)
        assert "go mod download" in cmds

    def test_rust_cargo(self) -> None:
        cmds = _get_install_commands(Framework.RUST, PackageManager.CARGO)
        assert cmds == []

    def test_unknown_combo(self) -> None:
        cmds = _get_install_commands(Framework.UNKNOWN, PackageManager.UNKNOWN)
        assert cmds == []


# ---------------------------------------------------------------------------
# Template validation - static workflow templates
# ---------------------------------------------------------------------------


class TestWorkflowTemplates:
    """Validate static workflow templates in templates/workflows/."""

    TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "workflows"

    def test_all_templates_exist(self) -> None:
        expected = [
            "ci-python.yml",
            "ci-node.yml",
            "ci-go.yml",
            "ci-rust.yml",
            "deploy.yml",
        ]
        for name in expected:
            path = self.TEMPLATE_DIR / name
            assert path.exists(), f"Missing template: {name}"

    def test_templates_are_valid_yaml(self) -> None:
        import yaml

        for yml_file in sorted(self.TEMPLATE_DIR.glob("*.yml")):
            content = yml_file.read_text()
            parsed = yaml.safe_load(content)
            assert parsed is not None, f"{yml_file.name} parsed as None"
            assert isinstance(parsed, dict), f"{yml_file.name} is not a mapping"

    def test_ci_templates_have_required_fields(self) -> None:
        import yaml

        for name in ["ci-python.yml", "ci-node.yml", "ci-go.yml", "ci-rust.yml"]:
            path = self.TEMPLATE_DIR / name
            parsed = yaml.safe_load(path.read_text())
            assert "name" in parsed, f"{name} missing 'name'"
            # YAML parses `on:` as boolean True, so check for both
            assert "on" in parsed or True in parsed, f"{name} missing 'on'"
            assert "jobs" in parsed, f"{name} missing 'jobs'"
            assert "ci" in parsed["jobs"], f"{name} missing 'ci' job"

    def test_ci_templates_use_checkout_v4(self) -> None:
        for name in ["ci-python.yml", "ci-node.yml", "ci-go.yml", "ci-rust.yml"]:
            content = (self.TEMPLATE_DIR / name).read_text()
            assert "actions/checkout@v4" in content, f"{name} missing checkout@v4"

    def test_ci_templates_use_makefile_targets(self) -> None:
        for name in ["ci-python.yml", "ci-node.yml", "ci-go.yml", "ci-rust.yml"]:
            content = (self.TEMPLATE_DIR / name).read_text()
            assert "make lint" in content, f"{name} missing 'make lint'"
            assert "make test" in content, f"{name} missing 'make test'"

    def test_ci_templates_have_caching(self) -> None:
        for name in ["ci-python.yml", "ci-node.yml", "ci-go.yml", "ci-rust.yml"]:
            content = (self.TEMPLATE_DIR / name).read_text()
            assert "actions/cache@v4" in content, f"{name} missing cache action"

    def test_deploy_template(self) -> None:
        import yaml

        path = self.TEMPLATE_DIR / "deploy.yml"
        parsed = yaml.safe_load(path.read_text())
        assert parsed["name"] == "Deploy"
        # YAML parses `on:` as boolean True
        on_key = "on" if "on" in parsed else True
        assert "push" in parsed[on_key]
        assert "deploy" in parsed["jobs"]
        content = path.read_text()
        assert "make deploy" in content

    def test_woodpecker_templates_exist(self) -> None:
        expected = [
            "woodpecker-python.yml",
            "woodpecker-node.yml",
            "woodpecker-go.yml",
            "woodpecker-rust.yml",
        ]
        for name in expected:
            path = self.TEMPLATE_DIR / name
            assert path.exists(), f"Missing template: {name}"
