"""Tests for scripts/check-control-ci-deps.py (issue #1036).

This gate's whole subject is an environment it does not run in. Every local run
has git, jq, shellcheck and gitleaks on PATH, so a version of it that examined
NOTHING would print the same green on a dev box forever - and the first evidence
of the blindness would be the CI red it exists to prevent, which is exactly the
sequence that produced the issue. So its cases are constructed trees rather than
observations of this one, and both directions are exercised for every
distinction it draws.
"""

from __future__ import annotations

import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-control-ci-deps.py"


def _binary_gate():
    """The file that records what the CI image contains, loaded as the gate does."""
    path = ROOT / "scripts" / "check-test-binary-guards.py"
    spec = spec_from_file_location("binary_guards_for_test", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules["binary_guards_for_test"] = module
    spec.loader.exec_module(module)
    return module


CI_IMAGE = _binary_gate().CI_IMAGE


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--root", str(root)],
        capture_output=True, text=True, timeout=120, check=False,
    )


def contract(out: str, key: str) -> str | None:
    for line in out.splitlines():
        if line.startswith(f"{key}: "):
            return line.split(": ", 1)[1].strip()
    return None


def pipeline(
    root: Path,
    image: str = CI_IMAGE,
    *,
    depends_on: str = "[stage]",
    battery_path: bool = False,
    stage_commands: list[str] | None = None,
) -> None:
    path_prefix = 'PATH="$PWD/.ci-bin:$PATH" ' if battery_path else ""
    staged = "\n".join(f"      - {command}" for command in (stage_commands or ["- true"][1:] or ["true"]))
    (root / ".woodpecker.yml").write_text(
        "steps:\n"
        "  negative-controls:\n"
        f"    image: {image}\n"
        f"    depends_on: {depends_on}\n"
        "    commands:\n"
        f"      - {path_prefix}python3 scripts/check-negative-controls.py --strict\n"
        "\n"
        "  stage:\n"
        f"    image: {image}\n"
        "    commands:\n"
        f"{staged}\n",
        encoding="utf-8",
    )


def control(root: Path, name: str, gate_rel: str, invocation: list[str]) -> None:
    directory = root / "controls" / name
    directory.mkdir(parents=True, exist_ok=True)
    import json

    (directory / "control.json").write_text(
        json.dumps({"gate": gate_rel, "invocation": invocation}), encoding="utf-8"
    )


def gate_script(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


#: The registration the BATTERY discovers. This gate resolves its register
#: through `check-negative-controls.discover()`, so a fixture gate without a
#: marker has no registered control at all - which is the point of sharing the
#: rule rather than globbing `controls/*/`.
MARKER = "# NEGATIVE-CONTROL: controls/toy\n"

NEEDS_GIT = f"""#!/bin/sh
{MARKER}REV=$(git rev-parse HEAD)
echo "toy-gate: 1 finding(s) at $REV"
exit 1
"""

NEEDS_NOTHING = f"""#!/bin/sh
{MARKER}echo "toy-gate: ok - 0 finding(s)"
exit 0
"""

NEEDS_ZSH_SHEBANG = f"""#!/usr/bin/env zsh
{MARKER}echo "toy-gate: ok - 0 finding(s)"
exit 0
"""


def test_a_gate_that_hard_requires_an_absent_binary_is_flagged(tmp_path: Path) -> None:
    """THE COMMITTED RED, and it is the real failure's shape.

    A control registered committed BARE GIT REPOSITORIES as its cases; `git` is
    not in the image that runs the battery, and because the harness REFUSES to
    skip a control it cannot run, that one control made the gate every other
    control's verdict is read through the thing that could not report.

    Note what the control DECLARED: `sh`, which every image has. The dependency
    was inside the gate, which is why examining the invocation alone is not
    enough - and why the committed anchor, which does exactly that, misses this.
    """
    pipeline(tmp_path)
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_GIT)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `git`" in out.stdout, out.stdout


def test_a_gate_needing_only_what_the_image_has_is_not_flagged(tmp_path: Path) -> None:
    """The half that matters for a gate wedged at 'fail'.

    This gate is in `make verify`, so a version that refused every tree would
    block every merge in the repository while passing the red case above on its
    own.
    """
    pipeline(tmp_path)
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_NOTHING)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout
    assert "CI_DEP:" not in out.stdout, out.stdout


