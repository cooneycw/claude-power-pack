#!/usr/bin/env python3
"""Stage a pinned git into `.ci-bin` for the CI steps that need it.

WHY THIS EXISTS (issue #1171). `flow-finish-gate.sh` now derives counter-model
enrolment - it asks whether a review is recorded for THIS branch at a commit
reachable from HEAD - and answering that needs git: `rev-parse`, and
`merge-base --is-ancestor` for the match itself. The pipeline's image
(`ghcr.io/astral-sh/uv:python3.11-bookworm-slim`) HAS NO GIT. Measured, not
assumed: `command -v git` is empty in it, which is also what
`check-test-binary-guards.py` has recorded about that image since #451.

WHAT BREAKS WITHOUT IT, and the number is the point. `scripts/check-control-ci-deps.py`
reports SEVEN registered controls as needing git - `controls/counter-model-enrolment`
plus the six `controls/flow-finish-gate*` registrations - because they all invoke the
same gate. The battery then refuses to run: the harness REFUSES to skip a control it
cannot run, so this is a red rather than a silence, exactly as the `secret-scan`
comment in `.woodpecker.yml` says of gitleaks.

ONLY ONE OF THE SEVEN ACTUALLY NEEDS IT AT RUNTIME, and that is recorded here so
nobody deletes this after measuring the other six. Run in the image with jq and make
staged as `validate` stages them, and no git:

    counter-model-enrolment       UNSIGNALLED   <- genuinely cannot run
    flow-finish-gate              PASS
    flow-finish-gate-resume       PASS
    flow-finish-gate-derivation   PASS

The six pass because their cases carry no receipts directory, so the gate takes the
not-enrolled path where its one git call is already `|| true`. They are staged for
anyway because `check-control-ci-deps` derives REQUIRED from what a script can REACH,
not from what a control's cases execute - a static reader cannot know which path a
case takes. Removing git because six controls pass without it would red the battery
on the static check while also making the seventh unrunnable.

THE SOURCE IS DEBIAN .debs, ten of them, and that is the whole reason this file is
longer than its siblings. jq is one static binary; make is one .deb whose only
shared-library dependency (libc6) is present by construction. git is neither:
`apt-get install --no-install-recommends git` pulls SEVENTEEN packages including
perl, perl-modules-5.36 and git-man. What is staged here is the minimal closure that
actually runs the operations the controls need - git plus its shared libraries, no
perl, no git-man. Verified in the image: `init -b`, `config`, `add`, `commit`,
`rev-parse --show-toplevel` and `merge-base --is-ancestor` all work, with one benign
warning that git's templates are absent.

THE ENVIRONMENT IS SCOPED TO GIT BY A WRAPPER, NOT EXPORTED INTO THE STEP. An
extracted git needs `LD_LIBRARY_PATH` for its libraries and `GIT_EXEC_PATH` for
git-core's helper binaries. Setting those in the `.woodpecker.yml` step would apply
them to EVERY process in it, so all 42 registered controls would run under an altered
loader environment to satisfy one - a global change serving a local need, and the
shape where something unrelated breaks weeks later with nobody connecting it. So
`.ci-bin/git` is a wrapper that sets both on its own exec line. Measured in the
image: with the wrapper on PATH, `LD_LIBRARY_PATH` and `GIT_EXEC_PATH` are both
UNSET in the step, `git --version` works, and a python `subprocess` resolves it -
so `.ci-bin` on PATH remains the entire interface, exactly as it is for jq and make,
and `check-control-ci-deps` keeps deriving PROVIDED the way it does today.

TWO PINS PER ARCHIVE, AND ONE MORE FOR THE BINARY. Each .deb is content-addressed,
and the EXTRACTED `usr/bin/git` is pinned separately - an archive can be repacked
around identical contents, and it is the binary that gets executed. A mismatch on
either is a hard failure, never a warning. That is ci-stage-make's rule (#1165) and
it applies here unchanged.

AND IT RUNS WHAT IT STAGED. `git --version` plus a real `init`/`commit`/
`merge-base --is-ancestor` smoke execute before this reports success, because a copy
that lands is not a tool that runs: #1168 measured a staged `jq` that existed, was
executable, satisfied `command -v` and failed on exec against a missing library. A
stager that only writes bytes cannot tell those apart - and for git the risk is
higher, not lower, because the thing being assembled is a closure rather than a file.
"""

