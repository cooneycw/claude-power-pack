"""The retirement gate is an instrument, and it is RUN, not read (#1017).

#934 could not delete `/flow:auto_codex` while sessions were driving on it, so it
committed the deletion's CONDITION beside the command: no live role in any wave
declares `driver=flow:auto_codex`. #1017 asked for that condition to be actually
evaluated, and evaluating it surfaced why the condition could not stay prose.

THREE TESTS USED TO LIVE IN `tests/test_counter_model_review.py` AND GREPPED THE
COMMAND DOCUMENT for `.liveness == "unknown"`, `select(type == "object")` and the
three `RETIREMENT:` outcome strings. Those assertions were sound about what the
procedure MEANT and silent about what it could SAY - and what it could say was
wrong: `flow-wave-registry.sh list` exits 0 with an empty roster when the
registry does not exist, so the procedure's own "the registry could not be
enumerated" branch was unreachable and a host with no registry read
`RETIREMENT: clear`. A text search for the word `unknown` finds that check in
perfect health. Running it does not.

So the same three properties are asserted here BEHAVIOURALLY, against
`scripts/flow-driver-retirement-check.sh`, plus the blindness the text tests
could never have reached.

WHAT THIS FILE DOES NOT TEST: whether the real registry on any given host is
clear. That is a fact about a host at a moment, not a property of the gate; the
gate's own `RETIREMENT_WAVE` / `RETIREMENT_SCOPE` lines are that evidence and
they belong in the run's report. Here the process table is PINNED through the
registry helper's own documented `FLOW_WAVE_LIVE_PIDS` / `FLOW_WAVE_UNKNOWN_PIDS`
hooks, which exist so that no test depends on a pid that happens to exist.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "flow-driver-retirement-check.sh"
CONTROL_DIR = ROOT / "controls" / "flow-driver-retirement-check"
CASES = CONTROL_DIR / "cases"

DRIVER = "flow:auto_codex"

#: Exit codes are part of the contract: a caller that deletes on anything but 0
#: is already wrong, and `blocked` and `unknown` must not share a code with each
#: other or with success.
CLEAR, BLOCKED, UNKNOWN = 0, 1, 3

#: The pinned process table. `999002` is the only pid that exists, `999001` is
#: the only one whose existence is undecidable, and every other pid is dead.
#: `FLOW_WAVE_HOST` is pinned for a reason that is easy to miss: an entry whose
#: host is not this host reads `stale other-host` regardless of its pid, so an
#: unpinned hostname would make every fixture read stale on every machine and
#: the live case would silently stop being a live case - a fixture that cannot
#: fail, wearing the name of the one that must.
PINNED_ENV = {
    "FLOW_WAVE_HOST": "control-host",
    "FLOW_WAVE_UNKNOWN_PIDS": "999001",
    "FLOW_WAVE_LIVE_PIDS": "999002",
}


def _run(*args: str, env: dict[str, str] | None = None,
         cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    environ = dict(os.environ)
    environ.update(PINNED_ENV)
    if env:
        environ.update(env)
    return subprocess.run(
        ["bash", str(GATE), *args],
        capture_output=True, text=True, cwd=str(cwd or ROOT), env=environ,
    )


#: The helper IS PINNED TO THE CHECKOUT, and not as a convenience (counter-model
#: finding, 2026-09-16). Unpinned, the gate's own resolution order prefers
#: `~/.claude/scripts/flow-wave-registry.sh`, which on a dev box is a symlink
#: into a DIFFERENT checkout - so these cases would exercise the INSTALLED
#: helper, a regression in this tree could stay green, and an unrelated install
#: could turn them red. The production resolution order is a separate property
#: and has its own test below.
CHECKOUT_HELPER = str(ROOT / "scripts" / "flow-wave-registry.sh")


def _case(name: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run("--driver", DRIVER, "--registry-dir", str(CASES / name),
                "--helper", CHECKOUT_HELPER, *extra)


def _stub(tmp_path: Path, name: str, *lines: str) -> str:
    """A helper that prints a fixed roster.

    The registry helper always computes a `liveness` for every entry, so the
    shapes below - a roster with no `liveness` at all, an unrecognised value, a
    valid JSON prefix followed by garbage - cannot be produced by a fixture
    registry. They are what a DIFFERENT or FUTURE helper could hand this gate,
    and the gate's behaviour on them is a property of the gate.
    """
    path = tmp_path / f"{name}.sh"
    body = "#!/usr/bin/env bash\n" + "".join(f"echo {line!r}\n" for line in lines)
    path.write_text(body + 'echo "FLOW_WAVE: listed"\n', encoding="utf-8")
    path.chmod(0o755)
    (tmp_path / "registry.json").write_text('{"w":{"roles":{}}}', encoding="utf-8")
    return str(path)


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    """The word after `RETIREMENT:`, read from the marker line and nowhere else.

    Scanning the whole of stdout would let the per-wave `RETIREMENT_WAVE` lines
    or a driver name that happens to contain a verdict word decide the answer.
    """
    for line in proc.stdout.splitlines():
        if line.startswith("RETIREMENT: "):
            return line.split()[1]
    return "<no marker>"


pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="the gate parses rosters with jq; absent, it correctly reports unknown "
           "and every case below would collapse to the same verdict",
)


# --------------------------------------------------------------------------- #
# The four committed cases. ADR 0008: this gate's verdict authorises a
# destructive action and nothing downstream re-derives it.
# --------------------------------------------------------------------------- #

def test_a_LIVE_role_on_the_driver_BLOCKS_retirement() -> None:
    """The reason the command outlived the stage by two months.

    Deleting it removes the lifecycle instructions a running session is in the
    middle of executing - "not a merge conflict; it is three in-flight PRs
    losing their driver mid-run".
    """
    proc = _case("bad-live-role")
    assert _verdict(proc) == "blocked", proc.stdout
    assert proc.returncode == BLOCKED, proc.stdout


def test_UNDETERMINED_liveness_BLOCKS_retirement() -> None:
    """Liveness is a FOUR-value vocabulary - live, released, stale, unknown -
    and only the middle two are conclusively inactive.

    Filtering on `== "live"` alone treats `unknown` (the registry could not
    determine whether the process exists) as absence, and would authorise
    deleting the command out from under a session still running on it. The
    tempting filter reads correctly, which is why this case is committed rather
    than argued.
    """
    proc = _case("bad-unknown-liveness")
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout
    assert "undetermined liveness" in proc.stdout


def test_an_ABSENT_REGISTRY_is_unknown_and_not_clear() -> None:
    """The defect #1017 found by running the procedure #934 committed.

    That procedure guarded this case as `raw=$(... list ...) || unknown`, and
    `list` exits 0 with an empty roster when the registry does not exist, so the
    branch was unreachable: a host with no registry read `RETIREMENT: clear`.
    "I could not look" and "nobody is there" produced the same word, on the gate
    whose own prose spends three paragraphs warning against exactly that.
    """
    proc = _case("bad-registry-absent")
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout
    assert "does not exist" in proc.stdout


def test_RELEASED_and_STALE_roles_do_not_block_retirement() -> None:
    """The other direction, and the one that never resolves on its own.

    `list` renders released and stale roles with their drivers too, so a
    substring scan counts sessions that ended months ago and blocks the
    retirement FOREVER. In the wave that wrote the trigger, `worker-A` is
    exactly that: `liveness: released`, `driver: flow:auto_codex`.
    """
    proc = _case("good-released-and-stale")
    assert _verdict(proc) == "clear", proc.stdout
    assert proc.returncode == CLEAR, proc.stdout


def test_the_clear_case_actually_MATCHED_roles_on_this_driver() -> None:
    """A green from a blind extractor and a green from a working one look
    identical, so the clear case above is only worth its verdict if the query
    could still FIND a role carrying the driver.

    Its fixture holds three, and a `matched=0` here would mean the filter had
    stopped matching rather than the wave had cleared - the failure this whole
    gate is about, one level down inside it.
    """
    proc = _case("good-released-and-stale")
    assert "matched=3" in proc.stdout, proc.stdout
    assert f"driver={DRIVER}" in proc.stdout, proc.stdout


# --------------------------------------------------------------------------- #
# The blindnesses a text search could not reach.
# --------------------------------------------------------------------------- #

def test_registry_METADATA_does_not_kill_the_query() -> None:
    """`unregistered_claims` (#687) is an ARRAY sitting beside the role objects,
    and `merge_starvation` is emitted on every listing including an empty one.

    A filter dropping only `wave_policy` then asks an array for `.liveness`, jq
    dies, and the check reports `unknown` on a roster that was perfectly
    readable - a wrong answer in the safe direction, which is still wrong and
    never resolves. Every case here exercises it, because `list` emits the
    metadata unconditionally; asserted on the GOOD case, where a metadata-induced
    `unknown` would be indistinguishable from caution.
    """
    proc = _case("good-released-and-stale")
    assert _verdict(proc) == "clear", proc.stdout
    assert "unparseable" not in proc.stdout, proc.stdout


def test_an_UNRESOLVABLE_HELPER_is_unknown_and_not_clear() -> None:
    """A helper that is not installed produces no matching roles, which is
    indistinguishable from a clear wave.

    This is the first of the two directions the trigger names, and it cannot be
    asserted by reading the gate: the text says `unknown`, and what decides it
    is whether the resolution loop can fall through to something that exists.
    """
    proc = _run("--driver", DRIVER,
                "--registry-dir", str(CASES / "good-released-and-stale"),
                "--helper", "/nonexistent/flow-wave-registry.sh")
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout
    assert "could not be resolved" in proc.stdout


def test_a_registry_that_does_not_PARSE_is_unknown(tmp_path: Path) -> None:
    """A truncated or half-written registry is not an empty one."""
    (tmp_path / "registry.json").write_text("{ this is not json", encoding="utf-8")
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path))
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout


def test_a_registry_with_NO_WAVE_is_unknown(tmp_path: Path) -> None:
    """A parseable registry holding no wave is not a clear verdict: there is no
    population to have looked at, and the distinction between an empty answer
    and an empty question is this gate's entire subject (#952)."""
    (tmp_path / "registry.json").write_text("{}", encoding="utf-8")
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path))
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout


