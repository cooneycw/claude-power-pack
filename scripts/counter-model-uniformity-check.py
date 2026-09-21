#!/usr/bin/env python3
"""Distinguish copied reviewer literals from verified uniformity (issue #1091).

Uniformity is an observation, not a defect. One model may really have reviewed
every change in a period. A diverse corpus raises no uniformity concern; a
uniform one needs independent evidence before this instrument calls it clean.
A disagreement with evidence is stronger than either observation and always
reports a finding, even in a diverse corpus.

PRINT THE DENOMINATOR ON EVERY RUN, INCLUDING THE CLEAN ONE. Examined receipts,
successful cross-verifications and distinct stored values are different counts.
Zero examined receipts is UNKNOWN, as is uniformity with zero verifications.
One confirmed receipt does not certify all the others: the denominator states
exactly how much was checked.

THE EVIDENCE LINK IS SUPPLIED, NEVER GUESSED. Existing receipts have no exec-log
or thread identifier. For X.json, an optional X.evidence.json manifest supplies
{"exec_log": "path", "sessions_dir": "path"}. Relative paths resolve against
the manifest's own directory; absolute paths are also accepted. There is no
implicit sessions directory and no lookup in the user's Codex home. The receipt
writer's existing derivation function is imported, so the two cannot silently
disagree about how a reviewer is derived. This checks supplied evidence, not
the authenticity of its association with a receipt.

Missing manifests are normal. Malformed or unusable evidence is diagnosed and
does not count as verifiable. Unparseable receipts are diagnosed and excluded;
only JSON objects with status "ran" enter the denominator. This is a uniformity
check, not another receipt-schema validator. Receipt discovery is recursive;
evidence manifests are matched by receipt stem in the evidence directory.

--selftest copies the five committed control cases into temporary directories
and checks their exact exit codes and output. It needs neither network access
nor real exec logs. Pytest uses the same committed cases, copied under tmp_path.

Usage:
    counter-model-uniformity-check.py [--receipts-dir DIR] [--evidence-dir DIR]
    counter-model-uniformity-check.py --selftest
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

#: NEGATIVE-CONTROL: controls/counter-model-uniformity
#:     ADR 0008: an operator may use this verdict to decide the disposition of
#:     landed receipts. Nothing downstream re-derives that reading. The cases
#:     distinguish diversity, copied uniformity, verified uniformity, missing
#:     evidence and an empty population; the anchor mistakes presence for proof.

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls" / "counter-model-uniformity"


def _load_receipt_module():
    spec = importlib.util.spec_from_file_location(
        "counter_model_receipt", ROOT / "scripts" / "counter-model-receipt.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RECEIPT = _load_receipt_module()


def derive_evidence(manifest: Path) -> tuple[str | None, str | None]:
    """Absent evidence is normal; supplied but unusable evidence gets a reason."""
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as exc:
        return None, f"cannot read evidence: {exc}"
    if not isinstance(payload, dict) or any(
        not isinstance(payload.get(key), str) or not payload[key].strip()
        for key in ("exec_log", "sessions_dir")
    ):
        return None, "evidence needs non-empty exec_log and sessions_dir string paths"
    try:
        return RECEIPT._derive_reviewer_from_exec_log(
            manifest.parent / payload["exec_log"],
            manifest.parent / payload["sessions_dir"],
        )
    except (OSError, ValueError) as exc:
        # The shared helper handles missing files; invalid encodings/paths may
        # still raise. They are unusable evidence, not a reviewer disagreement.
        return None, f"cannot derive reviewer: {exc}"


#: How a landed commit names the issue it closes. CPP squash-merges, so every
#: first-parent commit on the default branch IS one pull request, and its subject
#: carries the reference. Deliberately NOT just `#N`: the trailing `(#N)` GitHub
#: appends is the PR number, not the issue, and counting it as an issue would
#: invent enrolments nobody owed.
ISSUE_REF_RE = re.compile(r"\b(?:Closes|Fixes|Resolves|Refs)\s+#(\d+)", re.IGNORECASE)


#: Weakest evidence first. A commit is classified by the WORST status among the
#: issues it names, so a skip cannot be hidden behind a sibling issue that was
#: reviewed.
_RANK = {"invalid": 0, "unverifiable": 1, "skipped": 2, "ran": 3}


def enrolment_scan(repo: Path, receipts_dir: Path, ref: str, limit: int) -> tuple[int, str]:
    """Which landed changes owed a counter-model review and did not record one.

    THIS IS THE HALF THAT MAKES ABSENCE A FINDING (issue #1171). `scan()` above
    reads the receipts that EXIST, so a review that never happened simply shrinks
    its population and reports nothing - which is why #1152 and #1163 merged green
    with no receipt and were each later found to carry a HIGH. Here the population
    comes from the HISTORY instead: every first-parent commit is a merged PR, and
    one naming an issue with no receipt is a review that is missing, not a
    corpus that is smaller.

    UNATTRIBUTABLE IS NOT MISSING. A commit whose subject names no issue cannot be
    said to owe anything, so it is counted and reported separately rather than
    folded into the findings. Collapsing the two would inflate every number here
    with commits that were never in the population.

    THE THREE VERDICTS, WITH THE INPUT THAT PRODUCES EACH. "It can also report OK"
    is the half of a discrimination claim a reader cannot re-derive without being
    told where to look, so the windows are NAMED here rather than described. Fixed
    SHAs, never HEAD~N: a relative ref slides as the branch moves and stops
    reproducing the moment someone merges.

        FINDING  --enrolment-scan origin/main --enrolment-limit 23
                 -> reviewed=7 skipped=0 missing=16, exit 1
        OK       --enrolment-scan ff4936eef78a39126ddb5d9b1b4411be91f9e951 --enrolment-limit 8
                 -> reviewed=8 skipped=0 missing=0, exit 0
        UNKNOWN  --enrolment-scan no-such-ref
                 -> ENROLMENT-UNKNOWN naming the git failure, exit 2

    The FINDING window is the measurement that motivated #1171 and is expected to
    drift as receipts land; the OK window is historical and is expected to keep
    reproducing exactly.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--first-parent", f"-{limit}",
             "--format=%H%x09%s", ref],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return EXIT_UNKNOWN, f"ENROLMENT-UNKNOWN: could not read history: {exc}"
    if out.returncode != 0:
        return EXIT_UNKNOWN, (
            f"ENROLMENT-UNKNOWN: git log failed for ref {ref!r}: {out.stderr.strip()}"
        )

    # STATUS IS CARRIED, NOT DISCARDED (counter-model review, MEDIUM). Keying only
    # on "a receipt mentions this issue" counted an explicit `skipped:
    # codex-absent` as a completed review and then said "recorded a review" - which
    # recreates, in the instrument built to remove it, the exact skipped-versus-
    # reviewed ambiguity #1171 is about. An allowed skip may satisfy enrolment, but
    # the report has to NAME it as a skip.
    # A SKIP IS ONLY A SKIP IF ITS REASON IS IN THE COMMITTED SET (counter-model
    # review pass 2, MEDIUM). The scan accepted every `"status": "skipped"` receipt
    # as satisfying enrolment without looking at `skip_reason`, so `explicit-opt-out`
    # - the reason removed deliberately - and a receipt with no reason at all both
    # produced ENROLMENT-OK while the finish gate reds on exactly those states. A
    # historical report that certifies what the gate refuses is worse than no
    # report. Read from the same declaration the gate reads, never a second copy.
    allowed = tuple(getattr(RECEIPT, "SKIP_REASONS", ()))

    have: dict[str, set[str]] = {}
    for path in receipts_dir.rglob("*.json"):
        if not path.is_file():
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(receipt, dict) or receipt.get("issue") is None:
            continue
        status = receipt.get("status")
        if status == "ran":
            cls = "ran"
        elif status == "skipped":
            if not allowed:
                cls = "unverifiable"
            elif receipt.get("skip_reason") in allowed:
                cls = "skipped"
            else:
                cls = "invalid"
        else:
            cls = "invalid"
        have.setdefault(str(receipt["issue"]), set()).add(cls)

    missing: list[str] = []
    invalid: list[str] = []
    mixed: list[str] = []
    reviewed = skipped = unattributable = 0
    seen_issue_commits: dict[str, int] = {}
    for line in out.stdout.splitlines():
        sha, _, subject = line.partition("\t")
        issues = set(ISSUE_REF_RE.findall(subject))
        if not issues:
            unattributable += 1
            continue
        for i in issues:
            seen_issue_commits[i] = seen_issue_commits.get(i, 0) + 1
        absent = sorted(i for i in issues if i not in have)
        if absent:
            missing.append(f"{sha[:8]} {subject[:72]} -> no receipt for #{', #'.join(absent)}")
            continue
        # CLASSIFY BY THE WEAKEST EVIDENCE, NOT THE STRONGEST (counter-model review
        # pass 2, MEDIUM). Unioning every issue's statuses and preferring `ran` meant
        # a commit naming a reviewed #11 and a skipped #12 reported `reviewed=1
        # skipped=0` - the skip vanished, which is this issue's own ambiguity yet
        # again. A change is only as reviewed as its least-reviewed issue, and a
        # commit whose issues disagree is NAMED rather than rounded either way.
        per_issue = {i: min(have[i], key=_RANK.get) for i in issues}
        worst = min(per_issue.values(), key=_RANK.get)
        if len(set(per_issue.values())) > 1:
            mixed.append(
                f"{sha[:8]} {subject[:72]} -> issues disagree: "
                + ", ".join(f"#{i}={c}" for i, c in sorted(per_issue.items()))
            )
        if worst == "invalid":
            invalid.append(
                f"{sha[:8]} {subject[:72]} -> a receipt exists but records nothing usable "
                "(status is not 'ran', or a skip names a reason outside the committed set)"
            )
        elif worst == "unverifiable":
            invalid.append(
                f"{sha[:8]} {subject[:72]} -> a skip could not be checked against the "
                "committed reasons, so it is not evidence of anything"
            )
        elif worst == "ran":
            reviewed += 1
        else:
            skipped += 1

    # PER-ISSUE, AND IT SAYS SO (counter-model review, MEDIUM). One receipt covers
    # every commit naming its issue, so two changes closing #11 both read as
    # covered while only one was reviewed. Correlating a receipt with an individual
    # merged change is not possible from this data - a receipt records an issue and
    # a branch, not a squash sha - so the honest move is to report the keying and
    # name the multiply-counted issues rather than let "covered" be read as a
    # per-change claim it cannot support.
    shared = sorted(i for i, n in seen_issue_commits.items() if n > 1)
    attributable = reviewed + skipped + len(missing) + len(invalid)
    denominator = (
        f"commits={len(out.stdout.splitlines())} attributable={attributable} "
        f"reviewed={reviewed} skipped={skipped} missing={len(missing)} "
        f"invalid={len(invalid)} unattributable={unattributable}"
    )
    shared_note = (
        f"ENROLMENT-NOTE: coverage is keyed per ISSUE, not per change; "
        f"issue(s) #{', #'.join(shared)} are named by more than one commit here, so one "
        "receipt satisfies several - per-change coverage is UNKNOWN for those"
        if shared else
        "ENROLMENT-NOTE: coverage is keyed per ISSUE, not per change; no issue in this "
        "range is named by more than one commit"
    )
    if attributable == 0:
        return EXIT_UNKNOWN, (
            f"ENROLMENT-UNKNOWN: {denominator} - no commit in this range names an issue, "
            "so nothing could be attributed; this is an unrun check, not a clean one"
        )
    mixed_lines = [f"ENROLMENT-NOTE: {m}" for m in mixed]
    if missing or invalid:
        lines = [f"ENROLMENT-FINDING: {m}" for m in (*missing, *invalid)]
        lines.append(f"ENROLMENT-SUMMARY: {denominator}")
        lines.append(shared_note)
        lines.extend(mixed_lines)
        return EXIT_FINDING, "\n".join(lines)
    return EXIT_OK, "\n".join([
        f"ENROLMENT-OK: {denominator} - every attributable change has a receipt for its "
        f"issue ({reviewed} reviewed, {skipped} explicitly skipped)",
        shared_note,
        *mixed_lines,
    ])