from __future__ import annotations

import hashlib
import io
import lzma
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

#: (url, sha256 of the archive). Bookworm, amd64 - the distribution the image is
#: built from, so libc6 and friends are present by construction. HTTPS is required
#: (see `_require_https`); `apt` prints these as http, and they are rewritten here
#: rather than trusted over plaintext.
PACKAGES: tuple[tuple[str, str], ...] = (
    ("https://deb.debian.org/debian/pool/main/g/git/git_2.39.5-0%2bdeb12u3_amd64.deb",
     "637a85ddd6247fab13bdd0592f2f39aff04ce4dbf0655d3ab553ac359a38ce6f"),
    ("https://deb.debian.org/debian/pool/main/c/curl/libcurl3-gnutls_7.88.1-10%2bdeb12u15_amd64.deb",
     "bf430ecf80f7808704e0187cddc582fd57fc98789ea356d4797651edad387ef3"),
    ("https://deb.debian.org/debian/pool/main/n/nghttp2/libnghttp2-14_1.52.0-1%2bdeb12u3_amd64.deb",
     "5a5736cee57e51c1baed869979e6ecdbc6495e939e33203d6cfe3b6e5a149e3f"),
    ("https://deb.debian.org/debian/pool/main/r/rtmpdump/librtmp1_2.4%2b20151223.gitfa8646d.1-2%2bb2_amd64.deb",
     "e1f69020dc2c466e421ec6a58406b643be8b5c382abf0f8989011c1d3df91c87"),
    ("https://deb.debian.org/debian-security/pool/updates/main/libs/libssh2/libssh2-1_1.10.0-3%2bdeb12u1_amd64.deb",
     "fff72a194e493f88e100a2567e22472bb4ab828d429c2956965c6f2f134f1b3a"),
    ("https://deb.debian.org/debian/pool/main/libp/libpsl/libpsl5_0.21.2-1_amd64.deb",
     "4f0d35610204e4e754b057748719744114621f2f6f4202d846c314860a981afb"),
    ("https://deb.debian.org/debian/pool/main/o/openldap/libldap-2.5-0_2.5.13%2bdfsg-5_amd64.deb",
     "4b6c30f6554149c594628d945edc6003f0eea8d0cc1341638c0e71375db147ed"),
    ("https://deb.debian.org/debian/pool/main/c/cyrus-sasl2/libsasl2-2_2.1.28%2bdfsg-10_amd64.deb",
     "11ee190ad39f8d7af441d2c8347388b9449434c73acc67b4b372445ac4152efa"),
    ("https://deb.debian.org/debian/pool/main/c/cyrus-sasl2/libsasl2-modules-db_2.1.28%2bdfsg-10_amd64.deb",
     "3ac4fd6cbe3b3b06e68d24b931bf3eb9385b42f15604a37ed25310e948ca0ee6"),
    ("https://deb.debian.org/debian/pool/main/b/brotli/libbrotli1_1.0.9-2%2bb6_amd64.deb",
     "563b4caec1aa5e876bd3355b36e7a38e1484baf5a293b48d1e8bd22db786e4d7"),
)

#: The EXTRACTED binary, pinned separately from the archive that carried it.
GIT_BINARY_SHA256 = "2540879925a6881e3877ff7e3330746ba3027b04edf16a3a12dccd1644c4f32d"
GIT_VERSION = "git version 2.39.5"

DEST_DIR = Path(".ci-bin")
GIT_ROOT = DEST_DIR / "git-root"
WRAPPER = DEST_DIR / "git"

