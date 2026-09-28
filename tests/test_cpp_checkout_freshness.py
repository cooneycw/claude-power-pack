"""Controls for `scripts/cpp-checkout-freshness.sh` (issue #1282).

`/cpp:status` is read by other sessions, so its freshness verdict is an
instrument whose green nobody downstream re-derives (ADR 0008). Every case runs
against REAL repositories - a bare origin and a clone of it - because the
defect being fixed lives in how git behaves when a fetch or a count fails, and a
mocked git would only repeat what the mock was told.

  POSITIVE   one commit behind reads `behind 1`.
  NEGATIVE   the same clone after a pull reads `current` - without it, a gate
             stuck at "behind" passes the positive case on its own.
  BLIND      an unreachable origin, and a checkout the fetch cannot write, read
             `unknown` - never `current`, and never a count against the ref the
             last successful fetch left behind.

`test_pre_fix_block_reports_an_unreachable_origin_as_up_to_date` is the red
case: `/cpp:update`'s compare block as it stood at 164fdd4, run on the
fetch-fails fixture, prints "Already up to date!".
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cpp-checkout-freshness.sh"
PRE_FIX = (
    ROOT
    / "controls"
    / "cpp-checkout-freshness"
    / "anchors"
    / "164fdd4-pre-fix-update-compare-block.sh"
)

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="requires bash and git on PATH",
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str) -> None:
    (repo / "marker.txt").write_text(message, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", message)


def _clone(origin: Path, dest: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--quiet", str(origin), str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(dest, "config", "user.email", "test@example.invalid")
    _git(dest, "config", "user.name", "Test")
    return dest


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path, Path]:
    """(origin, seed, checkout): `seed` pushes to `origin`; `checkout` is the one measured."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--quiet", "--bare", "--initial-branch=main", str(origin)],
        check=True,
        capture_output=True,
    )
    seed = _clone(origin, tmp_path / "seed")
    _git(seed, "checkout", "--quiet", "-b", "main")
    _commit(seed, "one")
    _git(seed, "push", "--quiet", "origin", "main")
    checkout = _clone(origin, tmp_path / "checkout")
    return origin, seed, checkout


def _advance(seed: Path, message: str = "upstream") -> None:
    _commit(seed, message)
    _git(seed, "push", "--quiet", "origin", "main")


