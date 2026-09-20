#!/usr/bin/env python3
"""Stage a CONTENT-PINNED `jq` into `.ci-bin/` for the CI steps that need it (#1017).

WHY THIS EXISTS. `controls/flow-driver-retirement-check` is the first registered
control whose gate needs `jq`, and the CI image
(`ghcr.io/astral-sh/uv:python3.11-bookworm-slim`) has none. Without it the gate
correctly reports `unknown` on EVERY case - which is the honest answer to "I
cannot look" and is also indistinguishable, to the register, from a gate that has
stopped discriminating. So the register reported BLIND and CI went red, exactly
as designed: the harness REFUSES to skip a control it cannot run.

The pytest module was worse. It carried `skipif(shutil.which("jq") is None)`, so
all 26 of its tests SKIPPED in CI and `validate` went green - a suite that was
load-bearing on a dev box and inert in the one environment a reviewer can
re-derive. The register caught what the suite could not, and this script is the
fix for both.

PINNED BY CONTENT, NOT BY TAG. `.woodpecker.yml` pins every image by digest for
a reason it states at the shellcheck step: "running the gate under two different
linters would make the control's verdict depend on which container reached it".
The same applies here and is not hypothetical - `scripts/flow-wave-registry.sh`
carries a "#699 jq-1.6 update trap" comment about an expression that DELETES the
key it was told to update on one version and not the other. A sha256 over the
downloaded bytes gives the same guarantee a digest does.

PYTHON, NOT `curl`. The slim image is guaranteed to have python3 - it is a python
image - and is NOT guaranteed to have curl or wget. A stager that assumes a tool
the image may not carry fails in the same shape as the problem it is fixing.

Idempotent: an already-staged binary whose bytes hash correctly is left alone, so
re-running costs nothing and a step that runs twice does not re-download.
"""

from __future__ import annotations

import hashlib
import stat
import sys
import urllib.parse
import urllib.request
from pathlib import Path

#: jq 1.7.1, linux-amd64, from the project's own GitHub release.
JQ_URL = "https://github.com/jqlang/jq/releases/download/jq-1.7.1/jq-linux-amd64"

#: Measured on 2026-09-16 by downloading the URL above and hashing the bytes.
#: A mismatch is a HARD failure: it means the bytes are not the ones this pin was
#: taken against, and there is no reading of that which makes running them safe.
JQ_SHA256 = "5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5"

DEST_DIR = Path(".ci-bin")
DEST = DEST_DIR / "jq"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_https(url: str) -> None:
    """Refuse a non-https URL before it reaches `urlopen` (issue #1113).

    `JQ_URL` above is a constant, so today this can only fire if someone edits
    it. That is the point at which it is worth having: the sha256 pin below
    guarantees WHAT bytes we accept and says nothing about HOW they arrived, so
    an edit to `file:///...` or `http://...` would keep the pin satisfied while
    changing this from a pinned download into a local file read, or into one
    that a network attacker can answer. Two lines make the transport part of
    what is pinned.

    Raises `ValueError`; `main` classifies it into the existing non-zero
    "this is not a pass" path, so an unusable URL and an unreachable one exit
    the same way rather than one of them tracebacking.

    This does NOT clear bandit's B310 - that rule is a call blacklist with no
    dataflow, so it reports `urlopen` whatever guards it. The finding is
    dispositioned in `docs/security/bandit-finding-dispositions.md`.
    """
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme != "https":
        raise ValueError(
            f"refusing a non-https URL (scheme {scheme or 'none'!r}): {url}"
        )


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-check the scheme on every REDIRECT, not only on `JQ_URL` itself.

    This matters MORE here than at the initial URL, because `JQ_URL` is a
    GitHub release link and GitHub answers it with a 302 to its object store -
    so this download is redirected on every single run, and the redirect
    target is the URL the bytes actually come from. The stdlib's default
    handler permits a redirect to `http` or `ftp`
    (`HTTPRedirectHandler.http_error_302`), so without this the only scheme
    check would be on the one URL that never serves the payload.

    The sha256 pin below would still catch substituted BYTES. It would not
    catch the request going out in the clear, and it is not a reason to skip
    the cheaper guarantee.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_https_only_opener() -> urllib.request.OpenerDirector:
    """An opener that can speak https and NOTHING else, by construction.

    `urllib.request.build_opener()` installs `FileHandler`, `FTPHandler`,
    `DataHandler` and `HTTPHandler` alongside the https one. Measured: an
    opener built that way returns the bytes of a `file:///...` URL. So an
    opener built the default way is exactly as scheme-permissive as the bare
    `urlopen` it replaced, and the ONLY thing standing between it and a local
    file read would be the caller remembering to call `_require_https` first.

    Registering the handlers explicitly moves that from a discipline to a
    property: an unhandled scheme reaches `UnknownHandler`, which raises
    `URLError("unknown url type: file")` - so a future caller who forgets the
    check still cannot read a file with this opener.

    `ProxyHandler()` is included and self-configures from the environment; with
    no proxy set it registers no methods and is not retained, so it costs
    nothing and a proxied CI runner still works.

    `_require_https` is kept in front of this rather than replaced by it. The
    opener decides what is POSSIBLE; the check produces the classified,
    readable error the callers already handle, and refuses before a request is
    built.
    """
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        _HttpsOnlyRedirectHandler(),
        urllib.request.HTTPErrorProcessor(),
        urllib.request.UnknownHandler(),
    ):
        opener.add_handler(handler)
    return opener


_HTTPS_ONLY_OPENER = _build_https_only_opener()


def main() -> int:
    if DEST.is_file():
        have = _sha256(DEST.read_bytes())
        if have == JQ_SHA256:
            print(f"ci-stage-jq: ok - {DEST} already staged and matches the pin")
            return 0
        print(f"ci-stage-jq: {DEST} exists but hashes {have}, re-staging", file=sys.stderr)

    try:
        _require_https(JQ_URL)
        # NOT suppressed: bandit still reports B310 here, by design. The
        # scheme is enforced on JQ_URL one line up and on every redirect
        # target by the opener - GitHub redirects this download every run.
        with _HTTPS_ONLY_OPENER.open(JQ_URL, timeout=120) as response:  # noqa: S310
            payload = response.read()
    except Exception as exc:  # noqa: BLE001 - the cause is reported, not classified
        print(f"ci-stage-jq: FAILED to download {JQ_URL}: {exc}", file=sys.stderr)
        print("ci-stage-jq: this is not a pass - the controls that need jq cannot run.",
              file=sys.stderr)
        return 1

    got = _sha256(payload)
    if got != JQ_SHA256:
        print(f"ci-stage-jq: SHA256 MISMATCH for {JQ_URL}", file=sys.stderr)
        print(f"  expected {JQ_SHA256}", file=sys.stderr)
        print(f"  got      {got}", file=sys.stderr)
        return 1

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(payload)
    DEST.chmod(DEST.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"ci-stage-jq: ok - staged jq 1.7.1 at {DEST} ({len(payload)} bytes, sha256 {got})")
    return 0


if __name__ == "__main__":
    # Deliberately no chdir: every command in `.woodpecker.yml` runs with the
    # workspace as cwd, and a stager that relocates itself would stage into a
    # directory the consuming steps do not put on PATH.
    raise SystemExit(main())
