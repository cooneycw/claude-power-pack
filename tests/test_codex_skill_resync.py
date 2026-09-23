"""Pin: the Codex re-sync trigger asks what drifted, and there is only one of it (issue #1136).

Three copies of one shell condition decided whether to regenerate the Codex
mirrors::

    git diff --name-only ORIG_HEAD..HEAD | grep -q '^\\.claude/commands/.*\\.md$'

at ``flow/auto.md`` Step 6, ``flow/auto.md`` Step 7 and ``flow/finish.md``. Its
premise - that the generated surface changes only when a COMMAND DOCUMENT
changes - is false: ``codex-skill-sync.py`` bundles repository docs into the
skills too, so an edit to a bundled doc drifts the mirror while touching no
command document, and the grep stayed silent. Measured twice in two hours on
2026-09-20, by two sessions on two documents, each costing a full
lint-plus-5,100-test gate cycle and a re-gate.

THE TWO HALVES THIS FILE PINS, and the second is the one that outlives the fix:

1. The decision is DERIVED - the helper asks ``codex-skill-sync.py --check``
   what actually drifted rather than predicting it from a path pattern.
2. There is exactly ONE of it. Three copies is how one wrong condition reached
   three places, and a fourth was one paste away. ``test_no_call_site_carries_a
   _path_pattern_condition`` is a TRIPWIRE on that: it fails loudly if the old
   shape reappears anywhere under ``.claude/commands/``.

WHY THE TRIPWIRE HAS TO TELL A CITATION FROM A CONDITION, AND OUR THING FROM A
NEIGHBOUR'S. ``auto.md`` now QUOTES the old condition in a comment explaining
why it went away, and a naive text search would match that and fail on the
documentation written to prevent the bug - the "text search matches its own
documentation" trap, which good comments make MORE likely rather than less. It
also used to flag ANY uncommented occurrence of the pattern, so an unrelated
command listing command-document paths read as "decides a re-sync" (found by
the counter-model review). The scan is now narrowed twice - non-comment lines,
inside a fenced block that mentions ``codex-skill`` - and both narrowings are
themselves tested, one for each of the two detector questions.

Verified non-vacuous: every behavioural test here was run against the pre-fix
tree at a144b54 (the three inline conditions, no helper) and fails there; the
counter-model fixes each fail against the version before them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "scripts" / "codex-skill-resync.sh"
COMMANDS = REPO / ".claude" / "commands"
CONTROL = REPO / "controls" / "codex-skill-resync"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)

#: The blind condition's distinguishing half: a path pattern matched against a
#: diff. Anchored on the pattern rather than on `grep` so a rewrite using
#: `case`, `[[ =~ ]]` or `rg` is caught too - what must not come back is
#: DECIDING FROM A PATH SHAPE, not one utility.
PATH_PATTERN = re.compile(r"\.claude/commands/\.\*\\?\.md")

#: What makes a path-pattern match a DECISION rather than an operation: the
#: line is a shell condition. `grep -q` counts on its own - a quiet grep
#: produces no output and exists only to be tested.
CONDITIONAL = re.compile(r"(^\s*(if|elif|while)\b)|(&&)|(\|\|)|(grep\s+-[a-zA-Z]*q)")


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    full = dict(os.environ)
    full.pop("CODEX_SKILL_SYNC", None)
    full.pop("CODEX_RESYNC_CHANGED_PATHS", None)
    if env:
        full.update(env)
    return subprocess.run(
        ["bash", str(HELPER), *args], capture_output=True, text=True, env=full
    )


def _verdict(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("CODEX_RESYNC: "):
            return line.split(": ", 1)[1]
    return "<none>"


def _stub(
    tmp_path: Path,
    *,
    drifted: bool,
    write_fails: bool = False,
    repairable: bool = True,
) -> Path:
    """Stands in for `codex-skill-sync.py`: reports drift, never decides.

    STATEFUL, because a real generator is: `--check` fails, `--write` fixes the
    tree, and the next `--check` passes. A stub that reported drift forever
    would make the helper's post-write verification look broken when it is
    working - the verification exists precisely because `--write` succeeding is
    not the same fact as the tree being repaired.

    `repairable=False` models the case that motivated it (counter-model review):
    `--check` exits non-zero for conditions `--write` does not fix, such as an
    UNPACKAGED command or family, and `--write` then exits 0 having ignored it.
    """
    stub = tmp_path / "stub-sync.sh"
    write_rc = 1 if write_fails else 0
    marker = tmp_path / "written"
    check_body = (
        "exit 0"
        if not drifted
        else (
            f'if [ -f "{marker}" ]; then exit 0; fi; echo DRIFT: a/b.md; exit 1'
            if repairable
            else "echo UNPACKAGED: flow/new-family; exit 1"
        )
    )
    stub.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        f"  --check) {check_body} ;;\n"
        f'  --write) touch "{marker}"; exit {write_rc} ;;\n'
        "  *) exit 2 ;;\n"
        "esac\n"
    )
    stub.chmod(0o755)
    return stub


# --------------------------------------------------------------------------- #
# 1. The decision is derived from the generator, not from a path pattern
# --------------------------------------------------------------------------- #


@requires_bash
def test_drift_triggers_a_resync_with_no_command_document_in_sight(tmp_path: Path):
    """The exact input the old condition was blind to.

    Nothing here mentions a changed path at all - the helper never looks at
    one. That is the fix: the question "did the mirrors drift" is answered by
    the thing that generates them.
    """
    res = _run("--quiet", env={"CODEX_SKILL_SYNC": str(_stub(tmp_path, drifted=True))})
    assert _verdict(res.stdout) == "resynced", res.stdout
    assert res.returncode == 3


@requires_bash
def test_a_current_mirror_is_left_alone(tmp_path: Path):
    """Without this, a helper wedged at "always re-sync" passes the test above."""
    res = _run("--quiet", env={"CODEX_SKILL_SYNC": str(_stub(tmp_path, drifted=False))})
    assert _verdict(res.stdout) == "current", res.stdout
    assert res.returncode == 0


@requires_bash
def test_drift_is_named_before_it_is_repaired(tmp_path: Path):
    """The diagnostic is the reason this checks before writing (#1136 ruling).

    Unconditional `--write` would repair silently, and silent repair is how
    this blindness survived: drift that never matters is never noticed. An
    author who edits a bundled doc should learn that it reached the mirrors.
    """
    res = _run(env={"CODEX_SKILL_SYNC": str(_stub(tmp_path, drifted=True))})
    assert "DRIFT: a/b.md" in res.stderr, res.stderr
    assert "#1136" in res.stderr


@requires_bash
def test_a_missing_sync_script_is_unavailable_not_current(tmp_path: Path):
    """Fail-open keeps its own word.

    `/flow:auto` and `/flow:finish` run in repositories with no Codex surface,
    where there is genuinely nothing to do. But "there is nothing here to
    check" is not "I checked and they match", and only the second is evidence
    about the mirrors.
    """
    absent = tmp_path / "no-such-sync.py"
    assert not absent.exists(), "fixture must LACK the sync script"
    res = _run("--quiet", env={"CODEX_SKILL_SYNC": str(absent)})
    assert _verdict(res.stdout) == "unavailable", res.stdout
    assert res.returncode == 0


@requires_bash
def test_a_failed_write_is_an_error_not_a_resync(tmp_path: Path):
    """`resynced` claims a repair happened. If `--write` failed, it did not."""
    stub = _stub(tmp_path, drifted=True, write_fails=True)
    res = _run("--quiet", env={"CODEX_SKILL_SYNC": str(stub)})
    assert _verdict(res.stdout) == "error", res.stdout
    assert res.returncode == 2


@requires_bash
def test_a_successful_write_that_does_not_repair_is_an_error(tmp_path: Path):
    """A successful `--write` is not the same fact as a repaired tree (#1136).

    `--check` exits non-zero for conditions `--write` does not fix - an
    UNPACKAGED command or family, for instance - and `--write` exits 0 having
    ignored it. Reporting `resynced` there would claim a repair that did not
    happen, which is the same false-success shape as the verdict this helper
    replaced, reappearing inside the fix for it. Found by the counter-model
    review; the repair is verified by a second `--check` rather than assumed.
    """
    stub = _stub(tmp_path, drifted=True, repairable=False)
    res = _run(env={"CODEX_SKILL_SYNC": str(stub)})
    assert _verdict(res.stdout) == "error", res.stdout
    assert res.returncode == 2
    assert "UNPACKAGED" in res.stderr, res.stderr


@requires_bash
def test_every_generator_marker_is_relayed_not_an_allowlist(tmp_path: Path):
    """The diagnostic must not filter on a hardcoded set of marker prefixes.

    The first cut piped `--check` through `grep -E '^(DRIFT|STALE|ORPHAN):'`,
    which is a hardcoded universe - this issue's own defect class inside its own
    fix. The generator emits four markers, and that filter dropped `MISSING:`
    entirely and `ORPHAN skill:` too, since the colon is not where the pattern
    expected it. Adding or removing a bundled file then produced the generic
    message and named nothing.
    """
    stub = tmp_path / "stub-sync.sh"
    marker = tmp_path / "written"
    stub.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        f'  --check) if [ -f "{marker}" ]; then exit 0; fi;'
        ' echo "MISSING: codex/skills/x/y.md";'
        ' echo "ORPHAN skill: codex/skills/gone";'
        " exit 1 ;;\n"
        f'  --write) touch "{marker}"; exit 0 ;;\n'
        "  *) exit 2 ;;\n"
        "esac\n"
    )
    stub.chmod(0o755)
    res = _run(env={"CODEX_SKILL_SYNC": str(stub)})
    assert "MISSING: codex/skills/x/y.md" in res.stderr, res.stderr
    assert "ORPHAN skill: codex/skills/gone" in res.stderr, res.stderr


# --------------------------------------------------------------------------- #
# 2. There is exactly ONE of it - the half that outlives the fix
# --------------------------------------------------------------------------- #


def _call_sites() -> list[Path]:
    """Command documents that invoke the re-sync helper, DERIVED from the tree."""
    return sorted(
        p for p in COMMANDS.rglob("*.md") if "codex-skill-resync.sh" in p.read_text()
    )


def test_every_known_call_site_uses_the_helper():
    """All three, by name, so a silent drop of one is caught.

    The count is not asserted as a bare number: #1136's own issue body said the
    condition appeared "twice" when it appeared three times, and a test that
    only counted would have inherited whichever number someone typed.
    """
    # INVOCATIONS, not mentions (counter-model review pass 2, #1136). Counting
    # the filename counted the `[ -x ... ]` existence guards too, so deleting
    # the Step-6 invocation left three mentions in auto.md and still satisfied
    # `>= 2` - the test reported coverage for a site that executed nothing.
    for rel, expected in (("flow/auto.md", 2), ("flow/finish.md", 1)):
        doc = (COMMANDS / rel).read_text()
        calls = [
            ln
            for ln in doc.splitlines()
            if ln.strip() == "bash scripts/codex-skill-resync.sh"
        ]
        assert len(calls) == expected, (
            f"{rel}: expected {expected} helper invocation(s), found {len(calls)}. "
            "A guard line mentioning the helper is not an invocation."
        )


def _resync_pattern_matches(text: str) -> list[tuple[int, str]]:
    """Path-pattern matches that could plausibly DECIDE a re-sync.

    Two narrowings, and each answers one of the detector questions this repo
    asks of any new check (`docs/agents/detector-contracts.md`):

    * NON-COMMENT lines only - `auto.md` now quotes the old condition in a
      comment explaining its removal, and a scan matching that would fail on
      the documentation written to prevent the bug. Good comments make a
      text search MORE false-positive, not less.
    * only inside a fenced block that MENTIONS `codex-skill`, AND only on a line
      that is CONDITIONAL - `if`/`elif`, `&&`/`||`, or a quiet `grep -q`, which
      exists only to be tested. Without both, the scan could not tell our thing
      from a neighbour's: block-mention alone still flagged an unrelated
      `git ls-files | grep -c` over command-document paths sharing a fence
      with a helper call, and even a comment mentioning `codex-skill` armed it
      (counter-model review pass 2, #1136).

    Both limits are worth stating, because a narrowed tripwire is one that can
    be narrowed into silence. A re-introduction would escape if it decided a
    re-sync from a path pattern in a block never naming `codex-skill` - such a
    block could not invoke the sync script or this helper, so it would not be a
    working trigger - or if it tested the pattern without any conditional
    syntax on the line, which no shell condition does. The scan is tied to the
    subject by NAME and to the decision by SYNTAX, not by dataflow.
    """
    hits: list[tuple[int, str]] = []
    in_fence = False
    block: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            if in_fence:
                body = "\n".join(b for _, b in block)
                if "codex-skill" in body:
                    hits.extend(
                        (ln, raw)
                        for ln, raw in block
                        if PATH_PATTERN.search(raw)
                        and not raw.strip().startswith(("#", ">"))
                        and CONDITIONAL.search(raw)
                    )
                block = []
            in_fence = not in_fence
            continue
        if in_fence:
            block.append((n, line))
    return hits


def test_no_call_site_carries_a_path_pattern_condition():
    """TRIPWIRE: the old shape must not reappear anywhere under .claude/commands/.

    This is the guard against a fourth copy, and it is the reason the helper
    exists rather than three better copies.
    """
    offenders = []
    for doc in COMMANDS.rglob("*.md"):
        for n, line in _resync_pattern_matches(doc.read_text()):
            offenders.append(f"{doc.relative_to(REPO)}:{n}: {line.strip()[:90]}")
    assert not offenders, (
        "a command document decides a re-sync from a PATH PATTERN again (#1136).\n"
        + "\n".join(offenders)
    )


def test_the_tripwire_does_not_accuse_an_unrelated_path_match():
    """A neighbour's use of the same pattern must NOT read as a re-sync trigger.

    The first cut flagged any uncommented occurrence anywhere under
    `.claude/commands/`, so a documentation command listing command-document
    paths would have failed with "decides a re-sync" while doing no such thing -
    a non-zero that cannot tell our thing from a neighbour's.
    """
    unrelated = (
        "```bash\n"
        "# count the command documents for the docs index\n"
        "git ls-files | grep -c '^\\.claude/commands/.*\\.md$'\n"
        "```\n"
    )
    assert _resync_pattern_matches(unrelated) == [], _resync_pattern_matches(unrelated)


def test_the_tripwire_can_actually_fire(tmp_path: Path):
    """The scan above reports nothing today. Prove it is not simply blind.

    An absence is only evidence once the instrument that found it has been
    shown able to find something - and this one had to be narrowed to ignore
    comments, which is exactly the kind of narrowing that silently turns a
    tripwire off.
    """
    live = (
        "```bash\n"
        "if [ -x scripts/codex-skill-sync.py ] && git diff --name-only ORIG_HEAD..HEAD \\\n"
        "   | grep -q '^\\.claude/commands/.*\\.md$'; then\n"
        "    python3 scripts/codex-skill-sync.py --write || true\n"
        "fi\n"
        "```\n"
    )
    cited = (
        "```bash\n"
        "# it used to read '^\\.claude/commands/.*\\.md$' (codex-skill-sync) and that was the bug\n"
        "bash scripts/codex-skill-resync.sh\n"
        "```\n"
    )
    assert _resync_pattern_matches(live), "the tripwire cannot see a live condition"
    assert _resync_pattern_matches(cited) == [], "a citation must not be reported"


# --------------------------------------------------------------------------- #
# 3. The registered control's anchor is blind by input, not by being a stub
# --------------------------------------------------------------------------- #


@requires_bash
def test_the_anchor_is_blind_by_input_not_by_being_a_stub(tmp_path: Path):
    """The anchor answers `current` on every committed case. Prove it CAN fire.

    A committed case cannot show this: on a command-document edit the fixed
    helper re-syncs too, so the anchor would CATCH the input and the framework
    would score the control INERT. The orchestrator's brief asked for that
    known-good shape; it is registrable only here, which is why the manifest's
    `limits` names this test.
    """
    anchor = CONTROL / "anchors" / "condition-at-a144b54.sh"
    assert anchor.is_file(), "the vendored anchor is missing from the checkout"

    paths = tmp_path / "changed-paths.txt"
    paths.write_text(".claude/commands/flow/auto.md\n")
    fired = subprocess.run(
        ["bash", str(anchor)],
        capture_output=True,
        text=True,
        env={**os.environ, "CODEX_RESYNC_CHANGED_PATHS": str(paths)},
    )
    assert _verdict(fired.stdout) == "resynced", fired.stdout
    assert fired.returncode == 3

    # And the committed bad case really does lack a command document, which is
    # what makes the anchor miss it there.
    committed = (CONTROL / "cases" / "bad-drift-no-command-doc" / "changed-paths.txt").read_text()
    assert ".claude/commands/" not in committed, committed


def test_the_control_manifest_names_this_module_for_the_gap_it_covers():
    """The manifest's `limits` must point at the test carrying the other half.

    A limitation stated in a manifest and covered nowhere is a limitation
    nobody closed; one stated and covered here is a division of labour. If this
    module is renamed, the manifest stops being true and this fails.
    """
    manifest = json.loads((CONTROL / "control.json").read_text())
    assert "test_codex_skill_resync.py" in manifest["limits"]
    assert "test_the_anchor_is_blind_by_input_not_by_being_a_stub" in manifest["limits"]


def test_the_tripwire_ignores_an_unrelated_operation_in_the_same_fence():
    """A neighbour's path match sharing a fence with a helper call must pass.

    Block-mention alone was not enough: mentioning `codex-skill` anywhere in a
    fence armed the scan for every line in it, so an unrelated `git ls-files |
    grep -c` next to a helper invocation read as "decides a re-sync"
    (counter-model review pass 2). The line must also be CONDITIONAL.
    """
    same_fence = (
        "```bash\n"
        "bash scripts/codex-skill-resync.sh\n"
        "# and, unrelated, count the command documents for the index\n"
        "git ls-files | grep -c '^\\.claude/commands/.*\\.md$'\n"
        "```\n"
    )
    assert _resync_pattern_matches(same_fence) == [], _resync_pattern_matches(same_fence)


def test_a_comment_mentioning_the_subject_does_not_arm_the_tripwire():
    """The reviewer's sharper case: only a COMMENT names the subject."""
    commented = (
        "```bash\n"
        "# nothing to do with codex-skill here\n"
        "git ls-files | grep -c '^\\.claude/commands/.*\\.md$'\n"
        "```\n"
    )
    assert _resync_pattern_matches(commented) == [], _resync_pattern_matches(commented)


def test_the_tripwire_still_catches_a_reintroduced_condition_in_any_form():
    """The narrowings must not have narrowed it into silence.

    Three spellings of the same decision, none of them the original: an `if`,
    a `&&` chain, and a bare quiet grep. All must be caught, or the scan has
    been tuned to the one shape that already went away.
    """
    for body in (
        "if git diff --name-only | grep -q '^\\.claude/commands/.*\\.md$'; then",
        "changed && grep -q '^\\.claude/commands/.*\\.md$' list.txt && resync",
        "grep -q '^\\.claude/commands/.*\\.md$' changed.txt",
    ):
        fence = f"```bash\n# codex-skill re-sync\n{body}\n```\n"
        assert _resync_pattern_matches(fence), f"tripwire blind to: {body}"


def test_both_bundled_source_classes_are_registered_as_known_bad():
    """The generator bundles docs AND scripts; the retired grep missed both.

    The issue body recorded two occurrences, both docs, so a control with only
    a docs case would have proven the fix for one class of two - the shape of
    under-coverage this issue is about, reappearing in its own control. A third
    occurrence on 2026-09-20 drifted six script mirrors. Verified on this tree:
    appending a line to `scripts/stash-worktree-guard.sh` drifts three mirrors
    while the old condition stays silent.
    """
    manifest = json.loads((CONTROL / "control.json").read_text())
    bad = {c["name"] for c in manifest["cases"] if c["expect"] == "BAD"}
    assert "bad-drift-no-command-doc" in bad, bad
    assert "bad-drift-bundled-script" in bad, bad

    # And each case's changed-paths really is of its class, with no command
    # document in either - which is what makes the anchor miss them.
    for case, prefix in (
        ("bad-drift-no-command-doc", "docs/"),
        ("bad-drift-bundled-script", "scripts/"),
    ):
        paths = (CONTROL / "cases" / case / "changed-paths.txt").read_text().split()
        assert paths and all(p.startswith(prefix) for p in paths), (case, paths)
        assert not any(p.startswith(".claude/commands/") for p in paths), (case, paths)


# ---------------------------------------------------------------------------
# The trigger must key on the DIFF, not on the BASE (S4, sibling of #1136)
#
# #1136 replaced a path-pattern condition with a helper that decides for itself.
# What it did NOT touch is the condition WRAPPING that call: all three sites sit
# inside `if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]`, so the
# helper runs only when the BASE MOVED. Mirror drift is caused by EDITING a file
# the skills bundle, which is independent of the base - so an ordinary run that
# edits a bundled script on a current base never re-syncs, and `make verify` is
# the only thing that says so, at the cost of a full gate cycle.
#
# Measured: #1191 staled two mirrors, #1192 staled four, and neither run had a
# moved base.
# ---------------------------------------------------------------------------
BASE_MOVED = re.compile(r"rev-list\s+--count\s+HEAD\.\.origin/")

RESYNC_CALL = "bash scripts/codex-skill-resync.sh"


def _resync_calls_gated_on_base_moved(text: str) -> list[tuple[int, str]]:
    """Re-sync invocations that sit inside an OPEN base-moved conditional.

    Narrowed the same two ways as `_resync_pattern_matches`, for the same two
    detector questions, because the same traps apply:

    * NON-COMMENT lines only - this module and `auto.md` both discuss the base
      condition in prose, and a scan matching its own documentation is the trap
      good comments make MORE likely.
    * Only inside a fenced block that MENTIONS `codex-skill`, so an unrelated
      stale-base check elsewhere in a command document is a NEIGHBOUR'S thing,
      not ours. `flow/auto.md` legitimately branches on a moved base for the
      MERGE itself, and that must not read as this defect.

    It is STRUCTURAL rather than textual: an `if`/`fi` depth walk, so what is
    reported is an invocation actually ENCLOSED by the condition, not one that
    merely shares a block with it. A line-proximity scan would flag a re-sync
    placed correctly AFTER an unrelated base-moved block.
    """
    hits: list[tuple[int, str]] = []
    in_fence = False
    block: list[tuple[int, str]] = []

    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            if in_fence:
                body = "\n".join(b for _, b in block)
                if "codex-skill" in body:
                    open_base_moved: list[bool] = []
                    for ln, raw in block:
                        stripped = raw.strip()
                        if stripped.startswith(("#", ">")):
                            continue
                        if re.match(r"^(if|elif)\b", stripped):
                            open_base_moved.append(bool(BASE_MOVED.search(raw)))
                        elif stripped == "fi" and open_base_moved:
                            open_base_moved.pop()
                        elif stripped == RESYNC_CALL and any(open_base_moved):
                            hits.append((ln, raw))
                block = []
            in_fence = not in_fence
            continue
        if in_fence:
            block.append((n, line))
    return hits


def test_the_base_moved_tripwire_CAN_FIRE():
    """THE POSITIVE CONTROL, and it comes first deliberately.

    A structural walk that silently matched nothing - a changed fence marker, an
    `fi` spelling it does not recognise - would satisfy the tripwire below
    perfectly while detecting nothing at all. This constructs the exact shape the
    tripwire exists to catch and requires it to be seen.
    """
    constructed = "\n".join(
        [
            "```bash",
            "# codex-skill mirrors",
            'if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then',
            "    git merge --no-edit origin/main",
            f"    {RESYNC_CALL}",
            "fi",
            "```",
        ]
    )
    assert _resync_calls_gated_on_base_moved(constructed), (
        "the tripwire cannot see the shape it exists to catch"
    )


def test_the_base_moved_tripwire_does_not_accuse_a_CORRECT_call_site():
    """THE OTHER SIDE. A tripwire that fired on the fixed shape would be
    un-fixable, and the fix would look like the defect."""
    correct = "\n".join(
        [
            "```bash",
            "# codex-skill mirrors",
            'if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then',
            "    git merge --no-edit origin/main",
            "fi",
            f"{RESYNC_CALL}",
            "```",
        ]
    )
    assert _resync_calls_gated_on_base_moved(correct) == [], (
        "a re-sync placed AFTER the base-moved block is correct and must not be flagged"
    )


def test_the_base_moved_tripwire_ignores_a_NEIGHBOURS_base_check():
    """Our thing from a neighbour's: a base-moved block in a fence that never
    mentions codex-skill cannot be a mirror trigger, and must not be reported."""
    neighbour = "\n".join(
        [
            "```bash",
            'if [ "$(git rev-list --count HEAD..origin/main)" -gt 0 ]; then',
            "    git merge --no-edit origin/main",
            "fi",
            "```",
        ]
    )
    assert _resync_calls_gated_on_base_moved(neighbour) == []


def test_no_call_site_gates_the_resync_on_a_MOVED_BASE():
    """THE TRIPWIRE. Mirror drift is caused by the DIFF, never by the base.

    A run that edits a bundled script on a current base must still re-sync. The
    helper costs 0.14s on a clean tree and decides for itself; gating it on the
    base is what made it silent for the ordinary case.
    """
    offenders = []
    for doc in COMMANDS.rglob("*.md"):
        for n, line in _resync_calls_gated_on_base_moved(doc.read_text()):
            offenders.append(f"{doc.relative_to(REPO)}:{n}: {line.strip()[:90]}")
    assert not offenders, (
        "a command document runs the re-sync only when the BASE moved, but mirror "
        "drift comes from the DIFF - an edit to a bundled file on a current base "
        "never re-syncs (S4, sibling of #1136).\n" + "\n".join(offenders)
    )
