#!/usr/bin/env python3
"""Stage a pinned GNU make into `.ci-bin` for the CI steps that need it.

WHY THIS EXISTS (issue #1165). Subsumption asks MAKE which prerequisites an
aggregate actually runs, because a textual reader cannot evaluate `ifeq` and so
names prerequisites make will never run - which let a broken lint pass as a
`subsumed` gate. Asking make requires make, and the pipeline's image
(`ghcr.io/astral-sh/uv:python3.11-bookworm-slim`) HAS NONE - measured, not
assumed. Two consequences followed and both are why this file is here:

  * `controls/flow-finish-gate-derivation` went VACUOUS. Its cases still redded,
    but via "make could not be asked" rather than via the derivation - a control
    measuring the absence of a tool instead of its subject.
  * `tests/test_runner.py::TestSubsumedGates` carries a `shutil.which("make")`
    skip guard, so in `validate` it SKIPPED. The issue's own red case was
    untested in the one place a reviewer can re-derive it.

That pair is the jq stager's story exactly (#1017), which is why this is built
in its shape rather than a new one.

THE SOURCE IS A DEBIAN .deb, and that choice is worth stating. There is no
canonical static `make` release to pin the way jq publishes `jq-linux-amd64`,
so the bytes come from Debian's own pool - the same distribution the image is
built from, so its only shared-library dependency (libc6) is present by
construction. Verified: the extracted binary runs in the pinned image and
reports `GNU Make 4.3`.

EXTRACTED WITH THE STDLIB. A `.deb` is an `ar` archive whose `data.tar.xz`
carries `./usr/bin/make`; `ar` is a 60-byte-header format simple enough to read
directly, and `tarfile` handles xz through `lzma`. No `dpkg`, no `ar` binary,
no `curl` - the same reason the jq stager uses python: the slim image is
guaranteed to have python3 and is guaranteed nothing else.

TWO PINS, NOT ONE. The .deb is pinned so the download is content-addressed, and
the EXTRACTED BINARY is pinned too - an archive can be repacked around
identical contents, and it is the binary that gets executed. A mismatch on
either is a hard failure, never a warning.

AND IT EXECUTES WHAT IT STAGED. `make --version` runs before this reports
success, because a copy that lands is not a tool that runs: #1168 measured a
staged `jq` that existed, was executable, satisfied `command -v` and failed on
exec against a missing `libjq.so.1`. A stager that only writes bytes cannot
tell those apart.
"""

from __future__ import annotations

import hashlib
import io
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

#: Debian bookworm's make, from the distribution the image is built from.
MAKE_URL = (
    "https://deb.debian.org/debian/pool/main/m/make-dfsg/make_4.3-4.1_amd64.deb"
)
#: sha256 of the .deb as published.
DEB_SHA256 = "a1a83af8cbd854af887b72ad196b1f4af58387815e21ced1000253a116a46e2a"
#: sha256 of `./usr/bin/make` INSIDE it - the bytes that actually execute.
MAKE_SHA256 = "00b2c2071bf57aa52559a91bf8a4ddcd0fcfd4718da2f83100593a45896c1fec"
#: What `make --version` must report, checked after staging.
MAKE_VERSION = "GNU Make 4.3"

MEMBER = "./usr/bin/make"
DEST_DIR = Path(".ci-bin")
DEST = DEST_DIR / "make"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ar_members(blob: bytes) -> dict[str, bytes]:
    """Every member of an `ar` archive, by name.

    The format is a magic line then, per member, a 60-byte header whose name is
    the first 16 bytes and whose size is bytes 48-58 in decimal, followed by the
    payload padded to an even length. Read directly rather than shelling to
    `ar`, which the slim image does not have.
    """
    if not blob.startswith(b"!<arch>\n"):
        raise ValueError("not an ar archive")
    members: dict[str, bytes] = {}
    offset = 8
    while offset + 60 <= len(blob):
        header = blob[offset : offset + 60]
        name = header[0:16].decode("ascii", "replace").strip().rstrip("/")
        try:
            size = int(header[48:58].decode("ascii", "replace").strip())
        except ValueError as exc:
            raise ValueError(f"unreadable ar member size at offset {offset}") from exc
        members[name] = blob[offset + 60 : offset + 60 + size]
        offset += 60 + size + (size % 2)
    return members


