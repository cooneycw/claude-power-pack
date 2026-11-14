"""Static lifecycle parity, including its missing-coverage and blind controls.

This suite checks membership and policy freshness, not flags, ordering, live
model execution or the semantic truth of an approved equivalent. The real-tree
assertion deliberately fails until #1809 supplies the 15 required verb pairs.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "controls/driver-parity"


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


parity = module("driver_parity", ROOT / "scripts/check-driver-parity.py")
fixtures = module("driver_parity_fixtures", CONTROL / "run-case.py")


def tree(tmp_path: Path, mode: str = "baseline") -> Path:
    root = tmp_path / "owned"
    fixtures.materialize(root, mode)
    return root


def outcome(root: Path, gate: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(gate or ROOT / "scripts/check-driver-parity.py"), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


MANIFEST = json.loads((CONTROL / "control.json").read_text())


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda case: case["name"])
def test_committed_cases_distinguish_good_bad_and_the_blind_anchor(tmp_path: Path, case: dict) -> None:
    mode = json.loads((CONTROL / case["input"] / "case.json").read_text())["mode"]
    root = tree(tmp_path, mode)
    current = outcome(root)
    blind = outcome(root, CONTROL / MANIFEST["anchors"][0]["path"])
    if case["expect"] == "BAD":
        assert current.returncode == 1, current.stdout + current.stderr
        assert "DRIVER_PARITY: fail" in current.stdout
        assert blind.returncode == 0, blind.stdout + blind.stderr
    else:
        assert current.returncode == blind.returncode == 0, current.stdout + current.stderr


def test_uncovered_main_verbs_name_all_fifteen_pairs(tmp_path: Path) -> None:
    root = tree(tmp_path, "main-gap")
    result = outcome(root)
    assert result.returncode == 1
    assert result.stdout.count("DRIVER_PARITY_MISSING:") == 15
    for driver in parity.DRIVERS:
        for verb in ("approve", "compliance", "reconcile", "read-issue", "begin-run"):
            assert f"driver={driver} gate=flow-plan-record.py {verb}\n" in result.stdout


def test_one_driver_missing_an_invented_gate_is_named(tmp_path: Path) -> None:
    result = outcome(tree(tmp_path, "one-missing"))
    assert result.returncode == 1
    assert result.stdout.count("DRIVER_PARITY_MISSING:") == 1
    assert "driver=qwen gate=parity-invented-gate.sh" in result.stdout


def test_no_issue_link_is_not_an_exemption(tmp_path: Path) -> None:
    result = outcome(tree(tmp_path, "missing-issue"))
    assert result.returncode == 1 and "missing issue link" in result.stdout


@pytest.mark.parametrize("disposition", ["exempt", "equivalent"])
def test_approval_and_compliance_are_never_waived(tmp_path: Path, disposition: str) -> None:
    root = tree(tmp_path)
    policy = root / parity.POLICY
    data = json.loads(policy.read_text())
    entry = next(e for e in data["entries"] if e["gate"] == "flow-plan-record.py approve")
    entry["disposition"] = disposition
    policy.write_text(json.dumps(data))
    result = outcome(root)
    assert result.returncode == 1 and "never exemptable/equivalent" in result.stdout


@pytest.mark.parametrize(
    "text", ["", "## Instructions\n\n```bash\nscripts/only-one.sh\n```\n", "## Instructions\n```bash\nscripts/new.sh\n"]
)
def test_empty_short_or_unparseable_inventory_is_unknown(tmp_path: Path, text: str) -> None:
    root = tree(tmp_path)
    (root / parity.FLOW).write_text(text)
    result = outcome(root)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "DRIVER_PARITY: unknown" in result.stdout
    assert "DRIVER_PARITY: ok" not in result.stdout


def test_extractor_ignores_prose_examples_prohibited_commands_and_heredoc_data() -> None:
    source = """scripts/prose.sh is only a citation.
