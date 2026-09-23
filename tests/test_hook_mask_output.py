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
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MASKER = ROOT / "scripts" / "hook-mask-output.sh"

#: The repo convention for a test that shells out (#602): guard on
#: shutil.which so the no-git CI validate image SKIPS rather than errors.
requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git absent in the CI validate image"
)


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


@requires_git
def test_no_declaration_of_the_masker_ships_anywhere():
    """Run 1 of #1206 pinned that `.claude/hooks.json` still HELD the declaration.

    Decision 1 deleted the file, so that assertion's subject is gone and the
    test inverts rather than being deleted: what matters now is that no shipped
    file re-creates a declaration Claude Code would never load anyway.

    Inverting rather than deleting is deliberate. A removed test leaves nothing
    to notice the file coming back; this one names the exact path and fails if
    it returns.
    """
    # ASK THE SHIPPED INVENTORY, NOT THE FILESYSTEM. An `exists()` check fails on
    # an IGNORED leftover from an older install - which is the supported
    # migration state this change explicitly caters for (/cpp:update Step 4.7
    # offers its removal, default N). Reporting the user's own leftover as a
    # repository regression would contradict the migration in the same PR
    # (counter-model pass 2).
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", ".claude/hooks.json"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert not tracked, (
        ".claude/hooks.json is tracked again. CPP does not ship it (#1206 "
        "Decision 1): Claude Code never loaded that path, so its only effect "
        "was to make people believe their tool output was masked. If "
        "registration is being revisited, the documented home is the USER "
        "settings file written by the installer, not this one."
    )
    declaring = _files_declaring("hook-mask-output", _shipped_surfaces())
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


#: The surfaces that CARRIED the claim, by name. Hardcoded ON PURPOSE - this is
#: the universe, and deriving it is what the broad scan is for. A name that
#: leaves this list must be removed deliberately, which is the point.
CLAIM_BEARING = (
    "CLAUDE.md",
    "README.md",
    "docs/scripts.md",
    ".claude/commands/cpp/init.md",
    ".claude/commands/cpp/update.md",
    ".claude/commands/cpp/status.md",
    ".claude/commands/cpp/help.md",
    ".claude/commands/project/init.md",
    ".claude/commands/flow/doctor.md",
    ".claude/verify-coverage.json",
    "templates/claude-settings-permissions.md",
    "scripts/hook-permission-census.sh",
    "scripts/hook-mask-output.sh",
)

def test_the_named_claim_surfaces_are_clean_and_were_actually_read():
    """The half that CANNOT skip and CANNOT misattribute.

    Every path here is tracked and shipped, so a hit is unambiguously CPP's -
    and each file must exist and read non-empty, so "no offenders" can never
    mean "nothing was read". That is the failure the broad scan had: it counted
    paths, not successful reads, and would have reported a clean tree with every
    `read_text` raising.
    """
    unreadable: list[str] = []
    offenders: list[str] = []
    read_ok = 0
    for rel in CLAIM_BEARING:
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append(f"{rel}: {type(exc).__name__}")
            continue
        if not text.strip():
            unreadable.append(f"{rel}: empty")
            continue
        read_ok += 1
        for n, window in _claim_windows(text):
            if _asserts_active_masking(window):
                offenders.append(f"{rel}:{n}: {window[:120]}")
                break
    assert not unreadable, (
        "a named claim surface could not be read, so this test proves nothing "
        "about it: " + ", ".join(unreadable)
    )
    assert read_ok == len(CLAIM_BEARING), f"{read_ok}/{len(CLAIM_BEARING)} read"
    assert not offenders, "\n  ".join(["a named surface asserts active masking:"] + offenders)



def _files_declaring(helper_name: str, surfaces: list[Path]) -> list[str]:
    """Shipped files that register `helper_name` as a hook command.

    JSON IS PARSED, NOT GREPPED (counter-model finding). The first cut required
    `"command"` and the helper name on the SAME LINE, so this valid declaration
    slipped both scans untouched:

        {"type": "command",
         "command":
           "~/.claude/scripts/hook-mask-output.sh"}

    A registration's meaning does not depend on where the formatter put the line
    break, so neither can its detection. Non-JSON files still fall back to the
    line scan - they are prose and installer shell, where there is no structure
    to walk.
    """
    found: list[str] = []

    #: A `command` field only REGISTERS the helper when it sits under a hooks
    #: structure. Counting every matching command anywhere reported
    #: `{"tasks": [{"command": "hook-mask-output.sh < archive.json"}]}` as a
    #: registration - which is the explicitly RETAINED standalone use of the
    #: masker over a file at rest, i.e. the one thing this change preserves on
    #: purpose. A neighbour's task definition would have failed a
    #: hook-registration check (counter-model pass 2).
    EVENTS = {
        "hooks", "PostToolUse", "PreToolUse", "SessionStart", "SessionEnd",
        "PermissionRequest", "Stop", "SubagentStop", "Notification",
        "UserPromptSubmit", "PreCompact",
    }

    def walk(node: object, path: Path, trail: str, under_hook: bool) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "command" and isinstance(v, str) and helper_name in v and under_hook:
                    found.append(f"{path.relative_to(ROOT)}:{trail}.command")
                walk(v, path, f"{trail}.{k}", under_hook or k in EVENTS)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path, f"{trail}[{i}]", under_hook)

    for path in surfaces:
        if path.suffix not in {".json", ".md", ".sh"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if path.suffix == ".json":
            try:
                walk(json.loads(text), path, "$", False)
                continue
            except json.JSONDecodeError:
                pass  # not valid JSON after all - fall through to the line scan
        for n, line in enumerate(text.splitlines(), 1):
            if helper_name in line and '"command"' in line:
                found.append(f"{path.relative_to(ROOT)}:{n}")
    return found


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
    )
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\0")
    return [
        ROOT / rel for rel in listed
        if rel and rel != "CHANGELOG.md" and not rel.startswith(excluded)
        and (ROOT / rel).is_file()
    ]


