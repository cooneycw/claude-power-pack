"""Tests for issue #887: a sweep owns worktree teardown.

#887's defect is structural rather than an oversight: in a wave the party that
can remove a worktree has finished by the time the party that discovers it
exists gets there. ``gh pr merge --delete-branch`` deletes the remote branch,
then tries ``git branch -d``; git refuses while a worktree holds the branch and
gh has no notion of worktrees, so the worktree survives holding a branch that no
longer exists on the remote. Measured on cooneycw/kyle after one wave: 33
worktrees, 3.1G, 25 of them holding merged branches.

The decision - a sweep rather than a merge-time hook - and the argument that the
cross-session-mutation objection is DISCHARGED rather than inapplicable are in
``docs/decisions/0006-worktree-teardown-ownership.md``. What this file pins is the
half of that argument the code has to carry:

  * the five-condition test actually gates removal, each condition separately
    (``test_removable_*`` is the positive control; one test per skip reason);
  * every condition that cannot be ESTABLISHED is undecidable, never clean -
    ``pr-unknown`` is not ``pr-none`` and ``occupancy-unknown`` is not ``clear``,
    and either makes the run ``partial``;
  * the population is discovered from git, so a neighbouring repository sharing
    the parent directory is not in it (#627 puts them side by side);
  * the composition contract with #889: the sweep passes neither ``--force`` nor
    ``--steal``, and a refusal from the helper is recorded and left alone rather
    than retried or overridden. A teardown that routed around exit 5 in a loop
    over every worktree on a host would reopen the data-loss path #889 closed.

What a green run here does NOT prove, stated so nobody reads it as more:

  * It does not prove the sweep is RUN. ``/flow:cleanup`` and ``/flow:wave``
    Phase 3 invoke it; nothing here executes those documents.
  * It does not cover a real GitHub. ``gh`` is a stub emulating the one call the
    sweep makes. A change to that call's shape is invisible here.
  * ``test_gitignored_state_is_invisible_to_every_condition`` pins a known blind
    spot as a property rather than a TODO: gitignored local state is not work by
    any of the five conditions, and the sweep removes it with the worktree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "scripts" / "flow-worktree-sweep.sh"
REMOVE = ROOT / "scripts" / "worktree-remove.sh"

# Same constraint as tests/test_worktree_remove_occupied.py: the Woodpecker
# `validate` step runs in a slim image with bash but no git.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

# The occupancy signal is /proc-based, so those cases are Linux-only. Skipping is
# honest: without /proc the scan genuinely cannot run, and
# test_occupancy_unscannable_is_undecidable_not_clear pins that degradation.
requires_proc = pytest.mark.skipif(
    not Path("/proc/self/cwd").exists(),
    reason="occupancy detection reads /proc (Linux only)",
)


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout


def _repo(tmp_path: Path, name: str = "main") -> Path:
    main = tmp_path / name
    main.mkdir(parents=True)
    _git(main, "init", "-q", "-b", "main")
    (main / "base.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    # The slug parser reads this; without it every PR lookup is `pr-unknown`.
    _git(main, "remote", "add", "origin", "https://github.com/acme/widget.git")
    return main


def _add_worktree(main: Path, path: Path, branch: str) -> Path:
    _git(main, "worktree", "add", "-q", str(path), "-b", branch)
    return path


def _tip(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").strip()


def _fake_gh(bindir: Path) -> Path:
    """A `gh` that answers the one query the sweep makes, from FAKE_GH_ROWS.

    FAKE_GH_ROWS maps a branch name to rows exactly as
    `gh pr list --jq '.[] | [.state, .headRefOid, (.number|tostring)] | join("|")'`
    emits them: "STATE|OID|NUMBER", one per line, empty for a branch with no PR.
    Branch entries are separated by ';', a branch from its rows by '=', and rows
    from each other by '~'.

    FAKE_GH_EXIT makes the query fail, which is the `pr-unknown` lane - a gh that
    is missing, unauthenticated, rate-limited or offline.
    """
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "rc = int(os.environ.get('FAKE_GH_EXIT', '0'))\n"
        "if rc:\n"
        "    sys.stderr.write('boom\\n'); sys.exit(rc)\n"
        "branch = ''\n"
        "argv = sys.argv[1:]\n"
        "for i, a in enumerate(argv):\n"
        "    if a == '--head' and i + 1 < len(argv):\n"
        "        branch = argv[i + 1]\n"
        "rows = {}\n"
        "for chunk in os.environ.get('FAKE_GH_ROWS', '').split(';'):\n"
        "    if not chunk:\n"
        "        continue\n"
        "    k, _, v = chunk.partition('=')\n"
        "    rows[k] = v\n"
        "out = rows.get(branch, '')\n"
        "if out:\n"
        "    sys.stdout.write(out.replace('~', '\\n') + '\\n')\n"
        "sys.exit(0)\n"
    )
    gh.chmod(0o755)
    return gh


def _run_sweep(
    repo: Path,
    *args: str,
    bindir: Path | None = None,
    env: dict[str, str] | None = None,
    script: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if bindir is not None:
        run_env["PATH"] = f"{bindir}{os.pathsep}{run_env['PATH']}"
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(script or SWEEP), "--repo", str(repo), *args],
        env=run_env,
        cwd=str(repo),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )


def _dispositions(out: str) -> dict[str, str]:
    """path -> "<disposition> <detail>" for every SWEEP_WORKTREE line."""
    found = {}
    for line in out.splitlines():
        if line.startswith("SWEEP_WORKTREE: "):
            _, _, rest = line.partition("SWEEP_WORKTREE: ")
            path, _, disp = rest.partition(" ")
            found[path] = disp
    return found


def _status(res: subprocess.CompletedProcess[str]) -> str:
    for line in (res.stdout + res.stderr).splitlines():
        if line.startswith("FLOW_WORKTREE_SWEEP: "):
            return line.split(": ", 1)[1].strip()
    raise AssertionError(
        f"no FLOW_WORKTREE_SWEEP status line\nstdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )


@pytest.fixture()
def occupant():
    """A real long-lived process whose cwd is a given directory.

    Real rather than a synthetic /proc tree, for the reason
    tests/test_worktree_remove_occupied.py gives: a hand-built tree would only
    prove the matcher agrees with the author's idea of what /proc looks like.
    """
    procs: list[subprocess.Popen] = []

    def _spawn(cwd: Path) -> subprocess.Popen:
        p = subprocess.Popen(
            ["sleep", "60"], cwd=str(cwd),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 5
        link = Path(f"/proc/{p.pid}/cwd")
        while time.time() < deadline:
            try:
                if link.resolve() == cwd.resolve():
                    break
            except OSError:
                pass
            time.sleep(0.02)
        procs.append(p)
        return p

    yield _spawn
    for p in procs:
        p.kill()
        p.wait()


# --------------------------------------------------------------------------
# Positive control: the sweep can fire at all.
# --------------------------------------------------------------------------


@requires_git
@requires_proc
def test_merged_clean_idle_worktree_is_removable_and_removed(tmp_path: Path) -> None:
    """All five conditions pass -> reported removable, and --apply removes it.

    Without this the whole file could pass while the sweep removed nothing ever,
    which is question 1 of the detector contract in the tests rather than in the
    code.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-1", "issue-1")
    rows = {"issue-1": f"MERGED|{_tip(wt)}|1"}
    bindir = tmp_path / "bin"
    _fake_gh(bindir)
    env = {"FAKE_GH_ROWS": ";".join(f"{k}={v}" for k, v in rows.items())}

    dry = _run_sweep(main, bindir=bindir, env=env)
    assert _status(dry) == "ok", dry.stdout + dry.stderr
    assert _dispositions(dry.stdout)[str(wt)].startswith("removable"), dry.stdout
    assert wt.exists(), "a dry run must not remove anything"

    applied = _run_sweep(main, "--apply", bindir=bindir, env=env)
    assert _status(applied) == "ok", applied.stdout + applied.stderr
    assert _dispositions(applied.stdout)[str(wt)].startswith("removed"), applied.stdout
    assert not wt.exists()
    assert "issue-1" not in _git(main, "branch", "--list", "issue-1")


