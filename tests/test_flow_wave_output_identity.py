"""The wave helpers print the same bytes as before the #1691 tidy (issue #1691).

`flow-wave-registry.sh`, `flow-wave-mailbox.sh` and `flow-wave-lexicon.sh` are
read by other sessions and other repositories: their verdict lines, detail
lines, usage text and exit codes are an interface. Issue #1691 removes dead
functions and folds exact duplicates in them. "The existing tests still pass"
does not show that such a change printed nothing different, because the
existing tests assert on the lines they care about, not on every line.

THE INSTRUMENT. `tests/fixtures/flow-wave-pre-1691/` holds the three scripts as
they were before the tidy. For each script one fixed scenario - every
subcommand that can be driven without a second live session, including the
usage-error paths - is run twice: once with the snapshot, once with the script
in `scripts/`. Each run gets a fresh staging directory holding the SAME current
neighbours (the helpers source and call their siblings by directory), a fresh
wave directory and a fresh home directory, so the script under comparison is
the only thing that differs. stdout, stderr and the exit code of EVERY step are
then compared line for line.

WHAT IS NORMALISED, and nothing else: the two runs' own temporary paths, and
the values the mailbox takes from the wall clock, each named in `CLOCK_VALUES`
(a send stamp, a box's modification time, and the ages counted from them).
Pids, the session id, the host name and the registry's and lexicon's clock are
pinned through the helpers' test hooks rather than normalised.

EXPECTED DIFFERENCES. A deliberate change of a printed line is listed in
`EXPECTED_DIFFERENCES` as the exact old line and the exact new line. The test
asserts the set of differences found is EXACTLY that list: an unlisted
difference fails, and so does a listed one that no longer appears.

IT CAN FAIL. `test_one_changed_byte_is_reported` builds a copy of the current
registry with one printed byte changed and asserts the same comparison reports
it. To run the comparison by hand against any copy:

    .venv/bin/python -m tests.test_flow_wave_output_identity \\
        flow-wave-registry.sh /path/to/a/changed/copy.sh

which prints each difference and exits 1 when there is one.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SNAPSHOT = ROOT / "tests" / "fixtures" / "flow-wave-pre-1691"

REGISTRY = "flow-wave-registry.sh"
MAILBOX = "flow-wave-mailbox.sh"
LEXICON = "flow-wave-lexicon.sh"

# Every step runs a real helper under `bash`; the helpers need `jq`, `flock`
# and `awk`, and the registry scenario builds a real checkout with `git`.
requires_tools = pytest.mark.skipif(
    shutil.which("bash") is None
    or shutil.which("jq") is None
    or shutil.which("flock") is None
    or shutil.which("awk") is None
    or shutil.which("git") is None,
    reason="requires bash, jq, flock, awk and git on PATH",
)

WAVE = "identity-1691"
SELF_PID = "4242"
OTHER_PID = "5151"
CLAIM_PID = "7171"
HOST = "identity-host"


class Step(NamedTuple):
    """One invocation. `{tmp}` in an argument or value is the run's own directory."""

    name: str
    args: tuple[str, ...]
    stdin: str | None = None
    env: tuple[tuple[str, str], ...] = ()
    cwd: str = "{tmp}"
    #: Run this staged SIBLING instead of the script under comparison - a step
    #: that only builds state the next steps need (a registered address, say).
    helper: str = ""


class Outcome(NamedTuple):
    name: str
    exit_code: int
    stdout: str
    stderr: str


class Difference(NamedTuple):
    """One differing line. `old` or `new` is None for a line only one side has."""

    step: str
    stream: str
    old: str | None
    new: str | None


class Expected(NamedTuple):
    """A deliberate change of one printed line: the exact old and new text."""

    old: str
    new: str


#: Deliberate changes of printed lines, per script. Anything not listed here
#: must be byte-identical; anything listed must actually differ.
EXPECTED_DIFFERENCES: dict[str, frozenset[Expected]] = {
    REGISTRY: frozenset(),
    MAILBOX: frozenset(),
    LEXICON: frozenset(),
}


def _s(
    name: str, *args: str, stdin: str | None = None, cwd: str = "{tmp}", helper: str = "",
    **env: str,
) -> Step:
    return Step(name, args, stdin, tuple(sorted(env.items())), cwd, helper)


W = ("--wave", WAVE)
OTHER = {"CLAUDE_PID": OTHER_PID, "CLAUDE_CODE_SESSION_ID": "identity-other"}
LANE = ("--repo", "{tmp}/repo", "--cwd", "{tmp}/repo", "--branch", "issue-1710-x")

