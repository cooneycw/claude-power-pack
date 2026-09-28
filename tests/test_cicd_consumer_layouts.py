"""Consumer repository layouts: what detection reports, and what it does not cover.

Issue #1289. `detect_framework` read subdirectories only when the ROOT had no
marker, so a root `package.json` made a nested `backend/pyproject.toml` vanish
from the result; sibling `frontend/` + `backend/` came back MULTI with no
runners and no statement that nothing would run them; and a lock-less Django
project got `unknown` and an empty runner map because Django was promoted before
a package-manager fallback that only matched plain Python.

This is a small executable fixture matrix, not a testing platform: each layout
is a set of empty marker files built in a temp directory, its preconditions are
asserted before detection runs, and nothing is installed or executed.

The contract has two halves and both are pinned here:

- ENUMERATION (new): every component is listed with its path, framework,
  package manager and the files that decided them; `runner_resolution` says how
  far the root-level runner defaults reach - and it is REPORTING ONLY.
- COMPATIBILITY (unchanged): the six pre-#1289 fields are what `makefile.py` and
  `manifest.py` generate from, so for every single-root layout they must equal
  what they were on bdbe0fb. The one intended change is lock-less Django.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from lib.cicd.detector import detect_framework
from lib.cicd.manifest import generate_manifest, get_manifest_plan_steps
from lib.cicd.detector import _NON_COMPONENT_DIRS, _resolve_runners
from lib.cicd.models import (
    FRAMEWORK_RUNNERS,
    RESOLUTION_PARTIAL,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNKNOWN,
    RESOLUTION_UNRESOLVED,
    Component,
    Framework,
    PackageManager,
)
from lib.cicd.runner import DeterministicRunner

#: layout name -> marker files (relative paths). Every file is created empty
#: (JSON files as `{}`); detection reads names, never contents.
LAYOUTS: dict[str, list[str]] = {
    "python-uv": ["pyproject.toml", "uv.lock"],
    "python-pip-requirements": ["requirements.txt"],
    "node-npm": ["package.json", "package-lock.json"],
    "node-yarn": ["package.json", "yarn.lock"],
    "go": ["go.mod", "go.sum"],
    "rust": ["Cargo.toml", "Cargo.lock"],
    "django-uv": ["pyproject.toml", "uv.lock", "manage.py"],
    "django-no-lock": ["pyproject.toml", "manage.py"],
    "python-with-docs-site": ["pyproject.toml", "uv.lock", "docs/package.json"],
    "python-with-build-dirs": [
        "pyproject.toml",
        "uv.lock",
        "node_modules/package.json",
        ".venv/pyproject.toml",
        "venv/pyproject.toml",
        "dist/setup.py",
        "build/setup.py",
        "vendor/go.mod",
        "__pycache__/pyproject.toml",
        "site-packages/setup.py",
        "pkg.egg-info/setup.py",
    ],
    "root-node-nested-python": [
        "package.json",
        "package-lock.json",
        "backend/pyproject.toml",
        "backend/uv.lock",
    ],
    "sibling-frontend-backend": ["frontend/package.json", "backend/pyproject.toml"],
}

#: What each layout's runner coverage must be. Stated as data so the matrix is
#: also the report of every examined layout and whether it is fully supported.
EXPECTED_RESOLUTION: dict[str, str] = {
    "python-uv": RESOLUTION_RESOLVED,
    "python-pip-requirements": RESOLUTION_RESOLVED,
    "node-npm": RESOLUTION_RESOLVED,
    "node-yarn": RESOLUTION_RESOLVED,
    "go": RESOLUTION_RESOLVED,
    "rust": RESOLUTION_RESOLVED,
    "django-uv": RESOLUTION_RESOLVED,
    "django-no-lock": RESOLUTION_RESOLVED,
    # A docs site with its own package.json IS a Node stack the root Python
    # runners do not run; reporting it is correct, and runner_commands are
    # unchanged (pinned in LEGACY below).
    "python-with-docs-site": RESOLUTION_PARTIAL,
    "python-with-build-dirs": RESOLUTION_RESOLVED,
    "root-node-nested-python": RESOLUTION_PARTIAL,
    "sibling-frontend-backend": RESOLUTION_UNRESOLVED,
}

#: The pre-#1289 fields, captured on bdbe0fb, for every layout whose consumer
#: output must not move. (framework, package_manager, detected_files); the
#: runner map is pinned as FRAMEWORK_RUNNERS[(framework, package_manager)].
LEGACY: dict[str, tuple[Framework, PackageManager, list[str]]] = {
    "python-uv": (Framework.PYTHON, PackageManager.UV, ["pyproject.toml", "uv.lock"]),
    "python-pip-requirements": (Framework.PYTHON, PackageManager.PIP, ["requirements.txt"]),
    "node-npm": (Framework.NODE, PackageManager.NPM, ["package.json", "package-lock.json"]),
    "node-yarn": (Framework.NODE, PackageManager.YARN, ["package.json", "yarn.lock"]),
    "go": (Framework.GO, PackageManager.GO, ["go.mod", "go.sum"]),
    "rust": (Framework.RUST, PackageManager.CARGO, ["Cargo.toml", "Cargo.lock"]),
    "django-uv": (Framework.DJANGO, PackageManager.UV, ["pyproject.toml", "uv.lock", "manage.py"]),
    "python-with-docs-site": (Framework.PYTHON, PackageManager.UV, ["pyproject.toml", "uv.lock"]),
    "python-with-build-dirs": (Framework.PYTHON, PackageManager.UV, ["pyproject.toml", "uv.lock"]),
    "root-node-nested-python": (
        Framework.NODE,
        PackageManager.NPM,
        ["package.json", "package-lock.json"],
    ),
}


def _build(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    for rel in LAYOUTS[name]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n" if rel.endswith(".json") else "")
    # Precondition: the layout under test is the one described, file by file.
    for rel in LAYOUTS[name]:
        assert (root / rel).is_file(), f"fixture precondition: {rel} was not created"
    return root


def _uncovered(info) -> list[tuple[str, str]]:
    return [(c.path, c.framework.value) for c in info.uncovered_components]


def _components(info) -> dict[str, tuple[str, str, list[str]]]:
    return {
        c.path: (c.framework.value, c.package_manager.value, c.evidence) for c in info.components
    }


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_every_examined_layout_reports_its_runner_coverage(tmp_path: Path, name: str) -> None:
    """The matrix IS the report: every layout gets a stated coverage verdict."""
    info = detect_framework(_build(tmp_path, name))
    assert info.runner_resolution == EXPECTED_RESOLUTION[name], info.to_dict()
    if info.runner_resolution != RESOLUTION_RESOLVED:
        assert info.resolution_reason, "a non-resolved verdict must say why"
        assert info.uncovered_components, "a non-resolved verdict must name what is uncovered"
    else:
        assert info.uncovered_components == []


@pytest.mark.parametrize("name", sorted(LEGACY))
def test_single_root_consumer_inputs_are_unchanged(tmp_path: Path, name: str) -> None:
    """Condition 3 of the #1289 review: runner_resolution is REPORTING ONLY.

    makefile.py and manifest.py generate from these fields alone, so equal fields
    mean equal generated output. (Measured directly as well, on bdbe0fb vs this
    change: generate_makefile, generate_manifest and check_makefile are
    byte-identical for every one of these layouts.)
    """
    framework, pm, detected = LEGACY[name]
    info = detect_framework(_build(tmp_path, name))
    assert info.framework == framework
    assert info.package_manager == pm
    assert info.detected_files == detected
    assert info.runner_commands == FRAMEWORK_RUNNERS.get((framework, pm), {})


def test_a_root_manifest_no_longer_hides_a_nested_stack(tmp_path: Path) -> None:
    """THE #1289 RED CASE. On bdbe0fb the backend was absent from the result."""
    info = detect_framework(_build(tmp_path, "root-node-nested-python"))
    assert _components(info) == {
        ".": ("node", "npm", ["package.json", "package-lock.json"]),
        "backend": ("python", "uv", ["backend/pyproject.toml", "backend/uv.lock"]),
    }
    # The root still drives the primary result (single-stack behaviour kept)...
    assert info.framework == Framework.NODE
    # ...and the run it implies is stated as covering the root only.
    assert info.runner_resolution == RESOLUTION_PARTIAL
    assert _uncovered(info) == [("backend", "python")]
    assert info.uncovered_summary() == "backend/ (python)"


