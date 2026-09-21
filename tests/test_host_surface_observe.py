"""Tests for scripts/host-surface-observe.py - the #1150 observation harness.

Contract:
- The population is DERIVED from host-surface-check.py, never listed here.
- An unclassified member is REFUSED, not executed, because this harness runs
  what it classifies as observable and an unknown newcomer might `sudo`.
- The sandbox is verified IN THE CHILD, and both failing states are covered.
- Coverage depends on the write VERB.
- `certified=observed` is enforced, not decoration.

WHAT THESE TESTS DELIBERATELY DO NOT DO. They do not execute the sixteen real
helpers - that is the harness's own job and it takes minutes. They pin the
DECISIONS the harness makes about what it sees, against fixtures. The harness
running for real over the tree is what `make host-surface-observe` does, and its
committed control is what proves it can fail.

This module shells out to nothing but `sys.executable`, which is how the child
sandbox probe works and is not a guarded binary.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "host-surface-observe.py"


def _load():
    spec = importlib.util.spec_from_file_location("host_surface_observe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hso = _load()


# --------------------------------------------------------------------------- #
# The sandbox - both failing states, because they fail DIFFERENTLY
# --------------------------------------------------------------------------- #
def test_sandbox_verifier_accepts_a_real_sandbox(tmp_path: Path) -> None:
    """THE POSITIVE CONTROL for the two refusal tests below.

    Without it, a verifier that refused everything would satisfy both refusal
    tests perfectly while making the harness unable to run at all. This is the
    direction that asserts the instrument still works, not merely that it says
    no.
    """
    assert hso.verify_sandbox(tmp_path, Path(os.path.expanduser("~"))) == []


def test_sandbox_verifier_refuses_when_home_is_unset(monkeypatch, tmp_path: Path) -> None:
    """HOME UNSET is the state that ESCAPES, and it escapes silently.

    `Path.home()` and `os.path.expanduser('~')` fall back to
    `pwd.getpwuid(os.getuid()).pw_dir` when HOME is absent, so a helper run this
    way writes into the REAL home while the harness reports a sandboxed run.
    Measured during #1150: HOME unset resolved to the real home, HOME="" to "/".

    The issue's premise was "no getpwuid in any helper", which is true of the
    source text and misses this - two members reach it two stdlib functions
    down. That is why the check runs in the CHILD rather than trusting the
    source.
    """
    monkeypatch.setattr(hso, "sandbox_env", lambda s: {
        k: v for k, v in os.environ.items() if k != "HOME"
    })
    problems = hso.verify_sandbox(tmp_path, Path(os.path.expanduser("~")))
    assert problems, "an unset HOME must be refused - it resolves to the real home"
    assert any("REAL HOME" in p for p in problems), problems


def test_sandbox_verifier_refuses_when_home_is_the_real_home(monkeypatch, tmp_path: Path) -> None:
    """The other failing state: HOME set, but set to somewhere it must not be.

    Distinct from the unset case and checked separately because they fail by
    different mechanisms - this one never reaches the getpwuid fallback at all.
    A single test over "HOME is wrong" would pass while one of the two
    mechanisms went unguarded.
    """
    real = Path(os.path.expanduser("~"))
    monkeypatch.setattr(hso, "sandbox_env", lambda s: {**os.environ, "HOME": str(real)})
    problems = hso.verify_sandbox(tmp_path, real)
    assert any("REAL HOME" in p for p in problems), problems


def test_the_sandbox_check_asks_the_child_not_the_parent(tmp_path: Path) -> None:
    """`check the surface, not the verdict`, applied to the sandbox itself.

    A harness that verified it EXPORTED HOME would be asserting its own intent;
    `env -i`, a wrapper, or a `sudo -E` boundary strips it silently and the
    parent's belief survives unchanged. This asserts the value comes back from
    a real child process.
    """
    env = hso.sandbox_env(tmp_path)
    home_env, path_home, expanded = hso.child_home(env)
    assert home_env == str(tmp_path)
    assert Path(path_home).resolve() == tmp_path.resolve()
    assert Path(expanded).resolve() == tmp_path.resolve()


# --------------------------------------------------------------------------- #
# Coverage depends on the write VERB - the bug that made declarations unverifiable
# --------------------------------------------------------------------------- #
def test_mkdir_covers_the_directory_node_and_nothing_beneath_it() -> None:
    """A `write=mkdir` declaration covers exactly its own path (#1150).

    This is the defect the two-sided demonstration caught, and it was invisible
    to review: with subtree coverage, a declared `~/.codex` covered
    `~/.codex/skills`, so REMOVING the `~/.codex/skills` declaration changed no
    verdict and every declaration added by that change was unverifiable. The
    instrument was certifying its own input.

    The tree settles it without appeal to taste: `cpp-host-write.sh` declares
    `~/.claude`, `~/.claude/scripts` AND `~/.claude/settings.json` separately,
    which is redundant under subtree coverage and necessary under this rule.
    """
    declared = [(".codex", "mkdir", "observed")]
    assert hso.covered_by(".codex", declared)
    assert not hso.covered_by(".codex/skills", declared), (
        "a mkdir declaration covered a path beneath it; with this, removing a "
        "child declaration changes no verdict and cannot be shown to matter"
    )


def test_content_verbs_cover_what_they_wrote_beneath_the_path() -> None:
    """The other direction, so the rule is not simply `cover less`.

    copy/symlink/merge/append/replace/json-merge write CONTENT at the path, so
    what appears beneath is that surface's content. Without this the harness
    would report every copied file as an undeclared surface and the instrument
    would cry wolf on its own successful runs.
    """
    declared = [(".codex/skills/<skill>", "copy", "observed")]
    assert hso.covered_by(".codex/skills/security-deep", declared)
    assert hso.covered_by(".codex/skills/security-deep/SKILL.md", declared)
    assert not hso.covered_by(".codex", declared)


def test_placeholder_matches_exactly_one_segment() -> None:
    """`<skill>` means a skill directory, not a subtree spelled literally."""
    declared = [(".claude/commands/<family>", "symlink", "observed")]
    assert hso.covered_by(".claude/commands/flow", declared)
    assert not hso.covered_by(".claude/commands", declared)


# --------------------------------------------------------------------------- #
# `unresolved` is not `none`
# --------------------------------------------------------------------------- #
def test_an_unresolved_declaration_is_not_read_as_no_surfaces() -> None:
    """`unresolved` is a DECLARED state and collapsing it into `none` defeats a
    deliberate guard (#1150).

    `retired-surface-prune.py` reads its target from data at run time and says
    so, with the reason recorded beside the declaration: "an unresolvable
    target dropped from a manifest reads as 'no surface here', which is the
    drift this seam exists to make visible." This harness did exactly that -
    no `~/` prefix, so no surfaces, so nothing to compare, so counted among the
    certified. Observation certified it BECAUSE observation had nothing to look
    at, which is this instrument's own subject turned on itself.
    """
    check = hso._load_check()

    class _Fake:
        @staticmethod
        def declarations(text):
            return ["unresolved"]

    assert hso.declares_unresolved("irrelevant", _Fake)
    assert not hso.declares_unresolved("irrelevant", type("N", (), {
        "declarations": staticmethod(lambda t: ["none - reads nothing"])
    }))
    # and the real script still declares it, or this test is about nothing
    real = (ROOT / "scripts" / "retired-surface-prune.py").read_text(encoding="utf-8")
    assert hso.declares_unresolved(real, check), (
        "retired-surface-prune.py no longer declares `unresolved`; this test is "
        "no longer measuring the case it was written for"
    )


# --------------------------------------------------------------------------- #
# The population is DERIVED, and an unclassified member is refused
# --------------------------------------------------------------------------- #
def test_population_comes_from_the_checker_not_from_a_list_here() -> None:
    """One reader, per #1161/#1162 - a second is a second population to sync.

    #1150 was filed naming "all 15 install-path helpers", nine in and six out.
    Re-derived at the issue's own commit the population was SIXTEEN, ten of them
    in-$HOME: `stash-worktree-guard.sh` had entered the command documents the
    day before. A hardcoded roster goes stale in a day; this asserts the harness
    has no roster to go stale.
    """
    check = hso._load_check()
    members, _ = check.derive_members(ROOT)
    assert "stash-worktree-guard.sh" in members, (
        "the derived population lost the member whose absence from the issue's "
        "roster is the reason this harness derives instead of listing"
    )
    classified = set(hso.ESCAPES) | set(hso.INVOCATIONS)
    unclassified = members - classified
    assert not unclassified, (
        f"derived member(s) with no observable/escapes decision: {sorted(unclassified)}. "
        "They are refused rather than run - see the module docstring - so this is "
        "a FAILING TEST by design, not a silent omission. Classify them."
    )


def test_every_escaper_names_a_binary_that_is_actually_in_its_script() -> None:
    """A per-script escape reason must be true of that script.

    "A consumer must meet a non-uniform risk as non-uniform" is only worth
    anything if the named binary is really there; otherwise the table is six
    plausible strings and the six permanent `authored` values rest on nothing.
    """
    for name, reason in hso.ESCAPES.items():
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8", errors="replace")
        binaries = [b.strip() for b in reason.split(",")]
        assert any(b in text for b in binaries), (
            f"{name} is declared as escaping via {reason!r}, but none of those "
            "appear in it - the reason is unverified text"
        )


# --------------------------------------------------------------------------- #
# `certified=` is enforced, and the asymmetry is deliberate
# --------------------------------------------------------------------------- #
def test_declared_surfaces_carries_the_certified_value() -> None:
    check = hso._load_check()
    text = (ROOT / "scripts" / "cpp-host-write.sh").read_text(encoding="utf-8")
    surfaces = hso.declared_surfaces(text, check)
    by_path = {p: c for p, _v, c in surfaces}
    assert by_path[".bashrc"] == "observed"
    assert by_path[".claude/settings.json"] == "authored", (
        "this surface needs a template argument no invocation supplies, so "
        "nothing has observed it; marking it observed would be a certification "
        "produced by not looking"
    )


@pytest.mark.parametrize(
    "source, expect",
    [
        pytest.param("#: HOST-SURFACE: none - reads nothing\n", [], id="none"),
        pytest.param("#: HOST-SURFACE: unresolved\n", [], id="unresolved-has-no-path"),
        pytest.param(
            "#: HOST-SURFACE: note - target is $HOME_DIR/.claude, overridable\n", [],
            id="prose-note-is-not-a-surface",
        ),
    ],
)
def test_non_path_declaration_bodies_yield_no_surface(source: str, expect: list) -> None:
    """A `note - ...` body carries prose, not a path.

    Parsing one into a surface would invent a declaration nobody made, and the
    harness would then report it as unobserved forever.
    """
    check = hso._load_check()
    assert hso.declared_surfaces(source, check) == expect


# --------------------------------------------------------------------------- #
# The child environment is an ALLOWLIST - found by counter-model review
# --------------------------------------------------------------------------- #
def test_a_destination_override_does_not_reach_the_child(monkeypatch, tmp_path: Path) -> None:
    """A helper's own `$HOME` override must not survive into the sandbox (#1150).

    THIS IS THE ESCAPE THE SANDBOX CHECK CANNOT SEE. `verify_sandbox` asks a
    child where it resolves `~`; it does not constrain where an installer
    DECIDES to write. `cpp-commands-link.sh:183` reads
    `HOME_DIR="${CPP_COMMANDS_LINK_HOME:-$HOME}"`, so with that variable
    exported the helper writes into the REAL home while every check here
    passes. Measured before the fix: the variable reached the child and
    `verify_sandbox` returned NO refusals.

    The override was documented in that helper's own declaration note -
    "overridable by CPP_COMMANDS_LINK_HOME" - the whole time. The environment
    is an allowlist rather than a denylist for exactly that reason: a denylist
    names only the overrides somebody already thought of.
    """
    monkeypatch.setenv("CPP_COMMANDS_LINK_HOME", "/home/somebody")
    monkeypatch.setenv("BASH_ENV", "/tmp/evil-startup.sh")
    env = hso.sandbox_env(tmp_path)
    assert "CPP_COMMANDS_LINK_HOME" not in env, (
        "a destination override reached the child; the helper would write "
        "outside the sandbox while the sandbox check reports clean"
    )
    assert "BASH_ENV" not in env, "shell startup injection reached the child"
    assert env["HOME"] == str(tmp_path)


def test_the_allowlist_still_passes_what_a_helper_needs(tmp_path: Path) -> None:
    """THE POSITIVE CONTROL for the allowlist.

    An allowlist that stripped everything would satisfy the test above
    perfectly and leave the helpers unable to run - no PATH, no interpreter.
    This asserts the sandbox is still usable, which is the direction a
    tightening change breaks.
    """
    env = hso.sandbox_env(tmp_path)
    assert env.get("PATH"), "PATH was stripped; no helper can run"


# --------------------------------------------------------------------------- #
# The classification override is for control trees ONLY
# --------------------------------------------------------------------------- #
def test_a_classification_file_at_the_repository_root_is_refused(tmp_path, monkeypatch) -> None:
    """The refusal must FIRE, not merely be asserted absent (#1150).

    THIS TEST WAS VACUOUS ON ITS FIRST COMMIT, and that is why it reads the way
    it does now. It asserted the file was absent from the real root, then ran
    the harness WITHOUT creating it, gated on an environment variable
    (`HOST_SURFACE_OBSERVE_SELFTEST`) that was never implemented, and finished
    with an assertion that checked neither exit status nor stderr. Proven
    vacuous by removing the refusal from the gate: the test still passed.

    The refusal HAD been demonstrated - by hand, by planting the file and
    watching the harness exit 1. That evidence lived in a transcript, which is
    ADR 0008's own objection to a run nobody can repeat: nothing notices if it
    stops, and it leaves no artifact. A manual proof is not a committed check.

    So this creates the forbidden file in a temporary root, points REPO_ROOT at
    that root, and requires the refusal to raise.
    """
    (tmp_path / hso.CLASSIFICATION_REL).write_text(
        '{"escapes": {"codex-skill-sync.py": "fixture"}}', encoding="utf-8"
    )
    monkeypatch.setattr(hso, "REPO_ROOT", tmp_path)

    with pytest.raises(SystemExit) as excinfo:
        hso.load_classification(tmp_path)
    assert "REFUSED" in str(excinfo.value)
    assert hso.CLASSIFICATION_REL in str(excinfo.value)


def test_the_real_repository_root_carries_no_classification_file() -> None:
    """The companion fact: the file is not committed here.

    Separate from the refusal test on purpose. This one can only ever say the
    file is absent TODAY; it cannot show the gate would refuse it. Folding the
    two together is what made the original vacuous - an absence assertion that
    passes whether or not the mechanism works.
    """
    assert not (ROOT / hso.CLASSIFICATION_REL).exists(), (
        f"{hso.CLASSIFICATION_REL} is committed at the repository root; it can move a "
        "helper into `escapes` and skip enforcement of its declarations"
    )


def test_control_case_trees_carry_their_own_classification() -> None:
    """The other half: the mechanism must still work where it is meant to.

    Without this, refusing the file everywhere would satisfy the test above and
    silently break every control case, which would then red as UNCLASSIFIED -
    the right exit for the wrong reason.
    """
    for case in ("bad-understated", "good-declared"):
        path = ROOT / "controls" / "host-surface-observe" / "cases" / case / hso.CLASSIFICATION_REL
        assert path.is_file(), f"{case} lost its classification file"
        _esc, inv, supplied = hso.load_classification(path.parent)
        assert supplied is True
        assert "fixture-writer.sh" in inv, "the fixture is no longer classified observable"


# --------------------------------------------------------------------------- #
# The verdict reports two different facts as two numbers
# --------------------------------------------------------------------------- #
def _root(tmp_path: Path, name: str, body: str, decls: str, *, escapes: str = "") -> Path:
    """A minimal tree the harness will derive a population from and RUN.

    Built rather than mocked, because the decisions under test - exit handling,
    the certified/consistent split, the skip-path enforcement - live in
    `observe()` and `main()`, and a test that recomputes their predicates pins
    its own arithmetic instead. Two earlier tests here did exactly that and are
    replaced by these.
    """
    import json as _json
    root = tmp_path / name
    (root / ".claude/commands/cpp").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    doc = "# fixture\n\n```bash\n~/.claude/scripts/probe.sh\n```\n"
    (root / ".claude/commands/cpp/init.md").write_text(doc, encoding="utf-8")
    (root / ".claude/commands/cpp/update.md").write_text(doc, encoding="utf-8")
    cls: dict[str, object] = (
        {"escapes": {"probe.sh": escapes}} if escapes else {"invocations": {"probe.sh": [[]]}}
    )
    (root / hso.CLASSIFICATION_REL).write_text(_json.dumps(cls), encoding="utf-8")
    f = root / "scripts/probe.sh"
    f.write_text("#!/usr/bin/env bash\n" + decls + body, encoding="utf-8")
    f.chmod(0o755)
    return root


def _run(root: Path, capsys) -> tuple[int, str]:
    code = hso.main(["--root", str(root)])
    return code, capsys.readouterr().out


def test_a_helper_that_cannot_run_is_not_reported_as_consistent(tmp_path: Path, capsys) -> None:
    """Exit 126 must REACH the verdict, not merely be recognised (#1150).

    THE TEST THIS REPLACES WAS VACUOUS. It recomputed
    `[c for c in exit_codes if c in (126, 127) or c < 0]` inside the test body
    and asserted its own result, never calling `observe()` - so deleting the
    enforcement from the harness left all six parameters green. Found by
    counter-model review, one pass after the same shape was found in the
    refusal test.

    This runs a real fixture that exits 126 and requires the verdict to refuse.
    """
    root = _root(tmp_path, "unrunnable", "exit 126\n", "#: HOST-SURFACE: none\n")
    code, out = _run(root, capsys)
    assert code == 1, "a helper that could not run must not produce a clean verdict"
    assert "UNRUNNABLE" in out, out
    assert "ok -" not in out


def test_a_declaration_free_helper_is_consistent_not_certified(tmp_path: Path, capsys) -> None:
    """"Ran and wrote nothing" belongs in the consistent count, not the certified one.

    Also replaces a vacuous test: the original constructed two `Observation`
    dataclasses and asserted on their fields, so restoring the old single-number
    verdict would have left it green. This calls `main()` and reads the counts
    out of the verdict line the reader actually meets.
    """
    root = _root(tmp_path, "quiet", "exit 0\n", "#: HOST-SURFACE: none\n")
    code, out = _run(root, capsys)
    assert code == 0, out
    assert "0 member(s) were watched writing" in out, out
    assert "1 declare no surface and produced none" in out, out
    assert "is not a certification" in out


def test_a_helper_that_writes_a_declared_surface_is_certified(tmp_path: Path, capsys) -> None:
    """THE POSITIVE CONTROL for the split above.

    Without it, a verdict that counted nothing as certified would satisfy the
    consistent-count test perfectly while making the instrument unable to
    certify anything at all.
    """
    root = _root(
        tmp_path, "writer",
        'mkdir -p "$HOME/.probe"\nprintf x > "$HOME/.probe/one"\n',
        "#: HOST-SURFACE: ~/.probe owner=cpp write=mkdir certified=observed\n"
        "#: HOST-SURFACE: ~/.probe/one owner=cpp write=replace certified=observed\n",
    )
    code, out = _run(root, capsys)
    assert code == 0, out
    assert "1 member(s) were watched writing" in out, out


def test_a_skipped_helper_may_not_claim_certified_observed(tmp_path: Path, capsys) -> None:
    """An `escapes` member is never RUN, so it may not claim to have been (#1150).

    Declarations used to be read only on the path that runs a helper, so a
    member skipped as `escapes` or `unresolved` kept any concrete
    `certified=observed` declaration it carried - unverified, while the report
    said those members stay `authored`. The exclusion is preserved: the helper
    is still never executed. What is enforced without executing it is that it
    does not advertise an observation nobody made.
    """
    root = _root(
        tmp_path, "escaper", "exit 0\n",
        "#: HOST-SURFACE: ~/.never-written owner=cpp write=mkdir certified=observed\n",
        escapes="sudo",
    )
    code, out = _run(root, capsys)
    assert code == 1, "an escaping helper claiming certified=observed must refuse the green"
    assert "FALSE CLAIM" in out, out
    assert "never-written" in out


def test_an_escaping_helper_claiming_authored_is_accepted(tmp_path: Path, capsys) -> None:
    """THE POSITIVE CONTROL: escaping members are still excluded, not failed.

    Without this, refusing every escaping helper would satisfy the test above
    and destroy the deliberate exclusion that keeps `sudo`, `apt` and
    `systemctl` helpers from being executed at all.
    """
    root = _root(
        tmp_path, "honest-escaper", "exit 0\n",
        "#: HOST-SURFACE: ~/.never-written owner=cpp write=mkdir certified=authored\n",
        escapes="sudo",
    )
    code, out = _run(root, capsys)
    assert code == 0, out
    assert "escapes via sudo" in out


def test_a_transient_undeclared_write_is_NOT_detected(tmp_path: Path, capsys) -> None:
    """PINS A LIMITATION, deliberately - this asserts what the harness CANNOT see.

    Snapshots compare before and after, so they establish which paths SURVIVED
    to be inspected, not everything a helper wrote. A helper that creates an
    undeclared path and removes it before exiting passes.

    That happens entirely inside the redirected $HOME, so the containment note
    (#1182) does NOT cover it: this is a different blind spot with a different
    cause, and folding the two would let the containment issue look like it
    answers this one. Detecting a transient write needs execution tracing, which
    this design does not do.

    Asserting the CURRENT behaviour rather than the desired behaviour is the
    point. If someone later adds tracing, this test fails and they must decide
    deliberately whether the limitation is gone - rather than discovering years
    on that a green here never meant what its message implied. The verdict text
    says the same thing in the words a reader meets.
    """
    root = _root(
        tmp_path, "transient",
        'mkdir -p "$HOME/.probe"\n'
        'mkdir -p "$HOME/.undeclared-transient"\n'
        'rmdir "$HOME/.undeclared-transient"\n',
        "#: HOST-SURFACE: ~/.probe owner=cpp write=mkdir certified=observed\n",
    )
    code, out = _run(root, capsys)
    assert code == 0, "current behaviour: a transient undeclared write is not seen"
    assert "left nothing behind that they did not" in out, (
        "the success message must claim only what the snapshot supports - paths "
        "that SURVIVED - not everything the helper wrote"
    )
    assert "SURVIVED to be inspected" in out, (
        "the limitation must be stated where the verdict is read, not only here"
    )


def test_a_non_executable_shell_helper_reaches_the_verdict_as_refused(
    tmp_path: Path, capsys
) -> None:
    """Through the REAL dispatch, not a constructed exit code (#1150).

    The path: a `.sh` without its executable bit -> `os.access(X_OK)` False ->
    handed to `sys.executable` -> Python dies on a SyntaxError -> exit 1. And 1
    is NOT in the unrunnable set, deliberately, because the `--check` lanes use
    it for drift. So the helper never ran and, declaring no surfaces, was
    reported CONSISTENT.

    THE EARLIER TEST FOR THIS EXITED 126 EXPLICITLY AND THEREFORE MISSED IT.
    126 is "found but not executable" and never occurs here, because the
    fallback prevents the permission error from ever happening - so the test
    constructed the code it expected and passed while the real path stayed
    open. This fixture sets mode 0o644 and lets the dispatcher do what it does;
    nothing here names an exit code.
    """
    root = _root(tmp_path, "nonexec", "exit 0\n", "#: HOST-SURFACE: none\n")
    (root / "scripts/probe.sh").chmod(0o644)  # the only thing this test controls

    code, out = _run(root, capsys)

    assert code == 1, "a helper that could not be run must not produce a clean verdict"
    assert "REFUSED" in out, out
    assert "never ran" in out or "no interpreter" in out, out
    assert "is not a certification" not in out or "REFUSED" in out


def test_an_executable_shell_helper_still_runs(tmp_path: Path, capsys) -> None:
    """THE POSITIVE CONTROL for the refusal above.

    Refusing every `.sh` would satisfy that test perfectly and leave the harness
    unable to observe the seven shell helpers in the real population - which is
    most of it. This asserts the ordinary path still works.
    """
    root = _root(
        tmp_path, "exec-ok",
        'mkdir -p "$HOME/.probe"\n',
        "#: HOST-SURFACE: ~/.probe owner=cpp write=mkdir certified=observed\n",
    )
    code, out = _run(root, capsys)
    assert code == 0, out
    assert "1 member(s) were watched writing" in out, out
