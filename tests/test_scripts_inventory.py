"""The docs/scripts.md population is derived from scripts/ (issue #1013).

`docs/scripts.md` is the inventory of this repository's own tooling. Nothing
generated it and nothing checked it, so a script could be added and its entry
simply never written - 17 of 68 files were in that state when this landed - while
six test modules quoted individual sentences out of the file as if it were a
specification. An inventory that looks complete is read as complete; the gap was
invisible because no instrument could represent it.

WHAT THESE TESTS PIN:

  * the real tree passes - this IS the drift gate, and it is the assertion `make
    scripts-inventory-check` and the CI step both run;
  * the committed BAD/GOOD cases discriminate (ADR 0008), executed here as well as
    by the negative-control harness, because this gate's green is read by `make
    verify` and by CI and nothing downstream re-derives it;
  * the rule matches the DOCUMENT'S convention rather than the filename - issue
    #1013 as filed measured the gap by grepping for basenames with extensions,
    which appear in no heading in the file, and adopting that rule would have
    demanded every heading be rewritten;
  * an entry claim is a BACKTICKED name in heading-subject or bullet-head
    position, one rule read by both directions - the three counter-model findings
    were all the forward and reverse sides reading the document differently;
  * a stem that is a PREFIX of another stem is not satisfied by the longer one's
    entry - `project-next` and `project-next-vendor` are both live in this tree;
  * one script may own several sections - `check-test-binary-guards` owns three -
    so the rule asks whether at least one entry exists, never exactly one;
  * a population of zero refuses rather than reporting a clean verdict over an
    unexamined tree.

Hermetic and git-free: tmp_path trees plus the checked-in control fixtures, so
this gives the same verdict in CI's git-less validate container as locally.
"""

from __future__ import annotations

import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "scripts-inventory-check.py"
_spec = spec_from_file_location("scripts_inventory_check", _script_path)
sic = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(sic)  # type: ignore[union-attr]
sys.modules["scripts_inventory_check"] = sic

CASES = ROOT / "controls" / "scripts-inventory" / "cases"
ANCHOR = (
    ROOT
    / "controls"
    / "scripts-inventory"
    / "anchors"
    / "constructed-headings-only-scripts-inventory-check.py"
)


