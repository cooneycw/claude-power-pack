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