@requires_git
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
    # Third shape: verbatim from /cpp:help before #1206 run 3 - RED on that tree.
    assert _asserts_active_masking(
        "- **Hooks**: Security (command validation, output masking)"
    ), "the /cpp:help Tier 2 hook bullet is invisible to this predicate"
    # ...and the retained at-rest helper rows must NOT trip it.
    assert not _asserts_active_masking(
        "| mask-output helper | ✅/❌ | ~/.claude/scripts/hook-mask-output.sh "
        "(files at rest; not a live hook) |"
    )
    assert not _asserts_active_masking("| secrets-mask.sh | ✅/❌ | Output masking filter |")
    # The wrapped form, verbatim from the masker header the review caught.
    wrapped = _claim_windows(
        "# This hook receives tool output on stdin and masks sensitive data\n"
        "# before it's shown to Claude, preventing secrets from entering context.\n"
    )
    assert any(_asserts_active_masking(w) for _, w in wrapped), (
        "a claim split across two lines is invisible to this predicate"
    )



def _claim_windows(text: str) -> list[tuple[int, str]]:
    """Group lines into SENTENCES, not into fixed-size windows.

    The first cut joined 1-, 2- and 3-line runs, and the counter-model review
    broke it in both directions at once:

      TOO NARROW - a claim spread over four lines matched nothing:
          # PostToolUse processes command output
          # from Bash and Read invocations,
          # automatically removing credentials and
          # masking secrets before delivery.

      TOO WIDE - two unrelated bullets became a claim neither makes:
          - PostToolUse runs the audit logger.
          - secrets-mask.sh masks files at rest.

    Widening the window fixes the first and worsens the second, so the size was
    never the right dial. The unit is: a claim is a SENTENCE, and a sentence
    wraps. A line CONTINUES the previous one when the previous did not close a
    sentence and this one does not open a new item - so a wrapped claim of any
    length is one unit, and two adjacent list items are two.
    """
    units: list[tuple[int, str]] = []
    start = 0
    parts: list[str] = []

    def flush() -> None:
        if parts:
            units.append((start + 1, " ".join(parts)))

    def strip_marker(raw: str) -> str:
        body = raw.strip()
        while body[:1] in {"#", "*", "|"}:
            body = body[1:].lstrip()
        if body[:2] in {"- ", "+ "}:
            body = body[2:].lstrip()
        return body

    def opens_item(raw: str) -> bool:
        body = raw.strip().lstrip("#").lstrip()
        return body[:2] in {"- ", "* ", "+ ", "| "} or body[:1] == "|"

    prev_raw = ""
    for i, raw in enumerate(text.splitlines()):
        if not raw.strip():
            flush()
            parts, prev_raw = [], ""
            continue
        closed = prev_raw.rstrip().endswith((".", ":", ";", "!", "?", '"', "`"))
        if parts and (closed or opens_item(raw)):
            flush()
            parts = []
        if not parts:
            start = i
        parts.append(strip_marker(raw))
        prev_raw = raw
    flush()
    return units


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
    if "mask" not in low:
        return False
    if "posttooluse" in low:
        return True
    # THIRD SHAPE (#1206 run 3). `/cpp:help` listed Tier 2 as
    # "**Hooks**: Security (command validation, output masking)" - masking
    # sold as a HOOK FEATURE with neither the event name nor a dispatch phrase,
    # and #1224's scan read past it. "output masking" beside the word "hook" is
    # that shape. It deliberately does NOT fire on "hook" + "mask" alone: the
    # retained doctor row names `hook-mask-output.sh` as a helper for files at
    # rest, which is the tool this change keeps.
    if "output masking" in low and re.search(r"\bhooks?\b", low):
        return True
    # SECOND SHAPE, and it exists because the first one missed the masker's own
    # header. `scripts/hook-mask-output.sh` said it masks output "before it's
    # shown to Claude, preventing secrets from entering context" and billed
    # itself as "called by Claude Code hooks system" - the claim in full, with
    # the word PostToolUse nowhere in it, so the scan read the file and passed.
    #
    # These are DISPATCH assertions: masking described as something that happens
    # to live output on its way somewhere. They are a tripwire, not a coverage
    # proof - no token list can be - which is why the union of three anchors was
    # run by hand over the tree and why CLAIM_BEARING names the files outright.
    dispatch = (
        "before it's shown to claude",
        "before it is shown to claude",
        "entering context",
        "hooks system",
        "reaches claude's context",
        "in tool output before",
        "masking hook is retained",
        "masking hook is kept",
    )
    return any(token in low for token in dispatch)


