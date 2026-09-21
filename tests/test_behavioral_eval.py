"""Tests for the behavioural-eval consuming gate (issue #1084 half A).

Three groups, and the first is the acceptance criterion rather than the code.

THE TRIGGER. #1084 requires the check to be "registered where a change to
CLAUDE.md or to a skill causes it to run", and warns that "a check with no path
from a change to a verdict is the failure #1028 consolidates". That is a claim
about a PATH, which is exactly the kind of thing asserted and never checked.

The path has four links, and `scripts/check-ci-coverage.py` already enforces the
first three mechanically - it reads the verify prerequisites, the step names in
`.woodpecker.yml` and each directive's `ci:` clause, refusing UNDECLARED,
MALFORMED, ABSENT-STEP and ORPHANED-CLAUSE. These cases therefore assert the
END-TO-END property those three refusals do not state as one claim, and leave the
per-link enforcement where it already lives. A second parser here would drift from
that one, which is the reason check-ci-coverage.py:127 gives for not having one.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-behavioral-eval.py"
CONTROLS = ROOT / "controls" / "behavioral-eval"


def _load():
    spec = importlib.util.spec_from_file_location("check_behavioral_eval", GATE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


# --------------------------------------------------------------- the trigger

def _pipeline() -> dict:
    return yaml.safe_load((ROOT / ".woodpecker.yml").read_text())


def _makefile_recipe(target: str) -> list[str]:
    """The recipe lines of one target - what it actually RUNS, not that it exists."""
    body = (ROOT / "Makefile").read_text().split(f"\n{target}:", 1)[1]
    out = []
    for line in body.splitlines()[1:]:
        if not line.startswith("\t"):
            break
        out.append(line.lstrip("\t").lstrip("@-"))
    return out


def test_the_gate_is_reachable_from_a_change_to_CLAUDE_md() -> None:
    """The acceptance criterion, end to end.

    #1084 requires the check to be "registered where a change to CLAUDE.md or to a
    skill causes it to run", and warns that "a check with no path from a change to
    a verdict is the failure #1028 consolidates".

    This asserted the NAMES in each link and stopped there, which counter-model
    review showed to be insufficient in both directions at once: replacing both
    invocations with `true` left every assertion green (a path to a step that runs
    nothing is not a path to a verdict), while a `path:` filter on an unrelated
    neighbouring step turned it red (a non-zero that cannot tell our thing changed
    from a neighbour's). Both are the detector contract's own two questions, asked
    of the detector. So the links are now checked for EXECUTION and scoped to this
    gate's own dependency chain.
    """
    makefile = (ROOT / "Makefile").read_text()
    pipeline = _pipeline()

    verify_block = makefile.split("\nverify:", 1)[1].split("\n\n", 1)[0]
    assert "behavioral-eval-check" in verify_block, "link 1: not a verify prerequisite"

    directive = [
        ln for ln in makefile.splitlines()
        if ln.startswith("## verify-coverage:") and "behavioral-eval-check" in ln
    ]
    assert len(directive) == 1, f"link 2: expected one directive, found {len(directive)}"
    assert "ci: runs behavioral-eval-check" in directive[0], (
        "link 2: the clause does not declare a CI step. `ci: excluded` here would "
        "make the acceptance LOOK met while the gate ran only on a developer's box"
    )

    steps = pipeline.get("steps", {})
    assert "behavioral-eval-check" in steps, "link 3: no pipeline step"
    step = steps["behavioral-eval-check"]

    # link 3b: the two sites must RUN the consumer. A named target and a named step
    # whose bodies are `true` satisfy every name-based assertion above.
    recipe = _makefile_recipe("behavioral-eval-check")
    assert any(GATE.name in line for line in recipe), (
        f"link 3b: the Makefile target does not invoke {GATE.name}; it runs {recipe}"
    )
    # str() deliberately: YAML parses a bare `- true` as the BOOLEAN True, and
    # `"x" in True` raises TypeError. The test still failed, but by crashing
    # rather than by stating what was wrong - a red for the right reason told
    # badly is a red nobody can act on.
    commands = step.get("commands") or []
    assert any(GATE.name in str(c) for c in commands), (
        f"link 3b: the CI step does not invoke {GATE.name}; it runs {commands}"
    )

    # link 4: the pipeline fires on ordinary pushes and PRs, and nothing on THIS
    # gate's own dependency chain narrows that. A neighbour's filter is none of
    # this test's business - it cannot make this gate unreachable.
    top = pipeline.get("when")
    assert top == [{"event": ["push", "pull_request"]}], (
        f"link 4: the pipeline-level trigger is no longer the unrestricted "
        f"push/pull_request pair; it is {top!r}. A change to CLAUDE.md or a skill "
        f"may no longer reach this gate"
    )

    chain, frontier = set(), ["behavioral-eval-check"]
    while frontier:
        name = frontier.pop()
        if name in chain:
            continue
        chain.add(name)
        dep = steps.get(name, {}).get("depends_on") or []
        frontier.extend([dep] if isinstance(dep, str) else dep)

    for name in sorted(chain):
        assert name in steps, f"link 4: {name!r} is depended on but is not a step"
        cond = steps[name].get("when")
        assert cond is None, (
            f"link 4: step {name!r} is on this gate's dependency chain and carries "
            f"its own `when: {cond!r}`. A condition anywhere on the chain can stop "
            f"this gate running on a change that should reach it"
        )


# --------------------------------------------------------------- the exit-code rule

def test_exactly_one_verdict_maps_to_exit_zero() -> None:
    """`gate-lib.sh`'s rule, restated because this gate inherits no enforcement.

    gate-lib enforces "exactly one verdict maps to exit 0" at runtime for SHELL
    gates. This one is Python. Imitating a library's discipline without its
    mechanism is how the discipline quietly stops applying - and anyone who
    recognises these exit codes will assume gate-lib is covering it.
    """
    zeros = [name for name, code in mod.VERDICTS.items() if code == 0]
    assert zeros == ["pass"], (
        f"exactly one verdict may map to exit 0; these do: {zeros}. An unknowable "
        f"answer would then be rendered as a clean one (#1014, #800)"
    )
    assert len(set(mod.VERDICTS.values())) == len(mod.VERDICTS), (
        "two verdicts share an exit code, so a caller cannot tell them apart"
    )


def test_the_advisory_posture_names_what_would_end_it() -> None:
    """ADR 0009: a two-sided change names what would move it back, and PRE-COMMITS
    the trigger.

    This gate is advisory (`|| true`) because nothing produces its input yet. That
    is the right call now and the wrong one the moment half B lands, so the flip
    condition is written at the site. It was written as a COMMENT, and a comment
    cannot fail - someone can make this blocking, or delete the condition, and
    nothing would notice. This is the assertion that notices.

    It deliberately does not force either posture. It requires only that whichever
    posture is in force, the site still says what would change it.
    """
    makefile = (ROOT / "Makefile").read_text()
    block = makefile.split("\nbehavioral-eval-check:", 1)
    assert len(block) == 2, "the target vanished"
    recipe = block[1].split("\n\n", 1)[0]
    preamble = block[0].rsplit("\n\n", 1)[-1]

    advisory = "|| true" in recipe
    if advisory:
        assert "docs/measurements/behavioral-eval/" in preamble, (
            "the gate is advisory and the site no longer names the condition that "
            "would make it blocking - ADR 0009's pre-commitment is gone, and an "
            "advisory gate with no stated end is one that stays advisory forever"
        )
        assert "half B" in preamble, (
            "the flip condition does not name the work that would satisfy it"
        )
    else:
        # The flip condition, checked against the tree rather than against prose.
        # This is what makes the pre-commitment binding in the direction that
        # matters: the posture may only change when its stated trigger is TRUE.
        produced = sorted((ROOT / mod.DEFAULT_DIR).glob("*.json")) \
            if (ROOT / mod.DEFAULT_DIR).is_dir() else []
        assert produced, (
            f"the gate became blocking while {mod.DEFAULT_DIR}/ holds no artifact. "
            f"Its own pre-committed trigger is 'at least one artifact recorded by a "
            f"real behavioural case', and that is still false - so every build now "
            f"reds for exactly the reason the advisory posture existed to avoid"
        )


# --------------------------------------------------------------- the four verdicts

@pytest.mark.parametrize(
    ("case", "verdict"),
    [
        ("bad-records-failure", "failure"),
        ("bad-absent", "absent"),
        ("bad-version-newer", "unreadable"),
        ("good-records-pass", "pass"),
    ],
)
def test_each_committed_case_produces_its_verdict(case: str, verdict: str) -> None:
    got, _ = mod.evaluate(CONTROLS / "cases" / case)
    assert got == verdict


def test_a_recorded_failure_is_not_rendered_as_a_pass(tmp_path: Path) -> None:
    """The record is INTERNALLY CONSISTENT - FAIL, and its criteria derive FAIL.

    It was written here as `"criteria": []`, which the derivation correctly refused
    as forged (an empty population derives INCONCLUSIVE, never FAIL). Left that way
    this case would have asserted the forgery path while claiming to test the
    failure path - a test whose name and subject had quietly come apart.
    """
    (tmp_path / "r.json").write_text(json.dumps({
        "version": 1, "kind": "verified-result", "status": "FAIL",
        "criteria": [{"id": "c1", "mandatory": True, "outcome": "VIOLATED"}],
    }))
    verdict, _ = mod.evaluate(tmp_path)
    assert verdict == "failure"
    assert mod.VERDICTS[verdict] != 0


def test_an_absent_artifact_is_not_rendered_as_a_pass(tmp_path: Path) -> None:
    verdict, detail = mod.evaluate(tmp_path)
    assert verdict == "absent"
    assert mod.VERDICTS[verdict] != 0, "nothing to look at was rendered as clean"
    assert "half B" in detail and "skillc #5" in detail, (
        f"the absent line does not name its SPECIFIC blocker, so a reader cannot "
        f"check whether it still stands: {detail!r}"
    )


def test_a_newer_envelope_is_refused_rather_than_read_on_a_guess(tmp_path: Path) -> None:
    """Honouring skillc's contract rather than reinventing it."""
    (tmp_path / "r.json").write_text(json.dumps(
        {"version": mod.SUPPORTED_VERSION + 1, "kind": "verified-result", "status": "PASS"}
    ))
    verdict, detail = mod.evaluate(tmp_path)
    assert verdict == "unreadable"
    assert "guess" in detail


# --------------------------------------------------------------- honesty of the green

def test_every_verdict_names_the_population_including_the_green() -> None:
    """The green is the run nobody reads carefully, and it sits beside gates whose
    greens carry behavioural meaning."""
    for case in ("good-records-pass", "bad-records-failure", "bad-absent"):
        proc = subprocess.run(
            ["python3", str(GATE), "--dir", str(CONTROLS / "cases" / case)],
            capture_output=True, text=True,
        )
        assert mod.POPULATION_NOTE in proc.stdout, (
            f"{case} did not name its population, so its verdict is quotable as "
            f"evidence about a behavioural case"
        )
        assert "does not run a behavioural case" in proc.stdout


def test_the_control_registers_an_anchor_that_misses_every_bad_case() -> None:
    """Pins what the harness verified, so a later edit to control.json cannot
    quietly drop the anchor and leave the control UNPROVEN."""
    control = json.loads((CONTROLS / "control.json").read_text())
    anchors = control.get("anchors", [])
    assert len(anchors) == 1, "the control declares no anchor; it would be UNPROVEN"
    anchor = CONTROLS / anchors[0]["path"]
    assert anchor.is_file()
    bad = [c["input"] for c in control["cases"] if c["expect"] == "BAD"]
    assert bad, "no BAD case to be blind to"
    for rel in bad:
        proc = subprocess.run(
            ["python3", str(anchor), "--dir", str(CONTROLS / rel)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, (
            f"the anchor CAUGHT {rel}; it is not blind, so this control would not "
            f"notice the gate regressing to it"
        )

# --------------------------------------------------------------- the forged verdict

def test_a_forged_pass_over_a_mandatory_violation_is_refused() -> None:
    """The case the whole re-derivation exists for.

    Well-formed, parses, declares PASS - and its own criteria say FAIL. A consumer
    that READ `status` instead of deriving it would report a clean pass, and
    nothing downstream re-derives this gate's verdict.
    """
    verdict, detail = mod.evaluate(CONTROLS / "cases" / "bad-forged-pass-violation")
    assert verdict == "forged"
    assert mod.VERDICTS[verdict] != 0
    assert "derive" in detail


def test_a_pass_over_no_mandatory_criteria_is_refused(tmp_path: Path) -> None:
    """records.md: "No mandatory criteria yields INCONCLUSIVE, never PASS - an
    empty population must not render as a clean one." This repository's own #1014
    rule, arriving inside someone else's record format."""
    (tmp_path / "r.json").write_text(json.dumps({
        "version": 1, "kind": "verified-result", "status": "PASS", "criteria": [],
    }))
    verdict, _ = mod.evaluate(tmp_path)
    assert verdict == "forged", "an empty criteria set rendered as a clean pass"


def test_optional_criteria_do_not_enter_the_computation_in_either_direction(
    tmp_path: Path,
) -> None:
    """"Optional quality scores cannot average away mandatory failures."

    BOTH directions, and the second is the one that catches a real mutation. The
    first fixture alone reads as sufficient and is not: with optional criteria
    wrongly counted as mandatory it still derives FAIL, so it still reports
    `forged` and the assertion never moves. Only the second fixture separates
    "optional is excluded" from "optional happens not to matter here" - it is a
    genuine PASS that a gate counting optional criteria would refuse.
    """
    rescue = tmp_path / "rescue"
    rescue.mkdir()
    (rescue / "r.json").write_text(json.dumps({
        "version": 1, "kind": "verified-result", "status": "PASS",
        "criteria": [
            {"id": "m", "mandatory": True, "outcome": "VIOLATED"},
            {"id": "o1", "mandatory": False, "outcome": "SATISFIED"},
            {"id": "o2", "mandatory": False, "outcome": "SATISFIED"},
        ],
    }))
    assert mod.evaluate(rescue)[0] == "forged", "optional satisfaction rescued a failure"

    sink = tmp_path / "sink"
    sink.mkdir()
    (sink / "r.json").write_text(json.dumps({
        "version": 1, "kind": "verified-result", "status": "PASS",
        "criteria": [
            {"id": "m", "mandatory": True, "outcome": "SATISFIED"},
            {"id": "o1", "mandatory": False, "outcome": "VIOLATED"},
        ],
    }))
    assert mod.evaluate(sink)[0] == "pass", (
        "an optional violation sank a genuine pass - optional criteria are "
        "entering the derivation, which the record format forbids"
    )


def test_a_forged_verdict_cannot_escape_into_run_state(tmp_path: Path) -> None:
    """records.md permits a producer to declare only UNAVAILABLE or NOT_RUN;
    the other three are derived. Without that, the forgery just moves field."""
    (tmp_path / "r.json").write_text(json.dumps({
        "version": 1, "kind": "verified-result", "status": "PASS",
        "run_state": "PASS",
        "criteria": [{"id": "m", "mandatory": True, "outcome": "VIOLATED"}],
    }))
    verdict, detail = mod.evaluate(tmp_path)
    assert verdict == "forged"
    assert "run_state" in detail


def test_an_honest_inconclusive_is_not_reported_as_clean() -> None:
    """Consistent with its criteria, so NOT forged - and still never exit 0."""
    verdict, _ = mod.evaluate(CONTROLS / "cases" / "bad-inconclusive")
    assert verdict == "inconclusive"
    assert mod.VERDICTS[verdict] != 0


def test_the_violation_rule_is_tested_before_the_unknown_rule() -> None:
    """"An established mandatory violation remains FAIL when another criterion is
    unknown." Swapping the two steps softens an established failure into an
    inconclusive, which is a different wrong answer rather than a safer one."""
    got = mod.derive_status(
        [{"id": "a", "mandatory": True, "outcome": "VIOLATED"},
         {"id": "b", "mandatory": True, "outcome": "UNKNOWN"}], None)
    assert got == "FAIL", f"the unknown swallowed an established violation: {got}"


def test_a_criterion_outside_the_vocabulary_is_refused(tmp_path: Path) -> None:
    """Not bucketed into the nearest outcome this gate happens to understand."""
    (tmp_path / "r.json").write_text(json.dumps({
        "version": 1, "kind": "verified-result", "status": "PASS",
        "criteria": [{"id": "m", "mandatory": True, "outcome": "PROBABLY_FINE"}],
    }))
    assert mod.evaluate(tmp_path)[0] == "unreadable"


def test_a_usage_error_is_distinguishable_from_every_verdict() -> None:
    """argparse's default usage exit is 2, which is this gate's `absent`.

    A mistyped flag would otherwise report the same code as "I looked and found
    no artifact" - a gate answering a question nobody asked, in the vocabulary of
    the one they did.
    """
    proc = subprocess.run(["python3", str(GATE), "--no-such-flag"],
                          capture_output=True, text=True)
    assert proc.returncode == mod.USAGE_EXIT
    assert proc.returncode not in set(mod.VERDICTS.values()), (
        f"a usage error exits {proc.returncode}, which is also verdict "
        f"{[k for k, v in mod.VERDICTS.items() if v == proc.returncode]}"
    )


# ------------------------------------------- refusals found by counter-model review

def test_a_malformed_mandatory_flag_cannot_delete_a_violation(tmp_path: Path) -> None:
    """The sharpest hole the counter-model review found, and the least visible.

    `mandatory` was read as `is True`, so the STRING "true" was falsy for that
    test and the criterion silently became optional. A record could then carry a
    VIOLATED mandatory criterion, derive PASS because the violation had dropped
    out of the population, match its declared PASS, and report clean. One typo in
    a producer defeated the entire forged-verdict defence - by making evidence
    DISAPPEAR rather than by contradicting anything, which is why no assertion
    about agreement between status and criteria could have caught it.
    """
    (tmp_path / "r.json").write_text(json.dumps({
        "version": 1, "kind": "verified-result", "status": "PASS",
        "criteria": [
            {"id": "ok", "mandatory": True, "outcome": "SATISFIED"},
            {"id": "bad", "mandatory": "true", "outcome": "VIOLATED"},
        ],
    }))
    verdict, detail = mod.evaluate(tmp_path)
    assert verdict == "unreadable", (
        f"a non-boolean `mandatory` was accepted, so the VIOLATED criterion it "
        f"carries dropped out of the derivation: {verdict}"
    )
    assert "boolean" in detail


def test_a_record_of_another_kind_is_refused(tmp_path: Path) -> None:
    """A verdict about a population the record was never part of."""
    (tmp_path / "r.json").write_text(json.dumps({
        "version": 1, "kind": "artifact-manifest", "status": "PASS",
        "criteria": [{"id": "c", "mandatory": True, "outcome": "SATISFIED"}],
    }))
    verdict, detail = mod.evaluate(tmp_path)
    assert verdict == "unreadable"
    assert "verified-result" in detail


@pytest.mark.parametrize("field", ["status", "run_state"])
def test_an_unhashable_field_is_refused_not_crashed(tmp_path: Path, field: str) -> None:
    """JSON permits `"status": []`; `[] in frozenset(...)` raises TypeError.

    The traceback exited 1 - this gate's `failure` code - printing no verdict line
    and no population note. Malformed input was therefore reported as a producer's
    recorded FAILURE, and the advisory `|| true` wrappers swallowed the traceback
    that was the only sign anything had gone wrong. A crash rendering as a
    confident wrong answer is worse than one rendering as noise.
    """
    record = {"version": 1, "kind": "verified-result", "status": "PASS",
              "criteria": [{"id": "c", "mandatory": True, "outcome": "SATISFIED"}]}
    record[field] = []
    (tmp_path / "r.json").write_text(json.dumps(record))

    proc = subprocess.run(["python3", str(GATE), "--dir", str(tmp_path)],
                          capture_output=True, text=True)
    assert proc.returncode == mod.VERDICTS["unreadable"], (
        f"exit {proc.returncode}; stderr={proc.stderr.strip()[-200:]}"
    )
    assert "Traceback" not in proc.stderr
    assert mod.POPULATION_NOTE in proc.stdout, "a refusal printed no population note"


def test_the_gate_prints_a_verdict_line_on_every_committed_case() -> None:
    """No committed input may leave the gate silent - silence is unreadable output
    that the advisory `|| true` would turn into an ordinary green."""
    for case in sorted((CONTROLS / "cases").iterdir()):
        proc = subprocess.run(["python3", str(GATE), "--dir", str(case)],
                              capture_output=True, text=True)
        assert proc.stdout.startswith("behavioral-eval: "), (
            f"{case.name} produced no verdict line (stderr={proc.stderr[-200:]})"
        )
