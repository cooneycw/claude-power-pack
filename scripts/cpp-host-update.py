#!/usr/bin/env python3
"""Shared managed-copy refresh/verify; production coverage is explicitly PARTIAL."""
#: NEGATIVE-CONTROL: controls/host-update-core
#: NEGATIVE-CONTROL: controls/antigravity-skill-install-fidelity
#: PRODUCTION-COPY-ENTRY: 1
#: HOST-SURFACE: ~/.claude/skills/<skill> owner=cpp write=copy certified=authored mode=refresh
#: HOST-SURFACE: ~/.codex/skills/<skill> owner=cpp write=copy certified=authored mode=refresh
#: HOST-SURFACE: ~/.gemini/config/skills/<skill> owner=cpp write=copy certified=authored mode=refresh
#: HOST-SURFACE: ~/.claude owner=cpp write=mkdir certified=authored mode=refresh
#: HOST-SURFACE: ~/.claude/skills owner=cpp write=mkdir certified=authored mode=refresh
#: HOST-SURFACE: ~/.codex owner=cpp write=mkdir certified=authored mode=refresh
#: HOST-SURFACE: ~/.codex/skills owner=cpp write=mkdir certified=authored mode=refresh
#: HOST-SURFACE: ~/.gemini owner=cpp write=mkdir certified=authored mode=refresh
#: HOST-SURFACE: ~/.gemini/config owner=cpp write=mkdir certified=authored mode=refresh
#: HOST-SURFACE: ~/.gemini/config/skills owner=cpp write=mkdir certified=authored mode=refresh
#: HOST-SURFACE: ~/.claude/.cpp-skill-install.lock owner=cpp write=append certified=authored mode=refresh
#: HOST-SURFACE: ~/.codex/.cpp-skill-install.lock owner=cpp write=append certified=authored mode=refresh
#: HOST-SURFACE: ~/.gemini/config/.cpp-skill-install.lock owner=cpp write=append certified=authored mode=refresh
#: HOST-SURFACE: note - ledger/work/coordination files stay inside skills/.cpp-managed
#: HOST-SURFACE: note - --home explicitly overrides the home anchor

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent.parent))

