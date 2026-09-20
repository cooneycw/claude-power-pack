"""One vendor core for CPP's external-repo links (issue #1012).

CPP pulls two cores out of OTHER repositories and keeps a copy here so CI and
local runs never depend on a sibling checkout:

    .claude/commands/flow/eli5.md    <- cooneycw/eli5-gate       (a marker slice)
    vendor/project_next/**           <- cooneycw/codex-power-pack (16 whole files)

Before this module each link carried its own ~290-line script. The scripts were
separately-written solutions to one job - fetch, compare against a recorded
fingerprint, report drift, re-copy on demand - so a third external core meant a
third ~290-line script. This module owns that job once; a link is a
``VendorSpec`` declaration.

WHAT IS SHARED AND WHAT IS NOT. The issue that asked for this described the two
scripts as differing "mainly in constants", with both extracting via begin/end
markers. That is true of eli5 only: project-next vendors whole files and has two
invariants eli5 has no analogue for. So the declaration carries a LAYOUT - how
repo bytes map to named units - alongside its constants, and the layout is where
the two genuinely differ. Everything above it (manifest IO, hashing, fetching,
the fail-open classification, the three modes, the CLI, ``--root``) is here.

Three modes, because they catch different failures and none subsumes another:

``check`` (offline, the hard gate)
    Recompute each unit's sha256 and compare it to the manifest pin. Stdlib
    only, no network and no git, so it runs inside the uv:python3.11-slim
    validate container that ships neither curl nor git (the #451/#489 trap).
    Catches a local edit that bypassed re-vendoring.

``--upstream`` (network, advisory)
    Fetch the canonical copy and diff. This is the check that notices UPSTREAM
    MOVED - a manifest cannot, since it pins what WAS vendored, not what is now
    canonical. Fail-open: any network trouble exits 0 with a note, so an offline
    runner never reddens the pipeline.

``--revendor`` (network, writes)
    Re-fetch, replace in place, and rewrite the manifest so the offline gate
    goes green on the new content. Core and pin move in lockstep, which is the
    whole point of the manifest.

``--root`` EXISTS SO THE GATES CAN BE PROVED. Both scripts used to hardcode the
repository root at module level, so neither could be aimed at a known-bad tree
and neither carried a committed negative control (ADR 0008). A gate that cannot
be pointed at a broken input has never been shown able to fail, and its green is
the same bytes as a blind gate's. Taking the root as an argument is what makes
``controls/eli5-vendor`` and ``controls/project-next-vendor`` possible.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol


class VendorError(Exception):
    """A fatal, LOCAL problem: the gate cannot answer the question it was asked.

    Never fail-open on this. An unreadable manifest or a malformed marker pair
    means the check did not run, and reporting that as "clean" is the blindness
    every mode here exists to avoid.
    """


class SourceUnavailable(Exception):
    """The UPSTREAM source could not be read - network, DNS, HTTP, bad JSON.

    The one exception class the advisory mode is allowed to swallow. It is
    raised only by the fetch path, so "fail-open" can never widen to cover a
    local defect by accident.
    """


class NothingToCheck(Exception):
    """There is no vendored copy here at all.

    Distinct from drift and from a fatal error because the two modes answer it
    differently and both answers are correct: the offline gate treats an absent
    copy as a failure (it is supposed to be here), while the advisory upstream
    diff has nothing to compare and says so without reddening anything.
    """


class CoreNotFound(VendorError):
    """The marker-delimited core is missing or malformed."""


@dataclass(frozen=True)
class Drift:
    """One unit that does not match its pin. `actual` may be a word, not a hash."""

    unit: str
    expected: str
    actual: str


# --- primitives --------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise VendorError(f"manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VendorError(f"manifest is unreadable ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise VendorError(f"manifest is not a JSON object: {path}")
    return data


def write_manifest(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _require_https(url: str) -> None:
    """Refuse any URL that is not `https`, BEFORE it reaches `urlopen`.

    This replaces a comment (issue #1113). The call below used to carry
    `# noqa: S310 - fixed https hosts`, which is an assertion about every
    present and future caller, enforced by nobody. `urllib.request.urlopen`
    handles `file:`, `ftp:` and `data:` as happily as `https:`, so a caller that
    ever passed one through - a URL read from a manifest, a redirect target, a
    default that lost its prefix - would get a silent local file read where the
    comment promised a network fetch. Measured on the pre-#1113 code: a
    `file://` URL returned the file's bytes.

    `SourceUnavailable`, not a new exception type, because every caller already
    handles it and this IS the source being unusable. The class contract in
    `Fetcher` - one exception classification point - is preserved.

    NOTE, so nobody chases it twice: this does NOT clear bandit's B310. B310 is
    a call blacklist with no dataflow analysis, so it reports
    `urllib.request.urlopen` wherever it appears, whatever guards it. The
    finding is dispositioned in `docs/security/bandit-finding-dispositions.md`
    and stays in `.bandit-audit-allow`; what changed here is the hazard, not the
    count.
    """
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme != "https":
        raise SourceUnavailable(
            f"{url}: refusing a non-https URL (scheme {scheme or 'none'!r}); "
            f"this fetcher speaks https only"
        )


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-check the scheme on every REDIRECT, not only on the first URL.

    Checking the caller's URL is not enough (counter-model review, #1113).
    `urllib.request.HTTPRedirectHandler.http_error_302` permits a redirect to
    any of `http`, `https`, `ftp` or a relative target - the stdlib says so in
    a comment beginning "For security reasons" - so a server answering an
    `https` request with `302 Location: http://...` gets followed, and the
    fetch this function promised was https silently is not. That downgrade is
    the position a network attacker needs.

    Enforcing it here rather than post-hoc on `response.url` is the part that
    matters: by the time a downgraded response exists, the plaintext request
    has already crossed the network.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
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


#: Built once, module level, so tests can assert `bytes_at` uses THIS opener
#: rather than the global `urlopen` default.
_HTTPS_ONLY_OPENER = _build_https_only_opener()


@dataclass(frozen=True)
class Fetcher:
    """HTTPS reads with ONE exception classification point.

    Every network error becomes `SourceUnavailable` here and nowhere else. The
    two scripts this replaces each spelled the except-tuple out at three call
    sites, and the tuples had drifted apart - one caught `ValueError` from a bad
    JSON body, the other did not, so a malformed API response was fail-open in
    one script and a traceback in the other.
    """

    user_agent: str
    timeout: int = 15

    def bytes_at(self, url: str) -> bytes:
        _require_https(url)
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            # NOT suppressed: bandit still reports B310 here, by design - see
            # `_require_https` above and the register. The scheme is enforced
            # on the initial URL one line up AND on every redirect target, by
            # the opener's `_HttpsOnlyRedirectHandler`.
            with _HTTPS_ONLY_OPENER.open(request, timeout=self.timeout) as response:  # noqa: S310
                data = response.read()
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            raise SourceUnavailable(f"{url}: {exc}") from exc
        if not isinstance(data, bytes):  # pragma: no cover - defensive
            raise SourceUnavailable(f"{url}: response was not bytes")
        return data

    def text_at(self, url: str) -> str:
        try:
            return self.bytes_at(url).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceUnavailable(f"{url}: response is not UTF-8 ({exc})") from exc

    def json_at(self, url: str) -> Any:
        try:
            return json.loads(self.text_at(url))
        except json.JSONDecodeError as exc:
            raise SourceUnavailable(f"{url}: response is not JSON ({exc})") from exc


# --- marker extraction -------------------------------------------------------


def _marker_bounds(text: str, begin: str, end: str) -> tuple[int, int, list[str]]:
    """`(start, end, lines)` for the marker-delimited slice.

    Marker detection is anchored to the START of a line, so prose that merely
    MENTIONS a marker - eli5.md's Notes bullet does - cannot re-trigger the
    state machine. That anchoring came from the original shell implementation
    and is the reason this is a hand-rolled scan rather than a regex.
    """
    lines = text.splitlines(keepends=True)
    start: int | None = None
    stop: int | None = None
    for index, line in enumerate(lines):
        if start is None and line.startswith(begin):
            start = index + 1
        elif start is not None and line.startswith(end):
            stop = index
            break
    if start is None:
        raise CoreNotFound(f"no line starting with '{begin}'")
    if stop is None:
        raise CoreNotFound(f"'{begin}' has no matching '{end}'")
    return start, stop, lines


def extract_marker_section(text: str, begin: str, end: str) -> str:
    start, stop, lines = _marker_bounds(text, begin, end)
    return "".join(lines[start:stop])


def replace_marker_section(text: str, begin: str, end: str, replacement: str) -> str:
    start, stop, lines = _marker_bounds(text, begin, end)
    return "".join(lines[:start]) + replacement + "".join(lines[stop:])


# --- layouts -----------------------------------------------------------------


class Layout(Protocol):
    """How a declaration maps repository bytes to named, pinnable units.

    A "unit" is whatever the manifest pins one hash for: the marker slice of one
    file, or one whole file out of a fixed set. Everything the modes below do is
    expressed over units, so a third layout (a subtree, a tarball) plugs in
    without touching them.
    """

    #: Does this layout need the manifest for anything but the PIN? A layout
    #: whose upstream coordinates and file set live entirely in the DECLARATION
    #: does not, so both network modes can answer without a readable one - which
    #: is what keeps re-vendoring usable as the repair command for a corrupted
    #: pin file, and what keeps an advisory "have the local bytes diverged from
    #: upstream" from failing over a fact it never consults. A layout that reads
    #: its raw URL or its target path out of the manifest DOES need it, and a
    #: missing one there is a clear error rather than something to paper over.
    #:
    #: It was called `rebuilds_manifest` for one commit, when only `revendor`
    #: read it. The name described that one caller rather than the property, and
    #: went stale the moment `upstream` needed the same answer.
    manifest_is_optional: bool

    def validate(self, manifest: Mapping[str, Any]) -> None:
        """Raise `VendorError` if the manifest cannot be trusted to pin anything.

        Called by `check` ONLY. The advisory diff and the re-vendor write path
        deliberately do not: their questions do not rest on the pin, so a stale
        `vendored_at` must not turn an in-sync verdict into a failure, and a
        corrupt manifest must not block the command that rewrites it.
        """

    def pinned(self, manifest: Mapping[str, Any]) -> dict[str, str]:
        """unit -> sha256 recorded at vendoring time."""

    def local(self, root: Path, manifest: Mapping[str, Any]) -> dict[str, bytes]:
        """Present units only; absent ones are omitted, never faked as empty."""

    def unexpected(self, root: Path, manifest: Mapping[str, Any]) -> list[str]:
        """Units on disk that the manifest does not pin."""

    def audit(self, root: Path, manifest: Mapping[str, Any]) -> list[str]:
        """Layout-specific invariants; each string returned is a fatal finding."""

    def summary(self, root: Path, manifest: Mapping[str, Any]) -> str:
        """The one-line all-clear, naming what was actually compared."""

    def revision(self, fetcher: Fetcher, manifest: Mapping[str, Any]) -> str | None:
        """The upstream revision to vendor, or None when it cannot be pinned."""

    def remote(self, fetcher: Fetcher, manifest: Mapping[str, Any], revision: str | None) -> dict[str, bytes]:
        """Fetch the canonical units. Raises `SourceUnavailable` on any read failure."""

    def apply(self, root: Path, manifest: Mapping[str, Any], snapshot: Mapping[str, bytes]) -> bool:
        """Write the fetched units into the tree. Returns whether anything changed."""

    def repin(
        self, manifest: Mapping[str, Any], snapshot: Mapping[str, bytes], revision: str | None
    ) -> dict[str, Any]:
        """The manifest that pins `snapshot`."""


@dataclass(frozen=True)
class MarkerSectionLayout:
    """One marker-delimited slice of one text file (the eli5-gate link).

    The unit name is the vendored file's repo-relative path, so a drift report
    names a path a reader can open even though the pinned bytes are a slice of
    it.
    """

    begin_marker: str
    end_marker: str
    default_file: str
    subject: str
    #: Canonical coordinates, used when the manifest omits them. They are
    #: DEFAULTS and not requirements: the offline comparison never reads them,
    #: so a manifest missing `source.raw_url` must not flip the hard gate from
    #: pass to fail over metadata the comparison does not use.
    default_raw_url: str = ""
    default_commits_api: str = ""
    #: The raw URL and the target path live in the MANIFEST for this layout, so
    #: without one there is nothing to fetch and nowhere to put it.
    manifest_is_optional: bool = False

    # -- manifest accessors; this layout's schema nests under source/vendored --

    def _file(self, manifest: Mapping[str, Any]) -> str:
        vendored = manifest.get("vendored")
        rel = vendored.get("file") if isinstance(vendored, Mapping) else None
        return rel if isinstance(rel, str) and rel else self.default_file

    def _source(self, manifest: Mapping[str, Any], key: str) -> str:
        source = manifest.get("source")
        value = source.get(key) if isinstance(source, Mapping) else None
        if isinstance(value, str) and value:
            return value
        return {"raw_url": self.default_raw_url, "commits_api": self.default_commits_api}.get(key, "")

    def validate(self, manifest: Mapping[str, Any]) -> None:
        """Nothing to add. The offline gate's question is entirely `pinned()` vs
        the bytes on disk, and validating anything else would make the hard
        gate's verdict depend on fields its comparison never reads."""

    def pinned(self, manifest: Mapping[str, Any]) -> dict[str, str]:
        vendored = manifest.get("vendored")
        digest = vendored.get("core_sha256") if isinstance(vendored, Mapping) else None
        return {self._file(manifest): digest if isinstance(digest, str) else ""}

    def local(self, root: Path, manifest: Mapping[str, Any]) -> dict[str, bytes]:
        rel = self._file(manifest)
        path = root / rel
        if not path.is_file():
            raise NothingToCheck(f"{path} not found")
        core = extract_marker_section(path.read_text(encoding="utf-8"), self.begin_marker, self.end_marker)
        return {rel: core.encode("utf-8")}

    def unexpected(self, root: Path, manifest: Mapping[str, Any]) -> list[str]:
        return []

    def audit(self, root: Path, manifest: Mapping[str, Any]) -> list[str]:
        return []

    def summary(self, root: Path, manifest: Mapping[str, Any]) -> str:
        digest = next(iter(self.pinned(manifest).values()), "")
        upstream = self._source(manifest, "upstream_commit") or "unpinned"
        return f"{self.subject} matches the manifest (sha256 {digest[:12]}, upstream {upstream[:12]})"

    def revision(self, fetcher: Fetcher, manifest: Mapping[str, Any]) -> str | None:
        """Fail-SOFT: an unresolvable commit leaves provenance unpinned, not the run dead.

        The content pin is what the offline gate reads; the commit SHA is
        provenance beside it. Losing provenance is worth a note, and is not
        worth refusing to re-vendor content that fetched cleanly.
        """
        api = self._source(manifest, "commits_api")
        if not api:
            return None
        try:
            payload = fetcher.json_at(api)
        except SourceUnavailable as exc:
            print(f"  could not resolve the upstream commit SHA ({exc}) - leaving it unpinned", file=sys.stderr)
            return None
        if isinstance(payload, list) and payload and isinstance(payload[0], Mapping):
            sha = payload[0].get("sha")
            if isinstance(sha, str):
                return sha
        return None

    def remote(self, fetcher: Fetcher, manifest: Mapping[str, Any], revision: str | None) -> dict[str, bytes]:
        text = fetcher.text_at(self._source(manifest, "raw_url"))
        try:
            core = extract_marker_section(text, self.begin_marker, self.end_marker)
        except CoreNotFound as exc:
            # A canonical copy we cannot slice is an UPSTREAM problem, so it is
            # SourceUnavailable: advisory mode reports and exits 0, re-vendor
            # refuses. Treating it as local would redden an offline pipeline.
            raise SourceUnavailable(f"canonical copy has no usable core ({exc})") from exc
        return {self._file(manifest): core.encode("utf-8")}

    def apply(self, root: Path, manifest: Mapping[str, Any], snapshot: Mapping[str, bytes]) -> bool:
        rel = self._file(manifest)
        path = root / rel
        core = snapshot[rel].decode("utf-8")
        text = path.read_text(encoding="utf-8")
        if extract_marker_section(text, self.begin_marker, self.end_marker) == core:
            return False
        path.write_text(replace_marker_section(text, self.begin_marker, self.end_marker, core), encoding="utf-8")
        return True

    def repin(
        self, manifest: Mapping[str, Any], snapshot: Mapping[str, bytes], revision: str | None
    ) -> dict[str, Any]:
        updated = json.loads(json.dumps(manifest))
        core = snapshot[self._file(manifest)]
        updated.setdefault("source", {})["upstream_commit"] = revision
        vendored = updated.setdefault("vendored", {})
        vendored["core_sha256"] = sha256_hex(core)
        vendored["core_lines"] = len(core.decode("utf-8").splitlines())
        vendored["vendored_at"] = date.today().isoformat()
        return updated


@dataclass(frozen=True)
class FileSetLayout:
    """A fixed set of whole files under one subtree (the project-next link).

    `files` is the HARDCODED UNIVERSE and the manifest supplies the MEMBERS: a
    manifest whose key set differs from `files` is refused rather than trusted,
    so neither a dropped pin nor a smuggled extra file can pass as vendored. The
    same reason the on-disk scan below exists - a file nobody pins is reported,
    not ignored.
    """

    files: tuple[str, ...]
    subtree: str
    source_repo: str
    api_root: str
    raw_root: str
    default_branch: str = "main"
    #: Every upstream coordinate and the whole file set are in this declaration,
    #: so both network modes work from the declaration alone. The manifest here
    #: is a pin file and nothing more.
    manifest_is_optional: bool = True
    #: (relative path, regex with a `version` group, manifest key) or None.
    #: Cross-checks a value DERIVED FROM the vendored bytes against the value
    #: recorded in the manifest, so a hand-edited manifest field cannot claim a
    #: contract version the document does not carry.
    derived_field: tuple[str, str, str] | None = None

    def _root(self, root: Path) -> Path:
        return root / self.subtree

    def validate(self, manifest: Mapping[str, Any]) -> None:
        if manifest.get("source_repo") != self.source_repo:
            raise VendorError(f"manifest source_repo must be {self.source_repo}")
        commit = manifest.get("upstream_commit")
        if not isinstance(commit, str) or len(commit) != 40 or not all(c in "0123456789abcdef" for c in commit):
            raise VendorError("manifest upstream_commit must be a full lowercase commit SHA")
        for key in ("upstream_license", "contract_version"):
            value = manifest.get(key)
            if not isinstance(value, str) or not value.strip():
                raise VendorError(f"manifest {key} must be a non-empty string")
        vendored_at = manifest.get("vendored_at")
        if not isinstance(vendored_at, str):
            raise VendorError("manifest vendored_at must be an ISO date")
        try:
            date.fromisoformat(vendored_at)
        except ValueError as exc:
            raise VendorError("manifest vendored_at must be an ISO date") from exc

    def pinned(self, manifest: Mapping[str, Any]) -> dict[str, str]:
        files = manifest.get("files")
        if not isinstance(files, Mapping):
            raise VendorError("manifest field 'files' must be an object")
        if set(files) != set(self.files):
            missing = sorted(set(self.files) - set(files))
            extra = sorted(set(files) - set(self.files))
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("unexpected " + ", ".join(extra))
            raise VendorError("manifest file set differs from the vendoring contract: " + "; ".join(details))
        for path, digest in files.items():
            ok = isinstance(path, str) and isinstance(digest, str) and len(digest) == 64
            if not ok or not all(c in "0123456789abcdef" for c in digest):
                raise VendorError("manifest file hashes must map paths to lowercase sha256 strings")
        return dict(files)

    def local(self, root: Path, manifest: Mapping[str, Any]) -> dict[str, bytes]:
        present: dict[str, bytes] = {}
        for relative in self.files:
            path = self._root(root) / relative
            if path.is_file():
                present[relative] = path.read_bytes()
        return present

    def unexpected(self, root: Path, manifest: Mapping[str, Any]) -> list[str]:
        base = self._root(root)
        if not base.is_dir():
            return []
        on_disk = {
            path.relative_to(base).as_posix()
            for path in base.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        }
        return sorted(on_disk - set(self.files))

    def _derive(self, content: bytes) -> str:
        assert self.derived_field is not None
        match = re.search(self.derived_field[1], content.decode("utf-8"))
        if not match:
            raise VendorError(f"vendored {self.derived_field[0]} has no {self.derived_field[2]} line")
        return match.group("version")

    def audit(self, root: Path, manifest: Mapping[str, Any]) -> list[str]:
        if self.derived_field is None:
            return []
        relative, _pattern, key = self.derived_field
        try:
            actual = self._derive((self._root(root) / relative).read_bytes())
        except (OSError, UnicodeDecodeError) as exc:
            return [f"{relative}: {exc}"]
        except VendorError as exc:
            return [str(exc)]
        recorded = manifest.get(key)
        if actual != recorded:
            return [f"{key.replace('_', ' ')} mismatch: manifest {recorded!r}, document {actual!r}"]
        return []

    def summary(self, root: Path, manifest: Mapping[str, Any]) -> str:
        commit = str(manifest.get("upstream_commit") or "unpinned")
        detail = ""
        if self.derived_field is not None:
            detail = f" contract v{manifest.get(self.derived_field[2])}"
        return f"{len(self.files)} files match{detail} at {commit[:12]}"

    def revision(self, fetcher: Fetcher, manifest: Mapping[str, Any]) -> str | None:
        """Fail-HARD, deliberately unlike the marker layout.

        A whole-subtree snapshot is fetched AT a revision, so an unresolved
        revision means there is no immutable thing to fetch. Vendoring from the
        moving branch instead would pin hashes to bytes that nothing names.
        """
        payload = fetcher.json_at(f"{self.api_root}/commits/{self.default_branch}")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("sha"), str):
            raise SourceUnavailable("GitHub response did not contain a commit SHA")
        return str(payload["sha"])

    def remote(self, fetcher: Fetcher, manifest: Mapping[str, Any], revision: str | None) -> dict[str, bytes]:
        ref = revision or self.default_branch
        return {relative: fetcher.bytes_at(f"{self.raw_root}/{ref}/{relative}") for relative in self.files}

    def apply(self, root: Path, manifest: Mapping[str, Any], snapshot: Mapping[str, bytes]) -> bool:
        changed = False
        for relative, content in snapshot.items():
            destination = self._root(root) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.is_file() or destination.read_bytes() != content:
                changed = True
            destination.write_bytes(content)
        return changed

    def repin(
        self, manifest: Mapping[str, Any], snapshot: Mapping[str, bytes], revision: str | None
    ) -> dict[str, Any]:
        license_name = snapshot["LICENSE"].decode("utf-8").splitlines()[0].strip() if "LICENSE" in snapshot else ""
        if not license_name:
            raise VendorError("upstream LICENSE has no license name")
        rebuilt: dict[str, Any] = {
            "source_repo": self.source_repo,
            "upstream_commit": revision,
            "upstream_license": license_name,
            "vendored_at": date.today().isoformat(),
        }
        if self.derived_field is not None:
            relative, _pattern, key = self.derived_field
            rebuilt[key] = self._derive(snapshot[relative])
        rebuilt["files"] = {relative: sha256_hex(snapshot[relative]) for relative in sorted(snapshot)}
        return rebuilt


