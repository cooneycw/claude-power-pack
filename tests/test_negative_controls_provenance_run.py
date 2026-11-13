"""`--verify-provenance` is run for real, and can say "could not look" (issue #1732).

Every control here rests on its anchor being the artifact its manifest says it
is. The flag that checks that crashed on the real tree until #1719 and was
passed by nothing: no Makefile target, no CI step. So its green had never been
produced by the tree it exists to verify.

Wiring it as it stood would not have been enough. CI clones at depth 1, where a
historical anchor's commit does not exist, and the harness answered
`unverified` for that - the word a constructed anchor gets because it has
nothing to compare WITH. The flag would have printed `unverified` for every
control in CI and stayed green. So a historical anchor that could not be
compared now has its own word, UNCOMPARED, is named with its reason, and fails
under `--strict`.

The committed cases are `controls/check-negative-controls-provenance`; these
tests run the same cases directly, plus the things a control cannot hold: the
count line, the non-strict run, and the real tree.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "check-negative-controls.py"
CONTROL = ROOT / "controls" / "check-negative-controls-provenance"
RUNNER = CONTROL / "run-case.sh"
BLIND = CONTROL / "anchors" / "constructed-flag-never-passed-check-negative-controls.py"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("sh") is None, reason="requires git and sh"
)

COUNT = re.compile(r"^NEGATIVE_CONTROL_PROVENANCE_HISTORICAL: compared=(\d+) uncompared=(\d+) ", re.M)


def run_case(name: str, harness: Path = HARNESS, *,
             provenance_flag: str = "--verify-provenance") -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", str(RUNNER), str(CONTROL / "cases" / name), str(harness), provenance_flag],
                          cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)


def counts(out: str) -> tuple[int, int]:
    found = COUNT.search(out)
    assert found, f"no count line:\n{out[-800:]}"
    return int(found.group(1)), int(found.group(2))


# --- the two ways the comparison is owed -------------------------------------

def test_an_anchor_edited_after_it_was_vendored_is_a_mismatch() -> None:
    done = run_case("bad-anchor-differs-from-its-commit")
    assert done.returncode == 1, done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: MISMATCH" in done.stdout
    assert "-> PROVENANCE:MISMATCH" in done.stdout
    assert counts(done.stdout) == (1, 0), "it WAS compared; that is how the difference was found"


def test_a_commit_that_is_not_in_the_clone_is_uncompared_not_unverified() -> None:
    """The depth-1 case: what CI checks out."""
    done = run_case("bad-commit-not-in-this-clone")
    assert done.returncode == 1, done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: UNCOMPARED" in done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: unverified" not in done.stdout
    assert "-> PROVENANCE:UNCOMPARED" in done.stdout
    assert counts(done.stdout) == (0, 1)
    assert "is not in this clone, which is shallow" in done.stdout, "the reason names the remedy"
    assert "git fetch --unshallow" in done.stdout


def test_a_matching_anchor_is_ok_and_counted_as_compared() -> None:
    done = run_case("good-anchor-matches-its-commit")
    assert done.returncode == 0, done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: ok" in done.stdout
    assert counts(done.stdout) == (1, 0)


def test_a_constructed_anchor_with_no_sha_is_unverified_and_never_fails_for_it() -> None:
    """Project state: a tree with no historical anchor at all. Nothing to
    compare is said in so many words, and it is not a failure."""
    done = run_case("good-constructed-anchor-names-no-commit")
    assert done.returncode == 0, done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: unverified" in done.stdout
    assert "UNCOMPARED" not in done.stdout
    assert counts(done.stdout) == (0, 0)
    assert "no historical anchor is registered here" in done.stdout


def test_matching_bytes_on_a_side_branch_are_not_retained_by_main() -> None:
    done = run_case("bad-anchor-off-main")
    assert done.returncode == 1, done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: OFF_MAIN" in done.stdout
    assert "not an ancestor of" in done.stdout
    assert "on_main=0 off_main=1 unknown=0" in done.stdout
    assert counts(done.stdout) == (1, 0), "bytes were compared; retention is the failed axis"


def test_detached_history_without_main_is_unknown() -> None:
    done = run_case("bad-main-reference-missing")
    assert done.returncode == 1, done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: UNCOMPARED" in done.stdout
    assert "no main reference" in done.stdout
    assert "on_main=0 off_main=0 unknown=1" in done.stdout


def test_a_detached_checkout_with_origin_main_can_prove_retention() -> None:
    done = run_case("good-detached-main-reference")
    assert done.returncode == 0, done.stdout
    assert "on_main=1 off_main=0 unknown=0" in done.stdout


@pytest.mark.parametrize("case", ["bad-anchor-differs-from-its-commit", "bad-commit-not-in-this-clone",
                                  "bad-anchor-off-main", "bad-main-reference-missing"])
def test_the_wiring_before_this_change_passes_both_bad_cases(case: str) -> None:
    """Red case: with the flag never passed, both known-bad trees are green."""
    done = run_case(case, harness=BLIND)
    assert done.returncode == 0, done.stdout
    assert "MISMATCH" not in done.stdout and "UNCOMPARED" not in done.stdout
    assert not COUNT.search(done.stdout), "the count line is printed only when the flag is passed"


# --- built here, for what a committed case cannot pose -----------------------

def _fixture(tmp_path: Path, name: str, *, shallow: bool) -> Path:
    """The same two-commit repository run-case.sh builds, kept for inspection."""
    case = CONTROL / "cases" / name
    repo = tmp_path / "repo"
    shutil.copytree(case, repo)

    def g(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@e.com",
                               "-c", "commit.gpgsign=false", *args], check=True, capture_output=True,
                              text=True, timeout=60).stdout.strip()

    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, timeout=60)
    now = (repo / "scripts" / "toy-gate.sh").read_text()
    (repo / "first-commit-toy-gate.sh").rename(repo / "scripts" / "toy-gate.sh")
    (repo / "shallow-clone").unlink(missing_ok=True)
    g("add", "-A")
    g("commit", "-qm", "first")
    first = g("rev-parse", "HEAD")
    (repo / "scripts" / "toy-gate.sh").write_text(now)
    manifest = repo / "controls" / "toy" / "control.json"
    manifest.write_text(manifest.read_text().replace("@FIRST_COMMIT@", first))
    g("add", "-A")
    g("commit", "-qm", "now")
    if not shallow:
        return repo
    clone = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(clone)],
                   check=True, capture_output=True, timeout=60)
    assert subprocess.run(["git", "-C", str(clone), "cat-file", "-e", first], capture_output=True,
                          check=False).returncode != 0, "precondition: the commit is not in the clone"
    return clone


def harness(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(HARNESS), "--root", str(root), *args],
                          capture_output=True, text=True, timeout=1200, check=False)


def test_without_strict_an_uncompared_anchor_is_named_and_the_exit_is_as_before(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "bad-commit-not-in-this-clone", shallow=True)
    done = harness(root, "--verify-provenance")
    assert "NEGATIVE_CONTROL_PROVENANCE: UNCOMPARED" in done.stdout
    assert counts(done.stdout) == (0, 1)
    assert done.returncode == 0, "only --strict turns could-not-look into a failure"


def test_without_the_flag_nothing_is_compared_counted_or_failed(tmp_path: Path) -> None:
    """The run every caller made until now is unchanged, in a shallow clone too."""
    root = _fixture(tmp_path, "bad-commit-not-in-this-clone", shallow=True)
    done = harness(root, "--strict")
    assert done.returncode == 0, done.stdout
    assert "NEGATIVE_CONTROL_PROVENANCE: unverified" in done.stdout
    assert not COUNT.search(done.stdout) and "UNCOMPARED" not in done.stdout


def test_deepening_the_clone_turns_uncompared_into_ok(tmp_path: Path) -> None:
    """Lane: Checkout. The same tree, depth 1 and then deepened - what the CI
    step does before it runs the flag."""
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=True)
    assert counts(harness(root, "--strict", "--verify-provenance").stdout) == (0, 1)
    subprocess.run(["git", "-C", str(root), "fetch", "-q", "--unshallow", "origin"], check=True,
                   capture_output=True, timeout=60)
    done = harness(root, "--strict", "--verify-provenance")
    assert done.returncode == 0 and counts(done.stdout) == (1, 0), done.stdout


def test_a_digest_mismatch_never_reached_git_and_is_not_counted_as_compared(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    anchor = root / "controls" / "toy" / "anchors" / "first-commit-toy-gate.sh"
    anchor.write_text(anchor.read_text() + "# changed, digest not updated\n")
    done = harness(root, "--strict", "--verify-provenance")
    assert "NEGATIVE_CONTROL_PROVENANCE: MISMATCH" in done.stdout and done.returncode == 1
    assert counts(done.stdout) == (0, 0), "the bytes disagreed with the manifest before any commit was read"
    # ...and that is NOT "none registered": the population is the registrations.
    assert "no historical anchor is registered" not in done.stdout
    assert "of 1 historical anchor(s) registered" in done.stdout
    assert "1 never reached the comparison (its bytes already disagree" in done.stdout


def _make_unavailable(root: Path) -> None:
    """Turn the fixture's toy gate into one whose tool is absent, and commit."""
    (root / "scripts" / "toy-gate.sh").write_text(
        "#!/bin/sh\n#: NEGATIVE-CONTROL: controls/toy\n"
        "echo 'toy-gate: UNAVAILABLE - the toy tool is not installed'\nexit 3\n")
    manifest = root / "controls" / "toy" / "control.json"
    spec = json.loads(manifest.read_text())
    spec["unavailable_signal"] = "^toy-gate: UNAVAILABLE - the toy tool is not installed"
    manifest.write_text(json.dumps(spec))


