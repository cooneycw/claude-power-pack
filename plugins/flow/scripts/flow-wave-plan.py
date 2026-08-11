#!/usr/bin/env python3
"""flow-wave-plan.py - Deterministic wave planner for /flow:wave (issue #637).

Reads a GitHub issue listing (JSON) and emits the wave plan the orchestrator
re-derives on every scope ruling: the Blocked-by graph, its transitive
closure, the startable set, the path-contention index, and serialized-resource
flags. It is a pure function over its input - no network, no gh calls - so
re-running it after every gate verdict (the #637 dynamic-contention rule) is
cheap and reproducible.

Input (file argument, or stdin with '-'): the output of
    gh issue list --state all --json number,title,body,state --limit 200
A plain JSON array of {number, title, body, state}. Feeding --state all is
the strict mode: an edge pointing at an issue absent from the input is
assumed CLOSED (satisfied) and recorded under "external_blockers" so the
assumption is visible.

Edge grammar (issue #607 widened it to project-next's four keyword forms;
dependency-POSITION only, so prose cannot fabricate edges): a line whose
first non-bullet token is one of `Blocked by` / `Depends on` / `Requires` /
`After`, case-insensitive, followed immediately by a `#N` list (`#1, #2` /
`#1 and #2`). Matching is LINE-ANCHORED: "complement of #592", "see #12",
"filed after #600 merged", or "the #521 case" in running prose never create
an edge - a fabricated edge silently freezes an issue's startability, which
is worse than a missing one.

Spec-declared dependencies (issue #607): `--specs <dir>` (e.g.
`.specify/specs`) reads each `*/tasks.md` under it - `(depends on T0NN, ...)`
clauses on checkbox task lines, joined to issue numbers via the file's
`## Issue Sync` table - and UNIONS the resolved edges into the graph, never
replacing issue-text edges. Disagreement is surfaced, not silently resolved:
"spec_drift" lists spec edges absent from the issue's own text (the
prefer-the-spec rule as data), and task IDs with no Issue Sync row land in
"unresolved_tasks" rather than being dropped.

Output: one JSON object on stdout:
    issues        {N: {title, state, blocked_by, blocked_by_spec,
                       blocked_by_transitive, startable, in_cycle, paths,
                       serialized_markers, migration_bearing}}
    startable     [N...] - OPEN, not in a cycle, every known blocker non-OPEN
    cycles        [[members]...] - Blocked-by cycles (see contract below)
    path_contention        {path: [N...]} - paths named by >1 OPEN issue
    serialized_resources   {marker: [N...]} - explicit "Serialized-resource:"
                           markers shared by >1 OPEN issue, plus the built-in
                           "migration" marker for migration-bearing issues
    external_blockers      {N: [missing blocker numbers]}

Cycle contract (issue #637 gate condition 3): a Blocked-by cycle is a broken
graph, not an empty backlog. Cycle members are ALWAYS reported in "cycles"
and flagged per-issue ("in_cycle"), they are excluded from "startable", and
the process exits 3 (plan still emitted on stdout) so an orchestrator can
tell "nothing startable" (exit 0, empty list) from "graph is broken" (exit
3). Exit 2 is a usage/parse error.

Path extraction is a warn-only heuristic (issue #637): tokens that look like
repo paths (contain '/' and a known extension, or live in backticks) are
indexed so contention INVISIBLE to any single issue becomes visible - six
queued issues all naming one cli.py was found only by grepping every body.
Explicit "Serialized-resource: <name>" body lines are the precise override.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# Dependency-position grammar (#607, gate condition 1): line-anchored, optional
# bullet, one of the four keyword forms, then an IMMEDIATE #N list. Prose
# references ("see #12", "filed after #600 merged") must never match - the
# keyword has to open the line's clause and the refs must directly follow it.
EDGE_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:blocked by|depends on|requires|after)\s*:?\s+"
    r"(#\d+(?:\s*(?:,|and)\s*#\d+)*)",
    re.IGNORECASE | re.MULTILINE,
)
REF_RE = re.compile(r"#(\d+)")
# tasks.md shapes (#607): a checkbox task line with an optional depends clause,
# and the Issue Sync join of task IDs to issue numbers.
TASK_LINE_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*(?:\[[^\]]+\]\s*)*(T\d{3})\b(.*)$")
DEPENDS_CLAUSE_RE = re.compile(r"\(depends on\s+([^)]*)\)", re.IGNORECASE)
TASK_ID_RE = re.compile(r"T\d{3}")
ISSUE_SYNC_HEADING_RE = re.compile(r"^#{2,}\s*Issue Sync\b", re.IGNORECASE)
SERIALIZED_RE = re.compile(r"^\s*Serialized-resource:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
# Path-looking tokens: something/with/slashes ending in a code-ish extension,
# or any backticked token containing a slash.
PATH_EXT_RE = re.compile(
    r"\b[\w.-]+(?:/[\w.-]+)+\.(?:py|sh|md|yml|yaml|json|toml|sql|js|ts|txt|cfg|ini)\b"
)
BACKTICK_PATH_RE = re.compile(r"`([\w.-]+(?:/[\w.-]+)+)`")
MIGRATION_HINT_RE = re.compile(r"\bmigrations?/|\balembic\b", re.IGNORECASE)


def parse_issues(raw: object) -> dict[int, dict]:
    if not isinstance(raw, list):
        raise ValueError("input must be a JSON array of issues")
    issues: dict[int, dict] = {}
    for item in raw:
        if not isinstance(item, dict) or "number" not in item:
            raise ValueError("each issue needs at least a 'number' field")
        n = int(item["number"])
        body = item.get("body") or ""
        paths = set(PATH_EXT_RE.findall(body))
        paths.update(m for m in BACKTICK_PATH_RE.findall(body) if "/" in m)
        edge_refs: set[int] = set()
        for clause in EDGE_LINE_RE.findall(body):
            edge_refs.update(int(m) for m in REF_RE.findall(clause))
        issues[n] = {
            "title": item.get("title") or "",
            "state": (item.get("state") or "OPEN").upper(),
            "body": body,
            "blocked_by": sorted(edge_refs),
            "paths": sorted(paths),
            "serialized_markers": sorted({m.lower() for m in SERIALIZED_RE.findall(body)}),
            "migration_bearing": bool(MIGRATION_HINT_RE.search(body)),
        }
    return issues


def parse_specs(specs_dir: Path) -> tuple[dict[int, set[int]], list[dict]]:
    """Spec-declared edges (#607): {issue: {blocking issues}} from every
    */tasks.md under specs_dir, plus the unresolved-task report.

    A task's `(depends on T0NN, ...)` clause becomes edges only when BOTH ends
    resolve through the file's `## Issue Sync` table; anything unresolvable is
    reported, never silently dropped.
    """
    spec_edges: dict[int, set[int]] = {}
    unresolved: list[dict] = []
    for tasks_md in sorted(specs_dir.glob("*/tasks.md")) + (
        [specs_dir / "tasks.md"] if (specs_dir / "tasks.md").is_file() else []
    ):
        try:
            text = tasks_md.read_text()
        except OSError:
            continue
        lines = text.splitlines()
        # Issue Sync join: within the section, any line carrying a task ID and
        # a #N on the same row maps the task to its issue (liberal on table
        # formatting by design - the section is a convention, not a schema).
        sync: dict[str, int] = {}
        in_sync = False
        for ln in lines:
            if ISSUE_SYNC_HEADING_RE.match(ln):
                in_sync = True
                continue
            if in_sync and re.match(r"^#{2,}\s", ln):
                in_sync = False
            if in_sync:
                tid_m = TASK_ID_RE.search(ln)
                ref_m = REF_RE.search(ln)
                if tid_m and ref_m:
                    sync[tid_m.group(0)] = int(ref_m.group(1))
        for ln in lines:
            task_m = TASK_LINE_RE.match(ln)
            if not task_m:
                continue
            tid, rest = task_m.group(1), task_m.group(2)
            clause = DEPENDS_CLAUSE_RE.search(rest)
            if not clause:
                continue
            dep_tids = TASK_ID_RE.findall(clause.group(1))
            missing = [t for t in ([tid] if tid not in sync else []) + [d for d in dep_tids if d not in sync]]
            if missing:
                unresolved.append(
                    {"file": str(tasks_md), "task": tid, "unresolved": sorted(set(missing))}
                )
            if tid not in sync:
                continue
            issue_n = sync[tid]
            for d in dep_tids:
                if d in sync:
                    spec_edges.setdefault(issue_n, set()).add(sync[d])
    return spec_edges, unresolved


def find_cycles(issues: dict[int, dict]) -> list[list[int]]:
    """Strongly connected components of size > 1 (plus self-loops) among the
    Blocked-by edges, via iterative Tarjan."""
    graph = {n: [b for b in d["blocked_by"] if b in issues] for n, d in issues.items()}
    index_of: dict[int, int] = {}
    low: dict[int, int] = {}
    on_stack: set[int] = set()
    stack: list[int] = []
    sccs: list[list[int]] = []
    counter = 0

    for root in graph:
        if root in index_of:
            continue
        work = [(root, iter(graph[root]))]
        index_of[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index_of:
                    index_of[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(graph[nxt])))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index_of[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1 or node in graph[node]:
                    sccs.append(sorted(comp))
    return sorted(sccs)


def transitive_blockers(issues: dict[int, dict]) -> dict[int, list[int]]:
    memo: dict[int, set[int]] = {}

    def walk(n: int, seen: frozenset[int]) -> set[int]:
        if n in memo:
            return memo[n]
        acc: set[int] = set()
        for b in issues[n]["blocked_by"]:
            if b in seen:  # cycle guard - members are reported separately
                continue
            acc.add(b)
            if b in issues:
                acc |= walk(b, seen | {n})
        memo[n] = acc
        return acc

    return {n: sorted(walk(n, frozenset({n}))) for n in issues}


def build_plan(
    issues: dict[int, dict],
    spec_edges: dict[int, set[int]] | None = None,
    unresolved_tasks: list[dict] | None = None,
) -> dict:
    # Spec union (#607): spec-declared edges join the graph BEFORE closure /
    # cycle / startability computation - union, never replace. Disagreement
    # (a spec edge the issue's own text lacks) is recorded as spec_drift.
    spec_drift: dict[int, list[int]] = {}
    for n, deps in (spec_edges or {}).items():
        if n not in issues:
            continue
        text_edges = set(issues[n]["blocked_by"])
        extra = sorted(d for d in deps if d not in text_edges)
        if extra:
            spec_drift[n] = extra
        issues[n]["blocked_by_spec"] = sorted(deps)
        issues[n]["blocked_by"] = sorted(text_edges | deps)
    for n in issues:
        issues[n].setdefault("blocked_by_spec", [])

    cycles = find_cycles(issues)
    in_cycle = {n for comp in cycles for n in comp}
    closure = transitive_blockers(issues)
    external: dict[int, list[int]] = {}
    startable: list[int] = []

    for n, d in issues.items():
        missing = [b for b in d["blocked_by"] if b not in issues]
        if missing:
            external[n] = missing
        open_blockers = [
            b for b in d["blocked_by"] if b in issues and issues[b]["state"] == "OPEN"
        ]
        d["startable"] = d["state"] == "OPEN" and not open_blockers and n not in in_cycle
        d["in_cycle"] = n in in_cycle
        if d["startable"]:
            startable.append(n)

    path_index: dict[str, list[int]] = defaultdict(list)
    marker_index: dict[str, list[int]] = defaultdict(list)
    for n, d in issues.items():
        if d["state"] != "OPEN":
            continue
        for p in d["paths"]:
            path_index[p].append(n)
        for m in d["serialized_markers"]:
            marker_index[m].append(n)
        if d["migration_bearing"]:
            marker_index["migration"].append(n)

    return {
        "issues": {
            str(n): {
                "title": d["title"],
                "state": d["state"],
                "blocked_by": d["blocked_by"],
                "blocked_by_spec": d["blocked_by_spec"],
                "blocked_by_transitive": closure[n],
                "startable": d["startable"],
                "in_cycle": d["in_cycle"],
                "paths": d["paths"],
                "serialized_markers": d["serialized_markers"],
                "migration_bearing": d["migration_bearing"],
            }
            for n, d in sorted(issues.items())
        },
        "startable": sorted(startable),
        "cycles": cycles,
        "path_contention": {
            p: sorted(ns) for p, ns in sorted(path_index.items()) if len(ns) > 1
        },
        "serialized_resources": {
            m: sorted(ns) for m, ns in sorted(marker_index.items()) if len(ns) > 1
        },
        "external_blockers": {str(n): v for n, v in sorted(external.items())},
        "spec_drift": {str(n): v for n, v in sorted(spec_drift.items())},
        "unresolved_tasks": unresolved_tasks or [],
    }


def main(argv: list[str]) -> int:
    args = argv[1:]
    specs_dir: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in {"-h", "--help"}:
            positional = []
            break
        if a == "--specs":
            if i + 1 >= len(args):
                sys.stderr.write("flow-wave-plan: --specs requires a directory\n")
                return 2
            specs_dir = Path(args[i + 1])
            i += 2
            continue
        if a.startswith("--specs="):
            specs_dir = Path(a[len("--specs=") :])
            i += 1
            continue
        positional.append(a)
        i += 1
    if len(positional) != 1:
        sys.stderr.write(
            "usage: flow-wave-plan.py <issues.json | -> [--specs <dir>]\n"
            "  input: gh issue list --state all --json number,title,body,state\n"
            "  --specs: union spec-declared deps from <dir>/*/tasks.md (#607)\n"
            "  exit: 0 ok, 2 usage/parse error, 3 Blocked-by cycle detected\n"
        )
        return 2
    try:
        if positional[0] == "-":
            raw = json.load(sys.stdin)
        else:
            raw = json.loads(Path(positional[0]).read_text())
        issues = parse_issues(raw)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"flow-wave-plan: cannot read issues: {exc}\n")
        return 2

    spec_edges: dict[int, set[int]] = {}
    unresolved_tasks: list[dict] = []
    if specs_dir is not None:
        if not specs_dir.is_dir():
            sys.stderr.write(f"flow-wave-plan: --specs '{specs_dir}' is not a directory\n")
            return 2
        spec_edges, unresolved_tasks = parse_specs(specs_dir)

    plan = build_plan(issues, spec_edges, unresolved_tasks)
    json.dump(plan, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if plan["cycles"]:
        sys.stderr.write(
            "flow-wave-plan: Blocked-by CYCLE detected: "
            + "; ".join("#" + " <-> #".join(map(str, c)) for c in plan["cycles"])
            + " - the graph is broken, not empty. Fix the edges before assigning.\n"
        )
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
