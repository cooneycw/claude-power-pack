"""Tests for lib/vendor.py - the shared vendor core (issue #1012).

`scripts/eli5-vendor.py` and `scripts/project-next-vendor.py` were two
separately-written solutions to one job. This module is that job, written once;
the two scripts are declarations over it. Their own suites assert what each LINK
must do. What is asserted here is what the SHARED machinery must do, and in
particular the three distinctions that were re-derived (and had drifted apart)
in each script:

  - a LOCAL defect is never fail-open, however the upstream half behaves;
  - an absent copy is a different answer from a drifted one, and the two modes
    answer it differently on purpose;
  - a marker is a marker only at the start of a line.

It also asserts that the two committed controls exist IN THE REPOSITORY. A
control is exercised from the working tree, so an untracked case file passes
every local run and does not exist in a clean clone - the #964/#953 failure,
which `.gitignore`'s blanket `*.json` rule reintroduces for exactly this kind of
fixture.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

from lib import vendor

ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIRS = (ROOT / "controls" / "eli5-vendor", ROOT / "controls" / "project-next-vendor")

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git absent in the CI validate image")


# --- marker extraction -------------------------------------------------------


def test_a_marker_only_counts_at_the_start_of_a_line() -> None:
    text = "mentions BEGIN in prose\nBEGIN\nthe core\nEND\ntrailing\n"
    assert vendor.extract_marker_section(text, "BEGIN", "END") == "the core\n"


def test_an_unterminated_section_is_a_fatal_local_defect() -> None:
    """`CoreNotFound` is a `VendorError`, so every mode treats it as fatal.

    If it were ever reparented under `SourceUnavailable` the advisory half would
    start exiting 0 on a mangled local file, and the pipeline would go green on
    a document nobody could read.
    """
    with pytest.raises(vendor.CoreNotFound):
        vendor.extract_marker_section("BEGIN\ndangling\n", "BEGIN", "END")
    assert issubclass(vendor.CoreNotFound, vendor.VendorError)
    assert not issubclass(vendor.CoreNotFound, vendor.SourceUnavailable)


def test_replacing_a_section_leaves_everything_outside_the_markers_alone() -> None:
    text = "head\nBEGIN\nold\nEND\ntail\n"
    assert vendor.replace_marker_section(text, "BEGIN", "END", "new\n") == "head\nBEGIN\nnew\nEND\ntail\n"


# --- the fail-open boundary --------------------------------------------------


def test_every_network_error_becomes_source_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """ONE classification point, so "fail-open" cannot widen by accident.

    Each script used to spell this except-tuple out at three call sites, and the
    tuples had drifted: a malformed JSON body was fail-open in one and a
    traceback in the other.
    """
    raised: list[str] = []

    def explode(request, timeout=None):  # noqa: ANN001 - stands in for urlopen
        raised.append(getattr(request, "full_url", "?"))
        raise TimeoutError("read timed out")

    # Patches the OPENER, not `urllib.request.urlopen` (#1113): `bytes_at`
    # stopped using the global urlopen when the https-only redirect handler was
    # installed, and a stub left on the old name would be silently bypassed -
    # this test would then make a REAL network call and fail on DNS. The
    # `assert raised` below is what turns that from a silent bypass into a
    # visible one, which is why it is an assertion and not a comment.
    monkeypatch.setattr(vendor._HTTPS_ONLY_OPENER, "open", explode)
    with pytest.raises(vendor.SourceUnavailable):
        vendor.Fetcher(user_agent="test").bytes_at("https://example.invalid/x")
    assert raised, "the stub was never reached, so nothing was classified"


# --- B310: the https assertion, as code rather than a comment (issue #1113) ---
#
# `bytes_at` carried `# noqa: S310 - fixed https hosts`, which is an assertion
# about every caller, enforced by nobody. These tests are what make it true.
#
# They FAIL on the pre-#1113 code in the way that matters: `file://` is not
# refused there, it is FETCHED. A test that only asserted "raises" would be
# satisfied by a URL that happens to be unreachable, so each one below pins
# that the refusal happened WITHOUT a network or filesystem read - the stub
# records every call, and an empty record is the assertion.


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://example.invalid/x",
        "ftp://example.invalid/x",
        "//example.invalid/x",  # scheme-relative: urlsplit gives scheme ''
        "/etc/passwd",  # a bare path, if one ever reaches a URL argument
    ],
)
def test_non_https_urls_are_refused_before_any_fetch(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    reached: list[str] = []

    def spy(request, timeout=None):  # noqa: ANN001 - stands in for urlopen
        reached.append(getattr(request, "full_url", str(request)))
        raise AssertionError(f"urlopen was reached for {url!r}")

    monkeypatch.setattr(vendor._HTTPS_ONLY_OPENER, "open", spy)
    with pytest.raises(vendor.SourceUnavailable, match="https"):
        vendor.Fetcher(user_agent="test").bytes_at(url)
    assert not reached, f"{url!r} reached the opener; the scheme check did not run"


def test_a_file_url_cannot_read_a_real_file(tmp_path) -> None:  # noqa: ANN001
    """The concrete harm, with no stub in the way.

    The parametrized test above proves urlopen is not REACHED. This one proves
    what reaching it would have cost: on the pre-#1113 code this call returns
    the file's bytes, because `urllib.request.urlopen` handles `file:` and
    nobody had told it not to.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text("do-not-exfiltrate\n")

    with pytest.raises(vendor.SourceUnavailable, match="https"):
        vendor.Fetcher(user_agent="test").bytes_at(secret.as_uri())


