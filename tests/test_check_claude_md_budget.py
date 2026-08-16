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
