#!/usr/bin/env python3
"""
forced-claim-check.py - PROTOTYPE for issue #953.

Not a shipped gate. Nothing in the tree invokes this; see LIMITS in
docs/research/forced-claim-prototype-2026-09-15.md for what that means for
every claim made about it.

---------------------------------------------------------------------------
THE ONE IDEA
---------------------------------------------------------------------------
Every line of the end-of-run block is a CLAIM, an OBSERVATION made by
something other than the claimant, and a VERDICT that is a comparison of the
two.

That is one mechanism, not two. #956 forces an AGENT to state a checkable
claim ("I added 3 tests, named X Y Z") instead of grading itself. #952
forces an INSTRUMENT to state its denominator ("scanned 96 files") instead
of printing a bare green. A denominator IS a forced claim - the same
principle pointed at a script instead of at an agent - so this file
implements one convention and applies it to both.

---------------------------------------------------------------------------
THE VERDICT ENUMERATION - four, and the rule that keeps it at four (#953
condition 1)
---------------------------------------------------------------------------
VERIFIED   claim present, observation agrees. The ONLY clean state.
DISAGREE   claim present, observation contradicts it. An affirmative
           contradiction between two known values.
ABSENT     the checker ran and the claimant filed no claim. NOT a void:
           the checker running is what makes this an observation.
UNKNOWN    no interpretable observation could be made. Never clean.

Every non-VERIFIED verdict carries a MANDATORY reason. The rule that decides
whether a new state is a verdict or a reason:

    different CONCLUSION        -> a new verdict
    same conclusion, different CAUSE -> a reason on an existing verdict

So UNSIGNALLED - a pre-fix test run that failed without an attributable
assertion - is a REASON on UNKNOWN, not a fifth verdict and not a DISAGREE.
It licenses the same conclusion as any other UNKNOWN ("you may not conclude;
go fix the instrument"), and it is not a contradiction between two known
values, so filing it under DISAGREE would send a reader off to compare
numbers when the actual problem is a broken test run.

ABSENT stays separate from UNKNOWN under the same rule: they license
DIFFERENT actions. ABSENT means the agent was silent (make it file; tier 2
is disabled). UNKNOWN means the check could not conclude (fix the check).

---------------------------------------------------------------------------
A CRASH IS NOT A MATCH - detect_signal, translated from gates to pytest
---------------------------------------------------------------------------
Lifted directly from scripts/check-negative-controls.py (issue #946/#963),
which had this exact bug one level up: it decided a case from the exit code
alone, so a gate that CRASHED on the known-bad input scored identically to
one that REPORTED it.

Tier 2 re-runs each named test against the PRE-FIX tree and requires it to
fail there. But pytest exits non-zero for an assertion failure, a collection
error, an ImportError and a usage mistake alike. A test that fails pre-fix
by ImportError has demonstrated NOTHING about the defect, and scoring it as
a match would make the tier a check that passes for the wrong reason - the
precise failure it exists to prevent.

So a match requires a SIGNAL, not merely a non-zero exit. The signal is the
CAUSE in pytest's short summary line, `FAILED <nodeid> - <cause>`: an
assertion reads `assert 1 == 2` or `AssertionError: ...`, anything else names
the exception class that killed the test.

Reading only "is `FAILED` present" is NOT enough and was this file's own first
cut. pytest reports an exception raised INSIDE the test body as FAILED, not as
ERROR - only a COLLECTION failure is an ERROR - so an `import` that blows up on
the first line of the function scored as a clean assertion match. The committed
fixture hid it by putting the bad import at module scope. Codex found it on
review; there is now a fixture for each.

AND THE TIER IS TWO-SIDED. Failing before the fix proves nothing on its own: a
test that fails everywhere - `assert False` - fails pre-fix too. So a named
test must ALSO PASS on the fixed tree. This is the same argument #963 makes for
gates, where the known-good input is what separates a working gate from one
wedged at "fail", and this file argued it in its own design while checking one
side.

---------------------------------------------------------------------------
EXIT CODES - three, because two cannot say "not established" (#953)
---------------------------------------------------------------------------
0   VERIFIED. The only clean state.
1   HARD FAIL - DISAGREE(inflated), DISAGREE(no-match) or
    DISAGREE(no-discrimination).
3   NOT ESTABLISHED - UNKNOWN, ABSENT, or DISAGREE(under). Non-blocking by
    the approved asymmetric policy, and never a pass.

Exit 3 rather than 2 because argparse owns 2. A caller that treats 3 as a
pass has reintroduced the fail-open this prototype exists to close - which
is the same correction this ticket made to check-negative-controls.py, whose
"nothing was checked / UNCHECKED, not clean" message is honest while its
exit code is gated behind --strict (`return 1 if args.strict else 0`, line
593). UNKNOWN is the DEFAULT verdict here, not a strict-mode upgrade.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

CLAIM_FILE = "claim.json"
ANCHOR_FILE = "anchor.log"

VERIFIED = "VERIFIED"
DISAGREE = "DISAGREE"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"

EXIT_CLEAN = 0
EXIT_HARD_FAIL = 1
EXIT_NOT_ESTABLISHED = 3

# Reasons that hard-fail. Everything else that is not VERIFIED is exit 3.
HARD_FAIL_REASONS = {"inflated", "no-match", "no-discrimination"}

STDLIB_SKIP = {
    "pytest", "sys", "os", "json", "re", "pathlib", "subprocess", "typing",
    "dataclasses", "collections", "itertools", "functools", "math", "time",
    "datetime", "tempfile", "shutil", "hashlib", "argparse", "ast", "__future__",
}


@dataclass
class Row:
    """One CLAIM / OBSERVATION / VERDICT line of the block."""

    name: str
    claimed: str
    observed: str
    verdict: str
    reason: str = ""
    denominator: str = ""
    owner_items: list[str] = field(default_factory=list)

    def render(self) -> str:
        v = self.verdict if self.verdict == VERIFIED else f"{self.verdict}({self.reason})"
        return (
            f"  {self.name}\n"
            f"    claimed:     {self.claimed}\n"
            f"    observed:    {self.observed}\n"
            f"    denominator: {self.denominator or 'NOT STATED - reads UNKNOWN'}\n"
            f"    verdict:     {v}"
        )


def _test_functions(tree_root: Path) -> dict[str, set[str]]:
    """Map test-file relpath -> set of `def test_*` names. The PUBLISHED counting
    rule (#953): a test is a module-level or class-level `def`/`async def` whose
    name starts with `test_`, in a file named `test_*.py`. Published so a
    DISAGREE is about facts rather than about guessing the parser."""
    found: dict[str, set[str]] = {}
    if not tree_root.is_dir():
        return found
    for path in sorted(tree_root.rglob("test_*.py")):
        rel = str(path.relative_to(tree_root))
        names: set[str] = set()
        try:
            mod = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            found[rel] = names
            continue
        for node in mod.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith("test_"):
                        names.add(f"{node.name}::{sub.name}")
        found[rel] = names
    return found


def _changed_files(base: Path, head: Path) -> list[str]:
    """Relpaths differing between the two trees (added, removed or modified)."""
    def snapshot(root: Path) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        if not root.is_dir():
            return out
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[str(p.relative_to(root))] = p.read_bytes()
        return out

    a, b = snapshot(base), snapshot(head)
    return sorted(set(a) ^ set(b) | {k for k in set(a) & set(b) if a[k] != b[k]})


def _is_test_path(rel: str) -> bool:
    return Path(rel).name.startswith("test_") and rel.endswith(".py")


def _new_tests(base: Path, head: Path) -> list[str]:
    """Test node ids present in head and not in base."""
    before, after = _test_functions(base), _test_functions(head)
    new: list[str] = []
    for rel, names in after.items():
        for n in sorted(names - before.get(rel, set())):
            new.append(f"{rel}::{n}")
    return sorted(new)


def _import_escape(test_file: Path, temp_root: Path, project_modules: set[str]) -> str | None:
    """Return an offending module name if the test imports a local-looking module
    that is NOT present in the tree under test. That is the 'installed copy
    outlives the fix' hazard: the test would import site-packages, the pre-fix
    tree would never be exercised, and the run would record a result having run
    no experiment."""
    try:
        mod = ast.parse(test_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    names: set[str] = set()
    for node in ast.walk(mod):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    for name in sorted(names):
        if name in STDLIB_SKIP or name in sys.stdlib_module_names:
            continue
        # NARROWED after review. The first cut flagged ANY import that was not
        # in the tree but was importable from the ambient environment, so a
        # test importing an ordinary third-party dependency (yaml, requests)
        # reported UNKNOWN(import-escape) and asserted that "the pre-fix tree
        # was never exercised" - a claim the evidence did not support, and one
        # whose verdict would flip when an unrelated package was installed.
        #
        # Only PROJECT modules have provenance that matters here: a module the
        # change itself ships. If it exists in the head tree but not in the
        # tree under test, the test would import someone else's copy. An
        # external dependency is not this check's business - and if it is
        # genuinely missing, pytest fails and the signal check above catches it.
        if name not in project_modules:
            continue
        in_tree = (temp_root / f"{name}.py").exists() or (temp_root / name / "__init__.py").exists()
        if not in_tree:
            return name
    return None


def _project_modules(*roots: Path) -> set[str]:
    """Top-level module names the change itself ships, across the given trees."""
    mods: set[str] = set()
    scan: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        scan.append(root)
        # A src-layout project ships `src/widget/__init__.py`, so a root-only
        # scan called `import widget` an external dependency and skipped the
        # guard entirely. Common source roots are scanned too. This is still a
        # CONVENTION, not a read of the project's configured package roots -
        # see LIMITS in the design document.
        for conventional in ("src", "lib"):
            sub = root / conventional
            if sub.is_dir():
                scan.append(sub)
    for root in scan:
        for p in root.iterdir():
            if p.is_file() and p.suffix == ".py":
                mods.add(p.stem)
            elif p.is_dir() and (p / "__init__.py").exists():
                mods.add(p.name)
    return mods


def _claim_shape_error(claim: object) -> str | None:
    """Reject a structurally invalid claim BEFORE it is used.

    Added after review: only json.JSONDecodeError was handled, so valid JSON of
    the wrong shape (`null`, `{"tests": null}`, `{"tests_added": "oops"}`)
    raised out of the checker and produced NO BLOCK AT ALL. A checker that dies
    leaves exactly the state this design exists to remove - indistinguishable
    from a step that never ran."""
    if not isinstance(claim, dict):
        return f"claim is {type(claim).__name__}, expected an object"
    tests = claim.get("tests", [])
    if not isinstance(tests, list) or not all(isinstance(t, str) for t in tests):
        return "'tests' must be a list of strings"
    n = claim.get("tests_added", len(tests))
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        return "'tests_added' must be a non-negative integer"
    return None


def _resolve_runner() -> str | None:
    """An interpreter that can actually run pytest, or None.

    This exists because the first cut used sys.executable unconditionally and
    every pytest-invoking case came back UNKNOWN(unsignalled) - the checker
    reporting "your test crashed without an attributable assertion" when the
    truth was "I have no pytest". Same verdict class, completely different
    cause and completely different fix, which is exactly the distinction this
    file's own reason-vs-verdict rule exists to preserve. It was caught by the
    committed cases rather than by reading the code.
    """
    candidates = [sys.executable]
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        candidates.append(str(Path(venv) / "bin" / "python"))
    for parent in Path(__file__).resolve().parents:
        local_venv = parent / ".venv" / "bin" / "python"
        if local_venv.exists():
            candidates.append(str(local_venv))
            break
    # A git worktree has no .venv of its own - it lives in the primary
    # checkout, which git-common-dir resolves to from anywhere.
    common = subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parent),
         "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True,
    )
    if common.returncode == 0 and common.stdout.strip():
        primary = Path(common.stdout.strip()).parent / ".venv" / "bin" / "python"
        if primary.exists():
            candidates.append(str(primary))
    for cand in candidates:
        if not cand:
            continue
        probe = subprocess.run([cand, "-m", "pytest", "--version"], capture_output=True)
        if probe.returncode == 0:
            return cand
    return None


def _run_named_test(temp_root: Path, node_id: str, runner: str) -> tuple[str, str]:
    """Run one test in the pre-fix tree. Returns (outcome, detail) where outcome
    is one of match / no-match / unsignalled.

    The SIGNAL is `FAILED <nodeid>` in pytest's short summary. A non-zero exit
    alone is not a match - see the module docstring.

    The first cut of this function also treated any output containing the
    substring "error" as unsignalled, which matched pytest's own chatter and
    made EVERY case unsignalled. That is the over-broad-signal failure Codex
    found in check-negative-controls.py on #963 (a regex matching everything
    restores crash-as-detection), reproduced here by hand. The match is
    anchored to the node id now.
    """
    proc = subprocess.run(
        [runner, "-m", "pytest", "--tb=no", "-q", "-p", "no:cacheprovider", "-rA", node_id],
        capture_output=True, text=True, cwd=str(temp_root),
        env={**os.environ, "PYTHONPATH": str(temp_root)},
    )
    out = (proc.stdout + proc.stderr).replace("\r", "")
    if proc.returncode == 0:
        # Exit 0 is NOT "it passed". pytest also exits 0 when the selected test
        # is SKIPPED or XFAILed, so a conditional skip on the fixed tree scored
        # as a successful run and completed a discrimination that never
        # happened. Require the test to have actually reported PASSED.
        if f"PASSED {node_id}" in out:
            return "pass", "PASSED"
        state = next((w for w in ("SKIPPED", "XFAIL", "XPASS") if f"{w} {node_id}" in out), None)
        return "unsignalled", f"exit 0 but the test reported {state or 'no outcome'}, not PASSED"
    if proc.returncode == 5:
        return "unsignalled", "pytest collected no tests for this node id"

    failed = next((ln for ln in out.splitlines() if ln.startswith(f"FAILED {node_id}")), None)
    if failed:
        # THE SIGNAL, and the first cut got it wrong in a way Codex caught on
        # review. pytest prints `FAILED <nodeid>` for a raised exception INSIDE
        # the test body too - an ImportError at line 1 of the function is a
        # FAILED, not an ERROR. Only a COLLECTION failure is an ERROR. So
        # "FAILED is present" accepted exactly the crash-as-detection this
        # tier exists to refuse; the committed fixture had hidden it by putting
        # the bad import at module scope.
        #
        # pytest's short summary is `FAILED <nodeid> - <cause>`. A genuine
        # assertion reads `assert 1 == 2` or `AssertionError: ...`; anything
        # else names the exception class that killed it.
        tail = failed.split(" - ", 1)[1].strip() if " - " in failed else ""
        if tail.startswith("assert") or tail.startswith("AssertionError"):
            return "match", "failed by assertion on the pre-fix tree"
        cause = tail.split(":", 1)[0][:60] or "unknown cause"
        return "unsignalled", f"failed by {cause}, not by an assertion"
    if f"ERROR {node_id}" in out:
        first = next((ln for ln in out.splitlines() if "Error" in ln), "")
        return "unsignalled", f"collection/import error, not an assertion [{first.strip()[:80]}]"
    return "unsignalled", f"no FAILED line for {node_id} (exit {proc.returncode})"


def _amendment_count(case: Path, anchor: Path | None) -> tuple[str, str, str, int]:
    """(claimed, observed, reason) for the amendment counter.

    THE CONDITION-3 ANSWER. A counter kept anywhere the claimant can write is
    resettable, and a reset is INDISTINGUISHABLE from a genuine first filing -
    both present as 'no prior claims'. So a local counter cannot be made
    unfakeable, and this says so rather than printing a reassuring 0.

    Notice the shape: 'zero, or unable to tell?' is #952's amended denominator
    rule exactly. The counter IS a denominator - it states how many prior
    claims it examined - so the rule already on the books applies unchanged. A
    bare 0 is never emitted by this function.
    """
    if anchor is None or not anchor.exists():
        return ("-", "no non-claimant-authored record available",
                "unanchored", -1)
    # Records are PARSED, not counted as text. Counting distinct non-empty
    # lines meant an unrelated line ("CI job started") became an amendment, and
    # a pretty-printed claim could never match a single line - so formatting
    # decided identity. Both directions were wrong.
    def _norm(text: str) -> str | None:
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
        if _claim_shape_error(obj) is not None:
            return None
        assert isinstance(obj, dict)
        return json.dumps(
            {"tests_added": obj.get("tests_added", len(obj.get("tests", []))),
             "tests": sorted(obj.get("tests", []))},
            sort_keys=True,
        )

    seen: list[str] = []
    for line in anchor.read_text(encoding="utf-8").splitlines():
        rec = _norm(line.strip())
        if rec is not None and rec not in seen:
            seen.append(rec)
    # Added after review: an EMPTY or truncated anchor produced
    # "0 amendment(s) / 0 distinct claim(s)" and an anchored VERIFIED row, so a
    # record establishing nothing scored exactly like one establishing a clean
    # first filing. That is this file's own zero-denominator rule violated
    # inside the very counter written to honour it.
    #
    # An anchor is only evidence about THIS claim if it contains this claim.
    if not seen:
        return ("-", f"{anchor.name} exists but records nothing",
                "anchor-incomplete", -1)
    current = (case / CLAIM_FILE)
    if current.exists():
        want = _norm(current.read_text(encoding="utf-8").strip())
        if want is not None and want not in seen:
            return ("-", f"{anchor.name} does not contain the current claim",
                    "anchor-incomplete", -1)
    n = max(0, len(seen) - 1)
    return (f"{n} amendment(s)", f"{len(seen)} distinct claim(s) in {anchor.name}", "anchored", n)


def check_case(case: Path) -> tuple[list[str], str, str, int, dict]:
    """Returns (block_lines, verdict, reason, exit_code, facts)."""
    base, head = case / "base", case / "head"
    rows: list[Row] = []
    owner: list[str] = []
    facts: dict = {"tier2_tests_executed": 0}

    # --- Denominator first. #952: a zero reads UNKNOWN unless the instrument
    # can show it was looking in the right place.
    changed = _changed_files(base, head)
    base_ok = base.is_dir()
    denom = f"base={'present' if base_ok else 'MISSING'}, {len(changed)} changed file(s)"
    if not base_ok:
        rows.append(Row("scope", "-", "no pre-fix tree to compare against", UNKNOWN,
                        "no-denominator", denom))
        return _finish(rows, owner, facts)
    if not changed:
        rows.append(Row("scope", "-", "nothing changed between the trees", UNKNOWN,
                        "no-denominator",
                        f"{denom} - a zero denominator is UNKNOWN, not clean (#952 amendment)"))
        return _finish(rows, owner, facts)

    observed_new = _new_tests(base, head)
    code_changed = [f for f in changed if not _is_test_path(f)]
    obs_denom = f"base present, {len(changed)} changed file(s), {len(code_changed)} non-test"

    # --- The claim.
    claim_path = case / CLAIM_FILE
    if not claim_path.exists():
        # ABSENT, and tier 2 is DISABLED - not widened to the whole suite.
        rows.append(Row(
            "tests added", "no claim filed", f"{len(observed_new)} new test(s) in the diff",
            ABSENT, "no-claim", obs_denom))
        rows.append(Row(
            "match test (tier 2)", "-",
            "DISABLED - tier 2 is scoped BY the claim; with nothing named it does "
            "not fall back to the whole suite",
            ABSENT, "no-claim", "0 test(s) executed"))
        owner.append("No claim was filed. The checker ran and observed this - it is "
                     "not the same as the step not running.")
        facts["tier2_tests_executed"] = 0
        return _finish(rows, owner, facts)

    try:
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rows.append(Row("tests added", "unparseable claim", str(exc)[:70], UNKNOWN,
                        "claim-unreadable", obs_denom))
        return _finish(rows, owner, facts)

    shape_error = _claim_shape_error(claim)
    if shape_error:
        rows.append(Row("tests added", "claim of the wrong shape", shape_error, UNKNOWN,
                        "claim-unreadable", obs_denom))
        owner.append(f"The filed claim could not be interpreted: {shape_error}. The "
                     f"checker still produced this block - a receipt saying so is the "
                     f"point, since dying here would look like never having run.")
        return _finish(rows, owner, facts)

    claimed_names = list(claim.get("tests", []))
    claimed_n = int(claim.get("tests_added", len(claimed_names)))

    # --- Tier 1: mechanical, free, needs no model.
    missing = [t for t in claimed_names if t not in observed_new]
    unexamined = [t for t in observed_new if t not in claimed_names]

    # Condition 2: print BOTH numbers always, so under-reporting is measured
    # rather than merely tolerated.
    both = f"claimed {claimed_n}, diff contains {len(observed_new)}"

    if missing:
        rows.append(Row("tests added", f"{both}; named {len(claimed_names)}",
                        f"named-but-absent: {', '.join(missing)}",
                        DISAGREE, "inflated", obs_denom))
        owner.append(f"Claim names {len(missing)} test(s) not present in the diff: "
                     f"{', '.join(missing)}")
        return _finish(rows, owner, facts)
    if claimed_n > len(observed_new):
        rows.append(Row("tests added", both,
                        f"{len(observed_new)} found - claim exceeds the diff",
                        DISAGREE, "inflated", obs_denom))
        owner.append(f"Claim of {claimed_n} exceeds the {len(observed_new)} test(s) in the diff.")
        return _finish(rows, owner, facts)

    under = len(observed_new) > claimed_n or unexamined
    tier1_verdict, tier1_reason = (DISAGREE, "under") if under else (VERIFIED, "")
    rows.append(Row("tests added", both,
                    f"{len(observed_new)} new test(s); {len(unexamined)} unexamined",
                    tier1_verdict, tier1_reason, obs_denom))
    if under:
        owner.append(
            f"{len(unexamined)} test(s) in this diff were never named and therefore "
            f"never match-tested: {', '.join(unexamined)}. Under-reporting is "
            f"non-blocking but it is not invisible.")

    # --- Tier 2: match test, scoped BY the claim.
    if not code_changed:
        rows.append(Row("match test (tier 2)", f"{len(claimed_names)} named test(s)",
                        "pre-fix tree is identical in every non-test file",
                        UNKNOWN, "match-not-lit",
                        "0 test(s) executed - the experiment was never lit"))
        owner.append("Tier 2 could not be lit: the diff changes no non-test file, so "
                     "the pre-fix tree does not differ in the code under test.")
        return _finish(rows, owner, facts)

    runner = _resolve_runner()
    if runner is None:
        rows.append(Row("match test (tier 2)", f"{len(claimed_names)} named test(s)",
                        "no interpreter on this host can run pytest",
                        UNKNOWN, "no-runner",
                        "0 test(s) executed - the tier could not run at all"))
        owner.append("Tier 2 could not run: no pytest available. This is NOT the same "
                     "as the named tests failing to discriminate - do not read it as one.")
        return _finish(rows, owner, facts)

    # Added after review: an empty named-test population walked the loop zero
    # times and printed "all 0 failed by assertion" as VERIFIED. `scanned 0,
    # clean` - the exact shape #952's amendment forbids, inside the tool built
    # to enforce it. A tier with no population has not run an experiment.
    if not claimed_names:
        rows.append(Row("match test (tier 2)", "0 named test(s)",
                        "no population to run - nothing was match-tested",
                        UNKNOWN, "empty-population",
                        "0 test(s) executed - a zero here is UNKNOWN, not clean"))
        owner.append("The claim named no tests, so tier 2 ran no experiment. A tier-1 "
                     "count of zero may be legitimate; a tier-2 verdict on zero tests "
                     "is not.")
        return _finish(rows, owner, facts)

    project_mods = _project_modules(base, head)

    with tempfile.TemporaryDirectory(prefix="forced-claim-") as td:
        temp = Path(td) / "tree"
        shutil.copytree(base, temp)
        # Pre-fix code + post-fix tests. The fix is deliberately NOT applied.
        for rel in changed:
            if _is_test_path(rel) and (head / rel).exists():
                dst = temp / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(head / rel, dst)
        head_temp = Path(td) / "head"
        shutil.copytree(head, head_temp)

        outcomes: list[str] = []
        executed = 0
        for node_id in claimed_names:
            rel = node_id.split("::")[0]
            escape = _import_escape(temp / rel, temp, project_mods) if (temp / rel).exists() else None
            if escape:
                rows.append(Row("match test (tier 2)", node_id,
                                f"imports '{escape}' from outside the tree under test",
                                UNKNOWN, "import-escape",
                                f"{executed} test(s) executed"))
                owner.append(f"{node_id} resolves '{escape}' from the ambient environment, "
                             f"not the tree under test - the pre-fix tree was never exercised.")
                return _finish(rows, owner, facts)
            outcome, detail = _run_named_test(temp, node_id, runner)
            executed += 1
            outcomes.append(outcome)
            facts["tier2_tests_executed"] = executed
            if outcome == "match":
                # BOTH SIDES. Added after review: only the pre-fix tree was
                # run, so a test that fails EVERYWHERE - `assert False` - was
                # credited as discriminating the moment any non-test file
                # changed. Failing before the fix shows nothing on its own;
                # #963 makes exactly this argument for gates ("a gate wedged at
                # fail passes the known-bad half"), and this file quoted it in
                # its own design while checking one side.
                head_outcome, head_detail = _run_named_test(head_temp, node_id, runner)
                if head_outcome == "unsignalled":
                    # NOT no-discrimination. The fixed-tree run never produced an
                    # interpretable result - a collection error there says nothing
                    # about whether the test discriminates, and calling it an
                    # affirmative contradiction is the same collapse this file
                    # refuses for pre-fix crashes.
                    rows.append(Row(
                        "match test (tier 2)", node_id,
                        f"fixed-tree run was uninterpretable ({head_detail})",
                        UNKNOWN, "head-unsignalled", f"{executed} test(s) executed"))
                    owner.append(
                        f"{node_id} failed by assertion pre-fix, but the fixed-tree run "
                        f"could not be interpreted, so discrimination is UNPROVEN rather "
                        f"than refuted.")
                    return _finish(rows, owner, facts)
                if head_outcome != "pass":
                    rows.append(Row(
                        "match test (tier 2)", node_id,
                        f"fails on the pre-fix tree AND on the fixed tree ({head_detail})",
                        DISAGREE, "no-discrimination", f"{executed} test(s) executed"))
                    owner.append(
                        f"{node_id} fails on BOTH trees, so its pre-fix failure is not "
                        f"evidence about the defect. Either the test is broken or the "
                        f"claimed fix does not work.")
                    return _finish(rows, owner, facts)
            if outcome == "pass":
                rows.append(Row("match test (tier 2)", node_id, detail,
                                DISAGREE, "no-match", f"{executed} test(s) executed"))
                owner.append(f"{node_id} passes on the pre-fix tree - it does not "
                             f"discriminate and demonstrates nothing about the defect.")
                return _finish(rows, owner, facts)
            if outcome == "unsignalled":
                rows.append(Row("match test (tier 2)", node_id, detail,
                                UNKNOWN, "unsignalled", f"{executed} test(s) executed"))
                owner.append(f"{node_id} exited like a failure on the pre-fix tree without "
                             f"an attributable assertion. A crash is not a match (#963).")
                return _finish(rows, owner, facts)

        rows.append(Row("match test (tier 2)", f"{len(claimed_names)} named test(s)",
                        f"all {executed} failed by assertion pre-fix AND pass on the fix",
                        VERIFIED, "", f"{executed} test(s) executed, both trees"))

    return _finish(rows, owner, facts)


def _finish(rows: list[Row], owner: list[str], facts: dict) -> tuple[list[str], str, str, int, dict]:
    worst, reason = VERIFIED, ""
    for r in rows:
        if r.verdict == VERIFIED:
            continue
        if r.reason in HARD_FAIL_REASONS:
            worst, reason = r.verdict, r.reason
            break
        if worst == VERIFIED:
            worst, reason = r.verdict, r.reason
    if worst == VERIFIED:
        code = EXIT_CLEAN
    elif reason in HARD_FAIL_REASONS:
        code = EXIT_HARD_FAIL
    else:
        code = EXIT_NOT_ESTABLISHED
    lines = [r.render() for r in rows]
    for r in rows:
        owner.extend(r.owner_items)
    facts["_owner"] = owner
    return lines, worst, reason, code, facts


def render_block(case: Path, anchor: Path | None) -> tuple[str, str, str, int, dict]:
    rows, verdict, reason, code, facts = check_case(case)
    a_claimed, a_observed, a_reason, a_n = _amendment_count(case, anchor)
    amend = Row("claim amendments", a_claimed, a_observed,
                VERIFIED if a_reason == "anchored" else UNKNOWN,
                "" if a_reason == "anchored" else a_reason,
                "anchored to a record the claimant does not author"
                if a_reason == "anchored"
                else "NO anchor - a reset is indistinguishable from a first filing")
    facts["amendment_state"] = a_reason
    facts["amendments"] = a_n
    if a_reason != "anchored" and code == EXIT_CLEAN:
        code = EXIT_NOT_ESTABLISHED
        verdict, reason = UNKNOWN, a_reason

    out: list[str] = []
    out.append("=" * 72)
    out.append("END-OF-RUN BLOCK (prototype - issue #953)")
    out.append("=" * 72)
    out.append("")
    out.append("-- VERIFIED CLAIMS " + "-" * 53)
    out.extend(rows)
    out.append(amend.render())
    out.append("")
    out.append("  counter-model: absent (intent unreviewed)")
    out.append("")
    # Reserved for #965. Owned by that issue, populated here so its slot has a
    # producer on day one: every DISAGREE and every UNKNOWN lands in it.
    out.append("-- IN PLAIN LANGUAGE " + "-" * 51)
    out.append("  [reserved for #965 - this checker does not write this section]")
    out.append("")
    out.append("-- YOURS TO DECIDE " + "-" * 53)
    items = list(facts.get("_owner", []))
    if a_reason == "unanchored":
        items.append(
            "The amendment counter is unanchored: a claim that was discarded and "
            "re-filed is indistinguishable from a first filing, so the count reads "
            "UNKNOWN rather than 0.")
    elif a_reason != "anchored":
        items.append(
            "An amendment record exists but does not establish this claim, so it "
            "cannot support a count. An empty or unrelated record is not evidence "
            "of a clean first filing.")
    if items:
        for item in items:
            out.append(f"  - {item}")
    else:
        out.append("  - nothing outstanding")
    out.append("")
    out.append(f"FORCED_CLAIM_VERDICT: {verdict}" + (f"({reason})" if reason else ""))
    out.append(f"FORCED_CLAIM_TIER2_EXECUTED: {facts.get('tier2_tests_executed', -1)}")
    out.append(f"FORCED_CLAIM_AMENDMENT_STATE: {facts.get('amendment_state', '-')}")
    out.append(f"FORCED_CLAIM_AMENDMENTS: {facts.get('amendments', -1)}")
    out.append(f"FORCED_CLAIM_EXIT: {code}")
    return "\n".join(out), verdict, reason, code, facts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", help="run one case fixture directory")
    ap.add_argument("--anchor", help="a record of prior claims the claimant does not author")
    ap.add_argument("--selftest", action="store_true", help="run every case in control.json")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent

    if args.selftest:
        manifest = json.loads((here / "control.json").read_text(encoding="utf-8"))
        cases = manifest["cases"]
        print(f"FORCED_CLAIM_SELFTEST_SOURCE: {here / 'control.json'}")
        print(f"FORCED_CLAIM_SELFTEST_REGISTERED: {len(cases)}")
        if not cases:
            print("forced-claim: no case carries a registration - nothing was checked. "
                  "This is UNCHECKED, not clean.")
            return EXIT_NOT_ESTABLISHED
        # THE FIXTURE DATA MUST BE TRACKED. This guard exists because the
        # opposite nearly shipped: `.gitignore` carries blanket `*.json` and
        # `*.log` rules, so every manifest, claim and anchor here was ignored,
        # `git add -A` reported success while skipping them, and this selftest
        # reported "14/14 cases behaved as registered" against files that were
        # not in the repository. A fresh checkout would have crashed.
        #
        # An instrument that cannot see its own inputs going missing is the
        # exact thing #953 is about, so it detects it rather than trusting it -
        # the same move check-negative-controls.py makes when it refuses to go
        # green having scanned nothing.
        untracked: list[str] = []
        probe = subprocess.run(["git", "ls-files", "--error-unmatch", str(here / "control.json")],
                               capture_output=True, cwd=str(here))
        if probe.returncode != 0:
            untracked.append("control.json")
        for spec in cases:
            for fname in (CLAIM_FILE, ANCHOR_FILE):
                f = here / spec["input"] / fname
                if not f.exists():
                    continue
                r = subprocess.run(["git", "ls-files", "--error-unmatch", str(f)],
                                   capture_output=True, cwd=str(here))
                if r.returncode != 0:
                    untracked.append(f"{spec['name']}/{fname}")
        if untracked:
            print(f"FORCED_CLAIM_UNTRACKED: {len(untracked)}")
            for u in untracked:
                print(f"forced-claim: UNTRACKED fixture input - {u}")
            print("forced-claim: fixture data is not in the repository, so these results "
                  "describe this machine and not this commit. This is UNCHECKED, not clean.")
            return EXIT_NOT_ESTABLISHED
        print("FORCED_CLAIM_UNTRACKED: 0")

        failures = 0
        for spec in cases:
            cdir = here / spec["input"]
            # THROUGH THE REAL CLI, in a subprocess. The first cut asserted
            # against the tuple render_block returns, which never touched
            # `main()` or `sys.exit`. Changing the CLI's final `return code` to
            # `return 0` left every assertion green while real callers accepted
            # every negative case - the exact exit-contract regression these
            # assertions were added to catch, still uncaught by them.
            run = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--case", str(cdir)],
                capture_output=True, text=True,
            )
            code = run.returncode
            emitted = {}
            for line in run.stdout.splitlines():
                if line.startswith("FORCED_CLAIM_"):
                    k, _, v = line.partition(": ")
                    emitted[k] = v.strip()
            got = emitted.get("FORCED_CLAIM_VERDICT", "NO-VERDICT-LINE")
            facts = {
                "tier2_tests_executed": int(emitted.get("FORCED_CLAIM_TIER2_EXECUTED", -1)),
                "amendment_state": emitted.get("FORCED_CLAIM_AMENDMENT_STATE", "?"),
                "amendments": int(emitted.get("FORCED_CLAIM_AMENDMENTS", -1)),
            }
            want = spec["expect"]
            ok = got == want
            extra = ""
            if "expect_tier2_executed" in spec:
                want_n = spec["expect_tier2_executed"]
                got_n = facts.get("tier2_tests_executed", -1)
                if got_n != want_n:
                    ok = False
                extra += f" tier2_executed={got_n}(want {want_n})"
            if "expect_amendment_state" in spec:
                want_s = spec["expect_amendment_state"]
                got_s = facts.get("amendment_state", "?")
                if got_s != want_s:
                    ok = False
                extra += f" amend_state={got_s}(want {want_s})"
            if "expect_amendments" in spec:
                want_a = spec["expect_amendments"]
                got_a = facts.get("amendments", -1)
                if got_a != want_a:
                    ok = False
                extra += f" amendments={got_a}(want {want_a})"
            # The verdict STRING is not the contract - the exit code is what a
            # caller branches on. Checking only the string let a regression that
            # returned 0 for everything still report 9/9. Registered per case.
            want_exit = spec.get("expect_exit")
            if want_exit is not None:
                if code != want_exit:
                    ok = False
                extra += f" exit={code}(want {want_exit})"
            print(f"FORCED_CLAIM_CASE: {spec['name']:<30} expected={want:<26} "
                  f"observed={got:<26} {'ok' if ok else 'MISMATCH'}{extra}")
            if not ok:
                failures += 1
        print(f"FORCED_CLAIM_SELFTEST: {len(cases) - failures}/{len(cases)} cases behaved as registered")
        return EXIT_CLEAN if failures == 0 else EXIT_HARD_FAIL

    if not args.case:
        ap.error("one of --case or --selftest is required")
    cdir = Path(args.case).resolve()
    anchor = Path(args.anchor).resolve() if args.anchor else (cdir / ANCHOR_FILE)
    block, _, _, code, _ = render_block(cdir, anchor if anchor.exists() else None)
    print(block)
    return code


if __name__ == "__main__":
    sys.exit(main())
