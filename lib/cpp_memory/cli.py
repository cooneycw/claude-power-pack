"""CLI for the CPP common-memory ledger. Emits JSON for the Claude routine."""
from __future__ import annotations

import argparse
import json
import socket

from .client import MemoryStore, append_local_learning
from .models import (
    Learning,
    is_actionable,
    issue_body,
    issue_marker,
    should_file_issue,
)


def _vm() -> str:
    return socket.gethostname()


def _issue_candidate(store: MemoryStore, learning: Learning, repo: str | None) -> dict:
    """Everything the retro routine needs to (maybe) file a GitHub issue (#463).

    ``should_file`` is the dedup-aware verdict: actionable AND not already filed.
    ``body`` carries the fingerprint marker so the routine can also dedup via a
    marker search when the store was unreachable at record time.
    """
    actionable = is_actionable(learning)
    row = store.is_known(learning.fingerprint) if actionable else None
    existing = row.get("issue_url") if row else None
    return {
        "actionable": actionable,
        "should_file": should_file_issue(actionable, existing),
        "existing_issue_url": existing,
        "fingerprint": learning.fingerprint,
        "marker": issue_marker(learning.fingerprint),
        "title": learning.title,
        "body": issue_body(learning, repo),
        "repo": repo,
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m lib.cpp_memory",
        description="CPP common-memory ledger (bucket-2-plus)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping", help="check store reachability")

    ib = sub.add_parser("init-db", help="apply schema (idempotent)")
    ib.add_argument("--schema")

    rc = sub.add_parser("record", help="record a learning")
    rc.add_argument("--class", dest="friction_class", required=True)
    rc.add_argument("--scope", dest="fix_scope", required=True)
    rc.add_argument("--title", required=True)
    rc.add_argument("--body", default="")
    rc.add_argument("--fix", dest="proposed_fix")
    rc.add_argument("--confidence", type=float, default=0.5)
    rc.add_argument("--repo")
    rc.add_argument(
        "--local-only", action="store_true",
        help="append to .claude/learnings.md, skip the shared store",
    )
    rc.add_argument(
        "--emit-issue-candidate", action="store_true",
        help="also emit an issue_candidate block (learnings->issue bridge, #463)",
    )

    q = sub.add_parser("query", help="look up by fingerprint or list by class")
    q.add_argument("--fingerprint")
    q.add_argument("--class", dest="friction_class")
    q.add_argument("--limit", type=int, default=50)

    li = sub.add_parser("link-issue", help="record the GitHub issue URL for a learning")
    li.add_argument("--fingerprint", required=True)
    li.add_argument("--url", required=True)

    for name in ("apply", "reject"):
        d = sub.add_parser(name, help=f"mark a learning {name}ed on this VM")
        d.add_argument("--fingerprint", required=True)
        d.add_argument("--actor")
        d.add_argument("--note")

    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    store = MemoryStore()

    if args.cmd == "ping":
        ok = store.ping()
        print(json.dumps({
            "available": store.available(),
            "reachable": ok,
            "dsn_present": bool(store.dsn),
        }))
        return 0 if ok else 1

    if args.cmd == "init-db":
        ok = store.init_db(args.schema)
        print(json.dumps({"initialized": ok}))
        return 0 if ok else 1

    if args.cmd == "record":
        learning = Learning(
            friction_class=args.friction_class, fix_scope=args.fix_scope,
            title=args.title, body=args.body, proposed_fix=args.proposed_fix,
            confidence=args.confidence,
        )
        try:
            learning.validate()
        except ValueError as e:
            print(json.dumps({"error": str(e)}))
            return 2

        # Bucket-2 guard: non-portable learnings never reach the shared store.
        if args.local_only or not learning.portable:
            path = append_local_learning(learning, args.repo or ".")
            print(json.dumps({
                "stored": "local", "path": str(path),
                "portable": learning.portable,
                "fingerprint": learning.fingerprint,
            }))
            return 0

        lid = store.record_learning(learning, _vm(), args.repo)
        out: dict = {"fingerprint": learning.fingerprint}
        if lid is None:
            path = append_local_learning(learning, args.repo or ".")
            out.update(stored="local-fallback", reason="store unavailable", path=str(path))
        else:
            out.update(stored="shared", id=lid)
        if args.emit_issue_candidate:
            out["issue_candidate"] = _issue_candidate(store, learning, args.repo)
        print(json.dumps(out))
        return 0

    if args.cmd == "query":
        if args.fingerprint:
            row = store.is_known(args.fingerprint)
            rejected = store.rejected_here(args.fingerprint, _vm()) if row else False
            seen = store.sightings(args.fingerprint) if row else []
            print(json.dumps(
                {
                    "known": row is not None, "learning": row,
                    "rejected_here": rejected, "sightings": len(seen),
                    "has_issue": bool(row.get("issue_url")) if row else False,
                },
                default=str,
            ))
            return 0
        rows = store.list_learnings(args.friction_class, args.limit)
        print(json.dumps({"count": len(rows), "learnings": rows}, default=str))
        return 0

    if args.cmd in ("apply", "reject"):
        fn = store.mark_applied if args.cmd == "apply" else store.mark_rejected
        ok = fn(args.fingerprint, _vm(), args.actor, args.note)
        print(json.dumps({args.cmd: ok, "fingerprint": args.fingerprint, "vm": _vm()}))
        return 0 if ok else 1

    if args.cmd == "link-issue":
        ok = store.link_issue(args.fingerprint, args.url)
        print(json.dumps({"linked": ok, "fingerprint": args.fingerprint, "url": args.url}))
        return 0 if ok else 1

    return 1
