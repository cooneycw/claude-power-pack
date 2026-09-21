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

import json
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
    for bundled in sorted((ROOT / "codex" / "skills").glob("*/scripts/*")):
        source = ROOT / "scripts" / bundled.name
        assert source.is_file(), bundled
        assert bundled.read_bytes() == source.read_bytes(), bundled


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
