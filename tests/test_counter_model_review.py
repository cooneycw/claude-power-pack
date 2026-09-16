"""The counter-model stage is an instrument and does not ship green (#934).

Acceptance item 1, and the half that matters is the second one:

    "Seed a branch with a known defect of a class the reviewer should catch.
    Assert the stage REPORTS it. Then remove the defect and assert the stage
    reports CLEAN on the same branch. Both directions: a reviewer wedged at
    'findings' is as useless as one wedged at 'clean', and the first check alone
    passes for both."

So the transcript tests come in pairs, from RECORDED reviews of the same file -
see tests/fixtures/counter_model/README.md for how they were produced and what
they deliberately do not cover.

WHAT THIS FILE DOES NOT TEST. It does not exercise the reviewing model's
judgement. Neither `codex` nor `git` is in the CI image, a live call spends the
user's quota, and the reviewer is not deterministic across runs. The reviewer
was run once on each side of the pair, its answers committed, and what CI checks
is the STAGE's handling of them. Stated here rather than left for a reader to
infer from the absence of a network call.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "counter-model-receipt.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "counter_model"
COMMANDS = ROOT / ".claude" / "commands"


def _load():
    spec = importlib.util.spec_from_file_location("counter_model_receipt", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CM = _load()


def _fixture(name: str) -> str:
    path = FIXTURES / name
    assert path.exists(), f"missing fixture {path}"
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Acceptance item 1: the pair. Neither half means anything alone.
# --------------------------------------------------------------------------- #

def test_a_seeded_defect_IS_reported() -> None:
    """RED. The recorded review of the defective file names the seeded bug."""
    verdict, findings = CM.parse_review(_fixture("defect-present.review.md"))
    assert verdict == CM.PARSE_FINDINGS
    assert len(findings) == 1
    assert findings[0]["severity"] == "MEDIUM"
    # THE PARSED RESULT, not the fixture. The first cut re-read the transcript
    # and searched THAT for "empty" - which is a statement about the file on
    # disk, not about anything parse_review returned. Replacing every returned
    # title with "Unrelated invented finding" left it passing, so it protected
    # finding identity against nothing at all.
    assert "empty names" in findings[0]["title"].lower(), (
        f"the parsed finding is not about the seeded defect: {findings[0]['title']!r}"
    )


def test_the_same_file_WITHOUT_the_defect_is_clean() -> None:
    """GREEN, and the half the issue says matters.

    A stage wedged at "findings" passes the red half above. Only this separates
    it from one that works.
    """
    verdict, findings = CM.parse_review(_fixture("defect-removed.review.md"))
    assert verdict == CM.PARSE_CLEAN
    assert findings == []


def test_the_pair_reviews_THE_SAME_SUBJECT() -> None:
    """Otherwise the pair proves nothing about the defect.

    Two transcripts about two different files would satisfy both halves above
    while saying nothing about whether removing the defect is what changed the
    verdict. The patches must differ ONLY in the seeded line.
    """
    present = _fixture("defect-present.patch").splitlines()
    removed = _fixture("defect-removed.patch").splitlines()

    def body(lines: list[str]) -> list[str]:
        # Drop diff metadata (index hashes differ by construction).
        return [ln for ln in lines if ln.startswith("+") and not ln.startswith("+++")]

    b_present, b_removed = body(present), body(removed)
    differing = [
        (a, b) for a, b in zip(b_present, b_removed) if a != b
    ]
    assert len(b_present) == len(b_removed), "the two patches are different shapes"
    assert len(differing) == 1, (
        f"the pair differs in {len(differing)} lines, not 1; it is not a "
        f"controlled comparison: {differing}"
    )
    assert "is None" in differing[0][0] and "not name" in differing[0][1]


# --------------------------------------------------------------------------- #
# The zero that is not a clean bill of health.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("fixture", ["absent.review.md", "truncated.review.md",
                                     "prose-only.review.md"])
def test_a_transcript_that_says_nothing_is_UNPARSEABLE_not_clean(fixture: str) -> None:
    """All three hold zero finding headings, exactly like a clean review.

    A reviewer that crashed, was cut off, or answered in some other shape must
    not be recorded as having examined the change and found it sound. #952's
    denominator convention, applied to a review.
    """
    verdict, findings = CM.parse_review(_fixture(fixture))
    assert verdict == CM.PARSE_UNPARSEABLE, (
        f"{fixture} was read as {verdict!r}; a transcript with no findings and "
        f"no clean statement has not established anything"
    )
    assert findings == []


def test_the_transcript_corpus_contains_ALL_THREE_verdicts() -> None:
    """A corpus of one verdict cannot detect a parser wedged at that verdict.

    Asserted rather than assumed, because the natural way to extend this corpus
    later is with more of whichever case you were thinking about.
    """
    verdicts = {CM.parse_review(p.read_text(encoding="utf-8"))[0]
                for p in FIXTURES.glob("*.review.md")}
    assert verdicts == {CM.PARSE_FINDINGS, CM.PARSE_CLEAN, CM.PARSE_UNPARSEABLE}, (
        f"the fixture corpus covers only {verdicts}"
    )


def test_a_real_multi_severity_review_parses() -> None:
    """The recorded first-pass review of PR #1000: seven findings, real body."""
    verdict, findings = CM.parse_review(_fixture("real-multi-finding.review.md"))
    assert verdict == CM.PARSE_FINDINGS
    assert len(findings) == 7
    assert {f["severity"] for f in findings} >= {"HIGH", "MEDIUM"}


