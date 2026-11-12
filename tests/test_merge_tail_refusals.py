"""Refusals in the merge and cleanup helpers that nothing made fire (issue #1726).

Five helpers decide whether a pull request merges and whether a checkout is
deleted. Each "stop" branch in them exists because something was once lost.
The #1693 survey found about thirty that no test and no registered control
could show firing, so a change that broke one would have stayed green.

Each test here makes ONE refusal fire against the unmodified script and
asserts its exit code AND the text that names it. An exit code alone does not
tell two refusals with the same code apart, and several of these share one.
No test hook was added to a script to reach any of them: the inputs are
arguments, filesystem state in a temporary directory, an environment variable
the script already documents as a seam, or a stub placed first on PATH.

For the stub cases, a second test shows the stub failing for the WRONG caller
does not produce the refusal - otherwise a test could pass because something
broke, not because the branch under test fired.

The table on #1726 lists every refusal with the test that fires it, and
records that each test fails when its refusal is removed from a scratch copy
of the script.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAIM = ROOT / "scripts" / "flow-worktree-claim.sh"
SWEEP = ROOT / "scripts" / "flow-worktree-sweep.sh"
REMOVE = ROOT / "scripts" / "worktree-remove.sh"
GUARD = ROOT / "scripts" / "flow-worktree-guard.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="builds real git repositories and runs the helpers under bash",
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.email=t@example.com", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True, timeout=60,
    ).stdout


def _run(script: Path, *args: str, cwd: Path, env: dict[str, str] | None = None,
         ) -> subprocess.CompletedProcess[str]:
    full = dict(os.environ)
    for leak in ("FLOW_CLAIM_PROC_ROOT", "FLOW_CLAIM_LIVE_PIDS", "FLOW_CLAIM_GIT", "FLOW_WORKTREE_GIT",
                 "FLOW_CLAIM_MUTEX_WAIT", "CODEX_THREAD_ID"):
        full.pop(leak, None)
    full.update(env or {})
    return subprocess.run(["bash", str(script), *args], cwd=cwd, env=full, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60, check=False)


_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_TRAILER = re.compile(r"^[A-Z][A-Z_]*_EXIT=\d+$")


def _assert_stopped_at(done: subprocess.CompletedProcess[str], message: str, *, then: tuple[str, ...] = ()) -> None:
    """The script printed `message` ONCE and then stopped: nothing follows it
    on stderr but lines that belong to the same refusal (`then`) and the exit
    trailer.

    Asserting the message and the exit code is not enough. Several of these
    refusals are followed by a second line of defence with the same exit code,
    so with the refusal's `exit` deleted the script printed the same message,
    ran on, and was stopped later by something else - and a test that checked
    only message and code still passed. That is a script that kept going after
    saying it would not, and this is what notices."""
    lines = [_ANSI.sub("", ln) for ln in done.stderr.splitlines() if ln.strip()]
    hits = [i for i, ln in enumerate(lines) if message in ln]
    assert len(hits) == 1, f"expected {message!r} exactly once on stderr, saw {len(hits)}:\n{done.stderr}"
    after = [ln for ln in lines[hits[0] + 1:] if not _TRAILER.match(ln) and not any(t in ln for t in then)]
    assert not after, f"the script went on after refusing with {message!r}:\n" + "\n".join(after)


def _main_and_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "a.txt").write_text("a\n", encoding="utf-8")
    _git(main, "add", "a.txt")
    _git(main, "commit", "-q", "-m", "base")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", "-b", "issue-42-x", str(wt))
    return main, wt


# ============================================================================
# flow-worktree-claim.sh
# ============================================================================

CLAIM_ENV = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "observer", "FLOW_CLAIM_HOST": "testhost"}


@pytest.mark.parametrize("lookup", ["by-path", "by-issue"])
def test_claim_check_exit_code_returns_1_for_a_held_claim(tmp_path: Path, lookup: str) -> None:
    """`check --exit-code` is the one form a script can branch on. Nothing
    passed the flag: no test, and no caller in the repository."""
    main, wt = _main_and_worktree(tmp_path)
    owner = {"CLAUDE_PID": "9999", "CLAUDE_CODE_SESSION_ID": "other", "FLOW_CLAIM_HOST": "testhost",
             "FLOW_CLAIM_LIVE_PIDS": "9999"}
    assert _run(CLAIM, "claim", str(wt), "--issue", "42", cwd=tmp_path, env=owner).returncode == 0
    env = dict(CLAIM_ENV, FLOW_CLAIM_LIVE_PIDS="9999")
    where = (str(wt),) if lookup == "by-path" else ("--issue", "42", "--repo", str(main))

    plain = _run(CLAIM, "check", *where, cwd=tmp_path, env=env)
    assert plain.returncode == 0 and "FLOW_CLAIM: held" in plain.stdout, "precondition: held, and 0 without the flag"
    flagged = _run(CLAIM, "check", *where, "--exit-code", cwd=tmp_path, env=env)
    assert flagged.returncode == 1, flagged.stdout + flagged.stderr
    assert "FLOW_CLAIM: held" in flagged.stdout
    assert "FLOW_CLAIM_EXIT=1" in flagged.stderr


def test_claim_check_exit_code_stays_0_for_a_claim_that_is_not_held(tmp_path: Path) -> None:
    """The other side: the flag does not turn free or stale into a failure."""
    _main, wt = _main_and_worktree(tmp_path)
    free = _run(CLAIM, "check", str(wt), "--exit-code", cwd=tmp_path, env=CLAIM_ENV)
    assert free.returncode == 0 and "FLOW_CLAIM: free" in free.stdout


@pytest.mark.parametrize("argv,message", [
    ((), "usage: flow-worktree-claim.sh claim|check|release <WORKTREE_PATH> [options]"),
    (("frobnicate",), "unknown verb: frobnicate (expected claim, check or release)"),
    (("check", "WT", "--issue"), "--issue requires a number"),
    (("check", "--issue", "42", "--repo"), "--repo requires a path"),
    (("check", "WT", "--bogus"), "unknown option: --bogus"),
    (("check", "WT", "extra"), "unexpected argument: extra"),
    (("check", "WT", "--issue", "abc"), "--issue must be a number, got: abc"),
    (("check", "WT", "--issue=4x"), "--issue must be a number, got: 4x"),
    (("check",), "check requires a worktree path"),
    (("release",), "release requires a worktree path"),
    (("claim", "--issue", "42"), "claim requires a worktree path"),
], ids=["no-arguments", "unknown-verb", "issue-no-value", "repo-no-value", "unknown-option",
        "extra-argument", "issue-not-a-number", "issue-equals-not-a-number", "check-no-path",
        "release-no-path", "claim-no-path"])
def test_claim_usage_errors_exit_2_and_name_the_mistake(tmp_path: Path, argv: tuple[str, ...],
                                                        message: str) -> None:
    _main, wt = _main_and_worktree(tmp_path)
    args = [str(wt) if a == "WT" else a for a in argv]
    done = _run(CLAIM, *args, cwd=tmp_path, env=CLAIM_ENV)
    assert done.returncode == 2, done.stdout + done.stderr
    assert f"flow-worktree-claim: {message}" in done.stderr
    assert "FLOW_CLAIM:" not in done.stdout, "a usage error must not also print a verdict"
    listing = _git(wt, "worktree", "list", "--porcelain")
    assert "locked" not in listing, "a usage error changed a claim"


# ============================================================================
# flow-worktree-sweep.sh
# ============================================================================

@pytest.mark.parametrize("argv,message", [
    (("--repo",), "Error: --repo requires a path"),
    (("--repo", ""), "Error: --repo requires a path"),
    (("--bogus",), "Error: unknown argument '--bogus'"),
], ids=["repo-no-value", "repo-empty", "unknown-argument"])
def test_sweep_usage_errors_exit_1_and_say_error(tmp_path: Path, argv: tuple[str, ...], message: str) -> None:
    main, wt = _main_and_worktree(tmp_path)
    done = _run(SWEEP, *argv, cwd=main)
    assert done.returncode == 1, done.stdout + done.stderr
    _assert_stopped_at(done, message, then=("FLOW_WORKTREE_SWEEP: error", "Usage: flow-worktree-sweep.sh"))
    assert "FLOW_WORKTREE_SWEEP: error" in done.stderr
    assert "SWEEP_WORKTREE:" not in done.stdout, "a usage error must not have examined any worktree"
    assert wt.exists()


def test_sweep_unknown_argument_prints_its_usage(tmp_path: Path) -> None:
    main, _wt = _main_and_worktree(tmp_path)
    done = _run(SWEEP, "--aply", cwd=main)
    assert done.returncode == 1
    assert "Usage: flow-worktree-sweep.sh [--repo <path>] [--apply] [--include-closed]" in done.stderr


@pytest.mark.parametrize("how", ["repo-is-a-plain-directory", "repo-is-missing", "cwd-is-a-plain-directory"])
def test_sweep_outside_a_repository_is_an_error_not_an_empty_sweep(tmp_path: Path, how: str) -> None:
    """`no-candidates` means a repository with no linked worktrees. A path that
    is not a repository at all must not read as the same thing."""
    plain = tmp_path / "plain"
    plain.mkdir()
    probe = subprocess.run(["git", "-C", str(plain), "rev-parse", "--git-dir"], capture_output=True, check=False)
    assert probe.returncode != 0, "precondition: the temporary directory is outside every repository"
    if how == "repo-is-a-plain-directory":
        done = _run(SWEEP, "--repo", str(plain), cwd=tmp_path)
        named = str(plain)
    elif how == "repo-is-missing":
        done = _run(SWEEP, "--repo", str(tmp_path / "nowhere"), cwd=tmp_path)
        named = str(tmp_path / "nowhere")
    else:
        done = _run(SWEEP, cwd=plain)
        named = str(plain)
    assert done.returncode == 1, done.stdout + done.stderr
    assert f"Error: not a git repository: {named}" in done.stderr
    assert "FLOW_WORKTREE_SWEEP: error" in done.stderr
    assert "no-candidates" not in done.stdout + done.stderr


# ============================================================================
# worktree-remove.sh - usage and resolution errors (exit 1)
# ============================================================================

def test_remove_owner_repo_with_no_value_is_refused(tmp_path: Path) -> None:
    _main, wt = _main_and_worktree(tmp_path)
    done = _run(REMOVE, str(wt), "--owner-repo", cwd=tmp_path)
    assert done.returncode == 1, done.stdout + done.stderr
    _assert_stopped_at(done, "Error: --owner-repo requires a value")
    assert wt.exists()


def test_remove_a_second_positional_argument_is_refused_not_ignored(tmp_path: Path) -> None:
    """A mistyped flag after the path lands here too. Ignoring it would run a
    removal the caller did not spell."""
    _main, wt = _main_and_worktree(tmp_path)
    for extra in ("extra", "--forse"):
        done = _run(REMOVE, str(wt), extra, cwd=tmp_path)
        assert done.returncode == 1, done.stdout + done.stderr
        _assert_stopped_at(done, f"Error: Unknown argument: {extra}")
        assert wt.exists(), "the worktree was removed despite an argument the script did not understand"


def test_remove_no_path_names_what_is_missing(tmp_path: Path) -> None:
    """Already reached by a test that asserts only the exit code; this pins the text."""
    done = _run(REMOVE, cwd=tmp_path)
    assert done.returncode == 1
    _assert_stopped_at(done, "Error: Worktree path is required")


def test_remove_a_directory_that_is_not_a_worktree_says_so(tmp_path: Path) -> None:
    """Passing the MAIN checkout. Reached before by a test asserting only a
    non-zero exit, which a crash would also satisfy."""
    main, _wt = _main_and_worktree(tmp_path)
    done = _run(REMOVE, str(main), "--force", cwd=tmp_path)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "is not a git worktree" in done.stderr
    assert (main / ".git").is_dir() and (main / "a.txt").exists()


def test_remove_a_gitdir_pointer_to_nowhere_cannot_find_the_main_repository(tmp_path: Path) -> None:
    orphan = tmp_path / "orphan"
    orphan.mkdir()
    (orphan / ".git").write_text(f"gitdir: {tmp_path}/nowhere/.git/worktrees/x\n", encoding="utf-8")
    (orphan / "work.txt").write_text("someone's work\n", encoding="utf-8")
    assert not (tmp_path / "nowhere").exists(), "precondition: the pointer leads nowhere"
    done = _run(REMOVE, str(orphan), "--force", cwd=tmp_path)
    assert done.returncode == 1, done.stdout + done.stderr
    _assert_stopped_at(done, "Error: Could not find main repository", then=("Expected at:", "expected at"))
    assert (orphan / "work.txt").exists(), "the directory was touched"


def test_remove_refuses_when_it_cannot_enter_the_main_repository(tmp_path: Path) -> None:
    """Called from INSIDE the worktree, the script must move to the main
    repository before removing its own cwd. If that `cd` fails it stops. The
    only way to make `cd` fail right after `-d` passed, without a race, is a
    main repository whose relative name `cd` reads as an option."""
    wt = tmp_path / "W"
    (wt / "-x" / ".git").mkdir(parents=True)
    (wt / ".git").write_text("gitdir: -x/.git/worktrees/w\n", encoding="utf-8")
    (wt / "work.txt").write_text("someone's work\n", encoding="utf-8")
    done = _run(REMOVE, str(wt), "--force", cwd=wt)
    assert done.returncode == 1, done.stdout + done.stderr
    _assert_stopped_at(done, "Error: Failed to change to main repository")
    assert (wt / "work.txt").exists()


# ============================================================================
# worktree-remove.sh - the finish-partial-removal path, and the prescan
# ============================================================================

def _stub(bindir: Path, name: str, body: str) -> Path:
    """A stub for one tool, first on PATH. `REAL` in the body is the real tool."""
    real = shutil.which(name)
    assert real, f"precondition: a real {name} exists to stand in front of"
    bindir.mkdir(parents=True, exist_ok=True)
    path = bindir / name
    path.write_text("#!/bin/bash\n" + body.replace("REAL", real) + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _path_with(bindir: Path) -> dict[str, str]:
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}
    for tool in bindir.iterdir():
        found = shutil.which(tool.name, path=env["PATH"])
        assert found == str(tool), f"precondition: the stub {tool.name} is found first"
    return env


def _half_deleted(tmp_path: Path) -> tuple[Path, Path]:
    """The state --finish-partial-removal exists for: the directory is there,
    its .git file is gone, and the owner's registry still names it."""
    main, wt = _main_and_worktree(tmp_path)
    (wt / "leftover.txt").write_text("left behind by a failed removal\n", encoding="utf-8")
    (wt / ".git").unlink()
    assert "prunable" in _git(main, "worktree", "list", "--porcelain"), "precondition: the owner lists it prunable"
    return main, wt


