#!/usr/bin/env python3
"""Attribute a landed counter-model receipt to the rollout that produced it (issue #1048).

WHY THIS EXISTS
---------------
`docs/measurements/counter-model/` holds 13 receipts recording the identical
reviewer `codex/gpt-5.5`, copied out of a worked example in
`.claude/commands/flow/auto.md` rather than observed (#1045 removed the literal,
#1059 made the writer derive instead of accept). The forward half is fixed. What
remained was the disposition of the 13, and it was blocked on a premise recorded
in `docs/scripts.md`: that "real receipts carry no field connecting them back to
the exec log or thread_id that produced them, so retroactively verifying
anything already on disk is structurally impossible".

That premise is false, and this instrument is the demonstration. A receipt
records `branch`. A Codex rollout records its own `cwd` - the per-issue worktree
directory, which is named for that branch - and a start timestamp. That is an
association, and it is the one real receipts actually carry.

WHAT THIS IS NOT
----------------
It is not the thread-anchored derivation the WRITER performs (#1059). That one
reads a thread_id out of an exec log and is an identity. This is an INFERENCE
from a directory name and a time window, and its error rate is measured rather
than assumed - see `docs/measurements/counter-model-reviewer-attribution.md`,
which reports 15 of 16 agreement and 0 disagreements against the post-#1059
receipts whose reviewers were derived and are therefore ground truth.

It also does not write to `docs/measurements/counter-model/`. The receipts are
read-only here. What each run BELIEVED is itself evidence about how the defect
propagated, and this instrument's job is to say what was true, not to rewrite
what was recorded.

THE EXTRACTOR IS CONTROLLED BEFORE ITS OUTPUT IS BELIEVED
---------------------------------------------------------
The defect under investigation is a field that reports one value no matter what
happened. An instrument that reads a constant would produce exactly the same
"disagreement" output as one that reads correctly, so agreement and disagreement
are BOTH meaningless until the extractor is shown to discriminate. This reports
`extractor_distinct=<k>`, the number of distinct model values it read across the
rollouts it scanned, and REFUSES to report a finding when k <= 1: with one value
everywhere, a disagreement cannot be told from an echo. That refusal is the
whole reason this can be trusted where the thing it is auditing could not.

AMBIGUITY IS NOT A TIE TO BREAK. A receipt whose linked rollouts disagree with
each other is `ambiguous` and is verified neither way. Picking the nearest, the
first or the newest would manufacture a specific answer out of an unresolved
one, which is the failure this whole issue is about.

Usage:
    counter-model-reviewer-attribution.py [--receipts-dir DIR] [--rollouts-dir DIR]
    counter-model-reviewer-attribution.py --selftest
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

#: NEGATIVE-CONTROL: controls/counter-model-reviewer-attribution
#:
#: ADR 0008: this instrument's verdict is read by the OPERATOR deciding the
#: disposition of the 13 landed receipts (#1048 items 1-2), and nothing
#: downstream re-derives it. The committed cases distinguish a real
#: disagreement from a blind extractor, an unlinked corpus from a clean one,
#: and an ambiguous link from a verified one. The anchor mistakes the presence
#: of receipts for their attribution.

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls" / "counter-model-reviewer-attribution"

#: How far BEFORE a receipt's `recorded_at` a rollout may have started and still
#: be a candidate, and how far after. A review runs shortly before its receipt is
#: written; the grace absorbs clock skew between the two writers.
#: The repository name the committed fixtures' synthetic worktrees use.
CONTROL_REPO = "repo"

#: Every distinction this instrument exists to draw must stay registered. Named,
#: not counted, so a swap is caught as well as a deletion.
REQUIRED_CASES = frozenset(
    {
        "bad-ambiguous",
        "bad-blind-extractor",
        "bad-disagreement",
        "bad-foreign-repo",
        "bad-nothing-linked",
        "bad-unreadable-candidate",
        "good-agreement",
    }
)

DEFAULT_WINDOW = timedelta(hours=6)
DEFAULT_GRACE = timedelta(minutes=10)

#: The worktree a rollout ran in must belong to THIS repository, not merely end
#: with the same branch name. `Path(cwd).name.endswith(branch)` also matches
#: `another-repo-issue-9001-alpha`, and the default sessions directory spans
#: every repository on the host - so a neighbour's rollout could supply a
#: confident attribution, or manufacture a disagreement, for a receipt it has
#: nothing to do with (counter-model review, #1048). This is the detector
#: contract's second question - can a finding tell our thing from a neighbour's
#: - and the answer was no. The basename must now equal `<repo>-<branch>`
#: exactly.
#:
#: The repository name is DERIVED from the receipts' own checkout via git's
#: COMMON dir, never from the checkout's basename: this instrument runs inside
#: a flow worktree called `claude-power-pack-issue-1048-...`, whose basename is
#: not the repository's name. When it cannot be derived and none is supplied,
#: the scan REFUSES rather than falling back to suffix matching, which would
#: reopen the hole on exactly the path reached when something is already wrong.

#: The model field, read the SAME way `counter-model-receipt.py`'s
#: `_derive_reviewer_from_exec_log` reads it from a rollout - first match wins.
#: Kept as its own pattern rather than imported because that function's input is
#: an exec log and its contract is a thread_id lookup; if either side changes how
#: a rollout names its model, BOTH must change, and this comment is the link.
MODEL_RE = re.compile(r'"model"\s*:\s*"([^"]*)"')


def _rollout_meta(path: Path) -> tuple[str, str] | None:
    """(cwd, started_at) from a rollout's first line, or None if it has no header."""
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
    except OSError:
        return None
    try:
        record = json.loads(first)
    except ValueError:
        return None
    if not isinstance(record, dict) or record.get("type") != "session_meta":
        return None
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    cwd = payload.get("cwd")
    started = payload.get("timestamp") or record.get("timestamp")
    if not isinstance(cwd, str) or not isinstance(started, str):
        return None
    return cwd, started