# --- the declaration ---------------------------------------------------------


@dataclass(frozen=True)
class VendorSpec:
    """One external-repo link. Two of these replace two scripts."""

    #: Prefixes every message. Also the control directory's name by convention.
    name: str
    #: What the messages call the thing, in prose: "the vendored eli5 core".
    subject: str
    source_repo: str
    manifest_rel: str
    layout: Layout
    fetcher: Fetcher
    #: The command that reconciles drift, e.g. "make eli5-revendor".
    revendor_hint: str
    #: Extra guidance printed under a drift report. Prose, not a contract.
    remedy: tuple[str, ...] = ()
    #: Printed after a successful re-vendor, e.g. a follow-up sync command.
    revendor_next: tuple[str, ...] = ()
    #: Accept a positional `check` verb. project-next's CLI has always taken one
    #: and `make project-next-check` passes it; eli5's has not.
    check_verb: bool = False
    description: str = ""

    def manifest_path(self, root: Path) -> Path:
        return root / self.manifest_rel

    def say(self, message: str) -> None:
        print(f"{self.name}: {message}")

    def warn(self, message: str) -> None:
        print(f"{self.name}: {message}", file=sys.stderr)


# --- reporting ---------------------------------------------------------------


def render_drift(spec: VendorSpec, manifest_path: Path, entries: Sequence[Drift]) -> None:
    """ONE drift vocabulary for every link, so one `detect_signal` covers them all.

    The two scripts this replaces printed two different headers for the same
    finding, which meant a reader (and a control manifest) had to know which
    script produced a report before knowing what it said. `DRIFT: ` leads every
    one of these now; nothing else this module prints starts with it, which is
    what makes it usable as a detection signal rather than a decoration.
    """
    print("", file=sys.stderr)
    print(f"DRIFT: {spec.subject} does not match the manifest pin.", file=sys.stderr)
    print(f"  manifest: {manifest_path}", file=sys.stderr)
    for entry in entries:
        print(f"  {entry.unit}", file=sys.stderr)
        print(f"    expected: {entry.expected or '(missing)'}", file=sys.stderr)
        print(f"    actual:   {entry.actual}", file=sys.stderr)
    print("", file=sys.stderr)
    for line in spec.remedy:
        print(line, file=sys.stderr)
    print(f"Reconcile upstream first ({spec.source_repo}), then run: {spec.revendor_hint}", file=sys.stderr)


