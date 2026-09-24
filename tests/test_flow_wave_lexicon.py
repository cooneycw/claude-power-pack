"""Tests for the wave transition lexicon (issue #701).

Covers ``scripts/flow-wave-lexicon.sh``, the reserved vocabulary for the wave
speech acts that are STATE TRANSITIONS with a wrong-answer cost, and its two
read-back mechanisms.

Contract:
- A message with NO reserved token is always valid (``none``, exit 0). Prose
  carries the argument; only a malformed PRESENT token refuses. This is the
  property that keeps the lexicon from crowding out the reasoning, which the
  issue names as the thing that must not happen.
- Every reserved token that is present must parse, and each requirement traces
  to a specific field failure: a GATE verdict names its subject, a HOLD names
  what it waits behind, a conditional approval carries its conditions, a MERGE
  authorisation names a real check ("when CI passes" is refused), a STATE
  assertion carries ``as-of <commit>``.
- ``record`` DERIVES the #645 verdict-ledger entry from the parsed GATE token.
  A body with no parseable GATE verdict records NOTHING and exits 1.

THE POINT OF THIS FILE. The issue's own kill condition is that a lexicon nobody
validates is prose with extra steps - "a reflexive ``GATE: GO`` prints what a
considered one prints". A test suite that only feeds this parser WELL-FORMED
messages and asserts exit 0 would have exactly that defect: it would pass
identically against a validator that accepted everything. So the negatives come
first and carry the weight - each malformed shape is asserted to be REFUSED,
with the refusal naming its line. ``TestTheLedgerIsLoadBearing`` closes the loop
by running the real ``flow-wave-plan.py`` over a ledger this tool wrote and
asserting the PLANNER'S OUTPUT changes - never merely that a command exited 0.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.wave_namespace import unique_wave

ROOT = Path(__file__).resolve().parents[1]
LEXICON = ROOT / "scripts" / "flow-wave-lexicon.sh"
MAILBOX = ROOT / "scripts" / "flow-wave-mailbox.sh"
PLANNER = ROOT / "scripts" / "flow-wave-plan.py"

# Drives a real `bash` subprocess; the CI validate container may not ship one,
# so skip there (CPP core directive, same shape as the other flow suites).
requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)
requires_jq = pytest.mark.skipif(
    shutil.which("jq") is None, reason="requires jq on PATH"
)

#: Unique per pytest INVOCATION (#881, #882). This file spawns no watchers, so
#: it was not a source of the collision - it shares the definition so the
#: literal has exactly one home and a third copy is not typed by hand.
WAVE = unique_wave("testlex")


def _run(tmp: Path, *args: str, stdin: str | None = None, timeout: int = 60):
    env = os.environ.copy()
    env["FLOW_WAVE_LEXICON_DIR"] = str(tmp / "wave")
    env["FLOW_WAVE_NOW"] = "1786470000"
    return subprocess.run(
        ["bash", str(LEXICON), *args],
        capture_output=True,
        text=True,
        env=env,
        input=stdin,
        timeout=timeout,
    )


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    for line in proc.stdout.splitlines():
        if line.startswith("FLOW_LEXICON: "):
            return line.split(": ", 1)[1].strip()
    return ""


def _detail(proc: subprocess.CompletedProcess[str], key: str) -> str:
    prefix = f"FLOW_LEXICON_{key}="
    for line in proc.stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _transitions(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [
        ln.split("=", 1)[1]
        for ln in proc.stdout.splitlines()
        if ln.startswith("FLOW_LEXICON_TRANSITION=")
    ]


def _validate(tmp: Path, body: str):
    return _run(tmp, "validate", stdin=body)


# --------------------------------------------------------------------------
# The negatives. These carry the suite: a validator that accepted everything
# would pass every positive test in this file and fail every test here.
# --------------------------------------------------------------------------


@requires_bash
class TestMalformedTransitionsAreRefused:
    """Each case is a shape that FAILED IN THE FIELD, asserted to be refused.

    The assertion is on the refusal (exit 1 + `invalid`) AND on the message
    naming the offending line, because a guard whose complaint does not say what
    is wrong gets worked around rather than fixed.
    """

    @pytest.mark.parametrize(
        "body,because",
        [
            ("GATE: GO", "a verdict that does not name its subject goes stale"),
            ("GATE: MAYBE #701", "only GO/HOLD/GO-WITH-CONDITIONS are verdicts"),
            ("GATE: HOLD #52", "a hold must name what it waits behind"),
            (
                "GATE: GO-WITH-CONDITIONS #701",
                "conditions left in the paragraph below are the crossed lane/gate message",
            ),
            ("LANE: GRANT worker-a", "a grant with no paths can read as its own inverse"),
            ("LANE: BLESS worker-a src/x.py", "only GRANT/SET/REVOKE are lane verbs"),
            ("LANE: GRANT", "a lane must name the role it applies to"),
            (
                "MERGE: AUTHORIZED #701 when CI passes",
                "'CI' does not distinguish the PR pipeline from the push pipeline",
            ),
            ("MERGE: AUTHORIZED #701 when green", "vague predicate"),
            ("MERGE: AUTHORIZED #701", "no predicate at all"),
            ("MERGE: PERMITTED #701 when x/y", "AUTHORIZED is the only merge transition"),
            ("STATE: everything is fine", "an unstamped assertion is silently stale"),
            ("STATE: as-of yesterday", "as-of needs a commit sha, not a word"),
            ("RATIFY #701", "a ruling with no reason cannot be distinguished from inattention"),
            ("OVERRULE", "a ruling must name the issue it answers"),
            ("PUSHBACK", "pushback with no argument can be skimmed past as agreement"),
            ("LEDGER\ndelivered: x", "the ledger shape requires all three sections"),
        ],
    )
    def test_refused(self, tmp_path: Path, body: str, because: str):
        proc = _validate(tmp_path, body)
        assert proc.returncode == 1, f"should refuse ({because}): {body!r}"
        assert _verdict(proc) == "invalid"
        assert "flow-wave-lexicon: line " in proc.stderr, (
            "a refusal must name the offending line"
        )

    def test_the_refusal_names_the_real_line_number(self, tmp_path: Path):
        body = "Some prose.\n\nMore prose.\nGATE: HOLD #52\n"
        proc = _validate(tmp_path, body)
        assert proc.returncode == 1
        assert "line 4:" in proc.stderr, proc.stderr

    def test_error_count_is_reported(self, tmp_path: Path):
        proc = _validate(tmp_path, "GATE: GO\nSTATE: soon\n")
        assert _detail(proc, "ERRORS") == "2"


# --------------------------------------------------------------------------
# Absence is not an error - the property that keeps prose prose.
# --------------------------------------------------------------------------


@requires_bash
class TestProseIsNeverRefused:
    def test_plain_prose_is_none_not_invalid(self, tmp_path: Path):
        proc = _validate(
            tmp_path,
            "Please verify the necessity evidence against the tree yourself.\n"
            "I disagree with the premise: #56 already landed that fixture.\n",
        )
        assert proc.returncode == 0
        assert _verdict(proc) == "none"
        assert _detail(proc, "TRANSITIONS") == "0"

    def test_a_reserved_word_mid_sentence_does_not_declare(self, tmp_path: Path):
        """Line-anchored, the #607 edge-grammar rule: a mention is not a
        declaration, or every design discussion of the lexicon fails to send.
        """
        proc = _validate(
            tmp_path,
            "I think the GATE: GO token is wrong here, and LANE: GRANT is worse.\n"
            "We should discuss whether PUSHBACK belongs in the vocabulary.\n",
        )
        assert proc.returncode == 0
        assert _verdict(proc) == "none"

    def test_reasoning_below_a_valid_token_is_untouched(self, tmp_path: Path):
        proc = _validate(
            tmp_path,
            "GATE: GO #701\n\n"
            "The reasoning: I re-ran the necessity evidence and the worker's\n"
            "claim about #676 holds - it merged 14 minutes after filing.\n",
        )
        assert proc.returncode == 0
        assert _verdict(proc) == "ok"


# --------------------------------------------------------------------------
# Well-formed tokens parse into the right transitions.
# --------------------------------------------------------------------------


@requires_bash
class TestWellFormedTransitionsParse:
    def test_each_token_is_recognized(self, tmp_path: Path):
        body = "\n".join(
            [
                "GATE: GO #701",
                "LANE: GRANT worker-a scripts/cli.py scripts/x.py",
                "LANE: REVOKE worker-b",
                "MERGE: AUTHORIZED #701 when ci/woodpecker/pr/woodpecker reports success",
                "STATE: as-of 4d6a62a",
                "RATIFY #701 narrower boundary accepted",
                "OVERRULE #702 that premise is stale",
                "PUSHBACK the assignment names a file that is not in my lane",
                "LEDGER",
                "delivered: the parser",
                "in-scope: the mailbox wiring",
                "residual: register.md, filed as #706",
            ]
        )
        proc = _validate(tmp_path, body)
        assert proc.returncode == 0, proc.stderr
        assert _verdict(proc) == "ok"
        kinds = [t.split(":", 1)[0] for t in _transitions(proc)]
        assert kinds == [
            "GATE",
            "LANE",
            "LANE",
            "MERGE",
            "STATE",
            "RATIFY",
            "OVERRULE",
            "PUSHBACK",
            "LEDGER",
        ]

    def test_a_named_check_is_accepted_where_a_vague_one_is_not(self, tmp_path: Path):
        """The positive half of the vague-predicate control: the SAME sentence
        shape passes once the check is named, so the refusal is about the
        predicate rather than about the grammar.
        """
        vague = _validate(tmp_path, "MERGE: AUTHORIZED #701 when CI passes")
        named = _validate(
            tmp_path,
            "MERGE: AUTHORIZED #701 when ci/woodpecker/pr/woodpecker reports success",
        )
        assert vague.returncode == 1
        assert named.returncode == 0

    def test_trailing_clause_does_not_defeat_the_predicate_check(self, tmp_path: Path):
        """The reference wave's actual phrasing carried an on-fail clause."""
        proc = _validate(
            tmp_path,
            "MERGE: AUTHORIZED #701 when ci/woodpecker/pr/woodpecker reports pass, "
            "on fail STOP and report",
        )
        assert proc.returncode == 0, proc.stderr

    def test_hold_accepts_a_multi_issue_behind_list(self, tmp_path: Path):
        proc = _validate(tmp_path, "GATE: HOLD #52 behind #56, #57 waiting on the migration")
        assert proc.returncode == 0, proc.stderr


