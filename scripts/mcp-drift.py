#!/usr/bin/env python3
"""mcp-drift.py - Detect and tear down orphaned Docker MCP infrastructure.

Part of Claude Power Pack (CPP). Companion to scripts/drift-detect.sh
(systemd/host drift). This script owns *Docker MCP server* drift.

The hazard: when a server is removed from docker-compose.yml, a machine that ran
it keeps the old container, the old `mcp-<name>:*` images, and a live
`claude`/`codex mcp` registration pointing at a now-unmanaged port. /cpp:update
tore down orphaned systemd units but had no Docker equivalent, so that stale
infra just lingered and kept running (issue #405).

Detection is CURATED-LIST DRIVEN via `.claude/deprecated-mcps.yaml` - never a
blanket "every registration not in compose" sweep, which would tear down a
user's own custom MCP servers. A server is classified ORPHANED DOCKER MCP only
when BOTH hold:

  1. it is listed in deprecated-mcps.yaml, AND
  2. it is no longer a service in docker-compose.yml
     (docker compose config --services, across every profile), AND
  3. it is still locally present (container, mcp-<name>:* image, or registration).

Statuses:
  ORPHANED DOCKER MCP - listed, gone from compose, still present  -> offer teardown
  OK                  - listed but still a compose service        -> never touched
  ABSENT              - listed, gone from compose, nothing present -> nothing to do
  UNKNOWN             - current service set could not be determined
                        (no docker / compose parse failed)        -> never touched

Usage:
  mcp-drift.py                          # report table; exit 1 if orphans found
  mcp-drift.py --check                  # same as no args (explicit)
  mcp-drift.py --json                   # machine-readable findings (array)
  mcp-drift.py --list-orphans           # orphan server names, one per line (exit 0)
  mcp-drift.py --plan NAME [NAME..]     # print teardown commands (no execution)
  mcp-drift.py --teardown NAME [NAME..] # execute guarded teardown

Teardown options:
  --prune-all-images   Remove every mcp-<name>:* image (default: keep the newest
                       tag as a restore point).

Options:
  --deprecated-file FILE  Deprecation list (default: <repo>/.claude/deprecated-mcps.yaml)
  --compose-file FILE     Compose file (default: <repo>/docker-compose.yml)
  --verbose               Also list OK / ABSENT servers in the report

Exit codes:
  0 - No orphans (--check), plan printed, or teardown succeeded
  1 - Orphans detected (--check/--json), or teardown refused/failed
  2 - Usage error
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Status constants
ORPHANED = "ORPHANED DOCKER MCP"
OK = "OK"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Deprecation-list parsing (fallback drops folded text)
# --------------------------------------------------------------------------- #
def _load_yaml(text: str) -> dict:
    """Load YAML, preferring PyYAML; fall back to a minimal parser if absent."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except ImportError:
        return _fallback_parse(text)


def _strip_comment(value: str) -> str:
    in_single = in_double = False
    for i, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or value[i - 1] in " \t":
                return value[:i]
    return value


def _scalar(value: str) -> object:
    value = _strip_comment(value).strip()
    if not value or value in (">-", ">", "|", "|-", "[]"):
        return "" if value != "[]" else []
    if (value[0] == value[-1]) and value[0] in ("'", '"') and len(value) >= 2:
        return value[1:-1]
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


_LIST_FIELDS = ("containers", "claude_registrations", "codex_registrations")


