#!/usr/bin/env python3
"""Bounded B3 fixture config, compatible clients, teardown and call evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import select
import socket
import stat
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
SERVER = HERE / "issue-1899-b3-server.py"
STDIO, HTTP, FOREIGN = "cpp-pi1899-stdio", "cpp-pi1899-http", "foreign-pi1899-sentinel"
FOREIGN_ENTRY = {"command": sys.executable, "args": ["-c", "raise SystemExit(29)"], "enabled": False,
                 "description": "Synthetic foreign registration; never invoked"}
BASE = {"autoEnableCodemode": False, "mcpServers": {FOREIGN: FOREIGN_ENTRY}}
CASES = ("foreign", "stdio-direct", "stdio-default", "http-direct", "http-default", "stdio-dead", "http-dead")
TAG = re.compile(r"T[1-8]-(?:alpha|beta)\Z")
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Unknown(RuntimeError):
    pass


def load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), HERE / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path: Path, limit: int = 131072) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as error:
        raise Unknown("fixture evidence unavailable: " + path.name) from error
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Unknown("nonregular fixture input")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise Unknown("oversized fixture input")
        return data
    finally:
        os.close(fd)


def encode(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2).encode() + b"\n"


def create(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def directory(root: Path) -> Path:
    if not root.is_absolute():
        raise ValueError("absolute probe root required")
    for path in [root, root / "agent", root / "work"]:
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise ValueError("real probe directories required")
    return root / "work/pi-1899-b3"


def save(directory: Path, state: dict) -> None:
    temporary = directory / "state.pending"
    create(temporary, encode(state))
    os.replace(temporary, directory / "state.json")


def guard(root: Path) -> tuple[Path, dict]:
    folder = directory(root)
    state = json.loads(read(folder / "state.json"))
    if (state.get("phase") != "stable" or state.get("case") not in CASES
            or not isinstance(state.get("config"), dict)):
        raise Unknown("incomplete B3 state; no automatic recovery")
    observed = (root / "agent/mcp.json").lstat()
    if not stat.S_ISREG(observed.st_mode) or stat.S_IMODE(observed.st_mode) != 0o600:
        raise ValueError("mcp.json type/mode changed; preserve and stop")
    if read(root / "agent/mcp.json") != encode(state["config"]):
        raise ValueError("mcp.json changed; preserve and stop")
    if state["config"].get("mcpServers", {}).get(FOREIGN) != FOREIGN_ENTRY:
        raise ValueError("foreign sentinel changed; preserve and stop")
    return folder, state


def prepare(root: Path) -> dict:
    folder = directory(root)
    load("issue-1899-b2-files.py").check_t1(root)
    if load("issue-1899-b2-model.py").read_pin(root) != "github-copilot/gpt-5.3-codex":
        raise ValueError("unexpected retained model pin")
    target = root / "agent/mcp.json"
    try:
        target.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ValueError("preexisting probe mcp.json; never adopt")
    folder.mkdir(mode=0o700)
    (folder / "replies").mkdir(mode=0o700)
    create(folder / "batch.json", encode({"batch": secrets.token_hex(16)}))
    save(folder, {"phase": "blocked", "reason": "preparing"})
    create(target, encode(BASE))
    save(folder, {"phase": "stable", "case": "foreign", "config": BASE})
    return audit(root)


def endpoint(folder: Path) -> dict:
    value = json.loads(read(folder / "endpoint.json"))
    if (not isinstance(value.get("port"), int) or not 1 <= value["port"] <= 65535
            or not isinstance(value.get("pid"), int)
            or not re.fullmatch(r"[0-9a-f]{32}", value.get("instance", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", value.get("shutdown_token", ""))):
        raise Unknown("invalid fixture endpoint")
    return value


def set_case(root: Path, case: str) -> dict:
    folder, state = guard(root)
    desired = json.loads(json.dumps(state["config"]))
    servers = desired["mcpServers"]
    servers.pop(STDIO, None)
    servers.pop(HTTP, None)
    if case.startswith("stdio-"):
        servers[STDIO] = {"command": sys.executable, "args": [str(SERVER.resolve()),
                         "dead" if case.endswith("dead") else "stdio", "--directory", str(folder)], "timeout": 5}
        if not case.endswith("default"):
            servers[STDIO]["exposure"] = "direct"
    elif case.startswith("http-"):
        ep = endpoint(folder)
        if case.endswith("dead"):
            stopped = json.loads(read(folder / "http-stopped.json"))
            if stopped.get("instance") != ep["instance"]:
                raise Unknown("dead HTTP row requires the recorded server's teardown")
            with_socket = socket.socket()
            try:
                if with_socket.connect_ex(("127.0.0.1", ep["port"])) == 0:
                    raise ValueError("HTTP endpoint still listening; not a dead-server input")
            finally:
                with_socket.close()
        servers[HTTP] = {"url": f'http://127.0.0.1:{ep["port"]}/mcp', "timeout": 5}
        if not case.endswith("default"):
            servers[HTTP]["exposure"] = "direct"
    elif case != "foreign":
        raise ValueError("unknown fixture case")
    save(folder, {"phase": "blocked", "before": state["config"], "requested": desired})
    temporary = root / "agent/.pi-1899-b3-mcp.pending"
    create(temporary, encode(desired))
    os.replace(temporary, root / "agent/mcp.json")
    save(folder, {"phase": "stable", "case": case, "config": desired})
    return audit(root)


def audit(root: Path) -> dict:
    _folder, state = guard(root)
    return {"case": state["case"], "config_sha256": hashlib.sha256(encode(state["config"])).hexdigest(),
            "foreign_sha256": hashlib.sha256(encode(FOREIGN_ENTRY)).hexdigest(),
            "foreign_preserved": True}


def prompt(root: Path, tag: str) -> dict:
    _folder, state = guard(root)
    allowed = {"foreign": [1, 8], "stdio-direct": [2], "stdio-default": [3],
               "http-direct": [4], "http-default": [5], "stdio-dead": [6], "http-dead": [7]}
    if not TAG.fullmatch(tag) or int(tag[1]) not in allowed[state["case"]]:
        raise ValueError("tag does not match configured matrix row")
    kind = "http" if state["case"].startswith("http-") else "stdio"
    tool = f"mcp__cpp_pi1899_{kind}__probe_echo"
    text = (f'Call only {tool} exactly once with tag "{tag}". Return its text result verbatim. '
            'If this exact tool is not declared, reply TOOL_UNAVAILABLE. Do not call another tool.')
    return {"tag": tag, "expected_tool_id": tool, "prompt": text}


def init_request() -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "cpp-pi1899-control", "version": "1"}}}


def control(root: Path, transport: str, dead: bool = False) -> dict:
    folder = directory(root)
    requests = [init_request(), {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                    "name": "probe-echo", "arguments": {"tag": "control-" + transport}}}]
    if transport == "stdio":
        process = subprocess.Popen([sys.executable, str(SERVER), "dead" if dead else "stdio",
                                    "--directory", str(folder)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                   env={"PATH": os.defpath, "HOME": str(root / "home"), "LANG": "C.UTF-8"})
        try:
            assert process.stdin is not None and process.stdout is not None
            replies = []
            for message in requests:
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()
                if "id" in message:
                    if not select.select([process.stdout], [], [], 5)[0]:
                        raise ValueError("compatible client timed out")
                    reply = process.stdout.readline()
                    if not reply:
                        raise ValueError("compatible client saw EOF")
                    replies.append(json.loads(reply))
        finally:
            if process.stdin is not None:
                process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
            if dead and process.returncode != 23:
                raise Unknown("dead stdio child did not exit with the expected 23")
    else:
        ep = endpoint(folder)
        url = f'http://127.0.0.1:{ep["port"]}/mcp'
        sid = None
        replies = []
        for message in requests:
            headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                       "MCP-Protocol-Version": "2025-03-26"}
            if sid:
                headers["Mcp-Session-Id"] = sid
            request = urllib.request.Request(url, data=json.dumps(message).encode(), headers=headers)
            with LOCAL_HTTP.open(request, timeout=5) as response:
                sid = response.headers.get("Mcp-Session-Id", sid)
                payload = response.read()
                if "id" in message:
                    replies.append(json.loads(payload))
        if sid:
            request = urllib.request.Request(url, method="DELETE", headers={"Mcp-Session-Id": sid})
            with LOCAL_HTTP.open(request, timeout=5) as response:
                response.read()
    if [item.get("id") for item in replies] != [1, 2, 3]:
        raise ValueError("compatible client response IDs differ")
    if not any(item.get("name") == "probe-echo" for item in replies[1]["result"]["tools"]):
        raise ValueError("compatible client tool missing")
    payload = json.loads(replies[2]["result"]["content"][0]["text"])
    if (payload.get("tag") != "control-" + transport or payload.get("transport") != transport
            or not re.fullmatch(r"[0-9a-f]{32}", payload.get("nonce", ""))):
        raise ValueError("compatible client result invalid")
    return {"compatible_call": True, "transport": transport}


def stop_http(root: Path) -> dict:
    folder = directory(root)
    ep = endpoint(folder)
    base = f'http://127.0.0.1:{ep["port"]}'
    with LOCAL_HTTP.open(base + "/health", timeout=3) as response:
        health = json.load(response)
    if health != {"instance": ep["instance"], "pid": ep["pid"]}:
        raise Unknown("HTTP instance differs; do not stop it")
    request = urllib.request.Request(base + "/shutdown", data=b"", headers={"X-Probe-Teardown": ep["shutdown_token"]})
    with LOCAL_HTTP.open(request, timeout=3) as response:
        result = json.load(response)
    if result.get("instance") != ep["instance"]:
        raise Unknown("teardown response mismatch")
    for _ in range(50):
        try:
            stopped = json.loads(read(folder / "http-stopped.json"))
        except Unknown:
            time.sleep(0.1)
            continue
        if stopped.get("instance") != ep["instance"]:
            raise Unknown("teardown marker mismatch")
        sock = socket.socket()
        try:
            if sock.connect_ex(("127.0.0.1", ep["port"])) != 0:
                return {"http_stopped": True, "pid": ep["pid"]}
        finally:
            sock.close()
        time.sleep(0.1)
    raise Unknown("HTTP teardown not established")


def verify_events(data: bytes, batch: str, tag: str, transport: str, reply: str) -> dict:
    if not data.strip():
        raise Unknown("empty server evidence")
    try:
        rows = [json.loads(line) for line in data.splitlines()]
    except (ValueError, UnicodeError) as error:
        raise Unknown("unreadable server evidence") from error
    if not all(isinstance(row, dict) and "event" in row and "batch" in row for row in rows):
        raise Unknown("unsupported server evidence")
    calls = [row for row in rows if row.get("event") == "tools/call" and row.get("batch") == batch
             and row.get("tag") == tag and row.get("transport") == transport and row.get("peer") == "pi"
             and row.get("name") == "probe-echo"]
    if len(calls) != 1:
        raise ValueError("no unique matching pi-originated tools/call; exit 0/prose cannot prove a call")
    event = calls[0]
    if (type(event.get("pid")) is not int or event["pid"] <= 0
            or not isinstance(event.get("instance"), str) or not event["instance"]
            or type(event.get("request_id")) not in [int, str]):
        raise Unknown("call lacks process/instance/request binding")
    for kind in ["start", "initialize"]:
        if not any(row.get("event") == kind and row.get("batch") == batch
                   and row.get("instance") == event.get("instance")
                   and row.get("transport") == transport and row.get("pid") == event.get("pid")
                   and isinstance(row.get("time_ns"), int) and isinstance(event.get("time_ns"), int)
                   and row["time_ns"] <= event["time_ns"]
                   and (kind == "start" or row.get("peer") == "pi") for row in rows):
            raise Unknown("call lacks bound fixture start/initialize evidence")
    nonce = event.get("nonce", "")
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise Unknown("missing valid nonce in call record")
    if nonce not in reply or tag not in reply:
        raise ValueError("controlled reply does not contain this call's nonce and tag")
    responses = [row for row in rows if row.get("event") == "response" and row.get("batch") == batch
                 and row.get("instance") == event.get("instance") and row.get("pid") == event.get("pid")
                 and row.get("request_id") == event.get("request_id") and row.get("peer") == "pi"
                 and row.get("tag") == tag and row.get("nonce") == nonce and row.get("transport") == transport
                 and isinstance(row.get("time_ns"), int) and row["time_ns"] >= event["time_ns"]]
    if len(responses) != 1:
        raise Unknown("call lacks a unique bound response-send record")
    try:
        response = responses[0]["response"]
        if not isinstance(response, dict) or response.get("id") != event["request_id"]:
            raise Unknown("response ID differs from request")
        payload = json.loads(response["result"]["content"][0]["text"])
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise Unknown("response record unexaminable") from error
    if payload != {"tag": tag, "nonce": nonce, "transport": transport}:
        raise Unknown("response-send payload differs")
    return {"verified_pi_call": True, "tag": tag, "transport": transport, "pid": event.get("pid")}


def undo(root: Path) -> dict:
    folder, state = guard(root)
    if state["config"] != BASE:
        raise ValueError("restore foreign-only state before final undo")
    events = [json.loads(line) for line in read(folder / "events.jsonl", 4_000_000).splitlines()]
    starts = {event.get("instance") for event in events if event.get("event") == "start"}
    stops = {event.get("instance") for event in events if event.get("event") == "stop"}
    if not starts or not starts <= stops:
        raise Unknown("some logged fixture instances lack teardown evidence")
    ep = endpoint(folder)
    stopped = json.loads(read(folder / "http-stopped.json"))
    if (stopped.get("instance") != ep["instance"] or stopped.get("pid") != ep["pid"]
            or stopped.get("instance") not in stops):
        raise Unknown("HTTP stop not bound to logged fixture")
    save(folder, {"phase": "blocked", "reason": "undoing"})
    (root / "agent/mcp.json").unlink()
    save(folder, {"phase": "undone", "config": None})
    return {"probe_mcp_absent": True, "logged_fixture_instances_stopped": len(starts)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "set", "audit", "prompt", "control-stdio",
                                            "control-dead-stdio", "control-http", "stop-http",
                                            "record-reply", "verify", "undo"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--tag")
    parser.add_argument("--transport", choices=["stdio", "http"])
    args = parser.parse_args()
    try:
        if args.operation == "prepare":
            result = prepare(args.root)
        elif args.operation == "set":
            if args.case is None:
                parser.error("set requires --case")
            result = set_case(args.root, args.case)
        elif args.operation == "audit":
            result = audit(args.root)
        elif args.operation == "prompt":
            if args.tag is None:
                parser.error("prompt requires a bounded fixture --tag")
            result = prompt(args.root, args.tag)
        elif args.operation.startswith("control-"):
            result = control(args.root, "http" if args.operation == "control-http" else "stdio",
                             dead=args.operation == "control-dead-stdio")
        elif args.operation == "stop-http":
            result = stop_http(args.root)
        elif args.operation in ["record-reply", "verify"]:
            if args.tag is None or not TAG.fullmatch(args.tag):
                parser.error("a bounded fixture --tag is required")
            folder = directory(args.root)
            reply_path = folder / "replies" / (args.tag + ".txt")
            if args.operation == "record-reply":
                reply = sys.stdin.buffer.read(65537)
                if not reply or len(reply) > 65536:
                    raise Unknown("empty/oversized controlled reply")
                create(reply_path, reply)
                result = {"recorded_reply": args.tag}
            else:
                if args.transport is None:
                    parser.error("verify requires --transport")
                batch = json.loads(read(folder / "batch.json"))["batch"]
                result = verify_events(read(folder / "events.jsonl", 4_000_000), batch, args.tag,
                                       args.transport, read(reply_path).decode())
        else:
            result = undo(args.root)
    except Unknown as error:
        parser.exit(4, f"UNKNOWN: {error}\n")
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"STOP/NO VERIFIED CALL: {type(error).__name__}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
