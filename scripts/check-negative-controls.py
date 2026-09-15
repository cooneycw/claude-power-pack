#!/usr/bin/env python3
"""Run every gate's registered NEGATIVE CONTROL, and prove the control can fail (issue #924).

Seven of CPP's open issues are one defect in different gates: an instrument that
returns a confident verdict it is not entitled to. A green from a blind gate and
a green from a working gate are the same bytes, so the blindness is found by the
next person to rely on the gate rather than by the gate's author.

The practice that catches this already exists - a hand-run mutation at review
time - and it worked on every merge of 2026-09-13. What it leaves behind is
nothing: no registered control, no CI step, nothing that fails the build when a
control stops discriminating. In the reviewer's own words, "if I stop doing it,
nothing notices".

THE ONE IDEA HERE: the proof that a control CAN FAIL is a by-product of RUNNING
the control, never a separate ritual someone remembers. A control with no anchor
is UNPROVEN, `--strict` refuses it, and forgetting therefore produces a red
rather than a silence.

---------------------------------------------------------------------------
What a control asserts - three checks, and why each exists
---------------------------------------------------------------------------
DISCRIMINATION   gate(known-bad) == BAD *and* gate(known-good) == GOOD.
                 Both directions. A gate wedged at "fail" passes the known-bad
                 half on its own, so the good case is what separates a working
                 gate from a stuck one.

ANCHOR           the same control, run against a VENDORED BLIND ARTIFACT, must
                 FAIL - the artifact must MISS the known-bad input. This is
                 acceptance step 4 ("show the control still failing if the fix
                 is reverted"), executed on every run instead of once by hand.
                 An anchor that catches the bad input proves the control is not
                 load-bearing: INERT.

ANCHOR SANITY    the anchor must agree with the current gate on the known-GOOD
                 input. If it disagrees there too, it differs for reasons beyond
                 the blindness under test and the demonstration is not isolated.

---------------------------------------------------------------------------
Why the anchor is VENDORED and not fetched with `git show`
---------------------------------------------------------------------------
`git` IS NOT IN THE CI IMAGE. `scripts/check-test-binary-guards.py` carries the
machine-checked list (`CI_IMAGE_BINARIES`, pinned to `.woodpecker.yml`) and git
is not on it; that file's own docstring notes the rule "has now been forgotten
three times (#451, #489, #577)" and that it is structurally invisible locally,
because the dev box HAS git and `make verify` can never reproduce the failure.

A `git show <sha>^:<gate>` anchor would therefore have worked on the machine it
was written on and been INERT in the place it is meant to gate - which is this
issue's own defect class, inside the tool built for that defect class. So the
blind artifact is checked in, and git is used only to VERIFY its provenance,
where git happens to exist.

---------------------------------------------------------------------------
Five verdicts, because collapsing any of them loses a distinction that has
already cost someone work
---------------------------------------------------------------------------
PASS        discrimination holds and the anchor demonstrates the blindness.
BLIND       the gate did not discriminate. A real alarm about the GATE.
INERT       the anchor did not miss the known-bad input, so the control is not
            load-bearing - it would not notice the gate regressing.
UNRESOLVED  a path named by the registration is missing or unreadable. NOT a
            failure of the gate: it is the control pointed at something that is
            not here, which presents identically to BLIND and needs the opposite
            response.
UNPROVEN    registered, discriminating, but carrying NO anchor - so nothing has
            demonstrated it can fail. Not PASS. `--strict` exits non-zero.

PROVENANCE is a SEPARATE AXIS, never folded into the verdict and never a sixth
state: `ok` when the vendored anchor was byte-compared against its recorded sha,
`unverified` when git was unavailable to check. `unverified` must never print as
`ok` - the same rule as "unknown is not 0".

---------------------------------------------------------------------------
Never read the installed copy
---------------------------------------------------------------------------
This runs against the CHECKOUT, never `~/.claude/scripts`. Measured 2026-09-13:
of 54 installed helpers 51 were byte-identical to main, 3 were not, and 0 were
dead mounts - so `st_nlink == 0` corpse-checking reports a clean bill while
stale helpers serve. `check-test-binary-guards.py` was among the three, and it
was byte-identical to `c6df826` - the very pre-fix artifact this file uses as an
anchor. A control pointed at the installed copy would have produced a REAL RED
that looked like a successful demonstration: right about the file it read, and
silent about main.

Usage:
    check-negative-controls.py [--root DIR] [--strict] [--verify-provenance] [--quiet]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

#: The registration directive, read out of the GATE file itself so the control
#: cannot outlive the instrument it covers. Deleting the gate deletes the
#: registration with it; a directive naming a directory that is not there is an
#: UNRESOLVED verdict rather than a skip, because a registration that silently
#: resolves to nothing is the rot this issue exists to stop.
REGISTRATION_RE = re.compile(r"^#:?\s*NEGATIVE-CONTROL:\s*(?P<path>\S+)\s*$", re.MULTILINE)

GOOD = "GOOD"
BAD = "BAD"

PASS = "PASS"
BLIND = "BLIND"
INERT = "INERT"
UNRESOLVED = "UNRESOLVED"
UNPROVEN = "UNPROVEN"


@dataclass
class Result:
    gate: str
    control_dir: str
    verdict: str
    provenance: str = "unverified"
    details: list[str] = field(default_factory=list)


def _source_stamp(root: Path) -> str:
    """Name the copy under test: `worktree-at-<sha>`, never a bare "the helper".

    Any measurement of helper behaviour has to state WHICH COPY it ran, because
    an installed helper and a checkout can be different programs. git is absent
    in CI, so the sha comes from git when git exists, else from the CI
    environment, else it is honestly `unknown` - never guessed.
    """
    if shutil.which("git"):
        try:
            out = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                return f"worktree-at-{out.stdout.strip()}"
        except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
            pass
    for var in ("CI_COMMIT_SHA", "GITHUB_SHA"):
        sha = os.environ.get(var, "").strip()
        if sha:
            return f"worktree-at-{sha[:7]}"
    return "worktree-at-unknown"


def discover(root: Path) -> list[tuple[Path, str]]:
    """Every gate in `scripts/` carrying a registration directive."""
    found: list[tuple[Path, str]] = []
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        return found
    for path in sorted(scripts_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = REGISTRATION_RE.search(text)
        if match:
            found.append((path, match.group("path")))
    return found


#: Stands in for an exit code when the invocation could not be executed AT ALL -
#: a missing interpreter, a permissions error, a timeout. It is not a verdict.
#: Collapsing it into an exit code (it was -1, and every code but `good_exit`
#: means BAD) made an unrunnable control score as DETECTION on the known-bad case
#: and raise a GATE ALARM on the known-good one - an environment failure reported
#: as "the gate stopped discriminating", which is exactly the UNRESOLVED-versus-
#: BLIND collapse this file's verdict vocabulary exists to prevent.
UNRUNNABLE = None


def _run(argv: list[str], cwd: Path) -> tuple[int | None, str]:
    """`(exit code, diagnostic)`, or `(UNRUNNABLE, why)` when it never ran.

    The diagnostic is kept rather than discarded: a caller reading a verdict has
    no other way to tell a gate that reported something from one that fell over.
    """
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return UNRUNNABLE, f"timed out after 120s: {' '.join(argv)}"
    except (OSError, subprocess.SubprocessError) as exc:
        return UNRUNNABLE, f"{type(exc).__name__}: {exc}"
    stderr = (proc.stderr or "").strip()
    return proc.returncode, stderr.splitlines()[-1] if stderr else ""


def _verdict_of(exit_code: int, good_exit: int) -> str:
    return GOOD if exit_code == good_exit else BAD


def _invoke(spec: list[str], gate: Path, case: Path, root: Path) -> tuple[int | None, str]:
    argv = [part.replace("{gate}", str(gate)).replace("{case}", str(case)) for part in spec]
    return _run(argv, root)


def evaluate(directive_file: Path, control_rel: str, root: Path, verify_provenance: bool) -> Result:
    control_dir = (root / control_rel).resolve()
    res = Result(gate=str(directive_file.relative_to(root)), control_dir=control_rel, verdict=UNRESOLVED)

    manifest = control_dir / "control.json"
    if not manifest.is_file():
        res.details.append(f"no control.json at {control_rel}")
        return res
    try:
        spec = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        res.details.append(f"control.json unreadable: {exc}")
        return res

    invocation: list[str] = spec.get("invocation", [])
    good_exit: int = int(spec.get("good_exit", 0))
    cases: list[dict[str, str]] = spec.get("cases", [])
    anchors: list[dict[str, str]] = spec.get("anchors", [])

    # The manifest's `gate` is authoritative for WHAT IS INVOKED; the directive's
    # location is only how the control was DISCOVERED. Reading the discovered file
    # instead was a real defect in the first cut of this script, and this file's
    # own negative control is what caught it: with the declared gate absent, the
    # harness ran the file carrying the directive, which exited 0, and reported
    # BLIND. That is the exact collapse this verdict vocabulary exists to prevent -
    # "the control points at code that is not here" reported as "the gate stopped
    # discriminating". They present identically and need opposite responses.
    declared = spec.get("gate", "")
    if not declared:
        res.details.append("control.json names no gate")
        return res
    gate = (root / declared).resolve()
    if not gate.is_file():
        res.details.append(f"declared gate is absent from this checkout: {declared}")
        return res
    res.gate = declared
    # A registration must live NEXT TO the gate it covers. A directive in one file
    # declaring a control for another is the separate-document rot this design is
    # meant to avoid, so it is refused rather than followed.
    if gate != directive_file.resolve():
        res.details.append(
            f"registration lives in {directive_file.name} but declares gate {declared}"
        )
        return res
    if not invocation or not cases:
        res.details.append("control.json names no invocation or no cases")
        return res

    # A one-sided control tests nothing, so it may not reach PASS. This was only
    # DOCUMENTED before, and the code required a non-empty list: a GOOD-only
    # control passed against a gate that was genuinely blind, and a BAD-only one
    # passed against a gate wedged at "fail". Both printed the summary line "N
    # control(s) discriminate", which is a claim neither population supported.
    expects = {case.get("expect") for case in cases}
    unknown = expects - {GOOD, BAD}
    if unknown:
        res.details.append(f"control.json has case(s) with an unknown expect value: {sorted(map(str, unknown))}")
        return res
    if BAD not in expects:
        res.details.append("control.json registers no BAD case, so nothing exercises the blindness")
        return res
    if GOOD not in expects:
        res.details.append("control.json registers no GOOD case, so a gate wedged at 'fail' would pass")
        return res

    # -- DISCRIMINATION ---------------------------------------------------- #
    bad_cases: list[Path] = []
    for case in cases:
        case_path = control_dir / case["input"]
        if not case_path.is_dir():
            res.details.append(f"case input missing: {case['input']}")
            return res
        expected = case["expect"]
        code, diag = _invoke(invocation, gate, case_path, root)
        if code is UNRUNNABLE:
            res.details.append(f"case {case['name']}: the gate could not be executed - {diag}")
            return res
        observed = _verdict_of(code, good_exit)
        res.details.append(
            f"case {case['name']}: expected={expected} observed={observed} (exit {code})"
            + (f" [stderr: {diag}]" if diag else "")
        )
        if observed != expected:
            res.verdict = BLIND
            res.details.append(
                "the gate did not discriminate: it "
                + ("missed a known-bad input" if expected == BAD else "flagged a known-good input")
            )
            return res
        if expected == BAD:
            bad_cases.append(case_path)

    # -- ANCHOR + ANCHOR SANITY -------------------------------------------- #
    if not anchors:
        res.verdict = UNPROVEN
        res.details.append("no anchor: nothing has demonstrated this control can fail")
        return res

    good_cases = [control_dir / c["input"] for c in cases if c["expect"] == GOOD]
    provenances: list[str] = []
    for anchor in anchors:
        anchor_path = control_dir / anchor["path"]
        if not anchor_path.is_file():
            res.verdict = UNRESOLVED
            res.details.append(f"anchor missing: {anchor['path']}")
            return res

        # Record provenance BEFORE the behavioural checks below, and re-aggregate
        # on every anchor. All of those checks can return early, and aggregating
        # only on the success path discarded a MISMATCH already measured on an
        # EARLIER anchor - printing the default `unverified` instead. Verdict and
        # provenance are separate axes: a failing verdict must not quietly soften
        # what provenance had already established.
        provenances.append(_provenance(anchor, anchor_path, root, verify_provenance))
        res.provenance = _aggregate_provenance(provenances)

        for case_path in bad_cases:
            code, diag = _invoke(invocation, anchor_path, case_path, root)
            if code is UNRUNNABLE:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor['sha']} could not be executed - {diag}")
                return res
            observed = _verdict_of(code, good_exit)
            if observed != GOOD:
                res.verdict = INERT
                res.details.append(
                    f"anchor {anchor['sha']} CAUGHT the known-bad input, so this control would "
                    "not notice the gate regressing to it"
                )
                return res
            res.details.append(f"anchor {anchor['sha']}: missed the known-bad input (blind, as required)")

        for case_path in good_cases:
            code, diag = _invoke(invocation, anchor_path, case_path, root)
            if code is UNRUNNABLE:
                res.verdict = UNRESOLVED
                res.details.append(f"anchor {anchor['sha']} could not be executed - {diag}")
                return res
            observed = _verdict_of(code, good_exit)
            if observed != GOOD:
                res.verdict = INERT
                res.details.append(
                    f"anchor {anchor['sha']} disagrees with the current gate on a known-GOOD input, "
                    "so it differs for reasons beyond the blindness under test"
                )
                return res

    res.verdict = PASS
    return res


def _aggregate_provenance(values: list[str]) -> str:
    """Conservative: a `MISMATCH` anywhere survives, and `ok` needs EVERY anchor.

    Assigning per anchor into the single result field let the LAST anchor win, so
    a `MISMATCH` on an earlier one disappeared and the reported provenance
    depended on list order rather than on evidence. Provenance may be strengthened
    only by verification, never by position - the same rule that keeps
    `unverified` from printing as `ok`.
    """
    if not values:
        return "unverified"
    if "MISMATCH" in values:
        return "MISMATCH"
    return "ok" if all(value == "ok" for value in values) else "unverified"


def _provenance(anchor: dict[str, str], anchor_path: Path, root: Path, verify: bool) -> str:
    """`ok` only after a byte comparison against the recorded sha; else `unverified`.

    Never `ok` on a digest the manifest supplies about itself alone - that would
    only prove the file has not changed since someone wrote the digest down, not
    that it is the historical artifact it claims to be.
    """
    digest = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
    if digest != anchor.get("sha256", ""):
        return "MISMATCH"
    if not verify:
        return "unverified"
    if not shutil.which("git"):
        return "unverified"
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "show", f"{anchor['sha']}:{anchor['origin']}"],
            capture_output=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        return "unverified"
    if out.returncode != 0:
        return "unverified"
    return "ok" if hashlib.sha256(out.stdout).hexdigest() == digest else "MISMATCH"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--strict", action="store_true", help="exit non-zero on anything that is not PASS")
    parser.add_argument("--verify-provenance", action="store_true", help="byte-compare anchors against git history")
    parser.add_argument("--quiet", action="store_true", help="contract lines only")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    stamp = _source_stamp(root)
    registrations = discover(root)

    if not registrations:
        print("NEGATIVE_CONTROL_SOURCE: " + stamp)
        print("NEGATIVE_CONTROL_REGISTERED: 0")
        print("negative-controls: no gate carries a registration - nothing was checked. "
              "This is UNCHECKED, not clean.")
        return 1 if args.strict else 0

    results = [evaluate(gate, rel, root, args.verify_provenance) for gate, rel in registrations]

    for res in results:
        print(f"NEGATIVE_CONTROL_GATE: {res.gate}")
        print(f"NEGATIVE_CONTROL_SOURCE: {stamp}")
        for line in res.details:
            print(f"NEGATIVE_CONTROL_DETAIL: {line}")
        print(f"NEGATIVE_CONTROL_PROVENANCE: {res.provenance}")
        print(f"NEGATIVE_CONTROL_VERDICT: {res.verdict}")

    failing = [r for r in results if r.verdict != PASS]
    if not args.quiet:
        print()
        if failing:
            for res in failing:
                print(f"negative-controls: {res.gate} -> {res.verdict}")
                for line in res.details:
                    print(f"    {line}")
        else:
            print(f"negative-controls: ok - {len(results)} control(s) discriminate, "
                  "each demonstrated against an anchor that misses the known-bad input")
    return 1 if (failing and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
