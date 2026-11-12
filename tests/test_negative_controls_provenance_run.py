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


def run_case(name: str, harness: Path = HARNESS) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", str(RUNNER), str(CONTROL / "cases" / name), str(harness)],
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


@pytest.mark.parametrize("case", ["bad-anchor-differs-from-its-commit", "bad-commit-not-in-this-clone"])
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
    assert "1 never reached the comparison" in done.stdout


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
    done = subprocess.run([sys.executable, str(HARNESS), "--root", str(root), "--strict",
                           "--verify-provenance"], capture_output=True, text=True, timeout=300,
                          check=False, env={"PATH": str(nogit)})
    assert "NEGATIVE_CONTROL_PROVENANCE: UNCOMPARED" in done.stdout, done.stdout + done.stderr
    assert "git is not on PATH" in done.stdout


# --- the real tree, and who passes the flag ----------------------------------

def _registered_historical_anchors() -> list[tuple[Path, dict]]:
    """Derived from the registrations, never typed: every `kind: historical`
    anchor of a top-level control that names a real commit."""
    found = []
    for manifest in sorted((ROOT / "controls").glob("*/control.json")):
        for anchor in json.loads(manifest.read_text()).get("anchors", []):
            if (anchor.get("kind") == "historical" and anchor.get("origin")
                    and anchor.get("sha") not in (None, "", "0000000", "n/a")):
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


def _run_ci_block(tmp_path: Path, event: str | None, *, shallow: str, fetch_rc: int = 0):
    """Run the CI step's own shell block against a stub git."""
    script, _command = _ci_step_script()
    work = tmp_path / "ws"
    (work / ".ci-bin").mkdir(parents=True)
    git = work / ".ci-bin" / "git"
    git.write_text(f"""#!/bin/sh
echo "$*" >> "{work}/git.log"
case "$*" in
  *is-shallow-repository*) echo {shallow} ;;
  *fetch*) exit {fetch_rc} ;;
esac
""")
    git.chmod(0o755)
    sleeper = work / ".ci-bin" / "sleep"
    sleeper.write_text("#!/bin/sh\nexit 0\n")
    sleeper.chmod(0o755)
    env = {"PATH": f"{work / '.ci-bin'}:/usr/bin:/bin"}
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


def test_on_a_pull_request_an_already_deepened_clone_is_not_fetched_again(tmp_path: Path) -> None:
    """The enrolment step shares the workspace and may have deepened it first;
    `--unshallow` on a complete clone is an error, so it must not be tried."""
    done, flag, log = _run_ci_block(tmp_path, "pull_request", shallow="false")
    assert done.returncode == 0 and flag == "--verify-provenance"
    assert "fetch" not in log


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
