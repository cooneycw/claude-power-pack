#!/usr/bin/env python3
"""Read a CPP evaluation-enrollment decision record and report what it may claim (#1371).

THE DECISION IS DATA, AND THIS CONSUMER CAN ONLY PRINT ADVISORY STATES.
`docs/measurements/eval-enrollment/<skill>.json` records whether an evaluation
family is enrolled in CI, why, on what evidence, and until when. The reasoning
lives in `docs/decisions/0011-flow-check-eval-enrollment.md`; this script is what
makes the record CHECKED rather than merely written down. For flow-check the
decision is ADVISORY (skillc #288, answered with limits): two single-arm results,
neither able to compute #1084's Fisher rules, so the flip to blocking is
UNPROVEN, not refuted.

WHAT A READING MEANS, AND WHAT IT NEVER MEANS. Every state below is printed with
the word "advisory" or names why the record cannot be read; none says "pass",
"assured" or "blocking". A current reading says only that the recorded evidence
still applies to the shipped skill content and has not aged past its review
date - never that the skill is behaviourally assured. The record's own `limits`
are printed beside every reading, so a skimmer cannot drop them.

States (exit codes WITHOUT --advisory; each state has its OWN code, so a future
gate can tell them apart - one code for every non-current state would repeat
the defect check-skill-coverage-map.py carries, Nit Store #864):

    current        0  advisory - the recorded evidence still applies
    unknown        2  the record cannot be read as a decision (absent,
                      unreadable, unsupported schema, a required field missing,
                      a pass-rate threshold, or a blocking decision)
    stale-content  3  flow-check's shipped closure is no longer the content
                      the evidence was taken on (the CPP pin moved past the
                      evaluated revision in a way that touches the skill)
    stale-aged     4  today is past the record's review_by date
    failing        5  an evidence item records a FAILURE of its property
    fixture        6  the record describes a fixture population - not
                      behavioural evidence of any kind
    usage         64  bad arguments (not argparse's 2, which is `unknown`)

With --advisory every PRINTED verdict exits 0. A crash still exits non-zero
(a Python traceback is 1, which no state uses), so a broken consumer is never
read as "looked and found nothing" - the same discipline as
check-behavioral-eval.py's `--advisory`.

NO UNIVERSAL PASS-RATE THRESHOLD (#1084, #1367). A key naming a threshold or a
pass rate, anywhere in the record, is REFUSED as unknown rather than ignored: an
ignored threshold is one a later reader would assume was enforced.

A BLOCKING DECISION IS REFUSED HERE BY DESIGN. #1084's flip needs a
DISCRIMINATING and an IMPROVED result on a certified pairing; when that exists,
the change that lands it must also change this consumer and its tests. Until
then a record saying `blocking` is unknown, with the reason named - whether or
not its flip fields claim to be filled, because nothing here can verify them.

STALE-CONTENT IS A DIGEST OF THE WHOLE SKILL CLOSURE, computed the same way
check-skill-coverage-map.py's `digest_tree` computes it (every file under
codex/skills/<skill>/). It is restated here rather than imported so this file
runs unchanged from its registered control's anchor copy; tests pin the two
definitions equal. No git, no network, no skillc - it runs in the slim CI image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 1
USAGE_EXIT = 64
EXIT = {"current": 0, "unknown": 2, "stale-content": 3, "stale-aged": 4,
        "failing": 5, "fixture": 6}
DEFAULT_RECORD = Path("docs/measurements/eval-enrollment/flow-check.json")
REQUIRED = ("schema", "skill", "family", "decision", "population", "adr",
            "evaluated", "evidence", "limits", "review_trigger", "review_by",
            "review_by_reversal_trigger")
POPULATIONS = ("live-single-arm", "live-two-arm", "fixture")
#: A key that would smuggle in a pass-rate bar, matched on the key NAME.
THRESHOLD_KEY = re.compile(r"(?i)threshold|pass[_-]?rate|min[_-]?(pass|rate)")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"eval-enrollment: usage - {message}", file=sys.stderr)
        raise SystemExit(USAGE_EXIT)


def digest_tree(root: Path) -> dict[str, str]:
    """relative posix path -> sha256:<hex> for every FILE under root (the
    same definition as check-skill-coverage-map.py's `digest_tree`)."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = (
                "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest())
    return out


def closure_digest(repo: Path, skill: str) -> str | None:
    """One digest over the skill's whole shipped closure, or None if absent.

    Bytes AND the executable bit (counter-model review, #1371): the skill runs
    its bundled helpers directly, so a helper turned non-executable is a
    changed skill - it is exactly the degraded treatment ADR 0011's review
    trigger describes - even though not one byte moved.
    """
    root = repo / "codex" / "skills" / skill
    tree = digest_tree(root)
    if not tree:
        return None
    joined = "\n".join(
        f"{rel} {dig} {'x' if (root / rel).stat().st_mode & 0o111 else '-'}"
        for rel, dig in sorted(tree.items()))
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _threshold_keys(node: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)
            if THRESHOLD_KEY.search(str(key)):
                found.append(here)
            found += _threshold_keys(value, here)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found += _threshold_keys(value, f"{path}[{i}]")
    return found


#: NEGATIVE-CONTROL: controls/check-eval-enrollment
def evaluate(record_path: Path, repo: Path, today: date) -> dict[str, Any]:
    """The verdict for one record. Never raises on a bad record: every way a
    record can be unreadable is an `unknown` with its reason."""
    def unknown(reason: str) -> dict[str, Any]:
        return {"state": "unknown", "reason": reason, "record": str(record_path)}

    if not record_path.is_file():
        return unknown("no enrollment record - nothing records a decision, so nothing may be claimed")
    try:
        rec = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return unknown(f"record unreadable: {exc}")
    if not isinstance(rec, dict):
        return unknown("record is not a JSON object")
    if rec.get("schema") != SCHEMA:
        return unknown(f"unsupported schema {rec.get('schema')!r} (this consumer reads {SCHEMA})")
    missing = [k for k in REQUIRED if k not in rec]
    if missing:
        return unknown(f"required field(s) missing: {', '.join(missing)}")
    # Present is not usable (counter-model review, #1371): a null `adr` or
    # review trigger is a record that cannot say what governs it.
    unusable = [k for k in ("skill", "family", "adr", "review_trigger", "review_by_reversal_trigger")
                if not isinstance(rec[k], str) or not rec[k].strip()]
    if unusable:
        return unknown(f"required field(s) present but not a non-empty string: {', '.join(unusable)}")
    thresholds = _threshold_keys(rec)
    if thresholds:
        return unknown("a pass-rate threshold is refused, never ignored (#1084, #1367): "
                       + ", ".join(thresholds))
    if rec["decision"] == "blocking":
        return unknown("a blocking decision is not read by this consumer: #1084's flip needs a "
                       "DISCRIMINATING and an IMPROVED result on a certified pairing, and the change "
                       "that lands them must change this consumer too (ADR 0011)")
    if rec["decision"] != "advisory":
        return unknown(f"decision {rec['decision']!r} is neither advisory nor blocking")
    if rec["population"] not in POPULATIONS:
        return unknown(f"population {rec['population']!r} is not one of {', '.join(POPULATIONS)}")
    limits = rec["limits"]
    if not isinstance(limits, list) or not limits or not all(isinstance(x, str) and x.strip() for x in limits):
        return unknown("an advisory decision must state its limits - none are recorded")
    evidence = rec["evidence"]
    if not isinstance(evidence, list):
        return unknown("evidence is not a list")
    evaluated = rec["evaluated"]
    if not isinstance(evaluated, dict) or not evaluated.get("closure_digest"):
        return unknown("evaluated.closure_digest is missing - staleness cannot be decided")
    try:
        review_by = date.fromisoformat(str(rec["review_by"]))
    except ValueError:
        return unknown(f"review_by {rec['review_by']!r} is not an ISO date")

    base = {"record": str(record_path), "skill": rec["skill"], "family": rec["family"],
            "limits": limits, "review_by": review_by.isoformat(),
            "review_trigger": rec["review_trigger"], "adr": rec["adr"]}

    if rec["population"] == "fixture":
        return {**base, "state": "fixture",
                "reason": "fixture population - not behavioural evidence of any kind"}
    if not evidence:
        return unknown("a live population with no evidence items")
    for i, item in enumerate(evidence):
        if not isinstance(item, dict) or item.get("result") not in ("pass", "fail"):
            return unknown(f"evidence[{i}] has no result of 'pass' or 'fail'")
        provenance = [k for k in ("source_url", "skillc_sha", "family")
                      if not isinstance(item.get(k), str) or not item[k].strip()]
        if provenance:
            return unknown(f"evidence[{i}] lacks string provenance: {', '.join(provenance)}")
        # An evidence item must describe OBSERVATIONS (counter-model review,
        # #1371): counts present, integers, and at least one evaluable attempt.
        # This is a population check, not a pass-rate bar - no rate is computed.
        attempts, evaluable = item.get("attempts"), item.get("evaluable")
        if (not isinstance(attempts, int) or isinstance(attempts, bool)
                or not isinstance(evaluable, int) or isinstance(evaluable, bool)):
            return unknown(f"evidence[{i}] lacks integer attempts/evaluable counts")
        if not 0 < evaluable <= attempts:
            return unknown(f"evidence[{i}] records {evaluable} evaluable of {attempts} attempts - "
                           "no observation to stand on")

    # Evidence for ANOTHER family cannot sustain this family's reading
    # (counter-model review, #1371): #279 measures flow:auto and is recorded as
    # context, never as the evidence that keeps flow-check current.
    applicable = [item for item in evidence if item["family"] == rec["family"]]
    if not applicable:
        return unknown(f"no evidence item is for this record's own family {rec['family']!r} - "
                       "evidence about another family cannot stand in for it")

    notes: list[str] = []
    current = closure_digest(repo, str(rec["skill"]))
    content_stale = current != evaluated["closure_digest"]
    if content_stale:
        notes.append(f"shipped closure {current or '<absent>'} is not the evaluated "
                     f"{evaluated['closure_digest']} (evaluated at CPP "
                     f"{evaluated.get('cpp_revision', '?')})")
    aged = today > review_by
    if aged:
        notes.append(f"today {today.isoformat()} is past review_by {review_by.isoformat()}; "
                     f"{rec['review_by_reversal_trigger']}")

    failed = [str(item.get("id", i)) for i, item in enumerate(evidence) if item["result"] == "fail"]
    if failed:
        return {**base, "state": "failing", "notes": notes,
                "reason": "evidence records a FAILURE of its property: " + ", ".join(failed)}
    if content_stale:
        return {**base, "state": "stale-content", "notes": notes,
                "reason": "the evidence was taken on different skill content"}
    if aged:
        return {**base, "state": "stale-aged", "notes": notes,
                "reason": "the evidence is past its review date"}
    return {**base, "state": "current", "notes": notes,
            "reason": f"{len(applicable)} {rec['family']} evidence item(s) were taken on the shipped content "
                      "and are inside review_by"}


def render(v: dict[str, Any]) -> list[str]:
    skill = v.get("skill", "?")
    state = v["state"]
    if state == "unknown":
        return [f"eval-enrollment: {skill}: unknown - {v['reason']} ({v['record']})"]
    head = {
        "current": "advisory - evidence current",
        "stale-content": "advisory - STALE (content)",
        "stale-aged": "advisory - STALE (aged)",
        "failing": "advisory - evidence records a FAILURE",
        "fixture": "fixture population - not behavioural evidence",
    }[state]
    lines = [f"eval-enrollment: {skill} ({v['family']}): {head} - {v['reason']}. "
             f"NOT behavioural assurance; the decision is advisory (see {v['adr']})."]
    for note in v.get("notes", []):
        lines.append(f"eval-enrollment:   note: {note}")
    for limit in v["limits"]:
        lines.append(f"eval-enrollment:   limit: {limit}")
    lines.append(f"eval-enrollment:   review by {v['review_by']}, or on: {v['review_trigger']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = _Parser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=Path("."), help="CPP checkout (default: cwd)")
    ap.add_argument("--record", type=Path, default=None,
                    help=f"enrollment record (default: <repo>/{DEFAULT_RECORD})")
    ap.add_argument("--today", default=None, help="ISO date to evaluate review_by against (tests)")
    ap.add_argument("--advisory", action="store_true",
                    help="exit 0 on every verdict this consumer PRINTED; a crash still exits non-zero")
    ap.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    args = ap.parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    except ValueError:
        ap.error(f"--today {args.today!r} is not an ISO date")
    record = args.record if args.record is not None else args.repo / DEFAULT_RECORD
    verdict = evaluate(record, args.repo, today)
    if args.json:
        print(json.dumps(verdict, indent=2, sort_keys=True))
    else:
        print("\n".join(render(verdict)))
    return 0 if args.advisory else EXIT[verdict["state"]]


if __name__ == "__main__":
    sys.exit(main())
