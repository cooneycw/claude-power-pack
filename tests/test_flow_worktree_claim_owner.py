"""Who a worktree claim says its owner is (issue #1709).

Three changes to `scripts/flow-worktree-claim.sh`, each of which moves a claim
from `stale` to `held` and none of which moves one the other way:

- A Codex session's claim names the `codex` process above the tool shell. It
  used to name the shell, which exits with the command, so the claim read
  `stale` to every other session a moment after it was written.
- A Codex session's claim carries its thread id as the session, so the
  session's own later commands read it as `self`.
- State `Z` in /proc/<pid>/stat is a dead owner only when one thread is left.
  A process whose main thread exited while others still run reads `Z` too.

THE PROPERTY, pinned by `test_no_scenario_moves_towards_stale`: over a matrix
of every input the classifier reads, a claim the helper called held, foreign
or unknown BEFORE this change is never called stale after it, and is
called `self` only by the session whose id the claim carries. A live owner
read as stale is the direction that loses work (a second session takes the
worktree), so that is the direction the test forbids. The "before" side is the
helper as it stood at a88aafdd, kept as a fixture.
"""

from __future__ import annotations

import itertools
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAIM = ROOT / "scripts" / "flow-worktree-claim.sh"
BEFORE = ROOT / "tests" / "fixtures" / "flow-worktree-claim" / "pre-1709.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH",
)

CODEX_PID = "6000"
CODEX_START = "777777"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True,
                          check=False)


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    main.mkdir()
    assert _git(main, "init", "-q").returncode == 0
    assert _git(main, "commit", "-q", "--allow-empty", "-m", "init").returncode == 0
    wt = tmp_path / "wt"
    assert _git(main, "worktree", "add", "-q", str(wt), "-b", "issue-42-thing").returncode == 0
    return main, wt


def _stat(root: Path, pid: str, comm: str, ppid: str, *, state: str = "S", start: str = "1",
          threads: str = "1") -> None:
    """One /proc/<pid>/stat line. After the comm: state, ppid, then 18 more
    fields of which the 18th overall is the thread count and the 20th the
    start time."""
    rest = [state, ppid] + ["0"] * 18
    rest[17] = threads
    rest[19] = start
    d = root / pid
    d.mkdir(parents=True, exist_ok=True)
    (d / "stat").write_text(f"{pid} ({comm}) " + " ".join(rest) + "\n")


def _codex_tree(root: Path, *, session_comm: str = "codex") -> Path:
    """This test process is the helper's parent, so it plays the tool shell:
    shell -> codex-code-mode-host -> codex -> a login shell -> init."""
    me = str(os.getpid())
    _stat(root, me, "bash", "5000")
    _stat(root, "5000", "codex-code-mode", CODEX_PID)
    _stat(root, CODEX_PID, session_comm, "7000", start=CODEX_START)
    _stat(root, "7000", "bash", "1")
    return root


def _helper(script: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    base = {k: v for k, v in os.environ.items()
            if k not in ("CLAUDE_PID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID",
                         "FLOW_CLAIM_PROC_ROOT", "FLOW_CLAIM_LIVE_PIDS", "FLOW_CLAIM_NOW",
                         "FLOW_CLAIM_MAX_AGE_HOURS")}
    base["FLOW_CLAIM_HOST"] = "testhost"
    base.update(env)
    return subprocess.run(["bash", str(script), *args], env=base, capture_output=True, text=True,
                          check=False)


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("FLOW_CLAIM: ")]
    return lines[-1].removeprefix("FLOW_CLAIM: ").strip() if lines else "<none>"


def _field(proc: subprocess.CompletedProcess[str], key: str) -> str:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(f"FLOW_CLAIM_{key}=")]
    return lines[-1].split("=", 1)[1].strip() if lines else "<none>"


def _reason(main: Path, wt: Path) -> str:
    out = _git(main, "worktree", "list", "--porcelain").stdout
    block = out.split(f"worktree {wt.resolve()}", 1)[1]
    return next(ln for ln in block.splitlines() if ln.startswith("locked "))


