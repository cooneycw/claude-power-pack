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

NEW WRITES
----------
Schema 5 selects evidence independently for each role and binds the reviewed
artifact through runtime HEAD execution or exact captured patch bytes (#1584).
Schemas 1-4 retain historical shape validation, without a corpus migration.

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
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
# A receipt using extra_passes_reason declares this instead (issue #1495).
# No committed receipt uses that field yet, so no existing file needs a shim.
SCHEMA_EXTRA_PASSES = 2
SCHEMA_FLOW_SCOPE = 3
# A receipt whose retained Codex implementation rollout names more than one
# real turn model carries the complete derived set under `implementers`. The
# reviewer remains scalar: independence means it intersects none of this set.
SCHEMA_IMPLEMENTER_SET = 4
SCHEMA_ADAPTERS = 5
# The committed corpus tops out at 2 passes. The only historical extra-pass
# request was #1320, exactly pass 3 (fc87b5b8 / PR #1457); nothing above 3
# has ever been requested in the repository's review history.
PASSES_HARD_CEILING = 3
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
#: `scope` is REQUIRED on a default-direction `ran` receipt recorded at or after
#: this instant (issue #1461). Before it the field was optional, and 204 of the
#: 214 committed receipts carry none, so they stay valid. This is a COMPATIBILITY
#: WINDOW, not a security boundary: `recorded_at` is self-asserted, which is why
#: the CLI requires --scope on every write regardless of date and only
#: `validate()` - reading historical files - consults this cutoff.
SCOPE_REQUIRED_FROM = "2026-10-17T00:00:00Z"
#: Output fragments that mean a command RAN and was DENIED a read (issue #1461).
#: An ordinary non-zero exit is NOT a denial - a `grep` with no match also exits
#: 1 and streams exactly like a refused `cat` (measured, codex-cli 0.162.1) - so
#: only the text separates them. The reviewer runs under LC_ALL=C, so coreutils
#: and the shell print these in this form.
READ_DENIAL_MARKERS = ("permission denied", "operation not permitted")
# /codex:code_review's pre-run CODEX_REVIEW_NETWORK verdict (issue #1450).
NETWORKS = ("blocked", "open", "unverified")
# /codex:code_review's CODEX_REVIEW_LOCAL_CREDENTIALS verdict (issue #1459).
LOCAL_CREDENTIALS = ("present", "absent", "unknown")

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


def rollout_implementer_models(rollout_text: str) -> tuple[list[str] | None, str | None]:
    """All real turn models in one implementing Codex rollout, in first-seen order.

    The whole retained rollout remains the evidence boundary. Unlike reviewer
    attribution, a model switch in an implementation is representable rather
    than ambiguous, but one unknown turn still makes the complete set unknown.
    A caller cannot select a window or supply any model name.
    """
    turn_contexts = 0
    undeclared = 0
    unparseable = 0
    models: list[str] = []
    seen: set[str] = set()
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
            normalized = model.strip()
            if normalized not in seen:
                seen.add(normalized)
                models.append(normalized)
        else:
            undeclared += 1
    if turn_contexts == 0 and not unparseable:
        return None, "no turn_context record"
    if unparseable:
        return None, (
            f"{unparseable} unparseable line(s) beside {turn_contexts} turn_context "
            "record(s); an implementing turn's model may be among them, so the "
            "implementing models are not established"
        )
    if undeclared:
        return None, (
            f"{undeclared} of {turn_contexts} turn_context record(s) declare no "
            "payload.model; the implementing models are not established"
        )
    return models, None


# Fresh-flow attribution is deliberately a literal native-harness adapter, not
# a shell interpreter or an authorship detector. Unsupported anchors refuse.
class FlowScopeRefused(ValueError):
    pass


def _flow_need(condition: bool, reason: str) -> None:
    if not condition:
        raise FlowScopeRefused(reason)


def _flow_git(*args: str, strip: bool = True) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, timeout=15)
    _flow_need(result.returncode == 0, "cannot verify flow scope against Git")
    return result.stdout.rstrip("\n") if strip else result.stdout


def _flow_shell_commands(script: str) -> list[list[str]]:
    """Split only unquoted literal separators; never execute source text."""
    # Remove closed quoted heredoc data before lexing command syntax. The body
    # cannot supply commands, separators, or proof. Only Python may precede an
    # anchor in a supported sequence; other heredocs remain opaque commands.
    lines = script.splitlines(keepends=True)
    rendered = []
    cursor = 0
    while cursor < len(lines):
        line = lines[cursor]
        match = re.search(r"<<'([A-Za-z_][A-Za-z_0-9]*)'\s*$", line.rstrip("\n"))
        if match:
            prefix = line[: match.start()]
            rendered.append(prefix + "__FLOW_HEREDOC__\n")
            cursor += 1
            while cursor < len(lines) and lines[cursor].rstrip("\n") != match.group(1):
                cursor += 1
            _flow_need(cursor < len(lines), "unclosed quoted heredoc")
        else:
            rendered.append(line)
        cursor += 1
    source = "".join(rendered)
    segments = []
    current = []
    quote = None
    escaped = False
    for char in source:
        if escaped:
            current.append("__FLOW_LITERAL_GT__" if char == ">" else char)
            escaped = False
        elif char == "\\" and quote != "'":
            current.append(char)
            escaped = True
        elif quote:
            current.append("__FLOW_LITERAL_GT__" if char == ">" else char)
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            current.append(char)
            quote = char
        elif char in ";\n":
            if "".join(current).strip():
                segments.append("".join(current))
            current = []
        else:
            current.append(char)
    _flow_need(not quote and not escaped, "unclosed shell quoting")
    if "".join(current).strip():
        segments.append("".join(current))
    result = []
    for segment in segments:
        try:
            lexer = shlex.shlex(segment, posix=True, punctuation_chars="|&;<>(){}")
            lexer.whitespace_split = True
            lexer.commenters = ""
            result.append(list(lexer))
        except ValueError as exc:
            raise FlowScopeRefused("unclosed shell quoting") from exc
    return result


def _flow_bounded_sequence(parts: list[list[str]]) -> bool:
    """The small preparation vocabulary observed in supported original flows."""
    for original in parts:
        words = list(original)
        while words and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*=.*", words[0]):
            assignment = words.pop(0)
            if not assignment.startswith(("CLAUDE_PID=", "CLAUDE_CODE_SESSION_ID=")):
                return False
            if "`" in assignment or ("$" in assignment and not assignment.endswith("=$CODEX_THREAD_ID")):
                return False
        if not words or any("`" in word or "$" in word for word in words):
            return False
        name = Path(words[0]).name
        if name in (
            "flow-start-resolve.sh",
            "flow-plan-record.py",
            "flow-live-driver-guard.sh",
            "flow-stale-check.sh",
            "flow-wave-registry.sh",
        ):
            if any(word in ("|", "||", "&&", "&", "(", ")", "{", "}") for word in words):
                return False
            continue
        if words in (["pwd"], ["git", "status", "--short"], ["git", "status", "--porcelain"]):
            continue
        if name == "cat" and len(words) == 2 and words[1].startswith("/"):
            continue
        if words in (
            ["python3", "__FLOW_HEREDOC__"],
            ["python3", "-", "__FLOW_HEREDOC__"],
            ["uv", "run", "python", "-", "__FLOW_HEREDOC__"],
        ):
            continue
        if (
            words[:6] == ["uv", "sync", "--locked", "--extra", "dev", ">"]
            and len(words) == 10
            and words[6].startswith("/")
            and words[7:] == ["2", ">&", "1"]
        ):
            continue
        if name == "rg":
            # Original read-only discovery may pipe rg output through rg/head.
            stages = []
            stage = []
            for word in [*words, "|"]:
                if word == "|":
                    if not stage or Path(stage[0]).name not in ("rg", "head"):
                        return False
                    stages.append(stage)
                    stage = []
                elif word in ("||", "&&", "&", ">", "<", ">>", "(", ")", "{", "}"):
                    return False
                else:
                    stage.append(word)
            if stages:
                continue
        return False
    return True


def _flow_path(value: str, *, audit: bool) -> Path:
    return Path(os.path.normpath(value)) if audit else Path(value).resolve()


def _flow_commands(records: list[dict], branch: str, thread_id: str, root: Path, *, audit: bool = False) -> list[dict]:
    """Use harness execution events, never printed native response blocks."""
    issue = branch.split("-", 2)[1]
    completed = []
    identities = set()
    begin_seen = False
    for number, record in enumerate(records, 1):
        if record.get("type") != "event_msg":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        item = payload.get("item")
        if not isinstance(item, dict):
            continue
        candidate_output = item.get("aggregated_output")
        creation_output = (
            isinstance(candidate_output, str) and "WT_CREATED=" in candidate_output and branch in candidate_output
        )
        if item.get("type") != "CommandExecution":
            _flow_need(not creation_output, "malformed target execution item")
            continue
        argv = item.get("command")
        output = item.get("aggregated_output")
        raw = " ".join(argv) if isinstance(argv, list) and all(isinstance(x, str) for x in argv) else ""
        if not (
            isinstance(argv, list) and len(argv) == 3 and argv[:2] == ["/bin/bash", "-lc"] and isinstance(argv[2], str)
        ):
            _flow_need(
                not creation_output and "flow-start-resolve.sh" not in raw and "flow-plan-record.py" not in raw,
                "unsupported execution argv",
            )
            continue
        try:
            parts = _flow_shell_commands(argv[2])
        except FlowScopeRefused as exc:
            _flow_need(
                not creation_output and "flow-start-resolve.sh" not in raw and "flow-plan-record.py" not in raw,
                f"{exc} at record {number}",
            )
            continue
        from urllib.parse import unquote, urlparse

        encoded_cwd = item.get("cwd")
        execution_cwd = (
            _flow_path(unquote(urlparse(encoded_cwd).path), audit=audit)
            if isinstance(encoded_cwd, str) and encoded_cwd.startswith("file:///")
            else None
        )
        targets = []
        all_plan_parts = []
        for index, words in enumerate(parts):
            offset = 0
            while offset < len(words) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*=.*", words[offset]):
                offset += 1
            words = words[offset:]
            if not words:
                continue
            if Path(words[0]).name == "flow-plan-record.py":
                all_plan_parts.append((index, words))
                if (
                    len(words) != 3
                    or words[1] not in ("reconcile", "read-issue", "begin-run", "approve")
                    or words[2] != issue
                ):
                    continue
                _flow_need(not any("$" in x or "`" in x for x in words), "dynamic flow helper arguments")
                targets.append((index, words))
            elif Path(words[0]).name == "flow-start-resolve.sh" and len(words) > 1 and words[1] == issue:
                if ">" in words:
                    redirect = words.index(">")
                    _flow_need(
                        redirect == len(words) - 2
                        and words[-1].startswith("/")
                        and not any(
                            "$" in x or "`" in x or any(c in x for c in "|&;<>()")
                            for x in words[:redirect] + [words[-1]]
                        )
                        and index + 1 < len(parts)
                        and parts[index + 1] == ["cat", words[-1]],
                        "unsupported redirected creation transport",
                    )
                    words = words[:redirect]
                    _flow_need(
                        isinstance(output, str)
                        and re.findall(r"^Preparing worktree \(new branch '([^']+)'\)$", output, re.M) == [branch],
                        "redirected creation lacks unique new-branch diagnostic",
                    )
                _flow_need(
                    not any("$" in x or "`" in x or any(c in x for c in "|&;<>()") for x in words),
                    "dynamic flow helper arguments",
                )
                _flow_need(
                    len(words) == 3 or len(words) == 5 and words[3] == "--session-cwd" and words[4].startswith("/"),
                    "unsupported creation arguments or redirection",
                )
                # Creation must be independently attributable: no opaque
                # auxiliary command may manufacture fresh-worktree evidence.
                trailing = parts[index + 1 :]
                redirected = ">" in parts[index]
                if redirected:
                    _flow_need(index == 0 and len(trailing) in (1, 2), "unsupported creation sequence")
                    if len(trailing) == 2:
                        other = trailing[1]
                        _flow_need(
                            len(other) == 3
                            and Path(other[0]).name == "flow-plan-record.py"
                            and other[1] == "head-check"
                            and other[2].isdigit()
                            and other[2] != issue,
                            "unsupported trailing creation command",
                        )
                else:
                    _flow_need(len(parts) == 1, "creation must have no auxiliary commands")
                targets.append((index, words))
            elif words in (["git", "status", "--short"], ["git", "status", "--porcelain"]):
                _flow_need(offset == 0, "environment overrides on Git status are unsupported")
                if not begin_seen and execution_cwd == root:
                    targets.append((index, words))
        if execution_cwd == root and any(
            Path(words[0]).name == "flow-plan-record.py" and words[1] == "begin-run" for _, words in targets
        ):
            begin_seen = True
        if not targets or not any(
            Path(words[0]).name != "flow-plan-record.py" or words[1] != "read-issue" for _, words in targets
        ):
            continue
        _flow_need(
            not any(
                word
                in (
                    "if",
                    "then",
                    "else",
                    "fi",
                    "for",
                    "while",
                    "until",
                    "do",
                    "done",
                    "case",
                    "esac",
                    "function",
                    "eval",
                    "source",
                    ".",
                    "{",
                    "}",
                    "()",
                    "(",
                    ")",
                )
                for words in parts
                for word in words
            ),
            "unsupported shell control structure",
        )
        _flow_need(_flow_bounded_sequence(parts), "unsupported whole shell sequence")
        identity = item.get("id")
        _flow_need(
            isinstance(identity, str) and bool(identity) and identity not in identities,
            "duplicate or absent execution identity",
        )
        identities.add(identity)
        valid_execution = (
            payload.get("type") == "item_completed"
            and payload.get("thread_id") == thread_id
            and isinstance(payload.get("turn_id"), str)
            and item.get("source") == "unified_exec_startup"
            and item.get("status") == "completed"
            and type(item.get("exit_code")) is int
            and item["exit_code"] == 0
            and isinstance(output, str)
        )
        cwd = item.get("cwd")
        _flow_need(isinstance(cwd, str) and cwd.startswith("file:///"), "unsupported execution cwd")
        from urllib.parse import unquote, urlparse

        cwd = unquote(urlparse(cwd).path)
        verdicts = list(re.finditer(r"^FLOW_PLAN_RECORD_EXIT=(.*)$", output or "", re.M))
        if all_plan_parts:
            _flow_need(
                len(verdicts) == len(all_plan_parts) and all(v.group(1) == "0" for v in verdicts),
                f"missing or conflicting per-helper verdicts at record {number}",
            )
        for index, words in targets:
            helper_output = output
            completed.append(
                {
                    "argv": words,
                    "cwd": cwd,
                    "line": number,
                    "index": index,
                    "call_id": identity,
                    "turn_id": payload["turn_id"],
                    "output": helper_output,
                    "exit_code": item.get("exit_code"),
                    "valid_execution": valid_execution,
                }
            )
    return completed


