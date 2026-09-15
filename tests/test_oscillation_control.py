"""The oscillation detector flags a knob that moved BACK, and only that (#936).

Acceptance item 2 from the issue, and the half that matters is the second one:

    "The control must report oscillation on a knob that reversed, AND must not
    report it on a knob tightened monotonically over time. The second half is
    the one that matters - a detector that flags every threshold edit is noise,
    and it will be disabled, which is itself an oscillation."

So every test here comes in pairs. A detector wedged at "found" passes the red
half of any of them; only the green half separates it from one that works.

THE CORPUS IS THE FIVE ROWS FROM THE ISSUE plus the two live specimens the
owner's ruling added. Each is reconstructed as a synthetic history with a known
verdict, because the real commits for several of them predate this repository's
current shape and one of them lives in a different repo entirely. The
reconstruction is of the SHAPE - a knob moved, then moved back, or moved twice
the same way - which is what the detector keys on.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-oscillation.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_oscillation", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CHECK = _load()


#: The fixtures replace PATH wholesale rather than extending it, so a repo built
#: here cannot be perturbed by whatever the caller had on theirs. That makes git
#: a CONSTRUCTED presence, and both the skip guard below and the assertion in
#: `_env` look it up on THIS path. Guarding on the ambient PATH would be a check
#: on a different environment from the one the fixture actually runs in - green
#: on a host where git sits in /usr/bin, FileNotFoundError on one where it does
#: not, and the guard that was supposed to skip would have said nothing.
FIXTURE_PATH = "/usr/bin:/bin"


def _env(home: Path) -> dict[str, str]:
    """A hermetic git environment. PATH is REPLACED, not extended (#697)."""
    assert shutil.which("git", path=FIXTURE_PATH) is not None, (
        f"the fixture PATH ({FIXTURE_PATH}) carries no git, so every repository "
        f"below would fail to build for a reason unrelated to the detector"
    )
    return {
        "PATH": FIXTURE_PATH, "HOME": str(home),
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
    }


def _repo(tmp_path: Path, revisions: list[str], filename: str = "config.py") -> Path:
    """A git repo whose one file takes each given content in turn."""
    repo = tmp_path / "r"
    repo.mkdir(parents=True)
    env = _env(tmp_path)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True,
                   capture_output=True, env=env)
    for i, body in enumerate(revisions):
        (repo / filename).write_text(body, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-qm", f"rev {i}"], cwd=repo, check=True,
                       capture_output=True, env=env)
    return repo


def _findings(repo: Path, window: int = 50) -> list[str]:
    moves, commits = CHECK.collect_moves(repo, "HEAD")
    assert commits > 0, "the fixture history is empty - this test checks nothing"
    return [f"{f.path}:{f.key}" for f in CHECK.find_oscillations(moves, window)]


pytestmark = pytest.mark.skipif(
    shutil.which("git", path=FIXTURE_PATH) is None,
    reason=f"git builds the fixtures and must be on the fixture PATH ({FIXTURE_PATH})",
)


# --------------------------------------------------------------------------- #
# The pair that is the whole acceptance criterion.
# --------------------------------------------------------------------------- #

def test_a_knob_that_reversed_IS_reported(tmp_path: Path) -> None:
    """RED. 30 -> 60 -> 30: loosened, then put back. The signature."""
    repo = _repo(tmp_path, ["timeout = 30\n", "timeout = 60\n", "timeout = 30\n"])
    assert _findings(repo) == ["config.py:timeout"]


def test_a_knob_tightened_MONOTONICALLY_is_NOT_reported(tmp_path: Path) -> None:
    """GREEN, and the half the issue says matters.

    60 -> 30 -> 10 is three edits to one threshold and is NOT oscillation. A
    detector that flags this flags every threshold edit, becomes noise, and
    gets disabled - which the issue names as itself an oscillation, performed
    by the control built to prevent oscillation.
    """
    repo = _repo(tmp_path, ["timeout = 60\n", "timeout = 30\n", "timeout = 10\n"])
    assert _findings(repo) == []


