"""Owner-approved re-registration transitions (#1762), across three cwd shapes.

Omitted issue/repo values are retained. Work moves refuse unconsented loss;
explicit reset consent keeps its own acceptance cases. Every case starts with
a nonzero overtake count and an active lane/observation.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

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

#: Where a case's role starts, unless the case says otherwise. `{repo}`, `{wt}`
#: and the other places are filled in from the fixture, so no test interpolates
#: a path it does not own.
START_ISSUE = "1710"
START_REPO = "{repo}"


def _lane(issue: str = START_ISSUE, repo: str = START_REPO) -> tuple[str, ...]:
    """The lane description a registration repeats; an empty value is OMITTED."""
    flags: tuple[str, ...] = ("--cwd", "{wt}", "--branch", "issue-1710-x")
    if repo:
        flags = ("--repo", repo, *flags)
    if issue:
        flags = (*flags, "--issue", issue)
    return flags


def _first(issue: str, repo: str) -> tuple[str, ...]:
    """The fully-declared first registration."""
    return (
        *_lane(issue, repo), "--driver", "flow:auto", "--model", "opus",
        "--permission-mode", "bypassPermissions", "--capacity", "2",
        "--files", "a.py,b.py", "--pr", "55", "--base", "base-1", "--diff", "diff-1",
    )


def _overtake(issue: str, repo: str) -> tuple[str, ...]:
    """The same PR seen again on a new base with the same diff: one overtake."""
    return (*_lane(issue, repo), "--pr", "55", "--base", "base-2", "--diff", "diff-1")


#: What the role reads back as once it has been registered and overtaken once.
#: A case's expectation is this table with only the fields that case changes.
BASE_STATE = {
    "CWD": "{wt}", "REPO": "{repo}", "ISSUE": "1710", "BRANCH": "issue-1710-x",
    "MODEL": "opus", "PERMISSION_MODE": "bypassPermissions", "CAPACITY": "2",
    "DRIVER": "flow:auto", "FILES": "a.py,b.py",
    "pr": "55", "base": "base-2", "diff": "diff-1", "obs_repo": "{repo}",
    "overtaken": 1,
    # register's own lines for the registration under test, and its stderr notice
    "FILES_DROPPED": "-", "FILES_ADDED": "-", "dropped_notice": False,
}

SAME_LANE = _lane()

#: A move to other work: the lane and the merge observation reset.
MOVED = {
    "FILES": "-", "FILES_DROPPED": "a.py,b.py", "dropped_notice": True,
    "pr": "", "base": "", "diff": "", "obs_repo": "", "overtaken": 0,
}


class Case(NamedTuple):
    """One re-registration: its flags and the fields it changes from BASE_STATE.

    `setup` is re-registrations run AFTER the overtake and before the call
    under test (a re-brief that clears the issue, say). `start_issue` and
    `start_repo` are what the role is first registered with; an empty one is
    omitted from the first registration and from the overtake.
    """

    flags: tuple[str, ...]
    changes: dict[str, object]
    setup: tuple[tuple[str, ...], ...] = ()
    start_issue: str = START_ISSUE
    start_repo: str = START_REPO
    refused: bool = False


CASES: dict[str, Case] = {
    # --- the lane is KEPT -------------------------------------------------
    "same issue, no --files": Case(SAME_LANE, {}),
    "nothing but the role": Case(
        (), {"CWD": "-", "REPO": "-", "ISSUE": "-", "BRANCH": "-"}
    ),
    "--repo alone, no --issue": Case(
        ("--repo", "{repo}"), {"CWD": "-", "ISSUE": "-", "BRANCH": "-"}
    ),
    "the lane without --repo": Case(_lane(repo=""), {"REPO": "-"}),
    "a different --branch": Case(
        ("--repo", "{repo}", "--cwd", "{wt}", "--issue", "1710", "--branch", "other-branch"),
        {"BRANCH": "other-branch"},
    ),
    "a different --cwd": Case(
        ("--repo", "{repo}", "--cwd", "{plain}", "--issue", "1710", "--branch", "issue-1710-x"),
        {"CWD": "{plain}"},
    ),
    # --- a different --issue is a MOVE (#1222) -----------------------------
    "a different --issue": Case(
        ("--repo", "{repo}", "--issue", "1711"),
        {**MOVED, "CWD": "-", "ISSUE": "1711", "BRANCH": "-"},
    ),
    "a different --issue with --cwd and --branch": Case(
        _lane(issue="1711"), {**MOVED, "ISSUE": "1711"}
    ),
    "a different --issue with a new observation": Case(
        ("--repo", "{repo}", "--issue", "1711", "--pr", "77", "--base", "base-9", "--diff", "diff-9"),
        {**MOVED, "CWD": "-", "ISSUE": "1711", "BRANCH": "-",
         "pr": "77", "base": "base-9", "diff": "diff-9", "obs_repo": "{repo}"},
    ),
    "a different --issue repeating the same PR on a new base": Case(
        # The move wins over the overtake rule: the count restarts at zero.
        ("--repo", "{repo}", "--issue", "1711", "--pr", "55", "--base", "base-3", "--diff", "diff-1"),
        {**MOVED, "CWD": "-", "ISSUE": "1711", "BRANCH": "-",
         "pr": "55", "base": "base-3", "diff": "diff-1", "obs_repo": "{repo}"},
    ),
    "a different --issue WITH --files": Case(
        ("--repo", "{repo}", "--issue", "1711", "--files", "c.py"),
        {**MOVED, "CWD": "-", "ISSUE": "1711", "BRANCH": "-",
         "FILES": "c.py", "FILES_ADDED": "c.py"},
    ),
    # --- a different --repo is a MOVE too (#1266) --------------------------
    "a different --repo, same issue": Case(
        _lane(repo="{other}"), {**MOVED, "REPO": "{other}"}
    ),
    "a different --repo WITH --files": Case(
        ("--repo", "{other}", "--issue", "1710", "--files", "a.py,b.py"),
        {**MOVED, "REPO": "{other}", "CWD": "-", "BRANCH": "-",
         "FILES": "a.py,b.py", "FILES_DROPPED": "-", "dropped_notice": False},
    ),
    # --- FROM EMPTY: naming an issue or repo where none is recorded is NOT a
    # --- move, so the lane, the PR and the overtake count all survive ------
    "no --issue at first, then an issue": Case(SAME_LANE, {}, start_issue=""),
    "an --issue after a re-brief cleared it": Case(
        _lane(issue="1711"), {"ISSUE": "1711"}, setup=(_lane(issue=""),)
    ),
    "no --repo at first, then a repo": Case(
        # The observation was recorded with no repo and stays that way.
        SAME_LANE, {"obs_repo": ""}, start_repo=""
    ),
    "a --repo after a re-brief cleared it": Case(
        _lane(repo="{other}"), {"REPO": "{other}"}, setup=(_lane(repo=""),)
    ),
    "issue and repo both cleared, then both different": Case(
        ("--repo", "{other}", "--issue", "1711"),
        {"CWD": "-", "BRANCH": "-", "ISSUE": "1711", "REPO": "{other}"},
        setup=((),),
    ),
    "an --issue cleared, then a different issue in a different repo": Case(
        # The issue side is from-empty, but the REPO side is two non-empty
        # values that differ - which is a move on its own.
        _lane(issue="1711", repo="{other}"),
        {**MOVED, "ISSUE": "1711", "REPO": "{other}"},
        setup=(_lane(issue=""),),
    ),
    # --- explicit changes to one preserved fact ----------------------------
    "--files with an empty value": Case(
        (*SAME_LANE, "--files", ""),
        {"FILES": "-", "FILES_DROPPED": "a.py,b.py", "dropped_notice": True},
    ),
    "a different --model": Case((*SAME_LANE, "--model", "sonnet"), {"MODEL": "sonnet"}),
    "--model with an empty value": Case((*SAME_LANE, "--model", ""), {"MODEL": "-"}),
    "a different --permission-mode": Case(
        (*SAME_LANE, "--permission-mode", "default"), {"PERMISSION_MODE": "default"}
    ),
    "a different --capacity": Case((*SAME_LANE, "--capacity", "5"), {"CAPACITY": "5"}),
    "a different --driver": Case(
        (*SAME_LANE, "--driver", "codex:auto"), {"DRIVER": "codex:auto"}
    ),
    # --- the merge observation and its overtake count -----------------------
    "--clear-pr": Case(
        (*SAME_LANE, "--clear-pr"),
        {"pr": "", "base": "", "diff": "", "obs_repo": "", "overtaken": 0},
    ),
    "the same PR on a new base with the same diff": Case(
        (*SAME_LANE, "--pr", "55", "--base", "base-3", "--diff", "diff-1"),
        {"base": "base-3", "overtaken": 2},
    ),
    "the same PR on the same base with a new diff": Case(
        (*SAME_LANE, "--pr", "55", "--base", "base-2", "--diff", "diff-2"),
        {"diff": "diff-2"},
    ),
    "a different PR, same issue": Case(
        (*SAME_LANE, "--pr", "56", "--base", "base-2", "--diff", "diff-1"),
        {"pr": "56", "overtaken": 0},
    ),
}

# Owner ruling 2026-11-13: omitted identity is kept, and incomplete moves refuse.
for _name, _case in list(CASES.items()):
    if _name.startswith(("a different --issue", "a different --repo")) or _name in {
        "no --issue at first, then an issue", "an --issue after a re-brief cleared it",
        "no --repo at first, then a repo", "a --repo after a re-brief cleared it",
        "issue and repo both cleared, then both different",
        "an --issue cleared, then a different issue in a different repo",
    }:
        CASES[_name] = _case._replace(changes={}, refused=True)
CASES["nothing but the role"] = Case((), {"CWD": "-", "BRANCH": "-"})
CASES["--repo alone, no --issue"] = Case(("--repo", "{repo}"), {"CWD": "-", "BRANCH": "-"})
CASES["the lane without --repo"] = Case(_lane(repo=""), {})
CASES["move with explicit reset consent"] = Case(
    (*_lane(issue="1711"), "--allow-work-reset"), {**MOVED, "ISSUE": "1711"},
)
CASES["move with explicit empty lane and cleared observation"] = Case(
    (*_lane(issue="1711"), "--files", "", "--clear-pr"), {**MOVED, "ISSUE": "1711"},
)
CASES["move with both restated"] = Case(
    (*_lane(issue="1711"), "--files", "c.py", "--pr", "55", "--base", "base-3", "--diff", "diff-1"),
    {**MOVED, "ISSUE": "1711", "FILES": "c.py", "FILES_ADDED": "c.py",
     "pr": "55", "base": "base-3", "diff": "diff-1", "obs_repo": "{repo}"},
)

GET_FIELDS = (
    "CWD", "REPO", "ISSUE", "BRANCH", "MODEL", "PERMISSION_MODE", "CAPACITY",
    "DRIVER", "FILES",
)
STORED_FIELDS = ("pr", "base", "diff", "obs_repo", "overtaken")


def _git(where: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git for the FIXTURE, with the host's hooks switched off.

    A developer's `core.hooksPath`, or hooks copied in from a template
    directory, would otherwise run inside this throwaway repository on commit
    and on `worktree add` - the host deciding what a fixture does.
    """
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(where), *args],
        capture_output=True, text=True, check=False,
    )