def scan(receipts_dir: Path, evidence_dir: Path | None = None) -> tuple[int, str]:
    """Return the verdict and its report without modifying any input."""
    examined = verifiable = 0
    reviewers: set[str] = set()
    mismatches: list[tuple[str, object, str]] = []
    notes: list[str] = []
    for path in sorted(receipts_dir.rglob("*.json")):
        if not path.is_file():
            continue
        name = path.relative_to(receipts_dir).as_posix()
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            notes.append(f"UNIFORMITY-NOTE: {name}: receipt excluded: {exc}")
            continue
        if not isinstance(receipt, dict) or receipt.get("status") != "ran":
            continue
        examined += 1
        stored = receipt.get("reviewer")
        # Preserve JSON types and tolerate malformed reviewer fields without
        # adding schema-validation rules or crashing on unhashable values.
        reviewers.add(json.dumps(stored, sort_keys=True))
        if evidence_dir is None:
            continue
        derived, error = derive_evidence(evidence_dir / f"{path.stem}.evidence.json")
        if error:
            notes.append(f"UNIFORMITY-NOTE: {name}: evidence not verifiable: {error}")
        elif derived is not None:
            verifiable += 1
            if derived != stored:
                mismatches.append((name, stored, derived))

    distinct = len(reviewers)
    denominator = f"examined={examined} verifiable={verifiable} distinct={distinct}"
    if examined == 0:
        code = EXIT_UNKNOWN
        lines = [f"UNIFORMITY-UNKNOWN: {denominator} - nothing was examined (empty or misconfigured receipts-dir)"]
    elif mismatches:
        code = EXIT_FINDING
        lines = [
            f"UNIFORMITY-FINDING: {name}: stored reviewer={stored!r}, cross-verification derived={derived!r}"
            for name, stored, derived in mismatches
        ]
        lines.append(f"UNIFORMITY-SUMMARY: {denominator}")
    elif distinct > 1:
        code = EXIT_OK
        lines = [f"UNIFORMITY-OK: {denominator} - {distinct} distinct reviewer value(s), corpus is diverse"]
    elif verifiable > 0:
        code = EXIT_OK
        lines = [
            f"UNIFORMITY-OK: {denominator} - uniform, verified against {verifiable} receipt(s) "
            "of exec-log evidence, no mismatch"
        ]
    else:
        code = EXIT_UNKNOWN
        lines = [
            f"UNIFORMITY-UNKNOWN: {denominator} - uniform, but 0 of {examined} receipt(s) had verifiable evidence; "
            "could not distinguish a constant from a genuinely unchanging model"
        ]
    return code, "\n".join([*lines, *notes])


