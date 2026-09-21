from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check-claude-md-budget.py"
SPEC = importlib.util.spec_from_file_location("check_claude_md_budget", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
budget = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(budget)


def test_budget_accepts_exact_limit(tmp_path: Path) -> None:
    path = tmp_path / "CLAUDE.md"
    path.write_text("word " * budget.WORD_BUDGET, encoding="utf-8")

    assert budget.check(path) == (True, budget.WORD_BUDGET)


def test_budget_rejects_one_word_over_limit(tmp_path: Path) -> None:
    path = tmp_path / "CLAUDE.md"
    path.write_text("word " * (budget.WORD_BUDGET + 1), encoding="utf-8")
    assert budget.word_count(path) == budget.WORD_BUDGET + 1, "fixture must exceed the budget"

    assert budget.check(path) == (False, budget.WORD_BUDGET + 1)


def test_cli_fails_when_claude_md_is_missing(tmp_path: Path) -> None:
    assert not (tmp_path / "CLAUDE.md").exists(), "fixture must omit CLAUDE.md"

    assert budget.main(["--root", str(tmp_path)]) == 1


# --- the #1071 parameterisation: one instrument, two documents -----------------


def test_the_default_invocation_is_unchanged_by_the_parameterisation(
    tmp_path: Path, capsys
) -> None:
    """The pre-#1071 contract, pinned so generalising cannot quietly move it.

    ADR 0008 row 28 records this gate's verdict as `ok - N/2000 words`, and the
    report prefix is part of what a reader greps for. Deriving the label from
    `path.stem` instead of the filename renames it to `claude-budget`, which is
    the regression this asserts against - it looks like a cosmetic difference and
    is a changed published verdict.
    """
    (tmp_path / "CLAUDE.md").write_text("word " * 10, encoding="utf-8")

    assert budget.main(["--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "claude-md-budget: ok - 10/2000 words"


def test_a_positional_document_and_budget_are_honoured(tmp_path: Path, capsys) -> None:
    (tmp_path / "AGENTS.md").write_text("word " * 300, encoding="utf-8")

    assert budget.main(["AGENTS.md", "--budget", "450", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "agents-md-budget: ok - 300/450 words"


def test_the_smaller_budget_actually_binds(tmp_path: Path, capsys) -> None:
    """451 words passes CLAUDE.md's 2000 and must fail AGENTS.md's 450.

    Without this, a parameter that was accepted and then ignored would look
    identical to one that works: every document is under 2000.
    """
    (tmp_path / "AGENTS.md").write_text("word " * 451, encoding="utf-8")

    assert budget.main(["AGENTS.md", "--budget", "450", "--root", str(tmp_path)]) == 1
    assert "451 words; budget is 450" in capsys.readouterr().err


def test_the_agents_budget_refuses_APPENDING_the_core_directives_block(
    tmp_path: Path,
) -> None:
    """What the cap actually does, stated as narrowly as it is true (#1071).

    Its original form asserted the budget "forbids a copy of the Core Directives
    block". The post-merge counter-model review showed that is false in general -
    see the companion test below - so this one is renamed to the property that
    holds: APPENDING the block to the current content does not fit.

    Asserting `AGENTS_WORD_BUDGET == 450` would restate the constant; this asserts
    the reason it has that value.
    """
    content_words, core_directives_words = 308, 389

    (tmp_path / "AGENTS.md").write_text("word " * content_words, encoding="utf-8")
    assert budget.check(tmp_path / "AGENTS.md", budget=budget.AGENTS_WORD_BUDGET)[0]

    (tmp_path / "AGENTS.md").write_text(
        "word " * (content_words + core_directives_words), encoding="utf-8"
    )
    passed, count = budget.check(tmp_path / "AGENTS.md", budget=budget.AGENTS_WORD_BUDGET)
    assert not passed, f"{count} words must not fit a budget that forbids appending the block"


def test_the_agents_budget_does_NOT_forbid_a_replacement_copy(tmp_path: Path) -> None:
    """The limit, pinned so the overclaim cannot come back (#1071).

    A cap is a size limit. Delete AGENTS.md's Codex-specific content, paste the
    Core Directives block in its place, and the result is ~399 words - under the
    cap, and exactly the second copy the thin-pointer design exists to prevent.

    This asserts the instrument's BLIND SPOT on purpose: an under-budget
    replacement is ACCEPTED, so the cap demonstrably does not forbid one.

    WHAT IT DOES NOT DO, corrected at the re-review: an earlier version of this
    docstring said restoring the "forbids a copy" claim would fail this test. It
    would not. The test reads no prose - it measures word counts - so restoring
    that claim anywhere leaves it green. Asserting otherwise was another
    unsupported assurance, introduced in the commit correcting unsupported
    assurances. The prose is kept honest by review, not by this test.
    """
    pointer_plus_block = 6 + 389

    (tmp_path / "AGENTS.md").write_text("word " * pointer_plus_block, encoding="utf-8")
    passed, count = budget.check(tmp_path / "AGENTS.md", budget=budget.AGENTS_WORD_BUDGET)

    assert passed, "fixture must be under the cap for this test to say anything"
    assert count < budget.AGENTS_WORD_BUDGET
    # Not a defect to fix here: a size limit cannot distinguish 308 words of
    # Codex-specific content from 308 words of restated directives.


def test_production_and_the_tests_read_the_SAME_budget(tmp_path: Path) -> None:
    """The budget must be observable where it is actually enforced (#1071).

    The Makefile and .woodpecker.yml passed `--budget 450` as a literal, so the
    constant these tests assert against was read by nothing in production:
    raising both literals to 700 would have admitted a 697-word duplicate while
    every test stayed green. The test that existed to survive someone raising the
    budget could not see the budget anyone could raise.

    Both call sites now pass the document alone, so this asserts the resolution
    they actually depend on.
    """
    (tmp_path / "AGENTS.md").write_text("word " * 451, encoding="utf-8")

    # No --budget: exactly what the Makefile and the CI step now invoke.
    assert budget.main(["AGENTS.md", "--root", str(tmp_path)]) == 1
    assert budget.DOCUMENT_BUDGETS["AGENTS.md"] == budget.AGENTS_WORD_BUDGET
    assert budget.DOCUMENT_BUDGETS["CLAUDE.md"] == budget.WORD_BUDGET


def _production_invocations(text: str, comment_prefix: str) -> list[str]:
    """Executable invocations of the budget checker, with continuations joined.

    Line-at-a-time was the first shape and it was wrong three ways, all found by
    the re-review: `--budget 700` on a Makefile or YAML CONTINUATION escaped it
    entirely; a COMMENT merely mentioning the script and the flag failed it; and
    with no invocations at all the loop body never ran, so the test passed over
    an empty population - the success-claims-more-than-its-input defect this very
    PR exists to correct, committed in the test correcting it.
    """
    joined: list[str] = []
    pending = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith(comment_prefix):
            continue  # documentation is not an invocation
        line = pending + stripped
        if line.endswith("\\"):
            pending = line[:-1] + " "
            continue
        pending = ""
        if "check-claude-md-budget.py" in line:
            joined.append(line)
    if pending and "check-claude-md-budget.py" in pending:
        joined.append(pending)
    return joined


def test_no_production_call_site_carries_a_literal_budget() -> None:
    """The single source is only single while nothing re-introduces a literal.

    Asserts the population FIRST: an empty result is "I found no callers", which
    is not the same fact as "no caller carries a literal" and must not report as
    one.
    """
    root = Path(__file__).parents[1]
    expected = {"Makefile": ("#", 2), ".woodpecker.yml": ("#", 2)}

    for rel, (comment_prefix, minimum) in expected.items():
        invocations = _production_invocations(
            (root / rel).read_text(encoding="utf-8"), comment_prefix
        )
        assert len(invocations) >= minimum, (
            f"{rel} has {len(invocations)} budget-checker invocation(s), expected at least "
            f"{minimum}. An empty or shrunken population makes this test vacuous rather "
            "than passing - the callers it exists to check are not there."
        )
        for line in invocations:
            assert "--budget" not in line, (
                f"{rel} passes a literal budget: {line.strip()!r}. "
                "The budget belongs in DOCUMENT_BUDGETS, where the tests can see it."
            )


def test_the_caller_guard_ignores_documentation_and_sees_continuations(tmp_path: Path) -> None:
    """The guard's own two failure modes, pinned (#1071 re-review).

    A comment mentioning the flag is not an override; a continuation carrying it
    is. Both were wrong in the first version and neither is observable from the
    real repository, which contains neither.
    """
    comment_only = (
        "# scripts/check-claude-md-budget.py supports --budget for custom files\n"
        "\t@python3 scripts/check-claude-md-budget.py AGENTS.md\n"
    )
    assert _production_invocations(comment_only, "#") == [
        "@python3 scripts/check-claude-md-budget.py AGENTS.md"
    ], "a comment must not register as an invocation"

    continued = "\t@python3 scripts/check-claude-md-budget.py AGENTS.md \\\n\t\t--budget 700\n"
    found = _production_invocations(continued, "#")
    assert len(found) == 1 and "--budget 700" in found[0], (
        "a continuation must be joined into the command it belongs to, or an "
        "override simply moves to the next line"
    )
