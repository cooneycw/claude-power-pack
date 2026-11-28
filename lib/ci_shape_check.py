"""Real checkout shapes and bounded, tier-specific completion evidence (#1917).

Local GOOD covers the declared local population. It never closes the root lane.
No uid emulation, host config copying, or fallback from an image to local tools.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SELECTORS = (
    "tests/test_codex_skill_sync.py::test_real_repo_skills_in_sync",
    "tests/test_codex_skill_sync.py::test_real_repo_bundled_scripts_byte_identical",
    "tests/test_codex_skill_sync.py::test_real_repo_bundled_libraries_byte_identical",
    "tests/test_codex_skill_sync.py::test_generation_is_deterministic",
    "tests/test_codex_skill_sync.py::test_current_generator_only_removes_the_six_retired_cpp_exception_rows",
    "tests/test_codex_skill_sync.py::test_data_only_generator_guard_rejects_other_bytes",
    "tests/test_antigravity_codex_parity.py::test_canonical_source_ignores_a_probe_removed_after_directory_listing",
    "tests/test_antigravity_codex_parity.py::test_two_generators_use_independent_parsers_and_identical_inputs",
    "tests/test_antigravity_codex_parity.py::test_changed_output_mode_is_detected",
    "tests/test_antigravity_skill_sync.py",
    "tests/test_antigravity_skill_cli.py",
    "tests/test_pi_skill_sync.py",
    "tests/test_pi_skill_install.py",
    "tests/test_pi_host_fixture.py",
    "tests/test_pi_syscall_audit.py",
    "tests/test_pi_owner_probe.py",
    "tests/test_pi_owner_recovery.py",
    "tests/test_host_update_ci_shape.py::test_actual_entry_source_shapes[full-0]",
    "tests/test_host_update_ci_shape.py::test_actual_entry_source_shapes[worktree-0]",
    "tests/test_host_update_ci_shape.py::test_actual_entry_source_shapes[shallow-0]",
    "tests/test_host_update_ci_shape.py::test_control_declared_runtime_works_without_global_yaml",
    "tests/test_host_update_ci_shape.py::test_pinned_reader_rejects_bad_current_writer",
    "tests/test_host_update_ci_shape.py::test_moved_source_is_unknown_and_preserves_installation",
    "tests/test_host_update_command.py::test_real_historical_installer_population",
    "tests/test_ci_shape_check.py",
    "tests/test_ci_shape_cancel.py",
    "tests/test_ci_shape_review_entry.py",
    "tests/test_ci_shape_ci_entry.py",
    "tests/test_host_update_source_gc.py",
    "tests/test_ci_shape_history_skips.py",
)
LANES = ("depth-1", "depth-1-tree-0")
COLLECTION_FLOOR = 200
ROOT_RECEIPT = "docs/measurements/ci-shape-check/root-receipt.json"
BOOTSTRAP_PATHS = frozenset({
    "controls/ci-shape-check/validate-profile.json", ROOT_RECEIPT,
    "docs/measurements/ci-shape-check.md", "docs/scripts/ci-shape-check.md",
    "docs/measurements/ci-shape-check/validate-default-shell.txt",
    "docs/measurements/ci-shape-check/validate-image.txt",
})
_WITNESS_MODULE = "tests/test_ci_shape_check.py::"
REQUIRED_WITNESSES = {
    "1958-source-gc": "tests/test_host_update_source_gc.py::test_source_publication_joins_automatic_gc",
    "1961-cancel": ("tests/test_ci_shape_cancel.py::"
                    "test_cancel_reaps_pytest_group_before_outer_completion[15-term-ignoring-grandchild]"),
    "1909-modes": _WITNESS_MODULE + "test_1909_historical_inventory_retains_umask_checkout_modes",
    "1910-root": _WITNESS_MODULE + "test_1910_chmod_zero_is_readable_to_real_root_then_real_child_refuses",
    "1910-path": _WITNESS_MODULE + "test_1910_exact_old_path_fixture_then_fixed_staged_tool_fixture",
    "1916-history": _WITNESS_MODULE + "test_1916_actual_source_fixture_fails_without_pin_then_owned_history_passes",
    "1916-path": _WITNESS_MODULE + "test_1916_unchanged_owner_helper_loses_staged_tools",
    "1922-4056": _WITNESS_MODULE + "test_1922_real_filtered_commit_presence_does_not_prove_file_contents",
    "1922-4058": _WITNESS_MODULE + "test_1922_ci_true_rewritten_assertion_is_bounded_after_fix",
    "1923": _WITNESS_MODULE + "test_physical_canary_and_real_collector[internalerror]",
    "1923-zero-executed": _WITNESS_MODULE + "test_physical_canary_and_real_collector[zero-executed]",
    "host-source-owner": _WITNESS_MODULE + "test_donor_fetch_trusts_only_its_selected_different_owner_source",
    "1927": (
        "tests/test_pi_skill_install.py::test_unreadable_control_unknown_is_the_actual_ledger_permission_failure"
        "[umask022-symlink]"),
    "1927-direct022": (
        "tests/test_pi_skill_install.py::test_unreadable_control_unknown_is_the_actual_ledger_permission_failure"
        "[umask022-direct]"),
    "1927-direct000": (
        "tests/test_pi_skill_install.py::test_unreadable_control_unknown_is_the_actual_ledger_permission_failure"
        "[umask000-direct]"),
    "1927-symlink000": (
        "tests/test_pi_skill_install.py::test_unreadable_control_unknown_is_the_actual_ledger_permission_failure"
        "[umask000-symlink]"),
}
ROOT_ONLY_NODES = frozenset({
    "tests/test_pi_skill_install.py::test_root_unreadable_control_executes_real_cli_as_unprivileged_child",
    REQUIRED_WITNESSES["1910-root"], REQUIRED_WITNESSES["1910-path"], REQUIRED_WITNESSES["1916-path"],
})
# Historical compatibility name; these nodes are required omissions, not
# optional execution, in the shape-only collector and completion contract.
OPTIONAL_HISTORY_NODES = frozenset(
    "tests/test_host_update_command.py::test_real_historical_installer_population[" + name + "]"
    for name in ("real-pre-e32-install", "real-v13-install")
)
EXPECTED_HISTORY_SKIPS = {
    node: ("CI-shape expected history skip: historical installer execution is outside "
           "the shallow/filtered lane; use separate full-history validation")
    for node in OPTIONAL_HISTORY_NODES
}
HISTORICAL_PIN = "40d25173c8c09987fac851cffa565efdc0f11c72"
# A small runtime surface. In particular Git/Make are ONLY in the staged dir.
SYSTEM_TOOLS = (
    "sh", "bash", "env", "chmod", "cp", "mkdir", "mv", "rm", "ln", "cat",
    "sed", "grep", "dirname", "basename", "readlink", "realpath", "timeout",
    "sleep", "touch", "stat", "wc", "head", "tail", "find", "sort", "tr",
    "cut", "xargs", "printf", "tee", "date", "true", "false", "install", "id",
    "uname", "du", "diff", "which", "tar", "gzip", "awk", "ps", "kill", "uv", "mktemp",
)
PRECONDITIONS = (
    "shallow", "one_head_commit", "historical_pin_absent", "source_modes",
    "symlink_tmp", "private_home", "external_cwd", "ci_true", "staged_git",
    "staged_make", "partial_witness", "identity",
)


class Unknown(RuntimeError):
    """The requested population could not be examined."""


def command(argv, *, cwd=None, env=None, input=None, check=True):
    return subprocess.run(list(map(str, argv)), cwd=cwd, env=env, input=input,
                          capture_output=True, text=True, check=check, timeout=180)


def image_pin(root: Path) -> str:
    text = (root / ".woodpecker.yml").read_text()
    found = re.search(r"^  validate:\n    image: (\S+@sha256:[0-9a-f]{64})$", text, re.M)
    if not found:
        raise Unknown("validate image is not content pinned")
    return found[1]


def ci_entry_image(root: Path) -> str:
    """Check the CI declaration and actual identity; this is not image attestation."""
    if os.environ.get("CI") != "woodpecker":
        raise Unknown("CI entry requires Woodpecker context (CI=woodpecker)")
    if not re.fullmatch(r"[1-9][0-9]*", os.environ.get("CI_PIPELINE_NUMBER", "")):
        raise Unknown("CI entry requires a positive Woodpecker pipeline number")
    declared_commit = os.environ.get("CI_COMMIT_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", declared_commit):
        raise Unknown("CI entry requires an exact Woodpecker commit SHA")
    if command(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip() != declared_commit:
        raise Unknown("Woodpecker commit SHA does not match the checkout HEAD")
    if os.getuid() != 0 or os.geteuid() != 0:
        raise Unknown("CI entry requires actual uid/euid 0")
    image = image_pin(root)
    declared = re.search(r"^  ci-shape:\n    image: (\S+@sha256:[0-9a-f]{64})$",
                         (root / ".woodpecker.yml").read_text(), re.M)
    if not declared or declared[1] != image:
        raise Unknown("ci-shape step must declare the exact pinned validate image")
    return image


def selector_matches(nodeid: str, selector: str) -> bool:
    return (nodeid == selector or nodeid.startswith(selector + "::")
            or nodeid.startswith(selector + "["))


def manifest_complete(selectors: tuple[str, ...]) -> bool:
    return all(any(selector_matches(witness, selector) for selector in selectors)
               for witness in (*REQUIRED_WITNESSES.values(), *EXPECTED_HISTORY_SKIPS))


def ci_profile(root: Path) -> dict:
    try:
        profile = json.loads((root / "controls/ci-shape-check/validate-profile.json").read_text())
    except (OSError, ValueError) as exc:
        raise Unknown("pytest-time umask UNKNOWN: validate profile unavailable") from exc
    if (not isinstance(profile, dict) or profile.get("state") != "GOOD" or profile.get("image") != image_pin(root)
            or type(profile.get("umask")) is not int or not 0 <= profile["umask"] <= 0o777
            or not profile.get("evidence")):
        raise Unknown("pytest-time umask UNKNOWN: pinned validate default has not been proven")
    try:
        raw = (root / ROOT_RECEIPT).read_bytes()
        observed = json.loads(raw)
        # This is a historical IMAGE PROFILE, not a requirement that future
        # selector manifests equal the original run's population. The immutable
        # receipt digest binds that run; its identity/mask observation persists
        # only while the validate image digest stays unchanged.
        valid = (hashlib.sha256(raw).hexdigest() == profile["receipt_sha256"]
                 and observed["commit"] == profile["root_checkpoint"]
                 and observed["state"] == "GOOD" and observed["tier"] == "image"
                 and observed["root"]["state"] == "GOOD" and observed["image"] == profile["image"]
                 and observed["pytest_time_umask"]["state"] == "GOOD"
                 and observed["pytest_time_umask"]["image"] == profile["image"]
                 and observed["pytest_time_umask"]["umask"] == profile["umask"]
                 and len(observed["lanes"]) == 2
                 and profile["identity"]["uid"] == profile["identity"]["euid"] == 0
                 and all(lane["identity"] == profile["identity"] and lane["state"] == "GOOD"
                         for lane in observed["lanes"]))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise Unknown("validate profile root receipt unavailable or malformed") from exc
    if not valid:
        raise Unknown("validate profile does not match the committed root receipt")
    return profile


def bootstrap_changes(root: Path, base: str, head: str = "HEAD") -> tuple[str, str]:
    """One-time PR-A carry qualification, not a restriction on future changes."""
    git = shutil.which("git")
    if not git:
        return "UNKNOWN", "Git unavailable for bootstrap carry"
    ancestor = command([git, "-C", root, "merge-base", "--is-ancestor", base, head], check=False)
    if ancestor.returncode:
        return "UNKNOWN", "root checkpoint is not a proven ancestor"
    changed = command([git, "-C", root, "diff", "--name-only", "--no-renames", "-z", base, head]).stdout
    forbidden = set(changed.rstrip("\0").split("\0")) - {""} - BOOTSTRAP_PATHS
    if forbidden:
        return "BAD", "post-root change outside named data/docs paths: " + ", ".join(sorted(forbidden))
    return "GOOD", "root ancestor to HEAD changes only named profile/docs/measurement paths"


def completion(result: dict, returncode: int, log: str, tier: str) -> tuple[str, str]:
    """A zero exit is necessary, never sufficient (#1923)."""
    try:
        selected, outcomes, skips = result["selected"], result["outcomes"], result["skips"]
        if "INTERNALERROR" in log:
            return "BAD", "pytest output contains INTERNALERROR"
        if not any(value in {"passed", "failed"} for value in outcomes.values()):
            return "BAD", "zero executed tests"
        if len(selected) < COLLECTION_FLOOR:
            return "BAD", "collection below committed population floor"
        if not set(REQUIRED_WITNESSES.values()) <= set(selected):
            return "BAD", "required named acceptance witness missing from collection"
        for node, expected_reason in EXPECTED_HISTORY_SKIPS.items():
            if (node not in selected or outcomes.get(node) != "skipped"
                    or expected_reason not in skips.get(node, "")):
                return "BAD", "expected historical skip missing, executed or reason changed: " + node
        if (returncode or result["exit"] or result["errors"] or "INTERNALERROR" in log
                or not selected or len(selected) != len(set(selected))
                or set(selected) != set(outcomes) or set(skips) != {
                    key for key, value in outcomes.items() if value == "skipped"}):
            return "BAD", "failed, interrupted, empty or incomplete pytest results"
        if any(value not in {"passed", "skipped"} for value in outcomes.values()):
            return "BAD", "pytest failures or invalid terminal outcomes"
        # A non-root run may skip only tests explicitly requiring real uid 0.
        for nodeid, reason in skips.items():
            root_skip = tier == "local" and nodeid in ROOT_ONLY_NODES and "requires real root" in reason
            history_skip = (nodeid in EXPECTED_HISTORY_SKIPS
                            and EXPECTED_HISTORY_SKIPS[nodeid] in reason)
            if not root_skip and not history_skip:
                return "BAD", "unexpected skip: " + reason[:200]
        for selector in SELECTORS:
            population = [key for key in outcomes if selector_matches(key, selector)]
            unavailable_history = (
                selector == "tests/test_host_update_command.py::test_real_historical_installer_population"
                and population and all(key in skips for key in population))
            if not unavailable_history and not any(outcomes[key] == "passed" for key in population):
                return "BAD", "no executed passing tests for " + selector
    except (KeyError, TypeError, ValueError, AttributeError):
        return "BAD", "malformed pytest completion evidence"
    return "GOOD", "all declared selectors completed; skips named"


def assess(receipt: dict, *, tier: str, commit: str, image: str) -> tuple[str, str]:
    """The same public verifier is used by controls and downstream readers."""
    try:
        if (receipt["schema"] != 1 or receipt["tier"] != tier
                or receipt["commit"] != commit or receipt["image"] != image
                or receipt["selectors"] != list(SELECTORS)):
            return "BAD", "receipt identity, tier or selection mismatch"
        if not manifest_complete(SELECTORS):
            return "BAD", "manifest dropped a required named witness"
        if receipt.get("state") == "UNKNOWN" and not receipt["lanes"]:
            return "UNKNOWN", receipt["reason"]
        profile = receipt["pytest_time_umask"]
        if profile["state"] == "UNKNOWN":
            return "UNKNOWN", "pytest-time umask UNKNOWN: CI default not proven"
        if (profile["state"] != "GOOD" or profile["image"] != image
                or type(profile["umask"]) is not int or not 0 <= profile["umask"] <= 0o777
                or not profile["evidence"]):
            return "BAD", "invalid pytest-time umask evidence"
        root = receipt["root"]
        if tier == "local":
            if root != {"state": "UNKNOWN", "reason": "not examined: needs real uid 0"}:
                return "BAD", "local GOOD cannot claim root GOOD"
        elif tier != "image":
            return "BAD", "invalid tier"
        lanes = receipt["lanes"]
        if [row["name"] for row in lanes] != list(LANES):
            return "BAD", "missing or duplicated clone lane"
        for lane in lanes:
            if lane["state"] == "UNKNOWN":
                return "UNKNOWN", lane["reason"]
            if lane["state"] != "GOOD":
                return "BAD", lane["reason"]
            if lane.get("expected_skips") != EXPECTED_HISTORY_SKIPS:
                return "BAD", "lane does not declare its expected historical skips"
            if set(lane["preconditions"]) != set(PRECONDITIONS) or not all(
                    value is True for value in lane["preconditions"].values()):
                return "BAD", "shape precondition not established"
            if lane["test_umask"] != f"{profile['umask']:03o}":
                return "BAD", "pytest umask differs from the observed CI profile"
            uid, euid = lane["identity"]["uid"], lane["identity"]["euid"]
            if ((tier == "image" and (uid != 0 or euid != 0))
                    or (tier == "local" and (uid == 0 or euid == 0))):
                return "BAD", "wrong real uid for requested tier"
            state, reason = completion(lane["results"], lane["exit"], lane["diagnostic"], tier)
            if state != "GOOD":
                return state, reason
            outcomes = lane["results"]["outcomes"]
            if lane["counts"] != {
                    "selected": len(lane["results"]["selected"]),
                    "executed": sum(value != "skipped" for value in outcomes.values()),
                    "skipped": len(lane["results"]["skips"])}:
                return "BAD", "inconsistent selected/executed/skipped counts"
    except (KeyError, TypeError, ValueError, AttributeError):
        return "BAD", "missing or malformed receipt evidence"
    if tier == "image" and root != {"state": "GOOD", "reason": "real uid 0 in pinned validate image"}:
        return "BAD", "image/root evidence missing"
    return "GOOD", "both clone lanes completed for the declared tier only"


def fresh_environment(home: Path, tmp: Path, path: str) -> dict[str, str]:
    # Do not inherit Git, pytest, loader, Make, credential or HOME overrides.
    return {"HOME": str(home), "TMPDIR": str(tmp), "PATH": path, "CI": "true",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONNOUSERSITE": "1",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0", "UV_NO_PROGRESS": "1"}


def minimal_path(work: Path, stage: Path, python: Path) -> str:
    target = work / "system-bin"
    target.mkdir()
    for name in SYSTEM_TOOLS:
        source = shutil.which(name)
        if source:
            (target / name).symlink_to(source)
    for name in ("python", "python3"):
        (target / name).symlink_to(python)
    return os.pathsep.join((str(stage), str(target)))


def donor(root: Path, work: Path, git: str, commit: str, env: dict) -> tuple[Path, str]:
    """A private upload-pack server; never configure or mutate the author's repo."""
    path = work / "donor.git"
    command([git, "init", "--bare", "-q", path], env=env)
    command([git, "-C", path, "config", "uploadpack.allowFilter", "true"], env=env)
    source_gitdir = command([git, "-c", f"safe.directory={root}", "-C", root,
                             "rev-parse", "--absolute-git-dir"], env=env).stdout.strip()
    # File transport opens the source as its Git directory, unlike `git -C
    # ROOT`. Trust only these two spellings in THIS upload-pack process. The
    # read-only host mount may have a different uid from the image's root.
    upload_pack = shlex.join([git, "-c", f"safe.directory={root}",
                             "-c", f"safe.directory={source_gitdir}", "upload-pack"])
    command([git, "-C", path, "fetch", "--depth=1", "--upload-pack=" + upload_pack,
             root.as_uri(), commit], env=env)
    command([git, "-C", path, "update-ref", "refs/heads/checkpoint", "FETCH_HEAD"], env=env)
    # An unreferenced historical file with a present commit but absent tree/blob
    # distinguishes actual filtering from a remote that merely advertises it.
    blob = command([git, "-C", path, "hash-object", "-w", "--stdin"],
                   input="ci-shape historical blob witness\n", env=env).stdout.strip()
    tree = command([git, "-C", path, "mktree"], env=env,
                   input=f"100644 blob {blob}\told-only.txt\n").stdout.strip()
    author = {**env, "GIT_AUTHOR_NAME": "Shape witness", "GIT_COMMITTER_NAME": "Shape witness",
              "GIT_AUTHOR_EMAIL": "shape@example.invalid", "GIT_COMMITTER_EMAIL": "shape@example.invalid"}
    witness = command([git, "-C", path, "commit-tree", tree], input="historical witness\n",
                      env=author).stdout.strip()
    command([git, "-C", path, "update-ref", "refs/heads/witness", witness], env=env)
    return path, witness


def checkout(seed: Path, witness: str, work: Path, git: str, partial: bool, env: dict) -> Path:
    path = work / "checkout"
    options = ["--filter=tree:0"] if partial else []
    materialize = dict(env)
    materialize.pop("GIT_NO_LAZY_FETCH", None)
    command([git, "clone", "-q", "--depth=1", *options, "--branch=checkpoint",
             "--single-branch", seed.as_uri(), path], env=materialize)
    if partial:
        command([git, "-C", path, "fetch", "-q", "--depth=1", "--filter=tree:0",
                 "origin", witness], env=env)
    # Git 2.39 predates GIT_NO_LAZY_FETCH: an unreachable private origin also
    # prevents implicit fetch in older Git. HEAD's tracked files are materialized.
    command([git, "-C", path, "remote", "set-url", "origin", (work / "offline.git").as_uri()], env=env)
    return path


def observe(path: Path, work: Path, witness: str, git: str, stage: Path,
            env: dict, tier: str, partial: bool, *, historical_pin=HISTORICAL_PIN) -> tuple[dict, dict]:
    def g(*args, check=True):
        return command([git, "-C", path, *args], env=env, check=check)

    home, tmp = Path(env["HOME"]), Path(env["TMPDIR"])
    pin_absent = g("cat-file", "-e", historical_pin + "^{commit}", check=False).returncode != 0
    mode_inputs = {"CLAUDE.md": 0o666, "scripts/flow-finish-gate.sh": 0o777}
    modes = {name: (path / name).stat().st_mode & 0o777 for name in mode_inputs}
    filtered = True
    if partial:
        filtered = (g("config", "--get", "remote.origin.promisor").stdout.strip() == "true"
                    and g("config", "--get", "remote.origin.partialclonefilter").stdout.strip() == "tree:0"
                    and g("cat-file", "-e", witness + "^{commit}", check=False).returncode == 0
                    and g("cat-file", "-e", witness + ":old-only.txt", check=False).returncode != 0)
    identity = {"uid": os.getuid(), "euid": os.geteuid(), "gid": os.getgid(),
                "egid": os.getegid(), "groups": os.getgroups()}
    preconditions = dict(zip(PRECONDITIONS, (
        g("rev-parse", "--is-shallow-repository").stdout.strip() == "true",
        g("rev-list", "--count", "HEAD", check=False).stdout.strip() == "1", pin_absent,
        modes == mode_inputs, tmp.is_symlink() and tmp.resolve() == work / "tmp-real",
        home.is_dir() and home.stat().st_mode & 0o777 == 0o700,
        not work.is_relative_to(path), env["CI"] == "true",
        shutil.which("git", path=env["PATH"]) == str(stage / "git"),
        shutil.which("make", path=env["PATH"]) == str(stage / "make"), filtered,
        (identity["uid"] == 0 and identity["euid"] == 0) if tier == "image" else
        (identity["uid"] != 0 and identity["euid"] != 0),
    ), strict=True))
    return preconditions, {"identity": identity, "modes": modes,
                           "partial_witness_commit": witness if partial else None,
                           "tmp_spelling": str(tmp), "tmp_resolved": str(tmp.resolve())}



def _pytest_group_live(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    # Linux init may retain already stopped orphan zombies. They consume no
    # work and cannot be waited by this parent, unlike its direct child.
    if Path("/proc").is_dir():
        for path in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = path.read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == pgid and fields[0] not in {"Z", "X"}:
                    return True
            except (FileNotFoundError, ProcessLookupError):
                continue
        return False
    return True


def _stop_pytest_group(proc: subprocess.Popen) -> None:
    def send(signum):
        try:
            os.killpg(proc.pid, signum)
        except ProcessLookupError:
            pass
    send(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        send(signal.SIGKILL)
        proc.wait(timeout=5)
    # Its leader can exit while a TERM-ignoring descendant remains alive.
    send(signal.SIGKILL)
    deadline = time.monotonic() + 5
    while _pytest_group_live(proc.pid):
        if time.monotonic() >= deadline:
            raise Unknown("owned pytest group did not stop after SIGKILL")
        time.sleep(0.01)


def _owned_pytest(argv, *, cwd, env, output, timeout=1200) -> int:
    """Own the detached group through ordinary exit, timeout, and signals."""
    proc = None
    previous = []
    launching, stopping = True, False
    interrupted = None

    def cancel(signum, frame):
        nonlocal interrupted
        interrupted = signum
        # Do not interrupt Popen before we receive its child handle, or allow
        # repeated signals to cut group cleanup short.
        if not launching and not stopping:
            raise SystemExit(128 + signum)

    try:
        for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            previous.append((signum, signal.signal(signum, cancel)))
        if interrupted is not None:
            raise SystemExit(128 + interrupted)
        proc = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env,
                                stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        launching = False
        if interrupted is not None:
            raise SystemExit(128 + interrupted)
        return proc.wait(timeout=timeout)
    finally:
        stopping = True
        cleanup_error = None
        try:
            if proc is not None:
                _stop_pytest_group(proc)
        except BaseException as exc:
            cleanup_error = exc
            raise
        finally:
            for signum, handler in reversed(previous):
                signal.signal(signum, handler)
            if interrupted is not None:
                # A cleanup failure must remain visible without turning a
                # stop request into a returned UNKNOWN lane and more work.
                if cleanup_error is not None:
                    print(f"CI_SHAPE_CANCEL: UNKNOWN: {cleanup_error}", file=sys.stderr, flush=True)
                raise SystemExit(128 + interrupted) from cleanup_error


def run_lane(root: Path, seed: Path, witness: str, work: Path, stage: Path,
             python: Path, tier: str, partial: bool, logs: Path, test_umask: int) -> dict[str, Any]:
    work.mkdir()
    home, tmp = work / "home", work / "tmp-link"
    home.mkdir(mode=0o700)
    (work / "tmp-real").mkdir()
    tmp.symlink_to(work / "tmp-real", target_is_directory=True)
    env = fresh_environment(home, tmp, minimal_path(work, stage, python))
    git = str(stage / "git")
    name = LANES[int(partial)]
    declared_skips = {node: reason for node, reason in EXPECTED_HISTORY_SKIPS.items()
                      if any(selector_matches(node, selector) for selector in SELECTORS)}
    row: dict[str, Any] = {"name": name, "state": "UNKNOWN", "reason": "not started",
                           "expected_skips": declared_skips}
    before = time.monotonic()
    mask = os.umask(0)
    try:
        path = checkout(seed, witness, work, git, partial, env)
        preconditions, details = observe(path, work, witness, git, stage, env, tier, partial)
        row.update(preconditions=preconditions, **details)
        if not all(preconditions.values()):
            raise Unknown("shape preconditions failed: " + ", ".join(
                key for key, value in preconditions.items() if not value))
        # The checkout, not pytest fixture creation, inherits the clone umask.
        # The test mask must come from actual image evidence, never a guess.
        os.umask(test_umask)
        row.update(checkout_umask="000", test_umask=f"{test_umask:03o}")
        # Dependencies come from the frozen lock, not from the caller's plugins.
        # Link only an environment built for this exact project lock by run().
        (path / ".venv").symlink_to(python.parent.parent, target_is_directory=True)
        results = work / "results.json"
        env.update(PYTHONPATH=str(path), CPP_CI_SHAPE_RESULTS=str(results),
                   CPP_CI_SHAPE_EXPECTED_SKIPS=json.dumps(declared_skips, sort_keys=True),
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
        argv = [python, "-m", "pytest", "-c", path / "pyproject.toml", "--rootdir", path,
                "-p", "lib.ci_shape_pytest", "-p", "pytest_timeout", "-p", "xdist.plugin",
                "-n", "0", "--durations=15", "-q", "-rs", "--basetemp", work / "pytest",
                *[path / selector for selector in SELECTORS]]
        # Each run owns its basetemp under TemporaryDirectory, never the global
        # pytest-of-* namespace. The context removes it even after failure.
        with (logs / (name + ".log")).open("w") as output:
            exit_code = _owned_pytest(argv, cwd=work, env=env, output=output)
        log = (logs / (name + ".log")).read_text()
        payload = json.loads(results.read_text()) if results.exists() else {}
        state, reason = completion(payload, exit_code, log, tier)
        row.update(state=state, reason=reason, results=payload, exit=exit_code,
                   diagnostic="INTERNALERROR" if "INTERNALERROR" in log else "",
                   log_sha256=hashlib.sha256(log.encode()).hexdigest())
        outcomes = payload.get("outcomes", {})
        row["counts"] = {"selected": len(payload.get("selected", [])),
                         "executed": sum(value != "skipped" for value in outcomes.values()),
                         "skipped": len(payload.get("skips", {}))}
    except (Unknown, OSError, subprocess.SubprocessError, ValueError) as exc:
        row.update(state="UNKNOWN", reason=str(exc)[-2000:])
    finally:
        os.umask(mask)
        row["seconds"] = round(time.monotonic() - before, 2)
    return row


def run(root: Path, tier: str, receipt_path: Path, *, inside_image: str | None = None) -> dict:
    commit = "unresolved"
    image = image_pin(root)
    record: dict[str, Any] = {"schema": 1, "tier": tier, "commit": commit, "image": image,
                              "selectors": list(SELECTORS), "lanes": [], "state": "UNKNOWN"}
    record["root"] = {"state": "UNKNOWN", "reason": "not examined: needs real uid 0"}
    record["pytest_time_umask"] = {"state": "UNKNOWN", "reason": "CI default not proven"}
    try:
        bootstrap_git = shutil.which("git")
        if bootstrap_git:
            commit = command([bootstrap_git, "-c", f"safe.directory={root}", "-C", root,
                              "rev-parse", "HEAD"], env={"PATH": os.environ.get("PATH", ""),
                                                         "GIT_CONFIG_GLOBAL": os.devnull,
                                                         "GIT_CONFIG_NOSYSTEM": "1"}).stdout.strip()
            record["commit"] = commit
        if tier == "image" and (os.getuid() != 0 or os.geteuid() != 0 or inside_image != image):
            raise Unknown("image tier requires real uid 0 and the pinned-image launcher")
        if tier == "local" and (os.getuid() == 0 or os.geteuid() == 0):
            raise Unknown("local non-root tier requires a non-root process")
        if not manifest_complete(SELECTORS):
            raise Unknown("selector manifest dropped a required named witness")
        if tier == "image":
            actual_mask = os.umask(0)
            os.umask(actual_mask)
            profile = {"state": "GOOD", "image": image, "umask": actual_mask,
                       "evidence": "actual inherited umask at real uid 0 in pinned-image launcher"}
            print(f"CI_SHAPE_IMAGE_DEFAULT_UMASK: {actual_mask:04o}", flush=True)
        else:
            profile = ci_profile(root)
        record["pytest_time_umask"] = profile
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        logs = receipt_path.parent / (receipt_path.stem + "-logs")
        logs.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cpp-ci-shape-") as temporary:
            work = Path(temporary).resolve()
            if tier == "image":
                work.chmod(0o755)
            env = fresh_environment(work, work, os.environ.get("PATH", ""))
            env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="safe.directory",
                       GIT_CONFIG_VALUE_0=str(root))
            stage_root = work / "tools"
            stage_root.mkdir()
            for tool in ("git", "make"):
                staged = command([sys.executable, root / f"scripts/ci-stage-{tool}.py"],
                                 cwd=stage_root, env=env)
                (logs / f"stage-{tool}.log").write_text(staged.stdout + staged.stderr)
            stage = stage_root / ".ci-bin"
            source_git = [stage / "git", "-c", f"safe.directory={root}", "-C", root]
            commit = command([*source_git, "rev-parse", "HEAD"], env=env).stdout.strip()
            record["commit"] = commit
            # Refuse to label a committed SHA with dirty tracked inputs.
            if command([*source_git, "status", "--porcelain", "--untracked-files=no"], env=env).stdout:
                raise Unknown("tracked source is dirty; commit the implementation checkpoint")
            record["tools"] = {name: {"path": str(stage / name), "version": command(
                [stage / name, "--version"], env=env).stdout.splitlines()[0]}
                for name in ("git", "make")}
            uv = shutil.which("uv")
            if not uv:
                raise Unknown("uv unavailable")
            python_env = work / "venv"
            command([uv, "sync", "--project", root, "--extra", "dev", "--frozen"],
                    env={**env, "UV_PROJECT_ENVIRONMENT": str(python_env)})
            python = python_env / "bin/python"
            record["tools"].update({
                "python": {"path": str(python), "version": command([python, "--version"]).stdout.strip()},
                "uv": {"path": uv, "version": command([uv, "--version"]).stdout.strip()},
            })
            seed, witness = donor(root, work, str(stage / "git"), commit, env)
            for partial in (False, True):
                row = run_lane(root, seed, witness, work / LANES[int(partial)],
                               stage, python, tier, partial, logs, profile["umask"])
                record["lanes"].append(row)
                print("CI_SHAPE_LANE:", row["name"], row["state"], row["reason"], flush=True)
        if tier == "image" and all(row["state"] == "GOOD" for row in record["lanes"]):
            record["root"] = {"state": "GOOD", "reason": "real uid 0 in pinned validate image"}
        record["state"], record["reason"] = assess(record, tier=tier, commit=commit, image=image)
    except (Unknown, OSError, subprocess.SubprocessError, ValueError) as exc:
        detail = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            detail += "\n" + (exc.stdout or "") + (exc.stderr or "")
        record.update(state="UNKNOWN", reason=detail[-2000:])
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record