# --- B310: the redirect half of the same guarantee (counter-model, #1113) ----
#
# Checking the caller's URL is not enough. urllib's default redirect handler
# permits https -> http and https -> ftp by design (see the "For security
# reasons" comment in `HTTPRedirectHandler.http_error_302`), so an initial-URL
# check alone leaves the downgrade a server can force wide open.
#
# These fail on the first-cut #1113 code, which had `_require_https` and still
# used the bare `urllib.request.urlopen`.


@pytest.mark.parametrize("target", ["http://evil.invalid/x", "ftp://evil.invalid/x"])
def test_a_redirect_cannot_downgrade_the_scheme(target: str) -> None:
    handler = vendor._HttpsOnlyRedirectHandler()
    with pytest.raises(vendor.SourceUnavailable, match="https"):
        handler.redirect_request(
            urllib.request.Request("https://example.invalid/x"),
            None,
            302,
            "Found",
            {},
            target,
        )


def test_an_https_redirect_is_still_followed() -> None:
    """The half that must NOT fire.

    A handler that refused every redirect would pass the two cases above and
    break real downloads - GitHub release URLs redirect on every request, which
    is precisely `scripts/ci-stage-jq.py`'s only code path.
    """
    handler = vendor._HttpsOnlyRedirectHandler()
    new = handler.redirect_request(
        urllib.request.Request("https://example.invalid/x"),
        None,
        302,
        "Found",
        {},
        "https://cdn.example.invalid/y",
    )
    assert new is not None
    assert new.full_url == "https://cdn.example.invalid/y"


