"""Pin: a delegated lane cannot report success on a failed run (issue #798).

Every local/delegated-model lane decided a run's fate by testing `$?` against
zero, and in all six command documents that test could not observe the CLI's
exit status:

- **`| tee` masked it (exec lanes).** `$?` after a pipeline is the status of the
  LAST command - `tee` - and `pipefail` was set nowhere (grepped: zero hits
  across all three lanes). The documented `exit 124 = timeout` branch was
  therefore unreachable: a run that blew its 1800s timeout reported success.
- **A different shell captured it (auto lanes).** The invocation and the check
  sat in SEPARATE fenced `bash` blocks with prose between them, so `$?`
  reflected whatever ran last in the new shell - no relationship to the run at
  all. The comment `# After execution, check exit code` described an intent the
  code could not carry out.

A dead endpoint, a timeout, or an API error thus read as a completed task, and
`/*:auto` marched on into review, quality gates, `/flow:finish` and
`/flow:merge` on an empty diff. Found while diagnosing why `/qwen:*` had been
pointed at an offline MacBook: the endpoint was wrong long enough to matter and
nothing surfaced it, because the harness reported success throughout.

These are prompt documents, which is what makes this file the mechanism rather
than the discipline it replaces. The shapes below are exactly the ones that
broke, so a future editor cannot reintroduce a pipe, split the block, or drop
the payload check without turning one of these red.

`tests/test_delegated_run_check.py` owns the helper's own behaviour; this file
only pins that each lane REACHES it, and reaches it with the right arguments.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ROOT / ".claude" / "commands"

#: family -> (CLI binary as it appears at the head of an invocation, exit var)
LANES = {
    "qwen": ("qwen", "QWEN_EXIT"),
    "gemma": ("opencode run", "GEMMA_EXIT"),
    "codex": ("codex exec", "CODEX_EXIT"),
}

SURFACES = [(family, kind) for family in sorted(LANES) for kind in ("exec", "auto")]
IDS = [f"{family}:{kind}" for family, kind in SURFACES]

#: The helper every lane must consult. Named at its stable path so the shipped
#: allowlist rule matches (the #581 invocation discipline).
HELPER = "~/.claude/scripts/delegated-run-check.sh"


def read(family: str, kind: str) -> str:
    return (COMMANDS / family / f"{kind}.md").read_text(encoding="utf-8")


def bash_blocks(text: str) -> list[str]:
    """Every ```bash fenced block, in order.

    Deliberately NOT every fence: a plain ``` block in these documents holds a
    shell TRANSCRIPT demonstrating the bug (`$ ( timeout 1 ... | tee ...)`),
    which must stay readable without tripping the pipe checks below.
    """
    return re.findall(r"^```bash\n(.*?)^```", text, re.MULTILINE | re.DOTALL)


def invocation_blocks(text: str, binary: str) -> list[str]:
    """The bash blocks that actually launch the delegated CLI."""
    pattern = re.compile(
        r"^\s*(?:[A-Z_]+=\S+\s+)*(?:timeout\s+\d+\s+)?" + re.escape(binary) + r"\b",
        re.MULTILINE,
    )
    return [block for block in bash_blocks(text) if pattern.search(block)]


@pytest.mark.parametrize(("family", "kind"), SURFACES, ids=IDS)
def test_the_run_is_never_piped(family: str, kind: str) -> None:
    """Bug 1: `| tee` makes `$?` tee's status, so every failure reads as 0."""
    binary, _ = LANES[family]
    blocks = invocation_blocks(read(family, kind), binary)
    assert blocks, f"no {binary} invocation block found in {family}/{kind}.md"

    for block in blocks:
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "| tee" not in stripped, (
                f"{family}/{kind}.md pipes the delegated run through tee: {stripped!r}. "
                "`$?` would then be tee's status, not the CLI's - the #798 defect. "
                "Redirect with `> \"$OUT\" 2>&1` instead."
            )


