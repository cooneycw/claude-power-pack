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
import shutil
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
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    code, output = scan(args.receipts_dir, args.evidence_dir)
    print(output)
    return code


if __name__ == "__main__":
    sys.exit(main())