def test_the_opener_cannot_speak_file_or_ftp_at_all(tmp_path) -> None:  # noqa: ANN001
    """The guard as a PROPERTY, not a discipline (counter-model follow-up).

    `_require_https` protects the two current callers. It does nothing for a
    future third one that forgets it - and once `bytes_at` stopped calling
    `urllib.request.urlopen`, bandit stopped reporting the site too, so that
    future caller would get no warning from either direction.

    Measured on `urllib.request.build_opener()`, which was the first cut: it
    returns the bytes of a `file://` URL. This asserts the replacement cannot.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text("do-not-exfiltrate\n")
    with pytest.raises(Exception) as caught:  # noqa: PT011 - URLError subclass
        vendor._HTTPS_ONLY_OPENER.open(secret.as_uri(), timeout=2)
    assert "unknown url type" in str(caught.value)

    installed = {type(h).__name__ for h in vendor._HTTPS_ONLY_OPENER.handlers}
    assert not installed & {"FileHandler", "FTPHandler", "DataHandler", "HTTPHandler"}


def test_bytes_at_uses_the_hardened_opener_not_the_global_urlopen() -> None:
    """A handler nothing installs is the failure this catches.

    The two tests above exercise the handler directly, so they would both pass
    with `bytes_at` still calling the permissive `urllib.request.urlopen`. This
    is the one that says the guard is on the path the code actually takes.
    """
    import inspect

    source = inspect.getsource(vendor.Fetcher.bytes_at)
    assert "_HTTPS_ONLY_OPENER.open(" in source
    assert "urllib.request.urlopen(" not in source


def test_https_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """The half that must NOT fire: a scheme check that refuses everything
    would pass every test above and break every real fetch."""
    monkeypatch.setattr(
        vendor._HTTPS_ONLY_OPENER,
        "open",
        lambda request, timeout=None: _FakeResponse(b"payload"),  # noqa: ANN001
    )
    assert vendor.Fetcher(user_agent="test").bytes_at("https://example.invalid/x") == b"payload"


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_a_non_json_body_is_source_unavailable_not_a_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vendor.Fetcher, "bytes_at", lambda self, url: b"<html>rate limited</html>")
    with pytest.raises(vendor.SourceUnavailable):
        vendor.Fetcher(user_agent="test").json_at("https://example.invalid/api")


def test_source_unavailable_is_not_a_vendor_error() -> None:
    """The two are deliberately unrelated classes, and the modes rely on it.

    `upstream()` swallows `SourceUnavailable` and nothing else. If it were made
    a subclass of `VendorError` - or the reverse - a local defect would start
    exiting 0 through the same `except`, which is precisely the widening ADR
    0008 warns about when an instrument is changed.
    """
    assert not issubclass(vendor.SourceUnavailable, vendor.VendorError)
    assert not issubclass(vendor.VendorError, vendor.SourceUnavailable)
    assert not issubclass(vendor.NothingToCheck, vendor.VendorError)


# --- manifest IO -------------------------------------------------------------


def test_an_unreadable_manifest_is_fatal_rather_than_empty(tmp_path: Path) -> None:
    """A manifest that will not parse pins nothing, and "pins nothing" must never
    be read as "nothing is drifted"."""
    path = tmp_path / "m.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(vendor.VendorError):
        vendor.read_manifest(path)


def test_a_json_array_manifest_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(vendor.VendorError):
        vendor.read_manifest(path)


def test_a_missing_manifest_is_refused(tmp_path: Path) -> None:
    with pytest.raises(vendor.VendorError):
        vendor.read_manifest(tmp_path / "absent.json")


def test_write_manifest_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "m.json"
    vendor.write_manifest(path, {"a": 1})
    assert vendor.read_manifest(path) == {"a": 1}
    assert path.read_text(encoding="utf-8").endswith("\n"), "manifests end with a newline"


# --- the shared drift vocabulary ---------------------------------------------


def test_the_drift_header_is_what_the_controls_detect_on(capsys: pytest.CaptureFixture[str]) -> None:
    """One vocabulary across every link, so ONE `detect_signal` covers them all.

    Both `controls/*/control.json` files key on this line. If the wording moves,
    the controls report UNSIGNALLED - the gate exited like a finding and said
    nothing that identifies one - rather than silently scoring a crash as a
    detection.
    """
    spec = vendor.VendorSpec(
        name="probe-vendor",
        subject="the probed core",
        source_repo="https://example.invalid/repo",
        manifest_rel=".claude/probe.json",
        layout=vendor.MarkerSectionLayout("BEGIN", "END", "probe.md", "probed core"),
        fetcher=vendor.Fetcher(user_agent="probe"),
        revendor_hint="make probe-revendor",
    )
    vendor.render_drift(spec, Path("/tmp/probe.json"), [vendor.Drift("probe.md", "aaa", "bbb")])
    err = capsys.readouterr().err
    for control in CONTROL_DIRS:
        pattern = json.loads((control / "control.json").read_text(encoding="utf-8"))["detect_signal"]
        assert vendor.re.search(pattern, err, vendor.re.MULTILINE), f"{control.name} would not detect this report"


def test_the_drift_signal_does_not_match_a_clean_run() -> None:
    """A pattern that also matches the all-clear identifies a clean run as a
    finding, which is the same blindness pointed the other way."""
    clean = "eli5-vendor: vendored core matches the manifest (sha256 abc, upstream def)"
    for control in CONTROL_DIRS:
        pattern = json.loads((control / "control.json").read_text(encoding="utf-8"))["detect_signal"]
        assert not vendor.re.search(pattern, clean, vendor.re.MULTILINE)
        assert not vendor.re.search(pattern, "", vendor.re.MULTILINE), "a pattern matching empty output detects nothing"


# --- the committed controls exist in a clean clone ---------------------------


@requires_git
@pytest.mark.parametrize("control", CONTROL_DIRS, ids=lambda p: p.name)
def test_every_file_of_the_control_is_tracked(control: Path) -> None:
    """A control is exercised from the WORKING TREE, so an untracked case file
    discriminates locally and does not exist downstream. `.gitignore` carries a
    blanket `*.json` whose `!controls/*/control.json` negation is one level deep
    and cannot reach a case tree; these controls put a manifest inside one, so
    the negation added in #1012 is what this asserts still holds."""
    tracked = set(
        subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", str(control.relative_to(ROOT))],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    )
    on_disk = {str(p.relative_to(ROOT)) for p in control.rglob("*") if p.is_file()}
    assert on_disk, f"{control} is empty; this test is vacuous"
    missing = sorted(on_disk - tracked)
    assert not missing, f"not tracked, so a clean checkout gets a broken control: {missing}"


@pytest.mark.parametrize("control", CONTROL_DIRS, ids=lambda p: p.name)
def test_the_control_declares_one_bad_case_and_one_good_case(control: Path) -> None:
    """Both directions, always. A gate wedged at "fail" passes the known-bad
    half on its own, so the good case is what separates a working gate from a
    stuck one."""
    spec = json.loads((control / "control.json").read_text(encoding="utf-8"))
    expectations = [case["expect"] for case in spec["cases"]]
    assert "BAD" in expectations and "GOOD" in expectations
    for case in spec["cases"]:
        assert (control / case["input"]).is_dir(), f"{case['name']} names a directory that is not here"


@pytest.mark.parametrize("control", CONTROL_DIRS, ids=lambda p: p.name)
def test_the_anchor_file_named_by_the_control_is_present_and_pinned(control: Path) -> None:
    spec = json.loads((control / "control.json").read_text(encoding="utf-8"))
    for anchor in spec["anchors"]:
        path = control / anchor["path"]
        assert path.is_file(), f"{control.name} names an anchor that is not here: {anchor['path']}"
        assert vendor.sha256_hex(path.read_bytes()) == anchor["sha256"], (
            f"{control.name}'s anchor no longer matches its recorded sha256. An anchor is evidence only "
            "while it is byte-identical to what was registered; re-pin it deliberately, never silently."
        )


# --- the re-vendor write path ------------------------------------------------
#
# Added with the fixes for the #1012 counter-model review, which found this path
# uncovered and wrong in two ways: it wrote the tree before judging the fetched
# snapshot, and it refused to run at all without a valid manifest - on the one
# command an operator uses to REPAIR a broken manifest.

CONTRACT = "docs/contract.md"
FILES = ("LICENSE", CONTRACT, "engine.py")


def _fileset_spec() -> vendor.VendorSpec:
    return vendor.VendorSpec(
        name="probe-vendor",
        subject="the probed snapshot",
        source_repo="https://example.invalid/upstream",
        manifest_rel=".claude/probe-vendor.json",
        layout=vendor.FileSetLayout(
            files=FILES,
            subtree="vendor/probe",
            source_repo="https://example.invalid/upstream",
            api_root="https://api.example.invalid/upstream",
            raw_root="https://raw.example.invalid/upstream",
            derived_field=(CONTRACT, r"Contract version `(?P<version>[^`]+)`", "contract_version"),
        ),
        fetcher=vendor.Fetcher(user_agent="probe"),
        revendor_hint="make probe-revendor",
    )


def _upstream(contract: str = "Contract version `2.0`\n", license_text: str = "MIT License\n") -> dict[str, bytes]:
    return {
        "LICENSE": license_text.encode("utf-8"),
        CONTRACT: contract.encode("utf-8"),
        "engine.py": b"ENGINE = 'new'\n",
    }


def _serve(monkeypatch: pytest.MonkeyPatch, snapshot: dict[str, bytes]) -> list[str]:
    """Answer both the commit API and every raw file read from one stub."""
    seen: list[str] = []

    def bytes_at(self, url: str) -> bytes:
        seen.append(url)
        if url.startswith("https://api."):
            return json.dumps({"sha": "b" * 40}).encode("utf-8")
        for relative, body in snapshot.items():
            if url.endswith("/" + relative):
                return body
        raise vendor.SourceUnavailable(f"no fixture for {url}")

    monkeypatch.setattr(vendor.Fetcher, "bytes_at", bytes_at)
    return seen


def _vendored_tree(root: Path, *, with_manifest: bool = False) -> Path:
    base = root / "vendor" / "probe"
    base.mkdir(parents=True)
    for relative in FILES:
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"original {relative}\n", encoding="utf-8")
    if with_manifest:
        # The contract document must carry the version the manifest records, or
        # `check` fails on the derived-field audit before reaching the
        # comparison - a green/red decided by the wrong invariant.
        (base / CONTRACT).write_text("Contract version `1.0`\n", encoding="utf-8")
        # A VALID pre-existing manifest, so a test about WRITE ORDER is decided
        # by the write order. Without it, reverting the ordering leaves the test
        # green for an unrelated reason - the run stops at the missing manifest
        # before it ever fetches - and the test would claim a property it never
        # exercised.
        vendor.write_manifest(
            root / ".claude" / "probe-vendor.json",
            {
                "source_repo": "https://example.invalid/upstream",
                "upstream_commit": "a" * 40,
                "upstream_license": "MIT License",
                "contract_version": "1.0",
                "vendored_at": "2026-09-16",
                "files": {rel: vendor.sha256_hex((base / rel).read_bytes()) for rel in FILES},
            },
        )
    return base


