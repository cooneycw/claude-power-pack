"""`scripts/ci-stage-make.py` - the pins, the extraction, and the exec check.

NO NETWORK HERE. The download is the one part these tests do not exercise: a
test that fetched the .deb would fail on an offline runner and would be testing
Debian's availability rather than this script. The sha256 pins make the fetched
bytes content-addressed, and `make-stage` in `.woodpecker.yml` is what proves
the fetch works - loudly, in the place that needs it.

The jq stager has no same-named module; its pin is asserted in
`tests/test_pinned_tool_versions.py`, which is jq-specific rather than an
enumeration of stagers. That asymmetry is worth someone's attention and is
reported rather than fixed here (#1165 lane).
"""

from __future__ import annotations

import io
import re
import tarfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STAGER = ROOT / "scripts" / "ci-stage-make.py"


def _stager():
    spec = spec_from_file_location("ci_stage_make", STAGER)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _deb(payload: bytes, member: str = "data.tar.xz") -> bytes:
    """A minimal `ar` archive carrying one member, built the way a .deb is."""
    header = f"{member:<16}{'0':<12}{'0':<6}{'0':<6}{'100644':<8}{len(payload):<10}`\n"
    body = payload + (b"\n" if len(payload) % 2 else b"")
    return b"!<arch>\n" + header.encode() + body


def _data_tar(paths: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as archive:
        for name, blob in paths.items():
            info = tarfile.TarInfo(name)
            info.size = len(blob)
            archive.addfile(info, io.BytesIO(blob))
    return buf.getvalue()


def test_both_pins_are_declared_and_are_sha256_shaped() -> None:
    """TWO pins, not one - the archive AND the binary inside it.

    An archive can be repacked around different contents, and it is the binary
    that gets executed. A single pin on the .deb would content-address the
    download and say nothing about what runs.
    """
    text = STAGER.read_text(encoding="utf-8")
    for name in ("DEB_SHA256", "MAKE_SHA256"):
        match = re.search(rf'^{name} = "([0-9a-f]{{64}})"$', text, re.M)
        assert match, f"{name} is not declared as a 64-hex sha256"
    assert re.search(r'^MAKE_URL = \(\n\s+"https://', text, re.M), "the URL must be https"


def test_the_extraction_finds_make_in_a_deb_shaped_archive(tmp_path) -> None:
    module = _stager()
    payload = _data_tar({"./usr/bin/make": b"\x7fELF-not-really", "./usr/share/doc/x": b"d"})
    assert module._extract_make(_deb(payload)) == b"\x7fELF-not-really"


def test_a_deb_without_the_member_is_an_error_not_an_empty_success(tmp_path) -> None:
    """An archive that parses but lacks `./usr/bin/make` must raise.

    Returning empty bytes would stage a zero-length file that exists, is
    executable, and is not make - the shape #1168 measured with a staged jq
    that could not exec.
    """
    module = _stager()
    payload = _data_tar({"./usr/share/doc/x": b"d"})
    with pytest.raises((ValueError, KeyError)):
        module._extract_make(_deb(payload))


def test_a_non_ar_blob_is_refused() -> None:
    module = _stager()
    with pytest.raises(ValueError):
        module._extract_make(b"this is not an ar archive")


def test_the_exec_check_fails_a_binary_that_cannot_run(tmp_path) -> None:
    """A COPY THAT LANDS IS NOT A TOOL THAT RUNS (#1168).

    The staged file here exists and is executable and is not a program. Only
    running it settles that, which is why the stager runs `make --version`
    before reporting success rather than writing bytes and declaring victory.
    """
    module = _stager()
    fake = tmp_path / "make"
    fake.write_text("#!/nonexistent/interpreter\n")
    fake.chmod(0o755)
    ok, detail = module._runs(fake)
    assert ok is False
    assert detail


def test_the_exec_check_fails_a_runnable_binary_of_the_wrong_version(tmp_path) -> None:
    """Running is necessary, not sufficient: the version string is checked too,
    so a different `make` on the path cannot satisfy the pin by existing."""
    module = _stager()
    impostor = tmp_path / "make"
    impostor.write_text("#!/bin/sh\necho 'GNU Make 9.9'\n")
    impostor.chmod(0o755)
    ok, detail = module._runs(impostor)
    assert ok is False
    assert "9.9" in detail


def test_the_exec_check_accepts_the_pinned_version(tmp_path) -> None:
    module = _stager()
    stand_in = tmp_path / "make"
    stand_in.write_text(f"#!/bin/sh\necho '{module.MAKE_VERSION}'\n")
    stand_in.chmod(0o755)
    ok, detail = module._runs(stand_in)
    assert ok is True, detail
    assert detail.startswith(module.MAKE_VERSION)


def test_the_pipeline_stages_make_for_the_steps_that_need_it() -> None:
    """A stager nothing runs stages nothing.

    `validate` needs it because TestSubsumedGates carries a `make` skip guard -
    without it the issue's own red case SKIPS in CI. `negative-controls` needs
    it because `controls/flow-finish-gate-derivation` exercises the derivation,
    and with no make it measures make's ABSENCE instead of its subject.
    """
    pipeline = (ROOT / ".woodpecker.yml").read_text(encoding="utf-8")
    assert "ci-stage-make.py" in pipeline, "no step stages make"
    for step in ("validate", "negative-controls"):
        block = re.search(rf"^  {step}:\n(?:    .*\n|\n)*", pipeline, re.M)
        assert block, f"{step} step not found"
        assert "make-stage" in block.group(0), f"{step} does not depend on make-stage"