# --------------------------------------------------------------------------
# One test per condition in the five-condition test.
# --------------------------------------------------------------------------


@requires_git
@requires_proc
def test_dirty_worktree_is_skipped(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-2", "issue-2")
    (wt / "unsaved.md").write_text("work that exists nowhere else\n")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={"FAKE_GH_ROWS": f"issue-2=MERGED|{_tip(wt)}|2"},
    )

    assert _dispositions(res.stdout)[str(wt)].startswith("skip dirty"), res.stdout
    assert wt.exists()
    assert (wt / "unsaved.md").read_text() == "work that exists nowhere else\n"


@requires_git
@requires_proc
def test_unpushed_commit_is_skipped(tmp_path: Path) -> None:
    """A commit the PR head does not carry is local-only work, not a merge."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-3", "issue-3")
    merged_oid = _tip(wt)
    (wt / "later.md").write_text("committed here and nowhere else\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "local only")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={"FAKE_GH_ROWS": f"issue-3=MERGED|{merged_oid}|3"},
    )

    assert _dispositions(res.stdout)[str(wt)].startswith("skip unpushed"), res.stdout
    assert wt.exists()


@requires_git
@requires_proc
def test_locked_worktree_is_skipped_without_reaching_the_helper(tmp_path: Path) -> None:
    """A #597 claim IS a git worktree lock, so the sweep never needs --steal."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-4", "issue-4")
    _git(main, "worktree", "lock", str(wt), "--reason", "flow-claim pid 1234")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={"FAKE_GH_ROWS": f"issue-4=MERGED|{_tip(wt)}|4"},
    )

    assert _dispositions(res.stdout)[str(wt)] == "skip locked", res.stdout
    assert wt.exists()