def test_a_knob_loosened_monotonically_is_NOT_reported(tmp_path: Path) -> None:
    """The same claim in the other direction, so 'monotonic' is not a synonym
    for 'tightening'. A steadily relaxed knob may be wrong, but it is not
    OSCILLATING, and reporting it here would blur the signature."""
    repo = _repo(tmp_path, ["retries = 1\n", "retries = 3\n", "retries = 9\n"])
    assert _findings(repo) == []


def test_a_knob_changed_only_once_is_NOT_reported(tmp_path: Path) -> None:
    """One move cannot be a reversal. Without this, 'changed' and 'changed
    back' collapse into the same finding."""
    repo = _repo(tmp_path, ["timeout = 30\n", "timeout = 60\n"])
    assert _findings(repo) == []


# --------------------------------------------------------------------------- #
# The corpus: the five rows from #936 plus the two live specimens.
# --------------------------------------------------------------------------- #

CORPUS = [
    pytest.param(
        "worktree-remove-force",
        ["force_allowed = 1\n", "force_allowed = 0\n", "force_allowed = 1\n"],
        True,
        id="row1-worktree-force-tightened-then-loosened",
    ),
    pytest.param(
        "flow-finish-gate-verdicts",
        ["exit 0\n", "exit 1\n", "exit 0\n"],
        True,
        id="row2-warn-exit-policy-reversed",
    ),
    pytest.param(
        "gitleaks-allowlist",
        ["paths = 12\n", "paths = 13\n", "paths = 14\n"],
        False,
        id="row3-allowlist-only-ever-widens",
    ),
    pytest.param(
        "group-launch-fail-open",
        ["fail_open = 1\n", "fail_open = 0\n", "fail_open = 1\n"],
        True,
        id="row4-fail-open-reversed",
    ),
    pytest.param(
        "process-ceremony-tier",
        ["tier = 3\n", "tier = 1\n", "tier = 3\n"],
        True,
        id="row5-ceremony-tier-reversed",
    ),
    pytest.param(
        "lane-overlap-exact-vs-containment",
        ["containment = 0\n", "containment = 1\n", "containment = 0\n"],
        True,
        id="live1-lane-overlap-reversed",
    ),
    pytest.param(
        "flow-helpers-unverifiable-exit",
        ["exit 0\n", "exit 1\n"],
        False,
        id="live2-unverifiable-exit-moved-once",
    ),
]


@pytest.mark.parametrize("name,revisions,expect_flag", CORPUS)
def test_the_issue_corpus_reproduces_by_hand(
    name: str, revisions: list[str], expect_flag: bool, tmp_path: Path
) -> None:
    """Acceptance item 3: "a detector that cannot reproduce them by hand is not
    ready."

    Row 3 is the important one. The gitleaks allowlist only ever GREW - fourteen
    entries, one added each time something tripped a heuristic. That is a real
    problem and it is NOT oscillation, so the detector must stay silent on it.
    A control corpus in which every row is positive proves only that the
    detector says yes.

    live2 is the exit-code decision made on #927 earlier today: moved ONCE, with
    its reversal trigger committed beside it. Not yet an oscillation, and it
    must not be reported as one - the trigger is what makes the next move
    legible, not this one.
    """
    repo = _repo(tmp_path, revisions, filename=f"{name}.conf")
    found = _findings(repo)
    if expect_flag:
        assert found == [f"{name}.conf:{list(CHECK._knobs(revisions[0]))[0]}"], (
            f"{name} reversed and was not reported: {found}"
        )
    else:
        assert found == [], f"{name} did not reverse but was reported: {found}"


def test_the_corpus_contains_BOTH_verdicts() -> None:
    """A corpus of all-positives cannot detect a detector wedged at 'found'.

    Asserted rather than assumed, because the corpus is the thing a later
    reader will extend, and extending it with positives only is the natural
    thing to do.
    """
    verdicts = {p.values[2] for p in CORPUS}
    assert verdicts == {True, False}, f"the corpus is one-sided: {verdicts}"