def _run(checkout: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["CPP_FRESHNESS_FETCH_TIMEOUT"] = "20"
    return subprocess.run(
        ["bash", str(SCRIPT), "--path", str(checkout), *extra],
        capture_output=True,
        text=True,
        env=env,
    )


def _verdict(result: subprocess.CompletedProcess[str]) -> str:
    lines = [
        ln for ln in result.stdout.splitlines() if ln.startswith("CPP_CHECKOUT_FRESHNESS: ")
    ]
    assert len(lines) == 1, f"exactly one verdict line expected:\n{result.stdout}{result.stderr}"
    assert result.stdout.rstrip().splitlines()[-1] == lines[0], "the verdict must be the last line"
    return lines[0].removeprefix("CPP_CHECKOUT_FRESHNESS: ")


def test_one_commit_behind_reads_behind_1(repos: tuple[Path, Path, Path]) -> None:
    _, seed, checkout = repos
    _advance(seed, "the missing commit")
    result = _run(checkout)
    assert _verdict(result) == "behind 1"
    assert result.returncode == 3
    assert "the missing commit" in result.stdout, "the missing commits are listed"


def test_the_same_clone_after_a_pull_reads_current(repos: tuple[Path, Path, Path]) -> None:
    _, seed, checkout = repos
    _advance(seed)
    assert _verdict(_run(checkout)) == "behind 1"
    _git(checkout, "pull", "--quiet", "--ff-only")
    result = _run(checkout)
    assert _verdict(result) == "current"
    assert result.returncode == 0


def test_an_unreachable_origin_reads_unknown_not_current(
    repos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """The ref from the LAST fetch is still there and still says 0 behind - it must not be believed."""
    _, seed, checkout = repos
    _advance(seed)  # the remote is now ahead, but this checkout will never learn it
    _git(checkout, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    # Precondition: the stale ref says "0 behind", which is what must not be believed.
    assert _git(checkout, "rev-list", "--count", "HEAD..origin/main") == "0"
    assert not (tmp_path / "gone.git").exists()
    result = _run(checkout)
    verdict = _verdict(result)
    assert verdict.startswith("unknown: fetch failed"), verdict
    assert result.returncode == 4


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes, so read-only cannot be made")
def test_a_read_only_checkout_reads_unknown_not_a_stale_count(
    repos: tuple[Path, Path, Path],
) -> None:
    """A kyle container sees the checkout read-only: the fetch cannot write, so nothing may be counted."""
    _, seed, checkout = repos
    _advance(seed)
    git_dir = checkout / ".git"
    subprocess.run(["chmod", "-R", "a-w", str(git_dir)], check=True)
    try:
        assert not os.access(git_dir / "refs", os.W_OK), "precondition: the fetch cannot write"
        result = _run(checkout)
    finally:
        subprocess.run(["chmod", "-R", "u+w", str(git_dir)], check=True)
    assert _verdict(result) == "unknown: fetch failed (checkout not writable)"
    assert result.returncode == 4


def test_local_commits_read_ahead(repos: tuple[Path, Path, Path]) -> None:
    _, _, checkout = repos
    _commit(checkout, "local only")
    result = _run(checkout)
    assert _verdict(result) == "ahead 1"
    assert result.returncode == 3


def test_local_and_remote_commits_read_diverged(repos: tuple[Path, Path, Path]) -> None:
    _, seed, checkout = repos
    _advance(seed)
    _commit(checkout, "local only")
    assert _verdict(_run(checkout)) == "diverged (ahead 1, behind 1)"


def test_a_feature_branch_is_named(repos: tuple[Path, Path, Path]) -> None:
    _, _, checkout = repos
    _git(checkout, "checkout", "--quiet", "-b", "issue-9-feature")
    result = _run(checkout)
    assert "Branch: issue-9-feature (NOT main" in result.stdout
    assert _verdict(result) == "current", "still measured against origin/main"


def test_a_detached_head_is_named_and_an_empty_branch_is_unknown(
    repos: tuple[Path, Path, Path],
) -> None:
    """`/cpp:update` passes `git branch --show-current`, which is EMPTY when detached."""
    _, _, checkout = repos
    _git(checkout, "checkout", "--quiet", "--detach")
    result = _run(checkout)
    assert "Branch: (detached HEAD at" in result.stdout
    assert _verdict(result) == "current"
    empty = _run(checkout, "--branch", "")
    assert _verdict(empty) == "unknown: no branch to compare against (detached HEAD)"
    assert empty.returncode == 4


def test_a_branch_missing_on_origin_is_unknown(repos: tuple[Path, Path, Path]) -> None:
    _, _, checkout = repos
    result = _run(checkout, "--branch", "no-such-branch")
    assert _verdict(result).startswith("unknown: fetch failed")
    assert result.returncode == 4


def test_not_a_git_repository_is_unknown(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    result = _run(plain)
    assert _verdict(result) == "unknown: not a git repository"
    assert result.returncode == 4


def test_the_behind_listing_is_capped(repos: tuple[Path, Path, Path]) -> None:
    _, seed, checkout = repos
    for n in range(4):
        _advance(seed, f"upstream {n}")
    result = _run(checkout, "--log-cap", "2")
    assert _verdict(result) == "behind 4"
    assert "... and 2 more" in result.stdout


def test_pre_fix_block_reports_an_unreachable_origin_as_up_to_date(
    repos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """RED CASE: the block this issue replaces calls an unknown gap clean."""
    _, seed, checkout = repos
    _advance(seed)
    _git(checkout, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    assert _git(checkout, "rev-list", "--count", "HEAD..origin/main") == "0"
    result = subprocess.run(
        ["bash", str(PRE_FIX), "--path", str(checkout)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Already up to date!" in result.stdout
    assert "CPP_CHECKOUT_FRESHNESS" not in result.stdout


def test_update_md_no_longer_maps_a_failed_count_to_zero() -> None:
    """No executable line counts commits and falls back to 0 (a comment may name the old shape)."""
    text = (ROOT / ".claude" / "commands" / "cpp" / "update.md").read_text(encoding="utf-8")
    code = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    offenders = [ln for ln in code if "rev-list" in ln and "--count" in ln and '|| echo "0"' in ln]
    assert offenders == []
    assert any("cpp-checkout-freshness.sh" in ln for ln in code)


def test_status_md_runs_the_helper_and_says_it_fetches() -> None:
    text = (ROOT / ".claude" / "commands" / "cpp" / "status.md").read_text(encoding="utf-8")
    assert "cpp-checkout-freshness.sh" in text
    assert "fetches" in text


def test_a_local_tag_named_like_the_remote_ref_is_not_what_is_counted(
    repos: tuple[Path, Path, Path],
) -> None:
    """Counter-model finding: shorthand `origin/main` resolves `refs/tags/origin/main` first."""
    _, seed, checkout = repos
    _git(checkout, "tag", "origin/main", "HEAD")
    _advance(seed)
    # Precondition: the shorthand really is shadowed by the tag.
    assert _git(checkout, "rev-parse", "origin/main^{commit}") == _git(checkout, "rev-parse", "HEAD")
    assert _verdict(_run(checkout)) == "behind 1"


def test_an_inherited_git_dir_does_not_redirect_the_measurement(
    repos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Counter-model finding: `git -C` does not override GIT_DIR, so a neighbour would be measured."""
    origin, seed, checkout = repos
    neighbour = _clone(origin, tmp_path / "neighbour")
    _advance(seed)
    _git(neighbour, "pull", "--quiet", "--ff-only")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_DIR"] = str(neighbour / ".git")
    result = subprocess.run(
        ["bash", str(SCRIPT), "--path", str(checkout)], capture_output=True, text=True, env=env
    )
    assert _verdict(result) == "behind 1", "the declared checkout is behind; the neighbour is current"


def test_a_directory_inside_another_repository_is_not_measured_as_it(
    repos: tuple[Path, Path, Path],
) -> None:
    """Counter-model re-review: `git -C sub` discovers the ENCLOSING repository."""
    _, seed, checkout = repos
    _advance(seed)
    nested = checkout / "not-a-checkout"
    nested.mkdir()
    assert _git(nested, "rev-parse", "--show-toplevel") == str(checkout.resolve())
    result = _run(nested)
    assert _verdict(result).startswith("unknown: not a checkout root"), result.stdout
    assert result.returncode == 4


def test_a_shallow_clone_is_unknown_not_a_false_divergence(
    repos: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Counter-model re-review: origin rewound past a depth-1 boundary reads as diverged."""
    origin, seed, _ = repos
    _advance(seed, "B")
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", f"file://{origin}", str(shallow)],
        check=True, capture_output=True,
    )
    _git(seed, "reset", "--quiet", "--hard", "HEAD~1")
    _git(seed, "push", "--quiet", "--force", "origin", "main")
    assert _git(shallow, "rev-parse", "--is-shallow-repository") == "true"
    result = _run(shallow)
    assert _verdict(result).startswith("unknown: shallow clone"), result.stdout


def test_the_anchor_block_is_verbatim_from_164fdd4() -> None:
    """The anchor's provenance is `n/a` to the harness (the preamble is constructed); the span is checked here."""
    probe = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-e", "164fdd4:.claude/commands/cpp/update.md"],
        capture_output=True,
    )
    if probe.returncode != 0:
        pytest.skip("164fdd4 is not in this clone's history (shallow clone)")
    original = _git(ROOT, "show", "164fdd4:.claude/commands/cpp/update.md").splitlines()[147:166]
    lines = PRE_FIX.read_text(encoding="utf-8").splitlines()
    begin = next(i for i, ln in enumerate(lines) if "BEGIN verbatim" in ln)
    end = next(i for i, ln in enumerate(lines) if "END verbatim" in ln)
    assert lines[begin + 1 : end] == original


def test_a_host_without_timeout_still_measures(repos: tuple[Path, Path, Path], tmp_path: Path) -> None:
    """Orchestrator review of #1305: with no `timeout`, TIMEOUT_CMD is EMPTY.

    Under `set -u` a bare `"${TIMEOUT_CMD[@]}"` of an empty array is an unbound
    variable on bash < 4.4 (macOS /bin/bash 3.2), so every fetch died and read
    `unknown`. This pins the absent-timeout path; it cannot go red on the bash
    >= 4.4 this suite runs under, which is stated rather than claimed.
    """
    _, seed, checkout = repos
    _advance(seed)
    bin_dir = tmp_path / "bin-without-timeout"
    bin_dir.mkdir()
    for tool in ("bash", "git", "sed", "grep", "head", "tail", "awk", "readlink", "dirname", "cat"):
        found = shutil.which(tool)
        if found is None:
            pytest.skip(f"{tool} is not on PATH")
        (bin_dir / tool).symlink_to(found)
    assert shutil.which("timeout", path=str(bin_dir)) is None, "precondition: no timeout on PATH"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PATH"] = str(bin_dir)
    result = subprocess.run(
        [str(bin_dir / "bash"), str(SCRIPT), "--path", str(checkout)],
        capture_output=True, text=True, env=env,
    )
    assert _verdict(result) == "behind 1", result.stdout + result.stderr