FP = ("--finish-partial-removal", "--allow-dirty", "--allow-unpushed")


def _finish_partial(wt: Path, main: Path, *, flags: tuple[str, ...] = FP, env: dict[str, str] | None = None,
                    ) -> subprocess.CompletedProcess[str]:
    return _run(REMOVE, str(wt), "--owner-repo", str(main), *flags, cwd=main.parent, env=env)


def test_finish_partial_baseline_succeeds_so_the_refusals_below_are_the_stub(tmp_path: Path) -> None:
    """The same call with no stub and a usable TMPDIR ends in the documented
    success (exit 15, a printed rm line). Every refusal test below differs
    from this one in exactly one thing."""
    main, wt = _half_deleted(tmp_path)
    done = _finish_partial(wt, main)
    assert done.returncode == 15, done.stdout + done.stderr
    assert wt.exists(), "this path never deletes; it prints the command for a human"


def test_finish_partial_refuses_when_no_temp_file_can_be_made(tmp_path: Path) -> None:
    main, wt = _half_deleted(tmp_path)
    missing = tmp_path / "no-such-tmp"
    assert not missing.exists(), "precondition: TMPDIR names a directory that does not exist"
    done = _finish_partial(wt, main, env={"TMPDIR": str(missing)})
    assert done.returncode == 13, done.stdout + done.stderr
    _assert_stopped_at(done, "could not create a temp file to read the owner's worktree registry")
    assert "rm -rf" not in done.stdout, "a removal command was printed without the registry having been read"
    assert (wt / "leftover.txt").exists()


