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

A RUNNING container that merely shares a deprecated name but belongs to an
external compose project (or runs a non-CPP image) is treated as a LIVE FOREIGN
container: it is protected, never counted as a present CPP artifact, and never
torn down (issue #520). The external second-opinion server runs its own
`mcp-second-opinion` / `aws-secrets-agent` containers, so the bare name match
otherwise flagged a live external server as an orphan.

An UNREADABLE docker socket is NOT an empty host (issue #673). `docker ps`
refused for permission (or a dead daemon) used to empty the container inventory
silently: every curated server then classified ABSENT and the report printed the
clean banner when it meant "I could not look". A failed read is now carried as
its own state - every curated server is UNKNOWN, the banner is suppressed, and
the exit code is a distinct 3 so a caller can branch on "could not assess"
instead of reading it as "clean". A MISSING docker binary is deliberately the
other thing: nothing can be running under a docker that is not installed, so the
inventory is genuinely empty (CPP has shipped no container runtime since #469) -
that stays a clean read, named in the report rather than hidden.

Statuses:
  ORPHANED DOCKER MCP - listed, gone from compose, still present  -> offer teardown
  NAME COLLISION      - would be orphaned, but live evidence (its port answers,
                        or a live registration targets it) says the name may be
                        the user's own deployment                 -> never touched
  OK                  - listed but still a compose service        -> never touched
  ABSENT              - listed, gone from compose, nothing present -> nothing to do
  UNKNOWN             - current state could not be determined (docker unreadable,
                        or compose parse failed)                  -> never touched

Usage:
  mcp-drift.py                          # report table; exit 1 if orphans found
  mcp-drift.py --check                  # same as no args (explicit)
  mcp-drift.py --json                   # machine-readable findings (array)
  mcp-drift.py --list-orphans           # orphan server names, one per line
  mcp-drift.py --plan NAME [NAME..]     # print teardown commands (no execution)
  mcp-drift.py --teardown NAME [NAME..] # execute guarded teardown

Teardown options:
  --prune-all-images   Remove every mcp-<name>:* image (default: keep the newest
                       tag as a restore point).

Options:
  --deprecated-file FILE  Deprecation list (default: <repo>/.claude/deprecated-mcps.yaml)
  --compose-file FILE     Compose file (default: <repo>/docker-compose.yml)
  --verbose               Also list OK / ABSENT servers in the report
  --no-sudo               Never retry a permission-refused docker read via
                          `sudo -n` (the retry is non-interactive either way)
  --no-port-probe         Skip the localhost port probe that downgrades an
                          apparent orphan to NAME COLLISION

Exit codes:
  0 - No orphans (--check), plan printed, or teardown succeeded
  1 - Orphans detected (--check/--json), or teardown refused/failed
  2 - Usage error
  3 - Docker state could not be read (--check/--json/--list-orphans): nothing
      was assessed, so this is NOT a clean result
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

# Status constants
ORPHANED = "ORPHANED DOCKER MCP"
COLLISION = "NAME COLLISION"
OK = "OK"
ABSENT = "ABSENT"
UNKNOWN = "UNKNOWN"

# Docker readability states (issue #673). `absent` and `unreadable` are
# deliberately different answers: a docker that is not installed cannot be
# running anything, so its inventory is empty as a FACT; a docker that refused
# the read told us nothing at all.
DOCKER_OK = "ok"
DOCKER_ABSENT = "absent"
DOCKER_UNREADABLE = "unreadable"

# Signatures of a docker read that failed for permission rather than for a dead
# daemon. Only these are worth a `sudo -n` retry - sudo cannot start a daemon.
_PERMISSION_SIGNS = (
    "permission denied",
    "got permission denied",
    "dial unix /var/run/docker.sock",
    "connect: permission denied",
)

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
        container_meta: dict[str, dict] | None = None,
        docker_state: str = DOCKER_OK,
        docker_error: str = "",
        docker_prefix: tuple[str, ...] = ("docker",),
        listening_ports: set[int] | None = None,
        registration_targets: set[str] | None = None,
    ) -> None:
        self.current_services = current_services or set()
        self.services_known = services_known
        # How the docker inventory read went (issue #673): DOCKER_OK, DOCKER_ABSENT
        # (no binary - a known-empty inventory), or DOCKER_UNREADABLE (the read was
        # refused, so `containers`/`images` below are meaningless and every curated
        # server must classify UNKNOWN). Defaults to DOCKER_OK so a hermetic test
        # that hands over an inventory directly is classified exactly as before.
        self.docker_state = docker_state
        self.docker_error = docker_error
        # The argv prefix a teardown must use to reach the same docker the
        # inventory was read from - ("docker",) normally, ("sudo", "-n", "docker")
        # when the read only succeeded after a non-interactive sudo retry.
        self.docker_prefix = docker_prefix
        # Local TCP ports observed answering, and the raw target text of live
        # claude/codex registrations. Both are live-deployment evidence that
        # downgrades an apparent orphan to NAME COLLISION (issue #673 fix 3).
        self.listening_ports = listening_ports or set()
        self.registration_targets = registration_targets or set()
        self.containers = containers or {}  # container name -> state (running/exited/...)
        # container name -> {"image": <ref>, "project": <compose-project label>}.
        # Provenance used to protect a live external container that reuses a
        # deprecated name from being torn down (issue #520). Empty when unknown
        # (old docker, or a hermetic test): callers must treat missing provenance
        # as "no positive foreign evidence", i.e. classify exactly as before.
        self.container_meta = container_meta or {}
        self.images = images or {}          # image repository -> [{tag,id,size,created}]
        self.claude_regs = claude_regs or set()
        self.codex_regs = codex_regs or set()

    @property
    def docker_readable(self) -> bool:
        """False only when the docker read was REFUSED. A missing docker binary
        reads as readable-and-empty, which is the honest answer: nothing can be
        running under a runtime that is not installed (issue #673)."""
        return self.docker_state != DOCKER_UNREADABLE


def _run_capture(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    """(rc, stdout, stderr). stderr is what tells a permission refusal apart from
    an empty host, so the docker collectors need all three (issue #673)."""
    try:
        proc = subprocess.run(
            cmd, text=True, capture_output=True, check=False, timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    rc, out, _ = _run_capture(cmd, timeout)
    return rc, out


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _looks_like_permission_error(text: str) -> bool:
    low = text.lower()
    return any(sign in low for sign in _PERMISSION_SIGNS)


def collect_current_services(
    compose_file: Path, prefix: tuple[str, ...] = ("docker",)
) -> tuple[set[str], bool]:
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
    if not _has(prefix[0]):
        return set(), False

    base = [*prefix, "compose", "-f", str(compose_file)]
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


_PS_FORMAT = '{{.Names}}\t{{.State}}\t{{.Image}}\t{{.Label "com.docker.compose.project"}}'


def probe_docker(allow_sudo: bool = True) -> tuple[str, str, tuple[str, ...], str]:
    """Establish whether the docker inventory can be read at all (issue #673).

    Returns (state, error, prefix, ps_stdout):
      DOCKER_ABSENT    - no docker binary. A known-empty inventory, not a failed
                         read: nothing runs under a runtime that is not installed.
      DOCKER_UNREADABLE- docker is there but refused (permission denied, dead
                         daemon, timeout). NOTHING may be concluded from this.
      DOCKER_OK        - `prefix` is the argv the read succeeded with, and every
                         later docker call (including teardown) must reuse it so
                         what runs matches what `--plan` printed.

    On a PERMISSION-shaped refusal only, one non-interactive `sudo -n docker ps`
    retry is attempted (fix 2). `sudo -n` never prompts for a password, so a
    drift check can never block on a TTY; a sudo that would need one simply
    fails and the state stays UNREADABLE."""
    if not _has("docker"):
        return DOCKER_ABSENT, "docker command not found", ("docker",), ""

    argv = ["docker", "ps", "-a", "--format", _PS_FORMAT]
    rc, out, err = _run_capture(argv)
    if rc == 0:
        return DOCKER_OK, "", ("docker",), out

    detail = (err or out).strip().splitlines()
    message = detail[0].strip() if detail else f"docker ps exited {rc}"

    if allow_sudo and _has("sudo") and _looks_like_permission_error(err or out):
        rc2, out2, err2 = _run_capture(["sudo", "-n", *argv])
        if rc2 == 0:
            return DOCKER_OK, "", ("sudo", "-n", "docker"), out2
        sudo_detail = (err2 or out2).strip().splitlines()
        sudo_message = sudo_detail[0].strip() if sudo_detail else f"sudo -n docker ps exited {rc2}"
        message = f"{message} (sudo -n retry also failed: {sudo_message})"

    return DOCKER_UNREADABLE, message, ("docker",), ""


def _parse_ps(out: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0].strip():
            continue
        result[parts[0].strip()] = {
            "state": (parts[1].strip() if len(parts) > 1 else "").lower(),
            "image": parts[2].strip() if len(parts) > 2 else "",
            "project": parts[3].strip() if len(parts) > 3 else "",
        }
    return result


def collect_containers_full() -> dict[str, dict]:
    """Present containers keyed by name -> {"state", "image", "project"}.

    `project` is the `com.docker.compose.project` label (empty for containers not
    managed by compose); `image` is the image ref the container runs. Both feed
    the live-external-container guard in classification (issue #520). Older docker
    that does not support the label prints an empty final column, which the guard
    treats as unknown provenance.

    NOTE: an empty dict here is ambiguous by construction - it is returned for an
    empty host AND for a refused read. Callers that must tell those apart go
    through probe_docker() / collect_host_state() instead (issue #673); this
    wrapper is kept for back-compat with external callers."""
    state, _, _, out = probe_docker()
    if state != DOCKER_OK:
        return {}
    return _parse_ps(out)


def collect_containers() -> dict[str, str]:
    """Back-compat name -> state view over collect_containers_full()."""
    return {name: meta["state"] for name, meta in collect_containers_full().items()}


def collect_images(prefix: tuple[str, ...] = ("docker",)) -> dict[str, list[dict]]:
    """Image inventory, read through the same argv prefix the container read
    succeeded with (so a sudo-only docker is not half-read, issue #673)."""
    if not _has(prefix[0]):
        return {}
    rc, out = _run(
        [
            *prefix,
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


def _collect_registrations(cmd: str) -> tuple[set[str], set[str]]:
    """(names, target texts) of live MCP registrations.

    The target text is whatever follows the name on the line - typically the URL
    (`second-opinion: http://127.0.0.1:8080/mcp - connected`). It is kept because
    a live registration pointing at a retired name's port is evidence that the
    name belongs to the user's own deployment, not to a CPP leftover (issue #673
    fix 3)."""
    if not _has(cmd):
        return set(), set()
    rc, out = _run([cmd, "mcp", "list"])
    if rc != 0:
        return set(), set()
    names: set[str] = set()
    targets: set[str] = set()
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("no mcp", "checking", "mcp server")):
            continue
        # Accept "name: url ...", "name  url", or a bare "name".
        token = re.split(r"[:\s]", line, maxsplit=1)[0].strip()
        if token and not token.startswith(("-", "#", "=")):
            names.add(token)
            rest = line[len(token):].lstrip(": \t")
            if rest:
                targets.add(rest)
    return names, targets


def probe_listening_ports(ports: set[int], timeout: float = 0.2) -> set[int]:
    """Which of `ports` accept a local TCP connection right now.

    A plain connect to loopback - no payload is sent and no request is made - so
    the probe cannot disturb whatever is listening. Used only to downgrade an
    apparent orphan to NAME COLLISION, never to escalate anything (issue #673)."""
    answering: set[int] = set()
    for port in sorted(ports):
        for host in ("127.0.0.1", "::1"):
            with contextlib.suppress(OSError, ValueError):
                with socket.create_connection((host, port), timeout=timeout):
                    answering.add(port)
                    break
    return answering


def collect_host_state(
    compose_file: Path, allow_sudo: bool = True, probe_ports: set[int] | None = None
) -> HostState:
    docker_state, docker_error, prefix, ps_out = probe_docker(allow_sudo=allow_sudo)
    # Deliberately NOT routed through `prefix`: `docker compose config` parses YAML
    # and never touches the daemon, so a socket refusal does not affect it and
    # elevating it would only run the parse under a different environment.
    services, known = collect_current_services(compose_file)

    # A refused read yields no inventory at all - deliberately NOT an empty one,
    # which is what made the report claim "clean" for a host it never saw (#673).
    full = _parse_ps(ps_out) if docker_state == DOCKER_OK else {}
    containers = {name: meta["state"] for name, meta in full.items()}
    container_meta = {
        name: {"image": meta["image"], "project": meta["project"]}
        for name, meta in full.items()
    }
    images = collect_images(prefix) if docker_state == DOCKER_OK else {}

    claude_regs, claude_targets = _collect_registrations("claude")
    codex_regs, codex_targets = _collect_registrations("codex")

    return HostState(
        current_services=services,
        services_known=known,
        containers=containers,
        container_meta=container_meta,
        images=images,
        claude_regs=claude_regs,
        codex_regs=codex_regs,
        docker_state=docker_state,
        docker_error=docker_error,
        docker_prefix=prefix,
        listening_ports=probe_listening_ports(probe_ports) if probe_ports else set(),
        registration_targets=claude_targets | codex_targets,
    )


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
_NON_RUNNING_STATES = ("exited", "created", "dead", "")


def _is_running(state: str) -> bool:
    """True when a container is live (not exited/created/dead/unknown)."""
    return state not in _NON_RUNNING_STATES


def _image_repo(image: str) -> str:
    """Repository portion of a docker image ref, dropping a trailing ``:tag``.

    A registry ``host:port/repo`` ref is preserved because the tag, when present,
    never contains ``/`` - so only a trailing ``:<tag>`` with no slash is stripped.
    ``mcp-second-opinion:latest`` -> ``mcp-second-opinion``; ``ghcr.io/acme/x`` ->
    ``ghcr.io/acme/x``."""
    image = image.strip()
    if not image:
        return ""
    head, sep, tail = image.rpartition(":")
    if sep and "/" not in tail:
        return head
    return image


def _image_tag(image: str) -> str:
    """Tag portion of a docker image ref ('' when none). The same rule as
    _image_repo: a tag never contains '/', so a ``host:port/repo`` registry ref
    with no tag yields '' rather than the port."""
    image = image.strip()
    head, sep, tail = image.rpartition(":")
    if sep and "/" not in tail:
        return tail
    return ""


def _split_protected_images(
    entry: dict, foreign_containers: list[dict], all_images: list[dict]
) -> tuple[list[dict], list[dict]]:
    """(orphan_eligible, protected) image tags for this entry (issue #634).

    The #520 guard protects live external CONTAINERS but the image-prefix match
    still counted the tags those containers run as CPP leftovers - so a
    migrated host read ORPHANED forever and the offered teardown would `docker
    rmi` an image out from under the live external stack. A tag referenced by
    a FOREIGN-LIVE container (liveness inherited from _matching_containers:
    only running foreign containers land in that list) is protected; a tag
    referenced by nothing, or only by a stale CPP-project container, stays a
    legitimate orphan. A bare-repo ref counts as `latest`. Digest-form refs
    (@sha256:...) carry no tag and protect none - the running container itself
    remains #520-protected either way."""
    protected_tags: set[str] = set()
    for fc in foreign_containers:
        ref = str(fc.get("image") or "")
        if _image_repo(ref) == entry["image_prefix"] and "@" not in ref:
            protected_tags.add(_image_tag(ref) or "latest")
    eligible = [im for im in all_images if im["tag"] not in protected_tags]
    protected = [im for im in all_images if im["tag"] in protected_tags]
    return eligible, protected


def _container_is_foreign_live(name: str, state: str, entry: dict, host: HostState) -> bool:
    """A RUNNING matched container that provenance shows is NOT a CPP-built orphan.

    The false-positive this guards (issue #520): the external second-opinion
    server runs its own containers named `mcp-second-opinion` / `aws-secrets-agent`
    - the exact names this deprecation entry lists - so the bare name match flagged
    a LIVE external server for teardown. A running container is treated as foreign
    (and must never be torn down) when it carries a compose-project label (CPP
    ships no compose since #469, so any active compose project is external) or runs
    a non-CPP image (repo != image_prefix).

    Scope is deliberately RUNNING-only, per the issue: an exited/created container
    is not live and is the ordinary stale-orphan case, and - lacking a reliable CPP
    compose-project name - cannot be told apart from a CPP leftover by label. When
    provenance is unknown (container_meta empty), there is no positive foreign
    evidence, so the container is classified exactly as before."""
    if not _is_running(state):
        return False
    meta = host.container_meta.get(name, {})
    if str(meta.get("project") or "").strip():
        return True
    image_repo = _image_repo(str(meta.get("image") or ""))
    return bool(image_repo) and image_repo != entry["image_prefix"]


def _matching_containers(entry: dict, host: HostState) -> tuple[list[dict], list[dict]]:
    """(owned, foreign) present containers for this entry, respecting an optional
    CPP_CONTAINER_PREFIX. `owned` are CPP orphan candidates a teardown may
    stop/remove; `foreign` are live external containers that merely share the name
    and must be left running (issue #520)."""
    owned: list[dict] = []
    foreign: list[dict] = []
    for want in entry["containers"]:
        for name, state in host.containers.items():
            if name == want or name.endswith(want):
                if _container_is_foreign_live(name, state, entry, host):
                    meta = host.container_meta.get(name, {})
                    foreign.append({
                        "name": name,
                        "state": state,
                        "image": str(meta.get("image") or ""),
                        "project": str(meta.get("project") or ""),
                    })
                else:
                    owned.append({"name": name, "state": state})
    return owned, foreign


def _collision_evidence(entry: dict, host: HostState) -> list[str]:
    """Live-deployment evidence that a retired NAME is currently in use by
    something the teardown must not touch (issue #673 fix 3).

    The #520/#634 provenance guards answer this from the container itself, which
    only works when the container is visible AND docker-managed. A retired name
    can also be live as a plain host process or another machine's proxy - in which
    case the port answering, or a live registration aimed at that port, is the only
    signal there is. Either one downgrades ORPHANED to NAME COLLISION, so the
    curated list can never offer to tear down the user's own deployment."""
    evidence: list[str] = []
    port = str(entry.get("port") or "").strip()
    if not port.isdigit():
        return evidence

    if int(port) in host.listening_ports:
        evidence.append(f"port {port} answers on localhost")

    needle = f":{port}"
    for target in sorted(host.registration_targets):
        if needle in target:
            evidence.append(f"live registration targets port {port} ({target})")
            break
    return evidence


def classify(deprecated: list[dict], host: HostState) -> list[dict]:
    findings: list[dict] = []
    for entry in deprecated:
        name = entry["name"]
        in_compose = name in host.current_services

        containers, foreign_containers = _matching_containers(entry, host)
        # Image tags run by a foreign-live container are protected, not CPP
        # leftovers (issue #634, the image half of #520): only the remaining
        # tags count toward presence or a teardown offer.
        images, protected_images = _split_protected_images(
            entry, foreign_containers, host.images.get(entry["image_prefix"], [])
        )
        claude = [r for r in entry["claude_registrations"] if r in host.claude_regs]
        codex = [r for r in entry["codex_registrations"] if r in host.codex_regs]
        # A live external container that only shares the name is NOT a present CPP
        # artifact, so it must not make the entry look orphaned (issue #520).
        present = bool(containers or images or claude or codex)
        collision = _collision_evidence(entry, host)

        # An unreadable docker socket is not an empty host (issue #673): with no
        # trustworthy inventory NOTHING may be concluded, exactly as when the
        # compose service set cannot be read. UNKNOWN keeps teardown's hard
        # refusal in force for every curated server.
        if not host.services_known or not host.docker_readable:
            status = UNKNOWN
        elif in_compose:
            status = OK
        elif present and collision:
            status = COLLISION
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
                "foreign_containers": foreign_containers,
                "images": images,
                "protected_images": protected_images,
                "claude_registrations": claude,
                "codex_registrations": codex,
                "collision_evidence": collision if status == COLLISION else [],
                "docker_state": host.docker_state,
                "docker_error": host.docker_error,
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


def plan_teardown(finding: dict, prune_all_images: bool, docker_cmd: str = "docker") -> list[str]:
    """Return the ordered shell commands a teardown WOULD run. Pure - no side effects.

    `docker_cmd` is the argv prefix the inventory was actually read with - `sudo -n
    docker` when the plain socket was refused (issue #673). Emitting the prefix here
    means `--plan` shows verbatim what `--teardown` will execute, so the elevation is
    visible before the user confirms rather than discovered afterwards."""
    cmds: list[str] = []
    for c in finding["containers"]:
        if _is_running(c["state"]):
            cmds.append(f"{docker_cmd} stop {c['name']}")
        cmds.append(f"{docker_cmd} rm -f {c['name']}")

    to_remove = images_to_remove(finding["images"], prune_all_images)
    for img in to_remove:
        cmds.append(f"{docker_cmd} rmi {finding['image_prefix']}:{img['tag']}")
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
    docker_cmd: str = "docker",
) -> int:
    """Guarded teardown of ORPHANED DOCKER MCP servers.

    Hard-refuses any name that is not classified ORPHANED (unlisted, still in
    compose/OK, ABSENT, UNKNOWN, or NAME COLLISION) BEFORE running anything - this
    is what keeps a user's own custom MCP registration from ever being removed, and
    what makes an unreadable docker socket safe: every server reads UNKNOWN, so
    every teardown is refused. Each teardown step is best-effort so one failure does
    not strand the rest."""
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
            detail = ""
            if finding["status"] == UNKNOWN and finding.get("docker_error"):
                detail = f" (docker unreadable: {finding['docker_error']})"
            elif finding["status"] == COLLISION and finding.get("collision_evidence"):
                detail = f" ({'; '.join(finding['collision_evidence'])})"
            print(
                f"REFUSED {name}: classified {finding['status']}{detail}; only "
                "ORPHANED DOCKER MCP servers may be torn down",
                file=sys.stderr,
            )
            refused += 1
            continue

        cmds = plan_teardown(finding, prune_all_images, docker_cmd)
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
def render_table(findings: list[dict], verbose: bool, host: HostState | None = None) -> str:
    lines = ["Docker MCP Drift Report", "=======================", ""]

    # An unreadable docker socket is reported BEFORE anything else and suppresses
    # the clean banner entirely (issue #673). The old report was indistinguishable
    # from a genuinely clean host, and a caller relayed it as a positive finding.
    unreadable = host is not None and not host.docker_readable
    if unreadable:
        assert host is not None
        lines.append(f"DOCKER UNREADABLE: {host.docker_error or 'docker ps failed'}")
        lines.append(
            f"  Cannot assess {len(findings)} curated server(s) - every one is "
            "UNKNOWN. This is NOT a clean result: the inventory was never read."
        )
        lines.append(
            "  Fix: give this user docker access (e.g. the docker group), start "
            "the daemon, or re-run where docker is readable."
        )
        lines.append("")

    shown = [f for f in findings if verbose or f["status"] in (ORPHANED, COLLISION)]
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
        if f.get("protected_images"):
            present.append(
                f"({len(f['protected_images'])} protected: run by external stack)"
            )
        if f["claude_registrations"]:
            present.append(f"claude:{','.join(f['claude_registrations'])}")
        if f["codex_registrations"]:
            present.append(f"codex:{','.join(f['codex_registrations'])}")
        lines.append(f"  {f['server']} - present: {', '.join(present) or 'unknown'}")
        if f["replacement"]:
            lines.append(f"    replacement: {f['replacement']}")

    protected = [f for f in findings if f.get("foreign_containers")]
    if protected:
        lines.append(
            "Protected (live external container(s) sharing a deprecated name - "
            "left running, never torn down):"
        )
        for f in protected:
            for c in f["foreign_containers"]:
                origin = (
                    f"compose project '{c['project']}'" if c["project"]
                    else f"image '{c['image']}'"
                )
                lines.append(f"  {f['server']}: {c['name']} ({c['state']}, {origin})")

    collisions = [f for f in findings if f["status"] == COLLISION]
    if collisions:
        lines.append(
            "Name collisions (a retired name that live evidence says is in use - "
            "reported, never torn down):"
        )
        for f in collisions:
            lines.append(f"  {f['server']}: {'; '.join(f['collision_evidence'])}")
            lines.append(
                "    possibly your own deployment reusing the name - teardown is "
                "refused; remove it by hand if you are sure it is a leftover."
            )

    if any(f["status"] == UNKNOWN for f in findings) and not unreadable:
        lines.append(
            "Note: current service set could not be determined (docker/compose "
            "unavailable); nothing classified as orphaned."
        )
    if host is not None and host.docker_state == DOCKER_ABSENT:
        # Named rather than hidden: this IS a clean read (nothing can run under a
        # runtime that is not installed) but the reader deserves to know which
        # question was answered by absence rather than by inspection (issue #673).
        lines.append(
            "Note: docker is not installed - the container/image inventory is "
            "empty by absence, not unread. Registrations were still checked."
        )
    if host is not None and host.docker_prefix[:1] == ("sudo",):
        lines.append(
            "Note: the plain docker socket was refused; this inventory was read "
            "via 'sudo -n docker'. Teardown commands carry the same prefix."
        )

    if unreadable:
        lines.append(
            "Assessment INCOMPLETE - no server was evaluated. Nothing here means "
            "'clean'."
        )
    elif not orphans:
        clean = "No orphaned Docker MCP servers detected."
        if collisions:
            clean += (
                f" ({len(collisions)} name collision(s) reported above are NOT "
                "orphans and were not torn down.)"
            )
        lines.append(clean)
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
    parser.add_argument("--no-sudo", action="store_true",
                        help="Never retry a permission-refused docker read via 'sudo -n'")
    parser.add_argument("--no-port-probe", action="store_true",
                        help="Skip the localhost port probe behind NAME COLLISION")
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
    probe_ports = set()
    if not args.no_port_probe:
        probe_ports = {int(e["port"]) for e in deprecated if str(e["port"]).isdigit()}
    host = collect_host_state(
        compose_file, allow_sudo=not args.no_sudo, probe_ports=probe_ports
    )
    findings = classify(deprecated, host)
    docker_cmd = " ".join(host.docker_prefix)

    if args.plan:
        if host.docker_prefix[:1] == ("sudo",):
            print("# inventory read via: sudo -n docker (plain docker socket refused)")
        return teardown(args.plan, findings, args.prune_all_images,
                        execute=False, docker_cmd=docker_cmd)

    if args.teardown:
        return teardown(args.teardown, findings, args.prune_all_images,
                        execute=True, docker_cmd=docker_cmd)

    # A refused docker read is its own outcome, not a clean one (issue #673). Exit
    # 3 - distinct from both 0 (clean) and 1 (orphans found) - so a caller can
    # branch on "could not assess" instead of relaying silence as a positive
    # finding, which is exactly what /cpp:update did.
    unreadable_rc = 3 if not host.docker_readable else 0

    if args.list_orphans:
        # stdout stays names-only: consumers line-parse it. The warning goes to
        # stderr, and the exit code is what a script should branch on.
        for f in removable(findings):
            print(f["server"])
        if unreadable_rc:
            print(
                f"WARNING: docker unreadable ({host.docker_error}); "
                f"{len(findings)} curated server(s) UNKNOWN - this empty list "
                "means 'could not look', not 'nothing found'.",
                file=sys.stderr,
            )
        return unreadable_rc

    if args.json:
        print(json.dumps(findings, indent=2))
        return unreadable_rc or (1 if removable(findings) else 0)

    # default / --check
    print(render_table(findings, verbose=args.verbose, host=host))
    return unreadable_rc or (1 if removable(findings) else 0)


if __name__ == "__main__":
    sys.exit(main())