# --------------------------------------------------------------------------- #
# Extraction. Every case is a PAIR: one line that must yield a knob and one that
# must not, because an extractor tuned only on positives drifts into matching
# everything, and a knob series assembled from noise reverses constantly.
# --------------------------------------------------------------------------- #

EXTRACTION = [
    # (line, expected knobs)
    ("timeout = 30", {"timeout": 30.0}),
    # THE ONE THAT MATTERS. ADR 0009's strongest tell is a diff touching a line
    # whose adjacent comment explains why it is set that way - so an extractor
    # that cannot see a knob carrying an inline rationale is blind exactly where
    # the rule is strongest. The first cut required the value to be followed by
    # `,;)]` or end-of-line and returned NOTHING here.
    ("timeout = 30  # seconds, see ADR 0009", {"timeout": 30.0}),
    ("TIMEOUT=30 # why it is 30", {"TIMEOUT": 30.0}),
    # An ANNOTATED assignment must be keyed on the setting, not the type. Keyed
    # on `int`, every annotated knob in a file collapses into one series and
    # unrelated settings appear to swing against each other.
    ("timeout: int = 30", {"timeout": 30.0}),
    ("limit: float = 0.5  # tuned", {"limit": 0.5}),
    ("retries: 3,", {"retries": 3.0}),
    ("    --window 25 \\", {"--window": 25.0}),
    # A QUOTED key is the same setting. `.gitleaks.toml`, `control.json` and
    # every CI manifest here write it this way; unquoted-only, a JSON threshold
    # reversal produced no moves whatsoever.
    ('"timeout": 30,', {"timeout": 30.0}),
    ("'retries' = 5", {"retries": 5.0}),
    # A UNIT-BEARING value is not a number. Without a boundary `--timeout 1m`,
    # `--timeout 60s` and `--timeout 2m` read as 1, 60 and 2, so a duration that
    # stayed equal and then grew reported as a REVERSAL. No number beats a
    # wrong one.
    ("    --timeout 1m", {}),
    ("    --timeout 60s", {}),
    ("    --timeout 60", {"--timeout": 60.0}),
    # An ANNOTATION must not reach across a parameter separator. Allowing a
    # top-level comma in the type made `def f(timeout: int, retries=3)` read as
    # `{"timeout": 3}` AND suppress the correct `retries` reading, so moving
    # retries 3 -> 5 -> 3 reported an oscillation against a setting that never
    # changed. A finding naming the wrong line is the costliest failure here.
    ("def f(timeout: int, retries=3):", {"retries": 3.0}),
    ("def g(a: int, b=3, c=4):", {"b": 3.0, "c": 4.0}),
    ("x: int | None = 5", {"x": 5.0}),
    ("y: dict[str, int] = 3", {"y": 3.0}),
    # A value must END, not merely stop looking like a word. `(?![\w.])` alone
    # let an operator or a unit follow, so `60 * 60` then `120 * 30` then
    # `60 * 120` reported a reversal of a timeout that never changed - and a
    # quoted duration walked through the exclusion this detector claims for
    # duration strings.
    ("timeout = 60 * 60", {}),
    ("timeout = 120 * 30", {}),
    ('delay = "1 minute"', {}),
    ('delay = "60 seconds"', {}),
    ("port = 8080/tcp", {}),
    ("exit 3", {"exit": 3.0}),
    ("    self.timeout = 30", {"self.timeout": 30.0}),
    ("SEVERITY_THRESHOLD = 0.85", {"SEVERITY_THRESHOLD": 0.85}),
    # NEGATIVES. A partial number is not a knob...
    ("version = 1.2.3", {}),
    ("sha = 3f2a", {}),
    # ...and PROSE about exit codes is not a knob. This repository's docs
    # discuss exit codes constantly; unanchored, every one of them became a
    # knob named `exit` whose value swung between paragraphs, which is how a
    # reporting detector earns being ignored.
    ("the gate must exit 3 when it cannot look", {}),
    ("- check-oscillation: `unknown` must exit 3, never exit 0", {}),
]