def test_finish_partial_refuses_when_the_permission_scan_itself_fails(tmp_path: Path) -> None:
    """`PRESCAN: unknown` on the finish-partial path. The existing test for
    this path makes the scan FIND something (exit 9, `undeletable`); nothing
    made the scan itself fail. A `find` that reports an error is not a clean
    tree, and the rm line must not be printed on the strength of it."""
    main, wt = _half_deleted(tmp_path)
    bindir = tmp_path / "bin"
    _stub(bindir, "find", 'REAL "$@"\nexit 1')
    done = _finish_partial(wt, main, env=_path_with(bindir))
    assert done.returncode == 9, done.stdout + done.stderr
    assert "WORKTREE_REMOVE_PRESCAN: unknown" in done.stderr
    assert "the permission scan itself failed - this is not the same as clean" in done.stderr
    assert "rm -rf" not in done.stdout


def test_a_find_stub_that_changes_nothing_does_not_produce_that_refusal(tmp_path: Path) -> None:
    """Wrong-caller control for the test above: with a pass-through `find` the
    same call succeeds, so the refusal came from the scan failing."""
    main, wt = _half_deleted(tmp_path)
    bindir = tmp_path / "bin"
    _stub(bindir, "find", 'exec REAL "$@"')
    done = _finish_partial(wt, main, env=_path_with(bindir))
    assert done.returncode == 15, done.stdout + done.stderr
    assert "PRESCAN: unknown" not in done.stderr


