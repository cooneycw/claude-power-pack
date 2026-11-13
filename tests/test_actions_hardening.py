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
# Infrastructure has its own job/command population and approval model. Check
# its applicable properties explicitly rather than inheriting application-only
# secret-scan/deploy assumptions from COMMON (#1756).

INFRA_TIERS = ("foundation", "platform", "app")
INFRA_TOOLS = ("terraform", "pulumi", "bicep")
INFRA_LIMIT = "# Timeout is a Woodpecker project setting; configure it before running infrastructure jobs."


def infra_commands(tool: str, azure_location: str) -> tuple[str, str, str]:
    """Independent expected command contract, including provider substitution."""
    return {
        "terraform": ("terraform init", "terraform plan -out=tfplan", "terraform apply tfplan"),
        "pulumi": ("pip install -r requirements.txt", "pulumi preview", "pulumi up --yes"),
        "bicep": ("az bicep install",
                  f"az deployment sub what-if --location {azure_location} --template-file main.bicep",
                  f"az deployment sub create --location {azure_location} --template-file main.bicep"),
    }[tool]


def assert_infra_property(document: dict[str, Any], provider: str, tool: str, prop: str) -> None:
    assert provider in {"github-actions", "woodpecker"} and tool in INFRA_TOOLS
    if provider == "github-actions":
        jobs = document.get("jobs", {})
        assert set(jobs) == {"plan", "apply"}, "infra plan/apply jobs must be examined"
        if prop in {"permissions", "timeouts", "checkout_credentials"}:
            assert_property(document, prop)
            if prop == "permissions":
                assert all(job.get("permissions") == {"contents": "read"} for job in jobs.values())
            elif prop == "timeouts":
                assert jobs["plan"]["timeout-minutes"] == "30"
                assert jobs["apply"]["timeout-minutes"] == "120"
            else:
                for job in jobs.values():
                    assert any(step.get("uses", "").startswith("actions/checkout@")
                               for step in job.get("steps", []))
            return
        assert prop == "iac_commands", "unexamined infra property: " + prop
        init, plan, apply = infra_commands(tool, "${{ vars.AZURE_LOCATION }}")
        for phase, job in jobs.items():
            commands = [step["run"] for step in job.get("steps", []) if "run" in step]
            assert commands == ([init, plan] if phase == "plan" else [init, plan, apply])
    else:
        steps = document.get("steps", [])
        assert isinstance(steps, list) and steps, "no infrastructure steps examined"
        assert all(isinstance(step, dict) for step in steps)
        if prop == "image_pinning":
            for step in steps:
                assert re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", step.get("image", "")), step.get("image")
            return
        assert prop == "iac_commands", "unexamined infra property: " + prop
        init, plan, apply = infra_commands(tool, '"$${AZURE_LOCATION:?set AZURE_LOCATION}"')
        assert any(step.get("name", "").startswith("plan-") for step in steps)
        for step in steps:
            phase, separator, tier = step.get("name", "").partition("-")
            assert separator and tier in INFRA_TIERS and phase in {"plan", "apply"}
            assert step.get("commands") == [f"cd infra/{tier}", init, plan if phase == "plan" else apply]


@pytest.mark.parametrize("tool", INFRA_TOOLS)
@pytest.mark.parametrize("tier", INFRA_TIERS)
@pytest.mark.parametrize("provider,prop", [
    ("github-actions", "permissions"), ("github-actions", "timeouts"),
    ("github-actions", "checkout_credentials"), ("github-actions", "iac_commands"),
    ("woodpecker", "image_pinning"), ("woodpecker", "iac_commands"),
])
def test_generated_infra_hardening(tool: str, tier: str, provider: str, prop: str) -> None:
    from lib.cicd.config import InfrastructureConfig
    from lib.cicd.infrastructure import generate_infra_pipeline

    files = generate_infra_pipeline(InfrastructureConfig(provider=tool), provider)
    name = f".github/workflows/infra-{tier}.yml" if provider == "github-actions" else f".woodpecker/infra-{tier}.yml"
    assert_infra_property(yaml.load(files[name], Loader=yaml.BaseLoader), provider, tool, prop)


@pytest.mark.parametrize("tool", INFRA_TOOLS)
def test_woodpecker_infra_states_its_timeout_limit(tool: str) -> None:
    from lib.cicd.config import InfrastructureConfig
    from lib.cicd.infrastructure import generate_infra_pipeline

    files = generate_infra_pipeline(InfrastructureConfig(provider=tool), "woodpecker")
    assert len(files) == 3
    assert all(INFRA_LIMIT in text for text in files.values())


