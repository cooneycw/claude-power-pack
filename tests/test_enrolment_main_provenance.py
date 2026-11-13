"""#1754 trust boundary: execute only CPP revisions retained by official main.

Run the actual rendered command for each provider, with real Git and owned
repositories. Only the official fetch URL is redirected. The frozen historical
anchor still executes the feature sentinel and cannot enforce main ancestry.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from lib.cicd import enrolment
from lib.cicd.config import CICDConfig
from lib.cicd.pipeline import generate_github_actions, generate_woodpecker
from tests.test_cicd_pipeline import _make_info

FIXTURES = Path(__file__).parent / "fixtures/enrolment-main-provenance"
CASES = json.loads((FIXTURES / "cases.json").read_text())
requires_tools = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in (
        "git", "bash", "timeout", "mktemp", "sed", "head", "grep",
    )), reason="requires real Git and enrolment shell tools",
)


def _git(repo, env, *args, check=True):
    result = subprocess.run(
        [shutil.which("git"), "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        env=env, capture_output=True, text=True, timeout=15,
    )
    if check:
        assert result.returncode == 0, result.stderr
    return result


@pytest.fixture
def owned_source(tmp_path):
    env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_AUTHOR_NAME": "Owned fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Owned fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
           "GIT_TERMINAL_PROMPT": "0"}
    source, public, project = (tmp_path / name for name in ("source", "public.git", "project"))
    for repo in (source, public, project):
        repo.mkdir()
    _git(source, env, "init", "-q", "-b", "main")
    (source / "scripts").mkdir()

    def commit(label):
        # Harmless code marker proves which checker actually ran.
        (source / "scripts/flow-finish-gate.sh").write_text(
            '#!/bin/bash\nprintf "OWNED_CPP_CODE: ' + label + '\\nFLOW_FINISH_GATE: ok\\n"\n'
        )
        (source / "scripts/counter-model-receipt.py").write_text("# owned inert fixture\n")
        _git(source, env, "add", ".")
        _git(source, env, "commit", "-qm", label)
        return _git(source, env, "rev-parse", "HEAD").stdout.strip()

    ancestor = commit("main-ancestor")
    _git(source, env, "switch", "-qc", "feature")
    feature = commit("unmerged-feature")
    _git(source, env, "switch", "-q", "main")
    tip = commit("main-tip")
    assert ancestor != tip
    assert _git(source, env, "merge-base", "--is-ancestor", ancestor, tip).returncode == 0
    assert _git(source, env, "merge-base", "--is-ancestor", feature, tip, check=False).returncode == 1
    _git(public, env, "init", "--bare", "-q", "--initial-branch=main")
    _git(source, env, "push", "-q", str(public), "main", "feature")
    assert _git(public, env, "cat-file", "-t", feature).stdout.strip() == "commit"
    _git(project, env, "init", "-q", "-b", "owned-branch")
    (project / "owned.txt").write_text("owned consumer\n")
    _git(project, env, "add", ".")
    _git(project, env, "commit", "-qm", "consumer")
    head = _git(project, env, "rev-parse", "HEAD").stdout.strip()
    return dict(env=env, public=public, project=project, head=head,
                ancestor=ancestor, feature=feature, tip=tip)


def _exercise(tmp_path, source, case, provider):
    public, project, env = source["public"], source["project"], source["env"]
    if case["history"] == "missing-main":
        _git(public, env, "update-ref", "-d", "refs/heads/main")
        assert _git(public, env, "show-ref", "--verify", "--quiet", "refs/heads/main",
                    check=False).returncode == 1
        assert _git(public, env, "show-ref", "--verify", "--quiet", "refs/heads/feature").returncode == 0
    if case["history"] == "shallow":
        proof = tmp_path / "shallow-proof"
        proof.mkdir()
        _git(proof, env, "init", "-q")
        _git(proof, env, "fetch", "-q", "--depth=1", public.as_uri(), "refs/heads/main")
        assert _git(proof, env, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    binaries = tmp_path / "bin"
    binaries.mkdir()
    log = tmp_path / "git-calls"
    # All Git operations remain real. Only named main fetches are deliberately
    # made shallow in that case; the current blind anchor fetches only the pin.
    proxy = binaries / "git"
    proxy.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$*" >> ' + shlex.quote(str(log)) + '\n'
        'args=(); main_fetch=0\nfor arg in "$@"; do\n'
        ' [[ "$arg" == refs/heads/main* ]] && main_fetch=1\n'
        ' [[ "$arg" == https://github.com/cooneycw/claude-power-pack.git ]] && arg='
        + shlex.quote(public.as_uri()) + '\n args+=("$arg")\ndone\n'
        + ('[[ "$main_fetch" == 1 ]] && args+=("--depth=1")\n'
           if case["history"] == "shallow" else '')
        + 'fault="${OWNED_GIT_FAULT:-}"; hit=0\n'
        + '[[ "$fault" == init && " $* " == *" init "* ]] && hit=1\n'
        + '[[ "$fault" == fetch-timeout && "$main_fetch" == 1 ]] && hit=1\n'
        + '[[ "$fault" == history-probe && "$1" == -C && "$*" == *" --is-shallow-repository" ]] && hit=1\n'
        + '[[ "$fault" == main-ref || "$fault" == invalid-main ]] && '
        + '[[ "$*" == *" rev-parse --verify "* ]] && hit=1\n'
        + '[[ "$fault" == history-read || "$fault" == history-empty ]] && '
        + '[[ "$*" == *" rev-list "* ]] && hit=1\n'
        + 'if [[ "$hit" == 1 ]]; then\n'
        + ' printf "FAULT: %s\\n" "$fault" >> ' + shlex.quote(str(log)) + '\n'
        + ' [[ "$fault" == invalid-main ]] && { echo invalid; exit 0; }\n'
        + ' [[ "$fault" == history-empty ]] && exit 0\n'
        + ' [[ "$fault" == fetch-timeout ]] && exit 124\n'
        + ' exit 1\nfi\n'
        + 'exec ' + shlex.quote(shutil.which("git")) + ' "${args[@]}"\n'
    )
    proxy.chmod(0o755)
    metadata = {"base": {"repo": {"full_name": "o/r"}},
                "head": {"repo": {"full_name": "o/r"}, "ref": "owned-branch", "sha": source["head"]}}
    curl = binaries / "curl"
    curl.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(json.dumps(metadata)) + "\n")
    curl.chmod(0o755)
    config = CICDConfig()
    config._cpp_revision = source[case["pin"]]
    render = generate_github_actions if provider == "github-actions" else generate_woodpecker
    document = yaml.load(render(_make_info(), config), Loader=yaml.BaseLoader)
    if provider == "github-actions":
        runtime = document["jobs"]["counter-model-enrolment"]["steps"][-1]["run"]
        flags = ["-eo", "pipefail"]
    else:
        step = next(s for s in document["steps"] if s["name"] == "counter-model-enrolment")
        runtime = step["commands"][-1].replace("$$", "$")
        flags = []
    result = subprocess.run(
        ["bash", *flags, "-c", runtime], cwd=project,
        env={**env, "PATH": str(binaries) + os.pathsep + env["PATH"], "GH_TOKEN": "",
             "CPP_PR_EVENT": "pull_request", "CPP_PR_BRANCH": "owned-branch",
             "CPP_PR_HEAD_REPO": "o/r", "CPP_PR_BASE_REPO": "o/r",
             "CI_PIPELINE_EVENT": "pull_request", "CI_COMMIT_SOURCE_BRANCH": "owned-branch",
             "CI_COMMIT_PULL_REQUEST": "1", "CI_REPO": "o/r", "CI_FORGE_TYPE": "github",
             "CI_FORGE_URL": "https://github.com", "OWNED_GIT_FAULT": case.get("fault", "")},
        capture_output=True, text=True, timeout=20,
    )
    return result, log.read_text()


@requires_tools
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_emitted_job_requires_pin_retained_by_main(tmp_path, owned_source, case, provider):
    result, calls = _exercise(tmp_path, owned_source, case, provider)
    assert "fetch" in calls
    assert result.returncode == case["exit"], result.stdout + result.stderr
    diagnostics = [line for line in result.stdout.splitlines()
                   if line.startswith("CPP_COUNTER_MODEL_CPP_REVISION:")]
    assert len(diagnostics) == 1, result.stdout
    assert diagnostics[0].startswith("CPP_COUNTER_MODEL_CPP_REVISION: " + case["expect"] + " pin=")
    assert re.fullmatch(
        r"CPP_COUNTER_MODEL_CPP_REVISION: (reachable|not-reachable|unknown) "
        r"pin=[0-9a-f]{40} main=([0-9a-f]{40}|-)", diagnostics[0],
    )
    fetches = [line for line in calls.splitlines() if " fetch " in line]
    assert len(fetches) == 1 and "refs/heads/main:refs/remotes/cpp-enrolment/main" in fetches[0]
    assert "--depth" not in fetches[0]
    if case["expect"] != "reachable":
        assert " checkout " not in calls, "unapproved pin was checked out before proof"
    else:
        assert calls.index(" rev-list ") < calls.index(" checkout ")
    if case["expect"] == "reachable":
        assert "OWNED_CPP_CODE: main-ancestor" in result.stdout
        assert "CPP_COUNTER_MODEL_ENROLMENT: ok" in result.stdout
    else:
        assert "OWNED_CPP_CODE:" not in result.stdout, "unapproved or unexamined code executed"
        assert "CPP_COUNTER_MODEL_ENROLMENT: unknown" in result.stdout


@requires_tools
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
def test_historical_blind_anchor_still_executes_unmerged_checker(
        tmp_path, owned_source, monkeypatch, provider):
    spec = importlib.util.spec_from_file_location("owned_blind_enrolment", FIXTURES / "blind-enrolment.py")
    assert spec and spec.loader
    anchor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(anchor)
    monkeypatch.setattr(enrolment, "bootstrap_script", anchor.bootstrap_script)
    result, _ = _exercise(tmp_path, owned_source, CASES[0], provider)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OWNED_CPP_CODE: unmerged-feature" in result.stdout
    assert "CPP_COUNTER_MODEL_ENROLMENT: ok" in result.stdout


@requires_tools
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
@pytest.mark.parametrize("fault", [
    "init", "fetch-timeout", "history-probe", "main-ref", "invalid-main", "history-read", "history-empty",
])
def test_unreadable_main_proof_cannot_checkout_or_execute(tmp_path, owned_source, provider, fault):
    assert fault in {"init", "fetch-timeout", "history-probe", "main-ref", "invalid-main",
                     "history-read", "history-empty"}
    case = {"pin": "ancestor", "history": "full", "fault": fault}
    result, calls = _exercise(tmp_path, owned_source, case, provider)
    assert "FAULT: " + fault in calls, "the declared failure must actually be exercised"
    assert result.returncode == 5, result.stdout + result.stderr
    diagnostic = next(line for line in result.stdout.splitlines()
                      if line.startswith("CPP_COUNTER_MODEL_CPP_REVISION:"))
    assert re.fullmatch(r"CPP_COUNTER_MODEL_CPP_REVISION: unknown pin=[0-9a-f]{40} main=([0-9a-f]{40}|-)",
                        diagnostic)
    assert "CPP_COUNTER_MODEL_ENROLMENT: unknown" in result.stdout
    assert " checkout " not in calls
    assert "OWNED_CPP_CODE:" not in result.stdout


@requires_tools
@pytest.mark.parametrize("provider", ["github-actions", "woodpecker"])
def test_shallow_control_rejects_unrelated_unknown_near_miss(tmp_path, provider):
    """Review counterexample: UNKNOWN alone does not prove the shallow guard."""
    import sys

    root = Path(__file__).resolve().parents[1]
    mutation = json.loads((FIXTURES / "shallow-near-miss.json").read_text())
    source = (root / "lib/cicd/enrolment.py").read_text()
    assert source.count(mutation["remove"]) == source.count(mutation["insert_before"]) == 1
    mutated = source.replace(mutation["remove"], "# shallow refusal deliberately removed")
    mutated = mutated.replace(mutation["insert_before"], mutation["insert"] + mutation["insert_before"])
    assert mutation["remove"] not in mutated
    assert "unrelated main-tip refusal" in mutated
    gate = tmp_path / "broken-enrolment.py"
    gate.write_text(mutated)
    case = root / "controls/pinned-enrolment-main-provenance/cases" / ("unknown-main-shallow-" + provider)
    result = subprocess.run(
        [sys.executable, str(root / "controls/pinned-enrolment-main-provenance/run-case.py"), str(gate), str(case)],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "PINNED_MAIN_CONTROL: malformed evidence" in result.stdout
    assert "unrelated main-tip refusal" in result.stdout
