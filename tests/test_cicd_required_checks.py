"""PR-required contexts come from emitted pipelines, not provider guesses."""

import json
from pathlib import Path

import pytest

from lib.cicd.config import CICDConfig, InfrastructureConfig
from lib.cicd.infrastructure import generate_infra_pipeline
from lib.cicd.models import Framework, FrameworkInfo, PackageManager
from lib.cicd.pipeline import generate_pipeline


def test_infra_recorded_provider_list_generates_both(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    path = tmp_path / ".claude/cicd.yml"
    path.parent.mkdir()
    path.write_text("pipeline:\n  providers: [woodpecker, github-actions]\n")
    assert main(["infra-pipeline", "--path", str(tmp_path), "--json"]) == 0
    files = json.loads(capsys.readouterr().out)["files"]
    assert any(name.startswith(".woodpecker/") for name in files)
    assert any(name.startswith(".github/workflows/") for name in files)


def test_infra_legacy_both_never_silently_selects_woodpecker():
    files = generate_infra_pipeline(InfrastructureConfig(), "both")
    assert any(name.startswith(".woodpecker/") for name in files)
    assert any(name.startswith(".github/workflows/") for name in files)


@pytest.mark.parametrize("providers,expected", [
    (["github-actions"], ["ci (3.11)", "ci (3.12)"]),
    (["woodpecker"], ["ci/woodpecker/pr/woodpecker"]),
    (["woodpecker", "github-actions"], ["ci (3.11)", "ci (3.12)", "ci/woodpecker/pr/woodpecker"]),
])
def test_generated_checks_expand_matrix_and_exclude_push_only(providers, expected):
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": providers}})
    info = FrameworkInfo(Framework.PYTHON, PackageManager.UV)
    files = generate_pipeline(info, config)
    result = derive_required_checks(providers, files)
    assert result.status == "known", result.reason
    assert list(result.checks) == expected
    assert result.examined_files == len(files)


def test_wrong_provider_and_push_context_are_committed_bad_postures():
    from lib.cicd.checks import check_posture, derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["woodpecker"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    result = derive_required_checks(config.pipeline.providers, files)
    good = {"branch": "main", "protection": {"required_status_checks": {"contexts": list(result.checks)}}}
    assert check_posture(result, good)["status"] == "ok"
    for bad in ("ci", "ci/woodpecker/push/woodpecker"):
        posture = {"branch": "main", "protection": {"required_status_checks": {"contexts": [bad]}}}
        assert check_posture(result, posture)["status"] == "drift"


def test_unreadable_population_never_reports_consistent():
    from lib.cicd.checks import check_posture, derive_required_checks
    result = derive_required_checks(["github-actions"], {})
    assert result.status == "unknown"
    assert check_posture(result, {"protection": {"required_status_checks": {"contexts": []}}})["status"] == "unknown"


def test_dynamic_matrix_is_unknown():
    import yaml

    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["github-actions"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    assert derive_required_checks(["github-actions"], files).status == "known"
    data = yaml.load(files[".github/workflows/ci.yml"], Loader=yaml.BaseLoader)
    data["jobs"]["ci"]["strategy"]["matrix"] = "${{ fromJSON(needs.plan.outputs.matrix) }}"
    assert isinstance(data["jobs"]["ci"]["strategy"]["matrix"], str)
    files[".github/workflows/ci.yml"] = yaml.safe_dump(data)
    assert derive_required_checks(["github-actions"], files).status == "unknown"


@pytest.mark.parametrize("providers", ["github-actions", "woodpecker", "github-actions,woodpecker"])
def test_offline_project_setup_and_resume(  # binary-guard: allow intercepted sentinel
    tmp_path: Path, monkeypatch, capsys, providers
):
    import subprocess

    from lib.cicd.cli import main

    class NoExternalCommands(RuntimeError):
        pass

    def no_external_command(*args, **kwargs):
        raise NoExternalCommands("offline setup guard")

    monkeypatch.setattr(subprocess, "run", no_external_command)
    with pytest.raises(NoExternalCommands, match="offline setup guard"):
        subprocess.run(["fixture-no-external-commands"])
    (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="0.1.0"\n')
    args = ["pipeline", "--path", str(tmp_path), "--providers", providers,
            "--record", "--protection", "--write", "--json"]
    assert main(args) == 0
    generated = json.loads(capsys.readouterr().out)
    assert generated["written"] is True
    assert generated["required_checks"]["status"] == "known"
    for name in providers.split(","):
        assert generated["host_capability"][name] == {
            "status": "unknown", "reason": "host record unavailable (#1609)"
        }
    posture = json.loads((tmp_path / ".claude/branch-protection.json").read_text())
    assert posture["protection"]["required_status_checks"]["contexts"] == generated["required_checks"]["checks"]
    assert main(["checks", "--path", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["consistency"]["status"] == "ok"
    # Presence is insufficient: a tampered posture must stop a resumed setup.
    posture["protection"]["required_status_checks"]["contexts"] = ["foreign-check"]
    (tmp_path / ".claude/branch-protection.json").write_text(json.dumps(posture))
    assert main(["checks", "--path", str(tmp_path), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["consistency"]["status"] == "drift"


def test_directory_woodpecker_names_one_pr_context_per_file():
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["woodpecker"]}})
    emitted = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)[".woodpecker.yml"]
    files = {".woodpecker/lint.yml": emitted, ".woodpecker/test.yml": emitted}
    result = derive_required_checks(["woodpecker"], files)
    assert result.status == "known"
    assert result.checks == ("ci/woodpecker/pr/lint", "ci/woodpecker/pr/test")


def test_conditional_paths_cannot_be_required_for_every_pr():
    from lib.cicd.checks import derive_required_checks
    files = generate_infra_pipeline(InfrastructureConfig(), "both")
    result = derive_required_checks(["github-actions", "woodpecker"], files)
    assert result.status == "unknown" and not result.checks


def test_push_only_pipeline_is_unknown_not_an_empty_clean_population():
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["woodpecker"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    assert "event: [push, pull_request]" in files[".woodpecker.yml"]
    files[".woodpecker.yml"] = files[".woodpecker.yml"].replace("event: [push, pull_request]", "event: push")
    assert derive_required_checks(["woodpecker"], files).status == "unknown"


def test_duplicate_jobs_are_not_a_known_check_population():
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["github-actions"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    assert derive_required_checks(["github-actions"], files).status == "known"
    files[".github/workflows/ci.yml"] += "  ci: {runs-on: ubuntu-latest, steps: [{run: 'true'}]}\n"
    assert files[".github/workflows/ci.yml"].count("  ci:") == 2
    assert derive_required_checks(["github-actions"], files).status == "unknown"


def test_incomplete_job_is_not_a_known_check_population():
    from lib.cicd.checks import derive_required_checks
    files = {".github/workflows/ci.yml": "on: [pull_request]\njobs: {ci: {}}\n"}
    assert derive_required_checks(["github-actions"], files).status == "unknown"


def test_known_label_cannot_make_zero_contexts_clean():
    from lib.cicd.checks import RequiredChecks, check_posture, protection_record
    empty = RequiredChecks("known")
    posture = {"branch": "main", "protection": {"required_status_checks": {"contexts": []}}}
    assert check_posture(empty, posture)["status"] == "unknown"
    with pytest.raises(ValueError):
        protection_record(CICDConfig(), empty)


def test_hardened_generated_woodpecker_remains_supported():
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["woodpecker"],
        "woodpecker": {"secret_scan": True, "image_security": True, "runtime_smoke": True}}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    result = derive_required_checks(config.pipeline.providers, files)
    assert result.status == "known", result.reason


def test_disagreeing_explicit_policy_refuses_local_generation(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text("pipeline:\n  providers: [woodpecker]\nbranch_protection:\n  require_status_checks: [foreign]\n")
    assert main(["pipeline", "--path", str(tmp_path), "--protection", "--write"]) == 2
    assert "disagrees" in capsys.readouterr().err
    assert not (tmp_path / ".woodpecker.yml").exists()
    assert not (tmp_path / ".claude/branch-protection.json").exists()


def test_provider_registry_supplies_prompt_choices(tmp_path: Path, capsys):
    from lib.cicd.cli import main
    from lib.cicd.providers import PROVIDERS
    assert main(["provider", "--registry", "--path", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["registered_providers"] == list(PROVIDERS)


def test_invalid_pull_request_trigger_is_unknown():
    from lib.cicd.checks import derive_required_checks
    files = {".github/workflows/ci.yml":
             "on:\n  pull_request: []\njobs:\n  ci:\n    runs-on: ubuntu-latest\n    steps: [{run: 'true'}]\n"}
    assert derive_required_checks(["github-actions"], files).status == "unknown"


def test_each_selected_provider_must_establish_pr_population():
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["github-actions", "woodpecker"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    assert derive_required_checks(config.pipeline.providers, files).status == "known"
    assert "event: [push, pull_request]" in files[".woodpecker.yml"]
    files[".woodpecker.yml"] = files[".woodpecker.yml"].replace("event: [push, pull_request]", "event: push")
    assert derive_required_checks(config.pipeline.providers, files).status == "unknown"


def test_protection_for_wrong_branch_is_drift():
    from lib.cicd.checks import check_posture, derive_required_checks, protection_record
    config = CICDConfig.model_validate({"pipeline": {"providers": ["woodpecker"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    result = derive_required_checks(config.pipeline.providers, files)
    posture = protection_record(config, result)
    assert check_posture(result, posture)["status"] == "ok"
    posture["branch"] = "develop"
    assert check_posture(result, posture)["status"] == "drift"


@pytest.mark.parametrize("trigger", ["push: []", "push: broken", "workflow_dispatch: []"])
def test_invalid_sibling_trigger_is_unknown(trigger):
    from lib.cicd.checks import derive_required_checks
    files = {".github/workflows/ci.yml":
             ("on:\n  pull_request:\n  " + trigger +
              "\njobs:\n  ci:\n    runs-on: ubuntu-latest\n    steps: [{run: 'true'}]\n")}
    assert derive_required_checks(["github-actions"], files).status == "unknown"


def test_unverifiable_check_app_binding_is_unknown():
    from lib.cicd.checks import check_posture, derive_required_checks, protection_record
    config = CICDConfig.model_validate({"pipeline": {"providers": ["woodpecker"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    result = derive_required_checks(config.pipeline.providers, files)
    posture = protection_record(config, result)
    posture["protection"]["required_status_checks"] = {"checks": [{"context": result.checks[0]}]}
    assert check_posture(result, posture)["status"] == "ok"
    posture["protection"]["required_status_checks"]["checks"][0]["app_id"] = 12345
    assert check_posture(result, posture)["status"] == "unknown"


def test_explicit_matrix_name_is_outside_supported_generated_shape():
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig.model_validate({"pipeline": {"providers": ["github-actions"]}})
    files = generate_pipeline(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    assert derive_required_checks(config.pipeline.providers, files).status == "known"
    assert "  ci:\n" in files[".github/workflows/ci.yml"]
    files[".github/workflows/ci.yml"] = files[".github/workflows/ci.yml"].replace("  ci:\n", "  ci:\n    name: Test\n")
    assert derive_required_checks(config.pipeline.providers, files).status == "unknown"


def test_mutually_exclusive_sibling_filters_are_unknown():
    from lib.cicd.checks import derive_required_checks
    files = {".github/workflows/ci.yml": """on:
  pull_request:
  push:
    paths: [lib/**]
    paths-ignore: [docs/**]
jobs:
  ci:
    runs-on: ubuntu-latest
    steps: [{run: 'true'}]
"""}
    assert derive_required_checks(["github-actions"], files).status == "unknown"
