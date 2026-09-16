"""The three delegated drivers carry ONE lifecycle, rendered (issue #1011).

`/codex:auto`, `/qwen:auto` and `/gemma:auto` described the same eight-step
lifecycle three times - 367-454 non-blank lines shared per pair. That is not an
aesthetic complaint, and this file exists because of what it cost. Issue #774
found that all three printed a Step 2 plan report which "reads exactly like a
checkpoint and was not one": a grep for approval language between the Step 2 and
Step 3 headings "returned nothing in any of the three". One defect, three
documents, discovered on a six-worker wave where three workers described a halt
that did not exist. The test written to hold the three together was itself
deduplicated - `tests/test_delegated_driver_gates.py` imports its vocabulary from
the ELI5 pin with the comment "two copies of this guard would drift, and the
drift would be silent" - while the documents it guards were not.

By the time this landed the drift was already real rather than theoretical:
codex's Steps 6-8 carried ~60 lines qwen's and gemma's never received.

So the lifecycle lives once, in templates/delegated-driver-core.md, and is
rendered into each driver between `delegated-core` markers. What these tests pin:

  * the checked-in driver files match what the template renders - this IS the
    drift gate, and it is the assertion `make delegated-core-check` and the CI
    step both run;
  * rendering is idempotent, so a `--write` on a clean tree is a no-op and the
    gate cannot be satisfied by a check that simply rewrites what it reads;
  * the committed BAD/GOOD pair discriminates (ADR 0008), executed here as well
    as by the negative-control harness - a gate whose green is read by `make
    verify` and by CI is exactly the bound's "lets work through" case;
  * per-model text survives the move - the point is one lifecycle, not one
    driver, and a render that flattened the Ollama rows into the npm one would
    pass a bytes comparison against itself while destroying the documents;
  * the failure modes of the source itself - an unknown slot, a mis-cased
    placeholder, an orphaned value - are refused rather than rendered.

Hermetic and git-free: tmp_path trees plus checked-in fixtures, so this gives
the same verdict in CI's git-less validate container as it does locally.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "delegated-core-vendor.py"
_spec = spec_from_file_location("delegated_core_vendor", _script_path)
dcv = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(dcv)  # type: ignore[union-attr]
sys.modules["delegated_core_vendor"] = dcv

CASES = ROOT / "controls" / "delegated-core-vendor" / "cases"


# ---------------------------------------------------------------------------
# Real-repo pins - this is the drift gate
# ---------------------------------------------------------------------------


def test_real_repo_drivers_match_the_canonical_core():
    assert dcv.main(["check", "--root", str(ROOT)]) == 0


def test_rendering_the_real_repo_is_idempotent(tmp_path):
    """A --write on a clean tree changes nothing.

    Without this, `check` and `--write` could disagree and nobody would notice:
    the gate would be green on a tree that `--write` would immediately rewrite,
    which is a gate reporting on a document that is not the one that ships.
    """
    work = tmp_path / "repo"
    for rel in ["templates", ".claude"]:
        shutil.copytree(ROOT / rel, work / rel)
    before = {
        d: (work / f".claude/commands/{d}/auto.md").read_text(encoding="utf-8")
        for d in dcv.DRIVERS
    }
    assert dcv.main(["--write", "--root", str(work)]) == 0
    for d in dcv.DRIVERS:
        assert (work / f".claude/commands/{d}/auto.md").read_text(encoding="utf-8") == before[d]


@pytest.mark.parametrize("driver", dcv.DRIVERS)
def test_every_driver_carries_both_marker_pairs(driver):
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text(encoding="utf-8")
    for region in dcv.REGIONS:
        assert dcv.region_bounds(text, region, dcv.CORE_REL) is not None, (
            f"{driver}: delegated-core:{region} marker pair is missing or unpaired"
        )


# ---------------------------------------------------------------------------
# The committed negative control (ADR 0008), executed by pytest too
# ---------------------------------------------------------------------------


def test_committed_good_case_is_clean(capsys):
    assert dcv.main(["check", "--root", str(CASES / "good-matching")]) == 0
    assert "DRIFT" not in capsys.readouterr().out


def test_committed_bad_case_reports_drift(capsys):
    """The known-bad input: one rendered line edited in place, markers intact.

    The GOOD case above is the half that matters for a gate wedged at 'fail' -
    on its own, this assertion is also satisfied by a check that refuses every
    tree.
    """
    assert dcv.main(["check", "--root", str(CASES / "bad-drifted")]) == 1
    out = capsys.readouterr().out
    assert "DRIFT: .claude/commands/qwen/auto.md region B" in out


def test_blind_anchor_misses_the_bad_case(capsys):
    """The anchor must MISS what the gate catches, or it proves nothing.

    A markers-only check is the plausible weaker thing somebody would write. It
    catches deleted markers and is blind to a region edited in place - and an
    anchor that caught the bad input would mean the real gate's rendering
    comparison is not load-bearing.
    """
    anchor = ROOT / "controls/delegated-core-vendor/anchors/constructed-markers-only-delegated-core-vendor.py"
    # Run it, do NOT import it. An importlib load writes a .pyc under controls/,
    # and the negative-control harness's TRACKING axis reads any on-disk file the
    # index does not carry as "this control does not exist in a clean clone" -
    # so importing the anchor would make an unrelated gate report UNTRACKED on
    # every box that had run the tests. Subprocess is also how the harness itself
    # invokes it, which is the behaviour under test.
    for case, label in ((CASES / "bad-drifted", "known-bad"), (CASES / "good-matching", "known-good")):
        proc = subprocess.run(
            [sys.executable, "-B", str(anchor), "check", "--root", str(case)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"anchor reported a problem on the {label} case: {proc.stdout}"


def test_blind_anchor_can_still_report_something(tmp_path, capsys):
    """The anchor's own positive control - it must not be wedged at exit 0.

    `test_blind_anchor_misses_the_bad_case` asserts the anchor reports nothing on
    both committed cases, which is what the negative-control harness reads as
    "blind, as required". An anchor that had simply stopped working would satisfy
    that assertion identically, and the demonstration would then prove nothing
    about the real gate: a broken extractor's zeros look exactly like real ones.
    So feed it the ONE thing it does claim to catch - a deleted marker - and
    require it to say so.
    """
    work = tmp_path / "repo"
    shutil.copytree(CASES / "good-matching", work)
    driver = work / ".claude/commands/gemma/auto.md"
    driver.write_text(
        driver.read_text(encoding="utf-8").replace("<!-- delegated-core:end B -->", ""),
        encoding="utf-8",
    )
    anchor = ROOT / "controls/delegated-core-vendor/anchors/constructed-markers-only-delegated-core-vendor.py"
    proc = subprocess.run(
        [sys.executable, "-B", str(anchor), "check", "--root", str(work)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1, "the anchor reports nothing even on a deleted marker; it is broken, not blind"
    assert "MISSING" in proc.stdout


# ---------------------------------------------------------------------------
# Per-model text survives the move
# ---------------------------------------------------------------------------

#: A string that must appear in exactly one driver, and the driver it belongs
#: to. These are the passages that made the three documents different in the
#: first place; a render that lost one would leave a driver instructing the
#: wrong harness while every bytes comparison stayed green.
MODEL_SPECIFIC = {
    "codex": [
        "npm install -g @openai/codex",
        "--sandbox workspace-write",
        "CODEX_FIX_OUTPUT",
    ],
    "qwen": [
        "qwen3.8-code:latest",
        "QWEN_FIX_OUTPUT",
        "a local 27B model",
    ],
    "gemma": [
        "gemma-implementer",
        "GEMMA_FIX_OUTPUT",
        "a local 31B model",
        "WORKTREE_ROOT=$(git rev-parse --show-toplevel)",
    ],
}


@pytest.mark.parametrize("driver,needles", sorted(MODEL_SPECIFIC.items()))
def test_model_specific_text_survives(driver, needles):
    text = (ROOT / f".claude/commands/{driver}/auto.md").read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{driver}/auto.md lost model-specific text: {needle!r}"


@pytest.mark.parametrize("driver,needles", sorted(MODEL_SPECIFIC.items()))
def test_model_specific_text_did_not_leak_into_the_others(driver, needles):
    """Negative membership: the shared core must not have absorbed a neighbour.

    Asserting only that each driver KEPT its own strings passes just as well if
    all three ended up with all three sets - which is the other way a vendored
    core goes wrong, and the more plausible one, since it is what happens when a
    per-model passage is moved into the template by mistake.
    """
    for other in dcv.DRIVERS:
        if other == driver:
            continue
        text = (ROOT / f".claude/commands/{other}/auto.md").read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in text, (
                f"{other}/auto.md carries {driver}-specific text: {needle!r}"
            )


def test_the_step_3_gate_is_inside_the_vendored_core():
    """The #774 defect's home must be shared text, not three copies.

    If the approval gate drifted back OUT of the core - into the per-driver part
    of each file - this whole change would be cosmetic: the next lifecycle bug
    would again need fixing three times, which is the condition #1011 exists to
    end.
    """
    core = (ROOT / dcv.CORE_REL).read_text(encoding="utf-8")
    regions = dcv.parse_regions(core)
    assert "### Step 3: Approve - Pre-Implementation Gate" in regions["A"]
    assert "**The gate has no bypass (issue #784).**" in regions["A"]


# ---------------------------------------------------------------------------
# Malformed sources are refused, not rendered
# ---------------------------------------------------------------------------


@pytest.fixture()
def tree(tmp_path):
    """A minimal valid tree, copied from the committed GOOD case."""
    work = tmp_path / "repo"
    shutil.copytree(CASES / "good-matching", work)
    assert dcv.main(["check", "--root", str(work)]) == 0, (
        "fixture precondition: the copied GOOD case must start clean, or every "
        "assertion below would pass for the wrong reason"
    )
    return work


def test_unknown_slot_is_refused(tree, capsys):
    core = tree / dcv.CORE_REL
    core.write_text(core.read_text(encoding="utf-8") + "\n{{NO_SUCH_SLOT}}\n", encoding="utf-8")
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "no value for block slot {{NO_SUCH_SLOT}}" in capsys.readouterr().out


def test_mis_cased_placeholder_is_refused(tree, capsys):
    """`{{driver}}` is not a slot, so it would otherwise ship as literal text."""
    core = tree / dcv.CORE_REL
    core.write_text(
        core.read_text(encoding="utf-8").replace(
            "Claude reviews what {{DRIVER_TITLE}} wrote",
            "Claude reviews what {{driver_title}} wrote",
        ),
        encoding="utf-8",
    )
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "UNRESOLVED" in capsys.readouterr().out


def test_orphaned_slot_value_is_refused(tree, capsys):
    values = tree / dcv.VALUES_REL / "qwen.md"
    values.write_text(
        values.read_text(encoding="utf-8") + "<!-- slot: NOBODY_USES_ME -->\nx\n",
        encoding="utf-8",
    )
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "ORPHAN" in capsys.readouterr().out


def test_indented_block_slot_is_refused(tree, capsys):
    core = tree / dcv.CORE_REL
    core.write_text(
        core.read_text(encoding="utf-8").replace("{{STEP_EXTRA}}", "  {{STEP_EXTRA}}"),
        encoding="utf-8",
    )
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "is indented" in capsys.readouterr().out


def test_missing_marker_pair_is_reported(tree, capsys):
    driver = tree / ".claude/commands/codex/auto.md"
    driver.write_text(
        driver.read_text(encoding="utf-8").replace("<!-- delegated-core:end B -->", ""),
        encoding="utf-8",
    )
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "MISSING" in capsys.readouterr().out


def test_marker_welded_to_its_content_is_refused(tree, capsys):
    """The newline after a begin marker is not taken on faith (#1011 review).

    A substring search takes the next byte for granted. With the newline replaced
    by any other character the marker line absorbs the heading below it, and the
    payload located after it still compared EQUAL to the render - so the gate
    reported clean on a document whose region heading had been welded onto an
    HTML comment.
    """
    driver = tree / ".claude/commands/qwen/auto.md"
    text = driver.read_text(encoding="utf-8")
    marker = "<!-- delegated-core:begin B (canonical: templates/delegated-driver-core.md) -->\n"
    assert text.count(marker) == 1
    driver.write_text(text.replace(marker, marker.rstrip("\n") + "X"), encoding="utf-8")
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "MISSING" in capsys.readouterr().out


def test_regions_in_the_wrong_order_are_refused(tree, capsys):
    """Each region matching its own render says nothing about WHERE it sits.

    Swapped wholesale, both regions compare equal and the gate reports clean - on
    a driver that tells the reader to invoke the model and *then* asks for
    approval, which inverts the property #774 was about. That is the shape this
    whole change would otherwise make easier to produce, not harder.
    """
    driver = tree / ".claude/commands/codex/auto.md"
    text = driver.read_text(encoding="utf-8")
    a0 = text.index("<!-- delegated-core:begin A")
    a1 = text.index("<!-- delegated-core:end A -->") + len("<!-- delegated-core:end A -->")
    b0 = text.index("<!-- delegated-core:begin B")
    b1 = text.index("<!-- delegated-core:end B -->") + len("<!-- delegated-core:end B -->")
    swapped = text[:a0] + text[b0:b1] + text[a1:b0] + text[a0:a1] + text[b1:]
    driver.write_text(swapped, encoding="utf-8")
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "MISORDERED" in capsys.readouterr().out


def test_write_refuses_a_misordered_document(tree, capsys):
    """--write must not render each region correctly into the wrong position.

    Rewriting a misordered document in place leaves a tree the check then calls
    clean, which launders the defect instead of reporting it.
    """
    driver = tree / ".claude/commands/codex/auto.md"
    text = driver.read_text(encoding="utf-8")
    a0 = text.index("<!-- delegated-core:begin A")
    a1 = text.index("<!-- delegated-core:end A -->") + len("<!-- delegated-core:end A -->")
    b0 = text.index("<!-- delegated-core:begin B")
    b1 = text.index("<!-- delegated-core:end B -->") + len("<!-- delegated-core:end B -->")
    driver.write_text(text[:a0] + text[b0:b1] + text[a1:b0] + text[a0:a1] + text[b1:], encoding="utf-8")
    assert dcv.main(["--write", "--root", str(tree)]) == 1
    assert "MISORDERED" in capsys.readouterr().out


def test_duplicated_marker_is_refused(tree, capsys):
    """Two begin markers for one region make "the region" ambiguous."""
    driver = tree / ".claude/commands/gemma/auto.md"
    text = driver.read_text(encoding="utf-8")
    marker = "<!-- delegated-core:begin A (canonical: templates/delegated-driver-core.md) -->"
    driver.write_text(text.replace(marker, marker + "\n" + marker, 1), encoding="utf-8")
    assert dcv.main(["check", "--root", str(tree)]) == 1
    assert "MISSING" in capsys.readouterr().out


def test_write_refuses_a_malformed_source(tree, capsys):
    """--write must fail closed too, or the repair path launders the defect."""
    core = tree / dcv.CORE_REL
    core.write_text(core.read_text(encoding="utf-8") + "\n{{NO_SUCH_SLOT}}\n", encoding="utf-8")
    assert dcv.main(["--write", "--root", str(tree)]) == 1
    assert "no value for block slot" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Rendering rules
# ---------------------------------------------------------------------------


def test_empty_block_slot_removes_its_line():
    rendered, used = dcv.render("a\n{{X}}\nb", {"X": ""}, "test")
    assert rendered == "a\nb"
    assert used == {"X"}


def test_block_slot_lines_are_inserted_verbatim():
    rendered, _ = dcv.render("a\n{{X}}\nb", {"X": "one\ntwo\n"}, "test")
    assert rendered == "a\none\ntwo\n\nb"


def test_inline_slot_must_be_single_line():
    with pytest.raises(dcv.CoreError, match="must be a single line"):
        dcv.render("prefix {{X}} suffix", {"X": "one\ntwo"}, "test")


def test_empty_inline_slot_renders_as_nothing():
    rendered, _ = dcv.render("report.{{X}}\n", {"X": ""}, "test")
    assert rendered == "report.\n"


def test_template_preamble_is_not_rendered():
    """Text above the first region marker is authoring guidance, not content.

    It is also where the core documents its own `{{NAME}}` syntax, so a renderer
    that included it would refuse the template it is documenting.
    """
    regions = dcv.parse_regions((ROOT / dcv.CORE_REL).read_text(encoding="utf-8"))
    joined = "\n".join(regions.values())
    assert "EDIT HERE" not in joined
    assert "{{NAME}}" not in joined
