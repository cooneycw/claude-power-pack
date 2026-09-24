#!/usr/bin/env python3
"""flow-plan-record.py - the /flow:auto plan record and as-read snapshot (issue #1211).

One helper owns what used to be six programs pasted into `flow/auto.md`
(issues #1080, #1081, #1082). The agent calls a subcommand and reads its verdict;
the reasoning behind each rule lives in `docs/agents/flow-plan-record.md`.

    reconcile  ISSUE                    Step 1: restore the committed record, or remove scratch
    read-issue ISSUE [--body-file F]    Step 1: store the issue body as read, in the git dir
    approve    ISSUE                    Step 4: write the as-read snapshot, stamp the baseline
    drift      ISSUE [--live-file F]    Step 6: has the issue body moved since it was read?
    compliance ISSUE [--base REF]       Step 6: does the diff's file set match the approved plan?
    head-check ISSUE [--head SHA]       Step 6: does the record exist at the PR head?

Run every subcommand from inside the run's worktree. `--body-file`,
`--live-file` and `--head` replace the `gh` call so the decision can be
controlled with real local inputs instead of a stubbed `gh`.

EXIT CODES - each state has its own, so a caller reading `$?` can tell them apart:
    0  ok: reconciled, recorded, clean, agreement + unchanged, present
    1  error, or head-check ABSENT (a STOP)
    2  usage error
    3  finding: drift, divergence, or the plan record changed since Step 4
    4  unknown / unresolved: the question could not be answered. NEVER clean.

The verdict lines (AS_READ, ISSUE_DRIFT, PLAN_COMPLIANCE, PLAN_RECORD_STABILITY,
FLOW_PLAN_RECORD) are the contract. FLOW_PLAN_RECORD_EXIT=<code> is the last
line written, on stderr (issue #1031).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import hashlib
import os
import pathlib
import re
import subprocess
import sys
import traceback
from typing import NoReturn

CAP = 16384
OK, ERROR, USAGE, FINDING, UNKNOWN = 0, 1, 2, 3, 4


class Verdict(Exception):
    """Ends a subcommand with a verdict already printed."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def git(*args: str, cwd: pathlib.Path | None = None, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=check).stdout


def git_dir() -> pathlib.Path:
    return pathlib.Path(git("rev-parse", "--absolute-git-dir").strip())


def toplevel() -> pathlib.Path:
    return pathlib.Path(git("rev-parse", "--show-toplevel").strip())


def record_rel(issue: str) -> str:
    return f"docs/flow-runs/issue-{issue}.md"


def snapshot_rel(issue: str) -> str:
    return f"docs/flow-runs/issue-{issue}.as-read.md"


def gh_body(issue: str) -> bytes | None:
    """The live issue body, or None when it could not be read."""
    try:
        proc = subprocess.run(["gh", "issue", "view", issue, "--json", "body", "--jq", ".body"],
                              capture_output=True, check=False)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


# ---------------------------------------------------------------- reconcile (#1080)

def cmd_reconcile(issue: str) -> int:
    """Tracked is EVIDENCE and is restored; untracked or staged-only is SCRATCH.

    Asks HEAD, not the index, and restores from HEAD, not the index - see
    docs/agents/flow-plan-record.md for the four states that decided this.
    """
    root = toplevel()
    rec = record_rel(issue)
    in_head = subprocess.run(["git", "cat-file", "-e", f"HEAD:{rec}"], cwd=root,
                             capture_output=True).returncode == 0
    if in_head:
        subprocess.run(["git", "checkout", "HEAD", "--", rec], cwd=root, check=True,
                       capture_output=True)
        print(f"FLOW_PLAN_RECORD: restored {rec} (the last COMMITTED, approved record)")
        return OK
    subprocess.run(["git", "rm", "-q", "--cached", "--ignore-unmatch", rec], cwd=root,
                   capture_output=True)
    path = root / rec
    if path.exists():
        path.unlink()
        print(f"FLOW_PLAN_RECORD: removed {rec} (scratch never committed on this branch)")
    else:
        print(f"FLOW_PLAN_RECORD: absent {rec} (no approved record on this branch)")
    return OK


# ---------------------------------------------------------------- read-issue (#1081)

