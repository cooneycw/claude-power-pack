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

#: NEGATIVE-CONTROL: controls/project-next-ownership
#:     Registered per issue #1069. This gate lets work THROUGH - it is a
#:     prerequisite of `make verify` (ADR 0008), whose green is read as "the
#:     engine CPP ships is the one CPP pinned" by sessions that do not
#:     re-derive it. After the ownership transfer no upstream comparison
#:     remains to catch a drifted file by accident, so a blind version of this
#:     gate prints the same "11 files match" line over an edited engine.
#:
#:     It REPLACES controls/project-next-vendor rather than inheriting it: that
#:     control scored the upstream-fidelity question, which no longer exists.

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
    #
    # RECURSIVE since the #1069 post-merge review. `glob("*.py")` saw immediate
    # children only, and Python resolves a PACKAGE ahead of a module of the same
    # name: adding `lib/project_next/rank/__init__.py` leaves all 11 pinned files
    # byte-identical, so the gate stayed green while `import lib.project_next.rank`
    # resolved to the new package instead of the pinned `rank.py`. The pins were
    # all intact and the executed engine was not the pinned one.
    package = root / PACKAGE_REL
    if package.is_dir():
        # A SYMLINKED DIRECTORY inside the package is refused outright (#1069
        # re-review). `rglob` does not traverse directory symlinks, so
        # `lib/project_next/rank -> ../../alternate_rank` left every pin intact
        # and produced no finding, while Python still resolved the linked
        # package ahead of the pinned `rank.py` - the original shadowing defect
        # in a different filesystem shape. Rejecting them is narrower than
        # traversing: there is no legitimate symlinked directory in an owned
        # engine, and traversal would need cycle and boundary handling to be
        # correct.
        for entry in sorted(package.rglob("*")):
            if entry.is_symlink() and entry.is_dir():
                rel = entry.relative_to(root).as_posix()
                findings.append(
                    f"DRIFT: {rel} is a symlinked directory inside the owned package."
                )
        # No __pycache__ exclusion: it filtered on `module.parts`, the ABSOLUTE
        # path, so a checkout beneath a directory named __pycache__ skipped every
        # module and an unrelated ancestor decided whether the package was
        # examined. The glob is "*.py" and bytecode is ".pyc", so nothing needed
        # excluding.
        for module in sorted(package.rglob("*.py")):
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


def _recorded(root: Path) -> tuple[str | None, dict[str, str]] | None:
    """The manifest as it stands BEFORE a re-pin, or None if unreadable.

    None means "no baseline to compare against" - a first pin, or a manifest
    too damaged to read - and the caller must treat that as unknown rather than
    as agreement. An unreadable baseline is not evidence that nothing changed.
    """
    path = root / MANIFEST_REL
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    files = data.get("files")
    if not isinstance(files, dict):
        return None
    return data.get("contract_version"), files


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

    # REFUSE A CHANGED ENGINE AT AN UNCHANGED VERSION (#1069 post-merge review).
    #
    # This module's docstring claimed re-pinning without touching the contract
    # document was refused. It was not: `_repin` recomputed every hash and
    # re-derived the version from the document, so editing the engine and
    # re-pinning succeeded at the same version and `check` went green over
    # changed bytes. The claim was the gate's whole reason for existing, and
    # nothing implemented it.
    #
    # The property is about a TRANSITION, which is why neither committed case
    # caught it - each describes one state. Compare against what was recorded
    # BEFORE this re-pin: if any pinned file's hash moves while the derived
    # version does not, the bump is missing and the re-pin is refused.
    previous = _recorded(root)
    if previous is None and (root / MANIFEST_REL).is_file():
        # A manifest EXISTS and could not be read as a baseline. Skipping the
        # comparison here was the bug `_recorded`'s own docstring warned about -
        # "the caller must treat that as unknown rather than as agreement" - and
        # the caller treated it as agreement. An unreadable baseline is not
        # evidence that nothing changed.
        print(
            f"REFUSED: {MANIFEST_REL} exists but no baseline could be read from it, "
            "so a changed engine cannot be distinguished from an unchanged one.",
            file=sys.stderr,
        )
        print("  Repair the manifest, or delete it to pin from scratch.", file=sys.stderr)
        return 1
    if previous is not None:
        prior_version, prior_files = previous
        # An engine module PINNED BY THE CONTRACT but absent from the baseline is
        # an unusable comparison for that path, not a passing one. Editing a
        # module and dropping its pin bypassed the guard entirely.
        unbaselined = sorted(
            rel for rel in PINNED_FILES
            if rel.startswith(f"{PACKAGE_REL}/") and rel.endswith(".py") and rel not in prior_files
        )
        if unbaselined and derived == prior_version:
            print(
                f"REFUSED: {len(unbaselined)} engine module(s) have no baseline pin, "
                f"so a change to them cannot be detected at contract version {derived!r}.",
                file=sys.stderr,
            )
            for rel in unbaselined:
                print(f"  no baseline: {rel}", file=sys.stderr)
            return 1
        # SCOPED TO THE ENGINE, not to every pinned path. The defect is "the
        # executed engine changed and its consumer-facing version did not", so
        # the guard watches `lib/project_next/**`. The contract DOCUMENT is
        # where the version lives - editing it IS the bump - and the schema and
        # LICENSE are contract surface whose repair should not require a
        # behaviour-version bump. A guard over all eleven paths would demand a
        # contract bump to fix a typo in a template, which is the kind of
        # friction that gets a gate switched off rather than satisfied.
        changed = sorted(
            rel for rel in PINNED_FILES
            if rel.startswith(f"{PACKAGE_REL}/")
            and rel.endswith(".py")
            and rel in prior_files
            and _sha256(root / rel) != prior_files[rel]
        )
        if changed and derived == prior_version:
            print(
                f"REFUSED: {len(changed)} engine module(s) changed while "
                f"{CONTRACT_REL} still states contract version {derived!r}.",
                file=sys.stderr,
            )
            for rel in changed:
                print(f"  changed: {rel}", file=sys.stderr)
            print(
                "  contract_version is consumer-facing - the schema, the "
                "/project:next runtime pin, and the rendered decision-policy "
                "label all read it. Bump it in "
                f"{CONTRACT_REL}, or revert the engine change.",
                file=sys.stderr,
            )
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
        print(
            f"\nproject-next ownership: {len(findings)} finding(s). "
            "Re-pin with 'make project-next-repin' if the change was deliberate."
        )
        return 1
    print(f"project-next ownership: {len(PINNED_FILES)} files match their pins at contract v{_derived_version(root)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