# --------------------------------------------------------------------------
# record: the ledger entry is DERIVED, never hand-written.
# --------------------------------------------------------------------------


@requires_bash
@requires_jq
class TestRecordDerivesTheLedger:
    def _ledger(self, tmp: Path) -> list[dict]:
        path = tmp / "wave" / WAVE / "verdicts.json"
        return json.loads(path.read_text())

    def test_no_parseable_verdict_records_nothing(self, tmp_path: Path):
        """The refusal this verb exists for: a gate cannot be RECORDED as judged
        without a parseable verdict.
        """
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin="Looks good to me, go ahead.\n")
        assert proc.returncode == 1
        assert _verdict(proc) == "none"
        assert not (tmp_path / "wave" / WAVE / "verdicts.json").exists()

    def test_a_malformed_verdict_records_nothing(self, tmp_path: Path):
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin="GATE: GO\n")
        assert proc.returncode == 1
        assert _verdict(proc) == "invalid"
        assert not (tmp_path / "wave" / WAVE / "verdicts.json").exists()

    def test_go_becomes_an_approval(self, tmp_path: Path):
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin="GATE: GO #701 evidence checks out\n")
        assert proc.returncode == 0, proc.stderr
        assert _verdict(proc) == "recorded"
        entries = self._ledger(tmp_path)
        assert len(entries) == 1
        assert entries[0]["issue"] == 701
        assert entries[0]["ruling"] == "approved"
        assert entries[0]["reason"] == "evidence checks out"

    def test_hold_carries_holds_behind(self, tmp_path: Path):
        _run(tmp_path, "record", "--wave", WAVE, stdin="GATE: HOLD #52 behind #56, #57 migration first\n")
        entry = self._ledger(tmp_path)[0]
        assert entry["ruling"] == "hold"
        assert entry["holds_behind"] == [56, 57]

    def test_conditions_become_the_reason(self, tmp_path: Path):
        body = (
            "GATE: GO-WITH-CONDITIONS #60\n"
            "  - add a regression test pinning the empty-field case\n"
            "  - do not widen the fixture\n"
        )
        _run(tmp_path, "record", "--wave", WAVE, stdin=body)
        entry = self._ledger(tmp_path)[0]
        assert entry["ruling"] == "approved-with-conditions"
        assert "regression test" in entry["reason"]
        assert "widen the fixture" in entry["reason"]

    def test_serializes_becomes_adds_serialized(self, tmp_path: Path):
        """The two-`0009`s failure: a CONDITION can change an issue's footprint
        though its body never changes, and only the ledger can carry that.
        """
        body = (
            "GATE: GO-WITH-CONDITIONS #60\n"
            "  - evict the stale cache entries\n"
            "  serializes: migration-0009\n"
        )
        _run(tmp_path, "record", "--wave", WAVE, stdin=body)
        entry = self._ledger(tmp_path)[0]
        assert entry["adds_serialized"] == ["migration-0009"]

    def test_a_plain_approval_carries_no_optional_keys(self, tmp_path: Path):
        """Negative control for the two keys above - they must appear only when
        the token declared them, or every entry claims a footprint change.
        """
        _run(tmp_path, "record", "--wave", WAVE, stdin="GATE: GO #701 fine\n")
        entry = self._ledger(tmp_path)[0]
        assert "holds_behind" not in entry
        assert "adds_serialized" not in entry

    def test_entries_append_so_an_override_stays_recorded(self, tmp_path: Path):
        """#645 is last-entry-wins: overriding a ruling must remain a recorded
        act with its own reason, never a silent contradiction.
        """
        _run(tmp_path, "record", "--wave", WAVE, stdin="GATE: HOLD #52 behind #56 first\n")
        _run(tmp_path, "record", "--wave", WAVE, stdin="GATE: GO #52 #56 landed, hold lifted\n")
        entries = self._ledger(tmp_path)
        assert len(entries) == 2
        assert entries[0]["ruling"] == "hold"
        assert entries[1]["ruling"] == "approved"

    def test_dry_run_writes_nothing(self, tmp_path: Path):
        proc = _run(tmp_path, "record", "--wave", WAVE, "--dry-run", stdin="GATE: GO #701 ok\n")
        assert proc.returncode == 0
        assert not (tmp_path / "wave" / WAVE / "verdicts.json").exists()

    def test_a_non_array_ledger_is_refused_not_clobbered(self, tmp_path: Path):
        led = tmp_path / "led.json"
        led.write_text('{"not": "an array"}')
        proc = _run(
            tmp_path, "record", "--wave", WAVE, "--ledger", str(led), stdin="GATE: GO #701 ok\n"
        )
        assert proc.returncode == 3
        assert led.read_text() == '{"not": "an array"}'


# --------------------------------------------------------------------------
# The load-bearing proof: the planner's OUTPUT changes.
# --------------------------------------------------------------------------


