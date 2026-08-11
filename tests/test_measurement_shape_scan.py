"""Tests for scripts/measurement-shape-scan.py (issue #666).

Pins the detection floor for the #659 trap shape: a cwd-relative pathspec on a
git measurement read is flagged, while every sanctioned ref-scoped shape stays
silent. The fixtures are the literal commands from the 2026-08-11 damage
assessment plus the shapes the CLAUDE.md directive names as safe.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "measurement-shape-scan.py"

spec = importlib.util.spec_from_file_location("measurement_shape_scan", SCRIPT)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
sys.modules["measurement_shape_scan"] = mod
spec.loader.exec_module(mod)


def _warns(line: str) -> list[dict[str, str]]:
    return [f for f in mod.scan_line(line) if f["level"] == "warn"]


def _infos(line: str) -> list[dict[str, str]]:
    return [f for f in mod.scan_line(line) if f["level"] == "info"]


class TestWarnTier:
    def test_flags_the_damage_assessment_shape(self) -> None:
        found = _warns("git diff origin/main HEAD -- ui/")
        assert len(found) == 1
        assert found[0]["category"] == "relative-pathspec"
        assert found[0]["pathspec"] == "ui/"

    def test_flags_show_and_log_with_relative_pathspec(self) -> None:
        assert _warns("git show HEAD -- src/app.py")
        assert _warns("git log --oneline origin/main -- scripts/")

    def test_flags_command_embedded_in_transcript_json(self) -> None:
        line = '{"command": "git diff main dev -- lib/", "exit": 0}'
        assert _warns(line)

    def test_flags_multiple_pathspecs(self) -> None:
        found = _warns("git diff A B -- CLAUDE.md scripts/")
        assert found and found[0]["pathspec"] == "CLAUDE.md scripts/"


class TestSanctionedShapesStaySilent:
    def test_declared_root_anchors_relative_pathspec(self) -> None:
        assert not _warns("git -C /home/u/repo diff A B -- ui/")

    def test_git_dir_and_work_tree_count_as_declared(self) -> None:
        assert not _warns("git --git-dir=/r/.git diff A B -- ui/")
        assert not _warns("git --work-tree=/r diff A B -- ui/")

    def test_absolute_pathspec_is_safe(self) -> None:
        assert not _warns("git diff A B -- /home/u/repo/ui/")

    def test_pathspec_magic_is_root_anchored(self) -> None:
        assert not _warns("git diff A B -- ':(top)ui/'")
        assert not _warns("git diff A B -- :/ui")

    def test_ref_scoped_reads_without_pathspec(self) -> None:
        assert not _warns("git diff origin/main HEAD")
        assert not _warns("git show fc809d5:CLAUDE.md")
        assert not _warns("git cat-file -e HEAD:ui/app.py")

    def test_non_measurement_subcommands_ignored(self) -> None:
        assert not _warns("git checkout -- ui/")
        assert not _warns("git add -- ui/")


class TestInfoTier:
    def test_worktree_grep_is_info_not_warn(self) -> None:
        line = "git grep -n gate_policy"
        assert not _warns(line)
        found = _infos(line)
        assert found and found[0]["category"] == "worktree-grep"

    def test_ref_scoped_grep_is_silent(self) -> None:
        assert not _infos("git grep -n gate_policy origin/main")
        assert not _infos("git grep pattern HEAD")

    def test_declared_root_grep_is_silent(self) -> None:
        assert not _infos("git -C /home/u/repo grep -n gate_policy")


class TestFileScanAndCli:
    def test_scan_file_carries_location(self, tmp_path: Path) -> None:
        transcript = tmp_path / "session.md"
        transcript.write_text(
            "some prose\ngit diff origin/main HEAD -- ui/\nmore prose\n",
            encoding="utf-8",
        )
        findings = mod.scan_file(transcript)
        assert len(findings) == 1
        assert findings[0]["line"] == 2

    def test_cli_marker_counts_warns_only(self, tmp_path: Path, capsys) -> None:
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(
            '{"command": "git diff A B -- ui/"}\n{"command": "git grep -n x"}\n',
            encoding="utf-8",
        )
        rc = mod.main([str(transcript)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "MEASUREMENT_SHAPES: 1" in out

    def test_cli_json_mode(self, tmp_path: Path, capsys) -> None:
        transcript = tmp_path / "t.md"
        transcript.write_text("git diff A B -- ui/\n", encoding="utf-8")
        rc = mod.main([str(transcript), "--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out.splitlines()[0])
        assert payload["counts"] == {"warn": 1, "info": 0}
        assert payload["findings"][0]["category"] == "relative-pathspec"

    def test_unreadable_transcript_exits_2(self, tmp_path: Path, capsys) -> None:
        rc = mod.main([str(tmp_path / "missing.md")])
        assert rc == 2

    def test_clean_transcript_reports_zero(self, tmp_path: Path, capsys) -> None:
        transcript = tmp_path / "clean.md"
        transcript.write_text(
            "git -C /repo diff origin/main HEAD -- ui/\ngit status\n",
            encoding="utf-8",
        )
        rc = mod.main([str(transcript)])
        assert rc == 0
        assert "MEASUREMENT_SHAPES: 0" in capsys.readouterr().out
