"""Pin: the closing lifecycle surfaces route a supplemental finding to the nit store (issue #865).

The nit stores exist (kyle #1004, claude-power-pack #864, skillc #20; the map now
lives once, in scripts/nit-store-resolve.sh - #1272/#1273),
but before #865 no command document told a worker to use one. A finding noticed
while closing an issue had nowhere to go: too small to widen the change for, too
real to drop, and by the time the PR merged it had scrolled out of context. It was
dropped silently, which is the one outcome that leaves no trace to audit.

**Why these two surfaces.** `flow/finish.md` is the closing step of every
non-delegated run, and `codex/code_review.md` is where a cross-model review sorts
findings into agree/disagree/defer - `defer` being a supplemental finding by
definition, named and then discarded. Both are reached three ways: directly from
`~/.claude/commands` (a symlink into this repo), through kyle's container mount
(`DOCKER_TOOL_MOUNTS`, which delivers `commands` but no CLAUDE.md of any kind), and
- for `flow/finish.md` only - through the generated `codex/skills/flow-finish`
bundle. That last asymmetry is deliberate and load-bearing for the mirror test
below: `make codex-skills` does not mirror the `codex` namespace, so
`codex/code_review.md` has no generated copy to check.

**These are prompt documents, so the document is the enforceable layer.** No code
path reads them; a test can only establish that the instruction is present and
reachable. It cannot establish that an agent obeys it. `test_probes_are_not_vacuous`
is what keeps the first claim honest - it strips the section and requires every
probe to fail, so a rename or a move cannot leave this file passing on prose that
no longer says anything.

**Two kinds of test live here, and they establish different things.** The
structural probes prove the instruction is PRESENT and reachable in each surface
and in the generated bundle. They cannot prove the shell it publishes works - and
that gap was not hypothetical: the first version of this step resolved the nit
store with `basename "$(git rev-parse --show-toplevel)"`, which never matches,
because `/flow:finish` always runs from a per-issue worktree (`.../repo-issue-865`).
All three named repositories fell through to the full-text search on every real
invocation, and 30 green structural tests saw nothing. The executing tests below
run the published block from a path with that suffix, which is the only path it
ever has.

Verified non-vacuous: stashed against the pre-change tree, all 30 structural tests
here fail.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"

#: Closing surfaces that must carry the routing step. `flow/auto.md` inlines
#: its own Finish stage rather than delegating to `finish.md` and had no
#: routing step at all until issue #1030 - the same gap #865 closed for
#: `finish.md` and `code_review.md`.
SURFACES = (
    COMMANDS / "flow" / "finish.md",
    COMMANDS / "flow" / "auto.md",
    COMMANDS / "codex" / "code_review.md",
)

#: The generated bundle a codex-lane session reads instead of the command file,
#: for each surface that has one. Only `flow` is mirrored (see the module
#: docstring on why `codex/code_review.md` is not, so `code_review.md` is
#: absent from this mapping on purpose - `test_generated_codex_bundle_carries_
#: the_step` is parametrized over this dict's keys, not over SURFACES).
MIRRORS = {
    COMMANDS / "flow" / "finish.md": ROOT / "codex" / "skills" / "flow-finish" / "reference.md",
    COMMANDS / "flow" / "auto.md": ROOT / "codex" / "skills" / "flow-auto" / "reference.md",
}

#: Each probe is (name, pattern). Every one must match every surface, and every
#: one must FAIL on a document with the section removed - see the control below.
PROBES = (
    # #1272/#1273: the map is no longer copied into each surface. Each one calls
    # the one resolver and acts on its three verdicts - ok, none, unknown.
    ("calls the shared resolver", re.compile(r"~/\.claude/scripts/nit-store-resolve\.sh")),
    ("posts only on ok", re.compile(r"`ok` - post to the number")),
    (
        "posts into the repository it verified",
        re.compile(r"gh issue comment <NIT_STORE> --repo <NIT_STORE_REPO>"),
    ),
    ("unknown is not none", re.compile(r"`unknown` is not `none`")),
    (
        "falls back to a normal issue",
        re.compile(r"no nit store, file the finding as a normal issue"),
    ),
    ("one finding per comment", re.compile(r"One finding per comment")),
    (
        "records file and line, and the issue or PR",
        re.compile(r"file and line \(or the command\).+which issue or PR", re.S),
    ),
    (
        "read later without your context",
        re.compile(r"read later without your context"),
    ),
    ("inbox, not a backlog", re.compile(r"inbox, not a backlog")),
    ("a comment is a disposition", re.compile(r"disposition, not a fix")),
    (
        "a live defect still gets its own issue",
        re.compile(r"correctness, security, or data-loss.+own issue", re.S),
    ),
    (
        "names what was stored in the closing report",
        re.compile(r"with the comment link", re.S),
    ),
    (
        "nothing to store is an ordinary outcome",
        re.compile(r"(ordinary outcome|stores nothing)"),
    ),
)

#: The GENERATED MIRROR's own probe set, overriding exactly one entry (issue
#: #1408 bullet 4). The source surface legitimately keeps the convenience-
#: install absolute path `~/.claude/scripts/nit-store-resolve.sh` literally -
#: that is what a human or Claude session reads, where `~/.claude/scripts`
#: resolves. The generated bundle is correctly rewritten to the bundled
#: relative path `scripts/nit-store-resolve.sh` (the exact bug #1408 bullet 4
#: fixed: an unremapped absolute path in a Codex-only install hits exit 127,
#: since there is no `~/.claude/scripts/` there) - so the MIRROR satisfies the
#: same INTENT ("calls the shared resolver") through different literal text,
#: and needs a probe that accepts either form.
MIRROR_PROBES = tuple(
    (
        ("calls the shared resolver", re.compile(r"(?:~/\.claude/scripts/|scripts/)nit-store-resolve\.sh"))
        if name == "calls the shared resolver"
        else (name, pattern)
    )
    for name, pattern in PROBES
)


def _section(text: str) -> str:
    """The nit-store step only, so a probe cannot match unrelated prose elsewhere."""
    match = re.search(
        r"^###[^\n]*Nit Store[^\n]*$(.*?)(?=^### |\Z)", text, re.M | re.S
    )
    assert match, "no '### ... Nit Store' section found"
    return match.group(0)


@pytest.mark.parametrize("surface", SURFACES, ids=lambda p: p.name)
@pytest.mark.parametrize("name,pattern", PROBES, ids=lambda v: v if isinstance(v, str) else "")
def test_surface_routes_supplemental_findings(surface: Path, name: str, pattern: re.Pattern) -> None:
    assert surface.is_file(), f"{surface} is missing"
    assert pattern.search(_section(surface.read_text())), (
        f"{surface.relative_to(ROOT)} no longer {name}"
    )


def test_the_step_is_a_closing_step_in_finish() -> None:
    """Placed after the PR exists, so the comment can name the PR it came from."""
    text = (COMMANDS / "flow" / "finish.md").read_text()
    create_pr = text.index("### Step 6: Create PR")
    nit = text.index("### Step 6b: Route Supplemental Findings to the Nit Store")
    output = text.index("### Step 7: Output")
    assert create_pr < nit < output


def test_the_step_is_a_closing_step_in_auto() -> None:
    """Same placement rule as finish.md: after the PR exists, before Merge.

    `/flow:auto` inlines its own Finish stage rather than delegating to
    `finish.md` (issue #1030) - the current `flow/auto.md`, with no routing
    step at all between PR creation and Step 7, is itself the pre-fix red
    case for this ordering: there is no "Step 6b" heading to find until this
    fix adds one.
    """
    text = (COMMANDS / "flow" / "auto.md").read_text()
    create_pr = text.index('5. **Create PR** - if no PR exists:')
    nit = text.index("### Step 6b: Route Supplemental Findings to the Nit Store")
    merge = text.index("### Step 7: Merge - Squash-Merge and Clean Up")
    assert create_pr < nit < merge


def test_finish_output_reports_what_was_stored() -> None:
    """A finding recorded but not reported is indistinguishable from one dropped."""
    text = (COMMANDS / "flow" / "finish.md").read_text()
    output = text[text.index("### Step 7: Output") :]
    assert "Supplemental findings:" in output
    assert "#issuecomment-" in output, "the example must show a comment link"


@pytest.mark.parametrize("surface,mirror", MIRRORS.items(), ids=lambda p: p.name)
def test_generated_codex_bundle_carries_the_step(surface: Path, mirror: Path) -> None:
    """A codex-lane session reads the bundle, not the command file.

    Guards the drift the issue's own note warns about: `codex-skill-sync.py
    --write` must have been run after editing the surface, or this lane
    silently keeps the old text. Parametrized over MIRRORS rather than a
    single path (issue #1030): `flow/auto.md` gained this section and has its
    own generated bundle at `codex/skills/flow-auto/`, alongside the existing
    `flow/finish.md` -> `codex/skills/flow-finish/` mirror.
    """
    assert mirror.is_file(), f"{mirror} is missing"
    mirrored = _section(mirror.read_text())
    for name, pattern in MIRROR_PROBES:
        assert pattern.search(mirrored), (
            f"{mirror.relative_to(ROOT)} no longer {name} - "
            "run `python3 scripts/codex-skill-sync.py --write`"
        )


def test_probes_are_not_vacuous() -> None:
    """Positive control: with the section removed, every probe must fail.

    Without this, renaming the heading or moving the block elsewhere could leave
    the parametrized tests matching incidental prose - a green suite over an
    instruction that is no longer there.
    """
    for surface in SURFACES:
        text = surface.read_text()
        stripped = re.sub(
            r"^###[^\n]*Nit Store[^\n]*$.*?(?=^### |\Z)", "", text, flags=re.M | re.S
        )
        assert stripped != text, f"control removed nothing from {surface.name}"
        survivors = [name for name, pattern in PROBES if pattern.search(stripped)]
        assert not survivors, (
            f"{surface.name}: probes match outside the nit-store section, so they "
            f"prove nothing about it: {survivors}"
        )


def test_mirror_probes_are_not_vacuous() -> None:
    """The same positive control, for `MIRROR_PROBES` against the mirrors."""
    for mirror in MIRRORS.values():
        text = mirror.read_text()
        stripped = re.sub(
            r"^###[^\n]*Nit Store[^\n]*$.*?(?=^### |\Z)", "", text, flags=re.M | re.S
        )
        assert stripped != text, f"control removed nothing from {mirror.name}"
        survivors = [name for name, pattern in MIRROR_PROBES if pattern.search(stripped)]
        assert not survivors, (
            f"{mirror.name}: probes match outside the nit-store section, so they "
            f"prove nothing about it: {survivors}"
        )


# --------------------------------------------------------------------------
# Executing tests: run the published resolver, do not merely read it.
# --------------------------------------------------------------------------

#: These run the published call for real, so they need the binaries it calls (#577).
requires_shell = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="requires bash and git on PATH",
)

RESOLVER = ROOT / "scripts" / "nit-store-resolve.sh"

GH_STUB = r"""#!/usr/bin/env python3
# Stub gh: records every call, answers from a JSON fixture.
import json, os, sys
from pathlib import Path

state = Path(os.environ["GH_STUB_STATE"])
data = json.loads(state.read_text())
argv = sys.argv[1:]
data.setdefault("calls", []).append(argv)
state.write_text(json.dumps(data))

# The resolver must always name the repository it is asking about.
if argv[:2] != ["repo", "view"] and "--repo" not in argv:
    sys.exit(1)
if argv[:2] == ["repo", "view"]:
    out = data.get("repo_view", "")
    if not out:
        sys.exit(1)
    print(out)
elif argv[:2] == ["issue", "view"]:
    issue = data.get("issues", {}).get(argv[2])
    if issue is None:
        sys.exit(1)
    print(issue["state"] + "\t" + issue["title"])
elif argv[:2] == ["issue", "list"]:
    jq = argv[argv.index("--jq") + 1] if "--jq" in argv else ""
    rows = [(n, i) for n, i in sorted(data.get("issues", {}).items()) if i["state"] == "OPEN"]
    if "TOTAL" in jq:
        print(f"TOTAL {len(rows)}")
    for n, issue in rows:
        if issue["title"] == "Nit Store":
            print(n)
else:
    sys.exit(1)
"""


def _resolver_block(surface: Path) -> str:
    """The first bash block of the nit-store section - the published call."""
    section = _section(surface.read_text())
    match = re.search(r"```bash\n(.*?)```", section, re.S)
    assert match, f"no bash block in {surface.name}'s nit-store section"
    return match.group(1)


def _run_resolver(
    tmp_path: Path,
    surface: Path,
    *,
    origin: str | None,
    issues: dict | None = None,
    repo_view: str = "",
    dirname: str = "claude-power-pack-issue-865",
) -> tuple[int, str, list[list[str]]]:
    """Execute the published block from a per-issue worktree-shaped path, with
    HOME's ~/.claude/scripts holding the real resolver - as an install would."""
    workdir = tmp_path / dirname
    workdir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    if origin is not None:
        subprocess.run(["git", "remote", "add", "origin", origin], cwd=workdir, check=True)

    home = tmp_path / "home"
    (home / ".claude" / "scripts").mkdir(parents=True)
    (home / ".claude" / "scripts" / "nit-store-resolve.sh").symlink_to(RESOLVER)

    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)

    state = tmp_path / "state.json"
    state.write_text(json.dumps({"repo_view": repo_view, "issues": issues or {}}))

    env = {**os.environ, "HOME": str(home), "PATH": f"{bindir}:{os.environ['PATH']}",
           "GH_STUB_STATE": str(state)}
    proc = subprocess.run(["bash", "-c", _resolver_block(surface)], cwd=workdir, env=env,
                          capture_output=True, text=True)
    calls = json.loads(state.read_text()).get("calls", [])
    return proc.returncode, proc.stdout + proc.stderr, calls


OPEN_STORE = {"state": "OPEN", "title": "Nit Store"}


@requires_shell
@pytest.mark.parametrize("surface", SURFACES, ids=lambda p: p.name)
def test_resolver_matches_from_a_per_issue_worktree(tmp_path: Path, surface: Path) -> None:
    """The real case: the directory is `<repo>-issue-NNN`, never `<repo>`.

    The regression #865 found - keying on the directory basename fell through on
    every invocation - must stay dead now the map lives in the resolver.
    """
    code, output, calls = _run_resolver(
        tmp_path, surface, origin="https://github.com/cooneycw/claude-power-pack.git",
        issues={"864": OPEN_STORE},
    )
    assert code == 0 and "NIT_STORE=864" in output, output
    assert not [c for c in calls if c[:2] == ["issue", "list"]], (
        f"fell through to the search despite a known remote: {calls}"
    )


@requires_shell
@pytest.mark.parametrize("surface", SURFACES, ids=lambda p: p.name)
def test_resolver_handles_an_ssh_remote(tmp_path: Path, surface: Path) -> None:
    code, output, _ = _run_resolver(
        tmp_path, surface, origin="git@github.com:cooneycw/kyle.git", issues={"1004": OPEN_STORE}
    )
    assert code == 0 and "NIT_STORE=1004" in output, output


@requires_shell
@pytest.mark.parametrize("surface", SURFACES, ids=lambda p: p.name)
def test_resolver_refuses_to_answer_without_a_repository(tmp_path: Path, surface: Path) -> None:
    """No remote and no `gh repo view`: it must say unknown, never a number."""
    code, output, calls = _run_resolver(tmp_path, surface, origin=None)
    assert code == 3 and "NIT_STORE_STATUS: unknown" in output, output
    assert not [c for c in calls if c[:2] == ["issue", "comment"]], calls


@requires_shell
@pytest.mark.parametrize("surface", SURFACES, ids=lambda p: p.name)
def test_a_closed_mapped_store_is_never_answered(tmp_path: Path, surface: Path) -> None:
    """The #227 shape (#1273): the map pointed at a CLOSED issue and nothing checked."""
    code, output, _ = _run_resolver(
        tmp_path, surface, origin="https://github.com/cooneycw/claude-power-pack.git",
        issues={"864": {"state": "CLOSED", "title": "Nit Store"}},
    )
    assert code == 1 and "NIT_STORE=864" not in output and "normal issue" in output, output


@requires_shell
@pytest.mark.parametrize("surface", SURFACES, ids=lambda p: p.name)
def test_resolver_searches_by_exact_title_for_an_unknown_repo(
    tmp_path: Path, surface: Path
) -> None:
    code, output, calls = _run_resolver(
        tmp_path, surface, origin="https://github.com/cooneycw/some-other-repo.git",
        issues={"4242": OPEN_STORE}, dirname="some-other-repo-issue-7",
    )
    assert code == 0 and "NIT_STORE=4242" in output, output
    assert [c for c in calls if c[:2] == ["issue", "list"]], calls
