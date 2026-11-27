"""Exercise real checkout probes and terminal-result collection (#1917)."""
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from lib import ci_shape_check as shape

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shape_case", ROOT / "controls/ci-shape-check/run-case.py")
assert spec and spec.loader
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)


@pytest.mark.skipif(not shutil.which("git") or not shutil.which("make"), reason="Git and Make required")
@pytest.mark.parametrize("fault", ["good", "mode", "symlink", "ci", "git", "make", "filter",
                                 "shallow", "history", "root-claim", "internalerror", "incomplete",
                                 "missing-witness", "below-floor", "umask-mismatch", "umask-unknown", "unavailable"])
def test_physical_canary_and_real_collector(tmp_path, fault):
    receipt = cases.fixture(tmp_path, fault)
    state, reason = shape.assess(receipt, tier=receipt["tier"], commit=receipt["commit"],
                                image=shape.image_pin(ROOT))
    assert state == {"good": "GOOD", "unavailable": "UNKNOWN", "umask-unknown": "UNKNOWN"}.get(fault, "BAD"), reason


@pytest.mark.skipif(not shutil.which("git") or not shutil.which("make"), reason="Git and Make required")
def test_receipt_cannot_cross_commit_tier_image_or_population(tmp_path):
    original = cases.fixture(tmp_path, "good")
    for field, value in (("commit", "0" * 40), ("tier", "other"), ("image", "unpinned"),
                         ("selectors", []), ("lanes", [])):
        bad = copy.deepcopy(original)
        bad[field] = value
        assert bad[field] != original[field]
        assert shape.assess(bad, tier=original["tier"], commit=original["commit"],
                            image=original["image"])[0] == "BAD"


@pytest.mark.skipif(not shutil.which("git") or not shutil.which("make"), reason="Git and Make required")
def test_removing_any_required_witness_refuses_manifest_and_collection(tmp_path):
    receipt = cases.fixture(tmp_path, "good")
    results = receipt["lanes"][0]["results"]
    for witness in shape.REQUIRED_WITNESSES.values():
        narrowed = tuple(selector for selector in shape.SELECTORS if not shape.selector_matches(witness, selector))
        assert not any(shape.selector_matches(witness, selector) for selector in narrowed)
        assert not shape.manifest_complete(narrowed)
        damaged = copy.deepcopy(results)
        assert witness in damaged["selected"]
        damaged["selected"].remove(witness)
        damaged["outcomes"].pop(witness)
        damaged["skips"].pop(witness, None)
        assert shape.completion(damaged, 0, "", receipt["tier"])[0] == "BAD"


@pytest.mark.parametrize("payload", [{}, {"selected": []}, {"selected": [], "outcomes": {},
                                                           "skips": {}, "errors": [], "exit": 0}])
def test_exit_zero_without_completion_is_bad(payload):
    assert shape.completion(payload, 0, "", "local")[0] == "BAD"


def test_ci_profile_requires_digest_bound_observed_umask(tmp_path):
    (tmp_path / ".woodpecker.yml").write_text((ROOT / ".woodpecker.yml").read_text())
    target = tmp_path / "controls/ci-shape-check/validate-profile.json"
    target.parent.mkdir(parents=True)
    physical = tmp_path / "physical"
    physical.mkdir()
    # Synthetic RECORD fields exercise only the parser's data binding. This is
    # not a patched process uid or evidence that this test ran an image/root.
    record = cases.fixture(physical, "good")
    record["tier"] = "image"
    record["state"] = "GOOD"
    record["root"] = {"state": "GOOD", "reason": "real uid 0 in pinned validate image"}
    identity = {"uid": 0, "euid": 0, "gid": 0, "egid": 0, "groups": [0]}
    for lane in record["lanes"]:
        lane["identity"] = identity
    observed_path = tmp_path / shape.ROOT_RECEIPT
    observed_path.parent.mkdir(parents=True)
    observed_path.write_text(json.dumps(record))
    good = {"state": "GOOD", "image": shape.image_pin(ROOT),
            "umask": record["pytest_time_umask"]["umask"], "identity": identity,
            "root_checkpoint": record["commit"],
            "receipt_sha256": hashlib.sha256(observed_path.read_bytes()).hexdigest(),
            "evidence": "controlled parser fixture, not live-image evidence"}
    target.write_text(json.dumps(good))
    assert shape.ci_profile(tmp_path) == good
    for field, value in (("state", "UNKNOWN"), ("image", "other"), ("umask", None),
                         ("umask", True), ("umask", 0o1000), ("evidence", None)):
        bad = {**good, field: value}
        assert bad != good
        target.write_text(json.dumps(bad))
        with pytest.raises(shape.Unknown, match="UNKNOWN"):
            shape.ci_profile(tmp_path)
    for field, value in (("umask", 0o077), ("identity", {**identity, "uid": 123}),
                         ("root_checkpoint", "0" * 40), ("receipt_sha256", "0" * 64)):
        bad = {**good, field: value}
        assert bad != good
        target.write_text(json.dumps(bad))
        with pytest.raises(shape.Unknown, match="match"):
            shape.ci_profile(tmp_path)