def _tree(tmp_path: Path, scripts: list[str], doc: str) -> Path:
    """A miniature repo: named files under scripts/, and a docs/scripts.md."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)
    for name in scripts:
        (root / "scripts" / name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (root / "docs" / "scripts.md").write_text(doc, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Real-repo pins - this is the drift gate
# ---------------------------------------------------------------------------


def test_the_real_inventory_covers_the_real_tree():
    assert sic.main(["check", "--root", str(ROOT)]) == 0


def test_every_script_in_the_tree_has_an_entry():
    """The same property, stated as a set rather than an exit code.

    The exit-code test above would still pass if the gate were rewritten to
    examine nothing; this one names the population independently, so a gate that
    silently narrowed what it looks at is visible here.
    """
    doc = (ROOT / "docs" / "scripts.md").read_text(encoding="utf-8")
    stems = sic.script_stems(ROOT)
    assert len(stems) > 50, f"only {len(stems)} scripts found - the tree is not being read"
    missing = sorted(name for stem, name in stems.items() if not sic.has_entry(doc, stem))
    assert not missing, f"{len(missing)} script(s) with no entry in docs/scripts.md: {missing}"


def test_every_entry_claim_resolves_to_a_script_or_a_declaration():
    doc = (ROOT / "docs" / "scripts.md").read_text(encoding="utf-8")
    stems = set(sic.script_stems(ROOT))
    declared = sic.declared_non_script_sections(doc)
    assert declared, "the document declares no non-script sections; the marker is gone"
    claims = sic.entry_claims(doc)
    assert len(claims) > 50, f"only {len(claims)} claims parsed - the document is not being read"
    unresolved = sorted(c for c in claims if c not in stems and c not in declared)
    assert not unresolved, f"entr(ies) naming no script and undeclared: {unresolved}"


# ---------------------------------------------------------------------------
# The committed control (ADR 0008)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("bad-unlisted-script", 1),
        ("bad-stale-entry", 1),
        ("bad-stale-bullet", 1),
        ("good-complete", 0),
    ],
)
def test_the_committed_cases_discriminate(case, expected):
    assert sic.main(["check", "--root", str(CASES / case)]) == expected


@pytest.mark.parametrize(
    "case", ["bad-unlisted-script", "bad-stale-entry", "bad-stale-bullet"]
)
def test_the_anchor_is_blind_to_the_known_bad_input(case):
    """The registered anchor must MISS every bad case.

    An anchor that CATCHES a bad input proves the control is not load-bearing:
    the weaker check would have been enough, and the gate's green says nothing
    the cheaper instrument was not already saying.
    """
    proc = subprocess.run(
        [sys.executable, str(ANCHOR), "check", "--root", str(CASES / case)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"the anchor DETECTED {case}; it is not blind, so controls/scripts-inventory "
        f"does not demonstrate that the real gate is load-bearing.\n{proc.stdout}"
    )


def test_the_anchor_can_report_bad_at_all(tmp_path):
    """POSITIVE CONTROL FOR THE ANCHOR: prove it is weaker, not broken.

    Every other assertion about the anchor asks it to say GOOD - it must miss each
    bad case and agree on the good one. An anchor of `sys.exit(0)` satisfies all of
    them, and "blind, as required" would be printed over an instrument that cannot
    speak. So feed it the one input it IS supposed to catch - a repeated heading,
    which is the framing it embodies - and require a non-zero.
    """
    doc = tmp_path / "repo" / "docs"
    doc.mkdir(parents=True)
    (doc / "scripts.md").write_text(
        "# t\n\n## `alpha-tool`\n\n- a\n\n## `alpha-tool`\n\n- b\n", encoding="utf-8"
    )
    proc = subprocess.run(
        [sys.executable, str(ANCHOR), "check", "--root", str(tmp_path / "repo")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, (
        "the anchor reports GOOD on the input it exists to catch, so it is BROKEN "
        f"rather than blind and every 'missed the known-bad input' line is vacuous.\n{proc.stdout}"
    )


def test_the_anchor_agrees_with_the_gate_on_the_known_good_input():
    """Anchor sanity: it must differ from the gate ONLY in the blindness under test."""
    proc = subprocess.run(
        [sys.executable, str(ANCHOR), "check", "--root", str(CASES / "good-complete")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"anchor disagrees on the known-good case:\n{proc.stdout}"


# ---------------------------------------------------------------------------
# The matching rule
# ---------------------------------------------------------------------------


def test_a_heading_entry_satisfies_the_rule(tmp_path):
    root = _tree(tmp_path, ["solo.sh"], "# t\n\n## `solo`\n\n- solo - prose.\n")
    assert sic.main(["check", "--root", str(root)]) == 0


def test_a_backticked_bullet_entry_satisfies_the_rule(tmp_path):
    """How the grouped sections carry the seven scripts with no section of their own.

    The backticks are required, and that is the rule the counter-model review
    settled: without them the reverse check cannot see a stale bullet, and with a
    bare-token rule ordinary prose starts reporting UNDECLARED. The negative half
    is pinned by test_prose_leading_with_a_bare_name_is_not_an_entry_claim.
    """
    root = _tree(tmp_path, ["solo.sh"], "# t\n\n## Grouped things\n\n- `solo` - prose.\n")
    assert sic.main(["check", "--root", str(root)]) == 0


def test_the_extension_is_not_required_in_an_entry(tmp_path):
    """Issue #1013's own reproduce command demanded `solo.sh`; the document says `solo`.

    Had the gate adopted the filename rule, this tree would be RED and the remedy
    would have been to rewrite every heading in the real file to carry an
    extension - a larger and worse change than the one asked for.
    """
    root = _tree(tmp_path, ["solo.sh"], "# t\n\n## `solo`\n\n- solo - prose.\n")
    assert sic.main(["check", "--root", str(root)]) == 0


def test_a_longer_stems_entry_does_not_satisfy_a_prefix_stem(tmp_path):
    """`project-next` and `project-next-vendor` are both live in this repository.

    Without the trailing boundary, `- project-next-vendor ...` would be read as an
    entry for `project-next`, and a script could lose its entry the day a
    longer-named sibling gained one.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh", "alpha-extra.sh"],
        "# t\n\n## `alpha-extra`\n\n- alpha-extra - prose.\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 1