def _flow_fields(text: str) -> dict[str, str]:
    fields = {}
    for line in text.split("\n"):
        match = re.fullmatch(r"([A-Z][A-Z_]+)=(.*)", line)
        if match:
            _flow_need(match.group(1) not in fields, "duplicate flow creation field")
            fields[match.group(1)] = match.group(2)
    return fields


_FLOW_PROOF_KEYS = frozenset(
    {
        "version",
        "kind",
        "issue",
        "run_id",
        "branch",
        "base",
        "head",
        "approved_plan_sha256",
        "rollout_sha256",
        "rollout_bytes",
        "snapshot_records",
        "start_line",
        "creation_line",
        "start_execution_id",
        "creation_sha256",
        "approval_sha256",
        "clean_probe_sha256",
        "included_model_contexts",
        "excluded_prefix_records",
        "excluded_prefix_models",
        "initial_cleanliness",
        "originating_turn_id",
        "approval_execution",
    }
)


def _flow_proof_problems(proof: object, receipt: dict) -> list[str]:
    """Strict public shape/binding checks; private source re-derivation is separate."""
    if not isinstance(proof, dict) or set(proof) != _FLOW_PROOF_KEYS:
        return ["flow_scope has missing or unknown fields"]
    problems = []
    if proof["approval_execution"] != "unverified":
        problems.append("flow_scope approval execution must remain unverified")
    if type(proof["version"]) is not int or proof["version"] != 1 or proof["kind"] != "fresh-flow-run":
        problems.append("flow_scope has unsupported version/kind")
    for key, expected in (
        ("issue", str(receipt.get("issue"))),
        ("branch", receipt.get("branch")),
        ("head", receipt.get("head")),
    ):
        if proof[key] != expected:
            problems.append(f"flow_scope {key} disagrees with receipt")
    for key, length in (
        ("run_id", 32),
        ("base", 40),
        ("head", 40),
        ("approved_plan_sha256", 64),
        ("rollout_sha256", 64),
        ("creation_sha256", 64),
        ("approval_sha256", 64),
    ):
        if not isinstance(proof[key], str) or not re.fullmatch(rf"[0-9a-f]{{{length}}}", proof[key]):
            problems.append(f"flow_scope {key} is not a bounded identity")
    cleanliness = proof["initial_cleanliness"]
    clean_hash = proof["clean_probe_sha256"]
    if (
        cleanliness not in ("measured-clean", "unmeasured")
        or cleanliness == "unmeasured"
        and clean_hash is not None
        or cleanliness == "measured-clean"
        and (not isinstance(clean_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", clean_hash))
    ):
        problems.append("flow_scope initial cleanliness evidence disagrees")
    if not isinstance(proof["originating_turn_id"], str) or not proof["originating_turn_id"]:
        problems.append("flow_scope originating turn identity is invalid")
    for key in ("rollout_bytes", "snapshot_records", "start_line", "creation_line", "included_model_contexts"):
        if type(proof[key]) is not int or not 1 <= proof[key] <= 1024**3:
            problems.append(f"flow_scope {key} is not a bounded positive count")
    if type(proof["excluded_prefix_records"]) is not int or proof["excluded_prefix_records"] < 0:
        problems.append("flow_scope excluded prefix count is invalid")
    if (
        type(proof["start_line"]) is int
        and type(proof["snapshot_records"]) is int
        and (
            proof["start_line"] > proof["snapshot_records"]
            or proof["excluded_prefix_records"] != proof["start_line"] - 1
        )
    ):
        problems.append("flow_scope record bounds disagree")
    models = proof["excluded_prefix_models"]
    if (
        not isinstance(models, list)
        or any(not isinstance(m, str) or not m.strip() or len(m) > 128 for m in models)
        or len(set(m for m in models if isinstance(m, str))) != len(models)
    ):
        problems.append("flow_scope excluded model population is invalid")
    if not isinstance(proof["start_execution_id"], str) or not 1 <= len(proof["start_execution_id"]) <= 256:
        problems.append("flow_scope call identity is invalid")
    if (
        receipt.get("status") != "ran"
        or receipt.get("direction", DIRECTION_DEFAULT) != DIRECTION_DEFAULT
        or not str(receipt.get("implementer", "")).startswith("codex/")
    ):
        problems.append("flow_scope requires a ran default-direction Codex implementer")
    return problems


def _flow_argv(command: dict, *, require_supported: bool = True) -> tuple[list[str], str | None]:
    return command["argv"], command["cwd"]


def _flow_scope_model(
    text: str, thread_id: str, args: argparse.Namespace, *, audit: bool = False, historical_root: Path | None = None
) -> tuple[str, dict]:
    _flow_need(text.endswith("\n"), "incomplete original rollout snapshot")
    records = []
    lines = text.split("\n")[:-1]
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise FlowScopeRefused("unparseable original rollout record") from exc
        _flow_need(isinstance(record, dict), "unsupported original rollout record")
        records.append(record)
    headers = [r.get("payload", {}) for r in records if r.get("type") == "session_meta"]
    _flow_need(
        len(headers) == 1 and isinstance(headers[0], dict) and headers[0].get("id") == thread_id,
        "original thread identity disagrees",
    )
    models = []
    for number, record in enumerate(records, 1):
        if record.get("type") == "turn_context":
            payload = record.get("payload")
            model = payload.get("model") if isinstance(payload, dict) else None
            if not isinstance(model, str) or not model.strip():
                raise FlowScopeRefused("undeclared original model turn")
            models.append((number, model.strip()))
    run = args.implementer_flow_run
    issue, branch = str(args.issue), args.branch
    _flow_need(bool(re.fullmatch(r"[0-9a-f]{32}", run)), "unsupported flow run identity")
    _flow_need(
        bool(re.fullmatch(r"[1-9][0-9]*", issue)) and branch.startswith(f"issue-{issue}-"),
        "scope issue/branch identity disagrees",
    )
    root = historical_root if audit else Path(_flow_git("rev-parse", "--show-toplevel")).resolve()
    _flow_need(isinstance(root, Path) and root.is_absolute(), "missing absolute historical worktree identity")
    head = args.head if audit else _flow_git("rev-parse", "HEAD")
    if audit:
        _flow_need(_flow_git("rev-parse", f"{head}^{{commit}}") == head, "recorded head is unavailable")
    else:
        _flow_need(not args.head or args.head == head, "scoped head must be the actual current head")
        _flow_need(_flow_git("symbolic-ref", "--short", "HEAD") == branch, "actual branch disagrees with scope")
    commands = _flow_commands(records, branch, thread_id, root, audit=audit)
    starts = []
    clean = []
    mints = []
    begins = []
    approvals = []
    for command in commands:
        argv, cwd = _flow_argv(command)
        output = command["output"]
        creation = (
            bool(argv)
            and Path(argv[0]).name == "flow-start-resolve.sh"
            and len(argv) > 1
            and argv[1] == issue
            or isinstance(output, str)
            and "WT_CREATED=" in output
            and branch in output
        )
        if creation:
            _flow_need(
                argv and Path(argv[0]).name == "flow-start-resolve.sh" and len(argv) >= 2 and argv[1] == issue,
                "unsupported or contradictory creation call",
            )
            starts.append(command)
        if not argv or cwd is None:
            continue
        if _flow_path(cwd, audit=audit) != root:
            continue
        if argv == ["git", "status", "--short"] or argv == ["git", "status", "--porcelain"]:
            clean.append(command)
        if Path(argv[0]).name == "flow-plan-record.py" and len(argv) == 3 and argv[2] == issue:
            if argv[1] == "reconcile":
                mints.append(command)
            elif argv[1] == "begin-run":
                begins.append(command)
            elif argv[1] == "approve":
                approvals.append(command)
    _flow_need(len(starts) == 1, "missing, reused or conflicting fresh creation")
    start = starts[0]
    _flow_need(start["valid_execution"] and isinstance(start["output"], str), "incomplete creation execution")
    fields = _flow_fields(start["output"])
    _flow_need(
        start["valid_execution"]
        and fields.get("WT_CREATED") == "1"
        and fields.get("LANE") in ("fresh", "cross-repo")
        and fields.get("BRANCH") == branch
        and fields.get("WT_BASE") == "origin/main"
        and fields.get("WT_PATH")
        and _flow_path(fields["WT_PATH"], audit=audit) == root
        and fields.get("FLOW_START_RESOLVE_EXIT") == "0"
        and re.findall(r"^FLOW_START_RESOLVE: ok$", start["output"], re.M) == ["FLOW_START_RESOLVE: ok"],
        "creation is not a verified fresh worktree",
    )
    _flow_need(len(mints) == len(begins) == len(approvals) == 1, "missing or overlapping flow-run anchors")
    mint, begin, approval = mints[0], begins[0], approvals[0]

    def key(command: dict) -> tuple[int, int]:
        return command["line"], command["index"]

    _flow_need(key(start) < key(mint) < key(begin) < key(approval), "flow anchors are out of order")
    _flow_need(
        all(c["valid_execution"] for c in (start, mint, begin, approval)),
        "flow anchor events did not complete in a supported ordered invocation",
    )
    _flow_need(
        f"FLOW_PLAN_RUN: minted {run}\n" in mint["output"]
        and f"({run}) in docs/flow-runs/issue-{issue}.md" in begin["output"],
        "run mint/begin identity disagrees",
    )
    anchor_outputs = [
        (mint, rf"^FLOW_PLAN_RUN: minted {run}$"),
        (begin, rf"^FLOW_PLAN_RECORD: began run [1-9][0-9]* \({run}\) in docs/flow-runs/issue-{issue}\.md(?: - .*|)$"),
        (approval, r"^FLOW_PLAN_RECORD: baseline stamped [0-9a-f]{64}$"),
    ]
    output_positions = []
    for command, pattern in anchor_outputs:
        matches = list(re.finditer(pattern, command["output"], re.M))
        _flow_need(len(matches) == 1, "missing or ambiguous helper output anchor")
        output_positions.append((command["line"], matches[0].start()))
    _flow_need(
        output_positions == sorted(output_positions) and len(set(output_positions)) == 3,
        "helper output anchors are out of source order",
    )
    probes = [c for c in clean if key(start) < key(c) < key(begin)]
    _flow_need(all(c["valid_execution"] and c["output"] == "" for c in probes), "dirty initial Git-visible probe")
    cleanliness = "measured-clean" if probes else "unmeasured"
    digest = re.findall(r"FLOW_PLAN_RECORD: baseline stamped ([0-9a-f]{64})(?:\n|$)", approval["output"])
    _flow_need(len(digest) == 1, "missing or ambiguous approved-plan digest")
    record_text = _flow_git("show", f"{head}:docs/flow-runs/issue-{issue}.md", strip=False)
    marks = list(re.finditer(r"^<!-- flow-run n=[0-9]+ id=([0-9a-f]{32}) -->$", record_text, re.M))
    matching = [mark for mark in marks if mark.group(1) == run]
    _flow_need(len(matching) == 1, "approved plan has missing or overlapping run identity")
    mark = matching[0]
    later = [m.start() for m in marks if m.start() > mark.start()]
    run_text = record_text[mark.start() : min(later) if later else len(record_text)]
    approved = None
    prefix = ""
    for piece in run_text.splitlines(keepends=True):
        prefix += piece
        # flow-plan-record.section_digest hashes the run section with trailing
        # newlines removed, rather than the complete file's raw bytes.
        if hashlib.sha256(prefix.rstrip("\n").encode()).hexdigest() == digest[0]:
            approved = prefix
            break
    if approved is None:
        raise FlowScopeRefused("approved plan prefix differs from Git head")
    marker = re.findall(rf"<!-- flow-run n=([0-9]+) id={run} -->", approved)
    _flow_need(len(marker) == 1, "approved plan has missing or overlapping run identity")
    section = approved.split(f"id={run} -->", 1)[1]
    _flow_need(not re.search(r"<!-- flow-run ", section), "approved run is not the active final section")
    _flow_need(
        bool(re.search(rf"^- Issue:\s*#{issue}\s*$", section, re.M))
        and bool(re.search(r"^- Approval:\s*granted\s*$", section, re.M)),
        "approval/issue fields disagree",
    )
    bases = re.findall(r"^- Base SHA:\s*([0-9a-f]{40})\s*$", section, re.M)
    _flow_need(len(bases) == 1, "missing or ambiguous approved base")
    base = bases[0]
    initial = re.findall(r"^HEAD is now at ([0-9a-f]{7,40})\b", start["output"], re.M)
    _flow_need(
        len(initial) == 1
        and base.startswith(initial[0])
        and _flow_git("rev-parse", f"{initial[0]}^{{commit}}") == base,
        "fresh creation base disagrees",
    )
    _flow_git("merge-base", "--is-ancestor", base, head)
    origins = [
        (n, r["payload"].get("model"))
        for n, r in enumerate(records, 1)
        if r.get("type") == "turn_context"
        and isinstance(r.get("payload"), dict)
        and r["payload"].get("turn_id") == start["turn_id"]
        and n < start["line"]
    ]
    _flow_need(
        bool(origins) and len({model for _, model in origins}) == 1,
        "execution has no consistent originating model context",
    )
    origin = origins[0]
    included = [origin, *[row for row in models if row[0] > origin[0]]]
    _flow_need(len({model for _, model in included}) == 1, "model changes inside the derived flow span")

    def event_digest(command: dict) -> str:
        return hashlib.sha256((lines[command["line"] - 1] + "\n").encode()).hexdigest()

    proof = {
        "version": 1,
        "kind": "fresh-flow-run",
        "issue": issue,
        "run_id": run,
        "branch": branch,
        "base": base,
        "head": head,
        "approved_plan_sha256": digest[0],
        "rollout_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "rollout_bytes": len(text.encode("utf-8")),
        "snapshot_records": len(records),
        "start_line": origin[0],
        "creation_line": start["line"],
        "start_execution_id": start["call_id"],
        "creation_sha256": event_digest(start),
        "approval_sha256": event_digest(approval),
        "initial_cleanliness": cleanliness,
        "approval_execution": "unverified",
        "originating_turn_id": start["turn_id"],
        "clean_probe_sha256": event_digest(probes[0]) if probes else None,
        "included_model_contexts": len(included),
        "excluded_prefix_records": origin[0] - 1,
        "excluded_prefix_models": sorted({model for line, model in models if line < origin[0]}),
    }
    return included[0][1], proof


def _derive_reviewer_from_exec_log(
    exec_log: Path, sessions_dir: Path, role: str = "reviewer",
    implementer_set: bool = False,
) -> tuple[str | list[str] | None, dict | None, str | None]:
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
    except (OSError, UnicodeError) as exc:
        return None, None, f"cannot read {role} exec log {exec_log}: {exc}"
    records, error = _strict_records(exec_text)
    if error:
        return None, None, f"{role} exec log {exec_log}: {error}"
    thread_id, error = _codex_stream_thread(records)
    if error:
        return None, None, f"{role} exec log {exec_log}: {error}"
    return _derive_codex_from_thread(
        thread_id, sessions_dir, role, implementer_set=implementer_set
    )


def _derive_codex_from_thread(
    thread_id: str, sessions_dir: Path, role: str = "reviewer",
    flow_args: argparse.Namespace | None = None,
    implementer_set: bool = False,
) -> tuple[str | list[str] | None, dict | None, str | None]:
    """`codex/<model>` for one Codex thread, read from that thread's own rollout.

    Shared by the reviewer derivation (thread id read from an exec stream) and,
    since issue #1453, the implementer derivation inside a Codex session (thread
    id read from `$CODEX_THREAD_ID`, which Codex exports to every command it
    runs). One implementation, so the two sides cannot disagree about what a
    rollout says.
    """
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
        rollout_text = rollout.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        return None, None, f"cannot read matching rollout {rollout}: {exc}"
    flow_scope = None
    if flow_args is not None:
        try:
            model, flow_scope = _flow_scope_model(rollout_text, thread_id, flow_args)
            reason = None
        except (FlowScopeRefused, OSError, subprocess.SubprocessError) as exc:
            return None, None, f"fresh-flow scope refused: {exc}"
    else:
        if implementer_set:
            models, reason = rollout_implementer_models(rollout_text)
            model = models
        else:
            model, reason = rollout_turn_model(rollout_text)
    if model is None:
        return None, None, f"{reason} in matching rollout {rollout}"
    evidence = {
        "thread_id": thread_id,
        "rollout": rollout.relative_to(sessions_dir).as_posix(),
    }
    if flow_scope is not None:
        evidence["flow_scope"] = flow_scope
    if isinstance(model, list):
        identities = [f"codex/{item}" for item in model]
        return identities[0] if len(identities) == 1 else identities, evidence, None
    return f"codex/{model}", evidence, None


def _mid_run_sandbox_failures(exec_text: str) -> tuple[int, int]:
    """Count `command_execution` items, and how many of those show the
    SANDBOXED EXEC PROCESS ITSELF failing to launch - never a command that
    ran and merely returned a non-zero exit (issue #1400, comment
    5858478984). Returns `(failures, examined)`.

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

    `examined` is returned so a zero FAILURE count can be told apart from a
    zero POPULATION (counter-model review, codex gpt-6.1-sol): an exec log
    with no `command_execution` items at all offers no mid-run evidence
    either way, which is a materially weaker claim than "N commands
    launched and none failed" - `cmd_write` treats the two differently
    rather than letting an unexercised re-measurement read as a confirmed
    one.
    """
    failures = 0
    examined = 0
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
        examined += 1
        if item.get("exit_code") == -1 and item.get("status") == "failed":
            failures += 1
    return failures, examined


def _mid_run_read_denials(exec_text: str) -> int:
    """Commands that RAN and were denied a read, by their own output (issue #1461).

    `_mid_run_sandbox_failures` sees only a sandbox that could not launch. A
    claim of `full` is also false when the reviewer's read of some path was
    REFUSED partway through - a different path, a policy that changed - and that
    command launched fine and exited 1. Such a denial is counted; an ordinary
    non-zero exit is not, because it is indistinguishable by exit code from a
    `grep` that found nothing. A file whose CONTENT says "Permission denied" is a
    false denial; it downgrades `full`, which errs safe.
    """
    denials = 0
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
        # EXIT 0 IS NOT EXCLUDED (counter-model review): `cat denied; echo done`
        # prints the denial and exits 0 because its LAST command succeeded. Only
        # a launch failure (-1, counted by _mid_run_sandbox_failures) or an item
        # that never finished (None) is skipped here.
        if item.get("exit_code") in (-1, None):
            continue
        output = item.get("aggregated_output")
        if isinstance(output, str) and any(m in output.lower() for m in READ_DENIAL_MARKERS):
            denials += 1
    return denials


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


class EvidenceUnknown(ValueError):
    """Evidence could not establish an identity or reviewed artifact."""


class EvidenceRefused(ValueError):
    """Readable evidence establishes a violated boundary."""


def _evidence_error(exc: Exception) -> None:
    verdict = "REFUSED" if isinstance(exc, EvidenceRefused) else "UNKNOWN"
    print(f"COUNTER_MODEL_EVIDENCE: {verdict} - {exc}", file=sys.stderr)


def _snapshot(path: Path, root: Path | None = None) -> tuple[dict, list[dict], str]:
    """Hash exactly the bytes parsed, not a later read of a growing session."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvidenceUnknown(f"cannot read evidence {path}: {exc}") from exc
    records, error = _strict_records(raw.decode("utf-8"))
    if error:
        raise EvidenceUnknown(f"unreadable evidence {path}: {error}")
    assert records is not None
    return (
        {
            "path": path.relative_to(root).as_posix() if root else path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        records,
        raw.decode("utf-8"),
    )


def _one(paths: list[Path], description: str) -> Path:
    if len(paths) != 1:
        raise EvidenceUnknown(f"expected one {description}, found {len(paths)}")
    return paths[0]


def _codex_stream_thread(records: list[dict]) -> tuple[str | None, str | None]:
    ids = [r.get("thread_id") for r in records if r.get("type") == "thread.started"]
    if not ids:
        return None, "contains no thread_id from a thread.started event"
    if len(ids) != 1 or not isinstance(ids[0], str) or not ids[0].strip():
        return None, "requires one unambiguous thread.started event"
    runtime, error = _stream_harness(records)
    if error or runtime != "codex":
        return None, error or "not a Codex stream"
    return ids[0], None


def _adapter(args: argparse.Namespace, role: str) -> tuple[list[str], dict, list[dict]]:
    """Role-neutral evidence selection. No adapter accepts a model argument."""
    selectors = [
        (kind, getattr(args, f"{role}_{kind}", None)) for kind in ("thread_id", "rollout", "session_id", "exec_log")
    ]
    selected = [(kind, value) for kind, value in selectors if value is not None and value != ""]
    if not selected and role == "implementer":
        runtime, ident, error = _implementer_source(args)
        if error:
            raise EvidenceUnknown(error)
        selected = [("thread_id" if runtime == "codex" else "session_id", ident)]
    if len(selected) != 1:
        raise EvidenceUnknown(f"{role} requires exactly one evidence selector (thread, rollout, session or exec log)")
    kind, value = selected[0]
    sources: list[dict] = []
    runtime = "claude" if kind == "session_id" else "codex"
    stream: list[dict] = []
    if kind == "exec_log":
        source, stream, _ = _snapshot(value)
        sources.append(source)
        runtime, error = _stream_harness(stream)
        if error:
            raise EvidenceUnknown(error)
        if runtime == "codex":
            value, error = _codex_stream_thread(stream)
            if error:
                raise EvidenceUnknown(error)
    if runtime == "codex":
        root = args.codex_sessions_dir or _default_codex_sessions_dir()
        if kind == "rollout":
            path = value
            source, records, text = _snapshot(path)
            metas = [r.get("payload", {}).get("id") for r in records if r.get("type") == "session_meta"]
            if len(metas) != 1 or not isinstance(metas[0], str) or not metas[0].strip():
                raise EvidenceUnknown("rollout requires exactly one session_meta id")
            value = metas[0]
        else:
            path = _one(
                [p for p in root.rglob("*.jsonl") if p.name.endswith(f"{value}.jsonl")], f"Codex rollout for {value!r}"
            )
            source, records, text = _snapshot(path, root)
        sources.append(source)
        flow_scope = None
        if role == "implementer" and getattr(args, "implementer_flow_run", None):
            model, flow_scope = _flow_scope_model(text, value, args)
            models, error = [model], None
        elif role == "implementer":
            models, error = rollout_implementer_models(text)
        else:
            model, error = rollout_turn_model(text)
            models = [model] if model else None
        if error or not models:
            raise EvidenceUnknown(error or "Codex rollout has no model")
        evidence = {"thread_id": value, "rollout": source["path"]}
        if flow_scope:
            evidence["flow_scope"] = flow_scope
        identities = [f"codex/{model}" for model in models]
    elif runtime == "claude":
        root = args.claude_projects_dir or _default_claude_projects_dir()
        path = _one([p for p in root.rglob("*.jsonl") if p.stem == value], f"Claude transcript for {value!r}")
        source, records, text = _snapshot(path, root)
        sources.append(source)
        models = set()
        for record in records:
            if record.get("type") != "assistant":
                continue
            model = _eligible_assistant_model(record)
            if model is None or not model.strip() or model.strip().startswith("<"):
                raise EvidenceUnknown(
                    "contains no real-shaped model entry; nested tool arguments cannot supply one "
                    f"(read {len(records)} record(s); 0 unparseable; "
                    f"{sum(r.get('type') == 'assistant' for r in records)} eligible)"
                )
            models.add(model.strip())
        if not models or (role == "reviewer" and len(models) != 1):
            raise EvidenceUnknown(
                "contains no real-shaped model entry or has ambiguous reviewer models "
                f"(read {len(records)} record(s); 0 unparseable; "
                f"{sum(r.get('type') == 'assistant' for r in records)} eligible)"
            )
        identities = [f"claude/{model}" for model in sorted(models)]
        evidence = {"session_id": value, "transcript": source["path"]}
    elif runtime == "qwen-code":
        root = args.qwen_projects_dir or Path.home() / ".qwen" / "projects"
        model, evidence, error = _derive_qwen_code(stream, root)
        if error:
            raise EvidenceUnknown(error)
        source, records, _ = _snapshot(root / evidence["transcript"], root)
        actual = {r.get("model") for r in records if r.get("type") == "assistant"}
        if actual != {model.removeprefix("qwen-code/")}:
            raise EvidenceUnknown("Qwen evidence changed during derivation")
        sources.append(source)
        identities = [model]
    else:
        data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = args.opencode_db or Path(data_home) / "opencode" / "opencode.db"
        model, evidence, error = _derive_opencode(stream, path)
        if error:
            raise EvidenceUnknown(error)
        # A SQLite database can have live WAL pages. Hash the actual selected
        # session rows, not the possibly stale main database file.
        import sqlite3

        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                rows = db.execute(
                    "select data from message where session_id = ? order by id", (evidence["session_id"],)
                ).fetchall()
        except sqlite3.Error as exc:
            raise EvidenceUnknown(f"cannot snapshot OpenCode session rows: {exc}") from exc
        actual = set()
        for (data,) in rows:
            message = json.loads(data)
            if message.get("role") == "assistant":
                actual.add(f"opencode/{message.get('providerID')}/{message.get('modelID')}")
        if actual != {model}:
            raise EvidenceUnknown("OpenCode evidence changed during derivation")
        raw = json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode()
        sources.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "format": "sqlite-session-rows",
            }
        )
        records = stream
        identities = [model]
    evidence.update({"kind": kind, "runtime": runtime, "models": identities, "sources": sources})
    if kind == "exec_log":
        evidence["exec_log"] = sources[0]["path"]
    return identities, evidence, records


def _model_key(identity: str) -> str:
    """Harness is not model identity. Do not invent model-name aliases."""
    return identity.split("/", 2)[-1] if identity.startswith("opencode/") else identity.split("/", 1)[-1]


def _review_inputs(records: list[dict], runtime: str) -> list[str]:
    inputs = []
    for r in records:
        if runtime == "codex":
            message = r.get("payload", {}) if r.get("type") == "response_item" else {}
        else:
            message = r.get("message", {}) if r.get("type") == "user" else {}
        if message.get("role") != "user":
            continue
        content = message.get("parts", []) if runtime == "qwen-code" else message.get("content", [])
        if isinstance(content, str):
            inputs.append(content)
        elif isinstance(content, list):
            inputs.extend(
                c["text"]
                for c in content
                if isinstance(c, dict) and (runtime == "qwen-code" or c.get("type") in ("input_text", "text"))
                and isinstance(c.get("text"), str)
            )
    return inputs


def _review_commands(records: list[dict], runtime: str) -> list[tuple[str, str]]:
    """Supported runtime command/results only, never assistant prose or user text."""
    commands = []
    calls = {}
    for r in records:
        if runtime == "codex":
            p = r.get("payload", {})
            if (
                r.get("type") == "response_item"
                and p.get("type") == "function_call"
                and p.get("name") in ("exec_command", "functions.exec_command", "shell_command")
            ):
                try:
                    arg = json.loads(p["arguments"])
                    calls[p["call_id"]] = arg.get("cmd", arg.get("command"))
                except (KeyError, ValueError, TypeError):
                    continue
            elif (
                r.get("type") == "response_item"
                and p.get("type") == "function_call_output"
                and p.get("call_id") in calls
            ):
                out = p.get("output")
                if isinstance(out, str):
                    try:
                        result = json.loads(out)
                    except ValueError:
                        result = None
                    if (
                        isinstance(result, dict)
                        and type(result.get("exit_code")) is int and result["exit_code"] == 0
                        and isinstance(result.get("output"), str)
                    ):
                        commands.append((calls[p["call_id"]], result["output"]))
            elif r.get("type") == "event_msg":
                item = p.get("item", {})
                argv = item.get("command")
                if (
                    item.get("type") == "CommandExecution"
                    and type(item.get("exit_code")) is int and item["exit_code"] == 0
                    and isinstance(argv, list)
                    and len(argv) == 3
                    and argv[:2] == ["/bin/bash", "-lc"]
                ):
                    commands.append((argv[2], item.get("aggregated_output", "")))
        elif runtime == "qwen-code":
            for part in r.get("message", {}).get("parts", []):
                call = part.get("functionCall", {})
                if r.get("type") == "assistant" and call.get("name") == "run_shell_command":
                    calls[call.get("id")] = call.get("args", {}).get("command")
                response = part.get("functionResponse", {})
                result = r.get("toolCallResult", {})
                if (r.get("type") == "tool_result" and response.get("id") in calls
                        and result.get("callId") == response.get("id") and result.get("status") == "success"):
                    output = response.get("response", {}).get("output", "")
                    matched = re.search(r"\nOutput: (.*?)\nError: \(none\)\nExit Code: 0\n", output, re.S)
                    if matched:
                        commands.append((calls[response["id"]], matched.group(1)))
        elif runtime == "claude":
            message = r.get("message", {})
            for part in message.get("content", []) if isinstance(message.get("content"), list) else []:
                if not isinstance(part, dict):
                    continue
                if (
                    r.get("type") == "assistant"
                    and part.get("type") == "tool_use"
                    and part.get("name") in ("Bash", "run_shell_command")
                ):
                    calls[part.get("id")] = part.get("input", {}).get("command")
                elif (
                    r.get("type") == "user"
                    and part.get("type") == "tool_result"
                    and part.get("tool_use_id") in calls
                    and not part.get("is_error")
                ):
                    content = part.get("content")
                    if isinstance(content, str):
                        commands.append((calls[part["tool_use_id"]], content))
        elif runtime == "opencode" and r.get("type") == "tool_use":
            p = r.get("part", {})
            state = p.get("state", {})
            if (
                p.get("tool") == "bash"
                and state.get("status") == "completed"
                and type(state.get("metadata", {}).get("exit")) is int
                and state["metadata"]["exit"] == 0
            ):
                commands.append((state.get("input", {}).get("command"), state.get("output", "")))
    return commands


def _review_report_index(records: list[dict], runtime: str) -> int:
    """Use the last actual report, so a supervising session may review many PRs."""
    reports = []
    for index, r in enumerate(records):
        if runtime == "codex":
            message = r.get("payload", {}) if r.get("type") == "response_item" else {}
            content = message.get("content", []) if message.get("role") == "assistant" else []
        elif runtime == "opencode":
            content = [r.get("part", {})] if r.get("type") == "text" else []
        else:
            message = r.get("message", {}) if r.get("type") == "assistant" else {}
            content = message.get("parts", []) if runtime == "qwen-code" else message.get("content", [])
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                if re.search(r"^## Findings\s*$", part["text"], re.M):
                    reports.append(index)
    if not reports:
        raise EvidenceUnknown("missing runtime review report: retain the reviewer's '## Findings' assistant output")
    return reports[-1]


def _git_artifact(base_ref: str, target_ref: str = "HEAD") -> tuple[dict, bytes]:
    def git(*argv: str) -> bytes:
        return subprocess.check_output(["git", *argv], stderr=subprocess.PIPE)

    target = git("rev-parse", "--verify", f"{target_ref}^{{commit}}").decode().strip()
    base = git("rev-parse", "--verify", f"{base_ref}^{{commit}}").decode().strip()
    merge_base = git("merge-base", base, target).decode().strip()
    # Fixed flags make the exact artifact independent of host git presentation
    # config (external diff, colour, prefixes, quotePath and rename detection).
    patch = git(
        "-c",
        "core.quotePath=true",
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--no-renames",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "--binary",
        merge_base,
        target,
        "--",
    )
    binding = {
        "target_head": target,
        "base_sha": base,
        "merge_base": merge_base,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
    }
    return binding, patch


def _artifact_binding(args: argparse.Namespace, evidence: dict, records: list[dict]) -> dict:
    binding, patch = _git_artifact(args.review_base, args.head or "HEAD")
    target = binding["target_head"]
    report_index = _review_report_index(records, evidence["runtime"])
    records = records[:report_index]
    binding["report_record"] = report_index + 1
    if args.scope == "full":
        heads = [
            output.strip()
            for command, output in _review_commands(records, evidence["runtime"])
            if command == "git rev-parse HEAD"
        ]
        if not heads:
            raise EvidenceUnknown(
                "missing reviewer runtime HEAD probe: before review execute exactly "
                "'git rev-parse HEAD' and retain its tool result"
            )
        if heads[-1] != target:
            raise EvidenceRefused("reviewer runtime HEAD probe names a different head")
        binding["method"] = "runtime-head"
    else:
        patches = []
        for text in _review_inputs(records, evidence["runtime"]):
            # Codex frames captured stdin this way; Claude/Qwen producers use
            # the explicit CPP frame when sending an exact patch as user input.
            for opening, closing in (("<stdin>\n", "</stdin>"), ("<cpp-review-patch>\n", "</cpp-review-patch>")):
                starts = list(re.finditer(r"(?m)^" + re.escape(opening), text))
                if not starts:
                    continue
                ends = list(re.finditer(r"(?m)^" + re.escape(closing) + r"(?=\n|\Z)", text))
                if len(starts) != 1 or len(ends) != 1 or ends[0].start() < starts[0].end():
                    raise EvidenceUnknown("ambiguous captured reviewer patch framing")
                # A patch of this very reader contains the literal strings
                # '</stdin>' and '</cpp-review-patch>'. Hunk lines have a diff
                # prefix; only standalone transport lines delimit the frame.
                captured = text[starts[0].end():ends[0].start()]
                patches.append(captured.encode("utf-8"))
        if not patches:
            raise EvidenceUnknown(
                "missing captured reviewer patch: pass the exact canonical diff on stdin or in a "
                "<cpp-review-patch> user-input frame; retain the reviewer's runtime transcript"
            )
        if patches[-1] != patch:
            raise EvidenceRefused(
                "captured reviewer patch differs from the target head's current merge-base diff; "
                "re-review the exact patch"
            )
        binding["method"] = "captured-patch"
    args.head = target
    return binding


def build(args: argparse.Namespace) -> dict:
    implementer_set = isinstance(args.implementer, list)
    receipt: dict = {
        "schema": (
            SCHEMA_IMPLEMENTER_SET
            if implementer_set
            else SCHEMA_FLOW_SCOPE
            if getattr(args, "implementer_flow_run", None)
            else SCHEMA
        ),
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
    }
    if implementer_set:
        receipt["implementers"] = args.implementer
    else:
        receipt["implementer"] = args.implementer
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
    # OPTIONAL for the same reason (issue #1450): a receipt written before the
    # network probe existed has none, and absent is not a claim of `blocked`.
    if getattr(args, "network", None) and args.status == "ran":
        receipt["network"] = args.network
    # OPTIONAL, like `network` (issue #1459): absent says nothing about whether
    # the repository's own config carried a credential the review could not withdraw.
    if getattr(args, "local_credentials", None) and args.status == "ran":
        receipt["local_credentials"] = args.local_credentials
    # Written ONLY for a delegated run (issue #1383): absent means the default
    # direction, which is what every earlier receipt already means by omission.
    if getattr(args, "direction", DIRECTION_DEFAULT) == DIRECTION_DELEGATED:
        receipt["direction"] = DIRECTION_DELEGATED
        receipt["implementer_evidence"] = args.implementer_evidence
    elif getattr(args, "implementer_evidence", None):
        # A Codex IMPLEMENTER on the default direction (issue #1453): the thread
        # and rollout its identity was read from, so a reader can re-derive it.
        receipt["implementer_evidence"] = args.implementer_evidence
    if args.status == "skipped":
        receipt["skip_reason"] = args.reason
    else:
        receipt["passes"] = args.passes
        if getattr(args, "extra_pass_reason", None):
            receipt["extra_passes_reason"] = args.extra_pass_reason.strip()
            if not implementer_set:
                receipt["schema"] = (
                    SCHEMA_FLOW_SCOPE if getattr(args, "implementer_flow_run", None) else SCHEMA_EXTRA_PASSES
                )
        receipt["counts"] = {k: getattr(args, k) for k in COUNTS}
        receipt["red_cases"] = {
            "proposed": args.red_cases_proposed,
            "already_covered": args.red_cases_already_covered,
        }
    if getattr(args, "adapter_records", False):
        receipt["schema"] = SCHEMA_ADAPTERS
        receipt.pop("direction", None)
        receipt["reviewed_artifact"] = args.reviewed_artifact
    return receipt


def _validate_adapters(receipt: dict, source: str, implementers: list[str], reviewer: object) -> list[str]:
    bad = []

    def require(ok: bool, message: str) -> None:
        if not ok:
            bad.append(f"{source}: {message}")

    require(receipt.get("status") == "ran", "schema 5 requires a review that ran")
    require(type(receipt.get("schema")) is int, "schema 5 version must be an integer")
    require("direction" not in receipt, "schema 5 selects evidence per role, not direction")
    reviewer_evidence = receipt.get("reviewer_evidence")
    for role, identities in (("implementer", implementers), ("reviewer", [reviewer])):
        evidence = receipt.get(f"{role}_evidence")
        if not isinstance(evidence, dict):
            require(False, f"missing {role}_evidence object")
            continue
        runtime = evidence.get("runtime")
        kind = evidence.get("kind")
        require(
            isinstance(runtime, str) and runtime in ("codex", "claude", "qwen-code", "opencode"),
            f"{role} has an unsupported evidence runtime",
        )
        require(
            isinstance(kind, str) and kind in ("thread_id", "rollout", "session_id", "exec_log"),
            f"{role} has an unsupported evidence kind",
        )
        require(
            (runtime == "codex" and kind in ("thread_id", "rollout", "exec_log"))
            or (runtime == "claude" and kind == "session_id")
            or (runtime in ("qwen-code", "opencode") and kind == "exec_log"),
            f"{role} evidence kind does not match runtime",
        )
        require(evidence.get("models") == identities, f"{role} evidence models disagree with receipt identities")
        require(
            all(isinstance(i, str) and i.startswith(f"{runtime}/") for i in identities),
            f"{role} identities disagree with evidence runtime",
        )
        require(all(isinstance(i, str) and bool(_model_key(i).strip())
                    and not _model_key(i).strip().startswith("<") for i in identities),
                f"{role} requires a real nonempty model identity")
        keys = ("thread_id", "rollout") if runtime == "codex" else ("session_id",)
        for key in keys:
            require(
                isinstance(evidence.get(key), str) and bool(evidence[key].strip()), f"{role} evidence missing {key}"
            )
        sources = evidence.get("sources")
        require(isinstance(sources, list) and bool(sources), f"{role} evidence requires consumed sources")
        if isinstance(sources, list):
            expected = 2 if kind == "exec_log" else 1
            require(len(sources) == expected, f"{role} evidence requires {expected} consumed source(s)")
            paths = [item.get("path") for item in sources if isinstance(item, dict)]
            pointer = "rollout" if runtime == "codex" else "database" if runtime == "opencode" else "transcript"
            require(isinstance(evidence.get(pointer), str) and evidence[pointer] in paths,
                    f"{role} {pointer} must identify a consumed source")
            if kind == "exec_log":
                require(isinstance(evidence.get("exec_log"), str) and evidence["exec_log"] in paths,
                        f"{role} exec_log must identify a consumed source")
            if "flow_scope" in evidence:
                require(role == "implementer" and runtime == "codex", "fresh-flow proof requires a Codex implementer")
        for item in sources if isinstance(sources, list) else []:
            if not isinstance(item, dict):
                require(False, f"{role} evidence source must be an object")
                continue
            path = item.get("path")
            require(
                isinstance(path, str) and bool(path) and not Path(path).is_absolute() and ".." not in Path(path).parts,
                f"{role} source path must be relative and bounded",
            )
            require(
                isinstance(item.get("sha256"), str) and bool(re.fullmatch(r"[0-9a-f]{64}", item["sha256"])),
                f"{role} source requires sha256",
            )
            require(
                type(item.get("bytes")) is int and item["bytes"] > 0, f"{role} source requires positive byte length"
            )
    if isinstance(reviewer, str):
        require(
            all(_model_key(reviewer) != _model_key(i) for i in implementers),
            "reviewer overlaps an implementing model independently of runtime",
        )
    artifact = receipt.get("reviewed_artifact")
    if not isinstance(artifact, dict):
        require(False, "missing reviewed_artifact binding")
    else:
        require(type(artifact.get("report_record")) is int and artifact["report_record"] > 0,
                "reviewed_artifact requires runtime report_record")
        for key in ("target_head", "base_sha", "merge_base"):
            require(
                isinstance(artifact.get(key), str) and bool(re.fullmatch(r"[0-9a-f]{40}", artifact[key])),
                f"reviewed_artifact requires full {key}",
            )
        require(artifact.get("target_head") == receipt.get("head"), "reviewed artifact names a different head")
        require(
            isinstance(artifact.get("patch_sha256"), str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", artifact["patch_sha256"])),
            "reviewed_artifact requires patch_sha256",
        )
        method = "runtime-head" if receipt.get("scope") == "full" else "captured-patch"
        require(artifact.get("method") == method, "reviewed artifact method disagrees with review scope")
    require(receipt.get("scope") in SCOPES, "schema 5 requires a supported review scope")
    for key, values in (("network", NETWORKS), ("local_credentials", LOCAL_CREDENTIALS)):
        require(isinstance(receipt.get(key), str) and receipt[key] in values, f"schema 5 requires supported {key}")
    if isinstance(reviewer_evidence, dict) and not (
        reviewer_evidence.get("runtime") == "codex" and reviewer_evidence.get("kind") == "exec_log"
    ):
        require(receipt.get("network") == "unverified", "this reviewer adapter has no network probe")
        require(receipt.get("local_credentials") == "unknown", "this reviewer adapter has no credential probe")
    return bad


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

    if not isinstance(receipt, dict):
        return [f"{source}: receipt must be an object"]
    adapters = receipt.get("schema") == SCHEMA_ADAPTERS
    has_extra_reason = "extra_passes_reason" in receipt
    has_flow_scope = (
        isinstance(receipt.get("implementer_evidence"), dict) and "flow_scope" in receipt["implementer_evidence"]
    )
    has_implementer_set = "implementers" in receipt
    expected_schema = (
        SCHEMA_ADAPTERS
        if adapters
        else SCHEMA_IMPLEMENTER_SET
        if has_implementer_set
        else SCHEMA_FLOW_SCOPE
        if has_flow_scope
        else SCHEMA_EXTRA_PASSES
        if has_extra_reason
        else SCHEMA
    )
    if receipt.get("schema") != expected_schema:
        why = (
            "this receipt carries an 'implementers' set, which requires schema 4"
            if has_implementer_set else
            "this receipt carries 'extra_passes_reason', which schema 1 does not "
            "describe; re-write this receipt with the current counter-model-receipt.py "
            "to pick up schema 2"
            if has_extra_reason else
            "this receipt has no 'extra_passes_reason', so it should declare schema 1"
        )
        bad.append(
            f"{source}: schema is {receipt.get('schema')!r}, expected {expected_schema}: {why}"
        )
    if has_flow_scope:
        bad.extend(f"{source}: {problem}" for problem in _flow_proof_problems(
            receipt["implementer_evidence"]["flow_scope"], receipt))
    if receipt.get("schema") == SCHEMA_IMPLEMENTER_SET and not has_implementer_set:
        bad.append(f"{source}: schema 4 is missing its 'implementers' list")
    need("recorded_at", str)
    need("branch", str)
    if not isinstance(receipt.get("issue"), (int, str)):
        bad.append(f"{source}: missing or non-scalar 'issue'")

    status = receipt.get("status")
    if status not in STATUSES:
        bad.append(f"{source}: status {status!r} not in {STATUSES}")
        return bad

    implementer: object | None = None
    implementers: list[str] = []
    if has_implementer_set:
        if "implementer" in receipt:
            bad.append(
                f"{source}: schema 4 must not carry singular 'implementer' beside "
                "the 'implementers' set"
            )
        raw_implementers = receipt["implementers"]
        if not isinstance(raw_implementers, list):
            bad.append(
                f"{source}: 'implementers' is {type(raw_implementers).__name__}, expected list"
            )
        elif not raw_implementers:
            bad.append(f"{source}: 'implementers' must be a nonempty list")
        else:
            for index, value in enumerate(raw_implementers):
                if not isinstance(value, str):
                    bad.append(
                        f"{source}: implementers[{index}] is {type(value).__name__}; "
                        "all implementer identities must be strings"
                    )
                elif not value.strip():
                    bad.append(
                        f"{source}: implementers[{index}] is empty; a run must name every model"
                    )
                else:
                    implementers.append(value.strip())
            if len(implementers) != len(set(implementers)):
                bad.append(f"{source}: 'implementers' must contain unique model identities")
    else:
        implementer = need("implementer", str)
        if isinstance(implementer, str) and implementer.strip():
            implementers = [implementer.strip()]
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
        if isinstance(value, str) and not value.strip():
            bad.append(f"{source}: {name} is empty; a run must name the model")
    if isinstance(reviewer, str) and reviewer.strip() and implementers:
        # THE PROPERTY, CHECKED. A run whose reviewer IS the implementer is not
        # a counter-model review at all - it is the author agreeing with
        # themselves, recorded as independent evidence. Worse than no receipt,
        # because it is counted.
        if reviewer.strip() in implementers:
            if has_implementer_set:
                bad.append(
                    f"{source}: reviewer overlaps the implementer set "
                    f"({reviewer.strip()!r}); the reviewing model must differ from "
                    "every implementing model"
                )
            else:
                bad.append(
                    f"{source}: reviewer and implementer are the same model "
                    f"({reviewer!r}); the reviewing model must not be the implementing model"
                )

    head = receipt.get("head")
    if head is not None:
        if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{7,40}", head):
            bad.append(f"{source}: head {head!r} is not a git object name")

    if adapters:
        bad.extend(_validate_adapters(receipt, source, implementers, reviewer))
    if not adapters:
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
            elif delegated:
                # The CLI guard refuses `--scope` on the delegated lane (the
                # reviewer there is a Claude session, which has no sandbox probe
                # to measure) - the schema must refuse it too, or a hand-built
                # or historical receipt could carry it unchecked (counter-model
                # review, codex gpt-6.1-sol).
                bad.append(
                    f"{source}: a delegated receipt must not carry 'scope'; its "
                    "reviewer is a Claude session, which has no sandbox probe"
                )
            elif scope not in SCOPES:
                bad.append(f"{source}: scope {scope!r} not in {SCOPES}")

        if (status == "ran" and not delegated and "scope" not in receipt
                and isinstance(receipt.get("recorded_at"), str)
                and receipt["recorded_at"] >= SCOPE_REQUIRED_FROM):
            bad.append(
                f"{source}: a default-direction ran receipt recorded at or after "
                f"{SCOPE_REQUIRED_FROM} must carry 'scope' (issue #1461); a receipt "
                "without it says nothing about what the reviewer could see"
            )

        if "network" in receipt:
            network = receipt["network"]
            if status == "skipped":
                bad.append(
                    f"{source}: a skipped run must not carry 'network'; no review happened"
                )
            elif delegated:
                bad.append(
                    f"{source}: a delegated receipt must not carry 'network'; its "
                    "reviewer is a Claude session, which has no sandbox probe"
                )
            elif network not in NETWORKS:
                bad.append(f"{source}: network {network!r} not in {NETWORKS}")

        if "local_credentials" in receipt:
            local = receipt["local_credentials"]
            if status == "skipped":
                bad.append(
                    f"{source}: a skipped run must not carry 'local_credentials'; no review happened"
                )
            elif delegated:
                bad.append(
                    f"{source}: a delegated receipt must not carry 'local_credentials'; its "
                    "reviewer is a Claude session, which /codex:code_review did not launch"
                )
            elif local not in LOCAL_CREDENTIALS:
                bad.append(f"{source}: local_credentials {local!r} not in {LOCAL_CREDENTIALS}")

        if has_implementer_set:
            # Schema 4 is the Codex-rollout representation. This check is
            # independent of direction: on a delegated lane Codex is the
            # implementer, but a hand-built Qwen/OpenCode set must not acquire a
            # representation their writers cannot derive.
            if not implementers or any(not item.startswith("codex/") for item in implementers):
                bad.append(
                    f"{source}: schema 4 is recorded only for codex/ implementers "
                    "derived from one complete retained rollout"
                )
            if not _names(receipt.get("implementer_evidence"), ("thread_id", "rollout")):
                bad.append(
                    f"{source}: schema 4 requires implementer_evidence naming the Codex "
                    "thread and rollout from which the implementer set was derived"
                )

        if delegated:
            # A delegated receipt exists BECAUSE a review happened: the supervising
            # Claude session is always present on that lane, so neither committed
            # skip reason (an inability to run the reviewer) can be true of it.
            if status != "ran":
                bad.append(
                    f"{source}: a delegated receipt records a review that happened; "
                    f"status {status!r} is not 'ran'"
                )
            evidence = receipt.get("implementer_evidence")
            harness = evidence.get("harness") if isinstance(evidence, dict) else None
            if harness is not None and not isinstance(harness, str):
                # Checked BEFORE the membership test (counter-model review): an
                # unhashable value would raise instead of being reported.
                bad.append(f"{source}: implementer_evidence harness {harness!r} is not a string")
            elif harness not in DELEGATED_EVIDENCE_KEYS:
                bad.append(f"{source}: implementer_evidence harness {harness!r} is not one this "
                           f"writer derives ({', '.join(k for k in DELEGATED_EVIDENCE_KEYS if k)} or Codex)")
            elif not _names(evidence, DELEGATED_EVIDENCE_KEYS[harness]):
                bad.append(
                    f"{source}: a delegated receipt must carry implementer_evidence naming a "
                    "non-empty " + " and ".join(repr(k) for k in DELEGATED_EVIDENCE_KEYS[harness])
                )
            elif harness and not implementers:
                bad.append(f"{source}: no usable implementer identity matches evidence harness {harness!r}")
            elif harness and any(not item.startswith(f"{harness}/") for item in implementers):
                bad.append(f"{source}: implementers {implementers!r} do not all match their "
                           f"evidence's harness {harness!r}")
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
            # On the default direction it is recorded ONLY for a Codex implementer
            # (issue #1453), whose identity was read from its own thread's rollout.
            # A Claude implementer is derived from its transcript and carries none.
            if not implementers or any(not item.startswith("codex/") for item in implementers):
                bad.append(
                    f"{source}: 'implementer_evidence' on the default direction is "
                    "recorded only for a codex/ implementer (issue #1453); a Claude "
                    "implementer is derived from its session transcript"
                )
            elif not _names(receipt.get("implementer_evidence"), ("thread_id", "rollout")):
                bad.append(
                    f"{source}: a codex implementer's implementer_evidence must name a "
                    "non-empty 'thread_id' and 'rollout'"
                )
    if status == "skipped":
        if receipt.get("skip_reason") not in SKIP_REASONS:
            bad.append(
                f"{source}: skip_reason {receipt.get('skip_reason')!r} not in {SKIP_REASONS}"
            )
        for absent in ("counts", "red_cases", "passes", "extra_passes_reason"):
            if absent in receipt:
                bad.append(f"{source}: a skipped run must not carry {absent!r}")
        return bad

    passes = receipt.get("passes")
    reason = receipt.get("extra_passes_reason")
    if not isinstance(passes, int) or isinstance(passes, bool) or passes < 1:
        bad.append(f"{source}: passes is {passes!r}, expected a positive integer")
    elif passes > PASSES_HARD_CEILING:
        bad.append(
            f"{source}: passes is {passes}, beyond the hard ceiling of {PASSES_HARD_CEILING}; "
            "#1320's pass 3 is the only extra-pass precedent in this repository's "
            "review history; escalate the review loop rather than record another pass"
        )
    elif passes > 2 and not (isinstance(reason, str) and reason.strip()):
        # Two passes is the documented cap: each one spends the user's quota,
        # and an unbounded loop is how a review stage becomes a cost centre.
        # A pass beyond it is recordable only with the reason it was asked for
        # (issue #1400): refusing it made the receipt under-report a review
        # that happened and found something (#1320's pass 3).
        bad.append(
            f"{source}: passes is {passes}, beyond the cap of 2, and carries no "
            "'extra_passes_reason' saying why the extra pass was requested"
        )
    elif passes <= 2 and "extra_passes_reason" in receipt:
        bad.append(
            f"{source}: 'extra_passes_reason' is only for passes beyond the cap of 2 "
            f"(passes is {passes})"
        )

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


#: The delegated harnesses whose streams this writer can attribute (issue #1454),
#: with the evidence keys a receipt must carry for each. Codex records carry no
#: `harness` key - every delegated receipt before #1454 is Codex.
DELEGATED_EVIDENCE_KEYS = {
    None: ("thread_id", "rollout"),
    "qwen-code": ("harness_version", "session_id", "transcript"),
    "opencode": ("harness_version", "session_id", "database"),
}


def _stream_records(text: str) -> tuple[list[dict], int]:
    """`(event records, DAMAGED event line count)` of a JSONL stream (#1454).

    The lanes write the harness's stderr into the same file (`2>&1`), so a line
    that does not open like an event is a diagnostic and is skipped - stderr often
    starts with `[` (`[WARN] ...`), so only `{` opens one. A line that DOES open
    like an event but does not parse to an object is DAMAGED: it might have named another session or harness, so the
    caller refuses rather than attributing from the records that survived.
    """
    records: list[dict] = []
    damaged = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("{"):
            continue
        try:
            record = json.loads(stripped)
        except ValueError:
            damaged += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            damaged += 1
    return records, damaged


def _strict_records(text: str) -> tuple[list[dict] | None, str | None]:
    """Every non-blank line a JSON object, or a refusal (counter-model review).

    For a PERSISTED record (Qwen Code's transcript), not a stream: no stderr is
    written into it, so there is nothing to skip, and a damaged line - whatever
    it starts with - could have been an assistant record naming another model.
    """
    records: list[dict] = []
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            return None, f"line {number} is not JSON"
        if not isinstance(record, dict):
            return None, f"line {number} is not a JSON object"
        records.append(record)
    return records, None


#: Session identifiers as each harness writes them (measured): Qwen Code a UUID,
#: OpenCode `ses_` plus an alphanumeric id. Checked BEFORE any lookup, so an id
#: is never used as a pattern (counter-model review).
QWEN_SESSION_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
OPENCODE_SESSION_RE = re.compile(r"ses_[A-Za-z0-9]+")


def _stream_harness(records: list[dict]) -> tuple[str | None, str | None]:
    """Which harness wrote this stream, read from the stream's OWN shape (#1454).

    Codex: a `thread.started` record with a thread id. Qwen Code: a
    `system`/`init` record carrying `qwen_code_version`. OpenCode: step/text/tool
    events carrying a `sessionID`. Exactly one shape must match - a stream that
    looks like none, or like two, is refused rather than guessed at.
    """
    found = set()
    for r in records:
        if r.get("type") == "thread.started" and r.get("thread_id"):
            found.add("codex")
        elif r.get("type") == "system" and r.get("subtype") == "init" and "qwen_code_version" in r:
            found.add("qwen-code")
        elif r.get("sessionID") and r.get("type") in ("step_start", "text", "tool_use", "step_finish"):
            found.add("opencode")
    if len(found) == 1:
        return next(iter(found)), None
    if not found:
        return None, ("names no harness this writer recognises (no Codex thread_id, no "
                      "Qwen Code init, no OpenCode sessionID)")
    return None, f"carries the shapes of more than one harness ({', '.join(sorted(found))})"


def _derive_qwen_code(records: list[dict], projects_dir: Path) -> tuple[str | None, dict | None, str | None]:
    """`qwen-code/<model>` from a Qwen Code stream-json run and its own transcript.

    Measured on qwen 0.15.10 (fixtures under tests/fixtures/delegated-streams):
    the stream's `system/init.model` and each assistant record's `model` in the
    persisted transcript `<projects>/<cwd-slug>/chats/<session_id>.jsonl` name
    the REQUESTED model - the same basis as Codex `turn_context`. Both must be
    present, agree with each other, and agree across every assistant record.
    """
    inits = [r for r in records if r.get("type") == "system" and r.get("subtype") == "init"]
    raw_sessions = [r.get("session_id") for r in records if "session_id" in r]
    if any(not (isinstance(s, str) and QWEN_SESSION_RE.fullmatch(s)) for s in raw_sessions):
        return None, None, "a Qwen Code record carries a session_id that is not the measured UUID form"
    sessions = set(raw_sessions)
    if len(inits) != 1:
        return None, None, f"expected one Qwen Code init record, found {len(inits)}"
    if len(sessions) != 1:
        return None, None, f"expected one Qwen Code session_id, found {len(sessions)}"
    init = inits[0]
    session_id = next(iter(sessions))
    stream_model = init.get("model")
    version = init.get("qwen_code_version")
    if not (isinstance(stream_model, str) and stream_model.strip()):
        return None, None, "the Qwen Code init record declares no model"
    if not (isinstance(version, str) and version.strip()):
        return None, None, "the Qwen Code init record declares no qwen_code_version"
    try:
        # LITERAL lookup, never a glob of the id (counter-model review).
        matches = sorted(
            d / "chats" / f"{session_id}.jsonl" for d in projects_dir.iterdir()
            if (d / "chats" / f"{session_id}.jsonl").is_file()
        )
    except OSError as exc:
        return None, None, f"cannot search Qwen Code projects directory {projects_dir}: {exc}"
    if len(matches) != 1:
        return None, None, (f"expected one Qwen Code transcript for session {session_id!r} under "
                            f"{projects_dir}, found {len(matches)}")
    try:
        strict, reason = _strict_records(matches[0].read_text(encoding="utf-8"))
    except OSError as exc:
        return None, None, f"cannot read Qwen Code transcript {matches[0]}: {exc}"
    if strict is None:
        return None, None, f"Qwen Code transcript {matches[0]}: {reason}; refusing to attribute"
    transcript = strict
    assistants = [r for r in transcript if r.get("type") == "assistant"]
    if not assistants:
        return None, None, f"Qwen Code transcript {matches[0]} holds no assistant record"
    raw_models = [r.get("model") for r in assistants]
    if any(not (isinstance(m, str) and m.strip()) for m in raw_models):
        return None, None, f"an assistant record in {matches[0]} declares no model"
    models = set(raw_models)
    if len(models) != 1:
        return None, None, f"assistant records in {matches[0]} disagree ({', '.join(sorted(models))})"
    model = next(iter(models))
    if model != stream_model:
        return None, None, (f"the stream's init model {stream_model!r} disagrees with the "
                            f"transcript's {model!r}")
    evidence = {"harness": "qwen-code", "harness_version": version, "session_id": session_id,
                "transcript": matches[0].relative_to(projects_dir).as_posix()}
    return f"qwen-code/{model}", evidence, None


def _derive_opencode(records: list[dict], db_path: Path) -> tuple[str | None, dict | None, str | None]:
    """`opencode/<provider>/<model>` from an OpenCode run and its own database.

    Measured on opencode 1.18.32: the `--format json` stream carries NO model,
    only a `sessionID`; the model is on that session's assistant rows in the
    SQLite `message` table (`providerID`, `modelID`). The database is opened
    READ-ONLY, and a schema that is not the one measured is refused: a drifted
    schema must read as refused, never as a different model.
    """
    import sqlite3

    raw_sessions = [r.get("sessionID") for r in records if "sessionID" in r]
    if any(not (isinstance(s, str) and OPENCODE_SESSION_RE.fullmatch(s)) for s in raw_sessions):
        return None, None, "an OpenCode record carries a sessionID that is not the measured ses_ form"
    sessions = set(raw_sessions)
    if len(sessions) != 1:
        return None, None, f"expected one OpenCode sessionID in the stream, found {len(sessions)}"
    session_id = next(iter(sessions))
    if not db_path.is_file():
        return None, None, f"no OpenCode database at {db_path}"
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            columns = {table: {row[1] for row in db.execute(f"pragma table_info('{table}')")}
                       for table in ("message", "session")}
            if not {"session_id", "data"} <= columns["message"] or not {"id", "version"} <= columns["session"]:
                return None, None, (f"OpenCode database {db_path} does not have the measured schema "
                                    "(message.session_id/data, session.id/version); refusing rather "
                                    "than guessing")
            rows = db.execute("select data from message where session_id = ?", (session_id,)).fetchall()
            version_row = db.execute("select version from session where id = ?", (session_id,)).fetchone()
        finally:
            db.close()
    except sqlite3.Error as exc:
        return None, None, f"cannot read OpenCode database {db_path}: {exc}"
    if not (version_row and isinstance(version_row[0], str) and version_row[0].strip()):
        return None, None, f"OpenCode session {session_id!r} has no version in {db_path}"
    pairs = set()
    for (data,) in rows:
        try:
            message = json.loads(data)
        except (TypeError, ValueError):
            return None, None, f"an OpenCode message row for {session_id!r} is not JSON"
        if isinstance(message, dict) and message.get("role") == "assistant":
            provider, model_id = message.get("providerID"), message.get("modelID")
            if not (isinstance(provider, str) and provider and isinstance(model_id, str) and model_id):
                return None, None, (f"an assistant message in session {session_id!r} declares no "
                                    "provider or model")
            pairs.add((provider, model_id))
    if not pairs:
        return None, None, f"OpenCode session {session_id!r} has no assistant message in {db_path}"
    if any(not (isinstance(a, str) and a and isinstance(b, str) and b) for a, b in pairs):
        return None, None, f"an assistant message in session {session_id!r} declares no provider or model"
    if len(pairs) != 1:
        return None, None, (f"assistant messages in session {session_id!r} disagree "
                            f"({', '.join(sorted('/'.join(pair) for pair in pairs))})")
    provider, model = next(iter(pairs))
    evidence = {"harness": "opencode", "harness_version": version_row[0], "session_id": session_id,
                "database": db_path.name}
    return f"opencode/{provider}/{model}", evidence, None


def _implementer_source(args: argparse.Namespace) -> tuple[str, str, str | None]:
    """Which session implemented: `("claude", session_id)` or `("codex", thread_id)`.

    An explicit flag decides. Without one, the environment does - and the
    environment is often AMBIGUOUS in this fleet (issue #1453, measured): a codex
    process launched from a Claude session inherits `CLAUDE_CODE_SESSION_ID`
    and also gets its own `CODEX_THREAD_ID`. Picking either silently would
    attribute the work to a session that may not have written it, so both set
    is refused, and the refusal names the exact flag for each side. Neither set
    is refused too: an identity is derived, never assumed.
    """
    if args.implementer_session_id:
        return "claude", args.implementer_session_id, None
    if args.implementer_thread_id:
        return "codex", args.implementer_thread_id, None
    claude_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    codex_id = os.environ.get("CODEX_THREAD_ID", "").strip()
    if claude_id and codex_id:
        return "", "", (
            "ambiguous implementer: both CLAUDE_CODE_SESSION_ID and CODEX_THREAD_ID "
            "are set (a codex process launched from a Claude session sees both). "
            "Name the session that wrote the change: "
            '--implementer-thread-id "$CODEX_THREAD_ID" if Codex implemented, or '
            '--implementer-session-id "$CLAUDE_CODE_SESSION_ID" if Claude did'
        )
    if claude_id:
        return "claude", claude_id, None
    if codex_id:
        return "codex", codex_id, None
    return "", "", (
        "missing implementer identity; supply --implementer-session-id (a Claude "
        "session) or --implementer-thread-id (a Codex session), or run where "
        "CLAUDE_CODE_SESSION_ID or CODEX_THREAD_ID is set"
    )


def cmd_write(args: argparse.Namespace) -> int:
    adapters = args.status == "ran"
    if adapters:
        try:
            implementing, args.implementer_evidence, _ = _adapter(args, "implementer")
            reviewing, args.reviewer_evidence, review_records = _adapter(args, "reviewer")
            if len(reviewing) != 1:
                raise EvidenceUnknown("reviewer evidence must resolve exactly one model")
            if not args.scope and args.reviewer_exec_log and args.reviewer_evidence["runtime"] == "codex":
                print("counter-model-receipt: --status ran requires --scope with a Codex exec reviewer",
                      file=sys.stderr)
                return EXIT_USAGE
            args.scope = args.scope or "unverified"
            args.implementer = implementing[0] if len(implementing) == 1 else implementing
            args.reviewer = reviewing[0]
            if any(_model_key(args.reviewer) == _model_key(i) for i in implementing):
                raise EvidenceRefused(f"reviewer overlaps the implementer set ({args.reviewer!r}; {implementing!r}); "
                                      "the reviewing model must differ from every implementing model")
            args.adapter_records = True
            args.network = args.network or "unverified"
            args.local_credentials = args.local_credentials or "unknown"
        except (EvidenceUnknown, OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError) as exc:
            _evidence_error(exc)
            return EXIT_INVALID
    if adapters and args.reviewer_exec_log and args.reviewer_evidence["runtime"] == "codex":
        # Re-measure the caller's pre-run scope CLAIM against the same exec
        # log the reviewer identity was just derived from (issue #1400): a
        # probe that passed before the review started is not trusted alone
        # for the review's whole duration.
        if getattr(args, "scope", None) == "full":
            exec_text = args.reviewer_exec_log.read_text(encoding="utf-8")
            failures, examined = _mid_run_sandbox_failures(exec_text)
            denials = _mid_run_read_denials(exec_text)
            if failures:
                print(
                    f"counter-model-receipt: NOTE - downgrading scope 'full' to "
                    f"'diff-only': {failures} of {examined} command_execution "
                    f"item(s) in {args.reviewer_exec_log} could not launch the "
                    "sandboxed exec process (exit_code -1), the same failure "
                    "mode the pre-run probe checks for, so the claimed scope "
                    "did not hold for the review's whole duration",
                    file=sys.stderr,
                )
                args.scope = "diff-only"
            elif denials:
                print(
                    f"counter-model-receipt: NOTE - downgrading scope 'full' to "
                    f"'unverified': {denials} command(s) in {args.reviewer_exec_log} "
                    "printed a read-denial marker ('Permission denied' / 'Operation "
                    "not permitted'), so read access could not be verified for the "
                    "whole review (issue #1461). The marker may be a refused read or "
                    "file CONTENT that contains the phrase; this cannot tell them "
                    "apart, and downgrades either way",
                    file=sys.stderr,
                )
                args.scope = "unverified"
            elif examined == 0:
                # A re-measurement with nothing to examine is not a
                # confirmation: "0 failed of 0 examined" and "0 failed of 10
                # examined" are different claims, and only the second one
                # actually re-measured anything (counter-model review, codex
                # gpt-6.1-sol).
                print(
                    f"counter-model-receipt: NOTE - downgrading scope 'full' to "
                    f"'unverified': {args.reviewer_exec_log} carries no "
                    "command_execution item at all, so there is no mid-run "
                    "evidence to re-measure the pre-run probe's claim against",
                    file=sys.stderr,
                )
                args.scope = "unverified"
    elif not adapters:
        args.reviewer = None
        args.reviewer_evidence = None

    if not adapters:
        side, ident, error = _implementer_source(args)
        if error is not None:
            print(f"counter-model-receipt: {error}", file=sys.stderr)
            return EXIT_INVALID
        if side == "codex":
            sessions_dir = args.codex_sessions_dir or _default_codex_sessions_dir()
            implementer, evidence, error = _derive_codex_from_thread(
                ident, sessions_dir, role="implementer",
                flow_args=args if getattr(args, "implementer_flow_run", None) else None,
                implementer_set=not getattr(args, "implementer_flow_run", None),
            )
            if error is not None:
                print(f"counter-model-receipt: implementer thread: {error}", file=sys.stderr)
                return EXIT_INVALID
            args.implementer_evidence = evidence
        else:
            projects_dir = args.claude_projects_dir or _default_claude_projects_dir()
            implementer, error = _derive_implementer_from_session(ident, projects_dir)
            if error is not None:
                print(f"counter-model-receipt: {error}", file=sys.stderr)
                return EXIT_INVALID
        args.implementer = implementer

    if adapters:
        try:
            args.reviewed_artifact = _artifact_binding(args, args.reviewer_evidence, review_records)
        except (EvidenceUnknown, OSError, UnicodeError, ValueError, TypeError, KeyError,
                AttributeError, subprocess.SubprocessError) as exc:
            _evidence_error(exc)
            return EXIT_INVALID
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


def cmd_audit_flow(args: argparse.Namespace) -> int:
    """Re-derive the captured source prefix; hashes do not authenticate its author."""
    try:
        receipt = json.loads(args.receipt.read_bytes())
        _flow_need(isinstance(receipt, dict), "receipt is not an object")
        problems = validate(receipt, str(args.receipt))
        _flow_need(not problems, "; ".join(problems))
        evidence = receipt.get("implementer_evidence", {})
        proof = evidence.get("flow_scope")
        _flow_need(isinstance(proof, dict), "receipt has no fresh-flow evidence")
        sessions = (args.codex_sessions_dir or _default_codex_sessions_dir()).resolve()
        relative = Path(evidence["rollout"])
        _flow_need(not relative.is_absolute() and ".." not in relative.parts, "unsafe rollout identity")
        source = (sessions / relative).resolve()
        _flow_need(source.is_relative_to(sessions), "rollout escapes sessions root")
        raw = source.read_bytes()
        size = proof["rollout_bytes"]
        _flow_need(len(raw) >= size and hashlib.sha256(raw[:size]).hexdigest() == proof["rollout_sha256"],
                   "captured rollout prefix changed or was truncated")
        scope_args = argparse.Namespace(issue=receipt["issue"], branch=receipt["branch"],
                                        head=receipt["head"], implementer_flow_run=proof["run_id"])
        snapshot = raw[:size].decode("utf-8")
        creation = json.loads(snapshot.splitlines()[proof["creation_line"] - 1])
        historical_path = _flow_fields(creation["payload"]["item"]["aggregated_output"])["WT_PATH"]
        _flow_need(historical_path.startswith("/"), "historical worktree path is not absolute")
        model, derived = _flow_scope_model(snapshot, evidence["thread_id"], scope_args, audit=True,
                                           historical_root=_flow_path(historical_path, audit=True))
        _flow_need(derived == proof and receipt["implementer"] == f"codex/{model}",
                   "re-derived flow evidence disagrees with receipt")
    except (FlowScopeRefused, OSError, UnicodeError, ValueError, KeyError, IndexError, TypeError,
            subprocess.SubprocessError) as exc:
        print(f"COUNTER_MODEL_FLOW_AUDIT: refused ({exc})", file=sys.stderr)
        return EXIT_INVALID
    print("COUNTER_MODEL_FLOW_AUDIT: verified captured prefix")
    return EXIT_OK


def cmd_review_patch(args: argparse.Namespace) -> int:
    """Produce exactly the artifact the writer independently recomputes."""
    try:
        dirty = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.PIPE)
        if dirty:
            raise EvidenceRefused("commit the issue's implementation checkpoint "
                                  "before producing a receipt-bound review patch")
        _, patch = _git_artifact(args.base, args.head or "HEAD")
    except (EvidenceUnknown, EvidenceRefused, OSError, subprocess.SubprocessError) as exc:
        _evidence_error(exc)
        return EXIT_INVALID
    sys.stdout.buffer.write(patch)
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
        help="runtime exec stream from which to resolve the reviewing model and its persisted evidence",
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
        "--network",
        choices=NETWORKS,
        help="/codex:code_review's pre-run CODEX_REVIEW_NETWORK verdict (issue "
             "#1450), recorded as measured; 'open' and 'unverified' are never "
             "a network-fenced review",
    )
    w.add_argument(
        "--local-credentials",
        choices=LOCAL_CREDENTIALS,
        help="/codex:code_review's CODEX_REVIEW_LOCAL_CREDENTIALS verdict (issue "
             "#1459): a credential in the repository's own config that the "
             "review could not withdraw, recorded as measured",
    )
    w.add_argument(
        "--implementer-thread-id",
        help="a CODEX session's thread id (issue #1453) from which to derive the "
             "IMPLEMENTING model through its own rollout - inside a Codex session "
             "pass \"$CODEX_THREAD_ID\". Exclusive with --implementer-session-id",
    )
    w.add_argument("--implementer-flow-run", help="derive a Codex implementer from a verified fresh flow run identity")
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
        help="runtime exec stream resolving the implementing model through persisted evidence",
    )
    w.add_argument(
        "--qwen-projects-dir",
        type=Path,
        help="Qwen Code adapter: where its transcripts live "
             "(default ~/.qwen/projects)",
    )
    w.add_argument(
        "--opencode-db",
        type=Path,
        help="OpenCode adapter: its SQLite database, opened "
             "read-only (default $XDG_DATA_HOME/opencode/opencode.db)",
    )
    w.add_argument(
        "--reviewer-session-id",
        help="Claude session that reviewed the diff; derive its model from the runtime transcript "
             "(defaults to $CLAUDE_CODE_SESSION_ID when --implementer-exec-log is given)",
    )
    w.add_argument("--reviewer-thread-id", help="derive reviewer from its own Codex rollout")
    w.add_argument("--reviewer-rollout", type=Path, help="explicit reviewer Codex rollout file")
    w.add_argument("--implementer-rollout", type=Path, help="explicit implementer Codex rollout file")
    w.add_argument("--review-base", default="origin/main",
                   help="base ref for exact reviewed-artifact diff; resolved at write time")
    w.add_argument("--passes", type=int, default=1,
                   help="review passes run; beyond 2 requires --extra-pass-reason")
    w.add_argument(
        "--extra-pass-reason",
        help="why a pass beyond the cap of 2 was requested, and by whom (issue "
             "#1400); required when --passes > 2, refused otherwise",
    )
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

    patch = sub.add_parser("review-patch", help="emit the exact committed review artifact on stdout")
    patch.add_argument("--base", default="origin/main")
    patch.add_argument("--head")
    patch.set_defaults(func=cmd_review_patch)

    pr = sub.add_parser("parse", help="read a reviewer transcript and report its verdict")
    pr.add_argument("transcript", help="path to the reviewer's output")
    pr.set_defaults(func=cmd_parse)

    v = sub.add_parser("validate", help="check the shape of every committed receipt")
    v.add_argument("--dir", default=str(RECEIPT_DIR))
    v.set_defaults(func=cmd_validate)

    audit = sub.add_parser("audit-flow", help="re-derive a scoped receipt from its recorded original rollout prefix")
    audit.add_argument("receipt", type=Path)
    audit.add_argument("--codex-sessions-dir", type=Path)
    audit.set_defaults(func=cmd_audit_flow)

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
    if args.cmd == "write" and getattr(args, "implementer_flow_run", None):
        if args.status != "ran" or not args.implementer_thread_id or args.implementer_exec_log:
            ap.error("--implementer-flow-run requires a ran default-direction Codex --implementer-thread-id")
    if args.cmd == "write":
        args.direction = DIRECTION_DEFAULT
        for role in ("implementer", "reviewer"):
            supplied = [getattr(args, f"{role}_{kind}", None)
                        for kind in ("thread_id", "rollout", "session_id", "exec_log")]
            if sum(bool(value) for value in supplied) > 1:
                ap.error(f"{role} evidence selectors cannot be combined; name exactly one source")
        if args.implementer_exec_log and not any((args.reviewer_session_id, args.reviewer_thread_id,
                                                args.reviewer_rollout, args.reviewer_exec_log)):
            args.reviewer_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
        if args.status == "ran" and not any((args.reviewer_session_id, args.reviewer_thread_id,
                                            args.reviewer_rollout, args.reviewer_exec_log)):
            ap.error("--status ran requires reviewer evidence: --reviewer-exec-log, "
                     "--reviewer-thread-id, --reviewer-rollout or --reviewer-session-id")
    if args.cmd == "write" and args.implementer_session_id and args.implementer_thread_id:
        ap.error("--implementer-session-id (Claude) and --implementer-thread-id (Codex) "
                 "name two different implementers; pass the one that wrote the change")
    if args.cmd == "write" and args.status == "skipped":
        if any((args.implementer_exec_log, args.reviewer_session_id, args.reviewer_thread_id, args.reviewer_rollout)):
            ap.error("reviewer/exec evidence requires --status ran; no review happened on a skip")
    if args.cmd == "write" and args.status == "skipped" and not args.reason:
        ap.error("--status skipped requires --reason")
    if (args.cmd == "write" and args.status == "skipped"
            and args.reviewer_exec_log is not None):
        ap.error("--status skipped must not carry --reviewer-exec-log; no review happened")
    if args.cmd == "write" and args.status == "ran":
        if args.passes > PASSES_HARD_CEILING:
            ap.error(f"--passes beyond the hard ceiling of {PASSES_HARD_CEILING} has no "
                     "precedent in this repository's review history (#1320 is the only "
                     "ever-requested extra pass, and it was pass 3); something is wrong "
                     "with the review loop itself - escalate rather than record another pass")
        if args.passes > 2 and not (args.extra_pass_reason or "").strip():
            ap.error("--passes beyond 2 requires --extra-pass-reason: the cap exists "
                     "because each pass spends quota, so an extra one says why")
        if args.passes <= 2 and args.extra_pass_reason is not None:
            ap.error("--extra-pass-reason is only for --passes beyond 2")
    if args.cmd == "write" and args.status == "skipped" and args.extra_pass_reason is not None:
        ap.error("--status skipped must not carry --extra-pass-reason; no review happened")
    if args.cmd == "write" and args.status == "skipped" and args.scope:
        ap.error("--status skipped must not carry --scope; no review happened")
    if args.cmd == "write" and args.status == "skipped" and args.local_credentials:
        ap.error("--status skipped must not carry --local-credentials; no review happened")
    if args.cmd == "write" and args.status == "skipped" and args.network:
        ap.error("--status skipped must not carry --network; no review happened")

    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