# --------------------------------------------------------------------------- #
# The receipt. Item 3: counts queryable across runs, not only in a PR body.
# --------------------------------------------------------------------------- #

def _write(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "write", "--dir", str(tmp_path), *args],
        capture_output=True, text=True,
    )


def test_a_SKIP_is_recorded_not_omitted(tmp_path: Path) -> None:
    """The orchestrator's condition E, and the issue's whole premise.

    A skip with a receipt is a state. A skip without one is indistinguishable
    from a stage that was never wired in - which is the condition #934 was
    opened about: 0 of 170 merged PRs, with nothing anywhere recording it.
    """
    proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "skipped",
                  "--reason", "reviewer-unavailable",
                  "--reviewer", "codex/gpt-5.5", "--implementer", "claude/opus-5")
    assert proc.returncode == 0, proc.stderr
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1, "a skip wrote no receipt"
    receipt = json.loads(written[0].read_text(encoding="utf-8"))
    assert receipt["status"] == "skipped"
    assert receipt["skip_reason"] == "reviewer-unavailable"


def test_a_skip_must_say_WHICH_skip(tmp_path: Path) -> None:
    """"Not installed" and "invoked, returned nothing usable" say different
    things about whether the stage works. A free-text reason would let them
    share a bucket.

    (#1015 removed "someone decided not to" from the set entirely - it is no
    longer one of the things a reason has to distinguish.)"""
    proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "skipped",
                  "--reviewer", "codex/gpt-5.5", "--implementer", "claude/opus-5")
    assert proc.returncode == CM.EXIT_USAGE, proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_codex_absent_is_a_DISTINCT_skip_reason(tmp_path: Path) -> None:
    """#1015's green half: the reason the probe exists to record is accepted."""
    proc = _write(tmp_path, "--issue", "1015", "--branch", "b", "--status", "skipped",
                  "--reason", "codex-absent",
                  "--reviewer", "codex/gpt-5.5", "--implementer", "claude/opus-5")
    assert proc.returncode == 0, proc.stderr
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1, "a codex-absent skip wrote no receipt"
    assert json.loads(written[0].read_text(encoding="utf-8"))["skip_reason"] == "codex-absent"


@pytest.mark.parametrize("removed", ["no-diff", "explicit-opt-out"])
def test_a_removed_reason_is_REFUSED_at_the_write_path(tmp_path: Path, removed: str) -> None:
    """#1015's red half at the CLI: the reasons that left the set cannot re-enter
    through the front door."""
    proc = _write(tmp_path, "--issue", "1015", "--branch", "b", "--status", "skipped",
                  "--reason", removed,
                  "--reviewer", "codex/gpt-5.5", "--implementer", "claude/opus-5")
    assert proc.returncode != 0, f"{removed!r} was accepted as a skip reason"
    assert list(tmp_path.glob("*.json")) == [], "a refused receipt was written anyway"


