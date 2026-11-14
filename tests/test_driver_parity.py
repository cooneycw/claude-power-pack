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
    elif case["expect"] == "UNKNOWN":
        assert current.returncode == 2, current.stdout + current.stderr
        assert "DRIVER_PARITY: unknown" in current.stdout
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
literal heredoc data
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
    fixtures.append_mirror(root, call)
    assert gate in parity.inventory((root / parity.FLOW).read_text())
    missing, count = parity.evaluate(root, root / "codex/skills")
    assert count == 24
    assert missing == [f"driver={driver} gate={gate}" for driver in parity.DRIVERS]
    for driver in parity.DRIVERS:
        fixtures.append(root / f".claude/commands/{driver}/auto.md", call)
    assert not parity.evaluate(root, root / "codex/skills")[0]


@pytest.mark.parametrize("change", ["entry-point", "installed-paths"])
def test_real_generated_procedure_cannot_lose_its_entry_point_or_bundled_bindings(
    generated: Path, tmp_path: Path, change: str
) -> None:
    import re
    import shutil

    owned = tmp_path / "generated"
    shutil.copytree(generated / "flow-auto", owned / "flow-auto")
    skill = owned / "flow-auto"
    if change == "entry-point":
        assert (skill / "reference.md").is_file()
        (skill / "SKILL.md").write_text("# Unrelated entry point\n")
    else:
        reference = skill / "reference.md"
        text, replacements = re.subn(
            r'"?\$\{CPP_SKILL_DIR:-/dev/null\}"?/scripts/', "~/.claude/scripts/", reference.read_text()
        )
        assert replacements > 0
        reference.write_text(text)
    with pytest.raises(parity.Invalid):
        parity.evaluate(ROOT, owned)


@pytest.mark.parametrize(
    "shell",
    [
        'if [ "$(scripts/new.sh check)" ]; then',
        "time scripts/new.sh check",
        "OUT=$(scripts/new.sh check)",
    ],
)
def test_other_unsupported_helper_positions_are_unknown(shell: str) -> None:
    with pytest.raises(parity.Unknown):
        parity.inventory("## Instructions\n```bash\n" + shell + "\n```\n")


@pytest.mark.parametrize(
    "shell",
    [
        "echo '$(scripts/literal.sh check)'",
        "printf '%s' '`scripts/literal.sh check`'",
        'echo "$(date)"',
    ],
)
def test_literal_output_and_known_nonhelper_substitution_are_not_calls(shell: str) -> None:
    assert not parity.inventory("## Instructions\n```bash\n" + shell + "\n```\n")


@pytest.mark.parametrize(
    "shell",
    [
        "echo <(scripts/new.sh check)",
        'echo "`scripts/new.sh check`"',
    ],
)
def test_unsupported_executed_output_expansions_are_unknown(shell: str) -> None:
    with pytest.raises(parity.Unknown):
        parity.inventory("## Instructions\n```bash\n" + shell + "\n```\n")


@pytest.mark.parametrize(
    "fallback,code",
    [
        ('[ -f "$REC" ] || { echo absent; REC=echo; }', 2),
        ('[ -f "$REC" ] || REC=$OTHER', 2),
    ],
)
def test_conditional_alias_alternatives_cannot_supply_stale_identity(tmp_path: Path, fallback: str, code: int) -> None:
    root = tree(tmp_path)
    driver = root / ".claude/commands/codex/auto.md"
    old = "~/.claude/scripts/flow-plan-record.py approve 42"
    assert old in driver.read_text()
    driver.write_text(
        driver.read_text().replace(
            old, "REC=~/.claude/scripts/flow-plan-record.py\n" + fallback + '\n"$REC" approve 42'
        )
    )
    result = outcome(root)
    assert result.returncode == code, result.stdout + result.stderr


