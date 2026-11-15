"""A command document must not pass a helper a flag it lacks (issue #1835).

The delegated drivers' Step 3 escalation passed `--kind message` to
`flow-wave-mailbox.sh`, which has no `--kind`, so the command exited 2 and the
escalation never sent. `scripts/check-doc-helper-flags.py` compares the flags a
document writes after a `~/.claude/scripts/<helper>` path with the helper's
source. These tests pin what it reports and what it must not attribute to the
helper. Hermetic and git-free: tmp_path trees only.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "scripts/check-doc-helper-flags.py"

MAILBOX = """#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
  case "$1" in
    --to) shift ;;
    --body) shift ;;
    --*) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
"""


def tree(tmp_path: Path, doc: str, scripts: dict[str, str] | None = None) -> Path:
    (tmp_path / "scripts").mkdir(parents=True)
    for name, text in (scripts or {"mailbox.sh": MAILBOX}).items():
        (tmp_path / "scripts" / name).write_text(text)
    (tmp_path / ".claude/commands/x").mkdir(parents=True)
    (tmp_path / ".claude/commands/x/cmd.md").write_text(doc)
    return tmp_path


def run(root: Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(GATE), "--root", str(root)],
                          capture_output=True, text=True, cwd=cwd, check=False)


def test_unknown_flag_is_reported_with_doc_line_and_helper(tmp_path: Path) -> None:
    root = tree(tmp_path, "intro\n~/.claude/scripts/mailbox.sh send --to o --kind message --body b\n")
    assert "--kind" not in MAILBOX  # precondition: the flag really is unknown
    res = run(root)
    assert res.returncode == 1
    assert "UNKNOWN_FLAG: .claude/commands/x/cmd.md:2: mailbox.sh --kind" in res.stdout


def test_known_flags_pass_and_the_count_is_stated(tmp_path: Path) -> None:
    res = run(tree(tmp_path, "~/.claude/scripts/mailbox.sh send --to o --body b\n"))
    assert res.returncode == 0, res.stdout
    assert "ok - 2 flag(s) on 1 invocation(s) in 1 doc(s) checked" in res.stdout


def test_continuation_line_flags_are_checked(tmp_path: Path) -> None:
    doc = "~/.claude/scripts/mailbox.sh send \\\n  --to o \\\n  --kind m --body b\n"
    res = run(tree(tmp_path, doc))
    assert res.returncode == 1
    assert "mailbox.sh --kind" in res.stdout


def test_substitution_pipe_and_inline_span_flags_belong_to_others(tmp_path: Path) -> None:
    doc = (
        '~/.claude/scripts/mailbox.sh send --to "$(git rev-parse --show-toplevel)" --body b\n'
        "~/.claude/scripts/mailbox.sh send --to o | grep --count sent\n"
        "Run `~/.claude/scripts/mailbox.sh send --to o` and never `--kind`.\n"
    )
    res = run(tree(tmp_path, doc))
    assert res.returncode == 0, res.stdout


def test_delegate_and_computed_python_option_names_are_followed(tmp_path: Path) -> None:
    scripts = {
        "pre.sh": 'SCRIPT_DIR="$(dirname "$0")"\npython3 "$SCRIPT_DIR/pre.py" "$@"\n',
        "pre.py": "for name in ('repo', 'harness'):\n    p.add_argument('--' + name)\n",
    }
    res = run(tree(tmp_path, "~/.claude/scripts/pre.sh --repo . --harness auto\n", scripts))
    assert res.returncode == 0, res.stdout
    res = run(tree(tmp_path / "b", "~/.claude/scripts/pre.sh --nope\n", scripts))
    assert res.returncode == 1 and "pre.sh --nope" in res.stdout


def test_prefix_of_a_longer_flag_is_not_a_match(tmp_path: Path) -> None:
    scripts = {"h.sh": 'case "$1" in --kinds) ;; esac\n'}
    res = run(tree(tmp_path, "~/.claude/scripts/h.sh --kind\n", scripts))
    assert res.returncode == 1


def test_nothing_examined_is_unknown_not_ok(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    res = run(tmp_path)
    assert res.returncode == 2 and res.stdout.startswith("UNKNOWN")
    root = tree(tmp_path / "b", "~/.claude/scripts/absent.sh --x\n")
    res = run(root)
    assert res.returncode == 2 and "no resolvable helper invocation" in res.stdout


def test_runs_from_another_directory(tmp_path: Path) -> None:
    root = tree(tmp_path / "repo", "~/.claude/scripts/mailbox.sh --to o\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert run(root, cwd=elsewhere).returncode == 0


def test_the_live_repository_is_clean() -> None:
    res = subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True, check=False)
    assert res.returncode == 0, res.stdout


def test_flag_like_text_inside_a_quoted_argument_is_not_a_flag(tmp_path: Path) -> None:
    """Counter-model review on #1835: message wording must not block verify."""
    doc = '~/.claude/scripts/mailbox.sh send --to o --body "please drop --kind message"\n'
    res = run(tree(tmp_path, doc))
    assert res.returncode == 0, res.stdout