def render_diff(unit: str, local: bytes, remote: bytes) -> None:
    diff = difflib.unified_diff(
        local.decode("utf-8", errors="replace").splitlines(keepends=True),
        remote.decode("utf-8", errors="replace").splitlines(keepends=True),
        fromfile=f"vendored/{unit}",
        tofile=f"upstream/{unit}",
    )
    sys.stderr.writelines(diff)


# --- the three modes ---------------------------------------------------------


def check(spec: VendorSpec, root: Path) -> int:
    """Offline hard gate: every pinned unit must hash to its recorded value."""
    manifest_path = spec.manifest_path(root)
    try:
        manifest = read_manifest(manifest_path)
        spec.layout.validate(manifest)
        pinned = spec.layout.pinned(manifest)
        present = spec.layout.local(root, manifest)
    except NothingToCheck as exc:
        # The offline gate is the half that says the copy is SUPPOSED to be
        # here, so an absent copy fails. The advisory half below reads the same
        # state as "nothing to compare" and exits 0; both are correct for the
        # question each one asks.
        spec.warn(str(exc))
        return 1
    except VendorError as exc:
        spec.warn(str(exc))
        return 1

    findings = spec.layout.audit(root, manifest)
    if findings:
        for finding in findings:
            spec.warn(finding)
        return 1

    entries = [
        Drift(unit, digest, "missing" if unit not in present else sha256_hex(present[unit]))
        for unit, digest in sorted(pinned.items())
        if unit not in present or sha256_hex(present[unit]) != digest
    ]
    entries += [Drift(unit, "(not vendored)", "unexpected file") for unit in spec.layout.unexpected(root, manifest)]
    if entries:
        render_drift(spec, manifest_path, entries)
        return 1

    spec.say(spec.layout.summary(root, manifest))
    return 0


