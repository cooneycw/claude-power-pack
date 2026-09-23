"""CONSTRUCTED BLIND ANCHOR for controls/host-surface-observe (issue #1150).

This is scripts/host-surface-observe.py with ONE BLINDING: `covered_by` always
returns True, so every appeared path counts as declared and no understatement
can ever be reported. It is the gate with its comparison removed and everything
else - the derived population, the sandbox refusal, the ALLOWLISTED child
environment, the GIT CONTAINMENT refusal, the two runs, the vacuity guard - left
intact.

That is deliberately the NARROWEST possible blinding. An anchor that also broke
the sandbox or the population would miss the known-bad for reasons unrelated to
the property under test, and would pass this control while establishing nothing
about whether the comparison works.

THE BLINDING IS NOT THE ONLY DIFFERENCE, and whoever regenerates this next
should read that sentence twice. `REPO_ROOT` below resolves `parents[3]` rather
than the gate's `parents[1]` - an ADAPTATION, not a blinding, and it is load
bearing. Regenerating this file mechanically from the gate reapplies the
blinding and silently drops the adaptation; the anchor then CRASHES on the
known-bad instead of MISSING it, which is a different thing and the battery says
so (`UNRESOLVED`, not `PASS`). That is exactly what happened during the #1182
regeneration, and the comment beside REPO_ROOT had already predicted it.

REGENERATED FROM THE HARDENED SOURCE, TWICE NOW, FOR THE SAME REASON. The first
anchor was cut from the gate BEFORE the environment allowlist landed, so it kept
`dict(os.environ)` and forwarded `BASH_ENV` and `CPP_COMMANDS_LINK_HOME` into the
fixture it executes. The second regeneration is issue #1182: the gate learned to
neutralise the command-executing git configuration a repository can carry, and an
anchor left at the pre-#1182 source would have gone on running `git` with a live
`core.fsmonitor` route. An anchor is run by the battery like any other program: a
stale copy does not just misrepresent the gate, it CARRIES the live escape the
gate was fixed for. Anchors are frozen by sha256 on purpose, so regenerating one
is a deliberate act with a new digest - not a refresh that happens by itself.

The gate is new, so no previous blind version exists to vendor.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

#: parents[3], not [1]: this anchor lives at controls/<name>/anchors/, so the
#: gate's own depth would resolve the repo root inside controls/ and the anchor
#: would CRASH on the known-bad instead of MISSING it. An anchor must be blind,
#: not broken - a crash establishes nothing about whether the comparison works.
#: THIS IS AN ADAPTATION, NOT A BLINDING. A mechanical regeneration from the
#: gate drops it; #1182's regeneration did exactly that and the battery caught
#: it as UNRESOLVED.
REPO_ROOT = Path(__file__).resolve().parents[3]
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
    return True  # BLINDED: the comparison this control exists to test
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
    return _with_git_overrides(env, REPO_ROOT)


#: GIT EXECUTES COMMANDS THE REPOSITORY CONFIGURES, AND $HOME DOES NOT REACH
#: THEM (issue #1182). Redirecting HOME sandboxes a write that RESOLVES home
#: through $HOME. It does nothing about `core.fsmonitor`, which lives in the
#: checkout's own `.git/config` and which git EXECUTES on the `git diff` and
#: `git ls-files` calls some members make - `cpp-commands-link.sh:345-346` is
#: the live one. Such a write lands outside these snapshots entirely and the
#: run still reports clean.
#:
#: THIS TABLE IS MEASURED, NOT REASONED. Every candidate was planted with a
#: canary in a scratch repo and the three git commands these members actually
#: run were executed against it (git 2.43.0, 2026-09-23):
#:
#:     core.fsmonitor              FIRES on status, diff --name-only, ls-files
#:     filter.<driver>.clean       FIRES on status, diff --name-only
#:     filter.<driver>.smudge      -
#:     diff.external               -
#:     diff.<driver>.textconv      -
#:     core.pager / core.editor    -
#:     core.askPass                -
#:     credential.helper           -
#:     core.sshCommand             -
#:     core.gitProxy               -
#:     uploadpack.packObjectsHook  -
#:     core.alternateRefsCommand   -
#:     gpg.program                 -
#:     sequence.editor             -
#:     trailer.<token>.command     -
#:
#: `filter.<driver>.clean` was NOT one of the three routes #1182 was filed for.
#: It was found by RUNNING this enumeration, which is the whole argument for
#: acceptance item 3: the dashes above are worth reading only because
#: `core.fsmonitor` in the same column FIRES. A search that has never been shown
#: to find a route cannot tell "no more routes" from "cannot see one".
GIT_EXEC_CONFIG_NEUTRALISED: dict[str, str] = {"core.fsmonitor": "false"}

#: Filter drivers cannot be neutralised BY NAME - the driver name is arbitrary -
#: so they are DISCOVERED in the configuration that is actually in force and
#: disabled individually. An empty value is what disables one; measured.
#: `.*`, NOT `.+` (counter-model review round 2, #1182). Git accepts an EMPTY
#: subsection - `[filter ""]`, selected by the attribute `filter=` - and lists
#: it as `filter..clean`. `.+` rejected that, so the driver stayed live while
#: the verdict claimed configured filters were neutralised. Measured.
_GIT_EXEC_FILTER_RE = re.compile(r"^filter\..*\.(?:clean|smudge|process)$")

#: THE GIT ENVIRONMENT IS A CLOSED ALLOWLIST, NOT A DENYLIST (counter-model
#: review rounds 1 and 2, #1182). Measured: with `GIT_CONFIG=<file>` exported,
#: `git -C <scratch> config core.fsmonitor <cmd>` writes into <file> and leaves
#: <scratch> untouched - so this probe wrote a `core.fsmonitor` into the
#: CALLER'S OWN git configuration, a host surface, from the instrument whose
#: entire job is bounding host-surface writes, and its cleanup then deleted the
#: script that entry pointed at.
#:
#: The first fix enumerated the selectors to STRIP. That was the wrong shape and
#: round 2 proved it with a variable the list had not imagined: `GIT_TRACE` takes
#: an ABSOLUTE PATH and git appends to it, measured at 75 bytes written outside
#: the scratch tree by discovery alone. A denylist can only name the overrides
#: somebody already thought of - which is the reasoning ENV_ALLOWLIST itself
#: records one screen above, applied here a round later than it should have been.
#:
#: So git subprocesses inherit exactly ENV_ALLOWLIST plus a scratch HOME. That
#: HOME is also what keeps DISCOVERY honest: the children read config under a
#: fresh sandbox HOME, so discovery must too, or it reads a global configuration
#: the children will never see.


class GitDiscoveryError(RuntimeError):
    """Raised when the configuration in force could not be READ.

    A discovery that failed is not a discovery that found nothing. Returning the
    fixed overrides on error made an unreadable configuration byte-identical to
    a clean one, which is the defect this whole script exists to refuse, located
    in its own plumbing.
    """


def sanitised_git_env(home: str | os.PathLike[str]) -> dict[str, str]:
    """An environment in which the PARENT cannot redirect git, at all.

    Built from ENV_ALLOWLIST rather than by removing known-bad names, so a
    selector nobody has thought of is excluded by construction.
    """
    env = {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}
    env["HOME"] = str(home)
    return env


_OVERRIDES_CACHE: dict[str, list[tuple[str, str]]] = {}


def git_exec_config_overrides(repo: Path) -> list[tuple[str, str]]:
    """`(key, value)` pairs disabling every command-executing config we can name.

    Raises `GitDiscoveryError` when the configuration cannot be read.
    """
    key = str(repo)
    if key in _OVERRIDES_CACHE:
        return list(_OVERRIDES_CACHE[key])
    overrides = sorted(GIT_EXEC_CONFIG_NEUTRALISED.items())
    #: `--null --name-only` instead of parsing `key=value` (counter-model review,
    #: #1182). Git accepts a subsection containing `=`: `[filter "a=b"]` renders
    #: as `filter.a=b.clean=<cmd>`, and splitting on the first `=` yields
    #: `filter.a`, so no override was installed and that filter stayed live while
    #: the verdict claimed configured filters were neutralised. Measured, and the
    #: fsmonitor-only canary cannot see it.
    scratch_home = Path(tempfile.mkdtemp(prefix="cpp-observe-githome-"))
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "config", "--null", "--name-only", "--list"],
            capture_output=True, text=True, timeout=30,
            env=sanitised_git_env(scratch_home),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitDiscoveryError(f"could not read the git configuration in force ({exc})") from exc
    finally:
        shutil.rmtree(scratch_home, ignore_errors=True)
    if res.returncode != 0:
        raise GitDiscoveryError(
            "could not read the git configuration in force "
            f"(git exited {res.returncode}: {(res.stderr or '').strip()[:200]})"
        )
    for name in (res.stdout or "").split("\0"):
        if _GIT_EXEC_FILTER_RE.match(name):
            overrides.append((name, ""))
    _OVERRIDES_CACHE[key] = list(overrides)
    return overrides


def _with_git_overrides(env: dict[str, str], repo: Path) -> dict[str, str]:
    """Inject the neutralising config as `-c`-equivalent environment entries.

    AFTER the ENV_ALLOWLIST filter, and the keys are NEVER MEMBERS OF IT (issue
    #1182). These values are SET BY US. Adding `GIT_CONFIG_*` to the allowlist
    would instead let a PARENT-set value through into the child - a new escape of
    exactly the shape #1150 closed when it replaced the wholesale environment
    copy with a closed allowlist, so the fix would reintroduce the class it
    exists to close. A comment does not prevent that; the red case in
    tests/test_host_surface_observe.py does.
    """
    for stale in [k for k in env if k.startswith("GIT_CONFIG")]:
        del env[stale]
    try:
        overrides = git_exec_config_overrides(repo)
    except GitDiscoveryError:
        #: NARROW, and deliberately not a general fail-open. With no git binary
        #: there is no git child to redirect, so the fixed keys are inert and
        #: injecting them costs nothing; `verify_git_containment` has already
        #: reported that state in the bound. With git PRESENT, a failed
        #: discovery is a REFUSAL that happened before this point, so reaching
        #: here means something is wrong and it must not be swallowed.
        if shutil.which("git") is not None:
            raise
        overrides = sorted(GIT_EXEC_CONFIG_NEUTRALISED.items())
    env["GIT_CONFIG_COUNT"] = str(len(overrides))
    for i, (key, value) in enumerate(overrides):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    return env


_CANARY_SCRIPT = '#!/bin/sh\n: > "$CPP_OBSERVE_CANARY"\nexit 1\n'


def containment_bound_text() -> str:
    """The containment bound, DERIVING the key names from what is enforced.

    A hand-written list drifts from the table it describes, and the drifted
    version reads exactly as authoritative as the accurate one. Extracted from
    `main` so the agreement can be tested without running the whole gate - an
    assertion that costs minutes is one that gets deleted.
    """
    return (
        "  not contained: this run REDIRECTS $HOME and NEUTRALISES the "
        "command-executing git config it can name ("
        + ", ".join(sorted(GIT_EXEC_CONFIG_NEUTRALISED))
        + ", plus any filter driver configured in the checkout), verified by a "
        "canary REQUIRED to fire with the neutralisation removed"
        + (
            "" if shutil.which("git") is not None else
            " - BUT NO GIT BINARY IS PRESENT on this host, so that route does not "
            "exist here and the canary did not run; this line reports that state "
            "rather than folding it into 'verified'"
        )
        + ". It still does "
        "not CONFINE the filesystem. That neutralisation is an ENUMERATION and "
        "is only as strong as its candidate list: a git config key nobody has "
        "measured, or a write through a channel that is not git at all, remains "
        "outside what these snapshots can see. `observed` means watched through "
        "those paths, not proven confined (issue #1182)."
    )


def verify_git_containment() -> list[str]:
    """Refuse unless a planted `core.fsmonitor` fails to fire under the sandbox
    environment - AND fires with the neutralisation removed.

    The second half is the POSITIVE CONTROL and is not optional. "The canary did
    not fire" is equally consistent with a canary that could never fire, which is
    what a broken probe looks like from outside. Checking only the neutralised
    side would be the blind instrument this whole script exists to refuse.
    """
    #: GIT ABSENT IS NOT A REFUSAL, AND IS NOT SILENCE EITHER (counter-model
    #: review, #1182). With no git binary the route does not exist: the members
    #: that would reach it guard on `command -v git` and return early. Refusing
    #: here would make this gate unrunnable in the CI `validate` image, which
    #: ships no git - turning a containment check into a availability check. The
    #: state is REPORTED by the bound rather than folded into "verified".
    if shutil.which("git") is None:
        return []

    try:
        git_exec_config_overrides(REPO_ROOT)
    except GitDiscoveryError as exc:
        #: A DISCOVERY THAT FAILED IS NOT A CLEAN ONE. Returning the fixed
        #: overrides here would leave a configured filter live while the verdict
        #: said configured filters were neutralised.
        return [str(exc)]

    problems: list[str] = []
    workdir = Path(tempfile.mkdtemp(prefix="cpp-observe-git-"))
    try:
        repo = workdir / "repo"
        canary_script = workdir / "canary.sh"
        canary_file = workdir / "fired"
        probe_home = workdir / "home"
        setup_env = sanitised_git_env(probe_home)
        try:
            probe_home.mkdir()
            repo.mkdir()
            canary_script.write_text(_CANARY_SCRIPT, encoding="utf-8")
            canary_script.chmod(0o755)
            subprocess.run(
                ["git", "init", "-q", str(repo)], check=True, timeout=30,
                env=setup_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            (repo / "a.txt").write_text("hi\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "config", "core.fsmonitor", str(canary_script)],
                check=True, timeout=30, env=setup_env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return [
                f"could not build the git-containment probe ({exc}), so this run "
                "cannot establish that a repo-configured command is neutralised"
            ]

        def probe(env: dict[str, str]) -> tuple[bool, str]:
            """`(fired, failure)`. A non-empty failure means it did NOT COMPLETE.

            Collapsing those into one boolean made a timeout or a launch failure
            read as "did not fire", so an UNEXECUTED measurement reported
            containment (counter-model review, #1182).
            """
            canary_file.unlink(missing_ok=True)
            env = dict(env, CPP_OBSERVE_CANARY=str(canary_file))
            try:
                res = subprocess.run(
                    ["git", "-C", str(repo), "status"], env=env, timeout=30,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                return False, f"the probe invocation did not complete ({exc})"
            #: A NONZERO EXIT IS ALSO "did not complete" (counter-model review
            #: round 2). `git status` exits 0 even when the fsmonitor command
            #: fires AND fails - measured - so requiring success does not
            #: suppress the positive control; it only removes the case where git
            #: died at 128, or on a signal, before ever reaching the hook, and
            #: the absent canary read as successful neutralisation.
            if res.returncode != 0:
                return False, f"the probe invocation exited {res.returncode}"
            return canary_file.exists(), ""

        unprotected, failure = probe(sanitised_git_env(probe_home))
        if failure:
            return [f"the git-containment probe could not be established: {failure}"]
        if not unprotected:
            return [
                "the git-containment probe is BLIND: a planted core.fsmonitor did "
                "NOT fire even with the neutralisation removed, so a clean result "
                "from it would say nothing about containment"
            ]

        protected, failure = probe(_with_git_overrides(sanitised_git_env(probe_home), repo))
        if failure:
            return [
                "the NEUTRALISED half of the git-containment probe did not "
                f"complete, so its silence is not evidence: {failure}"
            ]
        if protected:
            problems.append(
                "a repo-configured core.fsmonitor EXECUTED under the sandbox "
                "environment, so this run cannot bound what a member wrote"
            )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return problems


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

    #: ENFORCEMENT, NOT A CAVEAT (issue #1182 acceptance item 2). #1150 stated
    #: the containment bound in its own verdict, which is the right place for a
    #: bound - but a statement nothing checks is decoration, and its broken
    #: version is indistinguishable from its working one. So the claim is now a
    #: PRECONDITION of certifying anything: if a planted command-executing git
    #: config either executes under the sandbox environment, or fails to execute
    #: with the neutralisation removed (a blind probe), nothing is certified.
    containment = verify_git_containment()
    if containment:
        for problem in containment:
            print(f"host-surface-observe: {problem}", file=sys.stderr)
        print(
            "host-surface-observe: REFUSED - git containment could not be "
            "established, so this run certifies no declaration: "
            + "; ".join(containment)
        )
        return 1

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
    #: THE BOUND NAMES THE ENFORCED KEYS BY DERIVING THEM, never by restating
    #: them. A hand-written list drifts from the table it describes, and the
    #: drifted version reads exactly as authoritative as the accurate one.
    #: tests/test_host_surface_observe.py pins that this line and
    #: GIT_EXEC_CONFIG_NEUTRALISED cannot disagree.
    print(containment_bound_text(), file=out)
    for o in escaping:
        print(f"    {o.name}: escapes via {o.reason}", file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
