"""The pipeline trigger: pull requests always, pushes only to main (issue #1308).

`.woodpecker.yml` used `when: event: [push, pull_request]` with no branch filter,
so every push to a PR branch ran the whole pipeline twice on one commit. Only the
pull-request context is required by branch protection, so the push twin gated
nothing while doubling load on a shared Woodpecker.

The check has three directions, and each is a way the trigger can be wrong:

  PUSH ON A NON-MAIN BRANCH   the doubling this issue removes (the pre-fix file).
  PUSH ON MAIN DROPPED        the post-merge verification silently disappears.
  PULL_REQUEST DROPPED        the one REQUIRED context never reports, so a PR
  OR NARROWED                 waits forever or merges on nothing. A target-branch
                              filter on the PR entry is a partial drop.

A `when:` shape the classifier does not understand - an unknown key, a filter it
cannot evaluate - is itself a violation. "I could not read this trigger" is not
"this trigger is fine".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

#: The keys a trigger entry may carry for this classifier to judge it. Anything
#: else (`path`, `cron`, `evaluate`, `status`, ...) changes which events run in a
#: way this check does not model, so it is reported rather than ignored.
KNOWN_KEYS = {"event", "branch"}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def trigger_violations(when: Any) -> list[str]:
    """Every way `when` departs from "pull_request always, push only on main"."""
    if when is None:
        return ["no `when:` - Woodpecker's default runs on every push to every branch"]
    entries = _as_list(when)
    violations: list[str] = []
    pr_runs = False
    push_main = False
    for n, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            violations.append(f"cannot classify entry {n}: not a mapping")
            continue
        unknown = sorted(set(entry) - KNOWN_KEYS)
        if unknown:
            violations.append(f"cannot classify entry {n}: unmodelled key(s) {unknown}")
            continue
        events = _as_list(entry.get("event"))
        if not events or not all(isinstance(e, str) for e in events):
            violations.append(f"cannot classify entry {n}: `event` is missing or not a string")
            continue
        branches = entry.get("branch")
        branch_list = None if branches is None else _as_list(branches)
        if "push" in events:
            # An unfiltered push, or one listing main among others, DOES run on
            # main - so main is covered - and ALSO runs elsewhere, which is the
            # violation. Reporting "main dropped" for it would be false.
            if branch_list is None or "main" in branch_list:
                push_main = True
            if branch_list is None or any(b != "main" for b in branch_list):
                violations.append(
                    f"entry {n}: push runs on branches other than main ({branch_list or 'any'})"
                )
        # UNFILTERED only (counter-model review): a branch filter on a PR entry
        # restricts the TARGET branch, so some pull requests would run nothing.
        if "pull_request" in events and branch_list is None:
            pr_runs = True
    if not pr_runs:
        violations.append(
            "no unfiltered pull_request entry - some or all pull requests never run the "
            "pipeline, so the required ci/woodpecker/pr context may never report"
        )
    if not push_main:
        violations.append("push on main dropped - no post-merge verification")
    return violations


def test_the_real_trigger_has_no_violations() -> None:
    pipeline = yaml.safe_load((ROOT / ".woodpecker.yml").read_text(encoding="utf-8"))
    assert "when" in pipeline, "the top-level trigger must be declared, not defaulted"
    assert trigger_violations(pipeline["when"]) == []


PRE_1308 = [{"event": ["push", "pull_request"]}]


@pytest.mark.parametrize(
    "when, expected",
    [
        # (a) the trigger as it stood at 7d1ad79 - the doubling
        (PRE_1308, "push runs on branches other than main"),
        # (b) main's push verification removed
        ([{"event": "pull_request"}], "push on main dropped"),
        # (c) the required context's pipeline removed
        ([{"event": "push", "branch": "main"}], "no unfiltered pull_request entry"),
        # (c') ... or narrowed to one target branch (counter-model review)
        (
            [{"event": "pull_request", "branch": "main"}, {"event": "push", "branch": "main"}],
            "no unfiltered pull_request entry",
        ),
        # a push filter wider than main is still the doubling
        (
            [{"event": "pull_request"}, {"event": "push", "branch": ["main", "release/*"]}],
            "push runs on branches other than main",
        ),
        # shapes this check cannot evaluate are violations, never clean
        (None, "no `when:`"),
        (
            [{"event": "pull_request"}, {"event": "push", "branch": "main", "path": "lib/**"}],
            "cannot classify entry 2",
        ),
        ([{"event": "pull_request"}, "push"], "cannot classify entry 2"),
    ],
)
def test_each_way_the_trigger_can_be_wrong_is_reported(when: Any, expected: str) -> None:
    violations = trigger_violations(when)
    assert any(expected in v for v in violations), violations


def test_the_pre_1308_trigger_reports_the_doubling_and_nothing_false() -> None:
    """The old trigger DID run on main; only its branch-push twin was wrong."""
    assert trigger_violations(PRE_1308) == ["entry 1: push runs on branches other than main (any)"]


def test_the_intended_shape_passes_in_either_spelling() -> None:
    assert trigger_violations([{"event": "pull_request"}, {"event": "push", "branch": "main"}]) == []
    assert trigger_violations([{"event": ["pull_request"]}, {"event": ["push"], "branch": ["main"]}]) == []