def _fallback_parse(text: str) -> dict:
    """Minimal YAML parser for the deprecated-mcps.yaml schema only.

    Handles a top-level `version` scalar and a `deprecated:` block list of
    mappings, each with scalar fields plus the block-list fields in _LIST_FIELDS.
    Folded scalars (reason/replacement `>-` blocks) are intentionally dropped
    so the parity test compares structured fields only. Keep folded reason text
    colon-free so a continuation line is never
    mistaken for a field.
    """
    result: dict = {}
    entries: list[dict] = []
    current: dict | None = None
    list_key: str | None = None
    list_indent = -1

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.lstrip(" ")

        # Continuation of a block list: "- item" more indented than its key.
        if list_key is not None and body.startswith("- ") and indent > list_indent:
            current.setdefault(list_key, []).append(_scalar(body[2:]))  # type: ignore[union-attr]
            continue
        list_key = None  # any other line ends the current block list

        # Top-level scalar (e.g. "version: 1") or the "deprecated:" header.
        if indent == 0 and not body.startswith("- ") and ":" in body:
            key, _, val = body.partition(":")
            key = key.strip()
            if key == "deprecated":
                result["deprecated"] = entries
            else:
                result[key] = _scalar(val)
            continue

        # New entry: "- name: X"
        if body.startswith("- ") and "name:" in body:
            current = {}
            entries.append(current)
            after = body[2:]
            key, _, val = after.partition(":")
            current[key.strip()] = _scalar(val)
            continue

        if current is None:
            continue

        # A field on the current entry mapping.
        if ":" in body and not body.startswith("- "):
            key, _, val = body.partition(":")
            key = key.strip()
            sval = _scalar(val)
            if key in _LIST_FIELDS and sval == "":
                current[key] = []
                list_key = key
                list_indent = indent
            else:
                current[key] = sval

    if "deprecated" not in result:
        result["deprecated"] = entries
    return result


def load_deprecated_mcps(deprecated_file: Path) -> list[dict]:
    """Return the normalized list of deprecated MCP server entries."""
    if not deprecated_file.is_file():
        return []
    data = _load_yaml(deprecated_file.read_text(encoding="utf-8"))
    out: list[dict] = []
    for entry in data.get("deprecated") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        image_prefix = str(entry.get("image_prefix") or name).strip()
        containers = [str(c) for c in (entry.get("containers") or [name])]
        out.append(
            {
                "name": name,
                "reason": (str(entry.get("reason") or "")).strip(),
                "replacement": (str(entry.get("replacement") or "")).strip(),
                "port": str(entry.get("port") or "").strip(),
                "image_prefix": image_prefix,
                "containers": containers,
                "claude_registrations": [str(r) for r in (entry.get("claude_registrations") or [])],
                "codex_registrations": [str(r) for r in (entry.get("codex_registrations") or [])],
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Host state - live inventory of what is actually present on the machine
# --------------------------------------------------------------------------- #
class HostState:
    """Present Docker/registration state. Built from the host by collect_host_state,
    or constructed directly in tests to keep classification hermetic."""

    def __init__(
        self,
        current_services: set[str] | None = None,
        services_known: bool = True,
        containers: dict[str, str] | None = None,
        images: dict[str, list[dict]] | None = None,
        claude_regs: set[str] | None = None,
        codex_regs: set[str] | None = None,
    ) -> None:
        self.current_services = current_services or set()
        self.services_known = services_known
        self.containers = containers or {}  # container name -> state (running/exited/...)
        self.images = images or {}          # image repository -> [{tag,id,size,created}]
        self.claude_regs = claude_regs or set()
        self.codex_regs = codex_regs or set()


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, text=True, capture_output=True, check=False, timeout=timeout
        )
        return proc.returncode, proc.stdout
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def collect_current_services(compose_file: Path) -> tuple[set[str], bool]:
    """Return (services, known). `known` is False when the current service set
    could not be determined - in which case NOTHING is classified orphaned."""
    # No compose file at all is a KNOWN-empty state, not an unknown one: as of
    # issue #469 CPP ships no docker-compose file (the Docker MCP runtime was
    # retired), so nothing is a CPP-managed compose service. A deprecated server
    # that still lingers on the host is therefore a genuine orphan worth offering
    # for teardown. (Contrast: a compose file that is PRESENT but unparseable is
    # still treated as UNKNOWN below.)
    if not compose_file.is_file():
        return set(), True
    if not _has("docker"):
        return set(), False

    base = ["docker", "compose", "-f", str(compose_file)]
    rc, out = _run(base + ["config", "--profiles"])
    profile_args: list[str] = []
    if rc == 0:
        for p in out.splitlines():
            p = p.strip()
            if p:
                profile_args += ["--profile", p]

    rc, out = _run(base + profile_args + ["config", "--services"])
    services = {line.strip() for line in out.splitlines() if line.strip()}
    # An empty result almost always means the parse did not really work (broken
    # docker, malformed compose). Treat it as UNKNOWN rather than "zero services",
    # otherwise every present server would be wrongly flagged orphaned. A real CPP
    # compose always yields at least one service.
    if rc != 0 or not services:
        return set(), False
    return services, True


def collect_containers() -> dict[str, str]:
    if not _has("docker"):
        return {}
    rc, out = _run(["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}"])
    if rc != 0:
        return {}
    result: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0].strip():
            continue
        result[parts[0].strip()] = (parts[1].strip() if len(parts) > 1 else "").lower()
    return result


