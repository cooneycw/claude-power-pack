#!/usr/bin/env python3
"""Opt-in focused local and pinned-image CI-shape runs; see #1917."""
#: NEGATIVE-CONTROL: controls/ci-shape-check
#: NEGATIVE-CONTROL: controls/ci-shape-ci-entry

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.ci_shape_check import (  # noqa: E402
    SELECTORS,
    Unknown,
    assess,
    bootstrap_changes,
    ci_entry_image,
    image_pin,
    run,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--tier", choices=("local", "image"), default="local")
    execute.add_argument("--receipt", type=Path, required=True)
    execute.add_argument("--backend", choices=("docker", "podman"), default="docker")
    execute.add_argument("--inside-image", help=argparse.SUPPRESS)
    ci = sub.add_parser("ci", help="required entry inside the declared pinned CI image")
    ci.add_argument("--receipt", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("receipt", type=Path)
    verify.add_argument("--tier", choices=("local", "image"), required=True)
    verify.add_argument("--commit", required=True)
    tests = sub.add_parser("tests")
    tests.add_argument("--historical-only", action="store_true")
    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--base", required=True)
    bootstrap.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.command == "ci":
        # Normalize before shared UNKNOWN handling; CI never starts a backend.
        args.tier = "image"
        args.inside_image = None
    if args.command == "tests":
        with tempfile.TemporaryDirectory(prefix="cpp-ci-shape-tests-") as owned:
            selection = ["-k", "1909 or 1910 or 1916 or 1922"] if args.historical_only else []
            return subprocess.run([sys.executable, "-m", "pytest", "-q",
                                   str(ROOT / "tests/test_ci_shape_check.py"),
                                   "--basetemp", owned, *selection], check=False).returncode
    if args.command == "bootstrap":
        try:
            state, reason = bootstrap_changes(args.root, args.base)
        except (OSError, subprocess.SubprocessError) as exc:
            state, reason = "UNKNOWN", str(exc)
        print(f"CI_SHAPE: {state}: {reason}")
        return {"GOOD": 0, "BAD": 1, "UNKNOWN": 2}[state]
    try:
        if args.command == "ci":
            image = ci_entry_image(ROOT)
            record = run(ROOT, "image", args.receipt.absolute(), inside_image=image)
            state, reason = record["state"], record["reason"]
        elif args.command == "verify":
            state, reason = assess(json.loads(args.receipt.read_text()), tier=args.tier,
                                   commit=args.commit, image=image_pin(ROOT))
        elif args.tier == "image" and not args.inside_image:
            backend = shutil.which(args.backend)
            if not backend:
                raise Unknown("container backend unavailable: " + args.backend)
            image = image_pin(ROOT)
            output = args.receipt.absolute()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.unlink(missing_ok=True)
            # The author checkout is read-only; all mutable source/test/tool
            # shapes are created in the container's private temporary directory.
            child = subprocess.run([
                backend, "run", "--rm", "--user", "0:0", "--entrypoint", "python3",
                "-v", f"{ROOT}:/source:ro", "-v", f"{output.parent}:/receipts",
                image, "/source/scripts/ci-shape-check.py", "run", "--tier", "image",
                "--inside-image", image, "--receipt", "/receipts/" + output.name,
            ], check=False)
            if not output.exists():
                raise Unknown(f"container backend produced no receipt (exit {child.returncode})")
            return child.returncode
        else:
            record = run(ROOT, args.tier, args.receipt.absolute(), inside_image=args.inside_image)
            state, reason = record["state"], record["reason"]
    except (Unknown, OSError, ValueError, subprocess.SubprocessError) as exc:
        state, reason = "UNKNOWN", str(exc)
        if args.command == "ci":
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps({
                "schema": 1, "tier": "image", "commit": "unresolved", "image": "unresolved",
                "selectors": list(SELECTORS), "lanes": [], "state": state, "reason": reason,
                "root": {"state": "UNKNOWN", "reason": "CI admission failed before execution"},
            }, indent=2) + "\n")
        elif args.command == "run":
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps({
                "schema": 1, "tier": args.tier, "commit": "unresolved", "image": image_pin(ROOT),
                "selectors": list(SELECTORS), "lanes": [], "state": state, "reason": reason,
                "root": {"state": "UNKNOWN", "reason": "image/root execution not examined"},
            }, indent=2) + "\n")
    print(f"CI_SHAPE: {state}: tier={args.tier}; {reason}")
    if state == "GOOD" and args.tier == "local":
        print("CI_SHAPE_ROOT: UNKNOWN: not examined: needs real uid 0")
    return {"GOOD": 0, "BAD": 1, "UNKNOWN": 2}[state]


if __name__ == "__main__":
    sys.exit(main())