def _extract_make(blob: bytes) -> bytes:
    members = _ar_members(blob)
    data_name = next((n for n in members if n.startswith("data.tar")), None)
    if data_name is None:
        raise ValueError(f"no data.tar member in the .deb (found {sorted(members)})")
    with tarfile.open(fileobj=io.BytesIO(members[data_name])) as archive:
        extracted = archive.extractfile(MEMBER)
        if extracted is None:
            raise ValueError(f"{MEMBER} is not a regular file in {data_name}")
        return extracted.read()


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


def _runs(path: Path) -> tuple[bool, str]:
    """Does the staged binary EXECUTE and report the version we pinned?

    A copy that lands is not a tool that runs (#1168): a staged binary can
    exist, be executable, satisfy `command -v` and still fail on exec against a
    shared library the image does not carry. Only running it settles that, and
    the version string doubles as a check that the bytes are the ones intended.
    """
    try:
        proc = subprocess.run(
            [str(path), "--version"], capture_output=True, text=True, timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    first = (proc.stdout or proc.stderr).splitlines()[:1]
    reported = first[0].strip() if first else "<no output>"
    if proc.returncode != 0:
        return False, f"exit {proc.returncode}: {reported}"
    if not reported.startswith(MAKE_VERSION):
        return False, f"reported {reported!r}, expected {MAKE_VERSION!r}"
    return True, reported


def main() -> int:
    if DEST.is_file() and _sha256(DEST.read_bytes()) == MAKE_SHA256:
        ok, detail = _runs(DEST)
        if ok:
            print(f"ci-stage-make: ok - {DEST} already staged, matches the pin, and runs ({detail})")
            return 0
        print(f"ci-stage-make: {DEST} matches the pin but does NOT run ({detail}); re-staging",
              file=sys.stderr)

    try:
        _require_https(MAKE_URL)
        # NOT suppressed: bandit still reports B310 here, by design. The scheme
        # is enforced on MAKE_URL one line up and on every redirect target by
        # the opener.
        with _HTTPS_ONLY_OPENER.open(MAKE_URL, timeout=120) as response:  # noqa: S310
            payload = response.read()
    except Exception as exc:  # noqa: BLE001 - the cause is reported, not classified
        print(f"ci-stage-make: FAILED to download {MAKE_URL}: {exc}", file=sys.stderr)
        print("ci-stage-make: this is not a pass - subsumption cannot ask make, and the "
              "controls that exercise it cannot run.", file=sys.stderr)
        return 1

    got = _sha256(payload)
    if got != DEB_SHA256:
        print(f"ci-stage-make: SHA256 MISMATCH for {MAKE_URL}", file=sys.stderr)
        print(f"  expected {DEB_SHA256}", file=sys.stderr)
        print(f"  got      {got}", file=sys.stderr)
        return 1

    try:
        binary = _extract_make(payload)
    except (ValueError, tarfile.TarError, OSError) as exc:
        print(f"ci-stage-make: could not extract {MEMBER} from the .deb: {exc}", file=sys.stderr)
        return 1

    binary_hash = _sha256(binary)
    if binary_hash != MAKE_SHA256:
        print(f"ci-stage-make: SHA256 MISMATCH for {MEMBER} inside the .deb", file=sys.stderr)
        print(f"  expected {MAKE_SHA256}", file=sys.stderr)
        print(f"  got      {binary_hash}", file=sys.stderr)
        print("  The archive hashed as expected, so this is a repack around different "
              "contents - which is why the binary is pinned as well.", file=sys.stderr)
        return 1

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(binary)
    DEST.chmod(DEST.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    ok, detail = _runs(DEST)
    if not ok:
        print(f"ci-stage-make: staged {DEST} but it does NOT run: {detail}", file=sys.stderr)
        print("  A copy that landed is not a tool that runs. Reporting failure rather than "
              "a green over a binary nothing can execute (#1168).", file=sys.stderr)
        return 1

    print(f"ci-stage-make: ok - staged {detail} at {DEST} "
          f"({len(binary)} bytes, sha256 {binary_hash}) and it runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