def test_committed_profile_equals_the_actual_root_receipt_when_published():
    path = ROOT / "controls/ci-shape-check/validate-profile.json"
    profile = json.loads(path.read_text())
    if profile["state"] == "UNKNOWN":
        assert profile["umask"] is None and not (ROOT / shape.ROOT_RECEIPT).exists()
        return
    assert shape.ci_profile(ROOT) == profile
    observed = json.loads((ROOT / shape.ROOT_RECEIPT).read_text())
    assert profile["image"] == observed["image"]
    assert profile["umask"] == observed["pytest_time_umask"]["umask"]
    assert all(profile["identity"] == lane["identity"] for lane in observed["lanes"])


@pytest.mark.parametrize("case,expected", [("bootstrap-good", 0), ("bootstrap-code", 1)])
def test_real_git_bootstrap_carry_accepts_only_named_paths(case, expected):
    result = subprocess.run([sys.executable, str(ROOT / "controls/ci-shape-check/run-case.py"),
                             str(ROOT / "scripts/ci-shape-check.py"),
                             str(ROOT / "controls/ci-shape-check/cases" / case)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == expected, result.stdout + result.stderr


def test_plugin_records_actual_skips_and_internal_errors(tmp_path, pytester, monkeypatch):
    # The collector is exercised by pytest's own hook runner, not JSON fabricated
    # in this test. The physical controls separately launch a normal subprocess.
    result = tmp_path / "results.json"
    monkeypatch.setenv("CPP_CI_SHAPE_RESULTS", str(result))
    pytester.makepyfile("import pytest\n@pytest.mark.skip(reason='needs real uid 0')\ndef test_root(): pass")
    pytester.runpytest_inprocess("-p", "lib.ci_shape_pytest")
    payload = json.loads(result.read_text())
    assert len(payload["selected"]) == 1 and len(payload["skips"]) == 1
    assert payload["outcomes"] == {payload["selected"][0]: "skipped"}


HISTORY = ROOT / "controls/ci-shape-check/history"
pytestmark = pytest.mark.skipif(not shutil.which("git") or not shutil.which("make"),
                                reason="historical shape witnesses require Git and Make")


def excerpt(name, **namespace):
    rows = json.loads((HISTORY / "provenance.json").read_text())
    record = next(row for row in rows if row["path"] == name + ".txt")
    path = HISTORY / record["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    module = types.ModuleType(name)
    module.__dict__.update(namespace)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def test_1909_historical_inventory_retains_umask_checkout_modes(tmp_path, monkeypatch):
    predecessor = excerpt("1909-modes", hashlib=hashlib)
    checkout, generated = tmp_path / "checkout", tmp_path / "generated"
    checkout.mkdir()
    generated.mkdir()
    (checkout / "docs").mkdir()
    source = checkout / "docs/guide.md"
    source.write_text("fixture guide\n")
    source.chmod(0o666)
    assert source.stat().st_mode & 0o777 == 0o666
    shutil.copy2(source, generated / "guide.md")
    old = predecessor.inventory(generated)
    expected = {"guide.md": [hashlib.sha256(source.read_bytes()).hexdigest(), 0o644]}
    assert old != expected, "historical comparison must be RED for 0666 copied source"
    from tests import test_antigravity_codex_parity as current
    shape.command(["git", "init", "-q", checkout])
    shape.command(["git", "-C", checkout, "add", "."])
    monkeypatch.setattr(current, "ROOT", checkout)
    normalized = current.canonical_source(tmp_path / "normalized")
    assert predecessor.inventory(normalized / "docs") == expected


def test_1916_actual_source_fixture_fails_without_pin_then_owned_history_passes(tmp_path):
    from tests.pi_owner_fixture_tools import fixture_source

    git = shutil.which("git")
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "input").write_text("owned current input")
    shape.command([git, "init", "-q", seed])
    shape.command([git, "-C", seed, "add", "."])
    shape.command([git, "-C", seed, "-c", "user.name=Fixture", "-c",
                   "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                   "commit", "-qm", "current"])
    shallow = tmp_path / "shallow"
    shape.command([git, "clone", "-q", "--depth=1", seed.as_uri(), shallow])
    assert shape.command([git, "-C", shallow, "rev-parse", "--is-shallow-repository"]).stdout.strip() == "true"
    missing = shape.command([git, "-C", shallow, "cat-file", "-e", shape.HISTORICAL_PIN], check=False)
    assert missing.returncode != 0
    class Factory:
        def mktemp(self, name):
            target = tmp_path / name
            target.mkdir()
            return target
    old = excerpt("1916-history", pytest=pytest, subprocess=subprocess, ROOT=shallow,
                  PROBE=types.SimpleNamespace(REVISION=shape.HISTORICAL_PIN))
    with pytest.raises(subprocess.CalledProcessError):
        old.source.__wrapped__(Factory())
    fixed = fixture_source(shallow, tmp_path / "owned-history")
    assert (fixed / "input").read_text() == "owned current input"


def test_1922_real_filtered_commit_presence_does_not_prove_file_contents(tmp_path):
    git = shutil.which("git")
    seed = tmp_path / "seed"
    seed.mkdir()
    shape.command([git, "init", "-q", seed])
    (seed / "HEAD.txt").write_text("current")
    shape.command([git, "-C", seed, "add", "."])
    shape.command([git, "-C", seed, "-c", "user.name=Fixture", "-c",
                   "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
                   "commit", "-qm", "current"])
    commit = shape.command([git, "-C", seed, "rev-parse", "HEAD"]).stdout.strip()
    env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
    donor, witness = shape.donor(seed, tmp_path, git, commit, env)
    clone = shape.checkout(donor, witness, tmp_path, git, True, env)
    assert shape.command([git, "-C", clone, "cat-file", "-e", witness + "^{commit}"], env=env).returncode == 0
    old_read = shape.command([git, "-C", clone, "show", witness + ":old-only.txt"], env=env, check=False)
    assert old_read.returncode != 0, "4056 predecessor's commit-presence inference must fail"
    def old_git(cwd, *args):
        return shape.command([git, "-C", cwd, *args], env=env).stdout.strip()
    old = excerpt("1922-partial", CLI=clone / "scripts/cpp-host-update.py", subprocess=subprocess,
                  pytest=pytest, git=old_git)
    with pytest.raises(subprocess.CalledProcessError):
        old.test_real_historical_installer_population(None, tmp_path, witness, False)
    from tests.conftest import skip_in_partial_clone
    with pytest.raises(pytest.skip.Exception, match="partial clone:"):
        skip_in_partial_clone(clone)


@pytest.mark.skipif(os.geteuid() != 0, reason="requires real root for historical chmod acceptance")
def test_1910_chmod_zero_is_readable_to_real_root_then_real_child_refuses(tmp_path):
    path = tmp_path / "ledger"
    path.write_text("owned fixture")
    path.chmod(0)
    assert path.stat().st_mode & 0o777 == 0
    assert os.access(path, os.R_OK), "root predecessor must not establish unreadability"
    # Current real control asserts permission failure in the SAME demoted child
    # that subsequently executes the real CLI. No mocked Python uid.
    result = subprocess.run([sys.executable, str(ROOT / "controls/pi-skill-install/run-case.py"),
                             str(ROOT / "scripts/pi-skill-sync.py"),
                             str(ROOT / "controls/pi-skill-install/cases/unreadable-install")],
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 4
    assert "unreadable uid=65534 gid=65534 groups=[]" in result.stderr
    assert "PermissionError" in result.stdout


@pytest.mark.skipif(os.geteuid() != 0, reason="requires real root pinned image for historical PATH acceptance")
def test_1910_exact_old_path_fixture_then_fixed_staged_tool_fixture(tmp_path, monkeypatch):
    import runpy

    from tests import test_pi_host_fixture as current

    # This exact predecessor is load-bearing only in the actual slim image:
    # local /usr/bin/git would hide it, as it hid it before PR CI 4030.
    assert shutil.which("git", path="/usr/bin:/bin") is None
    selected_git = shutil.which("git")
    assert selected_git is not None
    subject = runpy.run_path(str(ROOT / "scripts/pi-host-fixture.py"))
    old = excerpt("1910-path", pytest=pytest, shutil=shutil, Path=Path, SUBJECT=subject)
    with monkeypatch.context() as patch:
        with pytest.raises(ValueError, match="Git executable unavailable"):
            old.test_fixture_path_drops_unselected_home_search_entries(tmp_path, patch)
    current.test_fixture_path_drops_unselected_home_search_entries(tmp_path, monkeypatch)


@pytest.mark.skipif(os.geteuid() != 0, reason="requires real root pinned image for owner sanitized PATH acceptance")
def test_1916_unchanged_owner_helper_loses_staged_tools(tmp_path):
    from tests import test_pi_owner_probe as owner
    assert shutil.which("git", path="/usr/local/bin:/usr/bin:/bin") is None
    args = owner.arguments(tmp_path, ROOT)
    with pytest.raises(FileNotFoundError, match="git"):
        owner.PROBE.run(args)
    assert not Path(args.journal).exists()


def test_1922_ci_true_rewritten_assertion_is_bounded_after_fix(tmp_path):
    # Extracted unchanged 79f2edf helper; its frozen 138KB input is already
    # vendored by #1909. Only the assertion syntax differs in the green child.
    reference = ROOT / "controls/antigravity-skill-build/reference/codex-skill-sync-40d25173.py"
    assert reference.stat().st_size > 100_000
    old = (HISTORY / "1922-ci-assert.txt").read_text()
    text = '''import faulthandler, hashlib, pytest
from pathlib import Path
ROOT = Path(ROOT_VALUE)
_RETIRED_CPP_HELPERS = ("friction-log.sh", "commands-mirror-sync.sh", "codex-skill-sync.py",
                        "install-memory-harness.sh", "retired-surface-prune.py", "install-drift.sh")
_FROZEN_GENERATOR_SHA = "395696707af11e0bd181741879534fbe02807fe56f659c189b44e3e45bc5d7ea"
'''.replace("ROOT_VALUE", repr(str(ROOT))) + old + '''
def test_expected_guard_failure():
    _, expected, _, _ = _retired_cpp_generator_fixture()
    bad = expected.replace(b"def is_cpp_checkout_ref(", b"def blind_cpp_checkout_ref(", 1)
    assert bad != expected
    faulthandler.dump_traceback_later(1)
    try:
        with pytest.raises(AssertionError, match="six approved retired CPP exception rows"):
            _assert_only_retired_cpp_data_changed(bad)
    finally:
        faulthandler.cancel_dump_traceback_later()
'''
    env = dict(os.environ, CI="true", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    results = []
    for name, source in (("old", text), ("fixed", text.replace(
            '    assert candidate == expected, "only the six approved retired CPP exception rows may differ"',
            '    if candidate != expected:\n'
            '        raise AssertionError("only the six approved retired CPP exception rows may differ")'))):
        directory = tmp_path / name
        directory.mkdir()
        target = directory / "test_guard.py"
        target.write_text(source)
        try:
            child = subprocess.run([sys.executable, "-m", "pytest", "-q", "-s", str(target),
                                    "-o", "addopts="], cwd=directory, env=env,
                                   capture_output=True, text=True, timeout=4)
            results.append((name, "completed", child.returncode, child.stdout + child.stderr))
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or b"") + (exc.stderr or b"")
            results.append((name, "timeout", None, output.decode(errors="replace")))
    assert results[0][1] == "timeout", "4058 predecessor must reproduce the expensive rich assertion"
    assert "difflib" in results[0][3] or "_pytest/assertion" in results[0][3]
    assert results[1][1:3] == ("completed", 0), results[1][3][-2000:]