def upstream(spec: VendorSpec, root: Path) -> int:
    """Advisory network diff. Fail-open on the source, never on a local defect."""
    # This mode asks whether the local bytes still match UPSTREAM. The pin plays
    # no part in that, so the manifest is neither validated nor - for a layout
    # that does not need it - required at all (issue #1012, counter-model review
    # passes 1 and 2). Both were reddening an advisory check over facts its own
    # question never consults: first a malformed `vendored_at`, then a deleted
    # pin file. The offline gate is where the pin is judged.
    manifest: dict[str, Any] = {}
    try:
        manifest = read_manifest(spec.manifest_path(root))
    except VendorError as exc:
        if not spec.layout.manifest_is_optional:
            spec.warn(str(exc))
            return 1
        spec.warn(f"{exc} - comparing against upstream anyway")

    try:
        local = spec.layout.local(root, manifest)
    except NothingToCheck as exc:
        spec.warn(f"{exc} (nothing to check)")
        return 0
    except VendorError as exc:
        spec.warn(str(exc))
        return 1

    try:
        revision = spec.layout.revision(spec.fetcher, manifest)
        remote = spec.layout.remote(spec.fetcher, manifest, revision)
    except SourceUnavailable as exc:
        spec.warn(f"upstream unavailable ({exc}) - skipping (fail-open)")
        return 0

    changed = [unit for unit in sorted(remote) if local.get(unit) != remote[unit]]
    if not changed:
        at = f" at {revision[:12]}" if revision else ""
        spec.say(f"{spec.subject} is in sync with {spec.source_repo}{at}")
        return 0

    for unit in changed:
        render_diff(unit, local.get(unit, b""), remote[unit])
    print("", file=sys.stderr)
    print(f"WARNING: {spec.subject} has drifted from {spec.source_repo} in " + ", ".join(changed), file=sys.stderr)
    print(f"Reconcile upstream first, then run: {spec.revendor_hint}", file=sys.stderr)
    return 1