def store_base(issue: str) -> pathlib.Path:
    return git_dir() / f"flow-as-read-{issue}"


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_read_issue(issue: str, body_file: str | None) -> int:
    """Store what this run read in the GIT DIR, where the driver guard cannot see it."""
    base = store_base(issue)
    body_p, meta_p = base.with_suffix(".body"), base.with_suffix(".meta")
    upd_p = base.with_suffix(".updated")
    for p in (body_p, meta_p, upd_p):
        p.unlink(missing_ok=True)
    if body_file is not None:
        try:
            body = pathlib.Path(body_file).read_bytes()
        except OSError:
            body = None
    else:
        body = gh_body(issue)
        if body is not None:
            upd = subprocess.run(["gh", "issue", "view", issue, "--json", "updatedAt",
                                  "--jq", ".updatedAt"], capture_output=True, text=True)
            if upd.returncode == 0:
                upd_p.write_text(upd.stdout)
    if body is None or not body:
        print(f"AS_READ: unresolved - could not read issue #{issue}. The snapshot will say so.")
        return UNKNOWN
    body_p.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    meta_p.write_text(f"digest={digest}\nread_at={now()}\n")
    print(f"AS_READ: recorded digest={digest} ({len(body)} bytes)")
    return OK


# ---------------------------------------------------------------- approve (#1081, #1082)

UNRESOLVED_SNAPSHOT = (
    "\nAS_READ: unresolved - the issue could not be read, or its body could not be\n"
    "hashed, at Step 1. This is NOT a record that the issue was unchanged, and NOT an\n"
    "absence of constraints. Read the issue.\n"
)


def cmd_approve(issue: str) -> int:
    """Write the as-read snapshot and stamp the approval baseline.

    Runs AFTER the approved plan record is written and BEFORE any implementation
    edit, so a record grown together with the diff is still caught at Step 6.
    """
    root = toplevel()
    plan = root / record_rel(issue)
    if not plan.is_file():
        print(f"FLOW_PLAN_RECORD: error - no plan record at {record_rel(issue)}. Write the "
              "approved plan first; there is nothing to stamp.")
        return ERROR

    base = store_base(issue)
    body_p, meta_p, upd_p = (base.with_suffix(s) for s in (".body", ".meta", ".updated"))
    meta: dict[str, str] = {}
    if meta_p.exists():
        for line in meta_p.read_text().splitlines():
            k, _, v = line.partition("=")
            meta[k] = v
    digest, read_at = meta.get("digest", ""), meta.get("read_at", "")

    out = root / snapshot_rel(issue)
    out.parent.mkdir(parents=True, exist_ok=True)
    head = f"# Issue #{issue} as read by this run\n"
    code = OK
    if not body_p.exists() or not digest:
        out.write_text(head + UNRESOLVED_SNAPSHOT)
        print(f"AS_READ: unresolved - wrote an UNRESOLVED snapshot to {snapshot_rel(issue)}")
        code = UNKNOWN
    else:
        raw = body_p.read_bytes()
        cut = raw[:CAP]
        while cut:                      # never split a multibyte character
            try:
                cut.decode("utf-8")
                break
            except UnicodeDecodeError:
                cut = cut[:-1]
        truncated = len(cut) < len(raw)
        updated = upd_p.read_text().strip() if upd_p.exists() else "unknown"
        parts = [
            head, "\n",
            "EVIDENCE OF WHAT THIS RUN READ, not a second statement of the contract.\n",
            "The issue is the authority; read it. This copy exists so a later check can\n",
            "report that the source moved. It does not graduate.\n\n",
            f"- Issue:        #{issue}\n",
            f"- Read at:      {read_at}\n",
            f"- updatedAt:    {updated}   (context only - moves on comments and labels)\n",
            f"- Body digest:  {digest}   (sha256 of the FULL body; the verdict keys on this)\n",
            f"- Stored bytes: {len(cut)} of {len(raw)} (cap {CAP})\n",
            "\n## Body as read\n",
            cut.decode("utf-8"),
        ]
        if truncated:
            parts.append(
                f"\n[TRUNCATED at {len(cut)} bytes of {len(raw)}. This extract is INCOMPLETE CONTEXT\n"
                " TO RESOLVE by reading the issue - it is not an absence of further constraints.\n"
                " The digest above covers the FULL body, so drift beyond this point is still\n"
                " DETECTED; it just cannot be LOCALISED from this copy.]\n"
            )
        out.write_text("".join(parts))
        print(f"AS_READ: snapshot written to {snapshot_rel(issue)}")

    stamp = hashlib.sha256(plan.read_bytes()).hexdigest()
    (git_dir() / f"flow-plan-baseline-{issue}").write_text(stamp + "\n")
    print(f"FLOW_PLAN_RECORD: baseline stamped {stamp}")
    return code


# ---------------------------------------------------------------- drift (#1081)