#: Written to `.ci-bin/git`. Both variables are set ON THE EXEC LINE, so they apply
#: to git and to nothing else in the step - see the module docstring.
WRAPPER_TEMPLATE = """#!/bin/sh
# Generated by scripts/ci-stage-git.py (issue #1171). Do not edit.
# LD_LIBRARY_PATH and GIT_EXEC_PATH are scoped to this exec and are NOT exported
# into the CI step: every other process in `validate` runs under an unaltered
# loader environment.
LD_LIBRARY_PATH={libs} \\
GIT_EXEC_PATH={exec_path} \\
exec {binary} "$@"
"""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_https(url: str) -> None:
    """Refuse a non-https URL before it reaches `urlopen` (issue #1113).

    The pins below make the BYTES content-addressed, which is what protects the
    contents - but an edit to `http://` would keep every pin satisfied while moving
    the fetch onto a channel an observer can rewrite before the hash is taken.
    """
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme != "https":
        raise SystemExit(
            f"ci-stage-git: refusing a non-https URL (scheme {scheme or 'none'!r}): {url}"
        )


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """A redirect may not downgrade the scheme.

    `HTTPRedirectHandler` permits a redirect to `http` or `ftp`, so without this the
    only scheme actually enforced is the one typed above.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _require_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str) -> bytes:
    _require_https(url)
    opener = urllib.request.build_opener(_HttpsOnlyRedirectHandler())
    with opener.open(url, timeout=120) as resp:
        return resp.read()


def _ar_members(blob: bytes) -> dict[str, bytes]:
    """Read a `.deb` without dpkg or ar.

    An `ar` archive is an 8-byte magic followed by 60-byte headers, each naming a
    member and its decimal size, with members padded to an even offset. Simple
    enough to read directly, and the slim image is guaranteed python3 and guaranteed
    nothing else.
    """
    if not blob.startswith(b"!<arch>\n"):
        raise SystemExit("ci-stage-git: not an ar archive")
    out: dict[str, bytes] = {}
    off = 8
    while off + 60 <= len(blob):
        header = blob[off:off + 60]
        name = header[0:16].decode("ascii", "replace").strip()
        size_field = header[48:58].decode("ascii", "replace").strip()
        if not size_field.isdigit():
            break
        size = int(size_field)
        start = off + 60
        out[name.rstrip("/")] = blob[start:start + size]
        off = start + size + (size % 2)
    return out


def _data_tar(members: dict[str, bytes]) -> tarfile.TarFile:
    for name, blob in members.items():
        if name.startswith("data.tar"):
            if name.endswith(".xz"):
                return tarfile.open(fileobj=io.BytesIO(lzma.decompress(blob)))
            if name.endswith((".gz", ".tar")):
                return tarfile.open(fileobj=io.BytesIO(blob), mode="r:*")
            raise SystemExit(
                f"ci-stage-git: {name} uses a compression this stager does not read. "
                "Bookworm ships data.tar.xz; a change here is a real change and must "
                "not be papered over."
            )
    raise SystemExit("ci-stage-git: no data.tar member in the archive")


def _extract_into(tar: tarfile.TarFile, root: Path) -> None:
    """Extract, refusing any member that would escape `root`.

    `filter="data"` does this in 3.12+, and this file must also run on the image's
    3.11, so the check is explicit rather than delegated.
    """
    root = root.resolve()
    safe = []
    for member in tar.getmembers():
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            continue
        target = (root / member.name.lstrip("./")).resolve()
        if root not in target.parents and target != root:
            raise SystemExit(f"ci-stage-git: refusing member outside the root: {member.name}")
        safe.append(member)
    # ONE MEMBER AT A TIME, not `extractall`. The loop above already refuses anything
    # that would land outside `root`, but `extractall` is B202 to bandit whatever
    # precedes it - a reader, human or tool, cannot see the check from the call. This
    # extracts exactly the members that passed, which is the same thing the check says
    # and the thing the call now shows.
    for member in safe:
        tar.extract(member, root)


def _runs(binary: Path) -> tuple[bool, str]:
    """Execute what was staged. A copy that lands is not a tool that runs (#1168)."""
    try:
        got = subprocess.run([str(binary), "--version"], capture_output=True,
                             text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{binary} did not execute: {exc}"
    if got.returncode != 0:
        return False, f"{binary} --version exited {got.returncode}: {got.stderr.strip()}"
    if GIT_VERSION not in got.stdout:
        return False, f"expected {GIT_VERSION!r}, got {got.stdout.strip()!r}"
    return True, got.stdout.strip()


def _smoke(binary: Path) -> tuple[bool, str]:
    """The operations the controls actually perform, not just `--version`.

    `--version` passes on a git whose helper binaries are unreachable, and
    `merge-base --is-ancestor` is the one this issue's match predicate depends on -
    so it is exercised here rather than discovered in a control's verdict.
    """
    # ABSOLUTE, because this runs with `cwd` inside a temp directory and the wrapper
    # is written at a path relative to the repo root - so a relative argv[0] resolves
    # against the temp dir and raises FileNotFoundError. Found by this smoke test on
    # its first run in the image, which is the argument for having it.
    binary = binary.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        def run(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([str(binary), *args], cwd=tmp, capture_output=True,
                                  text=True, timeout=60)

        got = run("init", "-q", "-b", "master", ".")
        if got.returncode != 0:
            return False, f"init failed: {got.stderr.strip()}"
        Path(tmp, "a.txt").write_text("a\n")
        run("add", "-A")
        got = run("-c", "user.email=ci@ci", "-c", "user.name=ci", "commit", "-qm", "one")
        if got.returncode != 0:
            return False, f"commit failed: {got.stderr.strip()}"
        first = run("rev-parse", "HEAD").stdout.strip()
        Path(tmp, "b.txt").write_text("b\n")
        run("add", "-A")
        run("-c", "user.email=ci@ci", "-c", "user.name=ci", "commit", "-qm", "two")
        got = run("merge-base", "--is-ancestor", first, "HEAD")
        if got.returncode != 0:
            return False, "merge-base --is-ancestor failed on a known ancestor"
        got = run("rev-parse", "--show-toplevel")
        if got.returncode != 0:
            return False, f"rev-parse --show-toplevel failed: {got.stderr.strip()}"
    return True, "init/commit/rev-parse/merge-base --is-ancestor all ran"


def main() -> int:
    if GIT_ROOT.exists():
        shutil.rmtree(GIT_ROOT)
    GIT_ROOT.mkdir(parents=True, exist_ok=True)

    for url, want in PACKAGES:
        name = url.rsplit("/", 1)[-1]
        blob = _fetch(url)
        got = _sha256(blob)
        if got != want:
            print(f"ci-stage-git: {name} sha256 {got} != pinned {want}", file=sys.stderr)
            return 1
        _extract_into(_data_tar(_ar_members(blob)), GIT_ROOT)
        print(f"CI_STAGE_GIT_PACKAGE: {name} {got[:16]} ok")

    binary = GIT_ROOT / "usr" / "bin" / "git"
    if not binary.is_file():
        print("ci-stage-git: no usr/bin/git in the extracted closure", file=sys.stderr)
        return 1
    got = _sha256(binary.read_bytes())
    if got != GIT_BINARY_SHA256:
        print(f"ci-stage-git: extracted git sha256 {got} != pinned {GIT_BINARY_SHA256}",
              file=sys.stderr)
        return 1
    binary.chmod(0o755)
    for helper in (GIT_ROOT / "usr" / "lib" / "git-core").glob("*"):
        if helper.is_file():
            helper.chmod(0o755)

    libs = (GIT_ROOT / "usr" / "lib" / "x86_64-linux-gnu").resolve()
    exec_path = (GIT_ROOT / "usr" / "lib" / "git-core").resolve()
    WRAPPER.write_text(WRAPPER_TEMPLATE.format(
        libs=libs, exec_path=exec_path, binary=binary.resolve()))
    WRAPPER.chmod(0o755)

    ok, detail = _runs(WRAPPER)
    if not ok:
        print(f"ci-stage-git: STAGED BUT UNUSABLE - {detail}", file=sys.stderr)
        return 1
    print(f"CI_STAGE_GIT_VERSION: {detail}")

    ok, detail = _smoke(WRAPPER)
    if not ok:
        print(f"ci-stage-git: STAGED AND RUNS BUT CANNOT WORK - {detail}", file=sys.stderr)
        return 1
    print(f"CI_STAGE_GIT_SMOKE: {detail}")
    print(f"CI_STAGE_GIT: ok ({len(PACKAGES)} package(s) -> {WRAPPER})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
