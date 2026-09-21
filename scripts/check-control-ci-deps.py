#!/usr/bin/env python3
"""Flag a registered negative control that needs a binary CI does not have (issue #1036).

ONE CONTROL'S UNMET DEPENDENCY TAKES THE WHOLE BATTERY DOWN. That is the shape
this gate exists for, and it is not hypothetical. A control registered committed
BARE GIT REPOSITORIES as its cases; `git` is not in the image that runs the
`negative-controls` step, so CI produced::

    FileNotFoundError: No such file or directory: 'git'
    case bad-reversed: expected=BAD observed=UNSIGNALLED (exit 1)

`check-negative-controls.py` is the framework every other control's verdict is
read THROUGH, and it REFUSES to skip a control it cannot run - correctly, since
a skipped control and a passing one must never print the same thing. The
consequence is that a single unrunnable control makes the gate that reports
whether ANY instrument is controlled the thing that cannot report.

WHY IT IS STRUCTURALLY INVISIBLE WITHOUT THIS GATE. It passed `make verify`,
`--strict`, sixteen killed mutations and two review passes locally, because
every local instrument had `git` on PATH. The dev box cannot reproduce the
failure at all unless someone deliberately constructs it (`env -i PATH=<no-git>`),
so the condition is discoverable only on CI, only after the commit, and only as
a red on a step that names a different control than the one at fault. This
repository records the same class as forgotten three times already: #451, #489,
#577.

So this gate runs at REGISTRATION time, in `make verify`, on the dev box - the
one place the failure otherwise cannot be seen.

WHAT IS DERIVED, AND WHY THAT MATTERS MORE THAN THE CHECK
---------------------------------------------------------
The PROVIDED set - what the battery step can actually run - is derived from
`.woodpecker.yml`, never typed here:

  the step        the step whose commands invoke `check-negative-controls.py`.
                  Found by what it RUNS, not by its name, so renaming the step
                  does not silently point this gate at the wrong image.
  the image       that step's `image:`, digest stripped. It is then compared
                  against `CI_IMAGE` in `check-test-binary-guards.py`, which is
                  where this repository already records what the image
                  CONTAINS. A mismatch is a RED, not a fallback: the contents
                  list would otherwise go on describing an image the pipeline
                  stopped using, which is the hand-maintained-number failure
                  one level up from the one this gate catches.
  staged binaries `cp "$(command -v X)" .ci-bin/X` in any step the battery
                  `depends_on`, counted only when the battery's own command
                  puts `.ci-bin` on PATH. Three binaries reach the step that
                  way today (gitleaks, shellcheck, jq) and none of them are in
                  the image.

`CI_IMAGE_BINARIES` is IMPORTED from `check-test-binary-guards.py` rather than
copied, for the reason #1060 recorded about census parsers: two lists of what
one image contains drift apart silently, and both keep printing verdicts while
they do.

WHAT IS EXAMINED, AND WHAT IS DELIBERATELY NOT
-----------------------------------------------
Three surfaces per registered control, and the success line names all three so
nobody can read this gate as "every dependency is satisfied":

  invocation      `control.json`'s `invocation[0]`, after unwrapping `env` and
                  its `VAR=VALUE` assignments. `{gate}` and `{case}` are paths,
                  not commands, and are skipped.
  interpreter     the gate's shebang - `#!/usr/bin/env python3` needs
                  `python3` - but ONLY when the invocation runs the gate
                  directly. With an explicit interpreter (`["sh", "{gate}"]`)
                  the shebang is a comment, and requiring it turns a runnable
                  control into a false red; this gate is in `make verify`, so
                  a false red blocks every merge in the repository.
  shell gate body for a `sh`/`bash` gate only, the binaries it HARD-REQUIRES,
                  via `binaries_in_script` in `check-test-binary-guards.py` -
                  the audited extractor that already powers the binary-guards
                  gate, which excludes anything the script declares it degrades
                  without. This is the surface the `git` failure above came
                  through.

NOT EXAMINED: what a PYTHON gate shells out to, and what a case FIXTURE needs.
Both would need the AST and shell analysis `check-test-binary-guards.py` spends
1,500 lines on, aimed at a different population, and a looser scan is worse than
none - measured in that file, scanning for any mention of a binary produced 266
findings of which ~250 were scripts that run fine without the tool. A guess that
cries wolf costs more than the false negative it removes. The bound is stated in
the success line rather than left for a reader to discover.

`binaries_in_script` reports only names in `GUARDED_BINARIES`, so the REQUIRED
side is bounded by a hand-maintained list even though the PROVIDED side is
derived. That asymmetry is deliberate and is the same one its owning file
defends: in shell text a binary and a shell function sit in the same position,
and telling them apart needs a shell parser. The list is shared with the gate
that already enforces it on every test, so it is maintained by something other
than this file remembering.

Stdlib-only, git-free and offline, so `make verify` and the slim CI image give
the same verdict.

Usage:
    check-control-ci-deps.py [--root DIR]

Output: one `CI_DEP:` or `CI_PIPELINE:` line per finding, provenance counts,
then a verdict line. Exit 0 when every registered control's examined surface
resolves against the derived set, 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Optional

#: NEGATIVE-CONTROL: controls/control-ci-deps
#:
#: This gate lets work THROUGH - `make verify` reads its green as "no registered
#: control needs a binary the battery's CI step lacks", and nothing downstream
#: re-derives that. ADR 0008's bound therefore requires a committed case
#: (class G). It is also a gate whose whole value is a claim about an
#: ENVIRONMENT THAT IS NOT THE ONE IT RUNS IN, which is the hardest kind to
#: notice going blind: every local run has the binaries, so a version that
#: checked nothing would print the same green on this dev box forever.
#:
#: The registration lives in THIS file because that is what
#: `check-negative-controls.py` enumerates: a control directory alone is
#: invisible to the battery, which then reports PASS over a register the new
#: control is not in.

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where this repository records what the CI image CONTAINS, and the image that
#: list describes. Imported, never copied - see the module docstring.
BINARY_GATE_REL = "scripts/check-test-binary-guards.py"

WOODPECKER_REL = ".woodpecker.yml"
CONTROLS_REL = "controls"

#: The battery itself, whose `discover()` decides WHICH controls actually run.
#: IMPORTED rather than re-derived (counter-model review, codex/gpt-6-astra).
#: The first cut globbed `controls/*/control.json`, which is a DIFFERENT
#: population from the one the battery executes, and it was wrong in both
#: directions: an orphan manifest nothing registers could red `make verify`
#: over a control that never runs, and a marker naming a nested directory such
#: as `controls/group/toy` runs in the battery while this gate never saw it -
#: so a missing dependency in the one place it matters passed. Two readers of
#: one population is the exact drift this repository refuses elsewhere, and
#: this file argued for sharing a rule two paragraphs above while not doing it.
BATTERY_GATE_REL = "scripts/check-negative-controls.py"

#: The battery, identified by what a step RUNS rather than by the step's name.
BATTERY_SCRIPT = "check-negative-controls.py"

#: `cp "$(command -v gitleaks)" .ci-bin/gitleaks` - the staging idiom. Keyed on
#: the DESTINATION, which is what actually lands on PATH; a `cp` whose source
#: and destination names disagree stages the destination name.
#:
#: A MENTION IS NOT A STAGING, AND NEITHER IS A NEARBY VERB (counter-model
#: review, codex/gpt-6-astra, both passes). The first cut matched
#: `.ci-bin/<name>` ANYWHERE in a command, so `echo .ci-bin/git` credited git;
#: the second matched any command CONTAINING a copy-like word, so
#: `echo cp /usr/bin/git .ci-bin/git` and `cp /etc/hosts /tmp/x && echo
#: .ci-bin/git` both still did. Every one of those is a FALSE GREEN - the
#: derived set claiming a binary nothing produced - which is the worse
#: direction for this gate, since it lets a control through that will take the
#: whole register down.
#:
#: So the destination must be the LAST OPERAND of a copy-like command at
#: command position. `mkdir -p .ci-bin && cp "$(command -v gitleaks)"
#: .ci-bin/gitleaks` is the real idiom and matches; the three counterexamples
#: above do not. Anything else is not recognised, and an unrecognised
#: dependency step is REPORTED as unresolved rather than credited - the
#: direction this gate errs in everywhere else.
STAGE_CP_RE = re.compile(
    r"""(?:^|[|;&]\s*)\s*         # command position: start, or after | ; &&
        (?:cp|install|mv|ln)      # the copy-like verbs
        (?:\s+-\S+)*              # flags
        \s+\S.*?                  # at least one source operand
        \s\.?/?\.ci-bin/([A-Za-z0-9_.+-]+)\s*$   # ... and the destination LAST
    """,
    re.VERBOSE,
)

#: The second staging shape, and it is not a nicety: `jq-stage` runs
#: `python3 scripts/ci-stage-jq.py`, whose destination is built as
#: `DEST_DIR / "jq"` - no `.ci-bin/jq` string exists anywhere for STAGE_RE to
#: find, in the yaml OR in the script. Read the pipeline alone and jq is
#: invisible, so the provided set silently loses a binary that IS on PATH, and
#: the first control to need it gets a FALSE RED in `make verify`.
#:
#: Found by reading this gate's own output rather than by a failing test: it
#: printed `CI_DEPS_STAGED: 2 (gitleaks, shellcheck)` beside a pipeline whose
#: battery step depends on THREE staging steps. The counts are in the output for
#: exactly this reason.
#:
#: THE NAME ALONE IS NOT EVIDENCE, AND NEITHER IS A MENTION OF THE DIRECTORY
#: (same review, both passes). A file called `ci-stage-git.py` containing only
#: `print(".ci-bin")` was credited with providing git. So a stager must name
#: the destination directory, name the binary, AND carry a write. That is three
#: text conditions rather than a proof, and it is deliberately the weakest rule
#: that still separates `scripts/ci-stage-jq.py` - `DEST_DIR = Path(".ci-bin")`,
#: `DEST = DEST_DIR / "jq"`, `DEST.write_bytes(payload)` - from a file that
#: merely talks about staging. A stager this cannot recognise leaves its step
#: UNRESOLVED, which reports rather than credits.
STAGER_RE = re.compile(r"scripts/ci-stage-([A-Za-z0-9_.+-]+?)\.(?:py|sh)\b")
STAGER_DEST = ".ci-bin"
STAGER_WRITE_RE = re.compile(
    r"\b(?:write_bytes|write_text|shutil\.copy\w*|os\.replace|chmod|"
    r"cp\s|install\s|mv\s|ln\s|curl\s|wget\s)"
)

#: `PATH="$PWD/.ci-bin:$PATH" <cmd>` - a per-command prefix, effective for THAT
#: command only. `export PATH=...` on its own line persists for the rest of the
#: step's script, so both are accepted and nothing else is.
#:
#: SCOPE IS THE WHOLE POINT (counter-model review, codex/gpt-6-astra). The first
#: cut asked whether ANY command in the step mentioned `.ci-bin` on PATH, so a
#: step whose FIRST command was `PATH=...:$PATH true` credited the staged
#: binaries to a battery invocation that never saw them. A neighbouring command
#: changed the verdict without changing the battery's environment - a finding
#: that cannot tell our thing from a neighbour's, in a gate whose own docstring
#: asks that question of others.
#: `.ci-bin` AS A WHOLE PATH COMPONENT, never a prefix: `.ci-bin-backup`
#: matched the first cut's `\.ci-bin` and credited a directory that is not the
#: one staged into (counter-model review, second pass).
CI_BIN_COMPONENT = r"\.ci-bin(?=[:/\"']|$)"
CI_BIN_PREFIX_RE = re.compile(rf"^\s*PATH=\S*{CI_BIN_COMPONENT}")
CI_BIN_EXPORT_RE = re.compile(rf"^\s*export\s+PATH=\S*{CI_BIN_COMPONENT}\S*\s*$")
#: Any `PATH=` prefix on the battery command, whether or not it names `.ci-bin`.
#: A command-local assignment OVERRIDES an earlier `export`, so one that omits
#: `.ci-bin` un-stages everything for that command - which the first cut missed
#: by returning as soon as it saw the export.
PATH_PREFIX_RE = re.compile(r"^\s*PATH=")

#: A shebang's effective interpreter: the last path component, plus the first
#: argument when it is `/usr/bin/env`.
SHEBANG_RE = re.compile(r"^#!\s*(\S+)(?:\s+(\S+))?")


#: Why the sibling could not be loaded, for the finding line. A bare "could not
#: be loaded" sent the first run of this gate looking in the wrong place: the
#: real cause was the missing `sys.modules` registration below, which is a
#: two-line fix presenting as an unreadable file.
_LOAD_ERROR: dict[str, str] = {}


def _load(path: Path):
    """Import a sibling gate by path, or None. None means UNREAD, never EMPTY."""
    if not path.is_file():
        _LOAD_ERROR[str(path)] = "no such file"
        return None
    name = f"cpp_{path.stem.replace('-', '_')}"
    try:
        spec = spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            _LOAD_ERROR[str(path)] = "no import spec"
            return None
        module = module_from_spec(spec)
        # REGISTERED BEFORE EXECUTION, and it is load-bearing rather than
        # ceremonial: `@dataclass` resolves its own module out of `sys.modules`
        # while the class body is executing, so a module absent from it raises
        # `AttributeError: 'NoneType' object has no attribute '__dict__'` at
        # import. Both siblings this gate loads define dataclasses.
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - any failure here is UNREAD
        sys.modules.pop(name, None)
        _LOAD_ERROR[str(path)] = f"{type(exc).__name__}: {exc}"
        return None
    return module


def _image_name(image: str) -> str:
    """An image reference without its `@sha256:` digest."""
    return image.split("@", 1)[0].strip()


def _steps(text: str) -> dict[str, dict[str, object]]:
    """The `steps:` mapping of a Woodpecker pipeline, parsed for what is needed.

    A deliberately small reader rather than a YAML dependency: this gate must be
    stdlib-only so `make verify` and the slim CI image give the same verdict. It
    reads exactly three things per step - `image`, `depends_on` and `commands` -
    and reports a step it cannot parse rather than skipping it, because a step
    silently dropped here is a provided-set that is quietly too small.
    """
    steps: dict[str, dict[str, object]] = {}
    lines = text.splitlines()
    in_steps = False
    name: str | None = None
    section: str | None = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if indent == 0:
            in_steps = stripped.rstrip(":") == "steps" and stripped.endswith(":")
            name = None
            section = None
            continue
        if not in_steps:
            continue

        if indent == 2 and stripped.endswith(":"):
            name = stripped[:-1].strip()
            steps[name] = {"image": "", "depends_on": [], "commands": []}
            section = None
            continue
        if name is None:
            continue

        if indent == 4:
            section = None
            if stripped.startswith("image:"):
                steps[name]["image"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("depends_on:"):
                rest = stripped.split(":", 1)[1].strip()
                if rest.startswith("[") and rest.endswith("]"):
                    steps[name]["depends_on"] = [
                        item.strip() for item in rest[1:-1].split(",") if item.strip()
                    ]
                else:
                    section = "depends_on"
            elif stripped.startswith("commands:"):
                section = "commands"
            continue

        if indent >= 6 and stripped.startswith("- ") and section in {"depends_on", "commands"}:
            steps[name][section].append(stripped[2:].strip())  # type: ignore[union-attr]
    return steps


def _ci_bin_reaches_the_battery(commands: list[str]) -> bool:
    """Does `.ci-bin` end up on PATH for the command that RUNS the battery?

    Two shapes are effective and nothing else is: the per-command `PATH=... cmd`
    prefix ON the battery invocation, and a standalone `export PATH=...` earlier
    in the same step's script, which persists. A prefix on a NEIGHBOURING
    command does not, and reading it as one was the defect this function exists
    to fix.
    """
    exported = False
    for command in commands:
        if CI_BIN_EXPORT_RE.match(command):
            exported = True
            continue
        if not _is_battery_invocation(command):
            continue
        # A command-local `PATH=...` prefix REPLACES the environment for that
        # command, so it decides on its own: `.ci-bin` in it means yes, and a
        # prefix without it means no even after an export that had it.
        if PATH_PREFIX_RE.match(command):
            return bool(CI_BIN_PREFIX_RE.match(command))
        return exported
    return False


def _stager_product(root: Path, name: str) -> set[str]:
    """What `scripts/ci-stage-<name>` actually stages, or nothing.

    The name is a convention, not evidence: a `ci-stage-git.py` that stages
    nothing would credit `git` to the provided set. So the script must exist AND
    mention the destination directory - which is the weakest check that can
    still tell a real stager from a file named like one, and it is deliberately
    weak in the direction of reporting LESS.
    """
    for ext in (".py", ".sh"):
        candidate = root / "scripts" / f"ci-stage-{name}{ext}"
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            STAGER_DEST in text
            and re.search(rf"[\"'/]{re.escape(name)}[\"'\s]", text)
            and STAGER_WRITE_RE.search(text)
        ):
            return {name}
    return set()


#: The battery RUN, not the battery MENTIONED (counter-model review, second
#: pass). `_battery_step` used to select the first step whose commands merely
#: CONTAINED the script's filename, so an unrelated `echo
#: scripts/check-negative-controls.py` in an earlier Alpine step selected that
#: step and the whole pipeline failed on an image mismatch - a non-zero
#: reflecting a neighbour's change rather than the battery's environment, which
#: is the second question this file's own docstring asks of other gates.
#:
#: An invocation is the command itself, after an optional `PATH=...` prefix and
#: an optional interpreter: `python3 scripts/check-negative-controls.py`,
#: `./scripts/...`, or the path alone. A mention as an ARGUMENT to something
#: else is not one.
BATTERY_INVOCATION_RE = re.compile(
    rf"""^\s*(?:PATH=\S+\s+)*              # optional env prefixes
         (?:(?:python3?|sh|bash)\s+)?      # optional interpreter
         \.?/?(?:\S*/)?{re.escape(BATTERY_SCRIPT)}(?:\s|$)
    """,
    re.VERBOSE,
)


def _is_battery_invocation(command: str) -> bool:
    return bool(BATTERY_INVOCATION_RE.match(command))


def _battery_step(
    steps: dict[str, dict[str, object]]
) -> tuple[tuple[str, dict[str, object]] | None, list[str]]:
    """`(the step that RUNS the battery, every step that does)`.

    The second element is returned rather than discarded so an AMBIGUOUS
    pipeline - two steps genuinely running the battery, possibly under
    different images - is reported instead of silently resolved to whichever
    came first in the file.
    """
    matches = [
        (name, step)
        for name, step in steps.items()
        if any(_is_battery_invocation(str(command)) for command in step["commands"])  # type: ignore[union-attr]
    ]
    return (matches[0] if matches else None), [name for name, _ in matches]


def provided_binaries(root: Path) -> tuple[set[str] | None, list[str], list[str]]:
    """`(provided, notes, findings)` - what the battery's CI step can run.

    `provided` is None when the pipeline could not be read or its image is not
    the one `CI_IMAGE_BINARIES` describes. None means UNKNOWN, and the caller
    reports rather than falling back to a partial set: a provided-set that is
    silently too small turns every control into a false finding, and one that is
    silently too large is a false green.
    """
    notes: list[str] = []
    findings: list[str] = []

    binary_gate = _load(REPO_ROOT / BINARY_GATE_REL)
    if binary_gate is None:
        findings.append(
            f"CI_PIPELINE: {BINARY_GATE_REL} could not be loaded "
            f"({_LOAD_ERROR.get(str(REPO_ROOT / BINARY_GATE_REL), 'unknown reason')}), "
            "so what the CI image contains is unknown"
        )
        return None, notes, findings

    pipeline = root / WOODPECKER_REL
    if not pipeline.is_file():
        findings.append(f"CI_PIPELINE: {WOODPECKER_REL} does not exist under {root}")
        return None, notes, findings

    steps = _steps(pipeline.read_text(encoding="utf-8"))
    if not steps:
        findings.append(f"CI_PIPELINE: {WOODPECKER_REL} parsed to 0 steps")
        return None, notes, findings

    battery, every = _battery_step(steps)
    if battery is None:
        findings.append(
            f"CI_PIPELINE: no step in {WOODPECKER_REL} runs {BATTERY_SCRIPT}, so the "
            "environment the controls must satisfy cannot be derived"
        )
        return None, notes, findings
    if len(every) > 1:
        # Two environments, and nothing here can say which one a control has to
        # satisfy - possibly both, under different images. Resolving it to the
        # first would be an answer chosen by file order.
        findings.append(
            f"CI_PIPELINE: {len(every)} steps in {WOODPECKER_REL} run {BATTERY_SCRIPT} "
            f"({', '.join(every)}), so the environment the controls must satisfy is ambiguous"
        )
        return None, notes, findings
    step_name, step = battery

    image = _image_name(str(step["image"]))
    if not image:
        findings.append(f"CI_PIPELINE: step `{step_name}` declares no image")
        return None, notes, findings
    if image != binary_gate.CI_IMAGE:
        # A RED, never a fallback. `CI_IMAGE_BINARIES` describes ONE image; if
        # the pipeline moved to another, every answer below would be about a
        # container that no longer runs the battery.
        findings.append(
            f"CI_PIPELINE: step `{step_name}` runs `{image}` but {BINARY_GATE_REL} records "
            f"the contents of `{binary_gate.CI_IMAGE}` - the provided-binary list describes "
            "a different image, so nothing here can be trusted"
        )
        return None, notes, findings

    provided = set(binary_gate.CI_IMAGE_BINARIES)
    notes.append(f"CI_DEPS_STEP: {step_name} ({image})")

    commands = [str(command) for command in step["commands"]]  # type: ignore[union-attr]
    if _ci_bin_reaches_the_battery(commands):
        staged: set[str] = set()
        unresolved: list[str] = []
        for dependency in [str(dep) for dep in step["depends_on"]]:  # type: ignore[union-attr]
            found: set[str] = set()
            for command in [str(c) for c in steps.get(dependency, {}).get("commands", [])]:
                for fragment in re.split(r"(?:\|\||&&|[;&|])", command):
                    found.update(STAGE_CP_RE.findall(fragment.strip()))
                for name in STAGER_RE.findall(command):
                    found |= _stager_product(root, name)
            if found:
                staged |= found
            elif steps.get(dependency, {}).get("commands"):
                unresolved.append(dependency)
        provided |= staged
        notes.append(f"CI_DEPS_STAGED: {len(staged)} ({', '.join(sorted(staged)) or 'none'})")
        if unresolved:
            # UNSCANNED READS AS UNKNOWN, NEVER AS CLEAN. A dependency step this
            # gate cannot resolve may be staging a binary, so the provided set
            # below is a FLOOR. Printed on every run rather than folded into a
            # finding: it is a limit on what was seen, not a defect in a
            # control, and a reader chasing a `needs X` finding has to be able
            # to see that X might be staged by a step nothing here could read.
            notes.append(f"CI_DEPS_UNRESOLVED_STAGE: {', '.join(sorted(unresolved))}")
    else:
        notes.append("CI_DEPS_STAGED: 0 (the battery step does not put .ci-bin on PATH)")

    return provided, notes, findings


def interpreter_of(gate: Path) -> str | None:
    """The binary a gate's shebang asks for, or None when it has none."""
    try:
        with gate.open("r", encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
    except OSError:
        return None
    match = SHEBANG_RE.match(first)
    if not match:
        return None
    head = Path(match.group(1)).name
    if head == "env" and match.group(2):
        return Path(match.group(2)).name
    return head


def invocation_command(invocation: list[str]) -> str | None:
    """The binary an `invocation` actually runs.

    `env` and its `VAR=VALUE` assignments are unwrapped - `["env", "FOO=1",
    "bash", "{gate}"]` runs `bash`, and reading `env` as the dependency would
    check a binary that is present in every image while missing the one that
    might not be. `{gate}` and `{case}` are paths the harness substitutes, so a
    command position holding one means the gate is run directly and its
    INTERPRETER is the dependency - which `interpreter_of` answers.
    """
    index = 0
    while index < len(invocation):
        token = invocation[index]
        if index == 0 and Path(token).name == "env":
            index += 1
            while index < len(invocation) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", invocation[index]):
                index += 1
            continue
        if "{gate}" in token or "{case}" in token:
            return None
        return Path(token).name
    return None


def registered_controls(root: Path) -> tuple[list[Path] | None, str]:
    """`(control directories, provenance)` the BATTERY would actually execute.

    Resolved through the battery's own `discover()`, so this gate and the
    register cannot disagree about what is registered. `None` means the rule
    could not be loaded - UNKNOWN, never an empty register, which would make
    every assertion below vacuous.
    """
    battery = _load(REPO_ROOT / BATTERY_GATE_REL)
    if battery is None:
        return None, (
            f"{BATTERY_GATE_REL} could not be loaded "
            f"({_LOAD_ERROR.get(str(REPO_ROOT / BATTERY_GATE_REL), 'unknown reason')})"
        )
    try:
        registrations = battery.discover(root)
    except Exception as exc:  # noqa: BLE001 - a broken rule is UNREAD, never EMPTY
        return None, f"{BATTERY_GATE_REL}.discover raised {type(exc).__name__}: {exc}"
    directories: list[Path] = []
    for _gate, control_rel in registrations:
        directory = (root / control_rel).resolve()
        if directory not in directories:
            directories.append(directory)
    return directories, f"discovered via {BATTERY_GATE_REL}"


def requirements(root: Path, control_dir: Path, binary_gate) -> tuple[set[str], list[str]]:
    """`(binaries, notes)` this control needs - the examined surfaces."""
    needed: set[str] = set()
    notes: list[str] = []
    manifest = control_dir / "control.json"
    try:
        spec = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        notes.append(f"control.json unreadable: {exc}")
        return needed, notes

    invocation = [str(part) for part in spec.get("invocation", [])]
    command = invocation_command(invocation)
    if command:
        needed.add(command)

    declared = str(spec.get("gate", ""))
    if not declared:
        return needed, notes
    gate = root / declared
    if not gate.is_file():
        # Not this gate's finding: `check-negative-controls.py` already reports
        # an absent declared gate as UNRESOLVED, and reporting it twice in
        # different words sends a reader looking for two problems.
        return needed, notes

    # THE SHEBANG IS ONLY A DEPENDENCY WHEN THE GATE IS RUN DIRECTLY
    # (counter-model review, codex/gpt-6-astra). With an explicit interpreter in
    # the invocation - `["sh", "{gate}"]` - the shebang is a comment, so
    # requiring it turned a runnable control into a false red: a portable gate
    # marked `#!/usr/bin/env zsh` and invoked with `sh` runs perfectly in an
    # image with no zsh. This gate is in `make verify`, so a false red there
    # blocks every merge in the repository, which is the more expensive
    # direction to be wrong in.
    shebang = interpreter_of(gate)
    effective = command or shebang
    if command is None and shebang:
        needed.add(shebang)
    if effective in {"sh", "bash"}:
        needed |= set(binary_gate.binaries_in_script(gate))
    return needed, notes


#: Modules the interpreter always has. Derived from the running interpreter
#: rather than listed: a hand-kept list of stdlib names is the drift this file
#: spends its length refusing.
#:
#: BOUNDED, and the bound is stated rather than left to be discovered: this is
#: the HOST interpreter's name set, not the pinned image's. It names
#: platform-specific modules that do not import on Linux (`winreg`), and a host
#: newer than the image's python can include names the image lacks. Both make
#: this side of the comparison slightly generous, which is the safe direction
#: for a NECESSARY check - it can miss, it does not invent. The sufficient
#: answer is `make battery-in-ci-image`, which runs the battery under the
#: pinned digest and needs no model of the stdlib at all.
_PY_STDLIB = frozenset(sys.stdlib_module_names)

#: `python3 {gate}`, or `{gate}` whose shebang names python. Anything else is
#: not a python invocation and is COUNTED rather than walked.
_PY_INTERPRETER = re.compile(r"^python3?$")


def _python_entry(root: Path, control_dir: Path, spec: dict) -> Optional[Path]:
    """The python file this control's invocation runs, or None.

    Only the two shapes that are decidable without executing anything: an
    explicit `python3 {gate}`, and `{gate}` run directly with a python shebang.
    A `bash -c "...python3 ..."` wrapper is NOT resolved - the command is shell
    text, the file it runs may be produced by the case, and guessing at it is
    how a static reader starts reporting a neighbour's problem.
    """
    invocation = spec.get("invocation") or []
    gate_rel = spec.get("gate", "")
    if not gate_rel:
        return None
    gate = root / gate_rel
    if not gate.is_file():
        return None

    tokens = [str(t) for t in invocation]
    # `env VAR=V python3 {gate}` - same unwrapping the binary side does.
    idx = 0
    while idx < len(tokens) and (tokens[idx] == "env" or "=" in tokens[idx]):
        idx += 1
    if idx < len(tokens) and _PY_INTERPRETER.match(Path(tokens[idx]).name):
        # THE SCRIPT ARGUMENT MUST BE THE GATE (counter-model review). Any
        # invocation starting with python3 used to walk the declared gate
        # whatever came next, so `["python3", "{case}", "{gate}"]` - which runs
        # the CASE - was reported as the gate examined, and `-m` / `-c` forms
        # were attributed to a file they never execute. Attributing a walk to
        # the wrong file both misses real requirements and reports a
        # neighbour's imports as this control's.
        rest = [t for t in tokens[idx + 1:] if not t.startswith("-")]
        if rest and rest[0] == "{gate}":
            return gate
        return None
    if idx < len(tokens) and tokens[idx] == "{gate}":
        first = gate.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        if first and first[0].startswith("#!") and "python" in first[0]:
            return gate
    return None


def _executing_imports(tree: ast.AST) -> tuple[list[ast.stmt], int]:
    """Imports that run ON LOAD, and a count of those that do not.

    "Module level" is not "a direct child of `tree.body`", and the difference is
    a real miss: `if True: import pydantic`, a `try/except ImportError`
    fallback, and a class-body import all EXECUTE when the module is loaded,
    while a membership test against `tree.body` calls every one of them
    deferred. Counter-model review demonstrated all three against the first cut
    of this walker - each reported `ok`, which is the original failure recreated
    inside the check built to catch it.

    So EXECUTION SCOPE is tracked instead: everything is reached except the
    bodies of functions and lambdas, which run on call rather than on import -
    and `if TYPE_CHECKING:`, which is the one condition that is False by
    definition at runtime (issue #1162).

    THAT EXEMPTION IS A LITERAL, NOT A CONDITION EVALUATOR, and the narrowness
    is the point. `typing.TYPE_CHECKING` is False whenever the interpreter is
    running, so its block cannot execute; `if True:` can and must still report,
    which is the hole the review above closed and this must not reopen. Only
    the bare name `TYPE_CHECKING` or the attribute `typing.TYPE_CHECKING`
    qualifies - no other expression, however obviously constant.

    Measured: #1163 made `lib/cicd/__init__.py` lazy with exactly this idiom,
    re-declaring `.config` and friends under `if TYPE_CHECKING:` for type
    checkers alone. Walking into it made this check report that
    `verify-coverage`'s gate "imports pydantic at MODULE level, the import runs
    on load" - about code that does not run - and blocked a ratified change.
    An over-approximating check states a claim its input does not support,
    which is the contract this repository holds every detector to.
    """
    executing: list[ast.stmt] = []
    deferred = 0

    def visit(node: ast.AST, running: bool) -> None:
        nonlocal deferred
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                if running:
                    executing.append(child)
                else:
                    deferred += 1
                continue
            if _is_type_checking_block(child):
                # ONLY THE `if` BODY IS UNREACHABLE. The `else:` of a
                # TYPE_CHECKING block is the branch that RUNS at runtime - the
                # `else: import pydantic` shape is a real module-level import
                # and must still report. Deferring the whole `If` node covered
                # both and silently exempted it; measured on the first cut of
                # this fix.
                for stmt in child.body:
                    visit_stmt(stmt, False)
                for stmt in child.orelse:
                    visit_stmt(stmt, running)
                continue
            visit(
                child,
                running
                and not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
                ),
            )

    def visit_stmt(stmt: ast.stmt, running: bool) -> None:
        nonlocal deferred
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            if running:
                executing.append(stmt)
            else:
                deferred += 1
            return
        visit(
            stmt,
            running
            and not isinstance(
                stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            ),
        )

    visit(tree, True)
    return executing, deferred


