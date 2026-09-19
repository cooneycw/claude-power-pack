"""Controls for `scripts/toolchain-provenance.sh` (issue #1029, specimen 1).

The instrument's whole claim is a NUMBER, so the controls are the two ends of
it plus the state that must never be rendered as a number at all:

  POSITIVE  a checkout behind its upstream by N reports exactly N.
  NEGATIVE  a checkout at the tip reports 0 - without it, a gap counter that
            silently matches nothing renders identically to a working one.
  BLIND     a checkout with no upstream reports `unknown` and a NULL count.
            "could not measure" and "measured, gap zero" are different answers
            and only one of them is evidence; a 0 printed for the first is
            worse than no line, because it looks like data.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "toolchain-provenance.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="requires bash and git on PATH",
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_checkout_files(root: Path) -> None:
    """The two markers `is_checkout()` looks for, and nothing else.

    The command file inside `.claude/commands/flow/` is load-bearing, not
    decoration: git does not track empty directories, so a marker directory with
    no file in it survives the commit and vanishes from the clone - which made
    every clone in this module report `unknown` for the wrong reason.
    """
    flow = root / ".claude" / "commands" / "flow"
    flow.mkdir(parents=True, exist_ok=True)
    (flow / "auto.md").write_text("# auto\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# fake CPP\n", encoding="utf-8")


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--quiet", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.invalid")
    _git(path, "config", "user.name", "Test")


def _commit(path: Path, message: str) -> None:
    (path / "marker.txt").write_text(message, encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "--quiet", "-m", message)


@pytest.fixture
def upstream_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    """An origin with three commits, and a clone tracking its main."""
    origin = tmp_path / "origin"
    _init_repo(origin)
    _make_checkout_files(origin)
    for n in range(3):
        _commit(origin, f"commit {n}")

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", str(origin), str(clone)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(clone, "config", "user.email", "test@example.invalid")
    _git(clone, "config", "user.name", "Test")
    return origin, clone


def _run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "--path", str(path), *args],
        capture_output=True,
        text=True,
    )


def _json(path: Path) -> dict:
    result = _run(path, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_negative_control_a_checkout_at_the_tip_reports_zero(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """The half that separates a working counter from one matching nothing."""
    _, clone = upstream_and_clone
    payload = _json(clone)
    assert payload["verdict"] == "current"
    assert payload["behind"] == 0
    assert payload["ahead"] == 0


def test_positive_control_a_behind_checkout_reports_the_exact_gap(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """The #1029 case: origin moves, the executing copy does not know."""
    origin, clone = upstream_and_clone
    for n in range(3, 8):
        _commit(origin, f"commit {n}")
    _git(clone, "fetch", "--quiet", "origin")

    payload = _json(clone)
    assert payload["verdict"] == "behind"
    assert payload["behind"] == 5, "the gap must be the count, not a boolean"
    assert payload["ahead"] == 0

    report = _run(clone)
    assert "TOOLCHAIN_PROVENANCE: behind" in report.stdout
    assert "5 commit(s) BEHIND" in report.stdout


