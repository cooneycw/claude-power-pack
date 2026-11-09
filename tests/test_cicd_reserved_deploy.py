"""Reserved deployment targets must stay inside the provider's deploy stage."""

import pytest
import yaml

from lib.cicd.config import CICDConfig
from lib.cicd.models import Framework, FrameworkInfo, PackageManager
from lib.cicd.pipeline import generate_github_actions, generate_woodpecker


def _info() -> FrameworkInfo:
    return FrameworkInfo(
        framework=Framework.PYTHON, package_manager=PackageManager.UV,
        detected_files=[], recommended_targets=[], runner_commands={},
        secondary_frameworks=[],
    )


@pytest.mark.parametrize("branches,expected", [
    ({"main": ["lint", "deploy"], "pr": []}, ["lint"]),
    ({"main": ["deploy"], "pr": []}, []),
    ({"main": ["lint", "deploy"]}, ["lint"]),
    ({"main": ["deploy"]}, []),
    ({"main": ["lint", "test", "deploy"], "pr": ["lint", "test"]}, ["lint", "test"]),
])
@pytest.mark.parametrize("secrets_source", ["platform", "aws-secrets-manager"])
def test_actions_deploy_is_exclusive_and_serialized(branches, expected, secrets_source):
    config = CICDConfig()
    config.pipeline.branches = branches
    config.pipeline.secrets_source = secrets_source
    document = yaml.safe_load(generate_github_actions(_info(), config))
    jobs = document["jobs"]
    calls = [(name, step["run"]) for name, job in jobs.items()
             for step in job.get("steps", []) if "run" in step and "make deploy" in step["run"]]
    assert calls == [("deploy", "make deploy")]
    targets = [step["run"] for step in jobs["ci"]["steps"]
               if step.get("run", "").startswith("make ")]
    assert targets == [f"make {target}" for target in expected]
    assert jobs["ci"]["steps"], "deploy-only still has a valid setup-only prerequisite"
    assert jobs["deploy"]["needs"] == ["ci", "secret-scan"]
    assert jobs["deploy"]["environment"] == "production"
    assert jobs["deploy"]["if"] == "github.ref == 'refs/heads/main' && github.event_name == 'push'"
    assert jobs["deploy"]["concurrency"] == {
        "group": "deploy-${{ github.repository }}-production", "cancel-in-progress": False,
    }
    assert "github.sha" in document["concurrency"]["group"]


@pytest.mark.parametrize("branches,expected", [
    ({"main": ["lint", "deploy"], "pr": []}, ["lint"]),
    ({"main": ["deploy"], "pr": []}, []),
    ({"main": ["lint", "deploy"]}, ["lint"]),
    ({"main": ["deploy"]}, []),
    ({"main": ["lint", "test", "deploy"], "pr": ["lint", "test"]}, ["lint", "test"]),
])
@pytest.mark.parametrize("secrets_source", ["platform", "aws-secrets-manager"])
def test_woodpecker_deploy_is_exclusive(branches, expected, secrets_source):
    config = CICDConfig()
    config.pipeline.branches = branches
    config.pipeline.secrets_source = secrets_source
    steps = yaml.safe_load(generate_woodpecker(_info(), config))["steps"]
    names = [step["name"] for step in steps]
    assert len(names) == len(set(names)), "generic and dedicated stages must not collide"
    calls = [(step["name"], command) for step in steps for command in step.get("commands", [])
             if "make deploy" in command]
    assert len(calls) == 1 and calls[0][0] == "deploy"
    targets = [command for step in steps if step["name"] != "deploy"
               for command in step.get("commands", []) if command.startswith("make ")]
    assert targets == [f"make {target}" for target in expected]
    deploy = next(step for step in steps if step["name"] == "deploy")
    assert deploy["when"] == {"branch": "main", "event": "push"}
    for step in steps:
        if step["name"] in expected and not branches.get("pr"):
            assert step["when"]["event"] == "push"


@pytest.mark.parametrize("generator", [generate_github_actions, generate_woodpecker])
@pytest.mark.parametrize("main", [[], ["deploy"]])
def test_pr_deploy_is_rejected_with_configuration_fix(generator, main):
    config = CICDConfig()
    config.pipeline.branches = {"main": main, "pr": ["lint", "deploy"]}
    with pytest.raises(ValueError, match=r"pipeline\.branches\.pr.*pipeline\.branches\.main"):
        generator(_info(), config)


def test_woodpecker_runtime_smoke_cannot_alias_deploy():
    config = CICDConfig()
    config.pipeline.woodpecker.runtime_smoke = True
    config.pipeline.woodpecker.smoke_target = "deploy"
    with pytest.raises(ValueError, match=r"pipeline\.woodpecker\.smoke_target.*pipeline\.branches\.main"):
        generate_woodpecker(_info(), config)


@pytest.mark.parametrize("generator", [generate_github_actions, generate_woodpecker])
@pytest.mark.parametrize("branch", ["main", "pr"])
@pytest.mark.parametrize("target", ["lint deploy", "lint;make deploy", "-fdeploy"])
def test_application_entries_are_single_make_targets(generator, branch, target):
    config = CICDConfig()
    config.pipeline.branches = {branch: [target]}
    with pytest.raises(ValueError, match=rf"pipeline\.branches\.{branch}.*single.*target"):
        generator(_info(), config)


def test_programmatic_smoke_target_cannot_be_compound():
    config = CICDConfig()
    config.pipeline.woodpecker.runtime_smoke = True
    # Assignment bypasses the model's load-time shell-token validator.
    config.pipeline.woodpecker.smoke_target = "deploy lint"
    with pytest.raises(ValueError, match=r"pipeline\.woodpecker\.smoke_target.*single.*target"):
        generate_woodpecker(_info(), config)