@requires_git
@requires_proc
def test_occupied_worktree_is_skipped_even_though_it_is_clean(tmp_path: Path, occupant) -> None:
    """Stricter than worktree-remove.sh, deliberately.

    The helper removes an occupied-but-clean worktree because there is nothing
    unrecoverable to lose, which is right for a caller who named that one path.
    The sweep is choosing its own targets and pays nothing to leave one alone.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-5", "issue-5")
    occupant(wt)
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={"FAKE_GH_ROWS": f"issue-5=MERGED|{_tip(wt)}|5"},
    )

    assert _dispositions(res.stdout)[str(wt)].startswith("skip occupied"), res.stdout
    assert wt.exists()


@requires_git
@requires_proc
def test_open_pr_is_skipped(tmp_path: Path) -> None:
    """The worktree must survive review feedback; several PRs took three pushes."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-6", "issue-6")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={"FAKE_GH_ROWS": f"issue-6=OPEN|{_tip(wt)}|6"},
    )

    assert _dispositions(res.stdout)[str(wt)].startswith("skip pr-open"), res.stdout
    assert wt.exists()


@requires_git
@requires_proc
def test_an_open_pr_outranks_an_earlier_merged_one(tmp_path: Path) -> None:
    """Reopened/second PR on the same head: the open one decides."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-7", "issue-7")
    tip = _tip(wt)
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={"FAKE_GH_ROWS": f"issue-7=MERGED|{tip}|7~OPEN|{tip}|8"},
    )

    assert _dispositions(res.stdout)[str(wt)].startswith("skip pr-open"), res.stdout
    assert wt.exists()


# --------------------------------------------------------------------------
# The two skips that mattered on the measured host.
# --------------------------------------------------------------------------


@requires_git
@requires_proc
def test_a_branch_with_no_pr_is_skipped_not_swept(tmp_path: Path) -> None:
    """The preserved-WIP and wayfinder-research case.

    Two of the skips on the measured host were a deliberately preserved WIP
    branch and a wayfinder research branch, which by design never gets a PR. A
    sweep keyed on "no PR" would have destroyed both, so `pr-none` is a skip and
    never a reason to remove.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-wayfinder-map", "wayfinder-map")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(main, "--apply", bindir=bindir, env={"FAKE_GH_ROWS": ""})

    assert _dispositions(res.stdout)[str(wt)] == "skip pr-none", res.stdout
    assert wt.exists()
    assert _status(res) == "nothing-to-do"


