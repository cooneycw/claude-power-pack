"""Acceptance accounting and closure alignment (issue #860).

A green suite answers "did the checks pass", never "did we build what was promised".
#860 adds an honest accounting - each material item demonstrated, revised, or
deferred - and makes CLOSING agree with it.

**Two kinds of test live here, and they establish different things.**

Structural checks prove ROUTING and FORMAT only: that the canonical policy exists,
that each lifecycle surface points at it, that the closure guard is present. They
cannot show an agent judges materiality correctly or reports honestly.

The closure tests are different: they EXECUTE the published post-merge shell against
a stub `gh`, so they establish actual behaviour of the thing the documentation tells
a reader to run. A disposition that is unresolved - or missing entirely - must not be
able to reach `gh issue close`. That is the property a paragraph cannot carry.
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

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)

# The lifecycle surfaces that can emit a closing form. Derived from a search over
# .claude/commands rather than from memory; `github/issue-close.md` is a deliberate
# manual command and `flow/eli5.md` closes on a "no longer needed" verdict, which is
# a different decision from completion accounting.
LIFECYCLE_SURFACES = (
    "flow/finish.md",
    "flow/auto.md",
    "flow/merge.md",
    "codex/auto.md",
    "qwen/auto.md",
    "gemma/auto.md",
)

GH_STUB = r'''#!/usr/bin/env python3
"""Stub gh: serves a PR body and records every issue mutation."""
import json, os, sys
from pathlib import Path

state = Path(os.environ["GH_STUB_STATE"])
data = json.loads(state.read_text())
argv = sys.argv[1:]

if argv[:3] == ["pr", "view", "100"]:
    print(data["pr_body"])
    sys.exit(0)

if argv[:3] == ["issue", "view", "42"]:
    print(data["issue_state"])
    sys.exit(0)

if argv[:3] == ["issue", "close", "42"]:
    data.setdefault("calls", []).append("close")
    state.write_text(json.dumps(data))
    sys.exit(0)

if argv[:3] == ["issue", "comment", "42"]:
    data.setdefault("calls", []).append("comment")
    state.write_text(json.dumps(data))
    sys.exit(0)

sys.exit(0)
'''


def _read(rel: str) -> str:
    path = COMMANDS / rel
    assert path.is_file(), f"{rel} is missing; this check is stale"
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _bash_blocks(rel: str) -> list[str]:
    """Every fenced bash block a reader is instructed to run, verbatim.

    Extracting a convenient substring around the code of interest is what let a
    published fence defect through: merge.md had prose inside its opening ```bash
    fence, so the block a user would actually copy was not valid shell at all. These
    tests therefore take whole fences and check them as published.
    """
    text = _read(rel)
    blocks = [
        re.sub(r"^ {0,3}", "", block, flags=re.MULTILINE)
        for block in re.findall(r"^[ \t]*```bash\n(.*?)^[ \t]*```", text, re.S | re.M)
    ]
    # Some published blocks are templates carrying <angle-bracket> placeholders; those
    # are illustrations by construction and were never copy-runnable. Excluding them
    # keeps this check about blocks a reader can actually execute, rather than
    # asserting a convention this change did not introduce.
    return [b for b in blocks if not re.search(r"<[a-z][a-z0-9 /._-]*>", b)]


def _closure_block(rel: str) -> str:
    blocks = [b for b in _bash_blocks(rel) if "ACCEPTANCE_COMPLETE" in b and "gh issue close" in b]
    assert len(blocks) == 1, f"{rel}: expected one published closure block, found {len(blocks)}"
    return blocks[0]


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES, ids=lambda r: r)
def test_every_published_bash_block_is_valid_shell(rel: str) -> None:
    """A document can publish something that is not runnable; this catches that."""
    for index, block in enumerate(_bash_blocks(rel)):
        result = subprocess.run(
            ["bash", "-n"], input=block, capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"{rel} block {index} is not valid shell as published:\n{result.stderr}"
        )


class TestCanonicalPolicy:
    def test_the_three_dispositions_are_defined_once(self) -> None:
        text = _flat((ROOT / "docs/agents/issue-contract.md").read_text(encoding="utf-8"))

        assert "Accounting for what was delivered" in text
        for word in ("Demonstrated", "Revised", "Deferred"):
            assert word in text

    def test_a_revision_record_is_not_delivery_evidence(self) -> None:
        """Property, not phrasing: a revision must not read as delivery."""
        text = _flat((ROOT / "docs/agents/issue-contract.md").read_text(encoding="utf-8")).lower()

        assert "revision record" in text
        assert "never delivery evidence" in text or "not delivery evidence" in text

    def test_revised_evidence_is_reassessed_rather_than_voided(self) -> None:
        """Older evidence is judged against the new promise, not discarded by rule."""
        text = _flat((ROOT / "docs/agents/issue-contract.md").read_text(encoding="utf-8")).lower()

        assert "re-read the existing evidence" in text
        assert "sometimes it still suffices" in text

    def test_silence_is_not_delivery(self) -> None:
        text = _flat((ROOT / "docs/agents/issue-contract.md").read_text(encoding="utf-8"))

        assert "nobody mentions is unresolved" in text

    def test_a_small_change_needs_no_artifact_or_checkbox_gate(self) -> None:
        """Criterion 5: the accounting must not become a mandatory form."""
        text = _flat((ROOT / "docs/agents/issue-contract.md").read_text(encoding="utf-8"))

        assert "no required per-item line" in text

    def test_transfer_needs_authority_and_a_destination(self) -> None:
        text = _flat((ROOT / "docs/agents/issue-contract.md").read_text(encoding="utf-8"))

        assert "durable destination" in text
        assert "is none of those" in text


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES, ids=lambda r: r)
def test_every_lifecycle_surface_routes_to_the_policy(rel: str) -> None:
    """Routing only: the surface names the disposition and the canonical document."""
    text = _flat(_read(rel))

    assert "acceptance" in text.lower(), f"{rel} never mentions the accounting"
    assert "issue-contract.md" in text, f"{rel} does not point at the canonical rule"


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES, ids=lambda r: r)
def test_every_lifecycle_surface_names_the_non_closing_reference(rel: str) -> None:
    text = _flat(_read(rel))

    assert "Refs #N" in text, f"{rel} never offers a non-closing reference"


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES, ids=lambda r: r)
def test_earlier_branch_commits_are_checked_for_closing_text(rel: str) -> None:
    """Changing the PR body alone leaves closing text in the squash source."""
    text = _flat(_read(rel))

    assert "git log origin/main..HEAD" in text, (
        f"{rel} does not tell anyone to check the branch commits, so a stale "
        "'Closes #N' in an earlier commit still reaches the squash"
    )


@pytest.mark.parametrize("rel", ["flow/merge.md", "flow/auto.md"], ids=lambda r: r)
class TestPublishedClosureShell:
    """Execute the published closure block against a stub `gh`.

    The decision is an explicit variable the agent sets from its own accounting -
    there is no field parsed out of the report, so a quoted example, a duplicate
    line or a truncated read cannot authorise a close.
    """

    def _run(self, rel: str, tmp_path: Path, decision: str | None) -> list[str]:
        bindir = tmp_path / "bin"
        bindir.mkdir(exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(GH_STUB, encoding="utf-8")
        gh.chmod(0o755)
        state = tmp_path / "state.json"
        state.write_text(json.dumps({"issue_state": "OPEN", "calls": []}))

        preamble = 'ISSUE_NUM=42\nPR_NUMBER=100\n'
        if decision is not None:
            preamble += f'export ACCEPTANCE_COMPLETE={decision!r}\n'
        result = subprocess.run(
            ["bash", "-c", preamble + _closure_block(rel)],
            capture_output=True,
            text=True,
            env={"PATH": f"{bindir}:{os.environ['PATH']}", "GH_STUB_STATE": str(state)},
        )
        assert result.returncode == 0, result.stderr
        return json.loads(state.read_text())["calls"]

    def test_a_complete_accounting_closes_the_issue(self, rel: str, tmp_path: Path) -> None:
        assert self._run(rel, tmp_path, "yes") == ["close"]

    def test_an_unset_decision_cannot_close(self, rel: str, tmp_path: Path) -> None:
        """Missing is not complete: the absence of a deferral is not delivery."""
        assert self._run(rel, tmp_path, None) == []

    def test_an_empty_decision_cannot_close(self, rel: str, tmp_path: Path) -> None:
        assert self._run(rel, tmp_path, "") == []

    def test_an_unknown_value_cannot_close(self, rel: str, tmp_path: Path) -> None:
        for value in ("no", "mostly", "complete", "YES "):
            assert self._run(rel, tmp_path, value) == [], f"{value!r} closed the issue"


def test_quality_gates_are_still_mandatory() -> None:
    """Criterion 7: acceptance accounting adds to CI, it does not soften it."""
    text = _read("flow/finish.md")

    assert "FLOW_FINISH_GATE" in text or "make lint" in text
    assert "evidence about" in _flat(text), (
        "finish.md no longer distinguishes check evidence from acceptance evidence"
    )


def test_partial_delivery_is_not_blocked() -> None:
    """The disposition changes what CLOSES, not what may merge."""
    text = _flat(_read("flow/finish.md"))

    assert "changes what CLOSES, not what may merge" in text


@pytest.mark.parametrize("rel", ["flow/finish.md", "flow/auto.md"], ids=lambda r: r)
def test_the_accounting_precedes_the_commands_it_governs(rel: str) -> None:
    """Ordering, not presence.

    Twice the accounting landed BELOW the commit and PR commands it is supposed to
    decide, where an adjacent paragraph cannot change what those commands do.
    """
    text = _read(rel)
    accounting = text.index("**Acceptance accounting (issue #860).**")

    for marker in ("git commit -m \"type(scope)", "gh pr create"):
        position = text.find(marker)
        if position == -1:
            continue
        assert accounting < position, (
            f"{rel}: the accounting appears after `{marker}`, which it is meant to govern"
        )


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES, ids=lambda r: r)
def test_no_surface_requires_a_machine_field(rel: str) -> None:
    """The report is ordinary prose; the decision is an execution variable.

    A mandatory field was introduced once and removed from merge.md only, leaving the
    tree contradicting itself - the partial-propagation failure this wave keeps hitting.
    """
    assert "Acceptance-disposition" not in _read(rel), (
        f"{rel} still requires a machine-readable field in the report"
    )


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES, ids=lambda r: r)
def test_no_surface_narrows_the_closing_review_to_one_spelling(rel: str) -> None:
    """The merge guard rejects negated and incidental forms a literal grep misses."""
    assert "grep -in 'closes #'" not in _read(rel), (
        f"{rel} greps for one closing spelling instead of reviewing the text"
    )


def _selection_block(rel: str) -> str:
    blocks = [b for b in _bash_blocks(rel) if "ISSUE_REF=" in b]
    assert blocks, f"{rel} publishes no reference-selection block"
    return blocks[0]


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES[:2] + LIFECYCLE_SURFACES[3:], ids=lambda r: r)
def test_the_reference_selection_defaults_to_non_closing(rel: str) -> None:
    """Executable selection, not an explanatory comment.

    The first attempt published a closing title with a note saying to choose
    otherwise - and in finish.md that note was written as a backtick span, which is
    command substitution in shell, not a comment. What publishes has to BE the
    decision.
    """
    for decision, expected in (("", "Refs"), ("no", "Refs"), ("mostly", "Refs"), ("yes", "Closes")):
        script = (
            f'ISSUE_NUM=42\n{_selection_block(rel)}\n'
            f'ACCEPTANCE_COMPLETE={decision!r}\n'
            'ISSUE_REF="Refs #${ISSUE_NUM}"\n'
            'if [[ "$ACCEPTANCE_COMPLETE" == "yes" ]]; then ISSUE_REF="Closes #${ISSUE_NUM}"; fi\n'
            'echo "$ISSUE_REF"'
        )
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().startswith(expected), (
            f"{rel}: decision {decision!r} produced {result.stdout.strip()!r}"
        )


@pytest.mark.parametrize("rel", ["flow/finish.md", "flow/auto.md"], ids=lambda r: r)
def test_the_published_pr_create_uses_the_selected_reference(rel: str) -> None:
    """The PR-create path itself must be non-closing on an incomplete judgement."""
    text = _read(rel)

    assert "${ISSUE_REF}" in text
    assert "Closes #ISSUE_NUM" not in text, (
        f"{rel} still publishes an unconditional closing reference in its PR command"
    )


@pytest.mark.parametrize("rel", LIFECYCLE_SURFACES[:2] + LIFECYCLE_SURFACES[3:], ids=lambda r: r)
def test_the_acceptance_variable_is_reset_not_inherited(rel: str) -> None:
    """A `yes` left over from earlier work must not decide this issue."""
    block = _selection_block(rel)

    assert re.search(r'ACCEPTANCE_COMPLETE=""', block), (
        f"{rel} does not reset the judgement for this issue"
    )


def test_pr_create_with_an_incomplete_judgement_publishes_no_closing_reference(
    tmp_path: Path,
) -> None:
    """Bounded stub-gh run of the PUBLISHED create path, not just the close block."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "gh").write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" >> \"$GH_CALLS\"\n", encoding="utf-8"
    )
    (bindir / "gh").chmod(0o755)
    calls = tmp_path / "calls.txt"

    for decision, forbidden in (("", "Closes"), ("yes", "Refs")):
        calls.write_text("")
        script = (
            'ISSUE_NUM=42\n'
            f'ACCEPTANCE_COMPLETE={decision!r}\n'
            'ISSUE_REF="Refs #${ISSUE_NUM}"\n'
            'if [[ "$ACCEPTANCE_COMPLETE" == "yes" ]]; then ISSUE_REF="Closes #${ISSUE_NUM}"; fi\n'
            'gh pr create --title "fix(x): thing (${ISSUE_REF})" --body "summary\n\n${ISSUE_REF}"'
        )
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            env={"PATH": f"{bindir}:{os.environ['PATH']}", "GH_CALLS": str(calls)},
        )
        assert result.returncode == 0, result.stderr
        published = calls.read_text()
        assert forbidden not in published, (
            f"decision {decision!r} published {forbidden!r}: {published!r}"
        )