@pytest.mark.parametrize("line,expected", EXTRACTION, ids=[c[0][:40] for c in EXTRACTION])
def test_knob_extraction(line: str, expected: dict[str, float]) -> None:
    assert CHECK._knobs(line) == expected


def test_the_extraction_corpus_contains_BOTH_verdicts() -> None:
    """Same guard as the history corpus, one layer down: an extractor corpus of
    positives only cannot detect an extractor that matches everything."""
    kinds = {bool(exp) for _, exp in EXTRACTION}
    assert kinds == {True, False}, f"the extraction corpus is one-sided: {kinds}"


# --------------------------------------------------------------------------- #
# Telling OUR setting from its NEIGHBOUR. Every one of these was a Codex
# pre-PR finding: the detector reported, or could report, a swing that no single
# setting performed.
# --------------------------------------------------------------------------- #

def test_two_call_sites_sharing_a_NAME_are_not_one_knob(tmp_path: Path) -> None:
    """`(path, key)` is not an identity.

    One file, two sites both spelling `timeout`. The first is tightened once;
    much later the second is loosened once. NEITHER reversed - but keyed on the
    name alone they form a single series that appears to swing, and the finding
    would name a file whose settings only ever moved one way each.

    This is detector-contract question 2 - can a non-zero distinguish OUR thing
    changing from a NEIGHBOUR's - answered on the detector itself.
    """
    repo = _repo(tmp_path, [
        "first(timeout=60)\nsecond(timeout=10)\n",
        "first(timeout=30)\nsecond(timeout=10)\n",   # site 1 tightened
        "first(timeout=30)\nsecond(timeout=20)\n",   # site 2 loosened
    ])
    assert _findings(repo) == [], (
        "two independent single moves at different call sites were merged into "
        "one reversal; neither site changed back"
    )


def test_a_CONTINUOUS_reversal_at_one_site_is_still_reported(tmp_path: Path) -> None:
    """The green half of the pair above.

    Continuity is what separates our setting from its neighbour, so it has to be
    shown NOT to have silenced the real signature - otherwise the fix for a
    false positive is just a wedge at `none`.
    """
    repo = _repo(tmp_path, [
        "first(timeout=60)\nsecond(timeout=10)\n",
        "first(timeout=30)\nsecond(timeout=10)\n",
        "first(timeout=60)\nsecond(timeout=10)\n",
    ])
    assert _findings(repo) == ["config.py:timeout"]


def test_an_INTERVENING_site_does_not_hide_a_real_reversal(tmp_path: Path) -> None:
    """The cost of the continuity fix, paid back.

    Continuity checked between ADJACENT moves only silences a real swing the
    moment anything lands between its halves: first 60 -> 30, second 10 -> 20,
    first 30 -> 60. Neither adjacent pair is continuous, so nothing was
    reported - the first site genuinely reversed and the detector said `none`.

    The moves have to be threaded into per-site CHAINS before the direction
    test, not filtered pairwise after it. Without this test the fix for a false
    positive is indistinguishable from a wedge at `none`.
    """
    repo = _repo(tmp_path, [
        "first(timeout=60)\nsecond(timeout=10)\n",
        "first(timeout=30)\nsecond(timeout=10)\n",   # site 1 tightens
        "first(timeout=30)\nsecond(timeout=20)\n",   # site 2 moves, unrelated
        "first(timeout=60)\nsecond(timeout=20)\n",   # site 1 changes BACK
    ])
    assert _findings(repo) == ["config.py:timeout"], (
        "a real reversal at one site was hidden by an unrelated move at another"
    )


