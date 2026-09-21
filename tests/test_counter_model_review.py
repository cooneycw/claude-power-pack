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
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

requires_git = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="the finish gate derives counter-model enrolment from git (issue #1171)",
)

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


def _reviewer_derivation_fixture(
    tmp_path: Path,
    model: str,
    thread_id: str = "thread-for-counter-model-test",
) -> tuple[Path, Path]:
    exec_log = tmp_path / "reviewer-exec.jsonl"
    exec_log.write_text(
        json.dumps({"type": "thread.started", "thread_id": thread_id}) + "\n",
        encoding="utf-8",
    )
    sessions_dir = tmp_path / "sessions"
    rollout_dir = sessions_dir / "2026" / "09" / "19"
    rollout_dir.mkdir(parents=True)
    (rollout_dir / f"rollout-{thread_id}.jsonl").write_text(
        json.dumps({"model": model}) + "\n",
        encoding="utf-8",
    )
    return exec_log, sessions_dir


def _reviewer_evidence_args(exec_log: Path, sessions_dir: Path) -> list[str]:
    return [
        "--reviewer-exec-log", str(exec_log),
        "--codex-sessions-dir", str(sessions_dir),
    ]


def _implementer_session_fixture(
    tmp_path: Path,
    model: str,
    session_id: str = "session-for-counter-model-test",
) -> tuple[str, Path]:
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "fixture-project"
    project_dir.mkdir(parents=True)
    (project_dir / f"{session_id}.jsonl").write_text(
        json.dumps({"type": "assistant", "message": {"model": model}}) + "\n",
        encoding="utf-8",
    )
    return session_id, projects_dir


def _implementer_evidence_args(session_id: str, projects_dir: Path) -> list[str]:
    return [
        "--implementer-session-id", session_id,
        "--claude-projects-dir", str(projects_dir),
    ]


def _write_session_receipt(
    tmp_path: Path, projects_dir: Path, *args: str, status: str = "ran"
) -> subprocess.CompletedProcess:
    if status == "ran":
        exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, "gpt-5.5")
        review_args = _reviewer_evidence_args(exec_log, sessions_dir)
    else:
        review_args = ["--reason", "reviewer-unavailable"]
    return _write(
        tmp_path, "--issue", "1047", "--branch", "b", "--status", status,
        *review_args, "--claude-projects-dir", str(projects_dir), *args,
    )


def test_implementer_is_derived_from_the_matching_session(tmp_path: Path) -> None:
    model = "claude-sonnet-5"
    session_id, projects_dir = _implementer_session_fixture(tmp_path, model)
    # A suffix match (as used for Codex rollouts) must not match this decoy.
    (projects_dir / f"prefix-{session_id}.jsonl").write_text(
        '{"model":"claude-wrong-model"}\n', encoding="utf-8"
    )
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["implementer"] == f"claude/{model}"


@pytest.mark.parametrize("environment_id", [None, ""])
def test_a_missing_implementer_session_id_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, environment_id: str | None
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    if environment_id is not None:
        monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", environment_id)
    proc = _write_session_receipt(tmp_path, tmp_path / "projects")
    assert proc.returncode == CM.EXIT_INVALID, proc.stderr
    assert "missing implementer session id" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_an_implementer_session_without_a_matching_transcript_is_refused(
    tmp_path: Path,
) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "claude-opus-5")
    transcript = next(projects_dir.rglob("*.jsonl"))
    # The filename must be EXACTLY the id plus .jsonl, not merely end with it.
    transcript.rename(transcript.with_name(f"prefix-{session_id}.jsonl"))
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stderr
    assert "no transcript matching session_id" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_multiple_matching_implementer_transcripts_are_refused(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "claude-opus-5")
    other_project = projects_dir / "another-project"
    other_project.mkdir()
    (other_project / f"{session_id}.jsonl").write_text(
        '{"model":"claude-sonnet-5"}\n', encoding="utf-8"
    )
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stderr
    assert "multiple transcripts matching session_id" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


