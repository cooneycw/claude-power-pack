"""What a re-registration does to EVERY field, one change at a time (issue #1691).

A CHARACTERIZATION test: it asserts what `scripts/flow-wave-registry.sh
register` does today, measured by running it, so a later change to any of
these rules is a visible, deliberate edit to a table rather than a surprise in
a live wave.

`/flow:wave` and `/flow:register` said flatly that `--files` is PRESERVED by a
re-register. It is, with one deliberate exception (issue #1222, extended to
repositories by #1266): a re-register naming a DIFFERENT `--issue`, or a
different `--repo`, is a move to other work, and the preserved lane facts -
the file lane and the merge observation (PR, base, diff, overtaken) - reset
unless that same call supplies them. The registry reports the reset as
`FLOW_WAVE_FILES_DROPPED` and on stderr. Omitting `--issue` is not a move.

The rules the table below pins:

- `--cwd`, `--repo`, `--issue` and `--branch` are REWRITTEN by every
  re-register, to empty when omitted.
- `--model`, `--permission-mode`, `--capacity` and `--driver` are preserved
  when omitted and never reset by a move; an explicit empty value clears one.
- `--files` is preserved when omitted, replaced when given (an explicit empty
  value clears it), and reset by a move unless the same call passes it.
- The merge observation is preserved when omitted, replaced by a complete
  `--pr/--base/--diff`, withdrawn by `--clear-pr`, and reset by a move unless
  the same call supplies one.

Each case starts from the same fully-declared role and is run from three
working directories - the fixture's main checkout, a linked worktree of it,
and a plain directory outside any repository - because `register` takes its
lane from its flags and must answer the same wherever it is run.

`get` is the read-back for the fields it prints. It does not print the merge
observation, so those five fields are read from the stored entry.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_flow_wave_registry import _detail, _run, _verdict

# Drives the real registry under `bash` (which needs `jq` and `flock`), and
# builds a real checkout plus a linked worktree with `git`.
requires_tools = pytest.mark.skipif(
    shutil.which("bash") is None
    or shutil.which("jq") is None
    or shutil.which("flock") is None
    or shutil.which("git") is None,
    reason="requires bash, jq, flock and git on PATH",
)

WAVE = "reregister-matrix"
ROLE = "w1"

#: The role every case starts from. `{repo}` and `{wt}` are filled in from the
#: fixture, so no test interpolates a path it does not own.
BASE_ARGS = (
    "--repo", "{repo}", "--cwd", "{wt}", "--issue", "1710",
    "--branch", "issue-1710-x", "--driver", "flow:auto", "--model", "opus",
    "--permission-mode", "bypassPermissions", "--capacity", "2",
    "--files", "a.py,b.py", "--pr", "55", "--base", "base-1", "--diff", "diff-1",
)

#: What the base registration reads back as. A case's expectation is this
#: table with only the fields that case is expected to change.
BASE_STATE = {
    "CWD": "{wt}", "REPO": "{repo}", "ISSUE": "1710", "BRANCH": "issue-1710-x",
    "MODEL": "opus", "PERMISSION_MODE": "bypassPermissions", "CAPACITY": "2",
    "DRIVER": "flow:auto", "FILES": "a.py,b.py",
    "pr": "55", "base": "base-1", "diff": "diff-1", "obs_repo": "{repo}",
    "overtaken": 0,
    # register's own lines for the RE-registration, and its stderr notice
    "FILES_DROPPED": "-", "FILES_ADDED": "-", "dropped_notice": False,
}

#: The lane description a routine re-brief repeats.
SAME_LANE = (
    "--repo", "{repo}", "--cwd", "{wt}", "--issue", "1710", "--branch", "issue-1710-x",
)

#: A move to other work: the lane and the merge observation reset.
MOVED = {
    "FILES": "-", "FILES_DROPPED": "a.py,b.py", "dropped_notice": True,
    "pr": "", "base": "", "diff": "", "obs_repo": "", "overtaken": 0,
}

#: name -> (the re-register's flags, the fields it changes)
CASES: dict[str, tuple[tuple[str, ...], dict[str, object]]] = {
    # --- the lane is KEPT -------------------------------------------------
    "same issue, no --files": (SAME_LANE, {}),
    "nothing but the role": (
        (),
        {"CWD": "-", "REPO": "-", "ISSUE": "-", "BRANCH": "-"},
    ),
    "--repo alone, no --issue": (
        ("--repo", "{repo}"),
        {"CWD": "-", "ISSUE": "-", "BRANCH": "-"},
    ),
    "a different --branch": (
        ("--repo", "{repo}", "--cwd", "{wt}", "--issue", "1710", "--branch", "other-branch"),
        {"BRANCH": "other-branch"},
    ),
    "a different --cwd": (
        ("--repo", "{repo}", "--cwd", "{plain}", "--issue", "1710", "--branch", "issue-1710-x"),
        {"CWD": "{plain}"},
    ),
    # --- a different --issue is a MOVE (#1222) -----------------------------
    "a different --issue": (
        ("--repo", "{repo}", "--issue", "1711"),
        {**MOVED, "CWD": "-", "ISSUE": "1711", "BRANCH": "-"},
    ),
    "a different --issue with --cwd and --branch": (
        ("--repo", "{repo}", "--cwd", "{wt}", "--issue", "1711", "--branch", "issue-1711-y"),
        {**MOVED, "ISSUE": "1711", "BRANCH": "issue-1711-y"},
    ),
    "a different --issue with a new observation": (
        ("--repo", "{repo}", "--issue", "1711", "--pr", "77", "--base", "base-9", "--diff", "diff-9"),
        {**MOVED, "CWD": "-", "ISSUE": "1711", "BRANCH": "-",
         "pr": "77", "base": "base-9", "diff": "diff-9", "obs_repo": "{repo}"},
    ),
    "a different --issue WITH --files": (
        ("--repo", "{repo}", "--issue", "1711", "--files", "c.py"),
        {**MOVED, "CWD": "-", "ISSUE": "1711", "BRANCH": "-",
         "FILES": "c.py", "FILES_ADDED": "c.py"},
    ),
    # --- a different --repo is a MOVE too (#1266) --------------------------
    "a different --repo, same issue": (
        ("--repo", "{other}", "--cwd", "{wt}", "--issue", "1710", "--branch", "issue-1710-x"),
        {**MOVED, "REPO": "{other}"},
    ),
    "a different --repo WITH --files": (
        ("--repo", "{other}", "--issue", "1710", "--files", "a.py,b.py"),
        {**MOVED, "REPO": "{other}", "CWD": "-", "BRANCH": "-",
         "FILES": "a.py,b.py", "FILES_DROPPED": "-", "dropped_notice": False},
    ),
    # --- explicit changes to one preserved fact ----------------------------
    "--files with an empty value": (
        (*SAME_LANE, "--files", ""),
        {"FILES": "-", "FILES_DROPPED": "a.py,b.py", "dropped_notice": True},
    ),
    "a different --model": ((*SAME_LANE, "--model", "sonnet"), {"MODEL": "sonnet"}),
    "--model with an empty value": ((*SAME_LANE, "--model", ""), {"MODEL": "-"}),
    "a different --permission-mode": (
        (*SAME_LANE, "--permission-mode", "default"),
        {"PERMISSION_MODE": "default"},
    ),
    "a different --capacity": ((*SAME_LANE, "--capacity", "5"), {"CAPACITY": "5"}),
    "a different --driver": ((*SAME_LANE, "--driver", "codex:auto"), {"DRIVER": "codex:auto"}),
    # --- the merge observation ---------------------------------------------
    "--clear-pr": (
        (*SAME_LANE, "--clear-pr"),
        {"pr": "", "base": "", "diff": "", "obs_repo": "", "overtaken": 0},
    ),
    "the same PR on a new base with the same diff": (
        (*SAME_LANE, "--pr", "55", "--base", "base-2", "--diff", "diff-1"),
        {"base": "base-2", "overtaken": 1},
    ),
}

GET_FIELDS = (
    "CWD", "REPO", "ISSUE", "BRANCH", "MODEL", "PERMISSION_MODE", "CAPACITY",
    "DRIVER", "FILES",
)
STORED_FIELDS = ("pr", "base", "diff", "obs_repo", "overtaken")


def _git(where: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(where), *args], capture_output=True, text=True, check=False
    )


@pytest.fixture(scope="module")
def places(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """A main checkout, a linked worktree of it, a second repository, and a
    plain directory outside any repository - each shape asserted, not assumed."""
    top = tmp_path_factory.mktemp("reregister").resolve()
    repo, wt, other, plain = top / "repo", top / "wt", top / "other", top / "plain"
    for d in (repo, other, plain):
        d.mkdir()
    for d in (repo, other):
        assert _git(d, "init", "-q", "-b", "main").returncode == 0
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert _git(repo, "add", "a.py").returncode == 0
    committed = _git(
        repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init",
    )
    assert committed.returncode == 0, committed.stderr
    added = _git(repo, "worktree", "add", "-q", "-b", "issue-1710-x", str(wt))
    assert added.returncode == 0, added.stderr

    # The three shapes this test claims to run from, checked before any case.
    main_dir = _git(repo, "rev-parse", "--absolute-git-dir").stdout.strip()
    wt_dir = _git(wt, "rev-parse", "--absolute-git-dir").stdout.strip()
    assert main_dir == str(repo / ".git"), main_dir
    assert "/worktrees/" in wt_dir, f"{wt} is not a LINKED worktree: {wt_dir}"
    outside = _git(plain, "rev-parse", "--is-inside-work-tree")
    assert outside.returncode != 0, f"{plain} is inside a repository: {outside.stdout}"
    return {"repo": repo, "wt": wt, "other": other, "plain": plain}


def _fill(value: object, places: dict[str, Path]) -> object:
    return value.format(**places) if isinstance(value, str) else value


def _state(tmp: Path, registered: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """Every tracked field after a registration: `get`'s lines, the stored
    merge observation, and what `register` itself said about the lane."""
    got = _run(tmp, "get", ROLE, "--wave", WAVE)
    assert got.returncode == 0, got.stderr
    stored = json.loads((tmp / "reg" / "registry.json").read_text(encoding="utf-8"))
    entry = stored[WAVE]["roles"][ROLE]
    state: dict[str, object] = {f: _detail(got, f"FLOW_WAVE_{f}") for f in GET_FIELDS}
    state.update({f: entry[f] for f in STORED_FIELDS})
    # `get` and `register` must agree about the lane as now recorded.
    assert _detail(registered, "FLOW_WAVE_FILES") == state["FILES"]
    state["FILES_DROPPED"] = _detail(registered, "FLOW_WAVE_FILES_DROPPED")
    state["FILES_ADDED"] = _detail(registered, "FLOW_WAVE_FILES_ADDED")
    state["dropped_notice"] = " DROPPED " in registered.stderr
    return state


@requires_tools
@pytest.mark.parametrize("run_from", ["repo", "wt", "plain"])
@pytest.mark.parametrize("case", sorted(CASES))
def test_a_reregistration_changes_only_what_the_table_says(
    tmp_path: Path, places: dict[str, Path], run_from: str, case: str
) -> None:
    cwd = places[run_from]
    base_args = [str(_fill(a, places)) for a in BASE_ARGS]

    first = _run(tmp_path, "register", ROLE, "--wave", WAVE, *base_args, cwd=cwd)
    assert _verdict(first) == "registered", first.stderr
    # PRECONDITION: the role really holds everything a case may be said to
    # drop, so a "dropped" below is a drop and not a field that never arrived.
    before = _state(tmp_path, first)
    expected_base = {k: _fill(v, places) for k, v in BASE_STATE.items()}
    assert before == {**expected_base, "FILES_ADDED": "a.py,b.py"}, before

    flags, changes = CASES[case]
    again = _run(
        tmp_path, "register", ROLE, "--wave", WAVE,
        *[str(_fill(a, places)) for a in flags], cwd=cwd,
    )
    assert again.returncode == 0, again.stderr
    assert _verdict(again) == "updated", again.stdout

    expected = {**expected_base, **{k: _fill(v, places) for k, v in changes.items()}}
    after = _state(tmp_path, again)
    differing = {k: (after[k], expected[k]) for k in expected if after[k] != expected[k]}
    assert not differing, f"{case!r} from {run_from}: (actual, expected) {differing}"


@requires_tools
def test_the_table_covers_both_directions_of_the_lane_rule() -> None:
    """The matrix must hold cases that KEEP the lane and cases that DROP it.

    A table of nothing but preserved lanes would pass against a registry that
    could never reset one, and the reverse; this keeps the two populations from
    quietly becoming one.
    """
    kept = [n for n, (_, ch) in CASES.items() if "FILES" not in ch]
    dropped = [n for n, (_, ch) in CASES.items() if ch.get("FILES_DROPPED") == "a.py,b.py"]
    assert len(kept) >= 5, kept
    assert len(dropped) >= 5, dropped