@pytest.mark.parametrize(
    "probe",
    [
        "[ -x scripts/probe.sh ]",
        "[[ -f scripts/probe.sh ]]",
        "test -e scripts/probe.sh",
        "command -v scripts/probe.sh",
        "type -P scripts/probe.sh",
        "which scripts/probe.sh",
    ],
)
def test_closed_existence_probes_are_reported_and_never_run(probe: str) -> None:
    events = []
    text = "## Instructions\n```bash\n" + probe + "\n```\n"
    assert not parity.inventory(text, nonexecuting=events)
    assert events and all(event["helper"] == "probe.sh" for event in events)
    assert set(parity.inventory(text + "\n```bash\nscripts/probe.sh check\n```\n")) == {"probe.sh"}


def test_closed_same_basename_alias_fallback_is_run_only_at_invocation() -> None:
    text = '## Instructions\n```bash\nREC=~/.claude/scripts/probe.sh\n[ -f "$REC" ] || REC=/other/scripts/probe.sh\n'
    events = []
    assert not parity.inventory(text + "```\n", nonexecuting=events)
    assert any(event["kind"] == "same-helper fallback path resolution" for event in events)
    assert set(parity.inventory(text + '"$REC" check\n```\n')) == {"probe.sh"}


@pytest.mark.parametrize("target", ["echo", "/other/scripts/different.sh", "$OTHER"])
def test_closed_alias_fallback_rejects_different_or_nonpath_identity(target: str) -> None:
    text = (
        '## Instructions\n```bash\nREC=~/.claude/scripts/probe.sh\n[ -f "$REC" ] || REC='
        + target
        + '\n"$REC" check\n```\n'
    )
    with pytest.raises(parity.Unknown):
        parity.inventory(text)


@pytest.mark.parametrize("operator", ["-d", "-e", "-f", "-r", "-s", "-x", "-L"])
@pytest.mark.parametrize(
    "form", ["[ {op} scripts/probe.sh ]", "[[ {op} scripts/probe.sh ]]", "test {op} scripts/probe.sh"]
)
def test_closed_standard_file_test_operators_are_nonexecuting(operator: str, form: str) -> None:
    observations = []
    text = "## Instructions\n```bash\n" + form.format(op=operator) + "\n```\n"
    assert not parity.inventory(text, nonexecuting=observations)
    assert observations and observations[0]["helper"] == "probe.sh"


@pytest.mark.parametrize("operator", ["-n", "-z"])
def test_closed_quoted_alias_string_tests_are_nonexecuting(operator: str) -> None:
    text = "## Instructions\n```bash\nREC=~/.claude/scripts/probe.sh\n[ " + operator + ' "$REC" ]\n```\n'
    observations = []
    assert not parity.inventory(text, nonexecuting=observations)
    assert any(event["kind"] == "existence/location probe" for event in observations)


@pytest.mark.parametrize(
    "test",
    [
        "test -Q scripts/probe.sh",
        '[ -f "$(scripts/probe.sh)" ]',
        "REC=~/.claude/scripts/probe.sh\n[ -n $REC ]",
    ],
)
def test_closed_test_rules_reject_other_operators_substitutions_or_unquoted_aliases(test: str) -> None:
    with pytest.raises(parity.Unknown):
        parity.inventory("## Instructions\n```bash\n" + test + "\n```\n")


@pytest.mark.parametrize("join", ["&&", "||"])
def test_closed_chains_of_file_tests_do_not_count_as_calls(join: str) -> None:
    text = (
        "## Instructions\n```bash\nREC=~/.claude/scripts/probe.sh\nif [ -d docs ] "
        + join
        + ' [ -f "$REC" ]; then\n:\nfi\n```\n'
    )
    assert not parity.inventory(text)


@pytest.mark.parametrize("clear", ['REC=""', "REC="])
def test_closed_empty_alias_keeps_only_historical_same_helper_membership(clear: str) -> None:
    # Rule C describes document membership, not successful runtime execution.
    prefix = "## Instructions\n```bash\nREC=~/.claude/scripts/probe.sh\n"
    assert not parity.inventory(prefix + clear + "\n```\n")
    assert set(parity.inventory(prefix + clear + '\n"$REC" check\n```\n')) == {"probe.sh"}
    assert not parity.inventory("## Instructions\n```bash\n" + clear + '\n"$REC" check\n```\n')