@pytest.mark.parametrize("model", ["<synthetic>", "<future-session-placeholder>", "   "])
def test_non_real_implementer_model_shapes_are_refused(tmp_path: Path, model: str) -> None:
    # <future-session-placeholder> is deliberately novel, not denylisted in source.
    session_id, projects_dir = _implementer_session_fixture(tmp_path, model)
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stderr
    assert "contains no real-shaped model entry" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_an_implementer_transcript_without_model_entries_is_refused(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    next(projects_dir.rglob("*.jsonl")).write_text(
        '{"type":"user","message":"hello"}\n', encoding="utf-8"
    )
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stderr
    assert "contains no real-shaped model entry" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_the_latest_real_implementer_model_wins(tmp_path: Path) -> None:
    """A genuine mid-session model switch is preserved; sentinels do not erase it.

    PRESERVATION, NOT REGRESSION: this passes on both sides of #1109 and is not
    offered as evidence for that fix. Its SPECIMEN changed, though, and that is
    worth saying plainly - it used to be four bare `{"model": ...}` lines, which
    are not assistant messages and under #1109 correctly supply nothing. The
    property under test is unchanged; the input is now structurally the thing
    the property is about.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    next(projects_dir.rglob("*.jsonl")).write_text(
        "".join(
            json.dumps({"type": "assistant", "message": {"model": model}}) + "\n"
            for model in (
                "claude-opus-5",
                "claude-sonnet-5",
                "  <future-session-placeholder>  ",
                " ",
            )
        ),
        encoding="utf-8",
    )
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["implementer"] == "claude/claude-sonnet-5"


# --------------------------------------------------------------------------- #
# Issue #1109: an identity comes from the assistant, not from what it asked for.
#
# The extractor these pin replaced a whole-file regex for `"model": "..."` that
# kept the LAST hit. A transcript records every tool call the assistant made,
# arguments included, and some of those arguments are named `model` - on this
# host `mcp__substrate__add_worker` carries `input.model: "opus"`. So the field
# that exists to prove "the reviewer was a different model from the author"
# could be filled from a request the author happened to make last.
#
# Every case below except the two marked PRESERVATION fails on the pre-#1109
# extractor. That was verified by running them against a copy of the old source,
# not asserted; a fixture that is green on the buggy code proves nothing.
# --------------------------------------------------------------------------- #

def _nested_tool_record(assistant_model: str | None) -> dict:
    """The issue's specimen: a decoy `model` inside a tool_use argument.

    Key order matters and is deliberate. `message.model` is serialised BEFORE
    `content`, so the decoy is the LAST `"model"` substring in the line - which
    is precisely what a last-match-wins text scan selects.
    """
    message: dict = {}
    if assistant_model is not None:
        message["model"] = assistant_model
    message["content"] = [
        {
            "type": "tool_use",
            "id": "tool-1",
            "name": "mcp__substrate__add_worker",
            "input": {"model": "tool-request-model"},
        }
    ]
    return {"type": "assistant", "message": message}


def _overwrite_transcript(projects_dir: Path, *records: object) -> Path:
    """Replace the fixture transcript with these JSONL lines (str written raw)."""
    transcript = next(projects_dir.rglob("*.jsonl"))
    transcript.write_text(
        "".join(
            (r if isinstance(r, str) else json.dumps(r)) + "\n" for r in records
        ),
        encoding="utf-8",
    )
    return transcript


def test_a_nested_tool_argument_cannot_supply_the_implementer(tmp_path: Path) -> None:
    """The headline defect, through the PUBLIC writer.

    Pre-#1109 this recorded `claude/tool-request-model`: the name of a model the
    session ASKED a tool for, standing in for the model that did the work.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    _overwrite_transcript(projects_dir, _nested_tool_record("claude-sonnet-5"))
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["implementer"] == "claude/claude-sonnet-5"


def test_an_assistant_message_without_a_model_refuses_to_write(tmp_path: Path) -> None:
    """Absence must read as absence, not as the nearest available string.

    The sharpest half of the defect: deleting the real identity changed NOTHING
    pre-#1109 - the decoy answered either way, so "the transcript says who wrote
    this" and "the transcript does not" produced byte-identical receipts.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    _overwrite_transcript(projects_dir, _nested_tool_record(None))
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stdout
    assert "contains no real-shaped model entry" in proc.stderr
    assert "nested tool arguments cannot supply one" in proc.stderr
    assert "tool-request-model" not in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_a_non_assistant_record_cannot_supply_the_implementer(tmp_path: Path) -> None:
    """Eligibility is the record's TYPE, not the presence of a model key.

    Both decoys sit AFTER the real assistant turn, so a last-match-wins scan
    prefers them; a structural parser cannot see them as identities at all.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    _overwrite_transcript(
        projects_dir,
        {"type": "assistant", "message": {"model": "claude-opus-5"}},
        {"type": "user", "message": {"model": "user-side-decoy"}},
        {"model": "bare-record-decoy"},
    )
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["implementer"] == "claude/claude-opus-5"


def test_a_truncated_record_cannot_fabricate_an_implementer(tmp_path: Path) -> None:
    """Malformed input is COUNTED and refused, never pattern-matched.

    A transcript truncated mid-write is an ordinary accident, and pre-#1109 it
    was the most alarming case: the scan lifted a model out of a record the
    parser could not read, and the writer exited 0 on it.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    _overwrite_transcript(
        projects_dir,
        '{"type":"assistant","message":{"model":"fabricated-from-garbage"',
    )
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stdout
    assert "fabricated-from-garbage" not in proc.stderr
    # The census is the point: "1 unparseable" and "0 eligible" are different
    # facts about an empty result, and a diagnostic that cannot tell them apart
    # sends the reader looking in the wrong place.
    assert "read 1 record(s); 1 unparseable" in proc.stderr
    assert "0 eligible assistant message(s)" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_the_extractor_answers_the_issue_1109_specimens_directly(tmp_path: Path) -> None:
    """The same two specimens at the EXTRACTION seam, not only through the CLI.

    Both writer-level cases above route through `cmd_write`, so a regression
    that moved the decision into the caller could leave them green. This pins
    the function the issue names.
    """
    _, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    session_id = "session-for-counter-model-test"

    _overwrite_transcript(projects_dir, _nested_tool_record("real-implementer"))
    identity, error = CM._derive_implementer_from_session(session_id, projects_dir)
    assert (identity, error) == ("claude/real-implementer", None)

    _overwrite_transcript(projects_dir, _nested_tool_record(None))
    identity, error = CM._derive_implementer_from_session(session_id, projects_dir)
    assert identity is None
    assert error is not None and "no real-shaped model entry" in error


@pytest.mark.parametrize(
    "separator",
    # BUILT WITH chr(), never written raw into this file. A source file
    # holding a raw U+0085/U+2028/U+2029 is itself ambiguous to every tool
    # that numbers its lines with str.splitlines() - including one of this
    # repository's own gates, which mis-numbered this file's waiver comments
    # and reported two correctly-waived sites as violations. The runtime
    # VALUE is identical, so the property under test is unchanged.
    [chr(0x85), chr(0x2028), chr(0x2029), "\v", "\f",
     chr(0x1C), chr(0x1D), chr(0x1E)],
)
def test_message_content_cannot_decide_the_identity(
    tmp_path: Path, separator: str
) -> None:
    """A separator character inside message TEXT must not move the verdict.

    Raised by the counter-model review of #1109 and accepted. JSONL is
    newline-delimited, but `str.splitlines()` also breaks on these eight
    characters, every one of which is legal raw inside a JSON string. Splitting
    on them tore one record into fragments, so the older model won a switch the
    newer record had made - unrelated message content deciding the identity,
    which is the very defect #1109 exists to close, re-entering through the
    parser meant to close it.

    ONLY THREE OF THE EIGHT PARAMS ARE REGRESSION CASES, and saying so is the
    point of this paragraph. Verified against the `splitlines()` source: U+0085,
    U+2028 and U+2029 fail there; `\\v`, `\\f`, U+001C, U+001D and U+001E pass,
    because `json.dumps` escapes those five rather than emitting them raw. The
    five are kept as PRESERVATION - they pin that the escaping is what makes
    them safe, so a writer that ever emitted one raw would be caught - but they
    are not evidence for this fix and must not be counted as such.

    Reachable, not hypothetical: 1 of 120 real transcripts on the authoring host
    already carried 19 of these characters (7 NEL, 10 LS, 2 PS - exactly the
    three that are raw-reachable).
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    _overwrite_transcript(
        projects_dir,
        {"type": "assistant", "message": {"model": "claude-opus-5"}},
        # `ensure_ascii=False` writes the separator RAW, as a real transcript does.
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-5",
                    "content": [{"type": "text", "text": f"a{separator}b"}],
                },
            },
            ensure_ascii=False,
        ),
    )
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["implementer"] == "claude/claude-sonnet-5"