def test_a_pipeline_running_an_unpinned_image_is_UNKNOWN_not_clean(tmp_path: Path) -> None:
    """A contents list describing a retired image must not answer confidently.

    `CI_IMAGE_BINARIES` describes ONE image. If the pipeline moved to another,
    every answer about what is provided is about a container that no longer runs
    the battery - so the verdict is UNKNOWN and the exit is non-zero, never a
    fallback to a partial set.
    """
    pipeline(tmp_path, image="python:3.12-alpine")
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_NOTHING)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_PIPELINE:" in out.stdout and "UNKNOWN, not clean" in out.stdout, out.stdout


def test_env_is_unwrapped_so_the_real_command_is_examined(tmp_path: Path) -> None:
    """`env FOO=1 <cmd>` runs `<cmd>`; reading `env` checks the wrong binary.

    One registered control really does invoke this way. Scoring `env` - present
    in every image - would silently pass whatever it wraps, which is the shape
    of a check that examines a name rather than a dependency.
    """
    pipeline(tmp_path)
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_NOTHING)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["env", "FOO=1", "tmux", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `tmux`" in out.stdout, (
        "`env` was read as the dependency instead of the command it wraps\n" + out.stdout
    )


def test_a_ci_stage_script_counts_as_staging(tmp_path: Path) -> None:
    """The undercount this gate shipped with for one iteration.

    `jq-stage` runs `python3 scripts/ci-stage-jq.py`, whose destination is built
    as `DEST_DIR / "jq"` - there is NO `.ci-bin/jq` string in the yaml or in the
    script for a literal scan to find. Read the pipeline alone and jq is
    invisible, the provided set silently loses a binary that IS on PATH, and the
    first control to need it gets a false red in `make verify`.

    Found by reading this gate's own output, which printed `CI_DEPS_STAGED: 2`
    beside a battery step depending on three staging steps - not by a failing
    test. The counts are in the output for exactly that reason.
    """
    pipeline(
        tmp_path,
        battery_path=True,
        stage_commands=["python3 scripts/ci-stage-jq.py"],
    )
    # The script must actually name the destination. The first version of this
    # fixture was a bare shebang, and it passed - which the counter-model review
    # caught: the test asserted the convention rather than the staging, so it
    # would have gone on passing against a `ci-stage-jq.py` that staged nothing.
    gate_script(
        tmp_path,
        "scripts/ci-stage-jq.py",
        '#!/usr/bin/env python3\nDEST_DIR = Path(".ci-bin")\n'
        'DEST = DEST_DIR / "jq"\nDEST.write_bytes(payload)\n',
    )
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_NOTHING)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["jq", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout
    assert contract(out.stdout, "CI_DEPS_STAGED") == "1 (jq)", out.stdout


def test_a_ci_stage_script_that_is_absent_does_not_count(tmp_path: Path) -> None:
    """The convention is evidence only when the script is actually there.

    Without this, a pipeline could name any `ci-stage-<x>.py` and this gate would
    credit `<x>` as provided - a naming convention promoted to a fact, which is
    how a derived set quietly becomes a wish list.
    """
    pipeline(
        tmp_path,
        battery_path=True,
        stage_commands=["python3 scripts/ci-stage-jq.py"],
    )
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_NOTHING)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["jq", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `jq`" in out.stdout, out.stdout


def test_an_unreadable_staging_step_is_reported_not_silently_dropped(tmp_path: Path) -> None:
    """UNSCANNED READS AS UNKNOWN, NEVER AS CLEAN.

    A dependency step this gate cannot resolve may be staging a binary, so the
    provided count is a FLOOR. Saying so is what lets a reader chasing a
    `needs X` finding see that X might be staged by a step nothing here could
    read - and stops the floor being quoted as a total.
    """
    pipeline(
        tmp_path,
        battery_path=True,
        stage_commands=["./some-opaque-installer --into /usr/local/bin"],
    )
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_NOTHING)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert contract(out.stdout, "CI_DEPS_UNRESOLVED_STAGE") == "stage", out.stdout


def test_a_tree_with_no_registered_control_is_not_a_vacuous_green(tmp_path: Path) -> None:
    """A population of zero makes every assertion vacuously true.

    An `ok` over an empty `controls/` and an `ok` over the real register are
    otherwise the same line. See docs/agents/detector-contracts.md.
    """
    pipeline(tmp_path)
    (tmp_path / "controls").mkdir()
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "nothing compared" in out.stdout, out.stdout


