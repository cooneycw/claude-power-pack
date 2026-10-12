"""check-memory-supersession.py reports stale dependents of a superseded memory (#1440).

Every verdict is tested from both sides. A checker wedged at `stale` passes
every red half; a checker wedged at `clean` passes every green half; only the
pairs separate either from one that works. The cannot-decide states (`unknown`,
`unreadable`) each get a case of their own, because the failure that matters
most for this instrument is an undecidable store reading as clean.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-memory-supersession.py"
CONTROL = ROOT / "controls" / "check-memory-supersession"


def _load():
    spec = importlib.util.spec_from_file_location("check_memory_supersession", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CHECK = _load()


def _memory(root: Path, slug: str, body: str, modified: str | None = "2026-03-20",
            extra: str = "") -> Path:
    mod_line = f"  modified: {modified}T00:00:00Z\n" if modified else ""
    path = root / f"{slug}.md"
    path.write_text(
        f"---\nname: {slug}\ndescription: \"{slug}\"\nmetadata:\n  type: project\n"
        f"{mod_line}{extra}---\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _index(root: Path, *slugs: str) -> None:
    (root / "MEMORY.md").write_text(
        "".join(f"- [{s}]({s}.md) - hook\n" for s in slugs), encoding="utf-8"
    )


def _store(tmp_path: Path, dependent_modified: str | None) -> Path:
    """A superseded memory (2026-03-10) and one dependent linking to it."""
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "placement", "**Superseded 2026-03-10.** Containers only now.",
            modified="2026-03-10")
    _memory(root, "rollout", "Host until stage three, per [[placement]].",
            modified=dependent_modified)
    _index(root, "placement", "rollout")
    return root


def _run(*roots: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, str(SCRIPT)]
    for r in roots:
        args += ["--root", str(r)]
    return subprocess.run(args, capture_output=True, text=True, env=env, check=False)


def _verdict(proc: subprocess.CompletedProcess) -> str:
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("MEMORY_SUPERSESSION: ")]
    assert len(lines) == 1, proc.stdout
    return lines[0].split()[1]


# --- stale: both sides -----------------------------------------------------


def test_a_dependent_older_than_the_supersession_is_STALE(tmp_path):
    root = _store(tmp_path, "2026-02-01")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_STALE, proc.stdout
    assert _verdict(proc) == "stale"
    assert "MEMORY_SUPERSESSION_STALE:" in proc.stdout
    assert "rollout.md links [[placement]] superseded 2026-03-10" in proc.stdout


def test_a_dependent_newer_than_the_supersession_is_CLEAN(tmp_path):
    root = _store(tmp_path, "2026-03-15")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_CLEAN, proc.stdout
    assert _verdict(proc) == "clean"
    assert "MEMORY_SUPERSESSION_STALE:" not in proc.stdout


def test_clean_states_its_own_scope(tmp_path):
    """A clean verdict must not claim more than the strict marker lets it see."""
    proc = _run(_store(tmp_path, "2026-03-15"))
    assert "Supersession written only in prose is not examined" in proc.stdout
    assert "examined 2 memories; 1 of 1 store(s) fully read, 1 marked superseded" in proc.stdout


# --- the marker is strict --------------------------------------------------


def test_prose_superseded_is_NOT_a_marker(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "An earlier ruling here was superseded 2026-03-10 by a later one.",
            modified="2026-03-10")
    _memory(root, "user", "Depends on [[ruling]].", modified="2026-01-01")
    _index(root, "ruling", "user")
    # Precondition: the prose really is there and the dependent really is older,
    # so a clean verdict can only come from the marker being strict.
    assert "superseded 2026-03-10" in (root / "ruling.md").read_text()
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_CLEAN, proc.stdout
    assert "0 marked superseded" in proc.stdout


def test_the_marker_must_START_the_line(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "Note: **Superseded 2026-03-10.** quoted mid-line.",
            modified="2026-03-10")
    _memory(root, "user", "Depends on [[ruling]].", modified="2026-01-01")
    _index(root, "ruling", "user")
    assert _run(root).returncode == CHECK.EXIT_CLEAN


def test_frontmatter_superseded_key_is_a_marker(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "No body marker.", modified="2026-03-10",
            extra="  superseded: 2026-03-10\n")
    _memory(root, "user", "Depends on [[ruling]].", modified="2026-01-01")
    _index(root, "ruling", "user")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_STALE, proc.stdout


def test_the_marker_period_is_optional(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "**Superseded 2026-03-10** - containers only.", modified="2026-03-10")
    _memory(root, "user", "Depends on [[ruling]].", modified="2026-01-01")
    _index(root, "ruling", "user")
    assert _run(root).returncode == CHECK.EXIT_STALE


# --- unknown: cannot decide is never clean ---------------------------------


def test_an_UNDATED_dependent_is_unknown_not_clean(tmp_path):
    root = _store(tmp_path, None)
    assert "modified:" not in (root / "rollout.md").read_text()  # precondition
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert _verdict(proc) == "unknown"
    assert "dependent has no modified date" in proc.stdout


def test_a_SAME_DAY_dependent_is_unknown(tmp_path):
    proc = _run(_store(tmp_path, "2026-03-10"))
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert "order unknowable" in proc.stdout


def test_an_unclosed_frontmatter_is_unknown(tmp_path):
    root = _store(tmp_path, "2026-03-15")
    (root / "broken.md").write_text("---\nname: broken\nno closing fence\n", encoding="utf-8")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert "broken.md: frontmatter opened with '---' never closes" in proc.stdout


def test_an_undated_memory_that_links_nothing_superseded_is_not_unknown(tmp_path):
    """Undated is only undecidable when there is something to decide."""
    root = _store(tmp_path, "2026-03-15")
    _memory(root, "loose", "Links [[rollout]], which is not superseded.", modified=None)
    _index(root, "placement", "rollout", "loose")
    assert _run(root).returncode == CHECK.EXIT_CLEAN


# --- unreadable: examined nothing ------------------------------------------


def test_a_missing_directory_is_unreadable(tmp_path):
    proc = _run(tmp_path / "absent")
    assert proc.returncode == CHECK.EXIT_UNREADABLE, proc.stdout
    assert _verdict(proc) == "unreadable"


def test_an_EMPTY_store_is_unreadable_not_clean(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _index(root)  # an index alone is not a memory
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNREADABLE, proc.stdout
    assert "examined nothing" in proc.stdout


def test_no_default_store_is_unreadable(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    proc = _run(env=env)
    assert proc.returncode == CHECK.EXIT_UNREADABLE, proc.stdout


def test_the_default_finds_every_project_store(tmp_path):
    for project in ("-a", "-b"):
        root = tmp_path / ".claude" / "projects" / project / "memory"
        root.parent.mkdir(parents=True)
        root.mkdir()
        _memory(root, "solo", "A fact.")
        _index(root, "solo")
    proc = _run(env={**os.environ, "HOME": str(tmp_path)})
    assert proc.returncode == CHECK.EXIT_CLEAN, proc.stdout
    assert "2 of 2 store(s) fully read" in proc.stdout


def test_stale_takes_precedence_over_another_unreadable_store(tmp_path):
    stale = _store(tmp_path, "2026-02-01")
    proc = _run(stale, tmp_path / "absent")
    assert proc.returncode == CHECK.EXIT_STALE, proc.stdout
    assert "MEMORY_SUPERSESSION_UNREADABLE:" in proc.stdout


def test_unreadable_takes_precedence_over_unknown(tmp_path):
    proc = _run(_store(tmp_path, None), tmp_path / "absent")
    assert proc.returncode == CHECK.EXIT_UNREADABLE, proc.stdout


# --- scope and hygiene -----------------------------------------------------


def test_the_INDEX_is_never_a_dependent(tmp_path):
    root = _store(tmp_path, "2026-03-15")
    (root / "MEMORY.md").write_text(
        "- [placement](placement.md) [[placement]]\n- [rollout](rollout.md)\n", encoding="utf-8"
    )
    assert _run(root).returncode == CHECK.EXIT_CLEAN


def test_links_resolve_by_name_as_well_as_file_stem(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    (root / "old-filename.md").write_text(
        "---\nname: placement\nmetadata:\n  modified: 2026-03-10\n---\n\n"
        "**Superseded 2026-03-10.** Containers.\n",
        encoding="utf-8",
    )
    _memory(root, "rollout", "Per [[placement]].", modified="2026-02-01")
    _index(root, "old-filename", "rollout")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_STALE, proc.stdout
    assert "old-filename.md: name 'placement' differs from file stem" in proc.stdout


def test_hygiene_findings_are_reported_and_do_not_change_the_exit(tmp_path):
    root = _store(tmp_path, "2026-03-15")
    _memory(root, "extra", "Links [[not-written-yet]].")
    (root / "MEMORY.md").write_text(
        "- [placement](placement.md)\n- [rollout](rollout.md)\n- [gone](gone.md)\n",
        encoding="utf-8",
    )
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_CLEAN, proc.stdout
    assert "[[not-written-yet]] names no memory (dangling)" in proc.stdout
    assert "MEMORY.md: lists gone.md, which does not exist" in proc.stdout
    assert "extra.md: not listed in MEMORY.md" in proc.stdout


def test_a_self_link_is_not_its_own_dependent(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "placement", "**Superseded 2026-03-10.** See also [[placement]].",
            modified="2026-01-01")
    _index(root, "placement")
    assert _run(root).returncode == CHECK.EXIT_CLEAN


# --- the committed control's preconditions ---------------------------------


def test_control_cases_differ_ONLY_in_the_dependent(tmp_path):
    """The control's verdicts must come from the date comparison, not fixture drift."""
    cases = {p.name: p for p in (CONTROL / "cases").iterdir()}
    assert set(cases) == {"bad-stale-dependent", "good-current", "unknown-undated"}
    base = cases["good-current"]
    for name, case in cases.items():
        assert sorted(p.name for p in case.iterdir()) == sorted(p.name for p in base.iterdir())
        for f in case.iterdir():
            if f.name != "rollout-order.md":
                assert f.read_text() == (base / f.name).read_text(), (name, f.name)
    marker = CHECK.load_memory(base / "widget-placement.md").superseded
    assert marker is not None
    assert CHECK.load_memory(cases["bad-stale-dependent"] / "rollout-order.md").modified < marker
    assert CHECK.load_memory(cases["good-current"] / "rollout-order.md").modified > marker
    assert CHECK.load_memory(cases["unknown-undated"] / "rollout-order.md").modified is None
    # The prose decoy is present in every case and is not a marker.
    assert CHECK.load_memory(base / "unrelated-note.md").superseded is None
    assert "superseded" in (base / "unrelated-note.md").read_text()


