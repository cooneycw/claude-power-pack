"""Real checkout shapes and bounded, tier-specific completion evidence (#1917).

Local GOOD covers the declared local population. It never closes the root lane.
No uid emulation, host config copying, or fallback from an image to local tools.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SELECTORS = (
    "tests/test_codex_skill_sync.py",
    "tests/test_antigravity_codex_parity.py",
    "tests/test_antigravity_skill_sync.py",
    "tests/test_antigravity_skill_cli.py",
    "tests/test_pi_skill_sync.py",
    "tests/test_pi_skill_install.py",
    "tests/test_pi_host_fixture.py",
    "tests/test_pi_syscall_audit.py",
    "tests/test_pi_owner_probe.py",
    "tests/test_pi_owner_recovery.py",
    "tests/test_host_update_ci_shape.py",
    "tests/test_host_update_command.py",
    "tests/test_ci_shape_check.py",
)
LANES = ("depth-1", "depth-1-tree-0")
HISTORICAL_PIN = "40d25173c8c09987fac851cffa565efdc0f11c72"
# A small runtime surface. In particular Git/Make are ONLY in the staged dir.
SYSTEM_TOOLS = (
    "sh", "bash", "env", "chmod", "cp", "mkdir", "mv", "rm", "ln", "cat",
    "sed", "grep", "dirname", "basename", "readlink", "realpath", "timeout",
    "sleep", "touch", "stat", "wc", "head", "tail", "find", "sort", "tr",
    "cut", "xargs", "printf", "tee", "date", "true", "false", "install", "id",
    "uname", "du", "diff", "which", "tar", "gzip", "awk", "ps", "kill", "uv", "mktemp",
)
PRECONDITIONS = (
    "shallow", "one_head_commit", "historical_pin_absent", "source_modes",
    "symlink_tmp", "private_home", "external_cwd", "ci_true", "staged_git",
    "staged_make", "partial_witness", "identity",
)


class Unknown(RuntimeError):
    """The requested population could not be examined."""


def command(argv, *, cwd=None, env=None, input=None, check=True):
    return subprocess.run(list(map(str, argv)), cwd=cwd, env=env, input=input,
                          capture_output=True, text=True, check=check, timeout=180)


def image_pin(root: Path) -> str:
    text = (root / ".woodpecker.yml").read_text()
    found = re.search(r"^  validate:\n    image: (\S+@sha256:[0-9a-f]{64})$", text, re.M)
    if not found:
        raise Unknown("validate image is not content pinned")
    return found[1]


def completion(result: dict, returncode: int, log: str, tier: str) -> tuple[str, str]:
    """A zero exit is necessary, never sufficient (#1923)."""
    try:
        selected, outcomes, skips = result["selected"], result["outcomes"], result["skips"]
        if (returncode or result["exit"] or result["errors"] or "INTERNALERROR" in log
                or not selected or len(selected) != len(set(selected))
                or set(selected) != set(outcomes) or set(skips) != {
                    key for key, value in outcomes.items() if value == "skipped"}):
            return "BAD", "failed, interrupted, empty or incomplete pytest results"
        if any(value not in {"passed", "skipped"} for value in outcomes.values()):
            return "BAD", "pytest failures or invalid terminal outcomes"
        # A non-root run may skip only tests explicitly requiring real uid 0.
        for nodeid, reason in skips.items():
            root_skip = tier == "local" and "requires real root" in reason
            history_prefix = "tests/test_host_update_command.py::test_real_historical_installer_population["
            history_skip = (nodeid.startswith(history_prefix)
                            and ("historical installer" in reason or "partial clone:" in reason))
            if not root_skip and not history_skip:
                return "BAD", "unexpected skip: " + reason[:200]
        for selector in SELECTORS:
            if not any(key.startswith(selector + "::") and value == "passed"
                       for key, value in outcomes.items()):
                return "BAD", "no executed passing tests for " + selector
    except (KeyError, TypeError, ValueError, AttributeError):
        return "BAD", "malformed pytest completion evidence"
    return "GOOD", "all declared selectors completed; skips named"


def assess(receipt: dict, *, tier: str, commit: str, image: str) -> tuple[str, str]:
    """The same public verifier is used by controls and downstream readers."""
    try:
        if (receipt["schema"] != 1 or receipt["tier"] != tier
                or receipt["commit"] != commit or receipt["image"] != image
                or receipt["selectors"] != list(SELECTORS)):
            return "BAD", "receipt identity, tier or selection mismatch"
        if receipt.get("state") == "UNKNOWN" and not receipt["lanes"]:
            return "UNKNOWN", receipt["reason"]
        root = receipt["root"]
        if tier == "local":
            if root != {"state": "UNKNOWN", "reason": "not examined: needs real uid 0"}:
                return "BAD", "local GOOD cannot claim root GOOD"
        elif tier == "image":
            if root != {"state": "GOOD", "reason": "real uid 0 in pinned validate image"}:
                return "BAD", "image/root evidence missing"
        else:
            return "BAD", "invalid tier"
        lanes = receipt["lanes"]
        if [row["name"] for row in lanes] != list(LANES):
            return "BAD", "missing or duplicated clone lane"
        for lane in lanes:
            if lane["state"] == "UNKNOWN":
                return "UNKNOWN", lane["reason"]
            if lane["state"] != "GOOD":
                return "BAD", lane["reason"]
            if set(lane["preconditions"]) != set(PRECONDITIONS) or not all(
                    value is True for value in lane["preconditions"].values()):
                return "BAD", "shape precondition not established"
            uid = lane["identity"]["uid"]
            if (tier == "image" and uid != 0) or (tier == "local" and uid == 0):
                return "BAD", "wrong real uid for requested tier"
            state, reason = completion(lane["results"], lane["exit"], lane["diagnostic"], tier)
            if state != "GOOD":
                return state, reason
            outcomes = lane["results"]["outcomes"]
            if lane["counts"] != {
                    "selected": len(lane["results"]["selected"]),
                    "executed": sum(value != "skipped" for value in outcomes.values()),
                    "skipped": len(lane["results"]["skips"])}:
                return "BAD", "inconsistent selected/executed/skipped counts"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "BAD", "missing or malformed receipt evidence"
    return "GOOD", "both clone lanes completed for the declared tier only"


def fresh_environment(home: Path, tmp: Path, path: str) -> dict[str, str]:
    # Do not inherit Git, pytest, loader, Make, credential or HOME overrides.
    return {"HOME": str(home), "TMPDIR": str(tmp), "PATH": path, "CI": "true",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONNOUSERSITE": "1",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1", "UV_NO_PROGRESS": "1"}


def minimal_path(work: Path, stage: Path, python: Path) -> str:
    target = work / "system-bin"
    target.mkdir()
    for name in SYSTEM_TOOLS:
        source = shutil.which(name)
        if source:
            (target / name).symlink_to(source)
    for name in ("python", "python3"):
        (target / name).symlink_to(python)
    return os.pathsep.join((str(stage), str(target)))


def donor(root: Path, work: Path, git: str, commit: str, env: dict) -> tuple[Path, str]:
    """A private upload-pack server; never configure or mutate the author's repo."""
    path = work / "donor.git"
    command([git, "init", "--bare", "-q", path], env=env)
    command([git, "-C", path, "config", "uploadpack.allowFilter", "true"], env=env)
    command([git, "-C", path, "fetch", "--depth=1", root.as_uri(), commit], env=env)
    command([git, "-C", path, "update-ref", "refs/heads/checkpoint", "FETCH_HEAD"], env=env)
    # An unreferenced historical file with a present commit but absent tree/blob
    # distinguishes actual filtering from a remote that merely advertises it.
    blob = command([git, "-C", path, "hash-object", "-w", "--stdin"],
                   input="ci-shape historical blob witness\n", env=env).stdout.strip()
    tree = command([git, "-C", path, "mktree"], env=env,
                   input=f"100644 blob {blob}\told-only.txt\n").stdout.strip()
    author = {**env, "GIT_AUTHOR_NAME": "Shape witness", "GIT_COMMITTER_NAME": "Shape witness",
              "GIT_AUTHOR_EMAIL": "shape@example.invalid", "GIT_COMMITTER_EMAIL": "shape@example.invalid"}
    witness = command([git, "-C", path, "commit-tree", tree], input="historical witness\n",
                      env=author).stdout.strip()
    command([git, "-C", path, "update-ref", "refs/heads/witness", witness], env=env)
    return path, witness


def checkout(seed: Path, witness: str, work: Path, git: str, partial: bool, env: dict) -> Path:
    path = work / "checkout"
    options = ["--filter=tree:0"] if partial else []
    materialize = dict(env)
    materialize.pop("GIT_NO_LAZY_FETCH", None)
    command([git, "clone", "-q", "--depth=1", *options, "--branch=checkpoint",
             "--single-branch", seed.as_uri(), path], env=materialize)
    if partial:
        command([git, "-C", path, "fetch", "-q", "--depth=1", "--filter=tree:0",
                 "origin", witness], env=env)
    # Git 2.39 predates GIT_NO_LAZY_FETCH: an unreachable private origin also
    # prevents implicit fetch in older Git. HEAD's tracked files are materialized.
    command([git, "-C", path, "remote", "set-url", "origin", (work / "offline.git").as_uri()], env=env)
    return path


def observe(path: Path, work: Path, witness: str, git: str, stage: Path,
            env: dict, tier: str, partial: bool, *, historical_pin=HISTORICAL_PIN) -> tuple[dict, dict]:
    def g(*args, check=True):
        return command([git, "-C", path, *args], env=env, check=check)

    home, tmp = Path(env["HOME"]), Path(env["TMPDIR"])
    pin_absent = g("cat-file", "-e", historical_pin + "^{commit}", check=False).returncode != 0
    mode_inputs = {"CLAUDE.md": 0o666, "scripts/flow-finish-gate.sh": 0o777}
    modes = {name: (path / name).stat().st_mode & 0o777 for name in mode_inputs}
    filtered = True
    if partial:
        filtered = (g("config", "--get", "remote.origin.promisor").stdout.strip() == "true"
                    and g("config", "--get", "remote.origin.partialclonefilter").stdout.strip() == "tree:0"
                    and g("cat-file", "-e", witness + "^{commit}", check=False).returncode == 0
                    and g("cat-file", "-e", witness + ":old-only.txt", check=False).returncode != 0)
    identity = {"uid": os.getuid(), "gid": os.getgid(), "groups": os.getgroups()}
    preconditions = dict(zip(PRECONDITIONS, (
        g("rev-parse", "--is-shallow-repository").stdout.strip() == "true",
        g("rev-list", "--count", "HEAD", check=False).stdout.strip() == "1", pin_absent,
        modes == mode_inputs, tmp.is_symlink() and tmp.resolve() == work / "tmp-real",
        home.is_dir() and home.stat().st_mode & 0o777 == 0o700,
        not work.is_relative_to(path), env["CI"] == "true",
        shutil.which("git", path=env["PATH"]) == str(stage / "git"),
        shutil.which("make", path=env["PATH"]) == str(stage / "make"), filtered,
        (identity["uid"] == 0) if tier == "image" else (identity["uid"] != 0),
    ), strict=True))
    return preconditions, {"identity": identity, "modes": modes,
                           "partial_witness_commit": witness if partial else None,
                           "tmp_spelling": str(tmp), "tmp_resolved": str(tmp.resolve())}


def run_lane(root: Path, seed: Path, witness: str, work: Path, stage: Path,
             python: Path, tier: str, partial: bool, logs: Path) -> dict[str, Any]:
    work.mkdir()
    home, tmp = work / "home", work / "tmp-link"
    home.mkdir(mode=0o700)
    (work / "tmp-real").mkdir()
    tmp.symlink_to(work / "tmp-real", target_is_directory=True)
    env = fresh_environment(home, tmp, minimal_path(work, stage, python))
    git = str(stage / "git")
    name = LANES[int(partial)]
    row: dict[str, Any] = {"name": name, "state": "UNKNOWN", "reason": "not started"}
    before = time.monotonic()
    mask = os.umask(0)
    try:
        path = checkout(seed, witness, work, git, partial, env)
        preconditions, details = observe(path, work, witness, git, stage, env, tier, partial)
        row.update(preconditions=preconditions, **details)
        if not all(preconditions.values()):
            raise Unknown("shape preconditions failed: " + ", ".join(
                key for key, value in preconditions.items() if not value))
        # Dependencies come from the frozen lock, not from the caller's plugins.
        # Link only an environment built for this exact project lock by run().
        (path / ".venv").symlink_to(python.parent.parent, target_is_directory=True)
        results = work / "results.json"
        env.update(PYTHONPATH=str(path), CPP_CI_SHAPE_RESULTS=str(results),
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
        argv = [python, "-m", "pytest", "-c", path / "pyproject.toml", "--rootdir", path,
                "-p", "lib.ci_shape_pytest", "-p", "pytest_timeout", "-p", "xdist.plugin",
                "-n", "0", "--durations=15", "-q", "-rs", "--basetemp", work / "pytest",
                *[path / selector for selector in SELECTORS]]
        # Each run owns its basetemp under TemporaryDirectory, never the global
        # pytest-of-* namespace. The context removes it even after failure.
        with (logs / (name + ".log")).open("w") as output:
            proc = subprocess.Popen(list(map(str, argv)), cwd=work, env=env,
                                    stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                proc.wait(timeout=1200)
            except BaseException:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                raise
        log = (logs / (name + ".log")).read_text()
        payload = json.loads(results.read_text()) if results.exists() else {}
        state, reason = completion(payload, proc.returncode, log, tier)
        row.update(state=state, reason=reason, results=payload, exit=proc.returncode,
                   diagnostic="INTERNALERROR" if "INTERNALERROR" in log else "",
                   log_sha256=hashlib.sha256(log.encode()).hexdigest())
        outcomes = payload.get("outcomes", {})
        row["counts"] = {"selected": len(payload.get("selected", [])),
                         "executed": sum(value != "skipped" for value in outcomes.values()),
                         "skipped": len(payload.get("skips", {}))}
    except (Unknown, OSError, subprocess.SubprocessError, ValueError) as exc:
        row.update(state="UNKNOWN", reason=str(exc)[-2000:])
    finally:
        os.umask(mask)
        row["seconds"] = round(time.monotonic() - before, 2)
    return row


def run(root: Path, tier: str, receipt_path: Path, *, inside_image: str | None = None) -> dict:
    commit = "unresolved"
    image = image_pin(root)
    record: dict[str, Any] = {"schema": 1, "tier": tier, "commit": commit, "image": image,
                              "selectors": list(SELECTORS), "lanes": [], "state": "UNKNOWN"}
    record["root"] = ({"state": "GOOD", "reason": "real uid 0 in pinned validate image"}
                      if tier == "image" and os.getuid() == 0 and inside_image == image else
                      {"state": "UNKNOWN", "reason": "not examined: needs real uid 0"})
    try:
        if tier == "image" and (os.getuid() != 0 or inside_image != image):
            raise Unknown("image tier requires real uid 0 and the pinned-image launcher")
        if tier == "local" and os.getuid() == 0:
            raise Unknown("local non-root tier requires a non-root process")
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        logs = receipt_path.parent / (receipt_path.stem + "-logs")
        logs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cpp-ci-shape-") as temporary:
            work = Path(temporary).resolve()
            if tier == "image":
                work.chmod(0o755)
            env = fresh_environment(work, work, os.environ.get("PATH", ""))
            env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory",
                       GIT_CONFIG_VALUE_0=str(root))
            stage_root = work / "tools"
            stage_root.mkdir()
            for tool in ("git", "make"):
                staged = command([sys.executable, root / f"scripts/ci-stage-{tool}.py"],
                                 cwd=stage_root, env=env)
                (logs / f"stage-{tool}.log").write_text(staged.stdout + staged.stderr)
            stage = stage_root / ".ci-bin"
            source_git = [stage / "git", "-c", f"safe.directory={root}", "-C", root]
            commit = command([*source_git, "rev-parse", "HEAD"], env=env).stdout.strip()
            record["commit"] = commit
            # Refuse to label a committed SHA with dirty tracked inputs.
            if command([*source_git, "status", "--porcelain", "--untracked-files=no"], env=env).stdout:
                raise Unknown("tracked source is dirty; commit the implementation checkpoint")
            record["tools"] = {name: {"path": str(stage / name), "version": command(
                [stage / name, "--version"], env=env).stdout.splitlines()[0]}
                for name in ("git", "make")}
            uv = shutil.which("uv")
            if not uv:
                raise Unknown("uv unavailable")
            python_env = work / "venv"
            command([uv, "sync", "--project", root, "--extra", "dev", "--frozen"],
                    env={**env, "UV_PROJECT_ENVIRONMENT": str(python_env)})
            python = python_env / "bin/python"
            seed, witness = donor(root, work, str(stage / "git"), commit, env)
            for partial in (False, True):
                row = run_lane(root, seed, witness, work / LANES[int(partial)],
                               stage, python, tier, partial, logs)
                record["lanes"].append(row)
                print("CI_SHAPE_LANE:", row["name"], row["state"], row["reason"], flush=True)
        record["state"], record["reason"] = assess(record, tier=tier, commit=commit, image=image)
    except (Unknown, OSError, subprocess.SubprocessError, ValueError) as exc:
        detail = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            detail += "\n" + (exc.stdout or "") + (exc.stderr or "")
        record.update(state="UNKNOWN", reason=detail[-2000:])
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record
