"""Generated main app enrolment jobs and the trusted pinned bootstrap (#1610 B)."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from lib.cicd.config import CICDConfig
from lib.cicd.pipeline import generate_github_actions, generate_woodpecker
from tests.test_cicd_pipeline import _make_info

SPEC = importlib.util.spec_from_file_location(
    "pinned_enrolment_fixture", Path(__file__).resolve().parents[1] / "controls/pinned-enrolment/fixture.py",
)
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
exercise = fixture.exercise
PIN = fixture.PIN
requires_bash = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("bash", "timeout", "sed", "head", "grep", "mktemp")),
    reason="requires bootstrap shell tools",
)


@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
def test_main_app_template_has_enrolment_job(provider):
    config = CICDConfig()
    config._cpp_revision = PIN
    text = (generate_github_actions if provider == "github-actions" else generate_woodpecker)(_make_info(), config)
    document = yaml.load(text, Loader=yaml.BaseLoader)
    if provider == "github-actions":
        job = document["jobs"].get("counter-model-enrolment")
        assert job is not None, "Actions template has no enrolment job"
        assert job["steps"][0]["with"]["fetch-depth"] == "0"
        assert job["env"]["CPP_PR_BRANCH"] == "${{ github.head_ref }}"
    else:
        assert any(step["name"] == "counter-model-enrolment" for step in document["steps"])
        assert document["clone"][0]["settings"]["depth"] == "0"
    assert PIN in text


def test_pin_comes_from_cpp_init_snapshot_and_ignores_yaml_override(tmp_path):
    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    (config_dir / "cicd.yml").write_text("pipeline:\n  providers: [github-actions]\n  cpp_revision: main\n")
    (config_dir / "cpp-install.json").write_text(json.dumps({"schema": 1, "cpp_revision": PIN}))
    loaded = CICDConfig.load(str(tmp_path))
    assert loaded._cpp_revision == PIN
    text = generate_github_actions(_make_info(), loaded)
    assert "CPP_SHA=" + PIN in text




@requires_bash
@pytest.mark.parametrize("pin", ["main", "v1.0", "a" * 7, "refs/heads/" + PIN])
def test_moving_or_short_pin_is_refused_before_fetch(tmp_path, pin):
    assert len(pin) != 40
    result, calls = exercise(tmp_path, pin)
    assert result.returncode == 5
    assert "CPP_COUNTER_MODEL_ENROLMENT: unknown" in result.stdout
    assert "fetch" not in calls


@requires_bash
@pytest.mark.parametrize("scenario", ["mismatch", "fetch-failure", "broken-bootstrap"])
def test_fetch_pin_or_bootstrap_failure_is_unknown(tmp_path, scenario):
    result, calls = exercise(tmp_path, scenario=scenario)
    assert "fetch" in calls
    assert result.returncode == 5, result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: unknown" in result.stdout
    assert "CPP_COUNTER_MODEL_ENROLMENT: ok" not in result.stdout


@requires_bash
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
@pytest.mark.parametrize("fork", [False, True])
def test_only_positive_fork_evidence_warns_instead_of_missing_receipt_failure(tmp_path, provider, fork):
    result, calls = exercise(tmp_path, scenario="missing-receipt", fork=fork, provider=provider)
    assert result.returncode == (0 if fork else 1), result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: " + ("warn" if fork else "fail") in result.stdout
    if fork:
        assert "fetch" not in calls


@requires_bash
def test_same_repo_metadata_api_error_cannot_downgrade_to_fork_warning(tmp_path):
    result, calls = exercise(tmp_path, scenario="metadata-error", provider="woodpecker")
    assert result.returncode == 5, result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: unknown" in result.stdout
    assert "CPP_COUNTER_MODEL_ENROLMENT: warn" not in result.stdout
    assert "fetch" not in calls


@requires_bash
def test_full_pin_checks_consumer_cwd_and_branch(tmp_path):
    result, calls = exercise(tmp_path)
    assert "fetch" in calls and PIN in calls
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: ok" in result.stdout


requires_git = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("git", "bash", "timeout", "sed", "head", "grep", "mktemp")),
    reason="requires real git and bootstrap shell tools",
)


@requires_git
@pytest.mark.parametrize("receipt", ["missing", "ran", "skipped"])
def test_real_trusted_checker_checks_consumer_ancestry(tmp_path, receipt):
    from lib.cicd.enrolment import bootstrap_script

    real_git = shutil.which("git")
    assert real_git
    root = Path(__file__).resolve().parents[1]
    cpp = tmp_path / "trusted-cpp"
    project = tmp_path / "consumer"
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                   "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}

    def git_at(repo, *args):
        return subprocess.run([real_git, "-C", str(repo), *args], env=environment,
                              check=True, capture_output=True, text=True).stdout.strip()

    for repo in (cpp, project):
        repo.mkdir()
        git_at(repo, "init", "-q", "-b", "owned-branch")
    (cpp / "scripts").mkdir()
    for name in ("flow-finish-gate.sh", "counter-model-receipt.py", "gate-lib.sh", "coordination-admission.sh"):
        shutil.copy2(root / "scripts" / name, cpp / "scripts" / name)
    git_at(cpp, "add", ".")
    git_at(cpp, "commit", "-qm", "trusted checker")
    pin = git_at(cpp, "rev-parse", "HEAD")
    (project / "owned.txt").write_text("owned fixture\n")
    git_at(project, "add", ".")
    git_at(project, "commit", "-qm", "consumer change")
    head = git_at(project, "rev-parse", "HEAD")
    sentinel = project / "consumer-code-ran"
    if receipt == "skipped":
        (project / "json.py").write_text(
            "from pathlib import Path\nPath('consumer-code-ran').write_text('executed')\n"
            "raise RuntimeError('owned shadow')\n"
        )
        environment["PYTHONPATH"] = str(project)
    if receipt != "missing":
        directory = project / "docs/measurements/counter-model"
        directory.mkdir(parents=True)
        (directory / "owned.json").write_text(json.dumps({
            "branch": "owned-branch", "head": head, "status": receipt, "scope": "diff-only",
            "skip_reason": "codex-absent",
        }, indent=2) + "\n")
        git_at(project, "add", ".")
        git_at(project, "commit", "-qm", "receipt for ancestor")
        assert git_at(project, "rev-parse", "HEAD") != head
    else:
        assert not (project / "docs/measurements/counter-model").exists()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    proxy = binaries / "git"
    # Redirect only the fixed public fetch URL to the owned local repository.
    # Every git operation, including fetch, SHA resolution and ancestry, is real.
    import shlex
    proxy.write_text("#!/bin/bash\nargs=()\nfor arg in \"$@\"; do\n"
                     " [[ \"$arg\" == https://github.com/cooneycw/claude-power-pack.git ]] && "
                     f"arg={shlex.quote(str(cpp))}\n"
                     " args+=(\"$arg\")\ndone\n" + f"exec {shlex.quote(real_git)} \"${{args[@]}}\"\n")
    proxy.chmod(0o755)
    result = subprocess.run(["bash", "-c", bootstrap_script(pin, "github-actions")], cwd=project,
                            env={**environment, "PATH": str(binaries) + os.pathsep + environment["PATH"],
                                 "CPP_PR_EVENT": "pull_request", "CPP_PR_BRANCH": "owned-branch",
                                 "CPP_PR_HEAD_REPO": "o/r", "CPP_PR_BASE_REPO": "o/r"},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == (0 if receipt != "missing" else 1), result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: " + ("ok" if receipt != "missing" else "fail") in result.stdout
    assert not sentinel.exists(), "trusted checker imported consumer code through PYTHONPATH"


@requires_bash
def test_woodpecker_emitted_command_survives_provider_dollar_expansion(tmp_path):
    config = CICDConfig()
    config._cpp_revision = PIN
    document = yaml.load(generate_woodpecker(_make_info(), config), Loader=yaml.BaseLoader)
    step = next(step for step in document["steps"] if step["name"] == "counter-model-enrolment")
    command = step["commands"][-1]
    assert "$${CPP_SHA}" not in command  # The pin is literal; all later variables use runtime values.
    assert '$$CPP_SHA' in command
    # Woodpecker's documented $$ escape produces one literal dollar at runtime.
    runtime = command.replace("$$", "$")
    result = subprocess.run(["bash", "-n"], input=runtime, text=True, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr


def test_enrolment_trigger_does_not_run_main_only_targets_on_pr():
    from lib.cicd.checks import derive_required_checks
    config = CICDConfig()
    config.pipeline.branches = {"main": ["deploy"], "pr": []}
    text = generate_github_actions(_make_info(), config)
    document = yaml.load(text, Loader=yaml.BaseLoader)
    assert "pull_request" in document["on"]
    assert document["jobs"]["ci"]["if"] == "github.ref == 'refs/heads/main' && github.event_name == 'push'"
    result = derive_required_checks(["github-actions"], {".github/workflows/ci.yml": text})
    assert result.status == "known" and result.checks == ("counter-model-enrolment",)


def test_required_check_reader_refuses_unexamined_clone_shape():
    from lib.cicd.checks import derive_required_checks
    path = Path(__file__).parent / "fixtures/pinned-enrolment/bad-clone.yml"
    text = path.read_text()
    assert "depth: 1" in text
    result = derive_required_checks(["woodpecker"], {".woodpecker.yml": text})
    assert result.status == "unknown" and "clone" in result.reason
    repaired = derive_required_checks(["woodpecker"], {".woodpecker.yml": text.replace("depth: 1", "depth: 0")})
    assert repaired.status == "known"


@requires_bash
@pytest.mark.parametrize("scenario", ["conflicting-verdict", "shallow-fetch-failure"])
def test_unexamined_or_conflicting_evidence_cannot_be_green(tmp_path, scenario):
    result, calls = exercise(tmp_path, scenario=scenario)
    assert result.returncode == 5, result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: unknown" in result.stdout


@requires_bash
@pytest.mark.parametrize("metadata", [
    {"CPP_PR_HEAD_REPO": ""}, {"CPP_PR_BASE_REPO": ""}, {"CPP_PR_BRANCH": ""},
])
def test_missing_fork_metadata_never_warns(tmp_path, metadata):
    result, calls = exercise(tmp_path, fork=True, metadata=metadata)
    assert result.returncode == 5 and "warn" not in result.stdout
    assert "fetch" not in calls


@requires_bash
def test_unsupported_forge_cannot_be_excused_as_fork(tmp_path):
    result, calls = exercise(tmp_path, fork=True, provider="woodpecker", metadata={"CI_FORGE_TYPE": "unsupported"})
    assert result.returncode == 5 and "warn" not in result.stdout
    assert "fetch" not in calls


@pytest.mark.parametrize("revision", ["main", "v1.0", "abc1234", None])
def test_invalid_install_revision_never_becomes_a_fetch_ref(tmp_path, revision):
    directory = tmp_path / ".claude"
    directory.mkdir()
    (directory / "cpp-install.json").write_text(json.dumps({"schema": 1, "cpp_revision": revision}))
    assert CICDConfig.load(str(tmp_path))._cpp_revision == ""


@requires_bash
def test_woodpecker_tool_bootstrap_failure_is_unknown(tmp_path):
    config = CICDConfig()
    command = yaml.load(generate_woodpecker(_make_info(), config), Loader=yaml.BaseLoader)["steps"][0]["commands"][0]
    apt = tmp_path / "apt-get"
    apt.write_text("#!/bin/sh\nexit 22\n")
    apt.chmod(0o755)
    assert apt.is_file()
    result = subprocess.run(["bash", "-c", command],
                            env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 5 and "CPP_COUNTER_MODEL_ENROLMENT: unknown" in result.stdout


@requires_bash
def test_metadata_reader_never_imports_consumer_modules(tmp_path):
    sentinel = tmp_path / "consumer-code-ran"
    (tmp_path / "json.py").write_text(
        "from pathlib import Path\nPath('consumer-code-ran').write_text('executed')\n"
        "raise RuntimeError('owned shadow')\n"
    )
    assert not sentinel.exists()
    result, calls = exercise(tmp_path, provider="woodpecker")
    assert not sentinel.exists(), "metadata parsing executed a module from the consumer checkout"
    assert result.returncode == 0, result.stdout + result.stderr


@requires_bash
@pytest.mark.parametrize("scenario,expected", [("missing-receipt", 1), ("broken-bootstrap", 5), ("old-checker", 5)])
def test_actions_errexit_still_reports_checker_verdict(tmp_path, scenario, expected):
    result, calls = exercise(tmp_path, scenario=scenario, shell_flags=("-eo", "pipefail"))
    assert result.returncode == expected, result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: " + ("fail" if expected == 1 else "unknown") in result.stdout


@requires_bash
def test_checker_cannot_read_the_bootstrap_input_stream(tmp_path):
    result, calls = exercise(tmp_path, scenario="reads-stdin", stdin="owned input not for the checker\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CPP_COUNTER_MODEL_ENROLMENT: ok" in result.stdout


def test_woodpecker_app_checks_do_not_depend_on_enrolment():
    from lib.cicd.config import WoodpeckerConfig
    config = CICDConfig()
    config.pipeline.woodpecker = WoodpeckerConfig(secret_scan=True, image_security=True, runtime_smoke=True)
    document = yaml.load(generate_woodpecker(_make_info(), config), Loader=yaml.BaseLoader)
    steps = document["steps"]
    dag = any("depends_on" in step for step in steps)
    parents = {}
    previous = None
    for step in steps:
        parents[step["name"]] = step.get("depends_on", [] if dag or previous is None else [previous])
        previous = step["name"]

    def ancestors(name):
        return {parent for p in parents[name] for parent in ({p} | ancestors(p))}

    assert parents["counter-model-enrolment"] == []
    for name in parents:
        if name != "counter-model-enrolment":
            assert "counter-model-enrolment" not in ancestors(name), name
    assert "secret-scan" in ancestors("lint")
    assert "lint" in ancestors("test")


def test_docs_state_pr_workflow_and_pin_are_editable():
    text = (Path(__file__).resolve().parents[1] / "docs/agents/generated-ci-enrolment.md").read_text()
    assert "PR's own workflow" in text and "edit the pin" in text


@requires_bash
def test_control_distinguishes_fetch_unknown_from_receipt_failure():
    root = Path(__file__).resolve().parents[1]
    control = root / "controls/pinned-enrolment"
    result = subprocess.run([sys.executable, str(control / "run-case.py"),
                             str(root / "controls/pinned-enrolment-exit-class/anchors/unknown-as-fail.py"),
                             str(control / "cases/bad-fetch-failure")],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "missed contract" in result.stdout, "control accepted FAIL where the case requires UNKNOWN"