@pytest.mark.parametrize("tool,field", [("terraform", "TERRAFORM_IMAGE"),
                                      ("pulumi", "PULUMI_PYTHON_IMAGE"), ("bicep", "AZURE_CLI_IMAGE")])
def test_infra_images_use_the_shared_release_index_pin(tool: str, field: str) -> None:
    from lib.cicd.config import InfrastructureConfig
    from lib.cicd.infrastructure import generate_infra_pipeline

    files = generate_infra_pipeline(InfrastructureConfig(provider=tool), "woodpecker")
    images = [step["image"] for text in files.values()
              for step in yaml.load(text, Loader=yaml.BaseLoader)["steps"]]
    assert images and set(images) == {getattr(action_pins, field)}
    assert re.fullmatch(r"[^@\s]+:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", images[0])


INFRA_FIXTURES = FIXTURES / "infra"
INFRA_BAD_CASES = json.loads((INFRA_FIXTURES / "cases.json").read_text())


@pytest.mark.parametrize("case", INFRA_BAD_CASES, ids=[case["file"] for case in INFRA_BAD_CASES])
def test_infra_bad_fixture_is_detected_and_repair_removes_detection(case):
    good = yaml.load((INFRA_FIXTURES / case["good_file"]).read_text(), Loader=yaml.BaseLoader)
    bad = yaml.load((INFRA_FIXTURES / case["file"]).read_text(), Loader=yaml.BaseLoader)
    bad_parent, good_parent = bad, good
    for key in case["path"][:-1]:
        bad_parent, good_parent = bad_parent[key], good_parent[key]
    key = case["path"][-1]
    assert bad_parent[key] == case["bad_value"] and bad_parent[key] != good_parent[key]
    with pytest.raises(AssertionError):
        assert_infra_property(bad, case["provider"], case["tool"], case["property"])
    fixed = copy.deepcopy(bad)
    parent = fixed
    for key in case["path"][:-1]:
        parent = parent[key]
    parent[case["path"][-1]] = good_parent[case["path"][-1]]
    assert fixed == good, "repair must remove only the planted defect"
    assert_infra_property(fixed, case["provider"], case["tool"], case["property"])


@pytest.mark.parametrize("provider,prop", [
    ("github-actions", "permissions"), ("github-actions", "timeouts"),
    ("github-actions", "checkout_credentials"), ("woodpecker", "image_pinning"),
    ("woodpecker", "iac_commands"),
])
def test_infra_assertions_refuse_an_empty_population(provider: str, prop: str) -> None:
    document = {"jobs": {}} if provider == "github-actions" else {"steps": []}
    assert not document.get("jobs", document.get("steps"))
    with pytest.raises(AssertionError):
        assert_infra_property(document, provider, "terraform", prop)


@pytest.mark.parametrize("tool", ["none", "cloudformation"])
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
def test_unsupported_infra_tool_writes_nothing(tool: str, provider: str, tmp_path: Path) -> None:
    from lib.cicd.config import InfrastructureConfig
    from lib.cicd.infrastructure import generate_infra_pipeline

    output = tmp_path / "output"
    assert tool not in INFRA_TOOLS and not output.exists()
    with pytest.raises(ValueError) as exc:
        generate_infra_pipeline(InfrastructureConfig(provider=tool), provider, output)
    assert "infrastructure.provider" in str(exc.value) and tool in str(exc.value)
    assert all(value in str(exc.value) for value in INFRA_TOOLS)
    assert not output.exists()