def test_revendor_writes_the_snapshot_and_repins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The half that separates a working re-vendor from one that refuses everything."""
    base = _vendored_tree(tmp_path, with_manifest=True)
    fetched = _serve(monkeypatch, _upstream())

    assert vendor.revendor(_fileset_spec(), tmp_path) == 0
    assert fetched, "nothing was fetched, so nothing was proved about writing"
    assert (base / "engine.py").read_text(encoding="utf-8") == "ENGINE = 'new'\n"
    manifest = vendor.read_manifest(tmp_path / ".claude" / "probe-vendor.json")
    assert manifest["contract_version"] == "2.0"
    assert manifest["upstream_commit"] == "b" * 40
    assert manifest["files"]["engine.py"] == vendor.sha256_hex(b"ENGINE = 'new'\n")


def test_an_unusable_snapshot_is_rejected_BEFORE_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Zero writes, not sixteen and an apology.

    Judging the fetched snapshot AFTER applying it left the tree replaced under
    the previous manifest, so the offline gate then reported drift on every
    file - a re-vendor that reddens the very gate it exists to green. The
    assertion is on the TREE, because an exit code alone cannot tell "refused"
    from "wrote everything, then refused".
    """
    base = _vendored_tree(tmp_path, with_manifest=True)
    manifest_path = tmp_path / ".claude" / "probe-vendor.json"
    before = {relative: (base / relative).read_bytes() for relative in FILES}
    pinned_before = manifest_path.read_bytes()
    _serve(monkeypatch, _upstream(contract="# no version line here\n"))

    assert vendor.revendor(_fileset_spec(), tmp_path) == 1
    assert "unusable" in capsys.readouterr().err
    after = {relative: (base / relative).read_bytes() for relative in FILES}
    assert after == before, "a rejected snapshot must leave the vendored tree untouched"
    assert manifest_path.read_bytes() == pinned_before, "and must leave the existing pin alone"


