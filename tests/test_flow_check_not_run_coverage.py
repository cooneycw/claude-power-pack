"""Pin: /flow:check's report instructions cover NOT_RUN (issue #1388).

The `check` plan's aggregate is `lint -> test -> typecheck` (issue #1152,
`lib/cicd/manifest.py:528`). When an earlier step fails, `make` halts there
and `lib/cicd/state.py`'s `StepStatus.NOT_RUN` marks every later step's
`step_details` entry `status: not-run` with a `not_run_reason` naming the
step that failed - it never ran, so it is neither PASS, FAIL, WARN nor SKIP.

Before this fix, `.claude/commands/flow/check.md` named every OTHER state
the runner can emit (PASS/FAIL/WARN/SKIP) in both its exit-handling rules and
its report table, but never NOT_RUN - an agent reading the doc had no
instruction for a step the runner itself distinguishes, and the natural
failures are reporting it as PASS or leaving it out of the table entirely,
which turns a red run's unexecuted checks into apparent greens (the issue's
own "what it matters" paragraph).

This test does not run the aggregate; it is a content pin on the skill
document itself, extended to the generated codex mirror so a regeneration
that drops the new text fails too.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCE = ROOT / ".claude/commands/flow/check.md"
MIRROR = ROOT / "codex/skills/flow-check/reference.md"


def _assert_covers_not_run(text: str, where: Path) -> None:
    assert "NOT_RUN" in text, (
        f"{where} never mentions NOT_RUN - the runner's own not-run state "
        f"(lib/cicd/state.py StepStatus.NOT_RUN) has no report-table row or "
        f"exit-handling rule here, so an agent following this doc has no "
        f"instruction for a step that never ran because an earlier one failed"
    )
    assert "not-run" in text or "not_run_reason" in text, (
        f"{where} names NOT_RUN as a row state but never ties it to the "
        f"runner's actual signal (`step_details` status `not-run` / "
        f"`not_run_reason`) - the rule would be unfollowable from the "
        f"runner's real output"
    )


def test_source_command_covers_not_run() -> None:
    _assert_covers_not_run(SOURCE.read_text(encoding="utf-8"), SOURCE)


def test_codex_mirror_covers_not_run() -> None:
    _assert_covers_not_run(MIRROR.read_text(encoding="utf-8"), MIRROR)
