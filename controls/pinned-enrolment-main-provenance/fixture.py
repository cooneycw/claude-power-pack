"""Offline real-Git fixtures for the actual provider job emitters (#1754)."""
import importlib.util
import json
import os
import shlex
import shutil
import subprocess


def emitted_runtime(gate, pin, provider):
    spec = importlib.util.spec_from_file_location("lib.cicd._main_provenance_fixture", gate)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if provider == "github-actions":
        lines = module.github_actions_job(pin)
        start = lines.index("        run: |") + 1
        return "\n".join(line[10:] for line in lines[start:] if line)
    lines = module.woodpecker_step(pin)
    start = lines.index("      - |") + 1
    return "\n".join(line[8:] for line in lines[start:] if line).replace("$$", "$")


def _git(repo, env, *args, check=True):
    result = subprocess.run(
        [shutil.which("git"), "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        env=env, capture_output=True, text=True, timeout=15,
    )
    if check:
        assert result.returncode == 0, result.stderr
    return result


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


def exercise(tmp_path, source, case, provider, gate):
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
        + 'exec ' + shlex.quote(shutil.which("git")) + ' "${args[@]}"\n'
    )
    proxy.chmod(0o755)
    metadata = {"base": {"repo": {"full_name": "o/r"}},
                "head": {"repo": {"full_name": "o/r"}, "ref": "owned-branch", "sha": source["head"]}}
    curl = binaries / "curl"
    curl.write_text("#!/bin/sh\nprintf '%s\\n' " + shlex.quote(json.dumps(metadata)) + "\n")
    curl.chmod(0o755)
    runtime = emitted_runtime(gate, source[case["pin"]], provider)
    flags = ["-eo", "pipefail"] if provider == "github-actions" else []
    result = subprocess.run(
        ["bash", *flags, "-c", runtime], cwd=project,
        env={**env, "PATH": str(binaries) + os.pathsep + env["PATH"], "GH_TOKEN": "",
             "CPP_PR_EVENT": "pull_request", "CPP_PR_BRANCH": "owned-branch",
             "CPP_PR_HEAD_REPO": "o/r", "CPP_PR_BASE_REPO": "o/r",
             "CI_PIPELINE_EVENT": "pull_request", "CI_COMMIT_SOURCE_BRANCH": "owned-branch",
             "CI_COMMIT_PULL_REQUEST": "1", "CI_REPO": "o/r", "CI_FORGE_TYPE": "github",
             "CI_FORGE_URL": "https://github.com"},
        capture_output=True, text=True, timeout=20,
    )
    return result, log.read_text()
