"""The Makefile and `.woodpecker.yml` pin the SAME images (issue #1029).

`tools-version-check.sh` reads the pinned versions out of the Makefile because
that is where a shell script can reach them cheaply. #1029 asks it to compare
against "the pin that already exists in `.woodpecker.yml` rather than
re-declaring one", and reading a SECOND copy would satisfy the letter of that
while recreating the thing it forbids: two declarations that agree today and
have nothing holding them together tomorrow.

This is what holds them together. The digests must be byte-identical, so
"the Makefile pin" and "the CI pin" are one fact read from two convenient ends,
and a bump that touches only one side turns this red instead of quietly making
the local gate a different instrument from CI's.

No binary is executed here - it is a text comparison over two committed files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
WOODPECKER = ROOT / ".woodpecker.yml"

#: (Makefile variable, image repository). The repository is named so a variable
#: accidentally repointed at a different image is a finding rather than a pass.
PINNED_IMAGES = (
    ("SHELLCHECK_IMAGE", "koalaman/shellcheck-alpine"),
    ("GITLEAKS_IMAGE", "zricethezav/gitleaks"),
)

IMAGE_RE = r"[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}"


def _makefile_pin(variable: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(variable)}\s*:?=\s*({IMAGE_RE})\s*$", re.M)
    match = pattern.search(MAKEFILE.read_text(encoding="utf-8"))
    assert match, f"{variable} is not declared in the Makefile as a digest-pinned image"
    return match.group(1)


def _woodpecker_images(repository: str) -> list[str]:
    pattern = re.compile(
        rf"^\s*image:\s*({re.escape(repository)}:[\w.-]+@sha256:[0-9a-f]{{64}})\s*$", re.M
    )
    return pattern.findall(WOODPECKER.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("variable", "repository"), PINNED_IMAGES)
def test_makefile_and_ci_pin_the_same_image(variable: str, repository: str) -> None:
    makefile_pin = _makefile_pin(variable)
    ci_pins = _woodpecker_images(repository)
    assert ci_pins, f"{repository} is not pinned in .woodpecker.yml"
    assert set(ci_pins) == {makefile_pin}, (
        f"{variable} is {makefile_pin} but .woodpecker.yml uses {sorted(set(ci_pins))}. "
        "Local gates and CI would run different instruments, which is exactly what "
        "pinning the image exists to prevent (#1029)."
    )


def test_the_precondition_holds_both_files_actually_declare_these_pins() -> None:
    """Assert the negative condition before trusting the comparison above.

    A regex that matched nothing on BOTH sides would make every parametrised
    case pass vacuously - the comparison would be between two empty sets and
    would agree perfectly. This is the guard against that reading.
    """
    for variable, repository in PINNED_IMAGES:
        assert _makefile_pin(variable), variable
        assert _woodpecker_images(repository), repository


def test_jq_pin_is_declared_where_tools_version_check_reads_it() -> None:
    """`ci-stage-jq.py` owns the jq version; the checker must have it to read."""
    stager = (ROOT / "scripts" / "ci-stage-jq.py").read_text(encoding="utf-8")
    match = re.search(r"^JQ_URL\s*=\s*\"[^\"]*/jq-(\d+(?:\.\d+)+)/", stager, re.M)
    assert match, "ci-stage-jq.py no longer declares a parseable jq release version"