def _commit(root: Path) -> None:
    for args in (("add", "-A"), ("commit", "-qm", "later")):
        subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@e.com",
                        "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, timeout=60)


def test_a_control_that_cannot_run_here_still_has_its_anchor_compared(tmp_path: Path) -> None:
    """Found by the counter-model review. `make verify` excuses a control whose
    own tool is absent (UNAVAILABLE). The comparison used to live inside the
    scoring path, which returns before it for such a control - so a tampered
    anchor on a control that could not run here was never examined and the
    gate passed. Provenance does not depend on the gate's tool being installed."""
    import hashlib
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    _make_unavailable(root)
    _commit(root)
    posture = ("--strict", "--allow-unavailable")
    clean = harness(root, *posture, "--verify-provenance")
    assert "NEGATIVE_CONTROL_VERDICT: UNAVAILABLE" in clean.stdout, clean.stdout
    assert clean.returncode == 0 and counts(clean.stdout) == (1, 0), "precondition: excused, and still compared"

    anchor = root / "controls" / "toy" / "anchors" / "first-commit-toy-gate.sh"
    anchor.write_text(anchor.read_text() + "# edited after it was vendored\n")
    manifest = root / "controls" / "toy" / "control.json"
    spec = json.loads(manifest.read_text())
    spec["anchors"][0]["sha256"] = hashlib.sha256(anchor.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(spec))
    _commit(root)
    assert harness(root, *posture).returncode == 0, "precondition: without the flag it is excused and green"
    done = harness(root, *posture, "--verify-provenance")
    assert "NEGATIVE_CONTROL_PROVENANCE: MISMATCH" in done.stdout, done.stdout
    assert done.returncode == 1, "an excused verdict must not excuse a tampered anchor"


