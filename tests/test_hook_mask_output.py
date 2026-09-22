"""Tests for scripts/hook-mask-output.sh - the PostToolUse secret masker.

#1206 exists because three facts were confused for three months:

  CAPABILITY  - can the masker mask?                  provable, and always was
  REGISTRATION- is it declared where Claude Code reads it?   NOT fixed here
  DISPATCH    - does the harness route output to it?   not reachable from a test

Only the first was ever demonstrated, and it was read as the third. These tests
keep them apart, and assert the unfixed state rather than leaving it in prose.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MASKER = ROOT / "scripts" / "hook-mask-output.sh"


def _mask(payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(MASKER)], input=payload, capture_output=True, text=True, check=False
    )


# --- CAPABILITY -------------------------------------------------------------


def test_it_masks_a_password():
    out = _mask(json.dumps({"tool_output": "password=secret123"}))
    assert "secret123" not in out.stdout, out.stdout
    assert "password=****" in out.stdout


def test_a_TRIPLE_QUOTE_payload_is_masked_and_not_swallowed():
    """The defect that made this a security finding rather than a nuisance.

    The masker interpolated stdin as ``'''$INPUT'''`` into Python source, so a
    payload containing ``'''`` ended the literal and the rest became code: a
    SyntaxError, and EMPTY STDOUT. Empty stdout is this script's documented "no
    change" answer, so the failure was INDISTINGUISHABLE from "nothing needed
    masking" and the unmasked value went straight through.

    Pinned as a test rather than a control case because the anchor CRASHES on
    this input - it is the defect trigger - and an anchor must agree with the
    fixed gate on known-good inputs. The control reports that reasoning.
    """
    payload = json.dumps({"tool_output": "has ''' quotes and password=secret123"})
    out = _mask(payload)
    assert out.returncode == 0, out.stderr
    assert "secret123" not in out.stdout, (
        "the triple-quote payload must not defeat masking:\n" + out.stdout + out.stderr
    )
    assert "password=****" in out.stdout


def test_a_dollar_payload_is_masked():
    """The trigger is `'''`, not shell metacharacters generally - measured."""
    out = _mask(json.dumps({"tool_output": "has $VAR and password=secret123"}))
    assert "secret123" not in out.stdout
    assert "$VAR" in out.stdout, "unrelated content must survive unchanged"


# --- FAILING LOUDLY ---------------------------------------------------------


def test_a_parse_failure_ANNOUNCES_itself_and_does_not_read_as_clean():
    """The fail-open this change removes.

    The except branch said "on error, pass through unchanged" - a deliberate
    fail-open in a masker, producing empty stdout, which is "no change". So an
    input it could not parse looked exactly like an input with nothing to mask.

    A non-zero exit does NOT retract the tool output; by the time a PostToolUse
    hook runs, the output exists. What changes is that the failure is ANNOUNCED
    rather than mistaken for success.
    """
    out = _mask("not json at all")
    assert out.returncode != 0, "a parse failure must not exit 0"
    assert "FAILED to process" in out.stderr, out.stderr
    assert "NOT masked" in out.stderr, (
        "the message must say the output was not masked, or a reader takes the "
        "absence of secrets in it as evidence there were none"
    )


def test_genuinely_empty_output_is_still_quiet():
    """The other direction: 'nothing to mask' must stay indistinguishable from
    nothing to mask. Making every empty case loud would be the mirror defect."""
    out = _mask(json.dumps({"tool_output": ""}))
    assert out.returncode == 0
    # `.strip()`, not `== ""`: the script emits a trailing newline, and a shell
    # check with `$(cat ...)` strips it, so the two disagree. The test saw the
    # raw bytes and the shell did not - which is the correct direction for the
    # test to err, but worth naming so nobody "fixes" the script to satisfy a
    # measurement that was quietly normalising.
    assert out.stdout.strip() == "", repr(out.stdout)
    assert out.stderr == "", repr(out.stderr)


# --- REGISTRATION: the half this change does NOT fix ------------------------


def test_the_hook_is_STILL_NOT_REGISTERED_where_claude_code_reads():
    """ASSERTS THE UNFIXED STATE. This test failing is the good news.

    The masker is fixed; the hook is still declared only in
    `.claude/hooks.json`, which nothing Claude Code reads. Registering it is a
    HOST WRITE into `~/.claude/settings.json` by the installer - the pattern
    `docs/HOST_MANAGED_ARTIFACTS.md:107-112` documents for the PermissionRequest
    census hook at /cpp:init Step 7.7, and the reason PermissionRequest fires
    today while PostToolUse does not.

    That is another role's lane, held for an owner decision, so this change does
    not do it and must not appear to.

    WHEN THE INSTALLER LANDS, THIS TEST FAILS. That is the notification, not a
    regression: whoever does that work inverts this assertion as part of it.
    """
    assert not (ROOT / ".claude" / "settings.json").exists(), (
        "a tracked .claude/settings.json appeared - if the registration work "
        "landed, invert this test; if not, note that .gitignore:206 ignores "
        ".claude/settings*.json deliberately and the documented home for this "
        "hook is the USER settings file, written by the installer"
    )


def test_hooks_json_is_still_the_only_declaration_and_is_not_a_read_location():
    """The positive half of the same fact, so it cannot be read as 'no config'."""
    hooks = json.loads((ROOT / ".claude" / "hooks.json").read_text())
    post = hooks.get("hooks", {}).get("PostToolUse", [])
    masking = [
        e for e in post
        if any("hook-mask-output" in (h.get("command") or "") for h in (e.get("hooks") or []))
    ]
    assert masking, "the masking hook's declaration vanished from .claude/hooks.json"
    # And the shape defect is still there, unobservable until the location is fixed.
    assert all(isinstance(e.get("matcher"), dict) for e in masking), (
        "the matcher shape changed in a file nothing reads - that is a fix that "
        "looks like a fix and changes nothing; fix the LOCATION first"
    )