def test_a_blank_license_is_also_rejected_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _vendored_tree(tmp_path, with_manifest=True)
    before = (base / "engine.py").read_bytes()
    _serve(monkeypatch, _upstream(license_text="\n\nMIT\n"))

    assert vendor.revendor(_fileset_spec(), tmp_path) == 1
    assert (base / "engine.py").read_bytes() == before


def test_revendor_rebuilds_a_manifest_that_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Re-vendoring IS the repair path for a deleted or corrupt pin file.

    Requiring a valid manifest here refused exactly the input the command exists
    to fix. A layout whose upstream coordinates all live in its declaration owes
    the old manifest nothing.
    """
    _vendored_tree(tmp_path)
    manifest_path = tmp_path / ".claude" / "probe-vendor.json"
    assert not manifest_path.exists(), "fixture must start with no manifest"
    _serve(monkeypatch, _upstream())

    assert vendor.revendor(_fileset_spec(), tmp_path) == 0
    assert "rebuild" in capsys.readouterr().err
    assert vendor.read_manifest(manifest_path)["contract_version"] == "2.0"


def test_revendor_rebuilds_over_a_corrupt_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vendored_tree(tmp_path)
    manifest_path = tmp_path / ".claude" / "probe-vendor.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("{ this will not parse", encoding="utf-8")
    with pytest.raises(vendor.VendorError):
        vendor.read_manifest(manifest_path)  # precondition: it really is corrupt
    _serve(monkeypatch, _upstream())

    assert vendor.revendor(_fileset_spec(), tmp_path) == 0
    assert vendor.read_manifest(manifest_path)["upstream_commit"] == "b" * 40


def _marker_spec() -> vendor.VendorSpec:
    return vendor.VendorSpec(
        name="probe-vendor",
        subject="the probed core",
        source_repo="https://example.invalid/repo",
        manifest_rel=".claude/probe.json",
        layout=vendor.MarkerSectionLayout("BEGIN", "END", "probe.md", "probed core"),
        fetcher=vendor.Fetcher(user_agent="probe"),
        revendor_hint="make probe-revendor",
    )


@pytest.mark.parametrize("mode", [vendor.revendor, vendor.upstream], ids=["revendor", "upstream"])
def test_a_layout_that_needs_its_manifest_still_refuses_a_missing_one(tmp_path: Path, mode) -> None:
    """The narrow half: tolerance is a LAYOUT property, not a blanket.

    A marker layout reads its raw URL and its target path out of the manifest,
    so without one there is nothing to fetch and nowhere to put it. Saying
    "manifest not found" is the useful answer; fetching an empty URL is not.
    Without this, "the manifest is optional" would quietly become "the manifest
    is ignored", and both network modes would answer nonsense instead of
    refusing.
    """
    spec = _marker_spec()
    assert spec.layout.manifest_is_optional is False
    assert not (tmp_path / ".claude" / "probe.json").exists(), "fixture must lack the manifest"
    assert mode(spec, tmp_path) == 1


def test_upstream_ignores_manifest_metadata_its_question_does_not_rest_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An in-sync tree must not exit 1 over a malformed `vendored_at`.

    The advisory diff asks whether local bytes still match UPSTREAM. The pin
    plays no part in that, so validating it here turned an advisory check into
    one that reddens on a fact its own question never consults.
    """
    base = _vendored_tree(tmp_path)
    snapshot = _upstream()
    for relative, body in snapshot.items():
        (base / relative).write_bytes(body)
    manifest_path = tmp_path / ".claude" / "probe-vendor.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"vendored_at": "not-a-date", "files": {}}), encoding="utf-8")
    spec = _fileset_spec()
    with pytest.raises(vendor.VendorError):
        spec.layout.validate(vendor.read_manifest(manifest_path))  # precondition: it IS invalid
    _serve(monkeypatch, snapshot)

    assert vendor.upstream(spec, tmp_path) == 0