def collect_images() -> dict[str, list[dict]]:
    if not _has("docker"):
        return {}
    rc, out = _run(
        [
            "docker",
            "images",
            "--format",
            "{{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedAt}}",
        ]
    )
    if rc != 0:
        return {}
    result: dict[str, list[dict]] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or not parts[0].strip():
            continue
        repo = parts[0].strip()
        if parts[1].strip() == "<none>":
            continue
        result.setdefault(repo, []).append(
            {
                "tag": parts[1].strip(),
                "id": parts[2].strip(),
                "size": parts[3].strip() if len(parts) > 3 else "",
                "created": parts[4].strip() if len(parts) > 4 else "",
            }
        )
    return result


def _collect_registrations(cmd: str) -> set[str]:
    if not _has(cmd):
        return set()
    rc, out = _run([cmd, "mcp", "list"])
    if rc != 0:
        return set()
    names: set[str] = set()
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("no mcp", "checking", "mcp server")):
            continue
        # Accept "name: url ...", "name  url", or a bare "name".
        token = re.split(r"[:\s]", line, maxsplit=1)[0].strip()
        if token and not token.startswith(("-", "#", "=")):
            names.add(token)
    return names


def collect_host_state(compose_file: Path) -> HostState:
    services, known = collect_current_services(compose_file)
    return HostState(
        current_services=services,
        services_known=known,
        containers=collect_containers(),
        images=collect_images(),
        claude_regs=_collect_registrations("claude"),
        codex_regs=_collect_registrations("codex"),
    )


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def _matching_containers(entry: dict, host: HostState) -> list[dict]:
    """Present containers for this entry, respecting an optional CPP_CONTAINER_PREFIX."""
    found: list[dict] = []
    for want in entry["containers"]:
        for name, state in host.containers.items():
            if name == want or name.endswith(want):
                found.append({"name": name, "state": state})
    return found


def classify(deprecated: list[dict], host: HostState) -> list[dict]:
    findings: list[dict] = []
    for entry in deprecated:
        name = entry["name"]
        in_compose = name in host.current_services

        containers = _matching_containers(entry, host)
        images = host.images.get(entry["image_prefix"], [])
        claude = [r for r in entry["claude_registrations"] if r in host.claude_regs]
        codex = [r for r in entry["codex_registrations"] if r in host.codex_regs]
        present = bool(containers or images or claude or codex)

        if not host.services_known:
            status = UNKNOWN
        elif in_compose:
            status = OK
        elif present:
            status = ORPHANED
        else:
            status = ABSENT

        findings.append(
            {
                "server": name,
                "status": status,
                "reason": entry["reason"],
                "replacement": entry["replacement"],
                "port": entry["port"],
                "image_prefix": entry["image_prefix"],
                "in_compose": in_compose,
                "containers": containers,
                "images": images,
                "claude_registrations": claude,
                "codex_registrations": codex,
            }
        )
    return findings


def removable(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f["status"] == ORPHANED]