# --- counter-model review findings (gpt-6.1-sol, diff-only) ----------------


def test_an_unmarked_memory_claiming_the_slug_cannot_SHADOW_a_superseded_one(tmp_path):
    """`a.md` named `placement` must not hide `placement.md`'s supersession."""
    root = _store(tmp_path, "2026-02-01")
    (root / "a.md").write_text(
        "---\nname: placement\nmetadata:\n  modified: 2026-01-01\n---\n\nNo marker.\n",
        encoding="utf-8",
    )
    _index(root, "placement", "rollout", "a")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert "claimed by a.md, placement.md" in proc.stdout
    assert "ambiguous" in proc.stdout


def test_a_superseded_NEIGHBOUR_claiming_the_slug_is_not_a_confident_stale(tmp_path):
    """The other direction: a superseded `b.md` named `rollout-target` beside an
    unmarked `rollout-target.md` must not produce a confident stale finding."""
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "rollout-target", "Current, unmarked.", modified="2026-01-01")
    (root / "b.md").write_text(
        "---\nname: rollout-target\nmetadata:\n  modified: 2026-03-10\n---\n\n"
        "**Superseded 2026-03-10.** Neighbour.\n",
        encoding="utf-8",
    )
    _memory(root, "user", "Per [[rollout-target]].", modified="2026-02-01")
    _index(root, "rollout-target", "b", "user")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert "MEMORY_SUPERSESSION_STALE:" not in proc.stdout