def test_an_unavailable_control_in_a_shallow_clone_is_uncompared_and_fails_strict(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    _make_unavailable(root)
    _commit(root)
    clone = tmp_path / "shallow2"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{root}", str(clone)], check=True,
                   capture_output=True, timeout=60)
    done = harness(clone, "--strict", "--allow-unavailable", "--verify-provenance")
    assert counts(done.stdout) == (0, 1) and done.returncode == 1, done.stdout


def test_with_no_git_a_historical_anchor_is_uncompared(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    nogit = tmp_path / "bin"
    nogit.mkdir()
    for tool in ("sh", "env"):
        found = shutil.which(tool)
        if found:
            (nogit / tool).symlink_to(found)
    assert shutil.which("git", path=str(nogit)) is None, "precondition: no git on this PATH"
    done = subprocess.run([sys.executable, str(HARNESS), "--root", str(root), "--strict",
                           "--verify-provenance"], capture_output=True, text=True, timeout=300,
                          check=False, env={"PATH": str(nogit)})
    assert "NEGATIVE_CONTROL_PROVENANCE: UNCOMPARED" in done.stdout, done.stdout + done.stderr
    assert "git is not on PATH" in done.stdout


# --- the real tree, and who passes the flag ----------------------------------

def _registered_historical_anchors() -> list[tuple[Path, dict]]:
    """Derived from the registrations, never typed: every anchor of a
    top-level control that DECLARES itself historical. No further filter - a
    filter here is how a registration leaves the population unnoticed."""
    found = []
    for manifest in sorted((ROOT / "controls").glob("*/control.json")):
        for anchor in json.loads(manifest.read_text()).get("anchors", []):
            if anchor.get("kind") == "historical":
                found.append((manifest.parent, anchor))
    return found


def _harness_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_cnc_under_test", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-shallow-repository"],
                   capture_output=True, text=True, check=False).stdout.strip() != "false",
    reason="needs this repository's full history (a shallow or absent clone cannot compare; "
           "CI deepens the clone in the negative-controls step, which runs the flag itself)",
)
def test_every_historical_anchor_in_this_repository_is_its_commits_bytes() -> None:
    """The comparison the issue asked for, anchor by anchor, through the
    harness's own function. Every one must be `ok`: none uncomparable, none
    different - and the population is every historical anchor registered, so
    comparing none could not pass by finding no failures.

    The whole battery under the flag is `make negative-controls` (two minutes,
    over the suite's per-test limit); this is the same question without
    re-running every control's cases."""
    module = _harness_module()
    anchors = _registered_historical_anchors()
    assert len(anchors) >= 40, f"precondition: only {len(anchors)} historical anchors found"
    # In CI's partial clone every read below is a network fetch (issue #1718);
    # the population above is still counted there, the comparison is the
    # negative-controls step's.
    from tests.conftest import skip_in_partial_clone

    skip_in_partial_clone(ROOT)
    verdicts = {
        f"{control.name}/{anchor['path']}": module._provenance(anchor, control / anchor["path"], ROOT, True)
        for control, anchor in anchors
    }
    not_ok = {name: word for name, word in verdicts.items() if word != "ok"}
    assert not not_ok, not_ok
    assert len(verdicts) == len(anchors)


def test_the_orphaned_shellcheck_anchor_no_longer_claims_a_commit() -> None:
    """The first real run found one registration naming a commit that exists
    nowhere (pre-squash, orphaned). It is registered as what can be shown."""
    manifest = json.loads((ROOT / "controls" / "shellcheck-gate" / "control.json").read_text())
    anchor = next(a for a in manifest["anchors"] if a["path"] == "anchors/ed5349c-shellcheck-gate.sh")
    assert anchor["kind"] == "constructed" and "sha" not in anchor
    assert subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", "ed5349c^{commit}"],
                          capture_output=True, check=False).returncode != 0, (
        "ed5349c now resolves in this clone - if it is on main's history the anchor can be historical again")


def test_make_verify_passes_the_flag_strictly() -> None:
    makefile = (ROOT / "Makefile").read_text()
    recipes = [ln for ln in makefile.splitlines() if "check-negative-controls.py" in ln and ln.startswith("\t@")]
    assert any("--verify-provenance" in ln and "--strict" in ln for ln in recipes), recipes


