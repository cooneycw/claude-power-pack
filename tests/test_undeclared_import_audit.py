"""Tests for scripts/undeclared-import-audit.py (issue #1041).

These are a SECOND OPINION FROM A DIFFERENT PROCESS. `controls/undeclared-import-audit`
asks the gate to judge committed cases and the harness judges the answers; a harness
mutated to agree with itself would report PASS about itself. These tests drive the gate
by subprocess and assert on exit codes and stdout, which is the shape
`tests/test_negative_controls.py` uses for the same reason.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
GATE = REPO / "scripts" / "undeclared-import-audit.py"
CONTROL = REPO / "controls" / "undeclared-import-audit"

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2

#: The CI `validate` image carries no git (scripts/check-test-binary-guards.py
#: pins the list), so a test that shells out to it must say so rather than fail there.
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git absent in the CI validate image")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True, text=True, timeout=120, check=False,
    )


def tree(root: Path, pyproject: str, files: dict[str, str], allow: str | None = None) -> Path:
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    if allow is not None:
        (root / ".undeclared-import-allow").write_text(allow, encoding="utf-8")
    return root


#: The delivery-pilot shape: a module that puts its own `src/` on `sys.path`
#: before importing from it. The gate grants a `src/` exemption only to a file
#: that does this, so the header is load-bearing in these fixtures, not decoration.
PILOT = (
    "import sys\n"
    "from pathlib import Path\n"
    'sys.path.insert(0, str(Path(__file__).parent / "src"))\n'
)

MINIMAL = '[project]\nname = "t"\nversion = "0"\ndependencies = ["pydantic>=2.0"]\n'


# --------------------------------------------------------------------------- #
# The distinction the gate exists to draw
# --------------------------------------------------------------------------- #

def test_a_module_level_undeclared_import_is_a_finding(tmp_path: Path) -> None:
    tree(tmp_path, MINIMAL, {"m.py": "import requests\n"})
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_FINDING, result.stdout
    assert "UNDECLARED-IMPORT: m.py:1" in result.stdout


def test_declared_type_stubs_do_not_satisfy_the_package_they_stub(tmp_path: Path) -> None:
    """The exact state issue #1041 was filed against.

    `types-requests` CONTAINS "requests", so a gate matching on substrings reports
    this tree clean. It is the registered anchor's blindness, pinned here as well
    because it is the single most likely way a future edit reintroduces it.
    """
    tree(
        tmp_path,
        '[project]\nname = "t"\nversion = "0"\ndependencies = []\n'
        '\n[project.optional-dependencies]\ndev = ["types-requests>=2.31"]\n',
        {"m.py": "import requests\n"},
    )
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_FINDING, result.stdout
    assert "`requests`" in result.stdout


def test_a_package_declared_only_in_an_extra_counts_as_declared(tmp_path: Path) -> None:
    """The mechanism #1041 used to close the guarded half: `uv` resolves every
    extra into `uv.lock`, so an extra is under the advisory scan."""
    tree(
        tmp_path,
        '[project]\nname = "t"\nversion = "0"\ndependencies = []\n'
        '\n[project.optional-dependencies]\naws = ["boto3>=1.34"]\n',
        {"m.py": "import boto3\n"},
    )
    assert run("--root", str(tmp_path)).returncode == EXIT_OK


def test_an_import_name_that_differs_from_its_distribution_resolves_through_the_alias(tmp_path: Path) -> None:
    tree(tmp_path, '[project]\nname = "t"\nversion = "0"\ndependencies = ["pyyaml>=6.0"]\n', {"m.py": "import yaml\n"})
    assert run("--root", str(tmp_path)).returncode == EXIT_OK


def test_an_unknown_alias_reds_rather_than_passing_quietly(tmp_path: Path) -> None:
    """Step 3 of resolution is fail-CLOSED, and that is deliberate.

    A table that fell through to "assume declared" would reintroduce exactly the
    blindness the gate removes, so a name that resolves to nothing is a finding.
    """
    tree(tmp_path, MINIMAL, {"m.py": "import some_unmapped_package\n"})
    assert run("--root", str(tmp_path)).returncode == EXIT_FINDING


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("def f():\n    import requests\n    return requests\n", id="function-body"),
        pytest.param("try:\n    import requests\nexcept ImportError:\n    requests = None\n", id="import-error-guard"),
        pytest.param(
            "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    import requests\n",
            id="type-checking",
        ),
    ],
)
def test_an_import_that_cannot_crash_an_importer_is_not_a_finding(tmp_path: Path, body: str) -> None:
    tree(tmp_path, MINIMAL, {"m.py": body})
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_OK, result.stdout


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("try:\n    pass\nfinally:\n    import requests\n", id="finally"),
        pytest.param("try:\n    pass\nexcept ValueError:\n    pass\nelse:\n    import requests\n", id="try-else"),
        pytest.param("try:\n    import pydantic\nexcept ImportError:\n    import requests\n", id="except-body"),
        pytest.param("import contextlib\n\nwith contextlib.suppress(Exception):\n    import requests\n", id="with"),
        pytest.param("for _ in range(1):\n    import requests\n", id="for"),
        pytest.param("while False:\n    import requests\n", id="while"),
        pytest.param("class C:\n    import requests\n", id="class-body"),
        pytest.param(
            "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    pass\nelse:\n    import requests\n",
            id="type-checking-else",
        ),
        pytest.param(
            "from typing import TYPE_CHECKING\n\nif not TYPE_CHECKING:\n    import requests\n",
            id="not-type-checking",
        ),
    ],
)
def test_every_context_that_executes_at_import_is_a_finding(tmp_path: Path, body: str) -> None:
    """Counter-model review, HIGH. The first cut deferred all nine of these and
    reported each one clean, while every one of them runs during import.

    Two were the same mistake twice: `if TYPE_CHECKING:`'s exemption was decided by
    searching the test expression for the NAME, so `not TYPE_CHECKING` matched and
    the `else:` of a plain `if TYPE_CHECKING:` was exempted along with the body.
    An `except ImportError:` handler's own body is here too - the guard protects
    the name in the `try`, not the one in the fallback that runs when it fails.
    """
    tree(tmp_path, MINIMAL, {"m.py": body})
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_FINDING, f"this context executes at import: {result.stdout}"


def test_an_unreadable_if_condition_fails_closed(tmp_path: Path) -> None:
    """A test this gate cannot classify must not become an exemption: branches it
    cannot read are branches that might run."""
    tree(tmp_path, MINIMAL, {"m.py": "import os\n\nif os.environ.get('X'):\n    import requests\n"})
    assert run("--root", str(tmp_path)).returncode == EXIT_FINDING


def test_a_try_without_an_import_error_handler_is_still_a_finding(tmp_path: Path) -> None:
    """The guard is what makes the import safe, so a `try:` catching something
    unrelated does not earn the exemption."""
    tree(tmp_path, MINIMAL, {"m.py": "try:\n    import requests\nexcept ValueError:\n    requests = None\n"})
    assert run("--root", str(tmp_path)).returncode == EXIT_FINDING


def test_a_local_module_behind_a_sys_path_insert_is_not_third_party(tmp_path: Path) -> None:
    """`tests/fixtures/delivery_pilots/` does exactly this; without the rule the
    gate reports two findings that are not third-party imports at all."""
    tree(
        tmp_path,
        MINIMAL,
        {
            "tool/src/retry.py": "def backoff(n):\n    return n\n",
            "tool/check.py": (
                "import sys\nfrom pathlib import Path\n\n"
                'sys.path.insert(0, str(Path(__file__).parent / "src"))\n\n'
                "import retry  # noqa: E402\n\nprint(retry.backoff(1))\n"
            ),
        },
    )
    assert run("--root", str(tmp_path)).returncode == EXIT_OK


def test_an_unrelated_src_fixture_does_not_suppress_a_production_import(tmp_path: Path) -> None:
    """Counter-model review, MEDIUM. A `src/` exemption is scoped to the directory
    that inserts it; the first cut made every `src/` stem first-party everywhere,
    so `tests/fixtures/delivery_pilots/.../src/retry.py` silently suppressed an
    unrelated production `import retry` anywhere in the repository."""
    tree(
        tmp_path,
        MINIMAL,
        {
            "fixtures/pilot/src/retry.py": "def backoff(n):\n    return n\n",
            "fixtures/pilot/check.py": (
                "import sys\nfrom pathlib import Path\n"
                'sys.path.insert(0, str(Path(__file__).parent / "src"))\n'
                "import retry  # noqa: E402\n\nprint(retry)\n"
            ),
            "prod/service.py": "import retry\n",
        },
    )
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_FINDING, result.stdout
    assert "prod/service.py" in result.stdout
    assert "fixtures/pilot/check.py" not in result.stdout, "the inserting module must still resolve its own src/"


def test_a_nested_src_module_does_not_mask_an_unrelated_import_name(tmp_path: Path) -> None:
    """Counter-model re-review, MEDIUM. `tool/src/acme/requests.py` is importable as
    `acme.requests`, not as `requests`, so recording every descendant's stem made a
    deeply-nested file mask an undeclared `import requests` at the top level."""
    tree(
        tmp_path,
        MINIMAL,
        {
            "tool/src/acme/requests.py": "x = 1\n",
            "tool/check.py": PILOT + "import requests  # noqa: E402\n\nprint(requests)\n",
        },
    )
    assert run("--root", str(tmp_path)).returncode == EXIT_FINDING


def test_a_package_under_src_is_importable_by_its_directory_name(tmp_path: Path) -> None:
    """The other direction of the same defect: recording `__init__` as the stem
    left a legitimate `import acme` reported as undeclared."""
    tree(
        tmp_path,
        MINIMAL,
        {
            "tool/src/acme/__init__.py": "",
            "tool/check.py": PILOT + "import acme  # noqa: E402\n\nprint(acme)\n",
        },
    )
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_OK, result.stdout


def test_a_src_exemption_requires_evidence_that_something_sets_the_path(tmp_path: Path) -> None:
    """Counter-model re-review, MEDIUM. Scoping the exemption to the owner subtree
    narrowed the leak without closing it: every file under the owner inherited its
    names whether or not anything put that directory on `sys.path`."""
    tree(tmp_path, MINIMAL, {"tool/src/requests.py": "x = 1\n", "tool/check.py": "import requests\n"})
    assert run("--root", str(tmp_path)).returncode == EXIT_FINDING


def test_the_real_delivery_pilot_shape_still_resolves(tmp_path: Path) -> None:
    """The half that matters: the three fixes above must not have made the shape
    they exist to serve red. `tests/fixtures/delivery_pilots/pilots/*/check_*.py`
    is this tree, and a false red here blocks every merge in the repository."""
    tree(
        tmp_path,
        MINIMAL,
        {
            "tool/src/retry.py": "def backoff(n):\n    return n\n",
            "tool/check.py": PILOT + "import retry  # noqa: E402\n\nprint(retry.backoff(1))\n",
        },
    )
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_OK, result.stdout


def test_the_verdict_does_not_depend_on_where_the_checkout_sits(tmp_path: Path) -> None:
    """Counter-model review, MEDIUM. The first cut tested the ABSOLUTE path's parts
    for a `src` component, so a checkout under `/home/user/src/` turned every
    Python file's stem into a global exemption."""
    root = tmp_path / "src" / "checkout"
    root.mkdir(parents=True)
    tree(root, MINIMAL, {"m.py": "import requests\n"})
    assert run("--root", str(root)).returncode == EXIT_FINDING


