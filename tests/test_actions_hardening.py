"""Structural hardening contracts for consumer Actions workflows (#1604).

CPP's own CI is Woodpecker; these checks inspect generated and static consumer
workflows without submitting jobs, fetching secrets or running a provider.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from lib.cicd.config import CICDConfig
from lib.cicd.models import Framework, FrameworkInfo, PackageManager
from lib.cicd.pipeline import generate_github_actions

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORKS = {
    "python": (Framework.PYTHON, PackageManager.UV),
    "node": (Framework.NODE, PackageManager.NPM),
    "go": (Framework.GO, PackageManager.GO),
    "rust": (Framework.RUST, PackageManager.CARGO),
    "powershell": (Framework.POWERSHELL, PackageManager.PSRESOURCEGET),
    "unknown": (Framework.UNKNOWN, PackageManager.UNKNOWN),
}
SAMPLES = ["generated-" + name for name in FRAMEWORKS] + [
    "static-ci-python", "static-ci-node", "static-ci-go", "static-ci-rust", "static-ci-powershell", "static-deploy",
]
COMMON = ["remote_refs", "permissions", "checkout_credentials", "concurrency", "timeouts", "gitleaks", "safe_trigger"]
CASES = [(sample, prop) for sample in SAMPLES for prop in COMMON]
CASES += [(sample, "deploy_environment") for sample in SAMPLES
          if sample.startswith("generated-") or sample == "static-deploy"]
CASES += [(sample, "uv_version") for sample in ("generated-python", "static-ci-python")]
CANCEL_PULL_REQUEST = "${{ github.event_name == 'pull_request' }}"


def workflow(sample: str) -> dict[str, Any]:
    if sample.startswith("generated-"):
        framework, manager = FRAMEWORKS[sample.removeprefix("generated-")]
        config = CICDConfig.model_validate({"pipeline": {
            "providers": ["github-actions"], "branches": {"main": ["lint", "test", "deploy"], "pr": ["lint", "test"]},
            "secrets_source": "aws-secrets-manager", "aws_secret_name": "consumer-deploy",
        }})
        config._cpp_revision = "a" * 40
        text = generate_github_actions(FrameworkInfo(framework, manager), config)
    else:
        text = (ROOT / "templates/workflows" / (sample.removeprefix("static-") + ".yml")).read_text()
    return yaml.load(text, Loader=yaml.BaseLoader)


def assert_property(document: dict[str, Any], prop: str) -> None:
    jobs = document.get("jobs", {})
    assert jobs, "no workflow jobs examined"
    steps = [step for job in jobs.values() for step in job.get("steps", [])]
    checkouts = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
    assert checkouts, "no checkout steps examined"
    if prop == "remote_refs":
        actions = [step["uses"] for step in steps if "uses" in step]
        assert actions and all(re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action) for action in actions)
    elif prop == "permissions":
        assert document.get("permissions") == {"contents": "read"}
        for name, job in jobs.items():
            grants = job.get("permissions", document["permissions"])
            assert grants in ({"contents": "read"}, {"contents": "read", "id-token": "write"})
            if "id-token" in grants:
                assert name == "deploy"
                assert any(step.get("uses", "").startswith("aws-actions/configure-aws-credentials@")
                           for step in job.get("steps", []))
    elif prop == "checkout_credentials":
        assert all(step.get("with", {}).get("persist-credentials") == "false" for step in checkouts)
    elif prop == "concurrency":
        policy = document.get("concurrency", {})
        assert "${{ github.workflow }}" in policy.get("group", "")
        assert "github.ref" in policy.get("group", "")
        assert policy.get("cancel-in-progress") == CANCEL_PULL_REQUEST
    elif prop == "timeouts":
        assert all(str(job.get("timeout-minutes", "")).isdigit()
                   and 0 < int(job["timeout-minutes"]) <= 360 for job in jobs.values())
    elif prop == "gitleaks":
        scan = jobs.get("secret-scan", {})
        assert scan.get("runs-on") == "ubuntu-latest" and not scan.get("if")
        runs = "\n".join(step.get("run", "") for step in scan.get("steps", []))
        assert re.search(r"zricethezav/gitleaks:[\w.]+@sha256:[0-9a-f]{64}", runs)
        assert "--redact" in runs and "--no-git" not in runs
        checkout = next(step for step in scan["steps"] if step.get("uses", "").startswith("actions/checkout@"))
        assert checkout["with"]["fetch-depth"] == "0"
        if "deploy" in jobs:
            assert "secret-scan" in jobs["deploy"].get("needs", [])
    elif prop == "deploy_environment":
        assert jobs.get("deploy", {}).get("environment") == "production"
        assert "github.event_name == 'push'" in jobs["deploy"].get("if", "")
    elif prop == "uv_version":
        runs = "\n".join(step.get("run", "") for step in steps)
        assert re.search(r"pip install uv==\d+\.\d+\.\d+(?:\s|$)", runs)
        assert not re.search(r"pip install uv(?:\s|$)", runs)
    elif prop == "safe_trigger":
        assert "on" in document
        assert "pull_request_target" not in document["on"]
    else:
        raise AssertionError("unexamined property: " + prop)


@pytest.mark.parametrize("sample,prop", CASES, ids=[sample + "-" + prop for sample, prop in CASES])
def test_consumer_workflow_hardening(sample: str, prop: str):
    assert_property(workflow(sample), prop)


# Each fixture changes exactly one property of a fully hardened workflow. These
# are committed BAD/GOOD assertion controls, not an additional product gate.
FIXTURES = ROOT / "tests/fixtures/actions-hardening"
BAD_CASES = json.loads((FIXTURES / "cases.json").read_text())


@pytest.mark.parametrize("case", BAD_CASES, ids=[case["file"] for case in BAD_CASES])
def test_bad_fixture_is_detected_and_repair_removes_detection(case):
    good = yaml.load((FIXTURES / "good.yml").read_text(), Loader=yaml.BaseLoader)
    bad = yaml.load((FIXTURES / case["file"]).read_text(), Loader=yaml.BaseLoader)
    bad_parent, good_parent = bad, good
    for key in case["path"][:-1]:
        bad_parent, good_parent = bad_parent[key], good_parent[key]
    key = case["path"][-1]
    assert bad_parent[key] == case["bad_value"], "the planted defect is absent"
    assert case["remove_to_fix"] or bad_parent[key] != good_parent[key]
    with pytest.raises(AssertionError):
        assert_property(bad, case["property"])
    fixed = copy.deepcopy(bad)
    parent = fixed
    for component in case["path"][:-1]:
        parent = parent[component]
    if case["remove_to_fix"]:
        del parent[key]
    else:
        parent[key] = good_parent[key]
    assert fixed == good, "repair must remove only the planted defect"
    assert_property(fixed, case["property"])


def test_good_fixture_covers_every_hardening_property():
    good = yaml.load((FIXTURES / "good.yml").read_text(), Loader=yaml.BaseLoader)
    for prop in COMMON + ["deploy_environment", "uv_version"]:
        assert_property(good, prop)


def test_platform_deploy_has_no_oidc_grant():
    config = CICDConfig.model_validate({"pipeline": {
        "providers": ["github-actions"], "branches": {"main": ["deploy"], "pr": ["test"]},
        "secrets_source": "platform",
    }})
    text = generate_github_actions(FrameworkInfo(Framework.PYTHON, PackageManager.UV), config)
    document = yaml.load(text, Loader=yaml.BaseLoader)
    assert_property(document, "permissions")
    assert all("id-token" not in job.get("permissions", document["permissions"])
               for job in document["jobs"].values())


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("id") is None,
                    reason="scanner command harness uses bash and id")
@pytest.mark.parametrize("scanner_exit", [0, 1, 5])
def test_scanner_command_preserves_exit_and_mounts_read_only(tmp_path, scanner_exit):
    directory = tmp_path / "bin"
    directory.mkdir()
    docker = directory / "docker"
    docker.write_text('#!/bin/sh\nprintf \'%s\\0\' "$@" > "$DOCKER_ARGS"\nexit "$DOCKER_EXIT"\n')
    docker.chmod(0o755)
    workspace = tmp_path / "consumer with space"
    workspace.mkdir()
    arguments_file = tmp_path / "docker-arguments"
    env = {**os.environ, "PATH": str(directory) + os.pathsep + os.environ.get("PATH", ""),
           "DOCKER_ARGS": str(arguments_file), "DOCKER_EXIT": str(scanner_exit)}
    assert shutil.which("docker", path=env["PATH"]) == str(docker), "must use the owned Docker stub"
    command = workflow("generated-python")["jobs"]["secret-scan"]["steps"][1]["run"]
    result = subprocess.run(["bash", "-e", "-c", command], env=env, cwd=workspace,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == scanner_exit, result.stdout + result.stderr
    arguments = arguments_file.read_bytes().decode().split("\0")[:-1]
    assert arguments[arguments.index("-v") + 1] == str(workspace) + ":/repo:ro"
    assert re.fullmatch(r"\d+:\d+", arguments[arguments.index("--user") + 1])
    assert arguments[arguments.index("--env") + 1] == "HOME=/tmp"
    assert "--redact" in arguments and "--no-git" not in arguments