@pytest.mark.parametrize(
    ("records", "census"),
    [
        pytest.param((), "read 0 record(s); 0 unparseable; 0 eligible", id="empty"),
        pytest.param(
            ({"type": "assistant", "message": {"model": "<synthetic>"}},),
            "read 1 record(s); 0 unparseable; 1 eligible",
            id="sentinel-only",
        ),
    ],
)
def test_the_refusal_census_separates_empty_from_sentinel_only(
    tmp_path: Path, records: tuple, census: str
) -> None:
    """Two empty results that mean different things must not print alike.

    From the review's red cases. Both transcripts here yield no identity, but
    one was never asked anything and the other answered with a placeholder -
    'there was nothing to look at' versus 'I looked and found nothing'. A
    diagnostic that cannot separate them sends the reader to the wrong place.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    _overwrite_transcript(projects_dir, *records)
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stdout
    assert census in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


@pytest.mark.parametrize(
    "message",
    [
        {"model": 5},
        {"model": None},
        {"model": ["claude-opus-5"]},
        "a message that is not an object",
    ],
)
def test_a_non_string_declared_model_is_not_an_identity(
    tmp_path: Path, message: object
) -> None:
    """PRESERVATION of the refusal path under shapes the old scan never saw.

    A regex over text could only ever yield a string. A structural parser meets
    integers, nulls and lists, and each has to land in the same refusal rather
    than in a `claude/5`-shaped receipt or a traceback.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "discarded")
    _overwrite_transcript(projects_dir, {"type": "assistant", "message": message})
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stdout
    assert "contains no real-shaped model entry" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_a_skip_derives_its_implementer_and_keeps_a_null_reviewer(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "claude-sonnet-5")
    proc = _write_session_receipt(
        tmp_path, projects_dir, "--implementer-session-id", session_id, status="skipped"
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["status"] == "skipped"
    assert receipt["implementer"] == "claude/claude-sonnet-5"
    assert receipt["reviewer"] is None


@pytest.mark.parametrize("missing", ["session-id", "transcript"])
def test_a_skip_without_a_derivable_implementer_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    # #1046 accepted skips with a literal identity; #1047 deliberately fails closed.
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    args = [] if missing == "session-id" else ["--implementer-session-id", "missing-session"]
    proc = _write_session_receipt(tmp_path, tmp_path / "projects", *args, status="skipped")
    assert proc.returncode == CM.EXIT_INVALID, proc.stderr
    expected = (
        "missing implementer session id" if missing == "session-id"
        else "no transcript matching session_id"
    )
    assert expected in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


@pytest.mark.parametrize("flag", [None, "", "explicit-session"])
def test_implementer_session_id_uses_flag_or_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: str | None
) -> None:
    session_id, projects_dir = _implementer_session_fixture(
        tmp_path, "claude-sonnet-5", flag or "environment-session"
    )
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "unmatched-session" if flag else session_id)
    args = [] if flag is None else ["--implementer-session-id", flag]
    proc = _write_session_receipt(tmp_path, projects_dir, *args)
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["implementer"] == "claude/claude-sonnet-5"