def test_a_virtual_environment_in_the_tree_cannot_change_the_verdict(tmp_path: Path) -> None:
    """Counter-model review, MEDIUM. Environments were pruned by NAME, and `.venv`
    and `venv` are two spellings of many. An `env/` that slipped the list put its
    whole site-packages tree into the population, so a neighbour's installed
    imports would red this project against this project's metadata."""
    tree(tmp_path, MINIMAL, {"m.py": "import json\n"})
    env = tmp_path / "env" / "lib" / "python3.11" / "site-packages"
    env.mkdir(parents=True)
    (tmp_path / "env" / "pyvenv.cfg").write_text("home = /usr\nversion = 3.11.0\n", encoding="utf-8")
    (env / "dep.py").write_text("import neighbour_support\n", encoding="utf-8")
    assert (tmp_path / "env" / "pyvenv.cfg").is_file(), "fixture must carry the environment marker"
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_OK, result.stdout
    assert "1 virtual environment(s) by marker" in result.stdout, "the exclusion must print, not be silent"


# --------------------------------------------------------------------------- #
# The ledger, in both directions
# --------------------------------------------------------------------------- #

def test_a_ledger_entry_accepts_the_import_it_names(tmp_path: Path) -> None:
    tree(tmp_path, MINIMAL, {"m.py": "import boto3\n"}, allow="allow m.py boto3 #1041\n")
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_OK, result.stdout
    assert "1 accepted" in result.stdout