def _rollout_model(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = MODEL_RE.search(text)
    if match is None or not match.group(1).strip():
        return None
    return match.group(1).strip()


def _parse_time(value: object) -> datetime | None:
    # A NON-STRING IS NOT A TIME. `42.replace` raises AttributeError, which
    # neither branch below catches, so one malformed `recorded_at` aborted the
    # scan of every OTHER receipt - a whole corpus unexamined because one file
    # was wrong (counter-model review, #1048). It is now a per-receipt
    # diagnostic, reached through the same "no usable branch or recorded_at"
    # path as a missing value.
    if not isinstance(value, str):
        return None
    for parse in (
        lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")),
        lambda v: datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc),
    ):
        try:
            parsed = parse(value)
        except (ValueError, TypeError):
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def load_rollouts(rollouts_dir: Path) -> list[dict]:
    """Every rollout with a readable header, with its model already extracted."""
    found: list[dict] = []
    for path in sorted(rollouts_dir.rglob("*.jsonl")):
        if not path.is_file():
            continue
        meta = _rollout_meta(path)
        if meta is None:
            continue
        cwd, started = meta
        when = _parse_time(started)
        if when is None:
            continue
        found.append({"path": path, "cwd": cwd, "started": when, "model": _rollout_model(path)})
    return found


