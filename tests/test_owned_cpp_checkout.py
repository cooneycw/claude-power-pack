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

from tests.conftest import build_owned_cpp_checkout, venv_fingerprint

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
        (site / name / "__init__.py").write_text("")
        (site / name / "core.py").write_text("")
    (path / "pyvenv.cfg").write_text(f"home = /usr/bin\nversion_info = {version}\n")
    return path


def test_no_environment_reads_as_none(tmp_path: Path) -> None:
    assert venv_fingerprint(tmp_path / "absent") is None


def test_the_same_environment_reads_the_same_twice(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path / "venv")
    assert venv_fingerprint(venv) == venv_fingerprint(venv) == (
        "3.12.14 at /usr/bin", (("pytest", 2), ("yaml", 2)))


@pytest.mark.parametrize("damage", [
    "emptied", "one-package-gone", "rebuilt-on-another-python", "removed",
    "package-hollowed", "another-interpreter-same-version",
])
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
    elif damage == "package-hollowed":
        # the directory is still there under the same name, with nothing in it
        for path in (venv / "lib" / "python3.12" / "site-packages" / "yaml").iterdir():
            path.unlink()
    elif damage == "another-interpreter-same-version":
        (venv / "pyvenv.cfg").write_text("home = /opt/other/bin\nversion_info = 3.12.14\n")
    else:
        shutil.rmtree(venv)
    assert venv_fingerprint(venv) != before


def _holds(found: tuple[str, tuple[tuple[str, int], ...]], package: str) -> bool:
    return dict(found[1]).get(package, 0) > 0


def test_this_suites_own_environment_holds_the_packages_the_suite_needs() -> None:
    """The real `.venv`, read the same way. Where the suite is not run from a
    `.venv` in the checkout there is nothing to protect and nothing to read."""
    found = venv_fingerprint(ROOT / ".venv")
    if found is None:
        pytest.skip("this suite is not running from a .venv in the checkout")
    assert found[0][0].isdigit(), found[0]
    for package in ("yaml", "pytest"):
        assert _holds(found, package), (
            f"the surrounding environment holds no files for {package!r} (issue #1718)")


@pytest.mark.parametrize("packages", [(), ("_virtualenv",)])
def test_an_environment_with_only_its_bootstrap_files_does_not_hold_them(
        tmp_path: Path, packages: tuple[str, ...]) -> None:
    """The reading the check above must refuse: an empty environment, and one
    holding only what `virtualenv` itself puts there."""
    found = venv_fingerprint(_fake_venv(tmp_path / "venv", packages=packages))
    assert found is not None
    assert not _holds(found, "yaml") and not _holds(found, "pytest")


def test_a_package_directory_with_nothing_in_it_does_not_count_as_held(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path / "venv")
    for path in (venv / "lib" / "python3.12" / "site-packages" / "yaml").iterdir():
        path.unlink()
    found = venv_fingerprint(venv)
    assert found is not None and not _holds(found, "yaml") and _holds(found, "pytest")


def test_bytecode_written_inside_a_package_is_not_a_change(tmp_path: Path) -> None:
    """Importing a package writes `.pyc` files under it mid-suite."""
    venv = _fake_venv(tmp_path / "venv")
    before = venv_fingerprint(venv)
    cache = venv / "lib" / "python3.12" / "site-packages" / "yaml" / "__pycache__"
    cache.mkdir()
    (cache / "core.cpython-312.pyc").write_bytes(b"x")
    assert venv_fingerprint(venv) == before


def test_the_interpreters_own_bytecode_cache_is_not_a_change(tmp_path: Path) -> None:
    """A first run of the interpreter writes `site-packages/__pycache__`.
    That is not something a test did to the environment."""
    venv = _fake_venv(tmp_path / "venv")
    before = venv_fingerprint(venv)
    (venv / "lib" / "python3.12" / "site-packages" / "__pycache__").mkdir()
    assert venv_fingerprint(venv) == before


# --- a build that fails is an error, not a skip -------------------------------

def test_a_build_that_fails_with_its_prerequisites_present_is_an_error(tmp_path: Path) -> None:
    """A skip here would let a broken lock or project file turn every test of
    the real gate off and leave the suite green."""
    probe = subprocess.run(["uv", "python", "find", "3.11", "--no-python-downloads"],
                           capture_output=True, text=True, timeout=60, check=False)
    if probe.returncode != 0:
        pytest.skip("requires a Python 3.11 interpreter")
    broken = tmp_path / "source"
    broken.mkdir()
    (broken / "pyproject.toml").write_text("this is [not a project file\n")
    (broken / "uv.lock").write_text("")
    (broken / "lib").mkdir()
    (broken / "scripts").mkdir()
    with pytest.raises(AssertionError, match="did not build"):
        build_owned_cpp_checkout(broken, tmp_path / "copy")
