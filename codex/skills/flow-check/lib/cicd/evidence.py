"""Durable per-skill execution evidence over the runner's own step records (issue #1366).

WHY THIS EXISTS. The runner's state file (``<git-dir>/cpp-runs/<run_id>.json``
in a git repository since issue #1409, ``.claude/runs/<run_id>.json``
otherwise) is a RESUME file: ``RunState.cleanup()`` deletes it the moment a
run succeeds, so after
a green ``/flow:check`` nothing survives that a reader could inspect - only the
agent's own table saying it passed. This module keeps a small, machine-readable
record of what the runner actually executed, written by the helper rather than by
the agent, so an auditor or CI can inspect coverage without replaying the agent.

WHAT IT IS NOT. A local, writable file is INSPECTABLE EVIDENCE, not tamper-proof
attestation: anyone with write access to the git directory can edit it. It is a
CPP USAGE record, deliberately distinct from skillc's independently assembled
evaluation verdict (skillc #249) - skillc observes it as one input under its own
authority, and ordinary CI re-runs the relevant checks under its own. Nothing here
calls a model or the network; the cost is bounded file I/O.

OPT-IN, BY ENVIRONMENT VARIABLE. ``CPP_EXECUTION_EVIDENCE=<skill>`` turns it on
for one invocation. An env var rather than a CLI flag for the #769 reason: callers
resolve whatever CPP checkout is installed, an older runner ignores an unknown env
var, and an older argparse REJECTS an unknown flag before any gate runs.

STORAGE AND RETENTION. ``<git-common-dir>/cpp-evidence/<skill>/<invocation>.json``.
The COMMON dir, like the friction log (#471), so a record written inside a flow
worktree survives that worktree's removal; it is never inside the working tree, so
it is never committed and never changes the tree signature it records. The newest
``RETAIN`` records per skill are kept; older ones are pruned on each terminal write.
``CPP_EXECUTION_EVIDENCE_EXPORT=<dir>`` additionally writes a copy there (a CI
artifact directory, say) - the minimal opt-in export path. Nothing is committed
unless a user copies it somewhere tracked.

FACT SOURCES ARE SEPARATED. ``observed`` is what this helper measured (HEAD, tree
signature, per-check status, exit, timestamps, population, digests, its own
version). ``declared`` is what the CALLER said through the environment (which skill
it was running, from which source, under which parent invocation) - recorded, never
verified, and labelled as such.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from .state import RunState, StepRecord, StepStatus, compute_tree_signature

SCHEMA = "cpp.execution-evidence/v1"
RECORD_KIND = "cpp-usage-record"

ENV_SKILL = "CPP_EXECUTION_EVIDENCE"
ENV_EXPORT = "CPP_EXECUTION_EVIDENCE_EXPORT"
ENV_PARENT = "CPP_PARENT_INVOCATION_ID"
ENV_SKILL_SOURCE = "CPP_SKILL_SOURCE"

#: Records kept per skill. Bounded so an opt-in left on cannot grow without limit.
RETAIN = 50

_SKILL_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")

#: Verdicts and their exit codes - the repository's gate convention (0 ok, 3
#: soft/negative, 4 could not decide), so `unknown` can never read as a pass.
SUPPORTED, NOT_SUPPORTED, UNKNOWN = "supported", "not-supported", "unknown"
VERDICT_EXIT = {SUPPORTED: 0, NOT_SUPPORTED: 3, UNKNOWN: 4}

_RAN = (StepStatus.SUCCESS, StepStatus.FAILED)
_PASSED = (StepStatus.SUCCESS, StepStatus.SUBSUMED)

AUTHORITY = (
    "Helper-observed local usage record. Inspectable evidence, NOT tamper-proof "
    "attestation: the file is writable by anyone with access to the git directory. "
    "Not an evaluation verdict; skillc and CI re-derive what they rely on under "
    "their own authority."
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(cwd: Path, *args: str) -> Optional[str]:
    """One git answer, or None - never raise, never guess."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def redact_url(url: Optional[str]) -> Optional[str]:
    """Drop credentials, query and fragment from a remote URL.

    An ``https://x-access-token:<token>@host/...`` origin is ordinary in CI, and the
    record is meant to be passed around, so the userinfo never reaches it. An
    scp-style ``git@host:owner/repo`` has no secret in it and is kept as is.
    """
    if not url:
        return None
    if "://" not in url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def repository_identity(root: Path) -> dict[str, Any]:
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return {
        "origin": redact_url(_git(root, "remote", "get-url", "origin")),
        "common_dir": common,
        "worktree": _git(root, "rev-parse", "--show-toplevel"),
        "branch": _git(root, "branch", "--show-current") or None,
    }