def test_closed_missing_helper_note_and_clear_are_nonexecuting() -> None:
    text = """## Instructions
```bash
REC=~/.claude/scripts/probe.sh
[ -f "$REC" ] || { echo "NOTE: probe.sh absent"; REC=""; }
"$REC" check
```
"""
    observations = []
    assert set(parity.inventory(text, nonexecuting=observations)) == {"probe.sh"}
    assert any(event["kind"] == "literal missing-helper NOTE and empty alias clear" for event in observations)


def test_closed_quoted_note_is_prose_but_unquoted_helper_argument_is_unknown() -> None:
    text = '## Instructions\n```bash\necho "NOTE: probe.sh absent"\n```\n'
    assert not parity.inventory(text, helper_names={"probe.sh"})
    with pytest.raises(parity.Unknown):
        parity.inventory(text.replace('"NOTE: probe.sh absent"', "probe.sh"), helper_names={"probe.sh"})


@pytest.mark.parametrize("body", ["scripts/new.sh run", "$(scripts/new.sh run)"])
def test_helper_bearing_heredoc_is_unknown(body: str) -> None:
    with pytest.raises(parity.Unknown):
        parity.inventory("## Instructions\n```bash\ncat <<'DATA'\n" + body + "\nDATA\n```\n")


def test_comment_backslash_cannot_swallow_next_command() -> None:
    source = "## Instructions\n```bash\n# scripts/comment.sh \\\n scripts/actual.sh run\n```\n"
    assert set(parity.inventory(source)) == {"actual.sh"}


@pytest.mark.parametrize("prefix", ["${X:-/d}", "${X}", '"${X}"', '"$X"'])
def test_literal_parameter_path_segments_and_concatenation(prefix: str) -> None:
    source = "## Instructions\n```bash\n" + prefix + "/scripts/probe.sh check\n```\n"
    assert set(parity.inventory(source)) == {"probe.sh"}


@pytest.mark.parametrize("guard", ["-f", "-e", "-x"])
def test_same_helper_fallback_parameter_paths(guard: str) -> None:
    source = (
        "## Instructions\n```bash\nREC=/d/scripts/probe.sh\n[ "
        + guard
        + ' "$REC" ] || REC="${X:-/d}"/scripts/probe.sh\n"$REC" check\n```\n'
    )
    assert set(parity.inventory(source)) == {"probe.sh"}


@pytest.mark.parametrize("shell", ["'${CPP_SKILL_DIR}/scripts/probe.sh' check", "REC=/d/scripts/probe.sh\necho $REC"])
def test_literal_parameter_filenames_and_unquoted_alias_output_are_unknown(shell: str) -> None:
    with pytest.raises(parity.Unknown):
        parity.inventory("## Instructions\n```bash\n" + shell + "\n```\n")


@pytest.mark.parametrize("mode", ["fallback-substitution", "glob-probe"])
def test_pass3_dynamic_fallback_and_glob_probe_reproductions_are_unknown(tmp_path: Path, mode: str) -> None:
    result = outcome(tree(tmp_path, mode))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "DRIVER_PARITY: unknown" in result.stdout


@pytest.mark.parametrize("value", ["$(date)/scripts/probe.sh", "`date`/scripts/probe.sh", "/tmp/*/scripts/probe.sh"])
@pytest.mark.parametrize("assignment", ["REC={value}", '[ -f "$REC" ] || REC={value}'])
def test_original_alias_assignment_spelling_must_be_literal(value: str, assignment: str) -> None:
    source = (
        "## Instructions\n```bash\nREC=/d/scripts/probe.sh\n" + assignment.format(value=value) + '\n"$REC" check\n```\n'
    )
    with pytest.raises(parity.Unknown):
        parity.inventory(source)


@pytest.mark.parametrize(
    "probe",
    [
        "[ -f /tmp/*/scripts/probe.sh ]",
        "[[ -x /tmp/?/scripts/probe.sh ]]",
        "test -e /tmp/[ab]/scripts/probe.sh",
        "command -v /tmp/*/scripts/probe.sh",
    ],
)
def test_helper_probes_apply_the_same_literal_path_rule(probe: str) -> None:
    with pytest.raises(parity.Unknown):
        parity.inventory("## Instructions\n```bash\n" + probe + "\n```\n")
