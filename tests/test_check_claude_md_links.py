from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check-claude-md-links.py"
SPEC = importlib.util.spec_from_file_location("check_claude_md_links", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
links = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = links
SPEC.loader.exec_module(links)


def test_resolving_markdown_and_named_prefix_paths_pass(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("guide", encoding="utf-8")
    source = "See [guide](docs/guide.md) and `docs/guide.md`. Run `make lint`."

    assert links.find_broken_links(tmp_path, source) == []


def test_missing_relative_markdown_link_fails(tmp_path: Path) -> None:
    source = "See [missing](docs/missing.md)."
    assert not (tmp_path / "docs" / "missing.md").exists(), "fixture link must be broken"

    findings = links.find_broken_links(tmp_path, source)

    assert [(finding.kind, finding.target) for finding in findings] == [
        ("markdown link", "docs/missing.md")
    ]


def test_missing_named_prefix_backtick_path_fails(tmp_path: Path) -> None:
    source = "Read `scripts/missing.py`, then run `git push` with `--dry-run`."
    assert not (tmp_path / "scripts" / "missing.py").exists(), "fixture path must be missing"

    findings = links.find_broken_links(tmp_path, source)

    assert [(finding.kind, finding.target) for finding in findings] == [
        ("backtick path", "scripts/missing.py")
    ]


def test_cli_fails_when_claude_md_has_no_local_pointers(tmp_path: Path, capsys) -> None:
    """#841: zero link-shaped tokens in a present CLAUDE.md must not read the
    same as a clean scan - the exit code is what make verify reads."""
    (tmp_path / "CLAUDE.md").write_text("# Title\n\nNo pointers here.\n", encoding="utf-8")
    assert links.main(["--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "no repository-local pointers" in err


def test_external_and_anchor_links_are_not_local_paths(tmp_path: Path) -> None:
    source = "[web](https://example.com/a) [section](#section) [mail](mailto:a@example.com)"

    assert links.find_broken_links(tmp_path, source) == []


def _build_agents_tree(tmp_path: Path, count: int) -> Path:
    """N files under docs/agents/, named so the set is deterministic."""
    root = tmp_path / "repo"
    agents_dir = root / "docs" / "agents"
    agents_dir.mkdir(parents=True)
    for i in range(count):
        (agents_dir / f"topic-{i}.md").write_text(f"# topic {i}\n", encoding="utf-8")
    return root


def _claude_md_naming(root: Path, names: list[str]) -> str:
    lines = "\n".join(f"- `docs/agents/{name}`" for name in names)
    return f"# Title\n\n## Project Map\n\n{lines}\n"


def test_undocumented_canonical_doc_is_a_committed_red_case(tmp_path: Path) -> None:
    """#1037 review, required fix 1: a fixture, not the live pre-fix repo state.

    The live repo's own missing-delivery-pilots.md case disappears the moment
    this PR's own CLAUDE.md fix lands, which would leave this exact check
    with no case that can ever fail again. A generated tree of the same
    shape - N files on disk, N-1 named - persists independently of whatever
    CLAUDE.md says on any future commit.
    """
    root = _build_agents_tree(tmp_path, count=8)
    named = [f"topic-{i}.md" for i in range(7)]  # one short, on purpose
    source = _claude_md_naming(root, named)

    missing, disk_count = links.find_undocumented_canonical_docs(root, source)

    assert disk_count == 8
    assert missing == ["docs/agents/topic-7.md"]


def test_all_canonical_docs_documented_passes(tmp_path: Path) -> None:
    root = _build_agents_tree(tmp_path, count=8)
    named = [f"topic-{i}.md" for i in range(8)]  # all of them
    source = _claude_md_naming(root, named)

    missing, disk_count = links.find_undocumented_canonical_docs(root, source)

    assert disk_count == 8
    assert missing == []


def test_cli_fails_on_undocumented_canonical_doc(tmp_path: Path) -> None:
    root = _build_agents_tree(tmp_path, count=8)
    named = [f"topic-{i}.md" for i in range(7)]
    (root / "CLAUDE.md").write_text(_claude_md_naming(root, named), encoding="utf-8")

    assert links.main(["--root", str(root)]) == 1


def test_cli_passes_when_every_canonical_doc_is_documented(tmp_path: Path) -> None:
    root = _build_agents_tree(tmp_path, count=8)
    named = [f"topic-{i}.md" for i in range(8)]
    (root / "CLAUDE.md").write_text(_claude_md_naming(root, named), encoding="utf-8")

    assert links.main(["--root", str(root)]) == 0


def test_too_few_agents_docs_on_disk_is_unknown_not_clean(tmp_path: Path) -> None:
    """Required fix 2's floor shape, applied here too: a shrunk or missing
    docs/agents/ must not read as "every on-disk doc is referenced" over
    zero (or too few) files."""
    root = _build_agents_tree(tmp_path, count=1)
    source = _claude_md_naming(root, ["topic-0.md"])
    (root / "CLAUDE.md").write_text(source, encoding="utf-8")

    missing, disk_count = links.find_undocumented_canonical_docs(root, source)
    assert disk_count == 1
    assert missing == []  # would read as vacuously clean without the floor

    assert links.main(["--root", str(root)]) == 2


def test_the_real_repo_documents_every_canonical_agents_doc() -> None:
    """Regression-test EXECUTION against the live tree, not a committed case
    (see test_undocumented_canonical_doc_is_a_committed_red_case for why the
    fixtures above exist independently of this one)."""
    root = Path(__file__).resolve().parent.parent
    source = (root / "CLAUDE.md").read_text(encoding="utf-8")
    missing, disk_count = links.find_undocumented_canonical_docs(root, source)
    assert disk_count >= links.MIN_CANONICAL_AGENT_DOCS
    assert missing == []