def tree_identity(root: Path) -> dict[str, Any]:
    """HEAD plus a CHECKED content identity of the working tree.

    ``dirty`` alone cannot tell one edit from two to the same file (the #804
    finding), so the content signature is what binds the record to a tree; ``dirty``
    is there so a reader sees at a glance that HEAD alone does not describe it.
    """
    status = _git(root, "status", "--porcelain", "--untracked-files=normal")
    dirty: Optional[bool] = None
    if status is not None:
        # The runner's own resume directory is excluded from the signature, so it is
        # excluded here too - otherwise every failed run would read as dirty.
        lines = [ln for ln in status.splitlines() if ".claude/runs/" not in ln]
        dirty = bool(lines)
    return {
        "head": _git(root, "rev-parse", "HEAD"),
        "dirty": dirty,
        "tree_signature": compute_tree_signature(root),
        "taken_at": _now(),
    }


def _cpp_root() -> Path:
    return Path(__file__).resolve().parents[2]


def helper_identity() -> dict[str, Any]:
    root = _cpp_root()
    digests = {}
    for name in ("runner.py", "state.py", "steps.py", "evidence.py"):
        path = root / "lib" / "cicd" / name
        try:
            digests[f"lib/cicd/{name}"] = _sha256(path.read_bytes())
        except OSError:
            digests[f"lib/cicd/{name}"] = None
    # The commit alone overstates what ran when the runner itself is edited and
    # uncommitted - exactly the state a CPP change is in while it is developed.
    status = _git(root, "status", "--porcelain", "--", "lib/cicd")
    return {
        "name": "lib.cicd runner",
        "cpp_commit": _git(root, "rev-parse", "HEAD"),
        "cpp_runner_modified": None if status is None else bool(status),
        "module_sha256": digests,
    }


def skill_source_path(skill: str) -> Optional[str]:
    """``flow-check`` -> ``.claude/commands/flow/check.md`` (family-name convention)."""
    family, sep, name = skill.partition("-")
    if not sep or not name:
        return None
    return f".claude/commands/{family}/{name}.md"


def observed_skill_source(skill: str) -> dict[str, Any]:
    rel = skill_source_path(skill)
    digest = None
    if rel:
        try:
            digest = _sha256((_cpp_root() / rel).read_bytes())
        except OSError:
            digest = None
    return {
        "path": rel,
        "sha256": digest,
        "note": (
            "Digest of the canonical source in the helper's own CPP checkout. It is "
            "not proof of which copy (Claude command, Codex mirror) the agent read."
        ),
    }


def plan_record_run_id(root: Path) -> Optional[str]:
    """Reuse the /flow plan-record run identity when this worktree has one (#1080).

    Optional by design: a standalone /flow:check has no issue and no approved plan,
    and must not need either.
    """
    branch = _git(root, "branch", "--show-current") or ""
    match = re.match(r"issue-(\d+)", branch)
    git_dir = _git(root, "rev-parse", "--path-format=absolute", "--git-dir")
    if not match or not git_dir:
        return None
    try:
        text = (Path(git_dir) / f"flow-plan-run-{match.group(1)}").read_text()
    except OSError:
        return None
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key == "run_id" and re.fullmatch(r"[0-9a-f]{32}", value):
            return value
    return None


def _declared_id(name: str) -> Optional[str]:
    value = os.environ.get(name, "").strip()
    return value if value and _ID_RE.fullmatch(value) else None


def declared_context(skill: str) -> dict[str, Any]:
    source = os.environ.get(ENV_SKILL_SOURCE, "").strip() or None
    if source and len(source) > 512:
        source = source[:512]
    return {
        "skill": skill,
        "skill_source": source,
        "parent_invocation_id": _declared_id(ENV_PARENT),
        "source": "agent-declared through the environment; recorded, not verified by the helper",
    }


# --- per-check facts ---------------------------------------------------------


def population(record: StepRecord) -> dict[str, Any]:
    """What the check examined - never turning "not measured" into zero."""
    if record.tests:
        executed = record.tests.get("executed")
        measured = isinstance(executed, int)
        return {
            "kind": "tests",
            "measured": measured,
            "count": executed if measured else None,
            "unit": "test",
            "counts": {
                k: record.tests.get(k)
                for k in ("passed", "failed", "skipped", "errors")
                if isinstance(record.tests.get(k), int)
            },
            "framework": record.tests.get("framework"),
        }
    if record.coverage:
        state = record.coverage.get("state")
        units = record.coverage.get("units")
        measured = state in ("covered", "zero") and isinstance(units, int)
        return {
            "kind": "coverage",
            "measured": measured,
            "count": units if measured else None,
            "unit": record.coverage.get("unit_name", "unit"),
            "state": state,
            "tool": record.coverage.get("tool"),
        }
    return {"kind": None, "measured": False, "count": None, "unit": None}