def revendor(spec: VendorSpec, root: Path) -> int:
    """Re-fetch, write in place, and re-pin - content and manifest in lockstep."""
    manifest_path = spec.manifest_path(root)
    try:
        manifest: dict[str, Any] = read_manifest(manifest_path)
    except VendorError as exc:
        # A layout that rebuilds the manifest does not need the old one, and
        # REFUSING HERE WOULD BREAK THE REPAIR PATH: re-vendoring is what an
        # operator runs when the pin file is deleted or corrupt, so rejecting
        # exactly that input is the one failure this mode must not have.
        if not spec.layout.manifest_is_optional:
            spec.warn(str(exc))
            return 1
        spec.warn(f"{exc} - re-vendoring will rebuild it")
        manifest = {}
    # The manifest is NOT validated here: this mode overwrites it, so judging
    # the value about to be replaced can only refuse work that would have
    # succeeded.

    try:
        revision = spec.layout.revision(spec.fetcher, manifest)
        snapshot = spec.layout.remote(spec.fetcher, manifest, revision)
    except SourceUnavailable as exc:
        spec.warn(f"cannot re-vendor - upstream unavailable ({exc})")
        return 1

    # BUILD THE REPLACEMENT PIN BEFORE TOUCHING THE TREE (issue #1012,
    # counter-model review). `repin` is where a fetched snapshot is judged - a
    # contract version derived from the document, a license name read out of
    # LICENSE - and doing that after `apply` meant an upstream that had dropped
    # its version line left all 16 files REPLACED under the OLD manifest, so the
    # offline gate then reported drift on every one of them. The deleted
    # implementation validated first and wrote nothing on a bad snapshot; this
    # restores that order.
    try:
        updated = spec.layout.repin(manifest, snapshot, revision)
    except (VendorError, KeyError, UnicodeDecodeError) as exc:
        spec.warn(f"cannot re-vendor - upstream snapshot is unusable: {exc}")
        return 1

    try:
        changed = spec.layout.apply(root, manifest, snapshot)
        write_manifest(manifest_path, updated)
    except (VendorError, OSError) as exc:
        spec.warn(f"cannot re-vendor: {exc}")
        return 1

    at = f" from {revision[:12]}" if revision else ""
    spec.say(f"{'re-vendored' if changed else 'already current;'} {len(snapshot)} unit(s){at}; updated the manifest")
    for line in spec.revendor_next:
        print(line)
    return 0


# --- entry point -------------------------------------------------------------


def build_parser(spec: VendorSpec, default_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=spec.description or f"Verify or refresh {spec.subject}")
    if spec.check_verb:
        parser.add_argument("command", nargs="?", choices=("check",), default="check")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--upstream", action="store_true", help="diff the vendored copy against the canonical one (network, fail-open)"
    )
    mode.add_argument(
        "--revendor", action="store_true", help="re-fetch the canonical copy, replace it, and re-pin the manifest"
    )
    parser.add_argument(
        "--root",
        default=str(default_root),
        help="tree to operate on (default: this checkout). Fixtures and negative controls pass their own.",
    )
    return parser


def run(spec: VendorSpec, default_root: Path, argv: Sequence[str] | None = None) -> int:
    args = build_parser(spec, default_root).parse_args(argv)
    root = Path(args.root).resolve()
    if args.revendor:
        return revendor(spec, root)
    if args.upstream:
        return upstream(spec, root)
    return check(spec, root)