def test_literal_implementer_flag_is_no_longer_accepted(tmp_path: Path) -> None:
    proc = _write_session_receipt(tmp_path, tmp_path / "projects", "--implementer", "claude/opus-5")
    assert proc.returncode == CM.EXIT_USAGE, proc.stderr
    assert "unrecognized arguments: --implementer" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_projects_override_never_touches_the_real_claude_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A find/rglob of real ~/.claude/projects reads every session on this host,
    including other people's live conversations. An override must isolate ALL
    lookup and transcript reads, even when a populated default directory exists.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, "claude-sonnet-5")
    exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, "gpt-5.5")
    fake_home = tmp_path / "fake-home"
    forbidden_projects = fake_home / ".claude" / "projects"
    forbidden_projects.mkdir(parents=True)
    (forbidden_projects / f"{session_id}.jsonl").write_text(
        '{"model":"claude-private-conversation"}\n', encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    def forbidden_default() -> Path:
        pytest.fail("explicit override must not even resolve the default projects root")

    original_rglob, original_read = Path.rglob, Path.read_text
    searched = []

    def isolated_rglob(path: Path, pattern: str):
        assert path in (projects_dir, sessions_dir), f"unexpected transcript search: {path}"
        searched.append(path)
        return original_rglob(path, pattern)

    def isolated_read(path: Path, *args, **kwargs):
        assert path.is_relative_to(tmp_path), f"read outside fixture: {path}"
        assert not path.is_relative_to(fake_home), f"read of default projects root: {path}"
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(CM, "_default_claude_projects_dir", forbidden_default)
    monkeypatch.setattr(Path, "rglob", isolated_rglob)
    monkeypatch.setattr(Path, "read_text", isolated_read)
    monkeypatch.setattr(sys, "argv", [
        str(SCRIPT), "write", "--dir", str(tmp_path), "--issue", "1047",
        "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir),
    ])
    assert CM.main() == CM.EXIT_OK
    assert projects_dir in searched
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["implementer"] == "claude/claude-sonnet-5"


def test_a_SKIP_is_recorded_not_omitted(tmp_path: Path) -> None:
    """The orchestrator's condition E, and the issue's whole premise.

    A skip with a receipt is a state. A skip without one is indistinguishable
    from a stage that was never wired in - which is the condition #934 was
    opened about: 0 of 170 merged PRs, with nothing anywhere recording it.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "skipped",
                  "--reason", "reviewer-unavailable",
                  *_implementer_evidence_args(session_id, projects_dir))
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
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "934", "--branch", "b", "--status", "skipped",
                  *_implementer_evidence_args(session_id, projects_dir))
    assert proc.returncode == CM.EXIT_USAGE, proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_codex_absent_is_a_DISTINCT_skip_reason(tmp_path: Path) -> None:
    """#1015's green half: the reason the probe exists to record is accepted."""
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "1015", "--branch", "b", "--status", "skipped",
                  "--reason", "codex-absent",
                  *_implementer_evidence_args(session_id, projects_dir))
    assert proc.returncode == 0, proc.stderr
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1, "a codex-absent skip wrote no receipt"
    assert json.loads(written[0].read_text(encoding="utf-8"))["skip_reason"] == "codex-absent"