def scan(
    receipts_dir: Path,
    rollouts_dir: Path,
    repo_name: str,
    window: timedelta = DEFAULT_WINDOW,
    grace: timedelta = DEFAULT_GRACE,
) -> tuple[int, str]:
    """Return the verdict and its report. Never modifies either input."""
    rollouts = load_rollouts(rollouts_dir)
    # THE EXTRACTOR'S OWN DISCRIMINATION, measured before any verdict uses it.
    extractor_distinct = len({r["model"] for r in rollouts if r["model"] is not None})

    examined = linked = agreed = ambiguous = unlinked = 0
    disagreements: list[tuple[str, object, str]] = []
    notes: list[str] = []

    for path in sorted(receipts_dir.rglob("*.json")):
        if not path.is_file():
            continue
        name = path.relative_to(receipts_dir).as_posix()
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            notes.append(f"ATTRIBUTION-NOTE: {name}: receipt excluded: {exc}")
            continue
        if not isinstance(receipt, dict) or receipt.get("status") != "ran":
            continue
        examined += 1

        branch = receipt.get("branch")
        recorded_at = _parse_time(receipt.get("recorded_at") or "")
        if not isinstance(branch, str) or not branch.strip() or recorded_at is None:
            unlinked += 1
            notes.append(
                f"ATTRIBUTION-NOTE: {name}: no usable branch or recorded_at; cannot be linked"
            )
            continue

        expected = f"{repo_name}-{branch.strip()}"
        candidates = [
            r
            for r in rollouts
            if Path(r["cwd"]).name == expected
            and (recorded_at - window) <= r["started"] <= (recorded_at + grace)
        ]
        if not candidates:
            unlinked += 1
            continue
        # AN UNREADABLE CANDIDATE IS UNRESOLVED EVIDENCE, NOT AN ABSENT ONE
        # (counter-model review, #1048). Dropping it left the remaining
        # candidates looking unanimous, so a receipt whose real reviewer might
        # be the unreadable rollout was reported as a confident agreement - or
        # as a confident disagreement. Same rule as two candidates that
        # contradict each other: the evidence does not determine an answer.
        unreadable = [r for r in candidates if r["model"] is None]
        models = {r["model"] for r in candidates if r["model"] is not None}
        if unreadable:
            ambiguous += 1
            notes.append(
                f"ATTRIBUTION-NOTE: {name}: {len(unreadable)} of {len(candidates)} linked "
                "rollout(s) declare no model; the unreadable one could be the reviewer, "
                "so this receipt is verified neither way"
            )
            continue
        if not models:
            unlinked += 1
            continue
        if len(models) > 1:
            # NOT a tie to break. Two models in one worktree window means the
            # association does not determine an answer, and inventing one here
            # is the exact defect this instrument audits.
            ambiguous += 1
            notes.append(
                f"ATTRIBUTION-NOTE: {name}: {len(candidates)} linked rollout(s) disagree "
                f"({', '.join(sorted(models))}); verified neither way"
            )
            continue

        linked += 1
        derived = f"codex/{models.pop()}"
        if derived == receipt.get("reviewer"):
            agreed += 1
        else:
            disagreements.append((name, receipt.get("reviewer"), derived))

    denominator = (
        f"examined={examined} linked={linked} agreed={agreed} "
        f"disagreed={len(disagreements)} ambiguous={ambiguous} unlinked={unlinked} "
        f"extractor_distinct={extractor_distinct} repo={repo_name}"
    )

    if examined == 0:
        code = EXIT_UNKNOWN
        lines = [
            f"ATTRIBUTION-UNKNOWN: {denominator} - nothing was examined "
            "(empty or misconfigured receipts-dir)"
        ]
    elif extractor_distinct <= 1:
        # THE BLINDNESS REFUSAL. With one model value across every rollout read,
        # a correct extractor and one echoing a constant produce identical
        # output, so neither agreement nor disagreement is evidence yet.
        code = EXIT_UNKNOWN
        lines = [
            f"ATTRIBUTION-UNKNOWN: {denominator} - the model extractor read "
            f"{extractor_distinct} distinct value(s) across {len(rollouts)} rollout(s); "
            "a constant cannot be told from a correct reading, so no attribution is reported"
        ]
    elif disagreements:
        code = EXIT_FINDING
        lines = [
            f"ATTRIBUTION-FINDING: {name}: stored reviewer={stored!r}, "
            f"linked rollout derived={derived!r}"
            for name, stored, derived in disagreements
        ]
        lines.append(f"ATTRIBUTION-SUMMARY: {denominator}")
    elif linked == 0:
        code = EXIT_UNKNOWN
        lines = [
            f"ATTRIBUTION-UNKNOWN: {denominator} - 0 of {examined} receipt(s) yielded an "
            "unambiguous link; an unattributed corpus is unknown, never clean"
        ]
    else:
        code = EXIT_OK
        lines = [
            f"ATTRIBUTION-OK: {denominator} - every one of {linked} linked receipt(s) "
            "agrees with its rollout"
        ]
    return code, "\n".join([*lines, *notes])


