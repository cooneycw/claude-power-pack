"""A test must not rebuild the environment it is running in (issue #1718).

Two tests run the shipped finish path, which pins Python 3.11 with
`uv run --python 3.11 --project "$CPP_DIR"`. Pointed at the checkout the suite
runs from, uv made THAT checkout's `.venv` match the pin: on a host whose
`.venv` was first built on another minor, it removed it mid-suite. One of the
two runs offline with an empty cache, so the rebuilt environment stayed empty
and every later test that needed a dependency failed - 274 of them in one
run, all reading `No module named 'yaml'`, and all first taken for load.

`tests/conftest.py::owned_cpp_checkout` gives those tests a copy of the CPP
runtime with its own environment. These tests hold the two things that fix
rests on: the copy really is separate and usable, and the fingerprint used to
show "the surrounding environment is unchanged" can tell a changed one.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import venv_fingerprint

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="requires uv")


def test_the_owned_checkout_is_a_different_directory_with_its_own_environment(owned_cpp_checkout: Path) -> None:
    assert owned_cpp_checkout.resolve() != ROOT.resolve()
    assert ROOT.resolve() not in owned_cpp_checkout.resolve().parents, "the copy lives inside this checkout"
    assert (owned_cpp_checkout / ".venv").resolve() != (ROOT / ".venv").resolve()
    assert not (owned_cpp_checkout / ".venv").is_symlink()
    for part in ("lib/cicd", "scripts/flow-finish-gate.sh", "pyproject.toml", "uv.lock"):
        assert (owned_cpp_checkout / part).exists(), part


def test_the_owned_environment_is_python_3_11_with_the_runtime_dependencies(owned_cpp_checkout: Path) -> None:
    """Asked of the environment's own interpreter, never through `uv run`,
    which would repair it before answering."""
    python = owned_cpp_checkout / ".venv" / "bin" / "python"
    version = subprocess.run([str(python), "--version"], capture_output=True, text=True, timeout=30, check=False)
    assert version.stdout.startswith("Python 3.11."), version.stdout + version.stderr
    deps = subprocess.run([str(python), "-c", "import yaml, pydantic"], capture_output=True, text=True,
                          timeout=30, check=False)
    assert deps.returncode == 0, deps.stderr


def test_the_owned_copy_is_of_the_working_tree_not_of_a_commit(owned_cpp_checkout: Path) -> None:
    """It must test what is being edited. Compared file by file with the
    working tree's own scripts, which is what the suite is run against."""
    for script in sorted((ROOT / "scripts").glob("flow-finish-gate.sh")) + sorted((ROOT / "lib" / "cicd").glob("*.py")):
        relative = script.relative_to(ROOT)
        assert (owned_cpp_checkout / relative).read_bytes() == script.read_bytes(), relative


# --- the fingerprint can tell a changed environment ---------------------------

def _fake_venv(path: Path, version: str = "3.12.14", packages: tuple[str, ...] = ("yaml", "pytest")) -> Path:
    site = path / "lib" / f"python{version.rsplit('.', 1)[0]}" / "site-packages"
    site.mkdir(parents=True)
    for name in packages:
        (site / name).mkdir()
    (path / "pyvenv.cfg").write_text(f"home = /usr/bin\nversion_info = {version}\n")
    return path


def test_no_environment_reads_as_none(tmp_path: Path) -> None:
    assert venv_fingerprint(tmp_path / "absent") is None


def test_the_same_environment_reads_the_same_twice(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path / "venv")
    assert venv_fingerprint(venv) == venv_fingerprint(venv) == ("3.12.14", ("pytest", "yaml"))


@pytest.mark.parametrize("damage", ["emptied", "one-package-gone", "rebuilt-on-another-python", "removed"])
def test_a_changed_environment_reads_differently(tmp_path: Path, damage: str) -> None:
    """Each is what the old tests did to the surrounding environment, or part of it."""
    venv = _fake_venv(tmp_path / "venv")
    before = venv_fingerprint(venv)
    if damage == "emptied":
        shutil.rmtree(venv / "lib" / "python3.12" / "site-packages")
        (venv / "lib" / "python3.12" / "site-packages").mkdir()
    elif damage == "one-package-gone":
        shutil.rmtree(venv / "lib" / "python3.12" / "site-packages" / "pytest")
    elif damage == "rebuilt-on-another-python":
        shutil.rmtree(venv)
        _fake_venv(venv, version="3.11.16", packages=())
    else:
        shutil.rmtree(venv)
    assert venv_fingerprint(venv) != before


def test_this_suites_own_environment_has_a_fingerprint_when_it_exists() -> None:
    """The real `.venv`, read the same way: an interpreter version and a
    non-empty package list. Where the suite is not run from a `.venv` there
    is nothing to protect and nothing to read."""
    found = venv_fingerprint(ROOT / ".venv")
    if found is None:
        pytest.skip("this suite is not running from a .venv in the checkout")
    version, names = found
    assert version[0].isdigit(), version
    assert names, "the surrounding environment is EMPTY - it has been wrecked (issue #1718)"


def test_the_interpreters_own_bytecode_cache_is_not_a_change(tmp_path: Path) -> None:
    """A first run of the interpreter writes `site-packages/__pycache__`.
    That is not something a test did to the environment."""
    venv = _fake_venv(tmp_path / "venv")
    before = venv_fingerprint(venv)
    (venv / "lib" / "python3.12" / "site-packages" / "__pycache__").mkdir()
    assert venv_fingerprint(venv) == before