@pytest.mark.parametrize("removed", ["no-diff", "explicit-opt-out"])
def test_a_removed_reason_is_REFUSED_on_a_receipt_ALREADY_ON_DISK(
    tmp_path: Path, removed: str
) -> None:
    """The load-bearing case, and the reason the two above are not enough.

    Deleting a member from a tuple and commenting it out look identical in a
    diff, and both leave every OTHER test green. What distinguishes them is
    whether a receipt that already carries the removed reason - written before
    #1015, or by hand - is now REJECTED rather than validated.

    The receipt is produced by the tool itself and then mutated, so the fixture
    cannot drift out of schema and pass for the wrong reason: every field but
    `skip_reason` is one the current writer emits.
    """
    proc = _write(tmp_path, "--issue", "1015", "--branch", "b", "--status", "skipped",
                  "--reason", "reviewer-unavailable",
                  "--reviewer", "codex/gpt-5.5", "--implementer", "claude/opus-5")
    assert proc.returncode == 0, proc.stderr
    receipt_path = next(iter(tmp_path.glob("*.json")))

    # Control the control: it validates clean BEFORE the mutation.
    clean = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert clean.returncode == 0, f"the unmutated receipt already fails: {clean.stderr}"

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["skip_reason"] = removed
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == CM.EXIT_INVALID, (
        f"validate accepted a receipt carrying the removed reason {removed!r}; "
        "the member was taken out of SKIP_REASONS without being enforced"
    )
    assert removed in (proc.stdout + proc.stderr)


def test_the_CAPABILITY_PROBE_precedes_the_invocation(tmp_path: Path) -> None:
    """#1015: the inability to run codex is established BEFORE the invocation,
    not inferred from its wreckage.

    Without the probe, an absent codex is discovered by invoking it and reading
    the debris, which lands in `reviewer-unavailable` - the reason that means
    "invoked, returned nothing usable". Two different facts, one label.

    Doc-level, because the probe lives in a prompt document: the enforceable
    artifact IS the text. The probe must appear in Step 6 item 1a, and it must
    be stated as additive so a present-but-dead codex still reaches
    `reviewer-unavailable`.
    """
    text = _flat(_auto())
    assert "command -v codex" in text, (
        "Step 6 never probes for codex, so an absent binary is still "
        "discovered by invoking it and reading the failure"
    )
    assert "codex-absent" in text
    assert "ADDITIVE, never a replacement" in text, (
        "the probe is not stated as additive; a present-but-dead codex could "
        "be recorded as codex-absent, which is the wrong inability"
    )


def test_the_REVIEWER_COMMAND_does_not_skip_an_empty_diff_either() -> None:
    """Codex, MEDIUM, on this very change: the caller was fixed and the callee
    was not.

    `/flow:auto` Step 6 now says an empty diff gets an ordinary review. But
    `/codex:code_review` carried its own early exit - "If the diff is empty,
    report 'nothing to review vs $BASE' and stop (exit 0)" - which returns no
    findings report at all. Step 1c parses that as `unparseable` and records
    `skipped / reviewer-unavailable`: a skip whose reason names an inability
    that never happened, reached through the callee rather than the caller.

    Removing a skip from one document and leaving it in the one that document
    delegates to is not a removal. This holds both halves together.

    The shallow-clone guard above it is UNAFFECTED and must stay: an
    unresolvable merge base still exits 3 before this path, which is what
    test_a_failed_merge_base_does_not_become_an_empty_clean_review pins.
    """
    review = (COMMANDS / "codex" / "code_review.md").read_text(encoding="utf-8")
    stop_instruction = 'report "nothing to review vs $BASE" and stop'
    assert stop_instruction not in review, (
        "code_review.md still stops on an empty diff, so /flow:auto's promise "
        "that an empty diff is reviewed is defeated by its own reviewer command"
    )
    assert "An empty diff is still handed to the reviewer" in review
    # The shallow-clone guard is a DIFFERENT exit and must survive this change.
    assert "no common ancestor" in review, (
        "the merge-base guard was removed along with the empty-diff exit; an "
        "unresolvable base must still exit 3, not reach the reviewer"
    )