@requires_bash
@requires_jq
class TestTheLedgerIsLoadBearing:
    """The anti-decoration contract, proved end to end.

    Each test runs the REAL planner twice over identical issue data - once
    without the ledger, once with the ledger this tool wrote - and asserts the
    two outputs DIFFER. Asserting only the with-ledger result would pass against
    a planner that ignored the file entirely, which is the exact
    guard-that-cannot-fire shape the wave spent 2026-08-11 removing.
    """

    ISSUES = [
        {"number": 52, "title": "compiler fix", "body": "work", "state": "OPEN"},
        {"number": 60, "title": "cache evict", "body": "work", "state": "OPEN"},
        {"number": 61, "title": "holder", "body": "Serialized-resource: migration-0009", "state": "OPEN"},
    ]

    def _plan(self, tmp: Path, *extra: str):
        issues = tmp / "issues.json"
        issues.write_text(json.dumps(self.ISSUES))
        proc = subprocess.run(
            ["python3", str(PLANNER), str(issues), *extra],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc

    def test_a_recorded_hold_makes_the_planner_exit_4(self, tmp_path: Path):
        control = self._plan(tmp_path, "--in-flight", "52")
        assert control.returncode == 0, "control: no ledger, no conflict"

        _run(tmp_path, "record", "--wave", WAVE, stdin="GATE: HOLD #52 behind #56 migration first\n")
        ledger = tmp_path / "wave" / WAVE / "verdicts.json"

        withled = self._plan(tmp_path, "--in-flight", "52", "--verdicts", str(ledger))
        assert withled.returncode == 4, (
            "the token must change planner behaviour, not just a log line"
        )
        conflicts = json.loads(withled.stdout)["verdict_conflicts"]
        assert conflicts[0]["issue"] == 52
        assert conflicts[0]["ruling"] == "hold"

    def test_a_recorded_serializes_marker_surfaces_contention(self, tmp_path: Path):
        """#60's body never claims the migration - the CONDITION did. Without
        the ledger the collision with #61 is invisible; with it the planner
        names both issues.
        """
        control = self._plan(tmp_path, "--in-flight", "60,61")
        assert json.loads(control.stdout)["serialized_resources"] == {}

        body = "GATE: GO-WITH-CONDITIONS #60\n  - evict stale entries\n  serializes: migration-0009\n"
        _run(tmp_path, "record", "--wave", WAVE, stdin=body)
        ledger = tmp_path / "wave" / WAVE / "verdicts.json"

        withled = self._plan(tmp_path, "--in-flight", "60,61", "--verdicts", str(ledger))
        assert json.loads(withled.stdout)["serialized_resources"] == {
            "migration-0009": [60, 61]
        }


# --------------------------------------------------------------------------
# The mailbox gate: a broken transition cannot be DELIVERED.
# --------------------------------------------------------------------------


@requires_bash
class TestMailboxRefusesMalformedTransitions:
    def _send(self, tmp: Path, body: str, *extra: str, script: Path | None = None):
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp / "mb")
        return subprocess.run(
            [
                "bash",
                str(script or MAILBOX),
                "send",
                "--to",
                "worker-a",
                "--wave",
                WAVE,
                "--body",
                body,
                *extra,
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    def test_malformed_transition_is_refused_with_exit_6(self, tmp_path: Path):
        proc = self._send(tmp_path, "MERGE: AUTHORIZED #701 when CI passes")
        assert proc.returncode == 6
        assert "FLOW_MAILBOX: refused" in proc.stdout

    def test_a_refused_send_writes_nothing(self, tmp_path: Path):
        """The refusal must leave the box untouched: a partially-delivered
        message would be worse than either outcome.
        """
        self._send(tmp_path, "MERGE: AUTHORIZED #701 when CI passes")
        box = tmp_path / "mb" / WAVE / "outbox-worker-a.md"
        assert not box.exists()

    def test_a_valid_transition_delivers(self, tmp_path: Path):
        proc = self._send(
            tmp_path,
            "MERGE: AUTHORIZED #701 when ci/woodpecker/pr/woodpecker reports success",
        )
        assert proc.returncode == 0, proc.stderr
        assert "FLOW_MAILBOX: sent" in proc.stdout

    def test_prose_always_delivers(self, tmp_path: Path):
        proc = self._send(tmp_path, "Verify against the tree before you start.")
        assert proc.returncode == 0
        assert "FLOW_MAILBOX: sent" in proc.stdout

    def test_no_lexicon_is_the_escape(self, tmp_path: Path):
        proc = self._send(tmp_path, "MERGE: AUTHORIZED #701 when CI passes", "--no-lexicon")
        assert proc.returncode == 0
        assert "FLOW_MAILBOX: sent" in proc.stdout

    def test_a_missing_validator_fails_open(self, tmp_path: Path):
        """A wave must never stall because its linter is unavailable - that is
        the #676 undelivered-assignment failure wearing a different hat.
        """
        lone = tmp_path / "lone"
        lone.mkdir()
        shutil.copy(MAILBOX, lone / "flow-wave-mailbox.sh")
        proc = self._send(
            tmp_path,
            "MERGE: AUTHORIZED #701 when CI passes",
            script=lone / "flow-wave-mailbox.sh",
        )
        assert proc.returncode == 0, "delivery must not depend on the validator existing"
        assert "FLOW_MAILBOX: sent" in proc.stdout

    def test_a_broken_validator_fails_open(self, tmp_path: Path):
        broke = tmp_path / "broke"
        broke.mkdir()
        shutil.copy(MAILBOX, broke / "flow-wave-mailbox.sh")
        stub = broke / "flow-wave-lexicon.sh"
        stub.write_text("#!/usr/bin/env bash\nexit 2\n")
        stub.chmod(0o755)
        proc = self._send(
            tmp_path,
            "MERGE: AUTHORIZED #701 when CI passes",
            script=broke / "flow-wave-mailbox.sh",
        )
        assert proc.returncode == 0
        assert "FLOW_MAILBOX: sent" in proc.stdout
        assert "not a refusal" in proc.stderr


@requires_bash
class TestUsage:
    def test_unknown_verb_is_a_usage_error(self, tmp_path: Path):
        proc = _run(tmp_path, "judge", stdin="")
        assert proc.returncode == 2
        assert "unknown verb" in proc.stderr

    def test_help_documents_the_vocabulary(self, tmp_path: Path):
        proc = _run(tmp_path, "--help")
        assert proc.returncode == 0
        for token in ("GATE:", "LANE:", "MERGE:", "STATE:", "PUSHBACK", "LEDGER"):
            assert token in proc.stdout

    def test_help_is_not_truncated(self, tmp_path: Path):
        """#686: a hand-counted `sed 2,NNp` truncates as the header grows, so
        this helper uses a self-terminating range. Pin the last Env entry.
        """
        proc = _run(tmp_path, "--help")
        assert "FLOW_WAVE_NOW" in proc.stdout

    def test_an_invalid_wave_name_is_refused(self, tmp_path: Path):
        proc = _run(tmp_path, "record", "--wave", "../escape", stdin="GATE: GO #1 x\n")
        assert proc.returncode == 2
        assert "invalid wave name" in proc.stderr


# --------------------------------------------------------------------------- #
# #989 - MERGE: PRIORITY, and the verbs refused because they read as inverses
# --------------------------------------------------------------------------- #


def test_merge_priority_records_the_pr_that_goes_first(tmp_path: Path) -> None:
    out = _validate(tmp_path, "MERGE: PRIORITY #982 overtaken four times, oldest PR in the wave\n")
    assert "FLOW_LEXICON: ok" in out.stdout, out.stdout
    assert "MERGE: PRIORITY #982" in out.stdout, out.stdout


def test_merge_priority_without_an_argument_is_refused(tmp_path: Path) -> None:
    """The argument is mandatory for the same reason PUSHBACK's is.

    This preempts every other worker's merge in the wave. A scheduling decision
    with that blast radius must not be skimmable as a bare token.
    """
    out = _validate(tmp_path, "MERGE: PRIORITY #982\n")
    assert "FLOW_LEXICON: invalid" in out.stdout, out.stdout
    assert "must state WHY" in out.stdout + out.stderr


def test_merge_hold_is_refused_because_it_reads_as_its_own_inverse(tmp_path: Path) -> None:
    """The READING control, not a parsing one.

    `MERGE: AUTHORIZED #N` names its subject, so by exact parallel a reader meets
    `MERGE: HOLD #982` and derives "hold #982" - the precise inverse, since #982
    is the one PR NOT held. This repo already owns that specimen: a lane fence
    written as "explicitly NOT yours" was read as its own grant, which is why
    `LANE: GRANT` must name the paths it grants.

    Refused BY NAME rather than falling through to "unknown verb", because the
    author of such a line has the right intent and the wrong token, and a generic
    refusal would not tell them which.
    """
    for verb in ("HOLD", "BLOCK", "FREEZE"):
        out = _validate(tmp_path, f"MERGE: {verb} #982 until it lands\n")
        assert "FLOW_LEXICON: invalid" in out.stdout, (verb, out.stdout)
        assert "reads as its own inverse" in out.stdout + out.stderr, (verb, out.stdout)
        assert "MERGE: PRIORITY" in out.stdout + out.stderr, (verb, out.stdout)


def test_merge_authorized_is_unchanged(tmp_path: Path) -> None:
    """The existing verb must not regress: this added a sibling, not a rewrite."""
    out = _validate(
        tmp_path,
        "MERGE: AUTHORIZED #701 when ci/woodpecker/pr/woodpecker reports success\n",
    )
    assert "FLOW_LEXICON: ok" in out.stdout, out.stdout
    assert "MERGE: AUTHORIZED #701" in out.stdout, out.stdout


def test_an_unknown_merge_verb_names_both_transitions(tmp_path: Path) -> None:
    out = _validate(tmp_path, "MERGE: SOMETHING #1 whatever\n")
    assert "FLOW_LEXICON: invalid" in out.stdout, out.stdout
    assert "AUTHORIZED and PRIORITY" in out.stdout + out.stderr, out.stdout


# --------------------------------------------------------------------------
# #1026 - `LANE: EXTEND` named the inverse of the mechanism
# --------------------------------------------------------------------------


@requires_bash
def test_lane_extend_is_refused_because_the_registry_replaces(tmp_path: Path) -> None:
    """The NEGATIVE CONTROL for the verb change, and the reading control.

    The registry's ``--files`` REPLACES a role's lane wholesale, so a role
    re-registered on an "EXTEND" loses every path the new list omits - at the
    moment it is most likely to have just merged the file. A sender who reads the
    token as written therefore produces the exact opposite of what they intend.
    It fired twice in one day, the second time by an orchestrator who had
    reported the first occurrence two hours earlier.

    Refused BY NAME rather than through the unknown-verb arm, exactly as
    ``MERGE: HOLD`` is: the author of such a line has the right intent and the
    wrong token, and a generic "not a verb" would not tell them that the thing
    they want does not exist. The assertion is on the MESSAGE naming the
    mechanism, because that is the half that corrects the belief.
    """
    out = _validate(tmp_path, "LANE: EXTEND worker-a src/x.py\n")
    assert "FLOW_LEXICON: invalid" in out.stdout, out.stdout
    assert out.returncode == 1, out.stdout
    blob = out.stdout + out.stderr
    assert "REPLACES" in blob, blob
    assert "LANE: SET" in blob, blob
    # NOT the generic arm - if EXTEND ever falls through to it, this is what
    # notices, and the refusal alone would not.
    assert "unknown LANE verb" not in blob, blob


@requires_bash
def test_lane_set_is_accepted(tmp_path: Path) -> None:
    """The other side of the control (ADR 0008).

    A validator that refused every lane verb would satisfy the test above and
    tell us nothing. ``SET`` is the honest spelling of what the registry does, so
    it must PASS - and be traced, so the acceptance is observable rather than
    merely non-fatal.
    """
    out = _validate(tmp_path, "LANE: SET worker-a src/x.py,src/y.py\n")
    assert "FLOW_LEXICON: ok" in out.stdout, out.stdout
    assert out.returncode == 0, out.stdout
    assert "SET worker-a" in out.stdout, out.stdout


@requires_bash
def test_lane_grant_is_unchanged(tmp_path: Path) -> None:
    """``GRANT`` is a published token used across wave.md and the mailbox suite.

    #1026 added a precise spelling; it did not retire the established one, and a
    wave mid-flight must not start failing on messages it was already sending.
    """
    out = _validate(tmp_path, "LANE: GRANT worker-a src/x.py\n")
    assert "FLOW_LEXICON: ok" in out.stdout, out.stdout
    assert "GRANT worker-a src/x.py" in out.stdout, out.stdout


# --------------------------------------------------------------------------- #
# #980 - a QUOTED token is not an ISSUED one
#
# THE SPECIMEN. An orchestrator drafted a message whose entire purpose was to
# WITHDRAW a merge authorisation carrying an underspecified predicate. The draft
# quoted the bad line verbatim, indented two spaces, with prose around it saying
# it was wrong. `validate` reported a live `MERGE: AUTHORIZED #243` - a fresh
# grant of merge authority under the exact predicate being withdrawn. The same
# shape applied to `GATE: HOLD` blocks the planner on a phantom hold whose
# recorded `reason` is the quoted text, which reads as authentic to whoever
# investigates it later.
#
# THE TWO ARMS (ADR 0008). Every test below that asserts a token does NOT take
# effect is paired with one asserting the SAME token still does at column 0.
# Without the second arm a validator that refused or ignored everything would
# satisfy the first, and this file would be measuring nothing - the exact
# anti-decoration failure the suite docstring is about. The arms are written
# next to each other rather than in separate classes so removing one is visible.
# --------------------------------------------------------------------------- #


#: Arm A from the issue, verbatim: prose that RETRACTS the very hold it quotes.
#: Pre-fix this recorded `{"issue":999,"ruling":"hold",...}` - a hold on #999
#: derived from a message which says in prose that no hold stands on #999.
RETRACTION_INDENTED = (
    "Retrospective. Earlier I wrongly wrote:\n"
    "\n"
    "  GATE: HOLD #999 behind #998\n"
    "\n"
    "That was my error and I am retracting it. No hold stands on #999.\n"
)

#: The same retraction, quoting properly.
RETRACTION_QUOTED = (
    "Retrospective. Earlier I wrongly wrote:\n"
    "\n"
    "> GATE: HOLD #999 behind #998\n"
    "\n"
    "That was my error and I am retracting it. No hold stands on #999.\n"
)


def _citations(proc: subprocess.CompletedProcess[str]) -> list[str]:
    return [
        ln.split("=", 1)[1]
        for ln in proc.stdout.splitlines()
        if ln.startswith("FLOW_LEXICON_CITATION=")
    ]


@requires_bash
class TestAnIndentedTokenIsRefusedRatherThanGuessed:
    """The ambiguous shape, and why it REFUSES instead of picking a side.

    Both silent readings are wrong. Read as issued it is the defect above. Read
    as cited it silently DROPS a real transition typed with a stray leading
    space - and a dropped ``GATE: HOLD`` fails OPEN, letting a wave start an
    issue somebody is holding, which is the worse direction. A refusal is the
    only disposition that cannot fail open either way.
    """

    def test_the_field_specimen_is_refused(self, tmp_path: Path):
        proc = _validate(tmp_path, RETRACTION_INDENTED)
        assert proc.returncode == 1, proc.stdout
        assert _verdict(proc) == "invalid", proc.stdout
        assert _detail(proc, "GATES") == "0", proc.stdout

    def test_the_refusal_names_both_remedies(self, tmp_path: Path):
        """The author of an indented token has a definite intention, and which
        one it was is the single fact the parser cannot recover. A refusal that
        named only one remedy would push every such line to that side - which
        is how a teaching message becomes a transition, or a transition
        becomes prose.
        """
        proc = _validate(tmp_path, RETRACTION_INDENTED)
        blob = proc.stdout + proc.stderr
        assert "line 3:" in blob, blob
        assert "remove the leading whitespace" in blob, blob
        assert "'> '" in blob, blob
        assert "fenced" in blob, blob

    def test_it_records_nothing(self, tmp_path: Path):
        """THE RED ARM, and the one that fails on the pre-fix code.

        Run against ``scripts/flow-wave-lexicon.sh`` before #980 this body
        exits 0 with ``FLOW_LEXICON_RECORDED=1`` and writes a hold on #999 into
        ``verdicts.json``. `validate` only reports; `record` MUTATES, so the
        arm that matters is asserted against the file on disk, not the verdict.
        """
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin=RETRACTION_INDENTED)
        assert proc.returncode == 1, proc.stdout
        assert not (tmp_path / "wave" / WAVE / "verdicts.json").exists(), (
            "a message that retracts a hold in prose wrote that hold to the ledger"
        )

    def test_the_same_token_at_column_zero_still_issues(self, tmp_path: Path):
        """THE OTHER ARM. A parser that refused every GATE line would satisfy
        every assertion above and tell us nothing at all.
        """
        proc = _validate(tmp_path, "GATE: HOLD #999 behind #998 schema first\n")
        assert proc.returncode == 0, proc.stdout
        assert _verdict(proc) == "ok", proc.stdout
        assert _transitions(proc) == ["GATE: HOLD #999"], proc.stdout

    def test_a_reserved_word_indented_but_not_a_token_is_still_prose(
        self, tmp_path: Path
    ):
        """The refusal is scoped to lines that OPEN a reserved token.

        An indented sentence merely mentioning one stays prose, or every
        bulleted design discussion of the lexicon becomes unsendable.
        """
        proc = _validate(
            tmp_path,
            "Options:\n"
            "  - whether GATE: GO should carry a reason at all\n"
            "  - whether LANE: GRANT is the right name\n",
        )
        assert proc.returncode == 0, proc.stdout
        assert _verdict(proc) == "none", proc.stdout


@requires_bash
class TestCitationIsInertButNeverSilent:
    """Fenced and ``>``-quoted tokens are references, not transitions.

    ``>`` already failed to parse before #980 - ``trim`` left the ``>`` in place
    so the ``GATE:*`` match missed - but accidentally, undocumented, and
    UNREPORTED. The reporting is the half that makes skipping safe: inert and
    dropped produce identical silence, and the whole argument for having a skip
    at all is that the sender is told which one happened.
    """

    def test_a_fenced_token_is_a_citation(self, tmp_path: Path):
        proc = _validate(
            tmp_path,
            "Earlier ruling, for reference:\n\n```\nGATE: HOLD #999 behind #998\n```\n",
        )
        assert proc.returncode == 0, proc.stdout
        assert _verdict(proc) == "none", proc.stdout
        assert _transitions(proc) == [], proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_a_quoted_token_is_a_citation(self, tmp_path: Path):
        proc = _validate(tmp_path, RETRACTION_QUOTED)
        assert proc.returncode == 0, proc.stdout
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_the_citation_names_its_line_and_context(self, tmp_path: Path):
        """A count alone would not let a sender find the line, and the count is
        what they will read first. The context word is what tells them WHICH
        thing they did, so the remedy is obvious without re-reading the rule.
        """
        proc = _validate(tmp_path, RETRACTION_QUOTED)
        assert _citations(proc) == ["quote line 3: GATE: HOLD #999 behind #998"], (
            proc.stdout
        )

    def test_a_fenced_citation_names_the_fence(self, tmp_path: Path):
        proc = _validate(
            tmp_path, "Ref:\n\n```\nMERGE: AUTHORIZED #243 when CI passes\n```\n"
        )
        assert _citations(proc) == [
            "fence line 4: MERGE: AUTHORIZED #243 when CI passes"
        ], proc.stdout

    def test_a_cited_malformed_token_is_not_refused_either(self, tmp_path: Path):
        """Quoting a token BECAUSE it is wrong is the retraction use case.

        The predicate ``when CI passes`` is refused when issued (it is the
        VAGUE_PREDICATES specimen), and must NOT be refused when cited, or the
        channel still cannot carry the message that corrects it.
        """
        proc = _validate(
            tmp_path,
            "Your authorisation was underspecified:\n\n"
            "> MERGE: AUTHORIZED #243 when CI passes\n\n"
            "Name the pipeline. Re-send it against ci/woodpecker/pr/woodpecker.\n",
        )
        assert proc.returncode == 0, proc.stdout
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "ERRORS") == "0", proc.stdout

    def test_the_same_tokens_uncited_still_take_effect(self, tmp_path: Path):
        """THE OTHER ARM for this class, stated once over both contexts."""
        proc = _validate(
            tmp_path,
            "GATE: HOLD #999 behind #998 schema first\n"
            "MERGE: AUTHORIZED #243 when ci/woodpecker/pr/woodpecker reports success\n",
        )
        assert _verdict(proc) == "ok", proc.stdout
        assert _detail(proc, "TRANSITIONS") == "2", proc.stdout
        assert _detail(proc, "CITATIONS") == "0", proc.stdout

    def test_record_says_why_it_found_no_verdict(self, tmp_path: Path):
        """"You wrote no gate" and "your gate was read as a citation" are
        different diagnoses, and the second is the one somebody will hit.
        """
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin=RETRACTION_QUOTED)
        assert proc.returncode == 1, proc.stdout
        assert "read as CITATIONS" in proc.stderr, proc.stderr
        assert not (tmp_path / "wave" / WAVE / "verdicts.json").exists()