# --- a Codex session's claim names the codex process -------------------------

def test_a_codex_claim_names_the_codex_process_not_the_tool_shell(tmp_path, repo) -> None:
    main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    env = {"CODEX_THREAD_ID": "thread-a", "FLOW_CLAIM_PROC_ROOT": str(proc),
           "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}
    claimed = _helper(CLAIM, "claim", str(wt), "--issue", "42", env=env)
    assert claimed.returncode == 0, claimed.stderr
    reason = _reason(main, wt)
    assert f"pid={CODEX_PID} " in reason, reason
    assert f"start={CODEX_START}" in reason, "the witness is the codex process's start time"
    assert "session=thread-a " in reason, reason
    assert f"pid={os.getpid()} " not in reason, "the tool shell's pid was recorded"


def test_the_flip_a_codex_claim_is_held_to_another_session_after_the_shell_exits(tmp_path, repo):
    """The reported defect. The tool shell is gone (not in the live set); the
    codex process is alive. Another session must read `held`."""
    _main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    owner = {"CODEX_THREAD_ID": "thread-a", "FLOW_CLAIM_PROC_ROOT": str(proc),
             "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}
    other = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "someone-else",
             "FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}

    assert _helper(CLAIM, "claim", str(wt), "--issue", "42", env=owner).returncode == 0
    seen = _helper(CLAIM, "check", str(wt), env=other)
    assert _verdict(seen) == "held", seen.stdout
    assert _field(seen, "OWNER_WITNESS") == "matched"


def test_the_same_scenario_read_stale_before_the_change(tmp_path, repo) -> None:
    """Red case for the test above, on the helper as it stood before #1709."""
    _main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    owner = {"CODEX_THREAD_ID": "thread-a", "FLOW_CLAIM_PROC_ROOT": str(proc),
             "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}
    other = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "someone-else",
             "FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}
    assert _helper(BEFORE, "claim", str(wt), "--issue", "42", env=owner).returncode == 0
    seen = _helper(BEFORE, "check", str(wt), env=other)
    assert _verdict(seen) == "stale", "precondition: the old helper misjudged this owner"


def test_a_codex_sessions_later_command_reads_its_own_claim_as_self(tmp_path, repo) -> None:
    _main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    env = {"CODEX_THREAD_ID": "thread-a", "FLOW_CLAIM_PROC_ROOT": str(proc),
           "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}
    assert _helper(CLAIM, "claim", str(wt), "--issue", "42", env=env).returncode == 0
    assert _verdict(_helper(CLAIM, "check", str(wt), env=env)) == "self"


def test_another_thread_on_the_same_codex_process_is_not_self(tmp_path, repo) -> None:
    """One app-server can host several threads on one pid (#1563). The thread
    id keeps them apart; this is also the documented over-hold."""
    _main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    a = {"CODEX_THREAD_ID": "thread-a", "FLOW_CLAIM_PROC_ROOT": str(proc),
         "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}
    b = dict(a, CODEX_THREAD_ID="thread-b")
    assert _helper(CLAIM, "claim", str(wt), "--issue", "42", env=a).returncode == 0
    assert _verdict(_helper(CLAIM, "check", str(wt), env=b)) == "held"


@pytest.mark.parametrize("comm", ["codex-code-mode", "node", "co) dex", "Codex", "codex "])
def test_only_a_process_named_exactly_codex_is_taken_as_the_owner(tmp_path, repo, comm) -> None:
    """A walk that stopped at the wrong ancestor would hold the worktree long
    after its owner left, so a near miss records the parent as before."""
    main, wt = repo
    proc = _codex_tree(tmp_path / "proc", session_comm=comm)
    env = {"CODEX_THREAD_ID": "thread-a", "FLOW_CLAIM_PROC_ROOT": str(proc),
           "FLOW_CLAIM_LIVE_PIDS": f"{os.getpid()}:{CODEX_PID}"}
    assert _helper(CLAIM, "claim", str(wt), "--issue", "42", env=env).returncode == 0
    assert f"pid={os.getpid()} " in _reason(main, wt)


def test_claude_identity_is_untouched_even_with_a_codex_ancestor(tmp_path, repo) -> None:
    main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    _stat(proc, "4242", "claude", "1", start="55")
    env = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "claude-session",
           "CODEX_THREAD_ID": "thread-a", "FLOW_CLAIM_PROC_ROOT": str(proc),
           "FLOW_CLAIM_LIVE_PIDS": "4242"}
    assert _helper(CLAIM, "claim", str(wt), "--issue", "42", env=env).returncode == 0
    reason = _reason(main, wt)
    assert "pid=4242 " in reason and "session=claude-session " in reason, reason


def test_without_a_codex_thread_id_no_walk_happens(tmp_path, repo) -> None:
    """Neither harness variable set: the parent, exactly as before."""
    main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    env = {"FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": str(os.getpid())}
    assert _helper(CLAIM, "claim", str(wt), "--issue", "42", env=env).returncode == 0
    reason = _reason(main, wt)
    assert f"pid={os.getpid()} " in reason and "session=- " in reason, reason


def test_a_sessionless_claim_on_a_shared_codex_process_is_not_adopted(tmp_path, repo) -> None:
    """Found by the counter-model review. Once the caller's pid resolves to the
    Codex process, the older "same pid and the claim names no session" rule
    would call that claim `self` for EVERY thread the process hosts - and
    `self` makes worktree-remove.sh release the claim and skip its in-use
    check. A pid that can name several sessions proves nothing alone."""
    main, wt = repo
    proc = _codex_tree(tmp_path / "proc")
    _lock(main, wt, f"flow-claim issue=42 pid={CODEX_PID} session=- host=testhost "
                    f"ts={int(time.time())} start={CODEX_START}")
    env = {"CODEX_THREAD_ID": "thread-b", "FLOW_CLAIM_PROC_ROOT": str(proc),
           "FLOW_CLAIM_LIVE_PIDS": CODEX_PID}
    seen = _helper(CLAIM, "check", str(wt), env=env)
    assert _verdict(seen) == "held", seen.stdout
    released = _helper(CLAIM, "release", str(wt), env=env)
    assert _verdict(released) == "held", "a thread released another thread's claim"
    assert f"pid={CODEX_PID} " in _reason(main, wt), "the claim was dropped"


def test_a_claude_session_still_adopts_its_own_sessionless_claim(tmp_path, repo) -> None:
    """The rule the fix above narrows, unchanged where the pid names one session."""
    main, wt = repo
    proc = tmp_path / "proc"
    _stat(proc, "4242", "claude", "1", start="55")
    _lock(main, wt, f"flow-claim issue=42 pid=4242 session=- host=testhost "
                    f"ts={int(time.time())} start=55")
    env = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "claude-session",
           "FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": "4242"}
    assert _verdict(_helper(CLAIM, "check", str(wt), env=env)) == "self"


# --- a release must not unlock a claim it never judged -----------------------

def _racing_git(bindir: Path, wt: Path, proc: Path) -> Path:
    """A `git` that, the first time it is asked to list worktrees, lets the
    read finish and then has ANOTHER live session claim the worktree before
    returning - the interleaving between a release's read and its unlock."""
    bindir.mkdir(parents=True, exist_ok=True)
    real = shutil.which("git")
    wrapper = bindir / "git"
    wrapper.write_text(f"""#!/bin/bash
out="$({real} "$@")"; rc=$?
if [ -z "${{RACE_DONE:-}}" ] && [[ " $* " == *" worktree list "* ]] && [ ! -e "{bindir}/raced" ]; then
  : > "{bindir}/raced"
  ( RACE_DONE=1 FLOW_CLAIM_GIT={real} CLAUDE_PID=7777 CLAUDE_CODE_SESSION_ID=newcomer \
    FLOW_CLAIM_HOST=testhost FLOW_CLAIM_LIVE_PIDS=7777 FLOW_CLAIM_PROC_ROOT={proc} \
    bash {CLAIM} claim {wt} --issue 42 > "{bindir}/newcomer.out" 2>&1 & )
  {real} -C {wt} worktree list --porcelain >/dev/null   # give the newcomer a moment
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    grep -q FLOW_CLAIM: "{bindir}/newcomer.out" 2>/dev/null && break
    sleep 0.2
  done
fi
printf '%s' "$out"; [ -n "$out" ] && echo
exit $rc
""")
    wrapper.chmod(0o755)
    return wrapper


@pytest.mark.parametrize("serialized", [True, False], ids=["with-flock", "without-flock"])
def test_a_release_does_not_unlock_a_claim_taken_over_meanwhile(tmp_path, repo, serialized) -> None:
    """A stale claim; a release judges it; a live session takes it over before
    the release unlocks. The newcomer's lock must survive, with the mutex
    (the newcomer waits its turn) and without it (the release re-reads the
    lock and stands down)."""
    if serialized and shutil.which("flock") is None:
        pytest.skip("needs flock")
    main, wt = repo
    proc = tmp_path / "proc"
    proc.mkdir()
    _stat(proc, "7777", "claude", "1", start="77")
    _lock(main, wt, f"flow-claim issue=42 pid=9999 session=gone host=testhost "
                    f"ts={int(time.time())} start=111")
    bindir = tmp_path / "bin"
    wrapper = _racing_git(bindir, wt, proc)
    env = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "the-sweeper",
           "FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": "4242:7777",
           "FLOW_CLAIM_GIT": str(wrapper)}
    if not serialized:
        nobin = tmp_path / "noflock"
        nobin.mkdir()
        for tool in ("bash", "cat", "date", "hostname", "grep", "sed", "sleep", "env", "tail"):
            found = shutil.which(tool)
            if found:
                (nobin / tool).symlink_to(found)
        env["PATH"] = str(nobin)
        assert shutil.which("flock", path=str(nobin)) is None, "precondition: no flock on this PATH"
    assert _verdict(_helper(CLAIM, "check", str(wt), env=dict(env, FLOW_CLAIM_GIT="git")
                            if serialized else {k: v for k, v in env.items() if k != "PATH" and k != "FLOW_CLAIM_GIT"})) == "stale"

    released = _helper(CLAIM, "release", str(wt), env=env)
    assert released.returncode == 0, released.stderr
    deadline = time.time() + 10
    while time.time() < deadline and "FLOW_CLAIM:" not in (bindir / "newcomer.out").read_text():
        time.sleep(0.1)
    assert (bindir / "raced").exists(), "the interleaving never happened"
    assert "FLOW_CLAIM: self" in (bindir / "newcomer.out").read_text(), (bindir / "newcomer.out").read_text()
    reason = _reason(main, wt)
    assert "pid=7777 " in reason and "session=newcomer " in reason, (
        f"the newcomer's live claim was unlocked by the release:\n{reason}\n{released.stderr}")


# --- state Z is a dead owner only when one thread is left --------------------

def _lock(main: Path, wt: Path, reason: str) -> None:
    _git(main, "worktree", "unlock", str(wt))
    assert _git(main, "worktree", "lock", "--reason", reason, str(wt)).returncode == 0


@pytest.mark.parametrize("threads,expected,why", [
    ("1", "stale", "owner-zombie"),
    ("2", "held", "-"),
    ("17", "held", "-"),
    ("", "stale", "owner-zombie"),      # unreadable count: the reading #1605 fixed
    ("x", "stale", "owner-zombie"),
])
def test_state_z_counts_as_dead_only_with_one_thread(tmp_path, repo, threads, expected, why):
    main, wt = repo
    proc = tmp_path / "proc"
    _stat(proc, "9999", "worker", "1", state="Z", start="111", threads=threads or "0")
    if threads == "":
        (proc / "9999" / "stat").write_text("9999 (worker) Z 1 0\n")   # line too short to hold a count
    _lock(main, wt, f"flow-claim issue=42 pid=9999 session=other host=testhost "
                    f"ts={int(time.time())} start={'-' if threads == '' else '111'}")
    env = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "observer",
           "FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": "9999"}
    seen = _helper(CLAIM, "check", str(wt), env=env)
    assert _verdict(seen) == expected, seen.stdout
    assert _field(seen, "STALE_REASON") == why


def test_a_live_multi_thread_z_process_read_stale_before_the_change(tmp_path, repo) -> None:
    """Red case: the dangerous misread, on the helper before #1709."""
    main, wt = repo
    proc = tmp_path / "proc"
    _stat(proc, "9999", "worker", "1", state="Z", start="111", threads="2")
    _lock(main, wt, f"flow-claim issue=42 pid=9999 session=other host=testhost "
                    f"ts={int(time.time())} start=111")
    env = {"CLAUDE_PID": "4242", "CLAUDE_CODE_SESSION_ID": "observer",
           "FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": "9999"}
    assert _verdict(_helper(BEFORE, "check", str(wt), env=env)) == "stale"
    assert _verdict(_helper(CLAIM, "check", str(wt), env=env)) == "held"


# --- the property: nothing moves towards stale -------------------------------

NOW = 1_800_000_000
PROTECTED = {"held", "foreign", "unknown"}

OWNER_STATES = ["S", "Z1", "Zmany", "X", "nostat", "dead"]
WITNESSES = ["match", "mismatch", "absent"]
AGES = [60, 48 * 3600]
HOSTS = ["testhost", "elsewhere"]
OWNER_SESSIONS = ["other", "-", "thread-a"]
CALLERS = ["claude", "claude-nosession", "codex", "codex-no-ancestor", "bare"]


def _scenario_env(proc: Path, caller: str, live: str) -> dict[str, str]:
    env = {"FLOW_CLAIM_PROC_ROOT": str(proc), "FLOW_CLAIM_LIVE_PIDS": live,
           "FLOW_CLAIM_NOW": str(NOW)}
    if caller == "claude":
        env.update(CLAUDE_PID="4242", CLAUDE_CODE_SESSION_ID="observer")
    elif caller == "claude-nosession":
        env.update(CLAUDE_PID="4242")
    elif caller in ("codex", "codex-no-ancestor"):
        env.update(CODEX_THREAD_ID="thread-a")
    return env


def _scenarios():
    """(owner pid, owner state, witness, age, host, owner session, caller).

    The full product for a claim owned by an unrelated pid, then a smaller
    block where the claim's pid is the CALLER's own (the `self` lanes)."""
    for combo in itertools.product(OWNER_STATES, WITNESSES, AGES, HOSTS, OWNER_SESSIONS, CALLERS):
        yield ("9999", *combo)
    for combo in itertools.product(["S", "Z1", "Zmany"], WITNESSES, [60], ["testhost"],
                                   OWNER_SESSIONS, CALLERS):
        caller = combo[-1]
        yield ("4242" if caller.startswith("claude") else str(os.getpid()), *combo)
    # A claim naming the Codex process itself, which several threads can share.
    for combo in itertools.product(["S", "Z1", "Zmany"], WITNESSES, [60], ["testhost"],
                                   OWNER_SESSIONS, CALLERS):
        yield (CODEX_PID, *combo)


def test_no_scenario_moves_towards_stale(tmp_path, repo) -> None:
    """Every combination of what the classifier reads, judged by the helper
    before and after: 1,350 claims plus the states that are not claims."""
    main, wt = repo
    moved: list[str] = []
    seen_before: set[str] = set()
    flips: set[tuple[str, str]] = set()
    self_to_stale: list[tuple[str, str, str]] = []
    n = 0
    for owner_pid, owner_state, witness, age, host, owner_session, caller in _scenarios():
        n += 1
        proc = tmp_path / f"proc-{n}"
        proc.mkdir()
        if caller == "codex":
            _codex_tree(proc)
        elif caller == "codex-no-ancestor":
            _codex_tree(proc, session_comm="node")
        if owner_state not in ("nostat", "dead"):
            # Written after the tree, so an owner that IS the caller's parent
            # keeps its place in the chain (same parent) with the posed state.
            comm, parent = "owner", "1"
            if owner_pid == str(os.getpid()):
                comm, parent = "bash", "5000"
            elif owner_pid == CODEX_PID:
                comm, parent = ("codex" if caller == "codex" else "node"), "7000"
            _stat(proc, owner_pid, comm, parent, state=owner_state[0],
                  start="999" if witness == "mismatch" else "111",
                  threads="5" if owner_state == "Zmany" else "1")
        live = ":".join(p for p in ("4242", CODEX_PID, str(os.getpid()),
                                    "" if owner_state == "dead" else owner_pid) if p)
        start = "" if witness == "absent" else " start=111"
        _lock(main, wt, f"flow-claim issue=42 pid={owner_pid} session={owner_session} host={host} "
                        f"ts={NOW - age}{start}")
        env = _scenario_env(proc, caller, live)
        before = _verdict(_helper(BEFORE, "check", str(wt), env=env))
        after = _verdict(_helper(CLAIM, "check", str(wt), env=env))
        seen_before.add(before)
        if before != after:
            flips.add((before, after))
        if before == "self" and after == "stale":
            self_to_stale.append((owner_state, caller, owner_session))
        # `self` is as dangerous as `stale` when it is false: it makes
        # worktree-remove.sh drop the claim AND skip its in-use check. The only
        # true one is a caller whose own session id the claim carries.
        own = caller.startswith("codex") and owner_session == "thread-a"
        if before in PROTECTED and after == "self" and not own:
            moved.append(f"pid={owner_pid}/{owner_state}/{witness}/owner={owner_session}/"
                         f"caller={caller}: {before} -> a FALSE self")
        if before in PROTECTED and after == "stale":
            moved.append(f"pid={owner_pid}/{owner_state}/{witness}/{age}s/{host}/"
                         f"owner={owner_session}/caller={caller}: {before} -> {after}")
    assert n == 1350

    # The states that are not claims at all.
    env = _scenario_env(tmp_path / "proc-1", "claude", "4242")
    _lock(main, wt, "someone locked this by hand")
    assert _verdict(_helper(BEFORE, "check", str(wt), env=env)) == "foreign"
    assert _verdict(_helper(CLAIM, "check", str(wt), env=env)) == "foreign"
    for path, word in ((tmp_path / "nowhere", "unknown"), (main, "unsupported")):
        assert _verdict(_helper(BEFORE, "check", str(path), env=env)) == word
        assert _verdict(_helper(CLAIM, "check", str(path), env=env)) == word
    _git(main, "worktree", "unlock", str(wt))
    assert _verdict(_helper(CLAIM, "check", str(wt), env=env)) == "free"

    assert not moved, "a claim moved TOWARDS stale:\n" + "\n".join(moved)
    # The matrix must be able to show a difference, and must have exercised
    # the protected states, or the assertion above proves nothing.
    assert {"held", "stale", "self"} <= seen_before, seen_before
    assert ("stale", "held") in flips, f"the matrix never produced the intended flip: {flips}"
    # One other move ends at stale, and it is not a live owner being misread:
    # a Codex caller whose claim names its own PARENT, where that parent is
    # posed as an exited single-thread zombie. A process cannot be running as
    # the child of a parent in that state, so the row is reachable only in this
    # matrix. It is listed, not hidden, and pinned to exactly that shape.
    assert {before for before, after in flips if after == "stale"} <= {"self"}, flips
    assert self_to_stale, "expected the unreachable self row; the matrix changed shape"
    assert {(state, caller) for state, caller, _s in self_to_stale} == {("Z1", "codex")}, self_to_stale