@pytest.mark.parametrize("tool", ["none", "cloudformation"])
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
@pytest.mark.parametrize("mode", ["preview", "write", "json"])
def test_cli_rejects_unsupported_infra_tool_without_writing(tool, provider, mode, tmp_path, capsys):
    from lib.cicd.cli import main

    config = tmp_path / ".claude/cicd.yml"
    config.parent.mkdir()
    config.write_text(f"pipeline:\n  providers: [{provider}]\ninfrastructure:\n  provider: {tool}\n")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert tool not in INFRA_TOOLS and len(before) == 1
    extra = [] if mode == "preview" else ["--" + mode]
    assert main(["infra-pipeline", "--path", str(tmp_path), *extra]) == 2
    error = capsys.readouterr().err
    assert "infrastructure.provider" in error and tool in error
    assert all(value in error for value in INFRA_TOOLS)
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def execute_infra_commands(tmp_path, commands, provider, location):
    if shutil.which("bash") is None or shutil.which("sh") is None:
        pytest.skip("infra command harness needs bash and sh")
    directory = tmp_path / "bin"
    directory.mkdir(exist_ok=True)
    trace = tmp_path / "commands"
    for name in ("terraform", "pulumi", "pip", "az"):
        stub = directory / name
        stub.write_text('#!/bin/sh\nprintf \'%s\\0\' "${0##*/}" "$@" >> "$INFRA_TRACE"\n'
                        'printf \'\\n\' >> "$INFRA_TRACE"\n')
        stub.chmod(0o755)
    workspace = tmp_path / "workspace"
    (workspace / "infra/app").mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PATH": str(directory) + os.pathsep + os.environ.get("PATH", ""),
           "INFRA_TRACE": str(trace)}
    env.pop("AZURE_LOCATION", None)
    if location is not None:
        env["AZURE_LOCATION"] = location
    else:
        assert "AZURE_LOCATION" not in env
    assert all(shutil.which(name, path=env["PATH"]) == str(directory / name)
               for name in ("terraform", "pulumi", "pip", "az"))
    script = "\n".join(commands)
    if provider == "woodpecker":
        script = script.replace("$$", "$")  # Woodpecker's documented transport escape.
        cwd = workspace
    else:
        script = script.replace("${{ vars.AZURE_LOCATION }}", location or "")
        cwd = workspace / "infra/app"
    result = subprocess.run(["bash", "-e", "-c", script], env=env, cwd=cwd,
                            capture_output=True, text=True, timeout=10)
    calls = [[token.decode() for token in line.split(b"\0")[:-1]]
             for line in trace.read_bytes().splitlines()] if trace.exists() else []
    return result, calls


@pytest.mark.parametrize("tool", INFRA_TOOLS)
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
@pytest.mark.parametrize("phase", ["plan", "apply"])
def test_emitted_infra_commands_execute_the_selected_tool(tool, provider, phase, tmp_path):
    from lib.cicd.config import InfrastructureConfig
    from lib.cicd.infrastructure import generate_infra_pipeline

    files = generate_infra_pipeline(InfrastructureConfig(provider=tool), provider)
    if provider == "woodpecker":
        document = yaml.load(files[".woodpecker/infra-app.yml"], Loader=yaml.BaseLoader)
        step = next(step for step in document["steps"] if step["name"] == phase + "-app")
        commands = step["commands"]
    else:
        document = yaml.load(files[".github/workflows/infra-app.yml"], Loader=yaml.BaseLoader)
        commands = [step["run"] for step in document["jobs"][phase]["steps"] if "run" in step]
    location = "fixture region" if provider == "woodpecker" else "fixture-region"
    result, calls = execute_infra_commands(tmp_path, commands, provider, location)
    assert result.returncode == 0, result.stderr
    expected = [shlex.split(command) for command in infra_commands(tool, shlex.quote(location))]
    indexes = [0, 1] if phase == "plan" else ([0, 1, 2] if provider == "github-actions" else [0, 2])
    assert calls == [expected[index] for index in indexes]


def test_woodpecker_bicep_requires_runtime_location(tmp_path):
    from lib.cicd.config import InfrastructureConfig
    from lib.cicd.infrastructure import generate_infra_pipeline

    text = generate_infra_pipeline(InfrastructureConfig(provider="bicep"), "woodpecker")[".woodpecker/infra-app.yml"]
    step = yaml.load(text, Loader=yaml.BaseLoader)["steps"][0]
    result, calls = execute_infra_commands(tmp_path, step["commands"], "woodpecker", None)
    assert result.returncode != 0 and "AZURE_LOCATION" in result.stderr
    assert calls == [["az", "bicep", "install"]]


def test_github_location_substitution_does_not_add_quoting(tmp_path):
    from lib.cicd.config import InfrastructureConfig
    from lib.cicd.infrastructure import generate_infra_pipeline

    text = generate_infra_pipeline(InfrastructureConfig(provider="bicep"))[".github/workflows/infra-app.yml"]
    document = yaml.load(text, Loader=yaml.BaseLoader)
    commands = [step["run"] for step in document["jobs"]["plan"]["steps"] if "run" in step]
    location = "fixture region"
    assert len(location.split()) == 2 and "${{ vars.AZURE_LOCATION }}" in commands[1]
    result, calls = execute_infra_commands(tmp_path, commands, "github-actions", location)
    assert result.returncode == 0
    # GitHub inserts the raw value. The existing unquoted command splits it;
    # the harness must expose that fact, not manufacture shell quoting.
    assert calls == [["az", "bicep", "install"],
                     ["az", "deployment", "sub", "what-if", "--location", "fixture", "region",
                      "--template-file", "main.bicep"]]


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
