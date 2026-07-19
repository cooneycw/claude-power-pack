#!/usr/bin/env python3
"""eli5-vendor.py - guard the canonical -> vendored link for the eli5 gate core.

CPP's ``/flow:eli5`` vendors its core - the section between the
``eli5-core:begin`` / ``eli5-core:end`` markers - verbatim from the canonical
standalone repo https://github.com/cooneycw/eli5-gate (extracted in #443). That
link had a drift script but no automation of any kind: no CI step, no Makefile
target, no test (issue #591). Advisory-by-design is fine; advisory-and-never-run
is decoration.

Two checks, because they catch different failures and neither subsumes the
other:

``check`` (offline, the CI gate)
    Recompute the vendored core's sha256 and compare it to the pinned value in
    the manifest (``.claude/eli5-vendor.json``). Deterministic, stdlib-only, no
    network and no git - so it runs inside the uv:python3.11-slim validate
    container that ships neither curl nor git (the recurring #451/#489 trap).
    Catches a local edit of the vendored core that bypassed re-vendoring.

``--upstream`` (network, advisory)
    Fetch the canonical copy and diff it against the vendored one. This is the
    check that notices UPSTREAM MOVED - the manifest cannot, since it pins what
    was vendored, not what is now canonical. Fail-open: any network trouble
    exits 0 with a note, so an offline runner never reddens the pipeline.

``--revendor`` (network, writes)
    Re-vendor: fetch the canonical core, replace the marker section in place,
    and rewrite the manifest (content hash + upstream commit SHA + date) so the
    offline gate goes green on the new content. This keeps the core and its
    pin in lockstep - the whole point of the manifest.

Reconcile drift by editing the CANONICAL repo first, then re-vendoring here.
After a re-vendor, refresh the generated surfaces:
    scripts/plugin-sync.sh --write flow
    python3 scripts/codex-skill-sync.py --write flow
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / ".claude" / "eli5-vendor.json"
DEFAULT_VENDORED = ".claude/commands/flow/eli5.md"
DEFAULT_RAW_URL = "https://raw.githubusercontent.com/cooneycw/eli5-gate/main/commands/eli5.md"
DEFAULT_COMMITS_API = "https://api.github.com/repos/cooneycw/eli5-gate/commits?path=commands/eli5.md&per_page=1"

BEGIN_MARKER = "<!-- eli5-core:begin"
END_MARKER = "<!-- eli5-core:end"

NETWORK_TIMEOUT = 15


class CoreNotFound(Exception):
    """The marker-delimited core is missing or malformed."""


def extract_core(text: str) -> str:
    """Return the text between the eli5-core markers.

    Marker detection is anchored to the START of a line, so prose that merely
    MENTIONS a marker (the Notes bullet in eli5.md does) cannot re-trigger the
    state machine - the same anchoring the shell implementation used.
    """
    lines = text.splitlines(keepends=True)
    start = end = None
    for i, line in enumerate(lines):
        if start is None and line.startswith(BEGIN_MARKER):
            start = i + 1
        elif start is not None and line.startswith(END_MARKER):
            end = i
            break
    if start is None:
        raise CoreNotFound(f"no line starting with '{BEGIN_MARKER}'")
    if end is None:
        raise CoreNotFound(f"'{BEGIN_MARKER}' has no matching '{END_MARKER}'")
    return "".join(lines[start:end])


def core_sha256(core: str) -> str:
    return hashlib.sha256(core.encode("utf-8")).hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"manifest is not a JSON object: {path}")
    return data


def vendored_path(manifest: dict) -> Path:
    rel = manifest.get("vendored", {}).get("file", DEFAULT_VENDORED)
    return REPO_ROOT / rel


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "cpp-eli5-vendor"})
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:  # noqa: S310 - fixed https URL
        return resp.read().decode("utf-8")


# --- check (offline) ---------------------------------------------------------


def cmd_check(manifest: dict) -> int:
    """Vendored core must match the hash the manifest pins. Offline, hard gate."""
    local = vendored_path(manifest)
    if not local.is_file():
        print(f"eli5-vendor: {local} not found", file=sys.stderr)
        return 1
    try:
        core = extract_core(local.read_text(encoding="utf-8"))
    except CoreNotFound as exc:
        print(f"eli5-vendor: {local}: {exc}", file=sys.stderr)
        return 1

    pinned = manifest.get("vendored", {}).get("core_sha256", "")
    actual = core_sha256(core)
    if actual == pinned:
        upstream = manifest.get("source", {}).get("upstream_commit") or "unpinned"
        print(f"eli5-vendor: vendored core matches the manifest (sha256 {actual[:12]}, upstream {upstream[:12]})")
        return 0

    print("", file=sys.stderr)
    print("DRIFT: the vendored eli5 core does not match the manifest pin.", file=sys.stderr)
    print(f"  manifest: {MANIFEST_PATH}", file=sys.stderr)
    print(f"  expected: {pinned or '(missing)'}", file=sys.stderr)
    print(f"  actual:   {actual}", file=sys.stderr)
    print("", file=sys.stderr)
    print("The core between the eli5-core markers was edited locally. That core is", file=sys.stderr)
    print("vendored from https://github.com/cooneycw/eli5-gate - edit it THERE first,", file=sys.stderr)
    print("then re-vendor here:  make eli5-revendor", file=sys.stderr)
    print("If the local edit is the intended new content, the same target re-pins it.", file=sys.stderr)
    return 1


# --- upstream (network, advisory) --------------------------------------------


def cmd_upstream(manifest: dict) -> int:
    """Diff the vendored core against the live canonical copy. Fail-open."""
    local = vendored_path(manifest)
    url = manifest.get("source", {}).get("raw_url", DEFAULT_RAW_URL)

    if not local.is_file():
        print(f"eli5-vendor: {local} not found (nothing to check)", file=sys.stderr)
        return 0
    try:
        local_core = extract_core(local.read_text(encoding="utf-8"))
    except CoreNotFound as exc:
        print(f"eli5-vendor: {local}: {exc}", file=sys.stderr)
        return 1

    try:
        remote_text = fetch(url)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"eli5-vendor: canonical source unreachable ({url}): {exc} - skipping (fail-open)", file=sys.stderr)
        return 0

    try:
        remote_core = extract_core(remote_text)
    except CoreNotFound as exc:
        print(f"eli5-vendor: canonical copy has no usable core ({exc}) - skipping (fail-open)", file=sys.stderr)
        return 0

    if remote_core == local_core:
        print("eli5-vendor: vendored core is in sync with canonical eli5-gate")
        return 0

    diff = difflib.unified_diff(
        remote_core.splitlines(keepends=True),
        local_core.splitlines(keepends=True),
        fromfile="canonical/eli5-gate",
        tofile="vendored/cpp",
    )
    sys.stderr.writelines(diff)
    print("", file=sys.stderr)
    print("WARNING: the vendored eli5 core has drifted from the canonical copy at", file=sys.stderr)
    print(f"  {url}", file=sys.stderr)
    print("Reconcile by updating cooneycw/eli5-gate first, then re-vendoring:", file=sys.stderr)
    print("  make eli5-revendor", file=sys.stderr)
    return 1


# --- revendor (network, writes) ----------------------------------------------


def latest_upstream_commit(manifest: dict) -> str | None:
    api = manifest.get("source", {}).get("commits_api", DEFAULT_COMMITS_API)
    try:
        payload = json.loads(fetch(api))
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        print(f"eli5-vendor: could not resolve the upstream commit SHA ({exc}) - leaving it unpinned", file=sys.stderr)
        return None
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        sha = payload[0].get("sha")
        return sha if isinstance(sha, str) else None
    return None


def cmd_revendor(manifest: dict) -> int:
    local = vendored_path(manifest)
    url = manifest.get("source", {}).get("raw_url", DEFAULT_RAW_URL)

    try:
        remote_core = extract_core(fetch(url))
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"eli5-vendor: cannot re-vendor - canonical source unreachable ({url}): {exc}", file=sys.stderr)
        return 1
    except CoreNotFound as exc:
        print(f"eli5-vendor: cannot re-vendor - canonical copy has no usable core: {exc}", file=sys.stderr)
        return 1

    text = local.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start = end = None
    for i, line in enumerate(lines):
        if start is None and line.startswith(BEGIN_MARKER):
            start = i + 1
        elif start is not None and line.startswith(END_MARKER):
            end = i
            break
    if start is None or end is None:
        print(f"eli5-vendor: {local} has no usable marker pair - cannot re-vendor", file=sys.stderr)
        return 1

    changed = "".join(lines[start:end]) != remote_core
    if changed:
        local.write_text("".join(lines[:start]) + remote_core + "".join(lines[end:]), encoding="utf-8")

    manifest.setdefault("source", {})["upstream_commit"] = latest_upstream_commit(manifest)
    manifest.setdefault("vendored", {})["core_sha256"] = core_sha256(remote_core)
    manifest["vendored"]["core_lines"] = len(remote_core.splitlines())
    manifest["vendored"]["vendored_at"] = date.today().isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"eli5-vendor: {'re-vendored core and' if changed else 'core already current;'} updated the manifest")
    print("Next: scripts/plugin-sync.sh --write flow && python3 scripts/codex-skill-sync.py --write flow")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guard the vendored eli5 gate core (issue #591).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--upstream",
        action="store_true",
        help="diff the vendored core against the live canonical copy (network, fail-open)",
    )
    mode.add_argument(
        "--revendor",
        action="store_true",
        help="re-fetch the canonical core, replace it in place, and re-pin the manifest",
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"eli5-vendor: {exc}", file=sys.stderr)
        return 1

    if args.revendor:
        return cmd_revendor(manifest)
    if args.upstream:
        return cmd_upstream(manifest)
    return cmd_check(manifest)


if __name__ == "__main__":
    sys.exit(main())
