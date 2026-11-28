"""Serial pytest completion evidence for the opt-in CI-shape check (#1917)."""

import json
import os
from pathlib import Path

import pytest


class Results:
    def __init__(self):
        # Keep this collector usable without importing its producer package.
        declared = json.loads(os.environ.get("CPP_CI_SHAPE_EXPECTED_SKIPS", "{}"))
        if not isinstance(declared, dict) or any(
                not isinstance(key, str) or not isinstance(value, str) for key, value in declared.items()):
            raise ValueError("expected skip declaration must map node IDs to reasons")
        self.expected_skips: dict[str, str] = declared
        self.selected: list[str] = []
        self.outcomes: dict[str, str] = {}
        self.skips: dict[str, str] = {}
        self.errors: list[str] = []
        self.exact_execution = os.environ.get("CPP_CI_SHAPE_EXACT_EXECUTION") == "1"
        self.calls: set[str] = set()

    def pytest_collection_modifyitems(self, items):
        # This plugin instance exists only for a declared shape run. Marking
        # before setup avoids constructing sources for excluded history cases.
        for item in items:
            reason = self.expected_skips.get(item.nodeid)
            if reason is not None:
                item.add_marker(pytest.mark.skip(reason=reason))

    def pytest_collection_finish(self, session):
        self.selected = [item.nodeid for item in session.items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.errors.append("collection failed")
        elif report.skipped:
            self.errors.append("collection skipped: " + str(report.nodeid))

    def pytest_runtest_logreport(self, report):
        if self.exact_execution and report.when == "call":
            if report.nodeid in self.calls:
                self.errors.append("duplicate call report: " + report.nodeid)
            self.calls.add(report.nodeid)
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