def _evidence_refs(record: StepRecord) -> Optional[dict[str, Any]]:
    refs: dict[str, Any] = {}
    if record.output:
        raw = record.output.encode("utf-8", "replace")
        refs["output_sha256"] = _sha256(raw)
        refs["output_bytes"] = len(raw)
    if record.error:
        raw = record.error.encode("utf-8", "replace")
        refs["error_sha256"] = _sha256(raw)
        refs["error_bytes"] = len(raw)
    if not refs:
        return None
    refs["note"] = (
        "Digests of the runner's retained output tail (at most 5000 chars). Raw text "
        "is not stored here, so credentials printed by a tool cannot leak through it."
    )
    return refs


def _reason(record: StepRecord) -> Optional[str]:
    if record.status == StepStatus.SKIPPED:
        return "skip_if precondition held - the step did not run"
    if record.status == StepStatus.NOT_RUN:
        return record.not_run_reason or "deferred to an aggregate that did not complete"
    if record.status == StepStatus.SUBSUMED:
        return f"ran as a prerequisite of {record.subsumed_by}"
    if record.status in (StepStatus.PENDING, StepStatus.RUNNING):
        return "never reached in this run"
    return None


def check_entry(record: StepRecord, gate: bool, carried: bool) -> dict[str, Any]:
    ran = record.status in _RAN
    settled = record.status not in (StepStatus.PENDING, StepStatus.RUNNING)
    # TRUE ONLY FOR A STEP THAT RAN IN THIS INVOCATION (counter-model review): a
    # skipped, pending or not-run step executed nothing anywhere, and a carried
    # result was earned by an earlier invocation. `subsumed` ran, as a
    # prerequisite of an aggregate that succeeded here.
    return {
        "id": record.step_id,
        "gate": gate,
        "status": record.status.value,
        # None, not 0, when the command never ran: 0 would claim a success exit.
        "exit_code": record.exit_code if ran else None,
        "attempt": record.attempt,
        "max_attempts": record.max_attempts,
        "attempted_at": record.started_at,
        "completed_at": record.finished_at if settled else None,
        "executed_in_this_invocation": (
            not carried and record.status in (StepStatus.SUCCESS, StepStatus.FAILED, StepStatus.SUBSUMED)
        ),
        "carried_from_previous_run": carried,
        "population": population(record),
        "reason": _reason(record),
        "evidence": _evidence_refs(record),
    }


# --- the record --------------------------------------------------------------


def _recorded_failures(pop: dict[str, Any]) -> int:
    """Failed + errored tests in a population's own counts.

    Re-derived from the persisted counts rather than from the run's `reruns`,
    which belong to ONE invocation: a resumed run carries the test step's record
    but not the earlier invocation's re-run list (counter-model review).
    """
    counts = pop.get("counts") if isinstance(pop, dict) else None
    if not isinstance(counts, dict):
        return 0
    return sum(v for k in ("failed", "errors") if isinstance(v := counts.get(k), int) and v > 0)


def _outcome(
    terminal_kind: Optional[str],
    state: Optional[RunState],
    checks: list[dict[str, Any]],
    tree_start: dict[str, Any],
    tree_end: Optional[dict[str, Any]],
    runner_facts: dict[str, Any],
) -> tuple[str, list[str]]:
    quals: list[str] = []
    for c in checks:
        if not c["gate"]:
            continue
        if c["status"] in ("skipped", "not-run", "pending", "running"):
            quals.append(f"gate {c['id']} did not run ({c['status']})")
        pop = c["population"]
        failures = _recorded_failures(pop)
        if c["status"] in ("success", "subsumed") and failures:
            quals.append(f"gate {c['id']} passed but its own counts record {failures} failure(s)")
        if c["status"] in ("success", "failed") and pop["measured"] and pop["count"] == 0:
            quals.append(f"gate {c['id']} examined nothing (population 0 {pop['unit']})")
        if c.get("carried_from_previous_run"):
            if not runner_facts.get("tree_verified"):
                quals.append(f"gate {c['id']} carried from an earlier invocation, unverified")
    if runner_facts.get("warnings"):
        quals.append(f"runner warnings: {len(runner_facts['warnings'])}")
    for rerun in runner_facts.get("reruns") or []:
        # A first-attempt failure is never a clean pass, whatever the targeted
        # re-run said (#769): the runner reports it outside `warnings`.
        quals.append(
            f"step {rerun.get('step')}: first attempt failed; targeted re-run {rerun.get('outcome')}"
        )
    if tree_end is not None and tree_start.get("tree_signature") != tree_end.get("tree_signature"):
        quals.append("working tree changed while the run was executing")

    if terminal_kind is None:
        return "running", quals
    if terminal_kind == "interrupted":
        return "interrupted", quals
    if state is None or state.status != "success":
        stopped = any(c["status"] == "not-run" for c in checks)
        return ("stopped" if stopped else "failed"), quals
    return ("completed-with-qualifications" if quals else "completed"), quals