@pytest.mark.parametrize("behaviour,body", [
    ("readlink-fails", "exit 1"),
    ("readlink-prints-nothing", "exit 0"),
])
def test_finish_partial_refuses_a_path_it_cannot_resolve(tmp_path: Path, behaviour: str, body: str) -> None:
    """Two refusals with one message and one exit code: `readlink -f` failing,
    and `readlink -f` succeeding with an empty answer. Which one fired is
    decided by what the stub does. Either way the script must not fall back
    to the unresolved argument, which may be a symlink to somewhere else."""
    main, wt = _half_deleted(tmp_path)
    bindir = tmp_path / "bin"
    _stub(bindir, "readlink", body)
    done = _finish_partial(wt, main, env=_path_with(bindir))
    assert done.returncode == 12, f"{behaviour}: {done.stdout}{done.stderr}"
    _assert_stopped_at(done, "to a real path")
    assert "could not resolve" in done.stderr
    assert "rm -rf" not in done.stdout


def test_a_readlink_stub_that_changes_nothing_does_not_produce_that_refusal(tmp_path: Path) -> None:
    main, wt = _half_deleted(tmp_path)
    bindir = tmp_path / "bin"
    _stub(bindir, "readlink", 'exec REAL "$@"')
    done = _finish_partial(wt, main, env=_path_with(bindir))
    assert done.returncode == 15, done.stdout + done.stderr
    assert "could not resolve" not in done.stderr