def test_WAVES_ARE_ENUMERATED_rather_than_supplied(tmp_path: Path) -> None:
    """The registry helper has no verb that lists waves, so #934's procedure was
    per-wave by construction and "a wave nobody thought to check" was a standing
    hole in a gate whose whole subject is the difference between looking and
    finding nothing.

    A live role parked in a SECOND wave must block, without the caller naming
    that wave.
    """
    registry = {
        "wave-one": {"roles": {
            "worker-A": {"socket": "unknown", "pid": 999003, "host": "control-host",
                         "released": True, "driver": DRIVER},
        }},
        "wave-two": {"roles": {
            "worker-Z": {"socket": "unknown", "pid": 999002, "host": "control-host",
                         "released": False, "driver": DRIVER},
        }},
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")

    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path))
    assert _verdict(proc) == "blocked", proc.stdout
    assert "waves=2" in proc.stdout, proc.stdout
    assert "wave-two" in proc.stdout, proc.stdout

    # ...and narrowing to the clear wave alone is what would have missed it.
    narrowed = _run("--driver", DRIVER, "--registry-dir", str(tmp_path),
                    "--wave", "wave-one")
    assert _verdict(narrowed) == "clear", narrowed.stdout


def test_the_DRIVER_is_matched_EXACTLY() -> None:
    """A substring scan counts `flow:auto_codex` when asked about `flow:auto`,
    and the fixtures carry both."""
    proc = _run("--driver", "flow:auto",
                "--registry-dir", str(CASES / "good-released-and-stale"))
    assert "matched=1" in proc.stdout, proc.stdout