def test_sibling_stacks_are_enumerated_and_stated_unresolved(tmp_path: Path) -> None:
    """MULTI with no runners must SAY that nothing will run them."""
    info = detect_framework(_build(tmp_path, "sibling-frontend-backend"))
    assert info.framework == Framework.MULTI
    assert info.runner_commands == {}
    assert _components(info) == {
        "backend": ("python", "pip", ["backend/pyproject.toml"]),
        "frontend": ("node", "npm", ["frontend/package.json"]),
    }
    assert info.runner_resolution == RESOLUTION_UNRESOLVED
    assert "mixed execution cannot be inferred" in info.resolution_reason
    assert _uncovered(info) == [("backend", "python"), ("frontend", "node")]


def test_lockless_django_gets_the_pip_fallback_and_django_runners(tmp_path: Path) -> None:
    """THE #1289 RED CASE. On bdbe0fb: django / unknown / {}."""
    info = detect_framework(_build(tmp_path, "django-no-lock"))
    assert info.framework == Framework.DJANGO
    assert info.package_manager == PackageManager.PIP
    assert info.runner_commands == FRAMEWORK_RUNNERS[(Framework.DJANGO, PackageManager.PIP)]
    assert info.runner_commands, "precondition: (DJANGO, PIP) runners exist"
    assert _components(info) == {".": ("django", "pip", ["pyproject.toml", "manage.py"])}