def test_a_reversal_DELIVERED_BY_MERGES_is_reported(tmp_path: Path) -> None:
    """--first-parent must not be paired with --no-merges.

    Together they drop every change DELIVERED BY a merge commit, not merely
    those introduced by conflict resolution. On a repository that merges pull
    requests rather than squashing them, two PRs taking a setting 30 -> 60 -> 30
    produced no moves at all: total blindness, reading as `none`.

    The sibling of the divergent-branches test below - that one proves the
    lineage is not too WIDE, this one proves it is not too NARROW. Either alone
    is satisfied by a broken traversal.
    """
    env = _env(tmp_path)
    repo = _repo(tmp_path, ["timeout = 30\n"])

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)

    for value in ("60", "30"):
        git("checkout", "-qb", f"pr-{value}")
        (repo / "config.py").write_text(f"timeout = {value}\n", encoding="utf-8")
        git("commit", "-aqm", f"pr sets it to {value}")
        git("checkout", "-q", "main")
        git("merge", "-q", "--no-ff", "-m", f"merge pr-{value}", f"pr-{value}")

    merges = subprocess.run(["git", "log", "--first-parent", "--merges", "--oneline"],
                            cwd=repo, capture_output=True, text=True, env=env).stdout
    assert len(merges.strip().splitlines()) == 2, (
        f"the fixture did not produce two merge commits, so it cannot test "
        f"whether merge-delivered changes are seen: {merges!r}"
    )

    assert _findings(repo) == ["config.py:timeout"], (
        "a reversal delivered through two ordinary merge commits was not seen"
    )


def test_two_BRANCHES_moving_a_shared_base_are_not_a_reversal(tmp_path: Path) -> None:
    """`--no-merges` alone lists both sides of a merge and interleaves them.

    Main takes 30 -> 60; a branch cut from the same base takes 30 -> 10. Neither
    changed BACK, but read as successive states of one setting they render as a
    swing. The lineage this detector is for is the integrated branch, so it
    walks --first-parent.
    """
    env = _env(tmp_path)
    repo = _repo(tmp_path, ["timeout = 30\n"])

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)

    git("checkout", "-qb", "side")
    (repo / "config.py").write_text("timeout = 10\n", encoding="utf-8")
    git("commit", "-aqm", "side lowers it")
    git("checkout", "-q", "main")
    (repo / "config.py").write_text("timeout = 60\n", encoding="utf-8")
    git("commit", "-aqm", "main raises it")
    git("merge", "-q", "--no-ff", "-m", "merge side", "-X", "ours", "side")

    moves, commits = CHECK.collect_moves(repo, "HEAD")
    assert commits >= 2, "the fixture history is too short to say anything"
    assert not any(m.sha for m in moves if m.subject == "side lowers it"), (
        "a commit off the first-parent line was walked; --first-parent is not "
        "in effect and both sides of the merge are being read as one series"
    )
    assert CHECK.find_oscillations(moves, 50) == [], (
        "two branches moving a shared base in opposite directions were reported "
        "as a reversal; neither branch changed anything back"
    )


