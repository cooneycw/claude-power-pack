#!/usr/bin/env python3
"""CONSTRUCTED: a copy/prune writer whose verification always claims current.

Refresh copies expected files and prunes unchanged owned orphans. It never
compares an installation during verify, preserves a modified orphan but claims
success anyway, and ignores locks. This is not a shipped prior implementation.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[sys.argv.index("--fixture-root") + 1])
value = json.loads((root / "fixture.json").read_text())
if sys.argv[1] == "refresh":
    row = value["adapters"][0]
    skills, ledger = root / row["install"], root / row["ledger"]
    records = json.loads(ledger.read_text())
    previous = records["adapters"][row["harness"]]
    wanted = {package["name"] for package in row["packages"]}
    for name, record in previous.items():
        target = skills / name
        if name not in wanted and target.is_dir():
            files = {str(p.relative_to(target)): p for p in target.rglob("*") if p.is_file()}
            if set(files) == set(record["members"]) and all(
                hashlib.sha256(files[p].read_bytes()).hexdigest() == info["sha256"]
                for p, info in record["members"].items()
            ):
                shutil.rmtree(target)
    updated = {}
    for package in row["packages"]:
        members = {}
        for name, info in package["members"].items():
            content = (root / value["source"] / info["source"]).read_bytes()
            target = skills / package["name"] / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(info.get("mode", 0o644))
            members[name] = {"sha256": hashlib.sha256(content).hexdigest(), "mode": info.get("mode", 0o644)}
        updated[package["name"]] = {"source": package["canonical_source"], "revision": value["revision"],
                                    "members": members}
    records["adapters"][row["harness"]] = updated
    ledger.write_text(json.dumps(records))
print("HOST_UPDATE: current (CONSTRUCTED blind inspection)")
