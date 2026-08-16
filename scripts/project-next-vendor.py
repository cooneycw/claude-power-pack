#!/usr/bin/env python3
"""Vendor and verify codex-power-pack's deterministic project-next engine.

CPP consumes the project-next decision contract from codex-power-pack, while
shipping an always-present copy so CI and local runs never depend on a sibling
checkout. The copy is deliberately boring: a fixed list of upstream files,
each pinned by its own sha256 in ``.claude/project-next-vendor.json``.

Three modes catch different failures:

``check`` (default, offline, hard gate)
    Verify every expected file against its manifest hash. This uses only the
    standard library, no git and no network, so it runs in the slim validation
    container. Per-file pins name the exact damaged or locally edited file.

``--upstream`` (network, advisory)
    Compare the vendored files with upstream main. Network failures are notes
    and exit zero; actual content drift exits one so an advisory CI step can
    report it without reddening the pipeline.

``--revendor`` (network, writes)
    Resolve upstream main to a commit, fetch that immutable snapshot, replace
    the fixed file set, and rewrite the manifest in lockstep.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = REPO_ROOT / "vendor" / "project_next"
MANIFEST_PATH = REPO_ROOT / ".claude" / "project-next-vendor.json"
SOURCE_REPO = "https://github.com/cooneycw/codex-power-pack"
SOURCE_API = "https://api.github.com/repos/cooneycw/codex-power-pack"
RAW_ROOT = "https://raw.githubusercontent.com/cooneycw/codex-power-pack"
NETWORK_TIMEOUT = 20

UPSTREAM_FILES = (
    "LICENSE",
    "docs/project-next-contract.md",
    "lib/project_next/__init__.py",
    "lib/project_next/classify.py",
    "lib/project_next/cli.py",
    "lib/project_next/collect.py",
    "lib/project_next/config.py",
    "lib/project_next/models.py",
    "lib/project_next/rank.py",
    "lib/project_next/render.py",
    "scripts/project-next.py",
    "tests/project_next/fixtures/scenarios.json",
    "tests/project_next/fixtures/golden/brief.txt",
    "tests/project_next/fixtures/golden/compact.md",
    "tests/project_next/fixtures/golden/full.md",
    "tests/project_next/fixtures/golden/result.json",
)
CONTRACT_VERSION = re.compile(r"Contract version `(?P<version>[^`]+)`")


def _fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "cpp-project-next-vendor"})
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:  # noqa: S310 - fixed HTTPS hosts
        return response.read()


def _fetch_json(url: str) -> object:
    return json.loads(_fetch_bytes(url).decode("utf-8"))


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"manifest not found: {MANIFEST_PATH}")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"manifest is not a JSON object: {MANIFEST_PATH}")
    return data


def _pinned_files(manifest: dict[str, object]) -> dict[str, str]:
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest field 'files' must be an object")
    if set(files) != set(UPSTREAM_FILES):
        missing = sorted(set(UPSTREAM_FILES) - set(files))
        extra = sorted(set(files) - set(UPSTREAM_FILES))
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ValueError("manifest file set differs from the vendoring contract: " + "; ".join(details))
    if not all(
        isinstance(path, str) and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
        for path, digest in files.items()
    ):
        raise ValueError("manifest file hashes must map paths to lowercase sha256 strings")
    return files


def _validate_manifest(manifest: dict[str, object]) -> None:
    if manifest.get("source_repo") != SOURCE_REPO:
        raise ValueError(f"manifest source_repo must be {SOURCE_REPO}")
    commit = manifest.get("upstream_commit")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("manifest upstream_commit must be a full lowercase commit SHA")
    license_name = manifest.get("upstream_license")
    if not isinstance(license_name, str) or not license_name.strip():
        raise ValueError("manifest upstream_license must be a non-empty string")
    version = manifest.get("contract_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("manifest contract_version must be a non-empty string")
    vendored_at = manifest.get("vendored_at")
    if not isinstance(vendored_at, str):
        raise ValueError("manifest vendored_at must be an ISO date")
    try:
        date.fromisoformat(vendored_at)
    except ValueError as exc:
        raise ValueError("manifest vendored_at must be an ISO date") from exc


def _contract_version(content: bytes) -> str:
    match = CONTRACT_VERSION.search(content.decode("utf-8"))
    if not match:
        raise ValueError("vendored contract has no 'Contract version `...`' line")
    return match.group("version")


def cmd_check() -> int:
    """Verify the complete vendored snapshot without git or network."""
    try:
        manifest = _load_manifest()
        _validate_manifest(manifest)
        pinned = _pinned_files(manifest)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"project-next-vendor: {exc}", file=sys.stderr)
        return 1

    drift: list[tuple[str, str, str]] = []
    for relative in UPSTREAM_FILES:
        path = VENDOR_ROOT / relative
        if not path.is_file():
            drift.append((relative, pinned[relative], "missing"))
            continue
        actual = _sha256(path.read_bytes())
        if actual != pinned[relative]:
            drift.append((relative, pinned[relative], actual))
    expected_paths = set(UPSTREAM_FILES)
    actual_paths = {
        path.relative_to(VENDOR_ROOT).as_posix()
        for path in VENDOR_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    for relative in sorted(actual_paths - expected_paths):
        drift.append((relative, "(not vendored)", "unexpected file"))

    try:
        actual_version = _contract_version((VENDOR_ROOT / "docs/project-next-contract.md").read_bytes())
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"project-next-vendor: {exc}", file=sys.stderr)
        return 1
    pinned_version = manifest.get("contract_version")
    if actual_version != pinned_version:
        print(
            "project-next-vendor: contract version mismatch: "
            f"manifest {pinned_version!r}, document {actual_version!r}",
            file=sys.stderr,
        )
        return 1

    if drift:
        print("project-next vendor drift detected:", file=sys.stderr)
        for relative, expected, actual in drift:
            print(f"  {relative}", file=sys.stderr)
            print(f"    expected: {expected}", file=sys.stderr)
            print(f"    actual:   {actual}", file=sys.stderr)
        print("Reconcile upstream first, then run: make project-next-revendor", file=sys.stderr)
        return 1

    commit = str(manifest.get("upstream_commit") or "unpinned")
    print(
        f"project-next-vendor: {len(UPSTREAM_FILES)} files match contract "
        f"v{actual_version} at {commit[:12]}"
    )
    return 0


def _resolve_main() -> str:
    payload = _fetch_json(f"{SOURCE_API}/commits/main")
    if not isinstance(payload, dict) or not isinstance(payload.get("sha"), str):
        raise ValueError("GitHub response did not contain a commit SHA")
    return payload["sha"]


def _snapshot(revision: str) -> dict[str, bytes]:
    return {
        relative: _fetch_bytes(f"{RAW_ROOT}/{revision}/{relative}")
        for relative in UPSTREAM_FILES
    }


def cmd_upstream() -> int:
    """Report upstream main drift, failing open only when the network fails."""
    try:
        revision = _resolve_main()
        remote = _snapshot(revision)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"project-next-vendor: upstream unavailable ({exc}) - skipping (fail-open)", file=sys.stderr)
        return 0

    changed = []
    for relative in UPSTREAM_FILES:
        path = VENDOR_ROOT / relative
        local = path.read_bytes() if path.is_file() else b""
        if local == remote[relative]:
            continue
        changed.append(relative)
        diff = difflib.unified_diff(
            local.decode("utf-8", errors="replace").splitlines(keepends=True),
            remote[relative].decode("utf-8", errors="replace").splitlines(keepends=True),
            fromfile=f"vendored/{relative}",
            tofile=f"upstream/{relative}",
        )
        sys.stderr.writelines(diff)

    if not changed:
        print(f"project-next-vendor: vendored snapshot matches upstream main at {revision[:12]}")
        return 0
    print("", file=sys.stderr)
    print(
        "WARNING: project-next upstream moved in " + ", ".join(changed),
        file=sys.stderr,
    )
    print("Review upstream, then run: make project-next-revendor", file=sys.stderr)
    return 1


def cmd_revendor() -> int:
    """Fetch one immutable upstream snapshot and rewrite its manifest."""
    try:
        revision = _resolve_main()
        remote = _snapshot(revision)
        version = _contract_version(remote["docs/project-next-contract.md"])
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"project-next-vendor: cannot re-vendor: {exc}", file=sys.stderr)
        return 1

    license_name = remote["LICENSE"].decode("utf-8").splitlines()[0].strip()
    if not license_name:
        print("project-next-vendor: upstream LICENSE has no license name", file=sys.stderr)
        return 1

    for relative, content in remote.items():
        destination = VENDOR_ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    manifest = {
        "source_repo": SOURCE_REPO,
        "upstream_commit": revision,
        "upstream_license": license_name,
        "contract_version": version,
        "vendored_at": date.today().isoformat(),
        "files": {relative: _sha256(remote[relative]) for relative in sorted(remote)},
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"project-next-vendor: wrote {len(remote)} files from {revision[:12]} (contract v{version})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify or refresh CPP's vendored project-next engine")
    parser.add_argument("command", nargs="?", choices=("check",), default="check")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--upstream", action="store_true", help="compare with upstream main (network, fail-open)")
    mode.add_argument("--revendor", action="store_true", help="refresh from upstream main and rewrite the manifest")
    args = parser.parse_args(argv)
    if args.upstream:
        return cmd_upstream()
    if args.revendor:
        return cmd_revendor()
    return cmd_check()


if __name__ == "__main__":
    raise SystemExit(main())
