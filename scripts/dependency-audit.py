#!/usr/bin/env python3
"""Audit the locked dependency set against published advisories (issue #961).

CPP ran no dependency vulnerability audit. The two advisories on the root lock
were found by a person looking and filed as #922 ("tracked by no issue"); the
32 in `mcp-evaluate/uv.lock` the same way, as #943. Advisories arrive whether
or not anything is watching; the only variable is whether a gate finds them or
someone notices.

`lib/security/modules/pip_audit.py` is NOT that gate and this does not replace
it. That adapter runs only inside `/security:scan` (`scan_full` / `scan_deep`),
appends to `skipped` when the binary is absent, and reads `requirements.txt` -
a file CPP does not have - so with pip-audit installed it audits the ambient
environment rather than this project's lock. `lib.security gate` runs the quick
scan, which never reaches it at all (ADR 0008 row 61). Its defects are tracked
separately; this file is the repository's own gate over its own locks.

---------------------------------------------------------------------------
The shape, inherited rather than invented (ADR 0008, "Adopting a third-party
linter as an instrument")
---------------------------------------------------------------------------
`shellcheck` (#960) settled this shape and the ADR states it is the one
`pip-audit` (#961) and `bandit` (#962) inherit:

DERIVE THE POPULATION, NEVER GLOB IT. The lock files are found by walking the
tree with a declared prune list, and the run reports `source=walk`. A hardcoded
pair of paths would be wrong the day a third project is added, and would be
"fixed" by whoever adds it - the person least motivated to check.

PRINT THE DENOMINATOR ON EVERY RUN, INCLUDING THE CLEAN ONE. `0 findings` means
nothing beside an unstated number of files. A zero-file population is UNKNOWN,
not clean.

A MISSING BINARY IS UNKNOWN AND EXITS NON-ZERO, NEVER A PASS. So is an
unreachable advisory feed, which is the same fact arriving by a different route:
this run could not look. Issue #961 asks for the two outcomes to be
DISTINGUISHABLE IN THE OUTPUT, and they are - `dependency-audit: ok` is a
statement about the dependency set, `DEP-AUDIT-UNKNOWN:` is a statement about
this run. The tempting `command -v pip-audit || exit 0` goes green on every
machine that lacks the tool, which is the dormant-instrument failure the ADR
exists to prevent, and which the `lib/security` adapter above already
demonstrates in this repository.

SUPPRESSIONS ARE VISIBLE OR THEY DO NOT HAPPEN. Adopting at a level the tree
can hold means the residual is recorded, counted and printed - never disabled.
`.dependency-audit-allow` carries one line per accepted finding with the issue
tracking it, and the count appears on every run including the clean one.

---------------------------------------------------------------------------
Why an allowlist entry that matches NOTHING is a RED
---------------------------------------------------------------------------
An allowlist is a hand-maintained enumeration, and this repository's own
`.gitignore` is the standing demonstration of how those age: a negation list
whose comment says the glob "covers the next consumer", which then did not.
Only one side of that is fixable here, and it is the side that keeps the
residual honest: an `advisory` line whose finding is no longer reported, or a
`deferred` line whose file is absent or clean, is STALE and exits 1. So when
#922 lands, this gate reddens until its two lines come out - the suppression
cannot outlive the thing it suppresses.

The other side is NOT fixed: nothing here stops the list GROWING. That is named
rather than solved.

---------------------------------------------------------------------------
Three inputs, because the control has to run where the harness runs (ADR 0008)
---------------------------------------------------------------------------
LIVE (default)   walk the tree, `uv export` each lock, run pip-audit. Needs
                 `uv`, `pip-audit` and the network.

--from-capture   replay a committed capture of pip-audit's own JSON. Stdlib
                 only, offline, no `uv` and no network - so it gives the SAME
                 verdict in the slim CI image, on a dev box with no pip-audit,
                 and inside `check-negative-controls.py`. This is what the
                 registered control exercises, and the precedent is exactly
                 `controls/check-oscillation`, which feeds its detector
                 committed `git log` captures because git is absent from the CI
                 image.

--selftest       the live path against two committed requirements fixtures: a
                 pin with published advisories that must REPORT, and a clean
                 pin that must NOT. This is the half `--from-capture` cannot
                 cover - that pip-audit is actually invoked, and invoked against
                 the file we meant. The CI step runs it BEFORE the real audit,
                 so every clean verdict is preceded by a demonstration that this
                 run could have found something.

Neither alone is enough, and saying which one covers which half is the point.

Usage:
    dependency-audit.py [--root DIR] [--allow-file PATH]
    dependency-audit.py --from-capture FILE [--allow-file PATH]
    dependency-audit.py --capture FILE [--root DIR]
    dependency-audit.py --selftest [--root DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

#: NEGATIVE-CONTROL: controls/dependency-audit
#:     Registered per issue #961, under ADR 0008's bound: this is a gate that
#:     lets work THROUGH. The CI `dependency-audit` step reads its green as
#:     "the locked dependency set carries no unaccounted advisory", and nothing
#:     downstream re-derives that. A blind version prints the same clean line
#:     over a lock with four advisories in it, which is this tree's state today.
#:
#:     The registered cases are OFFLINE captures, deliberately. A control whose
#:     invocation needed the network would report UNSIGNALLED on a blip - an
#:     environment failure wearing the diagnosis "the gate stopped
#:     discriminating", which is the exact collapse the harness's verdict
#:     vocabulary exists to prevent. What the offline cases do NOT establish -
#:     that pip-audit is invoked, and invoked against the right file - is
#:     established by `--selftest` in the CI step instead. Both halves, each
#:     where it can actually run.

SUMMARY = "dependency-audit"
FINDING = "DEP-AUDIT-FINDING"
STALE = "DEP-AUDIT-STALE"
UNKNOWN = "DEP-AUDIT-UNKNOWN"
SELFTEST = "DEP-AUDIT-SELFTEST"

EXIT_OK = 0
EXIT_FINDING = 1
EXIT_UNKNOWN = 2

LOCK_NAME = "uv.lock"
ALLOW_FILE = ".dependency-audit-allow"
CAPTURE_SCHEMA = 1

#: Directories the walk never descends into, and the reason each is here.
#: Excluding a fixture DIRECTORY is not suppressing a check (ADR 0008): nothing
#: in these trees is a dependency set this repository installs.
PRUNE = {
    ".git",            # not a source tree
    ".venv", "venv",   # installed environments, not declarations
    "node_modules",
    "__pycache__",
    ".ci-bin",         # binaries staged by CI steps
    ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "controls",        # negative-control fixtures: captures, not locks
    "codex",           # byte-identical generated copies of scripts/ (#555)
    "vendor",          # vendored upstream source, locked by its own repo
}

#: How long pip-audit may take per file. It resolves every pinned package
#: against the advisory feed, and on a cold `uvx` it downloads pip-audit first.
AUDIT_TIMEOUT = 420
EXPORT_TIMEOUT = 180


@dataclass(frozen=True)
class Finding:
    path: str
    package: str
    version: str
    advisory: str

    def line(self) -> str:
        return f"{self.path} {self.package} {self.version} {self.advisory}"


@dataclass
class AllowEntry:
    kind: str          # "advisory" | "deferred"
    path: str
    package: str
    version: str
    advisory: str
    issue: str
    source_line: int
    used: bool = False


class Unknown(Exception):
    """This run could not look. Never a pass, and never printed as one."""


# --------------------------------------------------------------------------- #
# The allowlist
# --------------------------------------------------------------------------- #

def parse_allow(path: Path) -> list[AllowEntry]:
    """Read `.dependency-audit-allow`, or an empty list when it is absent.

    An ABSENT file is legitimately empty - a tree with no accepted residual -
    and is not UNKNOWN. An UNREADABLE or MALFORMED one is UNKNOWN: a
    suppression ledger that could not be read leaves every finding's
    disposition undecided, and guessing "nothing is suppressed" would redden
    a tree that is correctly accounted for while guessing the opposite would
    hide everything.
    """
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise Unknown(f"allowlist {path} is unreadable: {exc}") from exc

    entries: list[AllowEntry] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        # WHOLE-LINE COMMENTS ONLY, and a trailing one is a parse error rather
        # than a stripped suffix. `#` is the comment character AND the first
        # character of every issue reference this file exists to carry, so
        # `line.split("#")[0]` silently ate the `#922` off the end of the first
        # record written against this gate. Refusing the ambiguity is cheaper
        # than a heuristic about which `#` was meant.
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "advisory" and len(parts) == 6:
            _, file_path, package, version, advisory, issue = parts
            entries.append(AllowEntry("advisory", file_path, package, version, advisory, issue, number))
        elif parts[0] == "deferred" and len(parts) == 3:
            _, file_path, issue = parts
            entries.append(AllowEntry("deferred", file_path, "", "", "", issue, number))
        else:
            raise Unknown(
                f"allowlist {path} line {number} is not a record this gate understands: {raw.strip()!r} "
                "(expected `advisory <path> <package> <version> <advisory-id> <issue>` "
                "or `deferred <path> <issue>`)"
            )
    return entries


# --------------------------------------------------------------------------- #
# Reading pip-audit's own report
# --------------------------------------------------------------------------- #

def findings_from_report(path: str, report: dict) -> tuple[list[Finding], int]:
    """`(deduped findings, packages examined)` from one pip-audit JSON report.

    DEDUPED, because pip-audit reports the same advisory once per vulnerability
    SOURCE it resolved: `pyyaml==5.1` came back as "6 known vulnerabilities" for
    3 distinct advisory ids. Counting those six would inflate every number this
    gate prints and would make an allowlist entry look like it covered less than
    it does.
    """
    if not isinstance(report, dict):
        raise Unknown(f"pip-audit report for {path} is not an object")
    deps = report.get("dependencies")
    if not isinstance(deps, list):
        raise Unknown(f"pip-audit report for {path} carries no `dependencies` list")
    seen: set[Finding] = set()
    for dep in deps:
        name = str(dep.get("name", "")).strip()
        version = str(dep.get("version", "")).strip()
        for vuln in dep.get("vulns", []) or []:
            advisory = str(vuln.get("id", "")).strip()
            if not (name and version and advisory):
                raise Unknown(
                    f"pip-audit report for {path} carries a finding with no package, version or id"
                )
            seen.add(Finding(path, name, version, advisory))
    return sorted(seen, key=lambda f: (f.package, f.version, f.advisory)), len(deps)


# --------------------------------------------------------------------------- #
# The live path
# --------------------------------------------------------------------------- #

def resolve_pip_audit() -> list[str]:
    """The argv prefix that runs pip-audit, or UNKNOWN.

    `uv` is already a hard requirement of this repository (`TOOLS_HARD` in the
    Makefile), so `uvx pip-audit` makes the tool reachable on any box that can
    already run `make test` - no third declared dependency, and no `pip install`
    into an ambient environment.
    """
    direct = shutil.which("pip-audit")
    if direct:
        return [direct]
    for runner in ("uvx", "uv"):
        found = shutil.which(runner)
        if found and runner == "uvx":
            return [found, "pip-audit"]
        if found:
            return [found, "tool", "run", "pip-audit"]
    raise Unknown(
        "pip-audit is not on PATH and neither is `uv` to run it - this run examined nothing. "
        "Install pip-audit, or `uv`, which can run it without installing."
    )


def export_requirements(lock: Path, out: Path) -> None:
    """`uv export` one lock into a requirements file, without touching the lock.

    `--all-extras` IS LOAD-BEARING. The default export omits dev dependencies,
    and BOTH advisories on this repository's root lock (#922: pygments, pytest)
    live there - so the narrower export reports the root lock clean while the
    tree carries two known advisories. A gate answering a narrower question than
    the one asked is the failure this flag exists to avoid.

    `--frozen` is equally load-bearing in the other direction: without it
    `uv export` may re-resolve and REWRITE `uv.lock`, and an instrument that
    mutates the tree it measures is not an instrument.
    """
    uv = shutil.which("uv")
    if not uv:
        raise Unknown(f"`uv` is not on PATH, so {lock} could not be exported - this run examined nothing")
    cmd = [uv, "export", "--format", "requirements-txt", "--no-hashes",
           "--no-emit-project", "--all-extras", "--frozen"]
    try:
        proc = subprocess.run(
            cmd, cwd=lock.parent, capture_output=True, text=True,
            timeout=EXPORT_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise Unknown(f"`uv export` for {lock} could not be run: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        raise Unknown(f"`uv export` for {lock} failed: {tail[-1] if tail else 'no diagnostic'}")
    out.write_text(proc.stdout, encoding="utf-8")


def audit_requirements(requirements: Path, prefix: list[str]) -> dict:
    """pip-audit's raw JSON report for one requirements file.

    The exit code is NOT the verdict here - pip-audit exits 1 both when it finds
    advisories and when it cannot reach the feed. What separates them is whether
    a parseable report came back, so the report is the evidence and an
    unparseable one is UNKNOWN with pip-audit's own last diagnostic attached.
    """
    cmd = [*prefix, "--format", "json", "--progress-spinner", "off",
           "--requirement", str(requirements)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=AUDIT_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise Unknown(f"pip-audit timed out after {AUDIT_TIMEOUT}s on {requirements}") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise Unknown(f"pip-audit could not be run: {exc}") from exc
    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        tail = (proc.stderr or "").strip().splitlines()
        raise Unknown(
            f"pip-audit returned no usable report for {requirements} (exit {proc.returncode}): "
            f"{tail[-1] if tail else 'no diagnostic'} - the advisory feed may be unreachable, "
            "so this run examined nothing"
        ) from exc


def discover_locks(root: Path) -> list[Path]:
    """Every `uv.lock` under `root`, by walking with a declared prune list."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNE)
        if LOCK_NAME in filenames:
            found.append(Path(dirpath) / LOCK_NAME)
    return sorted(found)