@requires_git
@requires_proc
def test_pr_unknown_is_not_pr_none_and_makes_the_run_partial(tmp_path: Path) -> None:
    """"I asked and there is no PR" and "I could not ask" are different facts.

    Both are skips, so conflating them loses no worktree - it loses the sweep's
    ability to say whether it classified the tree at all, which is the claim the
    summary line makes.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-8", "issue-8")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(main, "--apply", bindir=bindir, env={"FAKE_GH_EXIT": "1"})

    disp = _dispositions(res.stdout)[str(wt)]
    assert disp.startswith("undecidable pr-unknown"), res.stdout
    assert "pr-none" not in disp
    assert _status(res) == "partial"
    assert res.returncode == 3, "partial must be distinguishable by exit code"
    assert wt.exists()


@requires_git
@requires_proc
def test_a_non_github_remote_is_undecidable_not_clean(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    _git(main, "remote", "set-url", "origin", "https://git.example.com/acme/widget.git")
    wt = _add_worktree(main, tmp_path / "widget-issue-9", "issue-9")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(main, "--apply", bindir=bindir, env={"FAKE_GH_ROWS": ""})

    assert "undecidable pr-unknown" in _dispositions(res.stdout)[str(wt)], res.stdout
    assert _status(res) == "partial"
    assert wt.exists()


# --------------------------------------------------------------------------
# Membership floor and ownership boundary.
# --------------------------------------------------------------------------


@requires_git
def test_no_linked_worktrees_reports_no_candidates_not_a_clean_sweep(tmp_path: Path) -> None:
    """An empty population must be its own state.

    `nothing-to-do` over zero worktrees would be a universal claim about a set
    never shown to be non-empty - the detector contract's question 1.
    """
    main = _repo(tmp_path)
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(main, bindir=bindir, env={"FAKE_GH_ROWS": ""})

    assert _status(res) == "no-candidates", res.stdout
    assert "candidates=0" in res.stdout
    assert res.returncode == 0


@requires_git
@requires_proc
def test_a_neighbouring_repository_is_not_in_the_population(tmp_path: Path) -> None:
    """Ownership boundary: the population comes from git, never from a glob.

    #627 puts worktrees beside the repo as `<parent>/<repo>-<branch>`, so an
    unrelated checkout sits in the same directory. `git worktree list` reports
    only worktrees registered to THIS repository; a path glob could not tell the
    two apart.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-10", "issue-10")
    stranger = _repo(tmp_path, name="widget-issue-11")   # same parent, different repo
    (stranger / "precious.md").write_text("not ours\n")
    _git(stranger, "add", "-A")
    _git(stranger, "commit", "-qm", "precious")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={"FAKE_GH_ROWS": f"issue-10=MERGED|{_tip(wt)}|10;main=MERGED|deadbeef|11"},
    )

    seen = _dispositions(res.stdout)
    assert str(stranger) not in seen, f"swept a neighbouring repository: {res.stdout}"
    assert (stranger / "precious.md").exists()
    assert "candidates=1" in res.stdout