def test_a_ledger_entry_that_accounts_for_nothing_is_a_finding(tmp_path: Path) -> None:
    """The direction a blanket skip has no way to express: without it a line
    outlives the import it records and becomes a permanent blindfold."""
    tree(tmp_path, MINIMAL, {"m.py": "import json\n"}, allow="allow gone.py requests #1041\n")
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_FINDING, result.stdout
    assert "UNDECLARED-IMPORT-STALE:" in result.stdout


def test_acceptance_is_keyed_on_the_import_name_not_only_the_file(tmp_path: Path) -> None:
    """Otherwise one recorded exception silently accepts every undeclared import
    added to that file afterwards."""
    tree(tmp_path, MINIMAL, {"m.py": "import boto3\nimport requests\n"}, allow="allow m.py boto3 #1041\n")
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_FINDING, result.stdout
    assert "`requests`" in result.stdout
    assert "UNDECLARED-IMPORT: m.py:1" not in result.stdout, "the accepted import must not be reported"


# --------------------------------------------------------------------------- #
# Unknown is never a pass
# --------------------------------------------------------------------------- #

def test_a_tree_with_no_pyproject_is_unknown_not_clean(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("import requests\n", encoding="utf-8")
    assert not (tmp_path / "pyproject.toml").exists(), "fixture must lack pyproject.toml"
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_UNKNOWN, result.stdout
    assert "UNDECLARED-IMPORT-UNKNOWN:" in result.stdout


def test_a_zero_file_population_is_unknown_not_clean(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(MINIMAL, encoding="utf-8")
    assert not list(tmp_path.rglob("*.py")), "fixture must contain no Python at all"
    result = run("--root", str(tmp_path))
    assert result.returncode == EXIT_UNKNOWN, result.stdout


def test_a_file_that_will_not_parse_is_unknown_not_clean(tmp_path: Path) -> None:
    """"could not read it" and "it is clean" are different facts."""
    tree(tmp_path, MINIMAL, {"m.py": "def broken(:\n"})
    assert run("--root", str(tmp_path)).returncode == EXIT_UNKNOWN


def test_a_malformed_ledger_line_is_unknown_not_silently_skipped(tmp_path: Path) -> None:
    tree(tmp_path, MINIMAL, {"m.py": "import json\n"}, allow="this is not a record\n")
    assert run("--root", str(tmp_path)).returncode == EXIT_UNKNOWN


def test_no_unknown_path_shares_an_exit_code_with_clean(tmp_path: Path) -> None:
    assert EXIT_UNKNOWN != EXIT_OK


# --------------------------------------------------------------------------- #
# What the gate must NOT do
# --------------------------------------------------------------------------- #

def test_the_gate_never_reads_the_ambient_environment() -> None:
    """Pinned as a property of the SOURCE, parsed rather than grepped.

    `importlib.metadata.packages_distributions()` maps import names to
    distributions exactly, and using it would make the verdict depend on what
    happens to be installed - green on a box with boto3 for unrelated reasons, red
    in CI. That is the ambient-scan failure #1044 closed one gate over. A prose
    note in the docstring cannot fail; this can.
    """
    import ast

    forbidden = {"importlib.metadata", "importlib_metadata", "pkg_resources"}
    tree_ = ast.parse(GATE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree_):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not (imported & forbidden), f"the gate must not read installed distributions: {imported & forbidden}"

    calls = {
        node.func.attr
        for node in ast.walk(tree_)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "packages_distributions" not in calls
    assert "distributions" not in calls


def test_the_success_line_reports_the_population_it_examined(tmp_path: Path) -> None:
    """The detector contract: a success message must not claim more than its input
    population supports. The count of guarded names is printed too, so "clean"
    cannot be read as "nothing else was imported"."""
    tree(tmp_path, MINIMAL, {"m.py": "import json\n"})
    out = run("--root", str(tmp_path)).stdout
    assert "file(s) examined" in out
    assert "pruned:" in out
    assert "guarded/deferred name(s) are outside this gate's question" in out


# --------------------------------------------------------------------------- #
# The control, and the live half
# --------------------------------------------------------------------------- #

def test_the_selftest_reports_the_planted_import_and_stays_silent_on_the_clean_tree() -> None:
    result = run("--selftest")
    assert result.returncode == EXIT_OK, result.stdout + result.stderr
    assert "selftest ok" in result.stdout


@requires_git
def test_the_live_selftest_fixtures_are_tracked() -> None:
    """A control exercised from the working tree that is not IN the repository
    behaves correctly here and does not exist in a clean clone (issue #978)."""
    live = CONTROL / "live"
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "--", str(live)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert out.returncode == 0, f"git ls-files failed: {out.stderr}"
    tracked = {line.strip() for line in out.stdout.splitlines() if line.strip()}
    assert tracked, "the live selftest fixtures are untracked, so a clone has no positive control"


@pytest.mark.parametrize(
    "case,expected",
    [
        ("bad-stub-only-declaration", EXIT_FINDING),
        ("bad-second-import-unaccounted", EXIT_FINDING),
        ("bad-stale-allow", EXIT_FINDING),
        ("good-all-declared", EXIT_OK),
        ("good-allowed-accounted", EXIT_OK),
    ],
)
def test_each_registered_case_scores_as_the_manifest_declares(case: str, expected: int) -> None:
    path = CONTROL / "cases" / case
    result = run("--root", str(path), "--allow-file", str(path / ".undeclared-import-allow"))
    assert result.returncode == expected, f"{case}: {result.stdout}{result.stderr}"


@pytest.mark.parametrize(
    "case",
    ["bad-stub-only-declaration", "bad-second-import-unaccounted", "bad-stale-allow"],
)
def test_the_registered_anchor_misses_every_known_bad_case(case: str) -> None:
    """The demonstration that the control can fail, asserted from pytest as well
    as from the harness. An anchor that CAUGHT a known-bad input would mean the
    control would not notice this gate regressing to it."""
    manifest = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))
    anchor = CONTROL / manifest["anchors"][0]["path"]
    path = CONTROL / "cases" / case
    result = subprocess.run(
        [sys.executable, str(anchor), "--root", str(path), "--allow-file", str(path / ".undeclared-import-allow")],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == EXIT_OK, f"anchor caught {case}, so the control is not load-bearing: {result.stdout}"


def test_the_registered_anchor_agrees_on_the_known_good_cases() -> None:
    """Anchor sanity: if it disagreed here too it would differ for reasons beyond
    the blindness under test, and the demonstration would not be isolated."""
    manifest = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))
    anchor = CONTROL / manifest["anchors"][0]["path"]
    for case in ("good-all-declared", "good-allowed-accounted"):
        path = CONTROL / "cases" / case
        result = subprocess.run(
            [sys.executable, str(anchor), "--root", str(path), "--allow-file", str(path / ".undeclared-import-allow")],
            capture_output=True, text=True, timeout=120, check=False,
        )
        assert result.returncode == EXIT_OK, f"anchor disagrees on {case}: {result.stdout}"


