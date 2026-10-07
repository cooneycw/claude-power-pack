#!/usr/bin/env python3
"""counter-model-receipt.py - record one counter-model review run (issue #934).

WHY A RECEIPT AND NOT A PR-BODY BLOCK
-------------------------------------
The stage used to record itself by appending `## Codex pre-PR review` to the PR
body, which made adoption countable by grepping merged PRs. That is a MARKER:
written by the thing being measured, and therefore defeated by whoever writes
it. PR #1000 ran two review passes, fixed eleven findings, and greps as having
had NO cross-model review, because its author rewrote the body by hand and used
a different heading. The PR block is now a RENDERING of the receipt; the receipt
is the record.

A RECEIPT IS ALSO WRITTEN ON A SKIP. A skip with a receipt is a state - it says
which reason, on which branch, at which time. A skip without one is
indistinguishable from a stage that was never wired in, which is precisely the
condition this issue was opened about: 0 of 170 merged PRs over two months, with
nothing anywhere recording that the stage had not run.

WHY IN THE REPOSITORY
---------------------
Evidence about an instrument that does not live in the tree cannot be
re-derived by anyone else: a count held outside the repo is a green nobody can
audit. One file per run, so concurrent workers never conflict on it.

WHAT THIS IS NOT
----------------
It is not a gate and it returns no verdict about a change. `validate` checks
SHAPE only, and its failure is caught by the surrounding suite
(tests/test_counter_model_review.py), which is why it carries no committed
negative control of its own - see docs/decisions/0008-instrument-negative-control-bound.md
for the bound. Reading the accumulated counts is a documented `jq` query in
ADR 0007 rather than a summarising instrument here, deliberately: a number that
decides whether the stage gets promoted to blocking should be derived in the
open by whoever is deciding, not handed to them by a script nobody controlled.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
RECEIPT_DIR = Path("docs/measurements/counter-model")

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2

STATUSES = ("ran", "skipped")

#: How much of the repository the reviewer could actually read (issue #1261,
#: recorded on the receipt since issue #1400). `full` - the sandbox started
#: and could read the tree. `diff-only` - the sandbox could not start, so the
#: reviewer judged the diff alone. `unverified` - no probe could be run at
#: all. Only `ran` receipts may carry it; a skip recorded no review and
#: therefore read nothing.
SCOPES = ("full", "diff-only", "unverified")

#: WHICH WAY ROUND THE TWO MODELS SAT (issue #1383). The default direction -
#: Claude implements, Codex reviews - is what every receipt before #1383
#: records, and a receipt with no `direction` field still means exactly that.
#: `delegated` is the /codex:auto lane: Codex implements, and the supervising
#: Claude session reviews the diff in that lane's Step 5. Before this, the
#: writer could only model the first direction, so a delegated run had two
#: options and both were false: a `ran` receipt derived as "Codex reviewed
#: Claude's code" (inverting the property this file checks), or a skip reason
#: claiming a reviewer was absent when it was not.
#:
#: THE PROPERTY DOES NOT CHANGE WITH THE DIRECTION. Both identities are still
#: DERIVED (#1047/#1048), each from the side that produced it, and a receipt
#: naming the same model twice is refused whichever way round it claims to be.
DIRECTION_DEFAULT = "claude-implements"
DIRECTION_DELEGATED = "delegated"
DIRECTIONS = (DIRECTION_DEFAULT, DIRECTION_DELEGATED)

#: A skip must say WHICH skip. An open-ended reason string would let
#: "not today" and "the reviewer binary is missing" share a bucket, and those
#: two say opposite things about whether the stage is working.
#:
#: OWNER RULING 2026-09-16 (issue #1015): "the only condition for skipping a
#: codex review is the inability to run codex." Both members below ARE that
#: inability; they differ in WHICH one, which is the #953 convention applied
#: one level down - the same conclusion reached for a different cause earns a
#: reason field, not a new verdict.
#:
#: `no-diff` and `explicit-opt-out` were REMOVED. Neither is an inability to
#: run the reviewer. `explicit-opt-out` had no producer anywhere in
#: .claude/commands/, so removing it changed no behaviour - but a
#: discretionary skip is precisely the mechanism that produced 0 of 170
#: (ADR 0007), and leaving the door in the wall invites someone to open it.
#:
#: REVERSAL TRIGGER (#936, committed here rather than in a PR body the next
#: person to touch this line will not read). This change makes a check
#: STRICTER without changing what it measures, which is one of that issue's
#: own tells:
#:
#:   If runs begin stalling or failing because the reviewer is invoked on
#:   changes it cannot usefully review - an empty or near-empty diff
#:   producing `unparseable` often enough that `reviewer-unavailable` stops
#:   meaning what it says - then `no-diff` returns as a distinct reason.
#:
#:   `explicit-opt-out` does NOT return on that trigger. It was removed for a
#:   different reason (no producer), and re-adding a discretionary skip is the
#:   swing this trigger exists to catch, not one it authorises.
SKIP_REASONS = (
    "codex-absent",           # the reviewer binary is not installed on this host
    "reviewer-unavailable",   # the second model could not be reached or run
)

COUNTS = ("accepted", "rejected", "deferred")
RED = ("red_cases_proposed", "red_cases_already_covered")


#: The review format `/codex:code_review` prescribes. A heading line per finding,
#: with the severity in brackets. Kept here rather than in the command document
#: because a format nobody parses is a format that drifts.
FINDING_RE = re.compile(r"^###\s*\[(?P<severity>CRITICAL|HIGH|MEDIUM|LOW)\]\s*(?P<title>.+?)\s*$",
                        re.MULTILINE)
FINDINGS_HEADING = re.compile(r"^##\s*Findings\s*$", re.MULTILINE)
#: The prescribed way of saying "nothing found". Matched explicitly, because the
#: whole point below is that its ABSENCE is not the same as its presence.
NONE_RE = re.compile(r"^\s*None\b.*no defects found", re.MULTILINE | re.IGNORECASE)

#: Where the Findings section ENDS. The reviewer is asked for a second section
#: ("## Red cases") whose whole job is to describe inputs - and an input worth
#: describing often looks exactly like a finding. Scanning the whole transcript
#: made a CLEAN review read as `findings` the moment its red-case section
#: carried an example headed `### [HIGH] Seeded defect`, and let a clean
#: statement sitting in some other section stand in for one in Findings. The
#: verdict has to come from the section it is about.
NEXT_H2 = re.compile(r"^##\s+(?!Findings\b)", re.MULTILINE)

#: A fenced block is CONTENT, not structure. A finding whose reproduction quotes
#: a `## Example` heading inside a fence ended the Findings section there, so
#: every finding after it vanished from triage - a HIGH silently dropped because
#: a MEDIUM above it quoted some markdown. Masking preserves offsets so the
#: ORIGINAL text can still be sliced by what was found in the masked copy.
FENCE = re.compile(r"^(?P<fence>```+|~~~+).*?(?:^(?P=fence)\s*$|\Z)",
                   re.MULTILINE | re.DOTALL)


def _mask_fences(text: str) -> str:
    out = list(text)
    for m in FENCE.finditer(text):
        for i in range(m.start(), m.end()):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)

PARSE_FINDINGS = "findings"
PARSE_CLEAN = "clean"
PARSE_UNPARSEABLE = "unparseable"
#: A review that HAPPENED and answered in another shape (issue #1259). Before
#: this it was `unparseable`, which step 1c records as `skipped /
#: reviewer-unavailable` - a receipt asserting that a real review, whose
#: findings the caller acted on, did not occur. Seen on #1056: both passes
#: returned `- **MEDIUM - file:line**` bullets.
PARSE_FORMAT_MISMATCH = "format-mismatch"

#: What makes a line in the Findings section read as a finding written in some
#: other shape: a LIST ITEM or HEADING that LEADS with an uppercase severity
#: label, after at most some emphasis or bracket punctuation - `- **MEDIUM -
#: x.py:1**`, `### HIGH: title`, `1. [LOW] title`. Deliberately narrow, in both
#: directions: a truncated `### [HIG` and a prose "looks good" carry no label
#: and stay `unparseable`; a lowercase "the risk is low" is English; and a
#: prescribed finding's own `- Issue: ... HIGH ...` field does not lead with one,
#: so a well-formed review is never mistaken for a mismatched one. A line the
#: prescribed `FINDING_RE` already reads is excluded by the caller.
OFFSHAPE_FINDING_RE = re.compile(
    r"^[ \t]*(?:[-*+]|\d+[.)]|#{1,6})[ \t]+[*_`\[(]*[ \t]*(?:CRITICAL|HIGH|MEDIUM|LOW)\b",
    re.MULTILINE,
)


def _offshape_findings(section: str) -> bool:
    """A finding-shaped line the prescribed heading regex does not read."""
    lines = [ln for ln in section.splitlines() if OFFSHAPE_FINDING_RE.match(ln)]
    return any(not FINDING_RE.match(ln) for ln in lines)


def parse_review(text: str) -> tuple[str, list[dict]]:
    """Read a reviewer transcript. Returns (verdict, findings).

    THREE OUTCOMES, NOT TWO, and that is the whole design of this function.

    A transcript the reviewer never produced, truncated mid-stream, or written
    in some other shape yields NO finding headings - which is byte-identical, to
    any code counting headings, to a review that found nothing wrong. Those are
    opposite facts: one says the change was examined and is sound, the other
    says nothing was examined. `clean` is returned ONLY when the reviewer said
    so in the prescribed words; a transcript with no findings and no such
    statement is `unparseable`, and the caller must not record it as a clean
    run.

    A FOURTH OUTCOME SPLITS THE THIRD (issue #1259). "Answered in some other
    shape" covered two opposite facts as well: a reply with no findings in it,
    and a real review whose findings are written as bullets rather than
    `### [SEVERITY]` headings. The second is `format-mismatch` - a review that
    happened, never to be recorded as a skip - and needs a severity-labelled
    list item or heading inside Findings to be claimed. Everything else that is
    neither findings nor clean stays `unparseable`.

    This is the #952 denominator convention applied to a review: an instrument
    prints what it examined, and a zero it cannot account for reads as unknown.
    """
    source = text or ""
    masked = _mask_fences(source)

    head = FINDINGS_HEADING.search(masked)
    if not head:
        return PARSE_UNPARSEABLE, []

    # Only the Findings section, and only headings that are STRUCTURE. Offsets
    # come from the masked copy; the slice is taken from the original.
    nxt = NEXT_H2.search(masked, head.end())
    end = nxt.start() if nxt else len(source)
    # Only the masked copy is scanned: a heading outside a fence is byte-identical
    # in both, and one inside a fence must not be found at all.
    masked_section = masked[head.end():end]

    findings = [
        {"severity": m.group("severity"), "title": m.group("title")}
        for m in FINDING_RE.finditer(masked_section)
    ]
    # CHECKED BEFORE EITHER SUCCESS (counter-model review). A section mixing one
    # prescribed heading with off-shape bullets returned `findings` counting only
    # the heading, and a clean statement followed by a bullet returned `clean` -
    # both reach a receipt with the off-shape findings silently uncounted. The
    # recognised findings are returned with the verdict, so nothing is lost.
    if _offshape_findings(masked_section):
        return PARSE_FORMAT_MISMATCH, findings
    if findings:
        return PARSE_FINDINGS, findings
    if NONE_RE.search(masked_section):
        return PARSE_CLEAN, []
    return PARSE_UNPARSEABLE, []


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-")[:60] or "unknown"


def rollout_turn_model(rollout_text: str) -> tuple[str | None, str | None]:
    """The model a Codex rollout's TURNS ran on, read structurally (issue #1269).

    WHY NOT THE FIRST `"model"` IN THE FILE. This used to be a whole-file regex,
    first match wins. A codex-cli 0.158.0 rollout carries five structural
    `model` keys, and the FIRST is `session_meta.payload.base_instructions
    .provenance.model` - the model the base instructions were written for, not
    the model that answered. `turn_context.payload.model` is the per-turn
    record of what ran. Measured on three real runs (the default, `-m gpt-5.5`,
    `-m gpt-5`): all five agreed, so no landed receipt is wrong - but they are
    different facts, and they part on a model switch or a resumed thread.

    Refuses rather than choosing when the turns disagree: picking one of two
    would manufacture a specific answer out of an ambiguous one - the same rule
    `counter-model-reviewer-attribution.py` applies to two linked rollouts. A
    rollout with no turn_context record at all (an older Codex that wrote a
    different shape) is refused too: a receipt naming a reviewer nobody can
    re-derive is worse than no receipt.

    AGREEMENT OF WHAT WAS READ IS NOT COMPLETE EVIDENCE (counter-model review).
    A turn_context that declares no model, or a line that does not parse and
    could have been a turn record, leaves that turn's model UNKNOWN - and one
    readable turn saying `A` beside an unknown one is not a rollout that says
    `A`. Both refuse, naming the count, rather than letting the readable part
    stand in for the whole.

    Returns `(model, None)` or `(None, reason)`; the reason names what is
    missing so the caller can print it against the rollout's path.
    """
    turn_contexts = 0
    undeclared = 0
    unparseable = 0
    models: set[str] = set()
    # `split("\n")`, never `splitlines()`: see _derive_implementer_from_session.
    for line in rollout_text.split("\n"):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            unparseable += 1
            continue
        if not isinstance(record, dict) or record.get("type") != "turn_context":
            continue
        turn_contexts += 1
        payload = record.get("payload")
        model = payload.get("model") if isinstance(payload, dict) else None
        if isinstance(model, str) and model.strip():
            models.add(model.strip())
        else:
            undeclared += 1
    if turn_contexts == 0 and not unparseable:
        return None, "no turn_context record"
    if unparseable:
        return None, (
            f"{unparseable} unparseable line(s) beside {turn_contexts} turn_context "
            "record(s); a turn's model may be among them, so the reviewing model "
            "is not established"
        )
    if undeclared:
        return None, (
            f"{undeclared} of {turn_contexts} turn_context record(s) declare no "
            "payload.model; the reviewing model is not established"
        )
    if len(models) > 1:
        return None, (
            f"turn_context records disagree ({', '.join(sorted(models))}); "
            "the reviewing model is ambiguous"
        )
    return next(iter(models)), None


def _derive_reviewer_from_exec_log(
    exec_log: Path, sessions_dir: Path, role: str = "reviewer"
) -> tuple[str | None, dict | None, str | None]:
    """Derive the model behind one Codex exec stream from its own rollout.

    Returns `(model, evidence, error)`. `evidence` is the pointer a later
    reader needs to re-derive the model (issue #1269): the thread id this
    derivation was anchored on, and the rollout it read, relative to the
    sessions directory so the receipt does not carry a host's home path.

    `role` only names the stream in diagnostics. On the default direction the
    stream is the REVIEWER's; on a delegated lane (issue #1383) it is the
    IMPLEMENTER's - the same derivation, read from the other side.
    """
    try:
        exec_text = exec_log.read_text(encoding="utf-8")
    except OSError as exc:
        return None, None, f"cannot read {role} exec log {exec_log}: {exc}"

    thread_match = re.search(r'"thread_id"\s*:\s*"([^"]*)"', exec_text)
    if thread_match is None or not thread_match.group(1):
        return None, None, f"{role} exec log {exec_log} contains no thread_id"
    thread_id = thread_match.group(1)

    try:
        matches = sorted(
            path
            for path in sessions_dir.rglob("*.jsonl")
            if path.is_file() and path.name.endswith(f"{thread_id}.jsonl")
        )
    except OSError as exc:
        return None, None, f"cannot search Codex sessions directory {sessions_dir}: {exc}"
    if not matches:
        return None, None, (
            f"no rollout matching thread_id {thread_id!r} under Codex sessions "
            f"directory {sessions_dir}"
        )
    if len(matches) > 1:
        # Mirrors _derive_implementer_from_session's equivalent refusal
        # (issue #1400, Nit Store #864 comment 5867878307): a thread id is a
        # UUID, so a real collision needs a copied or restored sessions
        # tree, but picking `matches[0]` silently would then name a
        # reviewer from an arbitrary one of the copies.
        return None, None, (
            f"multiple rollouts matching thread_id {thread_id!r} under Codex "
            f"sessions directory {sessions_dir}"
        )

    rollout = matches[0]
    try:
        rollout_text = rollout.read_text(encoding="utf-8")
    except OSError as exc:
        return None, None, f"cannot read matching rollout {rollout}: {exc}"
    model, reason = rollout_turn_model(rollout_text)
    if model is None:
        return None, None, f"{reason} in matching rollout {rollout}"
    evidence = {
        "thread_id": thread_id,
        "rollout": rollout.relative_to(sessions_dir).as_posix(),
    }
    return f"codex/{model}", evidence, None


def _mid_run_sandbox_failures(exec_text: str) -> int:
    """Count `command_execution` items whose SANDBOXED EXEC PROCESS ITSELF
    could not launch - never a command that ran and merely returned a
    non-zero exit (issue #1400, comment 5858478984).

    `exit_code: -1` paired with `status: "failed"` is codex's own signature
    for "could not create the exec process at all" (the shape of the real
    #1265/#836 incident recorded in docs/flow-runs/issue-1365.as-read.md and
    pinned across tests/test_delegated_run_check.py) - structurally different
    from `exit_code: 1, status: "failed"` on a `grep` that simply found
    nothing. The pre-run scope probe in `/codex:code_review` detects exactly
    this failure mode by trying to launch the SAME sandboxed exec machinery
    against one tracked file; this is that same test, re-applied to every
    command the reviewer actually ran, so a probe that passed before the
    review started is not trusted alone for its whole duration.
    """
    failures = 0
    for line in exec_text.split("\n"):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("type") != "item.completed":
            continue
        item = record.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        if item.get("exit_code") == -1 and item.get("status") == "failed":
            failures += 1
    return failures


def _default_codex_sessions_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "sessions"
    return Path.home() / ".codex" / "sessions"


def _eligible_assistant_model(record: object) -> str | None:
    """The model an assistant-message record declares as its OWN identity.

    ELIGIBILITY IS STRUCTURAL, and that is the whole point of this function
    (issue #1109). A transcript record is allowed to supply an implementer only
    when it IS an assistant message and the value is read from the one field
    where an assistant's own identity lives - `message.model`. Every other
    `"model"` in the file belongs to something else: the arguments the
    assistant passed to a tool, a tool result, session metadata. Those describe
    what was ASKED FOR, never who answered.

    Returns the declared string unchanged - trimming and sentinel handling are
    the caller's, because "this record declares an identity" and "that identity
    is real-shaped" are different questions and collapsing them here would hide
    a sentinel-only transcript behind a no-assistant-records diagnostic.
    """
    if not isinstance(record, dict) or record.get("type") != "assistant":
        return None
    # A SIDECHAIN record is a sub-agent speaking, not the implementing session
    # (issue #1269). The current harness writes those to
    # `<session>/subagents/agent-*.jsonl`, which the stem lookup never opens;
    # an older layout wrote them INLINE, where the last-wins rule below would
    # hand the implementer identity to whichever sub-agent answered last.
    if record.get("isSidechain") is True:
        return None
    message = record.get("message")
    if not isinstance(message, dict):
        return None
    model = message.get("model")
    # A non-string model is not an identity. `isinstance(True, int)` is the
    # usual trap here; strings have no such alias, so a plain check suffices.
    return model if isinstance(model, str) else None


def _derive_implementer_from_session(
    session_id: str, projects_dir: Path
) -> tuple[str | None, str | None]:
    """Derive the latest real model from the implementing Claude session.

    WHY THIS PARSES INSTEAD OF SEARCHING (issue #1109). This used to regex the
    whole transcript for `"model": "..."` and keep the last hit. A transcript
    is not a bag of strings: it also records every tool call the assistant
    made, arguments included, and some of those arguments are themselves named
    `model`. On this host `mcp__substrate__add_worker` carries
    `input.model: "opus"`, so a session whose last action was spawning a worker
    recorded `claude/opus` as its own implementer - an identity that came out
    of a REQUEST, not out of the assistant. Worse, deleting the real
    `message.model` changed nothing: the decoy answered either way, so the
    absence of an identity was indistinguishable from having one.

    There is deliberately NO fallback to the old scan. A fallback would restore
    exactly the fabrication this refuses, on the path reached when something has
    already gone wrong.
    """
    try:
        matches = sorted(
            path
            for path in projects_dir.rglob("*.jsonl")
            if path.stem == session_id and path.is_file()
        )
    except OSError as exc:
        return None, f"cannot search Claude projects directory {projects_dir}: {exc}"
    if not matches:
        return None, (
            f"no transcript matching session_id {session_id!r} under Claude "
            f"projects directory {projects_dir}"
        )
    if len(matches) > 1:
        return None, (
            f"multiple transcripts matching session_id {session_id!r} under Claude "
            f"projects directory {projects_dir}"
        )

    transcript = matches[0]
    try:
        transcript_text = transcript.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, f"cannot read matching transcript {transcript}: {exc}"
    records = 0
    unparseable = 0
    eligible = 0
    model = None
    # `split("\n")`, NEVER `splitlines()` (counter-model review of this change).
    # JSONL is newline-delimited and `\n` is its only delimiter, but
    # `str.splitlines()` also breaks on U+0085, U+2028, U+2029, \v, \f and the
    # ASCII file/group/record separators - every one of which is legal RAW
    # inside a JSON string. A record whose text merely CONTAINS one would be
    # torn into fragments, so a single valid assistant turn became "2 records,
    # 2 unparseable" and a mid-session switch silently reported the OLDER
    # model: unrelated message content deciding the identity verdict, which is
    # the exact defect class #1109 exists to close. Not hypothetical - 1 of 120
    # real transcripts on this host already carries 19 such characters.
    for line in transcript_text.split("\n"):
        if not line.strip():
            continue
        records += 1
        try:
            record = json.loads(line)
        except ValueError:
            # A truncated or corrupt line is COUNTED, not silently dropped and
            # not pattern-matched. The old scan would happily lift a `"model"`
            # out of a half-written record; a line this parser cannot read is a
            # line it knows nothing about, and it says so in the census below.
            unparseable += 1
            continue
        declared = _eligible_assistant_model(record)
        if declared is None:
            continue
        eligible += 1
        value = declared.strip()
        # THE DOCUMENTED RULE: the LAST eligible assistant model wins, so a
        # genuine mid-session model switch is preserved rather than pinned to
        # whatever answered first. Sentinels (`<synthetic>`) and blanks are
        # declarations without an identity - they are eligible records, so
        # their presence is reported, but they never overwrite a real value.
        if value and not value.startswith("<"):
            model = value
    if model is None:
        return None, (
            f"matching transcript {transcript} contains no real-shaped model entry "
            f"(read {records} record(s); {unparseable} unparseable; "
            f"{eligible} eligible assistant message(s) with a declared model). "
            f"An implementer is taken only from an assistant message's own "
            f"'message.model'; nested tool arguments cannot supply one."
        )
    return f"claude/{model}", None


def _default_claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def build(args: argparse.Namespace) -> dict:
    receipt: dict = {
        "schema": SCHEMA,
        "recorded_at": args.at or _now(),
        "issue": args.issue,
        "branch": args.branch,
        "status": args.status,
        # THE PROPERTY, recorded per run rather than asserted once in prose.
        # "the reviewing model must not be the implementing model" is the rule;
        # a receipt naming both is what makes a violation findable later.
        # A skip had no reviewing model, so it records JSON null rather than
        # fabricating an identity for a review that never happened.
        "reviewer": args.reviewer,
        "implementer": args.implementer,
    }
    # The commit this review was taken against (issue #1171). OPTIONAL, and the
    # optionality is load-bearing: every receipt committed before #1171 has no
    # `head`, and making it required would invalidate all 50 of them at once -
    # `test_every_COMMITTED_receipt_is_well_formed_AND_TRACKED` would red on a
    # corpus nobody touched. Absent therefore means "written before this field
    # existed", which the gate reads as NOT satisfying enrolment for a current
    # head rather than as a failure of the receipt.
    if getattr(args, "head", None):
        receipt["head"] = args.head
    # Where `reviewer` came from (issue #1269). OPTIONAL for the same reason
    # `head` is: every receipt committed before this field has none, and they
    # must keep validating. `cmd_write` always sets it on a `ran` receipt.
    if getattr(args, "reviewer_evidence", None):
        receipt["reviewer_evidence"] = args.reviewer_evidence
    # OPTIONAL for the same reason: every receipt before #1400 has none
    # (issue #1261 introduced the probe; nothing recorded its answer). `ran`
    # only - a skip recorded no review and therefore read nothing.
    if getattr(args, "scope", None) and args.status == "ran":
        receipt["scope"] = args.scope
    # Written ONLY for a delegated run (issue #1383): absent means the default
    # direction, which is what every earlier receipt already means by omission.
    if getattr(args, "direction", DIRECTION_DEFAULT) == DIRECTION_DELEGATED:
        receipt["direction"] = DIRECTION_DELEGATED
        receipt["implementer_evidence"] = args.implementer_evidence
    if args.status == "skipped":
        receipt["skip_reason"] = args.reason
    else:
        receipt["passes"] = args.passes
        receipt["counts"] = {k: getattr(args, k) for k in COUNTS}
        receipt["red_cases"] = {
            "proposed": args.red_cases_proposed,
            "already_covered": args.red_cases_already_covered,
        }
    return receipt


def validate(receipt: dict, source: str = "<receipt>") -> list[str]:
    """SHAPE only. Returns a list of problems; empty means well-formed."""
    bad: list[str] = []

    def need(key: str, kind: type | tuple[type, ...]) -> object | None:
        if key not in receipt:
            bad.append(f"{source}: missing {key!r}")
            return None
        if not isinstance(receipt[key], kind) or isinstance(receipt[key], bool):
            bad.append(f"{source}: {key!r} is {type(receipt[key]).__name__}, expected {kind}")
            return None
        return receipt[key]

    if receipt.get("schema") != SCHEMA:
        bad.append(f"{source}: schema is {receipt.get('schema')!r}, expected {SCHEMA}")
    need("recorded_at", str)
    need("branch", str)
    if not isinstance(receipt.get("issue"), (int, str)):
        bad.append(f"{source}: missing or non-scalar 'issue'")

    status = receipt.get("status")
    if status not in STATUSES:
        bad.append(f"{source}: status {status!r} not in {STATUSES}")
        return bad

    implementer = need("implementer", str)
    reviewer = receipt.get("reviewer")
    if status == "skipped":
        if reviewer is not None:
            bad.append(
                f"{source}: a skipped run must not carry a reviewer; no review happened"
            )
        reviewer = None
    else:
        reviewer = need("reviewer", str)
    # AN EMPTY IDENTITY IS NOT AN IDENTITY. The first cut guarded the comparison
    # with `if reviewer and implementer`, so a receipt naming NEITHER model
    # skipped the check and validated clean - recording "two different models
    # reviewed this" on the strength of two empty strings. A missing identity
    # has to fail the same check a colliding one does.
    for name, value in (("reviewer", reviewer), ("implementer", implementer)):
        if value is not None and not value.strip():
            bad.append(f"{source}: {name} is empty; a run must name the model")
    if reviewer and implementer and reviewer.strip() and implementer.strip():
        # THE PROPERTY, CHECKED. A run whose reviewer IS the implementer is not
        # a counter-model review at all - it is the author agreeing with
        # themselves, recorded as independent evidence. Worse than no receipt,
        # because it is counted.
        if reviewer.strip() == implementer.strip():
            bad.append(
                f"{source}: reviewer and implementer are the same model "
                f"({reviewer!r}); the reviewing model must not be the implementing model"
            )

    head = receipt.get("head")
    if head is not None:
        if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{7,40}", head):
            bad.append(f"{source}: head {head!r} is not a git object name")

    direction = receipt.get("direction", DIRECTION_DEFAULT)
    if direction not in DIRECTIONS:
        bad.append(f"{source}: direction {direction!r} not in {DIRECTIONS}")
        return bad
    delegated = direction == DIRECTION_DELEGATED

    def _names(evidence: object, keys: tuple[str, ...]) -> bool:
        return isinstance(evidence, dict) and all(
            isinstance(evidence.get(k), str) and evidence[k].strip() for k in keys
        )

    # Where each identity came from. On the default direction the CODEX side is
    # the reviewer; on a delegated one it is the implementer and the reviewer is
    # a Claude session (issue #1383). Each pointer is shaped by the side it
    # names, so a receipt cannot carry one direction's evidence under the other
    # direction's label.
    reviewer_keys = ("session_id",) if delegated else ("thread_id", "rollout")
    if "reviewer_evidence" in receipt:
        evidence = receipt["reviewer_evidence"]
        if status == "skipped":
            bad.append(
                f"{source}: a skipped run must not carry 'reviewer_evidence'; "
                "no review happened"
            )
        elif not _names(evidence, reviewer_keys):
            bad.append(
                f"{source}: reviewer_evidence {evidence!r} must name a non-empty "
                + " and ".join(repr(k) for k in reviewer_keys)
            )

    if "scope" in receipt:
        scope = receipt["scope"]
        if status == "skipped":
            bad.append(
                f"{source}: a skipped run must not carry 'scope'; no review happened"
            )
        elif scope not in SCOPES:
            bad.append(f"{source}: scope {scope!r} not in {SCOPES}")

    if delegated:
        # A delegated receipt exists BECAUSE a review happened: the supervising
        # Claude session is always present on that lane, so neither committed
        # skip reason (an inability to run the reviewer) can be true of it.
        if status != "ran":
            bad.append(
                f"{source}: a delegated receipt records a review that happened; "
                f"status {status!r} is not 'ran'"
            )
        if not _names(receipt.get("implementer_evidence"), ("thread_id", "rollout")):
            bad.append(
                f"{source}: a delegated receipt must carry implementer_evidence "
                "naming a non-empty 'thread_id' and 'rollout'"
            )
        if not _names(receipt.get("reviewer_evidence"), ("session_id",)):
            bad.append(
                f"{source}: a delegated receipt must carry reviewer_evidence "
                "naming a non-empty 'session_id'"
            )
        # The direction is checkable against the identities themselves: on a
        # delegated lane the REVIEWER is the Claude session. A receipt saying
        # `delegated` while a non-Claude model reviewed is the default
        # direction mislabelled.
        if isinstance(reviewer, str) and reviewer.strip() \
                and not reviewer.startswith("claude/"):
            bad.append(
                f"{source}: a delegated receipt's reviewer {reviewer!r} is not a "
                "Claude session; the supervising session is the reviewer"
            )
    elif "implementer_evidence" in receipt:
        bad.append(
            f"{source}: 'implementer_evidence' is recorded only on a delegated "
            "receipt; the default direction derives the implementer from a session"
        )

    if status == "skipped":
        if receipt.get("skip_reason") not in SKIP_REASONS:
            bad.append(
                f"{source}: skip_reason {receipt.get('skip_reason')!r} not in {SKIP_REASONS}"
            )
        for absent in ("counts", "red_cases", "passes"):
            if absent in receipt:
                bad.append(f"{source}: a skipped run must not carry {absent!r}")
        return bad

    passes = receipt.get("passes")
    if not isinstance(passes, int) or isinstance(passes, bool) or passes < 1 or passes > 2:
        # Two passes is the documented cap: each one spends the user's quota,
        # and an unbounded loop is how a review stage becomes a cost centre.
        bad.append(f"{source}: passes is {passes!r}, expected 1 or 2")

    counts = receipt.get("counts")
    if not isinstance(counts, dict):
        bad.append(f"{source}: missing 'counts' object")
    else:
        for key in COUNTS:
            v = counts.get(key)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                bad.append(f"{source}: counts.{key} is {v!r}, expected a non-negative int")

    red = receipt.get("red_cases")
    if not isinstance(red, dict):
        bad.append(f"{source}: missing 'red_cases' object")
    else:
        prop, cov = red.get("proposed"), red.get("already_covered")
        for name, v in (("proposed", prop), ("already_covered", cov)):
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                bad.append(f"{source}: red_cases.{name} is {v!r}, expected a non-negative int")
        if isinstance(prop, int) and isinstance(cov, int) and not isinstance(prop, bool) \
                and not isinstance(cov, bool) and cov > prop:
            # The diversity number is `already_covered / proposed`. Covered
            # exceeding proposed makes that ratio exceed 1 and silently corrupts
            # the only measurement that can tell an excellent reviewer from an
            # uncritical author.
            bad.append(
                f"{source}: red_cases.already_covered ({cov}) exceeds proposed ({prop})"
            )
    return bad


def _derive_head(explicit: str | None, cwd: Path | None = None) -> tuple[str | None, str | None]:
    """The commit this review was taken against, DERIVED rather than asserted.

    `--head` exists as an override for tests, but nothing in the flow passes it
    and nothing should have to: the only receipt-write call site lives in
    `.claude/commands/flow/auto.md`, and requiring a flag there would have made
    this field depend on a document being edited in lockstep with this script -
    the same "a marker written by the thing being measured" trap #1048 removed
    from `--reviewer`. Deriving it here means an existing call site produces a
    receipt the finish gate can use, with no edit at all.

    Returns `(head, warning)`. A head that cannot be derived is NOT fatal: the
    receipt is still a valid record of a review, it simply cannot satisfy the
    finish gate's enrolment check for a commit. That is said out loud rather
    than left for the gate to report as a bare `missing` later.
    """
    if explicit:
        return explicit, None
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"could not run git to derive the reviewed commit: {exc}"
    if out.returncode != 0:
        return None, "not a git checkout, so no reviewed commit could be derived"
    head = out.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{7,40}", head):
        return None, f"git returned {head!r}, which is not an object name"
    return head, None


def _tracking_state(path: Path) -> tuple[str, str | None]:
    """Whether git tracks the receipt just written: (state, reason).

    `tests/test_counter_model_review.py` requires every committed receipt to be
    TRACKED, and nothing here used to say that a fresh one is not (issue
    #1269). The helper WARNS and never stages (orchestrator ruling on #1269):
    it runs mid-flow, sometimes while an index is being built, and an index
    mutated behind the caller's back is a harder surprise to see than an
    untracked file.

    Three states, not two. Not being in a work tree, or git failing, is
    `unknown` - never `tracked`, which would be a green for a check that did
    not run.
    """
    where = str(path.parent)
    try:
        inside = subprocess.run(
            ["git", "-C", where, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return "unknown", "not inside a git work tree"
        listed = subprocess.run(
            ["git", "-C", where, "ls-files", "--error-unmatch", "--", path.name],
            capture_output=True, text=True, timeout=10,
        )
        if listed.returncode == 0:
            return "tracked", None
        ignored = subprocess.run(
            ["git", "-C", where, "check-ignore", "-q", "--", path.name],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "unknown", f"could not run git: {exc}"
    if ignored.returncode == 0:
        return "untracked", (
            "ignored by a .gitignore rule, so a plain `git add` will skip it "
            "silently; add a !negation for this directory"
        )
    if ignored.returncode == 1:
        return "untracked", f"stage it: git add {path}"
    return "unknown", f"git check-ignore exited {ignored.returncode}"


def _same_run_receipt(out_dir: Path, branch: str, head: str) -> Path | None:
    """An existing `ran` receipt for this (branch, head), if one is on disk.

    ONE RUN, ONE RECEIPT (issue #1269; Nit Store 5749736750). A run writes a
    single receipt carrying its final totals - `--passes 2` is how a re-review
    is recorded. A second `ran` receipt for the same branch at the same commit
    is a pass-1 receipt followed by a pass-2 one, and a corpus reader cannot
    tell that from two independent runs. A NEW head is a re-review of new
    commits and is a distinct run; a skip is an attempt that did not review, so
    a run after one is not a duplicate of it. Neither is refused.

    NOT A CONCURRENCY LOCK, deliberately (counter-model review, rejected with
    this reason). The scan and the exclusive create are two steps, so two
    writers for one (branch, head) in the same instant could both pass. The
    duplicate this exists for is SEQUENTIAL - one run writing after pass 1 and
    again after pass 2. Two simultaneous writers on one branch at one commit
    would be two sessions driving one checkout, which the #597 worktree claim
    already refuses upstream of this helper.
    """
    for existing in sorted(out_dir.glob("*.json")):
        try:
            data = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (isinstance(data, dict) and data.get("status") == "ran"
                and data.get("branch") == branch
                and _same_commit(data.get("head"), head)):
            return existing
    return None


def _same_commit(a: object, b: object) -> bool:
    """Two object names for one commit, abbreviated or full (counter-model review).

    `validate` accepts 7 to 40 hex characters and the corpus holds both shapes
    (65 full, 1 abbreviated at #1269), so `abc1234` and its full SHA must match.
    An abbreviation IS a prefix of the name it abbreviates - git's own rule -
    so a prefix test decides it without needing a repository to resolve in.
    """
    if not (isinstance(a, str) and isinstance(b, str)):
        return False
    a, b = a.lower(), b.lower()
    short, full = sorted((a, b), key=len)
    return len(short) >= 7 and full.startswith(short)


def _derive_delegated(args: argparse.Namespace) -> str | None:
    """Both identities for a delegated run (issue #1383), or the refusal.

    The inverse of the default direction, with the same rule on each side: the
    IMPLEMENTER is derived from the delegated model's own exec stream and the
    rollout its thread id names, and the REVIEWER from the supervising Claude
    session's transcript. Neither is accepted as a value. A stream that names
    no thread - Qwen Code and OpenCode streams today - is refused rather than
    attributed: there is no rollout to read a model from, and a receipt naming
    an implementer nobody can re-derive is worse than none.
    """
    sessions_dir = args.codex_sessions_dir or _default_codex_sessions_dir()
    implementer, evidence, error = _derive_reviewer_from_exec_log(
        args.implementer_exec_log, sessions_dir, role="implementer"
    )
    if error is not None:
        return error
    projects_dir = args.claude_projects_dir or _default_claude_projects_dir()
    reviewer, error = _derive_implementer_from_session(
        args.reviewer_session_id, projects_dir
    )
    if error is not None:
        return f"reviewer session: {error}"
    args.implementer = implementer
    args.implementer_evidence = evidence
    args.reviewer = reviewer
    args.reviewer_evidence = {"session_id": args.reviewer_session_id}
    return None


def cmd_write(args: argparse.Namespace) -> int:
    delegated = getattr(args, "direction", DIRECTION_DEFAULT) == DIRECTION_DELEGATED
    if delegated:
        error = _derive_delegated(args)
        if error is not None:
            print(f"counter-model-receipt: {error}", file=sys.stderr)
            return EXIT_INVALID
    elif args.status == "ran":
        sessions_dir = args.codex_sessions_dir or _default_codex_sessions_dir()
        reviewer, evidence, error = _derive_reviewer_from_exec_log(
            args.reviewer_exec_log, sessions_dir
        )
        if error is not None:
            print(f"counter-model-receipt: {error}", file=sys.stderr)
            return EXIT_INVALID
        args.reviewer = reviewer
        args.reviewer_evidence = evidence
        # Re-measure the caller's pre-run scope CLAIM against the same exec
        # log the reviewer identity was just derived from (issue #1400): a
        # probe that passed before the review started is not trusted alone
        # for the review's whole duration.
        if getattr(args, "scope", None) == "full":
            exec_text = args.reviewer_exec_log.read_text(encoding="utf-8")
            failures = _mid_run_sandbox_failures(exec_text)
            if failures:
                print(
                    f"counter-model-receipt: NOTE - downgrading scope 'full' to "
                    f"'diff-only': {failures} command_execution item(s) in "
                    f"{args.reviewer_exec_log} could not launch the sandboxed "
                    "exec process (exit_code -1), the same failure mode the "
                    "pre-run probe checks for, so the claimed scope did not "
                    "hold for the review's whole duration",
                    file=sys.stderr,
                )
                args.scope = "diff-only"
    else:
        args.reviewer = None
        args.reviewer_evidence = None

    if not delegated:
        session_id = args.implementer_session_id or os.environ.get("CLAUDE_CODE_SESSION_ID")
        if not session_id:
            print(
                "counter-model-receipt: missing implementer session id; supply "
                "--implementer-session-id or set CLAUDE_CODE_SESSION_ID",
                file=sys.stderr,
            )
            return EXIT_INVALID
        projects_dir = args.claude_projects_dir or _default_claude_projects_dir()
        implementer, error = _derive_implementer_from_session(session_id, projects_dir)
        if error is not None:
            print(f"counter-model-receipt: {error}", file=sys.stderr)
            return EXIT_INVALID
        args.implementer = implementer

    args.head, head_warning = _derive_head(getattr(args, "head", None))
    if head_warning:
        print(
            f"counter-model-receipt: {head_warning}; this receipt will not satisfy "
            "the finish gate's counter-model enrolment check (issue #1171)",
            file=sys.stderr,
        )

    receipt = build(args)
    problems = validate(receipt, "new receipt")
    if problems:
        for p in problems:
            print(f"counter-model-receipt: {p}", file=sys.stderr)
        return EXIT_INVALID

    out_dir = Path(args.dir)
    # A head that could not be derived cannot be matched, so no duplicate can
    # be established; the warning above already says this receipt is weaker.
    if receipt["status"] == "ran" and receipt.get("head") and out_dir.is_dir():
        existing = _same_run_receipt(out_dir, receipt["branch"], receipt["head"])
        if existing is not None:
            print(
                f"counter-model-receipt: {existing} already records a `ran` review "
                f"of branch {receipt['branch']!r} at {receipt['head']}; one run "
                "writes ONE receipt with its final totals (use --passes 2 for a "
                "re-review). Refusing to record the same run twice.",
                file=sys.stderr,
            )
            return EXIT_INVALID
    out_dir.mkdir(parents=True, exist_ok=True)
    # EXCLUSIVE CREATE, and a run id in the name. The first cut keyed the file on
    # a second-resolution timestamp plus the issue, and wrote with write_text:
    # two runs for one issue inside the same second - or two runs replaying the
    # same --at, which the tests do - both "succeeded" and left ONE file. A lost
    # run is invisible in a measurement whose whole purpose is counting runs.
    stamp = receipt["recorded_at"].replace(":", "")
    base = f"{stamp}-issue-{_slug(str(receipt['issue']))}"
    body = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    for attempt in range(100):
        suffix = "" if attempt == 0 else f"-{attempt}"
        path = out_dir / f"{base}{suffix}.json"
        try:
            with path.open("x", encoding="utf-8") as fh:
                fh.write(body)
            break
        except FileExistsError:
            continue
    else:
        print(f"counter-model-receipt: could not find a free name for {base} after "
              f"100 attempts; refusing to overwrite an existing receipt", file=sys.stderr)
        return EXIT_INVALID
    print(f"COUNTER_MODEL_RECEIPT: {path}")
    print(f"COUNTER_MODEL_STATUS: {receipt['status']}")
    tracked, reason = _tracking_state(path)
    print(f"COUNTER_MODEL_TRACKED: {tracked}" + (f" ({reason})" if reason else ""))
    if tracked != "tracked":
        print(
            f"counter-model-receipt: WARNING - receipt is {tracked}: {reason}. "
            "The suite requires every committed receipt to be tracked; this "
            "helper does not stage it.",
            file=sys.stderr,
        )
    return EXIT_OK


def cmd_parse(args: argparse.Namespace) -> int:
    try:
        text = Path(args.transcript).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"counter-model-receipt: cannot read {args.transcript}: {exc}", file=sys.stderr)
        print("COUNTER_MODEL_REVIEW: unparseable")
        return EXIT_INVALID

    verdict, findings = parse_review(text)
    print(f"COUNTER_MODEL_FINDINGS: {len(findings)}")
    for f in findings:
        print(f"COUNTER_MODEL_FINDING: [{f['severity']}] {f['title']}")
    print(f"COUNTER_MODEL_REVIEW: {verdict}")
    # An unparseable transcript is NOT a clean review and must not be recorded
    # as one; non-zero so a caller that forgets to read the verdict still stops.
    # A format mismatch is non-zero for the same reason: its findings were NOT
    # counted, so a caller reading only the exit code must not proceed as if
    # they had been.
    if verdict == PARSE_FORMAT_MISMATCH:
        print("counter-model-receipt: the Findings section carries findings in a shape "
              "this parser does not read - the review HAPPENED. Do not record it as a "
              "skip; see /flow:auto Step 6 item 1c.", file=sys.stderr)
    return EXIT_INVALID if verdict in (PARSE_UNPARSEABLE, PARSE_FORMAT_MISMATCH) else EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    paths = sorted(Path(args.dir).glob("*.json"))
    if not paths:
        # AN EMPTY DIRECTORY IS NOT A CLEAN RESULT. "No receipts" and "no runs
        # with problems" are different facts; conflating them is how the
        # original 0-of-170 went unnoticed for two months.
        print(f"counter-model-receipt: no receipts under {args.dir} - nothing was "
              f"examined, so this is UNKNOWN, not clean.", file=sys.stderr)
        print("COUNTER_MODEL_EXAMINED: 0")
        print("COUNTER_MODEL_RECEIPTS: unknown")
        return EXIT_INVALID

    problems: list[str] = []
    for path in paths:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path}: unreadable ({exc})")
            continue
        problems.extend(validate(receipt, str(path)))

    print(f"COUNTER_MODEL_EXAMINED: {len(paths)}")
    for p in problems:
        print(f"COUNTER_MODEL_PROBLEM: {p}")
    print(f"COUNTER_MODEL_RECEIPTS: {'invalid' if problems else 'ok'}")
    return EXIT_INVALID if problems else EXIT_OK


def cmd_skip_reasons(args: argparse.Namespace) -> int:
    """Print the committed skip reasons, one per line.

    `flow-finish-gate.sh` validates a `skipped: <reason>` enrolment line against
    this set and reads it from HERE rather than carrying its own copy (issue
    #1171). A second declaration in shell is the cross-language drift #890 and
    #1147 kept removing from this repository, and it fails in the dangerous
    direction: a shell copy still listing a reason Python has retired accepts a
    skip the committed set refuses - which is how `explicit-opt-out` would come
    back without anyone re-adding it to SKIP_REASONS.
    """
    for reason in SKIP_REASONS:
        print(reason)
    return 0


def cmd_rollout_model(args: argparse.Namespace) -> int:
    """Derive one Codex exec stream's reviewing model and print it alone.

    Issue #1400 (Nit Store #864 comment 5867878058): `/codex:code_review` and
    `/codex:ask` used to hand-roll this derivation in shell - `find ... | head
    -1` for the rollout, then `grep -o '"model":"[^"]*"' | head -1` for the
    model - which is exactly the whole-file-first-match bug #1269 removed
    from this script, re-introduced a second time in two command documents
    that never called back into the fix. This subcommand is the one
    implementation both now call, so there is one place this can go wrong
    again rather than three.

    Prints `codex/<model>` to stdout and exits 0 on success. On any refusal
    (ambiguous match, undeclared model, disagreeing turns, ...) prints
    nothing to stdout, prints the reason to stderr, and exits 1 - a caller
    that only checks the exit code still gets an empty MODEL, never a wrong
    one.
    """
    sessions_dir = args.sessions_dir or _default_codex_sessions_dir()
    model, _evidence, error = _derive_reviewer_from_exec_log(
        args.exec_log, sessions_dir, role=args.role
    )
    if error is not None:
        print(f"counter-model-receipt: {error}", file=sys.stderr)
        return EXIT_INVALID
    print(model)
    return EXIT_OK


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="record one run", allow_abbrev=False)
    w.add_argument("--dir", default=str(RECEIPT_DIR))
    w.add_argument("--issue", required=True)
    w.add_argument("--branch", required=True)
    w.add_argument("--status", required=True, choices=STATUSES)
    w.add_argument("--reason", choices=SKIP_REASONS, help="required when --status skipped")
    w.add_argument(
        "--reviewer-exec-log",
        type=Path,
        help="Codex --json exec stream from which to derive the REVIEWING model",
    )
    w.add_argument(
        "--codex-sessions-dir",
        type=Path,
        help="Codex sessions root (defaults to $CODEX_HOME/sessions or ~/.codex/sessions)",
    )
    w.add_argument(
        "--scope",
        choices=SCOPES,
        help="/codex:code_review's pre-run CODEX_REVIEW_SCOPE claim (issue "
             "#1400); re-measured against --reviewer-exec-log and downgraded "
             "from 'full' if any command_execution item there could not "
             "launch the sandboxed exec process",
    )
    w.add_argument(
        "--implementer-session-id",
        help="Claude session from which to derive the IMPLEMENTING model "
             "(defaults to $CLAUDE_CODE_SESSION_ID)",
    )
    w.add_argument(
        "--claude-projects-dir",
        type=Path,
        help="Claude projects root (defaults to ~/.claude/projects)",
    )
    w.add_argument(
        "--implementer-exec-log",
        type=Path,
        help="DELEGATED lane (issue #1383): the delegated model's --json exec "
             "stream, from which to derive the IMPLEMENTING model",
    )
    w.add_argument(
        "--reviewer-session-id",
        help="DELEGATED lane (issue #1383): the supervising Claude session that "
             "reviewed the diff, from which to derive the REVIEWING model "
             "(defaults to $CLAUDE_CODE_SESSION_ID when --implementer-exec-log is given)",
    )
    w.add_argument("--passes", type=int, default=1)
    for k in COUNTS:
        w.add_argument(f"--{k}", type=int, default=0)
    w.add_argument("--red-cases-proposed", type=int, default=0)
    w.add_argument("--red-cases-already-covered", type=int, default=0)
    w.add_argument(
        "--head",
        help="the commit this review was taken against (issue #1171); "
             "the finish gate matches it against the current HEAD by ancestry",
    )
    w.add_argument("--at", help="override the timestamp (tests)")
    w.set_defaults(func=cmd_write)

    pr = sub.add_parser("parse", help="read a reviewer transcript and report its verdict")
    pr.add_argument("transcript", help="path to the reviewer's output")
    pr.set_defaults(func=cmd_parse)

    v = sub.add_parser("validate", help="check the shape of every committed receipt")
    v.add_argument("--dir", default=str(RECEIPT_DIR))
    v.set_defaults(func=cmd_validate)

    sr = sub.add_parser("skip-reasons",
                        help="print the committed skip reasons, one per line")
    sr.set_defaults(func=cmd_skip_reasons)

    rm = sub.add_parser(
        "rollout-model",
        help="derive one Codex --json exec stream's model from its rollout "
             "(issue #1400: the one implementation /codex:code_review and "
             "/codex:ask should both call instead of hand-rolled grep/find)",
    )
    rm.add_argument("--exec-log", type=Path, required=True)
    rm.add_argument("--sessions-dir", type=Path)
    rm.add_argument("--role", default="reviewer")
    rm.set_defaults(func=cmd_rollout_model)

    args = ap.parse_args()
    if args.cmd == "write":
        # The direction is DERIVED from which evidence was supplied, never
        # declared by a flag of its own (issue #1383): a `--direction` value
        # would be one more assertion about the run, the thing #1048 removed.
        if args.implementer_exec_log is not None:
            args.direction = DIRECTION_DELEGATED
            if args.status != "ran":
                ap.error("--implementer-exec-log records a delegated review that "
                         "happened; it requires --status ran")
            if args.reviewer_exec_log is not None or args.implementer_session_id:
                ap.error("--implementer-exec-log (delegated: Codex implements, Claude "
                         "reviews) cannot be combined with --reviewer-exec-log or "
                         "--implementer-session-id (the other direction)")
            if args.scope:
                ap.error("--scope measures a Codex REVIEWER's sandbox access "
                         "(/codex:code_review); the delegated direction's "
                         "reviewer is a Claude session and has no such probe")
            args.reviewer_session_id = (args.reviewer_session_id
                                        or os.environ.get("CLAUDE_CODE_SESSION_ID"))
            if not args.reviewer_session_id:
                ap.error("--implementer-exec-log requires --reviewer-session-id or "
                         "CLAUDE_CODE_SESSION_ID: the reviewing Claude session")
        else:
            args.direction = DIRECTION_DEFAULT
            if args.reviewer_session_id:
                ap.error("--reviewer-session-id is the delegated direction and "
                         "requires --implementer-exec-log")
    if args.cmd == "write" and args.status == "skipped" and not args.reason:
        ap.error("--status skipped requires --reason")
    if (args.cmd == "write" and args.status == "skipped"
            and args.reviewer_exec_log is not None):
        ap.error("--status skipped must not carry --reviewer-exec-log; no review happened")
    if args.cmd == "write" and args.status == "skipped" and args.scope:
        ap.error("--status skipped must not carry --scope; no review happened")
    if (args.cmd == "write" and args.status == "ran"
            and args.direction != DIRECTION_DELEGATED
            and args.reviewer_exec_log is None):
        ap.error("--status ran requires --reviewer-exec-log")
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
