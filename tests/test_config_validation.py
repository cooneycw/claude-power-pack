"""Tests for CI/CD config validation (T018, T019, T020).

Tests Pydantic v2 migration, backwards compatibility, validate command,
and JSON Schema generation.
"""

from __future__ import annotations

import json

from lib.cicd.config import (
    BuildConfig,
    CICDConfig,
    ContainerConfig,
    HealthConfig,
    HealthEndpoint,
    InfrastructureConfig,
    PipelineConfig,
    ProcessCheck,
    SmokeTest,
)


class TestPydanticMigration:
    """Test that dataclass -> Pydantic v2 migration preserves all behavior."""

    def test_default_config(self):
        config = CICDConfig()
        assert config.build.framework == "auto"
        assert config.build.package_manager == "auto"
        assert config.build.required_targets == ["lint", "test"]
        assert config.pipeline.provider == "github-actions"
        assert config.health.post_deploy is False
        assert config.container.enabled is False
        assert config.infrastructure.provider == "terraform"
        assert config.infrastructure.cloud == "aws"

    def test_build_config_defaults(self):
        build = BuildConfig()
        assert build.framework == "auto"
        assert build.required_targets == ["lint", "test"]
        assert "format" in build.recommended_targets
        assert "deploy" in build.recommended_targets

    def test_health_endpoint(self):
        ep = HealthEndpoint(url="http://localhost:8000/health", name="API")
        assert ep.url == "http://localhost:8000/health"
        assert ep.name == "API"
        assert ep.expected_status == 200
        assert ep.timeout == 5

    def test_process_check(self):
        proc = ProcessCheck(name="uvicorn", port=8000)
        assert proc.name == "uvicorn"
        assert proc.port == 8000

    def test_smoke_test(self):
        st = SmokeTest(name="api", command="curl -sf http://localhost:8000/health")
        assert st.expected_exit == 0
        assert st.timeout == 10

    def test_pipeline_config_defaults(self):
        pipeline = PipelineConfig()
        assert "main" in pipeline.branches
        assert "pr" in pipeline.branches
        assert pipeline.woodpecker.local is True

    def test_infrastructure_tiers_defaults(self):
        infra = InfrastructureConfig()
        assert "foundation" in infra.tiers
        assert infra.tiers["foundation"].approval_required is True
        assert infra.tiers["foundation"].separate_credentials is True
        assert infra.tiers["platform"].approval_required is False
        assert infra.tiers["app"].approval_required is False

    def test_container_config(self):
        container = ContainerConfig(enabled=True, expose_ports=[8000, 8080])
        assert container.enabled is True
        assert container.expose_ports == [8000, 8080]


class TestBackwardsCompatibility:
    """Test extra='ignore' ensures existing configs load without errors."""

    def test_extra_fields_ignored_build(self):
        build = BuildConfig.model_validate({"framework": "python", "unknown_field": "value"})
        assert build.framework == "python"

    def test_extra_fields_ignored_health(self):
        health = HealthConfig.model_validate({"post_deploy": True, "new_option": 42})
        assert health.post_deploy is True

    def test_extra_fields_ignored_pipeline(self):
        pipeline = PipelineConfig.model_validate(
            {"provider": "woodpecker", "future_feature": True}
        )
        assert pipeline.provider == "woodpecker"

    def test_extra_fields_ignored_nested(self):
        config = CICDConfig.model_validate(
            {
                "build": {"framework": "python", "extra_key": "ignored"},
                "pipeline": {"provider": "both", "new_setting": 123},
                "unknown_section": {"data": True},
            }
        )
        assert config.build.framework == "python"
        assert config.pipeline.provider == "both"

    def test_full_config_with_extras(self):
        data = {
            "build": {
                "framework": "python",
                "package_manager": "uv",
                "required_targets": ["lint", "test", "typecheck"],
                "future_option": True,
            },
            "health": {
                "endpoints": [{"url": "http://localhost:8000/health", "name": "API"}],
                "processes": [{"name": "uvicorn", "port": 8000}],
                "smoke_tests": [{"name": "api", "command": "curl -sf localhost:8000"}],
                "post_deploy": True,
            },
            "pipeline": {
                "provider": "woodpecker",
                "branches": {"main": ["lint", "test"]},
            },
            "container": {"enabled": True, "expose_ports": [8000]},
            "infrastructure": {
                "provider": "terraform",
                "cloud": "aws",
                "tiers": {
                    "foundation": {"approval_required": True},
                    "platform": {"approval_required": False},
                },
            },
        }
        config = CICDConfig.model_validate(data)
        assert config.build.required_targets == ["lint", "test", "typecheck"]
        assert len(config.health.endpoints) == 1
        assert config.health.endpoints[0].url == "http://localhost:8000/health"
        assert config.pipeline.provider == "woodpecker"
        assert config.container.enabled is True
        assert config.infrastructure.tiers["foundation"].approval_required is True


