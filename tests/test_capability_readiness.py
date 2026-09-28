"""Tests for scripts/capability-readiness.py (issue #1290).

Every fixture is local: a bare origin plus a clone for the CPP checkout, a
throwaway HOME, a fake stdio MCP server written here, a loopback HTTP MCP
server, and a closed loopback port. No production credential or service is
used, and no model is called.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capability-readiness.py"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="needs bash and git",
)

FAKE_SERVER = r'''
import json, sys
mode = sys.argv[1] if len(sys.argv) > 1 else "ok"
if mode == "dead":
    sys.exit(5)
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        out = {"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-06-18",
               "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "0"}}}
    elif msg.get("method") == "tools/list":
        out = {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [{"name": "t1"}, {"name": "t2"}]}}
    else:
        continue
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()
'''


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x.invalid"})


@pytest.fixture(scope="session")
def cpp_seed_tree(tmp_path_factory) -> Path:
    """A minimal CPP tree: the real scripts/, commands and CLAUDE.md."""
    tree = tmp_path_factory.mktemp("cpp-tree")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "scripts", tree / "scripts", ignore=ignore, symlinks=True)
    shutil.copytree(ROOT / ".claude" / "commands", tree / ".claude" / "commands", ignore=ignore, symlinks=True)
    shutil.copy2(ROOT / "CLAUDE.md", tree / "CLAUDE.md")
    return tree


class Cpp:
    """seed (writer) -> origin.git (bare) -> checkout (what the host installs from)."""

    def __init__(self, base: Path, tree: Path):
        self.base = base
        self.origin = base / "origin.git"
        self.seed = base / "seed"
        self.checkout = base / "checkout"
        shutil.copytree(tree, self.seed, symlinks=True)
        _git("init", "-q", "--initial-branch=main", str(self.seed))
        _git("add", "-A", cwd=self.seed)
        _git("commit", "-q", "-m", "one", cwd=self.seed)
        _git("init", "-q", "--bare", "--initial-branch=main", str(self.origin))
        _git("remote", "add", "origin", str(self.origin), cwd=self.seed)
        _git("push", "-q", "origin", "main", cwd=self.seed)
        _git("clone", "-q", str(self.origin), str(self.checkout))

    def advance(self) -> None:
        (self.seed / "ADVANCED").write_text("two\n")
        _git("add", "-A", cwd=self.seed)
        _git("commit", "-q", "-m", "two", cwd=self.seed)
        _git("push", "-q", "origin", "main", cwd=self.seed)

    def install(self, home: Path) -> None:
        """The real install/update entry points, run as /cpp:init and /cpp:update run them."""
        env = {**os.environ, "HOME": str(home)}
        for var in ("FLOW_HELPERS_HOME", "FLOW_HELPERS_SOURCE", "CPP_COMMANDS_LINK_HOME", "CLAUDE_PLUGIN_ROOT"):
            env.pop(var, None)
        for helper in ("flow-helpers-install.sh", "cpp-commands-link.sh"):
            proc = subprocess.run(["bash", str(self.checkout / "scripts" / helper)], env=env,
                                  capture_output=True, text=True, check=False)
            assert proc.returncode == 0, f"{helper} failed:\n{proc.stdout}\n{proc.stderr}"


@pytest.fixture
def cpp(tmp_path, cpp_seed_tree) -> Cpp:
    return Cpp(tmp_path / "cpp", cpp_seed_tree)


@pytest.fixture
def home(tmp_path) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def project(tmp_path) -> Path:
    p = tmp_path / "project"
    p.mkdir()
    return p


@pytest.fixture
def fake_server(tmp_path) -> Path:
    path = tmp_path / "fake_mcp.py"
    path.write_text(FAKE_SERVER)
    return path


def closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _McpHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if msg.get("method") == "initialize":
            body = {"jsonrpc": "2.0", "id": msg["id"],
                    "result": {"protocolVersion": "2025-06-18", "serverInfo": {"name": "h"}}}
        elif msg.get("method") == "tools/list":
            body = {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": [{"name": "x"}]}}
        else:
            self.send_response(202)
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "s1")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # silence
        pass


@pytest.fixture
def http_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _McpHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/mcp"
    srv.shutdown()


def write_user_mcp(home: Path, servers: dict) -> None:
    (home / ".claude.json").write_text(json.dumps({"mcpServers": servers}))


def write_project_mcp(project: Path, servers: dict) -> None:
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))


def stdio(fake: Path, mode: str = "ok") -> dict:
    return {"type": "stdio", "command": sys.executable, "args": [str(fake), mode]}


def run(home: Path, project: Path, checkout: Path | None = None, *extra: str):
    args = [sys.executable, str(SCRIPT), "--home", str(home), "--project-dir", str(project), "--timeout", "8"]
    if checkout is not None:
        args += ["--checkout", str(checkout)]
    env = {k: v for k, v in os.environ.items() if k != "SECOND_OPINION_URL"}
    env["HOME"] = str(home)
    return subprocess.run([*args, *extra], capture_output=True, text=True, env=env, check=False, timeout=180)


def rows_of(proc) -> dict:
    text = proc.stdout.rsplit("CAPABILITY_READINESS:", 1)[0]
    doc = json.loads(text)
    return {r["capability"]: r for r in doc["capabilities"]}


def verdict_of(proc) -> str:
    return proc.stdout.strip().splitlines()[-1].split(":", 1)[1].strip()


# --------------------------------------------------------------------------- #
# MCP rows
# --------------------------------------------------------------------------- #

def test_nothing_registered_is_disabled_and_never_ready(home, project):
    proc = run(home, project, None, "--json")
    rows = rows_of(proc)
    assert rows["second-opinion"]["state"] == "disabled"
    assert rows["browser-qa"]["state"] == "disabled"
    assert rows["flow"]["state"] == "disabled"
    assert verdict_of(proc) == "unknown" and proc.returncode == 4


def test_healthy_stdio_and_http_servers_are_ready_for_the_handshake_only(home, project, fake_server, http_server):
    write_user_mcp(home, {"playwright": stdio(fake_server)})
    write_project_mcp(project, {"second-opinion": {"type": "http", "url": http_server}})
    rows = rows_of(run(home, project, None, "--json"))
    for cap in ("second-opinion", "browser-qa"):
        assert rows[cap]["state"] == "ready", rows[cap]
        assert rows[cap]["tested"].startswith("MCP initialize + tools/list")
        assert rows[cap]["unexamined"], "a handshake must name the layer it did not reach"


def test_unreachable_service_is_unreachable_not_ready(home, project):
    port = closed_port()
    with socket.socket() as s:  # precondition: nothing listens there
        assert s.connect_ex(("127.0.0.1", port)) != 0
    write_project_mcp(project, {"second-opinion": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}})
    proc = run(home, project, None, "--json")
    assert rows_of(proc)["second-opinion"]["state"] == "unreachable"
    assert verdict_of(proc) == "degraded" and proc.returncode == 3


def test_stdio_server_that_exits_before_initialize_is_unreachable(home, project, fake_server):
    write_user_mcp(home, {"playwright": stdio(fake_server, "dead")})
    row = rows_of(run(home, project, None, "--json"))["browser-qa"]
    assert row["state"] == "unreachable"
    assert "exited (code 5)" in row["observations"][0]["detail"]


def test_conflicting_scopes_are_conflicting_with_per_scope_evidence(home, project, fake_server):
    port = closed_port()
    write_user_mcp(home, {"second-opinion": stdio(fake_server)})
    write_project_mcp(project, {"second-opinion": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}})
    row = rows_of(run(home, project, None, "--json"))["second-opinion"]
    assert row["state"] == "conflicting"
    by_scope = {o["name"]: o["verdict"] for o in row["observations"]}
    assert by_scope == {"handshake[user]": "ok", "handshake[project]": "unreachable"}


def test_optional_service_absence_does_not_touch_the_flow_row(home, project, cpp):
    cpp.install(home)
    port = closed_port()
    write_project_mcp(project, {"second-opinion": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}})
    rows = rows_of(run(home, project, cpp.checkout, "--json"))
    assert rows["second-opinion"]["state"] == "unreachable"
    assert rows["flow"]["state"] == "ready"


def test_credentials_in_the_endpoint_never_reach_the_output(home, project):
    user = "u" + secrets.token_hex(6)
    password = "p" + secrets.token_hex(12)
    token = "t" + secrets.token_hex(16)
    url = f"http://{user}:{password}@127.0.0.1:{closed_port()}/mcp?token={token}"
    write_project_mcp(project, {"second-opinion": {"type": "http", "url": url}})
    table = run(home, project, None)
    js = run(home, project, None, "--json")
    for out in (table.stdout + table.stderr, js.stdout + js.stderr):
        for secret in (user, password, token):
            assert secret not in out
    row = rows_of(js)["second-opinion"]
    assert row["state"] == "unexamined", "an authenticated handshake is not authorised for status"


def test_table_and_json_carry_the_same_states(home, project, fake_server):
    write_user_mcp(home, {"playwright": stdio(fake_server, "dead"), "second-opinion": stdio(fake_server)})
    rows = rows_of(run(home, project, None, "--json"))
    table = run(home, project, None).stdout.splitlines()
    for cap, row in rows.items():
        line = next(ln for ln in table if ln.startswith(cap + " "))
        assert line.split()[1] == row["state"]


# --------------------------------------------------------------------------- #
# flow row
# --------------------------------------------------------------------------- #

def test_healthy_flow_install_is_ready(home, project, cpp):
    cpp.install(home)
    row = rows_of(run(home, project, cpp.checkout, "--json"))["flow"]
    assert row["state"] == "ready", row
    assert row["source"]["revision"] and len(row["source"]["revision"]) == 40


def test_missing_helper_is_stale(home, project, cpp):
    cpp.install(home)
    victim = home / ".claude" / "scripts" / "flow-stale-check.sh"
    victim.unlink()
    assert not victim.exists()
    row = rows_of(run(home, project, cpp.checkout, "--json"))["flow"]
    assert row["state"] == "stale-or-unknown"
    assert any(o["name"] == "helpers" and o["verdict"] == "missing" for o in row["observations"])


def test_old_checkout_is_stale(home, project, cpp):
    cpp.install(home)
    cpp.advance()
    row = rows_of(run(home, project, cpp.checkout, "--json"))["flow"]
    assert row["state"] == "stale-or-unknown"
    assert any(o["verdict"] == "behind 1" for o in row["observations"])


def test_failed_freshness_lookup_is_stale_or_unknown_not_ready(home, project, cpp):
    cpp.install(home)
    _git("remote", "set-url", "origin", str(cpp.base / "gone.git"), cwd=cpp.checkout)
    assert not (cpp.base / "gone.git").exists()
    row = rows_of(run(home, project, cpp.checkout, "--json"))["flow"]
    assert row["state"] == "stale-or-unknown"
    fresh = next(o for o in row["observations"] if o["name"] == "checkout-freshness")
    assert fresh["verdict"].startswith("unknown")


# --------------------------------------------------------------------------- #
# clean-home install / update smoke (acceptance: install AND update, real entry points)
# --------------------------------------------------------------------------- #

def _digest_tree(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_clean_home_install_then_update_smoke(home, project, cpp):
    # Host-owned files the installers must not touch.
    (home / ".bashrc").write_text("# mine\n")
    (home / ".claude" / "scripts").mkdir(parents=True)
    (home / ".claude" / "scripts" / "my-own-tool.sh").write_text("#!/bin/sh\necho mine\n")
    (home / ".claude" / "commands").mkdir(parents=True)
    (home / ".claude" / "commands" / "my-note.md").write_text("mine\n")
    sentinels = _digest_tree(home)
    assert len(sentinels) == 3

    before = rows_of(run(home, project, cpp.checkout, "--json"))["flow"]
    assert before["state"] == "disabled"

    cpp.install(home)
    installed = run(home, project, cpp.checkout, "--json")
    row = rows_of(installed)["flow"]
    assert row["state"] == "ready", row
    assert next(o for o in row["observations"] if o["name"] == "probe")["verdict"] == "ok"
    assert verdict_of(installed) == "ready" and installed.returncode == 0

    cpp.advance()
    assert rows_of(run(home, project, cpp.checkout, "--json"))["flow"]["state"] == "stale-or-unknown"

    _git("pull", "-q", "--ff-only", cwd=cpp.checkout)
    cpp.install(home)
    updated = rows_of(run(home, project, cpp.checkout, "--json"))["flow"]
    assert updated["state"] == "ready", updated
    assert next(o for o in updated["observations"] if o["name"] == "probe")["verdict"] == "ok"
    assert updated["source"]["revision"] != row["source"]["revision"]

    # Host-owned files unchanged; everything the installers added is a link into the checkout.
    assert _digest_tree(home) == sentinels
    for entry in (home / ".claude" / "scripts").iterdir():
        if entry.name == "my-own-tool.sh":
            continue
        assert entry.is_symlink() and str(entry.resolve()).startswith(str(cpp.checkout.resolve())), entry
    top = {p.name for p in home.iterdir()}
    assert top <= {".bashrc", ".claude"}, top


# --------------------------------------------------------------------------- #
# the shipped surface and the anchor
# --------------------------------------------------------------------------- #

STATUS_MD = ROOT / ".claude" / "commands" / "cpp" / "status.md"
ANCHOR = ROOT / "controls" / "capability-readiness" / "anchors" / "pre-fix-status-curl.sh"


def test_status_command_runs_the_readiness_table_not_the_brace_curl():
    """/cpp:status is served from this file itself (a ~/.claude/commands/cpp link; cpp/status.md
    has no Codex mirror by design - codex-skill-sync.py EXCLUDE), so the shipped surface is checked here.
    Red on 51dc14d: the old block grepped `http://127.0.0.1:8080}/mcp` and curled it."""
    text = STATUS_MD.read_text(encoding="utf-8")
    assert 'scripts/capability-readiness.py" --project-dir' in text
    assert "grep -oE 'https?://" not in text
    front = text.split("---", 2)[1]
    assert "Bash(python3:*)" in front, "the readiness call must be inside status.md's allowed-tools"


def test_status_md_has_no_codex_mirror_to_drift():
    """If cpp/status.md ever gains a Codex mirror, this readiness surface must be checked there too."""
    assert not list((ROOT / "codex" / "skills").glob("cpp-status*"))


def test_the_anchor_block_is_verbatim_from_51dc14d():
    """The anchor's provenance is `n/a` to the harness (the preamble is constructed); the span is checked here."""
    probe = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", "51dc14d:.claude/commands/cpp/status.md"],
                           capture_output=True, check=False)
    if probe.returncode != 0:
        pytest.skip("51dc14d is not in this clone's history (shallow clone)")
    original = subprocess.run(["git", "-C", str(ROOT), "show", "51dc14d:.claude/commands/cpp/status.md"],
                              capture_output=True, text=True, check=True).stdout.splitlines()[278:293]
    lines = ANCHOR.read_text(encoding="utf-8").splitlines()
    begin = next(i for i, ln in enumerate(lines) if "BEGIN verbatim" in ln)
    end = next(i for i, ln in enumerate(lines) if "END verbatim" in ln)
    assert lines[begin + 1:end] == original
    assert any("8080}" in ln or "grep -oE 'https?://" in ln for ln in original)


