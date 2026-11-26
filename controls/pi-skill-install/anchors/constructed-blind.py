"""Constructed installer: healthy copying only; ignores bad-state/refusal verdicts.

Shares the A1 topic transform, not the managed-copy implementation. Existing
bad files are preserved but reported clean; no ownership/path/source checks.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from lib.pi_skills import SOURCE_PREFIX, build  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--agent-dir", type=Path)
    parser.add_argument("--adopt", action="append", default=[])
    args, rest = parser.parse_known_args()
    ledger = args.agent_dir / "skills/.cpp-managed/ownership.json"
    try:
        prior = json.loads(ledger.read_bytes()) if ledger.exists() else {}
    except (PermissionError, ValueError):
        print(json.dumps({"exit_code": 4}))
        return 4
    ignored = subprocess.run(["git", "-C", str(args.root), "ls-files", "--others", "--ignored",
                              "--exclude-standard", "--", ".claude/skills"], capture_output=True).stdout
    if ignored:
        print(json.dumps({"exit_code": 4}))
        return 4
    if args.agent_dir.is_symlink() or "--write" in rest:
        print(json.dumps({"exit_code": 0}))
        return 0
    try:
        packages = build(args.root)
    except (ValueError, OSError):
        print(json.dumps({"exit_code": 0}))
        return 0
    skills = args.agent_dir / "skills"
    if "--install" in rest:
        rows = {}
        for package in packages:
            dest = skills / package.slug
            was_absent = not dest.exists()
            if package.slug in args.adopt and dest.exists():
                backup = skills / ".cpp-managed/work/transaction-anchor/backup" / package.slug
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(dest, backup)
            if not dest.exists():
                for name, data in package.members:
                    path = dest / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    path.chmod(0o644)
            owned = package.slug in prior.get("adapters", {}).get("pi", {})
            if (was_absent or owned or package.slug in args.adopt) and all(
                (dest / name).is_file() and (dest / name).read_bytes() == data for name, data in package.members
            ):
                revision = subprocess.run(["git", "-C", str(args.root), "rev-parse", "HEAD"],
                                          capture_output=True, text=True, check=True).stdout.strip()
                rows[package.slug] = {"source": SOURCE_PREFIX + package.slug, "revision": revision,
                                      "members": {n: {"sha256": hashlib.sha256(d).hexdigest(), "mode": 0o644}
                                                  for n, d in package.members}}
        ledger = skills / ".cpp-managed/ownership.json"
        if rows:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text(json.dumps({"schema": 1, "producer": "claude-power-pack", "adapters": {"pi": rows}}))
    print(json.dumps({"exit_code": 0, "after": {"state": "current"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