REGISTRY_STEPS: tuple[Step, ...] = (
    # usage and help
    _s("no-arguments"),
    _s("unknown-verb", "frobnicate"),
    _s("help", "--help"),
    _s("help-short", "-h"),
    _s("register-no-role", "register", *W),
    _s("register-wave-missing-value", "register", "w1", "--wave"),
    _s("register-unknown-option", "register", "w1", *W, "--no-such-flag"),
    _s("register-pr-without-base", "register", "w1", *W, "--pr", "55"),
    _s("policy-no-action", "policy", *W),
    _s("policy-set-bad-merge-strict", "policy", "set", *W, "--merge-strict", "perhaps"),
    _s("policy-set-bad-authority", "policy", "set", *W, "--authority", "approved"),
    _s("policy-set-bad-authority-model", "policy", "set", *W, "--authority-model", "anyone"),
    _s("get-no-role", "get", *W),
    _s("verify-no-from", "verify", "w1", *W),
    _s("close-no-wave", "close"),
    _s("lane-check-no-role", "lane-check", *W),
    # an empty registry
    _s("list-empty", "list", *W),
    _s("list-empty-json", "list", *W, "--json"),
    _s("list-empty-any-live", "list", *W, "--any-live"),
    _s("list-empty-with-claim", "list", *W, "--repo", "{tmp}/repo",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{CLAIM_PID}"),
    _s("list-empty-with-claim-json", "list", *W, "--repo", "{tmp}/repo", "--json",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{CLAIM_PID}"),
    _s("list-empty-missing-repo", "list", *W, "--repo", "{tmp}/no-such-repo"),
    _s("get-absent", "get", "w1", *W),
    _s("policy-show-absent", "policy", "show", *W),
    _s("release-absent", "release", "w1", *W),
    _s("close-absent-dry-run", "close", *W, "--dry-run"),
    # policy
    _s("policy-set", "policy", "set", *W, "--driver", "flow:auto", "--authority", "implement",
       "--authority-model", "orchestrator-only", "--gate", "plan", "--ledger", "verdicts",
       "--merge-authority", "orchestrator", "--merge-strict", "yes",
       "--deploy-policy", "none", "--repo", "{tmp}/repo"),
    _s("policy-show", "policy", "show", *W),
    _s("policy-show-json", "policy", "show", *W, "--json"),
    # registration
    _s("register-orchestrator", "register", "orchestrator", *W, "--socket", "uds:{tmp}/socks/9001.sock",
       "--repo", "{tmp}/repo", "--cwd", "{tmp}/repo"),
    _s("register-fresh", "register", "w1", *W, *LANE, "--issue", "1710", "--driver", "codex:auto",
       "--model", "opus", "--permission-mode", "bypassPermissions", "--capacity", "2",
       "--files", "a.py,b.py", "--pr", "55", "--base", "base-1", "--diff", "diff-1", **OTHER),
    _s("register-other-holder-refused", "register", "w1", *W, *LANE, "--issue", "1710",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("register-same-issue", "register", "w1", *W, *LANE, "--issue", "1710", **OTHER),
    _s("register-overtake", "register", "w1", *W, *LANE, "--issue", "1710",
       "--pr", "55", "--base", "base-2", "--diff", "diff-1", **OTHER),
    _s("get-after-rebrief", "get", "w1", *W, FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("register-different-issue", "register", "w1", *W, *LANE, "--issue", "1711", **OTHER),
    _s("register-with-files", "register", "w1", *W, *LANE, "--issue", "1711",
       "--files", "a.py,scripts/", **OTHER),
    _s("register-clear-pr", "register", "w1", *W, *LANE, "--issue", "1711", "--clear-pr", **OTHER),
    _s("register-unscoped-lane", "register", "w2", *W, "--issue", "1712", "--files", "a.py",
       "--driver", "no-such-driver", CLAUDE_PID="6161", CLAUDE_CODE_SESSION_ID="identity-w2"),
    _s("register-force-takeover", "register", "w2", *W, "--force", "--issue", "1712",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:6161"),
    _s("register-default-wave", "register", "stray"),
    # reads
    _s("get", "get", "w1", *W, FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("get-dead-owner", "get", "w1", *W, FLOW_WAVE_LIVE_PIDS=SELF_PID),
    _s("get-unknown-owner", "get", "w1", *W, FLOW_WAVE_LIVE_PIDS=SELF_PID,
       FLOW_WAVE_UNKNOWN_PIDS=OTHER_PID),
    _s("get-missing-role", "get", "nobody", *W),
    _s("list", "list", *W, FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("list-json", "list", *W, "--json", FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("list-with-claim", "list", *W, FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}:{CLAIM_PID}"),
    _s("list-with-claim-json", "list", *W, "--json",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}:{CLAIM_PID}"),
    _s("list-any-live", "list", *W, "--any-live", FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("list-from-checkout", "list", *W, cwd="{tmp}/repo",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("list-default-wave", "list"),
    _s("self-address", "self-address"),
    # verification
    _s("verify-mismatch", "verify", "w1", *W, "--from", "uds:{tmp}/socks/7777.sock"),
    _s("verify-same", "verify", "w1", *W, "--from", "uds:{tmp}/socks/7777.sock"),
    _s("verify-bad-address", "verify", "w1", *W, "--from", "not-an-address"),
    _s("verify-missing-role", "verify", "nobody", *W, "--from", "uds:{tmp}/socks/1.sock"),
    # lane-check, from the role's own checkout
    _s("lane-check", "lane-check", "w1", *W, "--base", "main", cwd="{tmp}/repo",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("lane-check-granted", "lane-check", "w1", *W, "--base", "main", "--granted", "a.py",
       cwd="{tmp}/repo", FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("lane-check-outside-checkout", "lane-check", "w1", *W, "--base", "main",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("lane-check-missing-role", "lane-check", "nobody", *W, cwd="{tmp}/repo"),
    # release and close
    _s("release-other-holder-refused", "release", "w1", *W,
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("close-dry-run-held", "close", *W, "--dry-run", "--archive", "{tmp}/archive",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("close-held-refused", "close", *W, "--archive", "{tmp}/archive",
       FLOW_WAVE_LIVE_PIDS=f"{SELF_PID}:{OTHER_PID}"),
    _s("release-own", "release", "w2", *W),
    _s("release-force", "release", "w1", *W, "--force"),
    _s("list-after-release", "list", *W),
    _s("close-dry-run", "close", *W, "--dry-run", "--archive", "{tmp}/archive", "--force"),
    _s("close", "close", *W, "--archive", "{tmp}/archive", "--force"),
    _s("close-again", "close", *W, "--archive", "{tmp}/archive-2", "--force"),
    _s("list-after-close", "list", *W),
)

MW = ("--wave", WAVE)
FENCED = "context\n```\nGATE: HOLD #7\n```\nend"

MAILBOX_STEPS: tuple[Step, ...] = (
    # usage and help
    _s("no-arguments"),
    _s("unknown-verb", "frobnicate"),
    _s("help", "--help"),
    _s("help-short", "-h"),
    _s("send-no-to", "send", *MW, "--body", "x"),
    _s("send-to-orchestrator-no-from", "send", "--to", "orchestrator", *MW, "--body", "x"),
    _s("send-empty-body", "send", "--to", "w1", *MW, "--body", ""),
    _s("send-unknown-option", "send", "--to", "w1", *MW, "--nope"),
    _s("send-bad-wave", "send", "--to", "w1", "--wave", ".hidden", "--body", "x"),
    _s("send-bad-role", "send", "--to", "w/1", *MW, "--body", "x"),
    _s("read-no-role", "read", *MW),
    _s("watch-no-mode", "watch", "--role", "w1", *MW, "--timeout", "0"),
    _s("watch-both-modes", "watch", "--role", "w1", *MW, "--timeout", "0", "--peek", "--consume"),
    _s("watch-bad-timeout", "watch", "--role", "w1", *MW, "--timeout", "soon", "--peek"),
    _s("watch-bad-interval", "watch", "--role", "w1", *MW, "--timeout", "0", "--interval", "0",
       "--peek"),
    _s("ack-no-revs", "ack", "--role", "w1", *MW),
    _s("escalate-no-role", "escalate", *MW),
    _s("supervise-no-role", "supervise", *MW),
    # a wave with no directory yet
    _s("list-absent", "list", *MW),
    _s("list-absent-json", "list", *MW, "--json"),
    _s("read-absent", "read", "--role", "w1", *MW),
    _s("ack-absent", "ack", "--role", "w1", *MW, "--revs", "1"),
    _s("status-absent", "watch", "--status", "--role", "w1", *MW),
    # sending
    _s("send-body", "send", "--to", "w1", *MW, "--body", "first: the assignment"),
    _s("send-stdin", "send", "--to", "w1", *MW, stdin="second: from stdin\nline two\n"),
    _s("send-stdin-marker", "send", "--to", "w1", *MW, "--body", "-", stdin="third: dash marker\n"),
    _s("send-body-file", "send", "--to", "w1", *MW, "--body-file", "{tmp}/body.txt"),
    _s("send-body-file-missing", "send", "--to", "w1", *MW, "--body-file", "{tmp}/absent.txt"),
    _s("send-gate-ok", "send", "--to", "w1", *MW, "--body", "GATE: GO #1710"),
    _s("send-gate-malformed", "send", "--to", "w1", *MW, "--body", "GATE: MAYBE #1710"),
    _s("send-gate-malformed-no-lexicon", "send", "--to", "w1", *MW, "--no-lexicon",
       "--body", "GATE: MAYBE #1710"),
    _s("send-citation", "send", "--to", "w1", *MW, "--body", FENCED),
    _s("send-to-orchestrator", "send", "--to", "orchestrator", "--from", "w1", *MW,
       "--body", "report: done"),
    _s("send-awaiting-reply", "send", "--to", "orchestrator", "--from", "w1", *MW,
       "--awaiting-reply", "--body", "question: which base?"),
    _s("send-awaiting-reply-wrong-way", "send", "--to", "w1", *MW, "--awaiting-reply",
       "--body", "x"),
    _s("send-other-worker", "send", "--to", "w2", *MW, "--body", "for w2"),
    _s("send-replace", "send", "--to", "w2", *MW, "--replace", "--body", "current state for w2"),
    # listing and status
    _s("list", "list", *MW),
    _s("list-json", "list", *MW, "--json"),
    _s("status-role", "watch", "--status", "--role", "w1", *MW),
    _s("status-all", "watch", "--status", "--all", *MW),
    _s("status-no-role", "watch", "--status", *MW),
    # reading and acknowledging
    _s("read-peek", "read", "--role", "w1", *MW, "--peek"),
    _s("watch-peek", "watch", "--role", "w1", *MW, "--timeout", "0", "--peek"),
    _s("ack-missing-rev", "ack", "--role", "w1", *MW, "--revs", "99"),
    _s("ack-bad-rev", "ack", "--role", "w1", *MW, "--revs", "one"),
    _s("ack-one", "ack", "--role", "w1", *MW, "--revs", "1"),
    _s("ack-one-again", "ack", "--role", "w1", *MW, "--revs", "1,2"),
    _s("read-out", "read", "--role", "w1", *MW, "--out", "{tmp}/read-out.md"),
    _s("read-all", "read", "--role", "w1", *MW, "--all", "--peek"),
    _s("send-after-read", "send", "--to", "w1", *MW, "--body", "late: one more"),
    _s("watch-consume", "watch", "--role", "w1", *MW, "--timeout", "0", "--consume"),
    _s("watch-consume-empty", "watch", "--role", "w1", *MW, "--timeout", "0", "--consume"),
    _s("watch-peek-empty", "watch", "--role", "w1", *MW, "--timeout", "0", "--peek"),
    _s("status-after-watch", "watch", "--status", "--role", "w1", *MW),
    _s("read-empty", "read", "--role", "w1", *MW),
    _s("read-orchestrator-peek", "read", "--role", "orchestrator", *MW, "--peek"),
    _s("read-orchestrator-from", "read", "--role", "orchestrator", *MW, "--from", "w1", "--peek"),
    _s("watch-orchestrator-peek", "watch", "--role", "orchestrator", *MW, "--timeout", "0",
       "--peek"),
    # escalation: pending inside the bound, fired past it, deduplicated, then acked
    _s("escalate-nothing-sent", "escalate", "--role", "w3", *MW),
    _s("escalate-pending", "escalate", "--role", "w1", *MW),
    _s("escalate-unresolved", "escalate", "--role", "w1", *MW, FLOW_WAVE_NOW="4102444800"),
    _s("register-the-target", "register", "orchestrator", *MW, "--socket",
       "uds:{tmp}/socks/9001.sock", helper=REGISTRY),
    _s("escalate-other-target-unresolved", "escalate", "--role", "w1", "--to", "w9", *MW,
       FLOW_WAVE_NOW="4102444800"),
    _s("escalate-fire", "escalate", "--role", "w1", *MW, FLOW_WAVE_NOW="4102444800"),
    _s("escalate-already", "escalate", "--role", "w1", *MW, FLOW_WAVE_NOW="4102444800"),
    _s("ack-box-worker-refused", "ack", "--role", "w2", *MW, "--box", "outbox-w2.md",
       "--all-unacked"),
    _s("ack-orchestrator-box", "ack", "--role", "orchestrator", *MW, "--box", "inbox-w1.md",
       "--revs", "1", "--answered-elsewhere"),
    _s("escalate-second-oldest", "escalate", "--role", "w1", *MW, FLOW_WAVE_NOW="4102444800"),
    _s("ack-all-unacked", "ack", "--role", "orchestrator", *MW, "--from", "w1", "--all-unacked"),
    _s("escalate-acked", "escalate", "--role", "w1", *MW, FLOW_WAVE_NOW="4102444800"),
    _s("list-final", "list", *MW),
    _s("list-final-json", "list", *MW, "--json"),
)

LW = ("--wave", WAVE)
LEDGER_BODY = "LEDGER\ndelivered:\n- one\nin-scope:\n- two\nresidual:\n- none\n"

LEXICON_STEPS: tuple[Step, ...] = (
    # usage and help
    _s("no-arguments"),
    _s("unknown-verb", "frobnicate"),
    _s("help", "--help"),
    _s("help-short", "-h"),
    _s("validate-unknown-option", "validate", "--nope"),
    _s("validate-body-missing-value", "validate", "--body"),
    _s("validate-body-file-missing", "validate", "--body-file", "{tmp}/absent.txt"),
    _s("record-default-wave", "record", "--body", "GATE: GO #5"),
    _s("record-wave-missing-value", "record", "--wave"),
    _s("record-bad-wave", "record", "--wave", "../x", "--body", "GATE: GO #5"),
    # validate
    _s("validate-prose", "validate", "--body", "nothing reserved here"),
    _s("validate-empty-stdin", "validate", stdin=""),
    _s("validate-gate-go", "validate", "--body", "GATE: GO #5"),
    _s("validate-gate-slug", "validate", "--body", "GATE: GO journal-false-red"),
    _s("validate-gate-no-subject", "validate", "--body", "GATE: GO"),
    _s("validate-gate-bad-verb", "validate", "--body", "GATE: MAYBE #5"),
    _s("validate-gate-hold", "validate", "--body", "GATE: HOLD #5 behind #56, #57 the base moves"),
    _s("validate-gate-hold-reason-lines", "validate", stdin="GATE: HOLD #5\n- the base moves\n"),
    _s("validate-gate-hold-bare", "validate", "--body", "GATE: HOLD #5 until it looks good"),
    _s("validate-gate-conditional", "validate",
       stdin="GATE: GO-WITH-CONDITIONS #5\n- rebase on main\n- rerun the suite\n"),
    _s("validate-lane-grant", "validate", "--body", "LANE: GRANT w1 scripts/a.sh scripts/b.sh"),
    _s("validate-lane-revoke", "validate", "--body", "LANE: REVOKE w1"),
    _s("validate-lane-bad-verb", "validate", "--body", "LANE: #5 scripts/a.sh"),
    _s("validate-lane-bad", "validate", "--body", "LANE:"),
    _s("validate-merge-authorized", "validate",
       "--body", "MERGE: AUTHORIZED #5 when ci/woodpecker/pr/woodpecker reports success"),
    _s("validate-merge-vague", "validate", "--body", "MERGE: AUTHORIZED #5 when it looks good"),
    _s("validate-merge-priority", "validate", "--body", "MERGE: PRIORITY #5 it unblocks #6"),
    _s("validate-merge-bad", "validate", "--body", "MERGE: SOON #5"),
    _s("validate-state", "validate", "--body", "STATE: as-of abc1234 main is green"),
    _s("validate-state-no-stamp", "validate", "--body", "STATE: main is green"),
    _s("validate-ratify", "validate", "--body", "RATIFY #5 narrower boundary accepted"),
    _s("validate-ratify-no-reason", "validate", "--body", "RATIFY #5"),
    _s("validate-overrule", "validate", "--body", "OVERRULE #5 the gate was wrong"),
    _s("validate-pushback", "validate", "--body", "PUSHBACK: the base moved under this"),
    _s("validate-pushback-bare", "validate", "--body", "PUSHBACK"),
    _s("validate-ledger", "validate", stdin=LEDGER_BODY),
    _s("validate-ledger-partial", "validate", stdin="LEDGER\ndelivered:\n- one\n"),
    _s("validate-fenced", "validate", stdin=FENCED + "\n"),
    _s("validate-quoted", "validate", stdin="> GATE: GO #5\nreply\n"),
    _s("validate-indented", "validate", stdin="  GATE: GO #5\n"),
    _s("validate-mixed", "validate",
       stdin="GATE: GO #5\nGATE: MAYBE #6\nSTATE: as-of abc1234\n> RATIFY #9 cited\n"),
    _s("validate-body-file", "validate", "--body-file", "{tmp}/body.txt"),
    # record
    _s("record-dry-run", "record", *LW, "--dry-run", "--body", "GATE: GO #5"),
    _s("record", "record", *LW, "--body", "GATE: GO #5"),
    _s("record-second", "record", *LW,
       stdin="GATE: HOLD #6 behind #5 the base moves\nGATE: GO #7 clean\n"),
    _s("record-conditional", "record", *LW,
       stdin="GATE: GO-WITH-CONDITIONS #8\n- rebase on main\nSerializes: scripts/a.sh\n"),
    _s("record-slug", "record", *LW, "--body", "GATE: GO journal-false-red"),
    _s("record-none", "record", *LW, "--body", "RATIFY #5 narrower boundary accepted"),
    _s("record-invalid", "record", *LW, "--body", "GATE: MAYBE #5"),
    _s("record-ledger-file", "record", *LW, "--ledger", "{tmp}/other-ledger.json",
       "--body", "GATE: GO #9"),
    _s("record-ledger-malformed", "record", *LW, "--ledger", "{tmp}/bad-ledger.json",
       "--body", "GATE: GO #9"),
    _s("record-unknown-option", "record", *LW, "--nope"),
)

SCENARIOS: dict[str, tuple[Step, ...]] = {
    REGISTRY: REGISTRY_STEPS,
    MAILBOX: MAILBOX_STEPS,
    LEXICON: LEXICON_STEPS,
}

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "identity", "GIT_AUTHOR_EMAIL": "identity@example.invalid",
    "GIT_COMMITTER_NAME": "identity", "GIT_COMMITTER_EMAIL": "identity@example.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
}

#: Everything rewritten before comparing, beyond the two runs' own paths. Each
#: is a value the mailbox takes from the wall clock: a send stamp, a file's
#: modification time, or an age counted from one of those.
CLOCK_VALUES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bts=\S+"), "ts=<TS>"),
    (re.compile(r"\b\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\b"), "<TIME>"),
    (re.compile(r"^(FLOW_MAILBOX_(?:ESCALATE|WATCH)_AGE=)\d+$", re.M), r"\1<AGE>"),
    (re.compile(r'("age_secs":)\d+'), r"\1<AGE>"),
    (re.compile(r"\b\d+s (old|ago)\b"), r"<AGE>s \1"),
    (re.compile(r"\b(unacknowledged for )\d+s\b"), r"\1<AGE>s"),
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        env={**os.environ, **_GIT_ENV},
    )


def _prepare(tmp: Path) -> None:
    """The fixed inputs every run starts from: a checkout, a claimed worktree, two files."""
    for sub in ("home/.claude/sessions", "socks", "wave", "scratch"):
        (tmp / sub).mkdir(parents=True)
    # The record that turns the orchestrator's registered socket into a name.
    (tmp / "home/.claude/sessions/9001.json").write_text(json.dumps(
        {"name": "identity-orchestrator", "messagingSocketPath": f"{tmp}/socks/9001.sock"}))
    (tmp / "body.txt").write_text("from a file\nGATE: GO #1710\n")
    (tmp / "bad-ledger.json").write_text("{not json\n")
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "a.py").write_text("a = 1\n")
    (repo / "c.py").write_text("c = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "issue-1710-x")
    (repo / "a.py").write_text("a = 2\n")
    (repo / "c.py").write_text("c = 2\n")
    _git(repo, "commit", "-q", "-am", "work")
    (repo / "untracked.py").write_text("u = 1\n")
    # A linked worktree under a flow-claim lock nobody registered (issue #687).
    _git(repo, "worktree", "add", "-q", "-b", "issue-555-claimed", str(tmp / "claimed"), "main")
    _git(repo, "worktree", "lock", str(tmp / "claimed"), "--reason",
         f"flow-claim issue=555 pid={CLAIM_PID} session=identity-claim host={HOST} ts=1700000000")


def stage(script: str, source: Path, dest: Path) -> Path:
    """Copy the current `scripts/` into DEST, with SCRIPT taken from SOURCE.

    The helpers find their siblings by their own directory, so every run gets
    the same current neighbours and exactly one file that may differ.
    """
    dest.mkdir(parents=True)
    for path in SCRIPTS.iterdir():
        if path.is_file():
            shutil.copy2(path, dest / path.name)
    shutil.copy2(source, dest / script)
    return dest / script


def _normalise(text: str, tmp: Path, staged: Path) -> str:
    text = text.replace(str(staged), "<SCRIPTS>").replace(str(tmp), "<TMP>")
    for pattern, token in CLOCK_VALUES:
        text = pattern.sub(token, text)
    return text


def capture(script: str, source: Path, tmp: Path) -> list[Outcome]:
    """Run SCRIPT's whole scenario with the copy at SOURCE, in the fresh directory TMP."""
    staged = stage(script, source, tmp / "scripts")
    _prepare(tmp)
    base = os.environ.copy()
    base.update(_GIT_ENV)
    base.update({
        "HOME": str(tmp / "home"),
        "TMPDIR": str(tmp / "scratch"),
        "CLAUDE_PID": SELF_PID,
        "CLAUDE_CODE_SESSION_ID": "identity-self",
        "FLOW_WAVE_REGISTRY_DIR": str(tmp / "wave"),
        "FLOW_WAVE_MAILBOX_DIR": str(tmp / "wave"),
        "FLOW_WAVE_LEXICON_DIR": str(tmp / "wave"),
        "FLOW_WAVE_SOCK_DIR": str(tmp / "socks"),
        "FLOW_WAVE_SESSION_PIDS": str(tmp / "no-session-pids"),
        "FLOW_WAVE_HOST": HOST,
        "FLOW_WAVE_LIVE_PIDS": SELF_PID,
        "FLOW_WAVE_UNKNOWN_PIDS": "",
        "FLOW_WAVE_PID_STARTTIMES": f"{SELF_PID}=w-{SELF_PID}:{OTHER_PID}=w-{OTHER_PID}:6161=w-6161",
    })
    if script != MAILBOX:
        # The mailbox measures a message's age against the wall-clock stamp it
        # wrote, so its clock is left real except where a step pins it.
        base["FLOW_WAVE_NOW"] = "1786470000"
    for name in ("XDG_RUNTIME_DIR", "FLOW_WAVE_PROC_ROOT", "FLOW_WAVE_MAILBOX_NO_CREATE"):
        base.pop(name, None)
    outcomes = []
    for step in SCENARIOS[script]:
        env = dict(base)
        env.update({key: value.replace("{tmp}", str(tmp)) for key, value in step.env})
        args = [arg.replace("{tmp}", str(tmp)) for arg in step.args]
        proc = subprocess.run(
            ["bash", str(staged.parent / (step.helper or script)), *args],
            capture_output=True, text=True, env=env, check=False, timeout=60,
            input=step.stdin, stdin=None if step.stdin is not None else subprocess.DEVNULL,
            cwd=step.cwd.replace("{tmp}", str(tmp)),
        )
        outcomes.append(Outcome(
            step.name, proc.returncode,
            _normalise(proc.stdout, tmp, staged.parent),
            _normalise(proc.stderr, tmp, staged.parent),
        ))
    return outcomes


def _line_differences(step: str, stream: str, old: str, new: str) -> list[Difference]:
    before, after = old.splitlines(keepends=True), new.splitlines(keepends=True)
    found = []
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        gone, came = before[i1:i2], after[j1:j2]
        for index in range(max(len(gone), len(came))):
            found.append(Difference(
                step, stream,
                gone[index] if index < len(gone) else None,
                came[index] if index < len(came) else None,
            ))
    return found


def differences(old: list[Outcome], new: list[Outcome]) -> list[Difference]:
    """Every line, of every stream of every step, that the two runs disagree on."""
    assert [o.name for o in old] == [n.name for n in new], "the two runs ran different steps"
    found = []
    for before, after in zip(old, new, strict=True):
        if before.exit_code != after.exit_code:
            found.append(Difference(
                before.name, "exit", f"{before.exit_code}\n", f"{after.exit_code}\n"))
        found += _line_differences(before.name, "stdout", before.stdout, after.stdout)
        found += _line_differences(before.name, "stderr", before.stderr, after.stderr)
    return found


def compare(script: str, old_source: Path, new_source: Path, tmp: Path) -> tuple[
    list[Outcome], list[Outcome], list[Difference]
]:
    """Run the scenario with both copies, side by side, and diff the transcripts.

    The two directories have names of the same length, so no captured byte
    count or padded column can differ because of where a run happened.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        old_run = pool.submit(capture, script, old_source, tmp / "run-a")
        new_run = pool.submit(capture, script, new_source, tmp / "run-b")
        old, new = old_run.result(), new_run.result()
    return old, new, differences(old, new)


def _render(found: list[Difference]) -> str:
    return "\n".join(
        f"[{d.step}/{d.stream}]\n  - {d.old!r}\n  + {d.new!r}" for d in found
    )


def _assert_scenario_is_not_blind(script: str, outcomes: list[Outcome]) -> None:
    """A comparison of two empty or all-failing transcripts would agree too."""
    codes = {o.exit_code for o in outcomes}
    assert 0 in codes and 2 in codes, f"{script}: scenario reached exit codes {sorted(codes)} only"
    assert all(o.exit_code not in (126, 127) for o in outcomes), (
        f"{script}: a step could not be executed at all"
    )
    marker = {REGISTRY: "FLOW_WAVE: ", MAILBOX: "FLOW_MAILBOX: ", LEXICON: "FLOW_LEXICON: "}[script]
    verdicts = {
        line for o in outcomes for line in o.stdout.splitlines() if line.startswith(marker)
    }
    assert len(verdicts) >= 4, f"{script}: scenario reached only {sorted(verdicts)}"


@requires_tools
@pytest.mark.parametrize("script", [REGISTRY, MAILBOX, LEXICON])
def test_output_is_identical_to_the_pre_1691_snapshot(script: str, tmp_path: Path) -> None:
    old, new, found = compare(script, SNAPSHOT / script, SCRIPTS / script, tmp_path)
    _assert_scenario_is_not_blind(script, old)
    _assert_scenario_is_not_blind(script, new)
    unexpected = [
        d for d in found
        if d.old is None or d.new is None
        or Expected(d.old.rstrip("\n"), d.new.rstrip("\n")) not in EXPECTED_DIFFERENCES[script]
    ]
    assert not unexpected, f"{script} prints something the snapshot did not:\n{_render(unexpected)}"
    seen = {Expected(d.old.rstrip("\n"), d.new.rstrip("\n")) for d in found if d.old and d.new}
    missing = EXPECTED_DIFFERENCES[script] - seen
    assert not missing, f"{script}: listed as an expected difference but not observed: {missing}"


@requires_tools
def test_the_two_runs_of_one_script_agree_with_themselves(tmp_path: Path) -> None:
    """The normalisation is sufficient: the same copy, run twice, has no difference.

    Without this a flake in the comparison would be read as a change in a script.
    """
    for script in (REGISTRY, MAILBOX, LEXICON):
        _, _, found = compare(script, SCRIPTS / script, SCRIPTS / script, tmp_path / script)
        assert not found, f"{script} differs from itself:\n{_render(found)}"


VERDICT_ECHO = 'echo "FLOW_WAVE: $1"'


@requires_tools
def test_one_changed_byte_is_reported(tmp_path: Path) -> None:
    """The red case: one printed byte changed in the registry is a difference."""
    source = (SCRIPTS / REGISTRY).read_text()
    assert source.count(VERDICT_ECHO) == 1, "precondition: the verdict echo exists exactly once"
    changed = tmp_path / "changed-registry.sh"
    changed.write_text(source.replace(VERDICT_ECHO, 'echo "FLOW_WAVE; $1"'))
    _, _, found = compare(REGISTRY, SCRIPTS / REGISTRY, changed, tmp_path / "work")
    assert found, "a changed verdict line was not reported"
    assert all(d.stream == "stdout" for d in found), _render(found)
    assert all(
        d.old is not None and d.new is not None
        and d.old.startswith("FLOW_WAVE: ") and d.new == d.old.replace("FLOW_WAVE: ", "FLOW_WAVE; ")
        for d in found
    ), _render(found)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in SCENARIOS:
        print(f"usage: python -m tests.test_flow_wave_output_identity "
              f"{{{'|'.join(SCENARIOS)}}} <copy-to-compare-with-scripts/>", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="flow-wave-identity-") as scratch:
        _, new, found = compare(argv[0], SCRIPTS / argv[0], Path(argv[1]).resolve(), Path(scratch))
    print(f"{argv[0]}: {len(new)} steps compared, {len(found)} differing line(s)")
    if found:
        print(_render(found))
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
