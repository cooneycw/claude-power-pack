"""Regression tests for the Codex SKILL.md skill generator (issue #555).

Hybrid single-SoT bridge (codex-power-pack epic cooneycw/codex-power-pack#64,
story B1): `.claude/commands/<family>/*.md` is the single source of truth and
`scripts/codex-skill-sync.py` emits checked-in per-command Codex skill
directories under `codex/skills/<family>-<command>/`. This surface superseded
the flat custom prompts from `scripts/codex-prompt-sync.py` (issue #446), which
were retired at the issue #556 cutover.

The hazards these pin:
  * the checked-in skills must stay in sync with their command source
    (the real-repo --check below IS the CI drift gate);
  * the generator must only ever manage skill dirs whose SKILL.md carries its
    GENERATED marker - hand-curated skill dirs must never be overwritten,
    pruned, or orphan-deleted;
  * SKILL.md frontmatter must stay valid YAML whatever the source description
    contains (the retired codex-skill-gen.py's #312 quoting bug);
  * the `codex` family must never be generated (Codex skills that orchestrate
    the Codex CLI itself are circular);
  * bundled helper scripts must be byte-identical copies of scripts/<name>;
  * slash references must rewrite only to skills that actually exist in the
    Codex surface (/flow:eli5 -> /flow-eli5, but /cpp:init stays untouched).

Hermetic and git-free: unit tests run against tmp_path trees via monkeypatched
module roots; the real-repo tests only read checked-in files. Runs in CI's
git-less validate container (see the cpp_validate_container_no_git learning).
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_script_path = ROOT / "scripts" / "codex-skill-sync.py"
_spec = spec_from_file_location("codex_skill_sync", _script_path)
codex_skill_sync = module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(codex_skill_sync)  # type: ignore[union-attr]
sys.modules["codex_skill_sync"] = codex_skill_sync

# DERIVED from the generator, never spelled twice (issue #1185). A test
# carrying its own copy of the manifest filename would keep excluding
# "SHA256SUMS" after the generator started writing something else, and the
# exclusion would then hide a real orphan under the old name.
MANIFEST_NAME = codex_skill_sync.MANIFEST_NAME


# ---------------------------------------------------------------------------
# Real-repo pins (this is the CI drift gate)
# ---------------------------------------------------------------------------


def test_real_repo_skills_in_sync():
    """codex/skills/ must match what the generator produces from source."""
    assert codex_skill_sync.main(["--check"]) == 0


def test_real_repo_skill_dirs_are_managed():
    skills_root = ROOT / "codex" / "skills"
    for family in codex_skill_sync.FAMILIES:
        for d in skills_root.glob(f"{family}-*"):
            if d.is_dir():
                assert codex_skill_sync.is_managed(d), d.name


def test_real_repo_frontmatter_is_valid():
    """Every generated SKILL.md opens with parseable name/description
    frontmatter followed by the GENERATED marker (issue #312 lesson)."""
    for skill_md in sorted((ROOT / "codex" / "skills").glob("*/SKILL.md")):
        lines = skill_md.read_text().splitlines()
        assert lines[0] == "---", skill_md
        assert lines[1].startswith("name: "), skill_md
        assert lines[2].startswith("description: "), skill_md
        assert lines[3] == "---", skill_md
        assert lines[4].startswith(codex_skill_sync.MARKER_PREFIX), skill_md
        name = json.loads(lines[1][len("name: "):])
        description = json.loads(lines[2][len("description: "):])
        assert name == skill_md.parent.name
        assert description.strip()


def test_real_repo_codex_family_not_generated():
    assert "codex" not in codex_skill_sync.FAMILIES
    assert not list((ROOT / "codex" / "skills").glob("codex-*"))


def test_real_repo_excluded_commands_not_generated():
    skills = ROOT / "codex" / "skills"
    assert not (skills / "cpp-init").exists()
    assert not (skills / "cpp-status").exists()
    assert not (skills / "cpp-update").exists()
    # self-improvement/memory.md ships as the curated prompt codex/cpp-memory.md
    # (relocated out of the retired codex/prompts/ flat surface at the #556 cutover).
    assert not (skills / "self-improvement-memory").exists()


def test_real_repo_bundled_scripts_byte_identical():
    """Every bundled script is a byte-identical copy of its repo source.

    `SHA256SUMS` is excluded BY NAME rather than by "skip anything with no
    source" (issue #1185). It is the one file under `scripts/` that is
    GENERATED rather than copied, so it has no repo-side source by design - but
    a blanket skip would also pass over a genuinely orphaned bundled script,
    which is the defect this test exists to catch. Naming the exception keeps
    the population exactly one file smaller instead of unboundedly smaller.
    """
    seen_manifest = False
    for bundled in sorted((ROOT / "codex" / "skills").glob("*/scripts/*")):
        if bundled.name == MANIFEST_NAME:
            seen_manifest = True
            continue
        source = ROOT / "scripts" / bundled.name
        assert source.is_file(), bundled
        assert bundled.read_bytes() == source.read_bytes(), bundled
    # The exclusion above is only safe while the thing it excludes EXISTS. If
    # the manifest ever stops being generated, this test would quietly go back
    # to covering a population that no longer contains it - and the integrity
    # check in flow-helpers-install.sh would have nothing to read.
    assert seen_manifest, (
        f"no {MANIFEST_NAME} under any bundle - the exclusion above is excluding "
        "nothing, and bundled helpers are no longer verifiable (#1185)"
    )


def test_real_repo_bundled_libraries_byte_identical():
    """The same property for the LIBRARIES bundled since #1028.

    This glob is separate rather than widened because the path rule differs: a
    bundled script is flattened to `scripts/<name>` and matched by basename,
    while a bundled library keeps its REPO-RELATIVE path - which is precisely
    what makes each script's own `parents[1]` resolution land inside the skill
    directory. Matching a library by basename would pass over a copy bundled at
    the wrong depth, and the wrong depth is the whole failure being fixed.
    """
    skills = ROOT / "codex" / "skills"
    bundled = [
        p
        for p in skills.rglob("*.py")
        if p.is_file()
        and "scripts" not in p.relative_to(skills).parts[1:2]
        and "__pycache__" not in p.parts
    ]
    # A POPULATION FLOOR, AND NOTHING MORE. This test compares the bytes of
    # whatever is bundled; it cannot see a library that should be bundled and is
    # not, because an absent file is absent from its population too. Which
    # bundles must EXIST is asserted by the two executed tests below, and that
    # division is deliberate - stripping flow-eli5's and project-next's
    # libraries left flow-auto's and flow-finish's standing, and this test went
    # green over the stripped tree exactly as its design says it should. The
    # message says that rather than "#1028's fix is gone", which it does not
    # check.
    assert bundled, "nothing to compare: no libraries are bundled anywhere"
    for path in sorted(bundled):
        rel = path.relative_to(skills).parts[1:]
        source = ROOT.joinpath(*rel)
        assert source.is_file(), f"{path} corresponds to no file in the checkout"
        assert path.read_bytes() == source.read_bytes(), path


def test_real_repo_eli5_drift_check_runs_from_its_own_bundle(tmp_path):
    """Issue #1028 item 4's acceptance, executed rather than asserted.

    The committed red case is the pre-#1028 tree: the bundler discovered
    `scripts/<name>` references in the command BODY, and `eli5-core-drift.sh`'s
    only `scripts/` token is in its header comment - the line that actually runs
    is `exec python3 "$SELF_DIR/eli5-vendor.py"`. So the shim shipped alone and
    every invocation from the Codex surface died on a missing file, in a script
    whose own header says it exists "so there is exactly ONE implementation
    behind them". On that tree this test fails at the first assertion.

    Executed against a real drifted tree rather than re-grepping the bundle,
    deliberately: a check that re-derived the dependency rule would share the
    resolver's blind spots and agree with it by construction.
    """
    shim = ROOT / "codex" / "skills" / "flow-eli5" / "scripts" / "eli5-core-drift.sh"
    assert shim.is_file()
    assert (shim.parent / "eli5-vendor.py").is_file(), "the shim's implementation is not bundled"
    assert (shim.parent.parent / "lib" / "vendor.py").is_file(), "its library is not bundled"

    drifted = tmp_path / "drifted"
    (drifted / ".claude" / "commands" / "flow").mkdir(parents=True)
    shutil.copy(ROOT / ".claude" / "eli5-vendor.json", drifted / ".claude")
    core = (ROOT / ".claude" / "commands" / "flow" / "eli5.md").read_text()
    assert "\n## What this is for\n" in core
    (drifted / ".claude" / "commands" / "flow" / "eli5.md").write_text(
        core.replace("\n## What this is for\n", "\n## What this is for (LOCAL EDIT)\n", 1)
    )

    result = subprocess.run(
        ["bash", str(shim), "--root", str(drifted)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    # Fail-open by design: no network means no verdict, and that is not a pass
    # to assert against either. Skip rather than let a plane ride look like a fix.
    if "upstream unavailable" in result.stderr:
        pytest.skip("canonical eli5-gate unreachable; the advisory is fail-open")
    assert result.returncode == 1, f"drift went unreported\n{result.stdout}{result.stderr}"
    assert "has drifted" in result.stderr


def test_real_repo_eli5_bare_invocation_fails_loudly_and_never_reports_in_sync():
    """The LIMIT of the eli5 fix, pinned rather than left to be discovered.

    The counter-model review's second pass is right that the bundled shim cannot
    produce a verdict with no `--root`: the skill directory carries the drift
    check's code but not `.claude/eli5-vendor.json`, nor the document that
    manifest identifies. Bundling those would mean this generator learning the
    layout of one particular script's config, and the honest subject of a drift
    check run from an installed skill is a CHECKOUT, which only `--root` can
    name.

    So the bare invocation is expected to fail - and what this pins is that it
    fails LOUDLY, naming the missing manifest, and can never print the in-sync
    line. A fail-open advisory that went quietly green with nothing to compare
    would be the blind instrument this whole issue is about, shipped inside the
    fix for it.
    """
    shim = ROOT / "codex" / "skills" / "flow-eli5" / "scripts" / "eli5-core-drift.sh"
    result = subprocess.run(
        ["bash", str(shim)],
        capture_output=True, text=True, timeout=120, check=False,
        cwd=str(shim.parent),
    )
    combined = result.stdout + result.stderr
    assert result.returncode != 0, f"a bare run must not succeed\n{combined}"
    assert "manifest not found" in combined, combined
    assert "is in sync" not in combined, (
        "the bundled drift check reported in-sync with nothing to compare"
    )


def test_real_repo_project_next_runs_a_real_query_from_its_own_bundle(tmp_path):
    """The second live instance of the same defect, which #1028 did not name.

    `codex/skills/project-next/scripts/project-next.py` died on
    `ModuleNotFoundError: No module named 'lib'` - the bundler carried the entry
    point and none of what it imports. One bundler bug, two shipped artifacts
    that could not run.

    THIS ASSERTS A REAL QUERY, NOT `--help`, AND THAT IS THE LESSON. The first
    version of this test ran `--help`, which passed the moment the imports
    resolved - and the counter-model review found that a real invocation still
    died on `[Errno 2] ... codex/skills/project-next/.claude/project-next-vendor.json`,
    because the entry point reads that manifest at rank time. A test named "starts
    from its own bundle" was true and useless: "it imports" is not "it works", and
    the gap was invisible from the passing side.

    `--input` supplies the repository state, so nothing here touches the network
    or `gh`; the manifest read is on the same code path either way.
    """
    entry = ROOT / "codex" / "skills" / "project-next" / "scripts" / "project-next.py"
    assert entry.is_file()

    state = tmp_path / "state.json"
    state.write_text(json.dumps({
        "repository": "o/r", "issues": [], "pull_requests": [],
        "branches": [], "worktrees": [], "spec_features": [], "spec_tasks": [],
    }))
    result = subprocess.run(
        [sys.executable, str(entry), "--input", str(state), "o/r"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"
    assert "No such file or directory" not in result.stdout + result.stderr


def test_a_mention_is_not_a_dependency(tmp_repo):
    """The closure follows `$VAR/<name>`, never a `scripts/<name>` mention.

    `flow-wave-registry.sh` PRINTS `"... scripts/checkout-readers.sh says when
    ..."` inside an echo; `speckit-tasks-to-issues.sh` names a sibling in a
    comment. Neither is a dependency, and a textual rule would bundle a whole
    subtree for a sentence - while still missing `eli5-core-drift.sh`, whose
    real dependency has no `scripts/` prefix at all.
    """
    scripts = tmp_repo / "scripts"
    (scripts / "helper.sh").write_text(
        "#!/bin/bash\n"
        "# see scripts/mentioned.sh for the history\n"
        'echo "scripts/mentioned.sh explains why" >&2\n'
        'SELF_DIR=$(dirname "$0")\n'
        'exec "$SELF_DIR/really-used.sh"\n'
    )
    (scripts / "mentioned.sh").write_text("#!/bin/bash\n")
    (scripts / "really-used.sh").write_text("#!/bin/bash\n")

    codex_skill_sync.main(["--write"])
    bundled = tmp_repo / "codex" / "skills" / "flow-auto" / "scripts"
    assert (bundled / "really-used.sh").is_file(), "the invoked sibling was not bundled"
    assert not (bundled / "mentioned.sh").exists(), "a mention was bundled as a dependency"


def test_an_indirect_import_is_bundled_and_the_bundle_runs(tmp_repo):
    """Dependency discovery walks, it does not take one pass (#1028 review).

    Scanning only the entry scripts meant a copied module was never itself
    examined: `x.py` imports `lib.a`, `lib/a.py` says `from .b import value`,
    and the bundle carried `a.py` with no `b.py`. Generation succeeded and the
    bundled entry point died at import.

    The real project-next bundle was complete only because its entry point
    imports all six modules DIRECTLY - the transitive edges held by coincidence,
    which is not a property anything was checking. This fixture removes the
    coincidence: nothing imports `b` except `a`.

    Executed, not inspected: the assertion that matters is that the bundled copy
    runs, which is the claim a file-presence check cannot make.
    """
    lib = tmp_repo / "lib" / "deep"
    lib.mkdir(parents=True)
    (lib / "__init__.py").write_text("")
    (lib / "a.py").write_text("from .b import value\n")
    (lib / "b.py").write_text("value = 'reached the indirect module'\n")
    # The real entry points resolve their root from their own location and
    # insert it on sys.path; that is exactly what makes a repo-relative bundle
    # layout work, so the fixture uses the same shape.
    (tmp_repo / "scripts" / "importer.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "REPO_ROOT = Path(__file__).resolve().parents[1]\n"
        "sys.path.insert(0, str(REPO_ROOT))\n"
        "from lib.deep.a import value\n"
        "print(value)\n"
    )
    (tmp_repo / ".claude" / "commands" / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nUses scripts/importer.py.\n"
    )

    codex_skill_sync.main(["--write"])
    bundled = tmp_repo / "codex" / "skills" / "flow-auto"
    assert (bundled / "lib" / "deep" / "b.py").is_file(), (
        "the indirect dependency was not bundled"
    )

    result = subprocess.run(
        [sys.executable, str(bundled / "scripts" / "importer.py")],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"
    assert "reached the indirect module" in result.stdout


def test_the_from_package_import_form_is_followed_too(tmp_repo):
    """`from . import b` is the same dependency as `from .b import value`.

    This spelling appears nowhere in the repository today, which is precisely
    why it is pinned: a closure written against only the shapes currently
    present is one refactor away from bundling an incomplete package, and the
    symptom would be an ImportError in a shipped artifact rather than a red here.
    """
    lib = tmp_repo / "lib" / "deep"
    lib.mkdir(parents=True)
    (lib / "__init__.py").write_text("")
    (lib / "a.py").write_text("from . import b\nvalue = b.value\n")
    (lib / "b.py").write_text("value = 'reached via from-package import'\n")
    (tmp_repo / "scripts" / "importer.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "REPO_ROOT = Path(__file__).resolve().parents[1]\n"
        "sys.path.insert(0, str(REPO_ROOT))\n"
        "from lib.deep.a import value\n"
        "print(value)\n"
    )
    (tmp_repo / ".claude" / "commands" / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nUses scripts/importer.py.\n"
    )

    codex_skill_sync.main(["--write"])
    bundled = tmp_repo / "codex" / "skills" / "flow-auto"
    assert (bundled / "lib" / "deep" / "b.py").is_file()
    result = subprocess.run(
        [sys.executable, str(bundled / "scripts" / "importer.py")],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"
    assert "reached via from-package import" in result.stdout


def test_a_runtime_data_file_the_entry_point_reads_is_bundled(tmp_repo):
    """Code is not the whole dependency (#1028 counter-model review).

    `project-next.py` imported fine and printed `--help` while a real query died
    on a manifest the bundle did not carry. "It starts" and "it works" are
    different claims; only the second matters to whoever runs it.
    """
    (tmp_repo / ".claude" / "pin.json").write_text('{"contract_version": "1"}\n')
    (tmp_repo / "scripts" / "reader.py").write_text(
        "from pathlib import Path\n"
        "REPO_ROOT = Path(__file__).resolve().parents[1]\n"
        'MANIFEST = REPO_ROOT / ".claude" / "pin.json"\n'
        "print(MANIFEST.read_text())\n"
    )
    (tmp_repo / ".claude" / "commands" / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nUses scripts/reader.py.\n"
    )

    codex_skill_sync.main(["--write"])
    bundled = tmp_repo / "codex" / "skills" / "flow-auto"
    assert (bundled / ".claude" / "pin.json").is_file()

    result = subprocess.run(
        [sys.executable, str(bundled / "scripts" / "reader.py")],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"
    assert "contract_version" in result.stdout


def test_a_data_path_rooted_somewhere_other_than_the_file_is_not_bundled(tmp_repo):
    """The narrow rule, and why narrow is correct here.

    Only a constant derived from the module's own `__file__` is trusted. Without
    that, any constant divided by a string literal that happens to exist under
    the repository root would pull a file into the bundle - and a bundle is not
    where you want to discover a loose heuristic.
    """
    (tmp_repo / ".claude" / "elsewhere.json").write_text("{}\n")
    (tmp_repo / "scripts" / "reader.py").write_text(
        "from pathlib import Path\n"
        "SOMEWHERE = Path('/etc')\n"
        'CONF = SOMEWHERE / ".claude" / "elsewhere.json"\n'
    )
    (tmp_repo / ".claude" / "commands" / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nUses scripts/reader.py.\n"
    )
    codex_skill_sync.main(["--write"])
    bundled = tmp_repo / "codex" / "skills" / "flow-auto"
    assert not (bundled / ".claude" / "elsewhere.json").exists()


def test_an_unresolvable_library_import_refuses_rather_than_shipping(tmp_repo):
    """Skipping is what the pre-#1028 bundler effectively did.

    The artifact it produced was indistinguishable from a working one until
    someone ran it, which is why this raises instead of bundling what it can.
    """
    (tmp_repo / "scripts" / "helper.sh").write_text("#!/bin/bash\n")
    (tmp_repo / "scripts" / "absent.sh").write_text("#!/bin/bash\n")
    (tmp_repo / ".claude" / "commands" / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nUses scripts/importer.py.\n"
    )
    (tmp_repo / "scripts" / "importer.py").write_text(
        "from lib.nowhere_at_all import thing\n"
    )
    with pytest.raises(SystemExit, match="resolves to no package"):
        codex_skill_sync.main(["--write"])


def test_interpreter_bytecode_beside_a_bundled_library_is_not_stale(tmp_repo):
    """A file no commit created and the generator never wrote (#1028).

    Bundling real packages made this reachable: running a bundled script writes
    `__pycache__/*.pyc` INSIDE the bundle, and the next `--check` called each one
    `STALE: ... (no longer generated)`. Before #1028 no bundled file was ever
    imported, so the case could not arise.
    """
    codex_skill_sync.main(["--write"])
    skill = tmp_repo / "codex" / "skills" / "flow-auto"
    cache = skill / "scripts" / "__pycache__"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "helper.cpython-312.pyc").write_bytes(b"\x00\x01")
    assert codex_skill_sync.main(["--check"]) == 0


def test_real_repo_folded_top_level_commands_generated():
    # #582: the six loose top-level commands were folded into families so the
    # Codex surface actually delivers them.
    skills = ROOT / "codex" / "skills"
    for name in [
        "project-next",
        "project-lite",
        "cpp-dockers",
        "cpp-happy-check",
        "cpp-load-best-practices",
        "cpp-load-mcp-docs",
    ]:
        assert (skills / name / "SKILL.md").is_file(), f"missing generated skill {name}"


def test_real_repo_no_top_level_source_commands():
    # #582 completeness invariant: discovery globs .claude/commands/<family>/
    # only, so a top-level *.md is invisible to every drift check.
    loose = sorted(p.name for p in (ROOT / ".claude" / "commands").glob("*.md"))
    assert loose == [], f"top-level commands are invisible to packaging: {loose}"


# ---------------------------------------------------------------------------
# Unit tests on a hermetic tmp tree
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    """A minimal source tree with two families, wired into the module."""
    src = tmp_path / ".claude" / "commands"
    (src / "flow").mkdir(parents=True)
    (src / "qa").mkdir(parents=True)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    out = tmp_path / "codex" / "skills"
    out.mkdir(parents=True)

    (src / "flow" / "auto.md").write_text(
        "# Flow Auto\n\nRun /flow:eli5 then /qa:test then /cpp:init.\n"
        "Uses the EnterWorktree tool and scripts/helper.sh; also mentions\n"
        "scripts/absent.sh which does not exist.\n"
    )
    (src / "qa" / "test.md").write_text(
        "---\ndescription: QA test\nallowed-tools: Bash(make:*)\n---\n"
        "# QA Test\n\nPlain body, no Claude-only surfaces here.\n"
    )
    (scripts / "helper.sh").write_text("#!/bin/bash\necho helper\n")
    (scripts / "helper.sh").chmod(0o755)

    monkeypatch.setattr(codex_skill_sync, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(codex_skill_sync, "SOURCE_ROOT", src)
    monkeypatch.setattr(codex_skill_sync, "SCRIPTS_ROOT", scripts)
    monkeypatch.setattr(codex_skill_sync, "OUTPUT_ROOT", out)
    monkeypatch.setattr(codex_skill_sync, "FAMILIES", ["flow", "qa"])
    monkeypatch.setattr(codex_skill_sync, "EXCLUDE", {})
    return tmp_path


def _skill_md(tmp_repo: Path, skill: str) -> str:
    return (tmp_repo / "codex" / "skills" / skill / "SKILL.md").read_text()


def test_write_generates_skill_dirs(tmp_repo):
    assert codex_skill_sync.main(["--write"]) == 0
    out = tmp_repo / "codex" / "skills"
    assert (out / "flow-auto" / "SKILL.md").is_file()
    assert (out / "qa-test" / "SKILL.md").is_file()


def test_frontmatter_name_and_description(tmp_repo):
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "qa-test").splitlines()
    assert lines[0] == "---"
    assert json.loads(lines[1][len("name: "):]) == "qa-test"
    assert json.loads(lines[2][len("description: "):]) == "QA test"
    assert lines[3] == "---"
    assert lines[4].startswith(codex_skill_sync.MARKER_PREFIX)
    assert "allowed-tools" not in _skill_md(tmp_repo, "qa-test")


def test_description_fallback_title_plus_paragraph(tmp_repo):
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "flow-auto").splitlines()
    description = json.loads(lines[2][len("description: "):])
    assert description.startswith("Flow Auto - Run /flow")


def test_description_capped_with_front_loaded_trigger_words(tmp_repo):
    src = tmp_repo / ".claude" / "commands" / "qa"
    long_tail = "very " * 80
    (src / "test.md").write_text(
        f"---\ndescription: QA test triggers first {long_tail}end\n---\n# QA Test\n\nBody.\n"
    )
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "qa-test").splitlines()
    description = json.loads(lines[2][len("description: "):])
    assert description.startswith("QA test triggers first")
    assert description.endswith(" ...")
    assert len(description) <= codex_skill_sync.DESCRIPTION_MAX + len(" ...")


def test_frontmatter_stays_valid_yaml_with_hostile_description(tmp_repo):
    """Colons and quotes in the source description must not break the
    frontmatter (issue #312)."""
    src = tmp_repo / ".claude" / "commands" / "qa"
    (src / "test.md").write_text(
        '---\ndescription: QA: runs "checks" - a: b\n---\n# QA Test\n\nBody.\n'
    )
    codex_skill_sync.main(["--write"])
    lines = _skill_md(tmp_repo, "qa-test").splitlines()
    assert json.loads(lines[2][len("description: "):]) == 'QA: runs "checks" - a: b'


def test_adaptations_block_only_when_constructs_detected(tmp_repo):
    codex_skill_sync.main(["--write"])
    flow = _skill_md(tmp_repo, "flow-auto")
    qa = _skill_md(tmp_repo, "qa-test")
    assert "Codex harness adaptations" in flow
    assert "EnterWorktree" in flow  # the worktree bullet was selected
    assert "Codex harness adaptations" not in qa


def test_worktree_adaptation_carries_visible_sibling_convention(tmp_repo):
    """Issue #586: the emitted worktree guidance names the visible-sibling
    location both harnesses converged on (ADR 0003/#627; codex-power-pack#133)
    - a generic `<path>` placeholder stripped CxPP's sibling guidance on every
    refresh, so a regression back to it must fail here."""
    codex_skill_sync.main(["--write"])
    flow = _skill_md(tmp_repo, "flow-auto")
    assert "../<repo>-<branch>" in flow
    assert "$FLOW_WORKTREE_BASE/<repo>-<branch>" in flow
    assert "git worktree add <path>" not in flow


def test_referenced_script_bundled_byte_identical(tmp_repo):
    codex_skill_sync.main(["--write"])
    bundled = tmp_repo / "codex" / "skills" / "flow-auto" / "scripts" / "helper.sh"
    assert bundled.read_bytes() == (tmp_repo / "scripts" / "helper.sh").read_bytes()
    assert "bundled under `scripts/`" in _skill_md(tmp_repo, "flow-auto")
    # A reference to a script that does not exist is skipped, not an error.
    assert not (tmp_repo / "codex" / "skills" / "flow-auto" / "scripts" / "absent.sh").exists()
    # Commands referencing no scripts get no scripts/ dir at all.
    assert not (tmp_repo / "codex" / "skills" / "qa-test" / "scripts").exists()


def test_slash_refs_rewrite_only_generated_targets(tmp_repo):
    codex_skill_sync.main(["--write"])
    content = _skill_md(tmp_repo, "flow-auto")
    assert "/flow-eli5" not in content  # eli5 has no source file here
    assert "/qa-test" in content        # qa/test.md is generated
    assert "/cpp:init" in content       # unknown target left untouched


def test_slash_refs_rewrite_known_sibling(tmp_repo):
    src = tmp_repo / ".claude" / "commands" / "flow"
    (src / "eli5.md").write_text("# ELI5\n\nGate.\n")
    codex_skill_sync.main(["--write"])
    content = _skill_md(tmp_repo, "flow-auto")
    assert "/flow-eli5" in content
    assert "/flow:eli5" not in content


def test_short_body_inlines_no_reference_md(tmp_repo):
    codex_skill_sync.main(["--write"])
    skill_dir = tmp_repo / "codex" / "skills" / "qa-test"
    assert "Plain body" in _skill_md(tmp_repo, "qa-test")
    assert not (skill_dir / "reference.md").exists()


def test_long_body_splits_to_reference_md(tmp_repo):
    src = tmp_repo / ".claude" / "commands" / "qa"
    filler = "\n".join(f"Step {i}: do the thing." for i in range(200))
    (src / "test.md").write_text(f"# QA Test\n\nLong procedure.\n\n{filler}\n")
    codex_skill_sync.main(["--write"])
    skill_dir = tmp_repo / "codex" / "skills" / "qa-test"
    skill_md = _skill_md(tmp_repo, "qa-test")
    reference = (skill_dir / "reference.md").read_text()
    assert "Read `reference.md`" in skill_md
    assert "Step 199" not in skill_md
    assert "Step 199: do the thing." in reference
    assert reference.startswith(codex_skill_sync.MARKER_PREFIX)


def test_check_detects_missing_drift_stale_and_orphan(tmp_repo, capsys):
    out = tmp_repo / "codex" / "skills"
    assert codex_skill_sync.main(["--check"]) == 1  # nothing generated yet

    codex_skill_sync.main(["--write"])
    assert codex_skill_sync.main(["--check"]) == 0

    skill_md = out / "qa-test" / "SKILL.md"
    pristine = skill_md.read_text()
    skill_md.write_text(pristine + "tampered\n")
    assert codex_skill_sync.main(["--check"]) == 1
    assert "DRIFT" in capsys.readouterr().out
    skill_md.write_text(pristine)

    stale = out / "flow-auto" / "scripts" / "stale.sh"
    stale.write_text("echo stale\n")
    assert codex_skill_sync.main(["--check"]) == 1
    assert "STALE" in capsys.readouterr().out
    stale.unlink()

    orphan = out / "flow-gone"
    orphan.mkdir()
    marker = codex_skill_sync.marker_for("flow", "gone.md")
    (orphan / "SKILL.md").write_text(f"{marker}\nstale\n")
    assert codex_skill_sync.main(["--check"]) == 1
    assert "ORPHAN" in capsys.readouterr().out


def test_write_prunes_stale_files_and_managed_orphans_only(tmp_repo):
    out = tmp_repo / "codex" / "skills"
    codex_skill_sync.main(["--write"])

    stale = out / "flow-auto" / "scripts" / "stale.sh"
    stale.write_text("echo stale\n")
    orphan = out / "flow-gone"
    orphan.mkdir()
    marker = codex_skill_sync.marker_for("flow", "gone.md")
    (orphan / "SKILL.md").write_text(f"{marker}\nstale\n")
    curated = out / "flow-curated"
    curated.mkdir()
    (curated / "SKILL.md").write_text("Hand-written, no marker.\n")

    codex_skill_sync.main(["--write"])
    assert not stale.exists()
    assert not orphan.exists()
    assert (curated / "SKILL.md").is_file()


def test_curated_skill_dir_never_flagged(tmp_repo):
    out = tmp_repo / "codex" / "skills"
    curated = out / "flow-curated"
    curated.mkdir()
    (curated / "SKILL.md").write_text("Hand-written, no marker.\n")
    (curated / "notes.md").write_text("Extra curated file.\n")
    codex_skill_sync.main(["--write"])
    assert codex_skill_sync.main(["--check"]) == 0
    assert (curated / "notes.md").is_file()


def test_is_managed_sees_marker_behind_frontmatter(tmp_repo):
    codex_skill_sync.main(["--write"])
    assert codex_skill_sync.is_managed(tmp_repo / "codex" / "skills" / "qa-test")
    curated = tmp_repo / "codex" / "skills" / "curated"
    curated.mkdir()
    (curated / "SKILL.md").write_text("---\nname: x\n---\nNo marker here.\n")
    assert not codex_skill_sync.is_managed(curated)


def test_family_subset_ignores_other_families(tmp_repo):
    codex_skill_sync.main(["--write"])
    skill_md = tmp_repo / "codex" / "skills" / "qa-test" / "SKILL.md"
    skill_md.write_text(skill_md.read_text() + "tampered\n")
    # flow-only check must not look at qa outputs.
    assert codex_skill_sync.main(["--check", "flow"]) == 0
    assert codex_skill_sync.main(["--check", "qa"]) == 1


def test_unknown_family_is_usage_error(tmp_repo):
    assert codex_skill_sync.main(["--check", "nonesuch"]) == 2


def test_generation_is_deterministic(tmp_repo):
    codex_skill_sync.main(["--write"])
    out = tmp_repo / "codex" / "skills"
    first = {f.as_posix(): f.read_text() for f in out.rglob("*") if f.is_file()}
    codex_skill_sync.main(["--write"])
    second = {f.as_posix(): f.read_text() for f in out.rglob("*") if f.is_file()}
    assert first == second


# ---------------------------------------------------------------------------
# Completeness gate (#582): sources outside every family fail --check loudly
# ---------------------------------------------------------------------------


def test_completeness_flags_top_level_command(tmp_repo):
    codex_skill_sync.main(["--write"])
    (tmp_repo / ".claude" / "commands" / "stray.md").write_text("# stray\n")
    assert codex_skill_sync.main(["--check"]) == 1


def test_completeness_allows_top_level_exclusion(tmp_repo, monkeypatch):
    codex_skill_sync.main(["--write"])
    (tmp_repo / ".claude" / "commands" / "stray.md").write_text("# stray\n")
    monkeypatch.setattr(codex_skill_sync, "TOP_LEVEL_EXCLUDE", {"stray.md"})
    assert codex_skill_sync.main(["--check"]) == 0


def test_completeness_flags_unlisted_family(tmp_repo):
    codex_skill_sync.main(["--write"])
    rogue = tmp_repo / ".claude" / "commands" / "rogue"
    rogue.mkdir()
    (rogue / "x.md").write_text("# x\n")
    assert codex_skill_sync.main(["--check"]) == 1


def test_completeness_allows_unpackaged_family(tmp_repo):
    codex_skill_sync.main(["--write"])
    # `spec` is in the module-default UNPACKAGED_FAMILIES carve-out.
    spec = tmp_repo / ".claude" / "commands" / "spec"
    spec.mkdir()
    (spec / "adopt.md").write_text("# adopt\n")
    assert codex_skill_sync.main(["--check"]) == 0


# ---------------------------------------------------------------------------
# Install to the host destination (issue #575)
#
# Before #575, `--install` copytree'd with dirs_exist_ok and never removed
# anything, so a skill dropped from the repo lingered in ~/.codex/skills
# forever and Codex kept loading a skill CPP no longer ships. These pin the
# pruning half - and that the marker predicate is what protects everything
# CPP does not own. run_install() was previously untested because it writes
# to Path.home().
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Redirect the install destination into the tmp tree."""
    home = tmp_path / "home"
    dest = home / ".codex" / "skills"
    monkeypatch.setattr(codex_skill_sync, "install_dest_root", lambda: dest)
    return dest


def test_install_copies_generated_skills(tmp_repo, tmp_home):
    codex_skill_sync.main(["--write"])
    assert codex_skill_sync.main(["--install"]) == 0
    assert (tmp_home / "flow-auto" / "SKILL.md").is_file()
    assert (tmp_home / "qa-test" / "SKILL.md").is_file()


def test_install_is_idempotent(tmp_repo, tmp_home):
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    before = sorted(p.name for p in tmp_home.iterdir())
    codex_skill_sync.main(["--install"])
    assert sorted(p.name for p in tmp_home.iterdir()) == before


def test_install_prunes_orphaned_managed_skill(tmp_repo, tmp_home):
    """A skill dropped from the repo must stop loading on the host."""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    assert (tmp_home / "qa-test").is_dir()

    (tmp_repo / ".claude" / "commands" / "qa" / "test.md").unlink()
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    assert not (tmp_home / "qa-test").exists(), "orphaned generated skill survived the install"
    assert (tmp_home / "flow-auto").is_dir()


def test_install_never_touches_unmarked_skills(tmp_repo, tmp_home):
    """A skill the user wrote (or `npx skills add` installed) has no CPP marker."""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    mine = tmp_home / "my-own-skill"
    mine.mkdir()
    (mine / "SKILL.md").write_text("---\nname: mine\n---\n# Hand written, not CPP\n")
    codex_skill_sync.main(["--install"])
    assert (mine / "SKILL.md").is_file(), "a non-CPP skill was removed"


def test_install_never_touches_dotted_entries(tmp_repo, tmp_home):
    """`.system` is Codex runtime state, not a skill."""
    codex_skill_sync.main(["--write"])
    tmp_home.mkdir(parents=True, exist_ok=True)
    system = tmp_home / ".system"
    system.mkdir()
    (system / "state.json").write_text("{}\n")
    codex_skill_sync.main(["--install"])
    assert (system / "state.json").is_file()


def test_install_drops_files_removed_from_a_skill_dir(tmp_repo, tmp_home):
    """Replacing rather than merging: a file dropped upstream must not survive
    inside the installed copy."""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    stale = tmp_home / "flow-auto" / "scripts" / "gone.sh"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("#!/bin/bash\necho stale\n")
    codex_skill_sync.main(["--install"])
    assert not stale.exists(), "a file removed upstream survived inside the installed skill"


# ---------------------------------------------------------------------------
# The install is safe to OBSERVE while it runs (issue #1235)
#
# Codex lists ~/.codex/skills and then reads each SKILL.md. The pre-#1235
# install rmtree'd every managed skill and copytree'd it back, so a Codex start
# during an ordinary `make codex-install` printed one "failed to read file"
# warning per skill with nothing wrong. The observer below snapshots the tree
# after EVERY mutating call the installer makes; it is the committed negative
# control: on the rmtree-then-copytree installer it reports holes, on the
# per-skill exchange it reports none.
# ---------------------------------------------------------------------------


def _holes(dest_root: Path, must_stay: set[str]) -> list[str]:
    """What a reader listing dest_root right now would fail to read."""
    found = []
    listed = {p.name for p in dest_root.iterdir()} if dest_root.is_dir() else set()
    for name in sorted(must_stay - listed):
        found.append(f"{name}: missing")
    for name in sorted(listed):
        p = dest_root / name
        if name.startswith(".") or not p.is_dir():
            continue
        if not (p / "SKILL.md").is_file():
            found.append(f"{name}: no SKILL.md")
    return found


@pytest.fixture
def observe_install(monkeypatch):
    """Wrap every tree mutation; after each, record any hole a reader would hit."""
    seen: list[str] = []
    state = {"dest": None, "must_stay": set()}

    def watch(fn):
        def wrapped(*a, **kw):
            try:
                return fn(*a, **kw)
            finally:
                if state["dest"] is not None:
                    seen.extend(
                        f"after {fn.__name__}: {h}"
                        for h in _holes(state["dest"], state["must_stay"])
                    )
        return wrapped

    for name in ("rmtree", "copytree"):
        monkeypatch.setattr(shutil, name, watch(getattr(shutil, name)))
    monkeypatch.setattr(os, "rename", watch(os.rename))
    # Tolerant of its absence so the red run on the pre-#1235 installer fails on
    # the ASSERTION, not on an AttributeError that proves nothing.
    if hasattr(codex_skill_sync, "_exchange_dirs"):
        monkeypatch.setattr(
            codex_skill_sync, "_exchange_dirs", watch(codex_skill_sync._exchange_dirs)
        )

    def arm(dest_root: Path, must_stay: set[str]):
        state["dest"], state["must_stay"] = dest_root, must_stay
        seen.clear()
        return seen

    return arm


@pytest.fixture
def exchange_supported(tmp_path):
    """Establish RENAME_EXCHANGE support INDEPENDENTLY of the install under test.

    Three outcomes, kept apart (counter-model review): a missing binding on
    Linux is a FAILURE of this code; an errno the kernel/filesystem uses to say
    "unsupported" is a SKIP naming that errno; anything else is a failure. A
    plain `sys.platform` gate would conflate the first two.
    """
    if not sys.platform.startswith("linux"):
        pytest.skip("renameat2 is Linux-only; the reported fallback is covered separately")
    a, b = tmp_path / "probe-a", tmp_path / "probe-b"
    a.mkdir()
    b.mkdir()
    err = codex_skill_sync._renameat2_exchange(a, b)
    if err is None:
        pytest.fail("Linux, but the renameat2 binding could not be loaded")
    if err in codex_skill_sync._EXCHANGE_UNSUPPORTED:
        pytest.skip(f"RENAME_EXCHANGE unsupported here ({errno.errorcode.get(err, err)})")
    assert err == 0, f"renameat2 failed: {os.strerror(err)}"


def test_reinstall_never_shows_a_reader_a_hole(
    tmp_repo, tmp_home, observe_install, exchange_supported
):
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    installed = {p.name for p in tmp_home.iterdir()}
    assert len(installed) > 1, "the control needs skills to replace"

    holes = observe_install(tmp_home, installed)
    assert codex_skill_sync.main(["--install"]) == 0
    assert holes == [], "a concurrent reader would have hit:\n" + "\n".join(holes[:10])


def test_the_observer_sees_the_pre_1235_installer(tmp_repo, tmp_home, observe_install):
    """Negative control for the test above: the SAME observer, over the
    rmtree-then-copytree replace #1235 removed, must report holes. Without this
    an observer that never looks would pass the test above just as well."""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    installed = {p.name for p in tmp_home.iterdir()}

    holes = observe_install(tmp_home, installed)
    for d in sorted(codex_skill_sync.OUTPUT_ROOT.iterdir()):
        dest = tmp_home / d.name
        shutil.rmtree(dest)
        shutil.copytree(d, dest, dirs_exist_ok=True)
    assert any(h.endswith(": missing") for h in holes), holes[:5]


def test_exchange_dirs_really_swaps(tmp_path, exchange_supported):
    """Guards the ctypes binding itself: a binding returning success without
    swapping would pass the probe and fail here on the contents."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "A").write_text("a")
    (b / "B").write_text("b")
    assert codex_skill_sync._exchange_dirs(a, b) is True
    assert [p.name for p in a.iterdir()] == ["B"]
    assert [p.name for p in b.iterdir()] == ["A"]


def test_fallback_is_reported_and_still_converges(tmp_repo, tmp_home, monkeypatch, capsys):
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    stale = tmp_home / "flow-auto" / "scripts" / "gone.sh"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale\n")
    capsys.readouterr()

    monkeypatch.setattr(codex_skill_sync, "_exchange_dirs", lambda a, b: False)
    assert codex_skill_sync.main(["--install"]) == 0
    out = capsys.readouterr().out
    assert "written NON-atomically" in out
    assert "exchange is unavailable" in out
    assert not stale.exists(), "the fallback must still replace, not merge"
    assert (tmp_home / "flow-auto" / "SKILL.md").is_file()


def test_atomic_install_prints_no_fallback_note(tmp_repo, tmp_home, capsys, exchange_supported):
    """The other half of the report: the note must not appear on the good path,
    or it is noise nobody reads."""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    capsys.readouterr()
    codex_skill_sync.main(["--install"])
    assert "NON-atomically" not in capsys.readouterr().out


def test_merge_into_an_unmarked_dir_is_reported_non_atomic(tmp_repo, tmp_home, capsys):
    """The unmarked-dir merge overwrites files in place; it must not count as
    atomic just because it deletes nothing (counter-model review)."""
    codex_skill_sync.main(["--write"])
    theirs = tmp_home / "flow-auto"
    theirs.mkdir(parents=True)
    (theirs / "SKILL.md").write_text("---\nname: flow-auto\n---\n# not CPP's\n")
    assert not codex_skill_sync.is_managed(theirs), "precondition: an UNMARKED dir"
    codex_skill_sync.main(["--install"])
    out = capsys.readouterr().out
    assert "merged into an existing dir without the CPP marker" in out
    assert "flow-auto" in out.split("NON-atomically", 1)[1]


def test_exdev_on_same_device_falls_back_and_says_so(tmp_repo, tmp_home, monkeypatch, capsys):
    """Equal st_dev is not proof a rename works: a same-filesystem bind mount
    still refuses with EXDEV. New skills, replacements and orphans must all
    fall back to copy/delete, and the note must name EXDEV (counter-model
    review)."""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    # An orphan: a MANAGED dir no source feeds any more.
    orphan = tmp_home / "zz-dropped-upstream"
    shutil.copytree(tmp_home / "flow-auto", orphan)
    assert codex_skill_sync.is_managed(orphan), "precondition: the orphan is CPP's"
    stale = tmp_home / "flow-auto" / "scripts" / "gone.sh"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale\n")
    brand_new = tmp_home / "qa-test"
    shutil.rmtree(brand_new)  # so one skill takes the new-skill path
    capsys.readouterr()

    real_rename = os.rename

    def cross_mount(src, dst, *a, **kw):
        if tmp_home in Path(dst).parents or tmp_home in Path(src).parents:
            raise OSError(errno.EXDEV, os.strerror(errno.EXDEV), str(src))
        return real_rename(src, dst, *a, **kw)

    monkeypatch.setattr(os, "rename", cross_mount)
    monkeypatch.setattr(codex_skill_sync, "_exchange_dirs", lambda a, b: False)
    assert codex_skill_sync.main(["--install"]) == 0
    out = capsys.readouterr().out
    assert "EXDEV" in out
    assert not orphan.exists(), "the orphan must still be pruned"
    assert (brand_new / "SKILL.md").is_file(), "the new skill must still arrive"
    assert not stale.exists(), "the replacement must still replace, not merge"


def test_orphan_deleted_in_place_is_reported_on_its_own(tmp_repo, tmp_home, monkeypatch, capsys):
    """An orphan-only install whose rename is refused must produce its OWN
    note - no skill write is degraded here, so nothing else can supply one
    (counter-model review, pass 2)."""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    orphan = tmp_home / "zz-dropped-upstream"
    shutil.copytree(tmp_home / "flow-auto", orphan)
    assert codex_skill_sync.is_managed(orphan), "precondition: the orphan is CPP's"
    capsys.readouterr()

    real_rename = os.rename

    def refuse_orphan(src, dst, *a, **kw):
        if Path(src) == orphan:
            raise OSError(errno.EXDEV, os.strerror(errno.EXDEV), str(src))
        return real_rename(src, dst, *a, **kw)

    monkeypatch.setattr(os, "rename", refuse_orphan)
    assert codex_skill_sync.main(["--install"]) == 0
    out = capsys.readouterr().out
    assert not orphan.exists()
    assert "written NON-atomically" not in out, "precondition: no skill write degraded"
    assert "1 orphan(s) deleted IN PLACE" in out
    assert "zz-dropped-upstream" in out


def test_a_second_installer_waits_for_the_first(tmp_repo, tmp_home):
    """Every installer shares one staging dir, so an unserialized second run
    would read a live run's scratch as a crashed run's and delete it (the HIGH
    counter-model finding). While the lock is held, an install must not start."""
    import fcntl
    import threading

    codex_skill_sync.main(["--write"])
    tmp_home.mkdir(parents=True, exist_ok=True)
    result: list[int] = []
    with open(codex_skill_sync.install_lock_path(tmp_home), "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        t = threading.Thread(target=lambda: result.append(codex_skill_sync.main(["--install"])))
        t.start()
        t.join(timeout=1.0)
        assert t.is_alive() and result == [], f"the install ran while another held the lock: {result}"
        fcntl.flock(fh, fcntl.LOCK_UN)
    t.join(timeout=30)
    assert result == [0]
    assert (tmp_home / "flow-auto" / "SKILL.md").is_file()


def test_staging_is_a_sibling_and_is_cleaned_including_a_crash_leftover(tmp_repo, tmp_home):
    codex_skill_sync.main(["--write"])
    staging = codex_skill_sync.install_staging_root(tmp_home)
    assert staging.parent == tmp_home.parent, "staging inside skills/ is listable by Codex"
    leftover = staging / "new-flow-auto"
    leftover.mkdir(parents=True)
    (leftover / "SKILL.md").write_text("half-built by a run that died\n")

    assert codex_skill_sync.main(["--install"]) == 0
    assert not staging.exists()
    assert not any(p.name.startswith((".cpp", "new-", "old-")) for p in tmp_home.iterdir())


def test_nothing_is_deleted_in_place_inside_the_install_tree(tmp_repo, tmp_home, monkeypatch):
    """rmtree is not atomic: a dir it is walking is listable with its SKILL.md
    already gone. So every deletion - the replaced copy AND a pruned orphan -
    must happen after a rename has taken it out of the listing. (A reader that
    listed an orphan BEFORE that rename still finds it gone - inherent to
    removing a skill, #1235.)"""
    codex_skill_sync.main(["--write"])
    codex_skill_sync.main(["--install"])
    (tmp_repo / ".claude" / "commands" / "qa" / "test.md").unlink()
    codex_skill_sync.main(["--write"])

    deleted: list[Path] = []
    real_rmtree = shutil.rmtree

    def recording_rmtree(path, *a, **kw):
        deleted.append(Path(path))
        return real_rmtree(path, *a, **kw)

    monkeypatch.setattr(shutil, "rmtree", recording_rmtree)
    codex_skill_sync.main(["--install"])
    assert not (tmp_home / "qa-test").exists()
    assert deleted, "the control needs the install to delete something"
    in_place = [p for p in deleted if p.parent == tmp_home]
    assert in_place == [], f"deleted in place, visible to a reader: {in_place}"


# ---------------------------------------------------------------------------
# Bundled canonical guidance (issue #861)
#
# The bundler discovered `scripts/<name>` references but not documentation, so
# a command routing to `[the issue contract](../../../docs/agents/issue-contract.md)`
# published that link verbatim into its generated skill. Inside this checkout it
# happens to resolve, because `codex/skills/<skill>/` sits exactly three levels
# below the repo root - which is why the defect was invisible from the repo. From
# `~/.codex/skills/flow-auto/reference.md` the same link resolves to
# `~/docs/agents/issue-contract.md`, i.e. to nothing, and the installed workflow
# cannot reach the canonical rule it is told to follow without borrowing a CPP
# checkout it may not have.
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo_docs(tmp_path, monkeypatch):
    """A source tree whose command links canonical docs. Separate from tmp_repo
    so the doc cases cannot perturb the adaptation/description pins above."""
    src = tmp_path / ".claude" / "commands"
    (src / "flow").mkdir(parents=True)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    docs = tmp_path / "docs" / "agents"
    docs.mkdir(parents=True)
    out = tmp_path / "codex" / "skills"
    out.mkdir(parents=True)

    # contract -> lifecycle is a BARE SIBLING link, which is why bundling both at
    # the same relative path makes it resolve with no rewriting of doc contents.
    (docs / "contract.md").write_text(
        "# Contract\n\nSee the [lifecycle](lifecycle.md) for what happens after.\n"
    )
    (docs / "lifecycle.md").write_text("# Lifecycle\n\nGraduation policy.\n")
    (docs / "unlinked.md").write_text("# Unlinked\n\nNobody links this.\n")
    (src / "flow" / "auto.md").write_text(
        "# Flow Auto\n\n"
        "The canonical rule is [the contract](../../../docs/agents/contract.md).\n"
        "A stale pointer to [nothing](../../../docs/agents/gone.md) too.\n"
        "Prose mentions docs/agents/unlinked.md without linking it.\n"
    )

    monkeypatch.setattr(codex_skill_sync, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(codex_skill_sync, "SOURCE_ROOT", src)
    monkeypatch.setattr(codex_skill_sync, "SCRIPTS_ROOT", scripts)
    monkeypatch.setattr(codex_skill_sync, "DOCS_ROOT", tmp_path / "docs")
    monkeypatch.setattr(codex_skill_sync, "OUTPUT_ROOT", out)
    monkeypatch.setattr(codex_skill_sync, "FAMILIES", ["flow"])
    monkeypatch.setattr(codex_skill_sync, "EXCLUDE", {})
    return tmp_path


def _flow_auto_body(repo: Path) -> str:
    skill = repo / "codex" / "skills" / "flow-auto"
    ref = skill / "reference.md"
    return (ref if ref.is_file() else skill / "SKILL.md").read_text()


def test_linked_doc_is_bundled_byte_identical(tmp_repo_docs):
    codex_skill_sync.main(["--write"])
    bundled = tmp_repo_docs / "codex/skills/flow-auto/docs/agents/contract.md"
    source = tmp_repo_docs / "docs/agents/contract.md"

    assert bundled.read_bytes() == source.read_bytes(), (
        "the bundled copy must be byte-identical: docs/ stays the only writable "
        "source and a drift check has to be able to compare them"
    )


def test_the_published_link_points_at_the_bundled_copy(tmp_repo_docs):
    codex_skill_sync.main(["--write"])
    body = _flow_auto_body(tmp_repo_docs)

    assert "](docs/agents/contract.md)" in body
    assert "../../../docs/agents/contract.md" not in body, (
        "a source-relative link survived into the generated skill"
    )


def test_closure_follows_sibling_links_between_bundled_docs(tmp_repo_docs):
    """flow/auto.md never names lifecycle.md; contract.md does."""
    codex_skill_sync.main(["--write"])
    skill = tmp_repo_docs / "codex/skills/flow-auto"

    assert (skill / "docs/agents/lifecycle.md").is_file(), (
        "a bundled doc's own sibling link dangles unless the closure follows it"
    )


def test_closure_does_not_sweep_the_docs_tree(tmp_repo_docs):
    """Bounded closure, not a crawler: unreferenced docs stay out."""
    codex_skill_sync.main(["--write"])
    skill = tmp_repo_docs / "codex/skills/flow-auto"

    assert not (skill / "docs/agents/unlinked.md").exists()


def test_prose_mention_is_neither_bundled_nor_rewritten(tmp_repo_docs):
    """Only source-relative LINKS are the demonstrated defect.

    A bare `docs/agents/x.md` in prose was never resolvable from a skill
    directory and is not a link; rewriting it would invent a meaning it never
    had, and bundling every such mention pulled in 241KB across the tree.
    """
    codex_skill_sync.main(["--write"])
    body = _flow_auto_body(tmp_repo_docs)

    assert "Prose mentions docs/agents/unlinked.md without linking it." in body


def test_a_broken_doc_link_stays_visible(tmp_repo_docs):
    """A typo must not be silently repointed at a file that does not exist."""
    codex_skill_sync.main(["--write"])
    body = _flow_auto_body(tmp_repo_docs)

    assert "](../../../docs/agents/gone.md)" in body
    assert not (tmp_repo_docs / "codex/skills/flow-auto/docs/agents/gone.md").exists()


def test_a_command_linking_no_docs_gets_no_docs_dir(tmp_repo_docs):
    (tmp_repo_docs / ".claude/commands/flow/plain.md").write_text(
        "# Plain\n\nNo documentation references at all.\n"
    )
    codex_skill_sync.main(["--write"])

    assert not (tmp_repo_docs / "codex/skills/flow-plain/docs").exists()


def test_real_repo_bundled_docs_byte_identical():
    bundled = sorted((ROOT / "codex" / "skills").glob("*/docs/**/*.md"))
    assert bundled, "no bundled docs found; this pin is stale"
    skills = ROOT / "codex" / "skills"
    for path in bundled:
        # Anchor on the skill's own docs/ root rather than counting parents: a
        # doc bundled at the top level (docs/x.md) has one fewer level than
        # docs/agents/x.md, and a fixed parent count silently resolves it to the
        # wrong source instead of failing.
        skill_docs = skills / path.relative_to(skills).parts[0] / "docs"
        source = ROOT / "docs" / path.relative_to(skill_docs)
        assert source.is_file(), path
        assert path.read_bytes() == source.read_bytes(), path


def test_real_repo_no_generated_body_publishes_a_source_relative_doc_link():
    """Tripwire over the whole generated surface, not the skills I happened to find.

    Modelled on test_every_packaged_converter_ships_its_context_helper: the
    bundler cannot see a dependency that is not a `scripts/<name>` reference, so
    the property has to be asserted across every generated body rather than
    fixed at the one call site that surfaced it.
    """
    offenders = [
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "codex" / "skills").rglob("*.md"))
        if "](../" in path.read_text() and "/docs/" in path.read_text().split("](../")[1][:40]
    ]
    assert not offenders, (
        "these generated bodies still publish a link that resolves only inside "
        "a CPP checkout: " + ", ".join(offenders)
    )


def test_real_repo_doc_links_resolve_and_read_in_an_isolated_skill(tmp_path):
    """The acceptance check: no CPP checkout anywhere above the skill.

    Resolution alone is not enough - the file is opened and its content checked,
    because a zero-byte or wrong-file copy resolves exactly as well as the real
    one (broken-and-working-look-alike).
    """
    import re
    import shutil

    skills = sorted(p.parent for p in (ROOT / "codex" / "skills").glob("*/docs"))
    assert skills, "no skill bundles docs; this pin is stale"

    for skill in skills:
        iso = tmp_path / skill.name
        shutil.copytree(skill, iso)
        for body_path in [p for p in (iso / "SKILL.md", iso / "reference.md") if p.is_file()]:
            body = body_path.read_text()
            for rel in set(re.findall(r"\]\((docs/[^)]+\.md)\)", body)):
                target = (body_path.parent / rel).resolve()
                assert target.is_file(), f"{skill.name}: {rel} does not resolve in isolation"
                content = target.read_text()
                assert content.strip(), f"{skill.name}: {rel} resolved but is empty"
                assert content.startswith("#"), f"{skill.name}: {rel} is not the document"
                # the bundled doc's OWN links must resolve from where it now lives
                for sib in set(re.findall(r"\]\(([A-Za-z0-9._-]+\.md)\)", content)):
                    assert (target.parent / sib).is_file(), (
                        f"{skill.name}: {rel} -> {sib} dangles in isolation"
                    )


# ---------------------------------------------------------------------------
# The success line names the compared trees (issue #1029, specimen 4).
#
# `--check` printed "N skill(s) in sync", which is the line a session reaches
# for when it wants to know whether its INSTALLED skills are current - and it
# answers a different question, because both sides of the comparison live inside
# the checkout. It is a generation-parity check, and `--check` is the DEFAULT
# mode, so the wrong reading was the easy one. Measured twice, four days apart on
# two hosts: this printed its green in the same session `install-drift` reported
# `65 current, 10 stale`, and the staleness was real.
#
# A string change owes no negative control. The PAIRING TEST is that the two
# instruments' success lines can no longer be read as answering the same
# question, and that is what these pin.
# ---------------------------------------------------------------------------


def test_check_success_line_names_both_compared_trees(tmp_repo, capsys):
    codex_skill_sync.main(["--write"])
    capsys.readouterr()

    assert codex_skill_sync.main(["--check"]) == 0
    out = capsys.readouterr().out

    assert "in sync" in out
    assert "commands/<family>/" in out, "the source side must be named"
    assert "codex/skills/" in out, "the generated side must be named"
    assert "IN-CHECKOUT" in out, "the boundary is the point of the line"


def test_check_success_line_disclaims_the_install_tree(tmp_repo, capsys):
    """It must say what it did NOT look at, and send the reader somewhere real."""
    codex_skill_sync.main(["--write"])
    capsys.readouterr()

    codex_skill_sync.main(["--check"])
    out = capsys.readouterr().out

    assert "NOTHING about the installed copies" in out
    assert str(codex_skill_sync.install_dest_root()) in out
    assert "install-drift" in out, "a disclaimer with no destination is a dead end"


def test_write_success_line_does_not_claim_the_install_tree(tmp_repo, capsys):
    """`--write` regenerates the in-checkout mirror and touches no install root."""
    assert codex_skill_sync.main(["--write"]) == 0
    out = capsys.readouterr().out

    assert "codex/skills/" in out
    assert "UNCHANGED" in out
    assert "--install" in out, "name the mode that would actually update them"


def test_the_two_success_lines_cannot_be_read_as_the_same_question(
    tmp_repo, capsys
):
    """The pairing test #1029 asks for, as an assertion rather than a claim.

    `--check`'s subject is the checkout; `--install`'s subject is the host. If a
    future edit collapses them back to interchangeable wording, this reds.
    """
    codex_skill_sync.main(["--write"])
    capsys.readouterr()

    codex_skill_sync.main(["--check"])
    check_line = next(
        line
        for line in capsys.readouterr().out.splitlines()
        if "skill(s) in sync" in line
    )

    codex_skill_sync.main(["--install"])
    install_line = next(
        line
        for line in capsys.readouterr().out.splitlines()
        if "installed" in line and "skill(s)" in line
    )

    install_root = str(codex_skill_sync.install_dest_root())
    assert install_root not in check_line, (
        "the in-checkout parity line must not name the install root as its subject"
    )
    assert install_root in install_line, (
        "the one mode whose subject IS the install tree must say so"
    )


def test_a_bundled_shell_script_brings_the_library_it_sources(tmp_path: Path) -> None:
    """The generator is an instrument, so it gets its own red case (issue #1061).

    `find_bundled_libs` follows PYTHON `lib.*` imports only, so a bundled SHELL
    script's dependency was invisible. `scripts/flow-finish-gate.sh` is bundled into
    four skills and sources `scripts/gate-lib.sh`; without this the four shipped
    copies carry a gate whose library reaches none of them, and since the gate now
    REFUSES when it cannot find gate-lib, those copies would exit 2 on every
    invocation - a functional regression against main, where the gate does not
    source it at all.
    """
    mod = codex_skill_sync
    got = mod.find_bundled_shell_libs(["flow-finish-gate.sh"])
    assert "scripts/gate-lib.sh" in got, (
        "a bundled shell script must bring what it sources, or the bundle cannot start"
    )
    assert got["scripts/gate-lib.sh"].is_file()


def test_the_shell_lib_rule_does_not_widen_to_unrelated_scripts() -> None:
    """The half that catches a predicate matching too much.

    A rule that bundled a library for every script would be indistinguishable from
    a correct one on the skills that need it, and would quietly grow every other
    bundle. Asserted against a script that sources nothing.
    """
    mod = codex_skill_sync
    assert mod.find_bundled_shell_libs(["flow-vantage.sh"]) == {}, (
        "a script that sources nothing must pull in nothing"
    )
    both = mod.find_bundled_shell_libs(["flow-finish-gate.sh", "flow-vantage.sh"])
    assert set(both) == {"scripts/gate-lib.sh"}, (
        f"only the sourced library may be added; got {sorted(both)}"
    )


def test_a_source_line_the_bundler_cannot_follow_refuses(tmp_path: Path) -> None:
    """An unfollowable source RAISES rather than shipping a silently incomplete bundle.

    A source target built from a variable - `. "$_gate_lib"` - hides the filename
    from a reader that is not a shell parser. That is the exact shape of the bug
    this function fixes, so it must fail at GENERATION, where the failure is cheap,
    rather than in a distributed copy where nobody runs the suite.
    """
    mod = codex_skill_sync
    victim = mod.SCRIPTS_ROOT / "zz-unfollowable-probe.sh"
    victim.write_text('#!/usr/bin/env bash\n_x=/tmp/gate-lib.sh\n. "$_x"\n')
    try:
        with pytest.raises(SystemExit) as caught:
            mod.find_bundled_shell_libs([victim.name])
        assert "cannot resolve" in str(caught.value)
    finally:
        victim.unlink()


# --- The bundled-scripts manifest (issue #1185) -----------------------------
#
# A bundle is the one surface where "is this source authentic" stops being
# answerable by looking around: there is no checkout to compare against. The
# manifest is what a Codex host reads instead. These pin that it EXISTS, that it
# is COMPLETE, and that it MOVES when its subject does - an immobile digest list
# certifies whatever it is handed.


def test_every_bundle_with_scripts_carries_a_manifest():
    bundles = sorted((ROOT / "codex" / "skills").glob("*/scripts"))
    assert bundles, "no bundled scripts at all - this test would be vacuous"
    for scripts_dir in bundles:
        payload = [
            f for f in scripts_dir.iterdir() if f.is_file() and f.name != MANIFEST_NAME
        ]
        if not payload:
            continue
        assert (scripts_dir / MANIFEST_NAME).is_file(), (
            f"{scripts_dir} bundles {len(payload)} script(s) and no {MANIFEST_NAME}"
        )


def test_the_manifest_covers_every_script_in_its_own_bundle():
    """Completeness, not merely presence.

    A manifest listing a SUBSET is the failure mode that reads as protection:
    the installer verifies the rows it is given, reports success, and the file
    nobody listed was never compared to anything.
    """
    for manifest in sorted((ROOT / "codex" / "skills").glob("*/scripts/" + MANIFEST_NAME)):
        scripts_dir = manifest.parent
        listed = {
            line.split()[1]
            for line in manifest.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        present = {
            f.name for f in scripts_dir.iterdir() if f.is_file() and f.name != MANIFEST_NAME
        }
        assert listed == present, (
            f"{manifest}: listed-but-absent {sorted(listed - present)}, "
            f"present-but-unlisted {sorted(present - listed)}"
        )


def test_the_manifest_does_not_list_itself():
    for manifest in sorted((ROOT / "codex" / "skills").glob("*/scripts/" + MANIFEST_NAME)):
        rows = [
            line for line in manifest.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert all(line.split()[1] != MANIFEST_NAME for line in rows), manifest


def test_the_manifest_digests_match_the_bundled_bytes():
    """The generator's digest is of the CONTENT STRING; the host hashes the FILE.

    Those are the same bytes only while nothing transforms on the way to disk.
    If they ever diverge, every bundled host refuses every helper - a total,
    silent outage of the install path that no unit test of the writer alone
    would catch, because the writer would still agree with itself.
    """
    import hashlib

    checked = 0
    for manifest in sorted((ROOT / "codex" / "skills").glob("*/scripts/" + MANIFEST_NAME)):
        for line in manifest.read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            digest, name = line.split()[0], line.split()[1]
            actual = hashlib.sha256((manifest.parent / name).read_bytes()).hexdigest()
            assert actual == digest, f"{manifest.parent / name}: {actual} != {digest}"
            checked += 1
    assert checked > 0, "no manifest rows checked - this test would be vacuous"


def test_the_manifest_moves_when_a_bundled_script_changes(tmp_path: Path):
    """A digest list that does not move certifies whatever it is handed.

    THE FIRST VERSION OF THIS TEST PASSED WITHOUT ANY MUTATION (counter-model
    review, codex, LOW). It fed generate_skill's whole output back into
    scripts_manifest, and that output ALREADY contains scripts/SHA256SUMS - so
    the recomputation added a row for the manifest itself and differed from the
    original no matter what happened to the victim. The assertion held for a
    reason that had nothing to do with its subject.

    Two halves now, and the first is what makes the second mean anything: an
    UNCHANGED input must reproduce the manifest byte-for-byte. Without that, a
    "they differ" assertion cannot tell a sensitive digest from a noisy one.
    """
    files = codex_skill_sync.generate_skill(
        ROOT / ".claude" / "commands" / "flow" / "doctor.md",
        "flow",
        codex_skill_sync.generated_names(["flow"]),
    )
    before = files.get(f"scripts/{MANIFEST_NAME}")
    assert before is not None, "flow-doctor bundles scripts but produced no manifest"

    # CONTROL: unchanged in, identical out. This is the half that was missing.
    assert codex_skill_sync.scripts_manifest(dict(files)) == before, (
        "recomputing over an unchanged bundle changed the manifest, so a "
        "difference cannot be attributed to a changed script"
    )

    victim = next(
        rel for rel in files
        if rel.startswith("scripts/") and not rel.endswith(MANIFEST_NAME)
    )
    mutated = dict(files)
    mutated[victim] = files[victim] + "\n# changed\n"
    after = codex_skill_sync.scripts_manifest(mutated)
    assert after != before, f"changing {victim} did not move the manifest"

    # And the difference must be IN THE VICTIM'S ROW, not anywhere else.
    victim_name = victim.split("/", 1)[1]
    row_before = [ln for ln in before.splitlines() if ln.endswith(f"  {victim_name}")]
    row_after = [ln for ln in after.splitlines() if ln.endswith(f"  {victim_name}")]
    assert row_before and row_after and row_before != row_after, (
        f"the manifest moved but {victim_name}'s own row did not"
    )


def test_the_manifest_never_lists_itself_whatever_the_caller_passes():
    """Correctness that depends on the caller's call order is not correctness."""
    out = codex_skill_sync.scripts_manifest(
        {"scripts/a.sh": "x", f"scripts/{MANIFEST_NAME}": "whatever"}
    )
    assert out is not None
    assert all(
        line.split()[1] != MANIFEST_NAME
        for line in out.splitlines()
        if line.strip() and not line.startswith("#")
    ), out


def test_a_bundle_with_no_scripts_carries_no_empty_manifest():
    """An empty manifest and a missing one mean different things to the reader.

    The installer refuses an empty manifest as `unverifiable-source` - it
    verifies nothing - so emitting one for a skill that legitimately bundles no
    scripts would manufacture a refusal out of a normal state.
    """
    assert codex_skill_sync.scripts_manifest({"SKILL.md": "x"}) is None


# ---------------------------------------------------------------------------
# --list-mirrors: a NON-MUTATING enumeration of the mirror set (issue #1151)
#
# `--check` answers "are the mirrors in sync". It was being read for "what IS
# the mirror set", which is what declaring a lane asks - and the two agree only
# on a DIRTY tree. On a clean one `--check` names nothing at all, and the only
# way to learn the set was `--write`, which answers by changing the tree.
# ---------------------------------------------------------------------------
def test_list_mirrors_names_every_generated_path(capsys):
    """The enumeration is PINNED TO THE GENERATOR, not to a number.

    A hardcoded count would pass while the generator's scope changed underneath
    it, which is how the neighbouring re-sync trigger stayed blind (#1136). This
    compares against `expected_outputs` itself, so the two cannot drift apart.
    """
    assert codex_skill_sync.main(["--list-mirrors"]) == 0
    printed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    outputs = codex_skill_sync.expected_outputs(codex_skill_sync.FAMILIES)
    expected = sorted(
        f"codex/skills/{skill}/{rel}"
        for skill, files in outputs.items()
        for rel in files
    )
    assert sorted(printed) == expected
    assert printed, "a repository with skills must enumerate at least one mirror"


def test_list_mirrors_writes_NOTHING(capsys, monkeypatch):
    """Non-mutating is the whole point, and EQUAL VERDICTS DO NOT ESTABLISH IT.

    The first draft compared `--check` exit codes before and after. That passes
    if the enumeration rewrites identical bytes, touches an unrelated file, or
    turns one already-drifted mirror into a differently-drifted one - the verdict
    is unchanged in all three (counter-model review). It asserted a proxy for the
    property, not the property.

    So: every file under codex/skills is inventoried BY CONTENT either side, and
    every write path the generator uses is trapped. The trap is what covers the
    identical-byte rewrite that digests cannot see.
    """
    root = ROOT / "codex" / "skills"

    def inventory():
        return {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def refuse(self, *a, **kw):  # noqa: ANN001 - test double
        raise AssertionError(f"--list-mirrors wrote to {self}")

    before = inventory()
    assert before, "fixture precondition: there are mirror files to protect"

    monkeypatch.setattr(Path, "write_text", refuse)
    monkeypatch.setattr(Path, "write_bytes", refuse)
    monkeypatch.setattr(Path, "mkdir", refuse)
    monkeypatch.setattr(Path, "unlink", refuse)

    assert codex_skill_sync.main(["--list-mirrors"]) == 0
    capsys.readouterr()

    monkeypatch.undo()
    assert inventory() == before, "--list-mirrors changed the tree"


def test_list_mirrors_maps_a_bundled_script_to_every_skill_that_bundles_it(capsys):
    """A source feeds MORE THAN ONE mirror, which is the fact that makes the
    enumeration worth having - an author editing one script has no way to know
    how far it reaches.

    Pinned against the generator rather than against the numbers observed when
    this was written: the counts move as bundling changes, and a test asserting
    `2` would fail for the right reason on the wrong day.
    """
    source = "scripts/gh-pr-merge.sh"
    assert codex_skill_sync.main(["--list-mirrors", source]) == 0
    printed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    outputs = codex_skill_sync.expected_outputs(codex_skill_sync.FAMILIES)
    bundling = [skill for skill, files in outputs.items() if source in files]
    # The copy AND the manifest that travels with it - see the manifest test
    # below for why the second half is not optional.
    expected = sorted(
        [f"codex/skills/{skill}/{source}" for skill in bundling]
        + [
            f"codex/skills/{skill}/scripts/{MANIFEST_NAME}"
            for skill in bundling
            if f"scripts/{MANIFEST_NAME}" in outputs[skill]
        ]
    )
    assert printed == expected
    assert len(bundling) > 1, "this source is bundled by more than one skill"


def test_list_mirrors_maps_a_command_document_to_its_whole_skill(capsys):
    """A command document generates SKILL.md and reference.md AND pulls in
    everything else its skill bundles, so it maps to the skill, not to a path."""
    assert codex_skill_sync.main(["--list-mirrors", ".claude/commands/flow/merge.md"]) == 0
    printed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    outputs = codex_skill_sync.expected_outputs(codex_skill_sync.FAMILIES)
    expected = sorted(f"codex/skills/flow-merge/{rel}" for rel in outputs["flow-merge"])
    assert printed == expected
    assert "codex/skills/flow-merge/SKILL.md" in printed


def test_an_UNBUNDLED_source_is_named_and_NON_ZERO_not_silent(capsys):
    """THE NEGATIVE CONTROL, and the one the issue asks for by name.

    A tool built to answer "what IS the mirror set" that returned SILENCE for a
    source it does not know would reproduce the exact defect it exists to
    remove: the caller cannot tell "this feeds nothing" from "I did not
    understand your path". So an unknown source is NAMED, on stderr, with a
    non-zero verdict - and the message states that a bundled source with an
    empty mirror set cannot occur, which is what makes zero lines readable.
    """
    rc = codex_skill_sync.main(["--list-mirrors", "README.md"])
    captured = capsys.readouterr()

    assert rc != 0, "an unknown source must not report success"
    assert [ln for ln in captured.out.splitlines() if ln.strip()] == []
    assert "NOT BUNDLED: README.md" in captured.err
    assert "cannot occur" in captured.err


def test_a_bundled_and_an_unbundled_source_together_report_BOTH(capsys):
    """The two answers must not mask each other: the bundled source still
    enumerates, and the unknown one is still named and still fails."""
    rc = codex_skill_sync.main(
        ["--list-mirrors", "scripts/gh-pr-merge.sh", "README.md"]
    )
    captured = capsys.readouterr()

    assert rc != 0
    assert [ln for ln in captured.out.splitlines() if ln.strip()], (
        "the bundled source must still be enumerated alongside the unknown one"
    )
    assert "NOT BUNDLED: README.md" in captured.err


def test_list_mirrors_includes_the_MANIFEST_that_travels_with_a_script(capsys):
    """A bundled script drifts TWO files per skill, not one.

    Every skill bundling any script also carries `scripts/<MANIFEST_NAME>` over
    those scripts, so changing one script changes the copy AND the manifest.
    Measured while building this: editing `codex-skill-sync.py` drifted 2 script
    copies and their 2 manifests, and the first cut of `--list-mirrors` named
    only the 2 copies - so a lane declared from its output would have been
    short by exactly the paths that turned up as unexplained extras in
    `lane-check` twice on 2026-09-23.

    MANIFEST_NAME is read from the generator, never spelled here, for the #1185
    reason: a test carrying its own copy keeps asserting the old name.
    """
    source = "scripts/gh-pr-merge.sh"
    assert codex_skill_sync.main(["--list-mirrors", source]) == 0
    printed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    outputs = codex_skill_sync.expected_outputs(codex_skill_sync.FAMILIES)
    bundling = [s for s, files in outputs.items() if source in files]
    assert bundling, "fixture assumption: this source is bundled somewhere"

    for skill in bundling:
        assert f"codex/skills/{skill}/{source}" in printed
        if f"scripts/{MANIFEST_NAME}" in outputs[skill]:
            assert f"codex/skills/{skill}/scripts/{MANIFEST_NAME}" in printed, (
                f"the manifest travels with the script, but {skill}'s was not named"
            )


def test_list_mirrors_never_names_a_path_the_generator_would_not_produce(capsys):
    """THE OTHER SIDE of the manifest rule.

    Adding the manifest by rule rather than by asking the generator would name
    `scripts/<MANIFEST_NAME>` under skills that have no manifest at all. Every
    path this prints must exist in `expected_outputs` - otherwise a lane
    declared from it claims a file that is never written.
    """
    assert codex_skill_sync.main(["--list-mirrors", "scripts/gh-pr-merge.sh"]) == 0
    printed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    outputs = codex_skill_sync.expected_outputs(codex_skill_sync.FAMILIES)
    every_real_path = {
        f"codex/skills/{skill}/{rel}"
        for skill, files in outputs.items()
        for rel in files
    }
    assert set(printed) <= every_real_path, (
        f"named paths the generator does not produce: {sorted(set(printed) - every_real_path)}"
    )


def test_the_manifest_is_emitted_ONLY_where_the_generator_writes_one(monkeypatch, capsys):
    """THE ABSENT-MANIFEST SIDE, which the real tree cannot exercise.

    Every skill that bundles a script currently has a manifest, so a test using
    real outputs passes whether the manifest rule is conditional or
    unconditional - it cannot tell them apart (counter-model review). Removing
    the presence guard in memory left the earlier subset test green.

    This supplies outputs where one skill bundles a script WITHOUT a manifest,
    asserts that precondition before exercising the code (the negative-fixture
    rule), and requires the enumeration to emit the script alone for it.
    """
    source = "scripts/gh-pr-merge.sh"  # a real repo file, so the existence check passes
    controlled = {
        "with-manifest": {source: "body", f"scripts/{MANIFEST_NAME}": "sums"},
        "without-manifest": {source: "body"},
    }
    assert f"scripts/{MANIFEST_NAME}" not in controlled["without-manifest"], (
        "fixture precondition: this skill must bundle a script and NO manifest"
    )
    assert f"scripts/{MANIFEST_NAME}" in controlled["with-manifest"], (
        "fixture precondition: the paired skill must have one"
    )
    monkeypatch.setattr(
        codex_skill_sync, "expected_outputs", lambda selected: controlled
    )

    assert codex_skill_sync.main(["--list-mirrors", source]) == 0
    printed = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    assert f"codex/skills/with-manifest/scripts/{MANIFEST_NAME}" in printed
    assert f"codex/skills/without-manifest/scripts/{MANIFEST_NAME}" not in printed, (
        "the manifest must be emitted only where the generator writes one"
    )
    assert f"codex/skills/without-manifest/{source}" in printed


def test_repeated_and_overlapping_sources_yield_a_SET(capsys):
    """The output is a mirror SET, not a concatenation (counter-model review).

    Passing one source twice printed it twice, and two sources sharing a skill
    repeated that skill's manifest - so a caller declaring a lane from this got
    duplicates, and a count of lines meant nothing.
    """
    once = codex_skill_sync.main(["--list-mirrors", "scripts/gh-pr-merge.sh"])
    first = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    twice = codex_skill_sync.main(
        ["--list-mirrors", "scripts/gh-pr-merge.sh", "scripts/gh-pr-merge.sh"]
    )
    second = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]

    assert once == twice == 0
    assert first == second, "a repeated source must not repeat its mirrors"
    assert len(second) == len(set(second)), "the output must contain no duplicates"


def test_a_GENERATED_filename_is_not_accepted_as_a_source(capsys):
    """The generator's own OUTPUT is not INPUT (counter-model review).

    `SKILL.md`, `reference.md` and `scripts/<MANIFEST_NAME>` are synthesised
    names present in every skill's outputs, so a bare name match answered
    `--list-mirrors SKILL.md` with 74 paths and exit 0 - a confident answer to a
    question nobody can ask, which is this issue's defect wearing the other hat.
    """
    for generated in ("SKILL.md", "reference.md", f"scripts/{MANIFEST_NAME}"):
        assert not (ROOT / generated).is_file(), (
            f"fixture precondition: {generated} must not exist as a repository file"
        )
        rc = codex_skill_sync.main(["--list-mirrors", generated])
        captured = capsys.readouterr()
        assert rc != 0, f"{generated} must not report success"
        assert [ln for ln in captured.out.splitlines() if ln.strip()] == []
        assert f"NOT BUNDLED: {generated}" in captured.err


def test_a_hyphen_collision_does_not_hand_over_a_NEIGHBOURS_mirrors(capsys):
    """`<family>-<stem>` loses the boundary between its two halves.

    The nonexistent `.claude/commands/second/opinion-help.md` composes to
    `second-opinion-help`, which is a REAL skill generated from
    `.claude/commands/second-opinion/help.md`. Checking only the composed name
    returned success and named a neighbour's mirrors (counter-model review).
    """
    real = ROOT / ".claude" / "commands" / "second-opinion" / "help.md"
    assert real.is_file(), "fixture precondition: the colliding REAL source exists"
    bogus = ".claude/commands/second/opinion-help.md"
    assert not (ROOT / bogus).is_file(), "fixture precondition: the bogus path does not"

    rc = codex_skill_sync.main(["--list-mirrors", bogus])
    captured = capsys.readouterr()
    assert rc != 0
    assert [ln for ln in captured.out.splitlines() if ln.strip()] == []

    assert codex_skill_sync.main(["--list-mirrors", str(real)]) == 0
    assert [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]


def test_equivalent_spellings_of_one_source_agree(capsys):
    """Resolution, not lexical trimming (counter-model review).

    `scripts/../scripts/x` and an absolute alias are the SAME source; a lexical
    prefix strip called them unbundled while the plain spelling worked.
    """
    spellings = [
        "scripts/gh-pr-merge.sh",
        "./scripts/gh-pr-merge.sh",
        "scripts/../scripts/gh-pr-merge.sh",
        str(ROOT / "scripts" / "gh-pr-merge.sh"),
    ]
    results = []
    for spelling in spellings:
        assert codex_skill_sync.main(["--list-mirrors", spelling]) == 0, spelling
        results.append([ln for ln in capsys.readouterr().out.splitlines() if ln.strip()])
    assert all(r == results[0] for r in results), results
    assert results[0], "fixture precondition: this source has mirrors"


def test_a_path_OUTSIDE_the_repository_is_refused(capsys):
    """Containment is answered by resolution, and a path outside the tree is not
    a source here - saying so is the honest answer rather than searching for it
    and reporting nothing found."""
    rc = codex_skill_sync.main(["--list-mirrors", "/etc/hosts"])
    captured = capsys.readouterr()
    assert rc != 0
    assert [ln for ln in captured.out.splitlines() if ln.strip()] == []
    assert "NOT BUNDLED: /etc/hosts" in captured.err