def _ci_step_script() -> tuple[str, str]:
    """(the shell block that decides the flag, the harness command) of the CI
    step, read from the pipeline file as text - no YAML library needed."""
    ci = (ROOT / ".woodpecker.yml").read_text()
    step = ci.split("\n  negative-controls:\n", 1)[1].split("\n  mutation-probe", 1)[0]
    block = step.split("      - |\n", 1)[1].split("\n      - ", 1)
    script = "\n".join(line[8:] if line.startswith("        ") else line for line in block[0].splitlines())
    return script, block[1].splitlines()[0]


def _run_ci_block(tmp_path: Path, event: str | None, *, shallow: str, fetch_rc: int = 0, main_fetch_rc: int = 0):
    """Run the CI step's own shell block against a stub git."""
    script, _command = _ci_step_script()
    work = tmp_path / "ws"
    (work / ".ci-bin").mkdir(parents=True)
    git = work / ".ci-bin" / "git"
    git.write_text(f"""#!/bin/sh
echo "$*" >> "{work}/git.log"
case "$*" in
  *is-shallow-repository*) echo {shallow} ;;
  *"fetch --quiet origin refs/heads/main:refs/remotes/origin/main"*) exit {main_fetch_rc} ;;
  *fetch*) exit {fetch_rc} ;;
esac
""")
    git.chmod(0o755)
    sleeper = work / ".ci-bin" / "sleep"
    sleeper.write_text("#!/bin/sh\nexit 0\n")
    sleeper.chmod(0o755)
    env = {"PATH": f"{work / '.ci-bin'}:/usr/bin:/bin"}
    assert shutil.which("git", path=env["PATH"]) == str(git), "precondition: the stub git is the one found"
    if event is not None:
        env["CI_PIPELINE_EVENT"] = event
    done = subprocess.run(["sh", "-c", script], cwd=work, env=env, capture_output=True, text=True,
                          timeout=60, check=False)
    flag = work / ".ci-bin" / "provenance-flag"
    log = (work / "git.log").read_text() if (work / "git.log").exists() else ""
    return done, (flag.read_text() if flag.exists() else None), log


def test_the_ci_step_runs_the_harness_with_whatever_the_block_decided() -> None:
    _script, command = _ci_step_script()
    assert "check-negative-controls.py --strict $(cat .ci-bin/provenance-flag)" in command, command


def test_on_a_pull_request_ci_deepens_a_shallow_clone_and_passes_the_flag(tmp_path: Path) -> None:
    done, flag, log = _run_ci_block(tmp_path, "pull_request", shallow="true")
    assert done.returncode == 0, done.stdout + done.stderr
    assert flag == "--verify-provenance"
    assert "fetch --quiet --unshallow origin" in log
    assert "fetch --quiet origin refs/heads/main:refs/remotes/origin/main" in log


def test_on_a_pull_request_an_already_deepened_clone_is_not_fetched_again(tmp_path: Path) -> None:
    """The enrolment step shares the workspace and may have deepened it first;
    `--unshallow` on a complete clone is an error, so it must not be tried."""
    done, flag, log = _run_ci_block(tmp_path, "pull_request", shallow="false")
    assert done.returncode == 0 and flag == "--verify-provenance"
    assert "--unshallow" not in log
    assert "fetch --quiet origin refs/heads/main:refs/remotes/origin/main" in log


def test_a_failed_main_reference_fetch_never_passes_the_provenance_flag(tmp_path: Path) -> None:
    done, flag, log = _run_ci_block(tmp_path, "pull_request", shallow="false", main_fetch_rc=1)
    assert done.returncode == 1 and "could not fetch main retention reference" in done.stdout
    assert flag is None
    assert log.count("fetch --quiet origin refs/heads/main:") == 3


def test_a_history_fetch_that_keeps_failing_reds_the_step_and_passes_nothing(tmp_path: Path) -> None:
    done, flag, log = _run_ci_block(tmp_path, "pull_request", shallow="true", fetch_rc=1)
    assert done.returncode == 1 and "could not deepen the clone after 3 attempts" in done.stdout
    assert flag is None, "the harness must not be handed a flag file from a step that failed"
    assert log.count("fetch") == 3


def test_on_a_main_push_the_flag_is_not_passed_and_no_history_is_fetched(tmp_path: Path) -> None:
    done, flag, log = _run_ci_block(tmp_path, "push", shallow="true")
    assert done.returncode == 0 and flag == ""
    assert "fetch" not in log
    assert "main pushes do not verify provenance" in done.stdout


def test_an_event_ci_cannot_name_is_a_failure_not_a_quiet_run_without_the_flag(tmp_path: Path) -> None:
    """The blind wiring this guards against: a variable renamed by the CI
    system, and the flag silently never passed again."""
    done, flag, _log = _run_ci_block(tmp_path, None, shallow="true")
    assert done.returncode == 1 and "CI_PIPELINE_EVENT is not set" in done.stdout
    assert flag is None


