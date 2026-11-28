"""Publishing a shared fixture source must join its real automatic maintenance."""
import json
import os
import shutil
import time

import pytest

from tests.test_host_update_adapters import source_template

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="real Git maintenance required")


def test_source_publication_joins_automatic_gc(tmp_path, monkeypatch):
    trace = tmp_path / "git-trace.jsonl"
    # Force the existing source commit above the auto-GC threshold; do not
    # emulate Git or replace the fixture's commit/clone commands.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "gc.auto")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "1")
    monkeypatch.setenv("GIT_TRACE2_EVENT", str(trace))
    assert os.environ["GIT_CONFIG_VALUE_0"] == "1" and not trace.exists()

    class Factory:
        def mktemp(self, name):
            path = tmp_path / name
            path.mkdir()
            return path

    source = source_template.__wrapped__(Factory())
    # An old-code red still owns the detached GC. Wait for cleanup before
    # reading its complete trace or allowing pytest to remove its repository.
    # This deadline is cleanup only; the verdict compares process event order.
    deadline = time.monotonic() + 30
    while (source / ".git/gc.pid").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not (source / ".git/gc.pid").exists(), "owned maintenance did not finish"
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    repacks = [row for row in events if row.get("event") == "start"
               and row.get("argv", [None])[1:2] == ["repack"]]
    assert repacks, "negative input did not trigger actual automatic repacking"
    for repack in repacks:
        gc_sid = repack["sid"].rsplit("/", 1)[0]
        assert any(row.get("event") == "start" and row.get("sid") == gc_sid
                   and row.get("argv", [None])[1:2] == ["gc"] for row in events)
        gc_exits = [i for i, row in enumerate(events)
                    if row.get("event") == "exit" and row.get("sid") == gc_sid]
        repack_exits = [i for i, row in enumerate(events)
                        if row.get("event") == "exit" and row.get("sid") == repack["sid"]]
        assert gc_exits and repack_exits, "maintenance completion was not observed"
        assert min(gc_exits) > max(repack_exits), (
            "source publication detached automatic GC before its repack finished")
