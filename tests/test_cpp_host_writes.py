"""The seam's VERDICT is read, not just its door used (issue #1198).

#1132 routed every host write in the two cpp command documents through
`scripts/cpp-host-write.sh`, which declares what it touches and can be told to
defer a surface. That made the seam TOTAL. Nothing checked that it was
REACHABLE, or that its answer was listened to.

The seam returns 0 wrote / 3 deferred-by-request / 1 failed, and 127 when it is
not installed. Measured on 2026-09-22, all twenty call sites discarded it:

    helper absent:   `✓ Flow allowlist merged (2 total allow rules)`  - 0 of 52
                     merged, the file untouched, and the count is the PRE-merge
                     total, so the false claim carried a plausible number
    surface deferred: `✓ Flow allowlist merged (2 total allow rules)` - printed
                     directly over the seam's own `DEFERRED ... not written, by
                     request`

The second is #1139's defect inverted. There, a caller was told a surface was
protected and it was written. Here, a caller is told it was written and it was
protected - and the seam did its job perfectly in both halves.

WHY THE RULE IS "ALWAYS" AND NOT "WHEN A CLAIM FOLLOWS". Keying the finding on a
nearby checkmark is the obvious framing and it excuses the shape that actually
bit: a `link-into` loop calling the seam ninety times, claiming nothing, and
silently linking nothing. `controls/cpp-host-writes/alternatives/` holds that
implementation and two others, and the discrimination tests below are what make
the committed cases load-bearing rather than decorative.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-cpp-host-writes.py"
CONTROL = ROOT / "controls" / "cpp-host-writes"
ALTERNATIVES = CONTROL / "alternatives"
DOCUMENTS = (".claude/commands/cpp/init.md", ".claude/commands/cpp/update.md")

#: The commit whose documents carried all twenty unguarded call sites - the
#: state measured on 2026-09-22, immediately before this fix. Pinned so the
#: regression keeps its subject after the fix lands on main.
PRE_FIX_SHA = "5a4d7fcd35d252420e5e69151db6c1ba5946de08"

BAD_CASES = (
    "bad-unguarded-seam-call",
    "bad-unguarded-loop-no-claim",
    "bad-status-only-inside-heredoc",
    #: Added after counter-model review of this issue's OWN fix. Both were
    #: reproduced against the first implementation before being fixed.
    "bad-quoted-invocation-unguarded",
    "bad-neighbour-command-status",
    #: Second counter-model pass. The LINE-HEAD framing that fixed the first
    #: pass's false positive could see none of these.
    "bad-invocation-after-separator",
    "bad-neighbour-chain-after-semicolon",
    "bad-status-captured-after-another-command",
)
#: CLAUDE.md core directive (#602): a test that shells out to a real binary
#: carries a shutil.which guard, so the CI validate image - which has no git -
#: skips it rather than failing on an absent tool.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git absent in the CI validate image"
)

GOOD_CASES = (
    "good-guarded-seam-call",
    "good-seam-call-chained",
    "good-continuation-then-handler",
    "good-seam-named-in-prose",
    "good-blank-line-before-handler",
    "good-same-line-status-capture",
    "good-neighbouring-script-not-the-seam",
    "good-seam-path-as-assignment-value",
)


def _run(script: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("case", BAD_CASES)
def test_the_gate_reds_on_each_known_bad_shape(case: str) -> None:
    res = _run(GATE, CONTROL / "cases" / case)
    assert res.returncode == 1, f"{case}: expected a finding, got {res.returncode}\n{res.stdout}"
    assert "UNREAD-SEAM-VERDICT:" in res.stdout, res.stdout


@pytest.mark.parametrize("case", GOOD_CASES)
def test_the_gate_passes_each_correct_shape(case: str) -> None:
    """A gate that cannot be satisfied is a gate that gets switched off.

    These are not decoration. `good-continuation-then-handler` is the exact
    shape of the real `json-merge-sections \\` call in both documents, and the
    first implementation of this check reported it as unguarded.
    """
    res = _run(GATE, CONTROL / "cases" / case)
    assert res.returncode == 0, f"{case}: expected clean, got {res.returncode}\n{res.stdout}"


@requires_git
def test_the_gate_reds_on_the_documents_as_they_were_before_the_fix(tmp_path: Path) -> None:
    """THE REGRESSION TEST. It must fail on the code before the fix.

    The pre-fix documents come from git rather than from a fixture, so this
    cannot drift into asserting against a hand-made copy of a defect nobody
    shipped. Twenty sites is the measured count, and it is asserted rather than
    merely printed: a version of this gate that found one site would otherwise
    satisfy a bare `!= 0`.

    THE SHA IS PINNED, NOT `HEAD`. Resolving HEAD makes this test pass once -
    on the branch that fixes the defect - and then skip forever, because after
    the merge HEAD carries the fix. A regression test that disables itself the
    moment it goes green is the thing this repository writes controls to avoid.
    Pinned, it keeps demonstrating on the real pre-fix bytes.

    The durable negative control is `controls/cpp-host-writes`, whose committed
    cases run whether or not this object is fetchable; this test adds that the
    gate reds on CONTENT THAT SHIPPED, not only on fixtures written to be caught.
    """
    base = PRE_FIX_SHA
    for rel in DOCUMENTS:
        blob = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{base}:{rel}"],
            capture_output=True, text=True,
        )
        if blob.returncode != 0:
            #: A shallow clone legitimately lacks the object (#1157). That is
            #: "could not look", never "looked and found it clean", so it skips
            #: rather than passing.
            pytest.skip(f"{rel} is not reachable at {base[:8]} (shallow clone?)")
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(blob.stdout, encoding="utf-8")

    res = _run(GATE, tmp_path)
    findings = [ln for ln in res.stdout.splitlines()
                if ln.startswith("UNREAD-SEAM-VERDICT:")]
    #: NO "the defect is gone" ESCAPE HATCH. An earlier draft skipped when the
    #: findings were empty, reasoning that the documents might have been fixed
    #: since. With the SHA pinned they cannot be: those bytes are frozen. Zero
    #: findings here means the GATE went blind, and routing that to a skip would
    #: make the one test that proves this gate can fail report "nothing to do"
    #: at exactly the moment it stopped being able to.
    assert res.returncode == 1, (
        f"the gate passed the pre-fix documents at {base[:8]}. Those bytes are "
        f"frozen and carried 20 unguarded call sites, so this is the gate going "
        f"blind, not the defect being fixed.\n{res.stdout}"
    )
    assert len(findings) == 20, (
        f"expected the 20 measured sites at {base[:8]}, found {len(findings)}"
    )


def test_the_fixed_documents_are_clean() -> None:
    """The other half of the pair above, run against the same gate.

    Separately, this is the assertion that keeps the two documents fixed: a
    twenty-first unguarded call added later reds here.
    """
    res = _run(GATE, ROOT)
    assert res.returncode == 0, res.stdout


@pytest.mark.parametrize(
    "alternative, excused",
    [
        #: Each pair is "this wrong implementation would let this case through".
        #: Without them, a reader cannot tell a case that earns its place from
        #: one that merely passes.
        ("naive-next-line-check-cpp-host-writes.py", "bad-unguarded-loop-no-claim"),
        ("naive-next-line-check-cpp-host-writes.py", "bad-status-only-inside-heredoc"),
        ("pre-1198-check-cpp-host-writes.py", "bad-unguarded-seam-call"),
        ("pre-1198-check-cpp-host-writes.py", "bad-unguarded-loop-no-claim"),
        ("pre-1198-check-cpp-host-writes.py", "bad-status-only-inside-heredoc"),
        #: The PROXIMITY framing - this gate's own first implementation,
        #: recovered from the index. Each of these was a live defect in it.
        ("proximity-framing-check-cpp-host-writes.py", "bad-quoted-invocation-unguarded"),
        ("proximity-framing-check-cpp-host-writes.py", "bad-neighbour-command-status"),
        #: The LINE-HEAD framing - the SECOND real implementation, recovered
        #: from the index between the two review passes.
        ("line-head-framing-check-cpp-host-writes.py", "bad-invocation-after-separator"),
        ("line-head-framing-check-cpp-host-writes.py", "bad-neighbour-chain-after-semicolon"),
        ("line-head-framing-check-cpp-host-writes.py", "bad-status-captured-after-another-command"),
    ],
)
def test_each_bad_case_is_excused_by_a_committed_wrong_implementation(
    alternative: str, excused: str
) -> None:
    """A bad case only demonstrates something if some plausible gate MISSES it.

    The control battery makes this claim for `anchors/first-framing`, which is
    blind to the whole register. These finer pairs say WHICH wrong framing each
    new case defends against - the property the battery's one-anchor model
    cannot express.
    """
    alt, gate = _run(ALTERNATIVES / alternative, CONTROL / "cases" / excused), \
        _run(GATE, CONTROL / "cases" / excused)
    assert gate.returncode == 1, f"the gate should catch {excused}\n{gate.stdout}"
    assert alt.returncode == 0, (
        f"{alternative} was expected to MISS {excused}; it caught it, so that "
        f"case no longer distinguishes the gate from it\n{alt.stdout}"
    )


@pytest.mark.parametrize("case", GOOD_CASES)
def test_the_over_broad_framing_reds_on_correct_code(case: str) -> None:
    """What the `good-` cases are for.

    `over-broad` flags every seam invocation without asking whether the status
    was consulted. It passes every bad case in the register, so only these
    cases separate it from the gate - and it fails on the fix itself, which is
    the direction of error that gets a check deleted rather than repaired.
    """
    over_broad = _run(ALTERNATIVES / "over-broad-check-cpp-host-writes.py", CONTROL / "cases" / case)
    gate = _run(GATE, CONTROL / "cases" / case)
    assert gate.returncode == 0, f"the gate should pass {case}\n{gate.stdout}"
    assert over_broad.returncode == 1, (
        f"over-broad was expected to red on {case}; it passed, so this case no "
        f"longer separates the gate from it\n{over_broad.stdout}"
    )


@pytest.mark.parametrize(
    "case",
    ["good-seam-named-in-prose", "good-blank-line-before-handler",
     "good-same-line-status-capture"],
)
def test_the_proximity_framing_false_positives_where_the_gate_passes(case: str) -> None:
    """The three false positives that would have got this gate deleted.

    A gate reporting a finding on its own documentation, on a blank line, and
    on a legitimate same-line `rc=$?` is not a stricter gate - it is one that
    cannot be satisfied by correct code, and the fix for that is usually
    someone removing it. These assert the direction of error, not just its
    presence.
    """
    proximity = _run(
        ALTERNATIVES / "proximity-framing-check-cpp-host-writes.py",
        CONTROL / "cases" / case,
    )
    gate = _run(GATE, CONTROL / "cases" / case)
    assert gate.returncode == 0, f"the gate should pass {case}\n{gate.stdout}"
    assert proximity.returncode == 1, (
        f"proximity-framing was expected to FALSE-POSITIVE on {case}; it passed, "
        f"so this case no longer records that defect\n{proximity.stdout}"
    )


def test_the_gate_can_see_the_bootstrap_this_issue_added() -> None:
    """The blind spot that mattered most, asserted on the REAL documents.

    The fix adds a bootstrap invocation written with a QUOTED path, and the
    first implementation of this gate could not match it - so the gate was
    blind to precisely the calls its own change introduced. Counting the
    invocations the gate can SEE, in the shipped documents, is what keeps that
    from silently returning: a pattern that stops matching quoted calls drops
    this count and fails here, even though the documents are clean either way.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("gate_mod", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for rel, expected in ((".claude/commands/cpp/init.md", 14),
                          (".claude/commands/cpp/update.md", 7)):
        text = (ROOT / rel).read_text(encoding="utf-8")
        seen = [st for _, st in mod._shell_statements(text)
                if mod.SEAM_INVOKE_RE.search(st)]
        assert len(seen) == expected, (
            f"{rel}: the gate sees {len(seen)} seam invocation(s), expected "
            f"{expected}. A drop means the matcher stopped recognising a form "
            f"the document uses - most likely the quoted bootstrap."
        )
        quoted = [st for st in seen if '"$CPP_DIR' in st]
        assert quoted, f"{rel}: no QUOTED invocation is visible to the gate"


@pytest.mark.parametrize(
    "case",
    ["good-neighbouring-script-not-the-seam", "good-seam-path-as-assignment-value"],
)
def test_a_finding_names_our_seam_and_not_a_neighbour(case: str) -> None:
    """The detector-contract question: can a non-zero tell ours from theirs?

    The line-head framing's path pattern accepted any prefix, so
    `./not-cpp-host-write.sh settings-merge` produced an UNREAD-SEAM-VERDICT
    naming OUR seam for somebody else's command - and an environment
    assignment whose value happens to be the seam's path was reported as an
    invocation. Both are findings that cannot distinguish our thing from a
    neighbour's, which is the half of the contract a stricter gate usually
    gets wrong.
    """
    line_head = _run(
        ALTERNATIVES / "line-head-framing-check-cpp-host-writes.py",
        CONTROL / "cases" / case,
    )
    gate = _run(GATE, CONTROL / "cases" / case)
    assert gate.returncode == 0, f"the gate should pass {case}\n{gate.stdout}"
    assert line_head.returncode == 1, (
        f"line-head-framing was expected to misattribute {case}; it passed, so "
        f"this case no longer records that defect\n{line_head.stdout}"
    )


def test_a_crash_is_not_a_detection() -> None:
    """Exit 1 without a verdict line is a traceback, not a finding.

    Written because it happened here: a bad edit removed `scan` from the
    module, every fixture then exited 1, and a probe reading only exit codes
    reported the whole register as passing. The control battery already makes
    this distinction (`detect_signal`); this asserts the gate keeps EMITTING
    the marker the battery keys on, so the two cannot drift apart.
    """
    for case, expected in (("bad-unguarded-seam-call", 1), ("good-guarded-seam-call", 0)):
        res = _run(GATE, CONTROL / "cases" / case)
        assert res.returncode == expected
        assert any(ln.startswith("check-cpp-host-writes: ")
                   for ln in res.stdout.splitlines()), (
            f"{case}: the gate exited {res.returncode} without its verdict line, "
            f"so this run cannot be told from a crash\n{res.stdout}{res.stderr}"
        )
