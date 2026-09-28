#!/usr/bin/env python3
"""capability-readiness.py - is flow / second-opinion / browser QA USABLE? (issue #1290)

/cpp:status used to answer "is it installed?" and let that stand for "does it
work?". Two measured cases show the gap. A playwright MCP registration was
present and failed to connect (`CONNECTION_CLOSED`), because the server exits
before it answers `initialize`. And status.md's second-opinion reachability
check curled `http://127.0.0.1:8080}/mcp` - a url it had grepped out of
`${SECOND_OPINION_URL:-...}` with the brace attached - so it could never report
a reachable server at all.

This reports ONE state per capability, from the observations that produced it:

  disabled          not installed / not registered - an optional capability's
                    absence is not a failure and does not affect the others
  unexamined        installed, but the layer that would prove it usable was not
                    probed (unreadable config, credentials in the endpoint, an
                    unsupported transport). NOT ready.
  stale-or-unknown  the CPP checkout is behind / ahead / diverged, its freshness
                    could not be established, or an installed artifact is
                    missing or stale against it
  conflicting       one MCP name defined at 2+ scopes with different endpoints
                    (#1256): which one a session reaches depends on where it
                    started, so no single probe result describes "the" server
  unreachable       the bounded probe was attempted and did not succeed
  ready             the named probe succeeded. `ready` is ready FOR THAT
                    OPERATION ONLY; every row lists what stayed unexamined.

The probes are bounded and harmless: the flow row runs one installed helper
read-only; the MCP rows do an MCP `initialize` + `tools/list` handshake and
call NO tool, so no model request is made and nothing is paid for. A stdio
server launched through a package launcher (npx, uvx, bunx, pnpx) is NOT
started - an offline flag does not stop npx installing from a warm cache - so
that row reads `unexamined` and says why. Any other stdio server starts with
`UV_OFFLINE`, `UV_NO_SYNC` and `npm_config_offline` set, which reduce but do
not sandbox what an arbitrary command may do. Every stdio child runs in its own
process group under a hard timeout and is killed and reaped; the HTTP handshake
has one overall deadline, and an SSE stream is read only until the answer.

Nothing here is re-implemented: the flow row consumes
`flow-helpers-install.sh --check`, `cpp-commands-link.sh --check` and
`cpp-checkout-freshness.sh` (#1282, which FETCHES - it updates the checkout's
origin/main remote-tracking ref, never its working tree); the MCP rows consume
mcp-drift.py's scope reader (#1256) and its redaction. Secret values, userinfo,
query strings and header values never reach the output: endpoints are printed
only through mcp-drift's allowlist redaction, and probe failures are reported
by exception TYPE, never by message.

Human and machine output come from one list of rows: `--json` serialises it,
the table renders it. Neither reclassifies.

Usage:
  capability-readiness.py [--json] [--home DIR] [--checkout DIR]
                          [--project-dir DIR] [--timeout SECONDS]

Last line (both modes print it; in --json mode it follows the JSON object):
  CAPABILITY_READINESS: ready | degraded | unknown
Exit: 0 ready (every ENABLED capability ready, at least one enabled),
      3 degraded (any stale-or-unknown / conflicting / unreachable),
      4 unknown (otherwise: something unexamined, or nothing enabled),
      2 usage.
"""
#: NEGATIVE-CONTROL: controls/capability-readiness

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import select
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCRIPTS_DIR = Path(__file__).resolve().parent

DISABLED = "disabled"
UNEXAMINED = "unexamined"
STALE = "stale-or-unknown"
CONFLICTING = "conflicting"
UNREACHABLE = "unreachable"
READY = "ready"
STATES = (DISABLED, UNEXAMINED, STALE, CONFLICTING, UNREACHABLE, READY)
DEGRADING = (STALE, CONFLICTING, UNREACHABLE)

#: The flow probe: an installed helper that reads only its own table.
FLOW_PROBE = "flow-driver-capability.sh"
FLOW_MARKER = "flow-start-resolve.sh"