@pytest.mark.parametrize("reason", ["codex-absent", "reviewer-unavailable"])
def test_a_skip_without_a_reviewer_records_an_explicit_null(
    tmp_path: Path, reason: str
) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "1046", "--branch", "b", "--status", "skipped",
                  "--reason", reason, *_implementer_evidence_args(session_id, projects_dir))
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["reviewer"] is None


def test_a_skip_naming_a_reviewer_is_REFUSED_at_the_write_path(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "1046", "--branch", "b", "--status", "skipped",
                  "--reason", "reviewer-unavailable",
                  "--reviewer-exec-log", str(tmp_path / "unused.jsonl"),
                  *_implementer_evidence_args(session_id, projects_dir))
    assert proc.returncode == CM.EXIT_USAGE, proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_a_skip_naming_a_reviewer_is_REFUSED_on_a_receipt_ALREADY_ON_DISK(
    tmp_path: Path,
) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "1046", "--branch", "b", "--status", "skipped",
                  "--reason", "reviewer-unavailable", *_implementer_evidence_args(session_id, projects_dir))
    assert proc.returncode == 0, proc.stderr
    receipt_path = next(tmp_path.glob("*.json"))

    clean = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert clean.returncode == 0, f"the unmutated receipt already fails: {clean.stderr}"

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["reviewer"] = "codex/gpt-5.5"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == CM.EXIT_INVALID
    assert "must not carry a reviewer" in (proc.stdout + proc.stderr)


