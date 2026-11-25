"""Explicit disposable adapters for core acceptance, never host auto-discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .driver import _source_blob
from .models import (
    AdapterError,
    Discovery,
    ExpectedBuild,
    ExpectedMember,
    ExpectedPackage,
    Policy,
    Request,
    Revision,
    State,
    build_manifest_sha256,
)
from .scope import Scope, absolute, parts
from .store import read_ledger

FIXTURE_MARKER = b"cpp-host-update-fixture-v1\n"


class FixtureAdapter:
    def __init__(self, root: Path, spec: dict[str, Any]) -> None:
        self.root = absolute(root)
        self.spec = spec
        self.harness = str(spec["harness"])

    def path(self, key: str) -> Path:
        value = self.spec[key]
        if not isinstance(value, str):
            raise AdapterError(f"fixture path {key} is not a string", state=State.UNMANAGED)
        return self.root.joinpath(*parts(value))

    def preflight(self, request: Request) -> Policy:
        # Validate all spellings before touching any installed-root descendant.
        paths = {key: self.path(key) for key in ("install", "ledger", "lock", "work", "source")}
        if request.revision.snapshot_root != paths["source"]:
            raise AdapterError("fixture source scope mismatch", state=State.UNMANAGED)
        if (paths["install"].is_relative_to(paths["source"])
                or paths["source"].is_relative_to(paths["install"])
                or paths["lock"].is_relative_to(paths["source"])):
            raise AdapterError("fixture write scope overlaps the immutable source", state=State.UNMANAGED)
        # The fixture anchor is approved, but descriptor-chosen descendants
        # beneath it are not system ancestors. Validate their existing prefixes
        # no-follow before returning a policy the core may open as a root.
        anchor = Scope(Policy(self.root, self.root / ".unused-ledger", self.root / ".unused-lock",
                              self.root / ".unused-work"))
        for key, path in paths.items():
            parent = path.parent if key in ("ledger", "lock") else path
            try:
                with anchor.directory(parent):
                    pass
            except FileNotFoundError:
                pass
        return Policy(paths["install"], paths["ledger"], paths["lock"], paths["work"])

    def discover(self, policy: Policy, request: Request) -> Discovery:
        records = read_ledger(Scope(policy, owner=self.harness))
        managed = bool(records)
        selected = self.spec.get("selected", managed)
        if type(selected) is not bool:
            raise AdapterError("fixture selection must be a boolean", state=State.UNMANAGED)
        return Discovery(selected, managed, ("explicit-fixture-selection" if "selected" in self.spec
                                           else "validated-CPP-ledger",))

    def build(self, revision: Revision, policy: Policy) -> ExpectedBuild:
        packages: list[ExpectedPackage] = []
        for row in self.spec["packages"]:
            members: dict[str, ExpectedMember] = {}
            for name, entry in row["members"].items():
                parts(name)
                relative = parts(entry["source"])
                content = _source_blob(revision, "/".join(relative))
                members[name] = ExpectedMember(content, entry.get("mode", 0o644))
            packages.append(ExpectedPackage(row["name"], row["canonical_source"], members))
        return ExpectedBuild(revision.commit, tuple(packages), build_manifest_sha256(revision.commit, packages))


def load_fixture(root: Path) -> tuple[tuple[FixtureAdapter, ...], Revision]:
    """Read only the explicit fixture marker/config before adapter preflight."""
    root = absolute(root)
    scope = Scope(Policy(root, root / ".unused-ledger", root / ".unused-lock", root / ".unused-work"))
    if scope.read(root / ".cpp-host-update-fixture") != FIXTURE_MARKER:
        raise AdapterError("explicit fixture marker missing or invalid", state=State.UNMANAGED)
    value = json.loads(scope.read(root / "fixture.json"))
    if value.get("schema") != 1 or not isinstance(value.get("adapters"), list):
        raise AdapterError("unsupported fixture descriptor", state=State.UNMANAGED)
    source = root.joinpath(*parts(value["source"]))
    adapters = tuple(FixtureAdapter(root, row) for row in value["adapters"])
    return adapters, Revision(value["revision"], source)
