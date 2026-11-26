"""Real maintained readers and plain-runtime production installations."""
import json
import os
import shutil
import subprocess
import venv
from pathlib import Path

import pytest

from tests.test_host_update_adapters import CLI, cli
from tests.test_host_update_adapters import source as source_fixture
from tests.test_host_update_adapters import source_template as template_fixture
from tests.test_host_update_links import seed

source_template = template_fixture
source = source_fixture
pytestmark = pytest.mark.skipif(
    not shutil.which("git") or not shutil.which("python3"),
    reason="git and python3 required for real plain-runtime sources",
)


def plain_environment(home):
    git = shutil.which("git")
    assert git is not None
    env = {"HOME": str(home), "PATH": str(Path(git).parent) + os.pathsep + os.defpath,
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    assert shutil.which("git", path=env["PATH"]) == git, "plain runtime must retain the actual Git binary"
    return env


@pytest.fixture(scope="module")
def plain_python(tmp_path_factory):
    root = tmp_path_factory.mktemp("stdlib-runtime")
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(root)
    executable = root / "bin/python"
    # The parent uses the owner's -I -S setup. The pinned child launches the
    # same executable without those flags: prove its empty venv also has no
    # YAML, so an ambient site installation cannot hide a child import bug.
    for flags in (("-I", "-S"), ("-I",)):
        checked = subprocess.run(
            [str(executable), *flags, "-B", "-c",
             "import json,fcntl,importlib.util; "
             "assert importlib.util.find_spec('yaml') is None; print('stdlib-without-yaml')"],
            env=plain_environment(root), capture_output=True, text=True, check=True,
        )
        assert checked.stdout.strip() == "stdlib-without-yaml"
    return executable


def plain_cli(executable, source, home, operation, *selected):
    args = [str(executable), "-I", "-S", "-B", str(CLI), operation,
            "--source-root", str(source), "--home", str(home), "--json"]
    for harness in selected:
        args += ["--select", harness]
    result = subprocess.run(args, env=plain_environment(home), cwd=home.parent,
                            capture_output=True, text=True, timeout=120)
    assert result.stdout, result.stderr
    return result, json.loads(result.stdout)


@pytest.mark.parametrize("scenario", ["claude-links", "codex", "mixed-unavailable"])
def test_plain_runtime_production_without_yaml(source, tmp_path, plain_python, scenario):
    home = tmp_path / "home"
    if scenario != "codex":
        seed(home, source)
        setup, report = cli(source, home)
        assert setup.returncode == 0, report
    if scenario == "claude-links":
        result, report = plain_cli(plain_python, source, home, "verify", "claude-links")
    elif scenario == "codex":
        result, report = plain_cli(plain_python, source, home, "refresh", "codex")
    else:
        result, report = plain_cli(plain_python, source, home, "refresh",
                                   "codex", "claude-topics", "antigravity")
    rows = {r["harness"]: r for r in report["results"]}
    if scenario == "mixed-unavailable":
        assert result.returncode == 4, report
        for name in ("claude-topics", "antigravity"):
            row = rows[name]
            assert row["exit_code"] == 4 and row["after"]["state"] == "unknown", row
            assert "UNAVAILABLE" in row["reason"] and name in row["reason"] and "yaml" in row["reason"], row
        successful = ("codex", "claude-links")
    else:
        assert result.returncode == 0, report
        successful = (scenario,)
    for name in successful:
        row = rows[name]
        assert row["exit_code"] == 0 and row["after"]["state"] == "current", row
        assert row["after"]["examined_members"] == row["after"]["expected_members"] > 0
    if scenario != "claude-links":
        assert (home / ".codex/skills/flow-auto/SKILL.md").is_file()