def test_a_QUOTED_path_does_not_land_on_its_neighbour(tmp_path: Path) -> None:
    """git quotes paths holding tabs or (by default) non-ASCII bytes.

    Matching only `+++ b/` left `path` pointing at the PREVIOUS file, so the
    quoted file's hunks were attributed to its neighbour - a reversal reported
    against a file that never reversed. The fix downgrades that to a miss.
    """
    env = _env(tmp_path)
    repo = tmp_path / "r"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True,
                   capture_output=True, env=env)
    plain, quoted = "a-plain.conf", "z-caf\u00e9.conf"
    series = [("30", "30"), ("20", "60"), ("10", "30")]
    for tight, swing in series:
        (repo / plain).write_text(f"timeout = {tight}\n", encoding="utf-8")
        (repo / quoted).write_text(f"timeout = {swing}\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True, env=env)
        subprocess.run(["git", "commit", "-qm", "rev"], cwd=repo, check=True,
                       capture_output=True, env=env)

    raw = subprocess.run(["git", "log", "-p", "--unified=0"], cwd=repo,
                         capture_output=True, text=True, env=env).stdout
    assert '+++ "b/' in raw, (
        "git did not quote the path, so this test is not exercising the quoted "
        "header at all"
    )

    moves, _ = CHECK.collect_moves(repo, "HEAD")
    mine = [m for m in moves if m.path == plain]
    assert [(m.before, m.after) for m in mine] == [(30.0, 20.0), (20.0, 10.0)], (
        f"the monotonic file was credited with moves it did not make: {mine}"
    )
    assert _findings(repo) == [], (
        f"{plain} only ever tightened, yet a finding names it"
    )


def test_a_STRING_allowlist_entry_is_outside_the_detector(tmp_path: Path) -> None:
    """The scope, pinned as a property rather than left as prose.

    The module header used to claim "allowlist membership" among what it
    derives. It never extracted it - `_knobs` reads numbers - so adding a string
    entry and later removing it yields NO moves, and with any unrelated numeric
    move in range the run prints `none`: a clean-looking verdict about a
    population that never contained the thing.

    Asserted so the claim cannot quietly come back, and so the day someone
    IMPLEMENTS membership this test fails and asks to be rewritten. Membership
    reversals are the DIRECTIVE's job (ADR 0009), not this detector's.
    """
    repo = _repo(tmp_path, [
        'paths = ["one"]\n',
        'paths = ["one", "two"]\n',
        'paths = ["one"]\n',
    ], filename="allow.toml")
    moves, commits = CHECK.collect_moves(repo, "HEAD")
    assert commits == 3, "the fixture history is empty - this test checks nothing"
    assert [m for m in moves if m.key == "paths"] == [], (
        "membership is now extracted; ADR 0009, docs/scripts.md and the module "
        "header all state it is NOT, so update them together with this test"
    )

    # No text assertion accompanies this one. The first cut grepped the module
    # header for "allowlist membership" to stop the claim returning - and it
    # fired immediately, because the header now DISCUSSES membership in order to
    # disclaim it. Documenting a limit well makes a text guard about that limit
    # more false-positive, not less; the behavioural assertion above is the one
    # that means anything.


# --------------------------------------------------------------------------- #
# The detector's own honesty.
# --------------------------------------------------------------------------- #

def test_two_opposing_edits_in_ONE_commit_are_not_an_oscillation(tmp_path: Path) -> None:
    """A swing is across time, not within a single change.

    The first cut had no such rule and reported a lockfile's package sizes,
    both "moves" carrying the same sha. Found by running the detector against
    this repository's real history rather than only against fixtures.
    """
    repo = _repo(tmp_path, ["a = 1\nb = 1\n"])
    env = _env(tmp_path)
    (repo / "config.py").write_text("a = 5\nb = 1\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-aqm", "up"], cwd=repo, check=True,
                   capture_output=True, env=env)
    (repo / "config.py").write_text("a = 1\nb = 1\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-aqm", "back"], cwd=repo, check=True,
                   capture_output=True, env=env)
    # Across commits this IS an oscillation...
    assert _findings(repo) == ["config.py:a"]

    # ...but the same two values inside one commit are not.
    #
    # PRECONDITION, and the reason it is asserted rather than assumed: the first
    # cut of this half built a TWO-revision fixture, which yields ONE move. One
    # move cannot form a pair, so find_oscillations() returned [] whatever the
    # same-sha rule said, and the assertion below passed on a detector with the
    # rule deleted. Found by mutation, not by reading - deleting `if a.sha ==
    # b.sha: continue` left all 16 tests green. A count here is what makes this
    # assertion about the sha rule instead of about the fixture's size.
    moves, _ = CHECK.collect_moves(repo, "HEAD")
    opposed = [m for m in moves if m.key == "a"]
    assert len(opposed) == 2, (
        f"this assertion needs a PAIR of opposing moves to say anything about "
        f"the same-sha rule; the fixture produced {len(opposed)}"
    )
    assert opposed[0].direction == -opposed[1].direction, "the pair does not oppose"
    assert opposed[0].sha != opposed[1].sha, "the fixture's moves already share a sha"

    for m in opposed:
        m.sha = "same"
    assert CHECK.find_oscillations(opposed, 50) == [], (
        "two opposing moves carrying ONE sha were reported as an oscillation; "
        "that is a single change settling on a value, not a swing across time"
    )