def test_a_LIVE_role_on_ANOTHER_DRIVER_does_not_block(tmp_path: Path) -> None:
    """The detector question in its second form: can a non-zero tell our thing
    from a neighbour's?

    A live session is the normal state of a busy host. If any live role blocked
    any retirement, the gate would be a permanent `blocked` and would be read as
    broken rather than as protective - which is how a correct refusal becomes
    friction and then gets removed.
    """
    registry = {"w": {"roles": {
        "worker-Z": {"socket": "unknown", "pid": 999002, "host": "control-host",
                     "released": False, "driver": "gemma:auto"},
        "worker-A": {"socket": "unknown", "pid": 999003, "host": "control-host",
                     "released": True, "driver": DRIVER},
    }}}
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path),
                "--helper", CHECKOUT_HELPER)
    assert _verdict(proc) == "clear", proc.stdout
    assert "matched=1" in proc.stdout, proc.stdout

    # ...and that same live role DOES block a retirement of ITS driver, so the
    # clear above is a discrimination rather than a failure to look.
    other = _run("--driver", "gemma:auto", "--registry-dir", str(tmp_path),
                 "--helper", CHECKOUT_HELPER)
    assert _verdict(other) == "blocked", other.stdout


def test_NO_DRIVER_is_unknown_rather_than_a_verdict() -> None:
    """Nothing was examined, so there is nothing to report about."""
    proc = _run("--registry-dir", str(CASES / "good-released-and-stale"))
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout


# --------------------------------------------------------------------------- #
# The retirement itself.
# --------------------------------------------------------------------------- #

def test_flow_auto_codex_IS_RETIRED() -> None:
    """The inverse of `test_flow_auto_codex_still_WORKS_and_is_not_retired`,
    which this replaces.

    Both the source command and its generated Codex skill go; the skill is
    orphan-deleted by `scripts/codex-skill-sync.py --write` rather than by hand,
    so a stale copy surviving here means the sync was not re-run.
    """
    assert not (ROOT / ".claude" / "commands" / "flow" / "auto_codex.md").exists()
    assert not (ROOT / "codex" / "skills" / "flow-auto_codex").exists()


def test_no_LIVE_SURFACE_still_routes_a_reader_to_the_dead_command() -> None:
    """Deleting a command and leaving the sentences that recommend it is worse
    than leaving the command: the reader follows a pointer to nothing.

    HISTORY IS EXEMPT AND THE EXEMPTION IS NARROW. A changelog, a research note,
    an ADR and this test file record what WAS true; a command document, the
    command reference and the help table tell a reader what to type now. The
    universe is hardcoded (the two `.claude/commands` and `docs` roots) and
    membership derived, per the #986 rule - a new command document is scanned
    without an edit here.
    """
    exempt = {
        Path("CHANGELOG.md"),
        Path("docs/decisions/0007-counter-model-review.md"),
        Path("docs/scripts.md"),
    }
    roots = [ROOT / ".claude" / "commands", ROOT / "docs"]
    offenders: list[str] = []
    scanned = 0
    for root in roots:
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(ROOT)
            if rel in exempt or rel.parts[:2] == ("docs", "research"):
                continue
            scanned += 1
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "auto_codex" in line:
                    offenders.append(f"{rel}:{n}: {line.strip()[:110]}")
    assert scanned > 20, f"only {scanned} document(s) scanned - the sweep is looking in the wrong place"
    assert not offenders, "live surfaces still name the retired command:\n" + "\n".join(offenders)


def test_the_CONTROL_CASES_are_present_and_tracked() -> None:
    """A control whose inputs are untracked is a green that does not survive a
    clone (#978). Asserted here as well as in the register because this file is
    what runs in CI, where git is absent from the image - so the tracking half
    skips there and the presence half does not.
    """
    for name in ("bad-live-role", "bad-unknown-liveness",
                 "bad-registry-absent", "good-released-and-stale"):
        assert (CASES / name).is_dir(), f"missing control case {name}"
    assert (CONTROL_DIR / "control.json").is_file()
    assert not (CASES / "bad-registry-absent" / "registry.json").exists(), (
        "the absent-registry case has acquired a registry, so it no longer "
        "reproduces the blindness it exists to pin"
    )

    if shutil.which("git") is None:
        pytest.skip("tracking is checked where git exists; CI's image has none")
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", "controls/flow-driver-retirement-check"],
        capture_output=True, text=True,
    )
    assert listed.returncode == 0, listed.stderr
    tracked = set(listed.stdout.split())
    on_disk = {
        str(p.relative_to(ROOT))
        for p in CONTROL_DIR.rglob("*") if p.is_file()
    }
    assert on_disk, "no control files on disk - the assertions above proved nothing"
    assert not (on_disk - tracked), f"untracked control file(s): {sorted(on_disk - tracked)}"


# --------------------------------------------------------------------------- #
# Four counter-model findings (codex/gpt-5.5, 2026-09-16), all accepted. Each
# was reproduced on the pre-fix gate before the fix was written.
# --------------------------------------------------------------------------- #

