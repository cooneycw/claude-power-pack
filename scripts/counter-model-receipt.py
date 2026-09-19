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
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
RECEIPT_DIR = Path("docs/measurements/counter-model")

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2

STATUSES = ("ran", "skipped")

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
    if findings:
        return PARSE_FINDINGS, findings
    if NONE_RE.search(masked_section):
        return PARSE_CLEAN, []
    return PARSE_UNPARSEABLE, []


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-")[:60] or "unknown"


def _derive_reviewer_from_exec_log(
    exec_log: Path, sessions_dir: Path
) -> tuple[str | None, str | None]:
    """Derive the reviewing model from one exec stream and its own rollout."""
    try:
        exec_text = exec_log.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read reviewer exec log {exec_log}: {exc}"

    thread_match = re.search(r'"thread_id"\s*:\s*"([^"]*)"', exec_text)
    if thread_match is None or not thread_match.group(1):
        return None, f"reviewer exec log {exec_log} contains no thread_id"
    thread_id = thread_match.group(1)

    try:
        matches = sorted(
            path
            for path in sessions_dir.rglob("*.jsonl")
            if path.is_file() and path.name.endswith(f"{thread_id}.jsonl")
        )
    except OSError as exc:
        return None, f"cannot search Codex sessions directory {sessions_dir}: {exc}"
    if not matches:
        return None, (
            f"no rollout matching thread_id {thread_id!r} under Codex sessions "
            f"directory {sessions_dir}"
        )

    rollout = matches[0]
    try:
        rollout_text = rollout.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read matching rollout {rollout}: {exc}"
    model_match = re.search(r'"model"\s*:\s*"([^"]*)"', rollout_text)
    if model_match is None or not model_match.group(1):
        return None, f"matching rollout {rollout} contains no model field"
    return f"codex/{model_match.group(1)}", None


def _default_codex_sessions_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "sessions"
    return Path.home() / ".codex" / "sessions"


def _derive_implementer_from_session(
    session_id: str, projects_dir: Path
) -> tuple[str | None, str | None]:
    """Derive the latest real model from the implementing Claude session."""
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
    model = None
    for match in re.finditer(r'"model"\s*:\s*"([^"]*)"', transcript_text):
        value = match.group(1).strip()
        # Sessions can switch models; sentinels after a real turn do not erase it.
        if value and not value.startswith("<"):
            model = value
    if model is None:
        return None, f"matching transcript {transcript} contains no real-shaped model entry"
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


def cmd_write(args: argparse.Namespace) -> int:
    if args.status == "ran":
        sessions_dir = args.codex_sessions_dir or _default_codex_sessions_dir()
        reviewer, error = _derive_reviewer_from_exec_log(
            args.reviewer_exec_log, sessions_dir
        )
        if error is not None:
            print(f"counter-model-receipt: {error}", file=sys.stderr)
            return EXIT_INVALID
        args.reviewer = reviewer
    else:
        args.reviewer = None

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

    receipt = build(args)
    problems = validate(receipt, "new receipt")
    if problems:
        for p in problems:
            print(f"counter-model-receipt: {p}", file=sys.stderr)
        return EXIT_INVALID

    out_dir = Path(args.dir)
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
    return EXIT_INVALID if verdict == PARSE_UNPARSEABLE else EXIT_OK


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
        "--implementer-session-id",
        help="Claude session from which to derive the IMPLEMENTING model "
             "(defaults to $CLAUDE_CODE_SESSION_ID)",
    )
    w.add_argument(
        "--claude-projects-dir",
        type=Path,
        help="Claude projects root (defaults to ~/.claude/projects)",
    )
    w.add_argument("--passes", type=int, default=1)
    for k in COUNTS:
        w.add_argument(f"--{k}", type=int, default=0)
    w.add_argument("--red-cases-proposed", type=int, default=0)
    w.add_argument("--red-cases-already-covered", type=int, default=0)
    w.add_argument("--at", help="override the timestamp (tests)")
    w.set_defaults(func=cmd_write)

    pr = sub.add_parser("parse", help="read a reviewer transcript and report its verdict")
    pr.add_argument("transcript", help="path to the reviewer's output")
    pr.set_defaults(func=cmd_parse)

    v = sub.add_parser("validate", help="check the shape of every committed receipt")
    v.add_argument("--dir", default=str(RECEIPT_DIR))
    v.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    if args.cmd == "write" and args.status == "skipped" and not args.reason:
        ap.error("--status skipped requires --reason")
    if (args.cmd == "write" and args.status == "skipped"
            and args.reviewer_exec_log is not None):
        ap.error("--status skipped must not carry --reviewer-exec-log; no review happened")
    if (args.cmd == "write" and args.status == "ran"
            and args.reviewer_exec_log is None):
        ap.error("--status ran requires --reviewer-exec-log")
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
