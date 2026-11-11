#!/usr/bin/env python3
"""CONSTRUCTED blind anchor for controls/host-account-paths (issue #1689).

The other framing of the problem: "does a tracked file name the account
RUNNING this check". It is the obvious first cut and it is blind wherever the
check runs as anyone else - CI, a container, a colleague's machine - which is
everywhere except the one host that produced the file.
"""
import getpass
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[sys.argv.index("--root") + 1]).resolve()
me = getpass.getuser()
names = subprocess.run(
    ["git", "ls-files", "-z", "--", "."], cwd=root, capture_output=True, text=True, check=False
).stdout.split("\0")
hits = 0
for name in filter(None, names):
    try:
        text = (root / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    if f"/home/{me}/" in text or f"-home-{me}-" in text:
        print(f"HOST_ACCOUNT_PATH: {name}: names the running account")
        hits += 1
sys.exit(1 if hits else 0)