def test_quoted_hash_or_semicolon_does_not_end_the_command(tmp_path: Path) -> None:
    """Counter-model review on #1835: a flag after a quoted `#` or `;` is still checked."""
    for i, body in enumerate(('"waiting #1835"', '"a; b"', "'x | y'")):
        doc = f"~/.claude/scripts/mailbox.sh send --to o --body {body} --kind m\n"
        res = run(tree(tmp_path / str(i), doc))
        assert res.returncode == 1, (body, res.stdout)
        assert "mailbox.sh --kind" in res.stdout


def test_unquoted_separator_and_comment_still_end_the_command(tmp_path: Path) -> None:
    doc = "~/.claude/scripts/mailbox.sh send --to o # --kind is not passed\n"
    assert run(tree(tmp_path / "a", doc)).returncode == 0
    doc = "~/.claude/scripts/mailbox.sh send --to o; other --kind\n"
    assert run(tree(tmp_path / "b", doc)).returncode == 0


def test_quoted_option_value_still_checks_the_option(tmp_path: Path) -> None:
    """Counter-model review pass 2 on #1835: --kind="message" must not hide --kind."""
    res = run(tree(tmp_path / "a", '~/.claude/scripts/mailbox.sh send --to o --kind="m" --body b\n'))
    assert res.returncode == 1 and "mailbox.sh --kind" in res.stdout
    res = run(tree(tmp_path / "b", '~/.claude/scripts/mailbox.sh send --to="o" --body b\n'))
    assert res.returncode == 0, res.stdout


def test_helper_path_inside_a_quoted_argument_is_not_an_invocation(tmp_path: Path) -> None:
    """Counter-model review pass 2 on #1835: quoted message text names no command."""
    doc = '~/.claude/scripts/mailbox.sh send --to o --body "run ~/.claude/scripts/mailbox.sh --kind m"\n'
    res = run(tree(tmp_path / "a", doc))
    assert res.returncode == 0, res.stdout
    assert "1 helper path(s) inside a quoted argument" in res.stderr
    # A substitution inside double quotes IS an invocation and is still checked.
    doc = 'X="$(~/.claude/scripts/mailbox.sh --kind m)"\n'
    res = run(tree(tmp_path / "b", doc))
    assert res.returncode == 1 and "mailbox.sh --kind" in res.stdout


def test_flag_after_the_helpers_own_substitution_belongs_to_the_outer_command(tmp_path: Path) -> None:
    """#1839 shape 1: reading past the helper's closing `)` credited `echo`'s flag to it."""
    doc = "echo $(~/.claude/scripts/mailbox.sh send --to o --body b) --kind\n"
    res = run(tree(tmp_path / "a", doc))
    assert res.returncode == 0, res.stdout
    # The helper's own flags inside the substitution are still checked.
    doc = "echo $(~/.claude/scripts/mailbox.sh send --to o --kind b) --body\n"
    res = run(tree(tmp_path / "b", doc))
    assert res.returncode == 1 and "mailbox.sh --kind" in res.stdout


def test_a_quote_continued_onto_the_next_line_stays_a_quote(tmp_path: Path) -> None:
    """#1839 shape 2: quote state restarted at each physical line."""
    doc = ('~/.claude/scripts/mailbox.sh send --to o --body "Please run \\\n'
           '~/.claude/scripts/mailbox.sh --kind message"\n')
    res = run(tree(tmp_path / "a", doc))
    assert res.returncode == 0, res.stdout
    assert "1 helper path(s) inside a quoted argument" in res.stderr
    # A flag after the continued quote closes is still the helper's.
    doc = ('~/.claude/scripts/mailbox.sh send --to o --body "Please \\\n'
           'run" --kind message\n')
    res = run(tree(tmp_path / "b", doc))
    assert res.returncode == 1 and "mailbox.sh --kind" in res.stdout


def test_a_quoted_paren_inside_a_substitution_does_not_swallow_the_command(tmp_path: Path) -> None:
    """#1839 shape 3: parentheses counted without reading quotes hid --kind."""
    doc = "~/.claude/scripts/mailbox.sh send --to o --body \"$(printf '(')\" --kind message\n"
    res = run(tree(tmp_path / "a", doc))
    assert res.returncode == 1 and "mailbox.sh --kind" in res.stdout
    doc = "~/.claude/scripts/mailbox.sh send --to o --body \"$(printf ')')\" --kind message\n"
    res = run(tree(tmp_path / "b", doc))
    assert res.returncode == 1 and "mailbox.sh --kind" in res.stdout
