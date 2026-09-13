"""Regression tests for issue #888: worktree-remove.sh must not delete a
worktree that a live session is working in without a claim.

Root cause: the #597 cross-session claim protects a worktree only where a claim
was actually staked. ``flow-worktree-claim.sh check`` can report seven states,
but the removal script's ``case`` handled only ``held|foreign`` (hard stop) and
``self|stale`` (release and proceed). ``free``, ``unsupported`` and ``unknown``
fell through it silently - and ``free`` is simply what a worktree created
outside the /flow lane reports. The uncommitted-changes backstop below could not
catch the fall-through either, because it is skipped whenever ``--force`` is
passed, and ``/flow:auto`` Step 7 always passes ``--force``.

Observed on 2026-09-13: a session sitting in ``flow-finish-gate`` held a 21KB
staged file in a worktree reporting ``CLAIM=free``. The only thing between it and
deletion was the #503 mtime heuristic, whose 30-minute window that session had
already outlived by being in a long test run - so both guards read "clear" on a
checkout that was plainly occupied.

The fix: when no claim names this session, scan for live processes whose working
directory is inside the worktree. Occupied AND dirty is a hard stop (exit 5) that
``--force`` does not suppress; ``--steal`` still overrides. A host that cannot
scan reports ``unknown``, never ``clear``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "worktree-remove.sh"

# Same constraint as test_worktree_remove_squash.py: the Woodpecker ``validate``
# step runs in a slim image with bash but no git.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="requires git and bash on PATH (absent in the CI validate container)",
)

# The occupancy signal is /proc-based, so the behavioural tests are Linux-only.
# Skipping is honest here: on a host without /proc the guard genuinely does not
# fire, and test_cannot_scan_reports_unknown_not_clear pins that degradation.
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


def _run_remove(
    cwd: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd,
        env=run_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )


def _repo(tmp_path: Path) -> Path:
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    (main / "base.txt").write_text("base\n")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")
    return main


def _add_worktree(main: Path, path: Path, branch: str) -> Path:
    _git(main, "worktree", "add", "-q", str(path), "-b", branch)
    return path


@pytest.fixture()
def occupant():
    """Spawn a real long-lived process whose cwd is a given directory.

    A real process is used rather than a synthetic /proc tree on purpose: a
    hand-built tree would only prove the matcher agrees with the author's idea of
    what /proc looks like.
    """
    procs: list[subprocess.Popen] = []

    def _spawn(cwd: Path) -> subprocess.Popen:
        p = subprocess.Popen(
            ["sleep", "60"],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for the kernel to publish its cwd link before the scan runs.
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


@requires_git
@requires_proc
def test_occupied_and_dirty_refused_despite_force(tmp_path: Path, occupant) -> None:
    """The core bug: --force must NOT delete a worktree in use with unsaved work."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    # Unsaved work of exactly the shape that was nearly lost: a staged new file.
    (wt / "spec.md").write_text("work that exists nowhere else\n")
    _git(wt, "add", "-A")
    occupant(wt)

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 5, (
        f"expected the #888 in-use refusal (exit 5), got {res.returncode}\n"
        f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    )
    assert wt.exists(), "worktree was removed out from under a live process"
    assert (wt / "spec.md").read_text() == "work that exists nowhere else\n"
    assert "WORKTREE_REMOVE_OCCUPANCY: occupied-dirty" in res.stderr
    # The report must name what it found, or the operator cannot act on it.
    assert "spec.md" in res.stderr


@requires_git
@requires_proc
def test_occupied_but_clean_is_still_removed(tmp_path: Path, occupant) -> None:
    """Occupancy alone does not block: with nothing unsaved, nothing is lost."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    occupant(wt)

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, f"clean occupied worktree should remove:\n{res.stderr}"
    assert not wt.exists()
    assert "WORKTREE_REMOVE_OCCUPANCY: occupied-clean" in res.stderr


@requires_git
@requires_proc
def test_idle_and_dirty_still_removed_with_force(tmp_path: Path) -> None:
    """Regression guard for the normal /flow:auto Step 7 path.

    The tempting over-broad fix - refuse whenever no claim names us - would turn
    a rare data-loss bug into an everyday blocker, because ``free`` is what every
    worktree created outside the /flow lane reports. An idle dirty worktree must
    still honour --force.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "leftover.txt").write_text("uncommitted but nobody is here\n")

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, (
        f"an idle worktree must still be removable with --force:\n{res.stderr}"
    )
    assert not wt.exists()
    assert "WORKTREE_REMOVE_OCCUPANCY: clear" in res.stderr


@requires_git
@requires_proc
def test_sibling_worktree_sharing_a_path_prefix_is_not_occupancy(
    tmp_path: Path, occupant
) -> None:
    """A finding must tell this worktree from its neighbour.

    ``<wt>-2`` starts with ``<wt>``, so a bare prefix test reports the neighbour's
    processes as occupying this one. That is not hypothetical: on the host where
    #888 was found, ``kyle-issue-1142`` is a real prefix of
    ``kyle-issue-1142-container-spec-superseded``.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    sibling = _add_worktree(main, tmp_path / "wt-2", "feature-2")
    (wt / "leftover.txt").write_text("dirty, but nobody is in THIS worktree\n")
    occupant(sibling)  # live process in the NEIGHBOUR only

    res = _run_remove(main, str(wt), "--force", "--delete-branch")

    assert res.returncode == 0, (
        "the neighbour's process was mistaken for occupancy of this worktree "
        f"(path-prefix false positive):\n{res.stderr}"
    )
    assert not wt.exists()
    assert sibling.exists(), "the neighbour must be untouched"
    assert "WORKTREE_REMOVE_OCCUPANCY: clear" in res.stderr


@requires_git
@requires_proc
def test_steal_overrides_the_occupancy_refusal(tmp_path: Path, occupant) -> None:
    """--steal stays the deliberate override, as it is for a #597 claim."""
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "spec.md").write_text("work\n")
    _git(wt, "add", "-A")
    occupant(wt)

    res = _run_remove(main, str(wt), "--force", "--delete-branch", "--steal")

    assert res.returncode == 0, f"--steal must override the #888 stop:\n{res.stderr}"
    assert not wt.exists()


@requires_git
def test_cannot_scan_reports_unknown_not_clear(tmp_path: Path) -> None:
    """An unscanned host must read as unknown, never as clean.

    A guard that cannot look, but prints a clean result, is worse than no guard:
    it manufactures the reassurance that stopped anyone checking. Pointed at a
    proc tree with nothing in it, the scan must say so.
    """
    main = _repo(tmp_path)
    wt = _add_worktree(main, tmp_path / "wt", "feature")
    (wt / "leftover.txt").write_text("dirty\n")
    empty_proc = tmp_path / "empty-proc"
    empty_proc.mkdir()

    res = _run_remove(
        main,
        str(wt),
        "--force",
        "--delete-branch",
        env={"WORKTREE_REMOVE_PROC_ROOT": str(empty_proc)},
    )

    assert "WORKTREE_REMOVE_OCCUPANCY: unknown" in res.stderr, (
        f"an unscannable host must report unknown:\n{res.stderr}"
    )
    assert "WORKTREE_REMOVE_OCCUPANCY: clear" not in res.stderr
    # Fail-open by design: it degrades to the pre-#888 behaviour, loudly.
    assert res.returncode == 0
