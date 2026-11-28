"""Real private clone/collector on tiny named canaries, not the real 41 tests."""
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
from tests.test_ci_shape_replay import damage  # noqa: E402


def fixture(work, fault):
    git, make = shutil.which("git"), shutil.which("make")
    if not git or not make:
        raise shape.Unknown("replay canary needs Git and Make")
    seed = work / "seed"
    seed.mkdir()
    for name in ("scripts", "lib", "tests"):
        (seed / name).mkdir()
    (seed / "CLAUDE.md").write_text("controlled clone input\n")
    (seed / "scripts/flow-finish-gate.sh").write_text("#!/bin/sh\nexit 0\n")
    (seed / "scripts/flow-finish-gate.sh").chmod(0o755)
    (seed / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    (seed / "lib/__init__.py").write_text("")
    shutil.copyfile(ROOT / "lib/ci_shape_pytest.py", seed / "lib/ci_shape_pytest.py")
    text, previous = "import pytest\n", None
    first = shape.RUNNER_REPLAY_SELECTORS[0]
    for node in shape.RUNNER_REPLAY_SELECTORS:
        _, cls, function = node.split("::")
        if cls != previous:
            text += "\nclass " + cls + ":\n"
            previous = cls
        if fault == "skipped" and node == first:
            text += "    @pytest.mark.skip(reason='controlled mandatory replay skip')\n"
        text += f"    def {function}(self):\n        assert True\n"
    (seed / "tests/test_runner.py").write_text(text)
    if fault == "skipped":
        assert "@pytest.mark.skip(reason='controlled mandatory replay skip')" in text
    if fault == "duplicate-report":
        (seed / "tests/conftest.py").write_text(
            "from pathlib import Path\n"
            "def pytest_configure(config):\n    global configuration\n    configuration = config\n"
            "def pytest_runtest_logreport(report):\n"
            f"    if report.when == 'call' and report.nodeid == {first!r}:\n"
            "        assert report.passed\n"
            "        collector = configuration.pluginmanager.get_plugin('cpp-ci-shape-results')\n"
            "        collector.pytest_runtest_logreport(report)\n"
            "        Path(__file__).with_name('duplicate-sent').write_text('one extra call report')\n")
    env = shape.fresh_environment(work, work, os.environ["PATH"])
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    shape.command([git, "init", "-q", seed], env=env)
    shape.command([git, "-C", seed, "config", "gc.autoDetach", "false"], env=env)
    shape.command([git, "-C", seed, "add", "."], env=env)
    shape.command([git, "-C", seed, "-c", "user.name=Fixture", "-c",
                   "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                   "-c", "core.hooksPath=/dev/null", "commit", "-qm", "replay canary"], env=env)
    commit = shape.command([git, "-C", seed, "rev-parse", "HEAD"], env=env).stdout.strip()
    stage = work / "stage"
    stage.mkdir()
    (stage / "git").symlink_to(git)
    if fault != "make":
        (stage / "make").symlink_to(make)
    else:
        assert shutil.which("make", path=str(stage)) is None
    donor, witness = shape.donor(seed, work, git, commit, env)
    logs = work / "logs"
    logs.mkdir()
    mask = os.umask(0)
    os.umask(mask)
    tier = "image" if os.getuid() == 0 else "local"
    lane = shape.run_lane(seed, donor, witness, work / "r", stage, Path(sys.executable),
                          tier, False, logs, mask, profile=shape.REPLAY_PROFILE)
    if fault == "duplicate-report":
        sent = work / "r/checkout/tests/duplicate-sent"
        assert sent.read_text() == "one extra call report"
    elif fault not in {"make", "skipped"}:
        assert lane["state"] == "GOOD", lane
    record = {"schema": 1, "tier": tier, "commit": commit, "image": shape.image_pin(ROOT),
              "selectors": list(shape.RUNNER_REPLAY_SELECTORS), "lanes": [lane],
              "state": "GOOD", "reason": "controlled producer claim",
              "root": {"state": "GOOD", "reason": "real uid 0 in pinned validate image"}
              if tier == "image" else {"state": "UNKNOWN", "reason": "not examined: needs real uid 0"},
              "pytest_time_umask": {"state": "GOOD", "image": shape.image_pin(ROOT), "umask": mask,
                                    "evidence": "controlled fixture, not pinned-image qualification"}}
    if fault not in {"make", "skipped", "duplicate-report"}:
        damage(record, fault)
    return record


def main():
    gate, case = map(Path, sys.argv[1:3])
    fault = json.loads((case / "case.json").read_text())["fault"]
    with tempfile.TemporaryDirectory(prefix="rr-canary-") as owned:
        try:
            record = fixture(Path(owned), fault)
        except (shape.Unknown, OSError, subprocess.SubprocessError) as exc:
            print("RUNNER_REPLAY_CONTROL: unavailable - " + str(exc))
            return 3
        path = Path(owned) / "receipt.json"
        path.write_text(json.dumps(record))
        result = subprocess.run([
            sys.executable, str(gate), "verify", str(path), "--profile", shape.REPLAY_PROFILE,
            "--tier", record["tier"], "--commit", record["commit"],
        ], capture_output=True, text=True, timeout=60)
        print(result.stdout, end="")
        print(result.stderr, file=sys.stderr, end="")
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
