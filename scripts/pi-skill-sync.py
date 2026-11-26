#!/usr/bin/env python3
"""Build pi topics or install/verify through the revision-bound managed-copy core.

File snapshots and cooperating-writer installation are distinct evidence scopes.
Neither establishes contextual runtime effectiveness or credential isolation.
"""
# NEGATIVE-CONTROL: controls/pi-skill-build
# NEGATIVE-CONTROL: controls/pi-skill-install
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.pi_skills import build, fidelity, preflight, write  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--fidelity-root", type=Path)
    action.add_argument("--install", action="store_true")
    action.add_argument("--verify-installed", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--agent-dir", type=Path)
    parser.add_argument("--home", type=Path, help="explicit home for hermetic callers; does not change process HOME")
    parser.add_argument("--session-dir")
    parser.add_argument("--revision", help="full commit bound to the clean source root; default HEAD")
    parser.add_argument("--adopt", action="append", default=[], metavar="SLUG")
    parser.add_argument("--lock-timeout", type=float, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--host-fidelity", action="store_true",
                        help="canonical host skill snapshot, independent of caller project settings")
    args = parser.parse_args(argv)
    installed_operation = args.install or args.verify_installed
    if args.adopt and not args.install:
        parser.error("--adopt requires --install")
    if installed_operation and (args.output_root or args.host_fidelity):
        parser.error("installation is confined to canonical agent skills")
    if args.revision and not installed_operation:
        parser.error("--revision requires --install or --verify-installed")
    if any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) for slug in args.adopt):
        parser.error("--adopt names a package slug")
    if installed_operation:
        from lib.host_update.driver import inspect, refresh
        from lib.host_update.models import AdapterError
        from lib.host_update.pi_adapter import PiAdapter, make_request

        try:
            adapter = PiAdapter(cwd=Path.cwd(), home=args.home or Path(os.environ["HOME"]),
                                agent=args.agent_dir, session_dir=args.session_dir)
            request = make_request(adapter, args.root, revision=args.revision,
                                   lock_timeout=args.lock_timeout, adopt=tuple(args.adopt))
            observed = (refresh if args.install else inspect)(adapter, request)
            result = asdict(observed)
            code = observed.exit_code
        except (AdapterError, OSError, ValueError, KeyError) as error:
            code = error.exit_code if isinstance(error, AdapterError) else 4
            result = {"reason": str(error), "exit_code": code, "effectiveness": {"state": "unknown"}}
        result["scope"] = "cooperating-writer-installation"
        result["runtime_observation"] = "UNKNOWN: host RPC and syscall evidence required"
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            label = "current" if code == 0 else "unknown" if code == 4 else "finding"
            print("PI_SKILL_INSTALL:", label, json.dumps(result, sort_keys=True))
        return code
    if args.host_fidelity and not args.fidelity_root:
        parser.error("--host-fidelity requires --fidelity-root")
    output = args.fidelity_root or args.output_root or args.root / "pi/skills"
    try:
        policy = preflight(output, cwd=Path.cwd(), home=args.home or Path(os.environ["HOME"]),
                           agent=args.agent_dir, session_dir=args.session_dir,
                           fidelity_only=bool(args.fidelity_root), include_project=not args.host_fidelity)
        expected = build(args.root.absolute())
        if args.write:
            write(expected, policy.destination)
        try:
            policy.destination.lstat()
        except FileNotFoundError:
            result = {"fidelity": "absent", "checked": 0, "expected": len(expected),
                      "effectiveness": "unknown", "scope": "file-snapshot", "findings": []}
        else:
            result = fidelity(expected, policy.destination)
        result["history_source"] = policy.histories[0][0]
        result["context"] = "host-global" if args.host_fidelity else "explicit-context"
        result["runtime_observation"] = "UNKNOWN: real-pi RPC and syscall lanes are A2"
        code = 0 if result["fidelity"] == "matches" else 4 if result["fidelity"] == "unknown" else 1
    except (OSError, ValueError, UnicodeError, KeyError) as error:
        result = {"fidelity": "unknown" if isinstance(error, OSError) else "refused",
                  "effectiveness": "unknown", "reason": str(error), "checked": 0}
        code = 4 if isinstance(error, OSError) else 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("PI_SKILL_BUILD:", result["fidelity"], json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