#: The exclusions the review asked for, written out HERE rather than read from
#: `_NON_COMPONENT_DIRS`: parametrizing over the set under test would delete a
#: case together with the exclusion it checks (measured - removing "vendor"
#: removed its case too).
EXPECTED_EXCLUSIONS = [
    "node_modules", "venv", "vendor", "dist", "build", "__pycache__",
    "site-packages", ".venv", ".tox", "pkg.egg-info",
]


def test_the_exclusion_list_is_the_one_reviewed() -> None:
    assert _NON_COMPONENT_DIRS == frozenset(
        {"node_modules", "venv", "vendor", "dist", "build", "__pycache__", "site-packages"}
    )


@pytest.mark.parametrize("excluded", EXPECTED_EXCLUSIONS)
def test_an_excluded_directory_is_not_a_component(tmp_path: Path, excluded: str) -> None:
    """Condition 2 of the #1289 review: the exclusion list, exercised one by one.

    The marker sits DIRECTLY inside the excluded directory - the only depth
    enumeration reads - and the same layout with an ordinary directory name is
    the control that shows the exclusion is what changes the result. (The first
    cut nested these markers two levels down, where they were never reached, so
    deleting an exclusion could not fail it: counter-model review.)
    """
    def layout(dirname: str) -> Path:
        root = tmp_path / dirname.replace(".", "_dot_")
        (root / dirname).mkdir(parents=True)
        (root / "pyproject.toml").write_text("")
        (root / "uv.lock").write_text("")
        (root / dirname / "package.json").write_text("{}\n")
        assert (root / dirname / "package.json").is_file(), "fixture precondition"
        return root

    assert list(_components(detect_framework(layout(excluded)))) == ["."]
    control = detect_framework(layout("frontend"))
    assert list(_components(control)) == [".", "frontend"], "control must see the stack"