@pytest.fixture(scope="module")
def places(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """A main checkout, a linked worktree of it, a second repository, and a
    plain directory outside any repository - each shape asserted, not assumed."""
    top = tmp_path_factory.mktemp("reregister").resolve()
    repo, wt, other, plain = top / "repo", top / "wt", top / "other", top / "plain"
    template = top / "empty-template"
    for d in (repo, other, plain, template):
        d.mkdir()
    for d in (repo, other):
        made = _git(d, "init", "-q", "-b", "main", f"--template={template}")
        assert made.returncode == 0, made.stderr
        # An empty template leaves no hooks directory behind at all.
        assert not (d / ".git" / "hooks").exists(), sorted((d / ".git" / "hooks").iterdir())
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


def _args(flags: tuple[str, ...], places: dict[str, Path]) -> list[str]:
    return [str(_fill(a, places)) for a in flags]


def _stored(tmp: Path) -> dict[str, object]:
    registry = json.loads((tmp / "reg" / "registry.json").read_text(encoding="utf-8"))
    return registry[WAVE]["roles"][ROLE]


def _state(tmp: Path, registered: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """Every tracked field after a registration: `get`'s lines, the stored
    merge observation, and what `register` itself said about the lane."""
    got = _run(tmp, "get", ROLE, "--wave", WAVE)
    assert got.returncode == 0, got.stderr
    entry = _stored(tmp)
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
@pytest.mark.parametrize("name", sorted(CASES))
def test_a_reregistration_changes_only_what_the_table_says(
    tmp_path: Path, places: dict[str, Path], run_from: str, name: str
) -> None:
    case = CASES[name]
    cwd = places[run_from]

    def register(flags: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        done = _run(tmp_path, "register", ROLE, "--wave", WAVE, *_args(flags, places), cwd=cwd)
        assert done.returncode == 0, done.stderr
        return done

    first = register(_first(case.start_issue, case.start_repo))
    assert _verdict(first) == "registered", first.stdout
    register(_overtake(case.start_issue, case.start_repo))
    for step in case.setup:
        register(step)

    # PRECONDITION, read from the stored entry just before the call under
    # test: the role really holds a lane, a PR and a NONZERO overtake count.
    # Without this a "dropped" below could be a field that never arrived, and
    # an `overtaken` of 0 could not tell a reset from a count never raised.
    before = _stored(tmp_path)
    assert before["files"] == "a.py,b.py", before
    assert (before["pr"], before["base"], before["diff"]) == ("55", "base-2", "diff-1"), before
    assert before["overtaken"] == 1, before
    # ...and it is in the issue/repo state this case is ABOUT: a from-empty
    # case must really start from an empty value.
    assert before["issue"] == case.start_issue, before
    assert before["repo"] == _fill(case.start_repo, places), before

    original = (tmp_path / "reg/registry.json").read_bytes()
    again = _run(tmp_path, "register", ROLE, "--wave", WAVE, *_args(case.flags, places), cwd=cwd)
    if case.refused:
        assert again.returncode == 1 and _verdict(again) == "refused", again.stdout + again.stderr
        assert (tmp_path / "reg/registry.json").read_bytes() == original
        return
    assert again.returncode == 0 and _verdict(again) == "updated", again.stdout + again.stderr

    expected = {k: _fill(v, places) for k, v in {**BASE_STATE, **case.changes}.items()}
    after = _state(tmp_path, again)
    differing = {k: (after[k], expected[k]) for k in expected if after[k] != expected[k]}
    assert not differing, f"{name!r} from {run_from}: (actual, expected) {differing}"


@requires_tools
def test_the_table_is_two_sided_for_the_lane_and_for_the_count() -> None:
    """The matrix must hold cases on BOTH sides of each rule it pins.

    A table of nothing but preserved lanes would pass against a registry that
    could never reset one, and the reverse; the same goes for the overtake
    count, and for the from-empty transitions against the real moves. This
    keeps each pair of populations from quietly becoming one.
    """
    def overtaken(case: Case) -> object:
        return case.changes.get("overtaken", BASE_STATE["overtaken"])

    kept = [n for n, c in CASES.items() if "FILES" not in c.changes]
    dropped = [n for n, c in CASES.items() if c.changes.get("FILES_DROPPED") == "a.py,b.py"]
    assert len(kept) >= 5, kept
    assert len(dropped) >= 3, dropped

    count_kept = [n for n, c in CASES.items() if overtaken(c) == 1]
    count_reset = [n for n, c in CASES.items() if overtaken(c) == 0]
    count_raised = [n for n, c in CASES.items() if overtaken(c) == 2]
    assert len(count_kept) >= 5, count_kept
    assert len(count_reset) >= 3, count_reset
    assert count_raised, "no case raises the overtake count"

    from_empty = [n for n, c in CASES.items() if c.setup or not c.start_issue or not c.start_repo]
    from_empty_kept = [n for n in from_empty if overtaken(CASES[n]) == 1]
    assert len(from_empty_kept) >= 4, from_empty_kept
    assert any(CASES[n].refused for n in from_empty), "no from-empty move refusal"
