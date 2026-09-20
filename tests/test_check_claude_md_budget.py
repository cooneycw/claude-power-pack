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


def test_the_agents_budget_refuses_a_copy_of_the_core_directives_block(
    tmp_path: Path,
) -> None:
    """The budget is set by what it FORBIDS, so assert that, not the number.

    AGENTS.md's legitimate content is ~308 words and CLAUDE.md's Core Directives
    block is 389. A cap a duplicate fits under is decoration, so the real
    property is: content passes, content plus a copy of that block does not.
    Asserting `AGENTS_WORD_BUDGET == 450` would restate the constant; this
    asserts the reason it has that value, and still fails if someone raises it
    to 700 because the number "felt tight".
    """
    content_words, core_directives_words = 308, 389

    (tmp_path / "AGENTS.md").write_text("word " * content_words, encoding="utf-8")
    assert budget.check(tmp_path / "AGENTS.md", budget=budget.AGENTS_WORD_BUDGET)[0]

    (tmp_path / "AGENTS.md").write_text(
        "word " * (content_words + core_directives_words), encoding="utf-8"
    )
    passed, count = budget.check(tmp_path / "AGENTS.md", budget=budget.AGENTS_WORD_BUDGET)
    assert not passed, f"{count} words must not fit a budget that forbids the block"
