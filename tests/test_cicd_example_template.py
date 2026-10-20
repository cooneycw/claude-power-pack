"""Validate the documented health and smoke example against the real schema."""

from pathlib import Path

import yaml

from lib.cicd.config import CICDConfig


def _parse_health_yaml(text: str) -> CICDConfig:
    return CICDConfig.model_validate(yaml.safe_load(text))


def test_health_smoke_example() -> None:
    template = (Path(__file__).parents[1] / "templates" / "cicd.yml.example").read_text()
    start_marker = "# <cicd-example:health-start>"
    end_marker = "# <cicd-example:health-end>"
    assert start_marker in template, f"Marker not found: {start_marker}"
    assert end_marker in template, f"Marker not found: {end_marker}"

    start = template.index(start_marker) + len(start_marker)
    end = template.index(end_marker)
    assert end > start, "Health example markers are out of order"
    block = template[start:end]
    uncommented = "\n".join(
        line.removeprefix("#").removeprefix(" ") for line in block.splitlines()
    ).strip()
    assert uncommented, "Health example block is empty"

    data = yaml.safe_load(uncommented)
    assert isinstance(data, dict)
    assert set(data) == {"health"}
    config = _parse_health_yaml(uncommented)

    assert config.health.deploy_verification.enabled is True
    assert config.health.deploy_verification.baseline_file == ".claude/deploy-baseline.json"
    assert config.health.deploy_verification.on_latency_regression == "review"
    assert len(config.health.endpoints) > 0
    assert len(config.health.processes) > 0
    assert len(config.health.smoke_tests) > 0
    assert config.health.endpoints[0].url == "http://localhost:8000/health"
    assert config.health.smoke_tests[0].command == "curl -sf http://localhost:8000/health"
    assert config.health.processes[0].port == 8000
    assert config.health.processes[1].systemd_user_unit == "my-worker.service"


def test_pre_fix_schema_silently_drops_probes() -> None:
    old_schema = """
health:
  url: https://your-app.com/health
  timeout: 30
  expected_status: 200
  expected_body: '"status":"ok"'
smoke:
  tests:
    - name: "Homepage loads"
      url: https://your-app.com/
      expected_status: 200
"""

    config = _parse_health_yaml(old_schema)

    assert len(config.health.endpoints) == 0
    assert len(config.health.smoke_tests) == 0
