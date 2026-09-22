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


def test_no_PROJECT_settings_file_declares_the_masker(tmp_path: Path):
    """ASSERTS THE UNFIXED STATE, scoped to the MASKER rather than to a filename.

    The first version of this test checked only whether `.claude/settings.json`
    EXISTED, and the counter-model review showed that fails the ownership
    question in both directions: an unrelated settings file added for any other
    reason would break it, and registering the masker in the DOCUMENTED place -
    the user-level `~/.claude/settings.json` - would leave it green. It claimed
    installer work would trip it and it would not have.

    So it keys on a masker-specific declaration in a specific artifact.

    HOST REGISTRATION IS UNEXAMINED, NOT ASSERTED ABSENT. `~/.claude/settings.json`
    is the user's own config; this suite does not read it, does not write it, and
    makes no claim about it. Whether the hook is registered THERE is exactly the
    fact no test in this repository can settle, and pretending otherwise would
    repeat #1206's original confusion.
    """
    project_settings = ROOT / ".claude" / "settings.json"
    if not project_settings.is_file():
        return  # nothing declares it here, which is the current state
    declared = json.loads(project_settings.read_text()).get("hooks", {}).get("PostToolUse", [])
    masking = [
        e for e in declared
        if any("hook-mask-output" in (h.get("command") or "") for h in (e.get("hooks") or []))
    ]
    assert not masking, (
        "a project settings file now declares the masker - if the registration "
        "work landed, invert this test; note that .gitignore:206 ignores "
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


# --- Counter-model findings, each reproduced before it was fixed ------------


def test_a_NUL_BYTE_CANNOT_RECONSTRUCT_THE_SECRET_AFTER_FILTERING():
    """The filter used to CREATE the secret it exists to remove.

    `pass<NUL>word=VALUE` does not match the password pattern - the NUL sits
    between the letters - so Python passed it through unchanged. The result was
    then captured with `MASKED_OUTPUT=$(...)`, and BASH STRIPS NULs during
    command substitution, so the script emitted `password=VALUE` with exit 0.

    A shell variable cannot hold a NUL, so no quoting fixes it: the capture
    itself was the defect. Python's stdout is now this script's stdout.
    """
    payload = json.dumps({"tool_output": "pass" + chr(0) + "word=SYNTHETIC_VALUE"})
    out = subprocess.run(
        ["bash", str(MASKER)], input=payload.encode(), capture_output=True, check=False
    )
    emitted = out.stdout.decode("utf-8", "replace")
    assert "password=SYNTHETIC_VALUE" not in emitted, (
        "the masker reconstructed a recognisable secret after filtering:\n" + emitted
    )


def test_INVALID_SHAPES_are_announced_and_not_silently_successful():
    """"The field is missing or the wrong type" is not "the output was empty".

    All three used to exit 0 with empty stdout and no diagnostic, which is this
    script's "no change" answer - so a caller supplying output under another
    field bypassed masking entirely and the run looked clean.
    """
    for payload in ('{}', '{"tool_output": null}', '{"tool_output": []}'):
        out = _mask(payload)
        assert out.returncode != 0, f"{payload} exited 0: {out.stdout!r}"
        assert "FAILED to process" in out.stderr, payload
        assert "NOT masked" in out.stderr, payload


def test_NON_UTF8_input_is_announced_rather_than_traced():
    """The read sat outside the try, so this path bypassed the announcement.

    It produced exit 1 with a raw UnicodeDecodeError traceback and no "NOT
    masked" line - the exact behaviour this change exists to remove, on a path
    the first round of tests did not cover.
    """
    out = subprocess.run(
        ["bash", str(MASKER)],
        input=bytes([255, 254]) + b" not utf8",
        capture_output=True, check=False,
    )
    err = out.stderr.decode("utf-8", "replace")
    assert out.returncode != 0
    assert "NOT masked" in err, "an undecodable payload must still announce:\n" + err