class TestYamlLoading:
    """Test loading from YAML files."""

    def test_load_defaults_no_file(self, tmp_path):
        config = CICDConfig.load(str(tmp_path))
        assert config.build.framework == "auto"
        assert config.pipeline.provider == "github-actions"

    def test_load_from_yaml(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        config_file = claude_dir / "cicd.yml"
        config_file.write_text(
            """
build:
  framework: python
  package_manager: uv
  required_targets:
    - lint
    - test
    - typecheck
pipeline:
  provider: woodpecker
health:
  post_deploy: true
  endpoints:
    - url: http://localhost:8000/health
      name: API Server
"""
        )
        config = CICDConfig.load(str(tmp_path))
        assert config.build.framework == "python"
        assert config.build.package_manager == "uv"
        assert config.pipeline.provider == "woodpecker"
        assert config.health.post_deploy is True
        assert len(config.health.endpoints) == 1
        assert config.health.endpoints[0].name == "API Server"

    def test_load_yaml_with_unknown_keys(self, tmp_path):
        """Backwards compat: unknown keys silently ignored."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        config_file = claude_dir / "cicd.yml"
        config_file.write_text(
            """
build:
  framework: python
  new_future_field: true
pipeline:
  provider: github-actions
  experimental: true
brand_new_section:
  key: value
"""
        )
        config = CICDConfig.load(str(tmp_path))
        assert config.build.framework == "python"
        assert config.pipeline.provider == "github-actions"

    def test_load_yaml_with_tagging_managed_by(self, tmp_path):
        """Test managed-by -> managed_by mapping."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        config_file = claude_dir / "cicd.yml"
        config_file.write_text(
            """
infrastructure:
  provider: terraform
  cloud: aws
  tagging:
    managed-by: terraform
    repo: my-repo
    owner: my-team
    environment: prod
"""
        )
        config = CICDConfig.load(str(tmp_path))
        assert config.infrastructure.tagging.managed_by == "terraform"
        assert config.infrastructure.tagging.repo == "my-repo"
        assert config.infrastructure.tagging.extra_tags == {"environment": "prod"}


class TestValidation:
    """Test the validate_file method."""

    def test_validate_valid_config(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
build:
  framework: python
pipeline:
  provider: github-actions
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert issues == []

    def test_validate_missing_file(self, tmp_path):
        issues = CICDConfig.validate_file(tmp_path / "missing.yml")
        assert len(issues) == 1
        assert "not found" in issues[0]

    def test_validate_invalid_yaml(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text("build: [invalid: yaml: syntax")
        issues = CICDConfig.validate_file(config_file)
        assert any("syntax" in i.lower() or "error" in i.lower() for i in issues)

    def test_validate_unknown_top_level_keys(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
build:
  framework: python
unknown_key: value
another_unknown: true
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert any("unknown_key" in i for i in issues)

    def test_validate_invalid_provider(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
pipeline:
  provider: jenkins
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert any("jenkins" in i and "invalid" in i for i in issues)

    def test_validate_missing_endpoint_url(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
health:
  endpoints:
    - name: API Server
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert any("url" in i for i in issues)

    def test_validate_missing_process_fields(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
health:
  processes:
    - port: 8000
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert any("name" in i for i in issues)

    def test_validate_misplaced_provider(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
build:
  framework: python
  provider: github-actions
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert any("pipeline.provider" in i for i in issues)

    def test_validate_invalid_iac_provider(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
infrastructure:
  provider: ansible
  cloud: aws
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert any("ansible" in i for i in issues)

    def test_validate_invalid_cloud(self, tmp_path):
        config_file = tmp_path / "cicd.yml"
        config_file.write_text(
            """
infrastructure:
  provider: terraform
  cloud: digitalocean
"""
        )
        issues = CICDConfig.validate_file(config_file)
        assert any("digitalocean" in i for i in issues)


class TestJsonSchema:
    """Test JSON Schema generation for IDE autocompletion."""

    def test_json_schema_output(self):
        schema_str = CICDConfig.json_schema()
        schema = json.loads(schema_str)
        assert schema["title"] == "CICDConfig"
        assert "properties" in schema
        assert "build" in schema["properties"]
        assert "health" in schema["properties"]
        assert "pipeline" in schema["properties"]
        assert "container" in schema["properties"]
        assert "infrastructure" in schema["properties"]

    def test_json_schema_nested_refs(self):
        schema_str = CICDConfig.json_schema()
        schema = json.loads(schema_str)
        # Pydantic v2 uses $defs for nested models
        assert "$defs" in schema
        assert "BuildConfig" in schema["$defs"]
        assert "HealthConfig" in schema["$defs"]


class TestCliValidate:
    """Test the validate CLI subcommand."""

    def test_validate_no_config(self, tmp_path):
        from lib.cicd.cli import main

        result = main(["validate", "--path", str(tmp_path)])
        assert result == 1

    def test_validate_valid_config(self, tmp_path):
        from lib.cicd.cli import main

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "cicd.yml").write_text("build:\n  framework: python\n")
        result = main(["validate", "--path", str(tmp_path)])
        assert result == 0

    def test_validate_json_output(self, tmp_path, capsys):
        from lib.cicd.cli import main

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "cicd.yml").write_text("build:\n  framework: python\n")
        result = main(["validate", "--path", str(tmp_path), "--json"])
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        assert output["valid"] is True
        assert output["issues"] == []

    def test_validate_schema_output(self, tmp_path, capsys):
        from lib.cicd.cli import main

        result = main(["validate", "--path", str(tmp_path), "--schema"])
        assert result == 0
        schema = json.loads(capsys.readouterr().out)
        assert "title" in schema
        assert schema["title"] == "CICDConfig"