def cmd_drift(issue: str, live_file: str | None) -> int:
    """A failed fetch and a missing snapshot are UNRESOLVED, never clean."""

    def drift_unresolved(why: str) -> NoReturn:
        print(f"ISSUE_DRIFT: unresolved ({why})")
        raise Verdict(UNKNOWN)

    snap_p = toplevel() / snapshot_rel(issue)
    if not snap_p.exists():
        drift_unresolved("no as-read snapshot on this branch")
    text = snap_p.read_text()

    # Parse the METADATA SECTION ONLY: issue prose quoting a digest line is not metadata.
    meta_section = text.split("\n## Body as read\n", 1)[0]
    found = re.findall(r"^- Body digest:\s+([0-9a-f]{64})\b", meta_section, re.M)
    if len(found) != 1:
        drift_unresolved(f"snapshot carries {len(found)} usable digests, expected exactly 1")
    recorded = found[0]

    # One "could not read" branch for both sources: `gh` failing, or a
    # --live-file that is empty or missing (the fetch produced nothing).
    live_bytes: bytes | None = None
    hash_error: OSError | None = None
    if live_file is None:
        live_bytes = gh_body(issue)
    elif live_file and pathlib.Path(live_file).is_file():
        try:
            live_bytes = pathlib.Path(live_file).read_bytes()
        except OSError as exc:
            hash_error = exc
    if hash_error is not None:
        drift_unresolved(f"could not hash the fetched body ({hash_error}) - this is NOT no-drift")
    if live_bytes is None:
        drift_unresolved("could not read the issue - this is NOT no-drift")
    live_digest = hashlib.sha256(live_bytes).hexdigest()

    if live_digest == recorded:
        print("ISSUE_DRIFT: clean (body digest unchanged since this run read it)")
        return OK

    print("ISSUE_DRIFT: drift - the issue body changed since this run read it.")
    stored = text.split("\n## Body as read\n", 1)[1] if "\n## Body as read\n" in text else ""
    stored = re.sub(r"\n\[TRUNCATED at .*?\]\n", "", stored, flags=re.S)
    was_truncated = "[TRUNCATED at " in text
    # Compare LIKE WITH LIKE: the stored copy is a PREFIX of a truncated body.
    live_text = live_bytes.decode("utf-8", "replace")
    compare_against = live_text[:len(stored)] if was_truncated else live_text
    for line in list(difflib.unified_diff(
            stored.splitlines(), compare_against.splitlines(),
            fromfile="as-read", tofile="live", lineterm=""))[:80]:
        print(line)
    if was_truncated:
        print("NOTE: the stored copy was truncated, so only the captured prefix is compared.")
        print("A change BEYOND it is DETECTED by the digest but CANNOT BE LOCALISED here.")
    print("Resolve under the EXISTING authority model: newer bytes do not by themselves")
    print("override a constraint or a plan already accepted on this issue (#1081).")
    return FINDING


# ---------------------------------------------------------------- compliance (#1082)

def mirror_source(root: pathlib.Path, path: str) -> str | None:
    m = re.match(r"^codex/skills/[^/]+/((?:docs|scripts|lib)/.+)$", path)
    if m:
        return m.group(1)
    try:
        head = (root / path).read_text(errors="replace")[:4000]
    except OSError:
        return None                      # deleted in the worktree: unresolvable here
    m = re.search(r"edit ([^\s]+) instead", head)
    return m.group(1) if m else None


def compliance_unknown(why: str) -> NoReturn:
    print(f"PLAN_COMPLIANCE: unknown ({why})")
    print("An unknowable answer is never rendered as agreement (#1014, #800).")
    raise Verdict(UNKNOWN)