MCP_ROWS = (
    # (capability, MCP server name, the layer a handshake cannot reach)
    ("second-opinion", "second-opinion",
     "a review request (a paid model call; not made by status)"),
    ("browser-qa", "playwright",
     "a browser launch and page load (the handshake does not start a browser)"),
)
HANDSHAKE = "MCP initialize + tools/list (no tool called)"
#: Launchers that fetch or materialise a package on start. An offline flag does
#: not stop npx installing from a warm cache into its exec directory, so status
#: does not start them at all (#1290 boundary: no dependency installation).
INSTALLING_LAUNCHERS = frozenset({"npx", "uvx", "bunx", "pnpx"})
_READ_CAP = 1 << 20


def _load_mcp_drift():
    spec = importlib.util.spec_from_file_location("mcp_drift", SCRIPTS_DIR / "mcp-drift.py")
    if spec is None or spec.loader is None:
        raise ImportError("mcp-drift.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _last_marker(text: str, prefix: str) -> str | None:
    """The value of the LAST `PREFIX: value` line - the helpers' contract."""
    found = None
    for line in text.splitlines():
        if line.startswith(prefix + ":"):
            found = line[len(prefix) + 1:].strip()
    return found


def _run(argv: list[str], env: dict[str, str], timeout: float, cwd: Path | None = None
         ) -> tuple[int | None, str]:
    """(exit code or None on timeout/unrunnable, stdout). Own process group, killed on timeout."""
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, env=env, cwd=cwd,
                                start_new_session=True, text=True)
    except OSError:
        return None, ""
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out or ""
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        return None, ""


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _obs(name: str, verdict: str, scope: str, detail: str = "") -> dict:
    return {"name": name, "verdict": verdict, "scope": scope, "detail": detail}


# --------------------------------------------------------------------------- #
# flow
# --------------------------------------------------------------------------- #

def resolve_checkout(explicit: str | None, home: Path) -> tuple[Path | None, str]:
    if explicit:
        return Path(explicit).resolve(), "--checkout"
    link = home / ".claude" / "scripts" / "flow-helpers-install.sh"
    if link.is_symlink():
        cand = link.resolve().parent.parent
        if (cand / "CLAUDE.md").is_file() and (cand / "scripts").is_dir():
            return cand, f"the {link.name} link in ~/.claude/scripts"
    cand = SCRIPTS_DIR.parent
    if (cand / "CLAUDE.md").is_file() and (cand / ".git").exists():
        return cand, "the checkout holding this script"
    return None, "none found"


def _revision(checkout: Path) -> str | None:
    rc, out = _run(["git", "-C", str(checkout), "rev-parse", "HEAD"], dict(os.environ), 10)
    return out.strip() if rc == 0 and out.strip() else None