## Instructions
`scripts/prose.sh` is only a citation.
Examples:
```bash
scripts/example.sh run
```
Do not run:
```bash
scripts/forbidden.sh run
```
Run the actual check:
```bash
# scripts/comment.sh run
echo "scripts/output.sh run"
UNUSED=~/.claude/scripts/assignment-only.sh
CM_RECEIPT=~/.claude/scripts/counter-model-receipt.py
python3 "$CM_RECEIPT" write
cat <<'DATA'
scripts/heredoc-data.sh run
DATA
scripts/actual.sh run
```
Run `scripts/inline.sh`.
"""
    assert set(parity.inventory(source)) == {"actual.sh", "inline.sh", "counter-model-receipt.py"}


def test_new_helper_is_derived_and_run_needs_no_manual_inventory_entry(tmp_path: Path) -> None:
    root = tree(tmp_path, "invented-run")
    policy = json.loads((root / parity.POLICY).read_text())
    assert not any(e["gate"] == "parity-invented-gate.sh" for e in policy["entries"])
    assert "parity-invented-gate.sh" in parity.inventory((root / parity.FLOW).read_text())
    assert outcome(root).returncode == 0


@pytest.mark.parametrize("change", ["duplicate-key", "duplicate-pair", "unknown-field", "bad-type", "path-escape"])
def test_policy_refuses_ambiguous_or_invalid_decisions(tmp_path: Path, change: str) -> None:
    root = tree(tmp_path)
    path = root / parity.POLICY
    data = json.loads(path.read_text())
    if change == "duplicate-key":
        path.write_text(path.read_text().replace('"schema": 1', '"schema": 1, "schema": 1'))
    else:
        if change == "duplicate-pair":
            data["entries"].append(data["entries"][0])
        elif change == "unknown-field":
            data["entries"][0]["invented"] = True
        elif change == "bad-type":
            data["entries"][0]["disposition"] = []
        else:
            entry = next(e for e in data["entries"] if e["disposition"] == "equivalent")
            entry["citations"][0]["file"] = "../outside.md"
        path.write_text(json.dumps(data))
    result = outcome(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "DRIVER_PARITY: fail" in result.stdout


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    destination = tmp_path_factory.mktemp("driver-parity-generated")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/codex-skill-sync.py"), "--write", "--output-root", str(destination)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return destination


def test_real_generator_preserves_flow_membership_and_leaves_delegated_families_unpackaged(generated: Path) -> None:
    missing, count = parity.evaluate(ROOT, generated)
    assert count >= 23
    assert not any("driver=generated-flow-auto " in item for item in missing), missing
    for driver in parity.DRIVERS:
        assert not (generated / f"{driver}-auto").exists()


def test_repository_driver_parity(generated: Path) -> None:
    # Deliberately red on pre-#1809 source. No xfail, known-red success, or waiver
    # hides approval/compliance. This assertion turns green when #1809 lands.
    missing, _ = parity.evaluate(ROOT, generated)
    assert not missing, "\n".join(missing)


@pytest.mark.parametrize("shell", ["scripts/first.sh; scripts/second.sh", 'echo "example"; scripts/new.sh'])
def test_unsupported_shell_chains_are_unknown_instead_of_losing_later_calls(shell: str) -> None:
    with pytest.raises(parity.Unknown):
        parity.inventory("## Instructions\n```bash\n" + shell + "\n```\n")


def test_a_future_plan_record_verb_is_a_new_parity_item(tmp_path: Path) -> None:
    root = tree(tmp_path)
    gate = "flow-plan-record.py future-parity-verb"
    call = "~/.claude/scripts/" + gate + " 42"
    fixtures.append(root / parity.FLOW, call)
    fixtures.append(root / "codex/skills/flow-auto/SKILL.md", call)
    assert gate in parity.inventory((root / parity.FLOW).read_text())
    missing, count = parity.evaluate(root, root / "codex/skills")
    assert count == 24
    assert missing == [f"driver={driver} gate={gate}" for driver in parity.DRIVERS]
    for driver in parity.DRIVERS:
        fixtures.append(root / f".claude/commands/{driver}/auto.md", call)
    assert not parity.evaluate(root, root / "codex/skills")[0]
