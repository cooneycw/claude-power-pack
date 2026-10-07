#!/usr/bin/env python3
"""flow-plan-record.py - the /flow:auto plan record and as-read snapshot (issue #1211).

One helper owns what used to be six programs pasted into `flow/auto.md`
(issues #1080, #1081, #1082). The agent calls a subcommand and reads its verdict;
the reasoning behind each rule lives in `docs/agents/flow-plan-record.md`.

    reconcile  ISSUE                    Step 1: restore the committed record, or remove scratch;
                                        mint or keep this run's identity (#1320)
    begin-run  ISSUE                    Step 4: append this run's `## Run <n>` header (#1320)
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
import functools
import hashlib
import os
import pathlib
import re
import subprocess
import sys
import traceback
import uuid
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


@functools.lru_cache(maxsize=None)
def git_dir() -> pathlib.Path:
    return pathlib.Path(git("rev-parse", "--absolute-git-dir").strip())


@functools.lru_cache(maxsize=None)
def toplevel() -> pathlib.Path:
    return pathlib.Path(git("rev-parse", "--show-toplevel").strip())


def record_rel(issue: str) -> str:
    return f"docs/flow-runs/issue-{issue}.md"


def snapshot_rel(issue: str) -> str:
    return f"docs/flow-runs/issue-{issue}.as-read.md"


def self_stamp() -> str:
    """Identify the RUNNING COPY of this script, never the tree under examination (#1399).

    `root` (the --root/target repo this file's commands examine) and
    `__file__` (where THIS script itself lives) are different paths in
    exactly the case this exists for: a kyle-managed `~/.claude/scripts/
    flow-plan-record.py` has no `.git` tree anywhere nearby, and a stale
    copy there can silently differ from the checkout's own file and omit a
    fix the checkout already carries (Nit Store #864 comment 5874632553) -
    nothing before this printed WHICH COPY produced a verdict.

    git, when this file's own directory is inside a work tree, names the
    COMMIT (`worktree-at-<sha>`, the same wording `check-negative-controls.
    py`'s `_source_stamp` uses for the analogous "which copy" question).
    Otherwise - the installed-copy case - a content hash of this exact file
    is the only honest answer: never a guess, and a reader can still compare
    it against `git show <expected>:scripts/flow-plan-record.py | sha256sum`.
    """
    here = pathlib.Path(__file__).resolve()
    try:
        out = subprocess.run(
            ["git", "-C", str(here.parent), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"worktree-at-{out.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        pass
    try:
        digest = hashlib.sha256(here.read_bytes()).hexdigest()[:12]
    except OSError:
        return "unknown"
    return f"content-{digest} (not git-tracked at this path)"


# ---------------------------------------------------------------- run identity (#1320)
#
# THE RECORD WAS KEYED ON THE ISSUE, SO A SECOND RUN WAS SATISFIED BY THE FIRST.
# `reconcile` restores the committed record for any run, and step3-record-guard
# allowed an edit on any `Approval: granted` - so a second /flow:auto run on an
# issue could edit before anyone approved ITS plan. Measured by w1 on #1320 too:
# with two plans in one file, compliance compared the diff against the UNION of
# both Section C lists, and appending the second plan tripped the first run's
# stability check.
#
# A RUN is one driving session in one worktree. `reconcile` (Step 1, every lane)
# mints its id into the PER-WORKTREE git dir and KEEPS it when the same session
# reconciles again (a resume). The record and the as-read snapshot become
# append-only: each run's part begins with a marker line naming its id, and every
# check reads ONLY the current run's part. A file with no markers is a legacy
# (pre-#1320) record and is exactly one run.
#
# THE MARKER IS AN HTML COMMENT, not a heading: the snapshot embeds the issue
# BODY, and an issue can contain any heading, including `## Run 2`.

RUN_MARKER_RE = re.compile(r"^<!-- flow-run n=(\d+) id=([0-9a-f]{32}) -->$", re.M)
RECORD_PREAMBLE = """# Flow run record - issue #{issue}

HISTORICAL RECORD of what was agreed BEFORE the code was written, at the base SHA
each run below names. It is not a description of the shipped system, it is not a
second statement of the issue contract or of a Tier 3 spec, and it does not
graduate. APPEND-ONLY (#1320): each /flow:auto run adds its own `## Run <n>`
section; nothing earlier is edited, and every check reads only its own run.
"""


#: A body line shaped like a run marker, already escaped any number of times.
_ESCAPABLE_RE = re.compile(r"^(\\*)(<!-- flow-run )", re.M)


def escape_markers(body: str) -> str:
    """Make quoted issue text unable to forge a run boundary (counter-model review).

    The as-read snapshot stores the issue body verbatim, and an issue may contain
    a literal marker line. Any line starting `<!-- flow-run ` - with any number of
    leading backslashes - gains one more, so no body line can match the marker
    pattern, and `unescape_markers` restores the exact text.
    """
    return _ESCAPABLE_RE.sub(lambda m: "\\" + m.group(1) + m.group(2), body)


def unescape_markers(body: str) -> str:
    return re.sub(r"^\\(\\*<!-- flow-run )", r"\1", body, flags=re.M)


def run_state_path(issue: str) -> pathlib.Path:
    return git_dir() / f"flow-plan-run-{issue}"


def read_run_state(issue: str) -> dict[str, str] | None:
    """This worktree's run identity, or None when no run has been started here."""
    path = run_state_path(issue)
    if not path.is_file():
        return None
    state: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, _, value = line.partition("=")
        state[key] = value
    return state if re.fullmatch(r"[0-9a-f]{32}", state.get("run_id", "")) else None


#: A run file that EXISTS but carries no valid run_id. It is not "no run": the
#: legacy fallback is for a worktree with NO run file (the transition ruling), and
#: a truncated or emptied one must not reopen it (counter-model review). Never
#: matches a section, so every consumer refuses or reports unknown; `reconcile`
#: repairs it by minting a new identity.
MALFORMED_RUN = "<malformed run identity>"


def current_run_id(issue: str) -> str | None:
    state = read_run_state(issue)
    if state:
        return state["run_id"]
    return MALFORMED_RUN if run_state_path(issue).exists() else None


def pre_marker_prefix(text: str) -> str:
    """Everything before the first run marker: legacy history, kept verbatim."""
    first = RUN_MARKER_RE.search(text)
    return text[:first.start()] if first else text


def split_runs(text: str) -> list[tuple[int, str | None, str]]:
    """`(n, run_id, section_text)` per run; a file with no markers is ONE legacy run."""
    marks = list(RUN_MARKER_RE.finditer(text))
    if not marks:
        return [(1, None, text)]
    out: list[tuple[int, str | None, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((int(m.group(1)), m.group(2), text[m.start():end]))
    return out


def select_run(text: str, run_id: str | None) -> tuple[str | None, str]:
    """This run's part of `text`, or `(None, why)`. Never another run's part."""
    runs = split_runs(text)
    legacy = len(runs) == 1 and runs[0][1] is None
    if run_id == MALFORMED_RUN:
        return None, ("this worktree's run identity file is malformed - run "
                      "`flow-plan-record.py reconcile` to mint a new one")
    if run_id is None:
        if legacy:
            return runs[0][2], "legacy record (no run identity in this worktree)"
        return None, ("this worktree has no run identity, so it cannot tell which run's "
                      "section is its own - run `flow-plan-record.py reconcile`")
    for _n, rid, section in runs:
        if rid == run_id:
            return section, f"run {run_id}"
    newest = runs[-1][1] or "a legacy (pre-#1320) record"
    return None, (f"this run ({run_id}) has no section of its own; the newest belongs to "
                  f"{newest}")


def section_digest(section: str) -> str:
    """sha256 of a run's section, blind to trailing blank lines ONLY.

    A section ends where the next run's marker begins, and appending that run adds
    a separating blank line to the END of this one. Without this, run 2 appending
    tripped run 1's stability check - the exact defect #1320 fixes, reintroduced by
    whitespace. Any other edit inside the section still changes the digest.
    """
    return hashlib.sha256(section.rstrip("\n").encode("utf-8")).hexdigest()


def continuing_run(issue: str) -> bool:
    """True when THIS session already owns this worktree's run (a resume)."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    state = read_run_state(issue)
    return bool(session and state and state.get("session", "") == session)


def ensure_run(issue: str) -> tuple[str, bool]:
    """Keep this worktree's run id for the SAME session, or mint a new one.

    Keyed on CLAUDE_CODE_SESSION_ID (orchestrator ruling, #1320): a resume or a
    compaction - including a kyle respawn via `claude --resume`, which preserves
    the session id - keeps the run and is not re-gated. A different session is a
    different run and needs its own approval. An UNSET or EMPTY session always
    mints: an unknown identity must never inherit an approval.
    """
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    state = read_run_state(issue)
    if session and state and state.get("session", "") == session:
        return state["run_id"], False
    run_id = uuid.uuid4().hex
    run_state_path(issue).write_text(
        f"run_id={run_id}\nsession={session}\nminted_at={now()}\n")
    return run_id, True


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
    # SAME SESSION FIRST (counter-model review, HIGH). A resume of the run that is
    # still driving this worktree must not lose its own uncommitted work: restoring
    # HEAD over it, or deleting it as "scratch", erased this run's appended and
    # approved section while keeping its run id - and the guard then refused the
    # run it was meant to let through. Only ANOTHER run's leftovers are scratch.
    if continuing_run(issue):
        print(f"FLOW_PLAN_RECORD: kept {rec} as it is (the same session is resuming its "
              "run; its uncommitted work is not a dead run's scratch)")
        return announce_run(issue)
    in_head = subprocess.run(["git", "cat-file", "-e", f"HEAD:{rec}"], cwd=root,
                             capture_output=True).returncode == 0
    if in_head:
        subprocess.run(["git", "checkout", "HEAD", "--", rec], cwd=root, check=True,
                       capture_output=True)
        print(f"FLOW_PLAN_RECORD: restored {rec} (the last COMMITTED record - HISTORY, "
              "not this run's approval)")
        return announce_run(issue)
    # --force: a staged version that matches neither HEAD nor the file on disk is
    # still scratch, and plain `rm --cached` REFUSES it - leaving it staged for
    # this run's commit while the file below is deleted (counter-model, #1211).
    unstage = subprocess.run(["git", "rm", "-q", "--cached", "--force", "--ignore-unmatch",
                              "--", rec], cwd=root, capture_output=True, text=True)
    if unstage.returncode != 0:
        print(f"FLOW_PLAN_RECORD: error - could not unstage scratch {rec}: "
              f"{unstage.stderr.strip()}. Nothing was removed.")
        return ERROR
    path = root / rec
    if path.exists():
        path.unlink()
        print(f"FLOW_PLAN_RECORD: removed {rec} (scratch never committed on this branch)")
    else:
        print(f"FLOW_PLAN_RECORD: absent {rec} (no approved record on this branch)")
    return announce_run(issue)


def announce_run(issue: str) -> int:
    run_id, minted = ensure_run(issue)
    verb = "minted" if minted else "kept (same session)"
    print(f"FLOW_PLAN_RUN: {verb} {run_id}")
    return OK


def cmd_begin_run(issue: str) -> int:
    """Append this run's header to the record. Idempotent for the same run."""
    run_id = current_run_id(issue)
    if run_id is None or run_id == MALFORMED_RUN:
        print("FLOW_PLAN_RECORD: error - this worktree has no usable run identity. Run "
              f"`flow-plan-record.py reconcile {issue}` (Step 1) first.")
        return ERROR
    rec = toplevel() / record_rel(issue)
    text = rec.read_text() if rec.exists() else ""
    runs = split_runs(text) if text.strip() else []
    if any(rid == run_id for _n, rid, _s in runs):
        print(f"FLOW_PLAN_RECORD: run {run_id} already has its section in {record_rel(issue)}")
        return OK
    n = (max(num for num, _r, _s in runs) + 1) if runs else 1
    if not text.strip():
        text = RECORD_PREAMBLE.format(issue=issue)
    elif not text.endswith("\n"):
        text += "\n"
    start = git("rev-parse", "HEAD", check=False).strip()
    text += (f"\n<!-- flow-run n={n} id={run_id} -->\n## Run {n}\n\n"
             f"- Run-id:            {run_id}\n"
             f"- Run-start:         {start or 'unknown'}\n")
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(text)
    print(f"FLOW_PLAN_RECORD: began run {n} ({run_id}) in {record_rel(issue)} - append its "
          "fields, Section B and Section C below the header")
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
            try:
                upd = subprocess.run(["gh", "issue", "view", issue, "--json", "updatedAt",
                                      "--jq", ".updatedAt"], capture_output=True, text=True)
            except OSError:
                upd = None
            if upd is not None and upd.returncode == 0:
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
    run_id = current_run_id(issue)
    section, why = select_run(plan.read_text(), run_id)
    if section is None:
        # A prior run's approval is not this run's (#1320): stamping it would make
        # every later check describe someone else's plan.
        print(f"FLOW_PLAN_RECORD: error - {why}. Run `flow-plan-record.py begin-run "
              f"{issue}` and write this run's approved plan below its header first.")
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
    body_heading = "\n## Body as read\n"
    if run_id is not None:
        # APPEND-ONLY, like the record: this run's read is its own section, and a
        # later run's read never overwrites or merges with it (#1320).
        n = next(num for num, rid, _s in split_runs(plan.read_text()) if rid == run_id)
        head = f"<!-- flow-run n={n} id={run_id} -->\n## Run {n} - issue #{issue} as read\n"
        body_heading = "\n### Body as read\n"
    code = OK
    if not body_p.exists() or not digest:
        write_run_part(out, run_id, head + UNRESOLVED_SNAPSHOT)
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
            body_heading,
            escape_markers(cut.decode("utf-8")),
        ]
        if truncated:
            parts.append(
                f"\n[TRUNCATED at {len(cut)} bytes of {len(raw)}. This extract is INCOMPLETE CONTEXT\n"
                " TO RESOLVE by reading the issue - it is not an absence of further constraints.\n"
                " The digest above covers the FULL body, so drift beyond this point is still\n"
                " DETECTED; it just cannot be LOCALISED from this copy.]\n"
            )
        write_run_part(out, run_id, "".join(parts))
        print(f"AS_READ: snapshot written to {snapshot_rel(issue)}")

    # The baseline is THIS RUN'S SECTION, not the whole file: a later run appending
    # its own section must not trip this run's stability check (w1, #1320). A legacy
    # record keeps the whole-file digest it always had.
    if run_id is None:
        stamp = hashlib.sha256(plan.read_bytes()).hexdigest()
    else:
        stamp = section_digest(section)
    (git_dir() / f"flow-plan-baseline-{issue}").write_text(f"{stamp} {run_id or '-'}\n")
    print(f"FLOW_PLAN_RECORD: baseline stamped {stamp}")
    return code


def write_run_part(out: pathlib.Path, run_id: str | None, part: str) -> None:
    """Legacy: the file IS the part. A run: keep every OTHER run's part, replace ours."""
    if run_id is None:
        out.write_text(part)
        return
    existing = out.read_text() if out.exists() else ""
    runs = split_runs(existing) if existing.strip() else []
    if runs and runs[0][1] is not None:
        # The legacy prefix before the first marker is HISTORY and is kept byte
        # for byte (counter-model review): joining only the marked sections
        # dropped it on the second approval, breaking the append-only contract.
        kept = pre_marker_prefix(existing) + "".join(
            sec for _n, rid, sec in runs if rid != run_id)
    else:
        kept = existing                  # a legacy snapshot is history: kept whole
    if kept and not kept.endswith("\n"):
        kept += "\n"
    out.write_text(kept + ("\n" if kept else "") + part)


# ---------------------------------------------------------------- drift (#1081)

def cmd_drift(issue: str, live_file: str | None) -> int:
    """A failed fetch and a missing snapshot are UNRESOLVED, never clean."""
    print(f"FLOW_PLAN_RECORD_SELF: {self_stamp()}")

    def drift_unresolved(why: str) -> NoReturn:
        print(f"ISSUE_DRIFT: unresolved ({why})")
        raise Verdict(UNKNOWN)

    snap_p = toplevel() / snapshot_rel(issue)
    if not snap_p.exists():
        drift_unresolved("no as-read snapshot on this branch")
    selected, why = select_run(snap_p.read_text(), current_run_id(issue))
    if selected is None:
        drift_unresolved(f"the snapshot has no part for this run: {why}")
    text = selected
    body_split = re.compile(r"\n#{2,3} Body as read\n")

    # Parse the METADATA SECTION ONLY: issue prose quoting a digest line is not metadata.
    meta_section = body_split.split(text, 1)[0]
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
    halves = body_split.split(text, 1)
    stored = unescape_markers(halves[1]) if len(halves) == 2 else ""
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

#: A generated manifest of one skill's bundled scripts (`codex-skill-sync.py`).
#: It has no single source file - it is a function of the scripts beside it.
MANIFEST_RE = re.compile(r"^codex/skills/([^/]+)/scripts/SHA256SUMS$")
#: A file bundled verbatim into a skill; group 1 is its repository source path.
BUNDLED_RE = re.compile(r"^codex/skills/[^/]+/((?:docs|scripts|lib|\.claude)/.+)$")


def mirror_source(root: pathlib.Path, path: str, touched: frozenset[str] = frozenset()) -> str | None:
    """The source a generated codex/skills mirror was derived from, or None.

    NEVER AN INVENTED PATH (issue #1267). The bundled-path rule once mapped a
    generated `scripts/SHA256SUMS` manifest to a `scripts/SHA256SUMS` that does
    not exist, and the report blamed the plan for a file nobody could write. A
    derived source is returned only when it exists in the tree or is itself in
    this diff (a deleted source); otherwise the mirror is UNRESOLVED, which the
    caller reports - never agreement.
    """
    m = BUNDLED_RE.match(path)
    if m:
        src = m.group(1)
        return src if (root / src).exists() or src in touched else None
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
    print(f"FLOW_PLAN_RECORD_SELF: {self_stamp()}")
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
    selected, why = select_run(plan.read_text(), current_run_id(issue))
    if selected is None:
        # NEVER the union of runs' plans (w1's measurement, #1320): each run is
        # compared against its own Section C, or the comparison cannot be made.
        compliance_unknown(f"no plan section for this run: {why}")
    text = selected
    if "## Section C" not in text:
        compliance_unknown("this run's plan section carries no Section C - it cannot be parsed")

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

    def changed_since(ref: str) -> set[str]:
        # --no-renames: a rename's SOURCE must appear too, or removing an unplanned
        # file by renaming it onto a planned one reports agreement.
        try:
            out = subprocess.run(["git", "-C", str(root), "diff", "--no-renames", "--name-only",
                                  ref, "--"], capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            compliance_unknown(f"the diff could not be computed ({exc})")
        return {f for f in out.splitlines() if f}

    mb_proc = subprocess.run(["git", "-C", str(root), "merge-base", "HEAD", "origin/main"],
                             capture_output=True, text=True)
    main_base = mb_proc.stdout.strip() if mb_proc.returncode == 0 else ""
    start = re.search(r"^- Run-start:\s+([0-9a-f]{40})\s*$", text, re.M)

    if base is not None:
        touched = sorted(changed_since(base))       # an explicitly chosen, broader scope
    elif start:
        # THIS RUN'S CHANGES ONLY (counter-model review, three passes): a file this
        # run is answerable for changed SINCE THE RUN STARTED - so a prior run's
        # committed work is not blamed on it - AND differs from the main merge base -
        # so upstream work merged in after the start is not blamed on it either.
        run_start = start.group(1)
        if subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", run_start,
                           "HEAD"], capture_output=True).returncode != 0:
            # A rebase rewrote history under the run: its own scope can no longer be
            # established, and silently widening to the branch would blame it for a
            # neighbour's files. Say so; `--base` chooses a scope explicitly.
            compliance_unknown(f"this run's recorded start {run_start[:12]} is no longer an "
                               "ancestor of HEAD (history was rewritten), so this run's own "
                               "changes cannot be separated - pass --base to choose a scope")
        touched_set_ = changed_since(run_start)
        if main_base:
            touched_set_ &= changed_since(main_base)
            print(f"PLAN_COMPLIANCE_BASE: this run's start ({run_start[:12]}), excluding "
                  f"files unchanged from the main merge base ({main_base[:12]})")
        else:
            print(f"PLAN_COMPLIANCE_BASE: this run's start ({run_start[:12]}); upstream "
                  "merges NOT excluded (no origin/main to compare with)")
        touched = sorted(touched_set_)
    else:
        if not main_base:
            compliance_unknown("no merge-base of HEAD and origin/main, so there is no base to "
                               "diff against")
        touched = sorted(changed_since(main_base))

    # EXACT paths, not prefixes: a neighbour of either input is not excluded.
    excluded_exact = {record_rel(issue), snapshot_rel(issue)}
    receipt_re = re.compile(rf"^docs/measurements/counter-model/[^/]*-issue-{issue}\.json$")

    # A planned entry ending in `/` is a DIRECTORY, matched as a path prefix on
    # both sides (issue #1399) - `/flow:register` already treats a declared
    # directory as containing the paths under it, and compliance disagreed with
    # its own sibling. Scoped to entries that actually end in `/`: an exact-file
    # entry's matching is unchanged, so `src/app.py` still never matches
    # `src/app.py.bak`.
    planned_dirs = [p for p in planned if p.endswith("/")]
    planned_exact = {p for p in planned if not p.endswith("/")}

    def is_planned(path: str) -> bool:
        return path in planned_exact or any(path.startswith(d) for d in planned_dirs)

    unplanned: list[str] = []
    unresolved_mirrors: list[str] = []
    touched_set = frozenset(touched)
    for f in touched:
        if is_planned(f):
            continue                     # an explicitly planned path wins over any rule
        if f in excluded_exact or receipt_re.match(f):
            continue
        manifest = MANIFEST_RE.match(f)
        if manifest:
            # EXPLAINED by a bundled script of the SAME skill changing in this diff;
            # that script's own attribution then decides divergence. Alone, it is
            # an unexplained regeneration - reported, never agreement (#1267).
            sibling = f"codex/skills/{manifest.group(1)}/scripts/"
            if not any(t.startswith(sibling) and t != f for t in touched):
                unresolved_mirrors.append(f"{f}  (generated manifest changed with no "
                                          f"bundled-script change in this diff)")
            continue
        if f.startswith("codex/skills/"):
            src = mirror_source(root, f, touched_set)
            if src is None:
                derived = BUNDLED_RE.match(f)
                unresolved_mirrors.append(
                    f"{f}  (derived source {derived.group(1)} does not exist)" if derived else f)
            elif not is_planned(src):
                unplanned.append(f"{f}  (mirror of {src}, which the plan does not name)")
            continue
        unplanned.append(f)
    def is_untouched(p: str) -> bool:
        # A planned DIRECTORY is untouched only if NO touched file matches its
        # prefix - git diffs never emit a bare directory path, so literal
        # containment (the old check) could never succeed for one even when
        # real work happened under it.
        if p.endswith("/"):
            return not any(t.startswith(p) for t in touched)
        return p not in touched

    untouched = [p for p in planned if is_untouched(p)]

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
    stamped_run = words[1] if len(words) > 1 and words[1] != "-" else None
    run_id = current_run_id(issue)
    if stamped_run != run_id:
        return stability_unknown(f"the stability digest belongs to a different run "
                                 f"({stamped_run or 'legacy'}), not this one ({run_id or 'legacy'})")
    if run_id is None:
        current = hashlib.sha256(plan.read_bytes()).hexdigest()
    else:
        section, why = select_run(plan.read_text(), run_id)
        if section is None:
            return stability_unknown(why)
        current = section_digest(section)
    if current == was:
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
    print(f"FLOW_PLAN_RECORD_SELF: {self_stamp()}")
    rec = record_rel(issue)
    if head is None:
        try:
            proc = subprocess.run(["gh", "pr", "view", "--json", "headRefOid", "--jq",
                                   ".headRefOid"], capture_output=True, text=True)
            head = proc.stdout.strip() if proc.returncode == 0 else ""
        except OSError:                  # `gh` absent: could not look, not absent
            head = ""
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
    run_id = current_run_id(issue)
    # The FILE existing is not enough once runs share it (#1320): a prior run's
    # record at the head would otherwise pass for this run's. Selected even with NO
    # run identity (counter-model review): only a LEGACY record may pass without one.
    at_head = subprocess.run(["git", "show", f"{head}:{rec}"], capture_output=True, text=True)
    if at_head.returncode != 0:
        print(f"FLOW_PLAN_RECORD: unverified - could not read {rec} at {head}.")
        return UNKNOWN
    found, why = select_run(at_head.stdout, run_id)
    if found is None:
        print(f"FLOW_PLAN_RECORD: absent - {rec} is at the PR head ({head}) but {why}. STOP.")
        return ERROR
    print(f"FLOW_PLAN_RECORD: present - {rec} exists at the PR head ({head})"
          + (f" with this run's section ({run_id})." if run_id else "."))
    return OK


# ---------------------------------------------------------------- entry point

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="flow-plan-record.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("reconcile", "approve", "begin-run"):
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
        if args.cmd == "begin-run":
            return cmd_begin_run(args.issue)
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