# --------------------------------------------------------------------------- #
# counter-model review findings (pass 1)
# --------------------------------------------------------------------------- #

class _StrictSseHandler(BaseHTTPRequestHandler):
    """Answers over SSE and KEEPS THE STREAM OPEN after the answer; refuses any
    post-initialize request that omits the negotiated MCP-Protocol-Version."""

    protocol_version = "HTTP/1.1"

    def do_POST(self):  # noqa: N802
        msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if msg.get("method") != "initialize" and self.headers.get("MCP-Protocol-Version") != "2025-06-18":
            self.send_response(400)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if msg.get("method") == "initialize":
            body = {"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-06-18", "capabilities": {}}}
        elif msg.get("method") == "tools/list":
            body = {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": []}}
        else:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", "s1")
        self.end_headers()
        self.wfile.write(f"event: message\ndata: {json.dumps(body)}\n\n".encode())
        self.wfile.flush()
        self.server.hold.wait(20)  # the stream stays open after the answer

    def log_message(self, *a):
        pass


class _TrickleHandler(BaseHTTPRequestHandler):
    """Sends one byte every 0.5s forever: each read beats a socket timeout."""

    def do_POST(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        while not self.server.hold.is_set():
            try:
                self.wfile.write(b":")
                self.wfile.flush()
            except OSError:
                return
            self.server.hold.wait(0.5)

    def log_message(self, *a):
        pass


def _serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    srv.hold = threading.Event()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/mcp"


def test_open_sse_stream_with_negotiated_version_is_ready(home, project):
    srv, url = _serve(_StrictSseHandler)
    try:
        write_project_mcp(project, {"second-opinion": {"type": "http", "url": url}})
        row = rows_of(run(home, project, None, "--json"))["second-opinion"]
    finally:
        srv.hold.set()
        srv.shutdown()
    assert row["state"] == "ready", row


def test_a_trickling_server_is_cut_off_by_the_overall_deadline(home, project):
    import time
    srv, url = _serve(_TrickleHandler)
    try:
        write_project_mcp(project, {"second-opinion": {"type": "http", "url": url}})
        t0 = time.monotonic()
        row = rows_of(run(home, project, None, "--json"))["second-opinion"]
        elapsed = time.monotonic() - t0
    finally:
        srv.hold.set()
        srv.shutdown()
    assert row["state"] == "unreachable"
    assert elapsed < 30, elapsed


def test_same_endpoint_with_one_failing_scope_is_not_ready(home, project, fake_server):
    # One endpoint (same command and args) at two scopes; the project scope's env
    # references an unset variable, so that probe cannot run.
    spec = stdio(fake_server)
    write_user_mcp(home, {"second-opinion": spec})
    write_project_mcp(project, {"second-opinion": {**spec, "env": {"K": "${CPP_TEST_UNSET_VAR_1290}"}}})
    assert "CPP_TEST_UNSET_VAR_1290" not in os.environ
    row = rows_of(run(home, project, None, "--json"))["second-opinion"]
    assert {o["verdict"] for o in row["observations"]} == {"ok", "unexamined"}
    assert row["state"] != "ready"


def test_dangling_install_links_are_a_broken_install_not_disabled(home, project, cpp):
    cpp.install(home)
    moved = cpp.base / "moved-away"
    cpp.checkout.rename(moved)
    marker = home / ".claude" / "scripts" / "flow-start-resolve.sh"
    assert marker.is_symlink() and not marker.exists()
    row = rows_of(run(home, project, moved, "--json"))["flow"]
    assert row["state"] == "stale-or-unknown", row


def test_a_package_launcher_is_not_started(home, project, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    witness = tmp_path / "npx-was-run"
    npx = bin_dir / "npx"
    npx.write_text(f"#!/bin/sh\ntouch {witness}\nexit 1\n")
    npx.chmod(0o755)
    write_user_mcp(home, {"playwright": {"type": "stdio", "command": str(npx), "args": ["-y", "pkg"]}})
    row = rows_of(run(home, project, None, "--json"))["browser-qa"]
    assert row["state"] == "unexamined"
    assert not witness.exists(), "status must not start a package launcher"
    assert "installs packages" in row["next"] and "by hand" in row["next"]


# --------------------------------------------------------------------------- #
# counter-model review findings (pass 2)
# --------------------------------------------------------------------------- #

class _MalformedHandler(BaseHTTPRequestHandler):
    """Answers every request with a bare dict: no jsonrpc, no id, no protocolVersion."""

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        data = json.dumps({"result": {"tools": []}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_a_malformed_mcp_answer_is_not_ready(home, project):
    srv, url = _serve(_MalformedHandler)
    try:
        write_project_mcp(project, {"second-opinion": {"type": "http", "url": url}})
        row = rows_of(run(home, project, None, "--json"))["second-opinion"]
    finally:
        srv.shutdown()
    assert row["state"] == "unreachable", row


def test_a_raw_http_protocol_error_never_reaches_the_output(home, project):
    sentinel = "s" + secrets.token_hex(12)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    port = listener.getsockname()[1]
    stop = threading.Event()

    def serve():
        listener.settimeout(0.5)
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except OSError:
                continue
            with conn:
                conn.recv(65536)
                conn.sendall(f"GARBAGE {sentinel}\r\n\r\n".encode())

    threading.Thread(target=serve, daemon=True).start()
    try:
        write_project_mcp(project, {"second-opinion": {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}})
        proc = run(home, project, None, "--json")
    finally:
        stop.set()
        listener.close()
    assert sentinel not in proc.stdout + proc.stderr
    assert rows_of(proc)["second-opinion"]["state"] == "unreachable"


@pytest.mark.parametrize("command,args", [
    ("npm", ["exec", "--yes", "--", "pkg"]),
    ("pnpm", ["dlx", "pkg"]),
    ("uv", ["tool", "run", "pkg"]),
])
def test_package_manager_exec_forms_are_not_started(home, project, tmp_path, command, args):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    witness = tmp_path / "was-run"
    exe = bin_dir / command
    exe.write_text(f"#!/bin/sh\ntouch {witness}\nexit 1\n")
    exe.chmod(0o755)
    write_user_mcp(home, {"playwright": {"type": "stdio", "command": str(exe), "args": args}})
    row = rows_of(run(home, project, None, "--json"))["browser-qa"]
    assert row["state"] == "unexamined"
    assert not witness.exists()


class _RedirectHandler(BaseHTTPRequestHandler):
    """Redirects every request elsewhere; the probe must not follow."""

    def do_POST(self):  # noqa: N802
        self.send_response(307)
        self.send_header("Location", "http://127.0.0.1:1/mcp")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


def test_a_redirect_is_not_followed(home, project):
    srv, url = _serve(_RedirectHandler)
    try:
        write_project_mcp(project, {"second-opinion": {"type": "http", "url": url}})
        row = rows_of(run(home, project, None, "--json"))["second-opinion"]
    finally:
        srv.shutdown()
    assert row["state"] == "unreachable"
    assert "HTTP 307" in row["observations"][0]["detail"]


# --------------------------------------------------------------------------- #
# orchestrator review of PR #1337: surviving mutants
# --------------------------------------------------------------------------- #

def _module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("capability_readiness", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("states,expected", [
    (["ready", "ready", "unexamined"], "unknown"),   # an unexamined row is NOT ready
    (["ready", "disabled", "disabled"], "ready"),    # optional absence does not count against
    (["ready", "unreachable", "disabled"], "degraded"),
    (["disabled", "disabled", "disabled"], "unknown"),
])
def test_overall_verdict(states, expected):
    mod = _module()
    assert mod.overall([{"state": s} for s in states]) == expected
    assert mod.EXIT[expected] == {"ready": 0, "degraded": 3, "unknown": 4}[expected]


def test_ready_rows_plus_an_unstarted_launcher_is_unknown_exit_4(home, project, cpp, fake_server, tmp_path):
    """The typical host: flow ready, second-opinion ready, playwright via npx (not started)."""
    cpp.install(home)
    npx = tmp_path / "bin" / "npx"
    npx.parent.mkdir()
    npx.write_text("#!/bin/sh\nexit 1\n")
    npx.chmod(0o755)
    write_user_mcp(home, {"second-opinion": stdio(fake_server),
                          "playwright": {"type": "stdio", "command": str(npx), "args": ["-y", "pkg"]}})
    proc = run(home, project, cpp.checkout, "--json")
    rows = rows_of(proc)
    assert [rows[c]["state"] for c in ("flow", "second-opinion", "browser-qa")] == ["ready", "ready", "unexamined"]
    assert verdict_of(proc) == "unknown" and proc.returncode == 4


class _NoProtocolVersionHandler(BaseHTTPRequestHandler):
    """A valid JSON-RPC envelope whose initialize result carries no protocolVersion."""

    def do_POST(self):  # noqa: N802
        msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        if msg.get("method") == "initialize":
            body = {"jsonrpc": "2.0", "id": msg["id"], "result": {"serverInfo": {"name": "x"}}}
        elif msg.get("method") == "tools/list":
            body = {"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": []}}
        else:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_an_initialize_result_without_protocol_version_is_not_ready(home, project):
    srv, url = _serve(_NoProtocolVersionHandler)
    try:
        write_project_mcp(project, {"second-opinion": {"type": "http", "url": url}})
        row = rows_of(run(home, project, None, "--json"))["second-opinion"]
    finally:
        srv.shutdown()
    assert row["state"] == "unreachable", row
    assert "initialize" in row["observations"][0]["detail"]