def _is_type_checking_block(node: ast.AST) -> bool:
    """Is this `if TYPE_CHECKING:` - the one branch that cannot run?

    Matched as a LITERAL name or attribute, never evaluated as an expression.
    `if TYPE_CHECKING:` and `if typing.TYPE_CHECKING:` qualify; `if True:`,
    `if not DEBUG:` and everything else do not, because an import under those
    DOES execute and reporting it is the whole job.

    The `else:` branch is not exempted: it runs at runtime, so a
    `if TYPE_CHECKING: ... else: import pydantic` still reports - the import
    that executes is the one that matters.
    """
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING" and isinstance(test.value, ast.Name)
    return False


def _module_chain(dotted: str) -> list[str]:
    """`a.b.c` -> [a, a.b, a.b.c]: every package python executes on the way in."""
    parts = dotted.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def _resolve_repo_module(
    root: Path, dotted: str, near: Optional[Path] = None
) -> Optional[Path]:
    """`lib.vendor` -> `<root>/lib/vendor.py`, or its package `__init__.py`.

    ``near`` is searched FIRST when given: python puts the script's own
    directory at the head of `sys.path`, so `scripts/gate.py` importing
    `helper` gets `scripts/helper.py`, not a root-level one. Searching only the
    root reported a sibling import as an external package, and could resolve a
    name against an unrelated root-level file - a finding that changes because
    a NEIGHBOUR changed (counter-model review).

    Not modelled: a gate that edits `sys.path` at run time. That is reported as
    unresolvable rather than guessed at.
    """
    rel = Path(dotted.replace(".", "/"))
    roots = [near, root] if near is not None else [root]
    for base in roots:
        for candidate in (base / rel.with_suffix(".py"), base / rel / "__init__.py"):
            if candidate.is_file():
                return candidate
    return None


