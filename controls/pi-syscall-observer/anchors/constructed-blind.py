"""Constructed framing-only reader, blind to all operation/path permissions."""
import json
import re
import sys


def main():
    value = json.load(open(sys.argv[1]))
    traces = list(value["traces"].values())
    children = re.findall(r"(?:clone|clone3|fork|vfork)\(.*\) = ([0-9]+)", "\n".join(traces))
    shared_without_open = any(
        "MAP_SHARED" in line and "PROT_WRITE" not in line and "mmap(" in line and
        not any("openat(" in opening and "O_RDONLY" in opening and "gconv-modules.cache" in opening
                for opening in "\n".join(traces).splitlines())
        for line in "\n".join(traces).splitlines())
    if (any("+++ exited with 0 +++" not in t or '"...' in t or "openat(99," in t for t in traces)
            or any(pid not in value["traces"] for pid in children) or shared_without_open):
        print("PI_SYSCALL: unknown")
        return 4
    print("PI_SYSCALL: matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