def test_the_real_repository_resolves_every_registered_control() -> None:
    """The integration direction: this gate must be green on the tree it ships in.

    It also pins the provenance lines a reader needs in order to judge the
    verdict - an `ok` over 23 controls and an `ok` over zero must not read alike.
    """
    out = run(ROOT)
    assert out.returncode == 0, out.stdout
    registered = contract(out.stdout, "CONTROL_CI_DEPS_REGISTERED")
    provided = contract(out.stdout, "CONTROL_CI_DEPS_PROVIDED")
    assert registered and int(registered) > 0, out.stdout
    assert provided and int(provided) > 0, out.stdout
    assert contract(out.stdout, "CI_DEPS_STEP"), out.stdout


# --------------------------------------------------------------------------- #
# Counter-model review findings (codex/gpt-6-astra, this branch). Each is a
# concrete input the reviewer named; each failed on the first cut of this gate.
# --------------------------------------------------------------------------- #


def test_a_mention_of_the_destination_is_not_a_staging(tmp_path: Path) -> None:
    """`echo .ci-bin/git` stages nothing, and must not credit `git`.

    The first cut matched `.ci-bin/<name>` ANYWHERE in a dependency step's
    commands, so a command that merely PRINTS the path put git into the derived
    provided set and a git-requiring control passed. That is this gate's own
    defect class pointed at its own input: a derived set silently including
    something nothing produced.
    """
    pipeline(tmp_path, battery_path=True, stage_commands=["echo .ci-bin/git"])
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_GIT)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `git`" in out.stdout, out.stdout
    assert contract(out.stdout, "CI_DEPS_STAGED") == "0 (none)", out.stdout


def test_a_real_copy_into_ci_bin_does_stage(tmp_path: Path) -> None:
    """The direction the rule above must NOT break.

    A staging tightened until it recognises nothing is not a fix; it turns
    every genuinely-staged binary into a false red in `make verify`.
    """
    pipeline(
        tmp_path,
        battery_path=True,
        stage_commands=['cp "$(command -v git)" .ci-bin/git'],
    )
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_GIT)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout
    assert contract(out.stdout, "CI_DEPS_STAGED") == "1 (git)", out.stdout


def test_a_ci_stage_script_that_stages_nothing_does_not_count(tmp_path: Path) -> None:
    """The name is a convention; the destination is the evidence.

    A file called `ci-stage-git.py` that never writes to `.ci-bin` would
    otherwise credit git - a naming convention promoted to a fact.
    """
    pipeline(
        tmp_path,
        battery_path=True,
        stage_commands=["python3 scripts/ci-stage-git.py"],
    )
    gate_script(tmp_path, "scripts/ci-stage-git.py", "#!/usr/bin/env python3\n")
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_GIT)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `git`" in out.stdout, out.stdout


def test_a_neighbouring_commands_PATH_does_not_reach_the_battery(tmp_path: Path) -> None:
    """A finding must tell our thing from a neighbour's - including this one.

    `PATH=...:$PATH true` is a PER-COMMAND prefix: it is gone by the time the
    next command runs. The first cut asked whether ANY command in the step
    mentioned `.ci-bin` on PATH, so changing an unrelated neighbouring command
    changed this gate's verdict without changing the battery's environment.
    """
    (tmp_path / ".woodpecker.yml").write_text(
        "steps:\n"
        "  negative-controls:\n"
        f"    image: {CI_IMAGE}\n"
        "    depends_on: [stage]\n"
        "    commands:\n"
        '      - PATH="$PWD/.ci-bin:$PATH" true\n'
        "      - python3 scripts/check-negative-controls.py --strict\n"
        "\n"
        "  stage:\n"
        f"    image: {CI_IMAGE}\n"
        "    commands:\n"
        '      - cp "$(command -v git)" .ci-bin/git\n',
        encoding="utf-8",
    )
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_GIT)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `git`" in out.stdout, out.stdout


def test_an_export_on_its_own_line_does_reach_the_battery(tmp_path: Path) -> None:
    """The shape that genuinely persists, so the rule above is not just strict.

    Woodpecker runs a step's commands as one script, so a standalone `export
    PATH=...` really is in effect for the battery invocation below it.
    """
    (tmp_path / ".woodpecker.yml").write_text(
        "steps:\n"
        "  negative-controls:\n"
        f"    image: {CI_IMAGE}\n"
        "    depends_on: [stage]\n"
        "    commands:\n"
        '      - export PATH="$PWD/.ci-bin:$PATH"\n'
        "      - python3 scripts/check-negative-controls.py --strict\n"
        "\n"
        "  stage:\n"
        f"    image: {CI_IMAGE}\n"
        "    commands:\n"
        '      - cp "$(command -v git)" .ci-bin/git\n',
        encoding="utf-8",
    )
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_GIT)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout


def test_an_unregistered_manifest_is_not_examined(tmp_path: Path) -> None:
    """The register is the BATTERY's, not a glob over `controls/`.

    An orphan manifest nothing registers never runs, so a dependency it
    declares cannot take the battery down - and reding `make verify` over it
    would fail the repository for a control that does not exist.
    """
    pipeline(tmp_path)
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_NOTHING)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    # Registered by nothing: no marker names it.
    gate_script(tmp_path, "scripts/orphan-gate.sh", "#!/bin/sh\nREV=$(git rev-parse HEAD)\n")
    control(tmp_path, "orphan", "scripts/orphan-gate.sh", ["git", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout
    assert "orphan" not in out.stdout, out.stdout


def test_a_nested_control_directory_is_examined(tmp_path: Path) -> None:
    """The other direction, and it is the dangerous one.

    A marker naming `controls/group/toy` registers a control the battery WILL
    execute, and a one-level glob over `controls/*/control.json` never sees it -
    so its missing dependency passes in the one place it matters.
    """
    pipeline(tmp_path)
    gate_script(
        tmp_path,
        "scripts/toy-gate.sh",
        "#!/bin/sh\n# NEGATIVE-CONTROL: controls/group/toy\nREV=$(git rev-parse HEAD)\n",
    )
    control(tmp_path, "group/toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `git`" in out.stdout, out.stdout


def test_an_unused_shebang_interpreter_is_not_required(tmp_path: Path) -> None:
    """With an explicit interpreter in the invocation, the shebang is a comment.

    A portable gate marked `#!/usr/bin/env zsh` and invoked with `sh` runs
    perfectly in an image with no zsh. Requiring it turned a runnable control
    into a false red - and this gate sits in `make verify`, where a false red
    blocks every merge in the repository.
    """
    pipeline(tmp_path)
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_ZSH_SHEBANG)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout
    assert "zsh" not in out.stdout, out.stdout


def test_a_directly_run_gate_still_depends_on_its_shebang(tmp_path: Path) -> None:
    """The half the fix above must not remove.

    With no explicit interpreter the kernel reads the shebang, so an absent one
    is a genuine dependency - and the commonest real shape, since most gates are
    invoked as `["python3", "{gate}"]` or run directly.
    """
    pipeline(tmp_path)
    gate_script(tmp_path, "scripts/toy-gate.sh", NEEDS_ZSH_SHEBANG)
    control(tmp_path, "toy", "scripts/toy-gate.sh", ["{gate}", "--root", "{case}"])
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `zsh`" in out.stdout, out.stdout


# --------------------------------------------------------------------------- #
# Counter-model review, SECOND pass (codex/gpt-6-astra). Every case below is a
# false GREEN the first round of fixes still allowed - the direction that lets a
# control through which would take the whole register down.
# --------------------------------------------------------------------------- #


def _battery_yaml(root: Path, battery_commands: list[str], stage_commands: list[str],
                  extra_steps: str = "") -> None:
    body = "\n".join(f"      - {command}" for command in battery_commands)
    staged = "\n".join(f"      - {command}" for command in stage_commands)
    (root / ".woodpecker.yml").write_text(
        "steps:\n"
        "  negative-controls:\n"
        f"    image: {CI_IMAGE}\n"
        "    depends_on: [stage]\n"
        "    commands:\n"
        f"{body}\n"
        "\n"
        "  stage:\n"
        f"    image: {CI_IMAGE}\n"
        "    commands:\n"
        f"{staged}\n"
        f"{extra_steps}",
        encoding="utf-8",
    )


BATTERY_WITH_PATH = ['PATH="$PWD/.ci-bin:$PATH" python3 scripts/check-negative-controls.py --strict']


def _needs_git_control(root: Path) -> None:
    gate_script(root, "scripts/toy-gate.sh", NEEDS_GIT)
    control(root, "toy", "scripts/toy-gate.sh", ["sh", "{gate}"])


def test_a_copy_word_inside_an_echo_does_not_stage(tmp_path: Path) -> None:
    """`echo cp /usr/bin/git .ci-bin/git` copies nothing.

    The first fix asked whether the command CONTAINED a copy-like word, which
    an echo of a copy command satisfies. The destination must be the last
    operand of a copy at command position, not a word in a string.
    """
    _battery_yaml(tmp_path, BATTERY_WITH_PATH, ["echo cp /usr/bin/git .ci-bin/git"])
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert contract(out.stdout, "CI_DEPS_STAGED") == "0 (none)", out.stdout


def test_a_real_copy_elsewhere_does_not_license_a_bare_mention(tmp_path: Path) -> None:
    """`cp /etc/hosts /tmp/x && echo .ci-bin/git` - a verb, and a mention, in
    two different commands. Splitting on the shell separators is what stops one
    command's verb vouching for another's text."""
    _battery_yaml(tmp_path, BATTERY_WITH_PATH, ["cp /etc/hosts /tmp/hosts && echo .ci-bin/git"])
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert contract(out.stdout, "CI_DEPS_STAGED") == "0 (none)", out.stdout


def test_the_real_mkdir_and_cp_idiom_still_stages(tmp_path: Path) -> None:
    """The shape the pipeline actually uses, joined by `&&` like the real one.

    A rule tightened until it recognises nothing is not a fix - it converts
    every genuinely staged binary into a false red in `make verify`.
    """
    _battery_yaml(
        tmp_path,
        BATTERY_WITH_PATH,
        ['mkdir -p .ci-bin && cp "$(command -v git)" .ci-bin/git'],
    )
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout
    assert contract(out.stdout, "CI_DEPS_STAGED") == "1 (git)", out.stdout


def test_a_stager_that_only_prints_the_directory_does_not_count(tmp_path: Path) -> None:
    """`print(".ci-bin")` stages nothing.

    Naming the directory is not producing the binary. A stager must name the
    destination, name the binary, and carry a write - three text conditions,
    which is the weakest rule that still separates the real `ci-stage-jq.py`
    from a file that merely talks about staging.
    """
    _battery_yaml(tmp_path, BATTERY_WITH_PATH, ["python3 scripts/ci-stage-git.py"])
    gate_script(tmp_path, "scripts/ci-stage-git.py", '#!/usr/bin/env python3\nprint(".ci-bin")\n')
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert contract(out.stdout, "CI_DEPS_STAGED") == "0 (none)", out.stdout


def test_a_command_local_PATH_override_un_stages_an_earlier_export(tmp_path: Path) -> None:
    """A `PATH=...` prefix REPLACES the environment for that command.

    So `export PATH=...:.ci-bin` followed by a battery invocation carrying its
    own `PATH=/usr/bin` prefix leaves the battery unable to see anything staged.
    The first fix returned as soon as it saw the export and never looked.
    """
    _battery_yaml(
        tmp_path,
        [
            'export PATH="$PWD/.ci-bin:$PATH"',
            "PATH=/usr/local/bin:/usr/bin:/bin python3 scripts/check-negative-controls.py --strict",
        ],
        ['cp "$(command -v git)" .ci-bin/git'],
    )
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `git`" in out.stdout, out.stdout


def test_a_similarly_named_directory_is_not_ci_bin(tmp_path: Path) -> None:
    """`.ci-bin-backup` is a different directory, and nothing stages into it."""
    _battery_yaml(
        tmp_path,
        ['PATH="$PWD/.ci-bin-backup:$PATH" python3 scripts/check-negative-controls.py --strict'],
        ['cp "$(command -v git)" .ci-bin/git'],
    )
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "CI_DEP: toy needs `git`" in out.stdout, out.stdout


def test_a_neighbouring_echo_of_the_battery_path_does_not_select_that_step(tmp_path: Path) -> None:
    """A mention as an argument is not an invocation.

    An unrelated step echoing the script's path used to be selected as THE
    battery step, and its image was then compared against the pin - so an
    otherwise healthy pipeline failed for a neighbour's change, which is
    exactly the question this gate's docstring asks of other gates.
    """
    _battery_yaml(
        tmp_path,
        BATTERY_WITH_PATH,
        ['cp "$(command -v git)" .ci-bin/git'],
        extra_steps=(
            "\n  chatter:\n"
            "    image: alpine:3.20\n"
            "    commands:\n"
            "      - echo scripts/check-negative-controls.py\n"
        ),
    )
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 0, out.stdout
    step = contract(out.stdout, "CI_DEPS_STEP")
    assert step is not None and step.startswith("negative-controls"), out.stdout


def test_two_steps_running_the_battery_are_ambiguous_not_first_wins(tmp_path: Path) -> None:
    """Two environments, and file order is not a way to choose between them."""
    _battery_yaml(
        tmp_path,
        BATTERY_WITH_PATH,
        ['cp "$(command -v git)" .ci-bin/git'],
        extra_steps=(
            "\n  second-battery:\n"
            "    image: alpine:3.20\n"
            "    commands:\n"
            "      - python3 scripts/check-negative-controls.py --strict\n"
        ),
    )
    _needs_git_control(tmp_path)
    out = run(tmp_path)
    assert out.returncode == 1, out.stdout
    assert "ambiguous" in out.stdout, out.stdout