def test_an_empty_population_is_UNKNOWN_and_not_none(tmp_path: Path) -> None:
    """#952 applied to this script: scanned nothing is not clean.

    Exit 3, not 0, and the word is `unknown`. "I examined 400 knob changes and
    none reversed" and "I examined nothing" must not share either.
    """
    repo = _repo(tmp_path, ["# no knobs here\n"])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(repo), "--range", "HEAD"],
        capture_output=True, text=True,
    )
    assert "OSCILLATION: unknown" in proc.stdout, proc.stdout
    assert "OSCILLATION_EXAMINED: 0" in proc.stdout
    assert proc.returncode == CHECK.EXIT_UNKNOWN, (
        f"an unexaminable run must not exit 0: got {proc.returncode}"
    )


def test_the_FOUR_ways_of_not_looking_are_told_apart(tmp_path: Path) -> None:
    """One verdict, one exit code, four distinguishable REASONS (#953).

    A range git REFUSES (`HEAD~200` on a short history) and a range that
    resolves to a real history with no knob edits are both "could not look" -
    but a reader chasing the first goes hunting for knobs that were never the
    problem. The first cut printed the same line for both.

    Asserting the reasons are DISTINCT rather than asserting each string: the
    point is discrimination, and four identical labels would satisfy four
    separate equality checks written one at a time.
    """
    def reason_of(root: Path, rev_range: str) -> tuple[str, int]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), "--range", rev_range],
            capture_output=True, text=True,
        )
        assert "OSCILLATION: unknown" in proc.stdout, proc.stdout
        line = [ln for ln in proc.stdout.splitlines()
                if ln.startswith("OSCILLATION_REASON: ")]
        assert len(line) == 1, f"no single reason line: {proc.stdout}"
        return line[0].split(": ", 1)[1], proc.returncode

    plain = tmp_path / "plain"
    plain.mkdir()
    knobless = _repo(tmp_path / "a", ["# no knobs here\n"])
    short = _repo(tmp_path / "b", ["timeout = 30\n", "timeout = 60\n"])

    observed = {
        "not-a-git-repository": reason_of(plain, "HEAD"),
        "range-unresolvable": reason_of(short, "HEAD~200..HEAD"),
        "range-empty": reason_of(short, "HEAD..HEAD"),
        "no-knob-changes": reason_of(knobless, "HEAD"),
    }

    for expected, (actual, rc) in observed.items():
        assert actual == expected, f"expected reason {expected!r}, got {actual!r}"
        assert rc == CHECK.EXIT_UNKNOWN, f"{expected} must exit 3, got {rc}"

    reasons = {actual for actual, _ in observed.values()}
    assert len(reasons) == 4, (
        f"the four ways of failing to look collapsed into {len(reasons)} "
        f"label(s) ({reasons}); a reason field that does not discriminate is "
        f"decoration"
    )


def test_a_FINDING_never_fails_the_build(tmp_path: Path) -> None:
    """The owner's ruling, pinned.

    A blocking detector that flags every threshold edit gets switched off, and
    switching it off is itself an oscillation. So the exit code for `found` is
    0 - deliberately, and distinctly from the `unknown` case above, which is
    the one that DOES fail.
    """
    repo = _repo(tmp_path, ["timeout = 30\n", "timeout = 60\n", "timeout = 30\n"])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(repo), "--range", "HEAD"],
        capture_output=True, text=True,
    )
    assert "OSCILLATION: found" in proc.stdout, proc.stdout
    assert proc.returncode == CHECK.EXIT_REPORTED, (
        "a finding must REPORT, not fail - a blocking detector gets disabled, "
        "which is the oscillation this control exists to prevent"
    )