def test_an_ambiguous_slug_with_nothing_superseded_is_info_only(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "fact", "One.")
    (root / "c.md").write_text("---\nname: fact\n---\n\nTwo.\n", encoding="utf-8")
    _memory(root, "user", "Per [[fact]].")
    _index(root, "fact", "c", "user")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_CLEAN, proc.stdout
    assert "[[fact]] is claimed by c.md, fact.md" in proc.stdout


def test_an_INVALID_body_marker_date_is_unknown_not_clean(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "**Superseded 2026-02-30.** Containers.", modified="2026-03-10")
    _memory(root, "user", "Per [[ruling]].", modified="2026-01-01")
    _index(root, "ruling", "user")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert "marker date '2026-02-30' is not a real date" in proc.stdout


def test_an_INVALID_frontmatter_marker_date_is_unknown_not_clean(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "No body marker.", modified="2026-03-10",
            extra="  superseded: 2026-02-30\n")
    _memory(root, "user", "Per [[ruling]].", modified="2026-01-01")
    _index(root, "ruling", "user")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert "metadata.superseded: '2026-02-30' is not a YYYY-MM-DD date" in proc.stdout


def test_an_unreadable_memory_FILE_makes_the_store_unreadable(tmp_path):
    """A file that cannot be read is an unseen part of the population (exit 2),
    not a seen memory whose date is undecidable (exit 3)."""
    root = _store(tmp_path, "2026-03-15")
    (root / "binary.md").write_bytes(b"\xff\xfe\x00 not utf-8")
    with pytest.raises(UnicodeDecodeError):
        (root / "binary.md").read_text(encoding="utf-8")  # precondition
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNREADABLE, proc.stdout
    assert "1 memory file(s) could not be read: binary.md" in proc.stdout
    assert "not fully examined" in proc.stdout