def _namespace_dir(root: Path, dotted: str, near: Optional[Path] = None) -> bool:
    """Is ``dotted`` a directory with no `__init__.py` - a PEP 420 package?

    Such a package executes no code on import, so there is nothing for the
    walker to follow and nothing that can be missing from the image. Treating
    it as an unresolved distribution reds a control for importing its own
    repository, which is how `lib/` in this tree produced a false finding.
    """
    rel = Path(dotted.replace(".", "/"))
    for base in ([near, root] if near is not None else [root]):
        candidate = base / rel
        if candidate.is_dir() and not (candidate / "__init__.py").is_file():
            return True
    return False


def _targets_for(
    root: Path, node: ast.stmt, current: Path
) -> tuple[list[str], list[Path]]:
    """(external top-level names, repo-local files) this statement executes.

    IMPORTING A SUBMODULE RUNS ITS PARENTS. `import a.b.c` executes
    `a/__init__.py`, then `a/b/__init__.py`, then `a/b/c`; and `from a.b import
    c` executes both initializers AND `a/b/c.py` when `c` is a submodule rather
    than an attribute. The first cut walked only the deepest name for `import`
    and only the package for `from ... import`, so a dependency sitting in a
    parent initializer or in the imported submodule was missed - both shown by
    counter-model review, both reporting `ok`.
    """
    external: list[str] = []
    local: list[Path] = []

    def add(dotted: str) -> None:
        top = dotted.split(".")[0]
        for step in _module_chain(dotted):
            found = _resolve_repo_module(root, step, near=current.parent)
            if found is not None:
                local.append(found)
                continue
            # A NAMESPACE PACKAGE HAS NO `__init__.py` AND IS STILL LOCAL
            # (PEP 420). `lib/` in this repository is exactly that, and
            # requiring every chain step to resolve to a FILE reported
            # `from lib.vendor import ...` as needing an external package
            # called `lib` - a false red on the one control that imports
            # first-party code at all. A directory with no initializer
            # executes nothing, so there is nothing to walk; it simply is
            # not a missing distribution.
            if _namespace_dir(root, step, near=current.parent):
                continue
            if step == top:
                # Only the TOP name can name a third-party distribution. A
                # deeper miss under a resolved parent is a module this reader
                # could not find, which the caller reports as unresolvable.
                external.append(top)

    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name.split(".")[0] not in _PY_STDLIB:
                add(alias.name)
        return external, local

    assert isinstance(node, ast.ImportFrom)
    if node.level:
        package = current.parent
        for _ in range(node.level - 1):
            package = package.parent
        base = package / (node.module.replace(".", "/") if node.module else "")
        for candidate in (base.with_suffix(".py"), base / "__init__.py"):
            if candidate.is_file():
                local.append(candidate)
                break
        for alias in node.names:
            for candidate in (base / f"{alias.name}.py", base / alias.name / "__init__.py"):
                if candidate.is_file():
                    local.append(candidate)
                    break
        return external, local

    if node.module and node.module.split(".")[0] not in _PY_STDLIB:
        add(node.module)
        for alias in node.names:
            found = _resolve_repo_module(
                root, f"{node.module}.{alias.name}", near=current.parent
            )
            if found is not None:
                local.append(found)
    return external, local


