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

FD_ANNOTATION = r"(?:/[^<>]*(?:<(?:char|block) [0-9]+:[0-9]+>)?|(?:pipe:|socket:|anon_inode:)[^<>]*)"
FD_TOKEN = r"-?[0-9]+(?:<" + FD_ANNOTATION + r">)?"


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
    git_roots = allowance.get("git_metadata_roots", [])
    runtime_files = allowance.get("runtime_files", [])
    native_dirs = allowance.get("native_library_dirs", [])
    mode = allowance["mode"]
    if mode not in ("install", "verify", "build", "record-only"):
        raise ValueError("unsupported operation mode")
    roots = [skills, lock, source, allowance["cwd"], *histories, *settings, *allowance.get("metadata", []),
             *allowance.get("runtime_reads", []), *allowance.get("aliases", {}).keys(),
             *allowance.get("aliases", {}).values(), *git_roots, *runtime_files, *native_dirs]
    if not roots or any(not isinstance(p, str) or not p.startswith("/") or posixpath.normpath(p) != p for p in roots):
        raise ValueError("allowance paths must be explicit normalized absolute paths")
    if "/" in (skills, lock, source, *histories, *settings, *allowance.get("runtime_reads", []),
               *runtime_files, *git_roots, *native_dirs):
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
    fd_tables = {}

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

    def descriptor_info(value, pid):
        if value is None:
            raise ValueError("missing descriptor")
        annotated = re.fullmatch(r"(?:[0-9]+|AT_FDCWD)<(/[^<>]*)(?:<(char|block) ([0-9]+):([0-9]+)>)?>", value)
        if annotated:
            target = annotated[1]
            if target.endswith(" (deleted)"):
                target = target[:-10]
            device = (annotated[2], int(annotated[3]), int(annotated[4])) if annotated[2] else None
            return posixpath.normpath(target), device
        if value == "AT_FDCWD":
            return cwd.get(pid), None
        if re.fullmatch(r"[0-9]+<(?:pipe:|socket:|anon_inode:)[^>]*>", value):
            return "stdio-or-ipc", None
        raise ValueError("unresolved file descriptor")

    def descriptor(value, pid):
        return descriptor_info(value, pid)[0]

    def fd_number(value):
        match = re.match(r"[0-9]+", value)
        return match[0] if match else None

    def native_read(path, operation):
        for directory in native_dirs:
            if not inside(path, directory):
                continue
            relative = path[len(directory):].lstrip("/")
            library = re.fullmatch(
                r"(?:glibc-hwcaps/[A-Za-z0-9_.-]+/)?(?:lib[A-Za-z0-9_.+-]+|ld-linux[A-Za-z0-9_.+-]*)\.so(?:\.[0-9]+)*",
                relative)
            gconv = re.fullmatch(r"gconv/[A-Za-z0-9_.+-]+\.so", relative)
            if library or gconv or relative == "gconv/gconv-modules.cache":
                return True
            if operation == "metadata" and (not relative or relative == "gconv" or
                                             re.fullmatch(r"glibc-hwcaps(?:/[A-Za-z0-9_.-]+)?", relative)):
                return True
        return False

    def fd_set(value):
        if value == "NULL":
            return []
        if not (value.startswith("[") and value.endswith("]")):
            raise ValueError("unsupported multiplexing fd set")
        body = value[1:-1]
        tokens, previous = [], 0
        for match in re.finditer(FD_TOKEN, body):
            if body[previous:match.start()].strip(" ,"):
                raise ValueError("unresolved multiplexing fd set")
            tokens.append(match[0])
            previous = match.end()
        if body[previous:].strip(" ,"):
            raise ValueError("truncated/unresolved multiplexing fd set")
        return tokens

    def poll_fds(value, count):
        if value == "NULL" and count == "0":
            return []
        if not (value.startswith("[") and value.endswith("]") and count.isdecimal()):
            raise ValueError("unsupported poll descriptor array")
        rows = arguments(value[1:-1]) if value[1:-1].strip() else []
        if len(rows) != int(count):
            raise ValueError("incomplete poll descriptor population")
        tokens = []
        for row in rows:
            match = re.fullmatch(r"\{fd=(" + FD_TOKEN + r")(?:, events=[^{}]*)?\}", row)
            if not match:
                raise ValueError("unresolved poll descriptor")
            # Negative poll fds are explicitly ignored by the kernel.
            if not match[1].startswith("-"):
                tokens.append(match[1])
        return tokens

    def examine(path, operation, call, args, discard_proven=False):
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
            if path == "/dev/null" and call in ("open", "openat", "openat2", "write", "writev",
                                                "pwrite64", "pwritev", "pwritev2"):
                if discard_proven is None:
                    raise ValueError("discard device identity unresolved")
                if discard_proven:
                    return
            writable = inside(path, skills) if mode != "record-only" else inside(path, skills + "/.cpp-managed")
            if mode == "verify" or not (writable or path == lock):
                findings.append(f"write outside operation allowance: {path}")
            return
        # Source/interpreter reads and exact bounded configuration are distinct
        # from metadata-only ancestor resolution. No general HOME/agent read.
        if (inside(path, skills) or path == lock or inside(path, source) or path in settings or
                path in runtime_files or any(inside(path, root) for root in git_roots) or native_read(path, operation)):
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
                    table = fd_tables.setdefault(pid, {})
                    fd_tables[result] = table if "CLONE_FILES" in raw else dict(table)
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
                flags = "O_WRONLY|O_CREAT|O_TRUNC" if call == "creat" else args[2 if at else 1]
                writing = re.search(r"O_(?:WRONLY|RDWR|CREAT|TRUNC|APPEND)", flags)
                operation = "write" if writing else "read"
                anchor = path == posixpath.dirname(lock) or any(
                    inside(root, path) for root in [skills, source, *git_roots])
                if not writing and "O_DIRECTORY" in flags and anchor:
                    operation = "metadata"
                opened = re.match(FD_TOKEN, result) if re.match(r"[0-9]", result) else None
                info = descriptor_info(opened[0], pid) if opened and "<" in opened[0] else None
                discard = info[1] == ("char", 1, 3) if info and info[0] == "/dev/null" else False
                if re.search(r"O_(?:CREAT|TRUNC|TMPFILE|EXCL)", flags):
                    discard = False
                examine(path, operation, call, raw, discard if info else None)
                if info:
                    examine(info[0], operation, call, raw, discard)
                    fd_tables.setdefault(pid, {})[fd_number(opened[0])] = {
                        "path": info[0], "readonly": "O_RDONLY" in flags and not writing,
                        "cloexec": "O_CLOEXEC" in flags}
                elif opened:
                    raise ValueError("successful open lacks resolved descriptor target")
            elif call in file_calls | writes | {"execve"}:
                operation = "write" if call in writes else "metadata" if call in file_calls else "read"
                examine(path_of(args[0], pid), operation, call, raw)
                if call == "execve" and result == "0":
                    table = fd_tables.setdefault(pid, {})
                    fd_tables[pid] = {n: v for n, v in table.items() if not v["cloexec"]}
            elif call in at_calls | at_writes | {"execveat"}:
                operation = "write" if call in at_writes else "metadata" if call in at_calls else "read"
                examine(path_of(args[1], pid, args[0]), operation, call, raw)
                if call == "execveat" and result == "0":
                    table = fd_tables.setdefault(pid, {})
                    fd_tables[pid] = {n: v for n, v in table.items() if not v["cloexec"]}
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
                target, device = descriptor_info(args[0], pid)
                examine(target, operation, call, raw, device == ("char", 1, 3))
                if call == "fcntl" and args[1] == "F_SETFD" and result == "0":
                    table = fd_tables.setdefault(pid, {})
                    previous = table.get(fd_number(args[0]))
                    if previous:
                        table[fd_number(args[0])] = dict(previous, cloexec="FD_CLOEXEC" in args[2])
                if call == "fcntl" and "F_DUPFD" in args[1] and re.match(r"[0-9]+", result):
                    previous = fd_tables.get(pid, {}).get(fd_number(args[0]))
                    if previous:
                        fd_tables.setdefault(pid, {})[fd_number(result)] = dict(
                            previous, cloexec="F_DUPFD_CLOEXEC" in args[1])
            elif call in ("poll", "ppoll", "ppoll_time64"):
                if len(args) < (3 if call == "poll" else 5):
                    raise ValueError("incomplete polling syscall")
                for value in poll_fds(args[0], args[1]):
                    examine(descriptor(value, pid), "metadata", call, raw)
            elif call in ("select", "_newselect", "pselect6", "pselect6_time64"):
                if len(args) < (5 if call in ("select", "_newselect") else 6) or not args[0].isdecimal():
                    raise ValueError("incomplete select syscall")
                for fd_group in args[1:4]:
                    for value in fd_set(fd_group):
                        examine(descriptor(value, pid), "metadata", call, raw)
            elif call in ("epoll_create", "epoll_create1"):
                if re.match(r"[0-9]+", result):
                    created = re.match(r"[0-9]+(?:<[^>]*>)?", result)
                    assert created
                    examine(descriptor(created[0], pid), "metadata", call, raw)
            elif call == "epoll_ctl":
                for value in (args[0], args[2]):
                    examine(descriptor(value, pid), "metadata", call, raw)
            elif call in ("epoll_wait", "epoll_pwait", "epoll_pwait2"):
                # Event data is caller payload, not an fd. Watched descriptors
                # are checked at epoll_ctl, the instance itself at every wait.
                examine(descriptor(args[0], pid), "metadata", call, raw)
            elif call in ("mmap", "mmap2"):
                if args[4] != "-1":
                    target = descriptor(args[4], pid)
                    if "MAP_SHARED" in args[3] and "PROT_WRITE" not in args[2]:
                        opened = fd_tables.get(pid, {}).get(fd_number(args[4]))
                        if not opened or opened["path"] != target or not opened["readonly"]:
                            raise ValueError("shared mapping lacks observed O_RDONLY provenance")
                    operation = "write" if "PROT_WRITE" in args[2] and "MAP_SHARED" in args[3] else "read"
                    examine(target, operation, call, raw)
            elif call in ("sendfile", "copy_file_range"):
                raise ValueError("unsupported file transfer syscall")
            elif call in ("dup", "dup2", "dup3") and re.match(r"[0-9]+", result):
                table = fd_tables.setdefault(pid, {})
                original = table.get(fd_number(args[0]))
                number = fd_number(result)
                table.pop(number, None)
                if original:
                    table[number] = dict(original, cloexec=call == "dup3" and "O_CLOEXEC" in raw)
            elif call == "close" and result == "0":
                fd_tables.setdefault(pid, {}).pop(fd_number(args[0]), None)
            elif call == "close_range" and result == "0":
                table = fd_tables.setdefault(pid, {})
                if "CLOSE_RANGE_UNSHARE" in raw:
                    table = fd_tables[pid] = dict(table)
                low, high = int(args[0], 0), int(args[1], 0)
                for number in list(table):
                    if low <= int(number) <= high:
                        if "CLOSE_RANGE_CLOEXEC" in raw:
                            table[number] = dict(table[number], cloexec=True)
                        else:
                            del table[number]
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