def selftest() -> int:
    """Exercise exactly the registered cases, including their denominators."""
    try:
        cases = json.loads((CONTROL / "control.json").read_text(encoding="utf-8"))["cases"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"UNIFORMITY-SELFTEST: FAIL: cannot load committed cases: {exc}")
        return EXIT_FINDING
    if len(cases) != 5:
        print(f"UNIFORMITY-SELFTEST: FAIL: expected five committed cases, found {len(cases)}")
        return EXIT_FINDING
    failures = 0
    with tempfile.TemporaryDirectory(prefix="counter-model-uniformity-") as temporary:
        for case in cases:
            try:
                fixture = shutil.copytree(CONTROL / case["input"], Path(temporary) / case["name"])
                code, output = scan(fixture / "receipts", fixture / "evidence")
                matched = code == case["expected_exit"] and output == case["expected_output"]
            except (OSError, ValueError, KeyError) as exc:
                matched, code, output = False, EXIT_FINDING, str(exc)
            if not matched:
                failures += 1
            print(f"UNIFORMITY-SELFTEST: {case['name']}: {'PASS' if matched else 'FAIL'}")
            if not matched:
                print(f"  observed exit={code}: {output}")
    print(f"UNIFORMITY-SELFTEST: {5 - failures}/5 cases matched")
    return EXIT_FINDING if failures else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--receipts-dir", type=Path, default=Path("docs/measurements/counter-model"))
    parser.add_argument("--evidence-dir", type=Path, help="manifests with paths relative to each manifest, or absolute")
    parser.add_argument("--selftest", action="store_true", help="run the five committed cases; ignore input flags")
    parser.add_argument("--enrolment-scan", metavar="REF", nargs="?", const="HEAD",
                        help="derive the population from history instead of from the receipts that "
                             "exist, and report a landed change with no receipt as a FINDING (#1171)")
    parser.add_argument("--repo", type=Path, default=Path("."),
                        help="repository to read history from with --enrolment-scan")
    parser.add_argument("--enrolment-limit", type=int, default=50,
                        help="how many first-parent commits to examine (default 50)")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.enrolment_scan:
        code, output = enrolment_scan(
            args.repo, args.receipts_dir, args.enrolment_scan, args.enrolment_limit
        )
        print(output)
        return code
    code, output = scan(args.receipts_dir, args.evidence_dir)
    print(output)
    return code


if __name__ == "__main__":
    sys.exit(main())