def collect_live(root: Path) -> list[dict]:
    """`[{path, report}]` for every lock in the tree."""
    locks = discover_locks(root)
    if not locks:
        raise Unknown(
            f"no {LOCK_NAME} found under {root} - a zero-file population is not a clean one"
        )
    prefix = resolve_pip_audit()
    files: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="dependency-audit-") as tmp:
        for index, lock in enumerate(locks):
            rel = lock.relative_to(root).as_posix()
            requirements = Path(tmp) / f"{index}-requirements.txt"
            export_requirements(lock, requirements)
            files.append({"path": rel, "report": audit_requirements(requirements, prefix)})
    return files


# --------------------------------------------------------------------------- #
# The capture
# --------------------------------------------------------------------------- #

def read_capture(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Unknown(f"capture {path} is unreadable: {exc}") from exc
    if payload.get("schema") != CAPTURE_SCHEMA:
        raise Unknown(f"capture {path} declares schema {payload.get('schema')!r}, not {CAPTURE_SCHEMA}")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise Unknown(f"capture {path} names no files - a zero-file population is not a clean one")
    for entry in files:
        if not isinstance(entry, dict) or "path" not in entry or "report" not in entry:
            raise Unknown(f"capture {path} carries an entry with no `path` or no `report`")
    return files


def write_capture(path: Path, files: list[dict]) -> None:
    payload = {"schema": CAPTURE_SCHEMA, "files": files}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# The verdict
# --------------------------------------------------------------------------- #

def adjudicate(files: list[dict], allow: list[AllowEntry], source: str) -> tuple[list[str], int]:
    """Print the report, return `(finding lines, exit code)`.

    Every disposition is one of four, and each is counted and printed:
    GATING (nothing accounts for it), SUPPRESSED (an exact `advisory` line),
    DEFERRED (its whole file is deferred to an issue), or absent. Plus STALE:
    an allowlist line that accounted for nothing this run.
    """
    deferred_paths = {e.path: e for e in allow if e.kind == "deferred"}
    advisory_index: dict[str, AllowEntry] = {
        f"{e.path} {e.package} {e.version} {e.advisory}": e for e in allow if e.kind == "advisory"
    }

    gating: list[Finding] = []
    suppressed = 0
    deferred_count = 0
    packages = 0
    seen_paths: set[str] = set()

    for entry in files:
        path = str(entry["path"])
        seen_paths.add(path)
        found, dep_count = findings_from_report(path, entry["report"])
        packages += dep_count
        deferral = deferred_paths.get(path)
        for finding in found:
            match = advisory_index.get(finding.line())
            if match is not None:
                match.used = True
                suppressed += 1
            elif deferral is not None:
                deferral.used = True
                deferred_count += 1
            else:
                gating.append(finding)

    lines: list[str] = []
    for finding in gating:
        lines.append(
            f"{FINDING}: {finding.line()} - no allowlist entry accounts for it. "
            f"Bump the package, or record it in {ALLOW_FILE} with the issue tracking it."
        )

    # An entry that accounted for NOTHING this run. Both kinds are stale by the
    # same rule - it stopped suppressing something - and they differ only in the
    # sentence printed, because "the file is gone" and "the file is clean now"
    # send a reader to different places.
    stale = [entry for entry in allow if not entry.used]
    for entry in stale:
        if entry.kind == "advisory":
            lines.append(
                f"{STALE}: {ALLOW_FILE} line {entry.source_line} suppresses "
                f"{entry.path} {entry.package} {entry.version} {entry.advisory} ({entry.issue}), "
                "which this run did not report - remove the line."
            )
        else:
            why = "is absent from the population" if entry.path not in seen_paths else "reported nothing"
            lines.append(
                f"{STALE}: {ALLOW_FILE} line {entry.source_line} defers {entry.path} "
                f"({entry.issue}), which {why} - remove the line."
            )

    residual = []
    if suppressed:
        issues = sorted({e.issue for e in allow if e.kind == "advisory" and e.used})
        residual.append(f"{suppressed} suppressed ({', '.join(issues)})")
    if deferred_count:
        issues = sorted({e.issue for e in allow if e.kind == "deferred" and e.used})
        files_deferred = len({e.path for e in allow if e.kind == "deferred" and e.used})
        residual.append(f"{deferred_count} deferred in {files_deferred} file(s) ({', '.join(issues)})")
    tail = ", " + ", ".join(residual) if residual else ""

    verdict = "ok - " if not lines else ""
    # `source=` names the DERIVATION, not just the count (ADR 0008's shape). A
    # `walk` verdict is about the tree as it is now; a `capture` verdict is about
    # the reports someone recorded earlier, and the two must never read alike.
    print(
        f"{SUMMARY}: {verdict}{len(files)} file(s) examined (source={source}), {packages} package(s), "
        f"{len(gating)} gating finding(s), {len(stale)} stale allowlist line(s){tail}"
    )
    return lines, EXIT_FINDING if lines else EXIT_OK


# --------------------------------------------------------------------------- #
# The live positive control
# --------------------------------------------------------------------------- #

def selftest(root: Path) -> int:
    """Prove the LIVE path can still find something, before any clean verdict.

    `--from-capture` cannot establish this: it replays a report rather than
    producing one, so it is silent on whether pip-audit is invoked at all, and
    on whether it is invoked against the file we meant. A clean run of a scan
    that cannot see is indistinguishable from a clean tree, so the CI step runs
    this FIRST and the real audit only afterwards.
    """
    live = root / "controls" / "dependency-audit" / "live"
    bad = live / "bad-known-advisory" / "requirements.txt"
    good = live / "good-clean" / "requirements.txt"
    for path in (bad, good):
        if not path.is_file():
            print(f"{UNKNOWN}: selftest fixture {path} is absent - this run proved nothing", file=sys.stderr)
            return EXIT_UNKNOWN

    prefix = resolve_pip_audit()
    bad_found, _ = findings_from_report(str(bad), audit_requirements(bad, prefix))
    good_found, _ = findings_from_report(str(good), audit_requirements(good, prefix))

    problems: list[str] = []
    if not bad_found:
        problems.append(
            f"the known-vulnerable fixture {bad.relative_to(root)} reported NOTHING, so a clean "
            "verdict from this run would say nothing about the tree"
        )
    if good_found:
        problems.append(
            f"the clean fixture {good.relative_to(root)} reported "
            + ", ".join(f.advisory for f in good_found)
            + " - re-pin it (see its own header); until then this gate cannot show it is not wedged at 'fail'"
        )
    if problems:
        for problem in problems:
            print(f"{SELFTEST}: {problem}", file=sys.stderr)
        print(f"{SELFTEST}: failed")
        return EXIT_FINDING
    print(
        f"{SELFTEST}: ok - the live path reported {len(bad_found)} advisory(ies) on the "
        "known-vulnerable fixture and none on the clean one"
    )
    return EXIT_OK


# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="tree to audit (default: the current directory)")
    parser.add_argument("--allow-file", default=None,
                        help=f"suppression ledger (default: <root>/{ALLOW_FILE})")
    parser.add_argument("--from-capture", default=None, metavar="FILE",
                        help="replay a committed capture instead of running pip-audit (offline)")
    parser.add_argument("--capture", default=None, metavar="FILE",
                        help="write this run's raw pip-audit reports to FILE")
    parser.add_argument("--selftest", action="store_true",
                        help="prove the live path can report a known advisory, and not a clean one")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    allow_path = Path(args.allow_file) if args.allow_file else root / ALLOW_FILE

    try:
        if args.selftest:
            return selftest(root)
        if args.from_capture:
            files, source = read_capture(Path(args.from_capture)), "capture"
        else:
            files, source = collect_live(root), "walk"
        if args.capture:
            write_capture(Path(args.capture), files)
        allow = parse_allow(allow_path)
        lines, code = adjudicate(files, allow, source)
    except Unknown as exc:
        # Printed AFTER nothing else, and never alongside a summary line: a run
        # that could not look must not also emit a sentence shaped like a
        # verdict about the dependency set.
        print(f"{UNKNOWN}: {exc}", file=sys.stderr)
        return EXIT_UNKNOWN
    for line in lines:
        print(line, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