def test_a_ran_write_without_a_reviewer_is_REFUSED(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "1046", "--branch", "b", "--status", "ran",
                  *_implementer_evidence_args(session_id, projects_dir), "--passes", "1")
    assert proc.returncode == CM.EXIT_USAGE, proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_reviewer_is_derived_from_the_matching_rollout(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    model = "fixture-review-model"
    exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, model)
    proc = _write(
        tmp_path, "--issue", "1048", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["reviewer"] == f"codex/{model}"


@pytest.mark.parametrize("exec_log_kind", ["missing", "unreadable"])
def test_a_missing_or_unreadable_exec_log_is_refused(
    tmp_path: Path, exec_log_kind: str
) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    exec_log = tmp_path / "reviewer-exec.jsonl"
    if exec_log_kind == "unreadable":
        exec_log.mkdir()
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    proc = _write(
        tmp_path, "--issue", "1048", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
    )
    assert proc.returncode == CM.EXIT_INVALID
    assert "cannot read reviewer exec log" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_an_exec_log_without_a_thread_id_is_refused(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    exec_log = tmp_path / "reviewer-exec.jsonl"
    exec_log.write_text('{"type":"item.completed"}\n', encoding="utf-8")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    proc = _write(
        tmp_path, "--issue", "1048", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
    )
    assert proc.returncode == CM.EXIT_INVALID
    assert "contains no thread_id" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_an_exec_log_without_a_matching_rollout_is_refused(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    exec_log = tmp_path / "reviewer-exec.jsonl"
    exec_log.write_text(
        '{"type":"thread.started","thread_id":"wanted-thread"}\n',
        encoding="utf-8",
    )
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "rollout-other-thread.jsonl").write_text(
        '{"model":"definitely-not-a-model"}\n', encoding="utf-8"
    )
    proc = _write(
        tmp_path, "--issue", "1048", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
    )
    assert proc.returncode == CM.EXIT_INVALID
    assert "no rollout matching thread_id" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_a_matching_rollout_without_a_model_is_refused(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, "discarded")
    rollout = next(sessions_dir.rglob("*.jsonl"))
    rollout.write_text('{"type":"session_meta"}\n', encoding="utf-8")
    proc = _write(
        tmp_path, "--issue", "1048", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
    )
    assert proc.returncode == CM.EXIT_INVALID
    assert "contains no model field" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_thread_match_wins_over_a_newer_unrelated_rollout(tmp_path: Path) -> None:
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    thread_id = "wanted-thread"
    exec_log, sessions_dir = _reviewer_derivation_fixture(
        tmp_path, "right-model", thread_id
    )
    correct_rollout = next(sessions_dir.rglob(f"*{thread_id}.jsonl"))
    unrelated_rollout = correct_rollout.parent / "zzzz-rollout-other-thread.jsonl"
    unrelated_rollout.write_text(
        '{"model":"definitely-not-a-model"}\n', encoding="utf-8"
    )
    os.utime(correct_rollout, (1, 1))
    os.utime(unrelated_rollout, (2, 2))

    proc = _write(
        tmp_path, "--issue", "1048", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
    )
    assert proc.returncode == CM.EXIT_OK, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["reviewer"] == "codex/right-model"
    assert receipt["reviewer"] != "codex/definitely-not-a-model"


@pytest.mark.parametrize("removed", ["no-diff", "explicit-opt-out"])
def test_a_removed_reason_is_REFUSED_at_the_write_path(tmp_path: Path, removed: str) -> None:
    """#1015's red half at the CLI: the reasons that left the set cannot re-enter
    through the front door."""
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "1015", "--branch", "b", "--status", "skipped",
                  "--reason", removed,
                  *_implementer_evidence_args(session_id, projects_dir))
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
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    proc = _write(tmp_path, "--issue", "1015", "--branch", "b", "--status", "skipped",
                  "--reason", "reviewer-unavailable",
                  *_implementer_evidence_args(session_id, projects_dir))
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


def test_the_PROPERTY_is_enforced_not_just_documented() -> None:
    """"The reviewing model must not be the implementing model" is the rule the
    issue asks for as a PROPERTY rather than a tool name.

    A run whose reviewer IS the implementer is the author agreeing with
    themselves, recorded as independent evidence - worse than no receipt at all,
    because it is counted.

    Tests validate() DIRECTLY against a hand-built receipt dict, not via the
    write CLI (issue #1047, review note): since #1047 made --implementer
    derive from a Claude session transcript (always "claude/<model>") and
    #1048 made --reviewer derive from a codex exec log (always
    "codex/<model>"), the two derivation paths can no longer collide by
    construction - there is no fixture that makes a normal `write` call
    produce equal reviewer/implementer strings anymore. The property this
    test protects is validate()'s own enforcement, independent of whichever
    path produced the values, so it is exercised directly rather than
    through a CLI invocation that can no longer reach the case.
    """
    receipt = {
        "schema": CM.SCHEMA,
        "recorded_at": "2026-09-19T00:00:00Z",
        "issue": "934",
        "branch": "b",
        "status": "ran",
        "reviewer": "claude/fixture-model",
        "implementer": "claude/fixture-model",
        "passes": 1,
        "counts": {"accepted": 0, "rejected": 0, "deferred": 0},
        "red_cases": {"proposed": 0, "already_covered": 0},
    }
    problems = CM.validate(receipt, "test receipt")
    assert any("must not be the implementing model" in p for p in problems), problems


def test_a_DIFFERENT_reviewer_is_accepted(tmp_path: Path) -> None:
    """The green half: the check must reject the violation and nothing else."""
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, "gpt-5.5")
    proc = _write(
        tmp_path, "--issue", "934", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "2", "--accepted", "3",
        "--rejected", "1", "--red-cases-proposed", "4",
        "--red-cases-already-covered", "3",
    )
    assert proc.returncode == 0, proc.stderr
    receipt = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert receipt["counts"] == {"accepted": 3, "rejected": 1, "deferred": 0}
    assert receipt["red_cases"] == {"proposed": 4, "already_covered": 3}


def test_coverage_cannot_exceed_what_was_proposed(tmp_path: Path) -> None:
    """The diversity number is already_covered / proposed, and it is the only
    thing that can tell an excellent reviewer from an uncritical author. A ratio
    above 1 corrupts that silently rather than loudly."""
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, "gpt-5.5")
    proc = _write(
        tmp_path, "--issue", "934", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
        "--red-cases-proposed", "2", "--red-cases-already-covered", "5",
    )
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