def _git_stub_without_head(bindir: Path, wt: Path) -> None:
    """A git whose registry listing names the path as prunable and carries NO
    HEAD field. Real git cannot produce this: with the admin HEAD file gone it
    still prints an all-zero HEAD."""
    record = f"worktree {wt.resolve()}\\0prunable gitdir file points to non-existent location\\0\\0"
    _stub(bindir, "git", f"""case " $* " in
  *" worktree list --porcelain -z "*) printf '{record}'; exit 0 ;;
esac
exec REAL "$@\"""")


def test_finish_partial_refuses_when_it_cannot_tell_which_commit_to_check(tmp_path: Path) -> None:
    """Without --allow-unpushed the path must show the worktree's commits are
    on a remote. With no HEAD in the owner's record there is no commit to ask
    about, and "nothing to check" must not read as "nothing unpushed"."""
    main, wt = _half_deleted(tmp_path)
    bindir = tmp_path / "bin"
    _git_stub_without_head(bindir, wt)
    done = _finish_partial(wt, main, flags=("--finish-partial-removal", "--allow-dirty"), env=_path_with(bindir))
    assert done.returncode == 7, done.stdout + done.stderr
    _assert_stopped_at(done, "could not determine the worktree's HEAD commit to check",
                       then=("whether it is pushed; refusing rather than assuming it is.",))
    assert "rm -rf" not in done.stdout


