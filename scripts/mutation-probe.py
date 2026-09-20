#!/usr/bin/env python3
"""Break each protection in turn, and require a control to fail (issue #970).

WHY THIS EXISTS, AND WHY READING CANNOT REPLACE IT
--------------------------------------------------
ADR 0008 requires a load-bearing instrument to ship a committed negative control.
That bound is right and it is doing work. What it does NOT establish is that the
control battery is SOUND, and the gap is structural rather than a matter of care.

An instrument is not one decision. It is a STACK of protections, and one
end-to-end case only travels whichever path its own input happens to take. Every
OTHER protection can be deleted with the battery still green. Demonstrated in
wave `cpp-completion` on 2026-09-15: nine committed controls, a genuine RED that
failed on the unfixed code, a GREEN positive control, an orchestrator who read
the set and explicitly called the positive control load-bearing - and then a
second model disabled comment rejection, command-position matching, hook
detection and transitive scanning, one at a time, and **all nine controls kept
passing, exit 0 every time**.

A battery that survives its own protections being removed and one with real
coverage PRODUCE IDENTICAL OUTPUT AND LOOK IDENTICAL ON THE PAGE. Reading is the
only method a review gate has, and reading provably cannot separate them. So
"has a committed negative control" is necessary and NOT sufficient, and the
method that does separate them is mutation: break a protection, require a
control to fail.

WHAT A VERDICT HERE MEANS, AND WHAT IT DOES NOT
-----------------------------------------------
CAUGHT       the protection was removed and the battery went RED. The battery
             NOTICES this protection. It does not establish that it noticed for
             the right reason - a mutation can also make the gate fall over, and
             a battery that reports "the gate fell over" is still noticing. The
             battery's own evidence line is printed beside every CAUGHT so a
             reader can see which happened; where the battery distinguishes them
             (check-negative-controls' BLIND versus UNSIGNALLED) the distinction
             is in that line.
UNCAUGHT     the protection was removed and the battery stayed GREEN. THIS IS
             THE DECORATIVE FINDING: nothing in the battery depends on this
             protection, so deleting it ships silently.
ACCEPTED     declared `expect: "uncaught"` with a written reason - a gap that is
             KNOWN and VISIBLE rather than hidden. Two-sided, see below.
STALE        an ACCEPTED gap that is now CAUGHT. The acceptance has outlived its
             reason and must be dropped. Without this direction the acceptance
             field would be a one-way fail-open: every accepted entry would stay
             accepted forever, including the ones somebody has since closed.
INAPPLICABLE the declared edit did not produce a working-but-weaker gate. Either
             it matched nothing (the file is unchanged, so no protection was
             removed) or it left the file unparseable. BOTH present identically
             to UNCAUGHT from the outside and need the OPPOSITE response - fix
             the declaration, not the battery - which is the same
             UNRESOLVED-versus-BLIND rule check-negative-controls already makes.
UNRESOLVED   the sandbox, the gate or the battery could not be run, or the
             UNMUTATED battery was not green. A mutation scored against a
             battery that was already red reads CAUGHT for free.

WHY THE SYNTAX CHECK IS NOT OPTIONAL
-------------------------------------
Without it the cheapest way to a green battery is to declare a mutation that
deletes the file. Everything goes red, every mutation reads CAUGHT, and the
battery is certified by an edit that never produced an instrument at all. A
mutation must leave something that still RUNS and is merely WEAKER; a file that
no longer parses is not that, and is refused as INAPPLICABLE rather than scored.

WHY THE TREE IS NEVER MUTATED
------------------------------
This tool edits instrument SOURCE, which makes it the most dangerous thing in
this repository if its sandboxing is wrong. It never writes inside the working
tree. Every mutation happens in a DISPOSABLE SANDBOX - a copy of the tracked
files under `--root` in a temp directory, git-initialised so batteries that ask
git a question still get an answer - and `tests/test_mutation_probe.py` asserts
the real gate file is byte-identical (sha256) before and after a probe run.

An in-place mutate-and-restore was the first design and is rejected: a kill
between the two leaves a weakened instrument in the tree, a concurrent suite
reads a file that is mutated for reasons it cannot see, and the restore is the
step most likely to be skipped on the failure path. 1,365 tracked files copy in
well under a second, which is cheaper than any of those.

DECLARING A MUTATION
--------------------
In the battery's own `control.json`, beside its cases - never in a separate
document, for the reason the registration directive lives in the gate file:

    "mutations": [
      {
        "name": "comment-rejection",
        "protection": "a commented-out invocation is not an invocation",
        "find": "if line\\\\.strip\\\\(\\\\)\\\\.startswith\\\\(\"#\"\\\\):",
        "replace": "if False:",
        "count": 1,
        "expect": "caught"
      }
    ]

`find` is a Python regex, matched with `re.MULTILINE` so `^` anchors a line;
`replace` is a LITERAL string, never a substitution template, so a backslash
in the replacement is a backslash and not an escape; and `count` is the number
of substitutions that MUST occur - an anchor matching twice is as wrong as one
matching nothing, which is why the count is required rather than inferred.

A manifest may declare its own `battery` (argv) when it is not one of
`controls/*`, with `battery_cwd` naming where to run it; the default battery is
the register itself, narrowed to the one control under test. Two substitutions
are available in that argv: `{root}` is the sandbox, and `{python}` is the
interpreter running this probe - a battery needing the project's dependencies
must use `{python}`, because the sandbox holds tracked files only and therefore
has no virtualenv for a runner-resolution walk to find.

WHAT THIS DOES NOT DO
---------------------
It does not enumerate a gate's protections - a human reads the gate and writes
them down. A tool that derived them would be answering "what does this code
protect against", which is not a mechanical question, and a derived list that
silently under-enumerates would recreate the exact false completeness this
exists to find. The count of DECLARED mutations is therefore a statement about
how hard somebody looked, never a coverage measure, and the summary says so.

Usage:
    mutation-probe.py [--root DIR] [--manifest REL ...] [--strict] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

#: NEGATIVE-CONTROL: controls/mutation-probe
#:     The committed pair is `covered` (a toy gate whose battery exercises both
#:     of its protections - this probe must report ok) and `decorative` (the same
#:     toy gate with a battery that exercises one - this probe must report
#:     MUTATION-UNCAUGHT and exit non-zero). The anchor is the naive first cut
#:     that reports a mutation proven whenever the battery RAN, without comparing
#:     the before and after verdicts; it passes `decorative` and is therefore
#:     blind in exactly the way the pair is built to demonstrate.
#:
#:     WHAT THIS PAIR DOES NOT COVER, said here rather than left to be assumed:
#:     the INAPPLICABLE, STALE and syntax-refusal paths are exercised by
#:     `tests/test_mutation_probe.py`, not by a committed case. That is ADR
#:     0008's carve-out applied deliberately - their failure is caught by the
#:     surrounding suite, so the suite's green is what is load-bearing there,
#:     not an individual committed input.

CAUGHT = "CAUGHT"
UNCAUGHT = "UNCAUGHT"
ACCEPTED = "ACCEPTED"
STALE = "STALE"
INAPPLICABLE = "INAPPLICABLE"
UNRESOLVED = "UNRESOLVED"

#: Verdicts that mean the battery is not established. ACCEPTED is deliberately
#: absent: it is a STATED gap, and a stated gap is the outcome this tool wants
#: when a control genuinely cannot be committed - the failure mode it exists to
#: end is the UNSTATED one.
FAILING = (UNCAUGHT, STALE, INAPPLICABLE, UNRESOLVED)

#: Long enough for a real battery (check-negative-controls runs every case of a
#: control as a subprocess), short enough that a wedged gate under mutation is
#: reported rather than inherited by whatever is waiting on this run.
BATTERY_TIMEOUT = 300


@dataclass
class Probe:
    manifest: str
    gate: str
    name: str
    protection: str
    verdict: str
    evidence: str = ""
    details: list[str] = field(default_factory=list)


def _run(argv: list[str], cwd: Path, timeout: int = 60) -> tuple[int | None, str]:
    """`(exit code, stdout+stderr)`, or `(None, why)` when it never ran at all.

    `None` is not an exit code and must never be compared against one: a battery
    that could not be executed is UNRESOLVED, and collapsing it into "non-zero,
    so the mutation was caught" would score every broken invocation as a proof.
    """
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s: {' '.join(argv)}"
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return proc.returncode, "\n".join(part for part in (proc.stdout, proc.stderr) if part)


def _source_stamp(root: Path) -> str:
    """Name the copy under test, never a bare "the probe" (the #1029 rule)."""
    code, out = _run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"], root)
    if code == 0 and out.strip():
        return f"worktree-at-{out.strip().splitlines()[0]}"
    for env in ("CI_COMMIT_SHA", "GITHUB_SHA"):
        value = os.environ.get(env, "")
        if value:
            return f"ci-at-{value[:7]}"
    return "unknown"


def build_sandbox(root: Path, dest: Path) -> tuple[bool, str]:
    """Copy `root`'s files into `dest` and make it a git repository.

    Tracked files are preferred, because a working tree carries build output,
    caches and other people's scratch files and none of them are the subject.
    A root that is not a git checkout - every committed case tree of this
    probe's own control is examined through one - is copied wholesale instead,
    and that fallback is reported rather than silent.

    The sandbox is git-initialised because batteries ask git questions. The
    register's tracking axis (#978) reports UNTRACKED for a file git does not
    know about, and an UNTRACKED control fails - so a sandbox without a commit
    would make every battery red for a reason that has nothing to do with the
    mutation under test, which is the UNRESOLVED-scored-as-CAUGHT collapse.
    """
    code, out = _run(["git", "-C", str(root), "ls-files", "-z"], root)
    try:
        if code == 0 and out:
            names = [n for n in out.split("\0") if n]
            for rel in names:
                src = root / rel
                if not src.is_file():
                    continue
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
            source = f"git ls-files ({len(names)} path(s))"
        else:
            # The prune list is an OWNERSHIP BOUNDARY, not an optimisation: a
            # virtualenv or a package cache is not the repository's code, and
            # copying one into the sandbox makes the sandbox's behaviour depend
            # on what happens to be installed in THIS checkout.
            shutil.copytree(root, dest, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(
                                ".git", ".venv", "venv", "node_modules",
                                "__pycache__", ".mypy_cache", ".pytest_cache",
                                ".ruff_cache", ".tox", "site-packages"))
            source = "wholesale copy (git could not enumerate this root)"
    except OSError as exc:
        # The ONE fatal branch, and it is fatal for a reason the alternative
        # makes obvious: a PARTIAL copy still runs, still produces verdicts, and
        # those verdicts are about a tree missing files nobody named. Refusing is
        # the difference between no answer and a confident wrong one.
        return False, f"copying {root} failed partway: {type(exc).__name__}: {exc}"

    #: GIT IS NOT IN THE CI IMAGE, by design - the same fact `check-negative-controls`
    #: vendors its anchors for. So the git-initialisation below is ADVISORY: without
    #: it a driven battery's tracking axis reads `unverified`, which is already that
    #: axis's honest answer when git is absent and is not a failure. Making it fatal
    #: would redden this step in the one place it most needs to run, for an
    #: environment fact rather than a repository one - and the step's message would
    #: say "the sandbox could not be built" about a sandbox that is perfectly usable.
    init, why = _run(["git", "-C", str(dest), "init", "-q"], dest)
    if init != 0:
        return True, f"{source}; NOT git-initialised ({why}) - driven batteries see no git"
    _run(["git", "-C", str(dest), "add", "-A"], dest)
    commit, why = _run([
        "git", "-C", str(dest),
        "-c", "user.email=mutation-probe@localhost",
        "-c", "user.name=mutation-probe",
        "commit", "-q", "-m", "sandbox",
    ], dest)
    if commit != 0:
        return True, f"{source}; git-initialised but not committed ({why})"
    return True, source


def syntax_ok(path: Path) -> tuple[bool, str]:
    """Does this file still PARSE? Three answers, and `unchecked` is not `yes`.

    A mutated gate that no longer parses is not a weaker instrument, it is a
    broken file, and scoring it would certify a battery with an edit that never
    produced an instrument. Where no checker is available the honest answer is
    that it was not checked - which the caller treats as usable, because
    refusing every mutation on a host without `bash` would make the tool depend
    on the machine rather than on the gate.
    """
    suffix = path.suffix
    try:
        head = path.open("r", encoding="utf-8", errors="replace").readline()
    except OSError as exc:
        return False, f"unreadable: {exc}"
    if suffix == ".py" or "python" in head:
        code, out = _run([sys.executable, "-m", "py_compile", str(path)], path.parent)
        cache = path.parent / "__pycache__"
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
        if code is None:
            return True, "unchecked (py_compile could not run)"
        return code == 0, "parses" if code == 0 else out.strip().splitlines()[-1] if out.strip() else "does not parse"
    if suffix == ".sh" or head.startswith("#!"):
        interpreter = "bash" if "bash" in head else "sh"
        if shutil.which(interpreter) is None:
            return True, f"unchecked ({interpreter} is not installed)"
        code, out = _run([interpreter, "-n", str(path)], path.parent)
        if code is None:
            return True, f"unchecked ({interpreter} -n could not run)"
        return code == 0, "parses" if code == 0 else out.strip().splitlines()[-1] if out.strip() else "does not parse"
    return True, "unchecked (no parser for this file type)"


def default_battery(control_rel: str) -> list[str]:
    """The register, NARROWED to the control under test.

    Running the whole register would dilute the answer in both directions: an
    unrelated control already red makes every mutation read CAUGHT, and
    twenty-two healthy controls do not make the twenty-third's silence quieter.
    `--control` refuses to match nothing (issue #970), so a narrowing typo is a
    red rather than an empty green.
    """
    return [sys.executable, "scripts/check-negative-controls.py",
            "--root", "{root}", "--control", control_rel, "--strict", "--quiet"]


def _battery_evidence(output: str) -> str:
    """The line a reader needs to see WHY the battery went red.

    Preference order is deliberate: the register's own verdict line carries the
    BLIND-versus-UNSIGNALLED distinction, which is the difference between "the
    gate stopped discriminating" and "the gate fell over" - the thing this tool
    cannot determine on its own and must not hide.
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for prefix in ("NEGATIVE_CONTROL_VERDICT:", "FAIL", "MUTATION-"):
        for line in lines:
            if line.startswith(prefix):
                return line
    return lines[-1] if lines else "(no output)"


def run_manifest(manifest_rel: str, root: Path, sandbox: Path, quiet: bool) -> list[Probe]:
    """Probe every mutation one manifest declares. Returns one Probe per mutation."""
    spec_path = root / manifest_rel
    control_rel = str(Path(manifest_rel).parent).replace(os.sep, "/")

    def unresolved(name: str, why: str) -> list[Probe]:
        return [Probe(manifest_rel, "", name, "", UNRESOLVED, details=[why])]

    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return unresolved("*", f"manifest unreadable: {exc}")

    mutations = spec.get("mutations", [])
    if not mutations:
        return []

    gate_rel = spec.get("gate", "")
    if not gate_rel:
        return unresolved("*", "manifest names no gate")
    #: A manifest under `docs/research/` names its gate relative to ITSELF; one
    #: under `controls/` names it from the repository root. Resolving only the
    #: second would read the research prototypes' gate as absent and report a
    #: whole battery UNRESOLVED for a path convention.
    gate = sandbox / gate_rel
    if not gate.is_file():
        gate = sandbox / Path(manifest_rel).parent / gate_rel
    if not gate.is_file():
        return unresolved("*", f"declared gate is absent from the sandbox: {gate_rel}")

    battery = spec.get("battery") or default_battery(control_rel)
    cwd_rel = spec.get("battery_cwd", ".")

    def run_battery() -> tuple[int | None, str]:
        #: `{python}` is THIS process's interpreter, and a battery that needs the
        #: project's dependencies must ask for it rather than write `python3`.
        #: The sandbox holds tracked files only, so it has no `.venv`; a battery
        #: resolving its runner by walking parents for one finds nothing there
        #: and reports every case UNKNOWN - an environment fact scored as a
        #: battery failure, which is the UNRESOLVED-versus-BLIND collapse. Run
        #: the probe itself under the project interpreter (`make mutation-probe`
        #: does) and `{python}` carries it through.
        argv = [part.replace("{root}", str(sandbox)).replace("{python}", sys.executable)
                for part in battery]
        return _run(argv, sandbox / cwd_rel, timeout=BATTERY_TIMEOUT)

    original = gate.read_text(encoding="utf-8")
    base_code, base_out = run_battery()
    if base_code is None:
        return unresolved("*", f"the unmutated battery could not be run: {base_out}")
    if base_code != 0:
        return unresolved("*", (
            f"the unmutated battery is already RED (exit {base_code}), so no mutation scored "
            f"against it would be evidence: {_battery_evidence(base_out)}"))
    if not quiet:
        print(f"MUTATION_PROBE_BASELINE: green ({manifest_rel})")

    probes: list[Probe] = []
    for entry in mutations:
        name = str(entry.get("name", "?"))
        protection = str(entry.get("protection", ""))
        expect = str(entry.get("expect", "caught")).lower()
        probe = Probe(manifest_rel, gate_rel, name, protection, UNRESOLVED)

        find = entry.get("find")
        replace = entry.get("replace")
        want = entry.get("count")
        if not isinstance(find, str) or not isinstance(replace, str) or not isinstance(want, int):
            probe.details.append("mutation declares no usable find/replace/count triple")
            probes.append(probe)
            continue
        if expect == "uncaught" and not str(entry.get("why", "")).strip():
            probe.details.append(
                "expect=uncaught with no `why`: an accepted gap with no written reason "
                "cannot be reviewed later and cannot be told from an oversight")
            probe.verdict = INAPPLICABLE
            probes.append(probe)
            continue

        try:
            #: `replace` is a LITERAL, never a substitution template. As a
            #: template, a backslash in the replacement is an escape - so
            #: swapping one regex constant for another (`\s`, `\$`, a
            #: backreference-looking `\1`) raised `bad escape` and the
            #: mutation was reported INAPPLICABLE for a reason that had
            #: nothing to do with the gate. A mutation declaration is a piece
            #: of source code to paste in, so it is pasted in.
            mutated, got = re.subn(find, lambda _m: replace, original, flags=re.MULTILINE)
        except re.error as exc:
            probe.verdict = INAPPLICABLE
            probe.details.append(f"`find` is not a usable regex: {exc}")
            probes.append(probe)
            continue
        if got != want:
            probe.verdict = INAPPLICABLE
            probe.details.append(
                f"`find` matched {got} time(s), the declaration requires {want}; the gate was "
                "NOT weakened, so a green battery here says nothing about the battery")
            probes.append(probe)
            continue

        gate.write_text(mutated, encoding="utf-8")
        try:
            parses, why = syntax_ok(gate)
            if not parses:
                probe.verdict = INAPPLICABLE
                probe.details.append(
                    f"the mutated gate does not parse ({why}); a broken file is not a weaker "
                    "instrument, and a battery reddened by one proves nothing")
                probes.append(probe)
                continue
            probe.details.append(f"mutated gate syntax: {why}")
            code, out = run_battery()
        finally:
            gate.write_text(original, encoding="utf-8")

        if code is None:
            probe.verdict = UNRESOLVED
            probe.details.append(f"the battery could not be run under mutation: {out}")
        elif code != 0:
            probe.evidence = _battery_evidence(out)
            probe.verdict = STALE if expect == "uncaught" else CAUGHT
        else:
            probe.verdict = ACCEPTED if expect == "uncaught" else UNCAUGHT
            if expect == "uncaught":
                probe.details.append(str(entry.get("why", "")))
        probes.append(probe)

    return probes


def discover_manifests(root: Path) -> list[str]:
    """Every `controls/*/control.json` in the tree, in a stable order.

    Deliberately NOT recursive past one level and deliberately not extended to
    `docs/`: a research prototype's manifest is probed by NAMING it with
    `--manifest`, so a directory of committed fixtures - this probe's own case
    trees among them - cannot enter the population of the run that is examining
    them.
    """
    controls = root / "controls"
    if not controls.is_dir():
        return []
    return sorted(
        f"controls/{child.name}/control.json"
        for child in controls.iterdir()
        if (child / "control.json").is_file()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", action="append", default=None, metavar="REL",
                        help="probe this manifest instead of every controls/*/control.json")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero on anything that is not CAUGHT or ACCEPTED")
    parser.add_argument("--quiet", action="store_true", help="contract lines only")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    print(f"MUTATION_PROBE_SOURCE: {_source_stamp(root)}")

    population = discover_manifests(root)
    selected = args.manifest if args.manifest else population
    if not selected:
        print("MUTATION_PROBE_POPULATION: 0")
        print("mutation-probe: no manifest to probe - nothing was checked. "
              "This is UNCHECKED, not clean.", file=sys.stderr)
        return 1

    missing = [rel for rel in selected if not (root / rel).is_file()]
    if missing:
        print("mutation-probe: named manifest(s) absent from this tree: "
              + ", ".join(missing), file=sys.stderr)
        return 1

    results: list[Probe] = []
    declaring = 0
    with tempfile.TemporaryDirectory(prefix="mutation-probe-") as tmp:
        sandbox = Path(tmp) / "tree"
        sandbox.mkdir(parents=True)
        built, how = build_sandbox(root, sandbox)
        print(f"MUTATION_PROBE_SANDBOX: {how}")
        if not built:
            print(f"mutation-probe: the sandbox could not be built - {how}. "
                  "Nothing was probed; this is UNRESOLVED, not clean.", file=sys.stderr)
            return 1
        for rel in selected:
            probes = run_manifest(rel, root, sandbox, args.quiet)
            if probes:
                declaring += 1
            results.extend(probes)

    for probe in results:
        line = f"{probe.manifest}::{probe.name}"
        if probe.protection:
            line += f" - {probe.protection}"
        if probe.verdict == CAUGHT:
            print(f"MUTATION-CAUGHT: {line}  via: {probe.evidence}")
        elif probe.verdict == ACCEPTED:
            print(f"MUTATION-ACCEPTED: {line}")
        else:
            print(f"MUTATION-{probe.verdict}: {line}")
        for detail in probe.details:
            if detail:
                print(f"MUTATION_PROBE_DETAIL: {detail}")

    undeclared = len(selected) - declaring
    print(f"MUTATION_PROBE_POPULATION: {len(selected)}")
    print(f"MUTATION_PROBE_COVERAGE: {declaring} of {len(selected)} selected manifest(s) "
          f"declare a mutation; {undeclared} declare none")

    failing = [p for p in results if p.verdict in FAILING]
    if not args.quiet:
        print()
        if failing:
            for probe in failing:
                print(f"mutation-probe: {probe.manifest}::{probe.name} -> {probe.verdict}")
                for detail in probe.details:
                    if detail:
                        print(f"    {detail}")
        else:
            caught = sum(1 for p in results if p.verdict == CAUGHT)
            accepted = sum(1 for p in results if p.verdict == ACCEPTED)
            # What this run ESTABLISHED, with its population beside it. The
            # declared count is how hard somebody looked, never how much of the
            # gate is covered - a gate with one declared mutation reads "1 of 1"
            # and is not thereby proven, which is why the sentence says so
            # instead of leaving the number to be read as a fraction of the gate.
            print(f"mutation-probe: ok - {caught} declared protection(s) removed and caught by a "
                  f"control, {accepted} accepted as uncovered with a written reason, across "
                  f"{declaring} of {len(selected)} manifest(s). The declared count states how "
                  f"many protections were WRITTEN DOWN, not how many the gate has.")
    return 1 if (failing and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
