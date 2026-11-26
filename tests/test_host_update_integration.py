"""One current source invocation feeds actual adapters, not fixture adapters."""
import shutil

import pytest

from lib.host_update.host import INCLUDED, registry, run_host
from lib.host_update.models import ExpectedBuild
from tests.test_host_update_adapters import cli, files, git, request
from tests.test_host_update_adapters import source as source_fixture
from tests.test_host_update_adapters import source_template as template_fixture

source = source_fixture
source_template = template_fixture

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git required for real integration")


def test_current_checkout_refreshes_all_from_one_revision(source, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    assert run_host(registry(home, INCLUDED), request(source)).exit_code == 0
    neighbor = home / ".gemini/config/skills/personal/SKILL.md"
    neighbor.parent.mkdir()
    neighbor.write_bytes(b"foreign exact bytes")
    before = files(neighbor.parent)
    guide = source / "docs/skills/python-packaging.md"
    guide.write_bytes(guide.read_bytes() + b"\nNew revision guide.\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "source B")
    target = git(source, "rev-parse", "HEAD")
    unrelated = tmp_path / "unrelated-repository"
    unrelated.mkdir()
    git(unrelated, "init", "-q")
    process, report = cli(source, home, cwd=unrelated)
    assert process.returncode == 0, process.stderr + str(report)
    assert report["coverage"] == "partial"
    assert all(r["revision"] == target and r["after"]["state"] == "current" for r in report["results"])
    assert files(neighbor.parent) == before
    adapters = registry(home)
    for adapter in adapters:
        expected = adapter.build(request(source).revision, adapter.preflight(request(source)))
        for package in expected.packages:
            root = home.joinpath(*adapter.prefix, "skills", package.name)
            assert files(root) == {p: (m.content, m.mode) for p, m in package.members.items()}
    checked, verification = cli(source, home, "verify")
    assert checked.returncode == 0, verification


def test_wrong_real_adapter_revision_fails(source, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    adapters = registry(home, INCLUDED)
    original = adapters[2].build

    def wrong(revision, policy):
        built = original(revision, policy)
        assert revision.commit != "f" * 40
        return ExpectedBuild("f" * 40, built.packages, built.manifest_sha256)

    monkeypatch.setattr(adapters[2], "build", wrong)
    report = run_host(adapters, request(source))
    assert report.exit_code == 4 and report.results[2].exit_code == 4
    assert all(r.revision == report.revision for r in report.results)
    assert all(r.after.state == "current" for r in report.results[:2])