# --------------------------------------------------------------------------- #
# THE RETIREMENT TRIGGER MOVED OUT OF THIS FILE (#1017).
#
# Three tests here asserted the trigger's properties by GREPPING the prose of
# `.claude/commands/flow/auto_codex.md` - that it filtered on liveness, that it
# distinguished `unknown`, that it could report all three outcomes, that it
# excluded the registry metadata keys. They were right about what the procedure
# MEANT and silent about what it could SAY, and what it could say was wrong:
# `flow-wave-registry.sh list` exits 0 on an absent registry, so the branch that
# existed to report "I could not look" was unreachable and a host with no
# registry read `RETIREMENT: clear`. A text search for the word `unknown` finds
# that check in perfect health.
#
# The trigger was then evaluated, found clear, and the command retired. The same
# properties are now asserted BEHAVIOURALLY against
# `scripts/flow-driver-retirement-check.sh` in `tests/test_flow_driver_retirement.py`,
# against four committed cases. A pointer rather than a deletion, because the
# next reader here will be looking for exactly these assertions.
# --------------------------------------------------------------------------- #


def test_an_EMPTY_model_identity_is_refused(tmp_path: Path) -> None:
    """Only the empty-implementer half remains after reviewer derivation.

    An empty reviewer can no longer be supplied as free text; failed reviewer
    derivation is covered by the refusal tests above.
    """
    session_id, projects_dir = _implementer_session_fixture(tmp_path, '')
    exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, "gpt-5.5")
    proc = _write(
        tmp_path, "--issue", "934", "--branch", "b", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
    )
    assert proc.returncode == CM.EXIT_INVALID, proc.stderr
    assert "contains no real-shaped model entry" in proc.stderr
    assert list(tmp_path.glob("*.json")) == []


def test_two_runs_in_the_same_second_both_SURVIVE(tmp_path: Path) -> None:
    """The filename carried a second-resolution timestamp and the issue, and the
    write was not exclusive: two runs for one issue inside the same second both
    "succeeded" and left ONE file. A lost run is invisible in a measurement
    whose entire purpose is counting runs."""
    session_id, projects_dir = _implementer_session_fixture(tmp_path, 'opus-5')
    exec_log, sessions_dir = _reviewer_derivation_fixture(tmp_path, "gpt-5.5")
    common = [
        "--issue", "934", "--status", "ran",
        *_reviewer_evidence_args(exec_log, sessions_dir),
        *_implementer_evidence_args(session_id, projects_dir), "--passes", "1",
        "--at", "2026-09-15T12:00:00Z",
    ]
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


# ---------------------------------------------------------------------------
# Issue #1030, defect 3: the receipt is written after the point the gate
# requires it to be TRACKED. Nothing staged a fresh receipt between item 1d's
# write and item 2's quality gates, so the first run to reach here always
# failed test_every_COMMITTED_receipt_is_well_formed_AND_TRACKED on its first
# attempt - an ordering defect, not a false green (the gate correctly
# refused), but one that cost a wasted full gate run every single time.
# ---------------------------------------------------------------------------


def test_the_receipt_is_staged_before_the_quality_gates_run() -> None:
    text = _auto()
    step6 = text.split("### Step 6:", 1)[1].split("### Step 6b:", 1)[0]
    write_call = step6.index('python3 "$CM_RECEIPT" write')
    gates = step6.index("**Quality gates**")
    assert write_call < gates, "the write call moved outside Step 6 as expected"
    stage = step6.find("git add", write_call)
    assert stage != -1 and stage < gates, (
        "the receipt write is not followed by a `git add` staging step before "
        "the quality gates run, so a fresh receipt fails the tracked-receipt "
        "test on the gate's first attempt (issue #1030)"
    )
    assert "docs/measurements/counter-model" in step6[stage : stage + 200], (
        "the staging step does not target the receipts directory"
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="requires git")
def test_the_published_staging_command_actually_tracks_a_fresh_receipt(
    tmp_path: Path,
) -> None:
    """Executes the PUBLISHED command, not a paraphrase of it.

    RED (implicit): before issue #1030's fix, there was no such command to
    extract at all - this test could not have existed against the pre-fix
    document. GREEN: build a repo with the same `.gitignore` negation rule
    the real repo carries for this directory (issue #934), write an untracked
    receipt exactly as `counter-model-receipt.py write` would, run the
    extracted command, and confirm `git ls-files` now lists it.
    """
    import re

    text = _auto()
    step6 = text.split("### Step 6:", 1)[1].split("### Step 6b:", 1)[0]
    anchor = step6.index("Stage the receipt immediately")
    match = re.search(r"```bash\n(.*?)```", step6[anchor:], re.S)
    assert match, "no fenced bash block found after the staging instruction"
    stage_command = match.group(1).strip()
    assert stage_command.startswith("git add"), (
        f"unexpected staging command extracted: {stage_command!r}"
    )

    def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            # negative-fixture: allow PATH is isolation, not an absence
            env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin",
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
        )

    repo = tmp_path / "repo"
    repo.mkdir()
    assert git("init", "-q", "-b", "main", cwd=repo).returncode == 0
    (repo / ".gitignore").write_text(
        "*.json\n!docs/measurements/counter-model/*.json\n", encoding="utf-8"
    )
    receipts_dir = repo / "docs" / "measurements" / "counter-model"
    receipts_dir.mkdir(parents=True)
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "base", cwd=repo)

    # A fresh, UNTRACKED receipt - exactly the state right after cmd_write().
    (receipts_dir / "2026-01-01T000000Z-issue-9999.json").write_text(
        "{}\n", encoding="utf-8"
    )

    proc = subprocess.run(
        ["bash", "-c", stage_command],
        cwd=repo, capture_output=True, text=True,
        # negative-fixture: allow PATH is isolation, not an absence
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin",
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"},
    )
    assert proc.returncode == 0, proc.stderr

    tracked = git("ls-files", "--", "docs/measurements/counter-model", cwd=repo).stdout
    assert "2026-01-01T000000Z-issue-9999.json" in tracked, (
        f"the published command did not track the fresh receipt:\n{tracked}"
    )


