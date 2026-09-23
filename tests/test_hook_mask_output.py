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


def test_no_declaration_of_the_masker_ships_anywhere():
    """Run 1 of #1206 pinned that `.claude/hooks.json` still HELD the declaration.

    Decision 1 deleted the file, so that assertion's subject is gone and the
    test inverts rather than being deleted: what matters now is that no shipped
    file re-creates a declaration Claude Code would never load anyway.

    Inverting rather than deleting is deliberate. A removed test leaves nothing
    to notice the file coming back; this one names the exact path and fails if
    it returns.
    """
    assert not (ROOT / ".claude" / "hooks.json").exists(), (
        ".claude/hooks.json is back. CPP does not ship it (#1206 Decision 1): "
        "Claude Code never loaded that path, so its only effect was to make "
        "people believe their tool output was masked. If registration is being "
        "revisited, the documented home is the USER settings file written by "
        "the installer, not this one."
    )
    declaring = []
    for path in _shipped_surfaces():
        if path.suffix not in {".json", ".md", ".sh"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if "hook-mask-output" in line and '"command"' in line:
                declaring.append(f"{path.relative_to(ROOT)}:{n}")
    assert not declaring, (
        "a shipped file declares the masker as a hook command: " + ", ".join(declaring)
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


# --- THE CLAIM CONTROL (#1206 Decision 1) -----------------------------------
#
# Everything above tests a BEHAVIOUR. This tests a CLAIM, and it is the control
# the removal needs: the owner ruled that CPP stops asserting a protection it
# does not provide, so the thing that can regress is the SENTENCE, not the code.
#
# It is the #1083 shape - a test that FAILS if the assertion returns - and it
# was shown RED against the pre-removal tree before the removal was written. A
# claim control written afterwards passes over an empty population and proves
# nothing about what it would catch.


def _shipped_surfaces() -> list[Path]:
    """Files whose text a USER reads as a statement about their install.

    The population is `git ls-files`, so an untracked scratch file cannot
    inflate it and an ignored one cannot hide in it. Exclusions are a DENY
    list, never an allow list: a new top-level directory is therefore scanned
    by default rather than silently skipped, and the failure direction of a
    too-narrow deny list is a loud false positive rather than a silence.

    What is excluded, and why each one is a RECORD rather than a claim:

      docs/flow-runs, docs/research, docs/reviews, docs/decisions,
      docs/measurements, .specify, CHANGELOG.md
                    history. An ADR saying what was true in September is not a
                    claim about what ships today, and rewriting it to match the
                    present is how a decision record stops being one.
      controls/     fixtures and frozen anchors. An anchor is a byte-exact copy
                    of a past implementation; editing one destroys the control.
      tests/        this file argues about the claim, so it must contain the
                    words. A scanner that reads its own assertions is the
                    text-search-matches-its-own-documentation trap.
      codex/skills/ byte-identical generated mirrors. They are regenerated from
                    the sources above, so flagging them would report every
                    finding twice and invite fixing the copy instead of the
                    source.
    """
    excluded = (
        "docs/flow-runs/", "docs/research/", "docs/reviews/", "docs/decisions/",
        "docs/measurements/", ".specify/", "controls/", "tests/", "codex/skills/",
        # Not surfaces at all: VCS internals, build output, dependency trees,
        # and this repository's own generated run artifacts.
        ".git/", ".venv/", "node_modules/", "__pycache__/", ".pytest_cache/",
        ".ruff_cache/", ".mypy_cache/", "htmlcov/", "dist/", "build/",
        ".claude/runs/",
    )
    # `.git` IS A FILE IN A LINKED WORKTREE, not a directory, so the ".git/"
    # prefix above does not cover it - and its one line is the absolute path of
    # a worktree whose directory is named after the branch. On this very branch
    # that name contains both "posttooluse" and "masking", so the scan matched
    # THE CHECKOUT'S OWN IDENTITY and reported a claim nobody wrote.
    # `.claude/runs/` is the same shape one step out: the finish gate writes
    # this test's own failure output there, so a second run reads the first
    # run's complaint as a fresh offender.
    not_a_surface = {".git"}
    # NO `git ls-files` HERE, deliberately. The repository's binary-guard rule
    # would require a skipif, and a skipif makes this control INERT in the CI
    # image that carries no git - silently, in the one environment nobody is
    # watching it. That is the exact shape #1206 is about. A filesystem walk
    # differs from `git ls-files` only by UNTRACKED files, which makes the scan
    # stricter rather than weaker, and every failure names its path.
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel == "CHANGELOG.md" or rel in not_a_surface or rel.startswith(excluded):
            continue
        out.append(path)
    return out


def test_the_scan_can_find_something_before_it_is_believed():
    """The extractor control. A broken scan's zero looks exactly like a real one.

    `test_no_shipped_surface_claims_active_masking` reports a POPULATION OF
    ZERO on a healthy tree, and that is indistinguishable from a scan that
    reads no files, decodes nothing, or matches nothing ever. So prove the
    machinery can produce a hit: run the same predicate over a line that is a
    known instance of exactly what it looks for.
    """
    surfaces = _shipped_surfaces()
    assert len(surfaces) > 100, f"population collapsed to {len(surfaces)} files"
    # A size check alone does not connect the population to the files that
    # matter - 100 files could all be fixtures. Name the four surfaces this
    # issue is actually about and require each one IN, so a deny list that
    # grows too greedy is caught by the test rather than by a later reader.
    must_scan = {
        "CLAUDE.md", "README.md", "docs/scripts.md",
        ".claude/commands/cpp/update.md",
    }
    present = {p.relative_to(ROOT).as_posix() for p in surfaces}
    assert must_scan <= present, (
        "the scan no longer reads: " + ", ".join(sorted(must_scan - present))
    )
    planted = "- **PostToolUse (Bash/Read)**: Secret masking via `hook-mask-output.sh`"
    assert _asserts_active_masking(planted), (
        "the predicate does not match a line taken verbatim from the pre-removal "
        "tree - it would report every tree clean"
    )
    assert not _asserts_active_masking("- PostToolUse hooks are not used by CPP.")


def _asserts_active_masking(line: str) -> bool:
    """`PostToolUse` and `mask` on ONE line, in either order, any case.

    A SHAPE rather than a phrase list, deliberately. The eight surfaces this
    issue set out to fix were found from three anchors; this shape found three
    MORE that nobody had named - `.claude/verify-coverage.json`,
    `scripts/hook-permission-census.sh` and
    `templates/claude-settings-permissions.md` - because a list of today's
    wordings only ever catches today's wordings.

    There is no negation carve-out, and that is the point: after this change
    CPP ships no PostToolUse masking hook, so a shipped file has no occasion to
    put the two words together even to deny it. Re-adding the pairing must be a
    deliberate act that also edits this predicate, which is what makes the
    control a record of the decision rather than a spell-checker.
    """
    low = line.lower()
    return "posttooluse" in low and "mask" in low


def test_no_shipped_surface_claims_active_masking():
    """RED before this change: 14 lines across 10 files, CLAUDE.md:134 among them.

    That red run is the evidence. Re-reading the removal would only confirm
    what it MEANT; this is what it CAN say.
    """
    offenders: list[str] = []
    for path in _shipped_surfaces():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: it is not a surface a user reads
        for n, line in enumerate(text.splitlines(), 1):
            if _asserts_active_masking(line):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:120]}")
    assert not offenders, (
        "a shipped surface pairs PostToolUse with masking again. CPP does not "
        "register a PostToolUse masking hook (owner ruling, #1206 Decision 1); "
        "the masker survives as a file-at-rest tool for /security:*. If this is "
        "a deliberate reversal, change the ruling and this test together:\n  "
        + "\n  ".join(offenders)
    )