# --------------------------------------------------------------------------- #
# Teardown planning + execution
# --------------------------------------------------------------------------- #
def images_to_remove(images: list[dict], prune_all: bool) -> list[dict]:
    """Which image tags to remove. keep-one (default) keeps the newest tag as a
    restore point; prune-all removes them all. Newest = last in docker's default
    (most-recent-first) ordering, so we keep index 0 and remove the rest."""
    if not images:
        return []
    if prune_all:
        return list(images)
    # docker images lists most-recently-created first; keep that one.
    return list(images[1:])


def plan_teardown(finding: dict, prune_all_images: bool) -> list[str]:
    """Return the ordered shell commands a teardown WOULD run. Pure - no side effects."""
    cmds: list[str] = []
    for c in finding["containers"]:
        if c["state"] not in ("exited", "created", "dead", ""):
            cmds.append(f"docker stop {c['name']}")
        cmds.append(f"docker rm -f {c['name']}")

    to_remove = images_to_remove(finding["images"], prune_all_images)
    for img in to_remove:
        cmds.append(f"docker rmi {finding['image_prefix']}:{img['tag']}")
    kept = [i for i in finding["images"] if i not in to_remove]
    if kept and not prune_all_images:
        cmds.append(f"# kept restore point: {finding['image_prefix']}:{kept[0]['tag']}")

    for reg in finding["claude_registrations"]:
        scope = detect_claude_scope(reg, execute=False)
        cmds.append(f"claude mcp remove {reg} -s {scope}")
    for reg in finding["codex_registrations"]:
        cmds.append(f"codex mcp remove {reg}")
    return cmds


def detect_claude_scope(name: str, execute: bool = True) -> str:
    """Best-effort scope detection for `claude mcp remove -s <scope>`.

    Parses `claude mcp get <name>` for a local/project/user scope; defaults to
    `local` (where these servers were registered). In plan mode we skip the probe
    and just report the default so `--plan` stays side-effect free."""
    default = "local"
    if not execute or not _has("claude"):
        return default
    rc, out = _run(["claude", "mcp", "get", name])
    if rc != 0:
        return default
    low = out.lower()
    for scope in ("local", "project", "user"):
        if re.search(rf"scope[^\n]*\b{scope}\b", low):
            return scope
    return default