@requires_git
@requires_proc
def test_the_main_worktree_is_never_a_candidate(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    _add_worktree(main, tmp_path / "widget-issue-12", "issue-12")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)

    res = _run_sweep(main, "--apply", bindir=bindir, env={"FAKE_GH_ROWS": ""})

    assert str(main) not in _dispositions(res.stdout), res.stdout
    assert main.exists()


@requires_git
def test_occupancy_unscannable_is_undecidable_not_clear(tmp_path: Path) -> None:
    """Unchecked must never render as clean.

    Reached through the FLOW_WORKTREE_SWEEP_PROC_ROOT seam, which exists so this
    lane is testable on a host with a perfectly good /proc. Nothing in normal
    operation sets it.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-13", "issue-13")
    bindir = tmp_path / "bin"
    _fake_gh(bindir)
    empty_proc = tmp_path / "empty-proc"
    empty_proc.mkdir()

    res = _run_sweep(
        main, "--apply", bindir=bindir,
        env={
            "FAKE_GH_ROWS": f"issue-13=MERGED|{_tip(wt)}|13",
            "FLOW_WORKTREE_SWEEP_PROC_ROOT": str(empty_proc),
        },
    )

    assert _dispositions(res.stdout)[str(wt)] == "undecidable occupancy-unknown", res.stdout
    assert _status(res) == "partial"
    assert wt.exists()


# --------------------------------------------------------------------------
# The composition contract with #889. These are the tests that matter most:
# a teardown that routed around exit 5 would reopen the data-loss path #889
# closed, and would do it in a loop over every worktree on the host.
# --------------------------------------------------------------------------


def _recording_helper(bindir: Path, exit_code: int = 0) -> tuple[Path, Path]:
    """A stand-in worktree-remove.sh that records its argv and does nothing.

    The sweep resolves the helper beside itself, so the sweep is copied next to
    this file. That is the only way to observe the argv the sweep composes, and
    the argv is the whole contract here.
    """
    bindir.mkdir(parents=True, exist_ok=True)
    log = bindir / "invocations.log"
    helper = bindir / "worktree-remove.sh"
    helper.write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        f"exit {exit_code}\n"
    )
    helper.chmod(0o755)
    shutil.copy2(SWEEP, bindir / "flow-worktree-sweep.sh")
    return bindir / "flow-worktree-sweep.sh", log


@requires_git
@requires_proc
def test_the_sweep_passes_only_the_flag_it_needs(tmp_path: Path) -> None:
    """Every flag but `--delete-branch` overrides a refusal, so the sweep passes none.

    The sweep's largest contribution to safety is what it does NOT pass. That
    used to be stated as an enumeration of two flags; it is now an allowlist,
    for the reason recorded inline below.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-14", "issue-14")
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)
    script, log = _recording_helper(tmp_path / "helperbin")

    res = _run_sweep(
        main, "--apply", bindir=ghbin, script=script,
        env={"FAKE_GH_ROWS": f"issue-14=MERGED|{_tip(wt)}|14"},
    )

    recorded = log.read_text()
    assert str(wt) in recorded, f"helper was never invoked:\n{res.stdout}{res.stderr}"
    assert "--delete-branch" in recorded, (
        "the branch must go with the worktree, or #887's orphaned-branch half is "
        "left behind"
    )

    # INVERTED, and the inversion is the point. This test enumerated the
    # forbidden flags - `--force` and `--steal` - which were the only two that
    # existed when #887 landed. #899 then split `--force` into `--force`,
    # `--allow-dirty` and `--allow-unpushed`, and the two NEW ones are precisely
    # the flags that now disarm the data-loss guards. The enumeration did not
    # know about them, so the sweep could have started passing `--allow-dirty`
    # and all 25 tests here would still have passed - in a loop over every
    # worktree on the host, which is the exact path #889 and #899 exist to close.
    #
    # Measured, not hypothetical: adding `--allow-dirty` to the invocation left
    # this file fully green before this assertion replaced the enumeration.
    #
    # An allowlist cannot go stale the way that enumeration did. A sixth flag
    # added to the helper tomorrow is covered on the day it lands, because the
    # question is no longer "is it one of the two we thought of" but "is it
    # anything other than the one flag the sweep needs".
    flags = {tok for tok in recorded.split() if tok.startswith("--")}
    assert flags == {"--delete-branch"}, (
        f"the sweep passed {sorted(flags - {'--delete-branch'})} to "
        f"worktree-remove.sh. It must pass NO flag but --delete-branch: every "
        f"other flag the helper accepts overrides a refusal, and the sweep is "
        f"the one caller that applies them to every worktree on the host "
        f"(issues #887, #889, #899)."
    )