@requires_git
def test_no_shipped_surface_claims_active_masking():
    """RED before this change: 14 lines across 10 files, CLAUDE.md:134 among them.

    That red run is the evidence. Re-reading the removal would only confirm
    what it MEANT; this is what it CAN say.
    """
    #: Extensions whose bytes are not prose. Anything ELSE that fails to read is
    #: a finding, not a skip: the aggregate read threshold below absorbed a
    #: single unreadable surface, and the narrow scan never visits a file
    #: outside CLAIM_BEARING - so a new tracked document could go unexamined by
    #: both halves at once while both reported clean (counter-model pass 2).
    BINARY = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2",
              ".ttf", ".otf", ".zip", ".gz", ".whl", ".so", ".dylib", ".class"}
    offenders: list[str] = []
    unreadable: list[str] = []
    read_ok = 0
    for path in _shipped_surfaces():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            if path.suffix.lower() not in BINARY:
                unreadable.append(f"{path.relative_to(ROOT)}: {type(exc).__name__}")
            continue
        read_ok += 1
        for n, window in _claim_windows(text):
            if _asserts_active_masking(window):
                offenders.append(f"{path.relative_to(ROOT)}:{n}: {window[:120]}")
                break
    # COUNT THE READS, NOT THE PATHS. Discarding read failures silently meant a
    # population of 400 files, none of them opened, still reported zero
    # offenders - a broken extractor whose zero is indistinguishable from a real
    # one. This is the same distinction the whole issue is about, applied to the
    # instrument enforcing it.
    assert not unreadable, (
        "a tracked text surface could not be read, so this scan proves nothing "
        "about it: " + ", ".join(unreadable)
    )
    assert read_ok > 100, (
        f"only {read_ok} of {len(_shipped_surfaces())} surfaces could be read; "
        "a zero from this scan would mean nothing"
    )
    assert not offenders, (
        "a shipped surface pairs PostToolUse with masking again. CPP does not "
        "register a PostToolUse masking hook (owner ruling, #1206 Decision 1); "
        "the masker survives as a file-at-rest tool for /security:*. If this is "
        "a deliberate reversal, change the ruling and this test together:\n  "
        + "\n  ".join(offenders)
    )


def test_the_declaration_scan_sees_a_declaration_the_formatter_wrapped(tmp_path, monkeypatch):
    """The red case for the JSON walk, driven through the PRODUCTION scanner.

    The first version of this test defined its OWN walker and asserted on that.
    Replacing `_files_declaring` with a stub returning `[]` left it green - it
    was exercising a copy, so it protected nothing. It now patches the
    population and calls the real function.

    Planting a file in the repo is not an option: `.gitignore` ignores `*.json`
    bar an allowlist, and #1206 just removed `.claude/hooks.json` from it, so a
    planted file would be untracked and outside a `git ls-files` population.
    """
    wrapped = tmp_path / "hooks.json"
    wrapped.write_text(
        '{\n  "hooks": {\n    "PostToolUse": [\n'
        '      {"type": "command",\n'
        '       "command":\n'
        '         "~/.claude/scripts/hook-mask-output.sh"}\n'
        '    ]\n  }\n}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)

    assert _files_declaring("hook-mask-output", [wrapped]), (
        "a declaration whose value starts on the next line must still be found"
    )
    assert not _files_declaring("hook-pending-retro", [wrapped]), (
        "the scan must not report a helper the file never mentions"
    )

    # And the same command OUTSIDE a hooks structure is NOT a registration -
    # it is the retained standalone use of the masker over a file at rest.
    task = tmp_path / "tasks.json"
    task.write_text(
        '{"tasks": [{"command": "scripts/hook-mask-output.sh < archive.json"}]}',
        encoding="utf-8",
    )
    assert not _files_declaring("hook-mask-output", [task]), (
        "a standalone invocation is not a hook registration"
    )


def test_a_claim_spanning_four_lines_is_one_unit_and_two_bullets_are_two():
    """Both directions the fixed-size window got wrong (counter-model pass 2)."""
    four_lines = (
        "# PostToolUse processes command output\n"
        "# from Bash and Read invocations,\n"
        "# automatically removing credentials and\n"
        "# masking secrets before delivery.\n"
    )
    assert any(_asserts_active_masking(u) for _, u in _claim_windows(four_lines)), (
        "a claim wrapped over four lines is invisible; the window is too narrow"
    )
    two_bullets = (
        "- PostToolUse runs the audit logger.\n"
        "- secrets-mask.sh masks files at rest.\n"
    )
    assert not any(_asserts_active_masking(u) for _, u in _claim_windows(two_bullets)), (
        "two unrelated list items were joined into a claim neither one makes"
    )