def test_the_enrolment_step_tolerates_the_clone_being_deepened_under_it() -> None:
    ci = (ROOT / ".woodpecker.yml").read_text()
    step = ci.split("\n  counter-model-enrolment:\n", 1)[1].split("\n  negative-controls:\n", 1)[0]
    loop = step.split("for attempt in 1 2 3; do", 1)[1].split("done", 1)[0]
    assert loop.index("is-shallow-repository") < loop.index("fetch --quiet --unshallow"), (
        "the clone's state must be re-read inside the loop, before each fetch")


def test_a_missing_anchor_on_a_control_that_cannot_run_here_fails_strict(tmp_path: Path) -> None:
    """Second review pass. Scoring refuses a missing anchor file - when it gets
    that far. A control whose tool is absent returns first and is excused, so
    a registered historical anchor that is simply GONE was counted as
    'unexamined' and the run passed without ever comparing it."""
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    _make_unavailable(root)
    (root / "controls" / "toy" / "anchors" / "first-commit-toy-gate.sh").unlink()
    _commit(root)
    posture = ("--strict", "--allow-unavailable")
    assert harness(root, *posture).returncode == 0, "precondition: excused and green without the flag"
    done = harness(root, *posture, "--verify-provenance")
    assert done.returncode == 1, done.stdout
    assert "the anchor file is missing" in done.stdout
    assert counts(done.stdout) == (0, 1)
    assert "-> PROVENANCE:UNCOMPARED" in done.stdout


def test_every_registered_historical_anchor_ends_in_exactly_one_outcome() -> None:
    """THE PROPERTY the three review findings shared: nothing registered may
    leave the run uncounted. Over every control in this repository, each
    registered historical anchor lands in exactly one of compared (equal or
    different), could-not-compare, or digest-mismatch-before-git - and the
    three add up to the number registered, which is counted here independently
    of the harness.

    Runs in any clone: in a shallow one every anchor is could-not-compare,
    and the sum must still hold."""
    module = _harness_module()
    registered_here = _registered_historical_anchors()
    by_control: dict[Path, int] = {}
    for control, _anchor in registered_here:
        by_control[control] = by_control.get(control, 0) + 1

    total = {"registered": 0, "compared": 0, "uncompared": 0, "unexamined": 0}
    for control in sorted((ROOT / "controls").glob("*/")):
        res = module.Result(gate="x", control_dir=str(control), verdict="PASS")
        module._verify_historical_anchors(res, control, ROOT)
        parts = res.historical_compared + res.historical_uncompared + res.historical_unexamined
        assert parts == res.historical_registered, (
            f"{control.name}: {res.historical_registered} registered, {parts} accounted for")
        assert res.historical_registered == by_control.get(control, 0), control.name
        if res.historical_unexamined:
            assert res.provenance == "MISMATCH", f"{control.name}: unexamined without a MISMATCH"
        if res.historical_uncompared:
            assert res.provenance in ("UNCOMPARED", "MISMATCH"), control.name
        total["registered"] += res.historical_registered
        total["compared"] += res.historical_compared
        total["uncompared"] += res.historical_uncompared
        total["unexamined"] += res.historical_unexamined
    assert total["registered"] == len(registered_here) > 0, total
    assert total["compared"] + total["uncompared"] + total["unexamined"] == total["registered"], total


@pytest.mark.parametrize("damage", ["none", "file-missing", "digest-stale", "bytes-differ", "shallow"])
def test_the_same_sum_holds_for_each_way_an_anchor_can_be_wrong(tmp_path: Path, damage: str) -> None:
    """The property on a tree where each outcome is forced, one at a time."""
    import hashlib
    module = _harness_module()
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=(damage == "shallow"))
    control = root / "controls" / "toy"
    anchor = control / "anchors" / "first-commit-toy-gate.sh"
    manifest = control / "control.json"
    if damage == "file-missing":
        anchor.unlink()
    elif damage == "digest-stale":
        anchor.write_text(anchor.read_text() + "# changed\n")
    elif damage == "bytes-differ":
        anchor.write_text(anchor.read_text() + "# changed\n")
        spec = json.loads(manifest.read_text())
        spec["anchors"][0]["sha256"] = hashlib.sha256(anchor.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(spec))
    res = module.Result(gate="x", control_dir=str(control), verdict="PASS")
    module._verify_historical_anchors(res, control, root)
    got = (res.historical_registered, res.historical_compared, res.historical_uncompared,
           res.historical_unexamined, res.provenance)
    expected = {
        "none": (1, 1, 0, 0, "unverified"),          # equal: the pass strengthens only towards failure
        "file-missing": (1, 0, 1, 0, "UNCOMPARED"),
        "digest-stale": (1, 0, 0, 1, "MISMATCH"),
        "bytes-differ": (1, 1, 0, 0, "MISMATCH"),
        "shallow": (1, 0, 1, 0, "UNCOMPARED"),
    }[damage]
    assert got == expected


# --- third review pass: the population is the declaration --------------------

def _mutate(root: Path, change) -> None:
    manifest = root / "controls" / "toy" / "control.json"
    spec = json.loads(manifest.read_text())
    change(spec)
    manifest.write_text(json.dumps(spec))


