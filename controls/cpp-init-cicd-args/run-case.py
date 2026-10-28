#!/usr/bin/env python3
"""Build isolated argument-source fixtures; always use the real CLI parser."""
import subprocess
import sys
import tempfile
from pathlib import Path

CALLS = ["detect --json", "check --summary", "pipeline --write", "container --write", "health --json"]


def populate(root, scenario):
    document = root / ".claude/commands/cpp/init.md"
    document.parent.mkdir(parents=True)
    commands = ["python -m lib.cicd " + args for args in CALLS]
    assert len(commands) == 5
    extra = []
    helpers = root / "scripts"
    helpers.mkdir()
    if scenario == "bad-flag":
        commands.append("python -m lib.cicd detect --no-such-flag")
    elif scenario == "bad-quoting":
        commands.append('python -m lib.cicd detect --path "unterminated')
    elif scenario == "bad-launcher":
        commands.append("not-python -m lib.cicd detect")
    elif scenario == "bad-bundle":
        commands.append('python -m lib.cicd detect "$EXTRA_ARGS"')
    elif scenario == "bad-command-expansion":
        commands.append('python -m lib.cicd "$COMMAND" --json')
    elif scenario == "bad-help":
        commands.append("python -m lib.cicd detect --help")
    elif scenario == "bad-outside-shell":
        extra.append("Run `python -m lib.cicd detect --json`.")
    elif scenario in {"bad-helper", "good-helper", "bad-python-helper", "good-python-helper"}:
        python = "python" in scenario
        name = "child.py" if python else "child.sh"
        args = "--no-such-flag" if scenario.startswith("bad-") else "--json"
        helper = helpers / name
        if python:
            helper.write_text(
                'import subprocess\nsubprocess.run(["python", "-m", "lib.cicd", "detect", "' + args + '"])\n'
            )
            commands.append('python3 "$CPP_DIR/scripts/' + name + '"')
        else:
            helper.write_text("#!/bin/sh\npython -m lib.cicd detect " + args + "\n")
            commands.append('bash "$CPP_DIR/scripts/' + name + '"')
        assert helper.is_file(), "fixture helper must exist"
    elif scenario == "bad-empty":
        commands = []
    elif scenario == "bad-floor":
        commands = commands[:1]
    elif scenario == "bad-after-redirection":
        commands.append("python -m lib.cicd detect 2>/dev/null --no-such-flag")
    elif scenario == "good-punctuation":
        commands.append('python -m lib.cicd detect --path ";" --json')
    elif scenario == "good-numeric-redirection":
        commands.append("python -m lib.cicd detect --path 2 > /dev/null")
    elif scenario == "bad-singlequoted-choice":
        commands.append("python -m lib.cicd pipeline --provider '$PROVIDER'")
    elif scenario == "good-dynamic-choice":
        commands.append('python -m lib.cicd pipeline --provider "$PROVIDER"')
    elif scenario == "good-inlinecomment":
        commands.append("true # python -m lib.cicd detect --no-such-flag")
    elif scenario == "bad-live-with-comment":
        commands.append("python -m lib.cicd detect --no-such-flag # old spelling")
    elif scenario == "good-neighbor":
        commands.append("python -m lib.cicd_other detect --no-such-flag")
    elif scenario in {"bad-quoted-heredoc", "bad-comment-heredoc"}:
        commands.append('echo "<<DATA"' if scenario == "bad-quoted-heredoc" else "true # <<DATA")
        commands.append("python -m lib.cicd detect --no-such-flag")
    elif scenario in {"bad-assigned-python", "good-python-docstring"}:
        helper = helpers / "assigned.py"
        code = ('import subprocess\ncmd = "python -m lib.cicd detect --json"\n'
                'subprocess.run(cmd, shell=True)\n')
        if scenario == "good-python-docstring":
            code = '\"\"\"Example: python -m lib.cicd detect --no-such-flag\"\"\"\n'
        helper.write_text(code)
        commands.append('python3 "$CPP_DIR/scripts/assigned.py"')
    elif scenario in {"bad-sibling", "good-sibling", "bad-scriptdir-root"}:
        parent = helpers / "parent.sh"
        if scenario == "bad-scriptdir-root":
            parent.write_text('SCRIPT_DIR="$PWD/foreign"\nbash "$SCRIPT_DIR/scripts/child.sh"\n')
            (helpers / "child.sh").write_text("python -m lib.cicd detect --json\n")
            nested = helpers / "scripts"
            nested.mkdir()
            (nested / "child.sh").write_text("python -m lib.cicd detect --json\n")
        else:
            parent.write_text('SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\n'
                              'bash "$SCRIPT_DIR/child.sh"\n')
            flag = "--no-such-flag" if scenario == "bad-sibling" else "--json"
            (helpers / "child.sh").write_text("python -m lib.cicd detect " + flag + "\n")
        commands.append('bash "$CPP_DIR/scripts/parent.sh"')
    elif scenario == "bad-unterminated-heredoc":
        commands.extend(["cat <<DATA", "body without its delimiter"])
    elif scenario == "good-multiple-heredoc":
        commands.extend(["cat <<A <<B", "first body", "A",
                         "python -m lib.cicd detect --no-such-flag", "B",
                         "python -m lib.cicd detect --json"])
    elif scenario == "good-metadata-path":
        commands.append('if [ -f "$foreign/scripts/not-a-call.sh" ]; then :; fi')
    elif scenario in {"bad-fragment-module", "good-fragment-module"}:
        flag = "--no-such-flag" if scenario.startswith("bad-") else "--json"
        commands.append("python -m lib.ci" + chr(92) + "\ncd detect " + flag)
    elif scenario == "bad-echo-compact":
        commands.append("echo ready; python -mlib.cicd detect --no-such-flag")
    elif scenario == "good-echo-commands":
        commands.append('echo ready; echo "python -mlib.cicd detect --no-such-flag"')
    elif scenario == "bad-mixed-launchers":
        commands.append("python -m lib.cicd detect --json; python -mlib.cicd detect --no-such-flag")
    elif scenario in {"bad-escaped-backslash", "good-escaped-backslash"}:
        flag = "--no-such-flag" if scenario.startswith("bad-") else "--json"
        commands.append("echo value" + chr(92) * 2 + "\npython -m lib.cicd detect " + flag)
    elif scenario == "bad-comment-continuation":
        commands.append("true # comment" + chr(92) + "\npython -m lib.cicd detect --no-such-flag")
    elif scenario == "good-module-value":
        commands.append("python -m lib.cicd detect --path lib.cicd --json")
    elif scenario == "bad-backtick-echo":
        commands.append('echo "`python -m lib.cicd detect --no-such-flag`"')
    elif scenario == "good-literal-backtick":
        commands.append("echo '`python -m lib.cicd detect --no-such-flag`'")
    elif scenario in {"bad-expanding-heredoc", "good-quoted-heredoc-substitution",
                      "good-partquoted-heredoc", "good-escaped-heredoc-substitution"}:
        opener = "cat <<DATA"
        if scenario == "good-quoted-heredoc-substitution":
            opener = "cat <<'DATA'"
        elif scenario == "good-partquoted-heredoc":
            opener = 'cat <<D"A"TA'
        body = "$(python -m lib.cicd detect --no-such-flag)"
        if scenario == "good-escaped-heredoc-substitution":
            body = chr(92) + body
        commands.extend([opener, body, "DATA"])
    elif scenario == "good-values":
        commands.append('python3 -m lib.cicd check --path "$PWD" --summary')
        commands.append('python -m lib.cicd detect --path="${PROJECT}" --json')
        commands.append('python -m lib.cicd check --path "a path with spaces" --summary')
    elif scenario == "good-continuation":
        commands.append('python -m lib.cicd check \\\n  --path "$PWD" --summary')
    elif scenario == "good-echo":
        commands.append('echo "python -m lib.cicd detect --no-such-flag"')
        commands.append('echo python -m lib.cicd detect --no-such-flag')
    elif scenario == "good-heredoc":
        commands.extend(["cat <<'DATA'", "python -m lib.cicd detect --no-such-flag", "DATA"])
    elif scenario != "good-basic":
        raise ValueError("unknown fixture " + scenario)
    document.write_text("```bash\n" + "\n".join(commands) + "\n```\n" + "\n".join(extra))
    if scenario == "bad-flag":
        assert "--no-such-flag" in document.read_text()
        assert sum("python -m lib.cicd" in line for line in commands) == 6


def main():
    gate, case = map(Path, sys.argv[1:])
    scenario = (case / "scenario.txt").read_text().strip()
    with tempfile.TemporaryDirectory(prefix="cpp-init-cicd-args-") as tmp:
        root = Path(tmp)
        populate(root, scenario)
        return subprocess.run([sys.executable, str(gate), "--root", str(root)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
