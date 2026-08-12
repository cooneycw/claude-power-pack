"""Pin: register.md's worker-side token examples are what the validator ACCEPTS (#709).

``flow-wave-lexicon.sh`` (#701) refuses a malformed ``PUSHBACK`` or ``LEDGER``,
and ``flow-wave-mailbox.sh send`` runs it - so a worker that emits either shape
wrongly is refused delivery. #709's defect was that the enforcement existed and
the worker-facing file said nothing about it: the guard fired correctly at a
reader who had never been told the rule.

Documenting a shape creates the mirror-image failure - a page that teaches a
shape the tool REJECTS is worse than silence, because the reader now has a
confident wrong answer. So this file does not assert that the words appear. It
EXTRACTS the examples out of ``register.md`` and runs them through the real
validator, which makes the documentation executable rather than plausible.

THE LOAD-BEARING HALF IS THE MUTATIONS. A suite that only feeds the parser the
documented (well-formed) examples would pass identically against a validator
that accepted everything - the exact defect #701's own kill condition names. So
each example is also MUTATED into the shape the doc says is refused (a bare
``PUSHBACK``, a ``LEDGER`` missing ``residual:``) and the refusal is asserted,
with the reason naming what is missing. A doc example that stops validating and
a validator that stops refusing both turn this file red.

Deliberately narrow, so a rewrite of the prose cannot fail it: the examples are
addressed by HTML marker, never by line number, and no phrasing outside the
fenced blocks is asserted.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTER_MD = ROOT / ".claude" / "commands" / "flow" / "register.md"
LEXICON = ROOT / "scripts" / "flow-wave-lexicon.sh"

# Drives a real `bash` subprocess; the CI validate container may not ship one,
# so skip there (CPP core directive, same shape as the other flow suites).
requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requires bash on PATH"
)


def _example(name: str) -> str:
    """Return the fenced example tagged ``<!-- lexicon-example: NAME -->``.

    Marker-addressed on purpose: a line-number or heading-text anchor would make
    an innocent rewording of the surrounding prose fail this file, which is how
    doc tests earn their bad reputation.
    """
    text = REGISTER_MD.read_text(encoding="utf-8")
    match = re.search(
        rf"<!-- lexicon-example: {re.escape(name)} -->\s*\n+```[a-z]*\n(.*?)\n```",
        text,
        re.S,
    )
    assert match is not None, (
        f"register.md carries no '<!-- lexicon-example: {name} -->' marker followed "
        f"by a fenced block. Issue #709 documented the worker-emitted {name.upper()} "
        f"shape there; if the example moved, move the marker with it - the marker is "
        f"how this test finds the text the validator must accept."
    )
    return match.group(1)


def _validate(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    body_file = tmp_path / "body.md"
    body_file.write_text(body + "\n", encoding="utf-8")
    return subprocess.run(
        ["bash", str(LEXICON), "validate", "--body-file", str(body_file)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _verdict(proc: subprocess.CompletedProcess[str]) -> str:
    for line in proc.stdout.splitlines():
        if line.startswith("FLOW_LEXICON: "):
            return line.split(": ", 1)[1].strip()
    return ""


def _transitions(proc: subprocess.CompletedProcess[str]) -> list[str]:
    prefix = "FLOW_LEXICON_TRANSITION="
    return [
        line[len(prefix) :] for line in proc.stdout.splitlines() if line.startswith(prefix)
    ]


class TestTheDocumentedExamplesValidate:
    """What register.md teaches is what the mailbox will actually deliver."""

    @requires_bash
    def test_pushback_example_is_accepted(self, tmp_path: Path) -> None:
        proc = _validate(tmp_path, _example("pushback"))
        assert _verdict(proc) == "ok", (
            "register.md's documented PUSHBACK example does not validate - the page "
            f"teaches a shape `send` would refuse (exit 6).\n{proc.stdout}\n{proc.stderr}"
        )
        assert any(t.startswith("PUSHBACK:") for t in _transitions(proc)), (
            "the example parsed, but as no PUSHBACK transition - a token that reads "
            f"as prose teaches nothing. Transitions seen: {_transitions(proc)}"
        )

    @requires_bash
    def test_ledger_example_is_accepted(self, tmp_path: Path) -> None:
        proc = _validate(tmp_path, _example("ledger"))
        assert _verdict(proc) == "ok", (
            "register.md's documented LEDGER example does not validate - the page "
            f"teaches a shape `send` would refuse (exit 6).\n{proc.stdout}\n{proc.stderr}"
        )
        assert "LEDGER: delivered/in-scope/residual" in _transitions(proc), (
            "the LEDGER example parsed without all three sections being recognized. "
            f"Transitions seen: {_transitions(proc)}"
        )


class TestTheRefusalStillFires:
    """The half that makes the two tests above mean something.

    Each mutation is the failure the doc explicitly warns about. If the
    validator stops refusing these, the documented requirements are decoration
    and the tests above would keep passing against a validator that accepts
    everything - so these run against the SAME examples, minimally broken.
    """

    @requires_bash
    def test_pushback_without_its_argument_is_refused(self, tmp_path: Path) -> None:
        # Strip everything but the token itself: the doc says a bare PUSHBACK is
        # refused "so a refutation cannot be skimmed past as agreement".
        bare = _example("pushback").splitlines()[0].split()[0]
        assert bare == "PUSHBACK", f"example no longer opens with the token: {bare!r}"
        proc = _validate(tmp_path, bare)
        assert proc.returncode == 1, (
            "a bare PUSHBACK was NOT refused. register.md tells workers the argument "
            f"is mandatory; if that stops being true the page is wrong.\n{proc.stdout}"
        )
        assert _verdict(proc) == "invalid"
        assert "argument" in proc.stderr.lower(), (
            f"the refusal does not say what is missing: {proc.stderr!r}"
        )

    @requires_bash
    def test_ledger_missing_a_section_is_refused_by_name(self, tmp_path: Path) -> None:
        lines = _example("ledger").splitlines()
        mutated = [ln for ln in lines if not ln.lower().lstrip().startswith("residual:")]
        assert len(mutated) < len(lines), (
            "the documented LEDGER example has no 'residual:' line to remove - it can "
            "no longer demonstrate the all-three-sections requirement it is there for."
        )
        proc = _validate(tmp_path, "\n".join(mutated))
        assert proc.returncode == 1, (
            "a LEDGER missing 'residual:' was NOT refused. register.md tells workers "
            f"all three sections are required.\n{proc.stdout}"
        )
        assert _verdict(proc) == "invalid"
        assert "residual" in proc.stderr.lower(), (
            f"the refusal does not name the missing section: {proc.stderr!r}"
        )


class TestTheWorkerIsPointedAtTheCheck:
    """#709's third ask: a worker can verify a report before the mailbox sees it."""

    def test_register_md_names_the_pre_send_validate_invocation(self) -> None:
        text = REGISTER_MD.read_text(encoding="utf-8")
        assert "flow-wave-lexicon.sh validate --body-file" in text, (
            "register.md no longer shows the pre-send check. Without it a worker's "
            "only way to discover a malformed token is a refused send (issue #709)."
        )
