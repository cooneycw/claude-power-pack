#!/usr/bin/env python3
"""Physical canary fixtures plus a real tiny pytest child, never the full suite."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib import ci_shape_check as shape  # noqa: E402


def fixture(work, fault):
    """Run the production clone/probe and collector against owned tiny inputs."""
    git, make = shutil.which("git"), shutil.which("make")
    if not git or not make:
        raise shape.Unknown("canary needs Git and Make")
    seed = work / "seed"
    seed.mkdir()
    (seed / "scripts").mkdir()
    (seed / "CLAUDE.md").write_text("fixture source\n")
    (seed / "scripts/flow-finish-gate.sh").write_text("#!/bin/sh\nexit 0\n")
    (seed / "scripts/flow-finish-gate.sh").chmod(0o755)
    files: dict[str, dict[str, list[str]]] = {}
    for selector in shape.SELECTORS:
        file, _, selected = selector.partition("::")
        name, _, param = selected.partition("[")
        files.setdefault(file, {}).setdefault(name or "test_canary", []).extend([param[:-1]] if param else [])
    for witness in (*shape.REQUIRED_WITNESSES.values(), *shape.EXPECTED_HISTORY_SKIPS):
        file, selected = witness.split("::")
        name, _, param = selected.partition("[")
        files.setdefault(file, {}).setdefault(name, []).extend([param[:-1]] if param else [])
    # A real tiny child still has to clear the production population floor;
    # these are canary cases, not a claim that the full repository suite ran.
    files["tests/test_antigravity_skill_sync.py"]["test_population_floor"] = [
        str(index) for index in range(shape.COLLECTION_FLOOR)]
    for file, functions in files.items():
        path = seed / file
        path.parent.mkdir(exist_ok=True)
        text = "import pytest\n"
        for name, params in functions.items():
            if params:
                text += (f"@pytest.mark.parametrize('value', {[None] * len(params)!r}, ids={params!r})\n"
                         f"def {name}(value):\n    assert True\n")
            else:
                text += f"def {name}():\n    assert True\n"
        path.write_text(text)
    shape.command([git, "init", "-q", seed])
    shape.command([git, "-C", seed, "add", "."])
    shape.command([git, "-C", seed, "-c", "user.name=Fixture", "-c",
                   "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                   "commit", "-qm", "canary inputs"])
    commit = shape.command([git, "-C", seed, "rev-parse", "HEAD"]).stdout.strip()
    stage = work / "staged"
    stage.mkdir()
    for name, binary in (("git", git), ("make", make)):
        (stage / name).symlink_to(binary)
    env = dict(os.environ)
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
    donor, witness = shape.donor(seed, work, git, commit, env)
    rows = []
    for partial in (False, True):
        lane = work / shape.LANES[int(partial)]
        lane.mkdir()
        (lane / "home").mkdir(mode=0o700)
        (lane / "tmp-real").mkdir()
        (lane / "tmp-link").symlink_to(lane / "tmp-real", target_is_directory=True)
        path_env = shape.fresh_environment(lane / "home", lane / "tmp-link",
                                          shape.minimal_path(lane, stage, Path(sys.executable)))
        mask = os.umask(0)
        try:
            checkout = shape.checkout(donor, witness, lane, git, partial, path_env)
        finally:
            os.umask(mask)
        if fault == "mode":
            (checkout / "CLAUDE.md").chmod(0o644)
            assert (checkout / "CLAUDE.md").stat().st_mode & 0o777 == 0o644
        elif fault == "symlink":
            (lane / "tmp-link").unlink()
            (lane / "tmp-link").mkdir()
            assert not (lane / "tmp-link").is_symlink()
        elif fault == "ci":
            path_env["CI"] = "false"
            assert path_env["CI"] != "true"
        elif fault in {"git", "make"}:
            path_env["PATH"] = str(lane / "system-bin")
            assert shutil.which(fault, path=path_env["PATH"]) is None
        elif fault == "filter" and partial:
            shape.command([git, "-C", checkout, "config", "remote.origin.partialclonefilter", "blob:none"])
            assert shape.command([git, "-C", checkout, "config", "--get",
                                  "remote.origin.partialclonefilter"]).stdout.strip() != "tree:0"
        elif fault == "shallow":
            (checkout / ".git/shallow").unlink()
            assert not (checkout / ".git/shallow").exists()
        pin = commit if fault == "history" else shape.HISTORICAL_PIN
        if fault == "history":
            assert shape.command([git, "-C", checkout, "cat-file", "-e", pin]).returncode == 0
        tier = "image" if os.getuid() == 0 else "local"
        preconditions, details = shape.observe(checkout, lane, witness, git, stage, path_env,
                                              tier, partial, historical_pin=pin)
        results_path = lane / "results.json"
        child_env = {**path_env, "PYTHONPATH": str(ROOT),
                     "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                     "CPP_CI_SHAPE_EXPECTED_SKIPS": json.dumps(shape.EXPECTED_HISTORY_SKIPS, sort_keys=True),
                     "CPP_CI_SHAPE_RESULTS": str(results_path)}
        if fault == "history-policy-missing":
            assert json.loads(child_env["CPP_CI_SHAPE_EXPECTED_SKIPS"]) == shape.EXPECTED_HISTORY_SKIPS
            del child_env["CPP_CI_SHAPE_EXPECTED_SKIPS"]
            assert "CPP_CI_SHAPE_EXPECTED_SKIPS" not in child_env
        child = subprocess.run([
            sys.executable, "-m", "pytest", "--rootdir", str(checkout),
            "-p", "lib.ci_shape_pytest", "--override-ini", "addopts=", "-q",
            *[str(checkout / selector) for selector in shape.SELECTORS],
        ], cwd=lane, env=child_env, capture_output=True, text=True, timeout=30)
        results = json.loads(results_path.read_text())
        if fault == "history-policy-missing":
            assert all(results["outcomes"][node] == "passed" and node not in results["skips"]
                       for node in shape.EXPECTED_HISTORY_SKIPS)
        diagnostic = ""
        if fault == "internalerror":
            fake = subprocess.run([sys.executable, "-c", "print('INTERNALERROR> worker failed')"],
                                  capture_output=True, text=True, check=True)
            assert fake.returncode == 0 and "INTERNALERROR>" in fake.stdout
            assert shape.completion(results, 0, "", tier)[0] == "GOOD"
            diagnostic = fake.stdout
        elif fault == "zero-executed":
            fake = subprocess.run([sys.executable, "-c", "print('no tests ran')"],
                                  capture_output=True, text=True, check=True)
            assert fake.returncode == 0 and "INTERNALERROR" not in fake.stdout
            results = {"selected": [], "outcomes": {}, "skips": {}, "errors": [], "exit": 0}
            assert not results["outcomes"]
            diagnostic = fake.stdout
        elif fault == "incomplete":
            assert results["selected"]
            del results["outcomes"][results["selected"][0]]
            assert set(results["selected"]) != set(results["outcomes"])
        elif fault == "false-root-skip":
            node = shape.REQUIRED_WITNESSES["1909-modes"]
            assert results["outcomes"][node] == "passed"
            results["outcomes"][node] = "skipped"
            results["skips"][node] = "requires real root (deliberately false label on non-root witness)"
        elif fault == "missing-witness":
            missing_node = shape.REQUIRED_WITNESSES["1923"]
            assert missing_node in results["selected"]
            results["selected"].remove(missing_node)
            del results["outcomes"][missing_node]
            assert len(results["selected"]) >= shape.COLLECTION_FLOOR
        elif fault == "below-floor":
            retained = list(shape.REQUIRED_WITNESSES.values())
            retained += [node for node in results["selected"] if node not in retained][
                :shape.COLLECTION_FLOOR - 1 - len(retained)]
            results["selected"] = retained
            results["outcomes"] = {node: results["outcomes"][node] for node in retained}
            assert len(retained) == shape.COLLECTION_FLOOR - 1
        elif fault in {"history-pass", "history-missing", "history-reason"}:
            node = sorted(shape.EXPECTED_HISTORY_SKIPS)[0]
            assert results["outcomes"][node] == "skipped"
            assert shape.EXPECTED_HISTORY_SKIPS[node] in results["skips"][node]
            if fault == "history-pass":
                results["outcomes"][node] = "passed"
                del results["skips"][node]
                assert node not in results["skips"]
            elif fault == "history-missing":
                results["selected"].remove(node)
                del results["outcomes"][node]
                del results["skips"][node]
                assert node not in results["selected"]
            else:
                results["skips"][node] = "historical installer skipped for an unexamined reason"
                assert shape.EXPECTED_HISTORY_SKIPS[node] not in results["skips"][node]
        rows.append({"name": shape.LANES[int(partial)], "state": "GOOD", "reason": "canary",
                     "expected_skips": dict(shape.EXPECTED_HISTORY_SKIPS),
                     "preconditions": preconditions, **details, "results": results,
                     "exit": child.returncode, "diagnostic": diagnostic,
                     "counts": {"selected": len(results["selected"]),
                                "executed": len(results["outcomes"]) - len(results["skips"]),
                                "skipped": len(results["skips"])}})
    tier = "image" if os.getuid() == 0 else "local"
    actual_umask = os.umask(0)
    os.umask(actual_umask)
    for row in rows:
        row["test_umask"] = f"{actual_umask:03o}"
    if fault == "history-declaration":
        assert rows[0]["expected_skips"] == shape.EXPECTED_HISTORY_SKIPS
        del rows[0]["expected_skips"]
        assert "expected_skips" not in rows[0]
    profile = {"state": "GOOD", "image": shape.image_pin(ROOT), "umask": actual_umask,
               "evidence": "controlled tiny canary process; does not attest a CI image"}
    if fault == "umask-mismatch":
        rows[0]["test_umask"] = "777" if actual_umask != 0o777 else "000"
        assert rows[0]["test_umask"] != f"{actual_umask:03o}"
    elif fault == "umask-unknown":
        profile = {"state": "UNKNOWN", "reason": "CI default not proven"}
    root_state = ({"state": "GOOD", "reason": "real uid 0 in pinned validate image"}
                  if tier == "image" else
                  {"state": "UNKNOWN", "reason": "not examined: needs real uid 0"})
    if fault == "root-claim":
        # This BAD remains meaningful even when the controls run as actual root:
        # a LOCAL receipt is never image/root evidence, regardless of caller uid.
        tier = "local"
        root_state = {"state": "GOOD", "reason": "root-like HOME"}
        assert root_state["state"] == "GOOD" and tier == "local"
    if fault == "unavailable":
        (stage / "make").unlink()
        assert not (stage / "make").exists()
        rows[0].update(state="UNKNOWN", reason="required tool unavailable")
        assert rows[0]["state"] == "UNKNOWN"
    return {"schema": 1, "tier": tier, "commit": commit, "image": shape.image_pin(ROOT),
            "selectors": list(shape.SELECTORS), "root": root_state, "lanes": rows,
            "pytest_time_umask": profile}


def main():
    gate, case = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    fault = json.loads((case / "case.json").read_text())["fault"]
    with tempfile.TemporaryDirectory(prefix="cpp-shape-control-") as temporary:
        work = Path(temporary).resolve()
        if fault.startswith("bootstrap-"):
            git = shutil.which("git")
            if not git:
                print("CI_SHAPE_CONTROL: unavailable - Git missing")
                return 2
            shape.command([git, "init", "-q", work])
            (work / "owned.py").write_text("# frozen code\n")
            shape.command([git, "-C", work, "add", "."])
            commit_command = [git, "-C", work, "-c", "user.name=Fixture", "-c",
                              "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                              "commit", "-qm", "fixture"]
            shape.command(commit_command)
            base = shape.command([git, "-C", work, "rev-parse", "HEAD"]).stdout.strip()
            doc = work / "docs/measurements/ci-shape-check.md"
            doc.parent.mkdir(parents=True)
            doc.write_text("observed profile evidence\n")
            if fault == "bootstrap-code":
                (work / "owned.py").write_text("# changed code after root checkpoint\n")
            shape.command([git, "-C", work, "add", "."])
            shape.command(commit_command)
            changed = shape.command([git, "-C", work, "diff", "--name-only", base, "HEAD"]).stdout
            assert ("owned.py" in changed) == (fault == "bootstrap-code")
            child = subprocess.run([sys.executable, str(gate), "bootstrap", "--root", str(work),
                                    "--base", base], capture_output=True, text=True, timeout=30)
            print(child.stdout + child.stderr, end="")
            return child.returncode
        if fault == "backend":
            empty = work / "empty-path"
            empty.mkdir()
            assert shutil.which("docker", path=str(empty)) is None
            child = subprocess.run([sys.executable, str(gate), "run", "--tier", "image",
                                    "--receipt", str(work / "missing-backend.json")],
                                   env={**os.environ, "PATH": str(empty)},
                                   capture_output=True, text=True, timeout=30)
            print(child.stdout + child.stderr, end="")
            return child.returncode
        try:
            record = fixture(work, fault)
        except shape.Unknown as exc:
            print("CI_SHAPE_CONTROL: unavailable -", exc)
            return 2
        receipt = work / "receipt.json"
        receipt.write_text(json.dumps(record))
        child = subprocess.run([sys.executable, str(gate), "verify", str(receipt),
                                "--tier", record["tier"], "--commit", record["commit"]],
                               capture_output=True, text=True, timeout=30)
        print(child.stdout + child.stderr, end="")
        return child.returncode


if __name__ == "__main__":
    sys.exit(main())