@requires_bash
class TestFenceDetectionHoldsAtTheEdges:
    def test_a_tilde_fence_cites_too(self, tmp_path: Path):
        proc = _validate(tmp_path, "Ref:\n\n~~~\nGATE: GO #701 fine\n~~~\n")
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_an_info_string_still_opens_a_fence(self, tmp_path: Path):
        proc = _validate(tmp_path, "Ref:\n\n```text\nGATE: GO #701 fine\n```\n")
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_a_fence_is_closed_only_by_its_own_character(self, tmp_path: Path):
        """A ``~~~`` SHOWN inside a backtick block must not close it.

        If it did, the very next line would re-arm the defect - and a message
        demonstrating one fence style inside another is exactly the shape a
        teaching message takes.
        """
        body = "```\n~~~\nGATE: GO #701 still inside the fence\n```\n"
        proc = _validate(tmp_path, body)
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout
        assert _detail(proc, "TRANSITIONS") == "0", proc.stdout

    def test_a_reopened_fence_does_not_swallow_the_text_between(
        self, tmp_path: Path
    ):
        """Between two fenced citations, a column-0 token still ISSUES.

        The state machine has to CLOSE, not merely open. A fence tracker that
        never cleared would turn every later transition into a citation, which
        is the fail-open this whole change is careful about.
        """
        body = (
            "```\nGATE: HOLD #1 behind #2\n```\n"
            "\nSo, ruling:\n\n"
            "GATE: GO #701 the quoted hold above is withdrawn\n"
            "\n```\nGATE: HOLD #3 behind #4\n```\n"
        )
        proc = _validate(tmp_path, body)
        assert _verdict(proc) == "ok", proc.stdout
        assert _transitions(proc) == ["GATE: GO #701"], proc.stdout
        assert _detail(proc, "CITATIONS") == "2", proc.stdout

    def test_an_unterminated_fence_reports_every_token_it_swallows(
        self, tmp_path: Path
    ):
        """THE NAMED RISK, made checkable rather than described.

        A stray opening fence runs to EOF and silences every later token - the
        fail-open direction in miniature. It is tolerated because each swallowed
        token is REPORTED: the sender sees the tokens named as citations rather
        than inferring the loss from a transition that never arrived. If this
        assertion is ever relaxed, the reversal trigger recorded in the script
        header applies.
        """
        body = "Here is the shape:\n\n```\nGATE: GO #701 approved\nLANE: GRANT worker-a src/x.py\n"
        proc = _validate(tmp_path, body)
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "CITATIONS") == "2", proc.stdout
        assert _citations(proc) == [
            "fence line 4: GATE: GO #701 approved",
            "fence line 5: LANE: GRANT worker-a src/x.py",
        ], proc.stdout


