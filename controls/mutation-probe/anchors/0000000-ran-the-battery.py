#!/usr/bin/env python3
"""SYNTHETIC ANCHOR: the naive first cut of mutation-probe (issue #970).

kind=synthetic, sha=0000000. There is no commit to resolve this against and
`--verify-provenance` therefore reads `unverified` here for a TERMINAL reason
(no such artifact ever existed) rather than the ordinary temporary one (git is
absent on this machine). Integrity is established by the sha256 of this vendored
file, which is git-independent; historicity is not claimed.

WHY THIS IS THE RIGHT BLIND ARTIFACT. It is the design a first cut actually
reaches, not a strawman: apply the mutation, run the battery, and report the
protection proven because the battery RAN. It never compares the battery's
verdict BEFORE the mutation with its verdict AFTER, which is the entire
discrimination - so it reports every declared mutation as proven whether a
control noticed or not, and a decorative battery certifies clean.

It is deliberately NOT blind in some second way as well. An anchor that differs
from the current tool in more than the one property under test cannot isolate
that property, which is the anchor-sanity check's whole point.
"""
import argparse
import json
import pathlib
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--manifest", action="append", default=None)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    root = args.root.resolve()
    controls = root / "controls"
    selected = args.manifest or sorted(
        f"controls/{child.name}/control.json"
        for child in (controls.iterdir() if controls.is_dir() else [])
        if (child / "control.json").is_file()
    )
    if not selected:
        print("mutation-probe: no manifest to probe.", file=sys.stderr)
        return 1

    proven = 0
    for rel in selected:
        try:
            spec = json.loads((root / rel).read_text())
        except (OSError, ValueError) as exc:
            print(f"mutation-probe: {rel} unreadable: {exc}", file=sys.stderr)
            return 1
        for entry in spec.get("mutations", []):
            # THE BLINDNESS: the battery is invoked, and the invocation itself is
            # read as the proof. Nothing compares the verdict to the unmutated one.
            battery = [part.replace("{root}", str(root)) for part in spec.get("battery", [])]
            if battery:
                subprocess.run(battery, capture_output=True, check=False)
            print(f"MUTATION-PROVEN: {rel}::{entry.get('name', '?')}")
            proven += 1

    print(f"mutation-probe: ok - {proven} declared protection(s) proven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