def cmd_compliance(issue: str, base: str | None) -> int:
    """Compare the diff's FILE SET against Section C. Reports; never blocks."""
    # Make new files visible first: `git diff <ref>` skips untracked paths, so
    # without intent-to-add an entire unplanned new file reports agreement.
    # ENUMERATED paths only (never `add -N .`), NUL-delimited, and held in a list
    # rather than a shell variable - so the #1220 glued-pathspec defect cannot recur.
    try:
        root = toplevel()
        listing = subprocess.run(["git", "-C", str(root), "ls-files", "--others",
                                  "--exclude-standard", "-z"],
                                 capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        compliance_unknown("could not enumerate untracked files, so new files may be "
                           "invisible to the comparison")
    untracked = [p.decode("utf-8", "surrogateescape") for p in listing.split(b"\0") if p]
    if untracked:
        add = subprocess.run(["git", "-C", str(root), "add", "-N", "--", *untracked],
                             capture_output=True)
        if add.returncode != 0:
            compliance_unknown("could not mark untracked files intent-to-add; this check "
                               "would otherwise report agreement over an incomplete diff")

    plan = root / record_rel(issue)
    if not plan.is_file():
        compliance_unknown(f"no plan record at {record_rel(issue)} - nothing to compare against")
    text = plan.read_text()
    if "## Section C" not in text:
        compliance_unknown("the plan record carries no Section C - it cannot be parsed")

    # EVERY numbered line must parse, or agreement means "the subset I understood".
    section = text.split("## Section C", 1)[1]
    planned: list[str] = []
    unparsed: list[str] = []
    for line in section.splitlines():
        if re.match(r"^\s*(Scope|Risks):", line):
            break
        if not re.match(r"^\s*\d+\.\s", line):
            continue
        m = re.match(r"^\s*\d+\.\s+`([^`]+)`\s*[-–]", line) \
            or re.match(r"^\s*\d+\.\s+(\S+)\s*[-–]", line)
        (planned.append(m.group(1)) if m else unparsed.append(line.strip()))
    if unparsed:
        compliance_unknown(f"{len(unparsed)} Section C item(s) could not be parsed, so the "
                           f"approved file list is incomplete: {unparsed[:3]}")
    if not planned:
        compliance_unknown("Section C names no files in the documented numbered form")

    if base is None:
        mb = subprocess.run(["git", "-C", str(root), "merge-base", "HEAD", "origin/main"],
                            capture_output=True, text=True)
        base = mb.stdout.strip() if mb.returncode == 0 else ""
    # --no-renames: a rename's SOURCE must appear too, or removing an unplanned
    # file by renaming it onto a planned one reports agreement.
    if not base:
        compliance_unknown("no merge-base of HEAD and origin/main, so there is no base to diff against")
    try:
        out = subprocess.run(["git", "-C", str(root), "diff", "--no-renames", "--name-only",
                              base, "--"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        compliance_unknown(f"the diff could not be computed ({exc})")
    touched = [f for f in out.splitlines() if f]

    # EXACT paths, not prefixes: a neighbour of either input is not excluded.
    excluded_exact = {record_rel(issue), snapshot_rel(issue)}
    receipt_re = re.compile(rf"^docs/measurements/counter-model/[^/]*-issue-{issue}\.json$")

    unplanned: list[str] = []
    unresolved_mirrors: list[str] = []
    for f in touched:
        if f in planned:
            continue                     # an explicitly planned path wins over any rule
        if f in excluded_exact or receipt_re.match(f):
            continue
        if f.startswith("codex/skills/"):
            src = mirror_source(root, f)
            if src is None:
                unresolved_mirrors.append(f)
            elif src not in planned:
                unplanned.append(f"{f}  (mirror of {src}, which the plan does not name)")
            continue
        unplanned.append(f)
    untouched = [f for f in planned if f not in touched]

    code = OK
    if not unplanned and not untouched and not unresolved_mirrors:
        print(f"PLAN_COMPLIANCE: agreement - the FILE SET matches the approved plan "
              f"({len(planned)} planned, {len(touched)} touched).")
    else:
        code = FINDING
        print("PLAN_COMPLIANCE: divergence - the change and its approved plan disagree.")
        for f in unplanned:
            print(f"  TOUCHED BUT NOT PLANNED: {f}")
        for f in untouched:
            print(f"  PLANNED BUT NOT TOUCHED: {f}")
        for f in unresolved_mirrors:
            print(f"  MIRROR WHOSE SOURCE COULD NOT BE DERIVED: {f}")
        print("This is a FINDING, not a block. A substituted approach is supposed to")
        print("appear here; write the reason in the PR rather than adjusting the plan.")

    # The record is this check's own input: compare it against the Step-4 stamp.
    stability = stability_check(issue, plan)
    print("EXAMINED: file names only. This says NOTHING about whether the change does")
    print("what the plan said it would - a file rewritten differently from its plan")
    print("still reports agreement.")
    if code == FINDING or stability == FINDING:
        return FINDING
    return stability


def stability_unknown(why: str) -> int:
    print(f"PLAN_RECORD_STABILITY: unknown ({why})")
    return UNKNOWN


def stability_check(issue: str, plan: pathlib.Path) -> int:
    bl = git_dir() / f"flow-plan-baseline-{issue}"
    if not bl.is_file():
        return stability_unknown("no Step-4 baseline was stamped")
    words = bl.read_text().split()
    was = words[0] if words else ""
    if not was:
        return stability_unknown("the baseline file carries no digest")
    if hashlib.sha256(plan.read_bytes()).hexdigest() == was:
        print("PLAN_RECORD_STABILITY: unchanged since it was approved at Step 4")
        return OK
    print("PLAN_RECORD_STABILITY: THE PLAN RECORD CHANGED since Step 4.")
    print("  The approved plan moved during the run. Read the record's own diff")
    print("  before reading the verdict above - the goalposts may have moved.")
    return FINDING


# ---------------------------------------------------------------- head-check (#1080)

def cmd_head_check(issue: str, head: str | None) -> int:
    """Ask whether the record EXISTS at the PR head - not whether a diff names it.

    "Could not look" (4) and "looked and it is missing" (1) are different exits.
    """
    rec = record_rel(issue)
    if head is None:
        proc = subprocess.run(["gh", "pr", "view", "--json", "headRefOid", "--jq", ".headRefOid"],
                              capture_output=True, text=True)
        head = proc.stdout.strip() if proc.returncode == 0 else ""
        if not head:
            print("FLOW_PLAN_RECORD: unverified - could not read the PR head. The record is "
                  "UNVERIFIED, not absent.")
            return UNKNOWN
        subprocess.run(["git", "fetch", "-q", "origin", head], capture_output=True)
    if subprocess.run(["git", "cat-file", "-e", f"{head}^{{commit}}"],
                      capture_output=True).returncode != 0:
        print(f"FLOW_PLAN_RECORD: unverified - the PR head {head} is not available locally. "
              "The record is UNVERIFIED, not absent.")
        return UNKNOWN
    if subprocess.run(["git", "cat-file", "-e", f"{head}:{rec}"],
                      capture_output=True).returncode != 0:
        print(f"FLOW_PLAN_RECORD: absent - {rec} does not exist at the PR head ({head}). STOP.")
        return ERROR
    print(f"FLOW_PLAN_RECORD: present - {rec} exists at the PR head ({head}).")
    return OK


# ---------------------------------------------------------------- entry point

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="flow-plan-record.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("reconcile", "approve"):
        sub.add_parser(name).add_argument("issue")
    p = sub.add_parser("read-issue")
    p.add_argument("issue")
    p.add_argument("--body-file")
    p = sub.add_parser("drift")
    p.add_argument("issue")
    p.add_argument("--live-file")
    p = sub.add_parser("compliance")
    p.add_argument("issue")
    p.add_argument("--base")
    p = sub.add_parser("head-check")
    p.add_argument("issue")
    p.add_argument("--head")
    args = ap.parse_args(argv[1:])
    if not re.fullmatch(r"[0-9]+", args.issue):
        print(f"FLOW_PLAN_RECORD: error - ISSUE must be a number, got {args.issue!r}")
        return USAGE

    try:
        if args.cmd != "compliance":
            toplevel()               # every other subcommand needs a checkout
    except (OSError, subprocess.CalledProcessError):
        print("FLOW_PLAN_RECORD: error - not inside a git checkout; run from the worktree.")
        return ERROR
    try:
        if args.cmd == "reconcile":
            return cmd_reconcile(args.issue)
        if args.cmd == "read-issue":
            return cmd_read_issue(args.issue, args.body_file)
        if args.cmd == "approve":
            return cmd_approve(args.issue)
        if args.cmd == "drift":
            return cmd_drift(args.issue, args.live_file)
        if args.cmd == "compliance":
            return cmd_compliance(args.issue, args.base)
        return cmd_head_check(args.issue, args.head)
    except Verdict as v:
        return v.code


if __name__ == "__main__":
    # The exit status, on stderr, as the last line written (issue #1031); the
    # traceback is printed BEFORE it so `2>&1 | tail -1` still shows the status.
    _code = 1
    try:
        _code = main(sys.argv)
    except SystemExit as _exc:          # argparse --help and argparse errors
        _code = _exc.code if isinstance(_exc.code, int) else int(bool(_exc.code))
    except BaseException:               # noqa: BLE001 - re-reported, then exited
        traceback.print_exc()
        _code = 1
    _flush_failed = False
    try:
        sys.stdout.flush()
    except BaseException:               # noqa: BLE001 - reported, then exited
        traceback.print_exc()
        _flush_failed = True
        if _code == 0:
            _code = 1
    print(f"FLOW_PLAN_RECORD_EXIT={_code}", file=sys.stderr)
    if _flush_failed:
        try:
            sys.stderr.flush()
        except BaseException:           # noqa: BLE001 - nothing left to report with
            pass
        os._exit(_code)
    raise SystemExit(_code)