@requires_bash
@requires_jq
class TestInertContentCannotSupplyALiveTokensFields:
    """The continuation grammar is where a citation can still change a RULING.

    ``- <condition>`` and ``serializes: <marker>`` lines beneath a token become
    that token's recorded ``reason`` and ``adds_serialized``, and the planner
    unions the latter into ``serialized_resources``. So content that is inert as
    a TRANSITION is not automatically inert as a FIELD, and the first cut of
    #980 missed exactly that: making a citation transparent to block
    continuation let a quoted ruling's conditions and serialization marker land
    in a LIVE gate's ledger entry. Found twice independently - once by reasoning
    about blockquotes, once by the counter-model reviewer about fences - which is
    why both halves are pinned here rather than the one that was noticed first.
    """

    #: The measured specimen. Before the fix this recorded #55 with reason
    #: "rerun the obsolete pipeline" and adds_serialized ["obsolete-lock"],
    #: neither of which appears anywhere in #55's own ruling.
    ABSORB = (
        "GATE: GO #55 approved on its own merits\n"
        "\n"
        "Earlier ruling, quoted for reference only:\n"
        "\n"
        "> GATE: GO-WITH-CONDITIONS #60 obsolete\n"
        "\n"
        "- rerun the obsolete pipeline\n"
        "serializes: obsolete-lock\n"
    )

    def _ledger(self, tmp: Path) -> list[dict]:
        return json.loads((tmp / "wave" / WAVE / "verdicts.json").read_text())

    def test_a_quoted_rulings_fields_do_not_reach_a_live_one(self, tmp_path: Path):
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin=self.ABSORB)
        assert _verdict(proc) == "recorded", proc.stdout + proc.stderr
        entries = self._ledger(tmp_path)
        assert [e["issue"] for e in entries] == [55], entries
        assert entries[0]["reason"] == "approved on its own merits", (
            "a quoted ruling's conditions became the live gate's recorded reason"
        )
        assert "adds_serialized" not in entries[0], (
            "a quoted ruling's serializes: marker entered the live gate's ledger "
            "entry, and the planner serialises the wave on it"
        )

    def test_a_fenced_condition_does_not_satisfy_a_live_conditional(
        self, tmp_path: Path
    ):
        """The counter-model half: no reserved token is involved at all.

        A fenced ``- obsolete condition`` carries no token, so the citation
        classes never see it - it is inert because it is fenced CONTENT. Left as
        ordinary content it silently qualified a conditional approval that
        carried none.
        """
        proc = _validate(
            tmp_path,
            "GATE: GO-WITH-CONDITIONS #60\n\n```\n- obsolete condition\nserializes: obsolete-lock\n```\n",
        )
        assert proc.returncode == 1, proc.stdout
        assert "carries no conditions" in proc.stdout + proc.stderr

    def test_the_refusal_says_why_the_conditions_were_not_read(
        self, tmp_path: Path
    ):
        """A sender looking at conditions RIGHT THERE needs to be told why they
        did not count, or the refusal reads as a parser bug and gets worked
        around rather than fixed.
        """
        proc = _validate(
            tmp_path, "GATE: GO-WITH-CONDITIONS #60\n\n```\n- obsolete condition\n```\n"
        )
        blob = proc.stdout + proc.stderr
        assert "INERT" in blob, blob
        assert "specimen" in blob, blob

    def test_live_conditions_still_qualify_it(self, tmp_path: Path):
        """THE OTHER ARM. A parser that read no conditions from anywhere would
        satisfy both refusals above and break every real conditional approval.
        """
        proc = _run(
            tmp_path,
            "record",
            "--wave",
            WAVE,
            stdin="GATE: GO-WITH-CONDITIONS #60\n\n- real condition\nserializes: migrations/0009\n",
        )
        assert _verdict(proc) == "recorded", proc.stdout + proc.stderr
        entry = self._ledger(tmp_path)[0]
        assert entry["reason"] == "real condition"
        assert entry["adds_serialized"] == ["migrations/0009"]

    def test_an_illustrative_fence_does_not_truncate_the_conditions_after_it(
        self, tmp_path: Path
    ):
        """Fenced content is SKIPPED, not a terminator - the one place the two
        inert classes differ from a citation.

        A closing fence makes the boundary unambiguous, so an example shown
        mid-block has no business ending the block. A quoted TOKEN does end it,
        because the lines under a quoted ruling belong to that ruling; a fence
        with nothing reserved in it makes no such claim.
        """
        proc = _run(
            tmp_path,
            "record",
            "--wave",
            WAVE,
            stdin=(
                "GATE: GO-WITH-CONDITIONS #60\n"
                "\n- rerun the pipeline\n"
                "\n```\nexample output, not a condition\n```\n"
                "\nserializes: migrations/0009\n"
            ),
        )
        assert _verdict(proc) == "recorded", proc.stdout + proc.stderr
        entry = self._ledger(tmp_path)[0]
        assert entry["reason"] == "rerun the pipeline"
        assert entry["adds_serialized"] == ["migrations/0009"]


@requires_bash
class TestFenceClosureIsLengthAware:
    """A fence closes only on its own character, a run at least as long, and
    nothing after it.

    Comparing only the character - the first cut - meant a four-backtick block
    containing a three-backtick example closed one line early, and any
    ```` ```bash ```` info line inside a block closed it. The next reserved token
    was then live again, inside a message whose author can plainly see it is
    fenced. That is the phantom-verdict defect restored by the repair for it,
    which is the failure mode worth a dedicated class.
    """

    def test_a_shorter_run_does_not_close_a_longer_fence(self, tmp_path: Path):
        proc = _validate(
            tmp_path, "````\n```\nGATE: HOLD #999 behind #998\n````\n"
        )
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "TRANSITIONS") == "0", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_a_run_carrying_an_info_string_does_not_close_a_fence(
        self, tmp_path: Path
    ):
        proc = _validate(
            tmp_path, "```\n```bash\nGATE: HOLD #999 behind #998\n```\n"
        )
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "TRANSITIONS") == "0", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_a_matching_run_does_close_it(self, tmp_path: Path):
        """THE OTHER ARM. A fence that never closed would satisfy both tests
        above by swallowing the whole message, and this is what notices.
        """
        proc = _validate(
            tmp_path,
            "````\nGATE: HOLD #1 behind #2\n````\n\nGATE: GO #701 live ruling\n",
        )
        assert _verdict(proc) == "ok", proc.stdout
        assert _transitions(proc) == ["GATE: GO #701"], proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout


@requires_bash
class TestAQuotedTokenInsideAFenceIsStillReported:
    """The reported zero has to mean "I looked and found nothing".

    Inside a fence, reserved-token detection ran before the blockquote prefix was
    stripped, so a fenced ``> GATE: HOLD`` was classified as ordinary fenced
    content: skipped correctly, and reported as ZERO citations. A zero that
    cannot distinguish "no citation here" from "a reserved token I silently
    passed over" defeats the reporting the whole skip depends on - and quoting a
    worker's token back to them inside a fence is a shape this channel is
    explicitly for.
    """

    def test_it_is_counted_and_named(self, tmp_path: Path):
        proc = _validate(
            tmp_path, "Showing what they sent:\n\n```\n> GATE: HOLD #999 behind #998\n```\n"
        )
        assert _detail(proc, "CITATIONS") == "1", proc.stdout
        assert _citations(proc) == ["fence line 4: GATE: HOLD #999 behind #998"], (
            proc.stdout
        )

    def test_ordinary_quoted_prose_in_a_fence_counts_nothing(
        self, tmp_path: Path
    ):
        """THE OTHER ARM. Counting every ``>`` line inside a fence would satisfy
        the test above and make the count meaningless.
        """
        proc = _validate(tmp_path, "```\n> just some quoted prose\n```\n")
        assert _detail(proc, "CITATIONS") == "0", proc.stdout
        assert _verdict(proc) == "none", proc.stdout