def test_a_MISSPELT_WAVE_is_unknown_and_not_clear() -> None:
    """`--wave` recreated, through the narrowing flag, the very failure the gate
    exists to prevent.

    `list --wave <typo>` returns an empty roster and exits 0, so a misspelt name
    produced `waves=1 matched=0` and a CLEAR verdict - against
    `bad-live-role`, the fixture that must block. Narrowing to a wave that
    EXISTS is legitimate and still works; a name the registry does not carry is
    an empty question, not an empty answer.
    """
    proc = _case("bad-live-role", "--wave", "does-not-exist")
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout
    assert "is not in" in proc.stdout

    # ...and the same registry, narrowed to the wave that IS there, still blocks.
    narrowed = _case("bad-live-role", "--wave", "cpp-completion")
    assert _verdict(narrowed) == "blocked", narrowed.stdout


def test_a_MISSING_liveness_key_does_not_authorise_retirement(tmp_path: Path) -> None:
    """Inactivity is a TERMINAL SET, never "not live".

    The classifier counted `live` and `unknown` by name and let the remainder
    fall through to inactive, so an entry with NO `liveness` field - a roster
    from a helper that predates it - read as conclusively inactive and cleared
    the retirement. Only `released` and `stale` establish inactivity.
    """
    helper = _stub(tmp_path, "no-liveness",
                   '{"worker-B":{"driver":"flow:auto_codex"}}')
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path), "--helper", helper)
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout


def test_an_UNRECOGNISED_liveness_value_does_not_authorise_retirement(tmp_path: Path) -> None:
    """The same defect from the other side: a state this gate has never heard of.

    A helper that renames or adds a liveness value would silently move its
    roles into "inactive" and authorise a deletion on a vocabulary neither side
    agreed on.
    """
    helper = _stub(tmp_path, "odd-liveness",
                   '{"worker-B":{"driver":"flow:auto_codex","liveness":"unreachable"}}')
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path), "--helper", helper)
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout


def test_a_VALID_PREFIX_followed_by_GARBAGE_is_unknown(tmp_path: Path) -> None:
    """A non-empty stdout is not evidence that the parse succeeded.

    jq prints a complete `[]` for a valid JSON prefix and THEN dies on trailing
    garbage. Testing only `-z "$roster"` accepted that partial result - zero
    matching roles, from a roster that was never fully read - and reported the
    wave clear.
    """
    helper = _stub(tmp_path, "prefix-then-garbage",
                   '{"worker-B":{"driver":"flow:auto_codex","liveness":"released"}}',
                   'not-json')
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path), "--helper", helper)
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout
    assert "unparseable" in proc.stdout


def test_TWO_JSON_VALUES_do_not_clear_a_wave_holding_a_LIVE_role(tmp_path: Path) -> None:
    """A defect the FIX for the finding above introduced, found on the second
    review pass - and strictly worse than the blindness it was added to remove.

    Command substitution strips the TRAILING newline, so two emitted arrays
    carry one newline between them and a `wc -l > 1` guard passes; bare
    `jq -e 'type == "array"'` then reports the status of the LAST value in the
    stream, so both were accepted. The counts came back multiline, `$(( ))`
    died with a syntax error on stderr, and the run printed `RETIREMENT: clear`
    and exited 0 - with a LIVE role sitting in the first value.

    The lesson is the guard's, not the parser's: a check added to make an
    instrument honest is itself an instrument, and it shipped with a hole its
    predecessor did not have.
    """
    helper = _stub(tmp_path, "two-values",
                   '{"worker":{"driver":"flow:auto_codex","liveness":"live"}}',
                   '{}')
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path), "--helper", helper)
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout
    assert "clear" not in proc.stdout, proc.stdout


def test_a_NON_ARRAY_roster_is_unknown(tmp_path: Path) -> None:
    """`null` is a valid JSON value and not a roster.

    Kept, and RENAMED, because its first name claimed something it could not
    establish. It was written as the regression test for a "the counts must be
    numeric" guard added beside the fix above - and it PASSED on the code
    without that guard, because the array check catches `null` first. A test
    that passes on the unfixed code is not a regression test whatever its name
    asserts, and the guard it named was unreachable: no input could reach the
    arithmetic carrying a non-number. The guard was removed; this assertion is
    real and stays, under a name that says what it actually pins.
    """
    helper = _stub(tmp_path, "null-roster", 'null')
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path), "--helper", helper)
    assert _verdict(proc) == "unknown", proc.stdout
    assert proc.returncode == UNKNOWN, proc.stdout