def test_with_a_real_registry_the_same_call_refuses_for_a_different_reason(tmp_path: Path) -> None:
    """Wrong-caller control: real git gives a HEAD, so the same flags reach
    the ordinary unpushed-commits refusal, not the no-HEAD one."""
    main, wt = _half_deleted(tmp_path)
    bindir = tmp_path / "bin"
    _stub(bindir, "git", 'exec REAL "$@"')
    done = _finish_partial(wt, main, flags=("--finish-partial-removal", "--allow-dirty"), env=_path_with(bindir))
    assert done.returncode == 7, done.stdout + done.stderr
    assert "could not determine the worktree's HEAD commit" not in done.stderr
    assert "WORKTREE_REMOVE_UNPUSHED: refused" in done.stderr


def test_normal_removal_refuses_when_the_permission_scan_cannot_run(tmp_path: Path) -> None:
    """`PRESCAN: unknown` on the ordinary path, pinned by its marker. The one
    existing test that reaches it accepts either of two messages and needs a
    non-root caller; this needs neither."""
    _main, wt = _main_and_worktree(tmp_path)
    missing = tmp_path / "no-such-tmp"
    assert not missing.exists(), "precondition: TMPDIR names a directory that does not exist"
    done = _run(REMOVE, str(wt), "--force", "--allow-unpushed", cwd=tmp_path, env={"TMPDIR": str(missing)})
    assert done.returncode == 9, done.stdout + done.stderr
    assert "WORKTREE_REMOVE_PRESCAN: unknown" in done.stderr
    assert "Re-run once the directory tree can be read." in done.stderr
    assert wt.exists() and (wt / ".git").exists(), "the worktree was touched after a scan that did not run"


# ============================================================================
# flow-worktree-guard.sh - the `unknown` verdicts nothing fired
# ============================================================================

def _guard(cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return _run(GUARD, "--strict", cwd=cwd, env=env)


def _verdict_line(done: subprocess.CompletedProcess[str]) -> str:
    return next((ln for ln in (done.stdout + done.stderr).splitlines()
                 if ln.startswith("FLOW_WORKTREE_GUARD:")), "")


def _git_seam(tmp_path: Path, body: str) -> dict[str, str]:
    """A git handed to the guard through its documented seam, FLOW_WORKTREE_GIT."""
    real = shutil.which("git")
    stub = tmp_path / "seam-git"
    stub.write_text("#!/bin/bash\n" + body.replace("REAL", str(real)) + "\n", encoding="utf-8")
    stub.chmod(0o755)
    return {"FLOW_WORKTREE_GIT": str(stub)}


def test_guard_baseline_is_no_leak_so_the_unknowns_below_are_their_cause(tmp_path: Path) -> None:
    _main, wt = _main_and_worktree(tmp_path)
    done = _guard(wt)
    assert done.returncode == 0 and _verdict_line(done).startswith("FLOW_WORKTREE_GUARD: no-leak")


def test_guard_with_no_git_is_unknown(tmp_path: Path) -> None:
    _main, wt = _main_and_worktree(tmp_path)
    absent = tmp_path / "no-such-git"
    assert not absent.exists(), "precondition: the named git does not exist"
    done = _guard(wt, env={"FLOW_WORKTREE_GIT": str(absent)})
    assert done.returncode == 4, done.stdout + done.stderr
    assert f"FLOW_WORKTREE_GUARD: unknown - git ('{absent}') is not on PATH" in _verdict_line(done)


def test_guard_in_a_worktree_of_a_bare_repository_is_unknown(tmp_path: Path) -> None:
    """There is no main TREE to have leaked into. That is could-not-look, and
    it must not be read as a clean one."""
    main, _wt = _main_and_worktree(tmp_path)
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(main), str(bare)], check=True, capture_output=True, timeout=60)
    wt2 = tmp_path / "from-bare"
    _git(bare, "worktree", "add", "-q", "-b", "issue-7-y", str(wt2))
    done = _guard(wt2)
    assert done.returncode == 4, done.stdout + done.stderr
    assert "FLOW_WORKTREE_GUARD: unknown - the main tree" in _verdict_line(done)
    assert "is not a readable work tree" in _verdict_line(done)