@requires_bash
@requires_jq
class TestTheCitationDistinctionReachesThePlanner:
    """The anti-decoration contract applied to #980 specifically.

    Asserting on ``FLOW_LEXICON:`` alone would prove only that a shell script
    prints a word. These two runs feed the REAL planner identical issue data and
    assert its EXIT CODE differs: a hold that was ISSUED blocks the wave, and the
    same hold CITED does not. That difference is the whole value of the change,
    and it is measured at the consumer rather than at the parser.
    """

    ISSUES = [{"number": 52, "title": "compiler fix", "body": "work", "state": "OPEN"}]

    def _plan(self, tmp: Path, *extra: str):
        issues = tmp / "issues.json"
        issues.write_text(json.dumps(self.ISSUES))
        return subprocess.run(
            ["python3", str(PLANNER), str(issues), *extra],
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_an_issued_hold_blocks_and_a_cited_one_does_not(self, tmp_path: Path):
        issued = tmp_path / "issued"
        cited = tmp_path / "cited"
        issued.mkdir()
        cited.mkdir()

        _run(issued, "record", "--wave", WAVE, stdin="GATE: HOLD #52 behind #56 migration first\n")
        issued_ledger = issued / "wave" / WAVE / "verdicts.json"
        assert issued_ledger.exists(), "the issued arm recorded nothing - the control is dead"
        blocked = self._plan(tmp_path, "--in-flight", "52", "--verdicts", str(issued_ledger))
        assert blocked.returncode == 4, blocked.stdout + blocked.stderr

        cited_body = (
            "Retracting what I sent an hour ago:\n"
            "\n"
            "> GATE: HOLD #52 behind #56 migration first\n"
            "\n"
            "#56 merged. No hold stands on #52.\n"
        )
        proc = _run(cited, "record", "--wave", WAVE, stdin=cited_body)
        assert proc.returncode == 1, proc.stdout
        cited_ledger = cited / "wave" / WAVE / "verdicts.json"
        assert not cited_ledger.exists()

        unblocked = self._plan(tmp_path, "--in-flight", "52")
        assert unblocked.returncode == 0, (
            "the retraction must leave the planner able to start #52 - "
            "that is the behaviour the phantom hold took away"
        )


@requires_bash
class TestTheMailboxTellsTheSenderAboutACitation:
    """The report only counts if it reaches a human, and this is the only place
    a sender sees the validator's answer on a SUCCESSFUL send.

    ``send`` discards the validator's stdout on exit 0, so without this the
    ``FLOW_LEXICON_CITATION=`` lines would exist and be seen by nobody - a
    report that is not delivered is the same as no report, and the safety
    argument for skipping rests entirely on it.
    """

    def _send(self, tmp: Path, body: str, *extra: str):
        env = os.environ.copy()
        env["FLOW_WAVE_MAILBOX_DIR"] = str(tmp / "mb")
        return subprocess.run(
            ["bash", str(MAILBOX), "send", "--to", "worker-a", "--wave", WAVE,
             "--body", body, *extra],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

    def test_a_cited_token_delivers_and_is_reported(self, tmp_path: Path):
        proc = self._send(tmp_path, RETRACTION_QUOTED)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "FLOW_MAILBOX: sent" in proc.stdout, proc.stdout
        assert "FLOW_LEXICON_CITATION=quote line 3:" in proc.stderr, proc.stderr
        assert "did NOT take effect" in proc.stderr, proc.stderr

    def test_a_message_with_no_citation_says_nothing_about_them(
        self, tmp_path: Path
    ):
        """The other arm: a NOTE printed on every send is a NOTE nobody reads.

        If this ever starts failing, the report has become ambient and stopped
        distinguishing the case it was added for.
        """
        proc = self._send(tmp_path, "Verify against the tree before you start.")
        assert proc.returncode == 0, proc.stderr
        assert "FLOW_LEXICON_CITATION=" not in proc.stderr, proc.stderr
        assert "did NOT take effect" not in proc.stderr, proc.stderr

    def test_an_indented_token_is_refused_at_send(self, tmp_path: Path):
        """The ambiguous shape never reaches an inbox at all."""
        proc = self._send(tmp_path, RETRACTION_INDENTED)
        assert proc.returncode == 6, proc.stdout + proc.stderr
        assert "FLOW_MAILBOX: refused" in proc.stdout, proc.stdout
        assert not (tmp_path / "mb" / WAVE / "outbox-worker-a.md").exists()


@requires_bash
class TestAFenceDelimiterMustNotBeIndentedContent:
    """A delimiter indented four or more spaces is CONTENT, not a fence.

    Fence detection ran on the TRIMMED line - the same shortcut that made this
    whole class of bug possible - so an indented ``~~~`` inside a block closed it
    early and the next reserved token went live again, reported as a real verdict
    with ZERO citations. The phantom verdict restored by an incomplete repair of
    the phantom verdict, which is why it is pinned rather than left to the
    length-aware check that did not catch it.
    """

    def test_a_four_space_delimiter_does_not_close_a_fence(self, tmp_path: Path):
        proc = _validate(
            tmp_path, "~~~\n    ~~~\nGATE: HOLD #999 behind #998\n~~~\n"
        )
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "TRANSITIONS") == "0", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_a_tab_indented_delimiter_does_not_close_a_fence(self, tmp_path: Path):
        proc = _validate(
            tmp_path, "~~~\n\t~~~\nGATE: HOLD #999 behind #998\n~~~\n"
        )
        assert _verdict(proc) == "none", proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout

    def test_a_three_space_delimiter_still_closes_it(self, tmp_path: Path):
        """THE OTHER ARM, and the boundary itself.

        Rejecting every indented delimiter would satisfy both tests above by
        never closing a fence at all - swallowing the rest of every message that
        contains one. Three spaces is the limit, so three must still work.
        """
        proc = _validate(
            tmp_path,
            "~~~\nGATE: HOLD #1 behind #2\n   ~~~\n\nGATE: GO #701 live ruling\n",
        )
        assert _verdict(proc) == "ok", proc.stdout
        assert _transitions(proc) == ["GATE: GO #701"], proc.stdout
        assert _detail(proc, "CITATIONS") == "1", proc.stdout


@requires_bash
class TestAnEmptyQuoteMarkerIsNotLiveContent:
    """``strip_quote`` cannot tell an empty blockquote from an unquoted line.

    Both strip to ``''``, so a bare ``>`` fell through to live content and a
    ``PUSHBACK`` whose only "argument" was the quote marker passed - exactly the
    skimmed-past-as-agreement failure the mandatory argument exists to prevent.
    The prefix is a property of the LINE; the payload is a separate question, and
    conflating them is what let an empty one count.
    """

    def test_a_bare_quote_marker_is_not_a_pushback_argument(self, tmp_path: Path):
        proc = _validate(tmp_path, "PUSHBACK\n>\n> quoted specimen\n")
        assert proc.returncode == 1, proc.stdout
        assert "carries no argument" in proc.stdout + proc.stderr

    def test_quoted_ledger_sections_do_not_satisfy_it(self, tmp_path: Path):
        proc = _validate(
            tmp_path, "LEDGER\n> delivered:\n> in-scope:\n> residual:\n"
        )
        assert proc.returncode == 1, proc.stdout
        assert "missing section(s)" in proc.stdout + proc.stderr

    def test_a_real_argument_still_passes(self, tmp_path: Path):
        """THE OTHER ARM. A parser that read no continuation content would
        satisfy both refusals above and break every real PUSHBACK.
        """
        proc = _validate(
            tmp_path, "PUSHBACK\nActual objection: the lane fences my own file out.\n"
        )
        assert _verdict(proc) == "ok", proc.stdout
        assert _transitions(proc) == [
            "PUSHBACK: Actual objection: the lane fences my own file out."
        ], proc.stdout

    def test_real_ledger_sections_still_pass(self, tmp_path: Path):
        proc = _validate(
            tmp_path, "LEDGER\ndelivered: the fix\nin-scope: the tests\nresidual: none\n"
        )
        assert _verdict(proc) == "ok", proc.stdout


# --------------------------------------------------------------------------
# ci-concurrency - a checker that COULD NOT RUN is not a checker that looked
# --------------------------------------------------------------------------


#: The shim is the deliverable, not a formality. It is the only thing that
#: separates this fix from code that merely happens to pass on an unloaded
#: machine: it reproduces the CI failure on demand instead of waiting for the
#: agent to be busy enough to produce it again.
_GREP_SHIM = """#!/bin/sh
if [ -n "$SHIM_ALWAYS_FAIL" ]; then
  echo "grep: fork: Resource temporarily unavailable" >&2; exit 127
fi
C="$SHIM_COUNTER"
n=$(cat "$C" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$C"
if [ "$n" = "$SHIM_FAIL_ON" ]; then
  echo "grep: fork: Resource temporarily unavailable" >&2; exit 127
fi
exec %s "$@"
"""

def _assert_ledger_was_actually_examined(proc, context: str) -> None:
    """Positive evidence that the block was PARSED, not merely not-complained-about.

    COUNTER-MODEL REVIEW FOUND THIS IN THIS FILE'S OWN CONTROL, which is this
    issue's defect class committed inside the test for it. Asserting only
    `returncode == 0` and `"missing section" not in stderr` is satisfied by a run
    that never examined anything: make the body-reading `cat` exit 127 and the
    script emits `FLOW_LEXICON: none` with `FLOW_LEXICON_TRANSITIONS=0` and exit
    0 - measured. Every assertion above would have passed on it.

    So a positive case must show the parser REACHED the ledger: verdict `ok` AND
    a LEDGER transition present. "Nothing went wrong" is not evidence that
    anything happened.
    """
    assert proc.returncode == 0, f"{context}: exit {proc.returncode}\n{proc.stderr}"
    assert _verdict(proc) == "ok", (
        f"{context}: verdict {_verdict(proc)!r}, not 'ok' - a run that never "
        f"examined the body reports 'none' and would otherwise pass\n{proc.stderr}"
    )
    kinds = [t.split(":", 1)[0].split()[0] for t in _transitions(proc)]
    assert "LEDGER" in kinds, (
        f"{context}: no LEDGER transition was recorded, so the section checks "
        f"were never reached: {_transitions(proc)}"
    )


_LEDGER_BODY = (
    "LEDGER\n"
    "delivered: the parser\n"
    "in-scope: the mailbox wiring\n"
    "residual: register.md, filed as #706\n"
)


def _with_failing_grep(tmp: Path, body: str, **shim_env: str):
    """Run `validate` with a `grep` that cannot exec, and return the process."""
    real_grep = shutil.which("grep")
    assert real_grep, "precondition: a real grep must exist to delegate to"
    shim_dir = tmp / "shim"
    shim_dir.mkdir(exist_ok=True)
    shim = shim_dir / "grep"
    shim.write_text(_GREP_SHIM % real_grep, encoding="utf-8")
    shim.chmod(0o755)

    body_file = tmp / "body.md"
    body_file.write_text(body, encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    env["SHIM_COUNTER"] = str(tmp / "counter")
    env.update(shim_env)
    return subprocess.run(
        ["bash", str(LEXICON), "validate", "--body-file", str(body_file)],
        capture_output=True, text=True, env=env,
    )


@requires_bash
class TestACheckerThatCouldNotRunIsNotAVerdict:
    """The ci-concurrency defect, and the red case that proves it is gone.

    MEASURED IN CI on 2026-09-23: pipelines 2504 (push) and 2505 (pull_request)
    built the SAME commit, their `validate` steps started in the SAME SECOND on
    one agent running WOODPECKER_MAX_WORKFLOWS=2, and 2505 failed with
    `LEDGER is missing section(s): delivered` on a body that plainly contained
    it. `push` is not a required check; `ci/woodpecker/pr/woodpecker` is the
    only entry in branch protection - so the run that failed is the one that
    governs the merge.

    The cause was three `grep` processes, one per section. `grep` reports "no
    match" with exit 1, and a `grep` that CANNOT BE STARTED also exits
    non-zero, so `|| missing=...` fired on a section that was present.

    ONE section, never three, is the signature that identified it: a truncated
    or malformed block loses all three, so a single missing section means one
    check failed while its two siblings succeeded on the same input microseconds
    apart.
    """

    @pytest.mark.parametrize(
        "fail_on,would_have_been",
        [("1", "delivered"), ("2", "in-scope"), ("3", "residual")],
    )
    def test_a_grep_that_cannot_exec_no_longer_invents_a_missing_section(
        self, tmp_path: Path, fail_on: str, would_have_been: str
    ):
        """Each of the three calls, because the failure picked one arbitrarily.

        Before the fix these produced exactly the CI text. Asserting only the
        exit code would let a version that reports a DIFFERENT false section
        pass, so the section name is asserted absent from the output too.
        """
        proc = _with_failing_grep(tmp_path, _LEDGER_BODY, SHIM_FAIL_ON=fail_on)
        _assert_ledger_was_actually_examined(proc, f"grep call {fail_on} failing")
        assert "missing section" not in proc.stderr, proc.stderr
        assert would_have_been not in proc.stderr, (
            f"{would_have_been!r} still named: the conflation survives for that call"
        )

    def test_the_whole_block_survives_grep_being_entirely_unavailable(
        self, tmp_path: Path
    ):
        """The all-three shape, which is what a truncated body looks like.

        Kept distinct from the per-call cases above because the two shapes are
        the diagnostic: one section means a failed fork, three means the body
        never arrived. A fix that handled only the first would pass those three
        and fail this.
        """
        proc = _with_failing_grep(tmp_path, _LEDGER_BODY, SHIM_ALWAYS_FAIL="1")
        _assert_ledger_was_actually_examined(proc, "grep entirely unavailable")
        assert "missing section" not in proc.stderr, proc.stderr


@requires_bash
class TestTheMatcherStillAcceptsAndRejectsWhatItDid:
    """CONDITION (ii): the translation changed the ENGINE, not the meaning.

    `grep -E` and bash `=~` are both POSIX ERE and the pattern is byte-identical,
    but that is an argument, not evidence. These are the spellings the grep
    implementation accepted and rejected, pinned from it BEFORE the change, so a
    silent change in which ledgers validate fails here.

    The could-not-run tests above would pass throughout such a change: they
    exercise a different axis entirely.
    """

    ACCEPTED = [
        "delivered:", "  delivered:", "\tdelivered:", "- delivered:",
        "* delivered:", "-delivered:", "  -  delivered  :", "DELIVERED:",
        "Delivered :", "delivered  :",
    ]
    REJECTED = [
        "-- delivered:", "** delivered:", "# delivered:", "xdelivered:",
        "delivered", "delivered x:", "+ delivered:",
    ]

    @pytest.mark.parametrize("opener", ACCEPTED)
    def test_previously_accepted_openers_are_still_accepted(self, tmp_path, opener):
        body = f"LEDGER\n{opener} the parser\nin-scope: x\nresidual: none\n"
        proc = _validate(tmp_path, body)
        #: Positive evidence, not merely an absent complaint: an unrelated
        #: process failure leaves stderr without "delivered" too.
        _assert_ledger_was_actually_examined(proc, f"accepted opener {opener!r}")
        assert "delivered" not in proc.stderr, (
            f"{opener!r} was accepted by the grep implementation and is now rejected"
        )

    @pytest.mark.parametrize("opener", REJECTED)
    def test_previously_rejected_openers_are_still_rejected(self, tmp_path, opener):
        body = f"LEDGER\n{opener} the parser\nin-scope: x\nresidual: none\n"
        proc = _validate(tmp_path, body)
        #: The rejected direction carries its own positive evidence - the
        #: diagnostic names the section - but the verdict is asserted too, so a
        #: run that failed for an unrelated reason cannot satisfy it.
        assert _verdict(proc) == "invalid", (
            f"{opener!r}: verdict {_verdict(proc)!r}, not 'invalid'\n{proc.stderr}"
        )
        assert "missing section(s): delivered" in proc.stderr, (
            f"{opener!r} was rejected by the grep implementation and is now accepted"
        )


@requires_bash
class TestTheControlsThemselvesCanFail:
    """Tests of the tests, because both were found unable to fail.

    Counter-model review established two ways this file's own controls were
    vacuous, and each is pinned here so the repair cannot silently rot back.
    """

    def test_a_run_that_never_examined_the_body_does_not_satisfy_our_guard(
        self, tmp_path: Path
    ):
        """The exact input that satisfied the old assertions.

        With the body-reading `cat` unable to exec, the script emits
        `FLOW_LEXICON: none` with zero transitions and exit 0. The previous
        assertions - exit 0, and "missing section" absent from stderr - were
        both true of it. `_assert_ledger_was_actually_examined` must reject it,
        and this asserts that it does rather than trusting that it would.
        """
        shim_dir = tmp_path / "catshim"
        shim_dir.mkdir()
        (shim_dir / "cat").write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
        (shim_dir / "cat").chmod(0o755)
        body_file = tmp_path / "body.md"
        body_file.write_text(_LEDGER_BODY, encoding="utf-8")

        env = dict(os.environ)
        env["PATH"] = f"{shim_dir}:{env['PATH']}"
        proc = subprocess.run(
            ["bash", str(LEXICON), "validate", "--body-file", str(body_file)],
            capture_output=True, text=True, env=env,
        )

        #: The shape that fooled the old control: clean exit, no complaint.
        assert proc.returncode == 0
        assert "missing section" not in proc.stderr

        #: And the guard refuses it anyway. If this stops raising, every
        #: positive case in this file has gone vacuous again.
        with pytest.raises(AssertionError):
            _assert_ledger_was_actually_examined(proc, "unreadable body")

    @pytest.mark.parametrize(
        "opener,accepted,because",
        [
            # U+0130 LATIN CAPITAL LETTER I WITH DOT ABOVE.
            ("DEL\u0130VERED:", False,
             "tr leaves it alone, so the section never matched - unrestricted "
             "bash ${x,,} folds it to ASCII 'i' and would ACCEPT this"),
            ("DELIVERED:", True, "plain ASCII uppercase always matched"),
        ],
    )
    def test_case_folding_is_ascii_only_exactly_as_tr_was(
        self, tmp_path: Path, opener: str, accepted: bool, because: str
    ):
        """CONDITION (ii) with the population the first pin was missing.

        The 17 spellings pinned from the grep implementation were ALL ASCII, so
        they could not see that `${x,,}` is locale-aware where
        `tr '[:upper:]' '[:lower:]'` is not. Measured under LC_ALL=C.utf8:
        tr yields `del\u0130vered`, `${x,,}` yields `delivered`, and a body
        using that spelling flipped from `invalid` to `ok`. The fix restricts
        the fold with `${x,,[A-Z]}`; this is the case that distinguishes them.

        The pin was sound and its POPULATION was too narrow - which is the more
        useful lesson than the encoding detail.
        """
        body = f"LEDGER\n{opener} the parser\nin-scope: x\nresidual: none\n"
        env = dict(os.environ)
        env["LC_ALL"] = "C.utf8"
        body_file = tmp_path / "body.md"
        body_file.write_text(body, encoding="utf-8")
        proc = subprocess.run(
            ["bash", str(LEXICON), "validate", "--body-file", str(body_file)],
            capture_output=True, text=True, env=env,
        )
        if accepted:
            _assert_ledger_was_actually_examined(proc, f"{opener!r} ({because})")
        else:
            assert "missing section(s): delivered" in proc.stderr, (
                f"{opener!r} should NOT match: {because}\n{proc.stderr}"
            )


# --------------------------------------------------------------------------
# #1189: the ledger's record of a ruling must not be narrower than the ruling.
#
# Defect 1 - a HOLD whose reason sits in prose beneath the token was recorded
# as `GATE: HOLD (no reason given)` while `record` printed success. The fix is a
# REFUSAL, not a wider harvest: widening would let a HOLD take any text beneath
# it as its reason, which is a different defect.
#
# Defect 2 (producer half) - a ruling on work that deliberately has no issue
# could not be formed at all, because the subject had to be `#N`. The consumer
# half (flow-wave-plan.py reading `subject`) landed in #1223.
# --------------------------------------------------------------------------


@requires_bash
class TestAHoldMustCarryItsReason:
    def test_a_reasonless_hold_is_refused(self, tmp_path: Path):
        proc = _validate(tmp_path, "GATE: HOLD #52 behind #56\n")
        assert proc.returncode == 1, proc.stdout
        assert _verdict(proc) == "invalid", proc.stdout
        assert "must state WHY" in proc.stdout + proc.stderr

    def test_prose_beneath_a_hold_is_refused_not_recorded_as_no_reason(
        self, tmp_path: Path
    ):
        """The field specimen: a five-line argument typed under the token was
        stored as ``(no reason given)`` and ``record`` said ``recorded``.
        """
        body = (
            "GATE: HOLD #52 behind #56\n"
            "\n"
            "The migration must land first because the schema\n"
            "changes under it.\n"
        )
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin=body)
        assert proc.returncode == 1, proc.stdout
        assert _verdict(proc) == "invalid", proc.stdout
        assert not (tmp_path / "wave" / WAVE / "verdicts.json").exists()

    def test_the_refusal_names_both_places_a_reason_may_go(self, tmp_path: Path):
        proc = _validate(tmp_path, "GATE: HOLD #52 behind #56\n")
        out = proc.stdout + proc.stderr
        assert "on the token line" in out, out
        assert "'- <reason>'" in out, out

    @requires_jq
    def test_an_inline_reason_is_recorded(self, tmp_path: Path):
        """THE OTHER ARM: a refusal that fired on every HOLD would pass above."""
        proc = _run(
            tmp_path, "record", "--wave", WAVE,
            stdin="GATE: HOLD #52 behind #56 the schema changes under it\n",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        entry = json.loads((tmp_path / "wave" / WAVE / "verdicts.json").read_text())[0]
        assert entry["reason"] == "the schema changes under it"

    @requires_jq
    def test_a_listed_reason_beneath_is_recorded(self, tmp_path: Path):
        proc = _run(
            tmp_path, "record", "--wave", WAVE,
            stdin="GATE: HOLD #52 behind #56\n- the schema changes under it\n",
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        entry = json.loads((tmp_path / "wave" / WAVE / "verdicts.json").read_text())[0]
        assert entry["reason"] == "the schema changes under it"
        assert "no reason given" not in entry["reason"]

    def test_a_reasonless_go_is_still_accepted(self, tmp_path: Path):
        """Scope pin: the refusal is HOLD's. A terse GO is a deliberate shape
        and stays valid; widening the refusal is a separate decision.
        """
        proc = _validate(tmp_path, "GATE: GO #701\n")
        assert _verdict(proc) == "ok", proc.stdout


@requires_bash
class TestAnIssuelessRulingCanBeFormed:
    def test_a_kebab_slug_subject_is_accepted(self, tmp_path: Path):
        proc = _validate(tmp_path, "GATE: GO journal-false-red fix is in lane\n")
        assert _verdict(proc) == "ok", proc.stdout + proc.stderr
        assert _transitions(proc) == ["GATE: GO journal-false-red"], proc.stdout

    @pytest.mark.parametrize(
        "body,because",
        [
            ("GATE: GO 701 looks right\n", "did you mean '#701'"),
            ("GATE: GO approved\n", "must name its subject"),
            ("GATE: GO Journal-False-Red ok\n", "must name its subject"),
            ("GATE: GO -leading-dash ok\n", "must name its subject"),
            # The existing guards still bind a SLUG subject (counter-model red cases).
            ("GATE: HOLD journal-false-red migration first\n", "must name what it waits behind"),
            ("GATE: GO-WITH-CONDITIONS journal-false-red\n", "carries no conditions"),
        ],
    )
    def test_a_subject_that_is_neither_is_refused(
        self, tmp_path: Path, body: str, because: str
    ):
        """A bare number is refused rather than read as a slug or an issue: a
        missing ``#`` must stay LOUD. A single word is refused so ``GATE: GO
        approved`` cannot become a ruling about a subject called "approved".
        """
        proc = _validate(tmp_path, body)
        assert proc.returncode == 1, proc.stdout
        assert because in proc.stdout + proc.stderr, proc.stdout + proc.stderr

    @requires_jq
    def test_record_writes_subject_for_a_slug_and_issue_for_a_number(
        self, tmp_path: Path
    ):
        body = (
            "GATE: GO-WITH-CONDITIONS journal-false-red\n"
            "- keep the fix inside the journal lane\n"
            "\n"
            "GATE: GO #701 evidence checks out\n"
        )
        proc = _run(tmp_path, "record", "--wave", WAVE, stdin=body)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        slug, num = json.loads((tmp_path / "wave" / WAVE / "verdicts.json").read_text())
        assert slug["subject"] == "journal-false-red" and "issue" not in slug, slug
        assert slug["reason"] == "keep the fix inside the journal lane"
        # Existing numeric entries stay byte-shaped as before: `issue`, a number.
        assert num["issue"] == 701 and "subject" not in num, num


@requires_bash
@requires_jq
def test_a_recorded_slug_ruling_does_not_disable_a_recorded_hold(tmp_path: Path):
    """End to end, producer through consumer: the pair #1223 measured by hand.

    Before #1223 one slug entry made the planner reject the whole ledger; before
    this change the lexicon could not WRITE one. Both halves together: the hold
    is still enforced and the slug is counted, not dropped.
    """
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps([
        {"number": 52, "title": "compiler fix", "body": "work", "state": "OPEN"},
    ]))
    body = (
        "GATE: GO journal-false-red in-lane residual, fixed not filed\n"
        "\n"
        "GATE: HOLD #52 behind #56 migration first\n"
    )
    rec = _run(tmp_path, "record", "--wave", WAVE, stdin=body)
    assert rec.returncode == 0, rec.stdout + rec.stderr
    ledger = tmp_path / "wave" / WAVE / "verdicts.json"
    plan = subprocess.run(
        ["python3", str(PLANNER), str(issues), "--in-flight", "52", "--verdicts", str(ledger)],
        capture_output=True, text=True, timeout=60,
    )
    assert plan.returncode == 4, plan.stdout + plan.stderr
    assert json.loads(plan.stdout)["verdict_conflicts"][0]["issue"] == 52
    assert "subject" in plan.stderr + plan.stdout, "the slug ruling must be COUNTED, not silently dropped"


@requires_bash
def test_the_lexicon_control_does_not_excuse_a_crashing_gate(tmp_path: Path):
    """A gate that crashes on every input must not score as UNAVAILABLE.

    ``make negative-controls`` runs with ``--allow-unavailable``, so a crash
    reported as "could not look" would pass the local gate with the lexicon
    broken. It must exit non-zero carrying NEITHER declared signal, which the
    harness scores UNSIGNALLED (counter-model review, #1189).
    """
    runner = ROOT / "controls" / "flow-wave-lexicon" / "run-case.sh"
    case = ROOT / "controls" / "flow-wave-lexicon" / "cases" / "bad-reasonless-hold"
    assert (case / "body.md").is_file(), "precondition: the fixture must be present"
    crash = tmp_path / "crash.sh"
    crash.write_text("exit 1\n")
    proc = subprocess.run(
        ["sh", str(runner), str(case), str(crash)],
        capture_output=True, text=True, timeout=60,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode not in (0, 1, 3), out
    assert "FLOW_WAVE_LEXICON_CONTROL: unavailable" not in out, out
    assert "FLOW_WAVE_LEXICON_CONTROL: finding" not in out, out

    missing = subprocess.run(
        ["sh", str(runner), str(case), str(tmp_path / "absent.sh")],
        capture_output=True, text=True, timeout=60,
    )
    assert missing.returncode == 3, missing.stderr
    assert "FLOW_WAVE_LEXICON_CONTROL: unavailable" in missing.stderr