def load_gate():
    """Import the gate module by path - its filename carries hyphens."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("undeclared_import_audit", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: the gate's frozen dataclasses resolve their own
    # module out of sys.modules, and exec'ing an unregistered module makes that
    # lookup return None.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def live_copy(dest: Path) -> Path:
    """A temp repo root carrying a copy of the committed live fixtures.

    Copied rather than mutated in place: the live fixtures are the repository's own
    positive control, and a test run must not touch them.
    """
    import shutil as _shutil

    target = dest / "controls" / "undeclared-import-audit"
    target.mkdir(parents=True)
    _shutil.copytree(CONTROL / "live", target / "live")
    return dest


def test_the_selftest_passes_on_the_unmutated_fixtures(tmp_path: Path) -> None:
    """The half that matters for a selftest wedged at 'fail'."""
    gate = load_gate()
    assert gate.selftest(live_copy(tmp_path)) == EXIT_OK


def test_the_selftest_refuses_an_unrelated_failure_standing_in_for_the_detection(tmp_path: Path) -> None:
    """Counter-model review, MEDIUM. The first cut compared exit codes only, so a
    bad fixture whose planted import had stopped being detected but whose ledger
    had gone stale still exited 1 - and the selftest printed "reported the planted
    import". An unrelated failure standing in for the intended detection is the
    substitution `UNSIGNALLED` exists to refuse one harness over.
    """
    root = live_copy(tmp_path)
    bad = root / "controls" / "undeclared-import-audit" / "live" / "bad-undeclared"
    bad.joinpath("scraper.py").write_text("import json\n\nprint(json)\n", encoding="utf-8")
    bad.joinpath(".undeclared-import-allow").write_text("allow gone.py requests #1041\n", encoding="utf-8")

    gate = load_gate()
    # Precondition: the mutated tree still fails, so the exit code alone cannot
    # tell this state from a healthy one. That is the whole point of the case.
    code, report = gate.audit(bad, bad / ".undeclared-import-allow")
    assert code == EXIT_FINDING, "the mutated fixture must still exit non-zero"
    assert not any(line.startswith("UNDECLARED-IMPORT: scraper.py") for line in report), (
        "the planted detection must be gone for this fixture to model the hazard"
    )

    assert gate.selftest(root) == EXIT_UNKNOWN, "a stale-ledger red must not stand in for the planted detection"


def test_the_selftest_refuses_two_unrelated_lines_adding_up_to_the_detection(tmp_path: Path) -> None:
    """Counter-model re-review, MEDIUM. The hardened selftest searched the JOINED
    report for the path and the package name independently, so a `scraper.py`
    finding about some OTHER package plus a stale ledger entry mentioning
    `requests` scored as the planted detection - the same substitution the
    previous pass closed, one level down. One line must carry both.
    """
    root = live_copy(tmp_path)
    bad = root / "controls" / "undeclared-import-audit" / "live" / "bad-undeclared"
    bad.joinpath("scraper.py").write_text("import urllib3\n\nprint(urllib3)\n", encoding="utf-8")
    bad.joinpath(".undeclared-import-allow").write_text("allow gone.py requests #1041\n", encoding="utf-8")

    gate = load_gate()
    code, report = gate.audit(bad, bad / ".undeclared-import-allow")
    assert code == EXIT_FINDING, "the mutated fixture must still exit non-zero"
    joined = "\n".join(report)
    assert "UNDECLARED-IMPORT: scraper.py:" in joined, "one line supplies the path"
    assert "`requests`" in joined, "a different line supplies the name"
    assert not any(line.startswith("UNDECLARED-IMPORT: scraper.py:") and "`requests`" in line for line in report), (
        "no single line carries both, which is what makes this a split match"
    )

    assert gate.selftest(root) == EXIT_UNKNOWN


def test_the_selftest_refuses_a_missing_fixture_rather_than_passing(tmp_path: Path) -> None:
    """A control that is not there presents identically to one that passed."""
    root = live_copy(tmp_path)
    import shutil as _shutil

    _shutil.rmtree(root / "controls" / "undeclared-import-audit" / "live" / "bad-undeclared")
    assert not (root / "controls" / "undeclared-import-audit" / "live" / "bad-undeclared").exists(), (
        "fixture must be absent for this case to model the hazard"
    )
    assert load_gate().selftest(root) == EXIT_UNKNOWN


def test_the_repository_itself_is_clean() -> None:
    """The live claim. Everything above proves the gate CAN discriminate; this is
    the statement that it currently reports this tree clean, which is the thing
    `make verify` and CI actually read."""
    result = run("--root", str(REPO))
    assert result.returncode == EXIT_OK, result.stdout + result.stderr
