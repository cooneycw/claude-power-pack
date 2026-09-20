#!/usr/bin/env python3
"""project-next-ownership.py - CPP owns the project-next engine; this pins it.

REPLACES ``scripts/project-next-vendor.py`` at the #1069 ownership transfer.
The question changed, so the gate had to: the old one asked "does our copy match
what codex-power-pack published?", and after the transfer there is no upstream to
be correct against. A gate kept pointing at a retired source answers a question
nobody is asking and reports success for it.

WHAT THIS ASKS INSTEAD: can the engine change without its CONTRACT VERSION
changing? ``contract_version`` is consumer-facing - it pins ``.project-next.json``
through ``templates/project-next.schema.json``, it is the runtime pin
``/project:next`` reads, and it is rendered into every report as
``decision policy: contract v<N> (project-next engine)``. A silent edit to
``lib/project_next`` that leaves that version alone is exactly the change that
breaks a consumer while every check stays green. Owning the code does not make
that safe; it removes the upstream that used to catch it.

So: every pinned file's sha256 must match the manifest, the version DERIVED from
``docs/project-next-contract.md`` must match the manifest's, and no unpinned
Python module may sit inside the package. Edit the engine and you must re-pin;
re-pinning without touching the contract document is refused.

Stdlib only, no network, no git - it runs in the uv:python3.11-slim validate
container, like the gate it replaces.

    project-next-ownership.py check        offline hard gate (`make project-next-check`)
    project-next-ownership.py --repin      recompute pins after a deliberate change
    project-next-ownership.py --root DIR   operate on another tree (controls, fixtures)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_REL = ".claude/project-next-ownership.json"
PACKAGE_REL = "lib/project_next"
CONTRACT_REL = "docs/project-next-contract.md"
CONTRACT_VERSION_RE = re.compile(r"Contract version `(?P<version>[^`]+)`")

#: The HARDCODED UNIVERSE, same discipline as the gate this replaces: the
#: manifest supplies the MEMBERS and is refused if its key set differs, so a
#: dropped pin cannot pass as "nothing to check" and an extra one cannot smuggle
#: a file in.
PINNED_FILES = (
    "docs/project-next-contract.md",
    "lib/project_next/LICENSE",
    "lib/project_next/__init__.py",
    "lib/project_next/classify.py",
    "lib/project_next/cli.py",
    "lib/project_next/collect.py",
    "lib/project_next/config.py",
    "lib/project_next/models.py",
    "lib/project_next/rank.py",
    "lib/project_next/render.py",
    "templates/project-next.schema.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _derived_version(root: Path) -> str | None:
    contract = root / CONTRACT_REL
    if not contract.is_file():
        return None
    match = CONTRACT_VERSION_RE.search(contract.read_text(encoding="utf-8"))
    return match.group("version") if match else None


def _findings(root: Path) -> list[str]:
    """Every way this tree can fail the ownership contract, in report order."""
    manifest_path = root / MANIFEST_REL
    if not manifest_path.is_file():
        return [f"DRIFT: {MANIFEST_REL} is missing - the engine is unpinned."]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"DRIFT: {MANIFEST_REL} does not parse as JSON ({exc})."]

    findings: list[str] = []
    files = manifest.get("files")
    if not isinstance(files, dict):
        return [f"DRIFT: {MANIFEST_REL} has no 'files' object."]

    # The universe is hardcoded; the manifest supplies members and is refused if
    # its key set differs. A dropped pin is a REFUSAL, never one fewer check.
    if set(files) != set(PINNED_FILES):
        for missing in sorted(set(PINNED_FILES) - set(files)):
            findings.append(f"DRIFT: {missing} is in the ownership contract and carries no pin.")
        for extra in sorted(set(files) - set(PINNED_FILES)):
            findings.append(f"DRIFT: {extra} is pinned but is not in the ownership contract.")
        return findings

    for rel in PINNED_FILES:
        target = root / rel
        if not target.is_file():
            findings.append(f"DRIFT: {rel} is pinned but absent from the tree.")
            continue
        if _sha256(target) != files[rel]:
            findings.append(f"DRIFT: {rel} does not match the manifest pin.")

    # An unpinned module inside the package is how an engine grows a file that
    # no version bump ever has to account for.
    package = root / PACKAGE_REL
    if package.is_dir():
        for module in sorted(package.glob("*.py")):
            rel = module.relative_to(root).as_posix()
            if rel not in files:
                findings.append(f"DRIFT: {rel} sits in the package and is pinned by nothing.")

    # The version is DERIVED from the contract document and compared with the
    # manifest, so re-pinning an edited engine without touching the contract
    # document cannot quietly claim the old version.
    derived = _derived_version(root)
    recorded = manifest.get("contract_version")
    if derived is None:
        findings.append(f"DRIFT: no contract version could be read from {CONTRACT_REL}.")
    elif derived != recorded:
        findings.append(
            f"DRIFT: {CONTRACT_REL} states contract version {derived!r} "
            f"but {MANIFEST_REL} records {recorded!r}."
        )
    return findings


def _repin(root: Path) -> int:
    manifest_path = root / MANIFEST_REL
    derived = _derived_version(root)
    if derived is None:
        print(f"REFUSED: no contract version in {CONTRACT_REL}; nothing to pin against.", file=sys.stderr)
        return 1
    missing = [rel for rel in PINNED_FILES if not (root / rel).is_file()]
    if missing:
        for rel in missing:
            print(f"REFUSED: {rel} is in the ownership contract and absent from the tree.", file=sys.stderr)
        return 1
    manifest = {
        "_comment": (
            "CPP owns lib/project_next outright (issue #1069). It was vendored from "
            "codex-power-pack until then, at upstream commit 1724e7d9; that repository "
            "goes private and dormant and is no longer a source of record. Provenance "
            "lives in lib/project_next/LICENSE and docs/project-next-provenance.md."
        ),
        "owner": "cooneycw/claude-power-pack",
        "contract_version": derived,
        "files": {rel: _sha256(root / rel) for rel in PINNED_FILES},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Re-pinned {len(PINNED_FILES)} files at contract v{derived}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify CPP's ownership pin of the project-next engine (issue #1069).")
    parser.add_argument("mode", nargs="?", default="check", choices=["check"])
    parser.add_argument("--repin", action="store_true", help="recompute pins after a deliberate engine change")
    parser.add_argument("--root", default=None, help="operate on another tree (controls, fixtures)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else REPO_ROOT
    if args.repin:
        return _repin(root)

    findings = _findings(root)
    if findings:
        for line in findings:
            print(line)
        print(f"\nproject-next ownership: {len(findings)} finding(s). Re-pin with 'make project-next-repin' if the change was deliberate.")
        return 1
    print(f"project-next ownership: {len(PINNED_FILES)} files match their pins at contract v{_derived_version(root)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