def flow_row(home: Path, checkout_arg: str | None, timeout: float) -> dict:
    scripts = home / ".claude" / "scripts"
    # lexists, not exists: a DANGLING link is a broken install, never an absent one
    installed = os.path.lexists(scripts / FLOW_MARKER) or os.path.lexists(home / ".claude" / "commands" / "flow")
    checkout, how = resolve_checkout(checkout_arg, home)
    row: dict[str, Any] = {"capability": "flow", "state": None, "tested": None, "source": None,
           "artifacts": [str(scripts) + "/<flow helpers>", str(home / ".claude" / "commands") + "/<cpp families>"],
           "config": [], "observations": [], "unexamined": [], "next": None}
    obs = row["observations"]
    if checkout is not None:
        rev = _revision(checkout)
        row["source"] = {"checkout": str(checkout), "revision": rev, "resolved_by": how}
    else:
        row["source"] = {"checkout": None, "revision": None, "resolved_by": how}
    if not installed:
        row["state"] = DISABLED
        row["next"] = "not installed: /cpp:init installs the flow helpers and command links"
        obs.append(_obs("install", "absent", str(scripts), f"no {FLOW_MARKER} and no commands/flow"))
        return row
    if checkout is None:
        row["state"] = STALE
        row["next"] = "no CPP checkout found to compare the install against; pass --checkout"
        obs.append(_obs("checkout", "unknown", "checkout resolution", how))
        return row

    env = dict(os.environ)
    env["FLOW_HELPERS_HOME"] = str(home)
    env["CPP_COMMANDS_LINK_HOME"] = str(home)
    env["CPP_FRESHNESS_FETCH_TIMEOUT"] = str(int(max(1, timeout)))
    stale = []

    rc, out = _run(["bash", str(checkout / "scripts" / "flow-helpers-install.sh"), "--check"], env, timeout * 3)
    verdict = _last_marker(out, "FLOW_HELPERS") or ("timeout" if rc is None else "no verdict")
    examined = _last_marker(out, "FLOW_HELPERS_EXAMINED")
    obs.append(_obs("helpers", verdict, f"{scripts} against {checkout}/scripts",
                    f"{examined} examined" if examined else ""))
    if verdict != "ok":
        stale.append(f"helpers {verdict}")

    rc, out = _run(["bash", str(checkout / "scripts" / "cpp-commands-link.sh"), "--check"], env, timeout * 3)
    verdict = _last_marker(out, "CPP_COMMANDS_LINK") or ("timeout" if rc is None else "no verdict")
    obs.append(_obs("command-links", verdict, f"{home}/.claude/commands against {checkout}/.claude/commands"))
    if verdict != "ok":
        stale.append(f"command links {verdict}")

    rc, out = _run(["bash", str(SCRIPTS_DIR / "cpp-checkout-freshness.sh"), "--path", str(checkout)],
                   env, timeout * 2 + 10)
    verdict = (_last_marker(out, "CPP_CHECKOUT_FRESHNESS")
               or ("unknown: timeout" if rc is None else "unknown: no verdict"))
    obs.append(_obs("checkout-freshness", verdict, f"{checkout} HEAD against origin/main (fetched)"))
    if verdict != "current":
        stale.append(f"checkout {verdict}")

    probe = scripts / FLOW_PROBE
    rc, out = _run(["bash", str(probe), "list"], env, timeout) if probe.exists() else (None, "")
    ran = rc == 0 and bool(out.strip())
    obs.append(_obs("probe", "ok" if ran else ("absent" if not probe.exists() else f"failed (exit {rc})"),
                    f"{probe} list"))
    row["unexamined"].append("any helper beyond the probe; GitHub reachability")
    if stale:
        row["state"] = STALE
        row["next"] = "; ".join(stale) + " - /cpp:update refreshes the checkout, /flow:repair the helpers"
    elif not ran:
        row["state"] = UNREACHABLE
        row["next"] = f"the installed {FLOW_PROBE} did not run - /flow:repair"
    else:
        row["state"] = READY
        row["tested"] = f"installed helper runs: {FLOW_PROBE} list"
    return row


# --------------------------------------------------------------------------- #
# MCP handshake
# --------------------------------------------------------------------------- #

_INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "cpp-capability-readiness", "version": "1"}}}
_INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
_LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}


def _handshake_result(init: object, tools: object) -> tuple[str, str]:
    if not (isinstance(init, dict) and isinstance(init.get("result"), dict)):
        return "unreachable", "initialize was not answered with a result"
    if not (isinstance(tools, dict) and isinstance(tools.get("result"), dict)
            and isinstance(tools["result"].get("tools"), list)):
        return "unreachable", "tools/list was not answered with a tool list"
    return "ok", f"{len(tools['result']['tools'])} tool(s) listed"


