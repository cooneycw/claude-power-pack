"""The harness upgrade reports the VERSION TRANSITION, not the exit code (#1022).

`/cpp:update` Step 5d.2 ran `npm install -g @qwen-code/qwen-code`, read exit 0,
and composed `Tier 6 refreshed`. On a host running node 20 that install does
nothing: npm resolves `latest` down to the newest ENGINE-COMPATIBLE release, and
0.24.0 declares `engines.node >=22.0.0`, so npm reinstalls the 0.15.10 already
present and exits 0 with no error. A real upgrade and a silently-capped one were
the same bytes on stdout, and the Step 10 summary quoting them is read by the
operator and by later sessions, none of which re-derive the version.

WHY THIS FILE EXISTS ALONGSIDE `controls/npm-global-upgrade/`. The control is
executed BY `check-negative-controls.py`, so a harness mutated to emit PASS would
report its own control passing. What falsifies that is a DIFFERENT runner driving
the same fixtures and asserting the verdicts rather than accepting them. That is
this file, and it is why the two are not redundant (ADR 0008, the row-63 note).

THE TRIPWIRE'S NEGATIVE CONTROL IS THE REAL PRE-FIX TEXT, not a synthetic one:
`tests/fixtures/npm_global_upgrade/update_5d_pre_fix.md` is Step 5d exactly as it
stood at 843ba08. Pointing a detector at a tree where nothing is wrong proves
nothing.

AND THE OBVIOUS TRIPWIRE IS BLIND HERE - the fixture is what showed it. The
pre-fix defect is NOT an `npm install -g` sitting in a bash block: the only
in-block occurrence is an echoed hint string, and the instruction to actually run
it lives in PROSE ("Ask the user, then run `npm install -g ...`"), which the model
executed ad hoc. A "no npm install in a code block" rule scores that tree clean.
Worse, the FIXED document quotes the old command in its explanation, so a text
search for it fires on the fix and not on the defect - exactly backwards. The
property that actually separates the two texts is where the lane status comes
from: asserted, or derived from the helper's verdict line.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "npm-global-upgrade.sh"
CONTROL = ROOT / "controls" / "npm-global-upgrade"
RUNNER = CONTROL / "run-case.sh"
UPDATE_MD = ROOT / ".claude" / "commands" / "cpp" / "update.md"
PRE_FIX = ROOT / "tests" / "fixtures" / "npm_global_upgrade" / "update_5d_pre_fix.md"

requires_sh = pytest.mark.skipif(
    shutil.which("sh") is None,
    reason="needs sh: these tests run the helper through it (CLAUDE.md binary-guard directive)",
)

#: (case, expected verdict word, expected exit code). The exit code is asserted
#: beside the word because they are separate claims: a verdict that named the
#: right problem and exited 0 would let `/cpp:update` carry on as if nothing had
#: been found, and every consumer of this helper reads one or the other.
CASES = [
    ("bad-capped-by-engines", "capped", 1),
    ("bad-silent-noop", "not-upgraded", 1),
    ("bad-unevaluable-engine", "not-upgraded", 1),
    ("bad-compound-engine", "not-upgraded", 1),
    ("bad-minor-engine-gap", "capped", 1),
    ("bad-major-only-engine", "not-upgraded", 1),
    ("bad-downgraded", "downgraded", 1),
    ("bad-prerelease-forward", "unknown", 2),
    ("bad-prerelease-backward", "unknown", 2),
    ("bad-install-failed", "failed", 1),
    ("bad-unreadable-latest", "unknown", 2),
    ("good-upgraded", "upgraded", 0),
    ("good-already-current", "current", 0),
]


def _run_case(gate: Path, case: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(RUNNER), str(gate), str(CONTROL / "cases" / case)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=ROOT,
    )


def _verdict(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("NPM_UPGRADE: "):
            return line[len("NPM_UPGRADE: ") :]
    return ""


@requires_sh
@pytest.mark.parametrize(("case", "word", "code"), CASES, ids=[c[0] for c in CASES])
def test_each_case_gets_its_own_verdict(case: str, word: str, code: int) -> None:
    """Each committed case produces its own verdict and its own exit code."""
    proc = _run_case(GATE, case)
    verdict = _verdict(proc.stdout)
    assert verdict.startswith(word), (
        f"case {case}: expected a '{word}' verdict, got {verdict!r}\n{proc.stdout}{proc.stderr}"
    )
    assert proc.returncode == code, (
        f"case {case}: expected exit {code}, got {proc.returncode} for verdict {verdict!r}"
    )


@requires_sh
def test_capped_names_the_constraint_and_the_host() -> None:
    """`capped` carries the evidence, not just the word.

    A bare "not upgraded" sends the operator to npm. The whole value of this
    verdict is that it names the two machine-readable facts that produced it, so
    the next person does not re-derive them - which is also why this instrument
    needs a committed control at all.
    """
    verdict = _verdict(_run_case(GATE, "bad-capped-by-engines").stdout)
    assert ">=22.0.0" in verdict, f"the engine constraint is missing from {verdict!r}"
    assert "v20.20.2" in verdict, f"this host's node version is missing from {verdict!r}"
    assert "0.24.0" in verdict, f"the published latest is missing from {verdict!r}"


@requires_sh
def test_an_unevaluable_constraint_is_never_reported_as_the_cause() -> None:
    """`^22 || ^20` is quoted verbatim and labelled, never turned into `capped`.

    THE DIRECTION THAT MATTERS: node 20 SATISFIES the `^20` branch, so blaming
    engines here would be a fabricated reason that is also false. A reason
    attached to a verdict nobody re-derives ends an investigation rather than
    starting one, and this is the shape where reading the message does not
    reveal the error.
    """
    proc = _run_case(GATE, "bad-unevaluable-engine")
    verdict = _verdict(proc.stdout)
    assert verdict.startswith("not-upgraded"), verdict
    assert "capped" not in verdict, f"an unevaluable constraint was reported as a cause: {verdict!r}"
    assert "^22 || ^20" in verdict, f"the constraint is not quoted verbatim in {verdict!r}"
    assert "NOT evaluated" in verdict, f"the constraint is not labelled unevaluated in {verdict!r}"


@requires_sh
@pytest.mark.parametrize(
    ("case", "engine"),
    [("bad-compound-engine", ">=22.0.0 || >=20.0.0"), ("bad-unevaluable-engine", "^22 || ^20")],
)
def test_a_constraint_the_host_satisfies_is_never_the_cause(case: str, engine: str) -> None:
    """A `>=` PREFIX is not a `>=` constraint.

    `>=22.0.0 || >=20.0.0` begins with `>=`, so reading the first major condemns
    a host the disjunction plainly admits. The counter-model review reproduced
    this; the author's own case set had only the `^22` shape, which the prefix
    match happened to reject for an unrelated reason. Both must land on
    `not-upgraded` with the constraint quoted, never on `capped`.
    """
    verdict = _verdict(_run_case(GATE, case).stdout)
    assert verdict.startswith("not-upgraded"), verdict
    assert "capped" not in verdict, f"a satisfiable constraint was reported as the cause: {verdict!r}"
    assert engine in verdict, f"the constraint is not quoted verbatim in {verdict!r}"


@requires_sh
def test_an_engine_ceiling_in_the_minor_version_is_still_the_cause() -> None:
    """The other half of the same finding.

    node v22.1.0 against `>=22.12.0`: the majors match, so a major-only
    comparison reports that nothing explains the stall when the constraint is
    the entire reason. An instrument wrong in both directions needs a test in
    both, or fixing one direction silently ships the other.
    """
    verdict = _verdict(_run_case(GATE, "bad-minor-engine-gap").stdout)
    assert verdict.startswith("capped"), verdict
    assert ">=22.12.0" in verdict and "v22.1.0" in verdict, verdict


@requires_sh
def test_an_abbreviated_engine_requirement_is_not_inflated() -> None:
    """`>=22` means 22.0.0, not 22.22.22.

    `cut -d. -f2` prints the ENTIRE line when it contains no delimiter, so the
    first comparator read an abbreviated requirement as 22.22.22 and condemned a
    node v22.1.0 host that satisfies it. Second counter-model pass. The tell is
    that the wrong answer is a CONFIDENT one: `capped` with a real constraint and
    a real node version quoted beside it.
    """
    verdict = _verdict(_run_case(GATE, "bad-major-only-engine").stdout)
    assert verdict.startswith("not-upgraded"), verdict
    assert "capped" not in verdict, f"a satisfied `>=22` was reported as the cause: {verdict!r}"


@requires_sh
@pytest.mark.parametrize(
    ("case", "transition"),
    [
        ("bad-prerelease-forward", "1.5.0 -> 1.5.0-beta.1"),
        ("bad-prerelease-backward", "1.5.0-rc1 -> 1.5.0"),
    ],
)
def test_a_move_with_no_establishable_direction_claims_none(case: str, transition: str) -> None:
    """A prerelease suffix change is `unknown`, not a direction.

    Both directions of one parsing defect, found on the second counter-model
    pass. Forward: equal numeric cores fell through to `upgraded`, so a stable
    harness replaced by a prerelease was reported as a successful upgrade.
    Backward: `tr -cd '0-9'` kept the suffix's digits, so `0-rc1` read as patch
    01 and a prerelease becoming its own stable scored as a DOWNGRADE. Both are
    committed, because fixing one half of a two-sided error silently ships the
    other.
    """
    proc = _run_case(GATE, case)
    verdict = _verdict(proc.stdout)
    assert verdict.startswith("unknown"), verdict
    assert proc.returncode == 2, proc.returncode
    assert transition in verdict, verdict
    assert "NOT established" in verdict, verdict


@requires_sh
def test_a_backward_move_is_not_an_upgrade() -> None:
    """1.6.0 -> 1.5.0 is `downgraded`, and it is a finding.

    `after != before` was the whole upgrade test, so a dist-tag that moved back
    reported `upgraded` and exit 0 - this issue's own defect class inside the fix
    for it. Found by the counter-model review.
    """
    proc = _run_case(GATE, "bad-downgraded")
    verdict = _verdict(proc.stdout)
    assert verdict.startswith("downgraded"), verdict
    assert proc.returncode == 1, f"a downgrade exited {proc.returncode}, so a caller reads it as fine"
    assert "1.6.0 -> 1.5.0" in verdict, verdict


@requires_sh
def test_a_host_already_on_latest_is_not_a_finding() -> None:
    """The healthy no-move exits 0.

    A check phrased as "did the version change" fails this tree. An instrument
    that reports every up-to-date machine as a problem is switched off within a
    week, which returns the lane to #1022 by a different route - so this is a
    property of the fix, not a nicety.
    """
    proc = _run_case(GATE, "good-already-current")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _verdict(proc.stdout).startswith("current")


@requires_sh
def test_the_blind_anchor_misses_every_bad_case() -> None:
    """The control can fail: the pre-fix shape scores clean on all five.

    This is the demonstration the Negative Control directive asks for, executed
    rather than described. `check-negative-controls.py` performs it too; doing it
    here as well is the point - the harness cannot be the only thing that
    certifies its own controls.
    """
    anchor = CONTROL / "anchors" / "constructed-exit-code-only-npm-global-upgrade.sh"
    assert anchor.is_file(), "the anchor is missing; nothing demonstrates this control can fail"
    for case, _word, _code in CASES:
        proc = _run_case(anchor, case)
        assert proc.returncode == 0, (
            f"the anchor reported something on {case} (exit {proc.returncode}); "
            "it is supposed to be blind, so this control would prove nothing"
        )


# --------------------------------------------------------------------------- #
# The tripwire over `/cpp:update`, and its negative control.
# --------------------------------------------------------------------------- #

#: A variable assigned from the helper's own verdict line. The pre-fix document
#: has no such assignment anywhere, which is the whole of the defect: the lane
#: status was ASSERTED rather than derived.
VERDICT_ASSIGN_RE = re.compile(r"^\s*([A-Z_][A-Z0-9_]*)=\$\([^)]*NPM_UPGRADE:", re.MULTILINE)

#: Every line that contributes to the Step 10 `Local-Model Lanes` summary.
STATUS_PART_RE = re.compile(r"^\s*LOCAL_MODEL_LANE_STATUS_PARTS\+=\((.*)\)\s*$", re.MULTILINE)


#: The lane subsections that must each carry their own harness verdict. An
#: ENUMERATION, not a discovered set: a lane that disappears from the document
#: has to read as a finding, and a rule that derives its population from the
#: document it is checking cannot report a missing member (the derive-members,
#: hardcode-universe split).
LANE_SECTIONS = ("#### 5d.2", "#### 5d.3")


def _step_5d(text: str) -> str:
    start = text.find("## Step 5d")
    assert start != -1, "Step 5d is not in this document"
    end = text.find("## Step 6", start)
    return text[start:end] if end != -1 else text[start:]


def _lane_region(text: str, heading: str) -> str | None:
    """The slice of Step 5d belonging to ONE lane, or None when it is absent."""
    region = _step_5d(text)
    start = region.find(heading)
    if start == -1:
        return None
    nxt = [region.find(h, start + 1) for h in LANE_SECTIONS]
    ends = [i for i in nxt if i > start]
    return region[start : min(ends)] if ends else region[start:]


def _status_parts_not_derived_from_a_verdict(text: str) -> list[str]:
    """Findings: a lane whose Step 10 status is not derived from ITS OWN verdict.

    Deliberately NOT a search for `npm install -g`, and not a naming convention.
    The fixture proved the first blind (the pre-fix install instruction is prose,
    and the FIXED text quotes the command while explaining it), and a rule keyed
    on a variable's spelling tests the spelling. What is asked is where the claim
    came from: a name assigned from a `NPM_UPGRADE:` line IN THE SAME LANE.

    TWO WAYS THIS WAS BLIND BEFORE, both reproduced by the counter-model review:

    - AN EMPTY POPULATION SCORED CLEAN. The check walked whatever status lines it
      found, so deleting both left nothing to walk and nothing to report - "I
      looked and found nothing" and "there was nothing to look at" sharing an
      answer, which is the exact question this repository asks of every detector.
      A lane with no status contribution is now a finding in its own right.
    - VERDICT VARIABLES WERE POOLED ACROSS LANES. Every name assigned anywhere in
      Step 5d cleared every status line, so writing the Gemma verdict into the
      Qwen summary passed. Each lane is now resolved against its own slice, so a
      Tier 6 line quoting Tier 7's harness is caught.
    """
    findings = []
    for heading in LANE_SECTIONS:
        region = _lane_region(text, heading)
        if region is None:
            findings.append(f"{heading}: the lane section is absent")
            continue
        derived = set(VERDICT_ASSIGN_RE.findall(region))
        parts = STATUS_PART_RE.findall(region)
        if not parts:
            findings.append(f"{heading}: no Local-Model Lanes status contribution")
            continue
        for value in parts:
            if not any(f"${name}" in value or f"${{{name}}}" in value for name in derived):
                findings.append(f"{heading}: {value.strip()}")
    return findings


def test_the_lane_status_is_derived_from_the_helpers_verdict() -> None:
    """Neither lane may assert its own refresh."""
    findings = _status_parts_not_derived_from_a_verdict(UPDATE_MD.read_text(encoding="utf-8"))
    assert findings == [], (
        "a Local-Model Lanes status is asserted rather than derived from the "
        f"upgrade helper's verdict: {findings}"
    )


def test_that_tripwire_fires_on_the_real_pre_fix_document() -> None:
    """THE NEGATIVE CONTROL for the test above.

    Both pre-fix status lines must be found: `Tier 6 refreshed` is a bare literal,
    and `Tier 7 refreshed ($GEMMA_PROFILE_STATUS)` carries a variable that is not a
    harness verdict at all - the trap for a detector that merely required "some
    interpolation". A tripwire that finds neither, or only one, is not watching
    what its name says.
    """
    findings = _status_parts_not_derived_from_a_verdict(PRE_FIX.read_text(encoding="utf-8"))
    assert len(findings) == 2, f"expected both pre-fix status lines, found {findings}"
    assert any("Tier 6 refreshed" in f for f in findings), findings
    assert any("Tier 7 refreshed" in f for f in findings), findings


def test_that_tripwire_fires_on_a_deleted_status_contribution() -> None:
    """A lane that contributes NOTHING is a finding, not an empty population.

    Reproduced by the counter-model review against the first cut: the detector
    walked the status lines it found, so removing them left it walking nothing
    and reporting nothing. "I looked and found nothing" must not share an answer
    with "there was nothing to look at".
    """
    text = UPDATE_MD.read_text(encoding="utf-8")
    mutated = re.sub(
        r"^\s*LOCAL_MODEL_LANE_STATUS_PARTS\+=\(\"Tier 6 [^\n]*\n",
        "",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    assert mutated != text, "the mutation did not apply; this test would prove nothing"
    findings = _status_parts_not_derived_from_a_verdict(mutated)
    assert any("5d.2" in f and "no Local-Model Lanes status" in f for f in findings), findings


def test_that_tripwire_fires_on_a_cross_lane_verdict() -> None:
    """Tier 6's summary may not quote Tier 7's harness verdict.

    Also from the counter-model review: verdict variables were pooled across the
    whole of Step 5d, so a name assigned in the Gemma lane cleared a claim made
    in the Qwen lane. A summary that reports one harness's state under another
    harness's name is wrong in the way that is hardest to notice - it is present,
    plausible, and about the wrong subject.
    """
    text = UPDATE_MD.read_text(encoding="utf-8")
    mutated = text.replace(
        'LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 6 harness $QWEN_LANE_VERDICT")',
        'LOCAL_MODEL_LANE_STATUS_PARTS+=("Tier 6 harness $GEMMA_HARNESS_VERDICT")',
    )
    assert mutated != text, "the mutation did not apply; this test would prove nothing"
    findings = _status_parts_not_derived_from_a_verdict(mutated)
    assert any("5d.2" in f and "GEMMA_HARNESS_VERDICT" in f for f in findings), findings


def test_the_upgrade_offers_route_through_the_helper() -> None:
    """Both 5d offers invoke the helper.

    WEAKER THAN IT LOOKS, said here rather than implied: this asks whether the
    document MENTIONS the helper in its Step 5d bash, not whether a run reaches
    it. The load-bearing check is the derivation test above, which cannot be
    satisfied without the helper's output actually existing.
    """
    region = _step_5d(UPDATE_MD.read_text(encoding="utf-8"))
    assert region.count("npm-global-upgrade.sh") >= 2, (
        "Step 5d does not route both harness upgrades through scripts/npm-global-upgrade.sh"
    )