def teardown(
    names: list[str],
    findings: list[dict],
    prune_all_images: bool = False,
    execute: bool = True,
) -> int:
    """Guarded teardown of ORPHANED DOCKER MCP servers.

    Hard-refuses any name that is not classified ORPHANED (unlisted, still in
    compose/OK, ABSENT, or UNKNOWN) BEFORE running anything - this is what keeps
    a user's own custom MCP registration from ever being removed. Each teardown
    step is best-effort so one failure does not strand the rest."""
    by_name = {f["server"]: f for f in findings}
    refused = 0
    torn = 0

    for name in names:
        finding = by_name.get(name)
        if finding is None:
            print(f"REFUSED {name}: not in the deprecated-mcps.yaml list of record", file=sys.stderr)
            refused += 1
            continue
        if finding["status"] != ORPHANED:
            print(
                f"REFUSED {name}: classified {finding['status']}; only "
                "ORPHANED DOCKER MCP servers may be torn down",
                file=sys.stderr,
            )
            refused += 1
            continue

        cmds = plan_teardown(finding, prune_all_images)
        if not execute:
            for c in cmds:
                print(c)
            torn += 1
            continue

        print(f"Tearing down {name} (port {finding['port'] or 'n/a'})...")
        for c in cmds:
            if c.startswith("#"):
                print(f"  {c}")
                continue
            rc, out = _run(c.split())
            marker = "ok" if rc == 0 else f"warn (rc={rc})"
            print(f"  [{marker}] {c}")
        removed_imgs = images_to_remove(finding["images"], prune_all_images)
        disk = ", ".join(f"{i['tag']} ({i['size']})" for i in removed_imgs if i.get("size"))
        freed_port = finding["port"] or "n/a"
        print(
            f"  freed port {freed_port}; removed {len(finding['containers'])} container(s), "
            f"{len(removed_imgs)} image tag(s)" + (f" - reclaimed {disk}" if disk else "")
        )
        torn += 1

    if refused:
        print(f"\n{torn} torn down, {refused} refused.", file=sys.stderr)
        return 1
    print(f"\n{torn} orphaned Docker MCP server(s) torn down.")
    return 0


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def render_table(findings: list[dict], verbose: bool) -> str:
    lines = ["Docker MCP Drift Report", "=======================", ""]
    shown = [f for f in findings if verbose or f["status"] == ORPHANED]
    if shown:
        lines.append(f"{'Server':<24} {'Port':<6} {'In-compose':<11} {'Status'}")
        lines.append(f"{'-' * 24} {'-' * 6} {'-' * 11} {'-' * 20}")
        for f in shown:
            lines.append(
                f"{f['server']:<24} {f['port'] or '-':<6} "
                f"{'yes' if f['in_compose'] else 'no':<11} {f['status']}"
            )
        lines.append("")

    orphans = removable(findings)
    for f in orphans:
        present = []
        if f["containers"]:
            present.append(f"{len(f['containers'])} container(s)")
        if f["images"]:
            present.append(f"{len(f['images'])} image tag(s)")
        if f["claude_registrations"]:
            present.append(f"claude:{','.join(f['claude_registrations'])}")
        if f["codex_registrations"]:
            present.append(f"codex:{','.join(f['codex_registrations'])}")
        lines.append(f"  {f['server']} - present: {', '.join(present) or 'unknown'}")
        if f["replacement"]:
            lines.append(f"    replacement: {f['replacement']}")

    if any(f["status"] == UNKNOWN for f in findings):
        lines.append(
            "Note: current service set could not be determined (docker/compose "
            "unavailable); nothing classified as orphaned."
        )
    if not orphans:
        lines.append("No orphaned Docker MCP servers detected.")
    else:
        lines.append(
            f"{len(orphans)} orphaned Docker MCP server(s) flagged. Teardown is "
            "offered with confirmation by /cpp:update; a keep-one image restore "
            "point is retained unless you choose prune-all."
        )
    lines.append(
        "Note: detection is curated-list driven (.claude/deprecated-mcps.yaml). "
        "A server removed from compose without a list entry is not auto-detected, "
        "and a user's own custom MCP registration is never flagged."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        add_help=True,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--check", action="store_true", help="Report drift table (default)")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON array")
    parser.add_argument("--list-orphans", action="store_true",
                        help="Print orphaned server names, one per line (exit 0)")
    parser.add_argument("--plan", nargs="+", metavar="NAME",
                        help="Print teardown commands for named servers (no execution)")
    parser.add_argument("--teardown", nargs="+", metavar="NAME",
                        help="Execute guarded teardown of named ORPHANED servers")
    parser.add_argument("--prune-all-images", action="store_true",
                        help="Remove every mcp-<name>:* image (default: keep newest)")
    parser.add_argument("--verbose", action="store_true", help="List OK/ABSENT too")
    parser.add_argument("--deprecated-file", default=None)
    parser.add_argument("--compose-file", default=None)
    args = parser.parse_args(argv)

    deprecated_file = (
        Path(args.deprecated_file) if args.deprecated_file
        else REPO_ROOT / ".claude" / "deprecated-mcps.yaml"
    )
    compose_file = (
        Path(args.compose_file) if args.compose_file
        else REPO_ROOT / "docker-compose.yml"
    )

    deprecated = load_deprecated_mcps(deprecated_file)
    host = collect_host_state(compose_file)
    findings = classify(deprecated, host)

    if args.plan:
        return teardown(args.plan, findings, args.prune_all_images, execute=False)

    if args.teardown:
        return teardown(args.teardown, findings, args.prune_all_images, execute=True)

    if args.list_orphans:
        for f in removable(findings):
            print(f["server"])
        return 0

    if args.json:
        print(json.dumps(findings, indent=2))
        return 1 if removable(findings) else 0

    # default / --check
    print(render_table(findings, verbose=args.verbose))
    return 1 if removable(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