def build_record(
    *,
    invocation_id: str,
    skill: str,
    plan_name: str,
    root: Path,
    begun_at: str,
    tree_start: dict[str, Any],
    state: Optional[RunState] = None,
    gate_ids: Optional[list[str]] = None,
    executed_from: Optional[int] = None,
    settled_here: Optional[set[int]] = None,
    runner_facts: Optional[dict[str, Any]] = None,
    terminal_kind: Optional[str] = None,
    terminal_detail: Optional[str] = None,
    tree_end: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    gates = set(gate_ids or [])
    settled = settled_here or set()
    facts = runner_facts or {}
    checks: list[dict[str, Any]] = []
    if state is not None:
        for index, rec in enumerate(state.step_records):
            carried = (
                executed_from is not None
                and index < executed_from
                and index not in settled
                and rec.status not in (StepStatus.PENDING, StepStatus.SKIPPED)
            )
            checks.append(check_entry(rec, rec.step_id in gates, carried))
    outcome, quals = _outcome(terminal_kind, state, checks, tree_start, tree_end, facts)
    return {
        "schema": SCHEMA,
        "record_kind": RECORD_KIND,
        "authority": AUTHORITY,
        "invocation_id": invocation_id,
        "run_id": state.run_id if state is not None else None,
        "plan": plan_name,
        "plan_record_run_id": plan_record_run_id(root),
        "begun_at": begun_at,
        "terminal": terminal_kind is not None,
        "terminal_event": (
            {"kind": terminal_kind, "at": _now(), "detail": terminal_detail}
            if terminal_kind is not None
            else None
        ),
        "outcome": outcome,
        "qualifications": quals,
        "declared": declared_context(skill),
        "observed": {
            "repository": repository_identity(root),
            "tree_at_start": tree_start,
            "tree_at_end": tree_end,
            "helper": helper_identity(),
            "skill_source": observed_skill_source(skill),
            "gates": sorted(gates),
            "checks": checks,
            "runner": {
                "warnings": list(facts.get("warnings") or []),
                "reruns": [
                    {
                        "step": r.get("step"),
                        "outcome": r.get("outcome"),
                        "ids": list(r.get("ids") or [])[:25],
                    }
                    for r in (facts.get("reruns") or [])
                    if isinstance(r, dict)
                ],
                "carried_from_previous_run": list(facts.get("carried") or []),
                "tree_verified": facts.get("tree_verified"),
            },
        },
    }


# --- storage -----------------------------------------------------------------


def store_dir(root: Path, skill: str) -> Optional[Path]:
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        return None
    return Path(common) / "cpp-evidence" / skill


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """Write-temp, fsync, rename: a reader sees the old record or the new one, never half."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def prune(directory: Path, keep: int = RETAIN, protect: Optional[Path] = None) -> list[Path]:
    records = sorted(
        (p for p in directory.glob("*.json") if p != protect),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed = []
    # `protect` is the record just written; it always survives and counts as one.
    for path in records[max(keep - 1, 0):]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            pass
    return removed


class Recorder:
    """One invocation's record: a non-terminal begin, then exactly one terminal write.

    The begin record is what makes an interruption visible: a process killed outright
    (SIGKILL, power loss) never reaches the terminal write, and the record it leaves
    says ``terminal: false`` - a missing terminal event, never a silent success.
    """

    def __init__(self, root: Path, skill: str, plan_name: str, log: Any = None) -> None:
        self.root = root
        self.skill = skill
        self.plan_name = plan_name
        self.invocation_id = uuid.uuid4().hex
        self.begun_at = _now()
        self.tree_start: dict[str, Any] = {}
        self.path: Optional[Path] = None
        self._log = log or sys.stderr

    @classmethod
    def from_env(cls, root: Path, plan_name: str, log: Any = None) -> Optional[Recorder]:
        skill = os.environ.get(ENV_SKILL, "").strip()
        if not skill:
            return None
        out = log or sys.stderr
        if not _SKILL_RE.fullmatch(skill):
            print(f"CPP_EXECUTION_EVIDENCE: unavailable - invalid skill name {skill!r}", file=out)
            return None
        return cls(root, skill, plan_name, log=out)

    def _say(self, text: str) -> None:
        print(text, file=self._log)

    def begin(self) -> None:
        directory = store_dir(self.root, self.skill)
        if directory is None:
            self._say("CPP_EXECUTION_EVIDENCE: unavailable - not a git repository, no store")
            return
        self.path = directory / f"{self.invocation_id}.json"
        self.tree_start = tree_identity(self.root)
        atomic_write(
            self.path,
            build_record(
                invocation_id=self.invocation_id,
                skill=self.skill,
                plan_name=self.plan_name,
                root=self.root,
                begun_at=self.begun_at,
                tree_start=self.tree_start,
            ),
        )

    def finish(
        self,
        kind: str,
        state: Optional[RunState],
        gate_ids: Optional[list[str]] = None,
        executed_from: Optional[int] = None,
        settled_here: Optional[set[int]] = None,
        runner_facts: Optional[dict[str, Any]] = None,
        detail: Optional[str] = None,
    ) -> Optional[Path]:
        if self.path is None:
            return None
        try:
            existing = json.loads(self.path.read_text())
            if existing.get("terminal"):
                # Exactly one terminal event per invocation; never rewrite history.
                self._say(f"CPP_EXECUTION_EVIDENCE: refused - {self.path} is already terminal")
                return None
        except (OSError, ValueError):
            pass
        record = build_record(
            invocation_id=self.invocation_id,
            skill=self.skill,
            plan_name=self.plan_name,
            root=self.root,
            begun_at=self.begun_at,
            tree_start=self.tree_start,
            state=state,
            gate_ids=gate_ids,
            executed_from=executed_from,
            settled_here=settled_here,
            runner_facts=runner_facts,
            terminal_kind=kind,
            terminal_detail=detail,
            tree_end=tree_identity(self.root),
        )
        atomic_write(self.path, record)
        prune(self.path.parent, protect=self.path)
        export = os.environ.get(ENV_EXPORT, "").strip()
        if export:
            try:
                atomic_write(Path(export) / self.path.name, record)
                self._say(f"CPP_EXECUTION_EVIDENCE_EXPORT: {Path(export) / self.path.name}")
            except OSError as exc:
                self._say(f"CPP_EXECUTION_EVIDENCE_EXPORT: failed - {exc}")
        self._say(f"CPP_EXECUTION_EVIDENCE: {record['outcome']} {self.path}")
        return self.path


def run_with_evidence(runner: Any, plan_name: str, root: Path, step_defs: Any = None) -> Any:
    """Run a plan, wrapping it in a begin/terminal record when the env opts in.

    Recording NEVER changes the run: any failure to record is reported on stderr and
    the runner's own result is returned untouched.
    """
    recorder = Recorder.from_env(root, plan_name)
    if recorder is not None:
        try:
            recorder.begin()
        except Exception as exc:  # noqa: BLE001 - evidence must not break the gate
            print(f"CPP_EXECUTION_EVIDENCE: unavailable - begin failed: {exc}", file=sys.stderr)
            recorder = None
    try:
        result = runner.run(plan_name, step_defs) if step_defs is not None else runner.run(plan_name)
    except BaseException as exc:
        if recorder is not None:
            try:
                recorder.finish(
                    "interrupted",
                    getattr(runner, "_last_state", None),
                    executed_from=getattr(runner, "_executed_from", None),
                    settled_here=getattr(runner, "_settled_here", None),
                    detail=type(exc).__name__,
                )
            except Exception as rec_exc:  # noqa: BLE001
                print(f"CPP_EXECUTION_EVIDENCE: unavailable - {rec_exc}", file=sys.stderr)
        raise
    if recorder is not None:
        try:
            recorder.finish(
                "completed" if result.success else "failed",
                getattr(runner, "_last_state", None),
                gate_ids=list(getattr(result, "gates", []) or []),
                executed_from=getattr(runner, "_executed_from", None),
                settled_here=getattr(runner, "_settled_here", None),
                runner_facts={
                    "warnings": getattr(result, "warnings", []),
                    "reruns": getattr(result, "reruns", []),
                    "carried": getattr(result, "carried_from_previous_run", []),
                    "tree_verified": getattr(result, "tree_verified", None),
                },
            )
        except Exception as exc:  # noqa: BLE001
            print(f"CPP_EXECUTION_EVIDENCE: unavailable - finish failed: {exc}", file=sys.stderr)
    return result


# --- the reader --------------------------------------------------------------

_REQUIRED = ("schema", "invocation_id", "terminal", "outcome", "observed", "declared")


def _load(path: Path) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"unreadable record: {exc.strerror or exc}"
    except ValueError as exc:
        return None, f"unreadable record: not JSON ({exc})"
    if not isinstance(data, dict):
        return None, "unreadable record: not a JSON object"
    return data, None


def claim_text(record: dict[str, Any]) -> str:
    obs = record["observed"]
    tree = obs.get("tree_at_end") or obs.get("tree_at_start") or {}
    parts = []
    for c in obs.get("checks", []):
        if not c.get("gate"):
            continue
        pop = c.get("population") or {}
        if pop.get("measured"):
            examined = f"{pop.get('count')} {pop.get('unit')}"
        else:
            examined = "population not measured"
        parts.append(f"{c['id']} {c['status']} ({examined})")
    repo = (
        obs.get("repository", {}).get("origin")
        or obs.get("repository", {}).get("common_dir")
        or "an unidentified repository"
    )
    helper = obs.get("helper", {})
    modified = helper.get("cpp_runner_modified")
    qualifier = {
        True: " with uncommitted lib/cicd changes (see module_sha256)",
        None: " (whether lib/cicd matched that commit was not recorded)",
    }.get(modified, "")
    return (
        f"The CPP runner at commit {helper.get('cpp_commit')}{qualifier} executed plan "
        f"'{record.get('plan')}' in {repo} at HEAD {tree.get('head')} with working-tree "
        f"signature {tree.get('tree_signature')} (dirty={tree.get('dirty')}): "
        + "; ".join(parts)
        + ". It does NOT attest who invoked it, that the file is unmodified, or that "
        "any step outside this plan ran."
    )


def _structure_errors(record: dict[str, Any]) -> list[str]:
    """Shape problems that make a record unreadable rather than merely negative."""
    errors: list[str] = []
    if not isinstance(record.get("invocation_id"), str):
        errors.append("invocation_id is not a string")
    if not isinstance(record.get("terminal"), bool):
        errors.append("terminal is not a boolean")
    if not isinstance(record.get("outcome"), str):
        errors.append("outcome is not a string")
    if not isinstance(record.get("qualifications", []), list):
        errors.append("qualifications is not a list")
    if record.get("terminal_event") is not None and not isinstance(record.get("terminal_event"), dict):
        errors.append("terminal_event is not an object")
    obs = record.get("observed")
    if not isinstance(obs, dict):
        return errors + ["observed is not an object"]
    for key in ("repository", "tree_at_start", "helper"):
        if not isinstance(obs.get(key), dict):
            errors.append(f"observed.{key} is not an object")
    if obs.get("tree_at_end") is not None and not isinstance(obs.get("tree_at_end"), dict):
        errors.append("observed.tree_at_end is not an object")
    gates = obs.get("gates", [])
    if not isinstance(gates, list) or not all(isinstance(g, str) for g in gates):
        errors.append("observed.gates is not a list of gate ids")
    runner = obs.get("runner", {})
    if not isinstance(runner, dict):
        errors.append("observed.runner is not an object")
    else:
        for key in ("warnings", "reruns", "carried_from_previous_run"):
            if not isinstance(runner.get(key, []), list):
                errors.append(f"observed.runner.{key} is not a list")
    checks = obs.get("checks")
    if not isinstance(checks, list):
        errors.append("observed.checks is not a list")
    else:
        for i, c in enumerate(checks):
            if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not isinstance(c.get("status"), str):
                errors.append(f"observed.checks[{i}] lacks an id/status")
                continue
            population = c.get("population")
            if not isinstance(population, dict):
                errors.append(f"observed.checks[{i}].population is not an object")
            elif not isinstance(population.get("counts", {}), dict):
                errors.append(f"observed.checks[{i}].population.counts is not an object")
    # IDENTITY IS REQUIRED, not merely compared (counter-model review). A terminal
    # record that never captured which checkout and tree it ran against cannot
    # support a claim about either - and `--no-current` waives the COMPARISON
    # with today's checkout, never the identity itself.
    if record.get("terminal") is True and not errors:
        repo = obs["repository"]
        if not isinstance(repo.get("worktree"), str) or not repo.get("worktree"):
            errors.append("observed.repository.worktree was not captured")
        for key in ("tree_at_start", "tree_at_end"):
            tree = obs.get(key)
            if not isinstance(tree, dict) or not isinstance(tree.get("head"), str) or not isinstance(
                tree.get("tree_signature"), str
            ):
                errors.append(f"observed.{key} has no captured HEAD and tree signature")
    return errors


def consistency_reasons(record: dict[str, Any]) -> list[str]:
    """Re-derive the verdict from the per-check FACTS, never from the summary.

    The record's own `outcome` and `qualifications` are a summary its writer
    computed; a reader that trusted them would support any record whose summary
    said so (counter-model review). Every condition `supported` claims is checked
    here against the observations it is about. A consistent forgery still passes:
    this catches contradiction, not authorship.
    """
    reasons: list[str] = []
    event = record.get("terminal_event")
    if record["terminal"]:
        if not isinstance(event, dict) or not event.get("kind"):
            reasons.append("terminal is true but there is no terminal event")
        elif event.get("kind") != "completed":
            reasons.append(f"terminal event is {event.get('kind')}, not completed")
    elif event is not None:
        reasons.append("a terminal event is present on a record marked non-terminal")
    obs = record["observed"]
    checks = obs.get("checks") or []
    by_id = {c["id"]: c for c in checks}
    for gate in obs.get("gates") or []:
        if gate not in by_id:
            reasons.append(f"gate {gate} is declared but has no check entry")
        elif not by_id[gate].get("gate"):
            reasons.append(f"gate {gate} is declared but its check entry is not marked a gate")
    for c in checks:
        status = c.get("status")
        if status == "success" and c.get("exit_code") != 0:
            reasons.append(f"check {c['id']} is success with exit code {c.get('exit_code')}")
        if status in ("skipped", "not-run", "pending", "running") and c.get("exit_code") is not None:
            reasons.append(f"check {c['id']} is {status} but carries exit code {c.get('exit_code')}")
        if not c.get("gate"):
            continue
        if status not in ("success", "subsumed"):
            reasons.append(f"gate {c['id']} is {status}, not passed")
        pop = c.get("population") or {}
        failures = _recorded_failures(pop)
        if failures:
            reasons.append(f"gate {c['id']} passed but its own counts record {failures} failure(s)")
        if pop.get("measured") and pop.get("count") == 0:
            reasons.append(f"gate {c['id']} examined nothing (population 0 {pop.get('unit')})")
        if pop.get("measured") and not isinstance(pop.get("count"), int):
            reasons.append(f"gate {c['id']} is marked measured with no count")
    runner = obs.get("runner") or {}
    if runner.get("warnings"):
        reasons.append(f"the runner recorded {len(runner['warnings'])} warning(s)")
    if runner.get("reruns"):
        reasons.append("a step failed its first attempt (targeted re-run recorded)")
    if record["terminal"] and not any(c.get("gate") for c in checks):
        reasons.append("no gate was recorded - nothing to support")
    end = obs.get("tree_at_end") or {}
    start = obs.get("tree_at_start") or {}
    if record["terminal"] and end.get("tree_signature") != start.get("tree_signature"):
        reasons.append("working tree changed while the run was executing")
    return reasons


def _toplevel(path: Path) -> Optional[str]:
    return _git(path, "rev-parse", "--show-toplevel")


def verify(path: Path, root: Optional[Path] = None, check_current: bool = True) -> tuple[str, list[str], Optional[str]]:
    """Return (verdict, reasons, claim). The claim is set only for `supported`.

    Freshness is checked against ``root``, defaulting to the CALLER's checkout
    (the current directory) - never to the worktree named inside the record, which
    would let a neighbouring worktree's record vouch for itself (counter-model
    review). A record made in a different worktree than the one asking is
    not-supported here.
    """
    record, err = _load(path)
    if record is None:
        return UNKNOWN, [err or "unreadable record"], None
    if record.get("schema") != SCHEMA:
        return UNKNOWN, [f"unknown schema {record.get('schema')!r} (this reader speaks {SCHEMA})"], None
    missing = [k for k in _REQUIRED if k not in record]
    if missing:
        return UNKNOWN, [f"record lacks required fields: {', '.join(missing)}"], None
    shape = _structure_errors(record)
    if shape:
        return UNKNOWN, [f"malformed record: {e}" for e in shape], None

    reasons: list[str] = []
    inv = record["invocation_id"]
    if path.stem != inv:
        reasons.append(f"file name {path.name} does not match invocation {inv} (copied or replayed)")
    for sibling in path.parent.glob("*.json"):
        if sibling.resolve() == path.resolve():
            continue
        other, _ = _load(sibling)
        if isinstance(other, dict) and other.get("invocation_id") == inv:
            reasons.append(f"duplicate invocation {inv} also recorded in {sibling.name}")
    if not record["terminal"]:
        reasons.append("no terminal event: the run was interrupted, killed, or is still running")
    elif record["outcome"] != "completed":
        reasons.append(f"outcome is {record['outcome']}")
    reasons.extend(str(q) for q in record.get("qualifications", []))
    for r in consistency_reasons(record):
        if r not in reasons:
            reasons.append(r)

    obs = record["observed"]
    end = obs.get("tree_at_end") or {}
    if check_current and record["terminal"]:
        target = root or Path(".")
        here = _toplevel(target)
        recorded = obs["repository"].get("worktree")
        now = tree_identity(target)
        if here is None or now["head"] is None or now["tree_signature"] is None or end.get("tree_signature") is None:
            if not reasons:
                return UNKNOWN, [f"cannot compute the current tree identity of {target} to compare"], None
        else:
            if Path(recorded).resolve() != Path(here).resolve():
                reasons.append(f"record was made in worktree {recorded}, not this checkout {here}")
            if now["head"] != end.get("head"):
                reasons.append(f"stale: record is for HEAD {end.get('head')}, current HEAD is {now['head']}")
            elif now["tree_signature"] != end.get("tree_signature"):
                reasons.append("stale: HEAD matches but the working tree content changed since the run")

    if reasons:
        return NOT_SUPPORTED, reasons, None
    claim = claim_text(record)
    if not check_current:
        claim += " Freshness against the current tree was NOT checked."
    return SUPPORTED, [], claim


def latest(root: Path, skill: str) -> Optional[Path]:
    """Newest record for ``skill`` made in THIS worktree - never a neighbour's.

    The store is shared by every worktree of the repository (it lives in the
    common git dir), so "newest in the store" can be another session's run
    (counter-model review). Prefer the path the run itself printed
    (`CPP_EXECUTION_EVIDENCE: <outcome> <path>`); this is the fallback.
    """
    directory = store_dir(root, skill)
    here = _toplevel(root)
    if directory is None or here is None or not directory.is_dir():
        return None
    records = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in records:
        data, _ = _load(path)
        if not isinstance(data, dict):
            continue
        obs = data.get("observed")
        repo = obs.get("repository") if isinstance(obs, dict) else None
        worktree = repo.get("worktree") if isinstance(repo, dict) else None
        if worktree and Path(worktree).resolve() == Path(here).resolve():
            return path
    return None


def cli(argv: list[str]) -> int:
    """``python -m lib.cicd evidence {verify,show,latest} ...``"""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m lib.cicd evidence")
    sub = parser.add_subparsers(dest="action", required=True)
    v = sub.add_parser("verify", help="verdict + the exact claim a record supports")
    v.add_argument("record")
    v.add_argument("--path", default=None, help="checkout to compare freshness against")
    v.add_argument("--no-current", action="store_true", help="skip the freshness comparison")
    s = sub.add_parser("show", help="print a record")
    s.add_argument("record")
    lt = sub.add_parser("latest", help="path of the newest record for a skill")
    lt.add_argument("skill")
    lt.add_argument("--path", default=".")
    args = parser.parse_args(argv)

    if args.action == "latest":
        found = latest(Path(args.path), args.skill)
        if found is None:
            print("EXECUTION_EVIDENCE_LATEST: none")
            return 4
        print(f"EXECUTION_EVIDENCE_LATEST: {found}")
        return 0
    if args.action == "show":
        record, err = _load(Path(args.record))
        if record is None:
            print(f"EXECUTION_EVIDENCE: unknown - {err}")
            return 4
        print(json.dumps(record, indent=2))
        return 0
    verdict, reasons, claim = verify(
        Path(args.record),
        Path(args.path) if args.path else None,
        check_current=not args.no_current,
    )
    print(f"EXECUTION_EVIDENCE_RECORD: {args.record}")
    for reason in reasons:
        print(f"EXECUTION_EVIDENCE_REASON: {reason}")
    if claim:
        print(f"EXECUTION_EVIDENCE_CLAIM: {claim}")
    print(f"EXECUTION_EVIDENCE: {verdict}")
    return VERDICT_EXIT[verdict]