def test_one_script_may_own_several_sections(tmp_path):
    """`check-test-binary-guards` owns three, distinguished by issue suffixes.

    Issue #1013 scoped that out explicitly, so the rule must tolerate it rather
    than demanding a bijection.
    """
    root = _tree(
        tmp_path,
        ["solo.sh"],
        "# t\n\n## `solo` (#1)\n\n- solo - first.\n\n## `solo` (#2)\n\n- solo - second.\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 0


def test_a_declared_non_script_section_is_accepted(tmp_path):
    root = _tree(
        tmp_path,
        ["solo.sh"],
        "# t\n\n<!-- scripts-inventory: non-script-sections: hooks -->\n\n"
        "## `solo`\n\n- solo - prose.\n\n## `hooks`\n\n- hooks\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 0


def test_an_undeclared_non_script_section_is_refused(tmp_path):
    """The declaration list narrows what is checked - so it must fail LOUDLY.

    A new non-script section turns the gate red until someone declares it, which
    is the difference between a list that narrows silently and one that does not.
    """
    root = _tree(
        tmp_path,
        ["solo.sh"],
        "# t\n\n## `solo`\n\n- solo - prose.\n\n## `hooks`\n\n- hooks\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 1


def test_the_document_title_is_not_treated_as_an_entry(tmp_path):
    """`# \\`scripts/\\` inventory` is an H1 and names no script."""
    root = _tree(tmp_path, ["solo.sh"], "# `scripts/` inventory\n\n## `solo`\n\n- solo - p.\n")
    assert sic.main(["check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# The gate refuses rather than reporting clean over nothing
# ---------------------------------------------------------------------------


def test_an_empty_scripts_dir_refuses_instead_of_passing(tmp_path, capsys):
    """A population of zero makes every assertion vacuously true.

    Reporting `ok` there is the blind-instrument shape: a clean line over a tree
    nothing examined, indistinguishable from a real pass.
    """
    root = _tree(tmp_path, [], "# t\n")
    assert sic.main(["check", "--root", str(root)]) == 1
    assert "nothing compared" in capsys.readouterr().out


def test_a_missing_inventory_refuses(tmp_path):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "solo.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    assert sic.main(["check", "--root", str(root)]) == 1


def test_directories_under_scripts_are_not_required_to_have_entries(tmp_path):
    root = _tree(tmp_path, ["solo.sh"], "# t\n\n## `solo`\n\n- solo - prose.\n")
    (root / "scripts" / "subdir").mkdir()
    assert sic.main(["check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# Counter-model review regressions (all three reproduce on the first cut)
# ---------------------------------------------------------------------------


def test_a_stale_bullet_for_a_deleted_script_is_caught(tmp_path):
    """The reverse check must read BULLETS, not only headings.

    The first cut examined heading subjects alone, so a bullet entry for a deleted
    script scored clean - and seven scripts in the real inventory are carried by a
    bullet alone, which is exactly the population that direction has to cover.
    """
    root = _tree(
        tmp_path,
        ["alpha-tool.sh"],
        "# t\n\n<!-- scripts-inventory: non-script-sections: hooks -->\n\n"
        "## `alpha-tool`\n\n- alpha-tool - prose.\n\n"
        "## `hooks`\n\n- `beta-tool` - entry for tooling that is gone.\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 1


def test_an_incidental_backticked_mention_does_not_satisfy_an_entry(tmp_path):
    """``## `alpha` (calls `beta`)`` is one section, about `alpha`.

    The first cut matched any backticked token anywhere on a heading line in the
    forward direction while taking only the first in the reverse - so a
    neighbour's incidental mention stood in as an undocumented script's entry.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        "# t\n\n## `alpha` (calls `beta`)\n\n- alpha - prose.\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 1


def test_a_fenced_example_is_not_read_as_the_document(tmp_path):
    """An illustrative heading must neither satisfy an entry nor report UNDECLARED.

    This gate is in `make verify`, so the false-red half is the expensive one: a
    markdown example in the inventory would have blocked every merge in the repo.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        "# t\n\n## `alpha`\n\n- alpha - prose. Example:\n\n"
        "```markdown\n## `beta`\n\n- `beta` - illustrative only.\n```\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 0


def test_an_example_entry_does_not_satisfy_a_real_missing_one(tmp_path):
    """The other half of the same rule, and the one a false-red fix could drop."""
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        "# t\n\n## `alpha`\n\n- alpha - prose. Example:\n\n"
        "```markdown\n## `beta`\n\n- `beta` - illustrative only.\n```\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 1


def test_prose_leading_with_a_bare_name_is_not_an_entry_claim(tmp_path):
    """The backticks are what make a bullet a claim.

    Measured on the real document: without that requirement, ``- shellcheck is
    also needed`` and two possessives reported UNDECLARED - three false findings
    in a gate that blocks every merge.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        "# t\n\n## `alpha`\n\n- alpha - prose.\n- shellcheck is also needed here.\n"
        "- alpha's own behaviour is unchanged.\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# Counter-model review pass 2 - fence and comment handling
# ---------------------------------------------------------------------------


def test_a_longer_fence_is_not_closed_by_a_shorter_inner_one(tmp_path):
    """````-fenced example containing ``` must stay entirely an example.

    A fixed three-character fence pattern read the inner ``` as the close and
    spilled the rest of the example into the document, reporting UNDECLARED on a
    correct inventory - a false red in a gate that blocks every merge.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        "# t\n\n## `alpha`\n\n- alpha - p. Example:\n\n"
        "````markdown\n```\n## `beta`\n```\n````\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 0


def test_a_fenced_declaration_cannot_widen_the_allowlist(tmp_path):
    """The worst direction: a false GREEN suppressing a real stale entry.

    Declarations were read from the raw text, so a marker inside a fenced example
    exempted a genuinely stale section. A list that narrows must not be widenable
    by prose.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh"],
        "# t\n\n## `alpha`\n\n- alpha - p.\n\n## `beta`\n\n- beta - STALE.\n\n"
        "```markdown\n<!-- scripts-inventory: non-script-sections: beta -->\n```\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 1


def test_a_fenced_comment_opener_does_not_eat_a_real_entry(tmp_path):
    """Comments must be stripped AFTER fences, not before.

    A `<!--` inside a fenced HTML example paired with an ordinary comment further
    down and deleted every entry between them, so a complete inventory reported a
    script missing whose entry is plainly visible.
    """
    root = _tree(
        tmp_path,
        ["alpha.sh", "beta.sh"],
        "# t\n\n## `alpha`\n\n- alpha - p. Example:\n\n"
        "```html\n<!-- an opener with no closer inside the fence\n```\n\n"
        "## `beta`\n\n- beta - a REAL entry.\n\n<!-- an ordinary later comment -->\n",
    )
    assert sic.main(["check", "--root", str(root)]) == 0


# ---------------------------------------------------------------------------
# Wiring - the gate must actually be run by something
# ---------------------------------------------------------------------------


def test_the_gate_is_wired_into_make_verify():
    """A gate nothing invokes is not a gate (the #591 shape: a working script
    called by no step, no target and no test, so staleness stayed invisible)."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\nscripts-inventory-check:\n" in text, "the make target is gone"
    verify = text.split("\nverify:", 1)[1].split("\n\n", 1)[0]
    assert "scripts-inventory-check" in verify, "the gate was dropped from `make verify`"


def test_the_gate_registers_its_negative_control():
    """The registration lives in the gate file because that is what the battery reads.

    A control directory alone is invisible to `check-negative-controls.py`, which
    then reports PASS over a register the new control is not in - observed while
    building this one.
    """
    text = _script_path.read_text(encoding="utf-8")
    assert "NEGATIVE-CONTROL: controls/scripts-inventory" in text