def test_the_PROPERTY_is_enforced_not_just_documented(tmp_path: Path) -> None:
    """"The reviewing model must not be the implementing model" is the rule the
    issue asks for as a PROPERTY rather than a tool name.

    A run whose reviewer IS the implementer is the author agreeing with
    themselves, recorded as independent evidence - worse than no receipt at all,
    because it is counted.
    """
    proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "ran",
                  "--reviewer", "claude/opus-5", "--implementer", "claude/opus-5",
                  "--passes", "1")
    assert proc.returncode == CM.EXIT_INVALID, proc.stdout
    assert "must not be the implementing model" in proc.stderr
    assert list(tmp_path.glob("*.json")) == [], "a refused receipt was written anyway"


def test_a_DIFFERENT_reviewer_is_accepted(tmp_path: Path) -> None:
    """The green half: the check must reject the violation and nothing else."""
    proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "ran",
                  "--reviewer", "codex/gpt-5.5", "--implementer", "claude/opus-5",
                  "--passes", "2", "--accepted", "3", "--rejected", "1",
                  "--red-cases-proposed", "4", "--red-cases-already-covered", "3")
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["counts"] == {"accepted": 3, "rejected": 1, "deferred": 0}
    assert receipt["red_cases"] == {"proposed": 4, "already_covered": 3}


def test_coverage_cannot_exceed_what_was_proposed(tmp_path: Path) -> None:
    """The diversity number is already_covered / proposed, and it is the only
    thing that can tell an excellent reviewer from an uncritical author. A ratio
    above 1 corrupts that silently rather than loudly."""
    proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "ran",
                  "--reviewer", "codex/gpt-5.5", "--implementer", "claude/opus-5",
                  "--passes", "1", "--red-cases-proposed", "2",
                  "--red-cases-already-covered", "5")
    assert proc.returncode == CM.EXIT_INVALID
    assert "exceeds proposed" in proc.stderr