def test_a_NON_REPOSITORY_is_UNKNOWN_and_not_none(tmp_path: Path) -> None:
    """The other way this run can be unable to look.

    Distinct from the empty-population case above: there, git answered and the
    history held no knob edits; here git cannot answer at all. Both must read
    UNKNOWN, and for a while only the first was tested - deleting the `unknown`
    verdict from THIS branch left every test green. That is the shape #952 is
    about, arriving through the door nobody checked.
    """
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    probe = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=plain,
                           capture_output=True, text=True)
    assert probe.returncode != 0, (
        "the fixture directory is inside a git repository, so this test is not "
        "exercising the no-history path at all"
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(plain), "--range", "HEAD"],
        capture_output=True, text=True,
    )
    assert "OSCILLATION: unknown" in proc.stdout, proc.stdout
    assert proc.returncode == CHECK.EXIT_UNKNOWN, (
        f"a run with no readable history must not exit 0: got {proc.returncode}"
    )


def test_the_window_actually_BOUNDS_which_pairs_are_reported(tmp_path: Path) -> None:
    """The --window threshold has to DO something, not just carry a comment.

    This control is subject to its own rule, and the rule is not satisfied by a
    setting whose reversal trigger is committed beside a value nothing reads.
    Widening the window must be able to change a verdict, or the trigger names
    an adjustment that cannot be made.

    Two-sided by construction: the SAME history, one window that reports it and
    one that does not.
    """
    revisions = ["timeout = 30\n# filler 0\n", "timeout = 60\n# filler 0\n"]
    revisions += [f"timeout = 60\n# filler {i}\n" for i in range(1, 6)]
    revisions += ["timeout = 30\n# filler 5\n"]
    repo = _repo(tmp_path, revisions)

    moves, _ = CHECK.collect_moves(repo, "HEAD")
    pair = [m for m in moves if m.key == "timeout"]
    assert len(pair) == 2, f"the fixture must produce exactly one pair, got {len(pair)}"
    distance = pair[1].ordinal - pair[0].ordinal
    assert distance == 6, f"the fixture's separation drifted: {distance}"

    assert _findings(repo, window=distance) == ["config.py:timeout"], (
        "a reversal exactly at the window edge must still be reported"
    )
    assert _findings(repo, window=distance - 1) == [], (
        "--window does not bound anything: a pair further apart than the window "
        "was still reported, so the threshold is decoration"
    )


def test_the_explicit_diff_merges_flag_is_present() -> None:
    """A GUARD ON INTENT, and weaker than every other test in this file.

    It asserts on argv text rather than on behaviour, because the behaviour it
    protects cannot be produced on this host: git has implied
    --diff-merges=first-parent from --first-parent since 2.36, and this box runs
    2.43, so deleting the flag changes no output and kills no test. On git
    2.31-2.35 it is the difference between reading merge diffs and reading
    nothing at all.

    Said plainly rather than dressed up: a reader who takes this for a
    behavioural check will over-trust it. It exists so the flag is not tidied
    away as redundant by someone measuring only on a modern git - the same shape
    as a check whose input is host state, load-bearing in one environment and
    inert in another.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"--diff-merges=first-parent"' in text, (
        "the explicit --diff-merges flag is gone; on git < 2.36 merge-delivered "
        "changes then vanish silently and the run reports `none`"
    )
    assert '"--no-merges"' not in text, (
        "--no-merges is back alongside --first-parent; together they drop every "
        "change delivered BY a merge commit, not only merge-resolution ones"
    )


def test_the_window_threshold_carries_its_own_reversal_trigger() -> None:
    """This control is subject to its own rule (#936 acceptance item 1).

    `--window` is a threshold, which is one of the issue's own tells. A control
    that exempts itself from its own directive is the most conspicuous possible
    way to fail, so the trigger is required to be present beside the setting -
    not in a PR body, which the next person to touch the line will not read.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    before = text.index("DEFAULT_WINDOW = ")
    window_comment = text[max(0, before - 1200):before]
    assert "REVERSAL TRIGGER" in window_comment, (
        "the --window threshold has no committed reversal trigger beside it"
    )