def test_a_stale_finding_survives_an_unreadable_file_in_the_same_store(tmp_path):
    root = _store(tmp_path, "2026-02-01")
    (root / "binary.md").write_bytes(b"\xff\xfe")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_STALE, proc.stdout
    assert "MEMORY_SUPERSESSION_UNREADABLE:" in proc.stdout


def test_the_LATEST_of_several_markers_is_the_supersession(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "**Superseded 2026-04-10.** Changed again.", modified="2026-04-10",
            extra="  superseded: 2026-03-10\n")
    _memory(root, "user", "Per [[ruling]].", modified="2026-03-20")
    _index(root, "ruling", "user")
    # The dependent postdates the frontmatter marker and predates the body one.
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_STALE, proc.stdout
    assert "superseded 2026-04-10" in proc.stdout


def test_an_invalid_marker_behind_a_valid_one_is_still_unknown(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "ruling", "**Superseded 2026-02-30.** Typo.", modified="2026-03-10",
            extra="  superseded: 2026-03-10\n")
    _memory(root, "user", "Per [[ruling]].", modified="2026-03-20")
    _index(root, "ruling", "user")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout


def test_a_dependent_that_ALSO_claims_the_slug_is_ambiguous_not_stale(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "placement", "**Superseded 2026-03-10.** Containers.", modified="2026-03-10")
    (root / "rollout.md").write_text(
        "---\nname: placement\nmetadata:\n  modified: 2026-02-01\n---\n\nPer [[placement]].\n",
        encoding="utf-8",
    )
    _index(root, "placement", "rollout")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
    assert "MEMORY_SUPERSESSION_STALE:" not in proc.stdout


def test_a_superseded_self_claimant_does_not_hide_the_ambiguity(tmp_path):
    root = tmp_path / "memory"
    root.mkdir()
    _memory(root, "fact", "Unmarked.", modified="2026-01-01")
    (root / "self.md").write_text(
        "---\nname: fact\nmetadata:\n  modified: 2026-02-01\n---\n\n"
        "**Superseded 2026-03-10.** See [[fact]].\n",
        encoding="utf-8",
    )
    _index(root, "fact", "self")
    proc = _run(root)
    assert proc.returncode == CHECK.EXIT_UNKNOWN, proc.stdout