def _derive_repo_name(receipts_dir: Path) -> str | None:
    """The repository the receipts belong to, from git's COMMON dir.

    NOT the checkout's basename: this runs inside a flow worktree named
    `<repo>-issue-<n>-<slug>`, and using that basename would make the expected
    worktree name `<repo>-issue-1048-...-<branch>`, matching nothing. The common
    dir is the PRIMARY checkout's `.git`, whose parent is the repository.
    """
    start = receipts_dir if receipts_dir.is_dir() else receipts_dir.parent
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    common = Path(out.stdout.strip())
    if not common.is_absolute():
        common = (start / common).resolve()
    name = common.parent.name
    return name or None


def selftest() -> int:
    """Exercise exactly the registered cases, including their denominators."""
    try:
        cases = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))["cases"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"ATTRIBUTION-SELFTEST: FAIL: cannot load committed cases: {exc}")
        return EXIT_FINDING
    # AN EMPTY REGISTRATION MUST NOT PASS (counter-model review, #1048).
    # `cases: []` printed "0/0 cases matched" and exited 0, so deleting the
    # population left the self-test green while it exercised no distinction at
    # all - a blind instrument reporting on itself. The required names are
    # asserted, not merely counted, so swapping a case for a different one is
    # caught as well as removing it.
    present = {case.get("name") for case in cases}
    missing = sorted(REQUIRED_CASES - present)
    if missing:
        print(
            "ATTRIBUTION-SELFTEST: FAIL: the registration is missing required case(s): "
            + ", ".join(missing)
        )
        return EXIT_FINDING
    failures = 0
    with tempfile.TemporaryDirectory(prefix="counter-model-attribution-") as temporary:
        for case in cases:
            try:
                fixture = shutil.copytree(CONTROL / case["input"], Path(temporary) / case["name"])
                code, output = scan(fixture / "receipts", fixture / "rollouts", CONTROL_REPO)
                matched = code == case["expected_exit"] and output == case["expected_output"]
            except (OSError, ValueError, KeyError) as exc:
                matched, code, output = False, EXIT_FINDING, str(exc)
            if not matched:
                failures += 1
            print(f"ATTRIBUTION-SELFTEST: {case['name']}: {'PASS' if matched else 'FAIL'}")
            if not matched:
                print(f"  observed exit={code}: {output}")
    print(f"ATTRIBUTION-SELFTEST: {len(cases) - failures}/{len(cases)} cases matched")
    return EXIT_FINDING if failures else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--receipts-dir", type=Path, default=Path("docs/measurements/counter-model")
    )
    parser.add_argument(
        "--rollouts-dir",
        type=Path,
        default=Path.home() / ".codex" / "sessions",
        help="Codex sessions root to link against (read-only)",
    )
    parser.add_argument(
        "--repo-name",
        help="repository whose worktrees may be linked; derived from the receipts' "
        "checkout when omitted. Without one the scan REFUSES rather than matching "
        "on a branch suffix alone",
    )
    parser.add_argument("--window-hours", type=float, default=6.0)
    parser.add_argument("--grace-minutes", type=float, default=10.0)
    parser.add_argument(
        "--selftest", action="store_true", help="run the committed cases; ignore input flags"
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    repo_name = args.repo_name or _derive_repo_name(args.receipts_dir)
    if not repo_name:
        print(
            "ATTRIBUTION-UNKNOWN: examined=0 linked=0 agreed=0 disagreed=0 ambiguous=0 "
            "unlinked=0 extractor_distinct=0 repo=<underivable> - could not establish "
            "which repository these receipts belong to, and a branch name alone does not "
            "distinguish this repository's worktree from a neighbour's; pass --repo-name"
        )
        return EXIT_UNKNOWN
    code, output = scan(
        args.receipts_dir,
        args.rollouts_dir,
        repo_name,
        timedelta(hours=args.window_hours),
        timedelta(minutes=args.grace_minutes),
    )
    print(output)
    return code


if __name__ == "__main__":
    sys.exit(main())
