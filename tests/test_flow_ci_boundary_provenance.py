"""Tie the constructed boundary bundle's member bytes to its named main commit."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANCHORS = ROOT / "controls/flow-ci-status-boundary/anchors"
requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="requires git to compare frozen source bytes")


@pytest.fixture(scope="module")
def source_bundle():
    bundle = json.loads((ANCHORS / "pre-1758-bundle.json").read_text())
    present = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(ROOT), "cat-file", "-e", bundle["source_main"] + "^{commit}"],
        capture_output=True, text=True, timeout=10,
    )
    if present.returncode:
        pytest.skip(
            f"source commit {bundle['source_main']} unavailable in this clone; "
            "cannot compare bundle provenance (shallow/missing history); fetch the named commit and rerun"
        )
    return bundle


def assert_bundle_matches_main(bundle, directory):
    for path, member in bundle["files"].items():
        original = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(ROOT), "show", bundle["source_main"] + ":" + path],
            capture_output=True, timeout=10,
        )
        assert original.returncode == 0, f"git could not read the named source artifact: {path}"
        actual = (directory / member["path"]).read_bytes()
        assert actual == original.stdout, f"bundle member differs from named main artifact: {path}"


@requires_git
def test_boundary_bundle_matches_named_main_source(source_bundle):
    assert_bundle_matches_main(source_bundle, ANCHORS)


@requires_git
def test_rehashed_altered_bundle_member_fails_main_comparison(tmp_path, source_bundle):
    bundle = json.loads(json.dumps(source_bundle))
    for member in bundle["files"].values():
        shutil.copyfile(ANCHORS / member["path"], tmp_path / member["path"])
    member = bundle["files"]["lib/cicd/flow.py"]
    original = (tmp_path / member["path"]).read_bytes()
    altered = original + b"\n# deliberately changed source bytes\n"
    (tmp_path / member["path"]).write_bytes(altered)
    member["sha256"] = hashlib.sha256(altered).hexdigest()
    assert altered != original
    assert hashlib.sha256((tmp_path / member["path"]).read_bytes()).hexdigest() == member["sha256"]
    with pytest.raises(AssertionError, match="differs from named main artifact"):
        assert_bundle_matches_main(bundle, tmp_path)
