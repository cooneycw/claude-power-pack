#!/usr/bin/env python3
"""Certify host-surface declarations by OBSERVATION, not by reading (issue #1150).

`host-surface-check.py` catches a reachable script with NO declaration,
mechanically. It cannot catch one that UNDERSTATES - lists one surface and
writes two - and it prints that bound in its own verdict line. Every declaration
in the tree therefore reads `certified=authored`: a person read the code and
wrote down what it writes.

Detecting understatement by PARSING was rejected in #1139 with measurements that
still hold: a write-verb pattern over the two command documents matched 228
lines, mostly `echo "-> ... skipped"` caught by the `>` inside an arrow; and a
same-line survey found NOTHING for `cpp-commands-link.sh`, whose entire job is
writing `~/.claude/commands/<family>` through a computed `$TARGET`. A pattern may
propose a population; it may not certify one. Running the helper can.

So: point `HOME` at a scratch directory, run the helper, and diff what APPEARED
against what it DECLARED.

THE POPULATION IS DERIVED, NEVER LISTED (#1150 pushback, upheld)
---------------------------------------------------------------
The issue was filed saying "all 15 install-path helpers" with nine in and six
out. Re-derived at 368617e - main's tip when the issue was created - by running
that commit's own `host-surface-check.py` against that commit's command
documents, the population was SIXTEEN, of which TEN are in-`$HOME`.
`stash-worktree-guard.sh` had entered the command documents the day before, via
#1077. The roster was wrong when it was written, and the issue argues against
itself one paragraph earlier: a pattern may propose a population.

So members come from `host-surface-check.derive_members` - imported, never
re-implemented, because a second reader is a second population to keep in sync
(the #1161/#1162 direction). The eleventh script is then a FAILING TEST rather
than a silent omission.

AN UNCLASSIFIED MEMBER IS REFUSED, NOT ASSUMED SAFE
---------------------------------------------------
Every member needs a DECISION: `observable` (runnable in a sandbox) or
`escapes` (reaches outside `$HOME`, so a redirect does not sandbox it). The
decisions are declared below; the MEMBERSHIP they apply to is derived.

Defaulting an unknown member to `observable` would be the dangerous direction:
this harness EXECUTES what it classifies that way, and an unclassified newcomer
might `sudo`, `apt-get install`, or `systemctl restart`. So a member with no
decision is reported and REDS the gate without being run. That is the same
asymmetry `host-surface-check.py` already applies to an empty population -
unknown is never clean.

WHY SIX STAY `authored` PERMANENTLY
------------------------------------
Executing them would install packages, restart units and push to a remote. That
is a decision, not a shortfall, and it is recorded PER SCRIPT with the escaping
binary named, because a consumer must meet a non-uniform risk as non-uniform.

A PATH SHIM TO WIDEN COVERAGE WAS REJECTED (#1139, restated here because this is
where someone would add one). Three reasons, the third decisive: #695's
precedent, where emptying `PATH` to prove a fail-open removed `ln`, `mkdir`,
`readlink` and `bash` too, so the script failed for unrelated reasons while its
assertions still passed; a stub returning 0 can take a branch the real binary
would not; and a stub would MANUFACTURE the exact defect these scripts exist to
detect - `npm-global-upgrade.sh` exists because `npm install -g` exits 0 having
installed nothing, so a stubbed `npm` reproduces that false success verbatim.

THE SANDBOX IS VERIFIED IN THE CHILD, NOT ASSERTED IN THE PARENT
----------------------------------------------------------------
The issue rests the whole approach on "all helpers resolve home through `$HOME`
- no `getpwuid` ... one `getpwuid` and the harness would write to the real home
while reporting a sandboxed run". True of the source text, and incomplete: two
members reach it TRANSITIVELY. `codex-skill-sync.py` uses `Path.home()` and
`retired-surface-prune.py` uses `os.path.expanduser()`, both of which fall back
to `pwd.getpwuid(os.getuid()).pw_dir` when `HOME` is ABSENT. Measured:

    HOME=/tmp/sandbox   ->  /tmp/sandbox/.claude     sandboxed
    HOME unset          ->  /home/<user>/.claude     ESCAPES to the real home
    HOME=""             ->  /.claude                 broken, not an escape

The two failing states fail DIFFERENTLY and only one escapes, so both are
covered. And the check runs IN THE CHILD: a harness that verifies it exported
`HOME` is asserting its own intent, which `env -i`, a wrapper or a `sudo -E`
boundary strips silently. `check the surface, not the verdict`, applied to the
sandbox itself.

A NO-OP RUN IS NOT A CLEAN RUN
-------------------------------
These helpers take subcommands - `cpp-host-write.sh bashrc-append`,
`codex-skill-sync.py --install`. Invoked with no arguments, most do nothing, and
"nothing appeared" then satisfies "appeared is a subset of declared" perfectly.
That is a vacuous green: detector-contracts question 1, pointed at this
instrument. So each observable member carries its INVOCATION, and a run that
produced no surface at all for a script that DECLARES one is reported as
`unexercised` rather than counted as clean.

Usage:
    python3 scripts/host-surface-observe.py            # observe, exit 1 on drift
    python3 scripts/host-surface-observe.py --json     # machine-readable report
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_REL = "scripts"

#: Loaded rather than re-implemented (#1161/#1162): the population this harness
#: observes MUST be the population `host-surface-check.py` validates, or the two
#: disagree and each stays green about a different set.
_CHECK_PATH = REPO_ROOT / SCRIPTS_REL / "host-surface-check.py"

#: The battery enumerates REGISTRATIONS, not directories: a control directory
#: alone is invisible to it, and it then reports PASS over a register this
#: control is not in. Adding the cases without this line leaves the gate
#: uncontrolled while everything looks green - measured here, the battery
#: answered `matched no registration - this is UNCHECKED, not clean`.
#: NEGATIVE-CONTROL: controls/host-surface-observe


def _load_check():
    spec = importlib.util.spec_from_file_location("host_surface_check", _CHECK_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load {_CHECK_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


#: The DECISIONS. Membership is derived; these say what to do with each member.
#: A member absent from here is refused, never guessed - see the module
#: docstring.
#:
#: `escapes` names the binary that leaves `$HOME`, per script, because a
#: consumer must meet a non-uniform risk as non-uniform. Each was verified
#: present in its script before being recorded here.
ESCAPES: dict[str, str] = {
    "bash-prep.sh": "sudo",
    "drift-detect.sh": "systemctl",
    "hook-permission-census.sh": "git push, gh, docker",
    "mcp-drift.py": "docker, sudo",
    "memories-db-setup.sh": "apt, apt-get, curl",
    "npm-global-upgrade.sh": "npm install -g, sudo",
}

#: How to actually EXERCISE each observable member. `[]` means the script does
#: its work with no subcommand.
#:
#: This is not decoration. Invoked with no arguments most of these do nothing,
#: and a no-op run makes "appeared is a subset of declared" true for free - the
#: vacuous green this instrument would otherwise hand out. The first draft of
#: this table listed `zshrc-append`, which `cpp-host-write.sh` does not have
#: (it is `rc-append`), and the run reported UNEXERCISED rather than clean.
#: That report is the guard working; keep it working.
#:
#: `{HOME}` is the sandbox. `{CONTENT}` is a caller-supplied content file that
#: is created OUTSIDE the sandbox on purpose: put it inside and it appears in
#: the after-snapshot as a surface the helper never wrote, which reads as an
#: understatement the helper is not guilty of.
INVOCATIONS: dict[str, list[list[str]]] = {
    "cpp-host-write.sh": [
        ["ensure-dir", "{HOME}/.claude"],
        ["ensure-dir", "{HOME}/.claude/scripts"],
        ["bashrc-append", "cpp-observe", "{CONTENT}"],
        ["rc-append", "{HOME}/.zshrc", "cpp-observe", "{CONTENT}"],
        ["file-write", "{HOME}/.config/claude-power-pack/secrets/cpp-memories.backend", "local"],
    ],
    "cpp-commands-link.sh": [["--check"], []],
    "codex-skill-sync.py": [["--install"]],
    "install-memory-harness.sh": [[]],
    "commands-mirror-sync.sh": [[]],
    "hook-pending-retro.sh": [[]],
    "install-drift.sh": [[]],
    "prompt-context.sh": [[]],
    "retired-surface-prune.py": [["--dry-run"]],
    "stash-worktree-guard.sh": [["status"]],
}

#: A case tree supplies its OWN classification, and the real repository must
#: not (issue #1150).
#:
#: Without this, a committed control is impossible to make discriminating. A
#: fixture script is not in the tables above, so it would be UNCLASSIFIED and
#: red - the right exit code for the wrong reason, reachable by a gate that
#: detects understatement and equally by one that detects nothing. That is the
#: trap #1139's control nearly shipped: "a case whose expected answer both
#: sides can reach proves nothing."
#:
#: It is a live risk in the other direction too - the same file could silence
#: the gate for the real tree - so its use is REPORTED on every run and it is
#: REFUSED at the repository root outright (see `load_classification`).
#:
#: THESE LINES ONCE CLAIMED A TEST ENFORCED THAT, AND NO SUCH TEST EXISTED.
#: The claim sat here and in control.json's `limits` through a full
#: implementation, and counter-model review found it; re-reading did not,
#: because re-reading checks what a comment MEANT. A claimed check that does
#: not exist is this instrument's own subject, committed in its documentation.
CLASSIFICATION_REL = ".host-surface-observe.json"


def load_classification(root: Path) -> tuple[dict[str, str], dict[str, list[list[str]]], bool]:
    """`(escapes, invocations, root_supplied)` for this tree."""
    escapes = dict(ESCAPES)
    invocations = {k: [list(a) for a in v] for k, v in INVOCATIONS.items()}
    path = root / CLASSIFICATION_REL
    if not path.is_file():
        return escapes, invocations, False
    #: REFUSED at the real repository root (counter-model review, #1150). The
    #: first cut accepted it anywhere, so `{"escapes": {"codex-skill-sync.py":
    #: "fixture"}}` committed here would skip that helper's execution AND the
    #: enforcement of its `certified=observed` declarations, and still report a
    #: clean verdict. The comments claimed a test forbade this; no such test
    #: existed - a claim of a check, in a change about claims nothing checks.
    #: Now the refusal is in the code and the test exists.
    if root.resolve() == REPO_ROOT.resolve():
        raise SystemExit(
            f"host-surface-observe: REFUSED - {CLASSIFICATION_REL} exists at the "
            "repository root. That file EXTENDS the classification and can move a "
            "helper into `escapes`, skipping both its execution and the enforcement "
            "of its declarations. It is for control case trees only."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    escapes.update(data.get("escapes", {}))
    invocations.update({k: [list(a) for a in v] for k, v in data.get("invocations", {}).items()})
    return escapes, invocations, True


#: Ask the CHILD where it thinks home is, in the env the helper will get.
_HOME_PROBE = (
    "import os,pathlib;"
    "print(os.environ.get('HOME','<unset>'));"
    "print(pathlib.Path.home());"
    "print(os.path.expanduser('~'))"
)


@dataclass
class Observation:
    """What one member did, or why it was not run."""

    name: str
    decision: str  # observable | escapes | UNCLASSIFIED
    reason: str = ""
    declared: list[str] = field(default_factory=list)
    appeared: list[str] = field(default_factory=list)
    undeclared: list[str] = field(default_factory=list)
    #: PER SURFACE, not per script. "This script is certified" would claim the
    #: whole declaration on the strength of whichever surface happened to be
    #: reachable by the invocation - `cpp-host-write.sh` declares seven, and an
    #: invocation exercising one would certify the other six for free.
    observed_surfaces: list[str] = field(default_factory=list)
    unobserved_surfaces: list[str] = field(default_factory=list)
    false_claims: list[str] = field(default_factory=list)
    unrunnable: list[int] = field(default_factory=list)
    stale_claims: list[str] = field(default_factory=list)
    runs: int = 0
    exercised: bool = False
    exit_codes: list[int] = field(default_factory=list)


def snapshot(root: Path) -> set[str]:
    """Every path under `root`, relative and POSIX-spelled.

    Directories are included: `~/.claude owner=cpp write=mkdir` is a declared
    surface, so a created directory is an appearance like any other.
    """
    out: set[str] = set()
    for p in root.rglob("*"):
        try:
            out.add(p.relative_to(root).as_posix())
        except ValueError:  # pragma: no cover - defensive
            continue
    return out


def declared_surfaces(text: str, check) -> list[tuple[str, str, str]]:
    """Declared surfaces as `(path, write-verb)`, sandbox-relative and POSIX.

    A declaration reads `~/.claude/settings.json owner=cpp write=merge ...`;
    only the leading token is a path. `note - ...` bodies carry prose, not a
    path, and are skipped rather than parsed into a bogus surface.

    The VERB is carried because coverage depends on it - see `covered_by`.
    """
    surfaces: list[tuple[str, str, str]] = []
    for body in check.declarations(text):
        parts = body.split()
        head = parts[0] if parts else ""
        if not head.startswith("~/"):
            continue  # `none`, `unresolved`, or a `note - ...` line
        verb = next((p[len("write="):] for p in parts if p.startswith("write=")), "")
        cert = next((p[len("certified="):] for p in parts if p.startswith("certified=")), "")
        surfaces.append((head[2:], verb, cert))
    return surfaces


def declares_unresolved(text: str, check) -> bool:
    """Does this script declare its surface UNRESOLVED?

    `unresolved` is not `none`, and collapsing the two defeats a guard somebody
    put there on purpose. `retired-surface-prune.py` reads its target from DATA
    at run time and says so, with the reason recorded beside the declaration:
    "an unresolvable target dropped from a manifest reads as 'no surface here',
    which is the drift this seam exists to make visible."

    This instrument read it as exactly that - no `~/` prefix, so no surfaces, so
    nothing to compare, so counted among the certified. An `unresolved`
    declaration is the one case where there is NOTHING to check understatement
    against, and it was being certified by observation precisely because
    observation had nothing to look at. So it gets its own state and stays out
    of the certified count.
    """
    return any(body.split()[:1] == ["unresolved"] for body in check.declarations(text))


def covered_by(appeared: str, declared: list[tuple[str, str, str]]) -> bool:
    """Is this appeared path accounted for by some declaration?

    COVERAGE DEPENDS ON THE WRITE VERB, and getting this wrong made every
    declaration in this change unverifiable (issue #1150, found by the
    two-sided demonstration rather than by review).

    `write=mkdir` declares that a DIRECTORY NODE is created. It covers exactly
    that path and nothing beneath it. The first cut let it cover the whole
    subtree, and the consequence was silent: with `~/.codex` declared, removing
    the `~/.codex/skills` declaration changed no verdict, so the added
    declarations could not be shown to matter and the instrument was certifying
    its own input. The tree says the same thing on its own - `cpp-host-write.sh`
    declares `~/.claude`, `~/.claude/scripts` AND `~/.claude/settings.json`
    separately, which is redundant under subtree coverage and necessary under
    this rule.

    Every other verb - copy, symlink, merge, append, replace, json-merge -
    writes CONTENT at the path, so what appears beneath it is that surface's
    content and is covered.

    `<placeholder>` segments match exactly one path segment: `~/.codex/skills/
    <skill>` means a skill directory, not a subtree spelled literally.
    """
    ap = appeared.split("/")
    for dec, verb, _cert in declared:
        dp = dec.split("/")
        if verb == "mkdir":
            if len(ap) != len(dp):
                continue
        elif len(ap) < len(dp):
            continue
        ok = True
        for want, got in zip(dp, ap):
            if want.startswith("<") and want.endswith(">"):
                continue
            if want != got:
                ok = False
                break
        if ok:
            return True
    return False


def child_home(env: dict[str, str]) -> tuple[str, str, str]:
    """What the CHILD resolves home to, in the env a helper would receive."""
    res = subprocess.run(
        [sys.executable, "-c", _HOME_PROBE],
        capture_output=True, text=True, env=env, timeout=30,
    )
    lines = (res.stdout or "").splitlines()
    while len(lines) < 3:
        lines.append("")
    return lines[0], lines[1], lines[2]


#: THE CHILD ENVIRONMENT IS AN ALLOWLIST, NOT A COPY (counter-model review,
#: #1150). The first cut passed `os.environ` through with only `HOME`
#: replaced, and that is not a sandbox: `cpp-commands-link.sh:183` reads
#: `HOME_DIR="${CPP_COMMANDS_LINK_HOME:-$HOME}"`, so a caller with that
#: variable set writes into the REAL home while every check here passes. The
#: probe measures a separate Python process resolving `~`; it does not
#: constrain where an installer decides to write. `BASH_ENV` is the same shape
#: through shell startup.
#:
#: Measured before the fix: with CPP_COMMANDS_LINK_HOME=/home/<user> exported,
#: the variable reached the child and `verify_sandbox` reported NO refusals.
#:
#: The set is what is ALLOWED and it is closed, which is this repository's own
#: answer to the same problem (#1165): a denylist can only name the overrides
#: somebody already imagined, and the one that bit here was documented in the
#: helper's own declaration note the whole time.
ENV_ALLOWLIST = frozenset({
    "PATH", "LANG", "LC_ALL", "TERM", "TZ", "SHELL", "USER", "LOGNAME",
})


def sandbox_env(sandbox: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}
    env["HOME"] = str(sandbox)
    #: TMPDIR inside the sandbox too: a helper writing to /tmp is not writing to
    #: a host surface, but keeping its scratch inside the tree we snapshot means
    #: we SEE it rather than miss it.
    env["TMPDIR"] = str(sandbox / ".tmp")
    (sandbox / ".tmp").mkdir(parents=True, exist_ok=True)
    return env


def verify_sandbox(sandbox: Path, real_home: Path) -> list[str]:
    """Refuse unless the CHILD resolves home inside the sandbox.

    Returns a list of refusals; empty means safe to proceed. Asserting our own
    export would be asserting intent - this asks the child.
    """
    problems: list[str] = []
    env = sandbox_env(sandbox)
    home_env, path_home, expanded = child_home(env)

    if home_env != str(sandbox):
        problems.append(f"child HOME is {home_env!r}, expected {str(sandbox)!r}")
    for label, got in (("Path.home()", path_home), ("expanduser('~')", expanded)):
        try:
            inside = Path(got).resolve().is_relative_to(sandbox.resolve())
        except (OSError, ValueError):  # pragma: no cover - defensive
            inside = False
        if not inside:
            problems.append(f"child {label} resolved to {got!r}, outside the sandbox")
        try:
            if Path(got).resolve().is_relative_to(real_home.resolve()):
                problems.append(f"child {label} resolved INSIDE THE REAL HOME: {got!r}")
        except (OSError, ValueError):  # pragma: no cover - defensive
            pass
    return problems


INVOCATIONS_FOR: dict[str, list[list[str]]] = {}


def observe(
    name: str, script: Path, declared: list[tuple[str, str, str]], real_home: Path
) -> Observation:
    """Run one member twice, each against a FRESH sandbox, and diff."""
    obs = Observation(name=name, decision="observable", declared=[p for p, _, _ in declared])
    invocations = INVOCATIONS_FOR.get(name, [[]])

    #: TWO RUNS, NOT ONE. A single run cannot distinguish a guard that works
    #: from one that was never exercised - #1139's relocation was proved
    #: byte-identical only across two runs. Each gets a FRESH sandbox so the
    #: second run cannot inherit the first's surfaces and read as idempotent.
    for run_index in range(2):
        for argv in invocations:
            sandbox = Path(tempfile.mkdtemp(prefix="cpp-host-observe-"))
            content_dir = sandbox  # rebound below; never unbound in `finally`
            try:
                refusals = verify_sandbox(sandbox, real_home)
                if refusals:
                    obs.decision = "REFUSED"
                    obs.reason = "; ".join(refusals)
                    return obs

                before = snapshot(sandbox)
                #: The content file lives OUTSIDE the sandbox. Inside, it would
                #: show up in the after-snapshot as a surface the helper never
                #: wrote, and be reported as an understatement it is not guilty
                #: of - the harness framing its own subject.
                content_dir = Path(tempfile.mkdtemp(prefix="cpp-host-observe-in-"))
                content = content_dir / "content.sh"
                content.write_text("# cpp-observe probe\n", encoding="utf-8")
                resolved = [
                    a.replace("{HOME}", str(sandbox)).replace("{CONTENT}", str(content))
                    for a in argv
                ]
                #: THE PYTHON FALLBACK IS FOR PYTHON, and was not (counter-model
                #: review, #1150). Anything non-executable went to `sys.executable`
                #: including `.sh` files, so a shell helper whose executable bit was
                #: unset died on a SyntaxError and exited 1 - which is NOT in the
                #: unrunnable set, because 1 is a legitimate drift verdict on the
                #: `--check` lanes. The helper never ran and, declaring no surfaces,
                #: was reported CONSISTENT.
                #:
                #: The earlier ruling that this needed no fix rested on the 126
                #: path - "found but not executable" - which never occurs, because
                #: the fallback prevents the permission error from happening at all.
                #: A member that did not really run must not count as fine; that is
                #: the same class as the `unresolved` state and the skip-branch
                #: enforcement already in this change.
                if os.access(script, os.X_OK):
                    cmd = [str(script), *resolved]
                elif script.suffix == ".py":
                    cmd = [sys.executable, str(script), *resolved]
                else:
                    obs.decision = "REFUSED"
                    obs.reason = (
                        f"{script.name} is not executable and is not a .py file, so "
                        "there is no interpreter to run it with. Handing it to python "
                        "produces a SyntaxError and exit 1, which reads as a drift "
                        "verdict from a helper that never ran"
                    )
                    return obs
                try:
                    res = subprocess.run(
                        cmd, capture_output=True, text=True,
                        env=sandbox_env(sandbox), cwd=str(REPO_ROOT), timeout=120,
                    )
                    obs.exit_codes.append(res.returncode)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    obs.decision = "REFUSED"
                    obs.reason = f"could not run: {exc}"
                    return obs

                after = snapshot(sandbox)
                for rel in sorted(after - before):
                    if rel not in obs.appeared:
                        obs.appeared.append(rel)
                obs.runs += 1
            finally:
                #: BOTH directories. The content dir sat outside this `finally`
                #: and leaked once per invocation - 28 per run, measured, with
                #: ~1500 accumulated in /tmp from this change's own development.
                #: A harness that litters is a harness people stop running.
                shutil.rmtree(sandbox, ignore_errors=True)
                shutil.rmtree(content_dir, ignore_errors=True)

    obs.undeclared = [a for a in obs.appeared if not covered_by(a, declared)]
    obs.observed_surfaces = [
        path for path, verb, _c in declared
        if any(covered_by(a, [(path, verb, _c)]) for a in obs.appeared)
    ]
    obs.unobserved_surfaces = [
        path for path, _, _ in declared if path not in obs.observed_surfaces
    ]
    #: `certified=` IS ENFORCED, not decoration. A surface claiming `observed`
    #: that this run did not observe is a false claim in the reassuring
    #: direction - the label a consumer weighs MORE, attached to evidence
    #: nobody produced. The reverse (`authored` on a surface we did observe) is
    #: merely stale and is reported, not failed: understating your own
    #: certification misleads nobody.
    obs.false_claims = [
        path for path, _, cert in declared
        if cert == "observed" and path not in obs.observed_surfaces
    ]
    obs.stale_claims = [
        path for path, _, cert in declared
        if cert == "authored" and path in obs.observed_surfaces
    ]
    #: A script that DECLARES surfaces and produced NONE of them was not
    #: exercised; its clean diff is vacuous, not evidence.
    obs.exercised = bool(obs.observed_surfaces) or not declared
    #: 127 is "could not run it at all" and a negative code is a signal. Either
    #: way the run measured nothing, and the exit codes were previously RECORDED
    #: and never read - a field that exists and decides nothing (counter-model
    #: review, #1150). Codes like 1/3/4 are NOT failures here: `--check` lanes
    #: use them for drift states, so treating nonzero as broken would report
    #: every drift-reporting helper as unrunnable.
    #: 127 = not found, 126 = found but NOT EXECUTABLE, negative = signal.
    #: 126 was missed on the first cut (counter-model review): a helper whose
    #: bit is unset runs nothing and, declaring no surface, was reported
    #: `consistent` - the exact conflation of `ran and produced nothing` with
    #: `could not run` that this field exists to separate.
    obs.unrunnable = [c for c in obs.exit_codes if c in (126, 127) or c < 0]
    return obs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args(argv)
    root: Path = args.root

    check = _load_check()
    escapes_tbl, invocations_tbl, root_supplied = load_classification(root)
    members, warnings = check.derive_members(root)
    for w in warnings:
        print(f"host-surface-observe: {w}", file=sys.stderr)

    if not members:
        print(
            "host-surface-observe: UNKNOWN - derived an empty population, so "
            "this run establishes nothing about any declaration"
        )
        return 1

    real_home = Path(os.path.expanduser("~"))
    observations: list[Observation] = []

    for name in sorted(members):
        script = root / SCRIPTS_REL / name
        #: DECLARATIONS ARE READ BEFORE THE SKIP BRANCHES (counter-model review,
        #: #1150). They used to be read only on the path that RUNS a helper, so a
        #: member skipped as `escapes` or `unresolved` could carry a concrete
        #: `certified=observed` declaration that this gate never verified - and
        #: the report still said those members stay `authored`. A skipped member
        #: advertising a certification nothing produced is the same overclaim the
        #: FALSE CLAIM check exists to refuse, reached by the one path that
        #: skipped the check.
        #:
        #: The exclusion of escaping helpers is preserved exactly: they are still
        #: never executed. What is enforced without executing them is that they
        #: do not CLAIM to have been.
        skip_declared = (
            declared_surfaces(check.read(script), check) if script.is_file() else []
        )
        unverifiable = [pth for pth, _v, cert in skip_declared if cert == "observed"]

        if name in escapes_tbl:
            obs = Observation(name=name, decision="escapes", reason=escapes_tbl[name])
            obs.false_claims = unverifiable
            observations.append(obs)
            continue
        if name not in invocations_tbl:
            #: Never assumed observable: this harness EXECUTES what it classifies
            #: that way, and an unclassified newcomer might sudo or apt-get.
            observations.append(Observation(name=name, decision="UNCLASSIFIED"))
            continue
        if not script.is_file():
            observations.append(
                Observation(name=name, decision="UNCLASSIFIED", reason="script not found")
            )
            continue
        text = check.read(script)
        if declares_unresolved(text, check):
            obs = Observation(
                name=name,
                decision="unresolved",
                reason="declares its surface unresolved - the target is read from data at "
                       "run time, so there is nothing for observation to compare against",
            )
            #: A mixed declaration - `unresolved` PLUS a concrete surface marked
            #: observed - skips the run and would otherwise keep the claim.
            obs.false_claims = unverifiable
            observations.append(obs)
            continue
        declared = declared_surfaces(text, check)
        INVOCATIONS_FOR.clear()
        INVOCATIONS_FOR.update(invocations_tbl)
        observations.append(observe(name, script, declared, real_home))

    unclassified = [o for o in observations if o.decision == "UNCLASSIFIED"]
    refused = [o for o in observations if o.decision == "REFUSED"]
    understating = [o for o in observations if o.undeclared]
    unexercised = [o for o in observations if o.decision == "observable" and not o.exercised]
    false_claimers = [o for o in observations if o.false_claims]
    #: TWO DIFFERENT FACTS, previously one number (counter-model review, #1150).
    #: A helper that DECLARED a surface and was watched writing it is CERTIFIED
    #: by observation. A helper that declares nothing, ran, and produced nothing
    #: is merely CONSISTENT with its declaration: the run falsified nothing and
    #: confirmed nothing, and it is equally consistent with a no-op - and two
    #: of them are shipped no-ops, since `stash-worktree-guard.sh` has no
    #: `status` command and `commands-mirror-sync.sh` examines nothing without a
    #: configured mirror. Counting those as "certified by observation" claimed
    #: more than the input population supports, in the verdict line of an
    #: instrument whose subject is exactly that.
    observed = [
        o for o in observations
        if o.decision == "observable" and not o.undeclared and o.observed_surfaces
    ]
    consistent = [
        o for o in observations
        if o.decision == "observable" and not o.undeclared and not o.declared
    ]
    unrunnable = [o for o in observations if o.unrunnable]
    escaping = [o for o in observations if o.decision == "escapes"]
    unresolved = [o for o in observations if o.decision == "unresolved"]

    #: `--json` puts the JSON and NOTHING ELSE on stdout. Emitting the prose
    #: report after it left a parser reading "Extra data: line 700" - found by
    #: consuming this instrument's own output, which is the only way a
    #: machine-readable flag gets tested. The human lines go to stderr so a
    #: caller still sees them without having to parse around them.
    out = sys.stderr if args.json else sys.stdout
    if args.json:
        print(json.dumps({o.name: o.__dict__ for o in observations}, indent=2, default=str))

    if root_supplied:
        print(
            f"host-surface-observe: classification supplied by {CLASSIFICATION_REL} "
            f"under {root} - built-in decisions were EXTENDED by that file",
            file=out,
        )
    for o in refused:
        print(f"host-surface-observe: REFUSED - {o.name}: {o.reason}", file=out)
    for o in unclassified:
        print(
            f"host-surface-observe: UNCLASSIFIED - {o.name} is in the derived "
            "population with no observable/escapes decision; it was NOT run",
            file=out,
        )
    for o in understating:
        print(f"host-surface-observe: UNDERSTATED - {o.name} wrote surfaces it did not declare:", file=out)
        for rel in o.undeclared:
            print(f"    ~/{rel}", file=out)
    for o in unexercised:
        print(
            f"host-surface-observe: UNEXERCISED - {o.name} declares "
            f"{len(o.declared)} surface(s) and produced none; its clean diff is "
            "vacuous, not evidence",
            file=out,
        )

    for o in false_claimers:
        for surface in o.false_claims:
            print(
                f"host-surface-observe: FALSE CLAIM - {o.name} declares ~/{surface} "
                "certified=observed, but this run did not observe it",
                file=out,
            )
    for o in observations:
        for surface in o.stale_claims:
            print(
                f"host-surface-observe: stale - {o.name} declares ~/{surface} "
                "certified=authored, but this run observed it; it can move to observed",
                file=out,
            )
    for o in unrunnable:
        print(
            f"host-surface-observe: UNRUNNABLE - {o.name} exited {o.unrunnable} - "
            "the run measured nothing about its declarations",
            file=out,
        )
    if refused or unclassified or understating or unexercised or false_claimers or unrunnable:
        print(
            f"\nhost-surface-observe: {len(observed)} of {len(observations)} member(s) "
            f"certified by observation; {len(escaping)} permanently authored",
            file=out,
        )
        return 1

    #: An UNOBSERVED surface must be VISIBLE as unobserved, not merely absent
    #: from the observed list. "Those declarations move to observed" would
    #: otherwise certify a surface nothing watched - a certification produced
    #: by not looking, which is this instrument's own subject.
    for o in observations:
        for surface in o.unobserved_surfaces:
            print(
                f"host-surface-observe: unobserved - {o.name} declares ~/{surface}, "
                "which no invocation here reaches; it stays certified=authored",
                file=out,
            )
    for o in unresolved:
        print(f"host-surface-observe: unresolved - {o.name}: {o.reason}", file=out)
    print(
        f"host-surface-observe: ok - {len(observed)} member(s) were watched writing "
        f"a surface they declared and left nothing behind that they did not; {len(consistent)} declare no "
        f"surface and produced none, which is CONSISTENT with the declaration and is not "
        f"a certification (a no-op run looks the same); {len(escaping)} reach outside "
        f"$HOME and stay certified=authored",
        file=out,
    )
    #: ACCEPTANCE ITEM 5 IS NOT MET, AND THIS SAYS SO WHERE THE VERDICT IS READ
    #: (#1150). "The real $HOME is never a target" is what a redirected HOME buys
    #: for a write that RESOLVES home through $HOME. It is not containment: a
    #: repository-configured core.fsmonitor executes an arbitrary command on the
    #: `git diff` and `git ls-files` calls some helpers make, and such a write
    #: lands outside these snapshots entirely.
    #:
    #: Printed on the SUCCESS path on purpose. A bound that appears only when
    #: something fails is a bound nobody reading the green ever meets - which is
    #: this instrument's own subject, and the reason host-surface-check.py prints
    #: its own bound in its own ok line.
    print(
        "  snapshots compare BEFORE and AFTER, so they establish which paths\n"
        "  SURVIVED to be inspected - not everything a helper wrote. A helper that\n"
        "  creates an undeclared path and removes it before exiting passes, and that\n"
        "  happens inside the redirected $HOME, so the containment note below does\n"
        "  not cover it. Detecting a transient write needs execution tracing, which\n"
        "  this design does not do and #1182 does not answer either.",
        file=out,
    )
    print(
        "  not contained: this run REDIRECTS $HOME, it does not CONFINE the "
        "filesystem. A write that does not resolve home through $HOME - a "
        "repo-configured core.fsmonitor firing on a helper's `git diff`, for "
        "instance - is outside what these snapshots can see. `observed` means "
        "watched through those paths, not proven confined (issue #1182).",
        file=out,
    )
    for o in escaping:
        print(f"    {o.name}: escapes via {o.reason}", file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