@pytest.mark.parametrize(("family", "kind"), SURFACES, ids=IDS)
def test_the_run_redirects_its_output_to_a_file(family: str, kind: str) -> None:
    """The monitoring surface must survive: no pipe AND no lost stream."""
    binary, _ = LANES[family]
    for block in invocation_blocks(read(family, kind), binary):
        assert re.search(r">\s*\"?\$?\{?[A-Za-z_]", block), (
            f"{family}/{kind}.md drops the delegated run's output entirely; "
            "redirect it to a file so the JSONL can still be read."
        )


@pytest.mark.parametrize(("family", "kind"), SURFACES, ids=IDS)
def test_invocation_and_status_check_share_one_shell(family: str, kind: str) -> None:
    """Bug 2 - the sharper one.

    `$?` in a LATER fenced block is a different shell's `$?`. The capture has
    to sit in the same block as the invocation that produced it.
    """
    binary, exit_var = LANES[family]
    text = read(family, kind)
    blocks = bash_blocks(text)

    capture = f"{exit_var}=$?"
    holders = [i for i, block in enumerate(blocks) if capture in block]
    assert holders, f"{family}/{kind}.md never captures {capture}"

    launchers = {
        i for i, block in enumerate(blocks)
        if block in invocation_blocks(text, binary)
    }

    for index in holders:
        assert index in launchers, (
            f"{family}/{kind}.md captures {capture} in a bash block that does not "
            f"invoke `{binary}`. Executed as written that is a separate shell, so "
            "`$?` reflects whatever ran last there - the #798 defect. Move the "
            "capture into the invocation's own block."
        )


@pytest.mark.parametrize(("family", "kind"), SURFACES, ids=IDS)
def test_the_capture_immediately_follows_the_invocation(family: str, kind: str) -> None:
    """Same block is necessary, not sufficient: an `echo` between them resets `$?`."""
    binary, exit_var = LANES[family]
    capture = f"{exit_var}=$?"

    for block in invocation_blocks(read(family, kind), binary):
        if capture not in block:
            continue
        lines = []
        for raw in block.splitlines():
            # Trailing comments are load-bearing documentation here (the
            # `</dev/null` note), so strip them rather than requiring the
            # redirect to be the last thing on the line.
            code = re.sub(r"\s+#.*$", "", raw).strip()
            if code and not code.startswith("#"):
                lines.append(code)
        position = lines.index(capture)
        previous = lines[position - 1]
        assert previous.endswith("2>&1") or binary.split()[0] in previous, (
            f"{family}/{kind}.md puts {previous!r} between the {binary} run and "
            f"{capture}; `$?` would be that command's status instead."
        )


@pytest.mark.parametrize(("family", "kind"), SURFACES, ids=IDS)
def test_the_payload_is_checked_not_only_the_exit_code(family: str, kind: str) -> None:
    """Bug 3: the Qwen CLI reports success on a failed run.

    Verified 2026-09-07 (@qwen-code/qwen-code 0.15.10) against an unreachable
    endpoint: `EXIT=0`, `subtype: "success"`, `is_error: false`, `num_turns: 1`,
    with the only evidence of failure inside the terminal `result` string. So
    even a correct exit-code check still passes, in every lane written on the
    assumption that a CLI reports its own failures.
    """
    text = read(family, kind)
    assert HELPER in text, (
        f"{family}/{kind}.md never consults {HELPER}; its failure detection "
        "rests on `$?` alone, which #798 showed is not evidence on these lanes."
    )


@pytest.mark.parametrize("family", sorted(LANES), ids=sorted(LANES))
def test_auto_lanes_expect_tools_of_a_delegated_implementation(family: str) -> None:
    """An `auto` run delegated an IMPLEMENTATION: a tool-free run wrote no code.

    The `exec` lanes deliberately do not pass this - a one-shot question can be
    answered without touching a file - so the flag is asserted only where the
    stricter reading is correct.
    """
    text = read(family, "auto")
    for line in text.splitlines():
        if HELPER in line and "--lane" in line:
            assert "--expect-tools" in line, (
                f"{family}/auto.md calls the run checker without --expect-tools: "
                f"{line.strip()!r}. A delegated implementation that used no tools "
                "produced no diff and must not read as a success."
            )