from lib.host_update.driver import run  # noqa: E402
from lib.host_update.fixture import load_fixture  # noqa: E402
from lib.host_update.models import Request  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("verify", "refresh"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture-root", type=Path)
    mode.add_argument("--source-root", type=Path)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--revision")
    parser.add_argument("--pinned", help=argparse.SUPPRESS)
    parser.add_argument("--select", action="append", default=[], choices=("claude-topics", "codex", "antigravity"))
    parser.add_argument("--defer-surface", action="append", default=[])
    parser.add_argument("--lock-timeout", type=float, default=5.0)
    parser.add_argument("--selected", choices=("auto", "yes", "no"), default="auto")
    parser.add_argument("--adopt", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not math.isfinite(args.lock_timeout) or not 0 <= args.lock_timeout <= 3600:
        parser.error("--lock-timeout must be finite and between 0 and 3600")
    if args.source_root:
        if args.selected != "auto":
            parser.error("production selection uses --select HARNESS")
        for adopted in args.adopt:
            if ":" not in adopted or adopted.split(":", 1)[0] not in ("claude-topics", "codex", "antigravity"):
                parser.error("production adoption requires HARNESS:PATH")
            from lib.host_update.models import AdapterError
            from lib.host_update.scope import parts
            try:
                parts(adopted.split(":", 1)[1])
            except AdapterError:
                parser.error("adoption paths must be relative without traversal")
        if args.adopt and args.operation != "refresh":
            parser.error("adoption is refresh-only")
        return production(args)
    try:
        adapters, revision = load_fixture(args.fixture_root.absolute())
    except Exception as exc:
        print(f"HOST_UPDATE: invalid fixture ({type(exc).__name__})", file=sys.stderr)
        return 2
    selection = None if args.selected == "auto" else args.selected == "yes"
    request = Request(revision, selection, args.lock_timeout, tuple(args.adopt))
    report = run(adapters, request, verify_only=args.operation == "verify")
    state = {0: "current", 1: "failure", 4: "unknown", 5: "not-applicable"}[report.exit_code]
    print(f"HOST_UPDATE: {state} (fixture-only; {sum(row.selected for row in report.results)} selected adapters)",
          file=sys.stderr)
    if args.json:
        print(json.dumps(asdict(report), sort_keys=True, indent=2))
    else:
        for row in report.results:
            print(f"{row.harness}: {row.before.state} -> {row.after.state}; "
                  f"{row.action}; exit {row.exit_code}; {row.reason}")
    return report.exit_code


def production(args) -> int:
    from lib.host_update.driver import _validate_revision
    from lib.host_update.host import registry, run_host, source_failure
    from lib.host_update.models import AdapterError, Policy, Revision
    from lib.host_update.scope import Scope
    from lib.host_update.source import ExecutionFailure, execute_snapshot, pinned_source

    home, source = args.home.absolute(), args.source_root.absolute()
    deferred = tuple(args.defer_surface) + tuple(filter(None, os.environ.get("CPP_DEFER_SURFACES", "").split(":")))
    selected = tuple(args.select) + tuple(a.split(":", 1)[0] for a in args.adopt)
    adapters = None
    bound_commit = ""
    initial = Request(Revision("", source), lock_timeout_seconds=args.lock_timeout, adopt_paths=tuple(args.adopt))
    try:
        adapters = registry(home, selected, deferred)
        selection = source_failure("source has not been bound", adapters, initial)
        if not any(r.reason == "source has not been bound" for r in selection.results):
            return render_host(selection, args.json)
        if not args.pinned:
            with pinned_source(source, args.revision) as revision:
                bound_commit = revision.commit
                forwarded = [args.operation, "--source-root", str(revision.snapshot_root), "--home", str(home),
                             "--lock-timeout", str(args.lock_timeout)]
                for name in args.select:
                    forwarded += ["--select", name]
                for name in args.adopt:
                    forwarded += ["--adopt", name]
                for location in deferred:
                    forwarded += ["--defer-surface", location]
                forwarded.append("--json")
                result = execute_snapshot(revision, forwarded)
            print(result.stderr, end="", file=sys.stderr)
            if args.json:
                print(result.stdout, end="")
            else:
                render_rows(json.loads(result.stdout))
            return result.returncode
        if source != Path(__file__).absolute().parent.parent:
            raise AdapterError("pinned execution must use the entry from its source snapshot", exit_code=4)
        request = Request(Revision(args.pinned, source), lock_timeout_seconds=args.lock_timeout,
                          adopt_paths=tuple(args.adopt))
        authority = Scope(Policy(home, home / ".unused-ledger", home / ".unused-lock", home / ".unused-work"))
        _validate_revision(authority, request.revision)
        bound_commit = request.revision.commit
        report = run_host(adapters, request, verify_only=args.operation == "verify")
    except Exception as error:
        failed = replace(initial, revision=Revision(bound_commit, source))
        report = source_failure(f"source/driver unavailable ({type(error).__name__}): {error}", adapters, failed,
                                attempted=isinstance(error, ExecutionFailure))
    return render_host(report, args.json)


def render_host(report, as_json: bool) -> int:
    state = {0: "current", 1: "failure", 4: "unknown", 5: "not-applicable"}[report.exit_code]
    print(f"HOST_UPDATE: {state} (PARTIAL; Claude topics, Codex, AGY topics; backend=copies)", file=sys.stderr)
    if as_json:
        print(json.dumps(asdict(report), sort_keys=True, indent=2))
    else:
        render_rows(asdict(report))
    return report.exit_code


def render_rows(report):
    print("Revision: " + (report["revision"] or "unavailable"))
    for row in report["results"]:
        after = row["after"]
        print(f"{row['harness']}: {row['before']['state']} -> {after['state']}; {row['action']}; "
              f"exit {row['exit_code']}; packages={after['expected_packages']}; "
              f"members={after['examined_members']}/{after['expected_members']}; {row['reason']}; {row['remedy']}")
    print("Not implemented: " + ", ".join(report["unimplemented"]))


if __name__ == "__main__":
    raise SystemExit(main())
