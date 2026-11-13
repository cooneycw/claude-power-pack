"""Printed re-registration advice agrees with the approved 196-row table."""
from pathlib import Path

from tests.test_flow_wave_reregister_cross_product import CASES

REGISTRY = Path(__file__).resolve().parents[1] / "scripts" / "flow-wave-registry.sh"
CLAUSE = "omitted --issue and --repo are kept; moving work refuses unconsented lane or observation loss"


def test_both_printed_lines_state_the_chosen_rule():
    echoes = [line.strip() for line in REGISTRY.read_text().splitlines()
              if line.lstrip().startswith("echo ")]
    statements = [line for line in echoes if CLAUSE in line]
    assert len(statements) == 2
    assert sorted(line.endswith(">&2") for line in statements) == [False, True]
    assert not any("two non-empty values resets" in line for line in echoes)


def test_the_old_permissive_sentence_mispredicts_the_99_refusals():
    refused = [c for c in CASES if c["chosen"]["exit"] == 1]
    assert len(refused) == 99
    assert all(c["exit"] == 0 for c in refused)
    assert any(c["chosen"]["exit"] == 0 for c in CASES)