# --- The reviewed commit, derived not asserted (issue #1171) -----------------


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    def run(*a: str) -> None:
        subprocess.run(["git", "-C", str(repo), *a], check=True,
                       capture_output=True, text=True)

    run("init", "-q", "-b", "master", ".")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    (repo / "f.txt").write_text("x\n")
    run("add", "-A")
    run("commit", "-qm", "base")
    return repo


@requires_git
def test_head_is_derived_from_the_checkout(tmp_path: Path) -> None:
    """Derived, not passed in, so an unedited call site produces a usable receipt.

    The only receipt-write call site is in `.claude/commands/flow/auto.md`. Requiring
    a `--head` flag there would make this field depend on a document being edited in
    lockstep with this script - the "a marker written by the thing being measured"
    trap #1048 removed from `--reviewer`.
    """
    mod = _load()
    repo = _git_repo(tmp_path)
    real = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    head, warning = mod._derive_head(None, repo)
    assert head == real
    assert warning is None


@requires_git
def test_an_explicit_head_overrides_derivation(tmp_path: Path) -> None:
    mod = _load()
    head, warning = mod._derive_head("abc1234", _git_repo(tmp_path))
    assert head == "abc1234"
    assert warning is None


@requires_git
def test_outside_a_checkout_head_is_absent_and_said_out_loud(tmp_path: Path) -> None:
    """Absent is a state, not a silent one: the receipt stays valid but cannot satisfy
    the finish gate, and the writer says so rather than leaving the gate to report a
    bare `missing` later."""
    mod = _load()
    head, warning = mod._derive_head(None, tmp_path)
    assert head is None
    assert warning and "not a git checkout" in warning


def test_a_receipt_without_a_head_is_still_well_formed() -> None:
    """Every receipt committed before #1171 lacks this field. Making it required would
    invalidate all of them at once, so absence means 'written before the field existed'."""
    mod = _load()
    receipt = {
        "schema": 1, "recorded_at": "2026-09-20T21:15:11Z", "issue": "1071",
        "branch": "b", "status": "ran", "reviewer": "codex/gpt-6-astra",
        "implementer": "claude/claude-opus-5", "passes": 1,
        "counts": {"accepted": 0, "rejected": 0, "deferred": 0},
        "red_cases": {"proposed": 0, "already_covered": 0},
    }
    assert mod.validate(receipt, "legacy") == []


def test_a_head_that_is_not_an_object_name_is_refused() -> None:
    mod = _load()
    receipt = {
        "schema": 1, "recorded_at": "2026-09-20T21:15:11Z", "issue": "1071",
        "branch": "b", "head": "not-a-sha", "status": "ran",
        "reviewer": "codex/gpt-6-astra", "implementer": "claude/claude-opus-5", "passes": 1,
        "counts": {"accepted": 0, "rejected": 0, "deferred": 0},
        "red_cases": {"proposed": 0, "already_covered": 0},
    }
    assert any("not a git object name" in p for p in mod.validate(receipt, "bad"))


def test_the_committed_skip_reasons_are_readable_by_the_shell_lane() -> None:
    """`flow-finish-gate.sh` validates a skip against this output. A second copy of the
    set in shell is the cross-language drift #890/#1147 kept removing, and it fails in
    the dangerous direction: a stale shell copy would accept a retired reason."""
    got = subprocess.run([sys.executable, str(SCRIPT), "skip-reasons"],
                         capture_output=True, text=True, check=True)
    mod = _load()
    assert got.stdout.split() == list(mod.SKIP_REASONS)
    assert "explicit-opt-out" not in got.stdout