MALFORMED = {
    "placeholder-sha": lambda spec: spec["anchors"][0].update(sha="0000000"),
    "sha-not-hex": lambda spec: spec["anchors"][0].update(sha="not-a-commit"),
    "no-sha": lambda spec: spec["anchors"][0].pop("sha"),
    "no-origin": lambda spec: spec["anchors"][0].pop("origin"),
    "no-path": lambda spec: spec["anchors"][0].pop("path"),
    "anchors-is-an-object": lambda spec: spec.update(anchors={"0": spec["anchors"][0]}),
    "kind-capitalised": lambda spec: spec["anchors"][0].update(kind="Historical"),
    "kind-missing": lambda spec: spec["anchors"][0].pop("kind"),
    "entry-is-a-string": lambda spec: spec.update(anchors=["anchors/first-commit-toy-gate.sh"]),
    "entry-is-null": lambda spec: spec.update(anchors=[None]),
}

#: Shapes where the entry cannot even be counted as historical: the control is
#: could-not-look as a whole, and the count line has no anchor to count.
UNCOUNTABLE = {"anchors-is-an-object", "kind-capitalised", "kind-missing", "entry-is-a-string",
               "entry-is-null"}


@pytest.mark.parametrize("shape", sorted(MALFORMED))
def test_a_declared_historical_anchor_cannot_leave_the_population(tmp_path: Path, shape: str) -> None:
    """Each of these was a way out: a registration that says `historical`,
    that an earlier cut of the pass decided did not count, on a control excused
    because its tool is absent. Exit 0, 'no historical anchor is registered'.
    Whatever a historical declaration lacks, it is counted and it fails strict."""
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    _make_unavailable(root)
    _mutate(root, MALFORMED[shape])
    _commit(root)
    done = harness(root, "--strict", "--allow-unavailable", "--verify-provenance")
    assert done.returncode == 1, f"{shape}: {done.stdout[-600:]}"
    assert "PROVENANCE:UNCOMPARED" in done.stdout, done.stdout[-600:]
    if shape not in UNCOUNTABLE:
        assert "no historical anchor is registered" not in done.stdout
        assert counts(done.stdout) == (0, 1), done.stdout[-400:]


def test_a_control_with_only_constructed_anchors_is_as_green_as_before(tmp_path: Path) -> None:
    """A declared other kind is a declaration too: skipped, and not a failure."""
    root = _fixture(tmp_path, "good-constructed-anchor-names-no-commit", shallow=False)
    _make_unavailable(root)
    _commit(root)
    done = harness(root, "--strict", "--allow-unavailable", "--verify-provenance")
    assert done.returncode == 0, done.stdout[-600:]
    assert "UNCOMPARED" not in done.stdout


@pytest.mark.parametrize("damage", ["not-json", "missing"])
def test_an_unreadable_manifest_under_the_flag_is_not_green(tmp_path: Path, damage: str) -> None:
    """The one return the comparison pass makes without a verdict of its own.
    It is safe only because scoring has already refused the control, with a
    verdict nothing excuses - shown here, not asserted in a comment."""
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    _make_unavailable(root)
    manifest = root / "controls" / "toy" / "control.json"
    if damage == "not-json":
        manifest.write_text("{ this is not json")
    else:
        manifest.unlink()
    _commit(root)
    done = harness(root, "--strict", "--allow-unavailable", "--verify-provenance")
    assert done.returncode == 1, done.stdout[-600:]
    assert "NEGATIVE_CONTROL_VERDICT: UNRESOLVED" in done.stdout, done.stdout[-600:]


def test_every_anchor_entry_in_this_repository_is_an_object_with_a_known_kind() -> None:
    """The unfiltered enumeration: nothing in the real tree is of a shape the
    comparison pass would have to call could-not-look."""
    module = _harness_module()
    seen = 0
    for manifest in sorted((ROOT / "controls").glob("*/control.json")):
        anchors = json.loads(manifest.read_text()).get("anchors", [])
        assert isinstance(anchors, list), manifest
        for position, anchor in enumerate(anchors):
            assert isinstance(anchor, dict), f"{manifest}: anchors[{position}]"
            assert anchor.get("kind") in module.ANCHOR_KINDS, f"{manifest}: anchors[{position}]"
            seen += 1
    assert seen > 100, f"only {seen} anchor entries found"


def test_without_the_flag_those_shapes_behave_as_they_did(tmp_path: Path) -> None:
    """The change is confined to --verify-provenance: an excused control with
    a placeholder sha is as green as before when the flag is not passed."""
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    _make_unavailable(root)
    _mutate(root, MALFORMED["placeholder-sha"])
    _commit(root)
    assert harness(root, "--strict", "--allow-unavailable").returncode == 0


