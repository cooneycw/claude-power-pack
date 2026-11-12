"""What the registry SAYS about `--files` is what the matrix pins (issue #1691).

Two lines the registry prints - one from `register`, one from `list` - told a
role with an unusable repo that `--files` "is preserved" by a re-register. The
re-register matrix (`tests/test_flow_wave_reregister_matrix.py`) pins the real
rule: the file lane is kept when `--files` is omitted, EXCEPT that a change of
`--issue` or `--repo` between two non-empty values resets it unless the same
call names it.

This file ties the sentence to the table. The sentence is restated here as a
rule (`_sentence_predicts`) and run over every case of the matrix: it must
predict the `FILES` value each case expects. The old sentence, as a rule, must
get at least one case wrong - otherwise this check could not tell the two
sentences apart.

It reads the script's text and the matrix's table; it runs nothing.
"""

from __future__ import annotations

from pathlib import Path

from tests.test_flow_wave_reregister_matrix import BASE_STATE, CASES, Case, _lane

REGISTRY = Path(__file__).resolve().parents[1] / "scripts" / "flow-wave-registry.sh"

#: The statement both lines must make, word for word.
CLAUSE = (
    "a change of --issue or --repo between two non-empty values resets the file lane "
    "unless the same call names it"
)


def _flag(flags: tuple[str, ...], name: str) -> str | None:
    """The value given for NAME, or None when the flag is absent."""
    return flags[flags.index(name) + 1] if name in flags else None


def _recorded(case: Case, name: str) -> str:
    """What the registry holds for --issue or --repo just before the call under test.

    Both are rewritten by every registration, to empty when omitted, so it is
    whatever the LAST registration before the call passed.
    """
    last = case.setup[-1] if case.setup else _lane(case.start_issue, case.start_repo)
    return _flag(last, name) or ""


def _is_move(case: Case) -> bool:
    """A change of --issue or --repo between two non-empty values."""
    return any(
        (old := _recorded(case, name)) and (new := _flag(case.flags, name)) and old != new
        for name in ("--issue", "--repo")
    )


def _sentence_predicts(case: Case, *, moves_reset: bool) -> str:
    """The file lane after the call, as the sentence states it.

    `moves_reset=False` is the OLD sentence: "--files is preserved".
    """
    named = _flag(case.flags, "--files")
    if named is not None:
        return named or "-"
    if moves_reset and _is_move(case):
        return "-"
    return str(BASE_STATE["FILES"])


def _expected(case: Case) -> str:
    return str({**BASE_STATE, **case.changes}["FILES"])


def test_the_sentence_predicts_every_case_of_the_matrix() -> None:
    moves = [name for name, case in CASES.items() if _is_move(case)]
    kept = [name for name, case in CASES.items() if not _is_move(case)]
    # The table must hold both kinds, or agreeing with it proves nothing.
    assert len(moves) >= 4 and len(kept) >= 4, (moves, kept)
    wrong = {
        name: (_sentence_predicts(case, moves_reset=True), _expected(case))
        for name, case in CASES.items()
        if _sentence_predicts(case, moves_reset=True) != _expected(case)
    }
    assert not wrong, f"the sentence disagrees with the matrix (predicted, pinned): {wrong}"


def test_the_old_sentence_gets_the_moves_wrong() -> None:
    """The red case: "--files is preserved" mispredicts every move that omits --files."""
    wrong = sorted(
        name for name, case in CASES.items()
        if _sentence_predicts(case, moves_reset=False) != _expected(case)
    )
    assert "a different --issue" in wrong and "a different --repo, same issue" in wrong, wrong
    assert all(_is_move(CASES[name]) and "--files" not in CASES[name].flags for name in wrong), wrong


def test_both_printed_lines_make_exactly_that_statement() -> None:
    echoes = [
        line.strip() for line in REGISTRY.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("echo ")
    ]
    stating = [line for line in echoes if "resets the file lane" in line]
    assert len(stating) == 2, stating
    assert all(CLAUSE in line and "--files is kept when omitted" in line for line in stating), stating
    # One is register's (stderr), one is list's (stdout).
    assert sorted(line.endswith(">&2") for line in stating) == [False, True], stating
    stale = [line for line in echoes if "--files" in line and "preserved" in line]
    assert not stale, f"a printed line still calls --files preserved: {stale}"
