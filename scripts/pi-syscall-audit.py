#!/usr/bin/env python3
"""Classify bounded pi copier traces, never a before/after-only boundary check.

Input is an explicit fixture record with allowance and per-pid raw strace text.
Unknown relevant syntax, incomplete children or paths never become clean.
"""
# NEGATIVE-CONTROL: controls/pi-syscall-observer
from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
from pathlib import Path


def inside(path, root):
    return path == root or path.startswith(root.rstrip("/") + "/")


def arguments(text):
    items, start, depth, quoted, escaped = [], 0, 0, False, False
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and not depth:
            items.append(text[start:index].strip())
            start = index + 1
    if quoted or depth:
        raise ValueError("incomplete syscall arguments")
    return [*items, text[start:].strip()]


def audit(record):
    """Return explicit findings and unexamined inputs; paths are fixture supplied."""
    allowance = record["allowance"]
    skills, lock, source = (allowance[k] for k in ("skills", "lock", "source"))
    histories = allowance["histories"]
    settings = allowance["settings"]
    mode = allowance["mode"]
    if mode not in ("install", "verify", "build", "record-only"):
        raise ValueError("unsupported operation mode")
    roots = [skills, lock, source, allowance["cwd"], *histories, *settings, *allowance.get("metadata", []),
             *allowance.get("runtime_reads", []), *allowance.get("aliases", {}).keys(),
             *allowance.get("aliases", {}).values()]
    if not roots or any(not isinstance(p, str) or not p.startswith("/") or posixpath.normpath(p) != p for p in roots):
        raise ValueError("allowance paths must be explicit normalized absolute paths")
    if "/" in (skills, lock, source, *histories, *settings, *allowance.get("runtime_reads", [])):
        raise ValueError("filesystem root is not a bounded read/write scope")
    findings, unknown, examined = [], [], 0
    events = []
    for pid, trace in record["traces"].items():
        exit_code = record.get("exit_codes", {}).get(pid, 0)
        if not isinstance(trace, str) or not re.search(r"\+\+\+ exited with " + str(exit_code) + r" \+\+\+\s*$", trace):
            unknown.append(f"{pid}: missing successful exit trace")
        for line in trace.split("\n"):
            if not line.strip():
                continue
            match = re.fullmatch(r"([0-9]+\.[0-9]+) (.*)", line)
            if not match:
                unknown.append(f"{pid}: missing timestamp/framing")
                continue
            events.append((float(match[1]), pid, match[2]))
    if not events:
        unknown.append("empty trace population")
    if record.get("root_pid") not in record["traces"]:
        unknown.append("root child identity missing/ambiguous")
    cwd = {str(record.get("root_pid", "")): allowance["cwd"]}

    def path_of(value, pid, directory=None):
        if value.endswith("..."):
            raise ValueError("truncated path")
        if not value.startswith('"'):
            raise ValueError("non-string path")
        path = ast.literal_eval(value)
        if not isinstance(path, str) or "\0" in path:
            raise ValueError("invalid path string")
        if not path.startswith("/"):
            base = descriptor(directory, pid) if directory else cwd.get(pid)
            if not base or not base.startswith("/"):
                raise ValueError("unresolved directory/cwd")
            path = posixpath.join(base, path)
        return posixpath.normpath(path)

    def descriptor(value, pid):
        if value is None:
            raise ValueError("missing descriptor")
        annotated = re.fullmatch(r"(?:[0-9]+|AT_FDCWD)<(/[^<>]*)>", value)
        if annotated:
            target = annotated[1]
            if target.endswith(" (deleted)"):
                target = target[:-10]
            return posixpath.normpath(target)
        if value == "AT_FDCWD":
            return cwd.get(pid)
        if re.fullmatch(r"[0-9]+<(?:pipe:|socket:|anon_inode:)[^>]*>", value):
            return "stdio-or-ipc"
        raise ValueError("unresolved file descriptor")

    def examine(path, operation, call, args):
        nonlocal examined
        if path == "stdio-or-ipc":
            return
        if not path or not path.startswith("/"):
            raise ValueError("unresolved operation target")
        examined += 1
        original = path
        follows = not (call in ("lstat", "readlink", "readlinkat") or "AT_SYMLINK_NOFOLLOW" in args or
                       call.startswith("open") and "O_NOFOLLOW" in args)
        if follows:
            for alias, target in allowance.get("aliases", {}).items():
                if inside(path, alias):
                    path = posixpath.normpath(target + path[len(alias):])
        if any(part in ("auth.json", "mcp-auth.json") for candidate in (original, path)
               for part in candidate.split("/")):
            findings.append(f"{operation}: authentication probe: {path}")
            return
        history = next((h for h in histories if inside(path, h)), None)
        if history:
            root_resolution = path == history and (call in ("lstat", "readlink", "readlinkat") or
                                                    call in ("newfstatat", "statx") and "AT_SYMLINK_NOFOLLOW" in args)
            if not root_resolution:
                findings.append(f"{operation}: forbidden history access: {path}")
                return
        if operation == "write":
            writable = inside(path, skills) if mode != "record-only" else inside(path, skills + "/.cpp-managed")
            if mode == "verify" or not (writable or path == lock):
                findings.append(f"write outside operation allowance: {path}")
            return
        # Source/interpreter reads and exact bounded configuration are distinct
        # from metadata-only ancestor resolution. No general HOME/agent read.
        if inside(path, skills) or path == lock or inside(path, source) or path in settings:
            return
        if any(inside(path, p) for p in allowance.get("runtime_reads", [])):
            return
        if operation == "metadata" and (path in allowance.get("metadata", []) or
                                        any(inside(root, path) for root in roots)):
            return
        findings.append(f"{operation} outside read allowance: {path}")

    file_calls = {"stat", "lstat", "access", "readlink", "statfs"}
    at_calls = {"newfstatat", "statx", "faccessat", "faccessat2", "readlinkat"}
    writes = {"unlink", "mkdir", "rmdir", "chmod", "truncate", "utime", "utimes", "chown", "lchown"}
    at_writes = {"unlinkat", "mkdirat", "fchmodat", "fchownat", "utimensat"}
    fd_reads = {"read", "pread64", "readv", "preadv", "preadv2", "getdents", "getdents64"}
    fd_writes = {"write", "pwrite64", "writev", "pwritev", "pwritev2", "ftruncate", "fchmod", "fchown"}
    fd_meta = {"fstat", "fstatfs", "lseek", "fsync", "fdatasync", "flock", "fcntl", "ioctl"}
    harmless = {"close", "close_range", "dup", "dup2", "dup3", "pipe", "pipe2", "exit", "exit_group",
                "wait4", "waitid", "kill", "tgkill", "pidfd_open", "pidfd_send_signal", "fork", "vfork"}
    for _, pid, line in sorted(events):
        if line.startswith(("+++ exited with ", "--- SIG")):
            continue
        match = re.fullmatch(r"([a-zA-Z0-9_]+)\((.*)\)\s+=\s+(.+)", line)
        if not match:
            unknown.append(f"{pid}: unsupported/incomplete trace line")
            continue
        call, raw, result = match.groups()
        try:
            args = arguments(raw)
            if call in ("clone", "clone3", "fork", "vfork"):
                if re.fullmatch(r"[0-9]+", result):
                    if result not in record["traces"]:
                        unknown.append(f"{pid}: child {result} omitted from trace population")
                    if pid in cwd:
                        cwd[result] = cwd[pid]
            elif call == "chdir":
                target = path_of(args[0], pid)
                examine(target, "metadata", call, raw)
                if result == "0":
                    cwd[pid] = target
            elif call == "fchdir":
                target = descriptor(args[0], pid)
                examine(target, "metadata", call, raw)
                if result == "0":
                    cwd[pid] = target
            elif call == "getcwd":
                if not result.startswith("-1"):
                    cwd[pid] = path_of(args[0], pid)
            elif call in ("open", "creat", "openat", "openat2"):
                at = call.startswith("openat")
                path = path_of(args[1 if at else 0], pid, args[0] if at else None)
                writing = call == "creat" or re.search(r"O_(?:WRONLY|RDWR|CREAT|TRUNC|APPEND)", raw)
                operation = "write" if writing else "read"
                examine(path, operation, call, raw)
                opened = re.match(r"[0-9]+</[^<>]*>", result)
                if opened:
                    examine(descriptor(opened[0], pid), operation, call, raw)
                elif re.match(r"[0-9]+", result):
                    raise ValueError("successful open lacks resolved descriptor target")
            elif call in file_calls | writes | {"execve"}:
                operation = "write" if call in writes else "metadata" if call in file_calls else "read"
                examine(path_of(args[0], pid), operation, call, raw)
            elif call in at_calls | at_writes | {"execveat"}:
                operation = "write" if call in at_writes else "metadata" if call in at_calls else "read"
                examine(path_of(args[1], pid, args[0]), operation, call, raw)
            elif call in ("rename", "link"):
                for value in args[:2]:
                    examine(path_of(value, pid), "write", call, raw)
            elif call in ("renameat", "renameat2", "linkat"):
                for index in (0, 2):
                    examine(path_of(args[index + 1], pid, args[index]), "write", call, raw)
            elif call in ("symlink", "symlinkat"):
                examine(path_of(args[-1], pid, args[1] if call == "symlinkat" else None), "write", call, raw)
            elif call in fd_reads | fd_writes | fd_meta:
                operation = "write" if call in fd_writes else "read" if call in fd_reads else "metadata"
                examine(descriptor(args[0], pid), operation, call, raw)
            elif call in ("mmap", "mmap2"):
                if args[4] != "-1":
                    if "MAP_SHARED" in args[3] and "PROT_WRITE" not in args[2]:
                        raise ValueError("shared mapping needs unobserved protection-transition evidence")
                    operation = "write" if "PROT_WRITE" in args[2] and "MAP_SHARED" in args[3] else "read"
                    examine(descriptor(args[4], pid), operation, call, raw)
            elif call in ("sendfile", "copy_file_range"):
                raise ValueError("unsupported file transfer syscall")
            elif call not in harmless:
                raise ValueError("unsupported relevant syscall " + call)
        except (ValueError, SyntaxError, IndexError, TypeError) as error:
            unknown.append(f"{pid}: {call}: {error}")
    if not examined:
        unknown.append("zero filesystem operations examined")
    state = "finding" if findings else "unknown" if unknown else "matches"
    return {"state": state, "examined": examined, "findings": findings, "unknown": unknown,
            "scope": "supplied-copier-child-traces", "runtime_isolation": "unclaimed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        count = 0
        cases = Path(__file__).resolve().parents[1] / "controls/pi-syscall-observer/cases"
        for path in sorted(cases.glob("*/case.json")):
            seed = json.loads(path.read_text())
            expected = {"GOOD": "matches", "BAD": "finding", "UNKNOWN": "unknown"}[seed["expect"]]
            if audit(seed["record"])["state"] != expected:
                raise ValueError("self-test failed: " + path.parent.name)
            count += 1
        if count < 10:
            raise ValueError("incomplete self-test population")
        print("PI_SYSCALL_SELFTEST:", count, "committed reader cases; no host execution claim")
        return 0
    if args.record is None:
        parser.error("record or --self-test required")
    try:
        answer = audit(json.loads(args.record.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as error:
        answer = {"state": "unknown", "reason": str(error), "examined": 0}
    print("PI_SYSCALL:", answer["state"], json.dumps(answer, sort_keys=True))
    return {"matches": 0, "finding": 1, "unknown": 4}[answer["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