def test_two_stacks_in_one_uncovered_directory_are_both_named(tmp_path: Path) -> None:
    """One directory can hold two stacks; the summary must name both (review)."""
    root = _build(tmp_path, "root-node-nested-python")
    (root / "backend" / "package.json").write_text("{}\n")
    info = detect_framework(root)
    assert _uncovered(info) == [("backend", "python"), ("backend", "node")]
    assert info.uncovered_summary() == "backend/ (python, node)"


def test_a_root_component_of_another_framework_is_not_covered() -> None:
    """Runner defaults cover ONE framework at the root, not every root stack (review).

    Unreachable through detect_framework today - two root stacks make the
    primary MULTI, with no runners - so the rule is pinned at the function.
    """
    runners = FRAMEWORK_RUNNERS[(Framework.PYTHON, PackageManager.UV)]
    components = [
        Component(".", Framework.PYTHON, PackageManager.UV, ["pyproject.toml"]),
        Component(".", Framework.NODE, PackageManager.NPM, ["package.json"]),
    ]
    state, _reason, uncovered = _resolve_runners(Framework.PYTHON, runners, components)
    assert state == RESOLUTION_PARTIAL
    assert [(c.path, c.framework) for c in uncovered] == [(".", Framework.NODE)]


def test_an_unlistable_root_reports_coverage_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """"Could not look" must not resolve as "nothing else is here" (review)."""
    root = _build(tmp_path, "python-uv")
    real_iterdir = Path.iterdir

    def iterdir(self):
        if self == root:
            raise PermissionError("denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    info = detect_framework(root)
    assert info.runner_resolution == RESOLUTION_UNKNOWN
    assert "could not be listed (PermissionError)" in info.resolution_reason
    # The root itself was readable, so the legacy fields are unaffected.
    assert info.framework == Framework.PYTHON


def _run_check(root: Path) -> str:
    log = StringIO()
    steps = get_manifest_plan_steps(generate_manifest(root), "check")
    DeterministicRunner(project_root=root, output=log).run("check", step_defs=steps)
    return log.getvalue()


def test_the_skipped_gate_cause_names_uncovered_components(tmp_path: Path) -> None:
    """Condition 1 of the #1289 review: a true verdict with a false reason.

    The skip conditions read only the ROOT Makefile and pyproject.toml. On
    bdbe0fb the siblings layout reported "(no Makefile target and no configured
    tool)" - false for a backend whose own pyproject configures its tools.
    """
    root = _build(tmp_path, "sibling-frontend-backend")
    (root / "backend" / "pyproject.toml").write_text("[tool.ruff]\n[tool.pytest.ini_options]\n")
    assert "ruff" in (root / "backend" / "pyproject.toml").read_text(), "precondition"
    text = _run_check(root)
    assert "completed WITH WARNINGS" in text
    assert "no configured tool at the repository root" in text
    assert "backend/ (python), frontend/ (node) not covered by root runners (unresolved)" in text


def test_a_single_root_skip_names_no_components(tmp_path: Path) -> None:
    """The other half: a plain root project is not accused of hiding anything."""
    text = _run_check(_build(tmp_path, "python-uv"))
    assert "no configured tool at the repository root)" in text
    assert "not covered by root runners" not in text


def test_a_failed_detection_reports_coverage_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reporting must neither end the run nor go quiet when detection fails."""
    root = _build(tmp_path, "python-uv")
    steps = get_manifest_plan_steps(generate_manifest(root), "check")

    def boom(_root):
        raise OSError("unreadable")

    monkeypatch.setattr("lib.cicd.detector.detect_framework", boom)
    log = StringIO()
    result = DeterministicRunner(project_root=root, output=log).run("check", step_defs=steps)
    assert result.success
    assert "component coverage UNKNOWN (detection failed: OSError)" in log.getvalue()