@pytest.mark.parametrize(
    "exit_code,expected",
    [
        (4, "refused claimed-by-live-session"),   # #597
        (5, "refused in-use-and-dirty"),          # #888
        (1, "refused helper-declined"),
    ],
)
@requires_git
@requires_proc
def test_a_helper_refusal_is_recorded_once_and_never_overridden(
    tmp_path: Path, exit_code: int, expected: str
) -> None:
    """A refusal is information, not an obstacle.

    One invocation, recorded, run reported `partial`. No retry, and above all no
    second attempt carrying --steal: that is the shape that would turn #889's
    single-path guard into a loop that defeats it everywhere at once.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-15", "issue-15")
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)
    script, log = _recording_helper(tmp_path / "helperbin", exit_code=exit_code)

    res = _run_sweep(
        main, "--apply", bindir=ghbin, script=script,
        env={"FAKE_GH_ROWS": f"issue-15=MERGED|{_tip(wt)}|15"},
    )

    assert _dispositions(res.stdout)[str(wt)].startswith(expected), res.stdout
    assert _status(res) == "partial"
    assert res.returncode == 3
    assert len(log.read_text().strip().splitlines()) == 1, (
        f"the helper was invoked more than once:\n{log.read_text()}"
    )
    assert "--steal" not in log.read_text()


@requires_git
@requires_proc
def test_one_refusal_does_not_stop_the_sweep(tmp_path: Path) -> None:
    """A refused worktree is skipped past, not treated as a fatal error - but the
    run still reports `partial`, so a caller cannot read a clean tree out of it."""
    main = _repo(tmp_path)
    wt_a = _add_worktree(main, tmp_path / "widget-issue-16", "issue-16")
    wt_b = _add_worktree(main, tmp_path / "widget-issue-17", "issue-17")
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)
    script, log = _recording_helper(tmp_path / "helperbin", exit_code=5)

    res = _run_sweep(
        main, "--apply", bindir=ghbin, script=script,
        env={
            "FAKE_GH_ROWS": (
                f"issue-16=MERGED|{_tip(wt_a)}|16;issue-17=MERGED|{_tip(wt_b)}|17"
            )
        },
    )

    seen = _dispositions(res.stdout)
    assert seen[str(wt_a)].startswith("refused"), res.stdout
    assert seen[str(wt_b)].startswith("refused"), res.stdout
    assert len(log.read_text().strip().splitlines()) == 2
    assert _status(res) == "partial"


@requires_git
def test_apply_refuses_outright_when_the_helper_is_absent(tmp_path: Path) -> None:
    """No fallback to a bare `git worktree remove`.

    That fallback would drop the #597 and #888 guards the whole design leans on,
    so an absent helper is an error rather than a slower path.
    """
    main = _repo(tmp_path)
    _add_worktree(main, tmp_path / "widget-issue-18", "issue-18")
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    shutil.copy2(SWEEP, isolated / "flow-worktree-sweep.sh")

    res = _run_sweep(
        main, "--apply", bindir=ghbin, script=isolated / "flow-worktree-sweep.sh",
        env={"FAKE_GH_ROWS": "", "HOME": str(tmp_path / "nohome")},
    )

    assert res.returncode == 1
    assert _status(res) == "error"
    assert "worktree-remove.sh not found" in res.stderr


# --------------------------------------------------------------------------
# Scope of --include-closed, and one named residual.
# --------------------------------------------------------------------------


def _mutating_git(
    bindir: Path, worktree: Path, mutation: str, after_status_call: int = 1
) -> Path:
    """A `git` wrapper that mutates the worktree after the Nth `status` call.

    This is how the removal-time window is made deterministic instead of raced.
    The wrapper answers the Nth `git status` truthfully first, then mutates, so
    every read the sweep takes AFTER that call sees the new state and every read
    before it saw the old one.

    Which N lands in the window depends on the order the sweep reads in, and
    getting it wrong makes the test inert rather than red - so each caller states
    the sequence it is aiming at and both tests assert a disposition that only
    the re-check can produce:

      1  classification dirty    <- N=1 lands after this
      2  classification unpushed (rev-parse, no `status`)
      3  occupancy scan          (no git)
      4  RE-VERIFY dirty         <- N=2 lands after this
      5  RE-VERIFY unpushed
      6  worktree-remove.sh
    """
    bindir.mkdir(parents=True, exist_ok=True)
    real = shutil.which("git")
    assert real, "git must be on PATH for this test"
    counter = bindir / "status-calls"
    wrapper = bindir / "git"
    wrapper.write_text(
        "#!/bin/bash\n"
        'for a in "$@"; do\n'
        '  if [[ "$a" == "status" ]]; then\n'
        f'    n=$(cat "{counter}" 2>/dev/null || echo 0); n=$((n + 1))\n'
        f'    printf "%s" "$n" > "{counter}"\n'
        f'    if [[ "$n" == "{after_status_call}" ]]; then\n'
        f'      "{real}" "$@"; rc=$?\n'
        f'      {mutation}\n'
        "      exit $rc\n"
        "    fi\n"
        "  fi\n"
        "done\n"
        f'exec "{real}" "$@"\n'
    )
    wrapper.chmod(0o755)
    return wrapper


@requires_git
@requires_proc
def test_a_commit_landing_after_classification_is_caught_before_removal(
    tmp_path: Path,
) -> None:
    """The window with no backstop underneath it.

    A paused session that COMMITS without pushing is invisible to every other
    guard: `git status --porcelain` reports clean, so worktree-remove.sh's own
    uncommitted-changes check passes, and a session paused between tool calls has
    no live process for either occupancy scan to find. `git log @{u}..` - here,
    the tip-versus-PR-head comparison - is the only check that sees it, and it is
    ours alone. So it is re-read as the last statement before the removal call
    rather than trusted from classification time.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-21", "issue-21")
    merged_oid = _tip(wt)
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)
    script, log = _recording_helper(tmp_path / "helperbin")
    _mutating_git(
        ghbin,
        wt,
        after_status_call=2,
        mutation=(
            f'printf "late\\n" > "{wt}/late.md"; '
            f'"$(command -v git || echo git)" -C "{wt}" add -A >/dev/null 2>&1; '
            f'GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com '
            f'GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com '
            f'"$(command -v git || echo git)" -C "{wt}" commit -qm late >/dev/null 2>&1'
        ),
    )

    res = _run_sweep(
        main, "--apply", bindir=ghbin, script=script,
        env={"FAKE_GH_ROWS": f"issue-21=MERGED|{merged_oid}|21"},
    )

    # Precondition: the mutation really did land, or this test pins nothing.
    assert (wt / "late.md").exists(), "the wrapper never committed; test is inert"
    assert _tip(wt) != merged_oid, "HEAD did not move; test is inert"

    assert _dispositions(res.stdout)[str(wt)].startswith("skip unpushed-at-removal"), (
        f"a commit that landed after classification was not re-checked:\n{res.stdout}"
    )
    assert not log.exists() or log.read_text().strip() == "", (
        f"the removal helper was invoked anyway:\n{log.read_text()}"
    )
    assert wt.exists()


