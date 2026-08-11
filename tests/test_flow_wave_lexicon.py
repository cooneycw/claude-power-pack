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

WAVE = "testwave"


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
            ("LANE: BLESS worker-a src/x.py", "only GRANT/EXTEND/REVOKE are lane verbs"),
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