def test_quiet_is_silent_when_current_and_speaks_when_behind(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """A line printed on every session start is a line nobody reads."""
    origin, clone = upstream_and_clone
    assert _run(clone, "--quiet").stdout.strip() == ""

    _commit(origin, "commit 3")
    _git(clone, "fetch", "--quiet", "origin")
    spoken = _run(clone, "--quiet").stdout
    assert "1 commit(s) BEHIND" in spoken


def test_blind_control_no_upstream_is_unknown_and_never_a_zero(
    tmp_path: Path,
) -> None:
    """The failure this instrument must not reproduce inside itself."""
    solo = tmp_path / "solo"
    _init_repo(solo)
    _make_checkout_files(solo)
    _commit(solo, "only commit")

    payload = _json(solo)
    assert payload["verdict"] == "unknown"
    assert payload["behind"] is None, "unmeasured must not render as a gap of zero"
    assert payload["ahead"] is None
    assert payload["reason"]

    report = _run(solo)
    assert "TOOLCHAIN_PROVENANCE: unknown" in report.stdout
    assert "NOT a gap of zero" in report.stdout


def test_blind_control_a_non_repo_checkout_is_unknown(tmp_path: Path) -> None:
    """A CPP checkout that is not a git repository cannot be measured."""
    plain = tmp_path / "plain"
    plain.mkdir()
    _make_checkout_files(plain)

    payload = _json(plain)
    assert payload["verdict"] == "unknown"
    assert payload["behind"] is None
    assert "not a git repository" in payload["reason"]


def test_ahead_is_not_reported_as_current(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """Carrying unpushed commits is not stale, and is not what a reviewer read."""
    _, clone = upstream_and_clone
    _commit(clone, "local only")

    payload = _json(clone)
    assert payload["verdict"] == "ahead"
    assert payload["ahead"] == 1
    assert payload["behind"] == 0


def test_the_gap_is_measured_against_the_branch_upstream_not_hardcoded_main(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """A checkout parked on another branch must not report a fabricated gap.

    Measuring everything against `origin/main` would make a release branch look
    arbitrarily behind, and a wrong number disables its own audit more
    thoroughly than an absent one.
    """
    origin, clone = upstream_and_clone
    _git(origin, "checkout", "--quiet", "-b", "release")
    _commit(origin, "release commit")
    _git(clone, "fetch", "--quiet", "origin")
    _git(clone, "checkout", "--quiet", "-b", "release", "--track", "origin/release")

    payload = _json(clone)
    assert payload["upstream"] == "origin/release"
    assert payload["verdict"] == "current"
    assert payload["behind"] == 0


def test_fetch_age_travels_with_the_counts_and_names_its_source(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """`behind=0` against stale evidence is a confident claim about old news.

    The SOURCE is asserted alongside the number because the three candidates are
    not equally good: a fresh clone has no FETCH_HEAD and stores its remote refs
    packed, so a loose-ref-only lookup returned nothing and the age silently read
    `unknown` in the ordinary case. `packed-refs` bounds staleness rather than
    dating a fetch, and the label is what stops it being read as the latter.
    """
    origin, clone = upstream_and_clone

    fresh = _json(clone)
    assert isinstance(fresh["fetch_age_seconds"], int)
    assert fresh["fetch_age_seconds"] >= 0
    assert fresh["fetch_age_source"] == "packed-refs", (
        "a fresh clone has no FETCH_HEAD and packs its remote refs"
    )

    _commit(origin, "commit 3")
    _git(clone, "fetch", "--quiet", "origin")
    fetched = _json(clone)
    assert fetched["fetch_age_source"] == "fetch-head", (
        "after a real fetch the age must come from the direct evidence"
    )


def test_fetch_age_is_null_when_nothing_dates_it(tmp_path: Path) -> None:
    """An unmeasurable age reports null and no source, never a zero."""
    plain = tmp_path / "plain"
    plain.mkdir()
    _make_checkout_files(plain)
    payload = _json(plain)
    assert payload["fetch_age_seconds"] is None
    assert payload["fetch_age_source"] is None


def test_a_missing_checkout_is_unknown_not_current(tmp_path: Path) -> None:
    result = _run(tmp_path / "does-not-exist", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "unknown"
    assert payload["behind"] is None


def test_an_unrelated_fetch_does_not_refresh_our_evidence_age(
    upstream_and_clone: tuple[Path, Path], tmp_path: Path
) -> None:
    """FETCH_HEAD is rewritten by a fetch of ANY remote (counter-model review).

    Accepting it unconditionally let `git fetch some-other-remote` date an
    observation of OUR upstream as freshly measured - a fabricated specificity,
    in the field that exists to prevent one. The clause git writes names the
    branch and the URL, and that is what must match.
    """
    origin, clone = upstream_and_clone
    _git(clone, "fetch", "--quiet", "origin")
    assert _json(clone)["fetch_age_source"] == "fetch-head"

    other = tmp_path / "other"
    _init_repo(other)
    _make_checkout_files(other)
    _commit(other, "unrelated")
    _git(clone, "remote", "add", "other", str(other))
    _git(clone, "fetch", "--quiet", "other")

    payload = _json(clone)
    assert payload["fetch_age_source"] != "fetch-head", (
        "a fetch of an unrelated remote is not evidence about origin/main"
    )
    assert payload["verdict"] == "current"


def test_json_survives_a_path_containing_quotes_and_backslashes(
    tmp_path: Path,
) -> None:
    """Every consumer of --json parses it, so it has to BE json."""
    hostile = tmp_path / 'we"ird\\dir'
    hostile.mkdir()
    _make_checkout_files(hostile)

    result = _run(hostile, "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)  # the assertion is that this parses
    assert payload["checkout"] == str(hostile)


def test_a_neighbouring_repository_url_does_not_date_our_observation(
    upstream_and_clone: tuple[Path, Path], tmp_path: Path
) -> None:
    """A substring test cannot tell our remote from one that shares its prefix.

    `grep -F "branch 'main' of .../origin"` matches a FETCH_HEAD line for
    `.../origin-fork` too, so fetching the neighbour dated our unchanged
    observation as fresh - the our-thing-versus-a-neighbour's failure, inside the
    association fix written to close it (counter-model review pass 2).
    """
    origin, clone = upstream_and_clone
    fork = tmp_path / "origin-fork"
    subprocess.run(
        ["git", "clone", "--quiet", str(origin), str(fork)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(fork, "config", "user.email", "test@example.invalid")
    _git(fork, "config", "user.name", "Test")
    _commit(fork, "fork commit")

    _git(clone, "remote", "add", "fork", str(fork))
    _git(clone, "fetch", "--quiet", "fork")

    payload = _json(clone)
    assert payload["fetch_age_source"] != "fetch-head", (
        "a fetch of origin-fork is not evidence about origin"
    )


def test_quiet_qualifies_a_zero_gap_measured_against_old_evidence(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """`current` against a stale reference is not the same claim as `current`.

    Quiet mode said nothing for any `current` verdict whatever the evidence age,
    and install-drift --quiet forwards that silence to the session-start
    surface - so a checkout matching a three-day-old reference printed
    byte-identically to a freshly verified one.
    """
    _, clone = upstream_and_clone
    assert _run(clone, "--quiet").stdout.strip() == "", "fresh evidence stays quiet"

    ref = Path(_git(clone, "rev-parse", "--git-path", "FETCH_HEAD"))
    if not ref.is_absolute():
        ref = clone / ref
    ref.write_text("", encoding="utf-8")  # make FETCH_HEAD exist but not name origin
    packed = Path(_git(clone, "rev-parse", "--git-common-dir"))
    if not packed.is_absolute():
        packed = clone / packed
    stale = packed / "packed-refs"
    assert stale.is_file(), "a fresh clone packs its remote refs"
    old = time.time() - (5 * 24 * 3600)
    os.utime(stale, (old, old))

    spoken = _run(clone, "--quiet").stdout
    assert "last refreshed" in spoken
    assert "zero gap against old evidence" in spoken


def test_json_survives_a_path_containing_an_embedded_newline(tmp_path: Path) -> None:
    """sed works one newline-delimited record at a time, so it never sees them.

    `[[:cntrl:]]` therefore replaced every control character EXCEPT the record
    separators, and a value carrying one produced invalid JSON with exit 0.
    """
    hostile = tmp_path / "two\nlines"
    hostile.mkdir()
    _make_checkout_files(hostile)

    result = _run(hostile, "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)  # the assertion is that this parses
    assert "two lines" in payload["checkout"]


def test_the_report_emits_the_key_value_contract(
    upstream_and_clone: tuple[Path, Path],
) -> None:
    """Shell consumers read fields by key, never by regex over JSON.

    `install-drift` pulled these out of the JSON with sed, which truncates at the
    first escaped quote and then re-emitted the fragment into its own JSON.
    """
    _, clone = upstream_and_clone
    report = _run(clone).stdout
    for key in (
        "TOOLCHAIN_CHECKOUT=",
        "TOOLCHAIN_HEAD=",
        "TOOLCHAIN_UPSTREAM=",
        "TOOLCHAIN_BEHIND=",
        "TOOLCHAIN_AHEAD=",
        "TOOLCHAIN_FETCH_AGE=",
        "TOOLCHAIN_FETCH_AGE_SOURCE=",
    ):
        assert any(line.startswith(key) for line in report.splitlines()), key
    assert "TOOLCHAIN_PROVENANCE: current" in report