def walk_module_level_imports(
    root: Path, entry: Path
) -> tuple[set[str], set[str], int, set[str]]:
    """Follow imports that EXECUTE ON LOAD from ``entry`` through repo files.

    Returns (external, repo_local, deferred_unfollowed, unresolvable).

    The bound is execution scope, and it is the whole design rather than a
    shortcut. An import that runs on load is a requirement this reader can
    decide. An import inside a FUNCTION is conditional on the call path, and
    deciding it needs a call graph from the invoked entry point.

    Walking both would be worse than walking one. Issue #1163 deliberately
    moved seven imports in `lib/cicd/cli.py` into the commands that use them,
    and the `run` path - the one the finish gate takes - reaches none of them.
    An all-imports walk reports that `-m lib.cicd` requires pydantic, which is
    FALSE for that path, and reds a control that runs perfectly well. That is
    the shape `check-test-binary-guards.py` measured at 266 findings of which
    ~250 were scripts that run fine without the tool: a guess that cries wolf
    costs more than the false negative it removes.

    So deferred imports are COUNTED and reported as a number, never followed
    and never silently dropped.
    """
    external: set[str] = set()
    repo_local: set[str] = set()
    unresolvable: set[str] = set()
    deferred = 0
    seen: set[Path] = set()
    queue = [entry]

    while queue:
        current = queue.pop()
        resolved = current.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            tree = ast.parse(current.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            unresolvable.add(str(current))
            continue

        executing, not_executing = _executing_imports(tree)
        deferred += not_executing
        for node in executing:
            tops, locals_ = _targets_for(root, node, current)
            external.update(tops)
            for path in locals_:
                repo_local.add(path.stem)
                queue.append(path)
    return external, repo_local, deferred, unresolvable


def python_import_findings(
    root: Path, registered: list[Path]
) -> tuple[list[str], dict[str, int]]:
    """Static half of #1168: a python gate's module-level imports must resolve.

    The battery's CI step installs no python packages - it runs the image and
    the checked-out workspace, nothing else - so the set a python gate may
    import is the stdlib plus this repository. Anything else would raise
    ModuleNotFoundError and take the whole register down, which is the failure
    `check-control-ci-deps` exists to catch and could not see: it examines the
    invocation, the shebang and a SHELL gate's binaries, never what a python
    gate imports.
    """
    findings: list[str] = []
    stats = {"walked": 0, "resolved": 0, "deferred": 0, "not_python": 0}

    for control_dir in registered:
        manifest = control_dir / "control.json"
        if not manifest.is_file():
            continue
        try:
            spec = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entry = _python_entry(root, control_dir, spec)
        if entry is None:
            stats["not_python"] += 1
            continue
        stats["walked"] += 1
        external, repo_local, deferred, unresolvable = walk_module_level_imports(root, entry)
        stats["resolved"] += len(repo_local)
        stats["deferred"] += deferred
        for name in sorted(unresolvable):
            findings.append(
                f"CI_DEP: {control_dir.name}: an import could not be resolved to the "
                f"stdlib, to a file in this repository, or to a package the step "
                f"provides ({name}). This is UNKNOWN, not clean."
            )
        for name in sorted(external):
            stats["resolved"] += 1
            findings.append(
                f"CI_DEP: {control_dir.name}: its python gate imports `{name}` at MODULE "
                f"level, which the battery's CI step does not provide - the import runs "
                f"on load, so this control would not fail alone, it would take the whole "
                f"register down (issue #1168)"
            )
    return findings, stats


def run_check(root: Path) -> int:
    controls_dir = root / CONTROLS_REL
    if not controls_dir.is_dir():
        print(f"control-ci-deps: no {CONTROLS_REL}/ under {root}; nothing compared.")
        return 1

    registered, whence = registered_controls(root)
    if registered is None:
        print(f"CI_PIPELINE: {whence}")
        print(
            "control-ci-deps: the register could not be read; nothing compared. "
            "This is UNKNOWN, not clean."
        )
        return 1
    if not registered:
        # A population of zero makes every assertion below vacuously true and
        # prints a clean verdict over an unexamined tree - the blind-instrument
        # shape this repository refuses to ship. See docs/agents/detector-contracts.md.
        print(
            f"control-ci-deps: no gate under {root} carries a NEGATIVE-CONTROL "
            "registration; nothing compared."
        )
        return 1

    provided, notes, findings = provided_binaries(root)
    for note in notes:
        print(note)
    for finding in findings:
        print(finding)
    if provided is None:
        print(
            "control-ci-deps: the CI environment could not be derived; nothing compared. "
            "This is UNKNOWN, not clean."
        )
        return 1

    binary_gate = _load(REPO_ROOT / BINARY_GATE_REL)
    examined = 0
    missing_total = 0
    for control_dir in registered:
        if not (control_dir / "control.json").is_file():
            # Not this gate's finding: the battery already reports a
            # registration naming a directory with no manifest as UNRESOLVED,
            # and saying it again in different words sends a reader looking for
            # two problems.
            continue
        needed, control_notes = requirements(root, control_dir, binary_gate)
        for note in control_notes:
            print(f"CI_DEP: {control_dir.name}: {note}")
            missing_total += 1
        if not needed:
            continue
        examined += 1
        for binary in sorted(needed - provided):
            print(
                f"CI_DEP: {control_dir.name} needs `{binary}`, which the battery's CI step "
                f"does not provide - this control would not fail alone, it would take the "
                f"whole register down"
            )
            missing_total += 1

    py_findings, py_stats = python_import_findings(root, registered)
    for finding in py_findings:
        print(finding)
    missing_total += len(py_findings)

    print(f"CONTROL_CI_DEPS_REGISTERED: {len(registered)}")
    print(f"CONTROL_CI_DEPS_EXAMINED: {examined}")
    print(f"CONTROL_CI_DEPS_PROVIDED: {len(provided)}")
    # THE FOUR COUNTS, printed on every run including the clean one. A verdict
    # that states its population numerically cannot be read as covering more
    # than it examined, and a zero here means "looked and found none" rather
    # than "did not look" (issue #1168).
    print(f"CI_DEPS_PY_GATES_WALKED: {py_stats['walked']}")
    print(f"CI_DEPS_PY_IMPORTS_RESOLVED: {py_stats['resolved']}")
    print(f"CI_DEPS_PY_DEFERRED_UNFOLLOWED: {py_stats['deferred']}")
    print(f"CI_DEPS_INVOCATIONS_NOT_PYTHON: {py_stats['not_python']}")

    if missing_total:
        print(
            f"control-ci-deps: {missing_total} finding(s). Stage the binary into `.ci-bin` "
            "from a step the battery depends on, or make the control not need it."
        )
        return 1

    print(
        f"control-ci-deps: ok - {examined} of {len(registered)} registered control(s) declare a "
        f"binary dependency, and every one resolves against the {len(provided)} binary/ies the "
        "battery's CI step provides. Examined: the invocation command, the gate's shebang "
        "interpreter WHEN THE GATE IS RUN DIRECTLY, a shell gate's hard-required binaries, and "
        f"since #1168 the MODULE-LEVEL imports of {py_stats['walked']} python gate(s) - "
        "NOT what a Python gate shells out to, nor what a case fixture needs, nor "
        f"{py_stats['deferred']} import(s) deferred inside a function, which are conditional on "
        "a call path this reader cannot decide.\n"
        "control-ci-deps: THIS IS NECESSARY, NOT SUFFICIENT. A green here means no examined "
        "surface names something the step lacks; it does not mean a control RUNS there - "
        "issue #1163's case reached lib.cicd through a case FIXTURE, which no static surface "
        "here covers. The sufficient instrument is `make battery-in-ci-image`, which runs "
        "the battery under the pipeline's own image digest with no network and a read-only "
        "workspace."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("mode", nargs="?", default="check", choices=["check"])
    parser.add_argument("--root", default=str(REPO_ROOT), help="tree to operate on")
    args = parser.parse_args(argv)
    return run_check(Path(args.root).resolve())


if __name__ == "__main__":
    sys.exit(main())