def test_guard_whose_main_tree_resolves_to_itself_is_unknown(tmp_path: Path) -> None:
    _main, wt = _main_and_worktree(tmp_path)
    env = _git_seam(tmp_path, """case "$*" in
  *--git-common-dir*) echo /a/b/.git ;;
  *--git-dir*) echo /a/b/.git/worktrees/w ;;
  *--show-toplevel*) echo /a/b ;;
  *--is-inside-work-tree*) echo true ;;
esac
exit 0""")
    done = _guard(wt, env=env)
    assert done.returncode == 4, done.stdout + done.stderr
    assert "FLOW_WORKTREE_GUARD: unknown - the main tree resolved to this worktree itself" in _verdict_line(done)


def test_guard_with_no_temp_file_is_unknown(tmp_path: Path) -> None:
    _main, wt = _main_and_worktree(tmp_path)
    missing = tmp_path / "no-such-tmp"
    assert not missing.exists(), "precondition: TMPDIR names a directory that does not exist"
    done = _guard(wt, env={"TMPDIR": str(missing)})
    assert done.returncode == 4, done.stdout + done.stderr
    assert "FLOW_WORKTREE_GUARD: unknown - no temporary file for main's status" in _verdict_line(done)


def test_guard_when_the_main_trees_status_fails_is_unknown(tmp_path: Path) -> None:
    """Real git, no stub: main's index is unreadable. The linked worktree has
    its own index, so every earlier probe still answers."""
    main, wt = _main_and_worktree(tmp_path)
    (main / ".git" / "index").write_bytes(b"this is not an index")
    probe = subprocess.run(["git", "-C", str(main), "status", "--porcelain"], capture_output=True, check=False)
    assert probe.returncode != 0, "precondition: git status fails in main"
    done = _guard(wt)
    assert done.returncode == 4, done.stdout + done.stderr
    assert "FLOW_WORKTREE_GUARD: unknown - git status of the main tree" in _verdict_line(done)
    assert "failed" in _verdict_line(done)


def test_guard_when_this_runs_history_cannot_be_related_to_main_is_unknown(tmp_path: Path) -> None:
    """Main has a tracked change and this worktree is on a branch with no
    common ancestor, so which paths this run edited cannot be worked out."""
    main, wt = _main_and_worktree(tmp_path)
    (main / "a.txt").write_text("changed in main\n", encoding="utf-8")
    _git(wt, "checkout", "-q", "--orphan", "lonely")
    _git(wt, "commit", "-q", "--allow-empty", "-m", "unrelated")
    probe = subprocess.run(["git", "-C", str(wt), "merge-base", "HEAD", "main"], capture_output=True, check=False)
    assert probe.returncode != 0, "precondition: no merge base with main"
    done = _guard(wt)
    assert done.returncode == 4, done.stdout + done.stderr
    assert "FLOW_WORKTREE_GUARD: unknown - git merge-base HEAD" in _verdict_line(done)
    assert "this run's edited paths are unknown" in _verdict_line(done)


