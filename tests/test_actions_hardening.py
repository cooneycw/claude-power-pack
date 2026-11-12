"""Structural hardening contracts for consumer Actions workflows (#1604).

CPP's own CI is Woodpecker; these checks inspect generated and static consumer
workflows without submitting jobs, fetching secrets or running a provider.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from lib.cicd import actions as action_pins
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
MAIN_PUSH_CONDITION = "github.ref == 'refs/heads/main' && github.event_name == 'push'"


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


def action_references(document: dict[str, Any]) -> list[str]:
    jobs = document["jobs"]
    return ([job["uses"] for job in jobs.values() if "uses" in job]
            + [step["uses"] for job in jobs.values() for step in job.get("steps", []) if "uses" in step])


def assert_shared_pins(document: dict[str, Any]) -> None:
    fields = ("CHECKOUT", "CACHE", "SETUP_PYTHON", "SETUP_NODE", "SETUP_GO", "SETUP_RUST",
              "AWS_CREDENTIALS", "AWS_SECRETS")
    values = [getattr(action_pins, field) for field in fields]
    assert all(re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", value) for value in values)
    registry = {value.split("@", 1)[0]: value for value in values}
    assert len(registry) == len(fields), "each action repository needs one canonical pin"
    references = action_references(document)
    assert references, "no action references examined"
    for reference in references:
        repository = reference.split("@", 1)[0]
        assert repository in registry
        assert reference == registry[repository]
    commands = [step["run"] for step in document["jobs"]["secret-scan"]["steps"] if "run" in step]
    images = [token for command in commands for token in shlex.split(command)
              if token.startswith("zricethezav/gitleaks:")]
    assert images and set(images) == {action_pins.GITLEAKS_IMAGE}


def assert_property(document: dict[str, Any], prop: str) -> None:
    jobs = document.get("jobs", {})
    assert jobs, "no workflow jobs examined"
    steps = [step for job in jobs.values() for step in job.get("steps", [])]
    checkouts = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
    assert checkouts, "no checkout steps examined"
    if prop == "remote_refs":
        actions = action_references(document)
        assert actions and all(isinstance(action, str) and
                               re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", action) for action in actions)
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
        assert all("token" not in step.get("with", {}) for step in checkouts)
    elif prop == "concurrency":
        policy = document.get("concurrency", {})
        assert "${{ github.workflow }}" in policy.get("group", "")
        assert "github.ref" in policy.get("group", "")
        assert "${{ github.sha }}" in policy.get("group", "")
        assert policy.get("cancel-in-progress", "false") == "false"
        for name, job in jobs.items():
            if name == "deploy":
                assert "concurrency" in job
            if "concurrency" in job:
                job_policy = job["concurrency"]
                assert isinstance(job_policy, dict) and job_policy.get("group")
                assert job_policy.get("cancel-in-progress", "false") == "false"
                if name == "deploy":
                    assert job_policy["group"] == "deploy-${{ github.repository }}-production"
                else:
                    assert "${{ github.sha }}" in job_policy["group"]
    elif prop == "timeouts":
        assert all(str(job.get("timeout-minutes", "")).isdigit()
                   and 0 < int(job["timeout-minutes"]) <= 360 for job in jobs.values())
    elif prop == "gitleaks":
        scan = jobs.get("secret-scan", {})
        # Extra execution context (container, env, services, defaults, etc.) can
        # replace Docker or change which repository the apparently safe scan sees.
        assert set(scan) <= {"runs-on", "timeout-minutes", "permissions", "steps"}
        assert scan.get("runs-on") == "ubuntu-latest" and "if" not in scan
        assert scan.get("continue-on-error", "false") == "false"
        # Ubuntu's implicit shell is the emitted policy. A custom/default shell
        # such as echo {0} can report success without executing the script.
        assert "shell" not in document.get("defaults", {}).get("run", {})
        assert "shell" not in scan.get("defaults", {}).get("run", {})
        scan_steps = scan.get("steps", [])
        assert all("shell" not in step for step in scan_steps if "run" in step)
        assert all("if" not in step and step.get("continue-on-error", "false") == "false" for step in scan_steps)
        commands = [step["run"].strip() for step in scan_steps if "run" in step]
        assert len(commands) == 1
        runs = commands[0]
        tokens = shlex.split(runs)
        assert tokens[:2] == ["docker", "run"]
        image_positions = [index for index, token in enumerate(tokens) if token.startswith("zricethezav/gitleaks:")]
        assert len(image_positions) == 1
        # Keep the actual scanner invocation closed: --exit-code 0, --help,
        # --log-opts and similar options can turn a successful process into a
        # non-enforcing scan even when its redaction/image checks still match.
        assert tokens[image_positions[0] + 1:] == ["detect", "--source=/repo", "--redact", "--no-banner"]
        assert not re.search(r"[|&;\n]", runs), "scan command must not mask its failure with shell control flow"
        assert re.search(r"zricethezav/gitleaks:[\w.]+@sha256:[0-9a-f]{64}", runs)
        assert "--redact" in runs and "--no-git" not in runs
        checkout = next(step for step in scan["steps"] if step.get("uses", "").startswith("actions/checkout@"))
        assert set(checkout["with"]) == {"fetch-depth", "persist-credentials"}
        assert checkout["with"]["fetch-depth"] == "0"
        if "deploy" in jobs:
            needs = jobs["deploy"].get("needs", [])
            dependencies = [needs] if isinstance(needs, str) else needs
            assert "secret-scan" in dependencies
            if "ci" in jobs:
                assert "ci" in dependencies
    elif prop == "deploy_environment":
        assert jobs.get("deploy", {}).get("environment") == "production"
        condition = jobs["deploy"].get("if", "")
        assert condition == MAIN_PUSH_CONDITION or (
            condition == "github.event_name == 'push'" and document["on"].get("push", {}).get("branches") == ["main"]
        )
    elif prop == "uv_version":
        runs = "\n".join(step.get("run", "") for step in steps)
        assert re.search(r"pip install uv==\d+\.\d+\.\d+(?:\s|$)", runs)
        assert not re.search(r"pip install uv(?:\s|$)", runs)
    elif prop == "pin_registry":
        assert_shared_pins(document)
    elif prop == "safe_trigger":
        assert "on" in document
        assert isinstance(document["on"], dict) and document["on"]
        assert set(document["on"]) <= {"push", "pull_request", "workflow_dispatch"}
    else:
        raise AssertionError("unexamined property: " + prop)


@pytest.mark.parametrize("sample,prop", CASES, ids=[sample + "-" + prop for sample, prop in CASES])
def test_consumer_workflow_hardening(sample: str, prop: str):
    assert_property(workflow(sample), prop)


# Each fixture changes one property of its applicable GOOD workflow. The reusable
# workflow case checks only reference immutability, not the callee's policy.
# These are committed assertion controls, not an additional product gate.
FIXTURES = ROOT / "tests/fixtures/actions-hardening"
BAD_CASES = json.loads((FIXTURES / "cases.json").read_text())


@pytest.mark.parametrize("case", BAD_CASES, ids=[case["file"] for case in BAD_CASES])
def test_bad_fixture_is_detected_and_repair_removes_detection(case):
    good = yaml.load((FIXTURES / case.get("good_file", "good.yml")).read_text(), Loader=yaml.BaseLoader)
    bad = yaml.load((FIXTURES / case["file"]).read_text(), Loader=yaml.BaseLoader)
    bad_parent, good_parent = bad, good
    for key in case["path"][:-1]:
        bad_parent, good_parent = bad_parent[key], good_parent[key]
    key = case["path"][-1]
    if case.get("missing"):
        assert key not in bad_parent and key in good_parent, "fixture must omit the required field"
    else:
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
    for prop in COMMON + ["deploy_environment", "uv_version", "pin_registry"]:
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



def test_main_commit_concurrency_groups_are_distinct():
    template = workflow("generated-python")["concurrency"]["group"]
    groups = []
    for sha in ("a" * 40, "b" * 40, "c" * 40):
        group = template
        for expression, value in {
            "${{ github.workflow }}": "CI", "${{ github.ref }}": "refs/heads/main",
            "${{ github.event.pull_request.number || github.ref }}": "refs/heads/main",
            "${{ github.sha }}": sha,
        }.items():
            group = group.replace(expression, value)
        assert "${{" not in group, "concurrency expression was not examined"
        groups.append(group)
    assert len(set(groups)) == 3, "main commits must not share GitHub's one-pending-run queue"



@pytest.mark.parametrize("sample", [name for name in SAMPLES if name.startswith("static-")])
def test_static_actions_and_scanner_match_canonical_pins(sample):
    assert_shared_pins(workflow(sample))


@pytest.mark.parametrize("sample", ["generated-python", "static-deploy"])
def test_dedicated_deploy_serializes_commits_without_cancelling_active(sample):
    policy = workflow(sample)["jobs"]["deploy"].get("concurrency", {})
    assert policy.get("cancel-in-progress") == "false"
    assert policy.get("group") == "deploy-${{ github.repository }}-production"
    groups = [policy["group"].replace("${{ github.repository }}", "O/R").replace("${{ github.sha }}", sha)
              for sha in ("a" * 40, "b" * 40, "c" * 40)]
    assert len(set(groups)) == 1, "production deploys from different commits need the same queue"


@pytest.mark.skipif(shutil.which("bash") is None, reason="fixture control uses Bash")
def test_ignored_exit_fixture_is_valid_shell_and_masks_a_real_failure(tmp_path):
    fixture = yaml.load((FIXTURES / "bad-18-scan-ignore-exit.yml").read_text(), Loader=yaml.BaseLoader)
    command = fixture["jobs"]["secret-scan"]["steps"][1]["run"]
    syntax = subprocess.run(["bash", "-n", "-c", command], capture_output=True, text=True, timeout=10)
    assert syntax.returncode == 0, syntax.stderr
    docker = tmp_path / "docker"
    marker = tmp_path / "scanner-ran"
    docker.write_text('#!/bin/sh\nprintf ran > "$SCANNER_MARKER"\nexit 5\n')
    docker.chmod(0o755)
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
           "SCANNER_MARKER": str(marker)}
    assert shutil.which("docker", path=env["PATH"]) == str(docker)
    result = subprocess.run(["bash", "-e", "-c", command], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert marker.read_text() == "ran", "owned scanner failure must actually execute"
    assert result.returncode == 0, "the BAD fixture must swallow the scanner's exit 5"


# --- generated INFRASTRUCTURE workflows (issue #1712, seq 695) ---------------
#
# These were absent from SAMPLES above, which is how `actions/checkout@v4`, a
# moving ref, stayed in `lib/cicd/infrastructure.py` under a test that forbids
# moving refs. They join here for the pin. The other COMMON properties
# (permissions, timeouts, checkout credentials, concurrency) are NOT asserted
# for them yet: the infra generator does not have them, which is issue #1756.

INFRA_TIERS = ("foundation", "platform", "app")


@pytest.mark.parametrize("tier", INFRA_TIERS)
def test_a_generated_infra_workflow_references_actions_only_through_the_shared_pins(tier: str) -> None:
    from lib.cicd.infrastructure import generate_infra_pipeline

    generated = generate_infra_pipeline(provider="github-actions")
    text = generated[f".github/workflows/infra-{tier}.yml"]
    references = action_references(yaml.load(text, Loader=yaml.BaseLoader))
    assert references, "no action references examined"
    registry = {
        value.split("@", 1)[0]: value
        for value in vars(action_pins).values()
        if isinstance(value, str) and re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", value)
    }
    for reference in references:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", reference), f"{reference} is not pinned to a commit"
        assert reference == registry.get(reference.split("@", 1)[0]), f"{reference} is not the shared pin"


def test_the_woodpecker_infra_pipelines_reference_no_github_action() -> None:
    """CI provider, the other value: nothing to pin there, and that is checked, not assumed."""
    from lib.cicd.infrastructure import generate_infra_pipeline

    generated = generate_infra_pipeline(provider="woodpecker")
    assert generated, "the Woodpecker infra generator produced nothing - this test examined no file"
    for name, text in generated.items():
        assert "uses:" not in text and "actions/" not in text, f"{name} references a GitHub action"