def test_an_EMPTY_receipt_directory_is_unknown_not_ok(tmp_path: Path) -> None:
    """"No receipts" and "no receipts with problems" are different facts.

    Conflating them is how 0 of 170 went unnoticed for two months.
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert "COUNTER_MODEL_RECEIPTS: unknown" in proc.stdout, proc.stdout
    assert proc.returncode != 0


def test_every_COMMITTED_receipt_is_well_formed_AND_TRACKED() -> None:
    """The receipts in the tree are the record.

    TRACKED, not merely present on disk. `.gitignore` carries a blanket `*.json`
    rule, and `git add` no-ops on an ignored path with no error - so the first
    receipt written here was invisible to git while this test read it happily
    off the filesystem and reported `ok`. In a clean clone there would have been
    no receipts at all and the validator would have said `unknown`: green here,
    red where it gates, which is the same failure this repository hit on #936
    and #953 and #924 before that.

    A validator that reads the working tree cannot see the difference. `git
    ls-files` can.
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "validate"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert "COUNTER_MODEL_RECEIPTS: ok" in proc.stdout, proc.stdout
    assert proc.returncode == 0, proc.stdout

    if shutil.which("git") is None:
        pytest.skip("git lists the tracked set")
    listed = subprocess.run(
        ["git", "ls-files", "--", "docs/measurements/counter-model"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert listed.returncode == 0, listed.stderr
    tracked = {line for line in listed.stdout.split() if line.endswith(".json")}
    on_disk = {f"docs/measurements/counter-model/{p.name}"
               for p in (ROOT / "docs/measurements/counter-model").glob("*.json")}
    assert on_disk, "no receipts on disk - the validator above proved nothing"
    missing = on_disk - tracked
    assert not missing, (
        f"receipt(s) exist but are NOT tracked, so they do not exist in a clean "
        f"clone and this measurement is empty there: {sorted(missing)}"
    )


# --------------------------------------------------------------------------- #
# Every one of these was a counter-model finding on THIS branch. They are the
# stage's own first output, and the reason its red case is not a formality.
# --------------------------------------------------------------------------- #

def test_a_finding_shaped_EXAMPLE_in_another_section_is_not_a_finding() -> None:
    """The reviewer's second output describes INPUTS, and an input worth
    describing often looks exactly like a finding.

    Scanning the whole transcript made a CLEAN review read as `findings` the
    moment its `## Red cases` section carried `### [HIGH] Seeded defect`. The
    verdict has to come from the section it is about.
    """
    clean_with_example = (
        "## Findings\n\nNone - no defects found.\n\n"
        "## Red cases\n\n### [HIGH] Seeded defect\n- supply greet(\"\")\n"
    )
    assert CM.parse_review(clean_with_example)[0] == CM.PARSE_CLEAN

    # ...and the other direction: a clean statement OUTSIDE Findings does not
    # make an empty Findings section clean.
    clean_elsewhere = "## Findings\n\n## Summary\n\nNone - no defects found.\n"
    assert CM.parse_review(clean_elsewhere)[0] == CM.PARSE_UNPARSEABLE

    # ...and a real finding is still found when other sections follow it.
    real = ("## Findings\n\n### [HIGH] a real problem\n- File: x.py:1\n\n"
            "## Red cases\n\n- something\n")
    verdict, findings = CM.parse_review(real)
    assert verdict == CM.PARSE_FINDINGS and len(findings) == 1


def test_a_FENCED_heading_does_not_truncate_the_findings(tmp_path: Path) -> None:
    """A fenced block is content, not structure.

    A finding whose reproduction quotes a `## Example` inside a fence ended the
    Findings section there, so every finding AFTER it vanished from triage - a
    HIGH silently dropped because a MEDIUM above it quoted some markdown. The
    worst shape of all: the review ran, found the defect, and the stage threw
    the finding away.
    """
    transcript = (
        "## Findings\n\n"
        "### [MEDIUM] first one\n- File: a.py:1\n- Issue: reproduce with\n\n"
        "```\n## Example\n```\n\n"
        "### [HIGH] second one, after the fence\n- File: b.py:2\n\n"
        "## Red cases\n\n- something\n"
    )
    verdict, findings = CM.parse_review(transcript)
    assert verdict == CM.PARSE_FINDINGS
    assert [f["severity"] for f in findings] == ["MEDIUM", "HIGH"], (
        f"a fenced heading truncated the section: {findings}"
    )


def test_a_fenced_FINDING_example_is_still_not_a_finding() -> None:
    """The green half of the pair above: masking fences must not start counting
    examples that happen to sit outside a fence's protection."""
    clean = (
        "## Findings\n\nNone - no defects found.\n\n"
        "## Red cases\n\n```\n### [HIGH] Seeded defect\n```\n"
    )
    assert CM.parse_review(clean)[0] == CM.PARSE_CLEAN


def test_the_retirement_query_excludes_registry_METADATA() -> None:
    """`unregistered_claims` (#687) is an ARRAY sitting beside the role objects.

    A filter dropping only `wave_policy` then asks an array for `.liveness`, jq
    dies, and the check reports `unknown` on a roster that was perfectly
    readable - a wrong answer in the safe direction, which is still wrong and
    never resolves.
    """
    text = (COMMANDS / "flow" / "auto_codex.md").read_text(encoding="utf-8")
    assert "unregistered_claims" in text
    assert 'select(type == "object")' in text


def test_UNDETERMINED_liveness_does_not_authorise_retirement() -> None:
    """Liveness is a four-value vocabulary: live, released, stale, unknown.

    Filtering on `== "live"` alone treats `unknown` - the registry could not
    determine whether the process exists - as absence, and would authorise
    deleting the command out from under a session still running on it. That is
    the same "unknown is not clean" rule this repository applies everywhere
    else, and this check is where it is easiest to get wrong, because the
    tempting filter reads correctly.
    """
    text = (COMMANDS / "flow" / "auto_codex.md").read_text(encoding="utf-8")
    assert '.liveness == "unknown"' in text, (
        "the retirement check does not distinguish undetermined liveness"
    )
    assert "RETIREMENT: unknown (" in text


def test_an_EMPTY_model_identity_is_refused(tmp_path: Path) -> None:
    """`if reviewer and implementer and ...` skipped the comparison when either
    was empty, so a receipt naming NEITHER model validated clean - recording
    "two different models reviewed this" on the strength of two empty strings.
    A missing identity must fail the same check a colliding one does."""
    for reviewer, implementer in [("", "claude/opus-5"), ("codex/gpt-5.5", ""),
                                  ("   ", "claude/opus-5")]:
        proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "ran",
                      "--reviewer", reviewer, "--implementer", implementer,
                      "--passes", "1")
        assert proc.returncode == CM.EXIT_INVALID, (
            f"reviewer={reviewer!r} implementer={implementer!r} was accepted"
        )
        assert "empty" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_two_runs_in_the_same_second_both_SURVIVE(tmp_path: Path) -> None:
    """The filename carried a second-resolution timestamp and the issue, and the
    write was not exclusive: two runs for one issue inside the same second both
    "succeeded" and left ONE file. A lost run is invisible in a measurement
    whose entire purpose is counting runs."""
    common = ["--issue", "934", "--status", "ran", "--reviewer", "codex/gpt-5.5",
              "--implementer", "claude/opus-5", "--passes", "1",
              "--at", "2026-09-15T12:00:00Z"]
    a = _write(tmp_path, *common, "--branch", "branch-a", "--accepted", "1")
    b = _write(tmp_path, *common, "--branch", "branch-b", "--accepted", "7")
    assert a.returncode == 0 and b.returncode == 0, (a.stderr, b.stderr)

    written = sorted(tmp_path.glob("*.json"))
    assert len(written) == 2, f"a run was overwritten: {written}"
    branches = {json.loads(w.read_text(encoding="utf-8"))["branch"] for w in written}
    assert branches == {"branch-a", "branch-b"}


def test_the_review_runs_BEFORE_the_quality_gates() -> None:
    """Accepted findings are fixed in the worktree, and those fixes are CODE.

    Placed after the gates, a review fix that breaks lint, types or tests rides
    to the PR ungated - Step 7 only re-gates when the base moved, so a branch
    whose base is current merges it. The first cut of this change had exactly
    that ordering.
    """
    text = _auto()
    step6 = text.split("### Step 6:", 1)[1].split("### Step 7:", 1)[0]
    review = step6.index("**Counter-model review**")
    gates = step6.index("**Quality gates**")
    assert review < gates, (
        "the counter-model review is placed AFTER the quality gates; fixes it "
        "accepts would never be gated"
    )


def test_an_UNPARSEABLE_review_is_a_SKIP_not_a_clean_run() -> None:
    """Recording a review that never happened as one that found nothing.

    A reviewer whose transcript is absent or truncated yields zero findings,
    and a `ran` receipt with zero counts enters the measurement as "examined,
    nothing wrong".

    NARROWED BY #1015. This test used to cover an empty diff too, on the
    reasoning that "a reviewer handed nothing to read and a reviewer that read
    the change and found nothing wrong are opposite facts". The owner ruled on
    2026-09-16 that the ONLY condition for skipping is the inability to run
    codex, so an empty diff now gets an ordinary review and an ordinary `ran`
    receipt. The empty-diff half is therefore GONE, not relaxed - and
    `test_a_removed_reason_is_REFUSED_on_a_receipt_ALREADY_ON_DISK` below holds
    the removal in place so it cannot drift back in as prose.
    """
    text = _flat(_auto())
    assert "unparseable" in text
    assert "never a `ran` receipt with zeros" in text


def test_the_receipt_helper_is_RESOLVED_not_assumed_present() -> None:
    """`/flow:auto` runs against other repositories, which do not contain CPP's
    scripts. A bare `python3 scripts/counter-model-receipt.py` resolves inside
    the target worktree and simply is not there."""
    text = _auto()
    assert "~/.claude/scripts/counter-model-receipt.py" in text
    assert "CLAUDE_PLUGIN_ROOT" in text.split("### Step 6:", 1)[1].split("### Step 7:", 1)[0]


def test_the_retirement_check_has_THREE_outcomes() -> None:
    """An empty result means "nobody is driving on it", "the registry could not
    be read", or "the helper is absent". Only the first authorises deletion.

    It must also filter on LIVENESS and match the driver EXACTLY: `list` renders
    released roles with their drivers, and in the wave that wrote this,
    `worker-A` is released while still carrying `driver: flow:auto_codex`. A
    substring scan counts it and blocks the retirement forever.
    """
    text = (COMMANDS / "flow" / "auto_codex.md").read_text(encoding="utf-8")
    for outcome in ("RETIREMENT: clear", "RETIREMENT: blocked", "RETIREMENT: unknown"):
        assert outcome in text, f"the retirement check cannot report {outcome!r}"
    assert '.liveness == "live"' in text, "the check does not filter on liveness"
    assert '.driver == "flow:auto_codex"' in text, "the check does not match the driver exactly"
    assert "unknown` is not\n`clear`" in text or "`unknown` is not" in text


# --------------------------------------------------------------------------- #
# The command surfaces. What must be true of them, and what must NOT change.
# --------------------------------------------------------------------------- #

def _auto() -> str:
    return (COMMANDS / "flow" / "auto.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace before matching prose.

    A sentence in a markdown document wraps, so a raw substring test for it is
    really a test of where the line breaks fall. The first cut of the property
    assertion below failed for exactly that reason while the property was
    present and correct - a test that was wrong about its own subject.
    """
    return " ".join(text.split())


def test_flow_auto_carries_the_stage_as_a_PROPERTY() -> None:
    """Item 2 of the issue: state the rule as a property, not a tool name, so a
    qwen or gemma lane inherits it without an edit here."""
    text = _flat(_auto()).lower()
    assert "the reviewing model must not be the implementing model" in text
    assert "counter-model review" in text


def test_the_stage_runs_by_DEFAULT_and_a_skip_is_recorded() -> None:
    """Opt-in is the defect this issue names, so the surface must not describe
    the stage as something to opt into."""
    text = _flat(_auto())
    assert "IT RUNS BY DEFAULT" in text
    assert "ALWAYS, including on a skip" in text


def test_the_step_numbering_is_UNCHANGED() -> None:
    """Adding the stage must not renumber /flow:auto.

    Seven files cite `Step 3/9`, including both #775 no-bypass guards, which
    hardcode the total. Renumbering to buy prominence would pay that cascade -
    and prominence was never the defect: this stage went unused for 170 PRs
    because it lived in a SEPARATE COMMAND, not because it was insufficiently
    visible inside one.

    Pinned here so a later change that renumbers meets this reason first.
    """
    text = _auto()
    assert "Step 3/9: ELI5" in text, "the ELI5 gate's step label moved"
    for n in range(1, 10):
        assert f"Step {n}/9" in text, f"no Step {n}/9 report line"
    assert "/10" not in text, "flow/auto.md has been renumbered to ten steps"


def test_flow_auto_codex_still_WORKS_and_is_not_retired() -> None:
    """It is this wave's declared driver.

    Retiring it while live roles declare `driver=flow:auto_codex` removes the
    lifecycle command those sessions are running on, including the one
    implementing the removal. The retirement is recorded with its trigger
    instead; this pins that it did not happen early.
    """
    path = COMMANDS / "flow" / "auto_codex.md"
    assert path.exists(), "flow/auto_codex.md was deleted while it is a live driver"
    text = path.read_text(encoding="utf-8")
    assert "RETIREMENT TRIGGER" in text
    assert "no live role in any wave declares" in text.lower()


def test_adding_the_stage_LEFT_THE_ELI5_GATE_BYTE_IDENTICAL() -> None:
    """The issue's own Constraints: this stage is additional, never a substitute
    for approval (#775). A new gate that quietly relaxed an older one would be
    the worst possible outcome of adding review.

    ASSERTED AS "UNCHANGED FROM main", not by hunting for words. The first cut
    searched the Step 3 section for `auto-granted` and failed immediately -
    because that section DOCUMENTS the absence of the value ("deliberately no
    `auto-granted` value..."). Good documentation of a rule makes a text guard
    about that rule more false-positive, not less; it is the third time in two
    days a search of mine has matched its own documentation.

    The no-bypass property itself already has a dedicated guard in
    tests/test_eli5_gate_not_bypassable.py. Duplicating it badly here would be
    worse than not covering it, so this asserts the narrower thing that is
    genuinely mine to protect: my change did not touch the gate at all.
    """
    import shutil
    if shutil.which("git") is None:
        pytest.skip("git reads the base revision of the command document")

    proc = subprocess.run(
        ["git", "show", "origin/main:.claude/commands/flow/auto.md"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.skip("origin/main is not available in this checkout")

    def eli5_section(text: str) -> str:
        after = text.split("### Step 3: ELI5", 1)
        assert len(after) == 2, "the ELI5 step heading is gone"
        return after[1].split("### Step 4", 1)[0]

    base, now = eli5_section(proc.stdout), eli5_section(_auto())
    assert base.strip(), "the base revision yielded an empty ELI5 section"
    assert now == base, (
        "the ELI5 approval gate changed while adding the counter-model stage; "
        "this stage is additional, never a substitute for approval (#775)"
    )