def probe_stdio(cmd: str, args: tuple, spec_env: dict[str, str], cwd: Path, timeout: float
                ) -> tuple[str, str]:
    env = dict(os.environ)
    env.update(spec_env)
    # status never installs anything (#1290 boundary)
    env.update({"UV_OFFLINE": "1", "UV_NO_SYNC": "1", "npm_config_offline": "true"})
    try:
        proc = subprocess.Popen([cmd, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=env, cwd=cwd, start_new_session=True)
    except OSError as exc:
        return "unreachable", f"could not start ({type(exc).__name__})"
    deadline = time.monotonic() + timeout
    buf = b""
    total = 0

    def send(msg: dict) -> bool:
        try:
            assert proc.stdin is not None
            proc.stdin.write((json.dumps(msg) + "\n").encode())
            proc.stdin.flush()
            return True
        except (BrokenPipeError, OSError):
            return False

    def recv(want_id: int):
        nonlocal buf, total
        assert proc.stdout is not None
        fd = proc.stdout.fileno()
        while True:
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == want_id:
                    return msg
            left = deadline - time.monotonic()
            if left <= 0:
                return "timeout"
            ready, _, _ = select.select([fd], [], [], min(left, 0.5))
            if not ready:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                return "eof"
            total += len(chunk)
            if total > _READ_CAP:
                return "oversized"
            buf += chunk

    try:
        if not send(_INIT):
            proc.wait(timeout=2)
            return "unreachable", f"exited (code {proc.returncode}) before initialize"
        init = recv(1)
        if isinstance(init, str):
            if init == "eof":
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                return "unreachable", f"exited (code {proc.returncode}) before answering initialize"
            if init == "timeout":
                return "unreachable", f"initialize: timeout after {timeout:g}s"
            return "unreachable", f"initialize: {init}"
        send(_INITIALIZED)
        send(_LIST)
        tools = recv(2)
        if isinstance(tools, str):
            return "unreachable", f"tools/list: {tools}"
        return _handshake_result(init, tools)
    finally:
        _kill_group(proc)


def _read_http_json(resp, want_id: int, deadline: float):
    """The JSON-RPC message with id `want_id`, read INCREMENTALLY: an SSE stream
    may stay open after delivering it, so reading to EOF would time out a
    healthy server. Returns None when it never arrives within the cap."""
    ctype = resp.headers.get("Content-Type", "")
    if "text/event-stream" not in ctype:
        try:
            return json.loads(resp.read(_READ_CAP))
        except ValueError:
            return None
    total = 0
    data: list[str] = []
    while time.monotonic() < deadline and total < _READ_CAP:
        raw = resp.readline(65536)
        if not raw:
            break
        total += len(raw)
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if line.startswith("data:"):
            data.append(line[5:].strip())
            continue
        if line == "" and data:
            try:
                msg = json.loads("\n".join(data))
            except ValueError:
                msg = None
            data = []
            if isinstance(msg, dict) and msg.get("id") == want_id:
                return msg
    return None


def _http_handshake(url: str, timeout: float, deadline: float) -> tuple[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    def post(msg: dict, sid: str | None, version: str | None):
        h = dict(headers)
        if sid:
            h["Mcp-Session-Id"] = sid
        if version:
            h["MCP-Protocol-Version"] = version
        req = urllib.request.Request(url, data=json.dumps(msg).encode(), headers=h, method="POST")
        left = max(0.1, deadline - time.monotonic())
        return urllib.request.urlopen(req, timeout=min(timeout, left))  # noqa: S310 - http(s) only, checked by caller

    try:
        with post(_INIT, None, None) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            init = _read_http_json(resp, 1, deadline)
        result = init.get("result") if isinstance(init, dict) else None
        version = result.get("protocolVersion") if isinstance(result, dict) else None
        version = version if isinstance(version, str) else None
        with post(_INITIALIZED, sid, version):
            pass
        with post(_LIST, sid, version) as resp:
            tools = _read_http_json(resp, 2, deadline)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return "auth-required", f"HTTP {exc.code}: the handshake needs authentication, which status does not send"
        return "unreachable", f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = exc.reason
        errno = f" (errno {reason.errno})" if isinstance(reason, OSError) and reason.errno else ""
        return "unreachable", f"{type(reason).__name__}{errno}"
    except (OSError, ValueError) as exc:
        return "unreachable", type(exc).__name__
    return _handshake_result(init, tools)


def probe_http(url: str, timeout: float) -> tuple[str, str]:
    """One overall deadline for the whole handshake. A socket timeout bounds
    each read, not the sum: a server trickling a byte at a time would hold
    status indefinitely. The handshake runs in a daemon thread and is abandoned
    - not waited for - when the deadline passes."""
    deadline = time.monotonic() + timeout
    box: list[tuple[str, str]] = []
    worker = threading.Thread(target=lambda: box.append(_http_handshake(url, timeout, deadline)), daemon=True)
    worker.start()
    worker.join(timeout + 0.5)
    if not box:
        return "unreachable", f"handshake did not complete within {timeout:g}s"
    return box[0]


def _carries_credentials(spec: dict, endpoint: tuple) -> bool:
    if spec.get("headers"):
        return True
    if endpoint[0] != "stdio":
        u = urlsplit(endpoint[1])
        return bool(u.username or u.password or u.query)
    return False


def probe_endpoint(mcp, spec: object, endpoint: tuple, cwd: Path, timeout: float) -> tuple[str, str]:
    """(verdict, detail): ok | unreachable | auth-required | unexamined."""
    spec = spec if isinstance(spec, dict) else {}
    if _carries_credentials(spec, endpoint):
        return "unexamined", ("endpoint carries credentials (userinfo, query or headers); "
                              "an authenticated probe is not authorised for status")
    if endpoint[0] == "stdio" and Path(endpoint[1]).name in INSTALLING_LAUNCHERS:
        return "unexamined", (f"launched through {Path(endpoint[1]).name}, which can install the package on start; "
                              "status installs nothing, so the handshake is not attempted")
    if endpoint[0] == "stdio":
        raw_env = spec.get("env") or {}
        try:
            env = ({str(k): mcp._expand_env(str(v), dict(os.environ)) for k, v in raw_env.items()}
                   if isinstance(raw_env, dict) else {})
        except mcp._Unresolved:
            return "unexamined", "the server's env uses an unset ${VAR} with no default"
        return probe_stdio(endpoint[1], endpoint[2], env, cwd, timeout)
    if endpoint[0] == "http" and urlsplit(endpoint[1]).scheme in ("http", "https"):
        return probe_http(endpoint[1], timeout)
    return "unexamined", f"transport '{endpoint[0]}' is not probed"


def _raw_specs(home: Path, project_dir: Path, name: str) -> dict[str, object]:
    """{scope: raw spec} - mcp-drift gives the ENDPOINT; the probe also needs env/headers."""
    out: dict[str, object] = {}
    try:
        data = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if isinstance(data, dict):
        if isinstance(data.get("mcpServers"), dict) and name in data["mcpServers"]:
            out["user"] = data["mcpServers"][name]
        proj = data.get("projects")
        if isinstance(proj, dict):
            local = proj.get(str(project_dir.resolve()))
            if isinstance(local, dict) and isinstance(local.get("mcpServers"), dict) and name in local["mcpServers"]:
                out["local"] = local["mcpServers"][name]
    try:
        pdata = json.loads((project_dir / ".mcp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pdata = None
    if isinstance(pdata, dict) and isinstance(pdata.get("mcpServers"), dict) and name in pdata["mcpServers"]:
        out["project"] = pdata["mcpServers"][name]
    return out


def mcp_row(mcp, capability: str, server: str, beyond: str, home: Path, project_dir: Path,
            timeout: float, scan) -> dict:
    defs, problems, unreadable_names, scope_unreadable = scan
    scopes = defs.get(server, {})
    row: dict[str, Any] = {"capability": capability, "state": None, "tested": None,
           "source": {"mcp_server": server, "scopes_read": [str(home / ".claude.json") + " (user, local)",
                                                             str(project_dir / ".mcp.json") + " (project)"]},
           "artifacts": [], "config": [], "observations": [], "unexamined": [beyond], "next": None}
    obs = row["observations"]
    for scope in mcp.SCOPE_ORDER:
        if scope in scopes:
            row["config"].append(f"{scope}: {mcp.redact_endpoint(scopes[scope])}")
    if server in unreadable_names or scope_unreadable:
        row["state"] = UNEXAMINED
        row["next"] = (f"MCP configuration could not be read ({len(problems)} problem(s)); "
                       "run mcp-drift.py --scope-check for detail")
        obs.append(_obs("config", "unreadable", "user/local/project scopes"))
        return row
    if not scopes:
        row["state"] = DISABLED
        row["next"] = f"'{server}' is not registered at any scope - /cpp:init registers it"
        obs.append(_obs("config", "absent", "user/local/project scopes"))
        return row
    raw = _raw_specs(home, project_dir, server)
    results = {}
    for scope in mcp.SCOPE_ORDER:
        if scope not in scopes:
            continue
        verdict, detail = probe_endpoint(mcp, raw.get(scope), scopes[scope], project_dir, timeout)
        results[scope] = verdict
        obs.append(_obs(f"handshake[{scope}]", verdict, f"{scope}-scope definition", detail))
    distinct = len(set(scopes.values())) > 1
    if distinct:
        row["state"] = CONFLICTING
        row["next"] = (f"'{server}' is defined at {len(scopes)} scopes with different endpoints; which one a "
                       f"session reaches depends on where it starts. Values: claude mcp get {server}. "
                       f"Remedy only on your say-so: claude mcp remove {server} -s <scope-to-drop>")
        return row
    # One endpoint, possibly probed from several scopes (each with its own env):
    # ready only when EVERY probe succeeded; any failure outranks a success.
    verdicts = set(results.values())
    if "unreachable" in verdicts:
        verdict = "unreachable"
    elif verdicts == {"ok"}:
        verdict = "ok"
    else:
        verdict = "unexamined"
    if verdict == "ok":
        row["state"] = READY
        row["tested"] = HANDSHAKE
    elif verdict in ("unexamined", "auth-required"):
        row["state"] = UNEXAMINED
        row["unexamined"].insert(0, "the MCP handshake")
        row["next"] = ("the handshake was not attempted (see the observation); "
                       "check it by hand or with an authorised client")
    else:
        row["state"] = UNREACHABLE
        row["next"] = f"the '{server}' server did not complete the handshake - check it with: claude mcp get {server}"
    return row


# --------------------------------------------------------------------------- #

def overall(rows: list[dict]) -> str:
    states = [r["state"] for r in rows]
    if any(s in DEGRADING for s in states):
        return "degraded"
    enabled = [s for s in states if s != DISABLED]
    if enabled and all(s == READY for s in enabled):
        return "ready"
    return "unknown"


EXIT = {"ready": 0, "degraded": 3, "unknown": 4}


def render(rows: list[dict]) -> str:
    lines = [f"{'CAPABILITY':<16}{'STATE':<18}TESTED"]
    for r in rows:
        lines.append(f"{r['capability']:<16}{r['state']:<18}{r['tested'] or '-'}")
    for r in rows:
        lines.append("")
        lines.append(r["capability"])
        src = r["source"] or {}
        if "checkout" in src:
            rev = (src.get("revision") or "unknown")[:12]
            where = src.get('checkout') or 'none'
            lines.append(f"  source:     {where} @ {rev} (resolved by {src.get('resolved_by')})")
        else:
            read = "; ".join(src.get("scopes_read", []))
            lines.append(f"  source:     MCP server '{src.get('mcp_server')}' read from {read}")
        for a in r["artifacts"]:
            lines.append(f"  artifact:   {a}")
        for c in r["config"]:
            lines.append(f"  config:     {c}")
        for o in r["observations"]:
            detail = f" - {o['detail']}" if o["detail"] else ""
            lines.append(f"  observed:   {o['name']}: {o['verdict']} [scope: {o['scope']}]{detail}")
        for u in r["unexamined"]:
            lines.append(f"  unexamined: {u}")
        if r["next"]:
            lines.append(f"  next:       {r['next']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="emit the rows as one JSON object")
    ap.add_argument("--home", default=None, help="home to examine (default: $HOME)")
    ap.add_argument("--checkout", default=None, help="CPP checkout (default: resolved from the installed helpers)")
    ap.add_argument("--project-dir", default=None, help="project whose .mcp.json/local scope is read (default: cwd)")
    ap.add_argument("--timeout", type=float, default=10.0, help="per-probe timeout in seconds (default 10)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    home = Path(args.home or os.environ.get("HOME", "~")).expanduser()
    project_dir = Path(args.project_dir or os.getcwd())

    rows = [flow_row(home, args.checkout, args.timeout)]
    try:
        mcp = _load_mcp_drift()
        scan = mcp.collect_scope_definitions(home / ".claude.json", project_dir, dict(os.environ))
    except Exception as exc:  # noqa: BLE001 - an unreadable reader is unexamined, never clean
        for capability, _server, beyond in MCP_ROWS:
            rows.append({"capability": capability, "state": UNEXAMINED, "tested": None, "source": {},
                         "artifacts": [], "config": [],
                         "observations": [_obs("config", "reader-failed", "mcp-drift.py", type(exc).__name__)],
                         "unexamined": ["the MCP handshake", beyond],
                         "next": "mcp-drift.py could not be loaded beside this script"})
    else:
        for capability, server, beyond in MCP_ROWS:
            rows.append(mcp_row(mcp, capability, server, beyond, home, project_dir, args.timeout, scan))

    verdict = overall(rows)
    if args.json:
        print(json.dumps({"verdict": verdict, "states": list(STATES), "capabilities": rows}, indent=2))
    else:
        print(render(rows))
    print(f"CAPABILITY_READINESS: {verdict}")
    return EXIT[verdict]


if __name__ == "__main__":
    sys.exit(main())