def _compile_time_names(text: str) -> set[str]:
    """Every braced variable in a pipeline file. Woodpecker substitutes that
    form when it compiles the pipeline, before any shell runs; the unbraced
    form and the doubled-dollar form are left for the shell."""
    import re

    return set(re.findall(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)", text))


def test_the_pipeline_braces_only_variables_woodpecker_itself_supplies() -> None:
    """Pipeline 3754 printed "provenance flag: not passed" on the run that
    passed it: a braced default on the script's own variable was substituted
    at compile time, where that variable is always unset. Under bash the line
    was right, so no test that runs the block in a shell could see it."""
    names = _compile_time_names((ROOT / ".woodpecker.yml").read_text())
    assert names, "the reader found no braced variable at all - it cannot see the form it exists to catch"
    own = sorted(name for name in names if not name.startswith("CI_"))
    assert not own, f"substituted when the pipeline is compiled, not when the step runs: {own}"


def test_the_reader_sees_a_braced_shell_variable_and_ignores_the_escaped_form() -> None:
    line = 'echo "${PROVENANCE:-none} ${CI_PIPELINE_EVENT} $PLAIN $${ESCAPED}"'
    assert _compile_time_names(line) == {"PROVENANCE", "CI_PIPELINE_EVENT"}


# --- main-retention contract (issue #1797) -----------------------------------

@pytest.mark.parametrize("state", ["main", "missing-main", "side-branch"])
def test_no_flag_stdout_and_exit_match_the_frozen_main_baseline(tmp_path: Path, state: str) -> None:
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    if state == "missing-main":
        subprocess.run(["git", "-C", str(root), "checkout", "--detach", "-q"], check=True)
        subprocess.run(["git", "-C", str(root), "branch", "-D", "main"], check=True, capture_output=True)
    elif state == "side-branch":
        # Repoint the recorded SHA to a genuine sibling commit with matching bytes.
        subprocess.run(["git", "-C", str(root), "checkout", "-qb", "side", "HEAD~1"], check=True)
        (root / "side-only").write_text("side branch commit\n")
        _commit(root)
        side = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        subprocess.run(["git", "-C", str(root), "checkout", "-q", "main"], check=True)
        assert subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", side, "main"],
                              capture_output=True, check=False).returncode == 1
        _mutate(root, lambda spec: spec["anchors"][0].update(sha=side))
        _commit(root)
    done = harness(root, "--strict")
    normalized = re.sub(r"(?m)(^NEGATIVE_CONTROL_SOURCE: worktree-at-)[0-9a-f]+", r"\1<COMMIT>", done.stdout)
    normalized = re.sub(r"(?<=historical )[0-9a-f]{40}", "<COMMIT>", normalized)
    assert done.returncode == 0 and done.stderr == ""
    assert normalized == (CONTROL / "no-flag-baseline.stdout").read_text()


def test_the_real_old_1a13_record_is_off_main_even_when_its_object_is_absent(tmp_path: Path) -> None:
    import hashlib
    module = _harness_module()
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    sha = "1a13bc6e184aebfaa1a3ddb8d492f2b6a80d78ce"
    assert subprocess.run(["git", "-C", str(root), "cat-file", "-e", sha],
                          capture_output=True, check=False).returncode != 0
    anchor_path = CONTROL / "anchors/off-main-1a13-branch-protection.sh"
    digest = "074a28aa67e2ec15d46a9b6c031e480ac3363d20649416f16a71801c3f79c820"
    assert hashlib.sha256(anchor_path.read_bytes()).hexdigest() == digest
    anchor = {"kind": "historical", "sha": sha, "origin": "scripts/branch-protection.sh", "sha256": digest}
    assert module._provenance(anchor, anchor_path, root, False) == "unverified"
    assert module._provenance(anchor, anchor_path, root, True) == "OFF_MAIN"
    assert "refs/heads/main" in module._HISTORICAL_RETENTION[id(anchor)][1]
    assert not module._HISTORICAL_COMPARED.get(id(anchor), False)


def test_a_non_main_remote_default_is_unknown_even_with_a_main_ref(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)
    for ref in ("refs/remotes/origin/main", "refs/remotes/origin/trunk"):
        subprocess.run(["git", "-C", str(root), "update-ref", ref, "HEAD"], check=True)
    subprocess.run(["git", "-C", str(root), "symbolic-ref", "refs/remotes/origin/HEAD",
                    "refs/remotes/origin/trunk"], check=True)
    done = harness(root, "--strict", "--verify-provenance")
    assert done.returncode == 1 and "default branch is not main" in done.stdout
    assert "on_main=0 off_main=0 unknown=1" in done.stdout


def test_a_shallow_clone_with_visible_anchor_still_cannot_prove_main_history(tmp_path: Path) -> None:
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=True)
    # Current HEAD's toy gate bytes differ, so use another committed path whose
    # bytes are the vendored anchor and name this visible commit instead.
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    _mutate(root, lambda spec: spec["anchors"][0].update(
        sha=sha, origin="controls/toy/anchors/first-commit-toy-gate.sh"))
    done = harness(root, "--strict", "--verify-provenance")
    assert done.returncode == 1 and counts(done.stdout) == (1, 0)
    assert "main ancestry is unknown in a shallow clone" in done.stdout
    assert "on_main=0 off_main=0 unknown=1" in done.stdout


def test_successful_ci_main_fetch_does_not_excuse_off_main_provenance(tmp_path: Path) -> None:
    done, flag, log = _run_ci_block(tmp_path, "pull_request", shallow="false")
    assert done.returncode == 0 and flag == "--verify-provenance"
    assert "refs/heads/main:refs/remotes/origin/main" in log
    # The emitted flag is passed to the actual harness over the known-bad tree.
    refused = run_case("bad-anchor-off-main", provenance_flag=flag)
    assert refused.returncode == 1 and "PROVENANCE:OFF_MAIN" in refused.stdout