@pytest.mark.parametrize("family", sorted(LANES), ids=sorted(LANES))
def test_auto_lanes_fail_closed_on_an_empty_diff(family: str) -> None:
    """The last line of defence, and the one the incident actually needed.

    Every failure in these lanes arrives at the same place - a tree with
    nothing in it - and prose saying "If the model made no changes, STOP and
    report" did not stop anything. The check has to be executable, and it has
    to exit.
    """
    text = read(family, "auto")

    empty_diff_blocks = [
        block for block in bash_blocks(text)
        if "FILES_CHANGED" in block and "-eq 0" in block
    ]
    assert empty_diff_blocks, (
        f"{family}/auto.md has no executable empty-diff gate; a failed "
        "delegation would advance to review and /flow:finish on nothing."
    )
    assert any("exit 1" in block for block in empty_diff_blocks), (
        f"{family}/auto.md notices an empty diff but does not stop on it."
    )


@pytest.mark.parametrize("family", sorted(LANES), ids=sorted(LANES))
def test_empty_diff_gate_counts_untracked_files(family: str) -> None:
    """`git diff --name-only` is blind to a model that only ADDED files.

    A run whose whole output is new, unstaged files would score 0 under a plain
    `git diff` and be killed as a failure - the false-positive direction of
    this gate, and the reason the count is taken from `git status --porcelain`.
    """
    text = read(family, "auto")
    for block in bash_blocks(text):
        if "FILES_CHANGED=" not in block:
            continue
        assignment = next(
            line for line in block.splitlines() if "FILES_CHANGED=" in line
        )
        assert "git status --porcelain" in assignment, (
            f"{family}/auto.md counts changes with {assignment.strip()!r}, which "
            "cannot see untracked files; a model that only added files would be "
            "reported as having changed nothing."
        )


@pytest.mark.parametrize("family", sorted(LANES), ids=sorted(LANES))
def test_the_finish_step_refuses_an_empty_diff(family: str) -> None:
    """Backstop at the boundary that ships: the Step 6 fix loop can also no-op."""
    text = read(family, "auto")
    finish = text.split("### Step 7: Finish", 1)
    assert len(finish) == 2, f"{family}/auto.md has no Step 7 Finish heading"

    step7 = finish[1].split("### Step 8", 1)[0]
    assert "git status --porcelain" in step7 and "exit 1" in step7, (
        f"{family}/auto.md Step 7 opens a PR without re-checking for an empty "
        "diff; #798's failure mode ends in exactly that PR."
    )


@pytest.mark.parametrize(("family", "kind"), SURFACES, ids=IDS)
def test_a_timeout_branch_exists_only_where_timeout_is_used(family: str, kind: str) -> None:
    """The `exit 124` branch must be reachable - or absent.

    An unreachable branch is the #798 defect one level down, so this is
    two-directional: a lane wrapped in `timeout` must name 124, and a lane that
    is not wrapped must not claim to detect it. `/codex:*` carries no `timeout`
    wrapper and therefore, correctly, no 124 branch.
    """
    text = read(family, kind)
    binary, _ = LANES[family]
    blocks = invocation_blocks(text, binary)
    wrapped = any(re.search(r"\btimeout\s+\d+\s", block) for block in blocks)

    mentions_124 = re.search(r"-eq\s+124", text) is not None
    if wrapped:
        assert mentions_124, (
            f"{family}/{kind}.md wraps the run in `timeout` but never reports "
            "exit 124; that is the branch #798 made unreachable."
        )
    else:
        assert not mentions_124, (
            f"{family}/{kind}.md has no `timeout` wrapper, so its exit-124 "
            "branch can never fire - an unreachable branch is the same defect."
        )


def test_no_lane_sets_pipefail_instead_of_fixing_the_pipe() -> None:
    """`set -o pipefail` would fix bug 1 and leave bug 2 standing.

    It is a real option the issue lists, and the wrong one here: it does
    nothing about a `$?` captured in another shell, and it silently changes the
    behaviour of every other pipeline in the block. If a future editor reaches
    for it, that is the moment to re-read this file.
    """
    for family, kind in SURFACES:
        text = read(family, kind)
        for block in bash_blocks(text):
            assert "pipefail" not in block, (
                f"{family}/{kind}.md sets pipefail; #798 is fixed by removing the "
                "pipe and co-locating the capture, not by changing pipe semantics."
            )