def test_guard_when_the_diff_of_this_runs_commits_fails_is_unknown(tmp_path: Path) -> None:
    main, wt = _main_and_worktree(tmp_path)
    (main / "a.txt").write_text("changed in main\n", encoding="utf-8")
    env = _git_seam(tmp_path, """case "$*" in
  "diff --name-only "*) exit 1 ;;
esac
exec REAL "$@\"""")
    done = _guard(wt, env=env)
    assert done.returncode == 4, done.stdout + done.stderr
    assert ("FLOW_WORKTREE_GUARD: unknown - git diff of this run's commits failed; "
            "this run's edited paths are unknown") in _verdict_line(done)


def test_a_seam_git_that_changes_nothing_gives_the_ordinary_verdict(tmp_path: Path) -> None:
    """Wrong-caller control for the two seam tests: the same dirty main with a
    pass-through git is an ordinary verdict about main, not `unknown`."""
    main, wt = _main_and_worktree(tmp_path)
    (main / "a.txt").write_text("changed in main\n", encoding="utf-8")
    done = _guard(wt, env=_git_seam(tmp_path, 'exec REAL "$@"'))
    assert "FLOW_WORKTREE_GUARD: unknown" not in _verdict_line(done), _verdict_line(done)


def test_guard_idle_worktree_with_a_file_deleted_in_main_is_unknown(tmp_path: Path) -> None:
    """This run edited nothing, and main has lost a tracked file. How recently
    cannot be established for a path that is not there, so the guard cannot
    say the change is old. The existing deleted-in-main test edits the same
    file in the worktree first and takes the overlap route."""
    main, wt = _main_and_worktree(tmp_path)
    (main / "a.txt").unlink()
    done = _guard(wt)
    assert done.returncode == 4, done.stdout + done.stderr
    assert ("FLOW_WORKTREE_GUARD: unknown - idle worktree; freshness of 1 main modification(s) "
            "could not be established") in _verdict_line(done)


# ============================================================================
# gh-pr-merge.sh - the close-keyword classifier's check on itself (exit 8)
# ============================================================================

def test_merge_stops_when_the_close_keyword_classifier_fails_its_own_check(tmp_path: Path) -> None:
    """Before it scans a pull request for a close keyword that would shut the
    wrong issue, the helper asks its classifier four questions with known
    answers. A wrong answer means the scan cannot be trusted, and the merge
    stops (exit 8) before anything is merged. The answers come from
    `grep -P`; a grep that cannot do it is how this fires outside a code
    change. Nothing made it fire: the only mention anywhere was a vendored
    copy of the script."""
    from tests.test_gh_pr_merge import _calls, _linked_worktree, _make_stubs
    from tests.test_gh_pr_merge import _run as merge_run

    stubs = _make_stubs(tmp_path, pr_state="OPEN", pr_title="fix: complete issue work", pr_body="Closes #99")
    bindir = tmp_path / "grepbin"
    _stub(bindir, "grep", '[ "$1" = "-Pq" ] && exit 1\nexec REAL "$@"')
    done = merge_run(_linked_worktree(tmp_path), stubs, "42", "issue-726-fix", extra_env=_path_with(bindir))
    assert done.returncode == 8, done.stdout + done.stderr
    assert "GH_PR_MERGE_INCIDENTAL_CLOSE_SELFCHECK: broken - classifier answered" in done.stderr
    assert "CLEAN STOP: the incidental-close classifier failed its own self-check" in done.stderr
    assert [c for c in _calls(stubs) if c.startswith("gh pr merge")] == [], "a merge was attempted after the stop"


def test_with_a_grep_that_changes_nothing_the_same_pull_request_merges(tmp_path: Path) -> None:
    """Wrong-caller control: a pass-through grep, same pull request, no stop."""
    from tests.test_gh_pr_merge import _linked_worktree, _make_stubs
    from tests.test_gh_pr_merge import _run as merge_run

    stubs = _make_stubs(tmp_path, merge_exit=0, pr_state="MERGED", pr_title="fix: complete issue work",
                        pr_body="Closes #99")
    bindir = tmp_path / "grepbin"
    _stub(bindir, "grep", 'exec REAL "$@"')
    done = merge_run(_linked_worktree(tmp_path), stubs, "42", "issue-726-fix", extra_env=_path_with(bindir))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "SELFCHECK: broken" not in done.stderr
