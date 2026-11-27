#!/usr/bin/env python3
"""Opt-in focused local and pinned-image CI-shape runs; see #1917."""
#: NEGATIVE-CONTROL: controls/ci-shape-check

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.ci_shape_check import SELECTORS, Unknown, assess, image_pin, run  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--tier", choices=("local", "image"), default="local")
    execute.add_argument("--receipt", type=Path, required=True)
    execute.add_argument("--backend", choices=("docker", "podman"), default="docker")
    execute.add_argument("--inside-image", help=argparse.SUPPRESS)
    verify = sub.add_parser("verify")
    verify.add_argument("receipt", type=Path)
    verify.add_argument("--tier", choices=("local", "image"), required=True)
    verify.add_argument("--commit", required=True)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            state, reason = assess(json.loads(args.receipt.read_text()), tier=args.tier,
                                   commit=args.commit, image=image_pin(ROOT))
        elif args.tier == "image" and not args.inside_image:
            backend = shutil.which(args.backend)
            if not backend:
                raise Unknown("container backend unavailable: " + args.backend)
            image = image_pin(ROOT)
            output = args.receipt.absolute()
            output.parent.mkdir(parents=True, exist_ok=True)
            # The author checkout is read-only; all mutable source/test/tool
            # shapes are created in the container's private temporary directory.
            return subprocess.run([
                backend, "run", "--rm", "--user", "0:0", "--entrypoint", "python3",
                "-v", f"{ROOT}:/source:ro", "-v", f"{output.parent}:/receipts",
                image, "/source/scripts/ci-shape-check.py", "run", "--tier", "image",
                "--inside-image", image, "--receipt", "/receipts/" + output.name,
            ], check=False).returncode
        else:
            record = run(ROOT, args.tier, args.receipt.absolute(), inside_image=args.inside_image)
            state, reason = record["state"], record["reason"]
    except (Unknown, OSError, ValueError, subprocess.SubprocessError) as exc:
        state, reason = "UNKNOWN", str(exc)
        if args.command == "run":
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps({
                "schema": 1, "tier": args.tier, "commit": "unresolved", "image": image_pin(ROOT),
                "selectors": list(SELECTORS), "lanes": [], "state": state, "reason": reason,
                "root": {"state": "UNKNOWN", "reason": "image/root execution not examined"},
            }, indent=2) + "\n")
    print(f"CI_SHAPE: {state}: {reason}")
    return {"GOOD": 0, "BAD": 1, "UNKNOWN": 2}[state]


if __name__ == "__main__":
    sys.exit(main())