@requires_git
@requires_proc
def test_a_dirty_tree_appearing_after_classification_is_caught_before_removal(
    tmp_path: Path,
) -> None:
    """Same window, the condition that DOES have a backstop.

    worktree-remove.sh would also refuse this one, because the sweep passes no
    --force. Re-checked here anyway so the refusal is a skip with a reason rather
    than an exit code to interpret, and so the two conditions are not treated
    differently for no stated reason.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-22", "issue-22")
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)
    script, log = _recording_helper(tmp_path / "helperbin")
    _mutating_git(ghbin, wt, mutation=f'printf "late\\n" > "{wt}/late.md"')

    res = _run_sweep(
        main, "--apply", bindir=ghbin, script=script,
        env={"FAKE_GH_ROWS": f"issue-22=MERGED|{_tip(wt)}|22"},
    )

    assert (wt / "late.md").exists(), "the wrapper never wrote; test is inert"
    assert _dispositions(res.stdout)[str(wt)].startswith("skip dirty-at-removal"), res.stdout
    assert not log.exists() or log.read_text().strip() == ""
    assert wt.exists()


@requires_git
@requires_proc
def test_closed_pr_needs_include_closed(tmp_path: Path) -> None:
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "widget-issue-19", "issue-19")
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)
    env = {"FAKE_GH_ROWS": f"issue-19=CLOSED|{_tip(wt)}|19"}

    default = _run_sweep(main, "--apply", bindir=ghbin, env=env)
    assert _dispositions(default.stdout)[str(wt)].startswith("skip pr-closed"), default.stdout
    assert wt.exists()

    opted_in = _run_sweep(main, "--apply", "--include-closed", bindir=ghbin, env=env)
    assert _dispositions(opted_in.stdout)[str(wt)].startswith("removed"), opted_in.stdout
    assert not wt.exists()


@requires_git
@requires_proc
def test_gitignored_state_is_invisible_to_every_condition(tmp_path: Path) -> None:
    """A named residual, pinned as a property rather than left as a TODO.

    `git status --porcelain` excludes ignored files, so a worktree whose only
    local state is a `.venv`, a `.env` or build output is `clean` by every one of
    the five conditions and is removed with that state. This test asserts the
    blind spot exists rather than pretending it does not: the five conditions
    answer "is there unsaved WORK here", and a reader can take that for "is there
    anything here I would miss".

    Deliberately not fixed by widening the dirty check to `--ignored`: that would
    make every worktree carrying a build directory permanently unremovable, which
    is the everyday-blocker over-correction #889 declined for the same reason.
    """
    main = _repo(tmp_path)
    (main / ".gitignore").write_text(".env\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "ignore .env")
    wt = _add_worktree(main, tmp_path / "widget-issue-20", "issue-20")
    (wt / ".env").write_text("LOCAL_ONLY=1\n")
    assert _git(wt, "status", "--porcelain") == "", (
        "precondition: the ignored file must not show as dirty, or this test is "
        "not exercising the blind spot it claims to pin"
    )
    ghbin = tmp_path / "bin"
    _fake_gh(ghbin)

    res = _run_sweep(
        main, "--apply", bindir=ghbin,
        env={"FAKE_GH_ROWS": f"issue-20=MERGED|{_tip(wt)}|20"},
    )

    assert _dispositions(res.stdout)[str(wt)].startswith("removed"), res.stdout
    assert not wt.exists(), "the residual this test pins is that the sweep removes it"


# --------------------------------------------------------------------------
# The helper the sweep delegates to must still be the real one.
# --------------------------------------------------------------------------


@requires_git
def test_the_real_remove_helper_exists_where_the_sweep_looks(tmp_path: Path) -> None:
    """Guards the resolution above: every behavioural test that uses a recording
    stub proves nothing about the shipped pairing."""
    assert REMOVE.is_file()
    assert os.access(REMOVE, os.X_OK)
    assert REMOVE.parent == SWEEP.parent
