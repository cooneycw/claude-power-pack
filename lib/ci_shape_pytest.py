"""Serial pytest completion evidence for the opt-in CI-shape check (#1917)."""

import json
import os
from pathlib import Path

import pytest


class Results:
    def __init__(self):
        self.selected: list[str] = []
        self.outcomes: dict[str, str] = {}
        self.skips: dict[str, str] = {}
        self.errors: list[str] = []

    def pytest_collection_finish(self, session):
        self.selected = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append("collection failed")
        elif report.skipped:
            self.errors.append("collection skipped: " + str(report.nodeid))

    def pytest_runtest_logreport(self, report):
        if report.failed:
            self.outcomes[report.nodeid] = "failed"
            print(f"\nCI_SHAPE_TEST_FAILED: {report.nodeid} ({report.when})", flush=True)
        elif report.skipped:
            self.outcomes.setdefault(report.nodeid, "skipped")
            self.skips[report.nodeid] = str(report.longrepr)[-1000:]
        elif report.when == "call":
            self.outcomes.setdefault(report.nodeid, "passed")

    def pytest_internalerror(self, excrepr, excinfo):
        self.errors.append("INTERNALERROR")

    def pytest_keyboard_interrupt(self, excinfo):
        self.errors.append("interrupted")

    def pytest_sessionfinish(self, session, exitstatus):
        path = Path(os.environ["CPP_CI_SHAPE_RESULTS"])
        payload = {"selected": self.selected, "outcomes": self.outcomes,
                   "skips": self.skips, "errors": self.errors, "exit": int(exitstatus)}
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n")
        temporary.replace(path)


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    if os.environ.get("CPP_CI_SHAPE_RESULTS"):
        config.pluginmanager.register(Results(), "cpp-ci-shape-results")