def test_an_UNREADABLE_WAVE_is_counted_apart_from_an_UNDETERMINED_ROLE(tmp_path: Path) -> None:
    """Both block, and they are not the same fact.

    One summary counter served both, so a wave that could not be parsed was
    reported as "1 role(s) of undetermined liveness" - a claim about a role,
    made where no role had been read at all.
    """
    helper = _stub(tmp_path, "unparseable", 'not-json')
    proc = _run("--driver", DRIVER, "--registry-dir", str(tmp_path), "--helper", helper)
    assert "0 role(s) of undetermined liveness" in proc.stdout, proc.stdout
    assert "1 wave(s) unreadable" in proc.stdout, proc.stdout


def test_the_ANCHORS_blindness_does_not_depend_on_AMBIENT_HOST_STATE() -> None:
    """An anchor that can stop being blind without an edit is not an anchor.

    It read `$HOME/.claude/daemon/roster.json` unconditionally - a file that
    EXISTS on the machine this was written on - so a daemon roster that ever
    carried a matching `driver` key would make it catch every fixture and score
    the control INERT, for a reason nobody had changed. The path is now pinned
    at a committed fixture by `control.json`, and the fixture is tracked.
    """
    anchor = CONTROL_DIR / "anchors" / "constructed-wrong-object-flow-driver-retirement-check.sh"
    roster = CONTROL_DIR / "anchors" / "wrong-object-roster.json"
    assert anchor.is_file() and roster.is_file()

    spec = json.loads((CONTROL_DIR / "control.json").read_text(encoding="utf-8"))
    pinned = [a for a in spec["invocation"]
              if a.startswith("FLOW_DRIVER_RETIREMENT_ANCHOR_ROSTER=")]
    assert pinned, f"the control does not pin the anchor's roster: {spec['invocation']}"
    assert pinned[0].endswith("anchors/wrong-object-roster.json")

    # The fixture is the WRONG OBJECT on purpose: no `driver` KEY anywhere, so a
    # query for one returns zero whatever the wave registry says. Asserted
    # STRUCTURALLY - the first cut was `"driver" not in <text>`, which matched
    # the word inside the fixture's own explanation of why it has no driver key.
    # Good documentation of a property makes a text guard about that property
    # MORE false-positive, not less.
    def _keys(node: object) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {k for v in node.values() for k in _keys(v)}
        if isinstance(node, list):
            return {k for v in node for k in _keys(v)}
        return set()

    assert "driver" not in _keys(json.loads(roster.read_text(encoding="utf-8")))

    # ...and pointed at it, the anchor is blind to the case that must block.
    env = dict(os.environ)
    env.update(PINNED_ENV)
    env["FLOW_DRIVER_RETIREMENT_ANCHOR_ROSTER"] = str(roster)
    proc = subprocess.run(
        ["bash", str(anchor), "--driver", DRIVER,
         "--registry-dir", str(CASES / "bad-live-role")],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert "RETIREMENT: clear" in proc.stdout, (
        "the anchor CAUGHT the known-bad input, so the control would not notice "
        f"the gate regressing to it: {proc.stdout}"
    )


def test_the_CONTROL_pins_the_CHECKOUT_helper() -> None:
    """Unpinned, the control exercises whatever is installed on the host.

    The gate's resolution order prefers `~/.claude/scripts/`, which on a dev box
    symlinks into a different checkout entirely - so a regression in THIS tree
    could stay green while an unrelated install turned the control red.
    """
    spec = json.loads((CONTROL_DIR / "control.json").read_text(encoding="utf-8"))
    argv = spec["invocation"]
    assert "--helper" in argv, f"the control does not pin a helper: {argv}"
    assert argv[argv.index("--helper") + 1] == "scripts/flow-wave-registry.sh"


def test_the_PRODUCTION_resolution_order_still_falls_back_to_the_sibling(tmp_path: Path) -> None:
    """The property the pinning above removed from the control, asserted where
    it belongs: with no `--helper` and no installed copy, the gate finds the
    helper beside itself rather than reporting unknown.
    """
    environ = dict(os.environ)
    environ.update(PINNED_ENV)
    environ["HOME"] = str(tmp_path)          # no ~/.claude/scripts/ here
    environ["CLAUDE_PLUGIN_ROOT"] = str(tmp_path)
    proc = subprocess.run(
        ["bash", str(GATE), "--driver", DRIVER,
         "--registry-dir", str(CASES / "good-released-and-stale")],
        capture_output=True, text=True, cwd=str(ROOT), env=environ,
    )
    assert _verdict(proc) == "clear", proc.stdout
