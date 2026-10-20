"""Pin the zero-check Final Message in the source and generated mirror (#1493)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".claude/commands/flow/check.md"
MIRROR = ROOT / "codex/skills/flow-check/reference.md"


def _assert_covers_zero(text: str, where: Path) -> None:
    final = text.split("### Final Message", 1)[1].split("## Notes", 1)[0]
    assert "CHECKS_RUN == 0" in final, f"{where}: zero checks need their own branch"
    assert final.index("CHECKS_RUN == 0") < final.index("**All pass:**")
    assert "unchecked, not a clean pass" in final, f"{where}: zero is not clean"
    assert "make lint test typecheck" in final, f"{where}: name the aggregate to run"


def test_source_command_covers_zero() -> None:
    _assert_covers_zero(SOURCE.read_text(encoding="utf-8"), SOURCE)


def test_codex_mirror_covers_zero() -> None:
    _assert_covers_zero(MIRROR.read_text(encoding="utf-8"), MIRROR)
