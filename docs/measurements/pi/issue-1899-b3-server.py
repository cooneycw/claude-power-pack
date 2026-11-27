#!/usr/bin/env python3
"""Disposable local MCP echo fixture. No provider credentials or filesystem tools."""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TOOL = "probe-echo"


def publish_new(path: Path, value: dict) -> None:
    temporary = path.with_name("." + path.name + ".pending")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(json.dumps(value).encode() + b"\n")
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    # Atomic, exclusive publication: an existing endpoint is never replaced.
    os.link(temporary, path, follow_symlinks=False)
    temporary.unlink()


def append_event(directory: Path, event: dict) -> None:
    batch = json.loads((directory / "batch.json").read_text())["batch"]
    data = {"batch": batch, "time_ns": time.monotonic_ns(), "wall_time_ns": time.time_ns(),
            "pid": os.getpid(), **event}
    fd = os.open(directory / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, json.dumps(data, sort_keys=True).encode() + b"\n")
    finally:
        os.close(fd)


def dispatch(request: dict, directory: Path, transport: str, instance: str, peer: str) -> dict | None:
    if "id" not in request:
        return None
    response = {"jsonrpc": "2.0", "id": request["id"]}
    method, params = request.get("method"), request.get("params", {})
    if method == "initialize":
        offered = params.get("protocolVersion")
        version = offered if offered in {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"} else "2025-03-26"
        result = {"protocolVersion": version,
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "cpp-pi1899-echo", "version": "1"}}
        append_event(directory, {"event": "initialize", "transport": transport, "instance": instance,
                                 "peer": peer, "protocol_version": version,
                                 "client_version": str(params.get("clientInfo", {}).get("version", "unknown"))[:40]})
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": TOOL, "description": "Return a fresh probe nonce with the supplied tag.",
                             "inputSchema": {"type": "object", "properties": {"tag": {"type": "string"}},
                                             "required": ["tag"], "additionalProperties": False},
                             "annotations": {"readOnlyHint": True, "destructiveHint": False,
                                             "idempotentHint": False, "openWorldHint": False}}]}
    elif method == "tools/call" and params.get("name") == TOOL:
        arguments = params.get("arguments", {})
        tag = arguments.get("tag") if isinstance(arguments, dict) else None
        if not isinstance(tag, str) or not re.fullmatch(r"(?:T[1-8]-(?:alpha|beta)|control-[a-z-]+)", tag):
            return {**response, "error": {"code": -32602, "message": "Invalid fixture tag"}}
        payload = {"tag": tag, "nonce": secrets.token_hex(16), "transport": transport}
        append_event(directory, {"event": "tools/call", "transport": transport, "instance": instance,
                                 "peer": peer, "name": TOOL, "request_id": request["id"],
                                 "request": {"method": "tools/call", "params": {"name": TOOL,
                                             "arguments": {"tag": tag}}}, **payload})
        result = {"content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}], "isError": False}
    else:
        return {**response, "error": {"code": -32601, "message": "Method not implemented by fixture"}}
    return {**response, "result": result}


def sent(reply: dict, directory: Path, transport: str, instance: str, peer: str) -> None:
    content = reply.get("result", {}).get("content")
    if not content:
        return
    payload = json.loads(content[0]["text"])
    append_event(directory, {"event": "response", "transport": transport, "instance": instance,
                             "peer": peer, "request_id": reply["id"], "response": reply, **payload})


def stdio(directory: Path, dead: bool = False) -> int:
    instance = secrets.token_hex(16)
    append_event(directory, {"event": "start", "transport": "stdio", "instance": instance})
    peer = "uninitialized"
    try:
        if dead:
            return 23
        for line in sys.stdin:
            request = json.loads(line)
            if request.get("method") == "initialize":
                peer = str(request.get("params", {}).get("clientInfo", {}).get("name", "unknown"))[:80]
            reply = dispatch(request, directory, "stdio", instance, peer)
            if reply is not None:
                print(json.dumps(reply), flush=True)
                sent(reply, directory, "stdio", instance, peer)
    finally:
        append_event(directory, {"event": "stop", "transport": "stdio", "instance": instance})
    return 0


def http(directory: Path) -> None:
    instance = secrets.token_hex(16)
    token = secrets.token_hex(32)
    sessions: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send_body(self, code: int, body: dict | None = None, sid: str | None = None):
            payload = b"" if body is None else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            if sid:
                self.send_header("Mcp-Session-Id", sid)
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/health":
                self.send_body(200, {"instance": instance, "pid": os.getpid()})
            else:
                self.send_body(405)

        def do_DELETE(self):
            sid = self.headers.get("Mcp-Session-Id", "")
            if self.path != "/mcp" or sid not in sessions:
                self.send_body(404)
                return
            del sessions[sid]
            self.send_body(204)

        def do_POST(self):
            if self.path == "/shutdown":
                if self.headers.get("X-Probe-Teardown") != token:
                    self.send_body(403)
                    return
                self.send_body(200, {"instance": instance, "stopping": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if self.path != "/mcp":
                self.send_body(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 65536:
                self.send_body(400)
                return
            request = json.loads(self.rfile.read(length))
            sid = self.headers.get("Mcp-Session-Id", "")
            if request.get("method") == "initialize":
                sid = secrets.token_hex(16)
                sessions[sid] = str(request.get("params", {}).get("clientInfo", {}).get("name", "unknown"))[:80]
            if sid not in sessions:
                self.send_body(404)
                return
            reply = dispatch(request, directory, "http", instance, sessions[sid])
            self.send_body(202 if reply is None else 200, reply, sid)
            if reply is not None:
                sent(reply, directory, "http", instance, sessions[sid])

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    endpoint = {"pid": os.getpid(), "port": server.server_port, "instance": instance, "shutdown_token": token}
    try:
        publish_new(directory / "endpoint.json", endpoint)
        append_event(directory, {"event": "start", "transport": "http", "instance": instance,
                                 "port": server.server_port})
        print(json.dumps({"http_pid": os.getpid(), "loopback_port": server.server_port}), flush=True)
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
        append_event(directory, {"event": "stop", "transport": "http", "instance": instance})
        publish_new(directory / "http-stopped.json", {"instance": instance, "pid": os.getpid()})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transport", choices=["stdio", "http", "dead"])
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        parser.error("fixture directory must be an existing real absolute directory")
    if args.transport == "http":
        http(directory)
        return 0
    signal.signal(signal.SIGTERM, lambda *_args: sys.exit(0))
    return stdio(directory, dead=args.transport == "dead")


if __name__ == "__main__":
    raise SystemExit(main())