@pytest.mark.parametrize("off_main", [False, True])
def test_ci_real_git_supplies_main_to_a_shallow_detached_restricted_checkout(tmp_path: Path, off_main: bool) -> None:
    import os
    source = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=False)

    def git(repo: Path, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    git(source, "checkout", "-qb", "pr")
    (source / "pr-only").write_text("pull request commit\n")
    if off_main:
        # This real PR commit has matching anchor bytes but is not in main.
        _commit(source)
        side = git(source, "rev-parse", "HEAD")
        _mutate(source, lambda spec: spec["anchors"][0].update(
            sha=side, origin="controls/toy/anchors/first-commit-toy-gate.sh"))
    _commit(source)
    if off_main:
        assert subprocess.run(["git", "-C", str(source), "merge-base", "--is-ancestor", side, "main"],
                              capture_output=True, check=False).returncode == 1
    git(source, "checkout", "-q", "main")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(source), str(origin)], check=True)
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--single-branch", "--branch", "pr",
                    f"file://{origin}", str(checkout)], check=True)
    git(checkout, "checkout", "-q", "--detach")
    assert git(checkout, "rev-parse", "--is-shallow-repository") == "true"
    assert git(checkout, "config", "--get", "remote.origin.fetch") == "+refs/heads/pr:refs/remotes/origin/pr"
    assert subprocess.run(["git", "-C", str(checkout), "show-ref", "--verify", "--quiet",
                           "refs/remotes/origin/main"], check=False).returncode == 1
    assert harness(checkout, "--strict", "--verify-provenance").returncode == 1
    (checkout / ".ci-bin").mkdir()
    script, _command = _ci_step_script()
    env = os.environ.copy()
    env["CI_PIPELINE_EVENT"] = "pull_request"
    done = subprocess.run(["sh", "-c", script], cwd=checkout, env=env,
                          capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    assert git(checkout, "rev-parse", "--is-shallow-repository") == "false"
    assert git(checkout, "rev-parse", "origin/main") == git(source, "rev-parse", "main")
    assert git(checkout, "config", "--get", "remote.origin.fetch") == "+refs/heads/pr:refs/remotes/origin/pr"
    flag = (checkout / ".ci-bin/provenance-flag").read_text()
    assert flag == "--verify-provenance"
    checked = harness(checkout, "--strict", flag)
    assert counts(checked.stdout) == (1, 0), checked.stdout
    if off_main:
        assert checked.returncode == 1 and "PROVENANCE:OFF_MAIN" in checked.stdout
    else:
        assert checked.returncode == 0 and "on_main=1 off_main=0 unknown=0" in checked.stdout


@pytest.mark.parametrize("state", ["unknown", "off-main"])
def test_non_strict_provenance_failure_is_advisory_but_never_a_clean_summary(tmp_path: Path, state: str) -> None:
    root = _fixture(tmp_path, "good-anchor-matches-its-commit", shallow=(state == "unknown"))
    if state == "off-main":
        _mutate(root, lambda spec: spec["anchors"][0].update(sha="1a13bc6e184aebfaa1a3ddb8d492f2b6a80d78ce"))
    advisory = harness(root, "--verify-provenance")
    strict = harness(root, "--strict", "--verify-provenance")
    assert advisory.returncode == 0 and strict.returncode == 1
    for done in (advisory, strict):
        word = "UNCOMPARED" if state == "unknown" else "OFF_MAIN"
        assert f"-> PROVENANCE:{word}" in done.stdout
        assert "negative-controls: ok" not in done.stdout


def test_main_history_is_cached_by_root_and_tip_and_unknown_is_not_cached(tmp_path: Path, monkeypatch) -> None:
    module = _harness_module()
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    one = _fixture(tmp_path / "one", "good-anchor-matches-its-commit", shallow=False)
    two = _fixture(tmp_path / "two", "good-anchor-matches-its-commit", shallow=False)
    anchor = json.loads((one / "controls/toy/control.json").read_text())["anchors"][0]
    real_run = subprocess.run
    enumerated = []
    fail_once = True

    def recording_run(argv, *args, **kwargs):
        nonlocal fail_once
        if "rev-list" in argv:
            enumerated.append(tuple(argv))
            if fail_once:
                fail_once = False
                return subprocess.CompletedProcess(argv, 1, "", "injected unreadable history")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", recording_run)
    assert module._main_ancestry(anchor, one)[0] == "UNCOMPARED"
    assert not module._MAIN_ANCESTORS, "a failed enumeration cannot populate the cache"
    assert module._main_ancestry(anchor, one)[0] == "ok"
    assert module._main_ancestry(anchor, one)[0] == "ok"
    assert len(enumerated) == 2, "one failure then one successful enumeration"
    anchor_two = json.loads((two / "controls/toy/control.json").read_text())["anchors"][0]
    assert module._main_ancestry(anchor_two, two)[0] == "ok"
    assert len(enumerated) == 3, "another root has an independent history"
    (one / "new-main-tip").write_text("tip changed\n")
    _commit(one)
    assert module._main_ancestry(anchor, one)[0] == "ok"
    assert len(enumerated) == 4, "a new main tip must not reuse old ancestry"