@pytest.mark.parametrize("damage", [None, "{ not json"], ids=["absent", "malformed"])
def test_upstream_answers_without_a_manifest_the_layout_does_not_need(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str | None
) -> None:
    """An in-sync tree must report in-sync even with the pin file gone.

    Every coordinate a file-set comparison needs - the API root, the raw root,
    the file list - is in the declaration. Requiring a readable manifest here
    made `make project-next-drift` refuse to answer on exactly the repository
    state an operator would run it to understand. Found on the second
    counter-model pass, after the first fix addressed only `revendor`.
    """
    base = _vendored_tree(tmp_path)
    snapshot = _upstream()
    for relative, body in snapshot.items():
        (base / relative).write_bytes(body)
    manifest_path = tmp_path / ".claude" / "probe-vendor.json"
    if damage is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(damage, encoding="utf-8")
    with pytest.raises(vendor.VendorError):
        vendor.read_manifest(manifest_path)  # precondition: it really is unreadable
    _serve(monkeypatch, snapshot)

    assert vendor.upstream(_fileset_spec(), tmp_path) == 0


def test_upstream_still_reports_drift_without_a_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction, so "answers without a manifest" cannot become
    "answers GOOD without a manifest" - a check that stopped comparing would
    pass the test above just as well."""
    _vendored_tree(tmp_path)  # 'original ...' bytes, which the snapshot replaces
    assert not (tmp_path / ".claude" / "probe-vendor.json").exists(), "fixture must lack the manifest"
    _serve(monkeypatch, _upstream())

    assert vendor.upstream(_fileset_spec(), tmp_path) == 1
    assert "has drifted" in capsys.readouterr().err


# --- narrowness: can a non-zero tell OUR thing from a NEIGHBOUR's? -----------
#
# The second of the two detector-contract questions, asked of both gates. A
# vendor gate that reddens on a change anywhere in the repository would be
# "working" by the drift tests above and useless in practice, and the person who
# found out would be whoever's unrelated commit it blocked. Red cases named by
# the #1012 counter-model review.


def test_the_fileset_gate_ignores_changes_outside_its_subtree(tmp_path: Path) -> None:
    root = _vendored_tree(tmp_path, with_manifest=True).parent.parent
    assert vendor.check(_fileset_spec(), root) == 0, "precondition: the pinned tree is clean"
    neighbour = root / "unrelated" / "neighbour.py"
    neighbour.parent.mkdir(parents=True)
    neighbour.write_text("NEIGHBOUR = 1\n", encoding="utf-8")

    assert vendor.check(_fileset_spec(), root) == 0, "a file outside vendor/probe is not this gate's business"


def test_the_marker_gate_ignores_changes_outside_its_markers(tmp_path: Path) -> None:
    document = tmp_path / "probe.md"
    document.write_text("head\nBEGIN\npinned\nEND\ntail\n", encoding="utf-8")
    vendor.write_manifest(
        tmp_path / ".claude" / "probe.json",
        {"vendored": {"file": "probe.md", "core_sha256": vendor.sha256_hex(b"pinned\n")}},
    )
    spec = _marker_spec()
    assert vendor.check(spec, tmp_path) == 0, "precondition: the pinned core is clean"

    document.write_text("REWRITTEN HEAD\nBEGIN\npinned\nEND\nREWRITTEN TAIL\n", encoding="utf-8")
    assert vendor.check(spec, tmp_path) == 0, (
        "text outside the markers is CPP's own wiring, not upstream's - this gate pins the core and "
        "must not redden on the surrounding document"
    )


# --- the .gitignore negation is a hole, not a hole-saw ------------------------


@requires_git
def test_the_control_case_json_negation_does_not_leak_past_controls() -> None:
    """`!controls/*/cases/**/*.json` must re-include the case manifests and NOTHING else.

    A negation written one character too wide stops being an exception and
    becomes the rule: `.claude/settings.local.json` and every other JSON the
    blanket `*.json` line exists to keep out would start being offered to
    `git add`. Asserting only the positive half - "the case manifest is
    trackable" - passes just as well when the negation matches everything.
    """
    case_manifest = "controls/eli5-vendor/cases/good-pinned-core/.claude/eli5-vendor.json"
    assert (ROOT / case_manifest).is_file(), "precondition: the case manifest is really there"

    def ignored(path: str) -> bool:
        return subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", path], check=False
        ).returncode == 0

    assert not ignored(case_manifest), "the negation must reach the case manifest"
    # A JSON directly inside a case directory is IN scope: `**` matching zero
    # directories is the intended reach, since a case tree nests as deep as the
    # repository it models. The leak to guard against is anything OUTSIDE
    # controls/*/cases/.
    assert not ignored("controls/eli5-vendor/cases/good-pinned-core/notes.json")
    # The anchor-fixture negation (#1017) is the second hole in this line, and it
    # is NAMED rather than globbed for the reason this test exists: its first cut
    # was `!controls/*/anchors/**/*.json`, which re-included every JSON in every
    # anchors directory and turned the exception into the rule. Pinned here so the
    # boundary is asserted from both sides.
    anchor_fixture = "controls/flow-driver-retirement-check/anchors/wrong-object-roster.json"
    assert (ROOT / anchor_fixture).is_file(), "precondition: the anchor fixture is really there"
    assert not ignored(anchor_fixture), "the negation must reach the anchor fixture"
    for still_ignored in (
        "controls/eli5-vendor/anchors/notes.json",  # a control dir, but not a case tree
        # ...and an anchors dir is not a blanket either: only the NAMED fixture
        # above is re-included, so a sibling JSON beside it stays out.
        "controls/flow-driver-retirement-check/anchors/notes.json",
        ".claude/settings.local.json",
        "docs/somewhere/else.json",
        "scratch.json",
    ):
        assert ignored(still_ignored), f"{still_ignored} must stay ignored - the negation leaked"
