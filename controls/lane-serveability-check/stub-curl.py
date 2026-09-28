#!/usr/bin/env python3
"""Stub `curl` for controls/lane-serveability-check (issue #1281). NOT A CLIENT.

It answers from files, never from a network. run-case.sh puts it first on PATH
as `curl`, and it maps the request URL's path to a canned response under
$LANE_STUB_RESPONSES:

    <name>.status       HTTP status the response carries        (e.g. 500)
    <name>.body         response body, written to -o            (verbatim)
    <name>.curl_exit    OR: curl's own exit code for a transport
                        failure; no body, http_code 000

where <name> is `version`, `tags` or `generate` for /api/version, /api/tags and
/api/generate. That is the whole of what the stub models: WHAT CAME BACK. It
does not model transport - timing, redirects, TLS, partial reads - so the
control built on it proves how the gate CLASSIFIES a response, not how the gate
behaves on a real socket. control.json's `limits` says so.

ONLY THE FLAGS THE GATE PASSES ARE HONOURED: -s, -o FILE, -w FORMAT (with
%{http_code} and %{time_total}), --max-time N, -H HEADER, -d DATA, and one URL.
Anything else is a usage this stub was not written for. It then does NOT answer
- an answer invented for an unrecognised request is the fabricated evidence a
stub must never produce - and it records the refusal in $LANE_STUB_ERRORS, which
run-case.sh reads so the case reports `cannot-run` instead of whatever verdict
the gate formed from a stub that fell over. Every call is logged to
$LANE_STUB_CALLS so run-case.sh can tell a gate that probed from one that never
reached the stub at all.
"""
import os
import sys
from urllib.parse import urlsplit

FIXED_ELAPSED = "0.012"


def refuse(why: str) -> "None":
    with open(os.environ["LANE_STUB_ERRORS"], "a") as fh:
        fh.write(why + "\n")
    sys.exit(2)


def main(argv: list) -> int:
    out_file = None
    fmt = None
    url = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "-s":
            i += 1
        elif a in ("-o", "-w", "--max-time", "-H", "-d"):
            if i + 1 >= len(argv):
                refuse(f"flag {a} has no value")
            if a == "-o":
                out_file = argv[i + 1]
            elif a == "-w":
                fmt = argv[i + 1]
            i += 2
        elif a.startswith("-"):
            refuse(f"unsupported flag {a!r}")
        else:
            if url is not None:
                refuse(f"a second URL {a!r}")
            url = a
            i += 1
    if url is None:
        refuse("no URL")

    path = urlsplit(url).path
    name = {"/api/version": "version", "/api/tags": "tags", "/api/generate": "generate"}.get(path)
    if name is None:
        refuse(f"no fixture for path {path!r}")
    with open(os.environ["LANE_STUB_CALLS"], "a") as fh:
        fh.write(name + "\n")

    base = os.path.join(os.environ["LANE_STUB_RESPONSES"], name)
    if os.path.exists(base + ".curl_exit"):
        code = int(open(base + ".curl_exit").read().strip())
        status, body = "000", b""
    elif os.path.exists(base + ".status"):
        code = 0
        status = open(base + ".status").read().strip()
        body = open(base + ".body", "rb").read() if os.path.exists(base + ".body") else b""
    else:
        refuse(f"fixture {name} has neither .status nor .curl_exit")

    if out_file is not None:
        with open(out_file, "wb") as fh:
            fh.write(body)
    elif body:
        sys.stdout.buffer.write(body)
    if fmt is not None:
        sys.stdout.write(fmt.replace("%{http_code}", status).replace("%{time_total}", FIXED_ELAPSED))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
